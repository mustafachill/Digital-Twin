"""POST-HOC — does closing the jaws square the part up?

**Registered nowhere in `criteria.md` and labelled post-hoc wherever it is
reported.** It is an analysis of a mechanism, run over data already collected for
Arm C, and it is reported because it changes what the Arm C rate *means* — not
because it was predicted.

THE MECHANISM. A square gripped at two opposite corners by flat parallel jaws is
in unstable equilibrium: the contact normals do not pass through the centre, so
squeezing produces a couple that rotates the part toward the orientation where a
face lies flat against each pad. If that happens here, then the gripper is itself
an aligning fixture, and a part picked at a yaw is *delivered* square whatever it
started at — which would matter a great deal to any handoff argument.

TWO INDEPENDENT READINGS, because either alone can be explained away:

  * **The part's own yaw**, from Gazebo's pose feed, before the grasp and during
    the carry. This is the direct observation.
  * **The width the jaws stalled at**, from `q_at_stall_rad` through the L0 axial
    map (`geometry.opening_m`). This is a second, independent witness: a part that
    stayed at yaw θ stops the jaws at `50·(cos θ + sin θ)` mm, and a part that
    squared up stops them at 50 mm. The two readings come from different
    subsystems — the physics pose feed and the joint state — so agreeing is
    evidence and disagreeing is a finding.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OFFSET = HERE.parent.parent / "2026-08-25-grasp-plane-offset" / "harness"
sys.path.insert(0, str(OFFSET))
sys.path.insert(0, str(HERE))

import geometry as G  # noqa: E402  (the L0 axial map, unchanged)
import yaw as yawlib  # noqa: E402

RAW = HERE.parent / "raw"


def load_track(path: Path, entity: str):
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            if r["entity"] != entity:
                continue
            out.append((
                float(r["sim_t"]),
                (float(r["x"]), float(r["y"]), float(r["z"])),
                (float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"])),
            ))
    return out


def at_time(track, t: float):
    """Nearest sample at or before `t`, as `measure_grasp.interpolate` does it."""
    best = None
    for s in track:
        if s[0] <= t:
            best = s
        else:
            break
    return best or (track[0] if track else None)


def analyse(*labels: str) -> None:
    labels = labels or ("graspyaw", "graspyaw2")
    rows = []
    for label in labels:
        trials_path = RAW / f"{label}_trials.json"
        if not trials_path.exists():
            continue
        for r in json.loads(trials_path.read_text()):
            if "trial" in r:
                r["block"] = label
                rows.append(r)
    if not rows:
        print("no Arm C trials")
        return

    print("\n" + "=" * 78)
    print("POST-HOC — does closing the jaws square the part up?")
    print("=" * 78)
    print("Not pre-registered. Reported because it changes what the Arm C rate means.\n")
    print(f"{'blk/tr':>5} {'yaw in':>7} {'before':>8} {'carry':>8} {'after':>8} "
          f"{'stall mm':>9} {'pred mm':>8} {'squared?':>9}")

    by_level: dict[float, list] = {}
    for r in rows:
        level = r.get("commanded_yaw_deg")
        if level is None or not r.get("pick_succeeded"):
            continue
        samples = RAW / f"{r['block']}_trial{r['trial']:03d}_samples.csv"
        if not samples.exists():
            continue
        entity = r.get("model") or ""
        track = load_track(samples, entity)
        if not track:
            continue
        t_grasp = r.get("t_grasp_sim")
        t_release = r.get("t_release_sim")
        if t_grasp is None:
            continue

        # THE FIRST SAMPLE OF THE TRACE, not a fixed offset back from the grasp
        # instant. `t_grasp` is stamped at PHASE_RETREATING — the moment the lift
        # begins, which is already AFTER the jaws have closed — so any small
        # offset back from it can still land after closure and read the squared
        # part as though it had been square all along. Recording starts before the
        # arm moves, so the first sample is the part at rest on the table at the
        # yaw it was spawned at, which is the reading this column wants.
        before = track[0]
        carry = at_time(track, (t_grasp + t_release) / 2.0) if t_release else None
        after = track[-1]

        yaw_before = yawlib.folded_yaw_deg(before[2]) if before else float("nan")
        yaw_carry = yawlib.folded_yaw_deg(carry[2]) if carry else float("nan")
        yaw_after = yawlib.folded_yaw_deg(after[2])

        q = r.get("q_at_stall_rad")
        stall_mm = G.opening_m(q) * 1000.0 if q else float("nan")
        pred_mm = yawlib.presented_mm(level)
        # "Squared up" means the jaws stopped near the square width rather than
        # near the width the spawn yaw predicts. Only meaningful where the two
        # predictions differ by more than the controller's own width bias.
        squared = ""
        if level > 0 and not math.isnan(stall_mm):
            squared = "yes" if abs(stall_mm - 50.0) < abs(stall_mm - pred_mm) else "no"

        print(f"{r['block'][-1] if r['block'][-1].isdigit() else '1'}/{r['trial']:<3d} {level:7.1f} {yaw_before:8.2f} {yaw_carry:8.2f} "
              f"{yaw_after:8.2f} {stall_mm:9.2f} {pred_mm:8.2f} {squared:>9}")
        by_level.setdefault(level, []).append((yaw_before, yaw_carry, yaw_after, stall_mm))

    print(f"\n{'level':>7} {'n':>3} {'median yaw in carry':>21} {'median stall mm':>17} "
          f"{'predicted mm':>13}")
    for level in sorted(by_level):
        vals = by_level[level]
        carries = sorted(v[1] for v in vals if not math.isnan(v[1]))
        stalls = sorted(v[3] for v in vals if not math.isnan(v[3]))
        mc = carries[len(carries) // 2] if carries else float("nan")
        ms = stalls[len(stalls) // 2] if stalls else float("nan")
        print(f"{level:7.1f} {len(vals):3d} {mc:21.2f} {ms:17.2f} "
              f"{yawlib.presented_mm(level):13.2f}")


if __name__ == "__main__":
    analyse(*(sys.argv[1:] or []))
