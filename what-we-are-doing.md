# What We Are Doing

**The CITE Digital Twin — project charter, architecture doctrine, and roadmap.**

| | |
|---|---|
| **Owner** | Center for Innovation, Technology and Entrepreneurship (CITE), Sam Houston State University |
| **Document version** | 1.11 |
| **Date** | 2026-08-31 |
| **Status** | Active — this is the authoritative source of truth |

---

## 0. How to read and maintain this document

**This document answers three questions and nothing else:** *What are we building? Why is it built this way? Where are we in that plan?*

- **It is the entry point.** Anyone joining the project — a new student, a new engineer, an AI agent, a stakeholder — reads this first. If something about the project's direction is not answered here, this document has a gap and the gap is a bug.
- **It is deliberately stable.** It describes intent, architecture, and phases. It does not describe today's build errors, this week's tickets, or API signatures. Those live elsewhere (§11).
- **It changes only by decision, never by drift.** Every edit must correspond to a real decision about the project's direction, must bump the version number, and must be recorded in §14. Small factual corrections are exempt from the version bump but not from being correct.
- **Everything else in the repository must agree with this document.** Where code, configuration, or another document contradicts this one, this one is right and the other is wrong — either the other artifact gets fixed, or a decision is made and recorded here first.

---

## 1. What the CITE Digital Twin is

The CITE Digital Twin is a **facility-scale digital twin of the Center for Innovation, Technology and Entrepreneurship**, built on ROS 2 and Gazebo, whose first and deepest instrument is a **multi-robot robotic work cell** built around UFACTORY xArm manipulators.

It is three things at once, and it must be all three to be worth building:

1. **A living virtual replica of a real place.** CITE's physical space is 3D-scanned and reconstructed to scale inside the simulator. The virtual facility is not decoration; it is dimensionally faithful to the building the robots actually stand in.

2. **A bidirectionally coupled twin of real hardware.** Real xArm arms and the virtual arms share one control interface. State flows from physical to virtual continuously. Behaviour developed and validated in the virtual cell deploys to the physical cell without rewriting it.

3. **A modular platform, not a one-off demo.** Robots, end-effectors, sensors, and process stations are plug-in components declared in configuration. Adding a robot type, swapping a gripper, or re-arranging the line is a configuration change, not a code change.

### 1.1 Why this exists

A simulation shows what a system *could* do. A digital twin shows what the real system *is* doing, *will* do, and *how far off* our model of it is. The value CITE gets from this project is the third item: a measured, auditable relationship between a physical facility and its model, and a safe place to change the physical facility before touching it.

### 1.2 What it is not

- Not a rendering or a video. Visual fidelity serves measurement and communication; it is never the goal by itself.
- Not a single-purpose pick-and-place demo. The pick-and-place line is the first workload, chosen because it exercises every layer of the architecture.
- Not a research prototype that only runs on one person's laptop. Reproducibility is a hard requirement, not an aspiration.

---

## 2. Twin maturity model

"Digital twin" is used loosely in industry. This project uses a precise, staged definition. Every claim we make about the system must name its level.

| Level | Name | Data flow | What it proves |
|---|---|---|---|
| **L0** | Virtual model | none | The model exists and behaves plausibly. A simulation. |
| **L1** | Shadow | real → virtual | The virtual asset reflects the physical asset's live state. Observation and recording. |
| **L2** | Validated | real → virtual, commands → both | The model is *accurate*. Divergence between prediction and reality is continuously measured and reported. |
| **L3** | Closed loop | virtual → real | The twin is *trusted*. Behaviour is validated in simulation and then commands the physical system. |
| **L4** | Predictive | virtual runs ahead of real | The twin is *useful for decisions*. What-if scenarios, bottleneck and collision prediction, optimization fed back to operations. |

**Our commitment: reach L2 with rigor, then L3, and architect from day one so that L4 requires no re-foundation.** A system that reaches L2 honestly is more valuable than one that claims L4 and cannot show its error metrics.

The prior iteration of this project (see §12) reached L0. This is the gap the rebuild closes.

**A mode is not a level, and L3 is where the two come apart.** §5's L5 operating modes say where commands *enter and land*; the levels above say where information *flows from*, and — for L3 — **what has to happen before it does**. The L3 row above is not satisfied by the direction alone: it reads *"Behaviour is validated in simulation and then commands the physical system"*, and the validation is not decoration, it is the level. `VIRTUAL_LEAD` (ADR-0041; ADR-0011's 2026-08-29 amendment) carries that direction with **no** such gate, so it is not L3 and nothing may cite it as L3 — and in Phase 2.A there is no physical side for the direction to reach at all, so the level there is L0 whichever mode is in force. **This paragraph is what the mode's maturity argument rests on**, together with `docs/architecture/L5-twin-synchronization.md`'s mode table, which carries the gate in the same way; ADR-0011's own level table gives the flow and not the gate, and does not close it. The first five modes each coincided with a level closely enough that the distinction never had to be written down. It does now.

These levels are deliberately aligned with the established literature rather than invented: L0 and L1 correspond to Kritzinger's *digital model* and *digital shadow*, and L3 onward to a full *digital twin* with automated bidirectional flow. L2 is our own refinement — a digital shadow that additionally proves its own accuracy — because a shadow whose error nobody measures is an assertion rather than a twin. The architecture is aligned with the ISO 23247 reference architecture for manufacturing digital twins; see `docs/architecture/standards-alignment.md` for the full mapping and `docs/reference/` for sources.

---

## 3. Scope

### 3.1 In scope

| Domain | Included |
|---|---|
| **Facility** | The CITE center, 3D-scanned, dimensionally accurate, spatially registered to real-world coordinates. Multiple cells/zones supported. |
| **Robots** | UFACTORY xArm 5 as the reference platform. Architecture is robot-agnostic: xArm 6/7, and other manipulators, are configuration entries. |
| **End-effectors** | Parallel grippers as reference. Vacuum, tooling, and sensor mounts are pluggable. |
| **Sensors** | Break-beam, proximity, RGB-D cameras, joint/force feedback. Sim and real expose identical interfaces. |
| **Process modules** | Conveyors, feeders, buffers, inspection and accumulation stations. Line topology is declarative. |
| **Control** | `ros2_control`-based, identical stack for simulated and physical hardware. MoveIt 2 for motion planning. |
| **Orchestration** | Behaviour-tree driven task and line coordination, including inter-robot handoff. |
| **Twin synchronization** | Mode-switched bridge (`SIM` / `REAL` / `SHADOW` / `VALIDATED` / `CLOSED_LOOP` / `VIRTUAL_LEAD`) plus continuous divergence measurement. |
| **Data** | Structured telemetry, deterministic recording and replay, historian. |
| **Presentation** | Web-based operator HMI and remote access. *Phase 4 delivery — but every interface below it is designed now to be consumable from a browser.* |

### 3.2 Out of scope (explicitly)

- Manufacturing execution (MES), ERP, and scheduling systems. We define the integration boundary; we do not build them.
- Safety certification of the physical cell. We implement software interlocks and E-stop handling; certified functional safety is a hardware and process matter outside this repository.
- Human digital twins, ergonomic simulation, or crowd simulation.
- Autonomous mobile robots and fleet navigation. The architecture must not preclude them; we are not building them.

### 3.3 Deferred, with interfaces reserved now

These are not built in the near phases, but the architecture is required to accommodate them without rework:

- **Industrial protocol bridges** (OPC-UA, MQTT) for PLC/SCADA integration.
- **Cloud deployment and multi-tenant remote access.**
- **Learning-based components** (synthetic data generation, learned policies, vision models).

---

## 4. Engineering principles

These are non-negotiable. They exist because the previous iteration failed on each of them, and every one of these failures is traceable to a missing principle rather than a missing feature.

### P1 — One source of truth
The facility is described **once**, declaratively, in a schema-validated model. World files, robot descriptions, controller configurations, launch graphs, and dashboard topology are **generated** from it. No hand-edited world file. No value that exists in two places.

### P2 — Simulation and reality are interchangeable
A node that commands the simulated cell commands the physical cell **without modification**. Topic names, action names, controller names, joint names, and frame names are identical. The only thing that changes is which hardware plugin `ros2_control` loads. If this ever stops being true, it is a defect of the highest severity.

### P3 — Typed contracts, always
Every interface between components is a versioned ROS 2 message, service, or action defined in an interface package. Never a stringified dictionary in a `std_msgs/String`. If a consumer cannot discover the shape of the data with `ros2 interface show`, the interface does not exist.

### P4 — Determinism over timing
System startup, shutdown, and mode transitions are driven by **lifecycle states and events**, never by sleeping for a guessed number of seconds. A launch file that works only because a machine is fast enough is broken.

