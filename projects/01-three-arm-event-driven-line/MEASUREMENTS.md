# Measurements — `01-three-arm-event-driven-line`

This file is **this snapshot's measurement point**: from 2026-10-01 on, the measurements of the three-arm, event-driven line on zone `cell_a` — and of the `pick_and_place` and `continuous_line` scenarios that drove it, including their runs against `cell_b` before the fixed program — are kept
here: a measurement taken of this snapshot is appended, dated, with
the command, the commit, the machine and who took it — with the tree-hash bump in
`projects/snapshots.yaml` that every change to a snapshot needs (main-repository
`docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md`, amendment of 2026-10-01).
Earlier campaigns whose subject is this milestone remain under the main repository's
`docs/measurements/`, frozen where they are (its review queue's Q84 sorts them).
Whether the snapshot builds and runs is not a measurement of it in this sense: those runs are
in `PROVENANCE.md`'s verification log and stay there.

## Where the text below came from

On 2026-10-01 the main repository's `CLAUDE.md` was cut back to the project's identity, goal
and working discipline. The measurements it held whose subject had left the main tree came
here; everything else it held went to the main repository's
`docs/reference/claude-md-review-queue.md`. Each section below names the lines of
`CLAUDE.md` it came from, at main-repository commit `960e6b4`
(`git show 960e6b4:CLAUDE.md`).

- **This is a CLOSED RECORD.** Every figure was true at the commit and on the date it names,
  and none has been re-measured. Do not append to these sections; add a new, dated one.
- **The text is verbatim**, with three mechanical changes: common leading indentation was
  removed; Markdown links were turned into plain-text paths, because this folder may be copied
  out of the repository; and a section header and source line were added above each excerpt.
- **Paths are main-repository paths.** Several do not exist inside this folder —
  `docs/measurements/`, `CLAUDE.md` and the charter are not part of the extract.
- **"Above", "below" and "this file" inside an excerpt refer to the old `CLAUDE.md`**, not to
  this file. Some excerpts begin or end mid-sentence where the original paragraph was split
  between destinations; each such cut is marked.

## The closed-record notices that framed these figures

_Source: `CLAUDE.md` lines 838-853 at `960e6b4`._

**Until 2026-10-01 this bullet's opening sentence described `./scripts/sim --headless --zone
cell_a`: three arms, nine controllers, one detection server, the topology served and the L4
coordinator off unless `line:=true`. Everything below that names `cell_a`, `pick_and_place`,
`continuous_line`, `line:=true` or `./scripts/demo` is a CLOSED RECORD of a cell and of
scenarios that are no longer in the main tree** — not retired, not re-measured, and not to be
appended to.
**EVERY FIGURE IN THIS BULLET AND IN THE THREE BELOW IT IS `cell_a`'s, AND CI NO LONGER
DRIVES `cell_a`.** ADR-0056 landed on 2026-09-16: the three scenarios now drive `cell_b`,
a one-arm cell, and `cell_a` keeps `validate-model` and `build` coverage only. **[Overtaken
2026-10-01 — ADR-0069 removed `cell_a`, `pick_and_place` and `continuous_line` from the main
tree; main CI drives `bringup` twice and `program_cycle` on `cell_b`, and `cell_a` has no
main-tree coverage at all.]** So the CI
tables below — `bringup`'s 50 invocations, `pick_and_place`'s 25, the twenty-five-row
`continuous_line` table, the teardown-family split, the hull-run list — are a **closed**
record of a cell that is no longer driven. They are not retired and not re-measured:
they are records of runs, which stand whatever the model declares.

## `cell_b`'s first two CI runs, which still drove `pick_and_place` and `continuous_line`

_Source: `CLAUDE.md` lines 854-895 at `960e6b4`._

**CI HAS NOW DRIVEN `cell_b`, ONCE, AND THE RUN WAS CLEAN END TO END.** Run
`35267272730` at `ad25a22`, 2026-09-17: conclusion `success`, all three jobs `success`, and
**all four scenario invocations printed the BARE verdict** — `bringup` twice,
`pick_and_place` once, `continuous_line` once. The bare string is the load-bearing detail:
`scripts/scenario` prints it only when `launch_test` itself exited 0, which it cannot do
while a post-shutdown assertion is failing, **so cycle and teardown both passed in all
four**. The advisory branch fired nowhere. **Nothing exited badly anywhere in the run** — no
`move_group` `-11`, no `parameter_bridge` `-6`/`-11`, no `gz` `-9`. And the `frame_server`
stall did not fire: **4 `configured with` against 4 `published`**, every managed transition
heard.
Read with the instrument this section mandates — the whole verdict string, anchored, and
restricted to the three `Simulation-in-the-loop` step columns.
**That paragraph said "ONCE" and the second run has happened, so the count and the word
"clean" both move.** Run `35399988901` at `21b0b44`, 2026-09-18 — the merge that paired
`cell_b` (ADR-0059) — read with the same instrument. Its workflow conclusion is `success`
**and it is not a clean run**, which is the trap this file spends a paragraph on:
`bringup` printed the bare verdict **twice** and `pick_and_place` once, so those three are
cycle and teardown both; **`continuous_line` printed `passed its cycle assertions`**, the
advisory branch, with `Scenario 'continuous_line': the cycle passed and the post-shutdown
check did not.` beside it.
**Its cycle carried 3 of 3 work-pieces** — `wp_000001` … `wp_000003 reached b_accumulation;
3 completed` — on a runner nobody prepared, which is the strongest `continuous_line` evidence
this project has for either cell.
**What failed is the teardown, on `move_group-12 exited with -9`**, twice in that step's log,
against an allowance of `[0, 130, -11]`. **`move_group` at -11 is exempted and -9 is not**,
and **no exemption may be widened to absorb it**.
**It reproduces the local observation of 2026-09-18 exactly** — same process, same signal,
same scenario, same teardown — which makes **two events on two machines** and is a
reproduction of a *signature*, **not a diagnosis and not a rate**. `-9` is `SIGKILL`; the
teardown-family bullet below keeps that signal outside the set that family's split was
measured over, and it has been seen there on `gz` rather than on `move_group`. **Sharing a
teardown and a minus sign is not evidence of sharing a cause.**
**So the `cell_b` CI record is two runs: cycle 4 of 4 invocations in the first and 4 of 4 in
the second, teardown 4 of 4 then 3 of 4.** **It is not a rate, and it must not start one**:
`continuous_line` has failed 7 of 25 CI runs against `cell_a`, and two runs against `cell_b`
say nothing about how often it will. **Do not append a `cell_b` run to any count above** —
those close at `cell_a`; this is a separate record and it now has two rows.
**This is also the first time the advisory branch has fired for `continuous_line` anywhere.**
The paragraph below records that across `cell_a`'s twenty-five runs the middle string
appeared for `bringup` and `pick_and_place` and **never** for this scenario; that sentence is
a claim about those twenty-five and stays true of them, and it is no longer true of the
repository.

## Local scenario runs against the paired `cell_b` (2026-09-18)

_Source: `CLAUDE.md` lines 922-924 (to "friction stall.") and 941-955 at `960e6b4`._

_The rest of the `bringup` paragraph — its 3-of-4 result on the paired plan and the lost goal response behind the failure — moved on 2026-10-01 to the main repository's `docs/reference/claude-md-review-queue.md` (Q89), because `bringup` on `cell_b` is still a main-tree gate. The first sentence stays here because it also carries the `pick_and_place` run; the queue quotes it as context._

**`bringup` was run four times locally against a PAIRED `cell_b` on 2026-09-18, and it
passed 3 of the 4**, and `pick_and_place` — a **blocking** CI step on this zone — passed once
with the bare verdict and one genuine friction stall.
**`continuous_line` was run once against the paired zone's plant side and its two questions
came apart.** Its **cycle passed** — `wp_000003 reached b_accumulation; 3 completed`, three of
three work-pieces carried end to end, `Ran 1 test in 181.359s`, with **no** `escalated to an
operator` line anywhere. Its **post-shutdown teardown failed**: `FAIL:
test_nothing_of_ours_exited_badly … AssertionError: -9 not found in [0, 130, -11] :
move_group-12 exited with -9`. **That is not exempted and no exemption may be widened to
absorb it**: the allowance covers `move_group` at **-11**, and this is **-9**, `SIGKILL`.
**It is recorded and not classified.** `-9` is the signal the teardown-family bullet below
keeps outside the set that family's split was measured over, and it has been seen there on
`gz` rather than on `move_group`. **Sharing a teardown and a minus sign is not evidence of
sharing a cause**, and one event on one machine with nothing registered in advance is not a
rate. **It would not have gated CI**: that step carries `continue-on-error` *and*
`--teardown-advisory`, so it would have printed the advisory verdict — which this local run
did not, because an interactive run answers the strict question.

## Local scenario observations of 2026-09-17

_Source: `CLAUDE.md` lines 961-983 at `960e6b4`._

**Before that run the scenarios had been observed only locally**, on 2026-09-17, and those
readings stand as what they were:
**`bringup`: 2 of 2**, once per zone, under the **strict** policy rather than CI's
`--teardown-advisory` — the bare `ok Scenario 'bringup' passed`, which `scripts/scenario`
prints only when `launch_test` itself exited 0, so cycle **and** post-shutdown teardown
both. **`pick_and_place`: 2 runs, cycle 1 of 2**, the passing run `Ran 1 test in 68.393s`
with one genuine friction stall (`commanded 45.0 mm, reached 49.9 mm, stalled=true,
reached_goal=false -> holding`). **`continuous_line`: 2 runs, cycle 2 of 2 and teardown
1 of 2**, both runs carrying **3 of 3** work-pieces with three genuine stalls and **zero**
`escalated to an operator`, at `179.280s` and `139.612s`.
**Two of those four runs failed on the first attempt, and that is the part a summary would
drop.** Neither failure was this branch's: one is the `frame_server` stall — configure
succeeds, the node never activates, and the launch dies blaming the model — which reached
`pick_and_place` for the first time there and has now hit **3 of 11** scenario launches
across two scenarios; the other is a teardown in which `skill_server` and `move_group`
failed to terminate 105 s after `SIGTERM` and were `SIGKILL`ed. **No exemption absorbed
either**: the `-9` was reported, because the allowance covers `-11` for `move_group` alone.
Both are in `docs/open-work.md`, and **neither is attributed**.
**One earlier `bringup` failure was this branch's own and is fixed**: it failed 4 of 4 on
both zones because the scenario compared the published joint set against a dataclass repr,
which no gate could see since `./scripts/test` runs no scenario.
**All of it is one tester agent, one host, one or two runs per scenario, with nothing
registered in advance. It is a demonstration that the cell works and it is not a rate.**

## `bringup` in CI on `cell_a`: cycle and teardown

_Source: `CLAUDE.md` lines 984-1019 at `960e6b4`._

**It is not a scenario that always passes, and until 2026-08-28 nothing said so.** Thirty
consecutive local runs at `de67d8b` — taken for another purpose and published as
`docs/measurements/2026-08-27-teardown-signal-family/results.md`
— include runs that failed `bringup`'s own `MoveTo` assertion, not merely its teardown
check. That campaign's note on the finding is explicit that it is **not a pre-registered
rate** and that whether it still happens is **unmeasured**. **It still happens**: the same
`the MoveTo goal was never accepted` assertion failed **one local run of four** on 2026-08-29,
on the merged Phase 2.A branch, reported by the implementing agent — one more event, on one
machine, with nothing registered in advance, and not a rate either. Against that,
`bringup`'s **cycle** has passed **50 of 50** in CI: it runs twice per run and the
twenty-five runs listed in the `continuous_line` bullet below all passed its cycle twice.
**Its teardown is clean in 47 of the 50**, and the three exceptions are `f6a3779` and
`13bc8e9`, both 2026-09-07, and **`e18251e` on 2026-09-08** — in each of the three, one of
that run's two invocations printed `Scenario 'bringup' passed its cycle assertions` and the
other printed the bare verdict. **They are no longer the only advisory verdicts in CI**:
`pick_and_place` printed one in that same `e18251e` run, which is the bullet below. That is a
statement about the twenty-five tabled `main` runs, twenty-two of them read on 2026-09-07,
the twenty-third on 2026-09-08 and **the last two read here on 2026-09-08 from their own
logs**, and about nothing
else. The cycle figure said
**12 of 12 across the six** until 2026-09-01, **36 of 36 across the eighteen** later that
day, **38 of 38 across the nineteen** until 2026-09-07, **44 of 44 across the twenty-two**
until 2026-09-08 and **46 of 46 across the twenty-three** for part of that day,
each right over the runs that
existed then; **until 2026-09-07 no teardown figure was stated separately at all**, because
until then no `bringup` teardown had failed in CI and the two questions had never come
apart, and the teardown figure read **44 of 46** until 2026-09-08.
**The 46 → 50 and 44 → 47 steps are different sizes and that is the whole point of stating
them apart.** Two runs added four invocations, all four of which passed their cycle, and
three of the four had a clean teardown: `aed36c4`'s two were both bare `passed`, and
`e18251e`'s were one bare and one advisory. 46 + 4 = 50 and 44 + 3 = 47.
**That the `13bc8e9` run's other `bringup` invocation passed its cycle is inferred, not
read.** The scenario step is blocking and `pick_and_place` and `continuous_line` ran after it
in that run, which they cannot do if it exited non-zero (`.github/workflows/ci.yml`: only the
`continuous_line` step carries `continue-on-error`). Say it that way rather than as a
reading; the advisory verdict itself is what was read.

## Vendor and hull geometry inside the `bringup` figures

_Source: `CLAUDE.md` lines 1072-1077 at `960e6b4`._

**Thirty-six of the fifty are on vendor collision geometry and fourteen are on convex
hulls** — the last seven rows of that table are the runs taken on the geometry this
repository ships; it said "two are on convex hulls" and "the last row" until 2026-09-07,
"eight" and "the last four rows" until 2026-09-08, and "ten" and "the last five rows" for
part of that day. **The vendor half has stopped moving and only the hull half grows**, which
is what has to happen once the selection changed.

## A local pair of runs at `37921dd`

_Source: `CLAUDE.md` lines 1078-1087 at `960e6b4`._

**One local pair of runs was taken on `feat/hosted-by-derived` and enters none of the CI
figures above.** At `37921dd` — that branch's second commit, not its tip `df91154` — with
`CITE_PHYSICS_SEED=42`, `bringup` printed the bare verdict `Scenario 'bringup' passed`, so
its cycle and its post-shutdown teardown were both clean, and `pick_and_place`'s cycle passed
**2 of 2** with one of those two runs failing its teardown on `gz-1 exited with -9`. **One
machine, one commit, two scenarios, no thresholds registered in advance, reported by the
`tester` agent that ran them and not re-run by the pass that wrote this down.** It is local,
so it moves no count in the CI tables in this section, and it is not at the tip. The `-9` is
the signal the teardown-family bullet below records as outside the set that split was
measured over and still unclassified.

## The line stop (ADR-0038)

_Source: `CLAUDE.md` lines 1186-1204 at `960e6b4`._

- **A station's escalation stopped the line and left the coordinator alive to serve that
  reset** (ADR-0038 (`docs/adr/0038-stop-the-line-without-ending-the-process.md`)). **This whole
  bullet describes `cite_orchestration`, which left the main tree with ADR-0069 on 2026-10-01
  and runs only in the `projects/01` snapshot; its present tense below is the tree before that
  date.** The one consequence that still binds the main tree is the P2 point that **a physical
  belt's setpoint persists**, which the twin boundary's belt route acts on. The
  generated root was a bare `Parallel`, so an escalating station failed the root, ended the
  tick loop and exited the process — which tore the whole cell down and took the evidence of
  the fault with it. The root is now a `Fallback` over that unchanged `Parallel` and a fault
  `Sequence` of `OnFault → StopAll → AwaitReset → AwaitReArm` in `line_fault.hpp`. A latched
  fault still exits 1 on **either** route into the branch, so a run in which the line stopped
  still fails CI.
  **`StopAll` is a P2 fix, not a convenience**, and it gives `ConveyorIndex::stop()` its first
  production caller. The simulated belts stopped by accident — Gazebo died with the launch and
  there was no belt left to run; a physical belt is a VFD and **a setpoint persists**. Identical
  command path, divergent consequence, and only the simulated half has ever been observed.
  **It is a state machine, not a protective measure.** What it buys is that the coordinator
  is still there to be asked a question, and that it stops commanding belts it has stopped
  supervising.

## `pick_and_place`

_Source: `CLAUDE.md` lines 1391-1422 at `960e6b4`._

**The cycle passed 6 of 6** in the measurement the implementing agent took on 2026-08-26,
in one isolated freshly built tree on one machine, every run reporting a genuine friction
stall. **The scenario verdict in those same runs was 5 of 6**: one run passed the cycle and
then failed the post-shutdown teardown check. No thresholds were registered in advance and
this is not a claim about any other machine.
**The wrong pass count named above was this bullet's.** It said 8/8; those runs executed
another worktree's binaries through shared Docker volumes, and the number arrived here
supplied rather than measured. Each checkout is now isolated and `lint`/`test` refuse to
answer from a stale build tree — **measure it yourself anyway.**
**`./scripts/scenario pick_and_place` was a blocking CI step**, promoted at `c1e9e03`, **until
ADR-0069 removed it from the main tree on 2026-10-01**; it runs only in the `projects/01`
snapshot now, and **no scenario in main CI drives `Pick` or `Place`** — ADR-0069 lists that
under "Coverage given up". Everything below in this bullet is a closed record. CI
passes `--teardown-advisory` to every scenario, splitting the two questions a scenario
answers in one exit code: **the cycle is gated, the post-shutdown teardown is reported and
not gated.** The flag is off by default, so an interactive run still answers the strict
question. Read `scripts/scenario`'s header and the phase-split block in `scripts/_lib.sh`
before treating a teardown failure as a gate — and never answer one by widening a tolerance.
**Its two questions have now come apart in CI, and until 2026-09-08 they never had.** Over
the twenty-five tabled `main` runs in the bullet below — one `pick_and_place` invocation
each — **the cycle has passed 25 of 25 and the teardown is clean in 24 of the 25**. The one
exception is `34258470163` at `e18251e`, which printed
`Scenario 'pick_and_place' passed its cycle assertions` and failed
`test_nothing_of_ours_exited_badly` on `AssertionError: -9 not found in [0, 130] : gz-1
exited with -9`; read here on 2026-09-08 with the instrument the `bringup` bullet mandates.
**This file stated one figure where there are two until that date** — the hull paragraph
below said `pick_and_place` "passed in all twenty-three tabled runs: 22 of 22 by exact-string
match … so 23 of 23", and that string was the bare verdict, so it was a claim about the cycle
**and** the teardown at once. The cycle half of it survives the twenty-fourth and
twenty-fifth runs untouched; the teardown half does not, and is stated separately from here
on. **Nothing here attributes the `-9`** — see the teardown-family bullet below, which is
where that process and that signal are kept and where they stay unclassified.

## The event-driven line in CI: `continuous_line`

_Source: `CLAUDE.md` lines 1423-1781 at `960e6b4`._

- **The line has completed in eighteen of the twenty-five CI runs that have driven it, and
  this
  is still the least-settled claim in this file.** **CLOSED RECORD since 2026-10-01**: the line
  and `./scripts/scenario continuous_line` left the main tree with ADR-0069 and run only in the
  `projects/01` snapshot, checked by the weekly, non-blocking `.github/workflows/projects.yml`;
  nothing in main CI drives them, and no row may be appended to this bullet's tables. The
  present tense below is the tree before that date. It read "three of the six" until
  2026-09-01, "fourteen of the eighteen" later that day, "fifteen of the nineteen" until
  2026-09-07, "sixteen of the twenty-two" until 2026-09-08 and "seventeen of the twenty-three"
  for part of that day, and **the extra runs make the
  count look better without making the
  finding go away**: the three-of-six failures are all still there, they are still
  unreproduced locally, and there are now **three distinct failure signatures among seven
  failures**, not one among four — a spawn timeout joined on 2026-08-31 and a pair of
  escalated aborts joined on 2026-09-02.
  **The set of signatures did not grow on 2026-09-08; the spawn timeout did.** The seventh
  failure, `34258470163` at `e18251e`, is the **second** occurrence of the spawn-timeout
  signature, eight days and thirteen table rows after the first — row 24 against row 11. **That is a count inside one
  signature and not a fourth signature**, and it is also not a rate: two events, at two
  commits, on two runners nobody prepared, with nothing registered in advance. Neither
  occurrence is attributed, and the reasons the first was not attributed are unchanged.
  `./scripts/scenario continuous_line` drives the three-arm sensor-driven line: the aid
  topics are bridged, `Detect` turns a beam level into a typed `DetectionEvent`, L4 stops the
  belt on that edge and restarts it on `CompleteHandoff` (ADR-0032), and the beam indexes on
  the part's body rather than its origin (ADR-0033). It runs in CI as `continue-on-error`.
  **A harness had been doing L4's job, and this is the sharpest example in this file of why a
  green run is not evidence.** ADR-0032 gave the belt setpoint an owner in L4 on 2026-08-26
  and that owner delivered nothing: `ConveyorIndex` creates its publishers inside the topology
  callback and published from the same callback, and **reliable QoS is a promise to *matched*
  subscribers**, of which there were none at that instant. The belts were being started by the
  scenario's own repeated sends. Every `continuous_line` figure recorded before 2026-08-27 was
  produced with the test harness compensating for a defect in the thing under test. Fixed
  event-driven — a subscriber matching is treated as an event — and the pre-fix counts are not
  re-measured.
  **What has been measured since, in the order it was taken.** All of it is on one machine
  with **no thresholds registered in advance** and **no directory in
  `docs/measurements/README.md`**; these are the size of the evidence,
  not a campaign.
  - Fixing agent, 2026-08-27, three runs: cycle **3 of 3**, teardown **3 of 3**.
  - Project owner, 2026-08-27, three runs, independent: cycle **3 of 3**, scenario verdict
    **1 of 3**. Both failures were teardown-only. **The cycle figure replicated and the
    teardown figure did not** — "the line works" and "the scenario is green" are not the same
    claim.
  - Most recent local run, one run: **3 of 3** work-pieces carried end to end, all four beams
    firing at every station, all nine grasps reporting a genuine friction stall, and cycle and
    teardown passing separately. It is better than anything above it. **The tester's own
    reading is that it is one good sample and not a new baseline**, and that is how it is
    recorded here. Do not promote a gate on it.
  **CI has now run it twenty-five times, and this is the only body of `continuous_line`
  evidence nobody's local environment could have flattered.** Every one of the twenty-five was
  on `main`, on a runner nobody prepared. It said "nineteen times" until 2026-09-07,
  "twenty-two" until 2026-09-08 and "twenty-three" for part of that day. Read by
  grepping each run's log for the scenario's own verdict
  line, because **the step conclusion lies**: the step is `continue-on-error`, and
  `gh run view <id> --json jobs` reports it `success` whether the scenario passed or failed —
  verified on 2026-08-29 against `33158091922`, whose `continuous_line` is *known* to have
  failed and which the API still calls `success`. The instrument is
  `gh run view <id> --log | grep "Scenario 'continuous_line'"`, **restricted to that
  scenario's own step column, `Simulation-in-the-loop scenario — continuous_line (advisory)`**
  — the `bringup` bullet above records what a
  whole-log grep counted instead, and records that there are three scenario step names rather
  than the one this line named until 2026-09-08.

  | CI run | date | commit | cycle |
  |---|---|---|---|
  | `33158091922` | 2026-08-28 | `60eb4a5` | **failed** — 1 of 3 |
  | `33208064683` | 2026-08-28 | `a8f1e3d` | **failed** — 2 of 3 |
  | `33235590086` | 2026-08-29 | `f1f914f` | passed |
  | `33241186260` | 2026-08-29 | `7afb2c6` | passed |
  | `33244350584` | 2026-08-29 | `3d23999` | passed |
  | `33261637940` | 2026-08-29 | `29068d4` | **failed** — 2 of 3 |
  | `33288010305` | 2026-08-30 | `b8a6c10` | passed |
  | `33290887432` | 2026-08-30 | `3f68a47` | passed |
  | `33298445106` | 2026-08-30 | `5c2990f` | passed |
  | `33331623351` | 2026-08-30 | `aafae47` | passed |
  | `33343317444` | 2026-08-31 | `3b8cd19` | **failed** — see below, a different signature |
  | `33377192704` | 2026-08-31 | `b6efc95` | passed |
  | `33398446772` | 2026-08-31 | `35ff5be` | passed |
  | `33424510102` | 2026-08-31 | `d35eca9` | passed |
  | `33438471901` | 2026-08-31 | `d7b1097` | passed |
  | `33472144723` | 2026-09-01 | `d79a856` | passed |
  | `33479867459` | 2026-09-01 | `2cf66df` | passed |
  | `33485617966` | 2026-09-01 | `c0badfb` | passed |
  | `33501707588` | 2026-09-01 | `e51238e` | passed — **the first row measured on convex hulls** |
  | `33575992281` | 2026-09-02 | `4ef2d7c` | **failed** — a third signature, below |
  | `33603610958` | 2026-09-02 | `51195e0` | **failed** — the same third signature |
  | `34085965578` | 2026-09-07 | `f6a3779` | passed |
  | `34247027502` | 2026-09-07 | `13bc8e9` | passed |
  | `34258470163` | 2026-09-08 | `e18251e` | **failed** — 2 of 3, the spawn signature a second time |
  | `34280056331` | 2026-09-08 | `aed36c4` | passed |

  **Eighteen of twenty-five is a count over the runs that exist, not a rate** — no thresholds
  were registered in advance and the twenty-five sit at twenty-five different commits. The
  table
  said **three of six** until 2026-09-01, **fourteen of eighteen** later that day,
  **fifteen of nineteen** until 2026-09-07, **sixteen of twenty-two** until 2026-09-08 and
  **seventeen of twenty-three** for part of that day, each
  right
  over the runs that existed when it was written; the
  twelve rows below `29068d4` were read on 2026-09-01 by the instrument named above, over every
  completed `main` run since, **every one of the nineteen rows was re-read by that
  instrument at `abdae38`**, reproducing the table exactly, and **all twenty-two rows then
  existing were
  re-read again on 2026-09-07**, this time with the whole verdict string anchored at both ends
  rather than matched as a prefix, reproducing the table exactly again.
  **The twenty-third row is weaker than the twenty-two above it and is marked so.** It was read
  on 2026-09-08 by the agent that supplied it, with the whole verdict string anchored and
  restricted to the scenario step column, and **it was not re-read by the pass that wrote it
  here**: `gh` was present on this host but unauthenticated, so no CI log could be opened at
  all. Everything in this file about run `34247027502` — its `continuous_line` verdict, its
  `pick_and_place` verdict and its `bringup` teardown — carries that one reading and no
  second one. **That weakness is not inherited by the two rows below it**: `gh auth status`
  reports this host authenticated as of 2026-09-08, and both new rows were read here from
  their own downloaded logs.
  **The twenty-fourth and twenty-fifth rows were read on 2026-09-08 at `6d51966`**, each by
  `gh run view <id> --log` into a file and then the step-restricted anchored match the
  `bringup` bullet gives. `34280056331` prints one line, `Scenario 'continuous_line' passed`.
  `34258470163` prints one line, `Scenario 'continuous_line' failed — 1 cycle assertion(s)
  failed`.
  **The last seven rows are the ones taken on the geometry this repository ships**, and the
  collision-geometry item in the gap list below is where that is kept; this file said "the
  last row is the only one" until 2026-09-07, "the last four rows" until 2026-09-08 and "the
  last five rows" for part of that day.
  **The prediction the previous re-audit made here was wrong, and how it was wrong is the
  point.** It said *"The next reader should not expect a twentieth soon"*, on the strength of
  five completed `main` runs after `e51238e` — `33534312429`, `33537296558`, `33551642119`,
  `33553778365` and `33567737946` — that all failed at the `Test` step and therefore
  **skipped** all three scenario steps (`gh run view <id> --json jobs`, read over all five on
  2026-09-01; that reading is not disturbed). **The next scenario-driving run started about
  eighteen minutes after the re-audit's own run did** — `33574775657` at `abdae38` was created
  2026-09-02T00:18Z and `33575992281` at `4ef2d7c` at 2026-09-02T00:36Z
  (`gh run list --branch main --json createdAt`) — and two more followed. The full account of
  the window, from
  `gh run list --branch main` on 2026-09-07, is those five plus **two cancelled runs that
  reached no scenario at all** — `33550148315` at `1b4c07b` and `33574775657` at `abdae38`,
  each with **no verdict line of any kind** in its log — plus the three new table rows. The
  five-run list was never wrong about those five; it was **incomplete as an account of the
  window**, because it omitted `33550148315`, which was already cancelled when it was written.
  A forecast about CI is not a measurement and should not be written in a rulebook.
  **The account of the window since `13bc8e9` is complete and short**, from
  `gh run list --branch main` on 2026-09-08: the two new table rows and **one run still in
  progress** — `34284120566` at `6d51966`, created 2026-09-08T22:05:52Z, which has reached no
  scenario verdict and is in no figure here. **No run exists for `dd6772f` at all**
  (`gh api repos/:owner/:repo/commits/dd6772f/check-runs` reports `total_count` 0, read on that
  date): it and `6d51966` were pushed together, so only the tip was built. **A commit on `main`
  is not a CI run**, and counting commits would have produced a twenty-sixth row that never
  ran. No forecast is made here about what `34284120566` will say.
  **Teardown is read for eighteen of the twenty-five and is clean in all eighteen, and this
  file
  said it was unread until 2026-09-01, read for fifteen of nineteen until 2026-09-07, for
  sixteen of twenty-two until 2026-09-08 and for seventeen of twenty-three for part of that
  day.**
  The verdict line distinguishes **three** states, not
  two: `scripts/scenario` prints `Scenario 'X' passed` only when `launch_test` itself exited 0,
  which it cannot do while a post-shutdown `TestCleanShutdown` assertion is failing; it prints
  `Scenario 'X' passed its cycle assertions` on the advisory branch where the cycle passed and
  teardown did not; and `Scenario 'X' failed — …` otherwise. **The middle string appears for
  `continuous_line` in none of the twenty-five runs**, so each of the eighteen bare `passed`
  verdicts carries its teardown with it, and in the seven whose cycle failed teardown is masked
  by the cycle failure and stays genuinely unread.
  **This file said until 2026-09-07 that "the advisory branch has never fired in CI", and
  that is now false.** It appears **four** times in the twenty-five runs' logs and still
  **never for this
  scenario**: at `f6a3779`, and again at `13bc8e9`, one of the two `bringup` invocations printed
  `Scenario 'bringup' passed its cycle assertions`; and at `e18251e` **both** a `bringup`
  invocation and `pick_and_place` did. It said "exactly once" until 2026-09-08 and "twice … on
  consecutive runs" for part of that day —
  counts over the runs that existed then.
  **The clause "and never for this scenario" was the only durable half and it is worth keeping
  separate**: three of the four appearances are `bringup`'s and one is `pick_and_place`'s, and
  the sentence about `continuous_line` has not been falsified once. The rest of it was a claim
  about what has never happened, and §2 has now been caught by that **three** times.
  **`--teardown-advisory` never reaches the scenario Python**: `scripts/scenario` puts it in
  `TEARDOWN_POLICY` and not in `LAUNCH_TEST_ARGS`, so the post-shutdown assertions always run
  and the flag only decides how their failure is reported. **`scripts/scenario` is correct here
  and is not to be changed on the strength of this paragraph** — what was wrong was the reading
  of it, not the instrument.
  **The fourth failure is not the other three, and that was the finding of the 2026-09-01
  re-audit.**
  `33343317444` never reached a milestone at all: its cycle assertion is
  `subprocess.TimeoutExpired` on `ros2 run ros_gz_sim create -file /tmp/cite_workpiece.sdf`
  after **120 s**, so the work-piece was never spawned and the line was never given anything to
  carry. That is the spawn path, not the transfer stall — and it must not be folded into the
  three below on the strength of sharing a scenario name.
  **This file called it "one event" until 2026-09-08. It is two, and the second one carried
  two work-pieces end to end first.** `34258470163` at `e18251e` fails on the same exception
  from the same command — `subprocess.TimeoutExpired: Command '['ros2', 'run', 'ros_gz_sim',
  'create', '-file', '/tmp/cite_workpiece.sdf', '-name', 'workpiece', '-x', '-0.475', '-y',
  '0.0', '-z', '0.63']' timed out after 120 seconds` — raised through
  `cite_bringup/gz.py`'s `run` from `_spawn_workpiece`, read here from that run's own log on
  2026-09-08. **Where the two differ is how far the run got before it**, and that is why the
  table row says 2 of 3 rather than 0 of 3: pieces 1 and 2 each walked the whole ten-milestone
  ladder, `line_orchestrator` printed `wp_000001 reached station_accumulation; 1 completed` and
  then `wp_000002 … 2 completed`, and the six grasps in those two carries all reported a
  genuine friction stall (`commanded 45.0 mm, reached 49.5–49.9 mm, stalled=true,
  reached_goal=false, effort=60.0 -> holding`, six occurrences in that run's
  `continuous_line` step). The timeout is on the spawn of
  **piece 3**, about 122 s after piece 2's last milestone, and `Ran 1 test in 890.871s`.
  **So "never reached a milestone at all" describes the 2026-08-31 event and not this one**, and
  the shared thing is the exception and the command, not the state of the line.
  **Nothing about either is attributed and the second adds no attribution.** It is still not
  established whether this is the partition defect class §10 names, a starved runner, or
  something else. **The line was not stopped**: no `escalated to an operator` line appears in
  that run's `continuous_line` step, no station reported `BLOCKED` — the eight `BLOCKED` strings
  in that step are `detection_server` reporting beam levels — and the raise came from
  `_spawn_workpiece` before any milestone loop. **So `30baea8`'s halt check and `_context`
  report were not on this run's path**, and the sentence below saying no run of the cell has
  exercised them survives its first CI failure since it was written. Two events, at
  two commits, on two runners nobody prepared, eight days apart, with nothing registered in
  advance. **That is not a rate**, and a second occurrence of an unattributed signature is a
  second occurrence and not a diagnosis.
  **The other three failures have the identical signature**, which is the finding: a work-piece
  reaches milestone 2 of 10, `lifted(station_transfer_1: cell_a__table_pick__surface)`, never
  reaches milestone 3, `on_link(station_transfer_1: cell_a__conveyor_1__infeed)`, and times
  out on the 420 s leg ceiling with `station_transfer_1` reporting `WAITING`, occupancy 1/1
  and the piece still assigned to it. **In all three of those `LineState` read `RUNNING` with
  `blocked_reason=none stall_reasons=none`.** `station_transfer_1`'s inbound edge in the
  generated topology is `via: null`, so ADR-0039's detector has no belt setpoint to read and
  is structurally silent there — the blind spot that record names.
  **The three runs end with the part at the same pose to the millimetre**, held in the air for
  the rest of the leg: `(-0.001, 0.273, 1.201)`, `(-0.001, 0.273, 1.201)` and
  `(-0.001, 0.274, 1.201)`, each about 390 s after the peak of the lift. **So the grasp is not
  what failed** — `lifted` is *measured*, computed by the scenario as
  `sample.z - self._resolve(milestone.frame)[2] > LIFTED_M` — in that file's `milestone.kind == "lifted"` branch,
  cited by symbol because the line number given here (`674-675`) was stale by 2026-09-08 and a
  line number in a file under active edit goes stale again — rather than
  reported by the arm, so the piece demonstrably rose off the pick frame and never came back
  down.
  **What stops the piece between those two milestones is now established, by one
  investigation and not by a campaign.** The gripper's *result* timed out on a wall-clock
  deadline supervising a simulation-time process, `Pick` returned `TIMEOUT` without ever
  saying what the gripper did, and the retry's own `MoveToHome` carried the part **off** the
  beam the station was about to wait on again — so the station re-entered `AwaitTrigger` on a
  beam that had gone clear and stayed clear, holding the piece. Two layers, two records, both
  written 2026-08-29:
  ADR-0045 (`docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md`) for the L3
  deadline and ADR-0046 (`docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md`)
  for the L4 retry. **Both stay `Proposed`, and both are now implemented and merged on `main` at `c555440`.** The
  status does not move because what would move it is a `continuous_line` run on a CI runner in
  which the gripper fails to answer and the line reports it, and **no such run exists** — a
  run in which the gripper answers quickly shows nothing at all. **What is evidenced is the
  mechanism, not the outcome:** a launch test holds simulated time still while the wall clock
  passes the constant the old code compared against, then advances simulated time past the
  declared value and requires the wait to end, the cancel to be sent and the report to say
  custody is unestablished; unit tests on the shipped station tree require a station that
  still holds its work-piece to be refused its retry and to go `STATE_BLOCKED`. Both ADRs were
  corrected on 2026-08-30 in that review — see each record's Correction section.
  **Every timing figure in those records is reported by the project owner's investigation and
  was not re-measured**, including the on-demand reproduction under CPU starvation — no
  thresholds registered in advance, no directory in
  `docs/measurements/README.md`, and both records say so in their own
  verification tables. What *is* checkable in the mechanism — the constant, the clock it is
  compared against, the controller's terminating rule read upstream, the recovery branch, the
  topology edge — was read from source and is tabulated there. Cite the records; do not copy
  their numbers around (P1).
  **This supersedes the account that called `33158091922` "the only one ever taken off a
  developer machine".** It also means the local sets above and the CI set disagree, and that
  the disagreement is now a repeated failure rather than a single one.
  **The fifth and sixth failures are a third signature, and unlike the other four the line
  said so.** `33575992281` at `4ef2d7c` and `33603610958` at `51195e0`, both 2026-09-02, fail
  with the same assertion character for character apart from its timestamp — `the line stopped
  while waiting for the work-piece 'workpiece' to leave the simulator. BLOCKED at <t>:
  station_transfer_1: result code 10: escalated to an operator` — followed in both by
  `1 not found in [0, 130] : line_orchestrator-30 exited with 1`. The two tracebacks name the
  same four frames at the same four line numbers, and each log carries **3**
  `escalated to an operator` lines emitted by `line_orchestrator`, against **0** in the run
  that passed. **Count the emitter, not the string**: `grep -c "escalated to an operator"`
  returns 20, 20 and 16 over the three runs, because seventeen or sixteen of those come from
  `skill_goals_test` and `line_nodes_test` in the `Test` step and have nothing to do with the
  scenario. That raw count was nearly written into this file as the signature.
  **This is not the silent dead end and must not be folded into it.** In the three failures
  above, `LineState` read `RUNNING` with `blocked_reason=none stall_reasons=none` and nothing
  escalated; here the station reports `BLOCKED`, the coordinator escalates, the belts are
  commanded to a standstill and the process exits 1 — which is what ADR-0038 specifies. It is
  also not the spawn timeout at `33343317444` or the one at `e18251e`. Three signatures, seven
  failures; sharing a scenario
  name is not evidence of sharing a cause, which is the move this bullet already warns against
  for the fourth failure. It said "six failures" until 2026-09-08, and **the signature set did
  not change when the seventh arrived** — three, two and two.
  **That sentence ended "so the scenario's fail-fast fired as designed rather than waiting out
  the leg ceiling" until 2026-09-08, and that clause was false.** Two independent readings say
  so. **Timestamps:** from the coordinator's first `escalated to an operator` line to the
  `AssertionError` is **417.8 s** at `4ef2d7c` and **420.6 s** at `51195e0`, against
  `LEG_CEILING_S = 420.0` — the ceiling was spent in full, and those figures are the
  investigation's, read from the two CI logs and **not re-read here**. **Source:** through
  `13bc8e9`, and identically at both failing commits, `_run_one_piece`'s per-milestone loop
  contained no halt check at all — neither `self._halt` nor `_fail_if_the_line_has_stopped`
  appears between its definition and `_context` at `4ef2d7c`, `51195e0` or `13bc8e9` — and
  `_fail_if_the_line_has_stopped` was reached only from `_spin_until`; what finally raised was
  the *removal* wait's pre-loop check, which is why the message named the work-piece leaving
  the simulator — a wait with nothing to do with the fault — and carried none of the diagnostic
  report, because `_context` was built at the verdict step and every earlier raise skipped it.
  That half was re-derived on 2026-09-08 with `git show <sha>:tests/scenarios/continuous_line.py`
  over all three commits.
  **It is fixed at `30baea8` on `main`, and what the fix evidences is narrow.** The leg loop
  gained a halt check and `_fail_if_the_line_has_stopped` now appends the full `_context`
  report on every path that raises. The guard is
  `tests/scenarios/guards/test_a_stopped_line_ends_the_run.py`, and it **fails 6 of its 9**
  against the pre-fix scenario and **passes 9 of 9** after — re-derived on 2026-09-08 by
  running that file from `30baea8` against a worktree at `13bc8e9`, then in this checkout.
  **It is a guard over a fabricated clock and a fabricated `LineState`, not a run of the
  cell**: it drives the shipped functions unbound against a fabricated `self` and brings
  nothing up. **No run of the cell has exercised the new path.** So what is evidenced is that
  the code can now end a run promptly and print the report; nothing here says the next failure
  of this kind was, or will be, reported that way.
  **What the logs record above the escalation, stated as what the log says and not as a
  cause.** In both runs `/cite/cell_a/arm_1/place` returned code 10, after the arm's
  `JointTrajectoryController` aborted — `State tolerances failed for joint 2` and `Aborted due
  to goal_time_tolerance exceeding by 0.506172 s` at `4ef2d7c`, `0.506390 s` at `51195e0`.
  **Why the arm stopped part-way is not established** and nothing here attributes it. The
  chain from an execution-side tolerance (ADR-0036) through the classifier (ADR-0037) to the
  stopped line (ADR-0038) is visible in both logs and **absent from the scenario half of
  `f6a3779`'s**, whose only code-10 lines come from `skill_goals_test` and `line_nodes_test`.
  Whether any of the nineteen runs before these contains the same chain was **not checked** —
  for those nineteen only the verdict lines were re-read.
  **What an investigation added on 2026-09-08, at investigation strength: read from those two
  logs, on two runs, with nothing registered in advance and no cause attributed.** The skill is
  `Place` and the motion is its **final descent onto the release pose** — the fifth trajectory
  of the piece, after `Place`'s own approach had reported `Goal reached, success!` — so the arm
  was over `cell_a__conveyor_1__infeed` **holding the part** when it failed. The joint is
  **`arm_1_joint3`**, and the log's `State tolerances failed for joint 2` names that same joint
  rather than a second one: the controller prints a **zero-based index** into its own `joints:`
  list, which for `arm_1_joint_trajectory_controller` is `joint1 … joint5`
  (`workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml:47-52`), and upstream
  prints `joint_idx` as an index into the error arrays (`ros2_controllers`, `jazzy`,
  `joint_trajectory_controller/include/joint_trajectory_controller/tolerances.hpp`, read
  2026-09-08). **Those two source facts are re-derived here; every log-derived figure in this
  paragraph and the next is the investigation's and was not re-read.**
  **The arm was stationary or drifting further from its goal, not converging, and this is the
  strongest thing the investigation produced.** Recovered two independent ways that agree — the
  limiter's clamped command plus one control cycle of that joint's 3.14 rad/s limit, against
  `actual + reported error` — the implied movement over the last cycle is **1.0e-4 rad** at
  `4ef2d7c` and **4.3e-6 rad** at `51195e0`. **That is what rules out a scheduling lag**: a lag
  closing on its target would show the opposite velocity sign.
  **It violates a deliberate design margin.** `PlaceAt`'s `release_height_m` default is
  **0.04** against a 50 mm part whose centre rests at 0.025 — a deliberate **15 mm** air gap,
  stated in that port's own comment
  (`workspace/src/cite_orchestration/include/cite_orchestration/skill_nodes.hpp:675-686`, read
  2026-09-08) — so nothing should touch the belt during that descent.
  **Nothing in the cell changed to explain the onset, and option F is not the discriminator.**
  Between the last passing hull run `e51238e` and the first failure `4ef2d7c`, the diff over
  `workspace model tools tests scripts .github assets` is **one test file**
  (`cite_test_hardware/test/test_unreachable.py`). And `git merge-base --is-ancestor d3eeac4
  <sha>` fails for `4ef2d7c`, which failed **without** option F, and succeeds for `51195e0`,
  which failed **with** it, and for `f6a3779`, which **passed** with it. Both re-derived on
  2026-09-08.
  **The physical cause is unestablished and nothing above attributes one.**
  `docs/open-work.md` #60 is where the item and the cheapest measurement
  that would settle it are kept.
  **Neither run is evidence for ADR-0045's or ADR-0046's promotion condition, and it would be
  easy to read it as such.** That condition is a `continuous_line` run in which *the gripper
  fails to answer and the line reports it*. Result code 10 is `MOTION_INTERRUPTED`, ADR-0037's
  classification of a trajectory that stopped part-way; **no gripper deadline expiry appears
  in either scenario** — the only `returned code 9` lines in either log come from the
  `line_nodes_test` unit test, not from the cell. That these failures land at the same station
  as the three silent ones is a **hypothesis and nothing more**; it is unestablished, an
  investigation is running separately, and its result may not be anticipated here.
  **Two events, on two CI runners nobody prepared, at two commits, with nothing registered in
  advance. That is not a rate.**

