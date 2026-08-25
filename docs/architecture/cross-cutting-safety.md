# Safety and interlocks

- **Status:** `DESIGNED` — **the safety layer described here does not exist.** No node
  enforces any row of the table below, and the enforcement point in the diagram is not in
  the command path. Binding from the first line of Phase 2 code.
  One rule it states *is* enforced today, and only one: nothing reaches a hardware backend
  without a deliberate opt-in. `CITE_ALLOW_HARDWARE=1` is required by
  `require_explicit_hardware_opt_in` in `scripts/_lib.sh` for `./scripts/enter hardware`,
  and independently by `require_hardware_opt_in` in `cite_bringup/cite_bringup/plan.py` for
  any bring-up plan naming a non-simulated backend. Both are covered by tests.
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
        L4 orchestration
               │
        L3 skills
               │
        L2 MoveIt / controllers
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

`SIM` → `REAL` and entry to `CLOSED_LOOP` are the two most dangerous state changes in the
system ([L5](L5-twin-synchronization.md)).

- Explicit and gated. Never reachable through a default parameter, an environment
  variable, or a launch-argument default.
- Current mode observable at runtime.
- `CITE_ALLOW_HARDWARE=1` required before anything can command physical hardware, with the
  cell confirmed clear.

## Multi-robot workspaces

When two arms can occupy the same volume, something must prevent it. Two mechanisms, and
they must not be confused:

| Mechanism | Layer | Prevents |
|---|---|---|
| Workspace arbitration | L4 | Deadlock and thrash |
| Collision checking and limits | L2 safety layer | **Collision** |

**L4 is not a safety mechanism.** If a coordination bug can cause a collision, the safety
layer is missing something. Relying on orchestration for collision avoidance is a Critical
finding.

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
