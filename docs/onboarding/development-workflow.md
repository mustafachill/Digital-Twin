# Development workflow

How work moves from an idea to a merged change.

- **Related:** [`../../CLAUDE.md`](../../CLAUDE.md) §11, [`../architecture/cross-cutting-testing.md`](../architecture/cross-cutting-testing.md)

## Before you write anything

1. **Read the architecture document for the layer you are touching.** It states what that
   layer owns and — more usefully — what it does not.
2. **Read the ADRs it references.** Most "why is it done this weird way" questions are
   answered there, and asking a person instead is how the answer gets lost.
3. **Check whether your change needs its own ADR.** Choosing a technology, moving an
   architectural boundary, or establishing a convention others must follow: yes. Write it
   **before** implementing (charter §10.3) — an ADR written afterwards is a justification,
   and justifications are written to defend rather than to weigh.

## The loop

```
branch → implement → quality gate → review → fix → re-verify → merge
```

### Branch

```bash
git checkout -b feat/<slug>
```

Never work on `main`.

### Implement

Match the surrounding code — its naming, its layering, its idioms. Reuse what exists rather
than adding a parallel way to do the same thing.

Watch for the standing prohibitions (`CLAUDE.md` §4). They are rejected in review without
discussion, so hitting one is wasted work:

- Hand-editing a generated artifact
- Structured data in a `std_msgs/String`
- `TimerAction` or `sleep` to sequence startup
- Copying third-party source into the tree
- Marking something complete without a test
- Anything not in English
- A value that now exists in two places

### Quality gate

```bash
./scripts/lint && ./scripts/build && ./scripts/test
```

Green before you hand off. Handing off a red branch spends someone else's time discovering
what you already could have.

### Review

Human review, plus the agent pipeline. `CLAUDE.md` §11 states the rules that bind every
contributor here, with or without the agents; the pipeline's dispatch routing lives with
the agent configuration, which is local tooling and is not committed, so a fresh clone
will not contain it. Which agents run depends on what the diff touches:

| Your diff touches | Also runs |
|---|---|
| always | `reviewer` |
| `model/`, descriptions, generated artifacts | `model-validator` |
| anything that can produce motion | `safety-auditor` |
| a new package or a layer boundary | `architect-reviewer` |
| the dependency manifest | `dependency-auditor` |
| a control loop or hot path | `performance-engineer` |

**Scale the ceremony to the risk.** A typo needs no agents. Anything that can move a
physical arm gets the full pipeline with `safety-auditor` mandatory and human sign-off.

### Fix and re-verify

Findings are addressed in severity order, each with a regression test that locks the fix
in. **Re-verification is not optional** — `reviewer` and `tester` run again on the fix
commit.

Disagreeing with a finding is fine. Say so explicitly, with reasoning, as `won't-fix`.
Silently skipping one is not.

### Merge

No open Critical or High. CI green. Documentation updated in the same change — not "in a
follow-up", which is where documentation goes to die.

## Definition of Done

From charter §9. All of it, no partial credit:

1. Generated from or declared in the L0 model, where applicable.
2. Interfaces typed and in an interface package.
3. Tested at the right level, passing in CI.
4. Runs headlessly in CI on a clean container, no manual step.
5. Works identically in simulation and on hardware — or its hardware path is explicitly
   marked unimplemented.
6. Documented: what it does, its interfaces, how to run it, how it fails.
7. Reviewed by a human and by the relevant agents.
8. Startup and shutdown event-driven, no timing guesses.

## Writing an ADR

Copy [`../adr/0000-template.md`](../adr/0000-template.md), take the next number, keep it to
a page.

The section people skip is **what this costs us**. An ADR with no costs listed has not been
thought through — every decision costs something, and the record exists so the next
person knows what was paid. Numbers are permanent; a superseded ADR is never rewritten.

## Escalation

Some things are not yours to decide. An `ESCALATE` goes to the project owner:

- A conflict with a locked decision in `CLAUDE.md` §3 or §4.
- A change that would break sim/hardware parity (P2).
- A change to `what-we-are-doing.md`, which is protected.
- Anything that could move a physical arm in a way nobody intended.

Do not work around an escalation. That is how a considered decision becomes an accident.
