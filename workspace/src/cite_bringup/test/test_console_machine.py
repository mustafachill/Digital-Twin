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
)
from cite_bringup.program.home import StartPose
from cite_bringup.program.steps import grip, Interrupted, move, release, StepFailed, track
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
        return self._rig.mode

    def carriage_refusal(self, homing: bool = False):
        self._call("carriage_refusal", homing)
        return None

    def refuse_if_holding(self) -> None:
        self._call("refuse_if_holding")
        if self._rig.holding:
            raise StepFailed("the arm is holding workpiece")

    def enter_validated(self, homing: bool = False) -> None:
        self._call("enter_validated", homing)

    def leave_validated(self) -> bool:
        self._call("leave_validated")
        return True

    def away_from_start(self, start):
        self._call("measure")
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
        self._call("cancel")
        if self._rig.cancel_fails:
            raise StepFailed("the cancel was not answered")

    def _step(self, *call) -> None:
        self._call(*call)
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
        self, physical=(), mode=TwinMode.MODE_SIM, holding=False, initialize=None
    ) -> None:
        self.calls: list[tuple] = []
        self.mode = mode
        self.holding = holding
        self.away: list[str | None] = []
        self.fail_on: tuple | None = None
        self.hold_on: tuple | None = None
        self.cancel_fails = False
        self.belts_confirm = True
        self.holding_step = threading.Event()
        self.speeds: list = []
        self.snapshots = []
        self._changed = threading.Condition()
        self.machine = ConsoleMachine(
            physical=list(physical),
            home_steps=HOME_STEPS,
            start=START,
            steps=PROGRAM,
            make_cell=self._make_cell,
            initialize_physical=initialize
            or (lambda say, interrupted: self.calls.append(("initialize",))),
            place_parts=lambda remove_first, say: self.calls.append(("place", remove_first)),
            set_belts=self._set_belts,
            on_change=self._on_change,
            log=lambda text: None,
        )

    def _make_cell(self, speed, interrupted) -> FakeCell:
        self.speeds.append(speed)
        return FakeCell(self, speed, interrupted)

    def _set_belts(self, running: bool, say) -> bool:
        self.calls.append(("belts", running))
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

    def started(self) -> "Rig":
        assert self.machine.start_robot().success
        self.calls.clear()
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


# --- Gating: nothing before Start robot, one request at a time ---------------


def test_nothing_but_start_robot_is_accepted_before_it_succeeds() -> None:
    rig = Rig()
    assert rig.machine.snapshot().state == ConsoleState.NOT_STARTED
    for outcome in (rig.machine.home(1.0), rig.machine.run_program(1.0, 1)):
        assert not outcome.success
        assert "Start robot" in outcome.detail
    assert "Start robot" in rig.machine.motion_refusal(1.0)
    # Refused before anything was touched.
    assert rig.speeds == [] and rig.calls == []
    assert rig.machine.snapshot().state == ConsoleState.NOT_STARTED


def test_start_robot_initializes_then_reads_custody_and_is_ready() -> None:
    rig = Rig()
    outcome = rig.machine.start_robot()
    assert outcome.success
    assert rig.calls == [("initialize",), ("refuse_if_holding",), ("close",)]
    # Start robot's cell only reads: it is built with no scale and never stepped.
    assert rig.speeds == [None]
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY
    assert snapshot.robot_started and not snapshot.busy
    assert rig.machine.motion_refusal(1.0) is None


def test_a_failed_start_is_a_fault_and_the_robot_is_not_started() -> None:
    rig = Rig(holding=True)
    outcome = rig.machine.start_robot()
    assert not outcome.success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert not snapshot.robot_started
    assert "holding" in snapshot.last_error
    assert "Start robot" in rig.machine.motion_refusal(1.0)


def test_confirm_part_is_refused_outside_awaiting_part() -> None:
    rig = Rig()
    assert not rig.machine.confirm_part().success
    rig.started()
    outcome = rig.machine.confirm_part()
    assert not outcome.success
    assert "AWAITING_PART" in outcome.detail


def test_stop_with_nothing_in_progress_is_refused() -> None:
    rig = Rig().started()
    outcome = rig.machine.stop()
    assert not outcome.success
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_one_request_at_a_time() -> None:
    rig = Rig(physical=["counterpart"]).started()
    join = rig.in_thread(lambda: rig.machine.run_program(0.5, 1))
    rig.wait_for_state(ConsoleState.AWAITING_PART)
    assert "in progress" in rig.machine.motion_refusal(0.5)
    assert not rig.machine.home(0.5).success
    assert not rig.machine.start_robot().success
    assert rig.machine.stop().success
    join()


