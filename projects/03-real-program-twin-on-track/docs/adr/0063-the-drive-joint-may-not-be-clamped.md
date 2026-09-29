# ADR-0063: The gripper's drive joint may not be clamped

- **Status:** Accepted — **the Decision is unchanged and binds exactly as written**: the
  simulation may not stop, limit or otherwise take hold of the gripper's drive joint. Two
  sections follow this block and must be read before the body. "Amendment — 2026-09-24: Option
  A's two halves are separable, and the L3 confirmation ships without the clamp" splits an
  option this record rejected as one thing; "Correction — 2026-09-24: the 116 commands are both
  sides of a pair" repairs a figure that does not reconcile as the body states it. Neither
  touches the Decision, the clamp, or any of the four measured arms.
- **Date:** 2026-09-24
- **Deciders:** Project owner, on the measurement below
- **Related:** [ADR-0062](0062-the-clamp-is-modelled-end-to-end.md) (superseded by this record),
  [ADR-0061](0061-hold-the-box-while-the-jaws-are-shut.md) (restored intact),
  [ADR-0023](0023-simulated-grasping-via-attachment.md),
  [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md), CLAUDE.md §3 (P2)

## Amendment — 2026-09-24: Option A's two halves are separable, and the L3 confirmation ships without the clamp

**What this record rejected, and what it did not.** Option A below is one line — *"keep the
clamp and teach L3 to wait for the release"* — and it was rejected as one thing. It is two
things, and only the first is closed:

- **The clamp stays rejected, permanently and without qualification.** The Decision is
  untouched. Nothing in the simulation may constrain that drive joint, and any future argument
  for it owes its own measurement, exactly as the Decision says.
- **An L3 confirmation of the release ships, WITHOUT the clamp**, in the commit after this
  record. `SkillServer::release_jaws` commands the jaws fully open, reads the outcome back
  through `cite_skills::gripper_is_holding`, and fails if they still read as holding.

**Why the measurement does not carry over.** The third arm of the table below is *"the clamp,
plus an L3 confirmation of the release"* — the confirmation **against the clamp**, which is
gone. Its 116 commands and zero releases measure what re-asking buys while a second mechanism
holds the joint shut; they measure nothing about a cell where nothing holds it. Reading that
row as a verdict on confirming a release is reading a control arm as a treatment.

**And the half of Option A that measurement actually condemned is not what ships.** What the
third arm did was **re-ask**: it re-commanded the open until a deadline expired. That loop is
**removed**. What ships is one command, one answer, and a failure if the answer says the jaws
are still on the part. There is no second deadline, no poll interval and no iteration cap
anywhere on the path; a single command's own answer is already bounded by the declared
`gripper_result_timeout_` inside `command_gripper`, counted in the node's own clock (ADR-0045).

The loop was removed for reasons of its own, independent of anything here, and they are
recorded so nobody rebuilds it:

- It **could not be cancelled**. `command_gripper`'s wait breaks on a ready future before it
  tests for cancellation, so against a controller answering in about 1.3 ms the 20 ms
  cancellation poll never ran. L4's fault branch waits on the goal *ending*, so the belts of an
  escalating station kept running for the whole window.
- Its bound was **twice** the declared timeout, because the condition was evaluated after each
  command.
- It read `result_timeout_s` as *"how slow a release may be"*, which that value's own L0 block
  forbids in capitals: the time a stall takes to be declared has no upper bound, so no value
  there can mean "too slow".

**A residual this record must carry, because it is what an operator meets.** On the confirmed
failure the skill stops and escalates — into [ADR-0038](0038-stop-the-line-without-ending-the-process.md)'s
`AwaitReset`, which waits for a person with no deadline — and **the jaws are left commanded
fully open at the configured effort, and that command persists**. Nothing further is sent. When
whatever is binding the jaws lets go, the part falls, with nobody expecting it. **What is
commanded there is deliberately not changed here**: drop-safe versus hold-safe is a
project-owner decision and this record does not take it. What the change does is **say so** —
the failure's own detail string names the state the gripper is left in, so the person walking
up to the cell is told rather than surprised.

