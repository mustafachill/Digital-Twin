# Criteria — how close does this cell actually pass, and how far does it step between the only checks it gets?

**Written and committed before the first campaign trial ran, before the harness exists, and
before anything was captured.** [`../README.md`](../README.md)'s rule 1 freezes this file **once
the first trial has run**. Until then it is corrigible; after then, any interpretation that had
to change is recorded as a numbered deviation in `ANALYSIS.md`, applied to data already
collected — never by re-running until the definition suited.

> **AMENDED 2026-09-04, before the first trial, and this is what that permits.** No harness
> exists, `raw/` does not exist, and no trial has run, so rule 1 has not yet closed this file.
> A pre-freeze review found eight defects in the rules below — five of them rules that could
> not fire, or could only fire one way, which is the failure mode this whole directory exists
> to prevent. **A rule that cannot refuse is worse than no rule**, because its silence reads as
> a pass. What changed, and what deliberately did not, is §12; every figure the amendment rests
> on was re-derived from source here rather than taken from the review. **No threshold moved.**
> Once the first trial runs this file freezes as it then stands, and every later correction is a
> numbered deviation in `ANALYSIS.md`.

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
  (`planning_pipeline.cpp:332-351`, MoveIt 2.12.4, read on 2026-09-04 from the 2.12.4 tag).
  `ValidateSolution`
  stands **before** `DisplayMotionPath` in both generated pipelines
  (`cell_a_arm_1_planning_pipelines.yaml`), so **a refused trajectory is never published**. The
  campaign can count refusals (REFUSE1) and cannot measure their geometry.
- The captured set is therefore **conditioned on acceptance under the hull set**. Together with
  the containment relation of §2.3 that has a consequence, registered here before any number
  exists: **no captured waypoint can be in collision under either geometry — in MoveIt's
  verdict.**
  **That is not the same statement about this campaign's distance metric, and the difference is
  the correction of 2026-09-04.** §2.2.1 establishes a standing base-to-pedestal overlap of
  about 132 nm that MoveIt reports as valid and an exact triangle-to-box distance must report as
  contact. **MoveIt accepting a trajectory therefore does not imply that this campaign's
  distance is positive**, and any rule that assumed it did has been restated. What the
  conditioning does give, and it is narrower: **for every (link, object) pair MoveIt's own
  predicate separates, both geometries are separated too**, since a superset cannot be further
  away. So FLIP1 (§7.2) has **no reachable outcome in the direction that would flatter the
  hull**, and its one reachable direction is now a named finding rather than an impossibility —
  §7.2.
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
- **The adapter chain breaks on the first failure.** `planning_pipeline.cpp:332-351` (MoveIt
  2.12.4, read from the 2.12.4 tag on 2026-09-04): the response adapters run in order and
  `if (!res.error_code)` returns false. So a
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
3. **The count is independently checkable from the log, and so is the pipeline.**
   `PlanningPipeline::generatePlan` logs `Calling PlanningResponseAdapter '<description>'` at
   INFO for every adapter it reaches (`planning_pipeline.cpp:339`), and
   `PlanningResponseAdapter '<description>' failed with error code <code>` at ERROR for one that
   refuses (`:345-346`). So the launch log carries a second, independent count of both
   **published** trajectories and **refusals**. I5 and I6.
   **It also carries the planner.** The same function logs `Calling Planner '<description>'` at
   INFO before the planner runs (`:318`), and the two descriptions are distinct string literals:
   `"Pilz Industrial Motion Planner"`
   (`pilz_industrial_motion_planner.cpp:116-119`) and `"OMPL"`
   (`ompl_planner_manager.cpp:104-107`), both read from the 2.12.4 tag on 2026-09-04 and both
   present in the shipped libraries (`strings` over
   `/opt/ros/jazzy/lib/libmoveit_planning_pipeline.so.2.12.4` returns the format string
   `Calling Planner '%s'`, read in the image on 2026-09-04). **That is I2's reading (c), and it
   is the only one of the three that discriminates** — §4.1.
   **Note what the adapter lines do *not* discriminate.** `DisplayMotionPath::getDescription()`
   returns the literal `"DisplayMotionPath"` in both pipelines, because each pipeline loads its
   own instance of the same plugin, so I5's grep counts publications across both pipelines
   together and never says which produced one.

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

#### 2.2.1 Every arm is bolted to a body that is also a planning-scene object, and the two overlap

**This is the single most consequential fact in this file, it was found by the pre-freeze
review, and it is registered here because four of the rules below go vacuous without it.**

Read from the tree at `HEAD` on 2026-09-04, each figure computed here:

| quantity | value | where it was read |
|---|---|---|
| `pedestal_1` centre, dimensions | `(0, -0.3, 0.3)`, `0.3 x 0.3 x 0.6` | `cell_a_planning_scene.yaml`, parsed |
| `pedestal_1` top face | **z = 0.600** exactly | centre + half height |
| `arm_1_mount` in `cite_world` | `(0, -0.3, 0.6)`, yaw `1.570796327` | `cell_a_static_tf.yaml`, parsed |
| `arm_1_mount` to `arm_1_link_base` | fixed joint `arm_1_world_joint`, origin `0 0 0` | expanded URDF; the macro is `xarm_device_macro.xacro:88-92` |
| `link_base`'s collision origin | `0 0 0`, `0 0 0` | expanded URDF, all 13 (§2.3) |
| `link_base.stl` minimum vertex z | **-1.324005e-07 m** | read from the STL, **identical in both mesh sets** |
| vertex entries below z = 0 | **138 of 978** in the hull mesh, **546 of 7392** in the vendor mesh | the same read; 23 and 88 distinct coordinates |
| those vertices in the pedestal's XY footprint | **all of them** — the whole link's world AABB is `x` in `[-0.063, 0.063]`, `y` in `[-0.392, -0.237]`, inside `x` in `[-0.15, 0.15]`, `y` in `[-0.45, -0.15]` | computed from the mount transform |

**So the arm's base overlaps its own pedestal by about 132 nm, at every configuration, under
both geometries.** It is configuration-independent: `link_base` is fixed to `arm_1_mount`, which
is fixed to the world. The AABBs of the two mesh sets are identical (§2.3), so **the overlap is
the same under both** and cannot produce a difference. The same arithmetic holds for `arm_2` and
`arm_3`: the mounts sit at `(2.1, -0.3, 0.6)` and `(4.2, -0.3, 0.6)` above `pedestal_2` and
`pedestal_3`, whose top faces are also at z = 0.600.

