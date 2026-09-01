# Criteria — capacity and the clock deficit on the configuration this repository actually ships

**Written and committed before the first trial ran**, in its own commit and alone. Frozen from
that commit (`docs/measurements/README.md`, rule 1). Any interpretation that had to change
afterwards is recorded as a numbered deviation in `ANALYSIS.md`, applied to data already
collected.

This campaign **re-runs the frozen instrument of
[`2026-08-31-capacity-and-clock-deficit`](../2026-08-31-capacity-and-clock-deficit/criteria.md)
on a different configuration of the product.** Same questions, same instrument, same window,
same validity rules but one — §7 states the one and why it was corrected here rather than
afterwards. What changed is not the measurement; it is what is being measured.

## 1. Why this campaign exists

Every capacity figure this repository holds was taken with `description.collision.select`
flipped **by hand, on a branch**, before [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md)
was promoted. At the time those trials ran, the shipped selection was `vendor_meshes` and the
hull condition was a scratch flip that was reverted and never committed. As of `main`
`dd93488` the shipped selection is `convex_hull` — ADR-0028 is `Accepted`, against the clause
[ADR-0051](../../adr/0051-restate-the-hull-grasp-gate.md) restates.

**So nobody has measured the capacity of the configuration that ships**, and the most-cited
document in this repository states a figure for it that is withdrawn. `what-we-are-doing.md`
§8's Phase 2.A paragraph, and its §14 v1.11 entry, say the hull pair reaches *"about 0.95
against a required 1.0"*. Both of the things that sentence asserts are now wrong in different
ways:

- **The figure is a throttled reading.** With the generated world's `real_time_factor: 1.0` in
  force, a measured `d(sim)/d(real)` is **capped at 1.0 by construction** — read in upstream
  `gz-sim` source and recorded in [ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md),
  with ADR-0028's and ADR-0043's 2026-09-01 corrections withdrawing the conclusion drawn from
  it. 0.95 is where a capped measurement sits; it is not a capacity and could not have exceeded
  1.0 whatever the machine did.
- **The parenthetical is stale.** It calls the hull geometry *"not the shipped default"*. It is
  the shipped default.

This campaign produces the evidence a correction to those sentences would rest on. **It does
not write that correction.** `what-we-are-doing.md` is protected (CLAUDE.md §12) and changes
only by the owner's explicit decision.

## 2. What this campaign will NOT do

- **It will not set either of ADR-0049's two thresholds**, and no figure it produces may be read
  as one. That record deliberately set neither; the campaign this one extends was forbidden by
  its own §2 from setting them and set neither; this campaign inherits that and sets neither.
  Where to put a capacity margin above 1.0, and where to put an operating deficit bound, are
  *decisions* informed by a measurement.
- **It will not edit `what-we-are-doing.md`, any ADR, or `CLAUDE.md`.** Figures stay in this
  directory and are cited (P1). One index row in `docs/measurements/README.md`, in that table's
  existing style, is the only edit outside this directory.
- **It will not change production source.** The vendor control arm is reached by the same
  scratch flip §5 describes; a flipped `model/` is never committed, and `git diff` against the
  base commit for `model/`, `workspace/`, `tools/`, `scripts/` and `tests/` must be empty when
  the campaign ends.
- **It will not promote, tune, buy or widen anything.** No scenario wall-clock ceiling,
  tolerance or `real_time_factor` is changed outside the scratch flips in §5.
- **It measures speed and never correctness.** Nothing here is evidence for or against any
  grasp claim; [`2026-09-01-hull-grasp`](../2026-09-01-hull-grasp/ANALYSIS.md) is the campaign
  that addressed that and it reached an inconclusive.

The one number this campaign *does* compare against is **1.0**, and it is not this campaign's
number: it is ADR-0043's floor, explicitly not relaxed by ADR-0049 decision 1. Reporting
whether capacity is above or below it is reading an existing requirement, not setting a new
one.

## 3. Questions, registered before the first trial

