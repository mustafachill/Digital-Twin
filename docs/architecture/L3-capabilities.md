# L3 — Capabilities (skills)

- **Status:** `PARTIAL` — **five of the six skills below have a server in the main tree;
  `Detect` has none there since 2026-10-01.**
  **Built:** `MoveTo`, `Grasp`, `Pick`, `Place` and `Transfer` are action servers in
  `cite_skills/src/skill_server.cpp`, one per arm, and each arm's server also publishes its
  `RobotState` latched on `state`.
  `MoveTo` to the `home` configuration is asserted by `./scripts/scenario bringup`, and
  `MoveTo` and `Grasp` are what the real robot's program drives
  ([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md);
  `cite_bringup/program/cell.py` creates action clients for those two and no others), which
  `./scripts/scenario program_cycle` gates in CI.
  **`Pick`, `Place` and `Transfer` have servers and no in-tree caller outside tests and the
  twin boundary's forwarding.** `Pick` and `Place` completed a cycle on one arm in
  `./scripts/scenario pick_and_place`, a blocking CI gate from `c1e9e03` until that scenario
  left the main tree with [ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) on 2026-10-01; **no scenario in main CI exercises them now**, which
  ADR-0069 lists under "Coverage given up". The figures are a closed record in
  [CLAUDE.md §2](../../CLAUDE.md). `Transfer` never had a caller: the line's L0 topology was
  conveyor-mediated and [L4](L4-orchestration.md) refused a direct arm-to-arm edge at plan time
  ([ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md), now
  deprecated).
  **`Detect` is not in the main tree.** Its action definition, `detection_server.cpp` and the
  `DetectionEvent`/`Detection` messages left with the event-driven line ([ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)); they run, frozen,
  in `projects/01`, whose line started a station on the beam
  transition and stopped the belt on it
  ([ADR-0032](../adr/0032-index-the-belt.md), deprecated). The beams themselves stay in
  `cell_b`'s world, and their levels are still bridged into ROS; nothing in the main tree turns
  them into a typed detection.
  **Built, and this layer now answers a question it used to pass upwards unanswered:** an
  execution abort is classified here, before [L4](L4-orchestration.md) dispatches any
  recovery motion ([ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md)).
  `classify_execution_failure` in `include/cite_skills/motion_end.hpp` is a free function
  reading the plan and the joint state — never an L2 error code — so it holds for any robot
  type (P9) and is identical on both backends (P2). It answers `MOTION_INTERRUPTED` when the
  arm stopped part-way and is holding position, and `EXECUTION_FAILED` at either endpoint.
  Every row of it, and `positions_in_trajectory_order` beside it, is unit-tested in
  `test/test_motion_end.cpp`; it was a private method reachable by no test before this.
  **Proven since 2026-08-28, and read the scope before citing it**
  ([ADR-0040](../adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md)).
  `cite_bringup/test/test_abort_classification_launch.py` drives a genuine
  `PATH_TOLERANCE_VIOLATED` abort through a real `move_group` and the real skill server and
  asserts `MOTION_INTERRUPTED` with the `PART_WAY` wording — the wording matters, because
  the unreadable-arm case answers with the same code. The hardware is
  `cite_test_hardware/JointStopSystem`, mock hardware with a pair of hard stops on one
  joint, which is what lets the arm come to rest *part way* rather than at the first point.
  **What is still not proven:** the plant is a perfect follower with no dynamics, so nothing
  here says what the classification does on an arm that decelerates, and nothing here runs
  under Gazebo.
  **Not proven:** `MoveTo.Goal.cartesian_path` returns
  `NOT_IMPLEMENTED` ([ADR-0026](../adr/0026-joint-space-goals-on-under-six-dof-arms.md)).
  **Not assertable:** how a part is oriented in the jaws — see "A grasp is evidenced by a
  stall" below.
- **Related:** [ADR-0006](../adr/0006-moveit2-motion-planning.md), [ADR-0010](../adr/0010-typed-ros-interfaces.md), [ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md), [ADR-0029](../adr/0029-simulated-grasping-by-friction.md), [ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md), [`../interfaces/README.md`](../interfaces/README.md)

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
| `Transfer` | Handoff pose, rendezvous token, work-piece id, hold timeout | Transferred / failed, and whether the part is still held |
| `Grasp` | End-effector command | Actuated / failed |
| `Detect` | Region of interest, object type | Detections, each with a pose **where the sensor can give one** |

