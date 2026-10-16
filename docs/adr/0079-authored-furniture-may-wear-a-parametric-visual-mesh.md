# ADR-0079: Authored furniture may wear a parametric visual mesh

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Project owner (decision of 2026-10-16: "make the belt we have look industrial,
  as far as it goes")
- **Related:** [ADR-0012](0012-large-asset-storage.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md), CLAUDE.md §3 (P1), §10 (inertia and collision
  geometry)

## Context

The cell's furniture renders in Gazebo as plain coloured boxes. The project owner finds that
unrealistic and asked first for the transfer belt (`belt_1200x400`) to look like an industrial
conveyor.

Some facts are fixed:

- **No usable ready model exists.** Gazebo Fuel has only Open-RMF's `conveyor_block`, which has
  the wrong proportions. The lab's real belt, a QCON-24 (a 24 V BLDC belt conveyor), has no
  public CAD.
- **The schema can already express it.** `Body.visual` and `Body.collision` are separate
  fields, `MeshGeometry` is in the schema, and the scene generator emits `<mesh>`.
- **The belt's behaviour depends on the collision box.** That covers the planning scene, the
  geometric and physical validators, the inertia, and the conveyor world plugin's footprint.
  None of these may change for a cosmetic reason.
- **The layout is `PROVISIONAL`**, engineered and not surveyed.

## Options considered

### Option A: a hand-modelled mesh (Blender or similar)
It would look best per hour spent by an artist. It was not chosen because it would be a second
statement of the belt's dimensions, which can drift from the L0 type (P1). Nothing could check
it against the model, and nobody on the project maintains a modelling tool chain.

### Option B: a primitive-only body with more boxes
`Body` holds one visual primitive, so this would mean a schema change for multi-part bodies,
which every generator and validator would then have to reason about. That costs far more than
the appearance it buys.

### Option C: a parametric mesh generated from the L0 type (chosen)
A committed script reads the type's collision box and draws the conveyor inside it. The output
is committed and checked byte for byte against a fresh generation, the same pattern the derived
collision hulls use (ADR-0028).

## Decision

An authored body may declare a **visual-only** mesh that a committed, deterministic generator
under `tools/cite_tools/visuals/` derives from that body's own collision box.
`python -m cite_tools.visuals` checks every such mesh and `--write` regenerates them. The
directory under `assets/meshes/visual/` that the URI names selects the drawer: `conveyors/` for
`belt_1200x400` and `tables/` for `work_table_600`. The collision, inertia, frames and plugins
stay the primitives the model declares.

1. **Envelope.** The mesh lies inside the collision box, with its origin at the box centre,
   which is where the scene template places a body's visual. Its top face is the box top, so
   the drawn surface is the one the type's `surface` frame names, and nothing rises above it.
2. **Format.** The mesh is a GLB with PBR finishes, which Gazebo Harmonic renders through
   assimp. Every finish is non-metallic: with no environment map to reflect, a PBR metal renders
   near black in Gazebo. A body wearing it declares no `material`, because a URDF material
   would override every finish in the mesh.
3. **URI.** The URI is `file://$(find cite_description)/meshes/...`, the absolute `file://` form
   the xArm meshes already use under Gazebo. The scene is expanded by xacro at launch, so no
   `GZ_SIM_RESOURCE_PATH` is involved. `cite_description` remains the only package that installs
   `assets/meshes` (ADR-0012), and the generated `package.xml` derives the dependency from the
   URI.
4. **Not survey.** The proportions are plausible appearance, not the lab's QCON-24, and the
   layout stays `PROVISIONAL`.

## Consequences

### What this gets us
- The belt reads as a conveyor, with frames, belt, drums, legs, drive and control box, and the
  work tables read as wooden benches on orange steel legs.
- Its envelope is still stated once, in L0.
- A stale or hand-edited mesh is caught by `tools/tests/test_visual_meshes.py`.

### What this costs us
- Binary files in git (the conveyor's is about 190 KB). Regenerating it is a second command, beside
  `./scripts/validate-model --write`, that a contributor has to know about. The test catches a
  forgotten run.
- The visual now shows air under the belt that the collision box still fills. The planner
  remains conservative, as before, but the picture no longer shows that.
- The material-library tests now accept a visual with no material when that visual is a mesh.
  A future mesh without its own finishes would render untextured with nothing flagging it.
- RViz renders GLB only if its assimp build accepts it. That is not verified here.

### What we will have to revisit
- When the Phase 3 scan produces surveyed geometry, it replaces this mesh.
- A drawer is chosen by directory name. If the furniture outgrows that, the choice belongs in L0.

## Addendum 2026-10-16: the track stands on a long pick table

The owner reported a fact about the lab: the linear track and the whole robot stand on the table
the part is picked from, and that table runs from its corner farthest from the belt to a little
past the end of the track. The model had drawn the track as a 0.705 m box on the floor beside a
0.6 m table. It now states the lab's arrangement:

- `infeed_table` is a `work_table_1450x800`, footprint x -0.800..0.650 and y 2.624..3.424 in
  `cite_world`, 60 mm clear of the belt. Its `surface` frame is off-centre, so the pick point
  stays at (-0.500, 2.924, 0.600).
- `picker_track`'s body is the rail alone, 1.000 × 0.110 × 0.105 m. It is placed on
  `infeed_table/surface`, so its foot is at (0.050, 3.300, 0.600). Its carriage frame is 0.110 m
  above that foot, so the carriage and the arm keep the world pose they had.
- Both wear generated meshes. A third drawer, `tracks/`, draws the rail. The table drawer adds a
  middle pair of legs when a side is longer than 1.2 m.

No world pose the program uses moved. The arm descriptions, the static frames, the world and
the bring-up plan regenerate byte-identical. Only the two bodies change, in the scene and in the
planning scene. The layout stays `PROVISIONAL`.
