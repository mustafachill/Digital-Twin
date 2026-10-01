# ADR-0066: Run the cell from a fixed program; park the event-driven line

- **Status:** Superseded by [ADR-0069](0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)
  — the *decision* to park the event-driven line in the main tree is withdrawn: ADR-0069 removes
  the line, `cell_a` and this record's taught-pose program (`program/cell_b_pick_place.py` and L0's
  `configuration.poses_rad` field) from the main tree, and the line runs as
  `projects/01` instead. The twin boundary's belt route this record
  added **stays**, on the project owner's decision, with no in-tree client. The fixed-program
  idea itself was already continued by [ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md).
  **Nothing below is rewritten and nothing below binds any longer.** Read ADR-0069 for what does.
  **[Replaced 2026-10-01, kept for the record:]** *"Proposed"*
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
   validator refuses a pose of the wrong length and one named `home`. **[Overtaken 2026-10-01 — ADR-0069 removes the field and both validator checks.]** The `cell_b` picker's four
   poses were **taught** by running the existing Pick and Place once in simulation and reading
   the joint states where the arm stood still.
2. **L3**: `MoveTo.named_configuration` accepts `home` and each L0 pose, on the same
   plan-and-execute path as `home`.
3. **L5**: the twin boundary forwards a belt setpoint from `/cite/twin/<zone>/<belt>/command` to
   each side's own command topic under the skills' routing table: nothing in `SIM`, both sides in
   `VALIDATED` and `VIRTUAL_LEAD`. **A stop is never gated**: a zero setpoint reaches every side in
   every mode, and a mode transition sends zero to the belts of any side the new mode no longer
   commands, because a physical belt's setpoint persists (ADR-0038).
4. **The program** (`cite_bringup/program/`) is a list of steps: home, open, pick_above, pick,
   grip, pick_above, place_above, place, open, place_above, home, belt on, wait, belt off. The
   grip width, belt speed and belt run time come from the plan. It refuses to start on an arm
   whose latched `RobotState` says it holds a part (its first step opens the jaws), puts the
   twin in `VALIDATED`, stops at the first step that does not succeed, and on any exit —
   including SIGINT and SIGTERM — cancels the goal in flight, even one not yet accepted, and
   commands the belt to zero; a stop it cannot send makes the exit status non-zero. It puts no
   part on the table: `--cycles N` assumes the caller supplies one per cycle, and
   `./scripts/program` does so by running it one cycle at a time, removing the last cycle's
   box and spawning a new one under the one model name the belt, beams and grasp hold match.
5. **The event-driven line is parked, not deleted.** Every file stays where it is, built and
   tested; `continuous_line` stays in CI; `./scripts/demo` and `line:=true` behave as before;
   the tag `event-driven-line-v1` marks the commit before this change; and
   `tools/tests/test_event_driven_line_is_kept.py` fails if a file of it disappears.
   **[Overtaken 2026-10-01 — ADR-0069 removes the line, the guard and `./scripts/demo` from the
   main tree; the line runs as `projects/01`.]**

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

After the review fixes, same machine, same day, not a rate: `./scripts/program --headless
--cycles 2` carried a box on both sides in both cycles, the last ending at x = 1.529 / 1.530 m.
SIGINT to the script during the belt's run printed `interrupted`, exited 130, and both sides'
measured belt speed went from 0.150 to 0.000 within about a second; SIGINT during a motion
exited 130 with no cancel reported as failed. **Four of about fourteen script runs never
started**, each reporting that no `RobotState` had arrived "within 60 s" (in one instrumented run:
one publisher matched and no sample, about ten of the domain's nodes discovered, the twin
boundary not among them), while the same read from another process answered in under 2 s.

**Corrected 2026-09-28: the cause was the program's own wait, not discovery.** `RosCell._until_true`
bounded its wait by a count of `rclpy.spin_once(timeout_sec=0.1)` calls (`SERVER_WAIT_S / 0.1`),
and `spin_once` returns as soon as any callback runs. The node runs with `use_sim_time`, so it
subscribes to `/clock`, and every sample ends a spin at once: the "60 s" was spent in about one
to two seconds. A failed probe reported "within 60 s" after **0.74 s, 1.28 s and 1.94 s**, and
the successful reads took up to **3.3 s** — so the wait routinely expired while discovery was
still in progress, which is what "one publisher matched, ten nodes discovered" was a snapshot
of. The wait is now bounded by `time.monotonic()`; `belt()`'s wait for a subscriber used the same
loop and is fixed with it. Measured on one machine against one pair of `cell_b` brought up
by `./scripts/sim --pair --headless`, each probe a fresh process running `refuse_if_holding`
through the twin: **3 of 15** failed before the fix and **0 of 15** after, the slowest success
at 3.03 s; and `./scripts/program --headless` then completed its cycle **6 of 6** times. Not a rate. The 60 s value was not changed. The regression test is
`test_a_wait_for_a_condition_is_bounded_by_time_not_by_spins` in `cite_bringup/test/test_program.py`.

### Must hold before a physical side
None of these matters while both sides are simulated, and each one is open. They are recorded
here so that pairing with hardware reopens them rather than discovering them.

- **The hardware opt-in does not cover belts.** `cite_twin/mode.py`'s gate derives the
  deployment from `controller_managers` only; a `Conveyor` declares no backend, so nothing
  refuses routing a belt setpoint to a physical drive.
- **The final `belt(0)` is published and not confirmed delivered** before `rclpy` shuts down,
  and the belt is open-loop anyway (nothing publishes `ConveyorState`).
- **Protections the parked line had and this program does not**: no arrival confirmation, no
  stop on the accumulation beam, no `StopAll` escalation, an open-loop belt. A direct
  `python3 -m cite_bringup.program --cycles N` pushes each finished part off the outfeed with
  the next belt run.
- **The poses were taught on the `PROVISIONAL` layout** and do not transfer to the building.
- **`--via plant` bypasses the L5 mode gate by design**: it addresses the plant's own servers.
- **Custody is read on the plant only.** Through the twin the program reads the plant arm's
  `RobotState`; the counterpart's is on a domain the program may not open (ADR-0044 clause 3),
  and the boundary does not route state, so a counterpart holding a part is not refused.
- `cite_bringup.program.cell.twin_name` restates `cite_twin.boundary.operator_endpoint`'s
  mapping, because `cite_twin` depends on `cite_bringup` and the reverse import would be an
  upward dependency. It is kept, and the two must change together.

### What we will have to revisit
When a joystick or teleoperation input arrives, it plugs into the parked line or into the
boundary's operator endpoints, and this record is reopened then. Promotion to `Accepted` wants
the program run on the pair with both boxes at the outfeed, recorded, and `program_cycle`
passing in CI.
