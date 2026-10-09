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
import time

from cite_bringup.plan import default_plan_path, load
from cite_bringup.program import belt as belt_command
from cite_bringup.program.__main__ import main as program_main
from cite_bringup.program.cell import (
    ask_until_accepted,
    await_arrival,
    await_heard,
    carriage_verdict,
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
from cite_bringup.program.targets import TWIN
from cite_bringup.readiness import PHYSICAL_SIDE_NOT_READY
from cite_interfaces.msg import RobotState
from cite_interfaces.srv import TrackArrived
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


def _answer(arrived: bool, detail: str, reason: int | None = None, routed: bool = True):
    """Build a `TrackArrived` answer; AWAY when not arrived unless ``reason`` says otherwise."""
    if reason is None:
        reason = TrackArrived.Response.ARRIVED if arrived else TrackArrived.Response.AWAY
    return TrackArrived.Response(arrived=arrived, reason=reason, routed=routed, detail=detail)


def _tracking(cell, plant_m: float, answers: list):
    """Build a twin-driven cell, its plant carriage at ``plant_m``, the twin saying ``answers``.

    Each answer is a `TrackArrived.Response`, or `(arrived, detail)` for a
    routed one.
    """
    answers = [_answer(*a) if isinstance(a, tuple) else a for a in answers]
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

    def ask_arrival(position_m: float, what: str, sides=()):
        asked.append(position_m)
        return lambda: answers.pop(0)

    ros._ask_arrival = ask_arrival
    ros._pause_between_asks = lambda: None
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


def test_a_track_step_in_a_mode_that_routes_no_track_command_fails(cell) -> None:
    """R-03: in SIM the plant alone "arrived" is not the step done."""
    ros, _ = _tracking(cell, 0.65, [_answer(True, "in SIM every side", routed=False)])
    with pytest.raises(StepFailed, match="not in a mode that routes"):
        ros.track(0.65, 0.1)
    assert ros._track_command.sent == []


def test_a_drop_to_sim_while_a_track_step_waits_fails_it(cell, monkeypatch) -> None:
    """R-03: a mid-run drop to SIM is never taken for both sides arriving."""
    import cite_bringup.program.cell as cell_module

    ros, _ = _tracking(
        cell,
        0.0,
        [(False, "plant: stands at 0.0 mm"), _answer(True, "in SIM every side", routed=False)],
    )
    ros._track_command.get_subscription_count = lambda: 1
    ros._track_command.topic_name = "t"

    def carriage_arrives(*_args, **_kwargs) -> None:
        ros._track_position = 0.65

    monkeypatch.setattr(cell_module.rclpy, "spin_once", carriage_arrives)
    with pytest.raises(StepFailed, match="not in a mode that routes"):
        ros.track(0.65, 0.1)


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

        def get_result_async(self):
            # The cancelled goal's end, which a cancel now reads (S-03).
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
        lambda topic, speed, domain, side, *_rest: commanded.append(side) or True,
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
        def service_is_ready(self):
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
    assert ros.return_to_sim()
    (request,) = sent
    assert request.mode == TwinMode.MODE_SIM
    assert "nothing crosses to the physical side" in capsys.readouterr().out
    # The sequencer `__main__` runs (`program.cycle`) asks for SIM after the run.
    cycle_source = (Path(__file__).resolve().parents[1] / "cite_bringup/program/cycle.py")
    text = cycle_source.read_text()
    assert text.index("status = run(") < text.rindex("cell.return_to_sim()")


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
            confirm_operator(
                mode, ["counterpart"], 0.1, said.append, asked.append, lambda: None
            )
    assert said == [] and asked == []
    confirm_operator(
        TwinMode.MODE_SIM, ["counterpart"], 0.1, said.append, asked.append, lambda: None
    )
    assert any("speed scale 0.1" in line for line in said) and len(asked) == 1

    def no_answer(_prompt: str) -> str:
        raise EOFError

    with pytest.raises(StepFailed, match="no operator answer"):
        confirm_operator(
            TwinMode.MODE_SIM, ["counterpart"], 0.1, said.append, no_answer, lambda: None
        )


class _PairCell:
    """`RosCell` on a pair with a physical side, as far as `main` uses it."""

    mode = None
    left = True
    carriage: str | None = None
    #: What each `away_from_start` measures, in order: None is "at the start".
    away: list[str | None] = []
    calls: list[str] = []
    #: What `console_refusal` answers: None where no operator console serves the pair.
    console: str | None = None
    #: The topic each `console_refusal` was asked about.
    console_asked: list[str] = []

    def __init__(self, *_args, **_kwargs) -> None:
        _PairCell.calls = []

    def console_refusal(self, topic: str) -> str | None:
        _PairCell.console_asked.append(topic)
        return _PairCell.console

    def require_running(self, target) -> None:
        pass

    def twin_mode(self):
        return _PairCell.mode

    def refuse_if_holding(self, sides=("plant",)) -> None:
        _PairCell.calls.append("refuse_if_holding")

    def carriage_refusal(self, target, homing: bool = False) -> str | None:
        return None if homing and _PairCell.carriage == "apart" else _PairCell.carriage

    def away_from_start(self, start, sides=()) -> str | None:
        _PairCell.calls.append(f"measure {start.pose}")
        return _PairCell.away.pop(0)

    def enter_target(self, target, homing: bool = False) -> None:
        _PairCell.calls.append("enter twin homing" if homing else "enter twin")

    def cancel(self) -> None:
        _PairCell.calls.append("cancel")

    def return_to_sim(self) -> bool:
        _PairCell.calls.append("return_to_sim")
        return _PairCell.left


def _main_on_a_pair(
    monkeypatch,
    mode,
    left: bool,
    answers=("",),
    carriage=None,
    initialized=True,
    argv=(),
    away=("arm away", None),
    homed=True,
) -> int:
    import builtins

    import cite_bringup.program.__main__ as program_module
    import cite_bringup.program.cell as cell_module
    import cite_bringup.program.cycle as cycle_module
    import cite_bringup.program.home as home_module
    import rclpy

    _PairCell.mode, _PairCell.left, _PairCell.carriage = mode, left, carriage
    _PairCell.away = list(away)
    answers = list(answers)
    monkeypatch.setattr(cell_module, "RosCell", _PairCell)
    monkeypatch.setattr(rclpy, "init", lambda **_kwargs: None)
    monkeypatch.setattr(rclpy, "try_shutdown", lambda: None)
    monkeypatch.setattr(program_module, "install_interrupt_handlers", lambda: None)
    monkeypatch.setattr(
        cycle_module, "run", lambda *_args, **_kwargs: _PairCell.calls.append("run") or 0
    )

    def initialize(_plan, sides, _say):
        _PairCell.calls.append(f"initialize {','.join(sides)}")
        if not initialized:
            raise StepFailed("counterpart: picker not initialized: the vendor refused")

    monkeypatch.setattr(program_module, "initialize", initialize)

    def run_home(steps, _cell, _say) -> None:
        _PairCell.calls.append("home " + " ".join(step.kind for step in steps))
        if not homed:
            raise StepFailed("move to zero: result code 3: refused")

    monkeypatch.setattr(home_module, "run_home", run_home)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": answers.pop(0))
    return program_main(["--zone", ZONE, "--speed-scale", "0.1", *argv])


def test_a_run_whose_return_to_sim_is_unconfirmed_fails(monkeypatch) -> None:
    """SA-S-05: a failed return to SIM is the run's failure, so no one is asked in next."""
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True) == 0
    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=False) != 0
    assert _PairCell.calls[-1] == "return_to_sim"


