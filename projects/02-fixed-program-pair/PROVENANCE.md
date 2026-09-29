# Provenance — `02-fixed-program-pair`

This folder is a frozen snapshot kept under
[ADR-0068](../../docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md) in the main
repository. It is a record of a past state, not a source: nothing here is copied back into
the main tree, and every edit it carries beyond the extract is listed below.

## Source

| | |
|---|---|
| Commit | `c83119b5f95063c27b40a397fd0f5094feb00ec2` |
| Tag | none |
| Subject | Merge feat/gui-camera: Gazebo opens framed on the cell from the customer side |
| Commit date | 2026-09-29 |

The last commit on `main` before ADR-0067's branch: it is the parent of `1c22ebd`, that branch's first commit, and `e02fb67` on the same branch removed the taught poses from L0. Checked before extracting: `model/assets/instances/arms.yaml` carries `poses_rad` here (`git show c83119b:model/assets/instances/arms.yaml`), and `40728e6` (`fix(program): bound the wait for RobotState by the wall clock, not by spins`, `RosCell._until_true` in `workspace/src/cite_bringup/cite_bringup/program/cell.py`) is an ancestor (`git merge-base --is-ancestor 40728e6 c83119b`). It also carries the two fixes merged after the fixed program and before ADR-0067 — `fb517d4` (program and demo replace this checkout's running container) and `ea8f835` (sides hear the supervisor's SIGINT) — and the windowed camera framing from `8133c46`/`a712aec`. No later commit on `main` predates ADR-0067, so there is no better source.

## How it was made

From the main repository's root:

```
tools/snapshot_project.sh c83119b projects/02-fixed-program-pair
```

The unpatched extract is committed on its own in the main repository at `3f475a3`, so
`git diff 3f475a3 -- <this folder>` shows every patch below and nothing else.

`git archive c83119b` of the whole tree, unpacked here. It reads the object database and
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
| 1 | `infra/docker/docker-compose.yml`, `scripts/_lib.sh`, `scripts/audit-deps`, `scripts/bootstrap` | The image tag `cite-digital-twin:dev` becomes `cite-digital-twin:p02-fixed-program` at every executable site. The tag was fixed, so the main tree and every snapshot on one host rebuilt and overwrote one image. Documentation that quotes `:dev` is left as it was: it records what was run at the time. |
| 2 | `.github/` (removed) | GitHub runs workflows from the repository root only, so a nested workflow never runs; the main repository's `.github/workflows/projects.yml` builds and runs this snapshot instead. |
| 3 | `run` (new) | The top-level entry point: a thin wrapper over `./scripts/program --zone cell_b`, every other argument passed through. |
| 4 | `PROVENANCE.md` (new) | This record. |
| 5 | `README.md` (replaced) | The source commit's README described the whole repository as it stood at that commit and pointed at `CLAUDE.md` and the charter, which are not in this folder. It is replaced by one describing this snapshot: what the milestone achieved, how to run and check it, how to take the folder out, and its known limits, drawn from the ADRs in `docs/adr/`. The source commit's README is still readable with `git show c83119b:README.md` in the main repository. |

Not patched, checked instead: the Compose project name and `ROS_DOMAIN_ID` are both derived
from the checkout's absolute path (`cite_project_name` and `cite_domain_id` in
`scripts/_lib.sh`), and the build volumes are declared bare in the compose file, so Compose
prefixes them with that per-path project name. Two snapshots and the main tree on one host
therefore get distinct volumes, containers, networks and domains without an edit.

### Diff against a clean extract

`diff -ru` of a fresh `tools/snapshot_project.sh c83119b` (`source/`) against this folder
(`snapshot/`), timestamps stripped. New files show as `Only in snapshot/…`; their content is
the file itself.

```diff
Only in source/02-fixed-program-pair: .github
diff -ru source/02-fixed-program-pair/infra/docker/docker-compose.yml snapshot/02-fixed-program-pair/infra/docker/docker-compose.yml
--- source/02-fixed-program-pair/infra/docker/docker-compose.yml
+++ snapshot/02-fixed-program-pair/infra/docker/docker-compose.yml
@@ -66,7 +66,7 @@
     args:
       USER_UID: ${CITE_UID:-1001}
       USER_GID: ${CITE_GID:-1001}
-  image: cite-digital-twin:dev
+  image: cite-digital-twin:p02-fixed-program
   working_dir: /workspace
   volumes:
     # The repository, mounted rather than copied: edits on the host are visible
Only in snapshot/02-fixed-program-pair/: run
diff -ru source/02-fixed-program-pair/scripts/audit-deps snapshot/02-fixed-program-pair/scripts/audit-deps
--- source/02-fixed-program-pair/scripts/audit-deps
+++ snapshot/02-fixed-program-pair/scripts/audit-deps
@@ -43,7 +43,7 @@
 # which lives in the container. Do the image export here, on the host, before
 # handing off — otherwise the image branch can never execute, which is how a
 # documented capability quietly becomes dead code.
-IMAGE="${CITE_IMAGE:-cite-digital-twin:dev}"
+IMAGE="${CITE_IMAGE:-cite-digital-twin:p02-fixed-program}"
 IMAGE_TAR=""
 if [ "$SCAN_IMAGE" -eq 1 ] && ! in_container; then
     if ! have docker; then
diff -ru source/02-fixed-program-pair/scripts/bootstrap snapshot/02-fixed-program-pair/scripts/bootstrap
--- source/02-fixed-program-pair/scripts/bootstrap
+++ snapshot/02-fixed-program-pair/scripts/bootstrap
@@ -233,7 +233,7 @@
 fi
 
 step "Container image"
-info "Building cite-digital-twin:dev — first run takes a while"
+info "Building cite-digital-twin:p02-fixed-program — first run takes a while"
 compose build dev
 ok "Image built"
 
diff -ru source/02-fixed-program-pair/scripts/_lib.sh snapshot/02-fixed-program-pair/scripts/_lib.sh
--- source/02-fixed-program-pair/scripts/_lib.sh
+++ snapshot/02-fixed-program-pair/scripts/_lib.sh
@@ -1004,7 +1004,7 @@
 
     # Warn before a first-run image build. Without this, `./scripts/test` on a
     # machine with no image looks like it has hung for ten minutes.
-    if ! docker image inspect cite-digital-twin:dev >/dev/null 2>&1; then
+    if ! docker image inspect cite-digital-twin:p02-fixed-program >/dev/null 2>&1; then
         warn "The container image does not exist yet and must be built first."
         warn "This takes several minutes. Run ./scripts/bootstrap to do it explicitly,"
         warn "or wait while it happens now."
```

## Verification log

Filled in by whoever runs it, one row per run. A run is a run, not a rate.

| Date | Command | Result | Who |
|---|---|---|---|
