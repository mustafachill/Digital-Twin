# What We Are Doing

**The CITE Digital Twin — project charter, architecture doctrine, and roadmap.**

| | |
|---|---|
| **Owner** | Center for Innovation, Technology and Entrepreneurship (CITE), Sam Houston State University |
| **Document version** | 1.17 |
| **Date** | 2026-10-02 |
| **Status** | Active — this is the authoritative source of truth |

---
## 0. How to read and maintain this document

**This document answers three questions and nothing else:** *What are we building? Why is it built this way? Where are we in that plan?*

- **It is the entry point.** Anyone joining the project — a new student, a new engineer, an AI agent, a stakeholder — reads this first. If something about the project's direction is not answered here, this document has a gap and the gap is a bug.
- **It is deliberately stable.** It describes intent, architecture, and phases. It does not describe today's build errors, this week's tickets, or API signatures. Those live elsewhere (§11).
- **It changes only by decision, never by drift.** Every edit must correspond to a real decision about the project's direction, must bump the version number, and must be recorded in §14 as one line. Small factual corrections are exempt from the version bump but not from being correct.
- **It holds no measurements and no decision records.** A figure belongs to a measurement campaign under `docs/measurements/`, or to a past milestone's `MEASUREMENTS.md` (see `projects/README.md`); the reasoning behind a decision belongs to its ADR in `docs/adr/`. This document names a decision and cites its record. What this document said before that rule — every earlier §14 entry in full, and every passage removed when the rule was introduced — is kept verbatim in `docs/reference/charter-history.md`.
- **`CLAUDE.md`'s §4, §9 and §12 are charter-level rules**, changed only by the project owner's decision, exactly as this document is.
- **Everything else in the repository must agree with this document.** Where code, configuration, or another document contradicts this one, this one is right and the other is wrong — either the other artifact gets fixed, or a decision is made and recorded here first.

---

## 1. What the CITE Digital Twin is

The CITE Digital Twin is a **facility-scale digital twin of the Center for Innovation, Technology and Entrepreneurship**, built on ROS 2 and Gazebo, whose first and deepest instrument is a **robotic work cell built around a UFACTORY xArm 5** on a linear track.

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

These levels are deliberately aligned with the established literature rather than invented: L0 and L1 correspond to Kritzinger's *digital model* and *digital shadow*, and L3 onward to a full *digital twin* with automated bidirectional flow. L2 is our own refinement — a digital shadow that additionally proves its own accuracy — because a shadow whose error nobody measures is an assertion rather than a twin. The architecture is aligned with the ISO 23247 reference architecture for manufacturing digital twins; the standard and its sources are in `docs/reference/standards.md`, and the layer-by-layer mapping is to be rewritten when L6 and L7 are built (ADR-0016).

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

### 6.1 Migration work this baseline created

Four consequences of the baseline were identified before the rebuild started, so that they were planned rather than discovered. All four are done:

1. **The conveyor plugin was rewritten** as a first-party Gazebo Sim system plugin with a typed ROS 2 interface, in `cite_simulation`. The IFRA plugin used previously was a Gazebo Classic plugin and would not load in Harmonic.
2. **xArm support on Jazzy and Harmonic was verified early**, by building and driving the vendor stack rather than reading about it, and the vendor source is pinned to a commit (ADR-0003; the verification is in `docs/reference/toolchain.md`).
3. **The sensor plugins were re-specified** against Gazebo Sim's sensor system and `ros_gz_bridge`; the break-beam is a `cite_simulation` system plugin of its own.
4. **World and model formats are generated, not ported** — consistent with P1, since they are generated artifacts (ADR-0021).

---

## 7. Repository structure

The repository is a monorepo. It contains the ROS 2 workspace, the facility model, the asset pipeline, infrastructure, and documentation, because these must version together.

**What is on disk today is described in `docs/architecture/repository-layout.md`, which lists only what exists.** This section gives the target shape that the layer stack in §5 implies; entries marked *target* do not exist yet, and nothing in `docs/` describes them.

