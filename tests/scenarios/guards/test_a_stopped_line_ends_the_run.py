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
that advances a fake clock and delivers a fabricated `LineState` on a chosen spin.
`_fail_if_the_line_has_stopped`, `_context`, `_spin_until`, `_spawn_workpiece` and
`_on_line_state` are bound onto the stand-in with `__get__`, so what runs is the
shipped code and not a restatement of it.

**Both arms are REACHED and not merely reachable, and that distinction is the
whole reason this paragraph is here.** The `line_state` fixture patches the
`LineState` family and `StationState` together to plain ints, which makes the
BLOCKED/FAULTED arm of `_fail_if_the_line_has_stopped` executable — and an earlier
version of this file stopped there, fabricating every halt as STALLED. The arm
that handles ADR-0038's escalation, which is the state BOTH CI incidents this file
exists for actually published, was then never entered: an early `return` in front
of it left this guard 9 of 9 green while a BLOCKED line no longer ended the run at
all. Every halt fabricated below is therefore parametrized over all three states,
and each case asserts the string its own arm produces.

**A `LineState` becomes a `Halt` through the shipped `_on_line_state` here**, not
through a restatement of it in the fixture. That latch — first halt only, and
`stall_reasons` rather than `blocked_reason` for a stall — is the one conversion
every test below depends on, and it was tested nowhere.

## What it cannot see

