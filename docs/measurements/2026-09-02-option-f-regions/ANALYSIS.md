# The regions option F opens, closes and has never touched

**Verdict, in this campaign's own terms.** Every one is `criteria.md` §7's registered rule
applied by `harness/analyse.py` to `raw/`, and every one is stated **per arm** — rule T: the
arms are not each other's evidence.

| Arm | Verdict | In one line |
|---|---|---|
| **B — the region the removed term used to cover** (Q-B, B1) | **REPRODUCED** | A drive joint jammed part-way through an **opening** stroke, inside the window, on jaws opening onto nothing, reports `holding = true`. **9 of 9** valid in-window jams. The superseded predicate reports `false` on all nine. The two controls at 46.00 and 54.00 mm are rejected, so **the window is what decides**. Replicate spread **0.000 rad**. |
| **A — free air across the commanded width** (Q-A, A1) | **NOT REPRODUCED**, **rule N-A applies** | No free-air close reported holding, at **n = 57** at commands `resolve_grasp_width` permits. **A1a is false everywhere — 0/57 stalled** — so F's *first* condition rejects free air on this backend and **the window is never consulted**. But **A1b is INSIDE at 27 of 57**, from a commanded 46.65 mm, so `gripper.hpp`'s sentence *"It falls below it at every command"* is **FALSE**. |
| **C — the wide edge** (Q-C, C1) | **NOT CROSSED**, **RULE W FIRES** | 24/24 trials with witnessed finger contact, and not one within 0.100 mm of the wide edge. Closest approach over every genuine grasp in the campaign: **2.4223 mm**. **The campaign has not tested that edge.** The lever failed for a reason it measured: **the jaws square the part up** — yaw at the stall is ~0° at every setpoint up to 12°, which is §7.5's prediction P4. |
| **D — the false-negative side** (Q-D, D1) | **NOT OBSERVED**, **rule M applies** | No valid grasp with witnessed contact was reported empty, at **n = 16**. Minimum observed `d_narrow`: **0.9269 mm**, positive. |

**And the quantity that is not a registered verdict but is the campaign's sharpest single
result.** At a commanded **48.0 mm** — above the validator's ceiling — on a real 50 mm part
with contact witnessed on every trial, `holding_F` is true on **8 of 8** and `holding_S` is
true on **0 of 8**. **The superseded predicate reports every real grasp empty at that command
and F reports every one held.** That is ADR-0052 §A.8's predicted recovery, measured on the
implemented predicate rather than computed from another campaign's raw.

- **Campaign:** `docs/measurements/2026-09-02-option-f-regions/`
- **Branch under measurement:** `feat/grasp-predicate-against-the-part`, off `main` at
  `4ef2d7c`, code under test at **`d3eeac4`**. **The branch is unmerged, and that is a
  condition of the campaign** (`criteria.md` §0, V1). Every block ran at `HEAD = e559264`,
  with `git diff d3eeac4..HEAD -- model/ workspace/src/ tools/` **empty** and the worktree
  clean in all three paths; `v1_clean` is `true` on every block header.
- **`criteria.md` sha256:**
  `17ee48480fd2c8b9a145c05ab2f556815c106f9e355d22b528ec3ed52ae4db73`
  Committed **alone**, at `79ae6d9`, before the harness existed and before any trial ran. The
  four data commits are `24d8f38` (B), `f1a8d97` (A), `fb537f6` (D) and `934e561` (C), all
  after it. That sha256 is recorded in `raw/provenance.txt` by every campaign invocation and
  is unchanged.
- **The record that asked for it:**
  [ADR-0052](../../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) §A.10 item 2,
  on the implemented predicate. **Its status does not move here and nothing about the band,
  the monotonicity term or the branch is decided.** See §10.
- **The campaign this one does not replace:**
  [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/ANALYSIS.md). It
  measured the **superseded** predicate, it stays frozen, and its figures are cited and never
  copied (P1).

## 1. What was run

| Arm | Question | Rig | Trials |
|---|---|---|---|
| **B** | Q-B | a real `ros2_control_node` over `cite_test_hardware/JointStopSystem`, **no physics**, one relaunch per trial, stops reversed so the stroke **opens** | **15 attempted, 14 produced data**; 9 of those are in-window jams |
| **A** | Q-A | the shipped cell, headless, **production backend**, **nothing between the pads and no work-piece in the world** | **39** coarse (2 blocks) **+ 18** refinement = **57**, all at permitted commands |
| **C** | Q-C | the shipped cell, headless, a yawed 50 mm cube, 8 yaw setpoints about the **world vertical** | **24**, 2 blocks |
| **D** | Q-D | the shipped cell, headless, `Pick` at 45.0 mm and `Grasp` at 48.0 mm interleaved, plus 3 `Pick`-refusal trials | **19** (16 grasps + 3 refusals), 2 blocks |

**97 campaign trials, plus the 18-trial refinement grid.** `raw/shakedown/` is excluded from
every figure above and below (`criteria.md` §10).

**Every verdict below is read from the shipped predicate, never from a copy.**
`Grasp.Result.holding` **is** `cite_skills::gripper_is_holding`'s return value and
`Grasp.Result.reached_width_m` **is** `gripper_width_for(result->position)`; for Arm D's
`Pick` door the verdict is `Pick.Result.holding`, which is the same function's answer on that
close. `holding_S` comes from a **build** of `4ef2d7c`, not a rewrite — worktree commit and
binary sha256 (`0f21e8ef…`) recorded per build in `raw/provenance.txt`, which is what V10
spends. `harness/arithmetic.py` reproduces `criteria.md` §2 and is used for **no reported
figure**.