### P5 — Configuration is data, code is mechanism
Adding a robot, changing a layout, or re-ordering a line is a data change. Code encodes *how* things work, never *which* things exist.

### P6 — Nothing is done until it is tested and reproducible
"Works on my machine" is not a state this project recognizes. Every capability ships with automated tests, and every capability is exercised headlessly in CI. See §9.

### P7 — Honest status
Documentation states what the system does, not what it was intended to do. A checkbox is marked complete only when a test proves it. Overstated status in documentation is treated as a defect and fixed like one.

### P8 — The twin measures itself
Any claim of fidelity is backed by a published metric. The system continuously reports how far the model is from reality, and that number is visible, recorded, and trended.

### P9 — Plug in, plug out
Every component category in §3.1 is replaceable at its interface boundary. A new robot type must not require touching the orchestration layer. A new station must not require touching the robot layer.

### P10 — Everything in English
All code, comments, identifiers, configuration, commit messages, and documentation are written in English, without exception. CITE is an international academic institution and this repository is a shared professional artifact.

---

## 5. Target architecture

The system is a strict layer stack. **Each layer may depend only on the layers below it.** Any upward dependency is an architectural defect.

```
┌───────────────────────────────────────────────────────────────────────────┐
│  L7  PRESENTATION            Operator HMI · remote access · reporting     │
├───────────────────────────────────────────────────────────────────────────┤
│  L6  DATA & TELEMETRY        Telemetry schema · recording · historian ·   │
│                              replay · external protocol bridges           │
├───────────────────────────────────────────────────────────────────────────┤
│  L5  TWIN SYNCHRONIZATION    Mode control · state mirroring · command     │
│                              routing · divergence measurement · calib.    │
├───────────────────────────────────────────────────────────────────────────┤
│  L4  ORCHESTRATION           Line coordinator · behaviour trees · task    │
│                              scheduling · handoff protocol · recovery     │
├───────────────────────────────────────────────────────────────────────────┤
│  L3  CAPABILITY (SKILLS)     MoveTo · Pick · Place · Transfer · Grasp ·   │
│                              Detect  — robot-agnostic action interfaces   │
├───────────────────────────────────────────────────────────────────────────┤
│  L2  CONTROL & HAL           ros2_control · controllers · MoveIt 2 ·      │
│                              hardware interfaces (sim plugin | real arm)  │
├───────────────────────────────────────────────────────────────────────────┤
│  L1  DESCRIPTION & ASSETS    URDF/Xacro · SDF · meshes · materials ·      │
│                              scanned geometry · generated worlds          │
├───────────────────────────────────────────────────────────────────────────┤
│  L0  FACILITY MODEL          The single declarative source of truth:      │
│                              assets · layout · topology · capabilities    │
└───────────────────────────────────────────────────────────────────────────┘
     Cross-cutting: safety & interlocks · diagnostics & health · lifecycle
                    management · configuration · testing · CI/CD · security
```

### L0 — Facility model

A schema-validated declarative description of everything that exists: the facility and its zones, every asset instance (robots, end-effectors, sensors, stations, fixtures), their poses, their types, and the process topology connecting them.

This layer has **no runtime behaviour**. It is data plus a validator plus generators. It is the answer to the configuration drift that made the previous iteration unmaintainable: there is exactly one place where "where is belt 2" is written down.

Generators consume it to emit: simulation world files, per-robot descriptions, controller parameter files, launch graphs, orchestration topology, and the topic/frame naming plan.

### L1 — Description and assets

Robot and component geometry, kinematics, dynamics, and appearance. Component libraries are versioned and reusable: a robot type or a gripper is defined once and instantiated many times with a prefix.

The 3D-scan pipeline lives here: raw capture → cleanup → decimation → separate visual and collision representations → material authoring → simulator-ready assets. Visual meshes may be dense; collision meshes are always simplified primitives or convex hulls. Scanned geometry is registered to the same coordinate frame as the engineered assets.

### L2 — Control and hardware abstraction

`ros2_control` is the hardware abstraction boundary. Controllers, joint names, and command/state interfaces are identical between simulation and hardware; only the loaded hardware plugin differs. MoveIt 2 provides kinematics, planning, and collision checking against a scene derived from L0/L1.

**This layer is where P2 is enforced.** It is the single most important layer in the system, because it is what separates a digital twin from a simulation.

### L3 — Capability (skills)

Robot-agnostic actions with stable, typed interfaces: move to a pose, pick an object, place an object, transfer to a peer, actuate an end-effector, detect an object. A skill accepts a goal, reports progress, returns a structured result, and can be cancelled and recovered.

Skills are the vocabulary the orchestration layer speaks. Because they are robot-agnostic, swapping an xArm 5 for an xArm 7 or a different manufacturer's arm changes nothing above this line.

### L4 — Orchestration

Process logic expressed as **behaviour trees**, not hand-rolled state machines. Behaviour trees are the current industry standard for robot task orchestration because they compose, they are inspectable at runtime, they make recovery and fallback explicit, and they can be edited and visualized without recompiling.

The line coordinator owns: work-piece tracking, station sequencing, inter-robot handoff negotiation, buffer and resource arbitration, throughput accounting, and fault recovery. Its topology comes from L0; its behaviour comes from trees; its actions come from L3.

### L5 — Twin synchronization

The layer that makes this a twin. It owns the **operating mode** of the system:

| Mode | Behaviour |
|---|---|
| `SIM` | Virtual cell only. Development and regression testing. |
| `REAL` | Physical cell only. Virtual model idle. |
| `SHADOW` | Physical state continuously drives the virtual model. (L1) |
| `VALIDATED` | Commands go to both; divergence is measured and published, virtual output does not actuate. (L2) |
| `CLOSED_LOOP` | Virtual validation gates physical execution. (L3) |
| `VIRTUAL_LEAD` | The virtual side is commanded; the far side follows and actuates. No validation gate — that is `CLOSED_LOOP` — and no reverse mirror — that is `SHADOW`. Not a maturity level. (ADR-0041) |

It also owns **calibration and registration** — the correspondence between the real cell's coordinate frame and the model's — and the **twin monitor**, which continuously publishes fidelity metrics: joint-space error, tool-centre-point pose error, cycle-time deviation, and event-timing deviation.

### L6 — Data and telemetry

A defined telemetry schema, deterministic recording of every run, a time-series historian for trend and post-hoc analysis, and replay of recorded runs into the simulator. The external integration boundary (OPC-UA, MQTT) is defined here and implemented when Phase 4/deferred work is scheduled.

### L7 — Presentation

Browser-based operator HMI: live cell state, robot status, throughput and cycle-time KPIs, alarm and event stream, twin divergence trends, and historical playback. Remote access for stakeholders outside CITE.

**Design constraint applied from Phase 1, delivered in Phase 4:** every piece of state that the HMI will need must be available over a versioned, transport-agnostic gateway, not only over native ROS 2 transport. This is why P3 is non-negotiable — a stringified dictionary cannot be rendered in a browser.

### Cross-cutting concerns

- **Safety and interlocks** — E-stop propagation, workspace limits, speed and separation monitoring, and a hard rule that no command reaches physical hardware without passing the safety layer.
- **Diagnostics and health** — every node reports structured health; the system has one aggregated view of whether it is well.
- **Lifecycle management** — managed nodes with deterministic configure/activate/deactivate/cleanup, which is what makes P4 achievable.
- **Testing and CI/CD** — see §9.
- **Security** — credentials, network segmentation between the robot network and the general network, and access control for remote features.

---

## 6. Technology baseline

Every choice below is a decision, not a default. Changing any of them requires an Architecture Decision Record (§11).

| Concern | Choice | Rationale |
|---|---|---|
| OS | **Ubuntu 24.04 LTS (Noble)** | Tier-1 platform for the chosen ROS 2 release; supported through 2029. |
| Middleware | **ROS 2 Jazzy Jalisco** | Current LTS, supported to May 2029. First-class pairing with the chosen simulator. |
| Simulator | **Gazebo Harmonic (LTS)** | Supported to May 2029, the same month as Jazzy. Gazebo Classic reached end of life in January 2025 and receives no fixes — building a multi-year institutional platform on it is not defensible. |
| ROS↔Sim bridge | **`ros_gz` (`ros_gz_sim`, `ros_gz_bridge`)** | The supported integration path for Jazzy + Harmonic. |
| Control framework | **`ros2_control` + `gz_ros2_control`** | The mechanism that makes P2 possible: one controller stack, two hardware backends. |
| Motion planning | **MoveIt 2** | Standard for manipulator planning; provides the collision-aware planning that skills depend on. |
| Task orchestration | **Behaviour trees (BehaviorTree.CPP v4 + Groot2)** | Composable, inspectable, recoverable, editable without recompiling. The alternative — bespoke state machines — is what failed in the previous iteration. |
| Robot support | **`xarm_ros2`, pinned and vendored via manifest** | Vendor-supported xArm integration for both simulated and physical arms. Consumed as a pinned external dependency with any local patches maintained as reviewable patch files — never copied into the tree. |
| Interfaces | **Dedicated ROS 2 interface packages** | Typed contracts per P3. |
| Recording | **`rosbag2` with MCAP storage** | Efficient, standard, replayable, and readable by external tooling. |
| Visualization/debug | **RViz 2 and Foxglove** | RViz for ROS-native debugging; Foxglove for shareable, browser-based inspection and as a stepping stone to L7. |
| Dependency management | **`vcstool` manifest + `rosdep`** | External sources are declared and pinned, never vendored into the tree. |
| Environment | **Docker + devcontainer, with GPU passthrough** | A new team member gets an identical, working environment in one command. |
| CI | **GitHub Actions, headless simulation** | Every change is built and tested automatically. |
| Languages | **C++ for real-time and control paths; Python for orchestration, tooling, and generators** | Standard division of labour in production ROS 2 systems. |

