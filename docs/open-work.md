# Open work — snapshot of 2026-09-01

**Status: SNAPSHOT.** This is not a tracker and must not become one.

Charter §11 says the home of *"what is being worked on right now"* is the issue tracker and
explicitly **not** a document. No tracker is configured for this repository, and the working
list has been living in a session that ends. This file exists so that the list survives that
ending, and it is written as a **dated snapshot** for a successor session.

**It goes stale the moment work resumes.** Every item below names the command, file or record
that reproduces it; check that, never this file. If an item here disagrees with
`./scripts/doctor`, with a record in [`docs/adr/`](adr/README.md), or with a campaign in
[`docs/measurements/`](measurements/README.md), those are right and this is wrong.

**When a real tracker exists, delete this file rather than maintaining it.** A second place
where open work is written down is a P1 violation waiting to happen, and this file's only
defence is that it is dated and says so.

**Updated 2026-09-03**, on the branch `feat/close-phase-debts`: #30's open half has a published
campaign and is rewritten against it, #55 gains a related but textually distinct sibling event
from that campaign's raw, and the table below was re-derived by running the commands its rows
name. **The heading date is the date this file was first written and is deliberately not
moved**; every later reading carries its own date.

**Updated 2026-09-04**, on the same branch at `f6f8827`: a thirteenth campaign is published and
#36 is rewritten against it — §A.10 item 1 is recorded as met, and item 2's bracketing bullet as
**half** met. The two table rows below that could have moved were re-derived with the commands
they name: `main` is still `51195e0` (`git rev-parse main`, with `origin/main` agreeing), and the
campaign count is **13 on this branch, 11 on `main`**. No other row was re-read on this date.

**Updated again 2026-09-04**, on the same branch at `2affb36`: a **fourteenth** campaign is
published and **#20 is rewritten against it** — its **healthy-run half is closed** and its firing
half is not. [ADR-0036](adr/0036-execution-side-trajectory-tolerances.md) carries a dated
amendment of the same date; its **status did not move**. The same two table rows were re-derived
with the commands they name: `main` is **still `51195e0`** (`git rev-parse main`, with
`origin/main` agreeing), and the campaign count is now **14 on this branch, 11 on `main`**. No
other row was re-read on this date.

**Updated a third time on 2026-09-04**, on the same branch at `20612c8`: a **fifteenth** campaign
is published and **#49 and #17 are rewritten against it**. #49's **margin half is partially
measured** and its refusal half is unanswerable through the door that campaign used; **#17 was
refused by the campaign's own pre-registered rule and is not advanced one step**.
[ADR-0027](adr/0027-pilz-planning-pipeline.md) carries a dated amendment of the same date; its
**status did not move**. A new instrument-honesty item **#59** records the empty description
read-back, which has now cost three campaigns data. The same two table rows were re-derived with
the commands they name: `main` is **still `51195e0`** (`git rev-parse main`, with `origin/main`
agreeing), and the campaign count is now **15 on this branch, 11 on `main`**. No other row was
re-read on this date.

**Updated again 2026-09-08**, on the branch `feat/hosted-by-derived` at `7d7ac19`, which is ahead
of `main`:
**#45 and #40 are both closed** by the change that lands ADR-0048 clause 3, and each entry names
the command that reproduces its closure. #45's own text carried a wrong cost — that removing
`hosted_by` moves `MODEL_HASH` — which is corrected where it stood rather than deleted, in this
file and in ADR-0048. **#38 is deliberately untouched** and is now stale in two directions; #45
says why and who owes it. No table row below was re-derived on this reading, and none of the
notes above is disturbed.

**Updated 2026-09-08**, and this reading is taken on **`main` itself at `30baea8`**, not on a
branch: the work the notes above describe is merged, and `git rev-parse main` reads `30baea8`
while `git rev-parse origin/main` reads `13bc8e9`, so `main` is **one commit ahead of the
remote**. A new known defect **#60** records the third `continuous_line` failure signature, which
is **not** the door #19 covers; #19 gains a cross-reference and is otherwise untouched. **Six of
the eight table rows below were re-derived** with the commands they name on this date: five did
not move and the campaign row did. **Two were not re-read** — the environment row, which needs
the container, and the CI row, which needs an authenticated `gh` and does not have one here.

