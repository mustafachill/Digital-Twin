# cite_interfaces

Every typed contract in the system — messages, services and actions — plus the QoS profile
library that says how each one is delivered. Nothing here runs. It is the vocabulary the
rest of the workspace is written in.

**It depends on nothing else in this project**, deliberately ([ADR-0010](../../../docs/adr/0010-typed-ros-interfaces.md)):
its `package.xml` names only `builtin_interfaces`, `geometry_msgs`, `std_msgs`, `rclcpp`
and `rclpy`. That is what lets an interface be reviewed before the code that consumes it
exists, and it is why this package sits at the bottom of the dependency graph.

## What is here

18 definitions — 8 `.msg`, 5 `.srv`, 5 `.action` — listed in `CMakeLists.txt` and frozen
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
| `ResultCode` | every action result above |
| `ModelVersion`, `GetModelVersion` | `cite_facility/model_info.py` |
| `RobotState` | `cite_skills/src/skill_server.cpp`, latched on each arm's `state` topic; read by `cite_bringup`'s program and its simulation-only grasp-hold bridge |
| `SafetyState` | **nothing** |
| `TwinHeartbeat` | `cite_twin/twin_boundary.py`, onto each side's own domain from that side's own executor (ADR-0070 item 5) |
| `DeadmanState` | `cite_hardware/deadman.py`, started first by `cite_bringup`'s `hardware.launch.py` on a physical side (ADR-0070 item 6); read by the relays and by the twin boundary's readiness gate |
| `InitializeAsset` | `cite_hardware/initializer.py`, on a physical side only, under the plan's `initialize_service` (ADR-0070); called by `cite_bringup.program.home` |
| `TwinMode`, `DivergenceMetrics`, `SetMode`, `TrackArrived`, `JointsAt` | `cite_twin/twin_boundary.py`, which the pair supervisor starts under `./scripts/sim --pair` and `./scripts/program` (ADR-0057) and no launch file starts; it refuses a zone declaring one side, and the one shipped zone, `cell_b`, declares two. Every `DivergenceMetrics` it can publish has `valid` false (ADR-0050) |

`TwinMode` and `DivergenceMetrics` each carry their own topic name as a `string TOPIC`
constant, and `SetMode` carries its own as a `string SERVICE` on the request — so each name exists in one place and a consumer reads it
off the definition rather than composing it. In Python a service's constant is on the
section it was declared in (`SetMode.Request.SERVICE`), which is the same place C++ reaches
it (`SetMode::Request::SERVICE`).

## What it deliberately does not do

- **No node, no logic, no runtime behaviour.** The one exception is the QoS library below,
  which is a table of constants and no more.
- **No `std_msgs/String` carrying structured data**, anywhere, for any reason
  (CLAUDE.md §4).
- **It does not guarantee behaviour.** `SetMode.srv` says so in its own body: bring-up and
  `./scripts/enter hardware` enforce the hardware opt-in before the stack starts, and the L5
  server now applies the same check at the transition — in a process only the pair supervisor
  starts, and no CI step. A
  contract is not an implementation, and an implementation nothing runs is not a guarantee
  either (P7).

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
ros2 interface show cite_interfaces/msg/TwinMode
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
