# ADR-0036: Detect a mistracked trajectory at execution, with tolerances declared in L0

- **Status:** Proposed
- **Date:** 2026-08-27
- **Deciders:** Coder agent, on a finding raised by `safety-auditor` while auditing ADR-0027
- **Related:** [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0027](0027-pilz-planning-pipeline.md),
  [cross-cutting-safety.md](../architecture/cross-cutting-safety.md),
  charter §3.2 and §4 (P1, P2, P5, P7)

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

`get_segment_tolerances` assigns `goal_state_tolerance[i].velocity =
constraints.stopped_velocity_tolerance` unconditionally, and that parameter defaults
to `0.01` rad/s rather than to zero. It is therefore the **one** goal-side check that
is live today. It has been harmless only because `goal_time` is `0.0`: a joint still
creeping at the trajectory's end keeps the goal open rather than failing it, and in
practice the joints settle and the goal succeeds.

Setting `goal_time` to a finite value changes that. A joint that settles at
`t_end + 0.8 s` succeeds today and would abort at `t_end + 0.5 s`. Enabling
`goal_time` without also deciding this parameter would introduce a *velocity*-driven
flake while intending to add a *position* detector.

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
