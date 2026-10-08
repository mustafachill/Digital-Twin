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

"""The physical gripper, behind the simulated gripper controller's action name.

ADR-0070 item 4. In simulation `picker_gripper_controller` serves
`control_msgs/GripperCommand` at the plan's `gripper_action`, in the drive
joint's own units. On the physical side no gripper controller runs: the vendor
plugin's embedded driver serves its own `GripperCommand` at
`<prefix>xarm_gripper/gripper_action`, in its own units. This node serves the
plan's name and relays, mapping the drive-joint position linearly between
`[open_position, closed_position]` and `[vendor_open_position,
vendor_closed_position]` in both directions, and nothing more.

**The vendor's units.** The vendor action takes and reports drive-joint-like
units, 0.0 open to 0.85 closed: it converts a goal to a pulse target as
``|max_pos - position * 1000|`` and a pulse reading back as
``|max_pos - pulses| / 1000``, with `xarm_gripper.max_pos` 850 by default
(`xarm_api/src/xarm_driver.cpp:507-515`, used at `:607` and `:643`). Its
`get_gripper_position` service reports the raw PULSES, about 850 open to 0
closed (`xarm_driver_service.cpp:800-805`). So the action's endpoints are
0.0 / 0.85 and the state service's 850 / 0, each its own pair of parameters.

**IT REPORTS WHAT THE VENDOR REPORTS, AND NOTHING IT DOES NOT.** The vendor's
action fills only `position` in its feedback and result: `stalled` and
`reached_goal` are never set and arrive false, and it succeeds whenever the
jaws stop moving, wherever that is (`xarm_api/src/xarm_driver.cpp`,
`_xarm_gripper_action_execute`). ADR-0063 left the SDK's stall path
unestablished, and this relay does not establish it by inventing one: both
flags are forwarded exactly as received, and a result in which the vendor
reported neither is said so in the log. A Grasp skill judging custody from it
therefore reads "not stalled", which is the safe direction — it reports an
empty gripper rather than a held part.

**Cancellation is forwarded, and the vendor ignores it.** The vendor accepts a
cancel request and its execute loop does not read it (the check is commented
out in the same function), so the jaws finish the motion they were sent. This
relay answers its own client's cancel once the vendor has acknowledged it, with
the last position the vendor reported. That is the whole of what "cancel" can
mean on this hardware, and it is stated rather than papered over.

**No preemption: a new goal is REJECTED while a vendor goal is still running**,
where `GripperActionController` would preempt. The vendor ignores a cancel, and
runs each goal on a thread of its own that keeps commanding the jaws until they
stop (`xarm_driver.cpp:542-546`, `:609-650`): preempting would run two vendor
threads against one gripper. A vendor goal counts as running until the vendor
reports its result, or until `result_timeout_s` after it was sent — whichever
comes first — so a vendor goal that never ends cannot wedge the relay. Our own
goal may already have ended by then (cancelled, or ended by the deadman); the
refusal still holds until the vendor's goal is over.

**The drive joint's state** is published too, because on the physical side
`joint_state_broadcaster` reports joint1..5 only and `robot_state_publisher`
and MoveIt would otherwise lack it. It is POLLED from `get_gripper_position`
rather than read from the vendor's own `<hw_ns>/joint_states`: the vendor
publishes gripper states there only from a real-time report thread that needs
firmware 2.7.101 and `add_gripper`, or from inside an action, and under six
joint names the generated description need not carry (`xarm_driver.cpp`, the
report loop and `_pub_xarm_gripper_joint_states`). The service reports PULSES,
a different unit from the action's, so the state has its own pair of endpoints.
It is published on the arm's joint-state topic beside `joint_state_broadcaster`
and the track adapter, each with the joints it owns; `robot_state_publisher`
and MoveIt's state monitor both merge partial messages by joint name.

**Every goal is bounded** by `result_timeout_s` on the steady clock. The bound
is not decoration: the vendor's error path calls `canceled()` on a goal no one
asked to cancel, which `rclcpp_action` refuses with an exception the vendor
catches and logs — so that vendor goal never ends. Without a bound, neither
would this relay's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import sys
import threading

from action_msgs.msg import GoalStatus
from cite_hardware.gate import DeadmanGate
from cite_hardware.mapping import LinearMap
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.qos import STATE
from control_msgs.action import GripperCommand
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.task import Future
from sensor_msgs.msg import JointState
from xarm_msgs.srv import GetFloat32

NODE_NAME = "gripper_relay"

SPECS: tuple[Spec, ...] = (
    Spec(
        "action_name",
        Parameter.Type.STRING,
        "the GripperCommand action this relay serves: the plan's gripper_action",
    ),
    Spec(
        "vendor_action_name",
        Parameter.Type.STRING,
        "the vendor driver's GripperCommand action (<prefix>xarm_gripper/gripper_action)",
    ),
    Spec("open_position", Parameter.Type.DOUBLE, "the drive joint's open position"),
    Spec("closed_position", Parameter.Type.DOUBLE, "the drive joint's closed position"),
    Spec(
        "vendor_open_position",
        Parameter.Type.DOUBLE,
        "the vendor action's position for fully open (0.0 for the xArm gripper)",
    ),
    Spec(
        "vendor_closed_position",
        Parameter.Type.DOUBLE,
        "the vendor action's position for fully closed (0.85 for the xArm gripper)",
    ),
    Spec(
        "result_timeout_s",
        Parameter.Type.DOUBLE,
        "how long one goal may wait for the vendor's result, and one position read "
        "for its answer, steady-clock seconds",
        positive=True,
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
    Spec("drive_joint", Parameter.Type.STRING, "the gripper's drive joint name"),
    Spec(
        "joint_state_topic",
        Parameter.Type.STRING,
        "the arm's joint-state topic, on which the drive joint's position is published",
    ),
    Spec(
        "get_position_service",
        Parameter.Type.STRING,
        "the vendor's get_gripper_position service (xarm_msgs/GetFloat32)",
    ),
    Spec(
        "vendor_state_open_position",
        Parameter.Type.DOUBLE,
        "what get_gripper_position reports fully open, in its own unit (pulses)",
    ),
    Spec(
        "vendor_state_closed_position",
        Parameter.Type.DOUBLE,
        "what get_gripper_position reports fully closed, in its own unit (pulses)",
    ),
    Spec(
        "poll_period_s",
        Parameter.Type.DOUBLE,
        "how often the gripper position is read and published, seconds",
        positive=True,
    ),
)

#: Marks a position read as in flight between reserving it and sending it.
_RESERVED = object()

#: How a forwarded goal ended, other than by the vendor's own result.
_CANCELLED = "cancelled"
_TIMED_OUT = "timed out"
_DEADMAN = "deadman"
_INACTIVE = "inactive"
_REFUSED = "refused by the vendor"
_VENDOR = "vendor"


@dataclass
class _Forwarded:
    """One goal of ours and the vendor goal behind it."""

    handle: object
    finish: Future = field(default_factory=Future)
    vendor: object | None = None
    #: The last position the vendor reported, in DRIVE-JOINT units.
    position: float = math.nan
    cancel_requested: bool = False
    deadline: object | None = None


class GripperRelay(LifecycleNode):
    def __init__(self, **node_options) -> None:
        # `node_options` reach `rclpy.node.Node` unchanged; a test hands its
        # parameter overrides in through them rather than through a launch.
        super().__init__(NODE_NAME, **node_options)
        self._required = RequiredParameters(self, SPECS)
        self._lock = threading.Lock()
        self._group = ReentrantCallbackGroup()
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self._config: dict | None = None
        self._map: LinearMap | None = None
        self._active = False
        self._server: ActionServer | None = None
        self._vendor: ActionClient | None = None
        self._gate: DeadmanGate | None = None
        self._current: _Forwarded | None = None
        #: The goal whose VENDOR goal may still be running. Outlives `_current`
        #: when our goal ends first; cleared by the vendor's result, a vendor
        #: refusal, or the goal's `result_timeout_s` deadline.
        self._busy: _Forwarded | None = None
        #: Drive joint <-> what `get_gripper_position` reports. A second map,
        #: because the vendor's state service and its action do not share a
        #: unit: the service reports pulses, the action converts them.
        self._state_map: LinearMap | None = None
        self._state_client = None
        self._state_publisher = None
        self._poll_timer = None
        #: The position read in flight, and when it is abandoned (N-08): a read
        #: the vendor never answers must not stop every later one.
        self._poll_future = None
        self._poll_deadline_ns = 0

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            config = self._required.read()
            self._map = LinearMap(
                config["open_position"],
                config["closed_position"],
                config["vendor_open_position"],
                config["vendor_closed_position"],
            )
            self._state_map = LinearMap(
                config["open_position"],
                config["closed_position"],
                config["vendor_state_open_position"],
                config["vendor_state_closed_position"],
            )
        except (ParameterError, ValueError) as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        if config["action_name"] == config["vendor_action_name"]:
            self.get_logger().error(
                "cannot configure: the relay would serve the action it forwards to"
            )
            return TransitionCallbackReturn.FAILURE
        self._config = config
        self._vendor = ActionClient(
            self, GripperCommand, config["vendor_action_name"], callback_group=self._group
        )
        self._server = ActionServer(
            self,
            GripperCommand,
            config["action_name"],
            execute_callback=self._execute,
            goal_callback=self._on_goal,
            handle_accepted_callback=self._on_accepted,
            cancel_callback=self._on_cancel,
            callback_group=self._group,
        )
        self._gate = DeadmanGate(
            self,
            config["deadman_state_topic"],
            config["deadman_state_max_age_s"],
            self._group,
            self._on_gate_closed,
        )
        self._state_client = self.create_client(
            GetFloat32, config["get_position_service"], callback_group=self._group
        )
        # STATE is `joint_state_broadcaster`'s own profile on this topic.
        self._state_publisher = self.create_lifecycle_publisher(
            JointState, config["joint_state_topic"], STATE
        )
        self.get_logger().info(
            f"configured: {config['action_name']} -> {config['vendor_action_name']}, "
            f"{config['drive_joint']} published on {config['joint_state_topic']}"
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
            current = self._current
        if self._poll_timer is not None:
            self.destroy_timer(self._poll_timer)
            self._poll_timer = None
        if current is not None:
            self._end(current, _INACTIVE, "the relay was deactivated")
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
            current = self._current
        if current is not None:
            self._end(current, _INACTIVE, "the relay is shutting down")
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def _release(self) -> None:
        if self._poll_timer is not None:
            self.destroy_timer(self._poll_timer)
            self._poll_timer = None
        if self._state_client is not None:
            self.destroy_client(self._state_client)
            self._state_client = None
        self._poll_future = None
        if self._state_publisher is not None:
            self.destroy_lifecycle_publisher(self._state_publisher)
            self._state_publisher = None
        self._state_map = None
        if self._gate is not None:
            self._gate.destroy()
            self._gate = None
        if self._server is not None:
            self._server.destroy()
            self._server = None
        if self._vendor is not None:
            self._vendor.destroy()
            self._vendor = None
        self._config = None
        self._map = None
        self._current = None
        self._busy = None

    # ------------------------------------------------------------------ #
    # The drive joint's state
    # ------------------------------------------------------------------ #

    def _poll(self) -> None:
        if self._gate is not None:
            self._gate.check()
        config = self._config
        if config is None:
            return
        now = self._steady.now().nanoseconds
        with self._lock:
            if not self._active:
                return
            overdue = None
            if self._poll_future is not None:
                if now <= self._poll_deadline_ns:
                    return
                overdue, self._poll_future = self._poll_future, None
            # Reserved under the lock before it is sent, with its deadline, so
            # a second poll on the reentrant group sends nothing.
            self._poll_future = _RESERVED
            self._poll_deadline_ns = now + int(config["result_timeout_s"] * 1e9)
        client = self._state_client
        if overdue is not None and overdue is not _RESERVED and client is not None:
            client.remove_pending_request(overdue)
            overdue.cancel()
            self.get_logger().error(
                "get_gripper_position unanswered within result_timeout_s; abandoned, and "
                "no drive-joint position is published until one is answered",
                throttle_duration_sec=5.0,
            )
        if client is None or not client.service_is_ready():
            with self._lock:
                self._poll_future = None
            self.get_logger().warning(
                "gripper position unread: the vendor's get_gripper_position is not available",
                throttle_duration_sec=5.0,
            )
            return
        with self._lock:
            future = client.call_async(GetFloat32.Request())
            self._poll_future = future
        future.add_done_callback(self._on_position)

    def _on_position(self, future) -> None:
        with self._lock:
            if self._poll_future is not future:
                return  # abandoned at its deadline, or the node was cleaned up
            self._poll_future = None
        if future.cancelled():
            return
        config, state_map, publisher = self._config, self._state_map, self._state_publisher
        error = future.exception()
        response = None if error is not None else future.result()
        if response is None or response.ret != 0 or config is None or state_map is None:
            detail = error if error is not None else (
                f"vendor code {response.ret}" if response is not None else "unconfigured"
            )
            self.get_logger().error(
                f"get_gripper_position failed ({detail}); no drive-joint position is "
                "published rather than a stale one",
                throttle_duration_sec=5.0,
            )
            return
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = [config["drive_joint"]]
        message.position = [state_map.inverse(float(response.data))]
        if publisher is not None:
            publisher.publish(message)

    # ------------------------------------------------------------------ #
    # The action server
    # ------------------------------------------------------------------ #

    def _on_goal(self, request: GripperCommand.Goal) -> GoalResponse:
        with self._lock:
            active = self._active
        if not active:
            self.get_logger().warning("gripper goal rejected: the relay is not active")
            return GoalResponse.REJECT
        assert self._gate is not None and self._vendor is not None
        if not self._gate.permits_motion():
            self.get_logger().warning(f"gripper goal rejected: {self._gate.why_closed()}")
            return GoalResponse.REJECT
        if not self._vendor.server_is_ready():
            self.get_logger().error(
                f"gripper goal rejected: {self._config['vendor_action_name']} is not available"
            )
            return GoalResponse.REJECT
        if not math.isfinite(request.command.position):
            self.get_logger().error(
                f"gripper goal rejected: position {request.command.position}"
            )
            return GoalResponse.REJECT
        with self._lock:
            busy = self._busy is not None or self._current is not None
        if busy:
            self.get_logger().warning(
                "gripper goal rejected: a vendor goal is still running, and the vendor "
                "cannot be preempted (see the module docstring)"
            )
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_accepted(self, goal_handle) -> None:
        forwarded = _Forwarded(handle=goal_handle)
        with self._lock:
            # Two goals accepted at once both passed `_on_goal`; the later one
            # is not executed, rather than preempting the first.
            taken = self._busy is not None or self._current is not None
            if not taken:
                self._current = forwarded
                self._busy = forwarded
        goal_handle.execute()

    def _on_cancel(self, goal_handle) -> CancelResponse:
        with self._lock:
            forwarded = self._current
        if forwarded is None or forwarded.handle is not goal_handle:
            return CancelResponse.REJECT
        forwarded.cancel_requested = True
        vendor = forwarded.vendor
        if vendor is None:
            # The vendor has not answered the goal yet; `_on_vendor_answer`
            # sees the flag and forwards the cancel when it does.
            return CancelResponse.ACCEPT
        self._forward_cancel(forwarded, conclude=True)
        return CancelResponse.ACCEPT

    async def _execute(self, goal_handle) -> GripperCommand.Result:
        with self._lock:
            forwarded = self._current
            active = self._active
        if forwarded is None or forwarded.handle is not goal_handle:
            # Refused at acceptance: another goal holds the gripper.
            goal_handle.abort()
            return self._result(math.nan)
        # Checked again here, immediately before the vendor is commanded: the
        # deadman, a cancel or a deactivate may all have arrived since
        # `_on_goal` said yes.
        gate = self._gate
        refusal = None
        if forwarded.finish.done():
            refusal = "ended before it was sent"
        elif not active:
            refusal = "the relay is not active"
        elif gate is None or not gate.permits_motion():
            refusal = gate.why_closed() if gate is not None else "no deadman gate"
        if refusal is not None:
            self._end(forwarded, _DEADMAN, f"not sent to the vendor: {refusal}")
            with self._lock:
                if self._busy is forwarded:
                    self._busy = None
                if self._current is forwarded:
                    self._current = None
            kind, payload = forwarded.finish.result()
            return self._conclude(forwarded, kind, payload)
        assert self._map is not None and self._vendor is not None and self._config
        command = goal_handle.request.command
        target = self._map.clamp(command.position)
        if target != command.position:
            self.get_logger().warning(
                f"gripper position {command.position} clamped to {target}, the drive "
                "joint's declared travel"
            )
        vendor_goal = GripperCommand.Goal()
        vendor_goal.command.position = self._map.forward(target)
        vendor_goal.command.max_effort = command.max_effort

        timeout_s = self._config["result_timeout_s"]
        forwarded.deadline = self.create_timer(
            timeout_s,
            lambda: self._on_deadline(forwarded, timeout_s),
            callback_group=self._group,
            clock=self._steady,
        )
        self.get_logger().info(
            f"gripper {command.position:g} -> vendor {vendor_goal.command.position:g}"
        )
        sent = self._vendor.send_goal_async(
            vendor_goal,
            feedback_callback=lambda message: self._on_vendor_feedback(forwarded, message),
        )
        sent.add_done_callback(lambda done: self._on_vendor_answer(forwarded, done))

        kind, payload = await forwarded.finish

        # The deadline is NOT destroyed here: it also bounds the vendor goal,
        # which may outlive ours (`_busy`).
        with self._lock:
            if self._current is forwarded:
                self._current = None
        return self._conclude(forwarded, kind, payload)

    def _on_deadline(self, forwarded: _Forwarded, timeout_s: float) -> None:
        self._end(forwarded, _TIMED_OUT, f"no vendor result within {timeout_s:g} s")
        self._vendor_over(forwarded, f"no vendor result within {timeout_s:g} s")

    def _vendor_over(self, forwarded: _Forwarded, why: str) -> None:
        """Record that the vendor goal behind ``forwarded`` is over, or no longer waited for."""
        with self._lock:
            freed = self._busy is forwarded
            if freed:
                self._busy = None
            timer, forwarded.deadline = forwarded.deadline, None
        if timer is not None:
            self.destroy_timer(timer)
        if freed:
            self.get_logger().info(f"the gripper takes a new goal: {why}")

    # ------------------------------------------------------------------ #
    # The vendor's side
    # ------------------------------------------------------------------ #

    def _on_vendor_answer(self, forwarded: _Forwarded, future) -> None:
        error = future.exception()
        vendor = None if error is not None else future.result()
        if vendor is None or not vendor.accepted:
            self._end(forwarded, _REFUSED, f"the vendor did not accept the goal ({error})")
            self._vendor_over(forwarded, "the vendor did not accept the last goal")
            return
        forwarded.vendor = vendor
        # The vendor's result is followed in every case: it is what says the
        # vendor goal is over (`_busy`), whether or not ours still waits on it.
        result = vendor.get_result_async()
        result.add_done_callback(lambda done: self._on_vendor_result(forwarded, done))
        if forwarded.finish.done():
            # Ended while the vendor was answering: asked to cancel, which the
            # vendor acknowledges and does not act on.
            self._forward_cancel(forwarded, conclude=False)
        elif forwarded.cancel_requested:
            self._forward_cancel(forwarded, conclude=True)

    def _on_vendor_result(self, forwarded: _Forwarded, future) -> None:
        error = future.exception()
        if error is not None:
            self._end(forwarded, _REFUSED, f"the vendor result failed: {error}")
        else:
            self._end(forwarded, _VENDOR, future.result())
        self._vendor_over(forwarded, "the vendor reported the last goal's result")

    def _on_vendor_feedback(self, forwarded: _Forwarded, message) -> None:
        if self._map is None:
            return
        vendor = message.feedback
        position = self._map.inverse(vendor.position)
        forwarded.position = position
        feedback = GripperCommand.Feedback()
        feedback.position = position
        feedback.effort = vendor.effort
        feedback.stalled = vendor.stalled
        feedback.reached_goal = vendor.reached_goal
        if forwarded.handle.is_active and not forwarded.finish.done():
            forwarded.handle.publish_feedback(feedback)

    def _forward_cancel(self, forwarded: _Forwarded, conclude: bool) -> None:
        """Ask the vendor to cancel; with ``conclude``, end ours once it answers.

        Ending ours on the vendor's answer rather than at once is what orders
        the two: by then the action server has moved our goal to CANCELING, so
        it can be reported CANCELED rather than ABORTED.
        """
        vendor = forwarded.vendor
        if vendor is None or self._vendor is None or not self._vendor.server_is_ready():
            if conclude:
                self._end(forwarded, _CANCELLED, "the vendor could not be reached to cancel")
            return
        cancelled = vendor.cancel_goal_async()
        if conclude:
            cancelled.add_done_callback(
                lambda _done: self._end(
                    forwarded,
                    _CANCELLED,
                    "cancel forwarded; the vendor acknowledges it and does not stop the jaws",
                )
            )

    def _on_gate_closed(self, reason: str) -> None:
        with self._lock:
            current = self._current
        if current is not None:
            self._end(current, _DEADMAN, reason)

    # ------------------------------------------------------------------ #
    # Ending a goal
    # ------------------------------------------------------------------ #

    def _end(self, forwarded: _Forwarded, kind: str, payload) -> None:
        """Finish ``forwarded`` once, whichever event gets there first."""
        with self._lock:
            if forwarded.finish.done():
                return
            forwarded.finish.set_result((kind, payload))
        if kind in (_TIMED_OUT, _DEADMAN, _INACTIVE):
            self.get_logger().warning(f"gripper goal ended, {kind}: {payload}")
            if forwarded.vendor is not None:
                self._forward_cancel(forwarded, conclude=False)

    def _conclude(self, forwarded: _Forwarded, kind: str, payload) -> GripperCommand.Result:
        handle = forwarded.handle
        if kind == _VENDOR:
            assert self._map is not None
            vendor = payload.result
            result = self._result(self._map.inverse(vendor.position))
            result.effort = vendor.effort
            result.stalled = vendor.stalled
            result.reached_goal = vendor.reached_goal
            if not vendor.stalled and not vendor.reached_goal:
                self.get_logger().info(
                    "the vendor reported neither stalled nor reached_goal; both are "
                    "forwarded false, as reported (ADR-0063 left the SDK stall path "
                    "unestablished)"
                )
            if payload.status == GoalStatus.STATUS_SUCCEEDED:
                handle.succeed()
            elif payload.status == GoalStatus.STATUS_CANCELED and handle.is_cancel_requested:
                handle.canceled()
            else:
                self.get_logger().error(
                    f"the vendor ended the gripper goal with status {payload.status}"
                )
                handle.abort()
            return result

        result = self._result(forwarded.position)
        if kind == _CANCELLED and handle.is_cancel_requested:
            self.get_logger().info(f"gripper goal cancelled: {payload}")
            handle.canceled()
        else:
            if kind not in (_TIMED_OUT, _DEADMAN, _INACTIVE):
                self.get_logger().error(f"gripper goal aborted, {kind}: {payload}")
            handle.abort()
        return result

    @staticmethod
    def _result(position: float) -> GripperCommand.Result:
        result = GripperCommand.Result()
        result.position = position
        return result


def main() -> int:
    return run(GripperRelay)


if __name__ == "__main__":
    sys.exit(main())
