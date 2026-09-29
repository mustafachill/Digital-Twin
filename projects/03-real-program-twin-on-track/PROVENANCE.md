# Provenance — `03-real-program-twin-on-track`

This folder is a frozen snapshot kept under
[ADR-0068](../../docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md) in the main
repository. It is a record of a past state, not a source: nothing here is copied back into
the main tree, and every edit it carries beyond the extract is listed below.

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
- any `__pycache__/`
- any `log/`

`.gitattributes` at the source commit declares no `export-ignore` or `export-subst`, so the
extract is exactly the tracked tree minus the paths above. At that commit no tracked path
lies under a `__pycache__/` or `log/` directory, so those two exclusions remove nothing.

## Patches

Nothing else is edited.

| # | Path | Change and why |
|---|---|---|
| 1 | `infra/docker/docker-compose.yml`, `scripts/_lib.sh`, `scripts/audit-deps`, `scripts/bootstrap` | The image tag `cite-digital-twin:dev` becomes `cite-digital-twin:p03-real-program` at every executable site. The tag was fixed, so the main tree and every snapshot on one host rebuilt and overwrote one image. Documentation that quotes `:dev` is left as it was: it records what was run at the time. |
| 2 | `.github/` (removed) | GitHub runs workflows from the repository root only, so a nested workflow never runs; the main repository's `.github/workflows/projects.yml` builds and runs this snapshot instead. |
| 3 | `run` (new) | The top-level entry point: a thin wrapper over `./scripts/program --zone cell_b`, every other argument passed through. |
| 4 | `PROVENANCE.md` (new) | This record. |
| 5 | `README.md` (replaced) | The source commit's README described the whole repository as it stood at that commit and pointed at `CLAUDE.md` and the charter, which are not in this folder. It is replaced by one describing this snapshot: what the milestone achieved, how to run and check it, how to take the folder out, and its known limits, drawn from the ADRs in `docs/adr/`. The source commit's README is still readable with `git show e90d230:README.md` in the main repository. |

Not patched, checked instead: the Compose project name and `ROS_DOMAIN_ID` are both derived
from the checkout's absolute path (`cite_project_name` and `cite_domain_id` in
`scripts/_lib.sh`), and the build volumes are declared bare in the compose file, so Compose
prefixes them with that per-path project name. Two snapshots and the main tree on one host
therefore get distinct volumes, containers, networks and domains without an edit.

### Diff against a clean extract

`diff -ru` of a fresh `tools/snapshot_project.sh e90d230` (`source/`) against this folder
(`snapshot/`), timestamps stripped. New files show as `Only in snapshot/…`; their content is
the file itself.

```diff
Only in source/03-real-program-twin-on-track: .github
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

## Verification log

Filled in by whoever runs it, one row per run. A run is a run, not a rate.

| Date | Command | Result | Who |
|---|---|---|---|
