# ADR-0030: Describe the work-piece in the facility model, as an asset type with no instances

- **Status:** Accepted — and, unusually for this repository, recorded **after** the change
  landed rather than before it. CLAUDE.md §12 requires the ADR first; this one was written
  during the documentation pass that followed commit `b2be77f`, because the decision was
  significant, was made, and existed nowhere but a commit message. That is the defect this
  file closes, and naming it is cheaper than pretending the order was right (P7).
- **Date:** 2026-08-26
- **Deciders:** Project owner
- **Related:** [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0020](0020-facility-model-conventions.md),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [L0](../architecture/L0-facility-model.md)

## Context

L0 held out against describing work-pieces on purpose, and the reason was a good one:
`Facility.workpiece_models` carried names and nothing else, because a work-piece with
attributes nobody reads is invented schema (P5). [L0](../architecture/L0-facility-model.md)
recorded that position, and its open-questions section asked whether the model should
describe products at all.

Two independent rules then turned out to need the same missing fact.

**One.** `./scripts/scenario pick_and_place` failed 0 of 18, deterministically. The belt
type declared its `infeed` and `outfeed` frames at ±0.600 m — exactly the leading and
trailing planes of its own collision box. A 50 mm cube released there has its centre of
mass projecting onto the *boundary* of its support polygon: neutrally stable. It tipped
about the edge and fell 0.600 m to the floor, landing at z = 0.025 with a 90-degree pitch,
while every layer above reported success, because the release itself succeeded.

The existing geometric rule, `frame-outside-geometry`, asks whether a frame lies outside
its body and uses strict comparisons, so a frame exactly on a boundary face passes it. The
rule that would have caught this asks a different question — *how much of a body does a
part cover, and how far from the edge must a place point therefore sit* — and that question
cannot be posed at all without the part's extents. `work_table_600.surface` never showed
the defect because it sits at the **centre** of its top face: same generator, opposite
support margin, and nothing anywhere expressed the difference as a rule.

**Two.** The grasp-width ceiling in `tools/cite_tools/validate/physical.py` had been
deliberately loosened from 60.92 mm to 88.93 mm when [ADR-0029](0029-simulated-grasping-by-friction.md)
removed the attachment plugin, because the tighter bound depended on the plugin's arming
angle. 88.93 mm is only the gripper's own widest opening. The bound that actually matters
under a friction grasp is "narrower than the part", and the docstring said in as many words
that it could not enforce that while L0 recorded no work-piece geometry.

Two consumers, one datum. That is what makes it a fact the model owes rather than a field
added for symmetry.

## Options considered

### Option A — Leave L0 as it is; put the numbers in the validator
Hard-code a 50 mm reference part inside `cite_tools.validate`. Cheapest, and it makes both
rules expressible immediately.

Rejected on P1 and P5. The part's size would then exist in the validator and, separately,
in whatever spawns a part in a scenario — a value in two places, one of them code that is
supposed to encode *how* things are checked and not *which* things exist.

### Option B — A new top-level document kind, `model/workpieces/`
Work-pieces are not equipment, so give them their own schema and their own directory.

Rejected as a second `Body` to keep in step. A work-piece needs exactly what every other
authored object needs — extents, mass, a centroidal inertia tensor — and `Body` already
says all of it and is already checked by `cite_tools.validate.physical`. A parallel
declaration would duplicate that schema and drift from it.

### Option C — An asset *type* with no instances. Chosen.
`model/assets/types/workpieces/workpiece.yaml`, category `workpiece`, described by the same
`Body` provider the belts, pedestals, tables and beams already use.

## Decision

**The facility model describes the cell's reference work-piece as an asset type, and
declares no instances of it.** The category exists precisely so that the distinction can be
made: the layout describes what is bolted down, and where a part is at any moment is the
process's business. Nothing generated places one.

**Its `id` is also the spawned Gazebo model name.** `Facility.workpiece_models` reaches the
generated world as the belt plugin's `<carry>` list and the break beam's `<watch>` list,
both of which match on the model name, so the two strings have to be one string and are.

