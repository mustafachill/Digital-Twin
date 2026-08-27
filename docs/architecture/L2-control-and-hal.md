# L2 — Control and hardware abstraction

- **Status:** `PARTIAL`.
  **Built:** one `ros2_control` controller manager per arm, hosted in Gazebo by
  `gz_ros2_control`, with **9 controllers active across three arms** — asserted by
  `./scripts/scenario bringup`. Controller configuration, MoveIt configuration and the
  planning scene are all generated from L0; `cite_facility/planning_scene_loader.py` applies
  the scene per arm and reads it back rather than trusting the service result. The gripper
  runs as a `ros2_control` controller ([ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md))
  and its stall is now the sole evidence that a part is held, no simulation plugin having
  survived to forge it ([ADR-0029](../adr/0029-simulated-grasping-by-friction.md)).
  **Built:** the planning pipelines. Each arm's `move_group` loads Pilz and OMPL from a
  generated `cell_a_arm_*_planning_pipelines.yaml` and plans with Pilz PTP by default
  ([ADR-0027](../adr/0027-pilz-planning-pipeline.md)). A launch test drives the real
  `move_group` against the real generated files and requires both pipelines to load, PTP to
  plan, an identical request to return a byte-identical trajectory, and — the assertion this
  layer's safety rests on — a PTP path through a **named** object in the real generated
  planning scene to be refused, with its complement proving the refusal came from the scene.
  Mutation-checked, and observed refusing a real path during `continuous_line`.
  **Built with a stated residual:** that gate checks trajectory **waypoints** and
  interpolates nothing between them, at Pilz's fixed 0.1 s sampling. An object thinner than
  one waypoint step can lie between two checked states. The step, the arithmetic and the two
  ways it can grow are in the ADR's 2026-08-27 correction; the number is not repeated here.
  **Built, and narrower than its name:** an execution-side mistracking detector. Every
  generated `JointTrajectoryController` now carries a `constraints:` block — `goal_time`,
  and per-joint `trajectory` and `goal` tolerances — from the arm type in L0
  ([ADR-0036](../adr/0036-execution-side-trajectory-tolerances.md)). Until it existed the
  controller ran any trajectory to the end and reported `SUCCEEDED` however badly it
  tracked, because every tolerance defaults to `0.0` and `0.0` disables the check; that
  silence reached `Pick` as a successful pick. A launch test drives two real controller
  managers over mock hardware and requires a tracked trajectory to succeed, a held joint to
  abort as `PATH_TOLERANCE_VIOLATED`, and an error between the two thresholds to abort as
  `GOAL_TOLERANCE_VIOLATED` — which is what shows the two are read as two numbers.
  **It is a detector, not a protective measure**, and it must not be cited as one: it
  reports after the fact, and what stops an arm driving into a fixture remains the vendor
  controller's torque limiting and physical guarding (charter §3.2).
  **Two residuals are stated rather than implied.** The tolerance values are UFACTORY's own
  for the xArm 5, *copied* from the vendor configuration at the pinned commit and **not
  measured on this stack** — no healthy-run following error has been sampled, because that
  is observable only under Gazebo. And the path tolerance detects a joint that is *held*,
  not a graze that deflects the arm and lets it continue; that case is still invisible.
  **Not built:** the safety layer. Its enforcement point in the diagram below does not exist
  — see [cross-cutting-safety.md](cross-cutting-safety.md).
  **Still enforced at planning only:** the acceleration and deceleration ceilings. ADR-0036
  bounds position error, not the rates that produced it, and `enforce_command_limits` builds
  its limiter from the URDF `<limit>` element, which has no acceleration or deceleration
  field. A deceleration ceiling the physical arm cannot honour is caught by nothing here, on
  either backend.
  **Not exercised:** the physical hardware path (Phase 2). The backend is declared per
  instance in L0, and a plan naming a non-simulated backend is refused at the ROS boundary
  unless `CITE_ALLOW_HARDWARE=1` is set (`cite_bringup/cite_bringup/plan.py`).
  **Not held:** the configured rate. The model asks for 150 Hz; `joint_states` was measured
  at roughly 21 Hz at a real-time factor of 0.14 (see
  [ADR-0028](../adr/0028-convex-hull-collision-meshes.md)).
