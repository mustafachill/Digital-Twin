# Provenance — `01-three-arm-event-driven-line`

This folder is a frozen snapshot kept under
ADR-0068 (`docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md` in the main
repository; a path, not a link, because this folder is meant to be copied out). It is a
record of a past state, not a source: nothing here is copied back into the main tree, and every edit it carries beyond the extract is listed below.

## Source

| | |
|---|---|
| Commit | `b5a0bc9e86b192b012c42f79c39623f5a292cd57` |
| Tag | `event-driven-line-v1` |
| Subject | Merge feat/materials-from-l0: the cell has its colours and a demo you can watch |
| Commit date | 2026-09-28 |

The tag `event-driven-line-v1` points at this commit, the last on `main` before ADR-0066 parked the event-driven line. ADR-0068 names `aed36c4` as the fallback source if the line does not run from here; that switch has not been made.

## How it was made

From the main repository's root:

```
tools/snapshot_project.sh b5a0bc9 projects/01-three-arm-event-driven-line
```

The unpatched extract is committed on its own in the main repository at `3f475a3`, so
`git diff 3f475a3 -- <this folder>` shows every patch below and nothing else.

`git archive b5a0bc9` of the whole tree, unpacked here. It reads the object database and
never the working tree, so nothing untracked or uncommitted can enter. Excluded:

- docs/measurements/
- legacy/
- real-robot-code/
- CLAUDE.md
- AGENTS.md
- what-we-are-doing.md
- projects/
- .github/ — GitHub runs workflows from the repository root only, so a nested workflow
  never runs; the main repository's `.github/workflows/projects.yml` builds and runs this
  snapshot instead
- any `__pycache__/`
- workspace/log/

`.gitattributes` at the source commit declares no `export-ignore` or `export-subst`, so the
extract is exactly the tracked tree minus the paths above. At that commit no tracked path
lies under `projects/`, a `__pycache__/` directory or `workspace/log/`, so those three
exclusions remove nothing. `.github/` was removed by hand when this snapshot was first
made and has been part of the script's exclusions since; re-running the command above
against `b5a0bc9` reproduces the unpatched extract at `3f475a3` exactly, less that
`.github/` (checked 2026-09-29 with `diff -rq`).

## Patches

Nothing else is edited.

| # | Path | Change and why |
|---|---|---|
| 1 | `infra/docker/docker-compose.yml`, `scripts/_lib.sh`, `scripts/audit-deps`, `scripts/bootstrap` | The image tag `cite-digital-twin:dev` becomes `cite-digital-twin:p01-three-arm-line` at every executable site. The tag was fixed, so the main tree and every snapshot on one host rebuilt and overwrote one image. Documentation that quotes `:dev` is left as it was: it records what was run at the time. |
| 2 | `tests/scenarios/_cell.py` | `DRIVEN_ZONE = "cell_b"` becomes `"cell_a"`. At the tag the scenarios already drove the one-arm `cell_b`, so without this `./scripts/scenario continuous_line` would not drive the three-arm line this snapshot keeps. `./scripts/scenario` follows it with no further change: `_cell.zone()` returns `CITE_SCENARIO_ZONE` when `--zone` sets it and `DRIVEN_ZONE` otherwise, and every scenario binds `ZONE = zone()`. |
| 3 | `run` (new) | The top-level entry point: brings `cell_a` up with `./scripts/sim --zone cell_a line:=true [--headless]`, waits for the cell's readiness token and then, as `tests/scenarios/continuous_line.py` does, for the first `LineState` on `LineState.TOPIC`, then feeds work-pieces onto the pick table one at a time, watches each reach the sink beam and confirms its removal from a pose snapshot, reusing `cite_bringup.demo`, `cite_bringup.gz` and `cite_bringup.workpiece` unedited. `./scripts/demo` at this commit drives a pair on `cell_b`, not this line. The cell's log is written under `workspace/log/run/`, this snapshot's log volume, so it outlives the container. Every wait in it is bounded by a ceiling and ends on its condition; the 900 s per-piece ceiling is stated, not measured. |
| 4 | `PROVENANCE.md` (new) | This record. |
| 5 | `README.md` (replaced) | The source commit's README described the whole repository as it stood at that commit and pointed at `CLAUDE.md` and the charter, which are not in this folder. It is replaced by one describing this snapshot: what the milestone achieved, how to run and check it, how to take the folder out, and its known limits, drawn from the ADRs in `docs/adr/`. The source commit's README is still readable with `git show b5a0bc9:README.md` in the main repository. |
| 6 | `MEASUREMENTS.md` (new, 2026-10-01) | This snapshot's measurement point. The measurements the main repository's `CLAUDE.md` held whose subject is this milestone were moved here, verbatim, when that file was cut back on 2026-10-01, and any later measurement of this snapshot is added here rather than anywhere in the main tree. Verification runs stay in this file's verification log. Allowed by the main repository's ADR-0068 amendment of 2026-10-01. |

