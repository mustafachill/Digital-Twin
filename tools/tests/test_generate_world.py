"""The world, and the simulation aids it declares.

Three plugins were written for this cell and none of them was reachable: the
world carried Physics, UserCommands, SceneBroadcaster and Contact and nothing
else, while the generated bring-up plan advertised a belt state topic, a belt
command topic and a beam detection topic per asset. The model asserted a set of
interfaces that did not exist at run time, which is a P7 gap that reads as a
sim/real parity failure the moment anything consumes it.

These tests are about the join: every conveyor and every sensor in L0 reaches the
world, and the names it reaches it under are the same names the plan declares.
"""

from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from cite_tools.generate import bringup, gui, world
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve

#: The zone, its arm and its belt, named once. The model declares one of each
#: (ADR-0069); every count below is asked of the model rather than written here.
ZONE = "cell_b"
ARM = "picker"
BELT = "transfer_belt"


@pytest.fixture
def cell(real_model: Path):
    return resolve(load(real_model), ZONE)


def world_xml(cell) -> ElementTree.Element:
    artifacts = world.generate(cell)
    assert len(artifacts) == 1
    return ElementTree.fromstring(artifacts[0].content).find("world")


def plugins(root: ElementTree.Element, filename: str) -> list[ElementTree.Element]:
    return [p for p in root.findall("plugin") if p.get("filename") == filename]


def value(plugin: ElementTree.Element, tag: str) -> str:
    element = plugin.find(tag)
    assert element is not None, f"{tag} missing from {plugin.get('filename')}"
    return (element.text or "").strip()


class TestEveryAidIsInstantiated:
    def test_one_conveyor_plugin_per_conveyor(self, cell) -> None:
        root = world_xml(cell)
        belts = cell.of_category("conveyor")
        assert belts, "the cell declares no conveyor, so this test asserted nothing"
        assert len(plugins(root, "cite_conveyor")) == len(belts)

    def test_one_beam_plugin_per_sensor(self, cell) -> None:
        # The property is the PAIRING, not the number. The trailing `== 3` that
        # used to be here was a second statement of how many beams the cell has,
        # and adding `beam_pick` to the model broke a test that had nothing to say
        # about it — which is exactly the "a value in two places" this repository
        # refuses. The count now comes from the model, once.
        root = world_xml(cell)
        sensors = cell.of_category("sensor")
        assert sensors, "the cell declares no sensor, so this test asserted nothing"
        assert len(plugins(root, "cite_break_beam")) == len(sensors)

    def test_the_world_still_loads_the_systems_the_cell_depends_on(self, cell) -> None:
        # Contact reporting is in this set although nothing reads it today: it
        # was loaded for ADR-0023's attachment plugin, which is removed. It is a
        # generic capability any `<sensor type="contact">` needs, kept
        # deliberately — see the comment in the world template.
        root = world_xml(cell)
        names = {p.get("name") for p in root.findall("plugin")}
        assert {
            "gz::sim::systems::Physics",
            "gz::sim::systems::UserCommands",
            "gz::sim::systems::SceneBroadcaster",
            "gz::sim::systems::Contact",
        } <= names


