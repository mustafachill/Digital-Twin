# ADR-0036: Detect a mistracked trajectory at execution, with tolerances declared in L0

- **Status:** Proposed, corrected 2026-08-27. The decision stands in full — all four
  values ship, from L0, identically on both backends. Three supporting claims do not:
  that `stopped_velocity_tolerance` is armed on this cell and that `goal_time` arms it,
  that the tolerances are the vendor's for this controller configuration, and that the
  path tolerance's margin was established. See the section
  "Correction — 2026-08-27" immediately below.
- **Date:** 2026-08-27
- **Deciders:** Coder agent, on a finding raised by `safety-auditor` while auditing ADR-0027
- **Related:** [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0027](0027-pilz-planning-pipeline.md),
  [cross-cutting-safety.md](../architecture/cross-cutting-safety.md),
  charter §3.2 and §4 (P1, P2, P5, P7)

## Correction — 2026-08-27: `stopped_velocity_tolerance` cannot fire on this cell, the vendor block is transplanted across a configuration difference, and the path-tolerance margin was asserted rather than derived

Three supporting claims below are wrong or unsupported. **The decision itself stands
unchanged.** All four values still ship, still declared in L0, still identically on both
backends; the schema still requires `goal_time_s` and `goal_tolerance_rad` to be strictly
positive, and that requirement is still load-bearing for the reason the "interaction"
section gives. Nothing that is generated changes. What changes is what this record says
about why.

**1. `stopped_velocity_tolerance` is not "the one goal-side check that is live today", and
setting `goal_time` does not arm it.** The section
"`stopped_velocity_tolerance` is already armed, and enabling `goal_time` arms it" is right
that `get_segment_tolerances` assigns `goal_state_tolerance[i].velocity` unconditionally
from a parameter that upstream defaults to `0.01` rather than to zero. It is wrong that the
check can therefore fire. `JointTrajectoryController::compute_error_for_joint` writes the
velocity error only under

```cpp
  if (
    has_velocity_state_interface_ &&
    (has_velocity_command_interface_ || has_effort_command_interface_))
  {
    error.velocities[index] = desired.velocities[index] - current.velocities[index];
  }
```

— `joint_trajectory_controller` 4.40.1, the version installed in the container image. Every
generated arm configuration in this cell declares `command_interfaces: [position]` and
nothing else, so both disjuncts of the inner condition are false.
`state_error_.velocities` is sized to `dof_` by `resize_joint_trajectory_point` and is never
written after that, so the number `check_state_tolerance_per_joint` reads is always `0.0`
and `abs(0.0) > tolerance` is false for every tolerance. **The velocity check is
structurally dead on this cell, whatever `goal_time` is.** Enabling `goal_time` cannot arm
it, and it would not have introduced a velocity-driven flake.

Emitting the vendor's explicit `0.0` is still the right call, for a reason the original text
did not give: it costs nothing, and it pre-empts the one change that would arm the check for
the first time. **Adding a `velocity` or an `effort` *command* interface to this arm is what
would arm `stopped_velocity_tolerance`** — nothing else does. That is not a hypothetical:
the vendor's own configuration, quoted in Option D, commands position *and* velocity, so
moving this arm onto the vendor's interface set is a plausible change and it would make this
parameter live on the first run after it.

**2. "The vendor's numbers for the vendor's arm" is true of the arm and not quite of the
controller configuration.** `xarm_controller/config/xarm5_controllers.yaml` at the pinned
commit declares `command_interfaces: [position, velocity]`. The generated configuration here
declares `command_interfaces: [position]`. The tolerances were written for a controller that
commands both, and they are being applied to one that commands position alone — the same
arm, a different control mode. That does not invalidate the values: they bound *position*
error, which both configurations track. It does mean the provenance is one step weaker than
"the vendor's configuration for the vendor's arm", and correction 1 is the concrete
consequence — the one number the vendor set with a live check behind it is the one that has
no check behind it here.

**3. "Loose enough that it cannot plausibly be the thing that fires on a healthy run" was an
assertion with no arithmetic behind it.** The conclusion holds. The margin is roughly 14×,
and it is worth writing down because the "revisit" section below asks for an observed peak
"at least an order of magnitude below `trajectory_tolerance_rad`" and gives a reader nothing
to compare against.

