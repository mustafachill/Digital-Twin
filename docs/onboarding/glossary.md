# Glossary

The single definition site for this project's vocabulary. When a term here conflicts with
its use elsewhere in the repository, this file wins and the other use is a defect.

## Twin maturity

| Term | Means here |
|---|---|
| **L0 — Virtual model** | A simulation with no automated link to physical reality. Kritzinger's *digital model*. |
| **L1 — Shadow** | Physical state automatically drives the virtual model. One direction. Kritzinger's *digital shadow*. |
| **L2 — Validated** | L1, plus continuous measurement of the divergence between model and reality. **Our refinement** — the literature does not draw this line. |
| **L3 — Closed loop** | Automated bidirectional flow; the virtual side gates or commands the physical. Kritzinger's *digital twin*. |
| **L4 — Predictive** | The virtual side runs ahead of the physical: what-if scenarios, prediction, optimization. |

> **Do not use "Mirror".** An earlier charter draft used it for L1 and "Shadow" for L2,
> which collided with the literature. Renamed in charter v1.2. If you find `MIRROR`
> anywhere, it is stale — report it.

## Operating modes

Runtime modes at L5, corresponding to the levels above.

| Mode | Physical | Virtual |
|---|---|---|
| `SIM` | idle | commanded |
| `REAL` | commanded | idle |
| `SHADOW` | commanded | follows physical |
| `VALIDATED` | commanded | commanded in parallel, divergence measured, does not actuate |
| `CLOSED_LOOP` | commanded after virtual validation | validates first |

## Architecture

| Term | Means here |
|---|---|
| **Layer (L0–L7)** | A horizontal slice of the architecture. A layer may depend only on layers below it. |
| **Facility model** | The L0 declarative description of everything that exists. The single source of truth. |
| **Generated artifact** | Anything emitted from the facility model — worlds, descriptions, controller configs, launch graphs. **Never hand-edited.** |
| **Component library** | Reusable type definitions (robot types, end-effectors, sensors, station types) instantiated many times with a prefix. |
| **Asset** | A physical thing that exists in the facility: a robot, a conveyor, a sensor, a fixture. Has an ID, a type, a pose, and a zone. |
| **Asset instance** | One occurrence of a component type, with an identity and a pose. |
| **Zone** | A named region of the facility. Zones partition; they do not nest. |
| **Skill** | An L3 robot-agnostic capability exposed as a ROS 2 action. The unit of meaningful work. |
| **Station** | An L4 position in the process topology where work happens. A station has a robot; a robot may serve a station. |
| **Handoff** | Transfer of ownership of a work-piece between two robots. Exactly one owner at any instant. |
| **Work-piece** | The thing being processed. Tracked by L4. |
| **Twin monitor** | The L5 component that continuously measures and publishes divergence. |
| **Divergence** | Measured difference between predicted (model) and observed (physical) behaviour. Never an estimate — always a published number. |
| **Registration** | The transform between the real cell's coordinate frame and the model's. What makes measurements transferable. |
| **Safety layer** | The L2 enforcement point every command traverses before reaching a hardware interface. |

## Process

| Term | Means here |
|---|---|
| **ADR** | Architecture Decision Record. One decision, its options, and its costs. In `docs/adr/`. |
| **Charter** | `what-we-are-doing.md`. Protected — changes only by explicit decision of the project owner. |
| **Status marker** | `DESIGNED`, `PARTIAL`, or `BUILT`, at the top of every architecture and interface document. |
| **`ESCALATE`** | A finding that conflicts with a locked decision. Returned to the project owner, never self-resolved. |
| **Standing prohibition** | An item in `CLAUDE.md` §4, rejected in review without discussion. |
| **Script contract** | The fixed `./scripts/*` entry points. Always invoked instead of the underlying tool. |
| **Gate** | A verification that must pass before a phase is considered complete. |

## Standards

| Term | Means here |
|---|---|
| **ISO 23247** | The manufacturing digital twin framework our architecture aligns with. See [`../architecture/standards-alignment.md`](../architecture/standards-alignment.md). |
| **OME** | Observable Manufacturing Element — ISO 23247's term for a physical asset being twinned. |
| **DCDC** | Data Collection and Device Control — the ISO 23247 domain mapping to our L2 and L5. |
| **Aligned, not certified** | We map our architecture onto ISO 23247. We have not undergone conformance assessment, and no document may claim we have. |

## Words we avoid

| Avoid | Because | Say |
|---|---|---|
| "Mirror" | Collides with the renamed L1 | "Shadow", or the mode `SHADOW` |
| "Digital twin", unqualified | It is the word that let v1 call a simulation a twin | Name the level: "an L2 twin" |
| "ISO 23247 compliant" | Untrue. We are aligned, not assessed | "aligned with ISO 23247" |
| "Config-driven" | v1 claimed it while hand-editing world files | "generated from the facility model" |
| "Should work" | It either has a test or it does not | "tested by X", or "unverified" |