class TestTheNamesAgreeWithThePlan:
    """P1: the plan and the world must not be two places a topic name is made."""

    def test_belt_topics_match_the_bring_up_plan(self, cell) -> None:
        plan = yaml.safe_load(bringup.generate(cell)[0].content)["plan"]
        declared = {
            entry["asset"]: (entry["command_topic"], entry["state_topic"])
            for entry in plan["conveyors"]
        }
        emitted = {
            (value(p, "command_topic"), value(p, "state_topic"))
            for p in plugins(world_xml(cell), "cite_conveyor")
        }
        assert emitted == set(declared.values())
        assert emitted == {(f"/cite/{ZONE}/{BELT}/command", f"/cite/{ZONE}/{BELT}/state")}

    def test_beam_topics_match_the_bring_up_plan(self, cell) -> None:
        plan = yaml.safe_load(bringup.generate(cell)[0].content)["plan"]
        declared = {entry["detection_topic"] for entry in plan["sensors"]}
        emitted = {value(p, "state_topic") for p in plugins(world_xml(cell), "cite_break_beam")}
        assert emitted == declared

    def test_grasp_hold_topics_match_the_bring_up_plan(self, cell) -> None:
        # The cell's bridge reads the plan; the plugin reads the world. If these
        # two came apart the bridge would publish attach messages into a topic
        # nothing listens on, and the arm would carry the box on friction alone
        # while every layer above reported a grasp — silently, because a
        # gz-transport publication with no subscriber reports nothing.
        plan = yaml.safe_load(bringup.generate(cell)[0].content)["plan"]
        declared = {(entry["attach_topic"], entry["detach_topic"]) for entry in plan["grasp_holds"]}
        emitted = {
            (value(p, "attach_topic"), value(p, "detach_topic"))
            for p in plugins(world_xml(cell), "cite_grasp_hold")
        }
        assert emitted == declared
        assert len(declared) == len(cell.of_category("robot")) == 1

    def test_every_arm_with_a_plugin_has_a_plan_entry_and_the_reverse(self, cell) -> None:
        # One condition, two generators. An arm with an entry and no plugin gets a
        # bridge publishing into an empty partition; an arm with a plugin and no
        # entry gets a plugin nothing can ever tell to take hold.
        plan = yaml.safe_load(bringup.generate(cell)[0].content)["plan"]
        assert {entry["asset"] for entry in plan["grasp_holds"]} == {ARM}
        assert len(plugins(world_xml(cell), "cite_grasp_hold")) == len(plan["grasp_holds"])

    def test_only_declared_workpieces_are_carried_or_watched(self, cell) -> None:
        # A belt that carried whatever entered its volume would drag the gripper
        # reaching into it; a beam that noticed every model would be broken by
        # the conveyor it watches.
        root = world_xml(cell)
        for plugin in plugins(root, "cite_conveyor"):
            assert [e.text for e in plugin.findall("carry")] == list(cell.workpiece_models)
        for plugin in plugins(root, "cite_break_beam"):
            assert [e.text for e in plugin.findall("watch")] == list(cell.workpiece_models)


class TestGeometryComesFromTheModel:
    def test_the_belt_is_driven_relative_to_the_surface_stations_reach_for(self, cell) -> None:
        # The carry volume and the place target must be the same frame, or a part
        # is released onto a belt that does not carry it.
        emitted = {
            value(p, "surface_pose").split()[0] for p in plugins(world_xml(cell), "cite_conveyor")
        }
        expected = {
            f"{cell.asset(a.id).frames['surface'].xyz_m[0]:g}" for a in cell.of_category("conveyor")
        }
        assert expected, "the cell declares no conveyor, so this test asserted nothing"
        assert emitted == expected

    def test_the_carry_footprint_is_the_belts_own_collision_box(self, cell) -> None:
        belt = cell.asset(BELT)
        size = belt.asset_type.description.body.collision.size_m
        plugin = plugins(world_xml(cell), "cite_conveyor")[0]
        assert float(value(plugin, "belt_length_m")) == pytest.approx(size[0])
        assert float(value(plugin, "belt_width_m")) == pytest.approx(size[1])

    def test_the_carry_height_is_the_tallest_workpiece(self, cell) -> None:
        # How far above the surface a part still counts as resting on the belt is
        # a fact about the part, not about the belt. A part at rest sits half its
        # own height up, so a volume one part-height tall holds it dead centre and
        # releases it once it has been lifted higher than it is tall.
        #
        # This used to be declared on the conveyor at 0.100 m, which held a 50 mm
        # cube until it had been lifted 75 mm.
        tallest = max(
            asset_type.description.body.vertical_extent_m for asset_type in cell.workpiece_types
        )
        for plugin in plugins(world_xml(cell), "cite_conveyor"):
            assert float(value(plugin, "carry_height_m")) == pytest.approx(tallest)

    def test_every_belt_agrees_about_what_it_can_carry(self, cell) -> None:
        heights = {value(p, "carry_height_m") for p in plugins(world_xml(cell), "cite_conveyor")}
        assert len(heights) == 1

    def test_the_beam_crosses_the_belt_rather_than_being_centred_on_its_housing(self, cell) -> None:
        # The belt's beam stands 250 mm to the side of a 400 mm belt and declares
        # a 500 mm beam. Centred on the housing it would span 250 mm beside the
        # belt, with its near edge exactly on the centreline. Offset by the
        # mounting standoff it is centred on the belt and covers it with 50 mm to
        # spare on each side.
        plugin = next(
            p
            for p in plugins(world_xml(cell), "cite_break_beam")
            if "/outfeed_beam/" in value(p, "state_topic")
        )
        belt_y = cell.asset(BELT).world_pose.xyz_m[1]
        housing_y = float(value(plugin, "beam_pose").split()[1])
        offset = float(value(plugin, "beam_offset_m"))
        half = float(value(plugin, "beam_length_m")) / 2.0
        centre = housing_y + offset
        assert centre == pytest.approx(belt_y)
        assert centre - half <= belt_y - 0.2 and centre + half >= belt_y + 0.2

    def test_a_belt_carries_no_faster_than_its_installed_drive(self, cell) -> None:
        belt = cell.asset(BELT)
        plugin = plugins(world_xml(cell), "cite_conveyor")[0]
        assert float(value(plugin, "installed_speed_mps")) == pytest.approx(
            belt.instance.configuration.installed_speed_mps
        )
        assert value(plugin, "direction") == belt.instance.configuration.direction


