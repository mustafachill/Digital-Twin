# ADR-0037: Classify an execution abort before any recovery motion is dispatched

- **Status:** Accepted, 2026-08-27, by the **orchestrator's** decision, on the evidence that
  decisions 1-5 are implemented, merged at `c7557c8`, and passed three scenarios. **Binding:
  violating it is an `ESCALATE`, not a code-review finding.**
  *(Corrected 2026-08-27: this line first attributed the promotion to the project owner. It was
  the orchestrator's call, and an over-claim about who decided is exactly what these records
  must not carry.)*
  It was written before the change, which is the point
  ([CLAUDE.md §12](../../CLAUDE.md)), and every "will" below was a commitment rather than a
  description when it was written.
  **That is no longer true of the whole record, and the status change does not make it
  true.** Decisions 1-5 are implemented and merged at `c7557c8`, and three scenarios passed
  on them — which is what the earlier status was waiting for when it said "Proposed until
  the branch merges". Decision 6 is still **deliberately undecided**; decision 7 is an
  ordering that has been followed; and decision 8 was **wrong about the fixture** and is
  corrected below. Read "Corrections to this record" before treating any "will" here as a
  description of what was built.
  **Amended 2026-08-27.** Correction 3's *decision* stands untouched; its *stated reason*
  cited the process exit that [ADR-0038](0038-stop-the-line-without-ending-the-process.md)
  replaces, and is restated in the section named "Amendment — 2026-08-27: correction 3's
  stated reason, restated for the built fault branch", at the head of "Corrections to this
  record". Nothing here was measured false, which is why this is an amendment and not a
  correction.
- **Date:** 2026-08-27
- **Deciders:** Docs-writer agent, from findings raised independently by two agents while
  auditing the L4 recovery path after ADR-0036
- **Related:** ADR-0036, *Detect a mistracked trajectory at execution, with tolerances
  declared in L0* (**prerequisite**, and **not on `main` at this commit** — it lives under
  `docs/adr/` on branch `feat/trajectory-tolerance-remediation`, which is why it is named
  here and not linked; the link is added when it merges),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0010](0010-typed-ros-interfaces.md),
  [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md),
  [cross-cutting-safety.md](../architecture/cross-cutting-safety.md),
  [L3](../architecture/L3-capabilities.md), [L4](../architecture/L4-orchestration.md),
  charter §3.2 and §4 (P2, P4, P7, P9)

## The decision, in one line

**No replanned motion is dispatched before the failure has been classified**, and a station
whose classification is `ESCALATE` or `STOP_LINE` performs no motion at all.

## This applies a rule this repository already wrote down; it does not invent one

[`cross-cutting-safety.md:85-87`](../architecture/cross-cutting-safety.md) says, of
E-stop reset:

> Requires a **deliberate reset**. Automatic resumption after an unexplained fault is a
> Critical finding — the fault has not been diagnosed, and resuming re-runs whatever caused
> it.

and its failure-mode table at `:140` grades *"Automatic resumption after fault"* as
**Critical**. Both quotations were read from the file at `b54140f` and both line numbers are
exact.

**Two qualifications, because the strong version of this claim does not survive checking,
and the brief that produced this record used the strong version.**

1. **The rule is written about E-stop, not about a controller abort.** What transfers is its
   stated reasoning — *the fault has not been diagnosed, and resuming re-runs whatever caused
   it* — which is about diagnosis rather than about the safety channel. The L4 recovery
   branch is a case of that reasoning. Extending it there is a judgement, not a citation.
2. **That document's status line is `DESIGNED`, and it says the layer it describes "does not
   exist" and is "[b]inding from the first line of Phase 2 code."** So the failure-mode table
   is not yet binding on Phase 1 code by its own terms. What *is* binding today is the same
   document's instruction two sections earlier: *"Audit simulation-only code as if it were
   hardware code, because one day it is. This is why `safety-auditor` reviews motion paths in
   Phase 1, long before a real arm is connected."*

So: this ADR does not report a violation of a currently-binding rule. It reports that a
Phase 1 motion path, audited as the document instructs, is on the wrong side of a rule the
document commits to from Phase 2 — and decides to fix it now, while the fix is cheap and the
path is short. That is a weaker and more accurate statement than "this violates our own
locked rule", and it is the one the evidence supports.

**Nothing here is a protective measure and it must never be described as one.** It removes
an automatic resumption. What stops an arm remains the vendor controller's torque limiting
and physical guarding (charter §3.2), exactly as ADR-0036 says of its own detector. A
station that stops instead of retrying is not safer in any certifiable sense; it is
diagnosable.

## Context

### The defect, live on `main` at `b54140f`

`workspace/src/cite_orchestration/trees/line_station.xml:166-171`:

```xml
      <Sequence name="recover">
        <MoveToHome           asset="{asset}" action="{move_to_action}" />
        <ReleaseStationClaims station="{station}" />
        <RecoverFromFailure   station="{station}" workpiece="{workpiece}"
                              token="{token}" />
      </Sequence>
```

and `station_cycle.xml:42-45` runs `MoveToHome` → `ReportBlocked`.

**The motion happens before the policy is consulted.** `RecoverFromFailure` — the only node
that reads `recovery_policy.hpp` — is the third leaf. `MoveToHome` is a
`SkillNode<MoveTo>` (`skill_nodes.hpp:462`); it sends a `MoveTo` goal, which plans a fresh
trajectory and executes it. So by the time the policy answers, an unattended arm motion has
already been planned and run.

Two policy rows say plainly that this must not happen. `recovery_policy.hpp:132-136`:

```cpp
    //: L2 refused the motion. L4 is not the safety mechanism and must never
    //: behave as though a refusal were a transient — retrying through one is how
    //: a coordination bug becomes an injury.
    case ResultCode::SAFETY_BLOCKED:
      return Recovery::STOP_LINE;
```

and `:138-141`, for `HARDWARE_FAULT`: *"The cell is not in a state to be commanded at all,
so no other station's work is trustworthy either."* — after which the cell is commanded.

### The second defect at the same site, which is worse and was found while checking the first

`SkillNode::poll` calls `record(outcome.code)` **unconditionally**, on success as well as on
failure (`skill_nodes.hpp:222`), and `record` writes the blackboard key
`kLastResultCode` (`skill_nodes.hpp:305-311`). `RecoverFromFailure` reads that same key
(`line_nodes.hpp:870`).

The recovery branch's `MoveToHome` therefore **overwrites the code the policy is about to
read**. When it succeeds it writes `SUCCESS`, `recovery_for(SUCCESS)` returns
`Recovery::NONE`, and the `NONE` arm of the switch (`line_nodes.hpp:880-892`) sets the
station to `WAITING` and returns `BT::NodeStatus::SUCCESS` — which the enclosing
`<Repeat num_cycles="-1">` turns into another attempt.