**What is NOT established, and the confirmation is explicitly unimplemented on hardware.** What
produces `stalled` on the physical path is unknown in this repository. L0 says twice that the
physical gripper is driven through the SDK's service layer and has **no
`GripperActionController` at all**, and that *"nothing here should be read as claiming the two
paths detect a stall alike, because they do not."* The *check* is backend-agnostic — it reads a
reported outcome against the facility's declared part interval, not a controller's internal
rule — but its *input* on hardware has no established producer. A physical server that never
sets `stalled` makes this confirmation a permanent no-op there, which is P2 broken in the
direction that matters. It is marked unimplemented (Definition of Done item 5) rather than
claimed as parity.

## Correction — 2026-09-24: the 116 commands are both sides of a pair, not one

**What was written.** *"116 commands, zero releases"*, under "Asking again makes it worse",
with no scope.

**What is true.** That figure is **both sides of a pair together** — about **58 each** — which
is how [`../open-work.md`](../open-work.md) #87 states the same measurement, and the scope was
dropped on the way into this record.

**Why it matters rather than being pedantry.** Read as one side it does not reconcile with
anything else in this record. Upstream cannot terminate a goal that never reaches its command
sooner than `stall_timeout` after `accepted_callback`, and `stall_timeout` is **0.3 s**, so one
side's ceiling over a 20 s window is about **66**. 116 on one side is impossible; 116 over two
is ordinary. A reader checking the arithmetic finds a contradiction and has no way to tell
whether the figure, the timeout or the window is wrong.

**How the error survived.** The figure was carried from the investigation into two documents and
only one of them kept the scope. Nothing checks a number quoted in two places against itself,
and the arithmetic that falsifies the one-sided reading needs an upstream constant that is in
neither document.

## Context

[ADR-0062](0062-the-clamp-is-modelled-end-to-end.md) decided that the simulation plugin should
**stop the drive joint at the box's declared width**, so that the instant the box is captured
stops being decided by the contact solver. It was implemented and measured on 2026-09-24. The
measurement refuted it.

**What the twin is being asked to do.** Two independent Gazebo simulations of one cell, driven
by one command stream through the twin boundary, must put the box in the same place. The
measured paired spread before this work was **2.418 mm**, with 3.418 mm and 0.146 mm on earlier
runs. A real xArm 5 repeats a taught position to **±0.1 mm**.

**What was already established and is not re-argued here.** The commanded trajectories are
identical on both sides — eight motions, identical durations and travel, joint-shape deltas from
**2.8e-18 rad** — so planning, IK and the boundary are exonerated. The two boxes are identical
to **0.0000 mm** for 19 s while nothing touches them and first differ at **exactly the instant
the box first moves**. The divergence is born at first jaw contact.

## The measurement

Four arms, each on a host confirmed empty of containers before it ran, one machine.

| arm | close | release | paired spread |
|---|---|---|---|
| ADR-0061, unchanged | `reached 49.7 mm`, contact-decided | clean | **2.418 mm** |
| ADR-0062's clamp | `reached 50.0 mm`, deterministic | late — the box was released mid-retreat | **74.68 mm** |
| the clamp, plus an L3 confirmation of the release | `reached 50.0 mm` | **never happened** | no placement at all |
| the early attach with the clamp removed | jaws close through the box | — | eliminated |

**What the clamp achieved, and it is the half worth keeping.** Both sides captured the box at
**exactly `0.405605 rad`** — the declared part width — in every run of every arm that used the
crossing detector. The capture instant *can* be made deterministic, and nothing below retracts
that.

**How the release broke, read from the drive joint rather than inferred.** A single-side run
recorded the joint through a whole cycle. Under the clamp it moves **twice** and is otherwise
dead still: `0.0000 -> 0.4056 rad` in 0.49 s for the close, stopping dead at the limit, and
`0.4056 -> 0.0009 rad` in 0.45 s for the open. Under ADR-0061 it never stops moving at all,
jittering continuously against the part it is pressed into.