## Teardown signal deaths in CI and locally

_Source: `CLAUDE.md` lines 1825-1877 at `960e6b4`._

**Run duration is retired as a predictor.** Three `continuous_line` runs on one machine on
2026-08-27 took **478.055 s (passed), 480.607 s (failed) and 497.710 s (failed)**. The
longest did fail, so duration is not *uncorrelated* — but 2.5 s separating a pass from a fail
rules it out as the mechanism. The comment in `tests/scenarios/continuous_line.py` still
asserts the duration correlation and has not been updated. The superseded account also named
`parameter_bridge` (-6) and `gz` (-9); those two are outside the set the split was measured
over and are not classified here. `parameter_bridge` has since been observed on **both** -6
and -11 in the campaign cited above, each once — which is what removes "MoveIt-linked" from
the signal family's description, and is still two events rather than a rate.
**The family now has two occurrences on CI runners nobody prepared, on consecutive runs and
on both signals.**
The two campaign events are at `de67d8b` on a developer machine; these two are not.
In CI run `34085965578` at `f6a3779`, one of the two `bringup` invocations passed its cycle and
failed its post-shutdown check on `FAIL: test_nothing_of_ours_exited_badly` with
`parameter_bridge-2 exited with -11`, and nothing else in that run exited badly. **In the next scenario-driving run in the
table above, `34247027502` at `13bc8e9`, the same thing happened on the other
signal**: `parameter_bridge-2 exited with -6`. **Neither is exempted**:
`tests/scenarios/bringup.py`'s
`UPSTREAM_TEARDOWN_SEGFAULT` covers
`move_group` and -11 and nothing else, so the process that died is outside it on both
signals, exactly as
`skill_server`'s -11 is outside `continuous_line`'s. **Four `parameter_bridge` events in
total across two
machines, and still not a rate.** This bullet said "a third … three in total" until
2026-09-08. Nothing about the
cause moves: no mechanism is demonstrated for any member of this family, and **no exemption
may be widened to absorb this one.** The `13bc8e9` reading is the single 2026-09-08 reading
described in the `continuous_line` bullet and was not re-read here.
**`gz` at -9 has reached CI, and it is recorded here rather than classified.** In CI run
`34258470163` at `e18251e`, two post-shutdown checks failed in the same run, in two different
scenarios, on the identical assertion: `FAIL: test_nothing_of_ours_exited_badly` with
`AssertionError: -9 not found in [0, 130] : gz-1 exited with -9`, once in
`bringup.TestCleanShutdown` at 17:59:45Z and once in `pick_and_place.TestCleanShutdown` at
18:04:00Z. Nothing else exited badly anywhere in that run's three scenario steps, and the
`continuous_line` step recorded no bad exit at all. Read here on 2026-09-08 from that run's
own log. **It is not exempted anywhere**: `UPSTREAM_TEARDOWN_SEGFAULT` is `"move_group"` and
the allowance is `-11` in all three of `tests/scenarios/bringup.py`,
`tests/scenarios/pick_and_place.py` and `tests/scenarios/continuous_line.py`, read in this
checkout on that date. **No exemption may be widened to absorb it.**
**This is deliberately not folded into the signal family above, and the reason is this
bullet's own rule.** The superseded account named `gz` (-9) among the processes it listed, and
this file has said since 2026-08-27 that `parameter_bridge` (-6) and `gz` (-9) are **outside
the set the family split was measured over and are not classified here**. That is still the
case: -9 is `SIGKILL` and the other members of the family died on -6 and -11, the split was
never measured over this process, and **sharing a teardown and a minus sign is not evidence
of sharing a cause**. Two events, in one CI run, at one commit, on one runner nobody
prepared, with nothing registered in advance. **That is not a rate and it is not a
classification.**
**One earlier observation of the same process and signal exists and is local**, at `37921dd`
on `feat/hosted-by-derived`, recorded in the `bringup` bullet above where `pick_and_place`
failed a teardown on `gz-1 exited with -9`. **That it is the same string is a fact; that it
is the same cause is not established**, and the local pair was reported by the agent that ran
it and not re-run.

