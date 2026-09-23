# ADR-0062: The clamp is modelled end to end — the jaws stop at the box

- **Status:** Proposed
- **Date:** 2026-09-23
- **Deciders:** Project owner, as the final decision maker, in those words
- **Related:** [ADR-0061](0061-hold-the-box-while-the-jaws-are-shut.md) (amended by this record),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md),
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md), CLAUDE.md §3 (P1, P2)

## Context

**The owner's instruction, and it is the decision:** *"There is no friction. The gripper
clamps the box and releases the box, and that is how it is known. The whole system is designed
around that. No unnecessary over-engineering."*

[ADR-0061](0061-hold-the-box-while-the-jaws-are-shut.md) went half the distance. It models the
**hold** — the box cannot slip or twist once the jaws are shut on it — and it deliberately does
not touch the joint, so the **close** is still decided by the contact solver. That half was
measured and it is where the twin still comes apart.

**Measured, on a paired run with both sides recorded.** One signal, two Gazebos, the full
station cycle:

- Both sides were commanded the **same eight motions**, with identical durations and identical
  joint travel — shape deltas from **2.8e-18** rad. Planning, IK and the twin boundary are
  exonerated.
- The 0.229 rad difference at matched simulated times is therefore **pure phase**.
- **The phase breaks in exactly one place: the motion out of the grasp, by 1.34 s.** Before it
  the two sides drift by ±6 ms; at that step the shift jumps by **-1.336 s** and comes back
  **+1.435 s**. The commanded-shape deltas step four orders of magnitude at the same point,
  from ~5e-9 to ~6e-5 rad.
- Across two paired runs the box's final spread was **3.418 mm** and **0.146 mm** — a
  **23-fold** spread between runs. **Two runs. That is not a rate**, and it is too scattered to
  average.

**Why the close is the variable.** `GripperActionController` restarts its stall search on every
control cycle in which the joint exceeds `stall_velocity_threshold`, so — in ADR-0045's own
words, read from upstream source — *"the quantity the deadline is asked to bound has no upper
bound."* That record measured the distribution: median **5.38 s**, max **16.95 s**, **sd
3.81 s**. A close whose duration is drawn from that is a close that captures the box at a
different moment of its own settling on every run, and holds it in a marginally different pose.

**So the residual is not slip. It is when the box was caught.** ADR-0061 removed the slip and
left the catching to contact chatter.

## Decision

**The plugin stops the drive joint at the box's width. The clamp is modelled end to end.**

| the world | what the cell observes | how |
|---|---|---|
| a box is between the pads | `stalled=true`, `reached_goal=false`, `position` at the box's width | the plugin stops the joint there and holds the box, as it already does |
| nothing is between the pads | `stalled=false`, `reached_goal=true` | the plugin does nothing; the joint runs to its command, as it already does |

**Nothing above `ros2_control` changes, and no threshold moves.** The controller still reports
the stall, `cite_skills::gripper_is_holding` still judges it against the same declared window,
custody, `Pick`, `Place`, `Transfer` and L5 are untouched. What changes is that the stall
becomes **deterministic** instead of contact-derived: the same box produces the same stop, at
the same position, every run and on every side.

**The width window already in the plugin is what keeps the empty case out**, and it is not
relaxed. Jaws closing on nothing rest at 46.0 mm, measured, which is outside the declared
[47.615, 52.385] mm window; jaws on the box stop at its width, inside it.

## What this amends

ADR-0061's *"It does not touch the joint"* is amended, not corrected — it was right when
written and the decision it states has been changed here. The property it bought, that the
stall the cell reads is untouched, is **kept**: the stall is still reported by the controller,
still at the box's width, still the thing every consumer reads.

## Consequences

### What this gets us
- **The box is caught in the same pose every time**, so the identical motions that follow carry
  it to the same place.
- **The close stops being drawn from a distribution with no upper bound**, which is the one
  remaining quantity in the cycle decided by contact rather than by a command.

### What this costs us
- **The stall is now modelled rather than emergent.** The simulation reports a stall because the
  plugin stopped the joint, not because the physics resisted it. **No claim about clamping
  force, contact dynamics or grasp reliability can rest on this cell**, and the gripper's
  reported effort is no longer a measurement of anything physical.
- **It is a larger claim on the simulator than ADR-0061 made**, and the honest description is
  that the gripper is now a modelled mechanism end to end, like the belt.
- **The hardware path is untouched and is where this is checked.** A real clamp stops on a real
  box; Phase 2.B is where this stops being a claim about a plugin.

## Promotion condition

1. **The kill switch, unchanged from ADR-0061 and still an abandonment trigger.** A grasp on the
   box reports `stalled=true, reached_goal=false` with `reached_width_m` at the box's width; a
   grasp on empty air reports `reached_goal=true`. **If either fails the change is abandoned
   rather than patched.**
2. **The close is deterministic.** The drive joint's stop position and the close duration are
   measured on both sides of a paired run, and reported whatever they say.
3. **The paired box spread is re-measured against 3.418 mm and 0.146 mm**, and the sequential
   spread against 0.201 mm — **whichever way they go**.
4. `pick_and_place` and `continuous_line` pass.
