# ADR-0058: Drive lifecycle transitions by request and confirmation, not by a volatile broadcast

- **Status:** Proposed — nothing in this record is implemented.
- **Date:** 2026-09-17
- **Deciders:** Project owner; drafted by the orchestrator against a root cause a `debugger`
  proved on 2026-09-17.
- **Related:** [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0034](0034-process-lifecycle-mechanism-in-cite-runtime.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md),
  **ADR-0057** (*on `feat/pair-boundary`, unmerged — deliberately not linked, because a
  link to a record this branch does not carry is a broken reference, not a citation*);
  `docs/architecture/cross-cutting-lifecycle.md`; `docs/open-work.md` #72; CLAUDE.md §10's first
  bullet and P4.

## Context

### The defect, and it is proven rather than suspected

`simulation.launch.py`'s `_managed` triggers activation on
`OnStateTransition(configuring → inactive)`. `launch_ros` derives that launch event from exactly
one thing: a **subscription** to `/<node>/transition_event`
(`launch_ros/utilities/lifecycle_event_manager.py`, `setup_lifecycle_manager`). Read off a live
stalled cell, both endpoints are **RELIABLE + VOLATILE**.

**Reliable is a promise to *matched* subscribers.** When the node's publisher has not yet matched
the launch node's subscription at the instant `on_configure` returns, the sample is dropped;
VOLATILE means it is never re-sent; the handler never fires; the node sits in `inactive` forever.
`wait_for_service` does not help — it gates on the `change_state` **service** endpoints, which are
a different pair discovered independently.

**This is CLAUDE.md §10's own first bullet**, the one that already cost this project a belt
setpoint that was never once delivered — this time inside `launch_ros`'s plumbing rather than
ours.

**The proof.** In a stalled trial the node was probed from outside and was in `inactive`, so
configure had succeeded. Driving `cleanup` then `configure` again from a third process 9.7 s later
made the launch's **same, still-registered** handler fire, and the node logged
`published 9 static transform(s)` immediately. Same process, same node, same transition —
delivered the second time, dropped the first.

**Not ours.** `_managed` is byte-identical to `main`'s; the stall reproduces with `zone:=cell_a`,
the configuration `main` ships, and in a three-node harness with no Gazebo, no MoveIt and nothing
zone-specific. Observed in **3 of 11** scenario launches and ~7 of ~92 harness trials — **one
host, counts, not a rate.**

### The sentence in the code that is false

`_managed`'s return comment says the handlers are registered before the transition is emitted
*"so a node that configures very quickly cannot reach `inactive` before anything is watching."*
Registration order in a launch description says nothing about when a DDS subscription matches.

`readiness_witness.py`'s `endpoints()` docstring carries the same assumption as fact, calling a
lifecycle transition a *"real completion event"*. It is the assumption this defect lives inside.

### The second half, which is separable and is why the damage is large

`_facility(plan)` is spliced into the action list with **nothing downstream gated on it**. So a
stalled `frame_server` does not stop bring-up; the chain runs on, and the first consumer to notice
is `move_group` ten seconds later, reporting `Tf has two or more unconnected trees` and
`Unknown frame: cite_world`. The launch then dies **blaming the model and the planning scene**.
That misdirection is the expensive part, and it is what `_managed`'s own docstring says the helper
exists to prevent — but all four of its handlers address a transition that *returns FAILURE*, and
a transition that succeeds and is never heard is covered by nothing.

### The constraint any answer must satisfy

P4 and CLAUDE.md §4 forbid sleeping for a guessed duration to sequence startup. **A ceiling whose
expiry is a failure naming what never answered is not that**, and the argument is already written
in this tree at `readiness_witness.py:84-106`: *"What makes it permitted is the ceiling, not the
interval… Nothing here proceeds because a timer elapsed."*

## Options considered

### Option A — keep the events, add a confirmation after them
Cheapest. Rejected: the four `_refuses` handlers ride the **same topic**, so a *failing*
transition is exactly as droppable as a succeeding one. Confirming a success while leaving the
failures on a lossy channel fixes the symptom that was observed and leaves the one that was not.

### Option B — drive the transitions by request, confirm with `get_state`
Chosen. Removes the class by construction: there is no event left to lose.

### Option C — only close the structural gap
Gate everything downstream of `_facility` on each node being observed `active`, and leave the
trigger alone. Rejected **as the whole answer** — it converts a ten-second misdirection into a
one-second accurate failure, which is worth having, but the cell still does not come up. It is
kept as a *consequence* of B rather than an alternative to it: B's driver exiting **is** that
gate.

### Option D — record it and move on
Rejected. It is a real bring-up defect on `main` that fires often enough to have hit three of
eleven scenario launches, and the next thing built on this launch is a twin pair — two copies of
the same graph, joined on tokens that depend on these transitions.

