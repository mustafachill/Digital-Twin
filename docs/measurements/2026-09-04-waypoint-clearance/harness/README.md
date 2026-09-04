# Harness — how close does this cell pass, and how far does it step between the only checks it gets?

The rig for [`../criteria.md`](../criteria.md). It **captures** the trajectories the cell
actually planned, off each arm's `display_planned_path` while the shipped scenarios run, and
then **computes** — offline, against both committed mesh sets — the per-waypoint distance from
every collision link to every planning-scene object, and the per-waypoint tool-point step.

**Read `../criteria.md` first.** Every threshold, every validity rule and every verdict in this
campaign lives there and is deliberately not restated here (P1). What this file carries is how
to run the rig, what each file is, where each came from, and what the rig **cannot** do.

## Before anything

- **`../criteria.md` is frozen from the first campaign trial** ([`../../README.md`](../../README.md)
  rule 1). A threshold discovered to be wrong is **applied literally and recorded as wrong**, as
  a numbered deviation in `ANALYSIS.md`, against data already collected. Nothing in this
  directory may edit it.
- **`harness/` is frozen once the first trial has run, and `raw/` with it** (rule 2). It is the
  code that produced the data, so editing it makes it no longer that.
- **One writer in this checkout** (V10). `v1_clean` is the conjunction of two `git` readings
  taken at both ends of every block, so a concurrent agent editing `model/`, `workspace/src/`,
  `tools/`, `tests/`, `scripts/`, `assets/` or `external/` mid-block **silently discards that
  block**. `docs/measurements/` may advance and nothing else may.
- **This rig brings up no cell of its own.** Each scenario starts its own `move_group` inside
  its own process and every run owns its own cell (rule C-i), so there is no
  `simulation.launch.py` here and no `CITE_SIDE_READY` gate. `capture.py` launches
  `./scripts/scenario` and watches the door while it runs.
- **ADR-0042 binds the cell and not this harness.** The harness constructs no Gazebo
  environment and makes **no `gz` call at all**; the scenarios carry `GZ_PARTITION` themselves
  through the shipped launch. `v12_gz_calls` is `0` on every record so that a reader can check
  that rather than trust it — an unpartitioned `gz model --list` reaches no world and **exits
  0**, which on a campaign whose whole hazard is silence would be plausible silence.
- **Do not run this while `./scripts/test` is running.** There is one DDS domain per checkout,
  `cite_skills`' launch tests start their own `move_group` nodes in the same namespaces, and
  two `move_group` nodes in one namespace answer each other's service calls. `run_cell_block.sh`
  refuses to start when one is already on the domain; `fk_check.py` does not.

## The exact reproduction command

Run from the repository root, **on the host**. The container entry is host-side; the captures
are not.

```
docs/measurements/2026-09-04-waypoint-clearance/harness/run_campaign.sh
```

That runs `B1`, `B2` and `B3` — three container sessions, three captures each (BRINGUP,
PICKPLACE, LINE in that fixed order), **nine scenario runs**. It builds the workspace **once**
before the first capture (V11), quiesces 30 s between blocks, skips a block that has already
been taken (V8), and stops the campaign loudly if one aborts.

One block on its own:

```
docs/measurements/2026-09-04-waypoint-clearance/harness/run_campaign.sh B2
```

Then the compute stage, which runs no cell, and the FK cross-check, which runs `move_group`
with no simulator:

```
./scripts/enter dev bash -lc \
  'python3 -u /workspace/docs/measurements/2026-09-04-waypoint-clearance/harness/compute.py'
./scripts/enter dev bash -lc \
  'python3 -u /workspace/docs/measurements/2026-09-04-waypoint-clearance/harness/fk_check.py'
```

REPRO1 needs three compute runs — twice in one interpreter, once in a second one with a
different `numpy` (`../criteria.md` section 9 names both):

```
./scripts/enter dev bash -lc \
  'python3 docs/measurements/2026-09-04-waypoint-clearance/harness/compute.py --suffix _repro'
.venv/bin/python docs/measurements/2026-09-04-waypoint-clearance/harness/compute.py \
    --suffix _second
```

Then read the result:

