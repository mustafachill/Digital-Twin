# ADR-0068: Keep each proven milestone as a frozen, runnable snapshot

- **Status:** Proposed (amended 2026-10-01) — its P1 exception **ratified by the project owner
  on 2026-09-29** and recorded in the charter at **v1.14** (`what-we-are-doing.md` §7 and §14).
  Ratification is not promotion: the promotion condition below is unchanged.
- **Date:** 2026-09-29
- **Deciders:** Project owner
- **Related:** [ADR-0001](0001-rebuild-rather-than-migrate.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0032](0032-index-the-belt.md),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md),
  [ADR-0056](0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md),
  [ADR-0066](0066-run-the-cell-from-a-fixed-program.md),
  [ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md),
  [`../reference/v1-lessons.md`](../reference/v1-lessons.md), CLAUDE.md §3 (P1, P6)

## Amendment — 2026-10-01: each snapshot has a measurement point, `MEASUREMENTS.md`

**Decided by the project owner** as part of cutting `CLAUDE.md` back to the project's
identity, goal and working discipline.

- **Change.** Decision 2's list of permitted patches gains one file per snapshot,
  `MEASUREMENTS.md`, listed in that snapshot's `PROVENANCE.md` like every other patch and
  shown in its "Diff against a clean extract" block.
- **What it holds.** From 2026-10-01 on, the measurements of that milestone; earlier campaigns
  whose subject is that milestone remain under [`docs/measurements/`](../measurements/README.md),
  frozen where they are (the review queue's Q84,
  [`../reference/claude-md-review-queue.md`](../reference/claude-md-review-queue.md), sorts
  them). On 2026-10-01 it received, verbatim,
  the measurements `CLAUDE.md` §2 held whose subject had left the main tree — the three-arm
  line and `cell_a`, the `pick_and_place` and `continuous_line` scenarios, the fixed program.
  A measurement taken of a snapshot from now on is added there, dated, with the hash bump
  decision 2 already requires; it does not go into the main tree.
- **What it does not hold.** Whether the snapshot builds and runs is verification, not
  measurement, and stays in `PROVENANCE.md`'s verification log. A main-tree measurement is
  still a campaign under [`docs/measurements/`](../measurements/README.md).
- **Why a file in the snapshot rather than a directory in the main tree.** The figures
  describe the snapshot's code, and the snapshot is what is handed over as one folder; a
  record kept outside it would not travel with it. Decision 3's one-way rule — nothing is
  copied from `projects/` into the main tree, and the main tree never imports or builds from
  it — is untouched: the figures stay in the snapshot and nothing in the main tree reads them.
- **Cost.** Each such addition edits a frozen record and bumps its tree hash, which is the
  friction decision 2 chose deliberately.

## Context

The repository has reached three milestones, each of which ran a cell end to end and each of
which the main tree has since moved past:

| Milestone | Source commit | What it runs |
|---|---|---|
| Three-arm event-driven line | tag `event-driven-line-v1` = `b5a0bc9` | Three arms on zone `cell_a`, coordinated by L4 behaviour trees on beam events, carry work-pieces along three belts ([ADR-0032](0032-index-the-belt.md), [ADR-0038](0038-stop-the-line-without-ending-the-process.md) and the records they build on). |
| Fixed-program pair | `c83119b` | Two Gazebo instances (paired `cell_b`), one arm each, driven through the twin boundary by a fixed program of taught joint poses and timed belt runs ([ADR-0066](0066-run-the-cell-from-a-fixed-program.md)). |
| Real program, arm on a track | `e90d230` | The real xArm 5's Blockly program drives both sides of paired `cell_b`, the arm on a linear track ([ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md)). |

The second milestone no longer runs on `main`: its taught poses lived in `poses_rad` under
`model/assets/instances/arms.yaml` (present at `c83119b`), and `e02fb67`, ADR-0067's model
commit, removed them from L0. The first is parked rather than deleted (ADR-0066), but at the
tag `tests/scenarios/_cell.py` already sets `DRIVEN_ZONE = "cell_b"`, so its own scenario does
not drive the three-arm cell without a change. A git tag records a state; it does not keep that
state runnable for someone who is handed a folder.

Facts that make a whole-tree copy work without code changes, read at `e90d230`:

- `scripts/_lib.sh` derives `REPO_ROOT` from its own location.
- `infra/docker/docker-compose.yml` uses `../..` as the build context and as the bind mount.
- The Compose project name and `ROS_DOMAIN_ID` are derived from the checkout path
  (`cite_project_name`, `cite_domain_id` in `scripts/_lib.sh`).
- The generator writes `cite_generated` into `workspace/src/`, the sibling of `model/`
  (ADR-0021).