**V2 and V7, read off the running cell rather than claimed.** Every block that brought the
cell up read **13** hull collision references under `cite_description`, **3** production
hardware-plugin references and **0** mock ones. **Every figure here is on convex-hull
collision geometry** (ADR-0028, promoted against the clause [ADR-0051](../../adr/0051-restate-the-hull-grasp-gate.md)
restates). Arm B asserted the description declared `gz_ros2_control/GazeboSimSystem`
**before** substituting its own plugin, on every launch.

## 2. B1 — the region the removed term used to cover, and it reproduced

`criteria.md` §5.2 registers the direction before any trial: a **closing** stroke satisfies
the removed term `reached_width > commanded_width` structurally and cannot produce this case,
so the region is reached only by an **opening** stroke that jams part-way. Every Arm B trial
was commanded to **56.000 mm** — wider than every jam — and the command was held fixed on
purpose, so that "the command does not enter F's verdict" is checkable rather than assumed.

### 2.1 The five jams

`w_reached` is I1. V5 passed on all fourteen trials that produced data: the plugin's own stop
warning appeared, the drive joint rested on the declared stop within 0.001 rad, and no
start-outside-the-stops refusal was seen.

| jam | role | n | `w_reached` (I1) | `stalled` | `reached_goal` | `holding_F` | `holding_S` | I7 | I8 refused |
|---|---|---|---|---|---|---|---|---|---|
| 46.00 mm | **control, narrow side** | 3 | 46.0000 mm | true | false | **false** | false | true | false |
| 48.00 mm | window | 3 | 48.0000 mm | true | false | **true** | false | true | false |
| 50.00 mm | window | 3 | 50.0000 mm | true | false | **true** | false | true | false |
| 52.00 mm | window | 3 | 52.0000 mm | true | false | **true** | false | true | false |
| 54.00 mm | **control, wide side** | 2 | 54.0000 mm | true | false | **false** | false | true | false |

**B1 — REPRODUCED (n = 9 valid in-window jams).** At least one — in fact all nine — valid
trials with the joint jammed inside the window during an opening stroke report
`holding_F = true`. Rule N-B does not fire.

**The two controls are what make this a result about the window.** F's flag conditions are
identical at 46.00 and 54.00 mm — `stalled ∧ ¬reached_goal` in both — and both are rejected.
The only thing that differs across the five rows is where the joint sits relative to
[47.615, 52.385] mm, so **the window is what decides, and the window is what admits the
three.**

**`holding_S` is false at all five**, which is prediction P3 exactly: the reached width is
below the command in every one of them, so the removed monotonicity term is unsatisfied
throughout. **`holding_S` enters no verdict** (`criteria.md` §4.4); it is here so a reader can
see which region the change opened.

**Prediction P6 held: the replicate spread is 0.000e+00 rad at every jam.** A non-zero spread
would have been a finding about the rig; there is none.

### 2.2 What REPRODUCED means here, and what it does not

- It is **a measured predicate defect on a rig**, and it is in a direction **ADR-0052 §A.3's
  specification permits**: F drops `reached_width > commanded_width` by design, and this is
  what dropping it costs on this rig.
- **It is not a decision that the monotonicity term returns.** That is the project owner's,
  and `criteria.md` §0 registered before any trial that this campaign does not take it.
- **It is not evidence about any physical gripper.** ADR-0052 records that there is no
  `GripperActionController` on the hardware path at all. Nothing here is a P2 result.
- **It is not evidence about where a real jam stops.** Arm B is a synthetic stop at a
  declared position, not a fouled finger — `criteria.md` §8 and ADR-0052 §A.9.2, both
  unchanged by this campaign. What is measured is what the predicate does with such a stall.
- **It says nothing about a closing stroke**, in either direction. §5.2's scope limit is a
  fact about the mechanism rather than an untested gap, and it is stated in that form.
- **The stop grid is 2.00 mm coarse.** ADR-0052 §A.10 item 2's second bullet also asks for
  the false-positive **flip bracketed to at least 0.05 mm**; Arm B locates it only to
  (46.00, 48.00] mm at the narrow side and [52.00, 54.00) at the wide side. **That bullet is
  not met by this campaign** — see §9.

### 2.3 One Arm B trial produced no data, and it is reported rather than replaced

Trial 10, the second block's 54.00 mm control, ended with *"the skill server never answered
the Grasp goal"*. The rig came up — controllers loaded, the gripper controller active — and
the harness tore it down about 120 s later; `raw/logs/B_010_54.00.log` is preserved with the
run's whole console. **It was not re-run and no condition was topped up** (V8), so the
54.00 mm control stands at **n = 2** and every other jam at n = 3. **Not attributed.**

`analyse.py` prints its V5 line as **14/14**, which is over the trials that produced a record.
**15 were attempted**; the difference is this trial and it is stated here rather than left to
be inferred from a smaller n.

## 3. A1 — free air on the production backend, NOT REPRODUCED, and rule N-A

**Rule N-A, applied in its registered wording and not paraphrased:** free air is **not
reproduced at n = 57, at these commands, on this machine, on this backend**. It **may never be
written as "free air is safe at any command"**, and no sentence in this document may imply it.

