"""Guard: a line that has published that it stopped ends the run, with the report.

Two defects, one incident, and both were paid for in CI.

**The time.** `continuous_line`'s per-milestone loop in `_run_one_piece` spun on
`rclpy.spin_once` and consulted neither `self._halt` nor `STOPPED_STATES`. The
coordinator escalated, nothing in the leg loop looked, and the assertion arrived
**417.8 s** and **420.6 s** later in two CI runs, against a `LEG_CEILING_S` of
420.0 s. What ended those runs was the budget, not the message.

**The evidence, which cost more.** `_context` — the milestone ladder, each piece's
stop point, the last `LineState` with per-station detail, the halt, the sample
extremes — took the ladder and the journeys as arguments and was therefore
callable from exactly one place: the final verdict. Every earlier raise lost the
whole report. The observed flow: the leg burned its ceiling, the piece loop called
`_remove_workpiece()`, and THAT wait's pre-loop halt check raised — so the message
named a removal wait, which had nothing to do with the fault, and carried no
diagnostic at all. The three earlier CI failures at that same station were
diagnosed from precisely the data that was not printed.

## Why this is a host guard and not a scenario assertion

Reproducing it in the cell means arranging for the coordinator to escalate mid-leg,
which is the fault nobody has reproduced on demand. The loop's behaviour under a
halt is arithmetic over a spin count and a clock, and arithmetic is checkable in
milliseconds on every `./scripts/test`, including `--host-only`.

## How it drives the code without ROS, and the trap in doing it the obvious way

**A real `TestContinuousLine` instance is useless here.** `setUpClass` calls
`rclpy.init()` and builds a `Node`, and `_now()` would read
`get_clock().now().nanoseconds` off a stub that `int(... * 1e9)` cannot consume.

**And under the stub loader the STALLED branch is unreachable.** In
`test_scenario_modules_load._ros_stubs`, `cite_interfaces.msg.LineState` is a
`_Stub` whose `__getattr__` MINTS A NEW OBJECT ON EVERY ACCESS, so
`LineState.STATE_STALLED is not LineState.STATE_STALLED`. `STOPPED_STATES` holds
three objects captured at module load, and `self._halt.state ==
LineState.STATE_STALLED` is therefore always False on the host — a guard written
against the stubs would silently exercise one branch and report both.

So this follows `test_timing_records.py`'s precedent: pull the unbound functions
off the class and call them with a fabricated `self` built from
`types.SimpleNamespace`. Every collaborator is an attribute of `self` or a module
global, so all of them are fabricable, and `rclpy.spin_once` is replaced by one
that advances a fake clock and sets `_halt` on a chosen spin — which is how a
`LineState` callback arrives in the real loop. `_fail_if_the_line_has_stopped` and
`_context` are bound onto the stand-in with `__get__`, so what runs is the shipped
code and not a restatement of it. The `line_state` fixture patches `LineState`,
`STOPPED_STATES` and `STOPPED_STATE_NAMES` TOGETHER to plain ints, so both
branches are reachable and the host behaves as the container does.

## What it cannot see

It drives the loop, not the cell: no station escalates here, and nothing measures
whether the coordinator's `LineState` arrives at all. That the scenario subscribes
to it, and that `_on_line_state` latches the first stopped state, is held
elsewhere. The last test is the tripwire for a rewrite that keeps the others
passing by accident.
"""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

#: The sibling guard that owns the stub finder and the by-path loader. Imported
#: rather than copied, for the reason `test_timing_records.py` gives; the
#: `sys.path` insert makes it independent of pytest's collection order.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_scenario_modules_load as loader

SCENARIO = loader.SCENARIO_DIR / "continuous_line.py"

#: Plain ints standing in for the three `LineState` constants. Any three distinct
#: values do; what matters is that they compare equal to themselves, which the
#: stub's freshly minted attributes do not.
BLOCKED, FAULTED, STALLED = 1, 2, 3

#: How far the fake node clock advances per spin, in seconds. The scenario's own
#: `SAMPLE_PERIOD_S`, so a spin count here means what it means there.
SPIN_STEP_S = 0.5


