# ADR-0038: Stop the line without ending the process, and gate resumption on re-armability

- **Status:** Proposed. Written before the implementation, which is the point
  ([CLAUDE.md §12](../../CLAUDE.md)). Every "will" below is a commitment, not a description.
  Nothing in this record is built at `c7557c8`.
- **Date:** 2026-08-27
- **Deciders:** Docs-writer agent, from an architect's audit of the L4 fault path at
  `c7557c8` after [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md) landed
- **Related:** [ADR-0007](0007-behaviour-trees-for-orchestration.md),
  [ADR-0010](0010-typed-ros-interfaces.md),
  [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0032](0032-index-the-belt.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md) (**amended by this
  change** — see "The amendment ADR-0037 is owed" below),
  [L4](../architecture/L4-orchestration.md),
  [cross-cutting-safety.md](../architecture/cross-cutting-safety.md),
  charter §3.2 and §4 (P2, P4, P5, P7)

## The decision, in one line

A station's escalation stops the line **and the coordinator stays alive**, serving the
reset — and resumption is gated on **re-armability**, not on acknowledgement.

## Nothing here is a protective measure, and it must never be described as one

This is a state machine. What stops an arm is the vendor controller's torque limiting and
physical guarding (charter §3.2), exactly as ADR-0036 and ADR-0037 say of their own
mechanisms. A coordinator that survives a fault is not safer in any certifiable sense; it is
**diagnosable**, and it stops commanding belts it has stopped supervising. Both of those are
coordination properties.

## Context

### What is true today, read from source at `c7557c8`

- The root tree the orchestrator generates is a bare `Parallel`
  (`line_tree.hpp:226-233`). **None of `EmergencyHandling`, `OnFault`, `StopAll` or
  `AwaitReset` exists anywhere in the repository**, though the design at
  [`L4-orchestration.md:104-113`](../architecture/L4-orchestration.md) draws all four. A
  grep for those four identifiers over `workspace/` and `tools/` on 2026-08-27 returned
  exactly one hit, and it is a comment: `line_station.xml:209`.
- `Recovery::ESCALATE` sets `STATE_BLOCKED` and returns `BT::NodeStatus::FAILURE`
  (`line_nodes.hpp:914-919`); `Recovery::STOP_LINE` sets `STATE_FAULTED` and returns
  `FAILURE` (`:921-925`). Either fails the root `Parallel` at `failure_count="1"`, the tick
  loop's `outcome` stops being `RUNNING`, the loop ends, `tree.haltTree()` runs, and the
  process returns 1 (`line_orchestrator.cpp:575-608`).
- **The coordinator's exit tears down the whole cell.** `simulation.launch.py:844` wires
  `on_exit=_fatal_on_exit("the line coordinator")`, and `_fatal_on_exit`
  (`simulation.launch.py:1078-1095`) returns `[LogInfo(...), Shutdown(reason=...)]` for any
  non-zero return code outside a shutdown already in progress. Gazebo, `move_group`, the
  three skill servers, the detection server and the bridge all go with it.
- **`ConveyorIndex::stop()` has no caller in production code.** It is defined at
  `conveyor_index.hpp:235`; the only callers in the tree are
  `test_conveyor_index.cpp:253` and `:321`. The belt stop that the line actually performs is
  `command(asset, 0.0)` inside `on_edge` (`conveyor_index.hpp:266`), bound to the sensor
  edge.
- **A line whose stations are all `WAITING` publishes `STATE_RUNNING`**
  (`line_maintenance.hpp:111-118`). The `else` branch is reached whenever no station is
  faulted, blocked or working, and its comment reasons about idleness — which is correct for
  idleness and is also what a permanently stalled line would report.
- `Pick` **opens the gripper before approaching** (`skill_server.cpp:937-940`), for the
  stated reason that arriving with a closed gripper is a collision the planner cannot see.
- `AwaitTrigger` **consumes** the edge (`line_nodes.hpp:125-141`: the event is popped from
  the queue), and both it (`:136`) and `ConveyorIndex::on_edge` (`:258`) require
  `previous_state != state`. A station triggers on the beam **breaking**
  (`line_plan.hpp:311`, `trigger_detection_state = DetectionEvent::STATE_BLOCKED`), not on
  it clearing.
