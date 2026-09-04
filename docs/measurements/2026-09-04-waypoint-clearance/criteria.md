# Criteria — how close does this cell actually pass, and how far does it step between the only checks it gets?

**Written and committed before the first campaign trial ran, before the harness exists, and
before anything was captured.** [`../README.md`](../README.md)'s rule 1 freezes this file **once
the first trial has run**. Until then it is corrigible; after then, any interpretation that had
to change is recorded as a numbered deviation in `ANALYSIS.md`, applied to data already
collected — never by re-running until the definition suited.

- **Date opened:** 2026-09-04
- **Branch under measurement:** `feat/close-phase-debts`
- **BASE_COMMIT:** **`c38a42c`**. Every figure below is a property of the tree at that commit.
  V1 in §10 is what spends it. **Verified on 2026-09-04 over the seven paths V1 watches**:
  `git merge-base --is-ancestor c38a42c HEAD` succeeds, `git diff c38a42c..HEAD -- model/
  workspace/src/ tools/ tests/ scripts/ assets/ external/` is **empty**, and
  `git status --porcelain` over those seven paths is empty.
- **The vendor half is pinned by SHA and cannot be watched by diff.** `external/cite.repos`
  fixes `xarm_ros2` at **`3dc2b5e8294758d96b54b15fa5920d581b7cbb3d`** and the imported checkout
  reads the same SHA (`git -C workspace/src/external/xarm_ros2 rev-parse HEAD`, 2026-09-04).
  **That half of the tree is one of the two geometries this campaign measures**, so the pin is
  not a formality here: it is the source of one of the two mesh sets, and V1 spends it at both
  ends of every block.
- **The two items that ask for it**, both in [`docs/open-work.md`](../../open-work.md):
  - **#49** — link-versus-environment clearance under hull geometry is measured by nothing.
  - **#17** — Pilz checks collisions every 0.1 s and can step past a beam housing.

  **They share one instrument — forward kinematics over trajectory waypoints — which this tree
  does not have.** §4 builds it once and §7 answers both against it.
- **The records that own the two questions:**
  [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md), whose audit covered arm-internal
  link pairs and whose own text names environment clearance at the cell's working poses as
  **still unmeasured**; and [ADR-0027](../../adr/0027-pilz-planning-pipeline.md), which records
  that `ValidateSolution` is the sole environment-collision gate and interpolates nothing
  between waypoints. **Neither record's figures enter this campaign's data** (rule H, and the
  explicit list in §2.5).
- **The record that constrains the rig:**
  [ADR-0042](../../adr/0042-partition-gazebo-transport-per-side.md). **The capture stage runs a
  simulator**, so every Gazebo-transport process must carry the partition the generated plan
  names, and an unpartitioned `gz model --list` reaches no world and **exits 0**. V12 is what
  spends it.
- **The record that makes the readiness gate an event rather than a sleep:**
  [ADR-0047](../../adr/0047-two-independent-launches-joined-not-sequenced.md). Nothing in the
  harness sleeps to sequence a bring-up (P4).
- **The campaigns this one inherits from, and does not edit.**
  [`2026-09-04-following-error/`](../2026-09-04-following-error/criteria.md) — its §10 validity
  rules, its two-ended `v1_clean`, its one-writer rule, its rule-letter discipline and its
  machine block; [`2026-09-03-stall-band-flip/`](../2026-09-03-stall-band-flip/criteria.md) —
  rules D, N, R and the two-ended `v1_clean` it passed on; and
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md) — **rule W's
  shape**, which is what §7.7's rule K is built in. **All three directories are FROZEN**:
  nothing in them is edited, re-run or re-analysed here, any file derived from one carries a
  header naming the source file and the commit it was copied at, and **no figure from any of
  them appears as this campaign's data**. Inherited rule letters are marked **inherited** where
  they appear.

---

## 0. This campaign decides nothing

The instruction that opened it was **measure, do not decide**.

- **It moves no threshold, no tolerance and no ceiling.** Not a scenario wall-clock ceiling, not
  a velocity or acceleration scaling factor, not a tolerance in a generated controller file.
- **It does not select a geometry.** `description.collision.select` stays at the shipped
  `convex_hull` and is not flipped. §5.2 records why flipping it is not available to this
  campaign at all.
- **It promotes nothing.** ADR-0028 is `Accepted` and this campaign does not touch that;
  ADR-0027's residual is that record's and the project owner's. Neither status moves here.