All 57 trials were at widths I6 — `cite_skills::resolve_grasp_width` itself — returned
`Goal` for. **No width in the grid was `Refused`**, so §7.1's scope clause never had to fire;
the grid stops at 47.85 mm, below the 47.8769 mm the shipped function permits. V3's Arm A
clause was discharged by its second half on every trial: **no work-piece existed in the
world**, read per trial from the world through `cite_bringup/gz.py`. Per `harness/README.md`,
**I4 does not exist in this arm** — it is a sensor on a work-piece and there is none — so this
is not written as "I4 witnessed no contact". A witness that sees nothing because there is
nothing to carry it is not a witness.

### 3.1 A1a — the flags reject, and this is the answer to the question the arm existed for

**A1a is false everywhere: 0 of 57.** Every free-air close reported `stalled = false` and
`reached_goal = true`, with `i1_result_code = 0` and the I2 report line read on all 57.

**Stated in the form `criteria.md` §7.1 requires: the FIRST condition is what rejects free air
on this backend, and the window is never consulted.** `GripperActionController` ends the goal
when `|error| < goal_tolerance`, `reached_goal` is then true, and F's second conjunct fails
before either edge is reached. The 2026-09-01 campaign listed *"whether ordinary free air on
the production backend behaves as ADR-0052 §3 predicts"* as **explicitly unmeasured**, because
its control measured mock hardware's dead velocity channel instead. **That is the measurement
this arm exists to take, and it is taken here: 57 of 57 on the production backend.**

Prediction **P1 held** on both of its clauses.

### 3.2 A1b — the width, and the sentence in `gripper.hpp` is false

A1b is registered as an **independent** question, and the decomposition exists precisely so
that a NOT REPRODUCED cannot be read as clearing a claim it does not touch.

**A1b is INSIDE at 27 of 57 trials**, from a commanded **46.65 mm** upward. Per command, on
I1 — `Grasp.Result.reached_width_m`, which `criteria.md` §2.1 defines as the width the
predicate consumes:

| `w_cmd` | n | `w_reached` (I1) | `w_reached − edge_lo` | A1b inside / n |
|---|---|---|---|---|
| 45.00 mm | 3 | 46.0492–46.0494 mm | **−1.566 mm** | 0/3 |
| 45.25 mm | 3 | 46.2581 mm | −1.357 mm | 0/3 |
| 45.50 mm | 3 | 46.4696 mm | −1.145 mm | 0/3 |
| 45.75 mm | 3 | 46.7903–46.7904 mm | −0.825 mm | 0/3 |
| 46.00 mm | 3 | 46.9999 mm | −0.615 mm | 0/3 |
| 46.25 mm | 3 | 47.2115 mm | −0.404 mm | 0/3 |
| 46.50 mm | 6 | 47.5312–47.5314 mm | −0.084 mm | 0/6 |
| 46.55 mm | 3 | 47.5726–47.5727 mm | −0.042 mm | 0/3 |
| **46.60 mm** | 3 | 47.6146–47.6147 mm | **−0.0004 mm** | **0/3** |
| **46.65 mm** | 3 | 47.6570 mm | **+0.0420 mm** | **3/3** |
| 46.70 mm | 3 | 47.6992–47.6993 mm | +0.084 mm | 3/3 |
| 46.75 mm | 6 | 47.7415–47.7416 mm | +0.127 mm | 6/6 |
| 47.00 mm | 3 | 47.9531 mm | +0.338 mm | 3/3 |
| 47.25 mm | 3 | 48.2718–48.2719 mm | +0.657 mm | 3/3 |
| 47.50 mm | 3 | 48.4829 mm | +0.868 mm | 3/3 |
| 47.75 mm | 3 | 48.8051 mm | +1.190 mm | 3/3 |
| 47.85 mm | 3 | 48.8879 mm | +1.273 mm | 3/3 |

**Therefore `gripper.hpp:341-342`'s sentence — *"the measured free-air settle at 45.852 mm
falls BELOW it. It falls below it at every command, which is the property the old form did not
have"* — is FALSE.** At 27 of 57 trials, the free-air settle lands **inside** F's window. The
first clause is true; the second is not.

**And the predicate is nonetheless safe on this backend, for a different reason than the
sentence gives.** The flags reject first, at every one of the 57. **These are two different
claims and only one of them is `gripper.hpp`'s**; §7.1 split A1 into A1a and A1b in advance
exactly so that they could not be confused, and they must not be merged here. The window is
not what makes free air safe on this backend — the terminating rule of
`GripperActionController` is.

**What this does not license.** A1a is a measurement of this backend at these commands.
Anything that lets a free-air close end **without** `reached_goal` — a different controller, a
cancelled goal, a preemption, a jammed stroke (which is Arm B, where exactly that happens) —
puts the verdict back on the window, and the window admits the settle from 46.65 mm upward.

### 3.3 Where the crossing is, bracketed at the registered step

`A_REFINE` swept **(46.50, 46.75]** at the registered **0.05 mm** step, three trials per
point. The crossing is bracketed to **(46.60, 46.65] mm**.

**`criteria.md` §2.2 predicted, before any trial, a crossing between 46.554 and 46.766 mm.
The prediction holds.** The measured bracket sits inside it, nearer the lower (worst-case,
one-full-tolerance) bound. Prediction **P2 held** on every one of its rows.

