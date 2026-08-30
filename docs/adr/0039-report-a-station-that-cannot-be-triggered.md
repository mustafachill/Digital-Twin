# ADR-0039: Report a station that cannot be triggered, as a line state of its own

- **Status:** Proposed. Written before the implementation, which is the point
  ([CLAUDE.md §12](../../CLAUDE.md)). Every "will" below is a commitment, not a description.
  Nothing here is built at `70c6431`.
  **Corrected 2026-08-28 — see the section "Correction — 2026-08-28" below, which every
  reader must pass before the body.** Every decision here is implemented on branch
  `feat/report-a-station-that-cannot-be-triggered` and is under review, not merged; decision
  5's deliberate absences are still absent there. **Every decision stands.** What was wrong
  was three supporting claims about *why* the predicate is safe, and one cost that was not
  listed at all. The corrections make the case for condition 4 stronger, never weaker.
  **Amended 2026-08-29 — see the section "Amendment — 2026-08-29: the blind spot has been
  measured, and the fault it hides is not the one the record assumed", which sits above the
  correction so that the newest state is met first.** Nothing was measured false and no
  decision moves; the 2026-08-28 correction stands exactly as written. What is new is
  evidence: three CI runs, with logs, at the station correction item 5 names — and a
  measured contrast at a belt-fed station that shows what the coverage gap costs.
- **Date:** 2026-08-27
- **Deciders:** Coder agent, from the project owner's brief, against the defect
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md) records in its Evidence
  section
- **Related:** [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0032](0032-index-the-belt.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md) (**this record builds on its
  decision 3 and is bound by its decision 4**),
  charter §4 (P1, P3, P4, P5, P6, P7)

## The decision, in one line

`LineState` gains a **fifth state, `STATE_STALLED`**, published when no station is blocked or
faulted and at least one station is waiting on a trigger **nothing in the system can produce**
— derived from the plan and the belt setpoint by the same rule `AwaitReArm` already applies,
and commanding nothing.

## Why this is a record and not a note on ADR-0038

The reasoning is ADR-0038 decision 3's, applied on the nominal path instead of the fault
path. That much *is* a note, and if a log line were the whole answer this record would not
exist.

It is a record because the answer has to reach `LineState`, and every value that message
already defines is taken. **A new enum value on a published message is a typed-contract
decision (P3)**: it changes what `ros2 interface show` says, it moves the stored interface
baseline, and it hands every present and future consumer a state they must decide what to do
about. ADR-0010 says an interface is a versioned artefact; this changes one.

## Amendment — 2026-08-29: the blind spot has been measured, and the fault it hides is not the one the record assumed

**This is an amendment and not a correction, and the difference is load-bearing here.**
Nothing in this record or in the 2026-08-28 correction below was measured false, and the
correction is left exactly as it stands. What this section adds is evidence for the cost
correction item 5 introduced, and one fact about that cost that nothing here anticipated.

### The uncaptured run's ambiguity stands, and a different branch has now been captured

The 2026-08-28 verification table's second-to-last row records a `continuous_line` run whose
log was not kept, in which the work-piece sat on `cell_a__table_pick__surface` for the whole
420 s leg, and it refuses to call that proof because *"'never picked' and 'picked, failed, and
closed the loop' are different faults that would look the same in the milestone data"*.

**That row is not being corrected.** For the shape it was written about — a piece that never
leaves the pick table — the two really are indistinguishable, and the row was right to say so.

What has happened since is that the *other* branch has been captured three times, on CI
runners, with logs. All three have the identical signature, recorded in
[CLAUDE.md §2](../../CLAUDE.md): the piece reaches milestone 2 of 10,
`lifted(station_transfer_1: cell_a__table_pick__surface)`, never reaches milestone 3,
`on_link(station_transfer_1: cell_a__conveyor_1__infeed)`, and the leg expires on the ceiling
with `station_transfer_1` reporting `WAITING`, occupancy 1/1, the piece still assigned to it,
and `LineState` reading `RUNNING` with `blocked_reason=none stall_reasons=none`.

**In this branch the milestone data does distinguish the two faults**, and by the instrument
the row doubted: `lifted` is *measured*, not reported — `tests/scenarios/continuous_line.py`
computes `sample.z - frame_z > LIFTED_M` — so a piece that reaches it demonstrably rose off
the pick frame. **The grasp held.** The three runs then leave the part at the same pose to the
millimetre for the rest of the leg — `(-0.001, 0.273, 1.201)`, `(-0.001, 0.273, 1.201)` and
`(-0.001, 0.274, 1.201)` — which is the arm's own home region and not the pick table:
`pedestal_1` stands at `(0.000, -0.300, 0.000)` and is 0.600 m tall with `arm_1` on its `top`
frame, while `table_pick` is at `(-0.475, 0.000, 0.000)`. The observed x is within 1 mm of the
arm's base x and 474 mm from the table's.

So the fault this blind spot hides at `station_transfer_1` is **not** the failed-grasp dead end
this record's Context section assumes it is. The grasp succeeded; the *gripper's result*
timed out on a wall-clock deadline, the retry's `MoveToHome` carried the part off the beam,
and the station returned to `AwaitTrigger` on a beam that had gone clear and stayed clear.
[ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md) is the trigger and
[ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) is the L4 defect. **This
record's predicate is silent for both**, and for the same structural reason: no belt, nothing
to read.

