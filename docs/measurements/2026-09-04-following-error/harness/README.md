# Harness — does the execution-side path tolerance stay quiet under `gz_ros2_control`?

The rig for [`../criteria.md`](../criteria.md). It brings the **shipped** cell up, drives L3
goals at four registered conditions, and records the joint trajectory controllers' own
`~/controller_state` while they run.

**Read `../criteria.md` first.** Every threshold, every validity rule and every verdict in
this campaign lives there and is deliberately not restated here (P1). What this file carries
is how to run the rig, what each file is, where each came from, and what the rig **cannot**
do.

## Before anything

- **`../criteria.md` is frozen from the first campaign trial** ([`../../README.md`](../../README.md)
  rule 1). A threshold discovered to be wrong is **applied literally and recorded as wrong**,
  as a numbered deviation in `ANALYSIS.md`, against data already collected. Nothing in this
  directory may edit it.
- **`harness/` is frozen once the first trial has run, and `raw/` with it** (rule 2). It is
  the code that produced the data, so editing it makes it no longer that.
- **One writer in this checkout** (V10). `v1_clean` is the conjunction of two `git` readings
  taken at both ends of every block, so a concurrent agent editing `model/`,
  `workspace/src/`, `tools/`, `tests/`, `scripts/`, `assets/` or `external/` mid-block
  **silently discards that block**.
- **This rig runs a simulator**, unlike the campaign it inherits its rules from. ADR-0042
  binds: every Gazebo-transport call goes through `cite_bringup.gz` and nothing else. An
  unpartitioned `gz topic -l` reaches no world and **exits 0** — plausible silence, on a
  campaign whose whole hazard is silence.

## The exact reproduction command

Run from the repository root, **on the host**. The container entry is host-side; the trials
are not.

```
docs/measurements/2026-09-04-following-error/harness/run_campaign.sh
```

That runs `B1`, `B2` and `B3` — three bring-ups, three cycles each, fourteen trials a cycle,
**126 trials**. It builds the workspace **once** before the first trial (V11), quiesces 30 s
between blocks, skips a block that has already been taken (V8), and stops the campaign loudly
if one aborts.

One block on its own:

```
docs/measurements/2026-09-04-following-error/harness/run_campaign.sh B2
```

Then read the result:

```
python3 docs/measurements/2026-09-04-following-error/harness/analyse.py \
    > /tmp/following_error_analysis.txt
```

> **THE PRINT IS THE PRODUCT AND IT IS LONG. Redirect it to a file; do not pipe it through
> `head`.** A previous campaign's operator piped a 1034-line report through `head`, saw 143
> lines, and `tee` still reported **exit 0**. Every rule in `../criteria.md` section 7 prints
> whether or not it fires, and a truncated print looks exactly like a rig with fewer rules.

## The shakedown, and it is not data

`../criteria.md` section 10 permits **exactly one** shakedown run per harness. It proves the
rig starts, brings the cell up, matches its subscriptions and writes a record. **It is not
data**: it is published under `../raw/shakedown/`, it is excluded from every figure in
section 7, and **it may not be used to set or adjust any threshold**. If it reveals a defect,
the harness is fixed and `../criteria.md` is not touched.

```
./scripts/enter dev bash -lc \
  'CITE_FE_OUT=/workspace/docs/measurements/2026-09-04-following-error/raw/shakedown \
   bash /workspace/docs/measurements/2026-09-04-following-error/harness/run_cell_block.sh \
        SHAKEDOWN --shakedown --cycles 1'
```

`CITE_FE_OUT` is set **inside** the container command and not on the host side of
`./scripts/enter`, which does not forward it.

Reading it back — and **this output is not a figure of anything**:

```
python3 docs/measurements/2026-09-04-following-error/harness/analyse.py \
    --raw docs/measurements/2026-09-04-following-error/raw/shakedown \
    --shakedown-dry-run > /tmp/following_error_shakedown.txt
```

