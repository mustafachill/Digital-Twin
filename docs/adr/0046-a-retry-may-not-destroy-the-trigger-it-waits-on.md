# ADR-0046: A retry may not re-enter a wait on a trigger its own recovery destroyed

- **Status:** Proposed. Written before the implementation, which is what
  [CLAUDE.md §12](../../CLAUDE.md) asks for. **Nothing in this record is built at `b8a6c10`**;
  every "will" below is a commitment and not a description.
- **Date:** 2026-08-29
- **Deciders:** Docs-writer agent, from the project owner's root-cause investigation of the
  three `continuous_line` CI cycle failures recorded in [CLAUDE.md §2](../../CLAUDE.md)
- **Related:** [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0032](0032-index-the-belt.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md) (**the same dead end, entered
  by a different door — see the section below, and its decision 5 is untouched**),
  [ADR-0039](0039-report-a-station-that-cannot-be-triggered.md) (**this record closes its
  table-fed blind spot for one failure shape and not for the class**),
  [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md) (**the L3 half of the
  same failure**),
  [L4](../architecture/L4-orchestration.md),
  charter §4 (P1, P3, P4, P5, P7)

## The decision, in one line

A station that **still holds the work-piece its failed attempt was about** may not re-enter
the nominal branch at `AwaitTrigger`: the retry is refused and the station escalates. The same
fact — waiting while holding — is published through
[ADR-0039](0039-report-a-station-that-cannot-be-triggered.md)'s existing `STATE_STALLED`, and
it needs no belt and no sensor, so it works at the table-fed station where that detector is
blind.

## The same dead end as ADR-0038, entered by a different door

This is the sentence every previous account of this failure got wrong, so it is stated before
anything else.

[ADR-0038](0038-stop-the-line-without-ending-the-process.md)'s Evidence section records a dead
end reached like this: **the grasp fails**, the part is never lifted, it stands at the pick
point still **breaking** the beam, the station retries, `AwaitTrigger` needs
`previous_state != state` and a beam that is already blocked produces no edge. The arm holds
nothing.

This record's dead end is reached like this: **the grasp holds**. What fails is the gripper's
*result*, on a wall-clock deadline
([ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md)). `Pick` returns
`TIMEOUT`, the recovery's `MoveToHome` carries the part **off** the beam, and the beam clears
and then stays clear. The station retries onto a beam that is clear, and the only queued event
is that clear edge, which `TriggerWatch::take` pops and discards because it is not the
transition the station waits on. **The arm is holding the piece.**

| | ADR-0038's door | This door |
|---|---|---|
| The grasp | failed | held |
| The beam's terminal level | blocked | clear |
| The arm | empty | **holding the work-piece** |
| The station | re-enters `AwaitTrigger`, no edge possible | re-enters `AwaitTrigger`, no edge possible |
| `LineState` | `RUNNING` | `RUNNING` |
| ADR-0039's detector | silent (table-fed) | silent (table-fed) |

**They are identical in the four rows that matter and different in the three that decide what
any fix would have to do.** ADR-0038's dead end needs a part cleared off a beam. This one needs
a part taken out of a gripper. Neither is decided, here or there.

## Context

### What is true today, read from source at `b8a6c10`

- **The recover branch is `RecoverFromFailure → ReleaseStationClaims → MoveToHome`**
  (`trees/line_station.xml:248-263`), and the station subtree is
  `Repeat[Fallback[nominal, recover]]`, so a recovery that returns `SUCCESS` re-enters the
  nominal branch at `AwaitTrigger` (`:46-57`).
- `RecoverFromFailure` reads the failed skill's `ResultCode` and asks `recovery_policy.hpp`;
  `RETRY_SAME` sets the station `STATE_WAITING` and returns `SUCCESS`
  (`line_nodes.hpp:1073-1086`), `ESCALATE` sets `STATE_BLOCKED` and returns `FAILURE`
  (`:1088-1093`). It is the sole author of `STATE_BLOCKED`, which is
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md) decision 4.
- **`TIMEOUT` maps to `RETRY_SAME`** (`recovery_policy.hpp:140-142`), sharing a branch with
  `EXECUTION_FAILED`.