# --- Speed: sent with every goal, validated, never defaulted -----------------


@pytest.mark.parametrize("scale", [0.0, -0.1, 1.0001, 2.0, math.nan, math.inf])
def test_a_speed_scale_outside_zero_to_one_is_rejected(scale: float) -> None:
    rig = Rig().started()
    assert "(0, 1]" in rig.machine.motion_refusal(scale)
    assert not rig.machine.home(scale).success
    assert not rig.machine.run_program(scale, 1).success
    assert rig.speeds == [None], "a cell was built for a rejected goal"


def test_zero_cycles_is_rejected_rather_than_read_as_forever() -> None:
    rig = Rig().started()
    assert "at least 1" in rig.machine.motion_refusal(1.0, 0)
    assert not rig.machine.run_program(1.0, 0).success


def test_every_motion_cell_runs_at_the_goals_own_scale() -> None:
    rig = Rig().started()
    rig.away = ["away", None]
    assert rig.machine.home(0.3).success
    assert rig.machine.run_program(0.7, 1).success
    assert rig.speeds == [None, 0.3, 0.7]
    assert rig.machine.snapshot().speed_scale == 0.7


# --- The order the library is called in ---------------------------------------


def test_home_on_a_simulated_pair_is_bring_to_start() -> None:
    rig = Rig().started()
    rig.away = ["joint1 away", None]
    outcome = rig.machine.home(1.0)
    assert outcome.success, outcome.detail
    assert rig.calls == [
        ("initialize",),
        ("measure",),
        ("enter_validated", True),
        ("move", "zero"),
        ("track", 0.0),
        ("measure",),
        ("enter_validated", False),
        ("close",),
    ]
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_run_on_a_simulated_pair_places_a_part_then_runs_each_cycle() -> None:
    rig = Rig().started()
    outcome = rig.machine.run_program(1.0, 2)
    assert outcome.success, outcome.detail
    assert outcome.cycles_completed == 2
    head = rig.calls[: rig.calls.index(("enter_validated", False)) + 1]
    assert head == [
        ("place", False),
        ("belts", True),
        ("refuse_if_holding",),
        ("enter_validated", False),
    ]
    # The second cycle takes the first cycle's part off before placing one,
    # and the belts already run.
    second = rig.calls.index(("place", True))
    assert ("belts", True) not in rig.calls[second:]
    assert rig.moves() == ["pick", "place"] * 2
    # No operator is asked and no SIM is asked for on a simulated pair.
    assert ("twin_mode",) not in rig.calls and ("leave_validated",) not in rig.calls
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY and not snapshot.busy


def test_a_physical_run_awaits_the_part_after_reading_sim_then_returns_to_sim() -> None:
    rig = Rig(physical=["counterpart"]).started()
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1))
    rig.wait_for_state(ConsoleState.AWAITING_PART)
    assert rig.machine.snapshot().step == PLACE_PROMPT
    # Asked only once the mode was read and the carriage judged; nothing entered.
    assert rig.calls[-2:] == [("twin_mode",), ("carriage_refusal", False)]
    assert ("enter_validated", False) not in rig.calls
    assert rig.machine.confirm_part().success
    outcome = join()
    assert outcome.success, outcome.detail
    after = rig.calls[rig.calls.index(("carriage_refusal", False)) + 1:]
    assert after[:2] == [("refuse_if_holding",), ("enter_validated", False)]
    assert after[-2:] == [("leave_validated",), ("close",)]


def test_a_physical_home_asks_the_operator_then_returns_to_sim() -> None:
    rig = Rig(physical=["counterpart"]).started()
    rig.away = [None]
    join = rig.in_thread(lambda: rig.machine.home(0.1))
    rig.wait_for_state(ConsoleState.AWAITING_PART)
    assert rig.machine.snapshot().step == HOME_PROMPT
    assert rig.calls[-1] == ("carriage_refusal", True)
    assert rig.machine.confirm_part().success
    assert join().success
    assert rig.calls[-2:] == [("leave_validated",), ("close",)]


