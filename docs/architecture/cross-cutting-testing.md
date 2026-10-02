# Testing strategy

- **Status:** `PARTIAL` — `./scripts/test`, `./scripts/scenario` and the two-stage CI
  workflow exist and run real tests. The unit level is populated — host tests under
  `tools/tests/` and `tests/`, and shell self-tests for the gate logic in `scripts/_lib.sh` —
  and so is the contract level: every interface definition in `cite_interfaces` is frozen
  against a stored baseline. **Ask the command for a count**
  (`.venv/bin/python -m pytest tools/tests --collect-only -q`); three host test files
  parametrise over every tracked file, so the count grows with the repository and measures
  the tree as well as the suite.
  The scenario level has two, both blocking CI gates on `cell_b`'s plant: `bringup`, run twice
  per run, and `program_cycle`, which runs the real robot's program
  ([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md)) for one cycle and
  asserts where the work-piece ends. Both run with `--teardown-advisory`, which splits the two
  questions a scenario answers in one exit code: **the cycle gates, the post-shutdown teardown
  is reported and does not gate.** It exempts no process and deletes no assertion — see the
  phase-split block in `scripts/_lib.sh`. **No scenario brings the pair up**; the twin boundary
  is held only by `cite_twin`'s own tests
  ([ADR-0057](../adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md) clause 4).
  One gap below is still open and is called out where it occurs: **scenarios are not
  deterministic.** Everything else below the status line is design, not description.
- **Related:** charter §9, [`../onboarding/development-workflow.md`](../onboarding/development-workflow.md),
  [`../measurements/README.md`](../measurements/README.md)

## Why this is a cross-cutting concern rather than a chore

The v1 workspace had **zero tests**. That is not incidental to how it failed — it is the
mechanism. A handoff coordinator published to a topic nothing subscribed to, and the defect
survived indefinitely because nothing ever asserted that a handoff completes. A state
machine had no exit from `MOVING_TO_PICK`, and nothing ever ran it far enough to notice.

P6: *nothing is done until tested and reproducible.* Everything below is how that is met.

## The pyramid

| Level | Scope | Runtime | Where |
|---|---|---|---|
| **Unit** | Pure logic, no ROS | milliseconds | `tools/tests/`, per-package tests |
| **Integration** | Node and launch behaviour | seconds | `launch_testing` |
| **Scenario** | Whole system, headless simulation | minutes | `tests/scenarios/` |
| **Contract** | Interface compatibility | milliseconds | per interface package |

Push tests down. A behaviour verifiable in a unit test should not need a simulation — the
scenario suite is the slowest and most valuable resource, and filling it with things a
unit test could have caught wastes it.

### Unit

Everything in `cite_tools` — schema validation, generators, geometry and inertia checks —
is pure Python and must be unit-tested. No ROS runtime, no simulator, no waiting. These
run on macOS.

`tools/tests/` covers the schema loader, the generators, identifiers, units, geometry, the
gripper linkage, close rate and stall threshold, and the geometric and referential
validators. `./scripts/test` runs them, and `./scripts/test --host-only` runs them without
Docker. The count is in the status line above and is deliberately not repeated here (P1).

Alongside them, `scripts/_selftest.sh` covers the **gate logic itself** — the lint coverage
assertion, the manifest SHA validator, and the DDS domain derivation. Those checks had no
tests of their own, and two of them were silently doing nothing for months as a result.

### Integration

`launch_testing` covers what only appears when nodes interact: lifecycle transitions, QoS
compatibility, parameter loading, namespace correctness, clean shutdown.

**QoS compatibility deserves a dedicated test.** Incompatible QoS connects silently and
delivers nothing — the topic exists, both endpoints appear in `ros2 topic info`, and no
data flows. It is the ecosystem's most-misdiagnosed failure, and it is trivially catchable
by asserting that a message actually arrives.

