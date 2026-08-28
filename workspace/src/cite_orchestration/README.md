# cite_orchestration

L4: behaviour trees and line coordination. This layer decides **what happens next**. It never
plans a trajectory and never commands a controller — every leaf that moves anything calls an
L3 skill as a ROS 2 action, and nothing else. That separation is what lets an arm be swapped
without touching orchestration (P9).

Trees rather than hand-written state machines
([ADR-0007](../../../docs/adr/0007-behaviour-trees-for-orchestration.md)), from three failed
v1 attempts: state machines make asynchronous operations, cancellation and recovery awkward
enough that developers route around them, and offer no runtime introspection that would
reveal it.

**It is not a safety mechanism.** L2's limits and collision checking prevent collisions; this
prevents deadlock and thrash, which is a throughput property. Confusing the two is how a
coordination bug becomes an injury, and it is written down in `resource_arbiter.hpp` for that
reason.

## What is here

Two executables and one hand-written station tree.

| Executable | What it runs |
|---|---|
| `line_orchestrator` | **the line.** Reads `LineTopology`, derives a plan, generates a root tree with one subtree of `trees/line_station.xml` per station, and ticks it |
| `line_coordinator` | **one station in isolation**, from `trees/station_cycle.xml` and parameters. What `./scripts/scenario pick_and_place` drives |

**There is no station name and no station count in any source file here.** Adding a fourth arm
changes `model/`. `line_plan.hpp` turns `LineTopology` into what the line needs; `line_tree.hpp`
assembles the root tree from that plan, because BT.CPP's XML has no loop and cannot express
"one of these per station". What a station *does* stays a file a person reads and reviews.

The rules the line is made of are headers, so that they can be tested without standing up a
cell:

| Header | The rule it holds |
|---|---|
| `workpiece_registry.hpp` | one owner per work-piece, transferred atomically. The single place an owner is recorded |
| `handoff_ledger.hpp` | the ADR-0024 protocol: token, two-party confirmation, timeout with a defined outcome |
| `resource_arbiter.hpp` | who may use a shared thing. FIFO fairness; deadlock prevented by acquiring in sorted order, not by timeout |
| `recovery_policy.hpp` | what the line does about a failure, chosen from `ResultCode.code` and never from text |
| `conveyor_index.hpp` | the belt setpoint and its owner (ADR-0032) |
| `line_plan.hpp` | topology to plan, including every refusal |
| `line_tree.hpp` | plan to root tree |
| `skill_nodes.hpp` | the leaves that call L3 |
| `line_nodes.hpp` | the leaves that do not — triggers, custody, claims, handoff, recovery |
| `line_maintenance.hpp` | expiring handoffs, confirming for a sink, counting arrivals, publishing `LineState`, and reporting a station that **cannot be triggered** (ADR-0039). It writes **no** station state (ADR-0038 decision 4) |
| `line_fault.hpp` | what the line does once it has stopped (ADR-0038): the four fault leaves and the two rules they are derived from |
| `station_reset.hpp` | the operator reset's preconditions and its one effect (ADR-0037) |

## Interfaces

| Name | Type | Direction | Profile |
|---|---|---|---|
| `LineTopology::TOPIC` | `cite_interfaces/LineTopology` | in | `LATCHED` |
| `LineState::TOPIC` (default) | `cite_interfaces/LineState` | out | `STATE` |
| each station's `trigger_topic` | `cite_interfaces/DetectionEvent` | in | `EVENT` |
| each conveyor's `command_topic` | `std_msgs/Float64`, m/s | out | — |
| the five per-arm skill actions, and the zone's `Detect` | `cite_interfaces` actions | called | — |
| `ResetStation::Request::SERVICE` (default) | `cite_interfaces/ResetStation` | served | — |

**Every action name arrives as a parameter**, as parallel arrays lined up by asset, and so do
the belts. The shape is deliberate: the alternative — declaring `skills.<asset>.pick` once the
topology has arrived — reads better in a launch file and hides a whole class of mistake,
because a parameter whose name nothing checks is silently absent when it is misspelled. Here a
mismatched length is refused at start-up with both lengths named. `cell_a_plan.yaml` carries a
`skills:` block per arm, so those names are generated rather than written by whoever launches
the node.

`Detect` is the exception: there is one server for the zone, so every asset is given the same
action name. That is one name read once, not one name in three places.

## The operator reset (ADR-0037)

