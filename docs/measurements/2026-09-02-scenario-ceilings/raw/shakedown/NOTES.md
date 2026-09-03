# Shakedown — one run, and it is not data

[`../../criteria.md`](../../criteria.md) §10 permits **one** shakedown run per harness,
before the first campaign trial, to prove the rig starts, captures a console and parses a
record. This is it.

- **What ran:** `./scripts/scenario bringup`, at **FULL**, through
  `harness/run_trial.py --label SHAKEDOWN_bringup --condition FULL --scenario bringup`.
- **When:** 2026-09-03, on the machine `criteria.md` §9 names — the compose project and
  domain the run recorded (`cite-digital-twin-3319196271`, domain 43) and the image ID
  (`3a41d4e431b0`) are the ones that section states, derived rather than typed.
- **Output:** `SHAKEDOWN_bringup.json` and `SHAKEDOWN_bringup.log` beside this file.

> **IT IS EXCLUDED FROM EVERY FIGURE IN §7 AND MAY NOT BE USED TO SET OR ADJUST ANY
> THRESHOLD.** The exclusion is in code, not in this sentence: `analyse.py` lists
> `raw/*.json` at the **top level only**, so this directory cannot be swept into a
> campaign figure by a recursive glob. Every threshold in `criteria.md` is derived from
> the inherited bands, from the emitters' own structure, or from the ceilings themselves,
> and none of them needed a shakedown to exist.
>
> **No number in this directory is a result.** The `elapsed_s` values here are one run of
> one scenario on one machine with nothing registered in advance, and quoting one anywhere
> — in `ANALYSIS.md`, in an ADR, in `CLAUDE.md` — would be exactly the mistake §11 exists
> to prevent.

## What the chain did, end to end

Capture → parse → validity flags → per-rule print, all four links exercised:

- **27 `CITE_TIMING` marker lines, 27 parsed, 0 mangled** (rule G's numerator and
  denominator both non-trivial, and its 5 % discard did not fire).
- **All 15 `bringup` manifest triples present at their full expected count** — rule E
  reported `k of n` with `k == n` on every one, and the 27 is the manifest's own sum
  (3 + 3 + 1 + 1 + 1 + 6 + 1 + 1 + 4 + 1 + 1 + 1 + 1 + 1 + 1), derived from the emitters'
  loops before the run and not from it.
- **Verdict read from `scripts/scenario`'s own line** (I2), not from the exit code.
- **V1 clean at both ends**, the two `git` readings agreeing and `HEAD` unmoved.
- **V2 satisfied off the running cell** (I7): 13 hull collision references in the
  description the running `description_publisher` served, and the throttle present in the
  installed world the cell loaded.
- **Rule Z, rule Q and rule NOISY all fired on real data**, including rule Q's
  `max - q <= 0` branch, which is the one that produces an INCONCLUSIVE with no upper
  bound.

## Three defects it revealed, all fixed in the harness

`criteria.md` was **not touched**. §10: if the shakedown reveals a defect, the harness is
fixed and that file is not.

1. **I4's end-of-run reading was structurally unobtainable.** `scripts/_lib.sh` starts a
   scenario with `compose run --rm`, so the container is **removed the instant
   `./scripts/scenario` exits**. The post-exit `docker exec` therefore returned
   `No such container`, and I4's second reading and V6's end-of-run confirmation were both
   empty — while `v6_ok` still computed to `true`, because `None` was being read as
   "nothing contradicted it". **Fix:** the watcher now samples I4 every 10 s *while the run
   is live* and keeps the last successful reading with how long before the exit it was
   taken (`i4_last_live`, `i4_last_live_before_exit_s`); the failed post-exit attempt is
   still recorded beside it (`i4_post_exit_attempt`) so the record cannot be mistaken for
   one taken after the process ended; and **a loaded run with no live reading now fails
   V6** rather than passing it, because NOT ESTABLISHED is not confirmation.

2. **The recorded seed was not the seed in force.** `scripts/scenario` exports
   `CITE_PHYSICS_SEED` with a default *after* reading the host, so the host shell's value
   is null on every ordinary run — which is what the shakedown recorded, while the run
   itself used `20260824`. **Fix:** the value is read off the console the scenario prints
   it on (I3), as `CITE_PHYSICS_SEED_in_force`, and the container's own `CITE_`-prefixed
   environment is read through `docker exec env` and recorded as
   `container.cite_environment_in_force`. It is a **condition recorded per run and not a
   reproducibility claim**: `gz sim --seed` seeds `gz::math::Rand` and not the physics
   solver.

3. **`docker update --cpus 0` releases nothing and says so with exit 0.** Measured
   directly on Docker 29.7.2 on this host: after `--cpus 2`, `cpu.max` read
   `200000 100000` and `NanoCpus` `2000000000`; `--cpus 0` returned 0 and left **both
   unchanged**. The harness had been calling it and believing it. **Fix:** the release is
   attempted, **read back**, and recorded with whether it took
   (`i4_release_attempt.released`). What actually isolates one run's allocation from the
   next is that the container is destroyed by `--rm` — and that holds only while no `dev`
   service is already up, because `_lib.sh` then uses `compose exec` instead and the
   container survives. So **a FULL run whose live reading shows a quota now fails V6**: at
   FULL the unconstrained `cpu.max` is a reading to be taken, not an absence of action.

## Two things to know when reading the published output

- **`SHAKEDOWN_bringup.json` was written by the PRE-FIX rig.** It therefore has
  `i4_at_end` carrying the `No such container` error rather than the `i4_last_live` /
  `i4_post_exit_attempt` / `i4_release_attempt` fields the fixed harness writes, and its
  `environment.CITE_PHYSICS_SEED` is `null` rather than the `20260824` the run actually
  used. It is published as it was produced. **A shakedown is not re-run to make its output
  match the harness that followed it** — that would be a second shakedown, which §10 does
  not permit, and the whole value of the record is that it is what revealed the defects.
- **The three fixes were verified without a second scenario run.** The seed reader was
  run against this directory's own captured console; the container-environment read and
  the `docker update --cpus` mechanism were exercised against a plain
  `./scripts/enter dev` container holding nothing but a `sleep`, which brings no cell up,
  runs no scenario and produces no `CITE_TIMING` record. That is a unit check of two
  `docker` helpers and **not** a use of §10's one-run allowance.

## One reading worth carrying into the campaign, and it is not a threshold

The container was discovered **1.7 s** after its own `StartedAt`, at FULL. V6 discards a
loaded run whose limit lands more than **10 s** into the container's life, so the
mechanism has room — on this run, on this machine, at this condition. **It is one
observation and not a rate**, it says nothing about a loaded run, and if a loaded run
exceeds the ceiling it is discarded and reported under V6 rather than being explained by
this paragraph.