### 6.1 Known migration work created by this baseline

These are consequences of the baseline, identified now so they are planned rather than discovered:

1. **The conveyor plugin must be rewritten.** The IFRA conveyor plugin used previously is a Gazebo Classic plugin and will not load in Harmonic. It becomes a first-party Gazebo Sim system plugin with a typed ROS 2 interface.
2. **xArm Jazzy/Harmonic support must be verified early.** The vendor's ROS 2 support for the target release combination is a Phase 1.A verification gate, not an assumption. If gaps exist, they are found in week one, not month three.
3. **All sensor plugins must be re-specified** against Gazebo Sim's sensor system and `ros_gz_bridge`.
4. **World and model formats must be regenerated**, not ported — which is consistent with P1, since they become generated artifacts.

---

## 7. Repository structure

The repository is a monorepo. It contains the ROS 2 workspace, the facility model, the asset pipeline, infrastructure, and documentation, because these must version together.

**This tree describes the target structure, not today's snapshot.** Entries are marked
where they do not yet exist, or will not exist for long. Directories that carry no marker
exist now.

```
Digital-Twin/
├── what-we-are-doing.md          the charter — what we are building and why
├── CLAUDE.md                     the rulebook — how to work here
├── AGENTS.md                     vendor-neutral pointer to CLAUDE.md
├── CONTRIBUTING.md               human contribution workflow
├── README.md                     orientation and quick start; points here
├── LICENSE                       Apache-2.0
│
├── model/                        ← L0: the facility model            (Phase 1.B)
│   ├── facility/                 ←   zones, layout, coordinate frames
│   ├── assets/                   ←   asset instances and their poses
│   ├── topology/                 ←   process flow and station relationships
│   └── schema/                   ←   JSON Schema definitions + validator
│
├── workspace/src/                ← The ROS 2 workspace               (Phase 1.B)
│   ├── cite_interfaces/          ←   L3-L5: typed messages, services, actions
│   ├── cite_runtime/             ←   process lifecycle mechanism only (ADR-0034)
│   ├── cite_facility/            ←   L0-L1 at runtime: serves the generated model
│   │                                 version, the frame and namespace plan, and the
│   │                                 process topology as a typed LineTopology; loads
│   │                                 the generated planning scene into MoveIt
│   ├── cite_generated/           ←   every artifact generated from L0: descriptions,
│   │                                 world, controller config, MoveIt config, static
│   │                                 frames, process topology, bring-up plan, planning
│   │                                 scene. Committed, never hand-edited (ADR-0021)
│   ├── cite_description/         ←   L1: robot and component descriptions
│   ├── cite_hardware/            ←   L2: hardware interfaces, sim and real
│   ├── cite_control/             ←   L2: controller configuration and bringup
│   ├── cite_skills/              ←   L3: robot-agnostic capability servers
│   ├── cite_orchestration/       ←   L4: behaviour trees and line coordination
│   ├── cite_twin/                ←   L5: mode control, sync bridge, twin monitor
│   ├── cite_telemetry/           ←   L6: telemetry, recording, historian bridge
│   ├── cite_safety/              ←   cross-cutting: interlocks and limits
│   ├── cite_bringup/             ←   composed launch entry points
│   ├── cite_simulation/          ←   Gazebo systems, plugins, generated worlds
│   └── external/                 ←   imported by vcstool; never committed
│
├── tools/                        ← Host-agnostic Python tooling: the L0 validator,
│                                   the generators, the asset pipeline. No ROS
│                                   dependency, so it runs on any operating system.
│
├── assets/                       ← L1: 3D assets and the scan pipeline
│   ├── scans/                    ←   raw and processed capture data (not in git)
│   ├── meshes/                   ←   visual and collision meshes
│   ├── materials/
│   └── manifest.yaml             ←   provenance and checksums for external assets
│
├── hmi/                          ← L7: web operator interface        (Phase 4)
│
├── infra/docker/                 ← Container image and compose services
├── .devcontainer/                ← Editor devcontainer definition
├── .github/workflows/            ← CI
│
├── external/                     ← Pinned third-party sources: the vcstool manifest
│                                   and reviewable patch files. Never vendored.
│
├── requirements/                 ← Host Python dependencies, and the document
│                                   explaining which of the four dependency layers
│                                   each kind belongs in.
│
├── .claude/                      ← Agent configuration      (local; not committed)
│   ├── agents/                   ←   active subagent roles (11)
│   └── orchestration.md          ←   pipeline and dispatch routing
│
├── scripts/                      ← one command per task; the contract every tool
│                                   and agent invokes instead of colcon or docker
│
├── tests/                        ← System- and scenario-level tests
│
└── docs/
    ├── adr/                      ← Architecture Decision Records
    ├── architecture/             ← Detailed per-layer design
    ├── interfaces/               ← Interface contract reference
    ├── operations/               ← Runbooks, bring-up, calibration, safety
    ├── onboarding/               ← Getting started, workflow, glossary
    └── reference/                ← Standards, literature, toolchain
```

**`legacy/` is gone.** The superseded v1 workspace was archived here for the length of the
rebuild and deleted at the end of Phase 1, as this tree said it would be. What it taught is
in `docs/reference/v1-lessons.md`, written before the deletion and anchored to the code that
proved each point; why it was replaced rather than migrated is **ADR-0001**. The tree itself
remains in version control, as §12 says — it is removed from the working tree, not from the
repository's history.

Three conventions in the tree above have their reasoning recorded rather than restated here:

- **`cite_generated/` is committed, not built.** Generated artifacts live in git and are
  verified against a fresh generator run, which is what makes hand-editing one detectable
  rather than merely forbidden. See **ADR-0021**.
- **QoS profiles are a library inside `cite_interfaces`, not a table each node copies.** An
  incompatible publisher/subscriber pair connects silently and delivers nothing, so the
  profiles are code with one definition rather than prose with many. See **ADR-0025**.
- **The `workspace/src/` tree above is the *production* structure. Packages that exist only
  to test it are deliberately not listed in it.** The first of them is `cite_test_hardware`,
  a `ros2_control` `SystemInterface` whose purpose is to make a fault happen on demand, and
  it is barred from production use by construction rather than by convention: its `on_init`
  refuses to initialise without a parameter that has nowhere to be declared in the L0 model,
  so it cannot be selected as the backend for an arm. What it is for, and why the fixture had
  to be a package rather than a flag on an existing one, is **ADR-0040**.
  **So `workspace/src/` contains a package this tree does not list, and that difference is
  this rule rather than drift.** `./scripts/doctor` counts every `package.xml` on disk, so its
  count answers what *exists*; this tree answers what is *production*, and the two are not
  meant to match. The next test-only fixture belongs outside this tree for the same
  reason. The precedent runs the other way only for production code: `cite_runtime` was added
  to this tree by explicit decision (**ADR-0034**, §14 v1.7) because it ships inside the
  running system, which a test fixture does not.

### 7.1 Naming and namespace convention

```
/cite/<zone>/<asset_id>/<interface>
```

Deterministic, generated from L0, identical in simulation and on hardware. Frame identifiers follow the same rule. No asset name is ever written by hand in two places.

---

## 8. Roadmap

Phases are sequential in dependency, but **Phase 3's asset work is parallelizable** with Phases 1–2 because it is content production, not code, and does not block the software track.

Each phase has a hard **exit criterion**. A phase is not complete because the calendar says so; it is complete when its exit criterion is demonstrated.

---

### Phase 1 — Foundation, architecture, and the virtual line

*The rebuild. Everything correct, from zero. This phase produces the platform that every later phase stands on.*

