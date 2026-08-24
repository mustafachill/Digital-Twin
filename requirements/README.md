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
