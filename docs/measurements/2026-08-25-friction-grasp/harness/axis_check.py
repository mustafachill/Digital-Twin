#!/usr/bin/env python3
"""What axis does the work-piece turn about, relative to the jaws?

A part that spins about the pad-to-pad axis is turning between two flat faces
that stay in contact -- a torsional friction failure. A part turning about any
other axis would have to lever a corner out of the jaws. Distinguishing the two
is the difference between "the grasp is loose" and "the grasp let go".
"""
import csv, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from measure_grasp import Sample, compose, interpolate, quat_mul, PAD_LINK, PAD_LINK_R

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
qinv = lambda q: (-q[0], -q[1], -q[2], q[3])

carry = [s for s in wp if tg <= s.t <= tr]
first, last = carry[0], carry[-8]
print("work-piece WORLD orientation, first and last of the carry:")
print(f"  t={first.t-tg:5.2f}  q={tuple(round(v,4) for v in first.q)}")
print(f"  t={last.t-tg:5.2f}  q={tuple(round(v,4) for v in last.q)}")
d = quat_mul(qinv(first.q), last.q)
ang = 2 * math.acos(max(-1.0, min(1.0, abs(d[3]))))
n = math.sqrt(sum(v*v for v in d[:3])) or 1.0
axis_w = tuple(v / n for v in d[:3])
print(f"  the part turned {math.degrees(ang):.2f} deg in the WORLD about {tuple(round(v,3) for v in axis_w)}")

for label, s in (("grasp", first), ("release", last)):
    l, r = interpolate(padl, s.t), interpolate(padr, s.t)
    lw, rw = compose(arm, l), compose(arm, r)
    v = [rw.p[i] - lw.p[i] for i in range(3)]
    m = math.sqrt(sum(c*c for c in v))
    print(f"  pad-to-pad axis at {label}: {tuple(round(c/m,3) for c in v)}")
    if label == "release":
        dot = abs(sum(axis_w[i] * v[i] / m for i in range(3)))
        print(f"  |cos(angle between the turn axis and the pad-to-pad axis)| = {dot:.4f}")

# What the pad itself did over the same window, for comparison.
lf, ll = compose(arm, interpolate(padl, first.t)), compose(arm, interpolate(padl, last.t))
dp = quat_mul(qinv(lf.q), ll.q)
print(f"  the PAD turned {math.degrees(2*math.acos(max(-1.0,min(1.0,abs(dp[3]))))):.2f} deg over the same window")
