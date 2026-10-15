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
the commanding node is the twin boundary, and open-work #74 records that
nothing watched it.

**What it watches, and what it does not.** `TwinHeartbeat` on its own domain,
published by the boundary PROCESS from a timer the executor serving this side
runs. A heartbeat that stops says the boundary process, or its executor, or the
DDS path from it to this node, stopped. It says nothing about the Ethernet or
Wi-Fi link between the vendor driver and the arm's controller: that link is the
vendor's, inside the vendor plugin, and its loss is the vendor's to detect
(`uf_robot_system_hardware.cpp` `read`, `ROBOT_IS_DISCONNECTED`). The decision
is `cite_hardware.liveness`'s and is not restated here.

**The arm is held stopped through the vendor's own state, whenever this deadman
is not HEALTHY.** The vendor plugin streams servo commands only while the arm
is in a state at or below 2 and in the servo (or joint-velocity) mode;
otherwise its `write` deactivates every controller and streams nothing
(`xarm_controller/src/hardware/uf_robot_system_hardware.cpp:339-344`, the
readiness test at `:464-502`). So, on every tick of a steady-clock timer, in
every state but HEALTHY — before activation, AWAITING, HELD, TRIPPED, INACTIVE
after a deactivate — it calls `set_state` with the vendor's STOP state (4).
Every tick and regardless of the last answer: a re-enable by UFACTORY Studio,
the pendant or any other client is undone within one tick. The plugin's own
`on_activate` sets the arm to START (`:248-254`), which is why activation is
followed at once by a STOP here; the owner accepted that brief energizing at
every connect rather than patch the vendor (ADR-0076, "What this costs us").

**A heartbeat holds; only the operator releases (ADR-0076).** The first
heartbeat of its zone's boundary moves AWAITING to HELD, not HEALTHY: the
boundary is followed and its loss trips, and the arm stays at STOP. The
`ReleaseArm` service this node serves (`release_service`) is the one way from
HELD to HEALTHY. The arm is released by any `ReleaseArm` call on the side's
domain once the side is ready; the operator routes are the only callers in
the tree: the asset's initializer calls it as its first step, on the console's
Start robot after the go-ahead, `./scripts/home`, or the homing of
`./scripts/program`. A release is refused in every other state, and in HELD
until the side is READY (S-01): the vendor's `set_state` served exactly once,
a STOP the vendor answered with success since this activation, and every
action in `cancel_actions` - the arm trajectory controller's and the gripper
relay's - served exactly once. The trajectory controller's action exists only
once the side's controllers are spawned, which the side's launch does after
its hold gate; it stays served while the vendor plugin keeps the controllers
inactive under STOP. So the initializer, which serves before the hold gate
and the controllers, cannot release an arm whose side is still coming up. A
side started while the boundary is already beating therefore comes up HELD,
and a reconnect never enables the arm.

**Only HEALTHY enables.** On HELD -> HEALTHY the deadman calls the vendor's
`set_mode` with the plugin's streaming mode, then, once that answered success
and HEALTHY still stands, `set_state(0)`. That is the vendor plugin's own
enable (`:252-254`) less `clean_error`, which is an operator's decision. An
enable that fails or is abandoned at `call_deadline_s` is tried again on later
ticks while HEALTHY lasts, one at a time and no sooner than
`ENABLE_RETRY_TICKS` ticks after the failure: `set_mode` itself stops the arm,
so a retry on every tick would cycle it between STOP and START (HW-S-04). Once
`set_state(0)` is acknowledged in this HEALTHY epoch,
`DeadmanState.arm_enabled` says so and it is not sent again. "HEALTHY in this
epoch, so START" is decided and sent under the one lock every trip and every
STOP takes, so no START is ever sent after the STOP a state change caused. The
`set_mode` service itself stops the arm before it changes the mode
(`xarm_api/src/xarm_driver_service.cpp:543-550`). Once the arm is ready again
the plugin's `write` reactivates the controllers itself
(`uf_robot_system_hardware.cpp:345-350`, `_activate_controller` at
`:426-440`).

**What a trip does, on every tick while TRIPPED**, all of it asynchronous and
none of it waited on:

1. ``set_state(4)``, as in every state but HEALTHY.
2. ``set_linear_motor_stop``, which stops the carriage.
3. A cancel of EVERY goal on each named action — the gripper relay's and the
   arm trajectory controller's — through the action protocol's own cancel
   service with a zero goal id and a zero stamp, which `action_msgs/CancelGoal`
   defines as "cancel all goals".

Each call carries a steady-clock deadline (`call_deadline_s`). A call not
answered by its deadline is abandoned and said in the log; it never holds back
the next tick's call. The arm is stopped by `set_state(4)` and the cancel of its
trajectory controller's goals, and by nothing else here.

**Then the trip ends the side (ADR-0076 decision 5, owner decision of
2026-10-15).** Once a `set_state(4)` sent at or after the trip is acknowledged,
or `call_deadline_s` after the trip when none is, the deadman ends its own
process with `EXIT_TRIPPED` (through `cite_hardware.process.run`, which first
sends `set_state(4)` once more and waits for it within `call_deadline_s`). The
side's launch takes the whole side down when the deadman exits for any reason
(`side_down_on_exit`, `hardware.launch.py`), and a side started again comes up
with a fresh deadman, held. Why end rather than wait latched for a lifecycle
reset: a trip says the commander or the vendor driver is not the one this side
was following, and a whole new side is the one recovery that re-checks
everything it depends on (the hold gate's STOP among them) instead of trusting
a driver that may have restarted under it. Where nothing restarts the side —
`./scripts/program`, a scenario, a pair without the console's keeper — the trip
already ended every motion, and the side ending now ends the pair as well.
When no STOP sent at or after the trip was acknowledged, the side ends all the
same and says that the arm may remain enabled (S-03): it is to be checked in
UFACTORY Studio before the next start.

**The vendor driver going away trips it.** While HEALTHY, and while HELD once
the driver has been SEEN since activation, the vendor's `set_state` service
must be served by exactly one server: none is a driver that went away, two is
one that restarted before the old one's discovery lease expired. Either way
the driver's `on_activate` has cleaned the error, enabled motion and STARTED
the arm by itself (`:248-254`), which nothing here asked for. HELD waits to see
the driver first because the deadman starts before the driver's controller
manager: a side started under a boundary already beating reaches HELD while no
driver exists yet. SEEN means a STOP sent since this activation was answered
with success while the service had exactly one server (S-02): a count of one
alone would be satisfied by the stale endpoint of a crashed driver, whose
expiry would then trip a side that never had a live driver, and every restart
of that side would energize the arm again (the plugin's `clean_error` and
START on activation). Seen on the tick: an outage shorter than one
`tick_period_s` with no overlap is not seen, and a driver restart takes
seconds.

**Latched.** A trip is never cleared by heartbeats resuming. The relays read
the published `DeadmanState`, republished on every tick, and refuse motion in
every state but HEALTHY.

**Recovery after a trip**, for an operator: find why the heartbeat stopped;
start the side again (or let the console's keeper do it, ADR-0077); the new
deadman says AWAITING, then HELD on the boundary's heartbeat, and keeps the arm
stopped until Start robot releases it. A vendor error (`curr_err`) is not
cleared by any of this and needs the vendor's own `clean_error` first.

**Its clock is the steady clock, and `use_sim_time` is refused.** It times a
process on real hardware: simulated time is the wrong instrument, and a deadman
whose timer waited on a `/clock` nobody publishes would never trip.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
import threading

from action_msgs.srv import CancelGoal
from cite_hardware.liveness import (
    FOLLOWING,
    HEALTHY,
    HELD,
    Liveness,
    Outcome,
    STATE_NAMES,
    TRIPPED,
)
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.msg import DeadmanState, TwinHeartbeat
from cite_interfaces.qos import LATCHED, STATE
from cite_interfaces.srv import ReleaseArm
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.event_handler import SubscriptionEventCallbacks
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from xarm_msgs.srv import Call, SetInt16

NODE_NAME = "deadman"

#: The vendor's states for `set_state`. Constants of the vendor's API, not facts
#: of the asset: `xarm_sdk/cxx/include/xarm/core/instruction/uxbus_cmd_config.h`,
#: `XARM_STATE` (START = 0, STOP = 4).
VENDOR_STATE_START = 0
VENDOR_STATE_STOP = 4

#: How many ticks a failed enable waits before it is tried again (HW-S-04). The
#: vendor's `set_mode` stops the arm before it changes the mode, so an enable
#: retried on every tick would cycle the arm between STOP and START at the tick
#: rate. A mechanism constant, not a fact of the asset.
ENABLE_RETRY_TICKS = 4

#: The vendor modes in which the vendor plugin streams commands: SERVO (1) for
#: position control, VELO_JOINT (4) for velocity control
#: (`uf_robot_system_hardware.cpp:487`; `XARM_MODE` in `uxbus_cmd_config.h`).
VENDOR_STREAMING_MODES = (1, 4)

#: The exit code of a deadman that ended its process because it tripped
#: (ADR-0076 decision 5). Non-zero, so the side's launch and the pair
#: supervisor read it as the side failing, which it did.
EXIT_TRIPPED = 3

SPECS: tuple[Spec, ...] = (
    Spec("zone", Parameter.Type.STRING, "the zone whose boundary's heartbeat is watched"),
    Spec("asset_id", Parameter.Type.STRING, "the arm whose side this deadman guards"),
    Spec(
        "timeout_s",
        Parameter.Type.DOUBLE,
        "the heartbeat timeout, steady-clock seconds since the last fresh heartbeat",
        positive=True,
    ),
    Spec(
        "tick_period_s",
        Parameter.Type.DOUBLE,
        "steady-clock period of the tick that checks the timeout, republishes the "
        "state and re-asserts every stop; below timeout_s",
        positive=True,
    ),
    Spec(
        "call_deadline_s",
        Parameter.Type.DOUBLE,
        "steady-clock seconds after which an unanswered vendor or cancel call is abandoned",
        positive=True,
    ),
    Spec(
        "state_topic",
        Parameter.Type.STRING,
        "where this deadman publishes its DeadmanState, latched and on every tick",
    ),
    Spec(
        "release_service",
        Parameter.Type.STRING,
        "the ReleaseArm service this deadman serves: its one way from HELD to HEALTHY",
    ),
    Spec(
        "set_state_service",
        Parameter.Type.STRING,
        "the vendor's set_state service (xarm_msgs/SetInt16)",
    ),
    Spec(
        "set_mode_service",
        Parameter.Type.STRING,
        "the vendor's set_mode service (xarm_msgs/SetInt16), called to enable on HEALTHY",
    ),
    Spec(
        "enable_mode",
        Parameter.Type.INTEGER,
        "the vendor mode the vendor plugin streams in: 1 (servo) or 4 (joint velocity)",
    ),
    Spec(
        "linear_motor_stop_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_stop service (xarm_msgs/Call)",
    ),
    Spec(
        "cancel_actions",
        Parameter.Type.STRING_ARRAY,
        "the actions whose every goal is cancelled on every tick while tripped",
    ),
)


@dataclass
class _Pending:
    """One call in flight, and when it is abandoned."""

    label: str
    client: object
    future: object
    deadline_ns: int


class Deadman(LifecycleNode):
    def __init__(self, **node_options) -> None:
        # `node_options` reach `rclpy.node.Node` unchanged; a test hands its
        # parameter overrides in through them rather than through a launch.
        super().__init__(NODE_NAME, **node_options)
        self._required = RequiredParameters(self, SPECS)
        # The lock, and NOT the callback group, is what serialises this node.
        # The group below holds heartbeats, the tick and the matched event, but
        # a vendor's answer is delivered through a future's done callback, and
        # rclpy (Jazzy, `Future.add_done_callback`) runs that as an executor
        # TASK outside every callback group: under the multi-threaded executor
        # it runs concurrently with a trip. So every decision that leads to a
        # vendor call — "HEALTHY in this epoch, so START", "not HEALTHY, so
        # STOP" — is taken and SENT under this lock, and no START is ever sent
        # after a STOP that a state change caused (N-01). Reentrant, because a
        # call refused before sending answers its continuation at once, under
        # the same lock. Nothing done under it blocks: every call is
        # asynchronous.
        self._lock = threading.RLock()
        self._group = MutuallyExclusiveCallbackGroup()
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self._config: dict | None = None
        self._liveness: Liveness | None = None
        self._state_publisher = None
        self._heartbeats = None
        self._timer = None
        self._set_state = None
        self._set_mode = None
        self._linear_stop = None
        self._cancels: list[tuple[str, object]] = []
        self._pending: list[_Pending] = []
        #: Steady-clock time of the last fresh heartbeat, nanoseconds.
        self._last_fresh_ns = 0
        #: Bumped on every change of state, so an enable answered after the
        #: state moved on is recognised as stale and goes no further.
        self._epoch = 0
        #: The epoch whose enable (`set_mode`, then `set_state(0)`) is in
        #: flight, so a tick does not start a second one; `None` when none is.
        self._enable_in_flight: int | None = None
        #: The epoch in which `set_state(0)` was acknowledged. The arm is
        #: enabled only while this equals the current epoch and HEALTHY holds.
        self._enabled_epoch: int | None = None
        #: After a failed enable in an epoch: that epoch, and the steady-clock
        #: time before which it is not tried again (HW-S-04).
        self._enable_backoff: tuple[int, int] | None = None
        self._release_server = None
        #: Bumped on every activation, so a STOP answered for an earlier one
        #: is not taken as this one's.
        self._activation = 0
        #: Whether a STOP sent since the last activation was answered with
        #: success: the vendor driver is live, not a stale endpoint (S-02).
        self._stop_acknowledged = False
        #: Whether the vendor was SEEN since the last activation: a STOP
        #: acknowledged while set_state had exactly one server. From then on,
        #: HELD trips on losing it (S-02).
        self._vendor_seen = False
        #: Steady-clock time of this process's first trip, nanoseconds; the
        #: process ends soon after it (ADR-0076 decision 5).
        self._tripped_at_ns: int | None = None
        self._end_requested = False
        #: Ends this process with an exit code; bound by `process.run`, and
        #: `None` for a node built in a test's own process.
        self._end_process = None

    def bind_end_process(self, end) -> None:
        """Take `process.run`'s way of ending this process with an exit code."""
        self._end_process = end

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        if self.get_parameter("use_sim_time").value:
            self.get_logger().error(
                "cannot configure: use_sim_time is set, and this deadman times a process "
                "on the steady clock (see the module docstring)"
            )
            return TransitionCallbackReturn.FAILURE
        try:
            config = self._required.read()
            liveness = Liveness(config["zone"], config["timeout_s"])
            if not config["tick_period_s"] < config["timeout_s"]:
                raise ValueError(
                    f"tick_period_s {config['tick_period_s']:g} must be below timeout_s "
                    f"{config['timeout_s']:g}, or the timeout is checked too rarely to hold"
                )
            if config["enable_mode"] not in VENDOR_STREAMING_MODES:
                raise ValueError(
                    f"enable_mode {config['enable_mode']} is not a mode the vendor plugin "
                    f"streams in {VENDOR_STREAMING_MODES}"
                )
        except (ParameterError, ValueError) as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        self._config = config
        self._liveness = liveness

        # A plain publisher, not a lifecycle one: INACTIVE has to be said
        # while inactive. LATCHED so a relay starting later hears the current
        # state at once; republished on every tick so a relay can tell a live
        # deadman from a last word.
        self._state_publisher = self.create_publisher(
            DeadmanState, config["state_topic"], LATCHED
        )
        self._set_state = self.create_client(
            SetInt16, config["set_state_service"], callback_group=self._group
        )
        self._set_mode = self.create_client(
            SetInt16, config["set_mode_service"], callback_group=self._group
        )
        self._linear_stop = self.create_client(
            Call, config["linear_motor_stop_service"], callback_group=self._group
        )
        self._cancels = [
            (
                action,
                self.create_client(
                    CancelGoal, f"{action}/_action/cancel_goal", callback_group=self._group
                ),
            )
            for action in config["cancel_actions"]
        ]
        # STATE is the boundary's heartbeat profile. The matched event is what
        # says the publisher went away; the timeout says it too, but later.
        self._heartbeats = self.create_subscription(
            TwinHeartbeat,
            TwinHeartbeat.TOPIC,
            self._on_heartbeat,
            STATE,
            callback_group=self._group,
            event_callbacks=SubscriptionEventCallbacks(matched=self._on_matched),
        )
        # From configure to cleanup, in every lifecycle state: the arm is held
        # stopped whenever this deadman is not HEALTHY, inactive included.
        self._timer = self.create_timer(
            config["tick_period_s"], self._tick, callback_group=self._group, clock=self._steady
        )
        # In the one group with the heartbeats and the tick: a release and a
        # trip never interleave. Nothing in its callback waits.
        self._release_server = self.create_service(
            ReleaseArm,
            config["release_service"],
            self._on_release_arm,
            callback_group=self._group,
        )
        self.get_logger().info(
            f"configured: zone {config['zone']!r}, timeout {config['timeout_s']:g} s, "
            f"tick {config['tick_period_s']:g} s, {len(self._cancels)} action(s) to cancel"
        )
        self._hold_stopped()
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        assert self._liveness is not None
        with self._lock:
            self._liveness.activate()
            self._epoch += 1
            self._activation += 1
            self._stop_acknowledged = False
            self._vendor_seen = False
        # The vendor plugin's own activation sets START; this undoes it at once.
        self._hold_stopped()
        self._publish_state()
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        if self._liveness is not None:
            with self._lock:
                self._liveness.deactivate()
                self._epoch += 1
            self._hold_stopped()
            self._publish_state()
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        if self._liveness is not None:
            with self._lock:
                self._liveness.deactivate()
                self._epoch += 1
            self._hold_stopped()
            self._publish_state()
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def stop_before_exit(self) -> tuple[list, float]:
        """Stop the arm because the PROCESS is ending: SIGINT or SIGTERM.

        rclpy (Jazzy) runs no lifecycle transition when its context goes down:
        `LifecycleNode.destroy_node` does not call `on_shutdown`, and a context's
        own `on_shutdown` callbacks run after `rcl` has shut down, when nothing
        can be sent. So `cite_hardware.process.run` calls this first, while the
        context still stands, and waits on the returned futures for at most the
        returned seconds. Best effort: sent whether or not the vendor is seen.
        The state is published INACTIVE first, so the relays close at once.
        """
        config, client = self._config, self._set_state
        if config is None or client is None:
            return [], 0.0
        with self._lock:
            # A trip stays said as the process ends: it is why it ends.
            if self._liveness is not None and self._tripped_at_ns is None:
                self._liveness.deactivate()
                self._epoch += 1
            request = SetInt16.Request()
            request.data = VENDOR_STATE_STOP
            future = client.call_async(request)
        self._publish_state()
        self.get_logger().warning("process ending: set_state(4) sent before exit")
        return [future], config["call_deadline_s"]

    def _release(self) -> None:
        if self._timer is not None:
            self.destroy_timer(self._timer)
            self._timer = None
        if self._heartbeats is not None:
            self.destroy_subscription(self._heartbeats)
            self._heartbeats = None
        if self._release_server is not None:
            self.destroy_service(self._release_server)
            self._release_server = None
        for client in [self._set_state, self._set_mode, self._linear_stop] + [
            client for _action, client in self._cancels
        ]:
            if client is not None:
                self.destroy_client(client)
        self._set_state = self._set_mode = self._linear_stop = None
        self._cancels = []
        self._pending = []
        self._enable_in_flight = None
        self._enabled_epoch = None
        self._enable_backoff = None
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
        publishers = self.count_publishers(TwinHeartbeat.TOPIC)
        with self._lock:
            before = self._liveness.state
            outcome = self._liveness.heartbeat(
                message.zone, message.boundary_id, message.sequence, publishers
            )
            after = self._liveness.state
            if outcome.accepted and not outcome.tripped:
                # The timeout runs from the last FRESH heartbeat.
                self._last_fresh_ns = self._steady.now().nanoseconds
            if after != before:
                self._epoch += 1
        if outcome.tripped:
            self._trip(outcome.reason)
            return
        if not outcome.accepted:
            if before != TRIPPED:
                self.get_logger().warning(outcome.reason, throttle_duration_sec=5.0)
            return
        if after != before:
            # AWAITING -> HELD at most: a heartbeat never enables (ADR-0076).
            self.get_logger().info(outcome.reason)
            self._publish_state()

    def _on_release_arm(self, _request, response):
        """Serve `ReleaseArm`: HELD -> HEALTHY, then the enable; refused otherwise.

        Decided under the lock every trip and every STOP takes, so a STOP a tick
        decided before the release is sent before the release's `set_mode`.
        """
        liveness, config = self._liveness, self._config
        if liveness is None or config is None:
            response.success = False
            response.detail = "release refused: the deadman is not configured"
            return response
        vendors = self.count_services(config["set_state_service"])
        unserved = [
            action
            for action in config["cancel_actions"]
            if self.count_services(f"{action}/_action/cancel_goal") != 1
        ]
        with self._lock:
            unready = None
            if liveness.state == HELD:
                unready = self._release_unready(vendors, unserved)
            if unready is not None:
                outcome = Outcome(accepted=False, reason=f"release refused: {unready}")
            else:
                outcome = liveness.release()
            if outcome.accepted:
                self._epoch += 1
            epoch = self._epoch
        response.success = outcome.accepted
        response.detail = outcome.reason
        if not outcome.accepted:
            self.get_logger().warning(outcome.reason)
            return response
        self.get_logger().info(outcome.reason)
        self._publish_state()
        # The one place the arm is enabled: the HELD -> HEALTHY edge.
        self._enable(epoch)
        return response

    def _release_unready(self, vendors: int, unserved: list[str]) -> str | None:
        """Why a HELD side is not ready to be released (S-01), or None; under the lock."""
        assert self._config is not None
        if vendors != 1:
            return (
                f"{self._config['set_state_service']} is served by {vendors} server(s), and "
                "the arm is enabled through exactly one"
            )
        if not self._stop_acknowledged:
            return (
                "the vendor has acknowledged no STOP since this deadman was activated, so "
                "the arm is not known to be held by a live driver"
            )
        if unserved:
            return (
                f"the side's controllers are not up: {', '.join(unserved)} is not served by "
                "exactly one server"
            )
        return None

    def _on_matched(self, status) -> None:
        if status.current_count > 0 or self._liveness is None:
            return
        with self._lock:
            outcome = self._liveness.publisher_lost()
            if outcome.tripped:
                self._epoch += 1
        if outcome.tripped:
            self._trip(outcome.reason)

    def _tick(self) -> None:
        """Check the timeout, republish the state, and hold every stop that applies."""
        liveness, config = self._liveness, self._config
        if liveness is None or config is None:
            return
        now = self._steady.now().nanoseconds
        self._abandon_overdue(now)
        outcome = None
        vendors = self.count_services(config["set_state_service"])
        with self._lock:
            if vendors == 1 and self._stop_acknowledged:
                self._vendor_seen = True
            if liveness.state in FOLLOWING:
                if now - self._last_fresh_ns > config["timeout_s"] * 1e9:
                    outcome = liveness.expired()
                elif self.count_publishers(TwinHeartbeat.TOPIC) > 1:
                    outcome = liveness.second_boundary(
                        "more than one heartbeat publisher on the topic"
                    )
                elif self.count_publishers(TwinHeartbeat.TOPIC) == 0:
                    outcome = liveness.publisher_lost()
                elif vendors != 1 and (liveness.state == HEALTHY or self._vendor_seen):
                    # N-03. The vendor's `ros2_control_node` restarting is a
                    # fault, not a pause: its plugin's `on_activate` cleans the
                    # error, enables motion and STARTS the arm on its own. Gone
                    # (0) or restarted before the old one's lease expired (2),
                    # the stop path is not the one this deadman follows. HELD
                    # applies it once the driver was served (module docstring).
                    outcome = liveness.vendor_lost(
                        f"{config['set_state_service']} is served by {vendors} server(s), "
                        "and the vendor driver this side was following is one"
                    )
            if outcome is not None and outcome.tripped:
                self._epoch += 1
            state = liveness.state
            epoch = self._epoch
            tripped_at = self._tripped_at_ns
        if outcome is not None and outcome.tripped:
            self._trip(outcome.reason)
            return
        if state == TRIPPED:
            self._issue_trip_stops()
        elif state != HEALTHY:
            self._hold_stopped()
        else:
            # A failed or abandoned enable is retried while HEALTHY lasts;
            # `_enable` itself refuses a second one in flight or a repeat.
            self._enable(epoch)
        if tripped_at is not None and now - tripped_at >= config["call_deadline_s"] * 1e9:
            self._end_after_trip(
                f"no set_state(4) acknowledged within {config['call_deadline_s']:g} s of the trip",
                acknowledged=False,
            )
        self._publish_state(log=False)

    # ------------------------------------------------------------------ #
    # The vendor calls
    # ------------------------------------------------------------------ #

    def _trip(self, reason: str) -> None:
        with self._lock:
            if self._tripped_at_ns is None:
                self._tripped_at_ns = self._steady.now().nanoseconds
        self.get_logger().error(reason)
        self._publish_state()
        self._issue_trip_stops()

    def _hold_stopped(self, then=None) -> None:
        """Send `set_state(4)` unless HEALTHY, deciding and sending under the lock.

        Under the lock so that a STOP decided on a state that is no longer
        current — a tick that read HELD just before a release — is not sent
        after that state's START.
        """
        request = SetInt16.Request()
        request.data = VENDOR_STATE_STOP
        with self._lock:
            if self._liveness is not None and self._liveness.state == HEALTHY:
                return
            activation = self._activation

            def answered(response) -> None:
                self._stop_answered(activation, response)
                if then is not None:
                    then(response)

            self._call("set_state(4)", self._set_state, request, then=answered)

    def _stop_answered(self, activation: int, response) -> None:
        """Record a STOP the vendor answered with success in this activation (S-02)."""
        if response is None or getattr(response, "ret", None) != 0:
            return
        with self._lock:
            if self._activation == activation and activation > 0:
                self._stop_acknowledged = True

    def _issue_trip_stops(self) -> None:
        self._hold_stopped(then=self._trip_stop_answered)
        self._call("set_linear_motor_stop", self._linear_stop, Call.Request())
        for action, client in self._cancels:
            # A default-constructed request is a zero goal id and a zero stamp:
            # "cancel all goals" in action_msgs/srv/CancelGoal.
            self._call(f"cancel all goals on {action}", client, CancelGoal.Request())

    def _trip_stop_answered(self, response) -> None:
        """End the side once a STOP sent at or after the trip is acknowledged."""
        if response is not None and getattr(response, "ret", None) == 0:
            self._end_after_trip("set_state(4) acknowledged after the trip")

    def _end_after_trip(self, why: str, acknowledged: bool = True) -> None:
        """Ask `process.run` to end this process, once (ADR-0076 decision 5).

        ``acknowledged`` False: no STOP sent at or after the trip was answered
        with success, so the arm may still be enabled, and that is said (S-03).
        """
        with self._lock:
            if self._end_requested or self._tripped_at_ns is None:
                return
            self._end_requested = True
            end = self._end_process
        if not acknowledged:
            self.get_logger().error(
                "no STOP was acknowledged after the trip: the arm may remain enabled; "
                "check it in UFACTORY Studio before the next start"
            )
        self.get_logger().error(
            f"ending this side after the trip ({why}): the deadman exits with code "
            f"{EXIT_TRIPPED}, and a side started again comes up held"
        )
        if end is not None:
            end(EXIT_TRIPPED)

    def _current(self, epoch: int) -> bool:
        """Whether HEALTHY holds in ``epoch``. Called with the lock held."""
        return (
            self._liveness is not None
            and self._liveness.state == HEALTHY
            and self._epoch == epoch
        )

    def _enable(self, epoch: int) -> None:
        """Enable the arm: `set_mode`, then `set_state(0)` once that succeeded.

        At most one enable is in flight, and none once this epoch's succeeded.
        One that fails or is abandoned at `call_deadline_s` clears its mark, so
        the next tick tries again while HEALTHY lasts.
        """
        assert self._config is not None
        request = SetInt16.Request()
        request.data = self._config["enable_mode"]
        now = self._steady.now().nanoseconds
        with self._lock:
            if not self._current(epoch) or epoch in (
                self._enable_in_flight,
                self._enabled_epoch,
            ):
                return
            backoff = self._enable_backoff
            if backoff is not None and backoff[0] == epoch and now < backoff[1]:
                return
            self._enable_in_flight = epoch
            self._call(
                f"set_mode({request.data})",
                self._set_mode,
                request,
                then=lambda response: self._start(epoch, response),
            )

    def _start(self, epoch: int, response) -> None:
        """Send `set_state(0)` if `set_mode` succeeded and HEALTHY still holds.

        The check and the send are one step under the lock, which every state
        change and every STOP also take: a trip either happened before the
        check, and nothing is sent, or happens after the send, and its STOP
        follows this START (N-01).
        """
        with self._lock:
            if not self._current(epoch):
                if self._enable_in_flight == epoch:
                    self._enable_in_flight = None
                self.get_logger().warning(
                    "enable dropped: the deadman left HEALTHY while set_mode was answered"
                )
                return
            if response is None or response.ret != 0:
                self._enable_in_flight = None
                self._back_off(epoch)
                self.get_logger().error(
                    "enable failed: set_mode did not succeed, so the arm stays stopped; "
                    "tried again on the next tick while HEALTHY",
                    throttle_duration_sec=5.0,
                )
                return
            request = SetInt16.Request()
            request.data = VENDOR_STATE_START
            self._call(
                "set_state(0)",
                self._set_state,
                request,
                then=lambda answer: self._started(epoch, answer),
            )

    def _started(self, epoch: int, response) -> None:
        """Record an acknowledged `set_state(0)` as this epoch's enable."""
        with self._lock:
            if self._enable_in_flight == epoch:
                self._enable_in_flight = None
            enabled = (
                response is not None and response.ret == 0 and self._current(epoch)
            )
            if enabled:
                self._enabled_epoch = epoch
            else:
                self._back_off(epoch)
        if enabled:
            self.get_logger().info("arm enabled: set_state(0) acknowledged while HEALTHY")
            self._publish_state(log=False)

    def _back_off(self, epoch: int) -> None:
        """Hold the next enable of ``epoch`` off for `ENABLE_RETRY_TICKS` ticks."""
        assert self._config is not None
        delay_ns = int(ENABLE_RETRY_TICKS * self._config["tick_period_s"] * 1e9)
        self._enable_backoff = (epoch, self._steady.now().nanoseconds + delay_ns)

    def _call(self, label: str, client, request, then=None) -> None:
        """Send one call with a deadline; never wait on it.

        ``then`` receives the response, or ``None`` when the call failed.
        """
        config = self._config
        if client is None or config is None:
            return
        if not client.service_is_ready():
            self.get_logger().error(
                f"{label} not sent: {client.srv_name} is not available; sent again on the "
                "next tick",
                throttle_duration_sec=5.0,
            )
            if then is not None:
                then(None)
            return
        future = client.call_async(request)
        pending = _Pending(
            label,
            client,
            future,
            self._steady.now().nanoseconds + int(config["call_deadline_s"] * 1e9),
        )
        with self._lock:
            self._pending.append(pending)
        future.add_done_callback(lambda done: self._on_answer(pending, done, then))

    def _on_answer(self, pending: _Pending, future, then) -> None:
        with self._lock:
            if pending in self._pending:
                self._pending.remove(pending)
        if future.cancelled():
            # Abandoned at its deadline: a continuation still hears that it
            # failed, so an enable is not left marked in flight for ever.
            if then is not None:
                then(None)
            return
        error = future.exception()
        response = None if error is not None else future.result()
        # A vendor call reports success as `ret == 0`. A cancel is answered with
        # a return code that is not a failure when there was nothing to cancel,
        # so any answer at all is enough for it.
        code = getattr(response, "ret", 0) if response is not None else None
        if response is None or (not isinstance(response, CancelGoal.Response) and code != 0):
            self.get_logger().error(
                f"{pending.label} did not land ({error if error else f'vendor code {code}'})",
                throttle_duration_sec=5.0,
            )
        if then is not None:
            then(response)

    def _abandon_overdue(self, now_ns: int) -> None:
        with self._lock:
            overdue = [each for each in self._pending if now_ns > each.deadline_ns]
            for each in overdue:
                self._pending.remove(each)
        for each in overdue:
            each.client.remove_pending_request(each.future)
            each.future.cancel()
            self.get_logger().error(
                f"{each.label} unanswered within call_deadline_s; abandoned",
                throttle_duration_sec=5.0,
            )

    def _publish_state(self, log: bool = True) -> None:
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
            message.detail = liveness.detail
            message.arm_enabled = (
                liveness.state == HEALTHY and self._enabled_epoch == self._epoch
            )
        publisher.publish(message)
        if log:
            self.get_logger().info(f"deadman {STATE_NAMES[message.state]}: {message.detail}")


def main() -> int:
    return run(Deadman)


if __name__ == "__main__":
    sys.exit(main())
