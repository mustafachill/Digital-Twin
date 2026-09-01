"""Geometric and physical checks, against the real cell model.

These run on `model/` itself rather than a toy, so a change to the cell that
breaks a rule fails here — on a laptop, in a fraction of a second — instead of
at simulation bring-up ten minutes later.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

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
        """Back to an empty set, and the round trip is worth stating.

        This assertion read `== set()` until 2026-08-31, when the collision
        declaration ADR-0028 added made `collision-reuses-visual-mesh` reach a
        vendor description for the first time and the shipped model started
        carrying it — a warning the project had decided to carry, written as an
        exact set so that a SECOND warning still failed and so that the day the
        default moved, this line was the one that had to change.

        That day is 2026-09-01. The shipped selection is the derived hulls
        (ADR-0028, `Accepted` against the clause ADR-0051 restates), the rule is
        an ERROR again rather than a WARNING, and the model no longer
        trips it. The exact-set form is kept for the reason it was chosen.
        """
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


class TestSupportMargin:
    """The rule that would have caught the belt end, and did not exist to.

    `cell_a__conveyor_1__infeed` lay exactly on the leading-edge plane of the
    belt's collision box. Every rule above passed it — the frame IS on its own
    geometry, the point IS inside the envelope, the corridor above it IS clear —
    and every work-piece released there was set down with half of it over the
    void, tipped about the edge and fell 0.600 m to the floor. `pick_and_place`
    failed 0 of 18 while the model validated cleanly every time.
    """

    BELT = "assets/types/conveyors/belt_1200x400.yaml"

    def _set_inset(self, model: Path, edit_yaml: Callable, inset: float) -> None:
        """Move both transfer frames `inset` metres in from the belt's ends."""

        def mutate(document: dict) -> None:
            frames = {f["id"]: f for f in document["asset_type"]["frames"]}
            frames["infeed"]["xyz_m"] = [-0.600 + inset, 0.0, 0.600]
            frames["outfeed"]["xyz_m"] = [0.600 - inset, 0.0, 0.600]

        edit_yaml(model / self.BELT, mutate)

    def test_a_point_on_the_supporting_edge_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Exactly the committed defect: transfer frames back on the belt's own
        # ends, inset 0.000. This is the case the shipped rules all passed.
        self._set_inset(real_model, edit_yaml, 0.000)
        assert "insufficient-support-margin" in geometric_rules(real_model)

    def test_the_frame_rule_alone_does_not_see_it(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The reason a second rule had to exist rather than the first being
        # tightened. `frame-outside-geometry` asks whether a frame is OUTSIDE its
        # body, with strict comparisons, so a frame lying exactly on a boundary
        # face is inside and passes — which is correct for a work surface and
        # useless for a work point.
        self._set_inset(real_model, edit_yaml, 0.000)
        assert "frame-outside-geometry" not in geometric_rules(real_model)

    def test_bare_footprint_support_is_still_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Half a work-piece of margin is neutral stability, not a fix.

        At an inset of exactly 0.025 m a 50 mm cube is just fully supported: its
        edge is flush with the belt's, its centre of mass projects onto the
        BOUNDARY of its support polygon, and any error towards the edge tips it.
        A probe released there did stay on the belt — which is exactly why a rule
        that stopped at the physical minimum would license it.
        """
        self._set_inset(real_model, edit_yaml, 0.025)
        assert "insufficient-support-margin" in geometric_rules(real_model)

    def test_the_shipped_inset_is_accepted(self, real_model: Path) -> None:
        assert "insufficient-support-margin" not in geometric_rules(real_model)

    def test_the_shipped_inset_costs_no_reach_margin(self, real_model: Path) -> None:
        # The other half of the fix, and the half that is easy to lose. Buying
        # support margin costs working distance, and at the original 0.350 m
        # standoff a 0.050 m inset put all five transfer points at 87.2% of the
        # envelope — over COMFORTABLE_REACH_FRACTION. The standoff was reduced to
        # pay for it, and this fails if either half is reverted alone.
        assert "reach-margin" not in geometric_rules(real_model, Severity.WARNING)

    def test_a_point_at_the_centre_of_its_surface_is_not_reported(self, real_model: Path) -> None:
        # `work_table_600.surface` sits at the centre of its top face — 0.300 m
        # of margin — and never showed this failure. Same generator, opposite
        # support margin, and the rule must not fire on the good case.
        model = load(real_model)
        cell = resolve(model, "cell_a")
        station = next(s for s in cell.stations if s.id == "station_transfer_1")
        assert station.pick_from == ("table_pick", "surface")
        assert "insufficient-support-margin" not in geometric_rules(real_model)

    def test_a_facility_with_no_workpiece_is_not_judged(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The margin is derived from the work-piece. With none declared there is
        # no bound, and reporting one anyway would mean inventing the part.
        self._set_inset(real_model, edit_yaml, 0.000)
        edit_yaml(
            real_model / "facility/facility.yaml",
            lambda d: d["facility"].__setitem__("workpiece_models", []),
        )
        assert "insufficient-support-margin" not in geometric_rules(real_model)

    def test_a_wider_workpiece_needs_more_margin(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The bound follows the part rather than being a constant: widen the cube
        # to 100 mm and the shipped 0.050 m inset is no longer enough for it.
        edit_yaml(
            real_model / "assets/types/workpieces/workpiece.yaml",
            lambda d: d["asset_type"]["description"]["body"]["collision"].__setitem__(
                "size_m", [0.100, 0.100, 0.100]
            ),
        )
        assert "insufficient-support-margin" in geometric_rules(real_model)


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


class TestDefaultGraspWidth:
    """The default a `Pick` closes to has to be a width the gripper can act on.

    Both bounds below are silent failures in the simulator: the gripper closes,
    the controller reports success, nothing attaches, and every layer above
    reports that it picked something up. The cost of finding that at run time is
    a full bring-up; the cost of finding it here is a millisecond.
    """

    #: The end-effector type carrying the default, as a path fragment.
    EFFECTOR = "assets/types/end_effectors/xarm_parallel_gripper.yaml"

    def _set(self, model: Path, edit_yaml: Callable, **fields: float) -> None:
        def mutate(document: dict) -> None:
            document["asset_type"]["grasp"].update(fields)

        edit_yaml(model / self.EFFECTOR, mutate)

    def test_the_shipped_default_is_within_the_bound(self, real_model: Path) -> None:
        assert "default-grasp-width-never-closes" not in physical_rules(real_model)

    def test_a_width_the_pads_cannot_open_to_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """95 mm on a gripper whose pads reach 88.93 mm is not commandable.

        This case used to read 65 mm, against a ceiling of
        opening(closed_threshold_rad) = 60.92 mm. That ceiling went with
        ADR-0023's attachment plugin: it bounded the width at which the plugin
        would fire, and nothing fires now. 65 mm is a width this gripper can
        genuinely close on, so asserting it is faulted would be asserting a
        defect as a requirement. The case is moved to the bound that survives
        rather than deleted, and the loosening is deliberate and recorded — see
        `_default_grasp_width_can_close`.
        """
        self._set(real_model, edit_yaml, default_grasp_width_m=0.095)
        assert "default-grasp-width-never-closes" in physical_rules(real_model)

    def test_a_width_inside_the_stroke_but_wider_than_the_part_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The gap that used to be documented instead of checked.

        65 mm is inside the gripper's stroke, so the weak bound accepts it. It is
        also 15 mm WIDER than the cell's 50 mm cube, so the pads never touch the
        part, the joint reaches its command, the controller reports `reached_goal`
        and every layer above believes a grasp happened. This test used to assert
        that the validator let it through — with a docstring explaining that L0
        recorded no work-piece geometry, so the bound could not be derived. L0
        records it now, and the assertion is inverted.
        """
        self._set(real_model, edit_yaml, default_grasp_width_m=0.065)
        assert "default-grasp-width-never-closes" in physical_rules(real_model)

    def test_a_width_equal_to_the_part_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # ADR-0022's whole mechanism: a parallel gripper evidences a grasp by
        # failing to reach where it was sent. Commanded exactly the part's width,
        # it arrives on target and the skill learns nothing.
        self._set(real_model, edit_yaml, default_grasp_width_m=0.050)
        assert "default-grasp-width-never-closes" in physical_rules(real_model)

    def test_a_margin_below_the_controller_bias_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Narrower than the part is necessary and not sufficient.

        48 mm leaves 2.00 mm against the 50 mm cube. `GripperActionController`
        ends a goal as soon as `|error| < goal_tolerance`, so the width it reports
        is systematically wider than commanded even in free air, and
        `cite_skills::gripper_is_holding` demands twice that bias — 2.14 mm here —
        before calling anything a grasp. A real grasp inside that band is
        indistinguishable from closing on air.
        """
        self._set(real_model, edit_yaml, default_grasp_width_m=0.048)
        assert "default-grasp-width-never-closes" in physical_rules(real_model)

    def test_the_bound_follows_the_declared_tolerance(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """It is derived, not a millimetre count someone wrote down.

        Loosen the controller's `goal_tolerance` fourfold and the discrimination
        threshold widens with it, so the 45 mm default that passes at 0.01 rad
        stops passing. That is the property that keeps this ceiling and the L3
        predicate from drifting apart — both read the same declared number.
        """

        def mutate(document: dict) -> None:
            for controller in document["asset_type"]["controllers"]:
                if controller["joints"] == "end_effector":
                    controller["parameters"]["goal_tolerance"] = 0.04

        edit_yaml(real_model / self.EFFECTOR, mutate)
        assert "default-grasp-width-never-closes" in physical_rules(real_model)

    def test_a_facility_with_no_workpiece_falls_back_to_the_weak_bound(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Stated rather than left to an absence: with no work-piece declared
        # there is no part width, so only the gripper's own opening is checked.
        # The rule reports what it can derive and does not invent the rest.
        self._set(real_model, edit_yaml, default_grasp_width_m=0.065)
        edit_yaml(
            real_model / "facility/facility.yaml",
            lambda d: d["facility"].__setitem__("workpiece_models", []),
        )
        assert "default-grasp-width-never-closes" not in physical_rules(real_model)

    def test_the_bound_sits_where_the_linkage_puts_it(self, real_model: Path) -> None:
        """The ceiling is the opening at `open_position`, to the millimetre.

        Pinned because the number is load-bearing. Asserting the derivation
        rather than the constant means the day the linkage changes, this test
        moves with it instead of lying.
        """
        model = load(real_model)
        grasp = model.asset_type("xarm_parallel_gripper").grasp
        ceiling = grasp.max_width_m
        assert ceiling == pytest.approx(0.08893, abs=1e-5)
        assert grasp.default_grasp_width_m < ceiling

    def test_the_bound_moves_with_the_linkage(self, real_model: Path, edit_yaml: Callable) -> None:
        """The ceiling is derived, not a constant. Shortening the crank lowers it.

        This is what stops the check from being a hardcoded millimetre count
        that quietly stops matching the model it is checking.
        """
        self._set(real_model, edit_yaml, default_grasp_width_m=0.045)
        assert "default-grasp-width-never-closes" not in physical_rules(real_model)

        def shrink(document: dict) -> None:
            document["asset_type"]["grasp"]["linkage"]["finger_offset_y_m"] = 0.010

        edit_yaml(real_model / self.EFFECTOR, shrink)
        assert "default-grasp-width-never-closes" in physical_rules(real_model)

    def test_an_end_effector_without_a_default_is_not_faulted(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Declining to name a default is a real state, not an omission.

        A vacuum end effector has no grasp width at all, and a parallel one may
        prefer the skill's explicit "no width was supplied" warning to a wrong
        number applied silently.
        """

        def mutate(document: dict) -> None:
            document["asset_type"]["grasp"].pop("default_grasp_width_m", None)

        edit_yaml(real_model / self.EFFECTOR, mutate)
        assert physical_rules(real_model) == set()


class TestDerivedCollisionGeometryIsBoundToAWidth:
    """ADR-0051 decision 3, which named this rule and did not write it.

    The hulls ship (ADR-0028, promoted 2026-09-01) on a campaign whose verdict on
    its own question was INCONCLUSIVE. What carries the promotion instead is a
    geometric clearance argument, and that argument was made over one part at one
    width: the hull's ramps sit behind the pad plane, and a 50 mm part stalls the
    jaws before it can reach them. A NARROWER part closes the jaws further, and
    nothing has measured whether they touch then.

    So the tests below are not a shape check. They are a check that **declaring a
    narrower part is refused**, which is the only moment anyone would find out.

    THE HAPPY PATH IS THE LEAST INTERESTING CASE HERE, deliberately. The campaign
    this rule comes out of shipped a pre-flight check naming a directory that does
    not exist; it reported nothing in all four of its blocks and nobody noticed,
    because a check that cannot fail is indistinguishable from one that passes.
    Every case below that matters makes the rule *fire* or proves it stays silent
    for a stated reason.
    """

    RULE = "derived-collision-outside-measured-range"
    UNSTATED = "derived-collision-range-unstated"
    WORKPIECE = "assets/types/workpieces/workpiece.yaml"
    ARM = "assets/types/robots/xarm5.yaml"

    def _mesh_the_part(self, model: Path, edit_yaml: Callable) -> None:
        """Give the cube a mesh collision body, which is what removes its width.

        Collision only. `horizontal_extents_m` reads the collision geometry, so
        this is the smallest edit that makes the width unknowable, and leaving the
        visual a box keeps `collision-reuses-visual-mesh` on the authored body out
        of the result — a second finding would make the assertions below ambiguous
        about which rule fired.
        """

        def mutate(document: dict) -> None:
            document["asset_type"]["description"]["body"]["collision"] = {
                "kind": "mesh",
                "uri": "package://cite_description/meshes/workpiece.stl",
            }

        edit_yaml(model / self.WORKPIECE, mutate)

    def _narrow_the_part(self, model: Path, edit_yaml: Callable, width_m: float) -> None:
        """Narrow the cube across its horizontal footprint, and only there.

        Height is left alone: the rule reads the horizontal extents, which is what
        a parallel gripper closes across, and moving the height would change what
        the geometric rules see for no reason this test cares about.
        """

        def mutate(document: dict) -> None:
            body = document["asset_type"]["description"]["body"]
            for geometry in (body["visual"], body["collision"]):
                _, _, height = geometry["size_m"]
                geometry["size_m"] = [width_m, width_m, height]

        edit_yaml(model / self.WORKPIECE, mutate)

    def _select_vendor(self, model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            model / self.ARM,
            lambda d: d["asset_type"]["description"]["collision"].__setitem__(
                "select", "vendor_meshes"
            ),
        )

    def test_the_shipped_model_is_inside_the_range(self, real_model: Path) -> None:
        """50 mm against a range that starts at 50 mm: the boundary is inclusive.

        The range is the width the campaign ran, so the part it ran on has to be
        inside it or the promotion it carries refers to nothing.
        """
        assert self.RULE not in physical_rules(real_model)

    def test_a_narrower_part_against_a_derived_set_is_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The case the rule exists for, and it is an ERROR.

        40 mm is inside every other bound in this file — the gripper opens to it,
        the default grasp width still clears the discrimination margin at it — so
        nothing else in the validator would say a word.
        """
        self._narrow_the_part(real_model, edit_yaml, 0.040)
        assert self.RULE in physical_rules(real_model, Severity.ERROR)

    def test_a_narrower_part_against_the_vendor_set_is_silent(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The other half, and it is what makes the finding actionable.

        The vendor's meshes carry no clearance argument to be outside of, so a
        narrow part is not this rule's business there — which is also why the
        finding can tell a model author to select them. If this fired on both
        selections it would be a rule about work-pieces, not about the binding.

        The second assertion is the one this test lacked until 2026-09-01, and
        lacking it is what let the contradiction ship: "this rule went quiet" is
        true of a remedy and of a dead end alike. `TestTheRemedyTheHintNamesIsAValidModel`
        below asks the whole question; this keeps the local half honest.
        """
        self._narrow_the_part(real_model, edit_yaml, 0.040)
        self._select_vendor(real_model, edit_yaml)
        assert self.RULE not in physical_rules(real_model, Severity.ERROR)
        assert "collision-reuses-visual-mesh" not in physical_rules(real_model, Severity.ERROR)

    def test_it_reads_the_selection_and_not_the_declaration(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """`convex_hull` stays DECLARED under the vendor selection above.

        Both sets are declared on this type whichever is bound, so a rule that
        keyed on "a derived set exists" would refuse a narrow part on a cell that
        loads none of it.
        """
        self._narrow_the_part(real_model, edit_yaml, 0.040)
        self._select_vendor(real_model, edit_yaml)
        model = load(real_model)
        collision = model.asset_type("xarm5").description.collision
        assert collision is not None
        assert {s.id for s in collision.sets} == {"vendor_meshes", "convex_hull"}
        assert self.RULE not in physical_rules(real_model, Severity.ERROR)

    def test_the_boundary_itself_is_accepted_and_a_hair_below_it_is_not(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Where the rule turns over, asserted rather than left to the reader.

        Written against the constant rather than against 0.050 so that moving the
        range with new evidence moves this test with it instead of leaving it to
        assert a number the module no longer holds.
        """
        self._narrow_the_part(real_model, edit_yaml, physical.NARROWEST_MEASURED_WORKPIECE_M)
        assert self.RULE not in physical_rules(real_model, Severity.ERROR)

        self._narrow_the_part(
            real_model, edit_yaml, physical.NARROWEST_MEASURED_WORKPIECE_M - 0.0001
        )
        assert self.RULE in physical_rules(real_model, Severity.ERROR)

    def test_a_facility_with_no_workpiece_is_not_judged(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Stated rather than left as an absence, because it is a real silence.

        With no work-piece declared there is no width, so the derived set ships
        against a range nobody has stated. The rule says nothing — it has nothing
        to say — and the docstring on `_derived_collision_is_within_its_measured_range`
        records that as a gap rather than as coverage.

        This is the case that stays silent. The one beside it — a work-piece that
        IS declared and states no width — does not, since 2026-09-01.
        """
        edit_yaml(
            real_model / "facility/facility.yaml",
            lambda d: d["facility"].__setitem__("workpiece_models", []),
        )
        assert self.RULE not in physical_rules(real_model, Severity.ERROR)
        assert self.UNSTATED not in physical_rules(real_model, Severity.ERROR)

    def test_a_mesh_workpiece_against_a_derived_set_is_its_own_finding(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The rule used to be switched off by omission, and this is that omission.

        `_narrowest_workpiece_width_m` returns `None` for a mesh work-piece as
        well as for a facility that declares none, and returning `[]` on `None`
        made those two states one. So changing the cube's collision geometry to a
        mesh — one line in L0 — shipped a part of *any* width against the hulls
        with this rule silent, which is exactly the act ADR-0051 decision 3 says
        reopens ADR-0028's clause 2.

        The width is unknowable here rather than merely unfavourable, so the
        finding is a different one: `derived-collision-range-unstated`.
        """
        self._mesh_the_part(real_model, edit_yaml)
        assert self.UNSTATED in physical_rules(real_model, Severity.ERROR)
        assert self.RULE not in physical_rules(real_model, Severity.ERROR)

    def test_the_unstated_finding_names_the_type_and_the_remedy(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """A refusal naming neither the part nor the way out sends someone reading code."""
        self._mesh_the_part(real_model, edit_yaml)
        finding = next(f for f in physical.check(load(real_model)) if f.rule == self.UNSTATED)
        assert finding.where == "types.xarm5.description.collision"
        assert "workpiece" in finding.message
        assert "ADR-0051" in (finding.hint or "")

    def test_the_vendor_set_stays_legal_for_a_mesh_workpiece(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The same escape hatch as for a narrow part, on the other refusal.

        Both collision rules read one predicate, so wherever the derived set is
        refused the vendor's set is not faulted — including here, where the width
        cannot be computed at all.
        """
        self._mesh_the_part(real_model, edit_yaml)
        self._select_vendor(real_model, edit_yaml)
        assert physical_rules(real_model, Severity.ERROR) == set()

    def test_the_finding_names_both_widths(self, real_model: Path, edit_yaml: Callable) -> None:
        """A refusal that does not say what it refused sends someone reading code.

        Both numbers, because the author needs to know which one to move: the
        part they just declared, and the range it fell out of.
        """
        self._narrow_the_part(real_model, edit_yaml, 0.040)
        finding = next(f for f in physical.check(load(real_model)) if f.rule == self.RULE)
        assert finding.where == "types.xarm5.description.collision"
        assert "40.0 mm" in finding.message
        assert "50.0 mm" in finding.message
        assert "ADR-0051" in (finding.hint or "")


class TestTheRemedyTheHintNamesIsAValidModel:
    """R-01. The escape hatch both collision rules point at has to exist.

    For one day it did not. `_derived_collision_is_within_its_measured_range`
    justified its ERROR severity by saying the correct answer *"is always
    available and never destructive — select the vendor's set"*, and the same
    change made `_vendor_collision_is_declared` refuse the vendor's set
    unconditionally. A 40 mm cube reported one rule on `convex_hull` and the other
    on `vendor_meshes`, so a narrow part had **no legal collision selection**, and
    both of the tests written for the hatch asserted only that one rule had gone
    quiet — which is true of a contradiction as well as of a remedy.

    So this class asserts the thing those tests could not: after applying the
    remedy the hint gives, **the model is valid**. Not "the rule stopped firing".
    """

    WORKPIECE = TestDerivedCollisionGeometryIsBoundToAWidth.WORKPIECE
    ARM = TestDerivedCollisionGeometryIsBoundToAWidth.ARM

    #: Narrow enough to be outside the measured range, wide enough that the
    #: gripper's own bound is untouched: `default_grasp_width_m` is 45 mm and the
    #: discrimination margin at that command is about 2.12 mm, so 48 mm clears
    #: `default-grasp-width-never-closes` and nothing else in the validator has an
    #: opinion. Anything narrower would make this test pass or fail for a second
    #: reason, which is how a "the model is valid" assertion turns into noise.
    NARROW_M = 0.048

    def _narrow(self, model: Path, edit_yaml: Callable) -> None:
        TestDerivedCollisionGeometryIsBoundToAWidth()._narrow_the_part(
            model, edit_yaml, self.NARROW_M
        )

    def test_the_narrow_part_is_refused_the_derived_set(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The premise, asserted first so the test below cannot pass vacuously.

        If 48 mm did not trip the range rule, the remedy assertion would be
        checking that a model nobody faulted is valid.
        """
        self._narrow(real_model, edit_yaml)
        assert physical_rules(real_model, Severity.ERROR) == {
            "derived-collision-outside-measured-range"
        }

    def test_taking_the_remedy_leaves_the_model_valid(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The finding, and the reason this class exists.

        `physical_rules(...) == set()` on BOTH severities: the vendor selection
        has to be silent rather than demoted, because a warning would still fail
        `validate --strict` and would leave the author of a narrow part carrying a
        finding for making the only choice available to them.
        """
        self._narrow(real_model, edit_yaml)
        edit_yaml(
            real_model / self.ARM,
            lambda d: d["asset_type"]["description"]["collision"].__setitem__(
                "select", "vendor_meshes"
            ),
        )
        assert physical_rules(real_model, Severity.ERROR) == set()
        assert physical_rules(real_model, Severity.WARNING) == set()

    def test_the_vendor_selection_is_still_refused_inside_the_range(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The hatch is conditional, and this is what stops it being an opt-out.

        With the shipped 50 mm part — inside the range — the derived set is
        available and selecting the vendor's rendering meshes is the plain defect
        CLAUDE.md §10 names. The condition is "the range rule fires", never "the
        author would rather not".
        """
        edit_yaml(
            real_model / self.ARM,
            lambda d: d["asset_type"]["description"]["collision"].__setitem__(
                "select", "vendor_meshes"
            ),
        )
        assert "collision-reuses-visual-mesh" in physical_rules(real_model, Severity.ERROR)

    def test_a_type_with_no_alternative_is_still_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The hatch needs an alternative to be a hatch.

        Drop the derived set from the type entirely and the vendor's meshes are
        not a fallback, they are the only geometry declared — and the finding
        ADR-0028 decision 4 exists for is exactly that state. A narrow part must
        not excuse it.
        """
        TestDerivedCollisionGeometryIsBoundToAWidth()._narrow_the_part(
            real_model, edit_yaml, self.NARROW_M
        )

        def only_vendor(document: dict) -> None:
            collision = document["asset_type"]["description"]["collision"]
            collision["select"] = "vendor_meshes"
            collision["sets"] = [s for s in collision["sets"] if s["kind"] == "vendor_meshes"]

        edit_yaml(real_model / self.ARM, only_vendor)
        assert "collision-reuses-visual-mesh" in physical_rules(real_model, Severity.ERROR)


class TestIndexingBeams:
    """A beam that stops a belt has to leave the part where a robot can reach it.

    THE FAILURE THESE EXIST FOR. `beam_c1_out` was authored 50 mm upstream of the
    point `station_transfer_2` picks from. A through beam breaks on a part's
    leading edge, so the belt stopped with the cube 69 mm short of the grasp and
    `arm_2` closed on air at `commanded 45.0 mm, reached 46.0 mm, stalled=false`.
    `continuous_line` stopped at milestone 4 of 10 on four runs out of four, and
    the model validated cleanly every time.

    The position is derived now — `cite_tools.model.resolve.index_offset_m` — so
    the specific mistake cannot be made again. These are for the mistakes that
    are still available: authoring an offset next to the derived one, indexing to
    a point nobody picks from, and declaring a part the geometry cannot serve.
    Ten minutes of scenario against a fraction of a second here.
    """

    SENSORS = "assets/instances/sensors.yaml"
    WORKPIECE = "assets/types/workpieces/workpiece.yaml"

    #: Index of each beam in `sensors.yaml`, which lists them in this order.
    PICK, C1_OUT, C2_OUT, C3_OUT = 0, 1, 2, 3

    @staticmethod
    def _beam_x(path: Path, beam: str = "beam_c1_out") -> float:
        model = load(path)
        asset = resolve(model, "cell_a").asset(beam)
        assert asset is not None
        return asset.world_pose.xyz_m[0]

    def test_the_stand_off_is_derived_from_the_part(self, real_model: Path) -> None:
        """The shipped number, and where it comes from.

        `conveyor_1/outfeed` is at x = 1.600. Half a 50 mm cube is 25 mm and half
        a 4 mm beam is 2 mm, so the housing stands at 1.627 and a part whose
        leading edge breaks the beam has its centre exactly on the pick point.
        """
        assert self._beam_x(real_model) == pytest.approx(1.627)

    def test_the_stand_off_follows_the_part(self, real_model: Path, edit_yaml: Callable) -> None:
        """The whole point of deriving it rather than writing it down.

        Double the part and the beam moves with it, with nothing authored to keep
        in step. A fitted coordinate would have stayed at 1.627 and started
        parking the new part 25 mm short, reporting nothing.
        """

        def widen(document: dict) -> None:
            document["asset_type"]["description"]["body"]["collision"]["size_m"] = [
                0.100,
                0.100,
                0.050,
            ]

        edit_yaml(real_model / self.WORKPIECE, widen)
        assert self._beam_x(real_model) == pytest.approx(1.652)

    def test_an_authored_offset_beside_the_derived_one_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The repair this project keeps being tempted by, made impossible.

        Sliding the beam by hand until the scenario passes fits L0 geometry to
        whatever the simulator happens to do. The old -0.050 is used here because
        it is exactly the value that was there.
        """
        edit_yaml(
            real_model / self.SENSORS,
            lambda d: d["assets"][self.C1_OUT]["pose"].__setitem__("xyz_m", [-0.050, 0.250, 0.030]),
        )
        assert "beam-indexes-off-frame" in geometric_rules(real_model)

    def test_indexing_to_a_point_no_station_picks_from_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """`station_accumulation` is a sink with no actor: nothing picks there.

        A belt indexed to a point no arm reaches for parks parts where nobody
        collects them, and the line blocks behind them.
        """
        edit_yaml(
            real_model / self.SENSORS,
            lambda d: d["assets"][self.C3_OUT]["configuration"].__setitem__(
                "indexes_workpiece", True
            ),
        )
        assert "beam-indexes-no-pick-point" in geometric_rules(real_model)

    def test_a_part_long_enough_to_push_the_beam_off_the_belt_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The transfer point is only 50 mm inside the belt's end.

        The stand-off is half a part, so a long enough part walks the housing
        past the end of the conveyor — where nothing crosses it, the belt never
        stops, and parts run off the end.
        """

        def lengthen(document: dict) -> None:
            document["asset_type"]["description"]["body"]["collision"]["size_m"] = [
                0.250,
                0.250,
                0.050,
            ]

        edit_yaml(real_model / self.WORKPIECE, lengthen)
        assert "beam-off-its-belt" in geometric_rules(real_model)

    def test_indexing_with_no_work_piece_declared_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Half of nothing is not a stand-off.

        Reported rather than raised: resolution runs first, so an exception here
        would replace every geometric finding with a traceback.
        """
        edit_yaml(
            real_model / "facility/facility.yaml",
            lambda d: d["facility"].__setitem__("workpiece_models", []),
        )
        assert "beam-cannot-index" in geometric_rules(real_model)

    def test_a_beam_the_part_walks_under_is_caught(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """80 mm above a belt carrying a 50 mm cube.

        This exact height was tried on this cell. The sensor could not be broken
        by anything the facility declared, and the only symptom was a station
        that waited for ever — the model validated, the world loaded, the belt
        ran. It is caught in the model now.
        """
        edit_yaml(
            real_model / self.SENSORS,
            lambda d: d["assets"][self.C1_OUT]["pose"].__setitem__("xyz_m", [0.000, 0.250, 0.080]),
        )
        assert "beam-cannot-see-workpiece" in geometric_rules(real_model)

    def test_the_shipped_mounting_height_clears_the_declared_part(self, real_model: Path) -> None:
        """30 mm under a 50 mm cube, with 20 mm to spare — and no upper bound.

        The beam used to have one: a window of part-CENTRE heights that missed
        anything over 100 mm tall while the physical cell saw it. There is no
        such rule here because there is no such bound any more.
        """
        assert "beam-cannot-see-workpiece" not in geometric_rules(real_model)