- **It proposes no fix for #17.** Lowering a velocity scaling, densifying a trajectory before
  validation and changing the layout are the levers named in that item; **this campaign
  evaluates none of them, recommends none of them and may not be cited as support for any of
  them.**
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/`, `scripts/`, `assets/` or
  `external/` is edited.** The cell is measured exactly as the tree at `c38a42c` ships it. All
  seven paths are watched by V1.
- **The harness lives entirely under `harness/` in this directory**, and `raw/` beside it.
- **It takes no position on the grasp predicate, the friction grasp, the line's dead ends or
  the real-time floor.** Those have their own records and their own campaigns.

---

## 1. The questions, and the ones they are not

**Q1 (#49) — over the joint trajectories this cell actually produced, what is the per-waypoint
minimum distance from every collision link to every planning-scene object, and how does that
distance differ between the convex-hull collision set this repository ships and the vendor mesh
set it replaced?**

**Q2 (#17) — over the same trajectories, how large is the per-waypoint tool-point Cartesian
step, against the smallest object in the generated planning scene; and does any densely
interpolated configuration between two checked waypoints touch an object that neither bracketing
waypoint touches?**

Q2's second clause is the sharper instrument and it is registered deliberately. The published
arithmetic in #17 — a step exceeding the housing thickness — is a **necessary condition for a
full traversal, not a sufficient condition for safety**: a segment can clip a corner of a convex
body with an arbitrarily short chord while both endpoints sit outside it. So the step is
reported (STEP1) **and** the thing the step is a proxy for is measured directly (TUNNEL1).

### 1.1 What this design structurally cannot answer, registered before it is discovered

**#49's feared consequence is a plan the hull set refuses and the vendor set would have
accepted. This campaign cannot observe one, and the reason is the capture door.**

- The capture door (§2.1) is `DisplayMotionPath`, a **response adapter**, and MoveIt's pipeline
  **breaks the response-adapter chain on the first failure**
  (`planning_pipeline.cpp:333-350`, MoveIt 2.12.4, read on 2026-09-04). `ValidateSolution`
  stands **before** `DisplayMotionPath` in both generated pipelines
  (`cell_a_arm_1_planning_pipelines.yaml`), so **a refused trajectory is never published**. The
  campaign can count refusals (REFUSE1) and cannot measure their geometry.
- The captured set is therefore **conditioned on acceptance under the hull set**. Together with
  the containment relation of §2.3 that has an exact consequence, registered here before any
  number exists: **no captured waypoint can be in collision under either geometry**, so FLIP1
  (§7.2) is **NONE by construction** and evidences nothing about either set. It is registered so
  that it cannot later be read as a clearance.
- **What is left, and it is what #49 asked for:** the **margin** — how close the cell actually
  passes, and how much of that margin the hull ate. That is genuinely unknown, and §7 measures
  it.

**A second thing this design does not claim.** Replaying a hull-run trajectory against the
vendor meshes answers *"what would `ValidateSolution` have said about **this** trajectory under
the vendor set"*. It does **not** answer *"what trajectory the cell would have produced under
the vendor set"*: the start states come from physics that loads the same collision geometry, and
Pilz's own generation performs a self-collision check against it. **The stronger claim is not
made anywhere in this campaign** and `ANALYSIS.md` may not make it.

### 1.2 Not in scope, deliberately

- **The physical arm.** The layout is `PROVISIONAL` and the physical scan is Phase 3 (charter
  §8). Nothing here transfers to the building.
- **The work-piece.** Nothing in this tree adds the carried part to the planning scene as an
  `AttachedCollisionObject` — `grep -rn "attachObject\|AttachedCollisionObject"` over
  `workspace/src` outside `external/` reaches two comments and no call, read on 2026-09-04. So
  the part is invisible to the planner **and to this campaign**, and a collision involving the
  carried part is neither measured nor excluded here.
- **Self-collision.** ADR-0028's audit covered arm-internal pairs and this campaign measures
  **link-to-environment** distances only. The generated SRDF's `disable_collisions` set — **52**
  pairs in the expanded SRDF for `arm_1`, counted on 2026-09-04 — governs the self-collision
  question and is recorded, not evaluated.
- **Re-deriving ADR-0028's geometry audit.** §2.5.
- **Whether any of ADR-0027's levers is right.** §0.
- **A rate.** Every count is a count over the trajectories that were captured, on one machine,
  on one image, at one commit.
- **Determinism.** Scenarios in this cell are not reproducible; the physics solver is unseeded
  ([`../../architecture/cross-cutting-testing.md`](../../architecture/cross-cutting-testing.md)).
  Every captured set is a sample. The **compute** stage, by contrast, is a pure function of what
  was captured and of two committed mesh sets — REPRO1 in §7.6 is what holds that.

---

## 2. The mechanism as implemented, and the arithmetic reproduced before any trial

Everything in this section was read from source or from the generated tree at `HEAD` on
2026-09-04 and computed before this file was committed.

### 2.0 What checks the environment, and when

- **Pilz does not search the scene.** The generated pipeline file declares
  `pilz_industrial_motion_planner/CommandPlanner` with response adapters
  `default_planning_response_adapters/ValidateSolution` then
  `default_planning_response_adapters/DisplayMotionPath`; the OMPL block declares
  `AddTimeOptimalParameterization`, then the same two, in that order
  (`workspace/src/cite_generated/moveit/cell_a_arm_1_planning_pipelines.yaml`, read at `HEAD`;
  identical in the `arm_2` and `arm_3` files, checked by reading all three).
- **`ValidateSolution` checks waypoints.** It calls `PlanningScene::isPathValid`, which tests
  each waypoint of the finished trajectory and interpolates nothing between them.
- **The spacing is 0.1 s and it is a C++ default argument** —
  `TrajectoryGenerator::generate(scene, req, res, double sampling_time = 0.1)`, called with
  three arguments by `PlanningContextBase::solve` — **with no ROS parameter**, so it cannot be
  stated in L0 and cannot be set from a generated file. **It is already asserted by a test in
  this tree**, `cite_skills/test/test_planning_pipeline.py:686` measures the `time_from_start`
  spacing of a PTP trajectory against `SAMPLING_TIME_S = 0.1` and fails if a MoveIt release
  changes it. **This campaign does not re-run that test as its evidence**; it records the
  spacing it measures per captured trajectory and reports any that disagrees.
- **The adapter chain breaks on the first failure.** `planning_pipeline.cpp:333-350` (MoveIt
  2.12.4): the response adapters run in order and `if (!res.error_code)` returns false. So a
  trajectory that reaches `DisplayMotionPath` is exactly a trajectory `ValidateSolution`
  accepted, and — because neither adapter modifies the trajectory — **the published waypoint set
  is byte-for-byte the waypoint set that was validated.** That equality is the soundness
  argument for the whole capture design and it is registered here rather than assumed.

### 2.1 The capture door, and what it costs

`DisplayMotionPath::initialize` creates
`node->create_publisher<moveit_msgs::msg::DisplayTrajectory>(params.display_path_topic,
rclcpp::SystemDefaultsQoS())` and `adapt()` publishes one message per successful pipeline run
(`moveit_ros/planning/planning_response_adapter_plugins/src/display_motion_path.cpp`, MoveIt
2.12.4, read on 2026-09-04). `display_path_topic` defaults to **`display_planned_path`**
(`/opt/ros/jazzy/include/moveit_ros_planning/default_response_adapter_parameters.hpp:73`, read
in the image on 2026-09-04) and **the generated pipeline files override it nowhere**, checked by
reading all three.

Three consequences, all registered:

1. **The topic is namespaced with the node.** Each arm's `move_group` runs in
   `/cite/cell_a/arm_N` (`cite_bringup/launch/simulation.launch.py`, `_motion_planning`), and a
   relative topic name resolves into the node's namespace, so the expected name is
   `/cite/cell_a/arm_N/display_planned_path`. **This is a resolution argument and not a reading
   off a running cell** — no cell was brought up to write this file. The harness **resolves the
   name from the running graph** and records what it found; a mismatch is reported, not
   corrected silently.
2. **`SystemDefaultsQoS` resolves in the RMW, not in MoveIt** — history, depth, reliability,
   durability and liveliness are all `*_SYSTEM_DEFAULT`. It is **not latched**, so a message
   published before a subscription has matched reaches nobody (CLAUDE.md §10). V4 requires a
   matched publisher and records the publisher's resolved endpoint QoS per block, and **rule C
   is what stops an empty capture reading as a quiet cell**.
3. **The count is independently checkable from the log.** `PlanningPipeline::generatePlan` logs
   `Calling PlanningResponseAdapter '<description>'` at INFO for every adapter it reaches
   (`planning_pipeline.cpp:336-337`), and `PlanningResponseAdapter '<description>' failed with
   error code <code>` at ERROR for one that refuses (`:343-345`). So the launch log carries a
   second, independent count of both **published** trajectories and **refusals**. I5 and I6.

### 2.2 The planning scene, read from the generator rather than taken on trust

Read from `workspace/src/cite_generated/moveit/cell_a_planning_scene.yaml` at `HEAD` on
2026-09-04 by parsing the file. **Twelve** collision objects, every one a `box`, every one with
`rpy_rad: [0, 0, 0]`, all in frame `cite_world`:

| type | count | dimensions (m) |
|---|---|---|
| `break_beam` | 4 | 0.04 × 0.04 × 0.12 |
| `belt_1200x400` | 3 | 1.2 × 0.4 × 0.6 |
| `pedestal_600` | 3 | 0.3 × 0.3 × 0.6 |
| `work_table_600` | 2 | 0.6 × 0.6 × 0.6 |

**The smallest dimension of any object in the scene is 0.040 m**, computed as the minimum over
all twelve objects' three dimensions. That single number is where every size in §7.0 comes from.

`pose` is the pose of the primitive's **centre** — the generator has already applied the
half-height offset from the L0 body's stand-on point, and the file says so in its own header.
**The campaign nevertheless uses the object poses read back off the running `move_group`**
(I4), not these, so no frame convention of this file has to be trusted; the file is the
cross-check and a disagreement is reported.

### 2.3 The two geometry sets, and the one relation between them that is not a measurement

The shipped description binds collision geometry through one xacro argument:
`collision_mesh_path="file://$(find cite_description)/meshes/collision/xarm5/convex_hull"`
(`cite_generated/description/cell_a_arm_1.urdf.xacro:28`). The vendor macro falls back to its
own `mesh_path` when that argument is empty
(`xarm_description/urdf/common/common.link.xacro:62`), **and the relative path below the root is
unchanged either way** — which is the property that makes an offline substitution exact.

Expanding the shipped description with `xacro` on 2026-09-04 gives, for `arm_1`:

| quantity | value |
|---|---|
| links | **16** |
| links carrying a `<collision>` element | **13** |
| links carrying none | **3** — `arm_1_mount`, `arm_1_link_eef`, `arm_1_link_tcp` |
| `<collision>` elements | **13**, each exactly one `<mesh>`, each with `origin xyz="0 0 0" rpy="0 0 0"` |
| collision mesh roots | all 13 under `cite_description/meshes/collision/xarm5/convex_hull` |

All **13** relative paths resolve under the pinned vendor root
`workspace/src/external/xarm_ros2/xarm_description/meshes/` — checked file by file on
2026-09-04. Triangle counts, read from the STL headers:

| set | triangles over the 13 meshes |
|---|---|
| shipped hulls, `assets/meshes/collision/xarm5/convex_hull` | **9,992** |
| vendor, `xarm_description/meshes` at the pinned SHA | **98,552** |

**The relation that is a theorem and not a measurement.** `cite_tools.meshes.convex_hull`
derives each hull from its source mesh's own vertices and re-triangulates facets by fanning from
a vertex of that facet, so **the hull's vertex set is a subset of the source's** and the hull
contains the source. Two consequences are used below and **neither is imported from any record**:

- **`d_hull <= d_vendor` at every configuration, link and object.** A superset cannot be further
  away. So a difference in the other direction contradicts the derivation, not the cell — rule E
  in §7.2.
- **The axis-aligned bounds and the origin radius of a hull equal its source's exactly**, because
  an extremum of a linear functional over a point set is attained at an extreme point, and every
  extreme point is a hull vertex. **Verified numerically on the committed files on 2026-09-04**:
  over all 13 pairs the largest AABB-corner difference is **0.000e+00 m** and the largest
  difference in the maximum vertex radius about the link origin is **0.000e+00 m**. The largest
  such radius is **0.392454 m**, on `link3`.

  That verification is this campaign's own arithmetic on committed files. **It is not, and must
  not be reported as, a reproduction of ADR-0028's support-function result** (§2.5): it is a
  statement about two axes and one radius, not about every direction.

  It is what makes the broad phase of §4.3 **symmetric**: a bound computed from the enclosing
  sphere censors the same pairs under both geometries, so censoring can never manufacture a
  difference.

### 2.4 The waypoint arithmetic for #17, computed here before any trial

Every arm joint of the shipped description declares `velocity="3.14"`
(`xarm_description/urdf/xarm5/xarm5.urdf.xacro`, expanded and read on 2026-09-04: all five of
`arm_1_joint1`..`joint5` are `type="revolute"` with `velocity` 3.14). The generated joint-limits
file declares `default_velocity_scaling_factor: 0.35` and
`default_acceleration_scaling_factor: 0.35`
(`cell_a_arm_1_joint_limits.yaml:44-45`), and **no caller in this tree sets a non-zero
`velocity_scaling`**: `grep -rn velocity_scaling workspace/src tests` on 2026-09-04 reaches the
action definition, the skill server's own `apply_scaling`, one unit test and one launch test,
and no producer of a `MoveTo` goal. So:

| quantity | derivation | value |
|---|---|---|
| fastest joint speed a shipped motion can plan | `3.14 * 0.35` | **1.099 rad/s** |
| joint travel in one 0.1 s waypoint interval | `1.099 * 0.1` | **0.1099 rad** |
| tool-point step per metre of moment arm | `2 sin(0.1099/2)` — the chord, not the arc | **0.109845 m/m** |
| moment arm at which one joint alone produces a **0.040 m** step | `0.040 / 0.109845` | **0.36415 m** |
| moment arm at which one joint alone produces a **0.020 m** step | `0.020 / 0.109845` | **0.18208 m** |
| tool speed at which a 0.1 s step equals 0.040 m | `0.040 / 0.1` | **0.400 m/s** |

The chord and the arc differ here by **0.05 %** (`0.1099 / 0.109845 = 1.00050`), and the chord is
the quantity a Cartesian step is, so the chord is what is registered.

**Two things this arithmetic is not.** It is a **single-joint** statement: five joints move at
once and the tool step is their vector sum, so 0.36415 m is neither an upper nor a lower bound on
what the cell produces — it is the scale at which the question becomes live. And **it does not
predict a magnitude**: the tool-point moment arm at the poses this cell reaches is not
established anywhere in this file, and #17's own `0.077 m per step at 0.7 m reach` rests on a
reach figure this campaign neither verifies nor imports (§2.5). **STEP1 measures the step. It is
not compared against any prior figure.**

### 2.5 Figures named in the sources that this campaign does NOT import

Rule H's list, written out so that it cannot be reached for by accident. **None of the
following is re-derived here, used as a threshold, differenced against anything, or reported as
this campaign's data:**

| figure | whose it is |
|---|---|
| the hull's support function exceeding its source's by +0.000000 mm over 20,000 random directions | ADR-0028's safety audit of 2026-09-01 |
| the per-link concavity depths (`link2`, `link3`, `link_base`, `link4`, gripper base, fingers) | the same audit |
| hull-to-scene clearance equal to the vendor's to 0.00 mm at the SRDF's two named group states | the same audit |
| the pad aperture and relief-shoulder figures | ADR-0028's geometry audit of 2026-08-31 |
| roughly 0.077 m of tool travel per step at a 0.7 m reach | #17's prose, and the generated pipeline file's comment |
| every figure in every campaign directory | those campaigns |

**ADR-0028's audit script was never committed.** `grep -rln "support function\|support_function\|
concavity"` over the tree on 2026-09-04 reaches CLAUDE.md, `docs/`, and one comment in
`tools/tests/test_meshes.py`, and no instrument. So there is **no audit code to extend and
nothing to inherit**, and the figures above exist as prose only. This campaign builds its own
instrument from scratch (§4) and **does not re-derive theirs**.