**MoveIt does not report it, and that contrast is itself a registered finding rather than a
problem to fix.** `cite_skills/test/test_planning_pipeline.py:939-970` applies this exact
generated scene to a real `move_group`, verifies the objects are in its world, and then asserts
at **line 964** that the home configuration is `valid` — and that test passes in
`./scripts/test`. **So MoveIt's collision predicate and an exact triangle-to-box distance are two
different predicates**, and this campaign measures the second. Candidates for the gap — **listed
without choosing**, in the shape rule E requires: the narrow-phase tolerance of whatever
collision detector `move_group` loaded, which **nothing in this tree configures**
(`grep -rn "collision_detector" model/ workspace/src/cite_generated/ workspace/src/cite_bringup/`
returns nothing on 2026-09-04, so it is MoveIt's own default and this campaign does not name
it); link padding or scaling, which **nothing in this tree sets either**
(`grep -rn "padding\|link_scale"` over the same three paths reaches one unrelated comment on the
same date, so whatever `move_group` resolves is again MoveIt's default, and I4 records the value
it read back); the mesh representation the detector builds from the STL; and the pose round trip
through TF. **Nothing here attributes it**, and no rule below is written as though the cause were
known.

**What this campaign does about it, registered before any trial.**

1. **The standing pair is named and excluded from every aggregate by name.** The pair
   `(arm_N_link_base, pedestal_N)` for the arm's own pedestal is reported as **its own row** in
   every distribution, with its measured distance, and enters **no** minimum-over-pairs, **no**
   aggregate distribution and **no** verdict in §7.2 – §7.4. It is a property of the layout, not
   of a trajectory, and averaging it into a per-waypoint minimum would make every such minimum
   the same number.
2. **Every metric that was stated over an aggregate minimum is restated over per-(link, object)
   distances.** MARGIN1, TUNNEL1 and rule K all say "per (link, object)" below, and that is the
   whole substance of the correction: a question asked of the minimum over all pairs is answered
   by the closest pair, and the closest pair is a constant.
3. **The exclusion is by name and by nothing else.** No distance threshold is used to drop it,
   and **no tolerance anywhere in this file is widened to make it disappear** — widening one
   would hide every other contact of the same size, which is exactly the class of event #49
   asks about.
4. **It is not read as a defect in the model.** Whether a 132 nm overlap between an arm base and
   its pedestal matters is a question for L0 and for whoever owns the layout; §0 forbids this
   campaign from editing `model/`, and it takes no position. **What it is, here, is a fact the
   rules have to survive.**

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

**One number in the generated tree looks like it contradicts the 0.400 m/s above and does not.
Recorded 2026-09-04 so that a reader meeting both does not draw the wrong conclusion.**
`cell_a_arm_1_cartesian_limits.yaml` declares `max_trans_vel: 0.25` m/s — below the 0.400 m/s at
which a 0.1 s step reaches 0.040 m — and **it bounds nothing here.** That file's own generated
header says why: *"Only Pilz reads these, and only its LIN and CIRC generators do — PTP plans in
joint space and never consults them"*, and it records that they are *"consumed by NO motion in
this cell today"*. Every motion this campaign captures is planned in joint space. **The 0.25 is
not a ceiling on the tool step, and STEP1 is not compared against it.**

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

> **Rule T — inherited from the 2026-09-04 following-error campaign's §3, which took it from the
> 2026-09-03 campaign's, which took it from the 2026-09-02 campaign's, and re-scoped from *arms*
> to *captures*.** The re-scoping is faithful and the word *verbatim*, which this rule carried
> until 2026-09-04, was wrong: the source reads *"the arms are not each other's evidence …
> every verdict is stated per arm"*, and the unit of independence here is the capture. Nothing
> else in the wording changed. The captures
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
| **I2** | which pipeline produced it | **three readings, and the attribution is (c). Corrected 2026-09-04, before any trial.** (c) — **the attribution** — the `Calling Planner '<description>'` INFO line in the block log, whose description is `Pilz Industrial Motion Planner` or `OMPL` and nothing else (§2.1), matched to the publication that follows it in the same pipeline run. (b) — a **corroboration** — the skill server's own WARN `planner fallback: <A> found no path, retrying with <B>` (`skill_server.cpp:1798-1803`), scraped with its timestamp. (a) — a **corroboration only, and a weak one** — the interior `time_from_start` spacing, which can say *"consistent with 0.1 s"* and can say nothing more, because **both pipelines emit 0.1 s**: `AddTimeOptimalParameterization`'s `resample_dt` default is also **0.1** (`default_response_adapter_parameters.hpp:77` and `:86`, and `time_optimal_trajectory_generation.hpp:196`, read in the image on 2026-09-04) and **the generated pipeline files override it nowhere** (`grep -rn "resample_dt\|totg" workspace/src/cite_generated/ model/` returns nothing on 2026-09-04). **A disagreement between (c) and either corroboration is reported and is not resolved by choosing**, and it is (c) that decides the population |
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
| **I11** | link poses at a configuration — **primary** | host-side forward kinematics computed from the expanded URDF's joint origins, axes, types **and `<mimic>` couplings**, in the model's own root frame. Pure `numpy`; no ROS, no simulator, no clock. **The mimics are named because omitting them was a real hazard**: five of the six moving gripper joints are `<mimic>` followers of `arm_N_drive_joint` with `multiplier="1" offset="0"` (§5.4), so an implementation reading only origins, axes and types would place all five at zero and disagree with I12 by construction. FK1 is what would catch it |
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
  which is how the gripper's **six** moving links get a configuration at all, since the arm group
  excludes the drive joint (the expanded SRDF's `arm_1_xarm5` group runs
  `arm_1_world_joint` … `arm_1_joint_tcp` and contains no gripper joint; the gripper is its own
  group).
- **Six, not four, and five of the six are coupled followers. Corrected 2026-09-04, before any
  trial.** Expanding the shipped description gives **15** joints, of which the gripper's are
  `arm_1_drive_joint` — revolute, limits `0` to `0.85` rad — driving `arm_1_left_outer_knuckle`,
  and **five `<mimic>` joints**, every one `<mimic joint="arm_1_drive_joint" multiplier="1"
  offset="0"/>` with the same `0` to `0.85` limits: `left_finger_joint`,
  `left_inner_knuckle_joint`, `right_outer_knuckle_joint`, `right_finger_joint` and
  `right_inner_knuckle_joint`. `arm_1_xarm_gripper_base_link` is fixed to `link_eef` by
  `arm_1_gripper_fix` and does not move. **So six gripper links carry a collision mesh and move
  with the drive joint, and they move together**: at multiplier 1 and offset 0 every one of the
  six sits at the drive joint's own value. **A configuration that moves the drive joint and
  leaves the five followers behind is not a pose this gripper can take**, and neither GRIP1 nor
  I11 may produce one.
