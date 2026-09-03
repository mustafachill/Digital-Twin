# Where option F's window flips: the narrow edge bracketed to 0.05 mm, the wide edge lost to one empty read-back

**Verdict, in this campaign's own terms.** Every one is `criteria.md` §7's registered rule
applied by `harness/analyse.py` to `raw/`, and every one is stated **per arm** — rule T: the
arms are not each other's evidence.

| Quantity | Verdict | In one line |
|---|---|---|
| **LO1 — the narrow edge** (arm LO, block LO-F, refining `holding_F`) | **BRACKETED at (47.60, 47.65] mm** | The registered 0.05 mm width. Both endpoints **n = 3 collected / 3 surviving**, unanimous — `false` at 47.60 on all three repeats, `true` at 47.65 on all three — and every rule-B conjunct satisfied at both. **Rule D: the bracket CONTAINS the computed `edge_lo` of 47.615000 mm.** |
| **HI1 — the wide edge** (arm HI, block HI-F, refining `holding_F`) | **NOT BRACKETED, rule N fires** | Block HI-F was **discarded whole** under V2, so no pair of adjacent fine-grid stops survives. Not bracketed at 0.05 mm, over these stops, **at n = 0 surviving of 18 collected**, on this rig. **Rule D is NOT EVALUABLE here.** |
| **`flip_S_lo` — the superseded predicate's narrow flip** (block LO-S, refining `holding_S`) | **BRACKETED at (47.10, 47.15] mm** | **n = 3/3** at both endpoints. **Rule D: the bracket CONTAINS the computed closed-form floor of 47.121519 mm.** This is a secondary quantity; the gate does not ask for it. |
| **FLOOR1 — the distance from the narrow flip to the floor** | **REPORTED, no pass/fail** | `flip_F_lo` lies **above** the floor — the direction ADR-0052 §A.6's subset argument depends on — at **(+0.478481, +0.528481) mm**. §A.6 sets no minimum distance and this campaign may not invent one (§0). |
| **INV1 — command invariance** | **NOT EVALUABLE** (deviation 8) | **2 of 4** INV stops had a shipped-command counterpart to compare against; 52.35 and 52.40 mm had none, because their counterpart is block HI-F. **No disagreement was found among the 2 compared stops** — which is not the sentence "INV1 HELD", and P5 is NOT EVALUABLE rather than confirmed. |
| **CTL — the controlled comparison** | **REPORTED, no verdict** (§7.4) | Terminated at **0.29999997 rad / 60.915272 mm**, `stalled`, `¬reached_goal`, `¬holding_F`, `holding_S`, no stop warning. **Not evidence about [`docs/open-work.md`](../../open-work.md) #25 in either direction**, and not powered to be. |

**What that does to the gate, stated plainly and conservatively.**
[ADR-0052](../../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) §A.10 item 2's
second bullet asks for *"the stop sweep re-run, which stops F admits, and the flip bracketed to
at least 0.05 mm against the floor §A.6 derives"*. **At the narrow edge, both halves are
delivered**: every stop's verdict is tabulated at both grids in §4, and the flip is bracketed to
the gate's own 0.05 mm with FLOOR1 reported against a floor computed here. **At the wide edge,
rule N's own words apply and this write-up states them: not bracketed at 0.05 mm, over these
stops, at n = 0 surviving, on this rig; the campaign's silence there may not be read as
agreement with §2.2's arithmetic, as validation of either band value, or as evidence that the
edge is where the declaration says; §A.10 item 2's second bullet is then still unmet, and this
document says so in those words.** The bullet names the flip **singular** and this campaign
reports **two** edges; whether the bullet's singular flip means the narrow one alone is a
reading for that record and its owner, not for this campaign to take (§0). **This document
therefore reports the bullet as HALF closed and does not write, or imply, that the gate is
closed.**

- **Campaign:** `docs/measurements/2026-09-03-stall-band-flip/`
- **Branch under measurement:** `feat/close-phase-debts`. **BASE_COMMIT `c38a42c`**, and the code
  under test never moved: `v1_clean` is `true` on **all 105 rows**, with the two `git` readings
  agreeing at both ends of every cycle, `head_moved_mid_block` false on every row, and the
  running cell's `MODEL_HASH` (`95dbbdd9…`) identical between source and install everywhere.
  `HEAD` advanced across blocks — seven distinct heads, from `8a35a03` to `ac449c8` — which V1
  permits and expects, because it watches `model/`, `workspace/src/`, `tools/`, `tests/` and
  `scripts/` and this campaign's own files land under `docs/measurements/`.
- **`criteria.md` sha256:** `5e9c3f0a474c7cb05f4d8d719993be69d588885291740fbf0f1fc9e50cec9f23`.
  **One distinct value across every cycle end of every record, and it agrees with the file on
  disk** (deviation 11). Committed **alone** in three commits — `5789ba8`, then the two
  amendments `a197275` and `554a8a9` — all before the harness existed and before any trial ran;
  both amendments are recorded in the file's own header. The harness is frozen from `8a35a03`:
  `git log 8a35a03..HEAD -- harness/ criteria.md` is **empty**. The seven data commits are
  `e03c24e` (LO-C), `f70da8b` (HI-C), `eb842b4` (LO-F), `68fc878` (HI-F), `f6c6ab5` (LO-S),
  `ac449c8` (INV) and `4435015` (CTL).
- **The record that asked for it:** ADR-0052 §A.10 item 2, second bullet, **and nothing else in
  §A.10**. **Its status does not move here and nothing about the band, the monotonicity term or
  either edge is decided.** See §11 and §12.
- **The campaigns this one does not replace and does not edit:**
  [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/ANALYSIS.md) and
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md). Both stay frozen;
  their figures are cited and never copied (P1), and **rule H forbids differencing any measured
  figure of theirs against anything here.**
