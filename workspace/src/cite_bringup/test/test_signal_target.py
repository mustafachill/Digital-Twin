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

"""The operator chooses where the signal goes (ADR-0072), without a graph.

The one target table (`program.targets`), which targets a deployment offers,
the sequencer's per-target gates (`program.cycle`), the console's per-target
refusals and per-side start (`program.console_machine`), the pair's sides by
the hardware opt-in (`program.sides.pair_sides`) and the cell's two pure
judgements: the twin's mode before every step (R-05) and a carriage the program
cannot read (R-08). Each test names the safety requirement it holds.
"""

from __future__ import annotations

from cite_bringup.plan import default_plan_path, load
from cite_bringup.program import cycle, targets
from cite_bringup.program.cell import mode_refusal, RosCell, single_side_start
from cite_bringup.program.from_plan import target as cell_of
from cite_bringup.program.home import StartPose
from cite_bringup.program.sides import (
    pair_sides,
    physical_sides,
    required_speed_scale,
    REAL_ARM_NOT_STARTED,
)
from cite_bringup.program.steps import move, run, StepFailed
from cite_interfaces.msg import ConsoleState, TwinMode
from cite_interfaces.srv import TrackArrived
import pytest

from test_console_machine import _at_start, Rig

ZONE = "cell_b"
SIM, REAL, TWIN = targets.SIM, targets.REAL, targets.TWIN

START = StartPose(
    pose="zero",
    joints=("joint1",),
    positions=(0.0,),
    tolerance_rad=0.01,
    track_m=None,
    track_tolerance_m=None,
)


# --- the one table -----------------------------------------------------------


def test_each_target_is_one_mode_and_its_sides() -> None:
    assert targets.MODES == {
        SIM: TwinMode.MODE_SIM,
        REAL: TwinMode.MODE_REAL,
        TWIN: TwinMode.MODE_VALIDATED,
    }
    assert targets.SIDES == {
        SIM: ("plant",),
        REAL: ("counterpart",),
        TWIN: ("plant", "counterpart"),
    }
    assert (SIM, REAL, TWIN) == (
        ConsoleState.TARGET_SIM,
        ConsoleState.TARGET_REAL,
        ConsoleState.TARGET_TWIN,
    )
    assert [targets.by_name(name) for name in ("sim", "real", "twin")] == [SIM, REAL, TWIN]
    with pytest.raises(ValueError):
        targets.by_name("both")


def test_only_twin_asks_the_homing_allowance() -> None:
    """R-11: `SetMode.homing` stays VALIDATED's alone."""
    assert [targets.homing_allowance(t) for t in targets.ALL] == [False, False, True]


@pytest.mark.parametrize(
    ("running", "commandable", "offered"),
    [
        # A pair started with the plant alone offers the simulation, and only it.
        (("plant",), ("plant",), [SIM]),
        # Both sides running and ready: all three.
        (("plant", "counterpart"), ("plant", "counterpart"), [SIM, REAL, TWIN]),
        # R-19: a physical side running but not measured ready offers no target
        # that commands it.
        (("plant", "counterpart"), ("plant",), [SIM]),
        # A side the twin calls commandable but this deployment did not start.
        (("plant",), ("plant", "counterpart"), [SIM]),
    ],
)
def test_what_a_deployment_offers(running, commandable, offered) -> None:
    assert targets.available(running, commandable) == offered


@pytest.mark.parametrize(
    ("target", "offered", "words"),
    [
        (0, [SIM, REAL, TWIN], "no target was sent"),
        (9, [SIM, REAL, TWIN], "is not a target"),
        (REAL, [SIM], "is not offered now"),
        (TWIN, [SIM], "is not offered now"),
    ],
)
def test_a_target_unset_unknown_or_not_offered_is_refused(target, offered, words) -> None:
    """R-18."""
    assert words in targets.refusal(target, offered)


def test_an_offered_target_is_not_refused() -> None:
    for target in targets.ALL:
        assert targets.refusal(target, list(targets.ALL)) is None


def test_the_running_physical_sides_are_the_plans_that_run() -> None:
    """R-16: in one place - a counterpart that does not run is no physical side of it."""
    plan = load(default_plan_path(ZONE))
    assert targets.running_physical(plan, ("plant", "counterpart")) == physical_sides(plan)
    assert targets.running_physical(plan, ("plant",)) == []


# --- the pair's sides, by the hardware opt-in --------------------------------


