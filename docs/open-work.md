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

**Updated 2026-09-16**, on the branch `feat/cell-b-zone`: two new structural items, **#66**
and **#67**, record the two validation gaps a second zone exposed — nothing compares two zones'
bounding boxes, and a cross-zone station reference passes referential validation and then skips
its reach check in silence. Both are **filed rather than fixed**, which is
[ADR-0056](adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md)'s own
decision and is recorded there under "What this costs us". Each entry names the command that
reproduces it. **No existing item was re-read on this date** and no table row below was
re-derived, so everything else in this file still carries whatever date it already carried.

**Updated 2026-09-18**, on the branch `feat/pair-boundary`, which is ahead of `main`: **six new
items, #74 to #79**, all pre-existing L5 design rather than that branch's defects — the pair
supervisor starting the twin boundary ([ADR-0057](adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md))
is the first thing that puts a boundary in front of a running pair, and what it exposed is what
the boundary already did. They are **filed rather than fixed**, deliberately: a remediation round
scoped to one branch's findings is the wrong place to redesign an L5 command path. Each entry
names what reproduces it and **attributes nothing beyond what was observed**. **No existing item
was re-read on this date** and no table row below was re-derived, so everything else in this file
still carries whatever date it already carried.

**Corrected 2026-09-17, on the same branch.** Two table rows below WERE stale and are
re-derived here rather than left, because the change that made them stale is this branch's:
the **L0 model** row read `1 zone, 7 types, 15 assets, 5 stations, 15 files` beside a command
that now answers `2 zone(s), 7 type(s), 22 asset(s), 8 station(s), across 16 file(s)`, and the
**Decision records** row read 52 against `./scripts/doctor`'s 55. A count printed beside the
command that produces it is a promise the two agree; not re-running a command you have just
invalidated is how each wrong figure in CLAUDE.md §2 got written. **Four other rows were
re-run on that date and did not move** — Packages (23), Measurement campaigns (15), Shipped
collision geometry (`convex_hull`) and the L0 model's own command exit status — and the two CI
rows were **not** re-read, because no CI run of this branch exists. **Item #67's reproduction
command was also updated** for the `cell_b` asset rename; a reproduction that no longer
reproduces is worse than none.

**Amended later the same day, after four reviewers read that change.** #45 stated that
`hosted_by` was *"never a branch on a backend"*, which is false and is corrected in place — it
was one of #38's three sites, which is why #38's count is **stale** rather than **wrong when
written**, and the difference matters because ADR-0041 still rests on that argument. #40's
closure narrated a failure that was already gone at `e18251e` and declined a measurement that
was two minutes away; the measurement is now taken, on both trees and both model shapes, and
its base row says the failures were already gone. **#61 is new** — a third side would be gated
by nothing — and is filed rather than fixed, for the reason it gives itself.

**Updated 2026-09-08**, and this reading is taken on **`main` itself at `30baea8`**, not on a
branch: the work the notes above describe is merged, and `git rev-parse main` reads `30baea8`
while `git rev-parse origin/main` reads `13bc8e9`, so `main` is **one commit ahead of the
remote**. A new known defect **#60** records the third `continuous_line` failure signature, which
is **not** the door #19 covers; #19 gains a cross-reference and is otherwise untouched. **Six of
the eight table rows below were re-derived** with the commands they name on this date: five did
not move and the campaign row did. **Two were not re-read** — the environment row, which needs
the container, and the CI row, which needs an authenticated `gh` and does not have one here.

**Updated again 2026-09-08**, on the branch `feat/hosted-by-derived`, after a second review round
and a `tester` run over the fix commit. **Three items are new** — **#62**, the two `cite_twin`
fixtures that append a counterpart unconditionally, which is #40's class alive one package over;
**#63**, the paired-plan document shape hand-built in five fixtures and tied to the generator in
none; and **#64**, a host-virtualenv `typer`/`click` incompatibility that breaks
`cite_tools.cli --help`. **#40 is corrected twice**: its closure is scoped to `cite_bringup`,
because the guard that holds it parses `Path(__file__)` and reaches one file, and its
measurement table's `single` row is re-measured — it read **205** and is **209**, which is what
the `pair` row already read. **#45's instrument count is corrected** from five lines in four
files to **6 in 5**, one of the six being the sentence that names the instrument. Every figure
in these edits was re-measured in this checkout on this date by the change that writes them; no
table row in the section below was re-read.

**Updated 2026-09-10**, on the branch `feat/declared-simulation-backend`, which is ahead of
`main` and implements [ADR-0054](adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md). **One
item is new: #65**, filed from a `safety-auditor` finding on that branch and re-driven by the
fixer that filed it — the arm type's `bound_args` carries the declared `ros2_control_plugin`
string into the description, **no validator reads `bound_args`**, and the vendor macro's own
default is the physical component, so an omitted binding reaches a physical arm with L0, the
plan and the bring-up gate all telling the truth. It is **pre-existing**, is filed rather than
fixed because the fix is a choice between two shapes, and ADR-0054 carries a matching Correction
of the same date for the three places it stated its residual as bounded to a *false* declaration.
**No other item was touched and no table row below was re-read on this date.**