```
python3 docs/measurements/2026-09-04-waypoint-clearance/harness/analyse.py \
    > /tmp/waypoint_clearance_analysis.txt
```

> **THE PRINT IS THE PRODUCT AND IT IS LONG. Redirect it to a file; do not pipe it through
> `head`.** A previous campaign's operator piped a 1034-line report through `head`, saw 143
> lines, and `tee` still reported **exit 0**. Every rule in `../criteria.md` section 7 prints
> whether or not it fires, and a truncated print looks exactly like a rig with fewer rules.

## What the wall clock costs, measured on the one shakedown

**The compute stage is this campaign's long pole and it is not close.** On the machine
`../criteria.md` section 9 names, one 62-waypoint trajectory took **76 s** to compute against
12 scene objects under both mesh sets — about **1.2 s per waypoint**, of which the vendor set's
98,552 triangles are most. **That figure is the shakedown's and it is superseded by the
memoisation below**; both are recorded, because the first is what the shakedown measured and
the second is what the shipped stage costs.

**The stage now serves TUNNEL1's bracketing distance maps from the maps `evaluate` has already
computed at each waypoint, instead of recomputing them.** They are the same numbers by
construction — the same kernel on the same transforms past the same censoring test — and the
change is verified by running the stage before and after on the shakedown's own capture and
comparing the output **byte for byte with only `compute_seconds` excluded**: identical, sha256
`919a8f29…`. Re-measured on the same host and the same trajectory: **71.6 s → 38.4 s**, from
1.16 s per waypoint to **0.62 s**, a factor of **1.87**. Nothing registered moved and REPRO1's
byte-identity is untouched.

**REPRO1 NEEDS THREE FULL COMPUTE RUNS, so the campaign's compute is about three times one
pass.** `../criteria.md` section 9 asks for the stage twice in one interpreter and once more
in a second one; each is a complete pass over every block, and the reproduction commands above
are the three. Budget accordingly: a `continuous_line` capture producing a few thousand
waypoints is an hour or more per pass per block, the three blocks are additive, and then the
whole thing is taken three times. **Budget the compute stage in hours and the capture stage in
tens of minutes.**

Two properties keep one pass finite and both are bounds rather than approximations: rule M's
broad phase censored 106 of 156 pairs on that trajectory, and the sub-sampling skip of
deviation 5 removes intervals no sub-sample could have changed. **The second of those was
unsound until 2026-09-04** — the reach table omitted each link's own mesh radius and shifted
the joint offsets by one — so it skipped intervals a sub-sample *could* have changed. Corrected
before the first trial; expect the sub-sampling to switch on where the old bound kept it off,
and expect the memoisation above to pay for it.

## The shakedown, and it is not data

`../criteria.md` section 10 permits **exactly one** shakedown run per stage. It proves the rig
starts, matches its subscriptions and writes a record. **It is not data**: it is published
under `../raw/shakedown/`, it is excluded from every figure in section 7, and **it may not be
used to set or adjust any threshold**. If it reveals a defect, the harness is fixed and
`../criteria.md` is not touched.

```
./scripts/enter dev bash -lc \
  'CITE_WC_OUT=/workspace/docs/measurements/2026-09-04-waypoint-clearance/raw/shakedown \
   bash /workspace/docs/measurements/2026-09-04-waypoint-clearance/harness/run_cell_block.sh \
        SHAKEDOWN --shakedown --captures BRINGUP'
```

`CITE_WC_OUT` is set **inside** the container command and not on the host side of
`./scripts/enter`, which does not forward it.

Reading it back — and **this output is not a figure of anything**:

```
python3 docs/measurements/2026-09-04-waypoint-clearance/harness/analyse.py \
    --raw docs/measurements/2026-09-04-waypoint-clearance/raw/shakedown \
    --shakedown-dry-run > /tmp/waypoint_clearance_shakedown.txt
```

**It has been run, once, and what it found is in
[`../raw/shakedown/NOTES.md`](../raw/shakedown/NOTES.md).** It caught four defects that would
each have corrupted the campaign, the largest of which read I4 before bring-up had applied the
planning scene — so every distance would have been a distance to an empty world. **The
committed harness is therefore not byte-identical to the one that ran**, section 10 grants no
second capture shakedown to prove the fixed one, and that residual is stated in the NOTES and
is the largest risk this rig carries into its first block.