- `ResumeBelt` is reachable only after `CompleteHandoff`, itself reachable only after the
  trigger: `line_station.xml:57` (`AwaitTrigger`), `:110` (`CompleteHandoff`), `:141`
  (`ResumeBelt`), all inside one `<Sequence name="nominal">`.

### The defect is not availability. It is that a fault erases its own evidence

The availability statement is the obvious one and it is the less important one. When a
station escalates today, the process exits 1, `_fatal_on_exit` shuts the launch down, and
with it go the arm's pose, the part's position, the planning scene, `move_group`'s world and
every node that could be asked a question. **The state a person would need in order to say
why the station stopped is destroyed within seconds of it stopping**, by the same event.

[ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md) decision 5 quotes Universal
Robots' Product Alert of 24 September 2019 on automatic acknowledgement *masking* the faults
that predict a failure, and adds: *"Restarting the process — today's only recourse — does
exactly that, just more slowly."* This record makes the sharper form of that observation:
today the process does not wait to be restarted. **The fault restarts it.**

ADR-0037 shipped a typed per-station reset (`station_reset.hpp`) whose whole purpose is that
a person examines a blocked station and clears it deliberately. There is no window in which
to call it. The service exists and the process that serves it is already gone.

### What a stopped line does to a belt is not the same in simulation and on hardware

This is the P2 consequence, and it is the reason `StopAll` is not optional.

In simulation the belts stop by accident. The coordinator exits, `_fatal_on_exit` shuts the
launch down, Gazebo dies, and there is no belt left to run. Nothing decided that; the
simulator's death did.

On a physical line the belt is a VFD taking a speed setpoint. **A setpoint persists.** The
coordinator exits, nothing publishes zero, and three belts keep running with no station
taking work off them and nobody supervising them. Identical command path — a
`std_msgs/Float64` on the same topic name (ADR-0032) — divergent consequence. The simulated
behaviour is not evidence about the real one, and today the simulated behaviour is the only
one anybody has seen.

### The re-arm problem, which is why this record exists at all

Every recovery this line has — the retry path and the operator reset alike — returns a
station to a state from which **nothing can ever trigger it again**. Two cases, and they are
exhaustive:

- **Failed before picking.** The part is standing at the pick point, still breaking the beam.
  A station triggers on the breaking edge (`line_plan.hpp:311`) and `AwaitTrigger` requires
  `previous_state != state` (`line_nodes.hpp:136`), so a part that is already there produces
  no edge. The belt that would bring another part is stopped, and the only thing that runs it
  again is `ResumeBelt` at `line_station.xml:141` — reachable only after `CompleteHandoff`,
  reachable only after the trigger that will not come.
- **Failed after picking.** The beam cleared when the part came off the belt, and a clearing
  edge is not this station's trigger. The belt is still stopped. The next part never arrives.

Closed loop either way, and closed by the same two facts. **A station returned to `WAITING`
is a station that will wait for ever.**

Now put that next to `line_maintenance.hpp:111-118`. A line of stations all in `WAITING`
publishes `STATE_RUNNING`. So a change that stopped the process from exiting, restored the
nominal branch after a reset, and stopped there would convert **a process that exits 1** into
**a process that reports a healthy running line, for ever**.

**This repository has paid for that exact class of failure twice.**

1. v1's handoff. *"Its coordinator published handoff commands to a topic nothing subscribed
   to, every transaction timed out forever, and no test noticed"*
   ([ADR-0024](0024-handoff-split-between-l3-and-l4.md), Context).
2. The belt setpoint, 2026-08-26 to 2026-08-27. The publishers were created in the topology
   callback and the start-up command was published from that same callback, before any
   subscriber had matched — *"so a reliable profile delivered it to nobody and a test harness
   was starting the belts"* ([`L4-orchestration.md:27-32`](../architecture/L4-orchestration.md),
   and the 2026-08-27 correction on [ADR-0032](0032-index-the-belt.md), which is where the
   measurement lives and is not restated here).

Both are the same shape: **the system reported that it was doing the thing, and the thing was
not happening.** A third instance is what this design is shaped to avoid, and the shape is
the fourth leaf below.

### The load-bearing external claim, and its status

The cancellation argument in this record — and the one already written in prose at
`line_tree.hpp:215-221` with no test behind it — rests on two properties of
BehaviorTree.CPP v4:

1. a `ParallelNode` halts its running children **before** returning `FAILURE`; and
2. a plain `Fallback` does not re-tick a child that has failed.

