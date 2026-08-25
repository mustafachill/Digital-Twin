# Architecture Decision Records

An ADR records **one decision**: the situation that forced it, the options that were
genuinely considered, what was chosen, and what that choice costs.

## Why we keep them

A codebase shows you *what* was decided. It never shows you *why*, which options were
weighed, or what the decision was expected to cost. Without that, every past decision
looks arbitrary to whoever arrives next — and arbitrary-looking decisions get reversed by
people who do not know what they are paying for.

The previous iteration of this project had no ADRs. Its architecture drifted three times
in six months, and nobody could reconstruct why any of the three had seemed right.

## When you must write one

- Choosing between technologies, frameworks, or libraries.
- Establishing or changing an architectural boundary.
- Adopting a convention that others must follow.
- **Reversing or superseding an existing ADR.**

Write it **before** implementing (charter §10.3). An ADR written afterwards is a
justification, and justifications are written to defend rather than to weigh.

## When you should not

Ordinary implementation choices with no downstream consequence. If nobody would be
surprised, and reversing it later would be cheap, it is not an ADR.

## How

Copy [`0000-template.md`](0000-template.md), take the next free number, keep it short.
A good ADR is one page. If yours needs five, it is probably two decisions.

Numbers are permanent. A superseded ADR is **never deleted or rewritten** — its status
changes to `Superseded by NNNN` and it stays exactly as written. The record of a decision
that turned out wrong is more valuable than the record of one that turned out right.

## Status values

| Status | Meaning |
|---|---|
| `Proposed` | Written, under discussion, not yet binding. |
| `Accepted` | Binding. Violating it is an `ESCALATE`, not a code-review finding. |
| `Superseded by NNNN` | Replaced. Kept for the record. |
| `Deprecated` | No longer applies, and nothing replaced it. |

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-rebuild-rather-than-migrate.md) | Rebuild rather than migrate the v1 workspace | Accepted |
| [0002](0002-ros2-jazzy.md) | Target ROS 2 Jazzy | Accepted |
| [0003](0003-gazebo-harmonic.md) | Target Gazebo Harmonic | Accepted |
| [0004](0004-facility-model-single-source-of-truth.md) | Generate all artifacts from one facility model | Accepted |
| [0005](0005-ros2-control-sim-real-boundary.md) | Use ros2_control as the simulation/hardware boundary | Accepted |
| [0006](0006-moveit2-motion-planning.md) | Use MoveIt 2 for motion planning | Accepted |
| [0007](0007-behaviour-trees-for-orchestration.md) | Orchestrate with behaviour trees | Accepted |
| [0008](0008-external-dependencies-via-vcstool.md) | Consume external sources via a pinned manifest | Accepted |
| [0009](0009-docker-primary-environment.md) | Make Docker the primary environment | Accepted |
| [0010](0010-typed-ros-interfaces.md) | Require typed ROS interfaces | Accepted |
| [0011](0011-twin-maturity-model-and-modes.md) | Adopt the twin maturity model and operating modes | Accepted |
| [0012](0012-large-asset-storage.md) | Store large assets by manifest, not Git LFS | Accepted |
| [0013](0013-host-agnostic-tooling.md) | Keep a host-agnostic tooling layer | Accepted |
| [0014](0014-monorepo.md) | Use a monorepo | Accepted |
| [0015](0015-english-only.md) | Write everything in English | Accepted |
| [0016](0016-iso-23247-alignment.md) | Align the architecture with ISO 23247 | Accepted |
| [0017](0017-mcap-recording-format.md) | Record with rosbag2 and MCAP storage | Accepted |
| [0018](0018-visualization-rviz-and-foxglove.md) | RViz 2 for debugging, Foxglove for shareable inspection | Accepted |
| [0019](0019-language-split-cpp-python.md) | C++ for control paths, Python for orchestration and tooling | Accepted |
| [0020](0020-facility-model-conventions.md) | Fix the facility model's units, axes, and file layout | Accepted |
| [0021](0021-generated-artifacts-are-committed.md) | Commit generated artifacts, in one generated package | Accepted |
| [0022](0022-gripper-as-ros2-control-controller.md) | Drive the gripper through `ros2_control`, not a separate action server | Accepted |
| [0023](0023-simulated-grasping-via-attachment.md) | Simulate a grasp by attachment, triggered by contact | Accepted |
| [0024](0024-handoff-split-between-l3-and-l4.md) | Split handoff — L4 owns the negotiation, L3 owns the motion | Accepted |
| [0025](0025-qos-profiles-in-cite-interfaces.md) | Ship the QoS profiles as a library inside `cite_interfaces` | Accepted |