- **The trigger is an edge and the queue is drained past non-matching events.**
  `TriggerWatch::take` (`line_nodes.hpp:127-144`) pops each queued event and returns only one
  with `event.state == state && event.previous_state != event.state`; anything else is popped
  and **discarded** (`:135-142`). A station triggers on the beam **breaking**
  (`line_plan.hpp:311`).
- **`station_transfer_1` is table-fed.** Its inbound edge in the generated topology is
  `{from: station_infeed, to: station_transfer_1, via: null, buffer: 6}`
  (`cite_generated/topology/cell_a_flow.yaml:63`). `beam_pick` stands over
  `table_pick/surface` and, in the L0 comment's own words, *"does NOT index. A table is not
  driven, so there is nothing to stop"* (`model/assets/instances/sensors.yaml`).
- **So nothing in the line carries work to it.** `untriggerable_reason`
  (`line_nodes.hpp:265-291`) returns `nullopt` at its first test whenever `inbound_belt` is
  empty, so `stalled_stations` (`line_maintenance.hpp:131-159`) can never report that station
  and the line publishes `STATE_RUNNING` (`:244-252`). That is exactly the blind spot
  [ADR-0039](0039-report-a-station-that-cannot-be-triggered.md)'s 2026-08-28 correction adds
  as a cost, and the comment at `line_nodes.hpp:239-249` says so in the code.
- **Custody survives the failure.** `TakeCustody` mints and admits the piece at a station that
  admits work, and writes `current_workpiece_id` (`line_nodes.hpp:550-561`). Only
  `CompleteHandoff` clears it (`:868`). `RecoverFromFailure` does not touch it, and neither
  does `SetStationState` (`:957-993`). `StationState.buffer_occupancy` is
  `WorkpieceRegistry::occupancy` — how many pieces that station owns
  (`line_maintenance.hpp:207-208`, `workpiece_registry.hpp:206-210`).
- **A re-arm here would drop the part.** `Pick`'s first physical act is to open the gripper
  (`skill_server.cpp:937-944`), the retry begins with `MoveToHome` carrying whatever is in the
  jaws, `cite_skills` attaches no `AttachedCollisionObject`, and
  [ADR-0029](0029-simulated-grasping-by-friction.md) removed the simulation-side attachment,
  so friction alone is holding it. This is ADR-0038 decision 5's hazard, unchanged.

### What the three CI runs show

All three have the identical signature, recorded in [CLAUDE.md §2](../../CLAUDE.md) and not
restated here beyond what this record's argument rests on: the piece reaches milestone 2 of
10, `lifted(station_transfer_1: cell_a__table_pick__surface)`, never reaches milestone 3,
`on_link(...conveyor_1__infeed)`, and the leg expires on the 420 s ceiling
(`tests/scenarios/continuous_line.py:125`) with `station_transfer_1` reporting `WAITING`,
occupancy 1/1, the piece still assigned to it — and `LineState` reading `RUNNING` with
`blocked_reason=none stall_reasons=none`.

**`lifted` is a measured milestone**, not a report from the arm: the scenario computes
`sample.z - frame_z > LIFTED_M` (`continuous_line.py:664-665`). So the piece demonstrably rose
off the pick table, and **the grasp held**.

The three runs end with the part at the same pose to the millimetre — `(-0.001, 0.273, 1.201)`
twice and `(-0.001, 0.274, 1.201)` once — held there for the rest of the leg. That pose is
**not** the pick table and it is where the arm's own home configuration puts the jaws:
`pedestal_1` stands at `(0.000, -0.300, 0.000)` and is 0.600 m tall, `arm_1` is placed on its
`top` frame yawed +90 degrees to face +Y, and `table_pick` is at `(-0.475, 0.000, 0.000)`. The
observed x is within 1 mm of the arm's base x and 474 mm from the table's; the observed z is
0.601 m above the arm's base.

### The controlled contrast, which is the sharpest evidence in the investigation

In a local run **the same fault class occurred at `station_transfer_3`**, which is belt-fed
(`cell_a_flow.yaml:65`, `via: conveyor_2`). ADR-0039's detector fired **0.341 s later** with a
named reason and aborted the run.

Same fault, **diagnosed in a third of a second at a belt-fed station and silent for 420 s at
the table-fed one.** That is a statement about coverage and not about the detector: the
detector works, and the rule it applies has nothing to read where there is no belt.

**That run is one run, reported by the investigation and not re-measured here.**