def test_without_the_opt_in_a_pair_starts_the_plant_alone() -> None:
    """ADR-0072 decision 4: the real arm is never started by default."""
    plan = load(default_plan_path(ZONE))
    assert physical_sides(plan), "the shipped counterpart is the physical arm"
    assert pair_sides(plan, {}) == "plant"
    assert pair_sides(plan, {"CITE_ALLOW_HARDWARE": "0"}) == "plant"
    assert pair_sides(plan, {"CITE_ALLOW_HARDWARE": "1"}) == "all"
    assert "CITE_ALLOW_HARDWARE is not 1; simulation target only" in REAL_ARM_NOT_STARTED


def test_the_sides_words_are_the_pair_supervisors() -> None:
    from cite_bringup import pair
    from cite_bringup.program import sides

    assert (sides.PAIR_SIDES_PLANT, sides.PAIR_SIDES_ALL) == (pair.SIDES_PLANT, pair.SIDES_ALL)


def test_the_scale_and_its_floor_are_the_targets() -> None:
    """R-25: the simulation alone needs no stated scale and has no floor."""
    plan = load(default_plan_path(ZONE))
    assert required_speed_scale(plan, "", "twin", targets.SIDES[SIM]) == 1.0
    assert required_speed_scale(plan, "0.01", "twin", targets.SIDES[SIM]) == 0.01
    for target in (REAL, TWIN):
        with pytest.raises(ValueError, match="must be given explicitly"):
            required_speed_scale(plan, "", "twin", targets.SIDES[target])


# --- the sequencer -------------------------------------------------------------


class Cell:
    """A cell recording every call, in SIM, at the start."""

    def __init__(self, log: list, not_running: str | None = None) -> None:
        self.log = log
        self.not_running = not_running

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.log.append((name, *args, *kwargs.values()))
            if name == "require_running" and self.not_running is not None:
                raise StepFailed(self.not_running)
            if name == "twin_mode":
                return TwinMode.MODE_SIM
            if name == "return_to_sim":
                return True
            return None

        return call


def _run(target: int, physical, log, read=None, **kwargs) -> cycle.Ended:
    return cycle.run_program(
        Cell(log, **kwargs),
        [move("pick")],
        target=target,
        physical=physical,
        scale=0.5,
        cycles=1,
        say=lambda text: log.append(("said", text)),
        await_operator=read or (lambda prompt: log.append(("asked", prompt)) or ""),
    )


def _home(target: int, physical, log, **kwargs) -> cycle.Ended:
    return cycle.home(
        Cell(log, **kwargs),
        [move("zero")],
        START,
        target=target,
        physical=physical,
        scale=0.5,
        say=lambda text: log.append(("said", text)),
        await_operator=lambda prompt: log.append(("asked", prompt)) or "",
        initialize_physical=lambda: log.append(("initialize",)),
        prompt="HOME?",
    )


def _names(log) -> list[str]:
    return [entry[0] for entry in log]


def test_a_simulation_run_asks_no_one_and_never_returns_to_sim() -> None:
    """R-13: nothing is asked and nothing says the cell may be entered; SIM is asked for."""
    log: list = []
    ended = _run(SIM, [], log)
    assert ended.status == 0 and ended.sim_confirmed is None
    names = _names(log)
    assert "asked" not in names and "twin_mode" not in names
    assert "return_to_sim" not in names
    assert ("enter_target", SIM) in log
    assert ("refuse_if_holding", ("plant",)) in log
    said = " ".join(text for name, text in [e for e in log if e[0] == "said"])
    assert "enter" not in said.lower() and "clear" not in said.lower()


def test_a_simulation_home_initializes_nothing() -> None:
    """R-03: no initialize, no vendor service, no operator."""
    log: list = []
    ended = _home(SIM, [], log)
    assert ended.status == 0
    names = _names(log)
    assert "asked" not in names
    assert "return_to_sim" not in names
    assert ("enter_target", SIM) in log


def test_a_real_run_carries_every_gate_and_returns_to_sim() -> None:
    """R-12, R-20, R-09: asked in SIM with a prompt naming the target, custody of the real arm."""
    log: list = []
    ended = _run(REAL, ["counterpart"], log)
    assert ended.status == 0 and ended.sim_confirmed is True
    names = _names(log)
    assert names.index("twin_mode") < names.index("asked") < names.index("enter_target")
    (asked,) = [entry[1] for entry in log if entry[0] == "asked"]
    assert "Target: the real arm" in asked and "counterpart" in asked
    assert ("carriage_refusal", REAL, False) in log
    assert ("refuse_if_holding", ("counterpart",)) in log
    assert ("enter_target", REAL) in log
    assert names[-1] == "return_to_sim"


def test_a_twin_run_reads_custody_on_both_sides() -> None:
    """R-09, R-23."""
    log: list = []
    _run(TWIN, ["counterpart"], log)
    assert ("refuse_if_holding", ("plant", "counterpart")) in log