- **That the gripper does not move during an arm trajectory is an assumption of the
  completion, and it is registered as one**: §7.4's GRIP1 reports the same distances recomputed
  at both ends of the drive joint's declared range, with **all six links moved together**, so the
  sensitivity is measured rather than argued.
- **The completion itself is sound, and this is better founded than the paragraph above claims.**
  `trajectory_start` is not assembled by this campaign: `DisplayMotionPath::adapt` fills it with
  `moveit::core::robotStateToRobotStateMsg(res.trajectory->getFirstWayPoint(), ...)`
  (`display_motion_path.cpp:89`, MoveIt 2.12.4, read on 2026-09-04), so it is a full MoveIt
  `RobotState` with every mimic already enforced by MoveIt's own `RobotModel`. **The gripper
  configuration the completion supplies is therefore consistent by construction**, and what is
  assumed is only that it does not change during the trajectory — which is what GRIP1 bounds.

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
a numerical identity, a constant this tree already ships, or an inherited rule** — never on
campaign data, never on a figure from §2.5's list. **Where a size is a judgement rather than a
derivation, its row says so.**

**Corrected 2026-09-04, before any trial: the claim that every size had a row here was false.**
Three registered sizes had none — V5's 1e-9 m, FK1's 200-waypoint sample, and rule C-i's ceiling,
which was not registered anywhere at all and is set in this table. They are rows now, and the fifth
source — *a constant this tree already ships* — is added because C-i's ceiling stands on one.

| Metric | Size | Why this size |
|---|---|---|
| `CLOSE_BAND`, the close-approach band | **0.040 m** | **the smallest dimension of any object in the generated planning scene** (§2.2). An arm closer to a body than the thinnest body in the cell is thick is near it in the only unit the cell itself declares |
| `STEP_HIGH`, the step that could traverse the thinnest object | **0.040 m** | the same dimension. A consecutive-waypoint step below it cannot carry the tool point clear through a beam housing's thin axis with both endpoints outside |
| `STEP_MID`, the comparable band's floor | **0.020 m** | half `STEP_HIGH`. **The factor of two is a judgement and is recorded as one**: it is the margin at which "far below" stops being an honest description |
| `DIFF_FLOOR`, the numerical floor on a hull-versus-vendor difference | **1e-9 m** | **the hull's vertex set is a subset of its source's, bit-identical** (§2.3) — not "the two sets share vertex coordinates", which was the loose wording this row carried until 2026-09-04 and is false in the other direction: the source has vertices the hull does not. Verified on the committed files on 2026-09-04, on four of the thirteen pairs spanning the size range, every hull vertex present in its source to the bit. So a difference below this is double-precision arithmetic and not geometry |
| `SUB_STEP`, the interpolation target | **0.002 m** of tool-point travel per sub-sample | one twentieth of the thinnest object's thickness. **The twentieth is a judgement, recorded as one**; what is not a judgement is that it is referred to the same declared 0.040 m |
| `SUB_CEILING`, the sub-sample ceiling | **200** sub-intervals per waypoint interval | a bound on the compute, not on the physics. **Every interval that hits it is counted and reported**, and its achieved sub-step is stated |
| `CENSOR`, the broad-phase cutoff | **0.500 m** | **12.5×** `CLOSE_BAND`, so nothing either question is about can be censored; and the bound it is applied to is identical under both geometries (§2.3), so censoring is symmetric. Rule M |
| FK agreement tolerance | **1e-6 m** and **1e-6 rad** | four orders of magnitude below `CLOSE_BAND`. **A judgement, recorded as one** |
| REPRO1's cross-interpreter tolerance | **1e-12 m** | the compute stage is deterministic within one interpreter; across two `numpy` versions a reduction order may differ, and 1e-12 m is six orders below `DIFF_FLOOR`'s own scale of interest. **A judgement, recorded as one** |
| rule C's trajectory floor | **2** waypoints | a trajectory with fewer has no interval, so it can contribute to neither STEP1 nor TUNNEL1 |
| rule C's instrument-loss ceiling | **20 %** of a capture's published trajectories | **a judgement, and recorded as one**, inherited in size and reasoning from the 2026-09-04 following-error campaign's rule L: above one in five lost, the surviving set is a sample of what the recorder happened to keep |
| V7's load flag | load average **4.0** on 16 cores | **inherited** from the 2026-09-02 scenario-ceilings campaign. It **flags and never excludes** |
| **V5's scene-agreement tolerance** | **1e-9 m** | **added 2026-09-04.** The scene read back and the generated file are the same float64 numbers under a rigid transform, so any residual is arithmetic; 1e-9 m is the same numerical floor `DIFF_FLOOR` uses, in the same units, on the same kind of quantity. **It is expected to fire under one accounting choice and that arithmetic is registered in V5 (§10)**, so a firing is not a discovery |
| **FK1's sample size** | **200** waypoints | **added 2026-09-04, and a judgement recorded as one.** It bounds a launch-based cross-check that costs a service round trip per waypoint; it is not a power calculation and no proportion is estimated from it. FK1 is a **conjunction over the sample** — every one of the 200 must agree — so a single disagreement is the result and the sample size bounds only how much of the trajectory set the check reaches |
| **rule C-i's door ceiling**, `DOOR_CEILING_S` | **240.0 s** | **added 2026-09-04, and it is a constant this tree already ships**: `BRING_UP_CEILING_S = 240.0` (`tests/scenarios/bringup.py:94`). The harness cannot need to wait for a publisher that `move_group` creates for longer than the scenario itself waits for the cell to come up, because the scenario has failed by then. **It is a bound on waiting and never a schedule** — the door opening is an event (V4, V13, P4) and nothing sleeps on it. **It is not differenced against anything and imports no campaign figure** (rule H); the tree's own comment records that the shipped ceilings rest on a campaign in this directory, and that campaign's figures do not enter here |
| **rule R's minimum interesting size**, per metric | DELTA1 **1e-9 m** (`DIFF_FLOOR`); MARGIN1 and STEP1 **0.002 m** (`SUB_STEP`); TUNNEL1 **not applicable** | **added 2026-09-04.** Rule R fired on "that metric's minimum interesting size" and **no table assigned one**: the scope condition was inherited and the number was not. No new number is introduced — DELTA1's quantity is bounded below by arithmetic, so anything above `DIFF_FLOOR` is interesting; MARGIN1 and STEP1 are lengths the campaign resolves geometry at `SUB_STEP`, so two values closer than that are the same approach as far as this instrument can tell. **TUNNEL1 is a binary observation and has no spread**, so rule R does not apply to it and V6 and V7 govern it by their own wording |

