# Capacity and the clock deficit on the configuration this repository actually ships

**Verdict: MEASURED.** The 2x2 is complete, no validity rule refused a headline figure, and
Q1 - Q7 of [`criteria.md`](criteria.md) are answered. 24 trials over three blocks, 23
collected and one discarded by V3, on one named machine, both sides of every pair sampled in
the same window.

**The shipped configuration clears ADR-0043's floor of 1.0, measured as capacity.** Paired,
throttle lifted, `select: convex_hull` unmodified: **1.219**, with every one of its four valid
side-windows above 1.0. The vendor control, on the same machine in the same session:
**0.914**, with every one of its six side-windows below it.

**This is not a statement that any requirement passes.**
[ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md) sets neither of its two
thresholds and `criteria.md` section 2 forbids this campaign from setting them. Section 9 says
what the data supports for each; it names no number as a threshold. **And a capacity measured
on an idle cell on a loaded host is not a margin** — sections 1 and 11 say what that costs.

## 0. Provenance, so that the order of events is checkable

| | |
|---|---|
| `criteria.md` sha256 | `138de7d9b5f042591bd8ea565bf9439772714126267b19164d5a2931d4e54dbe` |
| committed alone, at | `2b34aa0`, **2026-09-01 11:57:43 -05:00** |
| first trial started | **2026-09-01 12:14:09 -05:00** — 16 minutes later |
| last trial ended | **2026-09-01 14:20:32 -05:00** |
| campaign elapsed | **2.11 h**, inside the 5 h resource stopping rule `criteria.md` section 6 registered |
| base | branch `measure/capacity-on-shipped-main`, off `main` at **`734a26d`** |

**Every trial's own sidecar records the repository as clean outside this directory** —
`git status --porcelain -- model tools scripts tests workspace` returned **0** lines after the
revert on all 24, so no scratch flip was left applied and none was committed.

## 1. The machine

| | |
|---|---|
| Host | Apple **M4 Pro**, 12 cores, 24 GiB unified memory, macOS 26.5.2 (25F84), `Darwin 25.5.0` |
| Container | Docker Desktop Linux VM, **12 CPUs**, **7.653 GiB** (8,217,751,552 B) |
| Checkout | a git worktree with its own compose project, its own build volumes and its own `ROS_DOMAIN_ID` pair |
| Cell | `cell_a`, three xArm5 arms, idle at home pose; step size 0.001 s; headless |
| Other containers | 11 stopped before the first trial and **restored after the last** (the `turf-on-landing` Supabase stack, about 1.16 GiB while running) |
| Free disk | 55 GiB throughout; no trial was disk-constrained |

**This is the same machine as
[`2026-08-31-capacity-and-clock-deficit`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)**
— same CPU, same core count, same Docker allocation to the byte, same OS build, and the same
eleven containers stopped for it. That is recorded provenance, not inference, and it is what
makes section 7 a comparison of configurations rather than of machines.

**The host was not quiet and could not be made so.** `criteria.md` section 8 recorded the
contention before the first trial: `fileproviderd` at 83 % of a core, `WindowServer` at
47 - 50 %, Chrome helpers at 34 % and 17 %, Finder at 18 %, this agent's own session at
4 - 7 % — of the order of **1.5 - 2 cores busy on a 12-core machine with nothing of the
campaign running**, and a quiesced 1-minute load average of 3.5 - 3.7.

**Every capacity figure below is therefore a LOWER BOUND on what this machine would deliver
quiet, and the asymmetry matters in exactly one direction.** A figure that clears 1.0 here
would clear it quiet, because contention cannot manufacture headroom. A figure that *misses*
1.0 here is **not** thereby shown to miss it on a quiet machine. Section 4 states that beside
the vendor row rather than leaving it to be inferred.

## 2. Design as run

Eight conditions — `{PAIR, SOLO} x {VENDOR, HULL} x {THROTTLED, FREE}` — each run once per
block, three blocks, in the fixed order `criteria.md` section 6 registered: vendor throttled,
vendor free, hull throttled, hull free, pair before solo. **The vendor arm ran first even
though the shipped configuration is the hull one and running the shipped arm first would have
been more convenient had the campaign been cut short.** The order was registered before the
first trial and was followed.