---

## 3. The captures, and rule T over them

**The captures are named in words**, and every other family carries a prefix of its own: rules
are bare letters (**C**, **E**, **K**, **M**, **T**, **N**, **R**, **H**, **D**, **G**),
instruments **I**, validity rules **V**, predictions **PRED**, blocks **B**, and verdicts are
whole words. **No bare letter used as a rule here collides with a layer name (L0–L5) or a
principle (P1–P10)** — that discipline is the 2026-09-02 campaign's pre-freeze review's, kept
because the 2026-09-04 following-error campaign had to renumber two families to get it.

| capture | what it is | why it is here |
|---|---|---|
| **BRINGUP** | `./scripts/scenario bringup` | the smallest motion the cell ships: one `MoveTo`, asserted by a blocking CI gate |
| **PICKPLACE** | `./scripts/scenario pick_and_place` | one arm's full production cycle, including the approach to `table_pick` where the gripper comes closest to furniture |
| **LINE** | `./scripts/scenario continuous_line` | three arms, the belts, the beams and L4; the longest and most varied trajectory set the cell produces |

> **Rule T — inherited verbatim from the 2026-09-04 following-error campaign's §3, which took it
> from the 2026-09-03 campaign's, which took it from the 2026-09-02 campaign's.** The captures
> are not each other's evidence. A clean result in one says nothing about any other, **every
> verdict is stated per capture**, and an inconclusive one belongs in the verdict rather than in
> a footnote.

> **A scenario's own verdict does not gate its capture, and this is registered before any run.**
> `continuous_line` has failed its cycle in four of the nineteen CI runs that have driven it
> (CLAUDE.md §2 keeps that tally; it is cited, not used as data). **Every trajectory captured
> before a scenario failed is still a trajectory this cell produced**, and it is admitted. The
> scenario's verdict line and its exit status travel on the block record, and `ANALYSIS.md`
> states, per capture, how many of its runs passed. **Admitting only the runs that passed would
> select the trajectories for success**, which is the opposite of what #49 asks about.

---

## 4. Instruments, registered before the first trial

The campaign has **two stages**, and separating them is deliberate: the capture stage runs a
cell and is not reproducible; the compute stage runs no cell and is (REPRO1).

### 4.1 The capture stage

| # | Quantity | Instrument |
|---|---|---|
| **I1** | the trajectory a skill actually planned, as validated | `moveit_msgs/DisplayTrajectory` on each arm's `display_planned_path`, resolved from the running graph (§2.1). Recorded whole: `model_id`, `trajectory_start.joint_state`, and `trajectory[0].joint_trajectory` with its joint names, positions and `time_from_start` |
| **I2** | which pipeline produced it | **two readings, and neither is taken alone.** (a) the interior `time_from_start` spacing — Pilz emits a uniform 0.1 s (§2.0); (b) the skill server's own WARN `planner fallback: <A> found no path, retrying with <B>` (`skill_server.cpp:1798-1803`), scraped from the block log with its timestamp. **A disagreement between (a) and (b) is reported and is not resolved by choosing** |
| **I3** | the description that actually ran | the `robot_description` read back off the running node: each arm's `<ros2_control>` `plugin` element, and the collision-mesh references, which must be **13** under `cite_description/meshes/collision/xarm5/convex_hull`. V2 and V3 |
| **I4** | the scene the planner actually held | `GetPlanningScene` on each arm's `move_group` with `WORLD_OBJECT_GEOMETRY \| TRANSFORMS \| ALLOWED_COLLISION_MATRIX \| LINK_PADDING_AND_SCALING`, taken once per arm per block. **The object poses used by the compute stage are these**, in the frame `move_group` reports, not the generated file's. **`link_padding` and `link_scale` are recorded**: the compute stage is unpadded, so a non-zero padding makes MoveIt's verdict and this campaign's distance two different quantities, and that is reported rather than reconciled |
| **I5** | how many trajectories the pipeline published | the count of `Calling PlanningResponseAdapter 'DisplayMotionPath'` lines in the block log (§2.1). Spent by rule C against the number of messages actually received |
| **I6** | how many trajectories `ValidateSolution` refused | the count of `PlanningResponseAdapter 'ValidateSolution' failed with error code <code>` lines, with the code. REFUSE1 |
| **I7** | the code, the model and the vendor tree that ran | `git rev-parse HEAD`, `git status --porcelain`, `git diff c38a42c..HEAD` over the seven watched paths, and `git -C workspace/src/external/xarm_ros2 rev-parse HEAD` — **all taken at both ends of every block** — plus the running cell's `MODEL_HASH` |
| **I8** | the host's state | the one-, five- and fifteen-minute load averages from `/proc/loadavg`, at both ends of every block, read **inside** the container (§9) |
| **I9** | the scenario's own verdict | the `Scenario 'X' …` line `scripts/scenario` prints, and the process exit status, per run. **The step conclusion is never used**; the log line is the instrument |
| **I10** | the environment the block ran in | every `CITE_*` variable in the block's environment, verbatim, plus `ROS_DOMAIN_ID`, `GZ_PARTITION` and `RMW_IMPLEMENTATION` |

