# Capacity and the clock deficit — both geometries, both throttle states

**Verdict: MEASURED.** The 2x2 is complete, no validity rule refused a headline figure, and
Q1 - Q7 of [`criteria.md`](criteria.md) are answered. 24 trials, all collected, on one named
machine, both sides of every pair sampled in the same window.

**This is not a statement that any requirement passes.** [ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md)
sets neither of its two thresholds and `criteria.md` §2 forbids this campaign from setting
them. §8 below says what the data supports for each; it names no number as a threshold.

## 1. The machine

Named because ADR-0049 decision 6 makes provenance a clause, and because no document in this
repository named a machine before this one.

| | |
|---|---|
| Host | Apple **M4 Pro**, 12 cores, 24 GiB unified memory, macOS 26.5.2 (25F84) |
| Container | Docker Desktop Linux VM, **12 CPUs**, **7.653 GiB** (8,217,751,552 B), overlayfs |
| Cell | `cell_a`, three xArm5 arms, idle at home pose; step size 0.001 s; headless |
| Branch | `measure/capacity-and-clock-deficit`, criteria frozen at `fca1391` before the first trial |
| Other containers | 11 stopped before the first trial (a Supabase stack holding 1.62 GiB), restored after |
| Free disk | 15 GiB throughout; no trial was disk-constrained |

**The host was not quiet and could not be made so.** `criteria.md` §8 recorded the measured
contention before the first trial: `fileproviderd` at 74 - 85 % of a core, `WindowServer` at
29 - 40 %, Chrome helpers at roughly 30 %, 18 % and 12 % — of the order of 1.5 - 2 cores busy
on a 12-core machine with nothing of this campaign running. **Every capacity figure below is
therefore a lower bound on what this machine would deliver quiet**, which is the direction
that matters: it cannot manufacture the headroom reported in §4.

**This host is very probably the "campaign host" of
[`2026-08-28-second-world-cost`](../2026-08-28-second-world-cost/ANALYSIS.md).** Its Docker
allocation is 7.653 GiB, which is the figure ADR-0043 quotes for that campaign's host to the
same three decimals, and the solo figures in §3 reproduce that campaign's within a few per
cent. **This is provenance evidence, not proof** — that campaign named no machine, which is
the whole of ADR-0049's hypothesis 3 — but it is the first time any figure in this repository
can be put beside another with a machine attached to it.

## 2. Design as run

Eight conditions — `{PAIR, SOLO} x {VENDOR, HULL} x {THROTTLED, FREE}` — each run once per
block, three blocks, in the fixed order `criteria.md` §6 registered. Every trial: settle 30 s
after the last `CITE_SIDE_READY`, then a **120 s** window with every side sampled concurrently.
Bring-up took 36 - 51 s for a pair and 24 - 36 s for a solo cell.

Geometry is `description.collision.select` on the xArm5 type; the throttle is
`REAL_TIME_FACTOR` in the world generator; topology is `twin.sides`. All three were scratch
flips, regenerated through `cite_tools.cli validate --write`, reverted after every trial.
**Nothing flipped was committed**: the shipped zone is still `single` and `vendor_meshes`, and
no ceiling, tolerance or `real_time_factor` was changed outside those flips.

**The instrument is `Delta sim_time / Delta real_time`** from each side's
`/world/cell_a/stats`, reached only through `cite_bringup.gz` carrying that side's
`GZ_PARTITION`, with the side addressed by name. Gazebo's own `real_time_factor` field was
recorded and never used as a figure — see Q7 in §7.

## 3. The 2x2

Median of `rtf_window` over the valid side-windows of each condition, with the range across
them. **Repeats: 3 blocks; a paired condition therefore has 6 side-windows and a solo
condition 3.** `n` below is side-windows surviving §7's rules.

### Capacity — throttle lifted (`real_time_factor 0`). This is ADR-0049's first quantity.

