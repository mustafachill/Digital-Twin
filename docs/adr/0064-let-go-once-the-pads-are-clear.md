# ADR-0064: Let go once the pads are clear of the part

- **Status:** Proposed
- **Date:** 2026-09-24
- **Deciders:** Project owner — *"there is no friction: the arm clamps the box and puts it on
  the belt"*, and *"plan both and do the one that is right"*
- **Related:** [ADR-0061](0061-hold-the-box-while-the-jaws-are-shut.md) (amended by this record),
  [ADR-0063](0063-the-drive-joint-may-not-be-clamped.md) (names this as its successor),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md), CLAUDE.md §3 (P1, P5)

## Context

The twin's two digital sides are driven by one command stream and land the box in two places.
Three paired runs on `main` at `e41b445`, 2026-09-24, one machine, measured where that
difference is created rather than assuming it.

**The arm is not the problem, and this is the measurement that matters.** Read at each box's
own events, so the two worlds' clock phase cancels:

| | B1 | B2 | B3 |
|---|---|---|---|
| spread when the arm has finished lowering the box | 0.12 mm | 0.24 mm | 0.18 mm |
| spread once the box is at rest | **1.15 mm** | **1.12 mm** | **1.27 mm** |

Everything between those two rows happens **after the arm has stopped moving**. The arm stops
with the box **11.4-14.0 mm** above where it will rest, and the box then falls.

**The fall itself is deterministic. A contact during it is not.** The sideways travel of each
box during that fall, same three runs:

| | plant | counterpart |
|---|---|---|
| B1 | **0.003 mm** | 0.882 mm |
| B2 | **0.003 mm** | 1.257 mm |
| B3 | 1.341 mm | **0.003 mm** |

**One side of every run falls perfectly straight — three microns — and the other is pushed about
a millimetre sideways**, and which side is clean flips between runs. A box released with no
horizontal velocity and left alone moves 0.003 mm, which is what half the sample does. The other
half is touched by something on the way down.

**What touches it is the gripper, and the reason is a question this plugin asks wrongly.**
`grasp_hold.cpp` removes its weld when the drive joint has opened by more than
`detach_margin_rad`, which the generator fills from the gripper controller's own
`goal_tolerance`. That number answers *"has this joint moved meaningfully?"* — it is the
controller's own definition of the same position, and using it here was deliberate and
reasonable. **But the question this plugin needs answered is a different one: "have the pads let
go of the part?"** At `goal_tolerance` past the grasp the jaws have opened by a fraction of a
millimetre and are still against the part; the box becomes a free body while a pad is still
touching it, and an opening pad then flicks it.

The travel is almost pure world -Y with `x` changing by 0.17 mm, and it takes about 50 ms —
a horizontal velocity of roughly 27 mm/s, where the arm's own speed at that instant is
1.4-2.4 mm/s. The box is not carried; it is struck.

## Decision

**The weld is removed when the jaws have opened wider than any opening the grasp predicate
would call a grasp — not when the joint has merely moved.**

The threshold is `hold_position_min_rad`, which **already exists** in every generated world: it
is the open end of the part-width window `cite_skills::gripper_is_holding` judges a stall
inside, `0.382862254` on the shipped model, an opening of 52.385 mm against a 50 mm part. At
that position each pad is about 1.2 mm clear of the part, so no pad can reach it.

`detach_margin_rad` is **kept as a floor** and not deleted: it is still what stops joint jitter
from reading as a release, and it is still the controller's own number for that question. The
change is that both must now hold — the joint has genuinely moved, **and** the jaws are wider
than a grasp.

**No new parameter is declared, generated or plumbed.** One number that is already emitted is
asked a question it already answers.

## Options considered

### Option A — delay the release until the pads are clear
Chosen. It changes when the plugin lets go and nothing else: no motion changes, no arm goes
anywhere new, no generated artifact moves.

### Option B — close `PlaceAt`'s deliberate air gap so the part is resting when the jaws open
`release_height_m` is `0.04` against a part whose centre rests at `0.025`, a deliberate 15 mm
gap (`skill_nodes.hpp`). Setting it to the part's own half-height would remove the fall
altogether, and with it the airborne interval the flick needs.

**Not chosen first, and not rejected.** It moves the arm 12 mm lower into the belt, so it can
collide, it changes what two blocking scenarios assert, and the number it replaces was chosen to
stop the arm pressing the part into the surface. It treats the same symptom one layer further
from the cause: with Option A the box is not struck whether it falls or not. **If Option A's
measurement leaves a residual at the drop, this is the next rung and this record says so.**

### Option C — leave it and accept 1.2 mm
The project owner's bar is the ±0.1 mm a real xArm 5 repeats to, stated on 2026-09-24. 1.2 mm
is twelve times it, and half of every run already demonstrates that 0.003 mm is available.

## Consequences

### What this gets us
- **The outcome is already observed**, which is unusual for a fix: one side of every run behaves
  exactly as this change intends both sides to.
- If the fall stops being disturbed, what is left is the spread at release — **0.12-0.24 mm
  measured** — and that is within sight of the bar.

### What this costs us
- **The box is held rigid for slightly longer**, about 0.02-0.05 rad of extra jaw travel. During
  that interval the cell cannot show a part beginning to fall out of an opening gripper, which is
  a thing a real gripper can do. ADR-0061 already gave up more than this.
- **A part narrower than the declared window is released later still**, because the threshold is
  the window's open end rather than that part's width. Today's facility declares one part
  (ADR-0052 §A.5). A facility declaring two would want the wider one's threshold, and nothing
  here computes that — it is the same limitation `hold_stop_rad` carries, stated in the same
  place.

### What we will have to revisit
- **Whether the residual after this is the drop** (Option B) or something else. The instrument
  that answers it is the one that produced the tables above and it is not committed; if the bar
  is reached, this stops being an ADR's evidence and becomes a published campaign.

## Promotion condition

1. **Three paired runs**, reported whatever they say, against the three above: the spread at
   rest, the spread at release, and the sideways travel of each box during its fall. **The
   sideways travel is the load-bearing one** — this change is refuted if a side still travels a
   millimetre.
2. **The grasp is untouched.** A grasp on the box still reports `stalled=true,
   reached_goal=false`; a grasp on empty air still reports `reached_goal=true`. **If either
   fails the change is abandoned rather than patched**, which is ADR-0061's kill switch and is
   not weakened here.
3. `pick_and_place` and `continuous_line` pass on `cell_b`.
