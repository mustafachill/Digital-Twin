"""Shared building blocks for the generated visual meshes (ADR-0079).

A drawer module (``conveyor``, ``table``) describes its object as solid parts
grouped by finish; everything that turns those parts into committed bytes lives
here, so every generated mesh is shaded, rounded and exported the same way.

DETERMINISM. The GLBs are committed and checked byte for byte against a fresh
generation, as the derived hulls are (ADR-0028). Vertices are rounded to the
micrometre before export so that a last-bit difference in a platform's ``sin``
cannot reach the file, parts are concatenated in the drawer's fixed finish
order, and node and material names are fixed strings.

FINISHES ARE DIELECTRIC. The cell's worlds give a PBR metal no environment map
to reflect, so a metallic finish renders near black in Gazebo. Metal reads as
metal here through a light grey, and every finish keeps ``metallic`` at 0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

Triple = tuple[float, float, float]

#: Facets around every cylinder.
SECTIONS = 32

#: Micrometre rounding before export (see DETERMINISM above).
_DECIMALS = 6


@dataclass(frozen=True)
class Finish:
    """One PBR material, named in the GLB as its node and material name."""

    name: str
    rgba: tuple[float, float, float, float]
    metallic: float
    roughness: float


#: Every part of one drawing, grouped by finish, in the box-centred frame. The
#: dict's order is the export order.
Parts = dict[Finish, list[trimesh.Trimesh]]


def empty(finishes: tuple[Finish, ...]) -> Parts:
    """A parts table in ``finishes`` order, so the export order is the drawer's."""
    return {finish: [] for finish in finishes}


def box(extents: Triple, centre: Triple) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(centre)
    return mesh


def cylinder(radius: float, length: float, centre: Triple, axis: str) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=SECTIONS)
    if axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    elif axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    mesh.apply_translation(centre)
    return mesh


def frustum(
    bottom: tuple[float, float], top: tuple[float, float], z0: float, z1: float
) -> trimesh.Trimesh:
    """A rectangular frustum centred on the z axis, from ``z0`` to ``z1``.

    With ``top`` a little smaller than ``bottom`` it is a chamfered edge. The
    faces are written out rather than hulled, so their order is fixed.
    """
    (bx, by), (tx, ty) = (b / 2.0 for b in bottom), (t / 2.0 for t in top)
    vertices = np.array(
        [
            [-bx, -by, z0], [bx, -by, z0], [bx, by, z0], [-bx, by, z0],
            [-tx, -ty, z1], [tx, -ty, z1], [tx, ty, z1], [-tx, ty, z1],
        ]
    )  # fmt: skip
    faces = np.array(
        [
            [0, 2, 1], [0, 3, 2],  # bottom
            [4, 5, 6], [4, 6, 7],  # top
            [0, 1, 5], [0, 5, 4],
            [1, 2, 6], [1, 6, 5],
            [2, 3, 7], [2, 7, 6],
            [3, 0, 4], [3, 4, 7],
        ]
    )  # fmt: skip
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _material(finish: Finish) -> PBRMaterial:
    return PBRMaterial(
        name=finish.name,
        baseColorFactor=[int(round(c * 255)) for c in finish.rgba],
        metallicFactor=finish.metallic,
        roughnessFactor=finish.roughness,
    )


def scene(parts: Parts) -> trimesh.Scene:
    """One flat-shaded mesh per finish, in the parts table's order."""
    result = trimesh.Scene()
    for finish, meshes in parts.items():
        if not meshes:
            continue
        mesh = trimesh.util.concatenate(meshes)
        mesh.vertices = np.round(mesh.vertices, _DECIMALS)
        # One vertex per face corner, so every face is flat-shaded: a box with
        # shared corners gets averaged normals and renders like a pillow.
        mesh.unmerge_vertices()
        mesh.visual = trimesh.visual.TextureVisuals(material=_material(finish))
        result.add_geometry(mesh, node_name=finish.name, geom_name=finish.name)
    return result


def glb(parts: Parts) -> bytes:
    return trimesh.exchange.gltf.export_glb(scene(parts), include_normals=True)
