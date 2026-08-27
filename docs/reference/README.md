# Reference

External sources: standards, literature, and authoritative documentation — plus one
internal source, [v1-lessons.md](v1-lessons.md), which is here because it outlives the tree
it cites and is consulted the same way.

| Document | Holds |
|---|---|
| [standards.md](standards.md) | ISO 23247, Asset Administration Shell, robot safety standards |
| [literature.md](literature.md) | Academic sources the architecture draws on |
| [toolchain.md](toolchain.md) | Version-specific documentation for every tool in the stack |
| [v1-lessons.md](v1-lessons.md) | What the superseded `legacy/` tree taught, captured before it is deleted |

## How to use this section

Every entry says **why it matters to this project**, not just what it is. A bare citation
is a dead end; a sentence of context tells the next reader whether to open it.

This replaces the v1 `urls.txt` — a flat list of links with no annotation, which nobody
used because nobody could tell which link answered which question.

## Adding an entry

- **Version-specific links.** ROS and Gazebo documentation is per-distribution, and a
  generic link silently shows the reader the wrong release. Always link the Jazzy or
  Harmonic page.
- **One sentence on relevance.** What question does this source answer for us?
- **Note if it is paywalled.** Contributors should not discover that after clicking.
- **Note if it is stale but still useful.** The `xarm_ros2` README is a live example — but
  note *which branch*: the `humble` README links to Gazebo Classic install instructions,
  while the `jazzy` README links to Harmonic and states that Classic is no longer
  supported. Naming the wrong branch is how this page previously carried a wrong claim for
  a week. See [toolchain.md](toolchain.md).