class TestGraspHoldAidIsInstantiated:
    """One `cite_grasp_hold` plugin per arm that fits a grasping gripper (ADR-0061)."""

    def test_one_grasp_hold_plugin_per_arm_with_a_gripper(self, cell) -> None:
        root = world_xml(cell)
        arms = [a for a in cell.of_category("robot") if a.instance.end_effector is not None]
        assert arms, "the cell declares no arm with an end effector, so this asserted nothing"
        assert len(plugins(root, "cite_grasp_hold")) == len(arms)

    def test_the_attach_link_is_the_arm_s_own_last_link_not_the_gripper_s(self, cell) -> None:
        # `xarm_gripper_base_link` and `link_tcp` do not survive the URDF-to-SDF
        # conversion as entities of their own — see `GraspSpec.attach_link_suffix`
        # for the evidence. `link5` does.
        root = world_xml(cell)
        attach_links = {value(p, "attach_link") for p in plugins(root, "cite_grasp_hold")}
        assert attach_links == {f"{ARM}_link5"}

    def test_the_topics_are_generated_per_arm_from_the_asset_id(self, cell) -> None:
        # The names the cell's own bridge publishes to (ADR-0065). Built by the
        # SAME `ids.interface` calls the bring-up plan makes, which is what stops
        # the plugin listening on one name and the bridge publishing to another
        # — and asserted here rather than in one place, because a plugin nobody
        # can reach is a plugin that never attaches and never says so.
        root = world_xml(cell)
        assert {value(p, "attach_topic") for p in plugins(root, "cite_grasp_hold")} == {
            f"/cite/{ZONE}/{ARM}/grasp/attach"
        }
        assert {value(p, "detach_topic") for p in plugins(root, "cite_grasp_hold")} == {
            f"/cite/{ZONE}/{ARM}/grasp/detach"
        }

    def test_taking_hold_and_letting_go_are_never_one_topic(self, cell) -> None:
        for plugin in plugins(world_xml(cell), "cite_grasp_hold"):
            assert value(plugin, "attach_topic") != value(plugin, "detach_topic")

    def test_the_plugin_is_told_nothing_it_would_have_to_judge_with(self, cell) -> None:
        # ADR-0065's decision, as a check. Every parameter below let this plugin
        # re-derive `cite_skills::gripper_is_holding`'s verdict for itself, which
        # is the defect ADR-0062 and ADR-0064 were both refuted attempts to tune.
        # Emitting any of them again would not fail anything else here — the
        # plugin would simply ignore it — so the absence is asserted directly.
        judged_here = (
            "drive_joint",
            "stall_velocity_threshold",
            "stall_timeout_s",
            "detach_margin_rad",
            "open_position",
            "closed_position",
            "hold_position_min_rad",
            "hold_position_max_rad",
        )
        for plugin in plugins(world_xml(cell), "cite_grasp_hold"):
            emitted = [tag for tag in judged_here if plugin.find(tag) is not None]
            assert not emitted, (
                f"the world hands the grasp-hold plugin {emitted}, which is what it used "
                "to decide a grasp with. The cell decides that now (ADR-0065)."
            )

    def test_only_declared_workpieces_are_graspable(self, cell) -> None:
        root = world_xml(cell)
        for plugin in plugins(root, "cite_grasp_hold"):
            assert [e.text for e in plugin.findall("graspable")] == list(cell.workpiece_models)