**The exclusion is in code and it is three independent refusals**, not a convention about which
directory the operator redirected the run into:

1. `analyse.py` lists `*_trajectories.json` at the **top level** of `--raw` only, so a
   recursive glob cannot sweep `raw/shakedown/` in.
2. The `SHAKEDOWN` label is skipped wherever it is found.
3. Any row carrying `is_shakedown` is dropped, whatever its file is called.

`--shakedown-dry-run` lifts 2 and 3 **and nothing else**: it refuses to run if any campaign row
is present, and it prints a NOT-DATA banner above its output. It exists so that the analyser
could be demonstrated end to end before the campaign's first trial, which is the only way to
know that a rule prints before there is data to print it about.

## The files

| File | What it is |
|---|---|
| `common.py` | Every registered constant with the `criteria.md` section that registers it; the two-ended `snapshot`/`v1` pair; V2, V3, V7 and the vendor pin; the generated-scene, static-transform and plan readers; the log scrape for I2, I5, I6 and I9; `RecordWriter` and its `seal`. |
| `geometry.py` | I11 — forward kinematics from the description that actually ran, `<mimic>` couplings included — and the exact triangle-to-box distance, with the branch-and-bound culling, rule M's censoring bound, the sub-sampling motion bound, and `self_test`, which measures the kernel's residual against an independent convex QP. |
| `capture.py` | One block. Launches `./scripts/scenario` three times in the registered order with **one recorder alive across all three**; records I1, I2, I3, I4, I5, I6, I8, I9, I10, V4 and V14; writes a row per trajectory and **seals the rows with V1's closing reading — at the end of the block, or as the first act of the abort path**. |
| `compute.py` | The compute stage. Loads both mesh sets and checks section 2.3's identical-relative-path property, evaluates rule C's clauses, computes every per-(link, object) distance under both geometries, the tool-point steps, TUNNEL1's sub-sampling, GRIP1's sensitivity and V5's scene agreement, and draws FK1's registered sample. Runs no cell. |
| `fk_check.py` | I12 and VALID1. Launches `robot_state_publisher` + `move_group` with **no simulator and no controllers**, applies the generated scene, and calls `GetPositionFK` and `GetStateValidity` at the sampled waypoints. One arm per subprocess. |
| `run_cell_block.sh` | One block **inside the container**. Domain guard, environment sources, the load header, the runner under `tee`, the teardown sweep. |
| `run_campaign.sh` | The campaign, **on the host**. `build_once` (V11), `record_environment`, the 30 s quiesce, `already_taken` (V8) and the abort banner. |
| `analyse.py` | `criteria.md` section 7, applied to `raw/`. One function per registered rule; **every rule prints whether or not it fires**; a `DEVIATIONS` tuple at module top printed on every run. It reads the validity flags off the record and re-derives none of them. |
| `README.md` | This file. |
| `../raw/shakedown/NOTES.md` | What the one permitted shakedown proved, the defects it found, what was changed, and what it leaves open. **Not data.** |
| `.gitignore` | `__pycache__`. Nothing else in this directory is generated. |

## Where each file came from

**No campaign imports from another.** Every borrowing below is a **copy**, with the source file
and the commit it was copied at named in that file's own header. Both source directories are
FROZEN ([`../../README.md`](../../README.md) rule 2) and nothing in either is edited from here.