The open is the failure. The controller accepts the goal and the joint does not move for its
`stall_timeout` of **0.3 s**, so `GripperActionController` declares a stall and returns
`commanded 88.9 mm, reached 50.0 mm, stalled=true, reached_goal=false`. The control arm, at the
same point in the same cycle, returns `reached 88.1 mm, reached_goal=true`. `Place` proceeds to
the retreat on that success, and the box is released **39 mm above the belt** against a
deliberate 15 mm air gap, at whatever point of the retreat the joint finally opened — which
differs between the two sides. That is the 74.68 mm.

**Asking again makes it worse, which is what settles the mechanism.** With `Place` confirming
the release and re-commanding until the declared `gripper_result_timeout_` expired: **116
commands, zero releases**. **[Corrected 2026-09-24 — see the Correction section above.]** The
116 is both sides of a pair together, about 58 each; one side's ceiling over that window is
about 66. Each fresh goal restarts the controller driving the joint, and the
joint stays pinned for the whole window. A travel limit and `gz_ros2_control`'s command on the
same joint are in conflict.

**Why the clamp cannot simply be dropped.** Attaching before contact — the crossing detector
without the travel limit — merges the box into the arm's skeleton, `<self_collide>` is `false`,
and the box stops being the obstacle the jaws stall against: `commanded 45.0 mm, reached
46.0 mm, stalled=false, reached_goal=true -> empty`, with the box in the jaws. That is exactly
the failure [ADR-0023](0023-simulated-grasping-via-attachment.md) shipped and ADR-0061's own
header documents. **The early attach requires the clamp, and the clamp breaks the release.**

## Options considered

### Option A — keep the clamp and teach L3 to wait for the release
Implemented and measured: the third row above. It converts *"the box is dropped in the wrong
place"* into *"the box is never released"*, which is safer and still not a working cell. It also
means teaching the capability layer to work around a simulation plugin's grip on a joint, which
is a P2 hazard in its own right: no physical gripper has this conflict.
**[Amended 2026-09-24 — see the Amendment section above.]** This option is two things and only
the clamp half is closed. An L3 confirmation of the release ships without the clamp, and
without the re-asking this row measured.

### Option B — keep the early attach and drop the clamp
Implemented and measured: the fourth row above. A real grasp is reported empty. Rejected by
ADR-0061's own abandonment trigger.

### Option C — widen `stall_timeout` so the controller waits for the joint
Not implemented and not measured. Rejected without measuring: it is tuning a threshold to hide a
defect, which this project forbids, and it would change what a stall means on **both** backends
to accommodate one simulation plugin.

### Option D — revert to ADR-0061 and attack the held pose instead
Chosen.

## Decision

**The simulation may not stop, limit, or otherwise take hold of the gripper's drive joint.**
That joint has one owner — `GripperActionController` through `gz_ros2_control` — and a second
mechanism constraining it produces a cell that cannot let go. ADR-0062 is superseded and its
implementation is reverted in full; ADR-0061's plugin stands exactly as it was.

**The problem ADR-0062 was written for is not solved and is not abandoned.** The divergence is
still born at first jaw contact, and what decides where the box ends up in the gripper is still
the contact solve: `components::DetachableJointInfo` carries only `parentLink`, `childLink` and
`jointType`, so a weld freezes whatever relative transform exists on the step it is created.
Giving that transform a source other than the contact solve is the next decision, and it is a
separate record.

## Consequences

### What this gets us
- A cell that picks and places again, at the 2.418 mm the record started from.
- One mechanism eliminated **by measurement rather than by argument**, with the arms published
  above so nobody re-proposes it.
- The knowledge that a deterministic capture instant is reachable — `0.405605 rad`, both sides,
  every run — which the next record builds on.

### What this costs us
- **The 2.418 mm is not fixed, and the ±0.1 mm bar the owner set is not met.** This record buys
  a working cell and a closed door, not a result.
- A day of implementation and four measured arms, spent to learn where not to reach.

### What we will have to revisit
- **Why the joint sits dead for ~0.3 s under a tightened travel limit and then moves at a
  saturated 2.0 rad/s** — against a control that peaks at 0.952 rad/s — is **unestablished**.
  It was reproduced single-sided on a clean host and is attributed to nothing.
  [`docs/open-work.md`](../open-work.md) #87 holds it with the measurement that would settle it.
- If a future change ever needs the simulation to influence that joint, this record is what it
  must argue against, with its own measurement.
