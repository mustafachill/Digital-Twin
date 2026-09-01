# Criteria — capacity and the clock deficit, both geometries, both throttle states

**Written and committed before the first trial ran.** Frozen from that commit
(`docs/measurements/README.md`, rule 1). Any interpretation that had to change afterwards is
recorded as a numbered deviation in `ANALYSIS.md`, applied to data already collected.

The campaign [ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md) asks for in
item 1 of *What we will have to revisit*: both collision geometries by both throttle states, one
named machine, both sides of a pair sampled concurrently.

## 1. Why this campaign exists

[ADR-0043](../../adr/0043-hold-both-sides-to-the-wall-clock.md) half 2 required both sides of a
pair to sustain a measured real-time factor of at least 1.0 concurrently. Every figure ever taken
against it was taken **with half 1's throttle in force**, and ADR-0049 established from upstream
`gz-sim` source that under that throttle `d(sim)/d(real)` is capped at the declared factor by
construction and never banks an overrun back. An adequate machine and a vastly over-provisioned
one therefore both measure just under 1.0.

**So this project holds no capacity number for any host, and does not know whether the machine is
short or the instrument was.** ADR-0049 split the requirement into capacity (throttle lifted) and
the accumulated clock deficit in seconds (throttle in force) and **set neither threshold**.

## 2. What this campaign will NOT do

**It will not set either of ADR-0049's two thresholds, and no figure below may be read as one.**
Where to put a capacity margin above 1.0 and where to put an operating deficit bound are
*decisions* informed by a measurement, not findings of one; ADR-0049 decision 2 reserves them,
and the record's author sets them afterwards. This campaign produces numbers and says what they
support.

The one number this campaign *does* compare against is **1.0**, and it is not this campaign's
number: it is ADR-0043's floor, explicitly not relaxed by ADR-0049 decision 1. Reporting whether
capacity is above or below 1.0 is reading an existing requirement, not setting a new one.

Also out of scope, deliberately: nothing is bought, tuned, promoted or widened. No scenario
wall-clock ceiling, tolerance or `real_time_factor` is changed outside the scratch flips in §5.
The shipped `model/` stays `sides: single` and `select: vendor_meshes`.

## 3. Questions, registered before the first trial

| # | Question | Instrument |
|---|---|---|
| **Q1** | With the throttle **lifted**, what sustained real-time factor does each side of an idle pair reach, sampled concurrently, under each collision geometry? | `rtf_window` (§4) |
| **Q2** | With the throttle **in force**, what accumulated clock deficit does each side carry over the window, in seconds? | `deficit_total_s` (§4) |
| **Q3** | Is the deficit a steady drip or a small number of large overruns? | `deficit_top1pct_share`, `deficit_top5pct_share`, the per-interval quantiles (§4) |
| **Q4** | Is this host short of the 1.0 capacity floor, and by what factor? | `1.0 / capacity_min` (§4) |
| **Q5** | Does the hull geometry change capacity by the same factor it changes the throttled rate? | `G_capacity` against `G_throttled` (§4) |
| **Q6** | What is a **solo** cell's capacity, as the baseline the pair is measured against? | the same instruments, `sides: single` |
| **Q7** | By how much does Gazebo's own `real_time_factor` field disagree with the window instrument in each condition? | `rtf_reported_median / rtf_window` |

Q7 is recorded because ADR-0049 decision 5 forbids that field as the instrument on the strength
of one prior campaign's measurement. It is a check on the instrument, never a source of a figure.

## 4. The instrument, stated exactly

**Never Gazebo's own `real_time_factor` field** (ADR-0049 decision 5). Each side's
`/world/cell_a/stats` is streamed through `cite_bringup.gz`, carrying **that side's**
`GZ_PARTITION` (ADR-0042), with the side addressed **by name** and never by position (ADR-0044,
ADR-0047). `cite_bringup.gz` is the only door used.

From the stream of `WorldStatistics`, using the `sim_time` and `real_time` pair carried in each
message:

- `rtf_window  =  (sim_time[last] - sim_time[first]) / (real_time[last] - real_time[first])`
- `deficit_total_s  =  (real_time[last] - real_time[first]) - (sim_time[last] - sim_time[first])`
- per stats interval `i`: `d_i = dreal_i - dsim_i`, over consecutive messages. Reported as
  median, p95, p99, max, and `deficit_top1pct_share` / `deficit_top5pct_share` — the fraction of
  `deficit_total_s` contributed by the largest 1 % and 5 % of intervals.

**The resolution limit is registered in advance.** Gazebo publishes world statistics at about
5 Hz, so one interval covers roughly 200 physics steps at the world's 0.001 s step. A single
step's overrun is therefore **below this instrument's resolution**, and `d_i` measures the
aggregate overrun of a ~200 ms interval. Q3 is answerable at that granularity and no finer, and
`ANALYSIS.md` must say so rather than implying step-level detail.

Derived comparisons:

- `capacity_min` = the minimum `rtf_window` across the two sides of one unthrottled paired trial.
  The pair's capacity is its slower side; a mean would let one fast side hide a short one.
- `G_capacity` = hull `rtf_window` / vendor `rtf_window`, unthrottled, computed **within a
  block** (§6).
- `G_throttled` = the same ratio with the throttle in force.

## 5. The 2x2, and how each cell of it is produced

| Factor | Levels | How it is set |
|---|---|---|
| Collision geometry | `vendor_meshes`, `convex_hull` | `description.collision.select` on `model/assets/types/robots/xarm5.yaml` — an L0 choice |
| Throttle | in force (`1.0`), lifted (`0`) | `REAL_TIME_FACTOR` in `tools/cite_tools/generate/world.py`, regenerated into the world |
| Topology | `pair`, `solo` | `twin.sides` on `model/facility/zones.yaml` |

Every flip is a **scratch flip**: applied to the working tree, regenerated with
`cite_tools.cli validate --write`, rebuilt, run, and reverted with `git checkout`. **No flipped
`model/` and no flipped generator constant is committed.** The campaign's commits contain this
directory and nothing else.

Eight conditions: `{PAIR, SOLO} x {VENDOR, HULL} x {THROTTLED, FREE}`.

## 6. Design, windows and repeats

- **Settle** 30 s after the last side announces `CITE_SIDE_READY`, discarded.
- **Window** 120 s of stats streaming, both sides concurrently. 120 s matches the windows in
  ADR-0028's implementation note so the figures are comparable.
- **Cells are idle**, holding home pose after bring-up, as every prior real-time measurement in
  this repository was. **An idle margin is not a work allowance** — that is the second-world-cost
  campaign's rule 5 and it applies to every figure here.
- **Repeats: 3 blocks.** One block runs all eight conditions once. Within a block the order is
  fixed: vendor throttled, vendor free, hull throttled, hull free — pair first, then solo.
- **Block-paired, not pooled.** `docs/measurements/README.md` says interleave rather than block,
  because the offset campaign found a two-state process. Geometry cannot be interleaved against a
  running cell here: it is a rebuild. Blocking is the compromise, and the ratios in §4 are
  therefore computed **within a block** so that host drift between blocks cancels rather than
  landing on one condition. Pooled medians are reported beside them, subject to V1.

## 7. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule. These are applied literally.

- **V1 — spread.** If a condition's `rtf_window` range across its repeats exceeds **20 %** of that
  condition's median, that condition's **pooled** median is refused as a headline figure. It is
  still reported, labelled refused, and only the block-paired figures are read for it.
- **V2 — concurrency.** A paired trial is valid only if the two sides' sampling windows overlap by
  at least **90 %** of the shorter window, measured on the harness's own wall clock. ADR-0043's
  finding is about two sides *in the same window*; two sequential samples are not that.
- **V3 — the pair really came up.** A trial is valid only if every side announced
  `CITE_SIDE_READY` and no side exited during the window. Otherwise the trial is discarded and
  recorded as discarded, with the reason.
