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

"""The conjunction, and the arithmetic behind the gate that is always shut.

The load-bearing test in this file is
`test_valid_is_false_for_exactly_one_reason_today`. It does not merely assert
that `valid` is false — an assertion like that passes for any reason at all,
including a bug — it names WHICH conjunct fails, so a change that makes `valid`
true has to confront that term rather than slip past a boolean.

**Do not answer a failure here by weakening a term.** ADR-0050: if the
conjunction is unsatisfiable in a way that record did not anticipate, that is a
finding to report.
"""

from __future__ import annotations

from cite_interfaces.msg import TwinMode
from cite_twin.divergence import (
    assess,
    compare,
    DEFICIT_BOUND_S,
    MODES_THAT_DEFINE_THE_COMPARISON,
    Operand,
    PAIRING_WINDOW_S,
)
import pytest

DECLARED_MODES = [getattr(TwinMode, name) for name in dir(TwinMode) if name.startswith("MODE_")]

MODEL = "b8f0c2"


def operand(
    positions: dict[str, float] | None = None,
    received_wall_s: float = 1000.0,
    model_version: str = MODEL,
    clock_deficit_s: float | None = None,
) -> Operand:
    return Operand(
        positions={"arm_1_joint1": 0.0} if positions is None else positions,
        received_wall_s=received_wall_s,
        model_version=model_version,
        clock_deficit_s=clock_deficit_s,
    )


class TestTheGateIsStructurallyShut:
    def test_the_deficit_bound_is_unset_and_that_is_the_decision(self) -> None:
        """Keep the deficit bound unset, because that is the decision.

        ADR-0049 decision 2 refuses to set it: naming a figure now would be
        deciding what a campaign will find. `None` is therefore not a missing
        value waiting to be filled in by whoever wants a green sample.

        If this ever becomes a number, ADR-0049's decision was overridden and
        the record has to say so.
        """
        assert DEFICIT_BOUND_S is None

    @pytest.mark.parametrize("mode", DECLARED_MODES)
    def test_valid_is_false_in_every_mode(self, mode: int) -> None:
        """Every operand present, paired, agreeing, both sides simulated."""
        conditions = assess(mode, operand(), operand(), far_side_physical=False)
        assert not conditions.valid

    def test_valid_is_false_for_exactly_one_reason_today(self) -> None:
        """In VALIDATED, with everything else satisfied, term 3 is the only failure.

        This is the shape of the deliverable: the monitor publishes a
        self-describing invalid sample, and the term it names is the one with no
        instrument. Four of the five conjuncts hold — so a change that made
        `valid` true would have to be a change to term 3, which is
        ADR-0049 decision 5's instrument and decision 1's bound.
        """
        conditions = assess(
            TwinMode.MODE_VALIDATED, operand(), operand(), far_side_physical=False
        )
        assert conditions.failed_terms() == ("clock_deficit_within_bound",)

    def test_term_three_fails_for_two_independent_reasons(self) -> None:
        """The bound is unset AND neither side's deficit is measured.

        Both are checked, so closing one does not silently turn the term true on
        the strength of the other.
        """
        measured = assess(
            TwinMode.MODE_VALIDATED,
            operand(clock_deficit_s=0.001),
            operand(clock_deficit_s=0.001),
            far_side_physical=False,
            deficit_bound_s=None,
        )
        bounded = assess(
            TwinMode.MODE_VALIDATED,
            operand(),
            operand(),
            far_side_physical=False,
            deficit_bound_s=0.5,
        )
        assert not measured.clock_deficit_within_bound
        assert not bounded.clock_deficit_within_bound

    def test_a_sample_can_be_valid_once_both_halves_of_term_three_exist(self) -> None:
        """Not a claim that anything measures this — the instrument does not exist.

        It is the proof that the conjunction is satisfiable in principle, so
        that "valid is always false" is a statement about the tree rather than
        about the arithmetic.
        """
        conditions = assess(
            TwinMode.MODE_VALIDATED,
            operand(clock_deficit_s=0.01),
            operand(clock_deficit_s=0.02),
            far_side_physical=False,
            deficit_bound_s=0.1,
        )
        assert conditions.valid


class TestTermOneTheMode:
    def test_only_validated_defines_the_comparison(self) -> None:
        assert MODES_THAT_DEFINE_THE_COMPARISON == frozenset({TwinMode.MODE_VALIDATED})

    def test_shadow_does_not_define_it(self) -> None:
        """Against `DivergenceMetrics.msg`'s superseded header.

        In SHADOW the virtual side's state is DERIVED from the physical side's,
        so the comparison measures the mirror and the follower's own tracking
        law rather than the model. ADR-0011's level table puts Shadow at L1 and
        "divergence measured" one row down at L2 Validated.
        """
        conditions = assess(
            TwinMode.MODE_SHADOW, operand(), operand(), far_side_physical=False
        )
        assert not conditions.mode_defines_the_comparison

    def test_virtual_lead_does_not_define_it_either(self) -> None:
        assert not assess(
            TwinMode.MODE_VIRTUAL_LEAD, operand(), operand(), far_side_physical=False
        ).mode_defines_the_comparison


