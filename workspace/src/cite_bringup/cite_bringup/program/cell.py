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
the sides the twin's mode commands - the target's (ADR-0072, `program.targets`):
the plant in SIM, the counterpart in REAL, both in VALIDATED. The
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
from cite_bringup.plan import ControllerManager, Conveyor, PLANT_SIDE, resolve_uri, Track
from cite_bringup.program import targets
from cite_bringup.program.steps import Interrupted, scaled_motion, speed_scale, StepFailed
from cite_bringup.readiness import waits_for_a_physical_side, waits_for_goals_to_end
from cite_interfaces.action import Grasp, MoveTo
from cite_interfaces.msg import ConsoleState, ResultCode, RobotState, TwinMode, TwinSides
from cite_interfaces.qos import COMMAND, LATCHED, SENSOR, STATE
from cite_interfaces.srv import JointsAt, SetMode, TrackArrived
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rosgraph_msgs.msg import Clock
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
    mode: str = "VALIDATED",
) -> None:
    """Ask for ``mode`` until it is accepted, refused for good, or the ceiling passes.

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
            raise StepFailed(f"the twin refused {mode}: {detail}")
        if clock() > deadline:
            raise StepFailed(
                f"the physical side was not ready within {ceiling_s:.0f} s: {detail}"
            )
        if detail != said:
            say(f"waiting for the physical side: {detail}")
            said = detail
        pause()


#: The name of the node a TERMINAL client's cell creates: `python3 -m
#: cite_bringup.program` and `./scripts/home`, by either route. Written once:
#: the operator console reads it off the graph to refuse a motion request while
#: such a client runs (S-01), so a second spelling would be a console that never
#: sees one. The console's own cells are named otherwise (`console._CELL_NODE`).
TERMINAL_NODE = "fixed_program"

#: The simulated clock, bridged from Gazebo onto a simulated side's domain
#: (`simulation.launch.py`'s `CLOCK_BRIDGE`). A physical side runs on the wall
#: clock (`hardware.launch.py`, L-7) and nothing on it publishes this name.
SIMULATED_CLOCK = "/clock"


def mode_refusal(expected: int | None, heard: int | None) -> str | None:
    """Say why the next step may not be sent, as to the twin's mode, or None (R-05).

    ``expected`` is the mode this cell asked for and had accepted, None when it
    asked for none (via the plant alone, or before the first ask): then nothing
    is checked. ``heard`` is the latest `TwinMode` heard. Any mode it did not
    ask for - another client's, or one the boundary was moved to - means the
    sides the next step would reach are not the target's, so the run stops.
    """
    if expected is None:
        return None
    if heard is None:
        return f"no twin mode was heard since this run asked for {_mode_name(expected)}"
    if heard != expected:
        return (
            f"the twin is in {_mode_name(heard)}, not the {_mode_name(expected)} this run "
            "asked for: the next step would reach sides that are not its target's, so the "
            "run stops"
        )
    return None


def _mode_name(mode: int) -> str:
    for name in dir(TwinMode):
        if name.startswith("MODE_") and getattr(TwinMode, name) == mode:
            return name[len("MODE_"):]
    return str(mode)


def single_side_start(
    believed_m: float | None, confirmed: Callable[[float], tuple[bool, str]], what: str
) -> float:
    """Return where a carriage the program cannot read stands, confirmed by the twin (R-08).

    In a target that does not command the plant - the real arm alone - the
    carriage that moves is on a domain this program never opens, and the twin
    answers verdicts, never positions (ADR-0050 decision 1b). So the program
    keeps where it last SAW that carriage confirmed - the start, measured; the
    target of its last arrival - and asks the twin whether it still stands
    there before using it as the move's start point. Never the plant's: the
    plant is idle and its carriage stands wherever the last target left it.
    """
    if believed_m is None:
        raise StepFailed(
            f"{what}: where the target's carriage stands is not known to this program; "
            "Home with this target first"
        )
    there, detail = confirmed(believed_m)
    if not there:
        raise StepFailed(
            f"{what}: the target's carriage is not where this program last measured it "
            f"({believed_m * 1000:.0f} mm: {detail}); Home with this target first"
        )
    return believed_m


def console_holds(topic: str, state: ConsoleState | None) -> str:
    """Say that an operator console serves the pair, and so a terminal client may not."""
    from cite_bringup.program.console_machine import STATE_NAMES

    doing = "" if state is None else f" (it is {STATE_NAMES.get(state.state, state.state)})"
    return (
        f"an operator console serves this pair on {topic}{doing}: one operator surface per "
        "pair, so this terminal neither asks anyone into the cell nor moves it. Use the "
        "panel, or stop the console first (ADR-0071)"
    )


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
    _stop_deadline: Callable[[], float | None] | None = None
    #: The result of the goal in flight, awaited by a cancel for the goal's end.
    _result = None
    #: Class-level defaults of what `__init__` and `enter_target` set (ADR-0072),
    #: so a cell assembled without them drives the twin as it always has.
    _target: int | None = None
    _expected_mode: int | None = None
    _heard_mode: int | None = None
    _far_track_m: float | None = None
    _far_custody = None

    def __init__(
        self,
        arm: ControllerManager,
        via: str,
        *,
        conveyor: Conveyor | None = None,
        track: Track | None = None,
        speed: float = 1.0,
        interrupted: Callable[[], bool] | None = None,
        node_name: str = TERMINAL_NODE,
        stop_deadline: Callable[[], float | None] | None = None,
        far_custody: Callable[[str], RobotState | None] | None = None,
    ) -> None:
        skills = arm.skills
        #: Reads a side's `RobotState` on THAT side's domain (R-09), for a side
        #: other than the one this cell's node is on; None where none is given,
        #: and then such a side's custody is unheard, and refused.
        self._far_custody = far_custody
        #: The target this cell's run commands, once `enter_target` asked for
        #: it, and the mode it is run in: what every step is checked against.
        self._target: int | None = None
        self._expected_mode: int | None = None
        #: The latest `TwinMode` heard, kept for the whole of a run through the
        #: twin (R-05): asked before every step.
        self._heard_mode: int | None = None
        #: Where a carriage this node cannot read stands, as last confirmed by
        #: the twin (R-08). Set by a measured start and by an arrival.
        self._far_track_m: float | None = None
        #: Asked before every spin: True stops whatever is waiting with
        #: `Interrupted` (ADR-0071). None for a terminal run, whose stop is
        #: Ctrl-C's KeyboardInterrupt on the main thread.
        self._interrupted = interrupted
        #: The operator console's shutdown deadline, monotonic, or None before
        #: its shutdown began (R2-02): no wait of this cell - a cancel's, a
        #: return to SIM's, a server's - runs past it, so the stop in flight
        #: when the process ends ends within the console's own ceiling.
        self._stop_deadline = stop_deadline
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
        if via == "twin":
            self.node.create_subscription(TwinMode, TwinMode.TOPIC, self._on_mode, LATCHED)

    # --------------------------------------------------------------- setup

    def enter_target(self, target: int, homing: bool = False) -> None:
        """Put the twin in ``target``'s mode (`targets.MODES`): SIM, REAL or VALIDATED.

        The target is the operator's (ADR-0072); this asks for the mode it is
        run in and records both, so every step after is checked against it
        (R-05) and judged on the target's sides. For SIM it is an ask too, and
        never a transition into a commanding mode: SIM commands only the plant.
        ``homing`` asks with `SetMode.homing`, VALIDATED's alone
        (`targets.homing_allowance`), for the homing move before the first
        cycle only (`program.home.bring_to_start`): the carriages may stand
        apart then, since that move is what brings them together. The program
        itself always asks without it (ADR-0070).
        """
        mode = targets.MODES[target]
        if homing and not targets.homing_allowance(target):
            raise StepFailed(f"a homing allowance is VALIDATED's alone, not {targets.label(target)}'s")
        client = self.node.create_client(SetMode, SetMode.Request.SERVICE)
        self._await_ready(
            client.service_is_ready, f"{SetMode.Request.SERVICE} is not served; is the pair up?"
        )
        request = SetMode.Request(
            mode=mode,
            reason=(
                f"homing {targets.label(target)} to the program's start (ADR-0070)"
                if homing
                else f"fixed program on {targets.label(target)} (ADR-0072)"
            ),
            homing=homing,
        )
        name = _mode_name(mode)

        def ask() -> tuple[bool, str]:
            response = self._until(client.call_async(request), f"SetMode({name})")
            return response.accepted, response.result.detail

        def pause() -> None:
            ask_again = time.monotonic() + _ASK_AGAIN_S
            while time.monotonic() < ask_again:
                self._spin_once(_ASK_AGAIN_S)

        self._target = target
        ask_until_accepted(ask, pause, lambda text: print(text, flush=True), mode=name)
        self._expected_mode = mode
        # The accepted mode is latched; it is the one heard from here on, and
        # any other one heard later stops the run (R-05).
        self._heard_mode = mode

    def check_mode(self) -> None:
        """Raise `StepFailed` if the twin is not in the mode this run asked for (R-05).

        Asked before every step (`steps.execute`). The subscription is spun by
        every wait this cell makes, so the latest mode heard is current to
        within one spin slice.
        """
        if self._via != "twin":
            return
        self._spin_once(0.0)
        if mode_refusal(self._expected_mode, self._heard_mode) is None:
            return
        # Confirmed before refusing: a latched message queued before the
        # accepted transition may be delivered after it. A fresh subscription
        # receives the latest mode the boundary has published, and that one
        # decides.
        self._heard_mode = self.twin_mode()
        refusal = mode_refusal(self._expected_mode, self._heard_mode)
        if refusal is not None:
            raise StepFailed(refusal)

    def require_running(self, target: int) -> None:
        """Refuse ``target`` if a side it commands does not run (R-17, ADR-0072).

        Read from the twin's latched `TwinSides`, before anyone is asked into the
        cell: a pair started with the plant alone has no real arm, and a terminal
        run naming one is refused here rather than by a mode transition after
        the operator was asked in. Nothing falls back to another target.
        """
        if self._via != "twin":
            return
        heard: list[TwinSides] = []
        subscription = self.node.create_subscription(
            TwinSides, TwinSides.TOPIC, heard.append, LATCHED
        )
        try:
            self._until_true(lambda: bool(heard), f"TwinSides on {TwinSides.TOPIC}")
        finally:
            self.node.destroy_subscription(subscription)
        missing = [side for side in targets.SIDES[target] if side not in heard[-1].running]
        if missing:
            raise StepFailed(
                f"{targets.label(target)} commands {', '.join(missing)}, which this pair does not "
                "run (it was started with the plant alone: CITE_ALLOW_HARDWARE is not 1). "
                "Nothing else is run in its place"
            )

    def _on_mode(self, message: TwinMode) -> None:
        self._heard_mode = message.mode

    def return_to_sim(self) -> bool:
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
            left = self._return_to_sim()
        if left:
            self._expected_mode = TwinMode.MODE_SIM
            self._heard_mode = TwinMode.MODE_SIM
        return left

    def _return_to_sim(self) -> bool:
        client = self.node.create_client(SetMode, SetMode.Request.SERVICE)
        try:
            self._await_ready(
                client.service_is_ready,
                f"could not return to SIM: {SetMode.Request.SERVICE} is not served",
            )
        except StepFailed as failure:
            print(failure, flush=True)
            return False
        request = SetMode.Request(
            mode=TwinMode.MODE_SIM,
            reason="the program ended; a person may enter the physical cell",
        )
        # The boundary refuses a transition while a goal it dispatched is still
        # running (`waits_for_goals_to_end`): after a cancel that refusal clears
        # once the goal ends on every side, so it is asked again within the
        # cancel's own ceiling, and any other refusal is final (ADR-0071).
        deadline = time.monotonic() + CANCEL_CEILING_S
        while True:
            try:
                response = self._until(
                    client.call_async(request), "SetMode(SIM)", CANCEL_CEILING_S
                )
            except StepFailed as failure:
                print(f"could not return to SIM: {failure}", flush=True)
                return False
            if response.accepted and response.current_mode == TwinMode.MODE_SIM:
                break
            if (
                not waits_for_goals_to_end(response.result.detail)
                or time.monotonic() > deadline
            ):
                print(f"the twin stayed out of SIM: {response.result.detail}", flush=True)
                return False
            self._pause_between_asks()
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

    def console_refusal(self, topic: str) -> str | None:
        """Say why a terminal client may not drive this pair: a console serves it (N-01).

        ONE operator surface per pair (ADR-0071): where the zone's operator
        console runs, it alone asks a person into the cell, and a terminal
        client that also read SIM and asked would be a second invitation -
        whatever the console is doing, its AWAITING_OPERATOR included. The
        console is known by its latched `ConsoleState` on ``topic``: a message
        heard there, or a publisher of it on the graph.

        Read once a latched message of the pair's own has been heard on this
        domain - through the twin, the twin's mode; via the plant alone (R-05),
        where no twin runs, the arm's `RobotState`: that message is the event
        that discovery has reached the pair's participants, so an absence read
        before it is never taken as no console. DDS cannot prove an absence;
        this is the graph as known after that event. Raises `StepFailed` when
        that message is not heard at all.
        """
        heard: list[ConsoleState] = []
        witnessed: list = []
        if self._via == "twin":
            witness, witness_topic = TwinMode, TwinMode.TOPIC
        else:
            witness, witness_topic = RobotState, self._state_topic
        subscriptions = [
            self.node.create_subscription(ConsoleState, topic, heard.append, LATCHED),
            self.node.create_subscription(witness, witness_topic, witnessed.append, LATCHED),
        ]
        try:
            self._until_true(
                lambda: bool(heard or witnessed), f"{witness.__name__} on {witness_topic}"
            )
            present = bool(heard) or self.node.count_publishers(topic) > 0
        finally:
            for subscription in subscriptions:
                self.node.destroy_subscription(subscription)
        if not present:
            return None
        return console_holds(topic, heard[-1] if heard else None)

    def simulated_side_refusal(self) -> str | None:
        """Say why this domain is not shown to be a simulated side, or None (S-02r).

        `--via plant` checks its domain from the environment before any
        context exists (`plan.require_domain`); a shell that exported the
        counterpart's ROS_DOMAIN_ID would derive the base from it and pass that
        check. This is the graph's own answer: a simulated side's Gazebo
        publishes `SIMULATED_CLOCK` here, and a physical side publishes no such
        thing. A clock message heard is the event; none heard within
        `SERVER_WAIT_S` is no evidence, and refuses. Asked before any goal or
        mode, so a refusal moves nothing.
        """
        heard: list[Clock] = []
        # Best effort subscribes to a publisher of either reliability.
        subscription = self.node.create_subscription(
            Clock, SIMULATED_CLOCK, heard.append, SENSOR
        )
        try:
            self._until_true(lambda: bool(heard), f"{SIMULATED_CLOCK} on this domain")
        except StepFailed as error:
            return (
                f"{error}: nothing shows this domain is a simulated side, and a "
                "physical side publishes no simulated clock"
            )
        finally:
            self.node.destroy_subscription(subscription)
        return None

    def carriage_refusal(self, target: int, homing: bool = False) -> str | None:
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

        A target that does not command the plant - the real arm alone - is not
        asked this at all (ADR-0072): the plant is idle, and the boundary does
        not compare the carriages in REAL either.
        """
        if self._track_arrived is None or self._track is None:
            return None
        if PLANT_SIDE not in targets.SIDES[target]:
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

    def away_from_start(self, start, sides=()) -> str | None:
        """Measure the program's start on ``sides``; say where a side is not, or None.

        ``start`` is a `program.home.StartPose`; ``sides`` the target's
        (`targets.SIDES`, ADR-0072), every running side when empty. Through the
        twin each is asked of the boundary - the arm with `JointsAt`, the
        carriage with `TrackArrived`, both naming exactly those sides - and a
        physical side counts only with fresh positions, waited for within
        `PHYSICAL_SIDE_READY_CEILING_S`. Via the plant alone this domain's own
        joint states are read. Nothing is commanded (ADR-0070). A carriage this
        node cannot read, confirmed at the start, is remembered there (R-08).
        """
        sides = tuple(sides)
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
            self._ask_joints_at(start, sides), self._pause_between_asks, deadline
        )
        found.append(
            away_verdict(answer, f"the arm at {start.pose}", PHYSICAL_SIDE_READY_CEILING_S)
        )
        if start.track_m is not None and self._track_arrived is not None:
            what = f"the track at {start.track_m * 1000:.0f} mm"
            answer = await_heard(
                self._ask_arrival(start.track_m, what, sides),
                self._pause_between_asks,
                deadline,
            )
            found.append(away_verdict(answer, what, PHYSICAL_SIDE_READY_CEILING_S))
            if answer.arrived and sides and PLANT_SIDE not in sides:
                self._far_track_m = start.track_m
        found = [reason for reason in found if reason is not None]
        return "; ".join(found) if found else None

    def refuse_if_holding(self, sides=(PLANT_SIDE,)) -> None:
        """Refuse to start if an arm of ``sides`` says it holds a part (`holding_refusal`).

        R-09 (ADR-0072): every side the target commands is read. The plant's on
        THIS domain; any other side's on its own domain, through the reader
        this cell was given (`far_custody`). A side whose state is not heard
        refuses, as an unheard plant does.
        """
        for side in sides:
            if side == PLANT_SIDE:
                self._refuse_if_holding_here()
                continue
            state = None if self._far_custody is None else self._far_custody(side)
            refusal = holding_refusal(state, f"{side}: {self._state_topic}")
            if refusal is not None:
                raise StepFailed(refusal)

    def _refuse_if_holding_here(self) -> None:
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
        sides = self._target_sides()
        if self._track_arrived is not None and PLANT_SIDE not in sides:
            self._track_without_the_plant(position_m, speed_mps, sides, what)
            return
        self._until_true(
            lambda: self._track_position is not None,
            f"{self._track.joint} on the arm's joint states",
        )
        distance = abs(position_m - self._track_position)
        plant_there = distance <= self._track.goal_tolerance_m
        if self._track_arrived is not None:
            answer = self._ask_arrival(position_m, what, sides)()
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
            self._await_every_side(position_m, wall_end, what, sides)
        self._track_target = None

    def _track_without_the_plant(
        self, position_m: float, speed_mps: float, sides: tuple[str, ...], what: str
    ) -> None:
        """A track step in a target that leaves the plant idle (R-08, ADR-0072).

        Every position it uses is the target's carriage's, confirmed by the
        twin - never the plant's, which stands wherever the last target left
        it: the move's start point is where the twin confirms that carriage
        stands (`single_side_start`), and its arrival is the twin's verdict on
        those sides alone.
        """
        ask_target = self._ask_arrival(position_m, what, sides)
        answer = ask_target()
        _require_routed(answer, what)
        if answer.arrived:
            self._far_track_m = position_m
            return

        def confirmed(at_m: float) -> tuple[bool, str]:
            at = self._ask_arrival(at_m, what, sides)()
            return at.arrived, at.detail

        start_m = single_side_start(self._far_track_m, confirmed, what)
        seconds = abs(position_m - start_m) / (speed_mps * self._speed)
        if seconds <= 0.0:
            raise StepFailed(f"{what}: a move of no length cannot be commanded")
        self._until_true(
            lambda: self._track_command.get_subscription_count() > 0,
            f"a subscriber on {self._track_command.topic_name}",
        )
        self._track_target = position_m
        self._track_command.publish(
            track_trajectory(self._track, start_m, position_m, seconds)
        )
        # The commanded carriage is not on this domain: its arrival is the
        # twin's, asked within the same wall ceiling a step has.
        wall_end = time.monotonic() + WAIT_WALL_FACTOR * seconds + WAIT_WALL_MARGIN_S
        self._far_track_m = None
        self._await_every_side(position_m, wall_end, what, sides)
        self._far_track_m = position_m
        self._track_target = None

    def _target_sides(self) -> tuple[str, ...]:
        """The sides the current target commands; both before a target is entered."""
        if self._target is None:
            return targets.SIDES[targets.TWIN]
        return targets.SIDES[self._target]

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
        result, self._result = self._result, None
        if handle is None and sent is not None:
            # Interrupted before the server answered: the goal may still be
            # accepted, and an accepted goal nobody cancels runs to its end.
            handle = self._until(sent, "the acceptance of the goal to cancel", CANCEL_CEILING_S)
            if not handle.accepted:
                return
            result = None
        if handle is not None:
            self._until(handle.cancel_goal_async(), "the cancel", CANCEL_CEILING_S)
            # A cancel ANSWERED is not a goal ENDED: the goal ends on every side
            # after it, and until then the twin refuses SIM for it and the arm
            # may still be moving. Its terminal status is read, within the same
            # ceiling, before the stop counts as done (ADR-0071, S-03); unread,
            # the cancel fails and says so.
            if result is None:
                result = handle.get_result_async()
            self._until(result, "the end of the cancelled goal", CANCEL_CEILING_S)

    # --------------------------------------------------------------- mechanism

    def _ask_arrival(self, position_m: float, what: str, sides=()):
        """Return a call answering the twin's `TrackArrived` for ``position_m``, whole.

        ``sides`` names exactly the sides judged (ADR-0072); empty asks the
        boundary's own rule - every commanded side and every physical one.
        """
        client = self._track_arrived
        assert client is not None and self._track is not None
        self._await_ready(
            client.service_is_ready, f"{what}: {TrackArrived.Request.SERVICE} is not served"
        )
        request = TrackArrived.Request(
            joint=self._track.joint,
            position_m=float(position_m),
            tolerance_m=float(self._track.goal_tolerance_m),
            sides=list(sides),
        )

        def ask():
            return self._until(client.call_async(request), f"{what}: TrackArrived")

        return ask

    def _ask_joints_at(self, start, sides=()):
        """Return a call answering the twin's `JointsAt` for the arm's start pose."""
        client = self.node.create_client(JointsAt, JointsAt.Request.SERVICE)
        self._await_ready(
            client.service_is_ready, f"{JointsAt.Request.SERVICE} is not served; is the pair up?"
        )
        request = JointsAt.Request(
            joints=list(start.joints),
            positions=[float(value) for value in start.positions],
            tolerance=float(start.tolerance_rad),
            sides=list(sides),
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

    def _await_every_side(
        self, position_m: float, wall_end: float, what: str, sides=()
    ) -> None:
        ask_twin = self._ask_arrival(position_m, what, sides)

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
        self._await_ready(client.server_is_ready, f"{what}: {client._action_name} is not served")
        self._sent = client.send_goal_async(goal)
        handle = self._until(self._sent, f"{what}: acceptance")
        if handle.accepted:
            self._active = handle
        self._sent = None
        if not handle.accepted:
            raise StepFailed(f"{what}: {client._action_name} rejected the goal")
        self._result = handle.get_result_async()
        wrapped = self._until(self._result, what)
        self._active = None
        self._result = None
        code = wrapped.result.result
        if code.code != ResultCode.SUCCESS:
            raise StepFailed(f"{what}: result code {code.code}: {code.detail}")

    def _until(self, future, what: str, ceiling_s: float = STEP_CEILING_S):
        # Spun in slices rather than in one `spin_until_future_complete`, so
        # that an interruption is seen within one slice; the ceiling is the
        # same wall-clock bound it was.
        deadline = time.monotonic() + ceiling_s
        while not future.done():
            remaining = self._clamped(deadline) - time.monotonic()
            if remaining <= 0.0:
                raise StepFailed(f"{what} did not finish within {ceiling_s:.0f} s{self._why()}")
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
            if time.monotonic() > self._clamped(deadline):
                raise StepFailed(f"no {what} after {SERVER_WAIT_S:.0f} s{self._why()}")
            self._spin_once(0.1)

    def _await_ready(self, ready, refusal: str) -> None:
        """Wait for a server to be discovered, within `SERVER_WAIT_S`, or raise ``refusal``.

        Spun in slices like every other wait, so a stop and the console's
        shutdown deadline reach it; `wait_for_service` blocked for its whole
        timeout without either.
        """
        deadline = time.monotonic() + SERVER_WAIT_S
        while not ready():
            if time.monotonic() > self._clamped(deadline):
                raise StepFailed(f"{refusal}{self._why()}")
            self._spin_once(_SPIN_SLICE_S)

    def _clamped(self, deadline: float) -> float:
        """Return ``deadline``, or the console's shutdown deadline if that is sooner (R2-02)."""
        limit = None if self._stop_deadline is None else self._stop_deadline()
        return deadline if limit is None else min(deadline, limit)

    def _why(self) -> str:
        limit = None if self._stop_deadline is None else self._stop_deadline()
        if limit is not None and time.monotonic() >= limit:
            return ", cut short by the console's shutdown deadline"
        return ""

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