- **This document was written from the committed `raw/` and from `harness/analyse.py`'s print,
  by someone who did not run the campaign.** That is deliberate — the write-up is built from the
  record rather than from the runner's memory — and §10 states what it costs under V10.

## 1. What was run

| block | arm | grid | `w_cmd` | stops | repeats | collected | surviving |
|---|---|---|---|---|---|---|---|
| **LO-C** | LO | coarse 0.25 mm, 46.00–48.00 mm | 45.000 mm | 9 | 2 | 18 | **18** |
| **HI-C** | HI | coarse 0.25 mm, 52.00–54.00 mm | 45.000 mm | 9 | 2 | 18 | **18** |
| **LO-F** | LO | fine 0.05 mm, [47.50, 47.75] mm | 45.000 mm | 6 | 3 | 18 | **18** |
| **HI-F** | HI | fine 0.05 mm, [52.25, 52.50] mm | 45.000 mm | 6 | 3 | 18 | **0 — discarded under V2 (§2)** |
| **LO-S** | LO | fine 0.05 mm, [47.00, 47.25] mm | 45.000 mm | 6 | 3 | 18 | **18** |
| **INV** | INV | the four straddling stops | **40.000 mm** | 4 | 3 | 12 | **12** |
| **CTL** | CTL | no stop, plain `mock_components/GenericSystem` | 45.000 mm | 1 | 3 | 3 | **0 — V14 fires structurally (§8)** |

**105 trials collected, 84 surviving, across 5 contributing blocks** (V8, from the print).
Every trial is one launch of a real `ros2_control_node`, a real `move_group` and the real skill
server over `cite_test_hardware/JointStopSystem`. **There is no simulator in this rig at all** —
no Gazebo, no physics, no work-piece, and no `/clock`. `raw/shakedown/` is excluded from every
figure here by the analyser's own top-level glob (`criteria.md` §10).

**Every verdict is read from the shipped predicate, never from a copy.** `Grasp.Result.holding`
**is** `cite_skills::gripper_is_holding`'s return value and `Grasp.Result.reached_width_m` **is**
`gripper_width_for(result->position)`. `holding_S` comes from a **build** of `4ef2d7c`, not a
rewrite. `analyse.py` imports no arithmetic module and starts no front end; every width, edge and
floor it prints is read off a record that carries it.

**The four L0 statements option F is made of, as every record carries them:** declared part
interval **50.0 / 50.0 mm** (degenerate), window **`edge_lo` 47.615000 mm / `edge_hi`
52.385000 mm**, computed floor **47.121519 mm**. The **§2 cross-check passed on all seven
blocks**: the shipped code, asked through the compiled front end, reproduces `criteria.md` §2's
whole table — both window edges, both drive positions, the discrimination margin, the validator
ceiling and the floor.

**V13 found the production backend `gz_ros2_control/GazeboSimSystem` before every substitution,
on every launch of every block**, including the discarded one.

## 2. V2 discarded a whole block on one trial, and the failure is in the instrument

Reported first, because it decided one of this campaign's two headline results and three
downstream verdicts with it.

| trial | cycle | `w_stop` | `v2_ok` | `hull_collision_refs` | `description_chars` | `i1_result_code` | V1 | V4 | V5 | V13 | V14 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **HI-F 15** | 2 | **52.35 mm** | **False** | **0** | **0** | 0 | clean | pass | pass | pass | pass |
| the other 17 | 0, 1, 2 | 52.25–52.50 mm | True | **13** | 22 608–22 609 | 0 | clean | pass | pass | pass | pass |

V2 reads the description back off the **running** node with
`ros2 param get /cite/cell_a/arm_1/description_publisher robot_description` and counts collision
references under `cite_description/meshes/collision/xarm5/convex_hull`: **13** for the shipped
`convex_hull` selection ([ADR-0028](../../adr/0028-convex-hull-collision-meshes.md)). On trial 15
that call **returned zero characters**, so the count read 0 against 13 and `v2_ok` is `False`.

**V2 did the right thing with what it was given.** It is a conjunction of two **positive**
findings by construction — `len(running) > 0 and hulls == 13` — so *"no vendor mesh found"* is
not reachable by not looking, and an unreadable answer fails closed. **The trial is otherwise
sound in every other instrument:** `i1_result_code` 0, the stop announced at 0.383197 rad (I5),
no start-outside-the-stops refusal (I6), the joint resting on its stop with an I7 error of
**0.000000 mm**, I4 agreeing with I2 and I1 (V14), the two width instruments agreeing to
**0.000000 mm** (V4), and `v1_clean` true at both ends of its cycle.

**And the rig's own description text on that same trial carried 13 hull references.**
`rig.hull_collision_refs_in_text` reads **13** on trial 15, as on all eighteen: the description
the harness substituted and launched was the shipped one. What failed was the read-back of it
from the running node, not the description.

**V2's stated rationale is not what happened here.** `criteria.md` V2 discards a disagreeing
block because *"the rig would be built from a description this repository does not ship"*. This
rig was built from the description this repository ships — V13 passed on that launch, the
substituted text carried 13 references, and 17 of 18 read-backs returned 13.

**What the discard cost, in full.** Eighteen otherwise sound trials; **HI1**, one of the
campaign's two headline results; **INV1**, which lost the counterpart of 2 of its 4 stops and is
NOT EVALUABLE as a result; and **P1**, which is NOT EVALUABLE for the same reason (§9). One
transient empty read-back on 1 trial in 18 removed all four. Deviations 15, 16 and 18 in §9 are
where that is carried.

