# Criteria — what separates a grasp from a stall on nothing, measured in both directions

**Written and committed before the first campaign trial ran.** Frozen from that commit
(`docs/measurements/README.md`, rule 1). Any interpretation that had to change afterwards is
recorded as a numbered deviation in `ANALYSIS.md`, applied to data already collected — never
by re-running until the definition suited.

- **Date opened:** 2026-09-01
- **Branch / commit under measurement:** `measure/grasp-discrimination`, off `main` at `e51238e`
- **The record that asks for it:**
  [ADR-0052](../../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md), promotion gate
  clause 2, both bullets — *the false-negative side* and *the false-positive side* — plus its
  third bullet, which requires a pre-registered rule for what would refuse the chosen option.
- **The record that constrains it:**
  [ADR-0022](../../adr/0022-gripper-as-ros2-control-controller.md). A grasp is evidenced by a
  **stall**, the controller reports and does not interpret, and deciding what a stall means is
  L3's job. This campaign measures **against** that decision, not around it: every figure below
  is a property of the stall the controller reported and of the predicate that read it.
- **The record that makes a stall width legitimate evidence:**
  [ADR-0029](../../adr/0029-simulated-grasping-by-friction.md). Friction alone holds the part
  and nothing on the simulation side assists a grasp, so a reached width at a stall is a
  measurement of the part rather than an artefact.

## 0. This campaign produces evidence and chooses nothing

ADR-0052 weighs six options, A–F, and **deliberately chooses none**. Neither does this
campaign, and the constraint is registered here rather than remembered later:

- **No option is recommended, ranked, endorsed or argued for.** Where a figure below bears on
  an option, it is reported as a quantity with the option named as its consumer, and the
  sentence stops there.
- **ADR-0052's status does not move**, and nothing in `workspace/`, `tools/` or `model/` is
  edited by this campaign. The predicate is measured exactly as it ships.
- **No threshold, ceiling or tolerance anywhere in the tree is changed**, and none may be
  changed to absorb anything found here.
- **`main` ships convex-hull collision geometry** as of 2026-09-01
  ([ADR-0028](../../adr/0028-convex-hull-collision-meshes.md), promoted against the clause
  [ADR-0051](../../adr/0051-restate-the-hull-grasp-gate.md) restates). `select: convex_hull` in
  `model/assets/types/robots/xarm5.yaml:143` in this checkout. **Every previous grasp figure in
  this repository was taken on vendor meshes and these are not** — including the friction
  campaign, the offset campaign, the conveyor-yaw campaign, and the vendor arm of the
  hull-grasp campaign. The hull arm of that campaign is the only prior figure taken on the
  geometry that now ships, and it is n = 23 taken for another question.

## 1. The questions, and the ones they are not

**Q1 — false negative.** At a genuine stall on the shipped work-piece, what is the
distribution of the margin the predicate consumes, where does the band's edge sit relative to
that distribution, and does either move with the commanded width?

**Q2 — false positive.** With **nothing between the pads** and the drive joint stopped
part-way, what does the predicate say, how far is the reported width from the threshold, and
on which side?

**Q3 — the two arithmetics.** `cite_skills::gripper_is_holding` and
`default-grasp-width-never-closes` compute the same policy in two languages by two
derivations. How far apart are they across the commandable width range?

**Q4 — the unvalidated door.** ADR-0052 records that a caller-supplied `Pick.Goal.grasp_width_m`
is validated by nothing and that L4 sends one. Can a caller-supplied width place the band
somewhere worse than the declared default does?

Not in scope, deliberately:

- **This measures the simulator, not the cell.** The layout is `PROVISIONAL` and the physical
  scan is Phase 3 (charter §8). ADR-0052 records that the physical gripper has no
  `GripperActionController` at all — the vendor macro emits the gripper's `<ros2_control>`
  block only for the simulated plugin — so **nothing here evidences a grasp on the real arm**,
  and nothing here may be read as a P2 result.
