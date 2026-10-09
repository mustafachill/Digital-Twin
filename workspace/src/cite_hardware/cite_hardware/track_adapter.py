#!/usr/bin/env python3
# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The physical linear track, behind the simulated track controller's own names.

ADR-0070 item 3. In simulation the carriage is a `ros2_control` joint driven by
`picker_track_trajectory_controller`, commanded on that controller's
`joint_trajectory` topic and reported on the arm's joint states. The physical
track is not a `ros2_control` joint at all: the vendor plugin exports joint1..5,
and its embedded driver serves the track only as `xarm_api` services. This node
presents the simulated names on the physical side and translates:

- **Command.** It subscribes the same `command_topic` the simulated controller
  serves. A command carries its start as its first point and its target as its
  last (`cite_bringup.track_command`), so the COMMANDED speed is the distance
  between them over the time between them, the same on both sides. The vendor
  is sent that speed, capped at the axis maximum, and never one derived from
  where this carriage stands (SA2c-S-02 b); a command with one point names no
  speed and is refused. A trajectory with no points is refused, as the
  simulated controller refuses it (`joint_trajectory_controller` 4.x).
- **Speed.** The commanded speed is written with `set_linear_motor_speed`
  before a move at a speed the vendor has not ACKNOWLEDGED since this adapter
  was activated, and the move is sent only once that write answered 0. The
  vendor SDK's `set_linear_motor_pos` writes a speed only when it differs from
  the one it cached, and ignores whether that write succeeded
  (`xarm_sdk/cxx/src/xarm/wrapper/xarm_linear_motor.cc:208-210`), so a speed
  passed only with the move could be silently not the speed the carriage
  runs at (SA-S-03).
- **Segments.** A move is sent as `set_linear_motor_pos` to a point at most
  `segment_s` of travel at the commanded speed ahead of the carriage, and the
  next segment is sent on every fresh position read while the gate is open,
  until the target itself is within one segment and is sent. If every process
  here dies with the carriage moving, it runs at most one segment past the
  last read (SA2c-S-02 d). A failed or vendor-rejected answer to a segment, or
  to the speed write before it, ends the move: a stop is sent and no later
  segment of it is sent.
- **Hold.** A command whose first and last points are one position is a hold:
  the simulated controller holds where it stands, and this adapter sends
  `set_linear_motor_stop` and drops any move in progress, level-triggered like
  every other stop below, until one is acknowledged. A hold never moves the
  carriage, whatever position it names (SA2c-S-02 a), and a move that arrived
  before it is never sent after it, wherever that move was - being checked,
  waiting for its speed write, or held behind a vendor call (SA-S-06).
- **State.** It polls `get_linear_motor_pos` and publishes the track joint's
  position on the arm's joint-state topic, where the simulated side's
  `joint_state_broadcaster` publishes it. The program reads arrival from there.
- **Zero.** A position read from a track that has not found its zero is
  measured from wherever the carriage stood at power-up, so it is no place on
  the track at all. The adapter reads `get_linear_motor_on_zero` on activation
  and again after any vendor error, and - while the answer is not 1 - on every
  poll until it is (the initializer homes it). Until then it publishes NO track
  position, so the twin boundary hears the side as not ready and offers no
  target that commands it (S-03). Commands are handled exactly as before: the
  vendor refuses a move on a track it has not initialized.

**It never commands motion while not ACTIVE, and never while the deadman does
not permit it** (`cite_hardware.gate`). **It stops the carriage itself** with
`set_linear_motor_stop` when its gate closes for any reason — the deadman's
trip, the deadman's state going stale, a second deadman — and on deactivate and
shutdown, whenever a `set_linear_motor_pos` was in flight or a move it sent may
still be running. The deadman's own stop on a trip is the second, independent
one; a closure the deadman did not cause has only this one.

That stop is LEVEL-triggered: on every poll, active or not, while motion is not
permitted and a move may be running, it is sent again until the vendor answers
one with success that was sent after the last move was ANSWERED and with no
move call outstanding — only then is the carriage taken as no longer driven
from here. A stop unanswered within `position_max_age_s` is abandoned and sent
again. A move is marked possible BEFORE the last look at the gate, under the
lock, so a closure racing a move either prevents it or finds it and stops it.
On SIGINT or SIGTERM the process exits only once such a stop is acknowledged,
or after twice `position_max_age_s`: a move in flight when the signal came is
followed by a stop sent after its answer, so the exit stop is never overtaken
by it (`cite_hardware.process`, SA2c-S-02 e).

**A segment is planned only from a fresh position.** The carriage position is
polled; a read unanswered within `position_max_age_s` is abandoned, and a
position older than that is not used to plan a segment.