def test_a_target_whose_side_does_not_run_is_refused_before_anyone_is_asked() -> None:
    """R-17: never a silent fall back to another target."""
    log: list = []
    ended = _run(REAL, ["counterpart"], log, not_running="counterpart does not run")
    assert ended.status == 1
    names = _names(log)
    assert "asked" not in names and "enter_target" not in names and "move" not in names
    assert ("said", "FAILED before the first step: counterpart does not run") in log


def test_a_home_naming_a_side_that_does_not_run_asks_no_one_and_asks_for_sim() -> None:
    log: list = []
    ended = _home(TWIN, ["counterpart"], log, not_running="counterpart does not run")
    assert ended.status == 1
    names = _names(log)
    assert "asked" not in names and "initialize" not in names
    assert names[-1] == "return_to_sim"


def test_a_real_home_initializes_after_the_go_ahead_and_asks_no_allowance() -> None:
    log: list = []
    _home(REAL, ["counterpart"], log)
    names = _names(log)
    assert names.index("asked") < names.index("initialize")
    assert ("away_from_start", START, ("counterpart",)) in log


# --- R-05: a mode the run did not ask for stops it before the next step -------


def test_a_mode_the_run_did_not_ask_for_refuses_the_next_step() -> None:
    assert mode_refusal(None, TwinMode.MODE_REAL) is None
    assert mode_refusal(TwinMode.MODE_SIM, TwinMode.MODE_SIM) is None
    assert "REAL, not the SIM" in mode_refusal(TwinMode.MODE_SIM, TwinMode.MODE_REAL)
    assert "no twin mode" in mode_refusal(TwinMode.MODE_SIM, None)


def test_real_heard_between_two_steps_of_a_sim_run_stops_it_by_the_stop_path() -> None:
    """R-05: the next step is never sent; the goal in flight is cancelled."""
    sent: list = []

    class Cell:
        heard = TwinMode.MODE_SIM

        def check_mode(self) -> None:
            refusal = mode_refusal(TwinMode.MODE_SIM, self.heard)
            if refusal is not None:
                raise StepFailed(refusal)

        def move(self, pose, _velocity) -> None:
            sent.append(pose)
            # Another client puts the twin in REAL while this step runs.
            Cell.heard = TwinMode.MODE_REAL

        def cancel(self) -> None:
            sent.append("cancel")

    said: list = []
    status = run([move("pick"), move("place")], Cell(), 1, said.append)
    assert status == 1
    assert sent == ["pick", "cancel"]
    assert any("not the SIM this run asked for" in line for line in said)


# --- R-08: the real arm's carriage, never the plant's -------------------------


def test_the_start_of_a_single_side_move_is_where_the_twin_confirms_it() -> None:
    asked: list = []

    def confirmed(at_m):
        asked.append(at_m)
        return True, ""

    assert single_side_start(0.0, confirmed, "track") == 0.0 and asked == [0.0]
    with pytest.raises(StepFailed, match="not known to this program"):
        single_side_start(None, confirmed, "track")
    with pytest.raises(StepFailed, match="not where this program last measured"):
        single_side_start(0.2, lambda at_m: (False, "counterpart: stands at 0.0 mm"), "track")


class _Publisher:
    topic_name = "/cite/twin/cell_b/picker/track"

    def __init__(self) -> None:
        self.sent: list = []

    def publish(self, message) -> None:
        self.sent.append(message)


def test_a_real_track_step_starts_at_the_real_carriage_and_waits_on_it_alone() -> None:
    """R-08: plant at 0.5, counterpart at 0.0, REAL track to 1.0 - starts at 0.0."""
    track = cell_of(load(default_plan_path(ZONE))).track
    arrived = TrackArrived.Response.ARRIVED
    away = TrackArrived.Response.AWAY
    answers = [
        TrackArrived.Response(arrived=False, reason=away, routed=True, detail="away"),
        TrackArrived.Response(arrived=True, reason=arrived, routed=True, detail=""),
        TrackArrived.Response(arrived=True, reason=arrived, routed=True, detail=""),
    ]
    ros = object.__new__(RosCell)
    ros.node = None
    ros._via = "twin"
    ros._speed = 1.0
    ros._track = track
    ros._track_command = _Publisher()
    ros._track_target = None
    ros._track_position = 0.5  # the plant's carriage, which must not be used
    ros._track_arrived = object()
    ros._target = REAL
    ros._far_track_m = 0.0
    ros._until_true = lambda predicate, what: None
    ros._pause_between_asks = lambda: None
    asked: list = []

    def ask_arrival(position_m, what, sides=()):
        asked.append((position_m, tuple(sides)))
        return lambda: answers.pop(0)

    ros._ask_arrival = ask_arrival
    ros.track(1.0, 0.1)
    (command,) = ros._track_command.sent
    assert [list(point.positions) for point in command.points] == [[0.0], [1.0]]
    assert asked == [(1.0, ("counterpart",)), (0.0, ("counterpart",)), (1.0, ("counterpart",))]
    assert ros._far_track_m == 1.0


