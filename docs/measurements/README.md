# Measurements

Published measurement campaigns. One directory per campaign, named
`YYYY-MM-DD-<question>`.

P8 says any fidelity claim is backed by a published metric. This directory is where that
metric goes, so that a claim can be checked instead of trusted. ADR-0029 is the first
decision in this repository whose evidence is a campaign here rather than a dated
inspection of code.

## The campaigns

| Campaign | Question | Answer, in one line |
|---|---|---|
| [`2026-08-25-friction-grasp/`](2026-08-25-friction-grasp/results.md) | Is a friction grasp in `cell_a` repeatable enough to build a scenario on? | Repeatable in **position**, not in **orientation**. 84 trials. Decided [ADR-0029](../adr/0029-simulated-grasping-by-friction.md). |
| [`2026-08-25-grasp-plane-offset/`](2026-08-25-grasp-plane-offset/ANALYSIS.md) | Does the grasp-plane offset cause the twist? | It causes the **high mode** and not the rest. Rotations above 20°: 12/20 uncorrected, 0/20 corrected. Up to 18.7° of **roll about the pad-to-pad axis** survives correction. |
| [`2026-08-26-conveyor-yaw-transfer/`](2026-08-26-conveyor-yaw-transfer/ANALYSIS.md) | What yaw does a work-piece carry when it reaches a downstream outfeed, and can the gripper pick it? | The belt changes the yaw by **nothing** (36 trials), and the pick succeeds anyway — 23/23 up to 30° — because **the jaws square the part up as they close**. 74 trials. Corrected [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md). |
| [`2026-08-27-teardown-signal-family/`](2026-08-27-teardown-signal-family/results.md) | Does breaking the `SkillServer` reference cycle change the rate at which `skill_server` dies on a signal at teardown? | **Inconclusive, by its own rule 1.** The rig did not reproduce the defect at all in the pre-fix arm, so the clean post-fix arm evidences nothing. What did move is a leaked `class_loader` library, deterministically. 41 valid runs. |
| [`2026-08-28-second-world-cost/`](2026-08-28-second-world-cost/ANALYSIS.md) | Can two simulations coexist on one host, what does the second cost, and what dominates the step? | Two coexist, and **`ROS_DOMAIN_ID` is not what keeps them apart** — Gazebo transport needs `GZ_PARTITION`. A second world costs about a quarter of a world. Collision geometry is **34 % of the step**, and hulls buy **1.5x**. The headline ratio is **refused by the campaign's own validity rule**. |
| [`2026-08-29-real-time-factor-conditions/`](2026-08-29-real-time-factor-conditions/ANALYSIS.md) | What real-time factor does this cell achieve, under what condition, and is the recorded 0.14 wrong? | **Conditional, not wrong.** It reproduces on this host — both halves of the recorded pair together — when the cell is confined to about **one CPU core**; unconfined it idles above real time. Bring-up and load are rejected as the condition. No ceiling is too tight or too loose, and Gazebo's own `real_time_factor` field **over-reports by up to 4.15x under starvation**. 18 cells. |
| [`2026-08-31-capacity-and-clock-deficit/`](2026-08-31-capacity-and-clock-deficit/ANALYSIS.md) | Is this host short of the real-time floor once the throttle is lifted, and what does the clock deficit look like? | **Short by 1.11x with the shipped vendor meshes; clears the floor by 1.19x with hulls** — measured as capacity, on a **named** machine. The deficit is a **steady drip where the machine is short and rare discrete overruns where it has headroom**. The cross-host 1.23x discrepancy ADR-0049 refused to spend money on is **the throttle**, reproduced on one machine. 24 trials, 2x2, both sides concurrent. |

Read the sixth alongside the fifth and the second. It is the campaign ADR-0049 asked for, and
it is the first in this directory to **name its machine** — which is a decision clause of that
record, and which no earlier campaign satisfies. It also demonstrates the failure ADR-0049
derived from upstream source: a throttled real-time factor compresses everything above 1.0 onto
1.0, and reading one as a capacity changed an ADR's stated conclusion.

Read the second alongside the first: it corrects two of the first campaign's published
readings, and the corrections are listed in its own *Corrections to the friction campaign*
section.

The teardown campaign stands apart from the rest. It measures **the test rig's own teardown**
rather than anything the cell does, and its headline is an **inconclusive** — the
pre-registered decision rule fired, and the clean arm that followed was refused as evidence
because the arm it had to be compared against never reproduced the defect. It is here for
that reason and not in spite of it: a rule that only ever confirms is not a rule. It is also
the campaign that was nearly lost, having been committed to a branch that went stale before
it was published; its *Provenance and relocation* section records the move.