def test_a_twin_not_in_sim_is_never_entered_and_no_one_is_asked(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_VALIDATED, left=True, answers=()) == 1
    assert _PairCell.calls == []


# S-08: a carriage that disagrees is refused BEFORE the operator is asked in.


def test_a_carriage_apart_refuses_before_the_operator_is_asked() -> None:
    from cite_bringup.program.operator import confirm_operator
    from cite_interfaces.msg import TwinMode

    said: list[str] = []
    asked: list[str] = []
    with pytest.raises(StepFailed, match="from outside the cell"):
        confirm_operator(
            TwinMode.MODE_SIM,
            ["counterpart"],
            0.1,
            said.append,
            asked.append,
            lambda: "bring the physical carriage to 650 mm (home it) - from outside the cell",
        )
    assert said == [] and asked == []


def test_the_carriages_are_asked_of_the_twin_at_the_plants_own_position(cell) -> None:
    ros, asked = _tracking(cell, 0.65, [(False, "counterpart: stands at 0.0 mm")])
    refusal = ros.carriage_refusal(TWIN)
    assert asked == [0.65]
    assert refusal is not None
    assert "Bring the physical carriage to 650 mm (home it) - from outside the cell" in refusal
    assert "counterpart: stands at 0.0 mm" in refusal
    ros, _ = _tracking(cell, 0.65, [(True, "every commanded side is at the target")])
    assert ros.carriage_refusal(TWIN) is None


def test_an_unheard_physical_carriage_is_waited_for_before_the_operator(cell) -> None:
    """R-01: an unheard carriage is never taken for one in agreement."""
    unheard = TrackArrived.Response.UNHEARD
    ros, asked = _tracking(
        cell,
        0.65,
        [
            _answer(False, "counterpart: no track position heard", unheard, routed=False),
            _answer(False, "counterpart: no track position heard", unheard, routed=False),
            _answer(True, "in SIM every side", routed=False),
        ],
    )
    assert ros.carriage_refusal(TWIN) is None
    assert asked == [0.65]
    ros, _ = _tracking(
        cell,
        0.65,
        [
            _answer(False, "counterpart: no track position heard", unheard, routed=False),
            _answer(False, "counterpart: stands at 0.0 mm", routed=False),
        ],
    )
    assert "home it" in ros.carriage_refusal(TWIN)


def test_a_physical_carriage_never_heard_refuses_at_the_ceiling_and_says_so() -> None:
    """R-01, R-04: never heard in time refuses, and is not said as "home it"."""
    now = {"t": 0.0}

    def pause() -> None:
        now["t"] += 10.0

    never = _answer(
        False, "counterpart: no track position heard", TrackArrived.Response.UNHEARD
    )
    answer = await_heard(lambda: never, pause, deadline=120.0, clock=lambda: now["t"])
    assert answer is never and now["t"] > 120.0
    refusal = carriage_verdict(answer, 0.65, 120.0)
    assert refusal is not None
    assert "did not hear the physical carriage" in refusal
    assert "home it" not in refusal
    assert "No one is asked into the cell" in refusal
    assert carriage_verdict(_answer(True, ""), 0.65, 120.0) is None
    assert "home it" in carriage_verdict(_answer(False, "counterpart: away"), 0.65, 120.0)


