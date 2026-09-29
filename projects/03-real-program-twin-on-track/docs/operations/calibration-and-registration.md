# Calibration and registration

- **Status:** `DESIGNED` — Phase 2 (cell registration) and Phase 3 (facility scan registration).
- **Related:** [`../architecture/L5-twin-synchronization.md`](../architecture/L5-twin-synchronization.md), [`../architecture/L1-description-and-assets.md`](../architecture/L1-description-and-assets.md)

## What this is for

Registration establishes the correspondence between the real cell's coordinate frame and
the model's. It is what makes a measurement in the model predict a measurement in the
building.

**Without it, the twin is a nice picture.** A visually convincing scan that is
dimensionally unanchored tells you nothing about the physical world, and every divergence
number computed against it is meaningless.

## The frames

| Frame | Is | Established by |
|---|---|---|
| `cite_world` | The facility root, at the surveyed physical origin | Physical survey |
| Zone frames | Per-zone origins | L0 model, relative to `cite_world` |
| Asset base frames | Where each robot and fixture actually stands | Registration procedure |
| Scanned geometry | The building, as captured | Scan registration |

Everything hangs off `cite_world`, and `cite_world` is a physical place with a physical
marker — not an arbitrary origin someone picked in a CAD file.

## Cell registration — Phase 2

Establishes where each robot base actually is, as opposed to where the model says it is.
Robots are mounted by people; the difference is never zero.

1. **Survey the reference.** Identify the physical origin marker. Record it — a photograph
   and a written description, in `assets/manifest.yaml` for anything scanned.
2. **Measure each robot base** relative to that marker, with a method whose accuracy you
   know.
3. **Touch off known points.** Command the arm to a known physical feature at reduced
   speed, with a human at the stop. Record commanded pose against measured actual pose.
4. **Compute the transform** between model and physical for each asset.
5. **Record it** in the L0 model as the asset's registered pose, not as a runtime offset.
   A runtime correction is invisible; a model value is reviewable.
6. **Verify** with a point not used in the computation. Fitting to your own calibration
   points proves nothing.

**Expect:** residual error within the accuracy of your measurement method.
**If not:** the model is wrong, the measurement is wrong, or the robot is not where anyone
thinks it is. Do not proceed by absorbing the error into an offset.

## Scan registration — Phase 3

Ties scanned building geometry to the same frame.

1. **Place survey targets** before capture, at known positions relative to `cite_world`.
   Retrofitting registration to a scan captured without targets is far harder and less
   accurate.
2. **Capture** with the targets visible.
3. **Register** the point cloud to `cite_world` using them.
4. **Verify** by measuring a distance in the model and the same distance in the building.
5. **Record** the survey reference in the asset's `manifest.yaml` entry.

**Expect:** a measurement in the model matches the building within the scan's stated
accuracy.
**If not:** the scan is decoration. Re-register or re-capture — do not ship it and hope.

## Re-verification

**Registration is not permanent.** Floors settle. Fixtures get bumped. Robots get
remounted after maintenance. Nobody announces any of this.

Re-verify:

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
| Error absorbed into a runtime offset | Invisible correction; the model stays wrong | Record in the L0 model |
| Scan captured without targets | Registration is guesswork | Place targets before capture |
| Survey reference undocumented | Nobody can reproduce or check it | Record it in `manifest.yaml` at capture time |
