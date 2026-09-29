# 03 — The real program drives the twin, the arm on a track

A frozen, runnable snapshot of the CITE Digital Twin at the moment the **real xArm 5's own
program** first drove both sides of the twin pair, with the arm riding a linear track as it
does on the real cell. **It is a record, not a source**: it is kept so that this milestone can
be handed over as one folder and shown running, and nothing in it is copied back into the
main repository. Why snapshots exist and the rules they follow are ADR-0068 in the main
repository, which is not part of this folder.

| | |
|---|---|
| Source commit | `e90d230`, 2026-09-29 — the merge of ADR-0067 |
| Zone | `cell_b`, paired: two Gazebo instances, one arm on one track and one belt each |
| Entry point | `./run` (a thin wrapper over `./scripts/program --zone cell_b`) |
| Check | `./scripts/scenario program_cycle` |
| Verification of this folder | **pending — see [`PROVENANCE.md`](PROVENANCE.md)** |
| Changes against the source commit | listed, with their diff, in [`PROVENANCE.md`](PROVENANCE.md) |

## What was achieved, and why this step

The fixed program before this (snapshot 02) moved the twin through poses taught in
simulation. The real xArm 5 already had a program — a UFACTORY Studio Blockly project — and
it differed from the twin in the three ways that matter: the real arm rides a linear track,
its poses are other poses, and its gripper closes narrower than the twin's box. This step made
the real program the source
([ADR-0067](docs/adr/0067-the-real-program-drives-the-twin-on-a-track.md)):

- The exported program is kept byte for byte in
  `model/programs/xarm5_real_demo.blockly.xml`, pinned by a host test, and read — never
  hand-copied — by a strict reader that refuses any block it does not understand.
- Its poses and steps are generated into the bring-up plan, so `./scripts/validate-model`
  refuses a program the twin cannot run rather than the cell finding out mid-cycle.
- The arm stands on the carriage of a linear track with its own trajectory controller, and a
  track step is forwarded by the twin boundary to both sides.
- The layout and the box are derived from the program: the box is sized so the program's
  gripper close still evidences a grasp.
- **The belt is not twinned**: the real program has no belt block, so each side's belt is
  started on that side, never through the boundary.

On the way to a real + digital twin, this is the step where the twin runs what the real robot
runs, from the robot's own file. What is missing before a physical side is listed below.

The records that shape what you see:

- [ADR-0067](docs/adr/0067-the-real-program-drives-the-twin-on-a-track.md) — the real
  program, the track, the derived layout and box, and its 2026-09-29 corrections.
- [ADR-0066](docs/adr/0066-run-the-cell-from-a-fixed-program.md) — the fixed-program runner
  and the twin boundary's belt route this step builds on.
- [ADR-0052](docs/adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) — the grasp
  rules the box size is derived from.
- [ADR-0044](docs/adr/0044-one-ros-domain-per-side-identical-names.md),
  [ADR-0050](docs/adr/0050-what-crosses-the-twin-boundary.md) — one ROS domain per side, and
  what crosses the boundary.

## What you see

`./run` brings both sides of `cell_b` up **without** the line, one Gazebo window per side, and
waits for both sides and the twin boundary to announce readiness. It starts each side's belt
on that side, then, for each cycle (one by default), puts a work-piece on each side's pick
table and sends the real program **once** through the twin boundary: both arms grip the part
at track position 0, lift it, slide along the track, and place it on the belt's infeed, and
both belts carry it on. It then prints where each side's box ended against the outfeed frame
and tears the pair down. Ctrl-C cancels the goal in flight, holds the track where it stands and
tears the pair down. `./run --help` prints the full description, including
`./scripts/program`'s own.

To list the program's steps as the plan states them, inside the container:
`./scripts/enter dev python3 -m cite_bringup.program --zone cell_b --dry-run`.

`./run` is a demonstration, not an instrument: it asserts nothing. `program_cycle` is what
checks the program, on the plant side only.

