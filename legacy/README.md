# legacy/ — superseded first iteration

**This tree is reference material. It is not maintained, not built, and not extended.**

This is the original Digital-Twin workspace: ROS 2 Humble, Gazebo Classic, a bundled copy
of `xarm_ros2`, and three mutually incompatible attempts at a multi-robot architecture. It
reached a working single-robot simulation and taught the project a great deal about xArm
integration, `ros2_control`, and conveyor plugins. It is preserved here so that knowledge
remains reachable while the rebuild proceeds.

## Do not

- Build it. It targets Gazebo Classic, which reached end of life in January 2025.
  `./scripts/build` deliberately excludes this directory.
- Extend it, fix its bugs, or copy its patterns. See `what-we-are-doing.md` §12 for the
  specific reasons it is being replaced rather than migrated.
- Treat it as precedent in review. A pattern appearing here is not an argument for
  repeating it.

## Known broken state

`legacy/gazebo_ros2_control` was a git submodule reference (mode 160000) with no matching
`.gitmodules` entry. It resolved to an empty directory on a fresh clone, and the local
patch it once carried — the fix that allowed controllers to load at all — exists nowhere
in version control. This tree therefore cannot be built from a clean checkout by anyone.
That failure is the origin of the dependency rules now enforced in `CLAUDE.md` §4.

**The gitlink was removed from the index on 2026-08-24.** It pointed at nothing this
repository held (`git cat-file` could not resolve it) and its only effect was to fail the
supply-chain check in CI on every run. Before deleting it, its details are recorded here,
because this line was the last trace of what v1 actually built against:

| | |
|---|---|
| Path | `src/gazebo_ros2_control` (later `legacy/gazebo_ros2_control`) |
| Mode | `160000` (gitlink) |
| Commit | `42d875b482f0b254d9032950a91b2c5cbd7d1c3d` |
| Upstream | `github.com/ros-controls/gazebo_ros2_control`, `humble` branch |
| `.gitmodules` entry | none — this is why a clone produced an empty directory |

The commit is not retrievable from this repository. If the v1 patch is ever needed, start
from that upstream commit and re-derive it; `legacy/docs/WORK_LOG.md` (2025-11-25) describes
what the patch did — it set `robot_description` as a node parameter after controller manager
creation rather than passing it as a command-line argument.

## Lifetime

Scheduled for deletion at the end of Phase 1, once the rebuild covers everything worth
carrying forward. The git history remains regardless.
