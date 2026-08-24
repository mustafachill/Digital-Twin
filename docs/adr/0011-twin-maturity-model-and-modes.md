# ADR-0011: Adopt the twin maturity model and operating modes

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0005, ADR-0016, charter §2, `docs/architecture/L5-twin-synchronization.md`

## Context

"Digital twin" is used loosely enough to be nearly meaningless in marketing material. The
v1 project called itself a digital twin while containing no hardware interface whatsoever
— it was a simulation, and the name obscured that from everyone including its authors.

A staged, published definition is needed for two reasons: so the project can state
honestly what it has achieved, and so that the L5 architecture is designed against a
target rather than accumulating modes ad hoc.

The literature offers a foundation. Kritzinger et al. (2018) classify by the degree of
information-flow automation: **digital model** (no automated exchange), **digital shadow**
(automated physical → virtual), **digital twin** (automated bidirectional). A separate,
widely used functional classification runs descriptive → diagnostic → predictive →
prescriptive.

An earlier draft of the charter used "Mirror" for automated physical → virtual and
"Shadow" for the divergence-measuring stage. That collides directly with the literature's
"digital shadow", which means the first stage, not the second. In a university centre that
may publish, a private vocabulary that redefines a standard term is a liability.

## Options considered

### Option A — Adopt Kritzinger's three levels verbatim
Maximum alignment. Rejected: three levels are too coarse to plan five phases against, and
the classification says nothing about whether a shadow's accuracy is measured — which is
the distinction this project most needs to make.

### Option B — Keep the private vocabulary, document the mapping
Rejected: it forces every external reader to translate, and the collision on "shadow"
guarantees at least one misreading.

### Option C — Five levels, named to align with the literature
Chosen. Adopt the literature's terms where they apply, and add refinement only where the
project genuinely needs a distinction the literature does not draw.

## Decision

Five levels, and every claim about the system must name one:

| Level | Name | Data flow | Literature |
|---|---|---|---|
| L0 | Virtual model | none | Kritzinger *digital model* |
| L1 | Shadow | real → virtual | Kritzinger *digital shadow* |
| L2 | Validated | real → virtual, commands → both, divergence measured | our refinement |
| L3 | Closed loop | virtual → real | Kritzinger *digital twin* |
| L4 | Predictive | virtual ahead of real | functional *predictive/prescriptive* |

L5 exposes these as runtime **operating modes**: `SIM`, `REAL`, `SHADOW`, `VALIDATED`,
`CLOSED_LOOP`. Mode is explicit, observable at runtime, and gated — never a default that
can be reached by accident.

**Commitment: reach L2 with rigor, then L3, and architect so that L4 needs no
re-foundation.** L2 is the level that matters most. A shadow whose error nobody measures
is an assertion; L2 is where the twin starts proving itself, and it is why P8 requires
every fidelity claim to carry a published metric.

## Consequences

### What this gets us
- Honest, checkable claims. "We are at L2, here is the measured divergence" is defensible
  in a way that "we have a digital twin" is not.
- L5 has a designed mode set rather than an accumulated one.
- External readers and reviewers need no translation table.

### What this costs us
- L2 obliges us to build divergence measurement, calibration, and registration before
  claiming success — real work that a project willing to say "digital twin" loosely would
  skip.
- The charter had to be amended (v1.2) and the earlier vocabulary retired. Anyone who read
  the v1.1 charter learned names that no longer exist.
- Five levels is more than three, and the L1/L2 distinction has to be explained each time.

### What we will have to revisit
If L4 work begins in earnest, the functional classification (descriptive → prescriptive)
may become the more useful axis, and L4 may need subdivision.