def test_a_run_whose_carriages_disagree_never_asks_and_never_enters_validated(
    monkeypatch,
) -> None:
    """After the first cycle there is no homing move, so a carriage apart refuses."""
    from cite_interfaces.msg import TwinMode

    status = _main_on_a_pair(
        monkeypatch,
        TwinMode.MODE_SIM,
        left=True,
        answers=(),
        carriage="apart",
        argv=("--first-cycle", "2"),
    )
    assert status == 1
    assert _PairCell.calls == []


# T-01: `./scripts/program` refuses a physical side without the opt-in, before bring-up.


@pytest.mark.parametrize("value", [None, "", "0", "true", " 1", "1 "])
def test_a_physical_side_without_the_exact_opt_in_is_refused_before_bring_up(
    monkeypatch, capsys, value
) -> None:
    from cite_bringup.program import sides

    if value is None:
        monkeypatch.delenv("CITE_ALLOW_HARDWARE", raising=False)
    else:
        monkeypatch.setenv("CITE_ALLOW_HARDWARE", value)
    assert sides.main(["--zone", ZONE, "--hardware-opt-in"]) == 2
    said = capsys.readouterr().err
    assert "counterpart is physical" in said and "CITE_ALLOW_HARDWARE=1" in said


def test_a_physical_side_with_the_exact_opt_in_passes(monkeypatch, capsys) -> None:
    """R-05: the one value that permits it, checked in-process; nothing is brought up."""
    from cite_bringup.program import sides

    monkeypatch.setenv("CITE_ALLOW_HARDWARE", "1")
    assert sides.main(["--zone", ZONE, "--hardware-opt-in"]) == 0
    assert capsys.readouterr().err == ""


def test_the_script_checks_the_opt_in_before_it_brings_anything_up() -> None:
    script = (Path(__file__).resolve().parents[4] / "scripts" / "program").read_text()
    check = script.index('cite_bringup.program.sides --zone "$ZONE" --hardware-opt-in')
    assert check < script.index("start_in_own_group")


# --------------------------------------------------------------------------- #
# Initialize and home before the first cycle (ADR-0070)
# --------------------------------------------------------------------------- #


def test_home_is_the_programs_own_start(cell) -> None:
    from cite_bringup.program.home import home_steps

    steps = home_steps(cell)
    first_move = next(s for s in cell.program.steps if s.kind == "move")
    first_track = next(s for s in cell.program.steps if s.kind == "track")
    assert [step.kind for step in steps] == ["move", "track"]
    assert (steps[0].pose, steps[0].velocity_scaling) == (
        first_move.pose, first_move.velocity_scaling
    )
    assert steps[0].pose == "zero", "the real program starts with `reset`"
    assert (steps[1].position_m, steps[1].speed_mps) == (
        first_track.position_m, first_track.speed_mps
    )
    assert steps[1].position_m == 0.0


def test_a_failed_home_step_cancels_and_fails(cell) -> None:
    from cite_bringup.program.home import home_steps, run_home

    fake = FakeCell(fail_on="zero")
    with pytest.raises(StepFailed):
        run_home(home_steps(cell), fake, _quiet)
    assert fake.calls[-1] == ("cancel",)
    assert not [call for call in fake.calls if call[0] == "track"]


def test_a_first_cycle_away_from_the_start_homes_measures_again_then_runs(monkeypatch) -> None:
    """Initialize, then not at the start: home under the allowance, measure, re-enter plainly."""
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True) == 0
    assert _PairCell.calls == [
        "refuse_if_holding",
        "initialize counterpart",
        "measure zero",
        "enter twin homing",
        "home move track",
        "measure zero",
        # The program's own cycle never runs under the homing allowance.
        "enter twin",
        "run",
        "return_to_sim",
    ]


def test_a_first_cycle_already_at_the_start_initializes_and_homes_nothing(
    monkeypatch,
) -> None:
    """R-01: the physical arm is initialized every time, even at the start; no homing move."""
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True, away=(None,)) == 0
    assert _PairCell.calls == [
        "refuse_if_holding",
        "initialize counterpart",
        "measure zero",
        "enter twin",
        "run",
        "return_to_sim",
    ]


def test_a_failed_home_stops_without_a_retry_and_returns_to_sim(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(
        monkeypatch, TwinMode.MODE_SIM, left=True, away=("arm away",), homed=False
    ) == 1
    assert _PairCell.calls == [
        "refuse_if_holding",
        "initialize counterpart",
        "measure zero",
        "enter twin homing",
        "home move track",
        "return_to_sim",
    ]


def test_a_home_that_does_not_reach_the_start_stops_without_a_retry(monkeypatch, capsys) -> None:
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(
        monkeypatch,
        TwinMode.MODE_SIM,
        left=True,
        away=("arm away", "counterpart: picker_joint2 stands at 0.1000"),
    ) == 1
    assert _PairCell.calls == [
        "refuse_if_holding",
        "initialize counterpart",
        "measure zero",
        "enter twin homing",
        "home move track",
        "measure zero",
        "return_to_sim",
    ]
    said = capsys.readouterr().out
    assert "still not at the program's start" in said
    assert "counterpart: picker_joint2 stands at 0.1000" in said


def test_before_a_home_a_carriage_apart_does_not_refuse_the_operator(monkeypatch) -> None:
    """The carriage-agreement refusal before the prompt is the homing move's to clear."""
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True, carriage="apart") == 0
    assert "home move track" in _PairCell.calls
    # A carriage never heard still refuses, homing or not.
    assert _main_on_a_pair(
        monkeypatch, TwinMode.MODE_SIM, left=True, answers=(), carriage="unheard"
    ) == 1
    assert _PairCell.calls == []