`Recovery::ESCALATE` sets a station to `STATE_BLOCKED` and logs that it "needs an operator".
Until ADR-0037 that operator had no control at all: this package contained no `create_service`
call, and the only exit was restarting the process. `ResetStation` is that control.

**Reset is not start.** Clearing the block returns the station to `STATE_WAITING` — awaiting
its own trigger — and that is the whole effect. It does not plan, does not send a `MoveTo`
goal, does not drive the arm home and does not resume a belt. If the arm has to be cleared out
of the way first, that is a separate deliberate action. **None of this is a protective
measure**; it removes an automatic resumption. What stops an arm remains the vendor
controller's torque limiting and physical guarding (charter §3.2).

It refuses more often than it accepts, and the refusals carry a `ResultCode` rather than a bare
`false`, because "there was nothing to reset" and "this station is faulted and you may not"
want opposite next actions:

| Request | Answer |
|---|---|
| a station this line does not have | `PRECONDITION_FAILED`. `LineContext::station` is `operator[]`, so trusting the map would invent a phantom station and report success |
| a station that is `IDLE`, `WAITING` or `WORKING` | `PRECONDITION_FAILED`. Accepting it would make this a general "make it go" button |
| a station that is `FAULTED`, or any station while any is faulted | `HARDWARE_FAULT`. One faulted station is a faulted line, and `STOP_LINE` is set only by the two codes that mean the cell cannot be commanded at all. Clearing `STATE_FAULTED` is out of scope |
| a station that is `BLOCKED` | accepted; `SUCCESS`, and the response carries the reason it cleared |

**The response is the only place the reason survives.** `LineState` is volatile and says of
itself that it is "a periodic report of the present, not a record"; `StationState` has no
reason field; and `LineMaintenance` publishes only the *first* blocked station's reason, so
with two blocked stations one is already unpublished. The server also logs the cleared reason
at `WARN`.

**Threading.** Everything else that touches `StationRuntime` runs on the tick thread. A service
callback does not, so it is the package's first cross-thread writer: the handler takes a mutex
the tick loop holds across a whole tick, so a reset lands *between* ticks, and the service is
given its own callback group so that waiting on it cannot sit in front of the trigger
subscriptions that tell stations a part has arrived.

**It is reachable in production now, and it was not when it shipped.** This paragraph used to
say the opposite, and every clause of it: that a station's escalation ended the tick loop, so
the process ended at the moment the reset became relevant, and that making the line survive one
station's escalation was a change ADR-0037 did not decide and did not make. ADR-0038 decided it
and the fault branch below makes it — the coordinator stays up and goes on serving
`ResetStation` after a station has escalated, which is the window this service never had.
`test_line_nodes`'s `TheResetIsAcceptedAndTheLineStillDoesNotRestart` drives that path through
the shipped tree.

**Accepting a reset is still not restarting the line.** The station returns to `STATE_WAITING`
and the line stays on the fault branch, because `AwaitReArm` asks the different question and
refuses. See below.

## The fault branch (ADR-0038)

A station that escalates fails the root `Parallel` at `failure_count="1"`. That was the end of
the process: the tick loop stopped, `line_orchestrator` returned 1, and `simulation.launch.py`'s
`_fatal_on_exit` tore the whole cell down with it — the arm's pose, the part's position, the
planning scene and the reset service, all inside seconds of the fault that produced them.

The root tree is now a plain `Fallback` over that **unchanged** `Parallel` and a fault
`Sequence`, generated in `line_tree.hpp` and implemented in `line_fault.hpp`:

```
Fallback  "line"
├── Parallel "stations"  success_count="-1" failure_count="1"    <-- unchanged
└── Sequence "fault"
    └── OnFault → StopAll → AwaitReset → AwaitReArm
```

| Leaf | What it does |
|---|---|
| `OnFault` | records. Latches the station, its `ResultCode`, its reason and the time, and abandons every live handoff so a clock left running through the fault cannot expire during it. Writes no station state, releases no claim, commands nothing |
| `StopAll` | commands every declared belt to zero — `ConveyorIndex::stop()`'s first production caller |
| `AwaitReset` | `RUNNING` while any station is `BLOCKED` or `FAULTED`. The same predicate the reset's own precondition uses. No deadline, deliberately: waiting for a person must not have one |
| `AwaitReArm` | asks whether any station could ever be triggered again, and refuses with the station and the belt named. Derived from the plan and the last commanded setpoint, so it names nothing in code |

