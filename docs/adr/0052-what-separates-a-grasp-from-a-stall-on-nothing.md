# ADR-0052: Decide what separates a real grasp from a stall on nothing

- **Status:** Accepted — **the project owner chose option F on 2026-09-01**, on the campaign
  this record's gate asked for. That choice, and the mechanism F has to be given before anyone
  can build it, are in the section "Amendment — 2026-09-01: option F is chosen, and this is
  what F is", immediately below. Read it before the body: everything below it that says the
  choice has not been taken was true when written and is not now.
  **Nothing in the tree changes with this record or with that amendment.**
  `cite_skills::gripper_is_holding` is untouched,
  `tools/cite_tools/validate/physical.py` is untouched, no threshold, ceiling or
  tolerance moves, and no test is added or removed. **The defect is still live.** What is
  `Accepted` is the decision and the specification, not an implementation, and the gate the
  implementing change has to pass is §A.10 of the amendment — which replaces §"When this
  record is promoted" below, whose clause 1 the owner's choice has now satisfied.
  **One supporting claim in the body is also corrected on the same date** — option F's own
  paragraph names a lookup that cannot be written. See the section "Correction — 2026-09-01:
  option F names a lookup that cannot be written", which follows the amendment. **The decision
  survives it**; it is what forces §A.5's answer to be an interval.
  **[Replaced 2026-09-01, kept for the record:]** *"Proposed — **and this record deliberately
  chooses nothing.** It states a defect, the arithmetic that produces it, the measured
  distribution the shipped cell actually sits at, and six options with what each costs in both
  error directions. **The choice among them is the project owner's** and is owed a separate
  change; §"Decision" below says exactly what is decided here and what is not."*
  **This is the record [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md)
  says is owed** — its section *"A separate defect, found in the same investigation, owed its
  own record"* and its status block, which as of 2026-08-30 still read *"One thing named here
  as owed its own record still has none"*.
- **Date:** 2026-09-01
- **Deciders:** Docs-writer agent, drafting from the shipped source, the L0 declaration and the
  committed raw of the campaign named under *Evidence*. **The decision between options A-F is
  the project owner's and has not been taken.**
  **[Amended 2026-09-01 — see the amendment section below.]** It has been taken: the **project
  owner chose option F** on 2026-09-01, on the campaign added under *Evidence*. **The mechanism
  F is given in that amendment is the docs-writer agent's**, drafted from the shipped source and
  that campaign's committed raw — the same split [ADR-0051](0051-restate-the-hull-grasp-gate.md)
  records, where the owner decides the shape and the agent writes the clause. **It sets no
  threshold**; §A.6 states the interval measurement admits and deliberately picks nothing
  inside it.
- **Related:** [ADR-0022](0022-gripper-as-ros2-control-controller.md) (**a grasp is evidenced
  by a stall, and the stall is reported and not interpreted — a constraint on this record, not
  a subject of it**), [ADR-0029](0029-simulated-grasping-by-friction.md) (friction alone holds
  the part, so a reached width at a stall is a measurement of the part and not an artefact),
  [ADR-0030](0030-facility-model-describes-the-workpiece.md) (the work-piece is L0 data, which
  is what makes option F expressible at all),
  [ADR-0036](0036-execution-side-trajectory-tolerances.md) (**the precedent for the language:
  a detector, never a protective measure**),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md),
  [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md) (the record that names
  this defect and deliberately does not fold it in),
  [ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) (**closes this defect's
  L4 exit and does not touch the defect**),
  [ADR-0028](0028-convex-hull-collision-meshes.md) and
  [ADR-0051](0051-restate-the-hull-grasp-gate.md) (the shipped collision geometry moved on
  2026-09-01, and §2.4 below shows the measured margin moved with it),
  [L2](../architecture/L2-control-and-hal.md), [L3](../architecture/L3-capabilities.md),
  charter §4 (P1, P2, P5, P6, P7, P8), CLAUDE.md §2.
- **Evidence:**
  [`docs/measurements/2026-09-01-hull-grasp/`](../measurements/2026-09-01-hull-grasp/ANALYSIS.md)
  — 47 trials, thresholds registered before the first trial, machine named, **verdict
  INCONCLUSIVE on its own question**. **That campaign did not ask this record's question and
  published no figure about it.** What §2.4 reports is a quantity computed *here* from that
  campaign's committed raw — its per-trial `q_at_stall_rad` and its skill-server logs — and it
  is labelled as such throughout. The campaign's own figures are cited and not copied (P1).
  **Added 2026-09-01, and it is what the decision below rests on:**
  [`docs/measurements/2026-09-01-grasp-discrimination/`](../measurements/2026-09-01-grasp-discrimination/ANALYSIS.md)
  — the campaign the gate below asked for, **32 FN trials, 39 FP trials and a 262-point
  sweep**, thresholds registered before the first trial at a stated `criteria.md` hash, machine
  named, and **choosing none of A-F itself**. Verdicts: false negative **OBSERVED**, false
  positive **REPRODUCED**, the two arithmetics **IMMATERIAL**, the unvalidated caller door
  **DEMONSTRATED**, and D2 **INCONCLUSIVE** by two of its own rules.

## Amendment — 2026-09-01: option F is chosen, and this is what F is

**The project owner chose option F on 2026-09-01**, on the campaign this record's gate asked
for. This section records the decision, and then does the harder half: F is stated below as a
*direction*, and an implementing change cannot be written from a direction. Everything after
the decision is the mechanism, decided here so that it can be built and argued with.

**Nothing in the tree changes with this amendment either.** `cite_skills::gripper_is_holding`,
`tools/cite_tools/validate/physical.py`, the L0 model and every test are byte-identical after
it. What changes is the status of this record and the specification the implementing change
follows. **The defect is still live**, exactly as the Consequences section below says.

**Read the campaign, not this section, for its figures.**
[`docs/measurements/2026-09-01-grasp-discrimination/`](../measurements/2026-09-01-grasp-discrimination/ANALYSIS.md)
asks in its §10 and its `criteria.md` §11 that its figures stay in that directory and be cited
rather than copied (P1). **Four are quoted below because the decision rests on them, and a
decision that hides its own premises cannot be argued with**; everything else is cited.
Quantities computed *here* from its committed raw are labelled as such throughout, the way
§2.4 below is labelled against a different campaign.

### A.1 What was decided, and the reasoning that was shown

**Option F: judge the grasp against the part rather than against the commanded width.**
Options A, B, C and D are not taken. **E is not rejected** — §A.7 records that F cannot be
built correctly without it, so E is absorbed as a constraint rather than chosen as an
alternative.

The reasoning put to the owner, which this record carries as the decision's stated basis:

> The band's reference is the **command**, which is a policy value; the error is about where
> the **part** is. The validator's ceiling reasons from the work-piece's nominal 50.0 mm
> while the cell stalls at a median 49.804 mm, and that difference is the 0.164 mm by which
> `default-grasp-width-never-closes`'s ceiling sits **above** the band the cell actually
> produces — so the validator will pass a model whose grasps this predicate reports empty.

That is §2.3's third door — *"a stall that lands inside the band at a part the validator was
happy with"*, the one this record calls *"the one this cell is actually near"* — measured for
the first time. The campaign's §5.1 reports it as its most decision-relevant quantity and
chooses nothing on it.

**What the campaign settled, in its own verdicts.** False negative **OBSERVED** — a real
grasp, witnessed by the work-piece's own contact sensor, reported empty, with `Pick` returning
`EXECUTION_FAILED`. False positive **REPRODUCED** — a stall on nothing reported as a grasp,
with the flip bracketed to 0.05 mm around the value the arithmetic predicted before any trial.
The two arithmetics **IMMATERIAL**. The unvalidated caller door **DEMONSTRATED**. And D2 —
whether the stall distribution moves with the commanded width — **INCONCLUSIVE**, by two of
the campaign's own pre-registered rules, with the campaign stating that it is about twenty-five
times too small to answer it. §A.9 carries what that last verdict costs F.

### A.2 The decision this record now makes, in one line

The predicate stops asking *"did the jaws stop wider than we asked?"* and asks *"did the jaws
stop where a part this facility handles would stop them?"* — with both edges of that window
declared in L0, and with the runtime and the validator reading one statement of the part's
width rather than two.

### A.3 F.1 — the predicate

`cite_skills::gripper_is_holding` becomes:

```
holding  <=>  stalled
              and not reached_goal
              and w_reached  >  w_part_narrowest - stall_band_narrow
              and w_reached  <  w_part_widest    + stall_band_wide
```

`w_reached` is `gripper_width_for(report.reached_position, travel)`, unchanged.
`report.commanded_width_m` **leaves the predicate entirely** — it stays on `GripperReport` for
`describe_empty_grasp`'s report string, which must still print what was asked for, but nothing
decides on it.