**So on the common path — recovery `MoveToHome` succeeds — `STOP_LINE` and `ESCALATE` are
unreachable in `line_station.xml` today.** Every failure becomes a retry. This is read from
source at `b54140f`; it is not observed in a run, and no test in the tree covers it,
because L4's tests drive fake action servers that succeed when told to.

`station_cycle.xml` has the ordering defect and no policy at all: `ReportBlocked`
(`skill_nodes.hpp:930-957`) logs an error and returns `SUCCESS`.

### ADR-0036 makes this acute rather than causing it

ADR-0036 ships a per-joint path tolerance, so `PATH_TOLERANCE_VIOLATED` becomes a routine
producer of `EXECUTION_FAILED`, and `EXECUTION_FAILED` maps to `RETRY_SAME`
(`recovery_policy.hpp:116-118`). A path-tolerance abort means something physically held the
arm. Retrying it replans from a model of the world that the abort itself contradicts.

That is sharper here than in a general robot cell because of
[ADR-0029](0029-simulated-grasping-by-friction.md): a grasp in this cell is friction alone,
so an unexplained abort during a carry plausibly means the part has moved in the jaws or
left them. Replanning from a stale scene is the worst case for it.

### The abort vocabulary on this stack is four sites, and two of the codes are never emitted

`joint_trajectory_controller.cpp` on `ros-controls/ros2_controllers` branch `jazzy` has
exactly four `setAborted` sites:

| Error code set at | `setAborted` at | Condition |
|---|---|---|
| `:470` | `:472` | `PATH_TOLERANCE_VIOLATED` — a joint mistracked mid-path |
| `:517` | `:519` | `GOAL_TOLERANCE_VIOLATED` — outside goal tolerance past `goal_time` |
| `:1264` | `:1266` | `INVALID_GOAL` — an active goal at `on_deactivate` |
| `:1830` | `:1832` | `INVALID_GOAL` — an active goal at `preempt_active_goal` |

**`INVALID_JOINTS` and `OLD_HEADER_TIMESTAMP` appear nowhere in the file.** The conditions
those codes name — a joint-name mismatch, a trajectory whose start stamp is non-zero and
whose end is already in the past — are checked in `validate_trajectory_msg` (`:1671`
onward), which returns `false`, which the goal callbacks turn into
`rclcpp_action::GoalResponse::REJECT` (`:1411`, `:1416`).

**And a ROS 2 rejection carries no reason at all.** The `_SendGoal` service response is
constructed in `rosidl_parser/definition.py:696-705` with exactly two members —
`boolean accepted` and `builtin_interfaces/msg/Time stamp`. No result message is ever
produced for a rejected goal.

This matters, and it is why this section is here rather than in a comment: **the retryable
transport fault that motivated wanting a discriminator does not exist on this stack.** The
ADR-0036 branch currently says in three places that `ABORTED` carries `INVALID_JOINTS` and
`OLD_HEADER_TIMESTAMP` indistinguishably, and that the latter "MUST keep retrying". It
cannot arrive as an abort. Those three passages are wrong and are listed in
"What this record corrects" below.

**Version caveat, and it is load-bearing.** ADR-0036 states the installed controller is
`joint_trajectory_controller` **4.40.1**. At tag `4.40.1` there are only **three**
`setAborted` sites: `preempt_active_goal` calls `setCanceled`, not `setAborted`
(`4.40.1:1919`). The jazzy `distribution.yaml` in `ros/rosdistro` today releases
`ros2_controllers` **4.42.1-1**, which is the branch state with four. So which vocabulary
this cell actually sees depends on which of the two is in the image, and the image is being
rebuilt as this is written. The consequence is in decision 4.

### The information is destroyed by three funnels, not one

1. **`finishControllerExecution(const rclcpp_action::ResultCode& state)`** —
   `moveit_plugins/moveit_simple_controller_manager/.../action_based_controller_handle.hpp:221`.
   It takes the action's terminal code and nothing else. The controller's
   `FollowJointTrajectory::Result::error_code` is not a parameter, so it cannot be
   forwarded. `SUCCEEDED → SUCCEEDED`, `ABORTED → ABORTED`, `CANCELED → PREEMPTED`,
   `UNKNOWN → UNKNOWN`, everything else `→ FAILED`.
2. **`moveit_controller_manager::ExecutionStatus`** — `moveit_core/controller_manager/.../controller_manager.hpp:51-60`
   is a closed seven-value enum `{UNKNOWN, RUNNING, SUCCEEDED, PREEMPTED, TIMED_OUT,
   ABORTED, FAILED}` with a single private member `Value status_` (`:99`). **There is no
   payload field**, so a controller-manager plugin cannot extend it without changing
   `moveit_core`.
3. **`execute_trajectory_action_capability.cpp:126-147`** collapses everything except
   `SUCCEEDED`, `PREEMPTED` and `TIMED_OUT` into `MoveItErrorCodes::CONTROL_FAILED`.

`MoveGroupInterface::execute()` returns that error code verbatim
(`move_group_interface.cpp:862`, `return res->error_code;`), and
`cite_skills/src/skill_server.cpp:1631-1640` maps every non-`SUCCESS` value to
`ResultCode::EXECUTION_FAILED`, putting the numeric MoveIt code only into `detail` — which
`ResultCode.msg` says nothing may parse.

Recorded here so that nobody re-derives it. Each of the three is sufficient on its own.

### Nothing is fixed upstream, and nobody has asked

A survey on **2026-08-27** of `moveit/moveit2` issues and pull requests found no open
issue, no rejected pull request and no maintainer position on preserving the controller's
error code. Searches for `PATH_TOLERANCE_VIOLATED` returned zero results; searches for
`ExecutionStatus`, `FollowJointTrajectory error_code` and `goal rejected reason` returned
only unrelated threads.

This is a survey result, not a proof of absence. What can be stated is what was done and
when.

The one adjacent acknowledgement is **moveit2#1738** (opened 2022-11-18, closed
2022-11-29, "Completed trajectory execution with status ABORTED"), where a commenter wrote:

> It'd be nice if `moveit.simple_controller_manager` also logged the rejection reason (both
> an `error_code` as well as an `error_string` are part of the rejection result), but it
> doesn't seem like it does that any more (the ROS 1 version does I believe).

That is about **logging** a **rejection**, not about propagating an **abort** code, and it
produced no code change. Its premise is ROS 1's: as established above, a ROS 2 rejection
has no result message to carry a code in.

**The four files were compared between `jazzy` and `main` on 2026-08-27, and they are not
byte-identical.** Two differ: `plan_execution.cpp` by a single added `#include <cstdint>`,
and `action_based_controller_handle.hpp` by a single `and` → `&&`. Neither touches the
abort path. The substantive claim — that nothing has been fixed upstream — survives; the
word "byte-identical" does not, and is not used.

### MoveIt already implements the policy we are adopting

`plan_execution.cpp:225-228` on `jazzy`:

