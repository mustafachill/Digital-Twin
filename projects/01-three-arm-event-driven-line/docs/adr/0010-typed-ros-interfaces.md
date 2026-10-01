# ADR-0010: Require typed ROS interfaces

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** charter §4 (P3), `docs/interfaces/README.md`

## Context

The v1 workspace published robot status like this:

```python
msg = String()
msg.data = str(status_dict)      # a Python dict, stringified
self.status_pub.publish(msg)
```

The consequences were not theoretical:

- `ros2 topic echo` showed a Python dict repr. Nothing could tell you the shape without
  reading the publisher's source.
- No C++ node could consume it without writing a Python-literal parser.
- Adding or renaming a field broke every consumer silently, at runtime, with no error.
- No web client could use it, which quietly foreclosed the dashboard the project wanted.
- The project's own design documents claimed `RobotStatus.msg`, `HandoffRequest.msg`, and
  four other interface files existed. **None of them were ever created.** The stringified
  dict was the actual interface, and the documentation described one that did not exist.

## Options considered

### Option A — Convention plus documentation
Keep `String` payloads but standardise on JSON and document the schema. Rejected: the
schema is then enforced nowhere, drifts from the code immediately, and every consumer
still parses by hand. It is the same failure with better manners.

### Option B — Typed ROS interfaces
Define every interface as `.msg`, `.srv`, or `.action` in an interface package. Chosen.

## Decision

**Every interface between components is a versioned ROS 2 interface definition** in a
dedicated interface package. If a consumer cannot discover the shape with
`ros2 interface show`, the interface does not exist.

Structured data in a `std_msgs/String` is a standing prohibition (`CLAUDE.md` §4) —
rejected in review without discussion.

Interface packages sit at the bottom of the dependency graph and depend on nothing in this
project. They are reviewed **before** the code that uses them.

## Consequences

### What this gets us
- Interfaces are discoverable at runtime: `ros2 interface show`, `ros2 topic info`, and
  every ROS tool work as intended.
- Type checking at compile time in C++ and at message construction in Python. A renamed
  field is a build failure, not a silent runtime break.
- Language-neutral. C++, Python, and — via a bridge — a browser all consume the same
  definition, which is what keeps the Phase 4 HMI possible without redesign.
- Recorded bags are self-describing and replayable years later.

### What this costs us
- Changing an interface means a rebuild, and a breaking change means coordinating
  consumers. This friction is the point, but it is friction, and it is felt most during
  early exploration when interfaces are still moving.
- More packages and more build dependencies.
- Genuinely dynamic data — arbitrary key-value diagnostics — needs deliberate modelling
  (`diagnostic_msgs`-style key/value arrays) rather than a convenient JSON blob.

### What we will have to revisit
Nothing about the rule. If a case appears where a typed interface is genuinely
impossible, it is an `ESCALATE` and gets its own ADR — not a quiet exception.