### The contrast that shows the detector works and its coverage does not

In a local run the same fault class occurred at **`station_transfer_3`**, which is belt-fed
(`cell_a_flow.yaml`, `via: conveyor_2`). This record's detector fired **0.341 s later**, with
a named reason, and aborted the run.

Same fault, **diagnosed in a third of a second at a belt-fed station and silent for 420 s at
the table-fed one.** Correction item 5 says this change closes the class *"for two stations
out of three"*; that sentence now has a measurement behind it instead of an inference, and it
is the strongest evidence in this record that the decision was right and its coverage is
partial. **One local run, reported by the investigation and not re-measured here.**

### What this amendment does not do

It does not close the blind spot.
[ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) decision 2 proposes a
predicate that needs no belt — a station `IDLE` or `WAITING` while it still owns a work-piece
and still names a `current_workpiece_id` — and that closes **one failure shape** at the
table-fed station, not the class. The candidates correction item 5 names and declines to
choose between (the beam's *level* rather than its edges, or a re-observation of the pick
point) are still uncommitted, and neither is taken by that record either.

## Correction — 2026-08-28: the mechanism sentences under decision 3, and a blind spot that was not listed as one

Raised in review of the implementing commit. **The decision stands in full and no behaviour
below changed because of any of it.** One behaviour *was* added — a new plan-time refusal,
item 4 — and it is a refusal for a topology today's model cannot express.

### 1. "Under the same lock" was one critical section too few

Decision 3 says the count is incremented *"in the same callback, under the same lock, before
the standstill is recorded"*. The first and third clauses are right; the second is not.
`ConveyorIndex::on_edge` increments `stop_edges_` inside a scoped `lock_guard`, **releases
it**, and `command()` then re-acquires the same mutex to write `commanded_`. There are two
critical sections and the state between them is observable.

What the ordering actually guarantees is **one-directional**: a reader that sees the belt at a
standstill has necessarily seen the edge counted. The converse does not hold — a reader that
sees the count has *not* necessarily seen the standstill. `stalled_stations` reads in the safe
order (standstill first, count second) and is unaffected.

**A test was tripping on exactly this.** `test_line_nodes.cpp`'s `break_the_beam` waited on
`stop_edges > before` and then asserted `commanded == 0.0`, which is the unguaranteed
direction: a latent flake in the test that exists to prove the ordering, caused by the
ordering. It now waits on the standstill and asserts the count, which is the guaranteed
direction and is therefore deterministic *and* an assertion of the ordering rather than a
victim of it.

### 2. The interval is not two subscription callbacks racing, and it is wider than that

Decision 3 attributes the window to *"the two subscriptions to one detection topic, which are
dispatched separately and can be milliseconds apart under load"*. There are indeed two
subscriptions, and they **cannot be dispatched concurrently**. `TriggerWatch` and
`ConveyorIndex` both call `create_subscription` on the same node with no callback group
argument; rclcpp assigns the node's default group, and a node's default group is
`MutuallyExclusive`. Under the `MultiThreadedExecutor` the two callbacks are serialised.

The real interval is the gap between `ConveyorIndex` recording the standstill and the **tick
thread** next reaching `AwaitTrigger` and taking the edge — up to `tick_period_ms` (50 by
default), and longer whenever the station's subtree is elsewhere in its cycle.

**The conclusion is understated by the original, not overstated.** The window is wider than
"milliseconds apart", so condition 4 is *more* necessary than the record claimed.

### 3. Condition 4 closes one direction, and an ambient invariant closes the other

Decision 3 attributes the whole negative direction to the counters. They close *edge arrives →
station takes it*. They say nothing about *station takes it → `SetStationState` writes
`WORKING`*, and in **that** interval a perfectly healthy station satisfies all four
conditions: edge consumed, belt still stopped, state still `WAITING`.

What closes it is an invariant nothing in the tree states:

1. `TriggerWatch::take` is called only from `AwaitTrigger::onRunning`, on the tick thread, and
   `publish()` runs on that same thread after `tickOnce()` returns, inside the same
   `lock_guard`. No publication can land between the take and the end of that tick.
2. Within that one tick BT.CPP advances `AwaitTrigger` → `SetStationState`: the `idle`
   `<Parallel success_count="1">` reaches its threshold inside the child loop that saw the
   SUCCESS, and the enclosing node is a plain `<Sequence>` — whose early return on a child
   SUCCESS is gated on `asynch_`, which `Sequence` does not set. **BehaviorTree.CPP 4.9.0**,
   the version in this checkout.
3. Nothing else calls `take()`.

A `StatefulActionNode` inserted between the two leaves, a second `take()` caller, or
`publish()` moved onto a timer breaks it, and the counters do **not** save the predicate — it
becomes a false positive on **every arrival**, which `continuous_line` now aborts on. The
invariant is now written out in the `stalled_stations` comment, and
`RunningLine.ALineIsNeverReportedStalledWhileAPartIsArriving` drives the shipped XML through
real arrivals and fails if it is lost. Before that test, nothing exercised this leg at all:
all eight `StalledLine` cases call `take()` directly and set station state by hand.

