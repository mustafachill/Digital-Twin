#!/usr/bin/env python3
"""Compute a convex hull for each vendor mesh that is used as collision geometry.

This is the H arm of Q3.1. It exists to answer whether replacing the twelve
rendering meshes per arm with hulls changes the physics step materially --
ADR-0028's own condition for the record being worth promoting.

It is deliberately NOT the pipeline ADR-0028 specifies. That pipeline belongs in
tools/, is bound through L0, is deterministic and is unit-tested. This is a
measurement rig: it writes hulls into a scratch directory so that swap_meshes.sh
can put them where the vendor meshes were, run one condition, and put the vendor
meshes back. Nothing here is a proposal for how hulls should ship.

Reads and writes binary STL directly rather than depending on a mesh library, so
that reproducing the campaign needs only numpy and scipy, both already present in
the project image.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

HEADER_BYTES = 80
TRIANGLE_BYTES = 50


def read_stl(path):
    """Return an (n, 3, 3) array of triangle vertices. Handles binary and ASCII."""
    data = path.read_bytes()
    if len(data) >= HEADER_BYTES + 4:
        count = struct.unpack("<I", data[HEADER_BYTES:HEADER_BYTES + 4])[0]
        if len(data) == HEADER_BYTES + 4 + count * TRIANGLE_BYTES:
            body = np.frombuffer(
                data, dtype=np.uint8, offset=HEADER_BYTES + 4
            ).reshape(count, TRIANGLE_BYTES)
            floats = body[:, :48].copy().view("<f4").reshape(count, 4, 3)
            return floats[:, 1:, :].astype(np.float64)
    text = data.decode("utf-8", "replace")
    verts = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "vertex":
            verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    arr = np.asarray(verts, dtype=np.float64)
    return arr.reshape(-1, 3, 3)


def write_stl(path, triangles, normals):
    out = bytearray()
    out += b"cite convex hull, campaign 2026-08-28-second-world-cost".ljust(
        HEADER_BYTES, b" "
    )
    out += struct.pack("<I", len(triangles))
    for tri, nrm in zip(triangles, normals):
        out += struct.pack("<3f", *nrm.astype(np.float32))
        for v in tri:
            out += struct.pack("<3f", *v.astype(np.float32))
        out += struct.pack("<H", 0)
    path.write_bytes(bytes(out))


def hull_of(triangles):
    """Convex hull of the mesh's vertices, oriented outward."""
    points = triangles.reshape(-1, 3)
    hull = ConvexHull(points)
    tris = []
    normals = []
    for simplex, equation in zip(hull.simplices, hull.equations):
        a, b, c = points[simplex[0]], points[simplex[1]], points[simplex[2]]
        outward = equation[:3]
        face = np.cross(b - a, c - a)
        if float(np.dot(face, outward)) < 0.0:
            b, c = c, b
        tris.append(np.vstack([a, b, c]))
        normals.append(outward)
    return np.asarray(tris), np.asarray(normals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    help="vendor xarm_description meshes directory")
    ap.add_argument("--dest", required=True, help="where the hulls are written")
    ap.add_argument("--subdir", action="append", required=True,
                    help="mesh subdirectory to hull, relative to --source")
    args = ap.parse_args()

    source = Path(args.source)
    dest = Path(args.dest)
    manifest = []
    for sub in args.subdir:
        for stl in sorted(source.joinpath(sub).glob("*.stl")):
            triangles = read_stl(stl)
            hull_tris, hull_normals = hull_of(triangles)
            target = dest.joinpath(sub, stl.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            write_stl(target, hull_tris, hull_normals)
            manifest.append(dict(
                mesh=str(Path(sub).joinpath(stl.name)),
                vendor_triangles=int(triangles.shape[0]),
                hull_triangles=int(hull_tris.shape[0]),
                vendor_bytes=stl.stat().st_size,
                hull_bytes=target.stat().st_size,
            ))
    total_v = sum(m["vendor_triangles"] for m in manifest)
    total_h = sum(m["hull_triangles"] for m in manifest)
    summary = dict(
        meshes=manifest,
        total_vendor_triangles=total_v,
        total_hull_triangles=total_h,
        reduction=float(total_v) / float(total_h) if total_h else None,
    )
    dest.joinpath("hull_manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(dict(
        files=len(manifest),
        total_vendor_triangles=total_v,
        total_hull_triangles=total_h,
    )))
    return 0


if __name__ == "__main__":
    sys.exit(main())
