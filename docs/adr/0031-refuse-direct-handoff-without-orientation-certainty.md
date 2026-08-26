# ADR-0031: Refuse a direct arm-to-arm handoff at plan time until a grasp holds an orientation

- **Status:** Accepted — recorded **after** the change landed, not before, which CLAUDE.md
  §12 requires and this did not get. The decision existed only in the message of commit
  `7f7f451` until this ADR was written during the documentation pass following `b2be77f`.
  Stated rather than smoothed over (P7).
- **Date:** 2026-08-26
- **Deciders:** Project owner
- **Related:** [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0026](0026-joint-space-goals-on-under-six-dof-arms.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [L3](../architecture/L3-capabilities.md), [L4](../architecture/L4-orchestration.md),
  [`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md)

## Context

[ADR-0024](0024-handoff-split-between-l3-and-l4.md) settled *who owns what* in a handoff:
L4 owns ownership and the rendezvous token, L3 owns one robot's half of the motion. It
deliberately kept `Transfer` in the vocabulary so that a **direct** arm-to-arm handoff —
both grippers on the part at once, release order mattering — would not require re-adding a
skill later. It did not ask whether a direct handoff is *physically* possible in this cell.

It is not, and the reason is measured. A grasp here holds a **position, not an
orientation**. The 40-trial interleaved campaign in
[`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md)
took rotations above 20° from 60% of trials to 0% (p < 0.0001) by correcting the
grasp-plane offset, and left a **residual of up to 18.7°** of rotation of the part *within*
the jaws. [ADR-0029](0029-simulated-grasping-by-friction.md) carries that as a recorded
open divergence.

So after a `Pick`, the line does not know the part's yaw about the tool axis. Two handoff
topologies inherit that differently:

- **Conveyor-mediated.** The giver releases the part onto the belt before the receiver
  touches it, and the receiving station re-observes it with `Detect`, whose
  `Detection.pose` is a full pose. The uncertainty is *measured away*.
- **Direct arm-to-arm.** The receiver closes at the rendezvous pose while the giver still
  holds the part. Nothing re-observes it in between, so the receiving jaws close on a part
  whose yaw is unknown to ±18.7°.

Symmetry does not rescue the direct case. The cell's reference work-piece is a 50 mm cube,
so its symmetry about the approach axis has a period of 90°, and 18.7° is not a multiple of
90°. Across a square section rotated 18.7° the part measures 50·(cos 18.7° + sin 18.7°) =
**63.4 mm**, against the 45 mm the jaws are commanded to. The pads would meet a corner and
cam it out rather than grip it.

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
- The 18.7° figure is a **simulation** measurement. It is the right basis for refusing in
  simulation; whether the physical gripper's residual is larger or smaller is unmeasured,
  and Phase 2 has to establish it rather than inherit this number.
- A cell that genuinely needs direct handoff cannot be modelled at all until the gate lifts,
  even to develop against.

### What we will have to revisit
- **When an orientation observation exists** — a camera at the rendezvous, or a `Detect`
  that returns a full pose between the grippers — the gate should be replaced by a
  requirement that the edge carry such an observation, not simply deleted.
- **If the residual is driven to a multiple of 90°, or below the cam-out bound**, the
  symmetry argument changes and the arithmetic above has to be redone against the actual
  part and the actual commanded width, not assumed to still hold.
- **If a non-cubic work-piece is introduced**, the 90° period disappears and the bound gets
  stricter, not looser.
