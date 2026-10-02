# L1 — Description and assets

- **Status:** `PARTIAL`.
  **Built:** the arm, track, gripper and scene descriptions and the world SDF are generated
  from L0 into `workspace/src/cite_generated/` and load in Gazebo Harmonic — asserted by
  `./scripts/scenario bringup`. Inertial validation is implemented and tested
  (`tools/cite_tools/validate/physical.py`). Three simulation plugins ship in
  `cite_simulation` — the belt, the through-beam and the grasp hold — and the generated world
  instantiates them per asset.
  **Not built:** physically based materials beyond the facility appearance library.
  What this layer holds today, each with its record:
  - **Collision geometry is derived convex hulls**
    ([ADR-0028](../adr/0028-convex-hull-collision-meshes.md), `Accepted`, with its gate's
    clause 2 restated by [ADR-0051](../adr/0051-restate-the-hull-grasp-gate.md)). Thirteen hulls
    of the vendor meshes `external/cite.repos` pins sit under
    `assets/meshes/collision/xarm5/convex_hull/`, produced and checked by `./scripts/hulls`
    and installed by `cite_description`; each carries its source file's digest in
    `assets/manifest.yaml`. Selecting the vendor's meshes is a validator **error**. The
    evidence is bounded to a work-piece no narrower than 50.0 mm, and
    `validate.physical._derived_collision_is_within_its_measured_range` enforces that bound.
    ADR-0028's residuals section lists what promotion did not close.
  - **A hull adds no clearance.** Every gram a hull adds is inside a concavity, so an object
    approaching a link from outside contacts it at the same distance. ADR-0027's sampling
    residual is unaffected, and **hulls may never be cited as margin in a safety case.**
  - **A hull property rests on `<self_collide>` staying `false`**: under hulls the gripper
    linkage interpenetrates at every sampled configuration, so enabling self-collision would
    stall the drive joint at spawn on the simulated side only, a P2 divergence.
    `cite_tools.generate` refuses to emit that combination.
  - **One P2 asymmetry is known and bounded in the description**: the collision root's URI
    scheme is `file://$(find cite_description)` on the simulated backend and
    `package://cite_description` on the hardware one — same package, same meshes, no name
    touched — because the vendor's own visual `mesh_path` branches the same way. Its guard is
    `TestTheRootResolvesTheWayTheVendorsDoes` in `tools/tests/test_collision_binding.py`.
  - **The world is throttled to real time** (`real_time_factor` 1.0,
    [ADR-0043](../adr/0043-hold-both-sides-to-the-wall-clock.md)) so that two sides cannot
    run apart in simulated time. The value is a ceiling and cannot make a slow machine faster;
    the real-time floor on the machine is a separate requirement
    ([ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md)) whose thresholds are
    not set, and nothing in the tree measures it during a run.
- **Asset policy and pipeline:** [`../../assets/README.md`](../../assets/README.md)
- **Related:** [ADR-0003](../adr/0003-gazebo-harmonic.md), [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md), [ADR-0012](../adr/0012-large-asset-storage.md), [ADR-0061](../adr/0061-hold-the-box-while-the-jaws-are-shut.md), [ADR-0065](../adr/0065-the-cell-says-what-it-holds.md), [ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md), [ADR-0043](../adr/0043-hold-both-sides-to-the-wall-clock.md)

## Responsibility

L1 turns the facility model into the concrete geometry, kinematics, dynamics, and
appearance that the simulator and the planner consume: robot descriptions, world files,
meshes and materials. Scanning the CITE building is Phase 3 (charter §8) and is not part of
the main tree.

## Owns

- Robot and component descriptions (URDF/Xacro), generated from L0.
- Simulation world files (SDF), generated from L0.
- Visual meshes, collision geometry, and materials.
- The component library's geometric half: what an xArm 5, its track or a conveyor *looks
  like* and *collides like*.
- The simulation-only plugins in `cite_simulation`: belt, through-beam, grasp hold.

## Does not own

- **Where things are.** Poses come from L0. A description says what a conveyor is, never
  where this conveyor stands.
- Control. `ros2_control` tags in a description are generated from L0's controller plan;
  L2 owns their meaning.
- Raw capture data. Large assets live outside git ([ADR-0012](../adr/0012-large-asset-storage.md)).

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

### The grasp is held by a plugin the cell tells

The jaws close on the part by contact, as on hardware: friction stops the jaws where the part
is, and the drive joint stalls on it. What friction cannot do in the simulator is hold the part
**still** — it rolls between the pads, and the roll worsens as the physics timestep gets finer.
So while the cell says it is holding a part, a Gazebo system plugin
(`cite_simulation/src/grasp_hold.cpp`) fixes the part rigidly to the gripper link, and lets it
go when the cell says it no longer holds it
([ADR-0061](../adr/0061-hold-the-box-while-the-jaws-are-shut.md),
[ADR-0065](../adr/0065-the-cell-says-what-it-holds.md)).

**The plugin decides nothing.** Whether the jaws hold something is decided once, by
`cite_skills::gripper_is_holding` against the facility's declared work-piece interval
([ADR-0052](../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md)); the L3 skill
server publishes that verdict as `RobotState` on `/cite/<zone>/<asset_id>/state`, and the
simulation-only bridge `cite_bringup/grasp_hold_bridge.py` turns each change into an attach
or detach message — the same empty-message shape Gazebo's own `DetachableJoint` takes. The
plugin never touches the drive joint
([ADR-0063](../adr/0063-the-drive-joint-may-not-be-clamped.md)).

**The fidelity cost, stated.** While a part is held it is rigid in the gripper frame: it
cannot slip, rotate against the pads or be dropped by an inadequate clamping force. **No claim
about grasp reliability, slip margin or clamping force may rest on the simulated side.** The
physical arm has no such plugin; its grasp is the real one.

Two consequences belong to this layer specifically.

- **Where the jaws stop is still friction's job and still coupled to the physics timestep.**
  `max_step_size` is a generator constant; any change to it moves the stall position with it
  and must be re-measured, not assumed.
- **The grasp-plane offset** — the pads engaging the part above its centre of mass — is
  corrected by the L3 skill server from the end effector's declared `linkage`, so it is not an
  L1 concern.

The belt and beam plugins are described in
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

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Dense mesh used as collision | Real-time factor collapses; unexplained contact behaviour | `model-validator`, `performance-engineer` |
| Invalid inertia tensor | Arm behaves oddly; looks like a controller bug | `model-validator` |
| Missing collision geometry | Objects pass through each other; planner sees no obstacle | `model-validator` |
| Mesh referenced but not in manifest | Works locally, missing on every other machine | `dependency-auditor`, CI |
| Xacro that expands differently per run | Non-deterministic descriptions | Generator determinism check |

## Open questions

- **Where the boundary sits between generated and authored geometry.** A robot description
  comes from the vendor; a conveyor is ours. The component library needs a clear rule for
  incorporating vendor descriptions without editing them.
- **How far to author materials.** The facility appearance library
  (`cite_generated/materials/appearance.yaml`) colours the bodies; physically based materials
  are not authored.
