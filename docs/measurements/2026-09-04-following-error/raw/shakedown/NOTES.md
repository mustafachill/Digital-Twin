# The shakedown — what it proved, what it found, and why it is not data

**`criteria.md` section 10 permits exactly one shakedown run per harness, and this is it.** It
is **not data**: it is excluded from every figure in section 7, it may not be used to set or
adjust any threshold, and no number below may enter `ANALYSIS.md` as a campaign figure. It ran
**before the first campaign trial**, so `criteria.md` was still corrigible under
[`../../../README.md`](../../../README.md) rule 1 — and **`criteria.md` was not touched.** Section 10
says what to do instead, and it is what was done: *"If the shakedown reveals a defect, the
harness is fixed and this file is not touched."*

## What was run, and against which harness

| | |
|---|---|
| When | 2026-09-04, 16:25:34Z to 16:28:56Z (host clock), **202 s end to end** |
| Command | `run_cell_block.sh SHAKEDOWN --shakedown --cycles 1`, with `CITE_FE_OUT` pointed here |
| Repository | `feat/close-phase-debts` at `e6b0b2c`, worktree clean over V1's seven watched paths |
| Scope | **one** cycle — CRUISE 4 goals, FAST 4, CARRY 2, CONC 4 — that is **14 trials**, against a campaign block's 42 |

**The harness that ran is NOT byte-identical to the harness now committed**, and that is the
whole point of a shakedown. The files as run were:

```
f237591537a99a60292c508d8ea31835a69a54732b4738e8d883e01787e195ee  harness/common.py
a28884e4a746d4a74d32b19d8d937884648e38dc868f19eb18258eacbff14900  harness/cell.py
8358f32194b72b162925dcd56eb6a0af4ccfd5324a105c9ba6542cc8c91b1dfe  harness/measure.py
cdbe41b968280c48d757816171669ea55286f987fe2e7d9f898a567dcb29e548  harness/analyse.py
16e33726388817192bda6b69963720f3b04df5e6ecc6e8343e302f8fac785f52  harness/run_cell_block.sh
d8cb984e03b6f67737fabb32267f6c76c2a7a32e4f76499bf7db1e593bd28925  harness/run_campaign.sh
```

**So the committed harness has not itself been run end to end**, and section 10 grants no
second shakedown to prove that it has. That is stated here plainly rather than left for a
reader to work out, and it is the largest residual risk this rig carries into its first block.
The records in this directory therefore predate the fixes below and **do not carry the fields
those fixes add** — `i3b_unattributed`, `i3_other_arm_events`, and `<label>_setup.json`. The
analyser reads a missing field as *none found*, never as *none present*, and says so where it
matters.

## What the chain proved, end to end

Every link the campaign depends on was exercised:

| Link | Reading |
|---|---|
| The cell came up | `CITE_SIDE_READY side=plant zone=cell_a`, about **37 s** after launch, waited on as an event and never slept for (I5, V13, P4) |
| The backend that ran | **V3 passed** — 3 references to `gz_ros2_control/GazeboSimSystem`, **0** to the fixture plugin, **0** to mock hardware |
| The description that ran | **V2 passed** — **13** hull collision references, 33 653 characters read back off `/cite/cell_a/arm_1/description_publisher` |
| The subscription matched and delivered | **V4 passed** — **1** matched publisher, **551** messages already received before the block's first goal, waited **0.0 s** |
| The publisher's resolved QoS | recorded per block off `get_publishers_info_by_topic`, rather than asserted: `history=3, depth=0, reliability=1, durability=1, liveliness=1` |
| Gazebo transport carried the partition | **22** topics reached through `cite_bringup.gz` (V12); an unpartitioned probe returns an empty list and exits 0, so a non-empty answer is the positive reading |
| Samples were recorded | **10 937** samples in the fourteen trials' moving windows |
| The achieved rate | **142.93 to 153.85** samples per simulated second, against the 150 Hz the controller publishes at and rule L-ii's floor of 20 |
| Validity flags travelled on the record | `v1_clean` sealed on every row at the close of the block; V2, V3, V4, V13 and V7 on every row from the header |
| The analyser printed | 520 lines, every registered rule, including those that did not fire |
| The generated configuration | matched what `criteria.md` section 2.1 registered — `agrees_with_registration: true` |