```cpp
    // if execution succeeded or failed in a manner that we do not consider recoverable, we exit the loop (with failure)
    if (plan.error_code.val != moveit_msgs::msg::MoveItErrorCodes::MOTION_PLAN_INVALIDATED_BY_ENVIRONMENT_CHANGE)
    {
      break;
    }
```

Before motion, the same loop `continue`s on `PLANNING_FAILED`, `INVALID_MOTION_PLAN` and
`UNABLE_TO_AQUIRE_SENSOR_DATA` (`:186-197`), bounded by
`default_max_replan_attempts_ = 5` (`:94`). After motion it continues for exactly one
error code: the environment changed.

The encoded principle is the one this ADR adopts: **a planning failure is safe to retry
because nothing moved; an execution abort is not, because the world state is now unknown.**

### Industrial prior art converges, and the honest rule is narrower than "unexplained faults must halt"

The strongest external citation is **Universal Robots' Product Alert "Safety notice for CB3
UR10", dated 24 September 2019**:

> Protective stops must never be acknowledged and reset automatically, it must always be a
> deliberate action by a user to resume after a protective stop.

**The reason it gives is the interesting part**, and it is why the citation transfers to a
simulation orchestrator where nobody is at risk:

> Automatic acknowledgement and reset of protective stops masks faults that will lead to a
> failure condition.

Diagnostic, not only safety. Both sentences also appear verbatim in UR's current service
manual (SW5.21 and SW5.24, "Preventive Measures"), so this is standing guidance rather than
a one-off notice about one serial range.

Two vendor error handlers have the same shape, from secondary sources (vendor forums and
third-party knowledge bases; no primary manual was read):

- **FANUC Collision Recovery** resets and continues only on the named `SRVO-050 Collision
  Detect` alarm, and requires the Collision Guard and High Speed Skip software options.
- **ABB** recovers from a collision only inside a RAPID error handler that tests
  `ERRNO = ERR_COLL_STOP`, and only when the system parameter `CollisionErrorHandling` has
  been set. The community guidance that accompanies it is to bound the number of resets.

**Reporting against ourselves: Nav2 does not support the strong version of the rule.** Its
recoveries are selected by error code — `AreErrorCodesPresent` and its subclasses — the
ladder is bounded (`number_of_retries="6"` at the root, `1` at each inner `RecoveryNode`)
and escalating (`RoundRobin`: clear costmaps → `Spin` → `Wait` → `BackUp`), and every
action carries an `error_code_id`. But `WouldAControllerRecoveryHelp` and
`WouldAPlannerRecoveryHelp` **both** include `ActionResult::UNKNOWN` in their
recovery-worthy sets. That is two of two, not one of several. Nav2 therefore does retry on a
failure it cannot name.

The rule the survey actually supports is **recovery is selected by cause**, and the
structural detail worth copying is where the selection sits: in
`navigate_to_pose_w_replanning_and_recovery.xml` the recovery branch's **first** node is the
error-code condition and the recovery action is second (`:37-40`, `:44-53`). That is exactly
the reorder decided below.

### Do not cite ISO 10218 or ISO/TS 15066 for this

The 2025 edition's restart-interlock clauses address the **safety channel** — protective
stops, presence sensing, a person in the safeguarded space. A `ros2_control` trajectory
abort is a functional-channel controller fault, and no clause addresses it. Reaching for
those standards here would import a certification claim this repository cannot make (charter
§3.2, and [standards.md](../reference/standards.md), which already records their status).

The one transferable principle is **ISO 14118's *reset is not start*** — clearing a fault
must not itself command motion. **This attribution is secondary-source and unverified
against the standard text.** A survey on 2026-08-27 found the "no automatic restart after a
stop without deliberate action" rule attributed to ISO 14118 and the explicit
reset-independence requirement attributed to ISO 13849-1:2023, in commentary rather than in
either standard; ISO's own catalogue page returned HTTP 403. Do not upgrade this to a
citation without reading the clause.

## Options considered

### Option A — Leave the trees as they are and narrow `EXECUTION_FAILED` to `ESCALATE`

One-line policy change: treat every execution abort as needing an operator.

Genuinely plausible, and it is the conservative reading of the safety rule. Not chosen for
two independent reasons. It does not fix the ordering defect — a `SAFETY_BLOCKED` result
would still produce a `MoveToHome` before the policy was reached, and the blackboard
overwrite would still discard the code. And it makes every transient controller abort stop a
station, which is how a detector gets exempted rather than fixed — the failure mode ADR-0036
names in its own Context.

### Option B — Recover the vendor error code, then discriminate on it

Two routes were found and neither is taken now. Both are recorded in "What is not decided".

### Option C — A first-party `MoveItControllerManager` plugin that retains the code

The obvious place to fix it: our own controller manager plugin, reading
`FollowJointTrajectory::Result::error_code` and passing it on.

**Rejected**, blocked twice. `ExecutionStatus` is a closed enum in `moveit_core` with no
payload field, so the plugin has nothing to put the code into; and even given a side channel,
`execute_trajectory_action_capability.cpp:126-147` collapses `ABORTED` into `CONTROL_FAILED`
before the result reaches `MoveGroupInterface`. Its only route out would be for L3 to
correlate a side-channel code with an `execute()` return by time window — a P4 timing guess
on a path where the answer decides whether an arm moves.

### Option D — Classify from the world, in L3, and reorder both trees

Chosen. Detailed below.

## Decision

### 1. Nothing moves before the policy has chosen

Both trees are reordered so that the classification node is the **first** leaf of the
recovery branch. Clearing the arm becomes an action **of the retry path**, reachable only
when the policy has chosen to retry.

The current tree comment's justification — *"a station that failed mid-cycle may have left
the arm somewhere the next attempt would collide with"* (`line_station.xml:153-154`) — is
sound and misplaced. It argues for clearing the arm **inside** the retry, not **before** the
decision. It moves with the node.

A station whose classification is `ESCALATE` or `STOP_LINE` performs **no** motion. It stops
where it is.

The blackboard overwrite is fixed as part of the same change: after the reorder, the
policy reads `kLastResultCode` before any node in the recovery branch can write it. The
implementation must not rely on ordering alone — a later leaf added to the branch would
silently reintroduce the defect — so the failing code is captured into a port or a
subtree-private key at the point the policy reads it, and the reorder is asserted by a test.

### 2. `ResultCode` gains `MOTION_INTERRUPTED = 10`

Defined in world terms, not in controller terms:

> **`MOTION_INTERRUPTED`** — the arm stopped part-way through a commanded motion and is
> holding position. It is neither at the start nor at the goal, and why it stopped is not
> established.

`EXECUTION_FAILED` narrows to: **the command did not take effect and the arm did not move.**

Policy row: **`MOTION_INTERRUPTED → ESCALATE`**, not `STOP_LINE`. One station is
compromised; the cell is not. `STOP_LINE` stays reserved for `SAFETY_BLOCKED` and
`HARDWARE_FAULT`, the two codes that say the cell itself cannot be commanded.

