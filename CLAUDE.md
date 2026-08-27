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

It is also a **rebuild**. A first iteration (v1) was archived under `legacy/` and deleted at
the end of Phase 1; it survives only in version control, and **its patterns are not
precedent** — do not reintroduce them. What it taught is
[`docs/reference/v1-lessons.md`](docs/reference/v1-lessons.md); why it was replaced rather
than migrated is [ADR-0001](docs/adr/0001-rebuild-rather-than-migrate.md); the debt that
forced the decision is charter §12.

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
  to prove the output is byte-identical; it exits 0. `tools/tests/` holds **222** tests at
  this commit, counted by collection rather than by a run
  (`pytest tools/tests --collect-only -q`, 2026-08-27).
- **Eight first-party packages exist**, and `workspace/src/external/` adds the twelve from
  `xarm_ros2`. `./scripts/build` is a blocking CI step. The eight are `cite_interfaces`,
  `cite_runtime`, `cite_facility`, `cite_generated`, `cite_bringup`, `cite_skills`,
  `cite_orchestration` and `cite_simulation`. `cite_runtime` is the newest: it holds
  process-lifecycle mechanism only — signals, shutdown, spin-and-exit for `rclpy` nodes — and
  it exists rather than a helper landing in `cite_interfaces`
  ([ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md), charter v1.7).
  **`cite_twin`, `cite_telemetry`, `cite_safety`, `cite_description`, `cite_control` and
  `cite_hardware` do not exist**; those six plus the eight above are the fourteen charter §7
  lists.
  **Check the count rather than this sentence.** `./scripts/doctor`'s `workspace/src` line
  counts every `package.xml` beneath it, so it reads **8** in a checkout that has not run
  `./scripts/bootstrap` — measured on macOS on 2026-08-27 — and **20** once the manifest is
  imported, that being 8 plus the 12 `xarm_ros2` packages the manifest's own pinning note
  records building. The 20 is arithmetic here, not a reading taken in this checkout.
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
  check. Every teardown check still runs and still reports every bad exit. The account of
  that failure that stood here until 2026-08-27 has been overturned — see the teardown bullet
  below, and do not carry "process identity does not predict it" or "run duration" out of an
  older copy of this file.
  **What did change, and this file said otherwise until 2026-08-27:**
  `./scripts/scenario pick_and_place` is a **blocking** CI step, not `continue-on-error`. It
  was promoted at `c1e9e03` against its own recorded conditions. CI passes
  `--teardown-advisory` to all three scenarios, which splits the two questions a scenario
  answers in one exit code: **the cycle is gated, the post-shutdown teardown is reported and
  not gated.** The flag is off by default, so an interactive run still answers the strict
  question. Read `scripts/scenario`'s header and the phase-split block in `scripts/_lib.sh`
  before treating a teardown failure as a gate — and do not answer one by widening a
  tolerance.
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
  **Then a harness turned out to have been doing L4's job, and this is the sharpest example
  in this file of why a green run is not evidence.** ADR-0032 gave the belt setpoint an owner
  in L4 on 2026-08-26, and that owner delivered nothing. `ConveyorIndex` creates its
  publishers inside the topology callback and `run_all()` publishes from the same callback —
  **reliable QoS is a promise to *matched* subscribers, and at that instant none are
  matched**, however long the bridge has been up. The belts were being started by the
  scenario's own ten repeated sends, which the record already described as a closed gap.
  Reported by the fixing agent on 2026-08-27, measured once on one machine: with the
  scenario's publisher removed, a subscriber up for 100 s received nothing for the next 300.
  **Every `continuous_line` result above was produced with a test harness compensating for a
  defect in the thing under test.** Fixed event-driven — a subscriber matching is treated as
  an event and the belt's current setpoint is sent then, with `run_all()`'s immediate publish
  kept so an RMW without the matched event degrades to the old behaviour rather than worse.
  Two gtests fail without it and pass with it. The pass counts above are **not** re-measured
  against the fix and are left as they were reported.
  **After the fix, and this is the least-settled number here:** `continuous_line` passed
  **3 of 3** on both cycle and teardown, against a 3-of-4 and 2-of-4 baseline. That is the
  fixing agent's three runs on one machine, and the agent said in as many words that three
  runs on one machine is not a campaign.
  **The independent verification came back, and only half of it replicated.** Three further
  runs, taken by the project owner on one machine on 2026-08-27: **the cycle completed 3 of
  3, and the scenario verdict was 1 of 3.** Both failures were **teardown-only** — runs 2 and
  3 each reported `OK` from their in-flight tests and then failed the post-shutdown check. So
  the cycle figure replicated and the teardown figure did not. **That gap is the difference
  between "the line works" and "the scenario is green", and they are not the same claim.** The
  teardown half is the next bullet. Do not promote the gate on either number.
  **It is not finished.** One run had a piece stall at 8 of 10 after `arm_3` closed on air
  at `conveyor_2`'s outfeed, following the loosest grasp recorded anywhere — the full cube
  width, no compression. The stated hypothesis, and it is a hypothesis: a leading-edge test
  makes the index position depend on the part's **yaw**, so a square part arriving yawed
  parks a few millimetres short. That sensitivity is **real on hardware** — a physical
  photo-eye behaves the same way — and must not be described as a simulation artefact or
  compensated in the beam. It belongs to the release-orientation residual, and
  [`docs/measurements/2026-08-26-conveyor-yaw-transfer/`](docs/measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
  lists **whether that residual accumulates over three stations as explicitly unmeasured**.
- **The teardown flake is two failure families, not one, and what this file said about it
  was wrong until 2026-08-27.** It said the failures hit four undifferentiated processes, that
  **process identity does not predict it**, that the only candidate predictor ever seen was
  **run duration**, and that the cause was not established. A `debugger` investigation and the
  runs below overturned all four. Split by exit status, process identity predicts the family
  exactly.
  - **Exit code 1 — `topology_server.py` and `model_info.py`.** Both are `cite_facility`
    `rclpy` nodes, and both are instances of **one cause, which is established and fixed**.
    [ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md) records it: two
    upstream `rclpy` shutdown races, each link of the chain read in upstream source rather
    than inferred, each compensation carrying the condition for deleting it. **Read the ADR.**
    The mechanism is deliberately not restated here, and a second copy of it in this file
    would be the duplication P1 forbids.
  - **Signal deaths — `move_group` (×3) and `skill_server`.** Both MoveIt-linked C++, and
    **still unexplained.** The stated hypothesis, and it is only a hypothesis: `skill_server`
    holds a `shared_ptr<MoveGroupInterface>` constructed from its own node, and
    `MoveGroupInterface::getNode()` returns a `shared_ptr` reference, so a reference cycle may
    mean `~SkillServer` never runs. That is a **type-level observation, not a demonstrated
    cause** — the debugger said so in as many words, and nothing has been instrumented to show
    the destructor is skipped.
    **One member of this family is outside the exemption.** The third of the three runs below
    lost `skill_server` to -11, and the exemption in `tests/scenarios/continuous_line.py`
    covers `move_group` and
    -11 and nothing else — while the comment beside it attributes the cause to a MoveIt
    *destructor*, which is not specific to that binary. **No exemption has been added or
    widened.** Widening one to cover `skill_server` would be tolerating an undemonstrated
    cause, which is the opposite of what the split above bought.
  **Run duration is retired as a predictor.** Three `continuous_line` runs on one machine on
  2026-08-27 took **478.055 s (passed), 480.607 s (failed) and 497.710 s (failed)**. The
  longest run did fail, so duration is not *uncorrelated* — but 2.5 s separating a pass from a
  fail rules it out as the mechanism. The comment in `tests/scenarios/continuous_line.py`
  still asserts the duration correlation and has not been updated.
  **What is not accounted for here.** The superseded account also named `parameter_bridge`
  (-6) and `gz` (-9). Those two are not in the set the split above was measured over and this
  bullet does not classify them.
  Every figure in this bullet is from one machine on 2026-08-27, with **no thresholds
  registered before the runs**, and there is no directory for it in
  [`docs/measurements/`](docs/measurements/README.md). Treat them as the size of the
  evidence, not as a measurement of the defect.
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
    **This is the gap that hid the delivery defect above for ten commits**, and it is the
    reason that bullet is not merely a cost. There is no confirmation path, so "commanded"
    and "running" were indistinguishable from inside the system, and the only thing that
    could tell them apart was a scenario that was itself supplying the command. A publisher
    of `ConveyorState` — in the simulation plugin and on the hardware drive, which is L1/L2
    work — is what closes it.
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
- **The documentation is written, and its status markers are now the thing to read.** Each
  document in `docs/architecture/` and `docs/interfaces/` carries `DESIGNED`, `PARTIAL` or
  `BUILT`, with the evidence named. `DESIGNED` means the contract the code must satisfy;
  `PARTIAL` says which part is real and which is not. Read the layer document before
  touching a layer, and read its status line before believing its body.
- **Measured evidence lives in [`docs/measurements/`](docs/measurements/README.md)**, one
  directory per campaign, each with its thresholds written down before the first trial.
  This is what P8 looks like in practice. Cite a campaign; do not copy its numbers around.
- **Where Phase 1's exit criterion actually stands.** The charter states it in one sentence
  (§8, Phase 1); this is the clause-by-clause status, and one clause is blocked for a reason
  that is not technical.
  - **"On a clean machine, `git clone` followed by a single bootstrap command produces a
    running three-robot line"** — the clone-to-green half is **walked and passing**. Reported
    by the project owner on 2026-08-27, from a fresh clone of the remote into an empty
    directory rather than a worktree, **with zero deviations**: `./scripts/bootstrap`
    applied both vendor patches, `./scripts/doctor` reported **23 passed, 0 failed** with
    both patches verified present, `./scripts/build` finished **19 packages** — a figure from
    before `cite_runtime` existed; a package has been added since and the walk has not been
    repeated, so read it as 19 at that commit and not as the count today —
    `./scripts/test` was clean, and `./scripts/enter dev ./scripts/lint` was clean across
    **all eight linter labels**. Both previously-recorded clean-clone defects — the empty
    include directory that failed a fresh build, and the patch step that reported success and
    total failure identically inside a worktree — are gone. **What that walk did *not*
    include is launching the cell from the clean clone**: it ran to `lint`, and the running
    line is the next clause's evidence, measured elsewhere. *One measurement on one machine,
    not a campaign.*
  - **"…that executes a continuous, sensor-driven pick-and-transfer cycle"** — measured, and
    it is the least-settled claim in this file. See the `continuous_line` bullet above,
    including that a harness had been starting the belts and that the post-fix figure is
    three runs on one machine.
  - **"The entire cell layout is changeable by editing the facility model alone"** —
    **demonstrated.** Reported by the project owner on 2026-08-27: a pedestal was moved 50 mm
    in L0 and the tree regenerated. Five generated artifacts changed — the bring-up plan, the
    scene description, the static TF table, the planning-scene object and the model hash —
    the arm anchored to that pedestal followed it, and **nothing outside `model/` and
    `cite_generated/` changed at all.** That is P1 demonstrated end to end: a coordinate
    changed in one place and propagated everywhere it is used, with no hand edit anywhere.
    *One measurement on one machine, and it moved one asset — it is not a proof that every
    asset type propagates.*
  - **"CI is green" — CANNOT BE VERIFIED, AND NOT FOR A TECHNICAL REASON.** Triggering the
    workflow on 2026-08-27 returned *"The job was not started because recent account payments
    have failed or your spending limit needs to be increased"*, and **all three jobs —
    `host-tooling`, `ros-workspace`, `supply-chain` — were refused before starting**. That is
    an **account-level block on the GitHub Actions runner**, not a build failure, not a test
    failure, and not evidence of anything about the code. Nothing may be inferred about CI's colour from it in either direction: the last
    known CI state is not this commit's. **Do not record this clause as met, and do not
    record it as a technical gap.** It is unblocked by billing, and until then the clause is
    open.
  - **"Every architectural decision is written down"** — **34** ADRs at this commit,
    the newest being [ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md).
    **Six** are `Accepted (corrected …)` and a seventh, ADR-0023, carries a correction and
    is also superseded. Check the total against `./scripts/doctor`'s `ADR index` line, which
    reported **34 records, all indexed** on 2026-08-27, and the corrected count against the
    `Accepted (corrected …)` rows in [`docs/adr/README.md`](docs/adr/README.md) — `doctor`
    does not count those. `doctor` enforces that every ADR on disk is in the index and that
    every ADR referenced from `docs/` exists; it does **not** check that the set is
    *complete*, and no check can. That clause is a judgement, not a measurement.

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
  silently and delivers nothing — the most common silent failure in ROS 2. **Compatible QoS
  is not delivery either:** reliable is a promise to *matched* subscribers, so anything
  published in the same callback that created the publisher reaches nobody. That cost this
  project a belt setpoint that was never once delivered. Treat a match as an event, never a
  sleep or a publish loop — see
  [`docs/interfaces/qos-profiles.md`](docs/interfaces/qos-profiles.md).
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