### 7.1 LIVE1 — a measured capture, or a measured nothing

**This is the campaign's central hazard.** A subscription that never matched, a topic that does
not exist, a name resolved into the wrong namespace and a scenario that failed before it planned
anything all produce **the same empty set** — and an empty set reads as "no trajectory came close
to anything", which is the reassuring answer.

> **Rule C — the capture rule. No distance claim is admissible for a capture that does not
> satisfy it, and it is checked per capture per block.**
> - **C-i — the door was open. Restated 2026-09-04, before any trial, because as written it had
>   a dead primary clause and a live branch naming an unregistered number.** The clause it
>   carried required a matched publisher *before the scenario process was started*, and **that
>   can never happen**: the publisher is created by `DisplayMotionPath::initialize` on the
>   `move_group` node (§2.1), each scenario starts its own `move_group` through
>   `IncludeLaunchDescription` inside its own process (`tests/scenarios/bringup.py:110`), and
>   every run owns its own cell. **The topic does not exist until the scenario has started it**,
>   in all nine runs. So the branch that can occur is the only branch, and it is now the rule:
>   the subscription reported **at least one matched publisher on each arm's
>   `display_planned_path` within `DOOR_CEILING_S` (240.0 s, §7.0) of the scenario process being
>   started**, and it reported it **before that arm's first `Calling Planner` line in the block
>   log** — which is the clause that actually does the work, because a door matched after the
>   first plan is a door that missed one. The matched publisher count, **every** matched
>   publisher endpoint and the resolved endpoint QoS are recorded (V4). An arm that never matched
>   within the ceiling, or matched after its first plan, fails C-i for that block.
> - **C-ii — nothing was dropped, and a shortfall has a registered consequence. The consequence
>   was missing until 2026-09-04.** The number of `DisplayTrajectory` messages received equals
>   I5's count of `Calling PlanningResponseAdapter 'DisplayMotionPath'` lines in the same block
>   log. **Where the per-arm attribution of a log line cannot be resolved from the launch
>   process prefix, the equality is stated over the block total and the ANALYSIS says so.**
>   **What a shortfall does, registered here because a trajectory that was never received can
>   neither fail a clause nor be excluded, so the per-trajectory INSTRUMENT LOSS below cannot
>   reach it.** A shortfall of `k = I5 - received` is a **capture-level instrument loss of k
>   trajectories**, reported on its own line, never merged with the per-trajectory losses, and
>   **counted toward the 20 % ceiling** — which is stated over **I5's published count**, the
>   population the door was supposed to carry, and not over what arrived. If `k` alone exceeds
>   the ceiling, the capture is **NOT ADMISSIBLE** and rule N applies to it, exactly as for the
>   per-trajectory losses.
>   **A surplus is a different finding and is not a loss.** `received > I5` means the log and the
>   graph disagree about what was published; it is reported as a **DISAGREEMENT** under rule D,
>   nothing is re-run, and the capture's verdicts are stated with it beside them.
> - **C-iii — the trajectory is usable.** At least **2** waypoints; `time_from_start` strictly
>   increasing; every point's `positions` the same length as the message's joint-name list; every
>   named joint present in the expanded description.
> - **C-iv — the configuration is complete.** Every joint of the model is either named in the
>   trajectory or present in `trajectory_start.joint_state`; a model joint in neither makes the
>   trajectory inadmissible rather than silently defaulted to zero.
>
> A trajectory failing any clause is an **INSTRUMENT LOSS**: excluded from every distribution,
> **counted and reported separately from every other exclusion**, and **never counted as a
> trajectory that stayed clear**. If more than **20 %** of a capture's published trajectories —
> **published**, meaning I5's count, not the count that arrived — are instrument losses of any
> kind, C-ii's shortfall included, that capture's DELTA1, MARGIN1, STEP1 and TUNNEL1 are **NOT
> ADMISSIBLE** and rule N applies to it.

> **LIVE1 — ADMISSIBLE / NOT ADMISSIBLE, stated per capture**, with the trajectory count, the
> waypoint count, the loss count by clause, **C-ii's shortfall as its own line**, and the
> received-versus-logged counts side by side.
> **`ANALYSIS.md` states LIVE1 before it states any other verdict**, per capture, so that no
> clearance can be read without the instrument's own report beside it.

### 7.2 DELTA1 and FLIP1 — what the hull changed

Report, per capture, per link and per object: the distribution of `d_hull` and of
`d_vendor - d_hull` over admissible waypoints (min, median, p95, p99, max), the maximum with the
trajectory, waypoint, link and object that produced it, and the count of censored pairs. **The
standing `(link_base, own pedestal)` pair of §2.2.1 is reported as its own row and enters no
aggregate.**

> **DELTA1 — IDENTICAL / SMALLER / DISAGREEMENT / NOT EXERCISED / NOT ADMISSIBLE, stated per
> capture.**
> **IDENTICAL** iff `max(d_vendor - d_hull) <= DIFF_FLOOR` over every evaluated (waypoint, link,
> object). **SMALLER** iff it exceeds `DIFF_FLOOR` — reported in full, with the distribution, the
> maximum, and the minimum distance at that waypoint under each set. **NOT ADMISSIBLE** under
> rule C.
> **NOT EXERCISED** under rule K-i, **and this state was missing from the enumeration until
> 2026-09-04.** K-i's own text already says DELTA1 is then stated as *"not exercised"*, so the
> rule named an outcome the verdict could not take. It is a real state now that K-i can refuse
> at all (§7.7), and it takes precedence over IDENTICAL: a capture whose closest approach outside
> the standing pair never reached `CLOSE_BAND` has **not** measured that the two sets agree, it
> has measured nothing, and rule N governs its silence.

> **Rule E — one direction is a theorem, so a measurement in it falsifies the instrument.**
> `d_hull <= d_vendor` follows from containment (§2.3). If any evaluated triple has
> `d_hull > d_vendor + DIFF_FLOOR`, DELTA1 is **DISAGREEMENT**: it is reported with both numbers
> and the whole trace, **nothing is re-run**, **nothing is edited**, and **the campaign does not
> attribute it** — the mesh reader, the hull provenance, the transform, the triangle-box routine,
> the broad phase, **MoveIt's link padding and link scaling as I4 recorded them, and the
> narrow-phase solver's own tolerance** are listed as candidates without choosing. **The last
> three were added on 2026-09-04**, because §2.2.1 shows this tree already contains a
> configuration where MoveIt's verdict and an exact distance disagree, and a candidate list that
> omitted the most likely reason for such a disagreement was not a candidate list. It is stated
> in `ANALYSIS.md`'s verdict line, because it is a result about the instrument and not a
> procedural exception. This is rule D applied to the one comparison whose answer is known in
> advance.

