# Calibration and registration

- **Status:** `DESIGNED` — Phase 2 (cell registration, charter §8). No procedure here has been
  run, and nothing in the tree computes or applies a registration. What exists is the place L0
  keeps one: every asset instance carries a `registration` block
  (`model/schema/asset_instances.schema.json`), and `cell_b`'s arm declares
  `status: unregistered` (`model/assets/instances/arms.yaml`). Registering scanned building
  geometry is Phase 3 (charter §8) and is not described here.
- **Related:** [`../architecture/L5-twin-synchronization.md`](../architecture/L5-twin-synchronization.md), [`../architecture/L0-facility-model.md`](../architecture/L0-facility-model.md), [`safety-procedures.md`](safety-procedures.md)

## What this is for

Registration establishes the correspondence between the real cell's coordinate frame and
the model's. It is what makes a measurement in the model predict a measurement in the cell.

**Without it, the twin is a nice picture.** A model that is dimensionally unanchored to the
physical cell tells you nothing about the physical world, and every divergence number
computed against it is meaningless.

## The frames

| Frame | Is | Established by |
|---|---|---|
| `cite_world` | The facility root, at the surveyed physical origin | Physical survey |
| Zone frames | Per-zone origins | L0 model, relative to `cite_world` |
| Asset base frames | Where each robot and fixture actually stands | The procedure below |

Everything hangs off `cite_world`, and `cite_world` is a physical place with a physical
marker — not an arbitrary origin someone picked in a CAD file.

## Cell registration — Phase 2

Establishes where each robot base actually is, as opposed to where the model says it is.
Robots are mounted by people; the difference is never zero.

1. **Survey the reference.** Identify the physical origin marker. Record it — a photograph
   and a written description — and name it in the asset's `registration.survey_reference`.
2. **Measure each robot base** relative to that marker, with a method whose accuracy you
   know.
3. **Touch off known points.** Command the arm to a known physical feature at reduced
   speed, with a human at the stop ([`safety-procedures.md`](safety-procedures.md)). Record
   commanded pose against measured actual pose.
4. **Compute the transform** between model and physical for each asset.
5. **Record it in the L0 model**, in the asset's `registration` block and never in `pose`:
   `correction` is a body-frame delta (ADR-0020), with `status: measured`, the `method`,
   `measured_at` and `residual_rms_m`. Keeping it apart from `pose` means a measurement can
   never overwrite engineered intent, and `git diff` shows exactly what registration changed.
   **Never as a runtime offset**: a runtime correction is invisible; a model value is
   reviewable.
6. **Verify** with a point not used in the computation. Fitting to your own calibration
   points proves nothing.

**Expect:** residual error within the accuracy of your measurement method.
**If not:** the model is wrong, the measurement is wrong, or the robot is not where anyone
thinks it is. Do not proceed by absorbing the error into an offset.

## Detecting drift

**Registration is not permanent.** Floors settle. Fixtures get bumped. Robots get
remounted after maintenance. Nobody announces any of this.

Re-verify, and mark the block `status: stale` until you have:

- After any physical change to the cell.
- After maintenance on any robot mount.
- When twin divergence trends upward with no software change.
- On a schedule — at least each semester.

That third trigger is the reason L5 publishes divergence continuously. **A drifting
registration presents as slowly growing divergence with no software cause**, and it is one
of the harder faults to find without the metric. With the metric it is nearly obvious.

## Failure modes

| Failure | How it shows | What to do |
|---|---|---|
| Never registered | Model looks right, measurements are wrong | Register before claiming any fidelity |
| Registered once, never re-verified | Divergence grows over months | Scheduled re-verification |
| Verified against its own fit points | Residual looks excellent, reality does not agree | Always verify on a held-out point |
| Error absorbed into a runtime offset | Invisible correction; the model stays wrong | Record it in the L0 `registration` block |
| Survey reference undocumented | Nobody can reproduce or check it | Record it in `survey_reference` at measurement time |
