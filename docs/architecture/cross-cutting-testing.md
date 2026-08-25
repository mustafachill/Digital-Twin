# Testing strategy

- **Status:** `PARTIAL` — `./scripts/test`, `./scripts/scenario` and the two-stage CI
  workflow exist and run real tests. The unit level is populated: `tools/tests/` holds 94
  host tests, plus shell self-tests for the gate logic in `scripts/_lib.sh`. The scenario
  level has `bringup` and `pick_and_place`. Three gaps below are still open and are called
  out where they occur: **scenario determinism is documented but not implemented**, ROS
  package linters register nothing, and `pick_and_place` does not pass. Everything else
  below the status line is design, not description.
- **Related:** charter §9, [`../onboarding/development-workflow.md`](../onboarding/development-workflow.md)

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

`tools/tests/` exists and holds **94 tests** covering the schema loader, the generators,
identifiers, units, and the geometric and referential validators. `./scripts/test` runs
them, and `./scripts/test --host-only` runs them without Docker.

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

`./scripts/scenario` exports `CITE_PHYSICS_SEED`, and both scenarios read it into an
attribute they never use again. It reaches nothing else — not Gazebo, not the generated
world SDF, and not OMPL, which under [ADR-0006](../adr/0006-moveit2-motion-planning.md) is
the stochastic component that decides whether a plan succeeds. Measured: `pick_and_place`
run four times under an identical seed produced **two distinct failure modes**, each twice,
both under domain isolation.

The design intent stands and is what the seed exists for — a fixed seed so that a failure
reproduces instead of being a coin flip, because a non-deterministic scenario test is worse
than no test: it trains people to re-run until green. Closing it needs a consumer at each
end: a seed in the generated world SDF, and an OMPL seed in the generated MoveIt
configuration. Until both exist, a passing scenario is evidence about that run only, and
[ADR-0023](../adr/0023-simulated-grasping-via-attachment.md) rests part of its argument on a premise
the code does not yet provide.

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
| Sim/hardware interface parity | P2 — the project's central claim |
| Deterministic bring-up | P4 — no timing assumptions |
| Clean shutdown, no orphans | The next run's failure is this run's fault |
| Cycle completion | The line actually works |
| Twin divergence within bound (Phase 2+) | P8 |
| Scenario determinism | Same seed, same outcome — **not met today**, see Scenario above |

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

Two container-stage steps are marked `continue-on-error` and are **not** merge gates yet:
the ROS package lint step, because no first-party package declares a linter set for
`ament_lint_auto` to find, and `pick_and_place`, because it does not pass. Both run so the
failure is visible; neither is allowed to report success. The conditions for promoting each
to blocking are recorded next to it in `.github/workflows/ci.yml`.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Flaky scenario | Re-run until green becomes normal; the suite stops meaning anything | Determinism check; repeated runs in CI |
| Test asserting on a mock | Passes while the system is broken | `reviewer` |
| QoS mismatch untested | Silent no-op in production (v1's handoff) | Message-delivery assertion |
| Coverage of the happy path only | Cancellation and recovery untested | `reviewer`; scenario review |
| Slow suite | People stop running it locally | `performance-engineer`; CI duration tracking |
| Test disabling a safety check | A real limit disabled on a real arm | `safety-auditor` — Critical |
