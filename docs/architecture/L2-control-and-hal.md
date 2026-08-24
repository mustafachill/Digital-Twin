# L2 — Control and hardware abstraction

- **Status:** `DESIGNED` — no control packages exist yet. The physical hardware path is Phase 2.
- **Related:** [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [ADR-0006](../adr/0006-moveit2-motion-planning.md), [cross-cutting-safety.md](cross-cutting-safety.md)

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

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Name differs between sim and hardware | Works in simulation, fails or misbehaves on hardware | Generation from L0; `safety-auditor`; parity check in `tester` |
| Controller joint names ≠ description | Spawner times out; the error names the spawner, not the mismatch | `model-validator` interface matching |
| Planning scene missing an obstacle | Confidently unsafe trajectory | `model-validator`; `safety-auditor` |
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
- **Gripper control interface.** Whether the gripper is a `ros2_control` controller or a
  separate action server. Affects how L3's `Grasp` skill is shaped.
