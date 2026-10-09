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

"""The operator console's state machine (ADR-0071), against a fake cell.

What it refuses, the order it calls the program's library in, and what a stop
and a failure leave it in. Nothing here has a ROS graph: the cell is a fake
that records every call and, like `RosCell`, raises `Interrupted` from a
blocking step once the console asks it to stop.
"""

from __future__ import annotations

import math
import threading
import time

from cite_bringup.program.console_machine import (
    ConsoleMachine,
    HOME_PROMPT,
    PLACE_PROMPT,
    START_PROMPT,
)
from cite_bringup.program.home import StartPose
from cite_bringup.program.targets import ALL, REAL, SIM, TWIN
from cite_bringup.program.steps import (
    grip,
    Interrupted,
    move,
    release,
    speed_scale,
    StepFailed,
    track,
)
from cite_interfaces.msg import ConsoleState, TwinMode
import pytest

#: How long a test waits for the machine to reach a state, in wall seconds. A
#: hang detector; every wait ends the moment its condition holds.
SETTLE_S = 10.0

HOME_STEPS = [move("zero"), track(0.0, 0.1)]
START = StartPose(
    pose="zero",
    joints=("joint1",),
    positions=(0.0,),
    tolerance_rad=0.01,
    track_m=0.0,
    track_tolerance_m=0.001,
)
PROGRAM = [release(), move("pick"), grip(0.06), move("place"), release()]
SIDES = ("plant", "counterpart")


def _at_start(snapshot) -> bool:
    """Both sides at the program's start: what a twin target needs."""
    return snapshot.plant_at_start and snapshot.counterpart_at_start


class FakeCell:
    """`RosCell` as far as the console uses it; every call recorded in one shared log."""

    def __init__(self, rig: "Rig", speed, interrupted) -> None:
        self._rig = rig
        self.speed = speed
        self._interrupted = interrupted

    def _call(self, *call):
        self._rig.calls.append(call)

    # setup and checks
    def twin_mode(self):
        self._call("twin_mode")
        return self._rig.modes.pop(0) if self._rig.modes else self._rig.mode

    def carriage_refusal(self, target: int, homing: bool = False):
        self._call("carriage_refusal", homing)
        self._rig.targets_seen.append(("carriage_refusal", target))
        return None

    def refuse_if_holding(self, sides=("plant",)) -> None:
        self._call("refuse_if_holding")
        self._rig.custody_sides.append(tuple(sides))
        if self._rig.holding:
            raise StepFailed("the arm is holding workpiece")

    def require_running(self, target: int) -> None:
        # Not recorded in `calls`: every request asks it first, and the order
        # the tests below hold is the one after it.
        self._rig.targets_seen.append(("require_running", target))
        if self._rig.not_running is not None:
            raise StepFailed(self._rig.not_running)

    def enter_target(self, target: int, homing: bool = False) -> None:
        self._call("enter", target, homing)

    def return_to_sim(self) -> bool:
        self._call("return_to_sim")
        return self._rig.left.pop(0) if self._rig.left else True

    def away_from_start(self, start, sides=()):
        self._call("measure")
        self._rig.measured_sides.append(tuple(sides))
        return self._rig.away.pop(0) if self._rig.away else None

    def close(self) -> None:
        self._call("close")

    # steps
    def move(self, pose: str, velocity_scaling: float) -> None:
        self._step("move", pose)

    def grip(self, width_m: float, expect_object: bool) -> None:
        self._step("grip", expect_object)

    def track(self, position_m: float, speed_mps: float) -> None:
        self._step("track", position_m)

    def belt(self, speed_mps: float) -> None:
        self._step("belt", speed_mps)

    def wait(self, seconds: float) -> None:
        self._step("wait", seconds)

    def cancel(self) -> None:
        # What the console reports after a stop must be said of a cell whose
        # cancelled goal has ENDED (S-03): record the state the console is in
        # while the cancel runs.
        self._call("cancel")
        self._rig.state_during_cancel.append(self._rig.machine.snapshot().state)
        self._rig.on_cancel()
        if self._rig.cancel_fails:
            raise StepFailed("the cancel was not answered")

    def _step(self, *call) -> None:
        self._call(*call)
        if call == self._rig.on_call:
            self._rig.on_call_hook()
        if call == self._rig.fail_on:
            raise StepFailed(f"{call[0]} {call[1]}: result code 2: refused")
        if call == self._rig.hold_on:
            # A step that never ends by itself, as a motion on a stalled arm:
            # only the console's stop ends it, the way `RosCell` sees it.
            self._rig.holding_step.set()
            deadline = time.monotonic() + SETTLE_S
            while time.monotonic() < deadline:
                if self._interrupted():
                    raise Interrupted("stopped from the operator console")
                time.sleep(0.005)
            raise AssertionError("the held step was never stopped")