- **V4 — the stream did not stall.** A trial is valid only if the window yielded at least **100**
  parsed stats samples per side and the maximum inter-sample wall gap was under **10 s**. Set
  loose deliberately: this rule exists to catch a dead stream, not to encode an expectation about
  a publish rate this campaign has not measured.
- **V5 — the configuration under test is the configuration labelled.** Every trial records, from
  the **installed** artifacts rather than from the source tree, the `real_time_factor` in the
  loaded world and the collision-mesh root bound into the generated arm description. A trial whose
  recorded configuration does not match its condition label is **discarded**. This repository has
  twice published figures produced by a build that was not the build being described; this rule is
  that history made mechanical.
- **V6 — host drift.** The host's 1-minute load average is recorded before and after every trial.
  A trial whose pre-trial load average differs from the campaign's median pre-trial load average
  by more than **50 %** is excluded from pooled figures and reported separately.

**V6 needs its condition stated rather than a threshold alone, and §8 states it: this host is not
quiet.** V6 tests stability, not quietness, because an absolute quietness threshold would
disqualify every trial and measure nothing.

## 8. The machine, and the one thing wrong with it

Recorded here before the first trial because ADR-0049 decision 6 makes provenance a clause, and
because no document in this repository names a machine today.

| | |
|---|---|
| Host | Apple **M4 Pro**, 12 cores, 24 GiB unified memory, macOS 26.5.2 (25F84) |
| Container runtime | Docker Desktop, Linux VM allocated **12 CPUs** and **7.653 GiB** (8,217,751,552 B) |
| Repository | branch `measure/capacity-and-clock-deficit`, commit recorded per trial |
| Free disk before the campaign | **15 GiB** on `/System/Volumes/Data` (97 % capacity) |
| Other containers | **all stopped** before the first trial; 11 were running (a Supabase stack holding 1.62 GiB of the 7.653 GiB allocation) and are restored afterwards |

**This host is not quiet, and no threshold can make it so.** With every container stopped and
nothing of this campaign running, the host's 1-minute load average sits at **3.7 - 4.1** on 12
cores. The consumers are the user's own interactive session and are not the campaign's to close:
`fileproviderd` at 74 - 85 % of a core continuously, `WindowServer` at 29 - 40 %, and Chrome
helpers at roughly 30 %, 18 % and 12 %. That is of the order of **1.5 - 2 cores busy before
anything starts**.

**This is registered as a threat to validity, not as an excuse, and it cuts in one direction.**
Every capacity figure this campaign produces is a **lower bound** on what this machine would
deliver quiet. It is also the single most relevant fact to ADR-0049's hypothesis 2 — that the
vendor condition is bound by memory bandwidth or last-level cache rather than by per-core
throughput — because a browser and a file-sync daemon are memory-traffic generators, not
core-count consumers. **This campaign cannot separate that hypothesis from host contention**, and
§10 records it as unmeasured rather than guessing.

## 9. What a result looks like

The verdict line is one of:

- **MEASURED** — the 2x2 is complete, no validity rule refused a headline figure, and Q1 - Q7 are
  answered at the strength the data carries.
- **PARTIAL** — some cells of the 2x2 are answered and others are not; which, and why, is stated.
- **INCONCLUSIVE** — a validity rule refused the figures the campaign was run to produce.

**None of these three is "the requirement passes".** Nothing here can show a pass, because
ADR-0049 sets no threshold and this campaign may not set one either.

## 10. Named in advance as things this campaign will not answer

- **Whether this host is the host of any earlier figure.** ADR-0049's hypothesis 3 — that the
  "two hosts" are one machine — is settled by provenance, not by measurement, and no earlier
  campaign names its machine. This campaign names its own and can do nothing about theirs.
- **Whether the vendor condition is memory-bound.** Distinguishing that from the host contention
  in §8 needs hardware performance counters, which are not available under Docker Desktop's
  kernel.
- **What a pair doing work costs.** Every cell is idle, per §6.
- **A single physics step's overrun**, per §4's resolution limit.
- **Anything about the GUI**, which no trial runs.