**The interval was located by the data and the step was not** — that is bracketing, and
§5.1 registers the distinction rather than leaving it to be argued now.

### 3.4 Two things about that bracket that weaken it, stated rather than left out

**First: the deciding margin at the bracket's lower bound is 0.0004 mm.** At 46.60 mm the
reached width sits **0.0004 mm below** `edge_lo` — 250 times under the campaign's own
0.100 mm width MIS. The bracket's lower edge is therefore decided by a difference the campaign
registered in advance as too small to be interesting. Its **upper** edge is decided by
+0.042 mm, also under the MIS; the first command whose margin exceeds the MIS is **46.75 mm**,
at +0.127 mm.

**Second: the per-trial A1b the analyser reports drops a clause the registered median form
carries.** §7.1 words A1b INSIDE as the median lying within the window *"by more than the
0.100 mm MIS"*; `measure_arm_a.py:289` computes `a1b_inside_window` as strict containment,
`edge_lo < i1_reached < edge_hi`, with no margin. The substitute is therefore **looser** than
the form it stands in for. Read with the MIS clause restored, A1b would go INSIDE from
**46.75 mm** rather than 46.65 mm. **Both readings fall inside §2.2's predicted 46.554–46.766
bracket, so no verdict in this document changes either way** — but the looser reading is the
one the frozen analyser prints, and it is reported as such rather than silently preferred.
**No threshold was moved** (V9); this is recorded as a disagreement, in the shape V9 requires.

**Rule R-A was applied literally and could not fire**, because V4 leaves the Arm A
distribution empty (deviation 1). The analyser prints the within-command spread over **all**
trials as an explicit observation and not as the rule: it is **IQR ≤ 0.0001 mm** at every
command, min-to-max ≤ 0.0002 mm. That is far inside the 0.05 mm bracket step, so the flip is
reported as a bracket and not as an interval containing both verdicts — **but that is an
observation, and "R-A did not fire" may not be read as "the spread is within the bracket".**

**V6 did not downgrade Arm A.** Largest between-block difference **0.000158 mm** against a
largest between-condition difference of **2.839 mm**, a factor of 18,000.

## 4. C1 — the wide edge, NOT CROSSED, and RULE W FIRES

### 4.1 The lever was applied, and the mechanism removed it before the stall

I5 sampled the part's yaw about the **world vertical** at the spawn, at first contact and at
the stall. **A yaw is not a roll**; every angle here is a yaw about that axis and no figure
from the grasp-plane-offset campaign may be substituted for one.

| yaw setpoint | n | presented width at first contact | yaw at first contact | **yaw at stall (median)** | **presented width at stall (median)** | `w_reached` (I1, median) | contact |
|---|---|---|---|---|---|---|---|
| 0.0° | 3 | 50.000 mm | −0.000° | −0.139° | 50.121 mm | 48.7947 mm | 3/3 |
| 1.5° | 3 | 51.292 mm | 1.462–1.500° | −0.016° | 50.014 mm | 49.7204 mm | 3/3 |
| 3.0° | 3 | 52.548 mm | 3.000° | −0.009° | 50.008 mm | 49.6052 mm | 3/3 |
| 4.5° | 3 | 53.769 mm | 4.500° | −0.007° | 50.007 mm | 49.9537 mm | 3/3 |
| 6.0° | 3 | 54.953 mm | 6.000° | −0.004° | 50.004 mm | 49.8194 mm | 3/3 |
| 8.0° | 3 | 56.472 mm | 8.000° | −0.205° | 50.178 mm | 48.3832 mm | 3/3 |
| 10.0° | 3 | 57.923 mm | 10.000° | 0.000° | 50.090 mm | 49.5277 mm | 3/3 |
| 12.0° | 3 | 59.303 mm | 12.000° | 0.004° | 50.126 mm | 49.7873 mm | 3/3 |

**The lever genuinely reached the pads.** At every setpoint of 3° and above the part was still
at its full setpoint yaw when the fingers first touched it, presenting **52.548 to 59.303 mm**
across the pads — above `edge_hi = 52.385 mm` in every case, which is exactly the condition
Q-C was designed to create. §2.2's presented-width arithmetic reproduces on the measured
first-contact yaw to three decimals.

**And by the stall the part is square.** The yaw at the stall is within **0.327° of zero in
all 24 trials**, at every setpoint including 12°, and the presented width at the stall is
**50.000–50.285 mm** everywhere.

**Prediction P4 is confirmed, and this is what §7.3 required the write-up to distinguish.**
`w_reached` does **not** track the presented width; **the jaws square the part up as they
close**, which is the mechanism registered in advance as the candidate explanation and which
**reproduces the conveyor-yaw campaign's own finding** —
[`2026-08-26-conveyor-yaw-transfer/`](../2026-08-26-conveyor-yaw-transfer/ANALYSIS.md), cited
and not copied (P1). **So C1 is NOT CROSSED because the arm's lever was neutralised, not
because the edge was shown to be far away**, and those are the two explanations §7.3 named.

### 4.2 Rule W, in its registered wording

**C1 — NOT CROSSED (24/24 trials with witnessed finger contact).** No valid trial with
witnessed contact produced `w_reached > 52.385 mm`. Rule S-C did not fire: I4 witnessed finger
contact on all 24, with 40 finger contact points at the stall in every one.

