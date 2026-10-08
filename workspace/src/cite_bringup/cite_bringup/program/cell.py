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
executor (CLAUDE.md §10). The operator console (ADR-0071) runs the same loop on
a worker thread of its own, and stops it through ``interrupted``: every wait
here spins through `RosCell._spin_once`, which raises `steps.Interrupted` there
once the console asks - except inside a cancel and a return to SIM, which are
the stop itself and are never cut short.
"""

from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Callable

from cite_bringup import track_command
from cite_bringup.plan import ControllerManager, Conveyor, resolve_uri, Track
from cite_bringup.program.steps import Interrupted, scaled_motion, speed_scale, StepFailed
from cite_bringup.readiness import waits_for_a_physical_side
from cite_interfaces.action import Grasp, MoveTo
from cite_interfaces.msg import ResultCode, RobotState, TwinMode
from cite_interfaces.qos import COMMAND, LATCHED, STATE
from cite_interfaces.srv import JointsAt, SetMode, TrackArrived
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from trajectory_msgs.msg import JointTrajectory
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
#: measured at a twenty-fifth of it
#: (docs/measurements/2026-08-29-real-time-factor-conditions/), so 50x plus a minute
#: catches a clock that has STOPPED and never one that is merely slow.
WAIT_WALL_FACTOR = 50.0
WAIT_WALL_MARGIN_S = 60.0

#: How long, in wall seconds, the twin may keep refusing VALIDATED because a
#: physical side is not ready yet - its deadman has not enabled the arm, or its
#: controller and joints are not publishing (ADR-0070 item 6). A ceiling on a
#: failure, not a schedule: the request is re-asked until it is accepted, and an
#: arm that is enabled at once is not delayed. It covers the deadman hearing the
#: boundary's first heartbeat, the vendor enabling the arm over the network and
#: reactivating its controllers.
PHYSICAL_SIDE_READY_CEILING_S = 120.0

#: How long one wait between two asks blocks, in wall seconds: a poll bounded by
#: the ceiling above, spent spinning this node.
_ASK_AGAIN_S = 0.5

#: How long one wait between two `TrackArrived` asks blocks, in wall seconds: a
#: poll bounded by the track step's own ceiling, spent spinning this node.
_ARRIVAL_ASK_S = 0.1

#: The longest one spin blocks while a future is awaited, in wall seconds: how
#: soon an interruption is seen. Not a schedule - `spin_once` returns on the
#: first callback - and not a ceiling, which is the caller's.
_SPIN_SLICE_S = 0.1


def twin_name(name: str) -> str:
    """`/cite/cell_b/picker/move_to` -> `/cite/twin/cell_b/picker/move_to`."""
    if not name.startswith(f"{ROOT}/"):
        raise ValueError(f"{name!r} is not a name under {ROOT}/")
    return f"{TWIN_SCOPE}{name[len(ROOT):]}"


def state_topic(arm: ControllerManager) -> str:
    """Return the arm's latched `RobotState` topic: `state`, in the skill server's namespace."""
    return f"{arm.skills.move_to.rsplit('/', 1)[0]}/state"


def track_trajectory(
    track: Track, start_m: float, position_m: float, seconds: float
) -> JointTrajectory:
    """From ``start_m`` now to ``position_m`` ``seconds`` later (ADR-0067).

    ``start_m`` is where this program read the carriage, so the speed of the
    move is the distance over ``seconds``: the caller divides by the program's
    own speed, and nothing here guesses a duration. The start point is what
    lets a physical side take the COMMANDED speed from the message
    (`cite_bringup.track_command`).
    """
    return track_command.move(track.joint, start_m, position_m, seconds)


def await_arrival(ask, pause, deadline: float, what: str, clock=time.monotonic) -> None:
    """Ask the twin whether every commanded side's track has arrived, until it has.

    SA2c-S-02 c. ``ask`` returns `(arrived, detail)`. A ceiling on a failure,
    not a schedule: the step's own wall-clock ``deadline`` bounds it, and a side
    that never arrives fails the step, which cancels and stops the program.
    """
    while True:
        arrived, detail = ask()
        if arrived:
            return
        if clock() > deadline:
            raise StepFailed(f"{what}: not every side arrived: {detail}")
        pause()


def _require_routed(answer, what: str) -> None:
    """Fail a track step the twin's mode carries no track command for (R-03).

    In SIM, REAL or SHADOW the boundary drops a track command, so an answer
    "arrived" there would end the step on a move nobody made.
    """
    if not answer.routed:
        raise StepFailed(
            f"{what}: the twin is not in a mode that routes a track command to its "
            f"sides ({answer.detail}); the step is not done"
        )


def await_heard(ask, pause, deadline: float, clock=time.monotonic):
    """Ask `TrackArrived` (or `JointsAt`) until its answer is not UNHEARD, or ``deadline`` passes.

    R-01: a physical carriage whose position the twin has not heard fresh is
    neither agreeing nor apart, so the check before the operator waits for it,
    as VALIDATED waits for the rest of the physical side. A ceiling on a
    failure, not a schedule. Returns the last answer, whatever it says.
    """
    while True:
        answer = ask()
        if answer.reason != type(answer).UNHEARD or clock() > deadline:
            return answer
        pause()


def carriage_verdict(
    answer, plant_m: float, ceiling_s: float, homing: bool = False
) -> str | None:
    """Say why the operator may not be asked in, from the twin's last answer, or None.

    AWAY never clears by itself, so it says what to do from outside the cell;
    UNHEARD is said as unheard, never as "home it" (R-04). Before a homing
    move (``homing``) AWAY is no refusal: bringing the carriages together is
    what that move does, and the start is measured again after it (ADR-0070).
    """
    if answer.reason == TrackArrived.Response.ARRIVED:
        return None
    if homing and answer.reason == TrackArrived.Response.AWAY:
        return None
    if answer.reason == TrackArrived.Response.AWAY:
        return (
            f"the physical carriage does not stand where the plant's does ({answer.detail}). "
            f"Bring the physical carriage to {plant_m * 1000:.0f} mm (home it) - from "
            "outside the cell - and run the program again; no one is asked into the cell"
        )
    if answer.reason == TrackArrived.Response.UNHEARD:
        return (
            f"the twin did not hear the physical carriage's position fresh within "
            f"{ceiling_s:.0f} s ({answer.detail}), so whether it stands where the plant's "
            "does is unknown; is the physical side up and publishing its joint states? "
            "No one is asked into the cell"
        )
    return f"the twin cannot judge the carriages ({answer.detail}); no one is asked into the cell"


def away_verdict(answer, what: str, ceiling_s: float) -> str | None:
    """Say where a side stands away from the start, from the twin's last answer, or None.

    ``answer`` is a `JointsAt` or a `TrackArrived` response, after
    `await_heard`-style waiting: a position never heard fresh is not at the
    start, and is said as unheard (ADR-0070).
    """
    if getattr(answer, "at", False) or getattr(answer, "arrived", False):
        return None
    if answer.reason == type(answer).UNHEARD:
        return f"{what}: not heard fresh within {ceiling_s:.0f} s ({answer.detail})"
    return f"{what}: {answer.detail}"


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


def ask_until_accepted(
    ask,
    pause,
    say,
    ceiling_s: float = PHYSICAL_SIDE_READY_CEILING_S,
    clock=time.monotonic,
) -> None:
    """Ask for VALIDATED until it is accepted, refused for good, or the ceiling passes.

    A physical side comes up held, and the twin refuses to command it until its
    deadman has enabled the arm and its controller and joints are publishing
    (ADR-0070 item 6). That refusal clears by itself, so it is asked again
    after ``pause``; every other refusal is final and raised at once.
    ``ask`` returns `(accepted, detail)`.
    """
    deadline = clock() + ceiling_s
    said = ""
    while True:
        accepted, detail = ask()
        if accepted:
            return
        if not waits_for_a_physical_side(detail):
            raise StepFailed(f"the twin refused VALIDATED: {detail}")
        if clock() > deadline:
            raise StepFailed(
                f"the physical side was not ready within {ceiling_s:.0f} s: {detail}"
            )
        if detail != said:
            say(f"waiting for the physical side: {detail}")
            said = detail
        pause()


def default_scaling(arm: ControllerManager) -> tuple[float, float]:
    """Return the planner's default (velocity, acceleration) scaling, from the generated limits.

    The skill server applies these when a goal says 0; a slowed program scales
    them, so it reads them where move_group does rather than restating them.
    """
    document = yaml.safe_load(arm.moveit.joint_limits.read_text()) or {}
    return (
        float(document["default_velocity_scaling_factor"]),
        float(document["default_acceleration_scaling_factor"]),
    )


def gripper_effort_n(arm: ControllerManager) -> float:
    """Return the gripper controller's own effort ceiling, from its generated configuration."""
    controller = arm.gripper_action.rsplit("/", 1)[0]
    document = yaml.safe_load(resolve_uri(arm.parameters).read_text())
    return float(document[controller]["ros__parameters"]["max_effort"])