---

## Where the repository stood when this was written

`main` at `30baea8` — `git rev-parse main` on 2026-09-08, with `git rev-parse origin/main` one
commit behind at `13bc8e9`. It read `51195e0` on both, on 2026-09-03. This table was first taken at `3725af5`; every one of its original seven rows was
re-measured at `abdae38` on 2026-09-01 and **none of them moved**, and the head line read
`abdae38` until 2026-09-02. Reproduce each figure rather than quoting it from here.

**Re-measured again on 2026-09-03, and this time the checkout is not `main`.** The reading is
taken on the branch `feat/close-phase-debts`, which is **ahead of `main`** and carries the
twelfth measurement campaign; `main` itself **has not moved since 2026-09-02** and
is still `51195e0`, which was re-derived rather than assumed. **Seven of the eight rows were
re-read and one moved.** Measurement campaigns went **11 → 12**:
`2026-09-02-scenario-ceilings/` is the twelfth, and it is on this branch and **not yet on
`main`** — the same command run against `main` still returns 11.
**Re-read on 2026-09-04 at `f6f8827`: the count is 13 on this branch** —
`2026-09-03-stall-band-flip/` is the thirteenth — **and still 11 on `main`**, which has not
moved from `51195e0`.
**Re-read again on 2026-09-04 at `2affb36`: the count is 14 on this branch** —
`2026-09-04-following-error/` is the fourteenth — **and still 11 on `main`**, which still reads
`51195e0`.
**Re-read a third time on 2026-09-04 at `20612c8`: the count is 15 on this branch** —
`2026-09-04-waypoint-clearance/` is the fifteenth — **and still 11 on `main`**, which still reads
`51195e0`.
The other six re-read identically: `11` / `23` package manifests; `1 zone(s), 7 type(s),
15 asset(s), 5 station(s), across 15 file(s)` with `validate-model` exiting 0; `52 records, all
indexed` on `doctor`'s `ADR index` line, with `ADR references` resolving; charter v1.12; and
`select: convex_hull` at `model/assets/types/robots/xarm5.yaml:143`. The environment row was
re-read **in the container** at `29 passed, 0 failed, 1 skipped`, unchanged. **The row not
re-measured is the last one**, which needs `gh` against a CI run: **`gh` is installed neither
on this host nor in the container image**, so that row has now gone two days unchecked and a
claim about what CI has done expires the moment CI runs again. The environment row's own
history is the note below.

**Amended 2026-09-07: the host half of that sentence no longer holds.** A `gh` binary was
installed on this host on 2026-09-07 — `~/.local/bin/gh`, `gh version 2.100.0 (2026-09-03)` —
and the last row was re-measured with it that day. Whether the container image carries one was
**not checked**, so that clause is left as written and unverified. The sentence was true when it
was written; what it predicted came true faster than it allowed for.

| | | Command |
|---|---|---|
| Environment | 29 passed, 0 failed, 1 skipped, **in the container** | `./scripts/enter dev ./scripts/doctor` |
| Packages | 11 first-party, 23 with the imported vendor tree | `find workspace/src -name package.xml \| wc -l` |
| L0 model | 1 zone, 7 types, 15 assets, 5 stations, 15 files | `./scripts/validate-model` |
| Decision records | 52 indexed | `./scripts/doctor`, `ADR index` line |
| Measurement campaigns | 15, on `main` and on `origin/main` alike | `find docs/measurements -mindepth 1 -maxdepth 1 -type d \| wc -l` |
| Charter | v1.12, 2026-09-01 | `what-we-are-doing.md` header |
| Shipped collision geometry | `convex_hull` | `model/assets/types/robots/xarm5.yaml` |
| CI runs on the shipped geometry | 5 — `e51238e`, `4ef2d7c`, `51195e0`, `f6a3779`, `13bc8e9`; `continuous_line` passed in 3 of the 5 | `gh run view <id> --log \| grep -o "Scenario '[a-z_]*'[^\"]*"`, restricted to the scenario step column |

