# Toolchain reference

Authoritative documentation for every tool in the stack, at **the version we actually
use**. ROS and Gazebo documentation is per-release; a generic link silently shows the
reader the wrong one.

- **Related:** [`../../CLAUDE.md`](../../CLAUDE.md) §6, [`../adr/`](../adr/README.md)

## Core stack

| Tool | Version | Documentation |
|---|---|---|
| Ubuntu | 24.04 LTS (Noble) | <https://releases.ubuntu.com/24.04/> |
| ROS 2 | Jazzy Jalisco | <https://docs.ros.org/en/jazzy/> |
| Gazebo | Harmonic (LTS) | <https://gazebosim.org/docs/harmonic/> |

ROS 2 Jazzy and Gazebo Harmonic are both LTS releases, and both are supported to **May
2029** — the same month, so the stack ages as one unit. They are the officially paired
combination — see
[ADR-0002](../adr/0002-ros2-jazzy.md) and [ADR-0003](../adr/0003-gazebo-harmonic.md).

> **Support dates — verified 2026-08-24.** Jazzy Jalisco: released 23 May 2024, EOL
> **May 2029**, per the distribution table at
> <https://docs.ros.org/en/jazzy/Releases.html>. Gazebo Harmonic: released 2023-09, EOL
> **2029-05**, per the release-support chart at
> <https://gazebosim.org/docs/harmonic/releases/>. The two windows do end in the same
> month, which is what ADR-0002 and ADR-0003 rest on.

**Gazebo Classic reached end of life on 29 January 2025** and receives no further fixes.
Any tutorial referencing `gazebo_ros`, `libgazebo_ros_*` plugins, or `.world` files with
Classic plugin syntax does not apply here, however well it is written.

> **Verified 2026-08-24** against <https://classic.gazebosim.org/>, which carries a
> site-wide end-of-life banner and states in the Gazebo 11 release announcement that the
> release has "an end-of-life on January 29, 2025".

## Simulation integration

| Package | Purpose | Documentation |
|---|---|---|
| `ros_gz_sim` | Launch and manage Gazebo from ROS 2 | <https://gazebosim.org/docs/harmonic/ros2_integration/> |
| `ros_gz_bridge` | Bridge topics between ROS 2 and Gazebo transport | <https://gazebosim.org/docs/harmonic/ros2_integration/> |
| Installation matrix | Which Gazebo pairs with which ROS 2 | <https://gazebosim.org/docs/latest/ros_installation/> |

## Control

| Package | Purpose | Documentation |
|---|---|---|
| `ros2_control` | Controller framework, hardware abstraction | <https://control.ros.org/jazzy/> |
| `gz_ros2_control` | Gazebo Sim hardware interface | <https://control.ros.org/jazzy/doc/gz_ros2_control/doc/index.html> |
| `ros2_controllers` | Standard controllers | <https://control.ros.org/jazzy/doc/ros2_controllers/doc/controllers_index.html> |

`ros2_control` is the simulation/hardware boundary and therefore the most
architecturally load-bearing dependency in the project —
[ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md).

## Motion planning

| Tool | Documentation |
|---|---|
| MoveIt 2 | <https://moveit.picknik.ai/main/index.html> |
| MoveIt 2 tutorials | <https://moveit.picknik.ai/main/doc/tutorials/tutorials.html> |

## Orchestration

| Tool | Documentation |
|---|---|
| BehaviorTree.CPP v4 | <https://www.behaviortree.dev/> |
| ROS 2 integration guide | <https://www.behaviortree.dev/docs/ros2_integration/> |
| ROS package index | <https://index.ros.org/p/behaviortree_cpp/> |
| Groot2 (visual editor and live monitor) | <https://www.behaviortree.dev/groot/> |

## Robot support

| Repository | Notes |
|---|---|
| `xArm-Developer/xarm_ros2` | <https://github.com/xArm-Developer/xarm_ros2> |

**The `jazzy` branch targets Gazebo Sim (Harmonic), not Gazebo Classic.** Verified
2026-08-24 by fetching
`https://raw.githubusercontent.com/xArm-Developer/xarm_ros2/jazzy/xarm_gazebo/package.xml`:
it declares `gz_sim_vendor`, `sdformat_vendor`, `gz_ros2_control`, `ros_gz_sim`, and
`ros_gz_bridge`, and contains no occurrence of `gazebo_ros`, `gazebo_ros2_control`, or
`gazebo_dev`.