**It has been run, once, and what it found is in
[`../raw/shakedown/NOTES.md`](../raw/shakedown/NOTES.md).** It caught two defects that would
each have corrupted the campaign — a load arm's tolerance violation recorded as arm_1's, and a
registered FAST goal that was a no-op — and the harness was fixed for both. **The committed
harness is therefore not byte-identical to the one that ran**, and section 10 grants no second
shakedown to prove the fixed one; that residual is stated in the NOTES and is the largest risk
this rig carries into its first block.

**The exclusion is in code and it is three independent refusals**, not a convention about
which directory the operator redirected the run into:

1. `analyse.py` lists `*_trials.json` at the **top level** of `--raw` only, so a recursive
   glob cannot sweep `raw/shakedown/` in.
2. The `SHAKEDOWN` label is skipped wherever it is found.
3. Any row carrying `is_shakedown` is dropped, whatever its file is called.

`--shakedown-dry-run` lifts 2 and 3 **and nothing else**: it refuses to run if any campaign
row is present, and it prints a NOT-DATA banner above its output. It exists so that the
analyser could be demonstrated end to end before the campaign's first trial, which is the
only way to know that a rule prints before there is data to print it about.

## The files

| File | What it is |
|---|---|
| `common.py` | Every registered constant with the `criteria.md` section that registers it; the two-ended `snapshot`/`v1` pair; V2, V3, V7 and the vendor pin; `summarise_trial`, `moving_window`, `goal_settle` and V5's identity — **computed where the block is taken, on the unrounded samples**; `TrialWriter` and its `seal`; `LogCursor` for I3(b) and I3(c). |
| `cell.py` | The cell as this campaign addresses it: the `Driver` node, the `ControllerStateRecorder` (I1, I2), the `JointStateRecorder` (I4), the four registered goal shapes, the `LoadArm` shuttle for CONC, and every Gazebo-transport call routed through `cite_bringup.gz` (V12). |
| `measure.py` | One block. Three cycles, CRUISE → FAST → CARRY → CONC each, fourteen trials a cycle. Takes V1's opening reading, gates on V4, writes a row per trial, and **seals the rows with V1's closing reading — at the end of the block, or as the first act of the abort path**. |
| `run_cell_block.sh` | One block **inside the container**. Domain guard, the shipped `simulation.launch.py`, the `CITE_SIDE_READY` gate (I5, V13, P4), the runner, the teardown sweep. |
| `run_campaign.sh` | The campaign, **on the host**. `build_once` (V11), `record_environment`, the 30 s quiesce, `already_taken` (V8) and the abort banner. |
| `analyse.py` | `criteria.md` section 7, applied to `raw/`. One function per registered rule; **every rule prints whether or not it fires**; a `DEVIATIONS` tuple at module top printed on every run. It reads the validity flags off the record and re-derives none of them. |
| `README.md` | This file. |
| `../raw/shakedown/NOTES.md` | What the one permitted shakedown proved, the two defects it found, what was changed, and what it leaves open. **Not data.** |
| `.gitignore` | `__pycache__`. Nothing else in this directory is generated. |

## Where each file came from

**No campaign imports from another.** Every borrowing below is a **copy**, with the source
file and the commit it was copied at named in that file's own header. Each row names the commit that source file last landed at, so a reader
can `git show <commit>:<path>` and see exactly what was copied. Both source directories
are FROZEN ([`../../README.md`](../../README.md) rule 2) and nothing in either is edited from
here.

