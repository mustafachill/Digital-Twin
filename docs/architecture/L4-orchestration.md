# L4 — Orchestration

- **Status:** `PARTIAL`.
  **Built:** two executables on BehaviorTree.CPP v4.
  `src/line_coordinator.cpp` runs one station from `trees/station_cycle.xml` — a
  pick-then-place cycle with an explicit recovery branch — and is what
  `./scripts/scenario pick_and_place` drives.
  `src/line_orchestrator.cpp` **builds the line from the L0 topology**: it subscribes to
  `LineTopology` on the LATCHED profile, derives flow order from the edges by topological
  sort, and generates a root tree with one subtree of `trees/line_station.xml` per station.
  No source file names a station or counts them.
  Also built: the ADR-0024 L4 half — rendezvous tokens and two-party confirmation in
  `handoff_ledger.hpp`, with `workpiece_registry.hpp` making single ownership structural
  rather than protocol-dependent; `recovery_policy.hpp`, mapping every `ResultCode`
  constant to a response — `RETRY_SAME`, `RETRY_DIFFERENTLY`, `ESCALATE` or `STOP_LINE` for
  the nine failure codes, `NONE` for success — with retries bounded by a per-station budget
  and an unknown code escalating rather than defaulting to retry; `resource_arbiter.hpp`;
  and `LineState` publication from `line_maintenance.hpp`.
  Every leaf calls an L3 action; nothing here plans a trajectory.
  **Also built: L4 owns the belt setpoint** ([ADR-0032](../adr/0032-index-the-belt.md)).
  `conveyor_index.hpp` commands every belt at bring-up, stops the one feeding a station on
  that station's `DetectionEvent` transition, and `ResumeBelt` in `line_nodes.hpp` restarts
  it on `CompleteHandoff`. The stop is bound to the sensor edge rather than to a tree leaf,
  because a piece reaches the beam whenever it reaches the beam. Nothing sleeps and nothing
  branches on being in simulation. Which belt is never named here: it is the `via_asset_id`
  of the inbound edge of a station with a robot actor.
  **It owned the setpoint from 2026-08-26 and delivered it from 2026-08-27.** The publishers
  are created in the topology callback and the start-up command is published from that same
  callback, when no subscriber is matched yet — so a reliable profile delivered it to nobody
  and a test harness was starting the belts. A subscriber matching is now treated as an event
  and the belt's current setpoint is sent then. Read the 2026-08-27 correction on
  [ADR-0032](../adr/0032-index-the-belt.md) before changing anything about how the setpoint
  is published; the measurement and the failure mode are there and are not restated (P1).
  **Refused, deliberately:** a direct arm-to-arm handoff. `line_plan.hpp` rejects such an
  edge at plan time and a plan carrying refusals is not `usable()`
  ([ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md)). Today's
  topology has no such edge, so nothing is refused in practice.
  **The refusal stands and the reasoning behind it was corrected on 2026-08-26**: read that
  ADR's correction section before touching the gate or the string it emits. The residual the
  refusal string names is a **roll about the pad-to-pad axis, not a yaw**, so it cannot enter
  a presented-width calculation; nothing re-observes the part on any edge; and what makes the
  *permitted* conveyor edge safe is the receiving gripper closing on a free part — which is
  exactly what a direct handoff denies. The refusal string and the comment above the gate
  still carry the pre-correction reasoning; that is a code change, not a documentation one.
  **What the L4 tests prove, and what they do not.** **No arm moves in any of them.** The
  action servers are fakes that succeed because they are told to. What is proven is
  **sequence, ownership and recovery mapping** — not motion, not reachability, and not that
  the line works.
  **Motion is evidenced only by the scenario.** `./scripts/scenario continuous_line` now
  drives the whole line — the aid topics are bridged, `line_orchestrator` and the `Detect`
  server are started by `simulation.launch.py` (the coordinator behind `line:=true`), and
  the reported milestone ladder is full. That is reported from runs rather than from a
  campaign, and it runs in CI as `continue-on-error`; the count, its qualifications and what
  still stalls are in the status block in [CLAUDE.md §2](../../CLAUDE.md) and are not
  restated here (P1).
  **Not built:** parallel stations — stations tick one at a time — Groot2 integration, and
  any confirmation that a belt did what it was told: nothing publishes `ConveyorState`, so a
  belt that fails to stop or fails to restart is a stalled or a spilling line that L4 would
  not notice. The bridge carries a bare `std_msgs/Float64` each way.
- **Related:** [ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md), [ADR-0024](../adr/0024-handoff-split-between-l3-and-l4.md), [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md), [ADR-0032](../adr/0032-index-the-belt.md), [L3](L3-capabilities.md)

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