The two flag conditions are unchanged and are not up for discussion: §3 below establishes that
`reached_goal` and `stalled` are mutually exclusive upstream and that the first condition
carries no threshold, which is why it cannot be miscalibrated. **ADR-0022 is not reversed** —
the controller still reports and does not interpret, and the judgement stays in L3.

### A.4 F.2 — what the runtime reads instead, and that it is deliverable

**It is deliverable, and the delivery channel exists — but not the one option F below names.**

- **The width is in L0.** `model/assets/types/workpieces/workpiece.yaml` declares a 50 mm
  cube; `Body.horizontal_extents_m` (`cite_tools/model/schema.py:151-174`) derives the
  narrowest and widest horizontal extent from `collision.size_m` and is explicitly documented
  as existing because *"the narrowest is the width a parallel gripper closes across"*.
  `Facility.workpiece_models` names which types the facility handles, and
  `ResolvedCell.workpiece_types` resolves them. Nothing new has to be declared to know how wide
  a part is.
- **`Pick.Goal.workpiece_id` cannot be used to look one up, and option F below is wrong to
  imply it can.** The id on the goal is an *instance* id minted by L4's registry —
  `snprintf(buffer, sizeof(buffer), "wp_%06u", ++minted_)`,
  `cite_orchestration/workpiece_registry.hpp:231-236` — and `WorkpieceRecord` records an id, an
  owner, a location and a phase, and **no type**. There is no map from an instance id to an L0
  work-piece type anywhere in this repository. A per-part lookup would need the type on the goal
  (P3), the registry recording it, and `Detect` reporting it; none of those exist, and **F is
  decided without them** — see §A.5.
- **The gripper channel exists and is the wrong one.** `plan.py`'s `GRIPPER_KEYS`
  (`plan.py:284-297`) carries thirteen values from L0 to L3 verbatim, and `skill_server.cpp`
  declares each one; `gripper_default_grasp_width_m` and `gripper_goal_tolerance_rad` travel
  that way today. But every key on it is sourced by `_grasp` or `_linkage`
  (`generate/bringup.py:199-230`), both of which read the **end-effector type**. A work-piece
  width is not a property of an end effector, and putting it on a tuple named for the gripper is
  how a name stops meaning anything — the reason `ARM_KEYS` is a separate tuple.

**So: the plan states it once, at facility level, and the launch mechanism delivers it to every
skill server.** `cell_a_plan.yaml`'s `plan:` block already carries facility-level facts —
`zone`, `world`, `scene`, `static_frames`, `topology`, `sides` — and a `workpieces:` entry
beside them carrying `narrowest_width_m` and `widest_width_m` is one statement, in the place
this plan keeps one-per-zone statements, checked by `./scripts/validate-model` like every other
generated value. `cite_bringup` passes the pair to each skill server as parameters, the way it
passes the gripper keys. **This is a plan-shape decision and it is made here so that the
implementing change does not make it by accident.**

### A.5 F.3 — a facility that handles more than one part

**The predicate is given the interval of declared part widths, and never which part it is
holding.** `w_part_narrowest` and `w_part_widest` are the minimum and maximum of
`horizontal_extents_m[0]` over `Facility.workpiece_models`. On today's model, which declares
one part, the interval is degenerate and both values are the same number.

**Why the interval and not the part.** A per-part rule needs the work-piece *type* at L3, and
§A.4 establishes that nothing carries it; building that chain is a larger change than this
defect justifies, and it would put "which part am I picking" inside a skill that P9 requires to
be replaceable without touching orchestration. The interval keeps L3 knowing only *"the range
of part widths this facility handles"*, which is a fact about the facility and not about the
goal. **Adding a second part then changes data and not code**, which is the property P5 and P9
are asking for, and it is the property the alternative does not have.

**What it costs, stated rather than discovered later.** F's discrimination is the width of its
admitting window, and the window widens with the declared spread. A facility declaring a 20 mm
and an 80 mm part gets a 60 mm window plus both bands, at which point F is no better than option
C — every stall in that range is a grasp. **That is not left to be noticed**: §A.7's second
validator rule refuses a model whose window reaches below the width the command-referenced rule
would already have rejected, which is exactly the point where F stops buying anything. **This
project has paid twice for a constant that silently stopped applying** — the derived-hull range
constant and the vendor-mesh selection, both in ADR-0028 and ADR-0051 — and the answer both
times was a rule that fires rather than a sentence that warns.

**What is not decided here, and is not needed for this defect:** whether the day a second part
arrives, the right answer is to carry the type after all. The interval is correct for one part
and degrades honestly for several; if the spread ever makes the rule in §A.7 fire, **that is the
signal to reopen this**, and the rule's own message must say so.

### A.6 F.4 — the band, and the floor it may not cross

**Two values, declared in L0 on the end effector's `grasp` block, both required with no
default:** `stall_band_narrow_m` and `stall_band_wide_m`.

**Why declared and not derived from `goal_tolerance`.** Reusing the existing
`2 * gripper_width_tolerance_m(q_reached)` as the window is the tempting form — it needs no new
declaration, it is already delivered, and on the shipped values it brackets the measured
distribution. **It is rejected, on a property computed here from the shipped constants:** the
window would then *widen* as the declared tolerance loosens, which is the opposite of what the
present rule does. At a `goal_tolerance` of 0.02 rad, twice the shipped value, that window on a
50 mm part is `[45.79, 54.21]` mm and it **admits the measured free-air settle at 45.85 mm as a
grasp** — the exact case `gripper.hpp`'s `DO-NOT-SIMPLIFY` block exists to reject, and the
inversion of the property `GripperHolding.WidensItsMarginWhenTheControllerToleranceIsLooser`
asserts today. A threshold whose safety direction flips with an unrelated setting is not a
derivation, it is a coincidence.

**Why the end effector and not the work-piece.** The quantity is *"how far from a part's
declared width a genuine stall on that part lands"*, and the only mechanism anyone has named
for it — §2.4's mimic servo, recorded there as *"a candidate mechanism and not a finding"* — is
a property of the drive and its linkage rather than of the part. It sits beside
`goal_tolerance`'s consumers, where the rest of this arithmetic already lives, and it reaches L3
on the channel that already exists. **The cause of the shortfall is unexplained** (§A.9), so
this placement is a judgement and not a derivation, and it is recorded as one.

**The narrow edge is bounded on both sides by measurement, and the bound is narrower than the
band it constrains.** Computed here from the campaign's committed raw — its per-trial
`q_at_stall_rad` and `reached_position_rad` mapped through the shipped `gripper_width_for`,
reproducing its published per-command table exactly:

| bound on `stall_band_narrow_m` | from | value |
|---|---|---|
| **must exceed** the largest observed shortfall from nominal, or a real grasp is reported empty | minimum reached width over the 31 valid FN trials, 48.109 mm against a 50.0 mm part | **1.891 mm** |
| **must not exceed** the distance from nominal to the floor below which a stall on nothing starts being reported as a grasp | the FP flip, bracketed to 0.05 mm and containing 47.1215 mm | **2.879 mm** |

**The admissible interval is 0.987 mm wide, and this record does not pick a value inside it.**
The campaign's own rule R reports *every* width metric UNRESOLVED at its 0.100 mm minimum
interesting size, at all four commanded widths; a campaign that cannot resolve 0.1 mm has not
placed a value inside a 0.99 mm interval. **The implementing change lands a provisional value
with its provenance written into the L0 comment** — the shape ADR-0036 used for the UFACTORY
tolerances it recorded as copied — **and §A.10's gate is what sets it.**

**THE FLOOR IS A MEASUREMENT ON ONE MACHINE, AT ONE TIMESTEP, WITH ONE PART, ON ONE ARM.**
47.1215 mm is where the shipped predicate's verdict flips with nothing between the pads, on the
campaign's synthetic stopped joint, at the shipped 45.0 mm command. It is *not* a statement
about where a physical jam stops (§A.9), and it is not a rate. What it is good for is one thing
and the implementing change must use it for exactly that: **F's admitting set at the shipped
default command must be a subset of today's**, so that F cannot introduce a false positive
today's predicate would not also have produced. Verified here on the committed FP raw for every
candidate band with a lower edge at or above 47.1215 mm — the subset property holds in all of
them.

**The wide edge has no lower bound from any measurement.** No FN trial stalled above nominal;
the widest came within 0.023 mm of it. So the data says the edge is not needed to admit any
observed grasp, and says nothing about how large it must be to admit an unobserved one. **Any
positive value is unevidenced**, and §A.10 requires the gate's campaign to report the distance
from the largest observed stall to it, because **nothing has ever exercised that edge**.

### A.7 F.5 and F.6 — what the validator becomes, and E absorbed