@pytest.fixture(scope="module")
def module() -> types.ModuleType:
    """`continuous_line` loaded the way `launch_test` loads it, with ROS stubbed."""
    dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        with loader._ros_stubs():
            return loader._load_like_launch_test(SCENARIO)
    finally:
        sys.dont_write_bytecode = dont_write_bytecode


def test_the_stopped_state_set_still_has_three_members(module) -> None:
    """Read BEFORE anything is patched, so the patch cannot hide a shrinking tuple.

    Every test below replaces `STOPPED_STATES` with three plain ints. If the
    scenario ever stops treating one of BLOCKED, FAULTED and STALLED as an end,
    the patched tests would carry on passing about a set the scenario no longer
    has. This is the one check that looks at the real thing.
    """
    assert len(module.STOPPED_STATES) == 3, (
        f"the scenario treats {len(module.STOPPED_STATES)} state(s) as a stopped line; "
        "BLOCKED, FAULTED and STALLED are all ends (ADR-0038, ADR-0039), and the "
        "fixtures below fabricate three"
    )
    assert len(module.STOPPED_STATE_NAMES) == 3, (
        "STOPPED_STATE_NAMES and STOPPED_STATES have drifted apart; a halt in the "
        "unnamed state reports `state=<int>` instead of saying which end it was"
    )


@pytest.fixture
def line_state(module):
    """Patch the three `LineState` names together, and put them back afterwards.

    Together, because they are one fact stated three times: the constants, the
    tuple of stopped values, and the names the report prints. Patching one alone
    produces a module that is internally inconsistent in a way the container never
    is — a halt whose state is in `STOPPED_STATES` but matches no constant, or one
    that matches a constant and has no name.
    """
    saved = (module.LineState, module.STOPPED_STATES, module.STOPPED_STATE_NAMES)
    module.LineState = types.SimpleNamespace(
        STATE_BLOCKED=BLOCKED, STATE_FAULTED=FAULTED, STATE_STALLED=STALLED
    )
    module.STOPPED_STATES = (BLOCKED, FAULTED, STALLED)
    module.STOPPED_STATE_NAMES = {BLOCKED: "BLOCKED", FAULTED: "FAULTED", STALLED: "STALLED"}
    try:
        yield module
    finally:
        module.LineState, module.STOPPED_STATES, module.STOPPED_STATE_NAMES = saved


class _Clock:
    """A node clock, a clock and a `Time` in one object.

    `_run_one_piece` reads `self.node.get_clock().now().nanoseconds` and nothing
    else off the node, so one object answering all three calls is the whole of
    what the loop needs. It advances only when a spin advances it, which is what
    makes "how much clock did this leg spend" a measurement rather than a race.
    """

    def __init__(self) -> None:
        self.nanoseconds = 0

    def get_clock(self) -> _Clock:
        return self

    def now(self) -> _Clock:
        return self

    def advance(self, seconds: float) -> None:
        self.nanoseconds += int(seconds * 1e9)


def _ladder(module) -> tuple:
    """Three milestones, one of which is a `lifted` — which `_run_one_piece` requires.

    Fabricated rather than derived from the generated topology on purpose: these
    tests are about the loop, and `test_continuous_line_ladder.py` already owns
    the dependency on the generated artifact. `Milestone` is a plain `NamedTuple`,
    so constructing one needs nothing from ROS.
    """
    return (
        module.Milestone("sensed", "station_transfer_1", "", "/cite/cell_a/beam_1/events", ""),
        module.Milestone("lifted", "station_transfer_1", "cell_a__table_pick__surface", "", ""),
        module.Milestone("on_link", "station_transfer_1", "cell_a__conveyor_1__infeed", "", "c1"),
    )


def _line_state_message() -> types.SimpleNamespace:
    """A `LineState` carrying exactly the fields `_context` reads off one."""
    return types.SimpleNamespace(
        state=STALLED,
        workpieces_completed=0,
        blocked_reason="",
        stall_reasons=["station_transfer_1 still holds its work-piece"],
        stations=[
            types.SimpleNamespace(
                station_id="station_transfer_1",
                actor_asset_id="arm_1",
                state=4,
                buffer_occupancy=1,
                buffer_capacity=1,
                current_workpiece_id="workpiece_1",
            )
        ],
    )


