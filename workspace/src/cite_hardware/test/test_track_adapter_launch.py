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

"""The track adapter against a faked vendor track (ADR-0070 item 3).

The adapter runs as its own process, started by this launch description; the
vendor's three track services and the deadman's state are faked in the test's
own node. What is asserted is what crosses: the command topic in, the vendor
call out with the position in the vendor's unit, the position back on the
joint-state topic in metres — and every refusal, by its absence at the fake.

The numbers are test inputs, not the asset's facts.
"""

from __future__ import annotations

import os
import sys
import unittest

from builtin_interfaces.msg import Duration
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import COMMAND, LATCHED, STATE
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
from lifecycle_msgs.msg import Transition
import pytest
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import FakeDeadman, FakeTrack, Harness, SETTLE_S  # noqa: E402

NODE = "track_adapter"
VENDOR = "/test_vendor/xarm"
JOINT = "test_track_joint"
COMMAND_TOPIC = "/test/track_controller/joint_trajectory"
JOINT_STATES = "/test/joint_states"
DEADMAN = "/test/deadman_state"

PARAMETERS = {
    "command_topic": COMMAND_TOPIC,
    "joint": JOINT,
    "joint_state_topic": JOINT_STATES,
    "position_scale": 1000.0,
    "position_min_m": 0.0,
    "position_max_m": 0.7,
    "max_speed_mps": 0.5,
    "poll_period_s": 0.05,
    "position_max_age_s": 0.5,
    "auto_enable": False,
    "set_position_service": f"{VENDOR}/set_linear_motor_pos",
    "get_position_service": f"{VENDOR}/get_linear_motor_pos",
    "stop_service": f"{VENDOR}/set_linear_motor_stop",
    "deadman_state_topic": DEADMAN,
    "deadman_state_max_age_s": 0.5,
}


#: A second adapter, identical but for a set service nothing serves at first
#: and topics of its own: "the vendor service is unavailable" is tested as a
#: service that is not there and appears later (see `vendor_fakes.FakeTrack`).
UNSERVED = "track_adapter_unserved"
UNSERVED_VENDOR = "/test_vendor/unserved"
UNSERVED_SET = f"{UNSERVED_VENDOR}/set_linear_motor_pos"
UNSERVED_PARAMETERS = dict(
    PARAMETERS,
    command_topic="/test/unserved/joint_trajectory",
    joint_state_topic="/test/unserved/joint_states",
    set_position_service=UNSERVED_SET,
)


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    adapter = Node(
        package="cite_hardware",
        executable="track_adapter.py",
        name=NODE,
        parameters=[PARAMETERS],
        output="screen",
    )
    unserved = Node(
        package="cite_hardware",
        executable="track_adapter.py",
        name=UNSERVED,
        parameters=[UNSERVED_PARAMETERS],
        output="screen",
    )
    return (
        launch.LaunchDescription([adapter, unserved, launch_testing.actions.ReadyToTest()]),
        {"adapter": adapter, "unserved": unserved},
    )


def _command(positions, seconds: float, joints=(JOINT,)) -> JointTrajectory:
    message = JointTrajectory(joint_names=list(joints))
    if positions is not None:
        whole = int(seconds)
        message.points.append(
            JointTrajectoryPoint(
                positions=list(positions),
                time_from_start=Duration(sec=whole, nanosec=int((seconds - whole) * 1e9)),
            )
        )
    return message


class TestTrackAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Harness("track_adapter_test")
        node = cls.harness.node
        cls.track = FakeTrack(cls.harness, VENDOR)
        cls.states: list[JointState] = []
        node.create_subscription(JointState, JOINT_STATES, cls.states.append, STATE)
        cls.commands = node.create_publisher(JointTrajectory, COMMAND_TOPIC, COMMAND)
        cls.deadman = FakeDeadman(cls.harness, DEADMAN)
        cls.unserved_states: list[JointState] = []
        node.create_subscription(
            JointState,
            UNSERVED_PARAMETERS["joint_state_topic"],
            cls.unserved_states.append,
            STATE,
        )
        cls.unserved_commands = node.create_publisher(
            JointTrajectory, UNSERVED_PARAMETERS["command_topic"], COMMAND
        )
        cls.harness.bring_up(NODE)
        cls.harness.bring_up(UNSERVED)
        cls.harness.wait_for(
            lambda: cls.commands.get_subscription_count() > 0, "the adapter subscribed"
        )

    @classmethod
    def tearDownClass(cls):
        cls.harness.close()

    def setUp(self):
        self.deadman.publishing.set()
        self.track.answer_get.set()
        self.track.answer_set.set()
        self.track.set_ret = 0
        self.track.position_mm = 100

    def _deadman(self, proc_output, state: int) -> None:
        """Publish a deadman state and wait until the adapter has received it.

        Waited on, because the state and the command that follows travel on
        two topics and nothing orders them at the adapter: a refusal asserted
        without this could pass on a command that simply arrived first. The
        detail is unique, so an earlier identical state cannot satisfy the wait.
        """
        type(self)._sequence = getattr(type(self), "_sequence", 0) + 1
        detail = f"test state {type(self)._sequence}."
        self.deadman.say(state, detail)
        proc_output.assertWaitFor(expected_output=detail, timeout=SETTLE_S)

    def _send_until_count(self, message, count: int, what: str) -> None:
        """Publish once and wait for the fake to have seen ``count`` set calls."""
        self.commands.publish(message)
        self.harness.wait_for(lambda: len(self.track.set_requests) >= count, what)

    def _wait_for_position(self, metres: float) -> None:
        """Wait for a position published from NOW on: an older one may be stale."""
        seen = len(self.states)
        self.harness.wait_for(
            lambda: any(
                s.name == [JOINT] and abs(s.position[0] - metres) < 1e-9
                for s in self.states[seen:]
            ),
            f"{JOINT} at {metres} m on {JOINT_STATES}",
        )

    # ------------------------------------------------------------------ #

    def test_the_vendor_position_is_published_in_metres(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self.track.position_mm = 250
        self._wait_for_position(0.25)
        latest = self.states[-1]
        self.assertEqual(latest.name, [JOINT])
        self.assertEqual(len(latest.position), 1)

    def test_a_command_reaches_the_vendor_in_millimetres(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self._wait_for_position(0.1)
        before = len(self.track.set_requests)
        # 0.25 m from 0.1 m in 2.5 s: 100 mm/s.
        self._send_until_count(_command([0.35], 2.5), before + 1, "set_linear_motor_pos")
        request = self.track.set_requests[-1]
        self.assertEqual(request.pos, 350)
        self.assertEqual(request.speed, 100)
        self.assertFalse(request.wait, "a waiting call would hold the vendor's executor")
        self.assertFalse(request.auto_enable)

    def test_the_speed_is_clamped_to_the_declared_maximum(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self._wait_for_position(0.1)
        before = len(self.track.set_requests)
        self._send_until_count(_command([0.6], 0.5), before + 1, "set_linear_motor_pos")
        self.assertEqual(self.track.set_requests[-1].speed, 500)

    def test_an_empty_trajectory_is_refused_not_a_stop(self, proc_output):
        """R-02: refused, as `joint_trajectory_controller` refuses one (P2)."""
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        sets, stops = len(self.track.set_requests), self.track.stops
        self.commands.publish(_command(None, 0.0))
        proc_output.assertWaitFor(
            expected_output="track command refused: the trajectory has no points",
            timeout=SETTLE_S,
        )
        self.assertEqual(len(self.track.set_requests), sets)
        self.assertEqual(self.track.stops, stops)

    def _moving(self, proc_output) -> int:
        """Send a move while HEALTHY, and return the stop count before any stop."""
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self._wait_for_position(0.1)
        stops = self.track.stops
        before = len(self.track.set_requests)
        self._send_until_count(_command([0.3], 2.0), before + 1, "set_linear_motor_pos")
        return stops

    def test_a_trip_stops_a_moving_carriage(self, proc_output):
        """S-02: the adapter's own stop when its gate closes, beside the deadman's."""
        stops = self._moving(proc_output)
        self._deadman(proc_output, DeadmanState.STATE_TRIPPED)
        self.harness.wait_for(lambda: self.track.stops > stops, "set_linear_motor_stop")

    def test_a_silent_deadman_stops_a_moving_carriage(self, proc_output):
        """S-06: a closure the deadman did not cause — its state went stale."""
        stops = self._moving(proc_output)
        self.deadman.publishing.clear()
        self.harness.wait_for(
            lambda: self.track.stops > stops, "set_linear_motor_stop on a stale deadman"
        )
        proc_output.assertWaitFor(expected_output="above the bound of 0.5 s", timeout=SETTLE_S)

    def test_a_second_deadman_stops_a_moving_carriage(self, proc_output):
        """S-07: two deadmen are two answers to one question, and neither is taken."""
        stops = self._moving(proc_output)
        rival = self.harness.node.create_publisher(DeadmanState, DEADMAN, LATCHED)
        try:
            self.harness.wait_for(
                lambda: self.track.stops > stops, "set_linear_motor_stop on a second deadman"
            )
            before = len(self.track.set_requests)
            self.commands.publish(_command([0.2], 1.0))
            self.harness.hold_for(
                lambda: len(self.track.set_requests) > before, "a move beside two deadmen", 0.75
            )
        finally:
            self.harness.node.destroy_publisher(rival)

    def test_a_hung_position_read_refuses_motion(self, proc_output):
        """S-11: a read never answered is abandoned, and no speed is derived without one."""
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self._wait_for_position(0.1)
        self.track.answer_get.clear()
        proc_output.assertWaitFor(
            expected_output="get_linear_motor_pos unanswered within position_max_age_s",
            timeout=SETTLE_S,
        )
        before = len(self.track.set_requests)
        self.commands.publish(_command([0.3], 1.0))
        self.harness.hold_for(
            lambda: len(self.track.set_requests) > before, "a move on a stale position", 0.75
        )
        self.track.answer_get.set()

    def test_a_command_for_another_joint_is_refused(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.track.set_requests)
        self.commands.publish(_command([0.3], 1.0, joints=("some_other_joint",)))
        self.harness.hold_for(
            lambda: len(self.track.set_requests) > before, "a call for another joint", 1.0
        )

    def test_a_command_outside_the_travel_is_refused(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        before = len(self.track.set_requests)
        self.commands.publish(_command([0.71], 1.0))
        self.harness.hold_for(
            lambda: len(self.track.set_requests) > before, "a call beyond the travel", 1.0
        )

    def test_no_motion_unless_the_deadman_is_healthy(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        for state in (
            DeadmanState.STATE_AWAITING,
            DeadmanState.STATE_TRIPPED,
            DeadmanState.STATE_INACTIVE,
        ):
            self._deadman(proc_output, state)
            before = len(self.track.set_requests)
            self.commands.publish(_command([0.3], 1.0))
            self.harness.hold_for(
                lambda before=before: len(self.track.set_requests) > before,
                f"a call with the deadman in state {state}",
                0.75,
            )

    def test_a_newer_command_replaces_one_held_behind_a_slow_vendor(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        """Preemption: the vendor receives the latest target, never a backlog."""
        self._wait_for_position(0.1)
        self.track.answer_set.clear()
        before = len(self.track.set_requests)
        self._send_until_count(_command([0.2], 1.0), before + 1, "the first call")
        # The first is in flight and unanswered; these two are held, and the
        # second replaces the first of them.
        self.commands.publish(_command([0.3], 1.0))
        self.commands.publish(_command([0.4], 1.0))
        self.harness.hold_for(
            lambda: len(self.track.set_requests) > before + 1,
            "a second call while the first is unanswered",
            0.75,
        )
        self.track.answer_set.set()
        self.harness.wait_for(
            lambda: len(self.track.set_requests) >= before + 2, "the held target sent"
        )
        self.harness.hold_for(
            lambda: len(self.track.set_requests) > before + 2, "a superseded target sent", 0.75
        )
        self.assertEqual([r.pos for r in self.track.set_requests[before:]], [200, 400])

    def test_a_vendor_error_does_not_wedge_the_adapter(self, proc_output):
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self._wait_for_position(0.1)
        self.track.set_ret = -1
        before = len(self.track.set_requests)
        self._send_until_count(_command([0.2], 1.0), before + 1, "the failing call")
        self.track.set_ret = 0
        self._send_until_count(_command([0.3], 1.0), before + 2, "the next call")
        self.assertEqual(self.track.set_requests[-1].pos, 300)

    def test_an_unavailable_vendor_service_refuses_and_recovers(self, proc_output):
        """Run against the second adapter, whose set service nothing serves yet."""
        self._deadman(proc_output, DeadmanState.STATE_HEALTHY)
        self.harness.wait_for(
            lambda: self.unserved_commands.get_subscription_count() > 0,
            "the second adapter subscribed",
        )
        self.harness.wait_for(
            lambda: any(s.name == [JOINT] for s in self.unserved_states),
            "the second adapter read a position",
        )
        # Re-sent until refused for the reason under test: the deadman state
        # `_deadman` waited for may have reached the first adapter first.
        for _attempt in range(int(SETTLE_S / 0.5)):
            self.unserved_commands.publish(_command([0.2], 1.0))
            try:
                proc_output.assertWaitFor(
                    expected_output=f"{UNSERVED_SET} is not available", timeout=0.5
                )
                break
            except AssertionError:
                continue
        else:
            self.fail(f"no refusal naming {UNSERVED_SET} as unavailable")

        late = FakeTrack(self.harness, UNSERVED_VENDOR, serve=(FakeTrack.SET,))
        # Re-sent until it lands: the adapter learns the service exists by
        # discovery, which this process cannot observe from the adapter's side.
        self.harness.wait_for(
            lambda: late.set_requests or self.unserved_commands.publish(_command([0.25], 1.0)),
            "a call once the service appeared",
        )
        self.assertEqual(late.set_requests[-1].pos, 250)

    def test_z_an_inactive_adapter_commands_nothing(self, proc_output):
        """Last by name, because it deactivates the node the others drive.

        R-04: deactivating with a move sent stops the carriage first.
        """
        stops = self._moving(proc_output)
        self.assertTrue(self.harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self.harness.wait_for(
            lambda: self.track.stops > stops, "set_linear_motor_stop on deactivate"
        )
        try:
            before = len(self.track.set_requests)
            self.commands.publish(_command([0.3], 1.0))
            self.harness.hold_for(
                lambda: len(self.track.set_requests) > before, "a call while inactive", 0.75
            )
        finally:
            self.assertTrue(self.harness.transition(NODE, Transition.TRANSITION_ACTIVATE))


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_adapters_exit_cleanly(self, proc_info, adapter, unserved):
        for process in (adapter, unserved):
            self.assertIn(proc_info[process].returncode, (0, -2, -15))