**Updated again 2026-09-10**, on the same branch at `5516169`, from a `tester` run taken before
the merge. **#55 is corrected**: its *"One event in eleven paired and twelve solo bring-ups"* was
true when written and is false now — there is a **second occurrence**, and it is the **first in
the solo configuration**, which removes the concurrent clean counterpart that was the argument
for reading it as a race. The signature was compared against both the first occurrence and the
2026-09-03 sibling rather than matched on the node name: it is **the same as the first** and
**still distinct from the sibling**, and one of the four grounds that separated the sibling is
retired by it. Its console is **deliberately not committed** and the item says why and what that
costs. The item's heading changed and records what it used to read. **No other item was touched**
— the same run's second failure matches **#26** and is named in #55 without being developed
there — **and no table row below was re-read on this date.**

**Updated 2026-09-17**, on the branch `feat/cell-b-zone` at `87470fc`, which is ahead of `main`
and lands [ADR-0056](adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md).
**Three items are new and all three were measured rather than reasoned about**: **#69**, which a
`tester` reproduced 3 of 3 while answering a question about #68 and which **amends #68's closing
sentence**; **#70**, found by a `fixer` when `./scripts/test` reported 0 of 11 packages and
nothing of ours executed; and **#71**, a coverage gap a `tester` named in the round that closed
the defect around it. **No existing item below was re-read on this date and no table row was
re-derived**, except #68, which #69 amends where it stands.


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
`select: convex_hull` at `model/assets/types/robots/xarm5.yaml:153`. The environment row was
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
| L0 model | 2 zone(s), 7 type(s), 22 asset(s), 8 station(s), across 16 file(s) | `./scripts/validate-model` |
| Decision records | 55 indexed | `./scripts/doctor`, `ADR index` line |
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

### #80 — A held work-piece is attached to nothing, so the collision gate cannot see it
`ValidateSolution` is the sole environment-collision gate, and it checks the arm's links against
the planning scene. **It checks nothing at all against the part in the jaws.** `grep -rn
AttachedCollisionObject workspace/src` reaches three prose mentions and **no call**; ADR-0029
removed the simulation-side attachment as well, so friction alone holds the part and MoveIt does
not know it exists. A 50 mm cube hangs roughly 25 mm below the fingertip plane, so a plan that
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
ADR-0060. What checks this today is that `pick_and_place` and `continuous_line` assert where the
work-piece ends up: if the arm knocks it off a surface, they fail.

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

**A THIRD OCCURRENCE, ON `cell_b`, OBSERVED LOCALLY ON 2026-09-21 — and it is kept apart from
the two above rather than appended to them.** Watching a paired `cell_b` run its line, the
project owner saw one side's box sit on the belt while the other's was carried away. Measured:
`Place` aborted with `State tolerances failed for joint 2, Position Error 0.022293 vs Tolerance
0.010000` then `goal_time_tolerance exceeding by 0.506378 s` — against `0.506172 s` and
`0.506390 s` in the two `cell_a` CI runs. The station escalated, `StopAll` set the belt to 0.0,
and **the arm was left with its gripper clamped on the part** at `picker_drive_joint = +0.4088
rad`, because `Place` opens the jaws at a step the aborted descent never reached. The healthy
twin finished the same job with the gripper at 0.0000.

**This is a different cell, a different asset and a developer host**, so it is not appended to
the `cell_a` counts, which close where they are. What is shared is the assertion and the
mechanism; **sharing a signature is not sharing a cause**, and the physical cause of all three
remains unestablished. One event, one machine, nothing registered in advance. **That is not a
rate.** The campaign registered at
[`2026-09-21-place-abort-and-the-held-part`](measurements/2026-09-21-place-abort-and-the-held-part/criteria.md)
is what would turn it into a measurement, and its own rule 1 says that if the abort does not
reproduce, its silence evidences nothing.

**What the arm being left clamped now produces, which it did not before.** `Place.Result` carries
`still_holding`, filled at every exit and true when custody is unknown, and L4's blocked reason
names the held work-piece whatever the recovery — where before, `MOTION_INTERRUPTED` escalating
on its own meant the sentence was never written. **Nothing opens the jaws**: what to do with a
held part is ADR-0038 decision 5 and stays open.

