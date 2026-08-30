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

**Phase 1 of the rebuild is closed**, as of 2026-08-28: charter §8 records its exit
criterion MET, and records in the same place what that closure rests on and what it does
not cover. Nothing below is retired by the closure — the gap list is still the gap list.
**Phase 2 has since split into 2.A and 2.B (charter v1.9, 2026-08-29) and the first pieces
of 2.A are in the tree; nothing has ever brought a pair up.** The charter describes the
target; the repository is partway there. Check before assuming.

**Every count below names the command that reproduces it, and every figure names who
measured it and over how many runs.** That is what P7 costs, and this section is where it is
kept or lost. This file has carried a wrong asset count, a wrong pass count and a wrong
account of a flake; each was caught by someone re-running, never by someone reading.

- **Phase 1.A is closed.** Container image, the `./scripts/*` contract, dependency
  manifests, CI, and the asset policy all exist and work. `external/cite.repos` pins
  `xarm_ros2` to a commit SHA, after the branch was built and driven against our stack
  rather than merely inspected — see the verification table in
  [`docs/reference/toolchain.md`](docs/reference/toolchain.md). `./scripts/doctor` exits 0;
  run it to see the state of any machine.
- **The L0 model and its generators are built and proven** (Phase 1.B). `model/` describes
  the three-arm cell and `workspace/src/cite_generated/` holds everything derived from it:
  descriptions, the world, controller configuration, MoveIt configuration, the planning
  scene, static frames, process topology and the bring-up plan. That directory is
  **generated in its entirety and must never be hand-edited** (ADR-0021).
  `./scripts/validate-model` diffs it against a fresh generator run *and* regenerates in a
  second interpreter under a different hash seed to prove the output is byte-identical; it
  exits 0, reporting `1 zone(s), 7 type(s), 15 asset(s), 5 station(s), across 15 file(s)` in
  this checkout on 2026-08-29. The seventh type is the reference work-piece, which has no
  instances on purpose (ADR-0030).
  **Ask `./scripts/validate-model` for the cardinality; do not read it out of prose.** This
  file said "fourteen instances" until 2026-08-27 and it was fifteen — one addition, at
  `aef87e6`, falsified the number here, in L0's status line and in ADR-0027 at once, which is
  why ADR-0027's first correction ends *"do not state the cardinality of a generated
  collection in prose."*
  `tools/tests/` holds **331** tests, counted by collection rather than by a run
  (`.venv/bin/python -m pytest tools/tests --collect-only -q`, this checkout, 2026-08-29).
  It said **302** until 2026-08-29. **Collection and a run are different numbers, and so are
  these trees**: what `./scripts/test` reports is in the packages bullet below, and its host
  half walks `tests/` as well as `tools/`, so it is a larger number for a reason and not a
  correction to this one.
- **Nine first-party packages exist**, and `workspace/src/external/` adds the twelve from
  `xarm_ros2`. `./scripts/build` is a blocking CI step. Eight of the nine are
  `cite_interfaces`, `cite_runtime`, `cite_facility`, `cite_generated`, `cite_bringup`,
  `cite_skills`, `cite_orchestration` and `cite_simulation`. The ninth is
  **`cite_test_hardware`, which is test-only and deliberately not in charter §7's tree**:
  §7 is the production structure, and the package is barred from production use by its own
  `on_init` rather than by convention
  ([ADR-0040](docs/adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md),
  charter v1.8). So `cite_test_hardware` appearing on disk and not in §7's tree is the rule,
  not drift.
  `cite_runtime` holds process-lifecycle
  mechanism only — signals, shutdown, spin-and-exit for `rclpy` nodes — and exists rather
  than a helper landing in `cite_interfaces`
  ([ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md), charter v1.7).
  **`cite_twin`, `cite_telemetry`, `cite_safety`, `cite_description`, `cite_control` and
  `cite_hardware` do not exist**; those six plus the eight named above are the fourteen
  charter §7 lists. `./scripts/doctor`'s `workspace/src` line counts every `package.xml`
  beneath it, so it reads **9** before `./scripts/bootstrap` has imported the manifest —
  measured on macOS in this checkout on 2026-08-29. **The post-import figure is now measured
  at this commit**: `./scripts/build` reported `Summary: 21 packages finished` in this
  checkout on 2026-08-29, and `find workspace/src -name package.xml | wc -l` agrees at
  **21** — the nine plus the twelve. This line carried **20** until 2026-08-29, which was
  CI's figure at `60eb4a5`, before `cite_test_hardware` existed.
  **`./scripts/test` counts by a run and reports three numbers, not one**, in this checkout on
  2026-08-29: `113 passed, 0 failed (shell gate self-tests)`; `367 passed, 1 skipped` for the
  host half, which walks `tools/` **and** `tests/`, so it is larger than the `tools/tests`
  collection above; and, over the nine first-party packages, nine per-package summaries
  totalling **854 tests, 0 failures, 52 skipped**. It builds and tests the nine only — the
  twelve imported packages are built and not tested here.