- The image tag is fixed at `cite-digital-twin:dev` (`docker-compose.yml`, `scripts/_lib.sh`),
  so two trees on one host overwrite each other's image.

## Options considered

### Option A — Tags only
Keep the three commits as tags and check them out when needed. Costs nothing in size. Not
chosen: a tag is not extractable on its own, the first milestone needs a one-line change to run
at all, and nothing would ever notice that a tag had stopped building.

### Option B — Keep the old capabilities alive in the main tree
Keep `cell_a`, the event-driven line and the fixed program working beside the real program.
Not chosen: every platform change would have to carry three generations of behaviour, which is
the cost ADR-0066 already started to pay by parking the line.

### Option C — Frozen, self-contained snapshots under `projects/`
Copy each milestone's tree into its own folder, runnable from that folder alone. Chosen, and the
duplication it costs is accepted by the project owner.

## Decision

Each milestone is kept permanently as a frozen, self-contained, runnable snapshot under
`projects/<name>/`, which builds and runs when the folder is copied anywhere else:

- `projects/01-three-arm-event-driven-line/` from `event-driven-line-v1` (`b5a0bc9`); if it does
  not run, the fallback source is `aed36c4`.
- `projects/02-fixed-program-pair/` from `c83119b`.
- `projects/03-real-program-twin-on-track/` from `e90d230`.

1. **Mechanism.** A committed script, `tools/snapshot_project.sh`, runs `git archive <sha>` into
   the folder, excluding `docs/measurements/`, `legacy/`, `real-robot-code/`, `CLAUDE.md`,
   `AGENTS.md`, `what-we-are-doing.md`, `projects/` (a snapshot never nests another), `.github/`
   (GitHub runs workflows from the repository root only, so a nested one never runs),
   `**/__pycache__/` and `workspace/log/`. It refuses a destination that exists and is not an
   empty directory. `tools/tests/test_snapshot_extractor.py` extracts `HEAD` and checks each
   exclusion from both sides, and the refusals. The facts in Context make the folder its own root
   with no code change.
2. **Only minimal patches, each listed with its rationale in the snapshot's `PROVENANCE.md`:**
   a per-project image tag, `cite-digital-twin:<name>` in place of `:dev`, so snapshots do not
   overwrite each other's image; for project 01 only, `DRIVEN_ZONE = "cell_a"` in
   `tests/scenarios/_cell.py`; and a top-level `run` wrapper, `README.md` and `PROVENANCE.md` in
   each. Nothing else is edited. **[Amended 2026-10-01 — a fourth file, `MEASUREMENTS.md`, is
  now a listed patch in each snapshot; see the amendment above.]** `.github/` is **not** a patch: it was removed by hand when the
   snapshots were first made and has since become one of the script's exclusions, and
   re-running the script against each source commit reproduces the unpatched extract at
   `3f475a3` exactly, less that directory. **A snapshot is a record, not a source.**
   **"Frozen" is checked, not only stated**: `projects/snapshots.yaml` pins each folder's
   committed git tree hash and `tools/tests/test_snapshots_are_frozen.py` fails on any
   difference, so every change to a snapshot — a patch or a verification-log row alike — carries
   a visible hash bump in the same commit.
3. **One-way rule.** Nothing may be copied from `projects/` back into the main tree, and the main
   tree never imports or builds from `projects/`. A snapshot's patterns are not precedent, for
   the same reason v1's are not ([`../reference/v1-lessons.md`](../reference/v1-lessons.md)).
   On that rule P1 holds: a snapshot is a record of a past state, not a second source of any
   value the main tree uses. **Half of this rule has a mechanical check and half cannot have
   one.** `tools/tests/test_nothing_reaches_into_a_snapshot.py` fails when a tracked main-tree
   file names a snapshot's path outside an allowlist of the files that document or run the
   snapshots, which is what building or importing from one would require. **Copy-back itself
   cannot be detected mechanically**: a value or function copied out of a snapshot carries no
   trace of its origin, so that half rests on review and on this rule.
