# ADR-0061: Hold the box still while the jaws are shut on it

- **Status:** Proposed
- **Date:** 2026-09-22
- **Deciders:** Project owner, on a measured divergence and on what the real gripper does
- **Related:** [ADR-0003](0003-gazebo-harmonic.md),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0023](0023-simulated-grasping-via-attachment.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md) (superseded by this record),
  [ADR-0051](0051-restate-the-hull-grasp-gate.md),
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md), CLAUDE.md §3 (P1, P2, P4)

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