- **Related:** [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [ADR-0006](../adr/0006-moveit2-motion-planning.md), [ADR-0027](../adr/0027-pilz-planning-pipeline.md), [ADR-0036](../adr/0036-execution-side-trajectory-tolerances.md), [cross-cutting-safety.md](cross-cutting-safety.md)

## Responsibility

L2 is where a command becomes motion. It owns the controller stack, motion planning, and —
critically — **the boundary between simulation and physical hardware.**

> This is the most important layer in the system. It is what separates a digital twin from
> a simulation. If P2 breaks here, every claim the project makes above this line becomes
> unfounded.

## Owns

- `ros2_control` controller manager, controllers, and their configuration (generated from L0).
- Hardware interfaces: `gz_ros2_control` for simulation, a vendor interface for the
  physical arm.
- MoveIt 2: kinematics, planning scene, collision checking, trajectory generation.
- The safety layer's enforcement point — no command reaches a hardware interface without
  passing it ([cross-cutting-safety.md](cross-cutting-safety.md)).

## Does not own

- **What to move, or why.** L2 executes; L3 decides.
- Which hardware backend is loaded. That is configuration generated from L0 and selected
  by L5's mode.
- Task sequencing, handoff, recovery policy — all L4.

## Interfaces

**Consumes:** robot descriptions and controller configuration from L1/L0; the planning
scene derived from L0/L1.

**Exposes upward:** `FollowJointTrajectory` actions, joint state, controller state, and
MoveIt planning services — under names that are **identical** in simulation and on
hardware.

## Design

### The boundary, concretely

```
                        L3 skills
                            │
                            │  identical action and topic names in both cases
                            ▼
              ┌─────────────────────────────┐
              │   ros2_control              │
              │   controller manager        │
              │   + controllers             │
              └─────────────────────────────┘
                            │
                            │  hardware interface — the ONLY thing that differs
              ┌─────────────┴─────────────┐
              ▼                           ▼
   ┌────────────────────┐      ┌────────────────────┐
   │ gz_ros2_control    │      │ vendor interface   │
   │ (simulation)       │      │ (physical arm)     │
   └────────────────────┘      └────────────────────┘
              │                           │
              ▼                           ▼
      Gazebo Harmonic              The real xArm
```

Everything above the controller manager is unaware of which branch is active. Controller
names, joint names, command interfaces, state interfaces, action names, and frame names
are identical, because all of them are generated from L0.

### Why this survives contact with reality

The guarantee is fragile in exactly one way: a single hardcoded name that differs between
paths breaks it, and the break is invisible until someone runs on hardware — which is the
most expensive possible moment to discover it.

Three defences:

1. **Generation.** Names come from L0, so there is no opportunity to write two.
2. **`safety-auditor`.** Audits every motion path, including whether a simulation-only
   assumption can be reached on the hardware path.
3. **`tester`.** Verifies interface parity as a standing guarantee on every run.

### Mixed fleets are ordinary

Hardware arrives incrementally, so one physical arm and two simulated ones must be a
configuration rather than a special case. Because the backend is selected per robot
instance from L0, it is. Nothing above L2 changes, and nothing in L2 knows the fleet is
mixed.

### MoveIt's planning scene comes from L0

The obstacles MoveIt plans against and the obstacles in the simulator are generated from
the same source. They cannot disagree — which matters, because a planner with an
incomplete scene generates confidently unsafe trajectories.

**It matters more under Pilz than it did under OMPL.** A sampling planner treats the scene
as something to route around; a trajectory generator treats it as something to be checked
against after the fact. An object missing from the scene is a collision nobody planned
around either way, but under Pilz there is one adapter between that object and a real
motion rather than a search that never proposed the path.

### Which planner plans, and what a refusal means

Both pipelines are loaded per arm from L0; Pilz PTP plans, and OMPL answers only what Pilz
refuses. The decision, its cost, and the measured limits of Pilz's LIN generator on this
arm are [ADR-0027](../adr/0027-pilz-planning-pipeline.md) — read its 2026-08-27 correction
before assuming a Cartesian path is available.

Two consequences land in this layer.

- **A refusal is a normal outcome to design for**, not an exception. L2 reports it; L4's
  recovery has to tell "Pilz refused this straight path" from "the pose is unreachable",
  and those are different result codes ([ADR-0026](../adr/0026-joint-space-goals-on-under-six-dof-arms.md)).
- **Nothing above L2 knows which planner answered.** The pipeline is named in the request
  and resolved inside `move_group`, so the identical call plans in simulation and on
  hardware. P2 is untouched by this, and any change that makes a skill branch on the
  pipeline breaks it.
- **No error code tells a collision refusal from a geometric one.** Both come back as the
  generic `FAILURE`. The **only** discriminator is whether a trajectory is attached: a path
  generated and then rejected by `ValidateSolution` carries the rejected trajectory, and a
  path refused during generation carries none. A consumer must not read an attached
  trajectory as a plan, and must not branch on the code. Both halves are pinned by tests,
  and the enumeration showing nothing can execute a rejected trajectory today is in
  [ADR-0027](../adr/0027-pilz-planning-pipeline.md).

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Name differs between sim and hardware | Works in simulation, fails or misbehaves on hardware | Generation from L0; `safety-auditor`; parity check in `tester` |
| Controller joint names ≠ description | Spawner times out; the error names the spawner, not the mismatch | `model-validator` interface matching |
| Planning scene missing an obstacle | Confidently unsafe trajectory | `model-validator`; `safety-auditor` |
| Pilz path crosses a scene obstacle and `ValidateSolution` does not refuse it | A straight line through a table, executed | `test_9_a`/`test_9_b` in `cite_skills` — the only test in the repository that catches removal of this gate ([ADR-0027](../adr/0027-pilz-planning-pipeline.md)) |
| Obstacle thinner than one waypoint step lies between two checked waypoints | A collision the gate never saw | **Nothing** — a stated residual of the 0.1 s sampling, not a defect with a fix pending ([ADR-0027](../adr/0027-pilz-planning-pipeline.md)) |
| A caller distinguishes refusals by MoveIt error code | A rejected trajectory treated as a plan | Nothing automatic — the codes are the same; see "Which planner plans" above for the only discriminator |
| Command path bypassing the safety layer | Unexpected motion | `safety-auditor` — Critical, blocks merge |
| Controller update rate not held under load | Missed deadlines; degraded tracking | `performance-engineer` |
| Sim-only flag reachable on the hardware path | Limits disabled on a real arm | `safety-auditor` — Critical |

## Open questions

- **Which vendor hardware interface.** `xarm_ros2` provides one; whether it meets our
  safety-layer requirements unmodified is a Phase 2 question, and may need a patch
  ([ADR-0008](../adr/0008-external-dependencies-via-vcstool.md)).
- **Real-time requirements.** Whether the controller loop needs a real-time kernel, and
  whether that is compatible with containerized execution
  ([ADR-0009](../adr/0009-docker-primary-environment.md)).
- **Whether a stall is enough evidence of a grasp on hardware.** In simulation it is: the
  pads stop short of the commanded width and the controller reports
  `stalled=true, reached_goal=false` ([ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md)).
  Nothing has been run on a physical xArm, so whether the vendor gripper reports the same
  shape under the same conditions is a Phase 2 question.

*(The gripper's control interface is no longer open: it is a `ros2_control` controller,
decided in [ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md).)*
