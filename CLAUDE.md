# CLAUDE.md

Canonical working agreement for this repository. Auto-loaded into every session and every
subagent. **This file is the rulebook; `what-we-are-doing.md` is the reason.** When you
need to know *why* a rule exists, read the charter. When you need to know *what to do*,
this file is enough.

`AGENTS.md` points here. Do not duplicate this content anywhere else.

---

## 1. What this is

The **CITE Digital Twin** — a facility-scale digital twin of the Center for Innovation,
Technology and Entrepreneurship at Sam Houston State University, built on ROS 2 and
Gazebo, whose first instrument is a multi-robot xArm work cell.

It is a *twin*, not a simulation: real hardware and the virtual model share one control
interface, and the system continuously measures how far the model is from reality.

Full charter — identity, scope, architecture rationale, roadmap: **`what-we-are-doing.md`**.

## 2. Current state — read this before assuming anything exists

The project is in **Phase 1 of a rebuild**. The charter describes the target; the
repository is partway there. Check before assuming.

- **Phase 1.A is closed.** Container image, the `./scripts/*` contract, dependency
  manifests, CI, and the asset policy all exist and work. `external/cite.repos` pins
  `xarm_ros2` to a commit SHA, after the branch was built and driven against our stack
  rather than merely inspected — see the verification table in
  [`docs/reference/toolchain.md`](docs/reference/toolchain.md). `./scripts/doctor` exits 0;
  run it to see the state of any machine.
- **The L0 model and its generators are built and proven** (Phase 1.B). `model/` describes
  the three-arm cell — seven asset types, fourteen instances, five stations; the seventh
  type is the reference work-piece, which has no instances on purpose (ADR-0030) — and
  `workspace/src/cite_generated/` holds everything derived from it: descriptions, the
  world, controller configuration, MoveIt configuration, the planning scene, static frames,
  process topology and the bring-up plan. That directory is **generated in its entirety and
  must never be hand-edited** (ADR-0021). `./scripts/validate-model` diffs it against a
  fresh generator run *and* regenerates in a second interpreter under a different hash seed
  to prove the output is byte-identical; it exits 0. `tools/tests/` holds **215** tests at
  this commit, counted by collection rather than by a run.
- **Seven first-party packages exist**, and `workspace/src/external/` adds the twelve from
  `xarm_ros2`. `./scripts/build` is a blocking CI step. The seven are `cite_interfaces`,
  `cite_facility`, `cite_generated`, `cite_bringup`, `cite_skills`, `cite_orchestration`
  and `cite_simulation`. **`cite_twin`, `cite_telemetry`, `cite_safety`, `cite_description`,
  `cite_control` and `cite_hardware` do not exist.**
- **The simulated cell comes up.** `./scripts/sim --headless` brings the scene and three
  arms into Gazebo Harmonic with nine controllers active, one `move_group` and one skill
  server per arm, one detection server for the zone, the generated planning scene applied
  and read back, the facility's model version, frames and topology served, and one
  `ros_gz_bridge` carrying `/clock` plus every belt and beam topic the generated plan
  declares. The L4 coordinator is **off unless `line:=true`**, because it takes exclusive
  hold of each arm's skills. `./scripts/scenario bringup` asserts the bring-up and is a
  blocking CI gate, run twice per CI run.
- **One arm now picks and places a work-piece, and friction alone holds it.** ADR-0029
  removed the contact-triggered attachment plugin, so nothing on the simulation side
  assists a grasp: the pads close on the part, stall on it, and the controller reports
  `stalled=true, reached_goal=false -> holding` — the evidence ADR-0022 shaped the gripper
  path around.
  **The cycle passed 6 of 6** in the measurement the implementing agent took for this
  commit, every run reporting a genuine friction stall. That is six runs in one isolated,
  freshly built tree on one machine on 2026-08-26; earlier independent sets are *reported*
  to have passed likewise and are not re-verified here. This is not a campaign with
  pre-registered thresholds and it is not a claim about any other machine.
  The 84-trial measurement the grasp decision rests on is
  [`docs/measurements/2026-08-25-friction-grasp/`](docs/measurements/2026-08-25-friction-grasp/results.md).
  **This became true only recently, and the reason matters more than the number.** The
  belt's `infeed`/`outfeed` frames sat exactly on its collision box's end planes, so a
  released 50 mm cube was neutrally stable, tipped, and fell — the cycle failed **0 of 18**.
  `Pick` was never affected because the table's surface frame sits at the **centre** of its
  top face. The frames moved 50 mm inboard, the arm standoff 0.350 → 0.300 m, and L0 gained
  the work-piece geometry that makes the rule expressible at all
  ([ADR-0030](docs/adr/0030-facility-model-describes-the-workpiece.md)).
  **Read the history before trusting a pass count.** An earlier version of this bullet said
  the cycle passed 8/8. It did not. Those runs executed another worktree's binaries through
  shared Docker volumes, and the number reached this file because it was supplied rather
  than measured. Each checkout is now isolated and `lint`/`test` refuse to answer from a
  stale build tree — **measure it yourself anyway.**
  **Do not read any of this as a green scenario.** In the 6 runs above the *scenario
  verdict* was **5 of 6**: one run passed the cycle and then failed the post-cycle teardown
  check. That failure was on a **fourth distinct process**, after `parameter_bridge` (-6),
  `gz` (-9) and `topology_server.py` (1) on earlier runs — so **process identity does not
  predict it**, and the fourth is further evidence rather than a new symptom. The one
  candidate that has ever looked like a predictor is **run duration** — in an earlier set of
  five the failing run was the slowest — and that is a suggestion from a handful of runs, not
  a result. The cause is not established, **no exemption has been added or widened**, and
  `./scripts/scenario pick_and_place` runs in CI as `continue-on-error` at this commit.