| | **Pair** (both sides, same window) | **Solo** |
|---|---|---|
| **Vendor meshes** | **0.898** [0.865 – 0.913], n=6 | **1.091** [1.091], n=1 |
| **Convex hulls** | **1.194** [1.182 – 1.219], n=6 | **1.655** [1.625 – 1.685], n=2 |

### Throttled (`real_time_factor 1.0`) — the state every previous figure was taken in

| | **Pair** | **Solo** |
|---|---|---|
| **Vendor meshes** | **0.882** [0.858 – 0.907], n=4 | **0.997** [0.997 – 0.998], n=3 |
| **Convex hulls** | **0.994** [0.976 – 0.997], n=6 | **0.988** [0.969 – 0.997], n=3 |

**V1 refused nothing.** The widest spread in any condition is 5.6 %, against the 20 % refusal
threshold registered before the first trial.

**Read the two tables against each other, because that is the campaign's point.** Throttled,
the two geometries look 0.88 against 0.99 — a difference of an eighth, with the hull row
sitting where a capped measurement sits. Unthrottled, they are 0.90 against 1.19. **The
throttled table compresses everything above 1.0 onto 1.0 and tells you almost nothing about
the machine**, which is exactly what ADR-0049 derived from upstream source and what no figure
in this repository had yet demonstrated.

## 4. Is this host short, and by how much

**The direct answer, and it is different for the two geometries.**

| Condition | Capacity of the pair (slower side) | Against the 1.0 floor |
|---|---|---|
| **Vendor meshes — the shipped default** | **0.898** | **short by a factor of 1.11** |
| **Convex hulls** | **1.194** | **clears it, by a factor of 1.19** |

The 1.0 is not this campaign's number. It is ADR-0043's floor, which ADR-0049 decision 1
explicitly does not relax; reporting a measurement against it is reading an existing
requirement, not setting a new one.

**So the machine is genuinely short in the shipped configuration, and the shortfall is real
rather than an artefact of the requirement's wording.** ADR-0043's 2026-08-31 correction says
this in as many words and could not evidence it, because every figure it had was throttled.
It is now evidenced: with the throttle lifted the vendor pair still cannot reach 1.0, and it
misses by about the same eighth it missed by with the throttle on.

**And the same machine clears the floor with hulls, with margin.** ADR-0028's implementation
note concluded *"hulls move it materially and do not reach 1.0"*, and that conclusion was
drawn from a **throttled** measurement whose figures cluster at 0.949. Read as capacity, the
same lever on the same machine reaches **1.194**. **This is the instrument error ADR-0049
identified, caught changing an ADR's conclusion.** It does not promote ADR-0028 and nothing
here may be read as promoting it: that record's clause 2 is the friction-grasp campaign re-run
under hull geometry, this campaign measured cost and never correctness, and §9 keeps that
where it belongs.

## 5. The deficit, and its distribution

ADR-0049's second quantity: wall elapsed minus sim elapsed over the window, **in seconds**,
with the throttle in force, so that it is directly comparable to the p99 mirroring latency the
original argument is about. Per 120 s window, pooled over each condition's side-windows.

| Condition | Deficit per 120 s window | Rate | Intervals that fell behind | p50 | p99 | max | Top 1 % of intervals carries |
|---|---|---|---|---|---|---|---|
| **Pair, vendor** | **11.69 s** [11.12 – 17.05] | 0.0975 s/s | **7154 / 7154 = 100 %** | 9.59 ms | 38.3 ms | 94.1 ms | **4.9 %** |
| **Pair, hulls** | **0.68 s** [0.40 – 2.90] | 0.0057 s/s | 4824 / 7156 = 67 % | 0.06 ms | 17.5 ms | 65.5 ms | **26.5 %** |
| **Solo, vendor** | **0.35 s** [0.19 – 0.36] | 0.0029 s/s | 1928 / 3576 = 54 % | 0.00 ms | 6.9 ms | 38.2 ms | **49.3 %** |
| **Solo, hulls** | **1.42 s** [0.36 – 3.70] | 0.0119 s/s | 2624 / 3576 = 73 % | 0.39 ms | 11.4 ms | 51.7 ms | **9.2 %** |

