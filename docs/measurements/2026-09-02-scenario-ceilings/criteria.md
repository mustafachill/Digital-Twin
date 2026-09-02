# Criteria — what the six scenario wall-clock ceilings bound, measured rather than proxied

**Written and committed before the first campaign trial ran, before the harness exists, and
before anything was run.** Frozen from that commit ([`../README.md`](../README.md), rule 1).
Any interpretation that had to change afterwards is recorded as a numbered deviation in
`ANALYSIS.md`, applied to data already collected — never by re-running until the definition
suited.

> **AMENDED on 2026-09-02, still before the first trial and still before the harness existed.**
> An adversarial pre-freeze review found eleven gaps in the decision procedure — a rule named
> and never defined, a validity rule watching the wrong paths, a false statement about an
> instrument, a reporting rule that does not hold for partial failures, a presence check blind
> to partial loss, a snapshot taken at one end of a run, an unbranched crossing rule, four
> rule-letter collisions, an incomplete declaration of pre-campaign runs, a run order that
> contradicted its own totals, and an unpinned environment variable. **No threshold, band,
> effect size or sample-size figure was changed by the amendment**; every change closes a gap in
> how a decision is made, and each is marked in place with what the earlier draft said. **After
> the first trial these would have been permanent**: rule 1 requires a wrong rule to be applied
> literally and recorded as wrong, never corrected. The freeze binds from the amending commit.

- **Date opened:** 2026-09-02
- **Branch under measurement:** `feat/close-phase-debts`
- **BASE_COMMIT:** **`c38a42c`**. Every figure below is a property of the tree at that commit.
  V1 in §10 is what spends this, and it is the load-bearing rule of the campaign.
- **The item that asks for it:** [`docs/open-work.md`](../../open-work.md) **#30 — Re-derive
  the six scenario wall-clock ceilings.** It records the 2026-08-29 campaign as having answered
  part of the question and names what is still open: **the under-load figure**, and two levers
  that have moved since.
- **The campaign this one continues, and whose definitions it inherits:**
  [`2026-08-29-real-time-factor-conditions/`](../2026-08-29-real-time-factor-conditions/ANALYSIS.md).
  Its §5 margin definition and its three interpretation bands are **inherited verbatim** and are
  not reinvented here (§2.2). Its **rule D3** keeps its letter (§7.1). That directory is
  **frozen**: no file in it is edited, re-run or re-analysed here, and its figures are cited and
  not copied (P1).
- **Why it can be done now and could not be done then.** That campaign had to report two
  ceilings as **not assessed** under its own rule D3 and reach two more only through **proxies**,
  because per-milestone timings were not printed. They are printed now: commits **`eef5468`**,
  **`59f818d`** and **`c38a42c`** on this branch added a `CITE_TIMING` record per waited-for
  interval, and `tests/scenarios/guards/test_timing_records.py` binds the record's shape.
- **The two levers #30 says must be folded in.** The world now carries
  [ADR-0043](../../adr/0043-hold-both-sides-to-the-wall-clock.md)'s throttle —
  `workspace/src/cite_generated/worlds/cell_a.sdf` declares `<real_time_factor>1</real_time_factor>`,
  read there on 2026-09-02 — and the shipped collision geometry is convex hulls
  ([ADR-0028](../../adr/0028-convex-hull-collision-meshes.md);
  `model/assets/types/robots/xarm5.yaml` reads `select: convex_hull`, read there the same day),
  which [`2026-09-01-capacity-on-shipped-main/`](../2026-09-01-capacity-on-shipped-main/ANALYSIS.md)
  measures as materially cheaper. **Ceilings derived on vendor meshes may now be loose.** This
  campaign measures the **shipped** configuration and **attributes nothing to either lever** —
  §8 says why, and it is a consequence of §0 rather than an omission.

---

## 0. This campaign decides nothing

- **No threshold, ceiling, tolerance or band anywhere in the tree changes because this campaign
  ran.** Not one of the nine `*_CEILING_S` declarations is edited, and **none may be widened to
  absorb anything found here.** #30 says it in one line — *"Change no ceiling without the
  measurement, and never widen one to absorb a failure"* — and the second half binds this
  campaign as much as the first.
- **Changing a ceiling is a separate decision and is the project owner's.** This document is
  written before any number exists precisely so that no number produced by it can be read as an
  argument for a particular new value.
- **Nothing in `model/`, `workspace/src/`, `tools/`, `tests/` or `scripts/` is edited.** The
  scenarios are measured exactly as the tree at `c38a42c` ships them. **`tests/` and `scripts/`
  are on that list because everything this campaign measures lives there**: all nine
  `*_CEILING_S` declarations and every `_emit_timing` definition and call site are under
  `tests/scenarios/` (`grep -n "CEILING_S = " tests/scenarios/*.py` and
  `grep -rn _emit_timing tests/ scripts/ workspace/src/ tools/`, this checkout, 2026-09-02, which
  reaches `tests/scenarios/` and nothing else), `scripts/scenario` holds the four verdict strings
  I2 reads, and `scripts/_lib.sh` holds the `cite_project_name` §4.4 derives the container name
  from. An earlier draft watched three paths, under which **editing a ceiling value, a `what`
  string or a spin quantum mid-campaign would have left `v1_clean` true**. This is not only a
  discipline: V1 discards any block taken while one of those five paths differs from `c38a42c`,
  so an edit does not contaminate the data — it destroys it. It costs nothing to watch the two
  extra paths: `git diff --stat c38a42c..HEAD -- tests/ scripts/` is empty, read on 2026-09-02.
- **The harness lives entirely under `harness/` in this directory**, and `raw/` beside it.
- **The frozen harness of 2026-08-29 is copied, never edited in place.** Its CPU-limit scripts
  are the starting point for the loaded condition (§4.4). Leaving the original directory
  untouched is [`../README.md`](../README.md)'s second rule — *"`harness/` is frozen for the same
  reason, and `raw/` with it"*. **The per-file attribution header naming the source file and the
  commit it was copied at is this campaign's own practice and the README does not require it**;
  it is stated here so that a reader of `harness/` can tell a copied file from an original
  without diffing two directories.
- **This campaign proposes no replacement value for any ceiling.** Where a ceiling reads TOO
  LOOSE, the campaign says so and stops. Where it reads TOO TIGHT, the campaign says so and
  stops.

---

## 1. The questions, and the ones they are not

**Q-A — the margin at a full allocation, measured rather than proxied.** For each ceiling name,
**what is `M = ceiling / slowest measured instance of the interval it bounds`, computed from
records the scenarios themselves emit, and what is its verdict against the inherited bands?**
This is the half of #30 the 2026-08-29 campaign answered for four names and could not answer for
the other two.

**Q-B — the under-load condition, which is the half #30 explicitly leaves open.** **How does each
margin move as the cell's CPU allocation is reduced, and at which allocation does each ceiling
cross out of the APPROPRIATE band?** The 2026-08-29 campaign answered this by **scaling measured
intervals by a ratio of real-time factors**. This campaign measures the intervals under the
allocation directly.

**Q-C — the shipped configuration.** Every margin here is taken with ADR-0043's throttle in the
world and hull collision geometry selected. **Is any ceiling, on the configuration this
repository actually ships, outside the APPROPRIATE band?**

**Q-D — does the instrument mean what a parser will assume it means?** Ten structural threats to
the record are registered in §4.2 and two more in §4.3. **How many records does a run emit,
how many are non-measurements, how many are mangled, and does any record disagree with its own
ceiling?** This is reported as a first-class result, not as a footnote, because a margin computed
off the wrong quantity is worse than no margin.

Not in scope, deliberately:

- **This measures the simulator, on one machine.** The layout is `PROVISIONAL` and the physical
  scan is Phase 3 (charter §8). **Nothing here says anything about hardware**, and no figure here
  may be read as a P2 result.
- **This is not a determinism claim.** `CITE_PHYSICS_SEED` reaches `gz sim --seed` only, which
  seeds `gz::math::Rand` — sensor noise and transport RNG — and **does not seed the physics
  solver**; the OMPL fallback is unseeded and unseedable. `./scripts/scenario` prints this on
  every run. Every figure here is a distribution over repeats.
- **This is not a rate, and it is not a pass rate.** A scenario's verdict is recorded per run
  because §10's V3 needs it, and **the count of passes is not a result of this campaign**. The
  `continuous_line` CI tally in CLAUDE.md §2 is a different body of evidence taken on different
  machines, and nothing here is added to it.
