# ADR-0023: Simulate a grasp by attachment, triggered by contact

- **Status:** Superseded by [ADR-0029](0029-simulated-grasping-by-friction.md) — the
  *decision* is reversed, not merely corrected: the attachment plugin is removed and
  simulated grasping rests on friction, after an 84-trial measurement. Nothing below is
  rewritten. It was also corrected on 2026-08-25, before it was superseded, and that
  correction still explains why the shipped plugin never matched this record — see the
  section "Correction — 2026-08-25: the attach condition was never implementable",
  immediately after this block. **Nothing in this record binds any longer.** Read
  ADR-0029 for what does.
- **Date:** 2026-08-24
- **Related:** ADR-0003, ADR-0005, ADR-0022, [L1](../architecture/L1-description-and-assets.md), [cross-cutting-testing.md](../architecture/cross-cutting-testing.md)

## Correction — 2026-08-25: the attach condition was never implementable

The Decision's condition 2 — attach "only when both pads are in contact with the same
graspable model **and** the gripper's `drive_joint` is commanded closed beyond a threshold"
— has never been evaluable, for two independent reasons. It is marked where it stands
rather than rewritten.

1. **One pad does not move.** The gripper's five finger joints were coupled by no mechanism
   at all. The measurement, and the reason, are in the correction to
   [ADR-0022](0022-gripper-as-ros2-control-controller.md) and are not repeated here. "Both
   pads in contact" was mechanically impossible.
2. **No pad link carries a contact sensor.** There is no `<sensor>` element anywhere in
   `workspace/src/cite_generated/description/` — verified by search on 2026-08-25. The only
   contact sensor in the cell is the one `tests/scenarios/pick_and_place.py` spawns on the
   work-piece itself. The predicate actually evaluated therefore reduced to "the work-piece
   is touching *something*", which is true while it sits on the table.

**What the implementation does now, which is not what this record specifies.**
`GraspAttachment::FindGraspable` requires the contact pair to be *(a declared graspable
model, this plugin's own model)*. That is a real improvement and closes the worst of it:
before, any arm closing on empty air anywhere in the cell attached the box. It is **not**
the both-pads condition above, and this record must not be read as describing shipped
behaviour.

**The consequence the project actually lived through.** **Every lift observed during Phase
1.C was produced by this plugin's `DetachableJoint`, not by a grasp.** The cost this record
already lists — "the simulation now flatters us about grasping" — anticipated a grasp that
would slip in reality holding here. What happened was a category worse: there was no grasp
at all, the fingers never closed on the work-piece, and the cycle looked correct end to end
regardless. Read that warning at this strength.

**The logging benefit did not hold as shipped.** This record lists "logs its attach and
detach transitions, so `Pick` can be asserted on directly" among the benefits. `gzmsg` is
verbosity level 3 and the cell launches at `-v 2`
(`cite_bringup/launch/simulation.launch.py`), so a plugin that failed to load and a plugin
that never triggered produced identical output: silence. Corrected since — the transitions
are logged at a level the cell actually prints. It earns its own line because
unobservability is a large part of why the defect above took as long as it did to find.

**Outstanding work, so that the both-pads condition can become real.** Not done; recorded
here as the shape of the work rather than as a plan that has been carried out:

- A `<gazebo reference="${prefix}left_finger">` contact sensor per pad, naming the
  collision `${prefix}left_finger_collision`. The collision element name in the converted
  SDF is `<link>_collision` — verified on 2026-08-25 by running `gz sdf -p` on a URDF whose
  collision elements are unnamed, which emitted `<collision name='left_finger_collision'>`.
  Naming anything else yields a sensor that silently reports nothing.
- Both finger links do survive the URDF→SDF conversion, because a real joint moves them:
  `left_finger_joint` and `right_finger_joint` are `revolute` in the vendor description at
  the pinned SHA. They are the exception to the lumping described under *What this costs
  us* below, which removes `link_tcp` and `xarm_gripper_base_link`.
- The world already loads `gz-sim-contact-system`
  (`workspace/src/cite_generated/worlds/cell_a.sdf`), so that prerequisite is met.
- The L0 end-effector type carries a single `attach_link_suffix`
  (`model/schema/asset_type.schema.json`, `tools/cite_tools/model/schema.py`). It needs a
  **list** of pad suffixes before two pads can be named at all.
- `FindGraspable` iterates every `ContactSensorData` in the world and discards the
  reporting sensor's identity, deciding on the contact pair alone. It therefore cannot
  distinguish one pad from two, whatever sensors exist.

**How the error survived.** The condition was written as a specification and never as a
test. Nothing in the tree ever evaluated "both pads", and nothing asserted that the
condition actually evaluated matched the one written here. The failure was then silent in
the strongest possible way: the scenario asserted that the work-piece left the table, and
it did — carried by the very mechanism whose trigger condition was wrong. **A test that
observes the intended outcome through the wrong cause passes.**

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
   **[Corrected 2026-08-25 — see the Correction section above.]** This condition has
   never been evaluable, and it is not what the plugin does.
3. Detaches when the gripper is commanded open beyond a threshold.
4. Logs its attach and detach transitions.

   **Not** typed ROS events, as an earlier draft of this record said it would. Nothing
   consumes them yet, and the scenario asserts on something stronger: it reads the
   work-piece's pose from the simulator and requires that it actually left the table. A
   component reporting success proves only that the component thinks so. A typed event
   belongs here the day L4 needs to react to a grasp it did not command — and not before,
   because an interface with no consumer gets the wrong shape.

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
  **[Corrected 2026-08-25 — see the Correction section above.]** They were not
  observable as shipped.
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
- **The attachment link cannot be the tool centre point.** Converting URDF to SDF lumps
  every link joined by a fixed joint into its parent, so `link_base`, `link_eef`,
  `xarm_gripper_base_link` and `link_tcp` do not exist in the spawned model at all — only
  links moved by a real joint survive. The plugin therefore attaches to a finger. Naming a
  lumped link is a silent failure: the plugin logs "model has no link" once at start-up and
  then never grasps anything, while the gripper still closes and still reports a stall.
  Found on 2026-08-24, and the reason the link is declared in the model rather than assumed
  by the plugin.

### What we will have to revisit
When Phase 2 compares simulated and physical grasping under `VALIDATED` mode, this plugin
is the most likely source of divergence and the first thing to examine. If the divergence
matters, the answer is to add a friction-based mode for fidelity study — kept as a separate,
explicitly-selected configuration — rather than to make the attachment gradually more
physical, which would recreate the flakiness this decision exists to avoid.
