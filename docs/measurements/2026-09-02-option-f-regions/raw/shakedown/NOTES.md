# Shakedown — not data, and excluded from every figure

`criteria.md` §10's closing clause permits one shakedown run per harness, before the first
campaign trial, to prove it starts, connects and writes a record. This directory is that
output. **It is excluded from every figure in §7 and may not be used to set or adjust any
threshold**, and none of §7's thresholds needs it: every one is derived from the geometry
or from the system's own declared tolerances.

**No campaign trial has run.** `raw/` above this directory holds only build provenance.

---

## This shakedown SUPERSEDES the one taken at `3235cbc`, and why

The `3235cbc` shakedown described a harness that no longer exists. A pre-trial review
returned **do not run** on that harness with eleven findings, and the fixes changed **what
quantity four of the arms record**, not merely how they record it. A shakedown is a claim
that *this* harness starts, connects and writes a record; once the harness changed, the old
output stopped being that claim. It is replaced rather than annotated, and the runs below
were taken with the harness exactly as it now stands, at `62051df`.

**The change that matters most.** `criteria.md` §2.1 defines `w_reached` as
*"`gripper_width_for(reached_position)`, the width the predicate consumes"*, and §4.1 names
that **I1** — `Grasp.Result.reached_width_m` — with **I3** as the same quantity read
*independently* of the skill server, which is the cross-check V4 is the rule over. **The old
harness had the two inverted**: `d_narrow`, `d_wide` and A1b were all computed from I3.

In arms B, C and D the joint is stalled and the two agree, so nothing there moved. **In Arm A
it decides the answer.** The joint is still ramping at the I3 instant, the two readings sit
0.57–0.61 mm apart, and extrapolating the two shakedown points to `edge_lo = 47.615 mm` puts
the crossing at about **46.57 mm from I1** — inside the 46.554–46.766 mm bracket §2.2
registered — and about **47.19 mm from I3**, outside it. **The instrument alone decided
whether predictions P1 and P2 were confirmed or refuted.** `skill_server.cpp:2229-2236`
settles which is right rather than any argument here: `outcome.reached_width_m` and
`outcome.holding` are computed from the **same** `wrapped.result->position`, so I1 is
definitionally the value the predicate consumed. Both forms are now on every record — the
I3-derived pair under `d_narrow_i3_m`, `d_wide_i3_m` and `a1b_inside_window_i3` — because
V4 still needs I3 and the deviation has to be showable rather than asserted.

**`criteria.md` was not touched.** Its sha256 is
`17ee48480fd2c8b9a145c05ab2f556815c106f9e355d22b528ec3ed52ae4db73`, unchanged from the commit
that froze it (§10, V9). Nothing in `model/`, `workspace/src/` or `tools/` was edited either:
`git diff d3eeac4..HEAD` over those three paths is empty, which is what V1 spends.

---

## What ran, and what it produced

Every block below was taken on the machine `criteria.md` §9 names, one container entry per
block, quiescing 60 s first — which is how `run_campaign.sh` runs them and is not how the
`3235cbc` shakedown's lost block was taken.

| Arm | Runner | Trials | Outcome |
|---|---|---|---|
| B | `run_arm_b.sh 1 B_SHAKE --shakedown` | 1 (jam 50.0 mm) | the stop engaged, the joint rested on it, `holding_F` true and `holding_S` false; I1 and I3 agree **exactly**, V4 passes |
| A | `run_cell_block.sh a A_SHAKE --shakedown` | 2 (45.00, 47.85 mm) | both closes reached goal in free air; no work-piece in the world; V7 read 3 production plugins and 0 mocks; V4 **fails**, evaluably |
| D | `run_cell_block.sh d D_SHAKE --shakedown` | 3 (refusal, `Pick` 45.0, `Grasp` 48.0) | the refusal came back `PRECONDITION_FAILED` with no motion; both grasp doors reached the part and witnessed contact |
| C | `run_cell_block.sh c C_SHAKE --shakedown` | 2 (yaw 0.0, 12.0 deg) | contact witnessed, pose stream sampled, yaw read at the stall |

**Provenance, read off the records rather than claimed here.** `v1_clean` is true on every
block; the source and installed `MODEL_HASH` agree, so no block ran against a stale install;
`v2_ok` is true with 13 hull collision references; `v7_ok` is true; and the domain each block
ran on (99) is the one `scripts/_lib.sh` derives for this checkout on the host.

## How many times each harness was run, stated rather than implied

| Arm | Runs | Why more than one |
|---|---|---|
| B | 1 | — |
| A | 2 | the first was lost to a bring-up that never announced readiness — see below |
| D | 1 | — |
| C | 1 | — |

**The published record for each arm is its last run**, and every one was produced by the
harness exactly as it now stands. Nothing here was hand-edited.

## One bring-up failure, recorded because it is a fact about this machine

The first Arm A attempt never announced readiness and collected **no trial**. Its harness-side
log is kept as `logs/A_SHAKE_lost_bringup_attempt.log`. The chain, read from the sim log
before it was overwritten by the retry: `move_group` on `arm_1` logged
`Unknown frame: cite_world` twelve times, `planning_scene_loader.py` then reported
*"move_group refused the planning scene diff for zone 'cell_a'"* and exited 1, and the launch
tore the rest of the cell down; `parameter_bridge` died `-6` on a glibc
`pthread_mutex_lock` assertion during that teardown, which is the teardown signal family
`CLAUDE.md` §2 already carries.

**The readiness gate caught it and the block produced nothing, which is what that gate is
for.** Re-run 60 s later the same block came up and both trials ran. **This is one event, on
one machine, and it is NOT attributed** — a TF race at startup and a starved container are
both consistent with it and nothing here separates them. It is recorded rather than left out
because a bring-up that dies silently is a failure class this project has paid for before.
**It is not evidence about the predicate**, and nothing in this campaign's harness changed
between the two attempts.

## What this shakedown found

**Nothing new in the harness.** It was run to prove the repaired harness starts, connects and
writes a record, and it did for all four arms. The eleven findings it exists to close were
found by review of the `3235cbc` harness, not here, and each is fixed with its own comment in
the source. Three things it confirms rather than discovers:

1. **V4 fails in Arm A evaluably, and is applied literally.** Deltas of 0.566 mm and
   0.655 mm against a 0.100 mm tolerance, so every Arm A trial is excluded from the
   distribution. §7.1's A1b in its **median** form is therefore UNANSWERABLE, and the
   per-trial I1-based A1b is reported in its place — **numbered deviation 1**, printed by
   `analyse.py` on every run. The rule was **not** moved (V9).
2. **V4 is UNEVALUABLE, not failed, for Arm D's `Pick` door.** `Pick` returns no
   `Grasp.Result`, so that close has no I1 at all. The old harness compared I1 from a
   **second** close against I3 from the first and reported 0.70 mm — a number it manufactured
   itself. Read against the `Pick`'s own I2 line the two sit about 0.08 mm apart, **inside**
   V4. Those trials now stay in the distribution — deviations 3 and 4.
3. **The `holding_F` flip Arm A's refinement is registered against does not occur.** Free air
   ends `reached_goal = true` at both commands, so option F's *first* gate rejects and
   `holding_F` is false throughout. §7.1's own alternative — bracket the **A1b** crossing —
   is what `A_REFINE` will bracket, at the same registered 0.05 mm step: **deviation 2**.

**None of the three moved a threshold**, and none of them is a figure. Every number above is
from two or three trials and is here to show the instrument works, not to say anything about
the cell.