**All five sub-phases are complete, and the exit criterion is MET as of 2026-08-28.** Those
were two separate claims for most of this phase and this section still keeps them apart: a
sub-phase closes when its work exists and has been measured; the phase closes when the exit
criterion is demonstrated. The last clause to close was "CI is green", which had been blocked
at the account level rather than by anything in the code. **The clause table below records
what closed it and what that green run contains — including a scenario that failed inside
it.** Read both halves; a run that is green and a system that works are not the same
statement, and this phase has been wrong in that exact way before. Each sub-phase below keeps
its original text — that is the record of what the phase reached for — with a note beneath it
stating what was actually delivered wherever the two differ. Where a note gives a figure, it
also gives who measured it and over how many runs, because this phase repeatedly had "it
passes" overturned by measurement.

**1.A — Toolchain and repository foundation — COMPLETE**
Ubuntu 24.04 / Jazzy / Harmonic baseline stood up. Docker and devcontainer images. External dependencies declared in a manifest with pinned revisions and reviewable patches. `rosdep` complete. CI pipeline building and testing headlessly. Repository restructured per §7. Coding standards, linting, and formatting enforced automatically. Early verification of xArm support on the target stack.

> *Delivered as written.* `xarm_ros2` is pinned to a commit SHA and was built and driven
> against this stack rather than inspected — the verification table is in
> `docs/reference/toolchain.md`. **The qualification this note used to carry is discharged.**
> It said that "CI pipeline building and testing headlessly" meant the workflow was written
> and its jobs defined, not that it had been observed to pass. The workflow has now been
> observed: run `33158091922` on 2026-08-28 executed every job to completion and all three
> concluded `success`. What that run contains, and what it does not cover, is the CI clause
> below.

**1.B — Architecture and contracts — COMPLETE**
The facility model schema and validator. Generators from L0 to worlds, descriptions, controller configs, and launch graphs. All interface packages defined and reviewed *before* the implementations that use them. Lifecycle and namespace conventions established. Architecture Decision Records written for every choice in §6.

> *Delivered, and wider than written.* The generators also produce MoveIt configuration, the
> planning scene, static frames, process topology and the bring-up plan. `./scripts/validate-model`
> diffs the committed output against a fresh generator run and regenerates under a different
> hash seed to prove byte-identical output (**ADR-0021**).

**1.C — Vertical slice: one arm, every layer — COMPLETE**
A single xArm 5 in Harmonic, driven through the full stack: facility model → generated description → `ros2_control` with the simulation hardware plugin → MoveIt 2 → a real `Pick` skill → a behaviour tree that executes it. Thin but complete: this proves the architecture end to end before it is replicated.

> *Delivered.* The grasp is held by friction alone, with no simulation aid: **ADR-0029**
> removed the attachment plugin because it produced silent successes. The evidence is the
> friction-grasp campaign in `docs/measurements/`, which is also where the finding lives that
> the grasp is repeatable in **position and not in orientation** — a limitation that shapes
> 1.D and Phase 2 rather than being resolved here.

**1.D — The three-arm virtual line — COMPLETE, with one phrase not delivered as written**
Three arms, conveyors, and sensors — all instantiated from the facility model, not hand-placed. Real motion, real grasping, real sensor-triggered transitions, real handoff negotiation between robots. The line runs a continuous cycle without intervention. *This is the workload the previous iteration aimed at and never reached.*

> ***"Real handoff negotiation between robots" was not delivered in the sense the phrase
> reaches for, and this is not being redefined to match what was built.*** Read the sentence
> as it stands: it puts two robots in direct negotiation over a part. What exists is
> **conveyor-mediated**. Every edge in the L0 topology passes through a belt, and L4 does not
> merely leave the direct arm-to-arm case unimplemented — it **refuses** such an edge at plan
> time, so a topology containing one will not start.
>
> **ADR-0031** carries that decision and its 2026-08-26 correction, and the correction is the
> part to read: what makes the permitted conveyor edge safe is that the *receiving* gripper
> squares the part up as it closes on a free part, and a direct handoff denies exactly that,
> because a part still clamped by the giving gripper cannot rotate into alignment with the
> receiving one. The mechanism that rescues one case is the one the other forecloses. A direct
> handoff has never been attempted or measured in this cell. `Transfer` and its behaviour-tree
> leaf remain built and tested against their contract, with no caller.
>
> **What *was* delivered:** three arms, three belts and four beams instantiated from L0 and not
> hand-placed; real motion under MoveIt; a friction grasp; and sensor-triggered transitions —
> a beam edge becomes a typed `DetectionEvent`, L4 stops the belt on it and restarts it on
> completion (**ADR-0032**, **ADR-0033**). The line runs a continuous cycle without
> intervention, which is the sub-phase's last sentence and is met.
>
> **How well it runs is measured thinly and must be read that way.** The counts that exist are
> single-machine run sets by the implementing agent and by the project owner — a handful of
> runs each, with no thresholds registered in advance. They are recorded, with their
> qualifications, in `CLAUDE.md` §2 and are deliberately not copied here (P1). **The line
> completing is not the same as the line being reliable**, and no campaign in
> `docs/measurements/` measures its reliability. Two known open items go to Phase 2: the belts
> are commanded open-loop with nothing publishing `ConveyorState`, and the release-orientation
> residual's accumulation across three stations is explicitly unmeasured.

**1.E — Documentation and quality gates — COMPLETE**
Per-layer architecture documentation. Interface reference. Onboarding guide that a new contributor can follow to a running system unaided. Full test pyramid in place and enforced.

> *Delivered.* Every architecture and interface document carries a `DESIGNED` / `PARTIAL` /
> `BUILT` marker, which `./scripts/doctor` checks for presence, so a specification cannot be
> read as a description. The onboarding guide was walked from a fresh clone rather than
> reviewed — see the exit criterion's first clause. **"Enforced" now means enforced by an
> observed CI run and not only by the local quality gate:** run `33158091922` ran the build,
> the ROS linters, the tests and all three simulation-in-the-loop scenarios on a runner that
> had never seen this project. **One run, taken three commits back on `main`** — the CI
> clause below states both limits.

> **Exit criterion:** On a clean machine, `git clone` followed by a single bootstrap command produces a running three-robot line in Gazebo Harmonic that executes a continuous, sensor-driven pick-and-transfer cycle. CI is green. The entire cell layout is changeable by editing the facility model alone. Every architectural decision is written down.

**Exit criterion status — MET, as of 2026-08-28.** Phase 1 is **closed**. Its clauses stay
broken out below so that what was measured remains distinguishable from what was inferred,
and so that closing the phase does not quietly upgrade any single clause's evidence. **Every
clause is carried at the strength of the evidence that closed it, and none of that evidence
is a campaign.** The fifth clause is not closable as stated and is recorded that way rather
than waved through; the phase is closed on the four that are answerable.

| Clause | Status | On what evidence |
|---|---|---|
| Clean machine; clone plus one bootstrap command; a running line | **Demonstrated — by the CI run, not by the manual walk** | Two pieces of evidence, and they are not the same claim. **The manual walk** (project owner, 2026-08-27, one machine) went from a fresh clone of the remote — not a worktree — with no deviation from the documented steps: `./scripts/doctor` 23 passed / 0 failed, both vendor patches verified present in the imported vendor tree, `./scripts/build` 19 packages, `./scripts/test` clean, in-container `./scripts/lint` clean across all eight linter labels. **That walk stopped at `lint` and never launched the cell**, so what it demonstrates is clone-to-green, not a running line — this row used to cite it for the whole clause and that overstated it. **What demonstrates the clause is CI run `33158091922`:** on a runner that had never seen this project, `actions/checkout` → image build → `./scripts/bootstrap` → `./scripts/build` reporting `Summary: 20 packages finished` → ROS linters → tests → `./scripts/scenario bringup` twice, both reporting `ok Scenario 'bringup' passed`, unattended and headless. That is a clean machine to a running three-arm cell in Gazebo Harmonic. **One run**; its limits are in the CI row below. |
| A continuous, sensor-driven pick-and-transfer cycle | **Demonstrated; not characterised** | 3 of 4 runs completed. The run that did not failed when `ros2 run ros_gz_sim create` timed out spawning a work-piece — a harness failure. **No run failed for a line defect.** A further verification was in flight when this was written and its result is not recorded here. Four runs on one machine with no pre-registered thresholds is a demonstration, **not a reliability figure**. **The CI run that closed the clause below did not reproduce this one:** its `continuous_line` carried 1 of 3 work-pieces and failed. **When this clause closed, that was the only time this cycle had ever run on a machine nobody prepared, and it failed** — which is why this row says *not characterised* and must not be read as more. **It is no longer the only such run.** CI has run the scenario repeatedly since, on `main`, with both passes and failures; the log-derived tally, its runs and its qualifications are `CLAUDE.md` §2's and are cited rather than copied (P1) — including the instrument problem it records, that `gh run view --json jobs` reports this `continue-on-error` step as `success` even when the scenario failed, so only the log answers. **None of that reopens or upgrades this clause:** it closed on the evidence available then, a later run neither adds to nor subtracts from that closure, and the row still reads *not characterised* because nothing since has been a campaign. |
| The entire cell layout is changeable by editing the facility model alone | **Demonstrated** | A pedestal was moved 50 mm in L0 and the tree regenerated: five generated artifacts changed, the arm anchored to that pedestal followed it, and **nothing outside `model/` and `workspace/src/cite_generated/` changed at all**. This is P1 and **ADR-0004** exercised rather than asserted. |
| **CI is green** | **MET — and the green run contains a failed scenario** | Run `33158091922`, on `main`, 2026-08-28: conclusion `success`, all three jobs `success`. Inside it, the advisory `continuous_line` step **failed**. Both halves are the record; see below. |
| Every architectural decision is written down | **Cannot be closed as stated** | The record is complete and self-consistent — `./scripts/doctor` checks that every ADR on disk is indexed and every ADR reference resolves. But "every decision" is a universal that no check establishes, and there is a known counter-instance: **ADR-0031 records that its own decision existed only in a commit message until the documentation pass after the fact.** Read this clause as *the decisions we know of are recorded*, which is what the evidence supports. |