**One observation, recorded as an observation and not as a decision.** The controller's per-joint
abort threshold (`goal: 0.01`, `workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml`)
and the classifier's `arm_goal_tolerance_rad` (0.01,
`workspace/src/cite_generated/bringup/cell_a_plan.yaml`) are **one L0 value** —
`goal_tolerance_rad: 0.01` at `model/assets/types/robots/xarm5.yaml:332`, reaching both through
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

### #55 — `planning_scene_loader.py` exits 1 on a refused scene diff: two occurrences
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
gate and is exactly what caught this one.

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
Exactly three generator call sites branch on a backend: `ResolvedAsset.ros2_control_plugin` (into
the description), `control.py:236` (`use_sim_time`) and `bringup.py:378` (`hosted_by`). **All
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
Reproduce with `grep -rn hosted_by workspace tools tests scripts model .github infra`, which
returns **two** files and both are about the removal: the guard
`tools/tests/test_a_removed_plan_key_stays_removed.py`, which fails if any other tracked file
under those seven trees states the name — it walked the first four when this entry was written
and gained `model/`, `.github/` and `infra/` later the same day, because its own docstring
claimed every tree code is read out of — and
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
stated there, and it is now wrong for **two** reasons — one site was removed, and one site was
never listed. `hosted_by` **was** a branch on the plant's backend, which is precisely why it
was one of the three; what made it cheap to delete is that it was a total function of a backend
the plan already states per side and nothing read it. And the collision scheme in
`generate/description.py` was a site the count never included at all.
**[Corrected 2026-09-08 — this paragraph read "`hosted_by` was never a branch on a backend and
is no longer anywhere" when it was written hours earlier.** That is false: the deleted code was
`hosted_by="simulator" if asset.instance.hardware.backend == ids.SIMULATION_BACKEND else
"ros2_control_node"` (`e18251e:tools/cite_tools/generate/bringup.py:407-409`). Saying otherwise
retroactively invalidates #38's count, which was **correct when written**, and it invalidates
the same argument where ADR-0041 still rests on it. A stale count is not the same as a count
that was always wrong, and only the first of those is what happened here.**]**
**That entry is deliberately untouched here**, because the change that
makes those sites per-side is the one that owes them; `grep -rn "instance.hardware.backend"
tools/cite_tools` returns **6 lines in 5 files** and is the instrument — three of
them branch (the `ros2_control` plugin in `model/resolve.py`, the collision scheme in
`generate/description.py`, `use_sim_time` in `generate/control.py`), one restates the
value into the plan, one is `model/resolve.py`'s refusal message beside its own branch, and the
sixth is `validate/referential.py`'s own sentence naming this instrument.
**[Corrected 2026-09-08 — this read "five lines in four files today", measured before the
sentence naming the instrument was written into `referential.py`, which put the search scope
inside the search.** Re-run in this checkout on 2026-09-08 it is 6 in 5, and the sixth is that
sentence: **a guard that counts a string counts its own message**, which is the hazard this
branch named in `test_plan.py` and then walked into one file over. That docstring now states
6/5 and says which one is prose.**]**
**Ask the instrument for its reach as well as its count**: it reaches every read through
`ResolvedAsset.instance`, which is every **generator** site, and not every read of the plant's
backend — `model/schema.py`, `cli.py` and three lines in `validate/referential.py` spell it
`asset.hardware.backend` off the raw model asset, and none of them generates an artifact. The
docstring claimed the wider set and was corrected with the count.
**The instrument this entry first named,
`grep -rnE "backend|SIMULATION_BACKEND" tools/cite_tools/generate/*.py`, could not reach the
first of those three**, which lives outside `generate/`, so it under-read the very list it was
offered as the answer to. The two
places this commit's own edits landed in —
`tools/cite_tools/validate/referential.py`'s `divergent-counterpart-backend` docstring and
`tools/cite_tools/model/ids.py`'s `SIMULATION_BACKEND` comment — were corrected, because both
justified their count by naming `hosted_by` and could not be left saying "three" once it was
gone.

### #40 — `test_plan.py` on a paired checkout — CLOSED 2026-09-08
**Closed by construction at `7d7ac19`** on the branch `feat/hosted-by-derived`, **and measured
on 2026-09-08** — the entry said the measurement had not been taken and it was two minutes
away. The committed model stayed `twin: {sides: single}`; the run below was taken in the working
tree and reverted, and `git status` was checked clean afterwards. **[Overtaken 2026-09-18 —
ADR-0059 pairs `cell_b`; `cell_a` stays `single`. The closure is unaffected: the guard this item
closed on is the tree's, not the model's.]**

