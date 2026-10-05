# CITE Digital Twin

A **real + digital twin** of the UFACTORY xArm work cell at the Center for Innovation,
Technology and Entrepreneurship (CITE), Sam Houston State University, built on **ROS 2 Jazzy**
and **Gazebo Harmonic**. The target is a physical cell and a simulated one sharing **one
control interface**, with the system **continuously measuring how far the model is from
reality**. The cell is the first instrument; the project's scope is the building around it
([charter](./what-we-are-doing.md)).

**The counterpart is the physical arm, and it has never been driven.** Its side is built and
tested only against fakes ([ADR-0070](./docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)), so nothing here is measured against reality yet. Saying so plainly is a project rule, not modesty.

---

## Where the main tree is now

- **The real robot's program drives both sides of the twin.** The real xArm 5's UFACTORY
  Studio program is kept byte for byte in `model/programs/` and read strictly into the
  generated bring-up plan. `./scripts/program` brings up both sides of the paired zone
  `cell_b` — the Gazebo plant and the physical xArm 5 as its counterpart, which needs
  `CITE_ALLOW_HARDWARE=1` and refuses without it ([ADR-0070](./docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)) — and sends
  that program **once** through the twin boundary, so both arms and both tracks follow it
  ([ADR-0067](./docs/adr/0067-the-real-program-drives-the-twin-on-a-track.md), `Proposed`).
  The belt is not twinned: each side's belt is started on that side.
- **What checks it:** `./scripts/scenario program_cycle` runs the program on the plant side
  and asserts from the simulator that the part was lifted, carried along the track, placed on
  the belt and belted on. It is a blocking CI step (`.github/workflows/ci.yml`). **No scenario
  and no CI step brings the pair up**; both sides together are shown by `./scripts/program`
  and asserted by nothing.
- **What is not built or not proven.** The physical counterpart's side — vendor
  `ros2_control` plugin, track adapter, gripper relay and deadman — is built and has never
  driven the arm ([ADR-0070](./docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md));
  what only the bench can answer is in [`docs/open-work.md`](./docs/open-work.md) #93. A twin
  mode change during a track move sends no stop, and the counterpart's custody is not read
  back (ADR-0067). The cell layout is engineered, not surveyed (Phase 3).
- **The three-arm event-driven line is not in the main tree.** It, its behaviour-tree package
  and zone `cell_a` were removed on 2026-10-01 ([ADR-0069](./docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)) and run as milestone 01 below, which a
  weekly, non-blocking workflow checks; main CI no longer drives `pick_and_place` or
  `continuous_line`.

The current state, stated without counts, is [`CLAUDE.md`](./CLAUDE.md) §2; every count
comes from the `./scripts/*` command that reports it, and what a past milestone measured is
kept with that milestone (see [`projects/README.md`](./projects/README.md)). Each layer's design document in
[`docs/architecture/`](./docs/architecture/README.md) carries a `DESIGNED`, `PARTIAL` or
`BUILT` marker; read it before believing the body.

## Milestones

Three steps on the way here are kept as frozen, runnable snapshots under
[`projects/`](./projects/README.md), each a folder that builds and runs on its own
([ADR-0068](./docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md), `Proposed`):

| | Milestone | Run it |
|---|---|---|
| 01 | Three arms on `cell_a`, coordinated by behaviour trees on beam events | `projects/01-three-arm-event-driven-line/run` |
| 02 | One fixed program of taught poses drives both sides of the pair | `projects/02-fixed-program-pair/run` |
| 03 | The real robot's program drives both sides, the arm on a track | `projects/03-real-program-twin-on-track/run` |

Snapshots are records, not sources: nothing is copied from them into the main tree.

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

> **Today the rebuild is at L0.** Two simulated sides of one cell follow one program through
> the twin boundary, but both run the same model and the same solver, so their agreement is a
> thing agreeing with itself and produces no fidelity number (charter §8). There is no
> automated link to anything physical. The previous iteration called itself a digital twin
> while containing no hardware interface at all; this one says where it is.