Every trial: settle 30 s after the last `CITE_SIDE_READY`, then a **120 s** window with every
side sampled concurrently. **Bring-up took 35.6 - 48.9 s for a pair (median 42.5 s, n=11) and
23.5 - 32.5 s for a solo cell (median 29.0 s, n=12).**

**This campaign's one distinguishing fact: the shipped condition required no flip at all.**
`SOLO_HULL_THROTTLED` is `main` at `734a26d` untouched — `sides: single`,
`select: convex_hull`, `real_time_factor: 1.0`. Every other cell of the matrix was reached by a
scratch flip regenerated through `cite_tools.cli validate --write`, rebuilt, and reverted with
`git checkout`. **The vendor flip is the one place this campaign modified the model**, and it
exists only to produce the control.

**The instrument is `delta sim_time / delta real_time`** from each side's
`/world/cell_a/stats`, reached only through `cite_bringup.gz` carrying that side's
`GZ_PARTITION`, with the side addressed by name. Gazebo's own `real_time_factor` field was
recorded and never used as a figure — see Q7 in section 8, where it disagrees by 22 % in one
condition.

## 3. The 2x2

Median of `rtf_window` over the valid side-windows of each condition, with the range across
them. A paired condition has 6 side-windows and a solo condition 3; `n` is what survived
section 8's rules.

### Capacity — throttle lifted (`real_time_factor 0`). ADR-0049's first quantity.

| | **Pair** (both sides, same window) | **Solo** |
|---|---|---|
| **Convex hulls — THE SHIPPED SELECTION** | **1.219** [1.177 - 1.232], n=4 | **1.688** [1.656 - 1.702], n=3 |
| **Vendor meshes — the control** | **0.914** [0.884 - 0.920], n=6 | **1.123** [1.110 - 1.132], n=3 |

`PAIR_HULL_FREE` carries four side-windows rather than six because one trial was discarded by
V3; the cause is a bring-up failure in the product, and it is Deviation 2 in section 8 and a
finding in section 10.

### Throttled (`real_time_factor 1.0`) — the state the cell actually ships in

| | **Pair** | **Solo** |
|---|---|---|
| **Convex hulls — SHIPPED** | **0.992** [0.992 - 0.994], n=6 | **0.994** [0.988 - 0.995], n=3 |
| **Vendor meshes** | **0.905** [0.881 - 0.913], n=6 | **0.995** [0.991 - 0.997], n=3 |

**V1 refused nothing.** The widest spread in any condition is **4.6 %**, against the 20 %
refusal threshold registered before the first trial. The tightest is 0.2 %.

**Read the two tables against each other, because that is what the campaign is for.**
Throttled, the shipped hull pair reads 0.992 and the vendor pair 0.905 — a difference of about
a tenth, with the hull row sitting exactly where a capped measurement sits. Unthrottled the
same two are **1.219 and 0.914**. The throttled table compresses everything above 1.0 onto 1.0
and says almost nothing about the machine, which is what ADR-0049 derived from upstream source.

## 4. Does the shipped configuration clear 1.0

**The decision rule was registered in `criteria.md` section 6 before the first trial**, on
`PAIR_HULL_FREE`: CLEARS if the pooled median is above 1.0 **and every valid side-window** is;
SHORT if the pooled median is below 1.0; AMBIGUOUS in between.

| Condition | Pooled median | Every side-window | Capacity of the pair (slower side) | Verdict against the 1.0 floor |
|---|---|---|---|---|
| **Convex hulls — the shipped selection** | **1.219** | 1.226, 1.232, 1.211, 1.177 — **all above 1.0** | **1.201** | **CLEARS**, by a factor of **1.22** |
| **Vendor meshes — the control** | **0.914** | 0.914, 0.920, 0.896, 0.884, 0.915, 0.913 — **all below 1.0** | **0.913** | **SHORT**, by a factor of **1.09** |

The 1.0 is not this campaign's number. It is ADR-0043's floor, which ADR-0049 decision 1
explicitly does not relax; reporting a measurement against it is reading an existing
requirement, not setting a new one.

**What this establishes, stated narrowly.** The configuration this repository ships today,
paired, idle, on this machine, with the world's throttle lifted, sustains a real-time factor
above 1.0 on both sides concurrently — and the configuration it shipped until 2026-09-01 does
not, on the same machine in the same session, an hour apart.

