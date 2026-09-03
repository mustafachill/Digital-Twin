# Shakedown — one run, and it is not data

[`../../criteria.md`](../../criteria.md) §10 permits **one** shakedown run per harness,
before the first campaign trial, to prove the rig starts, connects and writes a record.
This is it, and there was only one.

- **What ran:** `harness/run_block.sh LO-C --shakedown`, inside the container, with
  `CITE_SBF_OUT` pointing at this directory. Two trials in one invocation — one at a stop
  of **50.00 mm**, and one on **plain `mock_components/GenericSystem` with no stop at
  all**, which is arm CTL's plugin substitution. Two, because the two rig shapes substitute
  different plugins and a defect in either would otherwise have been found during the
  campaign rather than before it.
- **The stop is on neither campaign grid, deliberately.** 50.00 mm is not a point of arm
  LO's (46.00–48.00 mm) or arm HI's (52.00–54.00 mm) coarse span, so no record here can be
  mistaken for a campaign trial by its lever. It is inside F's window, so the chain is
  exercised to a `holding_F` of `true` rather than only to a rejection.
- **When:** 2026-09-03, on the machine `criteria.md` §9 names, at `HEAD` = `554a8a9`, with
  the watched paths clean against `c38a42c` at both ends.
- **Output:** `SHAKEDOWN_trials.json`, `SHAKEDOWN_header.json` and `logs/` beside this file.
- **Where its build provenance lives, and where it does not.**
  `../predicate_eval_provenance.txt` is **truncated** by every `build.sh` run, so the first
  campaign block will overwrite the shakedown's copy; the version committed alongside this
  file is the shakedown's, and git is what preserves it.
  `../provenance.txt` and `../predicate_eval_superseded_provenance.txt` carry the
  superseded build, and `SHAKEDOWN_header.json` carries the same worktree commit and binary
  sha256 on the record itself — which is what V12 actually asks for.

> **IT IS EXCLUDED FROM EVERY FIGURE IN §7 AND MAY NOT BE USED TO SET OR ADJUST ANY
> THRESHOLD.** The exclusion is in code, not in this sentence: `analyse.py`'s `load_blocks`
> lists `raw/*_trials.json` at the **top level only**, so this directory cannot be swept
> into a campaign figure by a recursive glob. Every threshold in `criteria.md` is derived
> from the geometry, from the gate's own 0.05 mm, or from the declared tolerances, and none
> of them needed a shakedown to exist.
>
> **No number in this directory is a result.** Two trials, one machine, one commit, nothing
> registered in advance. Quoting one anywhere — in `ANALYSIS.md`, in ADR-0052, in
> `CLAUDE.md` — would be exactly the mistake §11 exists to prevent.

## What the chain did, end to end

Launch → stop applied → predicate evaluated on the running node → record written with its
validity flags → analyser print. All five links exercised.

- **The launch came up and the fixture engaged.** I5 read the plugin's own
  `has reached a declared stop at 0.405605` warning; I6 found no start-outside-the-stops
  refusal; the fixture named itself.
- **The verdict came off the running node**, out of `Grasp.Result.holding`, with
  `expect_object=false` — not out of `predicate_eval`.
- **I7 read a rest error of exactly 0.000000 mm** against `gripper_width_for` on the drive
  position the fixture was actually given, and the `repr()` round trip through the
  description was exact. §7.0's whole tolerance depends on that serialisation, and it holds.
- **V1 clean at both ends of the cycle**, the two `git` readings agreeing and `HEAD`
  unmoved. **V2 read 13 hull collision references off the running `description_publisher`**,
  not off the file the harness wrote. **V13** found `gz_ros2_control/GazeboSimSystem`
  before every substitution.
- **V12 is satisfied**: the superseded predicate is a build of `4ef2d7c` in a detached
  worktree, with its binary's sha256 in `../provenance.txt`, and the worktree was removed
  again — `git worktree list` shows only the checkout.
