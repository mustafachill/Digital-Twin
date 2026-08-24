# Testing strategy

- **Status:** `PARTIAL` — the parts that exist are `./scripts/test`, `./scripts/scenario`,
  and the two-stage CI workflow. **No test exists yet**, at any level: `tools/tests/`,
  `tests/scenarios/`, and `workspace/src/` are all empty, so both scripts report SKIP and
  the CI test step builds nothing. Everything below the status line is the design.
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

**Today `cite_tools` contains only `doclinks.py` and has no tests**, and `tools/tests/`
does not exist — so `./scripts/test`, which runs the host suite only when that directory
is present, runs nothing. The first module added under Phase 1.B creates the directory and
the suite.

### Integration

`launch_testing` covers what only appears when nodes interact: lifecycle transitions, QoS
compatibility, parameter loading, namespace correctness, clean shutdown.

**QoS compatibility deserves a dedicated test.** Incompatible QoS connects silently and
delivers nothing — the topic exists, both endpoints appear in `ros2 topic info`, and no
data flows. It is the ecosystem's most-misdiagnosed failure, and it is trivially catchable
by asserting that a message actually arrives.

### Scenario

Full system, headless, in the container, driven by `./scripts/scenario <name>`.

**Scenarios are deterministic.** A fixed physics seed (`CITE_PHYSICS_SEED`) so that a
failure reproduces instead of being a coin flip. A non-deterministic scenario test is worse
than no test: it trains people to re-run until green.

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
| Scenario determinism | Same seed, same outcome |

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

CI runs a fast host-tooling stage first — `./scripts/lint` and `./scripts/validate-model`,
in about a minute — then the container stage, which builds the image and runs
`./scripts/build` and `./scripts/test`. The host stage does not currently run
`./scripts/test`; add it when `tools/tests/` exists.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Flaky scenario | Re-run until green becomes normal; the suite stops meaning anything | Determinism check; repeated runs in CI |
| Test asserting on a mock | Passes while the system is broken | `reviewer` |
| QoS mismatch untested | Silent no-op in production (v1's handoff) | Message-delivery assertion |
| Coverage of the happy path only | Cancellation and recovery untested | `reviewer`; scenario review |
| Slow suite | People stop running it locally | `performance-engineer`; CI duration tracking |
| Test disabling a safety check | A real limit disabled on a real arm | `safety-auditor` — Critical |