**Wall clock, for planning the campaign.** Fourteen trials took **88.8 s** of goal time; the
block spanned **99.7 s of simulated time in 111.7 s of wall clock** (I9 ratio **0.892**, context
only, entering no verdict). Bring-up about 37 s, teardown about 30 s. A campaign block is three
cycles rather than one and now carries four repositioning moves a cycle, so **a block should be
expected to take roughly 8 minutes and the three-block campaign roughly half an hour** on a
quiet host — before any retry. Raw volume was **2.18 MB** for fourteen trials, so a full
campaign should be expected to publish **around 20 MB**, which is well inside this directory's
precedent.

## The two defects it found, and what was changed

Both are defects **of the harness**. Neither moved a threshold and neither touched
`criteria.md`. Both are registered as numbered deviations in `analyse.py`'s `DEVIATIONS` tuple,
which prints on every run.

### 1. A load arm's tolerance violation was recorded as arm_1's — the campaign's headline, manufactured

Under CONC, `arm_3` genuinely violated its own path tolerance:

```
[gz-1]       [ERROR] [tolerances]: State tolerances failed for joint 4:
[gz-1]       [ERROR] [tolerances]: Position Error: -1.071717, Position Tolerance: 1.000000
[gz-1]       [WARN]  [cite.cell_a.arm_3.arm_3_joint_trajectory_controller]: Aborted due to state tolerance violation
[move_group-17] [WARN] [...]: Controller 'arm_3_joint_trajectory_controller' failed with error PATH_TOLERANCE_VIOLATED
```

The I3 scrape read the whole log segment and attributed all of it to arm_1's trial 11 — which
the analyser then reported as **`QUIET1 [CONC] = FIRED`**, this campaign's headline verdict,
produced entirely by an arm about which rule T says no verdict is stated at all.

**Why it was possible.** I3(c)'s three lines each name the arm. **I3(b) does not name anything**:
all three controller managers live inside the one `gz` process and share a single `tolerances`
logger whose line carries no arm at all. That is a property of this cell, not an oversight in
`criteria.md`, and it is now recorded as a limit of the instrument.

**The fix.** `common.scrape_i3` takes the arm. I3(c) is filtered on the arm's own controller.
I3(b) is attributed by the controller warning that follows it within eight lines — the caller
that emitted it — and an event that cannot be attributed is counted as **unattributed** and
treated as *possibly arm_1's*, so it can only make a QUIET claim harder and never easier. Every
other arm's event is kept in `i3_other_arm_events` and reported rather than dropped.

**Verified against this directory's own log**: re-scraping trial 11's segment now returns no
event for `arm_1`, the full event for `arm_3`, and `arm_3`'s event under `i3_other_arm_events`
on arm_1's row.

### 2. FAST's first goal was a no-op, which made FAST NOT ADMISSIBLE by construction

`criteria.md` section 6 puts the arms' goal sets back to back and section 3 registers CRUISE and
FAST as `home → above pick → above place → home`. So CRUISE ends at `home` and FAST opens by
asking the arm to go where it already is. The shakedown recorded that goal as **14 samples with
a peak of exactly 0.000000** — an instrument loss under rule L's clauses L-i and L-iii.

That is **one FAST trial in four, every cycle, by construction**: 25 % against rule L's 20 %
instrument-loss ceiling. The analyser confirms it on this directory's own records —
`LIVE1 [FAST] = NOT ADMISSIBLE`. **FAST is the arm PRED3's uncomfortable prediction is about**,
and it would have been refused before the campaign began.

