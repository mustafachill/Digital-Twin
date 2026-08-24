# ADR-0008: Consume external sources via a pinned manifest

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0001, ADR-0009, `external/cite.repos`, `external/patches/README.md`

## Context

The v1 workspace made this repository unbuildable from a clean checkout, in two ways at
once:

1. **`xarm_ros2` was copied into the tree** — 805 files committed directly. Disconnected
   from upstream, impossible to update, and impossible to tell which parts had been
   modified.
2. **`gazebo_ros2_control` was a submodule gitlink with no `.gitmodules` entry.** A fresh
   clone produced an empty directory. The package had been patched locally — the fix that
   allowed controllers to load at all — and **that patch existed nowhere in version
   control.** One machine held the only copy.

Nobody noticed, because the machine where the project was developed always worked. The
failure was invisible until someone else tried to clone, which nobody did.

## Options considered

### Option A — Vendor everything into the tree
Guarantees the source is present, and the clone is self-contained. Rejected: no upstream
relationship, no way to review local changes, no way to update, and an enormous repository.
This is what v1 did.

### Option B — Git submodules
Native, and the standard answer. Rejected: submodules are exactly what failed here.
Getting them wrong is easy and silent, `--recursive` is easy to forget, and patched
submodules have no reviewable representation.

### Option C — `vcstool` manifest with pinned revisions and patch files
A YAML manifest declares each external repository and the exact commit to check out.
Bootstrap imports them into a gitignored directory. Local modifications live as patch
files applied after import. Chosen.

## Decision

External sources are declared in **`external/cite.repos`**, pinned to **exact commit
SHAs**, and imported by `./scripts/bootstrap` into `workspace/src/external/`, which is
gitignored. Local modifications live in `external/patches/` as patch files with a required
header stating the target repository, the upstream issue, the reason, and the condition
under which the patch can be removed.

Three things are enforced automatically in CI and by `dependency-auditor`:

- Third-party source tracked in git is a **Critical** finding.
- A gitlink without a `.gitmodules` entry is a **build failure**.
- A manifest entry pinned to a branch rather than a SHA is a **warning**, and blocks any
  claim of reproducibility.

## Consequences

### What this gets us
- A fresh clone plus `./scripts/bootstrap` reproduces the exact source tree, on any
  machine, on any day.
- Local patches are visible in a diff, reviewable in a pull request, and survive a
  dependency update as a merge conflict rather than a silent loss.
- A small repository with a clean upstream relationship.

### What this costs us
- Bootstrap requires network access. Offline or air-gapped work needs a pre-populated
  cache or a mirror.
- Updating a dependency is a deliberate act: change the SHA, re-check the patches, verify
  the build. This is slower than a branch reference — deliberately.
- Patch files rot. When upstream moves, a patch stops applying and someone must
  understand it well enough to rebase it. The required header exists so that person has
  something to work from.
- A patch with no removal condition is a permanent fork wearing a disguise. Reviewers must
  push back on those.

### What we will have to revisit
If patches against one dependency accumulate to the point of being a fork, make it a fork:
an explicit, versioned fork with its own upstream relationship is more honest than fifteen
patch files.