| File | Copied from | At |
|---|---|---|
| `common.py` | `docs/measurements/2026-09-04-following-error/harness/common.py` — the two-ended `snapshot`/`v1` pair, `manifest_vendor_sha`, `vendor_pin`, `model_hash`, `host_load`, `host_facts`, `v7`, `running_geometry`, `wilson`, and the `TrialWriter`/`seal`/`complete` shape that `RecordWriter` is | `0712272` |
| `capture.py` | `docs/measurements/2026-09-04-following-error/harness/measure.py` — the block header, the V1 opening reading taken before `rclpy.init()`, and the `try`/`except BaseException`/`finally` abort path whose first act is `writer.seal(...)` | `0712272` |
| `run_cell_block.sh` | `docs/measurements/2026-09-04-following-error/harness/run_cell_block.sh` — `set -uo pipefail` without `-e`, `set +u` around the setup sources, the domain guard, the load header, the teardown sweep, `python3 -u` under `tee` with `PIPESTATUS[0]`, the shakedown log retagging | `0712272` |
| `run_campaign.sh` | `docs/measurements/2026-09-04-following-error/harness/run_campaign.sh` — `already_taken`, `build_once`, `quiesce`, `record_environment` including the `bash -c` + `printf %q` marshalling of `scripts/_lib.sh`, `enter`, `run_one`, the abort banner | `0712272` |
| `analyse.py` | `docs/measurements/2026-09-04-following-error/harness/analyse.py` — the shape only: one function per registered threshold, every rule printing either way, `DEVIATIONS` at module top, `say`/`verdict`/`wrap`. **Every rule below it is this campaign's own.** | `0712272` |
| `fk_check.py` | `workspace/src/cite_skills/test/test_planning_pipeline.py` — the launch description, the five-entry parameter assembly with the joint-limits/Cartesian-limits merge, the `/tf` remappings on both nodes, the static-transform broadcast, the joint-state publisher, the `ApplyPlanningScene` diff plus the read-back that does not trust it, and `validity_of`'s contact intersection at line 418 | at `HEAD`, 2026-09-04 |
| `geometry.py` | **Nothing.** `criteria.md` section 2.5 records that ADR-0028's audit script was never committed, so there is no instrument to inherit and this one is built from scratch. | — |

## Nothing here edits the tree

`../criteria.md` section 0 and V1: nothing in `model/`, `workspace/src/`, `tools/`, `tests/`,
`scripts/`, `assets/` or `external/` is touched. The cell is measured exactly as the tree at
`c38a42c` ships it. **The campaign has no lever on the cell at all** — it does not even send a
goal; it watches what the shipped scenarios plan. The geometry substitution happens entirely
inside the compute stage, by reading a different file at the same relative path below the
collision root, so `description.collision.select` stays at the shipped `convex_hull`,
`MODEL_HASH` does not move and `v1_clean` holds throughout.

The vendor half of the tree is gitignored and holds no tracked file, so no `git diff` over it
can report anything; it is pinned by SHA instead, and every block records the SHA
`external/cite.repos` names against the SHA the imported checkout reads, **at both ends**.

## Fourteen things this rig cannot do, recorded here rather than discovered later

1. **It cannot measure the geometry of a refused plan.** The capture door is
   `DisplayMotionPath`, a response adapter that stands **after** `ValidateSolution`, and
   MoveIt's pipeline breaks the adapter chain on the first failure — so a refused trajectory is
   never published. REFUSE1 counts refusals and says nothing about how close anything was.
   **This is the bound on open-work #49's refusal question and the rig does not narrow it by
   one millimetre.**
2. **It cannot say what trajectory the cell would have produced under vendor geometry.** It
   replays a hull-run trajectory against the vendor meshes, which answers a narrower question.
   The start states come from physics that loaded the hull geometry, and Pilz's own generation
   self-checks against it.
3. **It cannot observe the carried work-piece.** Nothing in this tree adds it to the planning
   scene as an `AttachedCollisionObject`, so it is invisible to the planner **and to this rig**.
   A collision involving the carried part is neither measured nor excluded.
4. **It cannot measure self-collision.** Link-to-environment only. The generated SRDF's
   `disable_collisions` set governs the other question and is recorded, not evaluated.
5. **It cannot measure the executed path.** The controller tracks the waypoints with its own
   lag under a first-order plant, so the executed path is neither the waypoint set nor the
   interpolation TUNNEL1 samples. What TUNNEL1 measures is what `ValidateSolution` did not look
   at.
6. **It cannot make a trajectory happen.** It sends no goal and drives no arm. If a scenario
   plans nothing, the capture is empty — and rule C is what stops an empty capture reading as a
   quiet cell.
7. **It cannot attribute a log line to an arm where the launch prefix does not resolve it.**
   I2's reading (c) is the attribution; where it cannot resolve one, the trajectory is reported
   on its own line and enters neither pipeline population, and rule C-ii's equality falls back
   to the block total.