It drives the loop, not the cell: no station escalates here, and nothing measures
whether the coordinator's `LineState` arrives at all — that the scenario subscribes
to the topic is held by the scenario itself. The source-scanning tests at the end
are the tripwire for a rewrite that keeps the others passing by accident; they pin
WHERE the halt check sits, because a check that is merely present but late buys
back the ceiling this file is about.
"""

from __future__ import annotations

import ast
import re
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

#: Plain ints standing in for the `LineState` constants. Any distinct values do;
#: what matters is that they compare equal to themselves, which the stub's freshly
#: minted attributes do not. `RUNNING` is deliberately NOT in the fabricated
#: `STOPPED_STATES`: a latch that fires on it would be a line ended by a healthy
#: report.
RUNNING, BLOCKED, FAULTED, STALLED = 0, 1, 2, 3

#: A `StationState` value that is not `STATE_FAULTED`, and the one that is.
#: `_on_line_state` reads both, so the fixture patches that name too rather than
#: leaving the comparison to the stub's mint-a-new-object behaviour, which would
#: answer "not faulted" for a faulted station and be right by accident.
STATION_WORKING, STATION_FAULTED = 4, 9

#: Each stopped state with a fragment of the arm of `_fail_if_the_line_has_stopped`
#: that must handle it. STALLED has an arm of its own — ADR-0038 decision 5, no
#: re-arm path — and BLOCKED and FAULTED share the other, which is the one both CI
#: incidents landed in and the one nothing used to enter.
ARMS = {
    "stalled": (STALLED, "the line stalled while waiting for", "Nothing escalated"),
    "blocked": (BLOCKED, "the line stopped while waiting for", "no longer ends the process"),
    "faulted": (FAULTED, "the line stopped while waiting for", "no longer ends the process"),
}

#: The reason each fabricated `LineState` carries, in the field its own state uses.
#: `_on_line_state` reads `stall_reasons` for a stall and `blocked_reason`
#: otherwise, because they are different facts (ADR-0039); a guard that put the
#: same text in both could not tell which one the shipped code read.
STALL_REASON = "station_transfer_1 still holds its work-piece"
BLOCKED_REASON = "station_transfer_1 escalated and the line stopped"


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
    """Patch the message constants together, and put them back afterwards.

    Together, because they are one fact stated in several places: the constants,
    the tuple of stopped values, and the names the report prints. Patching one
    alone produces a module that is internally inconsistent in a way the container
    never is — a halt whose state is in `STOPPED_STATES` but matches no constant,
    or one that matches a constant and has no name.

    `StationState` joins them because `_on_line_state` reads it, and this guard
    now drives that function rather than restating it. `rclpy` joins them because
    `_fake_self` replaces the module's, and a replacement left behind is a module
    the next test in the session inherits in a state no container produces.
    """
    saved = (
        module.LineState,
        module.STOPPED_STATES,
        module.STOPPED_STATE_NAMES,
        module.StationState,
        module.rclpy,
    )
    module.LineState = types.SimpleNamespace(
        STATE_BLOCKED=BLOCKED, STATE_FAULTED=FAULTED, STATE_STALLED=STALLED
    )
    module.STOPPED_STATES = (BLOCKED, FAULTED, STALLED)
    module.STOPPED_STATE_NAMES = {BLOCKED: "BLOCKED", FAULTED: "FAULTED", STALLED: "STALLED"}
    module.StationState = types.SimpleNamespace(STATE_FAULTED=STATION_FAULTED)
    try:
        yield module
    finally:
        (
            module.LineState,
            module.STOPPED_STATES,
            module.STOPPED_STATE_NAMES,
            module.StationState,
            module.rclpy,
        ) = saved


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


def _line_state_message(state=STALLED, *, station_state=STATION_WORKING):
    """A `LineState` carrying exactly the fields `_on_line_state` and `_context` read.

    The reason goes in the field the state uses and the other is left empty, so
    that a test can tell which field the shipped latch read.
    """
    stalled = state == STALLED
    return types.SimpleNamespace(
        state=state,
        workpieces_completed=0,
        blocked_reason="" if stalled else BLOCKED_REASON,
        stall_reasons=[STALL_REASON] if stalled else [],
        stations=[
            types.SimpleNamespace(
                station_id="station_transfer_1",
                actor_asset_id="arm_1",
                state=station_state,
                buffer_occupancy=1,
                buffer_capacity=1,
                current_workpiece_id="workpiece_1",
            )
        ],
    )


def _fake_self(
    module,
    *,
    ladder=(),
    reached=lambda milestone, sample: False,
    halt_on=None,
    halt_state=STALLED,
):
    """A stand-in for the `TestCase`, carrying every attribute the loop touches.

    `halt_on` is the 1-based spin on which the fabricated `LineState` callback
    lands, expressed as a spin because that is how it arrives in the real loop:
    `rclpy.spin_once` delivers the message, and the next statement is what decides
    whether the run continues. The message is handed to the SHIPPED
    `_on_line_state`, so the conversion from a state to a `Halt` under test here
    is the one the cell performs.
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
        _faults=[],
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
    fake.assertEqual = lambda a, b, message="": None if a == b else fail(message)
    fake.assertIsNotNone = lambda value, message="": None if value is not None else fail(message)
    fake._resolve = lambda frame: (0.0, 0.0, 1.0)
    fake._spawn_workpiece = fake._spawned.append
    fake._workpiece_xyz = lambda: (0.1, 0.2, 1.3)
    fake._now = lambda: clock.nanoseconds / 1e9
    fake._within_the_cell = lambda sample: ""
    fake._reached = reached
    fake._emit_timing = lambda *args: fake._emitted.append(args)

    for name in ("_fail_if_the_line_has_stopped", "_context", "_on_line_state"):
        function = vars(module.TestContinuousLine)[name]
        setattr(fake, name, function.__get__(fake, type(fake)))

    def spin_once(node, timeout_sec=None):
        fake._spins += 1
        # The scenario's own `SAMPLE_PERIOD_S` rather than a copy of its value:
        # a spin count here then means what it means there, and CLAUDE.md §4
        # forbids the same number living in two files.
        clock.advance(module.SAMPLE_PERIOD_S)
        if halt_on is not None and fake._spins == halt_on:
            fake._on_line_state(_line_state_message(halt_state))

    module.rclpy = types.SimpleNamespace(spin_once=spin_once)
    return fake


def _bind(module, fake, name):
    """Bind one more shipped method onto the stand-in, for the tests that need it."""
    function = vars(module.TestContinuousLine)[name]
    setattr(fake, name, function.__get__(fake, type(fake)))
    return getattr(fake, name)


def _run_one_piece(module, fake, ladder, piece=1):
    return vars(module.TestContinuousLine)["_run_one_piece"](fake, piece, ladder)


