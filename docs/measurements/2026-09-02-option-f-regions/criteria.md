# Criteria — the regions option F opens, closes and has never touched

**Written and committed before the first campaign trial ran, before the harness exists, and
before anything was run.** Frozen from that commit (`docs/measurements/README.md`, rule 1).
Any interpretation that had to change afterwards is recorded as a numbered deviation in
`ANALYSIS.md`, applied to data already collected — never by re-running until the definition
suited.

- **Date opened:** 2026-09-02
- **Branch under measurement:** `feat/grasp-predicate-against-the-part`, off `main` at
  **`4ef2d7c`**, head **`d3eeac4`** — five commits implementing
  [ADR-0052](../../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) option F.
- **THE BRANCH IS NOT MERGED, AND THAT IS A CONDITION OF THIS CAMPAIGN.** Every figure below
  is a property of the predicate as it stands at `d3eeac4`. **If the branch is merged,
  rebased, amended or force-pushed before the campaign completes, the campaign is invalidated
  and is re-opened as a new directory** — not annotated, not partially salvaged. Each block
  records `git rev-parse HEAD` and `git status --porcelain` at its start, and V1 below is what
  spends that.
- **The record that asks for it:** ADR-0052 **§A.10 item 2**, all four of its required
  reports, on **the implemented predicate** rather than on the 2026-09-01 campaign's committed
  raw (item 1 is the re-analysis, which is not this).
- **The record that constrains it:**
  [ADR-0022](../../adr/0022-gripper-as-ros2-control-controller.md). The controller reports and
  does not interpret; deciding what a stall means is L3's job. This campaign measures the L3
  decision and changes neither half.
- **The record that makes a stall width legitimate evidence:**
  [ADR-0029](../../adr/0029-simulated-grasping-by-friction.md). Friction alone holds the part
  and nothing on the simulation side assists a grasp, so a reached width at a stall is a
  measurement of the part rather than an artefact.
- **The campaign this one does not replace:**
  [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/ANALYSIS.md). It
  measured the **superseded** command-referenced predicate and **stays frozen and untouched** —
  no file in that directory is edited, re-run or re-analysed here. It is cited; its figures are
  not copied (P1).

---

## 0. This campaign produces evidence and chooses nothing

The instruction that opened it was **measure, do not decide**, and the constraint is registered
here rather than remembered later:

- **Nothing here sets the band.** `stall_band_narrow_m` and `stall_band_wide_m` are declared
  provisional in L0 with their provenance written into the comment beside them. This campaign
  reports where the observed distributions sit relative to those edges and **picks no value**.
- **Nothing here amends ADR-0052**, moves its status, or decides whether the monotonicity term
  `reached > commanded` returns. Those are the project owner's, and this document says so
  before any number exists so that no number can be read as an argument for one.
- **Nothing here decides whether the branch merges.** Two review findings and §A.10's own
  outstanding asks are the reason the campaign exists; a campaign is not a review verdict.
- **No threshold, ceiling, tolerance or band anywhere in the tree is changed**, and none may be
  changed to absorb anything found here. **Neither edge of the window may be widened to make a
  trial pass** — `gripper.hpp` says so on the declaration itself, and it is repeated here
  because a campaign is where the temptation arrives.
- **Nothing in `model/`, `workspace/src/` or `tools/` is edited by this campaign.** The
  predicate is measured exactly as the branch ships it. The harness lives entirely under
  `harness/` in this directory.