> **Correction, 2026-08-24.** Earlier versions of this page, and
> [ADR-0003](../adr/0003-gazebo-harmonic.md), stated that the upstream README "links to
> Gazebo Classic installation instructions and is stale". **That is true of the `humble`
> branch, not of `jazzy`.** The `jazzy` `ReadMe.md` says in its changelog *"Classic Gazebo
> is no longer supported. Gazebo Harmonic is supported instead"* and its §3.3 links to
> <https://gazebosim.org/docs/harmonic/install_ubuntu/>. The `humble` branch README §3.3 is
> the one linking to `classic.gazebosim.org`. Do not repeat the original claim.
>
> One genuine Classic residue does remain in the `jazzy` README: §5.8 still suggests
> installing `gazebo_ros2_control` from source, which is the Classic-era package and does
> not apply. Treat that paragraph, not the whole document, as stale.

We use the `jazzy` branch, declared in
[`../../external/cite.repos`](../../external/cite.repos)
([ADR-0008](../adr/0008-external-dependencies-via-vcstool.md)). **Pinned to
`3dc2b5e8294758d96b54b15fa5920d581b7cbb3d` (`jazzy` head, 2026-08-11) on 2026-08-24**,
which closed the last Phase 1.A gate. The pin was made only after the build and a runtime
check, not before:

| Check | Result |
|---|---|
| `colcon build` of the whole manifest, in the container, arm64 | 12 packages, all succeed |
| `xarm_device` expansion with `gz_ros2_control/GazeboSimSystem` | one root link, joints prefixed `arm_1_joint1..5`, `arm_1_drive_joint` |
| Mesh URIs under that plugin | `file://` absolute, so no `GZ_SIM_RESOURCE_PATH` dependency |
| Spawn into Gazebo Harmonic headless | 6 joints, 12 hardware interfaces present |
| Controller activation | `joint_state_broadcaster`, `joint_trajectory_controller`, `GripperActionController` all active |
| `FollowJointTrajectory` goal | executed to `SUCCEEDED`; shutdown left no orphans |

Two things found during that verification are worth carrying forward:

- **`xarm_ros2` has a git submodule**, `xarm_sdk/cxx`. `./scripts/bootstrap` uses
  `vcs import --recursive` for this; without the flag the directory is empty and the build
  fails on `xarm_sdk`. The pin above still fixes it exactly, because the submodule pointer
  is part of the pinned commit.
- **The gripper's mimic-joint coupling emits a Gazebo Classic plugin**
  (`libgazebo_mimic_joint_plugin.so`) that cannot load under Harmonic, and this Harmonic
  build's physics engine reports that it does not support mimic constraints either. The
  URDF `<mimic>` tags are present, so `ros2_control` is what has to carry the coupling.
  See [ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md).

Branches on the upstream repository, from `git ls-remote --heads` on 2026-08-24: `foxy`,
`galactic`, `humble`, `humble_gz`, `jazzy`, `master`, `rolling`.

**Beware of name collisions when searching.** A GitHub search for `xarm_ros2 in:name` on
2026-08-24 returned **44** repositories. Several are unrelated — including
`DiegoCarvajal98/xarm_ros2`, "ROS2 packages for the xArm ESP32 robot", which is the
Hiwonder hobby arm, not a UFACTORY product. Ours is `xArm-Developer/xarm_ros2`.

## Data and visualization

| Tool | Purpose | Documentation |
|---|---|---|
| `rosbag2` | Recording and replay | <https://docs.ros.org/en/jazzy/p/rosbag2/> |
| MCAP | Storage format | <https://mcap.dev/> |
| RViz 2 | ROS-native visualization | <https://docs.ros.org/en/jazzy/p/rviz2/> |
| Foxglove | Browser-based visualization and bag playback | <https://docs.foxglove.dev/> |

## Package availability — verified

The apt package names in `infra/docker/Dockerfile` were verified on **2026-08-24** against
`ros:jazzy-ros-base-noble` and the OSRF Gazebo repository, rather than assumed —
by running `apt-cache policy` for each name inside that image:

```bash
docker run --rm ros:jazzy-ros-base-noble bash -c 'apt-get update -qq; apt-cache policy <pkg>'
```

All **21** `ros-jazzy-*` packages listed there resolve. Candidate versions at the time of
checking included `ros-jazzy-behaviortree-cpp` **4.9.0** (confirming the v4 line),
`ros-jazzy-gz-ros2-control` 1.2.19, `ros-jazzy-ros-gz` 1.0.22, `ros-jazzy-moveit` 2.12.4,
`ros-jazzy-ros2-control` 4.45.2, and `ros-jazzy-rosbag2-storage-mcap` 0.26.11.
`gz-harmonic` resolves at **1.0.0-1~noble** from
`packages.osrfoundation.org/gazebo/ubuntu-stable noble`.

Re-verify when changing the base image or adding a package — a name that does not exist
fails the image build, which is a slow way to learn it.

**`perf` is not available in the container**, and this was verified rather than assumed.
`linux-tools-common` installs only a wrapper that fails against the container's kernel
(`perf not found for kernel 6.10.14-linuxkit` under Docker Desktop), so it is deliberately
not installed. Use `valgrind --tool=callgrind` and `gdb`, which do work. Genuine `perf`
profiling requires a native Linux host with matching kernel tools — run it there with
`CITE_ENV=native`.

## Supply-chain scanning

`osv-scanner` **v2.5.1** is installed in the container image, pinned by version and by
SHA-256 so that a version bump forces updating the hash. Run it through
[`./scripts/audit-deps`](../../scripts/audit-deps), never directly — the script encodes
two things that are easy to get wrong:

1. **Our requirements files are not named `requirements.txt`**, so the lockfile type must
   be passed explicitly (`-L requirements.txt:<path>`). Without it osv-scanner reports
   *"no package sources found"*, which reads exactly like a clean result. Verified
   2026-08-24: the naive invocation finds **zero** packages in this repository.
2. **Coverage is partial**, and the script says so on every run.

| Layer | Covered |
|---|---|
| Python tooling (`requirements/*.txt`) | Yes, by default |
| Container image OS packages | Opt-in, `--image` (exports the image first, so it is slow) |
| ROS packages (`ros-jazzy-*`) | **No** — no OSV ecosystem covers them |
| Source pinned in `external/cite.repos` | **No** — no lockfile, and source analysis is unsupported |

The uncovered layers are *unmeasured*, not clean. Never report them as passing.

**On the image scan's numbers.** A `--image` run reports several hundred findings against
the Ubuntu 24.04 base and the ROS layer. That is the base image's known-CVE surface, not a
measure of this project — most are fixed by rebuilding on a current base rather than by
changing anything here. It becomes materially relevant at Phase 4, when remote access gives
the container an exposed attack surface. This is why the image scan is opt-in: several
hundred findings on every CI run would train everyone to ignore the tool.

## Build and dependency tooling

| Tool | Purpose | Documentation |
|---|---|---|
| colcon | Workspace build | <https://colcon.readthedocs.io/> |
| `vcstool` | Multi-repository management | <https://github.com/dirk-thomas/vcstool> |
| `rosdep` | System dependency resolution | <https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Rosdep.html> |

Invoke these through [the script contract](../../CLAUDE.md#7-commands), not directly.

## Description formats

| Format | Documentation |
|---|---|
| URDF | <https://docs.ros.org/en/jazzy/Tutorials/Intermediate/URDF/URDF-Main.html> |
| Xacro | <https://docs.ros.org/en/jazzy/Tutorials/Intermediate/URDF/Using-Xacro-to-Clean-Up-a-URDF-File.html> |
| SDF | <http://sdformat.org/spec> |

We generate all of these from the facility model
([ADR-0004](../adr/0004-facility-model-single-source-of-truth.md)). Read these to
understand what the generator emits, not to hand-author.

## A note on tutorials

Most ROS 2 material online targets Humble and Gazebo Classic. Before following any
tutorial, check three things:

1. Which ROS 2 distribution — Humble examples often do not run on Jazzy unmodified.
2. Which Gazebo — `gazebo_ros` means Classic and does not apply here at all.
3. Whether it hand-authors artifacts we generate. The technique may still be worth
   understanding; the workflow is not ours.
