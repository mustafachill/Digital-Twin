# Results — is a friction grasp in cell_a repeatable enough to build a scenario on?

Read [`criteria.md`](criteria.md) first. It was written and saved before the first trial
ran and states every threshold used below.

- **Date:** 2026-08-25
- **Branch / commit:** `feature/phase-1` at `dc68ab8`, main checkout
- **Isolation:** `COMPOSE_PROJECT_NAME=cite-meas-friction`, `ROS_DOMAIN_ID=77`, own build
  and install volumes, built from scratch (19 packages).
- **Environment check:** `./scripts/doctor` — 21 passed, 0 failed, 2 skipped (`ros 2`
  native, expected on macOS). Both declared patches verified **present** in
  `workspace/src/external/xarm_ros2`: `01-xarm_ros2-gripper-mimic-joints.patch` and
  `02-xarm_ros2-gripper-drive-rate-parameter.patch`.
- **Rig:** the full cell — `cell_a`, all three arms, nine controllers, three `move_group`s,
  brought up by the shipped `cite_bringup/launch/simulation.launch.py` headless. Not a
  reduced one-arm rig.
- **84 trials** across 8 blocks. Raw per-sample poses in `raw/`, consolidated metrics in
  `raw/all_trials_recomputed.csv`, harness in `harness/`.

## Headline

| Block | max_step_size | plugin | mu | n | Pick reported holding | cycle completed | twist median | twist max | slip median | slip max |
|---|---|---|---|---|---|---|---|---|---|---|
| `step0p0005` | 0.0005 | blind | 1.0 | 12 | 12/12 | 12/12 | **17.43°** | 34.26° | 9.12 mm | 16.88 mm |
| `step0p001` | **0.001 (shipped)** | blind | 1.0 | 20 | 20/20 | 20/20 | **9.60°** | 30.13° | 4.86 mm | 15.55 mm |
| `step0p002` | 0.002 | blind | 1.0 | 12 | 12/12 | 12/12 | **0.71°** | 0.84° | 2.06 mm | 2.71 mm |
| `plugin_off` | 0.001 | blind | 1.0 | 8 | 8/8 | 8/8 | 27.82° | 29.74° | 14.45 mm | 15.38 mm |
| `plugin_on` | 0.001 | **fires** | 1.0 | 8 | **0/8** | **0/8** | 0.16° | 0.21° | 0.00 mm | 0.00 mm |
| `mu0p5` | 0.001 | blind | 0.5 | 8 | 8/8 | 8/8 | 29.76° | 31.04° | 15.39 mm | 16.10 mm |
| `mu2p0` | 0.001 | blind | 2.0 | 8 | 8/8 | 8/8 | 23.90° | 30.41° | 12.37 mm | 15.72 mm |
| `plugin_control` | 0.001 | blind* | 1.0 | 8 | 8/8 | 8/8 | 5.16° | 29.74° | 3.22 mm | 15.41 mm |

\* `plugin_control` was *intended* as the plugin-on control and is not one: the work-piece
was spawned without a `<sensor type="contact">`, and `GraspAttachment::FindGraspable`
iterates `ContactSensorData` in the world. No pad link carries a sensor, so with none on
the work-piece there is no contact data anywhere and the plugin cannot fire whatever the
model is called. The block is kept as eight further friction trials and superseded as a
control by `plugin_on`, which spawns the sensor and in which the plugin demonstrably fires
(8 `attached 'workpiece'` transitions in `raw/logs/plugin_on_sim.log`).

## Verdicts against the pre-registered thresholds

**T1 — repetition at the shipped timestep: PASS.** 28 friction trials at
`max_step_size = 0.001` (`step0p001` + `plugin_off`): `trial_success` 28/28. Wilson 95%
lower bound on the rate **0.879**. Across every friction configuration tested — three
timesteps and three friction coefficients — 68/68. The gripper stalls on the part every
time, at `q = 0.406–0.418` rad, reporting `commanded 45.0 mm, reached 48.7–49.8 mm,
stalled=true, reached_goal=false -> holding`, which is what the L0 model predicts (contact
at opening 50.00 mm, `q = 0.4056`). n is 28 at the shipped timestep and 68 overall; that is
the number, and it is a rate over samples, not a determinism claim.

**T2 — slip: FAIL, on both halves.** `slip_max ≤ 5 mm` was required in every trial. At the
shipped timestep it is exceeded in **16 of 28** trials, reaching 15.55 mm. `slip_rate` is
positive in **76 of 76** friction trials (median 0.46 mm/s, worst 1.4 mm/s): the
displacement grows monotonically through the carry and stops only when the arm stops, so
the carry being 12 s rather than 60 s is the only reason the number is not larger.

