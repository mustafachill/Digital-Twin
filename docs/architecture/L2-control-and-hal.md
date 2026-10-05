# L2 — Control and hardware abstraction

- **Status:** `PARTIAL`.
  **Built:** one `ros2_control` controller manager per arm, hosted in Gazebo by
  `gz_ros2_control`, with every controller the zone's bring-up plan declares active —
  asserted by `./scripts/scenario bringup`, which derives the set from the plan rather than
  counting to a number. `cell_b`'s one arm, `picker`, declares the joint-state broadcaster,
  the gripper, the arm's trajectory controller and the linear track's
  ([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md); read
  `workspace/src/cite_generated/bringup/cell_b_plan.yaml` rather than this sentence).
  Controller configuration, MoveIt configuration and the planning scene are generated from
  L0; `cite_facility/planning_scene_loader.py` applies the scene per arm and reads it back
  rather than trusting the service result. The gripper runs as a `ros2_control` controller
  ([ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md)) and its stall is what L3
  judges a grasp by; on the simulated side a plugin then holds the part still while L3 says
  it is held ([L1](L1-description-and-assets.md), ADR-0061/0065).
  **Built, never run against the arm: the physical side**
  ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)). It is the vendor plugin
  `uf_robot_hardware/UFRobotSystemHardware` plus `cite_hardware`'s three nodes, started by
  `hardware.launch.py` and tested against fake vendor services only. See "What else differs on
  the physical xArm" below.
  **Built: the planning pipelines.** Each arm's `move_group` loads Pilz and OMPL from a
  generated `<zone>_<arm>_planning_pipelines.yaml` and plans with Pilz PTP by default
  ([ADR-0027](../adr/0027-pilz-planning-pipeline.md)). A launch test drives the real
  `move_group` against the real generated files and requires both pipelines to load, PTP to
  plan, an identical request to return a byte-identical trajectory, and a PTP path through a
  **named** object in the real generated planning scene to be refused, with its complement
  proving the refusal came from the scene.
  **Built with a stated residual:** that gate checks trajectory **waypoints** and
  interpolates nothing between them, at Pilz's fixed 0.1 s sampling, so an object thinner than
  one waypoint step can lie between two checked states (ADR-0027's 2026-08-27 correction).
  **Built, and narrower than its name: an execution-side mistracking detector.** Every
  generated `JointTrajectoryController` carries a `constraints:` block — `goal_time`, and
  per-joint `trajectory` and `goal` tolerances — from the arm type in L0
  ([ADR-0036](../adr/0036-execution-side-trajectory-tolerances.md)); without it every tolerance
  is `0.0`, which disables the check. A launch test over mock hardware requires a tracked
  trajectory to succeed, a held joint to abort as `PATH_TOLERANCE_VIOLATED`, and an error
  between the two thresholds to abort as `GOAL_TOLERANCE_VIOLATED`.
  **It is a detector, not a protective measure**, and must not be cited as one: what stops an
  arm driving into a fixture is the vendor controller's torque limiting and physical guarding
  (charter §3.2). Its residuals are ADR-0036's: the values are UFACTORY's, copied and not
  measured on this stack; the path tolerance detects a *held* joint, not a graze; and
  `stopped_velocity_tolerance` cannot fire on a position-only command interface.
  **The detector's abort reaches L3 as `CONTROL_FAILED`**, the same value a malformed goal
  produces, so [L3](L3-capabilities.md) does not read the code: it asks the arm where it is
  ([ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md)). A trajectory that
  left the arm part-way is `MOTION_INTERRUPTED`; an abort at either endpoint is
  `EXECUTION_FAILED`.
  **Not built:** the safety layer. Its enforcement point in the diagram below does not exist
  — see [cross-cutting-safety.md](cross-cutting-safety.md).
  **Enforced at planning only:** the acceleration and deceleration ceilings. ADR-0036 bounds
  position error, not the rates that produced it, and `enforce_command_limits` builds its
  limiter from the URDF `<limit>` element, which has no acceleration field.
  **Not exercised: the physical hardware path** — the main tree's next step (Phase 2.B). The
  backend is declared per instance in L0, and a plan on which some (asset, side) declares that
  its backend reaches a physical machine is refused at the ROS boundary unless
  `CITE_ALLOW_HARDWARE=1` is set (`cite_bringup/cite_bringup/plan.py`). The refusal reads L0's
  `commands_physical_hardware`, not the backend's id
  ([ADR-0054](../adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md)). It binds at
  bring-up: it does not gate an individual command and cannot stop an arm already moving.
  **The `joint_states` rate** is configured at 150 Hz; what it holds under the real-time
  throttle ([ADR-0043](../adr/0043-hold-both-sides-to-the-wall-clock.md)) is not measured, and
  a much lower figure taken on a host confined to about one CPU core is a fact about a starved
  machine
  ([`2026-08-29-real-time-factor-conditions`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md)).
- **Related:** [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [ADR-0006](../adr/0006-moveit2-motion-planning.md), [ADR-0027](../adr/0027-pilz-planning-pipeline.md), [ADR-0036](../adr/0036-execution-side-trajectory-tolerances.md), [ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md), [cross-cutting-safety.md](cross-cutting-safety.md)

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
- Task sequencing and recovery policy. The program client sequences; there is no recovery
  policy in the main tree — a program step that does not succeed stops the program.

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
                            │  hardware interface — what differs (plus adapters, below)
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

**What else differs on the physical xArm, and why**
([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md), owner decision
2026-10-05). The vendor's `ros2_control` plugin exports joint1..5 only. It serves the linear
track and the gripper outside `ros2_control`: the track as `xarm_api` services, the gripper as
its own `GripperCommand` action. So on the physical side, the package `cite_hardware` (L2)
serves the **same names** the simulated controllers serve:

- **`track_adapter`** serves the track controller's `joint_trajectory` topic and publishes the
  track joint.
- **`gripper_relay`** serves the gripper controller's `gripper_cmd` action and publishes the
  drive joint.
- **`deadman`** holds the arm through the vendor's state until the twin boundary's heartbeat is
  healthy.

The physical side's controller manager therefore loads no track or gripper controller. Its
joint states come from three publishers and are merged per joint by their consumers. Names
stay byte-identical, which is what P2 requires as CLAUDE.md now words it; what differs is the
component behind them. The side starts from `cite_bringup`'s `hardware.launch.py`. Its
parameters are generated from L0 into `control/counterpart/`. Its vendor names come from
`ids.vendor_interface`. Its residuals are listed in
[cross-cutting-safety](cross-cutting-safety.md) and in `cite_hardware`'s README.

### Why this survives contact with reality

The guarantee is fragile in exactly one way: a single hardcoded name that differs between
paths breaks it, and the break is invisible until someone runs on hardware — which is the
most expensive possible moment to discover it.

Three defences:

1. **Generation.** Names come from L0, so there is no opportunity to write two.
2. **`safety-auditor`.** Audits every motion path, including whether a simulation-only
   assumption can be reached on the hardware path.
3. **`tester`.** Verifies interface parity as a standing guarantee on every run.

### A real arm and a simulated one are ordinary

The twin pairs one physical xArm 5 with one simulated one, so a side whose arm is physical
must be a configuration rather than a special case. Because the backend is selected per
robot instance — and per side — from L0, it is. Nothing above L2 changes, and nothing in L2
knows which side it is on.

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

- **A refusal is a normal outcome to design for**, not an exception. L2 reports it, and
  "Pilz refused this straight path" and "the pose is unreachable" are different result codes ([ADR-0026](../adr/0026-joint-space-goals-on-under-six-dof-arms.md)).
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
