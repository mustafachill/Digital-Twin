# Criteria — is the grasp twist caused by the grasp-plane offset?

**Written before any trial of this campaign ran.** Recorded here so that the thresholds can
be seen to have preceded the numbers (P8). Nothing in this file may be edited once the
first trial has run; disagreements with it are recorded in `results.md` as deviations, with
the reason.

- **Date opened:** 2026-08-25
- **Branch / commit under measurement:** `feature/phase-1` at `a9d3559`, main checkout
- **Predecessor:** [`../2026-08-25-friction-grasp/`](../2026-08-25-friction-grasp/), 84
  trials. Read its `criteria.md` and `results.md` first. This campaign reuses that
  campaign's harness unchanged and reports the same statistics, so that the two sets are
  directly comparable.

## The question

The friction-grasp campaign established that a friction grasp in `cell_a` is repeatable
**in position** (68/68 carried and placed) and **not in orientation**: the work-piece
rotates between the jaws by up to **34.3°**, with median twist scaling by a factor of
**24.5** across a 4× timestep range (0.71° at `max_step_size` 0.002, 9.60° at 0.001,
17.43° at 0.0005). It attributed the mode to torsional friction and left the cause open.

**The hypothesis under test: the twist is produced by the grasp-plane offset, not by
friction.** The pads engage the part entirely above its centre of mass, which is a couple,
and a couple rotates things.

## The offset, and where every number in it comes from

Restated here rather than taken on trust, because it is the independent variable. Each
constant is a fact in a file that can be re-checked; `harness/geometry.py` computes the
rest and prints it.

| Fact | Value | Source |
|---|---|---|
| `link_tcp` above `xarm_gripper_base_link` | 0.172 m | `xarm_gripper.urdf.xacro`, `joint_tcp` |
| `drive_joint` pivot | (0, 0.035, 0.059098), axis +x | same file |
| `left_finger_joint` offset | (0, 0.035465, 0.042039), axis −x, mimic ×1 | same file |
| pad face | the `y = −0.026003` plane of `left_finger.stl`, z 0.022253 – 0.059753 | mesh, parsed |
| pad face height | **37.500 mm** | that z span |
| pad face centre, in the finger frame | z = 0.041003 | that z span |
| fingertip plane, in the finger frame | z = 0.061003 | mesh z-max |

The two mimic rotations cancel, so the pad face stays parallel to the tool axis and only
its origin translates. That gives the L0 model's own `opening(q)` unchanged, and the axial
offset this campaign is about:

```
offset(q) = 0.172 − (0.059098 + 0.035465·sin q + 0.042039·cos q) − 0.041003
          = 0.0718988 − (0.035465·sin q + 0.042039·cos q)
```

— how far **proximal of `link_tcp`** the centre of the pad face sits. `link_tcp` is the
fingertip plane to within 0.8 mm, not the pad centre. Values: **29.86 mm** fully open,
**19.23 mm** at `q = 0.4085`, which is the median drive angle at which the gripper stalls
on the cell's 50 mm reference part over the 32 published trials at `max_step_size` 0.001
and 0.0005.

`PickAt` (`skill_nodes.hpp:259,301`) then adds a further **+5.00 mm** by writing
`grasp_height_m = 0.030` against a part whose centre of mass is at 0.025. The published
harness restates the same 0.030 as `GRASP_HEIGHT_M`, so the published trials carry the
same total.

**Total, as shipped: +24.23 mm** of pad-centre above the part's centre of mass, leaving
**19.5 mm of the 37.5 mm pad face** engaged, all of it above the centre of mass, with the
engaged strip's centroid **15.2 mm** above it.

**This is confirmed against the published raw data before any new trial is run**, which is
the point of stating it here: `harness/engagement.py`, run over the published
`step0p001` traces, reads the pad-face centre out of the simulator's own pose feed at the
grasp instant and measures **+24.41 mm** against the +24.24 mm the formula predicts, with
**19.3 mm** of pad face engaged. The geometry above is therefore not a model of the cell;
it is a description of it, agreeing to 0.2 mm.