The measurement also found a mode the criteria did not name, and it dominates. The
work-piece **rotates between the jaws** — up to **34.3°** — about an axis that is the
pad-to-pad axis to within `|cos| = 1.0000`, while the pads themselves turn 0.14° and the
drive joint creeps 0.005 rad. It is a torsional friction failure: the two gripped faces
stay in contact and the part spins between them. Verified three independent ways, because
a pad-frame figure could have been an artefact of a rotating reference:

- rotation-invariant pad-to-part distance grows 6.0 mm, symmetrically for both pads;
- pad separation holds at 101.7 mm ± 0.5 mm throughout (the jaws do not open);
- the drive joint holds 0.4065–0.4116 rad, so the finger link is not the thing moving.

**T3 — timestep sensitivity: UPHELD, decisively.** Median twist runs
**17.43° → 9.60° → 0.71°** across `max_step_size` 0.0005 → 0.001 → 0.002: a factor of
**24.5** over a 4× change in timestep. Median slip runs 9.12 → 4.86 → 2.06 mm, a factor of
4.4, against a pre-registered failure threshold of 2. Carry duration is 12.10 / 12.14 /
12.22 s across the three blocks, so the part has the same time to move in each and the
difference is the timestep, not the trajectory.

The direction is the one that matters and it is the unhelpful one: **the finer the
timestep, the worse the grasp.** Refining physics for fidelity makes this worse; coarsening
it for real-time factor makes the simulator flatter you. ADR-0028 and Phase 3 both point at
retuning physics for real-time factor, which is precisely the change ADR-0023 warned would
silently move Phase 1's results.

**T4 — flung: PASS. Nothing was ever flung, and nothing was ever dropped.** Maximum
work-piece speed during any carry is **0.279 m/s**; the part never falls below
`z_rest + 0.05` m between lift and release in any trial. This corrects an earlier reading
of the same data — see the deviations below.

**T5 — friction coefficient and solver iterations.**

- **The friction coefficient is not the controlling variable.** Median twist at
  `mu = 0.5 / 1.0 / 2.0` is 29.76° / 9.60° / 23.90° — non-monotonic, all inside one range,
  and a 4× change in `mu` moves nothing the way a 2× change in timestep does. A grasp that
  does not improve when the friction is doubled is not being limited by friction.
- **"The solver's iteration count" is not a parameter this stack has.** The DART engine
  plugin (`libgz-physics-dartsim-plugin.so`, gz-physics 7) exposes a solver *type*
  (`DantzigBoxedLcpSolver` / `PgsBoxedLcpSolver`) and a collision detector, and no
  iteration count. ADR-0023 names a knob that does not exist here. Solver *type* was not
  varied; the timestep result was already decisive and the record's claim about iterations
  is answered by its absence.

## The control: what the plugin actually does

The single-variable pair, at the shipped timestep, differing only in the spawned model's
name so that the plugin's `<graspable>` list matches in one case and not the other:

| | `plugin_off` | `plugin_on` |
|---|---|---|
| gripper report | `commanded 45.0 mm, reached 48.7–49.8 mm, stalled=true, reached_goal=false -> holding` | `commanded 45.0 mm, reached 46.0 mm, stalled=false, reached_goal=true -> empty` |
| `Pick` result | SUCCESS 8/8 | **EXECUTION_FAILED 8/8** |
| work-piece | carried and placed, 8/8 | **lifted 0.576 m anyway**, welded to a finger |

This independently reproduces the defect on which this measurement was commissioned, with
`stall_velocity_threshold = 0.05` in place: the plugin attaches at first pad contact, the
jaws then close *through* the part to 46 mm feeling nothing, `gripper_is_holding` correctly
reports an empty gripper, and `Pick` fails — while the weld carries the part away. **The
plugin as shipped does not deliver a grasp. It delivers a lift with a failed `Pick`.**

## What this means for ADR-0023

Per the decision table in `criteria.md` this is the **third answer**, and it is a stronger
form of it than that table anticipated.

- **ADR-0023's central objection is confirmed, and its wording needs correcting.** It
  predicted that friction grasping "fails by the object slowly sliding out or by being
  flung across the cell" and that success would be timestep-sensitive. Measured: the object
  is never flung and never dropped — 68/68 carries, max carry speed 0.279 m/s — and *grasp
  success* is **not** timestep-sensitive, holding 100% across a 4× range. What is
  timestep-sensitive by a factor of 24 is *grasp quality*: how far the part turns and
  slides between the jaws. The record is right about the mechanism and wrong about the
  symptom, which matters because the symptom it names is the one a scenario would notice
  and the one it does produce is the one a scenario would not.
