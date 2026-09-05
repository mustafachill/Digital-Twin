# The hull is never larger anywhere it was measured, a finger passes within 5.8 mm of a conveyor, and #17's question was not tested

**Verdict, in this campaign's own terms.** Every one is `criteria.md` §7's registered rule applied
by `harness/analyse.py` to `raw/`, and every one is stated **per capture** — rule T: the captures
are not each other's evidence, and BRINGUP's silence says nothing about LINE.

| Quantity | Verdict | In one line |
|---|---|---|
| **LIVE1 — a measured capture, or a measured nothing** | **ADMISSIBLE on BRINGUP and LINE; NOT ADMISSIBLE on PICKPLACE** | BRINGUP **3** trajectories over **186** waypoints, LINE **105** over **4,500**. **PICKPLACE is a measured nothing**: its 24 trajectories were all logged as published, all received cleanly, **0 instrument losses**, and were then dropped at the join because the description read back empty. Its silence is evidence about nothing. |
| **DELTA1 — what the hull changed** | **SMALLER on BRINGUP and LINE**, and **LINE's is downgraded to INCONCLUSIVE** (§11) | Largest `d_vendor − d_hull` **0.0319444 m** on `(arm_3_link3, pedestal_3)` (LINE) and **0.0127867 m** on `(arm_1_link3, pedestal_1)` (BRINGUP). **Not on gripper links**, which refutes nothing registered but is not where PRED1 expected the mechanism. |
| **Rule E — containment** | **did not fire on either admissible capture** | Largest reverse difference anywhere is **+2.22045e-16 m** (LINE) against `DIFF_FLOOR` **1e-9 m**; BRINGUP's is **−0 m**. **0 REVERSED pairs.** The direction the derivation makes a theorem held in the measurement. |
| **FLIP1 — hull-only contact** | **NONE on BRINGUP and LINE; NOT EVALUABLE on PICKPLACE** | 0 pairs with `d_hull <= 0 < d_vendor`, 0 the other way. **PRED3 registered in advance that a NONE evidences nothing.** A hull-only contact would have been this campaign's most valuable single observation and **none occurred**. |
| **MARGIN1 — how close this cell actually passes** | **TIGHT on BRINGUP and LINE** | LINE: **25** non-standing pairs came within `CLOSE_BAND` (0.040 m), closest approach **0.00582921 m** — `(arm_3_left_finger, conveyor_2)`. BRINGUP: **3** pairs, closest **0.0314213 m**. **On trajectories `ValidateSolution` accepted.** |
| **STEP1 — the per-waypoint tool-point step** | **LINE/pilz COMPARABLE at 0.0241558 m; BRINGUP/pilz FAR BELOW at 0.0192488 m** | LINE lands inside `[STEP_MID, STEP_HIGH)` = `[0.020, 0.040)` m and **refutes PRED4**. **Zero unattributable trajectories** anywhere. **Zero OMPL intervals anywhere** — everything measured is Pilz, and nothing here bounds what OMPL would step. |
| **TUNNEL1 — does a body pass between two checked waypoints** | **NOT OBSERVED on both admissible captures, under both geometries — and rule K refuses it** | **0** sub-sample contacts. **Rule K-ii did not find its region on any capture**, so the analyser's own words stand: *"NO capture exercised #17's region, so open-work #17 STAYS OPEN on this campaign's evidence."* **PRED5 held** — the campaign predicted in advance that it would not test #17, and it did not. |
| **FK1 — the instrument checking itself** | **AGREES on BRINGUP and LINE** | **600 of 600** sampled waypoints answered by `move_group`, **0** unanswered; worst position residual **3.33067e-16 m** against 1e-6 m, worst angular **4.21468e-08 rad** against 1e-6 rad. |
| **VALID1 — MoveIt's predicate against the compute stage's sign** | **KNOWN-DIVERGENT on BRINGUP and LINE** | **600** non-reported contacts, **every one on §2.2.1's standing pair** and **0 on any other pair**; 0 forward violations; 0 unanswered. **0 of 27 scene read-backs carry a non-zero `link_padding` or a `link_scale` other than 1.0.** |
| **REPRO1 — the compute stage as a pure function** | **NOT REPRODUCED on all three blocks** | Same-interpreter clause **byte-identical on all three**. The cross-interpreter clause fires at **6**, **21** and **57** against a **1e-12 m** tolerance — **and those are dimensionless waypoint and trajectory indices compared against a metre tolerance** (§10). **PRED6's registered clause binds this document.** |
| **REFUSE1 — what the gate refused while we watched** | **8 on LINE, 0 on BRINGUP and PICKPLACE** | Codes `INVALID_MOTION_PLAN`; 0 `planner fallback:` WARNs. **A refusal's geometry is not measurable through this door**, and a count of zero would have established nothing either. |

**What this does to [`docs/open-work.md`](../../open-work.md) #49, stated conservatively.** #49's
**margin half** is measured for the two admissible captures and for them only: over the joint
trajectories these runs produced, the shipped hull set is **never farther** from a scene object
than the vendor set anywhere measured, is **smaller by at most 0.0319444 m** where it differs, and
**no pair contacted under one geometry and cleared under the other**. That is the "cheap
settlement" #49 names — replaying the trajectories the shipped scenarios produce under both mesh
sets — carried out for `bringup` and `continuous_line`. **It is not carried out for
`pick_and_place`**, which #49 names by name and which is a measured nothing here (§2, §3).
**#49's refusal question is untouched and this document does not narrow it by one millimetre**:
the capture door is a response adapter standing **after** `ValidateSolution`, so a refused
trajectory is never published and its geometry is not measurable here. LINE's 8 refusals are
located in time and in nothing else.

**What this does to #17: nothing, and that is the registered outcome.** **#17 is not closed and
not cleared. It was not tested.** TUNNEL1's NOT OBSERVED carries rule K with it and **may not be
reported as a clearance of ADR-0027's residual.** See §7.

- **Campaign:** `docs/measurements/2026-09-04-waypoint-clearance/`
- **Branch under measurement:** `feat/close-phase-debts`. **BASE_COMMIT `c38a42c`**, and the code
  under test never moved: V1 dropped **no rows on any block** for a dirty reading, **no block is
  lost**, and `disagreed_mid_block` is **false on all three blocks** — no edit to `model/`,
  `workspace/src/`, `tools/`, `tests/`, `scripts/`, `assets/` or `external/` landed inside a
  block. **The one-writer rule held** (V10). The vendor pin
  `3dc2b5e8294758d96b54b15fa5920d581b7cbb3d` held at **both ends of all three blocks** — that tree
  is one of the two geometries measured here, so a moved pin would have changed the comparison and
  not merely the cell.