## What is varied, and what is held fixed

**The single lever: `object_pose.pose.position.z` in the `Pick` goal** — where the skill is
told to put `link_tcp`, and hence where the pad face lands on the part. It is a *geometry*
change, made through the harness's commanded height. **No production code is edited to
make it**, so `PickAt`, the skill server and the L0 model are the shipped ones in every
block.

| Block | commanded height | pad centre vs part COM | pad face engaged |
|---|---|---|---|
| **`uncorrected`** | 0.0300 m (as shipped) | +24.23 mm | 19.5 of 37.5 mm, all above the COM |
| **`corrected`** | 0.0058 m | +0.03 mm | 37.5 of 37.5 mm, symmetric about the COM |
| **`half`** (run only if the host affords it) | 0.0250 m | +19.23 mm | 24.5 of 37.5 mm |

`half` removes only `PickAt`'s hand-written +5 mm and leaves the structural offset. It is
a dose-response point, not part of the core comparison, and is run last so that dropping it
costs nothing.

Held fixed unless named as a variable — every one of these identical to the published
campaign, so that its numbers are the comparison:

| Quantity | Value | Where it comes from |
|---|---|---|
| Cell | `cell_a`, all three arms, `cite_bringup/launch/simulation.launch.py` headless | **not** a reduced one-arm rig, deliberately |
| Work-piece | 50 mm cube, 0.2 kg, `mu = mu2 = 1.0`, contact sensor present | published harness, unchanged |
| Plugin | loads, and never fires — the part is spawned under a name not in `<graspable>` | published harness, unchanged |
| Commanded grasp width | 0.045 m | `default_grasp_width_m`, L0 |
| `max_effort` | 60.0 N | L0 |
| `stall_velocity_threshold` | **0.05** rad/s, as shipped at `a9d3559` | L0 — see below |
| `stall_timeout` / `goal_tolerance` | 0.3 s / 0.01 rad | L0 |
| approach / retreat / release | 0.10 / 0.12 / 0.04 m | published harness, unchanged |
| `max_step_size` | 0.001 s, and **0.0005 s** in the second pair of blocks | `STEP_SIZE_S`, world generator |

**On the earlier attempt at this question.** One agent previously corrected the height and
reported "outcome unchanged" while `stall_velocity_threshold` was at the shipped-at-the-time
0.001, which is 25× below the drive joint's contact creep and makes the gripper action
hang rather than answer — neither of `GripperActionController`'s two terminating branches
can fire. That trial could not report an outcome either way. It is treated here as void,
not as evidence. The threshold is 0.05 in the tree at `a9d3559`, so **this campaign needs
no deviation from the shipped configuration at the shipped timestep.**

**Declared deviation, second pair of blocks only.** `max_step_size` is `STEP_SIZE_S` in
`tools/cite_tools/generate/world.py`. Changing it to 0.0005 is a temporary local edit
applied at the generator and regenerated with `./scripts/validate-model --write`, never by
hand-editing a generated artifact, and reverted afterwards. It is the same lever the
published campaign used for its T3 blocks.

## Per-trial measurements

Every metric is the published campaign's, computed by its `harness/recompute.py` over the
saved pose traces, so the two campaigns' numbers mean the same thing. `twist_max_deg`,
`slip_max_mm`, `slip_rate_mm_per_s`, `place_err_at_release_m`, `carry_duration_s`,
`pad_separation_mm_mean`, `pad_dist_drift_mm`, `v_max_carry_mps`, `lift_m`,
`q_at_stall_rad`.

Two are added by this campaign, both of them measurements of the independent variable
rather than of the outcome, and both read from the simulator's own pose feed at the grasp
instant (`harness/engagement.py`):

| Symbol | Definition |
|---|---|
| `pad_offset_vs_com_mm` | world z of the pad-face centre minus world z of the work-piece's centre of mass |
| `pad_face_engaged_mm` | the part of the 37.5 mm pad face that overlaps the part's 50 mm height |
| `finger_tip_above_surface_mm` | fingertip plane above the pick surface — table clearance |

