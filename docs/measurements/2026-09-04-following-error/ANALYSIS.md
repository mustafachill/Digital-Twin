# The path tolerance stayed quiet on three arms, fired twice on the fourth, and the fastest motion the L3 contract permits misses ADR-0036's own line

**Verdict, in this campaign's own terms.** Every one is `criteria.md` §7's registered rule applied
by `harness/analyse.py` to `raw/`, and every one is stated **per arm** — rule T: the arms are not
each other's evidence, and CRUISE staying quiet says nothing about FAST.

| Quantity | Verdict | In one line |
|---|---|---|
| **LIVE1 — measured quiet, or measured nothing** | **ADMISSIBLE on all four arms** | **0 instrument losses out of 126 trials**, against rule L's 20 % ceiling, on every arm. L-iii is satisfied on every trial and **nothing reads 0.000000**: the per-arm minimum of `max_j │error_j│` is 0.0188 / 0.0809 / 0.0188 / 0.0188 rad against L-iii's 0.001 rad. **This is measured quiet and measured firing, not measured nothing** — the distinction the whole campaign was built around. |
| **QUIET1 — did the path tolerance fire** | **QUIET on CRUISE, FAST and CARRY; FIRED on CONC** | **Two trials**, both `PATH_TOLERANCE_VIOLATED`, both attributed by **I3(c)** to **`arm_1_joint_trajectory_controller` — arm_1's own controller**, on **`arm_1_joint3`** in both. **Zero unattributed I3(b) events anywhere in the campaign**, so the count is arm_1's on the instrument's own naming and **not by the conservative "possibly arm_1's" fallback**. |
| **BAND1 — how far below ADR-0036's line the healthy peak sits** | **FAR on CRUISE, CARRY and CONC; SHORT on FAST** | FAST's healthy peak is **0.115972442 rad** against ADR-0036's own **0.100 rad** line — **+15.97 %**, a margin of 0.015972442 rad. **The uncomfortable outcome, registered as PRED3 before any trial, landed.** The other three sit at 0.018878554, 0.018872962 and 0.026154394 rad. |
| **CONC1 — does concurrent load move arm_1's distribution** | **INDISTINGUISHABLE** | The two medians of the trial-peak are **bit-identical at 0.018848806 rad**; **│difference│ = exactly 0.0 rad** against the 0.005 rad minimum interesting size. **No guard suppressed it**: rule R did not bind, and V6 was **evaluable on both arms** and did not bind. n = 7 loaded CONC against n = 36 CRUISE. |
| **GOAL1 — the goal tolerance and the settle** | **CLEAR ×4, and uninformative exactly as registered** | Every settle on every arm is **0.0 s**, at or below one sample interval (0.006667 s), on 124 of 124 healthy admissible trials. **§7.3 registered before any trial that a CLEAR at that resolution evidences nothing** — not that the goal tolerance behaves, not that the goal window is comfortable, not that anything was exercised. |
| **X1 — did the campaign stress the tolerance at all** | **STRESSED on FAST and on CONC; NOT STRESSED on CRUISE and CARRY** | FAST reached **1.932841238 rad/s** and CONC **2.14097295 rad/s** against rule X's derived stress speed of **1.6667 rad/s**. CONC reaching it **falsifies §7.4's own "by construction" clause** — deviation 16. CRUISE and CARRY fall to **rule N**. |
| **Rule D — the arithmetic against the measurement** | **124 of 126 agree, to five significant figures** | The two disagreements are **the two firing trials**, at ratios **8.17** and **9.82**. **Neither is attributed** — rule D forbids it, and nothing was re-run. |

**What that does to [`docs/open-work.md`](../../open-work.md) #20, stated plainly and
conservatively.** #20's **healthy-run half** is answered for the two arms rule X calls STRESSED
and for those arms only: under `gz_ros2_control` the reported following error is what §2.2's
command law says it is, and at the fastest motion the L3 contract permits it lands **above**
ADR-0036's own order-of-magnitude line. **For CRUISE and CARRY rule N's own words apply and this
write-up states them: their quietness is a statement about the speeds they ran at and about
nothing faster, and their silence may not be read as agreement with §2.2's arithmetic, as a
clearance of the tolerance, or as evidence the detector behaves.**

**#20's firing half is untouched and this document does not narrow it by one millimetre.** The
two events on CONC are **not** the firing half. That half needs a **Gazebo-side mechanism that
obstructs an arm link** while `gz_ros2_control` remains the loaded hardware component, and
`criteria.md` §1.1 registers it as structurally out of scope. **These two events were not
induced.** The campaign did not make the tolerance fire, has no mechanism for making it fire, and
**nothing here shows the detector *can* detect an obstruction under this backend.** Nobody may
read #20's firing half as closed, half-closed, or narrowed.

- **Campaign:** `docs/measurements/2026-09-04-following-error/`
- **Branch under measurement:** `feat/close-phase-debts`. **BASE_COMMIT `c38a42c`**, and the code
  under test never moved: V1 dropped **no rows on any block** (`rows dropped for a missing or
  false flag: {}`), and V10 reports `disagreed_mid_block` **false on all three blocks** — no edit
  to `model/`, `workspace/src/`, `tools/`, `tests/`, `scripts/`, `assets/` or `external/` landed
  inside a block. **The one-writer rule held.** `head_moved_mid_block` is also false on all three,
  which V1 permits either way because it does not watch `docs/`.
- **`criteria.md` sha256:** `923a4d1e1c9fd578b5294f8f99d18c700fc3626f63ae6c46439c5e50db5193c6` —
  **one distinct value recorded across all three blocks, and it agrees with the file on disk**
  (V9). **`criteria.md` and `harness/` are frozen from `601a062`**: `git log 601a062..HEAD --
  criteria.md harness/` is **empty**. The three data commits are `63a6295` (B1), `62231a1` (B2)
  and `d687d44` (B3).
- **The record that asked for it:**
  [ADR-0036](../../adr/0036-execution-side-trajectory-tolerances.md)'s "revisit" bullet, and
  [`docs/open-work.md`](../../open-work.md) **#20**. **Neither moves here.** ADR-0036 is not
  promoted, its status is untouched, and no tolerance is proposed. See §12 and §13.
- **The campaigns this one does not replace and does not edit:**
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md),
  [`2026-09-02-scenario-ceilings/`](../2026-09-02-scenario-ceilings/ANALYSIS.md) and
  [`2026-09-03-stall-band-flip/`](../2026-09-03-stall-band-flip/ANALYSIS.md). All stay frozen,
  their figures are cited and never copied (P1), and **rule H forbids differencing any measured
  figure of theirs against anything here.**
- **This document was written from the committed `raw/` and from `harness/analyse.py`'s print, by
  someone who did not run the campaign.** That is deliberate — the write-up is built from the
  record rather than from the runner's memory.

