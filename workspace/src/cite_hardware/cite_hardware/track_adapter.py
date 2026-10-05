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
  serves, takes the trajectory's FINAL point — the program sends exactly one
  (ADR-0067) — and calls `set_linear_motor_pos` with the position in the
  vendor's unit and the speed that reaches it in the point's `time_from_start`.
  A trajectory with no points is refused, as the simulated controller refuses
  it (`joint_trajectory_controller` 4.x); it is not a stop there either.
- **State.** It polls `get_linear_motor_pos` and publishes the track joint's
  position on the arm's joint-state topic, where the simulated side's
  `joint_state_broadcaster` publishes it. The program reads arrival from there.

**It never commands motion while not ACTIVE, and never while the deadman does
not permit it** (`cite_hardware.gate`). **It stops the carriage itself** with
`set_linear_motor_stop` when its gate closes for any reason — the deadman's
trip, the deadman's state going stale, a second deadman — and on deactivate and
shutdown, whenever a `set_linear_motor_pos` was in flight or a move it sent may
still be running. The deadman's own stop on a trip is the second, independent
one; a closure the deadman did not cause has only this one.

That stop is LEVEL-triggered: on every poll, active or not, while motion is not
permitted and a move may be running, it is sent again until the vendor answers
one with success that was sent after the last move and with no move call
outstanding — only then is the carriage taken as no longer driven from here. A
stop unanswered within `position_max_age_s` is abandoned and sent again. A move
is marked possible BEFORE the last look at the gate, under the lock, so a
closure racing a move either prevents it or finds it and stops it. On SIGINT
or SIGTERM the stop is sent before the process exits (`cite_hardware.process`).

**A speed is derived only from a fresh position.** The carriage position is
polled; a read unanswered within `position_max_age_s` is abandoned, and a
position older than that is not used to derive a speed.

**The vendor call is never waited on.** `set_linear_motor_pos` is called with
`wait=false`, and that is load-bearing rather than a preference: the vendor's
driver serves every one of its services from one single-threaded executor
(`xarm_controller/src/hardware/uf_robot_system_hardware.cpp`, `rclcpp::spin`
of the driver node), so a waiting position call would hold that executor for
the whole move — and the deadman's `set_linear_motor_stop` and `set_state`
would queue behind it.

