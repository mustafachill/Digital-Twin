# ADR-0015: Write everything in English

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** charter §4 (P10)

## Context

The v1 workspace mixed Turkish and English across 23 files — launch files, configuration
comments, world files, and most documentation. This happened despite the project's own
`GOALS.md` explicitly requiring English-only, which is itself informative: a rule nobody
enforces is not a rule.

The project belongs to a centre at an American university. Its contributors, reviewers,
and any eventual publication audience read English. Some of the team are more comfortable
in Turkish.

## Options considered

### Option A — Bilingual documentation
Maintain critical documents in both languages. Rejected: two versions of a document
diverge, and the divergence is invisible to anyone who reads only one. It is P1 violated
in prose.

### Option B — English code, Turkish documentation
Rejected: it excludes exactly the readers — reviewers, external collaborators, future
contributors — for whom the documentation exists.

### Option C — English everywhere
Chosen.

## Decision

**All code, comments, identifiers, configuration, commit messages, documentation, and
agent reports are written in English.** No exceptions.

This includes AI agent output: the report templates in `.claude/agents/` produce English,
because those reports are pasted into pull requests and read by the team.

Conversation between team members in any language is unaffected. This governs artifacts,
not people.

## Consequences

### What this gets us
- Every artifact is readable by every contributor, reviewer, and stakeholder.
- No divergence between language versions, because there is one version.
- The project is publishable and shareable without a translation pass.
- Machine-checkable: a lint rule can catch violations, which is what makes this a rule
  rather than an aspiration.

### What this costs us
- Contributors write and review in a second language, which is slower and occasionally
  less precise. This is a real cost borne unevenly across the team.
- Explaining a subtle design point is harder in a second language, and there is a
  temptation to write less rather than write it imperfectly. **Write it imperfectly.** An
  awkward English explanation is worth more than an absent one.

### What we will have to revisit
Nothing. The v1 experience shows the alternative is not "bilingual" but "inconsistent".
