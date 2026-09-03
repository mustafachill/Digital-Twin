# Harness — what the six scenario wall-clock ceilings bound

Twenty-eight runs, four CPU allocations, three scenarios, one instrument. The order below
is [`criteria.md`](../criteria.md) §6's registered order and it is not a convenience:
**FULL runs appear at both ends and throughout**, so that a drift in the host over the
campaign's duration shows up as scatter *within* a condition rather than as a difference
*between* conditions.

**Everything here runs on the host.** `docker update` is host-side, I5 and I6 are
host-side, and I3 — the campaign capturing its own console — has to wrap
`./scripts/scenario`, which itself re-executes into the container. Nothing in this
directory runs inside the cell.

## Before anything

```sh
./scripts/validate-model          # the L0 tree is the one the plan describes
./scripts/build                   # V11: ONCE, before the first trial. run_campaign.sh does it
./scripts/test
./scripts/lint
```

`run_campaign.sh` runs `./scripts/build` itself and records its summary line into
`raw/provenance.txt`, because V11 makes "the build happened once, before the first trial"
part of the record rather than part of the operator's memory. A rebuild during the
campaign is a numbered deviation and splits the runs before it from the runs after it.

**`build_once` enforces both halves of V11 rather than describing them.** It refuses to
build a second time once any run record exists in `raw/` or once `provenance.txt` already
carries a build block — so a *resumed* campaign, which this script advertises, does not
rebuild the workspace under itself — and it **aborts the campaign when the build fails**
instead of recording `build_exit` and carrying on against a stale install.

## The whole campaign, in order

```sh
docs/measurements/2026-09-02-scenario-ceilings/harness/run_campaign.sh
```

Twenty-eight runs, in §6's three parts — an opening block of one FULL run per scenario, an
interleaved body of the remaining seven FULL runs and all sixteen loaded ones, and a
closing block of the last two FULL runs. It quiesces 60 s and records the host's load and
its surviving `gz sim` processes before each. **A run whose record already exists is
skipped rather than re-run**, so a resumed campaign never silently tops a condition up
(V8).

## One run at a time

```sh
docs/measurements/2026-09-02-scenario-ceilings/harness/run_trial.py \
    --label FULL_bringup_1 --condition FULL --scenario bringup

docs/measurements/2026-09-02-scenario-ceilings/harness/run_trial.py \
    --label C1_pick_and_place_1 --condition C1 --scenario pick_and_place
```

`run_campaign.sh` also takes labels, which is what a resumed campaign needs:

```sh
docs/measurements/2026-09-02-scenario-ceilings/harness/run_campaign.sh \
    C2_bringup_2 FULL_continuous_line_3
```

## Reading the result

```sh
python3 docs/measurements/2026-09-02-scenario-ceilings/harness/analyse.py
```

It applies §7's rules and **prints every one of them whether or not it fires**. It writes
no verdict into any decision record, sets no band, proposes no ceiling and chooses nothing
(§0). `ANALYSIS.md` is written from that print, later, by someone else.

## The shakedown, and it is not data

§10 permits **one** shakedown run per harness, to prove it starts, captures a console and
parses a record. Its output goes under `raw/shakedown/`, is excluded from every figure in
§7 — `analyse.py` lists `raw/*.json` at the top level only, so the exclusion is in code
rather than in a sentence somebody has to remember — and **may not be used to set or
adjust any threshold**. If it reveals a defect, the harness is fixed and `criteria.md` is
not touched.

It has been shaken down and the output is published, with what it found, in
[`../raw/shakedown/NOTES.md`](../raw/shakedown/NOTES.md). Read that before the first
campaign trial.

```sh
docs/measurements/2026-09-02-scenario-ceilings/harness/run_trial.py \
    --label SHAKEDOWN_bringup --condition FULL --scenario bringup \
    --out docs/measurements/2026-09-02-scenario-ceilings/raw/shakedown
```

## The files

