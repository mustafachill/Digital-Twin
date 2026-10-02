# Milestones

Each folder here is a **frozen, runnable snapshot** of this repository at a milestone it has
since moved past, kept so that the milestone can be handed over as one folder and shown
running ([ADR-0068](../docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md),
`Proposed`). Every folder is its own repository root: copy it anywhere, and `./run` from
there — **but copy it without its `.venv/`**, for example
`git archive HEAD:projects/<name> | tar -x -C <dest>` from this repository or
`rsync -a --exclude .venv`. A bootstrapped `.venv/` is not relocatable: its entry points name
the original folder in their shebang lines, so bootstrapping a `cp -a` copy re-points the
original's environment. Each snapshot's README has the recipe.

Whether each one has been verified to build and run, and when, is recorded in its own
`PROVENANCE.md` and nowhere else. From 2026-10-01 on, what is **measured** of it is kept in
its own `MEASUREMENTS.md`; earlier campaigns whose subject is that milestone remain under
[`docs/measurements/`](../docs/measurements/README.md), frozen where they are (the
[review queue](../docs/reference/claude-md-review-queue.md)'s Q84 sorts them).

## The journey

The project is heading for a twin of the CITE xArm work cell in which a real cell and a
digital one share one control interface. The three steps below are how it got to where the
[main tree](../README.md) is now.

### 01 — Three-arm event-driven line

Three arms on zone `cell_a`, one side, coordinated by L4 behaviour trees on break-beam events,
carry work-pieces along three belts, holding them by friction alone. It proved that the whole
stack — the generated model, `ros2_control`, MoveIt 2, the skills and the behaviour trees —
moves parts through a multi-robot line; the project then scoped down to one arm and one belt.
Source: `b5a0bc9` (tag `event-driven-line-v1`).
[README](01-three-arm-event-driven-line/README.md) ·
[PROVENANCE](01-three-arm-event-driven-line/PROVENANCE.md) · [MEASUREMENTS](01-three-arm-event-driven-line/MEASUREMENTS.md)

```bash
cd projects/01-three-arm-event-driven-line && ./scripts/bootstrap && ./scripts/build && ./run
```

### 02 — Fixed-program pair

Two Gazebo instances — the paired `cell_b`, one arm and one belt each — driven by **one**
fixed program of taught joint poses and timed belt runs, sent through the twin boundary so
both sides follow it. The first time one signal drove both sides of the twin. Source:
`c83119b`, the last `main` commit before the real program replaced the taught poses.
[README](02-fixed-program-pair/README.md) · [PROVENANCE](02-fixed-program-pair/PROVENANCE.md) · [MEASUREMENTS](02-fixed-program-pair/MEASUREMENTS.md)

```bash
cd projects/02-fixed-program-pair && ./scripts/bootstrap && ./scripts/build && ./run
```

### 03 — Real program, arm on a track

The real xArm 5's own UFACTORY Studio program, read from its exported file rather than
copied, drives both sides of `cell_b` through the twin boundary, with the arm riding a linear
track as it does on the real cell. The twin runs what the robot runs. Source: `e90d230`.
[README](03-real-program-twin-on-track/README.md) ·
[PROVENANCE](03-real-program-twin-on-track/PROVENANCE.md) · [MEASUREMENTS](03-real-program-twin-on-track/MEASUREMENTS.md)

```bash
cd projects/03-real-program-twin-on-track && ./scripts/bootstrap && ./scripts/build && ./run
```

### Then — the main tree

The main tree continues from 03 toward a physical side: the real xArm 5 program drives both
sides of the paired `cell_b` there today, and no hardware path has been run. See the
[root README](../README.md).

## The rules

- **A snapshot is a record, not a source.** Nothing is copied from `projects/` into the main
  tree, and the main tree never imports or builds from here. A snapshot's patterns are not
  precedent.
- **A snapshot changes only by a patch listed in its `PROVENANCE.md`**, with the reason and
  the diff — `MEASUREMENTS.md` included. Everything else is exactly the source commit's
  tracked tree, minus the paths `PROVENANCE.md` names as excluded.
- **A snapshot's measurements are in its `MEASUREMENTS.md`; its verification runs are in its
  `PROVENANCE.md`.** A measurement of a milestone — including one taken after the snapshot was
  made — is added to that snapshot's `MEASUREMENTS.md`, dated, with the hash bump below; it is
  never written into the main tree's `CLAUDE.md` or `docs/`. A main-tree measurement is a
  campaign under [`docs/measurements/`](../docs/measurements/README.md). (ADR-0068, amendment
  of 2026-10-01.)
- **Figures inside a snapshot were true at its source commit only**, except in its
  `MEASUREMENTS.md`, where each figure names the commit and date it was taken at. Its `docs/`
  are not maintained; read them as the state of that commit.
- **The main tree's checks deliberately skip `projects/`**, except for exactly this: this file
  and `snapshots.yaml` are walked (English, links) and the manifest yamllinted; each
  snapshot's `run` is shellchecked; and each snapshot's committed tree is checked against its
  pinned hash. Four repository walkers are narrowed to leave the snapshots out — three
  `git ls-files` host tests and `cite_test_hardware`'s ctest walk.
- **What a snapshot promises is that it builds, its scenario passes and `./run` runs.** Its
  own lint, unit tests and `doctor` are outside that promise and some of them fail by
  construction, because the extract leaves out `docs/measurements/`, `CLAUDE.md` and the
  charter; each `PROVENANCE.md` lists which.
- **A snapshot is frozen by a test, not only by this rule.** `projects/snapshots.yaml` pins
  each snapshot's git tree hash, and a host test fails when the committed tree differs, so a
  change to a snapshot needs a visible hash bump in the same commit.
- **A weekly workflow, not a gate.**
  [`.github/workflows/projects.yml`](../.github/workflows/projects.yml) builds each snapshot
  listed in [`snapshots.yaml`](snapshots.yaml) and runs its scenario — `continuous_line` for
  01, `program_cycle` for 02 and 03 — on
  Mondays and on demand. It does not gate `main`, and its scenario steps pass
  `--teardown-advisory`, so read the verdict in the step log rather than the step's
  conclusion.
