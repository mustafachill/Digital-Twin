# ADR-0018: Use RViz 2 for debugging and Foxglove for shareable inspection

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** [ADR-0009](0009-docker-primary-environment.md), [ADR-0017](0017-mcap-recording-format.md), [`../architecture/L7-presentation.md`](../architecture/L7-presentation.md)

## Context

Two different needs get confused with each other:

1. **Debugging while developing** — TF trees, planning scenes, interactive markers, robot
   state. Deep ROS integration, used by one person at their desk.
2. **Seeing what happened, and showing someone** — a recorded run, a live view for someone
   who is not running ROS, a view a macOS contributor can actually open.

They are not the same need, and a single tool serving both would serve neither well.
There is also a constraint from [ADR-0009](0009-docker-primary-environment.md): GUI
passthrough works on Linux and is not worth the trouble on macOS, so a meaningful share of
contributors cannot open a native GUI at all.

## Options considered

### Option A — RViz 2 only
The ROS-native answer, deepest integration. Rejected as the *only* tool: it needs a
display, so macOS contributors and CI see nothing, and sharing a view means sharing a
screenshot.

### Option B — Foxglove only
Browser-based, shareable, reads MCAP directly. Rejected as the *only* tool: it does not
match RViz's depth for interactive MoveIt debugging, which is exactly where a developer
needs the most help.

### Option C — Both, with distinct roles
Chosen.

## Decision

| Tool | Role |
|---|---|
| **RViz 2** | Native debugging on Linux: planning scenes, TF, interactive markers |
| **Foxglove** | Shareable and browser-based: live inspection, MCAP playback, headless workflows, and the **interim L7** until Phase 4 |

Foxglove is deliberately treated as the default view for anything shared, because it is
what CI, the review agents, and headless contributors effectively see. A macOS contributor
running headless is looking at the same thing as everyone else, rather than at a degraded
version of it.

## Consequences

### What this gets us
- macOS contributors are fully productive without GUI passthrough
  ([ADR-0009](0009-docker-primary-environment.md)).
- Recorded runs are shareable as artifacts, not screenshots — a bag plus a Foxglove layout
  is reproducible inspection.
- An early, honest check on whether our data is actually consumable outside ROS. If
  something cannot be displayed in Foxglove, that is a signal about the interface, and it
  arrives four phases before L7 makes it expensive.
- No commitment yet on the Phase 4 HMI stack.

### What this costs us
- Two tools to learn, and two places a visualization configuration can live.
- Foxglove is a commercial product with a free tier. Relying on it for the interim L7
  accepts a dependency whose terms are not ours to set. Mitigated because MCAP is an open
  format — the recordings remain readable by other tools if that changes.
- Layouts drift between the two, so a view someone built in one is not available in the
  other.

### What we will have to revisit
At Phase 4, when the bespoke HMI is designed. Foxglove may remain as the engineering view
alongside an operator interface, or the operator interface may subsume it. Revisit sooner
if Foxglove's licensing changes.