**A test of a safety gate is not finished until it has been mutation-checked.** The worked
example is the planning pipeline's collision gate
([ADR-0027](../adr/0027-pilz-planning-pipeline.md)): the gate was removed, the tree
**regenerated rather than hand-edited**, and the one test that should fail was confirmed to
fail while every other test in the file still passed. Without that step, a test that passes
proves the system works *or* that the test is inert, and the two are indistinguishable —
which is the same argument that makes "the fallback was never taken" evidence of nothing.
Pair it with an **anti-vacuous** assertion: remove the precondition and the test should fail
saying the premise is gone, not pass quietly.

### Scenario

Full system, headless, in the container, driven by `./scripts/scenario <name>`.

**Each checkout gets its own DDS domain.** Everything used to default to
`ROS_DOMAIN_ID=0`, so two cells running at once on one host discovered each other's nodes:
a scenario run was measured at 421 s instead of 105 s because another workspace's
`move_group` was in its graph. `scripts/_lib.sh` now derives a domain from the checkout
path, which isolates concurrent runs while keeping `./scripts/enter` and `./scripts/sim`
from the same checkout on the same domain, so a shell can still attach to the cell it
launched. Export `ROS_DOMAIN_ID` to override it and join someone else's cell deliberately.
`./scripts/doctor` reports the value in force.

**Scenarios are not deterministic yet.** This section previously stated that they were.
They are not, and the gap is load-bearing enough to state plainly:

`./scripts/scenario` decides `CITE_PHYSICS_SEED` once per run, and
`cite_bringup/launch/simulation.launch.py` now passes it as `gz sim --seed`. **`./scripts/sim`
decides none**, and the launch file omits `--seed` entirely when the variable is unset — so an
interactively launched cell, paired or not, is unseeded. **That is less
than it sounds and must not be read as more.** `gz sim --seed N` reaches
`ServerConfig::SetSeed()`, whose body is `math::Rand::Seed(_seed)` — so it seeds
`gz::math::Rand`, which is what sensor noise and the comms systems draw from. It does not
seed the physics solver: no library under `gz_physics_vendor` or `gz_dartsim_vendor`
references `gz::math::Rand` at all, and `libdart` keeps its own generator. And it reaches no
planner at all.

**A run under one seed has been repeated, with thresholds registered before the first trial,
and the cell did not reproduce**
([`2026-09-22-is-a-run-reproducible`](../measurements/2026-09-22-is-a-run-reproducible/ANALYSIS.md),
taken on a pick-and-place scenario that has since left the main tree). Both runs passed and
put the work-piece in two different places. Two runs on one machine is not a rate, and the
campaign's own control did not clear, so where the irreproducibility enters is **UNRESOLVED**
and may not be attributed to the solver, the coupling or the planner. The simulated grasp
hold ([ADR-0061](../adr/0061-hold-the-box-while-the-jaws-are-shut.md)) has since removed one
source of spread; nothing has re-measured the cell.

**Which part is stochastic has changed; that scenarios are not reproducible has not.**
[ADR-0027](../adr/0027-pilz-planning-pipeline.md) is the single record of both — the
evidence that OMPL cannot be seeded through MoveIt and would not be deterministic if it
could, and the decision that moved station-to-station motion to a non-sampling planner. It
is not restated here (P1). What matters at this level is the residue: Pilz answers by
default, the OMPL **fallback** remains unseeded and unseedable, and the physics solver is
untouched by any of it. **The decision does not by itself make a scenario reproducible**,
and nothing here may be upgraded on the strength of it — under P8 the claim is earned by
running scenarios repeatedly and measuring, or it is not made.

Until then a passing scenario is evidence about that run only. The design intent stands and
is what the seed exists for: a fixed seed so that a failure reproduces instead of being a
coin flip, because a non-deterministic scenario test is worse than no test — it trains
people to re-run until green.

### Wall-clock ceilings, and the machine condition they were sized for

**This is the one place in the tree that states the development host's real-time factor with
its condition; everywhere else cites the campaign.** Every ceiling in `tests/scenarios/` is
wall clock — the scenario observer nodes deliberately do not set `use_sim_time`, and
`bringup.py`'s comment at its first wait gives the reason — so every one of them scales inversely
with real-time factor, and a timeout is as much a statement about the host as about the code.

