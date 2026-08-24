# L1 — Description and assets

- **Status:** `DESIGNED` — no descriptions or meshes exist yet. Asset policy and pipeline are defined in [`../../assets/README.md`](../../assets/README.md).
- **Related:** [ADR-0003](../adr/0003-gazebo-harmonic.md), [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md), [ADR-0012](../adr/0012-large-asset-storage.md)

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