Derived rather than measured, and only for the simulated backend. Under `gz_ros2_control`
the position command interface is not a position servo: `GazeboSimSystem::write()` computes
`error = (position - command) * update_rate` and issues
`target_vel = -position_proportional_gain * error`, with the gain defaulting to `0.1` and
this cell overriding nothing. With the model's `update_rate_hz: 150` that is a first-order
lag of time constant `1 / (0.1 * 150) = 67 ms`. Tracking a constant-velocity segment, such a
lag settles at a following error of `v * tau`. The fastest segment this cell can plan is the
description's `velocity="3.14"` scaled by `default_velocity_scaling_factor: 0.35`, so
`v = 1.10 rad/s` and the steady-state following error is about **73 mrad** — against a
`trajectory_tolerance_rad` of `1.0`, a margin of about **14×**.

Three things about that number, in the order they matter:

- **It is simulation-only.** The 67 ms lag is a property of `gz_ros2_control`'s command
  conversion, not of the arm. On hardware the plant is UFACTORY's own servo loop and this
  arithmetic says nothing about it. The tolerance is still identical on both backends, which
  is P2 and is not negotiable; what differs is that only one backend's healthy following
  error has been estimated here, and neither has been measured.
- **Pure transport delay is a much smaller term and is not the one to quote.** One control
  period at `v = 1.10 rad/s` is `1.10 / 150 = 7.3 mrad`. The lag above dominates it by an
  order of magnitude, so a margin computed from the control period alone would be optimistic
  by that factor.
- **All of it is in simulation time.** `gz_ros2_control` calls the controller manager at the
  configured 150 Hz *in simulation time*; a real-time factor below 1 stretches wall-clock
  and leaves every quantity above unchanged. Do not compute this margin from the ~21 Hz
  wall-clock `joint_states` rate recorded in ADR-0028: mixing a wall-clock rate into a
  simulation-time error is the failure class CLAUDE.md §10 names under "Time", and it
  produces a plausible, wrong answer.

This estimate does **not** discharge the campaign in "What we will have to revisit". It is
what the first measurement should be checked against, not a substitute for taking it.

**How these errors survived.** All three share one shape: a fact was read off the code that
*sets* a value and never traced to the code that *reads* it. The
`stopped_velocity_tolerance` claim was verified as far as `get_segment_tolerances`, which
assigns the tolerance unconditionally — and stopped there, one call short of
`compute_error_for_joint`, which decides whether there is ever an error to compare it
against. The provenance claim compared the vendor's `constraints:` block to ours and did not
read the six lines above it in the same file. The margin claim asserted a conclusion about
following error without once computing a following error. Nothing in the change could have
caught any of them: the launch test drives mock hardware, which mirrors commands to state,
so its following error is identically zero — it can prove the tolerances are *read as two
numbers*, and it cannot prove anything about what a real one would be. A configuration
detector whose only evidence comes from a backend that cannot produce the error it detects
is under-evidenced by construction, and that is the transferable part.

## Amendment — 2026-09-04: the healthy-run half of the "revisit" campaign has been taken, and the path tolerance is not structurally silent under `gz_ros2_control`

**This is an amendment and not a correction.** Nothing in this record or in the 2026-08-27
correction above was measured false, and neither is rewritten. **The status line does not move,
this record is not promoted, and the detector is not validated on either backend.** What this
section adds is that one half of the measurement the "What we will have to revisit" section asks
for now exists, published as
[`docs/measurements/2026-09-04-following-error/`](../measurements/2026-09-04-following-error/ANALYSIS.md)
— thresholds registered before the first trial, machine named, run against the shipped cell with
`gz_ros2_control/GazeboSimSystem` asserted off the description the running node published.
**Cite the directory. No figure from it is copied here except the one comparison this record's
own line makes** (P1).

### What was measured