- **The §2 cross-check passed.** The shipped code, asked through `predicate_eval`,
  reproduces `criteria.md` §2's whole table: both window edges, both drive positions, the
  discrimination margin, the validator ceiling, and §2.2's closed-form floor at
  **47.121519 mm** — solved by bisection on the superseded **build's** own answer, not on a
  restatement of its inequality.
- **P6's rest position was reproduced to the digit.** The no-stop trial rested at
  **0.30 rad** and reported `reached_width_m` = **60.915272 mm**, which is what
  `stall_timeout` × `max_drive_rate_rad_s` comes to through the shipped linkage, with
  `stalled=true`, `reached_goal=false`, `holding_F=false`, `holding_S=true` and no stop
  warning. **That is a rig check and not a result** (§7.4), and this run is not the CTL
  block.

## How long a trial takes, so the campaign's wall clock can be estimated

- Node lifetime, from the launch's own log timestamps: **3.132 s** for the stopped trial
  and **2.946 s** for the no-stop one.
- End to end, including the container start, the domain check and building both front ends:
  **15 s** for the whole invocation.
- So a trial costs roughly **5 s** including launch and teardown. At 105 trials, 19 cycles
  and a 30 s quiesce between every cycle and before every block, the campaign is on the
  order of **20 minutes** of trial and quiesce wall clock, plus the one `./scripts/build`
  V11 puts before the first trial.

## Four defects it revealed, all fixed in the harness

`criteria.md` was **not touched**. §10: if the shakedown reveals a defect, the harness is
fixed and that file is not. None of these moved a threshold.

1. **`analyse.py` reported both of V14's exclusions as one number, and called them all
   "instrument losses".** The no-stop trial was excluded for an I4-versus-I2 *disagreement*,
   which is a different sentence from "the log line was never read" — and V14 exists
   precisely to keep an absent reading distinguishable from a measured one. **Fix:** the two
   are counted and printed apart, as `V14 (instrument loss)` and `V14 (disagreement)`.

2. **Arm CTL fails V4 and V14 structurally, and nothing said so.** With no stop the joint
   is not at rest: I3 samples it later than I1 (it read 0.340 rad against I1's 0.300), and
   I4's second command moves it further, so it reported `reached_goal` where I2 reported
   `stalled`. Applied literally, both rules exclude the trial *from every bracket* — and CTL
   contributes to no bracket, so nothing is lost. But an unexplained exclusion in the
   admission block reads as a rig failure. **Fix:** the exclusion is named where it happens,
   and §7.4's CTL report is printed from the **collected** trials rather than from the
   surviving set. **No rule was weakened**: V4 and V14 still exclude the trial, literally.

3. **`analyse.py` reported P1 and P3 REFUTED against a directory in which the blocks that
   would produce those brackets had never run.** A prediction that could not be tested is
   not one that was refuted. **Fix:** each bracket prediction is NOT EVALUABLE unless the
   block that would produce it is present in `raw/`. This is the same distinction `say`'s
   third state exists for, applied one level up.

4. **A shakedown's two per-block log files carried the campaign block's name.** The
   invocation borrows `--block LO-C` for its stop kind, so `run_block.sh` wrote
   `logs/LO-C_harness.log` and `logs/LO-C_load.txt` *inside this directory* — two files that
   look like a campaign block's log. **Fix:** `run_block.sh` derives a `SHAKEDOWN` log tag
   when `--shakedown` is passed. **The fix landed after this run, so the two files here
   still carry the old names**, and they are left alone rather than renamed: a harness is
   the code that produced the data, and renaming its output afterwards would make this
   directory no longer what ran.

## What the shakedown did not exercise, recorded rather than implied

- **No refinement, no INV and no CTL *block*.** The fine-grid refusal in `common.fine_grid`
  (an interval that is not an adjacent coarse pair), INV's four-stop refusal, and
  `run_campaign.sh`'s located-interval refusals are exercised by their own argument checks
  and not by this run.
- **No block-level V1 failure, no V2 disagreement, no V13 refusal and no instrument loss.**
  Every one of those paths printed `did not fire`, which is what it should print, and none
  was provoked.
- **Nothing about a grasp.** There is no part and no physics in this rig at all.