## The line's dead ends after a grasp (overtaken 2026-10-01)

_Source: `CLAUDE.md` lines 2142-2210 at `960e6b4`._

- **The line still stalls after a failed grasp, and the dead end is observed rather than
  predicted.** **[Overtaken 2026-10-01 — this item is about the event-driven line, which left the main tree with ADR-0069 and runs only in the `projects/01` snapshot. It is kept as that snapshot's record.]** A piece fails the friction grasp, the station retries, returns to
  `AwaitTrigger` on a beam the part is **already breaking**, and waits out the leg ceiling —
  while `LineState` reports `RUNNING`, so nothing escalates and the scenario's fail-fast —
  which keys on `BLOCKED`, `FAULTED` **and `STALLED`** in the tree today
  (`STOPPED_STATES`, `tests/scenarios/continuous_line.py:467`; it was 458 until 2026-09-01
  and 465 until `eef5468` on 2026-09-02, this file carried 465 until 2026-09-03, and **the
  set itself is unchanged** through all three — re-read the line rather than trusting it,
  because it has moved twice in a week), and this file said only the first two —
  correctly stays quiet, because the line publishes none of the three. Seen twice,
  reported by the project owner on 2026-08-27. ADR-0038 records why this is deliberately **not** fixed: the
  cheap fix restarts the belt, the retry begins with `MoveToHome` carrying whatever the arm
  holds, and `Pick`'s first physical act is to open the gripper — so the retry's first move
  would open the jaws at the home pose and drop a part no planner knows is held.
  **This is one entrance to the dead end and not the whole of it** — ADR-0038's 2026-08-29
  amendment records the second, which is the item below.
  **The account above is falsified for a failed grasp by the change recorded in the item below,
  and this is the fourth time this section has carried a wrong claim.** `TakeCustody` stands
  **above** `PickAt` in the shipped tree, so a failed grasp fails *after* custody is taken —
  which means ADR-0046's custody refusal covers it: the retry is refused, the station goes
  `STATE_BLOCKED`, and `LineState` no longer reads `RUNNING`. Its own test
  (`RunningLine.AStationStillHoldingItsWorkpieceIsRefusedTheRetryAndEscalates`) drives
  exactly that case through the shipped XML. **What is evidenced is the mechanism, not the
  outcome:** no run of the cell has produced this failure and reported it, so "the line
  stalls silently after a failed grasp" is corrected as an account of the *code* and not
  retired as an account of any *run*. **What is not covered is a failure above
  `TakeCustody`** — `DetectAt` is the only skill there — which still retries onto a beam the
  part is already breaking and is reported by nothing at a table-fed station. ADR-0038
  decision 5 is untouched either way: nothing decides what to do with a held part, and an
  escalating station performs no motion, so the arm stops where it stood.
- **The same dead end reached through a second door: the grasp holds and the retry carries
  the part off its own trigger.** **[Overtaken 2026-10-01 — this item is about the event-driven line, which left the main tree with ADR-0069 and runs only in the `projects/01` snapshot. It is kept as that snapshot's record.]** Three CI runs have left a work-piece stuck between
  `lifted` and `on_link` at `station_transfer_1` — the arm has the part, the place onto
  `conveyor_1`'s infeed never happens, `LineState` reads `RUNNING` and nothing escalates.
  The evidence and the milestone ladder are in the `continuous_line` bullet above and are
  not repeated here. **The cause is established** and has two records, both written
  2026-08-29 and both `Proposed`: the gripper result deadline is a wall-clock `constexpr`
  supervising a simulation-time process
  (ADR-0045 (`docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md`)), and a
  station that still holds its work-piece re-enters a wait its own recovery made
  unsatisfiable
  (ADR-0046 (`docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md`)).
  **It is the item above's dead end with a different entrance, and the difference decides
  what a fix must do.** There the grasp fails, the beam stays blocked and the arm is empty;
  here the grasp holds, the beam goes clear and the part is in the gripper — so **a fix
  keyed on "the beam is blocked" catches only one of the two**, which is why ADR-0046 keys
  its refusal on custody instead.
  **Widening the constant is not available as a fix**: `GripperActionController` resets its
  stall search on every control cycle in which the joint exceeds
  `stall_velocity_threshold`, so the quantity the deadline is asked to bound has no upper
  bound — the rule read upstream in ADR-0045's verification table.
  **The detector is not broken; its coverage is.** In one local run reported by the
  investigation, the same fault class at belt-fed `station_transfer_3` was named by
  ADR-0039's detector **0.341 s** later and aborted the run; at table-fed
  `station_transfer_1`, `untriggerable_reason` returns `nullopt` at its first test because
  there is no inbound belt, so the line published `RUNNING` for the rest of the leg. That
  contrast is ADR-0039's 2026-08-29 amendment, one run, not re-measured.
  **Three things stay explicitly unmeasured**, chief among them why CI's gripper-close
  distribution has a long tail that the investigating host did not reproduce at a comparable
  real-time factor. ADR-0045 lists all three with the measurement that would settle each;
  none may be smoothed over here or anywhere else.
  **Both records are implemented and merged on `main` at `c555440`**, and both stay `Proposed`. **The mechanism is evidenced
  and the outcome is not**: the deadline is now measured in the node's clock and declared in
  L0, an expiry sends a cancel and latches custody as unknown so that `Pick`, `Place` and
  `Transfer` refuse rather than assume an empty gripper, and a station that still holds its
  work-piece is refused its retry and goes `STATE_BLOCKED`. Every one of those is held by a
  unit or launch test; **none of them is held by a run of the cell in which this failure
  occurred**, because no such run has been taken since. Until one is, this is still the
  failure this project has the most evidence for, and nobody may write that it is fixed.

## Arm-to-arm handoff (overtaken 2026-10-01)

_Source: `CLAUDE.md` lines 2377-2381 at `960e6b4`._

- **L4 refuses a direct arm-to-arm handoff, and the residual is no longer the stated reason.** **[Overtaken 2026-10-01 — this item is about the event-driven line, which left the main tree with ADR-0069 and runs only in the `projects/01` snapshot. It is kept as that snapshot's record.]**
  ADR-0031 was corrected on 2026-08-26: nothing re-observes the part, and what makes the
  *permitted* conveyor edge safe is the receiving gripper closing on a free part — which a
  direct handoff denies. Read that ADR's correction before writing about either case. The
  refusal string in `line_plan.hpp` still carries the pre-correction reasoning.

## L4's own tests (overtaken 2026-10-01)

_Source: `CLAUDE.md` lines 2388-2392 at `960e6b4`._

- **L4's own tests move no arm.** **[Overtaken 2026-10-01 — this item is about the event-driven line, which left the main tree with ADR-0069 and runs only in the `projects/01` snapshot. It is kept as that snapshot's record.]** `line_orchestrator` derives one subtree per station from
  `LineTopology` and owns handoff, recovery, the fault branch and `LineState`; its unit and
  launch tests use fake action servers that succeed because they are told to, so what they
  prove is **sequence, ownership and the stop**, not motion. Motion is evidenced only by the
  scenarios.

## Open-loop belts and `StopAll`

_Source: `CLAUDE.md` lines 2393-2403 at `960e6b4`._

- **The belts are commanded open-loop.** **Since 2026-10-01 there is no typed contract for
  a measured belt speed at all**: `ConveyorState`, which existed to make commanded and measured
  speed disagree visibly and which nothing ever published, left `cite_interfaces` with
  ADR-0069, and a closed-loop belt now needs a contract of its own. The bridge
  carries a bare `std_msgs/Float64` each way. The rest of this item is as it read before that
  date, when `StopAll` was in the main tree: so `StopAll` states an intent it cannot confirm,
  and a belt that fails to stop, or fails to restart, is a spilling or a stalled line that
  nothing notices. **This is the gap that hid the delivery defect above for ten commits**:
  with no confirmation path, "commanded" and "running" were indistinguishable from inside the
  system. A publisher of `ConveyorState` — in the simulation plugin and on the hardware drive,
  which is L1/L2 work — is what closes it.

## CI runs on vendor and on hull collision geometry

_Source: `CLAUDE.md` lines 2532-2597 at `960e6b4`._

**MOST SCENARIO AND CI FIGURES IN THIS SECTION WERE MEASURED WITH VENDOR GEOMETRY; SEVEN
CI RUNS WERE MEASURED WITH HULLS.** This file said **"NO SCENARIO OR CI FIGURE ANYWHERE IN
THIS SECTION WAS MEASURED WITH HULLS"** and **"no CI run has ever brought this cell up
against the hulls"** until 2026-09-01, in capitals, and the second clause was false when
the first re-audit published it; it then said **"EXACTLY ONE CI RUN WAS"** until
2026-09-07, and that expired within seconds of being written and stood for five days
before anyone re-read it; **"FOUR"** until 2026-09-08 and **"FIVE"** for part of that day.
**That is four falsifications of one sentence** — none, one, four, five — and the count is
the only part of it that has ever been wrong.
**What stays true, and it is most of the sentence.** `bringup`'s first 36 of 50, every
`pick_and_place` run before `e51238e`, the first eighteen rows of the `continuous_line`
table and the whole teardown-family split were all taken with **vendor** collision
geometry. Read them as evidence about the cell that was.
**What is false, and by how much.** Seven CI runs on `main` have brought this cell up
against the hulls: **`33501707588`** at **`e51238e`**, **`33575992281`** at **`4ef2d7c`**,
**`33603610958`** at **`51195e0`**, **`34085965578`** at **`f6a3779`**,
**`34247027502`** at **`13bc8e9`**, **`34258470163`** at **`e18251e`** and
**`34280056331`** at **`aed36c4`**. That they are
hull runs is established rather than assumed: `git merge-base --is-ancestor dd93488 <sha>`
succeeds for each and `git show <sha>:model/assets/types/robots/xarm5.yaml | grep select:`
reads `select: convex_hull` for each — re-derived over the last two on 2026-09-08, the five
above them having been re-derived the same way earlier that day. Verdicts
were read from the logs, never from the step
conclusion, by the instrument this section mandates.
**What those seven runs show, scenario by scenario, and `pick_and_place` now needs two
figures where it needed one.** `pick_and_place`'s **cycle** passed in all seven, and in all
twenty-five tabled
runs; its **teardown** was clean in six of the seven, failing at `e18251e` on `gz-1 exited
with -9`. That split is the `pick_and_place` bullet above and is not restated here.
`bringup`'s cycle passed in all fourteen invocations, and three of the fourteen failed their
teardown, at `f6a3779` on a `parameter_bridge` -11, at `13bc8e9` on a -6 and at `e18251e` on
a `gz-1` -9 — the
teardown-family bullet above is
where all three are kept. `continuous_line` **passed in four of the seven and failed in
three**; two of the three failures are the third signature recorded in that bullet and the
third is the spawn signature's second occurrence.
**What the seven runs are not.** **Seven runs**, at seven commits, on runners nobody
prepared,
with **no thresholds registered in advance. It is not a rate**, and three of the seven
contain a `continuous_line` failure. This paragraph counted four runs until 2026-09-08 and
five for part of that day.
They say **nothing about the grasp** — the 2026-09-01
hull-grasp campaign's verdict is INCONCLUSIVE by its own pre-registered rule S and these
runs do not touch it — and **nothing about capacity**, which is the separate case below.
**Why the "no CI run" clause survived to be falsified twice, because that is the lesson.**
The runs at `dd93488` and `d6db73b` — the hull promotion and the commit after it — were
both **cancelled**; `e51238e`'s run completed *after* the re-audit that wrote the first
sentence, so the window in which anyone could have noticed was **one run wide**. The
replacement sentence was falsified by **the CI run of the very commit that wrote it**:
`git log --date=iso -S "EXACTLY ONE" -- CLAUDE.md` puts it at `4ef2d7c`, committed
2026-09-02T00:35:51Z, and `gh run list` puts `33575992281` — the hull run of that same
commit — at 2026-09-02T00:36:00Z, **nine seconds later**. It then stood in this file for
five days. A sentence about what CI has never done expires the moment CI runs again, and
twice now nothing re-read it; the second time, the push that wrote the sentence was itself
the thing that expired it.
**The count that replaced it has now expired twice more, and the second time repeats the
lesson to the minute.** "FOUR" was written at `13bc8e9`, and that commit's own CI run
`34247027502` was itself the fifth hull run. "FIVE" was written at `987e6b6`, committed
2026-09-08T17:20:18Z, and `34258470163` at `e18251e` — the sixth — was created at
2026-09-08T17:39:58Z, **under twenty minutes later** (`git log --date=iso` and
`gh run list --branch main --json createdAt`, both read 2026-09-08). That is the same shape
as the nine-second falsification above.
**What was different in the days between is why nobody caught it:** the three commits after
`13bc8e9` could not open a CI log at all, because `gh` on this host was unauthenticated.
**An instrument you cannot run is a claim you cannot keep**, and this paragraph is where
that shows first.

## Phase 1 exit criterion: the closing run

_Source: `CLAUDE.md` lines 2658-2674 at `960e6b4`._

- **The criterion is MET as of 2026-08-28 and that is not a green light.** It closed on CI run
  `33158091922`, one run, no thresholds registered in advance, at commit `60eb4a5`. **Inside
  that green run the advisory `continuous_line` step failed** — 1 of 3 work-pieces, a station
  stopped while `LineState` still read healthy. That silence is the blind spot ADR-0039
  records at that station. **What stopped the piece was not established when the clause
  closed and has been established since** — the gripper-result timeout and the retry that
  carried the part off its own trigger, ADR-0045 and ADR-0046, at the strength the
  `continuous_line` bullet above states. Nothing about that changes the closure: it was
  closed on evidence that did not include a cause, and knowing the cause does not add a run.
  **One attribution names the right dead end by the wrong door and must not be repeated as
  it stands.** Charter §8 reads that run as consistent with the *failed-grasp* dead end
  ADR-0038 records. It is that dead end, and it is not the failed grasp: the run's own
  milestone ladder puts the piece past `lifted(station_transfer_1:
  cell_a__table_pick__surface)` and leaves it in the air at `(-0.001, 0.273, 1.201)` for the
  rest of the leg, so the grasp held, and ADR-0038's 2026-08-29 amendment records the second
  door it went through instead. The charter is protected and still carries that sentence;
  treat the ladder and the two records as the record.

## Phase 1 exit criterion: the CI failures, the clean-clone walk and the cycle clause

_Source: `CLAUDE.md` lines 2680-2712 at `960e6b4`._

_This section resumes mid-sentence. The sentence it continues opens with the lesson "never cite 'CI is green' as evidence", which stayed in the main repository's review queue, and ended: "See the table in the `continuous_line` bullet, where **seven of"._

  twenty-five**
  CI runs failed the cycle, in **three** distinct signatures — three of them in the same way,
  **two** on a spawn timeout, and two that escalated and stopped the line. It said "four of
  nineteen … three of them in the same way and the fourth on a different signature entirely"
  until 2026-09-07 and "six of twenty-three … one on a spawn timeout" until 2026-09-08.
  **`34258470163` at `e18251e` is a fresh demonstration of the trap this paragraph names**:
  its workflow conclusion is `success` and its `continuous_line` failed.
- **The clean-clone walk of 2026-08-27 demonstrated clone-to-green, not a running line.** It
  ran `doctor` (23 passed, 0 failed), `build` (19 packages, before `cite_runtime` existed),
  `test` and `lint`, all clean, from a fresh clone of the remote with zero deviations — and
  **stopped at `lint` without launching the cell**. The clone-to-running-cell half is
  evidenced by the CI runs above, each of which brought the cell up twice from a checkout —
  `bringup`'s cycle has passed **50 of 50** across the twenty-five, with its teardown clean
  in
  **47** of those 50 — and by nothing else. It said "38 of 38 across the nineteen" until
  2026-09-07, when no teardown figure was stated separately because none had yet failed,
  "44 of 44 … 43" until 2026-09-08 and "46 of 46 … 44" for part of that day.
- **The cycle clause is the least-settled of them.** **Seven** CI failures are now part of
  its
  record, not one: three stopped the same piece at the same milestone, **two** timed out
  spawning a work-piece, and two escalated and stopped the line. It said "four" until
  2026-09-07 and "six" until 2026-09-08.
  **Eighteen CI runs have passed the cycle since the clause closed, and that does not settle
  it** — it was closed on one run with no thresholds registered in advance, and a longer
  unregistered tally is a longer unregistered tally. **The figure here read "thirteen more
  CI runs have passed the cycle since 2026-08-29" until 2026-09-07, and it reconciled with
  no reading of the table that could be derived on that date**: counting the table's `passed`
  rows dated 2026-08-29 or later gave 15 and counting those strictly later gave 12, neither
  of them 13. The seventeen above is every `passed` row in the table, which is the whole of it
  since the closure run `33158091922` is the table's first row and it failed; it read
  "sixteen" until 2026-09-08 and "seventeen" for part of that day. See
  the `continuous_line` bullet above, including that a
  harness had been starting the belts and that the best local figure is a single run.