---

## 1. What was run

| block | trials | admitted | V7 at start | V7 at end | I9 clock ratio |
|---|---|---|---|---|---|
| **B1** | 42 | **42** | not flagged | **flagged** | 0.9072591897806861 |
| **B2** | 42 | **42** | not flagged | **flagged** | 0.9100885518867144 |
| **B3** | 42 | **42** | **flagged** | **flagged** | 0.9033282422599775 |

**126 trials collected, 126 admitted, across 3 blocks.** `discarded blocks: {}`; `dropped rows:
{}`; `V14 exclusions: {}`. **No block was discarded, no row was dropped, and no trial was excluded
by any validity rule.** Every trial is one L3 `MoveTo`, `Pick` or `Place` goal against the
**shipped** cell — shipped collision geometry, shipped controller configuration, shipped world,
shipped `simulation.launch.py` — with the joint trajectory controller's own `~/controller_state`
recorded while it ran. `raw/shakedown/` is excluded from every figure here by three independent
refusals in the analyser (deviation 3), and the print confirms `Shakedown rows refused: none
found` at the top level it globs.

**The four arms, and their trial counts after rule L.**

| arm | what it is | n admitted | n healthy | goals |
|---|---|---|---|---|
| **CRUISE** | default scaling 0.35/0.35, arm_1 alone | 36 | **36** | `home → above pick → above place → home` |
| **FAST** | **full scaling 1.0/1.0**, arm_1 alone | 36 | **36** | the same set |
| **CARRY** | default scaling, a real work-piece carried | 18 | **18** | `Pick` then `Place` |
| **CONC** | default scaling, **arms 2 and 3 shuttling concurrently** | 36 | **34** | the same set as CRUISE, which is its control |

The two CONC trials that are not healthy are **the two firing trials** (§3). Per `criteria.md`
§5.3 they are **never excluded** — they are counted under `tolerance_event` and are the campaign's
headline, not a filtered-away nuisance.

**The admission gates, all of which passed on all three blocks.** V2 read **13 hull collision
references** off the description that actually ran. **V3 asserted `gz_ros2_control/GazeboSimSystem`
off the description the running node published, with no fixture and no mock plugin in it** — which
is the gate that separates this campaign from ADR-0036's launch test, where mock hardware mirrors
commands into states and produces a following error of exactly zero. V4 confirmed the
`controller_state` subscription **matched and received before the block's first goal**, with the
publisher's resolved endpoint QoS recorded per block as `RELIABLE` / `TRANSIENT_LOCAL` /
`AUTOMATIC`. V12 reached **22 Gazebo topics per block** through `cite_bringup.gz`, which is what
makes the partition a fact rather than an assumption — an unpartitioned `gz topic -l` reaches no
world and **exits 0**. V13 records the cell announcing readiness as an **event**, with the longest
server wait being `move_to` at 3.56 s on B1. V11 records **one build**, exit 0, before the first
trial.

**Wall clock: 28 min 29 s**, from the first campaign environment record (`recorded_at
2026-09-04T18:16:04Z`, B1) to the last block seal (`sealed_at 2026-09-04T18:44:33Z`, B3). The
three blocks' own measured spans sum to **1233.58 s (20 min 34 s)**; the remainder is bring-up,
teardown and the 30 s quiesces. **V7 fired on all three blocks** — deviation 17.

---

## 2. LIVE1 — this is measured quiet, not measured nothing

**`criteria.md` §7.1 calls this the campaign's central hazard**, and it is the reason the verdict
table states LIVE1 before it states QUIET1 on every arm. A subscriber that never matched, a topic
that does not exist, a QoS mismatch, a controller that never activated and a rig that quietly ran
on mock hardware **all produce the same empty or zero set**, and every one of them reads as *"the
tolerance stayed quiet"*.

| arm | LIVE1 | instrument losses | window samples min/median/max | achieved rate /simulated s (min/median/max) | `max_j │error_j│` min/max |
|---|---|---|---|---|---|
| **CRUISE** | **ADMISSIBLE** 36/36 | **0** (0.0 %) | 692 / 726.5 / 1151 | 142.98136646 / 143.054472126 / 143.063882572 | 0.018844203 / 0.018878554 |
| **FAST** | **ADMISSIBLE** 36/36 | **0** (0.0 %) | 205 / 212.0 / 288 | 143.354902937 / 143.5349369105 / 143.557422969 | 0.080889064 / 0.115972442 |
| **CARRY** | **ADMISSIBLE** 18/18 | **0** (0.0 %) | 1889 / 1907.5 / 2368 | 142.91749653 / 142.93207823950002 / 142.932808717 | 0.018844173 / 0.018872962 |
| **CONC** | **ADMISSIBLE** 36/36 | **0** (0.0 %) | 167 / 726.5 / 1151 | 142.98136646 / 143.054472126 / 143.717728055 | 0.018844203 / **1.150903069** |

**Zero instrument losses on every arm, against rule L's 20 % ceiling**, by every one of L's four
clauses — the loss count by cause is `none` on all four arms. Every window clears L-i's 100-sample
floor by a wide margin, and every achieved rate clears L-ii's 20/s floor by roughly a factor of
seven.

**L-iii is the clause that matters and it is satisfied on every trial.** L-iii requires at least
one sample in the trial with `max_j │error_j│ ≥ 0.001 rad`, and it exists precisely because mock
hardware produces **exactly 0.000000** and so does a subscription that received nothing. The
**per-arm minimum** of that quantity is 0.018844203, 0.080889064, 0.018844173 and 0.018844203 rad
— every one between **18 and 81 times** L-iii's floor, on the **worst** trial of each arm.
**Nothing anywhere in this campaign reads 0.000000.**

**So the quiet on CRUISE, FAST and CARRY is a measured quiet.** The instrument was demonstrably
live on every single trial that produced it, and the firing on CONC is a measured firing on the
same instrument. That is the distinction the campaign was built around, and it is the one thing
here that could not have been established by running the cell and seeing nothing.

**V5's second clause** compared the peak sample's feedback against the nearest independent
`/joint_states` reading on **all 126 trials**. The largest disagreement anywhere is
**4.98 × 10⁻¹⁰ rad**, which is double-precision noise; the clause reports and excludes nothing.

---

## 3. QUIET1 — three arms quiet, and two firings on CONC

> **Rule G.** Every figure in this section is a property of **`gz_ros2_control` 1.2.19's command
> conversion**, at this gain, this controller-manager rate, this world's 1 ms step and this host,
> and of **nothing else**. It is not a property of the arm — the lag is the plugin's, not
> UFACTORY's. **A quiet path tolerance here is not evidence that it stays quiet on hardware and
> not evidence that it fires there either**, and the word *validated* is not used about the
> tolerance on either backend.