## Thresholds — the decision rule

Stated as pass/fail *before* the numbers, so that the conclusion is read off rather than
argued to. `N` is decided by what the host affords and is **reported as the number it
actually was**; a block counts only at `n ≥ 10` at `max_step_size = 0.001` and `n ≥ 8` at
0.0005.

**G — the block is a valid comparison at all.** Checked first, and a block failing any
part of it is reported as *not a comparison* rather than as a result. This exists because
the cheapest way to make a twist disappear is to fail to grasp the part, and a control that
could not have fired is not a control.

- `pick_reported_holding` in **every** trial, and `Pick` returns SUCCESS in every trial.
- Median `q_at_stall_rad` within **0.02 rad** of the `uncorrected` block's median at the
  same timestep. The part is the same width in every block, so the drive joint must stop
  at the same angle; a different angle means a different grip, not a different height.
- Mean `pad_separation_mm` within **2 mm** across blocks.
- `lift_m > 0.05` in every trial, and median `carry_duration_s` within **15%** across
  blocks. A part that had less time to move has not been shown to twist less.
- `finger_tip_above_surface_mm > 2.0` in every trial. A fingertip that reaches the table
  adds a contact the block did not intend.
- Measured `pad_offset_vs_com_mm` within **3 mm** of the block's design value. A block that
  did not move the independent variable cannot answer the question.

**H1 — does correcting the offset remove the twist, at the shipped timestep?** Comparing
`corrected` against `uncorrected` at `max_step_size = 0.001`:

- **Removed** if median `twist_max_deg` in `corrected` is **≤ 20%** of the `uncorrected`
  median **and** the two samples do not overlap (max of `corrected` below min of
  `uncorrected`).
- **Reduced but not removed** if the median falls by more than half but the samples
  overlap.
- **Not the cause** if the median does not fall by more than half.

Reported alongside a two-sided permutation test on the difference of medians, 100 000
permutations, fixed seed, α = 0.01 — because with n of this size a rank test's p-value is
the only part of the comparison that is not eyeball.

**H2 — does the timestep scaling survive the correction?** This is the question that
decides what the answer is *for*, and it is pre-registered as a separate outcome rather
than folded into H1. For each condition let `R = median twist(0.0005) / median
twist(0.001)`. The published uncorrected value of `R` is 17.43 / 9.60 = **1.82**.

- **Scaling survives** if `R_corrected ≥ 0.5 × R_uncorrected`.
- **Scaling is removed** if `R_corrected < 0.5 × R_uncorrected`.
- **Floor** — if the `corrected` medians at *both* timesteps are below **1.0°**, `R` is not
  reported as a meaningful ratio. 1.0° is chosen because it is where the published
  `max_step_size = 0.002` block sits (median 0.71°, max 0.84°), which is the regime the
  published campaign already describes as a grasp that behaves rigidly.

**H3 — slip.** Correcting the offset is said to reduce slip if median `slip_max_mm` in
`corrected` is **≤ 50%** of `uncorrected` at the same timestep. `slip_rate_mm_per_s` is
reported for both; the published campaign found it positive in 76 of 76 trials, and whether
that survives is reported whichever way it falls.

**H4 — nothing else got worse.** `trial_success` as the published campaign defines it,
`place_err_at_release_m`, and `v_max_carry_mps` are reported for every block. A correction
that removes the twist by dropping the part is not a correction.

**H6 — which of the two mechanisms the height changes.** Registered now, before this
campaign's first trial, because it decides how the result should be *read* and because
deciding it after seeing the blocks would be choosing the explanation to fit them.

Moving the commanded height changes **two** things at once, and both would reduce twist:

