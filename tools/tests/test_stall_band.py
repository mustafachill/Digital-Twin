"""What separates a grasp from a stall on nothing: the band, and where it lives.

ADR-0052, option F. The L3 predicate used to compare the width the jaws reached
against the width they were COMMANDED to, and the command is a policy value while
the error is about where the *part* is. Both directions of that error are
measured — a real grasp reported empty, witnessed by the work-piece's own contact
sensor, and a stall on nothing reported as a grasp. Cite
`docs/measurements/2026-09-01-grasp-discrimination/` for the figures; they are
deliberately not copied into prose here (P1).

This file guards the model half of the remedy, in the shape
`test_gripper_result_timeout.py` uses for ADR-0045's deadline:

* the band is declared on the L0 end-effector type and travels to L3 through the
  generated bring-up plan, so no number for it exists in C++ at all;
* the work-piece interval it is applied to is a FACILITY fact and travels by a
  different route, in the plan's own `plan:` block (ADR-0052 §A.4);
* the validator refuses a band that has stopped discriminating, and refuses a
  grasping facility that states no part width at all;
* and both quantities move when L0 moves, which is what §A.10 item 4 asks for.

The behaviour half — that the predicate reads the interval rather than the
command — is held by `cite_skills/test/test_gripper.cpp` and by
`cite_bringup/test/test_grasp_predicate_launch.py`.

NOTHING HERE SAYS THE DEFECT IS FIXED. ADR-0052 §A.10 item 2's campaign has not
run, and item 5 is explicit that no green run promotes this. What these tests
evidence is the mechanism.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.model.workpieces import workpiece_widths
from cite_tools.validate import Severity, physical

#: The two rules this file is about, plus the one whose reason changed.
ADMITS_NOTHING = "stall-band-admits-a-stall-on-nothing"
NO_PART_WIDTH = "workpiece-width-unstated-for-a-grasping-facility"
NEVER_CLOSES = "default-grasp-width-never-closes"

#: The keys as L0 spells them, and as the generated plan and the skill server
#: spell them. Written once here so that a rename which broke the chain fails a
#: test rather than silently delivering nothing — which is exactly how seven
#: linkage dimensions once travelled nowhere while the node ran on compiled
#: defaults that happened to equal the L0 values.
MODEL_KEYS = ("stall_band_narrow_m", "stall_band_wide_m")
PLAN_KEYS = ("gripper_stall_band_narrow_m", "gripper_stall_band_wide_m")

EFFECTOR = "assets/types/end_effectors/xarm_parallel_gripper.yaml"
WORKPIECE = "assets/types/workpieces/workpiece.yaml"

REPO = Path(__file__).resolve().parents[2]
SKILL_SERVER = REPO / "workspace/src/cite_skills/src/skill_server.cpp"
GRIPPER_CPP = REPO / "workspace/src/cite_skills/src/gripper.cpp"

#: The campaign's committed raw. Reading `docs/measurements/` from a test is
#: acceptable here and nowhere near general: that tree is FROZEN by its own
#: README once a campaign's first trial has run, so these files are as stable as
#: a fixture and rather more honest than one. There is precedent at
#: `tools/tests/test_rtf_figure_conditions.py`, which walks the same tree.
CAMPAIGN = REPO / "docs/measurements/2026-09-01-grasp-discrimination/raw"


def physical_rules(path: Path, severity: Severity) -> set[str]:
    return {f.rule for f in physical.check(load(path)) if f.severity is severity}


def generated(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def plans(path: Path) -> list[dict]:
    documents = [
        yaml.safe_load(content)
        for name, content in generated(path).items()
        if name.endswith("_plan.yaml")
    ]
    assert documents, "the generator emitted no bring-up plan at all"
    return documents


@pytest.fixture
def grasp(real_model: Path):
    effector = load(real_model).asset_type("xarm_parallel_gripper")
    assert effector is not None and effector.grasp is not None
    return effector.grasp


@pytest.fixture
def widths(real_model: Path):
    model = load(real_model)
    return workpiece_widths(model.facility.workpiece_models, model.types)


# --------------------------------------------------------------------------- #
# The floor arithmetic
# --------------------------------------------------------------------------- #


class TestTheFloorArithmetic:
    """The derivation a future reader has to be able to recompute.

    The floor is `default_grasp_width_m` plus the discrimination margin above it:
    the width below which the PREVIOUS, command-referenced predicate already
    declined to call a stall a grasp. Option F moved the reference point from the
    command to the part; it did not buy permission to admit stalls the old
    reference already rejected.
    """

    def test_the_floor_is_the_default_plus_its_discrimination_margin(
        self, real_model: Path, grasp
    ) -> None:
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        margin = physical._grasp_discrimination_margin_m(
            effector, grasp, grasp.default_grasp_width_m
        )
        assert margin is not None
        floor = grasp.default_grasp_width_m + margin
        # ADR-0052 §A.7 quotes 47.138 mm for this cell, and §A.11 records the
        # same figure recomputed independently. Pinned rather than recomputed
        # loosely, because the C++ side pins the identical number in
        # `GripperDiscrimination.MatchesTheValidatorsOwnDerivation` — one policy,
        # two languages, and a drift in either fails one of the two tests.
        assert margin == pytest.approx(0.002137972, abs=1e-9)
        assert floor == pytest.approx(0.047137972, abs=1e-9)

    def test_the_shipped_band_clears_the_floor(self, grasp, widths) -> None:
        """Where the shipped value sits, stated rather than asserted loosely.

        The band's narrow edge opens the window down to `narrowest - band`. That
        has to stay above the floor or the predicate reports a grasp with nothing
        between the pads, which is the defect ADR-0052 exists to close rather
        than to move. The margin is reported in the message so that a future
        reader sees how much room there is without re-deriving it.
        """
        edge = widths.narrowest_m - grasp.stall_band_narrow_m
        assert edge > 0.047137972, (
            f"the window opens to {edge * 1000.0:.3f} mm, at or below the "
            f"47.138 mm the command-referenced bound already refused"
        )

    def test_the_band_is_inside_the_interval_the_record_derives(self, grasp) -> None:
        """ADR-0052 §A.6's two bounds, as bounds and not as a chosen value.

        The narrow edge must EXCEED the largest observed shortfall — below it a
        real grasp reads empty — and must NOT EXCEED the distance from nominal to
        the false-positive flip. Both are cited from the record rather than
        recomputed here; what this asserts is that the shipped value is inside
        them, which is the only claim anyone is entitled to make about it.

        THIS IS NOT A TEST THAT THE VALUE IS RIGHT. The record says in as many
        words that a campaign which cannot resolve 0.1 mm has not placed a value
        inside a 0.99 mm interval, and §A.10 item 2 is what would.
        """
        assert 0.001891 < grasp.stall_band_narrow_m <= 0.002879

    def test_the_wide_edge_carries_no_measurement_and_says_so(self, grasp) -> None:
        """The one thing known about the wide edge: nothing has exercised it.

        No observed grasp stalled above the part's nominal width at all, so the
        data says this edge is not needed to admit any observed grasp and says
        nothing about how large it must be to admit an unobserved one. It is set
        equal to the narrow edge because nothing establishes the shortfall is
        one-sided — a symmetry by default rather than by evidence — and the L0
        comment has to keep saying so.
        """
        assert grasp.stall_band_wide_m == grasp.stall_band_narrow_m
        source = (Path(__file__).resolve().parents[2] / "model" / EFFECTOR).read_text()
        assert "wide has NO measurement behind it" in source, (
            "the L0 declaration no longer records that its wide edge is unevidenced. "
            "A provisional number without its provenance is indistinguishable from a "
            "measured one."
        )


# --------------------------------------------------------------------------- #
# The validator
# --------------------------------------------------------------------------- #


class TestTheValidatorRejectsTheDefect:
    def test_the_real_model_is_clean(self, real_model: Path) -> None:
        assert physical.check(load(real_model)) == []

    def test_a_band_reaching_below_the_floor_is_an_error(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """4 mm on a 50 mm part opens the window to 46.0 mm, below the floor."""
        edit_yaml(
            real_model / EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__("stall_band_narrow_m", 0.004),
        )
        assert ADMITS_NOTHING in physical_rules(real_model, Severity.ERROR)

    def test_a_band_exactly_at_the_floor_is_accepted(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The boundary is inclusive, and the asymmetry with the deadline is real.

        A band whose edge sits exactly on the floor admits precisely the stalls
        the command-referenced bound admitted and no more, so there is nothing to
        refuse. `result_timeout_s`'s floor is exclusive because a deadline equal
        to its floor has to win a race; this is a comparison of two widths and
        there is no race in it.
        """
        edit_yaml(
            real_model / EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__(
                "stall_band_narrow_m", 0.050 - 0.047137972
            ),
        )
        assert ADMITS_NOTHING not in physical_rules(real_model, Severity.ERROR)

    def test_a_second_far_wider_part_fires_the_same_rule(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """§A.5's degradation, made to FIRE rather than to be noticed later.

        F is given the interval of declared part widths and never which part is in
        the jaws, so its discrimination is the width of the admitting window and
        that window widens with the declared spread. Nothing downstream of L0 can
        tell that has happened — every stall in the range simply becomes a grasp.
        This is where it is caught, and the rule's own message has to send the
        reader to §A.5 rather than to a smaller band.
        """
        edit_yaml(
            real_model / WORKPIECE,
            lambda d: d["asset_type"]["description"]["body"]["collision"].__setitem__(
                "size_m", [0.020, 0.020, 0.050]
            ),
        )
        findings = {f.rule: f for f in physical.check(load(real_model))}
        assert ADMITS_NOTHING in findings
        assert "A.5" in findings[ADMITS_NOTHING].hint, (
            "the rule fired without naming the record to reopen, so the reader is "
            "left to conclude the band is too large when the model is the problem"
        )

    def test_a_facility_that_states_no_part_width_is_an_error(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """Under F an unstated width is an unanswerable predicate, not a gap.

        It used to be a documented silence: `None` meant both "this facility
        handles no parts" and "a part nobody has stated the width of", and the
        grasp ceiling simply fell back to its weak bound. Under F there is no
        weaker bound to fall back to — the predicate has no reference at all.
        """
        edit_yaml(
            real_model / "facility/facility.yaml",
            lambda d: d["facility"].__setitem__("workpiece_models", []),
        )
        assert NO_PART_WIDTH in physical_rules(real_model, Severity.ERROR)

    def test_a_mesh_part_is_the_same_error_by_the_other_route(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The second of the two silences that used to be one `None`.

        A mesh work-piece carries its extents in a file L1 owns, so nothing at L0
        can measure across it. That is a legitimate way to describe a part and
        not a legitimate way to acquire a bound.
        """
        edit_yaml(
            real_model / WORKPIECE,
            lambda d: d["asset_type"]["description"]["body"].__setitem__(
                "collision",
                {"kind": "mesh", "uri": "package://cite_description/meshes/part.stl"},
            ),
        )
        assert NO_PART_WIDTH in physical_rules(real_model, Severity.ERROR)

    def test_the_grasp_ceiling_keeps_its_number(self, real_model: Path, grasp) -> None:
        """ADR-0052 §A.7: the ceiling does not move; its reason does.

        Under F the runtime no longer reads the command, so this rule stopped
        being a second derivation of the runtime's band. What remains is that a
        default has to be narrow enough that the close does not end on the
        controller's goal-tolerance branch — which needs ONE tolerance of width,
        and the rule keeps two. Halving it would loosen a ceiling by about a
        millimetre on a question nothing has measured, so the doubled quantity is
        pinned here against exactly that "simplification".
        """
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        tolerance = physical._gripper_goal_tolerance(effector)
        margin = physical._grasp_discrimination_margin_m(
            effector, grasp, grasp.default_grasp_width_m
        )
        position = grasp.linkage.position_for(grasp.default_grasp_width_m)
        towards_closed = 1.0 if grasp.closed_position >= grasp.open_position else -1.0
        one_tolerance = abs(
            grasp.linkage.opening_m(position)
            - grasp.linkage.opening_m(position + towards_closed * tolerance)
        )
        # Strictly greater, and by close to a factor of two: the rule keeps the
        # doubled quantity that the argument it now rests on does not need.
        assert margin > 1.9 * one_tolerance

    def test_a_default_that_ends_on_the_goal_tolerance_branch_is_still_refused(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The ceiling still fires, and on the same number it always did."""
        edit_yaml(
            real_model / EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__("default_grasp_width_m", 0.049),
        )
        assert NEVER_CLOSES in physical_rules(real_model, Severity.ERROR)


# --------------------------------------------------------------------------- #
# One statement, checked (ADR-0052 §A.10 item 4)
# --------------------------------------------------------------------------- #


class TestOneStatementOfThePartsWidth:
    """§A.7's accessor constraint is not met by two functions that happen to agree.

    So the check is behavioural: move the declared work-piece width in L0 and
    require BOTH the generated plan's interval AND the validator's ceiling to
    move with it. Two independent walks of `workpiece_models` would pass every
    test that reads only one of them, and would fail this one the moment they
    disagreed.
    """

    def test_moving_the_declared_width_moves_the_plan_and_the_ceiling_together(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        before = plans(real_model)[0]["plan"]["workpieces"]
        model = load(real_model)
        effector = model.asset_type("xarm_parallel_gripper")
        widths_before = workpiece_widths(model.facility.workpiece_models, model.types)
        margin = physical._grasp_discrimination_margin_m(
            effector, effector.grasp, effector.grasp.default_grasp_width_m
        )
        ceiling_before = widths_before.narrowest_m - margin

        # 44 mm rather than 20: wide enough to move both quantities by a
        # millimetre nobody could read as rounding, and narrow enough that the
        # shipped 45 mm default is genuinely refused afterwards — which is the
        # ceiling half of the statement, observed rather than computed.
        edit_yaml(
            real_model / WORKPIECE,
            lambda d: d["asset_type"]["description"]["body"]["collision"].__setitem__(
                "size_m", [0.044, 0.044, 0.050]
            ),
        )

        after = plans(real_model)[0]["plan"]["workpieces"]
        assert after["narrowest_width_m"] == pytest.approx(0.044)
        assert after["widest_width_m"] == pytest.approx(0.044)
        assert after["narrowest_width_m"] != before["narrowest_width_m"]

        model = load(real_model)
        effector = model.asset_type("xarm_parallel_gripper")
        widths_after = workpiece_widths(model.facility.workpiece_models, model.types)
        margin = physical._grasp_discrimination_margin_m(
            effector, effector.grasp, effector.grasp.default_grasp_width_m
        )
        ceiling_after = widths_after.narrowest_m - margin
        assert ceiling_after < ceiling_before
        assert ceiling_after == pytest.approx(0.044 - margin)

        # And the ceiling is not merely a number that moved: the shipped default
        # is now above it, so the validator refuses the model.
        assert NEVER_CLOSES in physical_rules(real_model, Severity.ERROR)

    def test_the_interval_is_read_through_one_accessor(self) -> None:
        """The structural half, read from source rather than inferred.

        The behavioural test above would still pass if a second walk existed and
        happened to agree today. This asserts that the two call sites the record
        names — `ResolvedCell` on the generator's side and `validate.physical` on
        the validator's — reach `cite_tools.model.workpieces` and do not walk
        `facility.workpiece_models` themselves.
        """
        for module in ("model/resolve.py", "validate/physical.py"):
            source = (REPO / "tools/cite_tools" / module).read_text()
            assert (
                "from cite_tools.model.workpieces import" in source
            ), f"{module} does not read the one accessor"
        physical_source = (REPO / "tools/cite_tools/validate/physical.py").read_text()
        mentions = physical_source.count("facility.workpiece_models")
        assert mentions == 1, (
            f"validate.physical names facility.workpiece_models {mentions} times. One is "
            f"the argument it hands the accessor; more than one means it walks the list "
            f"itself again, which is the second route ADR-0052 §A.7 removed — under "
            f"option F that produces a model validating against one part and a cell "
            f"judging against another."
        )
        assert "workpiece_widths(model.facility.workpiece_models" in physical_source, (
            "the single mention is not the accessor call, so where the interval comes "
            "from is no longer readable from this module"
        )


# --------------------------------------------------------------------------- #
# The values travel to L3 (P1)
# --------------------------------------------------------------------------- #


class TestTheValuesTravelToL3:
    """One declaration, delivered — not a second copy that happens to agree."""

    def test_the_plan_carries_the_band_for_every_arm_with_a_gripper(self, real_model: Path) -> None:
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        declared = {
            "gripper_stall_band_narrow_m": effector.grasp.stall_band_narrow_m,
            "gripper_stall_band_wide_m": effector.grasp.stall_band_wide_m,
        }
        carried = 0
        for document in plans(real_model):
            for manager in document["plan"]["controller_managers"]:
                if not manager.get("gripper_action"):
                    continue
                for key, value in declared.items():
                    assert key in manager, (
                        f"{manager['asset']} has a gripper and the plan does not tell "
                        f"its skill server what separates a grasp from a stall on "
                        f"nothing. An undelivered parameter is accepted by launch, "
                        f"dropped by rclcpp and reported by neither"
                    )
                    assert manager[key] == pytest.approx(value)
                carried += 1
        assert carried >= 1, "no arm in the generated plan has a gripper at all"

    def test_the_plan_states_the_part_interval_once_per_zone(self, real_model: Path) -> None:
        """§A.4: the interval is a facility fact and does NOT ride the gripper block.

        Every key on a controller manager's gripper block is sourced from the
        end-effector type. A work-piece width is not a property of an end
        effector, and putting it there is how a name stops meaning anything —
        which is the reason `ARM_KEYS` is a separate tuple from `GRIPPER_KEYS`.
        """
        model = load(real_model)
        expected = workpiece_widths(model.facility.workpiece_models, model.types)
        for document in plans(real_model):
            block = document["plan"]["workpieces"]
            assert block["narrowest_width_m"] == pytest.approx(expected.narrowest_m)
            assert block["widest_width_m"] == pytest.approx(expected.widest_m)
            for manager in document["plan"]["controller_managers"]:
                assert not [k for k in manager if "workpiece" in k], (
                    f"{manager['asset']}'s gripper block carries a work-piece width. "
                    f"It is a fact about the facility, stated once per zone"
                )

    def test_no_band_is_compiled_into_the_skill_server(self) -> None:
        """ADR-0052's values are L0's, so no number for them exists in C++.

        The parameters' compiled defaults are zero — sentinels meaning "not
        supplied", against which the node refuses to configure. A default equal
        to the L0 value would be the second copy P1 forbids: it would work, and
        it would work only for as long as the two copies agreed, which is exactly
        how `gripper_default_grasp_width_m` and seven linkage dimensions once
        travelled nowhere unnoticed.
        """
        source = SKILL_SERVER.read_text()
        for key in (*PLAN_KEYS, "workpiece_narrowest_width_m", "workpiece_widest_width_m"):
            assert f'declare_parameter("{key}", 0.0)' in source, (
                f"{key} is either undeclared — in which case a delivered value is "
                f"dropped silently — or declared with a compiled number, which is a "
                f"second home for an L0 value"
            )
        gripper = GRIPPER_CPP.read_text()
        assert "0.002385" not in gripper and "0.002385" not in source, (
            "the shipped band appears as a literal in C++. It is declared in L0 and "
            "delivered by the plan; a copy here would be a second place to be wrong"
        )

    def test_the_predicate_no_longer_reads_the_commanded_width(self) -> None:
        """Option F's central claim, read from the source it is about.

        `commanded_width_m` stays on `GripperReport` so that
        `describe_empty_grasp` can print what was asked for. What must not
        survive is any use of it inside the decision.
        """
        body = _without_comments(GRIPPER_CPP.read_text())
        start = body.index("bool gripper_is_holding(")
        assert "commanded_width_m" not in body[start:], (
            "gripper_is_holding still reads the commanded width. The command is a "
            "policy value and the error is about where the part is — which is the "
            "whole of ADR-0052's decision"
        )


# --------------------------------------------------------------------------- #
# The re-analysis (ADR-0052 §A.10 item 1)
# --------------------------------------------------------------------------- #
#
# The gate the implementing change has to pass, as a COMMITTED TEST rather than a
# one-shot script, so that the gate becomes a permanent regression guard: a
# future edit to the band or to the linkage is measured against the same trials.
#
# The campaign's committed raw already carries F's exact inputs — `q_at_stall_rad`
# for each false-negative trial and `reached_position_rad` for each false-positive
# one. Both predicates are evaluated here through the shipped closed forms.
#
# WHAT THIS IS NOT. It is a RE-READING of trials taken for a different question,
# not a campaign, and it says nothing about any run of the implemented predicate.
# ADR-0052 §A.10 item 2 is the campaign, and it has not run.
# --------------------------------------------------------------------------- #


def _without_comments(source: str) -> str:
    """Drop `//` line comments, so a source check reads code rather than prose.

    `test_gripper_result_timeout.py` records the weakness this avoids: its
    equivalent check exempts one comment by matching its exact text, so rewording
    that comment fails the test for a reason unrelated to the constant. Stripping
    line comments instead means the comment beside `gripper_is_holding` — which
    says in as many words that the commanded width is NOT read — does not itself
    trip the assertion that it is not read.

    Line comments only. This module has no block comments and no string literal
    containing `//`, and a real parse is not worth building for one assertion.
    """
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))


def _closed_forms(grasp):
    """The shipped width map and the shipped predicates, as plain functions.

    Built from the L0 declaration rather than from constants written here, so the
    re-analysis is evaluated against whatever this repository currently ships. A
    change to the linkage moves these with it.
    """
    linkage = grasp.linkage
    pivot = linkage.drive_pivot_y_m - linkage.pad_inset_m
    crank = math.hypot(linkage.finger_offset_y_m, linkage.finger_offset_z_m)
    phase = math.atan2(linkage.finger_offset_z_m, linkage.finger_offset_y_m)

    def width(q: float) -> float:
        return 2.0 * (pivot + crank * math.cos(q + phase))

    def tolerance(q: float, goal_tolerance: float) -> float:
        return abs(2.0 * crank * math.sin(q + phase) * goal_tolerance)

    return width, tolerance


@pytest.fixture
def campaign_trials():
    """The campaign's committed raw, split into its two arms.

    VALIDITY IS APPLIED HERE AND IS NARROWER THAN THE CAMPAIGN'S OWN. This keeps
    only "the trial ran and the instrument witnessed what it was meant to":
    finger contact on the false-negative side, and the synthetic stop actually
    engaging on the false-positive side with the controls excluded. The campaign
    applies further pre-registered rules of its own, so its denominators are
    smaller by one trial in each arm. That difference is stated rather than
    hidden, and the counts below are this file's, not the campaign's.
    """
    false_negative = []
    for name in ("FN_B1_trials.json", "FN_B2_trials.json"):
        false_negative += json.loads((CAMPAIGN / name).read_text())
    false_positive = json.loads((CAMPAIGN / "FP_trials.json").read_text())
    return (
        [t for t in false_negative if t["ok"] and t.get("finger_contact_points_max", 0) > 0],
        [t for t in false_positive if t["ok"] and t["condition"] == "FP" and t["stop_announced"]],
    )


class TestTheReanalysisGate:
    def test_the_campaigns_raw_is_where_it_is_expected(self, campaign_trials) -> None:
        """A gate whose input has moved must fail rather than pass vacuously.

        The measurement tree is frozen by its own README, so these counts are
        stable. Asserting them means a file that was renamed, truncated or
        re-filtered is caught here instead of silently reducing this gate to a
        test over an empty list — which is the failure mode ADR-0051's rule S was
        written about.
        """
        false_negative, false_positive = campaign_trials
        assert len(false_negative) == 32
        assert len(false_positive) == 34

    def test_every_valid_false_negative_trial_is_admitted(
        self, real_model: Path, campaign_trials
    ) -> None:
        """§A.10 item 1, first half. A band that fails this is not landed.

        Every one of these trials is a REAL grasp — the work-piece's own contact
        sensor witnessed the fingers on it — so a predicate that reports any of
        them empty is reporting a part it is holding as air. The
        commanded-width predicate reports several of them empty, which is the
        false negative ADR-0052 records as OBSERVED.
        """
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        grasp = effector.grasp
        model = load(real_model)
        parts = workpiece_widths(model.facility.workpiece_models, model.types)
        width, _ = _closed_forms(grasp)

        low = parts.narrowest_m - grasp.stall_band_narrow_m
        high = parts.widest_m + grasp.stall_band_wide_m
        rejected = [
            (t["label"], t["trial"], width(t["q_at_stall_rad"]))
            for t in campaign_trials[0]
            if not (low < width(t["q_at_stall_rad"]) < high)
        ]
        assert not rejected, (
            f"the landed band reports {len(rejected)} witnessed grasp(s) as empty: "
            f"{rejected}. The window is [{low * 1000.0:.3f}, {high * 1000.0:.3f}] mm. "
            f"A band that fails this is not landed (ADR-0052 §A.10 item 1)."
        )

    def test_it_recovers_grasps_the_commanded_width_predicate_reported_empty(
        self, real_model: Path, campaign_trials
    ) -> None:
        """The improvement, measured on the same data with no new constant chosen.

        Only the reference point moved. Asserted as a strict inequality rather
        than as two counts, so that this records the DIRECTION of the change and
        does not become a test that has to be edited whenever the campaign's raw
        is extended.
        """
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        grasp = effector.grasp
        model = load(real_model)
        parts = workpiece_widths(model.facility.workpiece_models, model.types)
        width, tolerance = _closed_forms(grasp)
        goal_tolerance = physical._gripper_goal_tolerance(effector)

        low = parts.narrowest_m - grasp.stall_band_narrow_m
        high = parts.widest_m + grasp.stall_band_wide_m
        under_f = sum(1 for t in campaign_trials[0] if low < width(t["q_at_stall_rad"]) < high)
        under_command = sum(
            1
            for t in campaign_trials[0]
            if width(t["q_at_stall_rad"]) - t["commanded_width_m"]
            > 2.0 * tolerance(t["q_at_stall_rad"], goal_tolerance)
        )
        assert under_f == len(campaign_trials[0])
        assert under_f > under_command, (
            f"F admits {under_f} of {len(campaign_trials[0])} witnessed grasps and the "
            f"commanded-width predicate admits {under_command}; F is supposed to recover "
            f"the difference, and here it recovers none"
        )

    def test_f_admits_no_false_positive_the_old_predicate_would_not_have(
        self, real_model: Path, campaign_trials
    ) -> None:
        """§A.10 item 1, second half — the SUBSET property, which is the real gate.

        The false-positive arm is a synthetic stop at a declared position with
        nothing between the pads, so every trial it admits is a stall on nothing
        reported as a grasp. The floor ADR-0052 derives is a measurement on one
        machine, at one timestep, with one part, on one arm, and it is good for
        exactly one thing: F's admitting set at the shipped default command must
        be a SUBSET of the commanded-width predicate's, so that F cannot
        introduce a false positive today's predicate would not also have
        produced. A band that fails this is not landed.

        A subset and not a smaller count. Nine of eighteen that were a different
        nine would be a new failure mode wearing an improved number.
        """
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        grasp = effector.grasp
        model = load(real_model)
        parts = workpiece_widths(model.facility.workpiece_models, model.types)
        width, tolerance = _closed_forms(grasp)
        goal_tolerance = physical._gripper_goal_tolerance(effector)

        low = parts.narrowest_m - grasp.stall_band_narrow_m
        high = parts.widest_m + grasp.stall_band_wide_m
        at_default = [
            t
            for t in campaign_trials[1]
            if t["commanded_width_m"] == pytest.approx(grasp.default_grasp_width_m)
        ]
        assert at_default, (
            "no false-positive trial ran at the shipped default command, so this gate "
            "has nothing to test and its silence may not be read as a pass"
        )

        under_f = {t["trial"] for t in at_default if low < width(t["reached_position_rad"]) < high}
        under_command = {
            t["trial"]
            for t in at_default
            if width(t["reached_position_rad"]) - t["commanded_width_m"]
            > 2.0 * tolerance(t["reached_position_rad"], goal_tolerance)
        }
        assert under_f <= under_command, (
            f"F reports {sorted(under_f - under_command)} as grasps on empty jaws where "
            f"the commanded-width predicate did not. F may improve on the old predicate "
            f"and may not introduce a failure it did not have (ADR-0052 §A.10 item 1)."
        )
        assert len(under_f) < len(under_command), (
            f"F admits {len(under_f)} stalls on nothing against the old predicate's "
            f"{len(under_command)}; the subset holds but nothing improved, which the "
            f"record's own re-reading of this raw says should not be the case"
        )