**`PATH_TOLERANCE_VIOLATED` is explicitly refused as a `ResultCode` constant.** It names an
upstream mechanism rather than a fact about the world; adding it would import a vendor
taxonomy into `cite_interfaces`; and it would be inexpressible for a robot type whose
controller has no such check, which breaks P9 at the interface that exists to make P9
possible.

Narrowing `EXECUTION_FAILED` changes no wire format and no constant value, so it is not a
breaking interface change. It **is** a semantic change to a published constant, and every
producer and consumer of it must be re-read as part of the implementation.

### 3. The classification is computed in L3, from the plan and the joint state

After `execute()` returns non-`SUCCESS`, `skill_server.cpp` compares the current joint state
against the plan's first and last points:

- within start tolerance of `points.front()` → the arm never moved → `EXECUTION_FAILED`;
- within goal tolerance of `points.back()` → it arrived and did not settle → the goal-side
  case;
- strictly between → it stopped mid-path and is holding → `MOTION_INTERRUPTED`.

No L2 error code is consulted, because there is none to consult.

Why this beats every alternative:

- **No race.** On a path-tolerance abort the controller installs a hold — `set_hold_position()`
  or `decelerate_to_hold_position()`, `joint_trajectory_controller.cpp:481-490` — at the same
  instant it calls `setAborted`. Every other route to a discriminator samples a moving
  quantity. *Caveat, stated because it is the kind of claim that gets overstated:* what is
  verified from source is that a hold is **commanded**. That the joint state is **static** by
  the time `execute()` returns is reasoned from the MoveIt round-trip being long relative to a
  control period, and is not measured. If `should_decelerate_on_cancel_` is set there is a
  deceleration ramp. The measurement is named in "revisit".
- **P2 by construction.** Joint states are identical on both backends. Nothing branches on
  simulation.
- **P9 by construction.** A robot type whose controller reports differently, or does not
  report at all, classifies identically — the classification is about the arm, not about the
  controller.
- No new package, no new plugin, no new process.

**The tolerances come from the L0 declaration ADR-0036 added, not from a new constant.**
`goal_tolerance_rad` already exists on the arm type. How it reaches L3 is an implementation
question, and the answer must not create a second copy of the number (P1).

### 4. Stop collapsing `TIMED_OUT` and `PREEMPTED`

They survive MoveIt's funnels intact and `execute_plan` discards them.
`MoveGroupInterface::execute()` returns `MoveItErrorCodes::TIMED_OUT` (`-6`) or `PREEMPTED`
(`-7`), set at `execute_trajectory_action_capability.cpp:132` and `:136`. Their sources are
`TrajectoryExecutionManager`: `TIMED_OUT` when the controller overruns the trajectory's
expected duration and MoveIt stops it (`trajectory_execution_manager.cpp:1553`), `PREEMPTED`
when `stopExecution()` is called (`:1224`).

`ResultCode::TIMEOUT` and `ResultCode::CANCELLED` already exist and already have distinct
policy rows. Mapping to them is a two-line change.

**The ADR-0036 branch comment that "reading a distinction out of `executed.val` would be
inventing one" is too strong and is corrected by this record.** For `ABORTED` it is right.
For these two values it is wrong: they are distinct in the enum, distinct in the funnel, and
distinct on the wire.

**An honest tension, recorded rather than smoothed over.** `TIMED_OUT` and `PREEMPTED` also
leave the arm mid-path, so decision 3's world-state test would classify them as
`MOTION_INTERRUPTED` too. The two are orthogonal axes: the world-state test says **whether
the arm moved**, the MoveIt code says **why the motion ended**. The policy consults the
world-state axis first; where the MoveIt code is present it refines the answer. The
implementation must state which wins and test it, and must not leave it to whichever branch
is written first.

**And a version dependency.** On `joint_trajectory_controller` 4.42.1 a controller-side
preemption is `setAborted` (`jazzy:1832`), so it arrives as `CONTROL_FAILED` and **not** as
`PREEMPTED`. On 4.40.1 it is `setCanceled` (`4.40.1:1919`) and arrives as `PREEMPTED`. The
`PREEMPTED` path is therefore reachable on both versions only through MoveIt's own
`stopExecution()`. Do not write a test that assumes a controller-side preempt produces
`PREEMPTED`; assert against the version in the image and record which one it was.

### 5. The operator reset is decided here, and it does not command motion

#### Why it is part of this change and not a follow-up

[`L4-orchestration.md:89`](../architecture/L4-orchestration.md) lists `reset` among the
control services L4 exposes, and the tree in the same document at `:106` contains
`Sequence: OnFault → StopAll → AwaitReset`. **There is an `AwaitReset` step in the design
with nothing to await.** `cite_interfaces/srv/` contains exactly `GetModelVersion.srv` and
`SetMode.srv`, and `cite_orchestration` contains **not a single `create_service` call**.

So `Recovery::ESCALATE` (`line_nodes.hpp:894-899`) sets `STATE_BLOCKED`, logs *"is blocked
and needs an operator"*, and returns `FAILURE` — and the operator it names has no control at
all. The only exit is restarting the process.

That is survivable today because `ESCALATE` is rare: it is reached by `UNREACHABLE`,
`NOT_IMPLEMENTED`, an unrecognised code from a newer producer, or a retry past budget.
**Decision 2 makes it routine.** `MOTION_INTERRUPTED → ESCALATE` means the first
path-tolerance abort blocks a station permanently. Without the reset, this change stops the
line correctly and never starts it again — trading a safety hole for an availability hole,
and this project's history says an availability hole gets the detector exempted rather than
fixed. The reset ships in this change or the change does not ship.

#### The decision: reset is not start

**Clearing `STATE_BLOCKED` returns the station to `STATE_WAITING` — awaiting its trigger —
and does nothing else.** It must not plan, must not send a `MoveTo` goal, must not drive the
arm home, and must not resume a belt.

This is ISO 14118's *reset is not start*, and it is the one principle from the standards
that transfers to this path. It is **not** ISO 10218: those restart-interlock clauses address
the safety channel — protective stops, presence sensing, a person in the safeguarded space —
and a controller abort is a functional-channel fault. Do not reach for them here. *(The ISO
14118 attribution itself is secondary-source and is marked unverified in the evidence table;
what is decided is the behaviour, which stands on its own reasoning below.)*

There is a second reason beyond safety, and it is the one Universal Robots' Product Alert
actually gives: **automatic acknowledgement masks the faults that predict a failure.** A
reset that silently re-drives the arm destroys the evidence of why it stopped. Restarting the
process — today's only recourse — does exactly that, just more slowly.

If clearing the arm is needed after a reset, that is a **separate, deliberate operator
action**, at reduced speed with a person present. This is the same reasoning that moves
`MoveToHome` out of the pre-decision path and into the retry path in decision 1: the motion
that makes the next attempt possible is part of the attempt, not part of the decision to
allow one.

#### Scope: one station, and it refuses a faulted line