- **Real-time factor and capacity are settled elsewhere and are not re-opened.** See
  [`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
  and [`2026-09-01-capacity-on-shipped-main/`](../2026-09-01-capacity-on-shipped-main/ANALYSIS.md).
  **No real-time-factor or capacity claim is made from this campaign**, and none of its figures
  may be quoted as one.
- **Teardown is not measured.** Post-shutdown behaviour is the teardown campaign's question, and
  it reports an inconclusive that this campaign does not disturb.
- **Whether any ceiling should change.** §0.

---

## 2. The quantities, named once

### 2.1 The ceiling inventory, read from the tree at `c38a42c`

**"Six ceilings" counts NAMES, not declarations, and the count has moved since #30 was written.**
As of `c38a42c`, `grep -c "CEILING_S = " tests/scenarios/*.py` totals **nine declarations**
carrying **seven distinct names**. #30's "six" are the six the 2026-08-29 table covers — the
eight declarations that existed then, of which `BRING_UP_CEILING_S` is three. The seventh name,
`pick_and_place.SETTLE_CEILING_S`, was a **bare literal** until `59f818d` and is a ninth
declaration; **it is reported here as a seventh ceiling and is not folded into the six.**

**`BRING_UP_CEILING_S` is declared three times with two values** — **240.0** in `bringup.py`,
**300.0** in `pick_and_place.py` and in `continuous_line.py`. **`SETTLE_CEILING_S = 60.0`
coincides in value with `bringup.TRAJECTORY_CEILING_S = 60.0` in a different file and bounds
something else entirely**, which is the reason it was given a name at all.

> **Every reported margin names the file as well as the constant.** A margin written as
> "`BRING_UP_CEILING_S`" without a file is ambiguous across two values, and one written as "60 s"
> is ambiguous across two names. `ANALYSIS.md` writes
> `<scenario>.<CONSTANT>` everywhere, with no exceptions.

| # | file | ceiling | value | emitting `what` (run-time text in `{}`) | contributes to the margin? |
|---|---|---|---|---|---|
| 1 | `bringup.py` | `BRING_UP_CEILING_S` | 240.0 | `{manager} to appear` | **no** — rule A |
| 1 | `bringup.py` | `BRING_UP_CEILING_S` | 240.0 | `{arm}'s controllers to be active` | **no** — rule A |
| 1 | `bringup.py` | `BRING_UP_CEILING_S` | 240.0 | `/cite/cell_a/arm_1/arm_1_gripper_controller/gripper_cmd` | **no** — rule A |
| 1 | `bringup.py` | `BRING_UP_CEILING_S` | 240.0 | `/cite/cell_a/arm_1/arm_1_joint_trajectory_controller/follow_joint_trajectory` | **no** — rule A |
| 1 | `bringup.py` | `BRING_UP_CEILING_S` | 240.0 | **`the arm_1 skill server`** | **yes — the only one** |
| 2 | `bringup.py` | `DELIVERY_CEILING_S` | 30.0 | `a message on {topic}` (two tests) | yes |
| 2 | `bringup.py` | `DELIVERY_CEILING_S` | 30.0 | `a joint state after the gripper closed on {topic}` | yes |
| 2 | `bringup.py` | `DELIVERY_CEILING_S` | 30.0 | `the model version` | yes |
| 2 | `bringup.py` | `DELIVERY_CEILING_S` | 30.0 | `a transform from cite_world to {frame}` | yes |
| 3 | `bringup.py` | `TRAJECTORY_CEILING_S` | 60.0 | `the gripper goal to be accepted`; `the gripper to report a result`; `the trajectory goal to be accepted`; `the trajectory to return a result`; `the MoveTo goal to be accepted` | yes |
| 4 | `bringup.py` | `SKILL_CEILING_S` | 120.0 | `MoveTo to return a result` | yes |
| 5 | `pick_and_place.py` | `BRING_UP_CEILING_S` | 300.0 | **`the skill server, and therefore the whole stack beneath it`** | yes — the cold one |
| 5 | `pick_and_place.py` | `BRING_UP_CEILING_S` | 300.0 | `a transform from cite_world to {frame}` | yes, warm |
| 6 | `pick_and_place.py` | `CYCLE_CEILING_S` | 420.0 | `the station cycle to run to completion` | yes — rule X applies |
| 7 | `pick_and_place.py` | `SETTLE_CEILING_S` | 60.0 | `the work-piece to settle` | yes — rule Z is decisive here |
| 8 | `continuous_line.py` | `BRING_UP_CEILING_S` | 300.0 | **`the first LineState, and so the line coordinator and the stack below it`** | yes — the cold one |
| 8 | `continuous_line.py` | `BRING_UP_CEILING_S` | 300.0 | `a transform from cite_world to {frame}` | yes, warm |
| 8 | `continuous_line.py` | `BRING_UP_CEILING_S` | 300.0 | `L4 to command every belt to a non-zero setpoint (ADR-0032). …` | yes |
| 9 | `continuous_line.py` | `LEG_CEILING_S` | 420.0 | **`piece {n}: {milestone}`** | **yes — the only leg** |
| 9 | `continuous_line.py` | `LEG_CEILING_S` | 420.0 | `the work-piece '{name}' to settle on the pick surface` | **no** — §2.3 |
| 9 | `continuous_line.py` | `LEG_CEILING_S` | 420.0 | `the work-piece '{name}' to leave the simulator` | **no** — §2.3 |

Plus **one interval that emits nothing at all, deliberately**: `bringup`'s follower-settle loop
inside `test_the_gripper_linkage_is_actually_coupled`, which carries `DELIVERY_CEILING_S`. §8.

### 2.2 The margin and the bands — INHERITED, not reinvented

From [`2026-08-29-real-time-factor-conditions/criteria.md`](../2026-08-29-real-time-factor-conditions/criteria.md)
§5, adopted word for word:

```
M = ceiling / the SLOWEST measured instance of the interval it bounds
```

| Band | Reading |
|---|---|
| `M < 1.5` | **TOO TIGHT.** Ordinary variation will hit it; this ceiling is a flake source |
| `1.5 <= M <= 10` | **APPROPRIATE.** Catches a hang, tolerates a slow run |
| `M > 10` | **TOO LOOSE.** A regression an order of magnitude in size would still pass. A ceiling that can no longer fail is not a check |

> **The symbol `M` here is the margin and is NOT a rule letter.** `Rule M` is taken, in
> [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/criteria.md) §7.8 and
> in [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/criteria.md) §7, where in
> both it is the false-negative null. **This campaign defines no rule M**, and every `M` below is
> the quantity in the box above. The reuse is declared rather than avoided because `M` is the
> inherited campaign's own symbol for the margin (§2.2) and renaming it would break the
> inheritance this section exists to state.

**The slowest, not the median, and not a percentile.** That is the earlier campaign's choice and
it is kept. The median, IQR and n are reported beside every margin so a reader can see how much
of the answer rests on one trial, but **the verdict is computed from the slowest valid instance**
and from nothing else.

**One margin per (scenario, ceiling name, condition).** Margins are never pooled across scenarios,
never pooled across CPU allocations, and never pooled across the two values of
`BRING_UP_CEILING_S`.

### 2.3 The record, and the key that identifies an interval

The record is one line, `CITE_TIMING ` followed by a JSON object with exactly these keys, a
contract asserted by `tests/scenarios/guards/test_timing_records.py`:

| field | what it is |
|---|---|
| `scenario` | the emitting module's stem — `bringup`, `pick_and_place`, `continuous_line` |
| `test` | the test method that produced it. **Load-bearing for rule A** |
| `what` | the human description of the wait |
| `ceiling_s` | the ceiling the wait ran under |
| `elapsed_s` | **the only time field.** `time.monotonic()` across the wait, rounded to 1 ms |
| `spins` | a **loop count**. **The discard field** — rule Z |
| `monotonic_s` | the emitting process's clock at print time, for ordering |

> **The interval key is `(scenario, what)`, and the ceiling is read from `ceiling_s` and never
> inferred from `what`.** This is not a stylistic preference. **`a transform from cite_world to
> {frame}` is emitted by all three scenarios under three different ceiling DECLARATIONS, which by
> this file's own names-not-declarations rule (§2.1) are two names carrying two values** — 30.0 s in
> `bringup` (`DELIVERY_CEILING_S`), 300.0 s in `pick_and_place` and 300.0 s in `continuous_line`
> (`BRING_UP_CEILING_S`, and `continuous_line.root_frame` is `cite_world`, so the strings are
> identical, not merely similar). A parser keying on `what` alone pools three intervals under one
> ceiling and produces a number that belongs to none of them.

> **`LEG_CEILING_S` is used in three places and only one of them is a leg.** A leg reads
> `piece <n>: <milestone>`; the other two name the work-piece and say `to settle on the pick
> surface` (order a second) or `to leave the simulator` (order milliseconds). **A margin computed
> over those two puts `LEG_CEILING_S` hundreds of times looser than the proxy it replaced.** The
> scenario's own `_spin_until` docstring says so; this campaign registers it as a filter, keyed on
> the `what` prefix `piece `.

---

## 3. The conditions, and rule T over them

| condition | what it is | why |
|---|---|---|
| **FULL** | the container unconstrained: `/sys/fs/cgroup/cpu.max` reads `max 100000` inside it, on a 16-core host | Q-A and Q-C. The margin on the machine as it is |
| **C4** | `docker update --cpus 4` applied to the running container | Q-B, the first step down |
| **C2** | `--cpus 2` | Q-B |
| **C1** | `--cpus 1` | Q-B. The allocation the recorded 0.14 real-time factor holds at, per the 2026-08-29 campaign |

Each condition is run against each of the three scenarios: `bringup`, `pick_and_place`,
`continuous_line`.

> **Rule T — INHERITED. It is first stated in
> [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/criteria.md) §7.8 —
> *"the arms are not each other's evidence"* — and carried in the same words into
> [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/criteria.md) §3.** An earlier
> draft credited the second of those and not the first; the letter and the wording are the
> grasp-discrimination campaign's. Here: **a condition is not
> another condition's evidence, and a scenario is not another scenario's.** A margin measured at
> FULL says nothing about C1; a `bringup` margin says nothing about the identically named
> `BRING_UP_CEILING_S` in `pick_and_place`, which is a different constant with a different value
> bounding a different wait. **Every verdict in §7 is stated per (scenario, ceiling, condition)**,
> and an inconclusive one belongs in the verdict rather than in a footnote.

> **Rule H — the 2026-08-29 figures are on a different machine and may not be differenced against
> these.** That campaign ran on a macOS arm64 laptop under Docker Desktop; §9 names an x86_64
> Linux host. **No margin here may be subtracted from, divided by, or described as an improvement
> on a margin there.** Both are cited; neither is a delta. This rule exists because the natural
> sentence — "the margin went from 6.8 to X" — is exactly the sentence the data cannot support.

---

## 4. Instruments, registered before the first trial

### 4.1 The instruments themselves

| # | Quantity | Instrument |
|---|---|---|
| **I1** | the duration of every waited-for interval | the `CITE_TIMING` record, extracted from a captured console with the regex **`CITE_TIMING (\{.*\})`** and `json.loads` on group 1. **Never a fixed slice after `startswith`** — see threat 6 |
| **I2** | whether the run's scenario passed | `scripts/scenario`'s own verdict line, `Scenario '<name>' passed` / `passed its cycle assertions` / `failed — …`. **Never the process exit code alone, and never a CI step conclusion** |
| **I3** | the console itself | the campaign's own redirection. `./scripts/scenario <name> 2>&1 \| tee raw/<label>.log`. **Nothing in the repository persists these records** — threat 7 |
| **I4** | the CPU allocation that was actually in force | **`/sys/fs/cgroup/cpu.max`, read from inside the running container**, and `docker inspect --format '{{.HostConfig.NanoCpus}}'` from outside it — both read **after** the limit is applied and again at the end of the run. Recorded per run. **Not `nproc` and not `.HostConfig.CpuQuota`: neither moves when the limit does** — §9 |
| **I5** | the host's load | `/proc/loadavg` and `uptime`, taken before and after every run. **On this host a container's reading is the host's** — §9 |
| **I6** | the code that ran | `git rev-parse HEAD`, `git status --porcelain`, and `git diff c38a42c..HEAD -- model/ workspace/src/ tools/ tests/ scripts/`, **taken at the START of every run and again at its END**, like I5 and I4. A run lasts minutes and an edit landing inside one would be invisible to a single snapshot. V1 |
| **I7** | the configuration that ran | the collision selection in the running cell's description and `<real_time_factor>` in the world it loaded, read back from the running cell rather than from the tree. V2 |
| **I8** | that the expected records exist, **and how many of each** | a **manifest** of `(scenario, what-pattern, ceiling_s, expected_count)` quadruples, written into `harness/expected.py` **before the first trial** from the inventory in §2.1 and from the emitters' own loops. A triple with no record is reported as an **absent expected key**, never as a zero; a triple with **fewer records than its expected count** is reported as `k of n present` — threat 10, threat 12, rule E |

### 4.2 The ten threats to the instrument, registered as findings of an adversarial review of it

Each was established by reading the emitters at `c38a42c`. A campaign that does not carry them
computes a margin off the wrong quantity.

1. **`spins` is the discard field, and `elapsed_s` is not.** `_spin_until` evaluates its predicate
   **once before looping**, so a wait already satisfied emits `spins: 0`. Such a record is a
   **non-measurement of the milestone** — it measures one evaluation of a predicate. **It is not
   always near zero**: `pick_and_place`'s work-piece predicate shells out to `gz model -p`, and a
   single evaluation of a subprocess costs an appreciable fraction of a second. A parser filtering
   on `elapsed_s` keeps such a record and times a subprocess. **The observed cost of that
   subprocess is unpublished — no directory here stands behind a figure for it — and this campaign
   puts no number on it.** The rule is therefore structural, not empirical: **rule Z**.
2. **`spins` is a loop count and NOT a time unit.** Its quantum is **0.5 s** in the three
   `_spin_until` implementations and in `bringup._await_future`, and
   **`SAMPLE_PERIOD_S = 2.0` s** in `pick_and_place._run_cycle`; `continuous_line`'s leg loop uses
   that file's own `SAMPLE_PERIOD_S = 0.5` s. `_await_future` further shortens its last spin to
   whatever remains of the ceiling. **`spins` may never be multiplied into a duration, and may not
   be read as a sampling density across one table**, because the three scenarios are parsed as one
   table and their quanta differ.
3. **Alphabetical test ordering makes most of `bringup`'s bring-up waits non-measurements.**
   `unittest.TestLoader` sorts methods alphabetically and `launch_testing` does not override it
   (`launch_testing/test_runner.py` runs `unittest.TextTestRunner(...).run(...)` over the loaded
   suite), so **`test_a_skill_moves_the_arm_to_its_home_configuration` runs FIRST** and absorbs the
   whole cold bring-up. Every later `BRING_UP_CEILING_S` wait in that file therefore reads near
   zero — correctly, and it is not a measurement of bring-up. **Rule A.** `pick_and_place` and
   `continuous_line` are unaffected: each has exactly one pre-shutdown test method, and its first
   wait is genuinely cold.
4. **Two clocks.** `elapsed_s` is `time.monotonic()`; the timeout in `_spin_until`, in
   `_run_cycle` and in the leg loop is enforced on **the node clock**, which is ROS time on the
   system clock because these observer nodes deliberately do not set `use_sim_time`. The system
   clock is steppable and the monotonic clock is not. **So `elapsed_s > ceiling_s` is possible
   without a timeout having occurred**, and so is the converse. **Rule K** treats it as a datum,
   not as an impossibility. `bringup._await_future` alone uses the monotonic clock for both.
5. **Poll quantisation biases `elapsed_s` UP.** A wait ends at the first predicate evaluation
   after the thing arrives, so the overshoot is bounded by one loop iteration: about **0.5 s**
   where the predicate returns immediately (every `DELIVERY_CEILING_S` wait, and the
   `continuous_line` waits), about **1.0 s** where the predicate itself blocks for 0.5 s
   (`bringup`'s four `wait_for_service`/`wait_for_server` bring-up waits), about **1.5 s** at
   the one `pick_and_place` site whose predicate blocks for 1.0 s, and about **2.0 s** in
   `pick_and_place._run_cycle`, whose loop spins on that file's `SAMPLE_PERIOD_S = 2.0`.
   **That list is not exhaustive and the one it omits is the largest**: the `active` predicate in
   `bringup.test_every_controller_reaches_active` calls
   `rclpy.spin_until_future_complete(..., timeout_sec=10.0)` (`bringup.py:291`), so the
   `{arm}'s controllers to be active` wait overshoots by up to about **10.5 s**. Rule A drops
   that wait for an unrelated reason, so no margin in this campaign carries it — **which is why
   it is named here rather than left to look like an omission.** **Irrelevant against 240 s;
   material against `DELIVERY_CEILING_S = 30.0`**, where a true interval of a fraction of a second
   measured half a second late shifts a derived margin by more than 3x. **Rule Q, §7.1**, which
   is where the decision this threat needs is written down.
6. **`print` writes payload and newline in two calls.** CPython's `print` issues
   `file.write(payload)` then `file.write(end)` — verified on 2026-09-02 against a recording
   text stream, which observed exactly two writes. The emitting test runs on a thread that shares
   `sys.stdout` with the launch service, so **a foreign write can land between the two**, mangling
   the line. Hence I1's regex, anchored on `CITE_TIMING (\{.*\})`. **Rule G**: mangled records are
   **counted and reported**, never silently dropped.
7. **Nothing persists the records.** `scripts/scenario` passes `--junit-xml` and nothing else, and
   `launch_testing/junitxml.py` writes only `testsuites`, `testsuite`, `testcase`, `failure`,
   `error` and `skipped` elements — **no `system-out`** (read in the image on 2026-09-02). The
   test runner is constructed without `buffer`, so the records reach the console and are then
   gone. **The campaign must capture its own console (I3), and a trial whose output was not
   redirected has produced nothing.** **Rule P.**
8. **A `CYCLE_CEILING_S` record exists even when the cycle FAILED.** `_run_cycle` emits whenever
   the coordinator process exits at all, a crash seconds in included; it deliberately does not
   assert on exit status, and the interval it measures genuinely ends when the process ends.
   **Folding a failed run's short elapsed into the margin makes `CYCLE_CEILING_S` look roomier
   than any run has shown it to be.** **Rule X.**
9. **One interval is uninstrumented, deliberately.** §8.
10. **Deleting an `_emit_timing` call passes the whole test suite.** The guard calls the emitter
    directly, so it proves what the writer writes and not that any particular wait calls it; its
    own docstring says *"a wait that stops calling `_emit_timing` is invisible here."* No other
    test in `tests/`, `tools/` or `workspace/src/` references `CITE_TIMING` or `_emit_timing`
    (`grep -rl` over the three trees, 2026-09-02). **A silently missing record must be detected as
    an absent expected key and never read as a zero.** **Rule E**, against I8's manifest.

### 4.3 Two more, found while writing this file

11. **The same `what` string is emitted by three scenarios under two different ceilings.** §2.3.
    Registered here because it was not in the review that produced the ten above, and because it
    is the one that silently produces a plausible wrong number rather than an obviously missing
    one.
12. **One `what` PATTERN stands for many records, so partial loss is invisible to a presence
    check.** `piece {n}: {milestone}` covers `WORKPIECES x len(milestones(topology))` records —
    **3 x 10 = 30** at full completion, with `WORKPIECES` defaulting to 3
    (`continuous_line.py:100`) and the generated `cell_a_flow.yaml` ladder computing to ten
    milestones, both read on 2026-09-02. **One surviving leg satisfies the pattern**, so a
    presence-only check reports nothing absent and V4 counts the triple present, while a
    `LEG_CEILING_S` margin could rest on 2 of 30 legs with no rule saying so. The same shape
    holds for `a message on {topic}`, `{manager} to appear` and `{arm}'s controllers to be
    active`, each of which is emitted once per arm or per topic. **The count is computable before
    any trial** — from `WORKPIECES`, from the generated topology and from the loops themselves —
    so I8's manifest carries it and rule E reports `k of n`.

### 4.4 The loaded condition's instrument, and its attribution

The 2026-08-29 harness has `cpu_limit_trial.sh`, `cpu_limit_trial_low.sh` and `cpu_limit_rates.sh`,
which apply `docker update --cpus` to the running cell. **That harness is frozen.** Its own README
records that **all three hard-code that checkout's compose project name** in the
`docker ps --filter` that finds the container, and that they therefore find nothing from a
different checkout.

- The scripts are **copied** into `harness/`, each with a header naming the source file and the
  commit it was copied at, and **the originals are not edited**.
- The copy **derives the project name from `cite_project_name` in `scripts/_lib.sh`** rather than
  hard-coding it. Sourcing `scripts/_lib.sh` in this checkout on 2026-09-02 yields
  `cite-digital-twin-3319196271`, which is the name §9 records — derived, not typed.
- **The limit is applied for the whole run, including bring-up**, because bring-up is one of the
  intervals under measurement. The harness watches for the container and applies the limit as soon
  as it exists; **the delay between container start and limit application is recorded per run**,
  and **V6 discards a run whose delay exceeds 10 s**.

---

## 5. What is varied, and what is held fixed

**Varied: two things, and only two.** The CPU allocation (§3) and the scenario.

Held fixed unless named:

| Quantity | Value | Where it comes from |
|---|---|---|
| Tree | `c38a42c`, clean in `model/`, `workspace/src/`, `tools/` | V1 |
| Collision geometry | **`convex_hull`**, the shipped selection, **unflipped** | §0 — flipping it would edit `model/` |
| World throttle | ADR-0043's `<real_time_factor>1</real_time_factor>`, as generated | §0 |
| Entry point | `./scripts/scenario <name>`, with no `--teardown-advisory` | the interactive, strict question |
| Cell | `cell_a`, three arms, headless | the scenarios' own launch |
| Pairing | **none.** `./scripts/sim --pair` is not used and the model declares `sides: single` | §8 |
| Concurrency | **one cell at a time.** No second scenario, no build, no other agent's container | V5, V10 |
| `CITE_LINE_WORKPIECES` | **unset, so `continuous_line` runs the default 3** — and **the value in force is read from the environment and recorded per run**, never assumed from this row | `continuous_line.py:100` reads it from the environment, and `scripts/_lib.sh:1011-1014` forwards **every** `CITE_`-prefixed host variable into the container, so a value set in an unrelated shell would silently change the leg count, the expected record count of threat 12 and the run duration |
| `CITE_PHYSICS_SEED` | whatever `./scripts/scenario` exports, recorded per run | a condition, not a reproducibility claim |
| Container image | `cite-digital-twin:dev`, one image for the whole campaign, its ID recorded | §9 |

**Nothing is rebuilt mid-campaign.** `./scripts/build` runs once before the first trial and its
summary line is recorded; a rebuild during the campaign is a deviation and is reported as one.

---

## 6. Design, sample size and order

**Interleave, do not block** ([`../README.md`](../README.md)). A run is indivisible, so the
interleaving here is over **runs**: conditions alternate rather than being taken in consecutive
blocks, so that a drift in the host over the campaign's duration shows up as scatter within a
condition rather than as a difference between conditions.

| condition | `bringup` | `pick_and_place` | `continuous_line` |
|---|---|---|---|
| **FULL** | 5 | 4 | 3 |
| **C4** | 2 | 2 | 2 |
| **C2** | 2 | 2 | 2 |
| **C1** | 2 | 1 | 1 |

**Minimum 28 runs.** These are **minimums, not quotas**: a run that aborts is reported with the n
it reached and **is never topped up** (V8). A condition that cannot be reached at all — the
cell failing to come up at 1 CPU, say — is reported as **not measured** for that cell, and rule
D3 governs every ceiling it would have carried.

**Order, with the FULL allocation split explicitly, because an earlier draft's order could not
be executed against its own totals.** The table allocates **12** FULL runs; "FULL first for all
three scenarios, then interleave FULL / C4 / C2 / C1 / FULL / …" spends all twelve before the
interleaving starts and leaves none for it. The split is therefore fixed here, in advance:

- **Opening block — one FULL run of each scenario, 3 runs.** Enough to show the harness parses a
  record from each scenario at the condition Q-A and Q-C rest on.
- **Interleaved body — the remaining 7 FULL runs and all 16 loaded runs**, cycling
  FULL / C4 / C2 / C1 and taking the scenarios in rotation, so that no condition is taken in one
  consecutive block.
- **Closing block — the last 2 FULL runs are taken last**, whichever scenarios they fall to.
  **3 + 7 + 2 = 12, which is the FULL total in the table above**, and 12 + 16 = 28, the minimum.

**FULL runs therefore appear at both ends and throughout, which is what makes a host drift over
the campaign's duration visible as scatter within a condition rather than as a difference between
conditions.** If a run aborts, the schedule is **not** re-planned to restore the shape: V8 governs
and the campaign reports the n it reached.

**A 60 s quiesce between a teardown and the next bring-up**, and a check for surviving `gz sim`
processes; a run that finds a survivor from its predecessor is **discarded, not adjusted** (V5,
inherited in shape from the 2026-08-29 campaign's conditions block).

**Every run records:** its label, condition, scenario, start and end wall time, I2's verdict line,
I4, I5 before and after, I6, I7, and the full captured console.

---

## 7. Thresholds — the decision rules

Stated as pass/fail *before* the numbers. Applied literally, including where inconvenient.

### 7.1 The discard and admission rules, applied before any margin is computed

> **Rule Z — a zero-spin record is a non-measurement and is discarded.** A record with
> `spins == 0` is excluded from every margin. **The filter is on `spins`, never on `elapsed_s`.**
> Zero-spin records are **counted and reported per (scenario, what)**, because a `what` that emits
> only zero-spin records has produced no measurement of its interval at all and rule D3 then
> governs it.

> **Rule A — `bringup`'s bring-up margin is assessed against one `what` only.** For
> `bringup.BRING_UP_CEILING_S`, only records whose `what` is **`the arm_1 skill server`**
> contribute. The other four `what` values in that file are dropped because
> `test_a_skill_moves_the_arm_to_its_home_configuration` sorts first alphabetically and absorbs
> the cold bring-up, so every later wait measures an already-running system. The `test` field
> makes this mechanical: the drop is by `what`, and the `test` field is reported alongside as the
> check that the ordering is what this rule assumes. **If the observed first test is not
> `test_a_skill_moves_the_arm_to_its_home_configuration`, this rule's premise has failed and
> `bringup.BRING_UP_CEILING_S` is reported as not assessed under D3** rather than silently
> re-keyed.

> **Rule X — `CYCLE_CEILING_S` records contribute only from runs whose scenario verdict passed
> (I2).** A record from a failed run measures a coordinator that exited early for a reason that is
> not the interval.

> **Rule X2 — every other ceiling admits records from failed runs, and the campaign checks that
> this changed nothing.** A non-`CYCLE` record is emitted only when its own wait succeeded, so it
> is a genuine measurement of that interval whatever a later assertion did. **The margins are
> computed twice: over all valid records, and over records from passing runs only. If the two
> differ in band for any (scenario, ceiling, condition), that cell is reported INCONCLUSIVE**, and
> both numbers are published.

> **Rule G — a mangled record is counted, not dropped in silence.** Lines matching `CITE_TIMING`
> but failing `json.loads` on the regex group, or parsing to a key set other than the seven, are
> reported per run as a count with the raw text of up to three of them. **A run whose mangled
> count exceeds 5 % of its `CITE_TIMING` lines is discarded and reported**, because at that point
> the campaign does not know what it is missing.

> **Rule E — an expected record that never appeared is ABSENT, not zero, and a PATTERN is
> reported `k of n`.** Against I8's manifest, every (scenario, what-pattern, ceiling_s) triple
> that a run should have emitted and did not is reported as absent, per run, with no value
> imputed. **A presence check is not enough, because one pattern stands for many records**
> (threat 12): `piece {n}: {milestone}` covers 30 records at full completion and one surviving
> leg satisfies it. So every triple is reported as **`k of n` present**, `n` being the manifest's
> expected count, and **every margin computed from a pattern carries the `k of n` of the records
> it was computed from, in the same table cell as the margin.** A margin resting on a fraction of
> its expected records is not wrong, but it is a different claim from one resting on all of them,
> and the reader is not asked to work out which they are looking at. **A ceiling all of whose
> expected records are absent across every valid run is reported as not assessed under D3.**

> **Rule P — a trial whose console was not captured produced nothing.** Not a short table: no
> data. It is not reconstructed from the junit report, which carries no stdout.

> **Rule Q — every margin is reported TWICE, and one that changes band between the two readings
> is INCONCLUSIVE.** Poll quantisation biases `elapsed_s` up by at most one loop iteration
> (threat 5), and the bound is a property of the emitting site rather than of the run. So each
> margin is computed from the measured maximum **and** from `max - q`, where `q` is that site's
> quantum, read from the emitters at `c38a42c`:
>
> | emitting site | `q` |
> |---|---|
> | any `_spin_until` or `_await_future` wait whose predicate returns immediately | **0.5 s** |
> | `bringup`'s four `wait_for_service` / `wait_for_server` waits, predicate blocking 0.5 s | **1.0 s** |
> | `pick_and_place`'s skill-server wait, predicate blocking 1.0 s | **1.5 s** |
> | `continuous_line`'s leg loop, spinning on that file's `SAMPLE_PERIOD_S = 0.5` | **0.5 s** |
> | `pick_and_place._run_cycle`, spinning on that file's `SAMPLE_PERIOD_S = 2.0` | **2.0 s** |
> | `bringup`'s `{arm}'s controllers to be active` wait, predicate blocking 10.0 s | **10.5 s** — dropped by rule A, so it reaches no margin |
>
> `ceiling / max` is a **lower bound** on the true margin and `ceiling / (max - q)` is an **upper
> bound** on it; the true margin lies between them. **Both are printed for every cell, beside
> each other, and the band is stated for each.** If the two land in different bands, that cell's
> verdict is **INCONCLUSIVE — the poll quantum spans a band edge**, and both readings and both
> bands are published rather than one being chosen. If `max - q <= 0`, the cell is INCONCLUSIVE
> for the same reason and no upper bound is printed.
> **`q` is subtracted from the maximum only, never from a median or an IQR**, because the margin
> is defined on the maximum and the corrected reading is an upper bound on the margin rather than
> a corrected distribution.
> **This is where it bites.** Against `BRING_UP_CEILING_S = 240.0` a 0.5 s quantum moves nothing.
> Against **`DELIVERY_CEILING_S = 30.0`** — one of the two ceilings this campaign exists to
> assess, and the one **PR2** predicts TOO LOOSE — a true interval of a fraction of a second
> measured half a second late shifts the derived margin by more than 3x, so the headline verdict
> for that ceiling is exactly the one the quantum can move. **Registering Q as a name without a
> decision, which an earlier draft did, would have left that verdict with a quantified bias and
> no rule governing it.**

> **Rule K — a record with `elapsed_s > ceiling_s` is a datum about the two clocks.** It is
> reported, with its run and its `what`, and is **excluded from the margin** for that
> (scenario, ceiling): the campaign cannot tell whether the wait or the clock is what moved. **If
> more than one such record appears in the campaign, the clock disagreement is reported as a
> finding in its own right.**

### 7.2 Q-A and Q-C — the per-ceiling verdict at each condition

For each (scenario, ceiling name, condition), report: n valid records, n discarded by each of
rules Z, A, X, K, and E, the `elapsed_s` distribution (min / median / IQR / **max**), the margin
`M = ceiling / max`, and the verdict:

> **TOO TIGHT** if `M < 1.5`. **APPROPRIATE** if `1.5 <= M <= 10`. **TOO LOOSE** if `M > 10`.
> Bands inherited from 2026-08-29 §5 (§2.2).

> **Rule D3 — INHERITED, and the letter is kept because the rule is the same rule.** From
> 2026-08-29 §5: *"A ceiling whose interval this campaign did not measure is reported as **not
> assessed** — never as fine."* Here it binds every cell of the table: a (scenario, ceiling,
> condition) with **no valid record after §7.1** is **not assessed**. **Never "fine", never
> "loose", never "unchanged", and never carried over from another condition or another scenario
> (rule T).**

> **Rule NOISY — INHERITED from 2026-08-29 §3**, where the earlier campaign numbered it V1. **It
> is renamed here to avoid a collision with this campaign's own V1, which is a different rule
> entirely (§10).** If a (scenario, ceiling, condition) group's `elapsed_s` range exceeds **25 %**
> of its median, the group is marked **NOISY** and its median is quoted only with the range beside
> it. **NOISY decorates and does not overturn the band verdict**, because the margin is defined on
> the maximum by design and a noisy group's maximum is exactly the quantity the definition wants.

**Two ceilings emit exactly ONE record per run, so a band can rest on n = 1.**
`bringup.SKILL_CEILING_S` has a single call site, on `ARMS[0]` only
(`bringup.py:616`), and `pick_and_place.CYCLE_CEILING_S` has one, in `_run_cycle`
(`pick_and_place.py:617`). At the n table's smallest cells that is **one record per condition**,
and at C1 `pick_and_place` is allocated a single run. **Every margin for those two names is
printed with its n and with the sentence "this band rests on N record(s)"**, and where N is 1 the
median, IQR and maximum are the same number and are printed as such rather than as a
distribution. This is acknowledged rather than fixed: topping the cell up would violate V8, and
the n table does not move once this file is frozen.

**The cold bring-up record is reported SEPARATELY from the warm ones, for `pick_and_place` and
`continuous_line`.** In each of those files `BRING_UP_CEILING_S` bounds one genuinely cold wait —
`the skill server, and therefore the whole stack beneath it` and `the first LineState, and so the
line coordinator and the stack below it` — and also the warm `a transform from cite_world to
{frame}` waits, which run against an already-started system. **Pooling them mixes a cold
bring-up with a warm lookup under one name**, which is the same mixture rule A treats as
disqualifying in `bringup`. So `ANALYSIS.md` reports, for each of those two ceilings, the cold
record's margin and the pooled warm distribution's margin **as two lines with two verdicts**, and
**the ceiling's headline verdict is the cold one**, because the cold wait is the interval the
ceiling was sized for. The warm line is published beside it and is never used to soften it.

**Reported separately, as its own line rather than folded into a margin:** for
`pick_and_place.SETTLE_CEILING_S`, the count of records discarded by rule Z. The scenario's own
comment records the settle as *"observed in about a second"*, and the wait's predicate is the
`gz model -p` subprocess of threat 1 — **so this is the ceiling most likely to be assessed
entirely on zero-spin records, and if it is, D3 applies and it is not assessed.**

### 7.3 Q-B — the under-load condition, which is the half #30 leaves open

Report, per (scenario, ceiling): the margin at FULL, C4, C2 and C1 side by side, each with its own
verdict and its own n.

> **B1 — the crossing, with every case it can land in named in advance.** For each ceiling,
> report **the lowest allocation at which its verdict is still APPROPRIATE, and the highest at
> which it is TOO TIGHT**, as a **bracket between two measured allocations**. **No margin is
> interpolated between allocations and none is extrapolated below C1.** The 2026-08-29 campaign
> derived its under-load figures by scaling measured intervals by a ratio of real-time factors;
> this campaign **measures at the allocation** and therefore reports brackets rather than a
> continuous curve.
>
> **An earlier draft defined an output for one case and left five undefined**, including the one
> **PR2** predicts for two ceilings. An operator meeting an undefined case after seeing the data
> would invent a reading, which is what the freeze exists to prevent. So the branches are
> enumerated here, and **in every one of them the four per-condition verdicts and their n are
> printed in full**, so the reading is checkable against the data rather than taken from the
> bracket:
>
> | verdict sequence over FULL, C4, C2, C1 | B1's output |
> |---|---|
> | APPROPRIATE throughout | **NOT LOCATED** — *"not located between 16 and 1 CPU"*, **never "safe at any allocation"** |
> | APPROPRIATE, then TOO TIGHT at some allocation | the **bracket** between the last APPROPRIATE and the first TOO TIGHT |
> | **TOO LOOSE throughout** | **NOT LOCATED — TOO LOOSE THROUGHOUT.** *"This ceiling was not APPROPRIATE at any allocation tried; no crossing exists to bracket."* It is **not** reported as a crossing below C1, and its TOO LOOSE verdict stands at every condition |
> | TOO LOOSE, then APPROPRIATE lower down, **no TOO TIGHT anywhere** | **two statements, both made**: the bracket of the TOO LOOSE -> APPROPRIATE crossing, and **NOT LOCATED** for the APPROPRIATE -> TOO TIGHT one. Neither is used to summarise the other |
> | TOO LOOSE, then APPROPRIATE, then TOO TIGHT | **both brackets**, reported as a pair |
> | **TOO TIGHT at FULL** | **TOO TIGHT THROUGHOUT.** No APPROPRIATE allocation was found between 16 and 1 CPU, and PR1 is refuted |
> | **non-monotone** — any sequence that is not TOO LOOSE -> APPROPRIATE -> TOO TIGHT in that order as the allocation falls | **NOT LOCATED — NON-MONOTONE.** The sequence is printed verbatim with its n per cell and **no bracket is read from it.** At n = 1-2 per cell a non-monotone sequence is within sampling variation, and this campaign does not distinguish that from a real non-monotonicity |
> | any cell **not assessed** (D3) or **INCONCLUSIVE** (rule Q, X2, V7) | a bracket **may not span it**. The bracket is reported **open** on that side, naming the allocation that was not assessed — *"between C4 and C1, C2 not assessed"* — and rule N governs the prose |

> **A timeout is a reportable outcome and is not a missing data point.** A wait that hits its
> ceiling emits **no record**, by design — a record for a wait that timed out would measure the
> ceiling rather than the milestone. That silence is reported as **"fired at C<n>"** from I2's
> verdict line and the failure text, alongside a **not assessed** under D3 for the margin. **The
> two statements are made together, and neither is used to soften the other.**

> **Rule F — a ceiling that fired in ANY contributing run is reported FIRED and receives NO
> band.** An earlier draft said a fired ceiling produces silence in its table cell. **That is
> true only when the ceiling fires on its first and only instance, and this campaign will meet
> two cases where it does not**, both read from the emitters at `c38a42c`:
>
> - **`continuous_line._run_one_piece` emits per milestone and `break`s on the one that times
>   out** (`continuous_line.py:1169-1176`). The earlier legs have already emitted, so their
>   records survive a leg that fired. It asserts nothing; the verdict is taken once at the end.
> - **`bringup._spin_until`'s assertion fails one test method and `unittest` continues.** There
>   are **eight** pre-shutdown test methods in that file, so seven keep running and keep emitting
>   after one has timed out.
>
> So a margin **can** be computed over the survivors, and a ceiling that **demonstrably fired in
> that run** could be banded APPROPRIATE or even TOO LOOSE off the instances that completed —
> which would be this campaign's worst possible output. **Therefore: any (scenario, ceiling,
> condition) in which that ceiling timed out in any contributing run is reported FIRED, with the
> run named and the failure text quoted, and receives NO band at all** — not APPROPRIATE, not
> TOO LOOSE, not TOO TIGHT. The surviving records' distribution is still published under the
> FIRED label, because it says what the completing instances cost, and **no sentence may derive a
> verdict on the ceiling from it.** FIRED is decided from I2's verdict line and the failure text,
> never from the absence of a record.

### 7.4 Q-D — the instrument

Report per run and pooled: total `CITE_TIMING` lines, mangled (rule G), zero-spin (rule Z),
absent expected keys (rule E), clock-disagreeing (rule K), and the count dropped by rule A. **This
table is published whatever the margins say**, because it is what tells the next campaign whether
these records can be trusted.

### 7.5 The refusal rule, and it is mandatory

> **Rule N — silence is not a pass, in the rule-S / rule-W shape this directory already uses.**
> **The letter is REUSED and the reuse is declared, the way rule NOISY's rename is.** `Rule N` in
> [`2026-09-01-grasp-discrimination/`](../2026-09-01-grasp-discrimination/criteria.md) §7.8 and
> in [`2026-09-02-option-f-regions/`](../2026-09-02-option-f-regions/criteria.md) §7 is the
> **false-positive null**, which is a different rule about a different quantity. Nothing here
> inherits from it, and a citation of "rule N" must name the campaign it belongs to.
> **If the campaign produces no valid record for an interval, it has not tested that ceiling.**
> Its silence there may not be read as a pass, as a validation of the ceiling's value, as evidence
> that the ceiling is large enough, or as a reason to leave the ceiling alone. The verdict is
> written as **"not assessed at n = 0 valid records, under these conditions, on this machine"**,
> and **no sentence in `ANALYSIS.md` may imply otherwise.**
>
> This is D3's twin and not a duplicate of it: **D3 decides what goes in the verdict column; N
> constrains what the prose may say around it.** The 2026-08-29 campaign needed exactly this and
> did not have it in words. It **did** state D3 in that section, and it then carried the heading
> *"No ceiling is too tight and none is too loose"* over a table of eight rows, **two of which its
> own rule had just marked not assessed** — a statement about every ceiling, placed above a table
> that assessed six of them.

### 7.6 Pre-registered predictions, so that this campaign can be wrong

**They are numbered `PR<n>`, not `P<n>`, and the reason is a collision inside this document.**
`P1` and `P2` are CLAUDE.md §3's hard rules — one source of truth, and sim/real
interchangeability — and **this file uses both in that sense**, at §0 and §11 for `(P1)` and at
§1 for *"no figure here may be read as a P2 result"*. A prediction table numbered `P1`-`P7`
would put two meanings of `P2` in one document, one of them a prediction this campaign expects to
confirm and the other a rule it must not be read as testing.

| # | Prediction | Refuted by |
|---|---|---|
| **PR1** | At FULL, **no ceiling is TOO TIGHT** — every assessed margin is `>= 1.5` | any assessed margin below 1.5 at FULL |
| **PR2** | At FULL, `bringup.DELIVERY_CEILING_S` and `bringup.TRAJECTORY_CEILING_S` — the two the 2026-08-29 campaign could not assess — are **TOO LOOSE** (`M > 10`), because they bound sub-second and second-scale intervals against 30 s and 60 s | either landing APPROPRIATE or TOO TIGHT |
| **PR3** | `pick_and_place.SETTLE_CEILING_S` is **not assessed** at every condition, because every one of its records is discarded by rule Z | any non-zero-spin settle record |
| **PR4** | At C1, `pick_and_place` **times out on `CYCLE_CEILING_S`** and emits no cycle record, so that cell is reported FIRED under rule F and receives no band. The 2026-08-29 campaign's scaled arithmetic predicted timeouts below about 1.2 cores | the cycle completing at C1 |
| **PR5** | `continuous_line.LEG_CEILING_S`, measured on real legs for the first time, is **APPROPRIATE** at FULL | TOO TIGHT or TOO LOOSE at FULL |
| **PR6** | Rule G's mangled count is **zero across the whole campaign**, and rule K's is zero too | any mangled or clock-disagreeing record, either of which is a finding about the instrument |
| **PR7** | `bringup.BRING_UP_CEILING_S` yields exactly **one** contributing record per run after rule A | any other count, which falsifies rule A's premise |

**A refuted prediction is a result and is reported as one.** None of the seven is a threshold; the
thresholds are §7.1 to §7.3, and they do not move if a prediction fails.

---

## 8. Explicitly not measured, recorded here rather than discovered later

- **The follower-settle loop in `bringup.test_the_gripper_linkage_is_actually_coupled`.** It
  carries `DELIVERY_CEILING_S`, and it **emits nothing, deliberately**: it breaks on a convergence
  condition it does not assert and **runs to the ceiling on non-convergence**, so the interval it
  bounds is not a milestone and a record for it would be a measurement of the ceiling. **So
  `bringup.DELIVERY_CEILING_S` is assessed over its five instrumented waits and not over this
  one**, and this campaign's margin for that ceiling is a statement about the five. It is not
  rounded up, and the loop is not instrumented by this campaign — that would edit `tests/`, which
  **§0 names among the five paths it forbids editing and V1 watches**. An earlier draft made this
  appeal to a §0 that watched three paths and did not mention `tests/` at all.
- **The 10 s service-call timeout inside `bringup.test_every_controller_reaches_active`.** It is a
  call timeout, not one of the file's ceilings, and no margin is computed for it. **It is
  nevertheless the largest poll quantum in the tree** — it bounds the `{arm}'s controllers to be
  active` wait's overshoot at about 10.5 s (threat 5) — and rule A drops that wait for an
  unrelated reason, so no margin here carries it.
- **The upper tail of every interval.** A wait that times out emits no record, so **this campaign
  can only ever see intervals that completed.** Every margin here is computed over the completing
  half of the distribution, and the slowest instance it reports is the slowest **that finished**.
  This is a structural bound on the whole campaign, not a caveat on one number.
  **The bias has a direction, it is one-sided, and it is stated here rather than left for a
  reader to derive.** `M = ceiling / max`, so **every censored instance removes a candidate for
  the maximum and can only make the maximum smaller, never larger** — and a smaller maximum is a
  larger `M`. **So censoring biases every margin UP, toward TOO LOOSE, and never toward TOO
  TIGHT.** Two consequences, both binding on `ANALYSIS.md`: a **TOO LOOSE** verdict here is the
  verdict most exposed to the bias and must be written with it named, and a **TOO TIGHT** verdict
  is the one censoring cannot have manufactured. Rule F is what keeps a run in which the ceiling
  demonstrably fired from being banded at all.
- **A CPU quota is not a smaller machine.** The loaded conditions apply `docker update --cpus`,
  which sets a CFS quota on the same sixteen cores. The 2026-08-29 campaign recorded the
  limitation and this campaign inherits it verbatim rather than rediscovering it:
  [`2026-08-29-real-time-factor-conditions/ANALYSIS.md`](../2026-08-29-real-time-factor-conditions/ANALYSIS.md)
  — *"A quota throttles a process that would otherwise use more; a machine with fewer physical
  cores behaves differently in cache and scheduling. The curve is a curve in available CPU time
  … but it is not a simulation of a smaller machine."* **So C4, C2 and C1 are allocations of CPU
  time and not core counts**, and no margin here may be described as the margin on a four-, two-
  or one-core machine. It is the right variable for Q-B — contention takes CPU time away in the
  same currency — and it is not the machine.
- **How much of any margin the two levers bought.** #30 says the throttle and the hulls must be
  folded in, and this campaign folds them in by **measuring the shipped configuration**, not by
  comparing it with an unshipped one. **Measuring a vendor-mesh or throttle-lifted control would
  require editing `model/` or the generated world, which §0 forbids and V1 discards.** So the
  campaign reports the margin on the shipped configuration and **attributes nothing to either
  lever.** The capacity difference between the two geometries is
  [`2026-09-01-capacity-on-shipped-main/`](../2026-09-01-capacity-on-shipped-main/ANALYSIS.md)'s
  result and is cited, not copied.
- **Whether the 2026-08-29 margins were right.** Different machine, different architecture,
  different geometry, different world. **Rule H.**
- **Any machine but the one in §9**, any container image but the one recorded there, and any CI
  runner. CI's own scenario history is a separate body of evidence (CLAUDE.md §2) and is not
  extended by this campaign.
- **Hardware.** No physical arm exists in this measurement.
- **A paired cell.** `./scripts/sim --pair` is not used; the shipped model declares
  `sides: single`, and pairing it would edit `model/`.
- **GUI and rendering cost.** Every run is headless.
- **Teardown, scenario pass rates, real-time factor and capacity.** §1.
- **The three pre-campaign scenario runs, none of which is data.** §11 names all three with
  their commits.

---

## 9. The machine, named

[`../README.md`](../README.md) gained the requirement to name the machine with the capacity
campaign. It matters more here than almost anywhere: **every ceiling in this campaign is a
wall-clock ceiling**, so every margin is a fact about a machine.

| | |
|---|---|
| Host | Linux **7.0.0-30-generic**, **x86_64**, **16** cores, **31 GiB** RAM |
| Free disk | **400 GiB** available on `/` at the time this file was written |
| Docker | **29.7.2** (build a7dcaa6); Docker Compose **v5.5.0** |
| Container image | **`cite-digital-twin:dev`**, image ID `3a41d4e431b0`, Ubuntu **24.04.4 LTS**, ROS 2 **Jazzy**, Gazebo Sim **8.11.0** — all four read from inside the image on 2026-09-02 |
| Isolation | compose project **`cite-digital-twin-3319196271`** and **`ROS_DOMAIN_ID` 43**, both derived from this checkout by `scripts/_lib.sh` and read from it on 2026-09-02, not typed in |
| Allocation | the container is **not** CPU-limited by default: `/sys/fs/cgroup/cpu.max` inside a plain `docker run` of the image reads **`max 100000`**, and `nproc` reads **16**. The loaded conditions apply the limit explicitly (§4.4), and **only the first of those two readings moves when they do** — see below |

**Host load before the first trial, measured rather than claimed.** Two readings taken while this
file was being written, on a host up **3 h 46 m**:

```
0.09 0.64 1.44        (host /proc/loadavg, 16 cores)
0.11 0.43 1.23        (host, minutes later)
0.11 0.43 1.23        (inside a container of the image, seconds after the line above)
```

**This host was quiet at the time of writing**, and that is a statement about that moment rather
than about the campaign: I5 records the load before and after every run, and V7 is what spends it.
A one-minute load of 0.09 on 16 cores is quiet by any reading; the fifteen-minute figure of 1.44
reflects the work that produced this file.

> **A container load reading comes from the container, and on this host that is the host's.**
> `/proc/loadavg` is not namespaced on native Linux and there is no `lxcfs` in the way, so the two
> readings above are **identical to the hundredth** taken seconds apart from inside and outside a
> container — which is the demonstration, not an assumption. **This is not true everywhere and it
> is why the distinction is written down**: the 2026-08-31 capacity campaign applied a validity
> rule that read a Docker Desktop **VM's** load rather than the host's, and applied it literally
> anyway. Here the two coincide, and **every load figure this campaign publishes names where it
> was read.**

> **`nproc` does NOT respond to a cgroup CPU limit, and I4 therefore does not use it.** An
> earlier draft of this file asserted the opposite. `docker --cpus` sets a **CFS quota**;
> `nproc` reports `sched_getaffinity`, which a quota does not touch. **Measured on this host on
> 2026-09-02, Docker 29.7.2, on a container of the image named above**: after
> `docker update --cpus 4`, `nproc` inside it still read **16**, while
> `/sys/fs/cgroup/cpu.max` moved from `max 100000` to `400000 100000`, and to `100000 100000`
> under `--cpus 1`. **`docker inspect` moves `.HostConfig.NanoCpus`** — 0, then 4000000000, then
> 1000000000 — **and leaves `.HostConfig.CpuQuota` at 0 throughout**, so a harness reading
> `CpuQuota` concludes "no limit" on a limited container. I4 therefore reads `cpu.max` from
> inside and `NanoCpus` from outside, and the **16** in the table above is a property of the
> machine at FULL rather than a reading of any limit. §8 carries what a quota is not.

---

## 10. Validity rules, registered before the first trial

A rule that only ever confirms is not a rule.

- **V1 — `v1_clean`, and it is the load-bearing rule of this campaign.** A block contributes only
  if **at BOTH ends of the run** — I6 is taken twice — `git diff c38a42c..HEAD -- model/
  workspace/src/ tools/ tests/ scripts/` is **empty** and `git status --porcelain` shows **no
  dirt** in those five paths. **`v1_clean` is the CONJUNCTION of the two readings**, and a run
  whose two readings disagree is discarded and reported as an edit that landed mid-run.
  **The five paths, and why an earlier draft's three were not enough.** All nine `*_CEILING_S`
  declarations and every `_emit_timing` definition and call site are in `tests/scenarios/`, and
  `scripts/` holds I2's verdict strings and §4.4's `cite_project_name`. Watching three paths
  would have let a ceiling value, a `what` string or a spin quantum change mid-campaign with
  `v1_clean` still true — the one thing this rule exists to prevent. `git diff --stat
  c38a42c..HEAD -- tests/ scripts/` is empty, read on 2026-09-02, so the wider watch costs
  nothing.
  **A single snapshot at the start of a run was the second half of the same defect.** A run lasts
  minutes; an edit landing after the snapshot would leave the flag true for the whole run, while
  V10 below promised mid-block detection. I5 is taken before and after every run and I4 after
  application and at the end; **I6 now matches them**, and V10's promise is a fact about the
  mechanism rather than a claim ahead of it.
  **The flag is computed where the block is taken and travels ON the record; `analyse.py` drops
  any row without it.** Not a note in a README, not a check at the end: a field.
  **`docs/measurements/` may advance while the campaign runs and nothing else may** — this
  campaign's own `criteria.md`, harness and raw all land on this branch, so `HEAD` necessarily
  advances and pinning it would discard every block including the first.
  **Why the base is `c38a42c` and not `51195e0`.** `git diff --stat 51195e0..c38a42c -- model/
  workspace/src/ tools/ tests/ scripts/` names **six** files, read on 2026-09-02. Four are the
  instrument this campaign exists to consume — the three scenarios and
  `tests/scenarios/guards/test_timing_records.py`, added by `eef5468`, `59f818d` and `c38a42c` —
  and basing on `51195e0` would mark every block dirty for the very change that makes the
  campaign possible. The other two, `tools/tests/test_stall_band.py` and
  `workspace/src/cite_skills/include/cite_skills/gripper.hpp`, are **comment- and
  docstring-only**, verified by diffing them on 2026-09-02, and have no bearing on any interval
  measured here. **Basing on `c38a42c` makes the flag mean what it says.** An earlier draft named
  only the last two, because it watched only three paths.
- **V2 — the configuration that actually ran.** Every run reads back, from the **running cell**,
  the collision selection its description points at and the `<real_time_factor>` in its world
  (I7). A run that does not read `convex_hull` and the throttle is **discarded and reported**: it
  is not a measurement of the shipped configuration.
- **V3 — the run's verdict travels with every record.** I2's verdict line is recorded per run and
  attached to each of that run's records. Rule X and rule X2 in §7.1 are what consume it.
- **V4 — record completeness.** Every run is checked against I8's manifest. A run missing more
  than **half** its expected triples is **discarded and reported** — at that point the campaign
  does not know whether the scenario ran the waits at all.
- **V5 — one cell, no survivors.** `gz sim` processes are checked for and cleared after every run;
  a run that finds a survivor from its predecessor is **discarded, not adjusted**. Inherited in
  shape from the 2026-08-29 campaign's conditions block.
- **V6 — the allocation was in force for the whole run.** A loaded run contributes only if I4
  confirms the limit both after application and at the end of the run, **and** the delay between
  container start and limit application is at most **10 s**. A run exceeding it is discarded and
  reported: part of its bring-up ran unconstrained.
- **V7 — the load is recorded, and a loud host is reported rather than excluded.** I5 is taken
  before and after every run. **No run is discarded for load**, because a load threshold chosen
  after seeing the data is a threshold chosen by the data; instead, **if the pre-run one-minute
  load exceeds 4.0 on 16 cores for any run, that run is flagged and every margin it contributes to
  is reported with and without it**, and if the band verdict differs, that cell is INCONCLUSIVE.
  This is the shape the 2026-08-31 campaign's literal application of a load rule taught.
- **V8 — n is what it was.** Every count is reported over the runs and records that actually ran.
  **No condition is topped up** to match another, and a block that aborts early is reported with
  the n it reached.
- **V9 — no threshold moves.** Nothing in this file changes once the first campaign trial has run.
  **A threshold discovered to be wrong is applied literally and recorded as wrong**, and the
  disagreement becomes a numbered deviation in `ANALYSIS.md`, applied to data already collected.
  The 2026-08-31 capacity campaign applied a validity rule it had found to be reading the wrong
  quantity, literally, and reported it; that is the precedent.
- **V10 — one writer at a time.** **A concurrent agent editing a watched path mid-run flips
  `v1_clean` and silently discards the block** — which is a fact only because V1 takes I6 at both
  ends of the run and conjoins the two readings; with a single snapshot at the start, this
  sentence would have been prose ahead of the mechanism. So the campaign runs with **one writer in this
  checkout**, and the campaign operator states in `ANALYSIS.md` whether that held. A campaign that
  loses blocks this way reports the loss under V1 rather than re-running until it stops happening.
- **V11 — no rebuild mid-campaign.** `./scripts/build` runs once before the first trial. If a
  rebuild becomes necessary, it is a numbered deviation and every run before it is reported
  separately from every run after it.

**One shakedown run per harness is permitted and is not data.** Before the first campaign trial,
each harness may be run **once** to prove it starts, captures a console and parses a record. Its
output is published under **`raw/shakedown/`**, is **excluded from every figure in §7**, and **may
not be used to set or adjust any threshold in this file** — every threshold above is derived from
the inherited bands, from the emitters' own structure, or from the ceilings themselves, and none
of them needs a shakedown to exist. If the shakedown reveals a defect, **the harness is fixed and
this file is not touched.**

---

## 11. Honesty bounds fixed in advance

- **This campaign changes nothing and proposes nothing.** No ceiling, threshold, tolerance or band
  moves because it ran. **Changing a ceiling is the project owner's decision.** §0.
- **THREE scenario runs were taken before this file existed, one of each scenario, and all three
  are named.** An earlier draft declared one of them; §11's whole purpose is that nobody later
  mistakes a pre-campaign run for a trial, and naming one of three defeats it.
  - **`bringup`, at `eef5468`.** That commit's message records a passing
    `./scripts/scenario bringup` emitting well-formed lines, every `elapsed_s` below its
    `ceiling_s` — the run that established the instrument emits at all. **Its line count is
    deliberately not repeated here**, because a pre-campaign observed count sitting in this file
    is exactly the kind of figure a later reader would mistake for I8's expected count.
  - **`pick_and_place`, at or before `59f818d`.** That commit's docstrings carried a zero-spin
    `elapsed_s` observed in a `pick_and_place` run; **`c38a42c` removed the figure** for having
    no campaign behind it, which is the same judgement this bullet makes.
  - **`continuous_line`, on 2026-09-02 at `aca48f7`.** Its only role was to establish that the
    leg emission fires at all.
  **None of the three is campaign data.** No figure from any of them may appear in this file, in
  `raw/`, or in the write-up. **They did not contaminate this file**: it states no measured
  `elapsed_s`, no observed record count and no margin. Every quantity in it is derived from the
  emitters' source, from the inherited bands or from the ceilings themselves — including threat
  12's expected count of 30, which is `WORKPIECES` times the generated ladder's length and would
  be the same number if no scenario had ever been run. This is a completeness gap in the
  declaration, closed before the first trial, and not a contamination.
- **A null is not a pass.** Rules D3, N, T, E, Z, Q and F exist for exactly that, and all seven
  were written before any trial ran. **Rule N is the one that matters most**: a ceiling this campaign
  fails to reach is a ceiling this campaign has not tested, and its silence may not be read as a
  clearance. The campaign it inherits from had to write *"not assessed"* twice and this one
  expects to write it again.
- **The conditions are not each other's evidence, and neither are the scenarios.** Rule T.
- **The 2026-08-29 figures are on a different machine and are never differenced against these.**
  Rule H.
- **This measures the simulator, on one machine, on one image, at one commit, in one checkout, and
  it says nothing about hardware.**
- **It is not a determinism claim.** `CITE_PHYSICS_SEED` reaches `gz sim --seed` only, which does
  not seed the physics solver.
- **It is not a rate**, and the count of scenario passes it happens to observe is not a result.
- **Every campaign it cites stays frozen.** No file under
  `2026-08-29-real-time-factor-conditions/`, `2026-08-31-capacity-and-clock-deficit/`,
  `2026-09-01-capacity-on-shipped-main/` or any other campaign directory is edited, re-run or
  re-analysed here. The CPU-limit scripts are **copied with attribution**, never edited in place.
- **Figures stay in this directory.** Nothing produced here is copied into `CLAUDE.md`,
  `docs/open-work.md`, any ADR, any layer document or any comment in `tests/scenarios/` (P1). Cite
  the directory.
