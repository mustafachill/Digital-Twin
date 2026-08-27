# Testing strategy

- **Status:** `PARTIAL` — `./scripts/test`, `./scripts/scenario` and the two-stage CI
  workflow exist and run real tests. The unit level is populated: `tools/tests/` holds **215**
  host tests at this commit, counted by collection, plus shell self-tests for the gate logic
  in `scripts/_lib.sh`. The contract level is populated: 22 interface definitions are frozen
  against a stored baseline.
  The scenario level has three: `bringup`, a blocking CI gate run twice per run;
  `pick_and_place`, **promoted to a blocking gate at `c1e9e03`**; and `continuous_line`,
  which drives the whole three-arm line and is the **one** container-stage step still marked
  `continue-on-error`. A scenario that cannot fail the build cannot hold a claim up, so
  `continuous_line` is evidence and not a gate.
  All three are run with `--teardown-advisory`, which splits the two questions a scenario
  answers in one exit code: **the cycle gates, the post-shutdown teardown is reported and
  does not gate.** It exempts no process and deletes no assertion — see the phase-split block
  in `scripts/_lib.sh`.
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
`cite_bringup/launch/simulation.launch.py` now passes it as `gz sim --seed`. **That is less
than it sounds and must not be read as more.** `gz sim --seed N` reaches
`ServerConfig::SetSeed()`, whose body is `math::Rand::Seed(_seed)` — so it seeds
`gz::math::Rand`, which is what sensor noise and the comms systems draw from. It does not
seed the physics solver: no library under `gz_physics_vendor` or `gz_dartsim_vendor`
references `gz::math::Rand` at all. And it has nothing to do with OMPL, which under
[ADR-0006](../adr/0006-moveit2-motion-planning.md) is the stochastic component that decides
whether a plan succeeds. Measured before the seed was plumbed: `pick_and_place` run four
times under an identical seed produced **two distinct failure modes**, each twice, both
under domain isolation.

**OMPL cannot be seeded from here, and a seed would not be enough if it could.** MoveIt
never calls `ompl::RNG::setSeed` and exposes no parameter for it; MoveIt is apt-installed
rather than pinned as source, so there is no patch hook; and OMPL draws each instance's seed
from a process-global generator whose hand-out order across threads is not fixed, while
MoveIt's default termination is wall-clock. The full evidence, and the decision taken
because of it, are in [ADR-0027](../adr/0027-pilz-planning-pipeline.md): station-to-station
motion moves to a non-sampling planner. **That decision does not by itself make a scenario
reproducible**, and nothing here may be upgraded on the strength of it — under P8 the claim
is earned by running scenarios repeatedly and measuring, or it is not made.

Until then a passing scenario is evidence about that run only. The design intent stands and
is what the seed exists for: a fixed seed so that a failure reproduces instead of being a
coin flip, because a non-deterministic scenario test is worse than no test — it trains
people to re-run until green.

### Measuring in this cell: interleave, never block

This follows from the paragraphs above rather than softening them — the cell is still not
reproducible, and nothing here should be read as saying otherwise. It is about how to
compare two configurations *given* that it is not.

**Some of what this cell does is bimodal, not continuous.** The grasp twist is the worked
example: a trial lands in a high state or a low one, and the physics timestep changes how
often the high state is entered rather than moving a magnitude. The two **grasp** campaigns
in [`../measurements/`](../measurements/README.md) turn on this, and the second one had to
withdraw a published "×24.5 median scaling" from the first because of it.

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

A scenario asserts on **outcomes and constraints**, never on exact trajectories. Sampling
-based planners are stochastic ([ADR-0006](../adr/0006-moveit2-motion-planning.md)); a test
asserting an exact joint sequence will be flaky and will be deleted by whoever is on call.

Good: *the work-piece reaches station 2 within 30 seconds, the arm never exceeds its
workspace bounds, no collision is reported.*

### Contract

Interface definitions are checked against a stored baseline. A breaking change to a
`.msg`, `.srv`, or `.action` fails the build rather than surfacing at runtime in a consumer
nobody thought about.

## Standing guarantees

The `tester` agent verifies these on **every** run, regardless of what changed:

