# 01 — Three-arm event-driven line

A frozen, runnable snapshot of the CITE Digital Twin at the moment its three-arm,
sensor-driven line was the thing the project ran. **It is a record, not a source**: it is
kept so that this milestone can be handed over as one folder and shown running, and nothing
in it is copied back into the main repository. Why snapshots exist and the rules they follow
are ADR-0068 in the main repository, which is not part of this folder.

| | |
|---|---|
| Source commit | `b5a0bc9` (tag `event-driven-line-v1`), 2026-09-28 |
| Zone | `cell_a`, one side (no twin pair) |
| Entry point | `./run` |
| Check | `./scripts/scenario continuous_line`, `./scripts/scenario pick_and_place` |
| Verification of this folder | **pending — see [`PROVENANCE.md`](PROVENANCE.md)** |
| Changes against the source commit | listed, with their diff, in [`PROVENANCE.md`](PROVENANCE.md) |

## What was achieved, and why this step

Three UFACTORY xArm 5 arms, three conveyor belts and a set of break beams, all described once
in the L0 facility model (`model/`) and generated into a Gazebo Harmonic world, controller
configurations, MoveIt configurations and a bring-up plan. A work-piece placed on the pick
table breaks a beam; an L4 behaviour tree per station reacts to that event, has its arm pick
the part and place it on a belt; the belt is indexed so the part stops at the next station's
beam; and the next arm takes over, until the part reaches the accumulation beam at the end of
the last belt. Grasping is by friction alone, with no attachment plugin
([ADR-0029](docs/adr/0029-simulated-grasping-by-friction.md)).

On the way to a twin of a real work cell, this was the step that proved the whole software
stack — the generated model, `ros2_control` with `gz_ros2_control`, MoveIt 2, the L3 skills
and L4 coordination — could move real parts through a multi-robot line in simulation. Having
answered that feasibility question, the project scoped down to one arm and one conveyor
([ADR-0056](docs/adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md)),
paired that cell into two twin sides
([ADR-0059](docs/adr/0059-pair-cell-b-and-leave-cell-a-single.md)), and later parked this
line in favour of a fixed program (snapshot 02).

The records that shape what you see:

- [ADR-0032](docs/adr/0032-index-the-belt.md) — L4 owns the belt setpoint and indexes a belt
  on a beam edge.
- [ADR-0033](docs/adr/0033-derive-the-index-standoff-from-the-workpiece.md) — the beam
  indexes on the part's body, not its origin.
- [ADR-0031](docs/adr/0031-refuse-direct-handoff-without-orientation-certainty.md) — L4
  refuses a direct arm-to-arm handoff; every handoff goes through a belt.
- [ADR-0037](docs/adr/0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0038](docs/adr/0038-stop-the-line-without-ending-the-process.md),
  [ADR-0039](docs/adr/0039-report-a-station-that-cannot-be-triggered.md) — how an abort is
  classified, how an escalation stops the line, and a station that can no longer be
  triggered.
- [ADR-0045](docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md),
  [ADR-0046](docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) — the two
  defects behind this line's best-documented failure (below).

## What you see

`./run` brings `cell_a` up with the line running, waits for the cell to announce that it is
ready, then feeds work-pieces onto the pick table one at a time (three by default). Nothing in
`./run` commands an arm or a belt: the part appearing on the table is what starts the line.
For each piece it prints the part's position as it travels and `ARRIVED` when the part
reaches the accumulation beam, then removes it and feeds the next. Ctrl-C tears the cell
down. `./run --help` prints the full description.

`./run` is a demonstration, not an instrument: it asserts nothing. The scenarios below are
what check the behaviour.

## Requirements

- Docker, and a Linux host. ROS 2 Jazzy, Gazebo Harmonic and MoveIt 2 run inside the
  container this folder builds; nothing needs to be installed on the host beyond Docker and
  a Python 3 interpreter for the host tooling.
- For a windowed run, an X display (`DISPLAY` set). `./run` refuses a windowed run on macOS
  and without `DISPLAY`; use `--headless` there.
- Network access on the first run: the container image is built and the pinned third-party
  sources in `external/cite.repos` are imported.

## Running it

From this folder:

```bash
./scripts/bootstrap        # host tooling, container image (tagged cite-digital-twin:p01-three-arm-line), imported sources
./scripts/build            # build the ROS 2 workspace in the container
./run --help               # what ./run does
./run                      # windowed: three work-pieces carried the length of the line
./run --headless           # the same with no window
./run --pieces 5           # five work-pieces, one at a time
```

