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

"""The deadman against a fake boundary and fake vendor stops (ADR-0070 item 5).

The test process is the boundary: it publishes `TwinHeartbeat` on the
contract's own topic, and stops. It also holds the vendor's `set_state` and
`set_linear_motor_stop`, a GripperCommand server whose goals the trip must
cancel, and a subscriber on the trajectory topic the trip must publish an empty
trajectory to. Nothing here reaches hardware.

The cases are one sequence, in one method, because the property under test is a
sequence — awaiting, healthy, tripped, latched, reset — and splitting it would
make each part's precondition another part's side effect.
"""

from __future__ import annotations

import os
import sys
import threading
import unittest

from action_msgs.msg import GoalStatus
from cite_interfaces.msg import DeadmanState, TwinHeartbeat
from cite_interfaces.qos import COMMAND, LATCHED, STATE
from control_msgs.action import GripperCommand
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
from lifecycle_msgs.msg import Transition
import pytest
from rclpy.action import ActionClient
from trajectory_msgs.msg import JointTrajectory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import (  # noqa: E402
    FakeArmState,
    FakeGripper,
    FakeTrack,
    Harness,
    HOLD,
)

NODE = "deadman"
ZONE = "test_zone"
VENDOR = "/test_vendor/xarm"
STATE_TOPIC = "/test/deadman_state"
GRIPPER_ACTION = "/test/gripper_controller/gripper_cmd"
ARM_TRAJECTORY = "/test/arm_controller/joint_trajectory"
TIMEOUT_S = 0.5
#: Ten heartbeats per timeout: the margin the deadman is meant to run with.
HEARTBEAT_PERIOD_S = 0.05

PARAMETERS = {
    "zone": ZONE,
    "asset_id": "test_arm",
    "timeout_s": TIMEOUT_S,
    "state_topic": STATE_TOPIC,
    "set_state_service": f"{VENDOR}/set_state",
    "linear_motor_stop_service": f"{VENDOR}/set_linear_motor_stop",
    "cancel_actions": [GRIPPER_ACTION],
    "stop_trajectory_topics": [ARM_TRAJECTORY],
}


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    deadman = Node(
        package="cite_hardware",
        executable="deadman.py",
        name=NODE,
        parameters=[PARAMETERS],
        output="screen",
    )
    return (
        launch.LaunchDescription([deadman, launch_testing.actions.ReadyToTest()]),
        {"deadman": deadman},
    )


class FakeBoundary:
    """Publish heartbeats from a timer while ``beating`` is set."""

    def __init__(self, harness: Harness, zone: str) -> None:
        self._harness = harness
        self.zone = zone
        self.sequence = 0
        self.beating = threading.Event()
        self._lock = threading.Lock()
        self.publisher = harness.node.create_publisher(TwinHeartbeat, TwinHeartbeat.TOPIC, STATE)
        self._timer = harness.node.create_timer(
            HEARTBEAT_PERIOD_S, self._beat, callback_group=harness.group
        )

    def _beat(self) -> None:
        with self._lock:
            if not self.beating.is_set() or self.publisher is None:
                return
            self.sequence += 1
            self.publisher.publish(TwinHeartbeat(zone=self.zone, sequence=self.sequence))

    def die(self) -> None:
        """Make the boundary process go away: its publisher disappears."""
        with self._lock:
            self._harness.node.destroy_publisher(self.publisher)
            self.publisher = None

    def restart(self) -> None:
        with self._lock:
            self.sequence = 0
            self.publisher = self._harness.node.create_publisher(
                TwinHeartbeat, TwinHeartbeat.TOPIC, STATE
            )


