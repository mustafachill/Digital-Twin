# ADR-0069: Remove the parked line and `cell_a` from the main tree

- **Status:** Proposed
- **Date:** 2026-10-01
- **Deciders:** Project owner
- **Related:** supersedes [ADR-0056](0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md)
  and [ADR-0066](0066-run-the-cell-from-a-fixed-program.md);
  deprecates [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md),
  [ADR-0032](0032-index-the-belt.md) and
  [ADR-0039](0039-report-a-station-that-cannot-be-triggered.md);
  overtakes sentences in [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md),
  [ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) and
  [ADR-0059](0059-pair-cell-b-and-leave-cell-a-single.md);
  builds on [ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md) and
  [ADR-0068](0068-keep-proven-milestones-as-frozen-snapshots.md);
  [ADR-0021](0021-generated-artifacts-are-committed.md); charter §7 and §14 (v1.15);
  [`../open-work.md`](../open-work.md)

## Context

[ADR-0068](0068-keep-proven-milestones-as-frozen-snapshots.md) keeps the three proven
milestones as frozen, runnable snapshots under `projects/`. The first of them,
`projects/01-three-arm-event-driven-line/`, is the three-arm, behaviour-tree-coordinated,
beam-triggered line on zone `cell_a`; its `PROVENANCE.md` verification log records
`./scripts/scenario continuous_line --zone cell_a` passing from the snapshot, on one machine,
after a first run that failed. ADR-0068 decision 6 deferred removing that line from the main
tree to a record of its own. This is that record.

Facts read in this checkout at `1ecc181` on 2026-10-01:

- Main CI run `36888750606` at `1ecc181` concluded `success`, and its four scenario step
  columns printed the bare verdicts `bringup` ×2, `pick_and_place`, `continuous_line` and
  `program_cycle` (`gh run view --log`, step-restricted anchored match, the instrument CLAUDE.md
  §2 names). `.github/workflows/projects.yml` had no run on GitHub at that date
  (`gh run list --workflow projects.yml` returned none).
- The main tree still carries everything [ADR-0066](0066-run-the-cell-from-a-fixed-program.md)
  parked: the `cite_orchestration` package (33 tracked files, 14 164 lines), the detection
  server in `cite_skills`, `cite_facility`'s `topology_server`, ten line-only interface
  definitions out of `cite_interfaces`' 23, `cite_bringup/demo.py` with `scripts/demo`, the
  `continuous_line` and `pick_and_place` scenarios with three guards, and
  `tools/tests/test_event_driven_line_is_kept.py`, which fails if any of it disappears.
- Zone `cell_a` is in L0 and has **31** tracked generated artifacts
  (`git ls-files workspace/src/cite_generated | grep -c cell_a`). Because two zones exist,
  `./scripts/sim` refuses to run without `--zone` (ADR-0056), and `tests/scenarios/_cell.py`
  sends `bringup`, `pick_and_place` and `continuous_line` to `cell_a` and `program_cycle` to
  `cell_b`.
- What the project now develops is the real-plus-digital twin path:
  paired `cell_b` ([ADR-0059](0059-pair-cell-b-and-leave-cell-a-single.md)), the arm on a
  linear track and the real Blockly program driven through the twin boundary
  ([ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md)), checked by
  `./scripts/program` and `program_cycle`. The next large step is connecting the real arm.
- Two ADR-0066 leftovers no longer serve that path. `program/cell_b_pick_place.py` is the
  taught-pose program ADR-0067 replaced, and it is the **only** client of the twin boundary's
  belt route. L0's `configuration.poses_rad` field is declared in the schema and checked by
  the validator, and no model entry uses it. The **plan's** `poses_rad` key is a different
  thing and is load-bearing: `generate/bringup.py` fills it from the Blockly program, and
  `simulation.launch.py` hands it to the skill server.

Every platform change today has to carry a second zone, a parked L4 and a retired program
that the target system does not use; ADR-0068 option B named that cost and declined to keep
paying it.

## Options considered

