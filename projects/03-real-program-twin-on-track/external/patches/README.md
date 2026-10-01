# external/patches/

Local modifications to third-party dependencies live here as patch files. They
are applied by `./scripts/bootstrap` after `vcs import`, in filename order.

## Why patches instead of editing the checkout

An edit made inside a checked-out dependency is invisible to git, lost on the
next `vcs import`, and impossible to review. The previous iteration of this
project lost a critical `gazebo_ros2_control` fix exactly this way: the patch
existed on one machine, was never committed anywhere, and a fresh clone could
not build. [ADR-0008](../../docs/adr/0008-external-dependencies-via-vcstool.md)
is the decision that closes that failure. The v1 tree was deleted at the end of
Phase 1, and [`docs/reference/v1-lessons.md`](../../docs/reference/v1-lessons.md)
records under *What this page does not capture* that the patch itself was never
in this repository — only v1's own description of it, which survives in git
history and nowhere else.

A patch file is visible in the diff, reviewable in a pull request, survives a
dependency update as a merge conflict rather than a silent loss, and documents
its own reason for existing.

## Naming

    NN-<repo>-<short-description>.patch

`NN` orders application. Example: `01-xarm_ros2-jazzy-cmake-fix.patch`.

## Two patches touch one file, and their order is a constraint

`02-xarm_ros2-gripper-drive-rate-parameter.patch` and
`03-xarm_ros2-collision-mesh-root.patch` both add a parameter to
`xarm_device_macro.xacro`'s parameter list, within a few lines of each other. **Patch 03's
insertion point is load-bearing for patch 02, and nothing said so until 2026-08-31.**

Move 03's inserted line one line lower and 02 no longer reverse-applies. `patch_state` in
`scripts/_lib.sh` asks the reverse question first, so an applied-but-shifted 02 reads as
neither `applied` nor `pending` and comes back **`conflict`** — which is fatal, and which
stops a second `./scripts/bootstrap` on a checkout where nothing is actually wrong.

Reproduced on 2026-08-31 in a throwaway clone of the pinned vendor commit: applying 01, 02 and
an unmodified 03 leaves `patch_state` reporting **`applied`** for 02; applying 01, 02 and a 03
whose `collision_mesh_path:=''` sits one line lower leaves it reporting **`conflict`** for the
same unmodified 02. One anchor, one run, and the mechanism rather than a rate.

The cost is not the failure, which is loud. It is that the failure **names the wrong cause**:
`conflict` is documented as "the usual cause is a version bump that moved the code the patch
edits", and the next person to refresh 02 against a vendor bump will read that and go looking
upstream.

**So: refreshing either of these two means regenerating both, against the same checkout, in
bootstrap's order.** Do not hand-edit one patch's context lines to make it apply.

## Every patch must carry a header

```
# Repo:     external/xarm_ros2
# Upstream: https://github.com/xArm-Developer/xarm_ros2/issues/NNN
# Reason:   One sentence on what breaks without this.
# Removal:  The condition under which this patch can be deleted.
```

A patch with no removal condition is a permanent fork. If that is genuinely the
intent, say so in the header and write an ADR — do not leave it implied.

## A declared patch that is not present is a build failure

`./scripts/bootstrap` classifies every patch into one of four states and only one
of them is quiet:

| State | What happens |
|---|---|
| already applied | `ok`, and bootstrap continues. This is what makes re-running it idempotent. |
| applies cleanly | applied, then `ok`. |
| does not apply and is not present | **bootstrap stops**, naming the patch and the reason. |
| target checkout missing or empty | **bootstrap stops**. An empty target is an import that failed part-way. |

`./scripts/doctor` audits the same four states without applying anything, so the
question "is every declared patch actually in the build?" is answerable in one
second on any machine, with or without ROS. Both use `patch_state` in
`scripts/_lib.sh`, so the applier and the auditor cannot drift apart.

This is not decoration. `01-xarm_ros2-gripper-mimic-joints.patch` was committed
and then absent from every build and every measurement for hours: bootstrap asked
only `git apply --check`, so "already applied" and "does not apply" both fell to
the same `info` line — *"already applied or does not apply — skipped"* — and
nothing else in the repository looked at all.

## Generating one

```bash
cd workspace/src/external/<repo>
git diff > ../../../../external/patches/NN-<repo>-<description>.patch
```