The service resets **one station**, named in the request. `STATE_BLOCKED` is per-station
(`StationState.msg:9`) and is what `ESCALATE` sets.

`STATE_FAULTED` (`StationState.msg:10`), which `STOP_LINE` sets at `line_nodes.hpp:901-905`,
is a **different condition and is not in scope for this service.** `STOP_LINE` is reserved
for `SAFETY_BLOCKED` and `HARDWARE_FAULT` — the two codes that say the cell itself cannot be
commanded — so a per-station reset of a faulted line would be resuming one station of a cell
that is not in a state to be commanded at all. The service **rejects** a request naming a
faulted station, and **rejects a request for any station while any station is faulted**,
because `line_maintenance.hpp:105-106` makes one faulted station a faulted line.

Clearing `STATE_FAULTED` is deliberately left open. It needs a decision about what evidence
makes a cell commandable again, and that decision belongs with the safety layer that does not
exist yet (`cross-cutting-safety.md`, status `DESIGNED`). Recording it as open is the honest
answer; implementing a line-wide reset now would be inventing that evidence standard by
accident.

#### It refuses a reset for a station that is not blocked

A request naming a station in `IDLE`, `WAITING` or `WORKING` is **rejected**, not silently
accepted as a no-op. Accepting it would make the service a general "make it go" button, and a
button that is safe to press when nothing is wrong gets pressed when something is.

The rejection carries a typed reason, not a bare `false` — the caller needs to distinguish
"there was nothing to reset" from "this station is faulted and you may not".

#### What it must record

The diagnostic argument above is lost if the reason a station blocked is discarded on reset.
It currently would be: `SetStationState` at `line_nodes.hpp:818-822` **clears
`runtime.blocked_reason` whenever the new state is neither `BLOCKED` nor `FAULTED`**, so a
reset implemented as "set the station to `WAITING`" destroys the reason as its first act.

`LineState` alone is not where the reason can live afterwards. `LineState.msg:3-5` says it is
published on the STATE profile — reliable, **volatile** — and is *"a periodic report of the
present, not a record"*. A person reading it after the fact gets the next message, not the
last one. And `line_maintenance.hpp:100-102` publishes only the **first** non-empty station
reason (`if (reason.empty() && ...)`), because `LineState.blocked_reason` is a single
line-level string and `StationState` carries no reason field at all — so with two stations
blocked, one reason is already unpublished today.

Three requirements follow, and they are part of this decision:

1. **The reset echoes the reason it cleared** in its typed response. That is the one place a
   volatile topic cannot lose it, because the operator who reset is holding the reply.
2. **The reset logs the cleared reason at `WARN` or above, in a stable format** — the station
   id, the `ResultCode` that caused the block, and the reason string — so the record survives
   in the process log whether or not anyone was subscribed.
3. **The station's post-reset state is `WAITING` with the reason cleared, and this must be an
   explicit act, not a side effect of `SetStationState`.** Relying on the clearing behaviour
   at `line_nodes.hpp:818-822` is what would make the loss silent.

Whether `StationState` should gain a per-station reason field so that all blocked reasons are
published rather than the first is **left open**: it is a change to a published message with
its own consumers, it is not needed for the reset to be diagnosable given requirement 1, and
deciding it inside this ADR would widen the change without evidence. It is named in "revisit".

#### It is typed, and it lives in `cite_interfaces`

P3 and [ADR-0010](0010-typed-ros-interfaces.md): a new `.srv` in `cite_interfaces`,
discoverable with `ros2 interface show`. Not a `std_msgs/String` command topic, not a
parameter, not an untyped trigger — a service, because a reset has exactly one caller at a
time, must return an answer, and must be able to refuse.

The request names a station. The response carries acceptance, a typed reason on refusal, and
the cleared reason on success. Beyond that the shape is the implementation's, and this record
deliberately does not sketch it.

### 6. What is not decided: recovering the vendor error code

Both routes found are recorded so that they are not re-derived, and neither is chosen.

- **An observer on the action's `get_result` service.** It works. It depends on
  `rclcpp_action` internals: the service name is constructed inside `rcl` as
  `"%s/_action/get_result"` (`rcl_action/src/rcl_action/names.c:94`) — a hidden name, not a
  public contract — and the request carries only a `goal_id`
  (`rosidl_parser/definition.py:714-718`). Whether the action server correlates that
  `goal_id` with the requesting client was **not traced**; treat "no identity check" as
  unverified. The hidden-name dependency alone is enough to leave this unchosen.
- **A first-party `follow_joint_trajectory` proxy.** Preserves everything, at the cost of one
  extra process per arm inserted into the motion chain.

Option C — a first-party `MoveItControllerManager` plugin — is **rejected**, not merely
deferred, for the two blocks and the P4 timing guess given above.

### 7. Ordering: ADR-0036 first

ADR-0036's `constraints:` block is the **prerequisite**, not a competing change. With no
block, the position tolerance is `0.0`, and `check_state_tolerance_per_joint` guards its
comparison with `state_tolerance.position > 0.0`
(`tolerances.hpp:309`) — so the check is disabled and a physically obstructed arm reports
`SUCCESSFUL`. *(The brief that produced this record cited `tolerances.hpp:307`; that line is
blank. The guard is at `:309`, inside the `is_valid` expression spanning `:308-311`.)*

The vocabulary must exist before a policy can discriminate over it. Nav2 shipped error codes
before its behaviour tree consumed them, in that order.

### 8. How this will be evidenced

L4's existing tests use fake action servers that succeed because they are told to; they
prove sequence and ownership and can prove nothing here.

ADR-0036's `workspace/src/cite_bringup/test/test_trajectory_constraints_launch.py` already
produces a genuine `PATH_TOLERANCE_VIOLATED` against mock hardware. **That is the fixture
the L4 assertion is built on** — a scenario cannot be made to fail on demand, and one that
could would be asserting the simulator rather than the policy.

The assertion is: given an abort, the recovery branch consults the policy **before** any
`MoveTo` goal is sent. A test that only checks the final station state would pass with the
leaves in either order.

## Consequences

### What this gets us

- The recovery branch stops violating a rule this repository has held since
  `cross-cutting-safety.md` was written, and stops silently converting `STOP_LINE` into a
  retry.
- A failure that stops an arm mid-path becomes a distinct, typed fact that L4 can act on,
  expressed in world terms that hold for any robot type (P9).
- `TIMED_OUT` and `PREEMPTED` stop being discarded, at a cost of two lines.
- Identical on both backends, because the classification reads joint states (P2).
- The three funnels and the four abort sites are written down once, with line numbers, so
  the next person does not spend the same day on them.

### What this costs us

- **`ESCALATE` becomes common, and the line becomes stoppable in a way it was not.** A
  path-tolerance abort now halts a station instead of retrying. If ADR-0036's copied
  tolerances are tighter than a healthy run needs, this converts ADR-0036's CI flake risk
  into a CI stop.