def test_a_later_cycle_neither_initializes_nor_homes(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(
        monkeypatch, TwinMode.MODE_SIM, left=True, argv=("--first-cycle", "2")
    ) == 0
    assert _PairCell.calls == ["refuse_if_holding", "enter twin", "run", "return_to_sim"]


def test_a_refused_initialization_runs_nothing_and_returns_to_sim(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True, initialized=False) == 1
    assert _PairCell.calls == [
        "refuse_if_holding",
        "initialize counterpart",
        "return_to_sim",
    ]


def test_initialize_calls_each_physical_arm_on_its_own_domain(monkeypatch) -> None:
    import cite_bringup.program.home as home

    plan = load(default_plan_path(ZONE))
    (manager,) = plan.controller_managers
    physical = manager.physical_on("counterpart")
    calls = []

    class Answer:
        success, detail = True, "track and gripper enabled"

    monkeypatch.setattr(
        home,
        "_call_on_domain",
        lambda service, domain, ceiling, stop, interrupted=None, say=None, stop_deadline=None:
        calls.append((service, domain, ceiling, stop, say)) or Answer()
    )
    said: list[str] = []
    environ = {"CITE_DOMAIN_BASE": "40"}
    home.initialize(plan, ["counterpart"], said.append, environ=environ)
    ((service, domain, ceiling, stop, say),) = calls
    # R2-06: what an interrupt comes to is said where the caller says things,
    # so the console's panel shows it.
    assert say == said.append
    # S-01: the stop sent if the call is interrupted is the one the generated
    # parameters name for that side's initializer, never a hand-written name.
    assert stop == (
        home.initializer_parameter(physical, "linear_motor_stop_service"),
        2.0 * home.initializer_parameter(physical, "call_deadline_s"),
    )
    assert stop[0].endswith("/set_linear_motor_stop")
    assert service == physical.initialize_service == "/cite/cell_b/picker/initialize"
    from cite_bringup.plan import domain_base, resolve_domain_id

    assert domain == resolve_domain_id(plan, "counterpart", domain_base(environ))
    assert domain != resolve_domain_id(plan, "plant", domain_base(environ))
    assert ceiling == 2.0 * home.initializer_deadline_s(physical)

    Answer.success, Answer.detail = False, "the vendor refused set_linear_motor_enable(1)"
    with pytest.raises(StepFailed, match="refused set_linear_motor_enable"):
        home.initialize(plan, ["counterpart"], said.append, environ=environ)


def test_a_simulated_side_has_nothing_to_initialize(monkeypatch) -> None:
    import cite_bringup.program.home as home

    monkeypatch.setattr(home, "_call_on_domain", lambda *_args: pytest.fail("called"))
    said: list[str] = []
    home.initialize(
        load(default_plan_path(ZONE)), ["plant"], said.append, environ={"CITE_DOMAIN_BASE": "40"}
    )
    assert any("nothing to initialize" in line for line in said)


# --------------------------------------------------------------------------- #
# The start is measured before any homing move, and after it (ADR-0070)
# --------------------------------------------------------------------------- #


def test_the_start_is_the_programs_first_pose_within_the_arms_goal_tolerance(cell) -> None:
    from cite_bringup.program.home import home_steps, start_pose

    start = start_pose(cell, home_steps(cell))
    assert start.pose == "zero"
    assert start.joints == tuple(f"picker_joint{n}" for n in range(1, 6))
    assert start.positions == cell.arm.moveit.poses_rad["zero"]
    assert start.tolerance_rad == cell.arm.arm["arm_goal_tolerance_rad"]
    assert start.track_m == 0.0
    assert start.track_tolerance_m == cell.track.goal_tolerance_m


def test_one_side_read_directly_is_at_the_start_only_within_both_tolerances(cell) -> None:
    from cite_bringup.program.home import home_steps, start_pose

    start = start_pose(cell, home_steps(cell))
    at = dict(zip(start.joints, start.positions))
    assert start.away_on_one_side(at, 0.0) is None
    nudged = {**at, "picker_joint3": start.positions[2] + 2 * start.tolerance_rad}
    assert "picker_joint3 stands at" in start.away_on_one_side(nudged, 0.0)
    assert "the track stands at 300.0 mm" in start.away_on_one_side(at, 0.30)
    assert "the track is not heard" in start.away_on_one_side(at, None)


class _StartCell:
    """A cell for `bring_to_start`: measures what it is told, records the rest."""

    def __init__(self, away, fail_on=None) -> None:
        self.away = list(away)
        self.fake = FakeCell(fail_on=fail_on)
        self.calls = self.fake.calls

    def away_from_start(self, start, sides=()):
        self.calls.append(("measure",))
        return self.away.pop(0)

    def enter_target(self, target, homing: bool = False) -> None:
        self.calls.append(("enter twin", homing))

    def __getattr__(self, name):
        return getattr(self.fake, name)


def test_bring_to_start_initializes_first_and_moves_nothing_when_every_side_is_there(
    cell,
) -> None:
    """R-01: initialized every time, before the start is measured."""
    from cite_bringup.program.home import bring_to_start, home_steps, start_pose

    steps = home_steps(cell)
    ros = _StartCell([None])
    assert not bring_to_start(
        steps, start_pose(cell, steps), ros, lambda: ros.calls.append(("initialize",)), _quiet
    )
    assert ros.calls == [("initialize",), ("measure",), ("enter twin", False)]


def test_bring_to_start_homes_under_the_allowance_then_enters_plainly(cell) -> None:
    from cite_bringup.program.home import bring_to_start, home_steps, start_pose

    steps = home_steps(cell)
    ros = _StartCell(["arm away", None])
    assert bring_to_start(
        steps, start_pose(cell, steps), ros, lambda: ros.calls.append(("initialize",)), _quiet
    )
    assert [call[0] for call in ros.calls] == [
        "initialize", "measure", "enter twin", "move", "track", "measure", "enter twin"
    ]
    assert ros.calls[2] == ("enter twin", True)
    assert ros.calls[-1] == ("enter twin", False)


def test_bring_to_start_via_the_plant_alone_asks_no_mode(cell) -> None:
    from cite_bringup.program.home import bring_to_start, home_steps, start_pose

    steps = home_steps(cell)
    ros = _StartCell(["arm away", None])
    assert bring_to_start(
        steps, start_pose(cell, steps), ros, lambda: None, _quiet, via_twin=False
    )
    assert [call[0] for call in ros.calls] == ["measure", "move", "track", "measure"]


@pytest.mark.parametrize(
    ("away", "fail_on", "initialize_fails", "calls"),
    [
        # The second measurement says a side is still away: stop, no retry.
        (["arm away", "still away"], None, False,
         ["measure", "enter twin", "move", "track", "measure"]),
        # A home step fails: cancelled, never retried, never measured again.
        (["arm away"], "zero", False, ["measure", "enter twin", "move", "cancel"]),
        # The physical arm cannot be initialized: nothing is measured, nothing moves.
        (["arm away"], None, True, []),
    ],
)
def test_bring_to_start_stops_on_any_failure_and_retries_nothing(
    cell, away, fail_on, initialize_fails, calls
) -> None:
    from cite_bringup.program.home import bring_to_start, home_steps, start_pose

    steps = home_steps(cell)
    ros = _StartCell(away, fail_on=fail_on)

    def initialize() -> None:
        if initialize_fails:
            raise StepFailed("counterpart: picker not initialized: the vendor refused")

    with pytest.raises(StepFailed):
        bring_to_start(steps, start_pose(cell, steps), ros, initialize, _quiet)
    assert [call[0] for call in ros.calls] == calls


def test_before_a_home_only_a_carriage_heard_apart_is_let_through() -> None:
    """Homing clears AWAY; an unheard carriage, or one the twin cannot judge, still refuses."""
    away = _answer(False, "counterpart: stands at 300.0 mm")
    assert carriage_verdict(away, 0.0, 120.0) is not None
    assert carriage_verdict(away, 0.0, 120.0, homing=True) is None
    unheard = _answer(False, "no track position heard", TrackArrived.Response.UNHEARD)
    assert "did not hear" in carriage_verdict(unheard, 0.0, 120.0, homing=True)
    other = _answer(False, "not a track", TrackArrived.Response.NOT_A_TRACK)
    assert carriage_verdict(other, 0.0, 120.0, homing=True) is not None


def test_the_twins_measurement_is_said_as_where_a_side_stands() -> None:
    from cite_bringup.program.cell import away_verdict
    from cite_interfaces.srv import JointsAt

    at = JointsAt.Response(at=True, reason=JointsAt.Response.AT, detail="")
    assert away_verdict(at, "the arm", 120.0) is None
    away = JointsAt.Response(
        reason=JointsAt.Response.AWAY, detail="counterpart: picker_joint1 stands at 0.2000"
    )
    assert "picker_joint1 stands at 0.2000" in away_verdict(away, "the arm", 120.0)
    unheard = JointsAt.Response(reason=JointsAt.Response.UNHEARD, detail="counterpart: old")
    assert "not heard fresh within 120 s" in away_verdict(unheard, "the arm", 120.0)
    assert away_verdict(_answer(True, "every side"), "the track", 120.0) is None
    assert "stands at" in away_verdict(_answer(False, "plant: stands at 5.0 mm"), "the track", 1)


def test_scripts_home_homes_only_when_a_side_is_away(monkeypatch) -> None:
    """`./scripts/home` runs the same measured sequence, minus the program."""
    import builtins

    import cite_bringup.program.cell as cell_module
    import cite_bringup.program.home as home_module
    from cite_interfaces.msg import TwinMode
    import rclpy

    monkeypatch.setattr(cell_module, "RosCell", _PairCell)
    monkeypatch.setattr(rclpy, "init", lambda **_kwargs: None)
    monkeypatch.setattr(rclpy, "try_shutdown", lambda: None)
    monkeypatch.setattr(
        "cite_bringup.program.steps.install_interrupt_handlers", lambda: None
    )
    monkeypatch.setattr(
        home_module, "initialize", lambda _plan, sides, _say: _PairCell.calls.append(
            f"initialize {','.join(sides)}"
        )
    )
    monkeypatch.setattr(
        home_module, "run_home", lambda steps, _cell, _say: _PairCell.calls.append("home")
    )
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    _PairCell.mode, _PairCell.left, _PairCell.carriage = TwinMode.MODE_SIM, True, "apart"

    _PairCell.away = [None]
    assert home_module.main(["--zone", ZONE, "--speed-scale", "0.1"]) == 0
    # R-01: initialized every time, even when already at the start.
    assert _PairCell.calls == [
        "initialize counterpart", "measure zero", "enter twin", "return_to_sim"
    ]

    _PairCell.away = ["arm away", None]
    assert home_module.main(["--zone", ZONE, "--speed-scale", "0.1"]) == 0
    assert _PairCell.calls == [
        "initialize counterpart",
        "measure zero",
        "enter twin homing",
        "home",
        "measure zero",
        "enter twin",
        "return_to_sim",
    ]

    _PairCell.away = ["arm away", "still away"]
    assert home_module.main(["--zone", ZONE, "--speed-scale", "0.1"]) == 1
    assert _PairCell.calls[-2:] == ["measure zero", "return_to_sim"]


# --- S-03 (ADR-0071): a stop is done when the goal has ENDED and SIM is back ---


class _Later:
    """A future that is done after ``spins`` spins of the cell."""

    def __init__(self, spins: int, value=None) -> None:
        self.left = spins
        self._value = value

    def done(self) -> bool:
        return self.left <= 0

    def result(self):
        return self._value


def _spinning(monkeypatch, futures: list) -> list[str]:
    """Make each spin advance the first future in ``futures`` that is not done."""
    import cite_bringup.program.cell as cell_module

    order: list[str] = []

    def spin_once(_node, timeout_sec=None) -> None:
        for name, future in futures:
            if not future.done():
                future.left -= 1
                if future.done():
                    order.append(name)
                return

    monkeypatch.setattr(cell_module.rclpy, "spin_once", spin_once)
    return order


def test_a_cancel_reads_the_cancelled_goals_end_before_it_returns(monkeypatch) -> None:
    answer, end = _Later(2), _Later(3)
    order = _spinning(monkeypatch, [("cancel answered", answer), ("goal ended", end)])

    class Handle:
        def cancel_goal_async(self):
            return answer

    ros = object.__new__(RosCell)
    ros.node = None
    ros._track_target = None
    ros._sent = None
    ros._active = Handle()
    ros._result = end
    ros.cancel()
    assert order == ["cancel answered", "goal ended"]
    assert ros._result is None and ros._active is None


def test_a_cancelled_goal_that_never_ends_fails_the_cancel_at_its_ceiling(monkeypatch) -> None:
    import cite_bringup.program.cell as cell_module

    monkeypatch.setattr(cell_module, "CANCEL_CEILING_S", 0.05)
    answer, end = _Later(0), _Later(10**9)
    _spinning(monkeypatch, [("goal ended", end)])

    class Handle:
        def cancel_goal_async(self):
            return answer

    ros = object.__new__(RosCell)
    ros.node = None
    ros._track_target = None
    ros._sent = None
    ros._active = Handle()
    ros._result = end
    with pytest.raises(StepFailed, match="the end of the cancelled goal"):
        ros.cancel()


def _asking_for_sim(monkeypatch, answers: list) -> tuple[RosCell, list]:
    import cite_bringup.program.cell as cell_module
    from cite_interfaces.msg import ResultCode

    monkeypatch.setattr(cell_module.rclpy, "spin_once", lambda *_a, **_k: None)
    monkeypatch.setattr(cell_module, "_ARRIVAL_ASK_S", 0.0)
    sent: list = []

    class Response:
        def __init__(self, mode: int, detail: str) -> None:
            self.accepted = detail == ""
            self.current_mode = mode
            self.result = ResultCode(detail=detail)

    class Client:
        def service_is_ready(self):
            return True

        def call_async(self, request):
            sent.append(request)
            return _Later(0, Response(*answers.pop(0)))

    class Node:
        def create_client(self, _type, _name):
            return Client()

    ros = object.__new__(RosCell)
    ros.node = Node()
    return ros, sent


def test_sim_is_asked_again_while_the_boundary_still_has_goals_in_flight(monkeypatch) -> None:
    """After a cancel the boundary refuses SIM until the goal ends; that clears by itself."""
    from cite_bringup.readiness import GOALS_STILL_RUNNING
    from cite_interfaces.msg import TwinMode

    refused = (TwinMode.MODE_VALIDATED, f"SIM describes a cell in which 1 {GOALS_STILL_RUNNING}")
    ros, sent = _asking_for_sim(
        monkeypatch, [refused, refused, (TwinMode.MODE_SIM, "")]
    )
    assert ros.return_to_sim()
    assert len(sent) == 3


def test_any_other_refusal_of_sim_is_final(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    ros, sent = _asking_for_sim(
        monkeypatch, [(TwinMode.MODE_VALIDATED, "refused for another reason")]
    )
    assert not ros.return_to_sim()
    assert len(sent) == 1


def test_sim_refused_for_goals_that_never_end_fails_at_the_cancel_ceiling(monkeypatch) -> None:
    import cite_bringup.program.cell as cell_module
    from cite_bringup.readiness import GOALS_STILL_RUNNING
    from cite_interfaces.msg import TwinMode

    monkeypatch.setattr(cell_module, "CANCEL_CEILING_S", 0.05)
    refused = (TwinMode.MODE_VALIDATED, f"1 {GOALS_STILL_RUNNING}")
    ros, sent = _asking_for_sim(monkeypatch, [refused] * 100000)
    assert not ros.return_to_sim()
    assert len(sent) >= 1


def test_a_stop_reaches_a_belt_whose_subscriber_is_awaited(monkeypatch) -> None:
    """S-08 (ADR-0071): the console's stop is asked while a side's belt is matched."""
    from cite_bringup.program.steps import Interrupted

    started = time.monotonic()
    with pytest.raises(Interrupted):
        belt_command._set_on_one_side(
            "/cite/cell_b/nobody_subscribes", 0.0, 90 + os.getpid() % 9, "plant",
            interrupted=lambda: True,
        )
    assert time.monotonic() - started < belt_command.MATCH_CEILING_S


# --- N-01 (ADR-0071): one operator surface per pair ----------------------------


def test_a_terminal_run_is_refused_where_a_console_serves_the_pair(monkeypatch, capsys) -> None:
    """Nothing is read, asked, entered or left: the console may hold the cell."""
    from cite_interfaces.msg import TwinMode

    plan = load(default_plan_path(ZONE))
    _PairCell.console_asked = []
    monkeypatch.setattr(_PairCell, "console", "an operator console serves this pair")
    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True, answers=()) == 1
    assert _PairCell.calls == []
    assert _PairCell.console_asked == [plan.console.state]
    assert "REFUSED: an operator console serves this pair" in capsys.readouterr().out


def test_without_a_console_the_terminal_run_goes_on(monkeypatch) -> None:
    from cite_interfaces.msg import TwinMode

    _PairCell.console_asked = []
    assert _main_on_a_pair(monkeypatch, TwinMode.MODE_SIM, left=True) == 0
    assert len(_PairCell.console_asked) == 1


def test_scripts_home_is_refused_where_a_console_serves_the_pair(monkeypatch, capsys) -> None:
    """N-01 (b): `./scripts/home` runs `program.home`, which asks the same question."""
    import builtins

    import cite_bringup.program.cell as cell_module
    import cite_bringup.program.home as home_module
    from cite_interfaces.msg import TwinMode
    import rclpy

    monkeypatch.setattr(cell_module, "RosCell", _PairCell)
    monkeypatch.setattr(rclpy, "init", lambda **_kwargs: None)
    monkeypatch.setattr(rclpy, "try_shutdown", lambda: None)
    monkeypatch.setattr("cite_bringup.program.steps.install_interrupt_handlers", lambda: None)
    monkeypatch.setattr(
        home_module, "initialize", lambda *_args: pytest.fail("initialized under a console")
    )
    monkeypatch.setattr(builtins, "input", lambda _prompt="": pytest.fail("asked"))
    monkeypatch.setattr(_PairCell, "console", "an operator console serves this pair")
    _PairCell.mode, _PairCell.left, _PairCell.carriage = TwinMode.MODE_SIM, True, None
    assert home_module.main(["--zone", ZONE, "--speed-scale", "0.1"]) == 1
    # Not even SIM is asked for: the console may be running a cycle in VALIDATED.
    assert _PairCell.calls == []
    assert "REFUSED:" in capsys.readouterr().out


def test_the_scripts_home_command_reaches_the_same_refusal() -> None:
    """`./scripts/home` execs `program.home`, which passes the console's topic."""
    script = (Path(__file__).resolve().parents[4] / "scripts" / "home").read_text()
    assert "exec python3 -u -m cite_bringup.program.home" in script


def test_a_console_refusal_that_cannot_be_read_refuses_too(capsys) -> None:
    """An unanswerable question is a refusal, never a pass (N-01)."""
    from cite_bringup.program import cycle

    class Unheard:
        def console_refusal(self, _topic: str):
            raise StepFailed("no TwinMode on /cite/twin/mode after 60 s")

        def __getattr__(self, name: str):
            raise AssertionError(f"{name} was called on a refused run")

    ended = cycle.run_program(
        Unheard(), [], target=TWIN, physical=["counterpart"], scale=0.1, cycles=1,
        say=print, await_operator=lambda _p: "", console="/cite/cell_b/console/state",
    )
    assert ended.status == 1 and ended.sim_confirmed is None
    assert "REFUSED: could not tell whether an operator console" in capsys.readouterr().out


# --- R2-02 (ADR-0071): no wait of a console's cell outlasts its shutdown -------


def test_a_cancel_is_cut_at_the_consoles_shutdown_deadline(monkeypatch) -> None:
    """The goal's end is not awaited for `CANCEL_CEILING_S` once the shutdown's cut passed."""
    answer, end = _Later(0), _Later(10**9)
    _spinning(monkeypatch, [("goal ended", end)])

    class Handle:
        def cancel_goal_async(self):
            return answer

    ros = object.__new__(RosCell)
    ros.node = None
    ros._track_target = None
    ros._sent = None
    ros._active = Handle()
    ros._result = end
    ros._stop_deadline = lambda: time.monotonic() - 1.0
    started = time.monotonic()
    with pytest.raises(StepFailed, match="cut short by the console's shutdown deadline"):
        ros.cancel()
    assert time.monotonic() - started < 1.0


def test_a_return_to_sim_is_cut_at_the_consoles_shutdown_deadline(monkeypatch, capsys) -> None:
    """A SetMode server never found is not waited for `SERVER_WAIT_S` past the cut."""
    import cite_bringup.program.cell as cell_module

    monkeypatch.setattr(cell_module.rclpy, "spin_once", lambda *_a, **_k: None)

    class Client:
        def service_is_ready(self):
            return False

    class Node:
        def create_client(self, _type, _name):
            return Client()

    ros = object.__new__(RosCell)
    ros.node = Node()
    ros._stop_deadline = lambda: time.monotonic() - 1.0
    started = time.monotonic()
    assert not ros.return_to_sim()
    assert time.monotonic() - started < 1.0
    assert "is not served, cut short" in capsys.readouterr().out


def test_without_a_shutdown_a_cells_waits_keep_their_own_ceilings() -> None:
    ros = object.__new__(RosCell)
    assert ros._clamped(123.0) == 123.0
    ros._stop_deadline = lambda: None
    assert ros._clamped(123.0) == 123.0
    ros._stop_deadline = lambda: 100.0
    assert ros._clamped(123.0) == 100.0


# S-02: `--via plant` only on the plant's own domain, and never beside a console.


def _plant_main(
    monkeypatch, environ: dict[str, str], simulated: str | None = None
) -> tuple[int, list]:
    """Run `--via plant` with ``environ``'s domain, recording what reached ROS.

    ``simulated`` is what the graph says to `simulated_side_refusal`: None for
    a simulated side heard, or the refusal.
    """
    import cite_bringup.program.__main__ as program_module
    import cite_bringup.program.cell as cell_module
    import rclpy

    reached: list = []
    for name in ("ROS_DOMAIN_ID", "CITE_DOMAIN_BASE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(rclpy, "init", lambda **_kwargs: reached.append("init"))
    monkeypatch.setattr(rclpy, "try_shutdown", lambda: None)
    monkeypatch.setattr(program_module, "install_interrupt_handlers", lambda: None)

    class Cell:
        def __init__(self, *args, **_kwargs) -> None:
            self.args = args

        def simulated_side_refusal(self) -> str | None:
            reached.append("asked the graph")
            return simulated

    monkeypatch.setattr(cell_module, "RosCell", Cell)

    class Ended:
        status = 0

    def run_program(cell, steps, **kwargs):
        reached.append(("run_program", kwargs["console"], kwargs["via_twin"]))
        return Ended()

    monkeypatch.setattr(program_module, "run_program", run_program)
    return program_main(["--zone", ZONE, "--via", "plant"]), reached


def test_via_the_plant_is_refused_on_the_counterparts_domain(monkeypatch, capsys) -> None:
    """S-02: on the counterpart's domain `--via plant` would drive the physical arm."""
    plan = load(default_plan_path(ZONE))
    counterpart = 40 + plan.side_named("counterpart").domain_offset
    assert counterpart != 40
    status, reached = _plant_main(
        monkeypatch, {"CITE_DOMAIN_BASE": "40", "ROS_DOMAIN_ID": str(counterpart)}
    )
    assert status == 2
    assert reached == [], "a ROS context was created before the refusal"
    assert "--via plant refused" in capsys.readouterr().err


def test_via_the_plant_is_refused_with_no_domain_to_check(monkeypatch, capsys) -> None:
    status, reached = _plant_main(monkeypatch, {"ROS_DOMAIN_ID": "40"})
    assert status == 2 and reached == []
    assert "CITE_DOMAIN_BASE" in capsys.readouterr().err


def test_via_the_plant_on_the_plants_domain_runs_and_asks_for_a_console(monkeypatch) -> None:
    """S-02 lets the plant's own domain through; R-05: the console is asked for too."""
    plan = load(default_plan_path(ZONE))
    status, reached = _plant_main(
        monkeypatch, {"CITE_DOMAIN_BASE": "40", "ROS_DOMAIN_ID": "40"}
    )
    assert status == 0
    assert reached == ["init", "asked the graph", ("run_program", plan.console.state, False)]


def test_via_the_plant_is_refused_where_the_graph_shows_no_simulated_side(
    monkeypatch, capsys
) -> None:
    """S-02r: the plant's domain in the environment, and no simulated clock on the graph.

    A shell that exported the counterpart's ROS_DOMAIN_ID derives the base from
    it, so the environment check passes; the graph's answer refuses before any
    goal or mode.
    """
    status, reached = _plant_main(
        monkeypatch,
        {"CITE_DOMAIN_BASE": "41", "ROS_DOMAIN_ID": "41"},
        simulated="no /clock on this domain after 60 s",
    )
    assert status == 2
    assert reached == ["init", "asked the graph"]
    assert "--via plant refused: no /clock" in capsys.readouterr().err