**What the class was:** a test that reads the live generated plan instead of building its own
document, so it asserts about whichever model the checkout happens to carry. On a checkout
flipped to `pair`, `_document()["plan"]["sides"].append(_counterpart(...))` produced two sides
named `counterpart` and the test failed on its own fixture rather than on what it asked about.
**[Corrected 2026-09-08 — that describes the tree BEFORE an earlier fixture fix, not before
this commit.** At `e18251e` no test does it unconditionally. Written as the state this change
found, it credits this change with a failure that was already gone — and the measurement below
says so directly, since the base passes paired.

**The first wording of this marker miscounted the base it was about**, which is worth keeping
because the whole subject of the marker is the base state. It read *"all three
`_counterpart(...)` appenders were already on `_solo_document()`"*; at `e18251e` there are
**two** on `_solo_document()`, at `:987` and `:1114`, and the third `_counterpart()` call is
inside `_paired_document` on `_document()`, guarded by `if not any(side["name"] ==
"counterpart" ...)`. Three is the **branch's** count, not the base's. Verified on 2026-09-08
with `git show e18251e:workspace/src/cite_bringup/test/test_plan.py | grep -n "_counterpart("`,
which returns four lines — the definition at `:931` and the three calls. The load-bearing
claim is untouched: nothing at `e18251e` appended a counterpart unconditionally, which is why
the base row passes paired.**]**

**What replaces it.** `_document()` is gone. `_live_document()` is the only reader of the live
plan and a test may not call it: `test_only_the_two_shape_helpers_read_the_live_plan` parses
the module and requires its callers to be exactly `_paired_document` and `_solo_document`.
Parsed rather than grepped, because a guard that counts a string counts its own message.
**That guard alone had a one-line bypass, and it was demonstrated on 2026-09-08.**
`_live_document`'s whole body is `yaml.safe_load(_generated().read_text())`, and `_generated`
is a module-level accessor with two dozen callers — so a test spelling that one line itself got
the live document with the guard green, and died on a paired tree with this entry's exact
signature. `test_nothing_reaches_the_live_plan_around_that_reader` closes it by SHAPE rather
than by caller: outside `_live_document` a call to the accessor must be the direct argument of
`load`, which returns a `Plan` with no `sides` list to append to, and `GENERATED_PLAN` may be
read nowhere but the accessor, since `Path(resolve_uri(GENERATED_PLAN))` is the same reach one
step lower. Both routes were written as mutations first and both are refused by name.
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

**The measurement, taken 2026-09-08 in this checkout, on one machine, with nothing registered
in advance.** Method: `sed -i 's/sides: single/sides: pair/' model/facility/zones.yaml`, then
`./scripts/validate-model --write`, then
`./scripts/enter dev bash -lc "cd /workspace && python3 -m pytest <path> -q"`. The generated
tree is symlink-installed, so no rebuild is needed for the tests to read the paired plan.
Reverted with `git checkout -- model/facility/zones.yaml workspace/src/cite_generated`, and
`MODEL_HASH` verified back at `95dbbdd9…`.

| tree | model | `test_plan.py` | whole `cite_bringup` suite |
|---|---|---|---|
| `e18251e` (base) | `single` | **84 passed** | not taken |
| `e18251e` (base) | `pair` | **84 passed** | not taken |
| branch, after two review rounds | `single` | **124 passed** | **209 passed** |
| branch, after two review rounds | `pair` | **124 passed** | **209 passed** |

**[Corrected 2026-09-08 — the `single` suite row read 205 and nobody can source it.** Two
readers went looking: a `tester` could reproduce 205 at neither commit (it read 204 at
`8b74f80`), and the project owner ran
`./scripts/enter dev … pytest workspace/src/cite_bringup/test --collect-only -q` on the
committed single-sided model and got **209 collected**. The row was re-measured a third time on
2026-09-08 in this checkout, by the change that writes this correction, on the same tree as the
`pair` row: **209 collected and 209 passed on `single`, 209 collected and 209 passed on
`pair`**, with `test_plan.py` at **124** on both. **The conclusion the table was offered for
comes out stronger, not weaker** — the count does not move with the model, and now both rows
say the same number rather than differing by four. Where the 205 came from is **unestablished**
and is left stated rather than smoothed over; the branch has gained tests since it was written,
so a stale reading is the likeliest explanation and nobody has shown it.**]**

**Read the base row before reading the branch row.** The base passes paired too, so what this
change closed is the class **in `cite_bringup`** — a test in that package may no longer read the
live plan, and the guard says so by parsing rather than by remembering — and **not** a set of
failures that were still occurring.

**The scope is the package and not the repository, and this entry said otherwise until
2026-09-08.** `test_nothing_reaches_the_live_plan_around_that_reader` and its sibling both parse
`Path(__file__)`, so each guards **one file**, and nothing outside `cite_bringup/test/` is
reached by either. The class is alive one package over: **#62** records the two `cite_twin`
fixtures that still append a counterpart unconditionally, measured refusing on a paired tree on
2026-09-08. Close a class only as far as the guard walks.
The fourteen failures this entry was opened for were already gone at `e18251e`. Saying this
change fixed them would be claiming a measurement nobody took.