### 4.2 The forward kinematics, and why there are two of them

| # | Quantity | Instrument |
|---|---|---|
| **I11** | link poses at a configuration — **primary** | host-side forward kinematics computed from the expanded URDF's joint origins, axes and types, in the model's own root frame. Pure `numpy`; no ROS, no simulator, no clock |
| **I12** | link poses at a configuration — **independent check** | `GetPositionFK` on a `move_group` started from the same generated files with **no simulator and no controllers** — the shape `cite_skills/test/test_planning_pipeline.py:207-258` already launches — over a registered random sample of captured waypoints. FK1 in §7.6 |

**Why two.** I11 is a reimplementation, and a reimplementation that nothing checks is where a
silently wrong frame convention lives. I12 is MoveIt's own `RobotModel`, which is what the cell
used. **They are not averaged and neither corrects the other**: FK1 states whether they agree,
and a disagreement is the result (rule D).

**I12's rig also answers the sign.** With the scene applied exactly as that test applies it,
`GetStateValidity` returns `valid` plus contacts at each sampled waypoint. The compute stage's
distance must be `> 0` wherever `valid` is true after removing contacts between two robot links
— the same intersection with the scene's object ids that test already performs
(`test_planning_pipeline.py:418`). VALID1 in §7.6 is the verdict.

### 4.3 The distance computation, and why it is host-side

**Registered choice: a host-side computation over the two committed STL sets and the scene's
box primitives.** The alternatives were weighed and both are refused, with reasons that are
facts about this image and this tree rather than preferences:

- **A `moveit_core`-linked probe in Python is not available.** `moveit_py` is not installed:
  `python3 -c "import moveit"` inside the image on 2026-09-04 raises `ModuleNotFoundError`, and
  `dpkg -l | grep -c moveit-py` reads **0**.
- **A `moveit_core`-linked probe in C++ would be a new package.** Nothing in the tree issues a
  `DistanceRequest` — `grep -rn "DistanceRequest\|distanceRobot\|distanceWorld"` over
  `workspace/src`, `tools/` and `tests/` outside `external/` returns nothing on 2026-09-04 — so
  it would have to be written, and §0 confines this campaign's code to `harness/`.
- **`GetStateValidity` returns a boolean and contacts, not a distance**, so the one probe the
  tree does have cannot answer Q1 at all. It is kept as the sign check (VALID1) and nothing more.
- **The host-side computation is a pure function of committed files**, which is what makes
  REPRO1 possible and what lets a reviewer re-run it without a cell.

**What it computes.** For a configuration `q`, I11 places each of the 13 collision meshes; each
mesh is a triangle soup; each scene object is a box with a pose. The distance for a (link,
object) pair is the minimum over the link's triangles of the exact distance between that
triangle and that box — **two convex sets**, so the distance is well defined and computable
without approximation. Below zero is penetration depth, reported as `0` with a penetration flag
rather than as a signed depth, because a penetration depth between a soup and a box is not a
single well-defined quantity.

**Broad phase, and its censoring, registered before any number.** A pair is evaluated exactly
only when the bound from the link's enclosing sphere — centre at the link origin, radius the
maximum vertex radius, **identical under both geometries** by §2.3 — puts it within the
**censoring cutoff of 0.500 m**. Everything beyond is recorded as `> 0.500 m` and enters no
distribution. **Rule M** in §7.7 is what stops a censored value being read as a number.

---

## 5. What is varied, and what is held fixed

### 5.1 What varies

**Two things.** The **capture** (§3), and the **geometry set** — and the second varies only
inside the compute stage, over one captured trajectory set, never by running the cell twice.

### 5.2 Why the geometry is not flipped in `model/`

Measuring both geometries by setting `description.collision.select` to `vendor_meshes` and
regenerating would edit `model/` and `workspace/src/cite_generated/`, **both watched by V1**,
and would move `MODEL_HASH`. The 2026-09-02 scenario-ceilings campaign registered the same
constraint in its own §5 — *"flipping it would edit `model/`"* — and measured the shipped
configuration, attributing nothing to that lever.

**This campaign does not need the flip**, and that is the design's whole point: the collision
root is the only thing that differs between the two sets, the relative paths beneath it are
identical (§2.3), and the substitution therefore happens **inside the compute stage** by reading
a different file at the same relative path. **`v1_clean` holds throughout, and no artifact this
repository ships is touched.**

### 5.3 Held fixed unless named

| Quantity | Value | Where it comes from |
|---|---|---|
| Tree | `c38a42c`, clean over the seven paths | V1 |
| Collision geometry the **cell** runs | **`convex_hull`**, the shipped selection, **unflipped** | §5.2, V3 |
| Vendor geometry | the pinned SHA's meshes, read but never loaded by a cell | preamble, V1 |
| Zone | `cell_a`, three arms, headless | the scenarios' own launch |
| Entry point | `./scripts/scenario <name>`, **no `--teardown-advisory`** | the interactive, strict question |
| Velocity / acceleration scaling | whatever the shipped callers apply — **no goal in this tree sets a non-zero value** (§2.4) | recorded per trajectory from the waypoints, never assumed |
| Pairing | **none.** `./scripts/sim --pair` is not used; the model declares `sides: single` | §8 |
| Concurrency | **one cell at a time.** No second scenario, no build, no other agent's container | V10, V11 |
| `CITE_PHYSICS_SEED`, `CITE_LINE_WORKPIECES` | whatever the environment carries, **recorded per block and never assumed** | I10 |
| Container image | one image for the whole campaign, its digest recorded | §9 |

### 5.4 What a captured trajectory is, and what a waypoint is

- **A captured trajectory** is one `DisplayTrajectory` message received on one arm's
  `display_planned_path` during one scenario run, with its receive order, its arm, its capture,
  its block and its run index.
- **A waypoint** is one entry of `trajectory[0].joint_trajectory.points`, with its
  `time_from_start`.
- **The configuration at a waypoint** is that point's `positions` for the joints named in the
  message, **completed** by `trajectory_start.joint_state` for every other joint in the model —
  which is how the gripper's four moving links get a configuration at all, since the arm group
  excludes the drive joint (the expanded SRDF's `arm_1_xarm5` group runs
  `arm_1_world_joint` … `arm_1_joint_tcp` and contains no gripper joint; the gripper is its own
  group). **That the gripper does not move during an arm trajectory is an assumption of the
  completion, and it is registered as one**: §7.4's GRIP1 reports the same distances recomputed
  at both ends of the drive joint's declared range (`0` to `0.85` rad, read from the expanded
  URDF), so the sensitivity is measured rather than argued.

---

## 6. Design, sample size and order

**A block is one container session.** Within a block the three captures run **in a fixed order**
— BRINGUP, PICKPLACE, LINE — with **one recorder alive across all three**, so no capture owns a
recorder start-up and every capture is sampled by the same instrument in the same session.

| block | container sessions | runs per block | recorder |
|---|---|---|---|
| B1, B2, B3 | 1 each | BRINGUP ×1, PICKPLACE ×1, LINE ×1 | one, alive across all three |

**Nine scenario runs over three blocks.** The number of *trajectories* and *waypoints* is not a
design parameter — it is whatever the cell produced — and V8 governs reading it.

**Why three blocks.** Two is the minimum that can show a block difference at all; three lets V6
see one without the campaign resting on a single session.

**Why the recorder and the scenario share a container.** DDS discovery does not cross Docker's
default bridge reliably
([`../../operations/troubleshooting.md`](../../operations/troubleshooting.md)), so a recorder in
a second container would produce a partial graph — and a partial graph here is an **empty
capture**, which is exactly the failure rule C exists to catch. `./scripts/scenario` run from
inside the container runs there natively (`scripts/_lib.sh:963`, `in_container` returns early),
so one session holds both.

