# ADR-0013: Keep a host-agnostic tooling layer

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0004, ADR-0009, `requirements/README.md`

## Context

The L0 facility model has no runtime behaviour (charter §5): it is data, a validator, and
generators. Nothing about validating a schema, checking an inertia tensor, or emitting a
URDF requires a ROS installation.

Meanwhile contributors author on macOS, where ROS 2 cannot be installed at all. If every
tool requires ROS, then every trivial check requires starting a container, and a
contributor on macOS cannot validate a model change without a five-minute round trip.

There is also a dependency hazard. ROS 2 Python packages come from apt. Installing a
library with `pip` alongside them produces two copies at different versions, and the
failure appears later as an import error in a node nobody touched.

## Options considered

### Option A — Everything is a ROS package
Uniform, and everything is available in one environment. Rejected: it makes the model
layer inaccessible from macOS for no technical reason, and couples pure data processing to
a robotics middleware.

### Option B — A separate host-agnostic Python package
`tools/` (`cite_tools`), importing no `rclpy`, installed into its own virtualenv. Chosen.

## Decision

**`tools/cite_tools` is a plain Python package with no ROS dependency.** It implements
schema validation, artifact generation, geometry and inertia checks, and the asset
pipeline. It runs on Linux, macOS, and in CI.

Dependencies are declared in four layers, each with exactly one correct home
(`requirements/README.md`):

| Layer | Declared in | Resolved by |
|---|---|---|
| ROS + system packages | `package.xml`, Dockerfile | `rosdep` → apt |
| External ROS source | `external/cite.repos` | `vcstool` |
| Host tooling | `requirements/tools.txt` | `pip` → venv |
| Dev tooling | `requirements/dev.txt` | `pip` → venv |

**A ROS Python dependency is never installed with `pip`.**

## Consequences

### What this gets us
- `./scripts/validate-model` and `./scripts/lint` run on any machine, in seconds.
- CI gets a fast first stage that catches most mistakes before the expensive container job
  starts.
- The generator layer is unit-testable without a ROS runtime, so its tests are fast and
  deterministic.
- The pip/apt collision cannot happen, because the two never share an environment.

### What this costs us
- Two dependency systems and two environments to understand. `requirements/README.md`
  exists because this genuinely confuses people.
- The host Python version must be constrained. Pinned wheels do not exist for every
  release: bootstrap selects Python 3.12 to match the container and fails with an
  actionable message outside 3.10–3.13. This was discovered the hard way, on a machine
  where `python3` was 3.14 and `scipy` tried to build from source.
- `cite_tools` cannot use ROS types. Where the model layer must express something ROS also
  models — a pose, a transform — it defines its own representation and converts at the
  boundary.
- `pip install cite-tools` alone installs no dependencies, because declaring them in
  `pyproject.toml` would duplicate `requirements/tools.txt` and violate P1. Bootstrap is
  the only supported installation path, and that constraint is documented in the file
  itself.

### What we will have to revisit
If the tooling layer starts needing ROS types heavily, reconsider whether part of it
belongs in a ROS package. Keep the schema validator host-agnostic regardless — that is the
piece whose portability matters most.