**Two smaller things the run settled.** The count does not move with the model: `test_plan.py`
collects and passes the same number on both shapes, because the `document` fixture's
parametrisation is static. And the before-figure this entry carried was wrong —
**[Corrected 2026-09-08 — it read "119 passed at this commit, against 76 tests before".** The
119 was measured; the **76** was copied from this entry's own older text, and `test_plan.py` at
`e18251e` collects **84** (`pytest --collect-only -q`, in the container). Setting a freshly
measured number beside a copied one is what CLAUDE.md §2 exists to prevent, and it happened
inside the entry that was closing a defect about trusting a stale figure.**]** The branch figure
has since moved from 119 to **124**: review added five tests to the same file — four for the
load-time refusal ADR-0048's promotion section records, one for the hardware gate's narrow
`except`.

Reproduce with `./scripts/test`, or in the container
`python3 -m pytest workspace/src/cite_bringup/test/test_plan.py -q`.

### #62 — `cite_twin`'s two launch fixtures append a counterpart unconditionally
`workspace/src/cite_twin/test/test_twin_boundary_launch.py:97-121` and
`test_twin_boundary_paired_launch.py:119-143` each build their paired plan the same way: read
the live generated plan with `default_plan_path(...)`, `plan["sides"].append({"name":
"counterpart", ...})` with **no test for a counterpart already being there**, write it to a
temporary file, and bind the result to a module-level `PLAN_PATH`. On a checkout whose L0
declares `twin: {sides: pair}` the live plan already carries that side, so the fixture writes a
document with **two sides named `counterpart`** and `cite_bringup.plan.load` refuses it. That is
**#40 verbatim**, in the package that is Phase 2.A's subject.

**Measured on 2026-09-08, in this checkout, one reading.** Method: flip
`model/facility/zones.yaml` to `sides: pair`, `./scripts/validate-model --write`, then import
each module in the container and call `load(PLAN_PATH)`. Both give
`SideNotDeclaredError: … two sides are named 'counterpart'`. Reverted, with `MODEL_HASH`
verified back at `95dbbdd9…`.

**Where it bites is later than it looks, and the difference matters for whoever fixes it.**
Collection **passes** — `pytest --collect-only` over both modules returns `2 tests collected` on
a paired tree — because `_paired_plan()` only *writes* the file; nothing at module scope loads
it. The refusal fires when the boundary node reads the plan at launch, so the symptom is a
launch test whose node exits, not an import error. An earlier reading of this said the module
errors at collection; it does not.

**Pre-existing, and not introduced by ADR-0048 clause 3.** The same fixtures behave identically
at `e18251e`. What changed is that #40's closure was written as a repository-wide statement
about the class while the guard that holds it parses `Path(__file__)` and reaches one file.

**THIS ITEM IS NOW LOAD-BEARING RATHER THAN MERELY OPEN, AS OF 2026-09-18.** `cell_b` is paired
in the shipped model (**ADR-0059**), and `./scripts/test` still passes, for one reason and one
reason only: **both fixtures name `cell_a` literally** — `default_plan_path("cell_a")` in
`test_twin_boundary_launch.py` and `ZONE = "cell_a"` in `test_twin_boundary_paired_launch.py`,
re-measured on that date — and `cell_a` is still `single`. So the defect is **stepped around,
not fixed**, and two ordinary changes trip it immediately: pairing `cell_a`, or making either
fixture read the default zone the way the scenarios do. ADR-0059 records that dependency as a
cost of pairing `cell_b`, and `model/facility/zones.yaml` states it at `cell_a`'s own `twin:`
block so that whoever flips that line reads it first. **Anyone who does either must fix this
item in the same change.**

**The fix is one line in each**, and it is already written twice in `cite_bringup`:
`if not any(side["name"] == "counterpart" for side in sides):` around the append, which is what
`test_plan.py`'s `_paired_document`, `test_pair.py`'s `_paired_plan` and
`test_simulation_launch.py`'s `_paired` all do. **Deliberately not fixed on
`feat/hosted-by-derived`**: `cite_twin` is L5 and outside that branch's subject, and an L5 edit
inside a plan-schema change is the blast-radius widening ADR-0048's own promotion section
declines for the same package.

**It bit on 2026-09-18, when `cell_b` was paired, and it is stepped around rather than fixed** —
see the paragraph above for the one reason `./scripts/test` still passes.
`./scripts/sim --zone cell_b --pair` now comes up from a clean checkout; `--pair` on `cell_a`
refuses, because that zone alone declares one side. Cross-references: #40, whose class this
is, and #63, which is the same fixtures counted a different way.