Three things worth knowing before you read a number out of this system. The cell layout is
**engineered, not surveyed**, so a measurement taken from the model does not transfer to
the building until the Phase 3 scan. **Scenarios are not reproducible**: a passing run is
evidence about that run only — see
[`docs/architecture/cross-cutting-testing.md`](./docs/architecture/cross-cutting-testing.md).
And a grasp here holds a part's **position, not its orientation**, so nothing may be
asserted about how a part sits in the jaws — see
[`docs/measurements/`](./docs/measurements/README.md).

## Quick start

```bash
git clone https://github.com/mustafachill/Digital-Twin.git
cd Digital-Twin
./scripts/bootstrap      # Python tooling, container image, dependencies
./scripts/doctor         # what works on this machine, and what does not
./scripts/build          # build the ROS 2 workspace
./scripts/scenario program_cycle   # one cycle on the simulated plant, asserted; no hardware
# The pair drives the PHYSICAL arm as its counterpart and refuses without the opt-in:
# read docs/operations/bring-up.md (Physical cell) first.
# CITE_ALLOW_HARDWARE=1 ./scripts/program --headless --speed-scale 0.1
./scripts/scenario program_cycle   # the check: one cycle on the plant side, asserted
```

A windowed run needs an X display (`DISPLAY` set) on a Linux host; use `--headless`
elsewhere. `./scripts/program` refuses to start while a container of another checkout is
running on the host, because it would share that checkout's ROS domain.

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

This is the target stack. **L4 and the `Detect` skill are not in the main tree today**: they
were removed with the event-driven line
([ADR-0069](./docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)) and run in
milestone 01. Each layer's document says what is built.

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
[ADR-0016](./docs/adr/0016-iso-23247-alignment.md) and the
[standards reference](./docs/reference/standards.md). We are aligned with it;
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
| `./scripts/sim [--zone <name>] [--headless] [--pair]` | Launch the simulated cell. The model declares one zone, `cell_b`, the one-arm cell, so `--zone` may be left out; it is required again whenever the model declares more than one ([ADR-0069](./docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) decision 5). `--pair` brings up both sides of a twin pair and needs a zone that declares one — `cell_b` does. |
| `./scripts/scenario [name] [--zone <name>]` | Run a headless scenario; no argument lists them. There are two, `bringup` and `program_cycle`, both on `cell_b`. |
| `./scripts/program [--headless] [--cycles N] [--speed-scale S]` | Bring up both sides of the paired zone — the counterpart is the physical arm, behind `CITE_ALLOW_HARDWARE=1` and an explicit `--speed-scale` — and run the real program once per cycle through the twin boundary. A demonstration: it asserts nothing; `program_cycle` is the check. |
| `./scripts/hulls [--write]` | Check, or re-derive, the convex-hull collision meshes L0 declares. |
| `./scripts/audit-deps [--image]` | Scan dependencies for known vulnerabilities. |
| `./scripts/fetch-assets` | Download large assets declared in the manifest. |
| `./scripts/enter [dev\|gui\|hardware] [command...]` | Interactive shell in the container; with a trailing command, runs it there and exits. |
| `./scripts/clean [--all]` | Remove build artifacts. |
| `projects/<name>/run` | Run a frozen milestone snapshot from its own folder; see [`projects/`](./projects/README.md). |

Quality gate before any handoff:

```bash
./scripts/lint && ./scripts/build && ./scripts/test
```

## How we work

The rules are in [`CLAUDE.md`](./CLAUDE.md); the reasoning behind each one is in
[`docs/adr/`](./docs/adr/README.md). Three things are worth knowing before you read code:

- **Decisions are recorded before they are implemented.** Every locked technology and
  boundary choice has an ADR, each stating what it costs as well as what it buys.
  `./scripts/doctor`'s `ADR index` line counts them; run it rather than trusting a figure
  written down anywhere. Superseded and corrected records are kept in place rather than
  deleted, and are listed as such in [`docs/adr/README.md`](./docs/adr/README.md).
