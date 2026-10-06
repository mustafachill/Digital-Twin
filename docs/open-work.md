# Open work — snapshot of 2026-10-02, amended 2026-10-05 for ADR-0070

**Status: SNAPSHOT.** This is not a tracker and must not become one. It lists the open work of
the **main project** — the paired `cell_b`, where one signal drives one real and one Gazebo
xArm 5 with the same code — and nothing else.

Charter §11 says the home of *"what is being worked on right now"* is the issue tracker and
explicitly **not** a document. No tracker is configured for this repository, so this file keeps
the list as a **dated snapshot**. **When a real tracker exists, delete this file rather than
maintaining it.**

**It goes stale the moment work resumes.** Every item names the command, file or record that
reproduces it; check that, never this file. If an item disagrees with `./scripts/doctor`, with a
record in [`docs/adr/`](adr/README.md), or with a campaign in
[`docs/measurements/`](measurements/README.md), those are right and this is wrong.

**Re-cut on 2026-10-02 for the main project.** The file was first written on 2026-09-01 and
carried a "where the repository stood" table and a dated update log; both are gone, and so is
the body of every item that is closed or whose subject left the main tree with
[ADR-0069](adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md). Such an item keeps
its number and one line, because code and documents cite items by number. Its full text is in
git history: `git show 911ba08:docs/open-work.md`. Items whose subject is still in the main tree
but whose evidence was taken on `cell_a` or on a removed scenario keep their text and open with
a line saying so; **re-verify those on `cell_b` before acting on them.** Nothing else in an item
was re-read on 2026-10-02.

---

## How to read the four groups

The grouping is by **what kind of work the item is**, because that decides who can do it and
what "done" means:

- **Measurement debts** — nothing is known to be broken; something is *unknown*. Done means a
  published campaign with thresholds registered before the first trial.
- **Known defects** — reproduced or computed, with a record. Done means a fix plus a
  regression test that fails without it.
- **Structural** — correct today, wrong on the next robot type, gripper or backend. Done means
  the shape changes, not the value.
- **Instrument honesty** — the tools that decide whether anything else is true. Every one of
  these misled this project at least once.

---

## 1. Measurement debts

### #49 — Link-versus-environment clearance under hull geometry: the margin half is partially measured, the refusal half is not
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**Partially answered on 2026-09-04, and every part of the answer is bounded.** The
measurement this item asked for — in one of its two directions, on two of the three scenarios it
names — is
[`docs/measurements/2026-09-04-waypoint-clearance/`](measurements/2026-09-04-waypoint-clearance/ANALYSIS.md),
thresholds registered before the first trial, machine named, run against the shipped tree with
neither mesh set flipped by hand. **Cite the directory; no figure from it is copied here, and its
own reproduction clause forbids copying one** (P1, and see the third bullet below).

**The heading changed on 2026-09-04.** It read *"is measured by nothing"*, and that is no longer
true of the margin half. The item's identifier is unchanged.

**What is now measured.**

- **The cheap settlement this item named was carried out, for `bringup` and `continuous_line`.**
  The joint trajectories those scenarios published were replayed under **both** committed mesh
  sets and every link-to-object distance recomputed per waypoint against the generated planning
  scene. **It was not carried out for `pick_and_place`**, which this item names by name — see the
  fourth bullet.
- **Containment held in the measurement**, on both admissible captures: the hull was never farther
  from a scene object than the vendor mesh it was derived from, anywhere measured. That direction
  is a theorem of the derivation rather than a discovery, which is why it was registered as an
  instrument check — a reading the other way would have falsified the instrument. **No pair
  contacted under one geometry and cleared under the other**, and the campaign registered in
  advance that such a null **evidences nothing**.
- **Real close approaches exist, on trajectories `ValidateSolution` accepted** — the closest a
  gripper finger against a conveyor, recurring across blocks and across the symmetric arm. **The
  figures stay in the campaign directory and may not be cited as settled measurements**: REPRO1,
  the campaign's reproduction clause, is **NOT REPRODUCED** on all three blocks, and its
  registered consequence is that no distance verdict from the affected captures is published as a
  measurement. **The diagnosis must travel with that verdict** — what the two interpreters
  disagree about is an **argmax tie-break over a constant-zero array**, reported in dimensionless
  waypoint and trajectory indices compared against a metre tolerance, and not a distance. The
  campaign took the strict reading anyway and this item follows it: **nothing here closes #49, and
  no threshold, tolerance or ceiling may rest on it.**