**The block index and the run index travel on every record**, and so does the receive order
within a run. V6 is what spends them.

**A block that aborts early is reported with the n it reached**, and no capture is topped up
(V8) — carrying the closing `v1_clean` reading V1 registers for that case.

---

## 7. Thresholds — the decision rules

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.0 The sizes, and where each comes from

Every one stands on **a dimension of the generated planning scene, a property of the derivation,
a numerical identity, or an inherited rule** — never on campaign data, never on a figure from
§2.5's list. **Where a size is a judgement rather than a derivation, its row says so.**

| Metric | Size | Why this size |
|---|---|---|
| `CLOSE_BAND`, the close-approach band | **0.040 m** | **the smallest dimension of any object in the generated planning scene** (§2.2). An arm closer to a body than the thinnest body in the cell is thick is near it in the only unit the cell itself declares |
| `STEP_HIGH`, the step that could traverse the thinnest object | **0.040 m** | the same dimension. A consecutive-waypoint step below it cannot carry the tool point clear through a beam housing's thin axis with both endpoints outside |
| `STEP_MID`, the comparable band's floor | **0.020 m** | half `STEP_HIGH`. **The factor of two is a judgement and is recorded as one**: it is the margin at which "far below" stops being an honest description |
| `DIFF_FLOOR`, the numerical floor on a hull-versus-vendor difference | **1e-9 m** | the two sets share vertex coordinates exactly (§2.3), so a difference below this is double-precision arithmetic and not geometry. The same role V5's 1e-9 plays in the following-error campaign |
| `SUB_STEP`, the interpolation target | **0.002 m** of tool-point travel per sub-sample | one twentieth of the thinnest object's thickness. **The twentieth is a judgement, recorded as one**; what is not a judgement is that it is referred to the same declared 0.040 m |
| `SUB_CEILING`, the sub-sample ceiling | **200** sub-intervals per waypoint interval | a bound on the compute, not on the physics. **Every interval that hits it is counted and reported**, and its achieved sub-step is stated |
| `CENSOR`, the broad-phase cutoff | **0.500 m** | **12.5×** `CLOSE_BAND`, so nothing either question is about can be censored; and the bound it is applied to is identical under both geometries (§2.3), so censoring is symmetric. Rule M |
| FK agreement tolerance | **1e-6 m** and **1e-6 rad** | four orders of magnitude below `CLOSE_BAND`. **A judgement, recorded as one** |
| REPRO1's cross-interpreter tolerance | **1e-12 m** | the compute stage is deterministic within one interpreter; across two `numpy` versions a reduction order may differ, and 1e-12 m is six orders below `DIFF_FLOOR`'s own scale of interest. **A judgement, recorded as one** |
| rule C's trajectory floor | **2** waypoints | a trajectory with fewer has no interval, so it can contribute to neither STEP1 nor TUNNEL1 |
| rule C's instrument-loss ceiling | **20 %** of a capture's published trajectories | **a judgement, and recorded as one**, inherited in size and reasoning from the 2026-09-04 following-error campaign's rule L: above one in five lost, the surviving set is a sample of what the recorder happened to keep |
| V7's load flag | load average **4.0** on 16 cores | **inherited** from the 2026-09-02 scenario-ceilings campaign. It **flags and never excludes** |

### 7.1 LIVE1 — a measured capture, or a measured nothing

**This is the campaign's central hazard.** A subscription that never matched, a topic that does
not exist, a name resolved into the wrong namespace and a scenario that failed before it planned
anything all produce **the same empty set** — and an empty set reads as "no trajectory came close
to anything", which is the reassuring answer.

> **Rule C — the capture rule. No distance claim is admissible for a capture that does not
> satisfy it, and it is checked per capture per block.**
> - **C-i — the door was open.** The subscription reported at least one matched publisher on
>   each arm's `display_planned_path` **before** the scenario process was started, or, where the
>   topic did not exist yet, within the harness's own ceiling after it appeared; the matched
>   publisher count and the resolved endpoint QoS are recorded (V4).
> - **C-ii — nothing was dropped.** The number of `DisplayTrajectory` messages received equals
>   I5's count of `Calling PlanningResponseAdapter 'DisplayMotionPath'` lines in the same block
>   log. **Where the per-arm attribution of a log line cannot be resolved from the launch
>   process prefix, the equality is stated over the block total and the ANALYSIS says so.**
> - **C-iii — the trajectory is usable.** At least **2** waypoints; `time_from_start` strictly
>   increasing; every point's `positions` the same length as the message's joint-name list; every
>   named joint present in the expanded description.
> - **C-iv — the configuration is complete.** Every joint of the model is either named in the
>   trajectory or present in `trajectory_start.joint_state`; a model joint in neither makes the
>   trajectory inadmissible rather than silently defaulted to zero.
>
> A trajectory failing any clause is an **INSTRUMENT LOSS**: excluded from every distribution,
> **counted and reported separately from every other exclusion**, and **never counted as a
> trajectory that stayed clear**. If more than **20 %** of a capture's published trajectories are
> instrument losses, that capture's DELTA1, MARGIN1, STEP1 and TUNNEL1 are **NOT ADMISSIBLE** and
> rule N applies to it.

> **LIVE1 — ADMISSIBLE / NOT ADMISSIBLE, stated per capture**, with the trajectory count, the
> waypoint count, the loss count by clause, and the received-versus-logged counts side by side.
> **`ANALYSIS.md` states LIVE1 before it states any other verdict**, per capture, so that no
> clearance can be read without the instrument's own report beside it.

### 7.2 DELTA1 and FLIP1 — what the hull changed

Report, per capture, per link and per object: the distribution of `d_hull` and of
`d_vendor - d_hull` over admissible waypoints (min, median, p95, p99, max), the maximum with the
trajectory, waypoint, link and object that produced it, and the count of censored pairs.

> **DELTA1 — IDENTICAL / SMALLER / DISAGREEMENT / NOT ADMISSIBLE, stated per capture.**
> **IDENTICAL** iff `max(d_vendor - d_hull) <= DIFF_FLOOR` over every evaluated (waypoint, link,
> object). **SMALLER** iff it exceeds `DIFF_FLOOR` — reported in full, with the distribution, the
> maximum, and the minimum distance at that waypoint under each set. **NOT ADMISSIBLE** under
> rule C.

> **Rule E — one direction is a theorem, so a measurement in it falsifies the instrument.**
> `d_hull <= d_vendor` follows from containment (§2.3). If any evaluated triple has
> `d_hull > d_vendor + DIFF_FLOOR`, DELTA1 is **DISAGREEMENT**: it is reported with both numbers
> and the whole trace, **nothing is re-run**, **nothing is edited**, and **the campaign does not
> attribute it** — the mesh reader, the hull provenance, the transform, the triangle-box routine
> and the broad phase are listed as candidates without choosing. It is stated in `ANALYSIS.md`'s
> verdict line, because it is a result about the instrument and not a procedural exception.
> This is rule D applied to the one comparison whose answer is known in advance.

> **FLIP1 — NONE / OBSERVED, stated per capture, and NONE evidences nothing.** A flip is a
> waypoint in contact under one set and clear under the other. **NONE is guaranteed by
> construction** (§1.1): the capture is conditioned on acceptance under the hull set, and
> containment carries that to the vendor set. **Registered before any trial: a NONE verdict is
> reported in the rule-N shape and may not be read as evidence that either geometry is safe, that
> the hull changed nothing, or that #49 is closed.** An OBSERVED verdict contradicts either
> containment or the conditioning, and is handled as a **DISAGREEMENT** under rule E — never as a
> finding about geometry.

### 7.3 MARGIN1 — how close this cell actually passes

Report, per capture: the minimum over all admissible waypoints of the minimum over (link,
object) distance, under each geometry; the count and the fraction of waypoints inside
`CLOSE_BAND`; and the identity of the closest approach — trajectory, waypoint, link, object,
arm, block.

> **MARGIN1 — TIGHT / CLEAR / NOT ADMISSIBLE, stated per capture.**
> **TIGHT** iff at least one admissible waypoint's minimum distance under the shipped hull set is
> `<= CLOSE_BAND` (0.040 m). **CLEAR** otherwise. **NOT ADMISSIBLE** under rule C.
> **A CLEAR verdict carries rule K with it**: it says these trajectories never came within the
> thinnest object's thickness of anything, and it does **not** say the cell cannot.

