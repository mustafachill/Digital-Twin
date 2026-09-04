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
| [`2026-09-01-hull-grasp/`](2026-09-01-hull-grasp/ANALYSIS.md) | Does convex-hull collision geometry change the grasp? | **Inconclusive, by its own rule S** — and the reason is the finding: the hull's wedges sit **0.41 mm behind the pad plane on the same rigid link** and never touch the part, so the mechanism [ADR-0028](../adr/0028-convex-hull-collision-meshes.md) predicted does not occur. No outcome differs; the only DETECTED metric is a control — the jaws stall **5.6 mrad earlier**. The contact patch got **shorter**, not longer, and two rules refuse to call it. 47 trials. |
| [`2026-09-01-grasp-discrimination/`](2026-09-01-grasp-discrimination/ANALYSIS.md) | What separates a real grasp from a stall on nothing, in **both** error directions? | **Both directions fire.** A real grasp — witnessed by the part's own contact sensor — is reported empty, the first time [ADR-0052](../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md)'s defect has been **observed** rather than derived. A stall on nothing is reported as a grasp, and the flip lands where the arithmetic says. The validator's ceiling sits **above** the band this cell produces. Whether the distribution moves with the commanded width is **INCONCLUSIVE** by two of its own rules, and the campaign says what n would settle it. 71 FN+FP trials plus a 262-point sweep. **Chooses none of ADR-0052's six options.** |
| [`2026-09-01-capacity-on-shipped-main/`](2026-09-01-capacity-on-shipped-main/ANALYSIS.md) | Does the configuration this repository **actually ships** clear the real-time floor, measured as capacity? | **It clears it, by 1.22x, and the vendor control misses it by 1.09x** on the same machine an hour apart. Every capacity figure here before this one was taken with `description.collision.select` flipped by hand on a branch; measured on the shipped tree with the flip reversed, **all eight conditions of [`2026-08-31`](2026-08-31-capacity-and-clock-deficit/ANALYSIS.md) reproduce within 3 %** — the branch-versus-shipped distinction changed nothing detectable. The shipped clock deficit is **0.71 s per 120 s window** with a **55 ms** worst interval. Under the throttle a second simulation appears **free** (1.997x aggregate), which is a cap artefact. 24 trials, 23 collected, **1 discarded for a real paired bring-up failure and deliberately not re-run**. **Sets neither of ADR-0049's thresholds.** |
| [`2026-09-02-option-f-regions/`](2026-09-02-option-f-regions/ANALYSIS.md) | What does option F's predicate do in the four regions nobody had measured — free air across the commanded width, the monotonicity term F removed, the wide edge, and the false-negative side? | **One region fires and one edge was never reached.** F reports a grasp on jaws **opening** onto nothing, jammed inside its window, where the superseded predicate does not — the term F removed is the one that covered it. Free air is rejected, but by F's **first** condition and never by the window, so the header's claim that the settle *"falls below it at every command"* is **false** while the predicate stays safe; the crossing lands inside the bracket predicted before any trial. The wide edge is **untested** — **rule W fires** — because the jaws square a yawed part up before the pads meet it. At a command above the validator's ceiling the old predicate reports every real grasp empty and F reports every one held. 97 trials plus an 18-trial refinement. **Chooses nothing**, and measures an unmerged branch. |
| [`2026-09-02-scenario-ceilings/`](2026-09-02-scenario-ceilings/ANALYSIS.md) | Are the scenario wall-clock ceilings still appropriate on the configuration this repository ships, at a full allocation and under load? | **Two `bringup` ceilings are TOO LOOSE at a full allocation**, and still too loose at four CPUs. Both intervals the 2026-08-29 campaign had to report *"not assessed"* under its rule D3 are instrumented here, so that debt is discharged — one of them is a TOO LOOSE verdict and the other lands INCONCLUSIVE below. **One crossing is located** and bracketed; three ceilings are **NOT LOCATED**, which is not "safe at any allocation". Eight cells have **no upper bound at all** because their measured intervals are smaller than the poll quantum — a property of the instrument, not a pass — and eight more are **NOT ASSESSED**, where rule N forbids reading silence as clearance. **Six of 28 runs were lost to the harness's own configuration read-back**, not to a wrongly configured cell, which is why every `bringup` cell at the two largest allocations rests on a single run. Rule H forbids differencing any of it against 2026-08-29. 28 runs, 4 allocations, 44 cells. **Chooses nothing:** its §0 reserves every ceiling change to the project owner, and none is proposed. |
| [`2026-09-03-stall-band-flip/`](2026-09-03-stall-band-flip/ANALYSIS.md) | Where does the **implemented** option-F predicate flip its verdict, and can that flip be bracketed to the 0.05 mm [ADR-0052](../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) §A.10 asks for? | **The narrow edge is BRACKETED at the registered 0.05 mm width; the wide edge is NOT, and the reason is the instrument rather than the data.** One trial of eighteen had the robot description read back off the running node as **zero characters** — while that same trial's record shows the rig launched the shipped description with its hull references intact, and the other seventeen read them back — and the validity rule's discard granularity is the **block**, so eighteen otherwise sound trials, the wide-edge result, command invariance's evaluability and one prediction's went with it. **A null is never a clearance:** rule N refuses to read the silence there as agreement with the arithmetic, as validation of either band value, or as evidence the edge is where the declaration says. Rule D — the arithmetic against the measurement — agrees at both brackets that could be evaluated. Command invariance is **NOT EVALUABLE** at 2 of 4 stops compared, and *"no disagreement among the two"* is not the sentence *"it held"*. 105 trials, 84 surviving, one arm, **no part, no physics and no simulator in the rig**. **Chooses nothing** — it sets no band, moves no status and does not take the monotonicity decision. |
| [`2026-09-04-following-error/`](2026-09-04-following-error/ANALYSIS.md) | Under `gz_ros2_control`, does the execution-side path tolerance stay quiet on a healthy run, and how far below [ADR-0036](../adr/0036-execution-side-trajectory-tolerances.md)'s own line does that run sit? | **The detector is not structurally silent under this backend — it fired**, twice, on the concurrently loaded arm, both attributed by the instrument's own naming to that arm's own controller and neither by its conservative fallback, with **zero unattributed events anywhere**. **Those two firings are not [`docs/open-work.md`](../open-work.md) #20's firing half**: they were **not induced**, no mechanism is attributed, and nothing here shows the tolerance can detect an obstruction. Counts, not causes — two events across three bring-ups, not one per bring-up, and the third produced none at the same schedule slot. Every quiet is a **measured** quiet: 126 trials, all admitted, **zero instrument losses** on all four arms. **At full velocity scaling the healthy peak lands above ADR-0036's own order-of-magnitude line** — the uncomfortable outcome, registered before any trial. The corrected command law is **established** and not merely admitted: every trial but the two firings agrees with it to five significant figures. Concurrent load is INDISTINGUISHABLE with both guards evaluated; the goal-side verdict is CLEAR and **uninformative by construction, exactly as registered**. Five numbered deviations, two of them findings the criteria did not contain. **Chooses nothing** — it moves no status, proposes no tolerance and does not decide whether the firing half is worth building. |

Read the eighth with [ADR-0028](../adr/0028-convex-hull-collision-meshes.md) open. It is
clause 2 of that record's promotion gate, and it is the second campaign here whose headline
is an **inconclusive** produced by a rule written before the data. The rule fired because
neither contact metric moved, and the campaign was then obliged by that same rule to say
whether the predicted mechanism was ever within reach of the part. It was not: the record's
own two figures — a pad aperture of 44.99 mm and a hulled relief shoulder at 45.40 mm on the
same link — already say the shoulder is recessed behind the pad, and the campaign measures
that clearance independently. **The geometry audit ADR-0028 published is confirmed; the
inference drawn from it is not.**

It is also the campaign whose pre-registered effect sizes did the most work. Eleven of its
eighteen metrics separate at `p < 0.01` and exactly one of them separates by as much as the
size registered in advance as interesting. A campaign reporting the other ten as findings
would have been reporting its own sample size.

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