def test_a_physical_run_is_refused_when_the_twin_is_not_in_sim() -> None:
    rig = Rig(physical=["counterpart"], mode=TwinMode.MODE_VALIDATED).started()
    outcome = rig.machine.run_program(0.1, 1)
    assert not outcome.success
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "not SIM" in snapshot.last_error
    # Never asked, never entered, nothing moved.
    assert not any(s.state == ConsoleState.AWAITING_PART for s in rig.snapshots)
    assert ("enter_validated", False) not in rig.calls
    assert rig.moves() == []


def test_a_physical_run_with_no_mode_heard_is_refused() -> None:
    rig = Rig(physical=["counterpart"], mode=None).started()
    assert not rig.machine.run_program(0.1, 1).success
    assert "no twin mode" in rig.machine.snapshot().last_error


# --- Stop and failure: READY or FAULT, and never a homing move ---------------


def test_stop_during_running_cancels_and_returns_ready_without_homing() -> None:
    rig = Rig().started()
    rig.hold_on = ("move", "place")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 3))
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.snapshot().state == ConsoleState.RUNNING
    assert rig.machine.stop().success
    assert rig.machine.stop().detail == "already stopping"
    outcome = join()
    assert not outcome.success and outcome.cycles_completed == 0
    stopped_at = rig.calls.index(("move", "place"))
    after = rig.calls[stopped_at + 1:]
    assert ("cancel",) in after
    # The belts this console started are stopped; nothing else moves.
    assert ("belts", False) in after
    assert [call for call in after if call[0] in ("move", "track", "grip")] == []
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.READY
    assert snapshot.robot_started and not snapshot.busy
    assert any(s.state == ConsoleState.STOPPING for s in rig.snapshots)


def test_stop_while_awaiting_the_part_enters_nothing_and_returns_ready() -> None:
    rig = Rig(physical=["counterpart"]).started()
    join = rig.in_thread(lambda: rig.machine.run_program(0.1, 1))
    rig.wait_for_state(ConsoleState.AWAITING_PART)
    assert rig.machine.stop().success
    assert not join().success
    assert ("enter_validated", False) not in rig.calls
    assert rig.machine.snapshot().state == ConsoleState.READY
    # The go-ahead it was waiting for is no longer asked.
    assert not rig.machine.confirm_part().success


def test_a_stop_during_a_home_cancels_and_does_not_home_again() -> None:
    rig = Rig().started()
    rig.away = ["away"]
    rig.hold_on = ("track", 0.0)
    join = rig.in_thread(lambda: rig.machine.home(1.0))
    assert rig.holding_step.wait(SETTLE_S)
    assert rig.machine.stop().success
    assert not join().success
    assert rig.calls[rig.calls.index(("track", 0.0)) + 1] == ("cancel",)
    assert rig.moves() == ["zero"]
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_failed_step_is_a_fault_and_nothing_homes() -> None:
    rig = Rig().started()
    rig.fail_on = ("move", "place")
    outcome = rig.machine.run_program(1.0, 2)
    assert not outcome.success and outcome.cycles_completed == 0
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "move place" in snapshot.last_error
    after = rig.calls[rig.calls.index(("move", "place")) + 1:]
    assert ("cancel",) in after and ("belts", False) in after
    assert [call for call in after if call[0] in ("move", "track", "grip")] == []
    # A FAULT is left by Start robot and by nothing else.
    assert "FAULT" in rig.machine.motion_refusal(1.0)
    assert rig.machine.start_robot().success
    assert rig.machine.snapshot().state == ConsoleState.READY


def test_a_stop_whose_cancel_fails_is_a_fault() -> None:
    rig = Rig().started()
    rig.hold_on = ("move", "pick")
    rig.cancel_fails = True
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1))
    assert rig.holding_step.wait(SETTLE_S)
    rig.machine.stop()
    join()
    snapshot = rig.machine.snapshot()
    assert snapshot.state == ConsoleState.FAULT
    assert "cancel" in snapshot.last_error


def test_a_belt_that_does_not_confirm_its_stop_is_a_fault() -> None:
    rig = Rig().started()
    rig.hold_on = ("move", "pick")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1))
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


def test_shutdown_stops_the_request_and_the_belts() -> None:
    rig = Rig().started()
    assert rig.machine.run_program(1.0, 1).success
    assert ("belts", False) not in rig.calls
    assert rig.machine.shutdown(SETTLE_S)
    assert rig.calls[-1] == ("belts", False)