**Two validation rules are derived from it, not declared beside it:**

- `insufficient-support-margin` (geometric) requires a place point to stand at least half
  the work-piece footprint plus `SUPPORT_CLEARANCE_M` = 20 mm from the edge of whatever
  supports it — 45.0 mm for the 50 mm cube. It fired against the committed defect with five
  errors naming `infeed` and `outfeed`, and does not report the centred table surface.
- `default-grasp-width-never-closes` (physical) re-tightens the ceiling to the narrowest
  work-piece less twice the controller's `goal_tolerance` in width: 50.00 − 2.14 =
  **47.86 mm**, strictly tighter than either predecessor. The subtracted term is not
  padding; `GripperActionController` ends a goal as soon as `|error| < goal_tolerance`, so
  a default inside that band produces real grasps L3 cannot distinguish from closing on air.

**The design stays authored; the validator derives and enforces the floor.** The belt's
transfer frames moved 50 mm inboard by hand, and the arm-to-belt standoff moved 0.350 →
0.300 m to pay for the reach that costs. Deriving a frame position from facility-level part
data would move every transfer point and every arm's reach the day someone adds a part.

## Consequences

### What this gets us
- A defect class that was invisible to the model is now mechanically rejected, and rejected
  at the type where the fault lives rather than at each of the three belts that inherit it.
- The grasp-width bound the project has wanted since ADR-0022 is enforceable and enforced.
- The part's extents, mass and inertia are written once, in the layer whose job is to say
  what physically exists.
- L0's long-standing open question — equipment only, or products too? — has an answer with
  a reason attached, instead of remaining open by default.

### What this costs us
- **L0's scope is wider than it was**, and the argument that kept work-pieces out was
  sound. The guard against re-inventing schema is now the two-consumer test in this ADR and
  nothing stronger: a future field with one reader does not clear it.
- **`default_grasp_width_m` is now provably in the wrong place.** It is a property of an
  end-effector *paired with* a work-piece and it sits on the end-effector type. With one
  part size that is a single source of truth; with two, it is a value that has to move.
- **The friction-grasp campaign released onto the defective frame and misread the result.**
  `docs/measurements/2026-08-25-friction-grasp/` placed at `cell_a__conveyor_1__infeed`,
  which was then at the belt's leading-edge plane, and 22 of its 84 trials ended with the
  part on the floor at z = 0.025. Its `recompute.py` attributed that to "the conveyor
  carrying a correctly placed part off its far end". The saved pose samples say otherwise:
  the part leaves belt height at x ≈ 0.40 and never exceeds x ≈ 0.45, the release point at
  the **near** end, so it tipped where it was set down rather than travelling 1.2 m to the
  far end. The campaign's conclusions are about the carry window and are unaffected, and
  both of its re-definitions remain the right ones; the *explanation* attached to them is
  wrong and is corrected in `results.md`. A defect can sit inside a published campaign
  without invalidating it, and can still make the campaign's prose false (P7).
- The 20 mm support clearance is a designed margin, not a measured one. Four probe cubes
  bound the *physical* requirement between 0 and 25 mm of inset; 20 mm on top of the
  half-footprint is engineering headroom above that, chosen and not derived.

### What we will have to revisit
- **The day a second work-piece size exists.** `default_grasp_width_m` moves to the
  work-piece and travels on `Pick.Goal`; the end-effector type keeps only the stroke. The
  support-margin rule already reads the narrowest part and needs no change.
- **A non-box work-piece.** Both rules read a footprint from box extents. A meshed part
  makes `_narrowest_workpiece_width_m` return `None` and both rules fall silent — the safe
  direction, but silence, and it would need a hull or a declared bounding footprint.
- **If a part is ever placed by the model rather than by the process** — a fixture holding a
  blank at a known pose, say — the "type with no instances" rule breaks and the category
  needs instances, which is a schema change and not a reinterpretation.
