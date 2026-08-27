#!/usr/bin/env python3
"""A rotation-invariant slip check.

`||p_workpiece - p_pad||` is a scalar distance between two points on two bodies.
If the grasp is rigid it is constant, whatever either body's orientation does.
It therefore cannot be confused by a rotating pad frame, which is the one way the
pad-frame slip figure could have been an artefact.
"""
import csv, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from measure_grasp import Sample, compose, interpolate, PAD_LINK, PAD_LINK_R, ARM_MODEL

raw, meta_path, trial = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
row = [r for r in json.loads(meta_path.read_text()) if r["trial"] == trial][0]
tracks = {}
with raw.open() as fh:
    for r in csv.DictReader(fh):
        tracks.setdefault(r["entity"], []).append(
            Sample(float(r["sim_t"]), (float(r["x"]), float(r["y"]), float(r["z"])),
                   (float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"]))))
arm = Sample(0.0, (0.0, -0.35, 0.6), (0.0, 0.0, 0.7071067823197225, 0.7071067800533724))
wp, padl, padr = tracks[row["model"]], tracks[PAD_LINK], tracks[PAD_LINK_R]
tg, tr = row["t_grasp_sim"], row["t_release_sim"]

print(f"{'t-tg':>7} {'|wp-padL|mm':>12} {'|wp-padR|mm':>12} {'|padL-padR|mm':>14}")
base = None
for k, s in enumerate([s for s in wp if tg <= s.t <= tr]):
    l, r = interpolate(padl, s.t), interpolate(padr, s.t)
    if not l or not r:
        continue
    lw, rw = compose(arm, l), compose(arm, r)
    dl, dr = math.dist(s.p, lw.p) * 1000, math.dist(s.p, rw.p) * 1000
    sep = math.dist(lw.p, rw.p) * 1000
    if base is None:
        base = (dl, dr)
    if k % 60:
        continue
    print(f"{s.t-tg:7.2f} {dl:12.3f} {dr:12.3f} {sep:14.3f}"
          f"   (dL {dl-base[0]:+7.3f}, dR {dr-base[1]:+7.3f})")

# --- relative ORIENTATION, the other half of a rigid-body check ---------------
from measure_grasp import quat_mul
def qinv(q):
    x, y, z, w = q
    return (-x, -y, -z, w)

print("\nrelative orientation of the work-piece with respect to the left pad")
print(f"{'t-tg':>7} {'rel_rot_deg':>12}")
ref = None
for k, s in enumerate([s for s in wp if tg <= s.t <= tr]):
    l = interpolate(padl, s.t)
    if not l:
        continue
    lw = compose(arm, l)
    rel = quat_mul(qinv(lw.q), s.q)
    if ref is None:
        ref = rel
        continue
    d = quat_mul(qinv(ref), rel)
    w = max(-1.0, min(1.0, abs(d[3])))
    if k % 60 == 0:
        print(f"{s.t-tg:7.2f} {math.degrees(2*math.acos(w)):12.3f}")