### Why nothing else caught it either

`continuous_line` fails fast on `BLOCKED`, `FAULTED` and `STALLED`
(`continuous_line.py:458`) and the line reported none of them. The 420 s leg ceiling is what
ended the run, and a ceiling accuses whichever milestone it was waiting for rather than
whatever stopped the piece — which is the same complaint
[ADR-0039](0039-report-a-station-that-cannot-be-triggered.md) decision 6 makes about it.

## Options considered

### Option A — Leave it, and fix the deadline in L3

[ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md) removes the trigger, so
the argument runs: with no spurious `TIMEOUT` there is no spurious retry, and the dead end is
unreachable.

**Rejected, and the reason is that it is an argument about one entrance.** The retry path is
reached by every `RETRY_SAME` code, and `EXECUTION_FAILED` shares that branch. The
empty-grasp misclassification named at the end of ADR-0045 reaches it too, from a completely
different defect. A dead end that is reachable by any code in a policy table is not closed by
removing one producer of one code.

### Option B — Restart the belt on the recovery path

The cheap fix, and the one that looks one line away. **Rejected on ADR-0038 decision 5**,
which this record does not reopen: the retry's first physical act would be `Pick` opening the
jaws at the home pose, dropping a part no planner knows is held. At `station_transfer_1` it is
not even available — there is no belt to restart.

### Option C — Report it and change nothing in the tree

Add the detection rule only. The line would publish `STATE_STALLED` with a named reason
within a publication period, the scenario would abort on the message instead of on the
ceiling, and no behaviour would change.

**Genuinely plausible, and it is half of what is chosen.** Rejected as the whole answer for
ADR-0039's own reason: *"a stall that is merely visible is still a dead line"*. It also leaves
the tree performing an action — re-entering a wait it has made unsatisfiable — that it can
know at the time is wrong.

### Option D — Refuse the retry on a prediction that no trigger can be produced

Extend `untriggerable_reason` so it answers for a table-fed station too, and refuse the retry
when it does.

**Rejected, because the rule would have to state an unprovable negative.** At a belt-fed
station the refusal is derived from a fact the coordinator owns: L4 commanded that belt to a
standstill. At a table-fed station there is no such fact. Whether something outside the line
puts another part on that table is not knowable from inside the coordinator, and a rule that
asserts it cannot is asserting something it cannot check. (That the *scenario* spawns the next
piece only when the current one finishes is a property of the harness, not of the line, and
must not be built into L4.)

### Option E — Key the refusal on custody, and publish the same fact

Chosen. Custody is a fact the line owns outright: the registry says which station owns the
piece and the station's runtime names it. It needs no belt, no sensor and no prediction about
the world outside the cell.

## Decision

### 1. A station that still holds its work-piece may not re-enter `AwaitTrigger`

When `RecoverFromFailure` would answer `RETRY_SAME` for a station whose
`current_workpiece_id` is non-empty, it answers **`ESCALATE`** instead, with a reason that
says the station is holding a piece and the branch it would return to waits for a new one.

**Custody decides, not the result code.** `recovery_policy.hpp` is untouched: the mapping from
`ResultCode` to `Recovery` stays exactly as it is, and this is a precondition applied to the
retry rather than a new row in the table. That matters for three reasons. It closes every
entrance at once rather than the one ADR-0045 removes. It keeps the policy table a statement
about failures and not about states. And it does not require any judgement about whether a
`TIMEOUT` "should" be retryable — a timeout with an empty gripper still is.

**Why escalation is the right refusal and not a lesser one.** The escalation path is built,
tested and already leads somewhere useful: the station goes `STATE_BLOCKED`, the root
`Parallel` fails at `failure_count="1"`, and ADR-0038's fault branch stops the belts, keeps
the coordinator alive and holds it open for the
[ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md) reset. The arm stays where it
is with the part still in the jaws, which is the state a person needs in order to decide what
to do with it.

**It does not give up availability that exists.** Today this station's failure stops the line
anyway — silently, for 420 s, and then the run dies accusing a milestone. What changes is that
the line says which station stopped it and why, and that there is a process left to ask.

### 2. The same fact is published, as an ADR-0039 stall

`LineMaintenance::publish` reports a station as stalled when **all three** hold:

1. its state is `IDLE` or `WAITING`;
2. its `buffer_occupancy` is greater than zero; and
3. its `current_workpiece_id` is non-empty.