| # | Question | Instrument |
|---|---|---|
| **Q1** | With the throttle **lifted**, what sustained real-time factor does each side of an idle pair reach, sampled concurrently, **on the shipped configuration** (`select: convex_hull`, unmodified)? | `rtf_window` (§4) |
| **Q2** | Does the shipped configuration clear ADR-0043's floor of 1.0? | the decision rule in §6 |
| **Q3** | What is the same figure for the **vendor** control, reached by the one permitted flip? | `rtf_window`, `G_capacity` (§4) |
| **Q4** | With the throttle **in force**, what accumulated clock deficit does the shipped configuration carry over the window, in seconds, and is it a drip or a tail? | `deficit_total_s`, `deficit_top1pct_share`, the interval quantiles (§4) |
| **Q5** | What does the **second side** cost? Solo against pair, both geometries, throttle lifted. | pairing penalty and aggregate throughput (§4) |
| **Q6** | Do the figures of [`2026-08-31-capacity-and-clock-deficit`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md) reproduce on the same machine at a later commit — and does the branch-versus-shipped distinction change anything? | per-condition medians against that campaign's, by the rule in §6 |
| **Q7** | By how much does Gazebo's own `real_time_factor` field disagree with the window instrument in each condition? | `rtf_reported_median / rtf_window` |

Q7 is carried forward unchanged because ADR-0049 decision 5 forbids that field as the
instrument. It is a check on the instrument, never a source of a figure.

## 4. The instrument, stated exactly

**Unchanged from the campaign this one extends**, deliberately: an instrument that moves at the
same time as the configuration cannot tell you which one produced the difference.

**Never Gazebo's own `real_time_factor` field** (ADR-0049 decision 5). Each side's
`/world/cell_a/stats` is streamed through `cite_bringup.gz`, carrying **that side's**
`GZ_PARTITION` (ADR-0042), with the side addressed **by name** and never by position (ADR-0044,
ADR-0047). `cite_bringup.gz` is the only door used.

From the stream of `WorldStatistics`, using the `sim_time` and `real_time` pair carried in each
message:

- `rtf_window  =  (sim_time[last] - sim_time[first]) / (real_time[last] - real_time[first])`
- `deficit_total_s  =  (real_time[last] - real_time[first]) - (sim_time[last] - sim_time[first])`
- per stats interval `i`: `d_i = dreal_i - dsim_i`, over consecutive messages. Reported as
  median, p95, p99, max, and `deficit_top1pct_share` / `deficit_top5pct_share`.

**The resolution limit is registered in advance.** World statistics arrive at about 10 Hz on
this host — measured by the extended campaign's shakedown and recorded in its harness README,
so it is carried here as a known rather than as an assumption. One interval is therefore about
100 ms, or about 100 physics steps at the world's 0.001 s step. **A single step's overrun is
below this instrument's resolution**, and `ANALYSIS.md` must say so rather than implying
step-level detail.

Derived comparisons:

- `capacity_min` = the minimum `rtf_window` across the two sides of one unthrottled paired
  trial. The pair's capacity is its slower side; a mean would let one fast side hide a short
  one.
- `G_capacity` = hull `rtf_window` / vendor `rtf_window`, unthrottled, computed **within a
  block** (§6).
- `G_throttled` = the same ratio with the throttle in force.
- pairing penalty = solo `rtf_window` / pair `rtf_window`, within a block.
- aggregate throughput = 2 x pair `rtf_window` / solo `rtf_window`, within a block.

## 5. The 2x2, and how each cell of it is produced

| Factor | Levels | How it is set |
|---|---|---|
| Collision geometry | `convex_hull` (**shipped**), `vendor_meshes` (**the control**) | `description.collision.select` on `model/assets/types/robots/xarm5.yaml` — an L0 choice |
| Throttle | in force (`1.0`, **shipped**), lifted (`0`) | `REAL_TIME_FACTOR` in `tools/cite_tools/generate/world.py`, regenerated into the world |
| Topology | `solo` (**shipped**), `pair` | `twin.sides` on `model/facility/zones.yaml` |

