# Standards alignment

- **Status:** `DESIGNED` — the mapping is defined; the layers it maps are not yet built.
- **Related:** [ADR-0016](../adr/0016-iso-23247-alignment.md), [ADR-0011](../adr/0011-twin-maturity-model-and-modes.md), [`../reference/standards.md`](../reference/standards.md)

This document maps the CITE Digital Twin architecture onto **ISO 23247**, reconciles our
maturity levels with the published literature, and states precisely what our alignment
claims and does not claim.

## What this claims, and what it does not

> **We align our architecture with the ISO 23247 reference architecture. We are not
> certified, we have not undergone conformance assessment, and no document in this
> repository may say otherwise.**

Alignment means our layers are deliberately mapped onto the standard's domains and
functional entities, and we adopt its vocabulary where ours would otherwise diverge for no
reason. It is a design discipline and a communication aid. It is not a certificate.

## ISO 23247 in brief

*Automation systems and integration — Digital twin framework for manufacturing.* Parts 1–4
published 2021; the series was extended in 2026.

| Part | Covers |
|---|---|
| 23247-1:2021 | Overview and general principles; defines Observable Manufacturing Elements (OMEs) |
| 23247-2:2021 | Reference architecture: domain-based and entity-based models, and functional views |
| 23247-3:2021 | Basic information attributes for observable manufacturing elements |
| 23247-4:2021 | Technical requirements for information exchange between entities |
| 23247-5:2026 | Digital thread for digital twin — lifecycle information traceability |
| 23247-6:2026 | Digital twin composition — building a larger twin from constituent twins |

**Our mapping below is against Part 2, the reference architecture.** Parts 5 and 6 are
recent and not yet studied. Part 6 in particular looks directly relevant to a
facility-scale twin composed of cell-scale twins, and reviewing it is outstanding work —
recorded here rather than omitted so that the gap is visible.

The reference architecture divides a manufacturing digital twin into four domains:

| Domain | Role |
|---|---|
| **Observable Manufacturing Element (OME)** | The physical manufacturing elements and their behaviours |
| **Data Collection and Device Control (DCDC)** | Acquires data from the OMEs and controls devices |
| **Core (Digital Twin)** | Holds the digital representations and models of the OMEs |
| **User** | Interfaces for people and applications — visualization, analytics |

## Domain mapping

```
   ISO 23247 domain                    CITE layer

   ┌─────────────────────┐             ┌──────────────────────────────────┐
   │  USER               │◄────────────┤  L7 Presentation                 │
   │                     │             │  L6 Data and telemetry           │
   └─────────────────────┘             └──────────────────────────────────┘
              ▲                                        ▲
   ┌─────────────────────┐             ┌──────────────────────────────────┐
   │  CORE (DIGITAL TWIN)│◄────────────┤  L4 Orchestration                │
   │                     │             │  L3 Capabilities                 │
   │                     │             │  L1 Description and assets       │
   │                     │             │  L0 Facility model               │
   └─────────────────────┘             └──────────────────────────────────┘
              ▲                                        ▲
   ┌─────────────────────┐             ┌──────────────────────────────────┐
   │  DATA COLLECTION    │◄────────────┤  L5 Twin synchronization         │
   │  AND DEVICE CONTROL │             │  L2 Control and HAL              │
   └─────────────────────┘             └──────────────────────────────────┘
              ▲                                        ▲
   ┌─────────────────────┐             ┌──────────────────────────────────┐
   │  OBSERVABLE         │             │  The physical cell:              │
   │  MANUFACTURING      │◄────────────┤  xArm arms, conveyors, sensors,  │
   │  ELEMENT            │             │  fixtures, the CITE facility     │
   └─────────────────────┘             └──────────────────────────────────┘
```

### Detailed mapping