- **`model/`** — L0, the facility model: the facility and its zones, asset types and instances, the process topology, the robot programs the cell runs, and the JSON Schemas that validate them.
- **`workspace/src/`** — the ROS 2 workspace, one package per responsibility: typed interfaces (`cite_interfaces`); every artifact generated from L0, committed and never hand-edited (`cite_generated`, ADR-0021); descriptions and meshes (`cite_description`); the facility's runtime services (`cite_facility`); hardware interfaces and controller bring-up for L2 (`cite_hardware` and `cite_control`, *target*); robot-agnostic skills for L3 (`cite_skills`); behaviour-tree orchestration for L4 (`cite_orchestration`, *target* — the line built in Phase 1 is kept under `projects/`); twin synchronization for L5 (`cite_twin`); telemetry and recording for L6 (`cite_telemetry`, *target*); interlocks and limits (`cite_safety`, *target*); simulation systems (`cite_simulation`); composed launch entry points (`cite_bringup`); and process-lifecycle mechanism (`cite_runtime`, ADR-0034). Packages that exist only to test the production tree, such as `cite_test_hardware` (ADR-0040), are deliberately not part of this structure.
- **`tools/`** — host-agnostic Python tooling: the L0 validator, the generators and the asset pipeline, with no ROS dependency.
- **`assets/`** — L1 meshes and the scan pipeline. Raw capture data is fetched, not committed.
- **`hmi/`** — L7, the web operator interface (*target*, Phase 4).
- **`infra/`, `.devcontainer/`, `.github/`, `external/`, `requirements/`, `scripts/`** — the container environment, CI, pinned third-party sources and patches, host dependencies, and the one-command-per-task contract every tool and agent invokes.
- **`tests/`** — system- and scenario-level tests.
- **`projects/`** — frozen, runnable snapshots of milestones the main tree has moved past; records, not sources (ADR-0068).
- **`docs/`** — decision records, per-layer design of what is built, interface reference, operations, onboarding, measurement campaigns and reference material.

### 7.1 Naming and namespace convention

```
/cite/<zone>/<asset_id>/<interface>
```

Deterministic, generated from L0, identical in simulation and on hardware. Frame identifiers follow the same rule. No asset name is ever written by hand in two places.

---

## 8. Roadmap

Phases are sequential in dependency, but **Phase 3's asset work is parallelizable** with Phases 1–2 because it is content production, not code, and does not block the software track.

Each phase has a hard **exit criterion**. A phase is not complete because the calendar says so; it is complete when its exit criterion is demonstrated.

### How we got here

The project began as a simulation that had reached L0 and could not be extended (§12). It was rebuilt from zero rather than migrated (ADR-0001), and the rebuild has passed through four shapes. Each earlier shape is kept as a frozen, runnable snapshot under `projects/`, introduced in `projects/README.md`, and its measurements are kept with it.

1. **The three-arm, event-driven line.** Phase 1 built the whole stack — the generated facility model, `ros2_control`, MoveIt 2, robot-agnostic skills and behaviour trees — and proved it on three arms carrying work-pieces along three belts, each transition triggered by a break-beam and each part held by friction alone. It is the line Phase 1's exit criterion names, and it closed that phase.
2. **One arm, paired.** The project then narrowed to what a twin is for: one cell with one of everything, brought up twice — a plant and a virtual counterpart — joined under a pair supervisor and served by an L5 twin boundary (ADR-0059, ADR-0047, ADR-0057). The first program to drive both sides was a fixed sequence of taught joint poses, sent through the boundary from one client (ADR-0066, since superseded).
3. **The real program, on a track.** The taught poses were replaced by the real xArm 5's own program, read from the file the vendor's tool exports, with the arm riding a linear track as it does on the real cell (ADR-0067). The twin runs what the robot runs.
4. **The main tree.** The line and its cell were removed from the main tree (ADR-0069), which now carries only the final project, built so that one signal will drive one real and one virtual xArm 5 with the same code. Today both sides are digital, in Gazebo, and one signal drives both; putting the physical cell behind one of them is Phase 2.B.


