# Analysis — does the grasp-plane offset cause the twist?

**Provenance, stated first because it matters.** The measuring agent was terminated by a
session limit before it could analyse its own data. The blocks below were collected by it,
under the criteria frozen in `criteria.md` before the first trial. **The analysis in this
file was computed by the orchestrator from the committed raw data, not by the agent.**
The scripts that produced the numbers are the ones in `harness/`; the conditions for
`paired2` were read from that block's own `[interleave]` log lines rather than inferred.

## Answer: the offset causes the *high mode*, and not the rest of the twist

Interleaved design, shipped timestep 0.001, `paired` + `paired2` pooled, **n = 20 per
condition**, both conditions alternated against one running cell.

| threshold | uncorrected (+24.4 mm) | corrected (+0.2 mm) | Fisher exact |
|---|---|---|---|
| > 5°  | 15/20 = 75% [53, 89] | 16/20 = 80% [58, 92] | 1.0000 |
| > 10° | 13/20 = 65% [43, 82] |  7/20 = 35% [18, 57] | 0.1128 |
| > 15° | 13/20 = 65% [43, 82] |  3/20 = 15% [5, 36]  | **0.0031** |
| > 20° | 12/20 = 60% [39, 78] |  **0/20 = 0%** [0, 16] | **< 0.0001** |
| > 25° |  8/20 = 40% [22, 61] |  **0/20 = 0%** [0, 16] | **0.0033** |

Intervals are Wilson 95%. Median twist 23.99° → 7.97°; maximum 31.37° → 18.71°. A rank
test using no threshold at all puts the uncorrected trial higher in 294 of 400 pairs (74%),
so the verdict does not depend on where the cut was drawn.

**Correcting the offset eliminates the high mode entirely and does not touch the low one.**
Every rotation above 20° disappears, with no exceptions in 20 trials; the rate of any
rotation above 5° is unchanged. Residual twist up to 18.7° survives correction.

## What this settles, and what it does not

- The **+24.4 mm** offset is confirmed as measured, against **+24.24 mm** predicted from the
  vendor URDF and the parsed pad-face geometry, with **19.3 mm** of a 37.5 mm pad face
  engaged. Corrected, the pad centre sits **0.2 mm** from the part's centre of mass with the
  full face engaged. The geometry is a description of the cell, not a model of it.
- The large rotations were a **couple**: contact patch 570 mm² with a 15.35 mm lever arm,
  becoming 1106 mm² with a 0.10 mm lever arm and invariant under the rotation.
- **Not settled: whether the timestep scaling survives correction.** The 0.0005 block
  (`paired_fine`) reached 4 of 20 planned trials before the session limit. Its 4 trials are
  committed and are not a result.

## Corrections to the friction campaign

Two claims in `../2026-08-25-friction-grasp/results.md` do not survive this campaign and
should be read with these alongside:

1. **Twist is bimodal, not a continuum.** A trial turns either 22–33° or under 5°, and the
   timestep sets how often the high mode is entered — 0/12 at 0.002, ~60% at 0.001, 12/12 at
   0.0005. The published "×24.5 median scaling" is that probability moving, not a magnitude
   scaling. Consequently that campaign's same-configuration blocks at 0.001 have medians of
   9.6°, 27.8°, 29.8°, 23.9° and 5.2°: it was sampling a two-state process with too few
   trials per block to see it, which is why **separate blocks cannot carry this comparison**
   and why this campaign interleaves.
2. **The spread is not attributable to unseeded OMPL.** The published record attributes it to
   "which plan the unseeded OMPL happens to return". Measured against the pad's driven
   trajectory, which is upstream of the grasp, the carry path varies by 0.13% in length and
   1.9% in peak speed across trials, and twist correlates with it at ρ = +0.10. The apparent
   ρ ≈ +0.8 against the *work-piece's* acceleration is circular: the part's twisting is
   itself relative motion and lands in its own second derivative.

## Consequence

The grasp-plane offset is worth fixing on mechanical grounds regardless — a gripper that
engages half its pad face above the part's centre of mass is wrong whatever the twist does.
This campaign adds that it is also the cause of every rotation above 20°.

The fix belongs in L0: the end-effector type declares where the pad plane sits relative to
the planning tip link, as the stroke-dependent quantity it is —
`offset(q) = 0.0718988 − (0.035465·sin q + 0.042039·cos q)` metres, 29.86 mm fully open and
18.58 mm at the 45 mm width — flowing through the bring-up plan to L3, with `PickAt`'s
hand-written `grasp_height_m` deleted.

Residual twist below 20° is not explained by the offset and remains an open sim/real
divergence for Phase 2, per ADR-0029.

## Note, 2026-08-26 — what the residual twist is, and what it is not

Added after publication, in the same style as the friction campaign's own in-place
correction. **Nothing above is withdrawn.** This campaign's headline — that correcting the
grasp plane eliminates every rotation above 20°, 12/20 → 0/20, p < 0.0001 — stands on its own
data and is untouched. What follows is about the *interpretation* of the residual, which two
later readings put in question.

**A later campaign proposes that `twist_max_deg` was partly measuring alignment.**
[`../2026-08-26-conveyor-yaw-transfer/`](../2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
finds that a gripper closing on a **yawed** part squares it up as the jaws close, and reads
the published twist figures as largely that alignment rather than a disturbance. The metric
genuinely cannot tell the two apart: `twist_max_deg` is the magnitude of the work-piece's
rotation relative to the pad since the grasp, and a magnitude does not say which way.

**Checked against this directory's own raw data, that reading does not reach this campaign.**
Re-analysed on 2026-08-26 with `../2026-08-25-friction-grasp/harness/axis_check.py`'s maths over
all 24 `paired` and 16 `paired2` carries (and the friction campaign's `step0p001` and
`step0p0005` blocks alongside, 72 carries in total):

- the net carry rotation lies along the **pad-to-pad axis**, which is horizontal, at
  |cos| ≥ 0.9776 in every trial;
- its component about the world vertical never exceeds **0.49°**;
- the part's folded yaw about the world vertical never leaves **0.00–0.84°** anywhere in any
  carry — including `paired` trial 20, the 18.71° maximum, whose vertical component is 0.01°.

The re-analysis re-implements `axis_check.py`'s arithmetic — that script cannot be imported
on a host without ROS — and reads the committed `*_samples.csv` and `*_trials.json` in this
directory and the friction campaign's. It is a re-analysis of published data with no
thresholds registered in advance, **not** a new campaign; the method is written out in the
*Correction, 2026-08-26* section of
[`../2026-08-26-conveyor-yaw-transfer/ANALYSIS.md`](../2026-08-26-conveyor-yaw-transfer/ANALYSIS.md).

The reason is in the rig rather than in the physics: `measure_grasp.spawn` passes `-x -y -z`
and no orientation, and `table_pick/surface` carries `rpy_rad [0, 0, 0]`, so the part is
presented **square** to jaws that close along world ±Y. There was no yaw for the jaws to
remove.

**So the residual is a roll between the pads, not a yaw about the tool axis**, and it remains
exactly what the *Consequence* above says it is: unexplained by the offset, and open for
Phase 2. Naming its axis matters downstream, because a roll and a yaw do not cost the same
thing — see the correction in
[ADR-0031](../../adr/0031-refuse-direct-handoff-without-orientation-certainty.md), where
18.7° was put into a presented-width calculation that only a yaw can enter, and the
correction in [ADR-0029](../../adr/0029-simulated-grasping-by-friction.md), which carries the
debt.