### 7.4 STEP1, TUNNEL1 and GRIP1 — the gap between two checks

> **STEP1 — FAR BELOW / COMPARABLE / EXCEEDS, stated per capture and per pipeline.**
> The quantity is the tool-point Cartesian step between consecutive waypoints — the position of
> **`arm_N_link_tcp`**, which is the tip of the SRDF's `arm_N_xarm5` group and the `tip_link` the
> generated bring-up plan hands the skill server (`cell_a_plan.yaml:230`,
> `skill_server.cpp:559`).
> **EXCEEDS** iff the maximum step is `>= STEP_HIGH` (0.040 m). **COMPARABLE** iff it lies in
> `[STEP_MID, STEP_HIGH)`. **FAR BELOW** iff it is below `STEP_MID` (0.020 m).
> **Stated per pipeline because #17 is a statement about Pilz**: an OMPL trajectory is
> re-timed by `AddTimeOptimalParameterization` and its spacing is not Pilz's, so mixing the two
> would report a spacing nobody configured. I2 is the attribution and a trajectory whose two
> readings disagree is reported separately and enters neither.
> **Registered before any trial: FAR BELOW is the likely outcome and it is not a clearance.** It
> says these trajectories stepped that far and no further. It does **not** say that a motion
> exists in this cell that cannot step further, and rule K is stated beside it.

> **TUNNEL1 — NOT OBSERVED / OBSERVED / NOT ADMISSIBLE, stated per capture, per geometry.**
> Between each consecutive waypoint pair the configuration is interpolated **linearly in joint
> space**, which is what MoveIt itself would do — `RevoluteJointModel::interpolate` computes
> `from + (to - from) * t` for a non-continuous revolute joint (MoveIt 2.12.4,
> `revolute_joint_model.cpp:170`, read on 2026-09-04) and every arm joint here is
> `type="revolute"` (§2.4). The interval is subdivided until the tool-point sub-step is
> `<= SUB_STEP`, to a ceiling of `SUB_CEILING`.
> **OBSERVED** iff any sub-sample's minimum distance is `<= 0` while **both** bracketing
> waypoints are `> 0` — a body passing strictly between two checked configurations, which is
> exactly ADR-0027's residual, measured on the trajectories the cell produced.
> **NOT OBSERVED** otherwise, **with rule K attached**.
> **This is not a claim about the path the arm physically followed.** The controller tracks the
> same waypoints with its own lag under a first-order plant, so the executed path is neither the
> waypoint set nor this interpolation. What TUNNEL1 measures is what `ValidateSolution` did not
> look at.

> **GRIP1 — the gripper completion's sensitivity, reported and deciding nothing.** Every distance
> involving one of the four gripper finger and knuckle links is recomputed with the drive joint
> at **0** and at **0.85 rad**, the ends of its declared range, and the largest change is
> reported per capture. **It sets no verdict**: it exists so that §5.4's completion assumption is
> a measured sensitivity rather than an argument.

### 7.5 REFUSE1 — what the gate refused while we watched

> **REFUSE1 — a count, stated per capture, with no threshold.** The number of
> `PlanningResponseAdapter 'ValidateSolution' failed with error code <code>` lines in the block
> log (I6), by code, with the `planner fallback:` WARNs that follow them (I2b) and the L3
> outcomes around them.
> **Registered before any trial, and this is the honest part:** a refusal's **geometry is not
> measurable through this door** (§1.1), so REFUSE1 locates refusals in time and says nothing
> about how close anything was. **A count of zero does not establish that the hull set refuses
> nothing** — it says nothing was refused in these nine runs. **This campaign cannot answer
> whether the shipped hull set refuses a motion the vendor set would have accepted**, and §8
> names what would.

### 7.6 FK1, VALID1 and REPRO1 — the instrument checking itself

> **FK1 — AGREES / DISAGREES.** Over a random sample of **200** admissible waypoints drawn with
> a seed registered in the harness and recorded in `raw/`, every one of the 13 collision links'
> poses from I11 and from I12 agree to **1e-6 m** and **1e-6 rad**. **DISAGREES** is a result
> under rule D: it is reported with the worst case, nothing is re-run, and **no distance verdict
> in §7.2–§7.4 is stated for a capture whose FK1 disagrees** — it falls to rule N.

> **VALID1 — CONSISTENT / INCONSISTENT.** At the same sampled waypoints, `GetStateValidity` in
> I12's rig is called and its verdict is compared with the compute stage's sign, after removing
> contacts whose two bodies are both robot links. A waypoint the compute stage puts at `d > 0`
> against every object must come back valid on the scene side. **INCONSISTENT is reported with
> the scene's recorded `link_padding` and `link_scale` beside it** (I4), because a non-zero
> padding is a sufficient explanation and the campaign states it rather than assuming it.

> **REPRO1 — REPRODUCED / NOT REPRODUCED.** The compute stage is run **twice in the same
> interpreter** and must produce **byte-identical** output; and **once more in a second
> interpreter with a different `numpy`** (§9 names both) and must agree to **1e-12 m**. A
> failure of either is reported and **no figure from that run is published as a measurement**.

### 7.7 The refusals that carry the campaign's honesty, and the predictions

> **Rule K — the region of interest, in the rule-W shape of the 2026-09-02 campaign, which took
> it from ADR-0051's rule S. Defined here, before anything was captured.**
> - **K-i — #49's region.** The hull-versus-vendor question is **exercised** by a capture only if
>   at least one admissible waypoint's minimum distance under the **vendor** set is
>   `<= CLOSE_BAND` (0.040 m). If none is, that capture **has not tested close-approach
>   clearance**: its DELTA1 is stated as *"not exercised; the closest approach was X m"*, and its
>   silence may **not** be read as a pass, as a clearance of the hull selection, as agreement
>   with ADR-0028's audit, or as evidence that #49 is closed.
> - **K-ii — #17's region.** The tunnelling question is **exercised** by a capture only if at
>   least one consecutive-waypoint pair has both a step `>= STEP_MID` (0.020 m) **and** a
>   bracketing minimum distance `<= CLOSE_BAND`. Moving fast far from everything tests nothing,
>   and creeping close to something tests nothing either; **the question needs both at once.** If
>   no pair has both, TUNNEL1 is stated as *"not exercised"* and **#17 stays open on this
>   campaign's evidence**, in those words.
>
> **If no capture exercises a region, the campaign has not tested that question at all**, and
> `ANALYSIS.md` says so in its verdict line rather than in a limitation paragraph.

> **Rule M — a censored distance is a bound, not a number.** Any pair beyond `CENSOR` is
> reported as `> 0.500 m` and enters no distribution, no minimum and no difference. Because the
> bound is identical under both geometries (§2.3), censoring cannot manufacture or hide a
> difference — but **a verdict computed over uncensored pairs only is a verdict about the near
> field**, and every such verdict is stated with its censored count beside it.

> **Rule N — a null is not a clearance. Inherited from the 2026-09-04 following-error campaign,
> whose own is in ADR-0051's rule-S shape.** Where a capture is NOT ADMISSIBLE under rule C, not
> exercised under rule K, or has a disagreeing FK1, the campaign's silence about it may **not**
> be read as agreement with any prior audit, as a clearance of either geometry, or as evidence
> that either gate behaves. The verdict names what was not tested, and the item stays open on
> that part.

> **Rule R — resolution. Inherited via the 2026-09-03 and 2026-09-04 campaigns.** For any metric
> whose spread **within one capture** exceeds that metric's minimum interesting size, a
> non-detection of a difference between captures is **INCONCLUSIVE for that metric — never "no
> difference"**.

> **Rule H — no cross-campaign differencing, and no importing. Inherited from the 2026-09-02
> scenario-ceilings campaign.** No measured figure from any other campaign, and no figure from
> §2.5's table, is differenced against, divided into, or described as an improvement on anything
> here. Prior figures may be **cited**; they may not be **used**.

> **Rule D — the arithmetic and the measurement are allowed to disagree, and the disagreement is
> the finding. Inherited from the 2026-09-03 campaign.** Where §2.4's arithmetic, §2.3's
> containment relation or §2.0's spacing is contradicted by the measurement, the contradiction is
> reported with both numbers, **nothing is re-run to resolve it**, **no constant anywhere in the
> tree is edited** (§0), and the campaign **does not attribute it**.