Reported by review on 2026-09-08 (G-2) and filed rather than fixed, at the project owner's
instruction.

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
The hardware opt-in decides on `commands_physical_hardware`, which L0 declares one line from the
`ros2_control_plugin` string it is about (ADR-0054). That plugin string reaches the generated
description through exactly one binding — `ros2_control_plugin: instance.hardware.ros2_control_plugin`
in the arm type's `bound_args` — and **nothing checks that the binding is there.**

**Driven end to end on the shipped model on 2026-09-10, not reasoned about.** Delete that one
line, a plausible edit while re-working bindings, and `cite-model validate --write` exits 0 with
`ok model valid — 1 zone(s), 7 type(s), 15 asset(s), 5 station(s), across 15 file(s)`, `--strict`
prints no finding, the generated `cell_a_arm_1.urdf.xacro` calls `<xacro:xarm_device …/>` with
**17** arguments where the committed one carries 18, `ros2_control_plugin` being the one it loses, and the vendor macro applies its own
default — `uf_robot_hardware/UFRobotSystemHardware`, at
`xarm_description/urdf/xarm_device_macro.xacro:14` and `urdf/xarm5/xarm5.ros2_control.xacro:5`,
emitted at that file's line 15. Meanwhile L0 still reads `gz_ros2_control/GazeboSimSystem` beside
`commands_physical_hardware: false`, the plan still carries `false` on all three arms, and
`require_hardware_opt_in` returns **without ever consulting `CITE_ALLOW_HARDWARE`**. The gate is
not wrong; it is answering honestly about a fact that stopped being connected to the description.
`grep -rn bound_args tools/cite_tools/validate/ | wc -l` reads **0**.

**This is the omission direction, and it is the one `cross-cutting-safety.md` forbids.** ADR-0054
closed the assertion direction — a physical plugin declared under the id `sim` — and made the
field and the plan key both unreachable by omission (its clauses 1 and 5). The binding is the
third layer, and no clause of that record looked at it: clause 3 asserts that **no description
moves**, which is exactly the artifact in which this appears.

**Pre-existing, and not introduced by `feat/declared-simulation-backend`.** The binding line is
present at `404bbac` and `bound_args` had zero validator readers there too; that branch strictly
narrows the neighbouring hazard. It blocked no merge and was not fixed there.

**Two candidate shapes, and neither is chosen here — that is the project owner's.**

- **An L0 rule.** A type whose `hardware_backends` declare a `ros2_control_plugin` must bind it:
  an ERROR in `validate.referential` on the unbound binding, in the shape ADR-0028 decision 4
  used for collision geometry — L0 declares what the vendor does, and a rule holds it. Cheap,
  runs anywhere, and catches the edit at the moment it is made. It checks a *binding name*, so
  it says nothing about what the vendor macro then does with the value.
- **A generated-artifact check.** Each arm description's `<plugin>` must equal the plugin the
  selected backend declares. Strictly stronger — it is the actual question — and strictly more
  expensive: it needs the vendor source imported and a xacro expansion, so it cannot run where
  `./scripts/validate-model` runs, and it lands in `./scripts/hulls` territory or in a
  `cite_description` test.

**Do it before any hardware launch exists** — ADR-0054's *What we will have to revisit* bullet on
the hardware launch shape is where it belongs. That is the last moment at which no deployment
depends on the answer, and the moment the vendor component acquires the connection parameters
ADR-0053 delivers is the moment an unguarded description stops being fail-closed by accident.

**2026-09-15: ADR-0053's implementation guards the parameter half, and this item stays open.**
A type that binds an instance parameter without binding `instance.hardware.ros2_control_plugin`
is refused as `unrouted-hardware-params`, at the validator and at the generator, because that
branch would otherwise have delivered a working address to the vendor's default physical
component. So the `grep` above no longer reads 0. Deleting the plugin binding on a type that binds
no instance parameter, and binding it under an argument name the vendor does not read, are both
still silent.

Reported by `safety-auditor` on 2026-09-10 (S-01), re-driven by the fixer that filed it, and
deliberately not fixed there. ADR-0054 carries the matching Correction of the same date.

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
`model/facility/zones.yaml` declares two `aabb` bounds and **no rule anywhere reads one against
the other.** A `cell_b` declared inside `cell_a`'s box validates clean, generates two worlds that
describe the same volume twice, and reports nothing.

Two independent reasons, and closing either alone would not close the gap.
`cite_tools.validate.geometric.check` takes a **single** `ResolvedCell`, and `cli.py` runs the
geometric level once per zone, so `_no_overlapping_bodies` — the rule that would notice two
solid bodies in one volume — only ever sees one zone's assets and can never be handed a pair
from different zones. And no rule at any level compares `Zone.bounds` to `Zone.bounds`; the only
thing that reads a zone's bounds is `_assets_inside_zone`, which asks whether a body is inside
**its own** zone.

Reproduce it — widen `cell_b`'s box in `model/facility/zones.yaml` until it swallows `cell_a`'s
whole, leaving every body exactly where it stands:

```bash
#   cell_b bounds: min_m [-1.000, 2.000, 0.000] -> [-1.000, -1.200, 0.000]
#                  max_m [ 3.000, 4.000, 2.500] -> [ 6.800,  4.000, 2.500]
./scripts/validate-model --write     # ok model valid — 2 zone(s) ... ; restore with git checkout
```

Run here on 2026-09-16: it exits **0** and reports the model valid, with `cell_b`'s zone now
containing all three of `cell_a`'s arms, its three belts and both its tables. Not one finding.
`--write` rather than a bare run, because a bare run fails on the byte-identity diff against the
committed tree — which fires for **any** model edit and says nothing whatever about this one.
That distinction is the trap: the first attempt at this recipe read the stale-tree error as the
validator noticing, and it was not.

Widening a zone is the mild version. Moving `cell_b`'s bodies into `cell_a`'s box as well is
equally silent, and produces two worlds that describe the same volume twice.

**Not fixed, deliberately** (ADR-0056, "What this costs us"). A guard written against the one
case we control is weaker than placing the cell correctly and recording why, which is what
`model/facility/zones.yaml` does: the comment on `cell_b`'s bounds states the 1.200 m of clear
air between the two boxes and states that nothing checks it. What a fix looks like is a
model-global rule beside the other model-global levels — `referential.py` and `physical.py` are
already model-global by construction — asking whether any two zones' boxes intersect. It is
worth writing when a third zone appears or when anyone moves one, whichever comes first.

**Nothing is known to be wrong today.** The two boxes are disjoint, and
`./scripts/validate-model` exits 0.

### #67 — A cross-zone station reference passes validation and then skips its reach check in silence
`referential.py` resolves station and flow references against **globally** known ids —
`_stations_reference_real_things` builds `known_assets` from `model.assets` and
`_flow_is_consistent` builds `known_stations` from `model.stations`, neither filtered by zone. So
a `cell_b` station naming `arm_1`, which stands in `cell_a` three metres away, is a **valid
reference**.

What makes it silent rather than merely permitted is what happens next.
`cite_tools.validate.geometric._stations_are_reachable` does `actor = cell.asset(station.actor)`
against the **resolved cell**, which holds only that zone's assets, and returns `None` for an
actor from another zone — at which point the rule `continue`s. The single most valuable check in
that module, the one its own docstring says pays for the file, is skipped with no finding at all
for exactly the station most likely to need it.

**IT IS `actor` AND ONLY `actor`, and this entry claimed more than that until 2026-09-17.**
It said the same shape applies to `pick_from` and `place_to` naming another zone's asset. It
does not. `resolve.py`'s `point` — the local function `_resolve_stations` calls for each
station point — raises `ResolveError` for an asset that is not in the resolved cell, and
`cite_tools/cli.py` catches it around its `geometric.check(resolve(...))` call, prints
`error resolve zone <id>: ...` and raises `typer.Exit(code=1)`. Both were re-read on
2026-09-17, and both are cited by symbol rather than by line because a line number in a file
under edit goes stale exactly as this claim did. So a cross-zone `pick_from` or
`place_to` **aborts the command with a diagnosis**, which is a different instrument from a rule
that reports a finding and is the opposite of silent. Only `actor` is unguarded, because
`_stations_are_reachable` reaches it through `cell.asset(...)` and treats `None` as nothing to
check rather than as something missing.

The distinction matters for whoever fixes this: an error that aborts `validate-model` cannot be
collected alongside other findings and cannot be downgraded with `--strict`, so a fix that gave
`actor` the same treatment would change the shape of the answer as well as its content.

Reproduce it:

```bash
sed -i 's/^    actor: picker$/    actor: arm_1/' model/topology/stations.yaml
./scripts/validate-model --write     # ok model valid — 2 zone(s) ... ; restore with git checkout
grep -n 'actor' workspace/src/cite_generated/topology/cell_b_flow.yaml
```

Run here on 2026-09-16: it exits **0** and reports the model valid, and
`cell_b_flow.yaml` then reads `actor: arm_1` against `b_transfer_1` — an arm three metres away in
another cell, whose reach to this station's pick point was checked by nothing. L4 would dispatch
a `cell_b` station's skills at a `cell_a` arm's action names, which on a one-zone-at-a-time
deployment is a station waiting for a server that is not running.

`--write` rather than a bare run, for the reason #66 gives: a bare run fails on the byte-identity
diff, which fires for any model edit and is not the validator noticing anything.

**Not fixed, deliberately** (ADR-0056, "What this costs us"), for the same reason as #66. The
shape of a fix is a referential rule requiring a station's `actor`, `assets`, `trigger.sensor`,
`pick_from.asset` and `place_to.asset` to be in that station's **own** zone — which is a rule
about the model rather than a guard against one mistake, and is worth writing as such. Note that
it is `referential.py` that owes it, not `geometric.py`: by the time the geometric level runs,
the cross-zone asset is simply absent, and a rule there could only report that an actor it was
told about does not exist.

