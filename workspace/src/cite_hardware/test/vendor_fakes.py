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

- the linear-track services and `set_state` answer with `ret`, 0 for success
  (`xarm_api/src/xarm_driver_service.cpp`);
- the gripper action fills only `position` in its feedback and result, never
  `stalled` or `reached_goal`, accepts a cancel and does not stop for it
  (`xarm_api/src/xarm_driver.cpp`, `_xarm_gripper_action_execute`).

Where a test needs the vendor to do something else — fail, stall, hold — it
says so through the fake's attributes, never by editing the fake per test.

The harness spins the test node on a background executor, so the fakes answer
while a test method waits; every wait ends the moment its condition holds.
"""

from __future__ import annotations

from collections.abc import Callable
import threading
import time

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
    """`set_linear_motor_pos`, `get_linear_motor_pos`, `set_linear_motor_stop`.

    ``serve`` names which of the three to advertise. A fake is never withdrawn
    mid-test: measured in this image, a service whose callback has run once
    under a `MultiThreadedExecutor` stays advertised after
    `Node.destroy_service`, so "the service went away" is tested as a service
    that was never there and appears later.
    """

    SET = "set_linear_motor_pos"
    GET = "get_linear_motor_pos"
    STOP = "set_linear_motor_stop"

    def __init__(
        self, harness: Harness, namespace: str, serve: tuple[str, ...] = (SET, GET, STOP)
    ) -> None:
        self.namespace = namespace
        self.position_mm = 100
        self.position_ret = 0
        self.set_ret = 0
        self.set_requests: list[LinearMotorSetPos.Request] = []
        self.stops = 0
        #: When cleared, `set_linear_motor_pos` does not answer until it is set:
        #: a vendor that is slow to answer, which is what makes a held command
        #: observable.
        self.answer_set = threading.Event()
        self.answer_set.set()
        handlers = {
            self.SET: (LinearMotorSetPos, self._on_set),
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
        return response

    def _on_get(self, _request, response):
        response.ret = self.position_ret
        response.data = self.position_mm
        return response

    def _on_stop(self, _request, response):
        self.stops += 1
        response.ret = 0
        return response


class FakeArmState:
    """`set_state`, failing its first ``failures`` calls when asked to."""

    def __init__(self, harness: Harness, namespace: str) -> None:
        self.requests: list[int] = []
        self.failures = 0
        self._service = harness.node.create_service(
            SetInt16, f"{namespace}/set_state", self._on_set_state,
            callback_group=harness.group,
        )

    def _on_set_state(self, request, response):
        self.requests.append(request.data)
        if self.failures > 0:
            self.failures -= 1
            response.ret = 1
        else:
            response.ret = 0
        return response


class FakeGripper:
    """The vendor's `GripperCommand` server, as `xarm_driver.cpp` behaves."""

    def __init__(self, harness: Harness, name: str, state_service: str = "") -> None:
        self.goals: list[float] = []
        self.cancels = 0
        #: What `get_gripper_position` reports, in the vendor's pulses.
        self.pulses = 850.0
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

    def _on_position(self, _request, response):
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
        command = goal_handle.request.command
        self.goals.append(command.position)
        feedback = GripperCommand.Feedback()
        feedback.position = command.position / 2.0
        goal_handle.publish_feedback(feedback)
        if command.max_effort == HOLD:
            self._release.wait(timeout=SETTLE_S * 3)
        result = GripperCommand.Result()
        result.position = command.position
        if command.max_effort == STALL:
            result.stalled = True
        # The vendor succeeds whenever the motion ends, from CANCELING too.
        goal_handle.succeed()
        return result