| File | Copied from | At |
|---|---|---|
| `common.py` | `docs/measurements/2026-09-03-stall-band-flip/harness/common.py` — the two-ended `snapshot`/`v1` pair, `model_hash`, `host_load`, `host_facts`, `v7`, `running_geometry`, `TrialWriter`, `LogCursor`, `wilson` | `8a35a03` |
| `common.py` | `docs/measurements/2026-09-02-option-f-regions/harness/common.py` — the `LogCursor` bracketing pattern and `repo_root` resolved from the file's own location | `ac11d84` |
| `cell.py` | `docs/measurements/2026-09-02-option-f-regions/harness/cell.py` — the `Driver`, `spin_until`, the goal plumbing, `resolve`, the work-piece SDF, the spawn/remove probes, and the load-bearing import order that sets `GZ_PARTITION` before any Gazebo transport node is built | `ac11d84` |
| `cell.py` | `workspace/src/cite_orchestration/include/cite_orchestration/skill_nodes.hpp` — `PickAt`'s `grasp_width_m` default of 0.045, `PlaceAt`'s `release_height_m` of 0.04 and `require_holding = true`, so that CARRY sends what the shipped line sends | at `HEAD`, 2026-09-04 |
| `cell.py` | `workspace/src/cite_bringup/test/test_trajectory_constraints_launch.py:110-115` — the explicit `controller_state` QoS profile, which is the only `JointTrajectoryControllerState` subscription anywhere in this repository | at `HEAD`, 2026-09-04 |
| `measure.py` | `docs/measurements/2026-09-03-stall-band-flip/harness/measure.py` — the block/cycle loop, the header, the abort path that takes the closing reading first | `a8b83fb` |
| `run_cell_block.sh` | `docs/measurements/2026-09-02-option-f-regions/harness/run_cell_block.sh` — the domain guard, the launch command, the `CITE_SIDE_READY` gate and the teardown sweep, kept verbatim in substance because they encode failures already paid for there | `3235cbc` |
| `run_campaign.sh` | `docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh` — `already_taken`, `build_once`, `quiesce`, `record_environment`, `enter`, `run_one`, the abort banner | `8a35a03` |
| `analyse.py` | `docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py` — the shape only: one function per registered threshold, every rule printing either way, `DEVIATIONS` at module top. **Every rule below it is this campaign's own.** | `8a35a03` |

## Nothing here edits the tree

`../criteria.md` section 0 and V1: nothing in `model/`, `workspace/src/`, `tools/`, `tests/`,
`scripts/`, `assets/` or `external/` is touched. The cell is measured exactly as the tree at
`c38a42c` ships it — shipped collision geometry, shipped controller configuration, shipped
world, shipped launch. **The campaign's only levers are two fields on a goal message**:
`MoveTo.Goal.velocity_scaling` and `acceleration_scaling`, which is what separates FAST from
CRUISE.

The vendor half of the tree is gitignored and holds no tracked file, so no `git diff` over it
can report anything; it is pinned by SHA instead, and every block records the SHA
`external/cite.repos` names against the SHA the imported checkout reads, **at both ends**.

## Fifteen things this rig cannot do, recorded here rather than discovered later

1. **It cannot make the path tolerance fire.** The firing half of open-work #20 is out of
   scope and the reason is structural, not budgetary: it needs a **Gazebo-side** mechanism
   that obstructs an arm **link** while `gz_ros2_control` remains the loaded hardware
   component, and `cite_test_hardware::JointStopSystem` is loaded **instead of** that plugin
   rather than beside it. `../criteria.md` sections 1.1 and 8.
2. **It says nothing about the physical arm.** One backend, one plugin, one gain. #20's P2
   asymmetry is not resolved in either direction by a simulation-only sample, and the word
   *validated* may not be used about the tolerance on either backend (rule G).
3. **It cannot see a tolerance event the controller did not publish a message for.**
   `publish_state` goes through a realtime publisher's `try_publish` and the tolerance check
   runs in `update()` whether or not the message is delivered. Every peak here is a maximum
   over the samples that **arrived** and is a **lower bound** on the maximum the controller
   compared (rule M).
4. **It cannot attribute an I3(b) line to an arm on that line's own evidence.** Every
   controller manager in this cell lives inside the `gz` process and shares one `tolerances`
   logger, whose line names no arm at all. I3(b) is attributed by the controller warning that
   follows it within eight lines; an event that window cannot attribute is recorded as
   **unattributed** and treated as possibly arm_1's, which can only make a QUIET claim harder.
   The 2026-09-04 shakedown is why this is here: an unattributed scrape recorded a genuine
   `arm_3` path-tolerance violation as arm_1's, which is this campaign's headline verdict.
5. **It cannot tell which check fired from the L3 result or from the tolerance log line.**
   Both checks emit the identical string on the identical logger, and MoveIt forwards only
   the rclcpp_action code. Only I3(c)'s discriminating lines can attribute an event, and
   where they are silent the verdict is **FIRED (unassigned)** — never attributed by
   assumption.