4. **Main-tree checks are deliberately narrowed, and this is a reduction of coverage.** Exactly
   these changes, each with a test that fails if it widens beyond the top-level `projects/`
   (`tools/tests/test_snapshots_are_left_out.py`):
   - `tools/cite_tools/tree.py`'s `SKIP_PATHS` gains `projects`, which takes the snapshots out of
     every `./scripts/lint` walk (English, links) — with `projects/README.md` and
     `projects/snapshots.yaml`, which are main-tree files, still walked;
   - three `git ls-files` walkers drop the snapshots through the one predicate `in_a_snapshot`:
     `tools/tests/test_superseded_real_time_requirement.py`,
     `tools/tests/test_interface_counts.py` and `tools/tests/test_the_retracted_gripper_claim.py`;
   - one disk walker states the exclusion itself because it cannot import the predicate:
     `workspace/src/cite_test_hardware/test/test_unreachable.py`, which runs under ctest without
     `cite_tools`, adds `projects` to its root-anchored `SKIPPED`. Every other walker from the
     repository root was checked on 2026-09-29 and walks named trees that exclude `projects`
     (`test_a_removed_plan_key_stays_removed.py`, `test_declared_hardware_fact.py`,
     `cite_bringup/test/test_the_bridge_is_simulation_only.py`), reads through `our_files`
     (`test_rtf_figure_conditions.py`), or asks only about named main-tree paths
     (`test_event_driven_line_is_kept.py`);
   - `.yamllint` ignores the root-anchored `/projects/`, re-admitting `projects/snapshots.yaml`;
   - `.dockerignore` leaves `projects/` out of the main image's build context;
   - `scripts/lint`'s shellcheck gains the extractor `tools/*.sh` and each snapshot's `run`, named
     exactly and nothing else under `projects/`;
   - `.github/` is excluded at extraction (decision 1), so no snapshot carries a workflow.

   `tools/tests/test_a_removed_plan_key_stays_removed.py` walks seven named trees, none of them
   `projects`, and is unaffected. **A snapshot's contract is that it builds, its scenario passes
   and its `./run` runs** — decided by the project owner on 2026-09-29. Its own `./scripts/lint`,
   unit and host tests and `./scripts/doctor` are **outside** that contract and some fail by
   construction: the extract omits `docs/measurements/`, `CLAUDE.md` and the charter, so the link
   check reports roughly 193–195 dead links per snapshot into them and host tests that read them
   fail, and the `git ls-files` walkers need a git checkout of the folder. Each snapshot's
   `PROVENANCE.md` lists which, and none of those failures may be answered with a patch unless it
   stops the build, the scenario or `./run`.
5. **CI.** A separate, non-blocking workflow, `.github/workflows/projects.yml`
   (`workflow_dispatch` and a weekly schedule), runs a matrix over the snapshots: build the
   image, bootstrap, `validate-model`, build, and the project's scenario with
   `--teardown-advisory` — `continuous_line` for 01, `program_cycle` for 02 and 03. **The matrix
   is read from `projects/snapshots.yaml`**, the one list of the snapshots (name, source commit,
   image tag, scenario, scenario arguments, tree hash), by a first job; the workflow restates
   none of it. The three image builds share one GitHub Actions cache scope with `mode=min`, while
   their Dockerfiles are byte-identical. It does not gate `main`.
6. **Out of scope.** Removing the parked event-driven line, `cell_a` and the fixed-program
   leftovers from the main tree is a later branch with its own ADR.

## Consequences

### What this gets us
- Each milestone can be handed over as one folder and shown running, independent of where
  `main` has gone.
- The main tree is free to drop old capabilities later without losing a runnable record of them.
- A weekly job, rather than nobody, is what notices a snapshot has stopped building.

### What this costs us
- Repository size grows by roughly three copies of `workspace/src`, `model/` and `tools/`.
- Main-tree lint and four repository walkers — three `git ls-files` host tests and
  `cite_test_hardware`'s ctest walk — no longer see the snapshots. What the main tree still
  checks under `projects/` is exactly: `README.md` and `snapshots.yaml` walked (English, links)
  and the manifest yamllinted, each snapshot's `run` shellchecked, and each snapshot's tree
  hash-checked. Any other defect there is caught only by the weekly job, since a snapshot's own
  lint and tests are outside its contract.
- Every change to a snapshot, including a verification-log row, needs a tree-hash bump in
  `projects/snapshots.yaml`: deliberate friction, and the price of "frozen" being checked.
- Snapshots rot silently if nobody reads the weekly job, and a non-blocking job is easy to ignore.
- Security and dependency fixes are not backported to snapshots.
- A snapshot carries its own docs without `CLAUDE.md`; any figure in them was true at its source
  commit only, and the snapshot's `README.md` must say so.

### What we will have to revisit
- **Promotion condition:** all three snapshots verified to build and run their scenario from a
  folder copied outside the repository, recorded in each `PROVENANCE.md`, and the projects
  workflow has run green once, read from the step logs and not from the step conclusions.
- If project 01 cannot be made to run from `b5a0bc9`, record the switch to `aed36c4` in its
  `PROVENANCE.md` and amend this record.
- If a snapshot's upstream pins (image base, `external/cite.repos`) stop resolving, decide
  whether to repair it with a listed patch or retire it.
