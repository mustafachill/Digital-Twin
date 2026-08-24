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
3. `legacy/` holds a superseded first iteration. It is reference material, not a codebase
   to extend, and it is deleted at the end of Phase 1. See `CLAUDE.md` §2.
4. Everything in this repository is written in English.

## Related

| File | Purpose |
|---|---|
| `CLAUDE.md` | Canonical rulebook — rules, architecture, commands, quality gates |
| `what-we-are-doing.md` | Project charter — identity, scope, roadmap, rationale |
| `.claude/orchestration.md` | Agent pipeline and dispatch routing |
| `.claude/agents/` | Active subagent role definitions |