The architect who audited this could not read BT.CPP's source from their host and recorded
both as unverified. **They were read for this record, from the released source, and both
hold** — see the verification table. That does not discharge the obligation: nothing in this
repository *asserts* either one, so an upstream change would break the line's cancellation
guarantee silently. **The implementation owes a test for it**, and that obligation is part of
this decision (decision 6).

## Options considered

### Option A — Leave it: exit 1, let the launch tear the cell down, restart

The status quo. It is genuinely defensible on one ground: a coordinator that has stopped
commanding is a coordinator that cannot command anything wrong, and a full restart is a known
state.

Rejected on two grounds, neither of which is availability. It destroys the diagnosis
(above), and on hardware it leaves the belts running (above). It also strands
`station_reset.hpp`, shipped one commit earlier, with no reachable caller — an interface that
exists and cannot be used is worse than one that does not exist, because it reads as a
capability.

### Option B — Catch the failure in `line_orchestrator.cpp` and keep spinning outside the tree

Do not touch the tree. When `tickOnce()` returns `FAILURE`, stop ticking, keep the node
alive, keep the executor spinning so the reset service answers.

Genuinely plausible, and the smallest diff. Rejected because it puts the line's fault
behaviour in C++ where the design puts it in the tree, and because "stop ticking" is not a
decision about the plant: the belts would still be at their last setpoint, and there would be
no place to express `StopAll`, no place to express what makes resumption legal, and nothing
Groot2 could show. [ADR-0007](0007-behaviour-trees-for-orchestration.md) chose trees
precisely so that recovery is inspectable rather than buried in the tick loop, and this is
the branch that most needs to be inspectable.

### Option C — Reset returns the line to the nominal branch

The obvious shape, and the one a reader will propose. `Fallback[ stations, Sequence[StopAll,
AwaitReset] ]` under a `Repeat`, so that a successful reset re-enters the stations.

**Rejected, and the reason is the whole record.** The re-arm problem above means the
re-entered stations all sit in `AwaitTrigger` for ever, and `line_maintenance.hpp:111-118`
publishes that as `STATE_RUNNING`. This option is exactly the third instance of the failure
class named above, and it is the option that looks most like progress.

### Option D — Fix the stall first, then make the line survive

"Make the belt restart on the recovery path, so the line is not stalled, and then the reset
can safely resume."

Rejected, and recorded because the ordering intuition is strong and wrong. See decision 5.

### Option E — Stop the line inside the tree, and gate resumption on re-armability

Chosen. Detailed below.

## Decision

### 1. The line stops and the process lives

The generated root tree becomes a `Fallback` whose **first** child is the existing
`Parallel` of station subtrees, unchanged, and whose **second** child is a fault `Sequence`.

```
Fallback  "line"
├── Parallel "stations"  success_count="-1" failure_count="1"   <-- unchanged
│   └── one <SubTree ID="LineStation"> per station
└── Sequence "fault"
    ├── StopAll
    ├── AwaitReset
    └── AwaitReArm
```

A station's `FAILURE` still fails the `Parallel` at `failure_count="1"`. The `Fallback` then
advances to the fault `Sequence` and — this is the property the shape turns on —
**never returns to the `Parallel`**, because `FallbackNode` carries `current_child_idx_`
across ticks and resets it only on `SUCCESS`, on exhausting every child, or on `halt()`
(`fallback_node.cpp:54-57`, `:85-90`, `:96-101`). The stations stay stopped for as long as
the fault branch runs.

**The fault branch never returns `FAILURE`.** `AwaitReset` and `AwaitReArm` are
`StatefulActionNode`s that return `RUNNING` while their condition is unmet. This is not a
style choice: a `FAILURE` there fails the `Sequence`, fails the `Fallback` — both children
having failed — makes the root's `outcome` `FAILURE`, ends the tick loop, and reinstates the
exact process exit this record removes. The refusal is **logged**, not returned.

The failure therefore no longer reaches a process exit, nor — through `_fatal_on_exit` — the
cell's teardown. The arm stays where it stopped, the part stays where it is, the planning
scene stays loaded, and the reset service stays answerable.

`line_orchestrator.cpp:602-608` keeps its `status = 1` on a root `FAILURE`. It becomes
unreachable through escalation and stays as the answer for a root that fails some other way.

