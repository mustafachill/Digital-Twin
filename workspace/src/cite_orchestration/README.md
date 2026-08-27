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
| `line_maintenance.hpp` | expiring handoffs, confirming for a sink, counting arrivals, publishing `LineState` |

## Interfaces

| Name | Type | Direction | Profile |
|---|---|---|---|
| `LineTopology::TOPIC` | `cite_interfaces/LineTopology` | in | `LATCHED` |
| `LineState::TOPIC` (default) | `cite_interfaces/LineState` | out | `STATE` |
| each station's `trigger_topic` | `cite_interfaces/DetectionEvent` | in | `EVENT` |
| each conveyor's `command_topic` | `std_msgs/Float64`, m/s | out | — |
| the five per-arm skill actions, and the zone's `Detect` | `cite_interfaces` actions | called | — |

**Every action name arrives as a parameter**, as parallel arrays lined up by asset, and so do
the belts. The shape is deliberate: the alternative — declaring `skills.<asset>.pick` once the
topology has arrived — reads better in a launch file and hides a whole class of mistake,
because a parameter whose name nothing checks is silently absent when it is misspelled. Here a
mismatched length is refused at start-up with both lengths named. `cell_a_plan.yaml` carries a
`skills:` block per arm, so those names are generated rather than written by whoever launches
the node.

`Detect` is the exception: there is one server for the zone, so every asset is given the same
action name. That is one name read once, not one name in three places.

## Indexing the belt (ADR-0032)

A station cannot pick from a running belt. The beam that starts a station sits a short distance
upstream of the point it picks from, and the work-piece leaves the belt's carry volume shortly
after — under a second at the declared belt speed, against a pick-and-place cycle of roughly
two minutes. The distances and the arithmetic are in `conveyor_index.hpp` and are not repeated
here. So the belt is **indexed**: it stops when the station it feeds is triggered, and runs
again when that station reports `CompleteHandoff`.

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
| `test_line_nodes` | the same rules composed: a real tree, real in-process action servers and a real sensor publisher, driving two stations through a handoff — against the shipped `trees/line_station.xml`, read from the source tree rather than copied |
| `test_detection_region.py` | the search region against the generated frames and topology |
| `test_indexed_belts.py` | that the generated topology and the generated bring-up plan name the same set of belts. A belt in one and not the other is a cell that refuses to come up, or a belt stopped for ever |

**These tests move no arm.** They use fake action servers that succeed because they are told
to, so what they prove is **sequence and ownership**, not motion. Motion is evidenced only by
the scenarios, and the honest status of those is in CLAUDE.md §2.
