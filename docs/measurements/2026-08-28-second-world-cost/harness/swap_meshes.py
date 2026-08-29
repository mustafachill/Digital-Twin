#!/usr/bin/env python3
"""Put hull collision meshes in the installed overlay, and put the vendor ones back.

Q3.1 needs the same cell run twice with one thing different. The vendor meshes are
reached through the built overlay, where colcon's --symlink-install leaves one
SYMLINK per mesh pointing into the vcs-imported source tree. This script replaces
those symlinks with real hull files and restores the symlinks afterwards, so the
vendor source tree is never written to at all -- only the install volume, which is
a build artefact and is rebuilt by ./scripts/build.

Every path it touches is recorded with a checksum before and after, and `verify`
refuses to pass unless the tree is byte-identical to how it was found. A rig that
mutates a build tree and cannot prove it put it back is a rig that will one day
explain a wrong measurement.

Only collision-relevant meshes are swapped. The runs are headless, so nothing
renders and the substitution changes what the solver collides against and nothing
else that executes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def targets(install_meshes, subdirs):
    found = []
    for sub in subdirs:
        for stl in sorted(install_meshes.joinpath(sub).glob("*.stl")):
            found.append(stl)
    return found


def do_hull(install_meshes, hull_root, subdirs, state_path):
    state = []
    for stl in targets(install_meshes, subdirs):
        rel = stl.relative_to(install_meshes)
        hull = hull_root.joinpath(rel)
        if not hull.exists():
            raise SystemExit("no hull for " + str(rel))
        entry = dict(path=str(stl), rel=str(rel), was_symlink=stl.is_symlink())
        if stl.is_symlink():
            entry["link_target"] = os.readlink(stl)
        else:
            entry["sha256"] = digest(stl)
            backup = Path(str(stl) + ".vendor-backup")
            shutil.copy2(stl, backup)
            entry["backup"] = str(backup)
        stl.unlink()
        shutil.copy2(hull, stl)
        entry["hull_sha256"] = digest(stl)
        state.append(entry)
    Path(state_path).write_text(json.dumps(state, indent=2))
    print(json.dumps(dict(condition="hull", swapped=len(state))))


def do_vendor(state_path):
    state = json.loads(Path(state_path).read_text())
    restored = 0
    for entry in state:
        stl = Path(entry["path"])
        if stl.exists() or stl.is_symlink():
            stl.unlink()
        if entry["was_symlink"]:
            os.symlink(entry["link_target"], stl)
        else:
            shutil.move(entry["backup"], stl)
        restored += 1
    print(json.dumps(dict(condition="vendor", restored=restored)))


def do_verify(install_meshes, subdirs, reference_path, write):
    """Record, or check, the fingerprint of every mesh this rig can touch."""
    current = dict()
    for stl in targets(install_meshes, subdirs):
        rel = str(stl.relative_to(install_meshes))
        if stl.is_symlink():
            current[rel] = "symlink:" + os.readlink(stl)
        else:
            current[rel] = "file:" + digest(stl)
    reference = Path(reference_path)
    if write:
        reference.write_text(json.dumps(current, indent=2))
        print(json.dumps(dict(recorded=len(current))))
        return 0
    expected = json.loads(reference.read_text())
    differing = [k for k in expected if current.get(k) != expected[k]]
    missing = [k for k in expected if k not in current]
    extra = [k for k in current if k not in expected]
    ok = not differing and not missing and not extra
    print(json.dumps(dict(
        identical=ok, differing=differing, missing=missing, extra=extra
    )))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("hull", "vendor", "record", "verify"))
    ap.add_argument("--install-meshes", required=True)
    ap.add_argument("--hull-root", default=None)
    ap.add_argument("--state", required=True)
    ap.add_argument("--reference", default=None)
    ap.add_argument("--subdir", action="append", required=True)
    args = ap.parse_args()

    install = Path(args.install_meshes)
    if args.action == "hull":
        do_hull(install, Path(args.hull_root), args.subdir, args.state)
        return 0
    if args.action == "vendor":
        do_vendor(args.state)
        return 0
    return do_verify(install, args.subdir, args.reference, args.action == "record")


if __name__ == "__main__":
    sys.exit(main())