**The 0.164 mm gap is not narrowed by F. It is dissolved, and that is the point.** It exists
because two layers answer one physical question from two different reference points: the
validator from the part's nominal width, the runtime from the command. Under F **both reason
from the same declared nominal width, through one accessor**, and the gap between nominal and
achieved becomes an explicit declared allowance — the band — instead of an unmodelled difference
between two layers.

**`default-grasp-width-never-closes` keeps its number and changes its job.** Under F the runtime
no longer reads the command, so the rule is no longer a second derivation of the runtime's band.
Its remaining job is the one its own docstring states first: *"a grasp is evidenced by failing
to reach where it was sent"*, so the declared default must be narrow enough that the close does
not terminate on the controller's goal-tolerance branch. That needs one `goal_tolerance` of
width, not two — **and the rule keeps two.** Halving it would loosen a ceiling by about 1.07 mm
on a question nothing has measured, and the campaign's own 47.0 mm column, whose worst trial
cleared the present band by 0.114 mm, is the evidence that this gripper works close to that
edge. **The ceiling does not move; its reason does.**

**Three rules the validator gains or changes, each firing rather than warning.**

1. **`workpiece-width-unstated-for-a-grasping-facility` — new, ERROR.** A facility whose end
   effector declares a `grasp` block and whose declared work-pieces state no width leaves the
   predicate with no reference at all. `_narrowest_workpiece_width_m`'s docstring already
   records that silence — *"this facility handles no parts"* and *"a part nobody has stated the
   width of"* collapsing into one `None` — and `_workpieces_without_a_stated_width` already
   separates them. Under F that silence stops being a documented gap and becomes an unanswerable
   predicate, so it must fire.
2. **`stall-band-admits-a-stall-on-nothing` — new, ERROR.** Refuse a model where
   `w_part_narrowest - stall_band_narrow_m` falls below
   `default_grasp_width_m + _grasp_discrimination_margin_m(default)`. **That comparator is
   derived from declared values alone** — it is the band edge the present rule already computes
   — and on the shipped model it lands at 47.138 mm, within 0.017 mm of the 47.1215 mm the
   campaign bracketed. This is the rule that makes §A.5's multi-part degradation visible instead
   of silent, and its message must name §A.5 as the thing to reopen.
3. **`default-grasp-width-never-closes` — kept, re-reasoned.** As above.

**Option E is absorbed, not deferred.** F changes *what* is computed on both sides, so a change
that moves one derivation and leaves the other is worse under F than it is today: it would
produce a model that validates against a part and a cell that judges against something else.
Concretely, **the narrowest and widest declared work-piece widths must have exactly one
accessor**, read by the generator and by the validator. They do not today —
`ResolvedCell.workpiece_types` and `physical._narrowest_workpiece_width_m` walk the same list by
two routes — and F makes that a P1 defect with consequences rather than a tidiness point. The
factor `2.0` remains written in two languages (`gripper.cpp:116`, `physical.py:574`); under F
they no longer compute the same thing, so **the implementing change must either give them one
home or state in both why they are now different quantities.**

### A.8 F.7 — the caller door, and F.8 — P2 as a constraint

**F closes the door the campaign demonstrated.** A caller-supplied `grasp_width_m` cannot move
the band, because there is no band keyed to the command. Computed here on the committed FN raw:
under F, **all 31 valid trials are admitted**, including the **7 of 7** at the unvalidated
48.0 mm command that the shipped predicate reports empty; today's rule admits 24 of the 31. On
the committed FP raw, under an **illustrative** band whose lower edge sits at 47.894 mm — a
placeholder inside §A.6's interval, not the value F ships with — **9 of 33** valid trials
report a grasp on empty jaws against today's **18 of 33**, and the 9 are a subset of the 18.
**Both directions improve on the same data, with no new constant chosen** — only the reference
point moved. These are quantities computed here from committed raw, not campaign figures, and
they are a re-reading of trials taken for a different question.

**It does not close the door entirely, and the remaining half is a different failure.** A
caller-supplied width that is *wider* still ends the close on the controller's goal-tolerance
branch, `reached_goal` is true, and F reports empty by its first condition — a false negative by
another route, and nothing validates a goal-supplied width against anything.
**`resolve_grasp_width` gains a refusal**: a resolved width, from either source, that does not
clear `w_part_narrowest` by at least the same `_grasp_discrimination_margin_m` the validator
uses is refused with a typed failure rather than executed. One policy, two layers, one number —
which is §A.7's constraint applied at the point of use.
**Its cost, stated because it is real:** on the shipped model that refuses a goal-supplied
48.0 mm, which the campaign shows this cell handles — all 7 of those trials stalled and none
reached goal. The refusal is conservative in the direction that fails safe, and **the
measurement that would justify relaxing it to one tolerance is the campaign's own 47.0 and
48.0 mm columns re-run at an n large enough to resolve 0.1 mm.**

**P2 is a constraint on the implementation, not a caveat at the end.**

- **The predicate reads fewer fields, not more.** `position`, `stalled` and `reached_goal` are
  all `control_msgs/GripperCommand.Result` carries on both paths, and F *removes* the commanded
  width from the decision. The P2 surface shrinks.
