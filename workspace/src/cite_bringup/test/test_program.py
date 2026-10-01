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

"""The fixed program (ADR-0066, ADR-0067), run against a fake cell: order and stop.

Nothing here moves an arm. What moves one is `tests/scenarios/program_cycle.py`.
"""

from __future__ import annotations

import os
import signal

from cite_bringup.plan import default_plan_path, load
from cite_bringup.program import cell_b_pick_place
from cite_bringup.program.cell import (
    holding_refusal,
    RosCell,
    state_topic,
    track_trajectory,
    twin_name,
)
from cite_bringup.program.from_plan import program, target
from cite_bringup.program.steps import (
    belt,
    EXIT_INTERRUPTED,
    install_interrupt_handlers,
    move,
    run,
    StepFailed,
    wait,
)
from cite_interfaces.msg import RobotState
import pytest

ZONE = "cell_b"


class FakeCell:
    """Records every call; fails or interrupts on the step it is told to."""

    def __init__(self, fail_on: str | None = None, interrupt_on: str | None = None) -> None:
        self.calls: list[tuple] = []
        self._fail_on = fail_on
        self._interrupt_on = interrupt_on

    def _record(self, *call) -> None:
        self.calls.append(call)
        if call[:2] == ("move", self._fail_on):
            raise StepFailed(f"move to {self._fail_on}: result code 3: refused")
        if call[:2] == ("move", self._interrupt_on):
            raise KeyboardInterrupt

    def move(self, pose: str, velocity_scaling: float) -> None:
        self._record("move", pose, velocity_scaling)

    def grip(self, width_m: float, expect_object: bool) -> None:
        self._record("grip", width_m, expect_object)

    def belt(self, speed_mps: float) -> None:
        self._record("belt", speed_mps)

    def wait(self, seconds: float) -> None:
        self._record("wait", seconds)

    def track(self, position_m: float, speed_mps: float) -> None:
        self._record("track", position_m, speed_mps)

    def cancel(self) -> None:
        self._record("cancel")


@pytest.fixture(scope="module")
def cell():
    return target(load(default_plan_path(ZONE)))


def _quiet(_: str) -> None:
    pass


def test_the_program_is_the_plans_step_for_step(cell) -> None:
    """Every step the plan states, in its order, and nothing else (ADR-0067)."""
    fake = FakeCell()
    assert run(program(cell), fake, cycles=1, say=_quiet) == 0
    ran = [call for call in fake.calls if call[0] != "cancel"]
    assert [call[0] for call in ran] == [step.kind for step in cell.program.steps]
    for call, step in zip(ran, cell.program.steps, strict=True):
        if step.kind == "move":
            assert call[1:] == (step.pose, step.velocity_scaling)
        elif step.kind == "track":
            assert call[1:] == (step.position_m, step.speed_mps)


def test_the_real_program_picks_slides_and_places(cell) -> None:
    """The shape the real robot's program has, read through the plan."""
    fake = FakeCell()
    run(program(cell), fake, cycles=1, say=_quiet)
    tracks = [call[1] for call in fake.calls if call[0] == "track"]
    assert tracks == [0.0, 0.65, 0.0]
    grips = [call for call in fake.calls if call[0] == "grip"]
    assert [expect for _, _, expect in grips] == [False, True, False]
    assert grips[1][1] < grips[0][1], "the close is narrower than the open"
    moves = [call for call in fake.calls if call[0] == "move"]
    assert moves[0][1] == moves[-1][1] == "zero"
    assert all(0.0 < scaling < 1.0 for _, _, scaling in moves)
    # The real program has no belt block, so the runner never touches a belt.
    assert not [call for call in fake.calls if call[0] == "belt"]


def test_a_caller_running_one_cycle_at_a_time_numbers_them_itself(cell) -> None:
    lines: list[str] = []
    assert run(program(cell), FakeCell(), cycles=1, say=lines.append, first_cycle=3) == 0
    assert lines[0].startswith("[cycle 3, step 1/")
    assert "done: 1 cycle(s)" in lines


def test_the_first_failure_stops_the_program(cell) -> None:
    fake = FakeCell(fail_on="blockly_03")
    assert run(program(cell), fake, cycles=3, say=_quiet) == 1
    moves = [call[1] for call in fake.calls if call[0] == "move"]
    assert moves[-1] == "blockly_03", "a step ran after the failure"
    assert fake.calls[-1] == ("cancel",)


def test_ctrl_c_cancels(cell) -> None:
    fake = FakeCell(interrupt_on="blockly_06")
    assert run(program(cell), fake, cycles=0, say=_quiet) == EXIT_INTERRUPTED
    assert fake.calls[-1] == ("cancel",)


def test_a_program_that_drives_a_belt_stops_it_on_the_way_out() -> None:
    """ADR-0066's rule, kept for a program that has a belt step."""
    fake = FakeCell()
    run([belt(0.15), move("home"), wait(1.0)], fake, cycles=2, say=_quiet)
    assert fake.calls[-2:] == [("cancel",), ("belt", 0.0)]


