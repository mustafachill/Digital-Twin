# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The real `Cell`: one rclpy node, on ONE domain, calling the L3 skills.

`--via twin` addresses the twin boundary's operator endpoints on the plant's
domain, and L5 forwards each goal, each belt setpoint and each track command to
both sides. The
program never opens the counterpart's domain itself: ADR-0044 clause 3 makes the
boundary the only component with endpoints in both. `--via plant` addresses the
plant's own servers, which is a single side.

Nothing here runs inside a callback. The program is a plain loop on the main
thread that spins the node while it waits, so a blocking call cannot starve an
executor (CLAUDE.md §10).
"""

from __future__ import annotations

import time

from builtin_interfaces.msg import Duration
from cite_bringup.plan import ControllerManager, Conveyor, resolve_uri, Track
from cite_bringup.program.steps import StepFailed
from cite_interfaces.action import Grasp, MoveTo
from cite_interfaces.msg import ResultCode, RobotState, TwinMode
from cite_interfaces.qos import COMMAND, LATCHED, STATE
from cite_interfaces.srv import SetMode
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
import yaml

#: The reserved twin scope, read off the one contract that states it. The
#: boundary forms `/cite/twin/<zone>/...` from a side's `/cite/<zone>/...` the
#: same way (`cite_twin.boundary.operator_endpoint`); cite_twin cannot be
#: imported here, because it depends on this package.
TWIN_SCOPE = SetMode.Request.SERVICE.rsplit("/", 1)[0]
ROOT = TWIN_SCOPE.rsplit("/", 1)[0]

#: How long to wait for a server to appear. A hang detector, not a schedule.
SERVER_WAIT_S = 60.0

#: How long one step may take before it is reported as hung, in wall seconds.
#: A motion or a grasp takes seconds; this is sized for a cell running well
#: below real time, and it bounds a failure rather than sequencing anything.
STEP_CEILING_S = 600.0

#: How long a cancel may take to be answered, in wall seconds. It runs on the
#: way out with interrupts ignored, so it is short: a hang here holds the exit.
CANCEL_CEILING_S = 30.0

#: A `wait` is in the cell's clock, which stops if Gazebo stalls; these bound it
#: in wall time so that a stalled simulator fails the step (and the belt is
#: stopped) instead of hanging the program. Generous on purpose: a windowed
#: pair on a busy host runs far below real time, and a starved one has been
#: measured at a twenty-fifth of it (CLAUDE.md §2), so 50x plus a minute
#: catches a clock that has STOPPED and never one that is merely slow.
WAIT_WALL_FACTOR = 50.0
WAIT_WALL_MARGIN_S = 60.0

#: How long a track is given to stop where it stands when a move is abandoned,
#: in the cell's clock. Short, because the carriage moves at 0.1 m/s in the real
#: program; a hold commanded with no duration would be a jump.
TRACK_HOLD_S = 0.2


def twin_name(name: str) -> str:
    """`/cite/cell_b/picker/move_to` -> `/cite/twin/cell_b/picker/move_to`."""
    if not name.startswith(f"{ROOT}/"):
        raise ValueError(f"{name!r} is not a name under {ROOT}/")
    return f"{TWIN_SCOPE}{name[len(ROOT):]}"


def state_topic(arm: ControllerManager) -> str:
    """Return the arm's latched `RobotState` topic: `state`, in the skill server's namespace."""
    return f"{arm.skills.move_to.rsplit('/', 1)[0]}/state"


def track_trajectory(track: Track, position_m: float, seconds: float) -> JointTrajectory:
    """One point, reached ``seconds`` from now in the controller's clock (ADR-0067).

    The controller interpolates from where the carriage stands, so the speed of
    the move is the distance over ``seconds``: the caller divides by the
    program's own speed, and nothing here guesses a duration.
    """
    whole = int(seconds)
    point = JointTrajectoryPoint(
        positions=[float(position_m)],
        velocities=[0.0],
        time_from_start=Duration(sec=whole, nanosec=int(round((seconds - whole) * 1e9))),
    )
    return JointTrajectory(joint_names=[track.joint], points=[point])


def holding_refusal(state: RobotState | None, topic: str) -> str | None:
    """Say why the program may not start on this arm state, or None if it may.

    The program opens with a release, and a release on an arm that holds a part
    drops it wherever the arm stands. So a held part, or no word at all about
    custody, refuses the start rather than being assumed away.
    """
    if state is None:
        return f"no RobotState on {topic} within {SERVER_WAIT_S:.0f} s; is the skill server up?"
    if state.gripper_holding:
        held = state.held_workpiece_id or "a part"
        return (
            f"{topic} says the arm is holding {held}; the program's first release "
            "would drop it where the arm stands. Take it out of the gripper first."
        )
    return None


def gripper_effort_n(arm: ControllerManager) -> float:
    """Return the gripper controller's own effort ceiling, from its generated configuration."""
    controller = arm.gripper_action.rsplit("/", 1)[0]
    document = yaml.safe_load(resolve_uri(arm.parameters).read_text())
    return float(document[controller]["ros__parameters"]["max_effort"])