**One thing on that list was checked and does not belong on it, which is the argument for
having the test rather than the reasoning.** Swapping the nominal `<Sequence>` for
`<AsyncSequence>` — the first refactor this correction predicted would break the invariant —
was applied to the shipped XML and the new test **still passed**. Setting `asynch_` is
evidently not on its own sufficient to make BT.CPP 4.9.0 yield between two synchronous
children; the early return is gated on more than the flag. So the prediction from reading the
library was wrong in the *safe* direction, and the mutation that does kill the test is a leaf
between the two that returns RUNNING once after consuming the edge — 1 of 36 cases failed, and
it was this one. **The list above is a warning, not a verified enumeration**; what is verified
is that the test discriminates.

### 4. One belt feeding two stations was assumed, and is now refused

The predicate compares `consumed(trigger_topic)` against `stop_edges(inbound_belt)`, which is
a statement about one station only if one belt feeds one station. `ConveyorIndex::index_on`
returns silently when a belt is already indexed, so under a shared belt the second station's
`consumed` would grow against a `stop_edges` count that never moves: condition 4 would never
suppress, and the line would report `STALLED` **continuously** — a sustained false positive
that now aborts the scenario with a misleading reason. `plan_line` had no uniqueness check on
`inbound_via_asset_id`.

**Refused at plan time**, beside the existing "no `conveyor_assets` entry declares a drive for
it" refusal it resembles: it is a plan property, it costs two lines, and it is checked before
the first tick rather than diagnosed from a wrong `LineState`. Not reachable on today's model,
which is exactly why a refusal is proportionate and a rewrite is not.

This is deliberately **narrower** than the shared-*trigger-topic* cost already in Consequences,
which stays a cost and not a refusal: which station a consumed edge belonged to is not a
question the plan can answer.

### 5. A cost that was missing: the detector is blind at a table-fed station

Not a wrong sentence but an absent one, and it is the correction that most changes what a
reader takes away. It is now stated in full as the first bullet of **What this costs us**.
In short: `station_transfer_1` has a trigger and no inbound belt, so condition 1 skips it; the
closed loop this record exists for happens there in the same shape and nothing reports it. The
record, the package README and the implementing commit all describe the skip as "the rule
working rather than an exception to it", which is true and is **not** the same sentence as
"the detector can see this failure here". This change closes the class for **two stations out
of three**.

### 6. Two claims the implementing commit made about its own evidence

Neither affects the code. Both are corrected in the verification table's 2026-08-28 block:
the mutation the commit cited does not discriminate what it said it did (the discrimination
that matters is real and lives in two other tests), and six of the eight `StalledLine` cases
assert a non-stall, not five. The Consequences bullet saying the baseline is "regenerated"
also disagreed with the commit saying it was hand-edited; review proved the two produce a
byte-identical file, so nothing was wrong and the record now says which was done.

### How these errors survived

**Items 1, 2 and 3 share one cause: the prose was written from the design and never re-derived
from the built code.** "Under the same lock" was true of the design intent and the
implementation split it in two; "dispatched independently" was true of the *subscriptions*
and false of their *dispatch*, which is a fact about rclcpp's default callback group that no
line of this package states; and the ambient invariant in item 3 was relied on without ever
being noticed, so it could not be written down or tested. None of the three was checkable from
the record — each needed a second file read that the verification table did not require of
itself, which is the discipline that table exists to enforce and did not.

**Item 5 survived because a true sentence stood in for a different one.** "The rule working
rather than an exception to it" is correct, defensible and answers a question nobody was
asking. The question was whether the failure is *visible* at that station, and no sentence in
the record was ever addressed to it.

**Item 1 also shows the shape of the cheapest possible detection**: the test written to prove
the ordering was itself written against the wrong direction of it. A test that asserts a
guarantee should be derived from the guarantee's statement, not from the behaviour observed
while writing it.

## Context

### The defect, observed rather than predicted

A work-piece fails the friction grasp ([ADR-0029](0029-simulated-grasping-by-friction.md)).
`RecoverFromFailure` classifies it as retryable, sets the station `STATE_WAITING`, and the
station's `Repeat` re-enters the nominal branch at `AwaitTrigger` — **on a beam the part is
already breaking**. Every link in what follows is checkable and was checked at `70c6431`:

| Fact | Where |
|---|---|
| A station triggers on the beam **breaking**, not clearing | `line_plan.hpp:311` |
| `TriggerWatch::take` requires `previous_state != state`, so a part already there produces no edge | `line_nodes.hpp:136` |
| `ConveyorIndex::on_edge` requires the same, and stopped the inbound belt on that edge | `conveyor_index.hpp:258`, `:266` |
| The only thing that runs that belt again is `ResumeBelt` | `line_station.xml:141` |
| `ResumeBelt` is reachable only after `CompleteHandoff`, itself only after the trigger | `line_station.xml:57`, `:110`, `:141`, one `<Sequence>` |
| A line with no station faulted, blocked or working publishes `STATE_RUNNING` | `line_maintenance.hpp:113-118` |

