# Harness — the regions option F opens, closes and has never touched

Four arms, three rigs, one predicate. The order below is
[`criteria.md`](../criteria.md) §6's registered order — **B, then A, then D, then C** —
and it is not a convenience: B is the cheapest and the only one with no cell, A answers
the question with the largest predicted effect, and C is last because its mechanism is the
least certain.

Everything runs from the repository root. The `./scripts/enter` steps are host-side; the
trials are not.

## Before anything

```sh
./scripts/validate-model          # the L0 tree is the one the plan describes
./scripts/build                   # cite_test_hardware builds only under BUILD_TESTING
./scripts/test                    # criteria.md section 9 records these three clean
./scripts/lint
```

`./scripts/build` is not optional for Arm B: `cite_test_hardware/JointStopSystem` is
test-only by construction (ADR-0040) and is built only with tests on.

## The whole campaign, in order

```sh
docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh
```

It runs B, then A (two blocks), then D (two blocks), then C (two blocks), quiescing 60 s
and recording the host load average before each. A block whose `raw/<label>_trials.json`
already exists is **skipped rather than re-run**, so a resumed campaign never silently
tops a condition up (V8).

## One arm at a time

```sh
# Arm B -- a jammed OPENING stroke. No Gazebo, no physics. 15 trials, one relaunch each.
docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh B

# Arm A -- genuine free air on the production backend, across the commanded width.
docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh A

# Arm D -- the false-negative side, plus the two doors and the three refusal trials.
docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh D

# Arm C -- the wide edge, via the part's yaw about the world vertical.
docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh C
```

Each of those is a thin wrapper over one command per block, which can also be run
directly:

```sh
./scripts/enter dev bash -lc \
  "bash /workspace/docs/measurements/2026-09-02-option-f-regions/harness/run_arm_b.sh 3 B"

./scripts/enter dev bash -lc \
  "bash /workspace/docs/measurements/2026-09-02-option-f-regions/harness/run_cell_block.sh \
     a A_B1 --cycles 2"
```

## The Arm A refinement grid

§5.1 registers the **step** (0.05 mm, three trials per point) and leaves the **interval**
to be bracketed by the coarse data. That is bracketing, not a threshold chosen by the data,
and the bracket is passed on the command line so that it is visible rather than buried:

```sh
CITE_OFR_REFINE_LOW_MM=46.50 CITE_OFR_REFINE_HIGH_MM=47.00 \
  docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh A_REFINE
```

**Which crossing is bracketed, because the obvious answer is the wrong one here.**
§5.1 words the interval as the last coarse width with `holding_F = false` and the first with
`holding_F = true`, and adds that if the coarse grid produces no flip, no refinement runs and
rule N-A applies. **The shakedown shows there will be no such flip**: a free-air close on the
production backend ends `reached_goal = true` and `stalled = false`, so option F's *first*
gate rejects and `holding_F` is false at every command. Read only that far, the refinement
would never be attempted at all.

§7.1 registers the alternative in the same breath, and it is what applies:

> the lowest commanded width at which `holding_F` flips to true — **or, if A1a is false
> throughout, at which A1b goes INSIDE** — bracketed to 0.05 mm or finer

So when A1a is false throughout, `A_REFINE` **is** run, and it brackets the **A1b** crossing:
the last coarse width whose `a1b_inside_window` is false and the first whose is true, both
computed from **I1** (`Grasp.Result.reached_width_m`), which §2.1 defines as `w_reached`.
`analyse.py` prints both bounds and records this as **deviation 2**. The step, the three
trials per point and the requirement to bracket to 0.05 mm are all unchanged — only which
crossing is bracketed, and §7.1 is where that choice is registered.

Rule N-A still applies to **A1**, which is a separate verdict and is not refined by this grid.

## The shakedown, and it is not data

§10 permits **one** shakedown run per harness, to prove it starts, connects and writes a
record. Its output goes under `raw/shakedown/`, is excluded from every figure in §7, and
may not be used to set or adjust any threshold. If it reveals a defect, the harness is
fixed and `criteria.md` is not touched.

**All four have been shaken down and the output is published**, with what it found — three
harness defects and one bring-up failure — in
[`../raw/shakedown/NOTES.md`](../raw/shakedown/NOTES.md). Read that before the first
campaign trial: two of its findings are `criteria.md` rules that **cannot be satisfied**
by the rig that exists, and they are applied literally rather than relaxed.

```sh
./scripts/enter dev bash -lc \
  "CITE_OFR_OUT=/workspace/docs/measurements/2026-09-02-option-f-regions/raw/shakedown \
   bash /workspace/docs/measurements/2026-09-02-option-f-regions/harness/run_arm_b.sh \
     1 B_SHAKE --shakedown"
```

The three cell arms take `--shakedown`, which runs two or three trials and nothing else:

```sh
./scripts/enter dev bash -lc \
  "CITE_OFR_OUT=/workspace/docs/measurements/2026-09-02-option-f-regions/raw/shakedown \
   bash /workspace/docs/measurements/2026-09-02-option-f-regions/harness/run_cell_block.sh \
     a A_SHAKE --shakedown"
```

## The arithmetic, with no cell and no container

```sh
python3 docs/measurements/2026-09-02-option-f-regions/harness/arithmetic.py
docs/measurements/2026-09-02-option-f-regions/harness/build_host.sh
```

`arithmetic.py` reproduces every figure in `criteria.md` §2 and §2.2 from the L0
declaration and nothing else. **No reported campaign figure comes from it.**

## Reading the result

```sh
python3 docs/measurements/2026-09-02-option-f-regions/harness/analyse.py
```

It applies §7's rules and prints them **whether or not they fire**. It writes no verdict
into any decision record, sets no band, and chooses nothing (§0).

