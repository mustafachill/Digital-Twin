# cite_twin

**L5 — the twin boundary.** One process per zone, one ROS context per side, and the only
component in the running system with endpoints in both domains
([ADR-0044](../../../docs/adr/0044-one-ros-domain-per-side-identical-names.md) clause 3).
Anything else that observes both sides is a defect.

What it is and what it refuses is [ADR-0050](../../../docs/adr/0050-what-crosses-the-twin-boundary.md);
what the layer owns is [L5](../../../docs/architecture/L5-twin-synchronization.md). Neither is
restated here (P1).

## Status, stated before anything else

- **It has never run against a pair.** The shipped model declares `twin: {sides: single}`,
  and [ADR-0049](../../../docs/adr/0049-measure-the-real-time-floor-as-capacity.md) decision 4
  keeps it there — so `twin_boundary.py` **refuses to start on a clean checkout**, saying that
  the zone declares no counterpart. Its launch test drives it against a plan fabricated in
  memory from the generated one.
- **Nothing starts it.** It is not in `simulation.launch.py`, not in `./scripts/sim`, and not
  in any scenario. A solo bring-up is exactly what it was before this package existed.
- **No goal has crossed the boundary in any automated test**, and none can today: `launch_test`
  puts the launch inside the test process, which holds one context on one domain, so two sides
  cannot be included in one (CLAUDE.md §2). What is evidenced is the routing decision, the mode
  decision and the conjunction — each by a test — and not the crossing.
- **`valid` is false in every sample this package can produce**, and that is the intended
  behaviour. See below.

## What it does

### 1. The mode server

`SetMode` on `/cite/twin/set_mode`, `TwinMode` latched on `/cite/twin/mode`, both on the
**plant's** domain, because that is the side the operator is on (ADR-0044 clause 5). The names
are constants on the contracts, so each is written once.

A transition that places physical actuation under an authority that was not previously
commanding it calls `cite_bringup.plan.require_hardware_opt_in` — **the same check bring-up
applies, at the transition rather than only at bring-up**, which is what `SetMode.srv`'s header
commits this server to. `force` cannot skip it. Which transitions those are is
[`cross-cutting-safety.md`](../../../docs/architecture/cross-cutting-safety.md)'s list and not a
second one.

**What that is not: the safety layer.** It is one refusal in one server. A transition this
server permits is not thereby supervised.

**The transition is atomic**, because a mode never instantiates anything (ADR-0050 decision 4,
ADR-0047 clause 2): nothing is started, nothing is waited for, and
`TwinMode.transition_in_progress` is false in every message this layer publishes.

### 2. Command routing

One L5 action server per arm per skill, under `/cite/twin/<zone>/<asset>/<skill>`, derived from
the plan's own generated name by adding the reserved scope. In the modes whose row in ADR-0050
decision 2's table has a goal crossing — `VALIDATED` and `VIRTUAL_LEAD` — **the goal is
dispatched to each side's own L3 action server, on that side's own domain, unchanged.** Nothing
below L3 ever crosses: no trajectory, no joint command, no controller setpoint, and `/clock`
never crosses in any mode.

**Both sides then plan the goal independently**, through their own `move_group`.
[ADR-0027](../../../docs/adr/0027-pilz-planning-pipeline.md) establishes that an identical
request returns a byte-identical trajectory *from one `move_group`* and records that *same seed,
same trajectory across runs* is **not** established. **So an operator watching the near side is
not, on present evidence, watching the path the far arm will take** — only the endpoint it will
reach. That needs planner determinism, which is a separate decision; nothing here should be read
as saying the two paths agree.

### 3. The divergence monitor

One `DivergenceMetrics` per asset on `/cite/twin/divergence`, `asset_id` never empty — there is
no facility-level divergence number.

**`valid` cannot be true today, by construction.** It is a conjunction of five terms (ADR-0050
decision 3), and term 3 is each side's accumulated clock deficit over the window, measured and
within a bound [ADR-0049](../../../docs/adr/0049-measure-the-real-time-floor-as-capacity.md)
decision 1 deliberately leaves unset — and nothing in the tree measures it. A term with no
instrument makes the conjunction false, so the gate is arithmetic rather than a warning in prose.