> **FLIP1 — NONE / HULL-ONLY CONTACT / REVERSED, stated per capture and per (link, object) pair.
> Split into two named outcomes on 2026-09-04, before any trial, because the single OBSERVED it
> carried folded the campaign's most valuable possible observation into an instrument fault.**
> A flip is a **(waypoint, link, object)** at which one geometry set is in contact and the other
> is clear.
> - **HULL-ONLY CONTACT** — `d_hull <= 0` and `d_vendor > 0`. **This is a finding about
>   geometry, and it is exactly #49's feared consequence made visible.** It is reported with its
>   depth, its trajectory, waypoint, link and object, and with whether MoveIt accepted the
>   trajectory — which it did, by the capture door (§1.1). **It does not contradict containment**:
>   containment forbids the hull being *further* away, and this is the hull being *closer*, which
>   is the direction containment predicts. What it would contradict is the *conditioning* — the
>   implication *MoveIt accepted, therefore exact `d_hull > 0`* — and **§2.2.1 shows that
>   implication is already false in this tree**, so this outcome is reachable and must not be
>   handled as a fault.
> - **REVERSED** — `d_vendor <= 0` and `d_hull > 0`. **This is the direction containment
>   forbids**, and it is a **DISAGREEMENT** under rule E: an instrument finding, reported with
>   its whole trace and not attributed.
> - **NONE** — neither, over every evaluated pair.
> **What the conditioning still guarantees, and it is narrower than the sentence this rule
> carried until 2026-09-04.** For every pair MoveIt's own predicate separates, both sets are
> separated. It does **not** guarantee that this campaign's exact distance is positive anywhere.
> **A NONE verdict is reported in the rule-N shape and may not be read as evidence that either
> geometry is safe, that the hull changed nothing, or that #49 is closed.**
> **Registered before any trial, so that a HULL-ONLY CONTACT is not read as more than it is.**
> It would say the hull is in contact where the vendor mesh is not, on a trajectory the cell ran
> and MoveIt accepted. It would **not** say the hull set refuses a motion the vendor set would
> accept — that question is structurally outside this campaign (§1.1, §7.5, §8) and **this
> campaign does not narrow it by one millimetre**, whichever way FLIP1 falls.
> **The added material is real and is not the reason to expect a flip.** Computed here on the
> committed files on 2026-09-04, the shipped hull's volume divided by its source's runs from
> **1.060** on `end_tool` to **2.965** on each inner knuckle, **1.596** over the thirteen
> together. **That is a bound on where material was added and not a prediction that any of it
> reaches an object**: every added point lies inside a concavity of the source, and whether a
> concavity faces anything in this cell at the poses these trajectories reach is precisely what
> is unknown. It is recorded so that a null result is not read as "the hull is the same shape".

### 7.3 MARGIN1 — how close this cell actually passes

**Restated over per-(link, object) distances on 2026-09-04, before any trial.** As written it
stood on the minimum over all pairs, and §2.2.1 makes that minimum a configuration-independent
constant at or below zero — so **TIGHT was guaranteed, and "the fraction of waypoints inside
`CLOSE_BAND`" was 100 % by construction**. A verdict that cannot come out the other way measures
nothing.

Report, per capture and **per (link, object) pair**: the distribution over admissible waypoints
of that pair's distance under each geometry; the count and the fraction of **(waypoint, pair)**
evaluations inside `CLOSE_BAND`; and, per pair, the identity of the closest approach —
trajectory, waypoint, arm, block. The standing pair of §2.2.1 is **one of the rows and is in no
aggregate**.

> **MARGIN1 — TIGHT / CLEAR / NOT ADMISSIBLE, stated per capture, and the set of pairs it is
> TIGHT on is named.**
> **TIGHT** iff at least one admissible (waypoint, link, object) **other than the standing pair
> of §2.2.1** has a distance under the shipped hull set of `<= CLOSE_BAND` (0.040 m). **CLEAR**
> otherwise. **NOT ADMISSIBLE** under rule C. **A TIGHT verdict is reported with every pair that
> produced it**, because "something came within 40 mm of something" is not a measurement and the
> pair is the finding.
> **A CLEAR verdict carries rule K with it**: it says these trajectories never came within the
> thinnest object's thickness of anything **but the arm's own pedestal**, and it does **not** say
> the cell cannot.
> **Registered before any trial: the standing pair is excluded by name and by nothing else.** No
> distance threshold drops it, and if the exclusion were removed MARGIN1 would read TIGHT on
> every capture and say nothing at all — which is what it did until this amendment.

### 7.4 STEP1, TUNNEL1 and GRIP1 — the gap between two checks

> **STEP1 — FAR BELOW / COMPARABLE / EXCEEDS, stated per capture and per pipeline.**
> The quantity is the tool-point Cartesian step between consecutive waypoints — the position of
> **`arm_N_link_tcp`**, which is the tip of the SRDF's `arm_N_xarm5` group and the `tip_link` the
> generated bring-up plan hands the skill server (`cell_a_plan.yaml:230`,
> `skill_server.cpp:559`).
> **EXCEEDS** iff the maximum step is `>= STEP_HIGH` (0.040 m). **COMPARABLE** iff it lies in
> `[STEP_MID, STEP_HIGH)`. **FAR BELOW** iff it is below `STEP_MID` (0.020 m).
> **Stated per pipeline because #17 is a statement about Pilz**: an OMPL trajectory is
> re-timed by `AddTimeOptimalParameterization`, and although both pipelines land on 0.1 s (§4.1,
> I2) the quantity is a different one — Pilz's generation spacing against a re-sampling interval
> — so the two populations are reported separately.
> **The attribution is I2's reading (c), the `Calling Planner` line, and the rule that discarded
> the OMPL population is deleted. Corrected 2026-09-04, before any trial.** The rule read *"a
> trajectory whose two readings disagree is reported separately and enters neither"*, with
> reading (a) — the interior spacing — as one of the two. **`AddTimeOptimalParameterization`'s
> `resample_dt` default is also 0.1 and this tree overrides it nowhere** (§4.1), so (a) reads
> "uniform 0.1" for **both** pipelines; on the stated justification every OMPL trajectory
> disagreed with itself and **the entire OMPL population was silently discarded**. That data is
> directly on-question: `ValidateSolution` runs on the post-TOTG trajectory in the OMPL pipeline
> too, so **#17's residual applies to OMPL identically**. Reading (a) is now a corroboration
> that can say *"consistent with 0.1 s"* and nothing more, and a trajectory it disagrees with is
> **reported and kept**, in the population (c) assigns it. **Only a trajectory that reading (c)
> cannot attribute at all** — no `Calling Planner` line resolvable to it — is reported separately
> and enters neither population, counted as its own line beside LIVE1.
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
> **OBSERVED** iff, **for some (link, object) pair other than the standing pair of §2.2.1**, a
> sub-sample's distance for that pair is `<= 0` while **both bracketing waypoints are `> 0` for
> that same pair** — a body passing strictly between two checked configurations, which is exactly
> ADR-0027's residual, measured on the trajectories the cell produced.
> **NOT OBSERVED** otherwise, **with rule K attached**.
> **Restated over per-(link, object) distances on 2026-09-04, before any trial, and this was the
> most damaging of the eight defects.** As written the condition was on the **aggregate** minimum
> at the bracketing waypoints, and §2.2.1 puts that aggregate at or below zero at **every**
> waypoint — so the OBSERVED branch was unreachable, TUNNEL1 was **NOT OBSERVED
> unconditionally**, and **PRED5's refuter could not fire**. That refuter is this campaign's
> whole answer to #17. Per pair, the condition is live: the standing overlap is one pair's
> business and says nothing about any other pair's bracketing distances.
> **This is not a claim about the path the arm physically followed.** The controller tracks the
> same waypoints with its own lag under a first-order plant, so the executed path is neither the
> waypoint set nor this interpolation. What TUNNEL1 measures is what `ValidateSolution` did not
> look at.