## The files

| File | What it does |
|---|---|
| `arithmetic.py` | the **reference** implementation. §2's cross-check and the source of the sweep points, and **nothing else**. No reported figure comes from it. |
| `predicate_eval.cpp` | a batch front end for the **shipped** arithmetic at `d3eeac4`, including `resolve_grasp_width` (I6). Contains no arithmetic of its own. |
| `predicate_eval_superseded.cpp` | the same front end against `4ef2d7c`'s API, for `holding_S`. |
| `build.sh` / `build_host.sh` | compile the shipped front end, in the container and on the host, from `workspace/src/cite_skills` unmodified. |
| `build_superseded.sh` | V10: a **detached `git worktree` at `4ef2d7c`**, compiled and then removed, with the worktree commit and the binary's sha256 written into `raw/provenance.txt`. |
| `common.py` | provenance (V1, V2), the two front ends, the plan, the window, and the record writer |
| `cell.py` | the shipped cell as arms A, C and D address it: driver, contact witness (I4), pose stream (I5), and every Gazebo call through `cite_bringup/gz.py` |
| `arm_b.launch.py` | Arm B's rig — the launch test's node set, with the stops reversed |
| `measure_arm_b.py` | B — five jam positions × 3, an **opening** stroke, one relaunch per trial |
| `measure_arm_a.py` | A — 13 commanded widths × 3 in free air on the production backend, plus the refinement grid |
| `measure_arm_d.py` | D — 45.0 mm through `Pick` and 48.0 mm through `Grasp`, interleaved, plus the three `Pick` refusals |
| `measure_arm_c.py` | C — 8 yaw setpoints × 3 about the world vertical |
| `run_arm_b.sh` | Arm B's block: domain guard, fixture-presence check, build, trials |
| `run_cell_block.sh` | one block against the shipped cell: domain guard, build, bring-up, **readiness gate**, trials, teardown |
| `run_campaign.sh` | all four arms in §6's order, with the quiesce and the load reading between blocks |
| `analyse.py` | §7's decision rules, applied to `raw/` |

## Where this harness came from

Every file names its source and the commit it was copied at, in its own header. The rig it
starts from is
[`../../2026-09-01-grasp-discrimination/harness/`](../../2026-09-01-grasp-discrimination/harness/README.md)
at commit `eeaf903` — `measure_fp.py` for the description surgery and the relaunch loop,
`measure_fn.py` for the driver, the contact witness and the block shape, `predicate_eval.cpp`
and its build scripts for the compiled-not-copied discipline, and `run_fn_block_after_ready.sh`
for the readiness gate. **That directory is frozen and nothing in it is edited from here.**
Arm B's node set comes from `workspace/src/cite_bringup/test/test_grasp_predicate_launch.py`
at `d3eeac4`, which §5.2 names as the shape it uses.

## Nothing here edits the tree

No `model/`, no `workspace/src/`, no `tools/`, no threshold anywhere. Three arms run the
cell exactly as it ships and their levers are fields on goal messages and a spawn pose.
Arm B substitutes a hardware plugin **inside its own expanded copy** of the description and
asserts, before substituting, that what it is replacing is the production backend (V7).
Arms A, C and D read the same two plugin names off the description the **running** cell
publishes and record `v7_ok` on every trial; **Arm A aborts the block** on a mock backend,
which is V7's own clause for it (§5.1) and which nothing asserted until 2026-09-02.
`build_superseded.sh` creates a git worktree **outside** this repository's working tree and
removes it again.

## Four things the rig cannot do, recorded here rather than discovered later

1. **I4 does not exist in Arm A.** §4.1 defines I4 as a contact sensor *on the work-piece*,
   and Arm A spawns none (§5.1: "Between the pads: **nothing.** No work-piece is spawned in
   Arm A at all"). V3's Arm A clause is therefore discharged by its **second** half — no
   work-piece exists in the world — read per trial from the world itself through
   `cite_bringup/gz.py`. A witness that sees nothing because there is nothing to carry it is
   not a witness, and `ANALYSIS.md` must say so rather than reporting "I4 witnessed no
   contact".
2. **I4 is structurally absent in Arm B.** That rig has no simulator, so nothing can touch
   anything. V3's "no contact at all" is discharged by construction.
3. **`Grasp` does not move the arm**, so arms C and D's `Grasp`-door trials reach the part
   with the shipped `MoveTo`, at the pose `Pick` would have planned — the pick frame offset
   along the tool axis by the shipped `gripper_pad_plane_offset_m` at the drive angle the
   commanded width asks for, read through `predicate_eval` and never recomputed. The target
   pose and the pose actually reached are on every record, and Arm D's `Pick` trials record
   `Pick.Result.grasp_pose`, so the two routes can be compared rather than assumed equal.
4. **The `Pick` door has no I1, and no rig change can give it one.** §4.1 defines I1 as
   `Grasp.Result`, and `Pick` returns none — its close is reported only through
   `Pick.Result.holding`, which **is** the shipped predicate's verdict on it
   (`skill_server.cpp:1215-1219`), and through I2's `%.1f` log line, which §4.1 reserves as
   the coarse instrument for V4. So for Arm D's `pick45` condition the **verdict** is
   `Pick.Result.holding` and the **width** is I3, sampled at a boundary each record names;
   V4 is **unevaluable** there rather than failed, and those trials stay in the
   distribution. Reading the verdict off a *second* close instead — which this harness did
   until 2026-09-02 — puts the event D1 exists to catch beyond the reach of its own
   threshold, because a first close reporting a real grasp empty is followed by a second
   that reports holding. `analyse.py` records this as **deviations 3 and 4**.