**`OnFault` from the design diagram is deliberately not built.** The `Parallel` returning
`FAILURE` *is* the fault event; a separate condition leaf would have to observe the same
station states the tree has just acted on, and would be a second author for the fact that a
station escalated. The diagram at
[`L4-orchestration.md:104-113`](../architecture/L4-orchestration.md) is the design; this is
the shape to build, and the difference is one node.

### 2. What "the line has stopped" means, actuator by actuator

**Arms: nothing new is done, and that is the point.** Every station subtree that was
`RUNNING` is halted by the `Parallel` itself — `parallel_node.cpp:122-128` calls
`resetChildren()` before returning `FAILURE`, and `ControlNode::resetChildren()`
(`control_node.cpp:38-48`) calls `haltNode()` on every child whose status is `RUNNING`. That
reaches `SkillNode::onHalted` (`skill_nodes.hpp:514`, `:661`, `:721`, `:866`, `:951`), which
calls `halt_goal()` and cancels the outstanding action goal. **This is a property of
`failure_count="1"` being reached, not of the process exiting**, so it is preserved exactly
by not touching the `Parallel`.

**Belts: `StopAll` commands every declared belt to zero.** L4 owns the setpoint
([ADR-0032](0032-index-the-belt.md)), so L4 is the layer that must put it down. `StopAll`
iterates `ConveyorIndex::assets()` and calls `stop()` on each — which gives
`conveyor_index.hpp:235` its first production caller — and returns `SUCCESS` once.

**Nothing else is touched and nothing new is commanded.** No arm is driven home, no gripper
is opened, no claim is released, no station state is written. The station that escalated is
already `STATE_BLOCKED`; the stations that were halted keep whatever state they held.

**`StopAll` is open loop and cannot confirm itself.** Nothing publishes `ConveyorState`; the
bridge carries a bare `std_msgs/Float64` each way, and `conveyor_index.hpp:57-65` says so of
itself. So `StopAll` states an intent and returns `SUCCESS` without evidence that any belt
slowed. **The condition under which that changes is named here so it is not re-derived:
when something publishes `ConveyorState`, `StopAll` becomes a `StatefulActionNode` that
returns `RUNNING` until every belt's measured speed has reached zero, and `SUCCESS` when it
has.** That is an event, not a duration — P4 is not satisfied by waiting a plausible number
of seconds for a belt to coast.

### 3. Resumption is gated on re-armability, not on acknowledgement

This is the heart of the record.

`AwaitReset` clears when no station is `STATE_BLOCKED`. That is acknowledgement: a person
looked, and used the ADR-0037 service. It says nothing about whether the line can run.

`AwaitReArm` is the fourth leaf and it answers the different question: **is there a station
that could ever be triggered again?** Its refusal is **derived from the plan and the belts,
not hard-coded**:

> For every station that has a trigger topic and an inbound belt, if that belt's last
> commanded setpoint is zero, the line cannot be re-armed. Refuse, naming the station and
> the belt.