Not patched, checked instead: the Compose project name and `ROS_DOMAIN_ID` are both derived
from the checkout's absolute path (`cite_project_name` and `cite_domain_id` in
`scripts/_lib.sh`), and the build volumes are declared bare in the compose file, so Compose
prefixes them with that per-path project name. Two snapshots and the main tree on one host
therefore get distinct volumes, containers, networks and domains without an edit.

**Distinct, not guaranteed distinct.** The domain is a checksum of the absolute path folded
onto 50 odd bases (`cite_domain_id`), so two arbitrary paths can land on the same one. On
the development host, at `/home/cite/Developer/Digital-Twin/projects/01-three-arm-event-driven-line/`, it derives 63, against 43 for the main tree there and a different value for
each other snapshot; a copy elsewhere derives its own. `./scripts/doctor` prints the
domain in use and says whether it was derived or set. To choose one, export `ROS_DOMAIN_ID`
before any script: `_lib.sh` keeps an explicit value rather than deriving one. A paired
snapshot also claims the even domain above that base for its counterpart.

### Diff against a clean extract

`diff -ru` of a fresh `tools/snapshot_project.sh b5a0bc9` (`source/`) against this folder
(`snapshot/`), timestamps stripped. New files show as `Only in snapshot/…`; their content is
the file itself.

```diff
diff -ru source/01-three-arm-event-driven-line/infra/docker/docker-compose.yml snapshot/01-three-arm-event-driven-line/infra/docker/docker-compose.yml
--- source/01-three-arm-event-driven-line/infra/docker/docker-compose.yml
+++ snapshot/01-three-arm-event-driven-line/infra/docker/docker-compose.yml
@@ -66,7 +66,7 @@
     args:
       USER_UID: ${CITE_UID:-1001}
       USER_GID: ${CITE_GID:-1001}
-  image: cite-digital-twin:dev
+  image: cite-digital-twin:p01-three-arm-line
   working_dir: /workspace
   volumes:
     # The repository, mounted rather than copied: edits on the host are visible
Only in snapshot/01-three-arm-event-driven-line/: MEASUREMENTS.md
Only in snapshot/01-three-arm-event-driven-line/: run
diff -ru source/01-three-arm-event-driven-line/scripts/audit-deps snapshot/01-three-arm-event-driven-line/scripts/audit-deps
--- source/01-three-arm-event-driven-line/scripts/audit-deps
+++ snapshot/01-three-arm-event-driven-line/scripts/audit-deps
@@ -43,7 +43,7 @@
 # which lives in the container. Do the image export here, on the host, before
 # handing off — otherwise the image branch can never execute, which is how a
 # documented capability quietly becomes dead code.
-IMAGE="${CITE_IMAGE:-cite-digital-twin:dev}"
+IMAGE="${CITE_IMAGE:-cite-digital-twin:p01-three-arm-line}"
 IMAGE_TAR=""
 if [ "$SCAN_IMAGE" -eq 1 ] && ! in_container; then
     if ! have docker; then
diff -ru source/01-three-arm-event-driven-line/scripts/bootstrap snapshot/01-three-arm-event-driven-line/scripts/bootstrap
--- source/01-three-arm-event-driven-line/scripts/bootstrap
+++ snapshot/01-three-arm-event-driven-line/scripts/bootstrap
@@ -233,7 +233,7 @@
 fi
 
 step "Container image"
-info "Building cite-digital-twin:dev — first run takes a while"
+info "Building cite-digital-twin:p01-three-arm-line — first run takes a while"
 compose build dev
 ok "Image built"
 
diff -ru source/01-three-arm-event-driven-line/scripts/_lib.sh snapshot/01-three-arm-event-driven-line/scripts/_lib.sh
--- source/01-three-arm-event-driven-line/scripts/_lib.sh
+++ snapshot/01-three-arm-event-driven-line/scripts/_lib.sh
@@ -989,7 +989,7 @@
 
     # Warn before a first-run image build. Without this, `./scripts/test` on a
     # machine with no image looks like it has hung for ten minutes.
-    if ! docker image inspect cite-digital-twin:dev >/dev/null 2>&1; then
+    if ! docker image inspect cite-digital-twin:p01-three-arm-line >/dev/null 2>&1; then
         warn "The container image does not exist yet and must be built first."
         warn "This takes several minutes. Run ./scripts/bootstrap to do it explicitly,"
         warn "or wait while it happens now."
diff -ru source/01-three-arm-event-driven-line/tests/scenarios/_cell.py snapshot/01-three-arm-event-driven-line/tests/scenarios/_cell.py
--- source/01-three-arm-event-driven-line/tests/scenarios/_cell.py
+++ snapshot/01-three-arm-event-driven-line/tests/scenarios/_cell.py
@@ -49,7 +49,7 @@
 #: `bringup` against `cell_a`" as the answer if the showcase is found broken, and
 #: `SELECTED_BY` below is what makes that a command rather than a commit:
 #: `./scripts/scenario bringup --zone cell_a`.
-DRIVEN_ZONE = "cell_b"
+DRIVEN_ZONE = "cell_a"
 
 #: Where `./scripts/scenario --zone` puts its answer. An environment variable
 #: rather than an argument because `launch_test` owns the scenario's argv and
```