> **Rule G — what these numbers are properties of.** Every figure here is a property of **the
> trajectories these nine scenario runs produced**, on this host, at this commit, in this image,
> with this scene and this arm model — and of **nothing else**.
> - **It is not a property of the cell's reachable motions.** Another goal, another start state,
>   another physics roll produces another trajectory set.
> - **It is not evidence about hardware.** The layout is `PROVISIONAL`.
> - **A clean clearance here is not a safety case, and hulls may never be cited as margin.**
> **`ANALYSIS.md` states rule G beside every verdict in §7.2 – §7.5.**

**Predictions, so that this campaign can be wrong:**

| # | Prediction | Refuted by |
|---|---|---|
| **PRED1** | **DELTA1 = SMALLER on at least one capture**, with the difference confined to gripper links — fingers, knuckles or gripper base — against a table or a conveyor, because those are the only links whose concavity faces a large flat body during a pick. | IDENTICAL everywhere, or a difference on `link_base`, `link1`, `link2`, `link3`, `link4` or `link5`, either of which says the mechanism is not the one predicted |
| **PRED2** | **DELTA1 is never DISAGREEMENT.** Containment is a property of the derivation (§2.3), not of the cell. | any triple with `d_hull > d_vendor + DIFF_FLOOR` — which would falsify the instrument, not the geometry, and is the most informative failure this campaign could have |
| **PRED3** | **FLIP1 = NONE on every capture, and it evidences nothing** (§1.1, §7.2). Registered so that it cannot be read as a result. | any flip, which is a DISAGREEMENT under rule E |
| **PRED4** | **STEP1 = FAR BELOW on the Pilz trajectories of every capture.** Producing a 0.040 m step from one joint needs a moment arm of 0.36415 m at the shipped scaling (§2.4), and this arm carries the tool point closer to its own axes over most of a station approach. **The moment arm at the poses this cell reaches is not established in this file**, so this is the weakest prediction here and it is marked as such. | any capture whose Pilz maximum step reaches `STEP_MID` |
| **PRED5** | **TUNNEL1 = NOT OBSERVED on every capture and every geometry**, and **rule K-ii fires** — that is, the campaign predicts it will not have tested the question. Registered in advance because **a NOT OBSERVED that rule K refuses is the honest expected outcome**, and it must not be reported as a clearance of ADR-0027's residual. | any observed sub-sample contact between two clear waypoints — which would be the campaign's headline and a direct measurement of #17 |
| **PRED6** | **FK1 = AGREES and REPRO1 = REPRODUCED.** | either failing, in which case no distance verdict is published for the affected captures |

---

## 8. Explicitly not measured, recorded here rather than discovered later

- **Whether the hull set refuses a motion the vendor set would have accepted.** §1.1 and §7.5
  give the structural reason. **What would settle it, named and not designed here:** replanning
  the same requests offline against both geometries — which needs a way to read a **refused**
  trajectory, and MoveIt publishes none. Candidates are a `move_group` run with a modified
  response-adapter order, a probe that calls the planner directly, or a scene diff applied at
  plan time. **Which of those is right, whether any is worth building, and what record would own
  it are not decided here.**
- **The trajectory the cell would have produced under vendor geometry.** §1.1's second paragraph.
- **The carried work-piece.** §1.2. It is in no planning scene and in no distance computed here.
- **Self-collision.** §1.2, and ADR-0028's residual that the generated SRDF's matrix was computed
  against vendor geometry is untouched by this campaign.
- **The executed path.** §7.4's TUNNEL1 paragraph. Following error under this backend is a
  different campaign's subject and none of its figures enter here (rule H).
- **Pilz's sampling time as a lever.** It is a C++ default argument with no ROS parameter (§2.0),
  so **nothing in this campaign can change it, and nothing in this campaign proposes changing
  it** (§0).
- **Any zone but `cell_a`**, any arm model but the shipped `xarm5` with its gripper, any
  collision selection but the shipped one on the running cell, and any scene but the generated
  twelve objects. Each reopens every number in §2.
- **A rate of anything.** Every count is over the nine runs that ran.

---

## 9. The machine, named

Naming the machine is a decision clause of
[ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md) and the practice of every
campaign in this directory since. It matters here because the capture stage runs three scenarios
per block and a starved host times a scenario out with nothing broken.

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM |
| Free disk | **398 GiB** available on `/`, read on 2026-09-04 |
| Docker | **29.7.2** (build a7dcaa6); Docker Compose **v5.5.0** |
| Container image | **`cite-digital-twin:dev`**, digest `sha256:3a41d4e431b0a200c0b7a00d89bbcb44669f03d3aa754f56b89496a240fede7d`, Ubuntu **24.04.4 LTS**, ROS 2 **Jazzy** |
| Motion planning | MoveIt **2.12.4** — `ros-jazzy-moveit`, `ros-jazzy-moveit-core`, `ros-jazzy-moveit-ros-planning` and `ros-jazzy-pilz-industrial-motion-planner` all `2.12.4-1noble`, `dpkg -l` inside the image on 2026-09-04. **Named because three load-bearing claims here are claims about MoveIt's source**: the adapter chain's break-on-failure (§2.0), `DisplayMotionPath`'s topic and QoS (§2.1), and `RevoluteJointModel::interpolate`'s linearity (§7.4) |
| ROS↔Sim | `ros-jazzy-ros-gz-sim` **1.0.22**, `dpkg -l` on 2026-09-04 |
| Middleware | `rmw_fastrtps_cpp` **8.4.4** (`dpkg -l`). `RMW_IMPLEMENTATION` reads `rmw_fastrtps_cpp` inside `./scripts/enter dev`, set explicitly by `infra/docker/docker-compose.yml:58`. **Named because the capture door's QoS resolves there and not in MoveIt** (§2.1) |
| Compute stage interpreters | container `python3` with `numpy` **1.26.4** / `scipy` **1.11.4**, and the host `.venv/bin/python` with `numpy` **2.1.3** / `scipy` **1.14.1**, both read on 2026-09-04. **REPRO1 uses both** |
| Isolation | compose project **`cite-digital-twin-3319196271`** and **`ROS_DOMAIN_ID` 43** (`CITE_DOMAIN_BASE` 43), all three derived from this checkout by **sourcing `scripts/_lib.sh`** on 2026-09-04, not typed in |
| Allocation | the container is **not** CPU-limited by any condition here |

> **The simulator version is the one the *sourced* environment resolves, and that distinction is
> load-bearing.** Inside `./scripts/enter dev`, `which gz` resolves to
> `/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz` and `gz sim --versions` reports **8.11.0**, while
> `dpkg -l` shows the system `gz-sim8-cli` at **8.15.0-1~noble** — both read on this image on
> 2026-09-04. **The cell runs sourced**, so **8.11.0** is the simulator this campaign's capture
> stage runs against. The split is recorded in
> [`../../operations/troubleshooting.md`](../../operations/troubleshooting.md) and is not
> restated further (P1).

**Host load before the first trial, measured rather than claimed.** Read on 2026-09-04 at
14:16 local, on a host up 2 days 2 h 10 m:

```
0.01 0.11 0.95        (/proc/loadavg, 16 cores)
```

**This host was quiet at the time of writing, and that is a statement about that moment and not
about the campaign.** I8 records the load at both ends of every block and V7 is what spends it.

> **A container load reading comes from the container, and on this host that is the host's.**
> `/proc/loadavg` is not namespaced on native Linux and there is no `lxcfs` in the way. I8
> nevertheless names where each reading was taken, because the 2026-08-31 capacity campaign
> applied a validity rule that read a virtual machine's load rather than the host's.

