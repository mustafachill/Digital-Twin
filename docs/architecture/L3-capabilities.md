# L3 — Capabilities (skills)

- **Status:** `PARTIAL`.
  **Built:** `MoveTo`, `Grasp`, `Pick`, `Place` and `Transfer` are action servers in
  `cite_skills/src/skill_server.cpp`, one server per arm, and each arm's server also
  publishes its `RobotState` latched on `state` — which is what the simulated grasp hold is
  told from ([ADR-0065](../adr/0065-the-cell-says-what-it-holds.md)).
  **`MoveTo` and `Grasp` are what the real robot's program drives**
  ([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md);
  `cite_bringup/program/cell.py` creates action clients for those two and no others).
  `MoveTo` to `home` is asserted by `./scripts/scenario bringup`, and the program's moves and
  grasps by `./scripts/scenario program_cycle`, both gating CI.
  **`Pick`, `Place` and `Transfer` have servers and no caller** outside tests and the twin
  boundary's forwarding; no scenario exercises them.
  **Built: abort classification**
  ([ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md)).
  `classify_execution_failure` in `include/cite_skills/motion_end.hpp` reads the plan and the
  joint state — never an L2 error code — so it holds for any robot type (P9) and on both
  backends (P2). It answers `MOTION_INTERRUPTED` when the arm stopped part-way and is holding
  position, and `EXECUTION_FAILED` at either endpoint; every row is unit-tested in
  `test/test_motion_end.cpp`. `cite_bringup/test/test_abort_classification_launch.py` drives a
  genuine `PATH_TOLERANCE_VIOLATED` abort through a real `move_group` and the real skill
  server on `cite_test_hardware/JointStopSystem`
  ([ADR-0040](../adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md)).
  **Not proven:** what the classification does on an arm that decelerates — the test plant is
  a perfect follower — and anything under Gazebo.
  **Not built:** `MoveTo.Goal.cartesian_path` returns `NOT_IMPLEMENTED`
  ([ADR-0026](../adr/0026-joint-space-goals-on-under-six-dof-arms.md)).
  **Not assertable:** how a part is oriented in the jaws — see "A grasp" below.
- **Related:** [ADR-0006](../adr/0006-moveit2-motion-planning.md), [ADR-0010](../adr/0010-typed-ros-interfaces.md), [ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md), [ADR-0052](../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md), [ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md), [`../interfaces/README.md`](../interfaces/README.md)

## Responsibility

L3 is the vocabulary the system speaks about work. It exposes **robot-agnostic skills** as
ROS 2 actions: move to a pose, pick an object, place it, transfer it to a peer, actuate an
end-effector.

A skill is the unit of meaningful work. Above this line, nothing knows what kind of arm is
executing — which is precisely what makes P9 achievable.

## Owns

- Skill action servers and their typed interfaces.
- Translating a semantic goal ("pick the box at this pose") into planning and execution.
- Skill-level error handling, cancellation, and preemption.
- Grasp strategy and approach/retreat behaviour.

## Does not own

- **When a skill runs, or why.** Its caller decides — in the main tree, the program client
  (`cite_bringup.program`), through the twin boundary.
- Planning algorithms or controller behaviour — L2.
- Any knowledge of the specific robot. A skill that branches on robot type has failed at
  its job.

## Interfaces

**Consumes:** MoveIt planning and `ros2_control` actions from L2.

**Exposes:** ROS 2 actions, one per skill. Actions, not services, because every skill is
long-running, must report progress, and must be cancellable.

The skill set:

| Skill | Goal | Result |
|---|---|---|
| `MoveTo` | Target pose or named configuration | Reached / failed, with reason |
| `Pick` | Object pose, grasp hint | Holding / failed |
| `Place` | Target pose | Released / failed |
| `Transfer` | Handoff pose, rendezvous token, work-piece id, hold timeout | Transferred / failed, and whether the part is still held |
| `Grasp` | End-effector command | Actuated / failed |