The reason names the station and the work-piece, in the shape `untriggerable_reason` already
uses, and it joins the existing `stall_reasons` list.

**This is not redundant with decision 1 and the two are not alternatives.** Decision 1 fires
only where `RecoverFromFailure` runs. The report is derived from the published state on every
publication, whatever route produced it, and it is the net for the routes decision 1 does not
cover. It is also what makes the failure visible to the scenario within a publication period
rather than after a leg ceiling.

**It needs no belt and no sensor**, which is the whole point: it works at
`station_transfer_1`, where ADR-0039's rule has nothing to read. **It closes that blind spot
for this failure shape only.** ADR-0038's door — a part left standing on the beam with the arm
empty — has occupancy 1 and an empty `current_workpiece_id` at the moment of the retry only if
custody was never taken, so this predicate does **not** close it, and nobody may read this
record as closing the table-fed blind spot in general.

### 3. `STATE_STALLED` is reused; no sixth `LineState` value is added

The meaning is already right — *no station is blocked or faulted, and at least one is waiting
for something that cannot come* — the precedence in `publish` (`line_maintenance.hpp:221-253`)
needs no change, and `continuous_line` already fails fast on it. A sixth value would hand
every consumer another case for a fact the fifth already describes.

**One documented contract narrows and must be widened.** `LineState.stall_reasons` says of
itself that each element names *"the station and the belt that would have carried work to
it"*. A reason with no belt in it falsifies that sentence, so the message's comment changes
with this decision. That is a typed-contract documentation change (P3) and it is part of the
implementation, not a footnote to it.

**`stall_reasons` stays empty unless `state` is `STALLED`**, and `STATE_BLOCKED` keeps exactly
one author. Nothing here writes a station state; decision 1 changes only what
`RecoverFromFailure` — already the sole author — answers.

### 4. The unreachability of the reported state is an assertion to prove, not to assume

Read from the tree at `b8a6c10`, the reported state **looks** unreachable in a healthy cycle:
`SetStationState state="2"` is written immediately after `AwaitTrigger`
(`line_station.xml:62`), `TakeCustody` (`:90`) and `CompleteHandoff` (`:110`) both fall inside
that window, the state returns to `0` only at `:147`, and `current_workpiece_id` is cleared by
`CompleteHandoff` before that. **"Looks unreachable" is exactly the kind of sentence this
project has been wrong about before**, so the implementation owes a test that drives the
shipped XML through real arrivals and fails if the predicate ever fires on a healthy cycle —
the shape `RunningLine.ALineIsNeverReportedStalledWhileAPartIsArriving` already has.

