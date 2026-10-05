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
from pathlib import Path
import signal

from cite_bringup.plan import default_plan_path, load
from cite_bringup.program import belt as belt_command
from cite_bringup.program.__main__ import main as program_main
from cite_bringup.program.cell import (
    ask_until_accepted,
    await_arrival,
    holding_refusal,
    RosCell,
    state_topic,
    track_trajectory,
    twin_name,
)
from cite_bringup.program.from_plan import program, target
from cite_bringup.program.sides import physical_sides, required_speed_scale, simulated_sides
from cite_bringup.program.steps import (
    belt,
    EXIT_INTERRUPTED,
    install_interrupt_handlers,
    move,
    run,
    scaled_motion,
    speed_scale,
    StepFailed,
    wait,
)
from cite_bringup.readiness import PHYSICAL_SIDE_NOT_READY
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


def test_a_track_move_runs_from_where_the_program_read_it(cell) -> None:
    """|distance| / speed seconds away, from the read start (ADR-0067, SA2c-S-02 b).

    The start point is what lets a physical side take the commanded speed from
    the message rather than from where its own carriage stands.
    """
    trajectory = track_trajectory(cell.track, 0.0, 0.65, 6.5)
    assert trajectory.joint_names == [cell.track.joint]
    start, end = trajectory.points
    assert list(start.positions) == [0.0]
    assert (start.time_from_start.sec, start.time_from_start.nanosec) == (0, 0)
    assert list(end.positions) == [0.65]
    assert (end.time_from_start.sec, end.time_from_start.nanosec) == (6, 500_000_000)
    assert list(start.velocities) == [0.0] and list(end.velocities) == [0.0]


class _Publisher:
    def __init__(self) -> None:
        self.sent: list = []

    def publish(self, message) -> None:
        self.sent.append(message)


def _cancelling(cell, via: str):
    ros = object.__new__(RosCell)
    ros.node = None
    ros._active = None
    ros._sent = None
    ros._via = via
    ros._track = cell.track
    ros._track_command = _Publisher()
    ros._track_target = 0.65
    ros._track_position = 0.2
    return ros


def test_a_cancel_through_the_twin_never_sends_the_plants_position(cell) -> None:
    """SA2c-S-02 a: a stop with no position, which the boundary holds per side."""
    ros = _cancelling(cell, "twin")
    ros.cancel()
    (stop,) = ros._track_command.sent
    assert stop.joint_names == [cell.track.joint]
    assert list(stop.points) == []


def test_a_cancel_on_one_side_holds_that_side_where_it_stands(cell) -> None:
    ros = _cancelling(cell, "plant")
    ros.cancel()
    (held,) = ros._track_command.sent
    assert [list(p.positions) for p in held.points] == [[0.2], [0.2]]


def test_a_side_that_never_arrives_fails_the_track_step() -> None:
    """SA2c-S-02 c: the counterpart's carriage, asked of the twin, within the ceiling."""
    now = {"t": 0.0}

    def pause() -> None:
        now["t"] += 1.0

    with pytest.raises(StepFailed, match="counterpart: stands at"):
        await_arrival(
            lambda: (False, "counterpart: stands at 100.0 mm"),
            pause,
            deadline=5.0,
            what="track to 650 mm",
            clock=lambda: now["t"],
        )
    answers = iter([(False, "counterpart: moving"), (True, "")])
    await_arrival(lambda: next(answers), lambda: None, deadline=5.0, what="t", clock=lambda: 0.0)


def _tracking(cell, plant_m: float, answers: list[tuple[bool, str]]):
    """Build a twin-driven cell, its plant carriage at ``plant_m``, the twin saying ``answers``."""
    ros = object.__new__(RosCell)
    ros.node = None
    ros._via = "twin"
    ros._speed = 1.0
    ros._track = cell.track
    ros._track_command = _Publisher()
    ros._track_target = None
    ros._track_position = plant_m
    ros._track_arrived = object()
    ros._until_true = lambda predicate, what: None
    asked: list[float] = []

    def ask_arrival(position_m: float, what: str):
        asked.append(position_m)
        return lambda: answers.pop(0)

    ros._ask_arrival = ask_arrival
    return ros, asked


