# cite_hardware

**L2 — the physical side's adapters for an xArm 5 on its linear track.** Three managed
(lifecycle) nodes that let the physical counterpart of `cell_b` present the names the
simulated side presents, and stop it when its commander goes away, and a fourth, the
initializer, that does what the operator does in UFACTORY Studio before the program
([ADR-0070](../../../docs/adr/0070-the-physical-arm-is-cell-b-s-counterpart.md) items 3, 4
and 5).

## Status, stated before anything else

- **Started by `cite_bringup`'s `hardware.launch.py`** on a physical side, with parameters
  generated from L0 into `cite_generated/control/counterpart/<zone>_<arm>_adapters.yaml`
  (ADR-0070 items 6–7). The deadman starts first; any of these nodes exiting brings the side
  down, and none respawns.
- **Supervised physical runs have exercised the arm and gripper; no full physical cycle
  has completed.** The track-transfer attempt was refused by the vendor. Observations are in
  [`bring-up.md`](../../../docs/operations/bring-up.md), "First physical runs". Automated
  adapter tests use fake vendor services and actions; they prove translation and state
  machines, not the machine's behaviour.
- **Python, not C++**, against CLAUDE.md §6's "C++ for real-time and control paths": none of
  the three is a control loop. Each relays a command to a vendor service or action that the
  vendor's own driver executes, or watches a heartbeat at a rate set in tenths of a second.
  The real-time path stays where it is: `ros2_control` and the vendor plugin.

## The three nodes

| Executable | Presents | Translates to (vendor) |
|---|---|---|
| `track_adapter.py` | the track controller's `joint_trajectory` topic in; the track joint's position on the arm's joint-state topic out | `set_linear_motor_pos`, `get_linear_motor_pos`, `set_linear_motor_stop` (`xarm_msgs`) |
| `gripper_relay.py` | `control_msgs/GripperCommand` at the plan's `gripper_action`; the drive joint's position on the arm's joint-state topic | the vendor driver's `GripperCommand` at `<prefix>xarm_gripper/gripper_action`; `get_gripper_position` (`xarm_msgs/GetFloat32`) |
| `deadman.py` | `cite_interfaces/DeadmanState`, latched and republished every tick | `set_state(4)` in every state but HEALTHY; `set_mode` then `set_state(0)` on entering HEALTHY, retried on later ticks while HEALTHY until acknowledged (`arm_enabled`); while tripped also `set_linear_motor_stop` and a cancel of every goal on named actions, every tick |

**How the arm is stopped.** The arm's own trajectory controller is not behind any gate here.
The deadman holds the arm stopped through the vendor's state: `set_state(4)` on every tick in
every state but HEALTHY, so a re-enable from UFACTORY Studio, the pendant or another client is
undone within one tick; and, while tripped, a cancel of every goal on the arm's
`FollowJointTrajectory` action. The vendor plugin streams nothing while the arm is in state 4
(`uf_robot_system_hardware.cpp:339-344`, `:464-502`). Only the transition AWAITING -> HEALTHY
enables the arm, with the vendor plugin's own sequence (`set_mode` with its streaming mode,
then `set_state(0)`), and the plugin then reactivates the controllers itself (`:345-350`).
`DeadmanState.state` HEALTHY says motion is permitted; `arm_enabled` says the deadman's
`set_state(0)` was acknowledged in this HEALTHY period. The relays gate on `state`; a consumer
that needs the arm ready must also require `arm_enabled`. The START decision and its send are
one step under the lock every trip and every STOP takes, so no START follows a trip's STOP. An
empty `JointTrajectory` is not a stop on `joint_trajectory_controller` 4.x (it is refused), so
nothing here sends one.

`track_adapter` and `gripper_relay` forward a motion command **only while ACTIVE and only while
the latest `DeadmanState` says HEALTHY, is younger than `deadman_state_max_age_s`, and comes from
the one deadman publishing**. When that gate closes for any reason, the track adapter calls
`set_linear_motor_stop` itself if a move it sent may still be running, and so it does on
deactivate and shutdown. That stop is level-triggered: sent again on every poll, active or not,
while motion is not permitted and a move may be running, until the vendor acknowledges one
sent after the last move was answered.

**What the track adapter sends** (SA2c-S-02). A track command carries the sender's start as its
first point and the target as its last (`cite_bringup/track_command.py`); the vendor speed is
that COMMANDED speed, capped at the axis maximum, never one derived from where this carriage
stands, and a one-point command is refused. A move goes out in segments reaching `segment_s`
of travel ahead of the carriage, the next sent on every fresh read while the gate is open, so a
lost stop with every process gone overruns by at most one segment. A command whose two points
are one position is a HOLD, answered with `set_linear_motor_stop` (level-triggered) and no
move; the twin boundary sends each side a hold at that side's own position when a program
abandons a move. The deadman's own behaviour, and why a trip latches, is in
`cite_hardware/deadman.py` and `cite_hardware/liveness.py`.