- **Reversing ADR-0023 cannot be justified as "friction is repeatable".** It is repeatable
  in position — 68/68, placement median 0.4–9.0 mm from the target frame — and not in
  orientation. Within one configuration the twist ranges 1.4°–30.1°, set by which plan the
  unseeded OMPL happens to return (ADR-0006, ADR-0027). A cube placed on a belt does not
  care, which is why `./scripts/scenario pick_and_place` passes while this happens; the
  moment `Transfer` needs a known part orientation for a handoff (ADR-0024), it does.
- **Keeping ADR-0023 cannot be justified as "the plugin works" either.** It fails `Pick`
  0/8. Its trigger has to be reshaped whatever is decided about friction, and the cheap
  escape is already eliminated: `closed_threshold_rad` cannot be raised past the 3 mrad
  between contact (q = 0.406) and the settled stall (q ≈ 0.409), and the settled condition
  the record specifies needs pad contact sensors that do not exist in the generated
  description.
- **The one thing that is now certain is that the choice is not free either way**, and that
  the deciding question is what a scenario is allowed to assert. If a scenario may only
  assert *where* a part ended up, friction is good enough today and the plugin is not. If a
  scenario must assert *how* a part is held — which is what a continuous sensor-driven line
  and a two-party handoff require — neither mechanism is ready, and the twist number is the
  gap to close.

## Deviations from `criteria.md`, and why

Recorded rather than quietly applied. The raw samples in `raw/` are the record; these are
changes to the interpretation of them, applied by `harness/recompute.py` to data already
collected rather than by re-running until the definition suited.

1. **`held_through_transport` was defined by height and could not be evaluated that way.**
   The criterion required the work-piece never to fall back below `z_rest + 0.03` m between
   lift and release. The commanded descent onto the belt takes the part back to its spawn
   height *before* the release, so a height test cannot tell a correct place from a drop.
   Restated as a slip bound: the part is held to the release if it never moves more than
   25 mm — half its width — relative to the pad. Discovered on the smoke run, before any
   measurement block.
2. **`flung` was measured over the whole trial and was measuring something after the
   release.** Five of the first twenty trials tripped `v_max > 1 m/s`. All five did so
   *after* the release, at 3.3 m/s, ending at `z = 0.025` — a 50 mm cube resting on the
   ground plane. Read as flings, it would have reported friction grasping as 75% reliable
   for a reason with nothing to do with friction. `flung` is now evaluated over the carry
   window alone, and `place_err` is measured at the release rather than at the end of the
   recording. **Both re-definitions stand; the reason first given for them was wrong — see
   the correction below.**
3. **`twist_max_deg` was added after the smoke run**, which showed the part rotating tens of
   degrees between jaws that themselves barely moved — a mode the pre-registered
   translation metric reports as a few millimetres. Its 5° threshold was therefore chosen
   after seeing that mode exists, which is stated plainly here; the full distribution is
   reported so that the conclusion does not rest on where the line was drawn, and at
   0.3°–34.3° against the 0.48°–0.85° seen at `max_step_size = 0.002` it is not a
   marginal call.

## Correction, 2026-08-26 — what the parts on the floor actually were

Deviation 2 above, and the docstring of `harness/recompute.py`, explained the trials ending
at `z = 0.025` as "the belt carrying a correctly placed part off its far end". **That
explanation is wrong.** The parts left the belt at the **near** end, where they were set
down, and were carried nowhere.

The evidence is in this directory's own `raw/pose_samples.tar.gz`. This campaign placed at
`cell_a__conveyor_1__infeed`, which at the time sat at x = 0.450 — exactly the leading-edge
plane of the belt's collision box. In `mu2p0` trial 3 and `plugin_off` trial 6, the two
checked here, the work-piece leaves belt height at x = 0.395 and x = 0.402 and never
exceeds x = 0.451. The belt's far end is at x = 1.650. A part carried off the far end would
have travelled 1.2 m first; these travelled backwards off the edge they were released on.

`raw/all_trials_recomputed.csv` puts the scale at **22 of 84 trials** ending at
`final_z = 0.025`, against 52 ending at 0.625 on the belt.

What was really happening is the defect [ADR-0030](../../adr/0030-facility-model-describes-the-workpiece.md)
was written for: a 50 mm cube released on that plane has its centre of mass over the
*boundary* of its support polygon and is neutrally stable, so it tips about the edge and
falls 0.600 m. The frames have since moved 50 mm inboard and the model validator now
rejects the arrangement.