It also broke section 3's own controlled comparison. CONC's control is CRUISE and *"arm_1 does
the identical thing in both"*; as the rig stood, CRUISE's first goal was home-to-home while
CONC's was conveyor-to-home, so the control and the treatment did not start from the same place.

**The fix.** A **non-trial** `MoveTo` to 0.10 m above `cell_a__conveyor_1__infeed` at default
scaling runs before each arm's registered set. It introduces no pose the registered sets do not
already visit, it is not a trial (section 5.3), it enters no distribution, and it is written to
`<label>_setup.json` where no glob over `*_trials.json` can reach it.

### Two smaller things, fixed at the same time

- **The runner's output was invisible while a block ran.** Python block-buffers its stdout
  through `tee`, so fourteen trials produced nothing on screen until the block ended.
  `run_cell_block.sh` now runs `python3 -u`.
- **`load_active` was false on all four CONC trials**, and one cause was the harness's own
  starting order: arm_1's first CONC goal was sent while arm_2 was still planning its first
  (`goals_sent 1, goals_accepted 0`, coverage 0.0). The runner now waits — as a bounded event,
  never a sleep — for both load arms to have had a goal accepted.

## What the shakedown did NOT fix, and what it leaves open

- **Coverage of arm_1's moving window ran 0.0, 0.78, 0.86, 0.96, 0.99, 1.00 across the load
  arms and trials.** `criteria.md` section 3 provides for a CONC trial without the flag — it is
  not an instrument loss, and CONC1 reports the count of trials that lack it — but **whether
  enough CONC trials will carry it for CONC1 to be evaluable is not established by one cycle**,
  and no threshold was moved to make it more likely.
  **CORRECTED 2026-09-04, AFTER REVIEW AND BEFORE ANY CAMPAIGN TRIAL. This entry said the cause
  was "the gaps between a load arm's consecutive goals", and there are no such gaps.** Read
  straight out of this directory's own `SHAKEDOWN_trials.json`, trial 14: every inter-goal gap
  is exactly `0.0` s on both load arms — arm_2's intervals run
  `99.616 → 105.686 → 111.223 → 119.474 → 124.390 → 124.572` and arm_3's
  `99.616 → 104.330 → 104.452 → 109.475 → 114.403 → 114.586 → 120.120`, each interval opening
  where the previous one closed — because a goal's planning happens *inside* the interval that
  goal already covers.
  **The real cause is that a load arm published only the goals that had FINISHED.** In that
  same trial arm_3 reads `goals_sent 7, goals_accepted 6`: a seventh goal was accepted and
  still in flight, arm_1's moving window `[120.799, 125.643]` lay **entirely inside it**, and
  the recorded `covered_fraction` was `0.0`. `load_active` was systematically false at every
  window's tail, and CONC1's population is `load_active is True`. **The defect is in the
  harness and it is fixed** — `LoadArm.snapshot()` now closes the currently open goal at the
  reading's own simulated instant, and `open_goal` travels on the record — so the coverage
  figures above describe the instrument as it was **at the shakedown** and not as it will be.
  **The figures in this file are unchanged and remain the shakedown's own record; nothing here
  is a campaign figure, and no threshold is set, adjusted or implied by this correction.**
  **The wrong mechanism was written in three places at once** — here, in `../../harness/
  README.md`'s limitation 15, and in `analyse.py`'s Deviation 9 — **and it is the prose that
  would have stopped anyone finding the defect.**
- **`arm_3`'s goals failed repeatedly**, four times in one cycle, each with `MOTION_INTERRUPTED`
  and *"the arm stopped part-way along the commanded trajectory and is holding position"*. Rule
  T governs: it is reported, and it is not a finding about arm_1. **It is also not investigated
  here** — this campaign takes no position on it and proposes nothing.
- **No campaign figure is set, adjusted or implied by anything in this directory.** Every number
  above describes the instrument, not the cell's following error.