class Rig:
    """A machine over a fake cell, with every collaborator recording into `calls`."""

    def __init__(
        self,
        physical=(),
        mode=TwinMode.MODE_SIM,
        holding=False,
        initialize=None,
        check_scale=speed_scale,
        minimum=0.0,
        available=ALL,
    ) -> None:
        self.calls: list[tuple] = []
        #: What the deployment offers now (`targets.available`).
        self.available = list(available)
        #: Which target each target-aware call was asked with, and which sides
        #: were measured and had their custody read.
        self.targets_seen: list[tuple] = []
        self.measured_sides: list[tuple] = []
        self.custody_sides: list[tuple] = []
        #: Why `require_running` refuses, None for never.
        self.not_running: str | None = None
        #: Every `check_scale` ask: (scale, target).
        self.scales_checked: list[tuple] = []
        #: What the cell reads from the twin, in order, then `mode` for ever.
        self.modes: list = []
        self.mode = mode
        #: What the node has heard on the twin's topic.
        self.heard = mode
        self.holding = holding
        self.away: list[str | None] = []
        #: What each `leave_validated` answers, in order, then True.
        self.left: list[bool] = []
        self.fail_on: tuple | None = None
        self.hold_on: tuple | None = None
        self.on_call: tuple | None = None
        self.on_call_hook = lambda: None
        self.cancel_fails = False
        #: Run inside every cancel: a slow stop, as an unanswered cancel is.
        self.on_cancel = lambda: None
        #: How long a belt STOP takes, and which thread made each one.
        self.belt_stop_s = 0.0
        self.belt_stoppers: list[str] = []
        self.belts_confirm = True
        self.spawn_fails_on: str | None = None
        self.holding_step = threading.Event()
        self.placed_on: list[tuple] = []
        self.speeds: list = []
        self.snapshots = []
        self.state_during_cancel: list[int] = []
        #: The terminal program client on the graph, None for none (S-01).
        self.terminal: str | None = None
        self._changed = threading.Condition()
        self.machine = ConsoleMachine(
            physical=list(physical),
            simulated=[side for side in SIDES if side not in physical],
            home_steps=HOME_STEPS,
            start=START,
            steps=PROGRAM,
            make_cell=self._make_cell,
            initialize_physical=initialize
            or (lambda say, interrupted: self.calls.append(("initialize",))),
            place_parts=self._place_parts,
            set_belts=self._set_belts,
            available=lambda: self.available,
            heard_twin_mode=lambda: self.heard,
            terminal_client=lambda: self.terminal,
            check_scale=lambda scale, target: (
                self.scales_checked.append((scale, target)) or check_scale(scale)
            ),
            minimum_speed_scale=minimum,
            on_change=self._on_change,
            log=lambda text: None,
        )

    def _make_cell(self, speed, interrupted) -> FakeCell:
        self.speeds.append(speed)
        return FakeCell(self, speed, interrupted)

    def _place_parts(self, sides, may_hold, say, interrupted) -> None:
        """`program.part.place_on_simulated_sides`'s contract, without Gazebo."""
        self.calls.append(("place", tuple(sorted(may_hold))))
        self.placed_on.append(tuple(sides))
        for side in sides:
            may_hold.discard(side)
            may_hold.add(side)
            if side == self.spawn_fails_on:
                raise StepFailed(f"{side}: the create failed")

    def _set_belts(self, running: bool, say, interrupted, ceiling) -> bool:
        self.calls.append(("belts", running))
        if not running:
            self.belt_stoppers.append(threading.current_thread().name)
            # A side whose subscriber is slow to match, as `belt.MATCH_CEILING_S` allows.
            time.sleep(self.belt_stop_s)
        return self.belts_confirm

    def _on_change(self, snapshot) -> None:
        with self._changed:
            self.snapshots.append(snapshot)
            self._changed.notify_all()

    def wait_for_state(self, state: int) -> None:
        with self._changed:
            reached = self._changed.wait_for(
                lambda: self.machine.snapshot().state == state, timeout=SETTLE_S
            )
        assert reached, f"never reached state {state}; at {self.machine.snapshot()}"

    def answer(self) -> None:
        """Wait for the operator's question and confirm it."""
        self.wait_for_state(ConsoleState.AWAITING_OPERATOR)
        outcome = self.machine.confirm_operator()
        assert outcome.success, outcome.detail

    def started(self) -> "Rig":
        if self.machine.physical:
            join = self.in_thread(self.machine.start_robot)
            self.answer()
            assert join().success
        else:
            assert self.machine.start_robot().success
        self.calls.clear()
        return self

    def homed(self) -> "Rig":
        """Start the robot and home it: what Start program needs."""
        self.started()
        self.away = [None]
        if self.machine.physical:
            join = self.in_thread(lambda: self.machine.home(1.0, TWIN))
            self.answer()
            assert join().success
        else:
            assert self.machine.home(1.0, TWIN).success
        assert _at_start(self.machine.snapshot())
        self.calls.clear()
        self.speeds.clear()
        return self

    def in_thread(self, request):
        """Run ``request`` on a thread, as the node's handler would; return a join."""
        box = {}
        thread = threading.Thread(target=lambda: box.setdefault("outcome", request()))
        thread.start()

        def join():
            thread.join(SETTLE_S)
            assert not thread.is_alive(), "the request never ended"
            return box["outcome"]

        return join

    def moves(self) -> list[str]:
        return [call[1] for call in self.calls if call[0] == "move"]

    def asked(self) -> int:
        """Count the times the operator was asked: entries into AWAITING_OPERATOR."""
        states = [snapshot.state for snapshot in self.snapshots]
        return sum(
            1
            for before, after in zip([None, *states], states)
            if after == ConsoleState.AWAITING_OPERATOR and before != after
        )


# --- Gating: nothing before Start robot, one request at a time ---------------


def test_nothing_but_start_robot_is_accepted_before_it_succeeds() -> None:
    rig = Rig()
    assert rig.machine.snapshot().state == ConsoleState.NOT_STARTED
    for outcome in (rig.machine.home(1.0, TWIN), rig.machine.run_program(1.0, 1, TWIN)):
        assert not outcome.success
        assert "Start robot" in outcome.detail
    assert "Start robot" in rig.machine.motion_refusal(1.0, None, TWIN)
    # Refused before anything was touched.
    assert rig.speeds == [] and rig.calls == []
    assert rig.machine.snapshot().state == ConsoleState.NOT_STARTED


def test_start_robot_on_a_simulated_pair_initializes_then_reads_custody() -> None:
    rig = Rig()
    outcome = rig.machine.start_robot()
    assert outcome.success
    # No question on an all-simulated pair, and no mode read.
    assert rig.calls == [("initialize",), ("refuse_if_holding",), ("close",)]
    assert rig.asked() == 0
    # Start robot's cell is never handed a step: it is built with no scale.
    assert rig.speeds == [None]
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY
    assert snapshot.robot_started and not snapshot.busy and not _at_start(snapshot)
    assert rig.machine.motion_refusal(1.0, None, TWIN) is None


