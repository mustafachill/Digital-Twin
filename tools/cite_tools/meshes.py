"""Derived collision geometry: convex hulls of vendor meshes (ADR-0028).

This is the ``tools/`` pipeline stage ADR-0028 decision 1 names. It is host
agnostic like the rest of the L0 layer — it imports no ROS — and its only inputs
are the vendor mesh files the L0 model names and the L0 model itself.

**What it is for.** Twelve links per arm collide against their own rendering
mesh, because the vendor's ``xarm5.urdf.xacro`` sets ``collision_dir`` to
``visual_dir`` for the variant we model. CLAUDE.md §10 names that as a defect
class in its own right, and ADR-0028 records the decision: the collision surface
for a vendor-described link is a convex hull of the vendor's own mesh, derived
here rather than authored, so that the shape's source of truth is still the
vendor file (P1).

**What it is not.** It does not decide *which* geometry a description collides
against. That is L0 data — ``description.collision.select`` on the robot type —
and this module only produces the alternative so that the model has something to
select. Producing a hull and binding it are deliberately separate, because the
project ships the vendor meshes until the friction-grasp campaign has been re-run
against hulls (ADR-0028's amended promotion gate).

**Determinism.** ADR-0028 requires that a regenerated hull be byte-identical or
the change be real, which is what makes a committed derived asset checkable.
Everything below was learned by watching it fail rather than designed up front,
and the order matters — each step was added because the previous set was not
enough:

* The *input* is canonicalised — vertices deduplicated and lexicographically
  sorted — before Qhull sees it. A test that hulls the same cube with its
  triangles reversed is what showed this was needed: Qhull's split of a coplanar
  facet follows the order it received its points in.
* Each *facet* is re-triangulated here rather than taken as Qhull cut it, fanned
  from its own lexicographically smallest vertex. This is the one that mattered
  most and the one nothing local would have caught. With only the two steps above,
  three of the thirteen vendor meshes hashed differently between macOS and the
  Linux container on the *same* pinned scipy — identical hull vertex sets,
  identical face counts, different diagonals across the flat faces. Same solid,
  different bytes, and a committed asset that no CI run could reproduce.
* The triangles are then sorted, and the header is a fixed string. No path, no
  date, no version: every one of those would make the same input produce different
  bytes on a different machine.

**Two residuals are stated rather than hidden, and there were two only after
2026-08-31 — this block named the first and omitted the second.**

*Qhull could still merge facets differently between versions*, which would change
the polygons this module fans and therefore the file. That is a coarser and much
rarer disagreement than the diagonal one, and it did not occur across the two
platforms measured — **but read what those two platforms are before taking
comfort from it. They are macOS/arm64 and the Linux container on the same host:
two operating systems and ONE CPU architecture.** CI is x86_64, this branch has
never run there, and the axis on which floating-point results most plausibly
differ is the one carrying no observation at all. ``scipy`` is pinned exactly in
``requirements/tools.txt`` for this reason, and ``./scripts/hulls`` reports the
drift loudly rather than silently re-writing.

*This module has a sensitivity of its own*, and it is nearer than Qhull's.
``_fan`` orders a facet's vertices by their bearing about the facet centroid, so
two vertices at the same bearing to within floating-point error would swap and
the file would change. Measured rather than argued: across **all 19,471
consecutive-bearing gaps in all 13 hulls the tightest is 1.77e-8 rad**, roughly
**8e7 ULPs**, with **zero exact ties**. That is a wide margin and it is a reason
to expect stability, not a proof of it — and it is a property of *these thirteen
meshes*, which a vendor bump can change. Radius already breaks an exact tie (see
``_fan``); nothing breaks a near-tie, because nothing needs to at this margin.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: Bytes 0..79 of a binary STL. Fixed, because anything that varies between
#: machines — a path, a timestamp, a tool version — makes the same input produce
#: different bytes and destroys the property the whole stage exists to have.
STL_HEADER = b"cite convex hull (ADR-0028) - derived from a vendor mesh, do not edit"

_HEADER_BYTES = 80
_TRIANGLE_BYTES = 50


class MeshError(Exception):
    """A mesh file could not be read, or a hull could not be computed from it."""


@dataclass(frozen=True)
class HullRecord:
    """What one derived hull is, and what it was derived from.

    Every field is what ``assets/manifest.yaml`` records for the asset, so that a
    hull in the tree can be traced to the exact vendor file and checked without
    re-running the pipeline (ADR-0012's provenance requirement, applied to a
    derived asset rather than to a fetched one).
    """

    #: Path relative to the mesh root, identical in the vendor tree and in ours.
    #: The mirror is the mechanism: one root replaces another only if every
    #: relative path is the same on both sides.
    path: str
    source_sha256: str
    sha256: str
    source_triangles: int
    triangles: int
    source_bytes: int
    bytes: int


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_stl(path: Path) -> np.ndarray:
    """Return an ``(n, 3, 3)`` array of triangle vertices from a binary or ASCII STL.

    Read directly rather than through a mesh library on purpose: a library that
    welds, reorders or re-indexes vertices would put a transformation this module
    cannot see between the vendor's bytes and the hull's input, and the hull is
    supposed to be a function of the vendor's bytes.
    """
    data = path.read_bytes()
    if len(data) >= _HEADER_BYTES + 4:
        count = struct.unpack("<I", data[_HEADER_BYTES : _HEADER_BYTES + 4])[0]
        if len(data) == _HEADER_BYTES + 4 + count * _TRIANGLE_BYTES:
            body = np.frombuffer(data, dtype=np.uint8, offset=_HEADER_BYTES + 4).reshape(
                count, _TRIANGLE_BYTES
            )
            floats = body[:, :48].copy().view("<f4").reshape(count, 4, 3)
            return floats[:, 1:, :].astype(np.float64)

    vertices: list[list[float]] = []
    for line in data.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "vertex":
            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
    if not vertices or len(vertices) % 3 != 0:
        raise MeshError(f"{path} is neither a binary nor an ASCII STL")
    return np.asarray(vertices, dtype=np.float64).reshape(-1, 3, 3)


def convex_hull(triangles: np.ndarray) -> np.ndarray:
    """The convex hull of a mesh's vertices, canonically ordered.

    ``scipy`` is imported here rather than at module scope so that importing
    ``cite_tools.meshes`` — which the manifest reader and the tests do — costs
    nothing on a machine that only wants to read the provenance records.
    """
    try:
        from scipy.spatial import ConvexHull  # type: ignore[import-untyped,import-not-found]
    except ImportError as exc:  # pragma: no cover - a missing pin, not a code path
        raise MeshError(
            "scipy is required to compute a hull; it is pinned in requirements/tools.txt"
        ) from exc

    # Canonicalise the INPUT, not only the output. Qhull's triangulation of a
    # coplanar facet — and a machined part is mostly coplanar facets — follows the
    # order it received the points in, so sorting the faces afterwards is not
    # enough: the same solid presented with its triangles in a different order
    # produces a different, equally correct, split of each flat face. Deduplicating
    # and lexicographically sorting the vertices first makes the hull a function of
    # the point SET, which is the thing the vendor file actually describes.
    points = np.unique(triangles.reshape(-1, 3), axis=0)
    if points.shape[0] < 4:
        raise MeshError("a hull needs at least four vertices")
    try:
        hull = ConvexHull(points)
    except Exception as exc:  # pragma: no cover - degenerate vendor mesh
        raise MeshError(f"convex hull failed: {exc}") from exc

    # Re-triangulate every FACET rather than trusting Qhull's own split of it.
    # A facet of a convex hull is a planar polygon; Qhull returns it already cut
    # into triangles, and WHICH diagonal it cut along is not stable across
    # platforms. That was measured, not feared: the same scipy 1.14.1 on macOS and
    # in the Linux container produced an identical hull vertex set and an identical
    # face count for all thirteen vendor meshes, and differing bytes for three of
    # them. Same solid, different diagonals.
    #
    # Fanning each facet from its own lexicographically smallest vertex makes the
    # triangulation a function of the facet's vertex set, which is the part that
    # was observed to agree. It produces the same number of triangles Qhull's split
    # does (an n-gon is n-2 either way).
    facets: dict[tuple[float, ...], set[int]] = {}
    for simplex, equation in zip(hull.simplices, hull.equations, strict=True):
        facets.setdefault(tuple(equation), set()).update(int(i) for i in simplex)

    faces: list[np.ndarray] = []
    for equation, indices in facets.items():
        faces += _fan(points[sorted(indices)], np.asarray(equation[:3], dtype=np.float64))

    if not faces:  # pragma: no cover - Qhull raises before this
        raise MeshError("convex hull produced no faces")
    stacked = np.asarray(faces, dtype=np.float64)
    order = np.lexsort(stacked.reshape(len(stacked), 9).T[::-1])
    return stacked[order]


def _fan(vertices: np.ndarray, normal: np.ndarray) -> list[np.ndarray]:
    """Triangulate one planar convex facet, deterministically and outward.

    The vertices arrive as a set. They are ordered around the facet's centroid in
    the plane, rotated so the lexicographically smallest comes first, and fanned
    from it — so nothing about the order they arrived in survives into the result.

    The bearing comparison is this module's own determinism residual, and the
    module docstring carries its measured margin: the tightest consecutive-bearing
    gap across all thirteen committed hulls is 1.77e-8 rad, with no exact ties. Two
    vertices closer than floating-point noise would swap and change the file.
    """
    centre = vertices.mean(axis=0)
    # Any two orthogonal directions in the plane will do; `axis` is chosen as the
    # coordinate the normal leans on least, which keeps the cross product far from
    # degenerate whatever the facet's orientation.
    axis = np.zeros(3)
    axis[int(np.argmin(np.abs(normal)))] = 1.0
    u = np.cross(normal, axis)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)

    offsets = vertices - centre
    angles = np.arctan2(offsets @ v, offsets @ u)
    # Radius breaks a tie between two vertices at the same bearing, which is what a
    # collinear pair on a facet edge looks like. Without it their order would come
    # from the sort's stability and therefore from the input order.
    order = np.lexsort((np.linalg.norm(offsets, axis=1), angles))
    ring = vertices[order]

    start = int(min(range(len(ring)), key=lambda i: tuple(ring[i])))
    ring = np.roll(ring, -start, axis=0)

    # `arctan2` walks anticlockwise about `normal`, so the ring is already wound
    # outward; reversing it would put every face's normal into the solid.
    return [np.vstack([ring[0], ring[i], ring[i + 1]]) for i in range(1, len(ring) - 1)]


def encode_stl(triangles: np.ndarray) -> bytes:
    """A binary STL with a fixed header and normals recomputed from the winding.

    The one place bytes are produced. Writing and checking go through it, so a
    check cannot pass against an encoding a write would never have produced.
    """
    out = bytearray()
    out += STL_HEADER.ljust(_HEADER_BYTES, b"\0")
    out += struct.pack("<I", len(triangles))
    for face in triangles:
        normal = np.cross(face[1] - face[0], face[2] - face[0])
        norm = float(np.linalg.norm(normal))
        # A degenerate face has no direction. Zero is what the STL specification
        # says to write when the normal is unknown, and every consumer recomputes
        # it from the winding anyway.
        unit = normal / norm if norm > 0.0 else np.zeros(3)
        out += struct.pack("<3f", *unit.astype(np.float32))
        for vertex in face:
            out += struct.pack("<3f", *vertex.astype(np.float32))
        out += struct.pack("<H", 0)
    return bytes(out)


def hull_bytes(source: Path) -> tuple[bytes, int, int]:
    """The hull of one mesh, as the bytes that belong on disk.

    Returns the bytes plus the source and hull triangle counts, so that a caller
    can compare without writing — which is what the ``--check`` mode needs, and
    what makes the check and the write share one implementation rather than two.
    """
    triangles = read_stl(source)
    hull = convex_hull(triangles)
    return encode_stl(hull), int(triangles.shape[0]), int(hull.shape[0])


def build(source_root: Path, dest_root: Path, meshes: list[str]) -> list[HullRecord]:
    """Hull every named mesh, writing the result at the same relative path.

    The mirrored layout is not tidiness. The binding this feeds replaces one mesh
    *root* with another in the vendor description, so a collision reference
    resolves under our root only if its relative path is unchanged.
    """
    records: list[HullRecord] = []
    for relative in sorted(meshes):
        source = source_root / relative
        if not source.is_file():
            raise MeshError(f"declared collision mesh is missing: {source}")
        payload, source_triangles, triangles = hull_bytes(source)
        target = dest_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        records.append(
            HullRecord(
                path=relative,
                source_sha256=sha256_of(source),
                sha256=hashlib.sha256(payload).hexdigest(),
                source_triangles=source_triangles,
                triangles=triangles,
                source_bytes=source.stat().st_size,
                bytes=len(payload),
            )
        )
    return records