So the monitor **publishes self-describing invalid samples rather than nothing**: the six
comparison fields are zeroed by the message's own rule, and the condition terms are not, because
they are how a reader learns which conjunct failed. `test_divergence.py` asserts that `valid` is
false *for that named term* rather than merely that it is false, so a change which makes it true
has to confront why.

**Do not make `valid` true by weakening a term.** If the conjunction turns out to be
unsatisfiable in a way ADR-0050 did not anticipate, that is a finding to report.

### What is NOT computed

`tcp_position_error_m`, `tcp_orientation_error_rad`, `cycle_time_deviation_s` and
`event_timing_deviation_s` are zero in every sample because **nothing here computes them**. The
first two need a tool pose per side, which needs one TF buffer per side (ADR-0050 clause 1c) and
forward kinematics; the last two need L4 line state from both sides. Their zero is
indistinguishable from the zeroing rule's zero while `valid` is false for every sample — which
is every sample today — and stops being so the moment term 3 gains an instrument.

## No fidelity claim, ever

**No number this package produces is a fidelity result and none may be published as one (P8).**
`valid` does not mean "true of reality"; it means the arithmetic was defined and its terms were
measured in this window. Whether a defined number could be a fidelity number is the separate
predicate `far_side_physical`, and in Phase 2.A its answer is always **no**: both sides run the
same L0 model, the same generated description, the same controllers and the same solver, so what
is being compared is a thing with itself. A 2.A divergence plot is a test of the instrument, and
anyone presenting one must label it as one
([ADR-0041](../../../docs/adr/0041-virtual-counterpart-is-a-second-full-simulation.md)).

## How to run it

It needs a zone that declares a counterpart, which the shipped model does not:

```bash
./scripts/enter dev ros2 run cite_twin twin_boundary.py
```

On a clean checkout that exits 2 with `zone 'cell_a' declares no side named 'counterpart'`.
Pairing a zone is an L0 change — `twin: {sides: pair}` on the zone, then
`./scripts/validate-model --write` and `./scripts/build` — and not something bring-up or this
package may invent (ADR-0041 Decision 3).

`--plan <path>` exists so a test can drive L5 against a paired plan without editing L0. Nothing
but a test passes it.

## Design notes worth knowing before editing

- **Which context a call is on is the whole of this package's difficulty.** Every publisher,
  subscription, service and action client is created through a `SideContext`, so the question is
  answered by which object the call went through. ADR-0044's cost list says L5 concentrates that
  class of defect in one place; spreading `Context` objects around would give the mitigation away.
- **`use_sim_time` is refused.** L5 holds two contexts whose simulated clocks are independent and
  separate without bound, so there is no one simulated clock to honour, and ADR-0050 pairs two
  operands on the wall clock for that reason. Every other node in this system honours it; this
  one cannot, and refuses to start rather than ignoring it.
- **This package does not use `cite_runtime`'s `init`/`spin`/`shutdown`.** That module's own
  adoption rule bars a process that commands an actuator from absorbing SIGINT, and this one
  dispatches goals that move arms. It imports from it only the one constant that module
  documents as the single place it is written down.
- **The executor is multi-threaded and the callback group is reentrant, deliberately.** The
  operator's goal is dispatched and then waited on inside a callback; on a single-threaded
  executor the wait for the plant's own goal would deadlock against itself.
- **No deadline on a far-side goal.** [ADR-0045](../../../docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md)
  records what a wall-clock deadline supervising a simulation-time process cost this project, and
  L5 has two simulated clocks to be wrong about rather than one. The operator's cancel is the
  bound, and it reaches every side. The one bounded wait is for a server to appear, which is a
  graph event.
- **One name here is written by hand and the plan does not carry it:** `joint_states`, the
  interface an arm's joint state arrives on. It is `joint_state_broadcaster`'s own topic, formed
  upstream. The namespace it hangs under is read off the plan rather than composed; what would
  close the residual is the plan carrying the topic, which is generator work.
