# L7 — Presentation

- **Status:** `DESIGNED` — nothing built. Phase 4. **Design constraints apply from Phase 1.**
- **Related:** [ADR-0010](../adr/0010-typed-ros-interfaces.md), [L6](L6-data-and-telemetry.md)

## Responsibility

L7 makes the twin legible to people who are not running ROS commands: operators, the CITE
team, and stakeholders outside the building.

## Owns

- The web operator interface: live cell state, robot status, KPIs, alarms, divergence
  trends, historical playback.
- Remote access, authentication, and access control.
- Reporting and export.

## Does not own

- Any data. Everything displayed originates below and is recorded by L6.
- Control logic. Operator actions become typed service or action calls into L4; L7 never
  commands hardware directly.

## Interfaces

**Consumes:** live state via a gateway, history from L6, scene topology from L0.

**Exposes:** a browser interface and, eventually, a versioned API for external consumers.

## Design

### Why this document exists now, four phases early

L7 is built in Phase 4, but it constrains every phase before it.

> **Every piece of state the HMI will need must be reachable over a versioned,
> transport-agnostic gateway — not only over native ROS 2 transport.**

This is why [ADR-0010](../adr/0010-typed-ros-interfaces.md) is non-negotiable. A browser
cannot consume a stringified Python dict. The v1 workspace published its entire robot
status that way, which quietly foreclosed the dashboard the project wanted — nobody
noticed, because the dashboard was always "later".

If Phase 1 gets its interfaces right, Phase 4 is a front-end project. If it does not,
Phase 4 begins by rewriting the interfaces of every layer beneath it.

### Gateway, not a ROS client in the browser

A browser does not speak DDS. Something must bridge — `rosbridge`, a Foxglove bridge, or a
purpose-built gateway. The choice is deferred, but two properties are not:

1. **Versioned.** The browser and the robot stack deploy independently and will not always
   agree on version.
2. **Curated.** The gateway exposes a deliberate subset. Bridging every topic to the
   internet is both a performance and a security problem.

### Foxglove first

Before a bespoke HMI exists, Foxglove provides live inspection and bag playback in a
browser. It is also what CI and the review agents effectively see, so a macOS contributor
running headless is looking at the same view as everyone else. Treat it as the interim L7
and as a check on whether the data is actually consumable.

### What the interface must answer

Ordered by how often the question is asked:

1. Is the line running, and if not, why?
2. Where is each work-piece?
3. What is each robot doing?
4. What is throughput and cycle time, now and trending?
5. **How far is the twin from reality, and is that getting worse?**
6. What happened during a past run?

Item 5 is the one that distinguishes this from a factory dashboard. It is the twin's own
self-report, and it should be visible rather than buried.

### Remote access is a security boundary

Charter §3.3 defers cloud access, but the day it arrives, the robot network becomes
reachable from outside the building. Authentication, authorization, network segmentation,
and audit are prerequisites rather than follow-ups, and the `security-auditor` role returns
to the active roster at that point.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| State only reachable over native ROS | HMI blocked; interfaces need rework | Design review from Phase 1 |
| Gateway bridging everything | Bandwidth exhaustion; needless exposure | Curated allowlist; review |
| HMI commanding hardware directly | Safety layer bypassed | `safety-auditor` — Critical |
| Stale display presented as live | Operator acts on old information | Freshness indicator; heartbeat |
| Divergence hidden in a sub-page | The twin's core metric goes unwatched | Interface review |
| Remote access without segmentation | Robot network exposed | `security-auditor` (Phase 4) |

## Open questions

- **Gateway technology** — `rosbridge`, Foxglove, or purpose-built. Phase 4.
- **Front-end stack.** Unconstrained today. The `ui-ux-pro-max` skill referenced in
  `.claude/agents/coder.md` applies when it is chosen.
- **Whether operators can command anything at all**, or whether L7 is read-only in its
  first version. Read-only is the safer starting point and probably right.
- **Multi-tenancy.** If CITE demonstrates the twin to visitors, what should a visitor see?