**Closest approach to the wide edge, over every genuine grasp in the campaign: 2.4223 mm**
(arm D, `D_B1` trial 5, `grasp48` — the largest stall observed anywhere here, 49.9627 mm).

> **RULE W FIRES.** The campaign produced no trial within **0.100 mm** of the wide edge, so
> **it has not tested that edge**. Its silence there **may not be read as a pass, as a
> validation of `stall_band_wide_m`, or as evidence that the edge is far enough away**.
> **ADR-0052 §A.9.5 stands unchanged.**

**The arm built to reach that edge got no closer than an ordinary grasp at another command.**
Arm C's own minimum `d_wide` is **2.4313 mm** (`C_B1` trial 12), against Arm D's 2.4223 mm — a
difference of **0.009 mm**, an order of magnitude below the 0.100 mm MIS. The yaw lever bought
nothing measurable in approach to the wide edge. That is the honest summary of Arm C, and it
is why rule W was written before the data existed.

**V6 did not downgrade Arm C, and the margin is narrow enough to say so.** Largest
between-block difference **0.858 mm** against a largest between-condition difference of
**1.691 mm** — a factor of about two, not the four orders of magnitude the other two arms
show, and the between-block figure is itself well above the 0.100 mm width MIS. V6 is applied
literally and does not fire; **the yaw setpoint is not established as the dominant source of
variation in `w_reached` in this arm**, and no finding here rests on it being one.

## 5. D1 — the false-negative side, NOT OBSERVED, and rule M

Two conditions through **two different doors**, which `criteria.md` §5.4 registers as itself a
finding to report: 45.0 mm through `Pick` — the production path and the width L4's `PickAt`
port default sends — and 48.0 mm through `Grasp`, because `resolve_grasp_width` refuses
48.0 mm before anything moves and `execute_grasp` applies no such refusal.

| condition | door | n | contact witnessed | `w_reached` median | `d_narrow` min / median / IQR / max | `holding_F` false | `holding_S` true |
|---|---|---|---|---|---|---|---|
| **`pick45`** (45.0 mm) | `Pick` | 8 | 8/8 | 48.7883 mm (I3) | **0.9269** / 1.1733 / 0.5202 / 2.1979 mm | **0/8**, Wilson 95 % [0.000, 0.324] | **8** |
| **`grasp48`** (48.0 mm) | `Grasp` | 8 | 8/8 | 49.9211 mm (I1) | **1.7396** / 2.3061 / 0.0187 / 2.3477 mm | **0/8**, Wilson 95 % [0.000, 0.324] | **0** |

**D1 — NOT OBSERVED (n = 16 with witnessed finger contact).**

> **Rule M, in its registered wording:** not observed at **n = 16**, at these commands, on this
> machine. **Minimum observed `d_narrow`: 0.9269 mm**, and its sign is **positive**. This may
> **never** be written as "the defect does not occur".

Prediction **P5 held**: the minimum `d_narrow` at 45.0 mm is positive, every admitted-contact
trial was admitted, and rule M applies.

**V6 did not downgrade Arm D.** Largest between-block difference **0.0485 mm** against a
largest between-condition difference of **1.129 mm**.

### 5.1 The 48.0 mm result, which is the recovery ADR-0052 §A.8 predicted

**`holding_F` true on 8/8; `holding_S` true on 0/8.** At a commanded width above the
validator's ceiling, on a real 50 mm part with the work-piece's own contact sensor witnessing
finger contact on every trial, **the superseded command-referenced predicate reports every one
of eight real grasps empty, and the implemented predicate reports every one held.**

ADR-0052 §A.8 predicted this by re-reading the 2026-09-01 campaign's committed raw. **This is
that prediction measured on the implemented predicate, on trials taken for the question** —
not a re-analysis of trials taken for another. **Its figures stay here and are cited from
elsewhere, never copied (P1).**

**`holding_S` is a datum and not a defect** (`criteria.md` §4.4), in either direction, and
nothing about what to do with the disagreement is decided here.

**At 45.0 mm the two agree — `holding_S` is true on all 8** — which is what makes the 48.0 mm
column the whole of the difference, and which is consistent with the shipped default command
sitting well clear of the region where the superseded form fails.

### 5.2 The three `Pick`-at-48.0 mm refusals, reported and not judged

These are **observations, not a verdict** — `criteria.md` §5.4 registers them as the measured
cost of `resolve_grasp_width`'s ceiling on this branch.

All three returned `PRECONDITION_FAILED` (`code = 5`) with **no motion**: the maximum joint
movement over the whole attempt was of order **1e-19 rad** — 1.90e-19, 8.13e-20 and 2.44e-19 —
which is nothing moving at all. The refusal message is quoted once because it is actionable
and names its own remedy:

> refusing to close to 48.00 mm on work-piece `'ofr_part_D_B1_001_absent'`: it leaves 2.00 mm
> against the narrowest part this facility handles (50.00 mm), below the 2.12 mm a close has
> to clear to evidence anything. A grasp is evidenced by FAILING to reach where the jaws were
> sent, and this close would arrive on the controller's goal-tolerance branch and be reported
> empty with the part between the pads. Ask for a narrower width, or lower
> `default_grasp_width_m` in the L0 end-effector type

**The cost is real and it is the one §A.8 already states:** the same 48.0 mm that `Grasp`
executes into 8 of 8 witnessed grasps is refused at the `Pick` door. **This campaign reports
that and does not judge it** (§0).

## 6. Deviations, numbered, applied to data already collected