**What it does not establish is the vendor row's converse.** Section 1's contention makes every
figure here a lower bound, so the hull result would survive a quiet machine and **the vendor
shortfall might not**. A quiet host could put the vendor pair above 1.0; nothing here rules
that out, and nobody may read the vendor row as "vendor meshes cannot reach 1.0".

**And clearing the bare floor is not a margin.** Every cell here is idle at home pose. The
second-world-cost campaign's rule 5 — an idle margin is not a work allowance — is inherited
unchanged, and section 11 keeps it.

## 5. The charter sentence this campaign was run to replace

`what-we-are-doing.md` section 8's Phase 2.A paragraph, and its section 14 v1.11 entry, say the
hull pair reaches *"about 0.95 against a required 1.0"* with *"the convex-hull collision
geometry that is not the shipped default"*. **Both halves are now measurably wrong, in
different ways, and this campaign is the evidence for each.**

- **0.95 was a throttled reading**, and under the throttle a measured real-time factor is
  capped at the declared factor by construction (ADR-0049, read in upstream `gz-sim` source;
  ADR-0028's and ADR-0043's 2026-09-01 corrections withdraw the conclusion). It could not have
  exceeded 1.0 whatever the machine did. **Measured as capacity on the shipped configuration
  the same pair reaches 1.219** — section 4.
- **The parenthetical is stale**: hulls *are* the shipped default as of `dd93488`, and
  `SOLO_HULL_THROTTLED` in section 3 is the shipped tree with no flip applied at all.

**This campaign does not edit the charter.** It is protected (CLAUDE.md section 12) and changes
only by the owner's explicit decision, with a version bump and a section 14 entry. What is
offered here is the measurement a correction would rest on, and the figures stay in this
directory (P1).

## 6. The deficit, and its shape

ADR-0049's second quantity: wall elapsed minus sim elapsed over the window, **in seconds**,
with the throttle in force. Per 120 s window, pooled over each condition's side-windows.

| Condition | Deficit per 120 s window | Rate | Intervals that fell behind | p50 | p99 | max | Top 1 % of intervals carries |
|---|---|---|---|---|---|---|---|
| **Pair, vendor** | **11.44 s** [10.40 - 14.24] | 0.0954 s/s | **7154 / 7154 = 100 %** | 8.89 ms | 26.7 ms | 103.8 ms | **4.7 %** |
| **Pair, hulls** | **0.91 s** [0.76 - 0.99] | 0.0075 s/s | 4650 / 7155 = 65 % | 0.04 ms | 11.8 ms | 105.4 ms | **39.1 %** |
| **Solo, vendor** | **0.60 s** [0.33 - 1.09] | 0.0050 s/s | 2030 / 3578 = 57 % | 0.00 ms | 9.2 ms | 92.4 ms | **59.1 %** |
| **Solo, hulls — THE SHIPPED CONFIGURATION** | **0.71 s** [0.63 - 1.48] | 0.0059 s/s | 2362 / 3577 = 66 % | 0.04 ms | 7.4 ms | 55.0 ms | **32.5 %** |

An interval is one gap between consecutive world-statistics messages, about **100 ms**. **A
single 1 ms physics step's overrun is below this resolution** and `criteria.md` section 4
registered that limit in advance.

**The two-regime finding of the extended campaign reproduces exactly.** Where the machine is
short — the vendor pair — the deficit is a **steady drip**: every one of 7,154 intervals fell
behind, not one kept up, the median interval loses 8.9 ms out of ~100 ms, and the largest 1 %
of intervals carries only 4.7 % of the total. Where the throttle actually binds — the solo
cells and the hull pair — it is **rare discrete overruns**: 57 - 66 % of intervals fall behind
at all, the median interval loses nothing measurable, and the top 1 % carries between a third
and three-fifths of the whole.

**Against the latency the argument is about.** ADR-0043's arithmetic, re-run on these rates
against its measured p99 one-way mirroring latency of 3.131 ms (cite that record for the
latency; it is not re-measured here):

| Condition | Deficit overtakes the p99 latency after |
|---|---|
| Pair, vendor | **33 ms** of wall time |
| Pair, hulls | **417 ms** |
| **Solo, hulls — shipped** | **531 ms** |
| Solo, vendor | **626 ms** |