**The last row is five runs and is not a rate.** No thresholds were registered in advance, and it
says nothing about the grasp or about capacity. CLAUDE.md §2's collision-geometry item is where
it is kept. It read **four** until 2026-09-08, when `34247027502` at `13bc8e9` was added: that
run's `continuous_line` and `pick_and_place` both passed and one of its two `bringup` invocations
took the advisory branch on `parameter_bridge-2 exited with -6`. **That row is the only one in
this table not re-derived on 2026-09-08** — `gh` on this host is unauthenticated, so no CI log
could be opened; it carries the single reading of the agent that supplied it. The instrument now
carries a restriction it did not have on 2026-09-07: a CI log echoes the **commit message**, so a
whole-log grep also counts verdict strings quoted in a commit body, which is exactly what
`13bc8e9`'s message does.

**That row read `1, 33501707588 at e51238e, all three scenarios passed` until 2026-09-07**, and
the note above it said it "has now gone two days unchecked". It had in fact been falsified within
nine seconds of the commit that wrote it: `4ef2d7c`'s own CI run is a hull run. Re-read on
2026-09-07 with `gh run list --branch main` and the whole-string grep above over every run's log —
`gh` is on that host at `~/.local/bin/gh`, which is why the row could be re-measured at all.
**`pick_and_place` passed in all four**, `bringup`'s cycle passed in all eight invocations with
one teardown failure at `f6a3779`, and `continuous_line` failed in `4ef2d7c` and `51195e0`.

**The environment row was re-measured on 2026-09-02 at `51195e0` and it moved.** It read
`25 passed, 0 failed, 1 skipped` until then. Two
things about that row, both read from `scripts/doctor` rather than assumed:

- **Say which side of the container the reading is from.** `doctor` is the one command in
  CLAUDE.md §7's table that does **not** re-execute itself inside the container — `build`, `test`,
  `sim`, `scenario` and `audit-deps` all call `require_ros_env` and `doctor` does not. On a
  Linux machine with Docker but no native ROS, the **host** `./scripts/doctor` therefore reports
  `✗ ros 2 — no /opt/ros/jazzy/setup.bash` and **exits 1**; it read `25 passed, 1 failed,
  0 skipped` here on 2026-09-02. The container reading is the meaningful one.
- **The figure depends on whether a build tree is present**, which is why two readings taken on
  the same day can differ by one. **Measured here:** `29 passed, 0 failed, 1 skipped`, with the
  one skip being `docker … not installed` inside the container and `build fingerprint` passing.
  **Reported separately on the same day and not re-taken here:** `28 passed, 0 failed,
  2 skipped`. **Read from `scripts/doctor:149-164`,** the branch that accounts for the
  difference: an empty `workspace/build` is reported as a **skip** (`build tree … absent`) and a
  matching one as a **pass** (`build fingerprint … matches`), which moves exactly one check
  between the two columns. That the second reading was taken without a build tree is the
  explanation this makes available, **not something observed**. Run it rather than quoting it.

Phase 1 is closed (charter §8, exit criterion MET 2026-08-28). Phase 2 has split into 2.A and
2.B; 2.A's bring-up mechanism exists and **closes no clause** of the Phase 2 exit criterion.

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
0.077 m per step at 0.7 m reach. There are four beam housings in the scene.

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

### #19 — The `station_transfer_1` dead end: fixed, and the records stay `Proposed`
**This item covers the gripper-deadline door and only that door. It is not #60.** The two failures
#60 records are at the same station and are a different signature: there the gripper answered with
a genuine friction stall, the handoff completed, and the word `custody` appears **zero** times in
the scenario half of either log — the investigation's reading of those two logs on 2026-09-08,
not re-read since. Do not read a `continuous_line` failure at `station_transfer_1` as this item
without first checking which of the three signatures it is.

Cause established: a wall-clock gripper deadline supervising a simulation-time process; on expiry
`Pick` returned `TIMEOUT` without recording custody or cancelling the goal, and the retry's
`MoveToHome` carried the part off its own trigger beam. Fixed and merged — the deadline is
L0-declared and counted in the node's clock, the goal is cancelled, L3 latches custody-unknown,
and L4 refuses a retry while a station still names a work-piece.

**ADR-0045 and ADR-0046 stay `Proposed` deliberately.** The promotion condition for each is a
`continuous_line` run on a CI runner **in which the gripper fails to answer and the line reports
it**. A run in which the gripper answers quickly shows nothing. What is evidenced is the
mechanism, forced in both directions locally; not the outcome.