def test_a_failed_start_is_a_fault_and_the_robot_is_not_started() -> None:
    rig = Rig(holding=True)
    outcome = rig.machine.start_robot()
    assert not outcome.success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert not snapshot.robot_started
    assert "holding" in snapshot.last_error
    assert "Start robot" in rig.machine.motion_refusal(1.0, None, TWIN)


def test_confirm_operator_is_refused_outside_awaiting_operator() -> None:
    rig = Rig()
    assert not rig.machine.confirm_operator().success
    rig.started()
    outcome = rig.machine.confirm_operator()
    assert not outcome.success
    assert "AWAITING_OPERATOR" in outcome.detail


def test_stop_with_nothing_in_progress_is_refused() -> None:
    rig = Rig().started()
    outcome = rig.machine.stop()
    assert not outcome.success
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_one_request_at_a_time() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    join = rig.in_thread(lambda: rig.machine.run_program(0.5, 1, TWIN))
    rig.wait_for_state(ConsoleState.AWAITING_OPERATOR)
    assert "in progress" in rig.machine.motion_refusal(0.5, None, TWIN)
    assert not rig.machine.home(0.5, TWIN).success
    assert not rig.machine.start_robot().success
    assert rig.machine.stop().success
    join()


# --- D1: Start robot on a physical side is gated like Home -------------------


def test_a_physical_start_reads_sim_and_asks_the_operator_before_initializing() -> None:
    rig = Rig(physical=["counterpart"])
    join = rig.in_thread(rig.machine.start_robot)
    rig.wait_for_state(ConsoleState.AWAITING_OPERATOR)
    snapshot = rig.machine.snapshot()
    assert snapshot.prompt == START_PROMPT
    # The mode was read; nothing has been initialized yet.
    assert rig.calls == [("twin_mode",)]
    assert rig.machine.confirm_operator().success
    assert join().success
    # Read again after the confirmation, then initialized, then custody.
    assert rig.calls == [
        ("twin_mode",),
        ("twin_mode",),
        ("initialize",),
        ("refuse_if_holding",),
        ("close",),
    ]
    assert rig.machine.snapshot().prompt == ""
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_physical_start_is_refused_when_the_twin_is_not_in_sim() -> None:
    rig = Rig(physical=["counterpart"])
    rig.mode = TwinMode.MODE_VALIDATED
    outcome = rig.machine.start_robot()
    assert not outcome.success
    assert rig.asked() == 0
    assert ("initialize",) not in rig.calls
    assert rig.machine.snapshot().state == ConsoleState.FAULT


# --- D2: SIM re-read on confirmation; a commanding mode this console did not enter


def test_a_confirmation_is_refused_while_the_twin_is_not_heard_in_sim() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1, TWIN))
    rig.wait_for_state(ConsoleState.AWAITING_OPERATOR)
    rig.heard = TwinMode.MODE_VALIDATED
    outcome = rig.machine.confirm_operator()
    assert not outcome.success and "not SIM" in outcome.detail
    # The question stands; nothing was entered.
    assert rig.machine.snapshot().state == ConsoleState.AWAITING_OPERATOR
    assert ("enter", TWIN, False) not in rig.calls
    assert rig.machine.stop().success
    join()


def test_a_twin_read_out_of_sim_after_the_confirmation_enters_nothing() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    # SIM when the gate reads it; VALIDATED when read again after the go-ahead.
    rig.modes = [TwinMode.MODE_SIM, TwinMode.MODE_VALIDATED]
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1, TWIN))
    rig.answer()
    outcome = join()
    assert not outcome.success
    assert ("enter", TWIN, False) not in rig.calls and rig.moves() == []
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT and "then read in mode" in snapshot.last_error


def test_a_commanding_mode_this_console_did_not_enter_refuses_every_request() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    for mode in (TwinMode.MODE_VALIDATED, TwinMode.MODE_VIRTUAL_LEAD):
        rig.heard = mode
        assert "did not ask for" in rig.machine.motion_refusal(0.1, None, TWIN)
        assert "did not ask for" in rig.machine.motion_refusal(0.1, 1, TWIN)
        assert not rig.machine.start_robot().success
        assert not rig.machine.home(0.1, TWIN).success
        assert not rig.machine.run_program(0.1, 1, TWIN).success
    assert rig.speeds == []


def test_a_commanding_mode_on_an_all_simulated_pair_refuses_nothing() -> None:
    rig = Rig().homed()
    rig.heard = TwinMode.MODE_VALIDATED
    assert rig.machine.motion_refusal(1.0, 1, TWIN) is None


# --- D3: a stop during the initialization is STOPPING until it has ended ------


def test_a_stop_during_start_robot_stays_stopping_until_the_initializer_ends() -> None:
    reached, ended = threading.Event(), threading.Event()

    def initialize(say, interrupted) -> None:
        reached.set()
        deadline = time.monotonic() + SETTLE_S
        while not interrupted():
            assert time.monotonic() < deadline, "the initialization was never stopped"
            time.sleep(0.005)
        # `home._call_on_domain`: the track stopped, the answer awaited, the
        # track stopped again - only then re-raised.
        assert ended.wait(SETTLE_S)
        raise Interrupted("stopped")

    rig = Rig(initialize=initialize)
    join = rig.in_thread(rig.machine.start_robot)
    assert reached.wait(SETTLE_S)
    assert rig.machine.stop().success
    time.sleep(0.05)
    assert rig.machine.snapshot().state == ConsoleState.STOPPING
    assert rig.machine.snapshot().busy
    ended.set()
    assert not join().success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.NOT_STARTED and not snapshot.robot_started


# --- Speed: sent with every goal, validated, never defaulted -----------------