**No leaf in it returns `FAILURE`, and none may.** A `FAILURE` fails the `Sequence`, fails the
`Fallback`, ends the tick loop, and reinstates the exit this removed. Refusals are logged. Nor
may one throw: an exception out of a `tick()` is `std::terminate` out of `main`, which is worse
than the exit — so the tick loop catches, halts the tree, and exits 1 rather than aborting.
Whether the coordinator should *survive* an exception is not decided anywhere and is not
decided here.

**None of it is a protective measure.** What stops an arm is the vendor controller's torque
limiting and the cell's physical guarding (charter §3.2). This is a state machine; what it buys
is that the coordinator is still there to be asked a question, and that it stops commanding
belts it has stopped supervising.

**A latched fault still exits 1**, so a run in which the line stopped still fails, and it exits
1 whether or not a station classified why — a root failure nothing classified is latched too,
because it is the one way left for the line to stop with the coordinator reporting nothing
wrong.

**The line does not resume, and that absence is a decision.** `AwaitReArm` has no `SUCCESS`
edge and the root has no `<Repeat>`. Every recovery this line has returns a station to a state
nothing can trigger it out of — the part is either still breaking the beam, which produces no
edge, or already off the belt that is now stopped. The `SUCCESS` edge and the `<Repeat>` land
together when re-arming is built, and not before (ADR-0038 decision 5).

## The stall detector (ADR-0039)

`AwaitReArm` asks whether a station could ever be triggered again, and it asks **only after
the line has already stopped**. `LineMaintenance` now asks the same question of a line that has
*not* stopped, so the condition is visible while the line is still notionally running.

That is not a hypothetical. A work-piece that fails its grasp is retried onto a beam the part
is already breaking, so no edge can ever arrive; the belt that would bring another part was
stopped by that same edge and is started again only by `ResumeBelt`, reachable only after the
trigger that will not come. Until this existed, a line in that state published `STATE_RUNNING`
for ever — the third time this repository has shipped "the system reported it was doing the
thing and the thing was not happening".

`LineState` gains `STATE_STALLED` and `stall_reasons` for it. **`STATE_BLOCKED` keeps exactly
one author** (ADR-0038 decision 4): a stall ranks strictly below it, and a blocked line
publishes no stall reasons.

**The rule is `untriggerable_reason` in `line_nodes.hpp`, and it is the same one `AwaitReArm`
uses**, so the two paths cannot answer differently and neither names an asset. Three conditions
are added on this path, and the last is the whole of the negative direction:

- the station is `IDLE` or `WAITING` — a `WORKING` station will reach `ResumeBelt` itself;
- its inbound belt is at a commanded standstill, or was never commanded;
- **it has already consumed every edge that stopped that belt.** The belt and the station learn
  of an arrival through two separate subscriptions to one topic, dispatched independently, so
  the first two conditions hold for a real interval of *every* normal arrival.
  `ConveyorIndex::stop_edges` and `TriggerWatch::consumed` are what separate an arrival in
  flight from a station that will wait for ever.

**It is a detector and it commands nothing.** No belt is restarted, nothing is planned, no
gripper is touched, no station state is written. The belt restart is the fix this must not be
read as being one line away from: the retry's first physical act is `Pick` opening the gripper
at the home pose, dropping a part nothing has attached as an `AttachedCollisionObject`.
**A visible stall is not a fixed stall.**

**`StopAll` states an intent it cannot confirm.** Nothing publishes `ConveyorState`, so no belt
answers. When something does, `StopAll` becomes a `StatefulActionNode` that runs until every
belt's *measured* speed is zero — an event, not a duration.

## Indexing the belt (ADR-0032)

A station cannot pick from a running belt, and the beam that starts it leaves no margin at all:
it sits a short distance **downstream** of the pick point, derived from the work-piece's own
length (ADR-0033), so a part breaks it at the instant the part's centre reaches the point it
must stop on. Every further metre of belt is displacement, against a pick-and-place cycle of
roughly two minutes. The distance and the arithmetic are in `conveyor_index.hpp` and are not
repeated here; `test_indexed_belts.py` reads the number out of that header and checks it
against the generated frames. So the belt is **indexed**: it stops when the station it feeds is
triggered, and runs again when that station reports `CompleteHandoff`.

The two ends are not symmetric, and that is load-bearing. The **stop** is bound to the sensor
edge itself, in `conveyor_index.hpp`, not to a leaf: a leaf acts only when its station's cycle
reaches it, and a work-piece that arrives while the station is still placing the previous one
would ride the length of the belt and off the end. The **restart** is a statement about one
station's own cycle, made at the one point where it is true, so it is the `ResumeBelt` leaf and
is read off the XML.

