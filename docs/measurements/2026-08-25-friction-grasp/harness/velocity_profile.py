#!/usr/bin/env python3
"""When in the trial does the work-piece move fast, and where is it then?

A high speed during the carry is a grasp that let go. A high speed after the
release command is the part being dropped or struck, which says nothing about
whether the grasp held. The two must not be reported as one number.
"""
import csv, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from measure_grasp import Sample

raw, meta, trial = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
row = [r for r in json.loads(meta.read_text()) if r["trial"] == trial][0]
wp = []
with raw.open() as fh:
    for r in csv.DictReader(fh):
        if r["entity"] == row["model"]:
            wp.append(Sample(float(r["sim_t"]),
                             (float(r["x"]), float(r["y"]), float(r["z"])),
                             (0, 0, 0, 1)))
tg, tr = row["t_grasp_sim"], row["t_release_sim"]
print(f"trial {trial}: grasp={tg:.2f} release={tr:.2f}  "
      f"reported v_max={row['v_max_mps']:.2f}")
events = []
for a, b in zip(wp, wp[1:]):
    dt = b.t - a.t
    if dt <= 1e-9:
        continue
    v = math.dist(a.p, b.p) / dt
    events.append((v, b.t, b.p))
events.sort(reverse=True)
print(f"{'v m/s':>8} {'t':>9} {'phase':>10} {'x':>8} {'y':>8} {'z':>8}")
for v, t, p in events[:8]:
    phase = "pre-grasp" if t < tg else ("CARRY" if t <= tr else "post-release")
    print(f"{v:8.2f} {t:9.2f} {phase:>10} {p[0]:8.3f} {p[1]:8.3f} {p[2]:8.3f}")
carry_v = max((v for v, t, _ in events if tg <= t <= tr), default=0.0)
print(f"  max speed DURING the carry: {carry_v:.3f} m/s")
print(f"  final position: {wp[-1].p}")