---

### Phase 1 — Foundation, architecture, and the virtual line

*The rebuild. Everything correct, from zero. This phase produces the platform that every later phase stands on.*

**All five sub-phases are complete, and the exit criterion is met (2026-08-28).** Each sub-phase below keeps its original text — the record of what the phase reached for — with a note on what was actually delivered wherever the two differ. The evidence that closed the phase — the CI run, the clean-clone walk, the layout-change check, and a scenario that failed inside the green run — is a measurement record and is kept with the three-arm line's snapshot (`projects/README.md`). Read it before citing the closure: a run that is green and a system that works are not the same statement.

**1.A — Toolchain and repository foundation — COMPLETE**
Ubuntu 24.04 / Jazzy / Harmonic baseline stood up. Docker and devcontainer images. External dependencies declared in a manifest with pinned revisions and reviewable patches. `rosdep` complete. CI pipeline building and testing headlessly. Repository restructured per §7. Coding standards, linting, and formatting enforced automatically. Early verification of xArm support on the target stack.

> *Delivered as written.* `xarm_ros2` is pinned to a commit and was built and driven against this stack rather than inspected (`docs/reference/toolchain.md`), and the CI pipeline has been observed building and testing headlessly.

**1.B — Architecture and contracts — COMPLETE**
The facility model schema and validator. Generators from L0 to worlds, descriptions, controller configs, and launch graphs. All interface packages defined and reviewed *before* the implementations that use them. Lifecycle and namespace conventions established. Architecture Decision Records written for every choice in §6.

> *Delivered, and wider than written.* The generators also produce MoveIt configuration, the planning scene, static frames, process topology and the bring-up plan. `./scripts/validate-model` diffs the committed output against a fresh generator run and regenerates under a different hash seed to prove byte-identical output (**ADR-0021**).

**1.C — Vertical slice: one arm, every layer — COMPLETE**
A single xArm 5 in Harmonic, driven through the full stack: facility model → generated description → `ros2_control` with the simulation hardware plugin → MoveIt 2 → a real `Pick` skill → a behaviour tree that executes it. Thin but complete: this proves the architecture end to end before it is replicated.

> *Delivered.* The grasp was held by friction alone, with no simulation aid (**ADR-0029**), and the friction-grasp campaign in `docs/measurements/` found it repeatable in **position and not in orientation**. The simulation has since been told what the skill layer decides it holds, rather than guessing (**ADR-0065**).

**1.D — The three-arm virtual line — COMPLETE, with one phrase not delivered as written**
Three arms, conveyors, and sensors — all instantiated from the facility model, not hand-placed. Real motion, real grasping, real sensor-triggered transitions, real handoff negotiation between robots. The line runs a continuous cycle without intervention. *This is the workload the previous iteration aimed at and never reached.*

> ***"Real handoff negotiation between robots" was not delivered in the sense the phrase reaches for, and this is not being redefined to match what was built.*** What was built is **conveyor-mediated**: every edge in the topology passed through a belt, and the line refused a direct arm-to-arm edge at plan time. **ADR-0031**'s correction is the part to read — the receiving gripper squares a free part up as it closes on it, and a direct handoff denies exactly that.
>
> **What *was* delivered:** three arms, belts and break-beams instantiated from L0 and not hand-placed; real motion under MoveIt; a friction grasp; and sensor-triggered transitions, a beam edge stopping and restarting a belt (**ADR-0032**, **ADR-0033**). The line ran a continuous cycle without intervention, which is the sub-phase's last sentence. **How reliably it ran was measured thinly**, and those figures are kept with its snapshot rather than here.

**1.E — Documentation and quality gates — COMPLETE**
Per-layer architecture documentation. Interface reference. Onboarding guide that a new contributor can follow to a running system unaided. Full test pyramid in place and enforced.

> *Delivered.* Every architecture and interface document carries a `DESIGNED` / `PARTIAL` / `BUILT` marker, which `./scripts/doctor` checks for presence, so a specification cannot be read as a description. The onboarding guide was walked from a fresh clone rather than reviewed, and the gates are enforced by CI as well as by the local quality gate.

