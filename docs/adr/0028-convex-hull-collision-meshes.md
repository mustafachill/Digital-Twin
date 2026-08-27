# ADR-0028: Generate convex-hull collision meshes as project assets, bound through L0

- **Status:** Proposed — **decided in principle, nothing implemented.** No hull exists:
  `assets/` contains only `README.md` and `manifest.yaml`, no `assets/meshes/` directory has
  been created, and the L0 schema has no field through which a collision mesh could be bound
  to a vendor-described type. Promoted to `Accepted` by the change that lands the first hull
  and its binding (P7).
- **Date:** 2026-08-25
- **Deciders:** Project owner, on the real-time-factor measurement from the Phase 1.C review wave
- **Related:** [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0012](0012-large-asset-storage.md), [ADR-0020](0020-facility-model-conventions.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0027](0027-pilz-planning-pipeline.md),
  [L1](../architecture/L1-description-and-assets.md), [`../../assets/README.md`](../../assets/README.md),
  CLAUDE.md §10, charter §4 (P1, P5, P8)

## Context

### The failure CLAUDE.md names by name is in the tree

CLAUDE.md §10 lists it as a standing review checkpoint: *"wrong inertia tensors and dense
visual meshes reused as collision geometry make a simulation run confidently and wrongly."*
That is what the three arms are running today.

Traced through the vendor description on 2026-08-25. `model/assets/types/robots/xarm5.yaml`
sets `mesh_suffix: stl` and `model1300: false`, so `model_num` resolves to `-1`
(`xarm_description/urdf/common/common.link.xacro`), and the selector at the top of
`urdf/xarm5/xarm5.urdf.xacro` takes its `unless` branch:

```xml
<xacro:unless value="${mesh_suffix == 'dae' or (model_num >= 1305 and model_num != 1380)}">
  <xacro:property name="visual_dir"    value="xarm5/visual"/>
  <xacro:property name="collision_dir" value="xarm5/visual"/>
```

`collision_dir` **is** `visual_dir`. The gripper does the same thing unconditionally:
`xarm_gripper.urdf.xacro` passes the identical `mesh_filename` to `common_link_visual` and
`common_link_collision` on all seven of its links.

Counted from the checked-out vendor meshes (binary STL triangle count read from the header,
`workspace/src/external/xarm_ros2/xarm_description/meshes/`):

| | triangles |
|---|---|
| `xarm5/visual/link2.stl` — the worst single link | **26,118** |
| `gripper/xarm/base_link.stl` | 24,227 |
| all **12** links per arm whose collision mesh is their visual mesh | **98,292** |
| across three arms | **294,876** |
| `end_tool/collision/end_tool.stl` — the one link that has a real collision mesh, `link5` | 260 |

Three links per arm carry no geometry at all — `link_eef`, `link_tcp`, and the
`arm_N_mount` link the generator emits — leaving thirteen with geometry. Of those,
**twelve** collide against a rendering mesh and one, `link5`, against a 260-triangle proxy.

### The measurement that gives it urgency

Real-time factor on the development host is **0.14** — `/cite/cell_a/arm_1/joint_states`
arrives at roughly **21 Hz** against the **150 Hz** the model configures
(`xarm5.yaml: control.update_rate_hz: 150`, generated into
`cite_generated/control/cell_a_arm_*_controllers.yaml` as `update_rate: 150`). The figure is
recorded in the tree at `tests/scenarios/bringup.py`, where every wall-clock ceiling in the
bring-up scenario is justified against it.

That is the load context in which `move_group` overran launch's **5 s** SIGINT default and
was killed mid-teardown, recording `-15` — the truncation rather than whatever the process
was actually doing. The deadline has since been raised to 45 s SIGTERM / 60 s SIGKILL
(`cite_bringup/launch/simulation.launch.py`, `TEARDOWN_SIGTERM_S`/`TEARDOWN_SIGKILL_S`), so
the symptom is gone. **The load that produced it is not.**

Under [ADR-0027](0027-pilz-planning-pipeline.md) this stops being only a performance
concern. A planner that fails on collision rather than routing around it makes the fidelity
of every collision surface load-bearing, and a 26,118-triangle hull of a rendering mesh is
not a fidelity improvement over a convex hull — it is the same shape with concavities the
solver must resolve, at two orders of magnitude more contact pairs.

### The validator that cannot fire

`cite_tools.validate.physical._collision_is_not_a_visual_mesh` is documented in its own
docstring as *"the single most consequential rule in L1, checked mechanically."* Its first
two lines are:

```python
body = asset_type.description.body
if body is None:
    return []
```

`description.body` is populated only for the bodies **we** author — conveyors, tables,
pedestals. Every vendor-described type sets `provider: xacro_macro` and leaves `body` unset,
so the check returns an empty list for it. **The rule can never fire on any vendor
description**, which is to say it cannot fire on the only links where the failure it names
actually occurs. It has been passing for as long as it has existed, and it is passing now.

### Why this is not a one-line flag change

The vendor does ship a decimated collision set, but only for one variant: under
`meshes/`, `xarm5_1305/` contains both `visual/` and `collision/`, while `xarm5/` contains
`visual/` alone. Reaching the decimated set means selecting `xarm5_1305` — a *different
robot variant*, with different kinematics parameters and a different inertial file, chosen
by `model_num >= 1305`. Changing which arm we model in order to obtain better collision
geometry would be a silent change to what the twin claims to represent, which is exactly
what P8 exists to prevent.

## Options considered

### Option A — Leave it, and buy real-time factor elsewhere
Raise ceilings, run on faster hardware, reduce the physics rate.

Rejected. It treats a fidelity defect as a scheduling problem. Contact behaviour computed
against a rendering mesh is not merely slow, it is wrong in a way nobody can explain at the
point it surfaces — which is CLAUDE.md §10's word for it, "confidently and wrongly" — and
under ADR-0027 wrong collision surfaces become refused motions rather than slow ones.

