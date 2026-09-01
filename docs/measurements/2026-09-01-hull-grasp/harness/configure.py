#!/usr/bin/env python3
"""Apply the one scratch flip this campaign has, on the HOST, and regenerate.

`description.collision.select` on the xArm 5 type is the whole of the A/B
(ADR-0028's implementation note: "flipping the field is now genuinely the whole
change"). It is a SCRATCH flip -- `run_campaign.sh` reverts with `git checkout`
before and after every block, and no flipped `model/` or generated artifact is
committed. The shipped selection stays `vendor_meshes` (criteria.md 2).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ARM = ROOT / "model" / "assets" / "types" / "robots" / "xarm5.yaml"


def swap(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text and old not in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one {old!r}, found {text.count(old)}")
    path.write_text(text.replace(old, new))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geometry", choices=("vendor_meshes", "convex_hull"), required=True)
    args = ap.parse_args()

    # `vendor_meshes` is the committed state, so it is a no-op rather than a swap
    # back: the driver reverts with `git checkout` before every block.
    if args.geometry == "convex_hull":
        swap(ARM, "select: vendor_meshes", "select: convex_hull")

    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "cite_tools.cli",
         "validate", "--model", str(ROOT / "model"), "--write"],
        cwd=ROOT, capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout[-3000:])
    sys.stderr.write(proc.stderr[-3000:])
    # A non-zero exit is EXPECTED once the model is flipped: the generated-artifact
    # diff compares against the committed (unflipped) tree and must disagree. Every
    # other validation level still runs and its failures are still printed above.
    # What the run is checked on instead is the description the RUNNING cell
    # publishes -- see `verify_geometry` in measure_hull_grasp.py (criteria.md V2).
    return 0


if __name__ == "__main__":
    sys.exit(main())