- **`pick_and_place` contributed nothing, in any block.** Its trajectories were captured cleanly
  — nothing published went missing — and then dropped whole, because the one arm it plans on read
  its robot description back as zero characters every time (**#59**). So the approach to
  `table_pick`, the pose this item's own consequence sentence is about and the one the campaign
  put that scenario in for, is **unmeasured**. A silence produced that way is evidence about
  nothing.
- **The gripper's own configuration sensitivity is larger than the band the question is framed
  in.** Recomputing every gripper-link distance across the declared drive range moves it by more
  than the campaign's close band — reported, like every distance verdict there, under the failed
  reproduction clause. It decides nothing by registration; it is noted because any future rule
  keying on a band for a **gripper** link would be keying on a band narrower than that
  sensitivity.

**Still open: the refusal direction, and the reason is structural.** A trajectory the hull set
refuses is **never published** — MoveIt breaks the response-adapter chain on the first failure and
`ValidateSolution` stands before `DisplayMotionPath` — so a plan the hull set refuses and the
vendor set would have accepted **cannot be seen through the door this campaign used**. Refusals
were counted on the line capture; their geometry was not measurable, and a count of zero would
have established nothing either. **Whether a campaign that could see them runs is the project
owner's decision and none is proposed here.**

**The original statement of the question, kept because it is what the campaign measured against.**
ADR-0028's 484-configuration audit covered only the **34 arm-internal** link pairs. No audit has
ever paired hull geometry with the environment, and the generated planning scene holds four
40×40×120 mm beam housings, three conveyors, three pedestals and two tables.

**Bounded on one side, and this is what keeps it from being alarming.** The safety audit
verified over 20,000 random directions on all 13 hulls that the hull's support function exceeds
the source's by **+0.000000 mm** — the hull adds zero outward extent, so nothing approaching a
link convexly from outside can newly collide. All added material is inside a concavity. Per link
the hull can eat at most its concavity depth: `link2` 61.75 mm, `link3` 60.27 mm, `link_base`
33.25 mm, `link4` 21.76 mm, gripper base 14.07 mm, fingers 9.82 mm.

**Measured clean:** at the SRDF's two named group states (`home`, `hold-up`), all three arms,
every hull-to-scene clearance equals the vendor's to 0.00 mm.

**Not settled when this was written, and now measured for two of the three scenarios above:** the
arm at the configurations the cell actually reaches, which needs IK and a running `move_group`.
The consequence if it bites is a station approach pose newly refused by `ValidateSolution`,
surfacing as a `MoveTo` planning failure naming nothing about geometry — and the pick already does
this on `table_pick` under vendor geometry (ADR-0027).

**The cheap settlement, and it needs no campaign:** replay the joint trajectories the existing
`pick_and_place` and `continuous_line` scenarios produce under vendor geometry, and report
per-waypoint minimum distance from every link to every planning-scene object under both
geometries. **This is what the 2026-09-04 campaign did** — for `bringup` and `continuous_line`,
and not for `pick_and_place` — and it needed a campaign after all, for the reasons in the bullets
above.

**Never widen a ceiling or a tolerance to absorb a planning refusal that appears after the hull
promotion.**

### #20 — Following error under `gz_ros2_control`: the healthy-run half is closed, the firing half is not
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**Answered on the healthy-run half, 2026-09-04, and still open on the firing half.** The
measurement this item asked for, in one of its two directions, is
[`docs/measurements/2026-09-04-following-error/`](measurements/2026-09-04-following-error/ANALYSIS.md)
— thresholds registered before the first trial, machine named, run against the shipped cell with
`gz_ros2_control/GazeboSimSystem` asserted off the description the running node published.
**Cite the directory; no figure from it is copied here (P1).** The record it bears on,
[ADR-0036](adr/0036-execution-side-trajectory-tolerances.md), carries a dated amendment of the
same date, and **its status did not move.**

**The heading changed on 2026-09-04.** It read *"has never been sampled"*, and that is no longer
true of the healthy half. The item's identifier is unchanged.

**What is now known.**

- **The healthy run is sampled, and the sample is a measured one rather than an empty
  subscription.** A registered admissibility rule refuses a silence produced by an instrument
  that received nothing — the failure this item's own premise would otherwise have been
  indistinguishable from — and every condition cleared it with no instrument losses, across
  three bring-ups.
- **The path tolerance is *not* structurally silent under `gz_ros2_control`. It fired.** Two
  trials, on the concurrently loaded condition, aborting as `PATH_TOLERANCE_VIOLATED`, both
  attributed by the instrument's own naming to **the arm under test's own controller** and
  neither by its conservative fallback, with zero unattributed events anywhere in the campaign.
  **This item's premise — that the detector may never fire in CI — is falsified as a structural
  claim.**
- **Counts, not causes.** Two events across three bring-ups, **not one per bring-up**: the third
  produced none at the same schedule slot that fired in the first two. The campaign attributes
  neither the firings nor their absence, and neither is a rate.
- **At full velocity scaling the healthy peak lands above ADR-0036's own order-of-magnitude
  line** — the outcome the campaign registered as the uncomfortable one before any trial. That
  comparison belongs to ADR-0036 and is quoted in its amendment, not here. The three
  default-scaled conditions — the scaling `pick_and_place` and `continuous_line` run at — sit
  below it, and **each of those is a lower bound**: the controller compares its tolerance whether
  or not the state message is delivered, and a measurable share of the compared states never
  reached the recorder. The one verdict above the line is not weakened that way — a delivered
  sample establishes it.
- **The corrected command law is established rather than merely admitted**: the campaign's
  arithmetic and its measurement agree on every trial but the two firings, to five significant
  figures, and it declines to attribute those two. This supersedes the
  first-order-lag derivation this item states below and the one in ADR-0036's 2026-08-27
  correction, both of which omit the controller's one-period lookahead.
- **Concurrent load did not move the distribution** — INDISTINGUISHABLE, with both of the
  campaign's guards evaluated and neither binding — and **the goal-side verdict is CLEAR and
  uninformative by construction, registered as such in advance** so that it could not later be
  read as evidence.

**Still open: the firing half, and the reason is structural.** Nothing above shows the detector
**can** detect an obstruction under this backend. The two firings were **not induced**; the
campaign has no mechanism for making the tolerance fire and registered that half as out of scope
before its first trial. Making it fire needs a **Gazebo-side** mechanism that obstructs an arm
**link** while `gz_ros2_control` is the loaded hardware component.

**The instrument note this item used to carry is now settled, in the opposite direction.** It
recorded the item as blocked on the absence of a fixture that can hold a joint part-way, and then
that `cite_test_hardware::JointStopSystem` (ADR-0040) *"now exists and does exactly that"*.
**It cannot serve here.** `JointStopSystem` derives from `mock_components::GenericSystem`
(`workspace/src/cite_test_hardware/include/cite_test_hardware/joint_stop_system.hpp`), so it is a
`ros2_control` hardware component loaded **instead of** `gz_ros2_control/GazeboSimSystem`, not
beside it: a description that names it has no Gazebo plugin driving its joints at all, and a rig
built on it measures mock hardware again — the blind spot ADR-0036 names in its own "How these
errors survived" paragraph.

**Whether the firing half is worth building is undecided and is the project owner's.** No fixture
is designed, no ADR is proposed and no campaign is started for it here — the campaign's own §0
reserves that, and so does this item.

**Also still open, and untouched by the campaign:** the scenario sample ADR-0036's "revisit"
bullet asks for. That rig drives L3 directly and runs neither `pick_and_place` nor
`continuous_line`, so that part of the bullet is not discharged.

**Two things the campaign surfaced that this item did not contain, and that no registered rule
read.** Both are recorded as **observations attributed to nothing** — neither is diagnosed, and
neither may be written up as a defect on the strength of this paragraph.

- **The campaign's own criteria contained a "by construction" claim that its data falsified.**
  The criteria stated as a registered rule that three of the four conditions *could not* reach
  the speed at which the tolerance is stressed; one of them reached nearly twice the cap that
  clause asserts. The rule was applied literally against data already collected and the clause
  is recorded as **wrong** rather than corrected. Note the direction: the falsification made the
  campaign's stress coverage **larger** than registered, so no verdict was weakened by it. **What
  produced the speed is not attributed.**
- **Reference velocities exceed the description's own declared joint limit, including in a
  *healthy* trial**, while **no measured joint speed anywhere exceeded it** — so the exceedance is
  in the reference and not in the feedback. **Nothing in the campaign's rules reads
  `reference.velocities` against a limit**, so no rule fired on it and none was invented. Whether
  it is the time parameterisation's output, an artefact of the abort path, or something else is
  not decided; whether `gz-sim` clamps the plugin's velocity command against the joint's SDF
  limit is separately recorded as unverified.

**The original statement of the question, kept because the arithmetic in it is what the campaign
checked.** In simulation the position command interface is not a position servo:
`GazeboSimSystem::write()` computes `target_vel = -position_proportional_gain * error *
update_rate` (`gz_system.cpp:790-806`; default gain 0.1, update rate 150), a first-order lag with
τ ≈ 67 ms, and that command is computed **inside** the plugin, downstream of
`enforce_command_limits`, so nothing clamps it. **The campaign's corrected law adds the
controller's one-period lookahead to that lag and is what agrees with the measurement**; the lag
alone does not. The P2 asymmetry this item names — that the detector could be silent in
simulation while live on hardware — **is not resolved in either direction**, and nothing here is
evidence about the physical arm.

**Never widen a tolerance to absorb any of this.** ADR-0036's own instruction stands: if the path
tolerance flakes, set it to `null` before lowering its value. The campaign proposes no tolerance,
no threshold and no ceiling.

### #30 — Re-derive the six scenario wall-clock ceilings
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**Answered on the under-load half, 2026-09-03, and still open on the attribution half.** The
measurement this item asked for is
[`docs/measurements/2026-09-02-scenario-ceilings/`](measurements/2026-09-02-scenario-ceilings/ANALYSIS.md)
— thresholds registered before the first trial, machine named, measured on the configuration
this repository ships. **Cite the directory; no figure from it is copied here (P1).**

**What is now known.**

- **All four allocations were measured**, including the loaded ones this item asked for, and
  they were measured *at* the allocation rather than derived by scaling an unloaded interval.
- **This heading says "six" and the tree declares nine.** `grep -n "_CEILING_S = "
  tests/scenarios/*.py` returns **9** declarations across the three scenarios, and the campaign
  bands all nine, split into eleven (scenario, ceiling, condition) families. The heading is left
  as the item's identifier; the nine are what was measured.
  **[Overtaken 2026-10-01 — [ADR-0069](adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) removed `pick_and_place` and `continuous_line` and the ceilings
  they declared. The same grep now returns **8** declarations across two scenarios: `bringup`'s
  four, which the campaign banded, and `program_cycle`'s four, which postdate the campaign and
  **have been banded by nothing**. Read the campaign's `pick_and_place` and `continuous_line`
  families as a record of scenarios that run only in `projects/01` now.]**
- **Two `bringup` ceilings read TOO LOOSE at a full allocation and stay TOO LOOSE at four
  CPUs**: `TRAJECTORY_CEILING_S` and `SKILL_CEILING_S`. **Both intervals the 2026-08-29 campaign
  had to report *"not assessed"* under its rule D3 — `DELIVERY_CEILING_S` and
  `TRAJECTORY_CEILING_S` — are instrumented and recorded here, so the instrumentation debt this
  item names is discharged.** `TRAJECTORY_CEILING_S` is in both lists; `DELIVERY_CEILING_S`
  lands INCONCLUSIVE at every allocation, for the reason below. **`SKILL_CEILING_S` was assessed
  by the 2026-08-29 campaign, on a named proxy, and rule H forbids reading the two verdicts
  against each other** — the TOO LOOSE here is an absolute verdict on this host and this
  configuration, never a change.
- **One crossing is located and bracketed between two measured allocations.** Three ceilings
  were APPROPRIATE at every allocation tried and are reported **NOT LOCATED** for that reason,
  which the campaign's registered vocabulary says is **never** "safe at any allocation" — it is
  a statement about four allocations on one host. Four brackets are **OPEN**, and an open
  bracket is not a narrower one.
- **A family of cells is INCONCLUSIVE because the measured intervals are smaller than the poll
  quantum**, so no upper bound on the margin exists and no band can be stated. **That is a
  property of the instrument, not a pass**, and the campaign predicted it in the same breath as
  it registered the rule.
- **Eight cells are NOT ASSESSED.** Rule N governs every sentence about them: not tested is not
  fine, not loose, not unchanged, and never carried over from another condition or another
  scenario. **Silence is not a clearance.**
- **This item's *"ceilings derived on vendor meshes may now be loose"* is answered as an
  absolute verdict on the shipped configuration and not as a delta.** The campaign's **rule H**
  forbids differencing any margin against 2026-08-29's — different machine, different CPU
  architecture, different collision geometry — so nothing here is subtracted from, divided by,
  or described as an improvement on anything there.
- **Six of 28 runs were lost to the harness's own configuration read-back**, not to a wrongly
  configured cell, and none was topped up. Every `bringup` cell at the two largest allocations
  therefore rests on a single run. Read the campaign's own §2.1 before leaning on one.

**Still open: the two levers this item asked to have folded in are folded in by measurement and
not by attribution.** ADR-0043's throttle and the hull geometry are both present in what was
measured — the campaign measured the shipped configuration — and **nothing is attributed to
either**, because a control arm would require editing `model/`, which the campaign's §0 forbids
and its rule V1 would discard. Separating the two levers still needs a campaign that may change
the model, and that is a different campaign from this one.

**No ceiling was changed and none is proposed.** The campaign's §0 reserves every ceiling
change to the project owner and it proposes no replacement value for anything.

**Change no ceiling without the measurement, and never widen one to absorb a failure.**

### #17 — Pilz checks collisions every 0.1 s and can step past a beam housing
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**A campaign has looked for this and refused the question, 2026-09-04. That is not progress
toward closing it.**
[`docs/measurements/2026-09-04-waypoint-clearance/`](measurements/2026-09-04-waypoint-clearance/ANALYSIS.md)
measured the **per-waypoint tool-point step** on the trajectories the shipped scenarios published
— directly, against the arithmetic below, which is what this item had instead of a measurement; a
survey of the published campaigns on 2026-09-04 found no earlier one that measured that quantity.
**Cite the directory; no figure from it is copied here** (P1).

- **The region was never exercised, and the campaign's own rule says so.** Closing this question
  needs one consecutive-waypoint interval carrying **both** a large enough step **and** a close
  enough bracketing distance to something — *at the same time*. **No interval on any capture
  carried both.** The campaign's shape for that result is the useful part: **the cell moves fast
  where it is far from everything and creeps where it is close.** Moving fast far from everything
  tests nothing, and creeping close to something tests nothing either.
- **Its "no body passed between two checked waypoints" is a null that the campaign refuses to read
  as a pass.** The rule that refuses it was registered before the first trial, and so was the
  prediction that the campaign would end up unable to test this question — **the prediction
  held**. **The residual stands exactly as [ADR-0027](adr/0027-pilz-planning-pipeline.md) records
  it**, and that record carries a dated amendment of 2026-09-04 saying the same thing; its status
  did not move.
- **A campaign that did exercise the region would have to produce the two conditions together** —
  a trajectory that is moving fast at the moment it passes close to a thin object — which the
  shipped scenarios, at the shipped velocity scaling, did not produce in nine runs.
  **[Overtaken 2026-10-01 — the scenarios that campaign captured ran on `cell_a`, and two of the
  three left the main tree with [ADR-0069](adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md). Main CI now drives `bringup` and `program_cycle` on
  `cell_b`, whose trajectories no campaign has measured for this question.]**
  [ADR-0027](adr/0027-pilz-planning-pipeline.md)'s residual section records a second path to a
  larger step — a caller passing `velocity_scaling: 1.0`, which bypasses the 0.35 default — and
  nothing sends it today. Note also that the campaign's sub-sampling machinery **never ran on
  campaign data**: the part of that instrument this question depends on is unexercised, and a
  later campaign should not treat it as tested. **Whether such a campaign runs is the project
  owner's decision and none is proposed here.**
- **What that campaign did refute is a smaller thing, and it belongs here anyway:** one capture's
  tool-point step landed in the middle band of the scale registered in advance, against a
  prediction that every capture would land far below it. The step this cell takes is therefore
  not as small as the campaign guessed, and it is still nowhere near the region above.

Pilz does not search the planning scene; `ValidateSolution` is the sole environment-collision
gate, and it calls `PlanningScene::isPathValid`, which checks the trajectory's **waypoints** and
interpolates nothing between them. Waypoint spacing is Pilz's sampling time, 0.1 s — a C++
default argument (`TrajectoryGenerator::generate(..., double sampling_time = 0.1)`, called with
three arguments by `PlanningContextBase::solve`) with **no ROS parameter**, so it cannot go into
L0 and cannot be set from a generated file.

The arithmetic: at 0.1 s a waypoint step exceeds the 40 mm beam housing whenever the tool point
exceeds 0.40 m/s, and this arm's 3.14 rad/s ceiling at 0.35 velocity scaling permits roughly
0.077 m per step at 0.7 m reach. There are four beam housings in the scene. **[Overtaken
2026-10-01 — that was `cell_a`'s scene; `cell_b`, the one zone L0 declares, has two beams,
`infeed_beam` and `outfeed_beam` in `model/assets/instances/sensors.yaml`, and both are
objects in `workspace/src/cite_generated/moveit/cell_b_planning_scene.yaml`. Their housing
dimensions were not re-read for this edit.]**

Both obvious levers are cell-wide behaviour changes on a blocking CI gate — lower
`max_velocity_scaling`, or change the layout. A third worth weighing: **densify the trajectory
before validation** rather than slowing the arm.

This is a gap in the **only** environment-collision gate the cell has, so it should not sit
unowned — but it is narrow (thin objects, high tool speed) and closing it wrongly costs cycle
time everywhere.

### #41 — ADR-0043's real-time requirement
**Substantially overtaken and kept open deliberately.** ADR-0049 restated the requirement as
capacity plus a clock-deficit budget rather than relaxing it, the owner ratified that decision
on 2026-08-31, and the 2026-09-01 capacity campaign measures the shipped configuration
**clearing the 1.0 floor**.

What is still open is what this task was always about: **ADR-0049 sets neither of its two
thresholds**, and both ADR-0043 and ADR-0049 remain `Proposed`. Clearing a bare floor is not a
margin. Nothing in `workspace/`, `tools/`, `tests/` or `scripts/` measures either quantity
during a run — the only instrument is a frozen campaign harness no bring-up, scenario or CI step
reaches.

### #85 — The cell does not reproduce under one seed, and where that enters is UNRESOLVED
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**Opened 2026-09-22, on a published campaign:**
[`2026-09-22-is-a-run-reproducible`](measurements/2026-09-22-is-a-run-reproducible/ANALYSIS.md),
criteria frozen before its harness existed, harness frozen before its first trial, machine
named. **Cite the directory; its figures are not copied here (P1), and nothing here proposes a
fix** — that campaign's §0 reserves every consequence of it to the project owner.

**What is established.** Two runs of `./scripts/scenario pick_and_place --zone cell_b`, **same
seed, same world, same commit, minutes apart**, put the work-piece in two different places,
three orders of magnitude outside the threshold registered in advance, and differed in cycle
duration by several seconds. **Both runs passed**, printing the bare verdict, and both were
answered by Pilz alone — so no unseedable OMPL motion is inside the result. That is the point
worth carrying out of the campaign: **a scenario passing is not a statement that the run
reproduces.** **Two runs, one machine, one commit. That is not a rate**, and nothing was
registered about how often it happens.

**What is open, and it is the whole of this item.** **Q4 — where the irreproducibility enters —
is UNRESOLVED**, and it may not be answered out of that directory. The campaign's control did
not clear: a 1e-6 m perturbation passed through at unit gain and missed the sensitivity
threshold, so its rule N fired and **the two questions that would have localised the divergence
are NOT ADMISSIBLE**. **Nobody may write that the physics engine was shown to reproduce, that
`gz sim --seed` was shown not to reach it, or that the divergence sits in the solver, the
coupling or the planner.** The underlying figures are published in that directory, labelled as
figures and not as verdicts, and may be cited only that way.

**What a future campaign has to do differently, in that campaign's own words and not as a
proposal.** Its deviation D1 records that the threshold was **unsatisfiable by construction**:
the probe world's ground plane is infinite and centred, so the dynamics are exactly
translation-equivariant in x and a perturbation along x can only ever return the perturbation
back. The rig could have read SENSITIVE only by a floating-point rounding bit. **A control that
tests this metric must perturb an axis the dynamics are not equivariant in, or perturb a
rotation, and state the gain it expects before the first trial.** Whether such a campaign runs
is the project owner's decision and none is proposed here.

**Two facts this campaign wrote down that stand on their own, independent of every verdict
above.**
- **The physics stack has a generator and nothing in this tree seeds it.** The symbol scan
  ADR-0027 rests on now exists on x86_64, with its command and output committed, and it
  **confirms** that record — no gz-physics plugin references `gz::math::Rand`. It also shows
  `libdart` defining its own `dart::math::Random::setSeed`/`getSeed` and ODE's `dRand*` beside
  it. `gz sim --seed` does not reach any of them. **An undefined `rand` symbol is a link and not
  a call site**, so this says nothing by itself about what a run does; it is kept here because
  *"the physics is unseeded because there is nothing there to seed"* is no longer available as a
  reading. [ADR-0027](adr/0027-pilz-planning-pipeline.md)'s amendment of 2026-09-22 carries it.
- **`./scripts/sim` passes no seed at all.** `grep -rn CITE_PHYSICS_SEED scripts` reaches
  `scripts/scenario` and nothing else, and the launch file omits `--seed` entirely when the
  variable is unset. So every `./scripts/sim` and `./scripts/sim --pair` run is unseeded,
  whatever the flag does or does not buy — including the paired runs that prompted the campaign.

**Cross-references, none of them an attribution.** **#84** is the other half of the owner's
question and was measured separately: two paired sides whose clocks agree to 0.01 % and whose
work does not, with the lag concentrated in the phase that plans. **#60** is an intermittent
`continuous_line` failure whose physical cause is unestablished; a cell that does not reproduce
against itself is the background any such failure sits against, and **that is a reason to be
careful with both, not a link between them.**

### #86 — The box still lands 0.201 mm apart, and where that comes from is unestablished
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**Opened 2026-09-23, on the measurement in
[ADR-0061](adr/0061-hold-the-box-while-the-jaws-are-shut.md)'s "Clause 2" section.** Cite that
record; the figures are not copied here (P1).

**What is established.** Two runs of `pick_and_place` on `cell_b` under one seed, at one commit,
put the box **0.201 mm** apart — down from 0.763 mm before any of this work and 0.331 mm after
the tick and settle fixes. The drift at the transition out of the grasp fell from **+343 ms** to
**+7 ms**, and the commanded trajectories that carry the box tightened by one to four orders of
magnitude. **Two runs before and two after is four runs**, on one machine, with nothing
registered in advance. That is not a rate.

**What is open, and it is the whole of this item.** A real xArm 5 repeats a taught position to
**±0.1 mm**. The simulation is still at twice that, in a cell with no wind, no thermal drift, no
backlash and no wear to spend it on. **Nothing here localises the remaining 0.201 mm.** It is
not attributed to the solver, the coupling, the planner or the grasp, and the campaign that
measured the original 0.763 mm
([`2026-09-22-is-a-run-reproducible`](measurements/2026-09-22-is-a-run-reproducible/ANALYSIS.md))
answered that question **UNRESOLVED** — a verdict this item does not quietly improve on.

**What the spread looks like, because the shape is a clue and is recorded rather than read
into.** The three axes are not alike: x **2.66e-5 m**, y **2.01e-4 m**, z **1.33e-8 m**. Almost
all of it is in **one horizontal axis**, and the vertical is gone entirely. Nothing here says
why, and a reader should resist the first explanation that fits.

**What would move it, stated as work rather than as a plan.** The instrument already exists and
is cheap — two runs, one seed, the commanded motions compared by shape and the box's final
position by a pose query. What it cannot do today is say *where* the difference enters, because
it samples the box only at rest. Sampling the box's pose **through the carry**, at matched
simulated times, would say whether the two runs part company at the grasp, during the transfer,
or at the release. **Whether that is worth building is the project owner's decision and none is
proposed here.**

**Cross-references, none of them an attribution.** **#85** is the unresolved localisation
question this item inherits. **#60** is an intermittent `continuous_line` failure whose physical
cause is unestablished; a cell that does not reproduce exactly against itself is the background
any such failure sits against, and **that is a reason to be careful with both, not a link
between them.**

---

### #87 — A clamped drive joint sits dead for ~0.3 s and then moves at a saturated rate, and why is unestablished
**Opened 2026-09-24, on the measurement in
[ADR-0063](adr/0063-the-drive-joint-may-not-be-clamped.md).** Cite that record; the arms are not
copied here (P1).

**What is established.** With `gz::sim::Joint::SetPositionLimits` tightening the gripper's
drive-joint travel limit to the position it was stopped at, an open command from
`GripperActionController` produces **no joint motion at all for the controller's own
`stall_timeout` of 0.3 s** — long enough for it to declare a stall and return
`reached 50.0 mm, stalled=true, reached_goal=false` — and the joint then moves at a **saturated
2.0 rad/s**, with no acceleration ramp. The control arm, same cycle, same host, same commit
minus the travel limit, opens promptly and peaks at **0.952 rad/s**, the declared
`gripper_max_drive_rate_rad_s`. Both readings are from one single-side run each, recorded off
`/cite/cell_b/picker/joint_states` on a host confirmed empty of containers first.

**Repeated commands make it worse rather than better**, which is the part that rules out "the
command simply arrives late": with `Place` re-commanding the open until the declared
`gripper_result_timeout_` expired, the joint stayed pinned for the whole window — **116
commands, zero releases**, both sides of a pair.

**What is NOT established, and nothing here attributes it.** Why the joint is dead for that
window. Two readings are consistent with it and neither is tested: a command the joint-limit
enforcement holds back, and a controller whose own abort path is what finally lets the command
through. **The saturated 2.0 rad/s is a clue and not an explanation** — it is not the declared
drive rate, so whatever produced it bypassed the rate the close obeyed.

**The cheapest measurement that would settle it.** Record the drive joint's **command
interface** alongside its position through an open, on a cell with the travel limit in force —
`/dynamic_joint_states` carries command values where the hardware exports them, and the joint
trace already exists as scratch tooling. If the command is present and the joint is not moving,
it is the limit; if the command is absent until the controller aborts, it is the controller.
**One run answers it, and this item is not worth more than that** unless somebody proposes
constraining that joint again — which [ADR-0063](adr/0063-the-drive-joint-may-not-be-clamped.md)
forbids.

**Cross-references, neither of them an attribution.** **#86** is the residual paired spread this
work was chasing when it found this, and **#85** is the unresolved localisation question behind
both. Sharing a session is not sharing a cause.

---

### #88 — DART models no torsional friction, and that is the term the friction grasp needed
**Opened 2026-09-28, from a survey of public practice. Read from source, not from a forum.**

**The finding.** `gz-physics`' DART backend refuses torsional friction by name —
`gzwarn << "DART doesn't support torsional friction setting"` in
`dartsim/src/SimulationFeatures.cc` — and its SDF parser reads only
`surface/friction/ode`'s `mu`, `mu2`, `slip1`, `slip2`, `fdir1`, with no torsional element
parsed at all. Gazebo's own torsional-friction tutorial states the same limit from the other
side: *"Torsional friction currently works only with the ODE physics engine."* `gz-sim` defaults
to DART (`src/systems/physics/Physics.cc`, `// 3. Use DART by default`).

**Why it matters here, and it is the whole point.**
[ADR-0029](adr/0029-simulated-grasping-by-friction.md)'s 84-trial campaign measured the friction
grasp failing in **rotation** — up to **34.3°** of roll about the pad-to-pad axis — and measured
that the coefficient was not the lever: at μ = 0.5 / 1.0 / 2.0 the median twist ran
29.76° / 9.60° / 23.90°, **non-monotonic**, from which that record concluded that a grasp which
does not improve when friction is doubled is not limited by friction. **That conclusion was
right and now it has a mechanism**: `mu` and `mu2` are *translational* coefficients and the
failure was *rotational*. The knob being turned was not connected to the quantity that was
failing, because in this engine that knob does not exist.

**What the field does instead.** MuJoCo's documentation names `condim=4` — torsional friction
torque opposing rotation about the contact normal — as *"useful for modeling soft fingers"* which
*"can substantially improve the stability of simulated grasping."* Both Gymnasium-Robotics'
Fetch gripper and robosuite's Panda gripper set `condim="4"` on the pads.

**The one lever inside Gazebo, and it is a hypothesis rather than a recommendation.**
`gz-physics`' `bullet-featherstone` backend **does** parse `<torsional><coefficient>` and
defaults it to 1.0 (`bullet-featherstone/src/SDFFeatures.cc`). Changing the physics engine under
this cell is a large, unmeasured change touching every contact in it, and **nothing here says it
would help** — what is established is only that it is the one route to the missing term without
leaving Gazebo.

**This changes no decision and nothing is proposed.** ADR-0029 is `Superseded by 0061` and stays
exactly as written; [ADR-0061](adr/0061-hold-the-box-while-the-jaws-are-shut.md)'s rigid hold is
what the cell runs and this finding **strengthens** its rationale rather than disturbing it. What
is owed is that ADR-0061's context should say *why* friction could not be tuned into working,
because the next person to ask will otherwise reach for `mu` as four records already did.

---

### #89 — Every trajectory is stamped zero, so every motion is phased differently against the physics
**Opened 2026-09-28, from a survey of public practice. Source-verified, ATTRIBUTED TO NOTHING.**

**The mechanism, read from shipped upstream source.** MoveIt stamps every trajectory it hands to
a controller with time zero — `trajectory.joint_trajectory.header.stamp = rclcpp::Time(0, 0,
RCL_ROS_TIME)` in `moveit_core/robot_trajectory/src/robot_trajectory.cpp` — and
`ros2_controllers`' own documentation defines that as *"start now"*. The
`joint_trajectory_controller` then pins `t = 0` to whichever control cycle first samples the
goal (`trajectory.cpp`: `if (trajectory_start_time_.seconds() == 0.0) { trajectory_start_time_ =
sample_time; }`), and takes **that cycle's measured joint state** as the interpolation start
point. The goal itself is deposited from `gz_ros2_control`'s own `MultiThreadedExecutor` thread
and picked up on the next cycle.

**So a goal crossing DDS at a wall-clock instant nobody controls decides which physics step the
whole motion is phased against**, by up to one control period, on every run.

**Why it is recorded and not acted on.** It is consistent with everything
[`#86`](open-work.md) and [ADR-0065](adr/0065-the-cell-says-what-it-holds.md) measured, and
consistency is not attribution. A peer-reviewed competing attribution exists for Gazebo
specifically — that non-determinism comes primarily from the physics engine, discrete-time
integration and floating-point behaviour in the solvers — and the 2026-09-22 campaign's own
rule N already stopped this project reading a matching story as a cause once. **Nobody may write
that the process boundary caused this cell's divergence until physics is excluded**, and nothing
here excludes it.

**The cheapest discriminators, none of them run.** `gz-sim` runs every `ISystemPostUpdate` on its
own worker thread by default (`SimulationRunner.hh`, `parallelPostUpdates{true}`), and
`gz_ros2_control` puts `read()` and `update()` in `PostUpdate`; the switch
`<gz:policies><parallel_postupdates>false</parallel_postupdates></gz:policies>` exists in this
checkout's `gz-sim 8.15.0` (`kPoliciesTag` is in the installed headers) and is one line in the
generated world. Separately, `<collision_detector>bullet</collision_detector>` changes the
contact-ordering path, which DART fixed for FCL in **6.17.0** and this checkout links **6.13.2**.

**Cross-reference, not an attribution.** [`#85`](open-work.md) is the unresolved localisation
question both inherit.

---

## 2. Known defects

### #36 — The grasp predicate: decided, specified, implemented; the gate is not fully cleared
**Updated 2026-09-02 at `51195e0`. The rest of this file is still the 2026-09-01 snapshot.**
This heading read *"decided, specified, not implemented"* until then, and the body below it said
what the implementing change *must* carry. **The change landed on 2026-09-01**, about two hours
after the commit this snapshot was taken at — `abdae38` is 19:10 and the five commits run
21:08 to 21:44, same day, `git log -1 --format=%ad --date=iso` on each — and nothing re-read
this item.

**Updated again 2026-09-04 at `f6f8827`**, against a campaign that did not exist on either
earlier date. Everything above the "What moved on 2026-09-04" block below is the 2026-09-02
reading and is unchanged; the two blocks below it are this date's.

The owner chose **option F** on 2026-09-01 —
judge the grasp against the part rather than against the commanded width — and
[ADR-0052](adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) is `Accepted` with the
mechanism specified in its 2026-09-01 amendment, §A.1–A.11. **The record's status did not move
when the implementation landed and does not move here.**

Both error directions were measured on the **superseded** predicate
([`2026-09-01-grasp-discrimination`](measurements/2026-09-01-grasp-discrimination/ANALYSIS.md)):
a real grasp reported empty, and a stall on nothing reported as a grasp.

**What landed**, in five commits ending `d3eeac4`, all ancestors of `main`
(`git merge-base --is-ancestor <sha> main`): `53f1d58` declares the stall band and the
work-piece interval in L0; `7a3e4d3` carries both into the generated bring-up plan; `3f6fe6f`
replaces the predicate; `f14d189` and `d3eeac4` are the tests.
`cite_skills::gripper_is_holding` now takes a `WorkpieceWidths` argument and judges the
**reached** width against the declared interval widened by a stall band at each edge, and its
own comment states that `report.commanded_width_m` is deliberately not read
(`workspace/src/cite_skills/src/gripper.cpp:142-161`). The shipped band is
`stall_band_narrow_m: 0.002385` / `stall_band_wide_m: 0.002385` in
`model/assets/types/end_effectors/xarm_parallel_gripper.yaml`.

**What the implementing change had to carry**, from the amendment — kept because it is what the
change is judged against, not because it is outstanding:
- The predicate reads the **interval of declared work-piece widths**, never "the part" —
  `Pick.Goal.workpiece_id` is an instance id minted by `WorkpieceRegistry::mint_id`, and
  `WorkpieceRecord` carries no type. Option F's own text claimed otherwise and is corrected.
- The band's admissible interval is measured; **no value is picked**, because the campaign
  reports every width metric unresolved at its own resolution. The binding constraint instead:
  **F's admitting set at the shipped default command must be a subset of today's.**
- `default-grasp-width-never-closes` keeps its number and changes its job; two new ERROR rules
  are specified.
- The caller door half-closes: a supplied width can no longer move the band, but a wider one
  still ends the close on goal tolerance. `cite_skills::resolve_grasp_width` now returns
  `GraspWidthSource::Refused` for a requested or configured width inside
  `gripper_discrimination_margin_m` of the narrowest declared part
  (`workspace/src/cite_skills/src/gripper.cpp:107-139`).
- **P2 is a constraint, not a caveat.** The campaign establishes nothing about the physical
  gripper — there is no `GripperActionController` on that path at all.

**What moved on 2026-09-04**, and neither half is the implementation landing.

- **§A.10 item 1 — the re-analysis — is MET, and it is met as tests rather than as prose.**
  ADR-0052 §B.2 records both of its clauses held by code that runs:
  `tools/tests/test_stall_band.py::TestTheReanalysisGate` evaluates the shipped closed forms on
  the 2026-09-01 campaign's committed raw, and the validator rule
  `stall-band-admits-a-stall-on-nothing` (`tools/cite_tools/validate/physical.py`) holds the
  structural half for states no trial visited.
  `.venv/bin/python -m pytest tools/tests/test_stall_band.py -q` reads **22 passed** in this
  checkout on 2026-09-04. **This file did not carry that until now.**
- **Item 2's bracketing bullet is HALF met.**
  [`2026-09-03-stall-band-flip`](measurements/2026-09-03-stall-band-flip/ANALYSIS.md) —
  thresholds and harness frozen before the first trial, machine named, measured on the
  **implemented** predicate — brackets the **narrow** edge to the 0.05 mm the bullet names, on a
  refinement whose every registered conjunct is satisfied. It does **not** bracket the wide edge.
  That supersedes the 2.00 mm stop grid of
  [`2026-09-02-option-f-regions`](measurements/2026-09-02-option-f-regions/ANALYSIS.md) at the
  narrow side only. ADR-0052's 2026-09-04 amendment, §C.1 to §C.3, is where this is recorded;
  the campaign's figures are cited and not copied here (P1).

**What is still open.** Item 2 as a whole is not met, so the gate is not closed and the defect
is not recorded as closed.

- **The wide edge — and what stopped it is an instrument failure, not a missing measurement.**
  The wide arm's refinement block was collected in full, eighteen trials, and then discarded
  **whole** by a validity rule whose instrument is per trial and whose discard granularity is
  the block, after **one** of those trials read the robot description back off the running node
  as zero characters. That trial's own record shows the rig launched the shipped description
  with its hull references intact, and the other seventeen read them back. The campaign carries
  this in its §2 and in numbered deviations 15 to 18, applied literally rather than corrected.
  **Its silence at that edge is not a clearance:** its rule N refuses to read it as agreement
  with the arithmetic, as validation of either band value, or as evidence that the edge is where
  the declaration says. **ADR-0052 §A.9.5 is unchanged and `stall_band_wide_m` is no better
  evidenced than it was.**
- **Whether a second campaign runs is the project owner's decision and has not been taken.** The
  campaign says so of itself in its §12, and this file does not prescribe one — neither that one
  runs, nor what its rules would be.
- **Whether the removed monotonicity term `reached > commanded` returns is an open project-owner
  decision.** The 2026-09-02 campaign **REPRODUCED** the region dropping it opens: a drive joint
  jammed part-way through an opening stroke, inside the window, on jaws opening onto nothing,
  reports `holding = true` on **9 of 9** valid in-window jams, where the superseded predicate
  reports `false` on all nine, and the two controls outside the window are rejected. That is a
  direction ADR-0052 §A.3 **permits** by design. **Both** campaigns registered before their
  first trial that they do not take the decision, and neither does this file.

### #25 — A gripper controller over plain mock hardware reports a grasp on empty air
`mock_components::GenericSystem::read()` never writes the velocity state when the command
interfaces are position-only, which is what every generated arm here declares. The generated JTC
config declares `state_interfaces: [position, velocity]`, so a controller reading velocity over
that plugin gets a permanent zero from cycle one.

Harmless for the trajectory controller. **Not harmless for the gripper:**
`position_controllers/GripperActionController` is configured with `allow_stalling: true` and
`stall_velocity_threshold: 0.05`, so it decides "held" from the velocity state — and since
ADR-0029 removed the attachment plugin, `stalled=true, reached_goal=false -> holding` is the
**sole** evidence anywhere in this project that a part is actually grasped.

Both production backends write velocity, so the running cell is fine. The hazard is a future
launch test standing the gripper controller up over plain `GenericSystem`.

**A hazard, not a defect — no test does this today.** The minimum action is one sentence in
`docs/architecture/cross-cutting-testing.md` beside the existing "What tests are not allowed to
do" list. Note that the 2026-09-01 campaign refuted a related prediction: over plain mock the
jaws stall at exactly `stall_timeout × ramp rate`, so a control designed to test free air tested
the ramp instead.

### #19 — The `station_transfer_1` dead end
Closed: moved with the event-driven line to snapshot 01 (ADR-0069); the L3 gripper-deadline half stays in `cite_skills` and is unaffected; full text in git history (`git show 911ba08:docs/open-work.md`).

### #80 — A held work-piece is attached to nothing, so the collision gate cannot see it
`ValidateSolution` is the sole environment-collision gate, and it checks the arm's links against
the planning scene. **It checks nothing at all against the part in the jaws.** `grep -rn
AttachedCollisionObject workspace/src` reaches three prose mentions and **no call**. The
simulation holds the part by its own grasp hold — a Gazebo-side hold while the jaws are shut
([ADR-0061](adr/0061-hold-the-box-while-the-jaws-are-shut.md)), told what is held by
[ADR-0065](adr/0065-the-cell-says-what-it-holds.md) — and that hold is not a MoveIt attachment,
so MoveIt does not know the part exists. A 50 mm cube hangs roughly 25 mm below the fingertip plane, so a plan that
clears a surface at the fingers can drag the part through it.

**Pre-existing, and newly exercised by ADR-0060.** Before that record the transit from the pick
to the place swung the long way round, through an azimuth sector where this cell's planning
scene contains nothing within reach — an unmodelled payload swept over nothing costs nothing.
The short arc crosses the infeed table and the belt. **Nothing here is a predicted collision**:
what is established is that the gate is blind to the payload and that the traffic has moved.
Whether any real interpolation brings the part within reach of a surface is **unmeasured**.

**Not fixed, by the project owner's decision on 2026-09-21** — *"do not build a simulation that
depends on a simulation"*. Attaching the part for the duration of custody is the fix that would
make the gate honest for **every** held motion, and it is a decision of its own, not a detail of
ADR-0060. What checks this today is that `program_cycle` asserts where the work-piece ends up — resting
on the belt at its infeed frame, then carried along it: if the arm knocks it off a surface, the
scenario fails.

**The cheapest measurement that would settle it** is the minimum part-to-surface clearance over
the transit, which is one instrument away from what
[`2026-09-21-place-abort-and-the-held-part`](measurements/2026-09-21-place-abort-and-the-held-part/criteria.md)
already registers. Cross-references: **#81**, which is the same arc against a different object.

### #81 — ADR-0060's arc crosses the one object ADR-0027's sampling residual is about
ADR-0027 records that `ValidateSolution` checks trajectory waypoints and **interpolates nothing
between them**, at a sampling that works out to roughly 77 mm of tool travel per step on this
cell — against a break-beam housing that is **40 mm** across. That residual is the record's own,
and it is unchanged by ADR-0060.

**What changed is the traffic.** `infeed_beam` sits at azimuth **130.8°** from the arm base at
radius **0.727 m**, in a height band that overlaps the tool's transit height. The old wound arc
spanned [147.7°, 391°] and did not cross it; the short arc spans [31°, 147.7°] and does.
**This is a region newly entered, not a predicted strike** — both arc endpoints sit at radius
≈ 0.56–0.60 m, so reaching the housing needs the interpolation to bulge outward by about 0.13 m,
and **nobody has measured whether it does**.

**Why the existing campaign does not answer it.**
[`2026-09-04-waypoint-clearance`](measurements/2026-09-04-waypoint-clearance/ANALYSIS.md) looked
for exactly this and found no interval carrying both a large enough step and a close enough
bracketing distance — but it measured **the trajectories the old branch selection produced**,
and its own pre-registered rule refuses its silence as a clearance even for those. It does not
transfer to paths that did not exist when it ran. **Not fixed**, for the same owner decision as
#80; re-running that campaign's instrument against the new trajectories is what would settle it.

### #82 — `cite_twin` compares joint angles with no angular wrap, so identical postures can read as 6.283 rad apart
`workspace/src/cite_twin/cite_twin/divergence.py` compares the two sides with `abs(plant - counterpart)`
per joint and feeds `joint_error_max_rad`. Two arms in **identical** postures whose `joint1`
happens to sit on different 2π sheets therefore report a maximum joint error of a full turn.

**It is pre-existing and ADR-0060 does not fix it** — it makes the coincidence rarer, because
both sides now normalise toward their own current configuration and both start from `joint1 = 0`.
**Filed separately and deliberately not folded into that change**, because folding it in would
hide it. The metric is a divergence instrument: a false 6.283 is exactly the reading that would
be quoted.

### #90 — Every GUI run in this project rendered in software until 2026-09-28, and nothing said so

`gz sim gui` had no GPU. The container's `gui` service passes no `/dev/dri` device and
`NVIDIA_VISIBLE_DEVICES` does nothing unless the NVIDIA container runtime is the one in use; Mesa
reached for the Intel driver and for a device node that was not there, failed, and fell back to
llvmpipe — painting a 3D scene on the CPU. **The only thing that ever said so was two lines in the
launch log that read like warnings**: `failed to load driver: iris` and `egl: failed to create dri2
screen`.

**What it cost, measured on 2026-09-28 on this 16-core host.** A paired run with one window per
side drove the load average to **22.74**; the counterpart's arm fell **29.7 degrees** behind its
own commanded trajectory on `picker_joint1` and **35.3** on `picker_joint3` against a `0.01` rad
tolerance; the trajectory controller aborted with `GOAL_TOLERANCE_VIOLATED`, `Pick` returned result
code 10, and L4 stopped the line and asked for an operator — ADR-0036, ADR-0037 and ADR-0038 all
behaving exactly as specified. The plant side, on the same commands and commit, completed its whole
cycle. The same run **headless** carried both boxes end to end with zero tolerance failures.

**The fix, and what it is evidenced by.** `scripts/sim` now exports `__NV_PRIME_RENDER_OFFLOAD` and
`__GLX_VENDOR_LIBRARY_NAME` for a windowed run, **guarded on `libGLX_nvidia.so.0` existing inside
the container**, so a host without one falls through untouched. After it, `nvidia-smi` names both
`gz sim gui` processes holding **293** and **295 MiB** of VRAM at 30% utilisation, the load average
reads **3.91**, and a two-window paired run carried both boxes to the end of the belt with
**zero** `tolerances` lines, **zero** `code 10` and **zero** escalations.

**What this is not.** One run per configuration on one machine, nothing registered in advance. It
is a discriminator on the one variable that changed and it is **not a rate**, and it sets **no
threshold**: nothing here says how much machine a windowed pair needs, only that this one has
enough once the GPU is doing the drawing. **No tolerance and no ceiling was widened**, and none may
be — the tolerance is a detector and it did its job.

**What stays open, and it is the reason this entry is not simply closed.** Every GUI observation
this project has ever made was taken on a software-rendered, CPU-starved cell, and **nothing has
been re-taken**. Nothing is known to be wrong: the findings that came out of watching the window
are about planning and geometry, which software rendering does not touch. But an aborted arm, a
slow cycle or a teardown timeout observed in a GUI run before this date may have had a cause that
is now gone, and **a reader must not treat those observations as having been taken on the cell that
ships today**. The cheapest thing that would settle any one of them is to re-run it.

### #83 — Two documents say the planning scene is empty, and it has not been for some time
`workspace/src/cite_generated/moveit/cell_b_planning_scene.yaml` carries a comment saying
*"Nothing reads this file yet"*, and ADR-0026's Consequences still describe planning against an
empty scene. Both are falsified by `workspace/src/cite_bringup/launch/simulation.launch.py`,
which spawns a `planning_scene_loader.py` per arm, and by the six bodies the generated file
declares.

**It matters beyond tidiness.** ADR-0026 predicted that the interaction between Pilz and a
non-empty scene *"becomes visible the moment the planning scene stops being empty"*. It has, and
that interaction is the whole of **#80** and **#81**. A reader who trusts either sentence
concludes the collision gate has nothing to check.

### #84 — The two sides' clocks agree to 0.01% and their work does not: the lag is in planning, not in physics
**Observed on 2026-09-21 while the project owner watched a paired `cell_b` run its line.** Both
sides completed the cycle; neither was in error; and they visibly did not move together. The
owner's question — if they run in the same environment on the same signal, they should be
exactly synchronous, so why are they not — is what this item records the answer to.

**The clocks are not the cause, and that is the load-bearing reading.** Sampling `/clock` on each
side's own domain over a 60 s window with both arms idle:

| side | messages | sim elapsed | wall elapsed | achieved RTF | deficit vs wall |
|---|---|---|---|---|---|
| plant | 57 457 | 57.456 s | 57.496 s | **0.9993** | +0.040 s |
| counterpart | 57 542 | 59.421 s | 59.455 s | **0.9994** | +0.034 s |

A rate difference of **-0.01%**, and a deficit against the wall clock of about **40 ms over
58 s** on each side. **The two simulated clocks tick at the same speed.**

**The lag concentrates in one phase, and it is the phase that plans.** Decomposing one
pick-and-place cycle into each side's *own* interval between milestones:

| segment | plant | counterpart | counterpart slower by |
|---|---|---|---|
| `admitted -> grasp` — detect, home, approach, descend: **all the planning** | 16.567 s | 19.986 s | **+3.419 s** |
| `grasp -> offered` | 3.646 s | 3.785 s | +0.139 s |
| `offered -> completed` — **the belt carries the part; pure physics** | 19.214 s | 18.810 s | **-0.403 s** |
| whole cycle | 39.427 s | 42.582 s | +3.155 s (+8.0%) |

The physics segment is **the same on both sides to within half a second, with the sign against
the lag**. Essentially all of the divergence is in the segment that calls IK and the planner —
which run on the CPU in wall time, outside the simulation clock, throttled by nothing.

**Removing the GUIs made it worse, which kills the obvious explanation.** The same decomposition
with both Gazebo GUIs up: `admitted -> grasp` +0.818 s, whole cycle +1.006 s over 53.224 s
(+1.9%). Headless, the plant's cycle *fell* to 39.427 s while the counterpart's fell less, so the
gap widened to +8.0%. **"The GUIs are eating the CPU" does not survive that.**

**What is wrong with these numbers, stated rather than left to be found.**
- **One run per condition. Nothing registered in advance. No directory in
  `docs/measurements/`. This is an observation and it is not a rate.**
- **The two conditions have different cycle durations** (53.2 s against 39.4 s), so the two
  percentages are rates over unlike windows and may not be differenced.
- **About 1.13 s of the initial offset is the instrument's, not the system's**: the spawner used
  places the work-piece on the plant and then on the counterpart, sequentially. The *growth* from
  admission to completion is what the table above measures, and it excludes that offset.
- **The clock instrument's own flaw:** the two subscriptions matched at different moments, so the
  windows differ (57.496 s against 59.455 s). The achieved RTFs are each computed within one
  side's own window and are sound; any figure differencing the two sides' *elapsed simulated
  time* across those unequal windows is not, and none is quoted here.
- **The instrument is not committed.** It was written for this reading and lives outside the
  tree, so reproducing these figures means rebuilding it.

**What this bears on.** [ADR-0049](adr/0049-measure-the-real-time-floor-as-capacity.md) names the
**accumulated clock deficit** as the quantity that must be bounded and sets no bound —
`DEFICIT_BOUND_S` is `None` in `workspace/src/cite_twin/cite_twin/divergence.py`, which is why
every `DivergenceMetrics` sample this project can produce has `valid: false`. These readings say
the deficit against the wall clock is small and the deficit *between the sides* is not the
problem; **the unmeasured quantity that matters is planning latency**, which no record names.

**Nothing here is attributed.** Why the counterpart's planning is consistently slower than the
plant's on the same host, with the same code and the same model, is **not established**. Process
start order, CPU affinity and cache state are candidates and **were not chased**.

### #60 — `Place`'s final descent aborts at `cell_a__conveyor_1__infeed`
Closed: moved with the line to snapshot 01 (ADR-0069); full text in git history (`git show 911ba08:docs/open-work.md`).

### #26 — `bringup`'s `MoveTo` fails when a run is slow, and the split is perfectly disjoint
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

In the teardown campaign's 30 pre-fix `bringup` runs, five exited non-zero; two are teardown-only
and three failed `bringup`'s own `MoveTo` assertion — the functional half of a blocking CI gate.

**Duration is the discriminator and it separates cleanly.** Clean runs took 32–47 s; the three
failing runs took 94, 95 and 254 s. Runs 12 and 14 show suite times of 91.677 and 91.759 s, which
is a normal suite minus the `MoveTo` test **plus exactly** `TRAJECTORY_CEILING_S = 60.0`. Run 29
blew `SKILL_CEILING_S = 120.0`.

So the mechanism is severe slowness starving MoveIt past fixed ceilings — not a race, not a
rejection. **What causes a run to be twice as slow is the open question.**

Two traps in the evidence: the message *"the goal was never accepted"* is **misleading** — it is
a timeout, not an acceptance check, and that wording caused a wrong common-cause hypothesis once
already. And *"Command of at least one joint is out of limits"* appears in **all 30** runs
including the 25 clean ones, so it has zero discriminating power.

### #37 — `line_orchestrator` timed out waiting for `LineTopology` at bring-up
Closed: moved with the line to snapshot 01 (ADR-0069); full text in git history (`git show 911ba08:docs/open-work.md`).

### #55 — `planning_scene_loader.py` exits 1 on a refused scene diff: two occurrences
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**The heading read *"A paired bring-up failed on the plant side"* until 2026-09-10**, and it was
right about the only occurrence there was. The second occurrence is a **solo** bring-up, so the
configuration is not what this item is about; the refused scene diff is. Two dated documents
under [`docs/measurements/`](measurements/README.md) describe this item as a paired bring-up.
That stays true of the first occurrence and is no longer a description of the item.

**The first occurrence, 2026-09-01, paired.** The counterpart announced readiness; the plant
never did. The plant's `planning_scene_loader.py`
for `arm_1` exited 1 with *"move_group refused the planning scene diff for zone 'cell_a'"*,
**12.8 ms after** that same `move_group` logged *"Unknown frame: cite_world"*. The node is
`required`, so the plant's launch shut down, and per ADR-0047 a side that ends ends the pair.
**That delta read "14 ms" until 2026-09-10 and is recomputed here** from the two timestamps in
the committed console, `1788290006.935280548` (the first of twelve) and `1788290006.948123256`;
against the last of the twelve it is 12.79 ms. Nothing rests on the difference — it is corrected
because it is checkable.

**Why it reads as a race and not a bad scene:** the counterpart brought the identical
configuration up cleanly at the same moment, on the same machine, in the same trial. **That
argument is available for the first occurrence only**, which is the whole significance of the
second one; see below.

**Corrected 2026-09-10.** This item read *"One event in eleven paired and twelve solo bring-ups,
**not attributed**"* until that date. It is **two events**, and the denominator has been dropped
rather than added to: the first event was one of eleven paired and twelve solo bring-ups taken
inside a campaign, the second was one of five `bringup` runs taken to verify a branch before a
merge, and summing two sets that were taken for different reasons with nothing registered in
advance either time would be manufacturing a rate. **Not attributed** is the half that survives,
and it survives for both. The first occurrence's full evidence is still
`docs/measurements/2026-09-01-capacity-on-shipped-main/raw/PAIR_HULL_FREE_3.console`, which
carries both sides' output.

**The second occurrence, 2026-09-10, solo — and it is the first in that configuration.**
A `tester` agent ran `./scripts/scenario bringup` five times on one machine at
`CITE_PHYSICS_SEED=42` on the branch `feat/declared-simulation-backend` at `5516169`. Three
printed the bare verdict `Scenario 'bringup' passed`; two failed. This item is one of the two.
**The other failure matches #26's signature — `the MoveTo goal was never accepted`, 95.977 s
against 41.5 / 41.2 / 43.5 s for the three that passed, against #26's recorded 94–95 s versus
32–47 s — and it is named here and nowhere else. #26 was not touched by this reading**, and
whether that item earns a line of its own is a separate decision. The
failing run was the first after a clean `./scripts/clean` and `./scripts/build`, as the tester
reported it; the log's own header records `Running scenario 'bringup' on DDS domain 43` and
`Bringing up zone cell_a side plant`, so it is a solo plant bring-up with no second side in
existence.

The chain, in the order the console carries it, quoted rather than summarised:

```
[move_group-15] [ERROR] [1789063688.916917294] [cite.cell_a.arm_1.move_group.moveit.core.planning_scene]: Unknown frame: cite_world
        ... twelve such lines, 1789063688.916917294 through .917012729 ...
[planning_scene_loader.py-24] [ERROR] [1789063688.935452500] [cite.cell_a.arm_1.load_planning_scene_arm_1]: move_group refused the planning scene diff for zone 'cell_a'
[ERROR] [planning_scene_loader.py-24]: process has died [pid 657, exit code 1, cmd '...cite_facility/planning_scene_loader.py --ros-args -r __node:=load_planning_scene_arm_1 -r __ns:=/cite/cell_a/arm_1 ...']
[INFO] [launch.user]: BRING-UP FAILED before the planning scene for arm_2: the previous step exited 1.
[INFO] [launch]: process[planning_scene_loader.py-24] was required: shutting down launched system
[INFO] [gz-1]: sending signal 'SIGINT' to process[gz-1]
[ERROR] [move_group-15]: process has died [pid 101, exit code -11, ...]   (and -16, -17, all three)
error Scenario 'bringup' failed — 8 cycle assertion(s) failed
```

The refusal is **18.5 ms** after the first of the twelve `Unknown frame` lines and 18.4 ms after
the last, from the two timestamps above. All eight cycle assertions failed with the identical
`Exception: Launch stopped before the active tests finished.`, and the teardown assertion
`test_nothing_of_ours_exited_badly` failed with the same exception — the cell was gone, so
nothing was measured about it.

**The tester reported 24 `Unknown frame: cite_world` lines; the distinct count is 12.** A raw
`grep -c` over that console doubles every process line, because `launch_test` replays each
process's whole output after the run — `Tf has two or more unconnected trees` reads 126 the same
way and is 63. The first occurrence's console, which is not a `launch_test` run, carries 12 and
63. **Compare distinct lines, not grep counts**, which is the same instrument defect CLAUDE.md §2
records for CI logs from the other direction.

**The three `move_group` -11s are recorded and not classified.** They are in
`rclcpp::CallbackGroup::~CallbackGroup()` on the way out of a shutdown this failure induced, and
the tester's own framing is kept: they are **consequences of the induced shutdown**, not the
exempted upstream teardown case, and **no exemption was widened**. They are also **not part of
this signature** — in the first occurrence all three `move_group`s exited **-15**, so the tails
differ and only the trigger matches.

**Attribution to the branch it was seen on was checked and is negative**, re-run here on
2026-09-10: `git diff --stat main..HEAD -- workspace/src/cite_facility
workspace/src/cite_generated/frames workspace/src/cite_generated/description` is **empty** at
`5516169` against `main` at `41b41e5`, and the branch's only change to `simulation.launch.py` is
a comment — `git diff main..HEAD -- '*simulation.launch.py' | grep -E '^[+-][^+-]'` returns
comment lines and nothing else, so the executable line `require_hardware_opt_in(plan,
os.environ)` is untouched.

**Strength.** One event, on one machine, at one commit, with **nothing registered in advance**.
It is **not a rate** and it is **not a campaign**. Nothing about the cause is attributed; the
first occurrence was not attributed either and this one adds no attribution. **A second
occurrence of an unattributed signature is a second occurrence and not a diagnosis.**

**It is textually the same failure as the first occurrence, and this was checked rather than
assumed on the strength of a shared node name.** Four points of identity, read here on
2026-09-10 from the two consoles: the same error string from the same node
`cite.cell_a.arm_1.load_planning_scene_arm_1` for the same zone and the same arm; the same
branch of the loader — the `if not response.success` branch of `PlanningSceneLoader.load` in
`workspace/src/cite_facility/cite_facility/planning_scene_loader.py`, cited by symbol because a
line number in a file under edit goes stale — a refusal that **returned**; the same twelve
`Unknown frame: cite_world` lines from that arm's `move_group` planning-scene logger in one
sub-millisecond cluster immediately before it; and the same 63 `Tf
has two or more unconnected trees` warnings — **an identical set, character for character**,
after stripping the launch prefix and the timestamp
(`grep "Tf has two or more" <console> | sed 's/^\[plant\] //; s/^\[[a-z_]*-[0-9]*\] //;
s/\[[0-9.]*\]//; s/^\[WARN\] //' | sort -u`, `diff` clean over both). The launch chain that
follows is the same line for line, down to `BRING-UP FAILED before the planning scene for
arm_2`. **What differs is the configuration, the delta (18.5 ms against 12.8) and the shutdown
tail.**

**What the solo occurrence does to the race reading.** The argument that this is a race and not
a bad scene was that a counterpart running the identical configuration came up cleanly at the
same moment, on the same machine, in the same trial — a control the first occurrence had for
free. **A solo bring-up has no companion side, so that control does not exist here.** What
replaces it is weaker and should be read as weaker: three of the five runs in the same session,
on the same machine, at the same commit and the same seed, brought the same cell up cleanly, and
the two that did not failed in two different ways. That is a control separated in time rather
than one running concurrently, and it does not rule out a scene that is wrong only sometimes.
**The race reading is not refuted and it is no longer supported by a concurrent control.**

**The full console is not committed, and that is a decision with a stated cost.**
[`docs/measurements/`](measurements/README.md) is for campaigns, and CLAUDE.md is explicit that a
campaign has its thresholds written down before its first trial; this run has none and must not
be dressed as one. Every committed non-markdown file under `docs/` sits inside a campaign's
directory — `git ls-files docs | grep -viE '\.md$' | grep -vE '^docs/measurements/'` returns
`docs/adr/.gitkeep` and nothing else, run 2026-09-10 — so there is no third place for a 224 KB
console that would not be inventing one, and inventing an evidence category is a
documentation-structure decision rather than a bookkeeping one. Committing it under a campaign
directory would also move the `lint` walk, a count CLAUDE.md §2 reconciles by hand and records as
tracking *how much campaign evidence is committed*. **What is preserved instead is above**: every
string a future occurrence would be matched on, the timestamps both deltas are computed from, the
exit codes and the verdict. **What is lost is stated too:** the set comparison in the paragraph
above was run once, against a console in a session scratchpad that does not survive the session,
and **a reader cannot re-run it**. The first occurrence's console is committed and can still be
re-read; this one's cannot. If a third occurrence is caught, capture it — #37's standing
instruction, which this item already cites, applies to this item too.

**Why an event here matters more than usual:** it fails a `required` node and takes the whole
launch down — the whole pair, when there is a pair — and **no test covers paired bring-up at
all**: `launch_test` with `IncludeLaunchDescription` holds one context on one domain, so a paired
scenario cannot take today's shape. A regression here fails nothing. **This paragraph read "why
one event matters more than usual here" until 2026-09-10**; the argument is unchanged by there
being two. Note that the solo half *is* covered — `./scripts/scenario bringup` is a blocking CI
gate and is exactly what caught this one. **[Overtaken 2026-10-01 — both occurrences were on
`cell_a`, which left the main tree with ADR-0069. The node still runs once per arm on `cell_b`,
so a recurrence would now surface in `bringup` or `program_cycle`, the two scenarios main CI
drives. #37, which this item cites for its capture-first instruction, is closed and moved to
`projects/01`; the instruction stands here.]**

P4 is the lens: if the scene load depends on a frame becoming resolvable, that is a sequencing
question and the answer is an event, never a retry or a sleep.

**A related but textually distinct failure of the same node, 2026-09-03, and it is deliberately
not counted as another observation of this item.** During
[`docs/measurements/2026-09-02-scenario-ceilings/`](measurements/2026-09-02-scenario-ceilings/ANALYSIS.md),
the run `C4_continuous_line_1` failed at bring-up with `planning_scene_loader.py` exiting 1 —
this item's process — but with a **different error text**, from **`arm_2`** and not `arm_1`:
`'apply_planning_scene' never returned a result`. `arm_1` had already loaded its collision
objects; the node is `required`, so the launch shut down and the run's tests never started.
The campaign discarded the run and it contributes to none of its figures.

**Why it is not folded in here.** A line-break-insensitive grep for this item's own three
strings — `Unknown frame: cite_world`, `Tf has two or more unconnected trees` and
`refused the planning scene diff` — across **all 28** captured campaign consoles returns
**none of them**, re-checked on 2026-09-03. The two messages are **two branches of one
function**, adjacent in
`workspace/src/cite_facility/cite_facility/planning_scene_loader.py`: this item's is
`response.success == False`, a refusal that **returned**; the new one is `future.result() is
None` after `spin_until_future_complete(..., timeout_sec=SERVICE_DEADLINE_S)`, a call that
**never returned at all**, and the campaign reports an elapsed time consistent with that
deadline. They also differ in the configuration — this item is a **paired** bring-up and the
new event is a **solo plant** run, so this item's *"the counterpart brought the identical
configuration up cleanly at the same moment"* has no counterpart to lean on there.
**The attribution is left open**, and whether the two are one defect is not established.

**One of those four grounds is retired by the second occurrence, and three stand — noted
2026-09-10.** The configuration ground is gone: this item now has a solo occurrence of its own,
so *"paired versus solo"* separates nothing. The error text, the branch of the function and the
arm are unchanged and are the load-bearing ones — a call that returned a refusal and a call that
never returned are different failures whatever the configuration. The sibling stays uncounted,
and **the attribution stays open**.

**The console is captured**, at
`docs/measurements/2026-09-02-scenario-ceilings/raw/C4_continuous_line_1.log`, with the run
document beside it — which is what #37's standing instruction asks for. **This item's first
occurrence carries a console too**, named above; **its second does not**, for the reason given
above. **It is #37 whose single event was restarted rather than analysed with no log kept**, and
the three must not be confused.

---

## 3. Structural — correct today, wrong on the next type

### #50 — The hull measured-range constant is one gripper's property applied to every type
`NARROWEST_MEASURED_WORKPIECE_M = 0.050` in `tools/cite_tools/validate/physical.py` is the width
at which **the xArm parallel gripper's** pad plane sits 0.41 mm proud of **its** hull's relief
wedges. The rule that reads it is facility-wide: it compares the facility's narrowest declared
work-piece against one module-level global, for every type that binds a derived set, with no
reference to whether the type carries an end effector or which one.

Wrong in both directions. A second robot type declaring its own `convex_hull` set — with no
campaign behind it — **passes silently**, so the rule that exists to say "you are outside the
evidence" says nothing exactly when there is no evidence. And a second gripper with different pad
geometry is **passed** at 50 mm on evidence taken for a different gripper.

Suggested direction from two independent reviews: key the floor by the derived set's identity
(`CollisionMeshSet` already carries `package` + `root`) and make "no entry for this set" a
refusal rather than a pass. That keeps the number out of author-editable L0 — which is correct,
because deriving it from L0 would reduce the check to `narrowest >= narrowest`, a check that
cannot fail.

### #51 — The unconditional vendor-mesh ERROR leaves a genuine-collision-mesh vendor no valid model
`_vendor_collision_is_declared` now fires an unconditional ERROR on any vendor-described type
whose selected set is `vendor_meshes`, and its hint states an xArm-specific fact as if general.

Many vendors — UR, Franka — ship collision geometry genuinely distinct from their visual
geometry. Under the promotion such a type has **no valid model at all**: `vendor_meshes` is a hard
error and the only other kind is `convex_hull`, which requires the vendor checkout, a
`cite-model hulls` run, committed assets and a campaign. Adding a robot type is P9's primary swap
axis and this makes it strictly more expensive, as a CI-blocking error.

The rule's real assertion is *"this type's collision geometry **is** its visual geometry"*, which
is a model fact, not a consequence of the word `vendor_meshes`.

The same defect from the other side: `emits_vendor_description` tests `provider == "xacro_macro"
and category == "robot"`, so a future vendor-described end effector with `vendor_integrated:
false`, or a vendor-described fixture or sensor, would collide against its visual meshes and get
no finding of any severity.

**Note the coupling with the escape hatch:** the vendor set must remain selectable when the range
rule fires, so these two rules' conditions are already linked and should be designed together.

### #61 — The hardware gate iterates a constant pair of sides, not the plan's own `sides:`
`cite_bringup.plan.require_hardware_opt_in` walks `BACKEND_FIELD_BY_SIDE`, which names exactly
`plant` and `counterpart`. A plan declaring a **third** side would have that side's backend
gated by nothing — including a physical one, which is the direction that matters, since the gate
is what stands between a checkout and a real arm.

**Not reachable today, and that is the whole reason this is here rather than fixed.**
`cite_tools.model.ids.SIDES` is exactly two, `cite_twin.routing`'s `_COMMANDED` names only
those two, and no generator can emit a third. The exposure is identical at `e18251e` and was
not introduced by ADR-0048 clause 3. It became worth writing down when the load-time refusal
`_every_declared_side_states_a_backend` landed on 2026-09-08: that function walks the plan's
own `sides:` and skips a name it has no backend field for, deliberately, because deciding how
many sides may exist is L0's answer and not the reader's — so the plan can now carry a side
that one function walks past and the other never looks at.

**The shape a fix should take is already in the tree**, and it is why this is a structural item
rather than a defect: `cite_twin.routing` refuses to IMPORT if `TwinMode` declares a mode its
tables have not been told about. The same move here — refuse at import if `ids.SIDES` and
`BACKEND_FIELD_BY_SIDE` disagree — turns a silent ungating into a build failure. **It belongs
with the change that adds a third side**, because a guard written against a set that cannot
grow is a guard nobody can test.

Reported by `safety-auditor` on 2026-09-08 (S-05) and deliberately not fixed there.

### #38 — The generator cannot render 2.B
Closed: closed 2026-10-05 by [ADR-0070](adr/0070-the-physical-arm-is-cell-b-s-counterpart.md), which built ADR-0048 clause 2 — every generator site reads the side's own backend and the counterpart gets its own description and controller configuration; full text in git history (`git show f651155:docs/open-work.md`).

### #45 — ADR-0048 clause 3
Closed: closed at `7d7ac19`; ADR-0048 records clause 3 as `Accepted`; full text in git history (`git show 911ba08:docs/open-work.md`).

### #40 — `test_plan.py` on a paired checkout
Closed: closed by construction at `7d7ac19` and measured on 2026-09-08; full text in git history (`git show 911ba08:docs/open-work.md`).

### #62 — `cite_twin`'s two launch fixtures append a counterpart unconditionally
Closed: both fixtures read `cell_b`'s paired plan and append no side (ADR-0069); full text in git history (`git show 911ba08:docs/open-work.md`).

### #63 — The paired-plan document shape is hand-built in five places and tied to the generator in none
Five fixtures now spell out what a paired plan looks like: `cite_bringup/test/test_plan.py`'s
`_paired_document`, `test_pair.py`'s `_paired_plan`, `test_simulation_launch.py`'s `_paired`,
and `cite_twin`'s two from #62. Each appends the `sides:` entry and sets `counterpart_backend`
on every controller manager, and **not one of them is derived from, or checked against, the
generator that emits the real thing**.

**Why nothing catches the drift.** `tools/tests` asserts what the generator writes;
`cite_bringup`'s and `cite_twin`'s fixtures assert against a hand-written copy of it. Those are
two build units — host tooling and ROS packages — and neither suite can see the other's
fixtures, so the copy can fall behind the generator with every test green. **The next key a
paired zone acquires is five edits**, and the failure mode if one is missed is the worst
available: the suite stays green while a real generated plan is refused, or accepted for the
wrong shape.

**It is a P1 shape** — one value described in six places — and it became load-bearing rather
than merely untidy when `_every_declared_side_states_a_backend` landed on 2026-09-08: `load`
now refuses a paired document that omits `counterpart_backend`, so a hand-built paired document
is no longer just approximate, it is the thing under test. Two of the five were caught omitting
exactly that key by that refusal, which is the demonstration rather than the argument.

**Two directions, and neither is chosen here.** Either one shared helper that builds the paired
document once and the five import it — cheap, but it still asserts nothing about the generator
— or a contract test that **regenerates** a paired plan and loads it, which is the only shape
that closes the build-unit gap. The second needs a decision about where a test may regenerate
L0, which is not this item's to take.

Cross-references: #62, which is two of the five and a live defect on its own; #38, which is the
change that makes the generator sites per-side and will move this shape again.

Reported by review on 2026-09-08 (R-06) and filed rather than fixed.

### #65 — Nothing verifies that the plugin L0 declares is the plugin the description loads
Closed: closed 2026-10-05 by [ADR-0070](adr/0070-the-physical-arm-is-cell-b-s-counterpart.md) — `cite_description`'s `test_each_side_loads_its_declared_plugin.py` expands each side's description and asserts the plugin L0 declares; full text in git history (`git show f651155:docs/open-work.md`).

### #47 — Five L5 review findings, with their content
Recorded here because they were once sent as bare identifiers and an agent correctly refused to
guess.

- **R-13** — `twin_endpoints()` is a hand-maintained mirror of what L5 owns, and the disjointness
  test reads its set **from that function** rather than from the `create_publisher` /
  `create_service` / `ActionServer` calls. Removing an entry leaves 12/12 green because the
  checked set merely shrinks. Assert its length and each named constant, or derive it from the node.
- **R-15** — two nodes named `twin_boundary` in one process collide on the rosout publisher
  registry. `rcl` warns, and because `stop()` destroys the plant's node first, anything the
  counterpart logs during teardown never reaches `/rosout`; counterpart-context log lines also ride
  the plant's domain rosout publisher, which is defensible but undocumented.
- **R-16** — `TestTheAssetNamespaceIsReadOffTheModel` cannot distinguish a derivation from a
  composition: replacing `manager.node.rpartition` with a literal f-string leaves 12/12 green. The
  test pins agreement with today's plan, not the mechanism its docstring names.
- **R-17** — two untested boundaries in `divergence.py` (`<= pairing_window_s` and `> bound_s` both
  survive flipping), and term 3's comparison is one-sided, so a **negative** deficit — a side
  running above real time — passes any bound. Wants an `abs()` or an explicit note when the
  instrument lands.
- **R-18** — the latched-mode launch test reads `modes[0]` from a class-level accumulator and
  passes only because alphabetically-earlier tests spin before any transition publishes. Create a
  throwaway subscriber inside the test, so that a late joiner is what tests late joining.

---

### #66 — Nothing compares two zones' bounding boxes, and the overlap check is per zone
Removed — subject left the main tree (ADR-0069): L0 declares one zone; the validator gap returns the day a second zone is declared, so read the full text first then; full text in git history (`git show 911ba08:docs/open-work.md`).

### #67 — A cross-zone station reference passes validation and then skips its reach check in silence
Removed — subject left the main tree (ADR-0069): L0 declares one zone; the gap returns with a second zone; full text in git history (`git show 911ba08:docs/open-work.md`).

### #68 — The one-zone-at-a-time refusal is sound and incomplete, in two named ways
Removed — subject left the main tree (ADR-0069): L0 declares one zone; residual 2, the same zone twice, is #69; full text in git history (`git show 911ba08:docs/open-work.md`).

### #69 — A second bring-up from one checkout destroys the first, whatever zone either is
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

**Measured 3 of 3 on 2026-09-17 at `4f29761`, one run per configuration.** This is a defect in
its own right, it is **pre-existing**, and it needs neither a second zone nor
`cite_facility/occupancy.py` to happen — which is why it is filed apart from
[#68](#68--the-one-zone-at-a-time-refusal-is-sound-and-incomplete-in-two-named-ways) rather than
inside it.

**The mechanism.** A second `./scripts/sim` from the same checkout emits `configure` on
`/cite/facility/model_info/change_state` and `/cite/facility/topology_server/change_state`.
Those names are **facility-singular by design** (`docs/architecture/naming-and-namespaces.md`'s
reserved-name section; `ids.RESERVED_SCOPES` refuses any zone or asset called `facility`, `twin`
or `line`), so they resolve to the **incumbent's already-active** nodes, which are asked for a
transition they cannot make:

```
[WARN] [rcl_lifecycle]: No transition matching 1 found for current state active
RCLError: Failed to trigger lifecycle state machine transition: Transition is not registered.,
    at ./src/rcl_lifecycle.c:355
process has died [pid NN, exit code 1]
```

The incumbent then fills with `[tf2_buffer]: Detected jump back in time. Clearing TF buffer.`,
which is two simulators feeding one `/clock`.

**The three runs, and the third is the one that matters:**

| incumbent | intruder | refusal fired? | what happened to the incumbent |
|---|---|---|---|
| `cell_b` | `cell_a` | no | `model_info` + `topology_server` dead, exit 1 |
| `cell_b` | `cell_b` | no — excluded by design, #68 residual 2 | **all three** facility nodes dead; 24 x jump-back |
| `cell_a` | `cell_b` | **yes, verbatim and correct** | still died — 3 x `move_group` exit **-11**, whole launch shut down |

**So the damage is not about zones, and #68's refusal cannot prevent it.** The refusal is the
**8th** process the launch starts, at **+0.753 s**; ahead of it sit `gz` (1st), the scene's
`robot_state_publisher` on `/robot_description` (3rd) and `create` (4th). By the time the rule
answers, two simulators are up and two publishers are describing different robots on one
`/robot_description` — the collision `occupancy.py`'s own docstring predicts. The damage
**precedes** the refusal by construction, so hardening the rule in place cannot close this; only
something that runs before `gz` could.

**This amends #68's last line.** That item ends *"Nothing is known to be wrong today"*. Something
is: a concurrent bring-up destroys a running cell, reproducibly, and it did so in the one run
where the refusal worked perfectly.

**Nothing here attributes the `-11`.** That is the unattributed `move_group` teardown family
CLAUDE.md §2 records, and its appearance in the third run is recorded rather than explained.

Reproduce it:

```bash
./scripts/sim --headless --zone cell_b     # wait for CITE_SIDE_READY, then in a second shell:
./scripts/sim --headless --zone cell_a     # from the SAME checkout
grep -c "No transition matching" <the first shell's output>
```

**Three runs, one host, one session, nothing registered in advance. That is not a rate.**


### #74 — No deadman on the L5 command path: if the boundary dies, dispatched goals keep running on both sides
**[2026-10-05] Closed on the physical side by [ADR-0070](adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)**: `cite_hardware`'s deadman watches the boundary's `TwinHeartbeat` and, on its loss, stops the arm through the vendor's state, stops the track and cancels the arm and gripper goals — tested against fake vendor services only. **Still open on the plant**: a simulated side has no deadman, so if the boundary dies it finishes the goal it holds. The text below is as of 2026-10-02.

`cite_twin/twin_boundary.py`'s `_await_far_side_goals` states its own bound in its docstring —
**"No deadline, deliberately … The operator's cancel is the bound, and it reaches every side"** —
and that bound is exactly what stops existing when the boundary is the process that died. The
goals are already accepted by each side's own L3 server; nothing on either side is watching the
boundary, and an action server does not abort a goal because its client went away. So both arms
finish whatever they were sent.

[`docs/architecture/cross-cutting-safety.md`](architecture/cross-cutting-safety.md) requires the
opposite in as many words: *"When the commanding node dies, the network stalls, or messages simply
stop, motion **stops**. It does not continue on the last command. Every command path has a
deadman"* — and its own risk table carries **"No watchdog on a command path | High"**.

**The docstring's reasoning is not wrong and is why this is filed rather than patched.** ADR-0045
records what a wall-clock deadline supervising a simulation-time process cost this project, and L5
has two simulated clocks to be wrong about rather than one. A deadline is the wrong instrument; a
liveness contract between the boundary and each side is a different mechanism and a decision
nobody has taken. **Nothing here is evidence about motion**: the shipped pair is simulated on both
sides, and no goal has ever crossed the boundary into a cell that moves.

Reproduce it by reading the two documents against each other:

```bash
sed -n '/No deadline, deliberately/,/reported\./p' \
  workspace/src/cite_twin/cite_twin/twin_boundary.py
sed -n '/## Watchdog and communication loss/,/^## /p' docs/architecture/cross-cutting-safety.md
```

### #75 — A half-dispatched goal is reported as "no side was ever sent", and the mode interlock then sees nothing outstanding
`_dispatch` loops over the routed sides and calls `send_goal_async` on each in turn. If a **later**
side's `wait_for_server` times out after `SERVER_WAIT_S`, it returns a `ResultCode` — and the goal
already sent to the earlier side is neither cancelled nor waited on. `_run_dispatched_goal` then
aborts with `_uncommanded_result`, whose docstring says, in the tree today, *"Return the result for
a goal no side was ever sent … this goal commanded nothing, so it took no custody"*. One side is
running it. Under `MODE_VIRTUAL_LEAD` that side is the plant.

**The second half is the sharper one.** `_run_goal` registers the goal in `self._in_flight` and
pops it in a `finally`, so the abort clears it — and `set_mode`'s interlock
(`outstanding = sorted(self._in_flight.values())`) reads an empty map. **A mode transition would
therefore be accepted while that arm is still moving**, which is the one thing the interlock
exists to refuse.

`holding=false` on that result is the same statement: it is a type default asserted as a fact
about a goal that *was* dispatched.

**Nothing here is attributed and nothing has been observed firing** — it is read from the source
on 2026-09-18, on the shipped code. What would produce it is one side serving its L3 action and
the other not, which ADR-0047 makes an ordinary state: the two sides are brought up independently
and neither waits on the other.

```bash
sed -n '/def _dispatch/,/return sent/p' workspace/src/cite_twin/cite_twin/twin_boundary.py
sed -n '/def _uncommanded_result/,/return result/p' workspace/src/cite_twin/cite_twin/twin_boundary.py
```

### #76 — A stranded boundary outlives the supervisor and can serve a later run's goals
`scripts/_lib.sh` allocates a checkout's domains by parity, so they are **the same two on every
run from that checkout**. A boundary left behind — by the `Queue.put` deadlock `pair.py` records,
by a `SIGKILL` to the supervisor, by anything that skips the stop path — keeps its `SetMode`
server and its per-skill action servers advertised on both of those domains. The next
`./scripts/sim --pair` resolves the same two and brings up a second boundary beside it, and
**nothing detects the collision**: two action servers on one name is a legal ROS graph, a client
binds to whichever it discovers, and there is no equivalent of a `GZ_PARTITION` clash to make it
visible.

**This is the orphan this repository already knows the cost of, one layer up** — `pair.py`'s
`_sweep` exists for exactly the Gazebo version of it — and the difference is that an orphaned
`gz sim` holds a transport while an orphaned boundary **commands arms**.

Reproduce it:

```bash
./scripts/sim --pair --zone <a paired zone>    # then SIGKILL the supervisor, not Ctrl-C
pgrep -af twin_boundary.py                     # still there
./scripts/sim --pair --zone <the same zone>    # a second one, on the same two domains
```

**Not observed; read from the allocation and the stop path on 2026-09-18.**

### #77 — `--pair --line` puts three commanders on the same arms
Closed: moved with the line to snapshot 01; `line:=true` is refused as an unknown launch argument (ADR-0069); full text in git history (`git show 911ba08:docs/open-work.md`).

### #78 — The readiness token proves the plant's executor is running, not that the pair is complete
`twin_boundary` announces from a timer callback on **`self._plant`'s** executor, which is the
right fact for what it claims — the endpoints are being served rather than merely created. What it
does not cover is the **counterpart**. `SideContext` spins each side on its own thread and records
a spin-thread failure in `self.failure`; the only thing that reads it is the `observing` property,
consumed at one place — `message.counterpart_observed`, a field of `DivergenceMetrics`, whose
`valid` is **false for every sample by construction** (ADR-0049 sets no `DEFICIT_BOUND_S`).

So a counterpart context that died on its way up leaves the boundary announcing readiness, the
pair supervisor reporting the pair complete, and the failure recorded in a field nothing gates on.

**Read from the source on 2026-09-18; not observed.** What would settle whether it matters is a
run in which a counterpart's spin thread fails, and no such run exists.

```bash
grep -n "self.failure" workspace/src/cite_twin/cite_twin/boundary.py
grep -rn "observing" workspace/src/cite_twin/cite_twin/twin_boundary.py
```

### #79 — Both side contexts name their node `twin_boundary`, so one side's log cannot be attributed
`SideContext.__init__` defaults `node_name` to `NODE_NAME`, which is `"twin_boundary"`, and the
boundary builds one context per side. Two nodes of one name in one process: `rcl.logging_rosout`
warns on every start, and every log line either side emits carries the same logger name, so **a
message cannot be attributed to the side that produced it** — in the one component whose whole job
is to hold endpoints in two domains at once.

**Observed 5 times** on paired bring-ups by a `tester` on 2026-09-18 — one machine, counted from
that run's own output, and it is a count of warnings and not a rate.

The node name is the same on both sides **on purpose** at the graph level: ADR-0044 requires
identical names per side, and the two nodes are on different domains where the collision is
invisible. What collides is the process-global logger, which is not a domain-scoped thing. So the
fix is not "rename a side's node", and that is why this is filed rather than patched.

```bash
grep -n "NODE_NAME\|node_name" workspace/src/cite_twin/cite_twin/boundary.py
```

### #71 — The refusals and the verdict are tested; the join between them is not
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

`./scripts/scenario --zone` gained nine shell-gate cases on 2026-09-17 covering its **refusals**
(`--zone` swallowing the next token, `--zone=` empty), and `scenario_verdict` is covered on
synthetic reports including the advisory branch. **Nothing asserts that a well-formed
`./scripts/scenario <name> --zone X --teardown-advisory` actually binds
`TEARDOWN_POLICY=advisory`.** The nearest self-test greps the script for the literal default
`TEARDOWN_POLICY="blocking"`, which pins the default and not the parse.

Why it is worth a line: the combination was **impossible** until that date — the `--zone` loop
consumed the following flag, so a caller who asked for an advisory teardown silently got a gating
one — and a run that passes cannot demonstrate the fix, because `scripts/scenario` exits at the
`launch_test` success branch before `scenario_verdict` is ever called. The only observation that
would show it is a run whose teardown fails.

Named by a `tester` in the round that closed the defect around it, and **deliberately not fixed
there**: one shell-gate case does not warrant a fix round of its own. It folds into the next round
that touches `scripts/scenario`.

**One trigger would change that judgement.** The gap bites only a caller who passes `--zone`
**and** `--teardown-advisory` together, and CI today passes `--teardown-advisory` alone with no
`--zone`. If a periodic `./scripts/scenario bringup --zone cell_a` job is ever added — which is
exactly [ADR-0056](adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md)'s
named mitigation for the showcase it stops driving — the untested join becomes load-bearing on a
gating path, and it should be closed **before** that job lands rather than after it has been
trusted once. Whoever adds that job should trip over this sentence.

### #72 — `frame_server` configures and never activates, because a lifecycle transition event is dropped
**Root cause established 2026-09-17 by a `debugger`, and it is not this project's code.**
`simulation.launch.py`'s `_managed` triggers activation on
`OnStateTransition(configuring -> inactive)`, and `launch_ros` derives that launch event from a
**subscription to `/<node>/transition_event`** (`launch_ros/utilities/lifecycle_event_manager.py`,
`setup_lifecycle_manager`). Both endpoints were read off a live stalled cell and are **RELIABLE +
VOLATILE**. Reliable is a promise to **matched** subscribers only, so when the node's publisher
has not yet matched the launch node's subscription at the instant `on_configure` returns, the
message is dropped and never re-sent. **This is CLAUDE.md §10's own named silent failure**, this
time inside `launch_ros`'s lifecycle plumbing rather than in ours — the same class that once cost
this project a belt setpoint that was never delivered.

**Proof rather than a story.** In a stalled trial the node was probed from outside and was in
`inactive`, so configure had succeeded. Driving `cleanup` and `configure` again from a third
process 9.7 s later made the launch's **same, still-registered** handler fire, and the node logged
`published 9 static transform(s)` immediately. Same handler, same node, same transition —
delivered the second time, dropped the first.

**Not ours**, established without a `main` build: `git diff main...HEAD -- simulation.launch.py`
changes only the `zone` `DeclareLaunchArgument`, so `_managed` is byte-identical to `main`'s; the
only `frame_server` change is `require_zone`, a string check ahead of `static_transforms` that
cannot touch DDS discovery; and the stall reproduces in a **three-node scratchpad harness** with
no Gazebo, no MoveIt and nothing zone-specific.

**What it costs when it fires.** No TF is published, `move_group` reports
`Tf has two or more unconnected trees` and `Unknown frame: cite_world`, the planning-scene diff is
refused, and the launch dies with `BRING-UP FAILED before the skill servers` — **a diagnosis that
points at the model and is wrong**. That misdirection is the expensive part.

**Observed 3 of 11 scenario launches** across two sessions and two scenarios — `bringup` 2 of 4 at
`4f29761`, `pick_and_place` 1 of 2 at `e726384`. **One host, a handful of runs, nothing registered
in advance: not a rate.**

**The structural half is separately fixable and is the cheaper half.** `_managed`'s four `_refuses`
handlers all cover a transition **returning FAILURE**; a **missed transition event** — node
healthy, sitting in `inactive`, nothing ever told to it again — is covered by nothing. That is
what lets bring-up continue for ten seconds and then fail in another layer. **A fix must not be a
timeout**: waiting a guessed interval to decide a node is stuck is the timing guess CLAUDE.md §4
forbids, and this item is not an invitation to add one.

**Distinguish it from [#69](#69--a-second-bring-up-from-one-checkout-destroys-the-first-whatever-zone-either-is)**, which looks superficially similar and is not: there a node that is already
`active` is told to configure and dies loudly on `No transition matching 1 found for current state
active`. Here configure **succeeds** and the silence is the whole defect.


**Trials, from the debugger's final report and stated as counts rather than as a rate.** Real
`./scripts/scenario bringup` on `cell_b`: 2 stalls in 4. Harness, `cell_b`, no added load: 2 in 35.
Harness, `cell_b`, plus twelve idle nodes of discovery load: 4 in 45. Harness, **`cell_a`**, plus
twelve idle nodes: 1 in 12 — which is the configuration `main` ships and is why this is filed as
pre-existing rather than as a property of the new cell. **About 7 stalls in about 92 harness
trials, on one host, in one afternoon, with a `tester` running scenarios on the same machine for
part of it. Not a rate.**

**THOSE HARNESS FIGURES ARE LOWER BOUNDS, BECAUSE THE INSTRUMENT RESCUED WHAT IT WAS COUNTING.**
Reported by the `tester` who re-ran this on 2026-09-17 and **not re-derived** here — the harness
is not in the tree, it lives in an untracked `REPRO/` directory on that host. `run3.sh`'s probe
re-drives `cleanup` + `configure` at **6 s** into each trial. That second request is exactly the
intervention the debugger's proof above used to un-stall a node: it makes the launch's still
registered handler fire and the node publish. The trial's own success grep then matches, and **a
stalled trial is counted as a pass.** So 2/35 and 4/45 are floors on that rig, not measurements
of the stall's frequency, and **anyone comparing a post-fix arm against them is comparing against
a number taken with a different instrument.** The 2026-09-17 re-run dropped the probe, which can
only raise sensitivity, and the control arm still produced **0/35 unloaded and 1/45 loaded** —
barely reproducing at all. That is why ADR-0058 clause 1 is **not** closed by 0 of 80 driven
trials: a driven arm cannot be distinguished from a control that does not reproduce.

**Two consequences for whoever re-runs clause 1.** The harness's `repro.launch.py` carries its
own private copy of `_managed` and imports nothing from `simulation.launch.py`, so after ADR-0058
it drives the **old** shape verbatim and is a control rather than a reproduction of current
`main`. And the first thing that campaign needs is a control arm that reproduces at a workable
rate — **without** the 6 s probe — because until one exists there is nothing for a driven arm to
be better than.

**Load is NOT established as the trigger**, and the tempting reading is wrong: time from launch
start to `configured` does not separate the outcomes — failures at **0.508 s** and **0.597 s**
against passes at **0.480 / 0.489 / 0.499 / 0.785 s**. A *faster* node is not what stalls, and the
loaded and unloaded arms are indistinguishable at this n.

**The four refusals are droppable too.** `_managed`'s `_refuses` handlers are driven by the **same
topic**, so a transition that *fails* can be lost exactly as one that succeeds. Nothing covers
either today.

**One assumption is written down as fact elsewhere and is false.**
`cite_bringup/readiness_witness.py`'s `endpoints()` docstring states that everything before it is
*"already gated on a real completion event — a spawner exiting, **a lifecycle transition**, the
planning-scene loader finishing."* That clause is the assumption this defect lives inside, and it
should be corrected by whoever fixes this.

**Fix direction, from the debugger, and the first line matters most: it is not "wait longer".**
(A) Stop keying activation and the four refusals on a volatile broadcast — have the launch's own
node **call `change_state` and read the response**, then **confirm with an idempotent, re-askable
`get_state`**, chaining configure → activate on answers rather than on events. The reply can be
dropped too (a `tester` run shows it), which is why the confirmation and not the response is the
gate. The legal precedent is already in the tree: `readiness_witness.py`'s `_SLICE_S` comment sets
the rule that a ceiling's expiry must be a **failure naming what never answered**, never a signal
to proceed. **Do not add a sleep and do not widen any existing ceiling.**
(B) Separable and cheaper: nothing downstream of `_facility()` may start until each managed node is
**observed** `active`. These runs would then have failed at ~1 s naming `frame_server`, instead of
at ~10 s naming frames and the planning scene.
(C) Cheapest: have `tests/scenarios/bringup.py` assert each managed facility node is `active`. It
would not prevent the stall but would name it.

**A fix must not break** the four `_refuses` diagnoses, the launch description shared
byte-identically by all three scenarios, or `--pair`'s readiness-token chain.

### #73 — `skill_server` and `move_group` hung through `SIGTERM` at teardown and were `SIGKILL`ed
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

One observation, `continuous_line` against `cell_b` on 2026-09-17, in a run whose **cycle passed
3 of 3 work-pieces** and whose post-shutdown check then failed:

```
process[skill_server-15] failed to terminate '105.0' seconds after receiving 'SIGTERM',
    escalating to 'SIGKILL'
process[move_group-11] failed to terminate '105.0' seconds after receiving 'SIGTERM',
    escalating to 'SIGKILL'
AssertionError: -9 not found in [0, 130, -11]
```

**The exemption behaved correctly and was not touched.** `UPSTREAM_TEARDOWN_SEGFAULT` allows
`-11` for `move_group` alone, so the `-9` was **reported rather than absorbed** — which is the
whole point of keeping that allowance narrow. **No exemption may be widened to cover this.**

**It is a different phenomenon from the two this project already records**, and the resemblance is
only the minus sign. CLAUDE.md §2's teardown family is a **segfault** family (`-11`, and
`parameter_bridge` on `-6`); the `gz -9` recorded there is an unclassified `SIGKILL` at teardown.
This is a **hang, then a supervisor-issued `SIGKILL` after a stated 105 s** — a process that did
not respond to `SIGTERM` at all, which is a liveness failure and not a crash.

**Nothing here attributes it.** Worth one line for whoever picks it up: the base carries
`f11f453`, *"ends an in-flight `skill_server` goal in a pre-shutdown callback"*, which is the same
process in the same phase. **Whether that is related is unestablished and was not chased.**

The second run of the same scenario at the same commit tore down cleanly, so it is intermittent
rather than a systematic regression. **One occurrence, one host, nothing registered in advance.**


### #91 — The program client has L4's job and lives in a composition package that L5 imports
Recorded 2026-10-02. `cite_bringup.program` runs the real robot's program through the L5
boundary, so it sits **above** L5 and does what L4 is for — it decides what work is done
([`architecture/README.md`](architecture/README.md)'s diagram). There is no L4 package
([ADR-0069](adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)), so it lives in
`cite_bringup`, which is **also** a lower-layer library `cite_twin` imports (`cite_bringup.plan`,
`cite_bringup.readiness`). **Correct today**: nothing under `cite_bringup` imports `cite_twin`
(`grep -rn cite_twin workspace/src/cite_bringup --include=*.py | grep import` returns nothing),
so no dependency points upward. **Wrong on the next change**: the first time the program client
needs a `cite_twin` symbol, the import is upward within one package and no package boundary
catches it. **Done means** `cite_bringup/program/` moves to an L4 package of its own — it is the
first candidate for one ([`architecture/repository-layout.md`](architecture/repository-layout.md))
— by a decision recorded in an ADR.

### #92 — The physical side's deadman timeout is declared, not measured
`model/facility/zones.yaml`'s `twin.physical_side` sets the values that bound how long the
physical arm may run on after the twin boundary dies
([ADR-0070](adr/0070-the-physical-arm-is-cell-b-s-counterpart.md) item 5): the deadman
timeout, tick, call deadline and state age. The validator holds their relations to each other.
Nothing measures:
- the heartbeat's real delivery on this host;
- the trip-to-stop latency through the vendor's single executor under poll load;
- the vendor's STOP-to-standstill time.

Done means a campaign under `docs/measurements/` with thresholds written before the first
trial.

### #93 — Hardware behaviour the physical side depends on and nothing in software can establish
Each item below is a bench question for the physical xArm 5, its track and its gripper. Each
must be answered before the physical counterpart is trusted beyond a supervised run at reduced
speed ([ADR-0070](adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)).
- What the controller does when its TCP stream ends in servo mode, and on a large
  `set_servo_angle_j` step.
- Whether the hardware E-stop also cuts the linear track's drive.
- What the gripper does with a held part on E-stop or power loss. This is a choice to be made
  and recorded, not only observed.
- Whether the track's segmented moves blend or stutter.
- Whether the vendor driver parameter block reaches `ufactory_driver`, so that exactly the
  allowed services appear.
- Whether the hold gate's STOP is acknowledged, and how spawner activation interleaves with
  the vendor's own controller switching while the arm is held.
- Whether the arm trajectory controller's action server and `controller_state` behave as
  `hardware.launch.py`'s witness and the boundary's readiness gate assume.
- Whether the operator prompt reads Enter through the container's stdin.
- Whether HEALTHY → enable → controllers active completes within the program's readiness
  ceiling over the lab's Wi-Fi.

### #94 — The vendor's gripper action is reachable without the deadman's gate
The xArm driver creates `<prefix>xarm_gripper/gripper_action` unconditionally
(`xarm_api/src/xarm_driver.cpp`), outside the `services` allow-list. Any client on the physical
side's domain can move the jaws while the deadman is tripped. Closing it needs either a patch
file under `external/patches/` or access control at the domain level. It is stated as a
residual in `workspace/src/cite_hardware/README.md`.

## 4. Instrument honesty

Every item here misled this project at least once, including in the session that wrote this file.


### #70 — `./scripts/test` failed all 11 packages twice while another container was up, and the mechanism is NOT established
**What was observed, three times on 2026-09-17.** Two consecutive `./scripts/test` runs exited 1
with **123** occurrences of

```
ModuleNotFoundError: No module named 'ament_cmake_test'
```

from `/opt/ros/jazzy/share/ament_cmake_test/cmake/run_test.py`, failing **all eleven** packages —
**including the `flake8`, `copyright` and `pep257` meta-tests, so none of our tests executed at
all.** The host halves were unaffected and identical in both runs (`144` shell gate,
`1623 passed, 1 skipped`), so only the per-package half is involved. A third run, after the one
change below, was clean: `1415 tests, 0 errors, 0 failures, 56 skipped`, zero `ModuleNotFoundError`.

**The one thing that changed between the failures and the pass**: an **orphaned container from
another session's debugging harness** — running twelve idle load nodes on `ROS_DOMAIN_ID=91`, up
13 minutes, outliving the agent that started it — was stopped. Nothing else was touched, and the
re-run began immediately.

**What is ruled out, by measurement rather than by argument.**
- **The `compose exec` path did not fire.** `scripts/_lib.sh:1036` keys on
  `compose ps --services --status running` and `grep -qx "$service"`. That command was measured
  **empty immediately before both failing runs**, while `docker ps` showed the orphan — because a
  `compose run` one-off is not listed by `--services`. So `exec_in_container` took the
  `compose run` branch both times.
- **A missing environment in a fresh container is ruled out.** `./scripts/enter dev printenv
  PYTHONPATH` returns the full path including `/opt/ros/jazzy/lib/python3.12/site-packages`, and
  `import ament_cmake_test` succeeds there — **with and without a login shell**, so the entrypoint
  is doing its job.

**So the correlation is strong and the mechanism is unknown.** Two containers of this project
share the `cite-build` and `cite-install` volumes, which is the direction worth looking first; that
is a hypothesis and nothing here tests it. **Three observations, one host, one afternoon, nothing
registered in advance. That is not a rate and it is not a cause.**

**The operational rule survives whatever the mechanism turns out to be**, and it is the reason this
sits under instrument honesty: **confirm `docker ps` is empty before taking a `./scripts/test`
figure, and say so when quoting one.** No `./scripts/test` figure recorded anywhere in this
repository states whether another container was up when it was taken.

**This entry was wrong when first written, and how it got wrong is the point.** It was filed
naming `compose exec` as the cause, on a `fixer`'s report, **without verifying it** — and the
verification took two commands and overturned it. `.claude/orchestration.md` rule 5 says not to
trust a report at face value; this is what it costs when you do.

### #64 — `cite_tools.cli --help` crashes in the host virtualenv: `typer` is pinned and `click` is not
`.venv/bin/python -m cite_tools.cli --help` exits **1** with
`TypeError: Parameter.make_metavar() missing 1 required positional argument: 'ctx'`, raised
inside `typer/rich_utils.py:369`. So does `--help` on any subcommand. The **commands themselves
work** — `… cli validate` exits 0 — and every `./scripts/*` entry point works, which is why this
had gone unnoticed: nothing in the quality gate asks the CLI to describe itself.

**Cause, read from the pins rather than guessed.** `requirements/tools.txt:32` pins
`typer==0.13.1`; **`click` is not pinned at all**, and the resolved version in this virtualenv is
**8.5.0**, which changed `Parameter.make_metavar()` to require a `ctx`. `typer` 0.13.1 calls it
with none. Neither package is a ROS dependency, so this is host tooling and `requirements/` is
its only home (`requirements/README.md`).

**Not this branch's, and measured so.** It reproduces at base `e18251e`, and
`git diff e18251e -- requirements/` is **empty** on `feat/hosted-by-derived`, so nothing here
moved a pin. It is an environment item, filed rather than chased.

**What it costs and what it does not.** It costs a reader the CLI's own documentation, which is
the instrument anyone reaches for first when `./scripts/*` is not the right door. It costs no
gate: the container has neither `typer` nor `cite_tools` installed, so CI never runs this path
at all — which is also why a fix has to be verified on the host and cannot be verified by
`./scripts/test`.

**The obvious direction is to pin `click` beside `typer`**, at a version 0.13.1 accepts, or to
move `typer` forward to one that accepts click 8.5. Which of the two is a dependency decision
and is not taken here; `./scripts/audit-deps` and `requirements/README.md` are where it belongs.

Reported by `tester` on 2026-09-08 (T-02) and re-reproduced the same day by the change that
files it.

### #52 — The verdict line and CI teardown
Withdrawn: this item was wrong in both of its claims; `scripts/scenario` distinguishes three verdict states; full text in git history (`git show 911ba08:docs/open-work.md`).

### #53 — MARKED 2026-09-01: two ADRs asserted `cite_twin` does not exist, inside verification tables marked "still true"
`docs/adr/0041-*.md` lines 31, 66 and 139 — line 139 inside a **verification table** marked
*"still true"*. `docs/adr/0044-*.md` line 40, and line 125's verification table, same marker.

All false as current state: `workspace/src/cite_twin/package.xml` is on disk, `twin_boundary.py`
serves `SetMode`, and `routing.py` keys on `MODE_VIRTUAL_LEAD`.

**Worse than ordinary prose drift:** a verification-table row saying "still true" is a claim that
someone re-checked it, and those tables exist so a reader can trust them without re-deriving. Two
were lying in exactly the place this project put its trust.

**Resolved with `Overtaken`, not `Corrected`, and the choice is the finding.** `cite_twin` landed
at `7ac064d` on **2026-08-31**; ADR-0041's rows were written on 2026-08-29 and 2026-08-30 and
ADR-0044's on 2026-08-30, so **every one of them was true when written**. Per
[`docs/adr/README.md`](adr/README.md)'s in-place marker table, that is `Overtaken` — *"right when
written, and events since made it false, with nobody wrong"* — and not `Corrected`, which asserts
the sentence was wrong when written and requires a Correction section. ADR-0050's precedent row
(`` `cite_twin` does not exist | **False.** It exists ``) is a **Correction** because there the
record's own status block was falsified by the branch implementing that record. Different
situation, different marker. Five markers added; no status value, index row or Correction section
changed, because nothing was measured false.

**The question this leaves open, and it is not closed by fixing five rows:** how many other
verification-table rows across the 52 records say "still true" about something that has since
moved? A row verified once and never re-read is a count with a date on it. **Nothing checks
this**, and a survey on 2026-09-01 covered only the two records this item names.

### #57 — ADR-0045's gripper-deadline launch rig passes with no controller ever activated
**Evidence taken on `cell_a`/removed scenarios; re-verify on `cell_b`.**

`workspace/src/cite_bringup/test/test_gripper_deadline_launch.py` starts a real
`controller_manager` and a `spawner` for the three real generated controllers (`:284-290`). In the
runs observed, the spawner's `load_controller` call timed out three times about 10 s apart, the
manager meanwhile **did** load the controller, the retry then failed with *"A controller named
'arm_1_joint_state_broadcaster' was already loaded"*, the spawner logged
`[FATAL] Failed loading controller arm_1_joint_state_broadcaster` and **died with exit code 1** —
and the test reported `Passed`. **Zero** `Configuring controller` or `Activating controller`
events appear anywhere in the run, so no controller was ever active.

**Why nothing noticed, established by grep and not inferred.**
`grep -n "assertExitCodes\|proc_info\|post_shutdown\|TestCleanShutdown"` on that file returns
**nothing**; the same grep on its sibling `test_abort_classification_launch.py` returns `:784`
`@launch_testing.post_shutdown_test()`, `:785` `class TestCleanShutdown` and `:806`
`def test_processes_exit_cleanly(self, proc_info)`. Same package, same rig pattern, one asserts
process exits and the other does not.

**Not one machine and not one branch.** Observed twice locally on 2026-09-01 and in **green** CI
run `33501707588` at `e51238e` on `main` (`gh run view 33501707588 --log | grep "Failed loading
controller"`, and the test's own line `Test #10: test_test_gripper_deadline_launch.py … Passed`).

**The rig's own assertions are not invalidated.** They concern the skill server's deadline against
a *fake* gripper action server outside the arm's namespace (`:131-135`), which does not depend on
those controllers — which is exactly why it passes. **But it is not the rig its docstring
describes**: `:83-84` says that above the fake gripper "everything is production: the generated
description, the generated controller configuration", and in these runs the generated controller
configuration brought up nothing. The rig's own comment at `:132-133` says the fake sits outside
the arm's namespace *because* "the real `arm_1_gripper_controller` is still spawned by this rig" —
so the design intends those controllers to be live, and observed runs are not.

**The cause is NOT established.** A candidate — the manager runs `use_sim_time: true` (the run
logs *"Using ROS clock for triggering controller manager cycles"*) while `/clock` is published
only from the test class's setup, after `ReadyToTest`, so the spawner's service waits expire
before any clock exists — is **inferred and unmeasured**, and must not be written up as the cause.
The rig sets `--controller-manager-timeout` from `STARTUP_CEILING_S = 240.0`; the ~10 s retry
interval is a **different** timeout the rig does not set, and which of the two matters here is
unverified.

**Owed:** its own investigation, and then a decision about whether the rig should assert its
spawner. Belongs beside #19 and #25 — this is part of ADR-0045's mechanism evidence, and both
ADR-0045 and ADR-0046 are deliberately `Proposed`.

### #58 — The premise behind ADR-0040's guard widening is checked by nothing
ADR-0040's 2026-09-01 amendment permits the test-only fixture's name anywhere under
`docs/measurements/`, on the argument that nothing invokes or installs anything in that tree.
**The argument is true today** — verified independently by three parties on 2026-09-01 — and
**no test fails if it stops being true.** A CI step, an install rule or a launch file that later
reaches into `docs/measurements/` would silently widen the fixture's reachable surface, and the
guard that was widened on this premise would not notice.

A guard turning the premise into a check is cheap and was deliberately deferred out of the change
that created the need for it. **This is a small code item, not a documentation one.**

### #56 — Charter §7 lists four packages that do not exist, and §8 does not know `cite_twin` landed
**Parts 1 and 2 are resolved by charter v1.17 (2026-10-02)**: §8's Phase 2.A now states what
exists, including the L5 twin boundary and what starts it, and §7's tree moved to
[`architecture/repository-layout.md`](architecture/repository-layout.md). **Part 3 remains
open.**

Reported by the charter v1.12 agent and **not edited** — the owner's authorization covered two
corrections and not these. Each needs its own owner decision under CLAUDE.md §12.

1. **§8's Phase 2.A blockquotes predate `cite_twin`.** They still describe 2.A's L5 deliverable
   with no marker that the boundary process exists. After v1.12, §14's marked v1.9 row is the
   **only** place in the charter that mentions the mode server, so a reader of §8 alone cannot tell
   that L5's package is in the tree. The correction is the same two-sided sentence the v1.9 marker
   carries: the boundary exists, **and** nothing starts it, it refuses on a `single` zone, `valid`
   is false in every sample it can produce, and ADR-0050 is `Proposed`.
2. **§7 says four packages exist that do not.** Its preamble states *"Directories that carry no
   marker exist now"*, and `cite_hardware/`, `cite_control/`, `cite_telemetry/` and `cite_safety/`
   carry no marker and are not on disk. The parent carries `(Phase 1.B)`, so a generous reading is
   that the marker is inherited — but Phase 1.B is closed and these are Phase 2 and Phase 4
   packages, which makes the inheritance reading wrong rather than the entries.
3. **§8's Phase 2 scope sentence** promises *"The twin monitor publishing live divergence
   metrics"* with no status note, while `DivergenceMetrics.valid` is false in every sample the
   shipped package can produce.

**When editing the charter, the five exit criteria must stay byte-identical.** Their combined
sha256 over `grep "^> \*\*Exit criterion:\*\*" what-we-are-doing.md` is
`c2de0d872adfca9ea16fd8f899e5a1f554715049a4f013341e33bce9d0458454`, verified before and after
v1.12. Check it before and after any charter change.

### #59 — The robot description reads back as zero characters, and it has now cost three campaigns
**Three campaign harnesses have lost data to the same read**, and a fourth author will meet it
too. The read is `ros2 param get <namespace>/description_publisher robot_description` against the
running cell — the read every recent harness uses to establish **which geometry the cell it is
measuring was actually built from**, because a generated file on disk is not evidence about a
running node.

- **2026-09-04**, [`waypoint-clearance`](measurements/2026-09-04-waypoint-clearance/ANALYSIS.md):
  eight of the twenty-seven arm-captures returned zero characters. One arm failed six of six
  across the two cycle scenarios while every `bringup` capture read all three arms cleanly; one
  scenario lost **every** row it contributed, and the campaign lost half its sample.
- **2026-09-03**, [`stall-band-flip`](measurements/2026-09-03-stall-band-flip/ANALYSIS.md): one
  trial of eighteen returned zero characters, and the validity rule's discard granularity took the
  other seventeen with it — see **#36**, where the consequence is recorded.
- **A read-back failure of a similar shape is recorded once more**, in
  [`scenario-ceilings`](measurements/2026-09-02-scenario-ceilings/ANALYSIS.md)'s deviation 1: a
  description read returning a short string carrying no hull reference on five runs of
  twenty-eight. **Whether it is the same defect is unestablished** and nothing here attributes it.

**Nothing is attributed.** Every one of those readings is a **read failure** and is recorded as
such: the 2026-09-04 harnesses keep "the rig could not read" and "the cell was built wrongly" in
separate fields precisely so the two cannot be confused, and **no claim is made anywhere that a
cell was built from the wrong geometry**. Candidate causes — a
`description_publisher` answering slowly while three `move_group` processes are up, a shared
re-read timer, something else — are named in the campaigns and **were not chased**.

**Why it costs more than a flaky read looks like it should.** The read-back is not a data point;
it is what makes every *other* data point admissible. A failed read therefore does not degrade a
figure, it **deletes** rows — at whatever granularity the campaign's discard rule uses, which in
one case was eighteen sound trials for one bad read. A harness author who treats this as unlikely
will lose the block that matters.

**What would settle it is not known and is not prescribed here.** No fix is proposed, no rule is
proposed and no campaign is proposed; the read is a harness-side instrument in frozen campaign
directories, and **whether anything in `workspace/` depends on the same read in the same way is
unexamined**.

### #95 — `bringup` intermittently loses the MoveTo goal response
`./scripts/scenario bringup` failed its cycle assertion in 2 of 6 runs on
`feat/real-counterpart` (2026-10-05), with the skill server logging *"Failed to send goal
response … (timeout): client will not receive response"*. It failed in 0 of 2 runs on
`2701729` taken alongside.

That is too few runs to attribute. The branch changes neither `tests/scenarios/` nor
`cite_skills`, and the mechanism is the one already recorded by
[ADR-0059](adr/0059-pair-cell-b-and-leave-cell-a-single.md) and #26.

Later the same day (2026-10-05), on `acee7bb`, the defect did not appear in 6 runs on the
branch and 6 on `2701729`, interleaved with nothing else running, nor in the branch's 2 CI-style
runs. That is an observation, not a campaign: n is small, and it neither attributes nor fixes
anything.

Done means a campaign that compares enough runs of both commits, under recorded load, to tell
a rate from noise. No ceiling is to be widened for it.

### #96 — `move_group` exits on SIGSEGV at every scenario teardown
Seen in every `bringup` and `program_cycle` run on both `2701729` and `feat/real-counterpart`
(2026-10-05). It exits with -11 in `rclcpp::CallbackGroup::~CallbackGroup()` while `MoveItCpp`
is destroyed.

`test_nothing_of_ours_exited_badly` still passes, because `move_group` is not counted as one
of ours. On the physical side, `move_group` exiting brings the whole side down by design, so
there the crash only ever happens at teardown.

### #97 — Low residuals left by the final Phase 2.B review (2026-10-05)
Each fails safe; none blocks the first supervised motion. From the last reviewer and
safety-auditor passes on `feat/real-counterpart`:
- A track step whose plant carriage is already at the target treats an UNHEARD physical
  carriage like an AWAY one and fails at once with "home it" (`program/cell.py`, `track`).
  It should wait with `await_heard` within the step's ceiling, then word the refusal by reason.
- `TrackArrived.Response.ARRIVED` is 0, so a response with `reason` left unset reads as
  arrived; `carriage_verdict` checks `reason` only. Every server path sets it today.
- `test_physical_readiness.py` asserts the absence of a string production no longer emits.
- The `_speed_epoch` bump on re-activation in the track adapter has no test.
- The program reads the twin's mode once before waiting up to the readiness ceiling for the
  carriage; a second `SetMode` client in that window is not seen. The operating precondition
  is that the program is the only `SetMode` client.

---

## 5. The one large composite item

### #6 — Phase 1.E: documentation, quality gates, legacy retirement
Most of this is done or overtaken; what remains is genuinely open and worth naming separately
rather than leaving inside a stage ticket.

**Still open:**
- **Walk `docs/onboarding/getting-started.md` from a genuinely clean clone** and fix whatever does
  not work. That walk is the Phase 1 exit criterion in miniature, and it has already proved its
  point twice — `./scripts/build` failed from a clean checkout for weeks because two packages
  installed an untracked empty `include/`, and `bootstrap` once silently skipped a patch in a
  worktree. The 2026-08-27 walk stopped at `lint` **without launching the cell**.
- **Interface reference generated** from the `.msg`/`.srv`/`.action` files; per-package READMEs.
- **`resolve.py:155` and `moveit.py:91` hardcode `"drive_joint"`** instead of reading
  `drive_joint_suffix` — a P1 duplication.
- **ADR-0022's correction cites candidate-comparison numbers that live only in an agent
  transcript**, not in a committed file. P8 says a fidelity claim is backed by a published metric.
- **The 0.0005 timestep block of the grasp-plane campaign reached 4 of 20 planned trials** before a
  session limit. Committed as data, not as a result.

**Overtaken since this was written:** the Pilz pipeline is implemented; convex hulls are
implemented, promoted and shipped; `_collision_is_not_a_visual_mesh`'s vendor blindness is closed
by ADR-0028 decision 4; L0 now carries a work-piece type with dimensions. **Re-read each line
before acting on it.**

---

## What is NOT in this list, and is still owed

- **No vendor-described link's mass or inertia tensor is validated by anything.** The validator
  reads `description.body`; vendor-described types leave it unset. A 2026-08-31 audit read all 27
  links by hand and found 0 violations — one pass by one reader, not a check. This is the same
  structural blindness ADR-0028 closed for collision geometry, still open for inertia, and **it has
  no record of its own.**
- **The self-collision matrix is the vendor's, computed against vendor geometry**, now paired with
  hull geometry. Sized rather than closed: 44 of 78 geometry-bearing pairs are disabled and
  unaudited; four interpenetrate as hulls where the vendor metal is 1.57–31.77 mm apart. No runtime
  consequence today — MoveIt's ACM excludes them and Gazebo computes no same-model self-contacts —
  but the shipped configuration now depends on the vendor's disable list to hide it. ADR-0028's
  named interim check was **considered and declined**, with reasoning, in its 2026-09-01 amendment.
- **Enabling `<self_collide>` would jam the gripper.** On hull geometry `left_inner_knuckle` and
  `left_outer_knuckle` interpenetrate at every one of 200 drive angles. Guarded in the generator;
  the guard is the only thing standing between an ordinary fidelity improvement and a gripper that
  cannot close.
- **Five of the minimal fixture's six committed JSON Schema exports are stale, and no test and no
  script reads them.** `tools/tests/fixtures/minimal/schema/` is copied into every `minimal_model`
  run and never opened: `cite_tools.model.loader` prunes any path with a `schema` component from
  its walk, and `export.differences` is called only on `model/schema` by the CLI, which no test
  invokes with the fixture. **They are reachable, and this entry said "nothing can read them"
  until 2026-09-09**: `cite-model schema --model tools/tests/fixtures/minimal` is a shipped,
  read-only command and it opens all six. The counts are
  `git ls-tree -r --name-only HEAD tools/tests/fixtures/minimal/schema/ | wc -l` → **6**, and that
  `cite-model schema` command → **5** `error` lines; `flow.schema.json` is the one that matches.
  `asset_type.schema.json` is behind by ADR-0028's `CollisionMeshSet` and ADR-0052's
  `GraspSpec` among others — a fresh export is a **591**-line diff at this commit
  (`git diff --no-index --numstat`, +578 −13) — and `zones`, `stations`, `facility`
  and `asset_instances` are behind too. **Established on 2026-09-09 while implementing
  [ADR-0054](adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md)**, whose decision 4 offered
  exactly this alternative to regenerating them; the drift was left out of that safety change
  rather than swept into it. What is owed is a decision: regenerate them in a `chore:` commit, add
  the check that would keep them honest, or delete them as an artifact nothing reads. **Nothing is
  known to be wrong** — the exports feed no validation — but a reader who opens one is reading a
  schema this repository has not exported for weeks.
- **A safety key fails closed in one direction only: nothing lets an older installed reader refuse
  a newer plan.** The new-reader/old-plan direction is closed — `cite_bringup.plan` parses
  `commands_physical_hardware` with `_require`, so a stale installed `cite_generated` raises a
  `PlanError` naming the key rather than defaulting it (ADR-0054, decision 3). **The mirror is
  open.** An installed `cite_bringup` built before that record reads a fresh plan, does not know
  the key, ignores it, and falls back to the name test the record deleted — which is the original
  defect, in a build state nobody looks at. Nothing in the plan or the reader makes the two
  versions compare notes. A plan format version, or the reader asserting `MODEL_HASH` against the
  value it was built against, would make every future safety key fail closed in **both**
  directions rather than one. **Recorded on 2026-09-09 while remediating ADR-0054's reviews; no
  code was written for it**, because which of those two mechanisms to build is a decision about
  every generated artifact and not about this one key. **Nothing is known to be wrong today** —
  `./scripts/build` reinstalls both packages together, and `./scripts/test` refuses to answer from
  a stale build tree — but that is a property of the workflow, not of the artifact.
