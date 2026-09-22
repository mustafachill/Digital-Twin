# ADR-0061: Hold the box still while the jaws are shut on it

- **Status:** Proposed (corrected 2026-09-22) — **the Decision is unchanged**: the box is
  still held rigidly while the drive joint is stalled on it, and released when the jaws are
  commanded open. What was wrong is one supporting sentence under "It cannot fire on empty
  air", which claimed a mechanism (a rail exclusion) that does not actually keep the empty-air
  case out. See the section "Correction — 2026-09-22: the rail exclusion does not reject a
  mid-stroke free-air rest, and the implementation has been changed to a part-width window",
  immediately after this block.
- **Date:** 2026-09-22
- **Deciders:** Project owner, on a measured divergence and on what the real gripper does
- **Related:** [ADR-0003](0003-gazebo-harmonic.md),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0023](0023-simulated-grasping-via-attachment.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md) (superseded by this record),
  [ADR-0051](0051-restate-the-hull-grasp-gate.md),
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md), CLAUDE.md §3 (P1, P2, P4)

## Correction — 2026-09-22: the rail exclusion does not reject a mid-stroke free-air rest, and the implementation has been changed to a part-width window

The Decision is unchanged: the mechanism is still "hold the box rigidly while the drive
joint is stalled on it, release on command open." Only the **test that gates it** changed.

### What was written

Under "It cannot fire on empty air": *"Jaws closing on nothing never stall — they arrive
where they were sent and report `reached_goal=true`. So the empty case needs no code at
all."* **[Corrected 2026-09-22 — see the Correction section above.]**

That sentence described the `GripperActionController`'s own report, which is true and is
not what the implementation actually tested. `cite_simulation::GraspHold` cannot see
`reached_goal` — it is a Gazebo-transport-side plugin with no controller-manager connection
at all — so its own stall test read only the drive joint's raw position and velocity, and
excluded a rest position from triggering an attach solely by checking whether it sat at
either declared rail (`open_position` / `closed_position`). The reasoning behind that
exclusion, also in the same section, was that "a genuine stall on a part always settles
STRICTLY BETWEEN [the rails], because nothing this cell commands the jaws to ever asks for
exactly `open_position` or `closed_position` while something is actually between the pads" —
true, but it says nothing about where a close on **empty air** settles, and nothing in the
implementation established that such a rest is confined to the rails either.

### What is true

Jaws closing on empty air do come to rest, and where they come to rest is **wherever the
close was commanded to** — for this end effector's ordinary close, `gripper_default_grasp_width_m`
(0.045 m), that is **mid-stroke**, nowhere near either rail. A tester drove a `Grasp` on
empty air and the controller reported:

```
gripper: commanded 45.0 mm, reached 46.0 mm, stalled=false, reached_goal=true, effort=60.0 -> empty
```

46.0 mm is well clear of both `open_position` (≈ 88.9 mm of opening) and `closed_position`
(≈ 1.6 mm of opening), so the rail exclusion admitted it. Whether the plugin would then have
attached depended only on a declared graspable model standing within `attach_radius_m` — a
condition ordinary proximity to a work-piece satisfies routinely. One deliberate attempt
placing a box inside the capture radius and closing on nothing did not reproduce a false
attach; that is one trial, not a proof, and does not rescue the reasoning above.

### How it was found

A review read the plugin's source against its own header comment and noticed the rail
exclusion's premise — "closing on air can settle mid-stroke too, but that case is already
handled by condition 2 below finding nothing to attach to" — assumed away exactly the
gripper's ordinary operating point without checking it. A tester then measured the free-air
rest position directly, against the shipped `default_grasp_width_m`, and confirmed the rail
exclusion does not reject it.

### What replaces it

The attach test is now a **window**, not a rail exclusion: the drive joint's own position
must lie inside `[hold_position_min_rad, hold_position_max_rad]`, the two joint positions
`tools/cite_tools/generate/world.py` resolves at generation time from the facility's declared
part interval widened by the stall band at each edge — exactly the width window
`cite_skills::gripper_is_holding` already judges a stall inside (ADR-0052 option F) — inverted
through the end effector's own linkage (`GripperLinkage.position_for`, the same inversion
`cite_tools.validate.physical`'s discrimination check performs, ADR-0052 §A.7). On the shipped
model that window is **[47.615, 52.385] mm** of opening; the measured 46.0 mm free-air rest
falls **1.6 mm outside** its narrow edge, and a real grasp (49.3–49.9 mm, per the friction
campaign) falls inside it. `open_position` and `closed_position` are kept in the generated
world only for the release direction (`open_direction_`), which the window does not decide.

This is not a new mechanism and not a new fidelity claim: it is the same test the rest of the
system already makes, applied where the rail exclusion used to stand.

## Context

**The job is to move a box.** An arm arrives, the gripper clamps the box, the box goes on the
belt. Contact dynamics is not the point of this facility and never was.