The figure those ceilings were written against — real-time factor about **0.14**, with
`joint_states` at roughly **21 Hz** against the configured 150 Hz — is **conditional, not
wrong.** It reproduces on the macOS development host, both halves of it together and by two
independent instruments, when the cell is confined to about **one CPU core**. Unconfined on
that same host the cell idles slightly above real time and `joint_states` runs at or above
its configured rate; an idle cell wants about four cores and gets no faster above that. Load
costs roughly 40 %, not a factor of seven, and bring-up is not a slow phase. Every figure,
the CPU curve they sit on, and the measured margin of each ceiling are in
[`../measurements/2026-08-29-real-time-factor-conditions/`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md)
and are cited rather than copied (P1).

**The flake class this creates.** The margins are wall clock, so they shrink with the host:
that campaign found a cycle ceiling of its day that timed out **with nothing broken** below
roughly 1.2 cores. `program_cycle`'s ceilings were sized after it and **have not been measured
against any allocation**; the point applies to them unchanged. Before looking for a motion bug,
check
what the container was allocated and what else was holding the host. **Never answer such a
timeout by widening a ceiling** — a ceiling sized for a starved machine can no longer catch a
hang on a healthy one, and that is the signal being spent.

**Do not measure real-time factor with Gazebo's own `real_time_factor` field.** It is a
smoothed estimate and it does not degrade with the thing it reports: under CPU starvation it
over-reports by up to a factor of four, and the two numbers disagree inside the same message.
The trap is specific — at half a core that field prints a value within rounding distance of
the recorded 0.14 while the cell is actually running at a twenty-fifth of real time, so a
reader trusting it would "confirm" the figure under a condition four times worse. Measure
`Δ sim_time / Δ real_time` from `/world/<zone>/stats` over a stated window instead, and state
the machine, its CPU allocation, what else was running and what the cell was doing. The
campaign's §4 is the recipe.

### Measuring in this cell: interleave, never block

This follows from the paragraphs above rather than softening them — the cell is still not
reproducible, and nothing here should be read as saying otherwise. It is about how to
compare two configurations *given* that it is not.

**Some of what this cell does is bimodal, not continuous.** The grasp twist under friction
alone was the worked example: a trial lands in a high state or a low one, and the physics
timestep changes how often the high state is entered rather than moving a magnitude. The two
**grasp** campaigns in [`../measurements/`](../measurements/README.md) turn on this.

Two rules come out of that, and they apply to any comparison run against this cell.

1. **Interleave the conditions against one running cell.** The first campaign ran each
   condition as its own consecutive block; the second reports that five of those blocks —
   which it treats as the same condition — have medians spread from 5.2° to 29.8°, a
   two-state process sampled with too few trials per block to see it. Block structure buys
   nothing here and hides a great deal. The second campaign alternated conditions and got an
   answer a rank test over the pairs agrees with.
2. **A median is the wrong summary for a two-state variable.** Report the rate of entering
   the high state, at a threshold fixed before the data was seen, with an interval on it.

The general form of the mistake is worth naming, because it is not specific to grasping: in
a system whose runs are independent samples rather than replicates, any structure in the
*order* of the runs can be read as an effect of the variable. Interleaving is what removes
it. Where a comparison genuinely cannot be interleaved, say so, and treat the result as
weaker than a threshold test makes it look.

A scenario asserts on **outcomes and constraints**, never on exact trajectories. A test
asserting an exact joint sequence will be flaky and will be deleted by whoever is on call.

**A deterministic planner does not relax this rule.** Sampling-based planning is stochastic
([ADR-0006](../adr/0006-moveit2-motion-planning.md)) and is still reachable through the
OMPL fallback, so a scenario cannot know which planner answered. And even where Pilz did:
it makes the same *request* produce the same answer, not the request the same. The one
place a trajectory may be the subject of an assertion rather than a proxy for a motion
having gone well is the planner's own launch test — see
[ADR-0027](../adr/0027-pilz-planning-pipeline.md), which is where that distinction is
argued.

Good: *the work-piece ends on the belt's outfeed within the cycle ceiling, the arm never
exceeds its workspace bounds, no collision is reported.*

### Contract

Interface definitions are checked against a stored baseline. A breaking change to a
`.msg`, `.srv`, or `.action` fails the build rather than surfacing at runtime in a consumer
nobody thought about.

