# cite_interfaces

Every typed contract in the system — messages, services and actions — plus the QoS profile
library that says how each one is delivered. Nothing here runs. It is the vocabulary the
rest of the workspace is written in.

**It depends on nothing else in this project**, deliberately ([ADR-0010](../../../docs/adr/0010-typed-ros-interfaces.md)):
its `package.xml` names only `builtin_interfaces`, `geometry_msgs`, `std_msgs`, `rclcpp`
and `rclpy`. That is what lets an interface be reviewed before the code that consumes it
exists, and it is why this package sits at the bottom of the dependency graph.

## What is here

23 definitions — 14 `.msg`, 3 `.srv`, 6 `.action` — listed in `CMakeLists.txt` and frozen
against `test/interfaces.baseline`. Read the shapes with `ros2 interface show`; they are not
restated here (P1). The conventions they follow are in
[`docs/interfaces/README.md`](../../../docs/interfaces/README.md).

**A definition existing is not evidence that anything fills it.** That confusion put a false
sentence into a locked decision once — see the "How the error survived" section of
[ADR-0031](../../../docs/adr/0031-refuse-direct-handoff-without-orientation-certainty.md).
So the table below is by producer, verified by reading the servers at this commit rather
than by reading the definitions.

| Definition | Produced at this commit by |
|---|---|
| `MoveTo`, `Grasp`, `Pick`, `Place`, `Transfer` (actions) | `cite_skills/src/skill_server.cpp`, one server per arm |
| `Detect` (action) | `cite_skills/src/detection_server.cpp`, one server per zone |
| `Detection` | inside a `Detect` result — see the limitation below |
| `DetectionEvent` | `detection_server.cpp`, one publisher per beam |
| `ResultCode` | every action result above |
| `LineTopology`, `StationTopology`, `StationEdge` | `cite_facility/topology_server.py` |
| `LineState`, `StationState` | `cite_orchestration/src/line_orchestrator.cpp` |
| `ModelVersion`, `GetModelVersion` | `cite_facility/model_info.py` |
| `ConveyorState` | **nothing** |
| `RobotState` | **nothing** |
| `SafetyState` | **nothing** |
| `TwinMode`, `DivergenceMetrics`, `SetMode` | **nothing** — L5 does not exist (CLAUDE.md §2) |
| `ResetStation` | `cite_orchestration/line_orchestrator` — the operator's only control over a blocked station (ADR-0037) |

`LineTopology` and `LineState` each carry their own topic name as a `string TOPIC` constant,
so the name exists in one place and a consumer reads it off the message rather than
composing it.

## What it deliberately does not do

- **No node, no logic, no runtime behaviour.** The one exception is the QoS library below,
  which is a table of constants and no more.
- **No `std_msgs/String` carrying structured data**, anywhere, for any reason
  (CLAUDE.md §4). `LineTopology` exists precisely because the topology used to be published
  that way as a temporary exception; the exception expired when a consumer appeared.
- **It does not guarantee behaviour.** `SetMode.srv` says so in its own body: bring-up and
  `./scripts/enter hardware` enforce the hardware opt-in, and nothing enforces it on this
  service, because no server implements it. A contract is not an implementation (P7).

## The QoS library (ADR-0025)

Five named profiles — `sensor`, `state`, `command`, `latched`, `event` — in
`include/cite_interfaces/qos.hpp` (C++) and `cite_interfaces/qos.py` (Python).
The numbers live in [`docs/interfaces/qos-profiles.md`](../../../docs/interfaces/qos-profiles.md)
and are not repeated here.

Incompatible QoS between a publisher and a subscriber **connects silently and delivers
nothing** — no error at either end, both endpoints visible in `ros2 topic info`. That is why
a `rclcpp::QoS` literal or a hand-built `QoSProfile` outside these two files is a review
finding.

There are two implementations because ROS 2 has two client libraries and there is no way to
have one. `test/test_qos_consistency.py` asserts that the header, the module and the
document state the same four values for all five profiles.

The Python half is installed by an explicit `install(FILES ...)` rather than by
`ament_python_install_package`, because `rosidl_generate_interfaces` already creates a Python
package of this name for the generated bindings and the two would define the same CMake
targets. `CMakeLists.txt` records that; it is not a detail to tidy away.

## How to run it

Nothing to run. To use it:

```bash
ros2 interface show cite_interfaces/msg/DetectionEvent
ros2 interface list | grep cite_interfaces
```

Build and test through the fixed entry points (CLAUDE.md §7):

```bash
./scripts/build
./scripts/test --packages-select cite_interfaces
```

## How it fails

| Symptom | Cause |
|---|---|
| `interface_contract` fails with a diff | a field was renamed, retyped, reordered, or a constant's value changed. **Read the diff before doing anything.** It is a question — is this breaking, and does it need a version decision? — and the baseline is deliberately not self-updating |
| `qos_consistency` fails | the C++ header, the Python module and `docs/interfaces/qos-profiles.md` no longer agree. Fix all three; there is no authoritative one |
| a topic is listed, both endpoints are visible, and no message ever arrives | improvised QoS. The publisher and the subscriber picked incompatible profiles and neither reports it |
| a consumer deserialises nonsense at run time | an interface changed and the baseline was regenerated without reading the diff |

Regenerating the baseline is a conscious act:

```bash
CITE_WRITE_INTERFACE_BASELINE=1 python3 -m pytest test/test_interface_contract.py
```

and the reason goes in the commit message.

## Tests

Both are pytest, both run without a ROS graph.

* `test_interface_contract.py` — every definition against `test/interfaces.baseline`. What
  is stored is the *semantic* content: field and constant lines, comments and blank lines
  removed, whitespace collapsed. Reformatting a definition or rewriting its comments does
  not fail; changing a type, a name, an order or a constant's value does. `cross-cutting-testing.md`
  required this and nothing implemented it, so every definition was unguarded until it landed.
* `test_qos_consistency.py` — the three copies of the QoS table, described above.