**Nothing here attributes the empty read-back.** Whether the parameter service was not yet
serving, the node was absent, or the call itself failed is **not established**: `running_geometry`
reads `subprocess.run(...).stdout` and checks neither `returncode` nor `stderr`, so `raw/` cannot
answer it (deviation 16). `harness/README.md` limitation 8 states the ambiguity in advance.

## 3. LO1 — the narrow edge, BRACKETED at (47.60, 47.65] mm

`w_reached` is I1, at full precision; every rest error below is I7 against the drive position the
fixture actually declared, at the 0.005 mm tolerance §7.0 registers.

**Block LO-C, the coarse grid, `w_cmd` = 45.000 mm, n = 2 per stop.** `w_reached` equals `w_stop`
exactly at every stop and I7 reads +0.000000 mm at every stop. This table is the gate's *"which
stops F admits"* half at 0.25 mm on the narrow side.

| `w_stop` | 46.00 | 46.25 | 46.50 | 46.75 | 47.00 | 47.25 | 47.50 | 47.75 | 48.00 |
|---|---|---|---|---|---|---|---|---|---|
| `stalled` | **false** | true | true | true | true | true | true | true | true |
| `reached_goal` | **true** | false | false | false | false | false | false | false | false |
| `holding_F` | false | false | false | false | false | false | false | **true** | **true** |
| `holding_S` | false | false | false | false | false | **true** | **true** | true | true |

**Rule U on LO-C: exactly one change of `holding_F`, at `(47.50, 47.75)`, and exactly one change
of `holding_S`, at `(47.00, 47.25)`** — which is what located LO-F's and LO-S's refinement
intervals respectively. Rule R is DETERMINATE on both predicates, with a largest within-stop
`w_reached` spread of **0.000000 mm** against the 0.100 mm MIS.

**The 46.00 mm row is the registered controller-branch fact and not an anomaly.** `criteria.md`
§5.1 recorded before any trial that at this stop the drive joint rests 0.009389 rad from the
position a 45.000 mm command asks for, against a `goal_tolerance` of 0.01 rad, so the controller
terminates on its **goal-tolerance** branch — `reached_goal = true`, `stalled = false`, no stall
at all — and that 46.00 mm is the only stop in either grid inside that boundary. The trial is
valid data: I5, I6 and I7 are satisfied and V5 passes; `holding_F` is false there twice over, by
the first condition and by the window alike; and rule U is unaffected.

**Block LO-F, the refinement, `w_cmd` = 45.000 mm, n = 3 per stop:**

| `w_stop` | `w_reached` (I1), all repeats | I7 rest error | `stalled` | `reached_goal` | `holding_F` | `holding_S` | I5 | I6 |
|---|---|---|---|---|---|---|---|---|
| 47.50 mm | 47.500000 mm ×3 | +0.000000 mm | true | false | **false** | true | true | false |
| 47.55 mm | 47.550000 mm ×3 | +0.000000 mm | true | false | **false** | true | true | false |
| **47.60 mm** | 47.600000 mm ×3 | +0.000000 mm | true | false | **false ×3** | true | true | false |
| **47.65 mm** | 47.650000 mm ×3 | +0.000000 mm | true | false | **true ×3** | true | true | false |
| 47.70 mm | 47.700000 mm ×3 | +0.000000 mm | true | false | **true** | true | true | false |
| 47.75 mm | 47.750000 mm ×3 | +0.000000 mm | true | false | **true** | true | true | false |

**Rule B's conjuncts, each printed by the analyser whether or not it fired:** exactly **one**
candidate adjacent pair with opposite verdicts, `(47.60, 47.65)`; repeats unanimous at both
endpoints; rule R DETERMINATE at both; V3, V4, V5 and V14 satisfied at both; V7's clause
satisfied — no reading of either stop's cycle exceeded 4.0; and rule U satisfied — arm LO's
coarse grid shows **exactly one** change of `holding_F`, between 47.50 and 47.75 mm.

> **LO1 — BRACKETED: (47.60, 47.65] mm, width 0.05 mm.** A bracket narrower than 0.05 mm is not
> claimed, because the grid cannot produce one. **n per endpoint, collected vs surviving:
> 47.60 — 3 / 3; 47.65 — 3 / 3.** Rule B's conjuncts are evaluated over the **surviving** repeats
> (deviation 7), so the second number is the n this bracket rests on; here the two are equal and
> no endpoint rests on a reduced n.

**Rule D — the arithmetic and the measurement agree here.** The measured bracket **contains** the
computed `edge_lo` of **47.615000 mm**. There is no DISAGREEMENT to report at this edge, and
therefore nothing for ADR-0052 or the owner to act on from rule D.

**What this is a property of — rule G.** `flip_F_lo` is a property of **the shipped predicate as
delivered** — the L0 declaration, the generator, the plan, the launch parameters and
`gripper_is_holding` — and of **nothing else**. It is not a property of the cell: a synthetic stop
puts the drive joint wherever the description says, and a part, a jam or a fouled finger does not.
It is not evidence about the physical gripper, and it does not say where a real jam stops
(ADR-0052 §A.9.2, unchanged). **The word "validated" is not used about either band value
anywhere in this document.**

## 4. HI1 — the wide edge, NOT BRACKETED, and the table that is not a result

> **Rule G applies to everything in this section.** This rig can reach the wide edge **precisely
> because it grasps nothing.** Nothing below is evidence that `stall_band_wide_m` is well sized,
> that any stall on a part reaches the wide edge, or that the wide edge has been exercised in the
> sense ADR-0052 §A.9.5 means.

> **Rule W is not applicable here: this rig produces no grasp, so the population it quantifies
> over is empty.** The 2026-09-02 campaign's rule W **stands unchanged and stands fired**, and
> nothing this campaign produces touches it. **No silence is reported here**, because a silence is
> read as a clearance.