class TestTermTwoThePairing:
    def test_two_operands_inside_the_window_pair(self) -> None:
        conditions = assess(
            TwinMode.MODE_VALIDATED,
            operand(received_wall_s=1000.0),
            operand(received_wall_s=1000.0 + PAIRING_WINDOW_S / 2),
            far_side_physical=False,
        )
        assert conditions.operands_paired_in_window

    def test_two_operands_outside_the_window_do_not(self) -> None:
        conditions = assess(
            TwinMode.MODE_VALIDATED,
            operand(received_wall_s=1000.0),
            operand(received_wall_s=1000.0 + PAIRING_WINDOW_S * 2),
            far_side_physical=False,
        )
        assert not conditions.operands_paired_in_window

    @pytest.mark.parametrize("missing", ["plant", "counterpart"])
    def test_a_missing_operand_is_not_a_pair(self, missing: str) -> None:
        conditions = assess(
            TwinMode.MODE_VALIDATED,
            None if missing == "plant" else operand(),
            None if missing == "counterpart" else operand(),
            far_side_physical=False,
        )
        assert not conditions.operands_paired_in_window


class TestTermFourTheModelVersion:
    def test_two_different_models_are_not_comparable(self) -> None:
        conditions = assess(
            TwinMode.MODE_VALIDATED,
            operand(model_version="aaa"),
            operand(model_version="bbb"),
            far_side_physical=False,
        )
        assert not conditions.model_versions_agree

    def test_an_unreported_model_version_is_not_agreement(self) -> None:
        """Two sides that have both said nothing have not agreed about anything."""
        conditions = assess(
            TwinMode.MODE_VALIDATED,
            operand(model_version=""),
            operand(model_version=""),
            far_side_physical=False,
        )
        assert not conditions.model_versions_agree


class TestTermFiveTheFrames:
    def test_two_simulated_sides_correspond_by_identity(self) -> None:
        """Both generated from one L0 model, so the correspondence is identity."""
        assert assess(
            TwinMode.MODE_VALIDATED, operand(), operand(), far_side_physical=False
        ).frames_correspond

    def test_a_physical_far_side_needs_a_registration_that_does_not_exist(self) -> None:
        """It stops being trivial in 2.B, where it is the registration transform.

        Every asset instance in L0 carries a `registration` block reading
        `unregistered`, and charter §8 puts the survey in Phase 3.
        """
        assert not assess(
            TwinMode.MODE_VALIDATED, operand(), operand(), far_side_physical=True
        ).frames_correspond


class TestTheComparison:
    def test_the_arithmetic_over_the_joints_both_sides_report(self) -> None:
        plant = operand(positions={"a": 0.0, "b": 0.0, "c": 0.0})
        counterpart = operand(positions={"a": 0.3, "b": -0.4, "c": 0.0})
        result = compare(plant, counterpart)
        assert result.joints == ("a", "b", "c")
        assert result.joint_error_max_rad == pytest.approx(0.4)
        assert result.joint_error_rms_rad == pytest.approx(
            ((0.3**2 + 0.4**2 + 0.0) / 3) ** 0.5
        )

    def test_a_joint_only_one_side_reports_is_not_an_error_of_any_size(self) -> None:
        plant = operand(positions={"a": 0.0, "only_here": 5.0})
        counterpart = operand(positions={"a": 0.1})
        result = compare(plant, counterpart)
        assert result.joints == ("a",)
        assert result.joint_error_max_rad == pytest.approx(0.1)

    def test_no_common_joint_is_zero_rather_than_an_exception(self) -> None:
        result = compare(operand(positions={"a": 1.0}), operand(positions={"b": 2.0}))
        assert result.joints == ()
        assert result.joint_error_rms_rad == 0.0

    @pytest.mark.parametrize("missing", ["plant", "counterpart"])
    def test_a_missing_operand_compares_to_zero(self, missing: str) -> None:
        result = compare(
            None if missing == "plant" else operand(),
            None if missing == "counterpart" else operand(),
        )
        assert result == compare(None, None)

    def test_the_comparison_is_computed_even_when_the_sample_is_invalid(self) -> None:
        """The arithmetic runs on every cycle rather than behind a shut gate.

        A gate that is always closed hides a rotting implementation behind it,
        which is exactly what would happen if `compare` were only called when
        `valid` were true — and it is never true today.
        """
        conditions = assess(
            TwinMode.MODE_SIM, operand(), operand(positions={"arm_1_joint1": 0.5}),
            far_side_physical=False,
        )
        result = compare(operand(), operand(positions={"arm_1_joint1": 0.5}))
        assert not conditions.valid
        assert result.joint_error_max_rad == pytest.approx(0.5)