## Requirements

- Docker, and a Linux host. ROS 2 Jazzy, Gazebo Harmonic and MoveIt 2 run inside the
  container this folder builds; nothing needs to be installed on the host beyond Docker and
  a Python 3 interpreter for the host tooling.
- For a windowed run, an X display (`DISPLAY` set). `./scripts/program` refuses a windowed
  run on macOS and without `DISPLAY`; use `--headless` there.
- No other container of any checkout running on the host: `./scripts/program` stops this
  folder's own and refuses while another's is up, because it would share its ROS domain.
- Network access on the first run: the container image is built and the pinned third-party
  sources in `external/cite.repos` are imported.

## Running it

From this folder:

```bash
./scripts/bootstrap        # host tooling, container image (tagged cite-digital-twin:p03-real-program), imported sources
./scripts/build            # build the ROS 2 workspace in the container
./run --help               # what ./run does
./run                      # windowed: both sides, the real program once through the twin boundary
./run --headless           # the same with no windows
./run --cycles 3           # three cycles, a fresh box each (0: until Ctrl-C)
```

`./run` refuses `--zone`; this milestone was proven on `cell_b` only.

To check the program rather than watch it:

```bash
./scripts/scenario program_cycle      # one cycle on the plant side: lifted, carried, placed, belted
```

A scenario prints `Scenario '<name>' passed` only when both its cycle and its post-shutdown
teardown check passed; `passed its cycle assertions` means the teardown check failed
(`scripts/scenario`'s header explains `--teardown-advisory`).

## Taking it out of the repository

Copy this folder anywhere and run the steps above from the copy; it is its own repository
root. The Compose project name and `ROS_DOMAIN_ID` are derived from the folder's path, so a
copy normally gets its own. **Normally, not certainly**: the domain is a checksum of the path
folded onto 50 values, so two arbitrary paths can share one. `./scripts/doctor` prints the
domain in use; to choose one, export `ROS_DOMAIN_ID` before running any script, which the
scripts keep rather than derive over. [`PROVENANCE.md`](PROVENANCE.md) has the detail.

**What this snapshot promises is that it builds, `./scripts/scenario program_cycle` passes, and
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

- **ADR-0067 is `Proposed`.** Its promotion wants `program_cycle` passing in CI and the
  program run on the pair with both boxes placed and carried, recorded. What it records as
  observed is one machine, with nothing registered in advance — not a rate.
- **The track has no hardware path.** The real track is commanded through the vendor's
  `set_linear_motor_pos` service; the track type declares a `sim` backend only, and a `real`
  track is refused by the validator.
- **A mode change during a track move sends no stop.** A track step is one trajectory point
  the boundary forwards to both sides and then forgets; if the twin leaves `VALIDATED` or
  `VIRTUAL_LEAD` while the carriages move, each side runs the point it already has to its
  end. Unlike a belt, whose setpoint the boundary zeroes. Recorded, not fixed.
- **The counterpart is commanded and not read back**: arrival of a track move is observed on
  the plant only, and so is custody of the part.
- **The belt is not twinned**, and is open-loop on both sides.
- **No trial has run at the program's grip width**; what holds the grasp rule there is the
  validator, not a measurement (ADR-0067's correction).
- **The event-driven line cannot run on this cell**: at track position 0 the belt's infeed is
  out of the arm's reach, so the transfer station declares no place frame and L4 refuses the
  line at plan time. `./scripts/demo`, which runs the line on the paired zone, therefore
  cannot run here; the three-arm line is snapshot 01.
- **No paired scenario.** `program_cycle` runs on the plant only; both sides together are
  shown by `./run` and asserted by nothing.
- **The layout is engineered, not surveyed**: the track's stand height and rail width are
  derived or engineered and `PROVISIONAL`, and the Blockly gripper speed is not modelled.
- Security and dependency fixes made in the main repository after the source commit are not
  carried here.