**And a bound on the rate does not bound the worst event.** The shipped configuration's largest
single interval overrun is **55.0 ms**, which is 18 times the p99 mirroring latency, on a cell
whose average deficit is 0.0059 s/s. A mirroring path sized on the average would not see it
coming. That is the extended campaign's finding, reproduced.

## 7. Q6 — does the extended campaign reproduce, and did branch-versus-shipped change anything

`criteria.md` section 6 registered the rule: a per-condition pooled median differing by **less
than 10 %** is **reproduced**; by 10 % or more, **changed**, with the commit and the host state
named as candidate explanations and not adjudicated.

| Condition | [`2026-08-31`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md) | This campaign | Difference | Verdict |
|---|---|---|---|---|
| PAIR_HULL_FREE | 1.194 | **1.219** | +2.1 % | reproduced |
| PAIR_VENDOR_FREE | 0.898 | **0.914** | +1.7 % | reproduced |
| SOLO_HULL_FREE | 1.655 (n=2) | **1.688** | +2.0 % | reproduced |
| SOLO_VENDOR_FREE | 1.091 (n=1) | **1.123** | +3.0 % | reproduced |
| PAIR_HULL_THROTTLED | 0.994 | **0.992** | -0.2 % | reproduced |
| PAIR_VENDOR_THROTTLED | 0.882 (n=4) | **0.905** | +2.6 % | reproduced |
| SOLO_HULL_THROTTLED | 0.988 | **0.994** | +0.6 % | reproduced |
| SOLO_VENDOR_THROTTLED | 0.997 | **0.995** | -0.2 % | reproduced |

**All eight reproduce, the largest difference is 3.0 %, and that is the answer to the question
this campaign was commissioned to ask.** The concern was that every capacity figure in this
repository had been taken with `description.collision.select` flipped by hand on a branch,
before ADR-0028 was promoted. Measured on the shipped tree with the flip in the other
direction, **the branch-versus-shipped distinction changed nothing detectable**: the figures
are the same figures, and the earlier campaign's numbers describe the product as well as they
described the branch.

**Seven of eight differences are positive**, which is consistent with a marginally quieter host
— this campaign's three blocks ran in 2.11 h against that campaign's afternoon — and nothing
separates that from the commit. **It is not adjudicated**, per `criteria.md` section 10.

### The block-paired ratios, and two the extended campaign did not report

Computed **within a block** so host drift between blocks cancels. `criteria.md` section 6's
effect size: `|ratio - 1| >= 0.10` is a finding **only if it holds in the same direction in
every completed block**; 0.05 - 0.10 is reported and labelled as sitting inside the run-to-run
spread; below 0.05 the conditions are **not separated by this campaign**.

| Ratio | Median | Per block | Extended campaign | Verdict by the registered effect size |
|---|---|---|---|---|
| **Hull gain on a pair, capacity** | **1.341** | [1.340, 1.342] | 1.342 | **finding** |
| Hull gain on a solo cell, capacity | 1.491 | [1.534, 1.474, 1.491] | — | **finding** |
| Hull gain on a pair, throttled | 1.095 | [1.123, 1.092, 1.095] | 1.119 | **not a finding** — 0.095, inside the 0.05 - 0.10 band |
| Hull gain on a solo cell, throttled | 0.997 | [1.004, 0.993, 0.997] | — | **not separated** |
| Pairing penalty, hulls, capacity | 1.386 | [1.385, 1.387] | 1.373 | **finding** |
| Pairing penalty, vendor, capacity | 1.239 | [1.210, 1.263, 1.239] | 1.258 | **finding** |
| Aggregate throughput, hulls, capacity | 1.443 | [1.445, 1.442] | 1.457 | **finding** |
| Aggregate throughput, vendor, capacity | 1.614 | [1.653, 1.584, 1.614] | 1.590 | **finding** |
| **What the throttle costs a vendor pair** | **0.992** | [0.964, 1.021, 0.992] | 0.999 | **not separated** |
| What the throttle costs a hull pair | 0.820 | [0.808, 0.831] | 0.825 | **finding** |
| What the throttle costs a solo vendor cell | 0.886 | [0.893, 0.886, 0.881] | 0.914 | **finding** |
| What the throttle costs a solo hull cell | 0.589 | [0.585, 0.596, 0.589] | 0.591 | **finding** |
| **Pairing penalty, hulls, THROTTLED** | **1.001** | [1.001, 0.996, 1.002] | — | **not separated** |
| **Aggregate throughput, hulls, THROTTLED** | **1.997** | [1.997, 2.009, 1.996] | — | — |