class TestGraspHoldStillDiscriminatesWhichPartIsInTheJaws:
    """The one question the cell cannot answer, and therefore the only judgement
    left in this plugin (ADR-0065, decision 3): WHICH declared graspable is in
    the jaws.

    THIS CLASS USED TO BE `TestGraspHoldReadsTheGripperControllerRatherThanRestatingIt`,
    and beside it `TestGraspHoldWindowReplacesTheRailExclusion`. Between them
    they held that the plugin's stall threshold, stall timeout, release margin,
    rails and part-width window were the same numbers the controller and
    `cite_skills::gripper_is_holding` use. Not one of those reaches the plugin
    any more — the cell publishes its verdict and the plugin is told — so the
    tests are deleted rather than adapted: a test kept against a parameter that
    is gone asserts its own fixture.
    """

    def test_the_radius_matches_the_declared_grasp_specification(self, cell) -> None:
        effector = cell.end_effector_type("xarm_parallel_gripper")
        plugin = plugins(world_xml(cell), "cite_grasp_hold")[0]
        assert float(value(plugin, "attach_radius_m")) == pytest.approx(
            effector.grasp.attach_radius_m
        )


class TestTheGeneratorRefusesRatherThanGuesses:
    def test_a_conveyor_with_no_surface_frame_is_an_error(self, cell) -> None:
        # Silently emitting an origin pose would put the carry volume at the
        # corner of the building, and the belt would simply never carry anything
        # — a failure with no error anywhere.
        belt = cell.asset(BELT)
        object.__setattr__(belt, "frames", {})
        with pytest.raises(world.WorldError, match="surface"):
            world.generate(cell)

    def test_belts_with_no_workpiece_geometry_behind_them_are_an_error(self, cell) -> None:
        # A guessed carry height is the worst outcome available here: the plugin
        # loads, advertises its topics, acknowledges every command and carries
        # nothing, which is precisely the invisible failure this belt was written
        # instead of adopting one that could not report state.
        object.__setattr__(cell, "workpiece_models", ())
        with pytest.raises(world.WorldError, match="carry volume"):
            world.generate(cell)


class TestTheWorldIsHeldToTheWallClock:
    """ADR-0043 half 1: the generated world declares a real-time factor of 1.0.

    It used to declare `0`, which is Gazebo's unthrottled value and overrides
    SDFormat's own default of 1.0. That was sound for ONE simulation graded on
    outcomes and does not survive a second one that has to agree with the first
    about what time it is: two free-running sides were measured at 0.888 and
    0.698 in the same wall-clock window with nothing wrong on either, and a clock
    deficit accumulates without bound while a transport latency does not.

    A CEILING, not a floor, and nothing here may be read as saying the machine
    holds it. That is ADR-0043's second half, whose WORDING is superseded: with
    this factor in the world a measured rate is capped at it by construction, so
    ADR-0043's status line says not to cite half 2 as written. ADR-0049 keeps the
    1.0 floor on two quantities instead — capacity with this throttle lifted, and
    the accumulated clock deficit in seconds with it in force — and nothing in the
    tree measures either.
    """

    def test_the_world_declares_a_throttled_factor(self, cell) -> None:
        physics = world_xml(cell).find("physics")
        assert physics is not None
        assert float(physics.findtext("real_time_factor")) == 1.0

    def test_it_is_not_unthrottled(self, cell) -> None:
        # `0` is Gazebo's "as fast as you can", and it is the value this
        # replaced. Named separately from the assertion above because it is the
        # regression that matters: a future edit reaching for "make CI faster"
        # lands exactly here.
        physics = world_xml(cell).find("physics")
        assert physics is not None
        assert physics.findtext("real_time_factor").strip() not in ("0", "0.0")

    def test_the_step_size_is_untouched(self, cell) -> None:
        # Throttling changes how fast wall time is consumed, never how the
        # physics is integrated. A scenario's results depend on the step size,
        # so a change here would be a change to what is being measured.
        physics = world_xml(cell).find("physics")
        assert physics is not None
        assert float(physics.findtext("max_step_size")) == 0.001


