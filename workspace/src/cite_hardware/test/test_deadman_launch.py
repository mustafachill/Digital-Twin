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

"""The deadman against a fake boundary and a fake vendor (ADR-0070 item 5).

The test process is the boundary: it publishes `TwinHeartbeat` on the
contract's own topic, and stops. It also holds the vendor's `set_state`,
`set_mode` and `set_linear_motor_stop`, and a GripperCommand server whose goals
a trip must cancel. Nothing here reaches hardware.

The vendor's arm state is one value any client may set, and the fake lets the
test be that other client (UFACTORY Studio, the pendant): the property under
test is that whenever the deadman is not HEALTHY, the arm is put back to STOP
within a tick, whoever moved it.

The cases are one sequence, in one method, because the property under test is a
sequence — awaiting, healthy, tripped, latched, reset — and splitting it would
make each part's precondition another part's side effect.
"""

from __future__ import annotations

import os
import sys
import threading
import unittest
import uuid

from action_msgs.msg import GoalStatus
from cite_interfaces.msg import DeadmanState, TwinHeartbeat
from cite_interfaces.qos import LATCHED, STATE
from control_msgs.action import GripperCommand
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
from lifecycle_msgs.msg import Transition
import pytest
from rclpy.action import ActionClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import (  # noqa: E402
    FakeArmState,
    FakeGripper,
    FakeTrack,
    Harness,
    HOLD,
    SETTLE_S,
)

NODE = "deadman"
ZONE = "test_zone"
VENDOR = "/test_vendor/xarm"
STATE_TOPIC = "/test/deadman_state"
GRIPPER_ACTION = "/test/gripper_controller/gripper_cmd"
TIMEOUT_S = 0.5
TICK_S = 0.05
CALL_DEADLINE_S = 0.3
#: Ten heartbeats per timeout: the margin the deadman is meant to run with.
HEARTBEAT_PERIOD_S = 0.05
STOP, START, SERVO = 4, 0, 1