6. **It does not run `pick_and_place` or `continuous_line`.** ADR-0036's revisit bullet asks
   for a sample across both scenarios; this rig drives L3 directly, because the recorder must
   live in the launch's own container and because a scenario failing for its own reasons
   would consume a block. **That part of the bullet is not discharged here.**
7. **It cannot reproduce a trial.** The physics solver is unseeded. Every figure is a sample,
   and V6 and rule R are what govern reading one.
8. **It cannot separate a load-arm failure from arm_1's condition beyond reporting it.** If a
   load arm's goal fails, `load_active` goes false for the trials it spans and the failure is
   published — but no verdict is stated about arms 2 and 3 at all (rule T).
9. **It cannot measure `stopped_velocity_tolerance`.** That check cannot fire on this
   controller for two independent reasons, either alone sufficient. It is registered as **not
   measured** rather than measured as a constant.
10. **It cannot say whether the physics engine clamps the plugin's velocity command.** The
   plugin writes `target_vel` into a `JointVelocityCmd` component; whether `gz-sim` then
   clamps it against the joint's SDF limit is unverified here. What this rig does record is
   whether any measured joint speed ever exceeds 3.14 rad/s, which is I2 and is reported
   either way.
11. **Its `v_peak` is a measured joint speed, not the IK solution's.** `../criteria.md`
    section 2.3's displacement estimate is a base **bearing** of a frame, and the IK solution
    is not obliged to agree with it. Rule D governs the arithmetic and the measurement
    disagreeing, and it does not resolve the disagreement.
12. **It cannot tell an unsealed block from a lost one after the fact beyond the count.** If
    the harness dies before V1's closing reading, its rows carry `v1_clean = None`,
    `analyse.py` drops them, and V1 reports the block as lost with the trial count it would
    have contributed. Those trials are **not re-run** and no arm is topped up (V8).
13. **It re-derives no validity flag.** Rule L's four clauses, V5's 1e-9 identity, V1's
    conjunction, V2's mesh count and V3's plugin reading are all computed where the block was
    taken and travel **on** the record. The per-sample arrays published in `raw/` are rounded
    to 9 decimal places **for readability only** — nothing in section 7 is compared against
    them at that resolution, and the identity check that ran was on the unrounded doubles.
14. **It measures one arm as a decision quantity, one zone, one collision geometry, one
    `max_step_size`, one controller-manager rate and one gain.** Each of those changes the
    plant and reopens every number in `../criteria.md` section 2.
15. **Whether enough CONC trials will carry `load_active` for CONC1 to be evaluable is not
    established.** The runner waits for both load arms to have had a goal accepted before
    arm_1's first CONC goal, and the coverage each arm achieved is published as
    `covered_fraction` beside `load_active` on every CONC row. No threshold was moved to make
    the flag more likely.
    **Corrected 2026-09-04, after review and before any campaign trial.** This entry used to
    attribute the shortfall to *"the gaps between a load arm's consecutive goals — planning
    time, and a replan after an abort"*. **There are no such gaps**: a load arm's recorded
    intervals are contiguous to the microsecond — every inter-goal gap in the shakedown's
    trial 14 is exactly 0.0 s on both arms — because planning happens *inside* the goal whose
    interval already covers it. The real cause was that a load arm published only the goals
    that had **finished**, so the goal still in flight at the end of arm_1's moving window —
    which is the goal that spans almost every window's tail — contributed nothing, and
    `load_active` was systematically false there. That is fixed (Deviation 1), not carried:
    `snapshot()` closes the open goal at the reading's own simulated instant, and `open_goal`
    travels on the record so the synthesised tail stays separable from the closed goals.
    **The wrong mechanism was stated in three places at once — here, in `raw/shakedown/
    NOTES.md`, and in Deviation 9 — and it is what would have stopped anyone finding the
    defect.**

## Recorded limitations, carried rather than fixed