Closed loop, and it **reports itself healthy while it is in it**. ADR-0038's Evidence section
records it twice from `continuous_line` runs against `c6acacc`: piece 1 completed all ten
milestones, piece 2 hit the grasp failure, the station retried, and `LineState` reported
`RUNNING` until the 420 s leg ceiling expired.

### This is the third instance of one failure class, and the class is named

ADR-0038 lists the first two — v1's coordinator publishing handoff commands to a topic
nothing subscribed to, and the belt setpoint a test harness was quietly supplying — and calls
the shape by its name: **the system reported that it was doing the thing, and the thing was
not happening.** ADR-0038 decision 5 refused to wire resumption precisely so as not to create
a third. The third arrived by another entrance, and it is here now.

### What is already built, and is exactly the right rule in the wrong place

`AwaitReArm` asks: *is there a station that could ever be triggered again?* Its refusal is
derived rather than authored — `rearm_refusals()` in `line_fault.hpp`, a free function over
the station map and `ConveyorIndex`:

> For every station that has a trigger topic and an inbound belt, if that belt's last
> commanded setpoint is a standstill, the line cannot be re-armed. Refuse, naming the station
> and the belt.

`ConveyorIndex::commanded()` returns `std::optional<double>` so that *never commanded* and
*commanded to zero* stay distinct facts. Nothing in that rule names a station, a belt or a
speed.

**It is only ever asked after the line has already stopped.** On the nominal path the same
question is never put, so the condition is invisible for exactly as long as it matters.

### The constraint that shapes the answer: `STATE_BLOCKED` has one producer

ADR-0038 decision 4 gave `LineState::STATE_BLOCKED` exactly one author — the station's own
tree, by way of `StationRuntime.state` — and stripped `LineMaintenance::expire_handoffs` of
its second write. That was not tidying: the second author is what let a reset be accepted for
a station mid-`PlaceAt` and clear its `blocked_reason` under a moving arm. **Anything added
here that publishes `STATE_BLOCKED` reintroduces the defect that decision closed.**

## Options considered

### Option A — A log line, and nothing on the wire

`LineMaintenance` logs, on change, the same sentence `AwaitReArm` logs.

Genuinely plausible and the smallest diff. It is also what ADR-0038 accepted as sufficient
*for the fault branch* — "what makes this acceptable is that the refusal is logged with the
station and the belt named".

**Rejected, and the reason is the difference between the two paths.** On the fault path the
log is a supplement: `LineState` already says `BLOCKED`, so the wire is not lying. Here the
wire says `RUNNING`, and a log line beside a message that says the opposite does not correct
it — it adds a second answer to a question that has one (P1). It is also unassertable: the
scenario that produced this defect reads `LineState` and cannot read the coordinator's log
until the run is over.

### Option B — Publish `STATE_BLOCKED`

Reuse the value that already means "the line is waiting and a station cannot proceed".

**Rejected on ADR-0038 decision 4**, without weighing anything else. It is a second author
for a value that has one, and the meaning it would carry is not the meaning that value has:
`AwaitReset`, `StationReset` and `stations_holding_the_line` all read `BLOCKED` as "an
operator must clear this station", and there is nothing at a stalled station for an operator
to clear.

### Option C — Publish `STATE_STOPPED` or `STATE_PAUSED`

Both values exist and neither has a producer.

Rejected. `STATE_STOPPED` is unpublishable by construction if it means what
`line_maintenance.hpp:113-118` says it means — "the coordinator is not ticking", which a
coordinator cannot report about itself — and `STATE_PAUSED` says somebody paused the line. A
stalled line was not paused and nothing chose it. Squatting on either is a semantic decision
dressed as an economy, and the next reader has to reverse-engineer which meaning was intended.

### Option D — A new `StationState` value, `STATE_STALLED`

The fact is per-station, so put it on the station.

**Rejected, and it was the closest call.** `StationState.state` is copied from
`StationRuntime.state`, which the station's own tree writes. A value that appeared only in the
published message and never in the runtime map would be a split brain: `ros2 topic echo` would
say `STALLED` while `stations_holding_the_line`, `StationReset` and `AwaitReset` — all reading
the same field from the map — said `WAITING`. That is the ADR-0038 decision 4 defect in a new
field rather than an avoided one.

A separate *boolean* on `StationState` avoids the split brain and was the runner-up. It is not
chosen because it leaves `LineState.state` reading `RUNNING`, which is the sentence the defect
is about; adding both would be two fields for one fact.

### Option E — A fifth `LineState` value, derived in `LineMaintenance`

Chosen. Detailed below.

## Decision

### 1. `LineState` gains `STATE_STALLED=5` and `string[] stall_reasons`

```
uint8 STATE_STALLED=5   # no station is blocked or faulted, and at least one is waiting
                        # on a trigger nothing can produce
string[] stall_reasons  # one per stalled station; empty unless state is STALLED
```

`stall_reasons` is plural because several stations can be stalled at once, where only one
station can be blocked (the root `Parallel` halts the rest). Each element names the station
and the belt, and each is the sentence `rearm_refusals()` already composes — the same author,
not a second copy of it.

**The reasons are prose for a person and nothing parses them**, exactly as `blocked_reason`
and `ResultCode.detail` say of themselves. A consumer that must *act* reads `state`.

