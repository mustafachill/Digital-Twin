# Safety and interlocks

- **Status:** `DESIGNED` — **the safety layer described here does not exist.** No node
  enforces any row of the table below, and the enforcement point in the diagram is not in
  the command path. Binding from the first line of Phase 2 code.
  Two things it relies on *are* enforced today, and nothing else.
  **First, a paired zone cannot reach a physical machine by any edit to L0**: the validator
  refuses a physical plant on a paired zone (`physical-plant-on-paired-zone`) and an asset whose
  two sides name different backends (`divergent-counterpart-backend`,
  [ADR-0048](../adr/0048-refuse-a-counterpart-the-generator-cannot-build.md) clause 1), both as
  ERRORs in `tools/cite_tools/validate/referential.py`, so such a model does not generate. That
  is a validate-time refusal, not a safety layer, and lifting it is Phase 2.B's work.
  **Second, nothing reaches a hardware backend without a deliberate opt-in.** `CITE_ALLOW_HARDWARE=1` is required by
  `require_explicit_hardware_opt_in` in `scripts/_lib.sh` for `./scripts/enter hardware`,
  and independently by `require_hardware_opt_in` in `cite_bringup/cite_bringup/plan.py` for
  any bring-up plan on which some (asset, side) **declares** that it reaches a physical
  machine. That refusal decides on a declared fact and not on the backend's id: L0 states
  `commands_physical_hardware` per backend, the generated plan carries it per (asset, side),
  and a physical backend is refused whatever it is called
  ([ADR-0054](../adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md)). Before ADR-0054
  it compared the id against the literal `sim`, and a type declaring the vendor's physical
  `ros2_control` plugin under that id passed the gate without it ever consulting the opt-in.
  Both are covered by tests.
  **That opt-in is not a guarantee about the cell, and this document is the last place that
  should read as though it were.** The refusal rests on a **self-declaration that nothing
  verifies**, and it fails in two directions rather than one: L0 can state `false` beside the
  vendor's physical plugin, and — the sharper one — L0 can be **entirely honest** and the
  loaded plugin still physical, because nothing checks that the plugin the model declares is
  the plugin the description loads. That second route needs no false statement at all, only an
  **omitted binding**, which is the omission this document forbids everywhere else. ADR-0054,
  linked above, carries both in its Correction of 2026-09-10; `../open-work.md` #65 carries the
  fix for the second and does not choose its shape. **State the rule with its residual or do
  not state it here** — this paragraph was corrected once already for stating a guarantee that
  no code provided.
  **The track is a motion path no planner checks.** A track step is one `JointTrajectory`
  point sent straight to the track's trajectory controller, forwarded to both sides by the
  twin boundary ([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md)); no
  planner checks a track move against the scene, so what bounds it is the controller's limits
  and, on hardware, the vendor's. The physical track's hardware path is not implemented: the
  track type declares a simulation backend only, so a physical track is refused by the
  validator.
  **What stops a physical arm is not in this repository.** The vendor controller's torque
  limiting and physical guarding stop an arm driving into something; the execution-side
  trajectory tolerances ([ADR-0036](../adr/0036-execution-side-trajectory-tolerances.md)) are a
  **detector** that reports a mistracked trajectory after the fact, and must never be cited as a
  protective measure.
  **Collision geometry is no safety margin.** The arms collide against derived convex hulls, and
  a hull adds no clearance — every gram it adds is inside a concavity — so hulls may never be
  cited as margin in a safety case; and enabling SDFormat `<self_collide>` under hulls would
  stall the simulated gripper at spawn, a P2 divergence the generator refuses to emit
  ([L1](L1-description-and-assets.md), [ADR-0028](../adr/0028-convex-hull-collision-meshes.md)).
- **Related:** [L2](L2-control-and-hal.md), [L5](L5-twin-synchronization.md), [`../operations/safety-procedures.md`](../operations/safety-procedures.md), [`../reference/standards.md`](../reference/standards.md)

## What this covers, and what it does not

> **This document covers software interlocks. It does not deliver functional safety.**

Certified safety for a physical robot cell is a hardware and process matter: a risk
assessment, a safety-rated controller, physical guarding, and certification against
ISO 10218-1/-2:2025. That is outside this repository (charter §3.2), and no amount
of careful software substitutes for it.

What this repository owns is the software layer: preventing our own code from commanding
something unsafe, and stopping promptly when told to. Both matter. Neither is sufficient
alone, and pretending otherwise is itself a hazard.

## The asymmetry that governs everything here

Simulation forgives every mistake. Hardware forgives none.

Because of [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), any code that
commands the simulated cell can be pointed at a physical arm by a one-line configuration
change. That is the project's central design principle and therefore its central safety
risk.