**How the CI clause was met, and what its meeting contains.** Both paragraphs below are the
clause. Neither is the whole of it.

**The run.** `33158091922`, triggered by a push to `main` on 2026-08-28, 42 minutes,
conclusion **`success`**. `Host tooling (lint, types, model)` and `Supply chain` had each
executed once before, earlier the same day; **`ROS workspace (build, test)` had never run at
all**, and it did — image build, `./scripts/bootstrap`, a 20-package build, the ROS linters,
the tests, and all three simulation-in-the-loop scenarios, on a runner that had never seen
this project. That is what
the clause asked for, and what the earlier account-level block had made unattemptable rather
than failing. Of the eight runs preceding it, **seven were refused before any step executed**
— for failed payments or a spending limit — and recorded zero steps; the eighth, earlier the
same day, executed and failed in host tooling, which skipped the ROS job by `needs:`. So
`33158091922` is the **only run in this repository's history in which the ROS workspace job
has executed a step at all**. The repository is public at the time of writing; that its
visibility is what lifted the block is the project owner's account and is not verified here.

**And the green run contains a failed scenario.** Inside it, `continuous_line` failed:

> `piece 1: complete, 10/10` — `piece 2: STOPPED after 2/10 milestones, waiting on
> on_link(station_transfer_1: cell_a__conveyor_1__infeed) for 420s` — `pieces 3..3 were not
> fed: the line had already stalled` — `error Scenario 'continuous_line' failed — 1 cycle
> assertion(s) failed`

That step carries `continue-on-error: true`, so it reported success to the job and the
workflow passed. **The workflow's green is therefore honest about what it gates and silent
about what it does not**, and the clause is met exactly as it reads and not one word further:
the blocking steps passed, and one advisory step failed on a real stall. The last `LineState`
of that run read `state=1` with `stall_reasons=none` while `station_transfer_1` held
`occupancy=1/1, workpiece=wp_000002` — a station stopped, and a line reporting itself
healthy. **That silence is the blind spot ADR-0039 records at exactly that station**, which
is measured. What stopped the piece was not established when this clause closed, and until
2026-08-30 this paragraph attributed it to the failed-grasp dead end **ADR-0038** records as
deliberately unfixed. **That attribution was false, and this run's own data falsifies it:**
the piece passed the `lifted` milestone at `station_transfer_1`, and that milestone is
*measured* — a sampled pose compared against the pick frame — rather than reported by the
arm, so the grasp held. **The cause has since been established, and it is recorded in
ADR-0045 and ADR-0046**; **ADR-0038**'s 2026-08-29 amendment records that the same dead end
is reached through a second door. Read those records rather than this paragraph: the
mechanism is theirs, it carries their status, and it is deliberately not repeated here.
**None of this reopens the clause** — it closed on evidence that never contained a cause,
and a cause does not add a run.

**What this run does not carry.** It ran at commit `60eb4a5`. Three commits have landed on
`main` since, and they add a ninth package, `cite_test_hardware` (§7, **ADR-0040**), which no
completed CI run has yet built — a run against `a90b05f` was in flight when this was written
and its result is **not** recorded here. And it is **one run**: no thresholds were registered
in advance, nothing about it is a reliability figure, and a second green run would be worth
more than any sentence in this paragraph. The clause is "CI is green", not "CI is green
repeatably" — closing the first does not close the second, and Phase 2 inherits it.

---

### Phase 2 — Physical integration and twin synchronization (L1 → L2)

Physical xArm hardware interface behind the same `ros2_control` boundary. Safety layer and E-stop path. Mode switching between `SIM`, `REAL`, `SHADOW`, `VALIDATED` and `VIRTUAL_LEAD` — the last being the operator-facing flow in which the simulated side is commanded and the far side follows and actuates, added for Phase 2.A and specified in ADR-0041. Calibration and spatial registration between the physical cell and the model. The twin monitor publishing live divergence metrics.

**Phase 2 is delivered in two sub-phases, and the split is deliberate: the twin mechanism is built and exercised before any hardware exists, and only then is hardware put behind it.**

**2.A — The twin mechanism against a virtual counterpart — IN PROGRESS: the pair comes up; nothing automated brings it up**
The plant is paired with a **virtual counterpart**: a complete second simulation of the same three-arm cell, generated from the same L0 model and modelled *as if it were physical*. The cell stays three-armed — 2.A builds on it rather than beside it — and what 2.A delivers is the mechanism the twin is made of: mode switching and command routing, the mirroring path, and the monitor that will later compute fidelity, all exercised end to end before any hardware exists. That the counterpart is a full second simulation rather than a kinematic echo or a replayed trajectory is **ADR-0041**; the two defect classes that exist only because there are two sides are **ADR-0042** (transport partitioning per side) and **ADR-0043** (both sides held to the wall clock). What a second cell costs was measured before the design fixed its shape — `docs/measurements/2026-08-28-second-world-cost/`.

> **What 2.A cannot claim, stated here rather than discovered later.** 2.A closes **no clause** of the exit criterion below, and **no number it produces is a fidelity measurement**. Both sides run the same L0 model, the same generated description and the same physics solver, so divergence measured across the pair is instrument, solver and scheduling noise; it is not a reality gap and does not become one by being plotted. Under §2's maturity model 2.A stays at level **L0**, however much of L5 it exercises: L1 and L2 are each defined by an information flow from the physical, and 2.A has no physical side. **2.A validates the instrument; 2.B is what first uses it.**

> **What exists, as of 2026-08-31: a pair comes up.** `./scripts/sim --pair` starts two independent launches and **joins** them — it does not sequence them — on a token each side prints from its own readiness witness, under a supervisor that owns the join and the pair's lifetime and holds no ROS context (**ADR-0047**). **Both isolations were verified at runtime rather than by reading the launch file:** one `/clock` publisher on each domain where a merged graph would show two, one Gazebo server per partition at different endpoints, and every name this project forms present exactly once on each side (**ADR-0044**, **ADR-0042**). That is the P2 property demonstrated rather than argued.
>
> **What is not built, in the same breath, because the bring-up half is the smaller one.** There is **no paired scenario, and none is possible in the present shape** — `launch_test` with `IncludeLaunchDescription` is one process holding one context on one domain — so **nothing automated brings a pair up**, and a regression in the witness, the token or either side's bring-up would not fail CI. The shipped model declares `single`, so a pair does not come up on a clean checkout. **2.A still produces no fidelity number**, exactly as the note above says it cannot. And **ADR-0043's real-time requirement is not met**: measured on one machine, with the convex-hull collision geometry that is not the shipped default, both sides reach about **0.95** against a required **1.0** — the figures are held in **ADR-0028**'s implementation note and are cited rather than copied. **ADR-0049** has since restated that requirement as a capacity measurement plus a clock-deficit budget, and **neither threshold is yet set**.
>
> **Strength: three joined runs on one machine by the implementing agent, not re-taken by review, with no test and no CI run covering any of it.** That is why this sub-phase is marked in progress and not complete, and none of it closes any clause of the exit criterion below.

**2.B — The real cell replaces the stand-in**
The counterpart is replaced by physical hardware behind the same `ros2_control` boundary, and what the plant talks to across the twin boundary does not change shape — that is what 2.A is built to guarantee (P2) and 2.B is the first test of it. **The first fidelity measurement in this project is produced here**, and the exit criterion below is closed in 2.B or not at all.

The architecture is designed for heterogeneous, incrementally-arriving hardware: the system runs correctly with one physical arm and two simulated ones, and gains arms without structural change.