**`Detect` has no server in the main tree since 2026-10-01 (ADR-0069); this paragraph records
how it behaved in the line, which still runs in `projects/01`.** No sensor in `cell_a` could
give a pose. The zone detected with through-beams, which
report occupancy, so `detection_server.cpp` marks `Detection.pose` unobserved rather than
filling it with the beam's own mounting transform — the convention is in
[`../interfaces/README.md`](../interfaces/README.md), and the cost of having got this wrong
is in [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md)'s
correction.

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

### A grasp is evidenced by a stall, and a stall says nothing about orientation

`Grasp` commands a width on the `ros2_control` gripper controller and nothing else
([ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md)). The part is held when the
pads **fail** to reach the commanded width — `stalled=true, reached_goal=false`, *and* the
width they did reach exceeds the command by more than the controller's own end-of-goal bias
(`cite_skills::gripper_is_holding`). A gripper that reaches its command reached it through
empty space, so success at the controller level is evidence of an *empty* gripper. `Pick`
reads it that way.

That is now the whole mechanism. There is no simulation-side attachment
([ADR-0029](../adr/0029-simulated-grasping-by-friction.md)), and the same code runs on both
paths — which is the point, and is why nothing in this layer branches on simulation.

**What the mechanism does not give is orientation.** A friction grasp in this cell is
repeatable in position and not in orientation: the part **rolls** between the jaws, about the
pad-to-pad axis, while the pads themselves barely move. The three campaigns behind that
statement are
[`../measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md),
[`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md)
and
[`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md);
their figures are not restated here (P1).

**Yaw is the one component the closure does control**, and in the direction that helps: jaws
closing on a part that is turned about the vertical rotate it into alignment, so the part is
carried square and released with a residual. That is a measured result about *this
simulator's* rigid-body contact, with no friction declared on the pads, and the third
campaign flags it as the largest sim/real divergence on its books. It is not a licence to
assert orientation — the restriction below is unchanged.

The standing restriction from ADR-0029 binds this layer:

> A scenario may assert **where** a part ends up. No scenario may assert **how** a part is
> oriented in the jaws.

Two pieces of work inherit that restriction rather than work around it, and each has taken
it differently.

**A direct arm-to-arm `Transfer` needs to know how a part is held, not only that it is**
([ADR-0024](../adr/0024-handoff-split-between-l3-and-l4.md)). It is therefore **refused at
plan time** rather than attempted
([ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md)).

A conveyor-mediated handoff is permitted, and **not** because anything re-observes the part:
`Detect` returns no pose, because the only pose sensor in the cell is a through-beam and
`cite_skills::mark_pose_unobserved` says so explicitly. *(Both left the main tree with the line
on 2026-10-01, ADR-0069; the reasoning stands for any future handoff.)* It is permitted because the part is
free when the **receiving** gripper closes on it, and closing on a yawed part squares it up —
measured in
[`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md),
which is the authority for the numbers. **The
same mechanism is what a direct handoff denies**, because a part clamped by the giving
gripper cannot rotate into alignment with the receiving one, so the refusal is unaffected. The
squaring-up is a rigid-body result with no friction declared on the pads; Phase 2 has to
re-measure it before anything is built on it.

**Whether orientation error accumulates across the three stations of the continuous line is
unmeasured**, and the campaign above names it as such: each station squares the part up on
closure and gives some back on release, and whether that converges or drifts over the ladder
was not run. It is not a prediction either way — do not write it down as one. The line now
reaches far enough to exercise it, which makes the experiment possible rather than
unnecessary.

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
| A grasp reported from the controller's own success | The gripper reaching its commanded width means it closed on *nothing* | `reviewer`; `cite_skills::gripper_is_holding` requires a stall **and** a width margin wider than the controller's end-of-goal bias |
| A skill or scenario relying on part orientation | Passes while the part turns tens of degrees in the jaws | `reviewer` — the restriction above is a review checkpoint |

## Open questions

- **Grasp representation.** Whether a grasp pose is supplied by the caller, computed by the
  skill, or looked up per object type. Affects whether perception is a `Detect` skill or
  something richer.
- **How a direct arm-to-arm handoff will ever observe orientation.**
  [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md) refuses one
  at plan time because nothing re-observes the part between two grippers, and names the
  observation as the blocker. What provides it — a camera at the rendezvous, or a `Detect`
  that returns a full pose there — is undecided, and the only pose sensor in the model
  today is a through-beam that reports occupancy. Nothing re-observes the part on a
  conveyor-mediated edge either; what makes that case work is the receiving gripper, and
  **a direct handoff has never been measured at all**. It needs its own experiment before
  the gate is touched.
- **Force-controlled skills.** Insertion and compliant placement need force feedback and a
  different control mode. Not scheduled, but the skill interface should not preclude it.
