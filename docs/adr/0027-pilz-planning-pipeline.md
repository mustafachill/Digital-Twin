# ADR-0027: Plan station-to-station motion with Pilz, keeping OMPL as the fallback

- **Status:** Accepted (corrected 2026-08-26 and 2026-08-27) — **the decision stands in full
  and nothing in it is withdrawn.** Two supporting claims have been measured false, newest
  first in the record.
  The **2026-08-27** correction is the larger one: this record described itself as *decided,
  not yet implemented* and named three files that no longer exist, and its sentence about
  what LIN buys is true for far fewer motions than it reads. The configuration is built. See
  the section "Correction — 2026-08-27: the pipeline is built, and LIN is available for far
  fewer moves than this record implies", immediately after this block.
  The **2026-08-26** correction, on the size and composition of the planning scene, follows
  it and is left exactly as it stood.
  **Implemented and merged**, at `ee60688` on `feature/phase-1`, 2026-08-27. The Critical
  raised against it — nothing asserted that a Pilz path through a known collision object is
  refused — **is closed**, mutation-checked and confirmed by the gate firing on a real path
  in the running cell. One residual is open and is stated rather than closed: the collision
  gate checks waypoints and does not interpolate between them. The newer correction has
  both.
- **Date:** 2026-08-25
- **Deciders:** Project owner, on the determinism findings from the Phase 1.C review wave
- **Related:** [ADR-0006](0006-moveit2-motion-planning.md) (MoveIt 2 — this decision sits
  *inside* it and does not reopen it), [ADR-0026](0026-joint-space-goals-on-under-six-dof-arms.md)
  (goal *specification*; complementary, see below), [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [L2](../architecture/L2-control-and-hal.md), [L3](../architecture/L3-capabilities.md),
  [cross-cutting-testing.md](../architecture/cross-cutting-testing.md), charter §4 (P4, P8)

## Correction — 2026-08-27: the pipeline is built, and LIN is available for far fewer moves than this record implies

**This is the second correction on this record.** The first — on the size of the planning
scene — is immediately below this section and is left exactly as it stood.

### What was written

Two claims, in two places.

The **status block** said the decision was *"Accepted — decided, not yet implemented"*, and
named its evidence: *"No generated MoveIt configuration declares a Pilz pipeline today:
`cite_generated/moveit/cell_a_arm_*_ompl_planning.yaml` lists `planning_pipelines: [ompl]`
and nothing else."*

Under *What this gets us*, this record lists *"LIN and CIRC available for the moves where a
defined Cartesian path is the requirement rather than a preference."*

### What is true — the configuration exists

Merged to `feature/phase-1` at **`ee60688`, 2026-08-27** — the one dated reference to where
this landed; every other document points here rather than repeating it.

- L0's `xarm5` type declares the pipeline choice — `default_pipeline`,
  `default_planner_id: PTP`, `fallback_pipeline`, `fallback_planner_id` — a per-joint
  `max_deceleration_rad_s2`, and four Cartesian ceilings. Which planner plans is data (P5),
  because it is a claim about *this arm*.
- The generator emits **`cell_a_arm_*_planning_pipelines.yaml`** per arm, declaring both
  pipelines with `default_planning_pipeline: pilz_industrial_motion_planner`, alongside
  `cell_a_arm_*_cartesian_limits.yaml`. The files the status block named —
  `cell_a_arm_*_ompl_planning.yaml` — were **renamed** and no longer exist: the old name
  stopped being true when the file began declaring two pipelines.
- The L3 skill server runs one whole IK-and-plan pass with the preferred planner and repeats
  the pass with the fallback **only** on a planning failure, never on `NoIkSolution` — which
  is a statement about the arm's reachable set that no planner changes (ADR-0026) — and
  never when the preferred planner is a Cartesian one, because there the shape of the path
  *is* the contract and a joint-space rescue would satisfy the request by ignoring it. A
  declined fallback is logged as such, so the decision is not silent. Nothing branches on
  the answer: the pipeline is named in the request and resolved inside `move_group`, so the
  identical call plans in simulation and on hardware and P2 is untouched.

**The Decision's clause that the fallback "is recorded so the frequency is visible rather
than inferred" is met, and at what strength.** The skill server logs both a taken and a
declined fallback, and `pick_and_place` and `continuous_line` count both occurrences into
the scenario report CI uploads — reported, never gated, and deliberately without a
threshold, because nothing has measured what a normal rate on this cell is (P8). It is not
an L6 metric and is not a substitute for one; it is a number in a report that already
existed.

**Two claims this record's first implementation stated as fact were wrong, and the
remediation corrected them rather than deleting the values.**

- *"Pilz refuses to build a PTP generator for a group whose joints do not all declare a
  deceleration limit."* Omitting the key would **not** have produced that refusal.
  `pilz_industrial_motion_planner/src/joint_limits_aggregator.cpp` sets
  `max_deceleration = -max_acceleration` whenever an acceleration limit is present and a
  deceleration limit is not, so the derived value would have been exactly the `-2.0` the
  generator emits; the refusal needs the *acceleration* ceiling to be absent as well. The
  key is stated anyway, for a different and better reason: it makes the braking ceiling a
  decision about this arm rather than an accident of its acceleration ceiling, and derived,
  the two could never differ. The value stayed; the reasoning changed.
- *The four Cartesian ceilings are "chosen for this arm".* Three of them are ours. The
  fourth, `max_cartesian_rotational_velocity_rad_s: 1.57`, is MoveIt's own template default
  byte for byte. Describing all four as chosen made a copied number look like a measurement.
  They are placeholders: low enough not to be the interesting constraint, present so the
  pipeline can be constructed, and **consumed by no motion in this cell** — every motion is
  planned in joint space, and a Cartesian ceiling cannot in any case guarantee a joint stays
  inside its own, since the joint rate a tool velocity requires is `J⁻¹ ẋ` and grows without
  bound near a singularity.

What *is* true about the Cartesian limits is the load-bearing part: Pilz's parameter
listener declares all four without defaults, so a missing one is an uncaught
`rclcpp::ParameterUninitializedException` that takes `move_group` down while the pipeline
initialises, rather than a planner that declines a LIN request.

### What is true — LIN is usable on one motion shape, not on Cartesian paths generally

Measured against the real `move_group` and the real generated files on 2026-08-27:

| Motion | LIN | PTP |
|---|---|---|
| Straight down 0.05 m, orientation and base yaw fixed | SUCCESS, 12 points | SUCCESS |
| Straight down 0.10 m, same | SUCCESS, 18 points | SUCCESS |
| Along +x 0.05 m, same | SUCCESS, 12 points | SUCCESS |
| Joint 1: 0 → 0.30 rad (turns the base) | **refused, no trajectory** | SUCCESS |
| Along +y 0.05 m at fixed orientation | endpoint has no IK at all | — |

**LIN is usable exactly where the whole path stays in the vertical plane the arm's first
joint points at.** An approach and a retreat are that shape. Anything that turns the base is
not.

That is enforced rather than left to this paragraph: the generator **refuses** a Cartesian
planner as an arm's default when its planning group has fewer than six joints, and refuses
a planner id the pipeline does not register at all. The rule is stated in terms of the joint
count, not of this arm, so a six-joint arm added to the cell is not caught by it. A typo or
an empty id fails `./scripts/validate-model` rather than the first request.

The mechanism is kinematic. LIN interpolates the tool *pose* — position linearly,
orientation by spherical interpolation — and solves full six-DOF IK at every sample. The
xArm 5 has one base yaw, three parallel pitch joints and one wrist roll, so its tool axis is
confined to the plane the first joint points at. Turning the base sweeps that plane while
the interpolated orientation does not follow it, and the samples in the middle have no
solution at all. **This is the arm's kinematics and holds identically on the hardware** — it
is not a simulation artefact, and
[ADR-0026](0026-joint-space-goals-on-under-six-dof-arms.md) is what predicts it, in its own
words: *"on this arm every interpolated pose that leaves the arm's plane is unsolvable, so a
general straight line is not achievable."*

**Which of that table is pinned by a test, and which is not.** Two rows are committed as
launch-test assertions in `cite_skills/test/test_planning_pipeline.py`: LIN plans the
vertical 50 mm approach, and LIN is refused for the motion that turns the base, with an
empty trajectory. A third test is the complement — PTP must plan the goal LIN refused — so
the refusal cannot pass merely by the goal being unreachable. The remaining three rows and
the point counts are from **one measurement on one machine** and are asserted nowhere.

**The specific error code of the LIN refusal is unverified and two reports disagree.** The
implementing commit recorded `NO_IK_SOLUTION`; a tester who instrumented the response
afterwards recorded the generic `FAILURE` (99999), the same code a collision refusal
returns. The test pins neither — it asserts `!= SUCCESS` and an empty trajectory — so
nothing in the tree settles it, and this record no longer states one. Instrumenting the
response in `test_7` and asserting the code would settle it. **What the code is does not
change the conclusion**, which rests on the empty trajectory and on `test_8` planning the
same goal; and the section below is why the code was never the right thing to branch on
anyway.

### LIN is deliberately not wired into `Pick` or `Place`, and the fallback would hide why

Nothing in L3 asks for LIN. That restraint is correct, and it is recorded here as a decision
rather than left as an omission: `offset_along_tool_z` follows the **tool's** axis, and
whether that axis lies in the arm's plane depends on the grasp pose, which depends on where
the part sits, which depends on the part's yaw — which
[`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
records as varying.

A safety review added the sharp point: **the fallback would have concealed the boundary from
whoever wires LIN in.** Every refused LIN would be rescued by OMPL, and every scenario
assertion is about where the work-piece ends up — so a LIN approach refused on most parts
and quietly planned by OMPL instead would produce a green scenario and no signal at all.

**That hole is closed rather than left as advice.** The fallback now declines a request
whose preferred planner is a Cartesian one: where the shape of the path is the contract, a
joint-space rescue satisfies the request by ignoring it. The Cartesian planner ids come from
the generator through the bring-up plan, so which ids those are is stated once and not
repeated in the skill server. A declined fallback is logged, because the silent version of
that decision is indistinguishable from the bug it prevents. Whoever wires LIN into an
approach will now see the refusal.

### The determinism claim, stated at the size of its evidence

**Proven.** An identical request to one `move_group` process returns a byte-identical
trajectory: every point's positions, velocities, accelerations and `time_from_start`,
asserted in `test_planning_pipeline.py`. That is a *planner* property, and it is the whole
reason this record exists.

**Not proven.** Same seed, same trajectory *across runs*. Nothing has measured that.

**Suggestive, and not conclusive.** Across `pick_and_place` ×2 and `continuous_line` ×1 the
fallback was logged **zero** times, so every arm motion in those runs was answered by Pilz.
A reviewer noted that a zero count is equally consistent with the fallback mechanism being
inert, and nothing yet distinguishes the two — which is exactly the argument that made the
collision gate's mutation check necessary rather than optional. Both scenarios now count
taken and declined fallbacks into the report CI uploads, so the number is observed on every
run instead of being reconstructed from three.

**Physics remains non-deterministic**, which is the part no planner touches: the friction
stall differed between two seeded runs, 48.9 mm against 48.8 mm. Nothing here permits
reinstating the withdrawn scenario-determinism guarantee in
[`../architecture/cross-cutting-testing.md`](../architecture/cross-cutting-testing.md).

### The collision gate — what became load-bearing, and the evidence that it holds

This record is where a reader goes to learn what the planning scene must contain, so this
belongs here. *What this costs us* below already says Pilz fails on a collision rather than
routing around it — re-verified on 2026-08-27 against `moveit2`'s `jazzy` branch, where the
only collision call in `pilz_industrial_motion_planner/src/trajectory_functions.cpp` is
`scene->checkSelfCollision(...)`. The consequence was not drawn out: **`ValidateSolution` is
the sole environment-collision gate for every Pilz-planned motion in the cell.** It is the
response adapter that calls `planning_scene->isPathValid(...)` — read on the same date in
`moveit_ros/planning/planning_response_adapter_plugins/src/validate_path.cpp` — and the
generated pipeline file configures it for exactly that reason.

A component that became load-bearing and gained no assertion was the Critical. **It is
closed.** The evidence is recorded rather than the verdict, because the verdict is the part
that ages worst.

- **A pair of tests, not one.** `test_9_a` loads the cell's real generated planning scene,
  proves through `check_state_validity` that a particular joint-space interpolation has a
  clear start, a clear goal and an intermediate configuration inside a **named** generated
  object, and asserts the request is refused. `test_9_b` removes the objects and asserts the
  identical request then succeeds — without which the refusal in `9_a` could be coming from
  anywhere.
- **Mutation-checked, reproduced twice independently.** With `ValidateSolution` removed from
  Pilz's response adapters and the tree **regenerated rather than hand-edited**, `test_9_a`
  fails and names both the object and the position along the path: *"the default planner
  returned a path whose interpolation is inside \['conveyor_1'\] at 60% of the way along
  it."* Every other test in the file passed under that mutation. A tester established the
  broader fact: **no host test and no unit test anywhere in the repository asserts the
  response-adapter chain, and none pins `MODEL_HASH` to a literal**, so `test_9_a` is the
  only test in the repository that catches removal of this gate.
- **It fired on a real path in the running cell**, which is stronger evidence than any test.
  During `continuous_line`, `arm_1`'s `move_group` logged *"Found a contact between
  `table_pick` and `arm_1_right_finger` … PlanningResponseAdapter 'ValidateSolution' failed
  with error code INVALID_MOTION_PLAN"*; the skill server retried the next IK seed and
  planned clean. Without the gate that is a finger through the pick table.
- **It is anti-vacuous.** Emptying the planning scene makes `test_9_a` fail loudly — *"the
  premise of this test is gone, not its conclusion"* — rather than pass. All ten candidate
  configurations satisfy its premise today, in mirror-symmetric pairs across two conveyors
  at four distinct path fractions, and each is re-admitted by `move_group`'s own check at run
  time rather than trusted from the sweep that found it.

### The residual that is open: the gate checks waypoints and interpolates nothing between them

`PlanningScene::isPathValid` tests each waypoint of the finished trajectory. What the gate
can see is therefore decided by how far apart the waypoints are, and that spacing is Pilz's
sampling time: **0.1 s**. It is a C++ default argument —
`TrajectoryGenerator::generate(scene, req, res, double sampling_time = 0.1)`, which
`PlanningContextBase::solve` calls with three arguments — and **not** a ROS parameter, so it
cannot be declared in L0 and cannot be set from the generated file. It is asserted rather
than assumed: `test_4_b` measures the `time_from_start` spacing of a PTP trajectory and
fails if a MoveIt release changes it.

The exposure, stated at the size of its evidence:

- The smallest object in the generated planning scene is a **40 mm** break-beam housing, so
  a waypoint step exceeds it whenever the tool point moves faster than **0.40 m/s**.
- The generated pipeline file records the arm's joints as limited to 3.14 rad/s by the
  vendor description, scaled by the 0.35 velocity factor in the joint-limit file; at a 0.7 m
  reach that permits roughly **0.077 m** of tool travel between two checked waypoints —
  **1.92×** the housing. An object thinner than that step *can* lie strictly between two
  checked waypoints and be missed.
- **0.077 m is a single-joint figure and is representative, not an upper bound.** Several
  joints moving together move the tool point further per step.
- **A second path to a larger step exists and nothing sends it today.**
  `MoveTo.action` documents `velocity_scaling` as a fraction of *"the arm's configured
  limit"*, while `MoveGroupInterface::setMaxVelocityScalingFactor` treats it as a fraction of
  the **URDF** limit — so `velocity_scaling: 1.0` bypasses the 0.35 default and gives about
  **0.22 m** per step, **5.5×** the housing. That mismatch is in the interface
  documentation and **predates this decision**; it is flagged here because this is where its
  consequence lands, and fixing it belongs to whoever owns `cite_interfaces`.

Nothing here closes this. It is a residual of choosing a generator over a search, and it is
named so that it is not rediscovered as a mystery collision.

### What a caller sees: two refusals that no error code tells apart

An L3 consumer must know this, because the obvious way to tell the two refusals apart does
not work.

- **A collision refusal** — a path generated successfully and then marked invalid by
  `ValidateSolution` — returns the generic `FAILURE` (99999), **not**
  `INVALID_MOTION_PLAN` and not a collision-specific code, and **carries the rejected
  trajectory**: 31 points in the instrumented case. Both the code and the non-empty
  trajectory are pinned by `test_9_a`.
- **A LIN refusal** — refused during generation — was instrumented as `FAILURE` (99999)
  too, and **carries no trajectory**. The empty trajectory is pinned by `test_7`; the code
  is not, and see the note above on the disagreement about it.

So the error code discriminates nothing, and **the only discriminator is whether a
trajectory is attached** — which is pinned on both sides. That makes "can anything execute
the attached trajectory?" the load-bearing question, and it was answered by enumeration
rather than by inspection: three `plan(...)` call sites all compare `== SUCCESS`, the single
`execute(plan)` is reachable only from `PoseGoalFailure::None`, nothing branches on the
trajectory's contents, and `cite_skills` is the only `MoveGroupInterface` consumer in the
tree. A rejected trajectory therefore cannot reach an arm today.

**What this constrains.** A caller must not tell a collision refusal from a geometric one by
error code, and must not treat an attached trajectory as a plan. If MoveIt starts
distinguishing a collision refusal, the skill server can act on it — `test_9_a` fails and
says so, which is the intended way to find out.

### The adapter chain matches MoveIt's shipped default, after an earlier justification for diverging turned out to be wrong

The first implementation gave Pilz **no** request adapters and argued that it wanted none.
That argument was wrong in one place that matters and imprecise in two more, so the chain
now matches upstream byte for byte. Fetched on 2026-08-27 from
`moveit_configs_utils/default_configs/pilz_industrial_motion_planner_planning.yaml` on
`moveit2`'s `jazzy` branch, and identical on `main`: MoveIt gives this pipeline the same
four request adapters it gives OMPL. Taken one at a time, which is what the earlier argument
did not do:

- **`ResolveConstraintFrames` is performed by nothing else.** The day a goal names a frame —
  a pose target, or a path constraint on a subframe — its absence is a plan against the
  *wrong frame* rather than an error. This is the one that matters.
- **`CheckStartStateBounds`** decides whether a start state a hair outside its bounds is
  nudged back in or refused. Refusing it here would spend a whole fallback pass on a
  numerical epsilon and report it as the cell's geometry — precisely the signal this record
  exists to keep clean.
- **`ValidateWorkspaceBounds`** supplies a default sampling volume for unbounded joints and
  is inert for this fixed-base revolute arm. It is kept because matching upstream is cheaper
  to reason about than a divergence, **not** because it enforces a cell workspace, which it
  has never done.
- **`CheckStartStateCollision`** is subsumed by `ValidateSolution`, which checks every
  waypoint including waypoint 0.

`AddTimeOptimalParameterization` is still absent from Pilz's response adapters, and that
absence is deliberate: the trapezoidal profile *is* the output, and re-parameterising it
would discard the timing the limits produced and substitute a different one.

### How the error survived

Both halves have one shape, and it is the shape the 2026-08-26 correction already named:
**prose asserting something about generated artifacts, with nothing able to fail when the
artifacts change.** The status block named three files by path and stated their contents; the
files were renamed and their contents replaced, and no test, linter or link checker notices
that a sentence in an ADR names a path that no longer exists. `./scripts/doctor` checks that
ADR *references* resolve — it cannot check that an ADR's *claims* do.

The LIN sentence survived differently, and is the more transferable failure. It was written
from what Pilz offers as a planner, not from what this arm can do, and the two were never
compared until someone asked for a plan. ADR-0026 had already measured the constraint that
falsifies it, in this same repository, and this record links to ADR-0026 in its own metadata
block. **A capability listed from a vendor's feature set is an unverified claim about our
hardware, however well sourced it is about the vendor's.** Say which of our motions it
covers, or do not list it.

The implementation repeated the same class of mistake in its own comments, which is the
third data point and the reason to state the rule generally. It said Pilz would refuse every
request without a deceleration limit, and that four Cartesian ceilings had been chosen for
this arm. The first was a plausible inference from a documented error message that upstream
code makes unreachable; the second described a copied default as a decision. **Neither
needed a running system to check** — one was a conditional in
`joint_limits_aggregator.cpp`, the other a diff against MoveIt's template — and both were
written confidently and reviewed past. A rationale is a claim. Where the claim is about
someone else's code, read their code; where it is about a number, say where the number came
from.

## Correction — 2026-08-26: the planning scene carries 12 objects, not 11

**What was written.** In *What this costs us*, this record states that
`cite_generated/moveit/cell_a_planning_scene.yaml` carries **11** collision objects, and
enumerates them as "three break beams, three conveyors, three pedestals, two tables".

**What is true.** It carries **12**, and the enumeration is wrong in one term: there are
**four** break beams, not three. Counted on 2026-08-26 against the generated file at commit
`7f2d8f9` — twelve `- id:` entries under `collision_objects`, grouping by the `type` field
as four `break_beam`, three `belt_1200x400`, three `pedestal_600`, two `work_table_600`.

**Why it changed.** `station_transfer_1` is fed from outside the cell and had nothing to
observe, so its cycle fell through `AwaitTrigger` and came to rest polling `Detect` against
a region no sensor was in. `beam_pick` was added to `model/assets/instances/sensors.yaml`
to let the line start, and — because the planning scene is generated from the same resolved
bodies as everything else (ADR-0004) — it appeared in the scene without anyone editing the
scene. The count in this record was written against the model as it stood on 2026-08-25 and
was not re-derived afterwards.

**What survives, unchanged.** The decision, and the argument this figure supports. The
point being made is that a planner which fails rather than searches is acutely sensitive to
the scene being **complete**, and an extra sensor housing standing in an arm's approach is
exactly the kind of object that argument is about. A larger scene makes that cost larger,
not smaller.

**How the error survived.** It was a count of a generated artifact, written by hand into
prose. `./scripts/validate-model` proves the generated tree matches its generator; nothing
proves a sentence in a document matches the generated tree, and no test can fail when an
asset is added to L0 and a number in an ADR is not re-read. The transferable lesson is the
narrower one: **do not state the cardinality of a generated collection in prose.** Name the
file and let the reader count, or state the count with the date and commit it was counted
at — which is what the correction above does.

## Context

### Scenario determinism was documented as a fact and was never real

`cross-cutting-testing.md` listed "scenario determinism — same seed, same outcome" as a
standing guarantee the tester verifies on every run. It was not implemented and could not
have been. The document has since withdrawn the claim; this record is where the reason is
kept, because the reason decides a planner.

**MoveIt cannot seed OMPL, and exposes no parameter that would.** Verified twice
independently during the review wave, and reproduced a third time for this record inside
`cite-digital-twin:dev` on 2026-08-25:

| Check | Command | Result |
|---|---|---|
| MoveIt's OMPL interface mentions a seed at all | `strings libmoveit_ompl_interface.so.2.12.4 \| grep -ci seed` | **0**, out of 2553 strings |
| MoveIt's OMPL interface calls OMPL's seeding entry point | `nm -D -u libmoveit_ompl_interface.so.2.12.4 \| c++filt \| grep setSeed` | no such undefined symbol |
| OMPL offers one | `nm -D --defined-only libompl.so.1.7.0 \| c++filt \| grep 'RNG::setSeed'` | `T ompl::RNG::setSeed(unsigned long)` |

So the entry point exists in OMPL and MoveIt never reaches it. There is also no patch hook:
MoveIt is **apt-installed** (`ros-jazzy-moveit`, `infra/docker/Dockerfile:65`) rather than
pinned as source in `external/cite.repos`, which pins only `xarm_ros2`. ADR-0008's patch
mechanism applies to manifest entries, and MoveIt is not one.

**A third finding is decisive on its own: a seed would not buy determinism even if MoveIt
set one.** Two independent mechanisms defeat it, both read from the shipped sources:

1. **OMPL draws per-instance seeds from a process-global generator.**
   `ompl::RNG::RNG()` is `localSeed_(getRNGSeedGenerator().nextSeed())` — a mutex-guarded
   singleton handing out the next value of one shared `std::ranlux24_base` sequence
   (`ompl/util/src/RandomNumbers.cpp`). Which seed a given sampler receives therefore
   depends on the **order in which RNG objects are constructed across the process**, which
   across threads is not fixed. OMPL says so itself, in a string present in the shipped
   `libompl.so.1.7.0`: *"Random number generation already started. Changing seed now will
   not lead to deterministic sampling."*
2. **MoveIt's default termination is wall-clock.**
   `ompl_interface::ModelBasedPlanningContext::constructPlannerTerminationCondition(double,
   const std::chrono::time_point<std::chrono::system_clock, …>&)` — the deadline is a
   system-clock instant, so the number of iterations a planner completes varies with
   machine load. Two runs on the same seed on the same machine do different amounts of work.

Measured consequence, recorded before any of this was understood: `pick_and_place` run four
times under one identical seed produced **two distinct failure modes, each twice**, both
under DDS domain isolation.

### What `CITE_PHYSICS_SEED` does and does not buy

The seed is now plumbed: `scripts/scenario` decides it once per run and
`cite_bringup/launch/simulation.launch.py` passes it as `gz sim --seed`. Stated precisely,
because the previous absence of a consumer was papered over with a claim that was not true:

- `gz sim --seed N` reaches `ServerConfig::SetSeed()`, whose body is
  `math::Rand::Seed(_seed)` (`gz-sim8`, `src/ServerConfig.cc`). A seed of `0` is discarded
  by an `if (_seed != 0)` guard in `src/gz.cc`; our default, `20260824`, is not 0.
- `gz::math::Rand` is what **sensor noise and the comms systems** draw from. Scanning every
  shared object under `/opt/ros/jazzy/opt` for undefined references to `gz::math::v7::Rand`
  returns `libgz-sensors8`, the RF and acoustic comms systems, the odometry publisher, the
  multicopter controller and the render engines — and **no physics library**: neither
  `gz_physics_vendor` nor `gz_dartsim_vendor` references it.

So the seed does **not** seed the physics solver, does **not** reach OMPL, and does **not**
make a scenario reproducible. It must not be described as doing so.

### Why this forces a planner decision now

P4 makes determinism an architectural property rather than a testing convenience, and P8
says a claim of it has to be a measurement. With OMPL, the project cannot have either: the
stochastic component that decides whether a plan succeeds is unreachable from our
configuration, and the failure it produces is a coin flip that trains people to re-run
until green. The only remaining lever is to stop asking a sampling planner for the motions
that do not need sampling.

Two constraints on any answer are fixed. **ADR-0006 locked MoveIt 2** and is not being
reopened. **P2** — whatever plans in simulation must be the identical call on hardware, so
the answer must be configuration inside MoveIt, not a branch in a skill.

## Options considered

### Option A — Keep OMPL and accept non-determinism
Document the guarantee as withdrawn, assert only on outcomes, and move on.

Rejected because it leaves a failure mode with no diagnosis. The four-run measurement above
is the cost: a scenario that fails two different ways under one seed cannot be bisected, and
a Critical defect that reproduces half the time is indistinguishable from a fixed one.

### Option B — Patch MoveIt to seed OMPL
Add the `ompl::RNG::setSeed` call MoveIt is missing.

Rejected twice over. Mechanically, there is nowhere to put the patch: MoveIt is
apt-installed, not a manifest entry, so adopting this option means moving MoveIt into
`external/cite.repos` and building it from source — a large, permanent increase in build
time and maintenance for one call. And it would not work: findings 1 and 2 above mean a
correctly placed seed still yields different plans across runs, so we would carry a source
fork **and** an unearned determinism claim.

### Option C — Constrain OMPL to a single deterministic sampler
Configure a planner whose behaviour is reproducible.

Rejected. Every planner in `ompl::geometric` constructs `ompl::RNG` objects, and finding 1
applies to all of them regardless of which is selected. The construction order, not the
algorithm, is the problem.

### Option D — Adopt the Pilz Industrial Motion Planner for station-to-station motion
Pilz is a **trajectory generator**, not a search: MoveIt's own documentation describes it as
providing "a trajectory generator to plan standard robot motions like point-to-point,
linear, and circular", with PTP producing "fully synchronized point-to-point trajectories
with trapezoidal joint velocity profiles". No sampling means no RNG, which means the same
request produces the same trajectory. Chosen.

It costs nothing to obtain. `ros-jazzy-pilz-industrial-motion-planner` is version `2.12.4`
in the ROS 2 Noble repository — the same version as `ros-jazzy-moveit` — and
`ros-jazzy-moveit-planners` depends on it alongside `-ompl`, `-chomp` and `-stomp`. It is
**already installed in `cite-digital-twin:dev`**: `libpilz_industrial_motion_planner.so` and
`share/pilz_industrial_motion_planner` are both present. Adopting it adds no dependency,
changes no manifest, and does not touch ADR-0006 — Pilz is a pipeline *inside* MoveIt 2.

## Decision

**Station-to-station motion is planned with the Pilz Industrial Motion Planner. OMPL is
retained as a configured fallback for motions Pilz cannot solve.**

- Both pipelines are declared in the generated MoveIt configuration, from the L0 model, so
  which pipeline an arm uses is data and not a constant in a generator (P1, P5).
- Pilz is the default pipeline. A motion that Pilz refuses falls back to OMPL rather than
  failing the skill, and the fallback is recorded so the frequency is visible rather than
  inferred.
- This is a change to *configuration*, identical on both backends. No skill branches on the
  pipeline, and P2 is unaffected.

**Determinism remains a measurement, not a configuration claim.** Under P8, scenarios will
be run repeatedly rather than once, and the claim that a scenario is reproducible is earned
by that measurement or not made at all. Configuring a deterministic planner is a necessary
condition and not a sufficient one: Gazebo's physics solver is untouched by any of this, and
`cross-cutting-testing.md` keeps the guarantee marked as not met until repeated runs say
otherwise. Nothing in this record permits reinstating the withdrawn claim.

## Relationship to ADR-0026 — complementary, neither supersedes the other

They decide different halves of the same request and were taken within a day of each other,
which makes them easy to confuse.

| | ADR-0026 | ADR-0027 (this record) |
|---|---|---|
| Decides | how a goal is **specified** | which **pipeline** searches |
| Rule | a skill never hands MoveIt a Cartesian pose goal; it solves IK on the exact pose and plans to the resulting joint configuration | station-to-station motion is planned by Pilz, with OMPL as fallback |
| Scope | deliberately holds under **any** pipeline | deliberately says nothing about goal form |

ADR-0026 is written to survive this decision: a 5-DOF arm's reachable orientation set is a
property of the arm, not of the planner, so its first measurement table is true under Pilz
too. Under Pilz, planning to a joint configuration hands PTP the configuration it would
have had to derive by IK anyway. **Changing the pipeline does not reopen ADR-0026, and
ADR-0026 does not settle the pipeline.** Read both.

## Consequences

### What this gets us
- The stochastic component is removed from the motions that carry the line. A PTP request
  is a computation, so a failure is reproducible and can be bisected.
- Industrial motion semantics the cell actually wants: PTP between stations, and LIN and
  CIRC available for the moves where a defined Cartesian path is the requirement rather
  than a preference.
  **[Corrected 2026-08-27 — see the Correction section above.]**
- No new dependency, no source fork, no manifest change — the planner is already in the
  image, and ADR-0006 stands unmodified.
- The fallback keeps OMPL's search available exactly where it earns its non-determinism:
  the motions a straight interpolation cannot make.

### What this costs us
- **Pilz plans point to point and fails on a collision rather than routing around it.**
  Reading the shipped source on `moveit2` `main`, the Pilz generator performs no
  scene-collision search; its only collision call is `scene->checkSelfCollision(...)` during
  IK (`src/trajectory_functions.cpp`). A generated path that intersects a collision object
  is refused, not detoured.
- **That cost lands directly on the planning scene, which until this wave was empty.** Not
  one `CollisionObject` or `PlanningScene` was constructed anywhere in the repository, so
  every plan in the system was computed against a world containing only the arm. The scene
  is now populated — `cite_generated/moveit/cell_a_planning_scene.yaml` carries **11**
  collision objects (three break beams, three conveyors, three pedestals, two tables), and
  **[Corrected 2026-08-26 — see the Correction section above.]**
  `cite_facility/planning_scene_loader.py` applies them per arm and reads them back rather
  than trusting `ApplyPlanningScene`'s success. **A planner that fails rather than searches
  is far more sensitive to that scene being right**, and to it being complete: an object
  missing from the scene becomes a collision nobody planned around, and an object wrongly
  present becomes a motion that is refused for no reason.
- **A refusal is now a normal outcome to design for**, not an exception. L4's recovery has
  to distinguish "Pilz refused this straight path" from "the pose is unreachable", and the
  fallback to OMPL is what stands between a refusal and a stopped line.
- **Two pipelines to keep configured and generated**, which is one more artifact per arm and
  one more thing the L0 model must describe.
- **Cartesian limits.** LIN and CIRC need Cartesian velocity and acceleration limits that
  the arm type does not declare today; adding them is L0 work that this decision creates.

### What we will have to revisit
- **When repeated scenario runs measure what Pilz actually buys.** If `pick_and_place` under
  Pilz still varies across runs, the remaining variance is elsewhere — physics, timing, or
  the controller — and this record must not be read as having removed it.
- **If the OMPL fallback becomes the common path rather than the exception.** That would
  mean the cell's geometry is not suited to point-to-point motion, and the answer is the
  layout or the scene, not the planner. The fallback is instrumented so the question can be
  answered with a number.
- **When the planning scene grows a moving obstacle.** Neighbouring arms are deliberately
  absent from the generated scene — an articulated robot frozen at one pose is confidently
  wrong wherever it actually is — and a planner that refuses on collision makes L4's
  workspace arbitration load-bearing sooner than a searching planner would.
- **If a Pilz limitation we have not hit turns out to be disqualifying.** Its documented
  constraints include sequence planning being all-or-nothing and blend radii that must not
  overlap; neither bites at one station per cycle, and both would need re-examining when
  ADR-0024's handoff runs.
