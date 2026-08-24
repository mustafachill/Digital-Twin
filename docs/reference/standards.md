# Standards

- **Related:** [ADR-0016](../adr/0016-iso-23247-alignment.md), [`../architecture/standards-alignment.md`](../architecture/standards-alignment.md)

> **How the designations on this page were verified — 2026-08-24.** `iso.org` returns 403
> to scripted requests, so every part number, title, publication date, and lifecycle stage
> below was read from catalogue mirrors that reproduce ISO's own record —
> `genorma.com` (which exposes ISO's stage codes and publication dates) cross-checked
> against CSA Group, DIN Media, and MyStandards listings. Interpretation of what the 2025
> ISO 10218 revision *changed* comes from secondary commentary, principally A3
> (Association for Advancing Automation), and is marked as such where used. Nobody on this
> project has read the standards themselves; they are paywalled.

## ISO 23247 — Digital twin framework for manufacturing

*Automation systems and integration — Digital twin framework for manufacturing.*
**The reference architecture this project aligns with.** Parts 1–4 were published in 2021;
the series was extended in 2026.

| Part | Title | Covers |
|---|---|---|
| 23247-1:2021 | Overview and general principles | Defines Observable Manufacturing Elements (OMEs); scope and objectives for a manufacturing digital twin |
| 23247-2:2021 | Reference architecture | Domain-based and entity-based reference models; functional views |
| 23247-3:2021 | Digital representation of manufacturing elements | Basic information attributes for OMEs — static (design specification) and dynamic (live sensor data) |
| 23247-4:2021 | Information exchange | Technical requirements for exchange between entities in the framework |
| 23247-5:2026 | Digital thread for digital twin | Traceability of information across the asset lifecycle |
| 23247-6:2026 | Digital twin composition | Composing larger twins from constituent twins |

*Six parts, and all six designations and titles above, verified 2026-08-24. Part 6 is
Edition 1, dated 2026-07. An earlier version of this page said the series had four parts.*

**Parts 5 and 6 are new and we have not studied them in depth.** Both look directly
relevant and are flagged here rather than quietly omitted:

- **Part 5 (digital thread)** concerns traceability of information across an asset's
  lifecycle. It overlaps our L6 provenance requirement — every recording stamped with the
  model version, software version, mode, and registration that produced it.
- **Part 6 (digital twin composition)** concerns building a larger twin from constituent
  twins. That is precisely our facility-scale question: a CITE twin composed of cell twins,
  which is the open question at the bottom of
  [`../architecture/L4-orchestration.md`](../architecture/L4-orchestration.md).

Reviewing both, and updating the mapping if they change it, is outstanding work.

**Why it matters here:** it gives the architecture an external, tested structure rather
than only our own reasoning, and a shared vocabulary with the manufacturing digital-twin
literature. Its four domains — OME, Data Collection and Device Control, Core (Digital
Twin), and User — map onto our layer stack; see
[`../architecture/standards-alignment.md`](../architecture/standards-alignment.md).

**Access:** paywalled. The catalogue entries are
[Part 1 — 75066](https://www.iso.org/standard/75066.html),
[Part 2 — 78743](https://www.iso.org/standard/78743.html),
[Part 3 — 78744](https://www.iso.org/standard/78744.html),
[Part 4 — 78745](https://www.iso.org/standard/78745.html),
[Part 5 — 87425](https://www.iso.org/standard/87425.html), and
[Part 6 — 87426](https://www.iso.org/standard/87426.html) — verified 2026-08-24 by
resolving each part number through the Genorma catalogue mirror, which exposes ISO's own
project identifiers. (An earlier version of this page cited 78745 as Part 1; it is Part 4.)
Most contributors will work from our mapping document and the secondary sources below
rather than the standard itself.

**Note:** we are *aligned with* ISO 23247. We have not undergone conformance assessment.
No document in this repository may claim otherwise.

## IEC 63278-1:2023 — Asset Administration Shell

*Asset Administration Shell for industrial applications — Part 1: Asset Administration
Shell structure.* The Industry 4.0 standard for a digital representation of an asset,
providing a standardized information model for interoperability between industrial
systems.

**Why it matters here:** it is the natural answer if CITE later integrates the twin with
partner or plant systems. **Deliberately not adopted yet** — AAS earns its keep at an
integration boundary, and this project has no external system to integrate with before
Phase 4. Recorded in [ADR-0016](../adr/0016-iso-23247-alignment.md), Option D, so the
option is not forgotten.

## Robot safety — ISO 10218:2025

- **ISO 10218-1:2025** — *Robotics — Safety requirements — Part 1: Industrial robots.*
- **ISO 10218-2:2025** — *Robotics — Safety requirements — Part 2: Industrial robot
  applications and robot cells.*

Both were published on **5 February 2025** (ISO stage 60.60), and both withdrew their 2011
predecessors — the first major revision of the series since 2011. Per secondary commentary
(A3), the revision expanded functional-safety and mode requirements and introduced
cybersecurity requirements insofar as they affect robot safety.

### ISO/TS 15066 — read this carefully, the status is not simple

**ISO/TS 15066:2016 has not been withdrawn.** As of 2026-08-24 its ISO lifecycle stage is
**90.92, "standard to be revised"** (set 26 June 2025), and a successor, **ISO/AWI
15066-1**, is in development. An earlier revision project, ISO/PWI 15066, was abandoned.

What *is* true is that its collaborative-operation content — including the force and
pressure limits for human contact — was folded into **ISO 10218-2:2025**, on the reasoning
that human-robot collaboration is a property of the application rather than of the robot.
A3 states that the terms "collaborative robot" and "collaborative operation" do not appear
in the revised series. This part is secondary-source commentary, not something we read in
the standard.

So: **cite ISO 10218-2:2025 for collaborative-operation requirements, not ISO/TS 15066** —
but do not write that 15066 is withdrawn, because it is not.

**Why they matter here:** they bound Phase 2 and are **not optional** once a physical arm
moves.

**What we can and cannot do about them.** These standards govern the *physical
installation* and its risk assessment — guarding, safety-rated controllers, certification.
That is a hardware and process matter outside this repository (charter §3.2). This project
implements **software interlocks**: limit enforcement, E-stop propagation, watchdogs, mode
gating ([`../architecture/cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)).

Software interlocks are necessary and are not sufficient. **No amount of careful software
makes an unassessed, unguarded cell safe**, and reading this section as if it did would be
its own hazard.

## Communication standards — deferred

| Standard | Status |
|---|---|
| **OPC UA** (IEC 62541) | Deferred to Phase 4+. The L6 boundary is designed to accommodate it (charter §3.3). |
| **MQTT** (ISO/IEC 20922) | Same. Lighter weight; likely the first bridge if one is needed. |

Both appear in the ISO 23247 implementation literature as the usual means of real-time
connectivity between a simulation model and a physical system.