def test_a_track_step_is_not_skipped_on_the_plants_carriage_alone(cell) -> None:
    """SA-S-01 a: the plant at the target and the counterpart away fails the step."""
    ros, asked = _tracking(cell, 0.65, [(False, "counterpart: stands at 0.0 mm")])
    with pytest.raises(StepFailed, match="home it"):
        ros.track(0.65, 0.1)
    assert asked == [0.65]
    assert ros._track_command.sent == []


def test_a_track_step_every_side_has_reached_commands_nothing(cell) -> None:
    ros, asked = _tracking(cell, 0.65, [(True, "every commanded side is at the target")])
    ros.track(0.65, 0.1)
    assert asked == [0.65] and ros._track_command.sent == []


def test_a_track_step_with_the_plant_away_moves_and_waits_for_every_side(
    cell, monkeypatch
) -> None:
    import cite_bringup.program.cell as cell_module

    ros, asked = _tracking(
        cell, 0.0, [(False, "plant: stands at 0.0 mm"), (False, "counterpart: moving"), (True, "")]
    )
    ros._track_command.get_subscription_count = lambda: 1
    ros._track_command.topic_name = "t"

    def carriage_arrives(*_args, **_kwargs) -> None:
        ros._track_position = 0.65

    monkeypatch.setattr(cell_module.rclpy, "spin_once", carriage_arrives)
    ros.track(0.65, 0.1)
    (sent,) = ros._track_command.sent
    assert [list(point.positions) for point in sent.points] == [[0.0], [0.65]]
    assert asked == [0.65, 0.65]


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


def test_the_twin_name_is_the_sides_name_in_the_twin_scope() -> None:
    assert twin_name("/cite/cell_b/picker/move_to") == "/cite/twin/cell_b/picker/move_to"
    with pytest.raises(ValueError):
        twin_name("/elsewhere/move_to")


# --- A physical side, and the speed of a first run (ADR-0070 items 6-7) -------


