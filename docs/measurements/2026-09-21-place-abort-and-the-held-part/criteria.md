# Criteria — what a `Place` that aborts leaves behind, and whether turning through the front changes how often it aborts

**Written before the harness exists and before any trial has run.** At the moment this file is
committed this directory holds this file and nothing else — no `harness/`, no `raw/` — and no
cell has been brought up for this campaign. From the first trial, rule 1 of
[`docs/measurements/README.md`](../README.md) binds and **V9** below applies: no threshold
moves.

- **Opened:** 2026-09-21
- **Branch under measurement:** `feat/turn-through-the-front`
- **`BASE_COMMIT`:** `6a39eae81df7a252e7d99753cd6d0b2ce203b349`
  (`git rev-parse HEAD` on that branch's base; `git merge-base --is-ancestor 6a39eae HEAD`
  must succeed at every block)
- **Vendor pin:** `xarm_ros2` at `3dc2b5e8294758d96b54b15fa5920d581b7cbb3d`, from
  `external/cite.repos`
- **The open-work item that asks for this:** [`#60`](../../open-work.md) — *"`Place`'s final
  descent aborts at `cell_a__conveyor_1__infeed`"*. It names the cheapest measurement that
  would settle it, and this campaign is that measurement plus the half #60 does not ask for.
- **Records that own the thresholds this campaign reads and may not move:**
  [ADR-0036](../../adr/0036-execution-side-trajectory-tolerances.md) (the execution-side
  tolerances), [ADR-0037](../../adr/0037-classify-an-abort-before-any-recovery-motion.md) (the
  classification), [ADR-0038](../../adr/0038-stop-the-line-without-ending-the-process.md)
  (what an escalation does, and decision 5, which is open).
- **Campaigns whose rules this one inherits, each FROZEN and none of them edited here:**
  [`2026-09-04-following-error`](../2026-09-04-following-error/criteria.md) — rules L, N, G, R,
  M and the `JointTrajectoryControllerState` instrument;
  [`2026-08-27-teardown-signal-family`](../2026-08-27-teardown-signal-family/results.md) — its
  rule 1, that a clean post-fix arm evidences nothing when the pre-fix arm did not reproduce
  the defect.

---

## §0 This campaign decides nothing

It measures. It does not change behaviour, and the following may not move on its evidence:

- **No tolerance is widened to absorb a measurement.** That is ADR-0036's own sentence, and
  `model/assets/types/robots/xarm5.yaml` states it again at the value itself: *"If this ever
  fires on a healthy run, set it to `null` … rather than widening it. A tolerance wide enough
  never to fire is not a detector."*
- **No scenario ceiling is widened**, whatever the load readings say.
- **It does not decide what to do with a held part.** That is ADR-0038 decision 5, it is
  deliberately open, and this campaign takes no position on it.
- **It attributes no physical cause to the abort.** #60 records the cause as unestablished;
  nothing here changes that.

## §1 The question, and the ones it is not

**Q1 — the state the cell is left in.** When `Place`'s descent aborts, is the gripper still
closed on the work-piece, and where is the work-piece?

**Q2 — the terminal error.** At the moment of the abort, what is each arm joint's error
against the 0.010 rad goal tolerance? #60 notes that the closest existing instrument reports
the **peak error in flight** and never the terminal error, which is the number the abort is
decided on.

**Q3 — does the front turn change the abort rate?** The wound path is about five times the
joint travel of the short one. Q3 asks whether the abort count differs between them.

### §1.2 Not in scope, deliberately

- **A rate.** Every count here is a count over the trials that ran, on one machine, on one
  image, at one commit. It is not a rate and may not be quoted as one.
- **Determinism.** Scenarios in this cell are not reproducible: the physics solver is unseeded
  and the OMPL fallback is unseeded and unseedable.
- **A fidelity number.** Nothing here measures the model against reality.
- **Attribution.** Q2 measures the error; it does not say what caused it.

## §2 The mechanism as implemented, read at `BASE_COMMIT` before any trial

- `Place` runs approach → **descent** → open jaws → retreat
  (`workspace/src/cite_skills/src/skill_server.cpp:1310-1344`). The jaws are opened by
  `command_gripper` at `:1327-1329`, **after** the descent at `:1319-1324`.
- The descent's failure path is `finish(outcome); return;` — there is no cleanup, no `catch`,
  and no path that reopens the jaws. `holding_` is cleared only at `:1334`, after a successful
  open.
- `Place.Result` carries `ResultCode result`, `PoseStamped release_pose`, `Duration duration`
  and **no custody field**, where `Transfer.Result` carries `still_holding`.