- **The band's values are the hazard.** They are being set from a distribution measured under
  `gz_ros2_control`, and its largest known component — the drive joint reading narrower than the
  part it holds — has a candidate cause that is **simulation-side** (§2.4's mimic servo).
  **The campaign establishes nothing about the physical gripper**, and cannot: there is no
  `GripperActionController` on that path at all, because the vendor macro emits the gripper's
  `<ros2_control>` block only for the simulated plugin and the real gripper is driven through
  the SDK's service layer.
- **Therefore the band is declared once and serves both sides.** L0 is one model for both
  (ADR-0041). If Phase 2.B shows the two sides need different values, **that is a P2 finding and
  an `ESCALATE`** — never a per-backend field, never a branch in `gripper_is_holding`.
- **Therefore the implementing change may not fit the band to the observed distribution.** It
  may place a value inside the measured interval in §A.6, and must record in the L0 comment that
  the interval is simulation-measured and its mechanism unexplained. A number tuned until the
  Gazebo trials pass is a P2 break wearing a measurement.

### A.9 What F does not fix

1. **D2 is unmeasured and F's narrow edge may depend on it.** The band must clear the narrowest
   stall over *every* command the cell uses. The campaign's 48.0 mm column has the lowest median
   reached width of the four; its V5 block-effect rule fired, so that column cannot be separated
   from a block effect; and the campaign states it is about twenty-five times too small to answer
   the question. **If the stall distribution does move with the command, the interval in §A.6 is
   narrower than it looks.**
2. **Where a real jam stops still has no campaign, and F makes that gap more load-bearing, not
   less.** §3 below establishes that the margin's real job is the jam case and that the factor of
   two was never sized against it. F's window is what would catch a jam — a bounded window
   catches what an unbounded half-line cannot — so **F's central claim rests on a quantity nobody
   has measured.** The campaign's FP arm produces a *synthetic stop at a declared position*, not
   a fouled finger, and says so.
3. **The drive joint reads narrower than the part it holds, and that is unexplained.** §2.4
   reports a median 1.14 mm on vendor geometry; the shipped hull geometry sits closer to nominal
   and the campaign did not re-derive that figure. **F makes this unexplained quantity the exact
   thing its narrow edge must cover.** The measurement that would settle it is §"What is not
   measured, and what would settle each" below, unchanged: sample the five follower joints
   alongside `drive_joint` through a hold.
4. **`Grasp` loses generality.** `expect_object` comes to mean *"expect a declared work-piece"*.
   A caller closing on something L0 does not declare cannot use it, and this record does not
   build the alternative.
5. **The wide edge is a new false-negative mode nothing has exercised.** A stall wider than
   `w_part_widest + stall_band_wide` reports empty. No observed grasp came within 2.1 mm of it.
6. **F is a detector, not a protective measure** — ADR-0036's language, applying unchanged. It
   reports after the fact and stops nothing.
7. **F does not touch the L4 exit.** `EXECUTION_FAILED` still shares `RETRY_SAME`, and
   ADR-0046's custody refusal still carries what happens next.
8. **This defect is not fixed by this record.** Nothing is built. A real grasp between the
   commanded width and about 2.1 mm above it is still reported empty on `main`.

### A.10 The gate the implementing change has to pass

**Written to ask for evidence that can exist**, in the shape ADR-0043, ADR-0049 and ADR-0051
arrived at the hard way. The re-run is cheap on purpose: the campaign's FN harness produces the
false-negative figure on every close, and its `JointStopSystem` rig (ADR-0040) produces the
false-positive side on demand.

1. **The re-analysis, which costs nothing and comes first.** The campaign's committed raw already
   carries F's exact inputs — `q_at_stall_rad` for each FN trial and `reached_position_rad` for
   each FP trial. The implementing change publishes F's verdict on every one of those records
   under the band it lands, and must show: every valid FN trial admitted, and **F's admitting set
   at the shipped default command a subset of today's**. A band that fails either is not landed.
2. **A campaign under [`docs/measurements/`](../measurements/README.md), thresholds registered
   before the first trial, machine named, on the implemented predicate**, reporting:
   - **the false-negative side** — over N grasps at the shipped command *and* at least one
     command above the validator's ceiling, the distribution of the distance from `w_reached` to
     the window's **narrow** edge, and its minimum;
   - **the false-positive side** — the stop sweep re-run, which stops F admits, and the flip
     bracketed to at least 0.05 mm against the floor §A.6 derives;
   - **the wide edge, which nothing has ever exercised** — the distance from the largest observed
     stall to it, reported as its own quantity;
   - **a pre-registered refusal rule in ADR-0051's rule-S shape**: if the campaign produces no
     trial within its registered minimum interesting size of an edge, it **has not tested that
     edge**, and its silence there may not be read as a pass.
3. **Tests, at the level each claim lives at.** A unit row per branch of the truth table,
   including both edges and the no-declared-width refusal; and a launch test driving a real
   `ros2_control_node` over `cite_test_hardware/JointStopSystem` at one stop inside the window
   and one outside — the same rig and the same pattern as
   `cite_bringup/test/test_abort_classification_launch.py`.
4. **One statement, checked.** A test that moves the declared work-piece width in L0 and requires
   the generated plan *and* the validator's ceiling to move with it. §A.7's accessor constraint
   is not met by two functions that happen to agree.
5. **What will not promote it: a green CI run**, or a passing `continuous_line`. This defect is
   silent when it does not fire, and it has fired in no run anyone has looked at.

### A.11 How this amendment's own claims were verified

Checked on **2026-09-01** against this worktree at `734a26d`. Figures marked *computed here* are
new quantities derived from the campaign's committed raw; the campaign published none of them.

| Claim | How | Result |
|---|---|---|
| The campaign's five verdicts, and the 0.164 mm gap | Read `criteria.md` and `ANALYSIS.md` in full; recomputed the FN per-command table, the pooled band edge in commanded terms and the FP flip from `raw/FN_B*_trials.json` and `raw/FP_trials.json` in a standalone script | **Reproduces.** 31 valid FN trials after V4's single exclusion; per-command reached medians, ratio minima and in-band counts identical; pooled reached median 49.804 mm, band edge 47.698 mm; FP flip between 47.10 (false) and 47.15 (true) |
| `Pick.Goal.workpiece_id` is an instance id with no type behind it | Read `workpiece_registry.hpp:59-69` and `:231-236`, `line_nodes.hpp:585-620`, `skill_nodes.hpp:653`, `:944` | Exact. `wp_%06u`, minted by L4; `WorkpieceRecord` holds id, owner, location, phase and no type. **No map from an instance id to an L0 type exists in this repository** |
| The part's width is in L0 and derivable without new schema | Read `model/assets/types/workpieces/workpiece.yaml`, `schema.py:151-174`, `:1300-1317`, `resolve.py:162-182` | Exact. `horizontal_extents_m` derives it from `collision.size_m` and its docstring names this gripper's rule as a consumer |
| Thirteen gripper values reach L3 through the plan, all sourced from the end-effector type | Read `plan.py:284-297`, `generate/bringup.py:199-230`, `:404-421`, `templates/bringup/plan.yaml.j2:181-187`, `skill_server.cpp:305`, `:402` | Exact. Every `GRIPPER_KEYS` entry comes from `_grasp` or `_linkage`, both of which read the end effector. **The channel exists; a work-piece width does not belong on it** |
| The plan already carries facility-level facts in one block | Read `workspace/src/cite_generated/bringup/cell_a_plan.yaml:15-20` | `zone`, `world`, `scene`, `static_frames`, `topology`, `sides` — one statement each, per zone |
| Reusing `2 * tolerance` as the window inverts with the declared tolerance | Evaluated the window on a 50 mm part at `goal_tolerance` 0.01 and 0.02 rad in the same script, against `kFreeAirSettle = 0.444793` from `test_gripper.cpp:64` | At 0.01 the window is `[47.895, 52.105]` mm and the 45.852 mm free-air settle is **rejected**; at 0.02 it is `[45.790, 54.210]` mm and the same settle is **admitted**. The reuse is rejected on this |
| The narrow edge's admissible interval is (1.891, 2.879] mm | Committed FN raw: minimum reached width 48.109 mm against 50.0 nominal. Committed FP data: flip bracketed to 0.05 mm containing 47.1215 mm | **Computed here.** 1.891 mm and 2.879 mm; interval 0.987 mm wide. The campaign's rule R reports every width metric UNRESOLVED at 0.100 mm |
| No observed grasp stalled above nominal | Maximum reached width over the 31 valid FN trials | **Computed here.** 49.977 mm, 0.023 mm below nominal. The wide edge is unexercised |
| F admits all 31 valid FN trials; today's rule admits 24 | Evaluated both predicates on each trial's `q_at_stall_rad` through the shipped closed forms, with a window of 50.0 mm plus and minus `2 * tolerance(q)` as an illustrative band | **Computed here.** 31 of 31 against 24 of 31; the 7 it recovers are the campaign's 7-of-7 at 48.0 mm |
| F reports 9 of 33 valid FP trials as grasps against today's 18, and the 9 are a subset | Same evaluation on `raw/FP_trials.json`, V6 applied as the campaign applies it | **Computed here.** 9 against 18, subset holds; and it holds for every candidate band with a lower edge at or above 47.1215 mm |
| The validator's own floor derivation lands at 47.138 mm | Reimplemented `_grasp_discrimination_margin_m` at the shipped 45.0 mm default | 2.137972 mm, floor 47.138 mm — 0.017 mm from the C++ fixed point, below the campaign's 0.100 mm materiality (its D4) |
| `_narrowest_workpiece_width_m` records the two-state silence F must close | Read `physical.py:470-529` | Exact, including `_workpieces_without_a_stated_width` beside it, which already separates the two states |
| Two accessors walk the same work-piece list | Read `resolve.py:162-182` and `physical.py:470-502` | Both exist; `check()` takes a `FacilityModel` and the generator a `ResolvedCell`. **One fact, two routes** |
| `Grasp.Goal` carries a width and a bool and no part reference | Read `cite_interfaces/action/Grasp.action` | Exact. `width_m`, `max_effort_n`, `expect_object` |
| That F works | **Not verified. Nothing is built, no band is set, and no run of the cell has exercised F** | **Unverified**, and §A.10 is what would change it |

## Correction — 2026-09-01: option F names a lookup that cannot be written

**What is wrong.** Option F below says *"the part's width is the physical fact, it is declared
in L0 (ADR-0030), and `Pick.Goal` already names a `workpiece_id`"*. The first two clauses are
right. The third is right about the field and **wrong about what the field is**, and the
sentence reads as though the two together give L3 the part's width.

**`Pick.Goal.workpiece_id` is an instance id, not a type id.** It is minted by L4's registry —
`snprintf(buffer, sizeof(buffer), "wp_%06u", ++minted_)`,
`cite_orchestration/workpiece_registry.hpp:231-236`, reached from `AdmitWorkpiece`
(`line_nodes.hpp:610-620`) and put on the goal by `skill_nodes.hpp:653`. `WorkpieceRecord`
holds an id, an owner station, a location and a phase, and **no type**. Nothing in this
repository maps `wp_000007` to `workpiece`, the L0 type whose `Body` carries the width.

**What survives.** The decision. F is chosen and is buildable — §A.4 and §A.5 above specify it
without any per-goal lookup, using the *interval* of declared work-piece widths delivered at
facility level. The correction removes a route, not the option: it is what forces §A.5's
multi-part answer to be an interval rather than a per-part rule, and that is a better answer
than the one the false sentence implied.

**How it survived.** The field exists, it is named `workpiece_id`, and a work-piece type in L0
is also named `workpiece` — the same word for two things, one an L4 runtime instance and one an
L0 type, related by nothing. The record was drafted by reading `Pick.action`, where the field's
own comment is *"what to record as held on success"* and says nothing about a type; the
inference that it could be resolved to one was never checked against `WorkpieceRegistry`,
because a `grep` for `workpiece_id` in `cite_skills` returns six log lines and no lookup, and
that absence reads as "not used yet" rather than "not possible". **The check that would have
caught it is the one this project keeps relearning:** a sentence that says a value is available
must name the code that reads it.

## Context

### 1. The predicate, and the two signals it is built from

`cite_skills::gripper_is_holding` (`workspace/src/cite_skills/src/gripper.cpp:106-117`) is the
only thing in this project that decides whether a close ended holding a part. It has one
production caller, `command_gripper` (`skill_server.cpp:2128`), and two consumers of its
verdict: `Pick`, which returns `EXECUTION_FAILED` with `describe_empty_grasp` when it is false
(`skill_server.cpp:1118-1120`), and `Grasp` with `expect_object`, which does the same
(`skill_server.cpp:928-935`).

It requires two things:

1. **The goal was not reached** — `!report.reached_goal`. This carries no threshold and so
   cannot be miscalibrated.
2. **The pads stopped wider than commanded by a margin**, where the margin must exceed
   **twice** what the controller's own `goal_tolerance` is worth in width at the position the
   joint actually stopped at.

The second is the subject of this record. It is not a constant: `gripper_width_tolerance_m`
evaluates `|d(opening)/dq| * goal_tolerance` at the reached position, so it follows the
linkage rather than a snapshot of it. What *is* a constant is the factor **2**.

### 2. The arithmetic, computed from the shipped constants

Every input is declared once, in
`model/assets/types/end_effectors/xarm_parallel_gripper.yaml`, and reaches L3 through the
generated bring-up plan (`cite_bringup/plan.py:283-296`, `GRIPPER_KEYS`).

| L0 field | value | where |
|---|---|---|
| `linkage.drive_pivot_y_m` | 0.035 | `:205` |
| `linkage.finger_offset_y_m` | 0.035465 | `:207` |
| `linkage.finger_offset_z_m` | 0.042039 | `:208` |
| `linkage.pad_inset_m` | 0.026 | `:209` |
| `controllers[].parameters.goal_tolerance` | 0.01 rad | `:423` |
| `grasp.default_grasp_width_m` | 0.045 m | `:263` |

With `pivot = drive_pivot_y - pad_inset = 0.009 m`,
`crank = hypot(finger_offset_y, finger_offset_z) = 0.0550004 m` and
`phase = atan2(finger_offset_z, finger_offset_y) = 0.870017 rad`:

```
opening(q)   = 2 * (pivot + crank * cos(q + phase))
tolerance(q) = |2 * crank * sin(q + phase)| * goal_tolerance
holding      <=> stalled and not reached_goal
                 and opening(q_reached) - commanded > 2 * tolerance(q_reached)
```

#### 2.1 ADR-0045's example reproduces exactly

A commanded 45.0 mm is `q = 0.452793`. A genuine stall at **46.6 mm** is
`q = 0.437759`, where `2 * tolerance` is **2.1244 mm** against a margin of
**1.6000 mm**. `gripper_is_holding` returns false and `Pick` returns
`EXECUTION_FAILED` with an empty-grasp description **while the part is in the jaws**. ADR-0045's
verification table records 2.1244 mm; this record recomputed it independently and agrees to
four decimal places.

#### 2.2 The band, stated once as a width rather than as one example

Against a commanded 45.0 mm the predicate is false for every reached width up to
**47.1215 mm** and true above it.
So the band is **2.12 mm wide and begins at the commanded width**, and the 46.6 mm case is one
point inside it. The band moves with the command: it is always `[w_cmd, w_cmd + 2*tolerance]`,
about 2.1 mm on this linkage across the working part of the stroke.

#### 2.3 Three doors into the band, and the validator closes exactly one

- **A facility whose narrowest declared work-piece falls inside the band.**
  `default-grasp-width-never-closes` in `tools/cite_tools/validate/physical.py:578-680` already
  refuses this: it computes the same 2x margin from the same declared tolerance and errors when
  `narrowest_workpiece - default < discrimination`, where `discrimination` is evaluated at the
  default width and is **2.138 mm** on the shipped model. **ADR-0045's example, read as a
  declared work-piece, is therefore a model `./scripts/validate-model` rejects**: a 46.6 mm part
  against the 45 mm default leaves 1.600 mm, below 2.138 mm. Read the other way round — against
  the shipped 50 mm part the rule caps the default at **47.86 mm**, and 45 mm clears it.
  **This door is shut, and it is the one the example describes.**
- **A caller-supplied `Pick.Goal.grasp_width_m`.** `resolve_grasp_width`
  (`gripper.cpp:95-104`) takes any positive request verbatim, and **nothing validates a
  goal-supplied width against anything.** L4's `PickAt` sends one: `skill_nodes.hpp:591` and
  `:656` carry a port default of `0.045` in C++, so the shipped line does not use the L0 default
  path at all. This door is open.
- **A stall that lands inside the band at a part the validator was happy with.** The validator
  models the stall as occurring at the part's *nominal* width. The cell does not. §2.4 measures
  the difference. This door is open, and it is the one this cell is actually near.

#### 2.4 What the shipped cell measures — 47 trials, and the quantity nobody had computed

The hull-grasp campaign committed, for each of its 47 trials, the drive-joint position at the
hold (`q_at_stall_rad`) and the skill server's own report line
(`gripper: commanded 45.0 mm, reached Y mm, ... -> holding|empty`). Those two are the exact
inputs to this predicate. **The campaign asked a different question and published nothing about
this one**; the figures below were computed here from its raw and are new.

| computed here, from the campaign's raw | vendor meshes (n=24) | convex hull (n=23) |
|---|---|---|
| reached width at the hold, min | **47.607 mm** | 48.641 mm |
| reached width at the hold, median | 48.856 mm | 49.692 mm |
| margin / threshold, **min** | **1.230** | **1.723** |
| margin / threshold, median | 1.826 | 2.227 |
| shortfall from the part's nominal 50.0 mm, max | 2.393 mm | 1.359 mm |

**Every one of the 47 was reported `holding` with result code 0.** The defect did not fire.
What it did was come close: the worst trial cleared the threshold by **0.49 mm**, which is
**4.58 mrad** of drive travel, on the geometry that shipped until 2026-09-01.

Three readings, and none of them may be strengthened:

- **The L0 comment's "5.00 mm of margin, 2.3x the threshold" (`xarm_parallel_gripper.yaml:228`,
  `:255`) is arithmetic on a stall at the part's exact nominal width.** The measured median is
  **1.83x** on vendor geometry. The comment is not wrong about its own arithmetic; it is a
  statement about an idealised stall, and it has been read as a statement about the cell.