8. **It cannot order the door against the first plan without a parseable log timestamp.**
   Deviation 2: the two events are seen by two instruments with no common ordering token, and
   the clause prints NOT EVALUABLE rather than passing by default. The ceiling clause is
   unaffected.
9. **It cannot tell a topic name from a publisher.** This node's own three subscriptions put
   every expected `display_planned_path` name on the graph whether or not a cell exists, which
   the shakedown demonstrated. `publisher_count_by_topic` is the reading that means something
   and it is recorded beside the names.
10. **Its distance is not MoveIt's collision predicate**, and the campaign exists partly
    because of that. `criteria.md` section 2.2.1 establishes a configuration where the two
    disagree in this very tree. The compute stage is **unpadded**; `link_padding` and
    `link_scale` are recorded so that a disagreement is stated rather than reconciled.
11. **It cannot report a penetration depth.** Below zero is reported as `0` with a flag,
    because a penetration depth between a triangle soup and a box is not a single well-defined
    quantity.
12. **It cannot say anything about a censored pair beyond the bound.** Rule M: a pair beyond
    0.500 m is `> 0.500 m` and enters no distribution, so every verdict is a verdict about the
    near field and is stated with its censored count beside it.
13. **It cannot be run twice for a better sample.** V8: n is what it was, no capture is topped
    up, and a block that aborts is reported with the n it reached. `already_taken` enforces
    that on the host side and `_complete.json` is what it reads.
14. **It cannot prove its own capture-side fixes, and there are now more of them.** The one
    permitted capture shakedown ran against a harness that read I4 too early; that fix is
    committed and **unexercised**, and section 10 grants no second capture shakedown. Four
    further capture-side changes landed on 2026-09-04 and are unexercised too: the per-capture
    receipt index that I2 reading (c) joins on, the log-order attribution walk, the settled
    publisher reading taken **while the scenario runs** rather than after it exited, and the
    `finally` that kills `./scripts/scenario` on every exit from the capture block. Each is
    covered by a fixture run outside the repository and by **no** run of a cell. See
    [`../raw/shakedown/NOTES.md`](../raw/shakedown/NOTES.md), whose correction of 2026-09-04
    lists them.

## Recorded limitations, carried rather than fixed

**Deviations 7 to 11 in `analyse.py` are the rest of this list and are not restated here
(P1).** They are printed at the top of every analyser run. In one line each: rule M's
censoring is applied to section 4.3's **bound** while rule M's sentence is about the
**distance**, so the distributions extend beyond `CENSOR` and the near-field subset is
reported beside them (7); a publication is joined to a **receipt** by position, so a rule C-ii
shortfall shifts the pipeline attribution after it (8); V6 compares a different spread from the
registered one, V6's and V7's downgrades are left for the write-up, REPRO1's cross-interpreter
comparison scores an absent key as zero, and I4's re-read timer is shared across three arms
(9); three third-state slips and `--startup-ceiling`, which `criteria.md` registers nowhere
(10); and four exactness slips, including that the standing pair leaks into two counts it is
excluded from by name (11). **None of them moves a threshold**, and each names the direction it
errs in.


- **`compute.py --diagnostic-scene-from-generated-file` is not a campaign path and must never
  be used as one.** It takes the scene from the generated file instead of I4's read-back, which
  `criteria.md` I4 forbids for a measurement. It exists because the one permitted capture
  shakedown produced an empty read-back and the distance computation would otherwise ship
  unexercised. It writes `<label>_diagnostic.json`, which `analyse.py` does not read, and it
  prints a NOT-DATA banner.
- **`fk_check.py` restarts a `LaunchService` per arm in its own subprocess.** Two `move_group`
  nodes for two arms in one process is a rig this campaign has no evidence about, so it is not
  attempted.
- **The sub-sampling ceiling is a bound on the compute and not on the physics.** Every interval
  that hits `SUB_CEILING` is counted and its achieved sub-step is stated.
- **`SCENARIO_WALL_CEILING_S` (3600 s) is the harness's outer bound on one scenario
  subprocess** and is deliberately far above every ceiling the scenario itself carries, so that
  it is the scenario's ceilings that fire and never this one. It is not registered in
  `criteria.md` and decides no quantity. **No scenario ceiling is widened anywhere here.**