## The two residual rotations are different quantities

This directory has published **two** rotation figures for the same cell and they have been
read as one. They are not, and confusing them has already put a number into an ADR's
arithmetic where it could not belong. Whenever you quote either, quote its axis.

| Figure | What it is | Where it comes from |
|---|---|---|
| up to **18.7°** | a **roll about the pad-to-pad axis** — the part turning between the pads, horizontally | the offset campaign's corrected condition, n = 20, with the axis established by a 2026-08-26 re-analysis over 72 published carries |
| up to **10.62°** | a **yaw about the world vertical** — how the part is turned as it lies on the belt | the conveyor-yaw campaign's 12 end-to-end trials |

A yaw is what decides how wide a part presents to closing jaws, and how far along a belt its
leading edge breaks a beam. A roll is not, and cannot be substituted for one. **An angle
without an axis is not a measurement of anything** — that lesson is the conveyor-yaw
campaign's own, applied to the campaign it quoted.

Read the third alongside both. It is the campaign a decision record was corrected on: it
did not change what ADR-0031 decided, and it replaced the whole of the reason. It also
proposes a reinterpretation of the two earlier campaigns' `twist_max_deg`, which a
re-analysis of their own raw data on 2026-08-26 does **not** support — both its own
*Correction* section and the note in
[`2026-08-25-grasp-plane-offset/ANALYSIS.md`](2026-08-25-grasp-plane-offset/ANALYSIS.md)
carry that, and neither disturbs the verdicts.

## What a campaign directory contains

| Path | What it is |
|---|---|
| `criteria.md` | The question, the thresholds, and the decision rule — **written and committed before the first trial ran** |
| `results.md` or `ANALYSIS.md` | The verdict against those thresholds, its deviations, and its threats to validity |
| `raw/` | What the harness recorded. Every figure in the write-up is derived from this |
| `harness/` | The code that produced `raw/`, and the reproduction command |

## Rules

- **`criteria.md` is frozen once the first trial has run.** A threshold moved after seeing
  the data is a threshold chosen by the data. Where an interpretation genuinely had to
  change, it is recorded as a numbered deviation in the write-up, applied to data already
  collected — never by re-running until the definition suited.
- **`harness/` is frozen for the same reason, and `raw/` with it.** It is the code that
  produced the data, so editing it makes it no longer that. When the tree moves under a
  published harness — a function it names is renamed or deleted, a topic it used is now
  owned elsewhere — **annotate the campaign's write-up with a dated note and leave the
  harness alone.** A stale reference inside a harness is a fact about when the measurement
  was taken; a corrected one is a claim about code that never ran. The worked example is the
  2026-08-27 note in
  [`2026-08-26-conveyor-yaw-transfer/ANALYSIS.md`](2026-08-26-conveyor-yaw-transfer/ANALYSIS.md).
  The rule also survives a **relocation**: the teardown campaign's harness resolves its input
  paths relative to its own directory, which publishing it here changed, and the fix was a
  dated note plus a reproduction command in
  [`2026-08-27-teardown-signal-family/results.md`](2026-08-27-teardown-signal-family/results.md)
  rather than a patched script.
- **A campaign measures the simulator unless it says otherwise.** Nothing here evidences
  behaviour on the physical arm; the layout is `PROVISIONAL` and the physical scan is
  Phase 3 (charter §8).
- **Rates are rates over samples, not determinism claims.** Scenarios in this cell are not
  reproducible — see
  [`../architecture/cross-cutting-testing.md`](../architecture/cross-cutting-testing.md).
- **Do not restate a campaign's numbers elsewhere (P1).** Link to the directory. A number
  copied into a layer document is a number that will disagree with its source.
- **What is not here is not measured.** The table above is the list; count it there rather
  than trusting a number in this sentence, which was wrong within a day of being written. In
  particular, **nothing here measures the three-arm continuous line**: that it now completes
  is reported from scenario runs, with no thresholds registered in advance, and the status
  block in [CLAUDE.md §2](../../CLAUDE.md) says so. Nothing here measures the parked index
  position either, or whether the release-orientation residual accumulates over three
  stations — the conveyor-yaw campaign names that last one as explicitly unmeasured. And
  **nothing here explains a teardown signal death**: the fourth campaign measured the rate
  of one and did not reproduce it.
- **Interleave, do not block.** The offset campaign established that the twist in this cell
  is a two-state process, so a comparison split into consecutive blocks samples the two
  states unevenly and misleads. Alternate conditions against one running cell.
