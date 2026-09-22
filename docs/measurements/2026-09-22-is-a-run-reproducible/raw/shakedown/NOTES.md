# The one permitted shakedown — NOT DATA

[`../../criteria.md`](../../criteria.md) §6 permits **exactly one** shakedown, published
here, **excluded from every figure**, and forbidden from setting or adjusting any threshold
in that file. This is it. Nothing in it may be quoted as a result of this campaign.

- **Run:** 2026-09-22, on the machine [`../../criteria.md`](../../criteria.md) §9 names,
  at `6c66cb9`, before any campaign trial existed.
- **Command:** arm A's shape, one probe trial, with `--shakedown`. The exact invocation is
  in [`../../harness/README.md`](../../harness/README.md).
- **Excluded three ways**, none of which is the directory it sits in:
  `analyse.py` globs `raw/*.json` at the top level only; it skips any label beginning
  `SHAKEDOWN`; and it drops any row carrying `is_shakedown`, which this record does.
  Verified: `analyse.py` run against `../` after this record existed reports
  **0 campaign rows** and refuses nothing, because refusal 1 alone already hides it.

## What it proved — mechanism only

- **The rig starts and completes.** `gz sim -s -r --iterations 15000 --seed 20260824`
  exited 0 having run its registered iteration count; the probe world parsed and loaded.
- **V-physics agrees with the installed world.** The probe's `<physics>` block and the
  block read through `ros2 pkg prefix cite_generated` canonicalise identically.
- **V10's door works.** The partition the record carries is the one the generated plan
  names for `cell_b`'s plant side, taken through `cite_bringup.gz`.
- **V4's event fires.** The first snapshot arrived on
  `/world/cite_probe/dynamic_pose/info` 2.21 s after launch, with the body already falling
  — so the subscription was matched before the body did anything.
- **I2 is satisfiable on this rig.** Two samples 1.0007 s apart agreed to 0.0 m, well
  inside the registered 1e-9 m, and `final_position` agreed with the at-rest sample to
  0.0 m.
- **The body falls, tumbles, travels and settles**, which is what arm A needs it to do:
  it left (0, 0, 0.5) and came to rest with its centre 0.025 m above the plane — one
  half-cube, so flat on a face — having translated about 31 mm horizontally. **That is a
  statement about this one trial and NOT a measurement of sensitivity**; whether a 1e-6 m
  perturbation moves the outcome is arm A''s question and T3's verdict.
- **The chosen `--iterations` has room.** Rest was reached about 3.4 s after launch and
  detected about 4.4 s after it; the trial ran 17.5 s wall in total.

## What it did NOT do

- It changed no threshold and no constant. **`../../criteria.md` was not touched.**
- It found no defect, so **every file that produced this record — `common.py`,
  `trial_probe.py`, `probe.sdf.in` — is byte-identical to the committed one**, unlike the
  2026-09-04 campaign, whose shakedown forced two fixes. (`trial_cell.py` gained one
  guard after this record was written, from a code read rather than from this run. It is
  arm C's file and it took no part in this trial.)
- It says nothing about arms B, A', C or S: it is one trial of arm A's shape.
- It is **not** a trial of anything. Its numbers appear in no figure and settle no
  question.