@pytest.mark.parametrize("scale", [0.0, -0.1, 1.0001, 2.0, math.nan, math.inf])
def test_a_speed_scale_outside_zero_to_one_is_rejected(scale: float) -> None:
    rig = Rig().homed()
    assert "(0, 1]" in rig.machine.motion_refusal(scale, None, TWIN)
    assert not rig.machine.home(scale, TWIN).success
    assert not rig.machine.run_program(scale, 1, TWIN).success
    assert rig.speeds == [], "a cell was built for a rejected goal"


def test_the_physical_floor_is_applied_and_shown() -> None:
    """D7: the command line's own rule, `sides.required_speed_scale`, floor included."""

    def check(scale: float) -> float:
        value = speed_scale(scale)
        if value < 0.25:
            raise ValueError(f"{value:g} is below 0.25")
        return value

    rig = Rig(check_scale=check, minimum=0.25).homed()
    assert "below 0.25" in rig.machine.motion_refusal(0.1, None, TWIN)
    assert "below 0.25" in rig.machine.motion_refusal(0.1, 1, TWIN)
    assert rig.machine.motion_refusal(0.25, 1, TWIN) is None
    assert rig.machine.snapshot().minimum_speed_scale == 0.25


def test_zero_cycles_is_rejected_rather_than_read_as_forever() -> None:
    rig = Rig().homed()
    assert "at least 1" in rig.machine.motion_refusal(1.0, 0, TWIN)
    assert not rig.machine.run_program(1.0, 0, TWIN).success


def test_every_motion_cell_runs_at_the_goals_own_scale() -> None:
    rig = Rig().started()
    rig.away = ["away", None]
    assert rig.machine.home(0.3, TWIN).success
    assert rig.machine.run_program(0.7, 1, TWIN).success
    assert rig.speeds == [None, 0.3, 0.7]
    assert rig.machine.snapshot().speed_scale == 0.7


# --- D11: Start program only from the program's start ------------------------


def test_start_program_is_refused_until_a_home_put_the_arms_at_the_start() -> None:
    rig = Rig().started()
    assert "Home first" in rig.machine.motion_refusal(1.0, 1, TWIN)
    assert not rig.machine.run_program(1.0, 1, TWIN).success
    assert rig.machine.motion_refusal(1.0, None, TWIN) is None, "Home itself is accepted"
    rig.away = [None]
    assert rig.machine.home(1.0, TWIN).success
    assert _at_start(rig.machine.snapshot())
    assert rig.machine.run_program(1.0, 1, TWIN).success
    # A completed cycle ends where it began.
    assert _at_start(rig.machine.snapshot())


def test_a_stop_a_failure_and_start_robot_each_clear_at_start() -> None:
    rig = Rig().homed()
    rig.hold_on = ("move", "pick")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    rig.machine.stop()
    join()
    assert not _at_start(rig.machine.snapshot())
    assert "Home first" in rig.machine.motion_refusal(1.0, 1, TWIN)

    rig = Rig().homed()
    rig.fail_on = ("move", "place")
    assert not rig.machine.run_program(1.0, 1, TWIN).success
    assert not _at_start(rig.machine.snapshot())

    rig = Rig().homed()
    assert rig.machine.start_robot().success
    assert not _at_start(rig.machine.snapshot())


# --- The order the library is called in ---------------------------------------


def test_home_on_a_simulated_pair_is_bring_to_start() -> None:
    rig = Rig().started()
    rig.away = ["joint1 away", None]
    outcome = rig.machine.home(1.0, TWIN)
    assert outcome.success, outcome.detail
    # No physical side in the target: nothing to initialize (R-03); and the
    # twin is asked for SIM again after any target but the simulation (R-20).
    assert rig.calls == [
        ("measure",),
        ("enter", TWIN, True),
        ("move", "zero"),
        ("track", 0.0),
        ("measure",),
        ("enter", TWIN, False),
        ("return_to_sim",),
        ("close",),
    ]
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_run_on_a_simulated_pair_places_a_part_then_runs_each_cycle() -> None:
    rig = Rig().homed()
    outcome = rig.machine.run_program(1.0, 2, TWIN)
    assert outcome.success, outcome.detail
    assert outcome.cycles_completed == 2
    head = rig.calls[: rig.calls.index(("enter", TWIN, False)) + 1]
    # The start measured first (N-03); Start robot left every simulated side's
    # world unknown, so each is cleared.
    assert head == [
        ("measure",),
        ("place", ("counterpart", "plant")),
        ("belts", True),
        ("refuse_if_holding",),
        ("enter", TWIN, False),
    ]
    # The second cycle clears the first cycle's part, and the belts already run.
    places = [call for call in rig.calls if call[0] == "place"]
    assert places == [("place", ("counterpart", "plant"))] * 2
    first = rig.calls.index(("place", ("counterpart", "plant")))
    second = rig.calls.index(("place", ("counterpart", "plant")), first + 1)
    assert ("belts", True) not in rig.calls[second:]
    assert rig.moves() == ["pick", "place"] * 2
    # No operator is asked and no SIM is asked for on a simulated pair.
    # No one is asked on an all-simulated pair; SIM is asked for after each
    # cycle all the same (R-20).
    assert ("twin_mode",) not in rig.calls
    assert rig.calls.count(("return_to_sim",)) == 2
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY and not snapshot.busy


def test_a_physical_run_awaits_the_operator_after_reading_sim_then_returns_to_sim() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1, TWIN))
    rig.wait_for_state(ConsoleState.AWAITING_OPERATOR)
    # R-12: the prompt names the target and its physical sides first.
    assert rig.machine.snapshot().prompt.endswith(PLACE_PROMPT)
    assert "Target: the twin" in rig.machine.snapshot().prompt
    # Asked only once the mode was read and the carriage judged; nothing entered.
    assert rig.calls[-2:] == [("twin_mode",), ("carriage_refusal", False)]
    assert ("enter", TWIN, False) not in rig.calls
    assert rig.machine.confirm_operator().success
    outcome = join()
    assert outcome.success, outcome.detail
    after = rig.calls[rig.calls.index(("carriage_refusal", False)) + 1:]
    # The mode read again after the go-ahead, then custody, then VALIDATED.
    assert after[:3] == [("twin_mode",), ("refuse_if_holding",), ("enter", TWIN, False)]
    assert after[-2:] == [("return_to_sim",), ("close",)]