def test_a_stop_that_cannot_be_sent_fails_a_clean_run() -> None:
    """S-03: a belt nobody stopped is a failure, however well the steps went."""

    class NoBelt(FakeCell):
        def belt(self, speed_mps: float) -> None:
            super().belt(speed_mps)
            if speed_mps == 0.0:
                raise StepFailed("no subscriber on the belt")

    said: list[str] = []
    assert run([belt(0.15), move("home")], NoBelt(), cycles=1, say=said.append) == 1
    assert any("NOT confirmed stopped" in line for line in said)


def test_a_second_interrupt_does_not_abandon_the_stop() -> None:
    """R-01: Ctrl-C reaches the program and the script forwards one more."""

    class Doubled(FakeCell):
        def cancel(self) -> None:
            super().cancel()
            os.kill(os.getpid(), signal.SIGINT)

    install_interrupt_handlers()
    try:
        fake = Doubled(interrupt_on="pick")
        steps = [belt(0.15), move("pick")]
        assert run(steps, fake, cycles=1, say=_quiet) == EXIT_INTERRUPTED
        assert fake.calls[-2:] == [("cancel",), ("belt", 0.0)]
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)


def test_an_inherited_ignored_sigint_is_restored() -> None:
    """R-01: a job started with `&` inherits SIGINT as SIG_IGN."""
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        install_interrupt_handlers()
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
        assert signal.getsignal(signal.SIGTERM) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, previous)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)


def test_a_held_part_refuses_the_start() -> None:
    """S-04: the first step opens the gripper, so a held part or silence refuses."""
    assert holding_refusal(RobotState(gripper_holding=False), "/t") is None
    assert "holding" in holding_refusal(RobotState(gripper_holding=True), "/t")
    assert "no RobotState" in holding_refusal(None, "/t")


def test_the_state_topic_is_beside_the_skills(cell) -> None:
    assert state_topic(cell.arm) == cell.arm.skills.move_to.rsplit("/", 1)[0] + "/state"


def test_a_track_move_is_one_point_at_the_programs_speed(cell) -> None:
    """|distance| / speed seconds away, in the controller's clock (ADR-0067)."""
    trajectory = track_trajectory(cell.track, 0.65, 6.5)
    assert trajectory.joint_names == [cell.track.joint]
    (point,) = trajectory.points
    assert list(point.positions) == [0.65]
    assert (point.time_from_start.sec, point.time_from_start.nanosec) == (6, 500_000_000)


def test_an_interrupt_before_acceptance_still_cancels(monkeypatch) -> None:
    """S-05: a goal accepted after the interrupt is cancelled, not left running."""
    import cite_bringup.program.cell as cell_module

    class Done:
        def __init__(self, value) -> None:
            self._value = value

        def done(self) -> bool:
            return True

        def result(self):
            return self._value

    class Handle:
        accepted = True
        cancelled = False

        def cancel_goal_async(self):
            Handle.cancelled = True
            return Done(None)

    monkeypatch.setattr(cell_module.rclpy, "spin_until_future_complete", lambda *a, **k: None)
    ros = object.__new__(RosCell)
    ros.node = None
    ros._active = None
    ros._track_target = None
    ros._sent = Done(Handle())
    ros.cancel()
    assert Handle.cancelled
    assert ros._sent is None


def test_a_wait_for_a_condition_is_bounded_by_time_not_by_spins(monkeypatch) -> None:
    """A `spin_once` that returns at once (a `/clock` message) must not end the wait.

    The wait used to be a count of spins; under use_sim_time every `/clock`
    sample returns `spin_once` immediately, so the "60 s" wait for RobotState
    ended in a second or two, before discovery had finished.
    """
    import cite_bringup.program.cell as cell_module

    spins = {"n": 0}

    def instant_spin(*_args, **_kwargs) -> None:
        spins["n"] += 1

    monkeypatch.setattr(cell_module.rclpy, "spin_once", instant_spin)
    ros = object.__new__(RosCell)
    ros.node = None
    # Far more instant spins than SERVER_WAIT_S / 0.1 before the condition holds.
    ros._until_true(lambda: spins["n"] >= 10 * int(cell_module.SERVER_WAIT_S / 0.1), "it")

    clock = {"t": 0.0}

    def fake_monotonic() -> float:
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr(cell_module.time, "monotonic", fake_monotonic)
    with pytest.raises(StepFailed):
        ros._until_true(lambda: False, "it")
    assert clock["t"] > cell_module.SERVER_WAIT_S


def test_a_cell_without_a_program_is_refused(tmp_path) -> None:
    """The shipped plan, with its program block removed.

    Written here rather than read from a second zone: the model declares one,
    and it has a program (ADR-0069).
    """
    import yaml

    document = yaml.safe_load(default_plan_path(ZONE).read_text())
    document["plan"].pop("programs", None)
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="program"):
        target(load(path))


def test_the_adr_0066_record_refuses_todays_plan() -> None:
    """The hand-written list is a record: its taught poses are gone from L0."""
    with pytest.raises(ValueError, match="declares no pose"):
        cell_b_pick_place.target(load(default_plan_path(ZONE)))


def test_the_twin_name_is_the_sides_name_in_the_twin_scope() -> None:
    assert twin_name("/cite/cell_b/picker/move_to") == "/cite/twin/cell_b/picker/move_to"
    with pytest.raises(ValueError):
        twin_name("/elsewhere/move_to")