**Audit simulation-only code as if it were hardware code**, because one day it is. This is
why `safety-auditor` reviews motion paths in Phase 1, long before a real arm is connected.

## The enforcement point

```
   program client / operator
               │
        L5 twin boundary (one goal, both sides)
               │                      │
        L3 skills                     │  track and belt setpoints
               │                      │  (declared L5 → L2 routes,
        L2 MoveIt / controllers ◄─────┘   no planner on them)
               │
        ┌──────▼──────┐
        │ SAFETY      │  ◄── every command passes through, without exception
        │ LAYER       │
        └──────┬──────┘
               │
        hardware interface
               │
        ┌──────┴──────┐
        ▼             ▼
   simulation     physical arm
```

**No command reaches a hardware interface without traversing the safety layer.** A single
unguarded publisher defeats the entire design. `safety-auditor` traces every motion path
from origin to hardware interface for exactly this, and treats a bypass as Critical.

## What the safety layer enforces

| Check | Enforced at | Why both |
|---|---|---|
| Joint position limits | Planning **and** execution | A planner can be bypassed; a controller can be commanded directly |
| Velocity and acceleration limits | Planning **and** execution | Same |
| Effort limits | Execution | Planning cannot predict contact |
| Cartesian workspace bounds | Planning **and** execution | Covers jog, teach, servo, and replay — motions no planner generated |
| Keep-out zones | Planning **and** execution | Human workspace, fixtures |
| Collision objects present | Planning | A missing object is an invisible collision |
| Command freshness | Execution | Stale commands must not be re-executed |

**Enforcement at only one of planning or execution is a High finding.** The two catch
different failures, and the gap between them is exactly where an unexpected motion lives.

## E-stop

- Propagates to **every** actuator.
- Is **independent of the normal command path** — it must work when a node has hung, a
  queue is full, or an executor is blocked. A stop that travels the same route as the
  commands cannot stop a system whose command path is what failed.
- Has a **bounded, measured latency**, not an assumed one.
- Requires a **deliberate reset**. Automatic resumption after an unexplained fault is a
  Critical finding — the fault has not been diagnosed, and resuming re-runs whatever caused
  it.

## Watchdog and communication loss

When the commanding node dies, the network stalls, or messages simply stop, motion
**stops**. It does not continue on the last command. Every command path has a deadman with
a bounded timeout, and the timeout is documented rather than tuned until the symptom goes
away.

## Mode transitions

`SIM` → `REAL`, entry to `CLOSED_LOOP`, and entry to `VIRTUAL_LEAD` **against a real far
side** are the three most dangerous state changes in the system
([L5](L5-twin-synchronization.md)).

