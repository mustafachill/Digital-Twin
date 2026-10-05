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

"""The vendor driver's endpoints, faked, and a harness to drive a node against them.

**Test-only, and nothing here reaches hardware.** Each fake is a service or an
action server in the TEST's own node, under a test-chosen name, recording what
it was asked. They imitate exactly the parts of `xarm_api`'s driver that the
adapters depend on, as read in the pinned source:

- the linear-track services, `set_state` and `set_mode` answer with `ret`, 0
  for success (`xarm_api/src/xarm_driver_service.cpp`); `set_mode` stops the
  arm before it changes the mode (`:543-550`), and the arm's state is one
  value any client may set — UFACTORY Studio, the pendant, another node;
- the gripper action takes and reports 0.0 (open) to 0.85 (closed), turning a
  goal into a pulse target as ``|850 - position * 1000|`` and pulses back as
  ``|850 - pulses| / 1000``; `get_gripper_position` reports the raw pulses,
  850 open to 0 closed (`xarm_api/src/xarm_driver.cpp:507-515`). It fills only
  `position` in its feedback and result, never `stalled` or `reached_goal`,
  accepts a cancel and does not stop for it (`_xarm_gripper_action_execute`).

Where a test needs the vendor to do something else — fail, stall, hold — it
says so through the fake's attributes, never by editing the fake per test.

The harness spins the test node on a background executor, so the fakes answer
while a test method waits; every wait ends the moment its condition holds.
"""

from __future__ import annotations

from collections.abc import Callable
import threading
import time
import uuid

from cite_interfaces.msg import DeadmanState, TwinHeartbeat
from cite_interfaces.qos import LATCHED, STATE
from control_msgs.action import GripperCommand
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState, GetState
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from xarm_msgs.srv import Call, GetFloat32, GetInt16, LinearMotorSetPos, SetInt16

#: How long a test waits for something that should already be on its way.
SETTLE_S = 20.0

#: A fake gripper goal's behaviour is chosen by its `max_effort`, which the
#: relay forwards unchanged — so the test steers the vendor through the goal it
#: sends, as `cite_twin`'s fake side does.
SUCCEED = 0.0
HOLD = 1.0
STALL = 2.0