`criteria.md` was frozen at `79ae6d9` and **no threshold, rule, MIS or exclusion in it was
changed after the first campaign trial ran**. **V9 requires a threshold discovered to be wrong
to be applied literally and recorded as wrong**, and that is what happened in all four cases
below: **none of them moved a threshold.** Each records where a registered *form* could not be
evaluated as worded, and what was reported in its place. All four were found **before** the
first campaign trial, by the shakedown (`raw/shakedown/NOTES.md`), and `analyse.py` prints
them on every run.

**Deviation 1 — §7.1's A1b in its literal MEDIAN form is UNANSWERABLE in Arm A, and the
per-trial I1-based A1b is reported in its place.** V4 requires I1 and I3 to agree to
0.100 mm. In free air the drive joint is still **moving** when the controller ends the goal,
so the two instruments read one joint at two instants: I1 is the position at the instant the
goal ends, I3 is the last `/joint_states` sample at or before the result **arrives**, a few
milliseconds later, by which time the joint has closed further. The measured deltas run
**0.1017 to 0.6909 mm** across all 57 trials — bounded by roughly one `goal_tolerance` of
width, about ten times V4's tolerance — and no action round trip is short enough to close it. **V4 was applied
literally: every Arm A trial is excluded from the DISTRIBUTION**, so no median survives to
test. A1b is a question about where a width fell; it is answered per trial from I1 without any
distribution. **A1's own verdict and A1a survive V4 untouched**, because both are read from
I2's exact booleans and from `Grasp.Result.holding`, not from a width — and V4 excludes a
trial *"from the distribution"*, which is a statement about widths. §3.4 records the one place
where the per-trial substitute is looser than the form it replaces.

**Deviation 2 — §5.1's refinement is registered against a `holding_F` flip that does not
occur, and §7.1 registers the alternative in the same breath.** Free air ends
`reached_goal = true`, so `holding_F` is false at every command and there is no flip to
bracket. §7.1 words the reported quantity as *"the lowest commanded width at which `holding_F`
flips to true — **or, if A1a is false throughout, at which A1b goes INSIDE**"*. So `A_REFINE`
brackets the **A1b** crossing, at the same registered **0.05 mm** step and the same three
trials per point. **The step is unchanged; only which crossing it brackets is**, and §7.1 is
where that choice was registered. Rule N-A still applies to A1, which is a separate verdict
and is not refined by that grid.

**Deviation 3 — V4 is UNEVALUABLE, not failed, for Arm D's `Pick` door.** `Pick` returns no
`Grasp.Result`, so that close has **no I1 at all**, and a rule comparing two instruments
cannot be applied where only one exists. **It is not failed** — a trial missing an instrument
has not exceeded a tolerance — and excluding it would empty the `w_reached` and `d_narrow`
distributions for the **shipped production path**, which is precisely what ADR-0052 §A.10
item 2 asks for. Those 8 trials stay in the distribution and are counted separately.
**Trials that have both instruments and fail the comparison are still excluded, literally.**

**Deviation 4 — Arm D's `pick45` decision quantity is I3 and not I1, for the same reason.**
Every `pick45` record carries `w_reached_source` saying so. **The VERDICT for that door is
`Pick.Result.holding`**, which **is** the shipped predicate's own answer on that close
(`skill_server.cpp:1215-1219`), not a reconstruction.

**One thing that is not a deviation, stated so it is not mistaken for one.** `analyse.py` was
written before the first campaign trial, which is the point — a rule implemented after the
data has been seen is a rule chosen by the data. Every constant in it names the `criteria.md`
section it is quoted from. It re-runs to byte-identical output over the committed `raw/`.

## 7. Two failures recorded rather than smoothed, and one shape they share

### 7.1 A discarded Arm D block-1 attempt — a TF timeout on a cell that came up

The first `D_B1` attempt **collected zero trials and wrote no trials file**, so re-running was
a **fresh attempt** and **V8 was never engaged**: nothing was topped up, because there was
nothing to top up. Its logs are **preserved rather than overwritten**, as
`raw/logs/D_B1_attempt1_discarded_tf_timeout.{harness,sim,load}.log`.

It died on the harness's own **420 s ceiling** waiting for a transform from `cite_world` to
`cell_a__table_pick__surface` (`harness/cell.py:394`). **The cell was not the fault, and its
own log says so:** `frame_server.py` reported *"published 21 static transform(s)"*, the launch
printed `CITE_SIDE_READY side=plant zone=cell_a`, **no node died**, and **`Unknown frame` does
not appear once** in that sim log. Container load at the discarded attempt was 3.73 (1 m) and
3.20 at the attempt that succeeded 17 minutes later, so load does not separate them either.

**Not attributed.** DDS discovery, transient-local delivery on subscription match, and the
listener's own setup are all consistent with what was observed, and **nothing kept separates
them**. The precedent for publishing a discarded attempt rather than quietly re-running is
`2026-09-01-grasp-discrimination/raw/FN_B2_attempt1_discarded_geometry.json`.

### 7.2 A lost bring-up during the shakedown — recorded, not log-verified

