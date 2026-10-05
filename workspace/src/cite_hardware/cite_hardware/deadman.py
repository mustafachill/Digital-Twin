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

"""A physical side's deadman on the twin boundary's heartbeat (ADR-0070 item 5).

cross-cutting-safety.md: *"When the commanding node dies, the network stalls, or
messages simply stop, motion stops. It does not continue on the last command.
Every command path has a deadman with a bounded timeout."* On a physical side
the commanding node is the twin boundary, which reaches this side over a link
the project does not control (ADR-0070: Wi-Fi), and open-work #74 records that
nothing watched it.

**What it watches.** `TwinHeartbeat` on its own domain, published by the
boundary from a timer that side's executor runs. The decision is
`cite_hardware.liveness`'s and is not restated here.

**What a trip does**, all of it asynchronous and none of it waited on:

1. ``set_state`` with the vendor's STOP state, which stops the arm on the
   controller itself rather than asking a controller in this process to
   (`xarm_sdk` `xarm_api.h`, `set_state`: "4: stop state").
2. ``set_linear_motor_stop``, which stops the carriage.
3. A cancel of EVERY goal on each named action — the gripper relay's and the
   arm trajectory controller's — through the action protocol's own cancel
   service with a zero goal id and a zero stamp, which `action_msgs/CancelGoal`
   defines as "cancel all goals".
4. An empty trajectory on each named `joint_trajectory` topic, which a
   `joint_trajectory_controller` takes as "stop and hold where you are".

A vendor call that fails or is not answered is re-issued on every timeout
period while the trip stands, until the vendor acknowledges it. That is not a
wait and nothing is sequenced on it; it is the trip refusing to be lost.

**Latched.** A trip clears only by a deliberate deactivate and activate, never
by heartbeats resuming. The relays read the published `DeadmanState` and refuse
motion in every state but HEALTHY, which covers the time before the first
heartbeat as well.

**Its clock is the steady clock, and `use_sim_time` is refused.** It times a
network link on real hardware: simulated time is the wrong instrument, and a
deadman whose timer waited on a `/clock` nobody publishes would never trip.
The twin boundary refuses `use_sim_time` for the same kind of reason, and this
refuses it the same way rather than quietly ignoring it.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
import threading

from action_msgs.srv import CancelGoal
from cite_hardware.liveness import Liveness, STATE_NAMES, TRIPPED
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.msg import DeadmanState, TwinHeartbeat
from cite_interfaces.qos import COMMAND, LATCHED, STATE
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.event_handler import SubscriptionEventCallbacks
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from trajectory_msgs.msg import JointTrajectory
from xarm_msgs.srv import Call, SetInt16

NODE_NAME = "deadman"

#: The vendor's STOP state for `set_state`. A constant of the vendor's API, not
#: a fact of the asset: `xarm_sdk/cxx/include/xarm/wrapper/xarm_api.h`, the
#: documentation of `set_state` ("4: stop state").
VENDOR_STATE_STOP = 4

SPECS: tuple[Spec, ...] = (
    Spec("zone", Parameter.Type.STRING, "the zone whose boundary's heartbeat is watched"),
    Spec("asset_id", Parameter.Type.STRING, "the arm whose side this deadman guards"),
    Spec(
        "timeout_s",
        Parameter.Type.DOUBLE,
        "the heartbeat timeout, steady-clock seconds; declared in L0 above the link's "
        "observed spikes",
        positive=True,
    ),
    Spec(
        "state_topic",
        Parameter.Type.STRING,
        "where this deadman publishes its DeadmanState, latched",
    ),
    Spec(
        "set_state_service",
        Parameter.Type.STRING,
        "the vendor's set_state service (xarm_msgs/SetInt16)",
    ),
    Spec(
        "linear_motor_stop_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_stop service (xarm_msgs/Call)",
    ),
    Spec(
        "cancel_actions",
        Parameter.Type.STRING_ARRAY,
        "the actions whose every goal is cancelled on a trip",
    ),
    Spec(
        "stop_trajectory_topics",
        Parameter.Type.STRING_ARRAY,
        "the joint_trajectory topics an empty trajectory is published on at a trip",
    ),
)


@dataclass
class _StopCall:
    """One vendor or protocol call a trip makes, and whether it has landed."""

    label: str
    client: object
    request: object
    in_flight: bool = False
    acknowledged: bool = False


class Deadman(LifecycleNode):
    def __init__(self, **node_options) -> None:
        # `node_options` reach `rclpy.node.Node` unchanged; a test hands its
        # parameter overrides in through them rather than through a launch.
        super().__init__(NODE_NAME, **node_options)
        self._required = RequiredParameters(self, SPECS)
        self._lock = threading.Lock()
        # One mutually exclusive group for every callback: heartbeats, the
        # timer, the matched event and the lifecycle-independent handlers all
        # touch the state machine, and none of them blocks, so serialising
        # them costs nothing and removes every interleaving.
        self._group = MutuallyExclusiveCallbackGroup()
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self._config: dict | None = None
        self._liveness: Liveness | None = None
        self._state_publisher = None
        self._heartbeats = None
        self._timer = None
        self._stops: list[_StopCall] = []
        self._trajectory_publishers = []
        self._clients = []

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        if self.get_parameter("use_sim_time").value:
            self.get_logger().error(
                "cannot configure: use_sim_time is set, and this deadman times a network "
                "link on the steady clock (see the module docstring)"
            )
            return TransitionCallbackReturn.FAILURE
        try:
            config = self._required.read()
            liveness = Liveness(config["zone"], config["timeout_s"])
        except (ParameterError, ValueError) as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        self._config = config
        self._liveness = liveness

        # A plain publisher, not a lifecycle one: INACTIVE has to be said
        # while inactive. LATCHED so a relay starting later hears the current
        # state at once.
        self._state_publisher = self.create_publisher(
            DeadmanState, config["state_topic"], LATCHED
        )
        set_state = self.create_client(
            SetInt16, config["set_state_service"], callback_group=self._group
        )
        linear_stop = self.create_client(
            Call, config["linear_motor_stop_service"], callback_group=self._group
        )
        stop_request = SetInt16.Request()
        stop_request.data = VENDOR_STATE_STOP
        self._clients = [set_state, linear_stop]
        stops = [
            _StopCall("set_state(stop)", set_state, stop_request),
            _StopCall("set_linear_motor_stop", linear_stop, Call.Request()),
        ]
        for action in config["cancel_actions"]:
            client = self.create_client(
                CancelGoal, f"{action}/_action/cancel_goal", callback_group=self._group
            )
            self._clients.append(client)
            # A default-constructed request is a zero goal id and a zero stamp:
            # "cancel all goals" in action_msgs/srv/CancelGoal.
            stops.append(_StopCall(f"cancel all goals on {action}", client, CancelGoal.Request()))
        self._stops = stops
        # COMMAND is the profile every trajectory command in this system is
        # published with (the program, the twin boundary).
        self._trajectory_publishers = [
            self.create_publisher(JointTrajectory, topic, COMMAND)
            for topic in config["stop_trajectory_topics"]
        ]
        # STATE is the boundary's heartbeat profile. The matched event is what
        # says the publisher went away; a timeout alone would say it too, but
        # later.
        self._heartbeats = self.create_subscription(
            TwinHeartbeat,
            TwinHeartbeat.TOPIC,
            self._on_heartbeat,
            STATE,
            callback_group=self._group,
            event_callbacks=SubscriptionEventCallbacks(matched=self._on_matched),
        )
        self.get_logger().info(
            f"configured: zone {config['zone']!r}, timeout {config['timeout_s']:g} s, "
            f"{len(self._stops)} stop call(s), "
            f"{len(self._trajectory_publishers)} trajectory topic(s)"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        assert self._liveness is not None and self._config is not None
        with self._lock:
            self._liveness.activate()
            for stop in self._stops:
                stop.in_flight = False
                stop.acknowledged = False
        self._timer = self.create_timer(
            self._config["timeout_s"],
            self._on_timer,
            callback_group=self._group,
            clock=self._steady,
        )
        self._publish_state()
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        if self._timer is not None:
            self.destroy_timer(self._timer)
            self._timer = None
        if self._liveness is not None:
            with self._lock:
                self._liveness.deactivate()
            self._publish_state()
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        if self._liveness is not None:
            with self._lock:
                self._liveness.deactivate()
            self._publish_state()
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def _release(self) -> None:
        if self._timer is not None:
            self.destroy_timer(self._timer)
            self._timer = None
        if self._heartbeats is not None:
            self.destroy_subscription(self._heartbeats)
            self._heartbeats = None
        for publisher in self._trajectory_publishers:
            self.destroy_publisher(publisher)
        self._trajectory_publishers = []
        for client in self._clients:
            self.destroy_client(client)
        self._clients = []
        self._stops = []
        if self._state_publisher is not None:
            self.destroy_publisher(self._state_publisher)
            self._state_publisher = None
        self._liveness = None
        self._config = None

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #

    def _on_heartbeat(self, message: TwinHeartbeat) -> None:
        if self._liveness is None:
            return
        with self._lock:
            before = self._liveness.state
            outcome = self._liveness.heartbeat(message.zone, message.sequence)
            after = self._liveness.state
        if not outcome.accepted:
            if before not in (TRIPPED,):
                self.get_logger().warning(outcome.reason, throttle_duration_sec=5.0)
            return
        # The timeout runs from the last FRESH heartbeat.
        if self._timer is not None:
            self._timer.reset()
        if after != before:
            self.get_logger().info(outcome.reason)
            self._publish_state()

    def _on_timer(self) -> None:
        if self._liveness is None:
            return
        with self._lock:
            outcome = self._liveness.expired()
            tripped_already = self._liveness.state == TRIPPED and not outcome.tripped
        if outcome.tripped:
            self._trip(outcome.reason)
        elif tripped_already:
            self._issue_stops()

    def _on_matched(self, status) -> None:
        if status.current_count > 0 or self._liveness is None:
            return
        with self._lock:
            outcome = self._liveness.publisher_lost()
        if outcome.tripped:
            self._trip(outcome.reason)

    # ------------------------------------------------------------------ #
    # The trip
    # ------------------------------------------------------------------ #

    def _trip(self, reason: str) -> None:
        self.get_logger().error(reason)
        self._publish_state()
        for publisher in self._trajectory_publishers:
            if publisher.get_subscription_count() == 0:
                self.get_logger().warning(
                    f"stop trajectory on {publisher.topic_name}: nothing is subscribed"
                )
            publisher.publish(JointTrajectory())
        self._issue_stops()

    def _issue_stops(self) -> None:
        for stop in self._stops:
            with self._lock:
                if stop.acknowledged or stop.in_flight:
                    continue
                ready = stop.client.service_is_ready()
                stop.in_flight = ready
            if not ready:
                self.get_logger().error(
                    f"trip: {stop.label} not sent, {stop.client.srv_name} is not available; "
                    "re-issued every timeout period until it lands",
                    throttle_duration_sec=5.0,
                )
                continue
            future = stop.client.call_async(stop.request)
            future.add_done_callback(lambda done, stop=stop: self._on_stop_answered(stop, done))

    def _on_stop_answered(self, stop: _StopCall, future) -> None:
        error = future.exception()
        response = None if error is not None else future.result()
        # A vendor call reports success as `ret == 0`. A cancel is answered with
        # a return code that is not a failure of the stop when there was
        # simply nothing to cancel, so any answer at all acknowledges it.
        code = getattr(response, "ret", 0) if response is not None else None
        landed = response is not None and (isinstance(response, CancelGoal.Response) or code == 0)
        with self._lock:
            stop.in_flight = False
            stop.acknowledged = landed
            everything = all(each.acknowledged for each in self._stops)
        if landed:
            self.get_logger().info(f"trip: {stop.label} acknowledged")
        else:
            self.get_logger().error(
                f"trip: {stop.label} did not land ({error if error else f'vendor code {code}'}); "
                "re-issued at the next timeout period"
            )
        if everything:
            self._publish_state(suffix="; every stop call acknowledged")

    def _publish_state(self, suffix: str = "") -> None:
        publisher = self._state_publisher
        config = self._config
        liveness = self._liveness
        if publisher is None or config is None or liveness is None:
            return
        with self._lock:
            message = DeadmanState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.asset_id = config["asset_id"]
            message.state = liveness.state
            message.timeout_s = liveness.timeout_s
            message.last_sequence = liveness.last_sequence
            message.detail = liveness.detail + suffix
        publisher.publish(message)
        self.get_logger().info(
            f"deadman {STATE_NAMES[message.state]}: {message.detail}"
        )


def main() -> int:
    return run(Deadman)


if __name__ == "__main__":
    sys.exit(main())