### 2. Exactly one producer, and it is not the one that owns `STATE_BLOCKED`

`LineMaintenance::publish` derives it. Precedence:

```
any station FAULTED   -> STATE_FAULTED
any station BLOCKED   -> STATE_BLOCKED     <- unchanged, one author, the station's tree
any station stalled   -> STATE_STALLED     <- new
otherwise             -> STATE_RUNNING     <- working or idle, both are running
```

`STATE_STALLED` sits **below** `BLOCKED`, so a blocked station still reports `BLOCKED` and
decision 4's single author is untouched. It sits **above** the working case deliberately: a
station that can never be triggered again will never be triggered again whether or not a
neighbour is still finishing its current piece, and the line is serial, so the neighbour
finishing is the last thing that will happen on it.

**`stall_reasons` is empty unless `state` is `STALLED`**, mirroring `blocked_reason`. During
a fault every belt is at a standstill because `StopAll` put it there, so a stall list
published then would be a description of `StopAll` rather than of a defect.

### 3. The predicate is a state predicate, and the negative direction is what it is shaped by

A station is stalled when **all** of these hold. Not one of them is a duration (P4).

1. It has a trigger topic and an inbound belt — the same gate `rearm_refusals()` applies, so
   a table-fed station is skipped by the rule working rather than by an exception to it.
   **[Corrected 2026-08-28 — see the Correction section above, item 5. True, and it is not
   the sentence a reader needs: the skip makes the detector blind at `station_transfer_1`,
   one of the three. The cost is now listed under Consequences.]**
2. Its state is `IDLE` or `WAITING` — the two states the tree writes while a station sits at
   its trigger. `WORKING` is a station that will reach `ResumeBelt`.
3. Its inbound belt's last commanded setpoint is a standstill, or the belt has never been
   commanded at all.
4. **It has already consumed every sensor edge that stopped that belt.**

Condition 4 is the whole of the negative direction and it is why this can be published at
all. Conditions 1-3 are true for several milliseconds of **every normal arrival**: the part
breaks the beam, `ConveyorIndex` stops the belt, and the station is still `WAITING` until it
takes the edge and its next leaf writes `WORKING`. A detector without condition 4 would fire
on every work-piece the line ever handles.
**[Corrected 2026-08-28 — see the Correction section above, items 2 and 3. The interval is
not "several milliseconds" but up to a tick period and longer, and condition 4 is not the
whole of the negative direction: it closes one of two legs.]**

It is expressed as two counters, each produced by the class that already produces the fact:

- `ConveyorIndex` counts, per belt, the edges on which it commanded that belt to a standstill.
  The count is incremented **in the same callback, under the same lock, before the standstill
  is recorded** — so any reader that sees the belt stopped also sees the edge counted. That
  ordering is what closes the window between the two subscriptions to one detection topic,
  which are dispatched separately and can be milliseconds apart under load.
  **[Corrected 2026-08-28 — see the Correction section above, items 1 and 2. Two critical
  sections, not one; the guarantee is one-directional and is the one this bullet names. The
  two subscriptions share the node's default `MutuallyExclusive` callback group and cannot be
  dispatched concurrently at all.]**
- `TriggerWatch` counts, per topic, the matching edges it has handed to a station.

Stalled requires `consumed >= stopped_on`. In the arrival window `consumed < stopped_on` and
the station is not reported. After the retry returns it to `AwaitTrigger` the counts are
equal, the belt is still at a standstill, and it is.

### 4. It commands nothing, and it is not a protective measure

It reads a plan, a setpoint record and two counters. It restarts no belt, plans nothing,
touches no gripper, writes no station state, releases no claim and moves no ownership. As with
everything in [ADR-0038](0038-stop-the-line-without-ending-the-process.md), what stops an arm
is the vendor controller's torque limiting and the cell's physical guarding (charter §3.2).
This is a report.

### 5. What is deliberately not built: the recovery half

**Re-arming is not decided here and this record must not be read as deciding it.** ADR-0038
decision 5 is unchanged, `AwaitReArm` still refuses, and nothing gains a `SUCCESS` edge.

The reason is worth restating because this change makes the wrong fix look one line away.
Re-arming is a decision about **what is where** — where the part is, whether the gripper holds
one, whether the beam is broken — and the cheap version of it is `ResumeBelt` on the recovery
path. The retry begins with `MoveToHome` carrying whatever the arm is holding; a new part
arrives on the now-running belt; the trigger fires; and `Pick`'s **first physical act is to
open the gripper** (`skill_server.cpp:937-940`), at the home pose, with the previous part
still in it. Nothing catches it: `cite_skills` attaches no `AttachedCollisionObject`, so the
planner does not know the part is there, and ADR-0029 removed the simulation-side attachment,
so friction alone is holding it. The tree already refuses the adjacent version of this at
`line_nodes.hpp:751-755`.

**This record makes the stall visible. It does not make it recoverable, and a stall that is
merely visible is still a dead line.**

### 6. The scenario ends on the state, not on the budget

`tests/scenarios/continuous_line.py` already fails fast on a `LineState` of `BLOCKED` or
`FAULTED`, because ADR-0038 removed the exit code that used to carry a stopped line out of the
process. `STALLED` joins them, for the same reason and with the same words: no station will
act again without a person, so nothing the run is waiting for can happen.

