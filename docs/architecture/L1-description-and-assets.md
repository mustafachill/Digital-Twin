# L1 — Description and assets

- **Status:** `PARTIAL`.
  **Built:** robot descriptions and the world SDF are generated from L0 into
  `workspace/src/cite_generated/` and load in Gazebo Harmonic — asserted by
  `./scripts/scenario bringup`. Inertial validation is implemented and tested
  (`tools/cite_tools/validate/physical.py`). Two simulation fidelity aids ship as Gazebo
  system plugins in `cite_simulation` — the belt and the through-beam — and the generated
  world instantiates one per asset. The beam intersects a segment with the part's **collision
  body**, and an indexing beam's along-belt mounting is **derived from the part** rather than
  authored ([ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md)); five
  rules in `cite_tools.validate.geometric` refuse the model shapes that would break it.
  **Not built:** no first-party *materials* exist and the scan pipeline is Phase 3.
  **Changed 2026-08-31:** `assets/` no longer holds only its README and manifest. Thirteen
  **derived** collision meshes are committed under `assets/meshes/collision/xarm5/convex_hull/`
  — convex hulls of the vendor meshes `external/cite.repos` pins, produced by
  `cite-model hulls` and installed by the new `cite_description` package. They are *derived*
  rather than authored, so the source of each shape is still the vendor file; each carries
  the digest of that file in `assets/manifest.yaml`, and `cite-model hulls` re-derives and
  compares rather than trusting them.
  **Removed:** the contact-triggered grasp attachment plugin, per
  [ADR-0029](../adr/0029-simulated-grasping-by-friction.md). No `<plugin>` element in any
  generated arm description assists a grasp; see "Grasping is not simulated" below.
  **Violated:** this layer's own first rule, below. Twelve links per arm collide against
  their *visual* mesh, and the validator written to catch that cannot fire on a vendor
  description. See [ADR-0028](../adr/0028-convex-hull-collision-meshes.md), which is
  `Proposed`: the hulls exist and are selectable by one L0 field, and the shipped selection is
  still `vendor_meshes` because its promotion gate is unmet. **Clause 2 of that gate cannot be
  met as written** — the campaign it demanded measured the predicted mechanism not to occur —
  and it is restated by [ADR-0051](../adr/0051-restate-the-hull-grasp-gate.md), which is also
  `Proposed`. The section "Visual and collision geometry are always separate" below states the
  rule, not the current state.
  **Changed 2026-08-29:** the generated world declares `real_time_factor` **1.0** rather than
  `0`. `0` is Gazebo's unthrottled value and overrode SDFormat's own default; the new value
  is a **ceiling**, so on a machine already below real time it changes nothing and cannot
  make a slow one faster. Two free-running sides cannot agree about what time it is, and a
  clock deficit accumulates without bound while a transport latency does not
  ([ADR-0043](../adr/0043-hold-both-sides-to-the-wall-clock.md)). The other half of that
  decision is a real-time floor on the machine, answered by measurement, and **nothing in the
  tree measures it**; do not read the generated value as that guarantee. **Its original wording
  — both sides *sustain* a measured 1.0 concurrently — is not the requirement**: under this
  generated throttle a measured real-time factor is capped at the declared factor by
  construction, so it was restated on 2026-08-31 by
  [ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md) as a capacity floor
  measured with the throttle **lifted**, plus a bound on the accumulated clock deficit measured
  with it in force. Neither of that record's thresholds is set, so the floor is **not met** in
  either shape; the paired figure measured by hand once on 2026-08-30 is in ADR-0043's
  correction of that date, and being throttled it is not a capacity number.
  `max_step_size` is untouched.
- **Asset policy and pipeline:** [`../../assets/README.md`](../../assets/README.md)
- **Related:** [ADR-0003](../adr/0003-gazebo-harmonic.md), [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md), [ADR-0012](../adr/0012-large-asset-storage.md), [ADR-0029](../adr/0029-simulated-grasping-by-friction.md), [ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md), [ADR-0043](../adr/0043-hold-both-sides-to-the-wall-clock.md)

## Responsibility

L1 turns the facility model into the concrete geometry, kinematics, dynamics, and
appearance that the simulator and the planner consume: robot descriptions, world files,
meshes, materials, and the scanned geometry of the CITE building.

## Owns

- Robot and component descriptions (URDF/Xacro), generated from L0.
- Simulation world files (SDF), generated from L0.
- Visual meshes, collision geometry, and materials.
- The 3D scan pipeline: capture → registration → cleanup → decimation → visual/collision
  split → materials → simulator assets.
- The component library's geometric half: what an xArm 5 or a conveyor *looks like* and
  *collides like*.

## Does not own

- **Where things are.** Poses come from L0. A description says what a conveyor is, never
  where this conveyor stands.
- Control. `ros2_control` tags in a description are generated from L0's controller plan;
  L2 owns their meaning.