The first Arm A **shakedown** attempt never announced readiness and collected no trial. Its
harness-side log is kept as `raw/shakedown/logs/A_SHAKE_lost_bringup_attempt.log`; **its
primary sim log was overwritten by the retry**, so the chain below is **recorded in
`raw/shakedown/NOTES.md`, not preserved as evidence**, and must not be presented as
log-verified. As recorded: `move_group` on `arm_1` logged `Unknown frame: cite_world` twelve
times, `planning_scene_loader.py` reported *"move_group refused the planning scene diff for
zone 'cell_a'"* and exited 1, the launch tore the cell down, and `parameter_bridge` died `-6`
on a glibc `pthread_mutex_lock` assertion during that teardown — the teardown signal family
CLAUDE.md §2 already carries. The readiness gate caught it and the block produced nothing,
which is what that gate is for. **Shakedown output is excluded from every figure here.**

### 7.3 Three observations of one shape, named and not diagnosed

Together with [open-work #55](../../open-work.md) — a paired bring-up whose plant-side
`planning_scene_loader.py` exited 1 fourteen milliseconds after that `move_group` logged
`Unknown frame: cite_world` — these are **three observations of one shape: a consumer that
never learned the cell's static frames.**

**What makes the third one worth recording here is that its consumer was not MoveIt.** It was
an ordinary `tf2_ros.TransformListener` in a **separate process**, started after the frame
server had already published, and it waited 420 s for a transform that a `move_group` in the
same cell had no trouble with. Two of the three are MoveIt's scene load; this one is not, so
"MoveIt's startup sequencing" does not describe the set.

**It is out of this campaign's scope to attribute, and this document does not diagnose it.**
Three events, on one machine, with nothing registered in advance. It is recorded because a
bring-up that fails silently is a failure class this project has paid for before.

## 8. The machine, the validity rules, and what host load could and could not reach

| | |
|---|---|
| Host | Apple **M4 Pro** (`Mac16,8`), 12 cores, 24 GiB, macOS **26.5.2** (Darwin 25.5.0, build 25F84) |
| Container | Docker Desktop, Linux VM, 12 CPUs / 7.65 GiB, `overlayfs`, `Linux-6.10.14-linuxkit-aarch64` |
| Isolation | `COMPOSE_PROJECT_NAME=cite-digital-twin-3748020299`, `ROS_DOMAIN_ID=99`, own build/install/log volumes |
| Environment | `./scripts/doctor` **25 passed, 0 failed, 1 skipped**; `./scripts/build` **23 packages finished**; `./scripts/test` **exit 0** — re-run before **every** campaign invocation and recorded in `raw/provenance.txt` |
| `MODEL_HASH` | source and installed agree on every block (`95dbbdd9…`), so no block ran against a stale install |

**Host load, recorded per block rather than claimed, and it is not a quiet host.** The
container's 1-minute load average at the start of each block: B **3.09**, `A_B1` **4.11**,
`A_B2` **3.79**, `D_B1` **4.91**, `D_B2` **4.88**, `C_B1` **8.39**, `C_B2` **5.85**,
`A_REFINE` **3.74**, on 12 container CPUs. **The macOS host's own 1-minute average read 17.90
at the first campaign invocation** — far above the 2.70 `criteria.md` §9 recorded when it was
written — and 4.49 and 4.55 at the two later ones. **This host was not quiet and could not be
made quiet**, exactly as the capacity and grasp-discrimination campaigns found and said.
**Every block header records the load from `/proc/loadavg` inside the container VM, which is
not the macOS host §9 names**, and both are reported above rather than one being passed off as
the other.

**What that threatens, argued rather than asserted.** Every width here is simulation state
sampled in simulation time — the drive joint's own position, contact-sensor stamps, and widths
derived from a static linkage — so load moves how long a trial takes and **not where a joint
stops**. The one route to the physics is a missed real-time deadline changing the interleaving
of controller updates with physics steps, which is why the load is recorded per block and why
V6 exists; **V6 did not fire in any arm**, though §4.2 records that Arm C's margin is only a
factor of two. **Arm B has no physics at all** and is bit-identical across replicates.
`raw/logs/B_010_54.00.log` carries controller-manager overrun warnings throughout, on a rig
with no simulator, which is a direct reading of how loaded the machine was.

**No real-time-factor claim is made from this campaign** (`criteria.md` §1). Capacity is
settled elsewhere — cite
[`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
and [`2026-09-01-capacity-on-shipped-main/`](../2026-09-01-capacity-on-shipped-main/ANALYSIS.md).

**All six pre-registered predictions held.** P1, P2, P3, P4, P5 and P6, each stated in §7.5
with what would refute it, and none was refuted. **That is a weaker result than it sounds:**
P1, P3 and P6 are consequences of the controller's own terminating rule and of a deterministic
plugin, and were close to arithmetic before the campaign ran. The two that could have gone
either way are **P2**, which located a crossing the instrument choice alone could have moved
(see `raw/shakedown/NOTES.md`), and **P4**, whose mechanism §7.3 recorded as the least certain
in the campaign.

## 9. What this campaign does not establish

Registered in `criteria.md` §8 before the first trial, and none of it moved.

- **Anything about the physical gripper.** ADR-0052 records there is **no
  `GripperActionController` on the hardware path at all**. **Nothing here is a P2 result**,
  and Phase 2.B bring-up is the only thing that would settle it.
- **The wide edge.** **Rule W fired.** The campaign has not tested it; closest approach
  2.4223 mm against a 0.100 mm MIS. ADR-0052 §A.9.5 stands unchanged, and `stall_band_wide_m`
  is no more evidenced after this campaign than before it.
- **The false-positive flip bracketed to 0.05 mm**, which ADR-0052 §A.10 item 2's second
  bullet also asks for. Arm B's stop grid is 2.00 mm and locates the flip only to
  (46.00, 48.00] mm at the narrow side. **That bullet of the gate is not met here.**
- **Where a real jam stops.** Arm B is a synthetic stop at a declared position. ADR-0052
  §A.9.2 stands unchanged and this campaign does not narrow it.
- **Whether the stall distribution moves with the commanded width** (ADR-0052 §A.9.1). That
  is the 2026-09-01 campaign's D2, reported INCONCLUSIVE there by two of its own rules and
  stated there to be about 25x too small. **This campaign is smaller on that question, not
  larger**, and any appearance of an answer in Arm D's two conditions is an artefact of n.
- **Why the drive joint reads narrower than the part it holds** (ADR-0052 §A.9.3). F's narrow
  edge must cover exactly this quantity and nothing here isolates it. Sampling the five
  follower joints alongside `drive_joint` through a hold is the instrument that would.
- **A closing stroke's behaviour in Arm B's region** — structurally, §5.2.
- **A rate of anything.** Every count is over the trials that ran: n = 3 per Arm A command,
  n = 3 per jam (n = 2 at one control), n = 3 per yaw setpoint, n = 8 per Arm D condition. One
  machine, one part, one arm, one timestep, one effort, one facility with **one declared part
  width** — F's discrimination *is* the width of the window and the window widens with the
  declared spread (ADR-0052 §A.5), and **the shipped interval is degenerate at 50.0–50.0 mm**.
- **Any timestep but 0.001 s**, any part but the 50 mm cube, any arm but `arm_1`, any effort
  but 60 N, and vendor collision geometry. The friction campaign found grasp quality varies by
  a factor of 24 across a 4x timestep change; every figure here is at one timestep.
- **Grasp quality.** Whether the part is held *well* is the friction and offset campaigns'
  question. Per ADR-0029 a scenario may assert where a part ends up and may not assert how it
  is held; this campaign reads the close and stops.
- **The three bring-up failures of §7.** Not attributed, and this document does not diagnose
  them.

## 10. What this campaign does not decide

**This campaign chooses nothing**, and that was registered in `criteria.md` §0 before any
number existed so that no number could be read as an argument for one.

- **It does not set the band.** `stall_band_narrow_m` and `stall_band_wide_m` are declared
  provisional in L0. This document reports where the observed distributions sit relative to
  those edges and **picks no value**.
- **It does not amend ADR-0052, move its status, or decide whether the monotonicity term
  `reached > commanded` returns.** B1 REPRODUCED is a measurement, not a recommendation.
- **It does not decide whether the branch merges.** A campaign is not a review verdict, and
  the branch it measures is **unmerged** — a merge, rebase or force-push before the campaign
  completed would have invalidated it (V1, §0). `d3eeac4` remains an ancestor of the branch
  head and the code under test never moved.
- **No threshold, ceiling, tolerance or band anywhere in the tree was changed**, and none may
  be changed to absorb anything found here. **Neither edge of the window may be widened to
  make a trial pass** — `gripper.hpp` says so on the declaration itself.
- **Nothing in `model/`, `workspace/src/` or `tools/` was edited.** The harness lives entirely
  under `harness/` in this directory.

Where a figure above bears on a decision, it is a quantity with its consumer named and the
sentence stops there:

| Quantity | What it bears on |
|---|---|
| B1 REPRODUCED, 9/9 in-window opening jams, controls rejected at both edges (§2) | whether the monotonicity term returns — ADR-0052 §A.3 dropped it, and this is what dropping it costs on this rig |
| A1a false at 57/57 (§3.1) | which of F's two conditions rejects free air on the production backend |
| A1b INSIDE at 27/57, crossing bracketed to (46.60, 46.65] mm (§3.2–3.3) | `gripper.hpp:341-342`'s free-air sentence, which is false as written |
| `holding_S` true on 0/8 at a witnessed 48.0 mm grasp against `holding_F` true on 8/8 (§5.1) | ADR-0052 §A.8's predicted recovery, now measured on the implemented predicate |
| minimum `d_narrow` 0.9269 mm, positive (§5) | the narrow edge's headroom at the shipped command on this cell |
| closest approach to the wide edge 2.4223 mm, rule W firing (§4.2) | ADR-0052 §A.9.5, unchanged — the wide edge is still unevidenced |
| the three `PRECONDITION_FAILED` refusals with no motion (§5.2) | the measured cost of `resolve_grasp_width`'s ceiling, which §A.8 already states is real |

**The choice is the project owner's.** This campaign exists to make it decidable.

## 11. Reproduction

`harness/README.md` carries every command, including the one-arm-at-a-time forms and the
refinement grid's bracket. The whole campaign is:

```sh
docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh
```

and every figure in this document comes from:

```sh
python3 docs/measurements/2026-09-02-option-f-regions/harness/analyse.py
```

which applies §7's rules to `raw/` and **prints them whether or not they fire**. It re-runs to
byte-identical output over the committed raw. Nothing in this document was derived by hand
from the trial files that the analyser does not print, except where a per-trial column is
quoted directly from `raw/*_trials.json` and named as such.

**Figures stay in this directory.** Nothing here is copied into ADR-0052, `CLAUDE.md`, the L0
comments or any layer document (P1). **Cite the directory.**
