# What We Are Doing

**The CITE Digital Twin — project charter, architecture doctrine, and roadmap.**

| | |
|---|---|
| **Owner** | Center for Innovation, Technology and Entrepreneurship (CITE), Sam Houston State University |
| **Document version** | 1.3 |
| **Date** | 2026-08-24 |
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
| **Twin synchronization** | Mode-switched bridge (`SIM` / `REAL` / `SHADOW` / `VALIDATED` / `CLOSED_LOOP`) plus continuous divergence measurement. |
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
│   ├── cite_facility/            ←   L0-L1: model loading, validation, generators
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
├── .claude/                      ← Agent configuration
│   ├── agents/                   ←   active subagent roles (11)
│   └── orchestration.md          ←   pipeline and dispatch routing
│
├── scripts/                      ← one command per task; the contract every tool
│                                   and agent invokes instead of colcon or docker
│
├── tests/                        ← System- and scenario-level tests
│
├── docs/
│   ├── adr/                      ← Architecture Decision Records
│   ├── architecture/             ← Detailed per-layer design
│   ├── interfaces/               ← Interface contract reference
│   ├── operations/               ← Runbooks, bring-up, calibration, safety
│   ├── onboarding/               ← Getting started, workflow, glossary
│   └── reference/                ← Standards, literature, toolchain
│
└── legacy/                       ← Superseded v1. Reference only, never built.
                                    Deleted at the end of Phase 1.   (temporary)
```

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

**1.A — Toolchain and repository foundation**
Ubuntu 24.04 / Jazzy / Harmonic baseline stood up. Docker and devcontainer images. External dependencies declared in a manifest with pinned revisions and reviewable patches. `rosdep` complete. CI pipeline building and testing headlessly. Repository restructured per §7. Coding standards, linting, and formatting enforced automatically. Early verification of xArm support on the target stack.

**1.B — Architecture and contracts**
The facility model schema and validator. Generators from L0 to worlds, descriptions, controller configs, and launch graphs. All interface packages defined and reviewed *before* the implementations that use them. Lifecycle and namespace conventions established. Architecture Decision Records written for every choice in §6.

**1.C — Vertical slice: one arm, every layer**
A single xArm 5 in Harmonic, driven through the full stack: facility model → generated description → `ros2_control` with the simulation hardware plugin → MoveIt 2 → a real `Pick` skill → a behaviour tree that executes it. Thin but complete: this proves the architecture end to end before it is replicated.

**1.D — The three-arm virtual line**
Three arms, conveyors, and sensors — all instantiated from the facility model, not hand-placed. Real motion, real grasping, real sensor-triggered transitions, real handoff negotiation between robots. The line runs a continuous cycle without intervention. *This is the workload the previous iteration aimed at and never reached.*

**1.E — Documentation and quality gates**
Per-layer architecture documentation. Interface reference. Onboarding guide that a new contributor can follow to a running system unaided. Full test pyramid in place and enforced.

> **Exit criterion:** On a clean machine, `git clone` followed by a single bootstrap command produces a running three-robot line in Gazebo Harmonic that executes a continuous, sensor-driven pick-and-transfer cycle. CI is green. The entire cell layout is changeable by editing the facility model alone. Every architectural decision is written down.

---

### Phase 2 — Physical integration and twin synchronization (L1 → L2)

Physical xArm hardware interface behind the same `ros2_control` boundary. Safety layer and E-stop path. Mode switching between `SIM`, `REAL`, `SHADOW`, and `VALIDATED`. Calibration and spatial registration between the physical cell and the model. The twin monitor publishing live divergence metrics.

The architecture is designed for heterogeneous, incrementally-arriving hardware: the system runs correctly with one physical arm and two simulated ones, and gains arms without structural change.

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
| How should an AI agent behave here? | `CLAUDE.md`, `AGENTS.md`, `.claude/orchestration.md` |
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
| 1.3 | 2026-08-24 | §7 repository structure brought back in line with the tree and given an explicit meaning: it describes the **target** structure, with markers for what does not yet exist (`model/`, `workspace/src/`, `hmi/`) and what is temporary (`legacy/`). Added `tools/`, `requirements/`, `docs/reference/`, `.devcontainer/`, `.github/` and `legacy/`; corrected the claim that `infra/` holds the devcontainer and CI, which live at the repository root because their tooling requires it. Removed `subagents/`, the portable upstream template library the active roles were adapted from — it was never tracked in git and is no longer present; the adapted roles in `.claude/agents/` are the only roster. §10.2 updated accordingly: the two roles deferred to Phase 4 will be written then rather than carried as dormant templates. No change to scope, architecture, technology baseline, or roadmap. |
| 1.2 | 2026-08-24 | Documentation tree written. Twin maturity levels renamed to align with the established literature: L1 `Mirror`→`Shadow`, L2 `Shadow`→`Validated`, with the corresponding L5 operating modes renamed to match (§2, §5). Architecture aligned with the ISO 23247 reference architecture (§2). The xArm Jazzy/Harmonic risk is closed following verification (§13). §11 documentation map expanded to the full tree and the status-marker convention introduced. No change to scope, layer architecture, technology baseline, or roadmap. |
| 1.1 | 2026-08-24 | Agent configuration integrated. Added `.claude/` and `subagents/` to the repository structure (§7); replaced the agent paragraph in §10.2 with the concrete eleven-role roster, the rationale for the two domain auditors, and the two roles deferred to Phase 4. No change to scope, architecture, technology baseline, or roadmap. |
| 1.0 | 2026-08-24 | Initial charter. Establishes project identity, twin maturity model, scope, engineering principles, layered architecture, technology baseline, repository structure, five-phase roadmap, quality gates, and working model. Supersedes all prior planning documents. |
