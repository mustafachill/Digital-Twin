# ADR-0063: The gripper's drive joint may not be clamped

- **Status:** Accepted
- **Date:** 2026-09-24
- **Deciders:** Project owner, on the measurement below
- **Related:** [ADR-0062](0062-the-clamp-is-modelled-end-to-end.md) (superseded by this record),
  [ADR-0061](0061-hold-the-box-while-the-jaws-are-shut.md) (restored intact),
  [ADR-0023](0023-simulated-grasping-via-attachment.md),
  [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md), CLAUDE.md §3 (P2)

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
commands, zero releases**. Each fresh goal restarts the controller driving the joint, and the
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