This is what the leg ceiling was doing badly. A 420 s timeout that accuses the wrong component
becomes a message that names the station and the belt.

## Consequences

### What this gets us

- The third instance of "reports healthy, does nothing" says so, in the field a consumer
  reads, at the moment it becomes true rather than after a 420 s ceiling.
- The rule that decides it has one author. `rearm_refusals()` and this predicate are the same
  sentence, derived from the plan and the setpoint, and neither names an asset (P1, P5).
- `continuous_line` stops spending a leg ceiling on a line that is already dead, and reports
  what killed it instead of which milestone it was waiting for.
- `AwaitReArm` stops being the only place the condition is stateable, so the fault path and
  the nominal path answer the same question the same way.

### What this costs us

- **THE DETECTOR IS BLIND AT A TABLE-FED STATION, AND THAT IS ONE OF THE THREE.** *(Added
  2026-08-28 — Correction item 5.)* Condition 1 skips a station with no inbound belt, and
  every sentence in this record calls that "the rule working rather than an exception to it".
  That is true, and it is a different sentence from *"the failure is visible here"*.
  `station_transfer_1` in today's model **has a trigger** —
  `/cite/cell_a/beam_pick/detection`, on `blocked` — and its inbound edge
  (`station_infeed → station_transfer_1`) names no belt. The closed loop this record exists
  for happens there in exactly the same shape: the grasp fails, the retry returns the station
  to `AwaitTrigger` on a beam the part is still breaking, no edge is possible, and nothing
  carries a new part to it. The line publishes `STATE_RUNNING` for ever, undetected. **It is
  also the station the run that motivated this record failed at.** So what this change closes
  is "reports healthy, does nothing" for **two stations out of three**, and a reader must not
  close the class on it.
  **No code change here is obviously right, which is why none was made.** The setpoint the
  rule reads does not exist for a table: there is no belt that could be at a standstill, so
  this rule has no correct answer to give. Closing it needs a **different fact**, and two are
  available in principle — the beam's *level* rather than its edges (`TriggerWatch` records
  only edges, and a station waiting at a trigger whose beam is already blocked is precisely
  the dead end), or a re-observation of the pick point. Either is a new source of truth for
  the predicate and therefore a separate decision, taken on its own evidence. **This record
  does not take it, and naming the candidates is not proposing one.**
  **It may already have been seen.** Of three `continuous_line` runs on 2026-08-28, the one
  that failed did so with the work-piece parked on `cell_a__table_pick__surface` for the whole
  420 s leg, and the run ended on the **ceiling** rather than on a `STALLED` message. That is
  the shape this bullet predicts, at the station it applies to — and it is one run whose log
  was not kept, so it is a coincidence worth someone's attention and **not** evidence. The
  verification table says exactly what is and is not known about it.
- **A published enum value that some consumers will not handle.** Every reader of
  `LineState.state` now has a fifth case. There is one first-party reader today — the
  scenario — and it is updated here; anything written later that switches on this field and
  omits `STALLED` will treat a dead line as an unknown state.
- **The interface baseline moves**, and `interfaces.baseline` is deliberately not
  self-updating. This change regenerates it, and the reason is this record.
  **[Corrected 2026-08-28 — see the Correction section above, item 6. It was hand-edited for
  the two added lines, not regenerated; the implementing commit said so and this bullet did
  not. Review proved the hand-edited file byte-identical to one written by
  `CITE_WRITE_INTERFACE_BASELINE=1`, so the artefact is right and only the two records
  disagreed about the route.]**
- **Two counters and two accessors** across `ConveyorIndex` and `TriggerWatch` — a further
  widening of two classes that had kept their state to themselves, for a predicate neither of
  them evaluates.
- **A dropped sensor edge silences the detector at that station, for ever.**
  `TriggerWatch`'s queue is bounded at 64 and drops the oldest with a warning; a drop leaves
  `consumed` permanently behind `stopped_on`, and condition 4 then never holds. The failure is
  in the safe direction — silence, not a false alarm — and it is a blind spot all the same.
- **Two stations sharing one trigger topic would break condition 4.** `TriggerWatch::take` is
  per topic and consumes for whichever station asks first, so the two counters would no longer
  be about the same station. Today's model gives every station its own beam; a model that did
  not would need this rule rewritten, not tuned. *(2026-08-28: this one stays a cost and not
  a refusal — which station a consumed edge belonged to is not a question the plan can
  answer. The neighbouring case below is different and is refused.)*
- **Two stations sharing one inbound belt is refused at plan time.** *(Added 2026-08-28 —
  Correction item 4.)* Unlike the shared trigger this is a plan property, and its failure is
  worse: `ConveyorIndex::index_on` returns silently for an already-indexed belt, so the second
  station's `consumed` grows against a `stop_edges` count that never moves, condition 4 never
  suppresses, and the line is reported `STALLED` **continuously** rather than in a window.
  Since `continuous_line` now aborts on `STALLED`, that would be a scenario failure with a
  misleading reason. `plan_line` names it beside the existing "no `conveyor_assets` entry
  declares a drive for it" refusal. Today's model cannot produce it; the refusal exists so
  that a model that could is stopped at bring-up rather than misreported at run time.
