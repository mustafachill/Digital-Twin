# Raw

What the harness recorded. Every figure in [`../ANALYSIS.md`](../ANALYSIS.md) is derived
from this directory, by `../harness/analyse.py` and `../harness/mechanism.py`.

| Path | What it is |
|---|---|
| `<LABEL>_trials.json` | one record per trial: every metric, every verdict input, and the timestamps they were computed over. **Every number in the A/B table comes from these four files.** |
| `<LABEL>_geometry.json` | V2's evidence — the collision-mesh reference count read off the description the **running** cell published |
| `<LABEL>_entities.txt` | what the Gazebo pose feed carried in that block |
| `<LABEL>_trial<NNN>_patch.csv.gz` | every finger contact point in the hold window: sim time, pad, position on the `ez`/`ey` axes, the contact normal on all three, and depth. **M3, M4 and the whole of `ANALYSIS.md` §4 derive from these.** |
| `pose_samples.tar.gz` | the full pose feed for every trial — work-piece, both pads, the gripper body and the arm model, at physics-publication rate |
| `drive_joint.tar.gz` | the drive joint's position through every trial |
| `contacts_kept/` | the unaggregated contact stream over the closure window, for the **first trial of each block** only |
| `analysis.json`, `mechanism.json` | machine-readable output of the two analysis scripts |
| `logs/` | each block's sim log, harness log, and the host load average and free disk read at its start |
| `shakedown/` | two vendor-geometry trials taken **before** `criteria.md` was frozen. Not campaign data — see its own README |

## What was pruned, and why it costs nothing

**The per-trial contact stream is 11 MB uncompressed and 47 trials of it is 528 MB**, which
is thirty times the largest `raw/` already published in this directory. Two reductions were
applied:

1. **At write time**, by the harness: the contact file keeps only contacts involving a
   finger, inside the closure window widened by one second at each end. Before that filter
   it was 131 MB per trial, and almost all of it was the work-piece resting on the pick
   surface.
2. **At publication**, here: the closure-window contact file is kept for the **first trial
   of each block** and dropped for the rest. **Nothing a figure depends on was removed** —
   M3, M4 and the mechanism diagnostic are computed from the `_patch.csv.gz` files, which
   are kept in full for **every** trial and which contain every contact point those figures
   use.

Pose samples and drive-joint traces are archived rather than deleted.

## Reading a patch file

Coordinates are in the gripper frame defined in `criteria.md` §3, taken at the instant of
first contact and expressed relative to `arm_1_link5`:

| column | meaning |
|---|---|
| `z_mm` | position along the **approach** axis. The pad spans ~134 to ~172 mm; ADR-0028's relief steps are at 132, 134 and 173 mm in this same frame |
| `y_mm` | position along the **jaw / closing** axis. The two pad faces sit at about ±25 mm |
| `n_pivot`, `n_close`, `n_approach` | the contact normal on the three axes. A flat pad reads `n_close` ≈ 1 and `n_approach` ≈ 0 |
| `depth_m` | the sensor's penetration depth. **It reads ~0 in every trial on both geometries** and no figure uses it |
