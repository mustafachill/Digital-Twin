# ADR-0072: The operator chooses where the signal goes — simulation, real arm, or twin

- **Status:** Proposed
- **Date:** 2026-10-09
- **Deciders:** Project owner (decisions of 2026-10-09: the routing change, and that the hardware
  opt-in decides which sides start)
- **Related:**
  - Amends [ADR-0050](0050-what-crosses-the-twin-boundary.md) decision 2, for the `SIM` and
    `REAL` rows of its routing.
  - Amends [ADR-0057](0057-start-the-twin-boundary-from-the-pair-supervisor.md): a pair may now
    start with the plant alone.
  - Builds on [ADR-0071](0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md),
    [ADR-0011](0011-twin-maturity-model-and-modes.md),
    [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 3 and
    [ADR-0070](0070-the-physical-arm-is-cell-b-s-counterpart.md).
  - [`../architecture/cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)

## Context

A digital twin must be able to run its program on the simulation alone, on the real arm alone, or
on both. On 2026-10-09 the project owner asked for that choice to be made from the operator panel
(ADR-0071). The choice must be possible whether or not the real arm is connected.

These facts constrain the design (as read on `main` at `71f19a9`):

- **The modes exist, but only one routes.** `TwinMode` already defines `SIM` (virtual commanded,
  physical idle), `REAL` (physical commanded, virtual idle) and `VALIDATED` (both commanded).
  `cite_twin/routing.py` sends a goal to both sides in `VALIDATED` and `VIRTUAL_LEAD`. It refuses
  every goal in `SIM` and in `REAL`, because ADR-0050 decision 2 assumed that the operator would
  command a single side directly on that side's own servers.
- **The physical arm cannot move without the boundary.** Its deadman enables it only while the
  boundary's heartbeat is fresh (ADR-0070 item 5). So "real arm only" cannot bypass L5: commanding
  the physical side directly is exactly the path that open-work #102 is narrowing.
- **The boundary already copes with a missing far side.** Any mode other than `SIM` on a
  deployment with no far side is refused at the transition (`cite_twin/mode.py`).
- **Bring-up today needs both sides.** The pair supervisor starts every side the plan declares,
  refuses fewer than two, and ends the pair when either side exits. The plan's counterpart is
  physical, so without `CITE_ALLOW_HARDWARE=1` nothing starts at all (open-work #101).
- **`SIM` is what makes it safe for a person to enter the cell.** The program and the console ask
  a person in only after reading `SIM`, because in `SIM` nothing reaches the physical side
  (SA-S-05). Any change to `SIM` must keep that true.

## Options considered

### Option A — Command a single side directly, outside the twin
Simulation-only uses the plant's own servers (`--via plant`), and real-only uses the
counterpart's. Not chosen. The real arm would then be commanded without the twin's mode gate and
without its hardware opt-in at the transition. That is the bypass open-work #102 exists to close,
and it would become a supported path instead of a misuse.

### Option B — New modes for single-side routing
Add `SIM_ONLY` and `REAL_ONLY` and leave `SIM` and `REAL` refusing goals. Not chosen. `SIM` and
`REAL` already mean "only this side is commanded", and a second pair of modes with the same
meaning is a value in two places (P1). ADR-0011's amendment also says that adding a mode is an
argument in the mode set, and nobody has made one.

### Option C — `SIM` and `REAL` route to the side they name
`SIM` routes to the plant only, `REAL` routes to the counterpart only, and `VALIDATED` routes to
both, as it does today. Every target goes through the boundary, so the deadman, the opt-in and
the readiness checks at the transition apply to all three.

## Decision

Option C.

1. **Routing (amends ADR-0050 decision 2).**

   | Mode | Goals, track and belt commands go to |
   |---|---|
   | `SIM` | the plant only |
   | `REAL` | the counterpart only |
   | `VALIDATED` | both sides, as before |

   The other modes keep their rows. Nothing crosses from one side to the other in `SIM` or
   `REAL`. Each mode commands exactly the sides that `routing._COMMANDED` already names for it,
   and the module's import-time consistency check now holds that the two tables agree side for
   side, not only on whether a mode commands anything.

2. **`SIM` stays safe for a person in the cell.** In `SIM` nothing reaches the physical side.
   That was the premise of SA-S-05, and it is now the routing table itself, not merely the
   absence of routing. Two consequences:
   - The operator gates and the hardware opt-in apply to `REAL` exactly as they apply to
     `VALIDATED`: the opt-in and readiness at the transition, the operator's go-ahead read in
     `SIM` before entering, the physical speed floor, and the return to `SIM` afterwards.
   - A target that includes the real arm initializes it first (Start robot).
   - In `REAL`, the boundary does not require the plant's carriage to agree with the
     counterpart's, because the plant is idle. Every physical-side readiness check still applies.

3. **The operator picks the target, and it is never defaulted.** The console's `HomeRobot` and
   `RunProgram` goals carry an explicit target (simulation, real arm or twin), sent with every
   request in the same way as the speed scale. The server refuses a goal with no target, and a
   target whose sides are not running.
   - `ConsoleState` publishes the targets the running deployment can serve, and the panel offers
     only those.
   - "At the program's start" is tracked **per side**. Start program requires it for every side
     in the target.
   - Switching target leaves the sides wherever the last target left them. A Home in twin
     brings both to the start.

4. **The hardware opt-in decides which sides start (amends ADR-0057).**
   - `./scripts/console` with `CITE_ALLOW_HARDWARE=1` starts both sides, the boundary and the
     console, and all three targets can be chosen.
   - Without the opt-in it starts the plant alone, with the boundary and the console, and only
     the simulation target can be chosen. A plant-only pair is a supported deployment, not a
     failure.
   - The real arm is never started by default.
   - A pair started with both sides still ends when either side exits, as before.

5. **Unchanged.**
   - The physical side is never the plant (ADR-0041 Decision 3).
   - `./scripts/program` keeps driving the twin (`VALIDATED`). The terminal path may take the
     same explicit target through the one sequencer, `program/cycle.py`.
   - `--via plant` remains the scenario route on a plant with no boundary.

## Consequences

### What this gets us
- One panel runs the real program on the simulation, on the real arm or on both, and the choice
  is made at runtime.
- The simulation can be operated with no robot connected at all.
- The real arm stays behind the deadman, the opt-in and the operator gates whatever the target.
- The meanings of `SIM` and `REAL` in `TwinMode.msg` become true of the routing as well.

### What this costs us
- **ADR-0050's "the counterpart is idle in `SIM`" is now enforced by the routing table**, not by
  refusing everything. A defect in the table would reach the physical side. The import-time
  table check and a test per mode are the guard.
- **`SIM` → `REAL` is one of the three most dangerous transitions**
  (`cross-cutting-safety.md`), and an operator can now request it from a panel. It carries the
  same gates as `VALIDATED`, nothing more.
- **A single-side target lets the sides drift apart**, and divergence metrics are meaningless
  while only one side is commanded. The panel shows the per-side start status, and twin requires
  a Home after any single-side run that left them apart.
- **A real-arm-only deployment without the simulation is not supported.** The plant always runs.
  Lifting that means a boundary that runs with only the counterpart, which is a further
  amendment.

### What we will have to revisit
- **When a physical belt exists:** the belt command's routing in `REAL`.
- **When `SetMode` ownership is enforced (open-work #100):** who may switch the target.
- **When an all-simulated pair can be started (open-work #101):** the plant-only deployment may
  cover part of that need.
