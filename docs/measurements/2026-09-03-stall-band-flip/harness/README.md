# Harness — where option F's window flips, bracketed to 0.05 mm at both edges

105 trials if V12 holds, 87 if it does not; seven blocks; one launch per trial; **no
simulator anywhere in it**. [`../criteria.md`](../criteria.md) is the contract and this
directory is the code that satisfies it. Where this file and `criteria.md` disagree,
**`criteria.md` wins**.

**Nothing here runs a Gazebo-transport process**, so CLAUDE.md §10's partition rule binds
nothing in this directory (§4.2). If this rig ever grows one it goes through
`cite_bringup/gz.py` and nothing else (ADR-0042).

## Before anything

```sh
./scripts/validate-model          # the L0 tree is the one the plan describes
./scripts/build                   # V11: ONCE, before the first trial. run_campaign.sh does it
./scripts/test
./scripts/lint
```

`run_campaign.sh` runs `./scripts/build` itself and records its summary line into
`../raw/provenance.txt`, because V11 makes "the build happened once, before the first
trial" part of the record rather than part of the operator's memory. **`build_once`
enforces both halves of V11 rather than describing them:** it refuses to build a second
time once any trial record exists or once `provenance.txt` already carries a build block —
so a *resumed* campaign, which this script advertises, does not rebuild the workspace under
itself — and it **aborts the campaign when the build fails** instead of recording an exit
code and carrying on against a stale install.

`cite_test_hardware` builds only under `BUILD_TESTING`, which `./scripts/build` sets.
`run_block.sh` proves the plugin is present before any trial, so that a null can be told
apart from a rig that was never asked.

## The exact reproduction command

**The two coarse blocks, which is where the campaign starts and where this script stops:**

```sh
docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh
```

It stops there **on purpose**. §5.1 draws the distinction the whole design rests on: *the
step is a threshold and is registered; the interval is a bracket and is located by the
data.* A script that went on to refine would have to choose the refinement interval, and
that choice belongs to a person reading the coarse table. Read it:

```sh
python3 docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py \
    > /tmp/stall_band_flip_coarse.txt
```

then pass the located intervals — each of which must be an **adjacent pair of that arm's
own coarse grid**, and `measure.py` refuses anything else:

```sh
CITE_SBF_LO_F_LOW_MM=<a> CITE_SBF_LO_F_HIGH_MM=<b> \
CITE_SBF_HI_F_LOW_MM=<c> CITE_SBF_HI_F_HIGH_MM=<d> \
CITE_SBF_LO_S_LOW_MM=<e> CITE_SBF_LO_S_HIGH_MM=<f> \
    docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh LO-F HI-F LO-S

CITE_SBF_INV_STOPS_MM=<w,x,y,z> \
    docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh INV

docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh CTL
```

A block that has already been taken is **skipped rather than re-run**, so a resumed campaign
never silently tops a condition up (V8). A block that aborts **stops the campaign**, loudly,
with its exit code captured rather than discarded.

**A block that finished and a block that died part-way are now different things**, and they
were not. `measure.py` writes `<label>_complete.json` only after the last trial of the
schedule; a trials file **without** that marker is a block that aborted, and `run_campaign.sh`
skips it with a loud banner instead of the one-line `collected` a finished block gets — it is
still not re-run, because re-running it would top the condition up. The V1 flag is written at
the close of **each cycle** rather than after the whole block, so an aborted block keeps every
cycle that closed and V8's *"a block that aborts early is reported with the n it reached"* is
a number rather than a promise. Before both changes, such a block reported **n = 0
permanently** and the runner called it done.

## One block at a time

```sh
./scripts/enter dev bash -lc \
    'bash /workspace/docs/measurements/2026-09-03-stall-band-flip/harness/run_block.sh LO-C'
```

## Reading the result

```sh
python3 docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py \
    > /tmp/stall_band_flip.txt
```

It applies §7's rules and **prints every one of them whether or not it fires**, in three
states: `FIRED`, `did not fire`, and `NOT EVALUABLE` — which is not the same as `did not
fire`, and the distinction is the same one V14 exists for one level down. It writes no
verdict into any decision record, sets no band, proposes no value and chooses nothing (§0).
`ANALYSIS.md` is written from that print, later, by someone else.

