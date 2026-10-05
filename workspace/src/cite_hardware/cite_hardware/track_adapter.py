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
  An empty trajectory is a stop, as it is to the simulated controller, and
  calls `set_linear_motor_stop`.
- **State.** It polls `get_linear_motor_pos` and publishes the track joint's
  position on the arm's joint-state topic, where the simulated side's
  `joint_state_broadcaster` publishes it. The program reads arrival from there.

**It never commands motion while not ACTIVE, and never while the deadman does
not permit it** (`cite_hardware.gate`). A stop is not motion and is never
gated.

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
    STOP,
    to_vendor_position,
    track_target,
    vendor_speed,
)
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.qos import COMMAND, STATE
from rclpy.callback_groups import ReentrantCallbackGroup
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
        self._set_in_flight = False
        self._get_in_flight = False
        self._pending: LinearMotorSetPos.Request | None = None

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
            self, config["deadman_state_topic"], self._group, self._on_gate_closed
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
        self._poll_timer = self.create_timer(
            self._config["poll_period_s"], self._poll, callback_group=self._group
        )
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            self._pending = None
        if self._poll_timer is not None:
            self.destroy_timer(self._poll_timer)
            self._poll_timer = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            self._pending = None
        self._release()
        return TransitionCallbackReturn.SUCCESS

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
        if target == STOP:
            # Never gated: a stop is not motion. Whatever was held is dropped
            # with it, so the stop is not followed by the move it stopped.
            with self._lock:
                self._pending = None
            self._call_stop()
            return

        with self._lock:
            active = self._active
            position = self._position_m
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
        assert self._set_client is not None
        if not self._set_client.service_is_ready():
            with self._lock:
                self._set_in_flight = False
                self._pending = None
            self.get_logger().error(
                f"track command refused: {self._set_client.srv_name} is not available"
            )
            return
        self.get_logger().info(
            f"track to {request.pos} at {request.speed} (vendor units, units/s)"
        )
        future = self._set_client.call_async(request)
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

    def _call_stop(self) -> None:
        if self._stop_client is None:
            return
        if not self._stop_client.service_is_ready():
            self.get_logger().error(
                f"track stop could not be sent: {self._stop_client.srv_name} is not available"
            )
            return
        self.get_logger().info("track stop")
        future = self._stop_client.call_async(Call.Request())
        future.add_done_callback(self._on_stop_answered)

    def _on_stop_answered(self, future) -> None:
        error = future.exception()
        if error is not None:
            self.get_logger().error(f"set_linear_motor_stop failed: {error}")
        elif future.result().ret != 0:
            self.get_logger().error(
                f"set_linear_motor_stop returned vendor code {future.result().ret}"
            )

    def _on_gate_closed(self, reason: str) -> None:
        # Only what is held here is dropped. The deadman stops the carriage
        # itself; a second stop from this node would race it for nothing.
        with self._lock:
            dropped = self._pending
            self._pending = None
        if dropped is not None:
            self.get_logger().warning(f"held track target {dropped.pos} dropped: {reason}")

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def _poll(self) -> None:
        with self._lock:
            if not self._active or self._get_in_flight:
                return
            self._get_in_flight = True
        assert self._get_client is not None
        if not self._get_client.service_is_ready():
            with self._lock:
                self._get_in_flight = False
                self._position_m = None
            self.get_logger().warning(
                f"track position unread: {self._get_client.srv_name} is not available",
                throttle_duration_sec=5.0,
            )
            return
        future = self._get_client.call_async(GetInt16.Request())
        future.add_done_callback(self._on_position)

    def _on_position(self, future) -> None:
        config = self._config
        error = future.exception()
        response = None if error is not None else future.result()
        if config is None or response is None or response.ret != 0:
            with self._lock:
                self._get_in_flight = False
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
            self._get_in_flight = False
            self._position_m = position
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