- **The healthy-run half of [`docs/open-work.md`](../open-work.md) #20 is answered.** The
  campaign sampled the controller's own `controller_state` on a real Gazebo-backed arm across
  four conditions and three bring-ups, with a registered admissibility rule that refuses a
  silence produced by an instrument that received nothing. Every condition was admissible with
  no instrument losses, so **its quiet is a measured quiet and not an empty subscription** —
  which is the one thing the launch test in this record could never have shown, for the reason
  its own "How these errors survived" paragraph gives.
- **The path tolerance is not structurally silent under this backend. It fired.** Two trials, on
  the concurrently loaded condition, both aborting as `PATH_TOLERANCE_VIOLATED`, both attributed
  by the campaign's own instrument to **the arm under test's own controller** rather than to a
  load arm and rather than by its conservative fallback. Two events across three bring-ups, not
  one per bring-up: the third produced none at the same schedule slot. **These are counts, not
  causes** — the campaign attributes neither the firings nor their absence, and neither is a
  rate.
- **The derivation this record's 2026-08-27 correction item 3 offered is superseded by a
  corrected command law, and that law is now established rather than merely admitted.** The
  campaign's own arithmetic adds the controller's one-period lookahead to the plugin's
  first-order lag, and the measurement agrees with it on every trial but two, to five significant
  figures. **The two disagreements are the two firing trials, and the campaign attributes
  neither.**
- **The goal-side pair produced no information, exactly as the campaign registered in advance
  that it would not.** Every settle landed at or below one sample interval on every admissible
  healthy trial, and the campaign registered before its first trial that a clearance at that
  resolution evidences nothing about the goal tolerance. `stopped_velocity_tolerance` is
  recorded as NOT MEASURED, for the two structural reasons correction item 1 above already
  gives.

### The finding this record has to carry: at full velocity scaling the healthy peak is above this record's own line

The "revisit" section sets the criterion: *"If the observed peak is not at least an order of
magnitude below `trajectory_tolerance_rad`, the value is wrong and the margin is the finding."*
Against the shipped `trajectory_tolerance_rad` of `1.0` rad that line is **0.100 rad**, and this
comparison is quoted here because the line is this record's own.

**At full velocity and acceleration scaling the campaign's healthy peak is 0.115972442 rad —
above 0.100 rad, by 15.97 %.** The campaign registered that outcome as its uncomfortable
prediction before any trial, and it landed. **The margin is the finding, in this record's own
words.**

Three bounds on it, all of them the campaign's own and none of them softening it:

1. **Full scaling is outside the condition this record's sentence is scoped to.** The "revisit"
   bullet asks for a sample across `pick_and_place` and `continuous_line`, which run at the
   configured default scaling. The campaign's three default-scaled conditions all sit below the
   line, subject to item 2; the one that exceeds it is the full-scaling condition, which is the fastest
   motion the L3 contract permits and is not what those two scenarios run. **A peak above the
   line at full scaling does not make this record's sentence false and is not written here as
   though it did.**
2. **Every below-the-line verdict is a lower bound.** The controller compares its tolerance
   inside `update()` whether or not the state message is delivered, and the campaign measured a
   share of those compared states that never reached its recorder. So the peaks
   below the line are maxima over the samples that arrived and are weaker evidence than the one
   above it, which a delivered sample establishes outright.
3. **This is one backend.** The campaign's own rule scopes every figure to `gz_ros2_control`'s
   command conversion at this gain, this controller-manager rate and this world's step, and to
   nothing else. Nothing here is a statement about UFACTORY's servo loop, and the P2 asymmetry
   #20 names is not resolved in either direction.

### The firing half remains unmeasured, and the reason is structural

**Nothing here shows the detector can detect an obstruction under `gz_ros2_control`.** The two
firings were **not induced**: the campaign has no mechanism for making the tolerance fire and
registered that half as out of scope before its first trial. Making it fire needs a Gazebo-side
mechanism that obstructs an arm **link** while `gz_ros2_control` is still the loaded hardware
component, and the fixture that can hold a joint part-way cannot serve —
`cite_test_hardware::JointStopSystem` (ADR-0040) derives from `mock_components::GenericSystem`
and is therefore loaded **instead of** `gz_ros2_control/GazeboSimSystem`, not beside it, so a
description that names it has no Gazebo plugin driving its joints at all. A rig built on it
measures mock hardware again, which is the blind spot this record already names.

