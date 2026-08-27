#!/usr/bin/env python3
"""Print the slip and height traces of one trial, so that a slip number can be
read as a shape rather than believed as a scalar."""
import csv, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from measure_grasp import Sample, compose, quat_conj_rotate, interpolate, PAD_LINK, ARM_MODEL

raw = Path(sys.argv[1])
meta = json.loads(Path(sys.argv[2]).read_text())
trial = int(sys.argv[3])
row = [r for r in meta if r["trial"] == trial][0]

tracks = {}
with raw.open() as fh:
    for r in csv.DictReader(fh):
        tracks.setdefault(r["entity"], []).append(
            Sample(float(r["sim_t"]),
                   (float(r["x"]), float(r["y"]), float(r["z"])),
                   (float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"]))))

wp_name = row["model"]
wp, pad = tracks[wp_name], tracks[PAD_LINK]
arm = Sample(0.0, tuple(row.get("arm_p", (0.0, -0.35, 0.6))),
             (0.0, 0.0, 0.7071067823197225, 0.7071067800533724))
tg, tr = row["t_grasp_sim"], row["t_release_sim"]
z_rest = row["z_rest"]

carry = [s for s in wp if tg <= s.t <= tr]
ref = None
print(f"trial {trial}: grasp={tg:.2f} release={tr:.2f} z_rest={z_rest:.4f}")
print(f"{'t-tg':>7} {'wp_z':>8} {'pad_z':>8} {'gap':>8} "
      f"{'slip':>7} {'sx':>7} {'sy':>7} {'sz':>7} {'air':>5}")
for k, s in enumerate(carry):
    p = interpolate(pad, s.t)
    if p is None:
        continue
    pw = compose(arm, p)
    rel = quat_conj_rotate(pw.q, (s.p[0]-pw.p[0], s.p[1]-pw.p[1], s.p[2]-pw.p[2]))
    if ref is None:
        ref = rel
        continue
    if k % 40:
        continue
    slip = math.dist(rel, ref) * 1000.0
    d = [(rel[j] - ref[j]) * 1000.0 for j in range(3)]
    air = s.p[2] > z_rest + 0.05
    print(f"{s.t-tg:7.2f} {s.p[2]:8.4f} {pw.p[2]:8.4f} {s.p[2]-pw.p[2]:8.4f} "
          f"{slip:7.2f} {d[0]:7.2f} {d[1]:7.2f} {d[2]:7.2f} {str(air):>5}")