**One leg of the predicate is load-bearing and was nearly left out.** Condition 2 alone —
`buffer_occupancy > 0` — is **reached in every healthy cycle at a belt-fed station**:
`CompleteHandoff` transfers ownership to the receiving station while the piece is
`IN_TRANSIT` on the belt (`line_nodes.hpp:851-859`, whose comment says *"the receiving station
owns it from this instant even though it has not touched it"*), and that station sits in
`WAITING` until the piece arrives. A predicate built on occupancy alone would fire on every
transfer the line ever performs. **Condition 3 carries the discrimination.**

### 5. What is deliberately not built

- **The re-arm path.** [ADR-0038](0038-stop-the-line-without-ending-the-process.md) decision 5
  is untouched, `AwaitReArm` still refuses, and nothing gains a `SUCCESS` edge. Deciding what
  a station does with a part it is holding — put it down where, observed how, with the planner
  told what — is the decision that record refuses to take blind, and this one does not take it
  either.
- **Any recovery that re-enters the nominal branch below `AwaitTrigger`.** A station holding a
  piece could in principle resume at `PlaceAt` rather than at the trigger. That is a plausible
  fix and it is a different decision: it needs an answer to what happens when the place fails
  again, and it changes the shape of the station subtree rather than a precondition on it.
- **Any change to `recovery_policy.hpp`.** See decision 1.

## Consequences

### What this gets us

- A recoverable fault stops turning into a dead, silent line. The station that cannot proceed
  says so, in the field a consumer reads, and the coordinator is still there to be asked.
- The failure this project has the most evidence for acquires a rule that closes it at the
  point of decision rather than a report that describes it afterwards.
- ADR-0039's table-fed blind spot is closed for this shape, by a fact that needs no belt —
  which is what that record's correction said would be needed and deliberately did not choose.
- One fact, two consumers, one author: the tree refuses on it and the report publishes it.

### What this costs us

- **A station's timeout now stops the line deliberately instead of accidentally.** That is the
  central cost and it must not be presented as a pure win. Today two of three stations go on
  working for the rest of the leg; after this they are halted by the `Parallel` the moment the
  first one escalates. What makes it acceptable is that the line was already going to die and
  that nothing downstream of a stopped `station_transfer_1` has work coming.
- **This is a state machine and not a protective measure**, exactly as ADR-0037, ADR-0038 and
  ADR-0039 say of theirs. What stops an arm is the vendor controller's torque limiting and the
  cell's physical guarding (charter §3.2). Nothing here is safer; it is diagnosable.
- **A registry/runtime disagreement silences the report.** The predicate is a conjunction, so
  a station whose runtime names a piece the registry does not think it owns is reported as
  nothing at all. The failure is in the safe direction — silence rather than a false alarm —
  and it is a blind spot all the same. Whether such a disagreement should be a report of its
  own is a separate question and is not taken here.
- **A blocked station is not a resumable one.** After decision 1 fires, the ADR-0037 reset
  clears the station's state and `AwaitReArm` still refuses, so the line does not restart. The
  operator gets a diagnosis and a part in a gripper, not a running line.
- **`continuous_line` will fail faster and on a different assertion.** Runs that used to spend
  420 s and accuse a milestone will now stop on a `BLOCKED` or `STALLED` state within a
  publication period. That is the intent, and it means the scenario's own timing figures are
  not comparable across this change.
- **Two of the three CI failures would have become explicit failures rather than late ones.**
  Neither would have passed. Nobody should read this record as making the line more likely to
  complete a cycle.

### What we will have to revisit

- **When the re-arm path exists**, decision 1's escalation becomes the wrong answer for the
  cases that path covers, and the refusal narrows to the cases it does not.
- **When a station may hold more than one work-piece**, condition 2 of the predicate stops
  being a corroboration of condition 3 and needs restating. Every station is capacity-1 today
  and `TakeCustody` fails loudly if it owns more than one (`line_nodes.hpp:532-539`).
- **When something publishes `ConveyorState`**, ADR-0039's rule reads a measured speed instead
  of a commanded one; this rule is unaffected, because custody is not a plant measurement.
- **If the same dead end is ever reached with the arm empty and the beam clear**, neither
  ADR-0038's door nor this one describes it, and it needs its own record rather than a widened
  predicate here.

## How the claims here were verified

In the style of [`toolchain.md`](../reference/toolchain.md). Everything was checked on
**2026-08-29** against the worktree at `b8a6c10` unless stated.

| Claim | How | Result |
|---|---|---|
| The recover branch is `RecoverFromFailure`, `ReleaseStationClaims`, `MoveToHome`, and a completed recovery re-enters at `AwaitTrigger` | Read `trees/line_station.xml:46-62`, `:248-263` | Exact. `Repeat[Fallback[nominal, recover]]`; the nominal branch begins at `AwaitTrigger` (`:57`) |
| `RETRY_SAME` sets `STATE_WAITING` and returns SUCCESS; `ESCALATE` sets `STATE_BLOCKED` and returns FAILURE | Read `line_nodes.hpp:1073-1099` | Exact. `RecoverFromFailure` is the sole writer of `STATE_BLOCKED` on this path |
| `TIMEOUT` maps to `RETRY_SAME` | Read `recovery_policy.hpp:140-142` | Exact, sharing a branch with `EXECUTION_FAILED` |
| `TriggerWatch::take` needs an edge and discards the rest | Read `line_nodes.hpp:127-144` | Exact. The loop pops each event and returns one only if `event.state == state && event.previous_state != event.state`; every other event is popped and dropped |
| A station triggers on the beam breaking | Read `line_plan.hpp:311` | `trigger_detection_state = DetectionEvent::STATE_BLOCKED` |
| `station_transfer_1` is table-fed and `station_transfer_3` is belt-fed | Read `cite_generated/topology/cell_a_flow.yaml:63-66` | `station_infeed → station_transfer_1` carries `via: null`; `station_transfer_2 → station_transfer_3` carries `via: conveyor_2` |
| `beam_pick` does not index | Read `model/assets/instances/sensors.yaml` | Stated in the instance's own comment: *"It does NOT index. A table is not driven, so there is nothing to stop"* |
| `untriggerable_reason` returns `nullopt` with no inbound belt, so `stalled_stations` cannot report a table-fed station | Read `line_nodes.hpp:265-291` and `line_maintenance.hpp:131-159` | Exact. The empty-`inbound_belt` test is the function's first statement at `:269` |
| A line with nothing faulted, blocked, stalled or working publishes `STATE_RUNNING` | Read `line_maintenance.hpp:221-253` | Exact, and the stall branch is asked only when nothing is faulted or blocked |
| Custody survives a retry | Read `line_nodes.hpp:519-562` (`TakeCustody`), `:868` (`CompleteHandoff`), `:957-993` (`SetStationState`), `:1040-1101` (`RecoverFromFailure`) | `current_workpiece_id` is written by `TakeCustody` only and cleared by `CompleteHandoff` only. Neither the state write nor the recovery touches it |
| `buffer_occupancy` is registry ownership | Read `line_maintenance.hpp:207-208` and `workpiece_registry.hpp:195-210` | `occupancy(station)` counts the records whose `owner_station_id` is that station |
| **`buffer_occupancy > 0` alone is reached in a healthy cycle** | Read `line_nodes.hpp:851-859` and the nominal branch | **It is.** `CompleteHandoff` moves ownership to the receiving station while the piece is `IN_TRANSIT`; that station is `WAITING` until it arrives. A predicate on occupancy alone would fire on every transfer |
| The `WORKING` window spans `TakeCustody` to `CompleteHandoff` | Read `line_station.xml:62`, `:90`, `:110`, `:147` | `SetStationState state="2"` at `:62`, `TakeCustody` `:90`, `CompleteHandoff` `:110`, `SetStationState state="0"` `:147`, all inside the nominal `<Sequence>` |
| A re-arm would drop the part | Read `skill_server.cpp:937-944` | `Pick` opens the gripper before approaching, with the stated collision reason. Cited from ADR-0038 and re-read because decision 5 rests on it |
| `LineState.stall_reasons` documents itself as naming a belt | Read `cite_interfaces/msg/LineState.msg` | *"each naming the station and the belt that would have carried work to it"*. That sentence narrows under decision 3 |
| The scenario fails fast on `BLOCKED`, `FAULTED` and `STALLED`, and the leg ceiling is 420 s | Read `tests/scenarios/continuous_line.py:125`, `:458` | `LEG_CEILING_S = 420.0`; `STOPPED_STATES` is those three |
| `lifted` is a measured milestone, so the grasp held | Read `continuous_line.py:659-667` | `sample.z - frame_z > LIFTED_M`. It is computed from the piece's pose, not reported by the arm |
| The parked pose is the arm's home region and not the pick table | Read `model/assets/instances/fixtures.yaml` (`pedestal_1` at `(0.000, -0.300, 0.000)`, `table_pick` at `(-0.475, 0.000, 0.000)`), `model/assets/types/fixtures/pedestal_600.yaml` (0.600 m tall), `model/assets/instances/arms.yaml` (`arm_1` on `pedestal_1/top`, yaw +90 degrees) | The observed x is within 1 mm of the arm's base x and 474 mm from the table's; the observed z is 0.601 m above the arm's base. **This is a geometric consistency check, not forward kinematics** — no joint solution was computed for this record |
| The three CI runs, their milestone ladder, the parked poses and the last `LineState` | **Not re-derived.** Read from [CLAUDE.md §2](../../CLAUDE.md) and the project owner's investigation | **Reported, not measured here.** Six CI runs at six commits, no thresholds registered in advance, no `docs/measurements/` directory |
| The 0.341 s contrast at `station_transfer_3` | **Not re-measured.** Taken from the investigation | **Reported, not measured here.** One local run. What is checkable — that the station is belt-fed and therefore inside ADR-0039's rule — was checked above |
| That decision 1 or decision 2 closes the failure | **Not verified. Nothing here is built** | **Unverified.** What would show it is a `continuous_line` run on a CI runner in which this failure occurs and the line reports it. A run in which it does not occur shows nothing |
