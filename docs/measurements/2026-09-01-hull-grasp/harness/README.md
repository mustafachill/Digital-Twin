# Harness — hull vs vendor collision geometry, at the grasp

Reproduction, from the repository root on the host:

    docs/measurements/2026-09-01-hull-grasp/harness/run_campaign.sh 2 12

| File | What it does |
|---|---|
| `configure.py` | applies the one scratch L0 flip (`description.collision.select`) and regenerates. Never committed in a flipped state. |
| `run_campaign.sh` | four blocks, `VENDOR HULL VENDOR HULL`, quiescing and reverting around each |
| `run_block.sh` | one bring-up, N trials, one teardown — inside the container |
| `measure_hull_grasp.py` | the trial driver and every metric |
| `analyse.py` | the decision rules of `criteria.md` §7, applied to `raw/` |

`measure_hull_grasp.py` is derived from the friction campaign's
`../../2026-08-25-friction-grasp/harness/measure_grasp.py`. That harness is frozen
(`../../README.md`), so it is copied rather than imported or edited, and every control
metric here is deliberately the same computation as the figure it is compared against.
