# L0 — Facility model

- **Status:** `DESIGNED` — schema and generators are Phase 1.B. `model/` is empty today.
- **Related:** [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md), [ADR-0013](../adr/0013-host-agnostic-tooling.md)

## Responsibility

L0 is the single declarative description of everything that physically exists: the
facility and its zones, every asset instance, their poses, their types, and the process
topology connecting them. Every artifact the rest of the system needs is **generated** from
it.

This layer has **no runtime behaviour.** It is data, a schema, a validator, and generators.
That is why it can be plain Python with no ROS dependency and run on any machine
([ADR-0013](../adr/0013-host-agnostic-tooling.md)).

## Owns

- The facility model: zones, coordinate frames, asset instances and poses, process topology.
- The JSON Schema that constrains it, and the validator.
- The generators that emit every derived artifact.
- The component library: reusable definitions of robot types, end-effectors, sensors, and
  station types, instantiated many times with a prefix.

## Does not own

- **Anything at runtime.** No node, no topic, no service. A running system never reads the
  model; it reads what was generated from it.
- Behaviour. The model says a station *exists* and what it is connected to, never what it
  *does* — that is L4.
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
| Launch graphs | bringup |
| Process topology | L4 |
| Frame and namespace plan | everything |
| Registration reference data | L5 |
| Scene topology for display | L7 |

## Design

### Shape of the model

Four concerns, kept in separate files so that a layout change and a topology change are
separately reviewable:

```
model/
├── facility/         zones, coordinate frames, the survey origin
├── assets/
│   ├── types/        the component library: reusable type definitions
│   └── instances/    asset instances: id, type, pose, zone, configuration
├── topology/         process flow: stations, upstream/downstream, buffers
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
| Referential | An asset referencing a type that does not exist; duplicate IDs; a station referencing a missing asset | validator |
| Geometric | Assets overlapping; a station outside its zone; a pose outside the facility | validator |
| Physical | Implausible mass, invalid inertia tensor, missing collision geometry | validator + `model-validator` |
| Generated | Output that does not match a fresh generator run | `model-validator` |

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Hand-edited generated artifact | Works locally, lost on the next regeneration | `model-validator` diff against fresh output |
| Non-deterministic generation | Spurious CI diffs; hand-edit check becomes noise | Generator run twice, diffed |
| Duplicate asset ID | Namespace collision; two robots publishing the same topic | Schema + referential validation |
| Silently ignored key | A `conveyors:`/`conveyor:` mismatch — exactly what v1 did — so the value falls back to a default and nobody knows | Schema with `additionalProperties: false` |
| Model diverging from reality | Simulation models a facility that does not exist; every measurement quietly wrong | Registration check at L5; physical survey |

The fourth row is worth dwelling on. In v1 the config loader read `conveyor` while the file
said `conveyors`; the conveyor configuration silently fell back to defaults and no error
was raised anywhere. **The schema must reject unknown keys.** A typo in a key name must be
an error, never a default.

## Open questions

- **How are zones bounded?** Axis-aligned boxes are simple and probably enough for a robot
  cell; a scanned building may want polygons. Deferred to Phase 3, when the scan exists.
- **How are model changes versioned against recorded data?** A bag recorded against
  yesterday's layout is not comparable to today's. The likely answer is a model version
  hash stamped into every recording — decide with L6 in Phase 4.
- **Does the model describe products and work-pieces, or only equipment?** Currently only
  equipment. If work-piece types acquire attributes that matter to orchestration, this
  needs revisiting.