- **the lever arm.** The engaged strip's centroid sits 15.2 mm above the centre of mass.
  Gravity alone produces no couple — the weight at the centre of mass and the friction
  force at the pads are collinear — but **every horizontal acceleration of the carry does**:
  a force `F` applied at height `h` above the centre of mass is a torque `F·h` about the
  pad-to-pad axis, which is precisely the axis the published campaign measured the rotation
  about, to `|cos| = 1.0000`. Correcting the height takes `h` from 15.2 mm to 0.03 mm.
- **the contact area.** The engaged pad face goes from 19.5 mm to 37.5 mm, so the torsional
  capacity resisting that torque roughly doubles.

The blocks cannot separate these, because the height sets both. This test can, and it runs
on data that already exists. Within a single block — one height, one lever arm, one
area — the only thing that varies between trials is the trajectory the unseeded OMPL
returned, and hence the horizontal accelerations the carry applies. So:

- **Predicted by the lever arm**, and by nothing in the area account: within the
  `uncorrected` block, `twist_max_deg` correlates with the horizontal acceleration of the
  carry — reported as Spearman `rho` against peak `|a|` and against `∫|a| dt`, both taken in
  the pad frame from the work-piece's own pose trace.
- Registered thresholds: `rho ≥ 0.5` supports the lever arm as the driving term;
  `rho ≤ 0.2` says the trajectory does not drive the twist and the area account is the
  better reading; anything between is reported as inconclusive.

Run over the published campaign's `step0p001` traces as well as this campaign's blocks.
**With respect to the published data this analysis is post-hoc** — that data and its
headline numbers were read before this paragraph was written — and it is labelled as such
wherever it is reported. With respect to this campaign's own blocks it is pre-registered,
which is the only sense in which any of the thresholds above are.

**H5 — dose-response,** if `half` runs. Median twist at pad offsets of +24.2 / +19.2 /
+0.03 mm, reported as three points and as a Spearman correlation across the pooled 0.001
trials. Stated in advance as a weak lever — the first two points differ by only 5 mm — and
so as corroboration only, never as the basis of the verdict.

## What each outcome means

| Outcome | Reading |
|---|---|
| H1 removed, H2 scaling removed | The offset explains the twist. L0 should declare where the pad plane sits relative to the planning tip link, flow it through the bring-up plan to L3, and `PickAt`'s hand-written `grasp_height_m` should be deleted. |
| H1 removed, H2 scaling survives | **A different and more important answer.** The offset sets the *magnitude* of the twist; the simulator's timestep sensitivity is a separate property that a geometry fix does not touch. Both are true and both must be reported, and the second transfers to Phase 2 as a known sim/real divergence. |
| H1 reduced but not removed | The offset is a contributor, not the cause. Report the fraction it accounts for; the remainder is the simulator's. |
| H1 not the cause | The twist is a limit of this simulator. It transfers to Phase 2 as a known sim/real divergence rather than something to keep chasing. |

**The offset is worth correcting on mechanical grounds regardless of this result** — a
gripper engaging half its pad face above the centre of mass is wrong whatever the twist
does — so a null result here costs nothing and is recorded as plainly as a positive one.

## Honesty bounds fixed in advance

- This measures the **simulator**, not the cell. Nothing here evidences that a friction
  grasp is mechanically sound on the physical xArm, and nothing here evidences that it is
  not. The layout is `PROVISIONAL` and the physical scan is Phase 3.
- Planning is unseeded (ADR-0006) and `CITE_PHYSICS_SEED` reaches nothing (ADR-0027), so
  trials are **not** replicates under a fixed seed. They are independent samples from the
  same configuration, and every rate is a rate over samples, never a determinism claim.
- Every pose is read from Gazebo's own pose feed, never from TF. TF would report the
  pad through forward kinematics on the commanded joint state, which is a software servo's
  opinion of where the finger is; the question is where it actually is. This is the
  published harness's design and is kept.
- The corrected block commands a grasp with **5 mm** of fingertip clearance above the pick
  surface. That is deliberate and it is measured per trial (`finger_tip_above_surface_mm`),
  not assumed.
- Real-time factor on this host is ~0.14. Wall-clock ceilings are not results.
