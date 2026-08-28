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

## Corrections

A **correction** is not a supersession. It is what you write when the decision holds but a
supporting claim in the record turns out to be false — an inference that was written down
as a fact and later measured. The decision survives; only the claim is wrong.

The same rule applies as for supersession: **nothing is rewritten.** A record that quietly
repairs itself teaches the reader nothing, and the most valuable thing in a corrected ADR
is how the wrong claim survived review in the first place. So:

1. Add a `## Correction — YYYY-MM-DD: <what was wrong>` section immediately **after** the
   metadata block and **before** `## Context`, so nobody can read the false text without
   first meeting the correction.
2. Leave the false sentences exactly where they are, each followed by
   `**[Corrected YYYY-MM-DD — see the Correction section above.]**`.
3. Qualify the `**Status:**` line with what stands and what does not, and name the
   correction section. Name it rather than linking to it: the heading carries an em
   dash and a colon, and Markdown renderers do not agree on the anchor that produces.
4. State plainly what survives. A correction that leaves a reader unsure whether the
   decision still binds has replaced one ambiguity with another.
5. End the correction with **how the error survived** — the untested inference, the silent
   failure mode, the missing assertion. That is the part that transfers.
6. Mark the index row `Accepted (corrected YYYY-MM-DD)`.
7. **A second correction goes above the first**, so the newest state is the first thing a
   reader meets, and the earlier correction is left exactly as it stands. Say in one line
   that it is there. Status and index row list every date:
   `Accepted (corrected YYYY-MM-DD and YYYY-MM-DD)`.
   **An earlier correction is not exempt from being corrected.** ADR-0032's 2026-08-26
   correction asserted that arithmetic downstream of the constant it moved was independent
   of it, and it was not — that is what the second correction on that record fixes.

If the *decision* is what turned out wrong, this is not a correction. Write a new ADR and
set this one to `Superseded by NNNN`.

[ADR-0022](0022-gripper-as-ros2-control-controller.md) is the worked example of a
correction. [ADR-0023](0023-simulated-grasping-via-attachment.md) is the worked example of
the distinction: it was corrected on 2026-08-25 for a claim, and superseded by
[ADR-0029](0029-simulated-grasping-by-friction.md) the same day when measurement showed the
decision itself was wrong. Its correction section is left in place — a superseded record is
not rewritten either.

## Status values

| Status | Meaning |
|---|---|
| `Proposed` | Written, under discussion, not yet binding. |
| `Accepted` | Binding. Violating it is an `ESCALATE`, not a code-review finding. |
| `Superseded by NNNN` | Replaced. Kept for the record. |
| `Deprecated` | No longer applies, and nothing replaced it. |
| `Accepted (corrected YYYY-MM-DD)` | Binding, and a supporting claim in it was measured false. See **Corrections** above. Several dates mean several corrections, newest first in the record. |

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
| [0022](0022-gripper-as-ros2-control-controller.md) | Drive the gripper through `ros2_control`, not a separate action server | Accepted (corrected 2026-08-25) |
| [0023](0023-simulated-grasping-via-attachment.md) | Simulate a grasp by attachment, triggered by contact | Superseded by [0029](0029-simulated-grasping-by-friction.md) |
| [0024](0024-handoff-split-between-l3-and-l4.md) | Split handoff — L4 owns the negotiation, L3 owns the motion | Accepted |
| [0025](0025-qos-profiles-in-cite-interfaces.md) | Ship the QoS profiles as a library inside `cite_interfaces` | Accepted |
| [0026](0026-joint-space-goals-on-under-six-dof-arms.md) | Plan to joint-space goals obtained by solving IK on the exact pose | Accepted (corrected 2026-08-27) |
| [0027](0027-pilz-planning-pipeline.md) | Plan station-to-station motion with Pilz, keeping OMPL as the fallback | Accepted (corrected 2026-08-26 and 2026-08-27) |
| [0028](0028-convex-hull-collision-meshes.md) | Generate convex-hull collision meshes as project assets, bound through L0 | Proposed |
| [0029](0029-simulated-grasping-by-friction.md) | Rest simulated grasping on friction, and remove the attachment plugin | Accepted (corrected 2026-08-26) |
| [0030](0030-facility-model-describes-the-workpiece.md) | Describe the work-piece in the facility model, as an asset type with no instances | Accepted |
| [0031](0031-refuse-direct-handoff-without-orientation-certainty.md) | Refuse a direct arm-to-arm handoff at plan time until a grasp holds an orientation | Accepted (corrected 2026-08-26) |
| [0032](0032-index-the-belt.md) | Index the belt — stop it on the trigger that starts a station, restart it on `CompleteHandoff` | Accepted (corrected 2026-08-26 and 2026-08-27) |
| [0033](0033-derive-the-index-standoff-from-the-workpiece.md) | Sense against the part's body, and derive an indexing beam's stand-off from it | Accepted |
| [0034](0034-process-lifecycle-mechanism-in-cite-runtime.md) | Compensate two rclpy shutdown races, in a new `cite_runtime` package | Accepted |
| [0035](0035-check-the-english-only-rule-by-character-signal.md) | Check the English-only rule by character signal, across the repository | Accepted (corrected 2026-08-27) |
| [0036](0036-execution-side-trajectory-tolerances.md) | Detect a mistracked trajectory at execution, with tolerances declared in L0 | Proposed (corrected 2026-08-27) |
| [0037](0037-classify-an-abort-before-any-recovery-motion.md) | Classify an execution abort before any recovery motion is dispatched | Accepted (amended 2026-08-27) |
| [0038](0038-stop-the-line-without-ending-the-process.md) | Stop the line without ending the process, and gate resumption on re-armability | Proposed (amended 2026-08-27) |
| [0039](0039-report-a-station-that-cannot-be-triggered.md) | Report a station that cannot be triggered, as a line state of its own | Proposed (corrected 2026-08-28) |