# --- the console --------------------------------------------------------------


def test_the_console_refuses_a_goal_with_no_target_or_one_not_offered() -> None:
    """R-18, at the console: refused when the goal arrives and when it starts."""
    rig = Rig(physical=["counterpart"], available=[SIM]).started()
    assert "no target was sent" in rig.machine.motion_refusal(1.0, None, 0)
    assert "not offered now" in rig.machine.motion_refusal(0.5, None, REAL)
    outcome = rig.machine.home(0.5, TWIN)
    assert not outcome.success and "not offered now" in outcome.detail
    assert rig.calls == []


def test_the_snapshot_says_what_is_offered_and_each_sides_start() -> None:
    rig = Rig(available=[SIM])
    snapshot = rig.machine.snapshot()
    assert snapshot.available_targets == (SIM,)
    assert not snapshot.plant_at_start and not snapshot.counterpart_at_start
    rig.available = [SIM, REAL, TWIN]
    assert rig.machine.snapshot().available_targets == (SIM, REAL, TWIN)


def test_a_simulation_home_on_a_physical_pair_asks_no_one_and_initializes_nothing() -> None:
    """R-03, R-13: a plant-only target never touches the physical side."""
    rig = Rig(physical=["counterpart"]).started()
    asked = rig.asked()
    rig.away = [None]
    outcome = rig.machine.home(0.5, SIM)
    assert outcome.success, outcome.detail
    assert rig.asked() == asked
    assert ("initialize",) not in rig.calls
    assert ("enter", SIM, False) in rig.calls
    assert ("return_to_sim",) not in rig.calls
    snapshot = rig.machine.snapshot()
    assert snapshot.plant_at_start and not snapshot.counterpart_at_start


def test_start_program_needs_the_start_on_every_side_of_its_target() -> None:
    """R-22: per side; a simulation start is not a twin start."""
    rig = Rig(physical=["counterpart"]).started()
    rig.away = [None]
    assert rig.machine.home(0.5, SIM).success
    assert rig.machine.motion_refusal(0.5, 1, SIM) is None
    refusal = rig.machine.motion_refusal(0.5, 1, TWIN)
    assert "counterpart is not known to be at the program's start" in refusal


def test_a_simulation_run_places_parts_on_the_plant_alone_and_measures_it_alone() -> None:
    rig = Rig().started()
    rig.away = [None]
    assert rig.machine.home(1.0, SIM).success
    rig.calls.clear()
    rig.measured_sides.clear()
    assert rig.machine.run_program(1.0, 1, SIM).success
    assert rig.measured_sides == [("plant",)]
    assert rig.placed_on == [("plant",)]
    assert rig.machine.snapshot().plant_at_start


def test_a_real_run_places_no_part_and_asks_the_operator_in_sim() -> None:
    rig = Rig(physical=["counterpart"]).started()
    rig.away = [None]
    join = rig.in_thread(lambda: rig.machine.home(0.5, REAL))
    rig.answer()
    assert join().success
    assert "Target: the real arm" in [s.prompt for s in rig.snapshots if s.prompt][-1]
    rig.calls.clear()
    join = rig.in_thread(lambda: rig.machine.run_program(0.5, 1, REAL))
    rig.answer()
    assert join().success
    assert rig.placed_on == []
    assert ("return_to_sim",) in rig.calls


def test_the_scale_is_checked_for_the_goals_target() -> None:
    """R-25."""
    rig = Rig().started()
    rig.machine.motion_refusal(0.5, None, REAL)
    assert rig.scales_checked[-1] == (0.5, REAL)


def test_a_stop_forgets_every_sides_start() -> None:
    """R-22: a Stop or a fault invalidates the start, on every side."""
    rig = Rig().homed()
    assert _at_start(rig.machine.snapshot())
    rig.hold_on = ("move", "pick")
    join = rig.in_thread(lambda: rig.machine.run_program(1.0, 1, SIM))
    assert rig.holding_step.wait(10.0)
    assert rig.machine.stop().success
    join()
    snapshot = rig.machine.snapshot()
    assert not snapshot.plant_at_start and not snapshot.counterpart_at_start