- `recovery_for(MOTION_INTERRUPTED)` is `ESCALATE`, so `would_retry` is false and
  `RecoverFromFailure`'s "still holds work-piece" sentence is **not** appended
  (`line_nodes.hpp:1159-1174`).
- `StopAll` commands every declared belt to zero and commands no arm
  (`line_fault.hpp:291-319`).
- The grasp is friction only (ADR-0029); the belt carries **kinematically** via
  `Link::SetLinearVelocity`, which suppresses wrenches for the step
  (`cite_simulation/src/conveyor.cpp:255-284`).

**The prediction this campaign will be scored against, written before any trial.** Given the
above, on every abort of the descent we expect `picker_drive_joint` to be at its closed stall
value and the work-piece to be within a grasp's distance of the tool point. **If that is not
what we see, the reading above is wrong and the campaign says so.**

## §3 Arms, and rule T

| Arm | Code | What it is |
|---|---|---|
| **W** (wound) | `BASE_COMMIT` | today's branch selection — the long way round |
| **F** (front) | `BASE_COMMIT` + Part A | the IK solution normalised to the branch nearest the arm |

**Rule T — the arms are not each other's evidence.** Every verdict is stated per arm. An
effect seen in one is not carried to the other, and §7's decision rules are applied to each
separately.

**Rule 1, inherited from the teardown campaign and load-bearing here.** If arm **W** does not
reproduce the abort, then arm **F**'s silence evidences nothing about the abort, and Q3's
verdict is **INCONCLUSIVE**. Q1 and Q2 are then **NOT OBSERVED** rather than answered.

## §4 Instruments, registered before the first trial

- **I1 — abort detection.** The `FollowJointTrajectory` result code and the controller's own
  strings on the arm's controller topic. An abort is `GOAL_TOLERANCE_VIOLATED` or
  `PATH_TOLERANCE_VIOLATED`, read from the result, never inferred from a timeout.
- **I2 — terminal joint error.** `control_msgs/JointTrajectoryControllerState` on the arm
  controller's `~/controller_state`, QoS as
  `cite_bringup/test/test_trajectory_constraints_launch.py:105-115` declares it. The sample
  taken is the **last one received before the result**, and it is recorded with its stamp.
- **I3 — jaw state.** `picker_drive_joint` from `/cite/cell_b/picker/joint_states`.
- **I4 — work-piece pose.** `cite_bringup.gz.ModelPoses`, which takes the partition from the
  plan through the one door ADR-0042 mandates.
- **I5 — the L3 verdict.** The `Place` action result code and detail.
- **I6 — load.** Host load average and container CPU quota, recorded per block, **flagged and
  never used to exclude** (V7).

### §4.3 What is deliberately not an instrument

- **The GUI.** No trial runs with a Gazebo GUI; a rendered window is a load confound.
- **A screenshot or a visual reading.** Nothing in this campaign is decided by looking.
- **The scenario verdict.** `pick_and_place` passing or failing is not an instrument here; the
  campaign drives L3 directly so that an abort is a measurement rather than a run that died.

## §5 What varies, what is held fixed

**Varied:** the arm (W / F); and the part condition — **with the part in the gripper** and
**without it** — which is the condition #60 names and no existing campaign has run.

**Held fixed:** zone `cell_b`, the `picker` asset, `release_height_m = 0.04`, the place frame
`cell_b__transfer_belt__infeed`, the shipped collision selection, the shipped tolerances, one
image, one machine, no GUI, `--headless`, no pair (one side only — a pair is a load confound
and Q1–Q3 are single-side questions).

### §5.3 What a healthy trial means, defined before the data

A trial is **healthy** when the cell reached readiness, the controller was active, the goal
was accepted, and a result of any kind came back. A trial that never reached readiness is not
a quiet trial; it is an **instrument loss** under §10.

## §6 Design, sample size and order

- One block = one bring-up. Trials are **interleaved** within a block where the condition
  allows, never blocked, per README rule "interleave, do not block".
- **n = 20 descents per arm**, 10 with the part and 10 without. Stated as a judgement, not a
  derivation: it is what fits the wall clock on this host, and §7's rules are written so that
  a small n produces an honest INCONCLUSIVE rather than a confident number.
- **Shakedown:** exactly one, published under `raw/shakedown/`, excluded from every figure in
  §7, and it may not set or adjust any threshold.
- **No arm is topped up** (V8). n is what it was.

## §7 Thresholds — the decision rules, applied literally

