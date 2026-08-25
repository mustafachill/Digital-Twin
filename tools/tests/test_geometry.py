"""Pose composition. A sign or order error here misplaces the whole cell."""

from __future__ import annotations

import math

import pytest

from cite_tools.model.geometry import Aabb, Pose

HALF_PI = math.pi / 2


class TestRoundTrip:
    @pytest.mark.parametrize(
        "rpy",
        [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, HALF_PI),
            (0.1, -0.2, 0.3),
            (math.pi, 0.0, 0.0),
            (-0.4, 0.5, -1.2),
        ],
    )
    def test_matrix_round_trip(self, rpy: tuple[float, float, float]) -> None:
        p = Pose(xyz_m=(1.0, -2.0, 0.5), rpy_rad=rpy)
        assert p.approx_equal(Pose.from_matrix(p.to_matrix()))

    def test_inverse_cancels(self) -> None:
        p = Pose(xyz_m=(1.0, 2.0, 3.0), rpy_rad=(0.3, -0.2, 1.1))
        assert p.compose(p.inverse()).approx_equal(Pose.identity())


class TestComposition:
    def test_translation_only(self) -> None:
        parent = Pose(xyz_m=(1.0, 0.0, 0.0))
        child = Pose(xyz_m=(0.0, 2.0, 0.0))
        assert parent.compose(child).approx_equal(Pose(xyz_m=(1.0, 2.0, 0.0)))

    def test_child_translation_is_expressed_in_the_parent_frame(self) -> None:
        # The parent is yawed 90 degrees, so the child's +x becomes the parent's +y.
        # This is the test that catches a reversed composition order: with the
        # operands swapped the result would be (1, 1, 0).
        parent = Pose(xyz_m=(0.0, 1.0, 0.0), rpy_rad=(0.0, 0.0, HALF_PI))
        child = Pose(xyz_m=(1.0, 0.0, 0.0))
        assert parent.compose(child).approx_equal(
            Pose(xyz_m=(0.0, 2.0, 0.0), rpy_rad=(0.0, 0.0, HALF_PI))
        )

    def test_composition_is_not_commutative(self) -> None:
        # b must translate in a plane the rotation actually affects: a pure z
        # translation commutes with a yaw, so it would prove nothing.
        a = Pose(xyz_m=(1.0, 0.0, 0.0), rpy_rad=(0.0, 0.0, HALF_PI))
        b = Pose(xyz_m=(0.0, 1.0, 0.0))
        assert a.compose(b).approx_equal(Pose(xyz_m=(0.0, 0.0, 0.0), rpy_rad=(0.0, 0.0, HALF_PI)))
        assert b.compose(a).approx_equal(Pose(xyz_m=(1.0, 1.0, 0.0), rpy_rad=(0.0, 0.0, HALF_PI)))

    def test_arm_on_a_pedestal(self) -> None:
        # The engineered layout: pedestal at y = -0.35, 0.6 m tall, arm on top
        # yawed to face +y. The arm base must land at (0, -0.35, 0.6).
        pedestal_top = Pose(xyz_m=(0.0, -0.35, 0.6))
        arm = Pose(rpy_rad=(0.0, 0.0, HALF_PI))
        placed = pedestal_top.compose(arm)
        assert placed.approx_equal(Pose(xyz_m=(0.0, -0.35, 0.6), rpy_rad=(0.0, 0.0, HALF_PI)))


class TestCalibrationCorrection:
    def test_correction_is_applied_in_the_body_frame(self) -> None:
        # An asset yawed 90 degrees, measured 10 mm further along its OWN x.
        # In world terms that is +y, not +x. A world-frame correction would be
        # the classic sign/axis error this convention exists to prevent.
        nominal = Pose(xyz_m=(1.0, 1.0, 0.0), rpy_rad=(0.0, 0.0, HALF_PI))
        correction = Pose(xyz_m=(0.010, 0.0, 0.0))
        assert nominal.corrected_by(correction).approx_equal(
            Pose(xyz_m=(1.0, 1.010, 0.0), rpy_rad=(0.0, 0.0, HALF_PI))
        )

    def test_identity_correction_changes_nothing(self) -> None:
        p = Pose(xyz_m=(2.0, 3.0, 1.0), rpy_rad=(0.0, 0.0, 0.7))
        assert p.corrected_by(Pose.identity()).approx_equal(p)


class TestDeterminism:
    def test_same_input_gives_bit_identical_output(self) -> None:
        parent = Pose(xyz_m=(1.05, 0.0, 0.6), rpy_rad=(0.0, 0.0, HALF_PI))
        child = Pose(xyz_m=(0.6, 0.0, 0.0))
        results = {parent.compose(child) for _ in range(50)}
        assert len(results) == 1


class TestAabb:
    def test_contains(self) -> None:
        box = Aabb(min_m=(-1.0, -1.2, 0.0), max_m=(6.8, 0.8, 2.5))
        assert box.contains((0.0, -0.35, 0.6))
        assert not box.contains((7.0, 0.0, 0.6))

    def test_intersects(self) -> None:
        a = Aabb(min_m=(0.0, 0.0, 0.0), max_m=(1.0, 1.0, 1.0))
        assert a.intersects(Aabb(min_m=(0.5, 0.5, 0.5), max_m=(2.0, 2.0, 2.0)))
        assert not a.intersects(Aabb(min_m=(1.5, 0.0, 0.0), max_m=(2.0, 1.0, 1.0)))

    def test_touching_boxes_do_not_count_as_overlapping(self) -> None:
        # Two conveyors placed end to end share a face. That is a layout, not a
        # collision, and reporting it would make the overlap check useless noise.
        a = Aabb(min_m=(0.0, 0.0, 0.0), max_m=(1.0, 1.0, 1.0))
        assert not a.intersects(Aabb(min_m=(1.0, 0.0, 0.0), max_m=(2.0, 1.0, 1.0)))

    def test_inverted_bounds_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="inverted"):
            Aabb(min_m=(1.0, 0.0, 0.0), max_m=(0.0, 1.0, 1.0))