**CRUISE, FAST and CARRY: QUIET.** Zero trials produced a tolerance event on **any** of I3's three
readings — not the L3 result (I3a), not the controller's `tolerances` log line (I3b), not the
discriminating abort lines (I3c). LIVE1 is ADMISSIBLE for each, so the verdict is QUIET rather
than NOT ADMISSIBLE.

**CONC: FIRED.** Two trials, and here is the whole of what the record says about them.

| | firing 1 | firing 2 |
|---|---|---|
| block / trial / cycle / goal | **B1**, trial **39**, cycle 3, `home` | **B2**, trial **39**, cycle 3, `home` |
| I3(a) — the L3 result | status **6** (ABORTED), `ResultCode` **10** = `MOTION_INTERRUPTED` | status **6**, `ResultCode` **10** |
| I3(a) detail | *"the arm stopped part-way along the commanded trajectory and is holding position; it is neither at the start nor at the goal, and nothing on this stack reports why (MoveIt error code -4)"* | identical |
| I3(b) — the shared `tolerances` logger | **1** event, joint index **2** (`arm_1_joint3`), **0 unattributed** | **1** event, joint index **2**, **0 unattributed** |
| I3(c) — the discriminating lines | **1 path abort**; MoveIt abort from **`arm_1_joint_trajectory_controller`**, code **`PATH_TOLERANCE_VIOLATED`** | identical |
| load arms in the same segment | arm_3 (joints 0, 2, 3) and arm_2 (joint 4) also violated | **none** |

**The attribution is the instrument's own naming, not the conservative fallback.** I3(b)'s line
names no arm — every controller manager in this cell lives inside the `gz` process and shares one
`tolerances` logger — so an I3(b) event is attributed by the controller warning that follows it
within eight lines, and an event that window cannot attribute is recorded **UNATTRIBUTED** and
treated as *possibly* arm_1's. **There are zero unattributed I3(b) events anywhere in this
campaign.** Both firings are attributed positively, by I3(c)'s own lines naming
`arm_1_joint_trajectory_controller`. Neither rests on the fallback, and the verdict is **FIRED**
rather than **FIRED (unassigned)**.

**Rule L does not suppress the event, and both readings of that are recoverable.** Deviation 10
applies reading A — §5.3's capitalised sentence that such a trial is never excluded — and the
print states `LIVE1 admissible = True` beside the verdict, so the question is moot here in any
case: CONC's LIVE1 is ADMISSIBLE with zero losses, and no reading of rule L touches this firing.

### 3.1 Counts, not causes — and what B3 did

**Two events across three blocks, not one per block.** They occurred in B1 and B2. **B3 produced
zero events on all three of I3's readings at the same schedule slot that fired in B1 and B2**: its
trial 39, CONC, cycle 3, the `home` goal, records `i3a_status = 4` (SUCCEEDED), `i3a_result_code =
0`, `i3b_tolerance_events = 0`, `i3b_unattributed = 0`, `i3c_path_aborts = 0`,
`i3c_moveit_aborts = []`, and is **healthy**. Two of three blocks fired at that slot and one did
not.

**This campaign does not attribute the firings, and does not attribute their absence in B3.**
Neither is a rate: three bring-ups, one machine, one image, one commit, nothing registered in
advance about how often the slot would fire. **What the two firings are** is the observation that
under this backend the reported following error is not bounded by §2.2's law on every trial — which
is rule D's finding (§8) and is stated there, not resolved here.

### 3.2 Rule T — the load arms' own violations, which are not findings about arm_1

**Three trials carried a tolerance event belonging to a load arm inside arm_1's log segment**, and
they are **reported and are not a finding about arm_1**. `criteria.md` §3's rule T states no
verdict about arms 2 and 3 at all.

| block / trial | load-arm events in the segment | arm_1's own verdict there |
|---|---|---|
| **B1**, trial 25 | arm_3, joint 2; `PATH_TOLERANCE_VIOLATED` on `arm_3_joint_trajectory_controller` | **healthy** — and it is BAND1 [CONC]'s peak trial |
| **B1**, trial 39 | arm_3 (joints 0, 2, 3) and arm_2 (joint 4); path aborts on both | **fired** — firing 1 above |
| **B3**, trial 39 | arm_3 (joints 0, 4); `PATH_TOLERANCE_VIOLATED` on `arm_3_joint_trajectory_controller` | **healthy** |

**B3's trial 39 is the instructive one: arm_3 violated its own path tolerance and arm_1 did not,
in the same log segment, at the schedule slot that fired in the other two blocks.** That is exactly
the confusion the 2026-09-04 shakedown found and deviation 8 exists to prevent — an unattributed
scrape recorded a genuine `arm_3` violation as arm_1's, which would have manufactured this
campaign's headline verdict out of a load arm. **The three trials above are arm_3's and arm_2's
business, and they are kept strictly separate from arm_1's two.**

**Rule T also reports the load arms' failed goals**, which are numerous — arm_3 in particular
returns `MOTION_INTERRUPTED` on many CONC trials, and on several also `ResultCode 2` (*the
commanded trajectory did not take effect*). **No verdict is stated about arms 2 and 3**, and none
is implied. Their failures matter here only in that they are the load condition CONC1 is measured
under, and §5 states what that does to it.

---

## 4. BAND1 — three arms far below the line, and FAST above it

> **Rule G** applies to every verdict in this section, as stated in §3.

| arm | BAND1 | peak `│error│` | joint | trial | `│feedback.velocities│` peak | `│reference.velocities│` peak | against 0.100 rad |
|---|---|---|---|---|---|---|---|
| **CRUISE** | **FAR** | **0.018878554** rad | `arm_1_joint5` | trial 2, B3, cycle 1, `above_pick` | 0.314578309 rad/s | 0.314321518 rad/s | **5.30× below** |
| **FAST** | **SHORT** | **0.115972442** rad | `arm_1_joint5` | trial 7, B1, cycle 1, `above_place` | 1.932841238 rad/s | 2.009125844 rad/s | **+15.97 % over** |
| **CARRY** | **FAR** | **0.018872962** rad | `arm_1_joint5` | trial 9, B1, cycle 1, `pick` | 0.314494421 rad/s | 0.314353241 rad/s | **5.30× below** |
| **CONC** | **FAR** | **0.026154394** rad | `arm_1_joint1` | trial 25, B1, cycle 2, `home` | 0.435718473 rad/s | **1.240514836** rad/s | **3.82× below** |

Sample counts behind those distributions: **29671** (CRUISE), **8253** (FAST), **35022** (CARRY)
and **28735** (CONC) samples over the moving windows. The per-joint pooled distributions — min,
median, p95, p99, max on all five joints — are in the print and are not reproduced here.

### 4.1 FAST is SHORT, and what that does and does not mean