def test_a_physical_home_asks_the_operator_then_returns_to_sim() -> None:
    rig = Rig(physical=["counterpart"]).started()
    rig.away = [None]
    join = rig.in_thread(lambda: rig.machine.home(0.1, TWIN))
    rig.wait_for_state(ConsoleState.AWAITING_OPERATOR)
    assert rig.machine.snapshot().prompt.endswith(HOME_PROMPT)
    assert rig.calls[-1] == ("carriage_refusal", True)
    assert rig.machine.confirm_operator().success
    assert join().success
    assert rig.calls[-2:] == [("return_to_sim",), ("close",)]


def test_a_physical_run_is_refused_when_the_twin_is_not_in_sim() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    asked = rig.asked()
    rig.modes = [TwinMode.MODE_REAL]
    outcome = rig.machine.run_program(0.1, 1, TWIN)
    assert not outcome.success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "not SIM" in snapshot.last_error
    # Never asked, never entered, nothing moved.
    assert rig.asked() == asked
    assert ("enter", TWIN, False) not in rig.calls
    assert rig.moves() == []


def test_a_physical_run_with_no_mode_heard_is_refused() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    rig.modes = [None]
    assert not rig.machine.run_program(0.1, 1, TWIN).success
    assert "no twin mode" in rig.machine.snapshot().last_error


# --- D15: a return to SIM that fails is a FAULT, and no one is asked in next --


def test_a_home_whose_return_to_sim_fails_is_a_fault() -> None:
    rig = Rig(physical=["counterpart"]).started()
    asked = rig.asked()
    rig.away = [None]
    rig.left = [False]
    join = rig.in_thread(lambda: rig.machine.home(0.1, TWIN))
    rig.answer()
    outcome = join()
    assert not outcome.success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "did not confirm SIM" in snapshot.last_error
    assert not _at_start(snapshot)
    assert rig.asked() == asked + 1


def test_a_run_whose_return_to_sim_fails_asks_no_one_in_for_the_next_cycle() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    asked_before = rig.asked()
    rig.left = [False]
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 3, TWIN))
    rig.answer()
    outcome = join()
    assert not outcome.success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "did not confirm SIM" in snapshot.last_error
    # The first cycle's question only: the second was never asked.
    assert rig.asked() == asked_before + 1
    assert rig.moves() == ["pick", "place"]


# --- Stop and failure: READY or FAULT, and never a homing move ---------------


def test_stop_during_running_cancels_and_returns_ready_without_homing() -> None:
    rig = Rig().homed()
    rig.hold_on = ("move", "place")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 3, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.snapshot().state == ConsoleState.RUNNING
    assert rig.machine.stop().success
    assert rig.machine.stop().detail == "already stopping"
    outcome = join()
    assert not outcome.success and outcome.cycles_completed == 0
    stopped_at = rig.calls.index(("move", "place"))
    after = rig.calls[stopped_at + 1:]
    assert ("cancel",) in after
    # D5: READY is said only once the cancel - and the goal's end - returned.
    assert rig.state_during_cancel and all(
        state == ConsoleState.STOPPING for state in rig.state_during_cancel
    )
    # The belts this console started are stopped; nothing else moves.
    assert ("belts", False) in after
    assert [call for call in after if call[0] in ("move", "track", "grip")] == []
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY
    assert snapshot.robot_started and not snapshot.busy
    assert any(s.state == ConsoleState.STOPPING for s in rig.snapshots)


def test_a_stop_after_the_last_step_reports_the_run_completed() -> None:
    """D5: a stop that came too late to stop anything is not reported as a stop."""
    rig = Rig().homed()
    # The program's last step is its second release, and the stop arrives while
    # it runs: nothing after it can be interrupted.
    rig.on_call = ("grip", False)

    def stop_during_the_last_step() -> None:
        if rig.calls.count(("grip", False)) == 2:
            assert rig.machine.stop().success

    rig.on_call_hook = stop_during_the_last_step
    outcome = rig.machine.run_program(1.0, 1, TWIN)
    assert outcome.success, outcome.detail
    assert outcome.cycles_completed == 1
    assert "1 cycle(s) completed" in outcome.detail
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_stop_while_awaiting_the_operator_enters_nothing_and_returns_ready() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1, TWIN))
    rig.wait_for_state(ConsoleState.AWAITING_OPERATOR)
    assert rig.machine.stop().success
    assert not join().success
    assert ("enter", TWIN, False) not in rig.calls
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY and snapshot.prompt == ""
    # The go-ahead it was waiting for is no longer asked.
    assert not rig.machine.confirm_operator().success


