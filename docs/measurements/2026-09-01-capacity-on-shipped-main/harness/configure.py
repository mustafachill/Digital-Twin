#!/usr/bin/env python3
"""Apply one scratch configuration flip, on the HOST, and regenerate from it.

ADAPTED from `2026-08-31-capacity-and-clock-deficit/harness/configure.py`. ONE change,
and it is the reason this campaign exists: **the geometry flip runs the other way.**
There, `vendor_meshes` was the committed state and `convex_hull` was the scratch flip.
Here `convex_hull` IS the committed state -- ADR-0028 was promoted and the shipped
`description.collision.select` moved with it -- so the shipped condition needs no flip at
all and **`vendor_meshes` is the scratch flip**, applied only to produce the control.
See `README.md` for the full adaptation list; everything else in this file is byte-identical.

Three flips, and every one of them is scratch (criteria.md 5): a flipped `model/` and a
flipped generator constant are never committed. `run_condition.sh` reverts with
`git checkout` before and after every trial.

The throttle is `REAL_TIME_FACTOR` in the generator rather than a hand edit of the
generated world: ADR-0021 forbids hand-editing a generated artifact, and the value has to
stay in one place (P1) so that both sides of a pair get it by construction.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ZONES = ROOT / "model" / "facility" / "zones.yaml"
ARM = ROOT / "model" / "assets" / "types" / "robots" / "xarm5.yaml"
WORLD_GEN = ROOT / "tools" / "cite_tools" / "generate" / "world.py"


def swap(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text and old not in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one {old!r}, found {text.count(old)}")
    path.write_text(text.replace(old, new))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topology", choices=("pair", "solo"), required=True)
    ap.add_argument("--geometry", choices=("vendor_meshes", "convex_hull"), required=True)
    ap.add_argument("--throttle", choices=("on", "off"), required=True)
    args = ap.parse_args()

    # `solo`, `convex_hull` and the throttle in force are the COMMITTED state on this
    # campaign's base commit, so each is a no-op rather than a swap back: the driver
    # reverts with `git checkout` before every trial (criteria.md 5).
    if args.topology == "pair":
        swap(ZONES, "sides: single", "sides: pair")
    if args.geometry == "vendor_meshes":
        # The reversed flip. `validate` below exits NON-ZERO on this one by design:
        # `_vendor_collision_is_declared` was promoted from WARNING to ERROR by the change
        # that moved the default, so declaring `vendor_meshes` is now a model error.
        # `--write` regenerates BEFORE findings are computed, so the artifacts are produced
        # regardless, and V5 reads what was INSTALLED rather than what the tool said.
        # criteria.md 5 registers this in advance; it is not a surprise to report later.
        swap(ARM, "select: convex_hull", "select: vendor_meshes")
    if args.throttle == "off":
        swap(WORLD_GEN, "REAL_TIME_FACTOR = 1.0", "REAL_TIME_FACTOR = 0.0")

    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "cite_tools.cli",
         "validate", "--model", str(ROOT / "model"), "--write"],
        cwd=ROOT, capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout[-2000:])
    sys.stderr.write(proc.stderr[-2000:])
    # A non-zero exit here is expected in exactly one case and must not be swallowed
    # blindly: the generated-artifact diff fails BY DESIGN once the model is flipped,
    # because the committed tree is the unflipped one. Every other level still runs.
    world = (ROOT / "workspace" / "src" / "cite_generated" / "worlds" / "cell_a.sdf").read_text()
    arm = (ROOT / "workspace" / "src" / "cite_generated" / "description"
           / "cell_a_arm_1.urdf.xacro").read_text()
    import re
    rtf = re.search(r"<real_time_factor>([^<]+)</real_time_factor>", world)
    root = re.search(r'collision_mesh_path="([^"]*)"', arm)
    print(f"CONFIGURED real_time_factor={rtf.group(1) if rtf else '?'} "
          f"geometry={'convex_hull' if root and 'convex_hull' in root.group(1) else 'vendor_meshes'} "
          f"topology={args.topology}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
