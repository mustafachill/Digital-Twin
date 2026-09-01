# ADR-0052: Decide what separates a real grasp from a stall on nothing

- **Status:** Proposed — **and this record deliberately chooses nothing.** It states a defect,
  the arithmetic that produces it, the measured distribution the shipped cell actually sits at,
  and six options with what each costs in both error directions. **The choice among them is the
  project owner's** and is owed a separate change; §"Decision" below says exactly what is
  decided here and what is not.
  **Nothing in the tree changes with this record.** `cite_skills::gripper_is_holding` is
  untouched, `tools/cite_tools/validate/physical.py` is untouched, no threshold, ceiling or
  tolerance moves, and no test is added or removed. The promotion gate is in §"When this record
  is promoted".
  **This is the record [ADR-0045](0045-measure-a-gripper-deadline-in-the-simulated-clock.md)
  says is owed** — its section *"A separate defect, found in the same investigation, owed its
  own record"* and its status block, which as of 2026-08-30 still read *"One thing named here
  as owed its own record still has none"*.
- **Date:** 2026-09-01
- **Deciders:** Docs-writer agent, drafting from the shipped source, the L0 declaration and the
  committed raw of the campaign named under *Evidence*. **The decision between options A-F is
  the project owner's and has not been taken.**
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

**Not rejected, and it is the largest piece of work here.** It is the option that would make the
measurement in the gate below worth taking for its own sake.

## Decision

**What is decided by this record:**

1. **The defect is real, it is recorded, and it is arithmetic rather than an observed failure.**
   No run of this cell has been attributed to it. §2.4's 47 trials all cleared the threshold.
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

## When this record is promoted

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
