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
  **Also built: the fault branch** ([ADR-0038](../adr/0038-stop-the-line-without-ending-the-process.md)).
  The generated root tree was a bare `Parallel` of station subtrees, so a station that
  escalated failed the root, ended the tick loop and exited the process — which
  `simulation.launch.py`'s `_fatal_on_exit` turned into a teardown of the whole cell, taking
  the evidence of the fault with it and leaving the ADR-0037 reset service with no process
  to serve it. The root is now a plain `Fallback` over that unchanged `Parallel` and a fault
  `Sequence` of `OnFault → StopAll → AwaitReset → AwaitReArm` in `line_fault.hpp`. No leaf in
  it returns `FAILURE`, none takes a port, and none commands an arm; `StopAll` commands every
  declared belt to zero, which is `ConveyorIndex::stop()`'s first production caller. A
  latched fault still exits 1, so a run in which the line stopped still fails CI — and it is
  latched on **either** route into the branch, the one where a station classified why and the
  one where none did. Latching only the classified route left the second exiting 0 with the
  coordinator hung in `AwaitReArm`, which is worse than the exit it replaced.
  **NONE OF IT IS A PROTECTIVE MEASURE.** What stops an arm is the vendor controller's
  torque limiting and the cell's physical guarding (charter §3.2). This is a state machine;
  what it buys is that the coordinator is still there to be asked a question, and that it
  stops commanding belts it has stopped supervising.
  **What is proven about it, and what is not.** The tests — count them rather than trusting this sentence: that a station's escalation
  cancels a **sibling's** in-flight goal — the property `line_tree.hpp` had asserted in prose
  since the root tree existed, and which nothing tested — that the root goes on returning
  `RUNNING` afterwards, that the belts are put down, that the ADR-0037 reset is accepted on
  its happy path (which had never been reachable), and that the line then does **not**
  restart. Every one of them drives fake action servers that succeed because they are told
  to, so they prove sequence, ownership and the stop. **They prove no motion.**
  Added on 2026-08-27, from review: that a root failure **no station classified** is latched
  all the same — reached by failing `MoveToHome` on the retry path, which is the one route
  into the branch that leaves nothing `BLOCKED` — that the first latch is the one kept, that
  the maintenance pass retires an expired handoff and writes no station state, and that a
  reset is refused for a station whose arm is still placing (ADR-0038 decision 4, which had
  no test at all). **One thing here is asserted as source text and not driven:** the tick
  loop's guard against a leaf that *throws*. An exception out of a `tick()` is
  `std::terminate` out of `main` — worse than the exit that was removed — and the loop now
  catches, halts the tree and exits 1; `test_recovery_ordering.py` asserts the guard is
  present, and nothing asserts what it does, because the loop lives in `main`.
  **The line still stalls after a failed grasp**, and that is not what this closed. A retry
  returns a station to `AwaitTrigger` on a beam the part is already breaking, so no edge ever
  comes — observed on a `continuous_line` run at this commit, where `arm_1`'s gripper reached
  its commanded width with `stalled=false` and the station then waited out the scenario's
  budget. ADR-0038 names that dead end and deliberately does not fix it: the resumption edge
  is decision 5's other half and is a separate task.
  **Also built: the stall is now reported, for two of the three stations**
  ([ADR-0039](../adr/0039-report-a-station-that-cannot-be-triggered.md)). The paragraph above
  described the whole of it until 2026-08-28; the detection half is closed and the recovery
  half is not, so read them apart. `LineState` gains `STATE_STALLED` and `string[]
  stall_reasons`, and `LineMaintenance` publishes them when nothing is faulted or blocked and
  a station is `IDLE` or `WAITING` on a trigger nothing can produce. The rule is the same
  `untriggerable_reason` that `AwaitReArm` already applies, asked on the nominal path instead
  of the fault path, so the two cannot answer differently and neither names an asset.
  **`STATE_BLOCKED` keeps exactly one author** — ADR-0038 decision 4 is not reopened — and a
  blocked line publishes no stall reasons. `continuous_line` fails fast on `STALLED` alongside
  `BLOCKED` and `FAULTED`, so the run ends on the message naming the station and the belt
  rather than on a 420 s leg ceiling accusing whichever milestone it was waiting for.
  **IT COMMANDS NOTHING, AND A VISIBLE STALL IS NOT A FIXED STALL.** No belt is restarted,
  nothing is planned, no gripper is touched, no station state is written. `AwaitReArm` still
  keeps no `SUCCESS` edge; the line still dies, and now says so.
  **A second rule now answers where that one cannot, and it refuses as well as reports**
  ([ADR-0046](../adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)). The dead end
  above has a second entrance, taken three times on CI runners: the grasp HELD, the gripper's
  result timed out on a wall-clock deadline (ADR-0045), and the recovery's `MoveToHome` carried
  the part off the beam the station was about to wait on. `RecoverFromFailure` therefore
  answers `ESCALATE` rather than a retry for any station whose `current_workpiece_id` is
  non-empty — **keyed on custody, not on a result code**, so `recovery_policy.hpp` is unchanged
  and every entrance to the dead end closes at once rather than the one ADR-0045 removes. The
  same fact is published through the existing `STATE_STALLED`: a station `IDLE` or `WAITING`
  that owns a piece in the registry AND still names one in its runtime. All three legs are
  load-bearing — occupancy alone is true of every healthy transfer, because `CompleteHandoff`
  moves ownership while the piece is still on the belt. **It re-arms nothing** and ADR-0038
  decision 5 is untouched.
  **Its blind spot is a station fed by a table, and that is one of the three.** The rule needs
  a belt setpoint to read, and `station_transfer_1` has a trigger and no inbound belt — so the
  same closed loop happens there and nothing reports it. What that station's failure would need
  is a different fact (the beam's level rather than its edges, or a re-observation), which is a
  separate decision ADR-0039 deliberately does not take. **Do not read this as closing the
  "reports healthy, does nothing" class**; it closes it for two stations out of three.
  Two supporting claims in ADR-0039 about *why* the predicate is safe were measured wrong on
  2026-08-28 and are corrected in that record's Correction section — read it before changing
  the predicate or the ordering in `conveyor_index.hpp`; the mechanism is there and is not
  restated here (P1).
- **Related:** [ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md), [ADR-0024](../adr/0024-handoff-split-between-l3-and-l4.md), [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md), [ADR-0032](../adr/0032-index-the-belt.md), [ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md), [ADR-0038](../adr/0038-stop-the-line-without-ending-the-process.md), [ADR-0039](../adr/0039-report-a-station-that-cannot-be-triggered.md), [L3](L3-capabilities.md)

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

**The diagram above is the design, and the built shape differs from it in two ways.** The
generated root is now a plain `Fallback` over that `Parallel` and a fault `Sequence` of
`OnFault → StopAll → AwaitReset → AwaitReArm`
([ADR-0038](../adr/0038-stop-the-line-without-ending-the-process.md)). `EmergencyHandling`
does not exist and the nominal branch is not wrapped in a `Sequence` with a throughput
monitor; throughput is accounted for in `LineMaintenance` instead. Read the ADR before
touching any of the four leaves — what "the line has stopped" means for each actuator, and
why resumption is gated on re-armability rather than on the operator's acknowledgement, are
decided there and are not restated here (P1).

**Two things in that ADR are not what was built, and the difference is the project owner's
decision rather than the implementation's.** Decision 1 records `OnFault` as deliberately
not adopted, on the grounds that the `Parallel`'s own `FAILURE` is the fault event; it is
built, because the fault branch needs something to latch the station, the `ResultCode`, the
reason and the time for the coordinator's exit status — the tick loop no longer carries that
fact — and to settle the ledger before a handoff clock can expire through the fault and
re-block a station an operator has already reset. Decision 1's fourth leaf, `AwaitReArm`,
comes from decision 3. The ADR's own text on both points has not been amended.

**What is deliberately absent** is the resumption edge: `AwaitReArm` never returns `SUCCESS`
and nothing wraps the root `Fallback` in a `<Repeat>`. They land together or not at all
(decision 5), and a test asserts the `Repeat`'s absence so that half of it cannot arrive on
its own.

### Handoff is a negotiation with an owner

The v1 handoff failed because the coordinator published to a topic nothing subscribed to —
and no test noticed, because there was no test. Every transaction timed out forever.

The replacement rules:

1. **A work-piece has exactly one owner at any instant.** Ownership transfers atomically.
2. **Both parties must confirm** before physical transfer begins.
3. **A timeout has a defined outcome**, not merely an expiry: the upstream robot retains
   ownership, and the station's own tree reports what that means for it. The maintenance
   pass that expires the handoff no longer writes the station's state — `STATE_BLOCKED` has
   exactly one author, which is the station's tree (ADR-0038 decision 4). It got one because
   the expiry window spans a `PlaceAt`, so the second author could report a station blocked
   while its arm was placing, and the operator reset would accept a reset for it and destroy
   the reason mid-motion.
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
