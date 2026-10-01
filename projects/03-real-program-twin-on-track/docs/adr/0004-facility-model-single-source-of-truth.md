# ADR-0004: Generate all artifacts from one facility model

- **Status:** Accepted — **amended 2026-08-29, and the amendment widens what L0 describes
  without moving anything out of it.** The decision below stands word for word: every derived
  artifact is generated, a hand edit is a Critical review finding, and generation is
  deterministic. What changed is the *scope* clause — "every physical and topological fact" —
  which was not wide enough for the first L0 field that is neither. See the section named
  "Amendment — 2026-08-29: L0 describes the modelled system, not only the building" below.
- **Date:** 2026-08-24
- **Related:** ADR-0013,
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)
  (added by the 2026-08-29 amendment), charter §4 (P1, P5),
  `docs/architecture/L0-facility-model.md`

## Amendment — 2026-08-29: L0 describes the modelled system, not only the building

**This is an amendment, not a correction.** Nothing below was measured false and nothing is
withdrawn. The Decision names L0 "the single source of truth for every **physical and
topological** fact about the system". That description fitted every field the model had, and
[ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)'s Decision 3 adds one it
does not fit.

`twin: {sides: single | pair}` says whether a zone is modelled as one cell or as a twinned
pair. **The building has one `arm_1`.** Pairing is a fact about the *modelled deployment* —
how many copies of the cell this system runs — and on the wording above it does not belong
in L0 at all.

**It is placed in L0 anyway, and the reason is this record's own machinery.** The field
changes what is generated: the number of Gazebo transport partitions, and in time a second
side's controller managers, world and node names. Under the Decision below, *everything
generated comes from L0*. So a value that decides generated output either lives here or it
lives in a launch argument or an environment variable — and `cross-cutting-safety.md` bars
both for a value of this class, on the grounds that a mode must never be reachable by
omission. Putting it outside L0 would have meant one of the two failure modes this record
exists to prevent: a generated artifact whose shape is decided somewhere the model cannot
see.

**So the scope clause is widened, and the widening is deliberately narrow.** Read the
Decision's "every physical and topological fact" as **every fact the generated artifacts are
derived from — the modelled system, not only the building.** The test for what qualifies is
[ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)'s and is reused rather
than restated: *if changing it requires a regeneration to take effect, it **describes** the
system; if a service call flips it, it **runs** the system.* `twin.sides` is the first;
`TwinMode`, gated through `SetMode.srv`, is the second and regenerates nothing.

**What this does not license.** It is not permission to put runtime configuration in L0. A
field that only some process reads at run time, and that no generator consumes, still does
not belong here — and the reopening trigger is named in ADR-0041: a launch argument or an
environment variable that turns pairing on *without* regenerating would put the same fact in
two places, and must be argued rather than added.

**How the wording came to be too narrow.** It was written when every fact in the model was a
coordinate, a mass, or an edge in the process flow, and it described that set exactly. The
clause therefore looked like a definition of L0's scope when it was really a description of
L0's contents at the time. A scope stated by enumerating what happens to be in it holds
until the first thing that is not.

## Context

In the v1 workspace the same physical facts were written down in several places and had
diverged without anyone noticing:

| Fact | `fleet_config.yaml` | `assembly_line.world` |
|---|---|---|
| Conveyor positions | −2.0 / 0.0 / 2.0 | −1.5 / 0.0 / 1.5 |
| Pick area | −3.0 | −2.8 |

Pick and place positions existed in two configuration files with different values, and the
code read one of them. The world file was hand-authored, so changing the configuration
changed nothing in simulation — the system was described as "config-driven" and was not.

This class of defect is silent. Nothing crashes; the simulation simply models a facility
that does not exist, and every measurement taken from it is quietly wrong.

## Options considered

### Option A — Discipline and review
Keep hand-authored artifacts, require reviewers to check consistency. Rejected: this is
exactly what v1 relied on, and it failed. Consistency across five files is not something
human review reliably catches, and the failure is invisible.

### Option B — Cross-validation
Keep the artifacts separate but add a checker that compares them. Rejected: it detects
divergence after it happens rather than making it impossible, and the checker becomes a
third place the facts are encoded.

### Option C — Single declarative model with generation
Describe the facility exactly once in a schema-validated model. Generate world files,
robot descriptions, controller configurations, launch graphs, and orchestration topology
from it. Chosen.

## Decision

The **L0 facility model** is the single source of truth for every physical and topological
fact about the system. **[Amended 2026-08-29 — read "physical and topological fact" as "fact
the generated artifacts are derived from": the modelled system, not only the building. See
the Amendment section above.]** All derived artifacts are **generated**. Hand-editing a generated
artifact is a Critical review finding (`CLAUDE.md` §4), enforced by the `model-validator`
agent comparing against a fresh generator run.

Generation must be **deterministic**: the same model input produces byte-identical output.
Non-determinism here makes the hand-edit check unusable and breaks reproducibility.

## Consequences

### What this gets us
- A fact exists once. Divergence is not caught — it is impossible.
- Changing the cell layout is a model edit. Reconfiguring the line does not touch code
  (P5), which is what makes the plug-in/plug-out requirement (P9) achievable.
- The model is machine-readable, so it can drive things beyond simulation: the dashboard
  topology, documentation, and the twin's own registration data.

### What this costs us
- A generator and a schema must be built and maintained before anything can be simulated.
  This is real up-front work with nothing visible to show for it, and it lands in
  Phase 1.B.
- Debugging gains a layer: a wrong value in a world file now means a wrong model *or* a
  wrong generator, and the reader must know which to look at.
- Anything the model cannot express cannot be simulated until the schema is extended. This
  friction is intentional — it forces additions to be considered — but it is friction.
- Generated artifacts should not be read as authored files. Reviewers must read the model
  and the generator instead, which is a habit that has to be taught.

### What we will have to revisit
If a legitimate need arises for an artifact the model genuinely cannot express, extend the
schema. Do not carve out an exception — one hand-authored artifact reintroduces the entire
failure mode.