> **GRIP1 — the gripper completion's sensitivity, reported and deciding nothing.** Every distance
> involving one of the **six** moving gripper links — `left_outer_knuckle`, `left_finger`,
> `left_inner_knuckle`, `right_outer_knuckle`, `right_finger`, `right_inner_knuckle` — is
> recomputed with the drive joint at **0** and at **0.85 rad**, the ends of its declared range,
> **and with all five `<mimic>` followers moved with it at multiplier 1 and offset 0** (§5.4).
> The largest change is reported per capture and per pair. **It sets no verdict**: it exists so
> that §5.4's completion assumption is a measured sensitivity rather than an argument.
> **Corrected 2026-09-04, before any trial, on two counts.** It said **four** links, which is two
> short and left a third of the moving gripper outside its scope; and it named the two drive-joint
> values without saying that the five followers move with the drive joint, which read literally
> specifies a kinematically impossible gripper — five knuckles and fingers frozen at zero while
> the sixth swings through 0.85 rad. `arm_1_xarm_gripper_base_link` is **fixed** and is not in
> GRIP1's scope; it is in every other distribution like any other link.

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

> **VALID1 — CONSISTENT / INCONSISTENT / KNOWN-DIVERGENT, and the informative direction is now
> the one registered. Restated 2026-09-04, before any trial.** As written its only clause was
> *a waypoint the compute stage puts at `d > 0` against every object must come back valid* — and
> §2.2.1 makes that antecedent **false at every waypoint**, so the rule was vacuously satisfied
> and could not fail. At the same sampled waypoints, `GetStateValidity` in I12's rig is called
> and its verdict is compared with the compute stage's sign, after removing contacts whose two
> bodies are both robot links. Three clauses, and the second is the one that carries information:
> - **Forward.** A waypoint the compute stage puts at `d > 0` for **every** (link, object) pair
>   must come back valid. Registered in the knowledge that it may have no instances.
> - **Reverse — the informative direction.** For each (link, object) pair the compute stage puts
>   at `d <= 0`, MoveIt is expected to report that pair among its contacts. **The standing pair
>   of §2.2.1 is expected to violate this** — `test_planning_pipeline.py:939-971` already shows
>   MoveIt calling the home configuration valid — so that pair alone is reported as
>   **KNOWN-DIVERGENT** and is not counted as an inconsistency. **Any other pair violating it is
>   INCONSISTENT and is a result**, not an exception: it would mean the two predicates disagree
>   somewhere the layout does not explain.
> - **Neither is resolved by choosing.** **INCONSISTENT is reported with the scene's recorded
>   `link_padding` and `link_scale` beside it** (I4), because a non-zero padding is a sufficient
>   explanation and the campaign states it rather than assuming it — and rule E's candidate list
>   applies here too. Nothing is re-run and no tolerance is widened.

> **REPRO1 — REPRODUCED / NOT REPRODUCED.** The compute stage is run **twice in the same
> interpreter** and must produce **byte-identical** output; and **once more in a second
> interpreter with a different `numpy`** (§9 names both) and must agree to **1e-12 m**. A
> failure of either is reported and **no figure from that run is published as a measurement**.

### 7.7 The refusals that carry the campaign's honesty, and the predictions

> **Rule K — the region of interest, in the rule-W shape of the 2026-09-02 campaign, which took
> it from ADR-0051's rule S. Defined here, before anything was captured.**
> **Restated over per-(link, object) distances on 2026-09-04, before any trial. As written,
> K-i could not refuse.** It keyed on the vendor set's **aggregate** minimum being `<= 0.040 m`,
> and §2.2.1 puts that aggregate at or below zero at every waypoint of every trajectory — so
> every capture was "exercised" by construction and the rule §11 calls *the one that matters most
> here* was inert. Per pair it can refuse, which is the only reason to have it.
> - **K-i — #49's region.** The hull-versus-vendor question is **exercised** by a capture only if
>   at least one admissible (waypoint, link, object) **other than the standing pair of §2.2.1**
>   has a distance under the **vendor** set of `<= CLOSE_BAND` (0.040 m). If none has, that
>   capture **has not tested close-approach clearance**: its DELTA1 is stated as *"not exercised;
>   the closest approach outside the standing pair was X m, on pair P"*, and its silence may
>   **not** be read as a pass, as a clearance of the hull selection, as agreement with ADR-0028's
>   audit, or as evidence that #49 is closed.
> - **K-ii — #17's region.** The tunnelling question is **exercised** by a capture only if at
>   least one consecutive-waypoint pair has both a step `>= STEP_MID` (0.020 m) **and**, for some
>   (link, object) pair other than the standing one, a bracketing distance `<= CLOSE_BAND`.
>   Moving fast far from everything tests nothing, and creeping close to something tests nothing
>   either; **the question needs both at once.** If no waypoint pair has both, TUNNEL1 is stated
>   as *"not exercised"* and **#17 stays open on this campaign's evidence**, in those words.
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

