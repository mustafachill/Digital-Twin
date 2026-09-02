# Shakedown — not data, and excluded from every figure

`criteria.md` §10's closing clause permits one shakedown run per harness, before the first
campaign trial, to prove it starts, connects and writes a record. This directory is that
output. **It is excluded from every figure in §7 and may not be used to set or adjust any
threshold**, and none of §7's thresholds needs it: every one is derived from the geometry
or from the system's own declared tolerances.

**No campaign trial has run.** `raw/` above this directory holds only build provenance.

| Arm | Runner | Trials | Outcome |
|---|---|---|---|
| B | `run_arm_b.sh 1 B_SHAKE --shakedown` | 1 (jam 50.0 mm) | the stop engaged, the joint rested on it, `holding_F` true and `holding_S` false |
| A | `run_cell_block.sh a A_SHAKE --shakedown` | 2 (45.00, 47.85 mm) | both closes reached goal in free air; no work-piece in the world |
| D | `run_cell_block.sh d D_SHAKE --shakedown` | 3 (refusal, `Pick` 45.0, `Grasp` 48.0) | the refusal came back `PRECONDITION_FAILED` with no motion; both grasp doors reached the part |
| C | `run_cell_block.sh c C_SHAKE --shakedown` | 2 (yaw 0.0, 12.0 deg) | contact witnessed, pose stream sampled, yaw read at the stall |

## How many times each harness was actually run, stated rather than implied

The harness was still being written while these were taken, and §10's clause is explicit
that a shakedown revealing a defect is answered by fixing the harness. That happened
three times, so some arms were started more than once:

| Arm | Runs | Why more than one |
|---|---|---|
| B | 2 | the first proved `initial_value` reaches the fixture; the second was taken after V4's second clause was added |
| A | 3 | the first found the V4 finding below; one run was lost to a bring-up that never announced readiness (see below); the third is what is published |
| D | 1 | — |
| C | 2 | the first proved the pose stream and the contact witness; the second was taken after the V4 helper landed |

**The published record for each arm is its last run**, and every one of them was produced
by the harness exactly as it now stands. Nothing here was hand-edited.

## What the shakedown found, and what was done about it

Three defects, all in the harness, all fixed there. **`criteria.md` was not touched**
(§10, V9).

1. **A malformed `--key=value` was accepted silently by both predicate front ends.**
   `strtod` stops at the first character it cannot read and reports success, so an
   argument that picked up trailing text set its own key from the numeric prefix and left
   every later key at its header default — two of which are the stall band's zero-width
   sentinel. The program would then have answered every question with a predicate that
   admits nothing, and answered it silently. Both front ends now refuse such an argument.
2. **V4 cannot be satisfied in Arm A, and the reason is structural.** In free air the
   drive joint is still MOVING when `GripperActionController` ends the goal at
   `|error| < goal_tolerance`. I1 is the position at that instant; I3 is "the last sample
   at or before the result arrives", milliseconds later, by which time the joint has
   closed further. Both shakedown trials exceeded V4's 0.100 mm by several times it.
   **The rule is applied literally and recorded as failing** (V9); the harness now
   publishes `i3_window_trace`, the drive joint through the close, so that `ANALYSIS.md`
   can state the deviation with numbers instead of asserting it.
3. **V4 cannot be satisfied for Arm D's `Pick` door either, for a different reason.**
   `Pick` produces no `Grasp.Result`, so its close has no I1 at all; what the harness
   records as I1 there is a second close on the jaws as they stand, separated from the
   first by a retreat. The shakedown's `pick45` trial shows the two 0.70 mm apart. Same
   treatment: applied literally, reported, and `analyse.py` prints V4's premise per rig
   beside every exclusion so a smaller n is never mistaken for a defect in the cell.

## One bring-up failure, recorded because it is a fact about this machine

An Arm A block was lost when the cell's `gz sim` exited about twenty seconds into
bring-up and the launch tore the rest down; the readiness gate caught it and the block
produced no trial, which is what that gate is for. It happened while four blocks were
being run back to back inside **one** container entry with no quiesce — which is not how
`run_campaign.sh` runs them: that script enters the container once per block and quiesces
60 s first. Re-run the documented way, the same block came up. **This is one event, not
attributed**, and it is recorded here rather than left out because a bring-up that dies
silently is the failure class this project has paid for before.
