# Provenance — `03-real-program-twin-on-track`

This folder is a frozen snapshot kept under
ADR-0068 (`docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md` in the main
repository; a path, not a link, because this folder is meant to be copied out). It is a
record of a past state, not a source: nothing here is copied back into the main tree, and every edit it carries beyond the extract is listed below.

## Source

| | |
|---|---|
| Commit | `e90d230224cf66cc84eb39443676ab28d2a9ed99` |
| Tag | none |
| Subject | Merge feat/real-program: the real xArm 5 program drives the twin, the arm rides a track (ADR-0067) |
| Commit date | 2026-09-29 |

The merge of ADR-0067's branch, `main`'s tip when ADR-0068 was written. `model/programs/xarm5_real_demo.blockly.xml`, the real program the twin reads, is tracked here and is in the extract.

## How it was made

From the main repository's root:

```
tools/snapshot_project.sh e90d230 projects/03-real-program-twin-on-track
```

The unpatched extract is committed on its own in the main repository at `3f475a3`, so
`git diff 3f475a3 -- <this folder>` shows every patch below and nothing else.

`git archive e90d230` of the whole tree, unpacked here. It reads the object database and
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
against `e90d230` reproduces the unpatched extract at `3f475a3` exactly, less that
`.github/` (checked 2026-09-29 with `diff -rq`).

## Patches

Nothing else is edited.

| # | Path | Change and why |
|---|---|---|
| 1 | `infra/docker/docker-compose.yml`, `scripts/_lib.sh`, `scripts/audit-deps`, `scripts/bootstrap` | The image tag `cite-digital-twin:dev` becomes `cite-digital-twin:p03-real-program` at every executable site. The tag was fixed, so the main tree and every snapshot on one host rebuilt and overwrote one image. Documentation that quotes `:dev` is left as it was: it records what was run at the time. |
| 2 | `run` (new) | The top-level entry point: a thin wrapper over `./scripts/program --zone cell_b`, every other argument passed through. |
| 3 | `PROVENANCE.md` (new) | This record. |
| 4 | `README.md` (replaced) | The source commit's README described the whole repository as it stood at that commit and pointed at `CLAUDE.md` and the charter, which are not in this folder. It is replaced by one describing this snapshot: what the milestone achieved, how to run and check it, how to take the folder out, and its known limits, drawn from the ADRs in `docs/adr/`. The source commit's README is still readable with `git show e90d230:README.md` in the main repository. |
| 5 | `MEASUREMENTS.md` (new, 2026-10-01) | This snapshot's measurement point. No measurement of this milestone has been recorded in it yet (the two main-repository counts first placed here when the main repository's `CLAUDE.md` was cut back on 2026-10-01 were moved out the same day), and any later measurement of this snapshot is added here rather than anywhere in the main tree. Verification runs stay in this file's verification log. Allowed by the main repository's ADR-0068 amendment of 2026-10-01. |

Not patched, checked instead: the Compose project name and `ROS_DOMAIN_ID` are both derived
from the checkout's absolute path (`cite_project_name` and `cite_domain_id` in
`scripts/_lib.sh`), and the build volumes are declared bare in the compose file, so Compose
prefixes them with that per-path project name. Two snapshots and the main tree on one host
therefore get distinct volumes, containers, networks and domains without an edit.

**Distinct, not guaranteed distinct.** The domain is a checksum of the absolute path folded
onto 50 odd bases (`cite_domain_id`), so two arbitrary paths can land on the same one. On
the development host, at `/home/cite/Developer/Digital-Twin/projects/03-real-program-twin-on-track/`, it derives 57, against 43 for the main tree there and a different value for
each other snapshot; a copy elsewhere derives its own. `./scripts/doctor` prints the
domain in use and says whether it was derived or set. To choose one, export `ROS_DOMAIN_ID`
before any script: `_lib.sh` keeps an explicit value rather than deriving one. A paired
snapshot also claims the even domain above that base for its counterpart.

### Diff against a clean extract

`diff -ru` of a fresh `tools/snapshot_project.sh e90d230` (`source/`) against this folder
(`snapshot/`), timestamps stripped. New files show as `Only in snapshot/…`; their content is
the file itself.

