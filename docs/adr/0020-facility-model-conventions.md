# ADR-0020: Fix the facility model's units, axes, and file layout

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0004, ADR-0013, [L0](../architecture/L0-facility-model.md), [naming-and-namespaces.md](../architecture/naming-and-namespaces.md)

## Context

[ADR-0004](0004-facility-model-single-source-of-truth.md) established that the L0 facility
model is the single source of truth and that every derived artifact is generated from it.
It did not say what the model *looks like*.

[`L0-facility-model.md`](../architecture/L0-facility-model.md) fixes four things and
deliberately leaves the rest open: the four directories under `model/`, that the schema is
JSON Schema with `additionalProperties: false`, that generation is byte-identical across
runs, and that an asset instance has an `id`, a `type`, a `pose`, a `zone` and a
`configuration`. Everything below that level is undefined — there is no unit system, no
rotation representation, no axis convention, no file-naming rule, and no home for the
component library that L0 says it owns.

These are conventions that every future contributor and generator must follow, so
[`adr/README.md`](README.md) requires a record, and charter §10.3 requires it before the
implementation rather than after.

Two constraints are fixed and not up for debate. Every downstream consumer of this model —
URDF, SDF, `ros2_control`, MoveIt, TF — is metres-and-radians, right-handed and Z-up,
because REP-103 and the SDF and URDF specifications all say so. And the model must survive
Phase 2 writing calibration results back into it without destroying the engineered
intent it started from.

## Options considered

### Option A — SI throughout, with unit-suffixed field names
Metres, radians, kilograms, seconds, expressed in field names that carry the unit:
`xyz_m`, `rpy_rad`, `mass_kg`. Verbose, and unusual enough that it needs justifying.

### Option B — SI throughout, with bare field names
`xyz`, `rpy`, `mass`. Conventional and shorter. Rejected: it puts the unit in a comment,
and a comment is not checkable. `speed: 0.15` is then a valid document whether the author
meant metres per second or millimetres per second, and the failure is silent — which is
the exact class of defect ADR-0004 exists to eliminate. With the unit in the name and
`additionalProperties: false` in the schema, changing a unit becomes a schema change and
therefore a review.

### Option C — Human-friendly units with conversion at load time
Degrees for angles, millimetres for lengths, because that is what a technical drawing and
a UFACTORY datasheet use. Rejected on two counts. It requires a conversion layer between
L0 and every consumer, and a conversion layer is where a factor of a thousand or a sign
hides. Worse, in practice it never stays single-valued: someone adds `yaw_rad` alongside
`yaw_deg` "for convenience" and the same fact now exists twice, in violation of P1.

### Option D — Quaternions for orientation
Free of gimbal lock and unambiguous. Rejected for the *model*: a quaternion is not
reviewable by a human, and the model's primary reader is a person checking that a robot
faces the conveyor. URDF `<origin rpy>` and SDF `<pose>` are both roll-pitch-yaw, so
quaternions would also require conversion on every emission. They remain the right choice
in generated artifacts and at runtime, where no human reads them.

## Decision

**Units.** Strict SI everywhere in `model/`: metres, radians, kilograms, seconds, and
derived units in the same system. No degrees, no millimetres, no alternate representation
of the same quantity anywhere in the model.

**Field naming.** Every field carrying a physical quantity names its unit as a suffix —
`xyz_m`, `rpy_rad`, `mass_kg`, `speed_mps`, `length_m`. Combined with
`additionalProperties: false`, this makes an unsuffixed quantity unrepresentable.

**Axes.** REP-103: right-handed, x forward, y left, z up. The facility root frame
`cite_world` is z-up and tied to the surveyed physical origin.

**Rotation.** `rpy_rad: [roll, pitch, yaw]`, intrinsic Z-Y-X — `R = Rz(yaw)·Ry(pitch)·Rx(roll)`
— which is what URDF `<origin rpy>` and SDF `<pose>` mean. The generator performs no
rotation conversion; a model triple is copied verbatim into the emitted pose.