Which belt is never named in this package. It is the `via_asset_id` of the inbound edge of a
station with a robot actor; the command topic and the speed arrive as parameters resolved from
L0.

**The belts are commanded open-loop, and nothing here would notice a belt that did not obey.**
`cite_interfaces/ConveyorState` exists to make commanded and measured speed disagree visibly
and **is published by nothing at this commit**; the bridge carries a bare `std_msgs/Float64`
each way. A belt that fails to stop is a spilling line and a belt that fails to restart is a
stalled one. ADR-0032 records that cost; closing it needs a `ConveyorState` publisher in the
simulation plugin and on the hardware drive, which is L1/L2 work.

## What it deliberately does not do

- **It does not command a controller or plan a trajectory.** Ever.
- **It does not build a name.** See above.
- **It does not use the blackboard as a global store.** A BT.CPP v4 subtree gets its own
  blackboard and sees only what is remapped into it, so a station's work-piece, token and
  detected pose are private by construction rather than by discipline. "Blackboard used as a
  global store — untraceable coupling between subtrees" is a named L4 failure mode.
- **It does not retry generically.** `recovery_policy.hpp` reads `ResultCode.code` and nothing
  else; `ResultCode.detail` is prose for a person and nothing may parse it. A generic retry
  loop is not a recovery policy — it is a way of failing repeatedly at speed.
- **It does not abandon a goal without cancelling it.** Returning FAILURE while a goal is still
  executing is not giving up; it is losing track of a moving arm, and because a skill server
  admits one goal at a time the recovery branch's next goal is then *rejected* while the
  abandoned one still runs. That made the recovery branch unreachable for a reason that
  appeared in no file.
- **It does not run a direct arm-to-arm handoff** — see below.

## The direct-handoff refusal

`plan_line` refuses, at plan time and with the reason attached, any outbound edge whose
receiving station has a robot actor and whose `via_asset_id` is empty. Conveyor-mediated edges
are permitted. Today's topology contains no direct edge, so nothing is lost by refusing; the
day one appears, this is what says why it cannot run.

**Read [ADR-0031](../../../docs/adr/0031-refuse-direct-handoff-without-orientation-certainty.md)'s
correction section before writing or changing anything about either case.** Both halves of the
decision stand and the justification for both was wrong:

* Nothing re-observes the part. `Detect` reports occupancy, not position, and
  `Detection.pose` is now explicitly unobserved.
* What makes the *permitted* conveyor case safe is the **receiving gripper closing on a free
  part** — jaws square a part up as they close. A direct handoff denies exactly that, because a
  part clamped by the giving gripper cannot rotate into alignment with the receiving one. The
  mechanism that rescues one case is the one the other forbids.
* The published grasp residual — up to 18.71° — is a **roll about the pad-to-pad axis, not a
  yaw**. The yaw figure is 10.62°, from a different campaign. The cam-out arithmetic in the
  ADR's Context is a function of yaw and was applied to an angle that is not one.
* That new ground is fragile: the squaring-up is a rigid-body contact result with no friction
  declared on the pads, and the campaign names it as the largest sim/real divergence risk on
  its books. Phase 2 must re-measure it before any handoff is built on it.

**Two stale claims in this package, at this commit, both about that refusal.** The refusal
string in `line_plan.hpp` still carries the pre-correction reasoning and speaks of a part
"whose yaw is unknown to ±18.7°" — the axis is wrong. And the `DetectAt` comment in
`trees/line_station.xml` says the leaf gives "where the part actually is, including its yaw",
which no detector in this cell does; `skill_nodes.hpp`'s `PickAt` documents the opposite and
falls back to the station's L0 frame, which is the normal path. Not fixed here; documentation
does not edit code.

## How to run it

The line coordinator is **off unless asked for**, because it takes exclusive hold of each arm's
skills — a scenario, an operator or a diagnostic would find its goals refused by a server
already serving the line.

```bash
./scripts/sim --headless line:=true     # the line
./scripts/scenario continuous_line      # the three-arm sensor-driven line, headless
./scripts/scenario pick_and_place       # one station, through line_coordinator
```

Both scenarios run in CI as `continue-on-error` at this commit. **Do not read either as a green
gate.** CLAUDE.md §2 carries the measured counts and the open failures, and they are not
restated here.

## How it fails