- **Speed is settled elsewhere.** No real-time-factor figure from this campaign may be quoted
  as a capacity result; see
  [`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md).
- **This is not a rate.** Every count below is a count over the trials that ran, on one
  machine, at one timestep, with one part, on one arm. ADR-0052 says of its own n = 47 that it
  is not a rate; the same applies here and to a larger n.
- **Grasp quality is not measured.** Whether the part is *held well* — twist, slip, carry — is
  the friction and offset campaigns' question. This campaign reads the close and stops.

## 2. The predicate, and the arithmetic reproduced before any trial

`cite_skills::gripper_is_holding` (`workspace/src/cite_skills/src/gripper.cpp:106-117`):

```
holding  <=>  stalled  and  not reached_goal
              and  opening(q_reached) - w_commanded  >  2 * tolerance(q_reached)
```

with, from `model/assets/types/end_effectors/xarm_parallel_gripper.yaml`:

```
pivot        = drive_pivot_y_m - pad_inset_m           = 0.009      m
crank        = hypot(finger_offset_y_m, finger_offset_z_m) = 0.0550004 m
phase        = atan2(finger_offset_z_m, finger_offset_y_m) = 0.870017 rad
opening(q)   = 2 * (pivot + crank * cos(q + phase))
tolerance(q) = |2 * crank * sin(q + phase)| * goal_tolerance,  goal_tolerance = 0.01 rad
```

**Reproduced independently on 2026-09-01, before this file was committed**, in
`harness/arithmetic.py`'s reference implementation and checked against ADR-0052 §2.1–2.2:

| quantity | this campaign | ADR-0052 |
|---|---|---|
| `q` at a 45.0 mm command | 0.452793 rad | 0.452793 |
| `2 * tolerance` at a 46.6 mm stall | **2.1244 mm** | 2.1244 mm |
| margin at that stall | 1.6000 mm | 1.6000 mm |
| band edge against a 45.0 mm command | **47.1215 mm** | 47.1215 mm |
| band width | 2.1215 mm | 2.1215 mm |
| one `goal_tolerance` of width at the commanded position | 1.0650 mm | 1.0650 mm |
| the two derivations at the shipped default | **2.1327 / 2.1380 mm** | 2.1327 / 2.1380 mm |

Every figure agrees to four decimal places. **The arithmetic is therefore not in question in
this campaign; what the cell does with it is.**

### 2.1 The quantities, named once

| symbol | definition | units |
|---|---|---|
| `w_cmd` | the width commanded — `Pick.Goal.grasp_width_m`, or `GripperCommand` translated through `gripper_position_for` | mm |
| `w_reached` | `opening(q_reached)`, the width the predicate consumes | mm |
| `margin` | `w_reached - w_cmd` | mm |
| `threshold` | `2 * tolerance(q_reached)` — the C++ derivation, at the **reached** position | mm |
| `ratio` | `margin / threshold`. **`ratio < 1` is the predicate reporting no grasp.** | — |
| `threshold_val` | `\|opening(q_cmd) - opening(q_cmd + 2*goal_tolerance)\|` — the validator's derivation, at the **commanded** position | mm |

**`ratio` is the campaign's single decision quantity** and is the one ADR-0052's gate names:
`(reached - commanded) / (2 * tolerance(q_reached))`.

## 3. The three arms

| arm | what it produces | rig | cost |
|---|---|---|---|
| **FN** | Q1, Q4 — the false-negative side | the shipped three-arm cell, headless, `Pick` on a real 50 mm work-piece | one bring-up per block |
| **FP** | Q2 — the false-positive side | a real `ros2_control_node` over `cite_test_hardware/JointStopSystem` on `arm_1_drive_joint`, **nothing between the pads** | one launch per block, no physics |
| **AR** | Q3 — the two arithmetics | both shipped implementations called directly, no cell | deterministic |

**All three read the shipped predicate rather than a copy of it.** FN reads
`Pick.Result` and the skill server's own report line; FP feeds the controller's
`GripperCommand.Result` into `cite_skills::gripper_is_holding` compiled from the shipped
source and linked from the built workspace; AR calls `cite_skills`'s C++ functions and
`cite_tools.validate.physical._grasp_discrimination_margin_m` on the same inputs. **No
reimplementation of the predicate appears in any figure**, and `harness/arithmetic.py`'s
reference implementation is used only for the §2 cross-check and for choosing the sweep
points in §5, never for a reported result.

## 4. Instruments, registered before the first trial

### 4.1 FN arm

| # | Quantity | Instrument |
|---|---|---|
| **I1** | the production verdict and its widths | the skill server's own line, `gripper: commanded %.1f mm, reached %.1f mm, stalled=%s, reached_goal=%s, effort=%.1f -> holding\|empty` (`skill_server.cpp:2141-2149`), scraped from the block's launch log. **Resolution 0.1 mm.** |
| **I2** | `w_reached` at full precision | `q_at_stall_rad` — the last `arm_1_drive_joint` sample on `/joint_states` at or before `Pick` reports `PHASE_RETREATING`, or, when `Pick` fails at the predicate, at or before the result arrives — mapped through the shipped `gripper_width_for`. |
| **I3** | `Pick.Result` | `result.code`, `result.holding`, and `result.detail`, which on the empty-grasp path prints commanded and reached widths at full `<<` precision (`describe_empty_grasp`, `skill_server.cpp:1892-1914`). |
| **I4** | a **typed, full-precision** read of the predicate's own inputs and output | after the primary record is complete, one `Grasp` goal at the same `w_cmd` with `expect_object=false` against the jaws as they stand. `Grasp.Result.reached_width_m` **is** `gripper_width_for(result->position)` and `Grasp.Result.holding` **is** `gripper_is_holding(...)` (`skill_server.cpp:906-926`). |
| **I5** | that a part was actually between the pads | a passive `gz.msgs.Contacts` sensor on the work-piece, as the hull-grasp campaign used. Finger contact points in the window around the stall. |

**I4 is a different event from the close I1–I3 report** — the jaws are already where they
stopped and are commanded there again — and it is reported **separately and never substituted
for I1 or I2**. It exists because ADR-0052 records that `q_at_stall_rad` is *"the same joint,
sampled a moment after the predicate ran, not the value the predicate consumed"*, and I4 is
the only instrument in this repository that reads the consumed value itself.

### 4.2 FP arm

| # | Quantity | Instrument |
|---|---|---|
| **I6** | what the controller reports with a stopped joint and empty jaws | `control_msgs/GripperCommand.Result` from `/cite/cell_a/arm_1/arm_1_gripper_controller/gripper_cmd` — `position`, `stalled`, `reached_goal`, `effort`. |
| **I7** | the shipped predicate's verdict on I6 | those four fields passed to `cite_skills::gripper_is_holding` through `harness/predicate_eval` — a program that links the built `cite_skills` library and adds no arithmetic of its own. |
| **I8** | that the stop engaged | `JointStopSystem`'s own `has reached a declared stop at %f` warning in the block log, and the drive joint's `/joint_states` position resting at the declared stop. |

### 4.3 AR arm

| # | Quantity | Instrument |
|---|---|---|
| **I9** | the C++ derivation | `cite_skills::gripper_width_tolerance_m`, called through `harness/predicate_eval`, linked against the built library. |
| **I10** | the validator derivation | `cite_tools.validate.physical._grasp_discrimination_margin_m`, imported and called on the `AssetType` loaded from the shipped `model/`. |

## 5. What is varied, and what is held fixed

### 5.1 FN arm — one lever, and it is the commanded width

`Pick.Goal.grasp_width_m` takes **four** values, chosen before any trial from the arithmetic
in §2 and the shipped work-piece width of 50.0 mm:

| `w_cmd` | why this value | predicted `ratio` at a 49.7 mm stall |
|---|---|---|
| **42.0 mm** | 3 mm below the shipped default — the wide-margin end, well clear of the band | ~3.7 |
| **45.0 mm** | **the shipped default** and the width L4's `PickAt` port default sends (`skill_nodes.hpp:591`, `:656`). The anchor. | ~2.2 |
| **47.0 mm** | inside `default-grasp-width-never-closes`'s 47.86 mm ceiling, and the closest registered point **above** the band edge | ~1.3 |
| **48.0 mm** | **above** that ceiling — a width the validator refuses as a declared default and never sees as a goal. Q4's door, opened deliberately. | ~0.8 |

The band edge in commanded-width terms, against a stall at `w_stall`, is
`w_stall - 2*tolerance(q_stall)`. At the hull-grasp campaign's hull median stall of 49.692 mm
that edge is at **47.58 mm**, so 47.0 mm and 48.0 mm straddle it by ±0.5 mm. **This is the
design and it is registered as such**: the campaign is built to bracket the edge, not to
avoid it.

Held fixed unless named:

| Quantity | Value | Where it comes from |
|---|---|---|
| Cell | `cell_a`, all three arms, the shipped `cite_bringup/launch/simulation.launch.py` headless | not a reduced rig |
| Arm under test | `arm_1` | as the friction and hull-grasp campaigns |
| Collision geometry | **`convex_hull`** — the shipped selection, unflipped | §0 |
| Work-piece | 50 mm cube, 0.2 kg, `mu = mu2 = 1.0`, one passive contact sensor | copied from the hull-grasp campaign's harness |
| `max_effort_n` | 60.0 N, the L0 value | ADR-0052 §5: `effort` is the commanded maximum echoed back, not a measurement |
| `max_step_size` | 0.001 s, shipped | not varied — §8 |
| Approach / retreat / grasp height | 0.10 / 0.12 / 0.03 m | the hull-grasp campaign's, verbatim |

**No deviation from the shipped tree is declared for the FN arm.** Nothing under `model/`,
`workspace/src/cite_generated/` or `workspace/src/cite_skills/` is edited.

### 5.2 FP arm — one lever, and it is where the joint stops

`arm_1_drive_joint` is stopped at a declared position by
`cite_test_hardware/JointStopSystem` ([ADR-0040](../../adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md)),
with **nothing between the pads** — there is no Gazebo and no work-piece in this rig at all.
The command is held at the shipped **45.0 mm** throughout; the stop position is the lever.

Twelve stop widths, chosen before any trial to bracket the §2 band edge of 47.1215 mm:

```
45.5  46.0  46.5  47.0  47.05  47.10  47.15  47.20  47.5  48.0  49.0  50.0   (mm)
```

`47.10` and `47.15` straddle the edge by ±0.02 mm, which is **five times finer than the 0.1 mm
the production instrument can print**. Each is converted to a drive-joint position by the
shipped `gripper_position_for` and declared as `stop_upper_rad`; `stop_lower_rad` is −1.0 rad,
which brackets the joint's initial position so the plugin's start-outside-the-stops refusal
does not fire.

**FP-C — the control.** The same rig with the gripper block on plain
`mock_components/GenericSystem` and no stop at all, commanded to the same 45.0 mm on empty
jaws. ADR-0052 §3 predicts `reached_goal = true, stalled = false`, so the predicate's first
condition rejects it and **the margin never runs**. FP-C is what establishes that ordinary
mock hardware cannot produce a false positive and that the stopped joint is what does.

### 5.3 AR arm

`w_cmd` swept from **20.0 mm to 85.0 mm in 0.25 mm steps**, plus the four FN commands, the
shipped default 45.0 mm, and the validator's own ceiling 47.86 mm. The range is the
linkage's: `opening(0.85) = 1.65 mm` closed and `opening(0.0) = 88.93 mm` open, and 20–85 mm
is the interior of that with both saturating ends excluded.

Both derivations are computed **at the commanded position**, which is the only apples-to-apples
comparison — the validator has no reached position to evaluate at. **A second, separately
reported quantity** is the C++ derivation at a *reached* position, against the validator's at
the commanded one, which is what the two implementations actually do in production. §7.5
registers both.

## 6. Design, sample size and order

### 6.1 FN

- **32 trials, 8 per commanded width, in 2 blocks of 16.** One block is one bring-up, sixteen
  trials against it, one teardown.
- **The four commanded widths are interleaved within a block**, cycling
  `42.0, 45.0, 47.0, 48.0` four times per block. `docs/measurements/README.md` requires
  interleaving rather than blocking, and unlike the hull-grasp campaign's lever this one
  **can** be interleaved: it is a field on a goal message, not a rebuild.
- **Two blocks so that a block effect is visible**, and V5 below is what spends it.
- **Quiesce 60 s** between a teardown and the next block's bring-up; the host's 1-minute load
  average is recorded at the start of every block.
- A block that aborts early is reported **with the n it actually reached**, never topped up.

### 6.2 FP

- **12 stop widths × 3 repeats = 36 trials, plus 3 FP-C control trials**, in one block against
  one launch. The stop widths are **interleaved**, cycling the twelve in order three times,
  for the same reason.
- The rig has no physics and a deterministic hardware plugin, so **the three repeats are
  expected to be exact replicates**. They are taken anyway, and their spread is reported: a
  non-zero spread is a finding about the rig and is registered as such here rather than
  explained afterwards.
- Changing a `stop_upper_rad` is a description change and therefore a relaunch. FP runs
  **one launch per stop width** and the interleaving is over the relaunch order.

### 6.3 AR

Deterministic; one pass. No repeats, and the fact that it needs none is checked by running the
sweep twice in the same invocation and requiring bit-identical output.

## 7. Thresholds — the decision rule

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.1 Minimum interesting size, per metric

Every one is derived from **the geometry or the system's own declared tolerances**, never from
campaign data.

| Metric | MIS | Why this size |
|---|---|---|
| any width in mm (`w_reached`, `margin`, `threshold`) | **0.100 mm** | it is the resolution of the production instrument — the skill server prints widths at `%.1f` mm — and it is under a tenth of the 1.0650 mm that one `goal_tolerance` is worth in width at the commanded position. Two independent derivations landing on the same size. |
| `ratio` | **0.05** | 0.100 mm against a ~2.1 mm threshold. The same size, expressed in the decision quantity's units. |
| `threshold - threshold_val` (Q3) | **0.100 mm** | materiality, not resolution: a disagreement below 0.1 mm cannot be seen by any instrument in this system that reports a width, so it cannot change any reported verdict. The exact disagreement is reported at full precision regardless. |
| `q_at_stall_rad` | **0.001 rad** | 0.100 mm of width at ~105 mm/rad through the linkage. The same size again. |

### 7.2 D1 — the false-negative direction

Over the FN trials at each commanded width, report `n`, `min`, `median`, IQR and `max` of
`w_reached`, `margin`, `threshold` and `ratio`, and the **count of trials with `ratio < 1`**
with its Wilson 95 % interval.

> **D1 — OBSERVED** at a commanded width if **at least one** valid trial there has
> `ratio < 1` while I5 witnesses finger contact. This is a real grasp reported empty.
> **D1 — NOT OBSERVED** at a commanded width if no valid trial there has `ratio < 1`, *and
> rule M below is then applied.*

### 7.3 D2 — does the distribution move with the commanded width?

Kruskal–Wallis across the four commanded widths on `w_reached`, then pairwise Hodges–Lehmann
shifts against the 45.0 mm anchor.

> **D2 — DETECTED** if `p < 0.01` **and** the largest pairwise `|HL shift| >= 0.100 mm`.
> **D2 — NOT DETECTED** if `p >= 0.01` **or** every `|HL shift| < 0.100 mm`, *and* rule R does
> not fire.

`p < 0.01` rather than 0.05 because four metrics are tested on the same trials and no
correction is applied.

**Registered in advance as the expected direction, so that the campaign can be wrong about
it:** a wider command demands less over-travel past contact, so the drive squeezes less and
`w_reached` is expected to be **weakly increasing** in `w_cmd`. If it decreases, or moves by
more than 0.5 mm across a 6 mm span of command, that is a finding about the mimic servo and is
reported as one.

### 7.4 D3 — the band edge against the distribution

Report, per commanded width and pooled:

- the band edge in **reached-width** terms, `w_cmd + threshold`;
- the band edge in **commanded-width** terms, `median(w_reached) - median(threshold)` — the
  largest command at which the observed median stall still clears the band;
- the distance from the shipped 45.0 mm command to that edge, **in mm and in units of the
  observed IQR of `w_reached`**.

The last is the quantity option B would move and option D would derive, and it is reported as
a quantity with no option preferred (§0).

### 7.5 D4 — the two arithmetics

Report `threshold` (C++, at a stated position) and `threshold_val` (validator, at the
commanded position) across the §5.3 sweep, and:

- **the linearisation term** — both evaluated at the **same** (commanded) position, so the
  only difference is linearised slope against exact finite difference;
- **the evaluation-point term** — the C++ derivation at a reached position minus the same
  derivation at the commanded position, for the reached positions the FN arm actually
  produced;
- **the total**, which is what the two production implementations differ by in practice.

> **D4 — MATERIAL** if the total exceeds **0.100 mm** anywhere in the swept range.
> **D4 — IMMATERIAL** if it does not, *and the report then states the disagreement's size and
> its trend rather than calling the P1 hole harmless* — the hole ADR-0052 §5 names is that two
> derivations of one policy are free to diverge on the next edit, and a small present
> disagreement is not evidence about that.

### 7.6 D5 — the false-positive direction

For each stop width report I6's four fields, I7's verdict, `margin`, `threshold`, `ratio`, and
**the side of the threshold the reported width falls on**. Then:

> **D5 — REPRODUCED** if at least one stop width yields `gripper_is_holding == true` with
> nothing between the pads. That is a stall on nothing reported as a grasp.
> **D5 — NOT REPRODUCED** otherwise, *and rule N below is then applied.*

Also report **the flip width** — the narrowest stop width at which the verdict becomes true —
bracketed by the sweep to 0.05 mm, against the §2 prediction of 47.1215 mm, and the width at
which the controller's `reached_goal` takes over from the margin as the rejecting condition.

### 7.7 D6 — the unvalidated caller-supplied width

> **D6 — DEMONSTRATED** if the 48.0 mm condition — a width above
> `default-grasp-width-never-closes`'s 47.86 mm ceiling, reachable only as a goal field —
> produces `ratio < 1` where the 45.0 mm condition on the same block does not.
> **D6 — NOT DEMONSTRATED** otherwise, with the observed ratios at both widths reported.

### 7.8 The rules that stop a null being read as a pass

> **Rule N — the false-positive null.** If the FP rig produces no trial in which the predicate
> returns true on empty jaws, the campaign's verdict on the false-positive direction is
> **INCONCLUSIVE**, reported as *"the rig did not reproduce it"*. **It may never be written as
> "the false-positive direction is safe", and no sentence in `ANALYSIS.md` may imply it.**
> The write-up must then state, from I6 and I8, whether the stop engaged at all and which of
> the predicate's two conditions rejected each trial.

> **Rule M — the false-negative null.** If no FN trial falls inside the band, the campaign
> reports the **minimum observed `ratio` and its distance to 1.0 in mm**, and its verdict on
> the false-negative direction is *"not observed at n = N, at these four commands, on this
> machine"* — never *"the defect does not occur"*.

> **Rule R — resolution.** For any metric whose within-condition IQR exceeds that metric's
> MIS, the instrument cannot attribute a difference of the interesting size to the lever. That
> metric is reported **UNRESOLVED**, and a non-detection on it is **INCONCLUSIVE for that
> metric — never "no difference"**.

> **Rule S — the mechanism.** If I5 witnesses no finger contact in a majority of FN trials,
> the FN arm has not measured a **genuine** stall and its verdict on Q1 is INCONCLUSIVE
> whatever the ratios say — a stall the harness cannot show was on the part is not evidence
> about a real grasp.

> **Rule T — the arms are not each other's evidence.** A clean FN arm says nothing about the
> false-positive direction and a clean FP arm says nothing about the false-negative one. The
> verdict is stated **separately for each direction**, and if either is inconclusive that
> belongs in the verdict rather than in a footnote.

### 7.9 Pre-registered predictions, so that this campaign can be wrong

| # | Prediction | Refuted by |
|---|---|---|
| **P1** | At 45.0 mm every valid FN trial clears the band (`ratio > 1`). | any trial with `ratio < 1` there |
| **P2** | At 48.0 mm every valid FN trial falls **inside** the band, producing the first observed false negative in this repository. | no trial with `ratio < 1` there |
| **P3** | Every FP trial reports `stalled = true, reached_goal = false`, and the predicate returns **true** for stop widths above 47.1215 mm. | any other combination |
| **P4** | FP-C reports `reached_goal = true, stalled = false`, so the margin never runs. | any other combination |
| **P5** | The linearisation term of D4 grows monotonically with `w_cmd` and stays below 0.100 mm across the whole swept range; the evaluation-point term is the larger of the two. | either failing |

## 8. Explicitly not measured, recorded here rather than discovered later

- **The physical gripper.** ADR-0052 records that there is no `GripperActionController` on the
  hardware path at all. Settled by the Phase 2.B bring-up and by nothing before it.
- **Any timestep but the shipped 0.001 s.** The friction campaign found grasp quality varies
  by a factor of 24 across a 4x timestep change, and the hull-grasp campaign names the
  timestep as the variable a grasp figure is most sensitive to. Every figure here is at one
  timestep.
- **Any part but the 50 mm cube, any arm but `arm_1`, any effort but 60 N.**
- **Vendor collision geometry.** The shipped selection is `convex_hull` and it is not flipped.
  Comparing the two is the hull-grasp campaign's question, already answered, and re-opening it
  here would double the trials for a comparison nobody asked for.
- **Why the drive joint reads narrower than the part it is holding.** ADR-0052 names the mimic
  servo as a candidate and nothing here isolates it. This campaign reports `w_reached` and does
  not explain it. Settled by sampling the five follower joints through a hold, which is a
  different instrument.
- **The jam case as it would occur physically.** The FP arm produces a *stopped joint*, which
  is a synthetic stop at a declared position, not a fouled finger. It answers what the
  predicate does with such a stall; it does not say where a real jam stops.
- **Determinism.** Planning is unseeded where OMPL answers and `CITE_PHYSICS_SEED` reaches only
  sensor noise, so FN trials are **independent samples from one configuration**, never
  replicates. The FP arm is a different matter and §6.2 registers what is expected there.
- **Any option in ADR-0052.** §0.

## 9. The machine, named

`docs/measurements/README.md` gained the requirement to name the machine with the capacity
campaign; this is the third campaign to do it.

| | |
|---|---|
| Host | Apple **M4 Pro** (`Mac16,8`), 12 cores, 24 GiB, macOS 26.5.2 (Darwin 25.5.0, build 25F84) |
| Container | Docker Desktop 28.5.1, Linux VM allocated **12 CPUs / 7.65 GiB**, `overlayfs` |
| Isolation | `COMPOSE_PROJECT_NAME=cite-agent-a424bd5e5ac7644b0-2554422286`, `ROS_DOMAIN_ID=73`, both derived from this checkout; own build/install/log volumes |
| Free disk | 54 GiB at the start of the session |
| Environment | `./scripts/doctor` clean on this checkout after `./scripts/bootstrap`; `./scripts/build` reported `Summary: 23 packages finished` |

**Host load before the first trial, recorded rather than claimed.** The 1-minute load average
read **3.21** on 12 cores at the time this file was written, with **11 unrelated containers**
running — a Supabase stack belonging to another project — plus a browser and macOS file
providers. **This host is not quiet and could not be made quiet.** The capacity campaign found
the same and said so before taking data; so does this one.

**What that does and does not threaten, argued rather than asserted.** Every FN quantity is a
function of simulation state sampled in simulation time — the drive joint's own position, the
contact sensor's stamps, and widths derived from a static linkage. None is a wall-clock
quantity. Host load moves how long a trial takes; it does not move where a joint stops between
two collision surfaces. The one route to the physics is a missed real-time deadline changing
the interleaving of controller updates with physics steps, which is why the load average is
recorded per block and why V5 exists. The FP and AR arms have no physics at all.

**No real-time-factor claim is made from this campaign** (§1).

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — the geometry that actually ran.** Every FN block reads the description the **running
  cell** publishes and counts collision-mesh references under `cite_description`: **13** for
  `convex_hull`. A block that disagrees is **discarded, not relabelled**, and the discard is
  reported.
- **V2 — the part was in the jaws.** An FN trial contributes to D1, D2 and D3 only if I5
  reports **at least one finger contact point** in the window from first contact to the stall.
  A trial with no contact is **excluded and reported**: without it, "a real grasp reported
  empty" would be asserted rather than measured.
- **V3 — the close happened.** A trial whose `Pick` never reported `PHASE_GRASPING` is
  excluded from every FN metric and reported, with its result code.
- **V4 — the two instruments agree.** Per trial,
  `|w_reached(I2) - w_reached(I1)| <= 0.100 mm`, the log's own resolution. A trial exceeding it
  is **excluded from the distribution and reported**: at that point the campaign does not know
  which value the predicate consumed.
- **V5 — the block effect.** Two FN blocks. If, for a metric, the difference between the two
  blocks at the **same** commanded width is larger than the largest difference **between**
  commanded widths, D2 is **downgraded to INCONCLUSIVE** whatever `p` says.
- **V6 — the stop engaged.** An FP trial contributes only if I8 shows the plugin's own stop
  warning **and** the drive joint rests at the declared stop within `0.001 rad`. A trial
  failing either is excluded and reported. If **every** FP trial is excluded, rule N fires.
- **V7 — the FP rig is not the production backend.** Every FP launch asserts that the
  description it substitutes into declared `gz_ros2_control/GazeboSimSystem` before
  substitution, exactly as `test_abort_classification_launch.py` does. A launch that finds
  anything else is discarded: the L0 backend has changed and the rig is no longer substituting
  what it thinks it is.
- **V8 — n is what it was.** Every count is reported over the trials that actually ran, with a
  Wilson 95 % interval where it is a proportion, and no condition is topped up to match
  another.
- **V9 — no threshold moves.** Nothing in this file changes once the first campaign trial has
  run. A disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data already
  collected.

**A rig-validation pass is permitted and is not data.** Before the first campaign trial, each
harness may be run once to prove it starts, connects and writes a record. Its output is
published under `raw/shakedown/`, is excluded from every figure in §7, and **may not be used
to set or adjust any threshold in this file** — every threshold above is derived from the
geometry and the declared tolerances, and none of them needs a shakedown to exist. If the
shakedown reveals a defect, **the harness is fixed and this file is not touched**.

## 11. Honesty bounds fixed in advance

- **No option is chosen, recommended or ranked, and ADR-0052's status does not move.** §0.
- **A null is not a pass.** Rules N, M, R, S and T exist for exactly that, and all five were
  written before any trial ran.
- **The two directions are reported separately.** Rule T. Measuring only the false-negative
  side would let a fix trade a defect nobody has seen for one nobody has measured, and that is
  the reason both arms exist.
- **This is one machine, one part, one arm, one timestep, and it is not a rate.**
- **Figures stay in this directory.** Nothing here is copied into ADR-0052, CLAUDE.md, the L0
  comments or any layer document (P1). Cite the directory.