- **The reset service is new scope**, pulled into this change by decision 5. It is a typed
  `.srv` in `cite_interfaces`, a service server in `cite_orchestration` — which has **no
  `create_service` call at all** today, so this is the first — and its own tests. It is not
  optional and it is not small.
- **The reset deliberately leaves the operator with an unhelpful answer in one case.** After
  a reset the station awaits its trigger with the arm wherever the abort left it. If that
  position blocks the next attempt, the operator must clear it as a separate deliberate
  action. That is the cost of *reset is not start*, and it is accepted rather than designed
  around.
- **`STATE_FAULTED` remains unclearable**, so `SAFETY_BLOCKED` and `HARDWARE_FAULT` still
  require restarting the process. Decision 5 narrows the unrecoverable set rather than
  emptying it, and says why.
- **A new interface constant to maintain**, and a narrowed meaning for an existing one, with
  every producer and consumer of `EXECUTION_FAILED` to be re-read.
- **The classification is a heuristic over positions, and it will sometimes be wrong.** A
  trajectory whose start and goal are close, or an abort a few milliseconds after motion
  begins, lands near a boundary. The tolerance is the arm's, so the answer is at least
  consistent with what the controller itself checks — but this is an inference, not a report.
- **It still does not distinguish *why*.** `MOTION_INTERRUPTED` says the arm stopped, not
  what stopped it. The vendor code remains unrecovered (decision 6), and the honest position
  is that we escalate because we cannot tell, not because we have diagnosed anything.
- **Two trees and their comments change**, and the comment moved in decision 1 has been
  quoted in review before. Moving it is deliberate and is recorded here so it does not read
  as a deletion.

### What we will have to revisit

- **Measure that the joint state is static when `execute()` returns.**
  **Taken on 2026-08-28 over three runs of ADR-0040's rig, and the answer there is yes** —
  0.000000000 rad/s at the instant the result reached the caller, over a still window of
  seven to eleven consecutive joint states, on a channel that read 2.0-2.6 rad/s during the
  healthy motion in the same runs. The numbers and their scope are in ADR-0040's "What was
  measured on it", and the scope is the point: that rig's plant is a perfect follower, so
  what is established is that the *commanded* motion has stopped, not that a real arm has
  stopped coasting. **This bullet is narrowed rather than closed.** The case decision 3's own
  "Consequences" names — an abort a few milliseconds after motion begins, where a
  DECELERATING arm is still within tolerance of the start — cannot be produced on a plant
  with no deceleration, and remains unmeasured on either backend.
- **Whether `MOTION_INTERRUPTED → ESCALATE` is the right severity** once there is a reset and
  a few weeks of aborts to look at. It may prove to warrant a bounded, operator-gated retry;
  that would be a new decision, not a widening of this one.
- **If the vendor code is ever recovered**, decision 6's two routes reopen and
  `MOTION_INTERRUPTED` may become the parent of a finer set. The world-terms definition is
  chosen so that a finer set can be added under it without changing what it means.
- **If `preempt_active_goal`'s terminal state changes again upstream**, decision 4's test
  changes with it. Pin the observed version in the test's own record.
- **If a robot type is added whose controller reports execution failures richly**, the
  temptation will be to branch on it. That is a P9 break and an `ESCALATE`, not a special
  case.
- **Whether `StationState` should carry a per-station blocked reason.** Today
  `LineState.blocked_reason` is one line-level string and `line_maintenance.hpp:100-102`
  publishes only the **first** blocked station's reason, so with two stations blocked one
  reason is already unpublished. Decision 5 works around this by returning the reason in the
  reset response rather than by widening a published message. If a second consumer ever needs
  all of them, that is the change to make.
- **How `STATE_FAULTED` is cleared**, once there is a safety layer to say what evidence makes
  a cell commandable again. Left open by decision 5 on purpose.

## What this record corrects

Three passages on branch `feat/trajectory-tolerance-remediation` state the abort vocabulary
wrongly. They are code comments, so correcting them is part of implementing this ADR, not a
documentation change:

1. `recovery_policy.hpp`, the note added to the `EXECUTION_FAILED` branch — *"`ABORTED`
   carries a physical stall, `INVALID_GOAL`, `INVALID_JOINTS` and `OLD_HEADER_TIMESTAMP`
   indistinguishably. The last of those is a transport fault and MUST keep retrying."*
   Neither `INVALID_JOINTS` nor `OLD_HEADER_TIMESTAMP` is ever emitted by this controller;
   both conditions produce a rejection, which carries no result at all.
2. ADR-0036's commit message, S-01, which repeats the same list.
3. `skill_server.cpp`'s note — *"Reading a distinction out of `executed.val` would be
   inventing one."* True of `ABORTED`; false of `TIMED_OUT` and `PREEMPTED`, which are
   distinct values in that same field.

**How these survived**, because the pattern is worth more than the corrections: each was
reasoned from what the `FollowJointTrajectory` **action definition** makes expressible,
rather than from what **this controller** emits. The action's `Result` declares
`INVALID_JOINTS` and `OLD_HEADER_TIMESTAMP`; `joint_trajectory_controller.cpp` never sets
them. Reading the interface and not the implementation is the same shape as ADR-0036's own
correction, which read the code that *set* a tolerance and not the code that *read* it.

## Corrections to this record — 2026-08-27, from implementing it

Three things this record says are wrong or unstated, found while implementing it and while
reviewing the implementation. They are corrected here rather than in the code, because in
each case the code is right and this record is the copy that is out of date.

### Amendment — 2026-08-27: correction 3's stated reason, restated for the built fault branch

**This is an amendment, not a correction.** Nothing below was measured false. The decision in
correction 3 — an escalating station keeps its claims — survives unchanged, and so does the
premise it rests on. What is replaced is the *wording* of the reason, because it cites a
mechanism that [ADR-0038](0038-stop-the-line-without-ending-the-process.md) changes, and a
forward reference to a design becomes a description of a thing that exists.

The premise is **preserved on purpose** by ADR-0038: the root `Parallel` still fails at
`failure_count="1"`, still halts every sibling and so cancels their goals, and the fault
branch then commands every belt to zero. Nothing runs alongside a blocked station either
way. The reason now reads:

> An escalating station keeps its claims because **the line stops around it** — the fault
> branch holds every station and every belt — so the claim record stays true to where the arm
> is standing, and starves nobody.

**The conditional, which is what a future contributor will trip on.** If the line is ever
allowed to keep other stations running past a block, **this decision does not survive.**
There is one `ResourceArbiter`, stations share reach frames, and `Grant::QUEUED` is
deliberately not a failure — `resource_arbiter.hpp:64-66` says *"A leaf that sees this
returns RUNNING"* and `line_nodes.hpp:452-454` implements exactly that. A neighbour asking for
a frame an escalated station still holds would therefore wait **silently and for ever**.
Whoever proposes graceful degradation owes a replacement rule for what a blocked station does
with its claims; reusing this one would be reusing a reason that has stopped being true.