- **The simulated cell comes up.** `./scripts/sim --headless` brings the scene and three
  arms into Gazebo Harmonic with nine controllers active, one `move_group` and one skill
  server per arm, one detection server for the zone, the generated planning scene applied
  and read back, the facility's model version, frames and topology served, and one
  `ros_gz_bridge` carrying `/clock` plus every belt and beam topic the generated plan
  declares. The L4 coordinator is **off unless `line:=true`**, because it takes exclusive
  hold of each arm's skills. `./scripts/scenario bringup` asserts the bring-up and is a
  blocking CI gate, run twice per CI run.
  **It is not a scenario that always passes, and until 2026-08-28 nothing said so.** Thirty
  consecutive local runs at `de67d8b` — taken for another purpose and published as
  [`docs/measurements/2026-08-27-teardown-signal-family/`](docs/measurements/2026-08-27-teardown-signal-family/results.md)
  — include runs that failed `bringup`'s own `MoveTo` assertion, not merely its teardown
  check. That campaign's note on the finding is explicit that it is **not a pre-registered
  rate** and that whether it still happens is **unmeasured**. **It still happens**: the same
  `the MoveTo goal was never accepted` assertion failed **one local run of four** on 2026-08-29,
  on the merged Phase 2.A branch, reported by the implementing agent — one more event, on one
  machine, with nothing registered in advance, and not a rate either. Against that,
  `bringup` has passed **12 of 12** in CI: it runs twice per run and the six runs listed in
  the `continuous_line` bullet below all passed it (`grep "Scenario 'bringup'"` over each
  run's `gh run view --log`, 2026-08-29). Treat a `bringup` failure as a finding to
  investigate, not as a known flake to re-run past.
- **Motion is planned by Pilz.** ADR-0027 is implemented and merged: L0 declares the
  pipeline choice and the limits, the generator emits `cell_a_arm_*_planning_pipelines.yaml`
  per arm declaring both pipelines, and the L3 skill server asks for Pilz PTP and falls back
  to OMPL **only** on a planning failure — never on an unreachable pose, and never when the
  requested planner is a Cartesian one, where the shape of the path is the contract.
  **What is proven:** an identical request returns a byte-identical trajectory from one
  `move_group`, and a PTP path through a named object in the real generated planning scene
  is refused — mutation-checked, and observed refusing a real path during `continuous_line`.
  **What is not:** same seed, same trajectory *across runs*. **LIN is configured and usable
  on one motion shape only**, and nothing in L3 asks for it. That, the measurement, and the
  fact that no error code tells a collision refusal from a geometric one are in
  [ADR-0027](docs/adr/0027-pilz-planning-pipeline.md)'s 2026-08-27 correction; the gate's own
  residual is in the gap list below.
- **A mistracked trajectory is now detected at execution, and the detector's own values are
  copied rather than measured.** Every generated `JointTrajectoryController` carries a
  `constraints:` block — `goal_time`, and per-joint `trajectory` and `goal` tolerances —
  declared on the arm type in L0 and identical on both backends
  ([ADR-0036](docs/adr/0036-execution-side-trajectory-tolerances.md)). Until it existed every
  tolerance was `0.0`, `0.0` disables the comparison, and **a physically obstructed arm ran
  the trajectory to its end and reported `SUCCESSFUL`** — silence that reached `Pick` as a
  successful pick. A launch test drives two real controller managers over mock hardware and
  requires a tracked trajectory to succeed, a held joint to abort as
  `PATH_TOLERANCE_VIOLATED`, and an error between the two thresholds to abort as
  `GOAL_TOLERANCE_VIOLATED`.
  **It is a detector, not a protective measure**, and must never be cited as one: it reports
  after the fact, and what stops an arm driving into a fixture is the vendor controller's
  torque limiting and physical guarding (charter §3.2).
  **The values are UFACTORY's, recorded as copied**, and ADR-0036's 2026-08-27 correction is
  where the residuals live — including that `stopped_velocity_tolerance` is structurally dead
  on a position-only command interface. What is unmeasured is in the gap list below.
- **An execution abort is classified before any recovery motion is dispatched**
  ([ADR-0037](docs/adr/0037-classify-an-abort-before-any-recovery-motion.md), binding —
  violating it is an `ESCALATE`). `ResultCode` gained `MOTION_INTERRUPTED = 10`, defined in
  world terms — the arm stopped part-way and is holding position — with policy row
  `ESCALATE`; `EXECUTION_FAILED` narrowed to the two endpoint cases. The classification is a
  free function in **L3**, `cite_skills::classify_execution_failure`, computed from the plan
  and the joint state rather than from any L2 error code, so it holds for any robot type
  (P9) and is identical on both backends (P2). A typed `ResetStation.srv` exists and is
  served by `cite_orchestration`, which had no `create_service` call at all before it; the
  reset commands no motion. Every row of the classifier is unit-tested in
  `cite_skills/test/test_motion_end.cpp`.
  **A genuine abort now reaches the classifier on demand, and this file said otherwise until
  2026-08-29.** ADR-0040's `cite_test_hardware/JointStopSystem` puts hard stops on one named
  joint, and `cite_bringup/test/test_abort_classification_launch.py` drives a real
  `ros2_control_node`, a real `move_group` and the real skill server: one goal clear of the
  stops must succeed, one through them must come back `MOTION_INTERRUPTED` with a `part-way`
  reason — the same rig, the same hardware, differing only in the goal. It passed 4 of 4 in
  `./scripts/test` in this checkout on 2026-08-29. The gap list below said no such fixture
  existed; the fixture landed at `a90b05f` on 2026-08-28 and this file was edited twice after
  that without noticing. **What it still cannot answer** is in its own docstring: mock
  hardware is a perfect follower, so the early abort ADR-0037 names — a decelerating arm still
  within tolerance of the start, misclassified as never having moved — cannot be produced
  there, and only a scenario measures the `gz_ros2_control` command interface.
- **A station's escalation now stops the line and leaves the coordinator alive to serve that
  reset** ([ADR-0038](docs/adr/0038-stop-the-line-without-ending-the-process.md)). The
  generated root was a bare `Parallel`, so an escalating station failed the root, ended the
  tick loop and exited the process — which tore the whole cell down and took the evidence of
  the fault with it. The root is now a `Fallback` over that unchanged `Parallel` and a fault
  `Sequence` of `OnFault → StopAll → AwaitReset → AwaitReArm` in `line_fault.hpp`. A latched
  fault still exits 1 on **either** route into the branch, so a run in which the line stopped
  still fails CI.
  **`StopAll` is a P2 fix, not a convenience**, and it gives `ConveyorIndex::stop()` its first
  production caller. The simulated belts stopped by accident — Gazebo died with the launch and
  there was no belt left to run; a physical belt is a VFD and **a setpoint persists**. Identical
  command path, divergent consequence, and only the simulated half has ever been observed.
  **It is a state machine, not a protective measure.** What it buys is that the coordinator
  is still there to be asked a question, and that it stops commanding belts it has stopped
  supervising.
- **P10 has its first automated check** ([ADR-0035](docs/adr/0035-check-the-english-only-rule-by-character-signal.md)).
  `./scripts/lint` fails when a tracked text file contains a letter specific to a language
  other than English — six Turkish-specific letters plus nine non-Latin script ranges, chosen
  by measuring four candidate instruments against the archived v1 tree, where this one catches
  **17 of 17** first-party files. It runs in the host half of `lint`, the half that always
  runs, and reported `1048 files checked, no non-English content outside 1 exemption(s)` in
  this checkout on 2026-08-29; it said **661** until then. Most of the difference is the
  measurement campaigns publishing their raw logs into the walk — `git diff --diff-filter=A
  --name-only 60eb4a5..HEAD -- docs/measurements` counts **368** files added there since the
  figure was taken — so **this number tracks how much evidence is committed and is not a
  measure of coverage.** Run `lint` rather than quoting it. The one exemption is
  `docs/reference/v1-lessons.md`, which quotes the
  original Turkish as primary-source evidence. The limits — chiefly that ASCII-only Turkish and
  every other Latin-script language pass untouched — are the ADR's; do not restate them.
- **One arm picks and places a work-piece, and friction alone holds it.** ADR-0029 removed
  the contact-triggered attachment plugin, so nothing on the simulation side assists a grasp:
  the pads close on the part, stall on it, and the controller reports
  `stalled=true, reached_goal=false -> holding` — the evidence ADR-0022 shaped the gripper
  path around. The 84-trial measurement the decision rests on is
  [`docs/measurements/2026-08-25-friction-grasp/`](docs/measurements/2026-08-25-friction-grasp/results.md).
  **The cycle passed 6 of 6** in the measurement the implementing agent took on 2026-08-26,
  in one isolated freshly built tree on one machine, every run reporting a genuine friction
  stall. **The scenario verdict in those same runs was 5 of 6**: one run passed the cycle and
  then failed the post-shutdown teardown check. No thresholds were registered in advance and
  this is not a claim about any other machine.
  **The wrong pass count named above was this bullet's.** It said 8/8; those runs executed
  another worktree's binaries through shared Docker volumes, and the number arrived here
  supplied rather than measured. Each checkout is now isolated and `lint`/`test` refuse to
  answer from a stale build tree — **measure it yourself anyway.**
  **`./scripts/scenario pick_and_place` is a blocking CI step**, promoted at `c1e9e03`. CI
  passes `--teardown-advisory` to all three scenarios, splitting the two questions a scenario
  answers in one exit code: **the cycle is gated, the post-shutdown teardown is reported and
  not gated.** The flag is off by default, so an interactive run still answers the strict
  question. Read `scripts/scenario`'s header and the phase-split block in `scripts/_lib.sh`
  before treating a teardown failure as a gate — and never answer one by widening a tolerance.
- **The line has completed in three of the six CI runs that have driven it, and this is the
  least-settled claim in this file.**
  `./scripts/scenario continuous_line` drives the three-arm sensor-driven line: the aid
  topics are bridged, `Detect` turns a beam level into a typed `DetectionEvent`, L4 stops the
  belt on that edge and restarts it on `CompleteHandoff` (ADR-0032), and the beam indexes on
  the part's body rather than its origin (ADR-0033). It runs in CI as `continue-on-error`.
  **A harness had been doing L4's job, and this is the sharpest example in this file of why a
  green run is not evidence.** ADR-0032 gave the belt setpoint an owner in L4 on 2026-08-26
  and that owner delivered nothing: `ConveyorIndex` creates its publishers inside the topology
  callback and published from the same callback, and **reliable QoS is a promise to *matched*
  subscribers**, of which there were none at that instant. The belts were being started by the
  scenario's own repeated sends. Every `continuous_line` figure recorded before 2026-08-27 was
  produced with the test harness compensating for a defect in the thing under test. Fixed
  event-driven — a subscriber matching is treated as an event — and the pre-fix counts are not
  re-measured.
  **What has been measured since, in the order it was taken.** All of it is on one machine
  with **no thresholds registered in advance** and **no directory in
  [`docs/measurements/`](docs/measurements/README.md)**; these are the size of the evidence,
  not a campaign.
  - Fixing agent, 2026-08-27, three runs: cycle **3 of 3**, teardown **3 of 3**.
  - Project owner, 2026-08-27, three runs, independent: cycle **3 of 3**, scenario verdict
    **1 of 3**. Both failures were teardown-only. **The cycle figure replicated and the
    teardown figure did not** — "the line works" and "the scenario is green" are not the same
    claim.
  - Most recent local run, one run: **3 of 3** work-pieces carried end to end, all four beams
    firing at every station, all nine grasps reporting a genuine friction stall, and cycle and
    teardown passing separately. It is better than anything above it. **The tester's own
    reading is that it is one good sample and not a new baseline**, and that is how it is
    recorded here. Do not promote a gate on it.
  **CI has now run it six times, and this is the only body of `continuous_line` evidence
  nobody's local environment could have flattered.** Every one of the six was on `main`, on a
  runner nobody prepared. Read by grepping each run's log for the scenario's own verdict line,
  because **the step conclusion lies**: the step is `continue-on-error`, and
  `gh run view <id> --json jobs` reports it `success` whether the scenario passed or failed —
  verified on 2026-08-29 against `33158091922`, whose `continuous_line` is *known* to have
  failed and which the API still calls `success`. The instrument is
  `gh run view <id> --log | grep "Scenario 'continuous_line'"`.

  | CI run | date | commit | cycle |
  |---|---|---|---|
  | `33158091922` | 2026-08-28 | `60eb4a5` | **failed** — 1 of 3 |
  | `33208064683` | 2026-08-28 | `a8f1e3d` | **failed** — 2 of 3 |
  | `33235590086` | 2026-08-29 | `f1f914f` | passed |
  | `33241186260` | 2026-08-29 | `7afb2c6` | passed |
  | `33244350584` | 2026-08-29 | `3d23999` | passed |
  | `33261637940` | 2026-08-29 | `29068d4` (this commit) | **failed** — 2 of 3 |

  Teardown passed in all six. **Three of six is a count over the runs that exist, not a rate**
  — no thresholds were registered in advance and the six sit at six different commits.
  **All three failures have the identical signature**, which is the finding: a work-piece
  reaches milestone 2 of 10, `lifted(station_transfer_1: cell_a__table_pick__surface)`, never
  reaches milestone 3, `on_link(station_transfer_1: cell_a__conveyor_1__infeed)`, and times
  out on the 420 s leg ceiling with `station_transfer_1` reporting `WAITING`, occupancy 1/1
  and the piece still assigned to it. **In all three `LineState` read `RUNNING` with
  `blocked_reason=none stall_reasons=none`.** `station_transfer_1`'s inbound edge in the
  generated topology is `via: null`, so ADR-0039's detector has no belt setpoint to read and
  is structurally silent there — the blind spot that record names.
  **The three runs end with the part at the same pose to the millimetre**, held in the air for
  the rest of the leg: `(-0.001, 0.273, 1.201)`, `(-0.001, 0.273, 1.201)` and
  `(-0.001, 0.274, 1.201)`, each about 390 s after the peak of the lift. **So the grasp is not
  what failed** — `lifted` is *measured*, computed by the scenario as
  `sample.z - frame_z > LIFTED_M` (`tests/scenarios/continuous_line.py:664-665`) rather than
  reported by the arm, so the piece demonstrably rose off the pick frame and never came back
  down.
  **What stops the piece between those two milestones is now established, by one
  investigation and not by a campaign.** The gripper's *result* timed out on a wall-clock
  deadline supervising a simulation-time process, `Pick` returned `TIMEOUT` without ever
  saying what the gripper did, and the retry's own `MoveToHome` carried the part **off** the
  beam the station was about to wait on again — so the station re-entered `AwaitTrigger` on a
  beam that had gone clear and stayed clear, holding the piece. Two layers, two records, both
  written 2026-08-29:
  [ADR-0045](docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md) for the L3
  deadline and [ADR-0046](docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)
  for the L4 retry. **Both are `Proposed`, nothing is implemented, and the failure will
  recur.**
  **Every timing figure in those records is reported by the project owner's investigation and
  was not re-measured**, including the on-demand reproduction under CPU starvation — no
  thresholds registered in advance, no directory in
  [`docs/measurements/`](docs/measurements/README.md), and both records say so in their own
  verification tables. What *is* checkable in the mechanism — the constant, the clock it is
  compared against, the controller's terminating rule read upstream, the recovery branch, the
  topology edge — was read from source and is tabulated there. Cite the records; do not copy
  their numbers around (P1).
  **This supersedes the account that called `33158091922` "the only one ever taken off a
  developer machine".** It also means the local sets above and the CI set disagree, and that
  the disagreement is now a repeated failure rather than a single one.
- **The teardown flake is two failure families, and process identity predicts the family
  exactly.** What this file said until 2026-08-27 — four undifferentiated processes, identity
  not predictive, run duration the only candidate predictor, cause unestablished — was wrong
  on all four counts. Split by exit status:
  - **Exit code 1 — `topology_server.py` and `model_info.py`.** Both `cite_facility` `rclpy`
    nodes, both instances of **one cause, which is established and fixed**.
    [ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md) records it: two
    upstream `rclpy` shutdown races, each link read in upstream source rather than inferred,
    each compensation carrying the condition for deleting it. **Read the ADR.** Restating the
    mechanism here would be the duplication P1 forbids.
  - **Signal deaths — `move_group` (×3) and `skill_server` (×1), and still unexplained.** The
    two observed in `continuous_line` are both MoveIt-linked C++, and **"MoveIt-linked" is no
    longer a description of the family**: the campaign below caught `parameter_bridge`, which
    links no MoveIt code, exiting -11 at teardown. One event, and enough to retire the
    characterisation.
    **This family now has a campaign, and it is the citation for every figure that used to sit
    in this bullet** —
    [`docs/measurements/2026-08-27-teardown-signal-family/`](docs/measurements/2026-08-27-teardown-signal-family/results.md).
    Thresholds were registered before the first trial and applied literally. Read it rather
    than trusting the summary here; the numbers are deliberately not copied (P1).
    **Its primary result is INCONCLUSIVE and must not be read as reassurance.**
    `skill_server` did not exit -11 at all in the campaign's **pre-fix** arm, so the rig does
    not reproduce the defect, and the campaign's own rule 1 refuses the clean post-fix arm as
    evidence that anything was fixed. The `continuous_line` death remains un-reproduced and
    un-explained; it is *rarer*, not *understood*. **This bullet said until 2026-08-28 that the
    non-recurrence figure was "supplied rather than reproducible from this checkout". It is now
    published with its logs and its analyser** — and note that it was measured at `de67d8b`,
    not at this commit.
    **The hypothesis gained a demonstration and did not gain a cause.** `skill_server` holds a
    `shared_ptr<MoveGroupInterface>` constructed from its own node and
    `MoveGroupInterface::getNode()` returns a `shared_ptr` reference, so a reference cycle may
    mean `~SkillServer` never runs. This bullet said until 2026-08-28 that **nothing had been
    instrumented to show the destructor is skipped. That is wrong** — the campaign instrumented
    it under `gdb`, one run in each direction, and the destructor demonstrably does not run
    while the cycle is intact. What is still **not** demonstrated is the part that matters: no
    mechanism links a skipped destructor to a signal death, and the arm that would have tested
    it never reproduced one.
    **`skill_server`'s -11 is outside the exemption and stays there.** The exemption in
    `tests/scenarios/continuous_line.py` covers `move_group` and -11 and nothing else.
    `move_group`'s is characterised and upstream, with the stack — the campaign's `gdb`
    backtrace puts frame #11 in `move_group`'s own `main`. **No exemption has been added or
    widened**, and widening one to cover `skill_server` would tolerate an undemonstrated cause,
    which is the opposite of what the split bought.
  **Run duration is retired as a predictor.** Three `continuous_line` runs on one machine on
  2026-08-27 took **478.055 s (passed), 480.607 s (failed) and 497.710 s (failed)**. The
  longest did fail, so duration is not *uncorrelated* — but 2.5 s separating a pass from a fail
  rules it out as the mechanism. The comment in `tests/scenarios/continuous_line.py` still
  asserts the duration correlation and has not been updated. The superseded account also named
  `parameter_bridge` (-6) and `gz` (-9); those two are outside the set the split was measured
  over and are not classified here. `parameter_bridge` has since been observed on **both** -6
  and -11 in the campaign cited above, each once — which is what removes "MoveIt-linked" from
  the signal family's description, and is still two events rather than a rate.
- **The recorded real-time factor of 0.14 is conditional, and the condition is roughly one CPU
  core.** It is not wrong: it reproduces on the development host — both halves of the recorded
  pair, RTF and the `joint_states` rate, together and by two independent instruments — when the
  cell is confined to about one core. Unconfined, the same host idles slightly **above** real
  time and holds the configured `joint_states` rate. Bring-up is rejected as the condition and
  so is load. Every figure is
  [`docs/measurements/2026-08-29-real-time-factor-conditions/`](docs/measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md);
  **the one place in the tree that states the figure with its condition is
  [`docs/architecture/cross-cutting-testing.md`](docs/architecture/cross-cutting-testing.md)
  under "Wall-clock ceilings"**, and everything else cites it rather than restating it (P1) —
  six copies of an unconditioned number is how the omission survived for five days.
  Two consequences to carry: **every scenario ceiling is wall clock**, so a starved host times a
  scenario out with nothing broken and **no ceiling may be widened to absorb that**; and
  **Gazebo's own `real_time_factor` field over-reports under CPU starvation by up to a factor of
  four**, printing a number close to 0.14 while the cell runs at a twenty-fifth of real time.
  Measure `Δ sim_time / Δ real_time` from the world's stats topic over a stated window; never
  quote that field.
- **Phase 2 has split into 2.A and 2.B, and the first pieces of 2.A are in the tree.
  Nothing has ever brought a pair up.** Charter v1.9 (2026-08-29) records the split: 2.A
  pairs the plant with a **virtual counterpart** — a second full simulation of the same cell,
  modelled as if it were physical — and 2.B replaces that stand-in with the real cell. The
  charter also records that **2.A closes no clause of the Phase 2 exit criterion and produces
  no fidelity number**, since both sides run the same L0 model and the same solver. Read §8
  there rather than inferring it from what is on disk.
  **What landed:** ADR-0041's decision 3 as a zone-level `twin: {sides: single | pair}`,
  required with no default, plus an optional per-asset `hardware.counterpart_backend`;
  ADR-0042 as a Gazebo transport partition derived per side and emitted into the generated
  bring-up plan; ADR-0043's first half as `real_time_factor: 1.0` in the generated world; and
  `TwinMode/MODE_VIRTUAL_LEAD = 5` in `cite_interfaces`.
  **What a paired model is not, and this is the part to carry.** `model/facility/zones.yaml`
  declares `sides: single` today, so nothing in this repository is paired. Set it to `pair`
  and the generated plan gains **one more `sides:` entry with the counterpart's partition,
  and a `counterpart_backend:` line per controller manager. That is all it gains** — no second
  world, no second controller manager, no second set of node names, no second launch.
  `cite_bringup/gz.py` says so in its own docstring: it addresses `plan.sides[0]`, the plant,
  and "bringing a counterpart up is a separate launch and is not built yet". ADR-0041 and
  ADR-0043 are still `Proposed` for exactly that reason. **`MODE_VIRTUAL_LEAD` is vocabulary
  only**: `grep -rn MODE_VIRTUAL_LEAD workspace/src` reaches the message, the interface
  baseline and one comment — nothing routes on it, `SetMode` has no server, and `cite_twin`
  does not exist.
  **The throttle is a ceiling, measured once, and not published.** SDFormat's
  `real_time_factor` bounds how fast a server may run and cannot make a slow one faster, so it
  binds only where the cell has spare capacity. The implementing agent measured it on one
  machine, two runs per scenario, **with no thresholds registered in advance and no directory
  in [`docs/measurements/`](docs/measurements/README.md)** — so **these figures are not
  reproducible from this checkout and were not re-taken for this file**: an idle cell at
  **0.9961** throttled against **1.094** unthrottled, and, under load, a cycle at
  **0.574 / 0.586** and a line at **0.657 / 0.656**, each within a few per cent of the
  unthrottled figure the RTF campaign holds for the same scenario. So it is a no-op under load
  on that machine and binds only on an idle cell. **ADR-0043's other half — that two sides
  sustain 1.0 concurrently — is unmeasured**, and no scenario ceiling was changed. **ADR-0043's
  status line still reads "nothing implemented" and describes `REAL_TIME_FACTOR = 0.0`**, which
  the tree falsifies; its promotion condition wants both halves, so `Proposed` may still be
  right, but do not read that sentence as a statement about the world file.
  **The sharpest lesson of that work is a defect class, not a decision.** Every process the
  launch graph starts carried the partition; the scenario harness started its own and carried
  none, so both cycle scenarios hung at their work-piece spawn — and an unpartitioned
  `gz model --list` **exits 0 having reached no world**, so fixing only the spawn would have
  produced scenarios that verify a part moved by asking an empty transport. One door now
  exists (`cite_bringup/gz.py`) and a guard,
  `tests/scenarios/guards/test_gz_calls_carry_the_partition.py`, fails the suite if a raw
  Gazebo-transport subprocess call reappears under `tests/`. §10 carries it as a review
  checkpoint.
- **What does not work, stated plainly** (Phase 1.C/1.D, in progress). **None of these is an
  exit-criterion clause** — that list is the last bullet in this section, and it is separate.
  - **The line still stalls after a failed grasp, and the dead end is observed rather than
    predicted.** A piece fails the friction grasp, the station retries, returns to
    `AwaitTrigger` on a beam the part is **already breaking**, and waits out the leg ceiling —
    while `LineState` reports `RUNNING`, so nothing escalates and the scenario's fail-fast —
    which keys on `BLOCKED`, `FAULTED` **and `STALLED`** in the tree today
    (`tests/scenarios/continuous_line.py:458`), and this file said only the first two —
    correctly stays quiet, because the line publishes none of the three. Seen twice,
    reported by the project owner on 2026-08-27. ADR-0038 records why this is deliberately **not** fixed: the
    cheap fix restarts the belt, the retry begins with `MoveToHome` carrying whatever the arm
    holds, and `Pick`'s first physical act is to open the gripper — so the retry's first move
    would open the jaws at the home pose and drop a part no planner knows is held.
    **This is one entrance to the dead end and not the whole of it** — ADR-0038's 2026-08-29
    amendment records the second, which is the item below.
  - **The same dead end reached through a second door: the grasp holds and the retry carries
    the part off its own trigger.** Three CI runs have left a work-piece stuck between
    `lifted` and `on_link` at `station_transfer_1` — the arm has the part, the place onto
    `conveyor_1`'s infeed never happens, `LineState` reads `RUNNING` and nothing escalates.
    The evidence and the milestone ladder are in the `continuous_line` bullet above and are
    not repeated here. **The cause is established** and has two records, both written
    2026-08-29 and both `Proposed`: the gripper result deadline is a wall-clock `constexpr`
    supervising a simulation-time process
    ([ADR-0045](docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md)), and a
    station that still holds its work-piece re-enters a wait its own recovery made
    unsatisfiable
    ([ADR-0046](docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)).
    **It is the item above's dead end with a different entrance, and the difference decides
    what a fix must do.** There the grasp fails, the beam stays blocked and the arm is empty;
    here the grasp holds, the beam goes clear and the part is in the gripper — so **a fix
    keyed on "the beam is blocked" catches only one of the two**, which is why ADR-0046 keys
    its refusal on custody instead.
    **Widening the constant is not available as a fix**: `GripperActionController` resets its
    stall search on every control cycle in which the joint exceeds
    `stall_velocity_threshold`, so the quantity the deadline is asked to bound has no upper
    bound — the rule read upstream in ADR-0045's verification table.
    **The detector is not broken; its coverage is.** In one local run reported by the
    investigation, the same fault class at belt-fed `station_transfer_3` was named by
    ADR-0039's detector **0.341 s** later and aborted the run; at table-fed
    `station_transfer_1`, `untriggerable_reason` returns `nullopt` at its first test because
    there is no inbound belt, so the line published `RUNNING` for the rest of the leg. That
    contrast is ADR-0039's 2026-08-29 amendment, one run, not re-measured.
    **Three things stay explicitly unmeasured**, chief among them why CI's gripper-close
    distribution has a long tail that the investigating host did not reproduce at a comparable
    real-time factor. ADR-0045 lists all three with the measurement that would settle each;
    none may be smoothed over here or anywhere else.
    **Nothing is implemented and the failure will recur**; it is still the failure this
    project has the most evidence for.
  - **A real grasp can be reported empty, and that is a separate defect owed its own record.**
    `cite_skills::gripper_is_holding` (`gripper.cpp:106-117`) requires the reached width to
    exceed the commanded width by more than **twice** the linkage's own width tolerance at
    that drive angle. Recomputed from the L0 linkage dimensions for ADR-0045 and reproducing
    exactly: against a commanded 45.0 mm, a genuine 46.6 mm stall leaves 1.6 mm of margin
    against a 2.12 mm threshold, so `Pick` returns `EXECUTION_FAILED` with an empty-grasp
    description while the part is in the jaws. **This is arithmetic over the shipped
    constants, not an observed run** — nothing has attributed a CI failure to it.
    `EXECUTION_FAILED` shares the `RETRY_SAME` branch with `TIMEOUT`, so it reaches the same
    dead end as the item above by a different entrance — a second reason ADR-0046 refuses on
    custody rather than on a result code. **ADR-0045 names it as owed its own record and
    deliberately does not fold it in; that record does not exist yet.**
  - **The only environment-collision gate has an unmeasured edge.** Pilz does not search the
    scene, so `ValidateSolution` is the sole gate, and it checks trajectory waypoints while
    interpolating nothing between them. The sampling time is **0.1 s**, a C++ default argument
    with no ROS parameter exposing it. The smallest object in the generated planning scene is
    a **40 mm** break-beam housing, so a waypoint step exceeds it whenever the tool point moves
    faster than **0.40 m/s**. The arithmetic and the two ways the step can grow are ADR-0027's.
  - **Nothing has measured what the execution-side tolerances do under Gazebo.** The launch
    test proves them against mock hardware with an injected fault; under `gz_ros2_control` the
    position command interface is a velocity law rather than a servo, and no following error
    has been sampled there. So neither that the path tolerance fires on a genuine obstruction
    nor that it stays quiet on a healthy run is established on the backend the scenarios use.
    ADR-0036's "revisit" section names the measurement that would settle it.
  - **A grasp holds a position, not an orientation, and the two published residuals are
    different quantities.** Correcting the grasp-plane offset took rotations above 20° from
    60% to 0% of trials and left a residual —
    [`docs/measurements/2026-08-25-grasp-plane-offset/`](docs/measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md).
    **That residual, up to 18.7°, is a *roll* about the pad-to-pad axis, not a yaw.**
    Re-analysed on 2026-08-26 over 72 committed carries: every net carry rotation lies along
    the pad-to-pad axis, the component about the world vertical never exceeds 0.49°, and the
    trial that *is* the published 18.71° has a vertical component of 0.01°. **The yaw figure is
    10.62°**, from the conveyor-yaw campaign's twelve end-to-end trials. An angle without an
    axis is not a measurement of anything — do not put 18.7° into anything only a yaw can enter.
    The offset correction is in the tree, where the campaign said it belonged: L0's end-effector
    `linkage` block declares the vendor dimensions and the L3 skill server derives the offset
    from them. Per ADR-0029 a scenario may assert where a part ends up and **may not assert how
    it is held**.
    **A square part arriving yawed parks a few millimetres short**, because a leading-edge test
    makes the index position depend on yaw. That sensitivity is **real on hardware** — a
    physical photo-eye behaves the same way — and must not be described as a simulation artefact
    or compensated in the beam. Whether the residual accumulates over three stations is listed
    as **explicitly unmeasured** in
    [`docs/measurements/2026-08-26-conveyor-yaw-transfer/`](docs/measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md).
  - **L4 refuses a direct arm-to-arm handoff, and the residual is no longer the stated reason.**
    ADR-0031 was corrected on 2026-08-26: nothing re-observes the part, and what makes the
    *permitted* conveyor edge safe is the receiving gripper closing on a free part — which a
    direct handoff denies. Read that ADR's correction before writing about either case. The
    refusal string in `line_plan.hpp` still carries the pre-correction reasoning.
  - **`Transfer` has a server and no caller.** Today's L0 topology is conveyor-mediated and L4
    refuses a direct arm-to-arm edge at plan time (ADR-0031).
  - **L4's own tests move no arm.** `line_orchestrator` derives one subtree per station from
    `LineTopology` and owns handoff, recovery, the fault branch and `LineState`; its unit and
    launch tests use fake action servers that succeed because they are told to, so what they
    prove is **sequence, ownership and the stop**, not motion. Motion is evidenced only by the
    scenarios.
  - **The belts are commanded open-loop.** `ConveyorState` exists in `cite_interfaces` to make
    commanded and measured speed disagree visibly, and **nothing publishes it**; the bridge
    carries a bare `std_msgs/Float64` each way. So `StopAll` states an intent it cannot confirm,
    and a belt that fails to stop, or fails to restart, is a spilling or a stalled line that
    nothing notices. **This is the gap that hid the delivery defect above for ten commits**:
    with no confirmation path, "commanded" and "running" were indistinguishable from inside the
    system. A publisher of `ConveyorState` — in the simulation plugin and on the hardware drive,
    which is L1/L2 work — is what closes it.
  - **Scenarios are not deterministic.** `CITE_PHYSICS_SEED` still reaches only
    `gz sim --seed`, which seeds sensor noise and **not the physics solver**. What changed is
    which part is stochastic: planning is no longer it wherever Pilz answers, and physics still
    is. The OMPL fallback remains unseeded and unseedable. See
    `docs/architecture/cross-cutting-testing.md` and ADR-0027 before writing anything about
    determinism, and do not upgrade the claim on the strength of the planner alone.
  - **Twelve links per arm use their visual mesh as collision geometry**, which §10 below names
    as a defect class. **The 0.14 real-time factor used to be quoted here and is not what makes
    this urgent** — a one-core allocation is what produced that figure, not collision geometry;
    see the bullet above and ADR-0028's 2026-08-29 correction. What the case now rests on is
    the second-world campaign's measured cost of collision geometry, cited in ADR-0028 rather
    than copied. ADR-0028 decides the fix and is still `Proposed`: `assets/` holds only its
    README and manifest.
- **The layout is `PROVISIONAL`.** The coordinates in `model/` are engineered, not surveyed.
  Charter §8 puts the physical scan in Phase 3; until then a measurement taken from this model
  does not transfer to the building, and no report should imply that it does.
- **The documentation is written, and its status markers are the thing to read.** Each document
  in `docs/architecture/` and `docs/interfaces/` carries `DESIGNED`, `PARTIAL` or `BUILT`, with
  the evidence named. `DESIGNED` means the contract the code must satisfy; `PARTIAL` says which
  part is real and which is not. Read the layer document before touching a layer, and read its
  status line before believing its body.
- **Measured evidence lives in [`docs/measurements/`](docs/measurements/README.md)**, one
  directory per campaign, each with its thresholds written down before the first trial. This is
  what P8 looks like in practice. Cite a campaign; do not copy its numbers around. **A campaign
  whose answer is "inconclusive" is published too** — the teardown one is, and its rule refused
  a clean arm as evidence rather than banking it.
- **Where Phase 1's exit criterion stands, and nothing above changes it.** **The clause-by-clause
  record is charter §8 and is not copied here** (P1) — it states which evidence closed which
  clause, at what strength, and what the closure does not cover. What belongs in a rulebook is
  the part that changes how you read everything else in this section:
  - **The criterion is MET as of 2026-08-28 and that is not a green light.** It closed on CI run
    `33158091922`, one run, no thresholds registered in advance, at commit `60eb4a5`. **Inside
    that green run the advisory `continuous_line` step failed** — 1 of 3 work-pieces, a station
    stopped while `LineState` still read healthy. That silence is the blind spot ADR-0039
    records at that station. **What stopped the piece was not established when the clause
    closed and has been established since** — the gripper-result timeout and the retry that
    carried the part off its own trigger, ADR-0045 and ADR-0046, at the strength the
    `continuous_line` bullet above states. Nothing about that changes the closure: it was
    closed on evidence that did not include a cause, and knowing the cause does not add a run.
    **One attribution names the right dead end by the wrong door and must not be repeated as
    it stands.** Charter §8 reads that run as consistent with the *failed-grasp* dead end
    ADR-0038 records. It is that dead end, and it is not the failed grasp: the run's own
    milestone ladder puts the piece past `lifted(station_transfer_1:
    cell_a__table_pick__surface)` and leaves it in the air at `(-0.001, 0.273, 1.201)` for the
    rest of the leg, so the grasp held, and ADR-0038's 2026-08-29 amendment records the second
    door it went through instead. The charter is protected and still carries that sentence;
    treat the ladder and the two records as the record.
    A workflow whose conclusion is `success` is therefore not a statement that every scenario
    passed. **Never cite "CI is green" as evidence that a capability works; cite the step that
    gates it** — and note that **the step's own conclusion is not the step's result either**:
    GitHub reports a `continue-on-error` step as `success` when it failed, so the log is the
    only instrument. See the table in the `continuous_line` bullet, where three of six CI runs
    failed the cycle in the same way.
  - **The clean-clone walk of 2026-08-27 demonstrated clone-to-green, not a running line.** It
    ran `doctor` (23 passed, 0 failed), `build` (19 packages, before `cite_runtime` existed),
    `test` and `lint`, all clean, from a fresh clone of the remote with zero deviations — and
    **stopped at `lint` without launching the cell**. The clone-to-running-cell half is
    evidenced by the CI runs above, each of which brought the cell up twice from a checkout —
    `bringup` has passed 12 of 12 across the six — and by nothing else.
  - **The cycle clause is the least-settled of them**, and it has got weaker rather than
    stronger. Three CI failures are now part of its record, not one, and all three stopped the
    same piece at the same milestone. See the `continuous_line` bullet above, including that a
    harness had been starting the belts and that the best local figure is a single run.
  - **"Every architectural decision is written down" is the one clause the charter records as
    unclosable as stated**, and the counting is the reproducible part. `./scripts/doctor`'s
    `ADR index` line reported **46 records, all indexed** in this checkout on 2026-08-29 — it
    said 43 earlier the same day, and 40 before that — the newest being
    [ADR-0046](docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md).
    **`ls docs/adr/[0-9]*.md` returns exactly one more than `doctor` does**, because the glob
    also matches `0000-template.md`; both numbers are right and
    they count different things, so name the command with the number. **This figure moves
    every time a decision is recorded, which is often — run `doctor` rather than quoting the
    number here.** The breakdown of corrected,
    amended and superseded records is the table in
    [`docs/adr/README.md`](docs/adr/README.md) and is deliberately not copied here — `doctor`
    does not count those. `doctor` enforces that every ADR on disk is indexed and that every ADR
    referenced from `docs/` exists; it does **not** check that the set is *complete*, and no check
    can. That clause is a judgement, not a measurement.

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