**`VIRTUAL_LEAD` pulls a direction forward and not a level.** §2 places virtual → real at maturity L3 and this roadmap places L3 in Phase 5, so naming the mode here is deliberate and is stated rather than assumed. What Phase 5 owns is the *validation gate* — no behaviour reaching hardware without passing automated validation in the twin — and `VIRTUAL_LEAD` has no such gate; it carries the direction alone. In Phase 2.A the far side is a second simulation, so nothing physical can move under it, and the level is L0 whichever mode is in force. What gates it against a physical far side is the refusal already in the tree: bring-up refuses a plan naming a non-`sim` backend unless `CITE_ALLOW_HARDWARE=1` is set. **The exit criterion below is unchanged, and no clause of it is closed by any of this.**

> **Exit criterion:** A physical xArm 5 moving under manual or programmatic control drives its virtual twin live, with sub-cycle latency. The same skill code, unmodified, executes on both. The twin monitor publishes and records a quantified fidelity error, and that number is defended with data rather than asserted.

---

### Phase 3 — Facility fidelity: CITE in the twin

*Parallelizable with Phases 1–2.*

3D capture of the CITE facility. The scan pipeline: capture → registration → cleanup → decimation → visual/collision separation → material authoring → simulator assets. Spatial registration of scanned geometry to the engineered coordinate frame. Lighting and material work for visual credibility. Multi-zone facility model supporting more than one cell.

> **Exit criterion:** The CITE facility exists in Harmonic at true scale, with the robot cell correctly registered inside it. A person who knows the building recognizes it, and a measurement taken in the model matches a measurement taken in the building.

---

### Phase 4 — Data platform and operator interface

Telemetry schema finalized. Historian deployed with retention and query. Deterministic record and replay of production runs. The web HMI: live state, KPIs, alarms, divergence trends, historical playback. Remote access with authentication and access control.

> **Exit criterion:** A stakeholder outside CITE opens a browser, watches the cell live, inspects throughput and twin-fidelity trends, and replays a run from last week.

---

### Phase 5 — Closed loop and predictive (L3 → L4)

Simulation-first deployment gate: no behaviour reaches physical hardware without passing automated validation in the twin. What-if scenario execution. Predictive analysis for bottlenecks and collisions. Optimization recommendations fed back to line operation. Industrial protocol bridges as integration demand appears.

> **Exit criterion:** A behaviour change is validated automatically in the twin and deployed to hardware through a gated pipeline, and the twin answers a real operational question — a layout, sequencing, or throughput decision — before the physical change is made.

---

## 9. Definition of Done and quality gates

A capability is **done** when all of the following are true. There is no partial credit.

1. **It is generated from or declared in the facility model** where applicable (P1, P5).
2. **Its interfaces are typed** and defined in an interface package (P3).
3. **It has automated tests at the appropriate level** and they pass in CI (P6):
   - *Unit* — pure logic, no ROS runtime.
   - *Integration* — node and launch behaviour, `launch_testing`.
   - *Simulation-in-the-loop* — headless scenario execution with deterministic outcomes.
   - *Contract* — interface compatibility guarded against regression.
4. **It runs headlessly in CI** on a clean container, with no manual step.
5. **It works identically in simulation and on hardware**, or its hardware path is explicitly and visibly marked as not yet implemented (P2, P7).
6. **It is documented** — what it does, its interfaces, how to run it, how it fails.
7. **It has been reviewed**, by a human and by the review agents (§10).
8. **Startup and shutdown are event-driven**, containing no timing guesses (P4).

### 9.1 Standing prohibitions

The following are rejected in review, without discussion:

- Hand-edited generated artifacts (world files, controller configs, launch graphs).
- `std_msgs/String` carrying structured data.
- `TimerAction` or `sleep` used to sequence startup.
- Third-party source copied into the tree instead of pinned in the manifest.
- A capability marked complete in documentation without a test proving it.
- Any identifier, comment, or document not in English.
- A value that exists in two places.

---

## 10. How we work

### 10.1 Team

The engineering team operates under CITE. This document defines *what* is built and *why*; assignment, scheduling, and prioritization are CITE's management responsibility. Phases are sized to be independently ownable so that work can be parallelized across the team without contention.

### 10.2 AI agents in the workflow

AI agents are first-class participants in this project, with defined roles and defined limits. `CLAUDE.md` is the canonical rulebook loaded by every session and every agent; `AGENTS.md` points to it; the pipeline and dispatch routing are defined in `.claude/orchestration.md`.

**`.claude/` is local tooling and is not committed to this repository.** A fresh clone will not contain it, and every reference to it below describes a directory the reader may have to obtain separately. The rules the agents enforce are in `CLAUDE.md`, which *is* committed — so the standards survive without the tooling, and a contributor working without agents is held to exactly the same bar.

The active roster is eleven roles in `.claude/agents/`:

- **Core pipeline** — `coder`, `reviewer`, `tester`, `fixer`.
- **Domain auditors** — `model-validator` (the L0 model and everything generated from it: schema, kinematic trees, inertia tensors, collision geometry, interface matching) and `safety-auditor` (every path that can produce motion: safety-layer bypass, E-stop propagation, limit enforcement, watchdogs, mode transitions).
- **Conditional specialists** — `architect-reviewer`, `debugger`, `performance-engineer`, `docs-writer`, `dependency-auditor`.

The two domain auditors exist because this project's most expensive failures are not ordinary bugs. A wrong inertia tensor produces a simulation that runs confidently and is wrong; an unguarded command path produces a physical arm that moves when nobody expected it. Neither is caught by ordinary code review.

Two roles are deliberately **absent** until Phase 4, when a historian and remote access give them a real domain: database and telemetry-schema review, and security auditing. They will be written then, against the domain they actually have to audit, rather than carried as dormant files — an agent with no live domain still competes for description-based routing and degrades dispatch accuracy for every other role.

The operating rules:

- **Agents propose; humans and tests decide.** No agent output merges without review and passing CI.
- **Agents are bound by this document.** An agent that produces work contradicting §4 or §9 is producing a defect.
- **Specialist review is routine, not exceptional.** Architecture, testing, security, dependency, performance, and documentation review agents run against changes as part of the normal flow rather than on request.
- **Documentation is kept in sync by agents, verified by humans.** Drift between code and documentation is treated as a defect (P7).

### 10.3 Change control

- **Architecture Decision Records** (`docs/adr/`) capture every significant technical decision: context, options considered, decision, consequences. An ADR is written *before* the decision is implemented, not after.
- **This document** is updated when direction changes, and only then (§0).
- **Commits and pull requests** describe intent and reference the ADR or phase item they serve.

---

## 11. Where things are written down

| Question | Where |
|---|---|
| What are we building and why? | **This document** |
| What are the rules for working here? | `CLAUDE.md` |
| Why was this technical choice made? | `docs/adr/` — one record per decision |
| How does layer *X* work in detail? | `docs/architecture/L*.md` |
| How does this relate to industry standards? | `docs/architecture/standards-alignment.md` |
| What is the shape of this interface? | `docs/interfaces/` and the interface packages |
| How do I get started? | `docs/onboarding/getting-started.md` |
| How do we work day to day? | `docs/onboarding/development-workflow.md` |
| What does this term mean here? | `docs/onboarding/glossary.md` |
| How do I bring up / calibrate / recover the cell? | `docs/operations/` |
| Where do I read more? | `docs/reference/` — standards, literature, toolchain |
| How should an AI agent behave here? | `CLAUDE.md` and `AGENTS.md` (committed); `.claude/orchestration.md` (local, not committed) |
| What is being worked on right now? | The issue tracker — **not** this document |

Every architecture and interface document carries a status marker — `DESIGNED`, `PARTIAL`, or `BUILT` — so that a specification is never mistaken for a description (P7).

---

## 12. Starting position

The project underwent an extended R&D period before this charter. That work produced real knowledge — xArm integration, `ros2_control` behaviour, conveyor plugin mechanics, multi-robot spawning, and a clear picture of what does not scale. It also accumulated debt that cannot be refactored away:

- The system was a simulation at **L0**, with no physical coupling despite the project's name — no hardware interface existed anywhere in the codebase.
- A critical dependency was patched locally and committed as a submodule reference with no manifest entry, meaning a fresh clone could not build and the patch existed only on one machine.
- Robot motion was simulated by timers rather than executed; the handoff protocol published to topics nobody subscribed to.
- Three mutually incompatible architectures coexisted, with contradictory naming and eight launch files of unclear provenance.
- Values were duplicated across configuration and world files and had diverged.
- There were no tests, no CI, and no reproducible environment.
- Documented status did not match reality.

**We are not migrating this. We are rebuilding on the same repository with the correct architecture, carrying forward knowledge rather than code.** The prior history remains in version control for reference; it does not constrain the new structure. Each failure above maps to a principle in §4 — that is why those principles exist and why they are not negotiable.

