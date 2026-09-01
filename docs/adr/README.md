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

## In-place markers

Rule 2 above puts `**[Corrected YYYY-MM-DD — …]**` beside a sentence that is now false. Four
markers of that shape are in use, and until 2026-09-01 only the first was written down here —
which is how a fourth spelling got invented without anyone noticing there were three.

They differ in **what happened to the sentence**, and picking the wrong one tells the reader
the wrong thing about why it is still there.

| Marker | Use it when | What the reader learns |
|---|---|---|
| `**[Corrected YYYY-MM-DD — …]**` | The sentence was **wrong when written**, and something later measured it. | Do not believe it. See the Correction section. |
| `**[Amended YYYY-MM-DD — …]**` | The sentence was right and the **decision it states has been changed** by a later amendment. | It is superseded by a decision, not by a measurement. |
| `**[Overtaken YYYY-MM-DD — …]**` | The sentence was right when written and **events since made it false**, with nobody wrong. A count that moved, a default that flipped, a campaign that has since been run. | It is stale, not mistaken. |
| `**[Replaced YYYY-MM-DD, kept for the record:]** *"…"*` | A **status line** was rewritten and the old wording is quoted after the marker. | This is what the status used to say. |

Three rules about them.

1. **`Superseded` is a status value, not an in-place marker.** It means *this whole record
   was replaced by ADR NNNN*, and using the word inside a record's body — especially inside
   the status block of an `Accepted` record — says the opposite of what is true. That is why
   the fourth row is `Replaced`. One in-place use survives, in
   [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md)'s status block, and it
   stays: a record's text is not rewritten to satisfy a convention written after it.
2. **A marker never edits the sentence it marks.** It stands after it, for the same reason
   corrections do not rewrite: how the wrong claim survived is the valuable part.