- Raw scan data. That lives outside git ([ADR-0012](../adr/0012-large-asset-storage.md)).

## Interfaces

**Consumes:** generated artifacts from L0; meshes fetched per `assets/manifest.yaml`.

**Exposes:** `robot_description` parameters, SDF worlds loadable by Gazebo Harmonic,
collision geometry for the MoveIt planning scene, and TF frames per
[naming-and-namespaces.md](naming-and-namespaces.md).

## Design

### Visual and collision geometry are always separate

This is the single most consequential rule in this layer.

| | Visual | Collision |
|---|---|---|
| Purpose | Look right | Contact and planning |
| Complexity | May be dense | Primitives or convex hulls |
| Source | Decimated scan or CAD | Simplified by hand or by hull generation |

Reusing a dense visual mesh as collision geometry is the most reliable way to destroy
Gazebo's real-time factor and to produce contact behaviour nobody can explain. It presents
as "the simulation got slow" or "the arm jitters", and the cause is never where people
look. `model-validator` rejects it.

### Grasping is not simulated

There is no simulation-side grasp mechanism, and that is a decision rather than an
omission. A work-piece is held by contact friction between the pads and the part, exactly
as on hardware; L1 contributes the surface properties and the geometry and nothing else.

This layer used to carry a Gazebo system plugin that welded a work-piece to a finger with a
`DetachableJoint` on contact. It is removed.
[ADR-0029](../adr/0029-simulated-grasping-by-friction.md) is the decision and
[`../measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md)
is the evidence; the numbers live there and are deliberately not copied here (P1).

Two consequences belong to this layer specifically.

- **Grasp quality is coupled to the physics timestep**, in the unhelpful direction: a finer
  timestep makes the grasp worse. `max_step_size` is a generator constant, so any change to
  it — and both [ADR-0028](../adr/0028-convex-hull-collision-meshes.md) and Phase 3 point at
  retuning physics for real-time factor — moves grasp quality with it and must be
  **re-measured, not assumed**.
- **The part rolls between the jaws, about the pad-to-pad axis.** The cause of the large
  rotations is a grasp-plane offset — the pads engage the part above its centre of mass,
  which is a couple — measured in
  [`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md).
  **The correction is now in the tree**, applied by the L3 skill server from the end
  effector's declared `linkage`, so it is no longer an L1 concern. A residual rotation
  survives it and is an open sim/real divergence for Phase 2. **Name the axis whenever you
  quote the residual**: it is a roll between the pads, not a yaw about the tool axis, and the
  two do not cost the same thing — see that campaign's re-analysis note and
  [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md)'s
  correction, where the figure had been put into a calculation only a yaw can enter.

The belt and beam plugins that remain are described in
[`cite_simulation`'s README](../../workspace/src/cite_simulation/README.md), including what
they flatter us about.

### Inertial properties are validated, not trusted

Wrong inertia does not raise an error. The simulation runs, and the physics is wrong in
ways that read as a controller bug. Every link is checked for:

- Positive, physically plausible mass for its size and material.
- A symmetric, positive-definite inertia tensor.
- Principal moments satisfying the triangle inequality — each no greater than the sum of
  the other two. A tensor failing this describes an impossible object and will make the
  solver misbehave.
- A centre of mass inside the link's geometry.
- No placeholder inertia copy-pasted across links of different size.

### The scan pipeline

```
capture  →  register  →  clean  →  decimate  →  split  →  material  →  SDF
 Drive       work/       work/      work/      meshes/    meshes/     model/
```

Registration is the step that matters most: scanned geometry must land in the same
coordinate frame as the engineered assets, tied to a surveyed reference. Without it the
scan is decoration — visually convincing, dimensionally meaningless, and useless for a
twin whose whole claim is that measurements transfer.

Every capture records its survey reference in `assets/manifest.yaml`.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Dense mesh used as collision | Real-time factor collapses; unexplained contact behaviour | `model-validator`, `performance-engineer` |
| Invalid inertia tensor | Arm behaves oddly; looks like a controller bug | `model-validator` |
| Missing collision geometry | Objects pass through each other; planner sees no obstacle | `model-validator` |
| Scan not registered | Model looks right, measurements are wrong | L5 registration check against survey |
| Mesh referenced but not in manifest | Works locally, missing on every other machine | `dependency-auditor`, CI |
| Xacro that expands differently per run | Non-deterministic descriptions | Generator determinism check |

## Open questions

- **Level of detail for the facility scan.** A whole building at full visual fidelity will
  not run. Whether to use LOD switching, region-based loading, or simply aggressive global
  decimation is a Phase 3 decision that needs real capture data to settle.
- **Where the boundary sits between generated and authored geometry.** A robot description
  comes from the vendor; a conveyor is ours. The component library needs a clear rule for
  incorporating vendor descriptions without editing them.
- **Whether materials are worth authoring before Phase 3.** Probably not, but the
  generated SDF should reference them from the start so that adding them is not a schema
  change.
