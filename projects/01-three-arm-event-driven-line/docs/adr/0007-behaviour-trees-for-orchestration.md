# ADR-0007: Orchestrate with behaviour trees

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0006, `docs/architecture/L4-orchestration.md`, `docs/reference/literature.md`

## Context

The L4 layer sequences work: which station acts next, when an arm may enter a shared
workspace, how a handoff is negotiated, and what happens when any of it fails.

The v1 workspace attempted this three times with hand-written state machines. All three
failed, and instructively:

- `multi_robot_coordinator` had no exit transition from `MOVING_TO_PICK` — it dispatched a
  trajectory and never handled the result, so a robot entering that state stayed there.
  The state machine was deadlocked *by construction*, and reading the transition table did
  not make that obvious.
- `robot_interface` faked motion with timers because wiring real asynchronous action
  results into the transition table was harder than faking it.
- `handoff_coordinator` published commands to `/{robot}/handoff/execute`, which nothing
  subscribed to. Every transaction timed out. Nothing detected this.

The common cause is not carelessness. Hand-written state machines make asynchronous
operations, cancellation, and recovery awkward enough that developers route around them,
and they offer no runtime introspection that would surface the result.

This is also the ROS ecosystem's own conclusion: ROS 1 navigation orchestrated with
hierarchical state machines; ROS 2's Nav2 changed its primary customization mechanism to
behaviour trees.

## Options considered

### Option A — Hand-written state machines
What v1 did, three times. Rejected on the evidence above.

### Option B — A hierarchical state machine framework
Better structure than hand-rolled, with tooling. Genuinely viable, and the comparative
literature finds HFSMs and BTs comparable in expressive power. Rejected on the secondary
properties: recovery and fallback must be encoded explicitly as transitions, which is
where the combinatorics grow, and inspecting a running machine is weaker.

### Option C — Behaviour trees (BehaviorTree.CPP v4)
Chosen. Asynchronous actions are first-class and non-blocking. Reactive and concurrent
execution compose. Fallback and recovery are structural nodes rather than transition
explosion. Trees are XML, editable and visualizable in Groot2 without recompiling, and a
running tree can be inspected live.

## Decision

Orchestrate with **behaviour trees using BehaviorTree.CPP v4**, authored as XML and
inspected with Groot2. Trees call L3 skills as ROS 2 actions. Line topology comes from the
L0 facility model (ADR-0004); process logic lives in trees; nothing at L4 calls a
controller or a hardware interface directly.

## Consequences

### What this gets us
- A long-running action is a normal node, not an awkward special case — the failure that
  produced timer-faked motion in v1 does not arise.
- Recovery is expressed where it belongs. A fallback node is one node, not N extra
  transitions.
- A running tree is observable. "Which node is the system in, and why" is answerable live,
  which is precisely what v1 could not answer.
- Process changes are XML changes. Reordering a line does not mean recompiling.

### What this costs us
- A concept most contributors have not met. Behaviour trees invert the intuition of state
  machines, and tick semantics, node status propagation, and blackboard scoping all have
  to be learned before anyone is productive. Budget onboarding time for this.
- Blackboard state is easy to abuse into a global variable store. Requires review
  discipline.
- Deeply nested trees become hard to reason about, in the way deeply nested conditionals
  do. Keep trees shallow and factor subtrees per station.
- A C++ dependency in a layer that might otherwise have been Python.

### What we will have to revisit
If orchestration outgrows a single coordinator — for example, a facility-wide scheduler
across multiple cells — reconsider whether one tree should own everything, or whether each
cell runs its own tree under a higher-level planner. The layer boundary does not change;
the number of trees might.