**Two rows deserve reading together, and the second pair is not in the extended campaign.** The
throttle costs a vendor pair **nothing** (0.992, not separated) and costs a solo hull cell
**41 %** of its speed — a ceiling binds only where there is headroom, which is ADR-0043's own
argument. And under the throttle, **pairing a hull cell appears free**: the pairing penalty
reads 1.001 and the aggregate throughput reads 1.997, i.e. two cells for the price of two
cells. **That is a measurement artefact and not a property of the machine.** Both sides are
clipped at 1.0, so the cost of the second side is invisible; with the throttle lifted the same
ratio is **1.386** and the aggregate is **1.443**. It is the sharpest single illustration in
either campaign of why ADR-0049 moved the requirement onto capacity — a throttled measurement
would report that a second simulation is free.

**One row is reported as not a finding and is worth naming.** The hull gain on a *throttled*
pair is 1.095, which falls in the middle band the criteria registered, so this campaign does
**not** call it an effect — even though every block exceeded 1.09 and the extended campaign
measured 1.119. Applying the rule literally costs the campaign a claim it could easily have
made, which is what a rule registered in advance is for.

## 8. Validity rules, applied literally

| Rule | Outcome |
|---|---|
| **V1** spread > 20 % refuses a pooled median | **Did not fire.** Widest spread **4.6 %** (`PAIR_HULL_FREE`), tightest 0.2 % |
| **V2** two sides overlap >= 90 % of the shorter window | **Did not fire.** Every paired trial's overlap is **>= 99.998 %** of the shorter window |
| **V3** every side announced readiness, none exited during the window | **FIRED, on one trial of 24** — `PAIR_HULL_FREE_3`. See Deviation 2 and section 10 |
| **V4** >= 100 samples per side, max gap < 10 s | **Did not fire.** **1,192 - 1,197** samples per 120 s window (~10 Hz); largest gap **0.26 s** |
| **V5** the configuration under test is the one labelled | **Did not fire, and it is the rule with teeth.** All 23 collected trials' `real_time_factor` and bound collision-mesh root were read off the **installed** artifacts and matched their label |
| **V6** pre-trial load within 50 % of the campaign median | **Did not fire on the registered instrument.** Host 1-min load median **3.525**, range **2.63 - 4.70**; widest deviation +33 %. See Deviation 1 |

**Q7 — Gazebo's own `real_time_factor` field against the window instrument.** Ratio of the
field's median to `rtf_window`, per condition:

| Condition | Field / instrument | Condition | Field / instrument |
|---|---|---|---|
| PAIR_VENDOR_THROTTLED | 1.023 | PAIR_VENDOR_FREE | 1.013 |
| PAIR_HULL_THROTTLED | 1.007 | PAIR_HULL_FREE | 0.989 |
| SOLO_VENDOR_THROTTLED | 1.005 | SOLO_VENDOR_FREE | 1.000 |
| **SOLO_HULL_THROTTLED** | **0.783** | SOLO_HULL_FREE | 1.011 |

Seven of eight are within **+/- 2.3 %**. The eighth — **`SOLO_HULL_THROTTLED`, which is the
shipped configuration** — has the field **under-reporting by 22 %**, range 0.736 - 0.788 across
its three trials. **The extended campaign found 0.791 in the same cell of the matrix and in no
other**, so this is a reproduced, condition-specific disagreement rather than noise, and
ADR-0049 decision 5's ban on that field stands. Neither campaign reproduced the **4.15x
over-report** the real-time-factor-conditions campaign measured, and neither could have: no
condition here is CPU-starved, which is the condition that campaign attached to it. Cite that
campaign for the 4.15x.

### Deviations

**Deviation 1 — V6's two instruments disagree, and the corrected one is the registered one.**
`criteria.md` section 7 corrected V6 **before the first trial** to read the macOS host's
1-minute load average rather than `os.getloadavg()` inside the container, which reads the
Docker Desktop Linux VM. Both were recorded on every trial.

- **On the host reading — the registered rule — V6 excluded nothing.** Median 3.525, range
  2.63 - 4.70, widest deviation +33 % against the 50 % threshold.
