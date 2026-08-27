#!/usr/bin/env python3
"""Run the published friction-grasp harness at a chosen commanded grasp height.

The published harness is reused **verbatim** — imported, not copied and not
edited. It already measures twist three independent ways, so that a rotating
reference frame cannot fake it, and rebuilding that would produce numbers which
could not be compared with the published set.

The only thing this file does is set `measure_grasp.GRASP_HEIGHT_M`, which the
harness reads at goal-construction time as `object_pose.pose.position.z`. That
is a *geometry* change: it moves where `link_tcp` is commanded to sit, and hence
where the pad face lands on the part. No production code is touched — `PickAt`,
the skill server, the controllers and the L0 model are the shipped ones in every
block — so the two conditions differ in one number and in nothing else.

    grasp_height_block.py --grasp-height 0.0058 --label corrected --trials 12 ...

Every other argument is passed to the harness unchanged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE.parent.parent / "2026-08-25-friction-grasp" / "harness"
sys.path.insert(0, str(PUBLISHED))

import measure_grasp as mg  # noqa: E402


def main(argv: list[str]) -> int:
    height = None
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--grasp-height":
            height = float(argv[i + 1])
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    if height is None:
        print("--grasp-height is required", file=sys.stderr)
        return 2

    previous = mg.GRASP_HEIGHT_M
    mg.GRASP_HEIGHT_M = height
    print(f"commanded grasp height: {previous:.4f} m (published) -> {height:.4f} m",
          flush=True)

    sys.argv = [sys.argv[0]] + rest
    code = mg.main()

    # Stamp the height into the block's own record. Provenance has to live with
    # the data: a trials file that does not say which height produced it is a
    # block that cannot be re-read six months from now.
    args = dict(zip(rest[::2], rest[1::2]))
    out = Path(args.get("--out", ""))
    label = args.get("--label", "run")
    summary = out / f"{label}_trials.json"
    if summary.exists():
        rows = json.loads(summary.read_text())
        for row in rows:
            row["commanded_grasp_height_m"] = height
        summary.write_text(json.dumps(rows, indent=2, default=str))
        print(f"stamped commanded_grasp_height_m={height} into {summary}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
