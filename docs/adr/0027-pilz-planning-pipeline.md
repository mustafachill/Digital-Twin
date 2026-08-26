# ADR-0027: Plan station-to-station motion with Pilz, keeping OMPL as the fallback

- **Status:** Accepted — **decided, not yet implemented.** No generated MoveIt configuration
  declares a Pilz pipeline today: `cite_generated/moveit/cell_a_arm_*_ompl_planning.yaml`
  lists `planning_pipelines: [ompl]` and nothing else. This record is the decision; the
  configuration and the scenario evidence follow it (P7).
  One supporting claim in this record — the size and composition of the planning scene — is
  now wrong and is corrected below; **nothing that was decided is withdrawn**, and the
  argument the claim supports is strengthened rather than weakened by the correction. See
  the section "Correction — 2026-08-26: the planning scene carries 12 objects, not 11",
  immediately after this block.
- **Date:** 2026-08-25
- **Deciders:** Project owner, on the determinism findings from the Phase 1.C review wave
- **Related:** [ADR-0006](0006-moveit2-motion-planning.md) (MoveIt 2 — this decision sits
  *inside* it and does not reopen it), [ADR-0026](0026-joint-space-goals-on-under-six-dof-arms.md)
  (goal *specification*; complementary, see below), [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [L2](../architecture/L2-control-and-hal.md), [L3](../architecture/L3-capabilities.md),
  [cross-cutting-testing.md](../architecture/cross-cutting-testing.md), charter §4 (P4, P8)

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