**FAST's healthy peak is 0.115972442 rad against ADR-0036's own 0.100 rad line** — the *"at least
an order of magnitude below `trajectory_tolerance_rad`"* that record asks for, against the declared
1.0 rad. It exceeds it by **0.015972442 rad, 15.97 %**. The value is remarkably stable: **9 of the
36 FAST trials peak at exactly 0.115972442 rad**, every one of them on the `above_place` goal.

**This is the outcome PRED3 registered before any trial, and registered as the uncomfortable one.**
§2.2's correction of 2026-09-04 narrowed the predicted margin over the line from about 26 % to
about 16 % **without flipping the prediction**, and the measured 15.97 % lands inside that.

**Two things bound it, both registered in advance and both stated here because §7.2 requires it.**

1. **FAST is outside the condition ADR-0036's sentence is scoped to.** That record asks for the
   sample *"across `pick_and_place` and `continuous_line`"*, which run at the configured **0.35**
   scaling. **CRUISE, CARRY and CONC are inside that scoping; FAST is not** — FAST is full scaling
   1.0/1.0. FAST is reported against the same band because **the band is the only registered line
   there is**. **A SHORT on FAST does not make ADR-0036's sentence false and is not written as
   though it did.**
2. **A SHORT verdict is reported and acted on by nobody here.** Whether the value is wrong is
   ADR-0036's question and the project owner's, not this campaign's (§0). **This campaign reports
   the margin and proposes nothing.**

### 4.2 Rule M — every FAR peak is a lower bound

> **Rule M, attached to every FAR verdict as `criteria.md` §7.2 requires.** `publish_state` runs at
> the end of every `update()`, but through a realtime publisher's `try_publish`, and **the
> tolerance check runs in `update()` whether or not the message is delivered.** So **BAND1's peak
> is a maximum over the samples that *arrived*, and is a lower bound on the maximum the controller
> actually compared. A FAR verdict is therefore weaker than a SHORT one** — SHORT is established
> by a single delivered sample; FAR is an assertion about samples that were not taken.

The three FAR arms' achieved sample rates, and what they cost:

| arm | median achieved rate | against the controller's 150 Hz | share of compared states never delivered |
|---|---|---|---|
| **CRUISE** | 143.054472126 /simulated s | 150 | **≈ 4.63 %** |
| **CARRY** | 142.93207823950002 /simulated s | 150 | **≈ 4.71 %** |
| **CONC** | 143.045360437 /simulated s | 150 | **≈ 4.64 %** |

**So roughly one state in twenty-one that the controller compared was never delivered to this
instrument, on every FAR arm.** Each of the three FAR peaks above is a **lower bound** on what the
controller actually checked. FAST's SHORT verdict carries no such weakening: it is established by
delivered samples that exceed the line.

---

## 5. CONC1 — INDISTINGUISHABLE, with no guard suppressing it

> **Rule G** applies here as in §3 and §4.

| | CONC (loaded) | CRUISE (the control) |
|---|---|---|
| **median of the trial-peak — the registered statistic** | **0.018848806 rad** | **0.018848806 rad** |
| n | **7** | **36** |
| max, reported beside and deciding nothing | 0.018848806 | 0.018878554 |
| p95, reported beside and deciding nothing | 0.018848806 | 0.01887297025 |

**│difference│ = exactly 0.0 rad**, against §7.0's 0.005 rad minimum interesting size. **CONC1 =
INDISTINGUISHABLE.**

**Neither guard suppressed it, and that is what makes the verdict worth stating.**

- **Rule R did not bind.** The within-arm spread of the statistic is **3.210999999999492 × 10⁻⁶
  rad** on CONC(loaded) and **3.435099999999844 × 10⁻⁵ rad** on CRUISE, against the 0.005 rad
  minimum interesting size — **about 1557× and about 146× below it respectively.** The binding
  quantity is the larger of the two, and even that sits more than two orders of magnitude clear.
  **`criteria.md` §7.2 registered in advance that rule R was *expected* to bind here, and it did
  not** — deviation 18.
- **V6 was evaluable on both arms and did not bind.** `CONC = False, CRUISE = False`, and the print
  states `unevaluable for neither arm`. Under deviation 12 an unevaluable V6 would have been
  treated as **binding** and CONC1 would have read INCONCLUSIVE; that path was not taken because
  the block effect was genuinely measurable and genuinely small. Per-block medians of the
  trial-peak are `{B1: 0.018848806, B2: 0.018848806, B3: 0.018848806}` on CONC — a within-arm block
  spread of **exactly 0.0** — and `{0.018848806, 0.018848806, 0.0188489185}` on CRUISE.

**So PRED5 held on a statistic that could actually have moved**, and the argument it was registered
on — that the controller manager is stepped by the simulator in **simulation** time, so concurrent
load stretches wall clock and leaves the loop's simulated cadence alone — survives its test rather
than escaping it.

### 5.1 `load_active`, and why CONC1 is evaluable at all

**`load_active` is true on 7 of the 34 admissible healthy CONC trials; 27 do not carry it.** A CONC
trial without it is **not** an instrument loss — arm_1's samples are still arm_1's, and LIVE1,
QUIET1 and BAND1 use all of them; it is simply not a sample of the load condition, and CONC1's
population is `load_active is True`.

**The 27 that lack it are not near zero coverage — they sit between 0.9911 and 1.0000.** Every one
of the 54 per-arm coverage fractions on those trials is at or above **0.991**, and several are
exactly **1.0** on one arm while the other falls a fraction short. The flag is a conjunction over
**both** load arms across the **whole** of arm_1's moving window, so a few milliseconds' gap on
either arm turns it false.

**This is the first block set taken with the pre-trial Critical fix, and CONC1 is evaluable because
of it.** Before that fix a load arm published only the goals that had **finished**, so the goal
still in flight at the end of arm_1's moving window — the goal that spans almost every window's
tail — contributed nothing, and **`load_active` was systematically false**. Deviations 1 and 9
record the fix and, notably, record that the *prose* had asserted a mechanism the code did not have
(*"the gaps between a load arm's consecutive goals"*) when the recorded intervals are contiguous to
the microsecond. **n = 7 is small**, and §12 says so; but it is 7 rather than 0, and it is a real
population.

**Rule T's caveat stands over this section.** The load arms failed goals on many CONC trials (§3.2).
**That is the load condition, not a defect in it**, and no verdict about arms 2 and 3 is stated.

---

## 6. GOAL1 — CLEAR on every arm, and it evidences nothing

> **Rule G** applies here as in §3.

