# ADR-0004: Generate all artifacts from one facility model

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0013, charter §4 (P1, P5), `docs/architecture/L0-facility-model.md`

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
fact about the system. All derived artifacts are **generated**. Hand-editing a generated
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