class RosCell:
    """Drive one arm, its track and (for the ADR-0066 record) a belt, via the twin or not."""

    def __init__(
        self,
        arm: ControllerManager,
        via: str,
        *,
        conveyor: Conveyor | None = None,
        track: Track | None = None,
    ) -> None:
        skills = arm.skills
        name = twin_name if via == "twin" else (lambda plain: plain)
        self._via = via
        self._effort_n = gripper_effort_n(arm)
        self.node = Node(
            "fixed_program", parameter_overrides=[Parameter("use_sim_time", value=True)]
        )
        self._move_to = ActionClient(self.node, MoveTo, name(skills.move_to))
        self._grasp = ActionClient(self.node, Grasp, name(skills.grasp))
        self._belt = (
            None
            if conveyor is None
            else self.node.create_publisher(Float64, name(conveyor.command_topic), COMMAND)
        )
        # The track is commanded on its controller's own trajectory topic, through
        # the boundary's endpoint for it when via the twin, and its arrival is
        # read on this domain's joint states: the plant's, through the twin.
        self._track = track
        self._track_command = (
            None
            if track is None
            else self.node.create_publisher(JointTrajectory, name(track.command_topic), COMMAND)
        )
        self._track_position: float | None = None
        self._track_target: float | None = None
        if track is not None:
            self.node.create_subscription(
                JointState, arm.joint_state_topic, self._on_joint_state, STATE
            )
        self._state_topic = state_topic(arm)
        self._active = None
        self._sent = None

    # --------------------------------------------------------------- setup

    def enter_validated(self) -> None:
        """Put the twin in VALIDATED, where L5 routes a command to both sides."""
        client = self.node.create_client(SetMode, SetMode.Request.SERVICE)
        if not client.wait_for_service(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{SetMode.Request.SERVICE} is not served; is the pair up?")
        request = SetMode.Request(
            mode=TwinMode.MODE_VALIDATED, reason="fixed program (ADR-0066)"
        )
        response = self._until(client.call_async(request), "SetMode(VALIDATED)")
        if not response.accepted:
            raise StepFailed(f"the twin refused VALIDATED: {response.result.detail}")

    def refuse_if_holding(self) -> None:
        """Refuse to start if the arm says it holds a part (see `holding_refusal`).

        Read on THIS domain only: through the twin that is the plant's arm, and
        the counterpart's custody is not read (ADR-0066).
        """
        received: list[RobotState] = []
        subscription = self.node.create_subscription(
            RobotState, self._state_topic, received.append, LATCHED
        )
        try:
            try:
                self._until_true(lambda: bool(received), f"RobotState on {self._state_topic}")
            except StepFailed:
                pass
            refusal = holding_refusal(received[-1] if received else None, self._state_topic)
            if not received:
                publishers = self.node.count_publishers(self._state_topic)
                refusal += f" ({publishers} publisher(s) discovered)"
        finally:
            self.node.destroy_subscription(subscription)
        if refusal is not None:
            raise StepFailed(refusal)

    # --------------------------------------------------------------- steps

    def move(self, pose: str, velocity_scaling: float = 0.0) -> None:
        goal = MoveTo.Goal(named_configuration=pose, velocity_scaling=float(velocity_scaling))
        self._goal(self._move_to, goal, f"move to {pose}")

    def grip(self, width_m: float, expect_object: bool) -> None:
        goal = Grasp.Goal(
            width_m=width_m, max_effort_n=self._effort_n, expect_object=expect_object
        )
        self._goal(self._grasp, goal, "grip")

    def belt(self, speed_mps: float) -> None:
        if self._belt is None:
            raise StepFailed("this program drives no belt")
        # Asked to wait for the belt's subscriber first: a setpoint published
        # before the match reaches nobody, reliable or not (CLAUDE.md §10).
        self._until_true(
            lambda: self._belt.get_subscription_count() > 0,
            f"a subscriber on {self._belt.topic_name}",
        )
        self._belt.publish(Float64(data=float(speed_mps)))

    def wait(self, seconds: float) -> None:
        clock = self.node.get_clock()
        end = clock.now().nanoseconds + int(seconds * 1e9)
        ceiling_s = WAIT_WALL_FACTOR * seconds + WAIT_WALL_MARGIN_S
        wall_end = time.monotonic() + ceiling_s
        while clock.now().nanoseconds < end:
            if time.monotonic() > wall_end:
                raise StepFailed(
                    f"wait {seconds:.2f} s: the cell's clock did not get there in "
                    f"{ceiling_s:.0f} wall seconds; is the simulator running?"
                )
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def track(self, position_m: float, speed_mps: float) -> None:
        """Slide the carriage to ``position_m`` at ``speed_mps`` and wait for it.

        The move is one trajectory point, ``|distance| / speed`` seconds away in
        the controller's clock, so the program's speed is kept and nothing is
        timed here: the step ends when the joint state reports the carriage
        within the track's goal tolerance of the target. The wall-clock ceiling
        bounds a stalled simulator, as `wait` does (P4).
        """
        if self._track is None or self._track_command is None:
            raise StepFailed("this arm rides no track")
        if speed_mps <= 0.0:
            raise StepFailed(f"a track move at {speed_mps} m/s")
        what = f"track to {position_m * 1000:.0f} mm"
        self._until_true(
            lambda: self._track_position is not None,
            f"{self._track.joint} on the arm's joint states",
        )
        seconds = abs(position_m - self._track_position) / speed_mps
        if seconds * speed_mps <= self._track.goal_tolerance_m:
            return
        self._until_true(
            lambda: self._track_command.get_subscription_count() > 0,
            f"a subscriber on {self._track_command.topic_name}",
        )
        self._track_target = position_m
        self._track_command.publish(track_trajectory(self._track, position_m, seconds))
        ceiling_s = WAIT_WALL_FACTOR * seconds + WAIT_WALL_MARGIN_S
        wall_end = time.monotonic() + ceiling_s
        while abs(self._track_position - position_m) > self._track.goal_tolerance_m:
            if time.monotonic() > wall_end:
                raise StepFailed(
                    f"{what}: the carriage stands at {self._track_position * 1000:.1f} mm "
                    f"after {ceiling_s:.0f} wall seconds; is the controller active?"
                )
            rclpy.spin_once(self.node, timeout_sec=0.1)
        self._track_target = None

    def cancel(self) -> None:
        if self._track_target is not None and self._track_position is not None:
            # Abandoned mid-move: hold the carriage where it stands, rather than
            # leave it running to a target nobody is waiting for.
            self._track_target = None
            self._track_command.publish(
                track_trajectory(self._track, self._track_position, TRACK_HOLD_S)
            )
        handle, self._active = self._active, None
        sent, self._sent = self._sent, None
        if handle is None and sent is not None:
            # Interrupted before the server answered: the goal may still be
            # accepted, and an accepted goal nobody cancels runs to its end.
            handle = self._until(sent, "the acceptance of the goal to cancel", CANCEL_CEILING_S)
            if not handle.accepted:
                return
        if handle is not None:
            self._until(handle.cancel_goal_async(), "the cancel", CANCEL_CEILING_S)

    # --------------------------------------------------------------- mechanism

    def _on_joint_state(self, message: JointState) -> None:
        if self._track is not None and self._track.joint in message.name:
            self._track_position = message.position[message.name.index(self._track.joint)]

    def _goal(self, client: ActionClient, goal, what: str) -> None:
        if not client.wait_for_server(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{what}: {client._action_name} is not served")
        self._sent = client.send_goal_async(goal)
        handle = self._until(self._sent, f"{what}: acceptance")
        if handle.accepted:
            self._active = handle
        self._sent = None
        if not handle.accepted:
            raise StepFailed(f"{what}: {client._action_name} rejected the goal")
        wrapped = self._until(handle.get_result_async(), what)
        self._active = None
        code = wrapped.result.result
        if code.code != ResultCode.SUCCESS:
            raise StepFailed(f"{what}: result code {code.code}: {code.detail}")

    def _until(self, future, what: str, ceiling_s: float = STEP_CEILING_S):
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=ceiling_s)
        if not future.done():
            raise StepFailed(f"{what} did not finish within {ceiling_s:.0f} s")
        return future.result()

    def _until_true(self, predicate, what: str) -> None:
        # Bounded by the WALL CLOCK, never by a count of spins. `spin_once`
        # returns as soon as any callback runs, and this node subscribes to
        # `/clock` (use_sim_time), so a count of 600 spins used to be spent in
        # one to three seconds — before discovery had finished — and the program
        # then reported "nothing within 60 s" (ADR-0066).
        deadline = time.monotonic() + SERVER_WAIT_S
        while not predicate():
            if time.monotonic() > deadline:
                raise StepFailed(f"no {what} after {SERVER_WAIT_S:.0f} s")
            rclpy.spin_once(self.node, timeout_sec=0.1)