| arm | GOAL1 | n | settle min/median/max | at or below one sample interval | goal-time aborts | unattributable events |
|---|---|---|---|---|---|---|
| **CRUISE** | **CLEAR** | 36 | 0.0 / 0.0 / 0.0 s | **36 of 36** | 0 | 0 |
| **FAST** | **CLEAR** | 36 | 0.0 / 0.0 / 0.0 s | **36 of 36** | 0 | 0 |
| **CARRY** | **CLEAR** | 18 | 0.0 / 0.0 / 0.0 s | **18 of 18** | 0 | 0 |
| **CONC** | **CLEAR** | 34 | 0.0 / 0.0 / 0.0 s | **34 of 34** | 0 | 0 |

**Every settle on every healthy admissible trial is 0.0 s**, against the 0.25 s line and one sample
interval of 0.006667 s. No trial ended its goal window with the error still outside the goal
tolerance, so deviation 11's NOT EVALUABLE state — added so that a never-settling trial could not
be read as a pass — did not need to fire on any of the 124.

> **Registered before any trial, and it evidences nothing.** `criteria.md` §7.3 predicts exactly
> this: the reported error at the last trajectory point is **the deceleration term alone** —
> 0.0027 rad at default scaling and 0.0076 rad at full — **both already inside the 0.01 rad goal
> tolerance before the goal window opens**, so the predicted settle is at most one sample interval
> and **GOAL1 = CLEAR is guaranteed by construction**. **This CLEAR is not evidence that the goal
> tolerance behaves, that the goal window is comfortable, or that anything was exercised.** It is
> reported in the rule-N shape, and it was registered in advance precisely so that it could not
> later be read as evidence. **Only a settle above one sample interval would have carried any
> information at all.**

**SVT — `stopped_velocity_tolerance`: NOT MEASURED**, and registered as not measured rather than
measured as a constant. It **cannot** fire on this controller for two independent reasons read in
source, **either alone sufficient**: this controller commands position only, so `state_error_`'s
velocities stay at the zeros they were sized to; and the generated value is `0.0`, which
`check_state_tolerance_per_joint` does not apply. **This campaign samples nothing for it**, and its
silence about it is not a measurement.

---

## 7. X1 — two arms stressed the tolerance, two did not

Rule X's stress speed is **1.6667 rad/s**, **derived and not chosen**: it is `0.100 / (1/k - 1/R)`
with `k = 15.0 s⁻¹` and `R = 150 Hz` — the joint speed at which the predicted **reported** error
equals ADR-0036's own line. Below it the criterion cannot be missed by the lag mechanism at all.

| arm | X1 | peak measured joint speed | peaks min/median/max |
|---|---|---|---|
| **CRUISE** | **NOT STRESSED** | 0.314578309 rad/s | 0.314069893 / 0.314146699 / 0.314578309 |
| **FAST** | **STRESSED** | **1.932841238 rad/s** | 1.348134645 / 1.3973622015 / 1.932841238 |
| **CARRY** | **NOT STRESSED** | 0.314494421 rad/s | 0.314069891 / 0.314111304 / 0.314494421 |
| **CONC** | **STRESSED** | **2.14097295 rad/s** | 0.31406989 / 0.314146699 / **2.14097295** |

**At least one arm is STRESSED, so the clause requiring this document to declare the path tolerance
untested does not fire.** Two arms reached the stress speed.

> **Rule N, for the two that did not.** CRUISE's and CARRY's quietness is a statement about the
> speeds they ran at and **about nothing faster**. Their silence may not be read as agreement with
> §2.2's arithmetic, as a clearance of the tolerance, or as evidence that the detector behaves. #20
> stays open on that part.

**CONC being STRESSED falsifies `criteria.md` §7.4's own "by construction" clause** — deviation 16
— and is what refutes PRED6. CONC's peak speed of **2.14097295 rad/s** is nearly **twice** the
1.099 rad/s cap §7.4 asserts for it, and it occurred on the B1 trial 39 firing.

---

## 8. Rule D — 124 of 126 agree to five significant figures, and the two that do not are the firings

Rule D compares, **per trial**, the measured peak `│error│` against `v_peak * (1/k - 1/R)` — that
is **`0.060 × v_peak`** — with `v_peak` that trial's **own** measured peak joint speed. The band is
**25 %** and it does not move.

| arm | trials compared | disagreements |
|---|---|---|
| **CRUISE** | 36 | **0** |
| **FAST** | 36 | **0** |
| **CARRY** | 18 | **0** |
| **CONC** | 36 | **2** |
| **total** | **126** | **2** |

**124 of 126 trials agree, and the agreement is far tighter than the 25 % band admits.** At each
arm's BAND1 peak trial the law and the measurement agree to five significant figures:

| arm | `0.060 × v_peak` | measured peak | relative difference |
|---|---|---|---|
| **CRUISE** | 0.01887469854 | 0.018878554 | **0.020 %** |
| **FAST** | 0.11597047428 | 0.115972442 | **0.0017 %** |
| **CARRY** | 0.01886966526 | 0.018872962 | **0.017 %** |

**This is what establishes §2.2's corrected command law rather than merely admitting it.** The
25 % band would have absorbed the superseded `v_peak / k` form, which is 11 % larger — the campaign
would have reported that the arithmetic agreed while carrying an unmodelled systematic term, which
is the exact shape rule D exists to expose. It does not have to: the corrected law
`v = e × (1/k - 1/R)`, one term from the plugin and one from the controller's own lookahead,
reproduces the measurement on 124 trials across four conditions and three bring-ups.

**The two disagreements are the two firing trials, and neither is attributed.**

| | firing 1 | firing 2 |
|---|---|---|
| block / trial / cycle / goal | B1, trial 39, cycle 3, `home` | B2, trial 39, cycle 3, `home` |
| `v_peak` | 2.14097295 rad/s | 1.953891775 rad/s |
| predicted | 0.128458377 rad | 0.1172335065 rad |
| **measured** | **1.049154254 rad** | **1.150903069 rad** |
| **ratio** | **8.167270041096657** | **9.817185405095769** |
| peak sample | `arm_1_joint3`, index 582 in window, sim_t 366.996 | `arm_1_joint3`, index 166 in window, sim_t 366.961 |
| V5 identity on that sample | `v5_ok: true` | `v5_ok: true` |

**The campaign does not attribute the disagreement.** Whether the cause is the gain, the update
rate, the physics engine's handling of the velocity command, the time parameterisation or the
harness **is not decided here**, and the candidates are listed without choosing among them.
**Nothing was re-run to resolve it, no goal was retuned in the direction that would make it go
away, and no constant anywhere in the tree was edited.** Both peak samples satisfy V5's identity,
so the records are internally consistent — the disagreement is between the arithmetic and the
plant, not between the message and itself.

**Note what the ratios mean and do not mean.** A measured error of 1.05 and 1.15 rad **exceeds the
declared `trajectory_tolerance_rad` of 1.0 rad**, which is why these two trials are the ones the
controller aborted. That is a coherent account of *the abort*; it is **not** an attribution of
*why the error got there*, and this document does not supply one.

---

