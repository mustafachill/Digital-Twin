# Documentation

Everything written down about the CITE Digital Twin, and where to find it.

## The three anchors

| Document | Answers | Changes |
|---|---|---|
| [`../what-we-are-doing.md`](../what-we-are-doing.md) | **What** we are building and **why** | Only by explicit decision of the project owner |
| [`../CLAUDE.md`](../CLAUDE.md) | **How** to work here — rules, commands, quality gates | When a working rule changes |
| `docs/` | **How it works** in detail, and **why each choice was made** | Continuously, alongside the code |

If any two disagree, the charter wins, then `CLAUDE.md`, then these documents. A
disagreement is a defect in the loser — fix it, do not leave both standing.

## Where to look

| Question | Go to |
|---|---|
| How do I get a working environment? | [`onboarding/getting-started.md`](onboarding/getting-started.md) |
| How do we work day to day? | [`onboarding/development-workflow.md`](onboarding/development-workflow.md) |
| What does this word mean here? | [`onboarding/glossary.md`](onboarding/glossary.md) |
| Why was *X* chosen over *Y*? | [`adr/`](adr/README.md) |
| How does layer *N* work? | [`architecture/`](architecture/README.md) |
| How does this relate to ISO 23247? | [`architecture/standards-alignment.md`](architecture/standards-alignment.md) |
| What shape is this interface? | [`interfaces/`](interfaces/README.md) |
| How do I bring up / calibrate / recover the cell? | [`operations/`](operations/README.md) |
| What number backs that claim? | [`measurements/`](measurements/README.md) |
| Where do I read more? | [`reference/`](reference/README.md) |

## Reading order for a new contributor

1. [`../what-we-are-doing.md`](../what-we-are-doing.md) — the whole project in one sitting.
2. [`../CLAUDE.md`](../CLAUDE.md) — the rules you will be held to.
3. [`onboarding/getting-started.md`](onboarding/getting-started.md) — get it running.
4. [`architecture/README.md`](architecture/README.md) — the layer stack.
5. The architecture document for the layer you are about to touch.
6. The ADRs referenced by that document.

Roughly two hours. Do not skip step 6: most "why is it done this weird way" questions are
answered by an ADR, and asking a person instead is how the answer gets lost.

## Status markers

Every architecture and interface document begins with a status. The project documents its
design *before* building it, so a reader must never have to guess whether a document
describes reality or intent. This is principle P7 made mechanical.

| Marker | Meaning |
|---|---|
| `DESIGNED` | Specified here, not built yet. **This document is the contract the code must satisfy.** |
| `PARTIAL` | Some of it exists. The document says exactly which parts. |
| `BUILT` | Implemented, and covered by tests that run in CI. |

A document marked `BUILT` that describes something which does not exist is a defect of the
same severity as a broken test. Reviewers check this.

## Writing here

- **English only**, without exception (P10).
- **Ground every claim in code**, a test, a published measurement, or a cited source. Mark
  anything else `unverified` rather than stating it plainly.
- **A claim about physical behaviour needs a measurement, not an argument.** Five ADRs
  carry a correction section at this commit — a sixth, since superseded, carries one too —
  because a plausible sentence about physics was written down as a fact and relied upon.
  Cite [`measurements/`](measurements/README.md) or say that nothing has been run.
- **Carry a quantity's units *and its axis* wherever you carry its magnitude.** A published
  18.7° residual travelled through this repository detached from the axis it was measured
  about, was read as a yaw when it is a roll, and reached an ADR's arithmetic where only a
  yaw belongs. A scalar moves between documents far more easily than the condition that
  gives it meaning — see the table in [`measurements/`](measurements/README.md).
- **Prefer deleting a stale sentence to hedging it.** Stale documentation is more
  dangerous than missing documentation, because it is trusted.
- **Never duplicate.** Link instead. A value that exists in two places will diverge (P1),
  and that applies to prose as much as to configuration.
- **`what-we-are-doing.md` is protected.** Do not edit it as a side effect of other work.

Internal links are checked by `./scripts/lint`. A renamed file surfaces as a lint failure
rather than a dead link somebody finds months later.
