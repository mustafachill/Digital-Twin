# CLAUDE.md

Canonical working agreement for this repository. Auto-loaded into every session and every
subagent. **This file is the rulebook; `what-we-are-doing.md` is the reason.** When you
need to know *why* a rule exists, read the charter. When you need to know *what to do*,
this file is enough.

`AGENTS.md` points here. Do not duplicate this content anywhere else.

**This file is near read-only** (§12): it changes only by the project owner's decision, holds
no measurement, count or dated history, and new knowledge goes into its own file and is at most
referenced from here by path. Factual corrections that keep it true against the tree (§7
matching `scripts/`, a broken link) go through normal review; new content does not.

---

## 1. What this is

The **CITE Digital Twin** — a facility-scale digital twin of the Center for Innovation,
Technology and Entrepreneurship at Sam Houston State University, built on ROS 2 and
Gazebo, whose first instrument is an xArm 5 work cell on a linear track.

It is a *twin*, not a simulation: real hardware and the virtual model share one control
interface, and the system continuously measures how far the model is from reality.

**The main tree's current scope is one signal, two arms, the same code.** It is built so that
one command will drive one real xArm 5 and one virtual xArm 5 in Gazebo, both running the real
robot's own program with the arm on a linear track, as the two sides of the paired zone
`cell_b`. The counterpart is declared to be the physical arm and its side is built
([ADR-0070](docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)); one signal has run the
real program on both arms together (Phase 2.B, charter §8).

It is also a **rebuild**. A first iteration (v1) was archived under `legacy/` and deleted at
the end of Phase 1; it survives only in version control, and **its patterns are not
precedent** — do not reintroduce them. What it taught is
[`docs/reference/v1-lessons.md`](docs/reference/v1-lessons.md); why it was replaced rather
than migrated is [ADR-0001](docs/adr/0001-rebuild-rather-than-migrate.md); the debt that
forced the decision is charter §12.

Full charter — identity, scope, architecture rationale, roadmap: **`what-we-are-doing.md`**.

## 2. Current state — read this before assuming anything exists

The charter describes the target; the repository is partway there. Check before assuming.
Measurements whose subject left the main tree are in the `MEASUREMENTS.md` of the snapshot that
keeps it (via [`projects/README.md`](projects/README.md)); an older "CLAUDE.md §2" citation
names text that is `git show 960e6b4:CLAUDE.md`.