> **THE PRINT IS THE PRODUCT AND IT IS LONG. REDIRECT IT TO A FILE; DO NOT PIPE IT THROUGH
> `head`.** The 2026-09-02 scenario-ceilings campaign's operator piped a 1034-line report
> through `head`, read 143 lines of it, and `tee` still reported exit 0 — so nothing said
> the other 891 lines existed. Every rule in `criteria.md` §7 prints, and a rule you did not
> read is a rule you cannot say fired or did not.

## The shakedown, and it is not data

§10 permits **one** shakedown run per harness. It has been run, and the output is published
with what it found in [`../raw/shakedown/NOTES.md`](../raw/shakedown/NOTES.md). **Read that
before the first campaign trial.** It is excluded from every figure in §7 and **may not be
used to set or adjust any threshold**. It revealed four defects, all fixed here;
`criteria.md` was not touched.

**The exclusion is now three independent refusals in code, and this file claimed it was one
when it was none.** It used to read *"`analyse.py` lists `raw/*_trials.json` at the top level
only, so the exclusion is in code rather than in a sentence"* — and that top-level glob is
not an exclusion at all. It rests entirely on the operator having set `CITE_SBF_OUT` to a
subdirectory: **a shakedown run without that variable writes `LO-C_trials.json` straight
into `raw/`, at the top level, under the campaign grid's own label, and the old glob admitted
it as data.** What refuses it now:

1. the top-level glob, which stops a recursive sweep of `raw/shakedown/`;
2. the `SHAKEDOWN` label, skipped wherever it is found;
3. an `is_shakedown` flag carried **on every row** by `TrialWriter`, dropped on whatever the
   file is called.

`analyse.py` **names what it refused** rather than dropping it silently, because a shakedown
excluded without a word is indistinguishable from a shakedown that was never there.

The command that produced it, recorded for reproduction and **not to be run again** — §10
permits one and it is used:

```sh
./scripts/enter dev bash -lc \
    'CITE_SBF_OUT=/workspace/docs/measurements/2026-09-03-stall-band-flip/raw/shakedown \
     bash /workspace/docs/measurements/2026-09-03-stall-band-flip/harness/run_block.sh \
        LO-C --shakedown'
```

**`analyse.py --raw .../raw/shakedown` now reports `Blocks collected (0)`** and names the
refusal, where it used to print a full §7 report over shakedown trials. That is the point:
what the shakedown found is in `NOTES.md`, which is a record written by a person, and not in
a rules report that looks exactly like a campaign's.

## The files

