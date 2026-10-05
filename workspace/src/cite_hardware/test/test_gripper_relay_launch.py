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

"""The gripper relay against a faked vendor gripper action (ADR-0070 item 4).

The vendor range here runs BACKWARDS against the drive joint's (open at 850,
closed at 0) on purpose: a relay that forgot to map would forward 0.425 as
0.425 and fail every assertion, where a range equal to the drive joint's would
let it pass. The numbers are test inputs, not the asset's facts.
"""

from __future__ import annotations

import os
import sys
import unittest

from action_msgs.msg import GoalStatus
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
from control_msgs.action import GripperCommand
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
from rclpy.action import ActionClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import FakeGripper, Harness, HOLD, SETTLE_S, STALL, SUCCEED  # noqa: E402

NODE = "gripper_relay"
ACTION = "/test/gripper_controller/gripper_cmd"
VENDOR_ACTION = "/test_vendor/xarm_gripper/gripper_action"
DEADMAN = "/test/deadman_state"
RESULT_TIMEOUT_S = 4.0

PARAMETERS = {
    "action_name": ACTION,
    "vendor_action_name": VENDOR_ACTION,
    "open_position": 0.0,
    "closed_position": 0.85,
    "vendor_open_position": 850.0,
    "vendor_closed_position": 0.0,
    "result_timeout_s": RESULT_TIMEOUT_S,
    "deadman_state_topic": DEADMAN,
}


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    relay = Node(
        package="cite_hardware",
        executable="gripper_relay.py",
        name=NODE,
        parameters=[PARAMETERS],
        output="screen",
    )
    return (
        launch.LaunchDescription([relay, launch_testing.actions.ReadyToTest()]),
        {"relay": relay},
    )


