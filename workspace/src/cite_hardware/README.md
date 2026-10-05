# cite_hardware

**L2 — the physical side's adapters for an xArm 5 on its linear track.** Three managed
(lifecycle) nodes that let the physical counterpart of `cell_b` present the names the
simulated side presents, and stop it when its commander goes away
([ADR-0070](../../../docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md) items 3, 4
and 5).

## Status, stated before anything else

- **Nothing starts these nodes yet.** The physical side's launch, and wiring their parameters
  from L0 through the generated plan, are ADR-0070 item 6 and later work. Until then they run
  only in this package's own tests.
- **No physical arm, track or gripper has been driven through them.** Every test runs against
  fake vendor services and a fake vendor action held by the test process. What the tests show
  is the translation and the state machines, not the machine's behaviour.
- **Python, not C++**, against CLAUDE.md §6's "C++ for real-time and control paths": none of
  the three is a control loop. Each relays a command to a vendor service or action that the
  vendor's own driver executes, or watches a heartbeat at a rate set in tenths of a second.
  The real-time path stays where it is: `ros2_control` and the vendor plugin.

## The three nodes

| Executable | Presents | Translates to (vendor) |
|---|---|---|
| `track_adapter.py` | the track controller's `joint_trajectory` topic in; the track joint's position on the arm's joint-state topic out | `set_linear_motor_pos`, `get_linear_motor_pos`, `set_linear_motor_stop` (`xarm_msgs`) |
| `gripper_relay.py` | `control_msgs/GripperCommand` at the plan's `gripper_action` | the vendor driver's `GripperCommand` at `<prefix>xarm_gripper/gripper_action` |
| `deadman.py` | `cite_interfaces/DeadmanState`, latched | `set_state` (stop), `set_linear_motor_stop`, a cancel of every goal on named actions, an empty trajectory on named controller topics |

`track_adapter` and `gripper_relay` forward a motion command **only while ACTIVE and only while
the latest `DeadmanState` says HEALTHY and a deadman is publishing**. A track stop (an empty
trajectory) is never gated. The deadman's own behaviour, and why a trip latches, is in
`cite_hardware/deadman.py` and `cite_hardware/liveness.py`.

The heartbeat is `cite_interfaces/TwinHeartbeat` on `TwinHeartbeat.TOPIC`, published by the
twin boundary (`cite_twin`) onto each side's own domain.

## Parameters

**None has a default.** Each is a fact of the asset, wired from L0 by whoever starts the node;
`configure` fails naming every one that is missing, empty, non-finite or of the wrong type.
The authoritative list is `SPECS` in each module; `ros2 param describe` shows each one's
meaning once the node is up.

**`track_adapter`** — `command_topic` (string), `joint` (string), `joint_state_topic`
(string), `position_scale` (double, vendor units per metre, > 0), `position_min_m` and
`position_max_m` (double, the travel; min < max), `max_speed_mps` (double, > 0),
`poll_period_s` (double, > 0), `auto_enable` (bool), `set_position_service`,
`get_position_service`, `stop_service`, `deadman_state_topic` (strings).

**`gripper_relay`** — `action_name`, `vendor_action_name` (strings, different),
`open_position`, `closed_position`, `vendor_open_position`, `vendor_closed_position`
(doubles; neither range empty), `result_timeout_s` (double, > 0), `deadman_state_topic`
(string).

**`deadman`** — `zone`, `asset_id`, `state_topic`, `set_state_service`,
`linear_motor_stop_service` (strings), `timeout_s` (double, > 0), `cancel_actions`,
`stop_trajectory_topics` (non-empty string arrays). It refuses `use_sim_time`.

## How each one fails

- **A command it will not forward is refused and logged, never clamped into a different
  motion.** A track trajectory naming any joint but the track's, a target outside the travel,
  a final point not in the future, a command while the carriage position is unread: refused.
  A gripper position beyond the drive joint's travel is clamped, as the simulated joint's own
  limits would clamp it, and said in the log.
- **A vendor service that is not advertised refuses the command** (no wait, no retry), and a
  vendor error return is logged with its code; the next command is handled normally.
- **A track position the vendor will not read is not published**, rather than a stale one.
- **Every gripper goal is bounded by `result_timeout_s`**, because the vendor's error path
  leaves its own goal running forever (it calls `canceled()` on a goal no one asked to cancel,
  which `rclcpp_action` refuses).
- **A gripper cancel is forwarded, and the vendor ignores it**: its execute loop does not read
  the request, so the jaws finish their motion. The relay reports its goal CANCELED once the
  vendor acknowledges, with the last position the vendor reported.
- **A preempted gripper goal ends ABORTED**, where the simulated `GripperActionController`
  ends it CANCELED: rclpy cannot cancel a goal no client asked to cancel.
- **`stalled` and `reached_goal` are forwarded exactly as the vendor reports them.** The vendor
  never sets either, so on the physical side both arrive false and a Grasp judging custody
  from them reads "not holding" (ADR-0063 left the SDK stall path unestablished).
- **The deadman trips when heartbeats stop for `timeout_s`, or when their publisher
  disappears**, after the first one. A stop call that fails or goes unanswered is re-issued
  every `timeout_s` while tripped, until the vendor acknowledges it. A trip is latched until a
  lifecycle deactivate and activate.

## Tests

`./scripts/test` runs them: unit tests for the unit conversions (`test_mapping.py`), the
deadman's state machine (`test_liveness.py`) and the required parameters
(`test_parameters.py`); one `launch_testing` test per node against fakes in
`test/vendor_fakes.py`. Nothing in them reaches hardware.
