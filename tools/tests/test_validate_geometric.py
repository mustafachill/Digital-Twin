"""Geometric and physical checks, against the real cell model.

These run on `model/` itself rather than a toy, so a change to the cell that
breaks a rule fails here — on a laptop, in a fraction of a second — instead of
at simulation bring-up ten minutes later.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve
from cite_tools.validate import Severity, geometric, physical


def geometric_rules(path: Path, severity: Severity = Severity.ERROR) -> set[str]:
    model = load(path)
    found: set[str] = set()
    for zone in model.zones:
        found |= {
            f.rule for f in geometric.check(resolve(model, zone.id)) if f.severity is severity
        }
    return found


def physical_rules(path: Path, severity: Severity = Severity.ERROR) -> set[str]:
    return {f.rule for f in physical.check(load(path)) if f.severity is severity}


class TestTheRealCellIsSound:
    def test_no_geometric_errors(self, real_model: Path) -> None:
        assert geometric_rules(real_model) == set()

    def test_no_geometric_warnings(self, real_model: Path) -> None:
        # The engineered layout should sit comfortably inside the reach envelope,
        # not scrape past it. If this starts failing, the layout drifted.
        assert geometric_rules(real_model, Severity.WARNING) == set()

    def test_no_physical_errors(self, real_model: Path) -> None:
        assert physical_rules(real_model) == set()

    def test_no_physical_warnings(self, real_model: Path) -> None:
        assert physical_rules(real_model, Severity.WARNING) == set()


class TestReach:
    def test_moving_an_arm_out_of_range_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Push pedestal_1 a metre further from the pick table. The arm on top of
        # it can no longer reach its own station.
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [1.0, -0.35, 0.0]),
        )
        assert "unreachable-station" in geometric_rules(real_model)

    def test_a_marginal_reach_is_warned_about(self, real_model: Path, edit_yaml: Callable) -> None:
        # +0.10 m, not +0.15: table_pick moved 25 mm further out to buy real
        # clearance against pedestal_1, so the warning band moved with it and
        # +0.15 now lands past the reach limit and reports as an error instead.
        # The property under test is unchanged — a reach that is legal but tight
        # is warned about — only the displacement that produces one.
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [0.10, -0.35, 0.0]),
        )
        assert "reach-margin" in geometric_rules(real_model, Severity.WARNING)


class TestLayout:
    def test_an_asset_outside_the_zone_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/instances/conveyors.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [40.0, 0.0, 0.0]),
        )
        assert "outside-zone" in geometric_rules(real_model)

    def test_overlapping_bodies_are_caught(self, real_model: Path, edit_yaml: Callable) -> None:
        # Put conveyor_2 on top of conveyor_1. The physics engine would resolve
        # the penetration on the first step and fling them apart.
        edit_yaml(
            real_model / "assets/instances/conveyors.yaml",
            lambda d: d["assets"][1]["pose"].__setitem__("xyz_m", [1.050, 0.0, 0.0]),
        )
        assert "overlapping-assets" in geometric_rules(real_model)

    def test_a_belt_and_its_sensor_move_together(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The property that makes anchoring worth it: move the belt and the
        # sensor follows, with no second edit and no chance of divergence.
        model = load(real_model)
        before = resolve(model, "cell_a").asset("beam_c1_out")
        assert before is not None

        edit_yaml(
            real_model / "assets/instances/conveyors.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [1.550, 0.0, 0.0]),
        )
        after = resolve(load(real_model), "cell_a").asset("beam_c1_out")
        assert after is not None
        assert round(after.world_pose.xyz_m[0] - before.world_pose.xyz_m[0], 6) == 0.5


class TestInertia:
    def test_impossible_tensor_is_rejected(self, real_model: Path, edit_yaml: Callable) -> None:
        # izz greater than ixx + iyy describes an object that cannot exist. It is
        # positive definite, so only the triangle inequality catches it.
        def mutate(d: dict) -> None:
            inertial = d["asset_type"]["description"]["body"]["inertial"]
            inertial["ixx"] = 0.1
            inertial["iyy"] = 0.1
            inertial["izz"] = 5.0

        edit_yaml(real_model / "assets/types/fixtures/pedestal_600.yaml", mutate)
        assert "inertia-triangle-inequality" in physical_rules(real_model)

    def test_centre_of_mass_outside_the_body_is_rejected(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/fixtures/pedestal_600.yaml",
            lambda d: d["asset_type"]["description"]["body"]["inertial"].__setitem__(
                "com_m", [0.0, 0.0, 2.0]
            ),
        )
        assert "com-outside-geometry" in physical_rules(real_model)

    def test_implausible_density_is_warned_about(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/fixtures/pedestal_600.yaml",
            lambda d: d["asset_type"]["description"]["body"]["inertial"].__setitem__(
                "mass_kg", 40000.0
            ),
        )
        assert "implausible-density" in physical_rules(real_model, Severity.WARNING)

    def test_a_tensor_copied_onto_a_different_sized_body_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The classic placeholder: someone copies a working inertial block to a
        # new part and never recomputes it. L1 names this specifically.
        source = load(real_model).asset_type("pedestal_600")
        assert source is not None and source.description.body is not None
        borrowed = source.description.body.inertial.model_dump()

        edit_yaml(
            real_model / "assets/types/conveyors/belt_1200x400.yaml",
            lambda d: d["asset_type"]["description"]["body"].__setitem__("inertial", borrowed),
        )
        assert "copied-inertia" in physical_rules(real_model)


class TestFramesAndTheirGeometry:
    """The rule that would have caught the conveyor in one second.

    A type whose named frames sit outside its own collision box describes two
    different objects. Nothing reports it: the model validates, the world loads,
    the simulation runs — and a station reaches for a surface that is not there.
    """

    def test_a_frame_above_its_own_body_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Exactly the committed defect: shrink the belt back to a 0.100 m slab and
        # leave its surface, infeed and outfeed frames at z = 0.600.
        def mutate(document: dict) -> None:
            body = document["asset_type"]["description"]["body"]
            body["collision"]["size_m"] = [1.2, 0.4, 0.1]
            body["visual"]["size_m"] = [1.2, 0.4, 0.1]

        edit_yaml(real_model / "assets/types/conveyors/belt_1200x400.yaml", mutate)
        assert "frame-outside-geometry" in geometric_rules(real_model)

    def test_a_frame_beyond_a_body_in_x_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Not only the vertical case: a belt end declared past the end of the belt
        # is the same class of mistake and the same consequence.
        edit_yaml(
            real_model / "assets/types/conveyors/belt_1200x400.yaml",
            lambda d: d["asset_type"]["frames"][1].__setitem__("xyz_m", [-0.9, 0.0, 0.6]),
        )
        assert "frame-outside-geometry" in geometric_rules(real_model)

    def test_a_frame_on_the_top_face_is_accepted(self, real_model: Path) -> None:
        # On the boundary is the normal case — a work surface IS the top face — so
        # the rule must not reject it. The real model is the fixture.
        assert "frame-outside-geometry" not in geometric_rules(real_model)

    def test_a_vendor_link_frame_is_not_judged(self, real_model: Path, edit_yaml: Callable) -> None:
        # `tcp` on the xArm is metres from that type's origin and has no body
        # here at all. Reporting on it would mean inventing an answer about
        # geometry this layer deliberately does not read.
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["frames"][1].__setitem__("xyz_m", [0.0, 0.0, 5.0]),
        )
        assert "frame-outside-geometry" not in geometric_rules(real_model)


class TestApproachCorridors:
    """The reach check asks whether the arm can get there. This asks what is in the way."""

    def test_an_obstruction_above_a_pick_point_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The committed placement: the sensor housing 50 mm back from the outfeed
        # and on the belt centreline, straight through the gripper's descent onto
        # station_transfer_2's pick point.
        edit_yaml(
            real_model / "assets/instances/sensors.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [-0.05, 0.0, 0.08]),
        )
        assert "approach-obstruction" in geometric_rules(real_model)

    def test_the_asset_the_point_sits_on_is_not_reported(self, real_model: Path) -> None:
        # Every pick point lies on a surface by construction, so the body under it
        # is always touching the base of the corridor. Reporting that would make
        # this rule fire at every station and be turned off.
        assert "approach-obstruction" not in geometric_rules(real_model)


class TestClearance:
    """Exact face contact is a layout one micrometre from a penetration."""

    def test_touching_faces_are_warned_about(self, real_model: Path, edit_yaml: Callable) -> None:
        # table_accumulation's near face exactly on conveyor_3's far face. The
        # overlap check uses a strict inequality and calls this "not
        # intersecting", which is true and useless.
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: d["assets"][4]["pose"].__setitem__("xyz_m", [6.15, 0.0, 0.0]),
        )
        assert "insufficient-clearance" in geometric_rules(real_model, Severity.WARNING)

    def test_a_designed_gap_is_accepted(self, real_model: Path) -> None:
        assert "insufficient-clearance" not in geometric_rules(real_model, Severity.WARNING)

    def test_an_asset_placed_on_another_is_still_allowed_to_touch(self, real_model: Path) -> None:
        # A sensor mounted on its conveyor is meant to be in contact with it.
        # Warning about that would be warning about the anchoring the model wants.
        model = load(real_model)
        beam = resolve(model, "cell_a").asset("beam_c1_out")
        assert beam is not None and beam.parent_asset == "conveyor_1"
        assert "insufficient-clearance" not in geometric_rules(real_model, Severity.WARNING)


class TestZoneContainmentUsesExtents:
    """The rule has to check the thing its name promises."""

    def test_a_body_hanging_over_the_boundary_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Origin inside the zone, box reaching past it. The old check tested the
        # origin alone and passed this.
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: d["assets"][4]["pose"].__setitem__("xyz_m", [6.7, 0.0, 0.0]),
        )
        model = load(real_model)
        asset = resolve(model, "cell_a").asset("table_accumulation")
        assert asset is not None
        assert model.zone("cell_a").bounds.max_m[0] > asset.world_pose.xyz_m[0]
        assert "outside-zone" in geometric_rules(real_model)

    def test_a_body_wholly_inside_is_accepted(self, real_model: Path) -> None:
        assert "outside-zone" not in geometric_rules(real_model)
