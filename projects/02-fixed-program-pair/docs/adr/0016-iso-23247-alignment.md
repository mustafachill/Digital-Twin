# ADR-0016: Align the architecture with ISO 23247

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0011, `docs/architecture/standards-alignment.md`, `docs/reference/standards.md`

## Context

The L0–L7 layer stack was derived from this project's own requirements: one source of
truth, an interchangeable simulation/hardware boundary, pluggable components, and a
measurable twin. It is defensible on its own terms.

But "we designed it this way because it seemed right" is a weak answer from an institutional
research centre, particularly to a reviewer, a funder, or an industrial partner. It is also
a weak answer to the next architect, who has no way to distinguish a considered structure
from an arbitrary one.

**ISO 23247** — *Automation systems and integration — Digital twin framework for
manufacturing* — is the relevant international standard. Parts 1–4 were published in 2021
and the series was extended in 2026:

| Part | Covers |
|---|---|
| 23247-1:2021 | Overview and general principles; defines Observable Manufacturing Elements |
| 23247-2:2021 | Reference architecture: domain-based and entity-based models, functional views |
| 23247-3:2021 | Basic information attributes for observable manufacturing elements |
| 23247-4:2021 | Technical requirements for information exchange between entities |
| 23247-5:2026 | Digital thread for digital twin |
| 23247-6:2026 | Digital twin composition |

Its reference architecture divides a manufacturing digital twin into four domains:
Observable Manufacturing Element, Data Collection and Device Control, Core (Digital Twin),
and User. Published implementations of it are conveyor-based laboratory production lines
with assembly stations — the same class of system this project is building.

## Options considered

### Option A — No standards alignment
Keep the layer stack purely as our own design. Rejected: it forgoes credibility that costs
almost nothing to acquire, and forgoes the chance to have our structure checked against
one that many people have already stress-tested.

### Option B — Mention the standard in the references
Cheap, and honest as far as it goes. Rejected: a reference nobody has mapped is decoration.
It would let us name-drop the standard without ever testing whether our architecture
actually satisfies its concerns.

### Option C — Full mapping, documented
Map every layer to its ISO 23247 domain and functional entity, publish the mapping, and
treat any layer that maps to nothing — or any domain concern with no layer — as a finding
worth investigating. Chosen.

### Option D — ISO 23247 plus Asset Administration Shell
Also adopt the AAS asset information model (IEC 63278). Rejected **for now**: AAS earns its
keep at the integration boundary with external Industry 4.0 systems, which is Phase 4 work
at the earliest. Adopting its modelling obligations before there is anything to integrate
with is cost without benefit. Recorded here so the option is not forgotten.

## Decision

Align the architecture with the **ISO 23247 reference architecture**, and document the
mapping in `docs/architecture/standards-alignment.md`.

Alignment means: our layers are mapped to its domains and functional entities, and we use
its vocabulary where ours would otherwise diverge for no reason. It does **not** mean
formal conformance assessment or certification, and no document in this repository may
claim that we are ISO 23247 certified.

## Consequences

### What this gets us
- The architecture is defensible to a reviewer, a partner, or a funder on grounds stronger
  than internal preference.
- Shared vocabulary with the manufacturing digital-twin literature, which makes the
  project's work legible to that audience and its work legible to us.
- A structural cross-check: a domain concern with no home in our stack is a gap worth
  knowing about. Mapping is a design review, not just a labelling exercise.
- A clear path to interoperability if CITE later integrates with partner systems.

### What this costs us
- A mapping document that must be maintained. If the architecture moves and the mapping
  does not, the mapping becomes a lie — the same failure mode as any stale documentation.
- Two vocabularies in play. `standards-alignment.md` and `glossary.md` exist so that
  translation happens in one place instead of in every reader's head.
- A temptation to overclaim. "Aligned with ISO 23247" is true; "ISO 23247 compliant" is
  not, and the difference matters. The distinction is stated in the mapping document and
  reviewers should enforce it.
- The standard is not free to read. Contributors will mostly work from the mapping and the
  secondary sources in `docs/reference/standards.md`.

### What we will have to revisit
When Phase 4 brings external integration, reconsider Option D — the Asset Administration
Shell becomes genuinely useful at that boundary. Revisit the mapping itself whenever a
layer's responsibility changes.
