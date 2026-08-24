# ADR-0019: C++ for control paths, Python for orchestration and tooling

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** [ADR-0007](0007-behaviour-trees-for-orchestration.md), [ADR-0013](0013-host-agnostic-tooling.md)

## Context

ROS 2 supports C++ and Python as first-class client languages. Choosing per component, ad
hoc, produces a codebase where the language of any given file is an accident of who wrote
it — and a convention others must follow is exactly what an ADR is for.

The two differ where it matters here: C++ has predictable latency and no garbage-collection
pauses; Python is faster to write, faster to change, and pleasant for data processing.

## Options considered

### Option A — Python everywhere
Fastest to develop, one language. Rejected: garbage-collection pauses and interpreter
overhead are unacceptable in a control loop that must hold its period, and the failure mode
is intermittent jitter — the hardest kind to diagnose.

### Option B — C++ everywhere
Uniform performance, one language. Rejected: it makes generators, validators, and tooling
far more expensive to write and change, and it would put the L0 tooling layer behind a
compiler for no benefit ([ADR-0013](0013-host-agnostic-tooling.md)).

### Option C — Split by latency requirement
Chosen.

## Decision

| Language | Used for |
|---|---|
| **C++** | Anything with a latency requirement: hardware interfaces, controllers, real-time paths, Gazebo system plugins, behaviour tree nodes |
| **Python** | Orchestration glue, generators, validators, the L0 tooling layer, launch files, test harnesses |

The rule: **if a missed deadline is a correctness problem rather than a slow response, it
is C++.**

Behaviour trees are C++ because BehaviorTree.CPP is
([ADR-0007](0007-behaviour-trees-for-orchestration.md)), and because a tick that stalls
stalls the line.

## Consequences

### What this gets us
- Predictable timing where timing is correctness, and fast iteration where it is not.
- The L0 tooling layer stays pure Python and therefore runs on any machine
  ([ADR-0013](0013-host-agnostic-tooling.md)) — which is what lets a macOS contributor
  validate a model at all.
- A clear rule, so nobody has to negotiate the choice per file.

### What this costs us
- Contributors need both languages, or the team partitions by language — which partitions
  by layer, and that is a real organisational risk worth watching.
- Two toolchains: `clang-format` and `ruff`, `gtest` and `pytest`, two sets of lint rules.
  `./scripts/lint` and `./scripts/test` hide this, but it is there.
- Interfaces crossing the boundary must be typed and language-neutral
  ([ADR-0010](0010-typed-ros-interfaces.md)) — which is required anyway, but this makes it
  load-bearing rather than merely good practice.
- The boundary will occasionally be argued. "Is this on the critical path?" is not always
  obvious, and the honest answer is sometimes "measure it"
  (`performance-engineer`).

### What we will have to revisit
If a Python component turns out to be on a critical path, port it rather than tuning it —
the rule exists so that this is a straightforward decision instead of a debate.
