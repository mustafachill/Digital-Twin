# ADR-0039: Report a station that cannot be triggered, as a line state of its own

- **Status:** Proposed. Written before the implementation, which is the point
  ([CLAUDE.md §12](../../CLAUDE.md)). Every "will" below is a commitment, not a description.
  Nothing here is built at `70c6431`.
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

It is expressed as two counters, each produced by the class that already produces the fact:

- `ConveyorIndex` counts, per belt, the edges on which it commanded that belt to a standstill.
  The count is incremented **in the same callback, under the same lock, before the standstill
  is recorded** — so any reader that sees the belt stopped also sees the edge counted. That
  ordering is what closes the window between the two subscriptions to one detection topic,
  which are dispatched separately and can be milliseconds apart under load.
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

- **A published enum value that some consumers will not handle.** Every reader of
  `LineState.state` now has a fifth case. There is one first-party reader today — the
  scenario — and it is updated here; anything written later that switches on this field and
  omits `STALLED` will treat a dead line as an unknown state.
- **The interface baseline moves**, and `interfaces.baseline` is deliberately not
  self-updating. This change regenerates it, and the reason is this record.
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
  not would need this rule rewritten, not tuned.
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
| The trigger and the belt stop are two separate subscriptions to one topic | Read `line_nodes.hpp:99-116` and `conveyor_index.hpp:190-200` | Two `create_subscription` calls on the same topic and profile, dispatched independently. This is the window condition 4 closes |
| The tick loop publishes `LineState` after the tick, on a period | Read `line_orchestrator.cpp:612-626` | `tickOnce()`, then `maintenance.run()`, then `publish()` every `state_period_ms` (default 200), under the tick mutex |
| `continuous_line` fails fast on `BLOCKED` and `FAULTED` only | Read `tests/scenarios/continuous_line.py` `_on_line_state`, `_fail_if_the_line_has_stopped` | Exact. A `RUNNING` stall is invisible to it, which is what ADR-0038's Evidence section observed |
| `Pick` opens the gripper before approaching | Read `skill_server.cpp:937-940` | Exact, with the stated collision reason. Cited from ADR-0038, re-read here because decision 5 above rests on it |
| The interface baseline is stored and not self-updating | Read `cite_interfaces/test/test_interface_contract.py` | Regeneration is behind `CITE_WRITE_INTERFACE_BASELINE=1` and the docstring asks for the reason in the commit message |
| Two `continuous_line` runs showed the stall reporting `RUNNING` | **Not re-verified.** Taken from ADR-0038's Evidence section | **Reported, not measured here.** Two runs on one machine against `c6acacc`, with no pre-registered thresholds and no `docs/measurements/` directory. The mechanism is checkable and was checked; the run narrative is one person's report |
| That the detector fires on the real defect in simulation | **Not verified when this record was written** | **Unverified.** It is what the implementation's `continuous_line` run is expected to show, and a run in which the grasp does not fail cannot show it at all |
