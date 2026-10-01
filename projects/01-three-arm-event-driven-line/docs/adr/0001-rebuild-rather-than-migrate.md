# ADR-0001: Rebuild rather than migrate the v1 workspace

- **Status:** Accepted
- **Date:** 2026-08-24
- **Note:** 2026-08-27 — carried out; read the note section below before the body.
- **Related:** charter §12, [`../reference/v1-lessons.md`](../reference/v1-lessons.md)

## Note — 2026-08-27: the deletion this record scheduled has happened

This is **not** a correction under [the convention](README.md#corrections). Nothing here
was measured false; the decision was carried out, and two consequences written in the
present tense are now discharged. The decided text below is left exactly as it stands.

`legacy/` was deleted in commit `f16ea98`, removing 952 files. The tree remains in version
control and is recoverable — `git show f16ea98^:legacy/<path>` — but no checkout contains
it. Consequently:

- The consequence *"Working xArm integration knowledge lives in `legacy/` and must be
  deliberately re-derived rather than copied"* was paid rather than avoided. What was
  carried forward is [`../reference/v1-lessons.md`](../reference/v1-lessons.md), written
  from the tree at commit `d68838b` before the deletion; the vendor stack itself is pinned
  by commit SHA in `external/cite.repos` and was never at risk.
- The consequence *"A period where `legacy/` and the new tree coexist and could confuse a
  newcomer"* has ended. Its stated mitigation, `legacy/README.md`, is gone with the tree;
  `CLAUDE.md` §1 now carries the standing part — that v1's patterns are not precedent.
- The `Related:` line above was repointed for the same reason: it named
  `legacy/README.md` until this date.

The charter records the deletion in §7 and §14 (v1.6).

## Context

The project spent an extended R&D period producing a ROS 2 Humble / Gazebo Classic
workspace. A review of that tree found, in summary:

- No hardware interface anywhere in the codebase, despite the project's name. It was a
  simulation at maturity level L0.
- A critical dependency patched locally and committed as a submodule gitlink with no
  `.gitmodules` entry. A fresh clone produced an empty directory, and the patch — the fix
  that allowed controllers to load at all — existed only on one machine.
- Robot motion simulated by timers rather than executed; the handoff protocol published to
  topics that had no subscriber.
- Three mutually incompatible architectures coexisting, with contradictory naming and
  eight launch files of unclear provenance.
- Values duplicated across configuration and world files, and diverged.
- No tests, no CI, no reproducible environment.
- Documented status that did not match reality.

Separately, the platform decision had already moved to Gazebo Harmonic (ADR-0003), which
invalidates the world files, the conveyor plugin, and every simulation launch path in that
tree regardless of its quality.

## Options considered

### Option A — Incremental migration
Move package by package to Jazzy and Harmonic, keeping the system working at each step.
Attractive because it never has a period of "nothing runs". Rejected: the majority of the
tree is coupled to Gazebo Classic and would be rewritten rather than ported, and the
architectural problems above are not refactorings — three competing architectures cannot
be incrementally reconciled into one that never existed. The migration would carry forward
naming, layering, and configuration decisions that the review identified as the causes of
failure.

### Option B — Rebuild in a new repository
Start clean elsewhere and archive this one. Rejected: it discards the git history and
splits the project's identity across two repositories for no benefit that Option C does
not also provide.

### Option C — Rebuild in place, archive the old tree
Move the v1 workspace to `legacy/`, build the new architecture alongside it, delete
`legacy/` at the end of Phase 1. Chosen.

## Decision

Rebuild the workspace from zero on the architecture described in charter §5, in this
repository. The v1 tree moves to `legacy/`, is excluded from the build by living outside
`workspace/`, and is deleted at the end of Phase 1. **We carry forward knowledge, not
code.**

## Consequences

### What this gets us
- Every principle in charter §4 is enforceable from the first commit rather than
  retrofitted onto code that violates it.
- No inherited naming or layering decisions to work around.
- Reproducibility from day one — the dependency failure above cannot recur under ADR-0008.

### What this costs us
- Several weeks before the system does anything visible again. Phase 1's exit criterion is
  a three-robot line that v1 already partly demonstrated. This is real lost ground and
  should be stated plainly to stakeholders rather than glossed.
- Working xArm integration knowledge lives in `legacy/` and must be deliberately
  re-derived rather than copied. That is the point, but it is not free.
- A period where `legacy/` and the new tree coexist and could confuse a newcomer. Mitigated
  by `legacy/README.md`, `CLAUDE.md` §2, and build exclusion.

### What we will have to revisit
Nothing. Reversing this would mean rebuilding on Gazebo Classic, which is end-of-life.