class TestTheWindowOpensOnTheCell:
    """A windowed run's camera frames the whole zone from the customer side.

    Presentation only: the file is passed to `gz sim --gui-config` when a window
    opens and never on a headless run. The pose is derived from L0 per zone.
    """

    @pytest.fixture
    def zone_cell(self, real_model: Path):
        return resolve(load(real_model), ZONE)

    def test_it_stands_across_the_line_from_the_arms_and_faces_them(self, zone_cell) -> None:
        pose = gui.gui_camera_pose(zone_cell)
        ys = [a.world_pose.xyz_m[1] for a in zone_cell.assets]
        robots = [a.world_pose.xyz_m[1] for a in zone_cell.of_category("robot")]
        others = [
            a.world_pose.xyz_m[1]
            for a in zone_cell.assets
            if a.id not in {r.id for r in zone_cell.of_category("robot")}
        ]
        # The customer is on the side of the line away from the arms: -Y in
        # cell_b, whose arm rides a track on +Y since ADR-0067. Derived from the
        # model, not assumed, so a cell laid out the other way round is covered.
        customer = 1.0 if sum(others) / len(others) >= sum(robots) / len(robots) else -1.0
        assert (pose.y - max(ys) if customer > 0 else min(ys) - pose.y) > 0
        assert pose.yaw == pytest.approx(-customer * math.pi / 2)
        # Positive pitch looks down in Gazebo's camera frame.
        assert math.radians(30) <= pose.pitch <= math.radians(35)
        assert pose.z > max(a.world_pose.xyz_m[2] for a in zone_cell.assets)

    def test_the_whole_x_extent_fits_the_view(self, zone_cell) -> None:
        pose = gui.gui_camera_pose(zone_cell)
        half_fov = gui.HORIZONTAL_FOV_RAD / 2
        for asset in zone_cell.assets:
            x, y, z = asset.world_pose.xyz_m
            # Distance along the viewing direction (along the yaw, tilted down).
            forward = (y - pose.y) * math.sin(pose.yaw) * math.cos(pose.pitch) + (
                pose.z - z
            ) * math.sin(pose.pitch)
            assert abs(x - pose.x) < forward * math.tan(half_fov), asset.id

    def test_the_config_keeps_harmonics_default_plugins(self, zone_cell) -> None:
        (artifact,) = gui.generate(zone_cell)
        assert artifact.path == f"worlds/{zone_cell.zone}_gui.config"
        root = ElementTree.fromstring(f"<root>{artifact.content.split('?>', 1)[1]}</root>")
        names = {p.get("filename") for p in root.findall("plugin")}
        assert {
            "MinimalScene",
            "GzSceneManager",
            "InteractiveViewControl",
            "CameraTracking",
            "MarkerManager",
            "SelectEntities",
            "Spawn",
            "VisualizationCapabilities",
            "EntityContextMenuPlugin",
            "WorldControl",
            "WorldStats",
        } <= names
        # Left out on purpose: docked, they kept half the window from the cell.
        assert not {"EntityTree", "ComponentInspector"} & names
        pose = gui.gui_camera_pose(zone_cell)
        emitted = [float(v) for v in root.find("plugin/camera_pose").text.split()]
        assert emitted == pytest.approx([pose.x, pose.y, pose.z, 0.0, pose.pitch, pose.yaw])

    def test_the_plan_names_it(self, zone_cell) -> None:
        (plan,) = bringup.generate(zone_cell)
        document = yaml.safe_load(plan.content)["plan"]
        assert document["gui_config"] == (
            f"package://cite_generated/worlds/{zone_cell.zone}_gui.config"
        )
