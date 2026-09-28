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
domain, and L5 forwards each goal and each belt setpoint to both sides. The
program never opens the counterpart's domain itself: ADR-0044 clause 3 makes the
boundary the only component with endpoints in both. `--via plant` addresses the
plant's own servers, which is a single side.

Nothing here runs inside a callback. The program is a plain loop on the main
thread that spins the node while it waits, so a blocking call cannot starve an
executor (CLAUDE.md §10).
"""

from __future__ import annotations

import time

from cite_bringup.plan import resolve_uri
from cite_bringup.program.cell_b_pick_place import Target
from cite_bringup.program.steps import StepFailed
from cite_interfaces.action import Grasp, MoveTo
from cite_interfaces.msg import ResultCode, RobotState, TwinMode
from cite_interfaces.qos import COMMAND, LATCHED
from cite_interfaces.srv import SetMode
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import Float64
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


def twin_name(name: str) -> str:
    """`/cite/cell_b/picker/move_to` -> `/cite/twin/cell_b/picker/move_to`."""
    if not name.startswith(f"{ROOT}/"):
        raise ValueError(f"{name!r} is not a name under {ROOT}/")
    return f"{TWIN_SCOPE}{name[len(ROOT):]}"


def state_topic(target: Target) -> str:
    """Return the arm's latched `RobotState` topic: `state`, in the skill server's namespace."""
    return f"{target.arm.skills.move_to.rsplit('/', 1)[0]}/state"


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


def gripper_effort_n(target: Target) -> float:
    """Return the gripper controller's own effort ceiling, from its generated configuration."""
    controller = target.arm.gripper_action.rsplit("/", 1)[0]
    document = yaml.safe_load(resolve_uri(target.arm.parameters).read_text())
    return float(document[controller]["ros__parameters"]["max_effort"])


class RosCell:
    """Drive one arm and one belt, through the twin or on the plant alone."""

    def __init__(self, target: Target, via: str) -> None:
        skills = target.arm.skills
        name = twin_name if via == "twin" else (lambda plain: plain)
        self._via = via
        self._effort_n = gripper_effort_n(target)
        self.node = Node(
            "fixed_program", parameter_overrides=[Parameter("use_sim_time", value=True)]
        )
        self._move_to = ActionClient(self.node, MoveTo, name(skills.move_to))
        self._grasp = ActionClient(self.node, Grasp, name(skills.grasp))
        self._belt = self.node.create_publisher(
            Float64, name(target.conveyor.command_topic), COMMAND
        )
        self._state_topic = state_topic(target)
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
        finally:
            self.node.destroy_subscription(subscription)
        if refusal is not None:
            raise StepFailed(refusal)

    # --------------------------------------------------------------- steps

    def move(self, pose: str) -> None:
        self._goal(self._move_to, MoveTo.Goal(named_configuration=pose), f"move to {pose}")

    def grip(self, width_m: float, expect_object: bool) -> None:
        goal = Grasp.Goal(
            width_m=width_m, max_effort_n=self._effort_n, expect_object=expect_object
        )
        self._goal(self._grasp, goal, "grip")

    def belt(self, speed_mps: float) -> None:
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

    def cancel(self) -> None:
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
        for _ in range(int(SERVER_WAIT_S / 0.1)):
            if predicate():
                return
            rclpy.spin_once(self.node, timeout_sec=0.1)
        raise StepFailed(f"no {what} after {SERVER_WAIT_S:.0f} s")