> **Rule R — resolution. Inherited via the 2026-09-03 and 2026-09-04 campaigns, and re-scoped
> here on 2026-09-04, before any trial, because as inherited it quantified over a comparison this
> campaign never makes.** For any metric whose spread **within one capture in one block** exceeds
> **that metric's minimum interesting size as §7.0 now assigns it**, a non-detection of a
> difference is **INCONCLUSIVE for that metric — never "no difference"**.
> **The comparisons it binds are the two that occur here**: V6's, between two blocks of the same
> capture; and V7's, between the load-flagged and unflagged subsets of one block. **The
> "between captures" comparison the rule was inherited with is dropped rather than carried**,
> because **rule T forbids it** — the captures are not each other's evidence and every verdict is
> stated per capture, so there is no between-capture non-detection to guard. Carrying a clause
> that binds nothing is the same defect as a threshold with no number.
> **The sizes are in §7.0's table**, one per metric, and TUNNEL1 has none because a binary
> observation has no spread.

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
| **PRED3** | **FLIP1 = NONE on every capture, and a NONE evidences nothing** (§1.1, §7.2). Registered so that it cannot be read as a result. **It is a real prediction again as of 2026-09-04**: before FLIP1 was split it was a statement about an outcome that could not occur. | a **HULL-ONLY CONTACT**, which is a geometry finding and would be this campaign's most valuable observation; or a **REVERSED**, which is a DISAGREEMENT under rule E |
| **PRED4** | **STEP1 = FAR BELOW on the Pilz trajectories of every capture.** Producing a 0.040 m step from one joint needs a moment arm of 0.36415 m at the shipped scaling (§2.4). **No mechanism is offered, and this is the weakest prediction here.** It carried one until 2026-09-04 — *"this arm carries the tool point closer to its own axes over most of a station approach"* — and **that sentence was an unsupported assertion about poses this file establishes nothing about**, in a file that elsewhere refuses those; it is deleted rather than hedged. What remains is a bare guess against an arithmetic scale, and §2.4 already says 0.36415 m is neither an upper nor a lower bound on what the cell produces. | any capture whose Pilz maximum step reaches `STEP_MID` |
| **PRED5** | **TUNNEL1 = NOT OBSERVED on every capture and every geometry**, and **rule K-ii fires** — that is, the campaign predicts it will not have tested the question. Registered in advance because **a NOT OBSERVED that rule K refuses is the honest expected outcome**, and it must not be reported as a clearance of ADR-0027's residual. **Its refuter was structurally unreachable until 2026-09-04** and is reachable now (§7.4). | any observed sub-sample contact, for one (link, object) pair, between two waypoints clear **for that pair** — which would be the campaign's headline and a direct measurement of #17 |
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
  least one matched publisher, and **every** matched publisher's resolved endpoint QoS from
  `get_publishers_info_by_topic` **travels on the block record**.
  **Expect two publishers per arm, not one, and record all of them. Added 2026-09-04.** Each
  pipeline loads its own `DisplayMotionPath` instance and `initialize` creates a publisher per
  instance on the same relative topic (`display_motion_path.cpp:63-71`, MoveIt 2.12.4, read on
  2026-09-04); both pipelines are declared for every arm
  (`cell_a_arm_1_planning_pipelines.yaml`, all three read). This rule said *"the publisher"* in
  the singular until this amendment. It is benign — the trajectories arrive on one topic either
  way — but a count recorded as 1 where 2 is correct is a discrepancy that would have to be
  explained later, and recording every endpoint costs nothing. **Treat the match as an event,
  never as a sleep** (CLAUDE.md §10). A block that ran a scenario without a matched subscription
  on an arm is reported, and that arm's trajectories for that block are an instrument loss under
  rule C-i rather than a silence.
- **V5 — the scene that actually planned. Its tolerance is carried unchanged and its expected
  firing is registered here rather than discovered in the write-up. Added 2026-09-04.** I4's
  read-back is compared with `cite_generated/moveit/cell_a_planning_scene.yaml`: the object ids
  must match exactly, and each object's dimensions and pose must agree to **1e-9 m** after the
  frame the planner reports is accounted for. A disagreement is **reported and the block's
  distances are stated against the read-back**, never against the file. A block whose read-back
  is empty is **discarded**: a plan validated against an empty world is not the gate this
  campaign is about.
  **The arithmetic that decides whether this rule fires, computed here on 2026-09-04.** The
  generated static transform `cite_world -> arm_N_mount` carries yaw `1.570796327`, which is
  `pi/2` truncated: the difference is **2.051035e-10 rad**. Applied at the horizontal lever arm
  of the furthest objects that displaces them by more than 1e-9 m — **three (arm, object) pairs
  of the 36**, all on `arm_1`: `table_accumulation` at **1.273e-9 m**, `beam_c3_out` at
  **1.185e-9 m** and `conveyor_3` at **1.079e-9 m**, the largest being 1.273e-9 m.
  **So the accounting decides it, and the choice is registered now.** The harness accounts for
  the frame using **the generated static transform's own value**, which is the value `move_group`
  itself was given, so the round trip cancels to double precision and V5 is expected to pass. **If
  the harness is instead written against `pi/2`, V5 fires on exactly those three pairs and on
  nothing else, and that firing is arithmetic rather than a scene defect.** Either way, **V5 only
  reports**: a firing is stated with the pair, the residual and which value was used, no tolerance
  is widened (V9), and the block's distances stand against the read-back.
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
- **One verdict direction is guaranteed before any data exists, and it is registered so that it
  cannot be cashed.** DELTA1's DISAGREEMENT direction is a theorem, so a measurement in it
  falsifies the instrument and never the geometry (rule E).
  **This bullet said *two* until 2026-09-04, and the second was withdrawn along with three
  others that were guaranteed and not registered.** FLIP1 = NONE was called guaranteed on a
  premise §2.2.1 falsifies, and FLIP1 now has a reachable geometry outcome (§7.2). What was
  guaranteed and **unregistered** was worse: **MARGIN1 = TIGHT**, from a static structural
  overlap rather than from any trajectory; **TUNNEL1 = NOT OBSERVED**, whose refuting branch
  could not be reached; and **VALID1 = CONSISTENT**, whose only clause had a false antecedent
  everywhere. Rule K-i could not refuse either. **All five stood on one fact about the layout
  that no rule mentioned**, and all five are restated over per-(link, object) distances in §7.
  **The lesson is registered with them:** a rule stated over an aggregate is answered by the
  aggregate's extreme member, and if that member is a constant the rule is decoration.
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

---

## 12. Amendment of 2026-09-04, before the first trial

**Permitted because rule 1 had not closed.** [`../README.md`](../README.md) freezes this file
**once the first trial has run**. When this amendment was written `harness/` did not exist,
`raw/` did not exist, `ANALYSIS.md` did not exist and **no trial had run**, so nothing here was
chosen by data — there was no data. **After the first trial none of this is available**, and
every later correction is a numbered deviation in `ANALYSIS.md` applied to data already
collected.