3. **A marker is not a substitute for a section.** `Corrected` and `Amended` require the
   section rule 1 describes; `Overtaken` and `Replaced` do not, because nothing was measured
   false — but both must name the record or the change that overtook them.

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
| [0004](0004-facility-model-single-source-of-truth.md) | Generate all artifacts from one facility model | Accepted (amended 2026-08-29) |
| [0005](0005-ros2-control-sim-real-boundary.md) | Use ros2_control as the simulation/hardware boundary | Accepted |
| [0006](0006-moveit2-motion-planning.md) | Use MoveIt 2 for motion planning | Accepted |
| [0007](0007-behaviour-trees-for-orchestration.md) | Orchestrate with behaviour trees | Accepted |
| [0008](0008-external-dependencies-via-vcstool.md) | Consume external sources via a pinned manifest | Accepted |
| [0009](0009-docker-primary-environment.md) | Make Docker the primary environment | Accepted |
| [0010](0010-typed-ros-interfaces.md) | Require typed ROS interfaces | Accepted |
| [0011](0011-twin-maturity-model-and-modes.md) | Adopt the twin maturity model and operating modes | Accepted (amended 2026-08-29) |
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
| [0028](0028-convex-hull-collision-meshes.md) | Generate convex-hull collision meshes as project assets, bound through L0 | Accepted (amended 2026-08-29 and 2026-09-01; corrected 2026-08-29, 2026-08-31 and twice on 2026-09-01) — implemented 2026-08-31 and **promoted 2026-09-01** against the clause [0051](0051-restate-the-hull-grasp-gate.md) restates, on a campaign whose own verdict was INCONCLUSIVE; see its amendment of that date for the evidence clause by clause and for the four things promotion does not establish |
| [0029](0029-simulated-grasping-by-friction.md) | Rest simulated grasping on friction, and remove the attachment plugin | Accepted (corrected 2026-08-26) |
| [0030](0030-facility-model-describes-the-workpiece.md) | Describe the work-piece in the facility model, as an asset type with no instances | Accepted |
| [0031](0031-refuse-direct-handoff-without-orientation-certainty.md) | Refuse a direct arm-to-arm handoff at plan time until a grasp holds an orientation | Accepted (corrected 2026-08-26) |
| [0032](0032-index-the-belt.md) | Index the belt — stop it on the trigger that starts a station, restart it on `CompleteHandoff` | Accepted (corrected 2026-08-26 and 2026-08-27) |
| [0033](0033-derive-the-index-standoff-from-the-workpiece.md) | Sense against the part's body, and derive an indexing beam's stand-off from it | Accepted |
| [0034](0034-process-lifecycle-mechanism-in-cite-runtime.md) | Compensate two rclpy shutdown races, in a new `cite_runtime` package | Accepted |
| [0035](0035-check-the-english-only-rule-by-character-signal.md) | Check the English-only rule by character signal, across the repository | Accepted (corrected 2026-08-27) |
| [0036](0036-execution-side-trajectory-tolerances.md) | Detect a mistracked trajectory at execution, with tolerances declared in L0 | Proposed (corrected 2026-08-27) |
| [0037](0037-classify-an-abort-before-any-recovery-motion.md) | Classify an execution abort before any recovery motion is dispatched | Accepted (amended 2026-08-27) |
| [0038](0038-stop-the-line-without-ending-the-process.md) | Stop the line without ending the process, and gate resumption on re-armability | Proposed (amended 2026-08-27 and 2026-08-29) |
| [0039](0039-report-a-station-that-cannot-be-triggered.md) | Report a station that cannot be triggered, as a line state of its own | Proposed (corrected 2026-08-28, amended 2026-08-29) |
| [0040](0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md) | Stop a joint part way with a test-only hardware plugin, so an abort reaches L3 on demand | Proposed (corrected 2026-08-28, amended 2026-09-01) |
| [0041](0041-virtual-counterpart-is-a-second-full-simulation.md) | Build the Phase 2.A virtual counterpart as a second full simulation | Accepted (corrected 2026-08-29 and 2026-08-30) |
| [0042](0042-partition-gazebo-transport-per-side.md) | Partition Gazebo transport per side, explicitly and never by default | Accepted (corrected 2026-08-29) |
| [0043](0043-hold-both-sides-to-the-wall-clock.md) | Hold both sides to the wall clock — throttle the generated world, and require RTF >= 1.0 on both concurrently | Proposed (corrected 2026-08-29, 2026-08-30, 2026-08-31 and 2026-09-01; half 2 restated by [0049](0049-measure-the-real-time-floor-as-capacity.md)) |
| [0044](0044-one-ros-domain-per-side-identical-names.md) | Give each side of a twin pair its own ROS domain, and keep both sides' names byte-identical | Proposed (corrected 2026-08-30) |
| [0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md) | Measure the gripper deadline in the clock the gripper runs on, and declare it in L0 | Proposed (corrected 2026-08-30) |
| [0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) | A retry may not re-enter a wait on a trigger its own recovery destroyed | Proposed (corrected 2026-08-30) |
| [0047](0047-two-independent-launches-joined-not-sequenced.md) | Bring a pair up as two independent launches, joined by a supervisor that sees only processes | Accepted (corrected 2026-09-01) |
| [0048](0048-refuse-a-counterpart-the-generator-cannot-build.md) | Refuse a counterpart whose backend differs from the plant's, until the generator emits per-side artifacts | Accepted on clause 1 (corrected 2026-08-30; promoted 2026-08-31) — clauses 2 and 3 unbuilt, see its status block |
| [0049](0049-measure-the-real-time-floor-as-capacity.md) | Keep the real-time floor and measure it as capacity, not as a throttled rate | Proposed (corrected 2026-09-01) |
| [0050](0050-what-crosses-the-twin-boundary.md) | Cross the twin boundary in L5's own memory, and say when a divergence number may be believed | Proposed (corrected 2026-08-31) |
| [0051](0051-restate-the-hull-grasp-gate.md) | Restate ADR-0028's grasp gate, and bind it to the work-piece width it was measured at | Accepted |
| [0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md) | Decide what separates a real grasp from a stall on nothing | Accepted (amended and corrected 2026-09-01) — the project owner chose **option F**, judge the grasp against the part rather than against the commanded width, on the campaign the record's own gate asked for. **Nothing is built and the defect is still live**: what is `Accepted` is the decision and the mechanism F is given in that amendment, and §A.10 there is the gate the implementing change has to pass. The correction of the same date removes option F's claim that `Pick.Goal.workpiece_id` can be resolved to a work-piece type — it cannot, and that is what makes the answer an interval |
