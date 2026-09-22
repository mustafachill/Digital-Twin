# Harness — is a run of this cell reproducible at all, and where does the irreproducibility enter?

The rig for [`../criteria.md`](../criteria.md). It runs five arms: a ROS-free
probe world under one seed (**A**), the same probe under five different seeds
(**B**), the same probe perturbed by 1e-6 m (**A'**), the whole cell twice
(**C**), and a symbol scan with its command written down (**S**).

**Read [`../criteria.md`](../criteria.md) first.** Every threshold, every n,
every instrument and every validity rule lives there and is deliberately not
restated here (P1). What this file carries is how to run the rig, what each file
is, where each came from, and **what the rig cannot do**.

## Before anything

- **[`../criteria.md`](../criteria.md) is frozen from the first campaign trial**
  ([`../../README.md`](../../README.md) rule 1). A threshold discovered to be
  wrong is **applied literally and recorded as wrong**, as a numbered deviation
  in `ANALYSIS.md`, against data already collected. Nothing in this directory
  may edit it.
- **`harness/` is frozen once the first trial has run, and `raw/` with it**
  (rule 2). It is the code that produced the data, so editing it makes it no
  longer that.
- **One writer in this checkout** (V5). Two `git` readings are taken at both
  ends of every trial, and a concurrent agent editing `model/`, `workspace/`,
  `tools/`, `tests/`, `scripts/`, `assets/`, `external/` or `.github/` mid-trial
  **flags that row**. It does **not** discard it: V1's drop condition is a
  missing recorded field and nothing else, which is what the clause says, and an
  exclusion criterion the analyser invented would be the unregistered exclusion
  V8 and V9 exist to forbid. `analyse.py` prints every flag beside the row it
  belongs to and `ANALYSIS.md` is where a reader decides what one is worth.
- **`docker ps` must be empty before every block** (V-container).
  `run_campaign.sh` **refuses** rather than warning. CLAUDE.md §2 records a
  whole `./scripts/test` reading lost to a `dev` container that was already up:
  `exec_in_container` reuses it with `compose exec`, which does not run the
  image's entrypoint, and nothing of ours executes at all.
- **This rig runs a simulator.** ADR-0042 binds: every Gazebo-transport process
  goes through `cite_bringup.gz` and nothing else (V10). An unpartitioned
  `gz model --list` reaches no world and **exits 0** — plausible silence, on a
  campaign whose whole question is whether two silences are the same silence.

## The exact reproduction command

Run from anywhere, **on the host**. The container entries are host-side; the
probe trials are not.

```
docs/measurements/2026-09-22-is-a-run-reproducible/harness/run_campaign.sh
```

That runs the one permitted shakedown, then **A B A B A B A B A B** (the
registered alternation, V-order), then **A' ×2**, then **C ×2**, then **S**. It
builds the workspace **once** before the first block (V6), checks `docker ps`
before every block (V-container), and skips any trial whose record already
exists (V8, resumability).

Then read the result:

```
python3 docs/measurements/2026-09-22-is-a-run-reproducible/harness/analyse.py \
    > /tmp/is_a_run_reproducible.txt
```

> **THE PRINT IS THE PRODUCT AND IT IS LONG. Redirect it to a file; do not pipe
> it through `head`.** A previous campaign's operator piped a 1034-line report
> through `head`, saw 143 lines, and `tee` still reported **exit 0**. Every rule
> in [`../criteria.md`](../criteria.md) §7 and §10 prints whether or not it
> fires, and a truncated print looks exactly like a rig with fewer rules.

One arm on its own, for a re-run of a single lost trial — **note that V8 forbids
topping an arm up**, so this is for a trial whose record does not exist:

```
./scripts/enter dev bash -lc \
  'python3 /workspace/docs/measurements/2026-09-22-is-a-run-reproducible/harness/trial_probe.py \
     --arm A --index 3 --seed 20260824 --x-offset 0.0 --label A_03 \
     --out /workspace/docs/measurements/2026-09-22-is-a-run-reproducible/raw'
```

## The shakedown, and it is not data

[`../criteria.md`](../criteria.md) §6 permits **exactly one** shakedown,
published under `../raw/shakedown/`, excluded from every figure, and **it may
not set or adjust any threshold**. `run_campaign.sh` runs it as its first act
and skips it if its record already exists. If it reveals a defect, the harness
is fixed and `../criteria.md` is not touched.

**The exclusion is in code and it is three independent refusals**, not a
convention about which directory the operator redirected into:

1. `analyse.py` lists `raw/*.json` at the **top level** only, so no recursive
   glob can sweep `raw/shakedown/` in;
2. any label beginning `SHAKEDOWN` is skipped wherever it is found;
3. any row carrying `is_shakedown` is dropped, whatever its file is called.

## The files

| File | What it is |
|---|---|
| `probe.sdf.in` | The probe world, as a template. Two plugins, a ground plane, one 50 mm box off equilibrium at step 0, and the `<physics>` block copied verbatim from the generated world. The initial pose is a parameter, because A' varies it and nothing else. |
| `common.py` | Every registered constant with the `../criteria.md` clause that registers it; the two-ended `git` reading (V1); the load reading (V7); `physics_agreement` (V-physics); `build_probe_world`; the record writer. |
| `trial_probe.py` | One probe trial — arm A, B or A'. Runs inside the container. V-physics before the server starts, `ModelPoses` subscribed before it starts (V4), I2's at-rest rule applied literally, one JSON record out. |
| `trial_cell.py` | One arm-C trial. Runs **on the host**: it starts `./scripts/scenario pick_and_place --zone cell_b` through a pty and starts the I1 reader in a container of its own. Scrapes the verdict line, the scenario's own `Ran N tests in Xs` duration, the harness wall duration beside it, and V-planner's fallback counts **restricted to the region the cell wrote**. |
| `read_workpiece.py` | Arm C's instrument. Holds the **same** `ModelPoses` subscription arms A/B/A' use, beside a running cell, and takes I3 on the event of `launch_test` printing its pre-shutdown summary. Also records V3's world hash for arm C, and the trailing-sample spread on the rows that took the registered fallback. |
| `scan_symbols.sh` | Arm S. `nm -D -u <lib> \| c++filt \| grep -i rand` over every shared object under both vendor trees, with the command, the list and `uname -m`. Reported; no pass/fail (T6). |
| `run_campaign.sh` | The registered order, the `docker ps` refusal, `build_once` (V6), `record_environment`, and the skip that makes it resumable (V8). |
| `analyse.py` | `../criteria.md` §7 and §10 applied to `raw/`. One function per registered rule; **every rule prints whether or not it fires**; `DEVIATIONS` at module top, printed on every run. |

## Where each file came from

**No campaign imports from another.** Every borrowing below is a **copy**, with
the source file and the commit it was copied at named in that file's own header.
Each row names the commit that source file last landed at, so a reader can
`git show <commit>:<path>` and see exactly what was copied. Every source
directory below is FROZEN ([`../../README.md`](../../README.md) rule 2) and
nothing in any of them is edited from here.

| File | Copied from | At |
|---|---|---|
| `common.py` | `docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/trial.py` — `load_average`, `installed_configuration`'s read of the configuration under test off `ros2 pkg prefix cite_generated`, and the one-invocation-one-record shape | `fca1391` |
| `trial_probe.py` | the same file — the bring-up/sample/teardown skeleton, the SIGINT-then-bounded-wait stop, and the console capture | `fca1391` |
| `run_campaign.sh` | `docs/measurements/2026-09-04-following-error/harness/run_campaign.sh` — `already_taken`, `build_once`, `record_environment`, `enter`, the abort banner | `30d916c` |
| `run_campaign.sh` | `docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/run_campaign.sh` — `sweep`'s container check, here tightened into a refusal | `28de922` |
| `analyse.py` | `docs/measurements/2026-09-04-following-error/harness/analyse.py` — the shape only: one function per registered rule, every rule printing either way, `DEVIATIONS` at module top. **Every rule below it is this campaign's own.** | `601a062` |
| `analyse.py` | `docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py` — the same shape, one step further back | `8a35a03` |
| `probe.sdf.in` | `workspace/src/cite_generated/worlds/cell_b.sdf` — the `<physics>` block, **verbatim**, held equal by V-physics | `f79ee02` |
| `probe.sdf.in` | `tests/scenarios/pick_and_place.py:_workpiece_sdf` — the 50 mm box, its computed inertia and its `<mu>` | `ee85e39` |
| `read_workpiece.py` | `tests/scenarios/continuous_line.py` — the long-lived `ModelPoses` subscription held for the whole run, rather than a process per sample | at `6c66cb9` |
| `read_workpiece.py` | `tests/scenarios/_cell.py:carried_models` — **imported, not copied**: it is repository source rather than a frozen campaign's, and it is the derivation the scenario itself uses to name the part it spawns | at `6c66cb9` |

## Nothing here edits the tree

[`../criteria.md`](../criteria.md) §0 and V1: nothing in `model/`,
`workspace/`, `tools/`, `tests/`, `scripts/`, `assets/`, `external/` or
`.github/` is touched. The cell is measured exactly as the tree at `6c66cb9`
ships it — shipped world, shipped controller configuration, shipped launch,
shipped scenario. **The campaign's only levers are a seed value, a 1e-6 m offset
in one world file this directory writes, and nothing else.**

## The two numbers this harness chose, and why

`../criteria.md` fixes neither, and both are stated here so they can be argued
with rather than guessed at. Both are in `common.py` beside this reasoning.

**`PROBE_ITERATIONS = 15000`.** `max_step_size` is 0.001 s and
`real_time_factor` is 1, so that is **15.0 s of simulated time** and about 15 s
of wall clock on a host that keeps up — which a two-model world with no ROS in
it does comfortably. The free fall is 0.319 s; a corner impact with zero
restitution (SDFormat's default) and `mu` 1.0 settles within about a second of
pivoting, so the body is down well inside 3 s. I2 needs two samples at least
1.0 s apart, found by a 0.2 s poll, so rest is **detected** by about 4 s in the
worst case, leaving over 11 s of margin.

**`--iterations` strengthens I2 and does not replace it.** It makes every trial
stop at the same *simulated* time, so the final reading is not taken at a
wall-clock instant that drifts between trials. The at-rest rule is registered in
`../criteria.md` §4, it is evaluated on every trial whatever this number is, and
a trial that does not reach rest inside the 120 s ceiling is an instrument loss
under V11.

**`PROBE_POSE = (0, 0, 0.5, 0.6, 0.7, 0.8)`.** 0.5 m of drop reaches 3.13 m/s,
and the impact — not the fall — is what amplifies a 1e-6 m difference. None of
the three rotations is a multiple of a quarter turn, so the box meets the ground
on a **corner** rather than an edge or a face: the lever arm from the contact
point to the centre of mass decides the resulting rotation, and a 1e-6 m shift
of the body moves that lever arm. `mu` 1.0 on both surfaces means the corner
**pivots** rather than slides, which turns the impact into a tumble instead of a
skid. **Whether that is enough sensitivity is not assumed — it is arm A's
control question, T3 measures it, and rule N fires if it is not.**

## Twelve things this rig cannot do, recorded here rather than discovered later

1. **It cannot see orientation.** I1 returns position only
   (`../criteria.md` §4). A tumbling box's orientation is the more sensitive
   channel and this door does not offer one. Registered as a limit of the
   campaign, not worked around with a second subscriber.
2. **It cannot say anything about two concurrent sides.** No pair is run (§1.2).
   A run that does not reproduce against itself can never agree with a
   concurrent twin, so the sequential question is the necessary condition — and
   it is the only one asked.
3. **It cannot localise arm C's divergence to a line.** Q4 localises it to a
   layer. One position per trial is the whole instrument (§8).
4. **It cannot tell a deterministic solver from an unexercised one.** A
   fixed-step rigid-body integrator can be perfectly reproducible while drawing
   from no RNG at all, and arm S cannot distinguish those either — which is
   exactly why T6 carries no pass/fail.
5. **It cannot prove the probe physics is the cell's physics beyond the
   `<physics>` block.** V-physics compares that block and nothing else. Gravity,
   the engine choice and the solver are compared by the fact that neither world
   declares them, which is an argument and not a measurement.
6. **The contact pair is not the cell's, and T5's sentence is the reason this
   matters.** The probe's box strikes an **infinite ground plane** and nothing
   else. The cell's box is carried by two **gripper pads**, set on a **table**
   and placed on a **conveyor** — four contacts, on moving bodies, with the
   arm's own dynamics behind them. Limit 5 above covers the `<physics>` block;
   this is a different statement, about what the solver is asked to solve.
   **T5's permitted sentence localises the irreproducibility to "the
   asynchronous coupling" and away from "the solver" on the strength of arm A
   reproducing — and arm A has never touched a single one of the cell's
   contacts.** A solver that is deterministic on one plane contact and not on a
   four-body grasp would produce exactly the combination T5 permits, and this
   rig cannot tell that apart from the coupling. Whoever writes `ANALYSIS.md`
   carries this sentence into it beside the verdict.
7. **It cannot reproduce arm C's schedule.** `gz_ros2_control` runs the
   controller managers inside the server process while `move_group` and the
   skill server are separate asynchronous processes; when a trajectory lands
   relative to a physics step is not under this rig's control and is not
   measured by it.
8. **Its arm-C reading depends on a log line arriving in time.** `launch_test`
   writes to whatever `./scripts/scenario` hands it, and `exec_in_container`
   forwards only `CITE_*` and `ROS_DOMAIN_ID`, so `PYTHONUNBUFFERED` cannot be
   handed across. A pty is opened for that reason, and the registered fallback
   reading covers the case where it still misses. **`i3_source` says which
   reading was used on every row.**
9. **It cannot rule out the arm-C reader's own container being a confound.** The
   reader is a second container on a host-networked machine. It speaks Gazebo
   transport only and starts no ROS node, but it is a process this campaign
   added beside a run it is measuring, and that is stated rather than dismissed.
10. **It cannot measure a rate.** Five trials, five trials, two, two and one
   scan, on one machine at one commit (§11). Every number is a count or a value
   over the trials that ran.
11. **It cannot say anything about `cell_a`, about a pair, about hardware, or
    about any host but the one §9 names.**
12. **It cannot make a null into a clearance.** Rule N is implemented as a gate
    in `analyse.py`, and if arm A' does not move the metric then T1 and T2 print
    NOT ADMISSIBLE rather than passing. This is the rule most likely to fire.

## Recorded limitations, carried rather than fixed

- **V1 drops a row for a missing field and for nothing else, and the other three
  conditions are flags.** Its operative sentence is *"the analyser drops any row
  without **them**"* — *them* being the two recorded readings — and that is
  executable as written, so it is applied as written. HEAD equality across the
  two ends, the `--is-ancestor` clause and the protected-tree porcelain filter
  are all evaluated and **printed as flags on rows that stay admitted**. They
  were drop conditions in a draft of `analyse.py`; a pre-first-trial review
  found that made the implementation stricter than the frozen rule, which is an
  unregistered exclusion criterion, and they were demoted. `analyse.py` prints
  the whole interpretation at the top of every run, under `INTERPRETATIONS`, and
  both ends' raw porcelain is on every record so any stricter reading is
  recoverable by a reader who wants it.
- **`INTERPRETATIONS` has a boundary and it is stated in the code.** An
  interpretation may make a **silent** clause concrete; it may not override a
  clause that is executable as written, nor change which rows are admitted
  relative to the literal reading.
- **V3 and T3 pull in opposite directions and `analyse.py` says so.** V3 refuses
  to compare two trials with different world hashes; T3 *requires* comparing arm
  A' against arm A, whose worlds differ by construction because the perturbation
  *is* a different world file. V3 is applied where a hash difference would be
  accidental (T1, T2) and not where it is the registered independent variable
  (T3). Both hashes are printed beside the T3 verdict.
- **`analyse.py` re-derives the validity flags rather than reading them off the
  record.** The 2026-09-04 campaign does the opposite, for a good reason: a flag
  computed where the block was taken cannot be recomputed against a tree that
  has since moved. Here every validity input is a *literal* recorded on the row
  — two git readings, a world hash, a partition string, a boolean — so
  re-deriving is re-reading, not re-measuring. Nothing is recomputed from a tree
  or from a cell.
- **T3's threshold is the perturbation's own value, and that is a real edge.**
  T3 declares SENSITIVE when a 1e-6 m offset moves the outcome by *more than*
  1e-6 m, and the probe's ground plane is infinite and centred, so the dynamics
  are translation-equivariant in x: a rig that amplifies **nothing** returns
  exactly 1e-6 m and the verdict turns on the last bits of the base coordinate.
  **T3 is frozen and is applied literally (V9); nothing here moves it.**
  `analyse.py` prints `delta / perturbation` beside every pair, so a
  pass-through at ≈1.000000 is visibly distinct from amplification, and says in
  the verdict that landing there is a **numbered deviation for `ANALYSIS.md`**
  and not a re-run.
- **I2 cannot tell a body at rest from a frozen subscription.** `ModelPoses`
  keeps only its newest snapshot and returns it forever, and `position()`
  discards the `Pose_V` header stamp, so a publisher that stopped and a body
  that stopped read identically under the at-rest rule. **I2 is unchanged.**
  `analyse.py` prints, per probe row, the count of **distinct** sampled
  positions and the wall time of the **last change**, so a frozen tail is
  visible rather than counted as rest.
- **V-planner's counts are restricted, because the instrument counted the
  advice.** `scripts/scenario:189-190` prints both `planner fallback:` strings
  itself, in its pre-run block, telling the reader to grep for them — so a
  whole-log count is at least 1 on every run and would have flagged **every**
  arm-C trial. The flag is computed from lines carrying the skill server's own
  logger prefix, after the cell's output starts; the raw whole-log counts stay
  on the record and are printed beside the restricted ones. Same defect class as
  the whole-log grep CLAUDE.md §2 records counting a verdict out of a commit
  body echoed by CI.
- **Arm C's seed read-back is not independent and the record says so.**
  `common.SEED_A` is `scripts/scenario:90`'s own default, so the seed line the
  scenario prints is identical whether or not `CITE_PHYSICS_SEED` crossed the
  container boundary. The probe arms read `/proc/<pid>/cmdline`; arm C has no
  equivalently cheap independent source, so its row carries
  `seed_readback_is_independent: false` rather than a field that reads like a
  passed check.
- **`scan_symbols.sh` also prints a defined-symbol scan that I5 does not
  register.** It is labelled as context in the output and is not part of arm S's
  registered instrument. It is there because an undefined-only answer cannot
  distinguish a library that defines its own generator from one that uses none.
- **The `DEVIATIONS` tuple is empty and `INTERPRETATIONS` is not.** A deviation
  is where an interpretation had to *change* after data was seen; an
  interpretation here is where the criteria's wording had to be made concrete
  *before* the first trial in order to be executable at all. Both print on every
  run. If any of the five interpretations turns out to have been the wrong
  reading, that becomes a numbered deviation applied to data already collected —
  never a re-run until the definition suited.