- **`analyse.py`'s `--shakedown-dry-run` is a door into the shakedown's rows.** It is fenced
  three ways — it refuses to run when any campaign row is present, it prints a NOT-DATA
  banner, and the shakedown's rows carry `is_shakedown` wherever they go — but the door
  exists, and a future operator could point it at a directory that later gained data. The
  fence is a runtime refusal and not a structural impossibility, and that is recorded here
  rather than presented as an exclusion it is not.
- **`run_cell_block.sh`'s teardown sweep is a `pkill` by process name.** It is copied from
  the frozen ancestor because it encodes failures already paid for, and on a machine running
  a second cell in another container it would reach processes this block did not start. The
  domain guard at the top is what makes that unlikely; it is not what makes it impossible.
- **I3 is scraped from a text log.** A change to any of the four matched strings — upstream
  `joint_trajectory_controller`, upstream `tolerances.hpp`, or MoveIt's controller handle —
  turns a firing into a silence. The patterns are matched verbatim in `common.py` with the
  upstream file and line each came from, so that such a change is findable; nothing in the
  rig would announce it.
- **`LogCursor.settle` waits a bounded interval for another process to flush its lines.** It
  sequences nothing and no cell waits on it (P4), but a firing whose line arrived after the
  bound is a firing this rig records as absent. The bound is stated in `common.py`.
- **Rule R is applied over an arm's whole trial set, pooling its four goal kinds**, where
  `../criteria.md` section 7's rule R says *"within one arm at one goal"*. `goal_kind` is on
  every row, so the registered per-goal form is computable; it is not computed. The direction
  is **conservative** — pooling four goal kinds can only enlarge the spread, so rule R binds at
  least as often as the registered form — and narrowing it would make this campaign less
  conservative than its own frozen text *after* the text was frozen. Declared as Deviation 14
  rather than changed.
- **`I3B_ATTRIBUTION_WINDOW_LINES = 8` was sized from a single-joint violation.**
  `check_state_tolerance_per_joint` emits a header and one detail line **per violating joint**,
  and under CONC three controller managers interleave into one log, so a multi-joint violation
  can put the attributing controller warning further than eight lines after the first detail
  line. Such an event is recorded **UNATTRIBUTED** and, by the rig's own conservative rule,
  treated as possibly arm_1's — it can make a QUIET claim harder and never easier.
  **The bound is stated rather than widened, and widening is not the obviously safe move**: a
  wider window can reach *past* the emitting caller to the next arm's warning, which would
  record a genuine arm_1 event as another arm's and **hide** it. That is the opposite direction
  and is worse than an unattributed event that is reported. The constant, its derivation and
  this bound are in `common.py`.
- **Nothing measures how long a load arm keeps running after `stop()` beyond the join.**
  `Thread.join(timeout=)` returns `None` whether or not the thread ended, so a stop that timed
  out and a stop that worked were indistinguishable — and CONC's control is the **next** cycle's
  CRUISE, which a still-running load arm would turn into a load condition. `stop()` now reads
  `is_alive()` after the join, prints a loud line when it is true, and carries one entry per
  stop to the block's completion record under `load_arm_stops`. **It reports; it excludes
  nothing and moves no threshold** — what it buys is that a CONC1 verdict taken over a
  contaminated control is visible as one.
- **V14 checks monotonicity only.** Section 10's V14 is about one clock — that no wall-clock
  reading enters a simulated-time quantity — and monotonicity is necessary for that and not
  sufficient, because a wall clock is monotonic too. No magnitude bound is applied, because a
  bound chosen now would be a new exclusion rule added to a frozen criteria after the fact.
  What stands in its place is an argument from source, not a measurement: see Deviation 15.
- **`DEVIATIONS` is not in numeric order.** The tuple reads 1, 2, 3, 4, 5, 7, 8, 9, 6, then 10
  to 15 — deviation 6 was written last of the original nine and appended rather than inserted.
  It is **recorded rather than reordered**: the numbers are referenced from this file and from
  `raw/shakedown/NOTES.md`, and every deviation prints on every run whatever the order. New
  deviations were appended after 6 so that the existing anomaly is preserved exactly and not
  enlarged.
