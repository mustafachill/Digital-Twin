# CITE Digital Twin

A **facility-scale digital twin** of the Center for Innovation, Technology and
Entrepreneurship at Sam Houston State University, built on ROS 2 and Gazebo. Its first
instrument is a multi-robot UFACTORY xArm work cell; its scope is the building around it.

It is a *twin*, not a simulation. Real hardware and the virtual model share **one control
interface**, and the system **continuously measures how far the model is from reality**.

---

## What "digital twin" means here

The term is used loosely enough to be almost meaningless, so this project uses a staged
definition and states which level it has actually reached. The levels align with the
published literature (Kritzinger et al., 2018); L2 is our own refinement.

```
  L4  Predictive     the twin runs ahead of reality and answers what-if
  L3  Closed loop    the twin validates, then commands the physical cell
  L2  Validated      divergence between model and reality is measured   ◄── our commitment
  L1  Shadow         physical state continuously drives the virtual model
  L0  Virtual model  a simulation, with no automated link to anything   ◄── where v1 stopped
```

**L2 is the level that matters.** A shadow whose error nobody measures is an assertion, not
a twin — which is why every fidelity claim in this project has to carry a published number.

> **Today the rebuild has not yet reached L0.** The architecture, environment, and
> documentation exist; no simulation runs yet. See [Status](#status). Saying so plainly is
> a project rule, not modesty — the previous iteration called itself a digital twin while
> containing no hardware interface at all.

## Status

A capability is listed as working only when something proves it.

| | State |
|---|---|
| Charter, architecture, ADRs | **Written** — 19 decisions recorded, 8 layers specified |
| Environment, dependencies, CI | **Working** — one command from clone to a built container |
| Supply-chain and CVE scanning | **Working** — zero known vulnerabilities in the tooling layer |
| Agent review pipeline | **Configured** — 11 roles |
| L0 facility model | Phase 1.B — not started |
| ROS packages | Phase 1.B — not started |
| Three-robot virtual line | Phase 1.D — not started |
| Physical hardware integration | Phase 2 |
| CITE facility 3D scan | Phase 3 |
| Data platform and operator HMI | Phase 4 |

`./scripts/doctor` reports **one** failing check on a clean clone: `xarm_ros2` is pinned to
the `jazzy` branch rather than a commit SHA, so two clones on different days can differ.
That is the last open Phase 1.A gate. Its support for Jazzy + Harmonic is *verified* —
see [ADR-0003](./docs/adr/0003-gazebo-harmonic.md).

## Quick start

```bash
git clone https://github.com/mustafachill/Digital-Twin.git
cd Digital-Twin
./scripts/bootstrap      # Python tooling, container image, dependencies
./scripts/doctor         # what works on this machine, and what does not
```

**You can author anywhere. Building and running require Linux** — ROS 2 Jazzy, Gazebo
Harmonic, and MoveIt 2 do not run natively on macOS or Windows. You should never have to
think about it: on a machine without ROS the scripts re-execute themselves inside the
container, so `./scripts/build` behaves identically on a MacBook and on the lab
workstation.

Authoring only, no Docker, nothing to build:

```bash
./scripts/bootstrap --host-only
```

Then read [`docs/onboarding/getting-started.md`](./docs/onboarding/getting-started.md).

## How the system is built

A strict layer stack. **A layer may depend only on layers below it** — an upward
dependency is an architectural defect, not a style preference.

```
  L7  PRESENTATION       operator HMI · remote access
  L6  DATA & TELEMETRY   telemetry schema · recording · historian · replay
  L5  TWIN SYNC          mode control · mirroring · divergence metrics · calibration
  L4  ORCHESTRATION      behaviour trees · line coordination · handoff · recovery
  L3  CAPABILITY         MoveTo · Pick · Place · Transfer · Grasp · Detect
  L2  CONTROL & HAL      ros2_control · MoveIt 2 · hardware interfaces
  L1  DESCRIPTION        URDF/Xacro · SDF · meshes · generated worlds
  L0  FACILITY MODEL     the single declarative source of truth
```

Three ideas hold it together:

**The facility is described once.** Worlds, robot descriptions, controller configurations,
and launch graphs are *generated* from the L0 model, never hand-written. Changing the cell
layout is a data change. ([ADR-0004](./docs/adr/0004-facility-model-single-source-of-truth.md))

**`ros2_control` is the simulation/hardware boundary.** Above it, nothing knows which is
running. Topic, action, controller, joint, and frame names are identical; only the loaded
hardware plugin differs. This is what makes work validated in simulation mean something on
hardware. ([ADR-0005](./docs/adr/0005-ros2-control-sim-real-boundary.md))

**Everything replaceable is replaceable at its interface.** Robot types, end-effectors,
sensors, and process stations are configuration entries. A new robot must not touch
orchestration.

The architecture is mapped onto **ISO 23247**, the international reference architecture for
manufacturing digital twins — see
[standards alignment](./docs/architecture/standards-alignment.md). We are aligned with it;
we are not certified, and no document here claims otherwise.

## Commands

Fixed entry points. Always invoke these rather than `colcon`, `docker`, or `ros2 launch`
directly — they route to the right environment automatically.

| Command | Purpose |
|---|---|
| `./scripts/bootstrap` | Prepare or repair the environment. Idempotent. |
| `./scripts/doctor` | Diagnose. Run this first when something is wrong. |
| `./scripts/build` | Build the ROS 2 workspace. |
| `./scripts/test` | Host tooling tests, then ROS tests. |
| `./scripts/lint` · `format` | Check · apply formatting and static analysis. |
| `./scripts/validate-model` | Validate the facility model. Runs anywhere. |
| `./scripts/sim [--headless]` | Launch the simulated cell. |
| `./scripts/scenario [name]` | Run a headless scenario; no argument lists them. |
| `./scripts/audit-deps [--image]` | Scan dependencies for known vulnerabilities. |
| `./scripts/fetch-assets` | Download large assets declared in the manifest. |
| `./scripts/enter [dev\|gui\|hardware]` | Interactive shell in the container. |
| `./scripts/clean [--all]` | Remove build artifacts. |

Quality gate before any handoff:

```bash
./scripts/lint && ./scripts/build && ./scripts/test
```

## How we work

The rules are in [`CLAUDE.md`](./CLAUDE.md); the reasoning behind each one is in
[`docs/adr/`](./docs/adr/README.md). Three things are worth knowing before you read code:

- **Decisions are recorded before they are implemented.** Nineteen ADRs cover every locked
  technology and boundary choice, each stating what it costs as well as what it buys.
- **Documentation is a contract, not a description.** Layer documents carry a status
  marker — `DESIGNED`, `PARTIAL`, or `BUILT` — so a specification is never mistaken for
  something that exists.
- **Review is partly automated.** Eleven specialist agents run against changes, including
  two written for this domain: one that validates the facility model and its generated
  artifacts (inertia tensors, collision geometry, interface matching), and one that audits
  every code path capable of moving a robot. The roster and its dispatch rules live in
  `.claude/`, which is local tooling and is not distributed with the repository.

Some standing prohibitions, so they are not a surprise in review: no hand-edited generated
artifacts, no structured data in a `std_msgs/String`, no `sleep` used to sequence startup,
no third-party source copied into the tree, and nothing marked complete without a test.

## Documentation

| Question | Go to |
|---|---|
| What are we building, and why? | [`what-we-are-doing.md`](./what-we-are-doing.md) — the charter |
| What rules apply to my change? | [`CLAUDE.md`](./CLAUDE.md) |
| How do I get set up? | [`docs/onboarding/getting-started.md`](./docs/onboarding/getting-started.md) |
| Why was *X* chosen over *Y*? | [`docs/adr/`](./docs/adr/README.md) |
| How does layer *N* work? | [`docs/architecture/`](./docs/architecture/README.md) |
| What shape is this interface? | [`docs/interfaces/`](./docs/interfaces/README.md) |
| How do I bring up or calibrate the cell? | [`docs/operations/`](./docs/operations/README.md) |
| Where do I read more? | [`docs/reference/`](./docs/reference/README.md) |
| What does this term mean here? | [`docs/onboarding/glossary.md`](./docs/onboarding/glossary.md) |

## Technology

| | |
|---|---|
| Platform | Ubuntu 24.04 LTS · ROS 2 Jazzy · Gazebo Harmonic — both supported to May 2029 |
| Control | `ros2_control` · `gz_ros2_control` · MoveIt 2 |
| Orchestration | BehaviorTree.CPP v4 · Groot2 |
| Data | `rosbag2` with MCAP · Foxglove · RViz 2 |
| Environment | Docker · devcontainer · GitHub Actions |
| Languages | C++ on control paths, Python for orchestration and tooling |

Every row has an ADR recording why it was chosen and what it cost.

## Repository layout

```
what-we-are-doing.md   the charter — what we are building and why
CLAUDE.md              the rulebook — how to work here
model/                 L0: the facility model (Phase 1.B)
workspace/src/         the ROS 2 workspace (Phase 1.B)
tools/                 host-agnostic Python tooling — no ROS dependency
assets/                3D assets and the scan pipeline
infra/docker/          container image and compose services
external/              pinned third-party sources — never vendored
scripts/               one command per task
docs/                  architecture · ADRs · interfaces · operations · reference
legacy/                superseded v1 — reference only, deleted at end of Phase 1
```

The charter's [§7](./what-we-are-doing.md) describes the target structure in full.

## A note on `legacy/`

The project spent an extended R&D period before this rebuild. That work produced real
knowledge and a codebase that could not be built from a clean clone by anyone. It is kept
as reference, excluded from the build, and deleted at the end of Phase 1. Why it is being
replaced rather than migrated is recorded in
[ADR-0001](./docs/adr/0001-rebuild-rather-than-migrate.md), and several of this project's
firmest rules exist because of specific ways it failed.

## License

Apache-2.0 — see [`LICENSE`](./LICENSE).

Third-party dependencies are consumed, never vendored
([ADR-0008](./docs/adr/0008-external-dependencies-via-vcstool.md)), so this repository
distributes no code but its own.