**The flip direction is reversed from the campaign this one extends, and that is the whole
point of running it.** There, `vendor_meshes` was the committed state and `convex_hull` the
scratch flip. Here `convex_hull` is the committed state and **`vendor_meshes` is the scratch
flip** — the one place this campaign is permitted to modify the model, and it is modified only
to produce the control against which the shipped figure is read.

Every flip is a **scratch flip**: applied to the working tree, regenerated with
`cite_tools.cli validate --write`, rebuilt, run, and reverted with `git checkout`. **No flipped
`model/` and no flipped generator constant is committed.** The campaign's commits contain this
directory and nothing else.

Two mechanical facts about the vendor flip, both known before the first trial and neither a
surprise to be reported afterwards:

1. **`validate` exits non-zero on the vendor flip, by design.** `_vendor_collision_is_declared`
   was promoted from WARNING to ERROR by the change that moved the default, so declaring
   `vendor_meshes` is now a model error. `--write` regenerates **before** findings are
   computed, so the artifacts are produced regardless, and V5 (§7) reads what was **installed**
   rather than what the tool said. The harness must not swallow this and must not treat it as a
   failed configuration.
2. **The generated `package.xml` moves with the selection.** Its dependencies are derived from
   the selected set, so the vendor flip drops the `cite_description` dependency and the hull
   state carries it. The build step therefore builds `cite_generated` **and**
   `cite_description` on every flip, as the frozen harness already does.

Eight conditions: `{PAIR, SOLO} x {HULL, VENDOR} x {THROTTLED, FREE}`.

**`SOLO_HULL_THROTTLED` is the shipped configuration exactly** — `sides: single`,
`select: convex_hull`, `real_time_factor: 1.0`, with no flip applied at all. It is the only
condition in the matrix that requires no scratch flip, and it is where ADR-0049's second
quantity, the operating clock deficit, is read for the product as it stands.

## 6. Design, windows, repeats, and the decision rules

- **Settle** 30 s after the last side announces `CITE_SIDE_READY`, discarded.
- **Window** 120 s of stats streaming, both sides concurrently. Unchanged from the extended
  campaign and from ADR-0028's implementation note, so the figures are comparable to both.
- **Cells are idle**, holding home pose after bring-up, as every prior real-time measurement in
  this repository is. **An idle margin is not a work allowance** — the second-world-cost
  campaign's rule 5, inherited unchanged.
- **Repeats: 3 blocks, 8 conditions each, 24 trials.** One block runs all eight conditions
  once. Within a block the order is fixed and is the extended campaign's order, so that the two
  campaigns' block structures line up: vendor throttled, vendor free, hull throttled, hull free
  — pair first, then solo within each.
- **Block-paired, not pooled.** Geometry cannot be interleaved against a running cell: it is a
  rebuild. Blocking is the compromise, and the ratios in §4 are computed **within a block** so
  that host drift between blocks cancels rather than landing on one condition. Pooled medians
  are reported beside them, subject to V1.

**A resource stopping rule, registered here so that stopping early is not a decision taken
after seeing data.** No new block is started once **5 hours** have elapsed from the first
trial's start. A block that has started runs to completion. If fewer than 3 blocks complete,
`ANALYSIS.md`'s verdict is **PARTIAL** and states which condition got how many repeats. **The
rule is on the clock and never on the data**: a block is never stopped, extended or repeated
because of what it showed.

### The decision rule for Q2, registered before the first trial

Read on `PAIR_HULL_FREE` — the shipped geometry, paired, throttle lifted — over the valid
side-windows surviving §7:

- **CLEARS 1.0** — the pooled median of `rtf_window` is above 1.0 **and every valid
  side-window** is above 1.0.
- **SHORT of 1.0** — the pooled median is below 1.0.
- **AMBIGUOUS** — the pooled median is above 1.0 but at least one valid side-window is not.