class Harness:
    """A test node, spun in the background, with helpers to wait and transition."""

    def __init__(self, name: str) -> None:
        rclpy.init()
        self.node = Node(name)
        self.group = ReentrantCallbackGroup()
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(self.node)
        self._thread = threading.Thread(target=self.executor.spin, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self.executor.shutdown()
        self.node.destroy_node()
        rclpy.shutdown()

    @staticmethod
    def wait_for(predicate: Callable[[], object], what: str, timeout_s: float = SETTLE_S):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            threading.Event().wait(0.02)
        raise AssertionError(f"{what} did not happen within {timeout_s:g} s")

    @staticmethod
    def hold_for(predicate: Callable[[], object], what: str, duration_s: float) -> None:
        """Assert ``predicate`` stays false for ``duration_s``: a NEGATIVE assertion.

        Bounded by construction — a thing that must not happen can only be
        watched for a while — and used only where the claim is "refused".
        """
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            if predicate():
                raise AssertionError(f"{what} happened, and must not")
            threading.Event().wait(0.02)

    def call(self, client, request, what: str):
        self.wait_for(client.service_is_ready, f"{client.srv_name} appeared")
        future = client.call_async(request)
        self.wait_for(future.done, what)
        return future.result()

    def transition(self, node_name: str, transition_id: int) -> bool:
        client = self.node.create_client(ChangeState, f"/{node_name}/change_state")
        try:
            request = ChangeState.Request()
            request.transition = Transition(id=transition_id)
            return self.call(client, request, f"{node_name} transition {transition_id}").success
        finally:
            self.node.destroy_client(client)

    def state(self, node_name: str) -> str:
        client = self.node.create_client(GetState, f"/{node_name}/get_state")
        try:
            return self.call(client, GetState.Request(), f"{node_name} state").current_state.label
        finally:
            self.node.destroy_client(client)

    def bring_up(self, node_name: str) -> None:
        assert self.transition(node_name, Transition.TRANSITION_CONFIGURE), "configure"
        assert self.transition(node_name, Transition.TRANSITION_ACTIVATE), "activate"


class FakeTrack:
    """`set_linear_motor_pos`, `_speed`, `get_linear_motor_pos`, `set_linear_motor_stop`.

    ``serve`` names which of the four to advertise. A fake is never withdrawn
    mid-test: measured in this image, a service whose callback has run once
    under a `MultiThreadedExecutor` stays advertised after
    `Node.destroy_service`, so "the service went away" is tested as a service
    that was never there and appears later.
    """

    SET = "set_linear_motor_pos"
    SPEED = "set_linear_motor_speed"
    GET = "get_linear_motor_pos"
    STOP = "set_linear_motor_stop"

    def __init__(
        self, harness: Harness, namespace: str, serve: tuple[str, ...] = (SET, SPEED, GET, STOP)
    ) -> None:
        self.namespace = namespace
        self.position_mm = 100
        self.position_ret = 0
        self.set_ret = 0
        self.set_requests: list[LinearMotorSetPos.Request] = []
        #: Every speed written, in vendor units per second, and the `ret` it is
        #: answered with.
        self.speeds: list[int] = []
        self.speed_ret = 0
        self.stops = 0
        #: "set" when a move's answer is sent, "speed" when a speed write
        #: arrives and "stop" when a stop arrives, in that order: what a stop
        #: overtaken by a move looks like, and a move before its speed.
        self.calls: list[str] = []
        #: How many of the next stops answer with a vendor error (ret 1).
        self.stop_failures = 0
        #: When cleared, `set_linear_motor_pos` does not answer until it is set:
        #: a vendor that is slow to answer, which is what makes a held command
        #: observable.
        self.answer_set = threading.Event()
        self.answer_set.set()
        #: The same for `get_linear_motor_pos`: a position read that hangs.
        self.answer_get = threading.Event()
        self.answer_get.set()
        handlers = {
            self.SET: (LinearMotorSetPos, self._on_set),
            self.SPEED: (SetInt16, self._on_speed),
            self.GET: (GetInt16, self._on_get),
            self.STOP: (Call, self._on_stop),
        }
        self._services = [
            harness.node.create_service(
                handlers[name][0], f"{namespace}/{name}", handlers[name][1],
                callback_group=harness.group,
            )
            for name in serve
        ]

    def _on_set(self, request, response):
        self.set_requests.append(request)
        self.answer_set.wait(timeout=SETTLE_S)
        response.ret = self.set_ret
        response.message = "fake"
        self.calls.append("set")
        return response

    def _on_speed(self, request, response):
        self.calls.append("speed")
        self.speeds.append(request.data)
        response.ret = self.speed_ret
        response.message = "fake"
        return response

    def _on_get(self, _request, response):
        self.answer_get.wait(timeout=SETTLE_S)
        response.ret = self.position_ret
        response.data = self.position_mm
        return response

    def _on_stop(self, _request, response):
        self.calls.append("stop")
        self.stops += 1
        if self.stop_failures > 0:
            self.stop_failures -= 1
            response.ret = 1
        else:
            response.ret = 0
        return response


class FakeArmState:
    """`set_state` and `set_mode`, and the one arm state every client shares.

    ``state`` starts at 0 (START), which is where the vendor plugin's own
    activation leaves the arm. ``flip`` is another client setting it.
    """

    def __init__(
        self,
        harness: Harness,
        namespace: str,
        on_call: Callable[[str, int], None] | None = None,
    ) -> None:
        self.requests: list[int] = []
        self.modes: list[int] = []
        #: Told of every call as it arrives, ("set_state" or "set_mode", n).
        self._on_call = on_call
        #: How many of the next set_mode calls answer with a vendor error.
        self.mode_failures = 0
        #: When set, the NEXT set_mode call is held unanswered until
        #: ``mode_release`` is set; ``mode_held`` says it arrived.
        self.hold_mode = threading.Event()
        self.mode_release = threading.Event()
        self.mode_held = threading.Event()
        #: Every call in arrival order, as ("set_state", n) or ("set_mode", n).
        self.calls: list[tuple[str, int]] = []
        #: Steady-clock arrival time of every set_mode call.
        self.mode_times: list[float] = []
        self.state = 0
        self.mode = 1
        self.failures = 0
        #: When set, the NEXT set_state call is held unanswered until
        #: ``release`` is set: a vendor that does not answer.
        self.hold_next = threading.Event()
        self.release = threading.Event()
        self._lock = threading.Lock()
        self._services = [
            harness.node.create_service(
                SetInt16, f"{namespace}/set_state", self._on_set_state,
                callback_group=harness.group,
            ),
            harness.node.create_service(
                SetInt16, f"{namespace}/set_mode", self._on_set_mode,
                callback_group=harness.group,
            ),
        ]

    def flip(self, state: int) -> None:
        """Another client (Studio, the pendant) sets the arm's state."""
        with self._lock:
            self.state = state

    def _on_set_state(self, request, response):
        if self._on_call is not None:
            self._on_call("set_state", request.data)
        with self._lock:
            hold = self.hold_next.is_set()
            self.hold_next.clear()
        if hold:
            self.release.wait(timeout=SETTLE_S)
        with self._lock:
            self.requests.append(request.data)
            self.calls.append(("set_state", request.data))
            if self.failures > 0:
                self.failures -= 1
                response.ret = 1
            else:
                self.state = request.data
                response.ret = 0
        return response

    def _on_set_mode(self, request, response):
        if self._on_call is not None:
            self._on_call("set_mode", request.data)
        with self._lock:
            self.modes.append(request.data)
            self.mode_times.append(time.monotonic())
            self.calls.append(("set_mode", request.data))
            # The vendor's service stops the arm before it changes the mode.
            self.state = 4
            hold = self.hold_mode.is_set()
            self.hold_mode.clear()
        if hold:
            self.mode_held.set()
            self.mode_release.wait(timeout=SETTLE_S)
        with self._lock:
            if self.mode_failures > 0:
                self.mode_failures -= 1
                response.ret = 1
            else:
                self.mode = request.data
                response.ret = 0
        return response


class FakeDeadman:
    """A deadman's `DeadmanState`, republished on a timer as the real one is."""

    PERIOD_S = 0.05

    def __init__(self, harness: Harness, topic: str) -> None:
        self._harness = harness
        self._topic = topic
        self._lock = threading.Lock()
        self.message: DeadmanState | None = None
        #: Cleared to make this deadman HANG: alive on the graph, silent.
        self.publishing = threading.Event()
        self.publishing.set()
        self.publisher = harness.node.create_publisher(DeadmanState, topic, LATCHED)
        self._timer = harness.node.create_timer(
            self.PERIOD_S, self._republish, callback_group=harness.group
        )

    def say(self, state: int, detail: str) -> None:
        with self._lock:
            self.message = DeadmanState(state=state, detail=detail)
        self.publisher.publish(self.message)

    def _republish(self) -> None:
        with self._lock:
            message = self.message
        if message is not None and self.publishing.is_set():
            self.publisher.publish(message)


class FakeGripper:
    """The vendor's `GripperCommand` server, as `xarm_driver.cpp` behaves."""

    #: `xarm_gripper.max_pos`, the vendor's default (`xarm_params.yaml`).
    MAX_POS = 850.0

    def __init__(self, harness: Harness, name: str, state_service: str = "") -> None:
        self.goals: list[float] = []
        self.cancels = 0
        #: How many vendor goals are executing now.
        self.running = 0
        #: What `get_gripper_position` reports, in the vendor's pulses.
        self.pulses = 850.0
        #: How many position reads arrived, answered or not.
        self.position_requests = 0
        #: When cleared, `get_gripper_position` does not answer until it is
        #: set: a vendor read that hangs.
        self.answer_position = threading.Event()
        self.answer_position.set()
        self._lock = threading.Lock()
        self._release = threading.Event()
        if state_service:
            self._state = harness.node.create_service(
                GetFloat32, state_service, self._on_position, callback_group=harness.group
            )
        self._server = ActionServer(
            harness.node,
            GripperCommand,
            name,
            execute_callback=self._execute,
            goal_callback=lambda _goal: GoalResponse.ACCEPT,
            cancel_callback=self._on_cancel,
            callback_group=harness.group,
        )

    @classmethod
    def to_pulses(cls, position: float) -> float:
        """Convert a goal as the vendor does, `_xarm_gripper_pos_convert(pos, true)`."""
        return abs(cls.MAX_POS - position * 1000.0)

    @classmethod
    def from_pulses(cls, pulses: float) -> float:
        """Convert pulses back as the vendor does, `_xarm_gripper_pos_convert(pos)`."""
        return abs(cls.MAX_POS - pulses) / 1000.0

    def _on_position(self, _request, response):
        with self._lock:
            self.position_requests += 1
        self.answer_position.wait(timeout=SETTLE_S)
        response.ret = 0
        response.data = self.pulses
        return response

    def release_held(self) -> None:
        """Let every held vendor goal finish, as the jaws eventually would."""
        self._release.set()

    def hold_again(self) -> None:
        """Make the next HOLD goal wait for :meth:`release_held` again."""
        self._release.clear()

    def _on_cancel(self, _goal_handle) -> CancelResponse:
        # Accepted, and NOT acted on: the vendor's execute loop has its cancel
        # check commented out.
        self.cancels += 1
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle):
        with self._lock:
            self.running += 1
        try:
            command = goal_handle.request.command
            self.goals.append(command.position)
            target = self.to_pulses(command.position)
            # Halfway there, reported as the vendor reports it.
            self.pulses = (self.pulses + target) / 2.0
            feedback = GripperCommand.Feedback()
            feedback.position = self.from_pulses(self.pulses)
            goal_handle.publish_feedback(feedback)
            if command.max_effort == HOLD:
                self._release.wait(timeout=SETTLE_S * 3)
            self.pulses = target
            result = GripperCommand.Result()
            result.position = self.from_pulses(self.pulses)
            if command.max_effort == STALL:
                # Not the vendor: it never sets `stalled`. Used only to show
                # the relay forwards what it is given.
                result.stalled = True
            # The vendor succeeds whenever the motion ends, from CANCELING too.
            goal_handle.succeed()
            return result
        finally:
            with self._lock:
                self.running -= 1


