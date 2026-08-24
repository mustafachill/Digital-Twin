# L4 — Orchestration

- **Status:** `DESIGNED` — no trees or coordinator exist. Phase 1.D.
- **Related:** [ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md), [L3](L3-capabilities.md)

## Responsibility

L4 decides what happens next: which station acts, when an arm may enter a shared
workspace, how a handoff is negotiated, what happens when any of it fails, and how the line
recovers.

## Owns

- Behaviour trees expressing process logic.
- The line coordinator: work-piece tracking, station sequencing, buffer and resource
  arbitration, throughput accounting.
- The handoff protocol between robots.
- Fault recovery policy — what to retry, what to escalate, what to stop.

## Does not own

- **How anything is done.** L4 calls skills; it never plans a trajectory or commands a
  controller.
- Which robot is at a station, or where stations are — that is L0 topology.
- Safety enforcement. L4 must not be the thing preventing a collision; that is
  [cross-cutting-safety.md](cross-cutting-safety.md) at L2.

## Interfaces

**Consumes:** L3 skill actions; process topology from L0; sensor state.

**Exposes:** line state, work-piece positions, station status, throughput and cycle-time
metrics, and control services (start, pause, resume, reset) — all typed
([ADR-0010](../adr/0010-typed-ros-interfaces.md)).

## Design

### Trees, not state machines

[ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md) records why, from three
failed v1 attempts. The short version: hand-written state machines make asynchronous
operations, cancellation, and recovery awkward enough that developers route around them,
and they offer no runtime introspection that would reveal it.

Structure:

```
LineCoordinator (root)
├── Fallback: EmergencyHandling
│   ├── Sequence: OnFault → StopAll → AwaitReset
│   └── Sequence: Nominal
│       ├── Parallel
│       │   ├── Subtree: Station1
│       │   ├── Subtree: Station2
│       │   └── Subtree: Station3
│       └── Monitor: Throughput
```

One subtree per station, instantiated from L0 topology. **Keep trees shallow.** A deeply
nested tree is as hard to reason about as deeply nested conditionals, and the tooling does
not save you.

### Handoff is a negotiation with an owner

The v1 handoff failed because the coordinator published to a topic nothing subscribed to —
and no test noticed, because there was no test. Every transaction timed out forever.

The replacement rules:

1. **A work-piece has exactly one owner at any instant.** Ownership transfers atomically.
2. **Both parties must confirm** before physical transfer begins.
3. **A timeout has a defined outcome**, not merely an expiry: the upstream robot retains
   ownership and the line reports a blocked station.
4. **A handoff is testable in isolation** in a scenario test.

### Shared workspace arbitration is authoritative

When two arms can occupy the same volume, something must prevent it. L4 holds the
allocation, but **L4 is not the safety mechanism** — L2's limits and collision checking
are. L4 arbitration prevents *deadlock and thrash*; safety prevents *collision*. Confusing
those is how a coordination bug becomes an injury.

### Recovery is expressed, not implied

Each failure class has a defined response in the tree: retry with the same parameters,
retry with a different approach, escalate to a human, or stop the line. A generic retry
loop is not a recovery policy — it is a way of failing repeatedly at speed.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Publishing to a topic nobody consumes | Silent no-op; transactions time out forever (v1) | Scenario test; `reviewer` |
| Unreachable tree state | The line stops with no error | Groot2 inspection; scenario coverage |
| Ownership ambiguity | Two robots reach for one work-piece | Scenario test; `safety-auditor` |
| L4 relied on for collision avoidance | A coordination bug becomes a collision | `safety-auditor` — Critical |
| Blackboard used as a global store | Untraceable coupling between subtrees | `reviewer` |
| Recovery masking a real fault | The line "works" while silently degrading | Throughput monitoring; fault-rate metric |

## Open questions

- **One tree or one per station?** A single tree is easier to reason about globally;
  per-station trees scale better and fail independently. Decide before Phase 1.D.
- **Where handoff lives** — see the same question in [L3](L3-capabilities.md). It must be
  answered once, in one layer.
- **Facility-scale orchestration.** When the twin covers multiple cells, whether one
  coordinator spans them or each cell runs its own under a higher-level planner. The layer
  boundary does not change; the number of trees might.