### 4.1 The verdict

> **HI1 — NOT BRACKETED.** Block HI-F has no surviving trials, so no pair of adjacent fine-grid
> stops exists. Not bracketed at 0.05 mm, over these stops, **at n = 0 surviving of 18
> collected**, on this rig. **The campaign's silence here may not be read as agreement with
> §2.2's arithmetic, as validation of either band value, or as evidence that the edge is where
> the declaration says. §A.10 item 2's second bullet is still unmet.**

**Rule D on HI1 is NOT EVALUABLE**: there is no bracket to compare against `edge_hi`. The
computed 52.385000 mm is therefore neither confirmed nor contradicted by this campaign.

**A null is never a clearance.** Rule N is a refusal, not a finding of agreement.

### 4.2 The coarse block, which did survive

Arm HI's coarse grid is admitted in full — V1, V2 and V13 clean on all 18 trials — and it is
reported as the gate's *"which stops F admits"* half at 0.25 mm, **not** as a bracket.

**Block HI-C, `w_cmd` = 45.000 mm, n = 2 per stop, I7 rest error +0.000000 mm at every stop:**

| `w_stop` | 52.00 | 52.25 | 52.50 | 52.75 | 53.00 | 53.25 | 53.50 | 53.75 | 54.00 |
|---|---|---|---|---|---|---|---|---|---|
| `holding_F` | **true** | **true** | false | false | false | false | false | false | false |
| `holding_S` | true | true | true | true | true | true | true | true | true |

`stalled` is true and `reached_goal` false at all nine stops. **Rule U on HI-C: exactly one change
of `holding_F`, at `(52.25, 52.50)`** — which is what located HI-F's refinement interval. Rule R
is DETERMINATE on both predicates, with a largest within-stop `w_reached` spread of
**0.000000 mm** against the 0.100 mm MIS.

**`holding_S` is true at all nine wide stops**, which is prediction P4 exactly: the superseded
predicate is a half-line with no upper edge at all.

### 4.3 The discarded HI-F table — printed for reporting only, and it is not a bracket

> **THIS IS NOT A RESULT.** The analyser prints it under the header *"NO SURVIVING TRIALS —
> printed for reporting only; these contribute to nothing"*. Block HI-F is discarded under V2
> (§2). **Rule B requires surviving trials at both endpoints**, and there are none here.

| `w_stop` | 52.25 | 52.30 | 52.35 | 52.40 | 52.45 | 52.50 |
|---|---|---|---|---|---|---|
| `holding_F` | true | true | true | false | false | false |
| `holding_S` | true | true | true | true | true | true |

**No registered rule admits this table into any verdict, and this document does not admit it
either.** It is printed because a block that was collected and discarded is not the same thing as
a block that was never taken, and a reader is entitled to see which it was.

**INV's echo at 40.000 mm is not a bracket either.** INV's stops at 52.35 mm (`holding_F` true)
and 52.40 mm (`holding_F` false) are 0.05 mm apart and carry opposite verdicts with n = 3 at each,
but rule B is registered over the **fine blocks at the shipped command** — LO-F, HI-F and LO-S —
and **no registered rule brackets on INV**, which is a different command and a different question
(§6). HI1 stays NOT BRACKETED.

## 5. `flip_S_lo` and FLOOR1

**Block LO-S, `w_cmd` = 45.000 mm, n = 3 per stop, I7 rest error +0.000000 mm at every stop.**
`holding_F` is **false at all six stops**, because the whole interval lies below
`edge_lo = 47.615000 mm` — which is exactly why rule B had to be generic in the predicate under
refinement, and is the hole `criteria.md`'s second pre-trial amendment closed.

| `w_stop` | 47.00 | 47.05 | **47.10** | **47.15** | 47.20 | 47.25 |
|---|---|---|---|---|---|---|
| `holding_S` | false | false | **false ×3** | **true ×3** | true | true |
| `holding_F` | false | false | false | false | false | false |

> **`flip_S_lo` — BRACKETED: (47.10, 47.15] mm, width 0.05 mm.** n per endpoint, collected vs
> surviving: **47.10 — 3 / 3; 47.15 — 3 / 3.** Every rule-B conjunct satisfied, including rule U:
> arm LO's coarse grid shows exactly one change of `holding_S`, at `(47.00, 47.25)`.

**Rule D: the bracket CONTAINS the computed closed-form floor of 47.121519 mm.**

> **V12 holds, so this quantity exists at all.** Every record carries the same build identity for
> the superseded predicate — worktree commit **`4ef2d7c9d3b6c4ee…`**, binary sha256
> **`1550ef5079aa863e…`**, plus both source hashes and the front end's. V12 is computed from that
> **invariant subset** (deviation 9); the seven differing `built_at` timestamps —
> 2026-09-03T22:11:40Z through 22:30:46Z, one per block — are printed as a separate note and are
> **not** a V12 finding, because `build_superseded.sh` refreshes that field on every build of the
> identical commit.

### 5.1 FLOOR1

> **FLOOR1 — REPORTED, and it carries no pass/fail.** `flip_F_lo` = (47.60, 47.65] mm; the floor,
> **computed on this rig** by bisection on the superseded build's own answer, is 47.121519 mm; the
> distance, as an interval because `flip_F_lo` is an interval, is **(+0.478481, +0.528481) mm**.
> **`flip_F_lo` lies ABOVE the floor**, which is the direction ADR-0052 §A.6's subset argument
> depends on. **ADR-0052 §A.6 sets no minimum distance and this campaign may not invent one**
> (§0), so no margin is claimed, proposed or implied.