---

## 13. Risks

| Risk | Impact | Response |
|---|---|---|
| ~~xArm ROS 2 support on Jazzy/Harmonic is incomplete~~ **Closed 2026-08-24** | — | Verified: the `jazzy` branch of `xarm_ros2` declares `gz_ros2_control`, `ros_gz_sim`, and `ros_gz_bridge` — full Gazebo Harmonic support. The upstream README still links to Gazebo Classic and is simply stale. Residual work is pinning to a commit SHA and confirming a real build. See ADR-0003. |
| Gazebo Harmonic migration is larger than estimated | Phase 1 schedule | Conveyor and sensor plugins are already scoped as rewrites (§6.1), not ports. The vertical slice (1.C) surfaces unknowns before replication. |
| 3D scan data is too heavy for real-time simulation | Facility twin unusable | Visual and collision representations are separated from the start; aggressive decimation and level-of-detail are pipeline requirements, not afterthoughts. |
| Physical hardware arrives incrementally | Phase 2 sequencing | The architecture supports mixed real/simulated fleets by design (P2, P9); no phase depends on all hardware being present. |
| Team turnover, students rotating through | Knowledge loss | This document, ADRs, onboarding docs, and enforced tests are the mitigation. The system must be legible to someone who was not there. |
| Scope pull toward visual demos over measured fidelity | Reduces the twin to a rendering | §2 maturity levels and P8 make fidelity a published number. Visual work is Phase 3 and serves measurement. |
| Architecture erosion under delivery pressure | Return to the prior state | §9 quality gates and the standing prohibitions in §9.1 are enforced in review, by humans and agents, without exception. |

---

## 14. Document history