## 9. The six predictions

| # | Registered | Outcome |
|---|---|---|
| **PRED1** | QUIET1 = QUIET on every arm | **REFUTED.** QUIET1 [CONC] = FIRED. The registered refutation clause — *"any path-tolerance violation on any arm"* — occurred, and the prediction's stated consequence is that it **refutes the mechanism as well as the prediction**. Rule D's two disagreements are the same two trials, which is consistent with that reading and is not developed further here. |
| **PRED2** | BAND1 = FAR on CRUISE, CARRY and CONC, **with peaks near 0.066 rad and in 0.063–0.066 rad** | **HELD IN VERDICT, REFUTED IN MAGNITUDE.** All three are FAR, as registered — the refutation clause was *"a peak above 0.100 rad on any of the three"* and no such peak occurred. But the peaks are **0.018878554, 0.018872962 and 0.026154394 rad**, and **none is in the registered 0.063–0.066 rad range.** See below. |
| **PRED3** | BAND1 = SHORT on FAST, peak near 0.116 rad and in 0.113–0.129 rad | **HELD, including in magnitude.** FAST = SHORT at **0.115972442 rad**, inside the registered range and within 0.03 % of the registered central value of 0.116. **The uncomfortable outcome, registered before any trial, landed.** |
| **PRED4** | GOAL1 = CLEAR on every arm, **and uninformative by construction** | **HELD AND UNINFORMATIVE**, exactly as registered. CLEAR ×4 with every settle at 0.0 s. §6. |
| **PRED5** | CONC indistinguishable from CRUISE at 0.005 rad | **HELD.** CONC1 = INDISTINGUISHABLE at a difference of exactly 0.0 rad, with rule R not binding and V6 evaluable and not binding. §5. |
| **PRED6** | X1 = STRESSED on FAST **and NOT STRESSED on the other three** | **REFUTED.** FAST is STRESSED as predicted, but **CONC is STRESSED too**, so the prediction as written is false. **Its registered refutation clause names only *"FAST failing to reach 1.667 rad/s"*, which did not happen** — the analyser reports PRED6 refuted on the verdict set rather than on that clause. Both readings are recorded; deviation 16 is where the underlying falsification is kept. |

### 9.1 PRED2's magnitude — a finding about §2.3's input, not about the command law

**Do not blur these two.** PRED2's verdict held and its magnitude did not, and **the magnitude
failure is upstream of the command law, not in it.**

§2.3 estimated the leading joint's swing from a **base bearing** of a frame — `cell_a__table_pick__surface`
at +1.0075 rad and `cell_a__conveyor_1__infeed` at −1.0304 rad in `arm_1_mount`'s frame, a swing of
2.038 rad — and concluded that a default-scaled trapezoidal profile would reach its **1.099 rad/s**
velocity cap. **The IK solution does not agree.** The measured peak joint speed on CRUISE is
**0.314321518 rad/s** reference and **0.314578309 rad/s** feedback — about **3.5× less** than the
estimate.

**The law then predicts what the cell delivers.** `0.060 × 0.314578309 = 0.01887469854` rad against
a measured **0.018878554** rad — agreement to **0.020 %**. The registered 0.0659 rad and the
measured 0.0189 rad differ by a factor of **3.49**, which is the **same factor** as the velocity
estimate's error, to three significant figures.

**So §2.3's displacement estimate was wrong and §2.2's command law was right.** `criteria.md` §2.3
anticipated exactly this — *"This is the base bearing of the frame, not the IK solution's `joint1`,
and the two are not identical; it is an estimate, `v_peak` is measured per trial, and rule D governs
the comparison"* — and the harness README's limitation 11 says the same. **Rule D agreeing to five
significant figures on 124 trials is what establishes the law**; PRED2's magnitude miss is a finding
about the input that fed the prediction, and it must not be written as a finding about the law.

---

## 10. Deviations, numbered, applied to data already collected

**Deviations 1–15 were written into `harness/analyse.py` before the first trial and print at the top
of every run. None moved a threshold, and the full wording is in the print and is not restated here
(P1).** They cover, in one line each: `load_active` as a statement about every instant of the moving
window (1); rule L and V5 computed where the block is taken (2); the shakedown's three independent
refusals (3); V1's seal (4); the work-piece removal point (5); GOAL1's settle measured from the goal
window's first sample (6); the non-trial repositioning move (7); I3 attributed to arm_1 and to
nothing else (8); the load-arm acceptance wait (9); a tolerance event outranking rule L's refusal,
with both readings stated (10); an unresolved settle reported NOT EVALUABLE rather than CLEAR (11);
V6's `None` treated as binding (12); V3 and V4 refusing a block before its first goal (13); rule R
pooled over four goal kinds, conservatively (14); and V14 checking monotonicity but not that the
stamp is a simulated one (15).

**Deviations 16–20 are this write-up's, found in the completed data and applied to it. None moves a
threshold, and every registered rule was applied literally.**

**16. §7.4's "by construction" claim is falsified by the campaign's own data.** `criteria.md` §7.4
states, in a registered rule and not in prose, that **"CRUISE, CARRY and CONC cannot stress it, by
construction"**, their cap being **1.099 rad/s**, and that reaching 1.6667 rad/s at their
acceleration ceiling would need a leading-joint displacement of 3.969 rad against the 2.038 rad the
cell offers. **CONC measured a peak joint speed of 2.14097295 rad/s — nearly twice that cap — and
X1 [CONC] = STRESSED.** Applied literally, as V9 requires, **X1 [CONC] stands as STRESSED and PRED6
is refuted by it.** The clause is recorded as **wrong** rather than corrected, against data already
collected. **What produced the speed is not attributed here**; it occurred on the B1 trial 39
firing, and §8 declines to attribute that trial for the same reason. Note the direction: the
falsification makes the campaign's stress coverage **larger** than registered, not smaller, so no
verdict was weakened by it.

**17. V7's with-and-without pair is not computable at this n.** V7 fired on **all three blocks**,
and requires that *"every verdict a flagged trial contributes to must be reported with and without
those trials"*. **The "without" set is empty**: removing every flagged trial removes all 126.
**This is reported as unsatisfiable at this n rather than reinterpreted** — no substitute
comparison is invented, no verdict is recomputed against a subset the rule does not name, and no
verdict is declared INCONCLUSIVE on a rule that could not be evaluated. **The load is largely
self-inflicted, and the record shows it**: B1 began at a 1-minute load average of **2.729**,
unflagged, and ended at **6.439**, flagged; B2 began at 3.720 and ended at 4.244; B3 began already
flagged at a 5-minute average of 4.569 and ended at 6.488. **The cell under measurement is what
raises the load**, so a campaign that brings this cell up three times cannot produce an unflagged
block by waiting. `criteria.md` §9 argues that host load reaches the **instrument** — `try_publish`
drops, which lowers the sample rate — and not the decision quantity, because the controller manager
is stepped in simulation time; **that argument is not tested by this campaign and is not confirmed
by it.**

