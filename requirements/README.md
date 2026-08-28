# Dependency layers

This project has four kinds of dependency, and each has exactly one correct
place to be declared. Putting one in the wrong layer is how a project becomes
unreproducible.

| Layer | What | Declared in | Resolved by |
|---|---|---|---|
| **1. System + ROS packages** | Gazebo, MoveIt, `ros2_control`, anything a ROS package needs at build or run time | each package's `package.xml`, plus stack-level packages in `infra/docker/Dockerfile` | `rosdep` → `apt` |
| **2. External ROS source** | `xarm_ros2` and any other repository built from source | `external/cite.repos` (pinned to commit SHAs) | `vcstool` |
| **3. Host tooling (Python)** | Model schema validation, generators, mesh pipeline — the L0 layer, which has no ROS runtime and must run on macOS too | `requirements/tools.txt` | `pip` into `/opt/cite-venv` |
| **4. Development tooling** | Linters, formatters, test plugins, pre-commit | `requirements/dev.txt` | `pip` into the same venv |

## Why not one `requirements.txt`

A ROS 2 Python node's dependencies belong in `package.xml`, not in a pip file.
Installing them with `pip` alongside the apt-provided ROS Python packages
produces two copies of the same library at different versions, and the failure
surfaces later as an import error inside a node that never changed. Layer 1 is
therefore `rosdep`'s job, always.

Layers 3 and 4 are genuinely separate: they are ordinary Python programs that
happen to live in a robotics repository. They import no `rclpy`, run on any
operating system, and are what makes it possible to validate the facility model
from a laptop that could never build the ROS stack.

## A tool that is not written in Python

Layer 4 is defined by **role**, not by implementation language: it is the tools a
gate runs. `shellcheck` is a linter, so it belongs there, and it is declared in
`dev.txt` as `shellcheck-py` — a distribution that carries the upstream binary
with a per-platform sha256 rather than any Python code. That keeps it beside
`ruff`, `mypy` and `yamllint`, installed by the same `pip` step into the same
virtualenv, and reachable at `${venv}/bin/shellcheck`.

The alternative was apt in the Dockerfile, and it is wrong here for a reason the
first CI run in this repository made concrete. The host job runs on the runner
with no container at all, so an apt pin would have reached one of the three
machines this gate runs on and left the other two answering out of `PATH` — which
is exactly what happened: 0.11.0 on the developer's host, whatever `ubuntu-24.04`
ships on the runner, and nothing at all in the container, where the shell step
reported success having read no script. A tool that only some of the machines get
is not pinned.

The rule that follows: **if a gate runs it, its version is a dependency, and it is
declared in the layer that reaches every machine that runs the gate.** Layer 1 is
right for what the ROS build needs, because only the container builds. Layer 4 is
right for what `./scripts/lint` and `./scripts/test` need, because everything runs
those.

## Vulnerability scanning

```bash
./scripts/audit-deps            # Python tooling layer
./scripts/audit-deps --image    # also the container image's OS packages (slow)
```

The pins in `tools.txt` and `dev.txt` are chosen to be free of known vulnerabilities, and
a few carry a comment recording the advisory that forced the version. Two entries —
`filelock` and `pygments` — are **transitive dependencies pinned deliberately**: their
parents' declared floors are old enough that a resolver reports a vulnerable version even
though pip installs a current one. Pinning what we actually use makes the declaration true,
which is better than suppressing a warning about a version we never install.

## Pinning

`tools.txt` and `dev.txt` pin exact versions. When you change one, change it
deliberately and say why in the commit message — an unpinned tooling dependency
means CI and a developer's machine can disagree about whether the model is valid.
