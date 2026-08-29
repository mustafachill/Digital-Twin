# ADR-0011: Adopt the twin maturity model and operating modes

- **Status:** Accepted — **amended 2026-08-29, and the amendment adds a mode without
  touching a level.** The five maturity levels below, their mapping to the literature and
  the commitment that follows them are unchanged and still bind. What changed is the mode
  set: [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) adds a sixth
  operating mode, and the sentence naming five modes is qualified in place. See the section
  named "Amendment — 2026-08-29: a sixth operating mode, and no sixth level" below.
- **Date:** 2026-08-24
- **Related:** ADR-0005, ADR-0016,
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)
  (added by the 2026-08-29 amendment), charter §2,
  `docs/architecture/L5-twin-synchronization.md`

## Amendment — 2026-08-29: a sixth operating mode, and no sixth level

**This is an amendment, not a correction.** Nothing in this record was measured false and
nothing in it is withdrawn. The Decision below defines five maturity levels and then states
that L5 exposes them as five operating modes. The first half stands. The second half was
not wide enough, and Phase 2.A is what found the gap.

The operating mode a Phase 2.A pair needs is: **an operator commands the virtual side, the
far side follows and actuates, and nothing mirrors back.** None of the five expresses it.
`SIM` and `REAL` each idle one side. `SHADOW` and `VALIDATED` are defined by a flow *from*
the physical side. `CLOSED_LOOP` has the direction but is defined by the validation gate in
front of it, which this flow does not have. So `TwinMode` gains
**`MODE_VIRTUAL_LEAD = 5`**, decided by the project owner and specified in
[ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 2, which
carries the reasoning, the gating and the rejected alternative. It is **cited and not
restated** (P1).

**No level is added, moved, or claimed.** The mode carries L3's *direction* without L3's
*validation gate*: a claim about this system still has to name a level, and the existence of
a mode is not a level. In Phase 2.A there is no physical side at all, so the level is L0
whichever mode is in force.

**That argument does not close on the table below, and saying so is the point of this
paragraph.** The L3 row gives the data flow — `virtual → real` — and nothing else. **The
validation gate is not in it.** Read on this record alone, `MODE_VIRTUAL_LEAD` against a real
far side *is* an L3 flow, and the amendment would be claiming a level while denying it. What
carries the gate is charter §2, whose L3 row reads *"Behaviour is validated in simulation and
then commands the physical system"*, and
`docs/architecture/L5-twin-synchronization.md`'s mode table, whose `CLOSED_LOOP` row is
*"commanded after virtual validation gates it"* against level L3. **This amendment rests on
those two documents and not on the table below**, and the charter change that names the mode
must land with it rather than after it, or the level distinction it depends on is not written
down anywhere binding. If either document is ever read as putting the direction alone at L3,
this amendment fails and the mode has to be re-argued.

**How this needed amending at all.** This record derived a mode set from a maturity ladder,
and the two are not the same axis: a level is defined by where information *flows from*, and
a mode is defined by where commands *enter and land*. Four of the five modes happened to
coincide with a level, which made the two look like one axis until Phase 2.A asked for a
flow no level names. A mode set derived from a level set is complete only by accident.

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
`CLOSED_LOOP`. **[Amended 2026-08-29 — a sixth mode, `VIRTUAL_LEAD`, was added; see the
Amendment section above.]** Mode is explicit, observable at runtime, and gated — never a
default that can be reached by accident.

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