**Rule H — no cross-campaign differencing.** The differenced floor is the value **computed here**
and never a measured figure of another campaign. ADR-0052 §A.6's cited **47.1215 mm** is named
beside it as an **agreement** and enters no arithmetic; the 2026-09-01 campaign's own bracket
around it, its rig, its machine and its trial counts stay in that directory.

**The rig-internal form of the same comparison**, free of any cross-campaign quantity:
`flip_S_lo` = (47.10, 47.15] mm, measured on this rig at this command, and the distance from
`flip_F_lo` to it is **(+0.450000, +0.550000) mm**.

**One comparison §2.2 registered before any trial.** It computed the arithmetic distance
`edge_lo − 47.1215 mm = 0.4935 mm` from the two records, stated that it *"is not this campaign's
datum"*, and registered it so that the measured distance could be compared with it **and could
differ**. The measured interval contains it. That is §2.2's own registered comparison; FLOOR1's
quantity remains the computed-against-computed one.

## 6. INV1 — NOT EVALUABLE, and why that is the honest state

**Block INV, `w_cmd` = 40.000 mm, n = 3 per stop, I7 rest error +0.000000 mm at every stop**,
against the same four stops at the shipped 45.000 mm command:

| `w_stop` | `holding_F` at 45.000 mm | `holding_F` at 40.000 mm | compared? |
|---|---|---|---|
| 47.60 mm | **false** (LO-F, n = 3) | **false** (n = 3) | yes — agree |
| 47.65 mm | **true** (LO-F, n = 3) | **true** (n = 3) | yes — agree |
| 52.35 mm | *(HI-F, discarded)* | true (n = 3) | **no counterpart** |
| 52.40 mm | *(HI-F, discarded)* | false (n = 3) | **no counterpart** |

`w_reached` is **bit-identical between the two commands** at both compared stops —
0.04760000000000001 m and 0.04765 m, the same value on all six repeats of each — with `stalled`
true and `reached_goal` false on every repeat at both commands (read from `raw/LO-F_trials.json`
and `raw/INV_trials.json`).

> **INV1 — NOT EVALUABLE.** §7.3 registers HELD as *"`holding_F` identical at both commands **at
> all four stops**"*, and this campaign cannot say that over stops it never compared.
> **No disagreement was found among the 2 compared stops** — and that is **not** the sentence
> "INV1 HELD". **P5 is NOT EVALUABLE rather than confirmed**, and rule C's applicability is
> undecided.

**NOT EVALUABLE is a third state `criteria.md` §7.3 does not register**, and it is deviation 8,
written into the analyser before any trial ran. The alternative readings were both worse: VIOLATED
would report a failure for a comparison never made, and HELD would **confirm P5 by not looking**.
The order applied is: any disagreement among the compared stops gives VIOLATED and rule C applies;
otherwise any unmatched stop gives NOT EVALUABLE; otherwise HELD, over a count of compared stops.

**What INV could not have settled even at four stops.** `criteria.md` §5.2 computes that the
superseded predicate returns **true at all eight** of these points, so a predicate reading the
command exactly as `holding_S` does would pass INV unchanged. **INV bounds how wrong §2's reading
of the source could be at four points; it is not a demonstration that the predicate ignores the
command.**

## 7. CTL — reported, no verdict

**CTL changes two things at once** — it removes the stop **and** swaps `JointStopSystem` for
`mock_components/GenericSystem` — so it cannot separate *"the stop produces the stall"* from
*"the plugin does"*. It does not need to: that question has a published answer elsewhere. What
CTL is: the controlled comparison whose quantity is **where the joint comes to rest**, which is
what shows the rest position is the fixture's and not the controller's.

**Read from the collected trials, not the surviving set** (V14 fires structurally here, §8):

| trial | `w_cmd` | `w_reached` (I1) | terminated (I1) | I3 sample | `stalled` | `reached_goal` | `holding_F` | `holding_S` | stop warning |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 45.000 mm | 60.915272 mm | 0.29999997 rad | 0.34666663 rad | true | false | **false** | true | none |
| 2 | 45.000 mm | 60.915272 mm | 0.29999997 rad | 0.34666663 rad | true | false | **false** | true | none |
| 3 | 45.000 mm | 60.915272 mm | 0.29999997 rad | 0.34666663 rad | true | false | **false** | true | none |

**Two rest positions are printed and they are different quantities.** §7.4's registered one is
**where the controller terminated** — I1's reached width carried back through the shipped
`gripper_position_for` — which is what P6's computed 0.300 rad is a prediction about. **I3 is the
last `/joint_states` sample at or before the result arrived, and on this arm there is no stop**,
so the joint is not at rest and I3 can be sampled later and further along. **Reading I3 as the
rest position compares P6 against the wrong number.**

**§7.4's one requirement is met: no stop warning appeared, and none may.**

**CTL is not the instrument that settles [`docs/open-work.md`](../../open-work.md) #25, it is
not powered to, and its result is not written up as evidence about it in either direction**
(§5.3, registered before any trial, in those words).

## 8. The six predictions

| # | Prediction | State | What the print reads |
|---|---|---|---|
| **P1** | LO1 at (47.60, 47.65] and HI1 at [52.35, 52.40), both containing §2.2's edges | **NOT EVALUABLE** — and see deviation 17 | LO1 = BRACKETED (47.60, 47.65]; HI1 = NOT BRACKETED |
| **P2** | Every repeat an exact replicate: spread 0.000 mm, `holding_F` unanimous | **HELD** | largest within-stop `w_reached` spread **0.000000 mm** anywhere (at HI-C stop 52.00); **no** stop's `holding_F` repeats disagree |
| **P3** | `flip_S_lo` at (47.10, 47.15] containing 47.121519 mm, with `flip_F_lo` above it | **HELD** | both brackets as predicted; `flip_F_lo` above `flip_S_lo` by (+0.450000, +0.550000) mm |
| **P4** | `holding_S` true at every stop in arm HI | **HELD** | `holding_S` false on **0** wide-arm trials |
| **P5** | INV1 HELD at all four straddling stops | **NOT EVALUABLE** — it *is* INV1 (§6) | 2 of 4 stops compared |
| **P6** | CTL: `stalled`, `¬reached_goal`, rest about 0.300 rad, `¬holding_F`, `holding_S`, no stop warning | **five of six terms reproduced; the rest term STATED, NOT TESTED** | see below |