**The criterion this list is built on**, written down because a fourth candidate has to be
*judged* rather than found to resemble the other three: a transition belongs here when it
**places physical actuation under an authority that was not previously commanding it.**
`SIM` → `REAL` hands the physical arm to a command path that had been reaching only the
model. Entry to `CLOSED_LOOP` hands it to the virtual side, behind a validation gate. Entry
to `VIRTUAL_LEAD` hands it to the virtual side with nothing interposed — it is
`CLOSED_LOOP` minus the validation gate, aimed at the same arm
([ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 2).
The third entry is therefore on this list on the same criterion as the other two, and not
by analogy.

**THE LIST IS THREE EXAMPLES OF THE CRITERION AND HAS NEVER BEEN THE SET, and on
2026-08-31 the difference stopped being academic.** L5's mode server transcribed these
three into code, and `VALIDATED` — which dispatches an operator's goal to both sides by
byte-identical code to `VIRTUAL_LEAD`'s — is not among them. On a plan with a real far
side, `SetMode(VIRTUAL_LEAD)` was refused `SAFETY_BLOCKED` and `SetMode(VALIDATED)` was
accepted with no gate and no `force`, after which a goal reached the physical arm. A test
asserted that acceptance and passed.

**Apply the criterion; never transcribe the list.** Applying it needs two facts, and both
are already data: *which sides does this mode command*, which `TwinMode.msg` states per
mode and `cite_twin.routing.commanded_sides` reads, and *does any of those sides, for any
asset in scope, load something other than a simulation*, which the generated bring-up plan
states per (asset, side). Computed that way, the answer on a cell with one physical far
side is **every mode but `SIM`** — the three above, and `VALIDATED`, and `SHADOW`, whose
own definition in `TwinMode.msg` is *"physical commanded, virtual follows its state"* and
which this list never asked about. A seventh mode is decided by the same two questions on
the day it is added.

**And on a cell with no physical side, no mode is gated.** That is the criterion too: a
mode cannot place physical actuation under a new authority where there is no physical
actuation. The refusal both guards below implement is scoped to the PLAN, so it could not
have refused anything there in any case — a gate reported as applying to a wholly
simulated deployment was reporting a check that was structurally a no-op.

**Whether entering `VIRTUAL_LEAD` can move anything physical is a per-asset fact, and a
facility-wide transition is not that question asked once.** Where *a given asset's* far
side is a simulated counterpart, entering the mode moves nothing physical **for that
asset** — which is what makes the mode reachable in Phase 2.A at all. But `TwinMode`
carries `asset_id` with *empty for facility-wide*, and a facility with more than one asset
may have some far sides physical and some simulated. **A facility-wide `SetMode(VIRTUAL_LEAD)` is dangerous if any
single asset's far side is real**, and two assets answering "simulated" is not an answer
for the third. Never read this mode's safety off the cell as a whole.

**The third entry is also the only one that is not self-identifying from the requested
value**, and that is filed as an open question rather than answered here — see
[L5](L5-twin-synchronization.md)'s open questions.

- Explicit and gated. Never reachable through a default parameter, an environment
  variable, or a launch-argument default.
- Current mode observable at runtime.
- `CITE_ALLOW_HARDWARE=1` required before anything can command physical hardware, with the
  cell confirmed clear.

**When that opt-in binds — the part this list needs, and the only part not already above.**
The two guards, where they live and that both carry tests are in this document's Status
bullet, and are deliberately not restated here (P1). What that bullet does not say is *when*
they take effect: **both refuse before the stack starts — one at the shell boundary, one at
bring-up.** What they buy is that the stack could not have **started** with a physical
backend, and neither is a per-command refusal.

**A third refusal now exists at the point of transition, and its reach is narrow.**
`cite_twin/twin_boundary.py` serves `SetMode` and calls the same
`cite_bringup.plan.require_hardware_opt_in` when a transition places physical actuation
under an authority that was not previously commanding it. **Which transitions those are is
computed from the criterion and not read off the list above** — see the correction under
that list, and `cite_twin/cite_twin/mode.py`, which states in its own comment that it holds
no list of gated modes and why. `force` cannot skip it, which its own unit tests hold, one
per mode the message declares ([ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md)).

**A second refusal, on a different hazard, is also out of `force`'s reach**: a transition
is refused while any goal L5 dispatched is still running. `/cite/twin/mode` is where every
consumer reads what the cell is doing, and publishing `SIM` — *"physical idle"* — while an
arm is mid-motion under L5's own command would be a statement no reader could check. The
refusal names the goals; cancelling them is the operator's remedy, and L5 does not cancel
an arm's goal as a side effect of a mode change.

**What that does not amount to:** it is one refusal in one server, and it is not the safety
layer. It is in force whenever the pair supervisor starts the twin boundary
(`./scripts/sim --pair`, `./scripts/program`); a single-sided bring-up starts no L5 and so
serves no mode transition at all.

## Shared workspaces

Each side of the main tree has one arm on one track, so no two arms share a volume today. If
a cell ever holds two, preventing them from meeting is the safety layer's job — collision
checking and limits at L2 — and never the job of whatever sequences their work. **Sequencing
is not a safety mechanism**; relying on it for collision avoidance is a Critical finding.

## Gripper behaviour on fault

What happens to a held payload on E-stop, power loss, or controller failure? Both possible
answers are hazards:

- **Drops the part** — falling object, damaged work-piece.
- **Cannot be released** — a trapped part, and possibly a trapped person.

Neither is wrong in the abstract. What is wrong is not having chosen. The design must state
which behaviour it selected and why, and `safety-auditor` reports an unstated choice as a
finding.

## Failure modes

| Failure | Severity | Detection |
|---|---|---|
| Command path bypassing the safety layer | **Critical** | `safety-auditor` path trace |
| Limits enforced at planning only | High | `safety-auditor` |
| E-stop sharing the command path | **Critical** | `safety-auditor` |
| Automatic resumption after fault | **Critical** | `safety-auditor` |
| Mode reachable by default | **Critical** | `safety-auditor` |
| Test fixture disabling limits, reachable on the hardware path | **Critical** | `safety-auditor` |
| No watchdog on a command path | High | `safety-auditor` |
| Missing collision object | High | `model-validator` |
| Unstated gripper fault behaviour | Medium | `safety-auditor` |

## Before any physical motion, ever

1. Risk assessment complete and current — **not a software artifact**.
2. Physical E-stop tested, latency measured.
3. Cell clear, confirmed by a person who is looking at it.
4. `CITE_ALLOW_HARDWARE=1` set deliberately.
5. Reduced speed for any first execution of a new motion.
6. A human with a hand on the stop.

See [`../operations/safety-procedures.md`](../operations/safety-procedures.md).