- **The shipped selection changed on 2026-09-01** to `convex_hull` (ADR-0028, promoted against
  the clause ADR-0051 restates), and the measured minimum ratio is better there — 1.72 against
  1.23. **That is not a fix and may not be cited as one.** It is one campaign, one machine, one
  arm, one part, one timestep, and **no CI run has ever brought this cell up on hulls**
  (CLAUDE.md §2). It is also not what the hulls were selected for.
- **Why the joint travels past the opening the map predicts is not established here.** The
  campaign measured contact-surface separation at the hold at about 50.0 mm on both geometries —
  the part's own width — while the drive joint read a median 1.14 mm narrower through the
  linkage on vendor geometry. Contact penetration was measured at essentially zero, so the part
  is not being crushed. A finger lagging its leader under load through the `gz_ros2_control`
  mimic servo would produce exactly this sign, and **that is a candidate mechanism and not a
  finding**: nothing here isolated it, and the campaign itself lists the reconciliation of these
  magnitudes as unmeasured. **If it is the servo, the offset is simulation-side and P2 is
  engaged**, because a physical linkage couples the fingers mechanically.

### 3. Why the factor of two exists — found, not assumed

It was chosen at **`cb4095e`, 2026-08-25**, in the commit that made the predicate discriminate
at all. Before it the predicate was `stalled && reached_width_m > commanded_width_m` — with no
`reached_goal` term — and that commit added both signals at once. **The factor has a stated
reason**, in `gripper.hpp:204-211`: *"one tolerance is the largest bias the controller can
produce, so anything above it is real; doubling it buys margin against the position being
sampled a cycle early."* So it is a factor somebody chose for a reason, not one nobody chose.

**Both halves of that reason are checkable, and one of them does not hold as stated.**

- **"One tolerance is the largest bias the controller can produce" is right.** The controller
  ends a goal as soon as `|error| < goal_tolerance`, so the reported position is short of the
  command by strictly less than one tolerance — 1.066 mm of width at the commanded position.
  Doubling therefore leaves exactly **one tolerance of headroom** above the worst bias.
- **The worked example the factor is justified against cannot reach this predicate.** The
  `DO-NOT-SIMPLIFY` block (`gripper.hpp:187-210`) and the regression test
  `GripperHolding.FreeAirIsNotAGraspEvenThoughItReportsExtraWidth` both use the measured
  free-air settle `kFreeAirSettle = 0.444793` (`test_gripper.cpp:64`) — **0.008 rad** short of
  the 45 mm command. `goal_tolerance` is **0.010 rad**, and the tolerance branch is evaluated
  **first** on every cycle, so at 0.008 rad of error the controller terminates on the success
  branch with `reached_goal = true, stalled = false`. `gripper_is_holding`'s **first** condition
  rejects that with no threshold at all. The test constructs `{stalled = true, reached_goal =
  false}` at that position, which is a pair of flags the controller cannot emit there: the two
  are mutually exclusive by construction upstream.
  **This does not make the margin useless and it does make its justification wrong.** What the
  margin actually covers is the *other* case the same header names: a jam or a fouled finger
  that stops the joint short of its command with nothing between the pads. The factor of two was
  never sized against that case, and no measurement of it exists.