- **On the container reading — the extended campaign's rule — V6 would have excluded three
  trials**: `SOLO_HULL_FREE_2` (VM load 2.97), `SOLO_HULL_FREE_3` (0.93) and
  `SOLO_HULL_THROTTLED_2` (3.52), against a VM median of 1.91. **All three are hull trials and
  all three are solo**, which is the same systematic bias the extended campaign identified in
  its own Deviation 1: in the registered block order a solo trial follows a paired teardown, so
  the container's load average measures how far the previous trial has drained rather than how
  busy the machine is. Here it would have thinned the shipped arm specifically.
- **The difference is immaterial to every conclusion, and it is reported anyway.** Under the
  container rule `SOLO_HULL_FREE` would read 1.702 instead of 1.688, and `SOLO_HULL_THROTTLED`
  0.994 either way. **No figure in sections 3, 4, 6 or 7 changes sign or crosses 1.0 under
  either reading.**

**Deviation 2 — one trial of 24 was discarded by V3, on the headline condition, and it was NOT
re-run.** `PAIR_HULL_FREE_3`: the counterpart announced readiness and the plant never did. The
cause is in section 10 and is a defect in the product's bring-up, not in the instrument.

`criteria.md` registered three blocks and **no replacement policy**. Running a ninth trial in
that block because the eighth failed would be a design change made after seeing a result, and a
rule that only fires when it is convenient is not a rule — so the trial stands discarded,
`PAIR_HULL_FREE` carries **two blocks and four side-windows** rather than three and six, and
block 3 contributes no hull-capacity ratio. **The missing replacement policy is recorded here
as a gap in the criteria and is deliberately not filled now.** A future campaign should
register one in advance, in either direction.

**The discard costs the headline its widest evidence and does not weaken it**: the four
surviving side-windows are 1.226, 1.232, 1.211 and 1.177, the lowest is 18 % above the floor,
and the two surviving blocks agree to 4.6 %.

**Deviation 3 — the "deficit" is a surplus wherever the throttle is lifted, and the
concentration statistic is undefined there.** A cell running above 1.0 banks sim time rather
than losing it: `SOLO_HULL_FREE` accumulates a **surplus of 82.5 s** per 120 s window. The
"share carried by the top 1 %" divides by a positive-only total that is then not the whole,
which is why `deficit_top5pct_share` reads -4.20 for `PAIR_HULL_FREE`. Section 6 therefore
reports the distribution for **throttled conditions only**, which is where ADR-0049 asks for
it. The unthrottled surpluses are in `raw/` and are not tabulated. This is the extended
campaign's Deviation 2, inherited.

**Deviation 4 — an analyser defect found after the last trial, fixed, and it moved no figure.**
`analyse.py`'s `load()` globs `*.json`, and this campaign's new `<LABEL>.host.json` sidecars
match it, so 24 ghost records entered the listing and `n_records` read **48**. Every ghost was
`valid=False` under V3 for having no window, so it entered no pooled median, no ratio and no
exclusion set. **The pre-fix and post-fix summaries were compared field by field: `pooled` and
`block_ratios` are identical, both V6 exclusion sets are identical, and both load medians are
identical.** The fix excludes the sidecars by suffix rather than renaming them, because
renaming would rewrite collected data. This is a defect in the campaign's own tooling, found
and reported rather than quietly corrected.

## 9. What the data supports for ADR-0049's two thresholds — **without setting either**

`criteria.md` section 2 forbids this campaign from naming either figure, and it does not.

**On the capacity margin above 1.0.**

- A margin measured on an **idle** cell is not a work allowance. Every trial here is idle;
  nothing here measures a pair doing work, so any margin set from these numbers is a margin
  above an idle baseline and has to say so.
- The margin has to absorb **run-to-run spread**, which is measurable here: **4.6 %** at its
  widest, across three blocks on one machine in 2.11 h. That is tighter than the extended
  campaign's 5.6 % and of the same order.
- It does **not** need to absorb a throttle loss. Section 7 measures what the throttle costs a
  pair with no headroom — 0.992, not separated from 1 — so the two quantities do not stack.
- **The two shipped-relevant configurations no longer sit on opposite sides of 1.0 in the way
  the extended campaign described, because the shipped one moved.** Today the shipped
  configuration is the one at **1.219** and the superseded one is at **0.914**. A margin
  anywhere between 0 % and 19 % separates them identically, and **this campaign cannot
  discriminate within that band and does not try.**
