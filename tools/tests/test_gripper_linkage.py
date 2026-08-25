"""The gripper's width map, pinned against measurement.

This map spent the whole of Phase 1.C wrong and silent. It was a linear
interpolation of the drive joint's stroke, which is not what a four-bar linkage
does: it read 85.00 mm fully open against a true 88.93 mm, and — the error that
mattered — 45.00 mm at q=0.400 rad against a true 50.59 mm. The cell's reference
work-piece is a 50 mm cube, so the default grasp was commanding the pads to a
width *wider than the part*, closing on air, and reporting success at it.

The numbers below are not this module's own arithmetic played back. They are the
openings a debugger measured from the simulator, and the confirmation is that the
map predicts a 50 mm part is met at q = 0.4056 rad while the measured settled
`drive_joint` on a 50 mm part is 0.4056 — geometry and simulator agreeing to four
decimals. A test that only checked `opening(position_for(w)) == w` would pass
just as happily against the linear map that caused all of this, because a wrong
map is still its own inverse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cite_tools.model.loader import load

#: Openings measured from the simulator, in metres, by drive-joint position.
#: Source: the collision mesh of `left_finger.stl`, whose pad face is 26.0 mm
#: inboard of the link origin, cross-checked against the settled joint state.
MEASURED_OPENINGS_M = {
    0.000: 0.08893,
    0.300: 0.06092,
    0.400: 0.05059,
    0.850: 0.00165,
}

#: The drive-joint position at which the pads meet a 50 mm work-piece. Measured
#: identically across six simulator runs; the map has to reproduce it.
WORKPIECE_M = 0.050
MEASURED_STALL_POSITION_RAD = 0.4056


@pytest.fixture
def grasp(real_model: Path):
    effector = load(real_model).asset_type("xarm_parallel_gripper")
    assert effector is not None and effector.grasp is not None
    return effector.grasp


class TestTheMapMatchesTheMechanism:
    @pytest.mark.parametrize(("position", "expected_m"), sorted(MEASURED_OPENINGS_M.items()))
    def test_opening_matches_the_measured_stroke(self, grasp, position, expected_m) -> None:
        assert grasp.linkage.opening_m(position) == pytest.approx(expected_m, abs=5e-5)

    def test_a_50_mm_part_is_met_where_the_simulator_meets_it(self, grasp) -> None:
        """The single strongest evidence that this map is the real one."""
        assert grasp.linkage.position_for(WORKPIECE_M) == pytest.approx(
            MEASURED_STALL_POSITION_RAD, abs=1e-4
        )

    def test_the_map_is_not_the_linear_approximation_it_replaced(self, grasp) -> None:
        """Guard against a well-meaning 'simplification' back to a straight line.

        The linear map is the obvious thing to write and reads plausibly at both
        ends of the stroke, so it will be proposed again. Restated here exactly as
        it was — a 0.085 m declared maximum interpolated across the stroke — so
        that the failure is concrete rather than a warning in a comment.

        At the one position the default grasp actually used, the two maps differ
        by 5.6 mm. A 50 mm part sits in a gripper whose useful clearance is a
        couple of millimetres, so that gap is not a refinement; it is the whole
        difference between grasping the work-piece and closing beside it.
        """
        historical_declared_max_m = 0.085
        stroke = grasp.closed_position - grasp.open_position
        linear_at_0_4 = historical_declared_max_m * (1.0 - (0.400 - grasp.open_position) / stroke)

        assert linear_at_0_4 == pytest.approx(0.045, abs=1e-4)
        assert grasp.linkage.opening_m(0.400) == pytest.approx(0.05059, abs=5e-5)
        assert grasp.linkage.opening_m(0.400) - linear_at_0_4 == pytest.approx(0.0056, abs=2e-4)


class TestDerivedWidths:
    def test_max_width_is_the_opening_at_open_position(self, grasp) -> None:
        # 88.93 mm, not the 85.00 mm that used to be declared beside it. The
        # declaration is gone precisely so the two cannot disagree again (P1).
        assert grasp.max_width_m == pytest.approx(0.08893, abs=5e-5)

    def test_min_width_is_the_opening_at_closed_position(self, grasp) -> None:
        assert grasp.min_width_m == pytest.approx(0.00165, abs=5e-5)

    def test_position_for_inverts_opening_across_the_stroke(self, grasp) -> None:
        for tenth in range(11):
            position = grasp.open_position + tenth / 10.0 * (
                grasp.closed_position - grasp.open_position
            )
            width = grasp.linkage.opening_m(position)
            assert grasp.linkage.position_for(width) == pytest.approx(position, abs=1e-9)

    def test_an_unreachable_width_saturates_rather_than_returning_nan(self, grasp) -> None:
        # `acos` of anything outside [-1, 1] is NaN, and a NaN reaching a joint
        # command is far worse than a saturated one.
        assert grasp.linkage.position_for(10.0) == pytest.approx(-grasp.linkage._phase_rad)
        assert grasp.linkage.position_for(-10.0) > 0.0


class TestTheDefaultGraspActuallySqueezes:
    """What the default width buys, in the terms the skill server judges it on.

    The value is 45 mm and was 45 mm before the map was corrected, which makes it
    exactly the kind of number someone will assume was already checked. It was
    not: under the linear map it commanded 0.400 rad and opened the pads to
    50.59 mm, giving 0.3 mm of clearance per side on a 50 mm part.
    """

    def test_the_default_is_narrower_than_the_work_piece(self, grasp) -> None:
        assert grasp.default_grasp_width_m < WORKPIECE_M

    def test_the_part_stops_the_joint_well_short_of_the_command(self, grasp) -> None:
        commanded = grasp.linkage.position_for(grasp.default_grasp_width_m)
        stalled_at = grasp.linkage.position_for(WORKPIECE_M)
        # Unrelieved error at the drive joint, which is what makes the stall
        # unambiguous rather than marginal: ~0.047 rad against a 0.01 rad
        # goal_tolerance.
        assert commanded - stalled_at == pytest.approx(0.0472, abs=5e-4)

    def test_the_width_margin_clears_the_controller_bias(self, grasp) -> None:
        """5.00 mm of real margin against a ~2.11 mm discrimination threshold."""
        margin = (
            grasp.linkage.opening_m(grasp.linkage.position_for(WORKPIECE_M))
            - grasp.default_grasp_width_m
        )
        assert margin == pytest.approx(0.005, abs=1e-4)