**Whether that half is worth building is undecided and is the project owner's**; it is not
proposed here.

### What this amendment does not do

- **The four values are still UFACTORY's, still recorded as copied and not measured.** Nothing
  in the campaign validates any of them, and **the campaign proposes no tolerance, no threshold
  and no ceiling** — its own §13 says so, and this record's own instruction stands: a tolerance
  is never widened to absorb a measurement.
- **It moves no status.** This record stays as its status line reads. The "revisit" section is
  **not** discharged: its scenario sample is untaken, since the campaign drives L3 directly and
  runs neither `pick_and_place` nor `continuous_line`, and the firing half is untouched.
- **It is still a detector and not a protective measure**, and the "What this costs us" bullet
  saying so is unchanged by anything measured.

## Context

The generated `JointTrajectoryController` configuration contains no `constraints:`
block. `joint_trajectory_controller` defaults `goal_time`, the per-joint `trajectory`
tolerance and the per-joint `goal` tolerance to `0.0`, and a `0.0` position tolerance
disables that check — `check_state_tolerance_per_joint` in `tolerances.hpp` skips any
variable whose tolerance is not `> 0.0`.

The consequence is that a trajectory which mistracks — because it clipped a conveyor,
because a joint stalled against a fixture, because the arm was never where the plan
assumed — runs to the end and reports `SUCCEEDED`. `execute_plan` in
`cite_skills/src/skill_server.cpp` maps that to `ResultCode::SUCCESS`, and `Pick`
reports success. **Nothing anywhere in this repository observes the difference.** No
scenario constraint fires either: `continuous_line`'s containment check bounds the
*work-piece*, not the arm, and its own comment already concedes that "a contact that
harmed nothing and was reported nowhere passes unnoticed".

This is not caused by ADR-0027, but ADR-0027 makes it acute. Pilz is a trajectory
generator rather than a search: it does not explore the scene, so the plan-time
collision check is a per-waypoint `ValidateSolution` pass and nothing more. With less
work being done at plan time, the absence of any check at execution time carries more
weight than it did under OMPL.

Three facts constrain the decision and are not up for debate.

1. **P2.** The simulated and physical cells must load the same controller
   configuration. A tolerance that differs by backend would be a parity break, not a
   tuning decision.
2. **P1/P5.** Tolerances are facts about an arm. They belong in the arm type in
   `model/`, alongside `update_rate_hz` and `max_acceleration_rad_s2`, not as
   constants in the generator.
3. **A blocking CI gate is at stake.** `./scripts/scenario pick_and_place` gates
   merges and `bringup` runs twice per CI run. A tolerance that fires on a healthy run
   under a loaded machine is a flake, and this project's history says a flake gets
   exempted rather than fixed. A detector that gets disabled has negative value: it
   costs the CI time and leaves the gap open.

### The interaction that shapes the decision

`goal_time` and the per-joint `goal` tolerance are **not independently shippable**,
and the naive reading — that the goal-side tolerances are the safe half and can go in
one at a time — is wrong in a way that matters.

From `joint_trajectory_controller.cpp` on `jazzy`, in `update()`:

```cpp
    outside_goal_tolerance = true;
    if (active_tol->goal_time_tolerance != 0.0)
    {
      if (time_difference > active_tol->goal_time_tolerance)
      {
        within_goal_time = false;
```

and the goal is aborted only in the `else if (!within_goal_time)` branch. So:

- **`goal` tolerance with `goal_time: 0.0`** — `within_goal_time` is never set false,
  the success branch is unreachable while the joint is outside tolerance, and the
  controller "runs another cycle" forever. The upstream parameter description says so
  outright: *"If set to zero, the controller will wait a potentially infinite amount
  of time."* That converts a false success into a **hang**, which is strictly worse:
  the caller observes a timeout in the layer above rather than an answer. This is the
  same failure shape ADR-0022 found in `GripperActionController`, where neither
  terminating branch could fire and the action simply never returned.
- **`goal_time` with a `goal` tolerance of `0.0`** — `outside_goal_tolerance` is never
  set from position at all, so the success branch is taken immediately and `goal_time`
  is dead configuration.

They ship together, both non-zero, or neither ships.

