# Criteria — does the path tolerance stay quiet under `gz_ros2_control`, and how far below it does a healthy run sit?

**Written and committed before the first campaign trial ran, before the harness exists, and
before anything was run.** Frozen from that commit ([`../README.md`](../README.md), rule 1).
Any interpretation that had to change afterwards is recorded as a numbered deviation in
`ANALYSIS.md`, applied to data already collected — never by re-running until the definition
suited.

- **Date opened:** 2026-09-04
- **Branch under measurement:** `feat/close-phase-debts`
- **BASE_COMMIT:** **`c38a42c`**. Every figure below is a property of the tree at that commit.
  V1 in §10 is what spends it. **Verified on 2026-09-04**: `git merge-base --is-ancestor
  c38a42c HEAD` succeeds, `git diff c38a42c..HEAD -- model/ workspace/src/ tools/ tests/
  scripts/` is **empty**, and `git status --porcelain` over those five paths is empty.
- **The item that asks for it:** [`docs/open-work.md`](../../open-work.md) **#20** — following
  error under `gz_ros2_control` has never been sampled, **in either direction**. **This
  campaign runs one of the two directions**: the healthy-run half. §1 registers the other half
  as out of scope and says why it cannot be run in this tree.
- **The record that owns the tolerances:**
  [ADR-0036](../../adr/0036-execution-side-trajectory-tolerances.md), whose *"What we will have
  to revisit"* section asks for exactly this sample and states the criterion this campaign
  spends in §7.2: *"If the observed peak is not at least an order of magnitude below
  `trajectory_tolerance_rad`, the value is wrong and the margin is the finding."* **That
  criterion was registered by that record before any data existed, and it is used here as
  written.**
- **The record that supplies the derivation this campaign checks:** ADR-0036's **2026-08-27
  correction, item 3**, which derives a healthy-run following error for the simulated backend
  and says of itself that it *"does not discharge the campaign"* and is *"what the first
  measurement should be checked against, not a substitute for taking it"*. §2.2 below
  re-derives every quantity in it **independently from source at `HEAD`**, before any trial,
  and reports the agreement. **No figure is copied from that record into this campaign's data**
  (rule H, P1).
- **The record that constrains the rig:**
  [ADR-0042](../../adr/0042-partition-gazebo-transport-per-side.md). Unlike the campaign this one
  inherits its rules from, **this campaign runs a simulator**, so every Gazebo-transport process
  must go through `cite_bringup/gz.py` and nothing else. V12 is what spends it.
- **The record that makes the readiness gate an event rather than a sleep:**
  [ADR-0047](../../adr/0047-two-independent-launches-joined-not-sequenced.md) — the cell's own
  `CITE_SIDE_READY` token (P4).
- **The campaigns this one inherits from, and does not edit.**
  [`2026-09-03-stall-band-flip/`](../2026-09-03-stall-band-flip/criteria.md) — its §10 validity
  rules, its two-ended `v1_clean`, its one-writer rule and its rule-letter discipline; and
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md) — whose
  `harness/run_cell_block.sh` and `harness/cell.py` are the shape this campaign's rig needs and
  already has. **Both directories are FROZEN**: nothing in either is edited, re-run or
  re-analysed here, any file derived from either carries a header naming the source file and the
  commit it was copied at, and **no figure from either appears as this campaign's data**.
  Inherited rule letters are marked **inherited** where they appear.

---

## 0. This campaign decides nothing

The instruction that opened it was **measure, do not decide**, and the constraint is registered
here rather than remembered later.

- **No tolerance moves.** `trajectory_tolerance_rad`, the per-joint `goal` tolerance,
  `goal_time` and `stopped_velocity_tolerance` are the tree's, and this campaign proposes no
  value for any of them, argues for none, and may not be cited as support for changing one.
  **A tolerance is never widened to absorb a measurement** — that is ADR-0036's own sentence, in
  the generated file's own comment, and it is repeated here because a campaign is where the
  temptation arrives.
- **Nothing here promotes ADR-0036** or moves its status. Whether the sample this campaign takes
  discharges that record's "revisit" bullet is that record's question and the project owner's,
  not this campaign's — and §7.2 states plainly which part of it a single arm can answer.