def _fake_self(module, *, ladder=(), reached=lambda milestone, sample: False, halt_on=None):
    """A stand-in for the `TestCase`, carrying every attribute the loop touches.

    `halt_on` is the 1-based spin on which the fabricated `LineState` callback
    lands, expressed as a spin because that is how it arrives in the real loop:
    `rclpy.spin_once` delivers the message, and the next statement is what decides
    whether the run continues.
    """
    clock = _Clock()
    fake = types.SimpleNamespace(
        node=clock,
        clock=clock,
        seed="unset",
        workpiece="",
        world="",
        _ladder=ladder,
        _journeys=[],
        _halt=None,
        _beams=[],
        _beams_from=0,
        _line_states=[],
        _samples=[],
        _emitted=[],
        _spawned=[],
        _spins=0,
    )

    def fail(message: str) -> None:
        raise AssertionError(message)

    fake.fail = fail
    fake.assertTrue = lambda value, message="": None if value else fail(message)
    fake.assertIsNotNone = lambda value, message="": None if value is not None else fail(message)
    fake._resolve = lambda frame: (0.0, 0.0, 1.0)
    fake._spawn_workpiece = fake._spawned.append
    fake._workpiece_xyz = lambda: (0.1, 0.2, 1.3)
    fake._now = lambda: clock.nanoseconds / 1e9
    fake._within_the_cell = lambda sample: ""
    fake._reached = reached
    fake._emit_timing = lambda *args: fake._emitted.append(args)

    for name in ("_fail_if_the_line_has_stopped", "_context"):
        function = vars(module.TestContinuousLine)[name]
        setattr(fake, name, function.__get__(fake, type(fake)))

    def spin_once(node, timeout_sec=None):
        fake._spins += 1
        clock.advance(SPIN_STEP_S)
        if halt_on is not None and fake._spins == halt_on:
            message = _line_state_message()
            fake._line_states.append(message)
            fake._halt = module.Halt(STALLED, "; ".join(message.stall_reasons), fake._now())

    module.rclpy = types.SimpleNamespace(spin_once=spin_once)
    return fake


def _run_one_piece(module, fake, ladder, piece=1):
    return vars(module.TestContinuousLine)["_run_one_piece"](fake, piece, ladder)


def test_the_fabricated_ladder_is_not_degenerate(line_state) -> None:
    """A ladder of one milestone would let every test below pass over nothing.

    The house habit: assert the fixture has enough structure to distinguish
    "stopped at the milestone in flight" from "stopped at the only milestone".
    """
    ladder = _ladder(line_state)
    assert len(ladder) >= 2, f"the fabricated ladder has {len(ladder)} milestone(s)"
    assert any(m.kind == "lifted" for m in ladder), (
        "`_run_one_piece` asserts that some station picks something up; a ladder "
        "without a `lifted` milestone would fail on that assertion instead of on "
        "the loop this guard is about"
    )


def test_a_halted_leg_ends_the_run_instead_of_spending_the_ceiling(line_state) -> None:
    """The 417.8 s claim, measured as one spin.

    The milestone is never reached, so before the fix this loop ran until the node
    clock passed `LEG_CEILING_S` and the failure arrived a full leg late. It must
    now end on the spin that delivered the halt.
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder, halt_on=3)

    with pytest.raises(AssertionError) as raised:
        _run_one_piece(module, fake, ladder)

    spent_s = fake.clock.nanoseconds / 1e9
    assert spent_s < module.LEG_CEILING_S / 10.0, (
        f"the leg spent {spent_s:.1f}s of clock against a ceiling of "
        f"{module.LEG_CEILING_S:.0f}s; the halt was published on spin 3 and the run "
        "should have ended there, not on the budget"
    )
    assert fake._spins <= 4, (
        f"the loop spun {fake._spins} time(s) after the halt was published on spin 3; "
        "the check belongs immediately after the spin, before the milestone test"
    )
    assert "stalled" in str(
        raised.value
    ), f"the failure does not report the stall it ended on: {raised.value}"


def test_a_leg_that_is_merely_slow_still_returns_what_it_managed(line_state) -> None:
    """The other half of the contract, and the reason a fail-fast alone is not enough.

    A missed milestone on a line that has NOT said it stopped is data: the piece
    returns a short `Journey` and the verdict at the end names the milestone. If
    this ever raises, the report stops being able to say "two of three pieces
    traversed the line" and starts saying "the first thing that went wrong".
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder, halt_on=None)
    # A large step so the node clock passes the leg ceiling in a few spins; the
    # loop's exit condition is the clock, not the spin count.
    fake.clock.advance(0)
    original = module.rclpy.spin_once

    def slow_spin(node, timeout_sec=None):
        original(node, timeout_sec)
        fake.clock.advance(60.0)

    module.rclpy = types.SimpleNamespace(spin_once=slow_spin)

    journey = _run_one_piece(module, fake, ladder)

    assert journey.reached == (), "no milestone was reachable, so none may be reported"
    assert len(journey.reached) < len(ladder), "a short journey is what a stalled piece returns"
    assert journey.waited_s >= 0.0, "the leg's own wait is what `_context` prints"
    assert fake._journeys == [], (
        "`_run_one_piece` appended a journey on the non-halt path; the caller owns "
        "that append, and a piece counted twice would misreport the verdict"
    )


