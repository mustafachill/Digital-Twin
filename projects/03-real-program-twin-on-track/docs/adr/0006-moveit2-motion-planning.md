# ADR-0006: Use MoveIt 2 for motion planning

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0005, `docs/architecture/L3-capabilities.md`

## Context

The L3 capability layer exposes robot-agnostic skills — `MoveTo`, `Pick`, `Place`,
`Transfer`. Each needs collision-aware motion planning against a scene containing the
conveyors, tables, fixtures, and the other arms sharing the workspace.

The v1 workspace never executed real motion; pick and place were two-second timers. Every
motion capability is therefore built from scratch, and the planning stack is chosen now.

## Options considered

### Option A — Hand-written joint trajectories
Precomputed poses interpolated by the trajectory controller. Simple, and adequate for a
fixed demonstration. Rejected: no collision awareness, so nothing prevents an arm from
striking a conveyor or another arm; and every layout change invalidates every stored pose,
which defeats ADR-0004.

### Option B — MoveIt 2
The ROS 2 ecosystem's manipulation planning framework: kinematics, collision checking
against a live planning scene, trajectory generation, and time parameterization. Chosen.

### Option C — A dedicated planning library behind our own interface
More control, less machinery. Rejected: we would rebuild MoveIt's planning scene, collision
checking, and controller integration to gain flexibility the project has no use for.

## Decision

Use **MoveIt 2** for kinematics, collision-aware planning, and trajectory generation.
Skills at L3 wrap it; nothing above L3 talks to MoveIt directly.

The planning scene is populated from the L0 facility model (ADR-0004), so the obstacles
MoveIt plans against and the obstacles in the simulator come from the same source and
cannot disagree.

## Consequences

### What this gets us
- Collision-aware planning against a scene that is correct by construction.
- Robot-agnostic capability: swapping an xArm 5 for an xArm 7 or another manufacturer's
  arm changes the description, not the skills (P9).
- A large, maintained ecosystem — planners, IK solvers, visualization, debugging tools.

### What this costs us
- MoveIt 2 is a heavy dependency with a real learning curve and a large configuration
  surface. Its configuration must be generated (ADR-0004) or it becomes another place
  facts are hand-written.
- Planning latency is variable. Orchestration at L4 must treat motion as asynchronous and
  potentially slow, never assume a bounded planning time. Behaviour trees (ADR-0007) handle
  this well; a state machine would have struggled.
- Planner behaviour is stochastic for sampling-based planners. Scenario tests must assert
  on outcomes and constraints, not on exact trajectories, or they will be flaky.
- Wrong collision geometry now produces confidently unsafe plans, reinforcing the
  `model-validator` role.

### What we will have to revisit
If planning latency proves incompatible with cycle-time targets, the response is a
cached-plan or precomputed-motion layer *behind the L3 skill interface* — not abandoning
MoveIt, and not letting anything above L3 learn about it.