**No threshold moved.** `CLOSE_BAND`, `STEP_HIGH`, `STEP_MID`, `DIFF_FLOOR`, `SUB_STEP`,
`SUB_CEILING`, `CENSOR`, the FK tolerance, REPRO1's tolerance, rule C's floor of 2, the 20 %
ceiling, V7's 4.0 and V5's 1e-9 m are all exactly what they were. **No geometry selection, no
sampling time, no velocity scaling and no layout figure is touched**, and §0 is unchanged.

**What changed, and why.** Eight defects, five of them rules that could not fire or could fire
only one way.

| # | What was wrong | How it was closed |
|---|---|---|
| 1 | **Four rules were vacuous at once.** Every arm's base overlaps its own pedestal by ~132 nm at every configuration under both geometries (§2.2.1), so the **aggregate** minimum distance is at or below zero everywhere. MARGIN1 = TIGHT was guaranteed by a static overlap, TUNNEL1's OBSERVED branch was unreachable and PRED5's refuter with it, rule K-i could never refuse, and VALID1's only clause had a false antecedent. | **By definition.** The fact is registered in §2.2.1 with its arithmetic; MARGIN1, TUNNEL1, rule K and VALID1 are restated over **per-(link, object)** distances; the standing pair is excluded **by name** from every aggregate and reported as its own row. Nothing was widened. |
| 2 | **The pipeline attribution could not tell Pilz from OMPL, and then discarded every OMPL trajectory.** Reading (a) was the 0.1 s interior spacing, but TOTG's `resample_dt` default is also 0.1 and nothing overrides it — so (a) read the same for both, every OMPL trajectory "disagreed", and STEP1's own rule dropped the lot. The data is on-question: `ValidateSolution` runs post-TOTG in that pipeline too. | **By deletion and replacement.** The discarding rule is deleted. I2 gains reading **(c)**, the `Calling Planner '<description>'` INFO line whose two descriptions are distinct string literals, as **the** attribution; (a) is demoted to a corroboration that can only say *"consistent with 0.1 s"*. |
| 3 | **FLIP1 foreclosed the only reading #49's positive answer can take.** Its single OBSERVED was routed to rule E as an instrument fault, with *"never as a finding about geometry"* attached — but the only reachable flip is hull-in-contact-where-vendor-is-clear, which is #49's feared consequence, and it contradicts the conditioning rather than containment. Rule E's candidates omitted the likeliest cause. | **By definition.** FLIP1 splits into **HULL-ONLY CONTACT** (a geometry finding, reported with its depth) and **REVERSED** (rule E). *"Never as a finding about geometry"* is **deleted**. Rule E gains MoveIt's padding, scaling and the narrow-phase tolerance as candidates. |
| 4 | **Rule C-i's primary clause was unsatisfiable** — it wanted a matched publisher before the scenario started, and the scenario starts the `move_group` that creates it — leaving one live branch that named an unregistered ceiling. | **By definition.** C-i is restated over the branch that can occur, with `DOOR_CEILING_S` = **240.0 s** registered in §7.0 against the tree's own `BRING_UP_CEILING_S`, plus the clause that does the work: matched **before** that arm's first plan. |
| 5 | **Rule C-ii had no consequence.** A trajectory never received can neither fail a clause nor be excluded, so the per-trajectory INSTRUMENT LOSS could not reach a shortfall. | **By definition.** A shortfall is a **capture-level** loss of `k` trajectories, counted toward the 20 % ceiling, which is now stated explicitly over **I5's published count**. A surplus is a rule-D DISAGREEMENT. |
| 6 | **"Four" moving gripper links; there are six**, five of them `<mimic>` followers, and GRIP1's two drive-joint values were stated without the coupling — read literally, a kinematically impossible gripper. | **By definition.** §5.4 and GRIP1 name all six and state the coupling; I11 names the mimics explicitly. Recorded in passing: FK1 is safe regardless, because `trajectory_start` is a full MoveIt `RobotState`. |
| 7 | **Rule R's threshold was undefined** — no table assigned a minimum interesting size — and it quantified over between-capture comparisons that rule T forbids, while V7 invoked it for a within-block one. | **By definition and by deletion.** §7.0 assigns a size per metric, introducing no new number; the between-capture clause is **dropped** and the rule re-scoped to V6's and V7's actual comparisons. |
| 8 | **§7.0's exhaustiveness claim was false** — three registered sizes had no row — and V5's 1e-9 m sits below its own arithmetic floor under one accounting choice. | **By definition.** The three rows are added. V5's tolerance is **carried unchanged** and its expected firing registered with the arithmetic: 2.051035e-10 rad of yaw truncation, three of 36 pairs above 1e-9 m, largest 1.273e-9 m. |

**Five smaller corrections, all of them wording or citation.** Two `DisplayMotionPath` publishers
per arm rather than one (V4); the Cartesian `max_trans_vel: 0.25` that bounds nothing here
(§2.4); `planning_pipeline.cpp` citations moved to the lines 2.12.4 actually has; rule T's
*"inherited verbatim"* corrected to a re-scoping; `DIFF_FLOOR`'s reason corrected from *"the two
sets share vertex coordinates"* to the true and one-directional *"the hull's vertex set is a
subset of its source's"*. PRED4's unsupported mechanism is **deleted** rather than hedged, and
DELTA1 gains the **NOT EXERCISED** state rule K-i already named.

**What was deliberately not changed.** **The registered bound on #49's refusal question stays
exactly where it was.** §1.1's capture-door argument, §7.5's REFUSE1 and §8's first bullet all
still say that a refused trajectory is never published, that its geometry is not measurable
through this door, and that **this campaign cannot answer whether the hull set refuses a motion
the vendor set would have accepted**. That bound is correct, it is the honest part of this
design, and **nothing in this amendment weakens it by one millimetre** — FLIP1's new geometry
outcome is about trajectories that were **accepted**, and it is not a refusal result.

**How the figures in this amendment were obtained.** Every one was computed or read here, on
2026-09-04, from the tree at `HEAD` and the pinned vendor checkout: the scene and static-transform
values by parsing the generated files; the mesh bounds, vertex counts, subset relation and
volumes by reading the committed STLs directly; the link, joint, mimic and collision-origin
counts by expanding the shipped xacro; the MoveIt behaviour from the 2.12.4 tag and from the
headers and `strings` of the shipped libraries in this image. **None of it is taken from any
campaign directory or from §2.5's list** (rule H), and **nothing in `model/`, `workspace/src/`,
`tools/`, `tests/`, `scripts/`, `assets/` or `external/` was edited** (§0, V1).