Both halves are already data. `LinePlan`'s station record carries `trigger_topic` and
`inbound_via_asset_id` (`line_tree.hpp:186` renders the latter as the `inbound_belt`
attribute), and `ConveyorIndex` already records what each belt was last commanded to, in
`commanded_` (`conveyor_index.hpp:346-350`, whose own comment calls it *"this class's whole
state about the plant"*). The one thing missing is a public reader for it; `commanded_` is
private and no accessor exists at `c7557c8`. Adding one is the whole mechanism.

**Today it always refuses, and it refuses for a reason rather than by construction.**
`StopAll` has just commanded every belt to zero, so every belt-fed station's inbound belt
reads zero. `model/topology/flow.yaml` gives `station_transfer_2` an inbound
`conveyor_1` and `station_transfer_3` an inbound `conveyor_2`, so two stations match the rule
today; `station_transfer_1` is fed by a table (`via: null`) and is skipped, which is the rule
working rather than an exception to it.

**It commands nothing, ever.** It reads a plan and a setpoint record and returns `RUNNING`.
It is a condition wearing an action's clothes because it has to hold the branch open.

**It clears itself.** The day someone builds a path that re-arms a station — a belt restart
that does not put a part on the floor, an operator jog that clears the pick point, a
re-observation that lets a station start from where the part actually is — this leaf stops
refusing on its own, because the setpoint it reads will not be zero. Nothing has to remember
to delete it. That is the property that makes it worth writing rather than leaving a
comment.

### 4. `STATE_BLOCKED` gets exactly one producer: the tree

Today it has two. `RecoverFromFailure` writes it from inside the station subtree
(`line_nodes.hpp:915`), and `LineMaintenance::expire_handoffs` writes it from the maintenance
pass, without failing the tree (`line_maintenance.hpp:130-143`). **The maintenance pass stops
writing it.** The handoff expiry keeps its outcome — the upstream station retains the
work-piece, structurally, because nothing touches the registry (ADR-0024 rule 3) — and the
expiry becomes a fact the station's own tree observes and acts on, so that the station's state
has one author.

That is wrong twice today, and one of the two is live at `c7557c8`:

- **Live now.** The expiry window is opened by `OfferHandoff` (`line_station.xml:104`;
  `handoff_ledger.hpp:163` sets `deadline = now + timeout`, default 120 s from
  `line_orchestrator.cpp:325`) and closed by `CompleteHandoff` (`:110`). `PlaceAt` (`:108`)
  sits between them. So a station can be reported `STATE_BLOCKED` **while its arm is
  placing** — and `station_reset.hpp:150-161` tests only `state != STATE_BLOCKED`, so the
  reset service will **accept** a reset for it, and `:169` clears `blocked_reason` as its
  first act, mid-motion. Nothing about that requires the change in this record; it is true at
  `c7557c8`.
- **Introduced by this record if left alone.** `AwaitReset` keys on the same state. A handoff
  clock still running through the fault will expire during the fault and re-block a station
  the operator has already reset, so the fault branch would never advance and the operator
  would see no reason why.

A station's state is owned by its tree. A second writer for a value with one meaning is the
same defect as a value in two places (P1, P5).

### 5. What is deliberately not built: the resumption edge

Two things are absent on purpose, and their absence is a decision rather than an oversight:

- **`AwaitReArm` returning `SUCCESS`.** No condition in the tree today can make it pass.
- **A `<Repeat num_cycles="-1">` wrapping the `Fallback`.** Without it, a fault `Sequence`
  that ever returned `SUCCESS` would make the `Fallback` return `SUCCESS`
  (`fallback_node.cpp:54-57`), end the tick loop with `outcome == SUCCESS`, and exit the
  coordinator quietly with status 0. With it, the `Fallback` restarts at
  `current_child_idx_ = 0` — the stations — which is the resumption.

**The `Repeat` is two lines and it is the *last* two lines**, so that the tree's shape does
not change a second time. Whoever wires resumption adds them and does not touch anything
else.

**Why the obvious ordering is wrong**, because a reader will reach for it. The obvious order
is: make the line survive, notice it stalls, fix the stall. Fixing the stall is not one
thing. It is the belt, the trigger, the part that may still be in the gripper, and the
planner's view of the payload, all at once — and the cheap-looking version of it drops the
part.

Concretely: put `ResumeBelt` on the recovery path so the line is not stalled. The retry
begins with `MoveToHome`, carrying whatever the arm is holding. A new part arrives on the
now-running belt, the trigger fires, the cycle reaches `PickAt` — and `Pick`'s first physical
act is to open the gripper (`skill_server.cpp:937-940`), at the home pose, with the previous
part still in it. Nothing catches it: `cite_skills` never attaches an
`AttachedCollisionObject` (a grep of that package on 2026-08-27 found no occurrence), and
`ADR-0029` removed the simulation-side attachment, so friction alone is holding it. The tree
already refuses the adjacent version of this for a different reason —
`line_nodes.hpp:751-755`: *"If it failed before picking, the piece is still at the beam and
running the belt would carry it off the end."*

There is a second reason not to wire resumption blind, found while checking the first:
`TriggerWatch`'s subscription is never torn down and its queue persists across a halt
(`line_nodes.hpp:99-116`, bounded at 64). An edge that arrives during a fault is still
pending when the branch resumes. Whoever builds resumption must decide what happens to it.

So the re-arm decision is written **before** resumption is wired, and the leaf that refuses
is in the tree before anything can pass it.

### 6. The implementation owes a test for the BT.CPP behaviour the argument rests on

Both properties in "The load-bearing external claim" were read from source for this record
and both hold at 4.9.1, the version Jazzy releases. Neither is asserted anywhere in this
repository, and the entire cancellation guarantee — *"a line that stops leaves no arm moving
under a goal nobody is holding"*, `line_tree.hpp:215-221` — depends on both. A test against
the shipped tree that drives a station to `FAILURE` and asserts that a sibling's outstanding
goal was cancelled, and that the `Parallel` is not re-entered, is part of this change.

## Consequences

### What this gets us

- A fault stops being the thing that destroys the evidence of the fault. The arm, the part
  and the scene survive it, which is the precondition for anyone diagnosing anything.
- The ADR-0037 reset gets a window in which it can be called. Today it has none.
- The belts are put down by a decision rather than by the simulator dying, so the sim and
  hardware paths do the same thing (P2) instead of appearing to.
- `ConveyorIndex::stop()` acquires its first production caller, closing a gap where a
  function existed and only tests used it.
- `STATE_BLOCKED` gets one author, and a live defect — a reset accepted for a station whose
  arm is placing — is closed with it.
- The stall is stated, in the tree, by a leaf that names the station and the belt, instead of
  being invisible behind a line reporting `STATE_RUNNING`.

### What this costs us

- **The line now stalls visibly instead of exiting, and a stall is not obviously better.**
  A stopped coordinator is unmistakable; a coordinator sitting in `AwaitReArm` for ever needs
  someone to read `LineState` or the log to know it is not working. What makes this
  acceptable is that the refusal is logged with the station and the belt named, and that the
  alternative — Option C — reports `STATE_RUNNING`. What would make it unacceptable is
  `AwaitReArm` refusing silently, so it must not.
- **CI scenarios that end when the coordinator ends have to change.** No scenario asserts the
  exit code 1 at `c7557c8` (checked across `tests/scenarios/`), so nothing breaks today, but
  a scenario written to fail a station and wait for the process is no longer possible.
  Assertions move to `LineState` and to the log.
- **`StopAll` asserts a standstill it cannot observe.** It is honest about that here and in
  its own comment, and it stays that way until something publishes `ConveyorState`. Until
  then a belt that ignores the zero is a spilling line that L4 still does not notice — this
  record narrows that gap by one command; it does not close it.
- **Three new leaves, and a fourth kind of node.** `StopAll` is an action, `AwaitReset` and
  `AwaitReArm` are `StatefulActionNode`s that can return `RUNNING` for ever. A leaf that never
  terminates is a shape this tree has not had at the root before, and it makes "the tree is
  RUNNING" stop meaning "the line is running".
- **A public reader on `ConveyorIndex::commanded_`.** A small widening of a class that has so
  far kept its plant state to itself, and one more consumer to consider whenever the
  publication path changes.
- **Moving `expire_handoffs` out of the state-writing business is not a one-line change.**
  The expiry has to become something a station's own tree observes, which means a leaf or a
  port that does not exist, and the existing tests for the expiry outcome move with it.
- **The re-arm gate will be read as an obstacle.** It refuses in every run, including runs
  where a person believes they have fixed the thing by hand. Whoever finds it in their way is
  meant to build the re-arm path rather than widen the gate, and this record is the only
  thing that says so.

### What we will have to revisit

- **When a re-arm path exists**, `AwaitReArm` stops refusing on its own and the `Repeat`
  goes in. That is decision 5's other half and it is a new task, not a widening of this one.
- **When something publishes `ConveyorState`**, `StopAll` becomes stateful and confirms
  itself, and the honest description of it in decision 2 is deleted rather than softened.
- **Whether `AwaitReset` should key on something other than `STATE_BLOCKED`** once decision 4
  has given that state one author. If a second producer is ever wanted, the gate needs a
  different signal, not a second meaning.
- **Whether the fault branch should be per-station rather than line-wide.** This record stops
  the whole line on one station's escalation, which is what the tree does today and what
  ADR-0037's claim decision assumes. Graceful degradation is a different decision and it owes
  a replacement rule — see the amendment below.
- **If BT.CPP's `FallbackNode` or `ParallelNode` semantics change upstream**, decision 6's
  test is what says so. Pin the observed version in the test's own record.

## The amendment ADR-0037 is owed

ADR-0037's correction 3 decides that an escalating station **keeps its claims**. That
decision survives this record unchanged, and the premise it rests on is preserved on purpose:
the `Parallel` still fails, still halts every sibling, and `StopAll` then takes the belts to
zero, so nothing runs alongside a blocked station.

What does not survive is the *wording*. Correction 3 justifies the decision by citing the
mechanism this record changes — *"its `FAILURE` fails the root `Parallel` today, and
`L4-orchestration.md`'s designed `OnFault → StopAll → AwaitReset` stops it deliberately"* —
and once the fault branch is built, that forward reference stops being a promise and becomes
a description of something that exists. The amendment is recorded on ADR-0037 itself and
reads:

> An escalating station keeps its claims because **the line stops around it** — the fault
> branch holds every station and every belt — so the claim record stays true to where the arm
> is standing, and starves nobody.

**And the conditional, because it is what a future contributor will trip on.** If the line is
ever allowed to keep other stations running past a block, **the decision does not survive.**
There is one `ResourceArbiter`, stations share reach frames, and `Grant::QUEUED` is
deliberately not a failure — `resource_arbiter.hpp:64-66` says *"A leaf that sees this
returns RUNNING"*, and `line_nodes.hpp:452-454` implements exactly that. So a neighbour
asking for a frame an escalated station is still holding would wait **silently and for
ever**. Whoever proposes graceful degradation owes a replacement rule for what a blocked
station does with its claims.

`line_station.xml:206-210` carries the pre-amendment wording verbatim. That is a code change
and belongs with the implementation, not with this record.

## How the claims here were verified

In the style of [`toolchain.md`](../reference/toolchain.md). Everything was checked on
**2026-08-27** against the worktree at `c7557c8` unless stated.

| Claim | How | Result |
|---|---|---|
| The root tree is a bare `Parallel` | Read `line_tree.hpp:226-233` | Exact. `success_count="-1" failure_count="1"`, station subtrees and nothing else |
| `EmergencyHandling`, `OnFault`, `StopAll`, `AwaitReset` exist nowhere | Grepped all four over `workspace/` and `tools/` | One hit, a comment: `line_station.xml:209` |
| `ESCALATE` → `STATE_BLOCKED` + `FAILURE`; `STOP_LINE` → `STATE_FAULTED` + `FAILURE` | Read `line_nodes.hpp:914-919`, `:921-925` | Exact |
| The tick loop ends on a non-`RUNNING` outcome, halts the tree, returns 1 | Read `line_orchestrator.cpp:575-608` | Exact. `haltTree()` at `:599`, `status = 1` at `:607` |
| The coordinator's exit tears down the cell | Read `simulation.launch.py` | `on_exit=_fatal_on_exit("the line coordinator")` is at **`:844`**, not `:843` as briefed. `_fatal_on_exit` at `:1078-1095` returns `[LogInfo, Shutdown]` for any non-zero code outside a shutdown |
| `ConveyorIndex::stop()` has no production caller | Read `conveyor_index.hpp`; grepped the package | Defined `:235`. Callers: `test_conveyor_index.cpp:253`, `:321` only. `on_edge` calls `command(asset, 0.0)` at `:266` |
| `ConveyorIndex` records the last commanded setpoint, with no public reader | Read `conveyor_index.hpp:318-350` and the public section `:153-248` | `commanded_[asset] = speed` at `:330`; member at `:350`; no accessor |
| All-`WAITING` publishes `STATE_RUNNING` | Read `line_maintenance.hpp:105-118` | Exact. The `else` at `:113-118` is reached when nothing is faulted, blocked or working |
| `expire_handoffs` writes `STATE_BLOCKED` from the maintenance pass | Read `line_maintenance.hpp:130-143`; read the call site `line_orchestrator.cpp:584` | Exact, and it does not affect the tree's status |
| The expiry window can span a `PlaceAt` | Read `handoff_ledger.hpp:163`, `line_orchestrator.cpp:325`, `line_station.xml:104/:108/:110` | Deadline set at `OfferHandoff`, default 120 s; `PlaceAt` lies between offer and completion |
| The reset accepts a station blocked mid-`PlaceAt` and destroys the reason | Read `station_reset.hpp:150-161`, `:169` | Tests only `state != STATE_BLOCKED`; `blocked_reason.clear()` before the state write |
| `STATE_BLOCKED` has two writers | Grepped the package for assignments | `line_nodes.hpp:915` and `line_maintenance.hpp:140` |
| `Pick` opens the gripper before approaching | Read `skill_server.cpp:937-940` | Exact, with the stated collision reason |
| `cite_skills` never attaches an `AttachedCollisionObject` | Grepped `cite_skills/src` and `include` for `AttachedCollisionObject`, `attachObject`, `attached_collision` | No occurrence. A survey of that package, not a proof about the system |
| `AwaitTrigger` consumes the edge; both it and `on_edge` need `previous_state != state` | Read `line_nodes.hpp:125-141`, `:252-263`; `conveyor_index.hpp:258` | Exact. `take` pops at `:135`, tests at `:136` |
| A station triggers on the beam breaking, not clearing | Read `line_plan.hpp:311` | `trigger_detection_state = DetectionEvent::STATE_BLOCKED` |
| `ResumeBelt` is reachable only after `CompleteHandoff`, itself only after the trigger | Read `line_station.xml:48-149` | `AwaitTrigger` `:57`, `CompleteHandoff` `:110`, `ResumeBelt` `:141`, one `<Sequence>` |
| `ResumeBelt` is kept off the recovery path deliberately | Read `line_nodes.hpp:751-755` | Exact; the stated reason is a work-piece carried off the belt end |
| `TriggerWatch`'s queue survives a halt | Read `line_nodes.hpp:87-116`, `:144` | Subscription is never torn down; queue bounded at `kMaxPending = 64` with the oldest dropped |
| Two stations are belt-fed, one is table-fed | Read `model/topology/flow.yaml`; `line_tree.hpp:181-186` | `conveyor_1` → `station_transfer_2`, `conveyor_2` → `station_transfer_3`; `station_transfer_1`'s inbound edge is `via: null` |
| `Grant::QUEUED` makes a leaf wait rather than fail | Read `resource_arbiter.hpp:58-71`; `line_nodes.hpp:443-454` | *"A leaf that sees this returns RUNNING"*; the leaf returns `RUNNING` |
| An escalating station's claims are kept; a halted sibling's are released | Read `line_station.xml:224-240`; `line_nodes.hpp:457-466` | `ReleaseStationClaims` is behind a leaf that fails on both refusing answers; `ClaimReach::onHalted` calls `release_all` |
| Jazzy releases BehaviorTree.CPP **4.9.1-1** | Fetched `ros/rosdistro` `master`, read `jazzy/distribution.yaml` `behaviortree_cpp_v4` | `version: 4.9.1-1`, package `behaviortree_cpp` — which is what `cite_orchestration/package.xml:24` depends on |
| `ParallelNode` halts its children before returning `FAILURE` | Fetched `BehaviorTree.CPP` tag `4.9.1`, read `src/controls/parallel_node.cpp:122-128` and `src/control_node.cpp:38-48` | **Verified.** `clear(); resetChildren(); return NodeStatus::FAILURE;`, and `resetChildren()` calls `haltNode()` on every `RUNNING` child. The architect recorded this as unverified; it holds |
| A plain `Fallback` does not re-tick a failed child | Fetched tag `4.9.1`, read `src/controls/fallback_node.cpp:31-101` | **Verified.** `FAILURE` increments `current_child_idx_` (`:59-60`); it is reset only on `SUCCESS` (`:56`), on exhausting all children (`:85-90`) or in `halt()` (`:98`) |
| `<Fallback>` is the synchronous `FallbackNode` | Fetched tag `4.9.1`, read `src/bt_factory.cpp:118-119` | `registerNodeType<FallbackNode>("Fallback")`; `AsyncFallback` is the separate registration |
| Nothing in this repository asserts either BT.CPP property | Grepped `workspace/` for the behaviour; read `line_tree.hpp:215-221` | Stated in prose only. Load-bearing and untested — decision 6 |
| No scenario asserts the coordinator's exit code 1 | Grepped `tests/scenarios/` for `returncode` | The hits are teardown checks and `gz` calls; none asserts an escalation exit |
| The two prior instances of "reports healthy, does nothing" | Read `0024-handoff-split-between-l3-and-l4.md:25-29`; `L4-orchestration.md:27-32` and `0032-index-the-belt.md:6` | Quoted verbatim from both |
| UR's Product Alert quotation and its date | Not re-fetched for this record | Taken from ADR-0037, which verified it against the UR Product Alert page and the SW5.21 service manual on 2026-08-27. Cited, not re-derived (P1) |
| Belt behaviour on a physical VFD | **Not verified.** No physical belt is connected to this project | **Unverified.** Reasoned from a speed setpoint being a held command rather than a stream. Settled by connecting a drive and observing what it does when the publisher stops |
| That the process surviving actually preserves the arm pose and the scene | **Not verified.** Nothing here is built | **Unverified.** It is a consequence of the launch not shutting down, and is what decision 6's test and the first implementation run are expected to show |