**The vendor call is never waited on.** `set_linear_motor_pos` is called with
`wait=false`, and that is load-bearing rather than a preference: the vendor's
driver serves every one of its services from one single-threaded executor
(`xarm_controller/src/hardware/uf_robot_system_hardware.cpp`, `rclcpp::spin`
of the driver node), so a waiting position call would hold that executor for
the whole move — and the deadman's `set_linear_motor_stop` and `set_state`
would queue behind it.

**Preemption.** A new command retargets the carriage: the vendor takes a new
position while moving, which is also what makes a segment's successor
seamless. A command that arrives while the previous vendor call has not yet
answered is held, and replaced by any later one, so the vendor receives the
latest target and never a backlog. A held command is discarded, not sent,
when the call it waited behind fails or is rejected by the vendor.
"""

from __future__ import annotations

import sys
import threading

from cite_hardware.gate import DeadmanGate
from cite_hardware.mapping import (
    from_vendor_position,
    next_segment,
    Refused,
    require_carried_out,
    require_within,
    to_vendor_position,
    track_target,
    TrackTarget,
    vendor_speed,
)
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.qos import COMMAND, STATE
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.task import Future
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory
from xarm_msgs.srv import Call, GetInt16, LinearMotorSetPos, SetInt16

NODE_NAME = "track_adapter"

#: Every parameter this node takes. None has a default (ADR-0070): each is a
#: fact of the asset, wired from L0 through the generated plan.
SPECS: tuple[Spec, ...] = (
    Spec(
        "command_topic",
        Parameter.Type.STRING,
        "the track controller's joint_trajectory topic, exactly as the plan names it",
    ),
    Spec("joint", Parameter.Type.STRING, "the track joint's name"),
    Spec(
        "joint_state_topic",
        Parameter.Type.STRING,
        "the arm's joint-state topic, on which the track position is published",
    ),
    Spec(
        "position_scale",
        Parameter.Type.DOUBLE,
        "vendor position units per metre (the xArm track reports millimetres)",
        positive=True,
    ),
    Spec("position_min_m", Parameter.Type.DOUBLE, "the track's lower travel limit, metres"),
    Spec("position_max_m", Parameter.Type.DOUBLE, "the track's upper travel limit, metres"),
    Spec(
        "max_speed_mps",
        Parameter.Type.DOUBLE,
        "the track's declared maximum speed, metres per second",
        positive=True,
    ),
    Spec(
        "poll_period_s",
        Parameter.Type.DOUBLE,
        "how often the vendor position is read and published, seconds",
        positive=True,
    ),
    Spec(
        "position_max_age_s",
        Parameter.Type.DOUBLE,
        "steady-clock bound on a carriage position a segment is planned from, on an "
        "unanswered position read and on an unanswered stop",
        positive=True,
    ),
    Spec(
        "segment_s",
        Parameter.Type.DOUBLE,
        "how far ahead of the carriage one vendor move reaches, seconds at the commanded "
        "speed; the overrun if every stop is lost",
        positive=True,
    ),
    Spec(
        "auto_enable",
        Parameter.Type.BOOL,
        "whether a position command may enable a disabled track motor",
    ),
    Spec(
        "set_position_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_pos service (xarm_msgs/LinearMotorSetPos)",
    ),
    Spec(
        "speed_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_speed service (xarm_msgs/SetInt16, units/s), "
        "written before a move at a speed not yet acknowledged",
    ),
    Spec(
        "get_position_service",
        Parameter.Type.STRING,
        "the vendor's get_linear_motor_pos service (xarm_msgs/GetInt16)",
    ),
    Spec(
        "stop_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_stop service (xarm_msgs/Call)",
    ),
    Spec(
        "on_zero_service",
        Parameter.Type.STRING,
        "the vendor's get_linear_motor_on_zero service (xarm_msgs/GetInt16): whether the "
        "track has found its zero; no position is published until it has",
    ),
    Spec(
        "deadman_state_topic",
        Parameter.Type.STRING,
        "the deadman's DeadmanState topic for this side",
    ),
    Spec(
        "deadman_state_max_age_s",
        Parameter.Type.DOUBLE,
        "steady-clock age above which the deadman's last state closes the gate; above "
        "the deadman's tick_period_s",
        positive=True,
    ),
)


class TrackAdapter(LifecycleNode):
    def __init__(self, **node_options) -> None:
        # `node_options` reach `rclpy.node.Node` unchanged; a test hands its
        # parameter overrides in through them rather than through a launch.
        super().__init__(NODE_NAME, **node_options)
        self._required = RequiredParameters(self, SPECS)
        self._lock = threading.Lock()
        self._config: dict | None = None
        self._active = False
        self._group = ReentrantCallbackGroup()
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self._set_client = None
        self._speed_client = None
        self._get_client = None
        self._stop_client = None
        self._zero_client = None
        self._state_publisher = None
        self._command_subscription = None
        self._gate: DeadmanGate | None = None
        self._poll_timer = None
        #: The carriage position last read from the vendor, metres. `None`
        #: until the first good read and after a failed one: a speed derived
        #: from a position nobody has read would be a guess.
        self._position_m: float | None = None
        #: Steady-clock time the position above was read, nanoseconds.
        self._position_at_ns = 0
        self._set_in_flight = False
        #: A position read is in flight: reserved under the lock BEFORE it is
        #: sent, so two polls never both send one and drop each other's reply.
        self._get_in_flight = False
        #: The position read in flight, and when it is abandoned.
        self._get_future = None
        self._get_deadline_ns = 0
        self._pending: LinearMotorSetPos.Request | None = None
        #: Counts every hold commanded and failed position call. A move
        #: carries the count it was accepted under, and one accepted before
        #: the latest hold or rejection is never
        #: sent, wherever it is in the pipeline (SA-S-06).
        self._hold_sequence = 0
        #: The hold count the move in progress, and the held move, were accepted under.
        self._target_hold = 0
        self._pending_hold = 0
        #: The vendor speed `set_linear_motor_speed` last answered 0 for, since
        #: activation; `None` before the first, after a failed write and once
        #: the gate is found closed, so the next move writes its speed first
        #: (SA-S-03, SA-S-09).
        self._acked_speed: int | None = None
        #: Counts every time `_acked_speed` is forgotten because the gate was
        #: found closed or the adapter re-activated. A speed write carries the
        #: count it was sent under, and its acknowledgement is recorded only if
        #: no closure came since: a trip landing while the write is in flight
        #: may reset the vendor after it (SA R-1).
        self._speed_epoch = 0
        #: A position command may have been sent since the last ACKNOWLEDGED
        #: stop: the carriage may be moving. Set before the move is sent and
        #: cleared only by a stop the vendor answered with success, sent after
        #: the last move and with no move call outstanding.
        self._move_possible = False
        #: Counts every move sent, so a stop knows whether a move followed it.
        self._move_sequence = 0
        #: The stop call in flight, the move count when it was sent, and when
        #: it is abandoned so the next poll sends another.
        self._stop_future = None
        self._stop_sequence = 0
        self._stop_deadline_ns = 0
        #: The stop in flight was sent with no move call outstanding, so it is
        #: processed after every move this adapter sent (SA2c-S-02 e).
        self._stop_after_answer = False
        #: The move in progress, until its last segment is sent: re-planned
        #: from every fresh position while the gate is open.
        self._target: TrackTarget | None = None
        #: A hold or vendor rejection ended the move: the carriage is stopped,
        #: level-triggered, until a move is accepted again.
        self._holding = False
        #: Completed once the carriage is no longer driven from here, while the
        #: process is ending (`stop_before_exit`).
        self._exit_future: Future | None = None
        #: Whether the vendor says the track has found its zero: `None` until
        #: read, and again after activation and after any vendor error. No
        #: position is published unless it is True (S-03).
        self._on_zero: bool | None = None
        #: The zero read in flight, and when it is abandoned.
        self._zero_future = None
        self._zero_deadline_ns = 0

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            config = self._required.read()
        except ParameterError as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        if not config["position_min_m"] < config["position_max_m"]:
            self.get_logger().error(
                "cannot configure: position_min_m must be below position_max_m, got "
                f"{config['position_min_m']} and {config['position_max_m']}"
            )
            return TransitionCallbackReturn.FAILURE
        self._config = config

        self._set_client = self.create_client(
            LinearMotorSetPos, config["set_position_service"], callback_group=self._group
        )
        self._speed_client = self.create_client(
            SetInt16, config["speed_service"], callback_group=self._group
        )
        self._get_client = self.create_client(
            GetInt16, config["get_position_service"], callback_group=self._group
        )
        self._stop_client = self.create_client(
            Call, config["stop_service"], callback_group=self._group
        )
        self._zero_client = self.create_client(
            GetInt16, config["on_zero_service"], callback_group=self._group
        )
        # STATE is `joint_state_broadcaster`'s own profile on this topic, so a
        # reader of the arm's joint states is matched by both publishers alike.
        self._state_publisher = self.create_lifecycle_publisher(
            JointState, config["joint_state_topic"], STATE
        )
        # COMMAND is the profile the twin boundary and the program publish a
        # track command with (cite_twin, cite_bringup.program.cell).
        self._command_subscription = self.create_subscription(
            JointTrajectory,
            config["command_topic"],
            self._on_command,
            COMMAND,
            callback_group=self._group,
        )
        self._gate = DeadmanGate(
            self,
            config["deadman_state_topic"],
            config["deadman_state_max_age_s"],
            self._group,
            self._on_gate_closed,
        )
        # From configure to cleanup, inactive included: a stop the vendor has
        # not acknowledged is sent again on every poll, whatever the state.
        self._poll_timer = self.create_timer(
            config["poll_period_s"], self._poll, callback_group=self._group
        )
        self.get_logger().info(
            f"configured: {config['command_topic']} -> {config['set_position_service']}, "
            f"{config['joint']} published on {config['joint_state_topic']}"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        assert self._config is not None
        with self._lock:
            self._active = True
            # The vendor's speed is not taken on trust across an inactive
            # period: the first move after activation writes it.
            self._acked_speed = None
            self._speed_epoch += 1
            # Nor whether the track has found its zero (S-03): read again.
            self._on_zero = None
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            self._pending = None
            self._target = None
        self._stop_if_moving("the adapter was deactivated")
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            self._pending = None
            self._target = None
        self._stop_if_moving("the adapter is shutting down")
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def stop_before_exit(self) -> tuple[list, float]:
        """Stop the carriage because the PROCESS is ending: SIGINT or SIGTERM.

        rclpy runs no `on_shutdown` when its context goes down, so
        `cite_hardware.process.run` calls this while the context still stands
        and waits on the returned future. The future completes only once a stop
        sent after the last move was ANSWERED is acknowledged (SA2c-S-02 e): a
        move still in flight when the signal came would otherwise reach the
        vendor after the exit stop and drive the carriage on. The bound is twice
        `position_max_age_s` - one for the move in flight to be answered, one
        for the stop after it - the bound this node already applies to an
        unanswered vendor call. Sent whenever a move this adapter sent may still
        be running, whether or not the vendor is seen.
        """
        config, client = self._config, self._stop_client
        with self._lock:
            self._active = False
            self._pending = None
            self._target = None
            moving = self._move_possible or self._set_in_flight
            if moving:
                self._exit_future = Future()
            done = self._exit_future
        if config is None or client is None or not moving or done is None:
            return [], 0.0
        self.get_logger().warning("process ending: set_linear_motor_stop sent before exit")
        self._call_stop()
        return [done], 2.0 * config["position_max_age_s"]

    def _release(self) -> None:
        if self._poll_timer is not None:
            self.destroy_timer(self._poll_timer)
            self._poll_timer = None
        if self._gate is not None:
            self._gate.destroy()
            self._gate = None
        if self._command_subscription is not None:
            self.destroy_subscription(self._command_subscription)
            self._command_subscription = None
        if self._state_publisher is not None:
            self.destroy_lifecycle_publisher(self._state_publisher)
            self._state_publisher = None
        for client in (
            self._set_client,
            self._speed_client,
            self._get_client,
            self._stop_client,
            self._zero_client,
        ):
            if client is not None:
                self.destroy_client(client)
        self._set_client = self._speed_client = self._get_client = self._stop_client = None
        self._zero_client = None
        self._zero_future = None
        self._on_zero = None
        self._position_m = None
        self._get_future = None
        self._get_in_flight = False
        self._stop_future = None
        self._target = None
        self._holding = False
        self._config = None

    # ------------------------------------------------------------------ #
    # Command
    # ------------------------------------------------------------------ #

    def _on_command(self, message: JointTrajectory) -> None:
        config = self._config
        if config is None:
            return
        try:
            target = track_target(message, config["joint"])
        except Refused as error:
            self.get_logger().error(f"track command refused: {error}")
            return

        with self._lock:
            active = self._active
            # Taken at entry, under the lock: a hold that lands while this
            # command is checked below outranks it (SA-S-06).
            accepted_under = self._hold_sequence
        if not active:
            self.get_logger().warning("track command refused: the adapter is not active")
            return
        if target.is_hold:
            # A hold is a stop here, whatever position it names: the simulated
            # controller holds where its own carriage stands, and this one is
            # stopped where it stands (SA2c-S-02 a). Never gated: a stop is
            # what a closed gate would do anyway.
            with self._lock:
                self._target = None
                self._pending = None
                self._holding = True
                self._hold_sequence += 1
            self._stop_if_moving("a hold was commanded")
            return
        assert self._gate is not None
        if not self._gate.permits_motion():
            self.get_logger().warning(
                f"track command refused: {self._gate.why_closed()}"
            )
            return
        try:
            require_within(
                target.position_m, config["position_min_m"], config["position_max_m"]
            )
            # Checked here, once, so no segment of an accepted move can be
            # refused later: below the vendor's slowest speed, or with a
            # segment too short to move the carriage (R-13, SA-S-07).
            vendor_speed(target.speed_mps, config["position_scale"], config["max_speed_mps"])
            require_carried_out(target.speed_mps, config["position_scale"], config["segment_s"])
        except Refused as error:
            self.get_logger().error(f"track command refused: {error}")
            return
        with self._lock:
            position = self._position_m
            position_age_s = (self._steady.now().nanoseconds - self._position_at_ns) * 1e-9
        if position is None:
            self.get_logger().error(
                "track command refused: the carriage position has not been read from "
                f"{config['get_position_service']}, so no segment can be planned"
            )
            return
        if position_age_s > config["position_max_age_s"]:
            self.get_logger().error(
                f"track command refused: the carriage position is {position_age_s:.3f} s old, "
                f"above position_max_age_s {config['position_max_age_s']:g}, so no segment "
                "can be planned from it"
            )
            return
        with self._lock:
            superseded = self._hold_sequence != accepted_under
            if not superseded:
                self._target = target
                self._target_hold = accepted_under
                self._holding = False
        if superseded:
            self.get_logger().warning(
                f"track command to {target.position_m:.4f} m dropped: a hold or vendor "
                "rejection arrived after it"
            )
            return
        self._advance(position)

    def _advance(self, position: float) -> None:
        """Send the next segment of the move in progress, planned from ``position``.

        The last segment is the target itself; after it the move is complete
        here and nothing more is sent for it.
        """
        config = self._config
        if config is None:
            return
        with self._lock:
            target = self._target
            hold = self._target_hold
            if target is None or not self._active:
                return
            goal, last = next_segment(
                position, target.position_m, target.speed_mps, config["segment_s"]
            )
            if last:
                self._target = None
        request = LinearMotorSetPos.Request()
        request.pos = to_vendor_position(goal, config["position_scale"])
        request.speed = vendor_speed(
            target.speed_mps, config["position_scale"], config["max_speed_mps"]
        )
        # Never wait: see the module docstring. The vendor's timeout applies
        # only to a waiting call, so it is left at the vendor's own default.
        request.wait = False
        request.auto_enable = config["auto_enable"]
        self._submit(request, hold)

    def _submit(self, request: LinearMotorSetPos.Request, hold: int) -> None:
        with self._lock:
            # A rejection can land after a segment was planned but before it
            # reached this lock. It must not revive the discarded move.
            superseded = hold != self._hold_sequence
            if not superseded:
                if self._set_in_flight:
                    if self._pending is not None:
                        self.get_logger().info(
                            f"track target {self._pending.pos} superseded by {request.pos} "
                            "before the vendor answered the previous call"
                        )
                    self._pending = request
                    self._pending_hold = hold
                    return
                self._set_in_flight = True
        if superseded:
            self.get_logger().warning(
                f"track segment to {request.pos} dropped: a hold or vendor rejection "
                "arrived after it was planned"
            )
            return
        self._send(request, hold)

    def _send(self, request: LinearMotorSetPos.Request, hold: int) -> None:
        """Send one move, its speed written first unless the vendor acknowledged it (SA-S-03)."""
        with self._lock:
            acknowledged = self._acked_speed
        if request.speed != acknowledged:
            self._send_speed(request, hold)
        else:
            self._send_position(request, hold)

    def _send_speed(self, request: LinearMotorSetPos.Request, hold: int) -> None:
        """Write ``request``'s speed; the move follows only once the vendor answers 0."""
        client = self._speed_client
        assert client is not None
        if not client.service_is_ready():
            self._drop_in_flight(f"{client.srv_name} is not available", request)
            return
        with self._lock:
            active = self._active
            epoch = self._speed_epoch
            if active:
                future = client.call_async(SetInt16.Request(data=request.speed))
        if not active:
            self._drop_in_flight("the adapter is not active", request)
            return
        future.add_done_callback(
            lambda done: self._on_speed_answered(request, hold, done, epoch)
        )

    def _on_speed_answered(
        self, request: LinearMotorSetPos.Request, hold: int, future, epoch: int
    ) -> None:
        error = future.exception()
        response = None if error is not None else future.result()
        if response is None or response.ret != 0:
            self._forget_zero()
            with self._lock:
                # Ends the move as a failed position call does: nothing
                # accepted before this answer is sent after it.
                self._acked_speed = None
                self._hold_sequence += 1
                self._target = None
                self._holding = True
            why = error if error is not None else (
                f"vendor code {response.ret}: {response.message}"
            )
            self._drop_in_flight(
                f"set_linear_motor_speed({request.speed}) failed ({why})", request
            )
            # A segment sent before this write may still be running.
            self._stop_if_moving("a track speed write failed")
            return
        with self._lock:
            # Recorded only if the gate was not found closed since the write
            # was sent (SA R-1): a trip after it may have reset the vendor, and
            # the move behind it is dropped rather than sent at a speed unknown.
            current = epoch == self._speed_epoch
            if current:
                self._acked_speed = request.speed
        if not current:
            self._drop_in_flight(
                f"the gate closed while set_linear_motor_speed({request.speed}) was in flight",
                request,
            )
            return
        self._send_position(request, hold)

    def _drop_in_flight(self, why: str, request: LinearMotorSetPos.Request) -> None:
        """Release the reserved send without moving anything, and drop what was held."""
        with self._lock:
            self._set_in_flight = False
            self._pending = None
        self.get_logger().error(f"track target {request.pos} not sent: {why}")

    def _send_position(self, request: LinearMotorSetPos.Request, hold: int) -> None:
        """Send one move, with the last word on the gate taken under the lock.

        `_move_possible` is set BEFORE that last look (N-04): a closure that
        lands after it either finds the move possible and stops it, or is the
        reason the move is not sent. Either way `_poll` keeps stopping the
        carriage while the gate is closed and a move may be running, so a move
        whose call reaches the vendor after the stop is stopped again.

        A move accepted before the latest hold (``hold`` behind the count) is
        not sent: the hold outranks it (SA-S-06). A move held behind it, if
        any, was accepted later and is sent in its place.
        """
        with self._lock:
            stale = hold != self._hold_sequence
        if stale:
            self._drop_superseded(request)
            return
        assert self._set_client is not None
        if not self._set_client.service_is_ready():
            with self._lock:
                self._set_in_flight = False
                self._pending = None
            self.get_logger().error(
                f"track command refused: {self._set_client.srv_name} is not available"
            )
            return
        gate = self._gate
        with self._lock:
            # Looked at again where the move is sent: a hold that landed since
            # the look above outranks it as surely (SA-S-10).
            stale = hold != self._hold_sequence
            permitted = False
            if not stale:
                self._move_possible = True
                permitted = self._active and gate is not None and gate.permits_motion()
                if permitted:
                    self._move_sequence += 1
                    future = self._set_client.call_async(request)
                else:
                    self._set_in_flight = False
                    self._pending = None
        if stale:
            self._drop_superseded(request)
            return
        if not permitted:
            why = gate.why_closed() if gate is not None else "the adapter is not configured"
            self.get_logger().warning(f"track target {request.pos} not sent: {why}")
            return
        self.get_logger().info(
            f"track to {request.pos} at {request.speed} (vendor units, units/s)"
        )
        future.add_done_callback(lambda done: self._on_set_answered(request, done))

    def _drop_superseded(self, request: LinearMotorSetPos.Request) -> None:
        """Drop a move accepted before the latest hold; send the one held behind it, if any."""
        with self._lock:
            follow = self._pending if self._active else None
            follow_hold = self._pending_hold
            self._pending = None
            self._set_in_flight = follow is not None
        self.get_logger().warning(
            f"track target {request.pos} dropped: a hold or vendor rejection arrived after it"
        )
        if follow is not None:
            self._send(follow, follow_hold)

    def _on_set_answered(self, request: LinearMotorSetPos.Request, future) -> None:
        error = future.exception()
        response = None if error is not None else future.result()
        failed = response is None or response.ret != 0
        if failed:
            self._forget_zero()
        with self._lock:
            if failed:
                # Abort the entire accepted pipeline, including a successor
                # queued before this answer. Invalidate segments and commands
                # concurrently being checked before they can reintroduce it.
                self._hold_sequence += 1
                self._target = None
                self._pending = None
                self._holding = True
            follow = self._pending if self._active else None
            follow_hold = self._pending_hold
            self._pending = None
            self._set_in_flight = follow is not None
            stopping = not self._active or self._holding
        if error is not None:
            self.get_logger().error(f"set_linear_motor_pos({request.pos}) failed: {error}")
        elif response is None:
            self.get_logger().error(f"set_linear_motor_pos({request.pos}) returned no response")
        elif response.ret != 0:
            self.get_logger().error(
                f"set_linear_motor_pos({request.pos}) returned vendor code {response.ret}: "
                f"{response.message}"
            )
        if follow is None:
            if stopping:
                # Answered after the carriage was told to stop: a stop sent
                # from now on is processed after this move (SA2c-S-02 e).
                self._stop_if_moving("a move was answered after the stop was asked for")
            return
        assert self._gate is not None
        if not self._gate.permits_motion():
            with self._lock:
                self._set_in_flight = False
            self.get_logger().warning(
                f"held track target {follow.pos} dropped: {self._gate.why_closed()}"
            )
            return
        self._send(follow, follow_hold)

    def _stop_if_moving(self, reason: str, repeated: bool = False) -> None:
        """Stop the carriage if a move this adapter sent may still be running.

        ``repeated`` is the poll's level-triggered stop, said in the log at
        most every five seconds; every other caller is an event, said each time.
        """
        with self._lock:
            moving = self._move_possible or self._set_in_flight
        if not moving:
            return
        if repeated:
            self.get_logger().warning(f"track stop: {reason}", throttle_duration_sec=5.0)
        else:
            self.get_logger().warning(f"track stop: {reason}")
        self._call_stop()

    def _call_stop(self) -> None:
        """Send `set_linear_motor_stop` unless one is already in flight and in time."""
        config, client = self._config, self._stop_client
        if config is None or client is None:
            return
        now = self._steady.now().nanoseconds
        with self._lock:
            overdue = None
            if self._stop_future is not None:
                if now <= self._stop_deadline_ns:
                    return
                overdue, self._stop_future = self._stop_future, None
        if overdue is not None:
            client.remove_pending_request(overdue)
            overdue.cancel()
            self.get_logger().error(
                "set_linear_motor_stop unanswered within position_max_age_s; sent again",
                throttle_duration_sec=5.0,
            )
        if not client.service_is_ready():
            self.get_logger().error(
                f"track stop could not be sent: {client.srv_name} is not available; "
                "sent again on the next poll",
                throttle_duration_sec=5.0,
            )
            return
        with self._lock:
            if self._stop_future is not None:
                return  # another poll sent one meanwhile
            future = client.call_async(Call.Request())
            self._stop_future = future
            self._stop_sequence = self._move_sequence
            self._stop_after_answer = not self._set_in_flight
            self._stop_deadline_ns = now + int(config["position_max_age_s"] * 1e9)
        future.add_done_callback(self._on_stop_answered)

    def _on_stop_answered(self, future) -> None:
        with self._lock:
            if self._stop_future is not future:
                return  # abandoned at its deadline, or the node was cleaned up
            self._stop_future = None
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            self._forget_zero()
            self.get_logger().error(f"set_linear_motor_stop failed: {error}")
            return
        if future.result().ret != 0:
            self._forget_zero()
            self.get_logger().error(
                f"set_linear_motor_stop returned vendor code {future.result().ret}; "
                "sent again on the next poll"
            )
            return
        # N-05 and SA2c-S-02 e: only an acknowledged stop, sent after the last
        # move was answered and with no move call outstanding since, says the
        # carriage is no longer driven by us.
        with self._lock:
            if (
                self._stop_sequence == self._move_sequence
                and self._stop_after_answer
                and not self._set_in_flight
            ):
                self._move_possible = False
            done = None if self._move_possible else self._exit_future
        if done is not None and not done.done():
            done.set_result(True)

    def _on_gate_closed(self, reason: str) -> None:
        # Whatever is held is dropped, and a move that may be running is
        # stopped here: the deadman stops the carriage on its own trip, but a
        # closure it did not cause — its state gone stale, a second deadman —
        # has only this stop.
        with self._lock:
            dropped = self._pending
            self._pending = None
            self._target = None
            # A trip or an E-stop may leave the vendor at another speed: the
            # next move writes its own again (SA-S-09).
            self._acked_speed = None
            self._speed_epoch += 1
        if dropped is not None:
            self.get_logger().warning(f"held track target {dropped.pos} dropped: {reason}")
        self._stop_if_moving(f"the deadman gate closed: {reason}")

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def _poll(self) -> None:
        gate = self._gate
        if gate is not None:
            gate.check()
        config = self._config
        if config is None:
            return
        # Level-triggered, not only on the gate's closing edge (N-04, N-05):
        # whenever motion is not permitted and a move may be running, the
        # carriage is stopped, on every poll until the vendor acknowledges it.
        with self._lock:
            active = self._active
            holding = self._holding
        if not active:
            self._stop_if_moving("the adapter is not active", repeated=True)
        elif gate is None or not gate.permits_motion():
            with self._lock:
                self._target = None
                self._acked_speed = None
                self._speed_epoch += 1
            why = gate.why_closed() if gate is not None else "no deadman gate"
            self._stop_if_moving(f"motion is not permitted: {why}", repeated=True)
        elif holding:
            self._stop_if_moving("a hold was commanded", repeated=True)
        self._read_zero_if_unknown(config)
        now = self._steady.now().nanoseconds
        overdue = None
        with self._lock:
            if not self._active:
                return
            if self._get_in_flight:
                if now <= self._get_deadline_ns:
                    return
                overdue, self._get_future = self._get_future, None
                self._position_m = None
            # Reserved, with its deadline, before it is sent (N-09): a second
            # poll running on the reentrant group sees it and sends nothing.
            self._get_in_flight = True
            self._get_deadline_ns = now + int(config["position_max_age_s"] * 1e9)
        assert self._get_client is not None
        if overdue is not None:
            self._get_client.remove_pending_request(overdue)
            overdue.cancel()
            self.get_logger().error(
                "get_linear_motor_pos unanswered within position_max_age_s; abandoned",
                throttle_duration_sec=5.0,
            )
        if not self._get_client.service_is_ready():
            with self._lock:
                self._get_in_flight = False
                self._position_m = None
            self.get_logger().warning(
                f"track position unread: {self._get_client.srv_name} is not available",
                throttle_duration_sec=5.0,
            )
            return
        with self._lock:
            future = self._get_client.call_async(GetInt16.Request())
            self._get_future = future
        future.add_done_callback(self._on_position)

    def _on_position(self, future) -> None:
        with self._lock:
            if self._get_future is not future:
                return  # abandoned at its deadline, or the node was cleaned up
            self._get_future = None
            self._get_in_flight = False
        if future.cancelled():
            return
        config = self._config
        error = future.exception()
        response = None if error is not None else future.result()
        if config is None or response is None or response.ret != 0:
            self._forget_zero()
            with self._lock:
                self._position_m = None
            detail = error if error is not None else (
                f"vendor code {response.ret}" if response is not None else "unconfigured"
            )
            self.get_logger().error(
                f"get_linear_motor_pos failed ({detail}); no track position is published "
                "rather than a stale one",
                throttle_duration_sec=5.0,
            )
            return
        position = from_vendor_position(response.data, config["position_scale"])
        with self._lock:
            self._position_m = position
            self._position_at_ns = self._steady.now().nanoseconds
            on_zero = self._on_zero
        publisher = self._state_publisher
        if on_zero is not True:
            # S-03: no place on the track until it has found its zero.
            self.get_logger().warning(
                f"{config['joint']} is not published: the track has not been read as on its "
                "zero (get_linear_motor_on_zero)",
                throttle_duration_sec=5.0,
            )
        elif publisher is not None:
            message = JointState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.name = [config["joint"]]
            message.position = [position]
            publisher.publish(message)
        # The next segment of a move in progress, from this fresh position,
        # only while motion is permitted (SA2c-S-02 d).
        gate = self._gate
        if gate is not None and gate.permits_motion():
            self._advance(position)

    # ------------------------------------------------------------------ #
    # Zero (S-03)
    # ------------------------------------------------------------------ #

    def _forget_zero(self) -> None:
        """After a vendor error, whether the track is on its zero is read again."""
        with self._lock:
            self._on_zero = None

    def _read_zero_if_unknown(self, config: dict) -> None:
        """Read `get_linear_motor_on_zero` while the track is not known to be on its zero.

        One read at a time; one unanswered within `position_max_age_s` is
        abandoned and sent again on the next poll, as a position read is.
        """
        now = self._steady.now().nanoseconds
        overdue = None
        with self._lock:
            if not self._active or self._on_zero is True:
                return
            if self._zero_future is not None:
                if now <= self._zero_deadline_ns:
                    return
                overdue, self._zero_future = self._zero_future, None
        client = self._zero_client
        if client is None:
            return
        if overdue is not None:
            client.remove_pending_request(overdue)
            overdue.cancel()
        if not client.service_is_ready():
            self.get_logger().warning(
                f"whether the track is on its zero is unread: {client.srv_name} is not "
                "available, so no track position is published",
                throttle_duration_sec=5.0,
            )
            return
        with self._lock:
            future = client.call_async(GetInt16.Request())
            self._zero_future = future
            self._zero_deadline_ns = now + int(config["position_max_age_s"] * 1e9)
        future.add_done_callback(self._on_zero_answered)

    def _on_zero_answered(self, future) -> None:
        with self._lock:
            if self._zero_future is not future:
                return  # abandoned at its deadline, or the node was cleaned up
            self._zero_future = None
        if future.cancelled():
            return
        error = future.exception()
        response = None if error is not None else future.result()
        if response is None or response.ret != 0:
            detail = error if error is not None else f"vendor code {response.ret}"
            self.get_logger().error(
                f"get_linear_motor_on_zero failed ({detail}); read again on the next poll",
                throttle_duration_sec=5.0,
            )
            return
        on_zero = response.data == 1
        with self._lock:
            before, self._on_zero = self._on_zero, on_zero
        if on_zero and before is not True:
            self.get_logger().info("the track is on its zero: its position is published")
        elif not on_zero:
            self.get_logger().error(
                "the track has not found its zero (get_linear_motor_on_zero = "
                f"{response.data}): no position is published until it has - initialize it "
                "(Start robot)",
                throttle_duration_sec=5.0,
            )


def main() -> int:
    return run(TrackAdapter)


if __name__ == "__main__":
    sys.exit(main())