| File | What it does |
|---|---|
| `common.py` | the shared half: the `CITE_TIMING` regex and the mangled-record count (I1, rule G), the verdict reader (I2), the two `git` snapshots V1 conjoins (I6), the host load (I5), the container lookup and `cpu.max` / `NanoCpus` readings (I4), the running cell's description and world (I7, V2), the survivor check (V5), and rule Q's per-site poll quantum |
| `expected.py` | I8's manifest — the (scenario, what-pattern, `ceiling_s`, expected-count) quadruples rule E reports `k of n` against, derived from the emitters' own loops, from `ARMS`, from `WORKPIECES` and from the generated topology |
| `run_trial.py` | one run: the survivor check, both `git` snapshots, the console capture, the `docker update --cpus` that holds the allocation **for the whole run including bring-up**, I4 and I7 read off the running cell, and the record every validity flag travels on |
| `run_campaign.sh` | §6's twenty-eight runs in the registered order, with the quiesce, the survivor reading, `./scripts/build` recorded once for V11, and the isolation values derived through `scripts/_lib.sh` |
| `analyse.py` | §7's decision rules — Z, A, X, X2, G, E, P, Q, K, D3, NOISY, N, F, B1 — plus §10's run-admission rules, the Q-D instrument table and PR1–PR7, each printed either way. Rules Z, A, X, K and §2.3's leg filter are *applied* in `classify`, and every margin carries its own discard counts, rule E's `k of n` and V7's with-and-without partition beside it |

## Where each file came from

Every file names its source and the commit it was copied at, in its own header. This
campaign's practice is copy-with-attribution; `../README.md` does not require the header,
and it is here so that a reader of this directory can tell a copied file from an original
without diffing two directories.

- **`run_trial.py`** — the **frozen** 2026-08-29 harness at commit `4e4313b`:
  [`run_trial.sh`](../../2026-08-29-real-time-factor-conditions/harness/README.md) for the
  "record the host state, run, clean up, record again" shape and the survivor check, and
  `cpu_limit_trial.sh` for the `docker update --cpus` mechanism and the `docker ps
  --filter` that finds the container.
- **`common.py`** — the **frozen**
  [2026-09-02 option-F harness](../../2026-09-02-option-f-regions/harness/README.md)'s
  `common.py` at commit `ac11d84`, for the "provenance travels on every record" shape, the
  `_git` helper, `host_facts` and the writer; and its `run_campaign.sh` at `62051df` for
  the `bash -c` isolation read.
- **`run_campaign.sh`** — the same directory's `run_campaign.sh` at `62051df`, for the
  `collected()` skip, the quiesce, the abort banner and `record_environment`.
- **`analyse.py`** — the same directory's `analyse.py` at `e559264`, for the "one function
  per registered threshold, and the rule prints even when it does not fire" shape and the
  `DEVIATIONS` tuple at module top.
- **`expected.py`** — original. No earlier campaign had a per-milestone record to count.

**No campaign imports from another, and neither frozen directory is edited.** The
2026-08-29 README's own warning is honoured rather than patched: all three of its CPU
scripts hard-code that checkout's compose project name, so `common.isolation()` derives
the name from `cite_project_name` in `scripts/_lib.sh` instead — read under `bash` by
absolute path, because `_lib.sh` computes `REPO_ROOT` from `${BASH_SOURCE[0]}` and any
other shell derives a wrong value that looks exactly as plausible as the right one.

## Nothing here edits the tree

`criteria.md` §0 forbids editing `model/`, `workspace/src/`, `tools/`, `tests/` and
`scripts/` — the five paths V1 watches — and this harness reads all five and writes only
under this campaign's own `raw/`. **Touching one of them does not contaminate the data; it
destroys it**, because V1 discards every block taken while a watched path differs from
`c38a42c`. The flag is computed at both ends of every run and travels on every record, so
a concurrent writer flips it rather than going unnoticed (V10).