- **Nothing here decides whether the firing half is worth building.** §1 registers it as out of
  scope and §8 names what it would need. This campaign proposes no fixture, no ADR and no work
  item.
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/` or `scripts/` is edited.** The
  cell is measured exactly as the tree at `c38a42c` ships it: shipped collision geometry,
  shipped controller configuration, shipped world. All five paths are watched by V1.
- **The harness lives entirely under `harness/` in this directory**, and `raw/` beside it.
- **This campaign takes no position on the grasp predicate.** A `Pick` whose grasp is reported
  empty is arm CARRY's business only as an excluded trial (§5.3); ADR-0052 and the
  2026-09-01/2026-09-02/2026-09-03 campaigns own that question and nothing here touches it.

---

## 1. The question, and the ones it is not

**Q — over a healthy run under `gz_ros2_control`, what is the distribution of per-joint
following error, and where does its peak sit against the `trajectory` path tolerance and the
`goal` tolerance the generated controller configuration declares?**

Two things make it a real question rather than a formality.

**It has never been sampled.** ADR-0036's launch test drives **mock hardware**, which mirrors
commands into states, so its following error is identically zero: that test proves the two
numbers are *read*, and can prove nothing about what a real one would be. Under
`gz_ros2_control` the position command interface is not a position servo (§2). So the detector
may be structurally silent in simulation while live on hardware — **a P2 asymmetry in the
direction this project cares about**, which is open-work #20's own reading and the reason the
healthy half is worth running on its own.

**A silence here is about the instrument and not about the hardware path.** Rule G in §7.5 is
what keeps that straight, and rule L in §7.1 is what keeps a silence from being manufactured by
a subscriber that never received anything.

### 1.1 The firing half is out of scope, and the reason is structural

**This campaign does not attempt to make the path tolerance fire under `gz_ros2_control`**, and
that boundary is registered here rather than discovered as a gap in the write-up.

Making it fire needs a **Gazebo-side** mechanism that obstructs an arm **link** while the
`gz_ros2_control` plugin is the loaded hardware component. **`cite_test_hardware::JointStopSystem`
(ADR-0040) cannot serve**: read at `HEAD` on 2026-09-04,
`workspace/src/cite_test_hardware/include/cite_test_hardware/joint_stop_system.hpp:99` declares
`class JointStopSystem : public mock_components::GenericSystem`, so it is a `ros2_control`
hardware component that is loaded **instead of** `gz_ros2_control/GazeboSimSystem`, not beside
it. A description that names it has no Gazebo plugin driving its joints at all, and a rig built
on it measures mock hardware again — the exact blind spot ADR-0036 names in its own "How these
errors survived" paragraph.

**What the firing half would need is named in §8 and is not designed here.**

### 1.2 Not in scope, deliberately

- **The physical arm.** Nothing here is evidence about UFACTORY's servo loop. The tolerance is
  identical on both backends, which is P2 and not negotiable; what this campaign samples is one
  backend's healthy following error, and it says nothing about the other's.
- **Whether any tolerance value is right.** Locating a distribution says where the healthy run
  sits, not what the threshold should be. §0.
- **The grasp, the part, the belts and the line.** Arm CARRY carries a work-piece because that
  is what a production motion does, not because anything about the grasp is measured.
- **A rate.** Every count is a count over the trials that ran, on one machine, on one image, at
  one commit.
- **Determinism.** Scenarios in this cell are not reproducible; the physics solver is unseeded
  (`../../architecture/cross-cutting-testing.md`). Every figure here is a sample, and V6 and
  rule R are what govern reading one.

---

## 2. The mechanism as implemented, and the arithmetic reproduced before any trial

Everything in this section was read from source at `HEAD` on 2026-09-04 and computed before this
file was committed. **Where a value agrees with one recorded in ADR-0036, that is agreement
between two derivations and is reported as such; no figure is imported** (rule H).

### 2.0 What the controller checks, and when

`joint_trajectory_controller` **4.40.1** — the version in the container image, read with
`dpkg -l`, upstream source read at tag `4.40.1`:

- `compute_error_for_joint` (`joint_trajectory_controller.cpp:1581-1607`) sets
  `error.positions[i] = desired.positions[i] - current.positions[i]` for a non-wraparound joint.
  **Every xarm5 arm joint is `type="revolute"`** (`xarm_description/urdf/xarm5/xarm5.urdf.xacro`),
  and `joints_angle_wraparound_[i]` is set only for `urdf::Joint::CONTINUOUS` (`:88-93`), so the
  plain difference is the quantity, exactly.
- The **path** check runs while the trajectory is being followed (`before_last_point ||
  first_sample`, and not holding) against `state_tolerance[i].position`, which
  `get_segment_tolerances` (`tolerances.hpp:109`) takes from the per-joint `trajectory` value.
- The **goal** check runs past the final point against `goal_state_tolerance[i].position`, from
  the per-joint `goal` value, and aborts only once `time_difference > goal_time_tolerance`.
- `check_state_tolerance_per_joint` (`tolerances.hpp:295-320`) applies a tolerance **only when it
  is greater than zero**, compares with `abs(error) > tolerance`, and on failure logs
  `State tolerances failed for joint %zu:` on the logger `tolerances`.
- The controller publishes `~/controller_state` with `rclcpp::SystemDefaultsQoS()`
  (`joint_trajectory_controller.cpp:1089-1090`) and calls `publish_state` **at the end of every
  `update()`** (`:571`), through a realtime publisher's `try_publish`.
- **Nothing in the goal overrides the generated values.** `resolve_tolerance_source`
  (`tolerances.hpp:127-152`) treats `0` as *"unspecified, keep the default"*; the generated
  MoveIt controller entry `cell_a_arm_1_moveit_controllers.yaml` declares no `path_tolerance`
  and no `goal_tolerance`, and Jazzy's `FollowJointTrajectoryControllerHandle` has its
  `configure()` commented out (`follow_joint_trajectory_controller_handle.hpp:66-67`, read in
  the image), so the goal MoveIt sends carries a default-constructed, empty tolerance set.
  **The numbers below are therefore the active ones.**

### 2.1 The declared values, read from the generated configuration

Read from `workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml` at `HEAD` on
2026-09-04, and identical in `cell_a_arm_2_controllers.yaml` and `cell_a_arm_3_controllers.yaml`
(checked by reading all three):

| declared quantity | value | where |
|---|---|---|
| per-joint `trajectory` (path) tolerance, all five arm joints | **1.0 rad** | `:111-125` |
| per-joint `goal` tolerance, all five arm joints | **0.01 rad** | `:111-125` |
| `goal_time` | **0.5 s** | `:91` |
| `stopped_velocity_tolerance` | **0.0** | `:110` |
| controller manager `update_rate` | **150 Hz** | `:15` |
| `command_interfaces` | **`position`** only | `:53-54` |
| `state_interfaces` | `position`, `velocity` | `:55-57` |
| `enforce_command_limits` | **true** | `:28` |

### 2.2 The command law under `gz_ros2_control`, and the four numbers it produces

`gz_ros2_control` **1.2.19** (`dpkg -l` in the image), upstream source read at tag `1.2.19`.
`GazeboSimSystem::write()` (`gz_system.cpp:790-797`) computes, for a joint under POSITION
control:

```
error      = (joint_position - joint_position_cmd) * update_rate
target_vel = -position_proportional_gain_ * error
```

so `target_vel = gain * update_rate * (command - position)`. The gain defaults to **0.1**
(`gz_ros2_control_plugin.cpp:314`, overridable only by an SDF `<position_proportional_gain>`
element), and **the shipped description overrides nothing**:
`cite_generated/description/cell_a_arm_1.urdf.xacro:69-74` declares the plugin with a
`<parameters>` element and a `<ros><namespace>` element and no gain. `update_rate` is the
controller manager's, passed into `initSim` (`gz_ros2_control_plugin.cpp:97-102`), and is the
150 Hz of §2.1.

**So the plant is a first-order lag, not a servo:**

| symbol | definition | value here |
|---|---|---|
| `k` | `gain * update_rate`, the lag's rate constant | **15.000 s⁻¹** |
| `tau` | `1 / k` | **0.06667 s** |
| steady-state following error tracking a constant joint velocity `v` | `v / k` | — |

**Four numbers, computed here before any trial:**

1. **What the plugin would have to command to reach the path tolerance.** An error of 1.0 rad
   gives `target_vel = 15 * 1.0 = ` **15.0 rad/s**, against the description's own
   `velocity="3.14"` on every xarm5 arm joint — a factor of **4.777**. **Nothing clamps it**:
   `enforce_command_limits` acts on the controller manager's *position* command interface before
   `write()` is called, and the velocity above is computed **inside** `write()` and written
   straight into the ECM's `JointVelocityCmd` component.
2. **The healthy peak at the speed the shipped `Pick` and `Place` use.**
   `cell_a_arm_1_joint_limits.yaml` declares `default_velocity_scaling_factor: 0.35` and
   `default_acceleration_scaling_factor: 0.35`, and `skill_server.cpp:1071` calls
   `apply_scaling(0.0, 0.0)` on the `Pick` path, which `apply_scaling` (`:1956-1967`) resolves to
   those defaults. So the fastest joint motion those skills can plan is `0.35 * 3.14 = ` **1.099
   rad/s**, and the steady-state following error is `1.099 / 15 = ` **0.07327 rad** — a margin
   of **13.65x** against the 1.0 rad path tolerance. **This reproduces ADR-0036's 2026-08-27
   correction, item 3**, which derives 73 mrad and "about 14x" by the same route; the agreement
   is between two derivations and enters no arithmetic here.
3. **The healthy peak at the fastest speed the L3 contract permits without editing anything.**
   `MoveTo.action` declares `velocity_scaling` as *"0..1 of the description's velocity limits"*
   and `apply_scaling` passes a positive value through unchanged, so a `MoveTo` goal with
   `velocity_scaling = 1.0` and `acceleration_scaling = 1.0` asks for the description's full
   3.14 rad/s. The steady-state error there is `3.14 / 15 = ` **0.20933 rad** — a margin of
   **4.777x**, and **above** ADR-0036's own 0.100 rad line. **That outcome is registered here,
   before any trial, precisely because it is the uncomfortable one.**
4. **The acceleration deficit, which makes the steady state an upper bound.** With the reference
   accelerating at `a`, the error approaches `v/k` from **below**, short by `a / k²`: at the full
   `max_acceleration: 2.0 rad/s²` that is **0.00889 rad**, and at the default-scaled
   `0.35 * 2.0 = 0.7 rad/s²` it is **0.00311 rad**. **A profile that never reaches its cruise
   velocity never reaches `v/k` at all**, which is why §7 states the prediction as `v_peak / k`
   with `v_peak` **measured per trial**, not as a single number.

### 2.3 Why the leading joint's displacement decides whether this campaign tests anything

Pilz PTP builds a trapezoidal profile bounded by `max_velocity * velocity_scaling` and
`max_acceleration * acceleration_scaling`. A move whose leading joint travels `d` reaches cruise
only if `d >= v² / a`; otherwise the profile is triangular and the peak velocity is
`sqrt(a * d)`.

**Computed here on 2026-09-04 from `cite_generated/frames/cell_a_static_tf.yaml`**, expressing
each frame in `arm_1_mount`'s own frame: `cell_a__table_pick__surface` lies at a base bearing of
**+1.0075 rad** and `cell_a__conveyor_1__infeed` at **-1.0304 rad**, so the swing between arm_1's
two production stations is **2.038 rad** of base rotation. **This is the base bearing of the
frame, not the IK solution's `joint1`**, and the two are not identical; it is an estimate,
`v_peak` is measured per trial, and rule D governs the comparison.

| condition | `a` | `v` cap | profile over `d = 2.038 rad` | predicted `v_peak` | predicted `v_peak / k` |
|---|---|---|---|---|---|
| default scaling 0.35/0.35 | 0.700 rad/s² | 1.099 rad/s | `sqrt(0.7*2.038) = 1.194 > 1.099` → **trapezoidal** | **1.099 rad/s** | **0.0733 rad**, less the 0.0031 deficit |
| full scaling 1.0/1.0 | 2.000 rad/s² | 3.140 rad/s | `sqrt(2.0*2.038) = 2.019 < 3.140` → **triangular** | **2.019 rad/s** | **0.1346 rad**, and the apex is approached from below |

**Two consequences registered before any trial.** The default-scaled arms **cannot** produce a
following error near ADR-0036's 0.100 rad line on any motion available to them — reaching 1.5
rad/s at `a = 0.7 rad/s²` needs a leading-joint displacement of `1.5²/0.7 = 3.214 rad`, larger
than the 2.038 rad swing this cell offers. And the full-scaled arm can, needing only
`1.5²/2.0 = 1.125 rad`. **Rule X in §7.4 is written on exactly that arithmetic.**

---

## 3. The four arms, and rule T over them

**The arms are named in words, not letters.** Every letter in this file names a **rule** and
nothing else, which is the discipline the 2026-09-02 campaign's pre-freeze review had to impose
on itself after four collisions.

| arm | question | motion | scaling |
|---|---|---|---|
| **CRUISE** | the healthy-run distribution at the speed the shipped `Pick`/`Place` use | arm_1: `MoveTo` home → 0.10 m above `cell_a__table_pick__surface` → 0.10 m above `cell_a__conveyor_1__infeed` → home | `velocity_scaling = 0.0`, `acceleration_scaling = 0.0` — i.e. the configured 0.35/0.35 |
| **FAST** | the same at the fastest the L3 contract permits with no edit anywhere | the identical goal set | `velocity_scaling = 1.0`, `acceleration_scaling = 1.0` |
| **CARRY** | the distribution through a real production skill with a work-piece in the jaws | arm_1: `Pick` the 50 mm cube off `table_pick`, `Place` it on `conveyor_1`'s infeed | whatever `Pick` and `Place` apply themselves — `apply_scaling(0.0, 0.0)` |
| **CONC** | whether three arms moving at once changes arm_1's distribution | arm_1 runs **CRUISE's goal set unchanged** while arm_2 and arm_3 shuttle `home` ↔ `hold-up` continuously | as CRUISE |

**CONC is a controlled comparison and CRUISE is its control**: arm_1 does the identical thing in
both, and the only difference is what else is running. Its decision quantity is **arm_1's**
error distribution. Arms 2 and 3 are load, and no verdict is stated about them.

> **Rule T — inherited verbatim from the 2026-09-03 campaign's §3, which took it from the
> 2026-09-02 campaign's.** The arms are not each other's evidence. A clean result in one says
> nothing about any other, **every verdict is stated per arm**, and an inconclusive one belongs
> in the verdict rather than in a footnote. In particular, **CRUISE staying quiet says nothing
> about FAST**, and FAST is the arm the interesting prediction is about.

---

## 4. Instruments, registered before the first trial

### 4.1 The decision quantity

| # | Quantity | Instrument |
|---|---|---|
| **I1** | per-joint following error, the decision quantity | `error.positions` on `/cite/cell_a/arm_N/arm_N_joint_trajectory_controller/controller_state` (`control_msgs/msg/JointTrajectoryControllerState`). **This is the controller's own `state_error_` buffer**, the same array `check_state_tolerance_per_joint` is handed (§2.0), not a reconstruction |
| **I2** | the reference and the feedback that produced it | `reference.positions`, `reference.velocities`, `feedback.positions`, `feedback.velocities` on the same message. `feedback.velocities` is populated because `has_velocity_state_interface_` is true (§2.1); it is the measured joint speed rule X is stated against |
| **I3** | whether the controller aborted, and on which check | two independent readings: the **L3 result** — `MoveTo.Result.result` / `Pick.Result.result` and its `detail` string, which is what a caller sees — and the **controller's own log line** `State tolerances failed for joint %zu:` on the logger `tolerances` (`tolerances.hpp:319`), scraped from the block log. **A firing is a positive event and both instruments must see it**; a disagreement between them is reported and is not resolved by choosing |
| **I4** | the joint positions from a second publisher | `/cite/cell_a/arm_N/joint_states`, published by `joint_state_broadcaster` rather than by the trajectory controller. Spent by V5's second clause; **never a reported decision quantity** |

**The QoS on I1 and I2 is declared explicitly and is the publisher's.** `SystemDefaultsQoS` is
KEEP_LAST depth 10, RELIABLE, VOLATILE, and the subscription declares exactly that — the profile
`workspace/src/cite_bringup/test/test_trajectory_constraints_launch.py:110-115` already declares
for this same topic. That file is the **only** place `JointTrajectoryControllerState` is
subscribed anywhere under `workspace/`, `tests/` or `tools/`, read by grep on 2026-09-04.
**An incompatible profile subscribes silently and delivers nothing** (CLAUDE.md §10), which on this campaign would produce
an empty set that reads as silence — the exact failure rule L exists to catch. V4 is what checks
the subscription matched before any goal was sent.

### 4.2 The rig

| # | Quantity | Instrument |
|---|---|---|
| **I5** | that the cell came up | the cell's own `CITE_SIDE_READY` token in the launch log, waited on as an event and never slept for (ADR-0047, P4) |
| **I6** | the backend that actually ran | the `robot_description` read back off the running node: the `<ros2_control>` `plugin` element for each arm, which must read **`gz_ros2_control/GazeboSimSystem`**, and the count of collision-mesh references under `cite_description/meshes/collision/xarm5/convex_hull`. **V3 and V2.** |
| **I7** | the code, the model and the description that ran | `git rev-parse HEAD`, `git status --porcelain`, `git diff c38a42c..HEAD` over the five watched paths — **taken at both ends of every block** — and the running cell's `MODEL_HASH` |
| **I8** | the host's state | the one-, five- and fifteen-minute load averages from `/proc/loadavg`, at both ends of every block, read **inside** the container. §9 records why that is the host's own reading here |
| **I9** | the simulated-to-wall clock ratio, **for context only** | `Δ sim_time / Δ real_time` over each block, computed from I1's header stamps against the wall clock. **Gazebo's own `real_time_factor` field is never quoted** — the 2026-08-29 campaign established that it over-reports under starvation, and that finding is cited, not copied. **I9 enters no verdict in §7** |

**Every Gazebo-transport call goes through `cite_bringup.gz`** — `gz_environment`, `plan_for` and
`run` — and through nothing else (ADR-0042, CLAUDE.md §10). An unpartitioned `gz model --list`
reaches no world and **exits 0**, so the failure this prevents is silence, on a campaign whose
whole hazard is silence. V12 is the rule.

### 4.3 What is deliberately not an instrument

- **`FollowJointTrajectory` action feedback.** It carries `feedback->error = state_error_`
  (`joint_trajectory_controller.cpp:454`) — the **same buffer** I1 publishes, so it is a second
  transport of one computation and not a second computation. It is not recorded, and agreement
  between the two would have evidenced nothing about the number.
- **Any reimplementation of the error.** V5 checks I1's internal consistency
  (`error == reference - feedback`) as an arithmetic identity on the message, which is a check on
  the *message*, not a second opinion about the *controller*.

---

## 5. What is varied, and what is held fixed

### 5.1 The lever is joint speed, and it is reached through the goal

Under the law of §2.2 the following error is `v / k` with `k` fixed by the plugin's gain and the
controller manager's rate. **`k` is not touched** — changing the gain means an SDF element in a
generated description, which §0 forbids. So **the only lever this campaign has is joint speed**,
and the only in-contract way to move it is `MoveTo.Goal.velocity_scaling` and
`acceleration_scaling`, which is what separates FAST from CRUISE. Both are fields on a shipped
action, sent by a caller, changing no file.

### 5.2 Held fixed unless named

| Quantity | Value | Where it comes from |
|---|---|---|
| Zone, arm under test | `cell_a`, `arm_1` | as the friction, hull-grasp, grasp-discrimination and option-F campaigns |
| Bring-up | `ros2 launch cite_bringup simulation.launch.py headless:=true zone:=cell_a` | the shipped launch, unmodified — the 2026-09-02 campaign's `run_cell_block.sh` shape |
| Collision geometry | the shipped `convex_hull` selection (ADR-0028) | V2; nothing is flipped |
| World | the generated `cell_a.sdf`, `max_step_size 0.001`, `real_time_factor 1` | unmodified |
| `use_sim_time` | true, throughout | the cell's own; I9's ratio is the only place a wall clock appears |
| Work-piece (CARRY only) | the 50 mm cube the 2026-09-02 harness spawns, at that harness's spawn pose and friction | copied with attribution; nothing about it is a lever here |
| Goal frames | `cell_a__table_pick__surface` and `cell_a__conveyor_1__infeed`, each with a **0.10 m** `+z` offset | the offset is the frozen harness's `APPROACH_M`, copied with attribution |

### 5.3 What "a healthy run" means, defined before the data

A trial is **one L3 goal**. A trial is **healthy** iff its L3 result is `SUCCEEDED`. Only healthy
trials enter the distributions in §7.2 and §7.3.

> **THE ONE EXCEPTION, AND IT IS THE POINT OF THE CAMPAIGN.** A trial whose goal failed **with a
> path- or goal-tolerance violation** — seen on either of I3's two readings — is **never
> excluded**. It is the headline finding, it is reported in full with its whole error trace, and
> the arm's QUIET1 verdict becomes FIRED. **An exclusion rule that filtered out the event the
> campaign exists to detect would manufacture the silence it is trying to measure**, and that
> sentence is registered here, before any trial, so that no later reading of "healthy" can
> reach it.

Every other failure — a planning failure, a `Pick` reporting an empty grasp, a timeout, a
refused goal — makes the trial **unhealthy**: it is excluded from the distributions, **counted
and reported by category**, and its trace is published in `raw/` anyway.

---

## 6. Design, sample size and order

**Interleave, do not block** ([`../README.md`](../README.md)). A block is **one cell bring-up**,
and within a block one **cycle** visits the four arms in order; the repeats are successive
cycles. So no arm occupies a contiguous stretch of any block, and no arm owns a bring-up.

| block | bring-ups | cycles per block | per cycle | trials per arm per block |
|---|---|---|---|---|
| B1, B2, B3 | 1 each | 3 | CRUISE 4 goals, FAST 4 goals, CARRY 2 goals, CONC 4 goals | CRUISE 12, FAST 12, CARRY 6, CONC 12 |

**126 trials over 3 bring-ups**: CRUISE 36, FAST 36, CARRY 18, CONC 36. Each trial yields
hundreds of I1 samples, so the sample count per trial is an instrument property (rule L) and not
a design parameter.

**Why three blocks.** Two is the minimum that can show a block difference at all; three lets V6
see one without the campaign resting on a single bring-up — and every published campaign in this
directory that rested on one has said so in its own limitations.

**Order within a cycle is fixed**, CRUISE → FAST → CARRY → CONC, and the cycle index and block
index **travel on every record**. A fixed order inside a cycle plus three cycles per block is
what makes an order effect visible as a cycle effect; V6 is what spends it.

**CARRY's work-piece is spawned at the start of each CARRY trial and removed at its end**, so no
cycle inherits the previous cycle's part.

**A block that aborts early is reported with the n it actually reached, and no arm is topped up**
(V8). **Quiesce 30 s between a teardown and the next bring-up**, and record I8 at both ends of
every block.

---

## 7. Thresholds — the decision rules

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.0 The sizes, and where each comes from

Every one is derived from **the declared tolerances, the geometry of the command law, or a
record's own registered criterion**, never from campaign data.

| Metric | Size | Why this size |
|---|---|---|
| the path-tolerance line | **0.100 rad** | **ADR-0036's own criterion**, *"at least an order of magnitude below `trajectory_tolerance_rad`"*, against the declared 1.0 rad. Registered by that record before any data existed |
| the goal-settle line | **0.25 s** | half the declared `goal_time` of 0.5 s. A settle taking more than half the window the controller allows is not comfortably inside it |
| minimum interesting difference, any following error | **0.005 rad** | one half of the declared per-joint `goal` tolerance of 0.01 rad — the smallest position difference this controller is configured to care about anywhere |
| rule X's stress speed | **1.5 rad/s** | **derived, not chosen**: it is `0.100 * k`, the joint speed at which the predicted steady-state error equals ADR-0036's own line. Below it the criterion cannot be missed by the lag mechanism at all |
| V5's identity tolerance | **1e-9 rad** | `error == reference - feedback` is an arithmetic identity on one message in double precision, not a measurement agreement |
| rule D's agreement band | **25 %** of `v_peak / k` | the acceleration deficit `a/k²` is **12.1 %** of the cruise prediction at default scaling and **12.1 %** at full scaling (§2.2 item 4 over §2.3's velocities); a 25 % band admits that deficit and roughly its double without admitting a factor of two |

### 7.1 LIVE1 — measured quiet, or measured nothing

**This is the campaign's central hazard.** A subscriber that never matched, a topic that does not
exist, a QoS mismatch, a controller that never activated, and a rig that quietly ran on mock
hardware all produce the same empty or zero set — and every one of them reads as *"the tolerance
stayed quiet"*.

> **Rule L — the liveness rule. No quietness claim is admissible for a trial that does not
> satisfy it, and it is checked per trial.** A trial's samples are admissible iff **all four**
> hold:
> - **L1 — enough samples.** At least **100** `controller_state` messages during the trial's
>   moving window, each carrying `error.positions` of length 5.
> - **L2 — a plausible rate.** At least **20 samples per second of simulated time** across that
>   window, against the 150 Hz the controller publishes at. The achieved rate is **reported per
>   trial** whatever it is.
> - **L3 — a demonstrated non-zero error somewhere.** At least one sample in the trial with
>   `max_j |error_j| >= 0.001 rad`. **This is what separates a quiet detector from a dead
>   instrument**: mock hardware mirrors commands into states and produces exactly 0.000000, and
>   so does a subscription that received nothing. 0.001 rad is far below every interesting size
>   in §7.0 and far above double-precision noise.
> - **L4 — the message is internally consistent.** V5 holds on at least 99 % of the trial's
>   samples **and** on the sample carrying the trial's peak.
>
> A trial failing any of the four is an **INSTRUMENT LOSS**: excluded from every distribution,
> **counted and reported separately from every other exclusion**, and **never recorded as a quiet
> trial**. If more than **20 %** of an arm's trials are instrument losses, that arm's QUIET1 and
> BAND1 are **NOT ADMISSIBLE** and rule N applies to it.

> **LIVE1 — ADMISSIBLE / NOT ADMISSIBLE, stated per arm**, with the sample counts, the achieved
> rates, the loss count by cause, and the per-arm minimum and maximum of `max_j |error_j|`.
> **`ANALYSIS.md` states LIVE1 before it states QUIET1**, for every arm, so that no quietness
> verdict can be read without the instrument's own report beside it.

### 7.2 QUIET1 and BAND1 — did it fire, and how far below is the healthy peak

Report, per arm and per joint: `n` trials, `n` samples, the distribution of `|error|` over the
moving window (min, median, p95, p99, max), the peak with the trial and sample that produced it,
the peak measured `|feedback.velocities|` and `|reference.velocities|`, and the block and cycle
index of every peak.

> **QUIET1 — QUIET / FIRED / NOT ADMISSIBLE, stated per arm.**
> **QUIET** iff LIVE1 is ADMISSIBLE for that arm **and** no trial of it produced a path-tolerance
> violation on either of I3's readings. **FIRED** if any trial did — reported in full, with both
> readings, as the campaign's headline. **NOT ADMISSIBLE** otherwise, under rule L.

> **BAND1 — FAR / SHORT, stated per arm, against ADR-0036's own line.**
> **FAR** iff the arm's peak `|error|` over all healthy trials is **<= 0.100 rad**, which is the
> *"at least an order of magnitude below"* that record asks for.
> **SHORT** iff it exceeds 0.100 rad. **A SHORT verdict is reported and acted on by nobody
> here** — ADR-0036 says of that outcome that *"the value is wrong and the margin is the
> finding"*, and **whether the value is wrong is that record's question and the project owner's,
> not this campaign's** (§0). This campaign reports the margin and proposes nothing.

> **The scope of ADR-0036's criterion, stated before the answer.** That record asks for the
> sample *"across `pick_and_place` and `continuous_line`"*, which run at the configured 0.35
> scaling. **CRUISE, CARRY and CONC are inside that scoping; FAST is not.** FAST is reported
> against the same band because the band is the only registered line there is, and
> **`ANALYSIS.md` must state beside FAST's BAND1 that it is outside the condition ADR-0036's
> sentence is about.** A SHORT on FAST does not make that record's sentence false, and may not be
> written as though it did.

> **Rule M — the sampled peak is a lower bound on the checked peak, and the two verdicts are not
> equally strong.** `publish_state` runs at the end of every `update()`, but through a realtime
> publisher's `try_publish`, and the tolerance check runs in `update()` **whether or not the
> message is delivered**. So a **FIRED** verdict rests on a positive event the controller itself
> reports and is as strong as the controller; a **QUIET** verdict rests on the absence of that
> event, which is equally strong; but **BAND1's peak is a maximum over the samples that
> arrived**, and is a **lower bound** on the maximum the controller actually compared. **A FAR
> verdict is therefore weaker than a SHORT one** — SHORT is established by a single delivered
> sample, FAR is an assertion about samples not taken. `ANALYSIS.md` states rule M beside every
> FAR verdict, with that arm's achieved sample rate.

### 7.3 GOAL1 — the goal tolerance and the settle

Report, per arm: whether any trial aborted on the goal check; and per trial the **settle
interval** from the last trajectory point to the first sample with `max_j |error_j| <= 0.01 rad`,
against the declared `goal_time` of 0.5 s.

> **GOAL1 — CLEAR / TIGHT / FIRED, stated per arm.** **CLEAR** iff no goal-tolerance abort
> occurred and every healthy trial's settle interval is **<= 0.25 s**. **TIGHT** iff no abort
> occurred but some trial's settle exceeded 0.25 s — the goal window is being used up rather than
> sat comfortably inside. **FIRED** iff any trial aborted on the goal check. Rule L gates it as it
> gates QUIET1, and rule M applies: a settle measured from delivered samples is bounded below by
> the sample interval.

> **SVT — NOT MEASURED, and registered as not measured rather than measured as a constant.**
> `stopped_velocity_tolerance` **cannot fire on this controller**, for **two independent reasons
> both read in source at §2.0**: `compute_error_for_joint` writes a velocity error only under
> `has_velocity_state_interface_ && (has_velocity_command_interface_ || has_effort_command_interface_)`
> and this controller commands **position only**, so `state_error_.velocities` stays at the zeros
> it was sized to; and `check_state_tolerance_per_joint` applies a velocity tolerance only when it
> is `> 0.0`, and the generated value is `0.0`. **Either alone is sufficient.** This campaign
> records that and samples nothing for it; the generated file's own comment says the same thing
> and is not restated further (P1).

### 7.4 X1 — did the campaign stress the tolerance at all

> **Rule X — the refusal, in the rule-S and rule-W shape, and "plausibly stress" is defined here
> before the answer is known.** The following error under this plant is `v / k` (§2.2), so the
> **only** quantity that can drive it towards the path tolerance is joint speed. A trial
> **stresses** the path tolerance iff its peak measured joint speed reaches **1.5 rad/s** — the
> speed at which the predicted error equals ADR-0036's own 0.100 rad line (§7.0).
>
> - **CRUISE, CARRY and CONC cannot stress it, by construction**, and this is registered rather
>   than discovered: their cap is 1.099 rad/s (§2.2), and reaching 1.5 rad/s at their
>   acceleration ceiling would need a leading-joint displacement of 3.214 rad against the 2.038
>   rad this cell offers (§2.3). **Their quietness is therefore a statement about the speeds they
>   ran at and about nothing faster.**
> - **Whether FAST stresses it is unknown before the trial.** §2.3 predicts 2.019 rad/s on a
>   triangular profile, but that rests on a base-bearing estimate of the leading joint's
>   displacement, and the IK solution is not obliged to agree with it.
>
> **X1 — STRESSED / NOT STRESSED, stated per arm.** If **no arm** is STRESSED, then **the
> campaign has not tested the path tolerance**, its verdict reads *"not tested above a peak joint
> speed of V rad/s, over these trials, on this rig"*, and **its silence may not be read as a
> pass, as a clearance of the detector, or as evidence that the tolerance is inert**. #20's
> healthy half is then **still open**, and `ANALYSIS.md` must say so in those words.

### 7.5 The refusals that carry the campaign's honesty, and the predictions

> **Rule G — what these numbers are properties of.** Every figure here is a property of
> **`gz_ros2_control` 1.2.19's command conversion**, at this gain, this controller-manager rate,
> this world's 1 ms step and this host — and of **nothing else**. In particular:
> - **It is not a property of the arm.** The 0.0667 s lag is the plugin's, not UFACTORY's.
> - **A quiet path tolerance here is not evidence that it stays quiet on hardware, and not
>   evidence that it fires there either.** #20's asymmetry is not resolved in either direction by
>   a simulation-only sample, and `ANALYSIS.md` may not use the word "validated" about the
>   tolerance on either backend.
> - **It is not evidence about the firing half.** §1.1. Nothing here shows the detector *can*
>   detect anything under this backend; it shows what a healthy run looks like.
>
> **`ANALYSIS.md` states rule G beside every verdict in §7.2 and §7.3.**

> **Rule N — a null is not a clearance. Inherited from the 2026-09-03 campaign, whose own is in
> ADR-0051's rule-S shape.** Where an arm is NOT ADMISSIBLE under rule L, or NOT STRESSED under
> rule X, the campaign's silence about it may **not** be read as agreement with §2.2's
> arithmetic, as a clearance of the tolerance, or as evidence the detector behaves. The verdict
> names what was not tested, and #20 stays open on that part.

> **Rule R — resolution. Inherited from the 2026-09-01 campaign's rule R via the 2026-09-02 and
> 2026-09-03 campaigns.** For any metric whose spread **within one arm at one goal** exceeds that
> metric's minimum interesting size of 0.005 rad, a non-detection of a difference between arms is
> **INCONCLUSIVE for that metric — never "no difference"**. The comparison this binds hardest is
> CONC against CRUISE.

> **Rule H — no cross-campaign differencing. Inherited from the 2026-09-02 scenario-ceilings
> campaign.** No **measured** figure from any other campaign is differenced against any figure
> here. ADR-0036's 73 mrad is admitted into §2.2 **only** because it is a **derivation** that this
> campaign reproduces from source, and it is named as an agreement between two derivations; it
> enters no arithmetic. No campaign directory's figures are subtracted from, divided by, or
> described as an improvement on anything here.

> **Rule D — the arithmetic and the measurement are allowed to disagree, and the disagreement is
> the finding. Inherited from the 2026-09-03 campaign.** Per trial, the measured peak `|error|` is
> compared with `v_peak / k`, `v_peak` being that trial's own measured peak joint speed and `k`
> the 15.000 s⁻¹ of §2.2. **If they differ by more than 25 %:**
> - it is reported as a **DISAGREEMENT**, with both numbers and the whole trace that produced it;
> - **nothing is re-run to resolve it**, no goal is retuned in the direction that would make it go
>   away, and no constant anywhere in the tree is edited (§0);
> - **the campaign does not attribute it.** Whether the cause is the gain, the update rate, the
>   physics engine's handling of the velocity command, the time parameterisation or the harness is
>   not decided here, and the write-up lists the candidates without choosing;
> - it is stated in `ANALYSIS.md`'s verdict line rather than in a deviation, because it is a
>   result and not a procedural exception.

**Predictions, so that this campaign can be wrong:**

| # | Prediction | Refuted by |
|---|---|---|
| **P1** | **QUIET1 = QUIET on every arm.** Reaching the 1.0 rad path tolerance needs the plugin to command 15.0 rad/s, 4.777x the description's own joint limit (§2.2 item 1). | any path-tolerance violation on any arm — which would be the campaign's headline and would refute the mechanism as well as the prediction |
| **P2** | **BAND1 = FAR on CRUISE, CARRY and CONC**, with peaks near **0.070 rad** (§2.3). | a peak above 0.100 rad on any of the three |
| **P3** | **BAND1 = SHORT on FAST**, with a peak near **0.126–0.135 rad** (§2.3), i.e. ADR-0036's own order-of-magnitude line is **not** met at the fastest speed the L3 contract permits. **This is registered as the uncomfortable outcome, before any trial.** | a FAST peak at or below 0.100 rad |
| **P4** | **GOAL1 = CLEAR on every arm.** The settle from 0.0733 rad to 0.01 rad is `tau * ln(7.33) = ` **0.133 s**, and from 0.2093 rad it is `tau * ln(20.93) = ` **0.203 s**, both inside the 0.25 s line and well inside the declared 0.5 s. | any settle above 0.25 s, or any goal-tolerance abort |
| **P5** | **CONC is indistinguishable from CRUISE** at the 0.005 rad minimum interesting size. The controller manager is stepped by the simulator in **simulation** time (`GazeboSimROS2ControlPlugin::PostUpdate` gates `update()` on `sim_period >= control_period`), so concurrent load stretches wall clock and leaves the loop's simulated cadence alone. **This is an argument from the plugin's structure, and P5 is what tests it.** | a difference above 0.005 rad, which would be a finding about the backend and not about the arms |
| **P6** | **X1 = STRESSED on FAST and NOT STRESSED on the other three.** | FAST failing to reach 1.5 rad/s — in which case rule X fires over the whole campaign, and the healthy half of #20 is still open |

---

## 8. Explicitly not measured, recorded here rather than discovered later

- **The firing half of #20** — that the path tolerance fires under `gz_ros2_control` on a genuine
  obstruction. §1.1 gives the structural reason it cannot be run in this tree.
  **What it would need, named and not designed** (§0): a mechanism that obstructs an arm **link**
  while the Gazebo plugin remains the loaded hardware component — for example a collision body
  placed in the arm's path, a joint perturbation applied through Gazebo's own transport, or a
  `ros2_control` hardware component that **wraps** `GazeboSimSystem` rather than replacing it.
  **Which of those is right, whether any is worth building, and what record would own it are not
  decided here.**
- **The physical arm**, and therefore #20's P2 asymmetry itself. Only Phase 2.B bring-up settles
  what the tolerance does on hardware; a simulation-only sample bounds one side of the asymmetry
  and not the asymmetry.
- **Whether the physics engine clamps the plugin's velocity command.** `write()` writes
  `target_vel` into a `JointVelocityCmd` component; whether `gz-sim` 8.11.0 or its dartsim backend
  then clamps that against the joint's SDF axis velocity limit is **unverified here**. It does not
  change §2.2 item 1 — the plugin still *commands* 15.0 rad/s at the tolerance — but it does bear
  on what happens after that, and the instrument that would settle it is reading `gz-sim` 8.11.0's
  physics system for its handling of that component, or measuring whether any joint's measured
  speed ever exceeds 3.14 rad/s. **The second of those is recorded by I2 anyway and will be
  reported**; the first is not done here.
- **`stopped_velocity_tolerance`.** §7.3, with both structural reasons.
- **Whether any declared tolerance is the right value.** §0.
- **`continuous_line`'s motion.** CONC runs three arms concurrently; it does not run the line, the
  belts, the beams, the handoffs or L4. ADR-0036's revisit bullet asks for a sample across both
  scenarios and **this campaign samples neither scenario**: it drives L3 directly, because a
  recorder must live in the same container as the launch (discovery from a second container is
  partial — `../../operations/troubleshooting.md`) and because a scenario failing for its own
  reasons would consume a block. **So the part of that bullet asking for the scenarios' own
  motions is not discharged here**, and `ANALYSIS.md` must say so.
- **Any arm but `arm_1` as a decision quantity**, any zone but `cell_a`, any collision geometry
  but the shipped hulls, any `max_step_size` but 1 ms, any controller-manager rate but 150 Hz, and
  any gain but the plugin's default 0.1. Each of those changes `k` or the plant and reopens every
  number in §2.
- **A rate of anything.** Every count is over the trials that ran.

---

## 9. The machine, named

Naming the machine is a decision clause of
[ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md) and the practice of every
campaign in this directory since. It matters **more** here than in the campaign this one inherits
its rules from, because this rig runs a simulator and the host's spare capacity decides the
wall-clock cost of every block.

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM |
| Free disk | **399 GiB** available on `/`, read on 2026-09-04 |
| Docker | **29.7.2** (build a7dcaa6); Docker Compose **v5.5.0** |
| Container image | **`cite-digital-twin:dev`**, image ID `3a41d4e431b0`, full digest `sha256:3a41d4e431b0a200c0b7a00d89bbcb44669f03d3aa754f56b89496a240fede7d`, Ubuntu **24.04.4 LTS**, ROS 2 **Jazzy**, Gazebo Sim **8.11.0** |
| Controllers | `gz_ros2_control` **1.2.19**, `joint_trajectory_controller` **4.40.1**, `controller_manager` **4.45.2**, all read with `dpkg -l` inside the image on 2026-09-04 |
| Isolation | compose project **`cite-digital-twin-3319196271`** and **`ROS_DOMAIN_ID` 43**, both derived from this checkout by **sourcing `scripts/_lib.sh`** on 2026-09-04, not typed in |
| Allocation | the container is **not** CPU-limited by any condition here |

> **The simulator version is the one the *sourced* environment resolves, and that distinction is
> load-bearing.** The image carries **two** Gazebo Sim installations: an unsourced probe
> (`docker run --entrypoint bash`) finds `/usr/bin/gz` at **8.15.0**, and a sourced one
> (`./scripts/enter dev bash -c`) finds `/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz` at **8.11.0**,
> both reproduced on this image on 2026-09-04. **The cell runs sourced**, so 8.11.0 is the
> simulator this campaign measures. The split is not only the CLI — the sourced
> `LD_LIBRARY_PATH` resolves `libgz-sim8.so.8` to the vendored 8.11.0 library ahead of the system
> 8.15.0. This is recorded in
> [`../../operations/troubleshooting.md`](../../operations/troubleshooting.md) and is not restated
> further (P1). **Unlike the campaign this one inherits from, this rig does bring Gazebo up**, so
> the version above is a fact about what was measured and not a formality.

**Host load before the first trial, measured rather than claimed.** Read on 2026-09-04 on a host
up 1 day 21 h 50 m:

```
0.13 0.11 0.03        (/proc/loadavg, 16 cores)
```

**This host was quiet at the time of writing, and that is a statement about that moment and not
about the campaign.** It must not be assumed to hold: the 2026-09-02 scenario-ceilings campaign
found many of its own post-run loads above 4.0 on this same host (its figures are cited and not
copied). I8 records the load at both ends of every block, and V7 is what spends it.

**What host load could and could not reach here, argued rather than asserted.** The controller
manager is stepped by the simulator in **simulation** time (§7.5's P5), so a starved host stretches
wall clock and leaves the 150 Hz cadence and the 1 ms physics step alone; the decision quantity is
a position difference inside that loop. **What load can reach is the instrument** — `try_publish`
drops when the non-realtime publisher thread is behind, which lowers the sample rate and is exactly
what rules L2 and M are written for — and **whether a trial completes at all**, which appears as a
failed trial and not as a moved number. I9's clock ratio is recorded per block as context and
**enters no verdict**.

> **A container load reading comes from the container, and on this host that is the host's.**
> `/proc/loadavg` is not namespaced on native Linux and there is no `lxcfs` in the way; the
> 2026-09-02 campaign demonstrated it on this host. I8 nevertheless names where each reading was
> taken, because the 2026-08-31 capacity campaign applied a validity rule that read a virtual
> machine's load rather than the host's.

---

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — `v1_clean`, inherited from the 2026-09-02 scenario-ceilings campaign via the 2026-09-03
  one, including its five watched paths and its both-ends reading.** A block contributes only if
  **at BOTH ends of the block** — I7 is taken twice — `git diff c38a42c..HEAD -- model/
  workspace/src/ tools/ tests/ scripts/` is **empty** and `git status --porcelain` shows **no
  dirt** in those five paths. **`v1_clean` is the CONJUNCTION of the two readings**, and a block
  whose two readings disagree is **discarded and reported** as an edit that landed mid-block. The
  base still holds, verified on 2026-09-04 (preamble). **`docs/measurements/` may advance while
  the campaign runs and nothing else may** — this campaign's own `criteria.md`, harness and raw
  all land on this branch, so `HEAD` necessarily advances and pinning it would discard every
  block including the first. **The flag is computed where the block is taken and travels ON the
  record; the analyser drops any row without it.** Not a note in a README: a field.
- **V2 — the description that actually ran.** Every block reads the description the rig publishes
  and counts collision-mesh references under
  `cite_description/meshes/collision/xarm5/convex_hull`: **13** for the shipped `convex_hull`
  selection — the count of files in `assets/meshes/collision/xarm5/convex_hull/`, read on
  2026-09-04 in this checkout. A block that disagrees is **discarded and reported**: the cell
  would be built from a description this repository does not ship. The running cell's
  `MODEL_HASH` is recorded with it.
- **V3 — THE BACKEND THAT ACTUALLY RAN, and it is the most important rule in this campaign.**
  Every block asserts, from the description read back off the running node, that each arm's
  `<ros2_control>` block names **`gz_ros2_control/GazeboSimSystem`**. A block that finds anything
  else is **discarded and reported**. **Mock hardware mirrors commands into states and produces a
  following error of exactly zero**, so a rig that silently ran on it would produce a perfect,
  perfectly meaningless silence — which is the precise failure ADR-0036 records having already
  been caught by once. Rule L3 catches it from the other side; both are kept.
- **V4 — the subscription matched before any goal was sent.** Per block, per arm, the
  `controller_state` subscription reports at least one matched publisher **and** at least one
  received message **before** the first L3 goal of the block. A block that sends a goal without
  it is **discarded and reported**: reliable QoS is a promise to *matched* subscribers, and a
  subscription created and immediately used reaches nobody (CLAUDE.md §10). **Treat the match as
  an event, never as a sleep.**
- **V5 — the message is internally consistent.** Per sample,
  `|error.positions[i] - (reference.positions[i] - feedback.positions[i])| <= 1e-9` for every
  joint. On these revolute joints that is an exact identity (§2.0), so a violation means the
  record is not what it claims to be. Spent by rule L4. Additionally, per trial, the peak
  sample's `feedback.positions` is compared with the nearest `/joint_states` sample (I4) and the
  difference reported; **a disagreement there is reported and excludes nothing**, because the two
  are sampled independently and are not obliged to coincide in time.
- **V6 — the block effect. Inherited.** Every bring-up is a block and every cycle within it is
  indexed, and both travel on every record. If, for any metric, the difference between two blocks
  within one arm is larger than the difference between two arms, that metric's finding is
  **downgraded to INCONCLUSIVE** whatever any test statistic says.
- **V7 — the load is recorded, and a loud host is reported rather than excluded. Inherited.** I8
  is taken at both ends of every block. **No block is discarded for load**, because a load
  threshold chosen after seeing the data is a threshold chosen by the data. **If any reading
  exceeds 4.0 on 16 cores, every trial in that block is flagged and every verdict it contributes
  to is reported with and without those trials**, and if a verdict differs, that verdict is
  INCONCLUSIVE under rule R.
- **V8 — n is what it was. Inherited.** Every count is reported over the trials that actually ran,
  with a Wilson 95 % interval where it is a proportion. **No arm is topped up** to match another,
  and a block that aborts early is reported with the n it reached.
- **V9 — no threshold moves. Inherited.** Nothing in this file changes once the first campaign
  trial has run. **A threshold discovered to be wrong is applied literally and recorded as wrong**,
  and the disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data already
  collected. The 2026-08-31 capacity campaign applied a validity rule it had found to be reading
  the wrong quantity, literally, and reported it; that is the precedent.
- **V10 — one writer at a time. Inherited.** **A concurrent agent editing a watched path mid-block
  flips `v1_clean` and silently discards the block** — a fact only because V1 takes I7 at both ends
  and conjoins the readings. So the campaign runs with **one writer in this checkout**, and the
  campaign operator states in `ANALYSIS.md` whether that held. A campaign that loses blocks this
  way **reports the loss under V1 rather than re-running until it stops happening.**
- **V11 — no rebuild mid-campaign. Inherited.** `./scripts/build` runs once before the first
  trial. If a rebuild becomes necessary it is a numbered deviation, and every block before it is
  reported separately from every block after it.
- **V12 — every Gazebo-transport process carries the partition (ADR-0042).** Every `gz`, every
  `ros_gz_sim` call and every probe goes through `cite_bringup.gz`, and the harness constructs no
  Gazebo environment of its own. **An unpartitioned `gz model --list` reaches no world and exits
  0**, so a block that made a raw call would produce plausible silence rather than an error; such
  a block is **discarded and reported**. The guard under `tests/scenarios/guards/` enforces this
  for `tests/` and does not reach `docs/measurements/`, which is why the rule is stated here.
- **V13 — the cell announced readiness as an event.** A block contributes only if the launch
  printed `CITE_SIDE_READY` (I5) before the first goal, and only if no arm's L3 action server had
  to be waited on past the harness's own ceiling. **Nothing in the harness sleeps to sequence
  bring-up** (P4).
- **V14 — one clock.** Every recorded stamp is the controller's simulated time, and the only place
  a wall clock appears is I9's ratio. **A wall-clock rate is never divided into a simulation-time
  error**; ADR-0036's own correction names that mixing as the failure class CLAUDE.md §10 records
  under "Time", and it produces a plausible, wrong answer. A trial whose samples carry a
  non-monotonic or wall-clock stamp is **excluded and reported**.

**One shakedown run per harness is permitted and is not data.** Before the first campaign trial,
each harness may be run **once** to prove it starts, brings the cell up, matches its
subscriptions and writes a record. Its output is published under **`raw/shakedown/`**, is
**excluded from every figure in §7**, and **may not be used to set or adjust any threshold in
this file** — every threshold above is derived from a declared tolerance, from the command law's
geometry, or from ADR-0036's own registered criterion, and none of them needs a shakedown to
exist. If the shakedown reveals a defect, **the harness is fixed and this file is not touched.**

---

## 11. Honesty bounds fixed in advance

- **This campaign chooses nothing.** It moves no tolerance, promotes no record, and decides
  nothing about whether the firing half should be built. §0.
- **It closes one half of one item, at most** — open-work #20's healthy-run direction, and only
  under rule L and rule X. **The firing half stays open and this campaign does not narrow it by
  one millimetre.** §1.1, §8.
- **A null is not a pass.** Rules L, X, N, M, R, G, D and T exist for exactly that, and all eight
  were written before any trial ran. **Rule L is the one that matters most here**: a subscriber
  that never received, a topic that does not exist, a QoS mismatch and a rig that ran on mock
  hardware all produce the same empty set, and **an empty set is not a quiet detector**.
- **Rule M's asymmetry is carried into every sentence.** A firing is established by one delivered
  sample; a silence about the *magnitude* is an assertion about samples that were not taken.
- **The measurement is allowed to contradict the arithmetic.** Rule D says what happens then, and
  it says it before the answer is known: the disagreement is the result, nothing is re-run and
  nothing is edited.
- **The uncomfortable prediction is registered, not discovered.** P3 predicts that the fastest
  motion this contract permits misses ADR-0036's own order-of-magnitude line. If it does, that is
  a reported margin and **not** an argument for changing a number (§0), and it is outside the
  condition that record's sentence is scoped to (§7.2).
- **Nothing here is a P2 result.** It samples one backend. It is not evidence about the physical
  arm in either direction, and #20's asymmetry is not resolved by it.
- **One machine, one image, one commit, one checkout, one zone, one arm as the decision quantity,
  three bring-ups, and it is not a rate.**
- **Both cited campaigns stay frozen.** No file under
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md) or
  [`2026-09-03-stall-band-flip/`](../2026-09-03-stall-band-flip/criteria.md) is edited, re-run or
  re-analysed here, **no figure from either appears as this campaign's data**, and rule H forbids
  differencing any measured figure of theirs against anything here.
- **Figures stay in this directory.** Nothing produced here is copied into ADR-0036, `CLAUDE.md`,
  [`docs/open-work.md`](../../open-work.md), the generated comments or any layer document (P1).
  **Cite the directory.**