| File | What it does |
|---|---|
| `common.py` | the registered constants (the two coarse grids, the fine step, the two commands, the MIS and the three 0.005 mm tolerances, V7's 4.0), the two-ended V1 snapshot and conjunction, I9's load, V2's read-back off the running description, the two compiled front ends, the closed-form floor solved on the superseded build, the plan readers, `TrialWriter`, `LogCursor`, and the V4 and V14 evaluators |
| `arithmetic.py` | the reference implementation and §2's cross-check. **No reported figure comes from it**; `measure.py` and `analyse.py` do not import it |
| `predicate_eval.cpp` | a batch front end linking the **shipped** `gripper.cpp` unmodified: the stop conversion, I3's and I7's widths, and the §2 cross-check |
| `predicate_eval_superseded.cpp` | the same for the predicate at `4ef2d7c`, which is where `holding_S` and the closed-form floor come from |
| `build.sh` | compiles `predicate_eval` against `workspace/src/cite_skills`, records both source hashes and the binary's, then calls `build_superseded.sh` |
| `build_superseded.sh` | V12 in one script: a detached `git worktree` at `4ef2d7c`, compiled unmodified, its commit and binary sha256 recorded, the worktree removed again. Refuses a commit that is not an ancestor of `HEAD`, and refuses one whose header already declares the bands |
| `rig.launch.py` | the node set — `robot_state_publisher`, a real `ros2_control_node` over the generated controller configuration, the spawner in the plan's own stage order, a real `move_group` and the real skill server, all with the parameters the **production** launch file builds |
| `measure.py` | one block: the stop grid, the description surgery and its `repr()` round-trip check, the launch, `Grasp` (I1), the I2 scrape, `/joint_states` (I3), the second `GripperCommand` (I4), I5/I6/I7, and every validity flag computed where the block is taken and written onto the record |
| `run_block.sh` | the container-side door: the domain guard, the fixture-presence check, the build, and the per-block load capture |
| `run_campaign.sh` | §6's registered order on the host, with `build_once` for V11, the 30 s quiesce, the isolation values derived through `scripts/_lib.sh`, the resumed-campaign skip — which now tells a **complete** block from a **partial** one — and the abort banner |
| `analyse.py` | §7's rules — B, N, U, R, D, C, G, T, H, W — plus LO1, HI1, `flip_S_lo`, FLOOR1, INV1, CTL, P1–P6 and V1–V14, each printed either way, with the `DEVIATIONS` tuple at module top printed on every run |

**V6 exists.** This table claimed V1–V14 while `grep -c '\bV6\b'` returned **0** across
`analyse.py`, `common.py` and `measure.py` — every other rule was non-zero. V6 is a
registered rule with a decision consequence (a metric's finding downgraded to INCONCLUSIVE),
and §7.1's note about it reads as though it were being evaluated elsewhere. It was not
evaluated anywhere. It is now computed over `w_reached`, per block, against that block's own
grid step, and printed either way — see deviation 6 for which of §10's two readings of *"the
difference between adjacent stops"* was taken.

**Three instrument inconsistencies were closed rather than recorded**, because each was
two things naming one quantity differently — the shape that stops being harmless the moment
either side moves:

- **V4 read I2's `reports[-1]` while V14 and `measure.py` read `reports[0]`.** The same line
  today, because `execute_grasp` issues exactly one `command_gripper` and `LogCursor`
  brackets one action's segment — so nothing changes. All four sites now name the first
  line, which is the one the decision quantities `stalled` and `reached_goal` come from.
- **V7's reported "highest reading" scanned `load_1m` alone while `common.v7` flags on all
  three load averages.** A block flagged on its five- or fifteen-minute average was printed
  beside a highest-reading figure below the threshold — a flag and a number contradicting
  each other on one line. The scan now covers the same three keys at both ends and names
  which average and which end it came from.
- **`run_campaign.sh` iterated `"$@"` as given and did not enforce §6's registered order.**
  It held in practice — `refine` refuses a coarse pair that is not adjacent on the arm's own
  grid, and INV refuses a wrong stop count, so an operator who had not read the coarse table
  could not supply the arguments — but it held *emergently*. A requested list must now be a
  subsequence of `common.BLOCK_ORDER`, which is read from `common.py` rather than restated
  in the script (P1).

**Five rules were printed and not applied, and printing is not applying.** Rule R's verdict
was computed, printed and then discarded at the call site, so an endpoint it had just
declared INDETERMINATE still yielded BRACKETED; V12 gated nothing it names; V6 did not exist;
INV1 reported HELD from zero comparisons; and rule B waived a conjunct it could not evaluate.
All five now reach the decision they were registered to make. **A registered rule that prints
and does not bind is worse than an absent one, because the print is what a reader audits.**

## Where each file came from

Every file names its source and **the commit it was copied at**, in its own header. This
campaign's practice is copy-with-attribution; [`../../README.md`](../../README.md) does not
require the header, and it is here so that a reader of this directory can tell a copied file
from an original without diffing two directories. **No campaign imports from another, and
neither frozen directory is edited.**

- **`predicate_eval.cpp`** and **`predicate_eval_superseded.cpp`** — the **frozen**
  [2026-09-02 option-F harness](../../2026-09-02-option-f-regions/harness/README.md) at
  commit `3235cbc`. **Everything below each file's header block is byte-identical** to that
  directory's copy; the header is rewritten because it is the one part that makes claims
  about a campaign, and the claims it made were about that campaign's `criteria.md`.
- **`build.sh`**, **`build_superseded.sh`**, **`run_block.sh`** — the same directory at
  `3235cbc` (`build.sh`, `build_superseded.sh`, `run_arm_b.sh`). `build_superseded.sh` gains
  the ancestry refusal; `run_block.sh` gains the shakedown log tag.
- **`rig.launch.py`** — that directory's `arm_b.launch.py` at `3235cbc`, itself derived from
  `workspace/src/cite_bringup/test/test_grasp_predicate_launch.py`.
- **`measure.py`** — that directory's `measure_arm_b.py` at `ac11d84`, for the description
  surgery, the relaunch loop, the `Launch` and `Driver` shapes and the "a failed trial is a
  recorded trial" handling; and `test_grasp_predicate_launch.py` at `HEAD` on 2026-09-03 for
  the **closing**-stroke stop orientation.
- **`arithmetic.py`** — that directory's `arithmetic.py` at `3235cbc`.
- **`common.py`** — **two** sources, and both are named because the halves came from
  different places: that directory's `common.py` at `ac11d84` for the front ends, the
  `REPORT` pattern, the plan readers, `LogCursor` and `TrialWriter`; and the **frozen**
  [2026-09-02 scenario-ceilings harness](../../2026-09-02-scenario-ceilings/harness/README.md)'s
  `common.py` at `b2fd9ba` for the **two-ended** `snapshot` / `v1` pair.
- **`run_campaign.sh`** — the option-F directory's at `62051df` for the `collected()` skip,
  the quiesce, the abort banner and `record_environment`; and the scenario-ceilings
  directory's at `ee1c997` for `build_once`.
- **`analyse.py`** — the scenario-ceilings directory's at `98fbbfc`, which took the shape
  from the option-F directory's at `e559264`: one function per registered threshold, the
  rule prints even when it does not fire, and the `DEVIATIONS` tuple at module top. Every
  rule in it is this campaign's own.

## Nothing here edits the tree

`criteria.md` §0 forbids editing `model/`, `workspace/src/`, `tools/`, `tests/` and
`scripts/` — the five paths V1 watches — and this harness reads all five and writes only
under this campaign's own `raw/`, plus its two ignored binaries beside itself. **Touching
one of them does not contaminate the data; it destroys it**, because V1 discards every block
taken while a watched path differs from `c38a42c`. The flag is computed at both ends of
every cycle and travels on every record, so a concurrent writer flips it rather than going
unnoticed (V10).

`build_superseded.sh` creates a `git worktree` and removes it again in a trap, outside the
repository's own tree, for the same reason: a second checkout of a different commit sitting
inside the tree would be exactly the thing this campaign claims not to have done.

## Ten things this rig cannot do, recorded here rather than discovered later

1. **It cannot say where a real jam stops.** Every stop is synthetic, at a position this
   harness chose and the description declares. ADR-0052 §A.9.2 records that F's central
   claim rests on a quantity nobody has measured, and **this campaign does not narrow it by
   one millimetre**. Rule G is the refusal that keeps that straight, and **no change to this
   harness can fix it** — fixing it means measuring a fouled finger, which needs a part and
   a simulator, and this rig has neither.

2. **It cannot produce a grasp, so it cannot say anything about one.** Nothing is between
   the pads and nothing can be. That is also why `criteria.md` records the 2026-09-02
   campaign's **rule W as NOT APPLICABLE** here rather than as a silence: the population that
   rule quantifies over is empty, and a silence is read as a clearance.

3. **It cannot reach the wide edge the way a part would.** Arm HI reaches `edge_hi`
   *precisely because* the jaws are empty. `flip_F_hi` is a property of the predicate and of
   nothing else, and the 2026-09-02 campaign's rule W — which fired, because the jaws square
   a yawed part up before the pads meet it — **stands unchanged whatever this campaign
   reads**.

4. **It cannot separate "the stop produces the stall" from "the plugin does".** CTL changes
   two things at once, and `criteria.md` §5.3 restates its role for exactly that reason: it
   is the controlled comparison whose quantity is **where the joint comes to rest**. No
   second control arm is added — that would be a design change, and this campaign is already
   105 trials.

5. **It cannot settle [`docs/open-work.md`](../../../open-work.md) #25**, is not powered to,
   and its CTL result may not be written up as evidence about it in either direction.

6. **It cannot tell F from a command-referenced predicate.** INV evaluates four fixed stops
   at two commands, and `criteria.md` §5.2 computes that the superseded predicate returns
   true at all eight of those points — so a predicate reading the command exactly as
   `holding_S` does would pass INV unchanged. INV bounds how wrong §2's reading of the source
   could be at four points; it is not a demonstration.

7. **It cannot produce a P2 result.** ADR-0052 records that the physical gripper is driven
   through the SDK's service layer and has **no `GripperActionController` at all**, so
   nothing here transfers to hardware. Phase 2.B bring-up settles it and nothing before it.

8. **It cannot detect a description that never reached the running node** except through V2's
   read-back, which is a `ros2 param get` against `description_publisher`. If that call
   returns nothing, `v2_ok` is `False` — the conjunction is of two positive findings, so "no
   mock found" is not reachable by not looking — but the harness cannot then say whether the
   node was absent or the parameter was.

9. **It cannot recover a trial whose I2 line was never written.** V14 excludes it and reports
   it as an instrument loss, counted apart from V4's and V5's exclusions and **never recorded
   as a measured `false`**. What it cannot do is reconstruct the two booleans: I4 is a
   *second* event against a joint already resting on the stop, so its agreement with the
   first is what V14 **checks** rather than what it assumes.

10. **It cannot choose between two brackets.** If more than one adjacent fine-grid pair
    carries opposite verdicts, `criteria.md` registers no rule that selects one — rule U
    covers that case on the coarse grid and rule N covers the case of none. `analyse.py`
    reports every such pair and declines to claim a bracket; it is deviation 3, registered
    before any trial rather than judged afterwards.

## Recorded limitations, carried rather than fixed

Found by an adversarial pre-freeze review, before the first campaign trial. Each is
**carried deliberately**: changing it would change a mechanism after the rules were
registered, and `criteria.md` §10's shakedown clause and V9 both say the harness is fixed
before the data exists and the *criteria* never after. Every one is a numbered deviation in
`analyse.py`'s `DEVIATIONS`, printed at the top of every run, so a write-up cannot drop one.

- **Rule B's conjuncts are evaluated over the surviving repeats** (deviation 7). V4, V5 and
  V14 exclude a *trial* from every bracket, so by the time rule B runs the excluded repeats
  are gone — and a `satisfied` unanimity clause can rest on **n = 1** after two of three
  repeats were excluded. The criteria does not disambiguate; the surviving-repeats reading
  is registered as the one taken, and every BRACKETED line now prints **collected vs
  surviving n at both endpoints**, with a marker when an endpoint rests on a single repeat.
- **V13's discard path is unreachable** (deviation 12). `measure.py`'s `rig_description`
  raises *before* `run_trial`'s `try`, so a launch that finds a non-production backend takes
  the **whole block** down rather than landing a `v13_ok: False` record. That is stricter
  than the rule and admits nothing wrong — but it **compounds an aborted block**, whose n is
  then whatever its closed cycles hold.
- **`run_block.sh`'s domain guard reads a failed `ros2 node list` as "domain clear"**
  (deviation 13). `ros2 node list 2>/dev/null | grep -c …` returns 0 both when the domain is
  empty and when the command failed outright. It is inherited verbatim from a frozen
  ancestor and is **protective rather than a datum** — nothing in §7 reads it.
- **`build_superseded.sh` carries V12's commit a third time, in shell.** `common.py` names
  it once for the harness and `analyse.py` reads it from there, but the build script has its
  own copy. It is left as it is on purpose: the script's copy is what **produces** the
  provenance and `common.py`'s is what **checks** it, so the two agreeing is the check, and
  collapsing them would remove the comparison.
- **`common.wilson` exists and nothing calls it** (deviation 14). No figure this campaign
  decides on is a proportion — the verdicts are set memberships, an identity and a distance
  — and the exclusion counts are reported with their denominators rather than as rates,
  because §8 lists *"a rate of anything"* as not measured here. The instrument is kept
  uncalled so that a write-up which does report a proportion uses it rather than
  reinventing one.
- **The quiesce is per cycle and per block, not per trial** (deviation 5). §6 reads
  *"quiesce 30 s between a teardown and the next launch"* and *"each is one launch"*, which
  is 104 quiesces; the rig performs **19**. No decision quantity moves — there is no
  simulator, no physics and no state shared between launches — and the campaign is **not
  lengthened** to close it.