| Guarantee | Why |
|---|---|
| Sim/hardware interface parity | P2 — the project's central claim. Asserted in simulation only; no hardware path has been run |
| Deterministic bring-up | P4 — no timing assumptions |
| Clean shutdown, no orphans | The next run's failure is this run's fault |
| Cycle completion | The line actually works — **partly met**: one arm's pick-and-place cycle completes and the three-arm line has now been reported completing its milestone ladder, but neither scenario is a merge gate, both are reported from runs rather than from a campaign, and the line has not carried every piece in every run. See [L3](L3-capabilities.md), [L4](L4-orchestration.md) and the status block in [CLAUDE.md §2](../../CLAUDE.md) |
| Twin divergence within bound (Phase 2+) | P8 |
| Scenario determinism | Same seed, same outcome — **not met today**, see Scenario above and [ADR-0027](../adr/0027-pilz-planning-pipeline.md) |

## What tests are not allowed to do

- **Disable a safety check.** A fixture that turns off limits and is reachable on the
  hardware path is a Critical finding ([cross-cutting-safety.md](cross-cutting-safety.md)),
  even if no current configuration reaches it.
- **Assert on mocks instead of behaviour.** A test proving a mock was called proves nothing
  about the system. For behaviour that matters, prefer a real dependency.
- **Depend on execution order.** Each test starts from a known state.
- **Command physical hardware.** Hardware verification requires explicit human
  authorization and is outside the automated suite.

## Running them

```bash
./scripts/test                    # host tooling tests, then ROS tests
./scripts/scenario                # list available scenarios
./scripts/scenario pick_and_place # run one
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

**One** container-stage step is marked `continue-on-error`: `continuous_line`. It runs so
that the failure is visible; it is not allowed to report success. Its promotion condition is
recorded next to it in `.github/workflows/ci.yml`.

The other two that used to be here were promoted at `c1e9e03`, against their own recorded
conditions rather than by decree:

- **The ROS package lint step blocks.** The reason it did not was that the gate selected
  linters by test *name* and ran 3 of 8 per package. It selects by the `linter` **label**
  now, which is what ament actually sets — 41 linter tests across the seven first-party
  packages. `./scripts/lint` additionally refuses to answer at all unless the build tree's
  fingerprint matches the first-party `package.xml` and `CMakeLists.txt` on disk, so a stale
  tree produces a diagnosis rather than a confident wrong linter set.
- **`pick_and_place` blocks.** Its remaining condition had narrowed to reproducibility, and
  its **seeding** condition was deliberately not carried forward: ADR-0027 establishes that
  OMPL cannot be seeded through MoveIt, and a gate held behind an unmeetable condition never
  gates. What replaced it is the pass count plus the phase split — not a determinism claim.
  Read `ci.yml`'s block above that step for what would **retract** the promotion.

`continuous_line`'s promotion condition was re-decided at the same commit and is now **one
rather than four**: it passes repeatably in an isolated, freshly built tree, measured against
thresholds written down before the runs. Three of its four original conditions were closed by
ADR-0032, ADR-0033 and the milestone ladder going from 4 of 10 to 10 of 10. Not a tolerance
change, and not a teardown allowance — the teardown half is already reported rather than
gated.

The teardown question is separate from all of this and is unresolved. `pick_and_place`'s
teardown check has failed after a passing cycle on several occasions, on four distinct
processes so far, so process identity does not predict it; the exemption route is closed on
evidence, and the fix named is a teardown coordinator in `cite_bringup` or a
lifecycle-managed bridge — not a wider allowlist and not a longer timeout.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Flaky scenario | Re-run until green becomes normal; the suite stops meaning anything | Determinism check; repeated runs in CI |
| Block-structured comparison in this cell | A confident effect that is the run order, not the variable | Interleave; see "Measuring in this cell" above |
| Test asserting on a mock | Passes while the system is broken | `reviewer` |
| QoS mismatch untested | Silent no-op in production (v1's handoff) | Message-delivery assertion |
| Coverage of the happy path only | Cancellation and recovery untested | `reviewer`; scenario review |
| Slow suite | People stop running it locally | `performance-engineer`; CI duration tracking |
| Test disabling a safety check | A real limit disabled on a real arm | `safety-auditor` — Critical |