- **A margin set from this campaign would be set from a lower bound.** Section 1 says why.

**On the operating deficit bound.**

- It is a bound on a quantity with **two regimes** (section 6), and a single scalar in seconds
  will describe one of them.
- **The shipped configuration's own number is 0.71 s per 120 s window** — measured on the
  shipped tree with no flip applied — at a rate of 0.0059 s/s, two thirds of its intervals
  falling behind and a third of the total carried by the top 1 %. That is the regime where the
  throttle binds.
- **The worst single interval is the number a mirroring path meets**, and for the shipped
  configuration it is **55.0 ms** — 18 times ADR-0043's 3.131 ms p99 latency, in one event. A
  bound written on the window total does not bound it.
- The bound is a statement about what a divergence measurement can tolerate, which is L5's
  question. `cite_twin` now exists and its `DEFICIT_BOUND_S` is `None` precisely because
  ADR-0049 declines to set it; **nothing here sets it**, and **nothing in this campaign
  measured a divergence number**.

**No threshold is proposed, and no configuration is promoted, tuned or bought on this
evidence.** ADR-0049 decision 4 is untouched.

## 10. One finding handed back: a paired bring-up failed on the plant side

`PAIR_HULL_FREE_3`, the only discarded trial, is a **product** failure and not a harness one,
and both sides' console output is committed in `raw/`.

The plant's `planning_scene_loader.py` for `arm_1` exited **1** with
`move_group refused the planning scene diff for zone 'cell_a'`, **14 ms** after that same
`move_group` logged `Unknown frame: cite_world`. That node is `required` in the launch, so the
plant's launch shut down; a side that ends ends the pair (ADR-0047), and the supervisor
reported `plant: ready=False status=1` / `counterpart: ready=True status=1`. **The counterpart,
running the identical configuration on its own domain and partition at the same moment, brought
its three planning scenes up cleanly** — 12 collision objects per arm, all three loaders
finishing cleanly.

**This looks like a startup race between the planning-scene load and the frame becoming
resolvable in `move_group`'s scene monitor, and it is one event.** It is consistent with
CLAUDE.md section 2's standing note that `bringup` is not a scenario that always passes, and it
is the same *class* of thing — but **it is not attributed** to that or to anything else here.
One occurrence in eleven paired bring-ups and twelve solo ones in this campaign; no threshold
was registered for it; this campaign measured speed and is not the instrument that would settle
it.

The record is `raw/PAIR_HULL_FREE_3.console`, which carries both sides' full launch output.

## 11. What this campaign did not measure

- **A second machine.** One host, three blocks, 2.11 hours. **A capacity is a property of a
  machine and a configuration together, and this campaign varies only the second.** Nothing
  here says what any other machine does, and the 1.219 is not a property of the software.
- **A quiet machine.** Section 1: every capacity figure is a **lower bound**, and a lower bound
  is not a capacity. The direction is safe for the hull result and unsafe for the vendor one.
- **A pair doing work.** Every cell is idle at home pose. Motion, planning, contact and grasp
  all cost more and none of it is here.
- **Anything about correctness, grasping or safety under either geometry.** This campaign
  measured speed. ADR-0028's grasp clause was addressed elsewhere, by a campaign whose verdict
  was INCONCLUSIVE — [`2026-09-01-hull-grasp`](../2026-09-01-hull-grasp/ANALYSIS.md) — and
  nothing here adds to or subtracts from it.
- **Whether the vendor condition is memory-bound** — ADR-0049's hypothesis 2. Separating that
  from section 1's host contention needs hardware performance counters, and `perf` does not
  work under Docker Desktop's kernel. **This needs a native Linux host and is handed back
  rather than estimated.**
- **Whether the difference from the extended campaign is the commit or the host.** Section 7
  reports it at under 3 % and does not adjudicate it, per `criteria.md` section 10.
- **A single physics step's overrun**, per section 6's ~100 ms resolution.
- **The GUI**, which no trial runs.
- **Anything about `cite_twin` or a divergence number.** L5 exists in the tree and nothing
  starts it; no trial here brought it up.
- **Determinism.** Scenarios in this cell are not reproducible; see
  [`cross-cutting-testing.md`](../../architecture/cross-cutting-testing.md).
