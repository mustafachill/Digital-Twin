"""Arm C — how much yaw can a gripper commanded to a nominal orientation absorb?

A shim over the published harness, in the pattern
`../../2026-08-25-grasp-plane-offset/harness/interleaved_block.py` established:
set one thing per trial that the harness reads at call time, key it off the trial
index embedded in the entity name, and post-stamp the condition into the trials
JSON. `measure_grasp.py` is not edited and no production code is touched.

WHAT IS VARIED: the yaw the work-piece is spawned at. Nothing else. The arm, the
station, the commanded width, the approach and retreat, the timestep and the
work-piece are the published campaigns' own, so the 0 degree cell of this sweep
is directly comparable with their 68/68 and this campaign inherits their meaning
for every metric.

WHY THE GRIPPER IS NOT TOLD ABOUT THE YAW. That is the situation under test.
`PickAt`'s `pose` port is empty in this cell and the frame fallback carries the
station frame's yaw, so the jaws arrive square at a part that is not
(`skill_nodes.hpp`: "THIS PORT IS EMPTY IN THIS CELL, AND THE FALLBACK IS THE
NORMAL PATH"). Commanding the true yaw would measure a cell that does not exist.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE.parent.parent / "2026-08-25-friction-grasp" / "harness"
sys.path.insert(0, str(PUBLISHED))
sys.path.insert(0, str(HERE))

import measure_grasp as mg  # noqa: E402

#: What `PickAt` sends today, and NOT what the published harness defaults to.
#:
#: DECLARED DEVIATION FROM THE PUBLISHED HARNESS, and the reason it is the
#: faithful choice rather than a change. `measure_grasp.GRASP_HEIGHT_M` is 0.030,
#: which was right against the skill server of its day: that server planned the
#: tip link straight to `object_pose`, so the harness had to pre-compensate. The
#: server at the commit under measurement offsets onto the pad plane itself using
#: the end effector's declared linkage (`skill_server.cpp`, `pad_offset_m`), and
#: `PickAt`'s port is now `workpiece_height_m`, defaulting to 0.025 — "where the
#: object is", which for a 50 mm cube resting on the frame is its centre.
#:
#: Sending 0.030 here would stack the harness's old pre-compensation on top of
#: the server's new one and park the pads 5 mm high, reintroducing precisely the
#: lever arm the offset campaign measured out. 0.025 is what the shipped line
#: sends, so 0.025 is what this campaign sends.
GRASP_HEIGHT_M = 0.025


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--yaws", default="0,5,10,15,20,30",
                    help="comma-separated spawn yaws in degrees, cycled per trial")
    ap.add_argument("--grasp-height", type=float, default=GRASP_HEIGHT_M)
    known, rest = ap.parse_known_args()

    yaws = [float(v) for v in known.yaws.split(",") if v]
    mg.GRASP_HEIGHT_M = known.grasp_height
    print(f"[yaw] commanded grasp height {known.grasp_height:.4f} m "
          f"(object centre above the frame, as PickAt sends today)", flush=True)
    print(f"[yaw] interleaving spawn yaws {yaws} degrees", flush=True)

    order: dict[int, float] = {}
    original_spawn = mg.spawn

    def spawn(world: str, name: str, xyz, mu: float):
        """`measure_grasp.spawn` with a yaw, chosen by the trial's own index.

        Keyed off the index parsed out of the model name rather than off a call
        counter, exactly as the offset campaign's shim does it and for the same
        reason: a retried or skipped trial must not shift every later trial's
        condition.
        """
        index = int(name.rsplit("_", 1)[-1])
        yaw_deg = yaws[(index - 1) % len(yaws)]
        order[index] = yaw_deg
        print(f"  [yaw] trial {index}: spawn yaw {yaw_deg:.2f} deg", flush=True)
        path = Path(f"/tmp/{name}.sdf")
        path.write_text(mg._workpiece_sdf(name, mu))
        return subprocess.run(
            [
                "ros2", "run", "ros_gz_sim", "create", "-file", str(path),
                "-name", name,
                "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2]),
                "-Y", f"{math.radians(yaw_deg):.9f}",
            ],
            capture_output=True, text=True, timeout=180,
        )

    mg.spawn = spawn

    sys.argv = [sys.argv[0], *rest]
    rc = mg.main()

    # Post-stamp the condition, so the raw data carries its own independent
    # variable rather than requiring this file to reconstruct it later.
    ap2 = argparse.ArgumentParser(add_help=False)
    ap2.add_argument("--label", default="run")
    ap2.add_argument("--out", default=str(HERE.parent / "raw"))
    stamped, _ = ap2.parse_known_args(rest)
    trials = Path(stamped.out) / f"{stamped.label}_trials.json"
    if trials.exists():
        rows = json.loads(trials.read_text())
        for row in rows:
            if "trial" in row:
                row["commanded_yaw_deg"] = order.get(row["trial"])
                row["commanded_grasp_height_m"] = known.grasp_height
        trials.write_text(json.dumps(rows, indent=2, default=str))
        print(f"[yaw] stamped {len(rows)} rows in {trials}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
