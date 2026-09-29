# ADR-0033: Sense against the part's body, and derive an indexing beam's stand-off from it

- **Status:** Accepted. Recorded **after** the change landed rather than before, which
  charter §12 requires and this did not get: the decision existed only in the messages of
  commits `c5c8784` and `b430a12` until this record was written in the documentation pass
  that followed them. Stated rather than smoothed over (P7), and it is the third record on
  this branch to have to say it — see
  [ADR-0030](0030-facility-model-describes-the-workpiece.md) and
  [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md).
- **Date:** 2026-08-26
- **Deciders:** Project owner
- **Related:** [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0020](0020-facility-model-conventions.md),
  [ADR-0030](0030-facility-model-describes-the-workpiece.md) (which put the work-piece in
  L0 and so made this expressible),
  [ADR-0032](0032-index-the-belt.md) (whose corrected consequence this repairs),
  [L0](../architecture/L0-facility-model.md),
  [L1](../architecture/L1-description-and-assets.md), charter §4 (P1, P2, P5)

## Context

[ADR-0032](0032-index-the-belt.md) stops a belt on a beam's edge and leaves the part
standing where a station picks from. That makes the beam's report a **position**, not just
an occupancy, and a position is only as good as what the sensor tests.

**The plugin tested the work-piece's model origin against a box.** That is a part-centre
window rather than a light beam, and it was wrong in two directions, both measured:

- **Across the beam**, the test admitted only parts whose *centre* fell inside the box. With
  the then-current 0.040 m width and a 0.030 m mounting height, a part taller than 100 mm or
  shorter than 20 mm was detected on hardware and missed here.
- **Along the belt**, it reported a 50 mm cube about 25 mm *after* its leading edge arrived.
  With the belt indexed on that edge, every piece parked short of the grasp.

These had been recorded as two defects. They are one.

**Two fixed constraints frame what could be done about it.**

1. A real through beam breaks on a **leading edge** and stays broken until the trailing edge
   is past, at any height the part reaches. Anything that diverges from that diverges
   simulation from hardware, which is the P2 boundary and the highest-severity defect class
   here.
2. The 0.040 m beam width was **anti-tunnelling inflation for the point test**, not a
   measurement: it existed so a part could not step across the beam between two physics
   frames. Half of it therefore had no physical meaning, and any geometry derived from it
   would inherit a simulator artefact.

The second constraint is what makes this a decision rather than a bug fix. Correcting the
extents test does **not** fix where the part parks — a leading-edge break stops the part
*earlier*, so at the old authored mounting the shortfall would have **grown**, from about
0.069 m to about 0.077 m. Getting the physics right created the need to decide where an
indexing beam is mounted; it did not remove it.

## Options considered

### Option A — Slide the beam until the scenario passes
Keep the authored along-belt offset in `model/assets/instances/sensors.yaml` and fit it to
whatever leaves the part under the gripper.

Rejected, and this had already been refused twice before on this branch. The number that
would come out is a fit against the simulator's behaviour, not a statement about the cell.
With the old point test, roughly half the beam width would have been baked into L0 geometry,
so the physical cell — where a real photo-eye breaks on the leading edge — would park its
parts about 20 mm elsewhere. Tuning L0 geometry to a simulator artefact is exactly what P2
exists to forbid, and a fitted constant is indistinguishable from a derived one once it is
sitting in a YAML file.

### Option B — Declare the part's length to the plugin
Pass `workpiece_length_m` into the `<plugin>` element so the beam can compute a leading edge.

Rejected on P1. The work-piece's geometry is already declared once, in L0, since
[ADR-0030](0030-facility-model-describes-the-workpiece.md). A second copy in the world file
is a second place to be wrong, and it would decouple the sensor from the model: a part whose
size changed in L0 would go on being sensed as the old one.

### Option C — Author the stand-off, but compute it by hand and comment the arithmetic
Leave the value in `sensors.yaml`, with the derivation written above it as a comment.

Rejected because a comment is not a mechanism (P5). The number still has to be recomputed by
a human whenever the part changes, nothing fails when they forget, and no validator can tell
a stale hand-computed value from a current one.

### Option D — Intersect the beam with the part's body, and derive the mounting. Chosen.

## Decision

**Two things, and they only work together.**