def test_a_stop_during_a_home_cancels_and_does_not_home_again() -> None:
    rig = Rig().started()
    rig.away = ["away"]
    rig.hold_on = ("track", 0.0)
    join = rig.in_thread(lambda: rig.machine.home(1.0, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.stop().success
    assert not join().success
    assert rig.calls[rig.calls.index(("track", 0.0)) + 1] == ("cancel",)
    assert rig.moves() == ["zero"]
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_failed_step_is_a_fault_and_nothing_homes() -> None:
    rig = Rig().homed()
    rig.fail_on = ("move", "place")
    outcome = rig.machine.run_program(1.0, 2, TWIN)
    assert not outcome.success and outcome.cycles_completed == 0
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "move place" in snapshot.last_error
    after = rig.calls[rig.calls.index(("move", "place")) + 1:]
    assert ("cancel",) in after and ("belts", False) in after
    assert [call for call in after if call[0] in ("move", "track", "grip")] == []
    # A FAULT is left by Start robot and by nothing else.
    assert "FAULT" in rig.machine.motion_refusal(1.0, None, TWIN)
    assert rig.machine.start_robot().success
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_stop_whose_cancel_fails_is_a_fault() -> None:
    rig = Rig().homed()
    rig.hold_on = ("move", "pick")
    rig.cancel_fails = True
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    rig.machine.stop()
    join()
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "cancel" in snapshot.last_error


def test_a_belt_that_does_not_confirm_its_stop_is_a_fault() -> None:
    rig = Rig().homed()
    rig.hold_on = ("move", "pick")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    rig.belts_confirm = False
    rig.machine.stop()
    join()
    assert rig.machine.snapshot().state == ConsoleState.FAULT
    assert "belt" in rig.machine.snapshot().last_error


def test_a_stop_during_start_robot_leaves_it_not_started() -> None:
    reached = threading.Event()

    def initialize(say, interrupted) -> None:
        reached.set()
        deadline = time.monotonic() + SETTLE_S
        while not interrupted():
            assert time.monotonic() < deadline, "the initialization was never stopped"
            time.sleep(0.005)
        raise Interrupted("stopped")

    rig = Rig(initialize=initialize)
    join = rig.in_thread(rig.machine.start_robot)
    assert reached.wait(SETTLE_S)
    assert rig.machine.stop().success
    assert not join().success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.NOT_STARTED and not snapshot.robot_started


# --- D4: in FAULT with the twin out of SIM, Stop asks for SIM again -----------


def test_stop_in_a_fault_with_the_twin_out_of_sim_asks_for_sim_again() -> None:
    rig = Rig(physical=["counterpart"]).started()
    rig.away = [None]
    rig.left = [False]
    join = rig.in_thread(lambda: rig.machine.home(0.1, TWIN))
    rig.answer()
    join()
    assert rig.machine.snapshot().state == ConsoleState.FAULT
    rig.heard = TwinMode.MODE_VALIDATED
    rig.calls.clear()
    outcome = rig.machine.stop()
    assert outcome.success, outcome.detail
    assert rig.calls == [("return_to_sim",), ("close",)]
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT and not snapshot.busy
    assert "confirmed SIM" in snapshot.last_error
    # A second refusal is said, and the console stays in FAULT.
    rig.left = [False]
    outcome = rig.machine.stop()
    assert not outcome.success and "did not confirm SIM" in outcome.detail
    # With the twin heard in SIM there is nothing for Stop to do.
    rig.heard = TwinMode.MODE_SIM
    assert not rig.machine.stop().success


def test_stop_in_a_fault_on_an_all_simulated_pair_does_nothing() -> None:
    rig = Rig(holding=True)
    rig.machine.start_robot()
    rig.heard = TwinMode.MODE_VALIDATED
    rig.calls.clear()
    assert not rig.machine.stop().success
    assert rig.calls == []


# --- D10: what may lie on each side's table is tracked per side --------------


def test_a_side_whose_spawn_failed_is_cleared_before_the_next_part(monkeypatch) -> None:
    """`program.part`: a side counts as holding a box from the moment its spawn is tried."""
    from cite_bringup.program import part

    log: list[tuple[str, str]] = []
    monkeypatch.setattr(part, "is_physical", lambda _plan, _side: False)
    monkeypatch.setattr(
        part,
        "_remove",
        lambda _zone, side, _world, _interrupted=None: log.append(("remove", side)),
    )
    failing = {"counterpart"}

    def spawn(_zone, side, *_args, **_kwargs):
        log.append(("spawn", side))
        return "the create failed" if side in failing else None

    monkeypatch.setattr(part, "spawn", spawn)
    may_hold: set[str] = set()
    with pytest.raises(StepFailed, match="counterpart"):
        part.place_on_simulated_sides("cell_b", may_hold, lambda _text: None)
    # The plant's box exists; the counterpart's may.
    assert may_hold == {"plant", "counterpart"}
    assert log == [("spawn", "plant"), ("spawn", "counterpart")]
    log.clear()
    failing.clear()
    part.place_on_simulated_sides("cell_b", may_hold, lambda _text: None)
    assert log == [
        ("remove", "plant"),
        ("spawn", "plant"),
        ("remove", "counterpart"),
        ("spawn", "counterpart"),
    ]


def test_a_stop_reaches_the_part_placement(monkeypatch) -> None:
    from cite_bringup.program import part

    monkeypatch.setattr(part, "is_physical", lambda _plan, _side: False)
    monkeypatch.setattr(part, "spawn", lambda *_a, **_k: pytest.fail("spawned after a stop"))
    with pytest.raises(Interrupted):
        part.place_on_simulated_sides("cell_b", set(), lambda _text: None, lambda: True)


def test_start_robot_resets_what_may_be_on_the_tables_to_every_simulated_side() -> None:
    rig = Rig()
    rig.machine._parts.clear()  # as if a run had cleared and spawned nothing
    rig.homed()
    assert rig.machine.run_program(1.0, 1, TWIN).success
    assert ("place", ("counterpart", "plant")) in rig.calls


# --- D12: a cancel stops only the request its goal owns ----------------------


def test_a_cancel_of_another_goal_does_not_stop_the_running_request() -> None:
    rig = Rig().homed()
    rig.hold_on = ("move", "pick")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN, owner=b"running"))
    assert rig.holding_step.wait(SETTLE_S)
    outcome = rig.machine.stop(owner=b"another")
    assert not outcome.success and "does not own" in outcome.detail
    assert rig.machine.snapshot().state == ConsoleState.RUNNING
    assert rig.machine.stop(owner=b"running").success
    assert not join().success
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_goal_cancelled_before_it_began_stops_at_once() -> None:
    rig = Rig().homed()
    outcome = rig.machine.run_program(1.0, 1, TWIN, owner=b"goal", cancelled=lambda: True)
    assert not outcome.success and "stopped" in outcome.detail
    assert rig.moves() == []
    assert rig.machine.snapshot().state == ConsoleState.READY


