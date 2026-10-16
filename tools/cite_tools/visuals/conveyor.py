"""A belt conveyor's visual mesh, generated inside the type's collision box (ADR-0079).

WHAT IT DRAWS. An industrial belt conveyor: two anodised-aluminium side frames,
a black rubber belt running over a drum at each end with its return run below,
four 40 x 40 profile legs with longitudinal and transverse braces and levelling
feet, a geared motor slung under the drive (outfeed, +x) end, and a small
safety-yellow control box with a red stop cap on one infeed leg.

WHAT IT READS. The envelope is the body's collision box, read from the L0 type
and never restated (P1). The mesh origin is the box CENTRE, because that is where
the scene template places a body's visual (half a height above the foot). The
belt's top face is the box's top face, ``+size_z / 2``, which is the 0.600 m the
type's ``surface``, ``infeed`` and ``outfeed`` frames already name: a part the
belt carries sits on the drawn belt. Nothing drawn rises above it, so the side
frames stop just short of the belt surface.

WHAT IT DOES NOT DO. It touches no collision, inertia, frame or plugin. The
proportions below are appearance — a plausible conveyor, not a survey of the
lab's QCON-24 — and the layout stays ``PROVISIONAL``.

WHICH FILES. Every conveyor type whose body visual is a mesh: the URI in the
model names the file, so the model says *which* conveyors wear one and this
module says only *how* one is drawn (P5).

DETERMINISM. The GLB is committed and checked byte for byte against a fresh
generation, as the derived hulls are (ADR-0028). Vertices are rounded to the
micrometre before export so that a last-bit difference in a platform's ``sin``
cannot reach the file, parts are concatenated in a fixed order, and node and
material names are fixed strings.

Usage::

    python -m cite_tools.visuals.conveyor           # check the committed files
    python -m cite_tools.visuals.conveyor --write   # regenerate them
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

from cite_tools.model.loader import FacilityModel, load
from cite_tools.visuals import VisualMeshError, asset_path

#: The category whose visual meshes this module draws.
CATEGORY = "conveyor"

# --------------------------------------------------------------------------- #
# Proportions. Appearance only; every one is checked to fit the envelope.
# --------------------------------------------------------------------------- #
FRAME_THICKNESS_M = 0.030  # side extrusion, across the belt
FRAME_DEPTH_M = 0.090  # side extrusion, vertical
FRAME_BELOW_BELT_M = 0.002  # the frames stop this far under the belt surface
BELT_THICKNESS_M = 0.006
DRUM_RADIUS_M = 0.035
PROFILE_M = 0.040  # 40 x 40 legs and braces
LEG_INSET_X_M = 0.120  # leg centre from each belt end
BRACE_HEIGHT_M = 0.150  # brace centre above the floor
FOOT_PAD_RADIUS_M = 0.026
FOOT_PAD_HEIGHT_M = 0.012
FOOT_STEM_RADIUS_M = 0.008
FOOT_STEM_HEIGHT_M = 0.030
GEARBOX_SIZE_M = (0.090, 0.090, 0.090)
MOTOR_RADIUS_M = 0.036
MOTOR_LENGTH_M = 0.150
MOTOR_CAP_LENGTH_M = 0.020
CONTROL_BOX_SIZE_M = (0.060, 0.070, 0.120)  # x (depth), y, z
STOP_CAP_RADIUS_M = 0.016
STOP_CAP_LENGTH_M = 0.012
STOP_COLLAR_RADIUS_M = 0.022
STOP_COLLAR_LENGTH_M = 0.004
SECTIONS = 32  # facets around every cylinder

#: Micrometre rounding before export (see DETERMINISM above).
_DECIMALS = 6


@dataclass(frozen=True)
class _Finish:
    name: str
    rgba: tuple[float, float, float, float]
    metallic: float
    roughness: float


ALUMINIUM = _Finish("anodised_aluminium", (0.70, 0.72, 0.74, 1.0), 0.0, 0.50)
RUBBER = _Finish("belt_rubber", (0.18, 0.18, 0.19, 1.0), 0.0, 0.90)
MOTOR = _Finish("motor_grey", (0.40, 0.42, 0.45, 1.0), 0.0, 0.55)
SAFETY_YELLOW = _Finish("safety_yellow", (0.95, 0.75, 0.05, 1.0), 0.0, 0.50)
STOP_RED = _Finish("stop_red", (0.80, 0.05, 0.04, 1.0), 0.0, 0.40)
FEET = _Finish("foot_black", (0.15, 0.15, 0.15, 1.0), 0.0, 0.70)

# Every finish is dielectric (metallic 0). The cell's worlds give a PBR metal no
# environment map to reflect, so a metallic finish renders near black in Gazebo;
# the aluminium reads as aluminium through a light grey instead.

#: Export order. Fixed, so the GLB's node and buffer order cannot drift.
FINISHES = (ALUMINIUM, RUBBER, MOTOR, SAFETY_YELLOW, STOP_RED, FEET)


@dataclass(frozen=True)
class Target:
    """One conveyor type that wears a generated visual mesh."""

    type_id: str
    size_m: tuple[float, float, float]
    path: Path


def _box(
    extents: tuple[float, float, float], centre: tuple[float, float, float]
) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(centre)
    return mesh


def _cylinder(
    radius: float, length: float, centre: tuple[float, float, float], axis: str
) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=SECTIONS)
    if axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    elif axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    mesh.apply_translation(centre)
    return mesh


def _parts(size_m: tuple[float, float, float]) -> dict[_Finish, list[trimesh.Trimesh]]:
    """Every part, grouped by finish, in the box-centred frame."""
    length, width, height = size_m
    hx, hy, hz = length / 2.0, width / 2.0, height / 2.0
    parts: dict[_Finish, list[trimesh.Trimesh]] = {finish: [] for finish in FINISHES}

    # Side frames: the full length, outer face on the envelope, top just under the belt.
    frame_top = hz - FRAME_BELOW_BELT_M
    frame_z = frame_top - FRAME_DEPTH_M / 2.0
    frame_y = hy - FRAME_THICKNESS_M / 2.0
    for side in (-1.0, 1.0):
        parts[ALUMINIUM].append(
            _box((length, FRAME_THICKNESS_M, FRAME_DEPTH_M), (0.0, side * frame_y, frame_z))
        )

    # Belt: carrying run on top (its top face IS the envelope top), drums at both
    # ends, return run underneath. The drums are belt-covered, so they are rubber.
    belt_width = width - 2.0 * FRAME_THICKNESS_M
    drum_x = hx - DRUM_RADIUS_M
    drum_z = hz - DRUM_RADIUS_M
    run = 2.0 * drum_x
    parts[RUBBER].append(
        _box((run, belt_width, BELT_THICKNESS_M), (0.0, 0.0, hz - BELT_THICKNESS_M / 2.0))
    )
    parts[RUBBER].append(
        _box(
            (run, belt_width, BELT_THICKNESS_M),
            (0.0, 0.0, drum_z - DRUM_RADIUS_M + BELT_THICKNESS_M / 2.0),
        )
    )
    for side in (-1.0, 1.0):
        parts[RUBBER].append(
            _cylinder(DRUM_RADIUS_M, belt_width, (side * drum_x, 0.0, drum_z), "y")
        )
    # Drum shafts, through the side frames.
    for side in (-1.0, 1.0):
        parts[ALUMINIUM].append(_cylinder(0.010, width, (side * drum_x, 0.0, drum_z), "y"))

    # Legs, from the top of the levelling foot to the underside of the frame.
    frame_bottom = frame_top - FRAME_DEPTH_M
    foot_top = -hz + FOOT_PAD_HEIGHT_M + FOOT_STEM_HEIGHT_M
    leg_length = frame_bottom - foot_top
    leg_z = foot_top + leg_length / 2.0
    leg_x = hx - LEG_INSET_X_M
    leg_y = hy - PROFILE_M / 2.0 - 0.010
    legs = [(sx * leg_x, sy * leg_y) for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)]
    for x, y in legs:
        parts[ALUMINIUM].append(_box((PROFILE_M, PROFILE_M, leg_length), (x, y, leg_z)))
        parts[FEET].append(
            _cylinder(
                FOOT_PAD_RADIUS_M, FOOT_PAD_HEIGHT_M, (x, y, -hz + FOOT_PAD_HEIGHT_M / 2.0), "z"
            )
        )
        parts[ALUMINIUM].append(
            _cylinder(
                FOOT_STEM_RADIUS_M,
                FOOT_STEM_HEIGHT_M,
                (x, y, -hz + FOOT_PAD_HEIGHT_M + FOOT_STEM_HEIGHT_M / 2.0),
                "z",
            )
        )

    # Braces: one along each side between its legs, one across at each end.
    brace_z = -hz + BRACE_HEIGHT_M
    for sy in (-1.0, 1.0):
        parts[ALUMINIUM].append(
            _box((2.0 * leg_x - PROFILE_M, PROFILE_M, PROFILE_M), (0.0, sy * leg_y, brace_z))
        )
    for sx in (-1.0, 1.0):
        parts[ALUMINIUM].append(
            _box((PROFILE_M, 2.0 * leg_y - PROFILE_M, PROFILE_M), (sx * leg_x, 0.0, brace_z))
        )
    # A cross member under the frames at each end, which carries the drive.
    for sx in (-1.0, 1.0):
        parts[ALUMINIUM].append(
            _box(
                (PROFILE_M, width - 2.0 * FRAME_THICKNESS_M, PROFILE_M),
                (sx * leg_x, 0.0, frame_bottom - PROFILE_M / 2.0),
            )
        )

    # Drive: a right-angle gearbox under the outfeed drum, motor pointing inboard.
    gx, gy, gz = GEARBOX_SIZE_M
    gearbox_x = hx - gx / 2.0 - 0.015
    gearbox_z = frame_bottom - PROFILE_M - gz / 2.0
    parts[MOTOR].append(_box(GEARBOX_SIZE_M, (gearbox_x, 0.0, gearbox_z)))
    motor_x = gearbox_x - gx / 2.0 - MOTOR_LENGTH_M / 2.0
    parts[MOTOR].append(_cylinder(MOTOR_RADIUS_M, MOTOR_LENGTH_M, (motor_x, 0.0, gearbox_z), "x"))
    cap_x = motor_x - MOTOR_LENGTH_M / 2.0 - MOTOR_CAP_LENGTH_M / 2.0
    parts[FEET].append(
        _cylinder(MOTOR_RADIUS_M * 0.85, MOTOR_CAP_LENGTH_M, (cap_x, 0.0, gearbox_z), "x")
    )
    # A mounting plate tying the gearbox to the cross member above it.
    parts[ALUMINIUM].append(
        _box((0.008, gy, PROFILE_M), (gearbox_x - gx / 2.0 - 0.004, 0.0, gearbox_z + gz / 2.0))
    )

    # Control box, on the outboard (infeed, -x) face of the infeed leg at +y,
    # facing out along the belt so the stop cap is reachable from the infeed end.
    bx, by, bz = CONTROL_BOX_SIZE_M
    box_x = -leg_x - PROFILE_M / 2.0 - bx / 2.0
    box_y = hy - by / 2.0 - 0.005
    box_z = 0.0
    parts[SAFETY_YELLOW].append(_box(CONTROL_BOX_SIZE_M, (box_x, box_y, box_z)))
    face_x = box_x - bx / 2.0
    parts[SAFETY_YELLOW].append(
        _cylinder(
            STOP_COLLAR_RADIUS_M,
            STOP_COLLAR_LENGTH_M,
            (face_x - STOP_COLLAR_LENGTH_M / 2.0, box_y, box_z + bz / 4.0),
            "x",
        )
    )
    parts[STOP_RED].append(
        _cylinder(
            STOP_CAP_RADIUS_M,
            STOP_CAP_LENGTH_M,
            (face_x - STOP_COLLAR_LENGTH_M - STOP_CAP_LENGTH_M / 2.0, box_y, box_z + bz / 4.0),
            "x",
        )
    )
    return parts


def _material(finish: _Finish) -> PBRMaterial:
    return PBRMaterial(
        name=finish.name,
        baseColorFactor=[int(round(c * 255)) for c in finish.rgba],
        metallicFactor=finish.metallic,
        roughnessFactor=finish.roughness,
    )


def build(size_m: tuple[float, float, float]) -> trimesh.Scene:
    """The conveyor as a scene: one flat-shaded mesh per finish."""
    scene = trimesh.Scene()
    for finish, meshes in _parts(size_m).items():
        if not meshes:
            continue
        mesh = trimesh.util.concatenate(meshes)
        mesh.vertices = np.round(mesh.vertices, _DECIMALS)
        # One vertex per face corner, so every face is flat-shaded: a box with
        # shared corners gets averaged normals and renders like a pillow.
        mesh.unmerge_vertices()
        mesh.visual = trimesh.visual.TextureVisuals(material=_material(finish))
        scene.add_geometry(mesh, node_name=finish.name, geom_name=finish.name)
    return scene


def glb_bytes(size_m: tuple[float, float, float]) -> bytes:
    """The GLB the committed file must equal."""
    return trimesh.exchange.gltf.export_glb(build(size_m), include_normals=True)


def targets(model: FacilityModel, repo_root: Path) -> list[Target]:
    """Every conveyor type whose body wears a mesh visual, sorted by id."""
    found = []
    for asset_type in sorted(model.types, key=lambda t: t.id):
        body = asset_type.description.body
        if asset_type.category != CATEGORY or body is None or body.visual.kind != "mesh":
            continue
        if body.collision.kind != "box":
            raise VisualMeshError(
                f"{asset_type.id}: a generated conveyor visual fills the collision box, "
                f"and this collision is a {body.collision.kind}"
            )
        if tuple(body.visual.scale) != (1.0, 1.0, 1.0):
            raise VisualMeshError(
                f"{asset_type.id}: the generated visual is drawn at the collision box's "
                "size, so a scale other than 1 would draw it at another"
            )
        x, y, z = body.collision.size_m
        found.append(
            Target(
                type_id=asset_type.id,
                size_m=(x, y, z),
                path=asset_path(repo_root, body.visual.uri),
            )
        )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cite_tools.visuals.conveyor", description=__doc__.split("\n")[0]
    )
    parser.add_argument("--model", type=Path, default=Path("model"), help="the model/ directory")
    parser.add_argument("--write", action="store_true", help="rewrite the committed meshes")
    args = parser.parse_args(argv)

    repo_root = args.model.resolve().parent
    problems = []
    found = targets(load(args.model), repo_root)
    for target in found:
        fresh = glb_bytes(target.size_m)
        shown = target.path.relative_to(repo_root)
        if args.write:
            target.path.parent.mkdir(parents=True, exist_ok=True)
            target.path.write_bytes(fresh)
            print(f"wrote {shown} ({target.type_id})")
        elif not target.path.is_file():
            problems.append(f"{shown}: missing ({target.type_id})")
        elif target.path.read_bytes() != fresh:
            problems.append(f"{shown}: differs from a fresh generation ({target.type_id})")
    for problem in problems:
        print(f"error {problem}", file=sys.stderr)
    if not args.write and not problems:
        print(f"ok {len(found)} conveyor visual mesh(es) match a fresh generation")
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())