## Twelve things this rig cannot do, recorded here rather than discovered later

1. **It cannot see the upper tail of any interval.** A wait that times out emits no
   record, by design — a record for a wait that timed out would measure the ceiling rather
   than the milestone. So every margin here is computed over the completing half of the
   distribution, and **the censoring biases every margin UP, toward TOO LOOSE**. §8 states
   it; rule F is the only thing keeping a run in which the ceiling demonstrably fired from
   being banded at all. **No change to this harness can fix it**: fixing it means emitting
   on the timeout path, which is an edit to `tests/`.

2. **It cannot instrument the follower-settle loop in
   `bringup.test_the_gripper_linkage_is_actually_coupled`.** That interval carries
   `DELIVERY_CEILING_S` and emits nothing, deliberately. Instrumenting it would edit
   `tests/`, which §0 forbids and V1 discards. So this campaign's `DELIVERY_CEILING_S`
   margin is a statement about that ceiling's **five instrumented waits** and not about
   its sixth, and `ANALYSIS.md` must say so rather than rounding up.

3. **It cannot tell a slow wait from a stepped clock.** `elapsed_s` is `time.monotonic()`
   and the timeout is enforced on the node clock, which is the steppable system clock.
   Rule K reports a record above its own ceiling as a datum about the two clocks and
   excludes it; **the harness cannot say which of the two moved**, and does not guess.

4. **It cannot separate a mangled record from a lost one.** Rule G counts lines that carry
   the marker and fail to parse. A record that never reached the console at all — because
   the emitting thread's write was lost rather than interleaved — leaves no marker line
   and is invisible to rule G; it shows up only as an absent expected key under rule E,
   and rule E cannot tell that from a wait that was never reached.

5. **It cannot attribute anything to either of #30's two levers.** Measuring a
   vendor-mesh or throttle-lifted control would require editing `model/` or the generated
   world. The campaign measures the shipped configuration and **attributes nothing** to
   the throttle or to the hulls (§8).

6. **A CPU quota is not a smaller machine.** C4, C2 and C1 set a CFS quota on the same
   sixteen cores. It is the right variable for Q-B — contention takes CPU time away in the
   same currency — and no margin here may be described as the margin on a four-, two- or
   one-core machine. Inherited verbatim from the 2026-08-29 campaign rather than
   rediscovered.

7. **It cannot bring a pair up, and it does not try.** `./scripts/sim --pair` is not used,
   the shipped model declares `sides: single`, and pairing it would edit `model/`. Every
   run here is the plant.

8. **It cannot recover a run whose console it did not capture.** Rule P: not a short
   table, no data. `scripts/scenario` passes `--junit-xml` and nothing else, and
   `launch_testing`'s junit writer emits no `system-out`, so there is nothing to
   reconstruct from. `analyse.py` refuses a run whose `.log` is missing from `raw/` even
   when the run document beside it looks complete.