def _stop_point(report: str) -> str:
    """The one `STOPPED after` line `_context` produced, asserted to be one."""
    lines = [line for line in report.splitlines() if "STOPPED after" in line]
    assert len(lines) == 1, f"expected one stop-point line, got {lines}"
    return lines[0]


def _reported_wait_s(stop_point: str) -> float:
    """The wait `_context` printed for a piece, in seconds.

    Parsed rather than pattern-matched because the defect this pins is a wrong
    NUMBER in a right-looking sentence: the report used to state `LEG_CEILING_S`
    where the leg's own wait belongs, and every substring assertion that named the
    ceiling was satisfied by the trailing `(the leg ceiling is 420s)` clause
    whichever number came first.
    """
    match = re.search(r"waiting on .* for ([0-9.]+)s \(the leg ceiling is", stop_point)
    assert match, f"the stop point states no wait at all: {stop_point}"
    return float(match.group(1))


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


# -----------------------------------------------------------------------------
# The latch: a `LineState` becomes a `Halt`
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state,name", [(BLOCKED, "BLOCKED"), (FAULTED, "FAULTED"), (STALLED, "STALLED")]
)
def test_the_latch_turns_a_stopped_line_state_into_a_halt(line_state, state, name) -> None:
    """`_on_line_state` is the only conversion every other test here rests on.

    It was covered by nothing: narrowing its state test to STALLED alone left this
    file 9 of 9 green, and `test_the_stopped_state_set_still_has_three_members`
    could not see it, because `STOPPED_STATES` stayed intact and merely stopped
    being read.
    """
    module = line_state
    fake = _fake_self(module)

    fake._on_line_state(_line_state_message(state))

    assert fake._halt is not None, (
        f"a line publishing {name} produced no halt; every member of STOPPED_STATES "
        "means no station will act again without a person (ADR-0038)"
    )
    assert fake._halt.state == state
    assert name in fake._halt.describe(), f"the halt does not say which end it was: {fake._halt}"
    assert fake._line_states == [
        fake._line_states[0]
    ], "the message itself is what `_context` prints the per-station detail from"


def test_the_latch_ignores_a_healthy_line(line_state) -> None:
    """A state outside `STOPPED_STATES` is the line working, and ends nothing."""
    module = line_state
    fake = _fake_self(module)

    fake._on_line_state(_line_state_message(RUNNING))

    assert fake._halt is None, (
        "a RUNNING LineState latched a halt; every wait in the scenario would then "
        "end on the first healthy report the coordinator published"
    )
    assert len(fake._line_states) == 1, "a healthy state is still context and is still kept"


@pytest.mark.parametrize(
    "state,expected",
    [(STALLED, STALL_REASON), (BLOCKED, BLOCKED_REASON), (FAULTED, BLOCKED_REASON)],
)
def test_the_latch_reads_the_reason_from_the_field_that_state_uses(line_state, state, expected):
    """`stall_reasons` for a stall, `blocked_reason` otherwise — they are two facts.

    ADR-0039: `blocked_reason` is what one station's tree said, `stall_reasons` is
    what the line derived about stations whose trees have said nothing. Reading
    the wrong one prints "no reason published" over the only sentence naming the
    station, which is the sentence the three CI failures were diagnosed from.
    """
    module = line_state
    fake = _fake_self(module)

    fake._on_line_state(_line_state_message(state))

    assert fake._halt.reason == expected, (
        f"a {module.STOPPED_STATE_NAMES[state]} halt reported reason "
        f"{fake._halt.reason!r}; the reason for this state lives in the other field"
    )


def test_the_latch_keeps_the_first_halt_and_not_the_last(line_state) -> None:
    """What stopped the line is what a person needs; the repeats are the same fact.

    A stopped line republishes several times a second, and a station that
    escalates after the first one did not cause this.
    """
    module = line_state
    fake = _fake_self(module)

    fake._on_line_state(_line_state_message(BLOCKED))
    first = fake._halt
    fake._on_line_state(_line_state_message(STALLED))

    assert fake._halt is first, (
        f"the halt moved from {first.describe()} to {fake._halt.describe()}; the run "
        "would then report whichever state the line was republishing when the "
        "assertion happened to fire, not the one that stopped it"
    )