def test_a_leg_that_completes_is_unaffected(line_state) -> None:
    """The check must not pre-empt a milestone that was reached.

    Placed after the `_reached` test instead of before it, the loop would answer
    "what wins when a halt and a milestone land in the same spin" differently from
    `_spin_until`, and would pay a `gz model -p` subprocess on the way out. Here
    nothing halts at all, and every milestone must still be recorded and timed.
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder, reached=lambda milestone, sample: True)

    journey = _run_one_piece(module, fake, ladder)

    assert journey.reached == tuple(
        m.describe() for m in ladder
    ), f"a complete piece reported {journey.reached}"
    assert len(fake._emitted) == len(ladder), (
        f"{len(fake._emitted)} CITE_TIMING record(s) for {len(ladder)} completed leg(s); "
        "a campaign re-deriving the leg ceiling reads one per milestone"
    )
    assert fake._halt is None and fake._journeys == []


def test_the_failure_carries_the_ladder_and_the_stop_point(line_state) -> None:
    """The report the observed incident lost.

    Asserted on substance rather than on phrasing: the halt, every milestone the
    topology defines, a stop-point line naming the milestone that was in flight,
    the per-station detail from the last `LineState`, and the sample summary. Each
    of those is something the three CI failures at `station_transfer_1` were
    diagnosed from, and none of them was printed by the run that motivated this.
    """
    module = line_state
    ladder = _ladder(module)
    # The first milestone is reached, the rest are not, and the halt lands while
    # the second is in flight — so the stop point and the ladder listing name
    # different milestones and the assertion below cannot pass on the wrong one.
    reached_first = {ladder[0]: True}
    fake = _fake_self(
        module,
        ladder=ladder,
        reached=lambda milestone, sample: reached_first.get(milestone, False),
        halt_on=4,
    )
    fake.workpiece = "workpiece_1"
    fake.world = "cell_a"

    with pytest.raises(AssertionError) as raised:
        _run_one_piece(module, fake, ladder)
    report = str(raised.value)

    assert fake._halt.describe() in report, "the halt itself is missing from the report"
    for milestone in ladder:
        assert milestone.describe() in report, (
            f"the ladder listing omits {milestone.describe()}; the report has to say "
            f"what the line was supposed to do:\n{report}"
        )
    stop_points = [line for line in report.splitlines() if "STOPPED after" in line]
    assert len(stop_points) == 1, f"expected one stop-point line, got {stop_points}"
    assert (
        ladder[1].describe() in stop_points[0]
    ), f"the stop point does not name the milestone in flight: {stop_points[0]}"
    assert (
        "station_transfer_1" in report and "workpiece_1" in report
    ), f"the per-station detail from the last LineState is missing:\n{report}"
    assert "work-piece samples:" in report, f"the sample summary is missing:\n{report}"
    assert (
        f"{module.LEG_CEILING_S:.0f}s" in stop_points[0]
    ), "the stop point states no ceiling to read the wait against"


def test_a_stop_during_the_removal_wait_still_carries_the_context(line_state) -> None:
    """THE REGRESSION FOR THE OBSERVED INCIDENT, on the exact path CI hit.

    The leg burned its ceiling, `_run_one_piece` returned short, the piece loop
    called `_remove_workpiece()`, and that wait's pre-loop halt check raised. The
    message named the removal wait — which had nothing to do with the fault — and
    carried no report at all. It fails before the change and passes after.
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder)
    fake.workpiece = "workpiece_1"
    fake.world = "cell_a"
    fake._line_states.append(_line_state_message())
    fake._halt = module.Halt(STALLED, "station_transfer_1 still holds its work-piece", 12.5)
    fake._journeys.append(module.Journey(1, (ladder[0].describe(),), (), 420.0))

    with pytest.raises(AssertionError) as raised:
        vars(module.TestContinuousLine)["_spin_until"](
            fake,
            lambda: None,
            module.LEG_CEILING_S,
            f"the work-piece '{fake.workpiece}' to leave the simulator",
        )
    report = str(raised.value)

    assert "to leave the simulator" in report, "the wait in flight is still named, as it was"
    for milestone in ladder:
        assert milestone.describe() in report, (
            "the removal wait's failure carries no ladder. This is the incident: the "
            f"message named a wait that had nothing to do with the fault.\n{report}"
        )
    assert (
        "STOPPED after 1/3" in report
    ), f"the piece's own stop point is missing from the removal wait's report:\n{report}"
    assert "station_transfer_1" in report, f"the per-station detail is missing:\n{report}"
    assert fake._spins == 0, "the pre-loop check must fire before the first spin"


