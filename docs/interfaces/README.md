# Interfaces

- **Status:** `BUILT` — `cite_interfaces` exists and holds **22 definitions** (14 `.msg`,
  2 `.srv`, 6 `.action`), every one frozen against a stored baseline at
  `workspace/src/cite_interfaces/test/interfaces.baseline`, so a breaking change fails the
  build rather than surfacing at runtime. The conventions below are what that package does,
  not what it intends to do.
  All six actions now have a server. `Detect` and `Transfer` have servers that no launch
  graph starts and no shipped tree calls, which is an
  [L3](../architecture/L3-capabilities.md) and [L4](../architecture/L4-orchestration.md)
  gap, not an interface gap — see those documents for what has and has not been run.
- **Related:** [ADR-0010](../adr/0010-typed-ros-interfaces.md), [`../architecture/naming-and-namespaces.md`](../architecture/naming-and-namespaces.md)

Every boundary between components in this system is a **typed ROS 2 interface**. If a
consumer cannot discover the shape with `ros2 interface show`, the interface does not
exist.

[ADR-0010](../adr/0010-typed-ros-interfaces.md) records why, from the v1 experience of
publishing an entire robot status as a stringified Python dict.

## Where they live

Interface definitions live in dedicated packages that depend on nothing else in this
project and sit at the bottom of the dependency graph:

```
workspace/src/cite_interfaces/
├── msg/       state and events — things that are published
├── srv/       request/response — fast, bounded, returns immediately
└── action/    long-running, cancellable, reports progress
```

## Choosing message, service, or action

| Use | When | Examples |
|---|---|---|
| **Message** | Continuously published state or events | joint state, line state, divergence metrics |
| **Service** | A request with a fast, bounded answer | query mode, fetch model version |
| **Action** | Long-running, cancellable, reports progress | every L3 skill, mode transition |

The most common mistake is a service where an action belongs. **If it can take more than a
few hundred milliseconds, or should be cancellable, it is an action.** A service call that
blocks for ten seconds blocks its executor, and the symptom is a hang with no error at all
— see [`../operations/troubleshooting.md`](../operations/troubleshooting.md).

## Naming

`UpperCamelCase` for types, `lower_snake_case` for fields.

```
RobotState.msg        not  robot_state.msg / robotStateMsg
mode_transition_time  not  modeTransitionTime
```

Names say what the thing **is**, not what it is for. `RobotState`, not `RobotStateForHmi` —
the moment a second consumer appears, that name is a lie.

## Every message carries identity and time

```
std_msgs/Header header      # stamp + frame_id
string asset_id             # the L0 asset this concerns
```

A measurement without a timestamp cannot be correlated. A measurement without an asset
identity cannot be attributed. Both are required for L6 recording to be interpretable
later ([L6](../architecture/L6-data-and-telemetry.md)).

This binds messages that are **published**. A message that only ever appears nested inside
another — `StationState`, `StationTopology`, `StationEdge`, `Detection` — carries neither,
because it inherits both from its container, and stamping it twice would be the same fact in
two places. `LineTopology` carries a `header` and a `zone` rather than an `asset_id`: a
topology is not about one asset.

## Enumerations are constants, not strings

```
uint8 MODE_SIM=0
uint8 MODE_REAL=1
uint8 MODE_SHADOW=2
uint8 MODE_VALIDATED=3
uint8 MODE_CLOSED_LOOP=4
uint8 mode
```

Not `string mode`. A typo in a string comparison is a runtime bug that a constant makes
impossible, and the valid set is discoverable rather than folklore.

## Failure is structured

`ResultCode.msg`, as shipped:

```
uint8 SUCCESS=0
uint8 PLANNING_FAILED=1
uint8 EXECUTION_FAILED=2
uint8 CANCELLED=3
uint8 SAFETY_BLOCKED=4
uint8 PRECONDITION_FAILED=5
uint8 TIMEOUT=6
uint8 HARDWARE_FAULT=7
uint8 NOT_IMPLEMENTED=8
uint8 UNREACHABLE=9
uint8 code
string detail                 # human-readable context, never the machine-readable part
```

`code` drives recovery; `detail` explains it to a person. L4 chooses a recovery
strategy from the code — which is impossible if failure is a free-text string, and is why
v1's orchestration could only ever retry generically.

## Compatibility and versioning

Interface packages are reviewed **before** the code that uses them. Changing one after it
has consumers is expensive, so the review is where the cost is paid.

| Change | Compatible | How to do it |
|---|---|---|
| Add a field with a sensible default | Yes | Just add it |
| Add a constant | Yes | Just add it |
| Rename a field | **No** | New field, deprecate old, remove after consumers migrate |
| Change a type | **No** | New field with a new name |
| Remove a field | **No** | Deprecate first, remove in a later release |

Contract tests compare against a stored baseline, so a breaking change fails the build
rather than surfacing at runtime in a consumer nobody remembered
([cross-cutting-testing.md](../architecture/cross-cutting-testing.md)).

## Genuinely dynamic data

Occasionally data is legitimately open-ended — arbitrary diagnostic key-values. The answer
is a typed key-value array in the style of `diagnostic_msgs`, **not** a JSON blob in a
string. The container stays typed even when the contents vary.

## Documenting an interface

Every `.msg`, `.srv`, and `.action` carries comments explaining what each field means, its
units, and its valid range. Units are not optional: `float64 velocity` is ambiguous,
`float64 velocity  # rad/s` is not. A large share of robotics defects are unit errors.
