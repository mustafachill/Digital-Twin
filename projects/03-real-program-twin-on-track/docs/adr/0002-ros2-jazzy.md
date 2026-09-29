# ADR-0002: Target ROS 2 Jazzy

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0003, charter §6

## Context

The v1 workspace targeted ROS 2 Humble on Ubuntu 22.04. The project is a multi-year
institutional platform, so the middleware choice must still be supported when students who
have not yet joined are maintaining it. The simulator decision (ADR-0003) and the ROS
distribution are not independent: each Gazebo release has one ROS 2 release it is packaged
and tested against.

## Options considered

### Option A — Stay on Humble
No Ubuntu upgrade, and the existing xArm and MoveIt setup is known to work. Rejected: its
support window ends well before this project does, and pairing it with Gazebo Harmonic is
an unsupported combination requiring `ros_gz` to be built from source — a permanent
maintenance liability sitting under the whole stack.

### Option B — Jazzy Jalisco
LTS, Ubuntu 24.04, supported into 2029. The distribution Gazebo Harmonic is packaged
against. Chosen.

### Option C — Kilted or Rolling
Newest features and the shortest path to future Gazebo releases. Rejected: APIs move, and
neither MoveIt nor vendor robot support tracks Rolling reliably. Acceptable for a research
spike; not for an institutional platform maintained by rotating contributors.

## Decision

Target **ROS 2 Jazzy Jalisco on Ubuntu 24.04 LTS**, paired with Gazebo Harmonic.

## Consequences

### What this gets us
- A supported, packaged, tested combination — `ros-jazzy-ros-gz` and
  `ros-jazzy-gz-ros2-control` install from apt rather than being built and maintained.
- A support window that outlasts the roadmap in charter §8.
- Vendor support: the `jazzy` branch of `xarm_ros2` exists and targets Gazebo Sim.

### What this costs us
- Ubuntu 24.04 on every development and lab machine. The container (ADR-0009) absorbs this
  for developers, but the workstation driving physical hardware must actually be upgraded.
- Humble-era tutorials, forum answers, and package versions no longer apply directly. This
  is a real friction cost for contributors learning ROS 2 from older material.
- The v1 tree does not build under it — but ADR-0001 already discards that tree.

### What we will have to revisit
When Jazzy approaches end of life, or when a Gazebo release we need is packaged only
against a newer distribution. Both Jazzy and Gazebo Harmonic reach end of life in **May
2029**, so expect a single coordinated move of ADR-0002 and ADR-0003 together, planned well
before that date.