class FakeBoundary:
    """The twin boundary's heartbeat, published from a timer while ``beating`` is set."""

    #: Ten heartbeats per half-second timeout: the margin a deadman runs with.
    PERIOD_S = 0.05

    def __init__(self, harness: Harness, zone: str) -> None:
        self._harness = harness
        self.zone = zone
        self.boundary_id = str(uuid.uuid4())
        self.sequence = 0
        self.beating = threading.Event()
        self._lock = threading.Lock()
        self.publisher = harness.node.create_publisher(TwinHeartbeat, TwinHeartbeat.TOPIC, STATE)
        self._timer = harness.node.create_timer(
            self.PERIOD_S, self._beat, callback_group=harness.group
        )

    def _beat(self) -> None:
        with self._lock:
            if not self.beating.is_set() or self.publisher is None:
                return
            self.sequence += 1
            self.publisher.publish(
                TwinHeartbeat(
                    zone=self.zone, boundary_id=self.boundary_id, sequence=self.sequence
                )
            )

    def die(self) -> None:
        """Make the boundary process go away: its publisher disappears."""
        with self._lock:
            if self.publisher is not None:
                self._harness.node.destroy_publisher(self.publisher)
            self.publisher = None

    def restart(self) -> None:
        """Start a new boundary process: a new publisher, a new id, counting from 1."""
        with self._lock:
            self.sequence = 0
            self.boundary_id = str(uuid.uuid4())
            self.publisher = self._harness.node.create_publisher(
                TwinHeartbeat, TwinHeartbeat.TOPIC, STATE
            )