- **The line completes, and this is the newest and least-settled claim in this file.**
  `./scripts/scenario continuous_line` drives the three-arm sensor-driven line: the aid
  topics are bridged, `Detect` turns a beam level into a typed `DetectionEvent`, L4 stops
  the belt on that edge and restarts it on `CompleteHandoff` (ADR-0032), and the beam
  indexes on the part's body rather than its origin (ADR-0033).
  **Measured by the implementing agent at this commit:** the milestone ladder reached
  **10 of 10** where it had been stuck at 4 of 10; **nine of twelve** pieces traversed every
  milestone; **two of four** runs carried all three pieces end to end; and all four beams
  fired at every station in every run. **That is one agent's four runs on one machine, not a
  campaign** — no thresholds were registered in advance, and an independent verification was
  in flight when this was written whose count is **not recorded here**. `continuous_line`
  runs in CI as `continue-on-error`.
  **It is not finished.** One run had a piece stall at 8 of 10 after `arm_3` closed on air
  at `conveyor_2`'s outfeed, following the loosest grasp recorded anywhere — the full cube
  width, no compression. The stated hypothesis, and it is a hypothesis: a leading-edge test
  makes the index position depend on the part's **yaw**, so a square part arriving yawed
  parks a few millimetres short. That sensitivity is **real on hardware** — a physical
  photo-eye behaves the same way — and must not be described as a simulation artefact or
  compensated in the beam. It belongs to the release-orientation residual, and
  [`docs/measurements/2026-08-26-conveyor-yaw-transfer/`](docs/measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
  lists **whether that residual accumulates over three stations as explicitly unmeasured**.
- **What does not work, stated plainly** (Phase 1.C/1.D, in progress):
  - **A grasp holds a position, not an orientation, and the two published residuals are
    different quantities.** Correcting the grasp-plane offset took rotations above 20° from
    60% to 0% of trials and left a residual —
    [`docs/measurements/2026-08-25-grasp-plane-offset/`](docs/measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md).
    **That residual, up to 18.7°, is a *roll* about the pad-to-pad axis, not a yaw.**
    Re-analysed on 2026-08-26 over 72 committed carries: every net carry rotation lies along
    the pad-to-pad axis, the component about the world vertical never exceeds 0.49°, and the
    trial that *is* the published 18.71° has a vertical component of 0.01°. **The yaw figure
    is 10.62°**, from the conveyor-yaw campaign's twelve end-to-end trials. An angle without
    an axis is not a measurement of anything — do not put 18.7° into anything that only a
    yaw can enter.
    **The offset correction is in the tree**, in the place the campaign said it belonged:
    L0's end-effector `linkage` block declares the vendor dimensions and the L3 skill server
    derives the offset from them. Per ADR-0029 a scenario may assert where a part ends up and
    **may not assert how it is held**.
    **L4 does still refuse a direct arm-to-arm handoff, and the residual is no longer the
    stated reason.** ADR-0031 was corrected on 2026-08-26: nothing re-observes the part, and
    what makes the *permitted* conveyor edge safe is the receiving gripper closing on a free
    part — which a direct handoff denies. Read that ADR's correction section before writing
    about either case. The refusal string in `line_plan.hpp` still carries the pre-correction
    reasoning.
  - **`Transfer` has a server and no caller.** Today's L0 topology is conveyor-mediated and
    L4 refuses a direct arm-to-arm edge at plan time (ADR-0031).
  - **L4's own tests move no arm.** `line_orchestrator` derives one subtree per station from
    `LineTopology` and owns handoff, recovery and `LineState`; its unit and launch tests use
    fake action servers that succeed because they are told to, so what they prove is
    **sequence and ownership**, not motion. Motion is evidenced only by the scenario above.
  - **The belts are commanded open-loop.** `ConveyorState` exists in `cite_interfaces` to
    make commanded and measured speed disagree visibly, and **nothing publishes it**; the
    bridge carries a bare `std_msgs/Float64` each way. A belt that fails to stop, or fails
    to restart, is a spilling or a stalled line that nothing notices.
  - **Scenarios are not deterministic.** `CITE_PHYSICS_SEED` reaches `gz sim --seed`, which
    seeds sensor noise and nothing else — not the physics solver, not the planner. See
    `docs/architecture/cross-cutting-testing.md` and ADR-0027 before writing anything about
    determinism.
  - **ADR-0027's Pilz pipeline is decided and not implemented.** Every generated
    `*_ompl_planning.yaml` still lists `planning_pipelines: [ompl]` and nothing else.
  - **Twelve links per arm use their visual mesh as collision geometry**, which §10 below
    names as a defect class. Real-time factor on the development host is 0.14. ADR-0028
    decides the fix and is still `Proposed`: `assets/` holds only its README and manifest.
- **The layout is `PROVISIONAL`.** The coordinates in `model/` are engineered, not surveyed.
  Charter §8 puts the physical scan in Phase 3; until then a measurement taken from this
  model does not transfer to the building, and no report should imply that it does.
- **`legacy/` holds the previous iteration (v1).** It is reference material being replaced,
  **not** a codebase to extend. Do not add features to it, fix its bugs, or treat its
  patterns as precedent. It is excluded from the build by living outside `workspace/`, and
  is deleted at the end of Phase 1. See `legacy/README.md` and charter §12.
- **The documentation is written, and its status markers are now the thing to read.** Each
  document in `docs/architecture/` and `docs/interfaces/` carries `DESIGNED`, `PARTIAL` or
  `BUILT`, with the evidence named. `DESIGNED` means the contract the code must satisfy;
  `PARTIAL` says which part is real and which is not. Read the layer document before
  touching a layer, and read its status line before believing its body.
- **Measured evidence lives in [`docs/measurements/`](docs/measurements/README.md)**, one
  directory per campaign, each with its thresholds written down before the first trial.
  This is what P8 looks like in practice. Cite a campaign; do not copy its numbers around.

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
  are identical; only the loaded `ros2_control` hardware plugin differs. Breaking this is
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

Each layer has a design document in [`docs/architecture/`](docs/architecture/README.md) —
[L0](docs/architecture/L0-facility-model.md),
[L1](docs/architecture/L1-description-and-assets.md),
[L2](docs/architecture/L2-control-and-hal.md),
[L3](docs/architecture/L3-capabilities.md),
[L4](docs/architecture/L4-orchestration.md),
[L5](docs/architecture/L5-twin-synchronization.md),
[L6](docs/architecture/L6-data-and-telemetry.md),
[L7](docs/architecture/L7-presentation.md).

Cross-cutting: [safety and interlocks](docs/architecture/cross-cutting-safety.md),
[lifecycle management](docs/architecture/cross-cutting-lifecycle.md),
[testing](docs/architecture/cross-cutting-testing.md),
[naming](docs/architecture/naming-and-namespaces.md), diagnostics, configuration, CI/CD,
security.

The architecture is aligned with the ISO 23247 reference architecture for manufacturing
digital twins — see [standards-alignment.md](docs/architecture/standards-alignment.md).

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
| `./scripts/sim [--headless]` | Launch the simulated cell |
| `./scripts/validate-model` | L0 schema validation + generator dry-run. Runs anywhere. |
| `./scripts/audit-deps` | Scan dependencies for known vulnerabilities. Read its header — it does not cover every layer. |
| `./scripts/scenario [name]` | Headless simulation-in-the-loop scenario; no argument lists them |
| `./scripts/enter [dev\|gui\|hardware] [command...]` | Interactive shell in the container; with a trailing command, runs it there and exits |
| `./scripts/fetch-assets` | Download large assets declared in `assets/manifest.yaml` |
| `./scripts/clean [--all]` | Remove build artifacts |

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
  silently and delivers nothing — the most common silent failure in ROS 2.
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
