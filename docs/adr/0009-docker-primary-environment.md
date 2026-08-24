# ADR-0009: Make Docker the primary environment

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0002, ADR-0013, `docs/onboarding/getting-started.md`

## Context

Contributors do not share an operating system. Authoring happens on macOS and Linux;
building and running require Ubuntu 24.04, because ROS 2 Jazzy, Gazebo Harmonic, and
MoveIt 2 have no macOS or Windows support. Physical robot work happens on a Linux
workstation in the lab.

The v1 workspace had no environment definition at all. It worked on the machine where it
was developed, and the question of whether it worked anywhere else was never asked.

CI adds a second requirement: whatever CI runs must be what a developer runs, or "green in
CI, broken locally" becomes possible and nobody trusts either signal.

## Options considered

### Option A — Native installation, documented
Everyone installs ROS 2 Jazzy on Ubuntu 24.04 following a guide. Simplest for GPU, USB
devices, and Gazebo GUI. Rejected as the *primary* path: every machine drifts, CI parity
cannot be guaranteed, and macOS contributors are excluded entirely.

### Option B — Docker only
No native path at all. Rejected: hardware debugging — USB devices, real-time kernel
behaviour, GPU drivers — is genuinely harder through a container, and Phase 2 makes that
routine work.

### Option C — Docker primary, native supported
One image used by developers and CI. Native installation documented and supported for
hardware work. Scripts route automatically. Chosen.

## Decision

**Docker is the primary environment.** One image (`infra/docker/Dockerfile`) serves
development and CI. Three compose services expose it: `dev` (headless), `gui` (display
passthrough), `hardware` (host networking and device passthrough).

`scripts/_lib.sh` provides `require_ros_env`, which re-executes a script inside the
container when the host has no ROS. **A developer never chooses.** `./scripts/build`
works identically from a MacBook and from the Linux workstation. `CITE_ENV` overrides the
choice when someone needs to.

Native installation on Ubuntu 24.04 remains supported and is used for hardware work.

## Consequences

### What this gets us
- One command to a working environment, on any machine.
- CI and development run the same image, so the two signals cannot disagree about the
  environment.
- macOS contributors are first-class for everything except GUI simulation.
- The environment is versioned with the code.

### What this costs us
- A large image, and a first build measured in minutes. Mitigated by layer caching and by
  warning before an unexpected first-run build, but the first experience is slow.
- File I/O through a bind mount is slower on macOS. Build artifacts live in named volumes
  to avoid the worst of it, which is a complication a native setup would not need.
- GUI passthrough works on Linux and is not worth the trouble on macOS. macOS contributors
  run headless and inspect with Foxglove — which is what CI and the review agents see, so
  it is not purely a loss.
- Hardware access needs privileged containers and host networking, weakening isolation
  exactly where the physical robots are.
- Docker must be installed and running, which on macOS means Docker Desktop and its
  licensing considerations.

### What we will have to revisit
If real-time control requirements make container scheduling a problem, the hardware path
may become native-only while development and CI stay containerized. The script contract
already allows this via `CITE_ENV=native`.