### `stopped_velocity_tolerance` is already armed, and enabling `goal_time` arms it
**[Corrected 2026-08-27 — see the Correction section above. Neither half of this heading
is true of this cell.]**

`get_segment_tolerances` assigns `goal_state_tolerance[i].velocity =
constraints.stopped_velocity_tolerance` unconditionally, and that parameter defaults
to `0.01` rad/s rather than to zero. It is therefore the **one** goal-side check that
is live today. It has been harmless only because `goal_time` is `0.0`: a joint still
creeping at the trajectory's end keeps the goal open rather than failing it, and in
practice the joints settle and the goal succeeds.
**[Corrected 2026-08-27 — see the Correction section above.]**

Setting `goal_time` to a finite value changes that. A joint that settles at
`t_end + 0.8 s` succeeds today and would abort at `t_end + 0.5 s`. Enabling
`goal_time` without also deciding this parameter would introduce a *velocity*-driven
flake while intending to add a *position* detector.
**[Corrected 2026-08-27 — see the Correction section above.]**

### What is measurable within this change, and what is not

The following error a healthy run produces is observable on
`.../controller_state`, but only under Gazebo — that is, only by running a scenario.
Mock hardware mirrors commands to state, so the following error there is identically
zero and measures nothing about the real system. This change was implemented under an
explicit instruction not to run scenarios (a concurrent measurement on the same
machine would be corrupted by the contention), so **no healthy-run following error was
measured for it.**

## Options considered

### Option A — Leave the tolerances disabled, and detect mistracking elsewhere
Add a scene-aware execution monitor, or assert arm containment in the scenarios the
way `continuous_line` asserts work-piece containment.