**P6's rest term, stated and not converted into a pass or a fail.** It is registered as *"about
0.3 rad (60.915 mm)"*, and **"about" carries no registered tolerance**; choosing one now would be
a threshold chosen by the data (V9, §0). The record's computed value is **0.300000 rad /
60.915269 mm**, derived from `stall_timeout` 0.3 s × `max_drive_rate_rad_s` 1.0 rad/s read from
the generated configuration and plan. The observed termination is **0.29999997 rad /
60.915272 mm** on all three trials. The differences are **3.0e-8 rad** and **3.0e-6 mm of
width**. **This document states them and stops there.**

**And §7.4 says what a reproduced P6 is worth:** it is a **rig check and not a result**. It says
the fixture behaves as the published mechanism says, and nothing more. The five reproduced terms
are the 2026-09-01 campaign's established fixture property, registered here precisely so that
this campaign did not manufacture a confirmation by predicting something already published.

**P2's strength, stated rather than left to look impressive.** The rig has no physics and a
deterministic hardware plugin, so exact replication was expected; §6 registered that the repeats
are taken **to check the rig rather than to estimate a variance**. What P2 rules out is a rig
defect, not a source of variation the cell has.

## 9. Deviations, numbered, applied to data already collected

**Deviations 1–14 were written into `harness/analyse.py` before the first trial and print at the
top of every run.** None moved a threshold. They are carried here in one line each so that this
document cannot quietly drop one; **the full wording is in the print and is not restated here**
(P1).

| # | In one line |
|---|---|
| 1 | §6 uses "block" for two things; I8/I9 are taken per **cycle**, the stricter reading, and both indices travel on every record. |
| 2 | Rule B's V7 clause is evaluated over the cycle's two readings, and its second half is computed literally by building the bracket twice. |
| 3 | Rule B does not say what happens when **more than one** fine-grid pair carries opposite verdicts; the analyser reports every such pair and declines to claim a bracket. |
| 4 | I3 is the last sample the harness's own executor held at the instant the result completed. |
| 5 | The rig quiesces per **cycle** and per **block** — 19 × 30 s, not 104 × 30 s. No decision quantity moves and the campaign was not lengthened to close it. |
| 6 | V6 is evaluated against the block's own observed grid step; the metric's own adjacent-stop difference is printed beside it for the other reading. |
| 7 | Rule B's conjuncts are evaluated over the **surviving** repeats; every BRACKETED line prints collected vs surviving n at both endpoints. |
| 8 | **INV1 gains a third state, NOT EVALUABLE**, which §7.3 does not register. §6 is where it is spent. |
| 9 | V12 is computed from the provenance's **invariant subset**; `built_at` disagreement is reported apart from the rule. |
| 10 | An unevaluable conjunct of rule B is treated as **unsatisfied for the decision** while still printing as `not applicable`. |
| 11 | The analyser prints one rule `criteria.md` does not register — the frozen contract's own hash. It gates nothing. |
| 12 | **V13's discard path is unreachable**: such a launch takes the whole block down rather than landing a `v13_ok: False` record. Stricter, not laxer. |
| 13 | `run_block.sh`'s domain guard reads a failed `ros2 node list` as "domain clear". Protective, and nothing in §7 reads it. |
| 14 | `common.wilson` exists and nothing calls it: **no figure this campaign decides on is a proportion**, and V8's print says so on every run. |

**Deviations 15–18 are this write-up's, found in the completed data and applied to it. None moves
a threshold, and every registered rule was applied literally.**

**15. V2's discard granularity is the block, while its instrument is per trial.** V4, V5 and V14
each exclude a **trial**; V2 discards a **block**. One transient empty read-back on **1 of 18**
trials cost the campaign 18 sound trials, HI1, INV1's evaluability and P1's (§2). **V2's stated
rationale — *"the rig would be built from a description this repository does not ship"* — is not
what happened**: V13 passed on that trial, its own substituted description text carried 13 hull
references, and 17 of 18 read-backs returned 13. **The rule was applied literally, as V9
requires, and is recorded as wrong-shaped rather than corrected.** What would settle whether the
granularity should differ is a decision for the next campaign's criteria, not for this document.

**16. `common.running_geometry` cannot tell a failed call from an empty description.**
`harness/common.py:441-455` reads `subprocess.run(...).stdout`, checks neither `returncode` nor
`stderr`, and discards both. `harness/README.md` limitation 8 anticipates the ambiguity — *"the
harness cannot then say whether the node was absent or the parameter was"* — but **it does not
anticipate that the consequence of the ambiguity is a whole-block discard.** Nothing in `raw/`
can attribute trial 15's empty read, and this document does not attribute it.

**17. P1's printed state contradicts its registered refutation clause, and both readings are
reported here without attribution.** §7.5 registers P1 as *"Refuted by either bracket landing
elsewhere, **or either edge NOT BRACKETED**"*. HI1 **is** NOT BRACKETED, so **a literal reading
refutes P1**. `analyse.py` instead prints **NOT EVALUABLE**, guarding on whether both refinement
blocks have surviving trials, with its rationale in a code comment (`analyse.py:1315-1330`):
*"a prediction that could not be tested is not a prediction that was refuted, and it is not one
that survived either"*. **That guard is not one of the fourteen numbered deviations**, so unlike
deviations 1–14 it was not carried into the print's own deviation list. **Both readings are
recorded and this campaign chooses neither.** Note that under either reading nothing about the
data changes: LO1 is bracketed where P1 said, and HI1 has no data at all.

