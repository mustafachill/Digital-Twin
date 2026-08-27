# ADR-0003: Target Gazebo Harmonic

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0001, ADR-0002, charter §6.1

## Context

The v1 workspace ran on Gazebo Classic 11, which **reached end of life in January 2025**
and receives no further fixes, including security fixes. Building a multi-year
institutional platform on an unmaintained simulator is not defensible to a reviewer, a
funder, or a maintainer in 2029.

The replacement is the Gazebo Sim line. Harmonic is its LTS release, supported to **May
2029**, and is the version packaged against ROS 2 Jazzy — whose support also ends May 2029.
The two lifetimes align exactly, which is worth more than either date alone: the stack ages
as one unit rather than forcing a partial migration.

The decision carried one serious open risk at the time it was made: whether UFACTORY's
`xarm_ros2` supported Gazebo Sim at all. The vendor's README links to Gazebo Classic
installation instructions, which suggested it did not.

**That risk was resolved before this record was written.** The `jazzy` branch of
`xArm-Developer/xarm_ros2` declares `gz_sim_vendor`, `gz_ros2_control`, `ros_gz_sim`, and
`ros_gz_bridge` in `xarm_gazebo/package.xml`, with no reference to `gazebo_ros`,
`gazebo_ros2_control`, or `gazebo_dev`. The branch targets Gazebo Sim; the README is
stale. See `docs/reference/toolchain.md`.

> **Correction appended 2026-08-24** (the decision is unchanged; a supporting fact was
> wrong). The paragraph above is right that the `jazzy` branch targets Gazebo Sim —
> re-verified against
> `raw.githubusercontent.com/xArm-Developer/xarm_ros2/jazzy/xarm_gazebo/package.xml`. It is
> **wrong that the `jazzy` README is stale about Gazebo**: that README states *"Classic
> Gazebo is no longer supported. Gazebo Harmonic is supported instead"* and links to the
> Harmonic install guide. The Classic link is in the **`humble`** branch README. The
> mistaken premise in "Context" above — that the vendor README suggested Classic was the
> only path — is preserved as written, per the rule that ADRs are not rewritten, but it
> should not be cited as fact. See `docs/reference/toolchain.md`.

## Options considered

### Option A — Stay on Gazebo Classic
Everything in v1 already runs there, and the IFRA conveyor plugin works. Rejected: end of
life, and ADR-0001 discards the v1 tree anyway, so the compatibility argument buys almost
nothing.

### Option B — Gazebo Harmonic (LTS)
Supported to May 2029 — the same month as ROS 2 Jazzy — with first-class integration
through `ros_gz` and actively developed physics and sensor systems. Chosen.

### Option C — NVIDIA Isaac Sim
Photorealistic rendering, GPU physics, synthetic data generation, and a strong story for
future machine-learning work. Rejected **for now**: it requires RTX-class GPUs on every
machine that runs a simulation, has a much steeper learning curve, and its ROS 2
integration is less direct than `ros_gz`. The cost lands on every contributor; the benefit
is concentrated in work this project has not scheduled. Worth revisiting if photorealistic
synthetic data becomes a project goal.

## Decision

Target **Gazebo Harmonic (LTS)**, integrated through `ros_gz_sim` and `ros_gz_bridge`,
with `gz_ros2_control` providing the simulated hardware interface.

## Consequences

### What this gets us
- A supported simulator whose lifetime matches the platform's.
- Vendor xArm support on the same combination, confirmed rather than assumed.
- Modern sensor and physics systems, and a migration path to later Gazebo releases.

### What this costs us
- **The conveyor plugin is a rewrite, not a port.** The IFRA plugin used in v1 is a Gazebo
  Classic plugin and will not load under Gazebo Sim. A survey in August 2026 found no
  maintained drop-in replacement — only worked examples, not a package to depend on. The
  established pattern transfers conceptually: a belt link on a prismatic joint that resets
  to its start while carried objects keep their displacement. We implement it as a
  first-party Gazebo Sim system plugin with a typed ROS 2 interface. If a maintained
  package appears later, reconsider — the interface is ours either way.

  > **Survey re-run 2026-08-24, and the bullet above overstates its case.** GitHub search
  > (`conveyor gazebo harmonic`, `gz sim conveyor`, `conveyor_belt ros2`, by name and
  > description) found:
  > - `IFRA-Cranfield/IFRA_ConveyorBelt` — 51 stars, last push 2026-05-20, but its default
  >   branch is `humble` and its README states it is tested only on Ubuntu 22.04 with
  >   ROS 2 Humble. This confirms it is not a Harmonic option.
  > - **`mzahana/conveyor_sim_ros2` — 9 stars, last push 2025-08-26 — *is* a ROS 2 Jazzy +
  >   Gazebo Harmonic conveyor package** ("does not work with earlier versions of Gazebo").
  >   It is therefore not true that nothing exists.
  >
  > Whether a 9-star, single-maintainer package last touched a year ago is something this
  > project should depend on is a judgement, and the decision to write our own still looks
  > defensible. But it should rest on that judgement, stated openly, rather than on the
  > claim that no alternative exists. Evaluate `conveyor_sim_ros2` before writing the
  > plugin in Phase 1.C.
  >
  > **Evaluated 2026-08-24. We write our own — for the interface, not for the physics.**
  >
  > What it gets right: it genuinely targets ROS 2 Jazzy and Gazebo Harmonic, it is MIT
  > licensed, and it works. The maintenance concern above turned out not to be the
  > deciding factor.
  >
  > What rules it out is its contract. It is controlled by publishing a
  > `std_msgs/msg/Float64` to a fixed `/conveyor/cmd_vel`, and that is disqualifying three
  > times over: an untyped scalar carrying a command is what `CLAUDE.md` §4 prohibits and
  > what ADR-0010 exists to prevent; a hardcoded global topic cannot be instantiated three
  > times under `/cite/<zone>/<asset_id>/command`, which is the naming P2 is made of; and
  > it reports no state, so a belt commanded to run and not moving is invisible — exactly
  > the failure a line must notice. It is also a model plus a bridge rather than a system
  > plugin, so it cannot be attached per-asset to a world generated from L0.
  >
  > Adapting it would mean wrapping it in a typed, namespaced interface that reports
  > measured as well as commanded speed — which is most of the work, with a dependency
  > still underneath. The belt physics is the small part; the contract is the point.
- Every sensor must be re-specified against the Gazebo Sim sensor system and bridged
  through `ros_gz_bridge`. Classic's `libgazebo_ros_*` plugins do not exist here.
- World and model files are regenerated, not ported — which ADR-0004 requires regardless.
- Contributors with Gazebo Classic experience must relearn. The two share a name and very
  little else.

### What we will have to revisit
When Harmonic approaches end of life in May 2029, together with ADR-0002 — the two expire
in the same month and should move together. Also revisit if the
project takes on photorealistic perception or learned-policy work, where Option C's
trade-off changes.