**The simulation is less repeatable than the machine it models, and that is not acceptable.**
Two runs of `pick_and_place` on `cell_b`, one seed, one commit, minutes apart, put the box
**0.763 mm** apart. A real xArm 5 repeats to **±0.1 mm**. A simulation with no wind, no thermal
drift, no backlash and no wear was **seven times** less repeatable than the arm it stands for.

Two defects were found by instrumenting two runs and diffing them, and both are fixed:
the station's behaviour tree ticked on a **10 ms wall-clock sleep** with nothing waking it on an
event, and the scenario began its cycle while the box was still settling. After those, the same
instrument reads **0.331 mm**, and the residual drift concentrates in one place: **+343 ms** in
the single transition out of the grasp, against ±7–49 ms everywhere else.

**That is an observation of two runs and it is not a proven cause.** The campaign that measured
the 0.763 mm
([`2026-09-22-is-a-run-reproducible`](../measurements/2026-09-22-is-a-run-reproducible/ANALYSIS.md))
answered its localisation question **UNRESOLVED**, and forbids reading a cause out of it. What
that campaign does record is that a four-body grasp is a candidate it could not test:
*"a solver deterministic on one plane contact but not on a four-body grasp would produce exactly
the combination T5 permits."* **This record does not claim the friction grasp is the remaining
source of divergence.** It rests on two things that hold whatever today's divergence turns out
to be.

### One: friction was never claimed to hold this cell together

[ADR-0029](0029-simulated-grasping-by-friction.md)'s own consequence section concedes it:
*"Scenario gates rest on a rate over samples, not on a determinism guarantee. 68/68 with a
Wilson lower bound of 0.879 is what is known."*

### Two: its 84-trial campaign measured friction doing exactly one thing well and one thing badly

- **It stops the jaws in the right place.** 68/68 held, in position.
- **It cannot hold the box still.** Up to **34.3°** of roll between the pads while the pads
  themselves turn 0.14°, and the sensitivity runs the wrong way: median twist 0.71° → 9.60° →
  17.43° as `max_step_size` goes 0.002 → 0.001 → 0.0005. **The finer the physics, the worse the
  grasp** — a factor of **24.5** over a 4× change. ADR-0029 accepted that coupling *"with open
  eyes because the alternative does not grasp at all."*

**A mechanism that degrades as the physics improves is not fidelity.** And the knob does not
help: that campaign measured the friction coefficient as **not the controlling variable and
non-monotonic over a 4× range**, so the number nobody can know the true value of is not even the
lever.

### What the real gripper does

It clamps the box hard and lifts it, then opens to release. It does not hold at a friction
margin, and it does not drop parts. **A simulation that drops them is the less faithful of the
two.** Nor can this project calibrate the alternative: every object's friction differs, and none
of it is declared anywhere in `model/` — the only `<mu>` in the tree is a literal `1.0` in two
scenario files, with no L0 home.

### The precedent is already shipped and accepted

`cite_simulation`'s conveyor carries parts **kinematically**, and says so in its own header:
*"transport here is kinematic, not frictional … No claim about belt handling, accumulation
pressure or singulation can rest on this plugin."* A declared, deterministic mechanism whose
fidelity cost is written down is an established pattern in this tree. The grasp gets the same
treatment for the same reason.

## Decision

**While the gripper's drive joint is stalled, the box is held rigidly in the gripper frame. It
is released when the jaws are commanded open.**

That is the whole of it. Three properties keep it small, and each closes a specific failure this
project has already paid for.

### It does not touch the joint

The jaws still close, still meet the box's collision, still stop at its width, and still report
`stalled=true, reached_goal=false` with `position` at the box's width. **The signal the cell
reads is untouched — and it is the same signal the physical arm produces**, which is what makes
this a change to the plant and not to the contract. `cite_skills::gripper_is_holding`, custody,
`Pick`, `Place`, `Transfer` and L5's `CUSTODY_FIELDS` all keep working with no change at all.

The one thing that changes is that the box, having stopped the jaws, can no longer be twisted or
dragged by them afterwards.

### It needs no contact sensors

The trigger is the **drive joint's velocity**, read from the ECM against the same
`stall_velocity_threshold` and `stall_timeout` the `GripperActionController` already uses,
resolved from L0 into the generated world (P1: one source, two consumers).

This is what [ADR-0029](0029-simulated-grasping-by-friction.md)'s rejected Option A could not
do. That option proposed attaching on a *settled stall* too, and was rejected on cost because it
was framed as a **position** threshold: contact at q = 0.4056 rad and the settled stall at
q ≈ 0.409 rad, *"bracketed by 3 mrad"*, which needed per-pad `<sensor type="contact">` elements
the generated description does not contain. **A velocity is not bracketed by 3 milliradians.**
The cost that killed Option A is not present here.

