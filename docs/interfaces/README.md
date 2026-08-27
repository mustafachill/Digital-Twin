# Interfaces

- **Status:** `BUILT` — `cite_interfaces` exists and holds **23 definitions** (14 `.msg`,
  3 `.srv`, 6 `.action`), every one frozen against a stored baseline at
  `workspace/src/cite_interfaces/test/interfaces.baseline`, so a breaking change fails the
  build rather than surfacing at runtime. The conventions below are what that package does,
  not what it intends to do.
  All six actions now have a server, and five of them are called by a shipped tree.
  `Transfer` has a server that nothing calls, which is an
  [L3](../architecture/L3-capabilities.md) and [L4](../architecture/L4-orchestration.md)
  gap, not an interface gap — see those documents for what has and has not been run.
  **`ConveyorState` is published by nothing.** It exists so that a belt's commanded and
  measured speed can disagree visibly; no belt fills it, and the only file in the workspace
  that mentions the type is `cite_orchestration/conveyor_index.hpp`, in a comment saying so.
  L4 commands belts over a bare `std_msgs/Float64` and gets no confirmation back.
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

## A field a sensor cannot fill says so

A message declares the shape of an answer; it does not promise that every sensor can give
one. `Detection` carries a `geometry_msgs/PoseStamped pose`, and the only pose sensor in
`cell_a` is a through-beam, which reports **occupancy**. It knows something crossed it, not
where along the beam and not how it is turned.

`PoseStamped` has no absent state, so absence has to be spelled out. The convention is
written once, in `cite_skills/include/cite_skills/observation.hpp`, as a writer
(`mark_pose_unobserved`) and the matching reader (`pose_is_observed`) side by side:

- **`header.frame_id` empty** — the semantic marker, and the field to test. `tf2` refuses an
  empty frame rather than resolving it, and `cite_orchestration`'s `PickAt` already reads it
  as "no observation, fall back to the station frame".
- **`header.stamp` zero** — stamping it would date an observation nobody made.
- **every position and orientation component `NaN`** — the guard against a consumer that
  ignores the frame and reads the numbers. NaN fails loudly in TF and in IK; zeroes and an
  identity rotation are a perfectly real pose in whatever frame is later attached, and
  identity in particular asserts "square to the frame", which is the assumption
  [ADR-0029](../adr/0029-simulated-grasping-by-friction.md) records as unsafe after a grasp.

**This is not "the pose is uncertain".** A beam constrains the axes across it and leaves the
third unconstrained along its whole length, and `Detection` has no covariance and no field
separating a measured axis from an inferred one. Reporting a constrained pose without the
shape of its uncertainty puts a number that *looks* measured back into the field, which is
the defect the convention replaces — see the correction in
[ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md), where a
decision was justified by a pose that was only ever the sensor's own mounting transform.

A consumer that needs the uncertainty needs new fields in `cite_interfaces`, not a
convention improvised at the call site.

**That gap is closed as of 2026-08-27, and how it closed is worth more than the fact.**
`pose_is_observed` is the test a consumer should make, and for a while no consumer could
call it: `cite_skills` declared no `ament_export_*`, so `find_package(cite_skills)` succeeded
and contributed no include directory. `cite_orchestration`'s `PickAt` fell back to testing
`header.frame_id.empty()` directly — which catches every unobserved pose the detector
actually produces, and does **not** catch a pose that carries a frame over NaN components.
That pose went to the planner as an object pose.

`cite_skills` now exports `include/${PROJECT_NAME}` and its `geometry_msgs` dependency, and
`PickAt` **calls** `cite_skills::pose_is_observed`. The predicate is not restated at the call
site, and now it cannot be: the call is a compile dependency rather than a comment asserting
another package's build state. Depending on an L3 header from L4 is downward and legal
(CLAUDE.md §5).

**The lesson is the one this section is about.** The convention had a writer and a reader in
one header precisely so they could not drift, and the reader was unreachable, so a consumer
wrote a weaker test that agreed with it on every input the system produced. Two rules that
agree on all observed inputs are not one rule. **A convention is only single-sourced when the
consumer can link against it.**

## Documenting an interface

Every `.msg`, `.srv`, and `.action` carries comments explaining what each field means, its
units, and its valid range. Units are not optional: `float64 velocity` is ambiguous,
`float64 velocity  # rad/s` is not. A large share of robotics defects are unit errors.