**18. No registered rule distinguishes "the block disagreed about its description" from "the
block's description instrument failed once."** Rules B and N report HI1 **exactly as if no data
had been taken** — which is also how §4.1 must state it, because that is what the rules say. The
18 collected trials, their unanimous per-stop verdicts and their clean V1/V4/V5/V13/V14 flags
are printed (§4.3) and enter nothing. A rule that separated the two cases would have had to be
registered before the first trial, and was not.

## 10. The machine, the load, and the validity rules

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM (`criteria.md` §9; `host_uname` on every campaign invocation record) |
| Container | image **`cite-digital-twin:dev`**, ID `3a41d4e431b0`, Ubuntu 24.04.4, ROS 2 Jazzy. **Not CPU-limited**: `cpu.max` reads `max 100000`, `nproc` 16 — all from `criteria.md` §9, read there on 2026-09-03 and not re-read here |
| Isolation | compose project **`cite-digital-twin-3319196271`**, **`ROS_DOMAIN_ID` 43**, both derived from this checkout and both recorded on every campaign invocation in `raw/provenance.txt` |
| Gazebo | 8.11.0 sourced — and **irrelevant here**: this rig starts no Gazebo process at all, and `raw/provenance.txt` records `gz_note=this rig starts no Gazebo-transport process at all, so no GZ_PARTITION binds here` |
| Build | **one** `./scripts/build` before the first trial, `Summary: 23 packages finished`, `build_exit=0` (V11). The **superseded** front end was rebuilt once per block, to an identical build identity (§5) |
| `MODEL_HASH` | source and installed agree on every one of the 105 rows (`95dbbdd9…`) |

**Wall clock, from `raw/` rather than from a stopwatch.** The campaign ran as **four**
`run_campaign.sh` invocations — `LO-C HI-C`, `LO-F HI-F LO-S`, `INV`, `CTL` — recorded at
22:11:05Z, 22:17:30Z, 22:27:27Z and 22:30:11Z on 2026-09-03, with the last block completing at
**22:31:58Z**. That is **20 min 53 s** from the first environment record to the last block's
completion, and **20 min 17 s** from the first trial's own I9 reading (22:11:41Z) to the same
end; the seven block spans sum to **13 min 20 s**, the remainder being the quiesces, the
per-block superseded rebuild and the idle gaps between the four invocations. **The campaign operator reported 21 min 14 s; that figure does not
reproduce from `raw/` by any of the three constructions above, and the raw-derived figures are
what this document carries.** `analyse.py` prints no wall clock at all.

**Load, at both ends and at its worst.** The host's own reading at the first invocation was
**0.42 / 0.31 / 0.22** on 16 cores; the first trial's I9 start read **0.367 / 0.308 / 0.226**;
the last trial's I9 end read **0.190 / 0.378 / 0.414**. **The highest reading anywhere in the
campaign, across all three averages at both ends of all 105 trials, is 1.463** (`load_1m` at the
end of LO-S trial 6), against V7's threshold of **4.0**.

> **V7 — 0 of 84 kept trials flagged.** No block is discarded for load, because a load threshold
> chosen after seeing the data is a threshold chosen by the data. No bracket here needed the
> with-and-without report V7 would otherwise require.

**What host load could and could not have reached.** Every decision quantity is a **width**: a
drive-joint position clamped by the fixture to a value the description declares, mapped through a
static linkage. There is no physics, no simulator and no clock coupling in this rig. The one
route by which load could touch a verdict is **a trial that never completes**, which appears as a
failed trial and not as a moved number — and **0 trials failed to complete** across the campaign.

**The other validity rules, as the print reports them.**

| rule | state |
|---|---|
| **V1** | clean at both ends of every cycle in all seven blocks; **0 rows dropped** for a missing flag |
| **V2** | fired once — block **HI-F discarded** (§2); the other six blocks read **13** hull references |
| **V3** | structurally discharged per trial: this rig has no simulator, so nothing can be between the pads |
| **V4** | **0** trials excluded |
| **V5** | **0** trials excluded; I5 present, I6 absent and I7 at +0.000000 mm on every arm trial |
| **V6** | did not fire on any block: largest between-cycle `w_reached` difference at one stop is **0.000000 mm** everywhere, against each block's own grid step |
| **V7** | did not fire (above) |
| **V8** | **84 surviving over 105 collected**, across 5 blocks. **No stop was topped up and no block was re-run** |
| **V9** | no threshold moved |
| **V11** | one build before the first trial |
| **V12** | **holds** on the identity subset; the freshness note is reported apart from it (§5) |
| **V13** | the production backend found before every substitution, on every launch |
| **V14** | fired on **CTL's 3 trials** and on nothing else: I4 disagrees with I2 or I1 there **structurally and as named in advance** — CTL declares no stop, so the joint is not at rest, I3 samples it later than I1, and I4's second command moves it further. **0** trials were excluded for instrument loss, and no absent I2 line was ever recorded as a measured `false` |

> **V10 — one writer at a time, and this is the one rule this document cannot discharge as
> written.** `criteria.md` §10's V10 asks the **campaign operator** to state in `ANALYSIS.md`
> whether one writer held.
> **This document was written from the committed record by someone who did not run the campaign,
> so no such statement is carried here.** What the record carries instead is the mechanism V10
> relies on: `v1_clean` is the conjunction of two `git` readings per cycle, it is `true` on all
> 105 rows, `disagreed_mid_block` and `head_moved_mid_block` are false on every row, and **no
> block was lost to V1**. That is evidence that no watched path was edited mid-cycle; it is not
> the operator's statement, and it is not written here as though it were.