9. **It reports `continuous_line`'s `L4 to command every belt to a non-zero setpoint
   (ADR-0032)` wait in the WARM half of `BRING_UP_CEILING_S`.** `_cell_key` splits that
   ceiling into exactly two halves — the cold `what` §7.2 names, and everything else —
   and §7.2 names only the *transform* waits as the warm ones. This wait is neither: it
   runs after the coordinator is up but it is not a cached transform lookup. It is put in
   the warm bucket because the split is binary, and **it cannot affect the cold headline
   verdict**, which is the one §7.2 makes the ceiling's verdict. The warm line for that
   scenario is therefore a pool of two different kinds of wait, and `ANALYSIS.md` must say
   so rather than describing it as the transform distribution.

10. **Rule Q's `q` for a cell is the MAXIMUM quantum over the records in it, not the
    quantum of the site that produced the maximum.** `margins()` cannot key `q` to the
    producing record without letting a single site's quantum stand for a pooled cell, so
    it takes the largest. No cell in this design mixes quantum classes — §7.1's table
    assigns 1.0 s to four `bringup` waits that are all dropped by rule A or sit alone in
    their cell, and every other contributing site is at the 0.5 s default except
    `pick_and_place`'s two — so today the maximum *is* the site's. Where it would not be,
    the direction is conservative: a larger `q` widens the gap between the two readings and
    produces **more** INCONCLUSIVE cells, never fewer. The `_QUANTUM_RULES` table in
    `common.py` matches §7.1's table row for row.

11. **It loses two `CITE_TIMING` records as one mangle when they land on the same line.**
    I1's regex is `CITE_TIMING (\{.*\})` and `.*` is greedy, so two records interleaved
    onto one line match once, from the first `{` to the last `}`, and fail `json.loads` as
    a single mangled entry. **The regex is exactly what I1 registers and is not changed
    here** — it is anchored on the payload rather than on a fixed slice for the reason
    threat 6 gives, and changing a registered instrument after the fact is what §9's freeze
    exists to prevent. The consequence to carry: rule G's 5 % denominator is `marker_lines`,
    which is **line-based**, so an interleaving of this shape undercounts by two — one
    record lost silently, and the pair counted as one mangled line rather than two.

12. **The 60 s quiesce runs before the FIRST trial too, where there is nothing to
    quiesce from.** §6 and this file describe it as a quiesce *between a teardown and the
    next bring-up*, and before the opening run there has been no teardown — so on that
    wording the first one is 60 s spent on nothing. **It is kept deliberately.**
    `build_once` runs `./scripts/build` immediately before the loop, and the run that
    follows it is `FULL_bringup_1` — one of the twelve FULL runs whose scatter the design
    reads as host drift. Removing the first quiesce would buy 60 s of machine time and
    pay for it by measuring the opening FULL run on a host still finishing a build, which
    is a worse trade than the one it looks like. The survivor reading and the load line
    inside `quiesce` are wanted before the first trial in any case, and V5 spends them.

Two more that are properties of the *criteria* rather than of the rig, and are listed
because a reader of this directory will meet them here first:

- **`analyse.py` re-implements the `continuous_line` ladder derivation on the host**,
  because `tests/scenarios/continuous_line.py` imports `launch_testing` and `rclpy`.
  That is **deviation 1**, printed on every run, and the derivation is cross-checked
  against the milestone descriptions the records themselves carry.
- **Rule F is applied literally**, so `LEG_CEILING_S` is reported FIRED when it timed out
  on one of the two waits §2.3 excludes from its margin. That is **deviation 2**. The
  print names which wait fired; the label is not withheld on the strength of that reading.
- **I4's second reading is the last live sample, not a reading taken "at the end of the
  run"** as I4 registers it. `scripts/_lib.sh` starts a scenario with `compose run --rm`,
  so the container is destroyed the instant `./scripts/scenario` exits and the registered
  form is structurally unobtainable. That is **deviation 3**, printed on every run. V6's
  end-of-run clause is evaluated against the substitute, the failed post-exit attempt is
  kept beside it, and a run for which no live reading survives is NOT ESTABLISHED and is
  discarded rather than passed.

**Two things the analyser reads that are worth knowing before reading its output.** The
workpiece count in force comes from `run["container"]["cite_environment_in_force"]` — the
environment of the process that actually ran — and falls back to the host shell's copy
only when that reading failed; the two agree in every configuration this campaign reaches,
because `_lib.sh` forwards every `CITE_`-prefixed host variable into the container. And
rule F has **two** instruments, not one: `_spin_until`'s own timeout assertion, and the six
caller assertions that are the only surface an expired `_await_future` has, because that
helper asserts nothing deliberately. Without the second, `bringup.TRAJECTORY_CEILING_S` and
`bringup.SKILL_CEILING_S` — the two ceilings bounded *only* by `_await_future` — could be
banded off the waits that completed in a run where one of them demonstrably expired.