The same rule is stated for the vendor control and reported beside it. **None of the three
outcomes is "the requirement passes"**: ADR-0049 sets no capacity margin above 1.0, and a
figure that clears the bare floor on an idle cell on a loaded host is not a margin.

### The effect sizes that count as interesting, registered before the first trial

- **Between conditions** (any ratio in §4): `|ratio - 1| >= 0.10` is an effect this campaign
  will report as a finding. Between 0.05 and 0.10 it is reported and explicitly labelled as
  sitting inside the run-to-run spread the extended campaign measured on this machine (5.6 % at
  its widest). Below 0.05 the two conditions are reported as **not separated by this
  campaign**.
- **Additionally**, a between-condition effect is called a finding only if it holds **in the
  same direction in every completed block**. A ratio that changes sign between blocks is
  reported as unstable, whatever its median.
- **Against the extended campaign** (Q6): a per-condition pooled median differing from that
  campaign's by **less than 10 %** is reported as **reproduced**; by 10 % or more, as
  **changed**, with the two candidate explanations — the commit and the host state — named and
  **not** adjudicated, because this campaign cannot separate them.

## 7. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule. These are applied literally, including where a
rule turns out to read the wrong thing.

- **V1 — spread.** If a condition's `rtf_window` range across its repeats exceeds **20 %** of
  that condition's median, that condition's **pooled** median is refused as a headline figure.
  It is still reported, labelled refused, and only the block-paired figures are read for it.
- **V2 — concurrency.** A paired trial is valid only if the two sides' sampling windows overlap
  by at least **90 %** of the shorter window, measured on the harness's own wall clock.
- **V3 — the pair really came up.** A trial is valid only if every side announced
  `CITE_SIDE_READY` and no side exited during the window. Otherwise the trial is discarded and
  recorded as discarded, with the reason.
- **V4 — the stream did not stall.** A trial is valid only if the window yielded at least
  **100** parsed stats samples per side and the maximum inter-sample wall gap was under
  **10 s**.
- **V5 — the configuration under test is the configuration labelled.** Every trial records,
  from the **installed** artifacts rather than from the source tree, the `real_time_factor` in
  the loaded world and the collision-mesh root bound into the generated arm description. A
  trial whose recorded configuration does not match its condition label is **discarded**. This
  repository has twice published figures produced by a build that was not the build being
  described.
- **V6 — host drift. CORRECTED HERE, AND THE CORRECTION IS REGISTERED BEFORE THE FIRST
  TRIAL.** The rule is unchanged in shape: a trial whose pre-trial 1-minute load average
  differs from the campaign's median pre-trial load average by more than **50 %** is excluded
  from pooled figures and reported separately. **What changed is which machine's load it
  reads.**

  The extended campaign's V6 read `os.getloadavg()` **inside the container**, which is the
  Docker Desktop Linux VM's `/proc/loadavg` and not the host's. Its own Deviation 1 records
  that it therefore measured how far the previous trial's teardown had drained rather than how
  busy the machine was, that it excluded 4 of 24 trials on that basis, and that the unexcluded
  medians were larger in every case. It applied the rule literally anyway, which was correct;
  it also said so afterwards rather than before, which is what this campaign is asked not to
  repeat.

  **Here V6 is evaluated on the macOS host's 1-minute load average**, read on the host side
  immediately before and immediately after each trial by the driver, and stored in a sidecar
  record beside the trial's JSON. **The container VM's load average continues to be recorded by
  `trial.py`, unchanged, and is reported alongside** so that the two campaigns' V6 inputs can
  be read against each other. If the two disagree about which trials to exclude, `ANALYSIS.md`
  reports **both** exclusion sets and reads the figures under both; the **registered** reading
  is the host one.

  **V6 stays two-sided**, exactly as written: a trial on a machine *quieter* than the campaign
  median by more than 50 % is excluded too. That is what the rule says and it is applied as
  written, not as intended.

  **V6 tests stability, not quietness.** An absolute quietness threshold would disqualify every
  trial on this machine and measure nothing — §8 says why.