PARAMETERS = {
    "zone": ZONE,
    "asset_id": "test_arm",
    "timeout_s": TIMEOUT_S,
    "tick_period_s": TICK_S,
    "call_deadline_s": CALL_DEADLINE_S,
    "state_topic": STATE_TOPIC,
    "set_state_service": f"{VENDOR}/set_state",
    "set_mode_service": f"{VENDOR}/set_mode",
    "enable_mode": SERVO,
    "linear_motor_stop_service": f"{VENDOR}/set_linear_motor_stop",
    "cancel_actions": [GRIPPER_ACTION],
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
        self.boundary_id = str(uuid.uuid4())
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
        cls.gripper_client = ActionClient(
            node, GripperCommand, GRIPPER_ACTION, callback_group=cls.harness.group
        )

    @classmethod
    def tearDownClass(cls):
        cls.gripper.release_held()
        cls.arm.release.set()
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

    def _undone_within_a_tick(self, what: str) -> None:
        """Another client starts the arm; the deadman puts it back to STOP."""
        self.arm.flip(START)
        self.harness.wait_for(lambda: self.arm.state == STOP, what)

    def _enabled(self, modes_before: int, what: str) -> None:
        """`set_mode(servo)` and then `set_state(0)`, in that order, once."""
        self.harness.wait_for(
            lambda: len(self.arm.modes) > modes_before and self.arm.state == START, what
        )
        calls = self.arm.calls
        last_mode = max(i for i, call in enumerate(calls) if call == ("set_mode", SERVO))
        self.assertIn(("set_state", START), calls[last_mode:], "set_state(0) after set_mode")

    def test_the_deadman_sequence(self, proc_output):
        harness = self.harness
        wrong_zone = FakeBoundary(harness, "another_zone")
        boundary = FakeBoundary(harness, ZONE)

        # 1. Active, nothing heard yet: AWAITING, the arm held at STOP however
        #    often another client starts it, and never a trip.
        harness.bring_up(NODE)
        self._state_is(DeadmanState.STATE_AWAITING, "AWAITING after activation")
        harness.wait_for(lambda: self.arm.state == STOP, "set_state(4) on activation")
        self._undone_within_a_tick("a START by another client undone while AWAITING")
        wrong_zone.beating.set()
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_AWAITING or self.arm.modes,
            "anything but AWAITING with only another zone's heartbeat",
            4 * TIMEOUT_S,
        )
        wrong_zone.beating.clear()
        wrong_zone.die()

        # 2. The first heartbeat of its own zone permits motion and enables the
        #    arm — the only place the deadman ever does.
        boundary.beating.set()
        healthy = self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY on the first heartbeat")
        self.assertEqual(healthy.asset_id, "test_arm")
        self.assertAlmostEqual(healthy.timeout_s, TIMEOUT_S)
        self._enabled(0, "the arm enabled on HEALTHY")
        stops = self.arm.requests.count(STOP)
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_HEALTHY
            or self.arm.requests.count(STOP) > stops,
            "a trip, or a STOP, while heartbeats arrive",
            4 * TIMEOUT_S,
        )

        # 3. The heartbeats stop with motion in flight: the trip stops
        #    everything, and keeps stopping it on every tick.
        held = self._hold_a_gripper_goal()
        cancels, track_stops = self.gripper.cancels, self.track.stops
        boundary.beating.clear()
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED after the timeout")
        self.assertIn("no heartbeat within", tripped.detail)
        harness.wait_for(lambda: self.arm.state == STOP, "set_state(4), the vendor's stop")
        harness.wait_for(
            lambda: self.track.stops >= track_stops + 3,
            "set_linear_motor_stop re-issued on every tick, acknowledged or not",
        )
        harness.wait_for(lambda: self.gripper.cancels > cancels, "every gripper goal cancelled")
        # And on every tick: a goal accepted after the trip is cancelled too.
        # (A goal already CANCELING is not offered to the cancel callback
        # again, so the count rises once per goal, not once per tick.)
        late = self._hold_a_gripper_goal()
        cancels = self.gripper.cancels
        harness.wait_for(
            lambda: self.gripper.cancels > cancels, "a goal sent after the trip cancelled too"
        )
        self._undone_within_a_tick("a START by another client undone while TRIPPED")
        # A vendor that does not answer holds back nothing: the next ticks'
        # calls still arrive, and the unanswered one is abandoned.
        self.arm.release.clear()
        self.arm.hold_next.set()
        harness.wait_for(lambda: not self.arm.hold_next.is_set(), "a set_state held")
        answered = len(self.arm.requests)
        harness.wait_for(
            lambda: len(self.arm.requests) >= answered + 3,
            "set_state re-issued while an earlier one is unanswered",
        )
        proc_output.assertWaitFor(
            expected_output="set_state(4) unanswered within call_deadline_s; abandoned",
            timeout=SETTLE_S,
        )
        self.arm.release.set()
        self.gripper.release_held()
        harness.wait_for(late.get_result_async().done, "the late goal ended")
        result = held.get_result_async()
        harness.wait_for(result.done, "the held goal ended")
        self.assertIn(
            result.result().status,
            (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED),
        )

        # 4. Latched: heartbeats resuming neither clear it nor enable the arm.
        modes = len(self.arm.modes)
        boundary.beating.set()
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_TRIPPED
            or len(self.arm.modes) > modes
            or self.arm.state != STOP,
            "the trip clearing, or the arm enabled, on resumed heartbeats",
            4 * TIMEOUT_S,
        )

        # 5. Deactivate: INACTIVE, and the arm still held stopped.
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self._state_is(DeadmanState.STATE_INACTIVE, "INACTIVE on deactivate")
        self._undone_within_a_tick("a START by another client undone while INACTIVE")
        # Activate: AWAITING first, still stopped; only the fresh heartbeat
        # that follows enables.
        boundary.beating.clear()
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_ACTIVATE))
        self._state_is(DeadmanState.STATE_AWAITING, "AWAITING after a reset")
        self.assertEqual(len(self.arm.modes), modes, "enabled before a heartbeat")
        self._undone_within_a_tick("a START by another client undone after the reset")
        boundary.beating.set()
        self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY again on a fresh heartbeat")
        self._enabled(modes, "the arm enabled again")

        # 6. A second boundary — another id on the same topic — trips it.
        boundary.boundary_id = str(uuid.uuid4())
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED on another boundary id")
        self.assertIn("this deadman follows", tripped.detail)
        harness.wait_for(lambda: self.arm.state == STOP, "the arm stopped on the rival")
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_ACTIVATE))
        self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY after a reset")

        # 7. A second heartbeat PUBLISHER trips it too.
        rival = FakeBoundary(harness, ZONE)
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED on a second publisher")
        self.assertIn("publisher", tripped.detail)
        rival.die()
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_ACTIVATE))
        self._state_is(DeadmanState.STATE_HEALTHY, "HEALTHY with the rival gone")

        # 8. The boundary dies outright: its publisher disappearing trips it.
        boundary.die()
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED on publisher loss")
        self.assertIn("disappeared", tripped.detail)
        boundary.beating.clear()
        harness.wait_for(lambda: self.arm.state == STOP, "the arm stopped on publisher loss")

        # 9. A restarted boundary is followed only after a reset.
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