**Nothing is known to be wrong today.** Every id a `cell_b` station names is a `cell_b` asset,
which `model/topology/stations.yaml` states in a comment beside them because nothing states it
mechanically.

### #68 — The one-zone-at-a-time refusal is sound and incomplete, in two named ways
[ADR-0056](adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md) decision 3
says exactly one zone is up at a time. `model_info.on_configure` now refuses a bring-up beside
another **declared** zone's names and says which zone that is, returning `FAILURE` so that
`simulation.launch.py`'s existing handler stops the launch. It is a synchronous graph-cache
query: nothing waits, and nothing is added to a clean bring-up. **It is therefore sound and not
exhaustive**, in two ways it is worth having written down rather than rediscovered.

**1. The discovery race.** DDS discovery is asynchronous. A zone started at the same instant as
this one may not be in the graph cache when `on_configure` runs, and will not be seen; the two
cells then come up together exactly as before. Closing it means concluding "I am alone" from an
**absence**, which needs a timeout — and a bring-up that waits a guessed interval to decide is
the timing guess CLAUDE.md P4 forbids. Refusing on a positive is an event; refusing on an
absence is not. A shape that would close it without a guess is a latched `ModelVersion`
subscription whose **arrival** is the event, with a rule for telling the newcomer from the
incumbent; nobody has designed that rule.

**2. The same zone twice.** Two `cell_b` bring-ups collide identically — one
`/cite/facility/get_model_version`, one `/clock` fed twice — and this rule says nothing about
them, because `cell_b`'s names are not foreign to `cell_b`. **Deliberate.** CI brings one zone
up twice in a row per run, and this project has a recurring teardown-leak history
(CLAUDE.md §2's teardown-family bullet); a rule that could not tell an unfinished teardown from
a second cell would convert a lingering process into a hard bring-up failure. Whoever closes it
needs a way to distinguish the two that does not rest on timing.

**That teardown-leak exposure is not confined to the same zone, and the argument above reads as
though it were.** The rule that IS enforced fires on any *declared* zone's names, so a `cell_b`
process that outlives its run and still holds `/cite/cell_b/...` makes the next
`./scripts/scenario bringup --zone cell_a` — ADR-0056's own named mitigation for a broken
showcase — fail at `on_configure`, naming `cell_b` as the intruder. Nothing is wrong with the
rule there: a live `cell_b` on the graph is exactly what it refuses on, and it cannot know the
process is a corpse. What is recorded here is the reading hazard. **A refused showcase bring-up
is evidence that `cell_b`'s names are on the graph and is not evidence that a second cell was
started**, and this repository's leak history makes the first far likelier than the second.
Check for a surviving process before attributing it to a cell nobody launched. The same-zone
case is excluded from the rule; the exposure the exclusion was reasoning about is not.

Reproduce the refusal working, without two simulators:

```bash
./scripts/enter dev python3 -c '
from cite_facility.artifacts import declared_zones
from cite_facility.occupancy import zones_already_on_the_graph
print(zones_already_on_the_graph(["/cite/cell_a/arm_1/move_to"], ["cell_b"], declared_zones()))
print(zones_already_on_the_graph(["/cite/cell_b/picker/move_to"], ["cell_b"], declared_zones()))'
```

The first prints `['cell_a']` — refused. The second prints `[]`, which is residual 2.

**Nothing is known to be wrong today**, and the invariant was enforced by nothing at all before
this: exactly one of the collisions ADR-0056 lists was loud, and only with `line:=true`.


### #69 — A second bring-up from one checkout destroys the first, whatever zone either is
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
`pair.py` forwards `line:=true` to **both** sides, so each side starts its own L4 coordinator,
which takes exclusive hold of that side's skills — and the boundary dispatches the operator's
goals to both sides' L3 servers at the same time. Three processes command the same arm names.

**It is bounded and it is not guarded.** `cite_skills`' `exclusive_goal` gate refuses a second
concurrent goal per arm (`skill_server.cpp`'s `claim`), so two commanders cannot overlap **within
one goal** — but nothing owns the arm **between** L4's goals, so an operator goal lands in the gap
between two line steps and the coordinator's next step follows it. Whether that is acceptable is a
decision about who owns an arm in a paired line, and no record takes it.

`./scripts/sim --pair --line` is reachable today (`_LAUNCH_STYLE` maps `line:=`), and **nothing
refuses the combination**.

**Not observed**: the combination is runnable on a clean checkout since `cell_b` was paired
(**ADR-0059**, 2026-09-18) — until then the model was `single` and it could not be run at all —
and no run of it is recorded here.

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