**What this changes, and what it does not.** Both re-definitions in deviation 2 remain
correct, and more clearly so: post-release behaviour is an artefact of the support, not of
the grasp, however the part left the belt. This campaign's conclusions are all drawn from
the **carry window** — slip, twist, stall, `pick_reported_holding` — and none of them
touches what happened after the release, so the headline results are unaffected. What was
wrong was the prose, and it was wrong in the direction that hides a defect: an anomaly
present in 22 of 84 trials was explained away as normal belt behaviour instead of
investigated, and the same defect then cost `./scripts/scenario pick_and_place` 18
consecutive runs before it was diagnosed from a different direction. This section exists
because a published campaign that is right about its question can still be wrong in its
margins, and the margins are where the next defect hides.

## Threats to validity, stated rather than assumed

- **This measures the simulator, not the cell.** ADR-0023's cost note applies in reverse:
  nothing here evidences that a friction grasp is mechanically sound on the physical xArm,
  and nothing here evidences that it is not. The layout is `PROVISIONAL` and the physical
  scan is Phase 3.
- **Trials are independent samples, not replicates.** `CITE_PHYSICS_SEED` reaches nothing
  (ADR-0027) and OMPL is unseeded (ADR-0006). Every rate above is a rate over samples.
- **Slip and twist are measured against the *left* pad.** The right pad tracks it — pad
  separation is constant to 0.5 mm — so the choice does not matter, but it is a choice.
- **The pose feed reports a top-level model in the world frame and a link in its own
  model's frame.** Every pad measurement is composed through `arm_1`'s constant model pose;
  without that composition the arm's own motion reads as slip, which is what the first
  uncorrected pass reported (1310 mm).
- **Blocks `step0p0005`, `step0p001`, `mu0p5`, `mu2p0` and `plugin_control` spawned the
  work-piece without a contact sensor.** The sensor is passive and changes no dynamics;
  `plugin_off` repeats the shipped-timestep friction condition *with* the sensor and agrees
  (8/8 holding, twist 0.27°–29.74°), so the friction results are unaffected.
- **One block was lost and retaken.** The first `max_step_size = 0.002` attempt started
  while the previous block's cell was still shutting down on the same `ROS_DOMAIN_ID`. Two
  cells, two `/clock` streams, `TF_OLD_DATA` floods and three segfaulting `move_group`s.
  The block was discarded and the runner now refuses to start while another `skill_server`
  is on the domain. No data from that attempt is in `raw/`.

## Reproducing

```
COMPOSE_PROJECT_NAME=<yours> ROS_DOMAIN_ID=<yours> ./scripts/enter dev \
  bash /workspace/docs/measurements/2026-08-25-friction-grasp/harness/run_block.sh <label> <n> [--graspable] [--mu M]
```

`stall_velocity_threshold` must be 0.05 (L0, `xarm_parallel_gripper.yaml`); the shipped
0.001 is below the drive joint's achievable creep and the gripper action hangs rather than
answering. `max_step_size` is `STEP_SIZE_S` in `tools/cite_tools/generate/world.py`;
changing it requires `./scripts/validate-model --write` and a rebuild of `cite_generated`.
Both were applied locally for this measurement and reverted afterwards.

## What is in this directory

| Path | What it is |
|---|---|
| `criteria.md` | thresholds, written before the first trial |
| `results.md` | this file |
| `raw/all_trials_recomputed.csv` | one row per trial, every metric quoted above |
| `raw/<block>_trials.json` | what the harness recorded live, per block |
| `raw/pose_samples.tar.gz` | **12 MB** — the per-sample pose traces every number is derived from, work-piece and both pads at the simulator's own publication rate |
| `raw/logs/<block>.evidence.txt` | the lines of each simulator log that carry evidence, de-duplicated; the full Gazebo output was discarded |
| `harness/measure_grasp.py` | the trial driver — spawn, `Pick`, carry, `Place`, record |
| `harness/recompute.py` | metrics, recomputed from the saved traces; the deviations above live here |
| `harness/run_block.sh` | brings the cell up, runs a block, tears it down |
| `harness/inspect_slip.py`, `invariant_check.py`, `axis_check.py`, `summarise.py`, `velocity_profile.py` | the checks that established the twist is real and the flings were not |

`pose_samples.tar.gz` is the only large item. It is the evidence for every figure here, so
it should not simply be deleted; whether it belongs in git or in `assets/manifest.yaml`
behind `./scripts/fetch-assets` is a call for whoever commits this.