**18. §7.2 registered that rule R "is expected to bind" for CONC1, and it did not.** The
registration says in as many words that *"rule R is expected to bind here, and saying so in advance
is the point of registering it"*. **It did not bind, and it was not close.** The within-arm spread
of CONC1's statistic is **3.211 × 10⁻⁶ rad** on CONC(loaded) and **3.435 × 10⁻⁵ rad** on CRUISE
against the 0.005 rad minimum interesting size — the binding one, CRUISE, sitting about **146×**
below it and the other about **1557×** below. **The registration's expectation was wrong in the
safe direction**: it predicted the campaign would be unable to state a CONC1 verdict, and the
campaign was able to. **No threshold moved and rule R was applied exactly as written**, including
deviation 14's conservative pooling over four goal kinds, which can only enlarge the spread — so
the registered per-goal form would bind **less** often still.

**19. CONC1's two medians are bit-identical, and this is an exact tie rather than a rounding
artefact.** Both read **0.018848806** rad and their difference prints as **exactly 0.0**. **That
value is not a coincidence of rounding: it is a value the cell lands on repeatedly.** **7 of the 36
CRUISE trial-peaks** and **15 of the 34 CONC trial-peaks** are exactly 0.018848806 rad — every one
of them on a `home` goal, on `arm_1_joint1` — and CRUISE's 36 peaks take only **13 distinct values**
in total while CONC's 34 take **10**. The median of an even-sized CRUISE set and the median of the
7-trial loaded CONC set both land on the modal value, and they are the same modal value.
**Nothing is attributed.** Whether the repetition reflects a deterministic trajectory, a quantised
reference, or something about the plant is **not established here**, and `criteria.md` §1.2 records
that this cell's physics solver is unseeded and every figure is a sample. The tie is reported
because a difference of *exactly* zero invites the reading that the statistic could not resolve
anything, and **that reading is wrong** — rule R and V6 were both evaluated and neither bound.

**20. Reference velocities exceed the description's own declared limit, and no registered rule reads
them.** `velocity="3.14"` is declared on **every one of the xarm5's five arm joints** — five
occurrences in `workspace/src/external/xarm_ros2/xarm_description/urdf/xarm5/xarm5.urdf.xacro`,
read at `HEAD` on 2026-09-04. **The two firing trials carry `│reference.velocities│` of 8.580992655
and 21.19300984 rad/s** on `arm_1_joint3` at their peak samples — **2.7× and 6.7× the declared
limit.** **Separately, and in a *healthy* trial:** BAND1 [CONC]'s peak trial (B1, trial 25) carries
a `│reference.velocities│` peak of **1.240514836 rad/s** on a **default-scaled** goal whose
registered cap is **1.099 rad/s** (§2.2 item 2). **No measured joint speed exceeded 3.14 rad/s
anywhere** — rule X's peaks top out at 1.932841238 (FAST) and 2.14097295 (CONC) — so the exceedance
is in the **reference**, not in the feedback. **Nothing in `criteria.md` §7 reads
`reference.velocities` against a limit**: rule X is stated on `feedback.velocities`, the measured
joint speed, and I2 records the reference only as context. **So no rule fires on this, and none is
invented here.** It is **recorded and not attributed**: whether the reference is the time
parameterisation's output, an artefact of the abort path on the two firing trials, or something
else is not decided by this campaign, and harness README limitation 10 already records that whether
`gz-sim` clamps the plugin's velocity command against the joint's SDF limit is **unverified** here.

---

## 11. The machine, the load, and the validity rules

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM (`criteria.md` §9; `host_uname` on every campaign invocation record) |
| Container | image **`cite-digital-twin:dev`**, ID `3a41d4e431b0`, Ubuntu 24.04.4 LTS, ROS 2 Jazzy. **Not CPU-limited by any condition here** |
| Simulator | **Gazebo Sim 8.11.0**, the version the **sourced** environment resolves — the image also carries an unsourced 8.15.0, and the cell runs sourced. **This rig does bring Gazebo up**, so the version is a fact about what was measured |
| Controllers | `gz_ros2_control` **1.2.19**, `joint_trajectory_controller` **4.40.1**, `controller_manager` **4.45.2** |
| Motion planning | MoveIt **2.12.4** |
| Middleware | `rmw_fastrtps_cpp` **8.4.4** — named because the publisher's QoS resolves there and not in the controller |
| Isolation | compose project **`cite-digital-twin-3319196271`**, **`ROS_DOMAIN_ID` 43**, both derived from this checkout and recorded on every campaign invocation in `raw/provenance.txt` |
| Vendor pin | `external/cite.repos` names **`3dc2b5e`** and the imported checkout read **`3dc2b5e`**, at both ends of every block |

**Load, measured at both ends of every block (I8), and V7's verdict on it.**

| block | load 1m / 5m / 15m at start | at end | V7 |
|---|---|---|---|
| **B1** | 2.729 / 0.759 / 0.317 | **6.439** / 5.122 / 2.708 | flagged at end |
| **B2** | 3.720 / 3.598 / 2.680 | 4.244 / **5.536** / 4.170 | flagged at end |
| **B3** | 2.582 / **4.569** / 3.982 | **6.219** / 6.488 / 5.102 | flagged at both ends |

**V7 flags and never excludes**, and **no block was discarded for load** — a load threshold chosen
after seeing the data is a threshold chosen by the data. Deviation 17 is what V7's own
with-and-without requirement became at this n. `/proc/loadavg` is read inside the container, and
`criteria.md` §9 records why that is the host's own reading on this host: it is not namespaced on
native Linux and there is no `lxcfs` in the way.

**I9 — the simulated-to-wall clock ratio, context only and entering no verdict:** 0.9073 (B1),
0.9101 (B2), 0.9033 (B3), computed from I1's own header stamps against the wall clock over
371.27 s, 372.64 s and 374.80 s of simulated time. **Gazebo's own `real_time_factor` field is never
quoted here** — the 2026-08-29 campaign established that it over-reports under starvation, and that
finding is **cited and not copied** (rule H).

**Every other validity rule passed and is recorded above:** V1 (§front matter), V2, V3, V4, V12 and
V13 (§1), V5 (§2), V6 (§5), V8 (below), V9, V10 and V11 (§front matter and §1), V14 (no
exclusions).

**V8 — n is what it was.** No arm was topped up to match another. Admissibility under rule L is
36/36 (CRUISE), 36/36 (FAST), 18/18 (CARRY) and 36/36 (CONC); the Wilson 95 % intervals on those
proportions are **(0.9036, 1.0)** for the three arms at n = 36 and **(0.8241, 1.0)** for CARRY at
n = 18. **Those intervals are about the instrument's loss rate and about nothing else** — they are
not confidence intervals on any following-error figure in this document.