An interval is one gap between consecutive world-statistics messages, about **100 ms**. A
single 1 ms physics step's overrun is below this resolution and `criteria.md` §4 registered
that limit in advance.

### The answer to "steady drip or rare large overruns" is: **both, and which one depends on whether the machine has headroom**

This is the finding ADR-0049 said nobody had looked at, and it does not have one answer.

- **Where the machine is short — the vendor pair — the deficit is a steady drip.** Every one
  of 7,154 intervals fell behind; not one kept up. The median interval loses 9.6 ms out of
  ~100 ms, and the largest 1 % of intervals carries only **4.9 %** of the total, against the
  1 % a perfectly uniform loss would carry. There is no tail worth speaking of: the deficit is
  a *rate*, and the throttle is irrelevant to it because the cell never reaches the ceiling.
- **Where the machine has headroom and the throttle actually binds — the solo vendor cell —
  the deficit is exactly what ADR-0049 predicted: rare discrete overruns.** Only 54 % of
  intervals fall behind at all, the median interval loses nothing measurable, and the largest
  **1 % of intervals carries 49.3 % of the whole deficit** — the top 5 % carries 89.6 %.
- The hull conditions sit between the two, which is what a cell with modest headroom should do.

**The consequence for a mirroring path is that the two regimes need different kinds of bound,
and a single mean would hide both.** A rate bound describes the short machine and says nothing
about the tail; a tail bound describes the headroom machine and says nothing about the drift.

### Against the latency the argument is about

ADR-0043's arithmetic, re-run on these rates against its measured p99 one-way mirroring
latency of 3.131 ms (cite that record for the latency; it is not re-measured here):

| Condition | Deficit overtakes the p99 latency after |
|---|---|
| Pair, vendor | **32 ms** of wall time |
| Pair, hulls | **554 ms** |
| Solo, vendor | **1,074 ms** |

ADR-0043 computed 23 ms from a throttled figure; 32 ms is the same conclusion from a measured
rate. **Hulls buy a factor of about 17 in that time and do not bound it** — below 1.0 the
deficit still accumulates without bound, which is that record's argument and is untouched.

**And a bound on the rate does not bound the worst event.** The hull pair's largest single
interval overrun is **65.5 ms**, which is 21 times the p99 mirroring latency, in one event,
on a cell whose average deficit is 0.0057 s/s. A mirroring path sized on the average would not
see it coming.

## 6. The cross-host discrepancy ADR-0049 flagged: it is the throttle, and it is one machine

ADR-0049 records that two hosts agree to about 2 % on the vendor pair and differ by about
**1.23x** on the hull pair, that no single per-core-throughput scalar produces both, and that
**nothing may be bought before that has an answer**. It offers three explanations and tests
none: the throttle (called "an unlikely *whole* explanation"), a memory-bound vendor
condition, and the two hosts being one machine.

**This campaign reproduces both figures on one machine, in one afternoon, differing only by
throttle state.** Block-paired, computed within a block so host drift cancels:

| The hull gain on a pair | Measured here | What ADR-0049 attributes it to |
|---|---|---|
| **Capacity** (throttle lifted) | **1.342** [1.329, 1.365] | the campaign host's ~1.35x |
| **Throttled** | **1.119** [1.101, 1.138] | the second host's ~1.10x |

**Both hosts' hull figures are this host's, at two throttle settings.** The explanation
ADR-0049 called unlikely as a *whole* explanation is the whole explanation, for the reason it
did not consider: the two figures are not the same quantity. One is a capacity and the other
is a throttled cap, and a cap cannot show a gain it has already clipped.

**What follows for ADR-0049's revisit item 2, which is the one gating a purchase.** The
per-core-throughput model was doubted because a single scalar could not produce both figures.
It never had to: there is no second host in that comparison that this evidence can find. The
memory-bound hypothesis is **not thereby refuted** — it is left without the motive it had, and
§9 records it as unmeasured rather than closed.

### The rest of the block-paired ratios