- **`criteria.md` sha256:** `e4c0351b87d937506fe540cbd8617c359993e77df7b3486b2401d0795ac84dd9` —
  **one distinct value recorded across all three blocks, and it agrees with the file on disk**
  (V9). **`criteria.md` and `harness/` are frozen from `2900259`**: `git diff 2900259..c03d64b --
  criteria.md harness/` is **empty**, checked for this write-up. The data commits are `4034492`
  (B1), `3a5796c` (B2), `5767003` (B3) and `c03d64b` (the compute stage).
- **`MODEL_HASH`** `95dbbdd9f18ca01be6a42a6f4da10e000fc29c5eeb6540396684d365550b7108`, source and
  installed identical, on every block.
- **The records that asked for it:** [`docs/open-work.md`](../../open-work.md) **#49** and **#17**,
  and behind them [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md) and
  [ADR-0027](../../adr/0027-pilz-planning-pipeline.md). **Neither ADR moves here.** Neither status
  is touched, no geometry is selected and no threshold is proposed. See §15 and §16.
- **The campaigns this one does not replace and does not edit:**
  [`2026-09-04-following-error/`](../2026-09-04-following-error/ANALYSIS.md),
  [`2026-09-03-stall-band-flip/`](../2026-09-03-stall-band-flip/ANALYSIS.md),
  [`2026-09-02-scenario-ceilings/`](../2026-09-02-scenario-ceilings/ANALYSIS.md),
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md),
  [`2026-09-01-hull-grasp/`](../2026-09-01-hull-grasp/ANALYSIS.md) and
  [`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md).
  All stay frozen, their figures are cited and never copied (P1), and **rule H forbids differencing
  any measured figure of theirs — or any figure from `criteria.md` §2.5's table — against anything
  here.**
- **This document was written from the committed `raw/` and from `harness/analyse.py`'s print, by
  someone who did not run the campaign.** That is deliberate: the write-up is built from the record
  rather than from the runner's memory. The print was regenerated for this document and read in
  full — **579 lines**, never piped through `head`.

---

## 1. What was run

**Three blocks, three captures each, in the registered order, nine scenario runs.** BRINGUP is
`./scripts/scenario bringup`, PICKPLACE is `./scripts/scenario pick_and_place`, LINE is
`./scripts/scenario continuous_line`. Each scenario starts its **own** `move_group` inside its own
process and **every run owns its own cell** (rule C-i) — the harness brings up no cell of its own
and makes no Gazebo-transport call at all (V12: `v12_gz_calls` is `0` on every row).

**216 trajectory rows were recorded, 72 per block.** The compute stage then ran **nine full
passes** — three per block, as REPRO1 requires — against both committed mesh sets: **13** collision
links per arm, **9,992** hull triangles against **98,552** vendor, **12** planning-scene objects.

| | B1 | B2 | B3 | total |
|---|---|---|---|---|
| rows recorded | 72 | 72 | 72 | **216** |
| rows admitted | 22 | 43 | 43 | **108** |
| dropped, V2 | 50 | 29 | 29 | **108** |
| dropped, V3 | 50 | 29 | 29 | **108** |
| dropped, V1 / V14 / unsealed | 0 | 0 | 0 | **0** |

**`dropped_v2` and `dropped_v3` are the same rows, and this is checked rather than inferred.** Both
rules are read out of the same description read-back, so an arm whose description came back empty
fails both. Verified directly against `raw/*_trajectories.json` for this write-up: the two failing
row sets are **identical in every block**, and **every** failing row carries `read_ok = false`,
`description_chars = 0` and `hull_collision_refs = 0`. So 108 + 108 = 216 double-counts one
population; **108 rows were dropped, not 216.**

**Trajectories by capture and arm, from the records.**

| capture | arm_1 | arm_2 | arm_3 | recorded | admitted |
|---|---|---|---|---|---|
| BRINGUP | 3 | 0 | 0 | 3 | **3** |
| PICKPLACE | 24 | 0 | 0 | 24 | **0** |
| LINE | 63 | 63 | 63 | 189 | **105** |

Two things follow that no verdict line states, and both bound how the figures below should be read:

- **BRINGUP's whole admissible set is one arm and three trajectories** — one per block. `bringup`
  plans a single `MoveTo`, and it planned it on `arm_1` only.
- **Every LINE figure is about two of three arms.** `arm_1` contributed **63 recorded and 0
  admitted** rows to LINE, because its description read back empty in all three blocks (§3).
  LINE's 105 admitted rows are `arm_2` (42) and `arm_3` (63).

**Wall clock.** Capture: B1 13 m 17 s, B2 14 m 06 s, B3 14 m 03 s — **41 m 26 s** across the three
blocks, 22:20:04Z to 23:32:12Z on 2026-09-04. Compute: **5,659.4 s ≈ 1 h 34 m** of
`compute_seconds` summed over the nine passes (B1 ≈ 400 s per pass, B2 and B3 ≈ 740 s per pass).
**The compute stage is the long pole by roughly a factor of two**, which is what `harness/README.md`
predicted from its shakedown.

---

## 2. LIVE1 — two measured captures and one measured nothing

**This was registered as the campaign's central hazard**, and it landed on one capture. A
subscription that never matched, a topic resolved into the wrong namespace and a scenario that
failed before planning anything all produce **the same empty set**, and an empty set reads as "no
trajectory came close to anything" — the reassuring answer.

**PICKPLACE is a measured nothing, and it did not fail in any of the ways rule C was built to
catch.** Its instrument was clean end to end:

- **I5 logged 24 published, 24 were received** — C-ii shortfall **0**, C-ii surplus **0**.
- **0 instrument losses of any kind** under C-iii/C-iv, against rule C's 20 % ceiling.
- **0 trajectories discarded under V5** for an empty or disagreeing scene.
- The C-i door never failed: **0 arm-blocks** failed it on any capture.

**Every one of those 24 rows was then dropped at the join**, because `arm_1` — the only arm
PICKPLACE planned on — read its description back as zero characters in all three blocks. So the
capture is not a silence produced by a broken recorder; it is 24 genuinely captured trajectories
that **no verdict may be computed from**, because nothing establishes which geometry the cell that
produced them was built from. Under rule N, **PICKPLACE's silence is evidence about nothing**: not
about the hull, not about the vendor set, not about the approach to `table_pick` that
`criteria.md` §3 put it in the campaign for.

**LIVE1's Wilson intervals are on admissible/published and are not rates of anything physical**:
BRINGUP `[0.438, 1.000]` on 3/3, LINE `[0.484, 0.625]` on 105/189, PICKPLACE `[0.000, 0.138]` on
0/24.

---

## 3. Finding 1 — the empty description read-back, and it is the third rig this has happened on

**Eight of the 27 arm-captures read `robot_description` back as zero characters.** This is a
finding in its own right and not merely an admission statistic, because it is what cost this
campaign half its rows and the whole of one capture.

| | BRINGUP | PICKPLACE | LINE |
|---|---|---|---|
| B1 | clean ×3 | **arm_1, arm_2** | **arm_1, arm_2** |
| B2 | clean ×3 | **arm_1** | **arm_1** |
| B3 | clean ×3 | **arm_1** | **arm_1** |

- **BRINGUP read all three arms cleanly in all three blocks — nine of nine.**
- **PICKPLACE and LINE did not read all three arms cleanly in any block.**
- **`arm_1` failed in six of six** — every PICKPLACE and every LINE capture.
- **`arm_2` failed twice**, both in B1. **`arm_3` never failed.**

**These are all read failures, and nothing is attributed.** `read_ok` and `v2_ok` are separate
fields in the record precisely so that *a rig that could not read* is distinguishable from *a cell
built wrongly*, and every one of the eight carries `read_ok = false` with `description_chars = 0`.
**No claim is made here that any cell was built from the wrong geometry** — the campaign cannot
tell, which is exactly why those rows are dropped rather than used. Whether the cause is the
`description_publisher` service being slow under three concurrent `move_group` processes, the
shared re-read timer of deviation 9(d), or something else, is **unestablished and was not chased**.

**This is the third occurrence across three rigs.** The 2026-09-03 stall-band-flip campaign lost
**eighteen trials** to exactly this, and the analyser prints that reminder on the rule's own line.
It is cited, not differenced (rule H).

**The harness stayed frozen, and the reason is worth recording.** B1 had already run when the
pattern was visible. Editing `harness/` after B1 would have meant B1's data was taken with a rig
that no longer exists, which is what `../README.md` rule 2 forbids and why the freeze is from the
first trial rather than from the last. The defect is therefore **carried, reported and applied
literally** — the price of the freeze, paid rather than hidden.

**Deviation 11(d) is adjacent and did not fire here:** `capture.py`'s `running_geometry` raises
`subprocess.TimeoutExpired` out of the capture loop rather than recording a failed read, so an
*unresponsive* publisher aborts a block instead of failing V2 on one arm-capture. **No block
aborted** — V8 reports every block has its `_complete.json` — so all eight failures took the
recorded-empty path and none took the abort path.

---

## 4. DELTA1, rule E and FLIP1 — what the hull changed

**Rule E held, and that is the load-bearing result of §4.** `d_hull <= d_vendor` follows from
containment (`criteria.md` §2.3), so a measurement in the other direction would falsify the
**instrument** and never the geometry. It did not occur:

| capture | largest `d_hull − d_vendor` | REVERSED pairs | against |
|---|---|---|---|
| BRINGUP | **−0 m** | 0 | `DIFF_FLOOR` 1e-9 m |
| LINE | **+2.22045e-16 m** | 0 | `DIFF_FLOOR` 1e-9 m |

LINE's `+2.22045e-16 m` is one unit in the last place of a double near 0.2–0.5 — **seven orders of
magnitude below the floor**, and it is what the floor exists to absorb. **PRED2 held.**

**DELTA1 = SMALLER on both admissible captures.**

| capture | max `d_vendor − d_hull` | on | where | hull / vendor | censored (rule M) |
|---|---|---|---|---|---|
| BRINGUP | **0.0127867 m** | `(arm_1_link3, pedestal_1)` | arm_1, traj 0, wp 48 | 0.494088 / 0.506875 m | 21,183 |
| LINE | **0.0319444 m** | `(arm_3_link3, pedestal_3)` | arm_3, traj 18, wp 2 | 0.424082 / 0.456026 m | 542,686 |

**PRED1 did not fire, and it came closer to being refuted than the print's `[did not fire]` shows.**
PRED1 predicted SMALLER on at least one capture **with the difference confined to gripper links** —
fingers, knuckles or gripper base — and named `link_base`, `link1`…`link5` as refuters. The
verdict-setting maxima on **both** captures are on **`link3`**. The analyser scores PRED1 on its
first clause, which held; **its second clause is where the mechanism was**, and the mechanism is not
the one predicted. The largest differences throughout the per-pair lists are `link3` and `link2`
against pedestals and beam housings, **not** gripper links against tables and conveyors. Stated
here rather than left in the per-pair rows, because a prediction that survives on its weaker clause
should not read as a confirmation of its stronger one.

**Rule M, and deviation 7.** The headline figures above are computed over **every evaluated pair**,
including pairs whose true distance exceeds `CENSOR` (0.500 m), because the censoring is applied to
§4.3's **bound** and not to the distance — rule M's own sentence is false of the data rather than
of the code, and it is applied as implemented and recorded as wrong (V9). The near-field
restriction is printed beside each verdict and **decides nothing**: restricted to evaluations inside
`CENSOR` under both geometries, BRINGUP's maximum falls to **0.0104835 m** and **LINE's is
unchanged at 0.0319444 m**.

**FLIP1 = NONE on both admissible captures**: 0 pairs with `d_hull <= 0 < d_vendor`, 0 with
`d_vendor <= 0 < d_hull`. **PRED3 registered in advance that a NONE evidences nothing**, and it is
recorded here in the rule's own words: a NONE **may not** be read as evidence that either geometry
is safe, that the hull changed nothing, or that #49 is closed. **A hull-only contact would have
been this campaign's most valuable single observation, and none occurred.**

---

## 5. MARGIN1 — TIGHT on both, and the substantive #49 observation

**MARGIN1 = TIGHT on BRINGUP and LINE**, stated over per-(link, object) distances. The per-pair
statement is what makes the verdict capable of coming out the other way: over an aggregate minimum,
TIGHT was guaranteed by §2.2.1's standing overlap and would have measured nothing.

| capture | non-standing pairs within `CLOSE_BAND` | (waypoint, pair) evaluations inside the band | Wilson 95 % | censored |
|---|---|---|---|---|
| BRINGUP | **3** | 15 of 7,647 = **0.001962** | [0.0012, 0.0032] | 21,183 |
| LINE | **25** | 940 of 154,814 = **0.006072** | [0.0057, 0.0065] | 542,686 |

**The substantive observation is LINE's closest approach: `0.00582921 m` — 5.8 mm — between
`arm_3_left_finger` and `conveyor_2`**, at trajectory 16 waypoint 0 in B3. It is not an outlier of
one block: the same geometry recurs across blocks and across the symmetric arm, at
**0.00583124 m** (`arm_3`/`conveyor_2`, B1), **0.0058339 m** (`arm_2`/`conveyor_1`, B2),
**0.00584051 m** (B2), **0.00584292 m** (B3) and **0.005844 m** on `arm_3_right_finger`. A second
cluster sits just under the band at **0.0199343–0.0199692 m**, on both fingers against
`conveyor_2` and `conveyor_3`, always at **waypoint 22**.

**These are trajectories `ValidateSolution` accepted**, and that is the whole point of the number:
the gate passed a path that brings a finger within 5.8 mm of a conveyor, under the geometry this
repository ships. **It is not a violation of anything** — no threshold in this campaign is a safety
limit, and `criteria.md` §0 reserves every threshold to the project owner. It is the answer to
#49's margin question for these trajectories: **the cell passes close, and it passes.**

**Both verdicts are verdicts about the near field** (rule M), stated with their censored counts
above. `CLOSE_BAND` (0.040 m) sits far inside `CENSOR` (0.500 m), so the TIGHT verdict itself is
unaffected by the censoring either way; what the restriction moves is the **denominator** of the
share, not the verdict.

---

## 6. STEP1 — LINE is COMPARABLE, and PRED4 is refuted

**STEP1 is stated per pipeline**, because #17 is a statement about Pilz and an OMPL trajectory is
re-timed by `AddTimeOptimalParameterization` — a different quantity even though both land on 0.1 s.

| capture / pipeline | verdict | max step | median | p95 | n intervals |
|---|---|---|---|---|---|
| BRINGUP / pilz | **FAR BELOW** | 0.0192488 m | 0.0177032 m | 0.0191441 m | 183 |
| LINE / pilz | **COMPARABLE** | **0.0241558 m** | 0.00849701 m | 0.0235003 m | 4,395 |
| BRINGUP / ompl | NOT EXERCISED | — | — | — | **0** |
| LINE / ompl | NOT EXERCISED | — | — | — | **0** |

**LINE's 0.0241558 m lands inside `[STEP_MID, STEP_HIGH)` = `[0.020, 0.040)` m and refutes PRED4**,
which predicted FAR BELOW on the Pilz trajectories of **every** capture. `criteria.md` registered
PRED4 as *"the weakest prediction here"* — a bare guess against an arithmetic scale — and it was
wrong. What COMPARABLE says is exactly what its verdict line says and no more: **these trajectories
stepped that far and no further.** It does **not** say a motion cannot step further, and it may not
be read as a bound on the cell.

**The attribution is clean, which is not automatic.** **Zero unattributable trajectories** on any
capture, and **zero capture records lacking the I2(c) walk**. Deviation 8 is therefore not engaged
by a shortfall: it warns that a C-ii shortfall shifts every later positional attribution on that
arm, and the C-ii shortfall is **0 on all three captures**.

**Zero OMPL intervals anywhere in the campaign.** Everything measured here is Pilz. **Nothing in
this campaign bounds what an OMPL trajectory would step**, and REFUSE1 corroborates the absence
from the other side: **0 `planner fallback:` WARNs** on every capture, so no Pilz plan fell back to
OMPL while the recorder watched.

**Finding 2 — reading (a) disagrees with the registered spacing on every LINE trajectory.** I2(a),
the interior-interval spacing, fired on **105** interior intervals on LINE and **3** on BRINGUP —
which is **one per admitted trajectory on each capture**. Reading (a) is a **corroboration only**
by registration: a trajectory it disagrees with is **reported and kept**, in the population reading
(c) assigns it, and no verdict above depends on it. It is recorded because a corroboration that
disagrees with the thing it corroborates on 100 % of trajectories is worth stating rather than
leaving in the print, and because **nothing here attributes it** — a single interval per trajectory
differing from 0.1 s is consistent with a first or last interval of a differently-timed segment, and
that is a hypothesis, not a finding.

---

## 7. TUNNEL1 and rule K — #17's answer is a refusal

**TUNNEL1 = NOT OBSERVED on both admissible captures under both geometries**: **0** sub-sample
contacts between two waypoints clear for that same pair. **And that null is refused as evidence by
the rule registered before anything was captured.**

**Rule K-ii did not find its region on any capture.** K-ii requires a consecutive-waypoint pair
carrying **both** a step `>= STEP_MID` (0.020 m) **and**, for some non-standing (link, object) pair,
a bracketing distance `<= CLOSE_BAND` (0.040 m) — **on that same interval**.

| capture | K-ii | intervals at or above the step | a non-standing pair within the band anywhere | both at once |
|---|---|---|---|---|
| BRINGUP | **FIRED** | 0 | yes | **0** |
| PICKPLACE | **NOT EVALUABLE** | 0 | no | not measured |
| LINE | **FIRED** | **595** | yes | **0** |

**LINE had 595 intervals at or above the step, and it did have near pairs — never both at the same
time.** That is the substantive shape of the result: **the cell moves fast where it is far from
everything and creeps where it is close.** The two halves separately do not make the rule, and
`criteria.md` §7.7 says why in advance: *"Moving fast far from everything tests nothing, and
creeping close to something tests nothing either; the question needs both at once."*

**A correction to how this is stated, because the print's own wording differs from the summary this
document was drafted against.** K-ii is printed **FIRED on two captures and NOT EVALUABLE on
PICKPLACE** — not "fired on all three". `NOT EVALUABLE` is a **third state** and the print's banner
says so in its opening lines: it is *not* "did not fire". PRED5's line folds PICKPLACE's third
state into "fired" — deliberately, *"because rule N says a null is not a clearance"* — and then
names it separately *"so that the write-up cannot lose it"*. It is named here. **The campaign-level
conclusion is identical either way**, because a capture that could not be evaluated has not
exercised anything: `[FIRED] K-ii over the whole campaign: NO capture exercised #17's region, so
open-work #17 STAYS OPEN on this campaign's evidence, in those words.`

**PRED5 held.** The campaign predicted **in advance** that TUNNEL1 would be NOT OBSERVED everywhere
**and that rule K-ii would fire** — that is, it predicted it would not have tested the question.
It did not test the question.

**#17 is not closed and not cleared. It was not tested.** TUNNEL1's NOT OBSERVED carries rule K
with it and **may not be reported as a clearance of ADR-0027's residual.**

**Finding 3 — the sub-sampling machinery was never exercised on campaign data.** **Zero
sub-intervals were taken**, in **every block** — checked directly across all three
`raw/*_computed.json` for this write-up, because deviation 11(c) records that the printed summary
takes the **last** block's counters rather than summing. Here the sum is **0** and so is each
block's, so the deviation does not bite; **the printed zero happens to be the true total, and that
is verified rather than assumed.** Zero ceiling hits, zero tunnel events, achieved sub-step `n = 0`.

This matters more than a zero usually does. The sub-sampling path is **the part of the compute
stage with the largest correctness surface**, and **its skip bound was found unsound before the
first trial** — deviation 5 records that the reach table omitted each link's own mesh radius and
shifted the joint offsets by one, leaving `reach[link2][joint2] = 0.0` against a mesh radius of
0.3385 m, brute-forced against the shakedown capture where the actual displacement exceeded the
bound on `link3` (0.011686 m against 0.009040 m) and on `link2` (0.002609 m against 0.000000 m). It
was corrected before the first trial. **The corrected bound then skipped every interval in the
campaign**, so the machinery below it — the interpolation, the sub-sample loop, the ceiling — ran on
no campaign data at all. **Nothing here evidences that it works**, and a future campaign that does
reach #17's region should not treat it as exercised.

---

## 8. FK1, VALID1 and GRIP1

**FK1 = AGREES on both admissible captures.** I11 is a reimplementation of forward kinematics, and
a reimplementation nothing checks is where a silently wrong frame convention lives; I12 is MoveIt's
own `RobotModel`, which is what the cell used. **They are not averaged and neither corrects the
other**, and FK1 is a conjunction over the sample, so a single disagreement would be the result.

- **600 waypoints** drawn with seed **20260904** against the registered 200 — **200 per block**,
  from pools of 962, 1,862 and 1,862.
- **600 answered, 0 unanswered** by `move_group`.
- Worst position residual **3.33067e-16 m** against 1e-6 m; worst angular **4.21468e-08 rad**
  against 1e-6 rad. **0 disagreeing waypoints.**

The position residual is at double-precision noise — ten orders of magnitude below the tolerance —
so the two implementations are not merely within tolerance, they agree to the bit on position.

**VALID1 = KNOWN-DIVERGENT on both admissible captures, and the informative direction is clean.**
The reverse clause counted **600 non-reported contacts, every one on §2.2.1's standing pair
`(arm_N_link_base, pedestal_N)` and 0 on any other pair.** The standing pair is *expected* to
violate it, which is why it is KNOWN-DIVERGENT rather than a result; **any other pair violating it
would have been INCONSISTENT and a finding**, and none did. The forward clause had **0 instances**,
exactly as registered — §2.2.1 makes its antecedent false at every waypoint. **0 sampled waypoints
went unanswered**, and **0 of 27 scene read-backs carry a non-zero `link_padding` or a `link_scale`
other than 1.0**, so the sufficient explanation for an inconsistency is measured absent rather than
assumed absent.

**Finding 4 — GRIP1 exceeds `CLOSE_BAND` on both admissible captures.** Every distance involving one
of the six moving gripper links is recomputed with the drive joint at 0 and at 0.85 rad, all five
mimic followers moved with it.

| capture | gripper-link pairs measured | largest change over the declared range | against `CLOSE_BAND` |
|---|---|---|---|
| BRINGUP | 72 | **0.0447471 m** — `(arm_1_left_finger, beam_pick)` | 0.040 m |
| LINE | 120 | **0.0452507 m** — `(arm_3_left_finger, beam_c2_out)` | 0.040 m |

**GRIP1 decides nothing by registration** and no verdict above is computed from it. It is stated
plainly anyway: **the pose uncertainty contributed by one unmodelled gripper completion is larger
than the entire band the #49 question is framed in.** The distances in §5 are computed at the drive
position the trajectory carries, so this is a sensitivity and not an error bar on those numbers —
but any future rule that keys on `CLOSE_BAND` for a **gripper** link is keying on a band narrower
than the gripper's own configuration sensitivity, and that should be decided deliberately rather
than inherited. `arm_N_xarm_gripper_base_link` is **fixed** and outside GRIP1's scope; it appears in
every other distribution like any other link, which is why §5's BRINGUP row can name it.

---

## 9. REFUSE1 — a count, and a door that cannot see what it counts

**REFUSE1 = 8 on LINE** (codes `INVALID_MOTION_PLAN`), **0 on BRINGUP**, **0 on PICKPLACE**; **0
`planner fallback:` WARNs anywhere.**

**A refusal's geometry is not measurable through this door.** MoveIt's pipeline breaks the
response-adapter chain on the first failure and `ValidateSolution` stands **before**
`DisplayMotionPath`, so a refused trajectory is **never published** and never reaches the recorder.
REFUSE1 locates refusals in time and says nothing about how close anything was.

**So the campaign's registered bound stands, and the count does not soften it: a plan the hull set
refuses and the vendor set would have accepted cannot be seen through this door.** The 8 refusals
are 8 events whose geometry is not measurable here. **A count of zero would have established
nothing either** — that is why the rule carries no threshold. `criteria.md` §8 names what would
settle it, and this campaign is not it.

---

## 10. REPRO1 = NOT REPRODUCED — the verdict, its diagnosis, and what it forbids this document

**REPRO1 failed on all three blocks, and the registered consequence binds this write-up.** It is
recorded here in full, because a bare "NOT REPRODUCED" would tell a reader something false.

| block | same interpreter | second interpreter: worst numeric difference | tolerance | verdict |
|---|---|---|---|---|
| B1 | **byte-identical** | **6** | 1e-12 m | **NOT REPRODUCED** |
| B2 | **byte-identical** | **21** | 1e-12 m | **NOT REPRODUCED** |
| B3 | **byte-identical** | **57** | 1e-12 m | **NOT REPRODUCED** |

`numpy` **2.1.3** against **1.26.4**; both interpreters report Python 3.12.3.

**The same-interpreter clause passed on all three blocks, byte for byte** (deviation 6: only
`compute_seconds`, the interpreter string and the self-test reference are excluded; **every measured
quantity is compared byte-for-byte**). Deviation 9(c) notes that the same-interpreter clause is the
one that would catch a truncated run, and it is the clause that held.

### 10.1 The diagnosis — and it must travel with the verdict

**6, 21 and 57 are not distances. They are dimensionless waypoint and trajectory indices, compared
against a metre tolerance.** `_worst_numeric_difference` walks **every** numeric leaf of the
compute document, and the argmax bookkeeping fields — `largest_delta.waypoint`,
`largest_delta.trajectory`, `grip1_largest_change.trajectory` — are integers sitting in the same
walk as the metres.

**Verified independently for this write-up, by differencing `raw/*_computed.json` against
`raw/*_computed_second.json` directly:**

- The **worst** difference in each block is an **index**: B1 `pairs/LINE/arm_3/[1]/largest_delta/waypoint`
  4 against 10; B2 a `largest_delta.trajectory` 14 against 35; B3 a
  `largest_delta_near_field.waypoint` 0 against 57.
- **Every** case where an index and its reported distances move is a pair whose **delta is
  numerically zero**. At B1's worst, the delta is **5.551e-17 m** at one location and **1.110e-16 m**
  at the other; at B3's largest distance excursion, **0.000e+00 m** against **5.551e-17 m**. Two
  `numpy` versions break an **argmax tie over a constant-zero array** differently and report a
  different `(trajectory, waypoint)` **for the same non-difference**.
- Excluding the argmax bookkeeping records, **the worst numeric difference anywhere in any block is
  4.44089e-16 m** — last-bit double precision, **four orders of magnitude below REPRO1's own 1e-12 m
  tolerance** and seven below `DIFF_FLOOR`. That covers every distribution summary (`min`, `max`,
  `median`, `p95`, `p99`), every `delta_m`, every `distance_m`, every `change_m` and every FK pose.
- **The headline DELTA1 maxima are bit-identical between interpreters**, location included:
  BRINGUP `0.012786707071593073` on `(arm_1_link3, pedestal_1)` at traj 0 wp 48, and LINE
  `0.031944367597948276` on `(arm_3_link3, pedestal_3)` at traj 18 wp 2 — **the same float and the
  same argmax in both runs.**

**A reader must not take NOT REPRODUCED to mean the instrument disagrees with itself about
distances. It does not.** Had the comparison been restricted to quantities carrying metres, it
would have passed with four orders of magnitude to spare. What it caught is that a **tie-break over
a null difference is not stable across `numpy` versions**, and that the location fields reporting
that tie are compared against a length tolerance.

**The rule is nevertheless applied literally and recorded as failing** (V9). `criteria.md` §7.6
says *"a failure of either is reported and no figure from that run is published as a measurement"*,
and nothing in it exempts a difference whose units are wrong. **A threshold discovered to be wrong
is applied literally**, and this one is.

### 10.2 What PRED6 forbids, worked out from `criteria.md` rather than assumed

PRED6's refuter reads: *"either failing, in which case **no distance verdict is published for the
affected captures**."*

**Which captures are affected: all three.** REPRO1 is evaluated **per block**, and it failed on
**B1, B2 and B3**. Every capture draws its rows from all three blocks — BRINGUP 1 + 1 + 1, LINE
21 + 42 + 42 — so **no capture is composed only of unaffected blocks**, and there is no clean subset
to publish. PICKPLACE is affected too, and is separately NOT ADMISSIBLE.

**What "published as a measurement" forbids, applied here.** The distance verdicts are §7.2's
DELTA1 and FLIP1, §7.3's MARGIN1, and §7.4's TUNNEL1 and GRIP1 — everything the compute stage
produces in metres. Under PRED6 **none of them is published as a measurement by this document**.
Concretely:

- **They are reported, with the NOT REPRODUCED flag attached**, because `criteria.md` §7.6 requires
  the failure to be *reported*, and rule N forbids the campaign's silence being read as a
  clearance. Suppressing them entirely would replace a flagged number with a null that reads as
  reassurance — the exact failure mode LIVE1 exists to prevent.
- **None of them may be cited outside this directory as a measured figure**, quoted into an ADR,
  into `CLAUDE.md`, into `docs/open-work.md` or into any layer document, or used to set, move or
  justify any threshold, tolerance or ceiling.
- **No item is closed on them.** §15 states what stays open, and #49's margin half is described
  there as *measured under a failed reproduction clause*, not as settled.

**This is the strictest reading available and it is the one taken**, in preference to arguing from
the diagnosis in §10.1 that the affected quantity is not a distance. The diagnosis explains the
verdict; **it does not overturn it**, and `criteria.md` gives this write-up no authority to decide
that a registered rule should not have fired.

---

## 11. V6 fired on LINE's DELTA1, and the downgrade is applied here

**Deviation 9(b) records that the analyser prints V6's finding and applies no downgrade — it is
left to this document. It is applied now.**

| capture | MARGIN1 | DELTA1 | STEP1 |
|---|---|---|---|
| BRINGUP | false | false | false |
| PICKPLACE | — | — | — |
| LINE | false | **true** | false |

**`DELTA1[LINE]` is downgraded to INCONCLUSIVE.** V6's own registered wording is *"that metric's
finding is downgraded to INCONCLUSIVE whatever any statistic says"*, and the summary table at the
top of this document carries the downgrade.

**The spread that fired it, computed from `raw/` for this write-up.** LINE's per-block DELTA1
maxima are **0.03194009403298931** (B1), **0.03193813675916701** (B2) and **0.031944367597948276**
(B3) — a between-block spread of **6.230839e-06 m** against DELTA1's rule-R minimum interesting size
of **1e-9 m** (`DIFF_FLOOR`). BRINGUP's spread is **1.131317e-13 m** and does not fire, which
reproduces the print exactly.

**This over-reports rather than under-reports, and deviation 9(a) is why.** V6 **as implemented**
compares the between-**block** spread of a metric's per-block extreme against **rule R's minimum
interesting size**; V6 **as worded** compares the between-block difference against the
**between-capture** difference. Those are different quantities, and the implemented one **fires more
readily**. The direction of the error is stated because it decides how the downgrade should be
read: **INCONCLUSIVE here is a conservative verdict, not a discovered instability.**

**Two things the downgrade does not reach, and the distinction is not invented for convenience.**

- **Rule E is a separate printed rule with its own verdict**, and V6 fired on DELTA1, not on rule E.
  Containment held on both captures, and it is backed by a property of the derivation rather than by
  a statistic.
- **`DELTA1[BRINGUP]` is not downgraded** — V6 did not fire on it.

**And the honest reading of the magnitude.** The three blocks' maxima agree to about **6 µm on a
32 mm quantity** — roughly two parts in ten thousand. **The downgrade fires because DELTA1's
minimum interesting size is `DIFF_FLOOR`, a floor set at arithmetic-noise scale**, so essentially
any real between-block variation exceeds it. That is a property of the size table, registered in
advance and applied literally, and it is **not** evidence that the blocks disagreed materially. Both
sentences are true and both are stated: **the verdict is INCONCLUSIVE, and the blocks agree to six
micrometres.**

---

## 12. V7 fired on all three blocks, so its comparison cannot be performed at this n

**V7 flags a block if any load reading at either end exceeds 4.0 on 16 cores. All three blocks are
flagged.**

| block | load at start (1 m / 5 m / 15 m) | load at end (1 m / 5 m / 15 m) | flagged by |
|---|---|---|---|
| B1 | 0.171 / 0.245 / 0.253 | 2.704 / **4.329** / 2.780 | end, 5 m |
| B2 | 0.524 / 0.841 / 1.530 | 2.853 / **4.447** / 3.439 | end, 5 m |
| B3 | 1.127 / 3.534 / 3.195 | 1.950 / **4.209** / 3.882 | end, 5 m |

Every block opened below the threshold and crossed it by its closing reading, on the five-minute
average, on the host's own `/proc/loadavg` read from inside the container — which on this host is
the host's reading, for the reason `criteria.md` §9 records.

**V7 requires that every verdict a flagged block contributes to be reported with and without the
flagged blocks. All three blocks are flagged, so the complement is empty and the comparison cannot
be performed.** There is no unflagged subset to compare against: removing the flagged blocks
removes every row.

**This is stated as unperformable at this n rather than reinterpreted.** It is not "V7 passed", not
"load had no effect", and not a licence to substitute a different comparison — comparing B3 against
B1 because B3 opened louder would be a different rule, and inventing one after the data is what V9
forbids. **No block is discarded for load** (V7 flags and never excludes), so the 108 admitted rows
are unaffected and every verdict above stands on all three blocks.

**It is the direct cost of running three blocks on one host that could not be quieted**, and it is
the campaign's own doing: the load at each block's close is the campaign's own three scenarios and
its own compute. Whether load moved any figure here is **unmeasured and unmeasurable at this n**.

---

## 13. V2 and V3's scope — both readings, side by side

**A reader must see which reading produced the 108.**

**The registered per-capture reading (deviation 1), which is what every number above rests on.**
V2, V3, V4 and V5 are read **per capture**, and the reading travels on every row the cell that
produced it produced. `criteria.md` §4.1 words I3 and I4 as *"per arm per block"* and V2/V3/V4 as
**block** rules, which was written against the shape of the frozen following-error rig — **one cell
per block**. Rule C-i's own restatement establishes the opposite here: **each scenario starts its
own `move_group` and every run owns its own cell**, so a block has **three cells** and there is no
single description, no single scene and no single matched publisher for a block-level reading to be
*about*. Reading once per block would have recorded whichever cell happened to be up.

**Under that reading: 108 of 216 rows survived**, and the campaign has two admissible captures.

**Under §10's literal block wording: all three blocks would be discarded whole.** V2 and V3 each
say *"a block that disagrees is **discarded and reported**"*, and **every block carries at least one
failed read-back** — B1 four, B2 two, B3 two (§3). So the literal block reading yields **0 admitted
rows, 0 admissible captures and no verdict in §7.2–§7.5 at all.**

**No threshold moved and no rule was weakened by the per-capture reading.** Every clause is applied
exactly as written, to the cell it is a statement about, and a block-level summary remains
recoverable from the record by conjunction. **But the difference between the two readings is the
whole campaign**, and it is registered as a deviation rather than discovered here: had the rig read
once per block, this document would report nothing.

---

## 14. Deviations, and the other findings

**Eleven deviations were registered before the first campaign trial** and are printed in full at the
head of `harness/analyse.py`'s output. They are not restated here (P1); the ones that bear on a
verdict are cited where they bear on it — **1** (§13), **5** and **11(c)** (§7), **6**, **9(c)** and
the index walk (§10), **7** (§4, §5), **8** (§6), **9(a)** and **9(b)** (§11), **9(d)** and **11(d)**
(§3). **Every one was applied to data already collected, and none moved a threshold.**

The numbered findings, collected:

- **Finding 1 — the empty description read-back.** §3. Eight of 27 arm-captures, `arm_1` in six of
  six, the third rig this has happened on, **all read failures, nothing attributed.**
- **Finding 2 — I2(a) disagrees with the registered spacing on every admitted trajectory.** §6.
  105 intervals on LINE, 3 on BRINGUP; a corroboration only, reported and kept, unattributed.
- **Finding 3 — the sub-sampling machinery was never exercised.** §7. Zero sub-intervals in every
  block, on the part of the compute stage with the largest correctness surface, whose bound was
  found unsound before the first trial.
- **Finding 4 — GRIP1 exceeds `CLOSE_BAND` on both admissible captures.** §8. 0.0447 m and
  0.0453 m against a 0.040 m band. Decides nothing by registration; stated because it is a pose
  uncertainty larger than the band the whole #49 question is framed in.
- **Finding 5 — nine of nine scenario runs failed their teardown assertion.** All nine, with an
  **identical signature**: `AssertionError: -15 not found in [0, 130, -11] : move_group-15 exited
  with -15`, in `TestCleanShutdown.test_nothing_of_ours_exited_badly`. **The cycle assertions
  passed in all nine** — every verdict line reads `failed — 1 teardown assertion(s) failed`, and
  none reports a cycle failure. **`criteria.md` §3 and rule T are explicit that a scenario's own
  verdict does not gate its capture**, so this discards nothing and admits nothing: every trajectory
  captured before a scenario failed is still a trajectory this cell produced. **Nine for nine is
  not a flake rate and no rule in this campaign is about it.** It is **not attributed** — the
  exemption set covers `-11` and this is `-15` (SIGTERM), a different signature from the teardown
  signal family recorded elsewhere in this tree, and one campaign observing it nine times on one
  host at one commit establishes neither a cause nor a rate.
- **Finding 6 — rule C-i's before-first-plan clause was NOT EVALUABLE on 12 of 27 arm-blocks.** Six
  on BRINGUP (`B1/arm_2`, `B1/arm_3`, `B2/arm_2`, `B2/arm_3`, `B3/arm_2`, `B3/arm_3`) and six on
  PICKPLACE (the same six); **zero on LINE**. Deviation 2 registers why: the clause orders two
  events observed by two different instruments — a matched publisher on the recorder's wall clock
  and a log line written by `move_group` — and **nothing in the tree emits a common ordering
  token**, so where the `Calling Planner` line carries no parsable `rcutils` timestamp the clause
  prints NOT EVALUABLE rather than passing by default. **On those twelve the door clause is carried
  by its ceiling half alone.** The door itself never failed: **0 arm-blocks failed C-i** on any
  capture.
- **Finding 7 — PRED1 survived on its weaker clause.** §4. The verdict-setting differences are on
  `link3` on both captures, not on the gripper links PRED1's mechanism named.
- **Finding 8 — the argmax tie-break is not stable across `numpy` versions.** §10.1. It is what
  REPRO1 caught, it moves no distance, and it is worth recording as a property of the compute
  stage's **reporting** rather than of its arithmetic.

---

## 15. What this campaign does not establish

- **It did not test #17.** Rule K-ii found its region on no capture. **TUNNEL1's NOT OBSERVED may
  not be reported as a clearance of ADR-0027's residual**, and #17 stays open in the analyser's own
  words.
- **It did not close #49.** The margin half is **partially measured** — on two captures, under a
  failed REPRO1 clause (§10.2), on trajectories from two of three arms on LINE and one arm on
  BRINGUP. **The refusal half is untouched**: a plan the hull set refuses and the vendor set would
  have accepted **cannot be seen through this door**, because a refused trajectory is never
  published. LINE's 8 refusals do not narrow it and a count of zero would not have either.
- **It measured nothing on PICKPLACE**, which `criteria.md` §3 put in the campaign for the approach
  to `table_pick` where the gripper comes closest to furniture. **That question is unmeasured.**
- **It says nothing about OMPL.** Zero OMPL intervals were captured.
- **Every figure is a property of the trajectories these nine scenario runs produced** — on this
  host, at this commit, in this image, with this scene and this arm model, and **of nothing else**
  (rule G). It is **not** a property of the cell's reachable motions: another goal, another start
  state, another physics roll produces another trajectory set. **It is not evidence about
  hardware** — the layout is `PROVISIONAL` and the physical scan is Phase 3. **Nothing here is a P2
  result.**
- **A clean clearance here is not a safety case, and hulls may never be cited as margin.**
- **One machine.** Linux 7.0.0-30-generic, x86_64, 16 cores, 31 GiB RAM; Docker 29.7.2; image
  `cite-digital-twin:dev`, Ubuntu 24.04.4 LTS, ROS 2 Jazzy; MoveIt **2.12.4**; `ros_gz_sim`
  **1.0.22**; `rmw_fastrtps_cpp` **8.4.4**; the sourced `gz sim` is **8.11.0**. Compute-stage
  interpreters: container `numpy` **1.26.4** / `scipy` **1.11.4** and host `numpy` **2.1.3** /
  `scipy` **1.14.1**. `ROS_DOMAIN_ID` 43; the container is **not** CPU-limited. **Three blocks on
  one host, nine scenario runs, no thresholds moved.**

## 16. What this campaign does not decide

**This campaign decides nothing, and §0 reserves every threshold to the project owner.**

- **It moves no threshold, no tolerance and no ceiling** — not a scenario wall-clock ceiling, not a
  velocity or acceleration scaling factor, not a tolerance in a generated controller file. **No
  scenario ceiling was widened to absorb anything here, and none may be.**
- **It selects no geometry.** `description.collision.select` stays at the shipped `convex_hull` and
  was not flipped.
- **It promotes nothing. ADR-0028 is `Accepted` and this campaign does not touch that; ADR-0027's
  residual is that record's and the project owner's. Neither status moves here.**
- **It proposes no fix for #17.** Lowering a velocity scaling, densifying a trajectory before
  validation and changing the layout are the levers that item names; **this campaign evaluates none
  of them, recommends none of them and may not be cited as support for any of them.**
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/`, `scripts/`, `assets/` or `external/`
  was edited.** The cell was measured exactly as the tree at `c38a42c` ships it.
- **It takes no position** on the grasp predicate, the friction grasp, the line's dead ends or the
  real-time floor. Those have their own records and their own campaigns.

---

## 17. Reproduction

The capture stage is `harness/run_campaign.sh`; `harness/README.md` carries every command,
including the one-block-at-a-time form, the three compute passes REPRO1 needs and the FK
cross-check. Every figure in this document comes from:

```sh
python3 docs/measurements/2026-09-04-waypoint-clearance/harness/analyse.py
```

which applies `criteria.md` §7's rules to `raw/` and **prints every rule whether or not it fires** —
**579 lines**, carrying 11 deviations, the quoted rules, every verdict and the per-pair lists.
**It must be redirected to a file rather than piped through `head`**: a previous campaign's
operator piped a 1034-line report through `head`, saw 143 lines, and `tee` still reported exit 0.
**A truncated print looks exactly like a rig with fewer rules.**

Nothing here was derived by hand from files the analyser does not print, except where a figure is
quoted directly from `raw/` and named as such: §1's block timestamps, wall clocks and per-capture
row counts; §1's verification that V2's and V3's dropped row sets are identical; §7's per-block
sub-sampling counters, read directly because deviation 11(c) reports only the last block; §10.1's
cross-interpreter difference walk over `raw/*_computed.json` against `raw/*_computed_second.json`;
§11's per-block DELTA1 maxima and their spread; §12's load readings from `raw/*_header.json` and
`raw/*_complete.json`; and §14's teardown assertion lines from `raw/logs/*.log`.

**The shakedown under `raw/shakedown/` is not data.** It is excluded from every figure above by
three independent refusals in the analyser, and it may not be used to set or adjust any threshold.
What it found is in [`raw/shakedown/NOTES.md`](raw/shakedown/NOTES.md), including the residual that
the committed harness is not byte-identical to the one that ran it.

**Figures stay in this directory.** Nothing here is copied into
[ADR-0027](../../adr/0027-pilz-planning-pipeline.md),
[ADR-0028](../../adr/0028-convex-hull-collision-meshes.md), `CLAUDE.md`,
[`docs/open-work.md`](../../open-work.md), the generated comments or any layer document (P1).
**Cite the directory.**