## Negative controls

Some assertions are only as good as the setup that reaches them. A test that says *"SIGINT
taken inside message conversion still exits 0"* is worth nothing unless the signal really
lands inside message conversion — and if the fixture that places it there quietly stops
working, the assertion goes on passing and stops meaning anything. It has become a **vacuous
pass**: green, and evidence of nothing. Nothing in the test itself can distinguish the two
states, because from inside, "the thing under test is correct" and "the setup no longer
exercises it" look identical.

A **negative control** is the second assertion that tells them apart. It drives the same
fixture with an input **known to fail** and asserts that it still does. If the control goes
green, the fixture has stopped exercising what it claims to, and the positive assertion beside
it must not be believed until that is understood.

The worked example is `cite_runtime`. `test/spinning_probe.py` carries the pre-`runtime`
shutdown idiom as a second mode, copied verbatim rather than paraphrased, and
`test_the_tripwire_still_breaks_the_idiom_it_replaced` drives it through the same SIGINT
tripwire as the fixed idiom and asserts that it still dies with the exact upstream traceback.

**A committed test that asserts a bug still exists is unusual, and the next person will want
to delete it.** These are the conditions under which it is legitimate, and all four must
hold:

1. **It validates another assertion.** The control exists to keep a specific positive test
   from passing vacuously. Name that test in the docstring. A "known bad" test with nothing
   depending on it is not a control; it is a behaviour lock.
2. **It asserts the failure's *signature*, not merely that it failed.** `returncode != 0` can
   be satisfied by an import error. The `cite_runtime` control also requires
   `Unable to convert call argument` in stderr, so the probe failing for an unrelated reason
   does not satisfy it.
3. **The subject is outside our control** — a third-party defect, a platform behaviour, an
   environment property. **A test asserting that *our own* bug still exists is not a negative
   control. It is a bug with a test.** Ours get fixed.
4. **Going red is a documented result, not a breakage.** The docstring must enumerate the
   ways it can turn green and say what each means, and the ADR carrying the removal condition
   must name the test as the detector. The `cite_runtime` control has exactly two: the
   tripwire stopped placing the signal, or upstream fixed `convert_to_py` — the second being
   [ADR-0034](../adr/0034-process-lifecycle-mechanism-in-cite-runtime.md)'s removal condition
   for Compensation 1 met. Without that, a red control is a puzzle, and a puzzle in CI gets
   deleted.

The pattern's real value is that it turns a "revisit when upstream fixes this" note — which
nobody revisits — into a test that fails on the day the condition is met and says why. Where
a compensation has no such control, **say so in the ADR** rather than leaving the reader to
assume one exists; ADR-0034's Compensation 2 is the worked example of that admission.

## Standing guarantees

The `tester` agent verifies these on **every** run, regardless of what changed:

| Guarantee | Why |
|---|---|
| Sim/hardware interface parity | P2 — the project's central claim. Asserted in simulation only; no hardware path has been run |
| Deterministic bring-up | P4 — no timing assumptions |
| Clean shutdown, no orphans | The next run's failure is this run's fault |
| Cycle completion | The cell actually works — **partly met**: one cycle of the real program on `cell_b`'s plant completes and gates the build. The pair is not driven by any gate. See [L3](L3-capabilities.md) and [L5](L5-twin-synchronization.md) |
| Twin divergence within bound (Phase 2+) | P8 |
| Scenario determinism | Same seed, same outcome — **not met** (see Scenario above and [ADR-0027](../adr/0027-pilz-planning-pipeline.md)). One `move_group` returns a byte-identical trajectory to an identical request; physics is unseeded |

## What tests are not allowed to do

- **Disable a safety check.** A fixture that turns off limits and is reachable on the
  hardware path is a Critical finding ([cross-cutting-safety.md](cross-cutting-safety.md)),
  even if no current configuration reaches it.
- **Assert on mocks instead of behaviour.** A test proving a mock was called proves nothing
  about the system. For behaviour that matters, prefer a real dependency.
- **Depend on execution order.** Each test starts from a known state.
- **Command physical hardware.** Hardware verification requires explicit human
  authorization and is outside the automated suite.