`line_station.xml:206-210` carries the pre-amendment wording verbatim. Correcting it is a
code change and belongs with ADR-0038's implementation.

**How this needed amending at all**, since it is the part that transfers: correction 3
justified a decision by describing the mechanism that produced it *today*, rather than by
naming the property the decision depends on. The property is "nothing else is running"; the
mechanism was "the process exits". Tying a reason to a mechanism makes the reason stale the
moment the mechanism is replaced, even when the decision is untouched.

### 1. `EXECUTION_FAILED` covers BOTH endpoints, not only the start

Decision 2 narrows `EXECUTION_FAILED` to *"the command did not take effect and the arm did
not move"*, while decision 3 lists three outcomes and leaves the middle one — *"within goal
tolerance of `points.back()` → it arrived and did not settle → the goal-side case"* —
without a code. The two halves of the same decision do not agree, and the implementation had
to pick one. **It put both endpoints under `EXECUTION_FAILED`, and that is now the
decision.**

`EXECUTION_FAILED` reads:

> the commanded motion did not complete, and the arm is at one of the trajectory's
> endpoints: it either never left the start or it reached the goal. It is **not** part-way
> and **not** holding an unexplained position.

The reason the two share a code is the reason the policy row exists at all. `RETRY_SAME` is
safe when the next plan can be built from where the arm actually is, and at either endpoint
it can: the arm is at a point the trajectory itself names, so the world has not contradicted
the plan. What `MOTION_INTERRUPTED` marks is precisely the case where it has. The two
endpoint cases are told apart in `detail`, which is prose for a person and which nothing
parses (`ResultCode.msg`).

**A third constant was considered and refused**, for decision 2's own reason: a code has to
be a fact about the world that any robot type can express, and "arrived but the controller
did not report the goal met" is a statement about a controller's settling behaviour. It also
has no distinct policy row to justify it — it would answer `RETRY_SAME`, which is what it
already gets.

### 2. Decision 8 names a fixture that cannot carry the assertion

Decision 8 says of `cite_bringup/test/test_trajectory_constraints_launch.py`: *"That is the
fixture the L4 assertion is built on."* **It is not, and it cannot be.** Two independent
reasons, both read out of that file:

- **It never reaches L3.** The rig launches `robot_state_publisher` and `ros2_control_node`
  and sends goals straight to
  `/cite/<zone>/<arm>/<arm>_joint_trajectory_controller/follow_joint_trajectory`. There is
  no `move_group` and no skill server in it, so nothing it produces passes through
  `classify_execution_failure` at all.
- **The abort it produces is the one answer that is not `MOTION_INTERRUPTED`.** Mistracking
  is injected with `mock_components/GenericSystem`'s `disable_commands`, which stops the
  command propagating so the state interface stays at its `initial_value` — the trajectory's
  first point. An arm frozen at `points.front()` classifies `AT_START`, which is
  `EXECUTION_FAILED`. The fixture that was named as evidence for the interruption case
  produces the endpoint case by construction.

**What the implementation evidences instead**, stated as narrowly as it deserves:

- The decision itself is a free function, `cite_skills::classify_execution_failure`, and
  every row of it is unit-tested in `cite_skills/test/test_motion_end.cpp` — both MoveIt
  codes, the precedence between the two axes, both endpoints, the interrupted case, the
  unreadable case, and that the answer turns on the tolerance handed in rather than on a
  constant. It was a private method of the server before this, reachable by no test.
- Reading the joint state **by the names the trajectory carries** is a second free function,
  `positions_in_trajectory_order`, tested for order and for the one-unreadable-joint case.
- That the tolerance is L0's and not a second copy is guarded at the layer the delivery
  happens at, by three tests in `cite_bringup/test/test_plan.py` modelled on the
  `GRIPPER_KEYS` ones.

**What remains unevidenced, and is a real gap rather than a wording problem: no fixture in
this repository drives a genuine abort into L3 on demand.** Doing so needs `move_group`, a
skill server, and mock hardware that can be made to hold a joint *part way* along a
trajectory rather than at its start — `disable_commands` cannot, because it never lets the
arm leave. That fixture does not exist and building it is not part of this change. Until it
does, the claim "a real abort reaches the classifier" is untested, and no document may say
otherwise.

**Closed on 2026-08-28 by [ADR-0040](0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md).**
The paragraph above stands as the record of what was true when this ADR was implemented; it
is no longer a description of the tree. `cite_test_hardware/JointStopSystem` is mock hardware
with a pair of hard stops on one named joint, and
`cite_bringup/test/test_abort_classification_launch.py` stands it up under a real
`move_group` and the real skill server. A real abort now reaches
`classify_execution_failure` and is answered `MOTION_INTERRUPTED`, with the `PART_WAY`
wording rather than the unreadable-arm wording asserted so that `UNKNOWN` cannot pass for it.

**Two things that paragraph got right and one it could not have known.** It was right that
`disable_commands` produces the endpoint case — ADR-0040 demonstrates it rather than reasons
it, by running the identical goal over that mechanism and watching L3 answer
`EXECUTION_FAILED`, *"still within its goal tolerance of the trajectory's first point"*. It
was right that the fixture had to reach L3 through `move_group` and a skill server. What it
could not have known is that the same rig would be needed for the *velocity* measurement in
"revisit" below, because on a position-only command interface no mock writes the velocity
state at all.

### 3. What an escalating station does with its claims was changed and not declared

Decision 1 reorders the recovery branch and says a station whose classification is
`ESCALATE` or `STOP_LINE` *"performs no motion at all"*. It says nothing about the station's
resource claims, and the reorder changes them: `ReleaseStationClaims` used to run ahead of
the policy, so claims were released on **every** recovery; after the reorder it sits behind a
leaf that returns `FAILURE` on both refusing answers, so they are released on **neither**.

**That behaviour is now decided, and it is the one the implementation has: an escalating
station keeps its claims.** It performs no motion, so its arm is still standing in the
frames it reached into and it still holds the outbound slot for a work-piece
`RecoverFromFailure` deliberately leaves with it. A claim is the line's record of what a
station occupies; releasing one would tell the arbiter a frame is free while an arm holds a
position nothing has established — which is the same kind of statement about the world that
this record exists to stop being made, about the same failure. Starving a neighbour is the
correct consequence and not a cost to work around, because an escalating station stops the
line: its `FAILURE` fails the root `Parallel` today, and `L4-orchestration.md`'s designed
`OnFault → StopAll → AwaitReset` stops it deliberately.
**[Amended 2026-08-27 — see the Amendment section above. The decision stands; this reason is
restated because ADR-0038 replaces the mechanism it cites.]**

**This is not a protective measure.** `resource_arbiter.hpp` says of itself that it prevents
deadlock and thrash and that relying on it for anything else is a defect. What is kept
honest here is the allocation record, which is a coordination property.