- **Documentation is a contract, not a description.** Layer documents carry a status
  marker — `DESIGNED`, `PARTIAL`, or `BUILT` — so a specification is never mistaken for
  something that exists.
- **Review is partly automated.** A roster of specialist agents runs against changes,
  including two written for this domain: one that validates the facility model and its
  generated artifacts (inertia tensors, collision geometry, interface matching), and one that
  audits every code path capable of moving a robot. The roster and its dispatch rules live in
  `.claude/`, which is local tooling and is not distributed with the repository — **so nothing
  here about it is checkable from a clone**, and this paragraph deliberately states no count.

Some standing prohibitions, so they are not a surprise in review: no hand-edited generated
artifacts, no structured data in a `std_msgs/String`, no `sleep` used to sequence startup,
no third-party source copied into the tree, and nothing marked complete without a test.

## Documentation

| Question | Go to |
|---|---|
| What are we building, why, and how did we get here? | [`what-we-are-doing.md`](./what-we-are-doing.md) — the charter |
| What rules apply to my change? | [`CLAUDE.md`](./CLAUDE.md) |
| How do I get set up? | [`docs/onboarding/getting-started.md`](./docs/onboarding/getting-started.md) |
| Why was *X* chosen over *Y*? | [`docs/adr/`](./docs/adr/README.md) |
| How does layer *N* work? | [`docs/architecture/`](./docs/architecture/README.md) |
| What shape is this interface? | [`docs/interfaces/`](./docs/interfaces/README.md) |
| How do I bring up or recover the cell? | [`docs/operations/`](./docs/operations/README.md) |
| What number backs that claim? | [`docs/measurements/`](./docs/measurements/README.md) |
| Where do I read more? | [`docs/reference/`](./docs/reference/README.md) |
| What does this term mean here? | [`docs/onboarding/glossary.md`](./docs/onboarding/glossary.md) |
| How do I run an earlier milestone? | [`projects/`](./projects/README.md) |

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
what-we-are-doing.md   the charter — what we are building, why, and how we got here
CLAUDE.md              the rulebook — how to work here
model/                 L0: the facility model — the single source of truth
workspace/src/         the ROS 2 workspace — first-party packages and imported sources
tools/                 host-agnostic Python tooling — no ROS dependency
assets/                3D assets and the scan pipeline
infra/docker/          container image and compose services
external/              pinned third-party sources — never vendored
scripts/               one command per task
docs/                  architecture · ADRs · interfaces · operations · measurements · reference
projects/              frozen, runnable snapshots of earlier milestones — records, not sources
```

What is on disk, package by package, is
[`docs/architecture/repository-layout.md`](./docs/architecture/repository-layout.md);
the charter's [§7](./what-we-are-doing.md) describes the target structure.

## The iteration before this one

This is a rebuild. The project spent an extended R&D period first, which produced real
knowledge and a codebase that nobody could build from a clean clone. That tree was kept
under `legacy/` for the length of the rebuild and **deleted at the end of Phase 1**; it is
still in version control, so nothing is lost, but you will not find it in a checkout.

Two documents carry it forward, and between them they are the reason several of this
project's firmest rules exist:

- [ADR-0001](./docs/adr/0001-rebuild-rather-than-migrate.md) — why it was replaced rather
  than migrated.
- [`docs/reference/v1-lessons.md`](./docs/reference/v1-lessons.md) — what it cost to learn,
  written before the deletion and anchored to the code that proved each point. Six of its
  failures were rediscovered independently by this rebuild, which is the strongest evidence
  on the page that they are properties of the problem rather than of that tree.

## License

Apache-2.0 — see [`LICENSE`](./LICENSE).

Third-party dependencies are consumed, never vendored
([ADR-0008](./docs/adr/0008-external-dependencies-via-vcstool.md)), so this repository
distributes no code but its own.
