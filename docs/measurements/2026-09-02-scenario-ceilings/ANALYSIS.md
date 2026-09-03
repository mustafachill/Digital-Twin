# The scenario ceilings, measured at four allocations, and the six runs the instrument lost

**Verdict, in this campaign's own registered vocabulary.** Every one is `criteria.md` §7's
rule applied by `harness/analyse.py` to `raw/`, and every one is stated **per (scenario,
ceiling, condition)** — rule T: a condition is not another condition's evidence, and a
scenario is not another scenario's. `M` is the inherited margin, `ceiling / slowest measured
instance`, banded `M < 1.5` TOO TIGHT, `1.5 <= M <= 10` APPROPRIATE, `M > 10` TOO LOOSE
(§2.2, from the 2026-08-29 campaign's §5).

| `<scenario>.<CONSTANT>` | value | FULL | C4 | C2 | C1 |
|---|---|---|---|---|---|
| `bringup.BRING_UP_CEILING_S` | 240.0 | **APPROPRIATE** 8.56 (n=1) | **APPROPRIATE** 8.12 (n=1) | **APPROPRIATE** 6.58 (n=2) | **APPROPRIATE** 4.54 (n=2) |
| `bringup.DELIVERY_CEILING_S` | 30.0 | **INCONCLUSIVE** (n=9) | **INCONCLUSIVE** (n=9) | **INCONCLUSIVE** (n=18) | **INCONCLUSIVE** (n=18) |
| `bringup.TRAJECTORY_CEILING_S` | 60.0 | **TOO LOOSE** 19.35 (n=5) | **TOO LOOSE** 19.36 (n=5) | **INCONCLUSIVE** (n=10) | **APPROPRIATE** 4.40 (n=10) |
| `bringup.SKILL_CEILING_S` | 120.0 | **TOO LOOSE** 19.67 (n=1) | **TOO LOOSE** 16.34 (n=1) | **APPROPRIATE** 8.95 (n=2) | **APPROPRIATE** 3.93 (n=2) |
| `pick_and_place.BRING_UP_CEILING_S` **[cold]** | 300.0 | **APPROPRIATE** 8.33 (n=4) | **APPROPRIATE** 8.31 (n=2) | **APPROPRIATE** 8.20 (n=2) | **APPROPRIATE** 5.62 (n=1) |
| `pick_and_place.BRING_UP_CEILING_S` **[warm]** | 300.0 | **INCONCLUSIVE** (n=4) | **INCONCLUSIVE** (n=2) | **INCONCLUSIVE** (n=2) | **INCONCLUSIVE** (n=1) |
| `pick_and_place.CYCLE_CEILING_S` | 420.0 | **APPROPRIATE** 6.93 (n=4) | **APPROPRIATE** 6.27 (n=2) | **APPROPRIATE** 3.31 (n=2) | **APPROPRIATE** 1.66 (n=1) |
| `pick_and_place.SETTLE_CEILING_S` | 60.0 | **NOT ASSESSED** | **NOT ASSESSED** | **NOT ASSESSED** | **NOT ASSESSED** |
| `continuous_line.BRING_UP_CEILING_S` **[cold]** | 300.0 | **APPROPRIATE** 9.81 (n=3) | **TOO LOOSE** 10.75 (n=1) | **APPROPRIATE** 7.23 (n=2) | **APPROPRIATE** 5.84 (n=1) |
| `continuous_line.BRING_UP_CEILING_S` **[warm]** | 300.0 | **NOT ASSESSED** | **NOT ASSESSED** | **NOT ASSESSED** | **NOT ASSESSED** |
| `continuous_line.LEG_CEILING_S` | 420.0 | **APPROPRIATE** 4.47 (n=90) | **FIRED — NO BAND** (n=1) | **APPROPRIATE** 2.74 (n=33) | **APPROPRIATE** 1.56 (n=30) |

**44 cells. 36 assessed, 8 NOT ASSESSED.** Of the 36: **21 APPROPRIATE, 5 TOO LOOSE,
9 INCONCLUSIVE, 1 FIRED, and 0 TOO TIGHT.** Every `M` printed above is the **lower bound**,
`ceiling / max`; rule Q's upper bound `ceiling / (max - q)` is printed beside it per cell in
§3 and is what decides most of the INCONCLUSIVE column.

**The four results that matter, each named by the rule that produced it.**

1. **Two ceilings are TOO LOOSE on the shipped configuration at a full allocation:**
   `bringup.TRAJECTORY_CEILING_S` (`M = 19.35`, n=5) and `bringup.SKILL_CEILING_S`
   (`M = 19.67`, n=1). Both are still TOO LOOSE at C4. §7.2's bands. **§8's censoring bias
   pushes every margin toward exactly this verdict**, and §3.1 states it beside the two rather
   than leaving a reader to derive it.
2. **One crossing is located, and only one.** `bringup.SKILL_CEILING_S` goes TOO LOOSE →
   APPROPRIATE **bracketed between C4 and C2** (B1). Every other ceiling is NOT LOCATED, or
   its bracket is reported open on the side of a cell no bracket may span.
3. **Rule Q's `max - q <= 0` branch decides 8 of the 36 assessed cells** — all four
   `bringup.DELIVERY_CEILING_S` cells and all four `pick_and_place.BRING_UP_CEILING_S`
   **[warm]** cells. Their measured maxima are **smaller than the poll quantum**, so no upper
   bound on the margin exists and no band can be stated. §7.1 predicted this in the same
   breath as it registered the rule, and it is why **PR2's headline half has no verdict**.
4. **V2 discarded 6 of 28 runs on an instrument failure, not on a wrongly configured cell**
   — the I7 read-back returned 22 characters with no `convex_hull` reference on five
   `bringup` runs, while the world `cat` in the *same* container succeeded. Deviation 1. It
   cost `bringup` four of its five FULL runs and one of its two C4 runs, which is why **every
   `bringup` cell at FULL and at C4 rests on a single run**, and four of those eight on a
   single record.

**One count is not in the table and belongs in the headline: `continuous_line.LEG_CEILING_S`
FIRED at C4**, in `C4_continuous_line_2`, on a genuine leg —
`piece 1: STOPPED after 1/10 milestones, waiting on lifted(station_transfer_1:
cell_a__table_pick__surface) for 420s`. That cell gets **no band**. The `M = 491.80` its one
surviving record computes to is published under the FIRED label in §3.4 because it says what
the completing instance cost, and **no sentence anywhere may derive a verdict on that ceiling
from it.**

- **Campaign:** `docs/measurements/2026-09-02-scenario-ceilings/`
- **Branch under measurement:** `feat/close-phase-debts`. **BASE_COMMIT `c38a42c`.** Every run
  executed at `HEAD = 98fbbfc`, with `git diff c38a42c..HEAD -- model/ workspace/src/ tools/
  tests/ scripts/` **empty** and the worktree clean in all five watched paths, at **both ends
  of every run**; `v1_clean` is `true` on all 28 run documents and no pair of readings
  disagreed.
- **`criteria.md` sha256:**
  `da918ad644c6b828347162e85670a2fcbb13701b474d40085ffa7a100c1fd133`
  Committed **alone** at `340a363`, amended at `f895733` before the harness existed and before
  any trial ran, and unchanged since. That sha256 is recorded in `raw/provenance.txt` by every
  campaign invocation and matches the file on disk.
- **The item that asked for it:** [`docs/open-work.md`](../../open-work.md) **#30**. Its "may
  now be loose" is answered here as an **absolute verdict on the shipped configuration** and
  never as a delta — **rule H**: the 2026-08-29 figures are on a different machine, a
  different architecture and different collision geometry, and no margin here is subtracted
  from, divided by, or described as an improvement on one there.
- **The campaign whose definitions this one inherits:**
  [`2026-08-29-real-time-factor-conditions/`](../2026-08-29-real-time-factor-conditions/ANALYSIS.md).
  Its §5 margin, its three bands and its rule D3 are used verbatim. It stays frozen; no file
  in it was read for a figure, edited or re-analysed.
- **The directory is dated 2026-09-02, when `criteria.md` was written and frozen. Every trial
  ran on 2026-09-03.** Both dates are in `raw/provenance.txt` and in every run document.

---

## 1. What was run

| condition | `bringup` | `pick_and_place` | `continuous_line` | runs | admitted |
|---|---|---|---|---|---|
| **FULL** (`cpu.max` = `max 100000`, 16 cores) | 5 | 4 | 3 | 12 | **8** |
| **C4** (`docker update --cpus 4`) | 2 | 2 | 2 | 6 | **4** |
| **C2** (`--cpus 2`) | 2 | 2 | 2 | 6 | **6** |
| **C1** (`--cpus 1`) | 2 | 1 | 1 | 4 | **4** |
| | 11 | 9 | 8 | **28** | **22** |

**28 runs taken, exactly the §6 minimum, and none topped up (V8).** All 28 produced a run
document and a captured console; **one of them produced zero `CITE_TIMING` records** because
its launch stopped during bring-up (§7). **22 admitted, 6 discarded**, every discard by V2 and
every one named in §2.1. `raw/shakedown/` holds one `bringup` run taken before the first trial
and is **excluded from every figure in this document** — the exclusion is in code, not in this
sentence: `analyse.py` globs `raw/*.json` at the top level only.

**Order.** §6 fixes an opening block of one FULL run per scenario, an interleaved body and the
last FULL runs at the end, so that host drift shows up as scatter *within* a condition rather
than as a difference *between* conditions. Executed: the first three runs were
`FULL_bringup_1`, `FULL_pick_and_place_1`, `FULL_continuous_line_1`; the last three were
`FULL_bringup_4`, `FULL_bringup_5`, `FULL_pick_and_place_4`; the twelve FULL runs sit at
positions 1-4, 8, 12, 16, 20, 23, 26, 27, 28 of 28. **FULL appears at both ends and
throughout**, which is what the design asked for.

**Wall clock, and two figures that are both right because they measure different things.**
From the campaign invocation's environment block, `2026-09-03T16:26:04Z`, to the last run's
end, `2026-09-03T19:11:00Z`: **2 h 44 min 56 s**. From the *first run's* start,
`16:27:04Z`, to the same end: **2 h 43 min 56 s**. The 28 run durations sum to **8208.8 s**
(2 h 16 min 49 s); the remainder is §6's 60 s quiesce between runs and per-run setup. Longest
run: `C1_continuous_line_1`, **2270.865 s**. Shortest: `FULL_bringup_2`, **43.214 s**.

**Every run is the plant, headless, on the shipped configuration.** `./scripts/sim --pair` is
not used and the model declares `sides: single`; `CITE_LINE_WORKPIECES` was **unset in every
run**, read from the container's own environment rather than assumed, so `continuous_line` ran
its default 3 work-pieces and the ladder derived from the generated topology at length 10 —
cross-checked against the milestone descriptions the records themselves carry, **10 distinct
milestones observed, agrees**.

---

## 2. Q-D — the instrument, reported first because it decided six runs

§1's Q-D says this is a first-class result and not a footnote, "because a margin computed off
the wrong quantity is worse than no margin". Two halves: the configuration read-back, which
failed six times, and the records themselves, which did not fail once.

### 2.1 V2 discarded six runs, and the failure is in the instrument

| run | condition | scenario | `v2_ok` | `hull_collision_refs` | `description_chars` | `world_throttle_declared` |
|---|---|---|---|---|---|---|
| `FULL_bringup_2` | FULL | bringup | **False** | 0 | **22** | True |
| `FULL_bringup_3` | FULL | bringup | **False** | 0 | **22** | True |
| `FULL_bringup_4` | FULL | bringup | **False** | 0 | **22** | True |
| `FULL_bringup_5` | FULL | bringup | **False** | 0 | **22** | True |
| `C4_bringup_2` | C4 | bringup | **False** | 0 | **22** | True |
| `C4_continuous_line_1` | C4 | continuous_line | **None** | — | — | — |

**The first five are one signature.** I7 reads the description back from the running cell with
`ros2 param get /cite/cell_a/arm_1/description_publisher robot_description`, executed with
`docker exec` inside the container under measurement, and reads the world with a `cat` of the
installed copy in the same container by the same mechanism. On these five runs the **world
read succeeded** — `world_read_ok` true, `world_throttle_declared` true, so ADR-0043's throttle
was read back off the running cell — and the **description read returned 22 characters**
containing neither `robot_description` nor `meshes/collision/xarm5/convex_hull`.
`FULL_bringup_1` ran the identical command against the identical image and read **33 653
characters with 13 hull references**, and so did every admitted run.

**So this is an instrument failure and not a wrongly configured cell**, and V2 did the right
thing anyway: it is a conjunction of two **positive** findings by construction — its own
docstring says *"'no vendor mesh found' must not be reachable by not looking"* — so an
unreadable answer fails closed. The five runs are discarded rather than believed.

**What cannot be said about it.** The five are not the last five runs, not one condition, and
not consecutive: they sit at positions 4, 16, 24, 26 and 27, with successful read-backs at
1, 7, 10, 13, 19 and 22. They are all `bringup`, and `bringup` is the shortest scenario, but
six of the eleven `bringup` runs read back correctly, so **scenario length does not separate
them**. The I7 gate's wait for the first `CITE_TIMING` line does not separate them either:
27.4-37.4 s on the five failing runs against 28.5-55.2 s on the six succeeding ones, and the
closest pair — `C4_bringup_1` at 30.215 s, which read back, and `C4_bringup_2` at 30.363 s,
which did not — differ by 148 ms. **Nothing here attributes the failure**, and deviation 1
records why nothing in `raw/` can.

**The sixth discard is a different thing entirely.** `C4_continuous_line_1`'s launch stopped
during bring-up (§7), so no `CITE_TIMING` line ever appeared, the I7 gate never opened and the
run document carries an empty `i7`. It failed **V2 and V4** — 6 of 6 expected triples absent,
against V4's threshold of half. Deviation 3 records that V2 is worded for a reading that
disagrees rather than for a reading never taken.

### 2.2 The records themselves, and they are clean

Pooled over all 28 collected runs, admitted and discarded:

| quantity | rule | result |
|---|---|---|
| `CITE_TIMING` marker lines | I1 | **606** |
| parsed | I1 | **606** |
| **mangled** | **G** | **0** (0.000, against a 5 % discard threshold) |
| **zero-spin, discarded** | **Z** | **187** |
| **`elapsed_s > ceiling_s`** | **K** | **0** |
| dropped by rule A | A | **0** |
| dropped by rule X | X | **0** |
| non-leg `LEG_CEILING_S` dropped | §2.3 | **0** |
| surviving to the margins | | **284** |

**Threat 6 did not materialise.** `print` writes payload and newline in two calls onto a stream
shared with the launch service, and I1's regex exists for that; not one line in the campaign
was interleaved. **Rule K found nothing either** — no record exceeded its own `ceiling_s`, so
the two-clock disagreement threat 4 registers produced no datum here. Both are **PR6**, and it
held.

**Rule A's premise was checked rather than assumed on every `bringup` run.** The first emitting
test was `test_a_skill_moves_the_arm_to_its_home_configuration` in all six admitted `bringup`
runs, so the alphabetical ordering rule A rests on holds, and **exactly one** contributing
record per run survived — **PR7**, held. Rule A dropped **0** records, because the analyser
selects `the arm_1 skill server` rather than deleting the others; the other four `what` values
appear in rule Z's table instead, where they are zero-spin as rule A predicts.

**Rule E found no absent triple in any admitted run except the two failed `continuous_line`
runs**, and there it reported `k of n` rather than presence:

- `C2_continuous_line_2`: `piece {n}: {milestone}` **3 of 30**, the settle **1 of 3**, the
  removal **ABSENT 0 of 3**.
- `C4_continuous_line_2`: `piece {n}: {milestone}` **1 of 30**, settle 1 of 3, removal 1 of 3.

That is threat 12 working as registered: one surviving leg satisfies a presence check, and
these two runs would have looked complete to one. **Every pooled `LEG_CEILING_S` cell below
carries its `k of n` in the same cell as its margin**, which is what §7.2 requires.

---

## 3. Q-A and Q-C — the margin at each allocation, on the configuration this repository ships

Every figure below is taken with **ADR-0043's throttle in the world** and **convex-hull
collision geometry selected**, both read back from the **running cell** on every admitted run:
13 hull collision references and `<real_time_factor>1</real_time_factor>` in the installed
world, on all 22. **This campaign attributes nothing to either lever** (§8, and the harness's
own limitation 5): measuring a vendor-mesh or throttle-lifted control would edit `model/` or
the generated world, which §0 forbids and V1 discards.

`max` is the slowest measured instance and the margin is defined on it. `q` is the emitting
site's poll quantum from §7.1's table.

| cell | n | min | median | **max** | `M = c/max` | `M = c/(max-q)` | verdict |
|---|---|---|---|---|---|---|---|
| `bringup.BRING_UP_CEILING_S` FULL | 1 | 28.022 | 28.022 | **28.022** | 8.56 | 8.88 (q=1.0) | APPROPRIATE |
| " C4 | 1 | 29.553 | 29.553 | **29.553** | 8.12 | 8.41 | APPROPRIATE |
| " C2 | 2 | 33.290 | 34.894 | **36.498** | 6.58 | 6.76 | APPROPRIATE |
| " C1 | 2 | 52.749 | 52.825 | **52.901** | 4.54 | 4.62 | APPROPRIATE |
| `bringup.DELIVERY_CEILING_S` FULL | 9 | 0.003 | 0.005 | **0.013** | 2307.69 | **none** — `max - q <= 0` | INCONCLUSIVE |
| `bringup.TRAJECTORY_CEILING_S` FULL | 5 | 0.000 | 0.001 | **3.100** | 19.35 | 23.08 (q=0.5) | **TOO LOOSE** |
| " C4 | 5 | 0.000 | 0.001 | **3.099** | 19.36 | 23.09 | **TOO LOOSE** |
| " C2 | 10 | 0.000 | 0.032 | **6.087** | 9.86 | 10.74 | INCONCLUSIVE |
| " C1 | 10 | 0.000 | 0.044 | **13.650** | 4.40 | 4.56 | APPROPRIATE |
| `bringup.SKILL_CEILING_S` FULL | 1 | 6.102 | 6.102 | **6.102** | 19.67 | 21.42 | **TOO LOOSE** |
| " C4 | 1 | 7.342 | 7.342 | **7.342** | 16.34 | 17.54 | **TOO LOOSE** |
| " C2 | 2 | 13.406 | 13.408 | **13.410** | 8.95 | 9.30 | APPROPRIATE |
| " C1 | 2 | 28.808 | 29.657 | **30.506** | 3.93 | 4.00 | APPROPRIATE |
| `pick_and_place.BRING_UP` [cold] FULL | 4 | 26.529 | 29.026 | **36.028** | 8.33 | 8.69 (q=1.5) | APPROPRIATE |
| " C4 | 2 | 24.550 | 30.318 | **36.086** | 8.31 | 8.67 | APPROPRIATE |
| " C2 | 2 | 36.050 | 36.322 | **36.595** | 8.20 | 8.55 | APPROPRIATE |
| " C1 | 1 | 53.337 | 53.337 | **53.337** | 5.62 | 5.79 | APPROPRIATE |
| `pick_and_place.CYCLE_CEILING_S` FULL | 4 | 58.759 | 59.908 | **60.609** | 6.93 | 7.17 (q=2.0) | APPROPRIATE |
| " C4 | 2 | 64.668 | 65.852 | **67.036** | 6.27 | 6.46 | APPROPRIATE |
| " C2 | 2 | 116.112 | 121.463 | **126.813** | 3.31 | 3.37 | APPROPRIATE |
| " C1 | 1 | 253.400 | 253.400 | **253.400** | 1.66 | 1.67 | APPROPRIATE |
| `continuous_line.BRING_UP` [cold] FULL | 3 | 26.466 | 27.259 | **30.578** | 9.81 | 9.97 (q=0.5) | APPROPRIATE |
| " C4 | 1 | 27.897 | 27.897 | **27.897** | 10.75 | 10.95 | **TOO LOOSE** |
| " C2 | 2 | 35.999 | 38.745 | **41.490** | 7.23 | 7.32 | APPROPRIATE |
| " C1 | 1 | 51.392 | 51.392 | **51.392** | 5.84 | 5.89 | APPROPRIATE |
| `continuous_line.LEG_CEILING_S` FULL | 90 | 0.570 | 13.342 | **93.893** | 4.47 | 4.50 (q=0.5) | APPROPRIATE (90 of 90) |
| " C2 | 33 | 1.091 | 26.290 | **153.454** | 2.74 | 2.75 | APPROPRIATE (33 of 60) |
| " C1 | 30 | 3.500 | 57.790 | **268.606** | 1.56 | 1.57 | APPROPRIATE (30 of 30) |

**Twenty-eight cells are listed above. The other sixteen are in §3.2, §3.3 and §3.4**, where
the rule that decided each is given: the remaining three `bringup.DELIVERY_CEILING_S` cells and
the four `pick_and_place` **[warm]** cells carry no upper bound; `SETTLE_CEILING_S` and
`continuous_line` **[warm]** are NOT ASSESSED, eight cells; and `continuous_line.LEG_CEILING_S`
at C4 is FIRED. **The `k of n` beside the three `LEG_CEILING_S` verdicts is rule E's**, and it
sits in the same cell as the margin because §7.2 requires it there.

**`rule X2` agreed with the pooled reading in every cell where it could be evaluated**, so no
cell was made INCONCLUSIVE by a failed run's records: the margins computed over all valid
records and over passing runs only land in the same band everywhere. Two cells —
`continuous_line.BRING_UP_CEILING_S` [cold] at C4 and `continuous_line.LEG_CEILING_S` at C4 —
have no passing-run record at all, so the two readings cannot be compared there, and the
analyser says so rather than reporting agreement.

**Rule NOISY decorated 15 of the 36 assessed cells and overturned none**, which is its
registered behaviour: the margin is defined on the maximum by design, and a noisy group's
maximum is exactly the quantity the definition wants. The noisiest are the ones whose distributions are genuinely
long-tailed — `LEG_CEILING_S` at every condition, and `TRAJECTORY_CEILING_S`, whose median is
milliseconds and whose maximum is seconds.

### 3.1 The two TOO LOOSE verdicts at FULL, with the bias that favours them named

`bringup.TRAJECTORY_CEILING_S` at **`M = 19.35`** and `bringup.SKILL_CEILING_S` at
**`M = 19.67`**, both TOO LOOSE at FULL and both still TOO LOOSE at C4. Under the inherited
band that reads: *"a regression an order of magnitude in size would still pass. A ceiling that
can no longer fail is not a check."*

**§8's censoring bias runs toward this verdict and must be stated with it.** A wait that times
out emits no record, so every censored instance removes a candidate for the maximum, a smaller
maximum is a larger `M`, and **censoring biases every margin up, toward TOO LOOSE, and never
toward TOO TIGHT**. These two verdicts are therefore the ones most exposed to the bias. What
limits the exposure here is that both were measured in runs whose scenario **passed** — no wait
in them timed out at all — so nothing is missing from those particular distributions; the bias
is a statement about the campaign's reach, not about these five and one records.

**`bringup.SKILL_CEILING_S`'s FULL and C4 cells each rest on one record**, because that ceiling
has a single call site on `ARMS[0]` and V2 discarded four of the five FULL `bringup` runs.
§7.2 requires this sentence and it is printed per cell: *this band rests on 1 record — median,
IQR and maximum are the same number.* At C2, where two records survived, they agree to 4 ms.

**`bringup.TRAJECTORY_CEILING_S`'s five records per run are not five samples of one thing.**
The ceiling bounds five different waits — gripper goal accepted, gripper result, trajectory
goal accepted, trajectory result, `MoveTo` goal accepted — pooled under one constant because
that is how the file declares it. Its median at FULL is **1 ms** and its maximum **3.100 s**;
the distribution is bimodal by construction, and the margin is the maximum, which is one of
the two result waits.

### 3.2 Nine INCONCLUSIVE cells, eight of them by rule Q's no-upper-bound branch

**This is the campaign's structural result and not an accident** (deviation 4). Rule Q requires
every margin to be computed twice, from `max` and from `max - q`, because poll quantisation
biases `elapsed_s` up by at most one loop iteration. Where `max - q <= 0` the cell is
INCONCLUSIVE and **no upper bound is printed**.

| cell family | `max` observed | `q` | why no upper bound |
|---|---|---|---|
| `bringup.DELIVERY_CEILING_S`, all four | 0.013 / 0.035 / 0.066 / 0.096 s | 0.5 s | the quantum exceeds the maximum |
| `pick_and_place.BRING_UP_CEILING_S` [warm], all four | 0.013 / 0.020 / 0.101 / 0.099 s | 0.5 s | the quantum exceeds the maximum |

Both families measure sub-100-millisecond intervals with a 500-millisecond poll. **The
measurement cannot resolve them**, and the true margin is bounded below by the printed figure
and above by nothing. §7.1 said this in advance and named `DELIVERY_CEILING_S` as the ceiling
*"the quantum can move"*, which is why registering rule Q with a decision rather than as a name
was the difference between a verdict and a quantified bias with no rule governing it.

**The lower bounds are extreme and are printed rather than suppressed**: `M >= 2307.69` for
`bringup.DELIVERY_CEILING_S` at FULL and `M >= 23076.92` for
`pick_and_place.BRING_UP_CEILING_S` [warm] at FULL, both reading TOO LOOSE on the lower bound
alone. **The cell's verdict is INCONCLUSIVE and the reading is not the verdict.** Nothing in
this document treats these ceilings as banded.

**The ninth INCONCLUSIVE cell is a different branch of the same rule.**
`bringup.TRAJECTORY_CEILING_S` at C2 reads `M = 9.86` (APPROPRIATE) from the maximum and
`M = 10.74` (TOO LOOSE) from `max - q`: **the poll quantum spans a band edge**, so both
readings and both bands are published and neither is chosen.

**One thing the `DELIVERY_CEILING_S` figures are a statement about, and one they are not.**
That ceiling bounds **six** waits in `bringup.py`; the sixth, the follower-settle loop in
`test_the_gripper_linkage_is_actually_coupled`, **emits nothing deliberately** and is not
instrumented here, because instrumenting it would edit `tests/`. So every `DELIVERY_CEILING_S`
figure above is a statement about the **five instrumented waits** and says nothing about the
sixth. It is not rounded up (§8, and the harness's limitation 2).

### 3.3 Eight NOT ASSESSED cells, and what rule N forbids saying about them

| ceiling | conditions | why |
|---|---|---|
| `pick_and_place.SETTLE_CEILING_S` | all four | **9 records, all zero-spin**, all discarded by rule Z. n = 0 valid |
| `continuous_line.BRING_UP_CEILING_S` **[warm]** | all four | every warm record is zero-spin. n = 0 valid |

**Rule N, in its registered wording, and it binds every sentence in this document.** *A ceiling
this campaign failed to reach is a ceiling this campaign has not tested. Its silence there may
not be read as a pass, as a validation of the ceiling's value, as evidence that the ceiling is
large enough, or as a reason to leave the ceiling alone.* The verdict is **"not assessed at
n = 0 valid records, under these conditions, on this machine"** — never "fine", never "loose",
never "unchanged", and never carried over from another condition or another scenario.

**`SETTLE_CEILING_S` is PR3 and the prediction held.** §7.1 predicted every settle record would
be discarded by rule Z because `_spin_until` evaluates its predicate once before looping and the
settle is *"observed in about a second"*; all 9 came back `spins: 0`. **A zero-spin record is a
non-measurement of the milestone** — it measures one evaluation of a predicate, and that
predicate is the `gz model -p` subprocess of threat 1. The filter is on `spins` and never on
`elapsed_s`, so no subprocess cost entered any margin.

**The `continuous_line` warm line is a pool of two different kinds of wait, and this is stated
rather than glossed.** `_cell_key` splits `BRING_UP_CEILING_S` into exactly two halves — the
cold `what` §7.2 names, and everything else — so the warm bucket for that scenario holds both
the nine cached transform lookups **and** the `L4 to command every belt to a non-zero setpoint
(ADR-0032)` wait, which is neither a cold bring-up nor a transform lookup. It is in the warm
half because the split is binary (the harness's limitation 9). **It cannot affect the cold
headline verdict**, which §7.2 makes the ceiling's verdict, and all of it is zero-spin in any
case, so the cell is NOT ASSESSED either way.

### 3.4 The FIRED cell

**`continuous_line.LEG_CEILING_S` at C4: FIRED, no band.** Rule F: any (scenario, ceiling,
condition) in which that ceiling timed out in any contributing run is reported FIRED with the
run named and the failure text quoted, and receives no band at all.

- Run: **`C4_continuous_line_2`**, verdict `failed`.
- Failure text, quoted from the console:
  `piece 1: STOPPED after 1/10 milestones, waiting on lifted(station_transfer_1:
  cell_a__table_pick__surface) for 420s`
- Surviving records in the cell: **1 of 30** expected legs, `elapsed_s = 0.854`, computing to
  `M = 491.80`. **Published under the FIRED label and no verdict is derived from it.**

**The work-piece never moved.** The scenario's own cycle assertion prints
`work-piece samples: 533, furthest t=1788460726.8s (-0.475, -0.000, 0.625), highest
t=1788460726.8s (-0.475, -0.000, 0.625), last t=1788461146.8s (-0.475, -0.000, 0.625)` — 533
samples over the 420 s leg, with the furthest, the highest and the last sample at **the same
pose to three decimal places**. The station was waiting on `lifted`, which
`continuous_line.py` computes from the sampled height rather than taking it from the arm, and
the height never changed: **the grasp never lifted the piece.** That is what the ceiling fired
on. **This campaign does not attribute it**, and it is one event on one machine.

**Rule F fired exactly once in the campaign.** Deviation 2 records that the harness anticipated
the opposite case and it did not occur.

---

## 4. Q-B — the under-load condition, reported as brackets between measured allocations

**#30's open half.** The 2026-08-29 campaign derived its under-load figures by scaling measured
intervals by a ratio of real-time factors; this campaign **measured at the allocation**, so B1
reports brackets between two measured allocations and **interpolates nothing between them and
extrapolates nothing below C1**.

| ceiling | FULL | C4 | C2 | C1 | B1 |
|---|---|---|---|---|---|
| `bringup.BRING_UP_CEILING_S` | APPROPRIATE (1) | APPROPRIATE (1) | APPROPRIATE (2) | APPROPRIATE (2) | **NOT LOCATED** — not located between 16 and 1 CPU |
| `bringup.DELIVERY_CEILING_S` | INCONCLUSIVE (9) | INCONCLUSIVE (9) | INCONCLUSIVE (18) | INCONCLUSIVE (18) | **OPEN on all four sides** |
| `bringup.SKILL_CEILING_S` | TOO LOOSE (1) | TOO LOOSE (1) | APPROPRIATE (2) | APPROPRIATE (2) | **the TOO LOOSE → APPROPRIATE crossing is bracketed between C4 and C2**; and NOT LOCATED for the APPROPRIATE → TOO TIGHT one |
| `bringup.TRAJECTORY_CEILING_S` | TOO LOOSE (5) | TOO LOOSE (5) | INCONCLUSIVE (10) | APPROPRIATE (10) | **OPEN on the side of C2** |
| `continuous_line.BRING_UP` [cold] | APPROPRIATE (3) | TOO LOOSE (1) | APPROPRIATE (2) | APPROPRIATE (1) | **NOT LOCATED — NON-MONOTONE** |
| `continuous_line.LEG_CEILING_S` | APPROPRIATE (90) | FIRED (1) | APPROPRIATE (33) | APPROPRIATE (30) | **OPEN on the side of C4** |
| `pick_and_place.BRING_UP` [cold] | APPROPRIATE (4) | APPROPRIATE (2) | APPROPRIATE (2) | APPROPRIATE (1) | **NOT LOCATED** — not located between 16 and 1 CPU |
| `pick_and_place.BRING_UP` [warm] | INCONCLUSIVE (4) | INCONCLUSIVE (2) | INCONCLUSIVE (2) | INCONCLUSIVE (1) | **OPEN on all four sides** |
| `pick_and_place.CYCLE_CEILING_S` | APPROPRIATE (4) | APPROPRIATE (2) | APPROPRIATE (2) | APPROPRIATE (1) | **NOT LOCATED** — not located between 16 and 1 CPU |

`pick_and_place.SETTLE_CEILING_S` and `continuous_line.BRING_UP_CEILING_S` [warm] have no B1
line: every cell is NOT ASSESSED and rule N governs.

**"NOT LOCATED" is the registered output and it is never "safe at any allocation".** Three
ceilings were APPROPRIATE at all four allocations tried. That is a statement about four
allocations on one machine and not a clearance.

**One crossing is located: `bringup.SKILL_CEILING_S`, TOO LOOSE → APPROPRIATE between C4 and
C2.** The margin falls monotonically — 19.67, 16.34, 8.95, 3.93 — as the interval it bounds
grows from 6.102 s to 30.506 s. B1's registered branch for this shape makes **two statements**
and neither summarises the other: the crossing is bracketed, and the APPROPRIATE → TOO TIGHT
crossing is NOT LOCATED.

**Four brackets are OPEN, and an open bracket is not a narrower one.** A bracket may not span
a cell that is INCONCLUSIVE, FIRED or NOT ASSESSED, so where `bringup.TRAJECTORY_CEILING_S`
goes TOO LOOSE (C4) → INCONCLUSIVE (C2) → APPROPRIATE (C1), the crossing is somewhere in
C4-to-C1 and **the campaign does not say where**.

**`continuous_line.BRING_UP_CEILING_S` [cold] is NON-MONOTONE and no bracket is read from
it.** The sequence APPROPRIATE / TOO LOOSE / APPROPRIATE / APPROPRIATE at n = 3 / 1 / 2 / 1 is
within sampling variation at these counts, **and this campaign does not distinguish that from a
real non-monotonicity.** The C4 cell reads `M = 10.75` against a band edge at 10 on a single
record of 27.897 s, and the FULL cell reads 9.81 on three records whose maximum is 30.578 s;
the two cells are 2.7 s apart on the quantity that decides them.

**The direction of most of the table is what the design expected, and it is stated as an
observation with its exceptions rather than as a law.** Nine ceilings are assessed at more
than one allocation. In **six** of them the measured maximum grows monotonically as CPU falls
and the margin shrinks with it. **Three do not**: `continuous_line.BRING_UP_CEILING_S`
[cold], whose C4 maximum is 2.7 s **below** its FULL one — the non-monotone case above;
`bringup.TRAJECTORY_CEILING_S`, whose FULL and C4 maxima differ by **1 ms** in that direction;
and `pick_and_place.BRING_UP_CEILING_S` [warm], whose C2 maximum exceeds its C1 one by
**2 ms**, on a family whose whole range is under 0.11 s. The last two are differences the poll
quantum swallows whole, which is why neither ceiling's cells are banded on them. The two
smallest margins
in the campaign are both at C1: `continuous_line.LEG_CEILING_S` at **1.56** and
`pick_and_place.CYCLE_CEILING_S` at **1.66**, each within 0.2 of the TOO TIGHT edge at 1.5 —
**both still APPROPRIATE, and neither is a prediction about anything below C1**, which B1
forbids extrapolating to.

---

## 5. The seven pre-registered predictions

| # | Prediction | Outcome |
|---|---|---|
| **PR1** | at FULL, no assessed margin is TOO TIGHT | **HELD** — 0 TOO TIGHT cells in the campaign, at any allocation |
| **PR2** | at FULL, `bringup.DELIVERY_CEILING_S` and `bringup.TRAJECTORY_CEILING_S` are TOO LOOSE | **SPLIT.** `TRAJECTORY_CEILING_S` **HELD**. `DELIVERY_CEILING_S` is **INCONCLUSIVE** by rule Q — readings TOO LOOSE / no upper bound — so **the prediction is neither held nor refuted there** |
| **PR3** | `SETTLE_CEILING_S` is NOT ASSESSED everywhere, every record discarded by rule Z | **HELD** — 9 zero-spin settle records, 0 assessed cells |
| **PR4** | at C1, `pick_and_place` times out on `CYCLE_CEILING_S` and that cell is FIRED | **REFUTED** — the cycle completed at C1 in **253.400 s** and emitted a record |
| **PR5** | `continuous_line.LEG_CEILING_S` is APPROPRIATE at FULL | **HELD** — `M = 4.47` over 90 legs |
| **PR6** | rule G's mangled count and rule K's are both zero | **HELD** — 0 mangled over all 28 collected runs, 0 clock-disagreeing over the 22 admitted |
| **PR7** | `bringup.BRING_UP_CEILING_S` yields exactly one contributing record per run after rule A | **HELD** |

**PR4 is a refuted prediction and is reported as a result.** §7.6 based it on the 2026-08-29
campaign's scaled arithmetic, which predicted `pick_and_place` timeouts below about 1.2 cores.
At 1 CPU on this machine the cycle finished with `M = 1.66`. **Rule H forbids reading that as a
correction to the earlier campaign** — different machine, architecture, geometry and world —
and the honest statement is the absolute one: **on this machine, on the shipped configuration,
the cycle completed at a one-CPU allocation.**

**PR2 is the prediction this campaign was least able to answer, and the reason was registered
before it ran.** §7.1 named `DELIVERY_CEILING_S` as the verdict the poll quantum could move,
and it moved it all the way to no verdict.

**Two of the five held predictions were close to arithmetic before the campaign ran**, and
saying so is what keeps the tally honest: PR3 follows from `_spin_until` evaluating its
predicate before looping against a settle observed in about a second, and PR7 follows from
`unittest`'s alphabetical ordering. **PR5 and PR4 are the two that could have gone either
way**, and one of them did.

---

## 6. Deviations, numbered, applied to data already collected

`criteria.md` was frozen at `f895733` and **no threshold, band, rule or sample-size figure in
it changed after the first trial ran.** V9 requires a threshold discovered to be wrong to be
**applied literally and recorded as wrong**, and that is what happened in every case below.
**None of them moved a threshold.**

Deviations 1-3 below correspond to the three the analyser prints on every run (`DEVIATIONS`
block, `analyse.py`), restated here with what they cost; 4-7 are recorded for the first time in
this document.

**Deviation 1 — V2's I7 read-back is unreliable on `bringup`, and `raw/` cannot diagnose it.**
Five runs' description read-back returned 22 characters (§2.1) while the world read in the
**same container** succeeded. `common.running_configuration` stores `description_chars`,
`hull_collision_refs` and a boolean — **not the failing text** — and `common._run` returns
either the subprocess's stdout or `<rc=N> {stderr}`, so **which of those two shapes the 22
characters had is unrecoverable from the committed raw.** The harness README's twelve-item
"cannot do" list does not name this. **Cost: 5 of 11 `bringup` runs, four of them at FULL and
one at C4**, which is why every `bringup` cell at FULL and at C4 rests on a single run. **V2 was applied literally and
the runs are discarded, not repaired**; V8 forbids topping them up. What would settle it is
storing the read-back's text, which is a change to a frozen harness and therefore a change for
the next campaign.

**Deviation 2 — the harness's own deviation 2 did not bite, and its opposite did.** It records
that rule F is applied literally, so `LEG_CEILING_S` would be reported FIRED even if it timed
out on one of the two waits §2.3 excludes from its margin — the spawn settle or the removal.
**The one firing observed is a genuine leg** (`piece 1: …`, §3.4), so the FIRED label here is
unqualified and the anticipated weakening never arose. Recorded because a reader of the
analyser's print will meet the deviation and should know it did not apply to this data.

**Deviation 3 — V2 is worded for a reading that disagrees, not for a reading never taken.**
`C4_continuous_line_1` never emitted a `CITE_TIMING` line, so the I7 gate never opened and
`v2_ok` is **`None`** rather than `False`. V2's text discards *"a run that does not read
`convex_hull` and the throttle"*; a run that read nothing is not literally that. **It was
discarded**, which is the safe direction and consistent with §10's fail-closed construction,
and it would have been discarded by V4 regardless — 6 of 6 expected triples absent against a
threshold of half. **Recorded rather than smoothed over because the rule as worded does not
cover the case that occurred.**

**Deviation 4 — rule Q's no-upper-bound branch decides 8 of the 36 assessed cells, and that is
a structural result rather than an accident.** Two whole ceiling families measure intervals
shorter than the poll that observes them (§3.2). **The campaign's instrument cannot resolve a
sub-100-millisecond interval sampled at 0.5 s**, and the consequence is that the ceiling PR2
predicted TOO LOOSE has **no verdict**. This is registered behaviour, not a failure —
§7.1 wrote the branch and §7.1's own commentary predicted the cell it would land on — and it is
numbered here because a reader comparing the printed lower bounds with the verdict column will
otherwise read the omission as an oversight.

**Deviation 5 — V7 reads pre-run load only, and post-run load exceeded its flag in 11 of 28
runs.** V7 flags a run whose **pre-run** one-minute load exceeds 4.0 on 16 cores and discards
none. **No run was flagged**: the highest pre-run reading in the campaign is **2.894**
(`FULL_continuous_line_1`) and the lowest **0.047**. The **post-run** readings, which V7 does
not consult, exceed 4.0 in **11 runs**, the largest being **8.353** after
`FULL_pick_and_place_1`; **8 of those 11 are admitted runs contributing to margins**. **V7 was
applied literally and correctly** — a load threshold chosen after seeing the data is a
threshold chosen by the data — and the post-run figure is largely the load the run itself
created, measured before the machine had settled. It is recorded because a reader comparing the
two columns in `raw/*.json` will ask, and because **"no run was flagged" is a statement about
the pre-run reading and not about the machine's state during the run.**

**Deviation 6 — an operator action, declared.** To satisfy both the README's ordering and V11's
one-build rule, the operator invoked `run_campaign.sh __PREFLIGHT_BUILD_ONLY__` — a label
matching no schedule entry — so that provenance and the single `./scripts/build` were recorded
and **zero trials ran**. When the real campaign started 3 min 51 s later, `build_once`'s own
guard refused a second build (`build_skipped=provenance already carries a build block`).
**Consequence: `raw/provenance.txt` carries two environment blocks and one build block**
(`Summary: 23 packages finished [2.93s]`, `build_exit=0`). **Nothing was edited**, no threshold
moved, and V11 holds: one build, before the first trial, and no rebuild mid-campaign.

**Deviation 7 — two admitted runs whose scenario failed contributed records to margins, and
rule X2's check confirmed it changed nothing.** §7.1 admits non-`CYCLE` records from failed runs on the ground that such a record is emitted
only when its own wait succeeded, and requires the margins to be computed twice to prove it.
The two failed `continuous_line` runs contributed 14 and 15 records. **Rule X2 found no cell
whose band differs between the two readings**, so no cell was made INCONCLUSIVE by it, and rule
X dropped **0** `CYCLE_CEILING_S` records because all nine `pick_and_place` runs passed.
Numbered here because it is a registered check that could have produced INCONCLUSIVE cells and
did not, and a silent pass is exactly the shape this directory reports rather than assumes.

**One thing that is not a deviation.** `analyse.py` was written before the first campaign trial
and re-runs to byte-identical output over the committed `raw/` — verified for this document by
running it twice and diffing. A rule implemented after the data has been seen is a rule chosen
by the data; this one was not.

---

## 7. A bring-up failure of the process `docs/open-work.md` #55 names, with a different error

**`C4_continuous_line_1` failed during bring-up and produced no campaign data.** It is
discarded (§2.1) and contributes to no figure. It is reported here because of what it is.

**What happened, from `raw/C4_continuous_line_1.log`.**

```
[planning_scene_loader.py-24] [INFO] [1788455384.335711873] [cite.cell_a.arm_1.load_planning_scene_arm_1]: loaded 12 collision object(s) for zone 'cell_a' in cite_world
[INFO] [planning_scene_loader.py-24]: process has finished cleanly [pid 691]
[INFO] [planning_scene_loader.py-25]: process started with pid [706]
[planning_scene_loader.py-25] [ERROR] [1788455509.027344439] [cite.cell_a.arm_2.load_planning_scene_arm_2]: 'apply_planning_scene' never returned a result
[ERROR] [planning_scene_loader.py-25]: process has died [pid 706, exit code 1, ...]
[INFO] [launch.user]: BRING-UP FAILED before the planning scene for arm_3: the previous step exited 1.
[INFO] [launch]: process[planning_scene_loader.py-25] was required: shutting down launched system
```

`arm_1` had already loaded its 12 collision objects. `arm_3` was skipped because the previous
step exited 1. The node is `required`, so the launch shut down, **the run's tests never
started**, and the scenario reported `failed — 1 cycle assertion(s) failed` with
`Exception: Launch stopped before the active tests finished.`

**This is the process #55 names and a textually different failure.** #55 records
`planning_scene_loader.py` for `arm_1` exiting 1 with *"move_group refused the planning scene
diff for zone 'cell_a'"*, 14 ms after that `move_group` logged *"Unknown frame: cite_world"*.
Here it is `arm_2`, and the message is *"'apply_planning_scene' never returned a result"*.
Those are **two different branches of the same function**, twelve lines apart in
`workspace/src/cite_facility/cite_facility/planning_scene_loader.py`: #55's is
`response.success == False`, a refusal that **returned**; this one is `future.result() is
None` after `rclpy.spin_until_future_complete(..., timeout_sec=SERVICE_DEADLINE_S)` with
`SERVICE_DEADLINE_S = 120.0`, a call that **never returned at all**. The elapsed time between
`arm_1`'s success and `arm_2`'s error is **124.7 s**, consistent with that deadline expiring.

**Correction, 2026-09-03, by a reader who is not the campaign operator: the two branches are
five lines apart, not twelve.** In the file this campaign measured — byte-identical at
`c38a42c`, at the campaign's `HEAD = 98fbbfc`, at `bbd40cf` and on `main`, checked by
`md5sum` — the two `self.get_logger().error(...)` calls are at **lines 110 and 115**, and the
`if` statements that reach them at 108 and 113: `if response is None:` immediately precedes
`if not response.success:`, with nothing between them but the first branch's message and its
`return 1`. **The claim that the two are branches of one function is unaffected and is what
the paragraph rests on**; only the distance was wrong, and the branches are nearer each other
than it said, not further. Everything else in this section was re-checked at the same time and
holds: the console quotation is `raw/C4_continuous_line_1.log:1098-1100`, `SERVICE_DEADLINE_S`
is `120.0` at line 62, and a line-break-insensitive grep for #55's three strings across all
**28** captured consoles returns **0** for each.

**A grep for #55's own strings across all 28 campaign consoles returns nothing** —
`Unknown frame: cite_world`, `Tf has two or more unconnected trees`, and #55's
`refused the planning scene diff` are absent from every log in `raw/`.

**So this is recorded as a related but textually distinct failure of the same node, and not as
a third observation of #55. The attribution is left open.** It differs from #55 in the arm, in
the branch, in the error text, and in the configuration: **#55 was a paired bring-up and this
is a solo plant run**, so #55's own reasoning — *"the counterpart brought the identical
configuration up cleanly at the same moment"* — has no counterpart here to lean on. One event,
on one machine, with nothing registered in advance.

**The console is captured, at `raw/C4_continuous_line_1.log`, with the run document beside
it.** That is what #37's standing instruction asks for — *"if it recurs, capture the log before
restarting"* — and what #37's own single event did not get, having been *"restarted rather than
analysed, so it is one event with no log kept"*. #55's occurrence does carry a console, in a
different campaign directory. **This one was neither restarted nor re-run**: V8 governs, the
run is discarded with its evidence intact, and the C4 `continuous_line` cell stands at the n it
reached.

---

## 8. The machine, the load, and the validity rules

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM. `Linux-7.0.0-30-generic-x86_64-with-glibc2.39`, read per run |
| Docker | **29.7.2** (build a7dcaa6) |
| Container image | **`cite-digital-twin:dev`**, image ID `3a41d4e431b0`, recorded on all 28 runs and identical on every one |
| Isolation | compose project **`cite-digital-twin-3319196271`**, **`ROS_DOMAIN_ID` 43**, both derived from this checkout by `scripts/_lib.sh` rather than typed |
| Allocation | I4 from **inside** the container (`/sys/fs/cgroup/cpu.max`) and **outside** it (`.HostConfig.NanoCpus`). Never `nproc`, never `.HostConfig.CpuQuota` |
| Build | one `./scripts/build`, `Summary: 23 packages finished`, before the first trial (V11, deviation 6) |

**This is one machine.** Every ceiling here is a **wall-clock** ceiling, so every margin is a
fact about this host at this moment, and about nothing else. **Nothing here says anything about
hardware** — no physical arm exists in this measurement — and no figure may be read as a P2
result. **Nothing here is a real-time-factor or capacity claim** either; those are settled in
[`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
and
[`2026-09-01-capacity-on-shipped-main/`](../2026-09-01-capacity-on-shipped-main/ANALYSIS.md),
which stay frozen and are cited rather than copied (P1).

**Load, at both ends of every run, read from `/proc/loadavg`** — which on this host is the
host's own. `criteria.md` §9 demonstrates that rather than assuming it: two readings taken
seconds apart from inside and outside a container of this image agree to the hundredth, because
`/proc/loadavg` is not namespaced on native Linux and there is no `lxcfs` in the way.

| | pre-run (V7's reading) | post-run |
|---|---|---|
| minimum | **0.047** (`C1_continuous_line_1`) | 0.134 (`C2_pick_and_place_1`) |
| maximum | **2.894** (`FULL_continuous_line_1`) | **8.353** (`FULL_pick_and_place_1`) |
| above V7's 4.0 flag | **0 of 28** | **11 of 28** |

**No run was flagged and no run was excluded for load**, which is V7 applied literally.
Deviation 5 records the asymmetry rather than smoothing it.

**The validity rules, and what each one did.**

- **V1 — the load-bearing rule.** `v1_clean` true on **all 28** runs, computed at both ends and
  travelling on the record; **0** disagreements, **0** mid-run `HEAD` moves. The five watched
  paths — `model/`, `workspace/src/`, `tools/`, `tests/`, `scripts/` — were clean against
  `c38a42c` throughout. **Nothing in the tree was edited to make anything measurable.**
- **V2** — discarded 6. §2.1.
- **V3** — the scenario's own verdict line recorded per run and attached to every record; 22
  admitted runs, **20 `passed` and 2 `failed`**. Read from `scripts/scenario`'s verdict string,
  never from an exit code.
- **V4** — one discard (`C4_continuous_line_1`, 6 of 6 absent). Every other run was within the
  half-of-expected-triples threshold.
- **V5** — **0 `gz sim` survivors** at the start of every one of the 28 runs.
- **V6** — every loaded run's limit was applied **3.8 s** into the container's life, against a
  10 s ceiling, and held to the last live reading. The FULL runs apply no limit and V6 says so
  rather than passing them silently.
- **V7** — see above.
- **V8** — n is what it was. **No condition was topped up to replace a discard**, which is why
  FULL `bringup` contributes one run out of five.
- **V9** — no threshold moved. §6.
- **V10 — the mechanism's reading, and not the operator's declaration.** §10 requires the
  campaign operator to state in this document whether one-writer-at-a-time held. **This
  write-up was not produced by the campaign operator** — it is written from the committed raw
  and the analyser's print — and it does not make that declaration on their behalf. What the
  records show: `v1_clean` true on all 28 runs with no disagreement between the two readings
  and no mid-run `HEAD` move, and every `git status --porcelain` captured during the campaign,
  56 readings over 28 runs, lists **only untracked files under this campaign's own directory**
  and nothing else in the tree. That is consistent with one writer; it is evidence and not a
  declaration.

  **The declaration, made by the campaign operator on 2026-09-03, after this write-up was
  published and added to it here rather than folded into the paragraph above.** It is theirs,
  and it is quoted rather than paraphrased:

  > Only the campaign runner wrote to this checkout for the whole campaign. No watched path
  > moved — `git diff --stat c38a42c..HEAD -- model/ workspace/src/ tools/ tests/ scripts/`
  > was empty at the end and the working tree was clean; four commits were made, all
  > `raw/`-only; and no containers or `gz sim` processes survived.

  **V10 is therefore satisfied**, and the paragraph above stays as it was written: it is the
  mechanism's evidence, the declaration is the operator's, and the two are different things.
  The declaration's checkable clauses were re-derived on 2026-09-03 by a reader who is not the
  operator and hold: the watched-path diff against `c38a42c` is empty at `bbd40cf`, the working
  tree is clean, and the four campaign commits — `0829119`, `225c025`, `cab1e56`, `807dd2e` —
  touch **only** files under this campaign's `raw/`. The surviving-process clause is the
  operator's own observation and is not reproducible after the fact.
- **V11** — one build. Deviation 6.

---

## 9. What this campaign does not establish

Registered in `criteria.md` §8 before the first trial, and none of it moved.

- **The upper tail of any interval.** A wait that times out emits no record, so **every margin
  here is computed over the completing half of the distribution**, and the slowest instance
  reported is the slowest *that finished*. The bias is one-sided and runs **toward TOO LOOSE**.
  Rule F is the only thing that keeps a run in which a ceiling demonstrably fired from being
  banded at all, and it fired once.
- **The sixth `DELIVERY_CEILING_S` wait.** Uninstrumented deliberately; the margin is a
  statement about five (§3.2).
- **Anything about either of #30's two levers.** The throttle and the hulls are folded in by
  **measuring the shipped configuration**, not by comparing it with an unshipped one, and
  **nothing here is attributed to either.**
- **The margin on a four-, two- or one-core machine.** `docker update --cpus` sets a CFS quota
  on the same sixteen cores. It is the right variable for Q-B — contention takes CPU time away
  in the same currency — and **it is not a smaller machine.** Inherited verbatim from the
  2026-08-29 campaign rather than rediscovered.
- **Anything below C1.** B1 extrapolates nothing.
- **Whether the 2026-08-29 margins were right.** Rule H.
- **Determinism.** `CITE_PHYSICS_SEED` reaches `gz sim --seed` only, which does not seed the
  physics solver; every figure here is a distribution over repeats.
- **A pass rate.** The count of scenario passes is not a result of this campaign, and the
  `continuous_line` CI tally in CLAUDE.md §2 is a different body of evidence on different
  machines that **nothing here extends.**
- **Teardown.** Not measured; the teardown campaign's inconclusive is not disturbed.
- **Any machine but the one in §8, any image but the one recorded there, and any CI runner.**
- **Why the I7 read-back failed** (deviation 1), **why `C4_continuous_line_2`'s grasp never
  lifted the piece** (§3.4), and **why `arm_2`'s `apply_planning_scene` never returned** (§7).
  Three separate things. **None of the three is attributed**, and each rests on one event —
  or on five, in the read-back's case — with nothing registered in advance.

---

## 10. What this campaign does not decide

**§0, and it is the first thing written in `criteria.md` for a reason.**

- **No threshold, ceiling, tolerance or band anywhere in the tree changes because this campaign
  ran.** Not one of the nine `*_CEILING_S` declarations is edited, and **none may be widened to
  absorb anything found here.**
- **This document proposes no replacement value for any ceiling.** Where a ceiling reads TOO
  LOOSE, it says so and stops. Where a cell is INCONCLUSIVE, NOT ASSESSED or FIRED, it says
  which rule produced that and stops.
- **Changing a ceiling is a separate decision and is the project owner's.** `criteria.md` was
  written before any number existed precisely so that no number produced by it could be read as
  an argument for a particular new value.
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/` or `scripts/` was edited**, and
  V1 would have discarded the affected runs if it had been.
- **A null is not a pass.** Eight cells are NOT ASSESSED and nine are INCONCLUSIVE. **Rule N
  binds every sentence about them**: not tested is not fine, not loose, not unchanged, and
  never carried over from another condition or another scenario.

**What the campaign hands over, and to whom.**

| finding | what it bears on |
|---|---|
| `bringup.TRAJECTORY_CEILING_S` TOO LOOSE at FULL and C4 (§3.1) | #30's "may now be loose", answered as an absolute verdict on the shipped configuration |
| `bringup.SKILL_CEILING_S` TOO LOOSE at FULL and C4, APPROPRIATE at C2 and C1, crossing bracketed between C4 and C2 (§4) | the same, plus the only located crossing in the campaign |
| eight cells decided by rule Q's no-upper-bound branch (§3.2) | the instrument, not the ceilings: two ceiling families cannot be assessed at a 0.5 s poll |
| eight cells NOT ASSESSED (§3.3) | ceilings this campaign has not tested |
| `continuous_line.LEG_CEILING_S` FIRED at C4 (§3.4) | a leg that stopped at `lifted`, reported and not attributed |
| the I7 read-back failure (deviation 1) | the next campaign's harness, which is not this one |

---

## 11. Reproduction

`harness/README.md` carries every command. The whole campaign is:

```sh
docs/measurements/2026-09-02-scenario-ceilings/harness/run_campaign.sh
```

and every figure in this document comes from:

```sh
python3 docs/measurements/2026-09-02-scenario-ceilings/harness/analyse.py
```

which applies §7's rules to `raw/` and **prints every rule whether or not it fired**, together
with the deviation block. It is **1034 lines** in this checkout and re-runs to byte-identical
output over the committed raw. **Redirect it to a file and read that**: piping it through `head`
truncates it silently and still exits 0 through `tee`, which produced a plausible-looking 143
lines during this campaign.

**What in this document did not come from that print**, each read from `raw/` or from the tree
at `c38a42c` and named where it is used: the campaign's wall-clock window and the run durations
(§1), the run order (§1), the per-run load figures (§8 and deviation 5), the I7 field values and
gate wait times (§2.1), the `git status --porcelain` readings (§8), the console quotations
(§3.4 and §7), and the `planning_scene_loader.py` source reading (§7). Every verdict, margin,
count and rule outcome is the print's.

**Figures stay in this directory.** Nothing here is copied into `CLAUDE.md`,
`docs/open-work.md`, any ADR, any layer document or any comment in `tests/scenarios/` (P1).
**Cite the directory.**