# -----------------------------------------------------------------------------
# The leg loop
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("arm", list(ARMS), ids=list(ARMS))
def test_a_halted_leg_ends_the_run_instead_of_spending_the_ceiling(line_state, arm) -> None:
    """The 417.8 s claim, measured as one spin, in each of the three states.

    The milestone is never reached, so before the fix this loop ran until the node
    clock passed `LEG_CEILING_S` and the failure arrived a full leg late. It must
    now end on the spin that delivered the halt.

    Parametrized because BOTH CI INCIDENTS WERE BLOCKED, and a version of this
    file that fabricated every halt as STALLED never entered the arm that handles
    them: a bare `return` in front of that arm passed 9 of 9 while a BLOCKED line
    no longer ended the run at all.
    """
    module = line_state
    state, opening, distinctive = ARMS[arm]
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder, halt_on=3, halt_state=state)

    with pytest.raises(AssertionError) as raised:
        _run_one_piece(module, fake, ladder)
    report = str(raised.value)

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
    assert opening in report, (
        f"a {arm.upper()} line did not produce its own arm's message. Each arm says "
        f"something different about what a person can do next:\n{report}"
    )
    assert distinctive in report, (
        f"the {arm.upper()} arm's own explanation is missing; the two arms differ on "
        f"whether /cite/line/reset_station has anything to clear:\n{report}"
    )
    for milestone in ladder:
        assert milestone.describe() in report, (
            f"the {arm.upper()} arm raised without `_context`. Both arms carry the "
            f"whole report — that is the half of this change that cost more:\n{report}"
        )
    assert len(fake._journeys) == 1, (
        f"{len(fake._journeys)} journey(s) recorded for one piece. The in-loop site "
        "appends before it raises, so a raise that does not happen makes one piece "
        "into hundreds of duplicate rows in the verdict"
    )


def test_a_leg_whose_helper_does_not_raise_still_ends_and_appends_once(line_state) -> None:
    """The amplifier, pinned on its own: the append must not outlive the raise.

    The in-loop site appends a partial `Journey` and then calls
    `_fail_if_the_line_has_stopped`, ASSUMING it raises. Under a mutation where it
    returns instead, the measured result was 839 duplicate journeys for one piece
    and a full 840-spin leg — a corrupted verdict rather than a clean miss. The
    loop therefore raises for itself if the helper hands control back.
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder, halt_on=2)
    fake._fail_if_the_line_has_stopped = lambda what: None

    with pytest.raises(AssertionError) as raised:
        _run_one_piece(module, fake, ladder)

    assert fake._spins <= 3, (
        f"the loop spun {fake._spins} time(s) with a halt latched on spin 2; it ran on "
        "to its deadline because it trusted the helper to raise"
    )
    assert len(fake._journeys) == 1, (
        f"{len(fake._journeys)} journey(s) appended for one piece; every spin past the "
        "halt appends another and `_context` reports the same piece once per spin"
    )
    for milestone in ladder:
        assert milestone.describe() in str(raised.value), (
            "the loop's own raise carries no report; it is the message a reader has "
            f"when the helper stopped producing one:\n{raised.value}"
        )


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
    # Bounded, not merely non-negative: `>= 0.0` is vacuous for a difference of
    # two `time.monotonic()` reads, and it passed unchanged while the field was
    # being filled with `LEG_CEILING_S`. The leg above is a handful of no-op
    # spins on a FAKE clock, so its real wall-clock cost is milliseconds; a value
    # anywhere near the ceiling means the ceiling was recorded as the wait.
    assert 0.0 <= journey.waited_s < module.LEG_CEILING_S / 10.0, (
        f"the leg reported a wait of {journey.waited_s:.1f}s against a ceiling of "
        f"{module.LEG_CEILING_S:.0f}s. This leg spun a fake clock a few times and cost "
        "milliseconds of wall clock; `waited_s` is the leg's OWN wait and not the "
        "budget it was allowed"
    )
    assert fake._journeys == [], (
        "`_run_one_piece` appended a journey on the non-halt path; the caller owns "
        "that append, and a piece counted twice would misreport the verdict"
    )


def test_a_leg_that_completes_is_unaffected(line_state) -> None:
    """The check must not pre-empt a milestone that was reached.

    Nothing halts at all here, and every milestone must still be recorded and
    timed. The companion case — a halt and a milestone landing on the SAME spin —
    is the test below; this one alone never halts, so it cannot see where in the
    loop body the check sits.
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


