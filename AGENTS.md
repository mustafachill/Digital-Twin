# AGENTS.md

**The canonical agent instructions for this repository are in [`CLAUDE.md`](./CLAUDE.md).
Read that file before doing any work here.**

This file exists so that agent tooling following the vendor-neutral `AGENTS.md`
convention finds a defined entry point. It deliberately contains a reference rather than
a copy: this project's first engineering principle is that no value exists in two places
(`CLAUDE.md` §3, P1), and an `AGENTS.md` that duplicated the rulebook would drift from it
within weeks — violating the very rule it was restating.

If your tooling cannot follow a file reference, load `CLAUDE.md` explicitly.

## Minimum you must know before editing anything

1. `CLAUDE.md` is the rulebook. `what-we-are-doing.md` is the project charter and explains
   why every rule exists.
2. `what-we-are-doing.md` is **protected** — it changes only by explicit decision of the
   project owner, never as a side effect of other work.
3. This repository is a **rebuild**. The superseded first iteration lived under `legacy/`
   and was deleted at the end of Phase 1; it remains in version control. What it taught is
   in `docs/reference/v1-lessons.md`. Do not reintroduce it or treat its patterns as
   precedent.
4. Everything in this repository is written in English.

## Related

| File | Purpose |
|---|---|
| `CLAUDE.md` | Canonical rulebook — rules, architecture, commands, quality gates |
| `what-we-are-doing.md` | Project charter — identity, scope, roadmap, rationale |
| `.claude/orchestration.md` | Agent pipeline and dispatch routing — *local, not committed* |
| `.claude/agents/` | Active subagent role definitions — *local, not committed* |