It follows that decision 5's reset does nothing about them, which is consistent with *reset
is not start*: a station returns to `WAITING` still holding what it held, and the next
cycle's `ClaimReach` asks again and is answered `GRANTED` because it is already the holder.
**Whether an operator should be able to release a blocked station's claims separately is
left open**, with the deliberate "clear the arm" action decision 5 also leaves out of scope.
Both are the same shape of question — a second, explicit operator action taken with a person
present — and neither should be invented as a side effect of a reset.

The comment that stated the opposite (*"`ReleaseStationClaims` runs on BOTH answers"*) was
false the moment it was written, because a `Sequence` stops at its first failing child. It is
corrected in `line_station.xml`, and the behaviour is now asserted by
`RunningLine.AStationThatEscalatesCommandsNothingAndKeepsWhatItIsStandingIn` against the
shipped tree rather than inferred from the tree's shape.

## How the claims here were verified

In the style of [`toolchain.md`](../reference/toolchain.md). Everything below was checked on
**2026-08-27** unless stated.

| Claim | How | Result |
|---|---|---|
| `cross-cutting-safety.md:85-87` and `:140` | Read at `b54140f` | Quoted verbatim; line numbers exact. **But** the document's status is `DESIGNED` and "[b]inding from the first line of Phase 2 code" — so "locked rule" was too strong and is narrowed above |
| `line_station.xml:166-171`, `station_cycle.xml:42-45` | Read at `b54140f` | Exact |
| `recovery_policy.hpp:132-141`; `ResultCode` max is `UNREACHABLE=9` | Read at `b54140f` | Exact; `10` is the next free value |
| `MoveToHome` is a `SkillNode`; `record()` is unconditional; `RecoverFromFailure` reads the same key | `skill_nodes.hpp:462`, `:222`, `:305-311`; `line_nodes.hpp:870-892` | Confirmed by reading; **not** observed in a run |
| `cite_interfaces/srv/` has no reset | `find` at `b54140f` | Two files: `GetModelVersion.srv`, `SetMode.srv` |
| `cite_orchestration` has no service server at all | grepped for `create_service` at `b54140f` | Zero occurrences in the package |
| `ESCALATE` sets `STATE_BLOCKED`; `STOP_LINE` sets `STATE_FAULTED` | `line_nodes.hpp:894-899`, `:901-905` | Exact |
| The design already specified an `AwaitReset` with nothing to await | `L4-orchestration.md:89`, `:106` | Exact |
| A reset via `SetStationState` would destroy the reason | `line_nodes.hpp:818-822` | Clears `blocked_reason` whenever the new state is neither `BLOCKED` nor `FAULTED` |
| `LineState` cannot hold the reason afterwards | `LineState.msg:3-5`, `:31`; `line_maintenance.hpp:100-102` | Volatile STATE profile, "a periodic report of the present, not a record"; one line-level string; only the **first** blocked station's reason is published |
| `StationState` carries no reason field | `StationState.msg` read in full | Confirmed; `STATE_BLOCKED=3`, `STATE_FAULTED=4` |
| One faulted station makes a faulted line | `line_maintenance.hpp:105-106` | Exact |
| Four `setAborted` sites on `jazzy` | Fetched `ros2_controllers` `jazzy` HEAD, grepped | Codes at `:470/:517/:1264/:1830`; `setAborted` at `:472/:519/:1266/:1832` |
| Three sites at tag `4.40.1` | Fetched tag `4.40.1`, grepped | `preempt_active_goal` calls `setCanceled` at `:1919` |
| Jazzy's released `ros2_controllers` | `ros/rosdistro` `jazzy/distribution.yaml` | `4.42.1-1`; branch `package.xml` says `4.42.1` |
| `INVALID_JOINTS` / `OLD_HEADER_TIMESTAMP` never emitted | grepped `.cpp` and `.hpp` on `jazzy` | No occurrence in either file; conditions checked in `validate_trajectory_msg:1671+`, rejected at `:1411`/`:1416` |
| A ROS 2 rejection carries no reason | `rosidl_parser/definition.py:696-705` (`jazzy`) | Response is `boolean accepted` + `builtin_interfaces/msg/Time stamp` |
| `finishControllerExecution` takes only the action code | `action_based_controller_handle.hpp:221` (`jazzy`) | Exact |
| `ExecutionStatus` is a closed 7-value enum with no payload | `controller_manager.hpp:51-60`, `:99` | Exact |
| The capability collapse | `execute_trajectory_action_capability.cpp:126-147` | Exact; `SUCCEEDED`/`PREEMPTED`/`TIMED_OUT` pass, all else `CONTROL_FAILED` |
| `execute()` returns that code | `move_group_interface.cpp:862` | `return res->error_code;` |
| Sources of `PREEMPTED` and `TIMED_OUT` | `trajectory_execution_manager.cpp:1224`, `:1553` | `stopExecution()`; controller overran expected duration |
| MoveIt's replan policy | `plan_execution.cpp:225-228`, `:186-197`, `:94` | Exact; the brief's `:224-228` is off by one at the start |
| `jazzy` vs `main` on the four files | Fetched both, compared SHA-256, diffed | Two identical; `plan_execution.cpp` differs by one `#include <cstdint>`; `action_based_controller_handle.hpp` by one `and` → `&&`. **Not byte-identical** |
| Nothing fixed upstream | GitHub issue/PR search over `moveit/moveit2` | Zero hits for `PATH_TOLERANCE_VIOLATED`; no relevant open issue found. A survey, not a proof |
| moveit2#1738 | Fetched issue and comments via API | Opened 2022-11-18, closed 2022-11-29; the quoted comment is about logging a rejection; no code change |
| Controller holds on abort | `joint_trajectory_controller.cpp:481-490` (`jazzy`) | `decelerate_to_hold_position()` or `set_hold_position()`. That the state is **static** is reasoned, not measured |
| `tolerances.hpp` guard | Fetched `jazzy`, read `:297-311` | Guard at `:309`; `:307` is blank |
| UR quotations and date | UR Product Alert page + SW5.21 service manual page | "Safety notice for CB3 UR10", 24 September 2019; both sentences verbatim in both places |
| Nav2 includes `UNKNOWN` | `would_a_controller_recovery_help_condition.cpp:26-31`, `would_a_planner_recovery_help_condition.cpp:26-33` (`main`) | Present in **both** sets |
| Nav2 puts the condition first | `navigate_to_pose_w_replanning_and_recovery.xml:37-40`, `:44-53` | Condition is the first node of each recovery branch; retries bounded at 6 and 1 |
| FANUC / ABB behaviour | Web survey, secondary sources only | Shape confirmed; **no primary manual read — treat as unverified detail** |
| ISO 14118 "reset is not start" | Web survey; iso.org returned HTTP 403 | **Unverified.** Attribution is secondary-source; ISO 13849-1:2023 is where commentary puts reset-independence |
| Installed controller version in the image | Not checked — the container image is being rebuilt and this record was written under an instruction not to build | **Unverified.** `docker run --rm ros:jazzy-ros-base-noble apt-cache policy ros-jazzy-joint-trajectory-controller` settles it |