**What the deadman watches.** The twin boundary's heartbeat: the boundary process, its executor
serving this side, and the DDS path from it. Not the vendor driver's link to the arm's
controller, which is the vendor's to detect.

**On SIGINT or SIGTERM** each process stops its asset before it exits: rclpy runs no lifecycle
transition when its context goes down, so `cite_hardware/process.py` takes the signal itself,
calls the node's `stop_before_exit()` while the context still stands — the deadman sends
`set_state(4)`, the track adapter `set_linear_motor_stop` if a move may be running — and waits
for the answers within the node's own vendor-call bound (`call_deadline_s`; twice
`position_max_age_s` for the track adapter, which exits only once a stop sent after any move in
flight was answered is acknowledged). A SIGKILL leaves no such chance: the relays' gates close when the
deadman's publisher goes, but nothing then puts the ARM back to state 4.

**Recovery after a trip.** Find why the heartbeat stopped. Then `ros2 lifecycle set
<deadman> deactivate` and `activate`: the deadman says AWAITING and keeps the arm stopped, and
enables it on the first heartbeat of a running boundary. A vendor error is not cleared by this;
it needs the vendor's own `clean_error` first.

The heartbeat is `cite_interfaces/TwinHeartbeat` on `TwinHeartbeat.TOPIC`, published by the
twin boundary (`cite_twin`) onto each side's own domain, carrying one `boundary_id` per boundary
start. The deadman latches the first id it hears; another id, or a second heartbeat publisher,
trips it.

## The initializer

`initializer.py` (ADR-0070, 2026-10-08) does what the operator does by hand in UFACTORY Studio
before running the program, when asked through `cite_interfaces/srv/InitializeAsset` on the
plan's `initialize_service`: `set_linear_motor_enable(1)`, `set_gripper_enable(1)`, then
`get_linear_motor_on_zero`, and only where it reads 0, `set_linear_motor_back_origin`
(no wait, no auto-enable; sent once) followed by zero reads every `poll_period_s` until it
reads 1. It does nothing until asked, refuses while inactive or while the deadman is not
HEALTHY, and answers `success: false` naming the step and the vendor's code on any refusal.
A homing that is refused, loses the deadman's gate or exceeds `deadline_s` is followed by
`set_linear_motor_stop`, as is the process ending during a homing. No `clean_error`. Tested
against vendor fakes only (`test/test_initializer_launch.py`); not yet run on the physical arm.

## Parameters

**None has a default.** Each is a fact of the asset, wired from L0 by whoever starts the node;
`configure` fails naming every one that is missing, empty, non-finite or of the wrong type.
The authoritative list is `SPECS` in each module; `ros2 param describe` shows each one's
meaning once the node is up.

