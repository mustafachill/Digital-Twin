# ADR-0076: A physical arm is held until the operator starts it

- **Status:** Proposed
- **Date:** 2026-10-15
- **Deciders:** Project owner (decision of 2026-10-15: "a connected arm stays held; its motors
  are enabled only when the operator presses Start robot with Real arm or Twin and confirms")
- **Related:**
  - Amends [ADR-0070](0070-the-physical-arm-is-cell-b-s-counterpart.md) item 5: the deadman no
    longer enables the arm on the AWAITING→HEALTHY edge.
  - [ADR-0075](0075-start-robot-and-home-act-on-the-selected-target.md) (Start robot per target),
    [ADR-0077](0077-the-operator-console-keeps-the-physical-counterpart.md) (reconnect),
    [`../architecture/cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)

## Context

The deadman (`cite_hardware/deadman.py`) holds STOP until the twin boundary's heartbeat
arrives, then goes HEALTHY and **enables the arm by itself**. Two things now make that wrong:

- The owner wants a physical arm to stay held until the operator presses Start robot with a
  target that includes it and confirms the go-ahead.
- [ADR-0077](0077-the-operator-console-keeps-the-physical-counterpart.md) lets the physical
  side restart while the boundary is already beating. A fresh deadman would go from AWAITING
  to HEALTHY at once and enable the arm before its controllers exist. The hold gate, which
  waits for AWAITING, would then never see it and take the side down.

Fixed facts, unchanged by this ADR:
- A heartbeat loss, a lost or duplicated boundary, or a lost vendor service trips the deadman,
  and the trip is latched.
- Only HEALTHY permits motion. The relays refuse motion in every other state.
- The physical E-stop is the only safety closure. Nothing here is a safety function in that
  sense.

## Options considered

### Option A — A HELD state released by the initializer
The deadman goes from AWAITING to a new **HELD** state on a fresh heartbeat. It sends STOP on
every tick in HELD, exactly as in AWAITING. A new `ReleaseArm` service moves it from HELD to
HEALTHY, and only that edge enables the arm. The asset initializer calls `ReleaseArm` as its
first step, so every route that initializes the arm releases it. Every one of those routes is
an operator command: the console's Start robot after the go-ahead, `./scripts/home`, and the
Homing of `./scripts/program`. Chosen.

### Option B — The console enables the arm directly
Start robot calls a vendor enable. This puts a vendor call outside the deadman, which is the
one place allowed to enable the arm. Rejected.

## Decision

1. `DeadmanState` gains `STATE_HELD`. A fresh heartbeat moves AWAITING to HELD. HELD sends STOP
   every tick, refuses motion, and trips exactly as HEALTHY does.
2. A new `ReleaseArm` service on the deadman moves HELD to HEALTHY. It is refused, with a
   reason, in any other state. The HEALTHY edge is the only place the arm is enabled.
3. The asset initializer releases the arm as its first step when the deadman is HELD, waits for
   HEALTHY with the arm enabled, then continues as before. Already HEALTHY: no release. Any
   other state: the initialization fails and names the state.
4. Every new deadman process starts held. So does a restarted physical side.
5. When the deadman trips, it keeps sending STOP and then ends its side. Under
   [ADR-0077](0077-the-operator-console-keeps-the-physical-counterpart.md) the side is
   restarted whole and comes up held. This is the operator's recovery path from a trip without
   restarting the app (owner decision of 2026-10-15).
6. The hold gate accepts AWAITING or HELD as held. Before it sends STOP, it waits until each
   vendor service has exactly one server, so the stale endpoints of a crashed driver are not
   mistaken for the live one.

## Consequences

### What this gets us
- No arm is enabled without an operator action. A reconnect never enables the arm by itself.
- A restarted side behaves exactly like a fresh one.

### What this costs us
- A contract change: `DeadmanState` gains a state, a new `ReleaseArm.srv`, a generated service
  name, and the initializer's sequence.
- The vendor plugin still sets START on each activation. The deadman reverts it within one
  tick, so the motors are briefly energized, holding position with no motion commanded, at
  every connect. The owner accepted this on 2026-10-15 rather than patching the vendor.
- Any terminal path that commands a physical side without initializing it first is now refused
  as held. That fails safe, but it is a behaviour change.

### What we will have to revisit
- A vendor patch that suppresses START on activation, if the brief energizing becomes a problem.
- Whether a trip should end the side or wait for an operator decision.