### It cannot fire on empty air

Jaws closing on nothing never stall — they arrive where they were sent and report
`reached_goal=true`. **So the empty case needs no code at all.**
**[Corrected 2026-09-22 — see the Correction section above.]**

This is the exact failure that killed [ADR-0023](0023-simulated-grasping-via-attachment.md).
Its weld fired at first pad contact, *"before any contact force develops"*, and the record of
what that cost is unambiguous: *"Every lift observed during Phase 1.C was produced by this
plugin's `DetachableJoint`, not by a grasp … the fingers never closed on the work-piece, and the
cycle looked correct end to end regardless."* Measured: `Pick` **EXECUTION_FAILED 8/8** while
the weld carried the box 0.576 m. **Here that case is closed by construction rather than by a
check**, because there is no stall to trigger on.

### Held in the gripper frame, never to a finger

ADR-0023 welded the box to **one finger**. The box then followed that finger, stopped being an
obstacle, and the jaws closed through it to the commanded width *"feeling nothing"* — destroying
the stall the whole grasp-evidence chain is built on. Fixing the box to a link that does **not**
move with the jaws leaves it exactly where it is: still the thing the jaws are stopped against.

## Options considered

### Option A — tune the friction

Rejected on this project's own measurement: the coefficient is not the controlling variable and
is non-monotonic over a 4× range. There is no value to tune to, and no source for one — the
facility declares no friction anywhere.

### Option B — make the contact solver deterministic

Not available. `gz-physics` 7's dartsim plugin exposes a solver *type* and a collision detector
and **no iteration count**; ADR-0029 established that a knob ADR-0023 named does not exist in
this stack. Nothing in this tree can seed or pin the contact solve.

### Option C — restore ADR-0023's plugin

Rejected. It reports success on an empty gripper, which is worse than no plugin.

### Option D — hold the box while the jaws are stalled on it

**Chosen.** It keeps the one thing friction does well, removes the one thing it does badly, adds
no new evidence path, and needs no sensor the description lacks.

## Consequences

### What this gets us

- **The carry becomes deterministic**, and the box's orientation with it.
- **ADR-0029's orientation debt closes by construction.** A held box cannot roll 34.3°, and that
  record's own revisit list asks for exactly this: *"when `Transfer` or the Phase 1.D line needs
  a known part orientation."* The restriction ADR-0029 imposed — *"no scenario may assert how a
  part is oriented in the jaws"* — can be revisited, though this record does not lift it.
- **The physics timestep stops working against the grasp.** The coupling ADR-0023 refused and
  ADR-0029 accepted *"with open eyes"* is gone: finer physics no longer means a worse grasp.
- **One mechanism, declared.** As with the belt, what the simulator does for us is written down
  rather than emergent.

### What this costs us

- **A grasp that is evidenced does not fail.** The simulation can no longer produce a dropped
  box, so the dead ends [ADR-0038](0038-stop-the-line-without-ending-the-process.md) and
  [ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) record keep only their
  unit tests. **This is a deliberate decision by the project owner, not an oversight**, and it
  is the largest thing this record gives up.
- **No claim about grasp reliability, slip margin or required clamping force may rest on this
  plugin.** The conveyor's sentence, in the grasp's words.
- **`tools/cite_tools/validate/physical.py`'s hull-clearance rule cites friction as its
  premise** — *"The pads hold by friction alone (ADR-0029), so the contact surface is the
  mechanism"*. That justification needs re-deriving; the rule itself still has a job.
- **The simulation now flatters us about grasping, and this record says so plainly.** That was
  ADR-0023's stated cost and it returns here. What is different is the failure it can no longer
  hide: ADR-0023 reported success with an empty gripper, and this cannot, because it triggers on
  the stall that only a real obstacle produces.

### What we will have to revisit

- **When a physical arm arrives.** Phase 2.B is where this plugin's absence on the hardware path
  gets tested against a real clamp, and grasping remains the most likely sim/real divergence.
- **When the line needs a grasp that can fail.** The answer then is a declared failure
  injection, not a return to hoping the contact solver drops something.
- **If the box's final position does not improve.** This record is not promoted on intent —
  see the promotion condition below.

## Promotion condition

This record stays `Proposed` until all of:

1. A grasp on the box reports `stalled=true, reached_goal=false` with `reached_width_m` at the
   box's width, and a grasp on empty air reports `reached_goal=true`. **If either fails the
   change is abandoned rather than patched**, because patching it means weakening
   `gripper_is_holding`, which is the lie ADR-0023 shipped.
2. The before/after instrument is re-run: two runs of `pick_and_place` on `cell_b` under one
   seed, and the box's final-position spread is reported against the 0.763 mm and 0.331 mm
   already measured, **whichever way it goes**.
3. `pick_and_place` and `continuous_line` pass, still asserting where the box ends up.
