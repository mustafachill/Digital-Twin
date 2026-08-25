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

from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from cite_tools.generate import bringup, world
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve

ZONE = "cell_a"


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
        assert len(plugins(root, "cite_conveyor")) == len(cell.of_category("conveyor")) == 3

    def test_one_beam_plugin_per_sensor(self, cell) -> None:
        root = world_xml(cell)
        assert len(plugins(root, "cite_break_beam")) == len(cell.of_category("sensor")) == 3

    def test_the_world_still_loads_the_systems_the_cell_depends_on(self, cell) -> None:
        # Contact reporting in particular: the grasp attachment plugin reads it,
        # and without it a grasp silently never holds (ADR-0023).
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
        assert emitted == {
            ("/cite/cell_a/conveyor_1/command", "/cite/cell_a/conveyor_1/state"),
            ("/cite/cell_a/conveyor_2/command", "/cite/cell_a/conveyor_2/state"),
            ("/cite/cell_a/conveyor_3/command", "/cite/cell_a/conveyor_3/state"),
        }

    def test_beam_topics_match_the_bring_up_plan(self, cell) -> None:
        plan = yaml.safe_load(bringup.generate(cell)[0].content)["plan"]
        declared = {entry["detection_topic"] for entry in plan["sensors"]}
        emitted = {value(p, "state_topic") for p in plugins(world_xml(cell), "cite_break_beam")}
        assert emitted == declared

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
            f"{cell.asset(a).frames['surface'].xyz_m[0]:g}"
            for a in ("conveyor_1", "conveyor_2", "conveyor_3")
        }
        assert emitted == expected

    def test_the_carry_footprint_is_the_belts_own_collision_box(self, cell) -> None:
        belt = cell.asset("conveyor_1")
        size = belt.asset_type.description.body.collision.size_m
        plugin = plugins(world_xml(cell), "cite_conveyor")[0]
        assert float(value(plugin, "belt_length_m")) == pytest.approx(size[0])
        assert float(value(plugin, "belt_width_m")) == pytest.approx(size[1])

    def test_the_beam_crosses_the_belt_rather_than_being_centred_on_its_housing(self, cell) -> None:
        # beam_c1_out stands 250 mm to the side of a 400 mm belt and declares a
        # 500 mm beam. Centred on the housing that spans y in [0.000, 0.500] —
        # half of it beside the belt, with its near edge exactly on the
        # centreline. Offset by the mounting standoff it spans [-0.250, +0.250]
        # and covers the belt with 50 mm to spare.
        plugin = plugins(world_xml(cell), "cite_break_beam")[0]
        housing_y = float(value(plugin, "beam_pose").split()[1])
        offset = float(value(plugin, "beam_offset_m"))
        half = float(value(plugin, "beam_length_m")) / 2.0
        centre = housing_y + offset
        assert centre == pytest.approx(0.0)
        assert centre - half <= -0.2 and centre + half >= 0.2

    def test_a_belt_carries_no_faster_than_its_installed_drive(self, cell) -> None:
        belt = cell.asset("conveyor_1")
        plugin = plugins(world_xml(cell), "cite_conveyor")[0]
        assert float(value(plugin, "installed_speed_mps")) == pytest.approx(
            belt.instance.configuration.installed_speed_mps
        )
        assert value(plugin, "direction") == belt.instance.configuration.direction


class TestTheGeneratorRefusesRatherThanGuesses:
    def test_a_conveyor_with_no_surface_frame_is_an_error(self, cell) -> None:
        # Silently emitting an origin pose would put the carry volume at the
        # corner of the building, and the belt would simply never carry anything
        # — a failure with no error anywhere.
        belt = cell.asset("conveyor_1")
        object.__setattr__(belt, "frames", {})
        with pytest.raises(world.WorldError, match="surface"):
            world.generate(cell)
