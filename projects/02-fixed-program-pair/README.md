# 02 — Fixed-program pair

A frozen, runnable snapshot of the CITE Digital Twin at the moment a fixed program first drove
**both sides of a twin pair with one signal**. **It is a record, not a source**: it is kept so
that this milestone can be handed over as one folder and shown running, and nothing in it is
copied back into the main repository. Why snapshots exist and the rules they follow are
ADR-0068 in the main repository, which is not part of this folder.

| | |
|---|---|
| Source commit | `c83119b`, 2026-09-29 — the last `main` commit before ADR-0067 |
| Zone | `cell_b`, paired: two Gazebo instances, one arm and one belt each |
| Entry point | `./run` (a thin wrapper over `./scripts/program --zone cell_b`) |
| Check | `./scripts/scenario program_cycle` |
| Verification of this folder | **pending — see [`PROVENANCE.md`](PROVENANCE.md)** |
| Changes against the source commit | listed, with their diff, in [`PROVENANCE.md`](PROVENANCE.md) |

## What was achieved, and why this step

The project owner's goal is one signal driving two arms: today both digital sides of the
paired cell, later one physical and one simulated. The three-arm line (snapshot 01) could not
do that — on a pair it ran two independent sensor-driven lines, one per side. This step
replaced it, for the paired cell, with a **fixed program** in the way the real xArm is taught:
move to a taught joint pose, close the gripper, move, open it, run the belt, stop it
([ADR-0066](docs/adr/0066-run-the-cell-from-a-fixed-program.md)).

The program is one client on the plant's ROS domain calling the **twin boundary**
(`/cite/twin/...`), which forwards each goal and each belt setpoint to both sides. That keeps
the rule that only the boundary holds endpoints in both domains
([ADR-0044](docs/adr/0044-one-ros-domain-per-side-identical-names.md),
[ADR-0050](docs/adr/0050-what-crosses-the-twin-boundary.md)). The four poses were taught in
simulation and declared in L0 as `configuration.poses_rad` in
`model/assets/instances/arms.yaml`. The event-driven line was parked, not deleted.

On the way to a real + digital twin, this is the step where the twin boundary first carried
a whole work cycle to two cells at once. The next step (snapshot 03) replaced the taught poses
with the real robot's own program.

The records that shape what you see:

- [ADR-0066](docs/adr/0066-run-the-cell-from-a-fixed-program.md) — the fixed program, and
  what it costs.
- [ADR-0059](docs/adr/0059-pair-cell-b-and-leave-cell-a-single.md) — `cell_b` is paired.
- [ADR-0057](docs/adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md) — the pair
  supervisor starts the twin boundary.
- [ADR-0065](docs/adr/0065-the-cell-says-what-it-holds.md) — the cell says what it holds;
  the program refuses to start on an arm that holds a part.

## What you see

`./run` brings both sides of `cell_b` up **without** the line, one Gazebo window per side, and
waits for both sides and the twin boundary to announce readiness. For each cycle (one by
default) it puts a work-piece on each side's pick table and runs the program once through the
twin boundary: it switches the twin to `VALIDATED`, then both arms move pose by pose, pick the
part, place it on the belt, return home, and both belts run for a computed time and stop. It
then prints where each side's box ended against the outfeed frame and tears the pair down.
Ctrl-C cancels the goal in flight, commands the belts to zero and tears the pair down.
`./run --help` prints the full description, including `./scripts/program`'s own.

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
./scripts/bootstrap        # host tooling, container image (tagged cite-digital-twin:p02-fixed-program), imported sources
./scripts/build            # build the ROS 2 workspace in the container
./run --help               # what ./run does
./run                      # windowed: both sides, one cycle through the twin boundary
./run --headless           # the same with no windows
./run --cycles 3           # three cycles, a fresh box each (0: until Ctrl-C)
```

`./run` refuses `--zone`; this milestone was proven on `cell_b` only.

To check the program rather than watch it:

```bash
./scripts/scenario program_cycle      # one cycle on the plant side, asserted from the simulator
```

A scenario prints `Scenario '<name>' passed` only when both its cycle and its post-shutdown
teardown check passed; `passed its cycle assertions` means the teardown check failed
(`scripts/scenario`'s header explains `--teardown-advisory`).

## Taking it out of the repository

Copy this folder anywhere **without its `.venv/`** and run the steps above from the copy; it
is its own repository root. From the main repository, the committed tree alone:

```bash
mkdir /path/to/copy && git archive HEAD:projects/02-fixed-program-pair | tar -x -C /path/to/copy
```

or, from a folder you already have, `rsync -a --exclude .venv 02-fixed-program-pair/ /path/to/copy/`.
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

- **ADR-0066 is `Proposed`.** Its promotion wants the program run on the pair with both boxes
  at the outfeed, recorded, and `program_cycle` passing in CI. The runs it records are on one
  machine, with nothing registered in advance, and it says itself that they are not a rate.
- **The program is open-loop about the part**: it does not look, and a part that is not on
  the table is found only when the grip closes on nothing. The belt run is a timed dwell. The
  beams exist and the program reads none of them.
- **The poses are only as good as the layout they were taught on**, and that layout is
  `PROVISIONAL` — engineered, not surveyed.
- **No paired scenario.** `program_cycle` runs the program on the plant only (`--via plant`,
  which bypasses the twin boundary's mode gate by design); both sides together are shown by
  `./run` and asserted by nothing.
- **Custody is read on the plant only**: a counterpart arm holding a part is not refused.
- **Open before any physical side**, all recorded in ADR-0066: the hardware opt-in does not
  cover belts; the final belt stop is published and not confirmed delivered; this program has
  none of the parked line's protections (arrival confirmation, `StopAll` escalation).
- **In the main repository this behaviour no longer exists.** ADR-0067 removed the taught
  poses from L0 and made the real robot's program the one that runs (snapshot 03).
- Security and dependency fixes made in the main repository after the source commit are not
  carried here.
