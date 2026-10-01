# ADR-0005: Use ros2_control as the simulation/hardware boundary

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0003, ADR-0011, charter §4 (P2), `docs/architecture/L2-control-and-hal.md`

## Context

The defining property of a digital twin, as opposed to a simulation, is that the same
control code drives both the virtual and the physical asset. If simulation and hardware
need different code, then work validated in simulation proves nothing about hardware, and
the twin's central claim collapses.

The v1 workspace had no hardware path at all, so the question was never forced. It must be
answered before any control code is written, because retrofitting a hardware abstraction
onto code that assumed simulation is a rewrite.

## Options considered

### Option A — An application-level abstraction
Define our own interface and implement it twice, once against Gazebo and once against the
xArm SDK. Rejected: it duplicates what `ros2_control` already provides, and every
controller, planner, and tool in the ROS ecosystem expects `ros2_control`'s interfaces.
We would be maintaining a parallel abstraction to gain nothing.

### Option B — Direct vendor SDK, with a simulation shim
Drive the xArm SDK directly on hardware and fake it in simulation. Rejected: it makes the
robot type a load-bearing assumption throughout the stack, defeating P9, and the simulation
path is a mock rather than a physics model.

### Option C — `ros2_control` as the boundary
One controller stack. `gz_ros2_control` provides the hardware interface in simulation; a
vendor hardware interface provides it on the physical arm. Chosen.

## Decision

**`ros2_control` is the simulation/hardware boundary.** Above it, nothing knows which is
in use. Controller names, joint names, command and state interfaces, action names, and
frame names are **identical** in both cases. The only thing that differs is which hardware
plugin the controller manager loads, selected by configuration generated from the L0 model.

Breaking this is the highest-severity defect the project recognises (P2).

## Consequences

### What this gets us
- Sim-to-real transfer is structural rather than aspirational. A skill validated in
  simulation runs on hardware unmodified, because it never knew the difference.
- Mixed fleets work: one physical arm and two simulated ones is a configuration, not a
  special case. This matters directly, since hardware arrives incrementally.
- MoveIt 2, controller tooling, and `ros2 control` introspection all work unchanged
  against both.

### What this costs us
- Discipline in naming. A single hardcoded controller or frame name that differs between
  paths silently breaks the guarantee, and the break is invisible until someone runs on
  hardware. Enforced by generation from the L0 model (ADR-0004) and checked by
  `model-validator` and `safety-auditor`.
- `ros2_control`'s model constrains us: it assumes a joint-level command/state interface,
  which fits manipulators well and would fit some future asset types poorly.
- Simulation fidelity now matters more. Under this design, a badly modelled arm is not a
  cosmetic problem — it invalidates simulation-based validation. This is why inertia and
  collision geometry validation is a first-class agent role rather than a checklist item.

### What we will have to revisit
If an asset type is added that `ros2_control` cannot represent. In that case it gets its
own boundary at the same architectural level, not an exception carved into this one.
