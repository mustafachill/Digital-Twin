# Criteria — where option F's window flips, bracketed to 0.05 mm at both edges

**Written and committed before the first campaign trial ran, before the harness exists, and
before anything was run.** Frozen from that commit ([`../README.md`](../README.md), rule 1).
Any interpretation that had to change afterwards is recorded as a numbered deviation in
`ANALYSIS.md`, applied to data already collected — never by re-running until the definition
suited.

- **Date opened:** 2026-09-03
- **Branch under measurement:** `feat/close-phase-debts`
- **BASE_COMMIT:** **`c38a42c`**. Every figure below is a property of the tree at that commit.
  V1 in §10 is what spends it.
- **The code under test has not moved since the campaign that measured it.** The predicate,
  the L0 declaration it reads, the generated plan that delivers it and the test fixture that
  drives it are **byte-identical** between `d3eeac4` — the head of the branch
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md) measured — and
  `HEAD` today: `git diff d3eeac4..HEAD -- workspace/src/cite_skills/src/gripper.cpp
  model/assets/types/end_effectors/xarm_parallel_gripper.yaml
  workspace/src/cite_generated/bringup/cell_a_plan.yaml workspace/src/cite_test_hardware/` is
  **empty**, read on 2026-09-03, and `git merge-base --is-ancestor d3eeac4 HEAD` succeeds.
  **This campaign therefore measures merged code, not a branch**, which is the one condition
  the earlier campaign had to carry and this one does not.
- **The record that asks for it:**
  [ADR-0052](../../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) **§A.10 item 2,
  second bullet** — *"the false-positive side — the stop sweep re-run, which stops F admits,
  and the flip bracketed to at least 0.05 mm against the floor §A.6 derives"*. **That bullet,
  and nothing else in §A.10.** Item 1 is met and is held as tests
  (`tools/tests/test_stall_band.py::TestTheReanalysisGate`, and the validator rule
  `stall-band-admits-a-stall-on-nothing`); item 2's other three bullets were run by the
  2026-09-02 campaign and are that campaign's, not this one's; items 3, 4 and 5 are code and
  policy rather than measurement. §8 names what this campaign therefore cannot settle.
- **The record that derives the quantity being compared against:** ADR-0052 **§A.6**, which
  bounds `stall_band_narrow_m` from above by *"the distance from nominal to the floor below
  which a stall on nothing starts being reported as a grasp"* and puts that floor at
  **47.1215 mm**. §2.2 below reproduces it in closed form before any trial.
- **The record that constrains it:**
  [ADR-0022](../../adr/0022-gripper-as-ros2-control-controller.md). The controller reports and
  does not interpret; deciding what a stall means is L3's job. This campaign measures the L3
  decision and changes neither half.
- **The record that makes the rig legitimate:**
  [ADR-0040](../../adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md).
  `cite_test_hardware/JointStopSystem` is a **test-only** component, barred from production by
  its own `on_init`, and it is the only thing in this repository that can put a drive joint at
  a chosen position and hold it there.
- **The campaigns this one does not replace, and does not edit.**
  [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/ANALYSIS.md) —
  whose false-positive arm is the *stop sweep* the gate says to re-run, and whose flip is
  §A.6's floor — and
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md), which ran the
  gate on the implemented predicate and reports of itself that this bullet is unmet. **Both
  stay frozen**: no file in either is edited, re-run or re-analysed here, and their figures are
  cited rather than copied (P1). **No figure from either appears anywhere in this campaign's
  data.**

---

## 0. This campaign decides nothing

The instruction that opened it was **measure, do not decide**, and the constraint is registered
here rather than remembered later.

- **Nothing here sets the band.** `stall_band_narrow_m` and `stall_band_wide_m` are declared
  `PROVISIONAL` in L0 with their provenance written into the comment beside them. This campaign
  locates where the shipped predicate's verdict flips and **picks no value**, proposes none, and
  argues for none.
- **Nothing here moves ADR-0052's status**, amends it, or writes into it. The record is
  `Accepted` on the owner's choice of option F and stays exactly as it is.
- **Nothing here decides whether the removed monotonicity term `reached > commanded` returns.**
  That is an **open project-owner decision**, recorded as open in ADR-0052 §B.4 and in
  [`docs/open-work.md`](../../open-work.md). The 2026-09-02 campaign registered before its first
  trial that it would not take it; **neither will this one**, and this sentence exists before
  any number does so that no number produced here can be read as an argument for either answer.
- **No threshold, ceiling, tolerance or band anywhere in the tree is changed**, and none may be
  changed to absorb anything found here. **NEITHER EDGE MAY BE WIDENED TO MAKE A RUN
  PASS** — that is `gripper.hpp:375-379`'s own sentence, on the declaration itself, and it is
  repeated here because a campaign is where the temptation arrives.
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/` or `scripts/` is edited.** The
  predicate is measured exactly as the tree at `c38a42c` ships it. All five paths are watched by
  V1 in §10, for the reason the 2026-09-02 scenario-ceilings campaign gave when it widened its
  own watch from three to five: everything this campaign consumes lives in them.
- **The harness lives entirely under `harness/` in this directory**, and `raw/` beside it.
- **The two campaigns above are copied from, never edited.** Any file derived from either
  carries a header naming the source file and the commit it was copied at, which is the
  2026-09-02 campaigns' practice rather than a README requirement.
- **`main` ships convex-hull collision geometry**
  ([ADR-0028](../../adr/0028-convex-hull-collision-meshes.md), promoted against the clause
  [ADR-0051](../../adr/0051-restate-the-hull-grasp-gate.md) restates). This rig runs no
  simulator and touches no collision geometry, but it is built from the same generated
  description, and V2 below checks that the description it publishes is still the shipped one.

---

## 1. The question, and the ones it is not

**Q — where does the shipped predicate's verdict flip, at each edge of its window, bracketed to
0.05 mm or finer, and how far is the narrow flip from the floor ADR-0052 §A.6 derives?**

The gate names *the* flip, singular. **The window has two edges and neither has been located.**
The 2026-09-02 campaign's stop grid is 2.00 mm and it places the narrow flip only in
(46.00, 48.00] mm and the wide one only in [52.00, 54.00) mm; it says so of itself in its §2.2
and again in its §9. **This campaign brackets both, reports both, and says which is which.**

**What this campaign is honestly for, stated before any number exists.** The flip's location is
*computable*: §2.2 below derives 47.6150 mm and 52.3850 mm from the L0 declaration in closed
form, before any trial. **So this is a verification campaign, not a discovery campaign**, and
what it verifies is not arithmetic but **delivery** — that the band L0 declares reaches the
running predicate unchanged through the generator, the plan, the launch parameters and the
skill server, and that the verdict a caller receives over the `Grasp` action flips where the
declaration says it should. A campaign that reimplemented the predicate would measure its own
arithmetic; this one reads `Grasp.Result.holding` off a running node (§3).

**Rule D in §7.5 is what makes that a question rather than a formality.** If the measured flip
does not contain the computed edge, that is a finding about the predicate, the delivery chain
or the linkage model, and it is reported as one — **not reconciled, not re-run, not smoothed**.
It is registered here, before the answer is known, because a campaign that can only confirm is
not a campaign.

Not in scope, deliberately:

- **This measures the simulator's control stack, and not even that far.** There is **no
  simulator in this rig at all** — no Gazebo, no physics, no work-piece. What runs is a real
  `ros2_control_node`, a real `move_group`, a real skill server and a test-only hardware
  component. **Nothing here is a P2 result**: ADR-0052 records that the physical gripper is
  driven through the SDK's service layer and has **no `GripperActionController` at all**.
- **This is not a grasp measurement.** Nothing is between the pads and nothing can be. Whether a
  real part is held, held well, or held at all is the friction, offset and grasp-discrimination
  campaigns' question, and per ADR-0029 a scenario may assert where a part ends up and may not
  assert how it is held.
- **This is not where a real jam stops.** A synthetic stop at a declared position is not a
  fouled finger. ADR-0052 §A.9.2 records that F's central claim rests on a quantity nobody has
  measured, and **this campaign does not narrow it by one millimetre**. Rule G in §7.5 is the
  refusal that keeps that straight.
- **This is not a rate.** Every count is a count over the trials that ran, on one machine, on
  one image, at one commit, with one facility declaring one part width.
- **Speed is settled elsewhere.** No real-time-factor figure is produced or quotable here; this
  rig runs on the wall clock with no `/clock` publisher at all.

---

## 2. The predicate as implemented, and the arithmetic reproduced before any trial

`cite_skills::gripper_is_holding` (`workspace/src/cite_skills/src/gripper.cpp:142-161`, read at
`HEAD` on 2026-09-03):

```
holding  <=>  stalled
              and not reached_goal
              and narrowest_m > 0 and widest_m > 0
              and w_reached  >  narrowest - stall_band_narrow_m
              and w_reached  <  widest    + stall_band_wide_m