| Ratio | Median | Per block |
|---|---|---|
| Pairing penalty, vendor, capacity | 1.258 | [1.258] |
| Pairing penalty, hulls, capacity | 1.373 | [1.384, 1.362] |
| Aggregate throughput (two cells / one), vendor, capacity | 1.590 | [1.590] |
| Aggregate throughput, hulls, capacity | 1.457 | [1.446, 1.468] |
| **What the throttle costs a pair, vendor** | **0.999** | [1.008, 0.990] |
| What the throttle costs a pair, hulls | 0.825 | [0.816, 0.835, 0.825] |
| What the throttle costs a solo cell, vendor | 0.914 | [0.914] |
| What the throttle costs a solo cell, hulls | 0.591 | [0.586, 0.596] |

**The throttle costs the vendor pair nothing — 0.999 — and costs a solo hull cell 41 % of its
speed.** A ceiling binds only where there is headroom, which is ADR-0043's own argument, now
measured across four conditions instead of one idle row.

Two cells deliver about **1.5x** one cell's throughput rather than 2x, so roughly a quarter of
the added work is lost to contention. That is the second-world campaign's pairing penalty,
reproduced here as capacity; cite it there.

## 7. Validity rules, applied literally

| Rule | Outcome |
|---|---|
| **V1** spread > 20 % refuses a pooled median | **Did not fire.** Widest spread 5.6 % |
| **V2** two sides overlap >= 90 % of the shorter window | **Did not fire.** Every paired trial's two windows started within **0.7 ms** of each other and ended within **66 ms**; the smallest overlap is >99.9 % of the shorter window |
| **V3** every side announced readiness, none exited during the window | **Did not fire.** 24 of 24 trials collected |
| **V4** >= 100 samples per side, max gap < 10 s | **Did not fire.** 1,192 - 1,197 samples per 120 s window (~10 Hz); largest gap 0.27 s |
| **V5** the configuration under test is the one labelled | **Did not fire, and it is the rule that had teeth.** Every trial's `real_time_factor` and bound collision-mesh root were read off the **installed** artifacts; all 24 matched their label |
| **V6** pre-trial load within 50 % of the campaign median | **Fired on 4 of 24 trials**, excluded from pooled figures. See Deviation 1 |

**Q7 — Gazebo's own `real_time_factor` field against the window instrument.** Ratio of the
field's median to `rtf_window`, per condition: within **±2.2 %** in seven of the eight
conditions, and **0.791** in `SOLO_HULL_THROTTLED`, where the field **under-reports by 21 %**.
So the field is not the instrument here either, and ADR-0049 decision 5's ban stands — but
**this campaign did not reproduce the 4.15x over-report** the real-time-factor-conditions
campaign measured, and could not have: no condition here is CPU-starved, which is the
condition that campaign attached to it. Cite that campaign for the 4.15x.

### Deviations

**Deviation 1 — V6 measures the container VM's load, not the host's.** `os.getloadavg()`
inside the container reads the Docker Desktop Linux VM's `/proc/loadavg`. The macOS-side
contention that `criteria.md` §8 characterised — `fileproviderd`, `WindowServer`, Chrome — is
**invisible to it**. So V6 tested how far the previous trial's teardown had drained rather
than how quiet the host was, and it is systematically biased: in the block order a solo trial
follows a paired teardown, so three of its four exclusions are solo trials, and one exclusion
(`PAIR_VENDOR_THROTTLED_1`, load 0.85 against a median of 2.04) is for a machine that was
*quieter* than typical, because the rule is two-sided as written.

**It is applied anyway, and the figures are reported both ways because the difference is
small.** Excluded trials moved the pooled medians as follows: `PAIR_VENDOR_THROTTLED`
0.882 → 0.903, `SOLO_VENDOR_FREE` 1.091 → 1.112, `SOLO_HULL_FREE` 1.655 → 1.685. **The
registered reading is the one in §3 and §4**; the unexcluded readings are larger in every
case, so applying the rule cost the campaign a little of the margin it reports and none of
its conclusions. **No number in §4 or §6 changes sign or crosses 1.0 under either reading.**

