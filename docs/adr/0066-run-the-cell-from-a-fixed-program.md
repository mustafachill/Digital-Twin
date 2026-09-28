# ADR-0066: Run the cell from a fixed program; park the event-driven line

- **Status:** Proposed
- **Date:** 2026-09-28
- **Deciders:** Project owner
- **Related:** [ADR-0032](0032-index-the-belt.md),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md), [ADR-0050](0050-what-crosses-the-twin-boundary.md),
  [ADR-0065](0065-the-cell-says-what-it-holds.md), CLAUDE.md §3 (P1, P2, P4)

## Context

The owner's goal is one signal driving two arms: both digital sides of the paired `cell_b`
today, one physical and one simulated later. What drives the cell today does not do that.
`line:=true` starts an L4 `line_orchestrator` **on each side**, each waiting on its own break
beam, so a pair runs two independent, identical, sensor-driven lines. The twin boundary routes
skills in `VALIDATED` and `VIRTUAL_LEAD`, and nothing sends it a goal. On `cell_b` the belt is
never indexed on a beam edge either: the only station's inbound edge has no belt, so the belt
simply runs from `run_all()` until `StopAll`.

The real xArm is taught the way UFACTORY Studio's Blockly teaches it: move to a taught pose,
close the gripper, move, open it, run the belt, stop it. The owner asked for the cell to be run
that way: fixed joint angles, fixed belt intervals, reached **through the twin boundary**, in
modular Python with no over-engineering, and with the event-driven line **kept**, not deleted,
for a later joystick or teleoperation input.

Fixed: only the boundary may hold endpoints in both domains (ADR-0044 clause 3); simulation and
hardware keep identical names (P2); every number about the cell lives once in L0 or the plan
(P1).

## Options considered

### Option A — Keep the event-driven line and route its goals through the boundary
Run one `line_orchestrator` on the plant and send its goals to `/cite/twin/...`. It keeps the
sensor-driven behaviour, but the beams are per side: the plant's beam would drive the
counterpart's arm, and the orchestrator's belt ownership (ADR-0032) would have to learn a
second domain. More machinery than the owner's goal needs, and not what the owner asked for.

### Option B — A fixed program in Python, through the boundary (chosen)
Taught joint poses in L0, a readable step list, one client on the plant's domain calling
`/cite/twin/...`. The boundary gains the one route it lacked, the belt setpoint.

### Option C — A fixed program that opens both domains itself
Simpler to write, and forbidden: ADR-0044 clause 3.

## Decision

The cell runs from a fixed program, `python3 -m cite_bringup.program`, and `./scripts/program`
runs it on the pair. Concretely:

1. **L0** gains `configuration.poses_rad` on a robot instance, a map of named joint poses. The
   validator refuses a pose of the wrong length and one named `home`. The `cell_b` picker's four
   poses were **taught** by running the existing Pick and Place once in simulation and reading
   the joint states where the arm stood still.
2. **L3**: `MoveTo.named_configuration` accepts `home` and each L0 pose, on the same
   plan-and-execute path as `home`.
3. **L5**: the twin boundary forwards a belt setpoint from `/cite/twin/<zone>/<belt>/command` to
   each side's own command topic under the skills' routing table: nothing in `SIM`, both sides in
   `VALIDATED` and `VIRTUAL_LEAD`.
4. **The program** (`cite_bringup/program/`) is a list of steps: home, open, pick_above, pick,
   grip, pick_above, place_above, place, open, place_above, home, belt on, wait, belt off. The
   grip width, belt speed and belt run time come from the plan. It puts the twin in
   `VALIDATED`, stops at the first step that does not succeed, and on any exit cancels the goal
   in flight and commands the belt to zero.
5. **The event-driven line is parked, not deleted.** Every file stays where it is, built and
   tested; `continuous_line` stays in CI; `./scripts/demo` and `line:=true` behave as before;
   the tag `event-driven-line-v1` marks the commit before this change; and
   `tools/tests/test_event_driven_line_is_kept.py` fails if a file of it disappears.

This reverses the "sensor-driven rather than timed" framing the belt plugin's header carried.

## Consequences

### What this gets us
One program moves both arms and both belts through the boundary, which is the owner's goal
stated as a command. The same program with `--via plant` drives one side, and
`./scripts/scenario program_cycle` checks it there. Nothing in the parked line changed.

### What this costs us
- **The program is open-loop about the part.** It does not look: a part that is not on the
  table is found only when the grip reports closing on nothing, and a part that lands somewhere
  else on the belt is carried for the same time anyway. The beams still exist and nothing in
  the program reads them.
- **The poses are only as good as the layout they were taught on.** Move a station and they
  must be taught again; nothing notices except the grip or the scenario.
- **The belt run time is a timed dwell.** It is computed from the belt's length and speed, not
  guessed, and it still runs whether or not the part is there.
- **L5 now publishes onto a side-owned topic**, the belt command, where before it only called
  side-owned action servers. What crosses is still a command, never state.
- The joint limits of a taught pose are not checked in L0, because L0 does not read the vendor
  description; the planning group refuses an out-of-range pose at `MoveTo`.

### What has been observed, 2026-09-28
One machine, nothing registered in advance, not a rate. `./scripts/scenario program_cycle`
passed once with the bare verdict (cycle and teardown), the program taking 57 s. `./scripts/program
--headless --cycles 1` ran all 14 steps through the boundary and both boxes ended resting on
their belts at x = 1.529 m against an outfeed frame at 1.600 m, 1 mm apart in y. With the pair
in `SIM`, a `MoveTo` sent to `/cite/twin/cell_b/picker/move_to` was aborted and a belt setpoint
was dropped with the boundary's log line.

### What we will have to revisit
When a joystick or teleoperation input arrives, it plugs into the parked line or into the
boundary's operator endpoints, and this record is reopened then. Promotion to `Accepted` wants
the program run on the pair with both boxes at the outfeed, recorded, and `program_cycle`
passing in CI.