Two things recorded and open: whether a friction grasp survives the cancel is unmeasured
(`set_hold_position` holds width and stops squeezing, and ADR-0029 leaves the grasp to friction
alone); and after a missed grasp `MoveToHome` no longer runs, so the arm stops inside the fixture
and nothing in software reopens the jaws.

### #60 — `Place`'s final descent aborts at `cell_a__conveyor_1__infeed`: the same dead end through a third door
**Two CI failures, on two runners nobody prepared, at two commits, with nothing registered in
advance. The physical cause is unestablished and nothing here attributes one.** The runs are
`33575992281` at `4ef2d7c` and `33603610958` at `51195e0`, both 2026-09-02 — the third
`continuous_line` signature, tabled in CLAUDE.md §2, which is where the log evidence is kept.

**The chain, as the logs record it.** `Place`'s approach reports `Goal reached, success!`; the
**final descent onto the release pose** — the fifth trajectory of that work-piece — aborts in the
arm's `JointTrajectoryController` on a state-tolerance failure followed by a `goal_time_tolerance`
overrun — the exact strings and figures are in CLAUDE.md §2 and are not copied here (P1); the L3
classifier
(ADR-0037) reads the arm as stopped part-way and `/cite/cell_a/arm_1/place` returns code 10,
`MOTION_INTERRUPTED`, whose policy row is `ESCALATE`; L4 stops the line (ADR-0038) and the process
exits 1. **Every figure in this paragraph is the investigation's reading of those two logs on
2026-09-08 and was not re-read afterwards** — `gh` on this host is unauthenticated.

**It is not #19, and the check is cheap.** In both runs the gripper answered with a genuine
friction stall and the handoff completed, and the word `custody` appears **zero** times in the
scenario half of either log — so ADR-0045's deadline and ADR-0046's custody refusal are not what
fired. Neither run is evidence for either record's promotion condition, and neither record's
status moves on this item.

**What was re-derived from the tree on 2026-09-08, as opposed to read from a log.**

- The log's `joint 2` and `arm_1_joint3` are **one joint**, not two. The controller prints a
  zero-based index into its own `joints:` list, which is `joint1 … joint5`
  (`workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml:47-52`), and upstream
  prints that index into the error arrays (`ros2_controllers`, `jazzy`,
  `joint_trajectory_controller/include/joint_trajectory_controller/tolerances.hpp`).
- The descent is supposed to leave a **15 mm air gap**: `PlaceAt`'s `release_height_m` default is
  0.04 against a 50 mm part whose centre rests at 0.025, stated in that port's own comment
  (`workspace/src/cite_orchestration/include/cite_orchestration/skill_nodes.hpp:675-686`). Nothing
  should touch the belt during it.
- **Nothing in the cell changed to explain the onset.** `git diff e51238e..4ef2d7c -- workspace
  model tools tests scripts .github assets` is **one test file**, and **option F is not the
  discriminator**: `git merge-base --is-ancestor d3eeac4 <sha>` fails for `4ef2d7c`, which failed
  without it, and succeeds for `51195e0`, which failed with it, and for `f6a3779`, which passed
  with it.

