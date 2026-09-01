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

> **Today the rebuild is at L0.** The simulated cell comes up, its three arms move under
> the real control stack, and work-pieces have been carried the length of the line by
> sensor-driven handoffs. There is no hardware interface and no automated link to anything
> physical, so nothing here is measured against reality yet. See [Status](#status). Saying
> so plainly is a project rule, not modesty — the previous iteration called itself a digital
> twin while containing no hardware interface at all.

## Status

A capability is listed as working only when something proves it.

| | State | What proves it |
|---|---|---|
| Charter, architecture, ADRs | **Written** — one design document per layer, L0 to L7, and a decision record for every locked technology and boundary choice | `./scripts/doctor`'s `ADR index` line counts the records — **51, all indexed**, in this checkout on 2026-09-01 — and its `ADR references` and `status markers` lines check that every reference resolves and every design document declares a marker. `ls docs/architecture/L[0-7]-*.md` returns 8. **Run `doctor` rather than reading the ADR figure here; it moves whenever a decision is recorded.** `ls docs/adr/[0-9]*.md` returns one more, because the glob also matches the template |
| Environment, dependencies, CI | **Working** — one command from clone to a built container | `./scripts/doctor` exits 0 — `22 passed, 0 failed, 4 skipped` in this checkout on 2026-09-01, the skips being the vendor source `./scripts/bootstrap` imports. **`doctor` does not build the image**: CI builds it on every run (`.github/workflows/ci.yml`), and the clone-to-green walk that exercised the whole path by hand is recorded in [CLAUDE.md §2](./CLAUDE.md) |
| Supply-chain and CVE scanning | **Working** — `./scripts/audit-deps` found no known vulnerabilities in the Python tooling layer on 2026-09-01. **A scan answers for the day it runs, not for the commit** | `./scripts/audit-deps`. It scans the two host requirement files only: not the ROS packages, not the pinned external sources, and not the container's OS packages unless given `--image`. It says so itself |
| L0 facility model and generators | **Working** — the whole cell is declared in `model/`, and every derived artifact is generated from it byte-identically | `./scripts/validate-model`, which exits 0 and prints the cardinality — **ask it for the numbers; they are deliberately not written out here**. The host suite in `tools/tests/` |
| Typed interfaces | **Working** — frozen against a stored baseline; the count is in [`docs/interfaces/README.md`](./docs/interfaces/README.md) | Contract test in `cite_interfaces`, against `test/interfaces.baseline` |
| Simulated cell bring-up | **Working, but not on every run** — 3 arms, 9 controllers, MoveIt and the planning scene per arm. The scenario has failed its own `MoveTo` assertion on developer machines; a failure there is a finding to investigate, not a flake to re-run past | `./scripts/scenario bringup`, a blocking CI gate run twice per CI run (`.github/workflows/ci.yml`). The arm and controller counts are in the generated plan, `workspace/src/cite_generated/bringup/cell_a_plan.yaml`; the pass record and its qualifications are in [CLAUDE.md §2](./CLAUDE.md) |
| L3 skills | **Partial** — all 6 have a server; `Transfer` has never been run against the simulator, because nothing calls it | Five servers in `cite_skills/src/skill_server.cpp` and one in `detection_server.cpp`; `MoveTo`, `Pick`, `Place`, `Grasp`, `Detect` asserted in scenarios; `Transfer` by unit test only |
| Pick-and-place cycle, one arm | **Partial** — the cycle completes and a friction grasp holds the part; the scenario is a merge gate, but it is still not reproducible | `./scripts/scenario pick_and_place`, a blocking CI gate (`.github/workflows/ci.yml`) |
| Line orchestration from the topology | **Partial** — L4 builds the line from L0, owns handoff, recovery and the belt setpoint, and **no arm moves in any of its own tests** | Unit tests against the fake arm in `cite_orchestration/test/fake_arm.cpp`; motion is evidenced only by `./scripts/scenario continuous_line` |
| Grasping | **By friction, no simulation aid** — repeatable in position, **not in orientation** | [`docs/measurements/`](./docs/measurements/README.md) holds **8** published campaigns (`find docs/measurements -mindepth 1 -maxdepth 1 -type d \| wc -l`, 2026-09-01) — **not all of them are about grasping**; that directory's own README says which is which. Cite a campaign; the numbers are not copied here |
| Sensor-driven three-robot line | **Runs, not finished** — Phase 1.D. The beams are bridged to ROS, `Detect` reads them, L4 indexes the belts, and the milestone ladder has been reported complete. Not every piece completed every run, and no campaign measures it | `./scripts/scenario continuous_line`, run as `continue-on-error` in CI (`.github/workflows/ci.yml`); the qualified count is in [CLAUDE.md §2](./CLAUDE.md) |
| Twin pair, and the L5 boundary | **Mechanism only** — `./scripts/sim --pair` starts two sides under a process supervisor, and `cite_twin` holds the mode server, command routing and the divergence monitor. The shipped model declares `sides: single`, so `--pair` refuses on a clean checkout and nothing starts `cite_twin`; **no scenario and no CI step brings a pair up**; and every divergence sample the code can produce is invalid, because one of its terms has no instrument. Phase 2.A produces no fidelity number and closes no clause of the Phase 2 exit criterion (charter §8) | Package tests in `cite_bringup` and `cite_twin`, including a paired launch test that crosses a goal between two fake sides in two processes. A pair of real cells has come up three times, on one machine, by hand — [ADR-0047](./docs/adr/0047-two-independent-launches-joined-not-sequenced.md) and [CLAUDE.md §2](./CLAUDE.md). `grep -rn -- --pair tests .github` returns nothing |
| Physical hardware integration | Phase 2.B — no hardware path has been run | — |
| CITE facility 3D scan | Phase 3 | — |
| Data platform and operator HMI | Phase 4 | — |

Three things worth knowing before you read a number out of this system. The cell layout is
**engineered, not surveyed**, so a measurement taken from the model does not transfer to
the building until the Phase 3 scan. **Scenarios are not reproducible**: a passing run is
evidence about that run only — see
[`docs/architecture/cross-cutting-testing.md`](./docs/architecture/cross-cutting-testing.md).
And a grasp here holds a part's **position, not its orientation**, so nothing may be
asserted about how a part sits in the jaws. Two rotation figures are published for this cell
and they are different quantities — a roll between the pads and a yaw about the vertical.
Quote the axis with the number:
[`docs/measurements/`](./docs/measurements/README.md) has the table.

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
| `./scripts/sim [--headless] [--pair]` | Launch the simulated cell; `--pair` brings up both sides of a twin pair. |
| `./scripts/scenario [name]` | Run a headless scenario; no argument lists them. |
| `./scripts/audit-deps [--image]` | Scan dependencies for known vulnerabilities. |
| `./scripts/fetch-assets` | Download large assets declared in the manifest. |
| `./scripts/enter [dev\|gui\|hardware] [command...]` | Interactive shell in the container; with a trailing command, runs it there and exits. |
| `./scripts/clean [--all]` | Remove build artifacts. |

Quality gate before any handoff:

```bash
./scripts/lint && ./scripts/build && ./scripts/test
```

## How we work

The rules are in [`CLAUDE.md`](./CLAUDE.md); the reasoning behind each one is in
[`docs/adr/`](./docs/adr/README.md). Three things are worth knowing before you read code:

- **Decisions are recorded before they are implemented.** Every locked technology and
  boundary choice has an ADR, each stating what it costs as well as what it buys. The count
  is in the status table above, beside the command that produces it. One record has been
  superseded on the evidence of a measurement campaign and is kept in place rather than
  deleted; several more carry dated corrections, which are listed with the record in
  [`docs/adr/README.md`](./docs/adr/README.md).
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
| What are we building, and why? | [`what-we-are-doing.md`](./what-we-are-doing.md) — the charter |
| What rules apply to my change? | [`CLAUDE.md`](./CLAUDE.md) |
| How do I get set up? | [`docs/onboarding/getting-started.md`](./docs/onboarding/getting-started.md) |
| Why was *X* chosen over *Y*? | [`docs/adr/`](./docs/adr/README.md) |
| How does layer *N* work? | [`docs/architecture/`](./docs/architecture/README.md) |
| What shape is this interface? | [`docs/interfaces/`](./docs/interfaces/README.md) |
| How do I bring up or calibrate the cell? | [`docs/operations/`](./docs/operations/README.md) |
| What number backs that claim? | [`docs/measurements/`](./docs/measurements/README.md) |
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
model/                 L0: the facility model — the single source of truth
workspace/src/         the ROS 2 workspace — first-party packages and imported sources
tools/                 host-agnostic Python tooling — no ROS dependency
assets/                3D assets and the scan pipeline
infra/docker/          container image and compose services
external/              pinned third-party sources — never vendored
scripts/               one command per task
docs/                  architecture · ADRs · interfaces · operations · measurements · reference
```

The charter's [§7](./what-we-are-doing.md) describes the target structure in full.

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