- **`main` ships convex-hull collision geometry** ([ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  promoted against the clause [ADR-0051](../../adr/0051-restate-the-hull-grasp-gate.md)
  restates) and this branch does not change that. Every figure here is taken on hulls.

---

## 1. The questions, and the ones they are not

**Q-A — the free-air region.** Option F rejects the measured free-air settle at the shipped
45.0 mm command. `gripper.hpp` asserts more than that: *"It falls below it at every command,
which is the property the old form did not have."* **On the production backend, across every
commanded width `Pick` permits, does a close on nothing produce a width inside F's window, and
does F report holding?**

**Q-B — the region the removed term used to cover.** F dropped `reached_width > commanded_width`.
**Does a drive joint jammed part-way through an OPENING stroke, inside the window, report
holding on jaws that are opening onto nothing?**

**Q-C — the wide edge, which nothing has ever exercised.** ADR-0052 §A.6 records that no
observed grasp came within 2.1 mm of it and that any positive value there is unevidenced.
**Does a yawed part present wide enough at the pads to stall above the wide edge, and is the
resulting report a false negative on a genuine grasp?**

**Q-D — the false-negative side, on the implemented predicate.** §A.10 item 2's first bullet.
**Over N grasps on the declared part, what is the distribution of the distance from `w_reached`
to the window's narrow edge, and what is its minimum?**

Not in scope, deliberately:

- **This measures the simulator, not the cell.** The layout is `PROVISIONAL` and the physical
  scan is Phase 3 (charter §8). ADR-0052 records that the physical gripper has no
  `GripperActionController` at all, so **nothing here evidences a grasp on the real arm** and
  nothing here may be read as a P2 result.
- **This is not a rate.** Every count is a count over the trials that ran, on one machine, at
  one timestep, with one part, on one arm.
- **Speed is settled elsewhere.** No real-time-factor figure from this campaign may be quoted
  as a capacity result; see
  [`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
  and [`2026-09-01-capacity-on-shipped-main/`](../2026-09-01-capacity-on-shipped-main/ANALYSIS.md).
- **Grasp quality is not measured.** Whether the part is *held well* — twist, slip, carry — is
  the friction and offset campaigns' question. Per ADR-0029 a scenario may assert where a part
  ends up and may not assert how it is held. This campaign reads the close and stops.
- **Where a real jam stops.** ADR-0052 §A.9.2 records that F's central claim rests on a quantity
  nobody has measured. Arm B produces a **synthetic stop at a declared position**, not a fouled
  finger, exactly as the 2026-09-01 FP arm did, and inherits that limit unchanged.

---

## 2. The predicate as implemented, and the arithmetic reproduced before any trial

`cite_skills::gripper_is_holding` at `d3eeac4`
(`workspace/src/cite_skills/src/gripper.cpp:142-163`):

```
holding  <=>  stalled
              and not reached_goal
              and w_reached  >  narrowest - stall_band_narrow_m
              and w_reached  <  widest    + stall_band_wide_m
```

with `w_reached = gripper_width_for(report.reached_position)` and **`commanded_width_m`
deliberately not read**. `resolve_grasp_width` (`gripper.cpp:104-140`) refuses, before anything
moves, a resolved width that fails `narrowest_m - w >= gripper_discrimination_margin_m(w)`.

**Reproduced independently on 2026-09-02, before this file was committed**, from the linkage in
`model/assets/types/end_effectors/xarm_parallel_gripper.yaml` and the facility block in
`workspace/src/cite_generated/bringup/cell_a_plan.yaml:50-52`:

| quantity | value | source it must agree with |
|---|---|---|
| `pivot`, `crank`, `phase` | 0.009 m, 0.0550004 m, 0.870017 rad | ADR-0052 §2.1 |
| `opening(0.00)` / `opening(0.85)` | 88.930 mm / 1.646 mm | `test_gripper.cpp` `kOpenWidth`, `kClosedWidth` |
| declared part interval | 50.000 / 50.000 mm | plan `workpieces.narrowest_width_m`, `widest_width_m` |
| declared band | 2.385 / 2.385 mm | L0 `stall_band_narrow_m`, `stall_band_wide_m` |
| **F's window** | **[47.615, 52.385] mm** | `test_gripper.cpp` `kWindowLow`, `kWindowHigh` |
| window edges as drive positions | 0.428191 rad / 0.382862 rad | derived here |
| `gripper_discrimination_margin_m(45.0 mm)` | 2.13797 mm | ADR-0052 §A.11's 2.137972 mm |
| validator ceiling, 50.0 − that margin | **47.862 mm** | ADR-0052's 47.86 mm |
| **largest width `resolve_grasp_width` permits** | **47.8769 mm** | solved here on the shipped function's own condition |
| free-air settle at 45.0 mm, from `kFreeAirSettle = 0.444793 rad` | **45.852 mm** | `gripper.hpp`'s 45.852 mm |

**The arithmetic is therefore not in question in this campaign; what the cell does with it is.**

### 2.1 The quantities, named once

| symbol | definition | units |
|---|---|---|
| `w_cmd` | the width commanded — `Grasp.Goal.width_m`, or `Pick.Goal.grasp_width_m` after `resolve_grasp_width` | mm |
| `w_reached` | `gripper_width_for(reached_position)`, the width the predicate consumes | mm |
| `edge_lo` / `edge_hi` | 47.615 / 52.385 mm, F's window on the shipped model | mm |
| `d_narrow` | `w_reached - edge_lo`. **Negative is F reporting empty on the narrow side.** | mm |
| `d_wide` | `edge_hi - w_reached`. **Negative is F reporting empty on the wide side.** | mm |
| `holding_F` | the shipped predicate's verdict, read from the running node | — |
| `holding_S` | the **superseded** command-referenced predicate's verdict on the same inputs, built from `4ef2d7c` (§4.4) | — |

**`d_narrow` and `d_wide` are the campaign's decision quantities**, and they are the two §A.10
item 2 names: the distance from `w_reached` to the narrow edge, and the distance from the
largest observed stall to the wide edge.

### 2.2 Two predictions computed before any trial, so that the arms can be wrong

**The free-air settle tracks the command.** `GripperActionController` ends a goal when
`|error| < goal_tolerance`, so the joint rests short of the command by up to one tolerance and
the width reads high by the linkage slope. Two bounding models: the **measured** shortfall of
0.008 rad behind `kFreeAirSettle`, and the **worst-case** 0.010 rad of one full tolerance.

| `w_cmd` | settle at 0.008 rad | settle at 0.010 rad | inside [47.615, 52.385]? |
|---|---|---|---|
| 45.00 mm | 45.852 mm | 46.065 mm | no, both |
| 46.50 mm | 47.349 mm | 47.561 mm | no, both — and 0.054 mm below the edge at 0.010 rad |
| 47.00 mm | 47.848 mm | 48.060 mm | **yes, both** |
| 47.50 mm | 48.347 mm | 48.558 mm | **yes, both** |
| 47.8769 mm | 48.722 mm | 48.933 mm | **yes, both** |

**Predicted crossing of `edge_lo`: a commanded width between 46.554 mm (0.010 rad) and
46.766 mm (0.008 rad)** — inside the range `resolve_grasp_width` permits, and therefore inside
the range a caller may ask for. This is the arithmetic behind Q-A and it is registered here so
that a measurement can refute it.

**A yawed square presents wider than its side.** A 50 mm square yawed by θ presents
`50·(cos θ + sin θ)` across the pads, which crosses `edge_hi = 52.385 mm` at **θ > 2.803°**.
The conveyor-yaw campaign
([`2026-08-26-conveyor-yaw-transfer/`](../2026-08-26-conveyor-yaw-transfer/ANALYSIS.md))
measured an end-to-end yaw residual well past that — **its figure is cited and not copied
(P1); read it there.** Presented widths: 51.715 mm at 2°, 52.548 mm at 3°, 54.168 mm at 5°,
57.923 mm at 10°, 59.303 mm at 12°.

**And that same campaign found the jaws square the part up as they close**, which is why Arm C
below measures the yaw **at the stall** and not only at the spawn: the presented width is what
the geometry offers, not necessarily what the pads meet.

---

## 3. The four arms, and rule T over them

| arm | question | rig | what makes it different from the 2026-09-01 campaign |
|---|---|---|---|
| **A** | Q-A — free air across commanded width | the shipped cell, headless, **production backend**, nothing between the pads | that campaign ran **all 39 of its false-positive trials at one commanded width**, so the command was never a lever |
| **B** | Q-B — a jammed **opening** stroke | a real `ros2_control_node` over `cite_test_hardware/JointStopSystem`, no physics | that campaign only ever jammed a **closing** stroke, where the removed term was satisfied anyway |
| **C** | Q-C — the wide edge, via part yaw | the shipped cell, headless, a yawed 50 mm cube | nothing in this repository has ever exercised the wide edge |
| **D** | Q-D — the false-negative side | the shipped cell, headless, `Pick` on the declared part | that campaign measured the **superseded** predicate; this measures the implemented one |

> **Rule T — the arms are not each other's evidence.** A clean result in one arm says nothing
> about any other. **Every verdict below is stated per arm**, and an inconclusive one belongs in
> the verdict rather than in a footnote. In particular: Arm A finding nothing does not make the
> wide edge safe, and Arm C finding nothing does not make free air safe.

**All four arms read the shipped predicate rather than a copy of it.** `Grasp.Result.holding`
**is** `cite_skills::gripper_is_holding`'s return value and `Grasp.Result.reached_width_m`
**is** `gripper_width_for(result->position)` (`skill_server.cpp:2227-2234`, `:971-974`). **No
reimplementation of the predicate appears in any reported verdict.** The reference
implementation in `harness/arithmetic.py` is used only for the §2 cross-check and for choosing
sweep points, never for a reported result.

---

## 4. Instruments, registered before the first trial

### 4.1 Common to every arm that drives the cell

| # | Quantity | Instrument |
|---|---|---|
| **I1** | the verdict and the widths, typed and at full precision | `Grasp.Result` — `holding`, `reached_width_m`, `measured_effort_n`, `result`. Driven with `expect_object=false` in arms A and B, so the fields are reported rather than converted into an `EXECUTION_FAILED`; `expect_object=true` in arms C and D, which is the production path. Both copy the three fields **before** the check (`skill_server.cpp:970-975`). |
| **I2** | `stalled` and `reached_goal`, which no result message carries | the skill server's own line, `gripper: commanded %.1f mm, reached %.1f mm, stalled=%s, reached_goal=%s, effort=%.1f -> holding\|empty` (`skill_server.cpp:2248-2255`), scraped from the block log. The two booleans are exact; **the two widths there are 0.1 mm and are the coarse instrument**, used only for V4. |
| **I3** | `w_reached` independently of the skill server | the last `arm_1_drive_joint` sample on `/joint_states` at or before the result arrives, mapped through the shipped closed form. |
| **I4** | that something was, or was not, between the pads | a passive `gz.msgs.Contacts` sensor on the work-piece, as the hull-grasp and grasp-discrimination campaigns used. Finger contact points in the window around the stall. In arms A and B its job is **inverted**: it must witness **no** contact. |
| **I5** | the part's pose and yaw through the close | the model pose from Gazebo transport, sampled at the spawn, at first contact and at the stall. **Every Gazebo-transport call goes through `cite_bringup/gz.py` and carries the plan's `GZ_PARTITION`** (CLAUDE.md §10, ADR-0042); an unpartitioned probe reaches no world and **exits 0**. |

### 4.2 Arm A only

| # | Quantity | Instrument |
|---|---|---|
| **I6** | that this width is one a caller may ask for | `cite_skills::resolve_grasp_width` itself, called through `harness/predicate_eval` on the plan's own values, recorded per trial as `Goal` / `Default` / `Refused`. **The permitted range is read from the shipped function, never from the 47.8769 mm in §2.** |

### 4.3 Arm B only

| # | Quantity | Instrument |
|---|---|---|
| **I7** | that the stop engaged | `JointStopSystem`'s own `has reached a declared stop at %f` warning in the block log (`joint_stop_system.cpp:186-191`), **and** the drive joint resting at the declared stop within 0.001 rad. |
| **I8** | that the fixture did not manufacture the fault | the absence of the plugin's `starts at %f, outside its declared stops` refusal (`joint_stop_system.cpp:171-182`). A launch carrying it produced **no data at all** and is reported as a launch that did not run. |

### 4.4 The superseded predicate, as a comparison quantity only

**`holding_S` is computed by building the base commit's shipped source, not by rewriting it.**
A detached `git worktree` at **`4ef2d7c`** is built once; `harness/predicate_eval_superseded`
links that build's `cite_skills` and adds no arithmetic of its own. Its sha256 and the worktree
commit are recorded in `raw/provenance.txt` per build, in the shape the 2026-09-01 campaign used
for its own `predicate_eval`.

> **`holding_S` never enters a verdict.** It is reported beside `holding_F` so that a reader can
> see which regions the change opened and which it closed, and for no other purpose. **A
> disagreement between them is a datum and not a defect**, in either direction — deciding what
> to do about one is ADR-0052's and the owner's (§0).

---

## 5. What is varied, and what is held fixed

### 5.1 Arm A — the lever is the commanded width, and the pads are empty

**The rig is the shipped cell on the production backend, and a mock substitute is refused.**
The 2026-09-01 campaign's §3.1 established that `mock_components/GenericSystem` fabricates a
stall on a ramping joint after exactly `stall_timeout`, because it writes velocity 0.000000 and
claims no velocity command interface — *"a property of mock hardware's dead velocity channel,
not of the shipped backend"*, and it **may not be counted as evidence about the production
system in either direction**. That campaign lists *"whether ordinary free air on the production
backend behaves as ADR-0052 §3 predicts"* as **explicitly unmeasured**. Arm A is that
measurement, and running it on mock hardware would repeat the error the earlier campaign
already caught.

**A synthetic stop is refused for the same arm, for a different reason.** Under F the verdict is
a function of `w_reached` alone, and a `JointStopSystem` stop **pins `w_reached` independently
of the command** — so a stop-sweep rig cannot answer whether the verdict moves with the command.
It has to be the controller's own settle. This is why Arm A is not the 2026-09-01 FP arm re-run.

**Commanded widths.** A registered coarse grid across the permitted range, at 0.25 mm:

```
45.00  45.25  45.50  45.75  46.00  46.25  46.50  46.75
47.00  47.25  47.50  47.75  47.85          (mm)
```

plus **45.0 mm** (the shipped default), **46.5, 47.0, 47.5**, and **47.85 mm** as the largest
grid point below the permitted ceiling, all of which the grid already contains. Each is checked
against I6 before it is used; a width I6 returns `Refused` for is **excluded from the A1 verdict
and reported separately** (§7.1's scope clause).

**A registered refinement procedure, whose step is fixed here and whose location is not.**
After the coarse grid, the interval between the **last** grid point with `holding_F = false` and
the **first** with `holding_F = true` is swept at a **0.05 mm step**, three trials per point.
**The step is a threshold and is registered; the interval is a bracket and is located by the
data — that is bracketing, not a threshold chosen by the data**, and the distinction is written
here so that it is not argued later. If the coarse grid produces no flip, no refinement runs and
rule N-A applies.

Held fixed unless named:

| Quantity | Value | Where it comes from |
|---|---|---|
| Cell | `cell_a`, all three arms, the shipped `cite_bringup/launch/simulation.launch.py` headless | not a reduced rig |
| Arm under test | `arm_1` | as the friction, hull-grasp and grasp-discrimination campaigns |
| Collision geometry | **`convex_hull`** — the shipped selection, unflipped | §0 |
| Between the pads | **nothing.** No work-piece is spawned in Arm A at all | Q-A |
| `max_effort_n` | 60.0 N, the L0 value | ADR-0052 §5: `effort` is the commanded maximum echoed back, not a measurement |
| `max_step_size` | 0.001 s, shipped | not varied — §8 |

### 5.2 Arm B — the lever is where the joint is jammed, and the stroke OPENS

**The direction is the whole of this arm, and it is registered before any trial.** The removed
term was `w_reached > w_cmd`. A **closing** stroke satisfies it structurally: the jaws stop short
of a narrower command, so the reached width is always the larger. Commanding a close to 52 mm
against a 50 mm part is **physically unreachable as a counter-example** — the jaws pass 52 mm
before they meet the part, the goal is reached, and F rejects on `reached_goal`. **So the region
the removed term used to cover is reached only by an OPENING stroke that jams part-way**, where
the joint is held **more closed** than commanded and `w_reached < w_cmd`.

> **Scope limit, registered rather than left to be assumed: a closing stroke cannot produce this
> case, and the campaign says so in its own verdict.** Arm B tests one direction of travel. Its
> silence about the other is a fact about the mechanism, not an untested gap, and `ANALYSIS.md`
> must state it in that form.

**The rig.** A real `ros2_control_node` over `cite_test_hardware/JointStopSystem` on
`arm_1_drive_joint` with a real skill server, the shape
`workspace/src/cite_bringup/test/test_grasp_predicate_launch.py` already uses — **with the stops
reversed**. The jaws must start **closed** and open into a **lower** stop:

- `stop_lower_rad` at the jam position; `stop_upper_rad` at `+1.0` rad, inert.
- The drive joint's initial position is set **closed** through `mock_components/GenericSystem`'s
  `initial_value` state-interface parameter, because `JointStopSystem` **refuses to run** if the
  joint starts outside its stops (I8) — *"a stop that has to move the arm to take effect
  manufactures the fault it is supposed to detect."* A rig that cannot start closed cannot run
  this arm, and that is a rig failure to report, never a reason to relax the stop.

**Jam positions**, converted to drive positions by the shipped `gripper_position_for`, each
driven by a `Grasp` at a commanded width **wider** than the jam so the stroke is an opening one:

| jam width | drive position | where it sits | role |
|---|---|---|---|
| 46.000 mm | 0.443404 rad | below `edge_lo` | **control, narrow side** |
| 48.000 mm | 0.424555 rad | inside the window | condition |
| 50.000 mm | 0.405605 rad | the declared part's own width | condition |
| 52.000 mm | 0.386545 rad | inside the window | condition |
| 54.000 mm | 0.367366 rad | above `edge_hi` | **control, wide side** |

Commanded width for every Arm B trial: **56.000 mm**, wider than every jam above, so the stroke
opens in all of them and `w_reached < w_cmd` throughout. **The command is held fixed** — under F
it does not enter the verdict, and holding it fixed is what makes that checkable rather than
assumed.

### 5.3 Arm C — the lever is the part's yaw

**Yaw setpoints**, spawned by `cite_bringup/gz.py` with the part's yaw about the world vertical:

```
0.0  1.5  3.0  4.5  6.0  8.0  10.0  12.0   (degrees)
```

0° is the control. 3.0° is the first setpoint past the 2.803° crossing §2.2 computes; 12° spans
past the conveyor-yaw campaign's measured residual. Everything else is §5.1's fixed set, plus a
50 mm cube with one passive contact sensor, `mu = mu2 = 1.0`, 0.2 kg, and the hull-grasp
campaign's approach / retreat / grasp heights of 0.10 / 0.12 / 0.03 m verbatim.

**A yaw is not a roll.** `docs/measurements/README.md` carries this repository's own lesson that
two published rotation figures are different quantities and that **an angle without an axis is
not a measurement of anything**. Every angle in this arm is a **yaw about the world vertical**,
recorded with its axis, and no figure from the offset campaign may be substituted for one.

### 5.4 Arm D — the shipped command, and the door above the ceiling

Two conditions, **and they go through two different doors, which is itself a finding to report**:

| condition | door | why |
|---|---|---|
| **45.0 mm**, the shipped default | `Pick`, `expect_object=true` | the production path, and the width L4's `PickAt` port default sends |
| **48.0 mm**, above the validator's 47.862 mm ceiling | `Grasp`, `expect_object=true` | **`Pick` cannot reach it on this branch.** `resolve_grasp_width` refuses it before anything moves; `execute_grasp` applies no such refusal (`skill_server.cpp:955-975`), so `Grasp` is the only door left |
| **48.0 mm through `Pick`** | `Pick` | run anyway, **three trials**, to record the refusal itself: `PRECONDITION_FAILED`, no motion, and the detail string. This is a reported quantity, not a verdict |

**The 48.0 mm condition is §A.10 item 2's "at least one command above the validator's ceiling"**,
and the two-door split is registered here because ADR-0052 §A.8 records that the refusal's cost
is real: *"on the shipped model this refuses a goal-supplied 48.0 mm, and the campaign shows this
cell handles 48.0 mm"*. What that refusal costs, measured on this branch, is a quantity this
campaign reports and does not judge.

---

## 6. Design, sample size and order

**Interleave, do not block** (`docs/measurements/README.md`). Every lever below is a field on a
goal message or a spawn pose, so every arm that shares a bring-up interleaves its conditions
within it.

| arm | design | trials |
|---|---|---|
| **A** | 13 coarse widths × 3, interleaved, in 2 blocks; plus the refinement grid at 0.05 mm × 3 | 39 + refinement |
| **B** | 5 jam positions × 3. A jam position is a description change and therefore a relaunch, so the interleaving is over the **relaunch order** | 15 |
| **C** | 8 yaw setpoints × 3, interleaved, in 2 blocks | 24 |
| **D** | 45.0 mm × 8 and 48.0 mm × 8, interleaved, in 2 blocks of 8; plus 3 `Pick`-refusal trials | 16 + 3 |

**Two blocks wherever the cell is brought up**, so that a block effect is visible; V6 is what
spends them. **A block that aborts early is reported with the n it actually reached, and is
never topped up** (V8). Quiesce 60 s between a teardown and the next bring-up, and record the
host's 1-minute load average at the start of every block.

**Arm B is expected to be exactly replicated** — no physics, a deterministic plugin — and its
three repeats are taken anyway. **A non-zero spread there is a finding about the rig** and is
registered as such here rather than explained afterwards, which is the shape the 2026-09-01
campaign's FP arm used and the shape that caught its own control's defect.

**Order:** B, then A, then D, then C. B is the cheapest and the only one with no cell; A answers
the question with the largest predicted effect; C is last because it is the one whose mechanism
is least certain (§2.2).

---

## 7. Thresholds — the decision rules

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.0 Minimum interesting size, per metric

Every one is derived from **the geometry or the system's own declared tolerances**, never from
campaign data.

| Metric | MIS | Why this size |
|---|---|---|
| any width in mm — `w_reached`, `d_narrow`, `d_wide` | **0.100 mm** | inherited from the 2026-09-01 campaign's rule R, which reported **every** width metric UNRESOLVED at this size. It is the production log's own `%.1f` resolution and under a tenth of what one `goal_tolerance` is worth in width at the commanded position. Two independent derivations landing on the same size |
| the Arm A flip location | **0.05 mm**, as a **bracket** | the resolution the 2026-09-01 campaign achieved on its own flip. **A bracket is not an MIS**: a 0.05 mm bracket does not resolve a 0.1 mm difference, and rule R-A below is what stops the two being conflated |
| yaw | **0.5°** | the setpoint resolution the spawn can hold, and an order below the crossing in §2.2 |
| drive position | **0.001 rad** | 0.100 mm of width through the linkage. The same size again |

### 7.1 A1 — the free-air region

Report, per commanded width: `n`, `w_cmd`, I6's source verdict, `w_reached` (min / median / IQR
/ max), `stalled`, `reached_goal`, `holding_F`, `holding_S`, `d_narrow`, and I4's contact count.

> **A1 — REPRODUCED** if **at least one valid trial at a commanded width `resolve_grasp_width`
> permits** reports `holding_F = true` with nothing between the pads and I4 witnessing no
> contact. That is a stall on nothing reported as a grasp, on the production backend, at a width
> a caller may ask for.
> **A1 — NOT REPRODUCED** otherwise, *and rule N-A below is then applied.*

**A1 decomposes, and the decomposition is registered because a NOT REPRODUCED here would
otherwise be read as clearing a claim it does not touch.** F has two independent gates and
`gripper.hpp` rests its free-air argument on the second:

> **A1a — the flags.** Does a free-air close on the production backend report
> `stalled ∧ ¬reached_goal`? Reported as a count per commanded width. **If it is false
> everywhere, the first condition is what rejects free air on this backend and the window is
> never consulted** — which must be written in exactly that form.
>
> **A1b — the width.** Independently of A1a: does `w_reached` fall inside [47.615, 52.385] mm?
> **A1b — INSIDE** at a commanded width if the median `w_reached` there lies within the window
> by more than the 0.100 mm MIS. **A1b is what tests `gripper.hpp`'s sentence** *"It falls below
> it at every command"*, and **A1b INSIDE at any permitted command falsifies that sentence
> whatever A1a says.**

**Report as its own quantity:** the lowest commanded width at which `holding_F` flips to true —
or, if A1a is false throughout, at which **A1b** goes INSIDE — **bracketed to 0.05 mm or finer**,
against the 46.554–46.766 mm §2.2 predicts.

**Widths I6 returns `Refused` for are outside A1's verdict** and are reported in their own row.
`Grasp` applies no such refusal, so such a width is still commandable through that action; that
is recorded as an observation about the door and **is not turned into a verdict here** (§0).

> **Rule N-A — the free-air null.** If no valid trial reports `holding_F = true`, the verdict is
> **"not reproduced at n = N, at these commands, on this machine, on this backend"**. **It may
> never be written as "free air is safe at any command", and no sentence in `ANALYSIS.md` may
> imply it.** The write-up must then state, from A1a and A1b, **which** of F's two conditions did
> the rejecting at each command — because "the window rejects free air" and "the flags reject
> free air" are different claims and only one of them is `gripper.hpp`'s.

> **Rule R-A — resolution.** If the within-command spread of `w_reached` exceeds the 0.05 mm
> bracket step, **the flip is reported as an interval containing both verdicts rather than as a
> point**, and is **UNRESOLVED at 0.05 mm**. And for any metric whose within-condition IQR
> exceeds that metric's MIS, a non-detection is **INCONCLUSIVE for that metric — never "no
> difference"**. This is the 2026-09-01 campaign's rule R, which fired on every width metric it
> had; it is inherited rather than reinvented, and it is expected to fire here too.

### 7.2 B1 — the region the removed term used to cover

Report, per jam position: `n`, jam width, commanded width, `w_reached`, `stalled`,
`reached_goal`, `holding_F`, `holding_S`, `d_narrow`, `d_wide`, I7 and I8.

> **B1 — REPRODUCED** if at least one valid trial with the joint jammed **inside** the window
> during an **opening** stroke reports `holding_F = true`. That is F reporting holding on jaws
> that are opening onto nothing.
> **B1 — NOT REPRODUCED** otherwise, *and rule N-B applies.*

**Report:** `holding_S` on the same trials — whether the superseded predicate reported holding
there — and the two controls at 46.0 mm and 54.0 mm, which are the only trials in this arm
expected to be rejected by the window itself.

> **Rule N-B — the opening-jam null.** If no valid trial reports `holding_F = true`, the verdict
> is **"not reproduced at n = N on this rig"**, and the write-up must state from I7 and I8
> whether the stop engaged at all and which condition rejected each trial. **It may not be
> written as "an opening stroke cannot produce a false positive"**, and it may not be
> generalised to a closing stroke in either direction (§5.2's scope limit).

### 7.3 C1 — the wide edge

Report, per yaw setpoint: `n`, yaw at spawn, **yaw at the stall** (I5), presented width from
§2.2's arithmetic, `w_reached`, `stalled`, `reached_goal`, `holding_F`, `holding_S`, `d_wide`,
and I4's contact count.

> **C1 — CROSSED** if at least one valid trial **with witnessed finger contact** produces
> `w_reached > 52.385 mm`. That is a genuine grasp on a real part reported empty by the wide
> edge — the false-negative mode ADR-0052 §A.9.5 records as never having been exercised.
> **C1 — NOT CROSSED** otherwise, *and rule S-C and rule W below both apply.*

**Report, as its own quantity, because §A.10 item 2 requires it:** **the distance from the
largest observed stall in the whole campaign to the wide edge**, over every arm that produced a
genuine grasp, with the trial that produced it named.

> **Rule W — the refusal, in ADR-0051's rule-S shape, and it is mandatory.** If the campaign
> produces **no trial within 0.100 mm of the wide edge**, it **has not tested that edge**. Its
> silence there may not be read as a pass, as a validation of `stall_band_wide_m`, or as
> evidence that the edge is far enough away. The verdict is stated as *"the wide edge remains
> unexercised; the closest approach was X mm"*, and ADR-0052 §A.9.5 stands unchanged.

> **Rule S-C — the mechanism, in ADR-0051's rule-S shape.** If I4 witnesses **no finger contact
> in a majority of Arm C's valid trials**, the arm has not measured a genuine grasp and **C1 is
> INCONCLUSIVE whatever the widths say** — a stall the harness cannot show was on the part is
> not evidence about a real grasp.

> **Registered in advance as the expected mechanism, so that the campaign can be wrong about
> it.** The conveyor-yaw campaign found that **the jaws square the part up as they close**. If
> `w_reached` does not track the presented width in §2.2's table, the squaring is the candidate
> explanation and **the yaw at the stall is the instrument that decides it** — which is why I5
> samples it there and not only at the spawn. A C1 of NOT CROSSED **caused by squaring is a
> different finding from one caused by the edge being far away**, and `ANALYSIS.md` must
> distinguish them or say it cannot.

### 7.4 D1 — the false-negative side, on the implemented predicate

Report, per condition and pooled: `n`, `w_reached` (min / median / IQR / max), **`d_narrow`
distribution and its minimum**, `holding_F`, `holding_S`, I4's contact count, and the count of
trials with `holding_F = false` with its Wilson 95 % interval.

> **D1 — OBSERVED** if at least one valid trial with I4 witnessing finger contact reports
> `holding_F = false`. That is a real grasp reported empty by the implemented predicate.
> **D1 — NOT OBSERVED** otherwise, *and rule M applies.*

**Report separately:** the three `Pick`-at-48.0 mm refusal trials — the result code, the detail
string, and that no motion occurred — as the measured cost of `resolve_grasp_width`'s ceiling on
this branch.

> **Rule M — the false-negative null.** If no valid trial is reported empty, the campaign reports
> **the minimum observed `d_narrow` and its sign**, and the verdict reads *"not observed at
> n = N, at these commands, on this machine"* — **never "the defect does not occur"**.

### 7.5 Pre-registered predictions, so that this campaign can be wrong

| # | Prediction | Refuted by |
|---|---|---|
| **P1** | In free air on the production backend, every trial reports `reached_goal = true` and `stalled = false`, so F's **first** condition rejects and A1 is NOT REPRODUCED while **A1b goes INSIDE at 47.0 mm and above**. | any free-air trial with `stalled ∧ ¬reached_goal`; or A1b staying OUTSIDE at every permitted command |
| **P2** | A1b is INSIDE at 47.00, 47.25, 47.50, 47.75 and 47.85 mm and OUTSIDE at 45.00 mm, with the crossing between 46.50 and 47.00 mm. | any of those going the other way |
| **P3** | Arm B reports `holding_F = true` at the 48.0, 50.0 and 52.0 mm jams and `false` at 46.0 and 54.0 mm; `holding_S` is **false at every one of the five**, because the reached width is below the command in all of them. | any other combination |
| **P4** | Arm C's `w_reached` does **not** track the presented width, because the jaws square the part up, and C1 is NOT CROSSED with rule W firing. | `w_reached` within 0.100 mm of the presented width at any yaw ≥ 3°, or C1 CROSSED |
| **P5** | Arm D's minimum `d_narrow` at 45.0 mm is positive — every valid grasp admitted — and D1 is NOT OBSERVED, with rule M applying. | any admitted-contact trial reporting empty |
| **P6** | Arm B's three repeats per jam are exact replicates to 1e-9 rad. | any non-zero spread, which is a finding about the rig |

---

## 8. Explicitly not measured, recorded here rather than discovered later

- **The physical gripper.** ADR-0052 records there is no `GripperActionController` on the
  hardware path at all. Settled by Phase 2.B bring-up and by nothing before it.
- **Where a real jam stops.** Arm B is a synthetic stop at a declared position, not a fouled
  finger. ADR-0052 §A.9.2 stands unchanged, and this campaign does not narrow it.
- **Whether the stall distribution moves with the commanded width (ADR-0052 §A.9.1).** That is
  the 2026-09-01 campaign's D2, reported INCONCLUSIVE by two of its own rules and stated there to
  be about 25x too small. **This campaign is smaller on that question, not larger**, and any
  appearance of an answer to it here is an artefact of n. It is named as unmeasured so nobody
  reads Arm D's two conditions as addressing it.
- **Why the drive joint reads narrower than the part it holds (ADR-0052 §A.9.3).** F's narrow
  edge must cover exactly this quantity and nothing here isolates it. The measurement that would
  settle it is sampling the five follower joints alongside `drive_joint` through a hold, which is
  a different instrument.
- **A closing stroke's behaviour in Arm B's region.** §5.2, structurally.
- **Any timestep but the shipped 0.001 s, any part but the 50 mm cube, any arm but `arm_1`, any
  effort but 60 N, and vendor collision geometry.** The friction campaign found grasp quality
  varies by a factor of 24 across a 4x timestep change; every figure here is at one timestep.
- **A facility declaring more than one part.** F's discrimination **is** the width of the window
  and the window widens with the declared spread (ADR-0052 §A.5). The shipped interval is
  degenerate — 50.0 to 50.0 mm — and this campaign measures the degenerate case only.
- **Whether the band should move.** §0.

---

## 9. The machine, named

`docs/measurements/README.md` gained the requirement to name the machine with the capacity
campaign; this campaign names it because the cell's real-time factor is CPU-sensitive and that
is measured, not assumed — see
[`2026-08-29-real-time-factor-conditions/`](../2026-08-29-real-time-factor-conditions/ANALYSIS.md).

| | |
|---|---|
| Host | Apple **M4 Pro** (`Mac16,8`), 12 cores, 24 GiB, macOS **26.5.2** (Darwin 25.5.0, build 25F84) |
| Container | Docker Desktop, Linux VM, `overlayfs`; the CPU and memory allocation is recorded per block from inside the container rather than claimed here |
| Isolation | `COMPOSE_PROJECT_NAME` and `ROS_DOMAIN_ID` derived from this checkout by `scripts/_lib.sh`; own build/install/log volumes. The exact values are recorded in `raw/provenance.txt` |
| Free disk | 47 GiB available on `/` at the time this file was written |
| Environment | `./scripts/doctor`, `./scripts/build` and `./scripts/test` run clean on this branch before the first trial, and their summary lines are recorded in `raw/provenance.txt` |

**Host load before the first trial, recorded rather than claimed.** The load averages read
**2.70 / 2.94 / 4.70** on 12 cores at the time this file was written, on a host up 9 days with
unrelated containers and applications running. **This host is not quiet and could not be made
quiet.** Two previous campaigns found the same and said so before taking data; so does this one.

**What that does and does not threaten, argued rather than asserted.** Every width quantity here
is a function of simulation state sampled in simulation time — the drive joint's own position,
the contact sensor's stamps, and widths derived from a static linkage. None is a wall-clock
quantity. Host load moves how long a trial takes; it does not move where a joint stops. The one
route to the physics is a missed real-time deadline changing the interleaving of controller
updates with physics steps, which is why the load average is recorded per block and why V6
exists. **Arm B has no physics at all.**

**No real-time-factor claim is made from this campaign** (§1).

---

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — the code that actually ran.** Every block records `git rev-parse HEAD`,
  `git status --porcelain` and the `MODEL_HASH` of the running cell. **The quantity that must not
  move is the code under test, not `HEAD`**: this campaign's own `criteria.md`, harness and raw
  all land on the same branch, so `HEAD` necessarily advances while the campaign runs, and pinning
  it would discard every block including the first. A block is **discarded, not relabelled**, and
  the discard reported, if `git diff d3eeac4..HEAD -- model/ workspace/src/ tools/` is **non-empty**
  or the worktree is dirty in any of those three paths. In other words: `docs/measurements/` may
  advance, and nothing else may. **A merge, rebase or force-push of the branch during the campaign
  invalidates the campaign** (§0).
- **V2 — the geometry that actually ran.** Every block that brings the cell up reads the
  description the **running cell** publishes and counts collision-mesh references under
  `cite_description`: **13** for `convex_hull`. A block that disagrees is discarded and reported.
- **V3 — the part was, or was not, between the pads.**
  - Arms **C** and **D**: a trial contributes only if I4 reports **at least one finger contact
    point** in the window from first contact to the stall. Without it, "a real grasp reported
    empty" would be asserted rather than measured.
  - Arms **A** and **B**: a trial contributes only if I4 reports **no contact at all** and, for
    Arm A, **no work-piece exists in the world**. A trial that finds one is discarded: it is not
    a free-air trial.
- **V4 — the two width instruments agree.** Per trial,
  `|w_reached(I1) - w_reached(I3)| <= 0.100 mm`, and both round to the I2 log line's `%.1f`.
  A trial exceeding it is **excluded from the distribution and reported**: at that point the
  campaign does not know which value the predicate consumed.
- **V5 — the stop engaged, and the fixture did not manufacture it.** An Arm B trial contributes
  only if I7 shows the plugin's own stop warning **and** the drive joint rests at the declared
  stop within 0.001 rad **and** I8 shows no start-outside-the-stops refusal. If **every** Arm B
  trial is excluded, rule N-B fires.
- **V6 — the block effect.** Two blocks wherever the cell is brought up. If, for a metric, the
  difference between the two blocks at the **same** condition is larger than the largest
  difference **between** conditions, that metric's finding is **downgraded to INCONCLUSIVE**
  whatever any test statistic says. This is the rule that fired on the 2026-09-01 campaign's D2
  and it is inherited deliberately.
- **V7 — the rig is not the production backend, and knows it.** Every Arm B launch asserts that
  the description it substitutes into declared `gz_ros2_control/GazeboSimSystem` **before**
  substitution, exactly as `test_abort_classification_launch.py` does. A launch that finds
  anything else is discarded: the L0 backend has changed and the rig is no longer substituting
  what it thinks it is. **Arm A may not be run on any mock backend** (§5.1); a block that finds
  one is discarded, not reinterpreted.
- **V8 — n is what it was.** Every count is reported over the trials that actually ran, with a
  Wilson 95 % interval where it is a proportion, and **no condition is topped up** to match
  another.
- **V9 — no threshold moves.** Nothing in this file changes once the first campaign trial has
  run. **A threshold discovered to be wrong is applied literally and recorded as wrong**, and the
  disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data already collected.
  The 2026-08-31 capacity campaign applied a validity rule it had found to be reading the wrong
  quantity, literally, and reported it; that is the precedent.
- **V10 — the superseded predicate is a build, not a rewrite.** `holding_S` contributes only if
  `raw/provenance.txt` records the `4ef2d7c` worktree commit and the sha256 of the binary that
  produced it. A trial without that provenance reports `holding_F` alone.

**One shakedown run per harness is permitted and is not data.** Before the first campaign trial,
each harness may be run **once** to prove it starts, connects and writes a record. Its output is
published under **`raw/shakedown/`**, is **excluded from every figure in §7**, and **may not be
used to set or adjust any threshold in this file** — every threshold above is derived from the
geometry and the declared tolerances, and none of them needs a shakedown to exist. If the
shakedown reveals a defect, **the harness is fixed and this file is not touched.**

---

## 11. Honesty bounds fixed in advance

- **This campaign chooses nothing.** It does not set the band, does not amend ADR-0052, does not
  decide whether the monotonicity term returns, and does not decide whether the branch merges.
  Those are the project owner's. §0.
- **It measures an unmerged branch**, `feat/grasp-predicate-against-the-part` at `d3eeac4`, and a
  merge before it completes invalidates it. §0, V1.
- **A null is not a pass.** Rules N-A, N-B, M, R-A, S-C, W and T exist for exactly that, and all
  seven were written before any trial ran. **Rule W is the one that matters most**: the wide edge
  has never been exercised by anything, and a campaign that does not reach it must say so rather
  than let its silence read as a clearance.
- **The arms are not each other's evidence.** Rule T. Four regions are measured because four
  regions are open, and a clean result in one is not a result about another.
- **This is one machine, one part, one arm, one timestep, one facility with one declared part
  width, and it is not a rate.**
- **The 2026-09-01 campaign stays frozen.** Nothing in that directory is edited, re-run or
  re-analysed here, and its figures are cited rather than copied (P1).
- **Figures stay in this directory.** Nothing here is copied into ADR-0052, `CLAUDE.md`, the L0
  comments or any layer document (P1). Cite the directory.