def test_the_context_survives_being_asked_before_anything_has_run(line_state) -> None:
    """`_context` is now reachable from three call sites, the earliest before step 1.

    `_resolve` waits on TF and can raise through `_fail_if_the_line_has_stopped`
    while `workpiece` and `world` are still empty strings and the ladder is still
    the empty tuple `setUp` gave it. It must not raise, and it must say what is
    missing rather than printing `model '' in world ''`, which reads like a cell
    with no work-piece rather than like a report taken early.
    """
    module = line_state
    fake = _fake_self(module)

    report = fake._context()

    assert (
        "not yet resolved" in report
    ), f"an unresolved work-piece and world are printed as empty strings:\n{report}"
    assert "0 milestone(s)" in report, f"the empty ladder is not stated:\n{report}"
    assert "no LineState was ever received" in report, f"silence is not stated:\n{report}"
    assert "never located in the simulator" in report, f"the missing samples are hidden:\n{report}"


def _calls_to(node: ast.AST, attribute: str) -> list[int]:
    """Line numbers of every `self.<attribute>(...)` call inside `node`."""
    return sorted(
        call.lineno
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == attribute
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
    )


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"continuous_line.py defines no function `{name}`")


def test_the_leg_loop_itself_checks_and_the_helper_itself_reports() -> None:
    """The tripwire for a rewrite that keeps every test above passing by accident.

    A source scan, because both halves are about WHERE the call is and not about
    what one call produces. The halt check has to be INSIDE the deadline loop —
    one placed just before or just after it looks identical to a call-graph test
    driven from outside, and buys back the full leg ceiling. And
    `_fail_if_the_line_has_stopped` has to build the report itself, because it is
    the raise a reader will actually have.
    """
    tree = ast.parse(SCENARIO.read_text())

    run_one_piece = _function(tree, "_run_one_piece")
    loops = [node for node in ast.walk(run_one_piece) if isinstance(node, ast.While)]
    assert len(loops) == 1, (
        f"`_run_one_piece` holds {len(loops)} `while` loop(s) at line(s) "
        f"{[loop.lineno for loop in loops]}; this guard is written against the one "
        "deadline loop that bounds a leg"
    )
    in_loop = _calls_to(loops[0], "_fail_if_the_line_has_stopped")
    assert in_loop, (
        "the leg's deadline loop (line "
        f"{loops[0].lineno}) never calls `self._fail_if_the_line_has_stopped`. A call "
        "elsewhere in the method is not the same thing: a line that stops mid-leg is "
        "then noticed only once the leg ceiling has expired, which cost two CI runs "
        "417.8 s and 420.6 s each"
    )

    helper = _function(tree, "_fail_if_the_line_has_stopped")
    reports = _calls_to(helper, "_context")
    assert reports, (
        f"`_fail_if_the_line_has_stopped` (line {helper.lineno}) never calls "
        "`self._context`; the raise that ends a stopped run would carry one sentence "
        "about whichever wait was in flight and no diagnostic at all"
    )