| Version | Date | Change |
|---|---|---|
| 1.11 | 2026-08-31 | **Two corrections to §8, and neither reopens a clause.** **First, Phase 2.A carried no progress marker at all**, so a reader could not tell that its bring-up half exists. It does: `./scripts/sim --pair` starts two independent launches and **joins** them — never sequences them — on a token each side prints from its own readiness witness, under a supervisor that owns the join and the pair's lifetime and holds no ROS context (**ADR-0047**); and **both isolations were verified at runtime rather than by reading the launch file** — one `/clock` publisher on each domain where a merged graph would show two, one Gazebo server per partition at different endpoints, and every name this project forms present exactly once on each side (**ADR-0044**, **ADR-0042**). That is P2 demonstrated rather than argued, and §8 records it with what it is not, in the same breath: **there is no paired scenario and none is possible in the present shape** — `launch_test` with `IncludeLaunchDescription` is one process holding one context on one domain — so nothing automated brings a pair up; the shipped model declares `single`; 2.A still produces **no fidelity number**, exactly as its standing note says it cannot; and **ADR-0043's real-time requirement is not met**, both sides reaching about 0.95 against a required 1.0 on one machine under the convex-hull geometry that is not the shipped default, which **ADR-0049** has since restated as a capacity measurement plus a clock-deficit budget with neither threshold yet set. **The strength is three joined runs on one machine by the implementing agent, not re-taken by review, with no test and no CI run covering any of it** — which is why the marker reads in progress rather than complete, and why the sub-phase's note says so before it says anything else. **The Phase 2 exit criterion is byte-unchanged and 2.A closes no clause of it**, by construction. **Second, clause 2 of Phase 1's exit-criterion table said of the `continuous_line` cycle that the failed run inside `33158091922` was *"the only time this cycle has ever run on a machine nobody prepared"*.** That was true when the clause closed and is not true now: CI has run the scenario repeatedly since, with both passes and failures, and the log-derived tally lives in `CLAUDE.md` §2 and is cited rather than copied (P1) — together with the instrument problem it records, that `gh run view --json jobs` calls a `continue-on-error` step `success` even when it failed, so only the log answers. **The clause is neither reopened nor upgraded**: it closed on the evidence available then, a later run neither adds to nor subtracts from that closure, and the row still reads *not characterised* because nothing since has been a campaign. No change to scope, architecture, technology baseline, or any phase beyond the two records corrected here. |
| 1.10 | 2026-08-30 | **§8 carried a false causal attribution for the one failure inside the run that closed Phase 1, and it is struck.** The CI clause closed on run `33158091922`, whose advisory `continuous_line` step failed carrying 1 of 3 work-pieces; §8 said that failure was consistent with the failed-grasp dead end **ADR-0038** records as deliberately unfixed. **The run's own data falsifies that:** the piece passed the `lifted` milestone at `station_transfer_1`, and that milestone is *measured* — a sampled pose compared against the pick frame — rather than reported by the arm, so the grasp held and the stall was never a failed grasp. **The cause has since been established and is recorded in ADR-0045 and ADR-0046**, with **ADR-0038** amended on 2026-08-29 to record that the same dead end is reached through a second door. **§8 names those records and does not reproduce their mechanism, deliberately:** causal detail belongs in the ADRs, which carry their own status, and **both new records are `Proposed` — their mechanism is evidenced and their outcome is not**, no CI run having yet shown the gripper failing to answer and the line reporting it. A charter paragraph restating an unpromoted mechanism would be a claim with an expiry date; §8's job is the phase record, and it stays true longer by saying less. **The exit criterion is untouched and no clause is reopened** — the CI clause closed on evidence that never contained a cause, a cause adds no run, and §8 still records the criterion MET at exactly the strength it was met. **The v1.8 entry below is deliberately left as written**, carrying the attribution that was believed at that version: a version history records what was believed, and rewriting a past row destroys what §14 is for — the correction is recorded here instead. No change to scope, architecture, technology baseline, or the phases beyond 1. |
| 1.9 | 2026-08-29 | **Phase 2 splits into 2.A and 2.B, and gains a sixth operating mode.** §8 now states that the plant is first paired with a **virtual counterpart** — a complete second simulation of the same three-arm cell, modelled as if it were physical (**ADR-0041**, with **ADR-0042** and **ADR-0043** for the two defect classes that exist only because there are two sides, and `docs/measurements/2026-08-28-second-world-cost/` for what a second cell costs) — and that 2.B replaces that stand-in with the real cell. **2.A closes no clause of the Phase 2 exit criterion and produces no fidelity number**: both sides run the same L0 model and the same solver, so divergence across the pair is instrument, solver and scheduling noise, and under §2 the level stays at **L0**, since L1 and L2 are each defined by a flow from the physical that 2.A does not have. 2.A validates the instrument; 2.B first uses it. **The sixth mode is `VIRTUAL_LEAD`** — an operator commands the simulated side, the far side follows and actuates, nothing mirrors back — and it is added to §3.1's scope table, §5's L5 mode table and §8's Phase 2 scope sentence. **None of the five existing modes expressed that flow**: `SIM` and `REAL` each idle one side, `SHADOW` and `VALIDATED` are *defined* by a flow from the physical, and `CLOSED_LOOP` has the direction but is defined by the validation gate in front of it. §3.1 was a third charter location that two reviews missed and a grep found — and **that grep is the instrument, which undercounts**: `grep -rn CLOSED_LOOP` reaches the twelve locations in nine files ADR-0041 lists, while a thirteenth, `DivergenceMetrics.msg`, constrains the mode set in prose that names no constant and is invisible to it; it was found by reading, is left alone as an open L5 question, and whether others remain is unknown. A fourteenth location, in a file already among the nine, was found **wrong** rather than merely incomplete: `docs/onboarding/glossary.md` introduced the modes as *"Runtime modes at L5, corresponding to the levels above"*, which the sixth mode falsifies and which was already false, `REAL` having no level — the same diagnosis as ADR-0011's amendment, surfacing in a fifth document. One enumeration needing this many places to agree is P1's shape at the level of prose. **The direction is pulled forward into Phase 2; the level is not.** §2 places virtual → real at L3 and §8 places L3 in Phase 5, and what Phase 5 owns is the gate rather than the direction. **§2's new paragraph is load-bearing rather than explanatory.** ADR-0011's own level table gives L3 as a data flow and nothing else, so on that record alone this mode reads as an L3 flow arriving three phases early; the argument that it is not closes on §2's L3 row — *"Behaviour is validated in simulation and then commands the physical system"* — and on `docs/architecture/L5-twin-synchronization.md`'s mode table, and nowhere else. If either is ever read as putting the direction alone at L3, the mode must be re-argued rather than repeated. **ADR-0011 takes a matching amendment** rather than a supersession: its five levels, their literature mapping and its commitment are untouched, and only the mode set widens. **The Phase 2 exit criterion is untouched — no clause of it is closed by any of this**, and 2.A closes none of it by construction. What gates the mode against a physical far side is the refusal **already in the tree**, bring-up refusing a plan that names a non-`sim` backend unless `CITE_ALLOW_HARDWARE` is set to exactly `1`, and not a new gate; that it binds at bring-up rather than at the transition is the stated residual. **The three dangerous-transition lists now name this mode, and the residual has moved rather than closed.** `cross-cutting-safety.md`, `L5-twin-synchronization.md` and `SetMode.srv`'s header each carried two transitions — `SIM` → `REAL` and entry to `CLOSED_LOOP` — and each now carries three, entry to `VIRTUAL_LEAD` **against a real far side** joining them on the same criterion rather than by analogy: it is `CLOSED_LOOP` minus the validation gate, aimed at the same arm. Each also states that where the far side is a simulated counterpart — Phase 2.A — entering it can move nothing physical. **What stands behind those lists is not a refusal at the point of transition.** `require_hardware_opt_in` and `CITE_ALLOW_HARDWARE` bind at **bring-up**, so what they buy is that the stack could not have started with a physical backend, and **nothing refuses a mode transition today, because no server implements `SetMode`** — `cite_twin` does not exist. That service's own standing commitment, that the L5 server which eventually serves it applies the same check at the transition, is cited and not extended; no new gate was invented for this mode. The gap is recorded here because it is what a future safety change has to close, and because a document asserting a guarantee no code provides is the false attestation P7 exists to prevent. No change to scope, layer architecture, technology baseline, or the phases beyond 2. |
| 1.8 | 2026-08-28 | **Phase 1 is closed: §8 records the exit criterion as MET.** The clause that had been open was "CI is green", and it was open for a reason outside the code — until that morning, every workflow run in this repository's history had been refused at the account level before a step executed, and the `ROS workspace (build, test)` job had never executed a step at all. Run `33158091922`, pushed to `main` on 2026-08-28, concluded `success` with all three jobs green, and the `ROS workspace (build, test)` job executed for the first time in this repository: image build, bootstrap, a 20-package build, the ROS linters, the tests, and all three simulation-in-the-loop scenarios. **The clause is recorded as met together with what its meeting contains.** Inside that green run the advisory `continuous_line` step **failed**, carrying 1 of 3 work-pieces and leaving a station stopped while `LineState` reported the line healthy — the blind spot **ADR-0039** records at that station and the dead end **ADR-0038** records as deliberately unfixed. The step is `continue-on-error`, so the workflow passed and the failure is real; §8 states both in one breath, because either half alone is a false reading. Two other clauses were corrected in the same pass rather than upgraded: clause 1 no longer rests on the manual clean-clone walk, which stopped at `lint` and never launched the cell, but on the CI run, which brought the three-arm cell up twice from a checkout on a machine that had never seen the project; and clause 2 records that the same run's `continuous_line` failed, being the only time that cycle has run outside a machine someone prepared. The fifth clause is untouched and still recorded as unclosable as stated. §8 also states what the run does not carry: one run, no thresholds registered in advance, at commit `60eb4a5`, three commits behind `main` and predating the ninth package. **§7 gains a third convention: its `workspace/src/` tree is the *production* structure, and packages that exist only to test it are deliberately not listed in it.** The first is `cite_test_hardware`, a `ros2_control` `SystemInterface` that cannot be selected as an arm's backend because its `on_init` refuses without a parameter the L0 model has nowhere to declare (**ADR-0040**). This is the opposite disposition to v1.7's, and deliberately: `cite_runtime` entered the tree because it ships inside the running system, which a test fixture does not. Written down so that a reader who counts more packages on disk than in the tree finds the rule rather than a drift. No change to scope, architecture, technology baseline, or the phases beyond 1. |
| 1.7 | 2026-08-27 | §7 gains `cite_runtime`, a package holding process-lifecycle mechanism only — signal handling and shutdown for `rclpy` nodes, with no domain knowledge and no in-project dependencies. It exists because a shutdown helper had to live somewhere and neither existing candidate was right: `cite_interfaces` holds interfaces and their delivery contract, and ADR-0025's closing clause named a helper landing there as the signal to reopen by amendment rather than let the package widen gradually — which is what this entry is; `cite_facility` describes itself as runtime access to artifacts generated from L0, which a signal handler is not. Recorded with the two upstream `rclpy` races it compensates for, and the condition for deleting each, in **ADR-0034**. One package added to the §7 tree. No change to scope, architecture, technology baseline, or roadmap. |
| 1.6 | 2026-08-27 | **Phase 1's record closed.** §8 marks sub-phases 1.A through 1.E complete, each with a note naming what was delivered and, where a figure is given, who measured it and over how many runs. **1.D is marked complete with one phrase explicitly not delivered as written:** "real handoff negotiation between robots" reaches for a direct arm-to-arm crossing, and what exists is conveyor-mediated, with L4 refusing a direct edge at plan time rather than leaving it unimplemented (ADR-0031 and its 2026-08-26 correction). The phrase is left standing and the divergence recorded beside it, rather than the phase being redefined to match what was built. **§8's exit criterion stays OPEN.** Three clauses are demonstrated — the clean-clone walk, the continuous sensor-driven cycle, and the layout being changeable from L0 alone — each with the size and limits of its evidence stated. The **CI clause is unverified and not currently verifiable**: every workflow run in this repository's history was refused at the account level before any step executed, for failed payments or a spending limit, which is a billing block and not a test result; the workflow running to completion is what would settle it. The fifth clause, "every architectural decision is written down", is recorded as unclosable as stated, since it is a universal and ADR-0031 is a known counter-instance. §7 removes `legacy/` from the repository tree, the v1 workspace having been deleted at the end of Phase 1 as that tree said it would be and after its lessons were captured in `docs/reference/v1-lessons.md`; the tree remains in version control. No change to scope, architecture, technology baseline, or the phases beyond 1. |
| 1.5 | 2026-08-25 | §7 brought back in line with the workspace. Added `cite_generated/`, which now exists and holds every artifact derived from L0 — descriptions, world, controller configuration, MoveIt configuration, static frames, process topology, bring-up plan and the planning scene. Corrected the description of `cite_facility/`, which had described something narrower than the package became: it is an L0–L1 **runtime** package that serves the generated model version, the frame and namespace plan and the process topology as a typed `LineTopology` message, and loads the generated planning scene into MoveIt — the generators themselves live in `tools/`, as the same tree already stated. Added pointers to ADR-0021 (generated artifacts are committed and verified against a fresh generator run) and ADR-0025 (the QoS profiles ship as a library inside `cite_interfaces`), because §7 is where a reader looks for the reasoning behind those two entries. No change to scope, architecture, technology baseline, or roadmap. |
| 1.4 | 2026-08-24 | Marked `.claude/` as local tooling that is not committed, in the §7 tree, §10.2 and the §11 documentation map. The agent configuration is excluded from the repository by decision; without the marker a reader would look for a directory a clone does not contain. Notes that the rules the agents enforce live in `CLAUDE.md`, which is committed, so the standards do not depend on the tooling. No change to scope, architecture, technology baseline, or roadmap. |
| 1.3 | 2026-08-24 | §7 repository structure brought back in line with the tree and given an explicit meaning: it describes the **target** structure, with markers for what does not yet exist (`model/`, `workspace/src/`, `hmi/`) and what is temporary (`legacy/`). Added `tools/`, `requirements/`, `docs/reference/`, `.devcontainer/`, `.github/` and `legacy/`; corrected the claim that `infra/` holds the devcontainer and CI, which live at the repository root because their tooling requires it. Removed `subagents/`, the portable upstream template library the active roles were adapted from — it was never tracked in git and is no longer present; the adapted roles in `.claude/agents/` are the only roster. §10.2 updated accordingly: the two roles deferred to Phase 4 will be written then rather than carried as dormant templates. No change to scope, architecture, technology baseline, or roadmap. |
| 1.2 | 2026-08-24 | Documentation tree written. Twin maturity levels renamed to align with the established literature: L1 `Mirror`→`Shadow`, L2 `Shadow`→`Validated`, with the corresponding L5 operating modes renamed to match (§2, §5). Architecture aligned with the ISO 23247 reference architecture (§2). The xArm Jazzy/Harmonic risk is closed following verification (§13). §11 documentation map expanded to the full tree and the status-marker convention introduced. No change to scope, layer architecture, technology baseline, or roadmap. |
| 1.1 | 2026-08-24 | Agent configuration integrated. Added `.claude/` and `subagents/` to the repository structure (§7); replaced the agent paragraph in §10.2 with the concrete eleven-role roster, the rationale for the two domain auditors, and the two roles deferred to Phase 4. No change to scope, architecture, technology baseline, or roadmap. |
| 1.0 | 2026-08-24 | Initial charter. Establishes project identity, twin maturity model, scope, engineering principles, layered architecture, technology baseline, repository structure, five-phase roadmap, quality gates, and working model. Supersedes all prior planning documents. |