**Transform composition.** `T_world_child = T_world_parent · T_parent_child`. A calibration
correction is applied as a body-frame post-multiplication:
`T_world_asset = T_world_parent · T_nominal · T_correction`.

**Pose is written once.** An asset instance has exactly one `pose`, expressed relative to
`cite_world` or to a named frame on another asset (`<asset_id>/<frame_id>`). Task poses —
where an arm picks, where it places — are never written in the model. Types declare named
frames; instances are placed; stations reference `<asset_id>/<frame_id>`. This makes v1's
duplicated-and-diverged pick-and-place coordinates structurally unrepresentable.

**Calibration is separate from intent.** `registration` is its own object alongside `pose`,
never merged into it, so that a Phase 2 write-back never overwrites the engineered value
and `git diff` shows exactly what calibration changed.

**File layout.**

```
model/
├── facility/     facility identity, root frame, survey origin, zones
├── assets/
│   ├── types/    the component library — reusable type definitions
│   └── instances/  placed instances, one file per asset kind
├── topology/     stations and the process flow edge list
└── schema/       JSON Schema, a generated export (see ADR-0021)
```

The component library lives at `model/assets/types/` rather than in a fifth top-level
directory. L0 owns the declarative half of the library and L1 owns its geometric half, so
the library is genuinely split; the declarative half belongs with the instances that
reference it, because changing a type's joint set and the controllers generated for its
instances is one reviewable change. Meshes and materials stay in `assets/` at the
repository root, referenced by URI, never inlined.

**Files do not affect output.** Every model file declares its own `schema:` key, and the
loader dispatches on that key rather than on the directory it was found in, so a misfiled
document is an error rather than a silent omission. The loader globs, then sorts every
collection by `id` before any generator sees it — so renaming or splitting a model file
produces no diff in generated output.

**Float emission has one implementation.** A single formatter in `cite_tools`, used by
every template, with `-0.0` normalised to `0.0`. Nothing else formats a float, because
generation must be byte-identical (ADR-0004).

## Consequences

### What this gets us
- No unit conversion anywhere between the model and any consumer. A model value is copied
  verbatim into URDF, SDF and TF, so a factor-of-a-thousand error has nowhere to live.
- Unit errors become schema errors. A large share of robotics defects are unit errors, and
  this converts an entire class of them from runtime-silent to review-time-loud.
- A layout change and a topology change remain separately reviewable, which is what
  `L0-facility-model.md` asked the directory split to achieve.
- Calibration can be written back into the model — which L5 requires — without any risk of
  losing the designed pose it corrects.

### What this costs us
- **Verbosity.** `xyz_m` and `rpy_rad` everywhere is uglier than `xyz` and `rpy`, and the
  suffixes appear thousands of times across a facility-scale model.
- **Radians are not how anyone thinks.** A reviewer checking that an arm faces the conveyor
  reads `1.570796327` rather than `90`. We accept this because the alternative is a second
  representation of the same angle, and mitigate it with `cite-model show`, which renders
  the model in human units for reading — a *view*, never a source.
- **RPY is degenerate near gimbal lock.** This is safe here because engineered mounting
  poses are axis-aligned or near it, and calibration corrections are small by definition. If
  a correction ever approaches gimbal lock, the registration is wrong, not the
  representation. Nobody should "fix" this by switching the model to quaternions.
- A fifth concern (`types/`) nested inside `assets/` is one level deeper than the flat
  four-directory picture in `L0-facility-model.md`, so that document needs a sentence
  updating.

### What we will have to revisit
- If the model ever has to describe something outside a single building — a site with
  several facilities at surveyed geodetic positions — `cite_world` as a single Cartesian
  root stops being sufficient and this decision is reopened alongside the zone-bounds
  question that L0 defers to Phase 3.
- If a vendor component ever forces a non-SI quantity into the model (a datasheet value
  with no SI equivalent), the rule against alternate representations is what has to be
  argued about, not quietly bent.