---

## 12. What this campaign does not establish

Registered in `criteria.md` §8 and §11 before the first trial, and none of it moved.

- **The firing half of #20.** §1.1 registers it as structurally out of scope. **The two events on
  CONC were not induced**, and **nothing here shows the detector *can* detect an obstruction under
  this backend.** No fixture, no ADR and no work item is proposed for it (§0).
- **Anything about the physical arm.** **Nothing here is a P2 result.** It samples one backend, one
  plugin, one gain. #20's asymmetry — that the detector may be structurally silent in simulation
  while live on hardware — **is not resolved in either direction**, and the word *validated* is not
  used about the tolerance on either backend (rule G).
- **That the tolerance is quiet at speeds above those measured.** Rule N, over CRUISE and CARRY,
  whose peaks are 0.3146 and 0.3145 rad/s against rule X's 1.6667 rad/s.
- **Why the two CONC trials violated the path tolerance.** §8 lists the candidates and chooses
  none. **Not attributed.**
- **Why B3 produced no event at the slot that fired in B1 and B2.** §3.1. Not attributed, and not a
  rate.
- **Why the reference velocities exceed the declared joint limit.** Deviation 20. Not attributed,
  and no registered rule reads them.
- **Whether `gz-sim` clamps the plugin's velocity command** against the joint's SDF limit. Harness
  README limitation 10; unverified here.
- **`stopped_velocity_tolerance`.** NOT MEASURED, for two independent structural reasons (§6). The
  campaign samples nothing for it.
- **The scenarios ADR-0036's bullet names.** This rig **does not run `pick_and_place` or
  `continuous_line`**; it drives L3 directly, because the recorder must live in the launch's own
  container and a scenario failing for its own reasons would consume a block. **That part of the
  bullet is not discharged here.**
- **Whether host load reaches the decision quantity.** §9's argument that it reaches only the
  instrument is an argument from the plugin's structure and is **not tested by this campaign**
  (deviation 17).
- **A rate of anything.** Every count is a count over the trials that ran. **One machine, one
  image, one commit, one checkout, one zone, one arm as the decision quantity, one collision
  geometry, one `max_step_size`, one controller-manager rate, one gain, three bring-ups.**
- **Any statistic over CONC1 at a comfortable n.** The loaded population is **7 trials**. The
  verdict is stated because the registered rule produced it and both guards were evaluated; the n
  is what it is (V8), and no arm was topped up to improve it.

---

## 13. What this campaign does not decide

**This campaign chooses nothing**, and that was registered in `criteria.md` §0 before any number
existed so that no number could be read as an argument for one.

- **It moves no tolerance.** `trajectory_tolerance_rad`, the per-joint `goal` tolerance, `goal_time`
  and `stopped_velocity_tolerance` are the tree's. **This campaign proposes no value for any of
  them, argues for none, and may not be cited as support for changing one.** **A tolerance is never
  widened to absorb a measurement** — that is ADR-0036's own sentence, in the generated file's own
  comment.
- **It does not promote ADR-0036 or move its status.** Whether the sample taken here discharges that
  record's "revisit" bullet is **that record's question and the project owner's**. §4.1 states what
  a SHORT on FAST does and does not mean for it.
- **It does not decide whether the firing half is worth building.** §12, and §0 registered it.
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/`, `scripts/`, `assets/` or `external/`
  was edited.** The harness lives entirely under `harness/` in this directory, and `raw/` beside it.
  V1's two-ended `git` reading holds on all 126 rows.
- **No ceiling, threshold or band anywhere in the tree was changed**, and none may be changed to
  absorb anything found here.

Where a figure above bears on a decision, it is a quantity with its consumer named and the sentence
stops there:

| Quantity | What it bears on |
|---|---|
| LIVE1 ADMISSIBLE ×4 at 0 instrument losses, L-iii satisfied on every trial (§2) | that #20's healthy half was answered by a **live** instrument, which is the one thing a green run could not have shown |
| BAND1 [FAST] = SHORT at 0.115972442 rad, +15.97 % over 0.100 rad (§4.1) | ADR-0036's own order-of-magnitude criterion — **at full scaling, outside the condition that record's sentence is scoped to** |
| BAND1 = FAR at 0.0189, 0.0189 and 0.0262 rad on the three default-scaled arms (§4) | the same criterion **inside** ADR-0036's scoping, subject to rule M's lower-bound caveat |
| QUIET1 [CONC] = FIRED, 2 events, both attributed to arm_1's own controller (§3) | that the path tolerance is **not** structurally silent under `gz_ros2_control` — which is **not** the same as showing it can detect an obstruction (§12) |
| Rule D: 124 of 126 agree to five significant figures (§8) | §2.2's corrected command law `e = v × (1/k − 1/R)`, and the retirement of the superseded `v/k` form |
| Rule D's two disagreements, ratios 8.17 and 9.82, unattributed (§8) | whatever a future campaign is designed to attribute; **nothing here** |
| X1 [CONC] = STRESSED at 2.14097295 rad/s (§7, deviation 16) | the shape of a future campaign's rule X, and §7.4's registered "by construction" clause, recorded as wrong |
| CONC1 = INDISTINGUISHABLE at exactly 0.0 rad, guards evaluated (§5) | PRED5's argument from the plugin's structure, at n = 7 loaded trials |

**The choice is the project owner's.** This campaign exists to make it decidable.

---

## 14. Reproduction

The whole campaign is `harness/run_campaign.sh`; `harness/README.md` carries every command,
including the one-block-at-a-time forms. Every figure in this document comes from:

```sh
python3 docs/measurements/2026-09-04-following-error/harness/analyse.py
```

which applies `criteria.md` §7's rules to `raw/` and **prints every rule whether or not it fires** —
**639 lines and about 105 KB**, carrying 24 rule sections, 15 deviations, the embedded per-joint
distributions and the full peak lists. **It must be redirected to a file rather than piped through
`head`**: a previous campaign's operator piped a 1034-line report through `head`, saw 143 lines,
and `tee` still reported exit 0. **A truncated print looks exactly like a rig with fewer rules.**

Nothing here was derived by hand from trial files the analyser does not print, except where a
per-trial column is quoted directly from `raw/*_trials.json` and named as such: §3.1's B3 trial 39
I3 columns, §1's and §11's block timestamps and load readings, and deviation 19's counts of repeated
peak values, which are tallied from the print's own per-arm peak lists.

**Figures stay in this directory.** Nothing here is copied into
[ADR-0036](../../adr/0036-execution-side-trajectory-tolerances.md), `CLAUDE.md`,
[`docs/open-work.md`](../../open-work.md), the generated comments or any layer document (P1).
**Cite the directory.**