def test_a_halt_and_a_milestone_on_one_spin_emit_no_timing_record(line_state) -> None:
    """What wins when both land on the same spin, and what it costs if the halt loses.

    The halt check sits before the milestone test, so a leg cut short by a stopped
    line records NOTHING: `_emit_timing`'s docstring makes that a decision, because
    a truncated leg's record is indistinguishable from a completed one's and a
    campaign deriving a margin as `ceiling / slowest instance` would ingest it.

    Move the check to the end of the loop body and every test that never halts on
    a reached spin carries on passing, while this case emits one contaminated
    record, reports one milestone the line did not really clear, and pays a
    `gz model -p` on the way out.
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder, halt_on=3)
    fake._reached = lambda milestone, sample: fake._spins == 3

    with pytest.raises(AssertionError) as raised:
        _run_one_piece(module, fake, ladder)

    assert fake._emitted == [], (
        f"{len(fake._emitted)} CITE_TIMING record(s) were emitted for a leg the line "
        "stopped under. `_emit_timing` excludes them by decision: such a record "
        "measures a coordinator's escalation and cannot be told from a real leg"
    )
    assert "STOPPED after 0/3" in str(raised.value), (
        "a milestone reached on the same spin as the halt was counted; the halt "
        f"check has moved to after the milestone test:\n{raised.value}"
    )
    assert fake._spins == 3, (
        f"the loop spun {fake._spins} times; the halt landed on spin 3 and the check "
        "immediately after the spin is what stops the next one"
    )


@pytest.mark.parametrize("arm", list(ARMS), ids=list(ARMS))
def test_the_failure_carries_the_ladder_and_the_stop_point(line_state, arm) -> None:
    """The report the observed incident lost.

    Asserted on substance rather than on phrasing: the halt, every milestone the
    topology defines, a stop-point line naming the milestone that was in flight
    and the wait THAT LEG actually spent, the per-station detail from the last
    `LineState`, and the sample summary. Each of those is something the three CI
    failures at `station_transfer_1` were diagnosed from, and none of them was
    printed by the run that motivated this.
    """
    module = line_state
    state, _, _ = ARMS[arm]
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
        halt_state=state,
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
    stop_point = _stop_point(report)
    assert (
        ladder[1].describe() in stop_point
    ), f"the stop point does not name the milestone in flight: {stop_point}"
    assert (
        "station_transfer_1" in report and "workpiece_1" in report
    ), f"the per-station detail from the last LineState is missing:\n{report}"
    assert (STALL_REASON if state == STALLED else BLOCKED_REASON) in report, (
        f"the reason a {arm.upper()} line published is missing; it is the only "
        f"sentence naming what the station was doing:\n{report}"
    )
    assert "work-piece samples:" in report, f"the sample summary is missing:\n{report}"
    assert (
        f"(the leg ceiling is {module.LEG_CEILING_S:.0f}s)" in stop_point
    ), f"the stop point states no ceiling to read the wait against: {stop_point}"
    # The wait and the ceiling are DIFFERENT NUMBERS, and the whole reason
    # `Journey.waited_s` exists is that the report used to print the second where
    # the first belongs. This leg was cut short after four no-op spins on a fake
    # clock, so anything approaching the ceiling is the ceiling.
    waited_s = _reported_wait_s(stop_point)
    assert waited_s < module.LEG_CEILING_S / 10.0, (
        f"the stop point reports a wait of {waited_s}s against a ceiling of "
        f"{module.LEG_CEILING_S:.0f}s. A leg the line stopped after four spins did not "
        "wait its budget; reporting the ceiling here is false timing evidence in the "
        "one place a reader goes for timing evidence"
    )


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
    fake._on_line_state(_line_state_message(STALLED))
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


def test_a_halt_during_the_spawn_wait_is_not_re_labelled_as_a_setup_failure(
    line_state, tmp_path, monkeypatch
) -> None:
    """A stopped line is not a missing work-piece, and must not be reported as one.

    `_spawn_workpiece` wraps its settling wait in `except AssertionError` and
    re-raises it framed as a setup failure, with the `create` output and a
    `gz model --list` attached. That framing is right for a work-piece that never
    appeared and wrong for the one failure it also catches: the halt raise, which
    already carries the whole report. Wrapped, it reads as a spawn problem about a
    part that was created perfectly well, and spends up to 30 s of a stopped
    cell's time collecting a listing nobody needs.

    `module.Path` is redirected so the fabricated SDF lands in pytest's `tmp_path`
    rather than in the host's `/tmp`; `_spawn_workpiece` is the only method here
    that uses it.
    """
    module = line_state
    ladder = _ladder(module)
    fake = _fake_self(module, ladder=ladder)
    fake.workpiece = "workpiece_1"
    fake.world = "cell_a"
    fake._on_line_state(_line_state_message(BLOCKED))
    _bind(module, fake, "_spin_until")
    del fake._spawn_workpiece  # the real one, not the recorder `_fake_self` installs
    spawn = _bind(module, fake, "_spawn_workpiece")

    calls: list[list[str]] = []

    def gz_run(command, **kwargs):
        calls.append(command)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module, "gz_run", gz_run)
    monkeypatch.setattr(module, "Path", lambda p: tmp_path / Path(p).name)

    with pytest.raises(AssertionError) as raised:
        spawn((0.0, 0.0, 1.0))
    report = str(raised.value)

    assert "create stdout" not in report and "gz model --list" not in report, (
        "a stopped line was re-labelled as a spawn failure. The reader is handed a "
        f"message about a work-piece that was created fine:\n{report}"
    )
    assert (
        "the line stopped while waiting for" in report
    ), f"the halt's own message did not survive the spawn path:\n{report}"
    for milestone in ladder:
        assert milestone.describe() in report, f"the report was lost on the way out:\n{report}"
    assert len(calls) == 1, (
        f"{len(calls)} gz calls; the halt path must not spend a `gz model --list` "
        "timeout on a cell that has already stopped"
    )


def test_the_context_survives_being_asked_before_anything_has_run(line_state) -> None:
    """A robustness pin on `_context`, NOT a live path — and the difference matters.

    `_context` must be callable at any moment, including before a work-piece name,
    a world or a milestone exists. It is not reachable that early today: the test
    method assigns `self._ladder` at step 0, resolves the names at step 1, and does
    not subscribe to `LineState` until step 3, so `_halt` cannot be set while any
    of the three is still empty and neither `'not yet resolved'` nor
    `0 milestone(s)` can appear in a real run. An earlier version of this docstring
    claimed `_resolve` could raise into that window; it cannot.

    What this pins is the ORDER staying safe. Move the subscription above the
    resolution — a reasonable-looking reordering — and the earliest report becomes
    live, formatted by code nothing had exercised. A report that raises while
    formatting a failure destroys the failure it was formatting.
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