- **It reports a stall a few seconds before the station reaches `AwaitTrigger`.** A station in
  the recover branch is `WAITING` with its belt stopped while `MoveToHome` runs. That is not a
  false positive — the station is already doomed by then — but a reader watching the log will
  see the report arrive before the tree gets back to the leaf it is about.
- **A visible stall is not a fixed stall**, and this is the cost that matters. The line still
  dies; it now says so. Whoever finds this report in their way is meant to build the re-arm
  path, and ADR-0038 decision 5 is the only thing that says what that costs.

### What we will have to revisit

- **When a re-arm path exists**, this predicate stops holding on its own, for the same reason
  `AwaitReArm` stops refusing on its own: the setpoint it reads will not be a standstill.
  Nothing has to remember to delete it.
- **When something publishes `ConveyorState`**, condition 3 can read a measured speed instead
  of a commanded one, and the difference between "L4 decided zero" and "the belt is stopped"
  becomes observable. Until then this predicate, like `StopAll`, knows only what L4 decided.
- **Whether a stalled station should be reported per station as well as per line.** Option D's
  runner-up — a boolean on `StationState` — is the shape to take if a consumer ever needs the
  identity typed rather than in prose.
- **Whether `STATE_STALLED` should outrank the working case.** This record puts it above,
  because the line is serial. A line with independent branches would need the rule restated,
  not the precedence flipped.

## How the claims here were verified

In the style of [`toolchain.md`](../reference/toolchain.md). Everything was checked on
**2026-08-27** against the worktree at `70c6431` unless stated.

| Claim | How | Result |
|---|---|---|
| A line with nothing faulted, blocked or working publishes `STATE_RUNNING` | Read `line_maintenance.hpp:105-118` | Exact. The `else` reasons about idleness and is reached by a permanently stalled line too |
| `LineState` defines exactly five states and `STATE_STALLED` is not among them | Read `msg/LineState.msg` | `STOPPED=0`, `RUNNING=1`, `PAUSED=2`, `BLOCKED=3`, `FAULTED=4`. Nothing publishes `STOPPED` or `PAUSED` |
| `STATE_BLOCKED` has one author after ADR-0038 | Grepped the package for writes to `LineState::STATE_BLOCKED` and to `StationRuntime::state` | `line_maintenance.hpp:110` derives it from station state only; the sole station-state author on that path is `line_nodes.hpp:915` |
| `rearm_refusals()` derives the rule from the plan and the setpoint, naming nothing | Read `line_fault.hpp` | Exact, three refusal sentences, all composed from `runtime.trigger_topic`, `runtime.inbound_belt` and `ConveyorIndex::commanded()` |
| `commanded()` distinguishes never-commanded from commanded-to-zero | Read `conveyor_index.hpp` | Returns `std::optional<double>`; absent until the first command |
| The station is `WAITING` when the retry re-enters `AwaitTrigger` | Read `line_nodes.hpp` `RecoverFromFailure` retry branch and `line_station.xml:248-264` | Retry sets `STATE_WAITING`, then `ReleaseStationClaims`, then `MoveToHome`, then the `Repeat` re-enters the nominal branch |
| The station is `WORKING` in the same tick as a successful trigger | Read `line_station.xml:56-62` | `SetStationState state="2"` is the next child of the same `<Sequence>`, and a BT.CPP `SequenceNode` advances to it within one `tickOnce()` |
| The trigger and the belt stop are two separate subscriptions to one topic | Read `line_nodes.hpp:99-116` and `conveyor_index.hpp:190-200` | Two `create_subscription` calls on the same topic and profile, dispatched independently. This is the window condition 4 closes. **[Corrected 2026-08-28 — item 2. The two calls are real; "dispatched independently" is false, and this row is where that claim was accepted without reading the callback-group argument neither call passes.]** |
| The tick loop publishes `LineState` after the tick, on a period | Read `line_orchestrator.cpp:612-626` | `tickOnce()`, then `maintenance.run()`, then `publish()` every `state_period_ms` (default 200), under the tick mutex |
| `continuous_line` fails fast on `BLOCKED` and `FAULTED` only | Read `tests/scenarios/continuous_line.py` `_on_line_state`, `_fail_if_the_line_has_stopped` | Exact. A `RUNNING` stall is invisible to it, which is what ADR-0038's Evidence section observed |
| `Pick` opens the gripper before approaching | Read `skill_server.cpp:937-940` | Exact, with the stated collision reason. Cited from ADR-0038, re-read here because decision 5 above rests on it |
| The interface baseline is stored and not self-updating | Read `cite_interfaces/test/test_interface_contract.py` | Regeneration is behind `CITE_WRITE_INTERFACE_BASELINE=1` and the docstring asks for the reason in the commit message |
| Two `continuous_line` runs showed the stall reporting `RUNNING` | **Not re-verified.** Taken from ADR-0038's Evidence section | **Reported, not measured here.** Two runs on one machine against `c6acacc`, with no pre-registered thresholds and no `docs/measurements/` directory. The mechanism is checkable and was checked; the run narrative is one person's report |
| That the detector fires on the real defect in simulation | **Not verified when this record was written** | **Unverified.** It is what the implementation's `continuous_line` run is expected to show, and a run in which the grasp does not fail cannot show it at all |