| # | Question | Rule |
|---|---|---|
| **T1** | Q1, jaws | On every abort, `picker_drive_joint > 0.30 rad` ⇒ **CLAMPED**; `< 0.05 rad` ⇒ **OPEN**; between ⇒ **INDETERMINATE**, reported as its own value and not folded into either. The 0.30 is below the measured stall of 0.4088 and above the open value of 0.0001 — it separates the two states that have been observed and is a judgement, not a derivation. |
| **T2** | Q1, part | On every abort, the work-piece's distance from the tool point at the abort. Reported; **no pass/fail**, because no prior value exists to compare it against. |
| **T3** | Q2 | The terminal per-joint error against `goal_tolerance_rad = 0.010`. A joint outside the band is **OUTSIDE**; all joints inside is **INSIDE**. ADR-0037's classifier tests the same band, so an abort classified `MOTION_INTERRUPTED` predicts **OUTSIDE**; a disagreement is a finding about the classifier and is reported as one. |
| **T4** | Q3 | Abort counts per arm, per condition, stated as counts. **INDISTINGUISHABLE unless the counts differ by more than the larger arm's own spread across its blocks** — and if arm W's count is 0, rule 1 fires and the verdict is INCONCLUSIVE whatever arm F shows. |
| **T5** | joint travel | Total `joint1` travel per descent, per arm, in degrees. Arm F is expected below 180°; arm W is expected to exceed it on at least one trial. **A prediction, scored, not a gate.** |

## §8 Explicitly not measured, recorded here rather than discovered later

- Whether the abort occurs on `cell_a`. This campaign runs `cell_b` only; #60's `cell_a`
  counts close where they are and nothing here is appended to them.
- Whether a running belt drags a held part out of the jaws. The mechanism is read from
  `conveyor.cpp` and is **not** exercised: doing so needs a belt commanded non-zero under a
  held part, which is the hazard ADR-0038 decision 5 exists for.
- Anything about hardware. Both sides of everything here are simulated.
- The 117.7° between the pick and the place. That is a layout question and a separate one.

## §9 The machine, named

11th Gen Intel Core i7-11800H @ 2.30 GHz, 16 logical CPUs, 31 GiB RAM, Linux, Docker.
**One machine.** Every figure this campaign produces is a figure about this host.

## §10 Validity rules, registered before the first trial

*A rule that only ever confirms is not a rule.*

- **V1 — clean tree.** `git status --porcelain` and a diff against `BASE_COMMIT` over the
  watched paths, taken at **both ends** of every block, computed where the block is taken and
  written **into the record as a field**. The analyser drops any row without it.
- **V2 — the arm that actually ran.** Each block records the commit and whether the
  normalisation is present, read from the built artifact rather than assumed. A block that
  cannot say which arm it is, is discarded.
- **V3 — the backend that actually ran.** `gz_ros2_control` and not mock hardware. Mock
  hardware mirrors commands into states and produces a following error of exactly zero, so a
  rig that silently ran on it would produce a perfect, perfectly meaningless silence — and a
  gripper over mock hardware reports a successful grasp on empty air, which
  `cross-cutting-testing.md` forbids any test from reading.
- **V4 — subscription as an event.** Every instrument must have matched **and** received one
  message before the first goal. Reliable QoS is a promise to matched subscribers only. Treat
  the match as an event, never as a sleep.
- **V5 — one writer.** One checkout, one writer, for the length of a block.
- **V6 — no rebuild mid-campaign.** The workspace is built once per arm, before its blocks.
- **V7 — load is flagged, never excluded.** A load threshold chosen after seeing the data is a
  threshold chosen by the data.
- **V8 — n is what it was.** No arm is topped up after seeing its numbers.
- **V9 — no threshold moves.** A threshold discovered to be wrong is applied literally and
  recorded as wrong, and the disagreement becomes a numbered deviation in `ANALYSIS.md`,
  applied to data already collected.
- **V10 — the partition door.** Every Gazebo-transport process goes through
  `cite_bringup.gz`. An unpartitioned `gz model --list` reaches no world and exits 0.
- **V11 — instrument loss is counted, never quiet.** A trial whose instrument returned nothing
  is excluded, **counted and reported separately from every other exclusion**, and never
  recorded as a trial in which nothing happened. Above 20 % per arm the verdict is **NOT
  ADMISSIBLE**.

## §11 Honesty bounds, fixed in advance

- **A null is not a clearance.** If the abort does not reproduce, this campaign has not tested
  the prediction in §2, and its silence may not be read as agreement with it, as a clearance
  of the tolerances, or as evidence that the fix works.
- **A null is not a pass.**
- **An absence of the abort in arm F is not evidence that arm F prevents it** unless arm W
  produced it. Rule 1.
- **`ANALYSIS.md` states rule 1 and rule T beside every verdict.**
- **Every count is a count over the trials that ran.** Not a rate.