```

with `w_reached = gripper_width_for(report.reached_position, travel)` and
`report.commanded_width_m` **deliberately not read** — the comment on the line where the command
used to be consumed says so. **Both window comparisons are strict**, which decides how a grid
point landing exactly on an edge would be classified; §5.1 keeps every grid point off the
computed edges by construction.

**The verdict a caller sees is that function's return value, not a copy of it.**
`skill_server.cpp:2233-2235` assigns `outcome.holding = cite_skills::gripper_is_holding(...)`
and `:2227-2228` assigns `outcome.reached_width_m = cite_skills::gripper_width_for(...)`;
`execute_grasp` (`skill_server.cpp:955-976`) copies both onto `Grasp.Result` **before** it
checks anything. **`execute_grasp` applies no `resolve_grasp_width` refusal** — that refusal is
on the `Pick` path (`skill_server.cpp:1077`) — so the `Grasp` door accepts any commanded width,
which §5.2 relies on and states.

**Reproduced independently on 2026-09-03, before this file was committed**, in a standalone
script from the linkage block of
`model/assets/types/end_effectors/xarm_parallel_gripper.yaml` and the facility block of
`workspace/src/cite_generated/bringup/cell_a_plan.yaml:50-52`:

| quantity | value | source it must agree with |
|---|---|---|
| `pivot`, `crank`, `phase` | 0.009 m, 0.055000398 m, 0.870017045 rad | ADR-0052 §2.1 |
| `opening(0.00)` / `opening(0.85)` | 88.930 mm / 1.646 mm | `test_gripper.cpp:53-54` `kOpenWidth`, `kClosedWidth` |
| declared part interval | 50.000 / 50.000 mm | plan `workpieces.narrowest_width_m`, `widest_width_m` |
| declared band | 2.385 / 2.385 mm | L0 `stall_band_narrow_m`, `stall_band_wide_m` |
| **`edge_lo`** | **47.6150 mm**, drive position **0.428191 rad** | `test_gripper.cpp:90` `kWindowLow` |
| **`edge_hi`** | **52.3850 mm**, drive position **0.382862 rad** | `test_gripper.cpp:91` `kWindowHigh` |
| `gripper_discrimination_margin_m(45.0 mm)` | 2.137972 mm | ADR-0052 §A.11's 2.137972 mm |
| validator ceiling, 50.0 − that margin | 47.862 mm | ADR-0052's 47.86 mm |

Every one of these reproduces the value the record or the shipped unit test already carries.
**The arithmetic is therefore not in question in this campaign; what the running stack does with
it is.**

### 2.1 The quantities, named once

| symbol | definition | units |
|---|---|---|
| `w_stop` | the stop width this trial declares — the lever, converted to a drive position by the shipped `gripper_position_for` | mm |
| `w_cmd` | `Grasp.Goal.width_m`, the width commanded | mm |
| `w_reached` | `gripper_width_for(reached_position)`, the width the predicate consumes, read as `Grasp.Result.reached_width_m` | mm |
| `holding_F` | the **shipped** predicate's verdict, read from the running node | — |
| `holding_S` | the **superseded** command-referenced predicate's verdict on the same inputs, from a build of `4ef2d7c` (§4.3) | — |
| `flip_F_lo` / `flip_F_hi` | the half-open interval of `w_stop` containing F's verdict change at each edge | mm |
| `flip_S_lo` | the same for `holding_S` at the narrow side — this campaign's own re-derivation of §A.6's floor | mm |

### 2.2 Four numbers computed before any trial, so that the sweep can be wrong

**The two edges.** From the shipped declaration, `edge_lo = 47.6150 mm` and
`edge_hi = 52.3850 mm`. On a rig where the joint rests exactly on its declared stop, `w_reached`
equals `w_stop`, so **F's verdict is predicted to be `true` exactly on `(47.6150, 52.3850)` mm
and `false` outside it**.

**The floor, and that it is arithmetic rather than only a measurement.** ADR-0052 §A.6 states
the floor as *"the FP flip, bracketed to 0.05 mm and containing 47.1215 mm"*, measured by the
2026-09-01 campaign on the superseded predicate at the shipped 45.0 mm command. Solved here in
closed form on the superseded condition `w_reached − w_cmd > 2·tolerance(q_reached)` at
`w_cmd = 45.000 mm`, the flip lands at **47.121519 mm** — reproducing §A.6's cited value to the
digits it states. **This matters for rule H**: the comparison the gate asks for is between a
width measured here and a width on the same linkage, not between two machines' timings.

**The distance the gate is asking about.** `edge_lo − 47.1215 mm = 0.4935 mm`. **That number is
computed from the two records and is not this campaign's datum**; it is registered here so that
the measured distance can be compared with it and can differ.

**Where the four brackets are predicted to land**, at the fine step registered in §7.0:

| bracket | predicted interval | why |
|---|---|---|
| `flip_F_lo` | **(47.60, 47.65] mm** | `edge_lo = 47.6150` mm lies inside it |
| `flip_F_hi` | **[52.35, 52.40) mm** | `edge_hi = 52.3850` mm lies inside it |
| `flip_S_lo` | **(47.10, 47.15] mm** | the closed-form floor 47.121519 mm lies inside it |
| `holding_S` at every wide stop | **`true` throughout** | the superseded predicate is a half-line with no upper edge at all; §7.5's P4 |

---

## 3. The two arms and one control, and rule T over them

**The arms are named in words, not letters, on purpose.** The 2026-09-02 scenario-ceilings
campaign's pre-freeze review found four rule-letter collisions in its own draft; every letter in
this file names a **rule** and nothing else.

| arm | question | stops swept | stroke |
|---|---|---|---|
| **LO** | where F's verdict flips at the **narrow** edge, and where the superseded predicate's flips | 46.00 → 48.00 mm | closing |
| **HI** | where F's verdict flips at the **wide** edge | 52.00 → 54.00 mm | closing |
| **CTL** | does the **stop** produce the stall, or does the plugin? | none — no stop at all | closing |

> **Rule T — inherited verbatim from the 2026-09-02 campaign's §3.** The arms are not each
> other's evidence. A clean result in one says nothing about any other, **every verdict is
> stated per arm**, and an inconclusive one belongs in the verdict rather than in a footnote.
> In particular, **arm HI locating a flip says nothing about whether any part or any jam ever
> reaches it** — rule G is what carries that.

**Both arms read the shipped predicate rather than a copy of it.** `Grasp.Result.holding` **is**
`cite_skills::gripper_is_holding`'s return value and `Grasp.Result.reached_width_m` **is**
`gripper_width_for(result->position)` (§2). **No reimplementation of the predicate appears in
any reported verdict.** The reference implementation under `harness/` is used only for the §2
cross-check and for converting stop widths to drive positions before any trial, and the value
the rig actually declares comes from the shipped `gripper_position_for` through the harness's
compiled front end.

---

## 4. Instruments, registered before the first trial

### 4.1 The verdict and the widths

| # | Quantity | Instrument |
|---|---|---|
| **I1** | the verdict and the width the predicate consumed | `Grasp.Result` — `holding`, `reached_width_m`, `measured_effort_n`, `result`. Driven with `expect_object=false`, so the fields are reported rather than converted into an `EXECUTION_FAILED` (`skill_server.cpp:994-1001`). **I1 is the decision quantity.** |
| **I2** | `stalled` and `reached_goal`, which no result message carries | the skill server's own line, `gripper: commanded %.1f mm, reached %.1f mm, stalled=%s, reached_goal=%s, effort=%.1f -> holding\|empty` (`skill_server.cpp:2245-2253`), scraped from the block log. **The two booleans are exact; the two widths there are `%.1f` and are two grid steps coarse**, so they are used for nothing but V4's second clause. |
| **I3** | `w_reached` independently of the skill server | the last `arm_1_drive_joint` sample on `/joint_states` at or before the result arrives, mapped through the shipped closed form. The cross-check V4 is the rule over, never a reported decision quantity. |
| **I4** | the controller's own typed answer at full precision | a second `GripperCommand` goal against a joint already resting on the stop, recorded as **a second event** and not as a repeat: it is the only full-precision source of `stalled`, `reached_goal` and `position`. |

### 4.2 The rig

| # | Quantity | Instrument |
|---|---|---|
| **I5** | that the stop engaged | `JointStopSystem`'s own `has reached a declared stop at %f` warning in the block log (`joint_stop_system.cpp:189-193`) — read at `HEAD` on 2026-09-03. |
| **I6** | that the fixture did not manufacture the fault | the absence of the plugin's `starts at %f, outside its declared stops [%f, %f]` refusal (`joint_stop_system.cpp:176-181`). A launch carrying it produced **no data at all** and is reported as a launch that did not run. |
| **I7** | that the joint rests **on** the stop and not merely near it | the drive joint's rest position, in **width** terms, against §7.0's rest tolerance. §7.0 explains why the inherited 0.001 rad is too coarse for this campaign and what replaces it. |
| **I8** | the code, the model and the description that actually ran | `git rev-parse HEAD`, `git status --porcelain`, `git diff c38a42c..HEAD` over the five watched paths — **taken at both ends of every block** — the running cell's `MODEL_HASH`, and the count of hull collision-mesh references in the description the rig publishes. V1 and V2. |
| **I9** | the host's state | the one-minute, five-minute and fifteen-minute load averages from `/proc/loadavg`, at both ends of every block, read **inside** the container, with §9's demonstration that on this host that is the host's own reading. |

**No Gazebo-transport process exists in this rig**, so CLAUDE.md §10's partition rule has
nothing to bind here. **If the harness ever grows one it goes through `cite_bringup/gz.py` and
nothing else** (ADR-0042) — registered now rather than discovered by a probe that reaches no
world and exits 0.

### 4.3 The superseded predicate, as a comparison quantity only

**`holding_S` is computed by building the base commit's shipped source, not by rewriting it.**
A detached `git worktree` at **`4ef2d7c`** — the last commit before option F landed, verified an
ancestor of `HEAD` on 2026-09-03 — is built once; the harness's superseded front end links that
build's `cite_skills` and adds no arithmetic of its own. Its sha256 and the worktree commit are
recorded in `raw/provenance.txt` per build, in the shape the 2026-09-01 and 2026-09-02 campaigns
both used.

> **`holding_S` enters no verdict of arm LO or arm HI.** It is reported beside `holding_F` for
> two reasons and no others: so that `flip_S_lo` — this campaign's own re-derivation of §A.6's
> floor, on this rig, at the same command — can be measured rather than imported; and so that a
> reader can see which region the change opened. **A disagreement between the two predicates is
> a datum and not a defect**, in either direction, and deciding what to do about one is
> ADR-0052's and the owner's (§0).

---

## 5. What is varied, and what is held fixed

### 5.1 The lever is the stop position, and the stroke closes

**The rig is the 2026-09-01 campaign's false-positive rig, which is the sweep the gate says to
re-run.** A real `ros2_control_node` over `cite_test_hardware/JointStopSystem` on
`arm_1_drive_joint`, with a real `move_group` and a real skill server, the node set
`workspace/src/cite_bringup/test/test_grasp_predicate_launch.py` uses. `stop_upper_rad` is the
jam, converted from `w_stop` by the shipped `gripper_position_for`; `stop_lower_rad` is
**−1.0 rad**, inert, and it brackets the joint's initial position so the fixture's
start-outside-the-stops refusal cannot fire. **The joint starts open at q = 0** — its default —
so **no `initial_value` injection is needed at all**, unlike the 2026-09-02 campaign's reversed
opening-stroke rig.

**Why a closing stroke and not an opening one, registered before any trial.** Three reasons,
and the third is the one that decides it:

1. **It is the stroke the floor was measured on.** §A.6's 47.1215 mm comes from a closing-stroke
   sweep at the shipped command. Bracketing F's flip on the same stroke makes the comparison the
   gate asks for a comparison between like things.
2. **It reaches both edges from below.** Every stop in both arms is **wider** than the command,
   so the joint closes from open, meets the stop before its goal, and is held there.
3. **It is what lets the command be the shipped default** — §5.2. An opening stroke into these
   stops requires a command wider than 54 mm, which no production caller sends.

**Under F the stroke direction cannot enter the verdict**, because the predicate reads
`w_reached` and two flags and nothing else (§2). **That is a claim about source, and this
campaign does not test it**: the 2026-09-02 campaign's opening-stroke arm and this one's
closing-stroke arms are on different commands as well as different strokes, so their verdicts at
the four stop widths they share are reported side by side as an observation and **are never
differenced** (rule H).

**The stop grids, in two stages, both steps registered here and only the fine stage's *location*
determined by the data.** That distinction is the 2026-09-02 campaign's, restated because it is
the thing most easily argued about afterwards: *the step is a threshold and is registered; the
interval is a bracket and is located by the data — that is bracketing, not a threshold chosen by
the data.*

**Stage 1 — coarse, 0.25 mm.**

```
arm LO:  46.00 46.25 46.50 46.75 47.00 47.25 47.50 47.75 48.00   (mm)
arm HI:  52.00 52.25 52.50 52.75 53.00 53.25 53.50 53.75 54.00   (mm)
```

Each span is exactly the interval the 2026-09-02 campaign left open at its 2.00 mm grid, and its
two endpoints are that campaign's two anchors. **They are re-measured here, not inherited.**

**Stage 2 — fine, 0.05 mm, inclusive of both endpoints of the located coarse interval.** Six
stops per refinement. Three refinements are registered:

- **LO-F** — across the coarse interval containing F's narrow verdict change.
- **HI-F** — across the coarse interval containing F's wide verdict change.
- **LO-S** — across the coarse interval containing the **superseded** predicate's narrow verdict
  change, conditional on V12. This is `flip_S_lo`, and it is a **secondary** quantity: the gate
  does not ask for it, and its absence does not make the gate's bullet unmet.

**No grid point can land on a computed edge.** 47.6150 and 52.3850 mm are not multiples of
0.05 mm offset from the grid origins above, and 47.121519 mm is not either, so the strictness of
the window's comparisons never has to be exercised at a measured point. Registered because a
grid point exactly on a strict edge would produce a verdict that is correct and unreportable.

Held fixed unless named:

| Quantity | Value | Where it comes from |
|---|---|---|
| Arm under test | `arm_1` | as the friction, hull-grasp, grasp-discrimination and option-F-regions campaigns |
| Simulator | **none** | §1 |
| Between the pads | **nothing**, and nothing can be | §1 |
| `max_effort_n` | 60.0 N, the L0 value | ADR-0052 §5: `effort` is the commanded maximum echoed back, not a measurement |
| `expect_object` | `false` | I1 |
| `stop_lower_rad` | −1.0 rad, inert | §5.1 |
| `use_sim_time` | `false` throughout | there is no `/clock` publisher; a manager waiting for one never runs a control cycle |

### 5.2 The command, and why it is the shipped default

**Every trial in arms LO, HI and CTL commands `w_cmd = 45.000 mm`** — `default_grasp_width_m` in
`model/assets/types/end_effectors/xarm_parallel_gripper.yaml:263`, delivered to L3 as
`gripper_default_grasp_width_m` in the generated plan, and the width `cite_skills::
resolve_grasp_width` returns when a caller supplies none. Four reasons, registered:

1. **It is the production command.** It is what `Pick` uses when `Pick.Goal.grasp_width_m` is
   unset, which is L4's `PickAt` port default.
2. **It is the command the floor was measured at.** §A.6's 47.1215 mm is the 2026-09-01
   campaign's flip at this command, and §2.2's closed form reproduces it at this command.
   Comparing F's flip against it at any other command would be comparing two different
   quantities.
3. **It is the command §A.10 item 1's guarantee is scoped to.** ADR-0052 §B.2 records that the
   subset property — F admitting no width the superseded predicate rejects — is *a property of
   the command*, and that it breaks at a commanded **45.4962 mm**, computed there two ways.
   Below that, the two predicates' admitting sets are nested; above it they are not. **This
   campaign runs inside the scope of that guarantee rather than outside it**, so that
   `holding_F` and `holding_S` on one trial are comparable at all.
4. **It is below every stop in both arms**, so the stroke closes and jams at every point of both
   grids.

**Both flips this campaign brackets are properties of the *window*, not of the command** — the
predicate does not read the command (§2). **That is read from source and is exactly the kind of
claim a campaign should not take on trust**, so it is measured:

> **Sub-condition INV — command invariance.** The **two fine-grid stops straddling each of F's
> two verdict changes** — four stops in all — are additionally run at a second command,
> **`w_cmd = 40.000 mm`**. 40.0 mm is below every stop in both arms, so the stroke still closes;
> it is well inside what `resolve_grasp_width` permits, and the `Grasp` door applies no such
> refusal in any case (§2). **The verdicts must agree point for point.** Rule C in §7.5 is what
> spends this.

### 5.3 CTL — the control that says the stop is what stalls the joint

The same rig with the gripper's `<ros2_control>` block on plain
`mock_components/GenericSystem` and **no stop at all**, commanded to the same 45.000 mm on empty
jaws. This is the 2026-09-01 campaign's FP-C control in shape, and its role is the same: to
establish that the **stop** is what produces the stall this campaign sweeps, and not the
hardware plugin underneath it.

> **CTL is reported and carries no verdict of its own, and this is registered rather than
> decided later.** [`docs/open-work.md`](../../open-work.md) **#25** records that a gripper
> controller over plain mock hardware can report a grasp on empty air, because
> `GenericSystem::read()` never writes the velocity state when the command interfaces are
> position-only. `JointStopSystem` **differentiates** velocity itself
> (`joint_stop_system.cpp`, the `differentiated_` list built in `on_init`), which is why the
> arms above have a working stall detector at all. **CTL is not the instrument that settles
> #25**, it is not powered to, and its result may not be written up as evidence about it in
> either direction.

---

## 6. Design, sample size and order

**Interleave, do not block** ([`../README.md`](../README.md)). A stop position is a description
change and therefore a **relaunch**, so — exactly as the 2026-09-01 and 2026-09-02 campaigns
recorded for the same rig — **the interleaving in this campaign is over the relaunch order**:
one cycle visits every stop of an arm once, and the repeats are successive cycles.

| block | what runs | stops | repeats | trials |
|---|---|---|---|---|
| **LO-C** | arm LO, coarse | 9 | 2 | 18 |
| **HI-C** | arm HI, coarse | 9 | 2 | 18 |
| **LO-F** | arm LO, fine, at F's coarse straddle | 6 | 3 | 18 |
| **HI-F** | arm HI, fine, at F's coarse straddle | 6 | 3 | 18 |
| **LO-S** | arm LO, fine, at the superseded straddle (conditional on V12) | 6 | 3 | 18 |
| **INV** | the four straddling stops at `w_cmd = 40.000 mm` | 4 | 3 | 12 |
| **CTL** | no stop, plain mock | 1 | 3 | 3 |

**105 trials if V12 holds, 87 if it does not.** Each is one launch.

**Why two repeats coarse and three fine.** The rig has no physics and a deterministic hardware
plugin, so **the repeats are expected to be exact replicates** and are taken anyway, to check
the rig rather than to estimate a variance. Two is the minimum that can show a disagreement at
all; the fine stops are the ones that carry every verdict in §7, so they get three. **A non-zero
spread within a stop is a finding about the rig** and is registered as such here rather than
explained afterwards — the shape the 2026-09-01 campaign used, and the shape that caught its own
control's defect.

**Each cycle is a block, and the block index travels on every record**, so a block effect is
visible; V6 is what spends it. **A block that aborts early is reported with the n it actually
reached, and no condition is topped up** (V8).

**Order:** LO-C, HI-C, then the refinements the coarse stages locate (LO-F, HI-F, LO-S), then
INV, then CTL. The coarse stages must complete before any refinement, because a refinement's
interval is located by them; INV depends on knowing which stops straddle; CTL is independent and
runs last so that a failure in it cannot consume the campaign's time budget.

**Quiesce 30 s between a teardown and the next launch**, and record I9 at both ends of every
block.

---

## 7. Thresholds — the decision rules

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.0 Minimum interesting size and the two tolerances, per metric

Every one is derived from **the geometry, the gate, or the system's own declared tolerances**,
never from campaign data.

| Metric | Size | Why this size |
|---|---|---|
| any width in mm | **0.100 mm** MIS | **Inherited** from the 2026-09-01 campaign's rule R via the 2026-09-02 campaign's §7.0. It is the production log line's own `%.1f` resolution and under a tenth of what one `goal_tolerance` is worth in width at these positions |
| **the bracket, at every edge** | **0.05 mm** | **ADR-0052 §A.10 item 2's own number.** *"the flip bracketed to at least 0.05 mm"*. **A bracket is not an MIS** — a 0.05 mm bracket does not resolve a 0.100 mm difference — and rule R below is what stops the two being conflated |
| **the rest tolerance (I7)** | **0.005 mm of width** | one tenth of the bracket step, so that a joint resting on its stop cannot be confused with a neighbouring grid point |
| **the two-instrument agreement (V4)** | **0.005 mm of width** | the same size, for the same reason |

> **The inherited 0.001 rad rest tolerance is too coarse for this campaign, and this is the
> sharpest thing in this file.** The 2026-09-02 campaign's I7 required the drive joint to rest
> within **0.001 rad** of its declared stop, derived there as *"0.100 mm of width through this
> linkage"* — which is right, and which is **twice this campaign's bracket step**. Computed here
> on 2026-09-03 from the shipped linkage: 0.001 rad is **0.1060 mm** of width at `edge_lo` and
> **0.1045 mm** at `edge_hi`, so the inherited rule would admit a trial resting **two grid
> points** from the stop it declared. The same applies to the inherited 0.100 mm V4 agreement
> threshold. **Both are therefore tightened here to 0.005 mm of width** — expressed in width
> rather than in radians so the criterion is uniform in the quantity the predicate consumes,
> which is **4.720e-05 rad at `edge_lo` and 4.785e-05 rad at `edge_hi`**. Tightening an
> inherited threshold rather than reusing it is registered before any trial and is the only
> change this campaign makes to a rule it inherits.

### 7.1 LO1 and HI1 — where F's verdict flips

Report, per stop: `n`, `w_stop`, `w_cmd`, `w_reached` (I1, all repeats at full precision),
`stalled`, `reached_goal`, `holding_F`, `holding_S`, I5, I6, I7's rest error in mm, and the
block index. **The gate's own phrasing — "which stops F admits" — is answered by that table in
full**, at both grids, and not only by the bracket.

> **Rule B — what "bracketed" means, and it is the campaign's decision rule.** An edge is
> **BRACKETED** when **two adjacent fine-grid stops, 0.05 mm apart, carry opposite `holding_F`
> verdicts**, and:
> - every repeat at each of those two stops agrees with its stop's verdict, and
> - both stops pass V3, V4, V5 and V7, and
> - the coarse grid showed exactly one verdict change in that arm (rule U).
>
> The result is reported as a **half-open interval** of `w_stop` whose width is **0.05 mm**,
> together with every repeat behind both endpoints. **A bracket narrower than 0.05 mm is not
> claimed**, because the grid cannot produce one.

> **LO1 — BRACKETED / NOT BRACKETED**, by rule B, over arm LO's fine grid.
> **HI1 — BRACKETED / NOT BRACKETED**, by rule B, over arm HI's fine grid.
> **Each is stated separately.** §A.10 names the flip singular; this campaign reports two, and
> one of them being bracketed says nothing about the other (rule T).

> **Rule N — the refusal, in ADR-0051's rule-S shape and this repository's rule-W shape.** **If
> an arm produces no pair of adjacent fine-grid stops with opposite verdicts, that edge is NOT
> BRACKETED**, the verdict reads *"not bracketed at 0.05 mm, over these stops, at n = N, on this
> rig"*, and **the campaign's silence there may not be read as agreement with §2.2's
> arithmetic**, as a validation of either band value, or as evidence that the edge is where the
> declaration says. §A.10 item 2's second bullet is then **still unmet**, and the write-up must
> say so in those words.

> **Rule U — one flip, or none claimed.** If an arm's coarse grid shows **more than one**
> verdict change, every change is reported, **no refinement is run on any of them**, and that
> edge is **NOT BRACKETED** under rule N. A window with two flips on one side is a finding about
> the predicate or the rig, not a choice of which flip to refine.

> **Rule R — resolution, inherited from the 2026-09-01 campaign's rule R via the 2026-09-02
> campaign's rule R-A.** If the repeats at any stop disagree in `holding_F`, or if
> `w_reached` varies within a stop by more than the 0.005 mm rest tolerance, that stop is
> **INDETERMINATE**; a bracket with an indeterminate endpoint is **UNRESOLVED at 0.05 mm** and
> rule N applies to that edge. And for any metric whose within-stop spread exceeds that metric's
> MIS, a non-detection is **INCONCLUSIVE for that metric — never "no difference"**.

### 7.2 FLOOR1 — the distance from the narrow flip to the floor

**Report, as the gate's own quantity:** the distance from `flip_F_lo` to the floor ADR-0052 §A.6
derives, **as an interval** — because `flip_F_lo` is an interval — with the floor stated as the
cited **47.1215 mm** and the arithmetic of §2.2 named beside it.

**Report separately, and as this campaign's own datum:** `flip_S_lo`, the superseded predicate's
narrow flip **measured on this rig at this command**, bracketed by rule B, and the distance from
`flip_F_lo` to it. **This is the rig-internal form of the same comparison**, and it is what makes
the gate's comparison free of any cross-campaign differencing.

> **FLOOR1 — REPORTED** whenever LO1 is BRACKETED. It carries **no pass/fail**, because ADR-0052
> §A.6 sets no minimum distance and this campaign may not invent one (§0). What it must state is
> the sign: whether `flip_F_lo` lies **above** the floor, which is the direction §A.6's subset
> argument depends on, or below it, which would be a finding.
> **FLOOR1 — NOT REPORTED** if LO1 is NOT BRACKETED. A distance from an unlocated flip is not a
> quantity.

> **Rule H — no cross-campaign differencing, inherited from the 2026-09-02 scenario-ceilings
> campaign.** No **measured** figure from any other campaign is differenced against any figure
> here. The floor is admitted into FLOOR1 **only** because §2.2 reproduces it in closed form
> from the shipped linkage and the declared `goal_tolerance`, so the comparison is between a
> width measured here and a width **computed** here, on one linkage. **The 2026-09-01
> campaign's own bracket around it, its rig, its machine and its trial counts stay in that
> directory** and are cited, never subtracted from anything.

### 7.3 INV1 — command invariance

Report, per straddling stop: `holding_F`, `w_reached` and `stalled`/`reached_goal` at
`w_cmd = 45.000 mm` and at `w_cmd = 40.000 mm`, side by side.

> **INV1 — HELD** if `holding_F` is identical at both commands at all four stops, over all
> repeats.
> **INV1 — VIOLATED** otherwise, *and rule C applies.*

> **Rule C — a command that reaches the verdict is a finding, not an adjustment.** If INV1 is
> VIOLATED, the campaign reports both commands' verdicts per stop and states plainly that
> **the shipped predicate's verdict depends on a value §2 reads it as not consuming**. Nothing
> is re-run, no constant is touched, and no bracket derived at either command is quietly
> preferred over the other: **both brackets are reported, and LO1 and HI1 are reported at the
> shipped 45.000 mm command with the disagreement stated on the same line.**

### 7.4 CTL — reported, no verdict

Report: `n`, `w_cmd`, `w_reached`, `stalled`, `reached_goal`, `holding_F`, `holding_S`, and
whether any stop warning appeared (it must not). §5.3 states what this may and may not be read
as.

### 7.5 The three refusals that carry the campaign's honesty, and the predictions

> **Rule G — what these two numbers are properties of, and it is the rule this campaign most
> needs.** `flip_F_lo` and `flip_F_hi` are properties of **the shipped predicate as delivered**
> — the L0 declaration, the generator, the plan, the launch parameters and
> `gripper_is_holding` — and of **nothing else**. In particular:
> - **They are not properties of the cell.** A synthetic stop puts the drive joint wherever the
>   description says; a part, a jam or a fouled finger does not. **This rig can reach the wide
>   edge precisely because it grasps nothing.**
> - **`flip_F_hi` is therefore not evidence that `stall_band_wide_m` is well sized, that any
>   stall on a part reaches the wide edge, or that the wide edge has been exercised in the sense
>   ADR-0052 §A.9.5 means.** The 2026-09-02 campaign's **rule W fired** on exactly that question
>   — no trial with a part came within its minimum interesting size of that edge, because the
>   jaws square a yawed part up before the pads meet it — and **that rule stands unchanged after
>   this campaign, whatever `flip_F_hi` reads.**
> - **They are not evidence about the physical gripper** (§1), and **not evidence about where a
>   real jam stops** (ADR-0052 §A.9.2).
>
> **`ANALYSIS.md` must state rule G beside every wide-edge figure it publishes**, and may not
> use the word "validated" about either band value.

> **Rule W — inherited verbatim from the 2026-09-02 campaign's §7.3, and expected not to fire.**
> If the campaign produces no trial within 0.100 mm of the wide edge, it has not tested that
> edge. **This rig places stops within 0.05 mm of it deliberately, so W is expected to stay
> silent — and its silence means only what it says**, which is that a stop was placed there.
> **It does not retire the firing of rule W in the campaign that measured a part**, and rule G
> is what keeps the two apart.

> **Rule D — the arithmetic and the measurement are allowed to disagree, and the disagreement is
> the finding.** §2.2 predicts every bracket in this campaign before any trial. **If a measured
> bracket does not contain its predicted edge:**
> - it is reported as a **DISAGREEMENT**, with both numbers, their difference, and the whole
>   fine grid that produced it;
> - **nothing is re-run to resolve it**, no grid is extended in the direction that would make it
>   go away, and no constant anywhere in the tree is edited (§0);
> - **the campaign does not attribute it.** Whether the cause is the delivery chain, the
>   predicate, the linkage model, the fixture or the harness is not decided here, and the
>   write-up lists the candidates without choosing;
> - it is stated in `ANALYSIS.md`'s verdict line rather than in a deviation, because it is a
>   result and not a procedural exception.
>
> **A disagreement at the narrow edge would also mean §A.6's derivation and the shipped band do
> not meet where the record says**, which is a finding for ADR-0052 and the owner and **not for
> this campaign to act on** (§0).

**Predictions, so that this campaign can be wrong:**

| # | Prediction | Refuted by |
|---|---|---|
| **P1** | LO1 is BRACKETED at **(47.60, 47.65] mm** and HI1 at **[52.35, 52.40) mm** — both containing §2.2's computed edges. | either bracket landing elsewhere, or either edge NOT BRACKETED |
| **P2** | Every repeat at every stop is an exact replicate: `w_reached` spread **0.000 mm** and `holding_F` unanimous. | any spread above the 0.005 mm rest tolerance, or any within-stop verdict disagreement — either of which is a finding about the rig |
| **P3** | `flip_S_lo` is BRACKETED at **(47.10, 47.15] mm**, containing §2.2's closed-form 47.121519 mm, and **`flip_F_lo` lies above it**. | either bracket landing elsewhere, or `flip_F_lo` below `flip_S_lo` |
| **P4** | `holding_S` is **true at every stop in arm HI**, because the superseded predicate has no upper edge at all. | any wide-arm trial with `holding_S` false |
| **P5** | INV1 is HELD at all four straddling stops. | any verdict differing between the two commands |
| **P6** | CTL reports `reached_goal = true`, `stalled = false`, `holding_F = false`, and no stop warning. | any other combination — which is a datum about the plugin and, per §5.3, not a result about open-work #25 |

---

## 8. Explicitly not measured, recorded here rather than discovered later

- **The physical gripper.** ADR-0052 records there is no `GripperActionController` on the
  hardware path at all. Settled by Phase 2.B bring-up and by nothing before it.
- **The other three bullets of §A.10 item 2.** The **false-negative distribution** at the
  shipped command and above the validator's ceiling, and **the wide edge exercised by a grasp**,
  were run by the 2026-09-02 campaign; the **rule-S-shaped refusal** that bullet asks for is
  that campaign's rule W. **This campaign runs the second bullet and only the second bullet**,
  and closing it closes one bullet of one item.
- **Whether `stall_band_narrow_m` or `stall_band_wide_m` is the right value.** Locating a flip
  says where the declared band puts the edge, not whether the band should be there. §0.
- **Where a real jam stops.** A synthetic stop at a declared position. ADR-0052 §A.9.2 stands
  unchanged. Rule G.
- **Whether any stall on a part ever reaches either edge.** Rule G, and the 2026-09-02
  campaign's rule W, which this campaign does not retire.
- **Whether the stall distribution moves with the commanded width** (ADR-0052 §A.9.1). The
  2026-09-01 campaign reported that INCONCLUSIVE by two of its own rules and stated it was about
  twenty-five times too small. **This campaign is smaller on that question, not larger**, and its
  two commands exist to test invariance (§7.3) rather than to sample a distribution.
- **Why the drive joint reads narrower than the part it holds** (ADR-0052 §A.9.3). F's narrow
  edge must cover exactly this quantity and nothing here isolates it; sampling the five follower
  joints alongside `drive_joint` through a hold is the instrument that would.
- **An opening stroke's behaviour**, which is the 2026-09-02 campaign's arm B and is not re-run
  here (§5.1).
- **Whether the monotonicity term should return.** An open owner decision. §0.
- **Open-work #25.** §5.3.
- **A facility declaring more than one part.** F's discrimination *is* the width of the window
  and the window widens with the declared spread (ADR-0052 §A.5). **The shipped interval is
  degenerate at 50.0–50.0 mm** and this campaign measures the degenerate case only.
- **Any part, any timestep, any collision geometry, any arm but `arm_1`, any effort but 60 N.**
  There is no part and no physics in this rig at all, so three of those are structurally absent
  rather than merely unvaried.
- **A rate of anything.** Every count is over the trials that ran.

---

## 9. The machine, named

Naming the machine is a decision clause of
[ADR-0049](../../adr/0049-measure-the-real-time-floor-as-capacity.md) and the practice of every
campaign in this directory since. It matters **less** here than in a timing campaign and is
recorded in full anyway, because §9's own argument below is what establishes that.

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM |
| Free disk | **399 GiB** available on `/`, read on 2026-09-03 |
| Docker | **29.7.2** (build a7dcaa6); Docker Compose **v5.5.0** |
| Container image | **`cite-digital-twin:dev`**, image ID `3a41d4e431b0`, Ubuntu **24.04.4 LTS**, ROS 2 **Jazzy**, Gazebo Sim **8.15.0** (`gz-sim8-cli 8.15.0-1~noble`, `gz-harmonic 1.0.0-1~noble`) — all read from inside the image on 2026-09-03 |
| Isolation | compose project **`cite-digital-twin-3319196271`** and **`ROS_DOMAIN_ID` 43**, both derived from this checkout by sourcing `scripts/_lib.sh` on 2026-09-03, not typed in |
| Allocation | the container is **not** CPU-limited: `/sys/fs/cgroup/cpu.max` inside a plain `docker run` of the image reads **`max 100000`**, and `nproc` reads **16**, both read on 2026-09-03. No condition here applies a limit |

> **The Gazebo version disagrees with the 2026-09-02 scenario-ceilings campaign, which named the
> same image ID, and this file states what it measured rather than what that one says.** That
> campaign's §9 records Gazebo Sim **8.11.0** against image ID `3a41d4e431b0`; the reading above
> is **8.15.0**, taken on 2026-09-03 from an image whose full digest —
> `sha256:3a41d4e431b0a200c0b7a00d89bbcb44669f03d3aa754f56b89496a240fede7d` — is byte-identical
> to the one recorded in that campaign's `raw/provenance.txt`. **Which reading is wrong is not
> established here and was not chased**; that directory is frozen and is not edited. **No figure
> in this campaign depends on the Gazebo version**, because this rig runs no simulator at all.
> It is recorded because a version number that disagrees with itself across two campaigns on one
> image is exactly the kind of claim this repository has been damaged by before.

**Host load before the first trial, measured rather than claimed.** Read on 2026-09-03 on a host
up 1 day 2 h 43 m:

```
0.03 0.24 0.50        (/proc/loadavg, 16 cores)
```

**This host was quiet at the time of writing, and that is a statement about that moment and not
about the campaign.** It must not be assumed to hold: the 2026-09-02 scenario-ceilings campaign
measured **11 of its 28 post-run one-minute loads above 4.0 on this same host** (its deviation 5
and its §8; the figures are cited and not copied). I9 records the load at both ends of every
block, and V7 is what spends it.

**What host load could and could not reach here, argued rather than asserted.** Every decision
quantity in this campaign is a **width**: a drive-joint position clamped by the fixture to a
value the description declares, mapped through a static linkage. **There is no physics, no
simulator and no clock coupling in this rig at all.** Host load moves how long a trial takes and
whether a launch reaches its startup ceiling; it does not move where a clamped joint rests.
**The one route by which it could touch a verdict is a trial that never completes**, which
appears as a failed trial and not as a moved number, and V8 is what governs that.

> **A container load reading comes from the container, and on this host that is the host's.**
> `/proc/loadavg` is not namespaced on native Linux and there is no `lxcfs` in the way. The
> 2026-09-02 scenario-ceilings campaign **demonstrated** this on this host — two readings taken
> seconds apart from inside and outside a container of this image agreeing to the hundredth —
> and I9 nevertheless names where each reading was taken, because the 2026-08-31 capacity
> campaign applied a validity rule that read a Docker Desktop VM's load rather than the host's.

---

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — `v1_clean`, inherited from the 2026-09-02 scenario-ceilings campaign, including its
  five watched paths and its both-ends reading.** A block contributes only if **at BOTH ends of
  the block** — I8 is taken twice — `git diff c38a42c..HEAD -- model/ workspace/src/ tools/
  tests/ scripts/` is **empty** and `git status --porcelain` shows **no dirt** in those five
  paths. **`v1_clean` is the CONJUNCTION of the two readings**, and a block whose two readings
  disagree is **discarded and reported** as an edit that landed mid-block.
  **The base still holds:** that diff is empty against `HEAD` and the worktree is clean, both
  read on 2026-09-03. **`docs/measurements/` may advance while the campaign runs and nothing
  else may** — this campaign's own `criteria.md`, harness and raw all land on this branch, so
  `HEAD` necessarily advances and pinning it would discard every block including the first.
  **The flag is computed where the block is taken and travels ON the record; the analyser drops
  any row without it.** Not a note in a README: a field.
- **V2 — the description that actually ran.** Every block reads the description the rig
  publishes and counts collision-mesh references under
  `cite_description/meshes/collision/xarm5/convex_hull`: **13** for the shipped `convex_hull`
  selection. A block that disagrees is **discarded and reported** — the rig would be built from
  a description this repository does not ship. The running cell's `MODEL_HASH` is recorded with
  it.
- **V3 — nothing was between the pads, and nothing could be.** This rig has no simulator, so the
  contact witness the grasp campaigns used is **structurally absent rather than silent**. That
  is recorded **per trial** as a stated fact about the rig rather than left to be inferred from
  a missing field, which is the 2026-09-02 campaign's practice for its own arm B.
- **V4 — the two width instruments agree.** Per trial, `|w_reached(I1) − w_reached(I3)| <=
  0.005 mm`, and both round to the I2 log line's `%.1f`. A trial exceeding it is **excluded from
  every bracket and reported**: at that point the campaign does not know which value the
  predicate consumed. §7.0 records why the inherited 0.100 mm is too coarse for this campaign.
- **V5 — the stop engaged, and the fixture did not manufacture it.** A trial in arm LO or HI
  contributes only if I5 shows the plugin's own stop warning, **and** I7 shows the drive joint
  resting within **0.005 mm of width** of the declared stop, **and** I6 shows no
  start-outside-the-stops refusal. If **every** trial at a stop is excluded, that stop has no
  verdict and rules U and N apply to the edge it was serving.
- **V6 — the block effect.** Every repeat cycle is a block and the block index travels on every
  record. If, for any metric, the difference between two blocks at the **same** stop is larger
  than the difference between adjacent stops, that metric's finding is **downgraded to
  INCONCLUSIVE** whatever any test statistic says. Inherited deliberately: this is the rule that
  fired on the 2026-09-01 campaign's D2.
- **V7 — the load is recorded, and a loud host is reported rather than excluded.** I9 is taken
  at both ends of every block. **No block is discarded for load**, because a load threshold
  chosen after seeing the data is a threshold chosen by the data. **If any reading exceeds 4.0
  on 16 cores, every trial in that block is flagged and every bracket it contributes to is
  reported with and without those trials**, and if a bracket differs, that edge is UNRESOLVED
  under rule R. This is the shape the 2026-08-31 campaign's literal application of a load rule
  taught, with the post-run half the 2026-09-02 ceilings campaign found missing.
- **V8 — n is what it was.** Every count is reported over the trials that actually ran, with a
  Wilson 95 % interval where it is a proportion. **No stop is topped up** to match another, and
  a block that aborts early is reported with the n it reached.
- **V9 — no threshold moves.** Nothing in this file changes once the first campaign trial has
  run. **A threshold discovered to be wrong is applied literally and recorded as wrong**, and
  the disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data already
  collected. The 2026-08-31 capacity campaign applied a validity rule it had found to be reading
  the wrong quantity, literally, and reported it; that is the precedent.
- **V10 — one writer at a time.** **A concurrent agent editing a watched path mid-block flips
  `v1_clean` and silently discards the block** — a fact only because V1 takes I8 at both ends
  and conjoins the readings. So the campaign runs with **one writer in this checkout**, and the
  campaign operator states in `ANALYSIS.md` whether that held. A campaign that loses blocks this
  way **reports the loss under V1 rather than re-running until it stops happening.**
- **V11 — no rebuild mid-campaign.** `./scripts/build` runs once before the first trial. If a
  rebuild becomes necessary it is a numbered deviation, and every block before it is reported
  separately from every block after it.
- **V12 — the superseded predicate is a build, not a rewrite.** `holding_S` and `flip_S_lo`
  contribute only if `raw/provenance.txt` records the `4ef2d7c` worktree commit and the sha256
  of the binary that produced them. **Without it, `holding_F` is reported alone**, block LO-S
  does not run, FLOOR1 is reported against the cited floor only, and the write-up says so.
  V12 failing **does not** make LO1 or HI1 unmeasurable: the gate's bullet is about F's flip.
- **V13 — the fixture is what it claims to be.** Every launch asserts that the description it
  substitutes into declared **`gz_ros2_control/GazeboSimSystem`** *before* substitution, exactly
  as `test_abort_classification_launch.py` and the 2026-09-02 campaign's arm B do. A launch that
  finds anything else is **discarded**: the L0 backend has changed and the rig is no longer
  substituting what it thinks it is.

**One shakedown run per harness is permitted and is not data.** Before the first campaign trial,
each harness may be run **once** to prove it starts, connects and writes a record. Its output is
published under **`raw/shakedown/`**, is **excluded from every figure in §7**, and **may not be
used to set or adjust any threshold in this file** — every threshold above is derived from the
geometry, the gate's own 0.05 mm, or the declared tolerances, and none of them needs a shakedown
to exist. If the shakedown reveals a defect, **the harness is fixed and this file is not
touched.**

---

## 11. Honesty bounds fixed in advance

- **This campaign chooses nothing.** It does not set the band, does not amend ADR-0052 or move
  its status, does not decide whether the monotonicity term returns, and proposes no value for
  anything. §0.
- **It closes one bullet of one item of one gate, at most.** §A.10 item 2's second bullet.
  Everything else in §A.10 is either already met, already another campaign's, or not a
  measurement. §8.
- **A null is not a pass.** Rules N, U, R, W, G, D, C and T exist for exactly that, and all
  eight were written before any trial ran. **Rule G is the one that matters most here**: this
  rig can place a stop at the wide edge precisely because it grasps nothing, and a bracket
  produced that way is a property of the predicate and **not** of any cell, part or jam. It does
  not retire the 2026-09-02 campaign's rule W and may never be written as if it had.
- **The measurement is allowed to contradict the arithmetic.** Rule D says what happens then,
  and it says it before the answer is known: the disagreement is the result, nothing is re-run
  and nothing is edited.
- **This is a verification campaign, not a discovery campaign.** §2.2 predicts every bracket.
  What it verifies is delivery — that the band L0 declares reaches the running predicate
  unchanged — and that is worth measuring precisely because it has never been measured. §1.
- **Nothing here is a P2 result**, nothing here is a grasp result, and nothing here says where a
  real jam stops. §1, §8.
- **One machine, one image, one commit, one checkout, one arm, one facility with one declared
  part width, no physics, and it is not a rate.**
- **Both cited campaigns stay frozen.** No file under
  [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/ANALYSIS.md) or
  [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/ANALYSIS.md) is edited, re-run
  or re-analysed here. **No figure from either appears as this campaign's data**, and rule H
  forbids differencing any measured figure of theirs against anything here.
- **Figures stay in this directory.** Nothing produced here is copied into ADR-0052, `CLAUDE.md`,
  [`docs/open-work.md`](../../open-work.md), the L0 comments or any layer document (P1). **Cite
  the directory.**