- **"A cycle early" is not a measured quantity either.** The generated controller managers run
  at **150 Hz** (`cite_generated/control/cell_a_arm_*_controllers.yaml:15`) and L0 caps the
  drive at **1.0 rad/s** (`xarm_parallel_gripper.yaml:125`), so one cycle is at most 6.7 mrad,
  worth about **0.7 mm** of width — under one tolerance. The doubling is larger than the effect
  it is justified by, in a direction nobody measured.
- **The 45.85 mm free-air figure is stated as measured in `cb4095e` and is not published.** A
  search of `docs/measurements/` on 2026-09-01 found no campaign directory reporting it.

### 4. What the L4 layer does with the false report today, and what it does not

**The dead end is closed and the defect is not.**
[ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)'s refusal keys on
**custody**, not on a result code, and its comment names this defect by name as one of the
entrances it closes (`line_nodes.hpp:1140-1142`). `TakeCustody` stands above `PickAt` in the
shipped tree (`line_station.xml:90`, `:93`), so a misreported grasp fails with
`runtime.current_workpiece_id` already set, the retry is refused, and the station goes
`STATE_BLOCKED` instead of re-entering a wait nothing can satisfy. `EXECUTION_FAILED` still maps
to `RETRY_SAME` in `recovery_policy.hpp:140-142`; the custody precondition overrides it.

**So the consequence of this defect on `main` today is a line that stops and says so, needing an
operator, when nothing was wrong with the grasp.** That is strictly better than the silent stall
it used to produce, and it is not the same as being fixed. **Nothing may write that this defect
is fixed** — a real grasp is still reported empty.

### 5. Constraints any change has to satisfy

- **ADR-0022 is not reversed.** A grasp is evidenced by a stall, the controller reports and does
  not interpret, and deciding what a stall means stays L3's job. An option that moves the
  judgement into the controller is out of scope of this record.
- **ADR-0029 holds.** Friction alone holds the part; nothing on the simulation side assists a
  grasp. A reached width at a stall is therefore a measurement of the part, not an artefact — so
  it is legitimate evidence, and §2.4's shortfall is a question about the *reading*, not about
  the physics of the hold.
- **P2.** Whatever the test becomes it must read only fields
  `control_msgs/GripperCommand.Result` carries on both paths and must ask a question about the
  mechanism. A threshold tuned to Gazebo's stall behaviour is a P2 break — and note that §2.4's
  candidate mechanism, if it is the mimic servo, means the *present* operating point is already
  simulation-specific.
- **P1.** The factor **2.0** is written in two places today —
  `cite_skills/src/gripper.cpp:116` and `tools/cite_tools/validate/physical.py:574` — in two
  languages, each derived independently, neither reading the other. They are not even the same
  arithmetic: the skill linearises (`slope * tolerance`) at the **reached** position, the
  validator takes an exact finite difference over `2 * tolerance` of drive travel at the
  **commanded** position. On the shipped model they differ by 0.005 mm, so nothing is broken
  today; two derivations of one policy are free to diverge on the next edit.
- **This is a detector, not a protective measure** — ADR-0036's language, and it applies
  unchanged. It reports after the fact. Nothing here stops an arm doing anything, and no option
  below may be written up as a safety improvement.
- **`effort` is not available as a signal.** `GripperCommand.Result.effort` reads **60.0 N** in
  every line of the campaign's logs, including closes that reach their goal with nothing between
  the pads. It is the commanded `max_effort` echoed back, not a measurement of contact.

## Options considered

### Option A — Leave it, and document the band

Change nothing. Record the band, the doors into it, and §2.4's distribution, and let the
validator's ceiling plus ADR-0046's escalation carry the risk.

**For it:** the defect has never been observed firing; 47 committed trials cleared it, and the
one door the shipped model can reach it through — a declared part inside the band — is already
an ERROR at validate time. It costs nothing and risks nothing new.

**Against it:** the worst measured trial cleared by 0.49 mm on the geometry that shipped for the
whole of Phase 1, and the shortfall that produced it has no established cause. A goal-supplied
`grasp_width_m` is unvalidated, and L4 sends one. And the failure mode is the expensive kind:
the line stops, an operator is called, and the part was in the jaws all along.

**Not rejected.** It is the honest default if the owner judges the evidence too thin to move a
threshold on, and it is what this record leaves in place until a choice is made.

### Option B — Lower the multiplier

Replace 2 with a smaller factor — 1.5, say — moving the band's top from 47.12 mm to about
46.6 mm and admitting ADR-0045's example as a grasp.

**Against it, decisively as a standalone:** it is the same act that produced the present factor —
a number chosen against no measurement — and it trades one error direction for the other with no
data on either. The false-positive side is where it spends: the margin's real job (§3) is the
jam that stops the joint short of its command, and lowering the factor shrinks the set of jams
caught, in exchange for shrinking a band the shipped cell has never entered. **A test loosened
until it calls closing on air a grasp is exactly the failure ADR-0022 shaped this path around**,
and `default-grasp-width-never-closes`'s own hint says so in the validator.

**Rejected on its own.** It is admissible only as the consequence of D or E, where the number
falls out of something rather than being picked.

### Option C — Drop the width margin and judge on the controller's flags alone

`stalled && !reached_goal` and nothing else.

**What is right about it:** §3 shows the first condition already rejects the free-air case the
margin is documented as existing for, without any threshold. It cannot be miscalibrated, it is
identical on both backends, and it eliminates the band entirely — no real grasp is ever reported
empty.

**What it costs, and it is the whole cost:** it admits every stall that is not a grasp. A jam,
a fouled finger, a joint stopped by a hard limit or by a test hardware plugin all report
`stalled && !reached_goal`, and each would come back as a grasp. **This is the false-positive
direction and it is the one that ends with the line carrying an imaginary work-piece to the next
station**, which `skill_server.cpp:928-935` exists to prevent. It also contradicts
`gripper.hpp:172-175` — *"a gripper that jams, or one whose fingers foul each other, stalls just
as truthfully as one holding a part"* — which is ADR-0022's own reasoning.

**Rejected**, and it is the most instructive rejection here: the margin is doing a job, it is
just not the job its comment claims.

### Option D — Derive the factor instead of choosing it

Keep the shape and stop the factor being a constant. The two quantities the margin must clear
are both derivable: **the controller's end-of-goal bias**, which is at most one `goal_tolerance`
of drive travel, and **one control cycle of travel**, which is `max_drive_rate_rad_s /
update_rate`. The threshold becomes `tolerance(q) + one_cycle_width(q)`, both read from declared
values.

**For it:** it removes the arbitrary number and replaces it with the two effects the header
already names, each declared once in L0 or in the generated controller configuration. It follows
a vendor bump automatically, the way the present threshold already follows `goal_tolerance`.
On the shipped values it lands **below** today's 2x (§3: one cycle is worth about 0.7 mm against
a 1.07 mm tolerance), so it narrows the band without anyone choosing a number.

**Against it:** `update_rate` is L2 controller-manager configuration and the skill server does
not read it today, so this adds a value to the plan and a parameter to L3 — and one that is not
a property of the end effector, which is where the rest of this arithmetic lives. It also still
says nothing about the jam case, which is the margin's real job. And it is **strictly smaller**
than today's threshold on the shipped values, so it moves the false-positive side without a
measurement of that side.

**Not rejected.** It is the option that makes the number honest; it does not make it right.

### Option E — One derivation, read by both the runtime and the validator

Whatever the rule becomes, state it once and have `cite_skills::gripper_is_holding` and
`default-grasp-width-never-closes` read the same statement — the factor declared in L0 beside
`goal_tolerance` (P5: configuration is data), delivered to L3 through the plan the way every
other gripper key already is, and read by the validator from the model directly.

**For it:** it closes the P1 defect in §5 — one policy, two languages, two independently written
derivations. It also makes the validator's ceiling and the runtime's band provably the same
question. That matters more than tidiness: a fix that leaves the two disagreeing produces a
model that validates and a cell that misreports, which is the worst combination available
here.

**Against it:** on its own it changes no number and fixes no false negative. A declared factor is
still a chosen factor; this option only guarantees it is chosen once.

**Not rejected, and it composes with any of B, D and F.** It is the only option here that is
plainly right regardless of which of the others is taken.

### Option F — Judge against the part, not against the command