Added **2026-08-28**, in review of the implementing commit. Checked against branch
`feat/report-a-station-that-cannot-be-triggered` unless stated.

| Claim | How | Result |
|---|---|---|
| `station_transfer_1` has a trigger and no inbound belt, so the detector is blind there | Read `cite_generated/topology/cell_a_flow.yaml` | Exact. Trigger `/cite/cell_a/beam_pick/detection` on `blocked`; the edge `station_infeed → station_transfer_1` carries `via: null`. One of the three transfer stations |
| The count and the standstill are two critical sections, not one | Read `conveyor_index.hpp` `on_edge` and `command` | Exact. `++stop_edges_[asset]` sits in a scoped `lock_guard` that is released before `command()` re-acquires the same mutex to write `commanded_` |
| `TriggerWatch` and `ConveyorIndex` cannot dispatch concurrently | Read both `create_subscription` calls and `line_orchestrator.cpp:374-376,438-439` | Same node, no callback group argument at either call site, so both take the node's default group. rclcpp creates a node's default group `MutuallyExclusive`; the executor is a `MultiThreadedExecutor`. The two callbacks are serialised |
| BT.CPP advances `AwaitTrigger → SetStationState` within one tick | Read `trees/line_station.xml` and BT.CPP 4.9.0 `ParallelNode` / `SequenceNode` | The `idle` `<Parallel success_count="1">` reaches its threshold inside the child loop, and the enclosing node is a plain `<Sequence>`, whose early return on a child SUCCESS is gated on `asynch_` — not set for `Sequence`. **This is an ambient property of a third-party library and a version bump can falsify it**, which is why item 3's test exists rather than this row |
| That the new test discriminates | Mutation, twice, rebuilt and re-run each time | **`<Sequence>` → `<AsyncSequence>` in the shipped XML did NOT kill it** — 36/36 still passed, so `asynch_` alone does not produce the yield in 4.9.0 and the reasoning above was wrong in the safe direction. **Making `AwaitTrigger` hold the consumed edge and return SUCCESS one tick later DID**: 35 passed, 1 failed, and it was `ALineIsNeverReportedStalledWhileAPartIsArriving` — both the synchronous sample (2 stalls, naming `station_two` and `conveyor_fixture`) and the message-level `STATE_STALLED` assertion. Nothing else in the file moved |
| `plan_line` had no uniqueness check on `inbound_via_asset_id` | Read `line_plan.hpp` at `bd8d639` | Exact. A shared inbound belt was accepted and `index_on` would have indexed it once, silently |
| **What actually discriminates the `publish()` precedence** | Mutation, re-traced from the implementing commit's own claim | **The implementing commit overstated it.** Disabling the `publish()` precedence kills only the two message-level assertions in `AStationReturnedToATriggerNothingCanProduceIsReportedAndNotRunning`; that same test's direct `stalled()` assertion still passes. The discrimination that matters is real and lives elsewhere, in the right shape: deleting condition 4 is killed by `AnArrivalInFlightIsNotAStall`, deleting condition 2 by `AWorkingStationHoldsItsOwnBeltStoppedAndIsNotStalled` — both negative tests |
| **How many `StalledLine` cases are negative** | Counted | **Six of the eight assert a non-stall**, not five as the implementing commit said. The two that assert a stall are `AStationReturnedToATriggerNothingCanProduceIsReportedAndNotRunning` and `ABeltNobodyHasEverCommandedIsItsOwnRefusal` |
| The hand-edited `interfaces.baseline` matches a regenerated one | Reviewer regenerated under `CITE_WRITE_INTERFACE_BASELINE=1` and diffed | Byte-identical. The contract check still discriminates under four mutations |
| A healthy line is never reported `STALLED` — at scenario scale, not only in a unit test | Two full `continuous_line` runs, 549 s and 572 s | **Zero** stall reports across both. Nine friction grasps per run, every one `stalled=true, reached_goal=false -> holding`; three cycles on each of the three arms; all beams firing. The predicate stayed quiet through every arrival |
| **The blind spot has probably been seen, and this is one uncaptured run** | A third `continuous_line` run, the first of three, whose full log was not kept | **Suggestive, not measured.** The cycle failed with the work-piece at `(-0.475, -0.000, 0.625)` for all 747 samples across the full 420 s leg — that is `cell_a__table_pick__surface` (`(-0.475, 0.0, 0.6)`) plus half a 50 mm cube, so the piece never left `station_transfer_1`'s pick table. The run ended on the **leg ceiling**, not on a `STALLED` message. That is the exact shape this blind spot predicts, at the exact station it applies to. It is **not** proof: the log is gone, and "never picked" and "picked, failed, and closed the loop" are different faults that would look the same in the milestone data. Recorded because the coincidence is worth the next person's attention, not because it settles anything |
| Verdicts across three runs at this commit | `./scripts/scenario continuous_line`, one machine, no thresholds registered in advance | **Cycle 2 of 3, teardown 3 of 3.** Runs 2 and 3 passed both phases. Run 1 failed the cycle as above and passed teardown. Three runs is the size of the evidence, not a campaign |
