# Getting started

Goal: from a fresh clone to a working environment, in one command, on any
machine. If any step here fails, that is a bug in the setup — report it rather
than working around it.

Read `what-we-are-doing.md` first to understand what you are building, and
`CLAUDE.md` for the rules you are expected to follow.

## The one thing to understand first

**You can author anywhere. You can build and run on Linux.**

ROS 2 Jazzy, Gazebo Harmonic, and MoveIt 2 do not run natively on macOS or
Windows. That does not stop you working — the layer that defines the facility
(L0) is plain Python with no ROS dependency, so model validation, generation,
linting, and the asset pipeline all run on your laptop. Everything else runs in
a Linux container, and the scripts route you there automatically.

You should never have to think about which. `./scripts/build` on a Mac builds
inside the container without being asked.

## Setup

```bash
git clone <repo-url> Digital-Twin
cd Digital-Twin
./scripts/bootstrap
```

That installs the Python tooling, builds the container image, imports external
sources, applies local patches, and resolves system dependencies. The first run
takes a while because the image is large; later runs are fast and idempotent.

Authoring only, no Docker, nothing to build:

```bash
./scripts/bootstrap --host-only
```

Then check your environment:

```bash
./scripts/doctor
```

`doctor` distinguishes *failed* from *skipped*. Skipped items are things that do
not exist at the current phase and are expected — see `CLAUDE.md` §2. Failures
are real.

## Everyday commands

| Command | What it does |
|---|---|
| `./scripts/bootstrap` | Prepare or repair the environment. Safe to re-run. |
| `./scripts/doctor` | Diagnose. Run this first when something is wrong. |
| `./scripts/build` | Build the ROS workspace. |
| `./scripts/test` | Host tooling tests, then ROS tests. |
| `./scripts/lint` | Lint everything lintable on this machine. |
| `./scripts/format` | Apply formatting in place. |
| `./scripts/validate-model` | Validate the L0 facility model. Runs anywhere. |
| `./scripts/sim [--headless] [--pair]` | Launch the simulated cell. `--pair` is the twin pair and needs a paired L0 model — see [`../operations/bring-up.md`](../operations/bring-up.md). |
| `./scripts/scenario [name]` | Run a headless scenario; no argument lists them. |
| `./scripts/enter [dev\|gui\|hardware] [command...]` | Interactive shell in the container; with a trailing command, runs it there and exits. |
| `./scripts/fetch-assets` | Download large assets declared in the manifest. |
| `./scripts/clean [--all]` | Remove build artifacts. |

`enter` also takes a one-off command after the service name — `./scripts/enter dev
ros2 topic list` runs it in the container and exits. Use that instead of reaching for
`docker compose run`, which is the working-around these entry points exist to prevent.
Shell syntax needs a shell: `./scripts/enter dev bash -lc 'colcon list | wc -l'`.

The quality gate before any handoff:

```bash
./scripts/lint && ./scripts/build && ./scripts/test
```

## Choosing where things run

`CITE_ENV` in your `.env`:

- `auto` — native ROS if present, container otherwise. The default; leave it.
- `native` — never use a container. For a Linux workstation with ROS installed.
- `docker` — always use the container, even on Linux. For reproducing a CI result.

## GUI

On the Linux workstation, `./scripts/sim` opens the Gazebo GUI through the `gui`
compose service. From macOS it will refuse, because X11 passthrough from a
container to macOS is more trouble than it is worth. Run headless and inspect
the result with Foxglove instead. CI and the review agents also run headless and
work from recorded MCAP bags rather than a live view, so a headless run is the
same view they get.

## Set your ROS_DOMAIN_ID

```bash
cp .env.example .env      # bootstrap does this for you
# then edit ROS_DOMAIN_ID to a value nobody else in the lab is using
```

A domain collision makes someone else's nodes appear in your graph. The symptom
is behaviour that no code in the repository explains, and it costs hours.

**A checkout claims two domains, not one.** A twin pair runs each side in its own
domain, because both sides carry byte-identical names by rule and one ROS graph
cannot hold two of them ([ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md)).
`scripts/_lib.sh` allocates an odd base per checkout and the counterpart takes
the even number above it, so no counterpart can ever land on another checkout's
plant. What you get by default — from `./scripts/enter`, `./scripts/scenario` and
`./scripts/sim` without `--pair` alike — is the **plant**, which is the side
every script here addresses; `./scripts/sim --pair` starts both sides, each on
its own domain, and leaves your shell on the plant's. `./scripts/doctor` prints it and says which side it is;
`docs/operations/troubleshooting.md` has the recipe for resolving any side's
domain from the plan.

## Physical hardware

Nothing commands a physical arm unless you set `CITE_ALLOW_HARDWARE=1`
explicitly, and hardware work belongs to Phase 2. Until then, if a command
appears to want hardware access, that is a bug — report it.

## When it breaks

1. `./scripts/doctor`
2. `./scripts/clean && ./scripts/bootstrap` — a stale build explains a
   surprising share of inexplicable failures.
3. Work through [`../operations/troubleshooting.md`](../operations/troubleshooting.md).
   It is organised by symptom — environment, build, runtime — and each entry is
   there because that specific problem cost someone a day already.