The band exists because the reference point is the **commanded** width, which is a policy value.
The part's width is the physical fact, it is declared in L0 (ADR-0030), and `Pick.Goal` already
names a `workpiece_id`. The predicate becomes "the jaws stopped where a part of the declared
width would stop them, within a band" rather than "the jaws stopped more than a margin wider than
we asked".
**[Corrected 2026-09-01 — see the section "Correction — 2026-09-01: option F names a lookup
that cannot be written" above.]**

**For it:** it is the only option that addresses §2.4 rather than the constant. The measured
shortfall is a gap between the *nominal* part and the *achieved* stall, and a rule written
against the part can be given a band that the measured distribution fixes, in both directions —
too narrow is a jam, too wide is the wrong part or no part. It would also catch the case nothing
catches today: the jaws stalling at a width that is not the part's.

**Against it, and these are real:** it makes L3 depend on knowing what it is picking, which is a
larger interface change than anything else here (P3) and puts work-piece knowledge into a skill
that is meant to be part-agnostic (P9). It needs the L0 work-piece width delivered to L3, which
it is not today. It has to answer what happens when a facility declares several work-pieces or
none — the same silence `_derived_collision_is_within_its_measured_range` records as a gap. And
the band it needs is exactly the distribution §2.4 measures on **one machine, one part, one arm,
one timestep**, which is not enough to set one.
**[Overtaken 2026-09-01 — every objection above is answered or accepted in the amendment, and
none of them is retired by being answered.]** §A.5 removes the first by giving L3 the *interval*
of declared widths rather than the part, so no skill learns what it is picking; §A.4 answers the
second with a plan-level entry on the channel the plan already has; §A.5 and §A.7 answer the
third with an interval that degrades honestly and two validator rules that fire; and the fourth
**stands** — §A.6 states the interval measurement admits and deliberately sets no value inside
it, which is what §A.10's gate is for.

**Not rejected, and it is the largest piece of work here.** It is the option that would make the
measurement in the gate below worth taking for its own sake.
**[Amended 2026-09-01 — it is chosen. See the amendment above.]**

## Decision

**What is decided by this record:**

1. **The defect is real, it is recorded, and it is arithmetic rather than an observed failure.**
   No run of this cell has been attributed to it. §2.4's 47 trials all cleared the threshold.
   **[Overtaken 2026-09-01 — the campaign added under *Evidence* observed it firing, 7 of 7 at
   a commanded 48.0 mm, with the part in the jaws and the contact sensor witnessing it. The
   sentence was true when written; nothing about it was wrong. It is still true that no *run of
   the line* has been attributed to it.]**
2. **It is stated as a band, not as an example.** Against any commanded width `w`, the predicate
   reports a real grasp as empty for every reached width in `(w, w + 2 * tolerance)` — about
   2.1 mm on this linkage. Anyone writing about this must use the band; the 46.6 mm case is one
   point in it, and the door it describes is the one the validator already shuts.
3. **The margin's documented justification is wrong and its job is the jam case.** §3 stands on
   its own and does not wait on the choice below: the free-air example the `DO-NOT-SIMPLIFY`
   block and its regression test are built on is rejected by the predicate's first condition,
   and the controller cannot emit the flag pair the test constructs.
4. **Nothing is changed in the tree by this record**, and in particular **no threshold is
   loosened**. `gripper_is_holding` and the validator rule are byte-identical after it.

**What is deliberately not decided here:** which of A-F is taken. That is the project owner's,
and the record is written so the choice can be made on what is above rather than on a
recommendation dressed as a finding. **The drafting agent's reading, offered as a reading:**
E is right whichever else is chosen; C is the only one that should be closed off now; F is the
only one that addresses the measured distribution, and it should not be attempted before the
gate below has produced one.
**[Amended 2026-09-01 — the paragraph above is kept as written and no longer states what this
record decides. The project owner chose **F** on 2026-09-01, after the gate's campaign had
produced the measurement the last clause asks for; E is absorbed into F as a constraint rather
than chosen separately. The decision and F's mechanism are the section "Amendment — 2026-09-01:
option F is chosen, and this is what F is" above.]**

## Consequences

### What this gets us

- The defect ADR-0045 named is written down with the arithmetic, the doors, and — for the first
  time — **a measured distribution of the quantity the predicate consumes**, computed from raw
  that was already committed and that nobody had read for this purpose.
- Two things that were believed and are not true are now on the record: that the margin protects
  against the measured free-air case, and that the shipped configuration sits at "5.00 mm,
  2.3x".
- Whoever takes the decision has both error directions in front of them, which the present code
  comments do not provide.

### What this costs us

- **The defect is still live.** A real grasp between the commanded width and 2.1 mm above it is
  still reported `EXECUTION_FAILED`, on both `Pick` and `Grasp`, and on `main` today that stops
  the line and calls an operator.
- **A goal-supplied `grasp_width_m` remains unvalidated**, and L4 sends one from a C++ port
  default that duplicates the L0 value (`skill_nodes.hpp:591`, `:656`; its own comment says the
  plan does not deliver the default to L3, which is no longer true — `plan.py:287` and
  `skill_server.cpp:305` both carry it).
  That duplication is a P1 defect this record found and does not fix.
- **The factor stays in two languages.** Until option E is taken, an edit to one derivation
  silently diverges from the other.
- One more `Proposed` record on a pile of them, with no test moving until a decision is taken.
  **[Overtaken 2026-09-01 — the record is `Accepted` and the decision is taken. What it costs
  now is different and is not smaller:]** an `Accepted` record that changes no line of code is
  a specification somebody has to build, and until they do, **every cost above is still being
  paid**. The two bullets above it are unaffected by the choice: the defect is live, the caller
  door's duplicated C++ port default is untouched, and the factor is still written in two
  languages — §A.7 makes that last one worse under F rather than better, and says so.

### What we will have to revisit

- **Any change to `goal_tolerance`, `max_drive_rate_rad_s` or the linkage** moves the band. The
  band follows the tolerance automatically; §2.4's *distribution* does not follow anything, and
  would have to be re-measured.
- **Phase 3's physics retune, and any change of `max_step_size`.** The hull-grasp campaign's §7
  names the timestep as the variable a grasp figure is most sensitive to, citing the friction
  campaign for the size of it; §2.4 is at one timestep and says nothing about another.
- **The physical arm (Phase 2.B).** If §2.4's shortfall is the mimic servo, it does not exist on
  hardware and the operating point moves. That is a P2 question, and it is the one this record
  would most like answered.
- **A second work-piece width.** It reopens option F's shape and re-engages the validator's own
  recorded silence about a facility declaring no work-piece at all.
  **[Overtaken 2026-09-01 — F is chosen, so this is no longer a thing that *would* reopen a
  shape; it is a thing the shape has to survive.]** §A.5 decides it — the interval of declared
  widths, never the part — and §A.7's two new validator rules are what make a spread that
  destroys F's discrimination, and a facility that declares no width at all, fire rather than
  pass.

## When this record is promoted

**[Amended 2026-09-01 — all three clauses below are met and this section is spent. It promoted
this record; it does not gate the implementing change, and §A.10 of the amendment above is what
does. The clauses are left exactly as written.]** Clause 1: the project owner chose **F** on
2026-09-01, recorded in §A.1. Clause 2: the campaign ran and is
[`docs/measurements/2026-09-01-grasp-discrimination/`](../measurements/2026-09-01-grasp-discrimination/ANALYSIS.md),
publishing both directions with its thresholds registered first and its machine named. **Read
its §3.1 before citing the false-positive bullet below as answered:** the control that was
meant to test §3's free-air prediction was **refuted as a prediction about its own rig** and
measured `mock_components/GenericSystem`'s dead velocity channel instead, so §3's prediction
about the **production** backend is *untested by that campaign, not confirmed by it* — its own
§8 says so. What the campaign did settle on this side is the stopped-joint case this bullet
names, and it settled it: **REPRODUCED**. Clause 3: §A.7 above states how the two derivations end up answering one
question, and makes it a condition on the implementing change rather than a hope.

**Written as a gate that asks for evidence that can exist**, in the shape ADR-0043, ADR-0049 and
ADR-0051 arrived at the hard way. Three clauses, and the measurement the second asks for is
one a run of this cell already produces.

1. **The project owner chooses among A-F**, and the choice is recorded here as a decision with
   its reasoning. A choice of A promotes this record with no code change and the band documented
   where it is enforced.
2. **If the choice is anything but A, a campaign under
   [`docs/measurements/`](../measurements/README.md) publishes both error directions**, with its
   thresholds registered before the first trial and its machine named:
   - **The false-negative side.** Over N grasps of the shipped part at the shipped command,
     report the distribution of `(reached - commanded) / (2 * tolerance(q_reached))` and its
     **minimum**. The instrument already exists and needs nothing built: the skill server prints
     `gripper: commanded X mm, reached Y mm, ...` on every close, and the drive-joint position is
     on `/joint_states`. §2.4 is a first sample of exactly this at n = 47, taken for another
     purpose.
   - **The false-positive side.** Command a close at the same width **with nothing between the
     pads**, and report which of `reached_goal` and `stalled` the controller returns and at what
     position. §3 predicts `reached_goal = true` and therefore no verdict from the margin at all;
     if that reproduces, the margin's remaining job is the jam case and a candidate rule must be
     measured against a **stopped** joint — `cite_test_hardware`'s `JointStopSystem` (ADR-0040)
     stops a named joint part-way and is the fixture that produces one on demand.
   - **A pre-registered rule for what would refuse the chosen option**, in the shape ADR-0051's
     rule S took: if the campaign cannot produce a false positive at all, it has not tested the
     false-positive side and its silence there may not be read as "no change".
3. **Whatever is chosen, the runtime predicate and `default-grasp-width-never-closes` end up
   answering the same question.** This is a constraint and not a choice of option E: a change
   that moves one derivation and leaves the other where it was produces a model that validates
   and a cell that misreports, and it does not promote this record.

**What will not promote it:** a green CI run. This defect is silent when it does not fire, and
it has not fired in any run anyone has looked at.

## What is not measured, and what would settle each

- **Why the drive joint reads 1.14 mm (median, vendor) narrower than the part it is holding.**
  Candidate: the mimic servo's steady-state error under contact load. **Settled by:** sampling
  the five follower joints alongside `drive_joint` through a hold and reporting the leader-follower
  error, which `/joint_states` already carries.
- **Whether any of this transfers to the physical gripper.** It cannot be measured until Phase
  2.B: there is no `GripperActionController` on that path at all — the vendor's macro emits the
  gripper's `<ros2_control>` block only for the simulated plugin, and the real gripper is driven
  through the SDK's service layer (`xarm_parallel_gripper.yaml:398-412`). **Settled by:** the
  hardware bring-up, and by nothing before it.
- **The rate at which a stall lands in the band.** §2.4 is 47 trials on one machine at one
  timestep on one part with one arm, taken for another question, with no thresholds registered
  in advance. It is **not a rate** and must not be quoted as one.
- **Everything about the jam case.** A survey of [`docs/measurements/`](../measurements/README.md)
  on 2026-09-01 found no campaign reporting where a fouled or jammed gripper stops relative to
  its command — which is the quantity the margin's real job is sized against. **Settled by:** a
  block driven through `cite_test_hardware`'s `JointStopSystem` on the drive joint (ADR-0040),
  which stops it part-way on demand.

## How the claims here were verified

In the style of [`toolchain.md`](../reference/toolchain.md). Everything was checked on
**2026-09-01** against this worktree at `dd93488`.

| Claim | How | Result |
|---|---|---|
| The predicate is `stalled && !reached_goal && margin > 2 * tolerance(q_reached)` | Read `cite_skills/src/gripper.cpp:106-117` | Exact |
| Its inputs are the seven linkage dimensions plus `goal_tolerance`, all declared in L0 | Read `xarm_parallel_gripper.yaml:204-211`, `:423`, and `cite_bringup/plan.py:283-296` | Exact. All thirteen gripper keys reach L3 through `GRIPPER_KEYS` |
| ADR-0045's example: commanded 45.0 mm, stall at 46.6 mm, margin 1.6 mm, threshold 2.12 mm | Recomputed independently in a standalone script from the L0 constants and the three functions in `gripper.cpp` | **Reproduces.** Margin 1.6000 mm, threshold 2.1244 mm, predicate false. Agrees with ADR-0045's own table to four decimals |
| The band's upper edge is 47.1215 mm against a 45.0 mm command | Bisection on `opening(q) - 0.045 - 2*tolerance(q)` in the same script | 47.1215 mm; band width 2.1215 mm |
| Worst-case free-air bias is one tolerance = 1.066 mm of width at the commanded position | Same script, `opening(q_cmd - goal_tolerance) - opening(q_cmd)` | 1.0650 mm. So 2x leaves exactly one tolerance of headroom |
| The controller evaluates `goal_tolerance` **before** the stall branch, and `reached_goal` and `stalled` are mutually exclusive | Fetched `ros-controls/ros2_controllers`, branch `jazzy`, `gripper_controllers/include/gripper_controllers/gripper_action_controller_impl.hpp` | **Verified upstream.** Tolerance branch first, sets `reached_goal = true, stalled = false`; the stall branch is reached only when the tolerance branch does not fire |
| `kFreeAirSettle` is 0.008 rad short of the 45 mm command, i.e. inside `goal_tolerance` | Read `test_gripper.cpp:57-64`; `q_cmd = 0.452793` from the script | 0.452793 − 0.444793 = 0.0080 < 0.010. So the measured free-air case terminates on the success branch and the margin never sees it |
| The 45.85 mm free-air figure has no published campaign | Searched `docs/measurements/` for the figure and for the constant, and read `cb4095e`'s message | **A survey on this date found none.** The commit states it as measured; it is not published with raw anywhere in the tree |
| The factor of 2 was chosen at `cb4095e` with a stated reason | `git log -S`, then read the commit message and `gripper.hpp:204-211` | Exact, and quoted in §3 |
| Controller managers run at 150 Hz and the drive is capped at 1.0 rad/s | Read `cite_generated/control/cell_a_arm_1_controllers.yaml:15` and `xarm_parallel_gripper.yaml:125` | Exact. One cycle ≤ 6.7 mrad ≈ 0.7 mm of width |
| `default-grasp-width-never-closes` computes the same 2x margin, and its ceiling is 47.86 mm | Read `physical.py:532-680`; reimplemented its arithmetic in the same script; read `tools/tests/test_validate_geometric.py:435-495` | Rule and ceiling as stated. **The validator was not run** — no Python environment in this worktree — so the ceiling is computed from the rule's source, not observed |
| The two derivations of the margin differ | Compared `gripper.cpp:116` (linearised, at the reached position) with `physical.py:574` (finite difference, at the commanded position) in the script | Both exist; 2.1327 mm against 2.1380 mm at the shipped default. `grep` finds `2.0` written in both files |
| 47 trials, all reported `holding`, minimum reached width 47.607 mm | Read every `*_trials.json` under `docs/measurements/2026-09-01-hull-grasp/raw/`; independently extracted the skill server's own report lines from the four `*_sim.log.gz` | **Both instruments agree.** 47 records, `pick_reported_holding` true and `pick_result_code` 0 in all; logs show 47 close reports at a 45.0 mm command, all `-> holding`, minimum printed 47.6 mm against 47.607 mm from the raw joint value |
| `q_at_stall_rad` is an independent read of the same joint | Read `harness/measure_hull_grasp.py:1039-1042` and `:409-421` | It is the last `/joint_states` sample of `arm_1_drive_joint` at or before `Pick` reports `PHASE_RETREATING` — **the same joint, sampled a moment after the predicate ran, not the value the predicate consumed.** The two agree to the log's 0.1 mm |
| Contact-surface separation at the hold is ~50.0 mm on both geometries | Read `harness/mechanism.py:40-70` and the campaign's §4 | It is the median y of right contact points less that of left — the separation of the two contact surfaces. **Cited from the campaign; not re-derived here** |
| Contact penetration is essentially zero | Read `penetration_depth_mm_median` across the trial records | Of order 1e-15 mm. The part is not being crushed |
| `effort` is the commanded maximum, not a measurement | Extracted every `gripper:` report line from the campaign logs | 60.0 N on every line, including closes that reach their goal with nothing between the pads |
| `TakeCustody` stands above `PickAt`, and the custody refusal names this defect | Read `cite_orchestration/trees/line_station.xml:87-93` and `line_nodes.hpp:1130-1170` | Exact. `TakeCustody` at `:90`, `PickAt` at `:93`; the refusal keys on `runtime.current_workpiece_id` and its comment names the `gripper_is_holding` margin defect explicitly |
| `EXECUTION_FAILED` maps to `RETRY_SAME` | Read `recovery_policy.hpp:140-142` | Exact, shared with `TIMEOUT` |
| L4 sends a non-zero `grasp_width_m` from a C++ default | Read `skill_nodes.hpp:570-591`, `:656` | Exact, 0.045 in both places. **Its comment says the plan does not deliver the L0 default to L3; `plan.py:287` and `skill_server.cpp:305` say it does** — the comment is stale |
| `gripper_is_holding` has one production caller and two consumers | `grep` over `workspace/src`, excluding tests | `skill_server.cpp:2128`; consumed by `Pick` at `:1118` and by `Grasp` with `expect_object` at `:928` |
| That any of this fixes anything | **Not verified. Nothing here is built, and no option is chosen** | **Unverified**, and deliberately so |