class _Clock:
    """A clock the test moves, so a ceiling is reached without waiting."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_validated_is_asked_again_while_the_physical_side_is_held() -> None:
    answers = [
        (False, f"{PHYSICAL_SIDE_NOT_READY}: entering VALIDATED would ... - held"),
        (False, f"{PHYSICAL_SIDE_NOT_READY}: entering VALIDATED would ... - held"),
        (True, "SIM -> VALIDATED"),
    ]
    said: list[str] = []
    pauses: list[None] = []
    ask_until_accepted(lambda: answers.pop(0), lambda: pauses.append(None), said.append)
    assert answers == [] and len(pauses) == 2
    assert len(said) == 1, "one line per new reason, not one per ask"


def test_any_other_refusal_is_final_at_once() -> None:
    asked: list[None] = []

    def ask() -> tuple[bool, str]:
        asked.append(None)
        return False, "entering VALIDATED would place physical actuation ... opt-in"

    with pytest.raises(StepFailed, match="refused VALIDATED"):
        ask_until_accepted(ask, lambda: None, lambda text: None)
    assert len(asked) == 1


def test_a_side_never_ready_fails_at_the_ceiling() -> None:
    clock = _Clock()

    def pause() -> None:
        clock.now += 1.0

    with pytest.raises(StepFailed, match="not ready within"):
        ask_until_accepted(
            lambda: (False, f"{PHYSICAL_SIDE_NOT_READY}: held"),
            pause,
            lambda text: None,
            ceiling_s=5.0,
            clock=clock,
        )
    assert clock.now > 5.0


@pytest.mark.parametrize("value", [0.0, -0.1, 1.5, float("nan"), float("inf")])
def test_a_speed_scale_outside_zero_to_one_is_refused(value: float) -> None:
    with pytest.raises(ValueError):
        speed_scale(value)


def test_full_speed_is_the_program_as_written() -> None:
    assert scaled_motion(0.111, 0.35, 0.35, 1.0) == (0.111, 0.0)
    assert scaled_motion(0.0, 0.35, 0.35, 1.0) == (0.0, 0.0)


def test_a_tenth_scales_velocity_and_acceleration_and_never_widens_anything() -> None:
    velocity, acceleration = scaled_motion(0.111, 0.35, 0.35, 0.1)
    assert velocity == pytest.approx(0.0111)
    assert acceleration == pytest.approx(0.035)
    # A move stating no speed is slowed from the server's default, not from zero.
    assert scaled_motion(0.0, 0.35, 0.35, 0.1) == pytest.approx((0.035, 0.035))


def test_a_bad_speed_scale_is_refused_before_anything_starts(capsys) -> None:
    with pytest.raises(SystemExit) as exited:
        program_main(["--zone", ZONE, "--dry-run", "--speed-scale", "2"])
    assert exited.value.code == 2
    assert "--speed-scale" in capsys.readouterr().err


def test_the_shipped_counterpart_is_the_physical_side() -> None:
    plan = load(default_plan_path(ZONE))
    assert physical_sides(plan) == ["counterpart"]
    assert simulated_sides(plan) == ["plant"]


def test_no_belt_is_commanded_on_a_physical_side(monkeypatch, capsys) -> None:
    commanded: list[str] = []
    monkeypatch.setenv("CITE_DOMAIN_BASE", "42")
    monkeypatch.setattr(
        belt_command,
        "_set_on_one_side",
        lambda topic, speed, domain, side: commanded.append(side) or True,
    )
    assert belt_command.main(["--zone", ZONE]) == 0
    assert commanded == ["plant"]
    assert "counterpart: physical" in capsys.readouterr().out
    commanded.clear()
    assert belt_command.main(["--zone", ZONE, "--side", "counterpart", "--stop"]) == 0
    assert commanded == []


def test_a_physical_side_never_runs_at_a_defaulted_speed_scale() -> None:
    """S-04: with a physical side the operator names the scale; none is assumed."""
    plan = load(default_plan_path(ZONE))
    assert physical_sides(plan), f"{ZONE} ships a physical counterpart"
    with pytest.raises(ValueError, match="must be given explicitly"):
        required_speed_scale(plan, "")
    assert required_speed_scale(plan, "0.1") == pytest.approx(0.1)


def test_a_scale_the_physical_track_cannot_carry_out_is_refused_before_bring_up() -> None:
    """SA-S-07: the adapter's own rule, asked of the program's slowest slide."""
    from cite_bringup.program.sides import minimum_speed_scale

    plan = load(default_plan_path(ZONE))
    minimum = minimum_speed_scale(plan)
    assert minimum is not None and 0.0 < minimum < 1.0
    with pytest.raises(ValueError, match="slower than the physical track carries out"):
        required_speed_scale(plan, f"{minimum / 2:g}")
    assert required_speed_scale(plan, f"{minimum:g}") == pytest.approx(minimum)
    # The plant alone is no physical track.
    assert required_speed_scale(plan, f"{minimum / 2:g}", via="plant") == pytest.approx(
        minimum / 2
    )


@pytest.mark.parametrize("typed", ["0", "1.5", "nan", "inf", "abc", "-0.2"])
def test_the_speed_scale_range_is_the_programs_own_before_bring_up(typed: str) -> None:
    """R-06/T-02: `./scripts/program` asks this before bring-up, by `steps.speed_scale`."""
    with pytest.raises(ValueError):
        required_speed_scale(load(default_plan_path(ZONE)), typed)


def test_the_script_checks_the_speed_scale_before_it_brings_anything_up() -> None:
    """The check and the prompt, read from `scripts/program` itself."""
    script = (Path(__file__).resolve().parents[4] / "scripts" / "program").read_text()
    check = script.index("cite_bringup.program.sides --zone \"$ZONE\" --speed-scale")
    assert check < script.index("start_in_own_group")
    # The prompt is the program's own (SA-S-02, SA-S-05): the script hands it
    # the terminal and asks nothing itself.
    assert "--speed-scale \"$SPEED_SCALE\" <&0 &" in script
    assert "read -r" not in script


def test_the_program_leaves_validated_before_the_operator_steps_in(capsys) -> None:
    """Operator safety: after a run on a pair with a physical side, the twin is put in SIM.

    SIM forwards nothing to the counterpart, so the person placing the next part
    is not beside an arm the twin can still command; the next run asks for
    VALIDATED again through the opt-in and the readiness check.
    """
    from cite_interfaces.msg import TwinMode

    sent = []

    class Client:
        def wait_for_service(self, timeout_sec):
            return True

        def call_async(self, request):
            sent.append(request)
            return request

    class Node:
        def create_client(self, _type, _name):
            return Client()

    class Accepted:
        accepted = True
        current_mode = TwinMode.MODE_SIM

    ros = object.__new__(RosCell)
    ros.node = Node()
    ros._until = lambda future, what, ceiling_s=0.0: Accepted()
    assert ros.leave_validated()
    (request,) = sent
    assert request.mode == TwinMode.MODE_SIM
    assert "nothing crosses to the physical side" in capsys.readouterr().out
    main_source = (Path(__file__).resolve().parents[1] / "cite_bringup/program/__main__.py")
    text = main_source.read_text()
    assert text.index("status = run(") < text.index("ros.leave_validated()")


def test_the_module_never_runs_a_physical_pair_at_a_defaulted_scale(capsys) -> None:
    """SA-S-02: the module asks `required_speed_scale` itself, not only the script."""
    with pytest.raises(SystemExit) as exited:
        program_main(["--zone", ZONE, "--dry-run"])
    assert exited.value.code == 2
    assert "must be given explicitly" in capsys.readouterr().err
    # The plant alone is no physical side: the program as written.
    assert program_main(["--zone", ZONE, "--via", "plant", "--dry-run"]) == 0


def test_the_operator_is_asked_only_once_the_twin_is_read_in_sim() -> None:
    """SA-S-05: the prompt's "nothing crosses" is read, never assumed."""
    from cite_bringup.program.operator import confirm_operator
    from cite_interfaces.msg import TwinMode

    said: list[str] = []
    asked: list[str] = []
    for mode in (None, TwinMode.MODE_VALIDATED):
        with pytest.raises(StepFailed):
            confirm_operator(mode, ["counterpart"], 0.1, said.append, asked.append)
    assert said == [] and asked == []
    confirm_operator(TwinMode.MODE_SIM, ["counterpart"], 0.1, said.append, asked.append)
    assert any("speed scale 0.1" in line for line in said) and len(asked) == 1

    def no_answer(_prompt: str) -> str:
        raise EOFError

    with pytest.raises(StepFailed, match="no operator answer"):
        confirm_operator(TwinMode.MODE_SIM, ["counterpart"], 0.1, said.append, no_answer)


