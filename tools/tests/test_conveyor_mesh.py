"""The conveyor's generated visual mesh (ADR-0079).

Four properties, each one the decision rests on:

* the committed GLB **is** the generator's output, byte for byte, so the file
  cannot drift from the model it was drawn from;
* it lies **inside the collision box**, so the visual never shows something the
  planner and physics do not know about;
* the **belt top is the box top**, where the type's `surface` frame says parts
  stand, so a carried part sits on the drawn belt;
* the scene draws the mesh and still **collides against the box**.
"""

from __future__ import annotations

import io
from xml.etree import ElementTree

import numpy as np
import pytest
import trimesh
from conftest import REAL_MODEL

from cite_tools import generate as gen
from cite_tools.generate import package
from cite_tools.model.loader import load
from cite_tools.visuals import VisualMeshError, asset_path, conveyor

REPO_ROOT = REAL_MODEL.parent
BELT = "belt_1200x400"
#: The tolerance on the belt-top height. The file stores float32.
TOLERANCE_M = 0.001


@pytest.fixture(scope="module")
def target() -> conveyor.Target:
    found = {t.type_id: t for t in conveyor.targets(load(REAL_MODEL), REPO_ROOT)}
    assert BELT in found, f"{BELT} no longer wears a generated visual mesh"
    return found[BELT]


@pytest.fixture(scope="module")
def committed(target: conveyor.Target) -> trimesh.Scene:
    return trimesh.load(io.BytesIO(target.path.read_bytes()), file_type="glb")


def test_the_committed_mesh_equals_a_fresh_generation(target: conveyor.Target) -> None:
    assert target.path.read_bytes() == conveyor.glb_bytes(target.size_m), (
        f"{target.path.relative_to(REPO_ROOT)} is stale; "
        "run python -m cite_tools.visuals.conveyor --write"
    )


def test_two_generations_are_byte_identical() -> None:
    assert conveyor.glb_bytes((1.2, 0.4, 0.6)) == conveyor.glb_bytes((1.2, 0.4, 0.6))


def test_the_check_command_passes_on_the_shipped_tree() -> None:
    assert conveyor.main(["--model", str(REAL_MODEL)]) == 0


def test_the_mesh_lies_inside_the_collision_box(
    target: conveyor.Target, committed: trimesh.Scene
) -> None:
    half = np.array(target.size_m) / 2.0
    lower, upper = committed.bounds
    assert np.all(lower >= -half - 1e-6), f"below the box: {lower} vs {-half}"
    assert np.all(upper <= half + 1e-6), f"above the box: {upper} vs {half}"


def test_the_belt_top_is_the_box_top(target: conveyor.Target, committed: trimesh.Scene) -> None:
    """+0.300 from the centre is 0.600 from the foot, where `surface` lies."""
    top = target.size_m[2] / 2.0
    rubber = committed.geometry["belt_rubber"]
    assert abs(rubber.bounds[1][2] - top) <= TOLERANCE_M
    assert abs(committed.bounds[1][2] - top) <= TOLERANCE_M

    surface = next(
        f
        for f in next(t for t in load(REAL_MODEL).types if t.id == BELT).frames
        if f.id == "surface"
    )
    assert abs((rubber.bounds[1][2] + top) - surface.xyz_m[2]) <= TOLERANCE_M


def test_nothing_rises_above_the_belt(committed: trimesh.Scene) -> None:
    rubber_top = committed.geometry["belt_rubber"].bounds[1][2]
    for name, mesh in committed.geometry.items():
        assert mesh.bounds[1][2] <= rubber_top + 1e-6, f"{name} stands proud of the belt"


def test_every_finish_is_a_pbr_material(committed: trimesh.Scene) -> None:
    for name, mesh in committed.geometry.items():
        material = mesh.visual.material
        assert material.metallicFactor is not None and material.roughnessFactor is not None, name


def test_the_scene_draws_the_mesh_and_collides_against_the_box() -> None:
    scene = next(a for a in gen.generate(load(REAL_MODEL)) if a.path.endswith("_scene.urdf.xacro"))
    root = ElementTree.fromstring(scene.content)
    link = root.find("./link[@name='transfer_belt_base_link']")
    assert link is not None, "no transfer_belt link in the scene"
    mesh = link.find("visual/geometry/mesh")
    assert mesh is not None and mesh.get("filename", "").endswith(f"/{BELT}.glb")
    assert link.find("visual/material") is None, "a URDF material would paint the mesh over"
    assert link.find("collision/geometry/box") is not None
    assert link.find("collision/geometry/mesh") is None


def test_the_uri_resolves_to_the_committed_file(target: conveyor.Target) -> None:
    assert target.path.is_file()
    assert target.path.is_relative_to(REPO_ROOT / "assets" / "meshes")


def test_a_uri_outside_the_installed_meshes_is_refused() -> None:
    with pytest.raises(VisualMeshError):
        asset_path(REPO_ROOT, "file:///tmp/belt.glb")


def test_the_mesh_package_is_a_dependency_of_the_generated_package() -> None:
    xml = next(a for a in package.generate(load(REAL_MODEL)) if a.path == "package.xml")
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