# --- D6: the end of the process ----------------------------------------------


def test_shutdown_stops_the_request_and_the_belts() -> None:
    rig = Rig().homed()
    assert rig.machine.run_program(1.0, 1, TWIN).success
    assert ("belts", False) not in rig.calls
    assert rig.machine.shutdown(SETTLE_S)
    assert rig.calls[-1] == ("belts", False)


def test_once_shutdown_began_every_request_is_refused() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    rig.hold_on = ("move", "pick")
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1, TWIN))
    rig.answer()
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.shutdown(SETTLE_S)
    join()
    assert not rig.machine.snapshot().busy
    for outcome in (
        rig.machine.start_robot(),
        rig.machine.home(0.1, TWIN),
        rig.machine.run_program(0.1, 1, TWIN),
        rig.machine.confirm_operator(),
    ):
        assert not outcome.success
    assert "closing" in rig.machine.motion_refusal(0.1, None, TWIN)


# --- D9: every snapshot is numbered, so the latest one is published ----------


def test_snapshots_are_numbered_in_the_order_they_were_taken() -> None:
    rig = Rig().homed()
    assert rig.machine.run_program(1.0, 1, TWIN).success
    numbers = [snapshot.sequence for snapshot in rig.snapshots]
    assert len(set(numbers)) == len(numbers)
    assert rig.machine.snapshot().sequence > max(numbers)


def test_the_node_never_publishes_an_older_snapshot_after_a_newer_one() -> None:
    """D9: two threads hand in snapshots out of order; the latched one is the newest."""
    from cite_bringup.program.console import CellConsole

    published: list = []

    class Publisher:
        def publish(self, message) -> None:
            published.append(message)

    class Clock:
        def now(self):
            class Now:
                def to_msg(self_inner):
                    from builtin_interfaces.msg import Time

                    return Time()

            return Now()

    node = object.__new__(CellConsole)
    node._mode_lock = threading.Lock()
    node._publish_lock = threading.Lock()
    node._twin_mode = TwinMode.MODE_SIM
    node._last = None
    node._publisher = Publisher()
    node._machine = None
    node.get_clock = lambda: Clock()
    rig = Rig()
    older = rig.machine.snapshot()
    rig.machine.start_robot()
    newer = rig.machine.snapshot()
    node._publish(newer)
    node._publish(older)
    assert [message.state for message in published] == [ConsoleState.READY]
    node._publish(rig.machine.snapshot())
    assert len(published) == 2


# --- R2-02: the shutdown is bounded, and stops the belts once ------------------


def test_shutdown_never_queues_behind_the_requests_own_belt_stop() -> None:
    """The request leaves its belts to the shutdown, which stops them once, itself."""
    rig = Rig().homed()
    rig.hold_on = ("move", "pick")
    rig.belt_stop_s = 0.5
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.shutdown(SETTLE_S, 0.1, tail_s=0.0)
    join()
    assert rig.calls.count(("belts", False)) == 1
    assert rig.belt_stoppers == [threading.current_thread().name]


def test_a_slow_stop_does_not_hold_the_shutdown_past_its_ceiling() -> None:
    """A request that does not end within the ceiling is reported, and its belts untouched."""
    rig = Rig().homed()
    rig.hold_on = ("move", "pick")
    release = threading.Event()
    # A cancel nobody answers, and that ignores the deadline: the worst fake.
    rig.on_cancel = lambda: release.wait(SETTLE_S)
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    started = time.monotonic()
    try:
        assert not rig.machine.shutdown(0.5, 0.1, tail_s=0.1)
        assert time.monotonic() - started < 0.5 + 1.0
        assert ("belts", False) not in rig.calls
    finally:
        release.set()
        join()


def test_the_shutdown_cuts_the_requests_waits_at_its_deadline() -> None:
    """A stop that waits as long as it is let - a cancel, a return to SIM - ends at the cut."""
    rig = Rig().homed()
    assert rig.machine.stop_deadline() is None
    rig.hold_on = ("move", "pick")

    def cancel_until_the_cut() -> None:
        while True:
            deadline = rig.machine.stop_deadline()
            if deadline is not None and time.monotonic() >= deadline:
                return
            time.sleep(0.005)

    rig.on_cancel = cancel_until_the_cut
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    started = time.monotonic()
    assert rig.machine.shutdown(1.0, 0.1, tail_s=0.5)
    elapsed = time.monotonic() - started
    join()
    assert 0.4 <= elapsed < 1.0, elapsed
    assert rig.machine.stop_deadline() == pytest.approx(started + 0.5, abs=0.1)


# --- R2-03: at the start is said with the release, never after it -------------


def test_a_completed_home_releases_the_request_already_at_the_start() -> None:
    """No snapshot reads the console idle after a home with the start still unknown."""
    rig = Rig().started()
    rig.away = [None]
    rig.snapshots.clear()
    assert rig.machine.home(1.0, TWIN).success
    released = next(snapshot for snapshot in rig.snapshots if not snapshot.busy)
    assert released.state == ConsoleState.READY
    assert _at_start(released)


def test_a_stopped_home_is_released_not_at_the_start() -> None:
    rig = Rig().started()
    rig.away = ["arm away", None]
    rig.hold_on = ("move", "zero")
    join = rig.in_thread(lambda: rig.machine.home(1.0, TWIN))
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.stop().success
    assert not join().success
    assert not _at_start(rig.machine.snapshot())


# --- N-03: Start program measures the start, not only remembers it ------------