def test_the_context_survives_a_journey_longer_than_the_ladder(line_state) -> None:
    """The `<` in `_context`'s stop-point branch, on the input it actually guards.

    Not an over-long journey against a real ladder — `reached` is built from the
    same tuple and cannot outrun it — but a journey and a ladder that came from
    different places. `self._ladder` still `()` with a journey already appended
    makes the unguarded expression `()[1]`, and an IndexError raised while
    formatting a failure report destroys the report it was formatting.
    """
    module = line_state
    fake = _fake_self(module)
    fake._journeys.append(module.Journey(1, ("some milestone",), (), 3.0))

    report = fake._context()

    assert "nothing this ladder names" in report, (
        "the stop-point branch indexed a ladder shorter than the journey instead of "
        f"saying it had nothing to name:\n{report}"
    )


# -----------------------------------------------------------------------------
# The source-scanning tripwires
# -----------------------------------------------------------------------------


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


def _assignments_to(node: ast.AST, attribute: str) -> list[int]:
    """Line numbers of every `self.<attribute> = ...` inside `node`."""
    return sorted(
        assign.lineno
        for assign in ast.walk(node)
        if isinstance(assign, ast.Assign)
        for target in assign.targets
        if isinstance(target, ast.Attribute)
        and target.attr == attribute
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    )


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"continuous_line.py defines no function `{name}`")


