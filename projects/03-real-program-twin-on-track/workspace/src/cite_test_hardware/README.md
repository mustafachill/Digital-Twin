# cite_test_hardware

`ros2_control` test doubles. **Nothing here describes real hardware, and nothing here may be
loaded by a production bring-up.**

Status: **BUILT**, and exercised by
[`cite_bringup/test/test_abort_classification_launch.py`](../cite_bringup/test/test_abort_classification_launch.py).
The decision is [ADR-0040](../../../docs/adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md).

## What is in it

### `cite_test_hardware/JointStopSystem`

`mock_components/GenericSystem` with two differences, both declared in the description:

| `<hardware>` parameter | Meaning |
|---|---|
| `stop_joint` | The joint that has hard stops. **Required.** |
| `stop_lower_rad` | The lower stop, in the joint's own units. **Required.** |
| `stop_upper_rad` | The upper stop. **Required**, and strictly above the lower. |

1. **A pair of hard stops.** After the base class has mirrored commands to states, the named
   joint's position state is clamped into `[stop_lower_rad, stop_upper_rad]`. The arm tracks
   its trajectory normally until it reaches the stop, and then stands there while the
   trajectory advances without it. That is what makes a controller abort land with the arm
   **part way** along its path — the case `mock_components/GenericSystem`'s `disable_commands`
   cannot produce, because it never lets the joint leave the first point.
2. **A velocity state that is a function of motion.** Every joint declaring a velocity state
   interface gets the first difference of its position state over the control period.
   Without this, a rig on position-only command interfaces reports a velocity of exactly
   zero for an arm travelling at any speed, because nothing ever writes that interface.

## Why it cannot be loaded by a real bring-up

Three things, and the first two are structural rather than conventional:

1. **It refuses to initialise without `stop_joint`.** That parameter has no home in the L0
   facility model — the model has no concept of a hard stop at a joint angle — so a
   generated `<ros2_control>` block cannot carry it, and a component that will not start
   without it cannot serve as a backend.
2. **The whole package is inside `if(BUILD_TESTING)`.** A build configured with
   `-DBUILD_TESTING=OFF` declares no library, installs no library, and registers no
   pluginlib class, so the class name does not resolve at all.
3. **Two guard tests.** `test/test_refusal.cpp` asserts every way `on_init` refuses —
   including the load-bearing one, a description with no `stop_joint` at all, which is the
   only shape a generated `<ros2_control>` block could ever have. `test/test_unreachable.py`
   asserts that the package name appears nowhere in `model/`, nowhere in
   `workspace/src/cite_generated/`, in no launch file, and in no package's dependency list
   except as a `<test_depend>`.

## What may be added here

The admission test is in `package.xml` and is deliberately narrow: a `ros2_control` hardware
component, existing to make a *failure* reproducible on demand, refusing to start without a
parameter L0 cannot express, depended on by nothing that is not a test. A package named for
what tests need will otherwise accumulate whatever a test needed.

## Running it

It is not run directly. `./scripts/test` builds it and
`cite_bringup/test/test_abort_classification_launch.py` stands it up under a real
`ros2_control_node`, a real `move_group` and the real L3 skill server.
