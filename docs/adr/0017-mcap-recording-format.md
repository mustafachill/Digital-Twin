# ADR-0017: Record with rosbag2 and MCAP storage

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** [ADR-0010](0010-typed-ros-interfaces.md), [`../architecture/L6-data-and-telemetry.md`](../architecture/L6-data-and-telemetry.md)

## Context

Recording serves three purposes here: evidence for a test finding, diagnosis of a specific
run, and replay into the simulator. All three need the recording to be readable later — by
a different tool, by a different person, possibly years after the code that produced it
changed.

`rosbag2` offers a choice of storage plugin. The default on most distributions is SQLite3;
MCAP is the alternative.

## Options considered

### Option A — SQLite3 (the default)
Works out of the box, queryable with ordinary SQL tooling. Rejected: larger files, slower
writes at high message rates, and — decisively — it is a ROS-specific container that
external tooling does not read.

### Option B — MCAP
A self-describing container format designed for robotics logs. Chosen.

### Option C — Custom logging
Rejected without much consideration. It discards `ros2 bag play`, every existing analysis
tool, and the replay path L6 depends on, in exchange for nothing.

## Decision

Record with **`rosbag2` using the MCAP storage plugin**. Bags embed their message
definitions, so a recording remains interpretable without the source tree that produced it.

## Consequences

### What this gets us
- **Self-describing.** Combined with typed interfaces
  ([ADR-0010](0010-typed-ros-interfaces.md)), a bag recorded today is readable in five
  years without the original packages. A bag full of stringified dicts would not have been.
- Foxglove reads MCAP directly, which is how a headless contributor or a review agent
  inspects a run — and is the interim L7.
- Lower write overhead at high rates, so recording perturbs the system less. That matters:
  a recording that changes cycle time is a recording of a different system.
- Readable outside ROS entirely, which keeps analysis options open.

### What this costs us
- An extra storage plugin (`ros-jazzy-rosbag2-storage-mcap`) rather than the default.
- `-s mcap` must be passed, or specified in configuration. Forgetting it silently produces
  a SQLite bag — which still works, but breaks the "readable everywhere" property nobody
  will check until they need it.
- Less convenient for casual SQL-style inspection than SQLite.

### What we will have to revisit
If `rosbag2`'s default changes to MCAP, this ADR becomes a statement of alignment rather
than a deviation. Nothing else about it changes.
