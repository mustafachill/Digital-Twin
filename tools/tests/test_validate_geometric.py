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
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [0.15, -0.35, 0.0]),
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