### Option B — Switch the model to the `xarm5_1305` variant
Set `model1300`/`robot_sn` so the vendor's `collision_dir` resolves to `xarm5_1305/collision`.

Rejected. It changes which physical arm the model describes in order to obtain a mesh. The
1305 variant carries its own kinematics and inertial parameters, so the twin would silently
represent hardware CITE does not have, and every measurement taken from it would be against
the wrong arm. The layout is already `PROVISIONAL` (CLAUDE.md §2); adding a second
unacknowledged divergence from reality is not acceptable.

### Option C — Replace collision geometry with primitives
Boxes and cylinders per link, authored by hand.

Rejected as the general answer, though it remains right for individual links. A primitive
per link is a hand-written approximation of vendor geometry, which means a value that exists
in two places (P1) and drifts on the first vendor upgrade. It is also strictly less accurate
than a hull for the links that matter, without being meaningfully cheaper.

### Option D — Generate convex hulls as project assets, bound through the L0 robot type
Compute a convex hull per link from the vendor visual mesh, store the result under
`assets/meshes/` with provenance in `assets/manifest.yaml` (ADR-0012), and bind it to the
type in `model/assets/types/robots/xarm5.yaml`. Chosen.

The hull is **derived** from the vendor mesh rather than authored, so it is reproducible and
regenerable on a vendor upgrade — P1 holds because the source of the shape is still the
vendor file. The binding lives in L0, so which mesh a link collides with is data, and a new
robot type is a model change and not a code change (P5, P9).

## Decision

**Collision geometry for vendor-described links is a convex hull, generated as a project
asset from the vendor's visual mesh and bound to the robot type in the L0 model.**

Four parts, and all four are required for the decision to mean anything:

1. **Hull generation is a `tools/` pipeline stage**, host-agnostic like the rest of L0
   (ADR-0013), reproducible, and covered by unit tests. Its output is deterministic for a
   given input mesh, so a regenerated hull is byte-identical or the change is real.
2. **Hulls are stored as project assets** under `assets/meshes/`, with provenance and
   checksums in `assets/manifest.yaml`, per ADR-0012 and `assets/README.md`. They are
   derived, not vendored third-party source, so ADR-0008 is not engaged.
3. **The binding is L0 data.** The robot type gains a field expressing "this link's
   collision geometry is this mesh". The L0 schema has no such field today —
   `DescriptionSpec` offers `fixed_args`, `bound_args` and `body`, none of which express a
   per-link collision override for a `xacro_macro` provider — so adding it is part of this
   work, and it must be added in a form that a *different* vendor description could also use.
4. **`_collision_is_not_a_visual_mesh` is extended to the `xacro_macro` provider**, so that
   the rule fires on the links it was written for. A validator that cannot fail on the case
   it names is worse than no validator, because its silence has been read as evidence.

**No status improves on the strength of this record.** L1 stays as it is marked until a
hull exists and a measurement shows what it bought. Under P8 the claim that this improves
real-time factor is earned by re-measuring RTF and `joint_states` frequency against the
0.14 / ~21 Hz baseline, not by asserting that hulls are faster.

## Consequences

### What this gets us
- Contact geometry that a physics solver can actually evaluate, in place of 98,292 triangles
  per arm of rendering detail — the failure CLAUDE.md §10 names, removed at its cause.
- Headroom on the measurement that currently governs every wall-clock ceiling in the
  scenario suite. Ceilings chosen against RTF 0.14 exist because of this, and they are the
  reason a slow machine and a hung machine look alike today.
- A collision surface fit for a planner that refuses rather than searches (ADR-0027).
- A validator that fires on vendor descriptions, which is the majority of the links in the
  cell and all of the ones that move.
- A pipeline the facility scan will need anyway in Phase 3, built once, on geometry small
  enough to debug.

### What this costs us
- **A new asset class to produce, store and keep in step with the vendor.** A vendor upgrade
  that changes a mesh now requires regenerating hulls, and a stale hull is a collision shape
  that does not match the arm — a failure that looks like a planner bug.
- **A convex hull is not the true shape.** Concavities are filled: the space between the
  gripper fingers, and any pocket a real part could enter, becomes solid. For the gripper in
  particular this is likely to be wrong in a way that matters, and per-link exceptions
  (primitives, or multiple hulls for one link) will be needed. That is a genuine loss of
  fidelity traded for a genuine gain in solvability, and it must be stated wherever a
  contact measurement is published (P8).
- **An L0 schema change**, which is a versioned contract with generated artifacts behind it
  (ADR-0021). Every generated file that references a collision mesh changes with it.
- **Build and pipeline time**, plus a new dependency for hull computation that
  `requirements/README.md` has to place in exactly one of the four layers.

### What we will have to revisit
- **When the gripper's filled concavity produces a wrong grasp.** The fingers are the links
  whose exact geometry decides whether a part fits, and they are the links a convex hull
  approximates worst. If it bites, the answer is per-link geometry for the fingers, not
  abandoning hulls elsewhere.
- **When the RTF re-measurement lands.** If 0.14 does not move materially, the bottleneck is
  elsewhere — three controller managers at 150 Hz, or the physics step itself — and this
  record must not be cited as having fixed it.
- **When the Phase 3 facility scan arrives.** Scanned geometry is far heavier than any of
  this, and the decimation and level-of-detail policy in `assets/README.md` will need to say
  how a scanned collision representation is produced. This pipeline should be the one that
  does it, or the project has two.
- **If a future vendor description ships usable collision meshes for the variant we model.**
  Then the binding added here points at the vendor's file instead of ours, which is the same
  mechanism and no schema change.
