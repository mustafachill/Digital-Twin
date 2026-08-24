# ADR-0014: Use a monorepo

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0004, ADR-0008, charter §7

## Context

The project spans more than a ROS workspace: a declarative facility model, generators, 3D
assets and their pipeline, container and CI infrastructure, documentation, and eventually
a web interface. These are coupled in a specific way — the L0 model generates the ROS
artifacts (ADR-0004), so a model change and the regenerated output must be reviewable as
one change.

## Options considered

### Option A — Repository per component
Independent versioning and access control per component. Rejected: a change to the model
schema, the generator, and the packages that consume the generated output would span three
repositories and three pull requests, with no atomic review and no way to bisect. The
coupling ADR-0004 creates is exactly the coupling that makes multi-repo painful.

### Option B — ROS workspace separate from everything else
Rejected for the same reason at smaller scale, and it leaves the question of where the
generators live unanswerable.

### Option C — Monorepo
One repository containing the workspace, model, assets, tooling, infrastructure, and
documentation. External dependencies stay outside, pinned by manifest (ADR-0008). Chosen.

## Decision

**One repository.** Layout as in charter §7. Third-party source is never part of it
(ADR-0008); large binaries are never part of it (ADR-0012).

## Consequences

### What this gets us
- Atomic changes. A model change, its regenerated artifacts, the code that consumes them,
  the tests, and the documentation land in one reviewable commit.
- One CI pipeline with a complete view. The supply-chain checks in `.github/workflows/ci.yml`
  can see the whole tree, which is how the vendored-source and orphaned-gitlink checks work
  at all.
- One place to look. A newcomer clones once.
- Documentation versions with the code it documents, which is what makes P7 enforceable.

### What this costs us
- The repository grows, and history accumulates across concerns. Mitigated by keeping
  dependencies and large binaries out, but a five-year-old monorepo is still large.
- Access control is all-or-nothing. Anyone who can contribute to the HMI can also commit
  to the safety layer. For a small team under one centre this is acceptable; it would not
  be for external collaborators, and that is the condition to watch.
- CI must be selective as the tree grows, or every change pays for every job. The current
  split — a fast host-tooling stage before the expensive container stage — is the first
  step; path filters will be needed later.
- Contributors interested in one area still clone everything.

### What we will have to revisit
If external collaborators need scoped access, or if CI times become dominated by
irrelevant jobs. The first response is path-filtered CI, not splitting the repository —
splitting sacrifices the atomicity that motivated this decision.