Genuinely plausible, and it is the only option that catches a *graze* — a contact that
perturbs nothing enough to accumulate joint error. Not chosen: it is a new node on the
execution path with no L0 home, it does not exist on the hardware backend at all
(so it would break P2's "same code commands both cells"), and it leaves the
zero-cost mechanism the controller already ships unused. The controller-side check is
strictly a subset of the work and available immediately.

### Option B — Ship all four constraint values, chosen from a measurement campaign
Sample `controller_state` across the healthy `pick_and_place` and `continuous_line`
runs, publish a campaign under `docs/measurements/`, and set each tolerance at a
stated margin above the observed peak.

This is the right long-run answer and it is what the "revisit" section below commits
to. Not chosen *now*: it requires running scenarios repeatedly, which this change was
explicitly forbidden from doing, and the campaign is a larger piece of work than the
configuration it would justify. Blocking a zero-to-one detector on it leaves the gap
open for the duration.

### Option C — Ship the goal-side pair only, and leave the path tolerance disabled
Set `goal_time` and the per-joint `goal` tolerance; emit no `trajectory` tolerance.

The conservative option, and the one the task that produced this ADR expected. The
goal-side checks fire after the trajectory has ended, where timing jitter is bounded
and a violation is unambiguous. Not chosen as the *whole* answer because it detects
only the endpoint: a trajectory that clips a conveyor mid-motion and then recovers to
the correct final pose is still reported as a clean success, which is the auditor's
originating case.

### Option D — Ship all four, taking the values from the vendor's own configuration
`xarm_controller/config/xarm5_controllers.yaml`, at the commit this project pins,
declares a `constraints:` block for this exact arm: `goal_time: 0.5`,
`stopped_velocity_tolerance: 0.0`, and `{trajectory: 1.0, goal: 0.01}` for every
joint. UFACTORY ships those as the working configuration for an xArm 5.

Chosen. The values have a real provenance — they are the arm vendor's numbers for the
arm vendor's arm, the same class of provenance the model already accepts for
`max_reach_m` — and the path tolerance in particular is loose enough (1.0 rad ≈ 57°)
that it cannot plausibly be the thing that fires on a healthy run.
**[Corrected 2026-08-27 — see the Correction section above. The vendor block quoted here
commands `[position, velocity]` where this cell commands `[position]`, and the margin
claim in the second half was an assertion with no arithmetic behind it. Both survive
correction; neither was established here.]**

## Decision

Generate a `constraints:` block for every `JointTrajectoryController` from four values
declared on the controller in the L0 arm type: `goal_time_s`,
`stopped_velocity_tolerance_rad_s`, `trajectory_tolerance_rad` and
`goal_tolerance_rad`. Seed them with UFACTORY's own values for the xArm 5 — `0.5`,
`0.0`, `1.0` and `0.01` — recorded in the model as **copied, not measured**, and
replace them with measured values when the campaign in "revisit" runs.

`trajectory_tolerance_rad` is nullable in the schema. `null` emits no per-joint
`trajectory` key and leaves the path check disabled, so an arm can decline the path
detector without declining the goal detector. `goal_time_s` and `goal_tolerance_rad`
are required and must both be `> 0.0`, because the analysis above shows that either
one alone is a defect rather than a partial feature.

## Consequences

### What this gets us

- A mistracked trajectory becomes `PATH_TOLERANCE_VIOLATED` or
  `GOAL_TOLERANCE_VIOLATED` at the controller, which MoveIt's `execute()` returns as a
  failure, which `execute_plan` already maps to `ResultCode::EXECUTION_FAILED`, which
  L4 can fault a station on. **No code changes on that path** — the plumbing was
  complete and the configuration was the missing half.
- The `goal_time`/`goal` hang described above is now unreachable by construction: the
  schema requires both to be positive, so the model cannot express the combination
  that never returns.
- `stopped_velocity_tolerance` becomes a stated decision instead of an unread default
  that would have been silently armed by enabling `goal_time`.
  **[Corrected 2026-08-27 — see the Correction section above. It becomes a stated
  decision, which is worth doing; nothing would have armed it. What would arm it is a
  `velocity` or `effort` command interface on this arm, and that is the change this
  explicit `0.0` pre-empts.]**
- Identical on both backends, from one generated file, so P2 holds by construction.

### What this costs us

- **The numbers are copied, not measured, and this ADR is the record of that.** They
  are the vendor's, they are not this stack's, and no healthy-run following error on
  Gazebo was observed before choosing them. If the vendor's path tolerance is tighter
  than a healthy Gazebo run needs, the cost lands on a blocking CI gate.
- **It is a detector, not a protective measure, and must never be described as one.**
  What stops an xArm driving into a fixture is the UFACTORY controller's torque
  limiting and physical guarding; a risk assessment and ISO 10218 are outside this
  repository (charter §3.2). This converts a silent success into a reported failure
  *after* the fact. It prevents nothing.
- **The path tolerance detects a stall, not a graze.** At 1.0 rad it fires when a joint
  is held back hard enough to accumulate 57° of position error. A contact that
  deflects the arm slightly and lets it continue stays invisible, exactly as it is
  today. Option A remains the only answer to that case.
- Every arm motion in the cell gains a new way to fail. That is the point, but it is a
  behaviour change to a path with no execution-side failure mode until now, and the
  first failures it produces may be pre-existing mistracking that was never reported
  rather than new regressions.
- The acceleration and deceleration ceilings remain enforced at planning only.
  `enforce_command_limits` builds its limiter from the URDF `<limit>` element, which
  carries position, velocity and effort and has **no** acceleration or deceleration
  field. This ADR does not close that gap, and the generated `joint_limits.yaml` is
  amended to keep saying so rather than to imply it was closed.

### What we will have to revisit

- **The first scenario run after this merges is the measurement.** Sample
  `/cite/cell_a/arm_N/arm_N_joint_trajectory_controller/controller_state` across
  `pick_and_place` and `continuous_line`, record the peak per-joint `error.positions`
  during motion and at `t_end + goal_time`, and publish it under
  `docs/measurements/`. If the observed peak is not at least an order of magnitude
  below `trajectory_tolerance_rad`, the value is wrong and the margin is the finding.
- If the path tolerance flakes, **lower the priority of keeping it before lowering its
  value**: set `trajectory_tolerance_rad: null`, which is why the field is nullable.
  Widening it towards a value that never fires would leave a detector that only looks
  like one.
- If a graze ever needs detecting, that is Option A and a separate decision.
- Should hardware ever require a different tolerance from simulation, that is a P2
  parity break and an `ESCALATE`, not a branch in the generator.