class _PairCell:
    """`RosCell` on a pair with a physical side, as far as `main` uses it."""

    mode = None
    left = True
    calls: list[str] = []

    def __init__(self, *_args, **_kwargs) -> None:
        _PairCell.calls = []

    def twin_mode(self):
        return _PairCell.mode

    def refuse_if_holding(self) -> None:
        _PairCell.calls.append("refuse_if_holding")

    def enter_validated(self) -> None:
        _PairCell.calls.append("enter_validated")

    def leave_validated(self) -> bool:
        _PairCell.calls.append("leave_validated")
        return _PairCell.left


def _main_on_a_pair(monkeypatch, mode, left: bool, answers=("",)) -> int:
    import builtins

    import cite_bringup.program.__main__ as program_module
    import cite_bringup.program.cell as cell_module
    import rclpy

    _PairCell.mode, _PairCell.left = mode, left
    answers = list(answers)
    monkeypatch.setattr(cell_module, "RosCell", _PairCell)
    monkeypatch.setattr(rclpy, "init", lambda **_kwargs: None)
    monkeypatch.setattr(rclpy, "try_shutdown", lambda: None)
    monkeypatch.setattr(program_module, "install_interrupt_handlers", lambda: None)
    monkeypatch.setattr(program_module, "run", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": answers.pop(0))
    return program_main(["--zone", ZONE, "--speed-scale", "0.1"])


def test_a_run_whose_return_to_sim_is_unconfirmed_fails(monkeypatch) -> None:
    """SA-S-05: a failed leave_validated is the run's failure, so no one is asked in next."""
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True) == 0
    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=False) != 0
    assert _PairCell.calls[-1] == "leave_validated"


def test_a_twin_not_in_sim_is_never_entered_and_no_one_is_asked(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_VALIDATED, left=True, answers=()) == 1
    assert _PairCell.calls == []