## 11. What this campaign does not establish

Registered in `criteria.md` §8 before the first trial, and none of it moved.

- **The wide edge.** **HI1 is NOT BRACKETED and rule N applies** (§4). ADR-0052 §A.9.5 stands
  unchanged, and `stall_band_wide_m` is no more evidenced after this campaign than before it.
- **That any stall on a part reaches either edge.** Rule G, and the 2026-09-02 campaign's rule W,
  which **stands fired and is not retired here**. **Rule W is not applicable to this campaign:
  this rig produces no grasp, so the population it quantifies over is empty**, and no silence of
  this campaign's may be read as a clearance at that edge.
- **Anything about the physical gripper.** ADR-0052 records there is **no
  `GripperActionController` on the hardware path at all**. **Nothing here is a P2 result**, and
  Phase 2.B bring-up is the only thing that would settle it.
- **Where a real jam stops.** A synthetic stop at a declared position is not a fouled finger.
  ADR-0052 §A.9.2 stands unchanged and this campaign does not narrow it by one millimetre.
- **Whether `stall_band_narrow_m` or `stall_band_wide_m` is the right value.** Locating a flip
  says where the declared band puts the edge, not whether the band should be there.
- **That the predicate ignores the command.** INV1 is NOT EVALUABLE, and even HELD would have been
  evidence about four points rather than about the functional form (§6).
- **Whether the stall distribution moves with the commanded width** (ADR-0052 §A.9.1). This
  campaign is **smaller** on that question, not larger; its two commands test invariance.
- **Why the drive joint reads narrower than the part it holds** (ADR-0052 §A.9.3).
- **Grasp quality, an opening stroke, a facility declaring more than one part** — the shipped
  interval is degenerate at 50.0–50.0 mm and only the degenerate case is measured here — **any
  part, any timestep, any collision geometry, any arm but `arm_1`, any effort but 60 N.** Three of
  those are structurally absent rather than merely unvaried: there is no part and no physics.
- **Open-work #25.** §7, and §5.3 registered it before any trial.
- **A rate of anything.** Every count is over the trials that ran. **One machine, one image, one
  commit, one checkout, one arm, one facility with one declared part width, no physics.**
- **The empty read-back of §2.** Not attributed, and this document does not diagnose it.

## 12. What this campaign does not decide

**This campaign chooses nothing**, and that was registered in `criteria.md` §0 before any number
existed so that no number could be read as an argument for one.

- **It does not set the band.** `stall_band_narrow_m` and `stall_band_wide_m` are declared
  `PROVISIONAL` in L0. This document reports where the shipped predicate's verdict flips and
  **proposes no value and implies none.**
- **It does not amend ADR-0052 or move its status**, and does not decide whether the removed
  monotonicity term `reached > commanded` returns. That is an open project-owner decision,
  recorded in ADR-0052 §B.4 and in [`docs/open-work.md`](../../open-work.md); **this campaign
  registered before its first trial that it would not take it, and it has not.**
- **No threshold, ceiling, tolerance or band anywhere in the tree was changed**, and none may be
  changed to absorb anything found here. **Neither edge of the window may be widened to make a run
  pass** — `gripper.hpp` says so on the declaration itself.
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/` or `scripts/` was edited.** The
  harness lives entirely under `harness/` in this directory, and `raw/` beside it.
- **It does not decide what to do about §2's discard**, about V2's granularity (deviation 15), or
  about whether a second campaign runs. Those are the owner's.

Where a figure above bears on a decision, it is a quantity with its consumer named and the
sentence stops there:

| Quantity | What it bears on |
|---|---|
| LO1 BRACKETED at (47.60, 47.65] mm, containing the computed 47.615000 mm (§3) | ADR-0052 §A.10 item 2's second bullet **at the narrow edge**, and the delivery of the declared band through the generator, the plan and the skill server |
| HI1 NOT BRACKETED, rule N (§4) | the same bullet **at the wide edge**, which is **still unmet** |
| FLOOR1 = (+0.478481, +0.528481) mm, `flip_F_lo` **above** the floor (§5) | ADR-0052 §A.6's subset argument, whose direction this is — with no margin claimed |
| `flip_S_lo` BRACKETED at (47.10, 47.15] mm (§5) | the rig-internal form of the same comparison, free of cross-campaign differencing |
| INV1 NOT EVALUABLE, 2 of 4 stops compared (§6) | how much of §5.2's source reading is bounded by measurement — less than the campaign intended |
| V2's block-level discard on 1 trial in 18 (§2, deviation 15) | the shape of a future campaign's V2, if one is run |

**The choice is the project owner's.** This campaign exists to make it decidable.

## 13. Reproduction

The whole campaign is `harness/run_campaign.sh`; `harness/README.md` carries every command,
including the one-block-at-a-time forms. Every figure in this document comes from:

```sh
python3 docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py
```

which applies `criteria.md` §7's rules to `raw/` and **prints every rule whether or not it
fires** — 365 lines, and it must be redirected to a file rather than piped through `head`.
Nothing here was derived by hand from the trial files that the analyser does not print, except
where a per-trial column is quoted directly from `raw/*_trials.json` (§2's V2 table, §7's I3
column, §10's load and wall-clock figures) and named as such.

**Figures stay in this directory.** Nothing here is copied into ADR-0052, `CLAUDE.md`,
[`docs/open-work.md`](../../open-work.md), the L0 comments or any layer document (P1). **Cite the
directory.**
