# external/patches/

Local modifications to third-party dependencies live here as patch files. They
are applied by `./scripts/bootstrap` after `vcs import`, in filename order.

## Why patches instead of editing the checkout

An edit made inside a checked-out dependency is invisible to git, lost on the
next `vcs import`, and impossible to review. The previous iteration of this
project lost a critical `gazebo_ros2_control` fix exactly this way: the patch
existed on one machine, was never committed anywhere, and a fresh clone could
not build. See `legacy/README.md`.

A patch file is visible in the diff, reviewable in a pull request, survives a
dependency update as a merge conflict rather than a silent loss, and documents
its own reason for existing.

## Naming

    NN-<repo>-<short-description>.patch

`NN` orders application. Example: `01-xarm_ros2-jazzy-cmake-fix.patch`.

## Every patch must carry a header

```
# Repo:     external/xarm_ros2
# Upstream: https://github.com/xArm-Developer/xarm_ros2/issues/NNN
# Reason:   One sentence on what breaks without this.
# Removal:  The condition under which this patch can be deleted.
```

A patch with no removal condition is a permanent fork. If that is genuinely the
intent, say so in the header and write an ADR — do not leave it implied.

## Generating one

```bash
cd workspace/src/external/<repo>
git diff > ../../../../external/patches/NN-<repo>-<description>.patch
```
