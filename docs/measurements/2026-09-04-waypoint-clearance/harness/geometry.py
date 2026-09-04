#!/usr/bin/env python3
"""I11 and the distance computation of `criteria.md` section 4.3, in pure `numpy`.

WRITTEN FOR THIS CAMPAIGN. Nothing here is copied from another campaign directory, because
none of them contains a geometry instrument: `criteria.md` section 2.5 records that
ADR-0028's audit script was never committed, so **there is no audit code to extend and
nothing to inherit**, and section 4.3 registers a host-side computation over the two
committed STL sets and the scene's box primitives as the choice.

WHY HOST-SIDE, in one line each (section 4.3 has the full reasoning): `moveit_py` is not
installed in this image; a `moveit_core`-linked C++ probe would be a new package and section
0 confines this campaign's code to `harness/`; `GetStateValidity` returns a boolean and
contacts, not a distance; and a pure function of committed files is what makes REPRO1
possible.

WHAT IS EXACT AND WHAT IS A BOUND -- the distinction this whole file turns on.

  * **The distance is exact.** A triangle and a box are two convex sets, so the minimum
    distance between them is attained at a (vertex, feature) or an (edge, edge) pair, and
    all of those are enumerated in closed form below. There is no iteration and no tolerance.
  * **The culling is a BOUND, never an approximation.** `dist(centroid, box) - circumradius`
    is a valid lower bound on every point of a triangle, so a triangle whose bound exceeds an
    already-achieved distance cannot hold the minimum and is skipped. Skipping it changes no
    answer. The same is true of `censoring_bound` and of `motion_bound`.
  * **Penetration is reported as `0` with a flag and never as a signed depth**, because a
    penetration depth between a triangle soup and a box is not a single well-defined
    quantity (section 4.3).

THE RESIDUAL THIS ACHIEVES IS MEASURED AND NOT ASSERTED. `self_test()` below checks the
kernel against an INDEPENDENT method that shares no code with it -- the convex quadratic
programme `min ||z||` over `conv({t_i - b_j})`, which is the Minkowski difference of the two
hulls -- plus three analytic configurations. It is run by `compute.py` on every invocation
and its worst residual travels ON the record, so no figure in this campaign rests on a
tolerance claim nobody re-measured.
"""

from __future__ import annotations

import math
import re
import struct
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------


def load_stl(path: Path) -> np.ndarray:
    """One binary STL as an `(n, 3, 3)` array of float64 vertices, in metres.

    Binary only, and deliberately: both committed sets are binary (`struct` header check
    below), the URDF carries **no `scale` attribute** on any of the 13 `<mesh>` elements, and
    the vendor macro emits none -- so the file's own units are the link frame's metres and
    nothing is rescaled here. An ASCII file raises rather than being guessed at.
    """
    blob = path.read_bytes()
    if len(blob) < 84:
        raise ValueError(f"{path} is too short to be a binary STL")
    count = struct.unpack("<I", blob[80:84])[0]
    if len(blob) != 84 + 50 * count:
        raise ValueError(
            f"{path} is not a binary STL: header declares {count} triangles, which needs "
            f"{84 + 50 * count} bytes and the file has {len(blob)}"
        )
    records = np.frombuffer(blob, dtype=np.uint8, count=50 * count, offset=84)
    records = records.reshape(count, 50)
    vertices = np.ascontiguousarray(records[:, 12:48]).view("<f4")
    return vertices.reshape(count, 3, 3).astype(np.float64)


class Mesh:
    """One collision mesh, with the quantities the broad phase and the culling need.

    `radius` is the maximum vertex distance from the LINK ORIGIN, which section 2.3 verifies
    is **identical between the two sets to 0.000e+00 m** -- the property that makes the broad
    phase symmetric, so censoring can never manufacture or hide a difference.
    """

    __slots__ = ("path", "vertices", "centroids", "circumradii", "radius", "aabb")

    def __init__(self, path: Path) -> None:
        self.path = path
        self.vertices = load_stl(path)
        self.centroids = self.vertices.mean(axis=1)
        offsets = self.vertices - self.centroids[:, None, :]
        self.circumradii = np.sqrt((offsets * offsets).sum(-1)).max(axis=1)
        points = self.vertices.reshape(-1, 3)
        self.radius = float(np.sqrt((points * points).sum(-1)).max())
        self.aabb = (points.min(axis=0), points.max(axis=0))

    @property
    def triangles(self) -> int:
        return int(self.vertices.shape[0])