### Option A — Keep the line parked (status quo, ADR-0066)
Nothing is lost from main CI: multi-arm bring-up, behaviour-tree orchestration and
beam-triggered handoff stay gated on every push. Not chosen: it was written before a runnable
record existed outside the main tree, and now that `projects/01` exists it buys that coverage
by making every change carry two zones, ~14 k lines of L4 and ten interfaces that the twin
path never calls.

### Option B — Remove L4 and the line, keep `cell_a` as a bring-up-only zone
Keeps a multi-arm cell under the generator and under `bringup`, so cross-arm naming and
multi-instance generation stay exercised by a real launch. Not chosen: with no line, `cell_a`
is a second zone that only `bringup` reaches, it keeps `--zone` mandatory everywhere and
forces per-zone parametrisation of every zone-dependent test, and the owner's target system
is one paired cell with one of everything. `projects/01` keeps the three-arm cell runnable.

### Option C — Remove the line, `cell_a` and the ADR-0066 leftovers together
Chosen.

## Decision

The main tree carries only the twin path; the event-driven line and `cell_a` live on as
`projects/01` and nowhere else.

1. **Removed from the main tree:** the `cite_orchestration` package (L4, the behaviour-tree
   line); from `cite_skills`, the detection server, `detection.cpp`, the `detection.hpp` and
   `observation.hpp` headers and their tests; `cite_facility`'s `topology_server` and its test;
   the line-only interfaces `LineState`, `LineTopology`, `StationTopology`, `StationEdge`,
   `StationState`, `DetectionEvent`, `Detection`, `Detect.action`, `ResetStation.srv` and
   `ConveyorState`; `cite_bringup/demo.py` and `scripts/demo`, after the helpers the program
   path uses move into `cite_bringup`; the `continuous_line` and `pick_and_place` scenarios and
   their line-only guards; and `tools/tests/test_event_driven_line_is_kept.py`, which enforced
   ADR-0066's "park, don't delete" promise that this record withdraws.
   **Each interface is re-verified unused outside the line before it is deleted**; any found
   in real use stays and is named here. A pre-check on 2026-10-01 (`git grep -w` outside
   `cite_orchestration` and the files this decision removes) found only comments and
   docstrings in `skill_server.cpp`, `break_beam.cpp`, `cite_twin/boundary.py`,
   `test_skill_contract.py` and `test_twin_mode_enumerations.py`, plus the code this decision
   already rewrites (plan reader, generator, launch file, readiness witness); the implementing
   change repeats the check after its edits.
2. **Zone `cell_a` leaves L0** — its zone entry, its flow document, its stations and its
   instances, and the `pedestal_600` type and `pedestal_steel` material if nothing else uses
   them — and its 31 generated artifacts are removed by regeneration, never by hand
   (ADR-0021). `cell_b` keeps its flow document, stations and beams: the schema requires a
   flow, and `program_cycle` reads its station frames from it.
3. **ADR-0066 leftovers:** `program/cell_b_pick_place.py` and the L0 `configuration.poses_rad`
   field (schema and validator checks) are removed. The **plan's** `poses_rad` key stays; it
   carries the Blockly poses to the skill server.
4. **Kept on the project owner's explicit decision:** the twin boundary's belt route
   `/cite/twin/<zone>/<belt>/command`, its stop of the belts a mode does not command, the
   `belt` program step and `RosCell`'s conveyor support. With `cell_b_pick_place.py` gone,
   nothing in the main tree drives a belt through the boundary; only `cite_twin`'s own tests
   hold the route. This is a known and accepted state, not an oversight.
5. **`--zone`:** when L0 declares exactly one zone, `./scripts/sim`, `./scripts/scenario`,
   `./scripts/program` and the scenarios default to it; when it declares more than one, the
   flag is required again, so ADR-0056's rule returns by itself the day a second zone is
   declared. The default is derived from the model in one place and stated nowhere else.
6. **Tests:** tests that depended on `cell_a` move to `cell_b`'s `picker`. A test whose
   assertion needed several arms or a single-sided zone is rebuilt on a synthetic fixture
   where the assertion survives; one that cannot survive is deleted and listed under
   "Coverage given up" below. A test moved onto paired `cell_b` must still be able to fail —
   a test that asserted something about pairing and now runs on an already-paired zone is
   inverted, not left passing vacuously.