@pytest.fixture(scope="module")
def tree() -> ast.AST:
    return ast.parse(SCENARIO.read_text())


def test_the_leg_loop_checks_before_it_measures_and_the_helper_itself_reports(tree) -> None:
    """The tripwire for a rewrite that keeps every test above passing by accident.

    A source scan, because both halves are about WHERE the call is and not about
    what one call produces. The halt check has to be INSIDE the deadline loop —
    one placed just before or just after it looks identical to a call-graph test
    driven from outside, and buys back the full leg ceiling.

    AND IT HAS TO BE EARLY IN THE BODY, which is the half this test used to miss.
    Moving the whole block to the end of the loop body kept the call inside the
    one `while` and left this tripwire green; the loop then emits a `CITE_TIMING`
    record for a leg the line stopped under, reports a milestone it did not really
    clear, and spends an extra spin and an extra `gz model -p` doing it.

    And `_fail_if_the_line_has_stopped` has to build the report itself, because it
    is the raise a reader will actually have.
    """
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
    locates = _calls_to(loops[0], "_workpiece_xyz")
    tests = _calls_to(loops[0], "_reached")
    assert locates and tests, (
        "the leg loop no longer locates the work-piece or tests the milestone; this "
        "tripwire orders the halt check against both and can order it against neither"
    )
    assert min(in_loop) < min(locates), (
        f"the halt check (line {min(in_loop)}) comes after `self._workpiece_xyz()` "
        f"(line {min(locates)}). That shells out to `gz model -p` with a 30 s timeout, "
        "on a cell that has already stopped and cannot answer differently"
    )
    assert min(in_loop) < min(tests), (
        f"the halt check (line {min(in_loop)}) comes after `self._reached()` (line "
        f"{min(tests)}). The spin → halt → predicate order is what `_spin_until` uses, "
        "and departing from it here gives this file two different answers to 'what "
        "wins when a halt and a milestone land in the same spin' — and credits the "
        "line with a milestone reached on the spin it stopped on"
    )

    helper = _function(tree, "_fail_if_the_line_has_stopped")
    reports = _calls_to(helper, "_context")
    assert reports, (
        f"`_fail_if_the_line_has_stopped` (line {helper.lineno}) never calls "
        "`self._context`; the raise that ends a stopped run would carry one sentence "
        "about whichever wait was in flight and no diagnostic at all"
    )


def test_the_ladder_reaches_the_instance_before_the_first_piece_is_fed(tree) -> None:
    """`self._ladder = ladder`, source-scanned, because nothing else can see it.

    `_context` reads the ladder off the instance — that is the whole of the second
    half of this change — and every test above sets `fake._ladder` itself, so
    deleting the one line that puts it there leaves this file green. In a real run
    the report would print `0 milestone(s)` and no ladder, which is exactly the
    evidence loss the change was made to end.

    Ordered against the feed loop, not merely present: an assignment after the
    pieces have run leaves every failure raised during them with an empty ladder.
    """
    verdict = _function(tree, "test_the_line_carries_every_workpiece_from_pick_to_accumulation")
    assignments = _assignments_to(verdict, "_ladder")
    assert assignments, (
        "the verdict method never assigns `self._ladder`. `_context` reads the ladder "
        "off the instance, so every failure it prints would list 0 milestone(s)"
    )
    runs = _calls_to(verdict, "_run_one_piece")
    assert runs, "the verdict method no longer feeds any piece through `_run_one_piece`"
    assert min(assignments) < min(runs), (
        f"`self._ladder` is assigned at line {min(assignments)}, after the first "
        f"`_run_one_piece` call at line {min(runs)}; a failure raised while a piece is "
        "in flight would carry no ladder, which is the report the incident lost"
    )