- **Phase 1 is closed** (charter §8; the evidence that closed it, and what that does not
  cover, is in snapshot 01's `MEASUREMENTS.md`, reached via [`projects/README.md`](projects/README.md)). **Phase 2.A
  is in progress**: the plant paired with a virtual counterpart, a second simulation of the same
  cell. It produces no fidelity number, since both sides run one model and one solver; 2.B
  replaces the counterpart with the physical cell.
- **L0 declares one zone, `cell_b`, paired** ([ADR-0059](docs/adr/0059-pair-cell-b-and-leave-cell-a-single.md)):
  one xArm 5 on a linear track, one belt, one pick table. `workspace/src/cite_generated/` is
  generated from it entirely and never hand-edited
  ([ADR-0021](docs/adr/0021-generated-artifacts-are-committed.md)).
- **The real robot's program drives both sides** through the twin boundary from one client
  ([ADR-0067](docs/adr/0067-the-real-program-drives-the-twin-on-a-track.md)): `./scripts/program`
  runs it on the pair, and `./scripts/scenario program_cycle` checks it on the plant.
- **`./scripts/sim --pair`** brings each side up on its own `ROS_DOMAIN_ID` and Gazebo
  partition, joins them on a readiness witness and starts the L5 twin boundary, `cite_twin`
  (ADR-0047, ADR-0050, ADR-0057). The physical counterpart's side starts from
  `hardware.launch.py`, and only with `CITE_ALLOW_HARDWARE=1` (ADR-0054, ADR-0070); without it
  the pair is refused. Lifecycle transitions are requested and confirmed (ADR-0058);
  Pilz plans, with OMPL only on a planning failure (ADR-0027); arms collide against derived
  convex hulls (ADR-0028).
- **CI gates** `lint`, `build`, `test`, and the scenarios `bringup` (twice) and `program_cycle`
  on `cell_b`, with `--teardown-advisory`: the cycle gates, the teardown is reported. **Read a
  scenario's verdict in the step log, never the step's conclusion.**
- **What the layer stack (§5, the target) has in the main tree today:** L4 has no package —
  the behaviour-tree line left with
  [ADR-0069](docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md), and the
  real program is driven from `cite_bringup.program` through the L5 boundary; L6 and L7 are
  not started.
- **Past milestones are frozen snapshots under [`projects/`](projects/README.md)**
  ([ADR-0068](docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md)); the three-arm
  line, `cell_a` and their scenarios left the main tree with
  [ADR-0069](docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md).

**What does not work yet, stated plainly:**

- **The physical cycle is demonstrated, not measured.** One signal has run the real program's
  full cycle on the physical xArm 5 and its twin together, supervised
  ([`docs/operations/bring-up.md`](docs/operations/bring-up.md), "First physical runs"); no
  fidelity number exists yet, and registration is not built. A physical plant on a paired zone
  is refused at validate time (ADR-0041 Decision 3).
- **Nothing automated brings a pair up**, so the twin boundary is held only by `cite_twin`'s own
  tests against fake sides (ADR-0057). `DivergenceMetrics.valid` is false by construction.
- **Runs are not deterministic**: the seed does not reach the physics solver, and
  `./scripts/sim` passes none.
- **ADR-0043's real-time requirement is not shown met**, and neither of ADR-0049's two
  thresholds is set. With the throttle lifted, a pair clears the 1.0 floor in
  [`2026-09-01-capacity-on-shipped-main`](docs/measurements/2026-09-01-capacity-on-shipped-main/ANALYSIS.md)
  (taken on the three-arm cell), with three qualifications: every figure is a lower bound, a
  bare floor cleared is not a margin, and every cell was idle at home pose. The recorded real-time factor holds only on about one CPU core
  ([`2026-08-29-real-time-factor-conditions`](docs/measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md)),
  and every scenario ceiling is wall clock.
- **The belts are open-loop**, and `Transfer`, `Pick` and `Place` have servers that no program
  calls. The rest is [`docs/open-work.md`](docs/open-work.md) and the architecture documents'
  status lines.
- **The layout is `PROVISIONAL`**: engineered, not surveyed, until the Phase 3 scan.

**Binding standing rules** (none is new: each is stated by the record it cites or was in this
file before):

- **An execution abort is classified before any recovery motion**
  ([ADR-0037](docs/adr/0037-classify-an-abort-before-any-recovery-motion.md)), and **a
  physical machine is never the plant of a paired zone** — it may only be the counterpart,
  refused otherwise at validate time (`physical-plant-on-paired-zone`;
  [ADR-0041](docs/adr/0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 3,
  [ADR-0070](docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md), which retired
  ADR-0048 clause 1). Both are binding: violating either is an `ESCALATE`, not a review finding.
- **Never widen a scenario ceiling, an execution tolerance or a teardown exemption to absorb a
  failure.** A scenario failure is a finding to investigate, not a flake to re-run past.

**How status is kept:**

- **Ask a command; do not quote a count.** `./scripts/validate-model`, `./scripts/doctor`,
  `./scripts/test` and `./scripts/lint` report the current figures; a count in prose names the
  command that reproduces it, or it is not written. Measure a figure; never derive it. A claim
  that something has never happened expires the moment it runs again.
- **Where a measurement goes.** Main tree: a campaign under
  [`docs/measurements/`](docs/measurements/README.md), thresholds written before the first
  trial — cite it, do not copy its numbers. A snapshot: its own `MEASUREMENTS.md`, with
  verification runs in its `PROVENANCE.md` ([`projects/README.md`](projects/README.md)).
  Never this file.
- **Read a document's status marker** (`DESIGNED`, `PARTIAL`, `BUILT`) before its body.

State this honestly in reports. Never claim a capability exists because the charter
describes it.

## 3. Hard rules

Violating any of these is a defect, regardless of how well the code otherwise works.
Charter §4 carries the full reasoning.

- **P1 — One source of truth.** The facility is described once, declaratively, in the L0
  model. Worlds, descriptions, controller configs, and launch graphs are *generated* from
  it. A value must never exist in two places.
- **P2 — Sim and real are interchangeable.** Code that commands the simulated cell
  commands the physical cell unmodified. Topic, action, controller, joint, and frame names
  are identical; only what serves those names differs — the loaded `ros2_control` hardware
  plugin, and an L2 adapter where a vendor serves an axis outside `ros2_control`
  ([ADR-0070](docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)). Breaking this is
  the highest-severity defect in the project.
- **P3 — Typed contracts, always.** Every interface is a versioned `.msg`/`.srv`/`.action`
  in an interface package. If a consumer cannot discover the shape with
  `ros2 interface show`, the interface does not exist.
- **P4 — Determinism over timing.** Startup, shutdown, and mode transitions are driven by
  lifecycle states and events. Never by sleeping for a guessed duration.
- **P5 — Configuration is data, code is mechanism.** Code encodes *how* things work, never
  *which* things exist.
- **P6 — Nothing is done until tested and reproducible.** Every capability ships with
  automated tests that run headlessly in CI.
- **P7 — Honest status.** Documentation states what the system does, not what was
  intended. A checkbox is ticked only when a test proves it.
- **P8 — The twin measures itself.** Any fidelity claim is backed by a published metric.
- **P9 — Plug in, plug out.** Robot types, end-effectors, sensors, and process modules are
  replaceable at their interface boundary. A new robot type must not touch orchestration.
- **P10 — Everything in English.** Code, comments, identifiers, configuration, commit
  messages, documentation, and agent reports. No exceptions.

## 4. Standing prohibitions — rejected in review, without discussion

- Hand-edited generated artifacts (world files, controller configs, launch graphs).
- `std_msgs/String` carrying structured data.
- `TimerAction` or `sleep` used to sequence startup.
- Third-party source copied into the tree instead of pinned in the vcs manifest.
- A capability marked complete in documentation without a test proving it.
- Any identifier, comment, or document not in English.
- A value that exists in two places.
- Copying code or values from `projects/` into the main tree — snapshots are records, not
  sources ([ADR-0068](docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md)).

## 5. Layer stack

```
L7 PRESENTATION        operator HMI, remote access                    (Phase 4)
L6 DATA & TELEMETRY    telemetry schema, recording, historian, replay (Phase 4)
L5 TWIN SYNC           mode control, mirroring, divergence metrics    (Phase 2)
L4 ORCHESTRATION       behaviour trees, line coordination, handoff
L3 CAPABILITY          MoveTo / Pick / Place / Transfer / Grasp / Detect
L2 CONTROL & HAL       ros2_control, controllers, MoveIt 2, hw interfaces
L1 DESCRIPTION         URDF/Xacro, SDF, meshes, generated worlds
L0 FACILITY MODEL      the single declarative source of truth
```

**A layer may depend only on layers below it.** An upward dependency is an architectural
defect and an `ESCALATE`, not a finding.

Each layer the main tree builds has a design document in
[`docs/architecture/`](docs/architecture/README.md) —
[L0](docs/architecture/L0-facility-model.md),
[L1](docs/architecture/L1-description-and-assets.md),
[L2](docs/architecture/L2-control-and-hal.md),
[L3](docs/architecture/L3-capabilities.md),
[L5](docs/architecture/L5-twin-synchronization.md). L4, L6 and L7 are in the target
architecture only (charter §5, §8) and have no document in `docs/`.

Cross-cutting: [safety and interlocks](docs/architecture/cross-cutting-safety.md),
[lifecycle management](docs/architecture/cross-cutting-lifecycle.md),
[testing](docs/architecture/cross-cutting-testing.md),
[naming](docs/architecture/naming-and-namespaces.md), diagnostics, configuration, CI/CD,
security.

The architecture is aligned with the ISO 23247 reference architecture for manufacturing
digital twins — charter §2 and [`docs/reference/standards.md`](docs/reference/standards.md).
The layer-by-layer mapping is not in `docs/` until L6/L7 are built
([ADR-0016](docs/adr/0016-iso-23247-alignment.md)'s 2026-10-02 amendment).

## 6. Technology baseline

Every row below has an ADR recording why it was chosen and what it costs — see
[`docs/adr/`](docs/adr/README.md). Changing any of them requires a new ADR.

| Concern | Choice |
|---|---|
| OS | Ubuntu 24.04 LTS (Noble) |
| Middleware | ROS 2 Jazzy Jalisco |
| Simulator | Gazebo Harmonic (LTS) — **not** Gazebo Classic, which is EOL |
| ROS↔Sim | `ros_gz_sim`, `ros_gz_bridge` |
| Control | `ros2_control` + `gz_ros2_control` |
| Motion planning | MoveIt 2 |
| Orchestration | BehaviorTree.CPP v4 + Groot2 |
| Robot support | `xarm_ros2`, pinned via manifest, local changes as patch files |
| Recording | `rosbag2` with MCAP storage |
| Visualization | RViz 2 (native debug), Foxglove (shareable) |
| Dependencies | `vcstool` manifest + `rosdep` — never vendored into the tree |
| Environment | Docker + devcontainer |
| Languages | C++ for real-time and control paths; Python for orchestration, tooling, generators |

## 7. Commands

Fixed entry points. Always invoke these rather than the underlying tool, so that changes
to the toolchain do not ripple through agent configurations and documentation.

| Command | Purpose |
|---|---|
| `./scripts/bootstrap` | Prepare or repair the environment. Idempotent. `--host-only` skips everything needing ROS. |
| `./scripts/doctor` | Diagnose the environment. Run first when something is wrong. |
| `./scripts/build` | Build the workspace |
| `./scripts/test` | Host tooling tests, then unit + integration + launch tests |
| `./scripts/lint` | Linters and type checks |
| `./scripts/format` | Apply formatting in place |
| `./scripts/sim [--zone <name>] [--headless] [--pair]` | Launch the simulated cell. **`--zone` defaults to the model's only zone and is required only when L0 declares more than one** (ADR-0069 decision 5, derived once in `cite_bringup/zones.py`); L0 declares one zone today, `cell_b`. Exactly one zone runs at a time. `--pair` brings both sides of a twin pair up under the pair supervisor and requires an L0 model that declares `twin: {sides: pair}`; both sides run in the one container the supervisor is started in, so one display passthrough serves both, and the two windows carry the same world name. A windowed run selects a GPU vendor library when the container has one, guarded on that library existing |
| `./scripts/validate-model` | L0 schema validation + generator dry-run. Runs anywhere. |
| `./scripts/hulls [--write]` | Check, or re-derive, the convex-hull collision meshes L0 declares (ADR-0028). Needs the imported vendor source, so unlike `validate-model` it does not run anywhere. |
| `./scripts/audit-deps` | Scan dependencies for known vulnerabilities. Read its header — it does not cover every layer. |
| `./scripts/scenario [name] [--zone <name>]` | Headless simulation-in-the-loop scenario; no argument lists them. `--zone` follows the same rule as `./scripts/sim`'s — the model's only zone by default, required when there are several (ADR-0069 decision 5) — through `tests/scenarios/_cell.py`, which asks `cite_bringup/zones.py`. The scenarios are `bringup` and `program_cycle` |
| `./scripts/program [--zone <name>] [--headless] [--cycles N] [--speed-scale S]` | Bring the twin pair up, start each side's belt on that side, put a box on each side's table and run the real xArm 5's program once through the twin boundary (ADR-0067): both arms and both tracks from one client. On a physical side (ADR-0070) it needs `CITE_ALLOW_HARDWARE=1` and an explicit `--speed-scale` in (0, 1], commands no belt, and asks the operator to place the part by hand before each cycle. `--zone` as for `./scripts/sim`. **A demonstration, not an instrument**: it gates nothing and is in no CI step; `./scripts/scenario program_cycle` is what checks it, on the plant |
| `./scripts/home [--zone <name>] [--speed-scale S]` | Against a pair that is ALREADY RUNNING (it attaches to that container and refuses when there is none; it restarts nothing): initializes each physical arm every time (`InitializeAsset`: track motor and gripper enabled, track homed if it has not found its zero, carriage brought to the program's start), then measures and brings both arms to the program's start through the twin only if a side is away (ADR-0070). `./scripts/program` does the same before its first cycle. On a physical side it needs `CITE_ALLOW_HARDWARE=1` and an explicit `--speed-scale` |
| `./scripts/enter [dev\|gui\|hardware] [command...]` | Interactive shell in the container; with a trailing command, runs it there and exits |
| `./scripts/fetch-assets` | Download large assets declared in `assets/manifest.yaml` |
| `./scripts/clean [--all]` | Remove build artifacts |
| `projects/<name>/run [--headless]` | Run a frozen milestone snapshot from its own folder, which is its own repository root with its own `./scripts/*` (ADR-0068). Not a main-tree command: nothing in the main tree calls it or builds from there. The three-arm, beam-triggered line runs as `projects/01-three-arm-event-driven-line/run`; [`projects/README.md`](projects/README.md) lists the others |

Quality gate before any handoff: `./scripts/lint && ./scripts/build && ./scripts/test`.

**Always invoke these rather than `colcon`, `docker`, or `ros2 launch` directly.** They
route to the right environment automatically: on a machine without ROS they re-execute
themselves inside the container, so the same command works from a macOS laptop and from
the Linux workstation. A command written directly against `colcon` works for its author
and for nobody else.

Dependencies are declared in four layers, each with exactly one correct home — see
`requirements/README.md`. In short: ROS and system packages in `package.xml` resolved by
`rosdep`; external ROS source pinned in `external/cite.repos`; host Python tooling in
`requirements/tools.txt`. Never install a ROS Python dependency with `pip`.

## 8. Naming

```
/cite/<zone>/<asset_id>/<interface>
```

Deterministic, generated from the L0 model, identical in simulation and on hardware.
Frame identifiers follow the same rule. No asset name is ever written by hand twice.

## 9. Definition of Done

A capability is done only when **all** hold. There is no partial credit.

1. Generated from or declared in the L0 model where applicable.
2. Interfaces are typed and live in an interface package.
3. Tested at the right level — unit, integration (`launch_testing`), simulation-in-the-loop
   scenario, and interface-contract regression — and passing in CI.
4. Runs headlessly in CI on a clean container with no manual step.
5. Works identically in simulation and on hardware, or its hardware path is explicitly
   marked unimplemented.
6. Documented: what it does, its interfaces, how to run it, how it fails.
7. Reviewed by a human and by the relevant review agents.
8. Startup and shutdown are event-driven, containing no timing guesses.

## 10. ROS 2 practice notes

Recurring failure classes in this domain. Treat each as a review checkpoint.

- **QoS**: declare profiles explicitly. Incompatible publisher/subscriber QoS connects
  silently and delivers nothing — the most common silent failure in ROS 2. **Compatible QoS
  is not delivery either:** reliable is a promise to *matched* subscribers, so anything
  published in the same callback that created the publisher reaches nobody. That cost this
  project a belt setpoint that was never once delivered. Treat a match as an event, never a
  sleep or a publish loop — see
  [`docs/interfaces/qos-profiles.md`](docs/interfaces/qos-profiles.md).
- **Gazebo transport is a second namespace, and `ROS_DOMAIN_ID` does not touch it.** Every
  process that speaks it — `gz sim`, `parameter_bridge`, `ros_gz_sim create`, every `gz`
  probe — must carry the `GZ_PARTITION` the generated plan names, and one that does not
  discovers a world that is not there. It does not fail loudly: `gz model --list` against no
  world **exits 0**. Start such a process through `cite_bringup/gz.py` and nothing else; a
  guard under `tests/scenarios/guards/` enforces that for `tests/`. ADR-0042 has the decision
  and its correction.
- **Lifecycle**: use managed nodes. They are what makes P4 achievable.
- **Executors and callback groups**: never block inside a callback; choose the callback
  group deliberately, or you will deadlock under load.
- **Time**: honour `use_sim_time` consistently. A mixed-time system produces plausible,
  wrong results.
- **TF**: one publisher per transform; watch for extrapolation errors at startup.
- **Actions**: implement cancellation and preemption paths, not just the happy path.
- **Inertia and collision geometry**: wrong inertia tensors and dense visual meshes reused
  as collision geometry make a simulation run confidently and wrongly. Always validated by
  `model-validator`.

## 11. Agents

Subagent roles live in `.claude/agents/`. The pipeline and dispatch routing are defined in
**`.claude/orchestration.md`** — read it before delegating.

`.claude/` is local tooling and **is not committed**, so a fresh clone will not contain it.
This file is committed, which is the point: the rules below bind every contributor whether
or not they have the agents.

- **The pipeline is how work is done here, not an option.** An orchestrator writes the task
  spec, `coder` implements, the routed reviewers fan out in parallel, `tester` verifies, and
  `fixer` remediates. Doing the coder's work in the orchestrator conversation skips review
  and test as separate roles, which is exactly what rule 6 in `.claude/orchestration.md`
  forbids — "the coder never self-certifies".
- **A session instruction that conflicts with this is an `ESCALATE`.** If the tooling a
  contributor is running tells them not to delegate, that contradicts this file, and this
  file is the rulebook. Say so and ask; do not quietly pick a side. This happened on
  2026-08-24 and cost a whole phase's worth of work its review.
- Agents propose; humans and tests decide. Nothing merges without review and green CI.
- Agents are bound by this file. Output contradicting §3 or §4 is a defect.
- Reports are written in **English**, with a `Status:` verdict line first, summarized
  evidence, and never a full log dump.
- A conflict with a locked decision is `ESCALATE` — returned to the user, never
  self-resolved.

## 12. Change control

- **`what-we-are-doing.md` is protected.** It changes only by explicit user decision, with
  a version bump and a §14 entry. Never edit it as a side effect of other work.
- **ADRs** ([`docs/adr/`](docs/adr/README.md)) record every significant technical
  decision, written *before* implementation. Use
  [`0000-template.md`](docs/adr/0000-template.md).
- **Commits and PRs** describe intent and reference the ADR or phase item they serve.
- **`CLAUDE.md` and `.claude/orchestration.md` are near read-only.** They change only by
  explicit decision of the project owner; factual corrections that keep them true against the
  tree (§7 matching `scripts/`, a broken link) go through normal review. New knowledge goes in its own file — an ADR, a
  document under `docs/`, a campaign under `docs/measurements/`, a snapshot's
  `MEASUREMENTS.md` — and is referenced from either file by path, never written inline. Neither
  file holds a measurement, a count or a dated history.