## 8. The machine, and the one thing wrong with it

Recorded here **before the first trial** because ADR-0049 decision 6 makes provenance a clause.

| | |
|---|---|
| Host | Apple **M4 Pro**, 12 cores, 24 GiB unified memory, macOS 26.5.2 (25F84), `Darwin 25.5.0` |
| Container runtime | Docker Desktop, Linux VM allocated **12 CPUs** and **7.653 GiB** (8,217,751,552 B) |
| Repository | branch `measure/capacity-on-shipped-main`, off `main` at **`734a26d`**; commit recorded per trial |
| Checkout | a git worktree under `.claude/worktrees/`, with its own Docker project, its own named build volumes and its own `ROS_DOMAIN_ID` pair — so no other checkout on this machine shares a build tree or a DDS domain with it |
| Free disk before the campaign | **55 GiB** on `/System/Volumes/Data` (87 % capacity) |
| Other containers | **11 stopped before the first trial** and restored afterwards — the same `turf-on-landing` Supabase stack the extended campaign stopped, holding about **1.16 GiB** of the 7.653 GiB allocation while running. The names are recorded in `harness/README.md` so the restoration is exact. |

**This host is the same machine as
[`2026-08-31-capacity-and-clock-deficit`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)**
— same CPU, same core count, same Docker allocation to the byte, same OS build. That is
provenance, recorded rather than inferred, and it is what makes Q6 a comparison of
configurations rather than of machines. It is not a claim about any *earlier* campaign's host.

**This host is not quiet, and no threshold can make it so.** With every unrelated container
stopped and nothing of this campaign running, the host's 1-minute load average sits at
**3.5 - 3.7** on 12 cores. The consumers are the user's own interactive session and are not the
campaign's to close: `fileproviderd` at **83 %** of a core continuously, `WindowServer` at
**47 - 50 %**, Chrome helpers at roughly **34 %** and **17 %**, Finder at **18 %**, and this
agent's own session at **4 - 7 %**. That is of the order of **1.5 - 2 cores busy before
anything starts**, which is the same characterisation the extended campaign registered on this
machine.

**This is registered as a threat to validity, not as an excuse, and it cuts in one direction.**
Every capacity figure this campaign produces is a **LOWER BOUND** on what this machine would
deliver quiet. It cannot manufacture headroom. A figure that clears 1.0 here would clear it
quiet; a figure that misses 1.0 here **is not thereby shown to miss it on a quiet machine**,
and `ANALYSIS.md` must state that asymmetry wherever it reports a miss.

## 9. What a result looks like

- **MEASURED** — the 2x2 is complete over the registered blocks, no validity rule refused a
  headline figure, and Q1 - Q7 are answered at the strength the data carries.
- **PARTIAL** — some cells are answered and others are not, or fewer than 3 blocks completed;
  which, and why, is stated.
- **INCONCLUSIVE** — a validity rule refused the figures the campaign was run to produce.

**None of these three is "the requirement passes."**

## 10. Named in advance as things this campaign will not answer

- **Anything about a second machine.** One host, one afternoon. A capacity is a property of a
  machine and a configuration together, and this campaign varies only the second.
- **What a pair doing work costs.** Every cell is idle, per §6.
- **Whether the vendor condition is memory-bound** — ADR-0049's hypothesis 2. Separating that
  from the host contention in §8 needs hardware performance counters, and `perf` does not work
  under Docker Desktop's kernel.
- **Anything about grasping, correctness or safety under either geometry.** This campaign
  measures speed.
- **A single physics step's overrun**, per §4's resolution limit.
- **The GUI**, which no trial runs.
- **Whether a difference from the extended campaign is the commit or the host.** §6 registers
  that this campaign reports the difference and does not adjudicate it.
- **Determinism.** Scenarios in this cell are not reproducible; see
  [`cross-cutting-testing.md`](../../architecture/cross-cutting-testing.md).