**Preemption.** A new command retargets the carriage: the vendor takes a new
position while moving. A command that arrives while the previous vendor call
has not yet answered is held, and replaced by any later one, so the vendor
receives the latest target and never a backlog.
"""

from __future__ import annotations

import sys
import threading

from cite_hardware.gate import DeadmanGate
from cite_hardware.mapping import (
    from_vendor_position,
    Refused,
    require_within,
    to_vendor_position,
    track_target,
    vendor_speed,
)
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.qos import COMMAND, STATE
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory
from xarm_msgs.srv import Call, GetInt16, LinearMotorSetPos

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
        "steady-clock bound on a carriage position used to derive a speed, and on an "
        "unanswered position read",
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
        self._get_client = None
        self._stop_client = None
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
        self._get_client = self.create_client(
            GetInt16, config["get_position_service"], callback_group=self._group
        )
        self._stop_client = self.create_client(
            Call, config["stop_service"], callback_group=self._group
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
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            self._pending = None
        self._stop_if_moving("the adapter was deactivated")
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            self._pending = None
        self._stop_if_moving("the adapter is shutting down")
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def stop_before_exit(self) -> tuple[list, float]:
        """Stop the carriage because the PROCESS is ending: SIGINT or SIGTERM.

        rclpy runs no `on_shutdown` when its context goes down, so
        `cite_hardware.process.run` calls this while the context still stands
        and waits on the returned future for at most `position_max_age_s`, the
        bound this node already applies to an unanswered vendor call. Sent
        whenever a move this adapter sent may still be running, whether or not
        the vendor is seen.
        """
        config, client = self._config, self._stop_client
        with self._lock:
            self._active = False
            self._pending = None
            moving = self._move_possible or self._set_in_flight
        if config is None or client is None or not moving:
            return [], 0.0
        self.get_logger().warning("process ending: set_linear_motor_stop sent before exit")
        return [client.call_async(Call.Request())], config["position_max_age_s"]

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
        for client in (self._set_client, self._get_client, self._stop_client):
            if client is not None:
                self.destroy_client(client)
        self._set_client = self._get_client = self._stop_client = None
        self._position_m = None
        self._get_future = None
        self._get_in_flight = False
        self._stop_future = None
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
            position = self._position_m
            position_age_s = (self._steady.now().nanoseconds - self._position_at_ns) * 1e-9
        if not active:
            self.get_logger().warning("track command refused: the adapter is not active")
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
        except Refused as error:
            self.get_logger().error(f"track command refused: {error}")
            return
        if position is None:
            self.get_logger().error(
                "track command refused: the carriage position has not been read from "
                f"{config['get_position_service']}, so no speed can be derived"
            )
            return
        if position_age_s > config["position_max_age_s"]:
            self.get_logger().error(
                f"track command refused: the carriage position is {position_age_s:.3f} s old, "
                f"above position_max_age_s {config['position_max_age_s']:g}, so no speed "
                "can be derived from it"
            )
            return

        request = LinearMotorSetPos.Request()
        request.pos = to_vendor_position(target.position_m, config["position_scale"])
        request.speed = vendor_speed(
            target.position_m - position,
            target.seconds,
            config["position_scale"],
            config["max_speed_mps"],
        )
        # Never wait: see the module docstring. The vendor's timeout applies
        # only to a waiting call, so it is left at the vendor's own default.
        request.wait = False
        request.auto_enable = config["auto_enable"]
        self._submit(request)

    def _submit(self, request: LinearMotorSetPos.Request) -> None:
        with self._lock:
            if self._set_in_flight:
                if self._pending is not None:
                    self.get_logger().info(
                        f"track target {self._pending.pos} superseded by {request.pos} "
                        "before the vendor answered the previous call"
                    )
                self._pending = request
                return
            self._set_in_flight = True
        self._send(request)

    def _send(self, request: LinearMotorSetPos.Request) -> None:
        """Send one move, with the last word on the gate taken under the lock.

        `_move_possible` is set BEFORE that last look (N-04): a closure that
        lands after it either finds the move possible and stops it, or is the
        reason the move is not sent. Either way `_poll` keeps stopping the
        carriage while the gate is closed and a move may be running, so a move
        whose call reaches the vendor after the stop is stopped again.
        """
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
            self._move_possible = True
            permitted = self._active and gate is not None and gate.permits_motion()
            if permitted:
                self._move_sequence += 1
                future = self._set_client.call_async(request)
            else:
                self._set_in_flight = False
                self._pending = None
        if not permitted:
            why = gate.why_closed() if gate is not None else "the adapter is not configured"
            self.get_logger().warning(f"track target {request.pos} not sent: {why}")
            return
        self.get_logger().info(
            f"track to {request.pos} at {request.speed} (vendor units, units/s)"
        )
        future.add_done_callback(lambda done: self._on_set_answered(request, done))

    def _on_set_answered(self, request: LinearMotorSetPos.Request, future) -> None:
        error = future.exception()
        if error is not None:
            self.get_logger().error(f"set_linear_motor_pos({request.pos}) failed: {error}")
        elif future.result().ret != 0:
            response = future.result()
            self.get_logger().error(
                f"set_linear_motor_pos({request.pos}) returned vendor code {response.ret}: "
                f"{response.message}"
            )
        with self._lock:
            follow = self._pending if self._active else None
            self._pending = None
            self._set_in_flight = follow is not None
        if follow is None:
            return
        assert self._gate is not None
        if not self._gate.permits_motion():
            with self._lock:
                self._set_in_flight = False
            self.get_logger().warning(
                f"held track target {follow.pos} dropped: {self._gate.why_closed()}"
            )
            return
        self._send(follow)

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
            self.get_logger().error(f"set_linear_motor_stop failed: {error}")
            return
        if future.result().ret != 0:
            self.get_logger().error(
                f"set_linear_motor_stop returned vendor code {future.result().ret}; "
                "sent again on the next poll"
            )
            return
        # N-05: only an acknowledged stop, sent after the last move and with no
        # move call outstanding, says the carriage is no longer driven by us.
        with self._lock:
            if self._stop_sequence == self._move_sequence and not self._set_in_flight:
                self._move_possible = False

    def _on_gate_closed(self, reason: str) -> None:
        # Whatever is held is dropped, and a move that may be running is
        # stopped here: the deadman stops the carriage on its own trip, but a
        # closure it did not cause — its state gone stale, a second deadman —
        # has only this stop.
        with self._lock:
            dropped = self._pending
            self._pending = None
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
        if not active:
            self._stop_if_moving("the adapter is not active", repeated=True)
        elif gate is None or not gate.permits_motion():
            why = gate.why_closed() if gate is not None else "no deadman gate"
            self._stop_if_moving(f"motion is not permitted: {why}", repeated=True)
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
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = [config["joint"]]
        message.position = [position]
        publisher = self._state_publisher
        if publisher is not None:
            publisher.publish(message)


def main() -> int:
    return run(TrackAdapter)


if __name__ == "__main__":
    sys.exit(main())
