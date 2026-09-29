# Provenance — `01-three-arm-event-driven-line`

This folder is a frozen snapshot kept under
[ADR-0068](../../docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md) in the main
repository. It is a record of a past state, not a source: nothing here is copied back into
the main tree, and every edit it carries beyond the extract is listed below.

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
- any `__pycache__/`
- any `log/`

`.gitattributes` at the source commit declares no `export-ignore` or `export-subst`, so the
extract is exactly the tracked tree minus the paths above. At that commit no tracked path
lies under a `__pycache__/` or `log/` directory, so those two exclusions remove nothing.

## Patches

Nothing else is edited.

| # | Path | Change and why |
|---|---|---|
| 1 | `infra/docker/docker-compose.yml`, `scripts/_lib.sh`, `scripts/audit-deps`, `scripts/bootstrap` | The image tag `cite-digital-twin:dev` becomes `cite-digital-twin:p01-three-arm-line` at every executable site. The tag was fixed, so the main tree and every snapshot on one host rebuilt and overwrote one image. Documentation that quotes `:dev` is left as it was: it records what was run at the time. |
| 2 | `.github/` (removed) | GitHub runs workflows from the repository root only, so a nested workflow never runs; the main repository's `.github/workflows/projects.yml` builds and runs this snapshot instead. |
| 3 | `tests/scenarios/_cell.py` | `DRIVEN_ZONE = "cell_b"` becomes `"cell_a"`. At the tag the scenarios already drove the one-arm `cell_b`, so without this `./scripts/scenario continuous_line` would not drive the three-arm line this snapshot keeps. `./scripts/scenario` follows it with no further change: `_cell.zone()` returns `CITE_SCENARIO_ZONE` when `--zone` sets it and `DRIVEN_ZONE` otherwise, and every scenario binds `ZONE = zone()`. |
| 4 | `run` (new) | The top-level entry point: brings `cell_a` up with `./scripts/sim --zone cell_a line:=true [--headless]`, waits for the cell's readiness token, then feeds work-pieces onto the pick table one at a time and watches each reach the sink beam, reusing `cite_bringup.demo`, `cite_bringup.gz` and `cite_bringup.workpiece` unedited. `./scripts/demo` at this commit drives a pair on `cell_b`, not this line. |
| 5 | `PROVENANCE.md` (new) | This record. |
| 6 | `README.md` (replaced) | The source commit's README described the whole repository as it stood at that commit and pointed at `CLAUDE.md` and the charter, which are not in this folder. It is replaced by one describing this snapshot: what the milestone achieved, how to run and check it, how to take the folder out, and its known limits, drawn from the ADRs in `docs/adr/`. The source commit's README is still readable with `git show b5a0bc9:README.md` in the main repository. |

Not patched, checked instead: the Compose project name and `ROS_DOMAIN_ID` are both derived
from the checkout's absolute path (`cite_project_name` and `cite_domain_id` in
`scripts/_lib.sh`), and the build volumes are declared bare in the compose file, so Compose
prefixes them with that per-path project name. Two snapshots and the main tree on one host
therefore get distinct volumes, containers, networks and domains without an edit.

### Diff against a clean extract

`diff -ru` of a fresh `tools/snapshot_project.sh b5a0bc9` (`source/`) against this folder
(`snapshot/`), timestamps stripped. New files show as `Only in snapshot/…`; their content is
the file itself.

```diff
Only in source/01-three-arm-event-driven-line: .github
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

## Verification log

Filled in by whoever runs it, one row per run. A run is a run, not a rate.

| Date | Command | Result | Who |
|---|---|---|---|