def test_start_program_measures_the_start_and_refuses_when_away() -> None:
    rig = Rig().homed()
    rig.away = ["picker_joint1 stands at 0.2000, not within 0.01 of 0.0000"]
    outcome = rig.machine.run_program(1.0, 1, TWIN)
    assert not outcome.success
    assert "not at the program's start" in outcome.detail and "Home first" in outcome.detail
    # Measured first, and nothing after: no part, no belt, no mode, no step.
    assert [call[0] for call in rig.calls] == ["measure", "close"]
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY and not snapshot.busy
    assert not _at_start(snapshot)
    assert "Home first" in rig.machine.motion_refusal(1.0, 1, TWIN)


def test_start_program_at_the_start_measures_once_then_runs() -> None:
    rig = Rig().homed()
    assert rig.machine.run_program(1.0, 1, TWIN).success
    assert rig.calls[0] == ("measure",)
    assert [call for call in rig.calls if call == ("measure",)] == [("measure",)]


# --- N-04: every mode but SIM is foreign on a physical pair, unless entered here


@pytest.mark.parametrize(
    "mode",
    [
        TwinMode.MODE_REAL,
        TwinMode.MODE_SHADOW,
        TwinMode.MODE_VALIDATED,
        TwinMode.MODE_CLOSED_LOOP,
        TwinMode.MODE_VIRTUAL_LEAD,
    ],
)
def test_every_mode_but_sim_this_console_did_not_enter_refuses(mode: int) -> None:
    rig = Rig(physical=["counterpart"]).homed()
    rig.heard = mode
    refusal = rig.machine.motion_refusal(0.1, 1, TWIN)
    assert refusal is not None and "did not ask for" in refusal
    assert not rig.machine.start_robot().success
    assert rig.speeds == []


def test_the_mode_this_console_entered_is_not_foreign() -> None:
    rig = Rig(physical=["counterpart"]).homed()
    rig.machine._set_entered(True)
    rig.heard = TwinMode.MODE_VALIDATED
    assert rig.machine.motion_refusal(0.1, 1, TWIN) is None


# --- A refusal reaches the published state (P-R01) ---------------------------


def test_a_refused_goal_is_published_as_last_error_and_changes_no_state() -> None:
    """P-R01: a rejected goal says nothing to its client; the state carries the reason."""
    rig = Rig()
    before = len(rig.snapshots)
    refusal = rig.machine.motion_refusal(1.0, None, TWIN)
    assert refusal is not None
    rig.machine.record_refusal(refusal)
    published = rig.snapshots[-1]
    assert len(rig.snapshots) == before + 1
    assert published.last_error == f"refused: {refusal}"
    assert published.state == ConsoleState.NOT_STARTED and not published.busy
    # The next request that begins clears it, as any error.
    assert rig.machine.start_robot().success
    assert rig.machine.snapshot().last_error == ""


def test_every_refused_request_publishes_its_reason() -> None:
    rig = Rig()
    for request in (
        lambda: rig.machine.home(1.0, TWIN),
        lambda: rig.machine.run_program(1.0, 1, TWIN),
        rig.machine.confirm_operator,
    ):
        outcome = request()
        assert not outcome.success
        snapshot = rig.machine.snapshot()
        assert snapshot.last_error == f"refused: {outcome.detail}"
        assert snapshot.state == ConsoleState.NOT_STARTED
    rig.terminal = "/fixed_program"
    outcome = rig.machine.start_robot()
    assert not outcome.success
    assert rig.machine.snapshot().last_error == f"refused: {outcome.detail}"


def test_a_refusal_in_fault_keeps_the_fault_cause() -> None:
    """R-01: a refused request in FAULT publishes its reason beside the fault's, not over it."""
    rig = Rig().homed()
    rig.fail_on = ("move", "place")
    assert not rig.machine.run_program(1.0, 1, TWIN).success
    cause = rig.machine.snapshot().last_error
    assert rig.machine.snapshot().state == ConsoleState.FAULT and "move place" in cause
    rig.terminal = "/fixed_program"
    outcome = rig.machine.start_robot()
    assert not outcome.success
    published = rig.snapshots[-1]
    assert published.state == ConsoleState.FAULT
    assert published.last_error == f"refused: {outcome.detail} (fault: {cause})"
    # A second refusal still carries the cause, once.
    rig.machine.record_refusal("again")
    assert rig.snapshots[-1].last_error == f"refused: again (fault: {cause})"
    # Leaving FAULT drops it: a refusal in READY carries none.
    rig.terminal = None
    assert rig.machine.start_robot().success
    assert not rig.machine.confirm_operator().success
    assert "fault:" not in rig.machine.snapshot().last_error


# --- A terminal program client on the graph (S-01) ---------------------------


def test_a_terminal_client_on_the_graph_refuses_every_motion_request() -> None:
    """S-01: the console does not start motion beside a terminal run of the program."""
    rig = Rig().homed()
    rig.terminal = "/fixed_program"
    refusal = rig.machine.motion_refusal(1.0, 1, TWIN)
    assert refusal is not None and "/fixed_program" in refusal
    for outcome in (
        rig.machine.home(1.0, TWIN),
        rig.machine.run_program(1.0, 1, TWIN),
        rig.machine.start_robot(),
    ):
        assert not outcome.success and "terminal program client" in outcome.detail
    # Refused before anything was touched.
    assert rig.calls == [] and rig.speeds == []
    rig.terminal = None
    assert rig.machine.motion_refusal(1.0, 1, TWIN) is None


def test_a_terminal_client_does_not_hold_back_the_return_to_sim() -> None:
    """The one request that only asks for SIM stops, it does not move: not refused."""
    rig = Rig(physical=["counterpart"]).started()
    rig.away = [None]
    rig.left = [False]
    join = rig.in_thread(lambda: rig.machine.home(0.1, TWIN))
    rig.answer()
    join()
    assert rig.machine.snapshot().state == ConsoleState.FAULT
    rig.heard = TwinMode.MODE_VALIDATED
    rig.terminal = "/fixed_program"
    rig.calls.clear()
    outcome = rig.machine.stop()
    assert outcome.success, outcome.detail
    assert rig.calls == [("return_to_sim",), ("close",)]