class TestDeadman(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Harness("deadman_test")
        node = cls.harness.node
        cls.arm = FakeArmState(cls.harness, VENDOR)
        cls.track = FakeTrack(cls.harness, VENDOR)
        cls.gripper = FakeGripper(cls.harness, GRIPPER_ACTION)
        cls.states: list[DeadmanState] = []
        node.create_subscription(DeadmanState, STATE_TOPIC, cls.states.append, LATCHED)
        cls.trajectories: list[JointTrajectory] = []
        node.create_subscription(
            JointTrajectory, ARM_TRAJECTORY, cls.trajectories.append, COMMAND
        )
        cls.gripper_client = ActionClient(
            node, GripperCommand, GRIPPER_ACTION, callback_group=cls.harness.group
        )

    @classmethod
    def tearDownClass(cls):
        cls.gripper.release_held()
        cls.gripper_client.destroy()
        cls.harness.close()

    def _state_is(self, state: int, what: str) -> DeadmanState:
        return self.harness.wait_for(
            lambda: self.states and self.states[-1].state == state and self.states[-1],
            what,
        )

    def _hold_a_gripper_goal(self):
        self.gripper.hold_again()
        self.harness.wait_for(self.gripper_client.server_is_ready, "the fake gripper served")
        goal = GripperCommand.Goal()
        goal.command.max_effort = HOLD
        sent = self.gripper_client.send_goal_async(goal)
        self.harness.wait_for(sent.done, "the held goal accepted")
        return sent.result()

    def test_the_deadman_sequence(self):
        harness = self.harness
        wrong_zone = FakeBoundary(harness, "another_zone")
        boundary = FakeBoundary(harness, ZONE)

        # 1. Active, and nothing heard yet: AWAITING, and it never trips.
        harness.bring_up(NODE)
        self._state_is(DeadmanState.STATE_AWAITING, "AWAITING after activation")
        wrong_zone.beating.set()
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_AWAITING
            or self.arm.requests,
            "anything but AWAITING with only another zone's heartbeat",
            4 * TIMEOUT_S,
        )
        wrong_zone.beating.clear()
        # Gone, so that step 6's publisher loss is the loss of the LAST one.
        wrong_zone.die()

        # 2. The first heartbeat of its own zone permits motion.
        boundary.beating.set()
        healthy = self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY on the first heartbeat")
        self.assertEqual(healthy.asset_id, "test_arm")
        self.assertAlmostEqual(healthy.timeout_s, TIMEOUT_S)
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_HEALTHY,
            "a trip while heartbeats arrive",
            4 * TIMEOUT_S,
        )

        # 3. The heartbeats stop with motion in flight: the trip stops everything.
        held = self._hold_a_gripper_goal()
        cancels = self.gripper.cancels
        boundary.beating.clear()
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED after the timeout")
        self.assertIn("no heartbeat within", tripped.detail)
        harness.wait_for(lambda: 4 in self.arm.requests, "set_state(4), the vendor's stop")
        harness.wait_for(lambda: self.track.stops > 0, "set_linear_motor_stop")
        harness.wait_for(
            lambda: self.gripper.cancels > cancels, "every gripper goal cancelled"
        )
        harness.wait_for(
            lambda: any(not t.points for t in self.trajectories),
            "an empty trajectory on the arm controller's topic",
        )
        self.gripper.release_held()
        result = held.get_result_async()
        harness.wait_for(result.done, "the held goal ended")
        self.assertIn(
            result.result().status,
            (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED),
        )
        harness.wait_for(
            lambda: "every stop call acknowledged" in self.states[-1].detail,
            "the trip recorded every stop as acknowledged",
        )

        # 4. Latched: heartbeats resuming do not clear it.
        boundary.beating.set()
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_TRIPPED,
            "the trip clearing on resumed heartbeats",
            4 * TIMEOUT_S,
        )

        # 5. Only a deliberate deactivate and activate clears it.
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self._state_is(DeadmanState.STATE_INACTIVE, "INACTIVE on deactivate")
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_ACTIVATE))
        self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY again after a reset")

        # 6. The boundary dies outright: its publisher disappearing trips it,
        #    and a vendor stop that fails is re-issued until it lands.
        arm_requests = len(self.arm.requests)
        self.arm.failures = 2
        # Still beating when it dies, so the timeout cannot be what trips it.
        boundary.die()
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED on publisher loss")
        self.assertIn("disappeared", tripped.detail)
        boundary.beating.clear()
        harness.wait_for(
            lambda: len(self.arm.requests) >= arm_requests + 3,
            "set_state re-issued until the vendor acknowledged it",
        )
        self.assertEqual(self.arm.failures, 0)
        harness.wait_for(
            lambda: "every stop call acknowledged" in self.states[-1].detail,
            "the re-issued stop acknowledged",
        )

        # 7. A restarted boundary counting from 1 is accepted only after a reset.
        boundary.restart()
        boundary.beating.set()
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_TRIPPED,
            "a restarted boundary clearing the trip",
            4 * TIMEOUT_S,
        )
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_ACTIVATE))
        self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY with the restarted boundary")
        boundary.beating.clear()


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_deadman_exits_cleanly(self, proc_info, deadman):
        self.assertIn(proc_info[deadman].returncode, (0, -2, -15))