**The investigation's strongest reading, not re-taken here: the arm was stationary or drifting
further from its goal, not converging.** Recovered two independent ways that agree — the limiter's
clamped command plus one control cycle of that joint's 3.14 rad/s limit, against `actual +
reported error` — the implied movement over the last cycle is **1.0e-4 rad** and **4.3e-6 rad** in
the two runs. That is what rules out a scheduling lag: a lag closing on its target would show the
opposite velocity sign.

**The cheapest measurement that would settle it.** Drive L3 `Place` at
`cell_a__conveyor_1__infeed` with `release_height_m = 0.04` repeatedly while recording
`/cite/cell_a/arm_1/arm_1_joint_trajectory_controller/controller_state`, and read
`arm_1_joint3`'s **terminal** error against the 0.010 rad goal tolerance. Running it **with and
without the part in the gripper** separates payload from contact.

**Most of that rig already exists, and the closest existing measurement did not reproduce the
abort.** `docs/measurements/2026-09-04-following-error/harness/` subscribes to that topic and its
**CARRY** arm already runs this exact motion: `PLACE_FRAME = cell_a__conveyor_1__infeed` and
`RELEASE_HEIGHT_M = 0.04`, with a real work-piece carried and `require_holding` true
(`harness/common.py:89-90`, `harness/cell.py:104-105`, `harness/measure.py:542-543`, read
2026-09-08). It ran **9 `place` trials** on that arm — counted from the campaign's own
`raw/B*_trials.json` on 2026-09-08 — and its verdict for CARRY is **QUIET**: no tolerance event of
any kind. **So the abort has not been reproduced by the closest instrument that exists**, at nine
trials, on a developer host rather than on a CI runner. What that harness never varied is the
**absence** of the part on this frame, and it reports the peak following error in flight rather
than the terminal error at the goal — which is where the two additions above go.

**One observation, recorded as an observation and not as a decision.** The controller's per-joint
abort threshold (`goal: 0.01`, `workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml`)
and the classifier's `arm_goal_tolerance_rad` (0.01,
`workspace/src/cite_generated/bringup/cell_a_plan.yaml`) are **one L0 value** —
`goal_tolerance_rad: 0.01` at `model/assets/types/robots/xarm5.yaml:308`, reaching both through
the generator — so this is **not** a P1 duplication. The consequence is structural:
`classify_motion_end` tests `within_tolerance(current, goal, arm_goal_tolerance_rad)` per joint
(`workspace/src/cite_skills/include/cite_skills/motion_end.hpp:102-145`), and a goal-tolerance
abort means some joint lies outside exactly that band, so such an abort **cannot** classify
`AT_GOAL`; it is `PART_WAY`, hence `MOTION_INTERRUPTED` and `ESCALATE`, unless the arm is also
within the band of its start. "Close enough to retry" is unreachable by construction. **Whether
that is the intended reading of ADR-0037 is the project owner's decision. This item takes none
and recommends none.**

### #26 — `bringup`'s `MoveTo` fails when a run is slow, and the split is perfectly disjoint
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
Seen once on 2026-08-29, on a run that was **restarted rather than analysed**, so it is one event
with no log kept. Nothing in the tree records this failure mode.

Candidates worth separating before calling it a flake: a QoS or latching mismatch on the topology
topic (CLAUDE.md §10's first bullet — a compatible pair still delivers nothing to a subscriber
that matched late); the publisher creating its publisher and publishing in the same callback (the
defect class that cost this project a belt setpoint for ten commits); or genuine slow bring-up.

**If it recurs, capture the log before restarting.**

### #55 — A paired bring-up failed on the plant side
The counterpart announced readiness; the plant never did. The plant's `planning_scene_loader.py`
for `arm_1` exited 1 with *"move_group refused the planning scene diff for zone 'cell_a'"*,
**14 ms after** that same `move_group` logged *"Unknown frame: cite_world"*. The node is
`required`, so the plant's launch shut down, and per ADR-0047 a side that ends ends the pair.

**Why it reads as a race and not a bad scene:** the counterpart brought the identical
configuration up cleanly at the same moment, on the same machine, in the same trial.

One event in eleven paired and twelve solo bring-ups, **not attributed**. Full evidence:
`docs/measurements/2026-09-01-capacity-on-shipped-main/raw/PAIR_HULL_FREE_3.console`, which
carries both sides' output.

**Why one event matters more than usual here:** it fails a `required` node and takes the whole
pair down, and **no test covers paired bring-up at all** — `launch_test` with
`IncludeLaunchDescription` holds one context on one domain, so a paired scenario cannot take
today's shape. A regression here fails nothing.

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

**The console is captured**, at
`docs/measurements/2026-09-02-scenario-ceilings/raw/C4_continuous_line_1.log`, with the run
document beside it — which is what #37's standing instruction asks for. **This item's own
occurrence carries a console too**, named above. **It is #37 whose single event was restarted
rather than analysed with no log kept**, and the two must not be confused.

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

### #38 — The generator cannot render 2.B
Exactly three generator call sites branch on a backend: `ResolvedAsset.ros2_control_plugin` (into
the description), `control.py:236` (`use_sim_time`) and `bringup.py:363` (`hosted_by`). **All
three read the plant's backend.**

In 2.A that is harmless — a paired zone's plant must be `sim`, the counterpart writes no
`counterpart_backend`, so all three answer identically for both sides. In 2.B it is wrong:
`counterpart_backend: real` today yields a plan saying `counterpart_backend: real` beside
`hosted_by: simulator`, and one controller config carrying `use_sim_time: true` for a side that
has no simulator.

**Needs an ADR before 2.B** — either the three sites become per-side, or the schema refuses the
combination until they are.

### #45 — ADR-0048 clause 3 — CLOSED 2026-09-08
**Closed at `7d7ac19`** on the branch `feat/hosted-by-derived`. ADR-0048's status block records clause 3 as
`Accepted` and carries a "Promotion — 2026-09-08" section; read that rather than this entry.

`hosted_by` is gone from the generator, the template, the plan schema and the committed plan.
`ControllerManager.backend_on(side)` replaces it and is the one place in `cite_bringup` that
maps an (asset, side) to a backend; `require_hardware_opt_in` now reads through it.
Reproduce with `grep -rn hosted_by workspace tools tests scripts`, which returns **two** files
and both are about the removal: the guard
`tools/tests/test_a_removed_plan_key_stays_removed.py`, which fails if any other tracked file
under those four trees states the name, and
`workspace/src/cite_bringup/test/test_a_removed_plan_key_is_ignored.py`, which pins that a plan
still carrying the key **loads** rather than being refused — the document most likely to carry
it is one left in a stale build tree, where the cause is a rebuild and not a key.

**One claim in the entry above was wrong and is worth keeping rather than deleting.** It said
removing the field moves *"the committed generated tree and `MODEL_HASH`"*, copying ADR-0048's
own *Consequences*. The tree moved — `bringup/cell_a_plan.yaml`, twelve lines, and nothing else
under `cite_generated/`. **`MODEL_HASH` did not**: it digests the loaded model's object graph
and not file bytes, the L0 model is untouched here, and the hash is byte-identical
(`95dbbdd9…`). ADR-0048 carries the correction in place, and
`tools/tests/test_generate.py::TestModelHash::test_does_not_change_when_a_template_changes`
asserts the property for every future template edit rather than the value for this one.

**The `test_two_sides_with_the_same_name_are_refused` half is also done**: it is on
`_solo_document()`, and #40 below is where that is kept.

**What this does NOT close:** #38 above. Its "exactly three generator call sites" is still
stated there, and it is now wrong twice over — `hosted_by` was never a branch on a backend and
is no longer anywhere, while the collision scheme in `generate/description.py` was a site the
count never included. **That entry is deliberately untouched here**, because the change that
makes those sites per-side is the one that owes them; `grep -rnE "backend|SIMULATION_BACKEND"
tools/cite_tools/generate/*.py` returns **four files** today and is the instrument. The two
places this commit's own edits landed in —
`tools/cite_tools/validate/referential.py`'s `divergent-counterpart-backend` docstring and
`tools/cite_tools/model/ids.py`'s `SIMULATION_BACKEND` comment — were corrected, because both
justified their count by naming `hosted_by` and could not be left saying "three" once it was
gone.

### #40 — `test_plan.py` on a paired checkout — CLOSED 2026-09-08
**Closed by construction at `7d7ac19`** on the branch `feat/hosted-by-derived`, and the distinction matters:
it is not closed by anyone having run against a paired model. The committed model stays
`twin: {sides: single}` and nothing here flips it.

**What the class was:** a test that reads the live generated plan instead of building its own
document, so it asserts about whichever model the checkout happens to carry. On a checkout
flipped to `pair`, `_document()["plan"]["sides"].append(_counterpart(...))` produced two sides
named `counterpart` and the test failed on its own fixture rather than on what it asked about.

**What replaces it.** `_document()` is gone. `_live_document()` is the only reader of the live
plan and a test may not call it: `test_only_the_two_shape_helpers_read_the_live_plan` parses
the module and requires its callers to be exactly `_paired_document` and `_solo_document`.
Parsed rather than grepped, because a guard that counts a string counts its own message.
Every test that edits a plan document now takes a `document` fixture parametrised over
**both** shapes, so both run on every checkout and neither can be the one nobody tried; the
three tests that APPEND a side take `_solo_document()` by name and say why.
`test_two_sides_with_the_same_name_are_refused` is one of those three — #45's second half, the
one that *"passes for a partly accidental reason"*.

**One thing the fixtures got wrong and this fixes.** `_paired_document()` appended the
counterpart's `sides:` entry and nothing else, while `_solo_document()`'s own docstring says
pairing adds exactly two things — the side, and a `counterpart_backend` on every controller
manager. So the paired fixture built a document no generator emits. It now applies both, in
ADR-0041 Decision 3's shape.

Reproduce: `./scripts/test` runs it, or in the container
`python3 -m pytest workspace/src/cite_bringup/test/test_plan.py -q` — **119 passed** at this
commit, against 76 tests before. **What is still not evidenced:** no run against a paired model
was taken here, so what is closed is the class, not a measurement of it.

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

## 4. Instrument honesty

Every item here misled this project at least once, including in the session that wrote this file.

### #52 — WITHDRAWN 2026-09-01: the verdict line distinguishes three states, and CI's teardown is read and clean
**This item was wrong in both of its claims, and it is left here rather than deleted because how
it was wrong is the transferable part.** It said the verdict line *"answers the cycle and says
nothing about teardown"*, and that teardown for the newer CI rows was *"unread, not clean"*.

**What is actually true, read off `scripts/scenario` and off all nineteen CI runs.** The script
prints **three** distinguishable strings, not two:

| String | Means |
|---|---|
| `Scenario 'X' passed` | `launch_test` itself exited 0 — every assertion passed, **including the post-shutdown teardown check**. `scenario_verdict` was never consulted. |
| `Scenario 'X' passed its cycle assertions` | The advisory branch: the cycle passed, teardown did not, `--teardown-advisory` was given. |
| `Scenario 'X' failed — …` | A cycle failure, or a failure the JUnit report does not explain. |

**The middle string appeared in none of the nineteen tabled CI runs**
(`gh run view <id> --log | grep -o "Scenario '[a-z_]*'[^\"]*"`, run over every one of them on
2026-09-01), so every one of the fifteen bare `passed` verdicts carried its teardown with it, and
only the four whose cycle failed left teardown masked and genuinely unread. The four were
`33158091922`, `33208064683`, `33261637940` and `33343317444` — the same four CLAUDE.md §2's
table named, arrived at independently.

**Amended 2026-09-07: this paragraph said "the advisory branch has never fired in CI", and that
has expired.** It fired at `f6a3779` (run `34085965578`), for `bringup` and not for
`continuous_line`: one of that run's two `bringup` invocations printed `Scenario 'bringup' passed
its cycle assertions`, its cycle having passed and its post-shutdown check having failed on
`parameter_bridge-2 exited with -11`. Re-read over all twenty-two tabled runs on 2026-09-07 with
the same grep, anchored at both ends: `continuous_line` is 16 bare `passed`, 6 `failed`, 0
advisory; `bringup` is 43 bare `passed`, 1 advisory, 0 failed; `pick_and_place` is 22 bare
`passed`. **The item's own lesson repeats itself here** — this was a claim about what has never
happened, and only re-running caught it.

**`--teardown-advisory` never reaches the scenario Python.** `scripts/scenario` puts it in
`TEARDOWN_POLICY` and not in `LAUNCH_TEST_ARGS`, so the post-shutdown assertions always run; the
flag decides only how a failure is reported.

**`scripts/scenario` is not to be changed on the strength of this item.** The instrument is
correct as written. What was wrong was the reading of it — the item inferred the verdict's
behaviour from `scenario_verdict()` alone without noticing that the function is called **only
after `launch_test` has already failed**, which is stated in its own header comment in
`scripts/_lib.sh`. **Reading one branch of a two-branch caller is how this item was written**, and
that is the lesson worth keeping in a section about instrument honesty.

**One sub-claim survives and is now recorded where it belongs:** the hull promotion was merged on
a CI run reporting scenario passes, and a scenario pass is evidence about one run. That is in the
state table above, with its strength stated.

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
- **`resolve.py:135` and `moveit.py:91` hardcode `"drive_joint"`** instead of reading
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
