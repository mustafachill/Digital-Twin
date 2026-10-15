# ADR-0077: The operator console keeps the physical counterpart: connect when reachable, survive its loss

- **Status:** Proposed
- **Date:** 2026-10-15
- **Deciders:** Project owner (decision of 2026-10-15: "the app opens with the robot off; the
  robot connects when it comes up, Real arm and Twin become selectable, and a disconnect does
  not close the app")
- **Related:**
  - Amends [ADR-0050](0050-what-crosses-the-twin-boundary.md) decision 4,
    [ADR-0057](0057-start-the-twin-boundary-from-the-pair-supervisor.md),
    [ADR-0072](0072-the-operator-chooses-where-the-signal-goes.md) decision 4,
    [ADR-0075](0075-start-robot-and-home-act-on-the-selected-target.md) decision 4 and the
    failure table of [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md).
  - Depends on [ADR-0076](0076-a-physical-arm-is-held-until-the-operator-starts-it.md).

## Context

With the hardware opt-in, the pair supervisor starts the plant and the physical counterpart
once. It joins them, then starts the twin boundary and the console. Today:

- An unreachable robot crashes the vendor driver. The counterpart's launch fails and the
  whole app exits.
- A robot that disconnects later makes the vendor driver exit. The side goes down and the
  supervisor ends the pair with exit code 3.
- The boundary and the console read which sides run once, at start
  (ADR-0050 decision 4: "a runtime knob may not decide whether a side exists").

The owner wants the operator console to open with the robot off. The robot should connect
when it comes up, the Real arm and Twin targets should then be selectable, and a disconnect
should not close the app.

## Options considered

### Option A — The supervisor keeps the counterpart; the side waits for the robot
- **The side waits for the robot.** The physical side's launch starts with a reach gate: a
  TCP probe of the arm's report port. The vendor driver therefore never starts against an
  absent robot.
- **The supervisor keeps the side.** It does not wait for the counterpart before starting the
  boundary and the console. A counterpart exit is treated as "disconnected", not as the end of
  the pair. After the old process group is swept, the side is restarted whole.
- **The boundary is told the side's state.** The supervisor sends each state line to the
  boundary on its stdin. `TwinSides.running` reports the sides up now.
- **The console follows it.** It offers the targets whose sides are up now.

Chosen.

### Option B — Patch the vendor driver to reconnect in place
Make the vendor driver survive an absent or lost robot and reconnect itself. This means a
patch to pinned third-party source that would have to be carried forward, and it relies on
vendor behaviour that has not been measured (open-work #93). Rejected.

### Option C — Restart the whole app on a disconnect
This is simple, but the plant and the operator's view are lost every time the robot drops.
Rejected.

## Decision

1. **Declared versus up.** The set of sides that may exist is still fixed at start
   (`--sides`). Whether a declared physical counterpart is up right now is a runtime fact. The
   supervisor reports it and the boundary measures it. This restates ADR-0050 decision 4.
2. **Hot-plug applies only to the operator console with the opt-in.** With the pair
   supervisor's `--hot-plug`, accepted only beside `--console --sides all` (the operator
   console with a physical counterpart and the hardware opt-in), the supervisor runs the side
   as **kept**:
   - It starts the side at once, but does not join on it.
   - It reports one of `waiting`, `connecting`, `up`, `down` or `failed`.
   - When the side exits after `up`, it sweeps the side's process group, reports `down` once
     the group is empty, restarts the side and reports `waiting`.
   - At most three consecutive attempts that reach the robot but fail before `up` are made
     (`readiness.KEPT_ATTEMPTS`); after that the side is `failed`.
   - At most five downs after `up` within ten minutes (`readiness.KEPT_RECONNECTS` within
     `readiness.KEPT_RECONNECT_WINDOW_S`); the next is `failed`, and only a restart of the app
     starts the side again. Every reconnect starts a whole vendor driver against a real arm,
     and an unbounded loop of them is a fault nobody is shown.
   - An exit before the robot was reachable, which means a configuration refusal, is `failed`
     at once. So is an announcement naming another participant.
   - A process group still not empty after `SIGKILL` and a bounded wait is `failed`: a second
     driver is never started beside processes of the first.
   - The kept side's stop and sweep are escalated from the supervisor's main loop and never
     waited on there, so they never delay judging the participants whose exit ends the pair.
   - A `failed` line carries the failed attempts in a row that ended it (`attempts=N`), and
     the boundary words its refusal from the line.
   - Every other pair, including `./scripts/program`, scenarios and CI, is unchanged. A side
     exit there still ends the pair (ADR-0072 decision 4).
   - *Implementation note (2026-10-15):* the pair supervisor runs the side with the launch
     argument `wait_for_robot:=true`; a physical side NOT kept still gives up after the reach
     gate's own ceiling (`reach_gate.REACH_CEILING_S`), so a terminal run against a robot that
     is off ends at once, as it did when the vendor driver crashed.
3. **The side waits for the robot.** The first process of the physical side is a reach gate.
   It retries a TCP connect to the arm's report port at a stated period; this is a necessary
   poll, because there is no event for a host starting to listen. It never prints the address.
   The rest of the side starts only when the gate exits.
4. **The boundary learns the state on its stdin** (`--side-states stdin`; an amendment to
   ADR-0057). An end of input counts as `down` for every kept side, so it fails closed.
   - `TwinSides.running` lists the sides up now.
   - The new fields `expected` and `connecting` list the declared sides and those being
     connected.
   - While the counterpart is absent or held, REAL and VALIDATED are refused by measurement.
   - *Implementation note (2026-10-15, review S-01):* a kept side that stops being `up`
     takes the mode to SIM if the mode in force commands it, published at once and carried
     by the mode hold. The mode was entered on a readiness measured against the incarnation
     that is gone; entering it again is a `SetMode`, which measures the new one.
   - Goals in flight to a side that went away end; they never hang.
   - *Implementation note (2026-10-15):* `TwinSides` also gained `failed` (declared sides not
     retried) and `held` (running sides whose deadman holds the arm, ADR-0076), so the panel
     shows both without matching `detail` text. A goal in flight to a side that went away
     ends as `HARDWARE_FAULT`.
5. **The console offers what is up** (amends ADR-0075 decision 4). `available_targets` and
   `counterpart_running` follow the sides up now. A physical side that leaves loses its
   started flag. A connected but held side accepts Start robot, which releases it
   (ADR-0076).
6. **Restarting is not resuming.**
   - A restarted side comes up held (ADR-0076). No motion happens without a new Start robot
     and the operator's go-ahead.
   - Inside a launch, nothing respawns.

## Consequences

### What this gets us
- The control center opens whether or not the robot is on, and keeps running through a
  disconnect.
- Real arm and Twin appear when the robot is there and disappear when it is not.

### What this costs us
- New supervisor state: the keeper, its restart bounds, and per-attempt ceilings. There is a
  new boundary input and a contract change to `TwinSides`.
- `TwinSides.running` changes meaning from "started" to "up now", so every reader must be
  checked. **This is a recorded exception** to the interface compatibility table
  ([`docs/interfaces/README.md`](../interfaces/README.md)), which says a field whose meaning
  changes is a new field: every reader of `running` is in this tree and was moved with the
  change, and for every pair that keeps no side the two meanings are the same set. A per-side
  typed status is the replacement that would retire the exception (open-work).
- Each reconnect briefly energizes the arm (ADR-0076, consequences).
- How fast the vendor detects a pulled cable has not been measured (open-work #93).

### What we will have to revisit
- The restart bounds and the probe period, once a physical disconnect has been measured.
- More than one physical side.