def mesh_relative_path(uri: str, hull_reference: str) -> str | None:
    """The path BELOW the collision root, which is identical in both sets (section 2.3).

    The description read back off the running node carries a resolved `file://` or
    `package://` URI ending in `.../meshes/collision/xarm5/convex_hull/<relative>`. That
    suffix is the only part the substitution uses, and returning `None` for a reference that
    does not carry it is what makes an unexpected root a loud failure rather than a silent
    fallback to the wrong geometry.
    """
    marker = hull_reference.split("/", 1)[1] if "/" in hull_reference else hull_reference
    index = uri.find(marker)
    if index < 0:
        return None
    return uri[index + len(marker):].lstrip("/")


# ---------------------------------------------------------------------------
# Rigid transforms
# ---------------------------------------------------------------------------


def rotation_from_rpy(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """URDF's fixed-axis roll-pitch-yaw, as `Rz @ Ry @ Rx`.

    The convention is URDF's own and is stated here rather than inherited, because getting it
    wrong is exactly the "silently wrong frame convention" I12 exists to catch (section 4.2).
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ]
    )


def rotation_from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    """Rodrigues, for a revolute joint about its declared axis."""
    norm = float(np.linalg.norm(axis))
    if norm == 0.0:
        return np.eye(3)
    unit = axis / norm
    c, s = math.cos(angle), math.sin(angle)
    cross = np.array(
        [[0.0, -unit[2], unit[1]], [unit[2], 0.0, -unit[0]], [-unit[1], unit[0], 0.0]]
    )
    return np.eye(3) + s * cross + (1.0 - c) * (cross @ cross)


def quaternion_to_rotation(x: float, y: float, z: float, w: float) -> np.ndarray:
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0.0:
        return np.eye(3)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def rotation_angle(first: np.ndarray, second: np.ndarray) -> float:
    """The angle of the rotation carrying `first` onto `second`. FK1's angular residual."""
    relative = first.T @ second
    trace = float(np.clip((np.trace(relative) - 1.0) / 2.0, -1.0, 1.0))
    return math.acos(trace)


# ---------------------------------------------------------------------------
# I11 -- forward kinematics from the description that actually ran
# ---------------------------------------------------------------------------


class Joint:
    __slots__ = ("name", "type", "parent", "child", "xyz", "rotation", "axis",
                 "mimic_joint", "mimic_multiplier", "mimic_offset", "limit")

    def __init__(self, element: ElementTree.Element) -> None:
        self.name = element.get("name", "")
        self.type = element.get("type", "fixed")
        self.parent = element.find("parent").get("link")  # type: ignore[union-attr]
        self.child = element.find("child").get("link")  # type: ignore[union-attr]
        origin = element.find("origin")
        xyz = _floats(origin.get("xyz") if origin is not None else None, (0.0, 0.0, 0.0))
        rpy = _floats(origin.get("rpy") if origin is not None else None, (0.0, 0.0, 0.0))
        self.xyz = np.array(xyz)
        self.rotation = rotation_from_rpy(*rpy)
        axis = element.find("axis")
        self.axis = np.array(_floats(axis.get("xyz") if axis is not None else None,
                                     (1.0, 0.0, 0.0)))
        mimic = element.find("mimic")
        # Section 4.2: FIVE of the six moving gripper joints are `<mimic>` followers of the
        # drive joint at multiplier 1 and offset 0. An implementation reading only origins,
        # axes and types would place all five at zero and disagree with I12 BY CONSTRUCTION.
        self.mimic_joint = mimic.get("joint") if mimic is not None else None
        self.mimic_multiplier = float(mimic.get("multiplier", 1.0)) if mimic is not None else 1.0
        self.mimic_offset = float(mimic.get("offset", 0.0)) if mimic is not None else 0.0
        limit = element.find("limit")
        self.limit = (
            (float(limit.get("lower", 0.0)), float(limit.get("upper", 0.0)))
            if limit is not None
            else None
        )


def _floats(text: str | None, default) -> tuple:
    if not text:
        return tuple(float(value) for value in default)
    return tuple(float(value) for value in text.split())


class RobotModel:
    """The kinematic chain, the collision meshes and their origins, from ONE URDF string.

    The URDF is the description **read back off the running node** (I3), not a fresh `xacro`
    expansion: it is what the cell that produced these trajectories actually planned against,
    and V1's rule that a validity reading travels on the record applies to it like any other.
    """

    def __init__(self, urdf: str) -> None:
        root = ElementTree.fromstring(urdf)
        self.name = root.get("name", "")
        self.joints = [Joint(element) for element in root.findall("joint")]
        self.by_name = {joint.name: joint for joint in self.joints}
        self.children: dict[str, list[Joint]] = {}
        for joint in self.joints:
            self.children.setdefault(joint.parent, []).append(joint)
        links = [element.get("name", "") for element in root.findall("link")]
        parented = {joint.child for joint in self.joints}
        roots = [link for link in links if link not in parented]
        if len(roots) != 1:
            raise ValueError(f"expected exactly one root link, found {roots}")
        self.root = roots[0]
        self.links = links

        # The 13 links carrying a `<collision>` element, each exactly one `<mesh>`
        # (section 2.3). The origin is read rather than assumed to be identity -- section 2.3
        # records that all 13 are `0 0 0`, and this reads them so that a change is a finding.
        self.collision: dict[str, dict] = {}
        for element in root.findall("link"):
            collision = element.find("collision")
            if collision is None:
                continue
            mesh = collision.find("geometry/mesh")
            if mesh is None:
                continue
            origin = collision.find("origin")
            xyz = _floats(origin.get("xyz") if origin is not None else None, (0.0, 0.0, 0.0))
            rpy = _floats(origin.get("rpy") if origin is not None else None, (0.0, 0.0, 0.0))
            self.collision[element.get("name", "")] = {
                "uri": mesh.get("filename", ""),
                "xyz": np.array(xyz),
                "rpy": list(rpy),
                "rotation": rotation_from_rpy(*rpy),
                "scale": mesh.get("scale"),
            }

        self.movable = [
            joint.name
            for joint in self.joints
            if joint.type in ("revolute", "continuous", "prismatic")
            and joint.mimic_joint is None
        ]
        self.mimics = {
            joint.name: joint.mimic_joint
            for joint in self.joints
            if joint.mimic_joint is not None
        }

    def resolve(self, positions: dict[str, float]) -> dict[str, float]:
        """Complete a configuration with every `<mimic>` follower's own value.

        Section 5.4: a configuration that moves the drive joint and leaves the five followers
        behind is **not a pose this gripper can take**, and neither GRIP1 nor I11 may produce
        one. A follower explicitly named in the input is overwritten by its coupling, which is
        the only way to guarantee that.
        """
        resolved = dict(positions)
        for name, leader in self.mimics.items():
            joint = self.by_name[name]
            if leader in resolved:
                resolved[name] = resolved[leader] * joint.mimic_multiplier + joint.mimic_offset
        return resolved

    def link_poses(self, positions: dict[str, float]) -> dict[str, tuple]:
        """Every link's `(rotation, translation)` in the model's own ROOT frame.

        Iterative rather than recursive, so a deep chain cannot exhaust the stack, and it
        touches every link exactly once.
        """
        resolved = self.resolve(positions)
        poses = {self.root: (np.eye(3), np.zeros(3))}
        stack = [self.root]
        while stack:
            parent = stack.pop()
            rotation, translation = poses[parent]
            for joint in self.children.get(parent, ()):
                local = joint.rotation
                if joint.type in ("revolute", "continuous"):
                    local = local @ rotation_from_axis_angle(
                        joint.axis, resolved.get(joint.name, 0.0)
                    )
                    offset = joint.xyz
                elif joint.type == "prismatic":
                    offset = joint.xyz + joint.axis * resolved.get(joint.name, 0.0)
                else:
                    offset = joint.xyz
                poses[joint.child] = (rotation @ local, rotation @ offset + translation)
                stack.append(joint.child)
        return poses

    def joint_reach(self, radii: dict[str, float]) -> dict[str, dict[str, float]]:
        """A STATIC upper bound on how far a point of each link can be from each joint axis.

        Used only by `motion_bound`, and it is a bound and never an estimate.

        `reach[link][j]` is the sum of the joint-origin offsets over the joints STRICTLY
        BETWEEN `j` and `link`, **plus that link's own maximum vertex radius** from `radii`.
        Both terms are load-bearing and each was wrong before 2026-09-04:

          * A URDF child link's frame IS its parent joint's frame, so the offset sum for the
            link's own parent joint is ZERO and the whole bound for that joint is the mesh
            radius. Accumulating the joint's own `xyz` shifted every entry by one joint, and
            omitting the radius left `reach[link2][joint2] = 0.0` against a mesh radius of
            0.3385 m -- so `motion_bound` returned zero for every interval in which only
            `joint2` moved, and `compute.py` skipped every `link2` pair in it.
          * `dist(point, axis_j) <= dist(point, origin_j) <= (offset sum) + radius`, and each
            intervening transform is a rotation about a point at most that far away, so the
            sum bounds the displacement of any point of the link under any rotation of `j`.

        Measured on the shipped `arm_1` against a brute force over the shakedown's own
        62-waypoint capture: the pre-fix values were exceeded by the ACTUAL displacement on
        `link3` (0.011686 m against a bound of 0.009040 m) and on `link2` (0.002609 m against
        0.000000 m). `radii` is REQUIRED rather than defaulted, because a default of zero is
        exactly the unsound bound this signature exists to make impossible to write.
        """
        missing = sorted(set(self.collision) - set(radii))
        if missing:
            raise ValueError(
                f"joint_reach needs a mesh radius for every collision link; missing {missing}"
            )
        parent_of = {joint.child: joint for joint in self.joints}
        chain: dict[str, list[str]] = {}
        for link in self.links:
            names: list[str] = []
            cursor = link
            while cursor in parent_of:
                joint = parent_of[cursor]
                names.append(joint.name)
                cursor = joint.parent
            chain[link] = names
        reach: dict[str, dict[str, float]] = {}
        for link, names in chain.items():
            # The radius of the link's own collision mesh about its ORIGIN. A link carrying no
            # collision element is not in `radii` and is not a link this campaign measures;
            # `motion_bound` is never asked about one, and a zero there would be unsound, so
            # such a link is given no entry at all rather than a zero one.
            if link not in radii:
                continue
            accumulated = float(radii[link])
            per_joint: dict[str, float] = {}
            for name in names:  # walked from the link outward toward the root
                # `j` is not yet part of the sum: the offset between `j`'s frame and the link's
                # is the sum over the joints already walked, which is exactly "strictly
                # between".
                per_joint[name] = accumulated
                accumulated += float(np.linalg.norm(self.by_name[name].xyz))
            reach[link] = per_joint
        return reach


# ---------------------------------------------------------------------------
# The exact triangle-to-box distance
# ---------------------------------------------------------------------------

_CORNER_SIGNS = np.array(
    [[sx, sy, sz] for sx in (-1.0, 1.0) for sy in (-1.0, 1.0) for sz in (-1.0, 1.0)]
)
_BOX_EDGES = np.array(
    [
        (i, j)
        for i in range(8)
        for j in range(i + 1, 8)
        if np.count_nonzero(_CORNER_SIGNS[i] != _CORNER_SIGNS[j]) == 1
    ]
)


def point_box_distance(points: np.ndarray, half: np.ndarray) -> np.ndarray:
    """Exterior distance from points to an origin-centred axis-aligned box. 0 inside."""
    outside = np.maximum(np.abs(points) - half, 0.0)
    return np.sqrt(np.sum(outside * outside, axis=-1))


def point_triangle_distance(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Distance from points `(..., 3)` to triangles `(..., 3, 3)`, broadcast together.

    The seven Voronoi regions of a triangle in closed form. Every branch is evaluated and
    selected with `where` rather than taken, because the arrays are large and the shapes are
    broadcast; the arithmetic is identical to the branching form.
    """
    a, b, c = triangles[..., 0, :], triangles[..., 1, :], triangles[..., 2, :]
    ab, ac = b - a, c - a
    ap, bp, cp = points - a, points - b, points - c
    d1 = np.sum(ab * ap, axis=-1)
    d2 = np.sum(ac * ap, axis=-1)
    d3 = np.sum(ab * bp, axis=-1)
    d4 = np.sum(ac * bp, axis=-1)
    d5 = np.sum(ab * cp, axis=-1)
    d6 = np.sum(ac * cp, axis=-1)

    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4

    denom_ab = np.where(d1 - d3 != 0.0, d1 - d3, 1.0)
    denom_ac = np.where(d2 - d6 != 0.0, d2 - d6, 1.0)
    denom_bc = np.where((d4 - d3) + (d5 - d6) != 0.0, (d4 - d3) + (d5 - d6), 1.0)
    denominator = va + vb + vc
    denom_safe = np.where(denominator != 0.0, denominator, 1.0)

    closest = np.broadcast_to(a, points.shape).copy()

    mask = (d1 <= 0.0) & (d2 <= 0.0)                                   # vertex a
    closest = np.where(mask[..., None], a, closest)
    done = mask

    mask = (~done) & (d3 >= 0.0) & (d4 <= d3)                          # vertex b
    closest = np.where(mask[..., None], b, closest)
    done = done | mask

    mask = (~done) & (d6 >= 0.0) & (d5 <= d6)                          # vertex c
    closest = np.where(mask[..., None], c, closest)
    done = done | mask

    mask = (~done) & (vc <= 0.0) & (d1 >= 0.0) & (d3 <= 0.0)           # edge ab
    closest = np.where(mask[..., None], a + (d1 / denom_ab)[..., None] * ab, closest)
    done = done | mask

    mask = (~done) & (vb <= 0.0) & (d2 >= 0.0) & (d6 <= 0.0)           # edge ac
    closest = np.where(mask[..., None], a + (d2 / denom_ac)[..., None] * ac, closest)
    done = done | mask

    mask = (~done) & (va <= 0.0) & ((d4 - d3) >= 0.0) & ((d5 - d6) >= 0.0)   # edge bc
    closest = np.where(
        mask[..., None], b + ((d4 - d3) / denom_bc)[..., None] * (c - b), closest
    )
    done = done | mask

    interior = a + (vb / denom_safe)[..., None] * ab + (vc / denom_safe)[..., None] * ac
    closest = np.where(~done[..., None], interior, closest)

    delta = points - closest
    return np.sqrt(np.sum(delta * delta, axis=-1))


def segment_segment_distance(p1, q1, p2, q2):
    """Distance between segments `[p1, q1]` and `[p2, q2]`, broadcast over leading axes."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a = np.sum(d1 * d1, axis=-1)
    e = np.sum(d2 * d2, axis=-1)
    f = np.sum(d2 * r, axis=-1)
    c = np.sum(d1 * r, axis=-1)
    b = np.sum(d1 * d2, axis=-1)

    denominator = a * e - b * b
    a_safe = np.where(a > 0.0, a, 1.0)
    e_safe = np.where(e > 0.0, e, 1.0)
    denom_safe = np.where(denominator > 0.0, denominator, 1.0)

    s = np.where(denominator > 0.0, np.clip((b * f - c * e) / denom_safe, 0.0, 1.0), 0.0)
    t = (b * s + f) / e_safe
    s = np.where(t < 0.0, np.clip(-c / a_safe, 0.0, 1.0), s)
    s = np.where(t > 1.0, np.clip((b - c) / a_safe, 0.0, 1.0), s)
    t = np.clip(t, 0.0, 1.0)
    s = np.where(a > 0.0, s, 0.0)
    t = np.where(e > 0.0, t, 0.0)

    delta = (p1 + s[..., None] * d1) - (p2 + t[..., None] * d2)
    return np.sqrt(np.sum(delta * delta, axis=-1))


def triangles_overlap_box(triangles: np.ndarray, half: np.ndarray) -> np.ndarray:
    """The thirteen-axis separating-axis test, per triangle, against an origin-centred box.

    Three box face normals, the triangle's own normal, and the nine edge cross products. A
    single separating axis proves disjointness; finding none proves overlap, because both
    bodies are convex.
    """
    v0, v1, v2 = triangles[:, 0, :], triangles[:, 1, :], triangles[:, 2, :]
    separated = np.zeros(triangles.shape[0], dtype=bool)

    for axis in range(3):
        low = np.minimum(np.minimum(v0[:, axis], v1[:, axis]), v2[:, axis])
        high = np.maximum(np.maximum(v0[:, axis], v1[:, axis]), v2[:, axis])
        separated |= (low > half[axis]) | (high < -half[axis])

    normal = np.cross(v1 - v0, v2 - v0)
    separated |= np.abs(np.sum(normal * v0, axis=-1)) > np.sum(np.abs(normal) * half, axis=-1)

    for edge in (v1 - v0, v2 - v1, v0 - v2):
        for axis in range(3):
            unit = np.zeros(3)
            unit[axis] = 1.0
            candidate = np.cross(unit, edge)
            projections = np.stack(
                [np.sum(candidate * vertex, axis=-1) for vertex in (v0, v1, v2)], axis=-1
            )
            radius = np.sum(np.abs(candidate) * half, axis=-1)
            separated |= (projections.min(axis=-1) > radius) | (
                projections.max(axis=-1) < -radius
            )
    return ~separated


def exact_triangle_box(triangles: np.ndarray, half: np.ndarray) -> np.ndarray:
    """Exact distance from DISJOINT triangles to an origin-centred box.

    For two disjoint convex polytopes the closest pair of points lies on a pair of features,
    and every such pair is one of: a triangle vertex against the box, a box corner against the
    triangle, or a triangle edge against a box edge. All three are enumerated.
    """
    count = triangles.shape[0]
    corners = _CORNER_SIGNS * half

    best = point_box_distance(triangles, half).min(axis=1)

    points = np.broadcast_to(corners[None, :, :], (count, 8, 3))
    expanded = np.broadcast_to(triangles[:, None, :, :], (count, 8, 3, 3))
    best = np.minimum(best, point_triangle_distance(points, expanded).min(axis=1))

    tri_p = triangles[:, [0, 1, 2], :][:, :, None, :]
    tri_q = triangles[:, [1, 2, 0], :][:, :, None, :]
    box_p = np.broadcast_to(corners[_BOX_EDGES[:, 0]][None, None, :, :], (count, 3, 12, 3))
    box_q = np.broadcast_to(corners[_BOX_EDGES[:, 1]][None, None, :, :], (count, 3, 12, 3))
    best = np.minimum(
        best, segment_segment_distance(tri_p, tri_q, box_p, box_q).min(axis=(1, 2))
    )
    return best


#: How many of the smallest-lower-bound triangles are evaluated exactly per tightening round,
#: and how many rounds are attempted. **Neither is a threshold and neither can change an
#: answer**: they trade compute against how quickly the sound bound tightens. Not registered
#: in `criteria.md` because `criteria.md` registers no property of the culling -- only that
#: the distance is exact, which `self_test` measures.
_SEED_BATCH = 16
_TIGHTENING_ROUNDS = 3


def mesh_box_distance(mesh: Mesh, matrix: np.ndarray, offset: np.ndarray,
                      half: np.ndarray) -> tuple[float, bool, int]:
    """Exact minimum distance from one collision mesh to one box, and whether it penetrates.

    `matrix` and `offset` carry the mesh's LINK frame into the box's own frame, so only the
    candidate triangles are ever transformed -- the mesh itself is transformed lazily and the
    full `(n, 3, 3)` array is never rotated. Returns `(distance, penetrating, triangle)`;
    `distance` is `0.0` when penetrating, per section 4.3.
    """
    centroids = mesh.centroids @ matrix + offset
    lower = np.maximum(point_box_distance(centroids, half) - mesh.circumradii, 0.0)

    count = lower.shape[0]
    upper = math.inf
    best_index = -1
    seen: set[int] = set()
    for _ in range(_TIGHTENING_ROUNDS):
        take = min(_SEED_BATCH, count)
        order = np.argpartition(lower, take - 1)[:take] if take < count else np.arange(count)
        fresh = [int(index) for index in order if int(index) not in seen]
        if not fresh:
            break
        seen.update(fresh)
        picked = np.array(fresh)
        transformed = mesh.vertices[picked] @ matrix + offset
        overlap = triangles_overlap_box(transformed, half)
        if overlap.any():
            return 0.0, True, int(picked[int(np.argmax(overlap))])
        exact = exact_triangle_box(transformed, half)
        local = int(np.argmin(exact))
        if float(exact[local]) < upper:
            upper = float(exact[local])
            best_index = int(picked[local])
        # Retire the evaluated triangles so the next round picks different ones, and shrink
        # the survivor set with the tightened bound. Both are bound operations: a triangle
        # whose lower bound exceeds an ACHIEVED distance cannot hold the minimum.
        lower = lower.copy()
        lower[picked] = math.inf
        if not (lower <= upper).any():
            return upper, False, best_index

    candidates = np.flatnonzero(lower <= upper)
    if candidates.size == 0:
        return upper, False, best_index
    transformed = mesh.vertices[candidates] @ matrix + offset
    overlap = triangles_overlap_box(transformed, half)
    if overlap.any():
        return 0.0, True, int(candidates[int(np.argmax(overlap))])
    exact = exact_triangle_box(transformed, half)
    local = int(np.argmin(exact))
    if float(exact[local]) < upper:
        return float(exact[local]), False, int(candidates[local])
    return upper, False, best_index


def censoring_bound(link_translation: np.ndarray, link_radius: float,
                    box_centre: np.ndarray, box_half: np.ndarray) -> float:
    """Rule M's broad phase: a sound LOWER bound on the (link, object) distance.

    The link is inside a sphere of `link_radius` about its own origin, and the box is inside a
    sphere of `|half|` about its centre, so the centre distance minus both radii cannot
    exceed the true distance. **Identical under both geometries** (section 2.3 verifies the
    origin radius agrees to 0.000e+00 m), which is what makes censoring symmetric.
    """
    gap = float(np.linalg.norm(link_translation - box_centre))
    return gap - link_radius - float(np.linalg.norm(box_half))


def motion_bound(model: RobotModel, link: str, deltas: dict[str, float],
                 reach: dict[str, dict[str, float]]) -> float:
    """A sound bound on how far any point of `link` moves over a joint-space interval.

    Sum over the joints of `|delta| * reach`, where `reach` bounds the distance from that
    joint's axis to any point of the link. Every intermediate configuration of a LINEAR
    joint-space interpolation differs from the start by at most the same sum, because each
    delta is scaled by `t` in `[0, 1]`.

    **It is a bound and it is used only to SKIP work.** If a pair's bracketing distance
    exceeds it, no sub-sample of that interval can reach contact, so the sub-sampling is
    provably unnecessary rather than heuristically skipped. Section 7.4's TUNNEL1 asks about
    a sub-sample distance reaching `<= 0`; this cannot hide one.
    """
    if link not in reach:
        # A zero bound skips work, so an absent link may NOT default to an empty table:
        # that is the shape that made `reach[link2][joint2] = 0.0` skip every `link2` pair.
        raise KeyError(
            f"motion_bound has no reach table for {link!r}; joint_reach was built without it"
        )
    per_joint = reach[link]
    total = 0.0
    for name, delta in deltas.items():
        if delta == 0.0:
            continue
        joint = model.by_name.get(name)
        if joint is None:
            continue
        if joint.type == "prismatic":
            total += abs(delta)
        else:
            # A joint that is not an ancestor of the link has no entry and moves no point of
            # it, so 0.0 is the SOUND value here and not a default standing in for a missing
            # one -- `reach[link]` carries every joint on the link's own chain to the root.
            total += abs(delta) * per_joint.get(name, 0.0)
    return total


# ---------------------------------------------------------------------------
# The residual, measured rather than asserted
# ---------------------------------------------------------------------------


def _independent_distance(triangle: np.ndarray, half: np.ndarray, rng) -> float:
    """`min ||z||` over `conv({t_i - b_j})` -- the Minkowski difference of the two hulls.

    `conv(A) - conv(B) = conv(A - B)`, so the distance between the triangle and the box is the
    norm of the smallest element of the convex hull of the 24 pairwise differences. That is a
    convex quadratic programme over a simplex, and it is solved here by **SciPy's SLSQP** --
    third-party code that shares no line with `exact_triangle_box`, enumerates no feature and
    knows nothing about triangles or boxes.

    Frank-Wolfe was tried first and REFUSED: its O(1/k) tail left a 7.3 mm residual on this
    problem, which would have made the check report the reference's convergence rather than
    the kernel's error. A reference that is worse than the thing it checks is not a check.
    """
    from scipy.optimize import minimize  # noqa: PLC0415 - self-test only; see `self_test`

    points = (triangle[:, None, :] - (_CORNER_SIGNS * half)[None, :, :]).reshape(-1, 3)
    gram = points @ points.T
    count = points.shape[0]
    constraints = [
        {"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(count)}
    ]
    best = math.inf
    for _ in range(5):
        start = rng.random(count)
        start /= start.sum()
        result = minimize(
            lambda w: float(w @ gram @ w),
            start,
            jac=lambda w: 2.0 * (gram @ w),
            bounds=[(0.0, 1.0)] * count,
            constraints=constraints,
            method="SLSQP",
            options={"maxiter": 500, "ftol": 1e-18},
        )
        best = min(best, float(result.fun))
    return math.sqrt(max(best, 0.0))


def self_test(trials: int = 120, seed: int = 20260904) -> dict:
    """Measure the kernel's residual against the independent method and three analytic cases.

    Run by `compute.py` on every invocation, with its worst residual travelling ON the
    record. `criteria.md` does not register a tolerance for the distance computation itself --
    it registers `DIFF_FLOOR` at 1e-9 m and REPRO1's 1e-12 m, and both are quantities this
    residual has to sit below for either to mean anything. **The number is reported and this
    function sets no threshold.**
    """
    rng = np.random.default_rng(seed)
    worst_random = 0.0
    disjoint = 0
    penetrating = 0
    try:
        import scipy  # noqa: F401, PLC0415 - probed, so a missing reference is a THIRD state

        reference_available = True
        reference_note = f"scipy {scipy.__version__} SLSQP"
    except ImportError:  # pragma: no cover - both named interpreters carry scipy
        reference_available = False
        reference_note = "scipy is absent: the independent check was NOT EVALUABLE here"
        trials = 0
    for _ in range(trials):
        half = rng.uniform(0.02, 0.6, 3)
        centre = rng.normal(0.0, 0.55, 3)
        triangle = centre + rng.normal(0.0, rng.uniform(0.05, 1.0), (3, 3))
        overlap = triangles_overlap_box(triangle[None], half)
        if overlap.any():
            penetrating += 1
            continue
        disjoint += 1
        mine = float(exact_triangle_box(triangle[None], half)[0])
        worst_random = max(worst_random, abs(mine - _independent_distance(triangle, half, rng)))

    analytic = []
    half = np.array([0.02, 0.02, 0.06])
    triangle = np.array([[0.5, 0.0, 0.0], [0.5, 0.1, 0.0], [0.5, 0.0, 0.1]])
    analytic.append(("face_normal", float(exact_triangle_box(triangle[None], half)[0]), 0.48))
    half = np.array([0.05, 0.05, 0.05])
    triangle = np.array([[0.1, 0.1, 0.1], [0.3, 0.2, 0.15], [0.25, 0.35, 0.4]])
    analytic.append(
        ("box_corner", float(exact_triangle_box(triangle[None], half)[0]),
         float(np.linalg.norm([0.05, 0.05, 0.05])))
    )
    half = np.array([0.1, 0.1, 0.1])
    triangle = np.array([[-1.0, 0.0, 0.2], [1.0, 0.0, 0.2], [0.0, 0.0, 0.2000001]])
    analytic.append(("edge_edge", float(exact_triangle_box(triangle[None], half)[0]), 0.1))

    worst_analytic = max(abs(measured - expected) for _, measured, expected in analytic)
    return {
        "method": "exact feature enumeration vs the convex QP over the Minkowski difference",
        "reference": reference_note,
        "reference_available": reference_available,
        "random_trials": trials,
        "random_disjoint": disjoint,
        "random_penetrating": penetrating,
        "worst_residual_vs_independent_m": worst_random if reference_available else None,
        "analytic": [
            {"case": name, "measured_m": measured, "expected_m": expected,
             "residual_m": abs(measured - expected)}
            for name, measured, expected in analytic
        ],
        "worst_analytic_residual_m": worst_analytic,
        "worst_residual_m": max(worst_random, worst_analytic),
        "numpy": np.__version__,
    }


def _strip_uri(uri: str) -> str:
    return re.sub(r"^(file://|package://)", "", uri)


if __name__ == "__main__":  # pragma: no cover - a convenience, not a stage
    import json

    print(json.dumps(self_test(), indent=2))
