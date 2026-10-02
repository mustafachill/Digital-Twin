# Repository layout

- **Status:** `BUILT` — this page lists what is in the main tree, and only that. The target
  shape, including packages that do not exist yet, is the charter's §7
  ([`what-we-are-doing.md`](../../what-we-are-doing.md)). Count anything here by running a
  command rather than reading it off this page: `./scripts/doctor` counts packages and ADRs,
  `./scripts/validate-model` counts what the model declares.
- **Related:** [`README.md`](README.md) (the layer stack), [`../../CLAUDE.md`](../../CLAUDE.md)
  §7 (the commands), [`../../projects/README.md`](../../projects/README.md) (past milestones)

The repository is a monorepo: the ROS 2 workspace, the facility model, the asset pipeline,
the infrastructure and the documentation version together, because they must.

## Top level

```
Digital-Twin/
├── what-we-are-doing.md   the charter — what we are building, why, and how we got here
├── CLAUDE.md              the rulebook — how to work here
├── AGENTS.md              vendor-neutral pointer to CLAUDE.md
├── CONTRIBUTING.md        human contribution workflow
├── README.md              orientation and quick start
├── LICENSE                Apache-2.0
├── model/                 L0: the facility model
├── workspace/src/         the ROS 2 workspace
├── tools/                 host-agnostic Python: validator, generators, asset tooling
├── assets/                L1: meshes, the asset manifest, raw scan data (not committed)
├── tests/                 simulation-in-the-loop scenarios and their guards
├── scripts/               one command per task (CLAUDE.md §7)
├── infra/docker/          container image, entrypoint and compose services
├── .devcontainer/         editor devcontainer definition
├── .github/workflows/     CI (`ci.yml`) and the weekly snapshot check (`projects.yml`)
├── external/              the vcstool manifest and reviewable patch files
├── requirements/          host Python dependencies, and which layer each belongs in
├── projects/              frozen, runnable milestone snapshots (ADR-0068)
└── docs/                  decisions, design, interfaces, operations, onboarding,
                           measurements, reference
```

`.claude/` holds the local agent configuration and is **not committed**; see
[`../onboarding/development-workflow.md`](../onboarding/development-workflow.md).

## `model/` — L0

| Path | Holds |
|---|---|
| `model/facility/` | the facility, its zones (one today, `cell_b`, paired), materials |
| `model/assets/types/` | asset types: robots, axes, end-effectors, conveyors, sensors, fixtures, work-pieces |
| `model/assets/instances/` | asset instances and their poses: arms, tracks, conveyors, sensors, fixtures |
| `model/topology/` | the stations and the process flow of each zone |
| `model/programs/` | the real robot's own program, as its vendor tool exported it — read-only (ADR-0067) |
| `model/schema/` | the JSON Schemas the validator holds the model to |

See [`L0-facility-model.md`](L0-facility-model.md).

## `workspace/src/` — the ROS 2 workspace

| Package | Layer | Holds |
|---|---|---|
| `cite_interfaces` | L3–L5 | every typed contract — messages, services, actions — and the QoS profile library (ADR-0025) |
| `cite_generated` | L0 → L1–L5 | every artifact generated from the model: descriptions, world, controller and MoveIt configuration, frames, topology, bring-up plan, planning scene. Committed, never hand-edited (ADR-0021) |
| `cite_description` | L1 | the project's own description assets — the convex-hull collision meshes — installed so a package URI resolves |
| `cite_facility` | L0–L1 at runtime | serves the model version and the facility's static frames, and loads the generated planning scene into MoveIt |
| `cite_simulation` | L1/L2 | Gazebo Sim system plugins: the conveyor, the break-beam and the simulation-only grasp hold. Nothing above `ros2_control` knows they exist |
| `cite_skills` | L3 | the robot-agnostic skill server: `MoveTo`, `Grasp`, `Pick`, `Place`, `Transfer` |
| `cite_twin` | L5 | the twin boundary: mode control, command routing across both sides, the divergence monitor |
| `cite_bringup` | composition | launch entry points, the lifecycle driver, the pair supervisor, and `cite_bringup.program`, the client that runs the robot's program through the twin boundary |
| `cite_runtime` | mechanism | process lifecycle for this repository's Python nodes, and nothing else (ADR-0034) |
| `cite_test_hardware` | test only | `ros2_control` test doubles, refused by construction in a production bring-up (ADR-0040) |
| `external/` | — | the vendor packages `vcstool` imports from `external/cite.repos`; never committed |

There is **no L4 package** in the main tree: the behaviour-tree line built in Phase 1 left it
with ADR-0069 and runs only in its snapshot. Nothing at L6 or L7 is built.

**`cite_bringup` plays two parts, at two heights of the stack, and that is a recorded debt.**
It is a lower-layer library that L5 imports — `cite_twin` reads the bring-up plan through
`cite_bringup.plan` and announces itself through `cite_bringup.readiness` — and it is also the
home of `cite_bringup/program/`, the program client, which sits **above** L5 and fills L4's role
([README.md](README.md)'s diagram). Nothing in it imports `cite_twin`, so no dependency points
upward today, but one package now spans both sides of L5. **`program/` is the first candidate
for a future L4 package**; `docs/open-work.md` #91 records the placement.

## `tools/`

`tools/cite_tools/` is the L0 validator (`validate/`), the generators (`generate/` and their
`templates/`), the convex-hull and asset tooling, and the repository's own checks — the
English-only check and the documentation link check. `tools/tests/` is the host test suite.
None of it depends on ROS, so it runs on any operating system. `tools/snapshot_project.sh`
extracts a milestone snapshot (ADR-0068).

## `tests/`

`tests/scenarios/` holds the simulation-in-the-loop scenarios `./scripts/scenario` runs —
`bringup` and `program_cycle` — and `tests/scenarios/guards/`, host tests that hold the
scenario harness to its own rules.

## Conventions this layout encodes

- **`cite_generated/` is committed, not built.** Generated artifacts live in git and are
  verified against a fresh generator run, which is what makes hand-editing one detectable
  rather than merely forbidden (ADR-0021).
- **QoS profiles are a library inside `cite_interfaces`, not a table each node copies**
  (ADR-0025).
- **Test-only packages sit outside the production structure.** `cite_test_hardware` is in
  `workspace/src/` because it must build there; its `on_init` refuses to start without a
  parameter the model has no way to declare, so it cannot be selected as an arm's backend
  (ADR-0040). `./scripts/doctor` counts every `package.xml` on disk, so its count answers
  what exists, not what ships.
- **`projects/` is a record, not a source.** Nothing is copied from it into the main tree,
  and the main tree never imports or builds from it (ADR-0068).