1. **The beam is a segment tested against the collision shapes the simulator holds** for the
   part, measured in the part's own axes. No work-piece dimension is declared to the plugin
   or passed into it, so a part whose size changes in L0 changes what the beam sees with
   nothing to keep in step.
2. **An indexing beam's along-belt stand-off is derived, not authored.** A beam declared
   `indexes_workpiece: true` is mounted with its upstream face on the leading-edge plane of a
   correctly parked part: half a part length plus half a beam width downstream of the frame
   the part must stop on. The derivation lives in the resolver
   (`cite_tools.model.resolve.index_offset_m`), so the housing's description, the static TF
   frame, the planning-scene object and the plugin all move together rather than describing
   different places.

`sensors.yaml` therefore carries a **zero** along-belt component for an indexing beam — the
frame it is mounted against *is* the point the part must stop on — and the geometric
validator refuses a non-zero one. Half a beam width entering the derivation is also why
`beam_width_m` is now a real 4 mm lensed aperture rather than the 40 mm inflation.

**This is how a photo-eye is actually set on an indexing line**, which is the point: the
sim and the hardware paths are set by the same rule.

## Consequences

### What this gets us
- **The part parks where the model says it parks.** For `beam_c1_out` the beam frame moves
  from x = 1.550 to x = 1.627 — `conveyor_1/outfeed` at 1.600 plus a derived 0.027 m — so a
  part whose leading edge breaks the beam comes to rest with its centre on the outfeed frame.
- **The fitted constant cannot come back.** `beam-indexes-off-frame` rejects an authored
  along-belt offset on an indexing beam outright.
- **A class of defect that used to need a four-run scenario now fails in a second.** Five
  rules in `cite_tools.validate.geometric` cover index geometry: `beam-indexes-off-frame`,
  `beam-indexes-no-pick-point`, `beam-off-its-belt`, `beam-cannot-index`, and
  `beam-cannot-see-workpiece` for the height face.
- **The anti-tunnelling margin went up when the inflation came out**, because the occlusion
  window is now the part's own length rather than the beam's width. The schema states the
  arithmetic and it is not restated here (P1).

### What this costs us
- **The index position now depends on the part's yaw, and that is real rather than an
  artefact.** A leading-edge test is a test on a leading *extent*: a 50 mm square yawed by θ
  presents a leading half-extent of 25·(cos θ + sin θ), so a yawed part breaks the beam
  earlier and parks short. At the largest arrival yaw the conveyor-yaw campaign measured, the
  shortfall is about 4.2 mm. The figure and the campaign are in
  [`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
  and are not restated here (P1). **A physical photo-eye behaves the same way**, so this must
  not be compensated in the beam; it belongs to the release-orientation residual. That
  campaign lists whether the residual accumulates over three stations as **explicitly not
  measured**.
- **The derivation uses the longest work-piece the facility declares.** With one part type it
  is exact. A facility declaring several would park the longest on its point and the shorter
  ones downstream of it, by half the difference in length. Nothing warns about that today.
- **The beam now depends on the simulator holding collision geometry for the part.** A part
  present only as a visual, or spawned without collision shapes, is invisible to the beam
  where the origin test would have seen it. This is closer to hardware, not further from it,
  but it is a new way for a rig to produce nothing.
- **One real bound remains and holds identically on hardware:** a beam mounted 0.030 m above
  the belt cannot see a part shorter than about 30 mm, because the part passes under it.
  `beam-cannot-see-workpiece` rejects that pairing in the model. There is no upper bound.
- **Nothing measures the parked position as a published campaign.** That the line now
  completes is reported from runs, not from a campaign with pre-registered thresholds — see
  the status block in [CLAUDE.md §2](../../CLAUDE.md).

### What we will have to revisit
- **If the facility handles more than one work-piece length**, the "longest part" rule stops
  being exact and the stand-off has to become per-part or per-station. That is the point to
  reopen this, and it should be a validator rule before it is a decision.
- **If a part is ever fed at a controlled yaw** rather than square, the leading-extent
  sensitivity above stops being a residual and becomes a systematic offset that the model
  could account for.
- **If a beam is ever mounted on something other than a belt** — an indexing rotary table,
  a lift — the derivation's assumption that the parent's local +x is the direction of travel
  has to be re-examined.
