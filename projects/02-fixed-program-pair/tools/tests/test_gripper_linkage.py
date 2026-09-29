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

#: How far proximal of `link_tcp` the centre of the pad face sits, in metres, by
#: drive-joint position. From the grasp-plane campaign's own `harness/geometry.py`,
#: which derived them from the vendor URDF and the parsed pad-face mesh before any
#: trial ran — not from this model's arithmetic played back.
CAMPAIGN_OFFSETS_M = {
    0.0000: 0.029860,
    0.4056: 0.019277,
    0.4528: 0.018581,
}


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


class TestThePadPlaneSitsWhereTheCampaignMeasuredIt:
    """The axial half of the same linkage, pinned against its own campaign.

    `link_tcp` — the link every skill plans to — is the FINGERTIP plane, and the
    pads grip with their faces, which sit proximal of it. The 40-trial interleaved
    campaign in `docs/measurements/2026-08-25-grasp-plane-offset/` measured the
    consequence of ignoring that: the commanded tool pose was 24.4 mm high, 19.3 mm
    of a 37.5 mm pad face was engaged, and the resulting couple rotated the
    work-piece past 20 degrees in 12 of 20 trials. Correcting it: 0 of 20,
    p < 0.0001.

    The numbers below are that campaign's, not this model's arithmetic played
    back: they come from `harness/geometry.py`, which derived them from the vendor
    URDF and the parsed pad-face mesh before any trial ran.
    """

    @pytest.mark.parametrize(("position", "expected_m"), sorted(CAMPAIGN_OFFSETS_M.items()))
    def test_the_offset_matches_the_campaign(self, grasp, position, expected_m) -> None:
        assert grasp.linkage.pad_plane_offset_m(position) == pytest.approx(expected_m, abs=5e-6)

    def test_the_constant_term_is_the_campaigns(self, grasp) -> None:
        """The 0.0718988 m the analysis quotes, derived rather than declared."""
        assert grasp.linkage._axial_reach_m == pytest.approx(0.0718988, abs=5e-7)

    def test_the_offset_is_not_a_constant(self, grasp) -> None:
        """The mistake the deleted `grasp` frame made, kept out by a test.

        That frame declared one number, 0.172 m, and called it the point between
        the pads. Both halves were wrong: 0.172 is the fingertip, and the pad
        centre travels 11.3 mm along the tool axis across the stroke, so no single
        constant is right at more than one width.
        """
        wide = grasp.linkage.pad_plane_offset_m(grasp.open_position)
        narrow = grasp.linkage.pad_plane_offset_m(
            grasp.linkage.position_for(grasp.default_grasp_width_m)
        )
        assert wide - narrow == pytest.approx(0.01128, abs=5e-5)

    def test_correcting_it_puts_the_pad_face_on_the_work_piece(self, grasp) -> None:
        """End to end, in the terms the campaign reported.

        A 50 mm cube resting on a surface has its centre 25 mm up. Planning the
        tip link straight there — which is what `Pick` did — leaves the pad centre
        24.2 mm above the part's centre of mass. Backing the tip link off by this
        offset instead leaves it within a millimetre, with the whole pad face on
        the part.
        """
        stall = grasp.linkage.position_for(WORKPIECE_M)
        uncorrected = grasp.linkage.pad_plane_offset_m(stall)
        assert uncorrected == pytest.approx(0.0193, abs=5e-4)

        commanded = grasp.linkage.pad_plane_offset_m(
            grasp.linkage.position_for(grasp.default_grasp_width_m)
        )
        # Where the pad centre lands, relative to the part's centre of mass, once
        # the tip link is put `commanded` below the object's pose. The residual is
        # the clearance between the commanded width and the part's own, which this
        # layer cannot remove: L0 records no work-piece geometry.
        residual_m = uncorrected - commanded
        assert 0.0 < residual_m < 0.001
