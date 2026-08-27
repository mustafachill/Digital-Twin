# ADR-0031: Refuse a direct arm-to-arm handoff at plan time until a grasp holds an orientation

- **Status:** Accepted (corrected 2026-08-26) — **both halves of the decision stand**: the
  direct arm-to-arm edge is still refused and the conveyor-mediated one is still permitted.
  The *justification* given below for permitting the conveyor case is false, and the
  arithmetic given for refusing the direct one is keyed to the wrong angle. Neither is
  withdrawn from the record; both are marked where they stand. See the section
  "Correction — 2026-08-26: nothing re-observes the part, and the gripper is what makes the
  conveyor case safe", immediately after this block.
  Recorded **after** the change landed, not before, which CLAUDE.md
  §12 requires and this did not get. The decision existed only in the message of commit
  `7f7f451` until this ADR was written during the documentation pass following `b2be77f`.
  Stated rather than smoothed over (P7).
- **Date:** 2026-08-26
- **Deciders:** Project owner
- **Related:** [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0026](0026-joint-space-goals-on-under-six-dof-arms.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0032](0032-index-the-belt.md) (timing, **not** orientation — see the correction),
  [L3](../architecture/L3-capabilities.md), [L4](../architecture/L4-orchestration.md),
  [`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md)
- **Evidence for the correction:**
  [`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
  — 74 trials, thresholds registered in
  [`criteria.md`](../measurements/2026-08-26-conveyor-yaw-transfer/criteria.md) before the
  first scored trial ran

## Correction — 2026-08-26: nothing re-observes the part, and the gripper is what makes the conveyor case safe

The decision is unchanged. What was wrong is why it was made, on both sides of it. The
campaign that establishes this is
[`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md);
it is the authority for every trial figure in this section, and its numbers are not restated
anywhere else (P1). One paragraph below — the one about the axis of the published residual —
comes instead from a re-analysis of the two *earlier* campaigns' raw data, and says so.

### What was written

1. That a conveyor-mediated handoff is safe because "the receiving station re-observes it
   with `Detect`, whose `Detection.pose` is a full pose. The uncertainty is *measured away*."
2. That after a `Pick` "the line does not know the part's **yaw** about the tool axis",
   quantified as ±18.7°, and that at 18.7° a 50 mm cube presents 63.4 mm across jaws
   commanded to 45 mm, so "the pads would meet a corner and cam it out rather than grip it."

### What is true

**Nothing re-observes the part.** The only pose sensor in the model is a through-beam, which
reports occupancy. `cite_skills::mark_pose_unobserved` now leaves `Detection.pose`
explicitly unobserved — empty `frame_id`, zero stamp, NaN components — and
`detection_server.cpp` says so on its SUCCESS path. Before that change the claim was already
false in a worse way: the pose the beam returned carried the beam frame's own constant
`rpy (0, 0, 0)`, so the residual was being "measured away" by a hard-coded identity, which
is the assumption this gate exists to refuse wearing the costume of a measurement.

**The belt removes nothing.** Across six starting yaws from 0° to 45° and both belt modes,
the yaw at the outfeed equals the yaw the part started at: pooled median |Δ| **0.0000°** over
36 trials, largest single value anywhere **1.8 × 10⁻⁸ degrees**. Both mechanisms that could
have made the ride matter are refuted — no squaring by settling, and 0 of 36 trials arriving
above 1 °/s. Three control trials spawned under a name outside the world's `<carry>` list
travelled **0.0000 m**, so the null is not the artefact of a part that was never carried.

**The pick is safe anyway, to at least 30°** — the largest yaw tested, and the pooled result
is 23 of 23 successful picks over 0–30°, Wilson 95% [0.857, 1.000]. Success was judged
physically (lift, held through transport, placed within tolerance) and **not** by
`pick_reported_holding`, which `criteria.md` pre-registered as unusable and which duly
returned true in all 23 while discriminating nothing.

**The reason is the gripper, not the belt.** A square held at two opposite corners by flat
parallel jaws is in unstable equilibrium: the contact normals miss the centre, so squeezing
produces a couple that rotates the part until a face lies flat on each pad. Two witnesses
from different subsystems agree — in the physics pose feed a part spawned at 30° is *carried*
at 0.03°, and in `/joint_states`, read through the L0 axial map, the jaws stall at
48.8–49.96 mm at every level, where a part still at 30° would have stopped them at 68.30 mm.

**So the cam-out arithmetic is inverted in practice.** The geometry in the Context is right:
at 18.7° the part does present 63.4 mm to a 45 mm closure, and the pads do meet a corner.
What they then do is cam the part **into** alignment rather than out of it.

**And 18.7° was never a yaw.** Re-analysed on 2026-08-26 by re-implementing the friction
campaign's own `harness/axis_check.py` arithmetic — a re-analysis of published data, not a
new campaign; the method is written out in the *Correction, 2026-08-26* section of
[`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
— over all 72 carries in the two published campaigns'
`step0p001`, `step0p0005`, `paired` and `paired2` blocks: the net carry rotation lies along
the **pad-to-pad axis**, which is horizontal (|cos| ≥ 0.9776 in every trial), its component
about the world vertical never exceeds **0.49°**, and the part's yaw about the world vertical
never leaves 0.00–0.84° anywhere in any carry. The trial that produced the 18.71° figure is a
roll of 18.71° about that horizontal axis with a vertical component of **0.01°**. The
published residual is real; it is a **roll between the pads, not a yaw about the tool axis**,
and the presented-width arithmetic above — which is a function of yaw — was applied to an
angle that is not one.

### What survives, unchanged

**The decision, in full.** `plan_line` still refuses an outbound edge whose receiving station
has a robot actor and whose `via_asset_id` is empty, and still permits conveyor-mediated
edges. Nothing in the *Decision* section is withdrawn.

**The refusal is not weakened by any of this, and must not be read as licensing its removal.**
What rescues the conveyor case is that the *receiving* gripper removes the yaw by closing on
it. That ground is not conveyor-specific — jaws square a part up whoever holds it — but it
**cannot** carry over to a direct handoff, because a part clamped by the giving gripper
cannot rotate into alignment with the receiving one. The mechanism that rescues one case is
precisely the one the other denies. The campaign did **not** test a direct handoff; it says
so itself, and lists that experiment as work not done.

**The permission now rests on a physical result rather than on a detector.** That is a
better footing than it had, and a narrower one: it holds for a part the receiving gripper
closes on, and for nothing else.

**Option A's rejection is corroborated**, and by the campaign's own metric rather than by
argument. This record rejected "let it fail at run time" because a bad grasp reports holding
rather than failing. `criteria.md` pre-registered `pick_reported_holding` as unusable for
exactly that reason, and it then returned true in all 23 trials while discriminating nothing.
A runtime gate on that signal would have been a gate on nothing.

### How fragile the new ground is

The squaring-up is a rigid-body contact result from DART, with `mu = mu2 = 1.0` declared on
the work-piece and **no friction declared on the pads or on the table**. The campaign names
it as the most simulator-dependent thing it measured and as the single largest sim/real
divergence risk on its books: compliant pads, chamfers or burrs, and real surface friction
may align a part less willingly, or not at all. **Phase 2 must re-measure this before any
handoff is built on it.** The whole of the permission's new justification rests on it.

### ADR-0032 is a timing fix and has nothing to do with this

[ADR-0032](0032-index-the-belt.md) stops the belt so a station has a pick window. Whether
that also changes the arrival yaw was pre-registered and measured: paired within trial, the
median difference between a reading taken in motion and one taken after the belt has stopped
and settled is **0.0000°**, two-sided permutation **p = 0.7417**. Indexing neither helps nor
hurts orientation. A reader who assumes the two fixes are the same fix will build a handoff
on a belt stop that does nothing for it.

### How the error survived

The false sentence was not an unexamined guess about physics — it was a claim about **our
own message**, and it could have been checked with `ros2 interface show` and ten lines of
the detection server. `Detection.pose` exists as a field, so a reader who knew `Detect` was
in the vocabulary could write "the receiving station re-observes it" and be describing the
*type* correctly while being wrong about every implementation of it. The type system carried
the claim past review: a `PoseStamped` has no absent state, so a beam with nothing to say
filled the field with its own mounting pose and the record read that as an observation.
The lesson is narrow and repeatable: **a field's existence is not evidence that anything
fills it.** Before resting a decision on a value, read the server that writes it, not the
`.msg` that declares it.

The second error is a different kind and worth separating. "Residual rotation" was carried
from one campaign into another record without its **axis**, and an angle without an axis
cannot be put into a trigonometric argument. The published harness reports `twist_max_deg`
as a magnitude, the axis was checked once in that campaign and mentioned in prose, and by
the time the number reached this record it had become "yaw" because yaw was the quantity the
argument needed.

## Context

[ADR-0024](0024-handoff-split-between-l3-and-l4.md) settled *who owns what* in a handoff:
L4 owns ownership and the rendezvous token, L3 owns one robot's half of the motion. It
deliberately kept `Transfer` in the vocabulary so that a **direct** arm-to-arm handoff —
both grippers on the part at once, release order mattering — would not require re-adding a
skill later. It did not ask whether a direct handoff is *physically* possible in this cell.

It is not, and the reason is measured.
**[Corrected 2026-08-26 — see the Correction section above. A direct handoff has never been
attempted or measured in this cell; what is measured is that a grasp does not hold an
orientation. The edge is refused because nothing establishes the part's orientation between
two grippers, not because the operation was tried and failed.]**
A grasp here holds a **position, not an
orientation**. The 40-trial interleaved campaign in
[`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md)
took rotations above 20° from 60% of trials to 0% (p < 0.0001) by correcting the
grasp-plane offset, and left a **residual of up to 18.7°** of rotation of the part *within*
the jaws. [ADR-0029](0029-simulated-grasping-by-friction.md) carries that as a recorded
open divergence.

So after a `Pick`, the line does not know the part's yaw about the tool axis.
**[Corrected 2026-08-26 — see the Correction section above: the measured residual is a roll
about the pad-to-pad axis, not a yaw about the tool axis.]** Two handoff
topologies inherit that differently:

- **Conveyor-mediated.** The giver releases the part onto the belt before the receiver
  touches it, and the receiving station re-observes it with `Detect`, whose
  `Detection.pose` is a full pose. The uncertainty is *measured away*.
  **[Corrected 2026-08-26 — see the Correction section above. Nothing re-observes the part;
  the conveyor case is safe for a different, measured reason.]**
- **Direct arm-to-arm.** The receiver closes at the rendezvous pose while the giver still
  holds the part. Nothing re-observes it in between, so the receiving jaws close on a part
  whose yaw is unknown to ±18.7°.
  **[Corrected 2026-08-26 — see the Correction section above. "Nothing re-observes it" is
  confirmed; "±18.7° of yaw" is not — that figure is a roll.]**

Symmetry does not rescue the direct case. The cell's reference work-piece is a 50 mm cube,
so its symmetry about the approach axis has a period of 90°, and 18.7° is not a multiple of
90°. Across a square section rotated 18.7° the part measures 50·(cos 18.7° + sin 18.7°) =
**63.4 mm**, against the 45 mm the jaws are commanded to. The pads would meet a corner and
cam it out rather than grip it.
**[Corrected 2026-08-26 — see the Correction section above. The width arithmetic is right
and its input angle is not; and where the pads do meet a corner, they were measured to cam
the part into alignment rather than out of it.]**

The decision was forced now, and not deferred, because `cite_orchestration` stopped running
one hand-written station and started **building the line from the L0 topology**. A planner
that derives stations from edges must decide what to do with an edge it cannot execute.

## Options considered

### Option A — Plan it and let it fail at run time
Build the direct-handoff subtree; the receiving `Pick` fails on a bad grasp, and recovery
handles it.

Rejected. The failure is not reliably a failure. A cammed-out grasp can report a stall and
`gripper_is_holding` can read holding while the part sits crooked or is dropped a moment
later, so the line's most likely outcome is a *wrong* answer rather than an error — the
same class of silent success that ADR-0029's attachment plugin produced. Spending a bounded
recovery budget on a physically impossible operation also converts a design gap into an
intermittent runtime fault, which is the hardest kind to diagnose.

### Option B — Assume the part is square to its frame
Treat the yaw as nominal, as `trees/station_cycle.xml` does for a part placed by hand at
the start of a scenario.

Rejected. That assumption is true of a part nobody has gripped and false of one that has
just been through a gripper — which is precisely every part arriving at a handoff. It would
encode as a default the one thing the measurement says is not true.

### Option C — Add an orientation observation between the grippers
A camera or a re-`Detect` at the rendezvous pose. This is the *right* long-term answer.

Not chosen now because it is Phase 1.D-or-later work with no sensor to do it: the only pose
sensor in the model is a through-beam, which reports occupancy and not orientation.

### Option D — Refuse the edge at plan time, with the measurement named. Chosen.

## Decision

**`plan_line` refuses an outbound edge whose receiving station has a robot actor and whose
`via_asset_id` is empty** — that being exactly the shape of a direct arm-to-arm handoff —
and puts the refusal, with the 18.7° measurement and its source, into `plan.refusals`. A
plan carrying refusals is not `usable()`, so the line does not start.

The refusal is a **property of the topology, checked once at plan time**, not a runtime
branch. Today's L0 topology contains no such edge — every transfer-to-transfer edge names a
conveyor — so nothing is refused in practice and nothing is lost.

**`Transfer` and its `TransferTo` leaf stay built and tested against their contract.** What
stands between here and a direct handoff is orientation certainty, not code.

## Consequences

### What this gets us
- An impossible operation is impossible to start, rather than intermittently wrong.
- The reason is attached to the refusal, so whoever first authors such an edge is told what
  the blocker is and where the measurement lives, instead of debugging a dropped part.
- ADR-0024's protocol is unchanged and untouched: this constrains which topologies may run,
  not how a handoff is negotiated.
- The gate is a single predicate over the topology, so lifting it is deleting one check
  once the observation exists — not unpicking assumptions spread through the tree.

### What this costs us
- **`Transfer` now has a server and no caller**, and `TransferTo` is reachable in no shipped
  tree. It is verified against its contract by unit tests and by nothing else, which is a
  weaker guarantee than the other five skills have and should be read as one.
- **The refusal is a design-time approximation of a physical fact.** It keys on "the
  receiver is a robot and no asset mediates", which is a structural proxy for "nothing
  re-observes the part". A future edge that mediates through an asset which does *not*
  re-observe — a passive chute, say — would pass this check and should not.
  **[Corrected 2026-08-26 — see the Correction section above. The cost is real and larger
  than stated: *nothing* re-observes the part on any edge, mediated or not, so the proxy
  never distinguished what it was said to distinguish. What the check now stands for is
  "the receiving gripper gets to close on a free part", which is what was measured.]**
- The 18.7° figure is a **simulation** measurement. It is the right basis for refusing in
  simulation; whether the physical gripper's residual is larger or smaller is unmeasured,
  and Phase 2 has to establish it rather than inherit this number.
  **[Corrected 2026-08-26 — see the Correction section above. It is a simulation
  measurement, and it is a roll rather than a yaw, so it is not the right basis for this
  refusal. The Phase 2 obligation stands and now covers the squaring-up mechanism too.]**
- A cell that genuinely needs direct handoff cannot be modelled at all until the gate lifts,
  even to develop against.

### What we will have to revisit
- **When an orientation observation exists** — a camera at the rendezvous, or a `Detect`
  that returns a full pose between the grippers — the gate should be replaced by a
  requirement that the edge carry such an observation, not simply deleted.
- **If the residual is driven to a multiple of 90°, or below the cam-out bound**, the
  symmetry argument changes and the arithmetic above has to be redone against the actual
  part and the actual commanded width, not assumed to still hold.
  **[Corrected 2026-08-26 — see the Correction section above. There is no cam-out bound to
  fall below in simulation: within the tested range the pads meeting a corner is what
  aligns the part. The clause to keep is the last one — redo the arithmetic against the
  actual part and the actual commanded width rather than assuming it still holds.]**
- **If a non-cubic work-piece is introduced**, the 90° period disappears and the bound gets
  stricter, not looser.
- **When the squaring-up is re-measured with friction on the pads, or on hardware.** The
  permission's whole justification is that result. If a compliant or chamfered part does not
  square up, the conveyor case loses its ground and has to be re-decided — which is a new
  ADR, not an edit to this one.