`Grasp` is the end-effector actuation skill in general, not only closing a parallel
gripper — a vacuum end-effector actuates through the same skill.


## Design

### Robot-agnostic means genuinely agnostic

A skill accepts a goal in **task space**, not joint space. `Pick` takes a pose in a named
frame, never five joint angles. Joint-space goals leak the robot's kinematics upward and
break every promise this layer makes.

Swapping an xArm 5 for an xArm 7, or for another manufacturer's arm, changes the L0
instance and the L1 description. It must change nothing at L3 or above. When that stops
being true, something has leaked and it is an `architect-reviewer` finding.

### Every skill implements the full action contract

The v1 workspace faked motion with timers precisely because wiring real asynchronous
results was harder. The result was a system where nothing could fail, which meant nothing
could be trusted.

Every skill must therefore implement:

- **Feedback** — progress, meaningful enough to display and to time out against.
- **Cancellation** — a cancelled skill leaves the robot in a safe, known state. Not
  "wherever it stopped".
- **Preemption** — a new goal supersedes the current one deterministically.
- **Structured failure** — a typed reason, never a string. "Failed" is not a result; "IK
  solution not found for target pose" is.

### A grasp is judged against the part, and says nothing about orientation

`Grasp` commands a width on the `ros2_control` gripper controller and nothing else
([ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md)). Whether the jaws then hold
something is decided once, by `cite_skills::gripper_is_holding`: the **reached** width is
judged against the facility's declared work-piece interval, widened by a stall band at each
edge ([ADR-0052](../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md), option F).
The commanded width is deliberately not read. A requested or configured grasp width that
lands within the discrimination margin of the narrowest declared part is refused before it is
executed (`cite_skills::resolve_grasp_width`).

The same code runs on both sides. On the simulated side the verdict is published as
`RobotState`, and a simulation-only plugin holds the part still while the verdict says it is
held ([L1](L1-description-and-assets.md)); on the physical side the real gripper holds it.
Nothing in this layer branches on simulation.

**What the predicate cannot give is orientation.** A part may sit in the jaws turned, and
nothing in the cell observes how. The standing restriction binds this layer:

> A scenario may assert **where** a part ends up. No scenario may assert **how** a part is
> oriented in the jaws.

A direct arm-to-arm `Transfer` would need exactly that knowledge
([ADR-0024](../adr/0024-handoff-split-between-l3-and-l4.md)); it has a server and no caller.

### Skills are stateless between goals

A skill server holds no memory of previous goals, beyond publishing what its gripper holds.
Sequencing lives in the caller. This keeps skills independently testable and independently
restartable, and it stops L3 from quietly becoming a second orchestrator.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Joint-space goal in a skill interface | Works for one robot, breaks on the next | `architect-reviewer` |
| Cancellation unimplemented | System cannot be stopped cleanly; E-stop leaves indeterminate state | `safety-auditor`, `reviewer` |
| Skill accumulating state | Restarting it changes behaviour; tests pass in isolation and fail in sequence | `reviewer` |
| Untyped failure reason | The caller cannot tell why a step stopped; everything becomes a generic retry | `reviewer` |
| Skill reaching into L2 internals | Layer violation; controller change breaks the skill | `architect-reviewer` |
| Planning latency assumed bounded | Intermittent timeout under load | `tester`, `performance-engineer` |
| A grasp reported from the controller's own success | The gripper reaching its commanded width means it closed on *nothing* | `reviewer`; `cite_skills::gripper_is_holding` judges the reached width against the declared part |
| A skill or scenario relying on part orientation | Passes while the part turns tens of degrees in the jaws | `reviewer` — the restriction above is a review checkpoint |

## Open questions

- **Grasp representation.** Whether a grasp pose is supplied by the caller, computed by the
  skill, or looked up per object type.
- **Force-controlled skills.** Insertion and compliant placement need force feedback and a
  different control mode. Not scheduled, but the skill interface should not preclude it.