> **Exit criterion:** On a clean machine, `git clone` followed by a single bootstrap command produces a running three-robot line in Gazebo Harmonic that executes a continuous, sensor-driven pick-and-transfer cycle. CI is green. The entire cell layout is changeable by editing the facility model alone. Every architectural decision is written down.

**Exit criterion status — met.** Phase 1 is **closed**. Four of the five clauses were demonstrated, and the evidence for each is in the three-arm snapshot's measurement record. The fifth — *every architectural decision is written down* — cannot be closed as stated: it is a universal no check establishes, and **ADR-0031** records a decision that existed only in a commit message until after the fact. It is read as *the decisions we know of are recorded*. The clause *CI is green* closed on one run; *repeatably green* is a separate claim, and Phase 2 inherits it.

---

### Phase 2 — Physical integration and twin synchronization (L1 → L2)

Physical xArm hardware interface behind the same `ros2_control` boundary. Safety layer and E-stop path. Mode switching between `SIM`, `REAL`, `SHADOW`, `VALIDATED` and `VIRTUAL_LEAD` — the last being the operator-facing flow in which the simulated side is commanded and the far side follows and actuates, added for Phase 2.A and specified in ADR-0041. Calibration and spatial registration between the physical cell and the model. The twin monitor publishing live divergence metrics.

**Phase 2 is delivered in two sub-phases, and the split is deliberate: the twin mechanism is built and exercised before any hardware exists, and only then is hardware put behind it.**

**2.A — The twin mechanism against a virtual counterpart — IN PROGRESS: the pair comes up and the real program runs on it; nothing automated brings it up**
The plant is paired with a **virtual counterpart**: a complete second simulation of the same cell, generated from the same L0 model and modelled *as if it were physical*. **The paired cell is `cell_b` — one xArm 5 on a linear track, one conveyor, one of everything — and both sides are digital (ADR-0059).** What 2.A delivers is the mechanism the twin is made of: mode switching and command routing, the mirroring path, and the monitor that will later compute fidelity, all exercised end to end before any hardware exists. That the counterpart is a full second simulation rather than a kinematic echo or a replayed trajectory is **ADR-0041**; the two defect classes that exist only because there are two sides are **ADR-0042** (transport partitioning per side) and **ADR-0043** (both sides held to the wall clock); and the twin boundary that serves a running pair is started by the pair supervisor on the join rather than by a launch file, which is **ADR-0057**. What a second world costs is a campaign, `docs/measurements/2026-08-28-second-world-cost/`, taken on the three-arm cell.

> **Both sides are simulated by refusal, not by convention, and this is what stands between 2.A and a physical machine today.** ADR-0048 clause 1 makes an asset whose two sides name different backends an **ERROR** at validate time, and a physical plant on a paired zone a second ERROR. **So the L5 command path cannot reach a physical actuator by any edit to the L0 model** — what protects it is a validate-time refusal rather than a safety layer, and that distinction must be carried rather than smoothed over. Lifting it is Phase 2.B's work.

> **What 2.A cannot claim, stated here rather than discovered later.** 2.A closes **no clause** of the exit criterion below, and **no number it produces is a fidelity measurement**. Both sides run the same L0 model, the same generated description and the same physics solver, so divergence measured across the pair is instrument, solver and scheduling noise; it is not a reality gap and does not become one by being plotted. Under §2's maturity model 2.A stays at level **L0**, however much of L5 it exercises: L1 and L2 are each defined by an information flow from the physical, and 2.A has no physical side. **2.A validates the instrument; 2.B is what first uses it.**