| Symptom | Cause |
|---|---|
| the node refuses at start-up naming missing parameters | they describe which station this is and what it calls, and they come from the model rather than this node's initiative |
| the node refuses naming two array lengths | the parallel arrays disagree. Caught at start-up rather than as an off-by-one at run time |
| the plan is refused with a reason attached | `line_plan.hpp` cannot run this topology correctly. A plan with any refusal is not run at all — a line missing a station is not a smaller line |
| the line runs backwards, or a station never fires | flow order is derived by topological sort of the edges, never from the topology's array order (in `cell_a_flow.yaml` the sink is listed first) |
| every leaf sits at RUNNING for ever | nothing is spinning the node. The leaves are `StatefulActionNode`s that poll and never spin; the executor thread in `main` is what makes them progress |
| a station waits for a trigger that never comes | the `LATCHED` topology or the `EVENT` trigger never arrived. A volatile publisher on either would connect silently and deliver nothing |
| the recovery branch fails every time | a leaf gave up without cancelling, so the next goal is rejected by a server still executing the old one |
| a belt is stopped for ever | nothing confirms a belt's state. See the open-loop note above |
| a station blocks and the line stops, but the process stays up | decided (ADR-0038). The fault branch holds; call `ResetStation`, and expect `AwaitReArm` to go on refusing afterwards |
| `LineState` reports `STATE_STALLED` and nothing escalated | a station was returned to a trigger nothing can produce and its inbound belt is stopped (ADR-0039). `stall_reasons` names the station and the belt. There is nothing for `ResetStation` to clear, and no re-arm path exists — read ADR-0038 decision 5 before restarting a belt by hand |
| the coordinator sits for ever after a reset, logging a refusal that names a station and a belt | `AwaitReArm`. Nothing re-arms a station yet; the refusal is the design saying so, not a bug to widen the gate around |
| the coordinator exits 1 having logged that no station said why | a station subtree returned `FAILURE` without its recovery policy classifying anything. `OnFault` latches it so the run still fails; the defect is in that subtree |
| a reset is refused with `HARDWARE_FAULT` on a station that is only blocked | some other station is faulted, which makes the line faulted |

## Tests

```bash
./scripts/test --packages-select cite_orchestration
```

| Test | What it proves |
|---|---|
| `test_line_logic` | the rules: single ownership, the two-party handoff and its timeout, buffer and reach arbitration, the recovery policy, and topology-to-plan-to-tree. Pure logic, no cell |
| `test_conveyor_index` | which edge stops which belt, and which belt is left alone — against a real publisher and a real subscription, with the setpoint read back off the command topic |
| `test_skill_goals` | what a leaf puts in a goal, read from the far side of the action. A leaf's whole job is turning ports into one typed goal, and `PickAt` once filled in a tool height where the action asks where the object is |
| `test_skill_cancellation` | what a leaf does to a **server** when it gives up. Driven against a real action server, because a mock would test the wrong side of the boundary |
| `test_line_nodes` | the same rules composed: a real tree, real in-process action servers and a real sensor publisher, driving two stations through a handoff — against the shipped `trees/line_station.xml`, read from the source tree rather than copied. It also drives the fault branch: that an escalation cancels a **sibling's** outstanding goal, that the root goes on returning `RUNNING`, that the belts are put down, that the reset is accepted and the line still does not restart, and that a root failure nothing classified is latched all the same. Its `StalledLine` fixture drives the ADR-0039 detector against a real beam, a real belt and the real `LineMaintenance`, read back off the `LineState` topic — including the two negative cases that keep it from being noise: an arrival still in flight, and a station working with its own belt held stopped |
| `test_detection_region.py` | the search region against the generated frames and topology |
| `test_indexed_belts.py` | that the generated topology and the generated bring-up plan name the same set of belts. A belt in one and not the other is a cell that refuses to come up, or a belt stopped for ever |
| `test_station_reset` | the operator reset's refusals, driven through the real `StationReset` handler: a faulted line refuses everything, an unblocked station is refused rather than quietly accepted, an unknown id invents no phantom station, and the cleared reason is captured before it is cleared |
| `test_recovery_ordering.py` | that `RecoverFromFailure` is the first leaf of the recovery branch and no motion leaf precedes it, read out of the shipped XML. A test of the final station state would pass with the leaves in either order. It reads the generated fault branch out of `line_tree.hpp` under the same `MOTION_LEAVES` set, and asserts the tick loop is guarded against a leaf that throws |

**These tests move no arm.** They use fake action servers that succeed because they are told
to, so what they prove is **sequence and ownership**, not motion. Motion is evidenced only by
the scenarios, and the honest status of those is in CLAUDE.md §2.
