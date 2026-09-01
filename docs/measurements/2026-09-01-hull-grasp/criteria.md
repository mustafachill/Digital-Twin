# Criteria — does convex-hull collision geometry change the grasp?

**Written and committed before the first campaign trial ran.** Frozen from that commit
(`docs/measurements/README.md`, rule 1). Any interpretation that had to change afterwards
is recorded as a numbered deviation in `ANALYSIS.md`, applied to data already collected —
never by re-running until the definition suited.

- **Date opened:** 2026-09-01
- **Branch / commit under measurement:** `measure/hull-grasp`, off `main` at `d79a856`
- **Campaign this repeats:** [`2026-08-25-friction-grasp/`](../2026-08-25-friction-grasp/results.md)
- **The record that asks for it:** [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  promotion gate clause 2, as restated by its **correction of 2026-08-31**

## 1. The question, and the one it is not

**Q0 — does selecting `convex_hull` collision geometry change how a work-piece is
grasped, held and placed by `cell_a/arm_1`?**

Not in scope, deliberately:

- **Nothing is promoted.** ADR-0028 stays `Proposed` and `description.collision.select`
  stays `vendor_meshes` in the shipped tree whatever this campaign finds. A record's
  promotion is a decision taken on evidence, not a finding of the measurement.
- **Nothing is bought, tuned or widened.** No ceiling, no tolerance, no threshold in any
  scenario, and nothing under `model/` or `workspace/src/cite_generated/` outside the
  scratch flip in §5, which is reverted with `git checkout` before and after every block.
- **Speed is settled elsewhere and is not re-measured here.** See
  [`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md).
  No real-time-factor figure from this campaign may be quoted as a capacity result.
- **This measures the simulator, not the cell.** The layout is `PROVISIONAL` and the
  physical scan is Phase 3 (charter §8). Nothing here evidences a grasp on the real arm.

## 2. What the geometry predicts, and why a naive re-run would miss it

ADR-0028 said in four places that a convex hull *"fills the space between the fingers"*.
It does not: each link is hulled separately, so that space lies between two collision
bodies. At the shipped 45 mm command the jaw aperture is **44.99 mm on both geometries
over the whole 37 mm pad**, identical to 0.01 mm — pad plane, first contact and normal
unchanged. **A campaign designed around a filled gap would find nothing and read as a
clean pass.**

What the hull does change is each pad's own 2.0 mm relief step, at the proximal and the
distal end, which the hull ramps across instead — **two inclined wedges inside the part's
envelope**, aperture 48.99 → 45.40 mm at worst. Inclined contact on a flat face carries
force **along the approach axis**; the two wedges push in opposite directions and are not
symmetric in length. Those figures are ADR-0028's audit and are cited, not restated (P1).

**ADR-0028's own statement of the prediction is internally ambiguous about one axis** —
its mechanism paragraph says the force acts *"along the approach axis"* and its
bulleted prediction says *"translation of the part along the jaw axis"*. This campaign
does not choose between them: it reports the displacement on **all three** named axes and
lets the data say which one moved.

## 3. The three axes, named once

Every displacement and rotation below is expressed on this triad, taken from the left
finger link's own frame in the simulator at the instant of first contact:

| Axis | What it is | Which published residual is about it |
|---|---|---|
| `ex` | the **finger-pivot** axis | none — this is the axis ADR-0028 says nothing has measured |
| `ey` | the **jaw / closing** axis, oriented left pad → right pad | the **18.7° roll** of the offset campaign |
| `ez` | the **approach** axis, distal-positive | the **10.62° yaw** of the conveyor-yaw campaign, which is a yaw about the world vertical and coincides with `ez` at the grasp pose |

The two published residuals are **controls**, not the prediction. An angle without an axis
is not a measurement of anything (`../README.md`), so no figure below is reported without
its axis.

## 4. Questions and instruments, registered before the first trial

| # | Question | Instrument | Window |
|---|---|---|---|
| **M1** | How far does the part translate on each axis while the jaws close? | `d_pivot_mm`, `d_close_mm`, `d_approach_mm` — the work-piece position relative to `arm_1_link5`, differenced on the triad | first finger contact → settled hold |
| **M2** | How far does it rotate about the finger-pivot axis over the same window? | `pitch_pivot_deg`, with `roll_close_deg` and `yaw_approach_deg` reported beside it | same |
| **M3** | How long is the contact patch along the pad, against 37 → ~44 mm? | `patch_len_left_mm_median`, `patch_len_right_mm_median` — the `ez` extent of finger contact points, per sensor message, median over the hold | last 25 % of the closure window |
| **M4** | Is the contact **inclined**, which is the mechanism itself? | `normal_approach_component_median` / `_max` — \|n·ez\| of the reported contact normals | same as M3 |
| **C1** | Does the published **roll** about the pad-to-pad axis move? | `twist_max_deg`, the friction campaign's own computation, unchanged | grasp → release |
| **C2** | Does the **yaw** about the world vertical move? | `carry_rot_world_vertical_deg` | grasp → release |
| **C3** | Do the shipped verdicts move? | `pick_reported_holding`, `lift_m`, `held_through_transport`, `place_err_m`, `v_max_mps`, `slip_max_mm`, `slip_rate_mm_per_s` | as the friction campaign defines them |
| **C4** | Do the jaws stall in the same place? | `q_at_stall_rad`, `pad_separation_mm_*` | grasp → release |
| **C5** | Does the narrowed outer-knuckle throat show up as a **planning** effect? | non-zero `MoveTo`/`Pick`/`Place` result codes, and refusals in the block's sim log | whole block |

**M1 and M2 are measured relative to `arm_1_link5`**, the rigid body the gripper is lumped
into, so any residual arm motion during closure cancels rather than being assumed absent.
`body_move_mm` is reported per trial as the size of what was cancelled.

**M3 and M4 cannot be inferred from poses at all.** They come from a passive
`gz.msgs.Contacts` sensor on the work-piece, which the world's already-loaded
`gz::sim::systems::Contact` system serves and which nothing consumes — ADR-0029 removed
the attachment plugin that used to read contact data.

### The instrument's resolution, established before the thresholds below

Two shakedown trials on the **shipped vendor geometry**, published under
`raw/shakedown/`. They are not campaign data, are not compared against anything, and exist
only so that the thresholds in §5 can be set against a known noise floor rather than
against a hope:

| quantity | trial 1 | trial 2 | what it establishes |
|---|---|---|---|
| `patch_len_left_mm_median` | 37.519 | 37.499 | the instrument measures the **37 mm pad** to 0.02 mm |
| `normal_approach_component_median` | 8.7e-05 | 2.7e-03 | a flat pad reads as flat to ~1e-3 |
| `d_approach_mm` | +0.222 | +0.305 | between-trial spread **0.08 mm** |
| `d_close_mm` | −0.611 | −0.564 | spread **0.05 mm** (sign convention pre-flip; see the harness) |
| `pitch_pivot_deg` | +0.309 | +0.157 | spread **0.15°** |
| contact points per message | 40 | 40 | the patch is sampled by ~40 points, not by 2 |

## 5. What is varied, and what is held fixed

**One lever, and it is an L0 choice:** `description.collision.select` on
`model/assets/types/robots/xarm5.yaml`, `vendor_meshes` or `convex_hull`. Applied by
`harness/configure.py`, regenerated with `cite_tools.cli validate --write`, rebuilt into
`cite_generated` and `cite_description`, and **reverted with `git checkout` before and
after every block**. No flipped `model/` and no flipped generated artifact is committed.

Held fixed unless named:

| Quantity | Value | Where it comes from |
|---|---|---|
| Cell | `cell_a`, all three arms, the shipped `cite_bringup/launch/simulation.launch.py` headless | not a reduced rig, deliberately |
| Arm under test | `arm_1` | as the friction campaign |
| Work-piece | 50 mm cube, 0.2 kg, `mu = mu2 = 1.0`, one passive contact sensor | copied from the friction campaign's harness |
| Commanded grasp width | 0.045 m | L0 `default_grasp_width_m` |
| `max_step_size` | 0.001 s | the shipped value; **not varied** — see §8 |
| Timestep, friction coefficient, solver | shipped, unvaried | the friction campaign already varied these |

**No deviation from the shipped tree is declared.** The friction campaign had to raise
`stall_velocity_threshold` from 0.001 to 0.05; that fix has since landed, so this campaign
runs the tree as it is.

## 6. Design, sample size and order

- **48 trials, 24 per geometry, in 4 blocks of 12** — `VENDOR, HULL, VENDOR, HULL`.
  One block is one bring-up, twelve trials against it, one teardown.
- `docs/measurements/README.md` says **interleave, do not block**, because the offset
  campaign found the twist to be a two-state process. **Geometry cannot be interleaved
  against a running cell: it is a rebuild and a relaunch.** Blocking is the compromise,
  exactly as the capacity campaign made it, and V4 below is what pays for it — each
  geometry gets **two separate blocks**, so a block effect is visible as a within-geometry
  difference and can be compared against the between-geometry one.
- **n per condition is 24 against the friction campaign's largest single-condition n of
  20**, which is the shape it is being matched to. Its 84 trials span eight
  configurations; this campaign has two.
- **Quiesce 60 s** between a teardown and the next block's bring-up, and the host's
  1-minute load average is recorded at the start of every block.
- A block that aborts early is reported **with the n it actually reached**, never topped up
  from another block.

## 7. Thresholds — the decision rule

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.1 Minimum interesting size, per metric

Every one of these is derived from the **geometry or from the system's own tolerances**,
never from campaign data. A difference smaller than the metric's MIS is reported as
measured and is **not** called a change.

| Metric | MIS | Why this size |
|---|---|---|
| `patch_len_*_mm_median` (M3) | **2.0 mm** | the prediction is +7 mm (37 → 44); 2.0 mm is under a third of it and 100x the shakedown's spread |
| `normal_approach_component_max` (M4) | **0.02** | the relief ramp's own slope is ~0.22 (0.88 mm of aperture over 2 mm of `ez`, per side); 0.02 is a tenth of that and 50x a flat pad's reading |
| `d_approach_mm`, `d_close_mm`, `d_pivot_mm` (M1) | **0.20 mm** | twice the shakedown's between-trial spread, and three orders below the 100 mm place tolerance the scenario asserts |
| `pitch_pivot_deg` (M2) | **0.50°** | twice the shakedown's spread, and far below the 18.7° roll already published as tolerable |
| `twist_max_deg` (C1) | **5.0°** | the friction campaign's median at this timestep is 9.60° and its range within one configuration is 1.4–30.1°; a change smaller than 5° is not distinguishable from that process |
| `carry_rot_world_vertical_deg` (C2) | **2.0°** | the conveyor-yaw campaign's published maximum is 10.62° |
| `q_at_stall_rad` (C4) | **0.005 rad** | the gap between contact (0.4056) and the settled stall (~0.409) is 3 mrad; a change of that size moves where the jaws stop |
| `place_err_m` (C3) | **0.010 m** | a tenth of the 0.100 m tolerance the shipped scenario asserts |

### 7.2 The detection rule, D

For each metric: a two-sided **Mann–Whitney U** over the 24 vs 24 trials, and the
**Hodges–Lehmann** median of pairwise differences as the effect size.

> **D — DETECTED** if `p < 0.01` **and** `|HL shift| >= MIS`.
> **D — NOT DETECTED** if `p >= 0.01` **or** `|HL shift| < MIS`, *and* rule R below does
> not fire.

`p < 0.01` rather than 0.05 because eight metrics are tested at once and no correction is
being applied to a rate this campaign also uses for its controls.

### 7.3 The resolution rule, R — the one that stops a null being read as a pass

> **R** — if the **vendor arm's own interquartile range** on a metric is **larger than
> that metric's MIS**, the instrument cannot attribute a difference of the interesting
> size to the geometry. That metric is reported **UNRESOLVED**, and a non-detection on it
> is reported as **INCONCLUSIVE for that metric — never as "no difference"**.

**Registered in advance: R is expected to fire on C1 and probably on C2.** The friction
campaign's own figures put `twist_max_deg` between 1.4° and 30.1° inside one
configuration, which is six times C1's MIS. If it fires, this campaign reports that it
cannot see a change in the published roll at n = 24, and says what n would be needed —
it does not quietly report "the roll is unchanged".

### 7.4 The mechanism rule, S — the one that stops the campaign flattering itself

> **S** — if **neither M3 nor M4 is DETECTED**, this campaign's verdict on Q0 is
> **INCONCLUSIVE and not "no change"**, because the static geometry says the wedges exist
> and a measurement that cannot see them has not tested the prediction. The write-up must
> then report the stall aperture and the `ez` extent of the contact patch against the
> wedges' own `ez` positions (132–134 mm and 173 mm in ADR-0028's audit frame) and state
> whether the wedges were ever within reach of the part at all.

### 7.5 The outcome rules, taken unchanged from the campaign being repeated

Applied to each arm separately, and the comparison is between arms rather than against
the friction campaign's own historical numbers.

- **T1 — repetition.** `trial_success` = `grasp_acquired ∧ lift_achieved ∧
  held_through_transport ∧ placed ∧ ¬flung`, with that campaign's definitions and
  thresholds verbatim. Required in **every** trial. One failure in N is a fail for that
  arm. Wilson 95 % lower bounds reported for both.
- **T2 — slip.** `slip_max ≤ 5 mm` in every trial and `slip_rate` not significantly
  positive. **This is known to fail on vendor geometry** — the friction campaign reported
  it failing 16 of 28 — so T2 is reported here as a **between-arm comparison** and a T2
  failure on hull alone is a finding, while a T2 failure on both is a restatement.
- **T4 — flung.** A single `flung` trial in either arm is a hard fail for that arm, with
  no rate argument.

### 7.6 What each outcome means for Q0

| Outcome | Reading |
|---|---|
| T1 and T4 hold on both arms, no M1/M2 detection above MIS, M3 and/or M4 detected | **The mechanism is real and its consequence is below anything this cell reacts to.** Reported as such. Not a promotion, and not "no difference" either. |
| T1 or T4 fails on hull where vendor holds | **Hull geometry breaks the grasp.** ADR-0028's per-link exception for the fingers is what the finding points at. |
| M1 or M2 detected above MIS with outcomes intact | **The part is held slightly elsewhere** — which is the risk ADR-0028's correction says it should have been naming. Reported with the axis. |
| Neither M3 nor M4 detected | **INCONCLUSIVE by rule S.** |
| C1 or C2 UNRESOLVED by rule R | Reported as unresolved, with the n that would resolve it. |

## 8. Explicitly not measured, and it is recorded here rather than discovered later

- **Timestep sensitivity of any hull effect.** The friction campaign found grasp *quality*
  varies by a factor of 24 across a 4x timestep change. This campaign runs the shipped
  0.001 s only, so **every figure here is at one timestep** and none of it says how a hull
  behaves at another. Crossing geometry with timestep is 4 conditions and roughly twice
  the trials; it is not attempted.
- **Any arm but `arm_1`, any grasp but the shipped 45 mm command, any part but the 50 mm
  cube.** The wedges' effect depends on where the part's face sits relative to the relief
  steps, so a different part height is a different question.
- **The `end_tool` hull**, which ADR-0028 records as the one link where the trade goes the
  wrong way. It is not on the grasp path and nothing here reads it.
- **The self-collision matrix.** ADR-0028 records that the generated SRDF invokes the
  vendor's matrix, computed against vendor geometry, and that hulls narrow the reachable
  configuration space by a measured 1.9 %. C5 will see it only if it happens to refuse a
  motion in these 48 trials; **48 trials of one motion pattern is not a test of that**, and
  a clean C5 must not be reported as one.
- **Determinism.** Planning is unseeded where OMPL answers and `CITE_PHYSICS_SEED` reaches
  only sensor noise, so trials are **independent samples from one configuration**, never
  replicates. Every rate here is a rate over samples.
- **The physical arm.** See §1.

## 9. The machine, named

`docs/measurements/README.md` gained the requirement to name the machine with the capacity
campaign. This is the second campaign to do it.

| | |
|---|---|
| Host | Apple **M4 Pro**, 12 cores, 24 GiB, macOS Darwin 25.5.0 |
| Container | Docker Desktop, Linux VM allocated **12 CPUs / 7.65 GiB**, `overlayfs` |
| Isolation | `COMPOSE_PROJECT_NAME=cite-digital-twin-3748020299`, `ROS_DOMAIN_ID=99`, both derived from this checkout; own build/install/log volumes |
| Free disk | 16 GiB at the start of the session; **63 GiB** after removing 81 stale Docker volumes belonging to worktrees that no longer exist (44 GB) and 11 GB of unused build cache |
| Environment | `./scripts/doctor` — 25 passed, 0 failed, 1 skipped (`ros 2` native, expected on macOS); all three vendor patches present |

**This host cannot be made quiet, and it is not.** At the start of the session it carried a
browser with several renderer processes, a ten-container Supabase stack, and macOS file
providers; the 1-minute load average was **4.80** on 12 cores. The capacity campaign found
the same and said so before taking data.

**What that does and does not threaten here, argued rather than asserted.** Every metric in
§4 is a function of **simulation state sampled in simulation time** — pose feed stamps,
contact sensor stamps, and the drive joint's own position. None of them is a wall-clock
quantity. Host load moves how long a trial takes and does not move where the part ends up
between two collision surfaces. The one place it could reach the physics is through a
missed real-time deadline changing the *interleaving* of controller updates with physics
steps, and that is why the load average is recorded per block and why V4 exists.

**No real-time-factor claim is made from this campaign** (§1).

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — resolution.** Rule R, §7.3. Applied to every metric, reported for every metric,
  including the ones where it is inconvenient.
- **V2 — the geometry that actually ran.** Every block reads the description the **running
  cell** publishes and counts collision-mesh references under `cite_description`: 13 for
  `convex_hull`, 0 for `vendor_meshes`. A block that disagrees with its own label is
  **discarded, not relabelled**, and the discard is reported. The flip happens in L0 on the
  host, three build steps and a launch away from the physics; nothing else in the pipeline
  checks that what arrived is what was asked for.
- **V3 — the frame.** Every trial reports `pad_to_pad_axis_angle_deg`, the residual between
  the triad's `ey` and the measured pad-to-pad direction. **A trial whose residual exceeds
  5° is excluded from M1 and M2**, because a frame that has come apart relabels two axes
  rather than mis-measuring one.
- **V4 — the block effect.** Each geometry runs **two** blocks. If, for a metric, the
  difference between the two blocks of the **same** geometry is larger than the difference
  between the geometries, the detection on that metric is **downgraded to INCONCLUSIVE**
  whatever `p` says.
- **V5 — the arm was still.** M1 is a displacement measured while the arm holds position.
  A trial whose `body_move_mm` exceeds **2.0 mm** over the closure window is reported
  separately and excluded from M1 and M2: at that size the measurement is a difference of
  two moving bodies and the cancellation is doing more work than the signal.
- **V6 — n is what it was.** Every rate is reported over the trials that actually ran, with
  its Wilson 95 % lower bound, and no arm is topped up to match the other.
- **V7 — no threshold moves.** Nothing in this file changes once the first campaign trial
  has run. A disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data
  already collected.

## 11. Honesty bounds fixed in advance

- **Nothing here promotes ADR-0028**, and the campaign's own verdict may not be written as
  a recommendation. §1.
- **A null is not a pass.** Rules R and S exist for exactly that, and both were written
  before any hull trial ran.
- **The shakedown is not data.** It is two vendor trials, published, used only for §4's
  resolution table, and excluded from every figure in §7.
- **This is one machine.** Nothing here is a claim about CI, about x86_64, or about anyone
  else's host.