| ISO 23247 domain | Functional concern | CITE layer | Where |
|---|---|---|---|
| OME | Physical assets and their observable behaviour | — (physical) | The lab cell |
| DCDC | Data collection from OMEs | L2 state interfaces, L5 mirroring | [L2](L2-control-and-hal.md), [L5](L5-twin-synchronization.md) |
| DCDC | Device control toward OMEs | L2 command interfaces, L5 command routing | [L2](L2-control-and-hal.md), [L5](L5-twin-synchronization.md) |
| DCDC | Identification and correspondence | L5 calibration and registration | [L5](L5-twin-synchronization.md) |
| Core | Digital representation of OMEs | L0 model, L1 descriptions | [L0](L0-facility-model.md), [L1](L1-description-and-assets.md) |
| Core | Simulation and analysis | L1 generated worlds, L5 divergence | [L1](L1-description-and-assets.md), [L5](L5-twin-synchronization.md) |
| Core | Operation and management | L3 skills, L4 orchestration | [L3](L3-capabilities.md), [L4](L4-orchestration.md) |
| Core | Synchronization with the physical | L5 modes and twin monitor | [L5](L5-twin-synchronization.md) |
| User | Application and service | L6 telemetry, historian, replay | [L6](L6-data-and-telemetry.md) |
| User | Presentation | L7 operator HMI, remote access | [L7](L7-presentation.md) |
| Cross-domain | Information exchange (23247-4) | Typed ROS interfaces; protocol bridges at L6 | [`../interfaces/`](../interfaces/README.md) |

### What the mapping surfaced

Mapping is a design review, not a labelling exercise. Two observations from doing it:

1. **The Core domain spans five of our layers.** ISO 23247 does not subdivide it, because
   its concern is the boundary with the physical world, not the internal structure of the
   twin. Our L0–L4 split is a refinement inside one of its domains, not a contradiction of
   it. This is the expected relationship between a reference architecture and an
   implementation architecture.

2. **DCDC maps to two of our layers, and that is deliberate.** ISO 23247 treats data
   collection and device control as one domain. We split it: L2 owns the interface to the
   device, L5 owns which direction data flows and under which mode. That split is what
   makes P2 — one control stack for simulation and hardware — expressible at all. It is the
   most substantive place our architecture departs from the standard's structure, and it
   departs by refining rather than by omitting.

## Twin maturity: reconciling with the literature

Kritzinger et al. (2018) is the canonical classification, by degree of information-flow
automation. Our five levels ([ADR-0011](../adr/0011-twin-maturity-model-and-modes.md)) map
onto it as follows.

| CITE level | Data flow | Kritzinger | Functional classification |
|---|---|---|---|
| **L0** Virtual model | none | Digital Model | — |
| **L1** Shadow | real → virtual, automated | Digital Shadow | Descriptive |
| **L2** Validated | real → virtual + divergence measured | (Digital Shadow, refined) | Diagnostic |
| **L3** Closed loop | bidirectional, automated | Digital Twin | Prescriptive |
| **L4** Predictive | virtual ahead of real | Digital Twin | Predictive / Prescriptive |

**L2 is our own refinement.** Kritzinger's classification asks whether information flows
automatically; it does not ask whether the model is *correct*. We separate those, because
a shadow whose divergence nobody measures is an assertion. L2 is the level at which the
twin begins proving itself, and it is why P8 requires every fidelity claim to carry a
published metric.

### A terminology hazard, resolved

An earlier draft of the charter used **Mirror** for automated physical → virtual and
**Shadow** for the divergence-measuring stage. That collides with the literature, where
*digital shadow* means the first of those, not the second.

The charter was amended (v1.2): **L1 is now `Shadow`** and **L2 is now `Validated`**, with
the L5 operating modes renamed to match. If you encounter `MIRROR` anywhere, it is stale
and should be reported.

## Standards we deliberately have not adopted

| Standard | Why not, and when to revisit |
|---|---|
| **IEC 63278 — Asset Administration Shell** | A strong asset information model for Industry 4.0 interoperability. It earns its keep at an integration boundary with external systems, which is Phase 4 at the earliest. Adopting its modelling obligations before there is anything to integrate with is cost without benefit. Revisit when external integration is scheduled. See [ADR-0016](../adr/0016-iso-23247-alignment.md), Option D. |
| **OPC UA / MQTT information models** | Charter §3.3 defers protocol bridges. The L6 boundary is designed so they can be added without restructuring. |
| **ISO 10218-1/-2:2025 — robot safety** | These bound Phase 2 and are **not optional** — but they govern the physical installation and its risk assessment, which is a hardware and process matter outside this repository (charter §3.2). We implement software interlocks; we do not deliver certified functional safety. Note that ISO/TS 15066's collaborative-operation content was absorbed into ISO 10218-2:2025. See [cross-cutting-safety.md](cross-cutting-safety.md) and [`../reference/standards.md`](../reference/standards.md). |

## Maintaining this document

The mapping is only useful while it is true. When a layer's responsibility changes, update
the mapping in the same change — a stale mapping is worse than none, because it is
trusted. `architect-reviewer` treats an unmapped layer, or a mapping that no longer matches
the layer document, as a finding.