To check the behaviour rather than watch it:

```bash
./scripts/scenario continuous_line    # work-pieces carried end to end by the line
./scripts/scenario pick_and_place     # one arm picks and places one work-piece
```

Both drive `cell_a`: this snapshot changes the scenarios' default zone from `cell_b` to
`cell_a` (patch 2 in [`PROVENANCE.md`](PROVENANCE.md)). A scenario prints
`Scenario '<name>' passed` only when both its cycle and its post-shutdown teardown check
passed; `passed its cycle assertions` means the teardown check failed
(`scripts/scenario`'s header explains `--teardown-advisory`).

## Taking it out of the repository

Copy this folder anywhere **without its `.venv/`** and run the steps above from the copy; it
is its own repository root. From the main repository, the committed tree alone:

```bash
mkdir /path/to/copy && git archive HEAD:projects/01-three-arm-event-driven-line | tar -x -C /path/to/copy
```

or, from a folder you already have, `rsync -a --exclude .venv 01-three-arm-event-driven-line/ /path/to/copy/`.
**Never `cp -a` a folder that has been bootstrapped**: `.venv/` is not relocatable — its
`pip` and other entry points carry the absolute path of the original in their shebang lines —
so `./scripts/bootstrap` in the copy runs the ORIGINAL's `pip` and re-points the original's
environment rather than building the copy's own. If a copy already has a `.venv/`, delete it
(`rm -rf .venv`) before running any script there; `./scripts/bootstrap` recreates it.

The copy is then a plain folder and not a git checkout. The Compose project name and
`ROS_DOMAIN_ID` are derived from the folder's path, so a copy normally gets its own. **Normally, not certainly**: the domain is a checksum of the path
folded onto 50 values, so two arbitrary paths can share one. `./scripts/doctor` prints the
domain in use; to choose one, export `ROS_DOMAIN_ID` before running any script, which the
scripts keep rather than derive over. [`PROVENANCE.md`](PROVENANCE.md) has the detail.

**What this snapshot promises is that it builds, `./scripts/scenario continuous_line` passes, and
`./run` runs — nothing more.** Its own `./scripts/lint`, its host and unit tests and
`./scripts/doctor` are outside that promise, and some of them fail by construction: the
extract leaves out `docs/measurements/`, `CLAUDE.md` and the charter, so the link check
reports dead links into them and host tests that read them fail; and tests that list files
with `git ls-files` find nothing in a copy that is not a git checkout.
[`PROVENANCE.md`](PROVENANCE.md) lists which, and why. The build, `./run` and the scenario
depend on none of it.

## Known limits and open issues

Every figure and status in this folder's `docs/` was true at the source commit only; nothing
here has been re-measured since, except what [`PROVENANCE.md`](PROVENANCE.md)'s verification
log records.

- **`continuous_line` is not a scenario that always passes.** The main repository's
  `CLAUDE.md` §2 records it failing its cycle in **7 of 25** CI runs on `cell_a` (2026-08-28
  to 2026-09-08, at commits earlier than this snapshot's, with no thresholds registered in
  advance — a count, not a rate), in **three** distinct failure signatures: a work-piece held
  in the air between `lifted` and `on_link` at the first transfer station while the line
  still reported `RUNNING`; a timeout spawning a work-piece; and a `Place` descent that
  aborted and escalated, stopping the line. The first is analysed in ADR-0045 and ADR-0046,
  the stop in ADR-0038; the third signature's physical cause was not established
  ([`docs/open-work.md`](docs/open-work.md) #60). ADR-0038, ADR-0039, ADR-0045 and ADR-0046
  are all `Proposed`.
- **At the source commit CI did not drive this line on `cell_a`**: the scenarios' default
  zone was `cell_b` (ADR-0056). The zone change in this folder restores `cell_a`; whether the
  line runs here is what the verification log is for.
- **A grasp holds a position, not an orientation**, and scenarios are not deterministic:
  `CITE_PHYSICS_SEED` reaches `gz sim --seed` and not the physics solver, and `./run`
  (through `./scripts/sim`) passes no seed at all
  ([`docs/architecture/cross-cutting-testing.md`](docs/architecture/cross-cutting-testing.md)).
- **The belts are commanded open-loop**: nothing publishes `ConveyorState`, so a belt that
  fails to stop is not noticed.
- **No hardware path.** Everything here is simulated; the layout is engineered, not surveyed.
- Security and dependency fixes made in the main repository after the source commit are not
  carried here.