## What this snapshot promises, and what it does not

**The contract is three things: it builds (`./scripts/bootstrap`, `./scripts/build`),
the scenario `continuous_line` passes, and `./run` runs.** That is what ADR-0068 and the main repository's
weekly projects workflow hold it to.

**Its own lint, unit tests and `./scripts/doctor` are outside the contract, and some of them
fail by construction.** The extract leaves out `docs/measurements/`, `CLAUDE.md` and
`what-we-are-doing.md`, and the folder is not a git checkout once copied out. Expected to fail,
identified by reading and grep on 2026-09-29 rather than by a run of each:

- **`./scripts/lint`'s link check** — 193 dead links, every one of them into
  `docs/measurements/`, `CLAUDE.md`, `AGENTS.md` or `what-we-are-doing.md` (counted by running
  this folder's own `cite_tools.doclinks` over it).
- **Host tests under `tools/tests/` that read the charter, `CLAUDE.md` or
  `docs/measurements/`** — for example `test_rtf_figure_conditions.py` and
  `test_stall_band.py`.
- **Host tests that walk `git ls-files`** — `test_interface_counts.py`,
  `test_superseded_real_time_requirement.py`, `test_the_retracted_gripper_claim.py`,
  `test_a_removed_plan_key_stays_removed.py`, `test_declared_hardware_fact.py` among them —
  which find no files, or the wrong ones, outside a git checkout of this folder.
- **`./scripts/doctor`**, whose checks include the ADR index and paths this extract omits.

None of those failures is a defect in the milestone, and none may be "fixed" by a patch here
unless it stops the build, the scenario or `./run`.

## Verification log

Filled in by whoever runs it, one row per run. A run is a run, not a rate.

| Date | Command | Result | Who |
|---|---|---|---|
| 2026-09-29/30 | `./scripts/bootstrap` | exit 0. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/validate-model` | exit 0, `… 2 zone(s), 7 type(s), 22 asset(s), 8 station(s), across 17 file(s)`. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/build` | exit 0, 23 packages. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/scenario continuous_line --zone cell_a` (first run) | **exit 1**, `Scenario 'continuous_line' failed — 1 cycle assertion(s) failed`. Piece 1 stopped after 1 of 10 milestones, waiting 420 s on `lifted(station_transfer_1)` while `LineState` read `RUNNING`: the silent dead end at the table-fed `station_transfer_1`, where nothing escalates. The piece never reached `lifted`, so this is not the lifted-then-held signature README.md lists from CI. Not attributed. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/scenario continuous_line --zone cell_a` (re-run) | exit 0, `Scenario 'continuous_line' passed`, `wp_000003 reached station_accumulation; 3 completed`, `Ran 1 test in 325.669s`. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/scenario pick_and_place --zone cell_a` | **exit 1**, `Scenario 'pick_and_place' failed — 1 teardown assertion(s) failed`. Cycle passed (`Ran 1 test in 83.772s`, genuine stall, commanded 45.0 mm, reached 49.4 mm); teardown failed on `gz-1 exited with -9`, a known signature, unclassified. | tester agent, one machine |
| 2026-09-29/30 | `./run` before main-repository commit `51d6cf8` | hung at teardown: SIGINT was ignored by the background launch job. Fixed at `51d6cf8`. | tester agent, one machine |
| 2026-09-29/30 | `./run --headless` at `d16885a` | exit 0, 338 s. `work-piece 1 reached beam_c3_out after 109 s`, 2 after 91 s, 3 after 92 s; `all 3 work-piece(s) carried from the pick table to the sink`; `the cell is down`. `move_group` exited -11 three times at teardown, the known upstream member. | tester agent, one machine |
| 2026-09-29/30 | `./run` at `d16885a`, SIGINT sent to its process group at 60 s (no TTY) | `./run` exited 130 immediately; the container finished an orderly teardown about 25 s later, no orphaned containers. A keyboard Ctrl-C was not tested. | tester agent, one machine |

Each row above is a single run on one machine, not a rate. Where no commit is named, the report
the rows were copied from did not name one.
