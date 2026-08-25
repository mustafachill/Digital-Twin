#!/usr/bin/env python3
"""Run both grasp heights against ONE cell, alternating trial by trial.

WHY THIS EXISTS, and why the separate-block form is not enough.

The published campaign ran five blocks at `max_step_size = 0.001` whose grasp
configuration was nominally identical or nearly so, and their median twists were
9.60°, 27.82°, 29.76°, 23.90° and 5.16°. That is a factor of six between blocks
that differ in nothing the measurement was varying. The per-trial distribution is
bimodal — a trial either twists 20-30° or barely twists at all — so a block's
median is really a statement about what fraction of its trials fell into the high
mode, and that fraction moves between bring-ups.

Comparing one block against another therefore risks reporting a bring-up as an
effect. The fix is not more trials per block; it is to put both conditions inside
the same bring-up, so that whatever varies between cells is shared by both arms
of the comparison rather than confounded with it. Trials alternate
A, B, A, B, ... against one cell, one physics configuration, one set of
controllers.

The published harness is still used verbatim; the only addition is that the
commanded height is set immediately before each `Pick` rather than once per
block. `Driver.do_pick` reads `measure_grasp.GRASP_HEIGHT_M` at call time, which
is what makes this possible without touching that file.

    interleaved_block.py --heights 0.030,0.0058 --label paired --trials 24 ...
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
    heights: list[float] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--heights":
            heights = [float(v) for v in argv[i + 1].split(",")]
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    if len(heights) < 2:
        print("--heights needs at least two comma-separated values", file=sys.stderr)
        return 2

    order: dict[int, float] = {}
    original = mg.Driver.do_pick

    def do_pick(self, workpiece):
        # Keyed off the TRIAL INDEX carried in the work-piece's name, not off a
        # call counter. A trial that fails before it reaches `Pick` -- a spawn
        # that did not take, a `MoveTo` that timed out -- would otherwise shift
        # every later trial into the other condition, and the block would look
        # perfectly ordinary while being scrambled.
        index = int(workpiece.rsplit("_", 1)[-1])
        height = heights[(index - 1) % len(heights)]
        order[index] = height
        mg.GRASP_HEIGHT_M = height
        print(f"  [interleave] trial {index}: commanded grasp height "
              f"{height:.4f} m", flush=True)
        return original(self, workpiece)

    mg.Driver.do_pick = do_pick
    print(f"interleaving commanded grasp heights {heights} against one cell",
          flush=True)

    sys.argv = [sys.argv[0]] + rest
    code = mg.main()

    args = dict(zip(rest[::2], rest[1::2]))
    summary = Path(args.get("--out", "")) / f"{args.get('--label', 'run')}_trials.json"
    if summary.exists():
        rows = json.loads(summary.read_text())
        for row in rows:
            n = row.get("trial")
            if isinstance(n, int) and n in order:
                row["commanded_grasp_height_m"] = order[n]
        summary.write_text(json.dumps(rows, indent=2, default=str))
        print(f"stamped per-trial commanded_grasp_height_m into {summary}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
