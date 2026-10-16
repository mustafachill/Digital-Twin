"""The generated visual meshes of authored bodies (ADR-0079).

Each property below is asked of every body that wears one, because each is one
the decision rests on:

* the committed GLB **is** the generator's output, byte for byte, so the file
  cannot drift from the model it was drawn from;
* it lies **inside the collision box**, so the visual never shows something the
  planner and physics do not know about;
* its **top is the box top**, where the type's `surface` frame says parts stand,
  and nothing rises above it;
* every finish is **non-metallic**, because a metal with no environment map to
  reflect renders near black in Gazebo;
* the scene draws the mesh, paints nothing over it, and still **collides against
  the box**.
"""

from __future__ import annotations

import io
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest
import trimesh
from conftest import REAL_MODEL

from cite_tools import generate as gen
from cite_tools.generate import package
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve
from cite_tools.visuals import VisualMeshError, asset_path, bodies, conveyor, table

REPO_ROOT = REAL_MODEL.parent
#: The tolerance on the top's height. The file stores float32.
TOLERANCE_M = 0.001
#: The types that must wear a generated mesh. Asked of the model below, and
#: named here only so that losing one is a failure rather than a smaller loop.
EXPECTED = {"belt_1200x400": "conveyors", "work_table_600": "tables"}

MODEL = load(REAL_MODEL)
TARGETS = bodies.targets(MODEL, REPO_ROOT)
IDS = [t.type_id for t in TARGETS]


def _committed(target: bodies.Target) -> trimesh.Scene:
    return trimesh.load(io.BytesIO(target.path.read_bytes()), file_type="glb")


def _surface_z(type_id: str) -> float:
    asset_type = next(t for t in MODEL.types if t.id == type_id)
    return next(f for f in asset_type.frames if f.id == "surface").xyz_m[2]


def test_the_expected_bodies_wear_a_generated_mesh() -> None:
    assert {t.type_id: t.drawer for t in TARGETS} == EXPECTED


@pytest.mark.parametrize("target", TARGETS, ids=IDS)
def test_the_committed_mesh_equals_a_fresh_generation(target: bodies.Target) -> None:
    assert (
        target.path.read_bytes() == target.glb()
    ), f"{target.path.relative_to(REPO_ROOT)} is stale; run python -m cite_tools.visuals --write"


@pytest.mark.parametrize("target", TARGETS, ids=IDS)
def test_two_generations_are_byte_identical(target: bodies.Target) -> None:
    assert target.glb() == target.glb()


def test_the_check_command_passes_on_the_shipped_tree() -> None:
    assert bodies.main(["--model", str(REAL_MODEL)]) == 0


@pytest.mark.parametrize("target", TARGETS, ids=IDS)
def test_the_mesh_lies_inside_the_collision_box(target: bodies.Target) -> None:
    half = np.array(target.size_m) / 2.0
    lower, upper = _committed(target).bounds
    assert np.all(lower >= -half - 1e-6), f"below the box: {lower} vs {-half}"
    assert np.all(upper <= half + 1e-6), f"above the box: {upper} vs {half}"


@pytest.mark.parametrize("target", TARGETS, ids=IDS)
def test_the_top_is_the_surface_frame(target: bodies.Target) -> None:
    """+half a height from the centre is the foot-relative `surface` height."""
    half_height = target.size_m[2] / 2.0
    top = _committed(target).bounds[1][2]
    assert abs(top - half_height) <= TOLERANCE_M
    assert abs((top + half_height) - _surface_z(target.type_id)) <= TOLERANCE_M


@pytest.mark.parametrize("target", TARGETS, ids=IDS)
def test_no_finish_is_metallic(target: bodies.Target) -> None:
    for name, mesh in _committed(target).geometry.items():
        material = mesh.visual.material
        assert material.roughnessFactor is not None, name
        assert material.metallicFactor == 0.0, f"{name} is metallic"


def test_the_belt_is_what_the_conveyor_top_is() -> None:
    """On the conveyor, the topmost thing is the belt, so a part rides on rubber."""
    target = next(t for t in TARGETS if t.drawer == "conveyors")
    committed = _committed(target)
    rubber_top = committed.geometry[conveyor.RUBBER.name].bounds[1][2]
    for name, mesh in committed.geometry.items():
        assert mesh.bounds[1][2] <= rubber_top + 1e-6, f"{name} stands proud of the belt"


def test_the_table_top_is_the_top_finish() -> None:
    target = next(t for t in TARGETS if t.drawer == "tables")
    committed = _committed(target)
    top = committed.geometry[table.TOP.name].bounds[1][2]
    assert abs(top - target.size_m[2] / 2.0) <= TOLERANCE_M
    assert committed.geometry[table.FRAME.name].bounds[1][2] < top


def _instances_wearing_a_mesh() -> list[str]:
    worn = {t.type_id for t in TARGETS}
    return sorted(
        asset.id
        for zone in MODEL.zones
        for asset in resolve(MODEL, zone.id).assets
        if asset.asset_type.id in worn
    )


@pytest.mark.parametrize("asset_id", _instances_wearing_a_mesh())
def test_the_scene_draws_the_mesh_and_collides_against_the_box(asset_id: str) -> None:
    scene = next(a for a in gen.generate(MODEL) if a.path.endswith("_scene.urdf.xacro"))
    link = ElementTree.fromstring(scene.content).find(f"./link[@name='{asset_id}_base_link']")
    assert link is not None, f"no {asset_id} link in the scene"
    mesh = link.find("visual/geometry/mesh")
    assert mesh is not None and mesh.get("filename", "").endswith(".glb")
    assert link.find("visual/material") is None, "a URDF material would paint the mesh over"
    assert link.find("collision/geometry/box") is not None
    assert link.find("collision/geometry/mesh") is None


@pytest.mark.parametrize("target", TARGETS, ids=IDS)
def test_the_uri_resolves_to_the_committed_file(target: bodies.Target) -> None:
    assert target.path.is_file()
    assert target.path.is_relative_to(REPO_ROOT / bodies.VISUAL_ROOT / target.drawer)


def test_a_uri_outside_the_installed_meshes_is_refused() -> None:
    with pytest.raises(VisualMeshError):
        asset_path(REPO_ROOT, "file:///tmp/belt.glb")


def test_a_visual_directory_with_no_drawer_is_refused(real_model: Path, edit_yaml) -> None:
    edit_yaml(
        real_model / "assets/types/fixtures/work_table_600.yaml",
        lambda d: d["asset_type"]["description"]["body"]["visual"].__setitem__(
            "uri", "file://$(find cite_description)/meshes/visual/chairs/work_table_600.glb"
        ),
    )
    with pytest.raises(VisualMeshError, match="no drawer"):
        bodies.targets(load(real_model), real_model.parent)


def test_the_mesh_package_is_a_dependency_of_the_generated_package() -> None:
    xml = next(a for a in package.generate(MODEL) if a.path == "package.xml")
    assert "<exec_depend>cite_description</exec_depend>" in xml.content


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("file://$(find cite_description)/meshes/a.glb", "cite_description"),
        ("package://some_pkg/meshes/a.dae", "some_pkg"),
        ("file:///abs/a.glb", None),
    ],
)
def test_a_body_mesh_names_its_package(uri: str, expected: str | None) -> None:
    match = package._URI_PACKAGE.match(uri)
    assert (match and (match.group(1) or match.group(2))) == expected