---

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — `v1_clean`, inherited from the 2026-09-02 scenario-ceilings campaign via the 2026-09-03
  and 2026-09-04 ones, including its both-ends reading and the seven watched paths the last of
  them arrived at.** A block contributes only if **at BOTH ends of the block** — I7 is taken
  twice — `git diff c38a42c..HEAD -- model/ workspace/src/ tools/ tests/ scripts/ assets/
  external/` is **empty** and `git status --porcelain` shows **no dirt** in those seven paths.
  **`v1_clean` is the CONJUNCTION of the two readings**, and a block whose readings disagree is
  **discarded and reported** as an edit that landed mid-block. **`docs/measurements/` may advance
  while the campaign runs and nothing else may** — this campaign's own `criteria.md`, harness and
  raw all land on this branch, so `HEAD` necessarily advances and pinning it would discard every
  block. **The flag is computed where the block is taken and travels ON the record; the analyser
  drops any row without it.**
  **The vendor tree cannot be watched by diff and is pinned by SHA instead** (preamble): every
  block records `git -C workspace/src/external/xarm_ros2 rev-parse HEAD` at both ends and
  requires it to equal the SHA `external/cite.repos` pins. **A block that disagrees at either end
  is discarded and reported** — that tree is **one of the two geometries this campaign measures**,
  so a moved pin does not merely change the cell, it changes the comparison.
  **What an aborted block's rows carry:** the closing reading is taken at the abort, as the first
  act of the harness's abort path, so V1 and V8 do not contradict each other. Only where no
  closing reading could be taken do the rows carry `v1_clean = unknown`; those are dropped and
  **reported under V1 as a lost block, with the trajectory count they would have contributed**.
- **V2 — the geometry that actually ran.** Every block reads the description the rig publishes
  and counts collision-mesh references under
  `cite_description/meshes/collision/xarm5/convex_hull`: **13**, which is
  `find assets/meshes/collision/xarm5/convex_hull -name '*.stl' | wc -l` in this checkout on
  2026-09-04 and agrees with `git ls-files` over the same path. **The command is named because
  the meshes sit in three nested directories**, so counting that directory's own entries reads
  **3** and is a different quantity. A block that disagrees is **discarded and reported**. The running
  cell's `MODEL_HASH` is recorded with it.
- **V3 — the backend that actually ran.** Every block asserts, from the description read back off
  the running node, that each arm's `<ros2_control>` block names
  **`gz_ros2_control/GazeboSimSystem`**. A block that finds anything else is **discarded and
  reported**: the trajectories a differently-backed cell produces are a different sample.
- **V4 — the door was matched before it was needed, and the publisher's resolved QoS is recorded
  rather than assumed.** Per block, per arm, the `display_planned_path` subscription reports at
  least one matched publisher, and the publisher's resolved endpoint QoS from
  `get_publishers_info_by_topic` **travels on the block record**. **Treat the match as an event,
  never as a sleep** (CLAUDE.md §10). A block that ran a scenario without a matched subscription
  on an arm is reported, and that arm's trajectories for that block are an instrument loss under
  rule C-i rather than a silence.
- **V5 — the scene that actually planned.** I4's read-back is compared with
  `cite_generated/moveit/cell_a_planning_scene.yaml`: the object ids must match exactly, and each
  object's dimensions and pose must agree to **1e-9 m** after the frame the planner reports is
  accounted for. A disagreement is **reported and the block's distances are stated against the
  read-back**, never against the file. A block whose read-back is empty is **discarded**: a plan
  validated against an empty world is not the gate this campaign is about.
- **V6 — the block effect. Inherited.** Every session is a block and every run is indexed, and
  both travel on every record. If, for any metric, the difference between two blocks within one
  capture is larger than the difference between two captures, that metric's finding is
  **downgraded to INCONCLUSIVE** whatever any statistic says.
- **V7 — the load is recorded, and a loud host is reported rather than excluded. Inherited.**
  I8 at both ends of every block. **No block is discarded for load.** If any reading exceeds
  **4.0** on 16 cores, every trajectory in that block is flagged and every verdict it contributes
  to is reported with and without them; if a verdict differs, that verdict is INCONCLUSIVE under
  rule R.
- **V8 — n is what it was. Inherited.** Every count is reported over the trajectories that were
  actually captured, with a Wilson 95 % interval where it is a proportion. **No capture is topped
  up**, and a block that aborts early is reported with the n it reached.
- **V9 — no threshold moves. Inherited.** Nothing in this file changes once the first campaign
  trial has run. **A threshold discovered to be wrong is applied literally and recorded as
  wrong**, and the disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data
  already collected.
- **V10 — one writer at a time. Inherited.** **A concurrent agent editing a watched path
  mid-block flips `v1_clean` and silently discards the block.** So the campaign runs with **one
  writer in this checkout**, and the operator states in `ANALYSIS.md` whether that held. A
  campaign that loses blocks this way **reports the loss under V1 rather than re-running until it
  stops happening.**
- **V11 — no rebuild mid-campaign. Inherited.** `./scripts/build` runs once before the first
  block. If a rebuild becomes necessary it is a numbered deviation, and every block before it is
  reported separately from every block after it.
- **V12 — every Gazebo-transport process carries the partition (ADR-0042).** The scenarios start
  their own Gazebo processes through the shipped launch, which carries it; **the harness
  constructs no Gazebo environment of its own and makes no `gz` call at all** — the recorder is a
  ROS subscriber and the compute stage touches no transport. **An unpartitioned `gz model --list`
  reaches no world and exits 0**, so a block in which the harness had made a raw call would
  produce plausible silence rather than an error; such a block is **discarded and reported**. The
  guard under `tests/scenarios/guards/` enforces this for `tests/` and does not reach
  `docs/measurements/`, which is why the rule is stated here.
- **V13 — the cell announced readiness as an event.** The scenarios' own bring-up gates are the
  event; **nothing in the harness sleeps to sequence a bring-up** (P4). The recorder waits for a
  matched publisher (V4) and for nothing else.
- **V14 — the recorder is on the graph the cell is on.** Every block records `ROS_DOMAIN_ID` and
  compares it with the domain the generated plan resolves for the plant side. A block whose
  recorder was on another domain is **discarded and reported** — that is the failure that
  produces a complete, empty, plausible capture.
- **V15 — one clock for labels and none for decisions.** Captured records carry the recorder's
  receive time and the message's own header stamp, and both are labels. **No verdict in §7
  depends on a clock**: every decision quantity is a distance, a step or a count computed
  offline. A record with a non-monotonic stamp is reported and excludes nothing.

**One shakedown run per stage is permitted and is not data.** Before the first campaign trial,
the capture harness may be run **once** to prove it starts, matches its subscriptions and writes
a record, and the compute stage may be run **once** on that shakedown capture. Their output is
published under **`raw/shakedown/`**, is **excluded from every figure in §7**, and **may not be
used to set or adjust any threshold in this file** — every threshold above is derived from the
generated scene's own dimensions, from the derivation's containment property, or from a stated
judgement, and none of them needs a shakedown to exist. **If the shakedown reveals a defect, the
harness is fixed and this file is not touched.**

---

## 11. Honesty bounds fixed in advance

- **This campaign chooses nothing.** It moves no threshold, promotes no record, selects no
  geometry and proposes no fix for either item. §0.
- **It closes at most part of two items.** #49's margin question and #17's tunnelling question,
  and only under rules C and K. **#49's refusal question stays open and this campaign does not
  narrow it by one millimetre** (§1.1, §8).
- **A null is not a pass.** Rules C, E, K, M, N, R, H, D, G and T exist for exactly that, and all
  ten were written before anything was captured. **Rule K is the one that matters most here**:
  the likely outcome is that these trajectories never went fast near anything, and that is a fact
  about these trajectories and not about the cell.
- **Two verdicts are guaranteed before any data exists and are registered so that they cannot be
  cashed.** FLIP1 = NONE follows from the capture's conditioning plus containment; DELTA1's
  DISAGREEMENT direction is a theorem. Neither is evidence about geometry.
- **The measurement is allowed to contradict the arithmetic.** Rule D and rule E say what happens
  then, before the answer is known: the disagreement is the result, nothing is re-run and nothing
  is edited.
- **No figure from any prior campaign, from ADR-0028's prose or from #49's or #17's prose enters
  as this campaign's data.** §2.5 lists them by name. Every arithmetic result in §2 was computed
  here from source and says where it came from.
- **Nothing here is a safety case, and a hull may never be cited as margin.** Rule G.
- **Nothing here is a P2 result.** It samples the simulated cell. The layout is `PROVISIONAL` and
  the physical scan is Phase 3.
- **One machine, one image, one commit, one checkout, one zone, three scenarios, nine runs, three
  blocks — and it is not a rate.**
- **The three cited campaigns stay frozen.** Nothing in their directories is edited, re-run or
  re-analysed here.
- **Figures stay in this directory.** Nothing produced here is copied into ADR-0027, ADR-0028,
  `CLAUDE.md`, [`docs/open-work.md`](../../open-work.md), the generated comments or any layer
  document (P1). **Cite the directory.**