**Deviation 2 — the deficit's concentration statistic is undefined where the deficit is
negative.** With the throttle lifted a cell above 1.0 runs a *surplus*, not a deficit, and the
"share carried by the top 1 % of intervals" divides by a positive-only total that is no longer
the whole. §5 therefore reports the distribution for **throttled conditions only**, which is
where ADR-0049 asks for it. The unthrottled surpluses are in `raw/` and are not tabulated.

**Deviation 3 — the interval is ~100 ms, not the ~200 ms `criteria.md` §4 assumed.** World
statistics arrive at about 10 Hz, not 5 Hz. This was found by the mechanics shakedown and
recorded in `harness/README.md` before the first trial. The registered resolution limit was
conservative and still holds in kind.

## 8. What the data supports for ADR-0049's two thresholds — **without setting either**

`criteria.md` §2 forbids this campaign from naming either figure, and it does not. What the
data supports about **where** each threshold has to live:

**On the capacity margin above 1.0.**
- A margin measured on an **idle** cell is not a work allowance. Every trial here is idle, as
  every prior real-time figure in this repository is; the second-world campaign's rule 5 says
  so and this campaign inherits it unchanged. **Nothing here measures a pair doing work**, so
  any margin set from these numbers is a margin above an idle baseline and has to say so.
- The margin has to absorb **run-to-run spread**, which is measurable here: 5.6 % at its widest,
  across three blocks on one machine over about three hours.
- It does **not** need to absorb a throttle loss. §6 measures what the throttle costs a pair
  that has no headroom — 0.999, i.e. nothing — so the two quantities do not stack the way
  ADR-0049 anticipated when it said "the throttle loss established above adds to it".
- The two shipped-relevant configurations land on opposite sides of 1.0 with **0.898** and
  **1.194**, so any margin between about 0 % and 19 % separates them identically. **This
  campaign cannot discriminate within that band and does not try.**

**On the operating deficit bound.**
- It is a bound on a quantity with **two regimes** (§5), and a single scalar in seconds will
  describe one of them. A short machine loses 11.7 s per 120 s window as an even drip; a
  machine with headroom loses 0.35 s per window almost entirely in the top 1 % of intervals.
- Whatever the bound is, **the worst single interval is the number a mirroring path meets**,
  and it is 38 - 94 ms here across conditions — one to two orders above ADR-0043's 3.131 ms
  p99 latency. A bound written on the window total does not bound it.
- The bound is a statement about what a divergence measurement can tolerate, which is L5's
  question and is **not answered by this campaign**. Nothing here measured a divergence number.

**No threshold is proposed, and no configuration is promoted, tuned or bought on this
evidence.** ADR-0049 decision 4 is untouched.

## 9. What this campaign did not measure

- **A pair doing work.** Every cell is idle at home pose. Motion, planning, contact and grasp
  all cost more and none of it is here.
- **Whether the vendor condition is memory-bound** — ADR-0049's hypothesis 2. §6 removes its
  motive without testing it. Separating memory bandwidth from the host contention in §1 needs
  hardware performance counters, and `perf` does not work under Docker Desktop's kernel. **This
  needs a native Linux host and is handed back rather than estimated.**
- **Whether the earlier figures' host is this host.** §1 gives provenance evidence, not proof.
  The one line ADR-0049 says would settle it is still not written by anyone who took those
  measurements.
- **A second machine.** Everything here is one host, three blocks, one afternoon.
- **Anything about correctness under hulls.** This campaign measured speed. ADR-0028's
  promotion gate is the friction-grasp campaign re-run under hull geometry and this is not it.
- **A single physics step's overrun**, per §5's ~100 ms resolution.
- **The GUI**, which no trial runs, and which ADR-0043 item 2 already records as completely
  unmeasured.
- **Determinism.** Scenarios in this cell are not reproducible; see
  [`cross-cutting-testing.md`](../../architecture/cross-cutting-testing.md).
