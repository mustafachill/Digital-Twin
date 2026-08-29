# Harness

What produced `../raw/`. Frozen with it, per the campaign convention.

## Reproduction

From the repository root, on a machine with Docker, after `./scripts/bootstrap`
and `./scripts/build`:

```
docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh host
docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh hulls
docs/measurements/2026-08-28-second-world-cost/harness/sequence.sh
docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh world
docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh mirror
docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh shadow SHADOW_1
docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh pairgz PAIRGZ_1
./scripts/enter dev python3 /workspace/docs/measurements/2026-08-28-second-world-cost/harness/gz_crossing.py \
    --out /workspace/docs/measurements/2026-08-28-second-world-cost/raw
python3 docs/measurements/2026-08-28-second-world-cost/harness/analyse.py \
    --raw docs/measurements/2026-08-28-second-world-cost/raw
```

`CITE_SAMPLE_SECONDS` shortens the sampling window; the campaign ran at its default
of 120 s.

## What each piece is

| File | What it does |
|---|---|
| `run_campaign.sh` | one phase per invocation, so the interleaving in `criteria.md` is visible in the call order rather than buried in a loop |
| `sequence.sh` | the interleaved order exactly as executed |
| `cell_run.py` | brings one cell up through `./scripts/sim --headless`, waits for every controller to report active, samples Gazebo's own `WorldStatistics`, records the ROS and Gazebo graphs, `/proc` CPU and resident memory, and tears down |
| `make_hulls.py` | convex hull per vendor mesh, for the H arm of Q3.1 |
| `swap_meshes.py` | puts hulls into the built overlay and puts the vendor symlinks back, with a byte-identical check either way |
| `world_only.py` | the arms-free and physics-paused ablations of Q3.2 |
| `gz_crossing.py` | Q1.4 below the bridge: two servers in one container, with and without `GZ_PARTITION` |
| `shadow_side.py` | Q4's physics-free virtual side: three `robot_state_publisher` and a cross-domain relay |
| `mirror_latency.py` | Q5's latency rig: source, relay and mirror in one process on one wall clock |
| `analyse.py` | reduces `../raw/` to the figures `criteria.md` registered, and applies validity rule V2 |

## Two things this harness is not

**It is not the hull pipeline ADR-0028 specifies.** That one belongs in `tools/`, is
bound through L0, is deterministic and is unit-tested. `make_hulls.py` writes hulls
into a scratch directory so one condition can be measured and undone. Nothing here
is a proposal for how hulls should ship.

**It does not touch the vendor source tree.** `colcon --symlink-install` leaves one
symlink per mesh in the built overlay; `swap_meshes.py` replaces those symlinks and
restores them, so the only thing mutated is the install volume, which
`./scripts/build` recreates.