7. **Records, applied in the same branch:** ADR-0066 and ADR-0056 become
   `Superseded by 0069`; ADR-0031, ADR-0032 and ADR-0039 become `Deprecated` — their mechanism
   is removed with no replacement in the main tree and still runs in `projects/01`; ADR-0024,
   ADR-0037, ADR-0038, ADR-0046 and ADR-0059 keep their status and gain
   `**[Overtaken 2026-10-01 — ADR-0069]**` markers on their L4 and `cell_a` sentences. No ADR
   and nothing under `docs/measurements/` is deleted or rewritten. The L4 architecture documents
   stay, because many records link to them, and their status lines become `DESIGNED` with a
   pointer to `projects/01`.
8. **Charter v1.15** (project owner's decision, 2026-10-01): §7's `cite_orchestration/` line is
   marked as not in the main tree and runnable as `projects/01`, with a §14 entry. L4 stays in
   the target architecture.

### Coverage given up

Filled by the implementing change. **Deleted with the code they tested** — their subject is
gone from the main tree and still runs in `projects/01`, so nothing here is a loss of coverage
of anything the main tree ships: `cite_orchestration`'s whole test suite; `cite_skills`'
`test_detection`, `test_observation`, `test_detection_contract.py` and
`test_downstream_include.py` (whose only subject was reaching `observation.hpp` from another
package); `cite_facility`'s `test_topology_message.py`; the `continuous_line` and
`pick_and_place` scenarios with the guards `test_a_stopped_line_ends_the_run.py`,
`test_continuous_line_ladder.py` and `test_place_assertion_sees_height.py`; the
`cite_bringup` launch-file tests of the detection server and the line coordinator; the
`./scripts/demo` self-test block; and `tools/tests/test_event_driven_line_is_kept.py`.

**Given up or weakened, because the assertion needed a second arm or a second zone:**

- **A behaviour-tree `Pick`/`Place` driven end to end in simulation.** `pick_and_place` was a
  blocking CI scenario; `program_cycle` still carries a part from table to belt, but through
  the real program's joint moves rather than through `Pick` and `Place`, so the L3 pick and
  place skills are no longer exercised by any scenario in main CI.
- **`bringup`'s `test_no_joint_name_is_shared_between_arms`** is vacuous on one arm, as its
  own docstring says; only its joint-count half still has teeth.
- **`test_trajectory_constraints_launch.py`** ran two different arms' generated controller
  files; it now runs the one arm's file twice under two namespaces. The per-instance joint
  naming it also caught is now held only by `tools/tests/test_trajectory_constraints.py`,
  on a second arm added to a model copy.
- **`cite_skills/test_planning_pipeline.py`'s collision premise** was swept against belts
  standing either side of a middle arm; it now searches a generated grid against `cell_b`'s
  furniture. Whether a candidate in that grid satisfies the premise is the test's own
  finding, not a value carried over.
- **Multi-instance properties in the host suite** — per-instance backends and parameters,
  per-instance tolerance names, every arm's gripper policy, an arm without a track, a second
  arm being a data-only change — are now asked of a second, track-less arm that the
  `add_arm` fixture adds to a model copy. That arm is generated and never validated
  geometrically, so these assertions no longer say anything about a real multi-arm layout.
- **`test_a_hardware_plan_refuses_to_bring_the_cell_up`** asserted that the refusal named
  `arm_2`, the arm whose backend the test had flipped on a plan with several, so it held that
  the refusal named **the right arm among several**. On one arm it names `picker`, the only arm
  there is, and that half of the assertion can no longer fail on a wrong pick.
- **The generator's `DETECTION_SCOPE` asset-name check** went with the detection server: it
  refused a zone holding an asset named `detection`, which would have shared a namespace
  with that server. With no detection server there is no namespace to collide with, so the
  check and its subject left together, and nothing in the main tree reserves that name.
- **Indexing beams and belt station points** no longer exist in the shipped cell; the
  validator rules about them (`beam-indexes-*`, `beam-off-its-belt`, `beam-cannot-index`,
  `insufficient-support-margin`) are now exercised only on a copy of the model that puts a
  belt station point and an indexing beam back.
- **`cite_twin`'s mixed far side** ran on three real assets; it now runs on the shipped arm
  and a renamed clone of its controller manager, which shares the arm's generated files.
- **The second-zone refusal in `cite_facility`'s `model_info`** is asserted with a second
  zone injected into the node rather than read from the model; the model declares one zone,
  so the refusal contributes nothing to a real bring-up until a second is declared.

## Consequences

### What this gets us
- One zone, one cell, one path: every platform change, including connecting the real arm,
  carries only what the twin uses.
- `--zone` stops being a required argument for a facility that has one zone, without
  discarding ADR-0056's reason for requiring it.
- ADR-0059's load-bearing reason for leaving `cell_a` single, and [`../open-work.md`](../open-work.md)
  #62's fixtures that append a counterpart to a `cell_a` plan, stop applying.

### What this costs us
- CI drops the `pick_and_place` step (blocking) and the `continuous_line` step (advisory);
  `bringup` ×2 moves to `cell_b`; `program_cycle` is unchanged.
- **Nothing in main CI exercises a multi-arm cell, behaviour-tree orchestration, beams as
  triggers, or the line's stop and escalation.** `.github/workflows/projects.yml` — weekly,
  `workflow_dispatch`, and not gating `main` — becomes the only check of any of them, and it
  had never run on GitHub when this was written.
- `bringup`'s `test_no_joint_name_is_shared_between_arms` is vacuous on a one-arm cell; its own
  docstring already says so.
- The belt route has no in-tree client; a regression in it is caught only by `cite_twin`'s unit
  and launch tests, which drive fake sides.
- **The break-beam levels are still bridged and nothing in the main tree reads them.** The
  generated bring-up plan still declares each beam's topic and `ros_gz_bridge` still carries
  it, but the detection server that consumed them is gone; the beams publish into a graph with
  no subscriber. Read in this checkout on 2026-10-01: `simulation.launch.py` remaps each
  sensor's `detection_topic` onto its `level_topic`, and no source outside `cite_generated`
  and the tests names a `level_topic` to subscribe to it. Their consumer runs in
  `projects/01`.
- **StopAll was the main tree's only automatic all-belts stop**, and it left with the line.
  `./scripts/program` now commands every side's belt back to zero when it ends — normally, on
  a failure and on Ctrl-C — and `program_cycle` stops the belt it started when its test ends,
  passed or failed; but that is each tool stopping what it started, not a cell-wide stop. A physical belt is a drive whose setpoint persists, so
  before [ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md)'s belt becomes real
  it needs a drive-side stop of its own; nothing in this tree provides one.
- **`Pick`, `Place` and `Transfer` have no production caller in the main tree.** The skill
  server serves them, the readiness witness waits for their servers, L5 routes them, and the
  package launch tests cover them; nothing in the main tree sends one a goal. **On the project
  owner's decision of 2026-10-01** they and their routes stay as they are, and the end-to-end
  coverage that matters is `program_cycle` — the real program, through `MoveTo` and `Grasp`
  (ADR-0067).
- `ConveyorState` was the typed contract reserved for a measured belt speed, which CLAUDE.md §2
  names as what would close the open-loop belt gap. A future closed-loop belt re-introduces a
  contract by its own decision.
- Tests whose assertions needed several arms are lost or weakened; the section above lists them.

### What we will have to revisit
- **Re-introducing L4, a multi-arm zone or a beam-triggered line** needs a new ADR and is
  re-derived from `projects/01`, never copied out of it (ADR-0068 decision 3).
- **A second zone** brings `--zone` back as required (decision 5) and every zone-dependent test
  back to parametrisation.
- **Promotion condition:** main CI green on this branch's merge commit, with `bringup` ×2 and
  `program_cycle` printing the bare `passed` verdict, read from the step logs and not from the
  step conclusions; `./scripts/program --headless` carries both boxes to the belt end in a local
  run; and `git diff 1ecc181 -- projects` is empty.