```diff
diff -ru source/03-real-program-twin-on-track/infra/docker/docker-compose.yml snapshot/03-real-program-twin-on-track/infra/docker/docker-compose.yml
--- source/03-real-program-twin-on-track/infra/docker/docker-compose.yml
+++ snapshot/03-real-program-twin-on-track/infra/docker/docker-compose.yml
@@ -66,7 +66,7 @@
     args:
       USER_UID: ${CITE_UID:-1001}
       USER_GID: ${CITE_GID:-1001}
-  image: cite-digital-twin:dev
+  image: cite-digital-twin:p03-real-program
   working_dir: /workspace
   volumes:
     # The repository, mounted rather than copied: edits on the host are visible
Only in snapshot/03-real-program-twin-on-track/: MEASUREMENTS.md
Only in snapshot/03-real-program-twin-on-track/: run
diff -ru source/03-real-program-twin-on-track/scripts/audit-deps snapshot/03-real-program-twin-on-track/scripts/audit-deps
--- source/03-real-program-twin-on-track/scripts/audit-deps
+++ snapshot/03-real-program-twin-on-track/scripts/audit-deps
@@ -43,7 +43,7 @@
 # which lives in the container. Do the image export here, on the host, before
 # handing off — otherwise the image branch can never execute, which is how a
 # documented capability quietly becomes dead code.
-IMAGE="${CITE_IMAGE:-cite-digital-twin:dev}"
+IMAGE="${CITE_IMAGE:-cite-digital-twin:p03-real-program}"
 IMAGE_TAR=""
 if [ "$SCAN_IMAGE" -eq 1 ] && ! in_container; then
     if ! have docker; then
diff -ru source/03-real-program-twin-on-track/scripts/bootstrap snapshot/03-real-program-twin-on-track/scripts/bootstrap
--- source/03-real-program-twin-on-track/scripts/bootstrap
+++ snapshot/03-real-program-twin-on-track/scripts/bootstrap
@@ -233,7 +233,7 @@
 fi
 
 step "Container image"
-info "Building cite-digital-twin:dev — first run takes a while"
+info "Building cite-digital-twin:p03-real-program — first run takes a while"
 compose build dev
 ok "Image built"
 
diff -ru source/03-real-program-twin-on-track/scripts/_lib.sh snapshot/03-real-program-twin-on-track/scripts/_lib.sh
--- source/03-real-program-twin-on-track/scripts/_lib.sh
+++ snapshot/03-real-program-twin-on-track/scripts/_lib.sh
@@ -1004,7 +1004,7 @@
 
     # Warn before a first-run image build. Without this, `./scripts/test` on a
     # machine with no image looks like it has hung for ten minutes.
-    if ! docker image inspect cite-digital-twin:dev >/dev/null 2>&1; then
+    if ! docker image inspect cite-digital-twin:p03-real-program >/dev/null 2>&1; then
         warn "The container image does not exist yet and must be built first."
         warn "This takes several minutes. Run ./scripts/bootstrap to do it explicitly,"
         warn "or wait while it happens now."
```

## What this snapshot promises, and what it does not

**The contract is three things: it builds (`./scripts/bootstrap`, `./scripts/build`),
the scenario `program_cycle` passes, and `./run` runs.** That is what ADR-0068 and the main repository's
weekly projects workflow hold it to.

**Its own lint, unit tests and `./scripts/doctor` are outside the contract, and some of them
fail by construction.** The extract leaves out `docs/measurements/`, `CLAUDE.md` and
`what-we-are-doing.md`, and the folder is not a git checkout once copied out. Expected to fail,
identified by reading and grep on 2026-09-29 rather than by a run of each:

- **`./scripts/lint`'s link check** — 195 dead links, every one of them into
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
| 2026-09-29/30 | `./scripts/bootstrap` | exit 0, 575 s. At main-repository commit `03261a3`; nothing under this folder but `README.md` and `PROVENANCE.md` has changed since (`git diff --stat 03261a3..d16885a`). | tester agent, one machine |
| 2026-09-29/30 | `./scripts/validate-model` | exit 0, `ok model valid — 2 zone(s), 8 type(s), 22 asset(s), 8 station(s), across 19 file(s)`. At `03261a3`. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/build` | exit 0, `Summary: 23 packages finished [3min 58s]`. At `03261a3`. | tester agent, one machine |
| 2026-09-29/30 | `./scripts/scenario program_cycle --zone cell_b` | exit 0, `Scenario 'program_cycle' passed` (cycle and teardown both), `Ran 1 test in 98.672s`; one genuine stall, `commanded 60.9 mm, reached 65.8 mm, stalled=true … -> holding`. At `03261a3`. | tester agent, one machine |
| 2026-09-29/30 | `./run --headless` | exit 0, 96 s, all 22 steps, `done: 1 cycle(s)`. Box on the plant at x=+1.944 y=+3.060 z=+0.631, on the counterpart identical to 3 decimals; the outfeed frame is at x=+1.855. Pair teardown: `plant: ready=True status=1`, `counterpart: ready=True status=1`, `boundary: ready=True status=0` — why the two sides exited 1 was not read. At `03261a3`. | tester agent, one machine |
| 2026-09-29/30 | `cp -a` of this folder to a scratch directory outside any git checkout, copied `.venv/` deleted, then `./scripts/validate-model` and `./scripts/build` | both exit 0; build `Summary: 23 packages finished [4min 8s]`. | tester agent, one machine |
| 2026-09-29/30 | `cp -a` of this folder **with** the copied `.venv/`, then `./scripts/bootstrap` in the copy | bootstrap re-pointed the **original** folder's `.venv/`, not the copy's — the reason README.md now says to take a copy with `git archive` or `rsync --exclude .venv`. | tester agent, one machine |

Each row above is a single run on one machine, not a rate.