> **What exists.** `./scripts/sim --pair` starts two independent launches and **joins** them — it does not sequence them — on a token each side prints from its own readiness witness, under a supervisor that owns the join and the pair's lifetime and holds no ROS context (**ADR-0047**). Each side has its own ROS domain and its own Gazebo partition under identical names (**ADR-0044**, **ADR-0042**), and the L5 twin boundary starts on the join. `./scripts/program` runs the real xArm 5's program through that boundary, so one client drives both arms and both tracks (**ADR-0067**).
>
> **What is not built, in the same breath.** There is **no paired scenario** — `launch_test` with `IncludeLaunchDescription` is one process holding one context on one domain — so **nothing automated brings a pair up**, and a regression in the witness, the token, either side's bring-up or the boundary fails no gate. **2.A produces no fidelity number**, exactly as the note above says it cannot. And **ADR-0043's real-time requirement is not shown to be met**: **ADR-0049** restates it as a capacity measurement plus a clock-deficit budget, sets neither of its two thresholds, and is `Proposed`. What the capacity campaigns under `docs/measurements/` show is theirs to state, with their qualifications, and is cited rather than copied. None of this closes any clause of the exit criterion below, which is why this sub-phase is marked in progress.

**2.B — The real cell replaces the stand-in**
The counterpart is replaced by physical hardware behind the same `ros2_control` boundary, and what the plant talks to across the twin boundary does not change shape — that is what 2.A is built to guarantee (P2) and 2.B is the first test of it. **The first fidelity measurement in this project is produced here**, and the exit criterion below is closed in 2.B or not at all.

The architecture is designed for heterogeneous, incrementally-arriving hardware: the system runs correctly with a mix of physical and simulated arms, and gains arms without structural change.

**`VIRTUAL_LEAD` pulls a direction forward and not a level.** §2 places virtual → real at maturity L3 and this roadmap places L3 in Phase 5, so naming the mode here is deliberate and is stated rather than assumed. What Phase 5 owns is the *validation gate* — no behaviour reaching hardware without passing automated validation in the twin — and `VIRTUAL_LEAD` has no such gate; it carries the direction alone. In Phase 2.A the far side is a second simulation, so nothing physical can move under it, and the level is L0 whichever mode is in force. What gates it against a physical far side is the refusal already in the tree: bring-up refuses a plan on which any (asset, side) declares it commands physical hardware, unless `CITE_ALLOW_HARDWARE=1` is set (ADR-0054). **The exit criterion below is unchanged, and no clause of it is closed by any of this.**

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
- Copying code or values from `projects/` into the main tree — snapshots are records, not sources (ADR-0068).

---

## 10. How we work

### 10.1 Team

The engineering team operates under CITE. This document defines *what* is built and *why*; assignment, scheduling, and prioritization are CITE's management responsibility. Phases are sized to be independently ownable so that work can be parallelized across the team without contention.

### 10.2 AI agents in the workflow

AI agents are first-class participants in this project, with defined roles and defined limits. `CLAUDE.md` is the canonical rulebook loaded by every session and every agent; `AGENTS.md` points to it. The roles, the pipeline they form and the local tooling that defines them are described in `docs/onboarding/development-workflow.md`.

The operating rules:

- **Agents propose; humans and tests decide.** No agent output merges without review and passing CI.
- **Agents are bound by this document.** An agent that produces work contradicting §4 or §9 is producing a defect.
- **Specialist review is routine, not exceptional.** Architecture, testing, security, dependency, and performance review agents run against changes as part of the normal flow rather than on request.
- **Documentation is written by the orchestrating session, when it needs writing, and verified by humans; there is no documentation agent.** Drift between code and documentation is treated as a defect (P7).

### 10.3 Change control

Change control is `CLAUDE.md` §12. An Architecture Decision Record (`docs/adr/`) captures every significant technical decision — context, options considered, decision, consequences — and is written *before* the decision is implemented. Commits and pull requests describe intent and reference the ADR or phase item they serve. This document is updated when direction changes, and only then (§0).

---

## 11. Where things are written down

