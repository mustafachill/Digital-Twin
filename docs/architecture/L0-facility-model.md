# L0 — Facility model

- **Status:** `BUILT` — `model/` describes **one zone, `cell_b`, paired**: one xArm 5 on a
  linear track, one belt, one pick table, and the real robot's program
  (`model/programs/xarm5_real_demo.blockly.xml`). The generators in
  `tools/cite_tools/generate/` emit every artifact in the table below except the last two.
  `./scripts/validate-model` runs all five validation levels, diffs the committed
  `cite_generated/` against a fresh generator run, and regenerates in a second interpreter
  under a different hash seed to prove the output byte-identical. **Ask that command for the
  model's cardinality; do not read a count out of prose.**
  **Not produced:** registration reference data for L5 and scene topology for a display — the
  two rows whose consumers do not exist.
  What L0 decides, beyond layout:
  - **The work-piece** ([ADR-0030](../adr/0030-facility-model-describes-the-workpiece.md)):
    `model/assets/types/workpieces/workpiece.yaml` gives the reference part's extents, mass
    and inertia, so the validator enforces that the default grasp width is narrower than the
    narrowest part less the discrimination margin, and the support-margin rule. The type has
    **no instances**, deliberately — where a part is at any moment is the process's business,
    not the layout's. The end-effector's `linkage` block declares the vendor dimensions from
    which the grasp-plane offset is *derived*.
  - **The program** ([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md)):
    `cite_tools.model.blockly` reads the real robot's Blockly export into the bring-up plan,
    accepts only the block types that program uses, and refuses anything else, so a program
    edited on the robot to use a block the twin does not model fails validation instead of
    being approximated. The file is read-only and pinned by
    `tools/tests/test_real_program_is_pinned.py` (`model/programs/README.md`).
  - **The track** (ADR-0067): the arm stands on a linear-axis type
    (`model/assets/types/axes/ufactory_linear_motor.yaml`) with its own trajectory controller.
  - **The planner** ([ADR-0027](../adr/0027-pilz-planning-pipeline.md)): the robot type declares
    default and fallback pipelines, the planner id for each, a per-joint deceleration limit
    and Cartesian ceilings; the generator holds what a pipeline is *made* of (the P5 split).
  - **The beams** ([ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md)): an
    indexing break beam's stand-off is derived from the part length and the beam width, and a
    non-zero authored offset is refused.
  - **The pair** ([ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md)):
    a zone declares `twin: {sides: single | pair}`, required with no default, and an instance
    may declare `hardware.counterpart_backend`. **Twinned is derived** from `sides == pair`.
    Pairing is a model change, not a runtime mode: it regenerates `cite_generated/` and moves
    `MODEL_HASH`; the runtime knob is `TwinMode`. A paired zone emits one more `sides:` entry
    and each asset's counterpart backend into the bring-up plan. A counterpart on the plant's
    backend adds nothing else: no second world, controller manager or set of node names,
    because it is the same artifacts started in another environment. A counterpart on a
    different backend is the physical one, described next.
  - **Which backend reaches a machine**
    ([ADR-0054](../adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md)):
    `hardware_backends.<id>.commands_physical_hardware` is required with no default, and every
    hardware gate reads it rather than the backend's name. Nothing verifies the claim against
    the plugin string beside it. `use_sim_time` still keys on the backend id, a residual pinned
    by two characterisation tests.
  - **The physical counterpart**
    ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)): `cell_b`'s `picker`
    and `picker_track` declare `counterpart_backend: real`. The generator emits per-side
    artifacts only where a side's backend differs from the plant's, with the side in the file
    path (`description/counterpart/`, `control/counterpart/`) and never in a name. The plan names
    the counterpart's own description, parameters, controllers, vendor names and adapter
    parameters. What L0 declares for that side:
    - a robot address as an environment reference of a declared kind
      (`{env: CITE_XARM_IP, kind: ip_address}`), never a value;
    - on the arm's `real` backend, `vendor_driver`: an allow-list of exactly the vendor services
      the side's nodes call, and the vendor's absolute `controller_manager_services`, which are
      remapped to the side's own;
    - on the track's `real` backend, a `vendor_axis` block (scale, poll period, position age,
      `segment_s`, `auto_enable`); travel and speed stay the axis's own;
    - on the gripper, `grasp.vendor` with `max_pos_pulses`, from which both vendor ranges are
      derived;
    - on the zone's `twin` block, `heartbeat_period_s` and a `physical_side` block with the
      deadman's timeout, tick, call deadline and state age.
  - **Refusals** in `cite_tools.validate.referential`, all ERRORs:
    - `physical-plant-on-paired-zone`: a paired zone may not have a physical plant.
    - `counterpart-backend-on-unpaired-zone`.
    - `literal-param-on-physical-backend`.
    - `plugin-less-backend-on-a-bound-description`.
    - `vendor-service-not-allowed` (which refuses the vendor's `debug` switch) and
      `vendor-service-missing`.
    - `vendor-axis-unstated` and `vendor-gripper-units-unstated`.
    - The timing relations: `physical-side-timing-unstated`,
      `deadman-timeout-below-three-heartbeats`, `deadman-tick-not-below-timeout`,
      `state-max-age-not-above-tick`, `state-max-age-not-above-a-poll-period`,
      `track-position-age-not-above-poll`, `track-segment-not-above-poll`,
      `track-segment-above-deadman-timeout`, `track-initialize-speed-above-max` and
      `call-deadline-not-below-timeout`.

    `divergent-counterpart-backend` (ADR-0048 clause 1) was deleted on 2026-10-05, when per-side
    generation made it unnecessary.
  - **Two isolations per side**, emitted for every side: a `gz_partition` and a
    `domain_offset`, formed together in `cite_tools.model.ids`
    ([ADR-0042](../adr/0042-partition-gazebo-transport-per-side.md),
    [ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md) clause 2). The domain is
    an **offset**, never absolute; the base travels in `CITE_DOMAIN_BASE` and
    `cite_bringup.plan.resolve_domain_id` adds them, once.
  `./scripts/sim --pair` brings the pair up
  ([ADR-0047](../adr/0047-two-independent-launches-joined-not-sequenced.md)). Read the emitted
  plan rather than this list for what a model change produces.
- **Related:** [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md), [ADR-0013](../adr/0013-host-agnostic-tooling.md), [ADR-0030](../adr/0030-facility-model-describes-the-workpiece.md), [ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md), [ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md), [ADR-0042](../adr/0042-partition-gazebo-transport-per-side.md), [ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md), [ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md)

## Responsibility

L0 is the single declarative description of everything that physically exists: the
facility and its zones, every asset instance, their poses, their types, the process
topology connecting them, and the program the cell runs. Every artifact the rest of the system needs is **generated** from
it.

This layer has **no runtime behaviour.** It is data, a schema, a validator, and generators.
That is why it can be plain Python with no ROS dependency and run on any machine
([ADR-0013](../adr/0013-host-agnostic-tooling.md)).

## Owns

- The facility model: zones, coordinate frames, asset instances and poses, process topology.
- The JSON Schema that constrains it, and the validator.
- The generators that emit every derived artifact.
- The component library: reusable definitions of the six asset categories the schema
  admits — `robot`, `end_effector`, `conveyor`, `sensor`, `fixture` and `workpiece` —
  instantiated many times with a prefix. A station is not a type; stations live in
  `model/topology/` and name assets.

## Does not own

- **Anything at runtime.** No node, no topic, no service. A running system never reads the
  model; it reads what was generated from it.
- Behaviour. The model says a station *exists* and what it is connected to, never what it
  *does*. The one behaviour it carries is the real robot's program, which it reads, not
  writes.
- Geometry itself. The model references meshes; L1 owns them.
- Tuning values that are not facts about the facility. A controller gain is not a property
  of the building.

## Interfaces

**Consumes:** nothing. L0 is the bottom.

**Produces**, by generation:

| Artifact | Consumed by |
|---|---|
| Simulation world files (SDF) | L1 / the simulator |
| Robot and component descriptions (URDF/Xacro) | L1, L2, MoveIt |
| Controller configurations | L2 |
| MoveIt configuration — SRDF, kinematics, joint limits, Cartesian limits, controllers, and the planning pipelines each arm plans with ([ADR-0027](../adr/0027-pilz-planning-pipeline.md)) | L2 / MoveIt |
| Planning scene | L2 |
| Facility appearance — the material library, and which body wears which entry | whatever spawns a body that is in no description; today `cite_bringup.workpiece` |
| Launch graphs | bringup |
| Process topology | nothing at runtime today; generated and validated |
| Frame and namespace plan | everything |
| Registration reference data | L5 (not produced) |
| Scene topology for display | a future display (not produced) |

## Design

### Shape of the model

Five concerns, kept in separate files so that a layout change and a topology change are
separately reviewable:

```
model/
├── facility/         zones, coordinate frames, the survey origin
├── assets/
│   ├── types/        the component library: reusable type definitions
│   └── instances/    asset instances: id, type, pose, zone, configuration
├── topology/         process flow: stations, upstream/downstream, buffers
├── programs/         the real robot's program, as its own tool exported it
└── schema/           JSON Schema definitions
```

The component library sits inside `assets/` rather than in a directory of its own: a type
and the instances that reference it version together, because changing a type's joint set
and the controllers generated for its instances is one reviewable change. The library's
*geometric* half — what a conveyor looks like and collides like — is L1's and lives in
`assets/` at the repository root. See [ADR-0020](../adr/0020-facility-model-conventions.md)
for the full convention, including units, axes and rotation representation.

The validator itself lives in `tools/cite_tools`, not under `model/` — `model/` is data,
and Python there would sit outside the lint and type-check path
([ADR-0013](../adr/0013-host-agnostic-tooling.md)).

An **asset instance** names a type from the component library and gives it an identity, a
pose, and a zone. Adding a fourth arm is a new instance, not new code — this is what makes
P9 achievable.

### Generation must be deterministic

The same model input must produce **byte-identical** output. This is not a nicety:

- The hand-edit check compares a generated artifact against a fresh generator run. Under
  non-determinism that check reports false positives and gets ignored.
- CI cannot distinguish a real change from generator noise.
- Reproducibility fails silently.

Practically: sort every collection before emitting, never iterate an unordered set, never
embed a timestamp or a random identifier, and never depend on filesystem ordering.
`model-validator` runs the generator twice and diffs.

### Validation is layered

| Level | Catches | Where |
|---|---|---|
| Schema | Structural errors, missing required fields, wrong types | `jsonschema` |
| Referential | An asset referencing a type that does not exist; duplicate IDs; a station referencing a missing asset; a body naming a material the facility's library does not declare | validator |
| Geometric | Assets overlapping; a station outside its zone; a frame outside the body it names; a station out of reach or its approach corridor obstructed; a place point too near the edge of what supports it | validator |
| Physical | Implausible density; an inertia tensor that is not positive definite, breaks the triangle inequality, or is copied between differently sized bodies; a centre of mass outside its geometry; collision geometry reusing a visual mesh; a gripper whose stroke is zero, whose default grasp width cannot close on the narrowest part, whose mimic followers have no velocity headroom, or whose `result_timeout_s` is short enough to cut its own controller's stall search short (ADR-0045); a material worn by a body that stands in the cell declaring a colour brighter than the URDF-to-SDF conversion can carry | validator + `model-validator` |
| Generated | Output that does not match a fresh generator run | `model-validator` |

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Hand-edited generated artifact | Works locally, lost on the next regeneration | `model-validator` diff against fresh output |
| Non-deterministic generation | Spurious CI diffs; hand-edit check becomes noise | Generator run twice, diffed |
| Duplicate asset ID | Namespace collision; two robots publishing the same topic | Schema + referential validation |
| Silently ignored key | A `conveyors:`/`conveyor:` mismatch — exactly what v1 did — so the value falls back to a default and nobody knows | Schema with `additionalProperties: false` |
| Model diverging from reality | Simulation models a facility that does not exist; every measurement quietly wrong | Registration check at L5; physical survey |
| A frame that is arithmetically right and physically useless | The belt's `infeed`/`outfeed` sat exactly on its end planes, so a released cube was neutrally stable, tipped, and fell — while every layer above reported success | `insufficient-support-margin`, which needs the work-piece extents [ADR-0030](../adr/0030-facility-model-describes-the-workpiece.md) added |

The fourth row is worth dwelling on. In v1 the config loader read `conveyor` while the file
said `conveyors`; the conveyor configuration silently fell back to defaults and no error
was raised anywhere. **The schema must reject unknown keys.** A typo in a key name must be
an error, never a default.

## Open questions

- **How are zones bounded?** Axis-aligned boxes are simple and probably enough for a robot
  cell; a scanned building may want polygons. Deferred to Phase 3, when the scan exists.
- **How are model changes versioned against recorded data?** A bag recorded against
  yesterday's layout is not comparable to today's. The likely answer is the model version
  hash (`MODEL_HASH`, served by `model_info`) stamped into every recording.
- **How is a work-piece fact that is really a *pair* fact housed?**
  `default_grasp_width_m` is a property of an end-effector paired with a work-piece and
  currently sits on the end-effector type. With one part size that is written once and the
  validator checks it against the part; with two, it has to move to the work-piece and
  travel on the goal. Decided when a second part exists, not before —
  [ADR-0030](../adr/0030-facility-model-describes-the-workpiece.md).