- **Read a grasp off mock hardware.** `GripperActionController` decides "held" from the
  velocity state interface, via `stall_velocity_threshold` — and on
  `mock_components/GenericSystem` that interface is never written, because no controller
  claims the velocity *command*, so the loopback leaves it at its initial value and it reads
  0.0 from the first cycle. A gripper controller stood up over that backend therefore
  satisfies the stall threshold unconditionally and reports a successful grasp on empty air.
  The stall is what `cite_skills::gripper_is_holding` judges, and on the simulated side its
  verdict is what the grasp-hold plugin acts on, so nothing independent would catch it. Under
  Gazebo the velocity is real and the cell is fine. **No test does this
  today, and none may**; the mechanism is in
  [ADR-0040](../adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md)'s
  2026-08-28 correction.

## Running them

```bash
./scripts/test                    # host tooling tests, then ROS tests
./scripts/scenario                # list available scenarios
./scripts/scenario program_cycle  # run one
./scripts/validate-model          # L0 validation — runs anywhere
```

CI runs a fast host-tooling stage first — `./scripts/lint`, `./scripts/test --host-only`
and `./scripts/validate-model`, in about a minute — then the container stage, which builds
the image and runs `./scripts/lint`, `./scripts/build`, `./scripts/test` and the scenarios.

`./scripts/lint` runs in both stages on purpose, and does different work in each. The
host-tooling runner has no ROS, so its ROS-package block **skips and says so**; only the
container stage can run the C++, CMake and package linters. A green `./scripts/lint` on a
laptop means the Python, YAML, shell and documentation checks passed — it says nothing
about the C++.

No scenario step is marked `continue-on-error`. The ROS package lint step blocks: it selects
linters by the `linter` **label** ament sets, not by test name, and `./scripts/lint` refuses to
answer unless the build tree's fingerprint matches the first-party `package.xml` and
`CMakeLists.txt` on disk, so a stale tree produces a diagnosis rather than a confident wrong
linter set.

The teardown question is separate and is **half resolved**. A scenario's cycle can pass and
its post-shutdown check still fail. Split by exit status the failures are **two families**, and within the split
process identity predicts the family exactly: an **exit-1 family** of `rclpy` nodes, whose
cause is established and fixed in
[ADR-0034](../adr/0034-process-lifecycle-mechanism-in-cite-runtime.md); and a **signal
family** that is **still unexplained** — `move_group`, `skill_server` and `parameter_bridge`
have each exited on a signal at teardown, and only `move_group` at -11 is exempted. The
measurement is
[`../measurements/2026-08-27-teardown-signal-family/`](../measurements/2026-08-27-teardown-signal-family/results.md),
whose thresholds were registered before its first trial. **Read its primary result before
citing it — it is an inconclusive**, because the arm that had to reproduce the defect never
did, so nothing there evidences a fix. Its `gdb` captures are the closest thing this project
has to a mechanism for either process, and they characterise rather than explain.

For the unexplained family, the position is unchanged: the exemption route stays closed, the
fix named is a teardown coordinator in `cite_bringup` or a lifecycle-managed bridge, and the
answer is not a wider allowlist and not a longer timeout. Tolerating a cause nobody has
demonstrated is how an assertion stops being able to fail.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Flaky scenario | Re-run until green becomes normal; the suite stops meaning anything | Determinism check; repeated runs in CI |
| Block-structured comparison in this cell | A confident effect that is the run order, not the variable | Interleave; see "Measuring in this cell" above |
| Test asserting on a mock | Passes while the system is broken | `reviewer` |
| QoS mismatch untested | Silent no-op in production (v1's handoff) | Message-delivery assertion |
| Coverage of the happy path only | Cancellation and recovery untested | `reviewer`; scenario review |
| Slow suite | People stop running it locally | `performance-engineer`; CI duration tracking |
| Wall-clock ceiling met on a starved host | A scenario times out with nothing broken | Check the container's CPU allocation before the code; see "Wall-clock ceilings" above |
| Test disabling a safety check | A real limit disabled on a real arm | `safety-auditor` — Critical |