| Question | Where |
|---|---|
| What are we building, why, and how did we get here? | **This document** |
| What are the rules for working here? | `CLAUDE.md` |
| Why was this technical choice made? | `docs/adr/` — one record per decision |
| What is in the repository, and where? | `docs/architecture/repository-layout.md` |
| How does layer *X* work in detail? | `docs/architecture/` — for the layers that are built |
| What is the shape of this interface? | `docs/interfaces/` and the interface packages |
| What number backs that claim? | `docs/measurements/` — one campaign per question |
| What did an earlier milestone do, and how was it measured? | `projects/` — each snapshot's `PROVENANCE.md` and `MEASUREMENTS.md` |
| How do I get started? | `docs/onboarding/getting-started.md` |
| How do we work day to day, and which agents take part? | `docs/onboarding/development-workflow.md` |
| What does this term mean here? | `docs/onboarding/glossary.md` |
| How do I bring up or recover the cell? | `docs/operations/` |
| Where do I read more? | `docs/reference/` — standards, literature, toolchain |
| What did this document say before? | `docs/reference/charter-history.md` |
| How should an AI agent behave here? | `CLAUDE.md` and `AGENTS.md` (committed); `.claude/orchestration.md` (local, not committed) |
| What is open right now? | `docs/open-work.md` — **not** this document |

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
| ~~xArm ROS 2 support on Jazzy/Harmonic is incomplete~~ **Closed** | — | Verified against the target stack, and the vendor source is pinned to a commit. See ADR-0003 and `docs/reference/toolchain.md`. |
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
| 1.17 | 2026-10-02 | Measurements and decision records leave this document (§0). §7's tree moves to `docs/architecture/repository-layout.md` and §10.2's roster to `docs/onboarding/development-workflow.md`; §10.3 points at `CLAUDE.md` §12; §8 gains *How we got here*. Earlier entries and every removed passage are archived in `docs/reference/charter-history.md`. §1's work cell is named as the xArm 5 cell the main tree builds, and §9.1 gains the `projects/` prohibition CLAUDE.md §4 already carries. |
| 1.16 | 2026-10-02 | The `docs-writer` agent leaves the roster (§10.2). |
| 1.15 | 2026-10-01 | The three-arm line, its services and zone `cell_a` leave the main tree and stay runnable under `projects/` (ADR-0069). |
| 1.14 | 2026-09-29 | §7 gains `projects/`: frozen, runnable milestone snapshots (ADR-0068). |
| 1.13 | 2026-09-18 | The twin is built on `cell_b`, paired, both sides digital; the three-arm cell is set aside (ADR-0059). |
| 1.12 | 2026-09-01 | A throttled real-time figure is withdrawn and claims about `cite_twin` corrected (ADR-0049, ADR-0028, ADR-0043, ADR-0050). |
| 1.11 | 2026-08-31 | Phase 2.A gains a progress marker; one §8 clause is reworded (ADR-0047, ADR-0044, ADR-0042). |
| 1.10 | 2026-08-30 | A false causal attribution in §8 is struck (ADR-0045, ADR-0046, ADR-0038). |
| 1.9 | 2026-08-29 | Phase 2 splits into 2.A and 2.B; `VIRTUAL_LEAD` is added as a sixth mode (ADR-0041, ADR-0011). |
| 1.8 | 2026-08-28 | Phase 1 is closed; test-only packages stay outside §7's production tree (ADR-0040). |
| 1.7 | 2026-08-27 | §7 gains `cite_runtime` (ADR-0034). |
| 1.6 | 2026-08-27 | Phase 1's record is closed; 1.D's handoff phrase is recorded as not delivered as written; `legacy/` is removed (ADR-0031, ADR-0001). |
| 1.5 | 2026-08-25 | §7 is brought in line with the workspace (ADR-0021, ADR-0025). |
| 1.4 | 2026-08-24 | `.claude/` is marked as local tooling, not committed. |
| 1.3 | 2026-08-24 | §7 is declared the target structure. |
| 1.2 | 2026-08-24 | Documentation tree written; maturity levels renamed; ISO 23247 alignment; xArm risk closed (ADR-0011, ADR-0016, ADR-0003). |
| 1.1 | 2026-08-24 | The agent roster joins §10.2. |
| 1.0 | 2026-08-24 | Initial charter. |

Each entry up to 1.16 is given in full in `docs/reference/charter-history.md`.