**`track_adapter`** — `command_topic` (string), `joint` (string), `joint_state_topic`
(string), `position_scale` (double, vendor units per metre, > 0), `position_min_m` and
`position_max_m` (double, the travel; min < max), `max_speed_mps` (double, > 0),
`poll_period_s` (double, > 0), `position_max_age_s` (double, > 0: the oldest position a
segment is planned from, the deadline of a position read and of a stop), `segment_s` (double,
> 0: how far ahead of the carriage one vendor move reaches, in seconds at the commanded speed),
`auto_enable` (bool),
`set_position_service`, `get_position_service`, `stop_service`, `deadman_state_topic`
(strings), `deadman_state_max_age_s` (double, > 0, above the deadman's `tick_period_s`).

**`gripper_relay`** — `action_name`, `vendor_action_name` (strings, different),
`open_position`, `closed_position` (doubles, the drive joint), `vendor_open_position`,
`vendor_closed_position` (doubles, the vendor ACTION's unit: 0.0 open and 0.85 closed for the
xArm gripper; neither range empty), `result_timeout_s` (double, > 0, also the bound on an unanswered
`get_gripper_position`), `deadman_state_topic` (string), `deadman_state_max_age_s` (double,
> 0), `drive_joint`, `joint_state_topic`,
`get_position_service` (strings), `vendor_state_open_position`, `vendor_state_closed_position`
(doubles, what the vendor's `get_gripper_position` reports, in PULSES: about 850 open and 0
closed), `poll_period_s` (double, > 0).

The vendor gripper action converts as `pulses = |850 - position * 1000|` and reports back
`|850 - pulses| / 1000` (`xarm_api/src/xarm_driver.cpp:507-515`, `max_pos` 850 by default), so
its action and its state service have different units, and each has its own pair of endpoints.

Every vendor service and action name is a parameter, never assembled here: with the
generated description the vendor's `hw_ns` expands to `${prefix}${hw_ns}`, so the names are
the generator's to emit.

## Where the side's joint states come from

On the physical side `joint_state_broadcaster` reports joint1..5 only. The track adapter
publishes the track joint and the gripper relay the drive joint, **on the same arm
joint-state topic**, each message naming only the joints its publisher owns. No merger node:
`robot_state_publisher` and MoveIt's current-state monitor both update per joint name from
partial messages, and so does the twin boundary's divergence operand, whose age is its oldest
joint's (`cite_twin`).

**While the deadman holds the arm at state 4, the vendor plugin deactivates every controller in
its controller manager** — `joint_state_broadcaster` included — and on recovery activates every
controller it lists (`uf_robot_system_hardware.cpp:398-424`, `:426-440`), through the
manager's `list_controllers` and `switch_controller`, which it names absolutely and
`hardware.launch.py` remaps onto the asset's own manager. So joint1..5 are not
published while AWAITING, INACTIVE or TRIPPED; the track adapter and gripper relay keep
publishing theirs.

**`deadman`** — `zone`, `asset_id`, `state_topic`, `set_state_service`, `set_mode_service`,
`linear_motor_stop_service` (strings), `timeout_s` (double, > 0), `tick_period_s` (double,
> 0, below `timeout_s`), `call_deadline_s` (double, > 0), `enable_mode` (integer, 1 servo or 4
joint velocity: the mode the vendor plugin streams in), `cancel_actions` (non-empty string
array: the gripper relay's action and the arm controller's `follow_joint_trajectory`). It
refuses `use_sim_time`.

## How each one fails

- **The vendor's gripper action is always served, and bypasses the relay's gate on the
  physical domain** (SA2c-S-05, a residual, not fixed here). The driver creates
  `<prefix>xarm_gripper/gripper_action` unconditionally (`xarm_driver.cpp:485-486`), so any
  client on the physical side's domain can move the gripper without the deadman's gate. The
  deadman cancels only the relay's action. What bounds this is who can reach that domain.

- **A command it will not forward is refused and logged, never clamped into a different
  motion.** A track trajectory with no points or only one, naming any joint but the track's, a
  target outside the travel, a last point not after the first, a command while the carriage
  position is unread or older than `position_max_age_s`: refused.
  A gripper position beyond the drive joint's travel is clamped, as the simulated joint's own
  limits would clamp it, and said in the log.
- **A vendor service that is not advertised refuses the command** (no wait, no retry), and a
  vendor error return is logged with its code; the next command is handled normally.
- **A failed track position call ends the accepted track command.** Its target and queued
  segments are discarded, and conservative stop handling remains in force. Fresh position
  reports cannot retry that rejected command; a new command still requires the normal gate.
  This topic-based interface does not return a typed rejection to its sender, which may wait
  until its existing arrival deadline.
- **A track position the vendor will not read is not published**, rather than a stale one.
- **Every gripper goal is bounded by `result_timeout_s`**, because the vendor's error path
  leaves its own goal running forever (it calls `canceled()` on a goal no one asked to cancel,
  which `rclcpp_action` refuses).
- **A gripper cancel is forwarded, and the vendor ignores it**: its execute loop does not read
  the request, so the jaws finish their motion. The relay reports its goal CANCELED once the
  vendor acknowledges, with the last position the vendor reported.
- **A new gripper goal is REJECTED while a vendor goal is still running**, where the simulated
  `GripperActionController` would preempt: the vendor runs each goal on its own thread and
  ignores a cancel, so preempting would run two vendor threads against one gripper. "Still
  running" lasts until the vendor's result, or `result_timeout_s` after the goal was sent.
- **`stalled` and `reached_goal` are forwarded exactly as the vendor reports them.** The vendor
  never sets either, so on the physical side both arrive false and a Grasp judging custody
  from them reads "not holding" (ADR-0063 left the SDK stall path unestablished).
- **The deadman trips when heartbeats stop for `timeout_s`, when their publisher disappears,
  or when a second boundary appears** (another `boundary_id`, or a second publisher), after
  the first one. **It trips too when the vendor's `set_state` stops being served by exactly one
  server** while HEALTHY: a vendor driver that went away or restarted has STARTED the arm in its
  own `on_activate`. Seen on the tick, so an outage shorter than `tick_period_s` with no overlap
  of old and new server is not seen. While tripped every stop is re-issued on every tick whether or not the last
  one was acknowledged, and each call is abandoned at `call_deadline_s` so an unanswered call
  never holds back the next. A trip is latched until a lifecycle deactivate and activate.

## Tests

`./scripts/test` runs them: unit tests for the unit conversions (`test_mapping.py`), the
deadman's state machine (`test_liveness.py`) and the required parameters
(`test_parameters.py`); one `launch_testing` test per node against fakes in
`test/vendor_fakes.py`. Nothing in them reaches hardware.
