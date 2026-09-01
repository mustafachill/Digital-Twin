# Harness

Frozen with `criteria.md` before the first trial (`docs/measurements/README.md`, rule 2).
If the tree moves under it, annotate `ANALYSIS.md` with a dated note and leave these files
alone.

| File | What it does |
|---|---|
| `configure.py` | Applies one scratch flip — topology, geometry, throttle — on the host and regenerates from the model. Never committed in a flipped state. |
| `trial.py` | Runs inside the container. Brings one cell or one pair up, samples every side concurrently over the window, tears it down, writes one JSON record. |
| `run_campaign.sh` | The block sequence: revert, configure, build, trial, sweep, revert, for every cell of the 2x2 and its solo baseline. |
| `analyse.py` | Applies `criteria.md` §7's validity rules to `raw/` and produces the tables in `ANALYSIS.md`. Written after the data was collected; the rules it applies were not. |

## Reproduction

From the repository root, on a host where `./scripts/doctor` exits 0:

```
docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/run_campaign.sh 3
```

It is resumable: a condition whose `raw/<LABEL>.json` already exists is skipped, so an
interrupted campaign continues rather than re-measuring what it has.

## Two things worth knowing before reading the code

**Every Gazebo-transport call goes through `cite_bringup.gz`, and the side is named.**
ADR-0049 decision 5 requires both. `gz.py`'s own docstring records what a positional side
lookup costs: a partition that reaches the wrong side fails silently by construction.

**`./scripts/enter` is `docker compose run --rm`.** Each trial therefore owns a fresh
container that is destroyed when the trial returns, which is what stops an orphaned
`gz sim` from holding the next trial's partition. `sweep()` checks that rather than
assuming it.