class TestGripperRelay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Harness("gripper_relay_test")
        node = cls.harness.node
        cls.vendor = FakeGripper(cls.harness, VENDOR_ACTION)
        cls.deadman = node.create_publisher(DeadmanState, DEADMAN, LATCHED)
        cls.client = ActionClient(node, GripperCommand, ACTION, callback_group=cls.harness.group)
        cls.harness.bring_up(NODE)
        cls.harness.wait_for(cls.client.server_is_ready, f"{ACTION} served")

    @classmethod
    def tearDownClass(cls):
        cls.vendor.release_held()
        cls.client.destroy()
        cls.harness.close()

    def setUp(self):
        self.vendor.hold_again()

    def tearDown(self):
        # A held vendor goal occupies a thread of the test's executor; let it go.
        self.vendor.release_held()

    def _deadman(self, proc_output, state: int) -> None:
        """Publish a deadman state and wait until the relay has received it."""
        type(self)._sequence = getattr(type(self), "_sequence", 0) + 1
        detail = f"test state {type(self)._sequence}."
        self.deadman.publish(DeadmanState(state=state, detail=detail))
        proc_output.assertWaitFor(expected_output=detail, timeout=SETTLE_S)

    def _send(self, position: float, behaviour: float):
        goal = GripperCommand.Goal()
        goal.command.position = position
        goal.command.max_effort = behaviour
        self.feedback: list[float] = []
        future = self.client.send_goal_async(
            goal, feedback_callback=lambda m: self.feedback.append(m.feedback.position)
        )
        self.harness.wait_for(future.done, "the relay answered the goal")
        return future.result()

    def _result_of(self, handle, timeout_s: float = SETTLE_S):
        future = handle.get_result_async()
        self.harness.wait_for(future.done, "the relay's result", timeout_s)
        return future.result()

    # ------------------------------------------------------------------ #

    def test_a_goal_reaches_the_vendor_mapped_and_comes_back_mapped(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.vendor.goals)
        handle = self._send(0.425, SUCCEED)
        self.assertTrue(handle.accepted)
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_SUCCEEDED)
        self.assertAlmostEqual(self.vendor.goals[before], 425.0)
        self.assertAlmostEqual(outcome.result.position, 0.425)
        # The vendor reports neither flag, and neither is invented.
        self.assertFalse(outcome.result.stalled)
        self.assertFalse(outcome.result.reached_goal)

    def test_feedback_is_mapped_back_too(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        handle = self._send(0.85, SUCCEED)  # vendor 0; its feedback is half of that
        self._result_of(handle)
        self.harness.wait_for(lambda: self.feedback, "feedback reached the client")
        self.assertAlmostEqual(self.feedback[0], 0.85)

    def test_a_vendor_stall_is_forwarded_as_reported(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        outcome = self._result_of(self._send(0.6, STALL))
        self.assertTrue(outcome.result.stalled)
        self.assertFalse(outcome.result.reached_goal)

    def test_a_command_beyond_the_travel_is_clamped(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.vendor.goals)
        self._result_of(self._send(1.2, SUCCEED))
        self.assertAlmostEqual(self.vendor.goals[before], 0.0)

    def test_a_cancel_is_forwarded_to_the_vendor(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        cancels = self.vendor.cancels
        before = len(self.vendor.goals)
        handle = self._send(0.5, HOLD)
        self.assertTrue(handle.accepted)
        self.harness.wait_for(lambda: len(self.vendor.goals) > before, "the vendor goal")
        cancelled = handle.cancel_goal_async()
        self.harness.wait_for(cancelled.done, "the cancel was answered")
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_CANCELED)
        self.assertGreater(self.vendor.cancels, cancels)

    def test_a_newer_goal_preempts_and_cancels_the_vendor_goal(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        cancels = self.vendor.cancels
        before = len(self.vendor.goals)
        first = self._send(0.5, HOLD)
        self.harness.wait_for(lambda: len(self.vendor.goals) > before, "the first vendor goal")
        second = self._send(0.2, SUCCEED)
        self.assertTrue(second.accepted)
        outcome = self._result_of(first)
        # ABORTED, where GripperActionController reports CANCELED: rclpy cannot
        # cancel a goal no client asked to cancel (see gripper_relay.py).
        self.assertEqual(outcome.status, GoalStatus.STATUS_ABORTED)
        self.harness.wait_for(
            lambda: self.vendor.cancels > cancels, "the preempted vendor goal cancelled"
        )
        self.assertEqual(self._result_of(second).status, GoalStatus.STATUS_SUCCEEDED)

    def test_a_tripped_deadman_aborts_the_goal_in_flight(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        cancels = self.vendor.cancels
        handle = self._send(0.5, HOLD)
        self.assertTrue(handle.accepted)
        self._deadman(proc_output, DeadmanState.STATE_TRIPPED)
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_ABORTED)
        self.harness.wait_for(
            lambda: self.vendor.cancels > cancels, "the vendor goal cancelled on the trip"
        )

    def test_no_goal_is_accepted_unless_the_deadman_is_healthy(self, proc_output):
        for state in (
            DeadmanState.STATE_AWAITING,
            DeadmanState.STATE_TRIPPED,
            DeadmanState.STATE_INACTIVE,
        ):
            self._deadman(proc_output, state)
            before = len(self.vendor.goals)
            handle = self._send(0.3, SUCCEED)
            self.assertFalse(handle.accepted, f"accepted with the deadman in state {state}")
            self.assertEqual(len(self.vendor.goals), before)

    def test_a_vendor_that_never_answers_is_bounded(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        handle = self._send(0.5, HOLD)
        outcome = self._result_of(handle, timeout_s=RESULT_TIMEOUT_S + SETTLE_S)
        self.assertEqual(outcome.status, GoalStatus.STATUS_ABORTED)
        proc_output.assertWaitFor(
            expected_output=f"no vendor result within {RESULT_TIMEOUT_S:g} s",
            timeout=SETTLE_S,
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_relay_exits_cleanly(self, proc_info, relay):
        self.assertIn(proc_info[relay].returncode, (0, -2, -15))
