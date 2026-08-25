# L3 — Capabilities (skills)

- **Status:** `PARTIAL` — **four of the six skills below have a server.**
  **Built:** `MoveTo`, `Grasp`, `Pick` and `Place` are action servers in
  `cite_skills/src/skill_server.cpp`. `MoveTo` to the `home` configuration is asserted by
  `./scripts/scenario bringup`.
  **Not built:** `Transfer` and `Detect`. Both have `.action` definitions in
  `cite_interfaces` and no implementation anywhere.
  **Not proven:** no pick-and-place cycle has completed, and **no work-piece has been
  grasped**. `./scripts/scenario pick_and_place` does not pass and runs in CI as
  `continue-on-error`. `MoveTo.Goal.cartesian_path` returns `NOT_IMPLEMENTED`
  ([ADR-0026](../adr/0026-joint-space-goals-on-under-six-dof-arms.md)).
- **Related:** [ADR-0006](../adr/0006-moveit2-motion-planning.md), [ADR-0010](../adr/0010-typed-ros-interfaces.md), [`../interfaces/README.md`](../interfaces/README.md)

## Responsibility

L3 is the vocabulary the system speaks about work. It exposes **robot-agnostic skills** as
ROS 2 actions: move to a pose, pick an object, place it, transfer it to a peer, actuate an
end-effector, detect an object.

A skill is the unit of meaningful work. Above this line, nothing knows what kind of arm is
executing — which is precisely what makes P9 achievable.

## Owns

- Skill action servers and their typed interfaces.
- Translating a semantic goal ("pick the box at this pose") into planning and execution.
- Skill-level error handling, cancellation, and preemption.
- Grasp strategy and approach/retreat behaviour.

## Does not own

- **When a skill runs, or why.** L4 decides.
- Planning algorithms or controller behaviour — L2.
- Any knowledge of the specific robot. A skill that branches on robot type has failed at
  its job.

## Interfaces

**Consumes:** MoveIt planning and `ros2_control` actions from L2.

**Exposes:** ROS 2 actions, one per skill. Actions, not services, because every skill is
long-running, must report progress, and must be cancellable.

Initial skill set:

| Skill | Goal | Result |
|---|---|---|
| `MoveTo` | Target pose or named configuration | Reached / failed, with reason |
| `Pick` | Object pose, grasp hint | Holding / failed |
| `Place` | Target pose | Released / failed |
| `Transfer` | Peer identity, handoff pose | Transferred / failed |
| `Grasp` | End-effector command | Actuated / failed |
| `Detect` | Region of interest, object type | Detections with poses |

`Grasp` is the end-effector actuation skill in general, not only closing a parallel
gripper — a vacuum end-effector actuates through the same skill. This table named it
`Actuate` until 2026-08-24; charter §5 and `CLAUDE.md` §5 both say `Grasp`, and the
charter is authoritative over other documents by its own §0, so the name here was
wrong. Corrected before `cite_interfaces` was written, since renaming an action after
it has consumers is a breaking change ([interfaces/README.md](../interfaces/README.md)).


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

### Skills are stateless between goals

A skill server holds no memory of previous goals. Work-piece tracking, station state, and
sequencing live at L4. This keeps skills independently testable and independently
restartable, and it stops L3 from quietly becoming a second orchestrator.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Joint-space goal in a skill interface | Works for one robot, breaks on the next | `architect-reviewer` |
| Cancellation unimplemented | System cannot be stopped cleanly; E-stop leaves indeterminate state | `safety-auditor`, `reviewer` |
| Skill accumulating state | Restarting it changes behaviour; tests pass in isolation and fail in sequence | `reviewer` |
| Untyped failure reason | L4 cannot choose a recovery; everything becomes a generic retry | `reviewer` |
| Skill reaching into L2 internals | Layer violation; controller change breaks the skill | `architect-reviewer` |
| Planning latency assumed bounded | Intermittent timeout under load | `tester`, `performance-engineer` |

## Open questions

- **Grasp representation.** Whether a grasp pose is supplied by the caller, computed by the
  skill, or looked up per object type. Affects whether perception is a `Detect` skill or
  something richer.
- **Where handoff logic lives.** `Transfer` as an L3 skill assumes two arms can negotiate
  through it. It may instead belong at L4 as a coordinated pair of `Place` and `Pick`. This
  needs deciding before Phase 1.D and is the most consequential open question in this layer.
- **Force-controlled skills.** Insertion and compliant placement need force feedback and a
  different control mode. Not scheduled, but the skill interface should not preclude it.
