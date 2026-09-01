# Harness

**This is not a new instrument.** It is the frozen harness of
[`2026-08-31-capacity-and-clock-deficit`](../../2026-08-31-capacity-and-clock-deficit/harness/README.md),
re-run on a different configuration of the product. That campaign's harness stays where it
is and stays callable; nothing here edits it.

Re-running a frozen instrument on a new commit is the cheap, comparable move: same
questions, same window, same arithmetic, one variable changed. Designing a second
instrument would have made every difference between the two campaigns un-attributable.

| File | What it does | Relative to the frozen harness |
|---|---|---|
| `trial.py` | Runs inside the container. Brings one cell or one pair up, samples every side concurrently over the window, tears it down, writes one JSON record. | **byte-identical** (`diff` is empty) |
| `configure.py` | Applies one scratch flip — topology, geometry, throttle — on the host and regenerates from the model. | **one change**: the geometry flip runs the other way |
| `run_condition.sh` | Runs one condition once: revert, quiesce, read the host load, configure, build, trial, sweep, revert, write the host sidecar. | **new file**, holding what `run_campaign.sh` used to inline, plus the corrected V6 reading |
| `run_campaign.sh` | The block sequence, in `criteria.md` §6's registered order. | **loop only**; the body moved to `run_condition.sh` |
| `analyse.py` | Applies `criteria.md` §7's validity rules to `raw/` and produces the tables in `ANALYSIS.md`. | **one rule moved**: V6 |

## The three adaptations, stated exactly

**1. `configure.py` — the geometry flip is reversed, and that is the whole reason this
campaign exists.** In the frozen harness `vendor_meshes` was the committed state and
`convex_hull` was the scratch flip. Here `convex_hull` is the committed state — ADR-0028
was promoted on 2026-09-01 and `description.collision.select` moved with it — so the
**shipped condition needs no flip at all** and `vendor_meshes` is the scratch flip, applied
only to produce the control. One `swap()` call changed direction; the rest of the file is
unchanged.

Two consequences, both registered in `criteria.md` §5 before the first trial rather than
reported afterwards:

- `cite_tools.cli validate --write` **exits non-zero on the vendor flip, by design**.
  `_vendor_collision_is_declared` was promoted from WARNING to ERROR by the same change, so
  declaring `vendor_meshes` is now a model error. `--write` regenerates *before* findings are
  computed, so the artifacts are produced regardless — and V5 reads the **installed**
  artifacts, never the tool's exit code.
- The generated `package.xml` moves with the selection, so the build step builds
  `cite_generated` **and** `cite_description` on every flip. The frozen harness already did
  this and it is unchanged.

**2. `run_condition.sh` — the loop body was split out so it can be invoked one condition at a
time.** The frozen campaign drove all 24 trials from one long-lived `run_campaign.sh`
invocation. This campaign is driven by an agent whose shell calls are individually
time-bounded. The body is the frozen campaign's, step for step and in the same order,
including the 60 s quiesce before the load average is read. `run_campaign.sh` still walks the
same eight conditions in `criteria.md` §6's registered order — **including that the vendor arm
runs first**, which is less convenient than running the shipped arm first and is followed
anyway, because the order was registered before the first trial.

**3. `analyse.py` — V6 reads the host's load average, and `criteria.md` §7 registered the
correction before any trial ran.** The frozen campaign's V6 called `os.getloadavg()` inside
the container, which reads the Docker Desktop Linux VM's `/proc/loadavg`; the macOS-side
contention that dominates this machine is invisible to it. Its own Deviation 1 records that,
after its data was collected — and it applied the rule literally anyway, which was right.

Here `run_condition.sh` reads the **macOS host's** 1-minute load average either side of every
trial into `raw/<LABEL>.host.json`, and that is what V6 is evaluated on. `trial.py`'s
container-side reading is **unchanged and still recorded**, and `analyse.py` computes the
exclusion set both instruments would produce and reports both. Where they disagree,
`ANALYSIS.md` publishes both readings; the registered one is the host's.

## The machine, and the containers that were stopped for it

`criteria.md` §8 names the machine. Eleven unrelated containers — the `turf-on-landing`
Supabase stack, holding about 1.16 GiB of the Docker VM's 7.653 GiB — were **stopped before
the first trial and restarted after the last**, which is what the frozen campaign did on this
same machine. Restoring them exactly:

```
docker start supabase_db_turf-on-landing supabase_vector_turf-on-landing \
  supabase_analytics_turf-on-landing supabase_kong_turf-on-landing \
  supabase_auth_turf-on-landing supabase_inbucket_turf-on-landing \
  supabase_rest_turf-on-landing supabase_realtime_turf-on-landing \
  supabase_storage_turf-on-landing supabase_pg_meta_turf-on-landing \
  supabase_studio_turf-on-landing
```

## Reproduction

From the repository root, on a host where `./scripts/doctor` exits 0:

```
docs/measurements/2026-09-01-capacity-on-shipped-main/harness/run_campaign.sh 3
```

It is resumable: a condition whose `raw/<LABEL>.json` already exists is skipped, so an
interrupted campaign continues rather than re-measuring what it has.

Then:

```
.venv/bin/python docs/measurements/2026-09-01-capacity-on-shipped-main/harness/analyse.py \
  --raw docs/measurements/2026-09-01-capacity-on-shipped-main/raw
```

## Two things worth knowing before reading the code

**Every Gazebo-transport call goes through `cite_bringup.gz`, and the side is named.**
ADR-0049 decision 5 requires both. A partition that reaches the wrong side fails silently by
construction, and an unpartitioned `gz` probe exits 0 having reached no world.

**`./scripts/enter` is `docker compose run --rm`.** Each trial therefore owns a fresh
container that is destroyed when the trial returns, which is what stops an orphaned `gz sim`
from holding the next trial's partition. `sweep()` checks that rather than assuming it.

**The checkout is a git worktree** with its own compose project, its own named build volumes
and its own `ROS_DOMAIN_ID` pair, so no other checkout on this machine shares a build tree or
a DDS domain with it. That isolation is why a stale build cannot answer for a fresh one here.