## Decision

**A short-lived lifecycle driver program in `cite_bringup` drives each managed node through
`configure` and `activate` by calling `change_state` and confirming with `get_state`, and the
launch gates everything downstream on its exit.**

Per node: `change_state(CONFIGURE)` → read the response → **confirm with `get_state`** →
`change_state(ACTIVATE)` → **confirm with `get_state`**. It exits 0 when every node is observed
`active`, and non-zero naming **the node and which step never answered**.

**The confirmation is the gate, not the response**, and that is the load-bearing choice: a reply
can be dropped exactly as a broadcast can — one observed run carries
`RuntimeWarning: failed to send response (timeout)` and
`Abandoning wait for the '…/change_state' service response`. `get_state` is idempotent and
re-askable, so asking again is free and correct.

**The shape is not new.** `cite_facility/planning_scene_loader.py` already does exactly this:
`wait_for_service` under a deadline → `call_async` + `spin_until_future_complete` → an explicit
*"never returned a result"* branch → then `_not_in_the_scene()`, a second read-only re-askable
query confirming the first took effect. It exists because `move_group` accepts and then silently
drops objects whose frame cannot resolve. The same relationship, one layer down.

**The three `LifecycleNode` actions stay and the four `_refuses` handlers keep their diagnoses.**
The driver replaces the event chain, not the nodes, and the refusals remain as a better-worded
answer on the occasions they do arrive. **Nothing relies on them.**

## Consequences

### What this gets us
- **The class is removed, not the instance.** No transition event is load-bearing any more, for
  success or for failure.
- **The misdirection goes.** Bring-up fails in about a second, naming the node and the step,
  instead of ten seconds later naming frames and the planning scene.
- **`_facility` stops being ungated**, which is the structural half, closed by the same change.

### What this costs us
- **A fourth program in `cite_bringup`**, its executable bit, its CMake install rule, and a place
  in the launch's gate chain. `test_every_installed_program_is_executable_in_the_tree` fails
  without the bit, and a program that cannot exec produces **no launch event at all**.
- **One more ceiling.** It must be on the **wall clock** — `time.monotonic`, `use_sim_time=False`
  — for the reason `readiness_witness.py`'s docstring gives: a deadline in a clock that never
  starts cannot expire.
- **A launch that is a little less declarative.** Sequencing moves from launch event handlers
  into a program. That is the trade: the handlers were declarative and lossy.
- **It does not make every participant a managed node.** `cross-cutting-lifecycle.md` records
  that the skill server and the line coordinator are plain nodes; this record does not change it.

### What we will have to revisit
- **If `launch_ros` ever exposes QoS on that subscription**, or makes the transition event
  durable, the event-driven form becomes safe and this becomes a choice rather than a repair.
- **When a node is added to `_facility`.** The driver must learn about it, and the node names
  live in `simulation.launch.py` with a second copy in `test_simulation_launch.py`'s `MANAGED`.
  A third copy would be the value-in-two-places §4 prohibits.

## The promotion condition

1. The harness that reproduces the stall today — 2 of 35 unloaded, 4 of 45 loaded — **stops
   reproducing it**, reported as counts on one host and **not as a rate**, because the
   before-figures are not one either.
2. A test drives the driver's failure path: a node that never answers `change_state`, and a node
   that answers but never reaches `active`, each producing a non-zero exit naming that node and
   that step.
3. `test_simulation_launch.py`'s existing lifecycle assertions still pass unchanged — the three
   `LifecycleNode` actions, and `activating → inactive` still producing no `EmitEvent`.
4. Nothing downstream of `_facility` starts until every managed node is observed `active`, driven
   by a test rather than described.
5. All three scenarios pass their cycle against `cell_b`, and `./scripts/sim --zone cell_a` still
   brings the showcase up.
6. No sleep sequences anything, and **no existing ceiling is widened.**

## Two corrections this record owes

- **`readiness_witness.py`'s `endpoints()` docstring** calls a lifecycle transition a *"real
  completion event"*. After this change it is one; until then the sentence is the false
  assumption the defect lives inside, and it should say so rather than be quietly made true.
- **`cross-cutting-lifecycle.md` says bring-up sequences on 7 registered event handlers**; the
  source has **6** `RegisterEventHandler(` call sites, several inside loops, so the runtime count
  depends on the plan. **Resolve it by counting, not by editing the prose to match** — and this
  change moves the number again.

## What this record does not decide

- **Whether the skill server and the line coordinator become managed nodes.**
  `cross-cutting-lifecycle.md` says the pattern remains binding on them; that is a separate
  change.
- **Anything about the twin pair.** ADR-0057 stands on top of this and is unaffected by which
  mechanism drives a side's transitions.
- **`docs/open-work.md` #69, #70 and #73.** Filed, measured, and not this record's.
