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

The fake vendor converts as the real one does: its action takes and reports
0.0 (open) to 0.85 (closed), and its `get_gripper_position` reports pulses,
850 open to 0 closed (`vendor_fakes.FakeGripper`). The drive joint's range here
is 0.0 to 1.7 on purpose, twice the vendor's: a relay that forgot to map would
forward 0.85 as 0.85 and fail every assertion, where a range equal to the
vendor's would let it pass. The drive-joint numbers are test inputs, not the
asset's facts.
"""

from __future__ import annotations

import os
import sys
import unittest

from action_msgs.msg import GoalStatus
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import STATE
from control_msgs.action import GripperCommand
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import (  # noqa: E402
    FakeDeadman,
    FakeGripper,
    Harness,
    HOLD,
    SETTLE_S,
    STALL,
    SUCCEED,
)

NODE = "gripper_relay"
ACTION = "/test/gripper_controller/gripper_cmd"
VENDOR_ACTION = "/test_vendor/xarm_gripper/gripper_action"
DEADMAN = "/test/deadman_state"
RESULT_TIMEOUT_S = 4.0
DRIVE_JOINT = "test_drive_joint"
JOINT_STATES = "/test/joint_states"
GET_POSITION = "/test_vendor/xarm/get_gripper_position"
#: The drive joint's closed position in this test: twice the vendor's 0.85.
CLOSED = 1.7

PARAMETERS = {
    "action_name": ACTION,
    "vendor_action_name": VENDOR_ACTION,
    "open_position": 0.0,
    "closed_position": CLOSED,
    # The vendor action's own unit: 0.0 open, 0.85 closed.
    "vendor_open_position": 0.0,
    "vendor_closed_position": 0.85,
    "result_timeout_s": RESULT_TIMEOUT_S,
    "deadman_state_topic": DEADMAN,
    "deadman_state_max_age_s": 0.5,
    "drive_joint": DRIVE_JOINT,
    "joint_state_topic": JOINT_STATES,
    "get_position_service": GET_POSITION,
    # Pulses: open at 850, closed at 0, as the vendor's state service reports.
    "vendor_state_open_position": 850.0,
    "vendor_state_closed_position": 0.0,
    "poll_period_s": 0.05,
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
        cls.vendor = FakeGripper(cls.harness, VENDOR_ACTION, state_service=GET_POSITION)
        cls.states: list[JointState] = []
        node.create_subscription(JointState, JOINT_STATES, cls.states.append, STATE)
        cls.deadman = FakeDeadman(cls.harness, DEADMAN)
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
        self.deadman.publishing.set()

    def tearDown(self):
        # A held vendor goal occupies a thread of the test's executor; let it go.
        self.vendor.release_held()
        self.harness.wait_for(lambda: self.vendor.running == 0, "every vendor goal over")

    def _deadman(self, proc_output, state: int) -> str:
        """Set the deadman's state and wait until the relay has received it."""
        type(self)._sequence = getattr(type(self), "_sequence", 0) + 1
        detail = f"test state {type(self)._sequence}."
        self.deadman.say(state, detail)
        proc_output.assertWaitFor(expected_output=detail, timeout=SETTLE_S)
        return detail

    def _send_once(self, position: float, behaviour: float):
        goal = GripperCommand.Goal()
        goal.command.position = position
        goal.command.max_effort = behaviour
        self.feedback: list[float] = []
        future = self.client.send_goal_async(
            goal, feedback_callback=lambda m: self.feedback.append(m.feedback.position)
        )
        self.harness.wait_for(future.done, "the relay answered the goal")
        return future.result()

    def _send(self, position: float, behaviour: float):
        """Send a goal the test expects accepted, once the relay is free.

        The previous test's vendor goal ends asynchronously, and until the
        relay has heard its result it refuses new goals (S-05). The refusal
        itself is asserted by its own tests; here it is waited out.
        """
        handles = []

        def accepted():
            handle = self._send_once(position, behaviour)
            handles.append(handle)
            return handle.accepted

        self.harness.wait_for(accepted, "the relay accepted the goal")
        return handles[-1]

    def _result_of(self, handle, timeout_s: float = SETTLE_S):
        future = handle.get_result_async()
        self.harness.wait_for(future.done, "the relay's result", timeout_s)
        return future.result()

    # ------------------------------------------------------------------ #

    def test_a_goal_reaches_the_vendor_mapped_and_comes_back_mapped(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.vendor.goals)
        handle = self._send(0.85, SUCCEED)
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_SUCCEEDED)
        # Half the drive joint's travel is half the vendor's: 0.425, which the
        # vendor turns into a target of 425 pulses.
        self.assertAlmostEqual(self.vendor.goals[before], 0.425)
        self.assertAlmostEqual(self.vendor.pulses, 425.0)
        self.assertAlmostEqual(outcome.result.position, 0.85)
        # The vendor reports neither flag, and neither is invented.
        self.assertFalse(outcome.result.stalled)
        self.assertFalse(outcome.result.reached_goal)

    def test_the_drive_joint_is_published_in_its_own_units(self):
        """Pulses from the state service, mapped onto the drive joint's travel.

        Not gated by the deadman: reporting where the jaws are moves nothing.
        """
        for pulses, expected in ((850.0, 0.0), (425.0, CLOSED / 2), (0.0, CLOSED)):
            self.vendor.pulses = pulses
            self.harness.wait_for(
                lambda expected=expected: any(
                    s.name == [DRIVE_JOINT] and abs(s.position[0] - expected) < 1e-6
                    for s in self.states[-5:]
                ),
                f"{DRIVE_JOINT} at {expected} on {JOINT_STATES}",
            )

    def test_feedback_is_mapped_back_too(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self.vendor.pulses = 850.0  # fully open
        # Fully closed: vendor 0.85, a target of 0 pulses. The fake reports
        # halfway, 425 pulses, which the vendor reports as 0.425.
        handle = self._send(CLOSED, SUCCEED)
        self._result_of(handle)
        self.harness.wait_for(lambda: self.feedback, "feedback reached the client")
        self.assertAlmostEqual(self.feedback[0], CLOSED / 2)

    def test_a_vendor_stall_is_forwarded_as_reported(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        outcome = self._result_of(self._send(0.6, STALL))
        self.assertTrue(outcome.result.stalled)
        self.assertFalse(outcome.result.reached_goal)

    def test_a_command_beyond_the_travel_is_clamped(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.vendor.goals)
        self._result_of(self._send(CLOSED + 0.5, SUCCEED))
        self.assertAlmostEqual(self.vendor.goals[before], 0.85)

    def test_a_cancel_is_forwarded_to_the_vendor(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        cancels = self.vendor.cancels
        before = len(self.vendor.goals)
        handle = self._send(0.5, HOLD)
        self.harness.wait_for(lambda: len(self.vendor.goals) > before, "the vendor goal")
        cancelled = handle.cancel_goal_async()
        self.harness.wait_for(cancelled.done, "the cancel was answered")
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_CANCELED)
        self.assertGreater(self.vendor.cancels, cancels)

    def test_a_new_goal_is_refused_while_the_vendor_goal_runs(self, proc_output):
        """S-05: no preemption — the vendor would run two threads on one gripper.

        Refused while ours runs, and still refused after ours was cancelled,
        because the vendor ignores the cancel and its goal runs on; accepted
        once the vendor reports its result.
        """
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.vendor.goals)
        first = self._send(0.5, HOLD)
        self.harness.wait_for(lambda: len(self.vendor.goals) > before, "the first vendor goal")
        self.assertFalse(self._send_once(0.2, SUCCEED).accepted, "accepted beside a running one")
        cancelled = first.cancel_goal_async()
        self.harness.wait_for(cancelled.done, "the cancel was answered")
        self.assertEqual(self._result_of(first).status, GoalStatus.STATUS_CANCELED)
        self.assertEqual(self.vendor.running, 1, "the vendor ignored the cancel")
        self.assertFalse(
            self._send_once(0.2, SUCCEED).accepted,
            "accepted while the cancelled goal's vendor goal still runs",
        )
        self.assertEqual(len(self.vendor.goals), before + 1)
        self.vendor.release_held()
        self.assertEqual(self._result_of(self._send(0.2, SUCCEED)).status,
                         GoalStatus.STATUS_SUCCEEDED)

    def test_a_tripped_deadman_aborts_the_goal_in_flight(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        cancels = self.vendor.cancels
        handle = self._send(0.5, HOLD)
        self._deadman(proc_output, DeadmanState.STATE_TRIPPED)
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_ABORTED)
        self.harness.wait_for(
            lambda: self.vendor.cancels > cancels, "the vendor goal cancelled on the trip"
        )

    def test_a_silent_deadman_closes_the_gate(self, proc_output):
        """S-06: a deadman alive on the graph but no longer publishing is not HEALTHY."""
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        handle = self._send(0.5, HOLD)
        self.deadman.publishing.clear()
        outcome = self._result_of(handle)
        self.assertEqual(outcome.status, GoalStatus.STATUS_ABORTED)
        proc_output.assertWaitFor(expected_output="above the bound of 0.5 s", timeout=SETTLE_S)

    def test_no_goal_is_accepted_unless_the_deadman_is_healthy(self, proc_output):
        for state, name in (
            (DeadmanState.STATE_AWAITING, "AWAITING"),
            (DeadmanState.STATE_TRIPPED, "TRIPPED"),
            (DeadmanState.STATE_INACTIVE, "INACTIVE"),
        ):
            detail = self._deadman(proc_output, state)
            before = len(self.vendor.goals)
            handle = self._send_once(0.3, SUCCEED)
            self.assertFalse(handle.accepted, f"accepted with the deadman in state {state}")
            self.assertEqual(len(self.vendor.goals), before)
            # Refused for THIS reason, not for a previous test's vendor goal.
            proc_output.assertWaitFor(
                expected_output=f"gripper goal rejected: the deadman reports {name}: {detail}",
                timeout=SETTLE_S,
            )

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
