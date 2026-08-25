# ADR-0023: Simulate a grasp by attachment, triggered by contact

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0003, ADR-0005, ADR-0022, [L1](../architecture/L1-description-and-assets.md), [cross-cutting-testing.md](../architecture/cross-cutting-testing.md)

## Context

Phase 1.D requires "real grasping" and a line that "runs a continuous cycle without
intervention". Phase 1.C requires a `Pick` skill that actually picks.

A parallel gripper holding a box by friction alone is one of the least reliable things a
rigid-body simulator does. It depends on contact stiffness, friction coefficients, the
solver's iteration count and the physics timestep, and it fails by the object slowly
sliding out or by being flung across the cell. That behaviour is also *timestep-sensitive*,
which collides directly with
[`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md): scenarios must be
deterministic under a fixed seed, and "a non-deterministic scenario test is worse than no
test: it trains people to re-run until green."

So the question is not "which is more physically honest" but "what makes a continuous,
repeatable, sensor-driven cycle testable" — while not weakening the sim/hardware guarantee
that everything above `ros2_control` rests on.

Verified in the container on 2026-08-24: Gazebo Harmonic ships
`gz-sim-detachable-joint-system`, `gz-sim-contact-system` and `gz-sim-touchplugin-system`,
so the mechanism below is built on upstream components rather than on something we must
invent. Also verified: the vendor gripper expands with real collision geometry on its
finger links, so contact between pad and work-piece is detectable.

## Options considered

### Option A — Friction only
Tune surface friction, contact stiffness, solver iterations and gripper effort until a box
is held.

Rejected as the primary mechanism. It is the most physically honest option and it is the
one that makes scenario tests flaky. It also couples grasp reliability to the physics
timestep, so a performance change in Phase 3 would silently break Phase 1's tests. It is
not rejected as *wrong* — it stays available for a deliberate physics-fidelity study, which
is a different activity from a line cycle test.

### Option B — Vacuum end-effector instead
Far easier to simulate reliably. Rejected: the charter names parallel grippers as the
reference platform, and switching the reference to dodge a simulation difficulty would make
the twin model an end-effector the cell does not have.

### Option C — Contact-triggered attachment
A first-party Gazebo system plugin that creates a `DetachableJoint` between the gripper and
a graspable object when the gripper's pads are in contact and the gripper is closing, and
breaks it when the gripper opens. Chosen.

## Decision

`cite_simulation` provides a Gazebo Harmonic system plugin — **a simulation fidelity aid,
not a control path** — which:

1. Watches contacts on the gripper pad links of an arm, via Harmonic's contact system.
2. Attaches a `DetachableJoint` between the gripper's tool link and a work-piece **only
   when** both pads are in contact with the same graspable model **and** the gripper's
   `drive_joint` is commanded closed beyond a threshold.
3. Detaches when the gripper is commanded open beyond a threshold.
4. Publishes its attach/detach transitions as typed events, so a scenario can assert on
   them rather than inferring from pose.

**The critical property, stated so it is not eroded later: nothing above `ros2_control`
knows this plugin exists.** The `Grasp` skill commands `GripperCommand` on
`<asset_id>_gripper_controller` ([ADR-0022](0022-gripper-as-ros2-control-controller.md))
and nothing else, in simulation and on hardware alike. The plugin observes the *result* of
that command inside the simulator, exactly as the physical world would. There is no
sim-only branch, no `if simulation` in any skill, and no topic that exists on one path and
not the other. This is what keeps [ADR-0005](0005-ros2-control-sim-real-boundary.md) intact.

Which objects are graspable, and the pad links, are generated from the L0 model — not
hardcoded in the plugin. The plugin is mechanism; which things exist is data (P5).

## Consequences

### What this gets us
- A grasp that holds, repeatably, under a fixed seed — which is the precondition for the
  continuous-cycle scenario being a test rather than a demonstration.
- Grasp success stops depending on the physics timestep, so tuning physics for real-time
  factor in Phase 3 does not silently break Phase 1's tests.
- Attach and detach are observable events, so `Pick` can be asserted on directly rather
  than by watching a pose and hoping.
- The pattern is reusable for the vacuum end-effector the charter defers.

### What this costs us
- **The simulation now flatters us about grasping.** A grasp that would slip in reality
  will hold here. That is a real fidelity loss and it must be stated wherever grasp results
  are reported — this simulation does not evidence that a grasp is mechanically sound. P8
  applies: any claim about grasp reliability needs a measurement against hardware, and this
  plugin cannot provide one.
- A C++ Gazebo system plugin to write, test and maintain, plus its L0 schema for graspable
  objects and pad links.
- The attach threshold is a tuning parameter, and a badly chosen one produces a gripper
  that grabs things it is merely near. It needs a test that a *near-miss does not attach*,
  not only that a correct grasp does.
- Two mechanisms now exist for object contact — real friction for everything else,
  attachment for grasping — and someone will eventually be confused about which is acting.
  The plugin's events are what disambiguate it.

### What we will have to revisit
When Phase 2 compares simulated and physical grasping under `VALIDATED` mode, this plugin
is the most likely source of divergence and the first thing to examine. If the divergence
matters, the answer is to add a friction-based mode for fidelity study — kept as a separate,
explicitly-selected configuration — rather than to make the attachment gradually more
physical, which would recreate the flakiness this decision exists to avoid.