class RosCell:
    """Drive one arm, its track and (for the ADR-0066 record) a belt, via the twin or not."""

    #: Class-level defaults of the two attributes `__init__` sets for the
    #: operator console's stop, so a cell assembled without it never stops.
    _interrupted: Callable[[], bool] | None = None
    _uninterruptible = 0

    def __init__(
        self,
        arm: ControllerManager,
        via: str,
        *,
        conveyor: Conveyor | None = None,
        track: Track | None = None,
        speed: float = 1.0,
        interrupted: Callable[[], bool] | None = None,
        node_name: str = "fixed_program",
    ) -> None:
        skills = arm.skills
        #: Asked before every spin: True stops whatever is waiting with
        #: `Interrupted` (ADR-0071). None for a terminal run, whose stop is
        #: Ctrl-C's KeyboardInterrupt on the main thread.
        self._interrupted = interrupted
        #: How deep inside a cancel or a return to SIM this cell is: there the
        #: predicate is not asked, because those ARE the stop.
        self._uninterruptible = 0
        #: The fraction of its own speed every move and every track slide runs
        #: at (`--speed-scale`). One command through the twin, so both sides run
        #: at the same fraction.
        self._speed = speed_scale(speed)
        self._default_scaling = default_scaling(arm)
        name = twin_name if via == "twin" else (lambda plain: plain)
        self._via = via
        self._effort_n = gripper_effort_n(arm)
        self.node = Node(
            node_name, parameter_overrides=[Parameter("use_sim_time", value=True)]
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
        #: Whether every commanded side's track arrived, asked of the twin.
        self._track_arrived = (
            self.node.create_client(TrackArrived, TrackArrived.Request.SERVICE)
            if track is not None and via == "twin"
            else None
        )
        #: Every joint position this domain's joint states carry, by name.
        self._positions: dict[str, float] = {}
        self.node.create_subscription(
            JointState, arm.joint_state_topic, self._on_joint_state, STATE
        )
        self._state_topic = state_topic(arm)
        self._active = None
        self._sent = None

    # --------------------------------------------------------------- setup

    def enter_validated(self, homing: bool = False) -> None:
        """Put the twin in VALIDATED, where L5 routes a command to both sides.

        ``homing`` asks it with `SetMode.homing`, for the homing move before the
        first cycle only (`program.home.bring_to_start`): the carriages may
        stand apart then, since that move is what brings them together. The
        program itself always asks without it (ADR-0070).
        """
        client = self.node.create_client(SetMode, SetMode.Request.SERVICE)
        if not client.wait_for_service(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{SetMode.Request.SERVICE} is not served; is the pair up?")
        request = SetMode.Request(
            mode=TwinMode.MODE_VALIDATED,
            reason=(
                "homing to the program's start (ADR-0070)"
                if homing
                else "fixed program (ADR-0066)"
            ),
            homing=homing,
        )

        def ask() -> tuple[bool, str]:
            response = self._until(client.call_async(request), "SetMode(VALIDATED)")
            return response.accepted, response.result.detail

        def pause() -> None:
            ask_again = time.monotonic() + _ASK_AGAIN_S
            while time.monotonic() < ask_again:
                self._spin_once(_ASK_AGAIN_S)

        ask_until_accepted(ask, pause, lambda text: print(text, flush=True))

    def leave_validated(self) -> bool:
        """Ask the twin for SIM, where no command crosses to the counterpart.

        Called when the program ends on a pair with a physical side, so the
        operator's next step - placing a part by hand - happens while the twin
        forwards nothing to the physical arm or carriage; the next run asks for
        VALIDATED again, through the opt-in and the readiness check. SIM does
        NOT disable the arm: the deadman keeps it enabled while heartbeats
        arrive, and it holds where it stands. Return whether the twin confirmed
        SIM: a refusal, a timeout or no server is said and returns False, which
        the caller makes the run's failure (SA-S-05). Never interrupted: it is
        where a stop ends on a pair with a physical side.
        """
        with self._not_interrupted():
            return self._leave_validated()

    def _leave_validated(self) -> bool:
        client = self.node.create_client(SetMode, SetMode.Request.SERVICE)
        if not client.wait_for_service(timeout_sec=SERVER_WAIT_S):
            print(f"could not leave VALIDATED: {SetMode.Request.SERVICE} is not served")
            return False
        request = SetMode.Request(
            mode=TwinMode.MODE_SIM,
            reason="the program ended; a person may enter the physical cell",
        )
        try:
            response = self._until(client.call_async(request), "SetMode(SIM)", CANCEL_CEILING_S)
        except StepFailed as failure:
            print(f"could not leave VALIDATED: {failure}", flush=True)
            return False
        if not response.accepted or response.current_mode != TwinMode.MODE_SIM:
            print(f"the twin stayed in VALIDATED: {response.result.detail}", flush=True)
            return False
        print("the twin is in SIM: nothing crosses to the physical side", flush=True)
        return True

    def twin_mode(self) -> int | None:
        """Read the twin's mode from its latched topic, or None if none is heard in time."""
        received: list[TwinMode] = []
        subscription = self.node.create_subscription(
            TwinMode, TwinMode.TOPIC, received.append, LATCHED
        )
        try:
            self._until_true(lambda: bool(received), f"TwinMode on {TwinMode.TOPIC}")
        except StepFailed:
            return None
        finally:
            self.node.destroy_subscription(subscription)
        return received[-1].mode

    def carriage_refusal(self, homing: bool = False) -> str | None:
        """Say why the operator may not be asked in, as to the carriages, or None (S-08).

        Asked in SIM, before the operator is: the twin answers `TrackArrived`
        for the plant's own track position, judging every physical carriage.
        One not heard fresh yet is waited for, within
        `PHYSICAL_SIDE_READY_CEILING_S` (R-01); one heard standing elsewhere
        never clears by itself, so it is said now, with what to do - from
        outside the cell - rather than once VALIDATED is asked of an operator
        who confirmed it clear. Never heard in time refuses too. Before a
        homing move (``homing``) a carriage apart is no refusal: that move
        brings it to the start (`carriage_verdict`).
        """
        if self._track_arrived is None or self._track is None:
            return None
        self._until_true(
            lambda: self._track_position is not None,
            f"{self._track.joint} on the arm's joint states",
        )
        plant_m = self._track_position
        answer = await_heard(
            self._ask_arrival(plant_m, "the carriages before the operator"),
            self._pause_between_asks,
            time.monotonic() + PHYSICAL_SIDE_READY_CEILING_S,
        )
        return carriage_verdict(answer, plant_m, PHYSICAL_SIDE_READY_CEILING_S, homing)

    def away_from_start(self, start) -> str | None:
        """Measure the program's start on every side; say where a side is not, or None.

        ``start`` is a `program.home.StartPose`. Through the twin every side is
        asked of the boundary - the arm with `JointsAt`, the carriage with
        `TrackArrived` - and a physical side counts only with fresh positions,
        waited for within `PHYSICAL_SIDE_READY_CEILING_S`. Via the plant alone
        this domain's own joint states are read. Nothing is commanded (ADR-0070).
        """
        if self._via != "twin":
            self._until_true(
                lambda: all(joint in self._positions for joint in start.joints)
                and (self._track is None or self._track_position is not None),
                "the arm's joints on its joint states",
            )
            return start.away_on_one_side(self._positions, self._track_position)
        deadline = time.monotonic() + PHYSICAL_SIDE_READY_CEILING_S
        found = []
        answer = await_heard(
            self._ask_joints_at(start), self._pause_between_asks, deadline
        )
        found.append(
            away_verdict(answer, f"the arm at {start.pose}", PHYSICAL_SIDE_READY_CEILING_S)
        )
        if start.track_m is not None and self._track_arrived is not None:
            what = f"the track at {start.track_m * 1000:.0f} mm"
            answer = await_heard(
                self._ask_arrival(start.track_m, what), self._pause_between_asks, deadline
            )
            found.append(away_verdict(answer, what, PHYSICAL_SIDE_READY_CEILING_S))
        found = [reason for reason in found if reason is not None]
        return "; ".join(found) if found else None

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
        velocity, acceleration = scaled_motion(
            velocity_scaling, *self._default_scaling, self._speed
        )
        goal = MoveTo.Goal(
            named_configuration=pose,
            velocity_scaling=float(velocity),
            acceleration_scaling=float(acceleration),
        )
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
            self._spin_once(0.1)

    def track(self, position_m: float, speed_mps: float) -> None:
        """Slide the carriage to ``position_m`` at ``speed_mps`` and wait for it.

        The move is one trajectory point, ``|distance| / speed`` seconds away in
        the controller's clock, so the program's speed is kept and nothing is
        timed here: the step ends when the joint state reports the carriage
        within the track's goal tolerance of the target. The wall-clock ceiling
        bounds a stalled simulator, as `wait` does (P4).

        **Through the twin, never skipped on the plant's carriage alone**
        (SA-S-01 a). Every commanded side is asked first (`TrackArrived`); the
        step is done only if every side is there. A move is commanded when the
        plant's carriage is away from the target, and the counterpart's,
        wherever it stands, runs at the same commanded speed and is waited for.
        When the plant's carriage is already there and a counterpart's is not,
        no move can be commanded - its duration is the plant's distance, which
        is none, and the boundary returns verdicts rather than positions
        (ADR-0050 decision 1b) - so the step fails and says which carriage to
        bring to the target. A twin in a mode that routes no track command -
        SIM, REAL, SHADOW - fails the step at every ask, so a drop to SIM
        mid-run is never taken for an arrival (R-03).
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
        distance = abs(position_m - self._track_position)
        plant_there = distance <= self._track.goal_tolerance_m
        if self._track_arrived is not None:
            answer = self._ask_arrival(position_m, what)()
            _require_routed(answer, what)
            arrived, detail = answer.arrived, answer.detail
            if arrived:
                return
            if plant_there:
                raise StepFailed(
                    f"{what}: the plant's carriage is there and not every side's is "
                    f"({detail}). A move of no length cannot be commanded through the "
                    f"twin: bring that carriage to {position_m * 1000:.0f} mm (home it) "
                    "and run the program again"
                )
        elif plant_there:
            return
        seconds = distance / (speed_mps * self._speed)
        self._until_true(
            lambda: self._track_command.get_subscription_count() > 0,
            f"a subscriber on {self._track_command.topic_name}",
        )
        self._track_target = position_m
        self._track_command.publish(
            track_trajectory(self._track, self._track_position, position_m, seconds)
        )
        ceiling_s = WAIT_WALL_FACTOR * seconds + WAIT_WALL_MARGIN_S
        wall_end = time.monotonic() + ceiling_s
        while abs(self._track_position - position_m) > self._track.goal_tolerance_m:
            if time.monotonic() > wall_end:
                raise StepFailed(
                    f"{what}: the carriage stands at {self._track_position * 1000:.1f} mm "
                    f"after {ceiling_s:.0f} wall seconds; is the controller active?"
                )
            self._spin_once(0.1)
        if self._track_arrived is not None:
            # Through the twin, this domain's joint states are the plant's
            # only: the counterpart's carriage - the physical one - is asked of
            # the boundary, within the same ceiling (SA2c-S-02 c).
            self._await_every_side(position_m, wall_end, what)
        self._track_target = None

    def cancel(self) -> None:
        """Cancel the goal in flight and hold the track; never itself interrupted."""
        with self._not_interrupted():
            self._cancel()

    def close(self) -> None:
        """Release this cell's node. The cell is not used again."""
        self.node.destroy_node()

    def _cancel(self) -> None:
        if self._track_target is not None and self._track_command is not None:
            # Abandoned mid-move: stop every carriage where IT stands, rather
            # than leave it running to a target nobody is waiting for. Through
            # the twin that is a trajectory with no points, which the boundary
            # answers with a hold at each side's own position (SA2c-S-02 a):
            # the plant's position sent to the physical carriage would move it.
            # On one side, a hold at that side's own position.
            self._track_target = None
            if self._via == "twin":
                self._track_command.publish(JointTrajectory(joint_names=[self._track.joint]))
            elif self._track_position is not None:
                self._track_command.publish(
                    track_command.hold(self._track.joint, self._track_position)
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

    def _ask_arrival(self, position_m: float, what: str):
        """Return a call answering the twin's `TrackArrived` for ``position_m``, whole."""
        client = self._track_arrived
        assert client is not None and self._track is not None
        if not client.wait_for_service(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{what}: {TrackArrived.Request.SERVICE} is not served")
        request = TrackArrived.Request(
            joint=self._track.joint,
            position_m=float(position_m),
            tolerance_m=float(self._track.goal_tolerance_m),
        )

        def ask():
            return self._until(client.call_async(request), f"{what}: TrackArrived")

        return ask

    def _ask_joints_at(self, start):
        """Return a call answering the twin's `JointsAt` for the arm's start pose."""
        client = self.node.create_client(JointsAt, JointsAt.Request.SERVICE)
        if not client.wait_for_service(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{JointsAt.Request.SERVICE} is not served; is the pair up?")
        request = JointsAt.Request(
            joints=list(start.joints),
            positions=[float(value) for value in start.positions],
            tolerance=float(start.tolerance_rad),
        )

        def ask():
            return self._until(client.call_async(request), "JointsAt")

        return ask

    def _pause_between_asks(self) -> None:
        # Bounded by the wall clock: `spin_once` returns on any callback, and
        # this node hears `/clock`.
        again = time.monotonic() + _ARRIVAL_ASK_S
        while time.monotonic() < again:
            self._spin_once(_ARRIVAL_ASK_S)

    def _await_every_side(self, position_m: float, wall_end: float, what: str) -> None:
        ask_twin = self._ask_arrival(position_m, what)

        def ask() -> tuple[bool, str]:
            answer = ask_twin()
            _require_routed(answer, what)
            return answer.arrived, answer.detail

        await_arrival(ask, self._pause_between_asks, wall_end, what)

    def _on_joint_state(self, message: JointState) -> None:
        self._positions.update(zip(message.name, message.position))
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
        # Spun in slices rather than in one `spin_until_future_complete`, so
        # that an interruption is seen within one slice; the ceiling is the
        # same wall-clock bound it was.
        deadline = time.monotonic() + ceiling_s
        while not future.done():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise StepFailed(f"{what} did not finish within {ceiling_s:.0f} s")
            self._spin_once(min(_SPIN_SLICE_S, remaining))
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
            self._spin_once(0.1)

    def _spin_once(self, timeout_sec: float) -> None:
        """Spin this node once, unless the console asked this cell to stop (ADR-0071)."""
        if (
            self._interrupted is not None
            and self._uninterruptible == 0
            and self._interrupted()
        ):
            raise Interrupted("stopped from the operator console")
        rclpy.spin_once(self.node, timeout_sec=timeout_sec)

    @contextmanager
    def _not_interrupted(self):
        self._uninterruptible += 1
        try:
            yield
        finally:
            self._uninterruptible -= 1
