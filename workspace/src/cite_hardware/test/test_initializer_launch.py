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

"""The initializer against faked vendor services (ADR-0070).

The initializer runs as its own process; the vendor's enable, zero-read, homing
and stop services and the deadman's state are faked in the test's own node.
What is asserted is what crosses to the vendor, in what order, and what the
`InitializeAsset` caller is told: the enables always, a homing only where the
track has not found its zero, a move to the start only where the carriage is
not there, the gate asked immediately before each motion, and every refusal
named. Nothing reaches hardware.

The numbers are test inputs, not the asset's facts.
"""

from __future__ import annotations

import os
import sys
import time
import unittest

from cite_interfaces.msg import DeadmanState
from cite_interfaces.srv import InitializeAsset
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
from lifecycle_msgs.msg import Transition
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import FakeDeadman, FakeTrack, FakeTrackInit, Harness  # noqa: E402

NODE = "initializer"
VENDOR = "/test_vendor/xarm"
DEADMAN = "/test/deadman_state"
SERVICE = "/test/picker/initialize"
#: Short, so the case that never homes ends quickly; a ceiling, not a schedule.
DEADLINE_S = 3.0

PARAMETERS = {
    "service_name": SERVICE,
    "linear_motor_enable_service": f"{VENDOR}/set_linear_motor_enable",
    "gripper_enable_service": f"{VENDOR}/set_gripper_enable",
    "linear_motor_on_zero_service": f"{VENDOR}/get_linear_motor_on_zero",
    "linear_motor_back_origin_service": f"{VENDOR}/set_linear_motor_back_origin",
    "linear_motor_stop_service": f"{VENDOR}/set_linear_motor_stop",
    "linear_motor_speed_service": f"{VENDOR}/set_linear_motor_speed",
    "linear_motor_set_position_service": f"{VENDOR}/set_linear_motor_pos",
    "linear_motor_get_position_service": f"{VENDOR}/get_linear_motor_pos",
    "position_scale": 1000.0,
    "start_position_m": 0.0,
    "start_tolerance_m": 0.001,
    "speed_mps": 0.1,
    "poll_period_s": 0.05,
    "call_deadline_s": 0.25,
    "deadline_s": DEADLINE_S,
    "deadman_state_topic": DEADMAN,
    "deadman_state_max_age_s": 0.5,
}


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    initializer = Node(
        package="cite_hardware",
        executable="initializer.py",
        name=NODE,
        parameters=[PARAMETERS],
        output="screen",
    )
    return (
        launch.LaunchDescription([initializer, launch_testing.actions.ReadyToTest()]),
        {"initializer": initializer},
    )


class TestInitializer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Harness("initializer_test")
        #: While set, every zero read is answered only once this steady time
        #: has passed: the deadman's state has then aged past its bound.
        cls.hold_zero_until = None
        cls.vendor = FakeTrackInit(cls.harness, VENDOR, on_call=cls._on_vendor_call)
        cls.track = FakeTrack(cls.harness, VENDOR)
        cls.deadman = FakeDeadman(cls.harness, DEADMAN)
        cls.client = cls.harness.node.create_client(InitializeAsset, SERVICE)

    @classmethod
    def tearDownClass(cls):
        cls.harness.close()

    @classmethod
    def _on_vendor_call(cls, name, _request):
        until = cls.hold_zero_until
        if name == FakeTrackInit.ON_ZERO and until is not None:
            Harness.wait_for(lambda: time.monotonic() > until, "the deadman state aged")

    def setUp(self):
        type(self).hold_zero_until = None
        self.track.position_mm = 0
        self.track.arrives = True
        self.track.answer_get.set()
        self.track.set_requests.clear()
        self.track.speeds.clear()
        self.deadman.publishing.set()
        self.deadman.say(DeadmanState.STATE_HEALTHY, "healthy")
        self.vendor.calls.clear()
        self.vendor.failures.clear()
        self.vendor.on_zero = 0
        self.vendor.homes = True

    def _initialize(self) -> InitializeAsset.Response:
        return self.harness.call(self.client, InitializeAsset.Request(), "initialize answered")

    def _sent(self) -> list[str]:
        return [name for name, _request in self.vendor.calls]

    # ------------------------------------------------------------------ #

    def test_0_an_inactive_initializer_sends_nothing(self):
        self.assertTrue(self.harness.transition(NODE, Transition.TRANSITION_CONFIGURE))
        response = self._initialize()
        self.assertFalse(response.success)
        self.assertIn("not active", response.detail)
        self.assertEqual(self._sent(), [])
        self.assertTrue(self.harness.transition(NODE, Transition.TRANSITION_ACTIVATE))

    def test_a_track_on_its_zero_is_enabled_and_not_homed(self):
        self.vendor.on_zero = 1
        stops = self.track.stops
        response = self._initialize()
        self.assertTrue(response.success, response.detail)
        self.assertEqual(
            self._sent(), [FakeTrackInit.ENABLE, FakeTrackInit.GRIPPER, FakeTrackInit.ON_ZERO]
        )
        requests = dict(self.vendor.calls)
        self.assertEqual(requests[FakeTrackInit.ENABLE].data, 1)
        self.assertEqual(requests[FakeTrackInit.GRIPPER].data, 1)
        self.assertEqual(self.track.stops, stops)
        self.assertEqual(self.track.set_requests, [], "a carriage at the start is not moved")
        self.assertIn("not moved", response.detail)

    def test_a_carriage_on_its_zero_but_away_is_brought_to_the_start(self):
        """`on_zero == 1` is a zero found, not a carriage standing at it."""
        self.vendor.on_zero = 1
        self.track.position_mm = 500
        response = self._initialize()
        self.assertTrue(response.success, response.detail)
        self.assertEqual(self._sent(), [
            FakeTrackInit.ENABLE, FakeTrackInit.GRIPPER, FakeTrackInit.ON_ZERO
        ])
        (move,) = self.track.set_requests
        self.assertEqual(move.pos, 0)
        self.assertEqual(move.speed, 100, "speed_mps 0.1 at 1000 units per metre")
        self.assertFalse(move.wait)
        self.assertFalse(move.auto_enable)
        self.assertEqual(self.track.speeds, [100], "the speed is written before the move")
        self.assertEqual(self.track.calls[-1], "set")
        self.assertIn("brought to the start", response.detail)
        self.assertEqual(self.track.position_mm, 0)

    def test_a_move_to_the_start_that_never_arrives_stops_the_track(self):
        self.vendor.on_zero = 1
        self.track.position_mm = 500
        self.track.arrives = False
        stops = self.track.stops
        response = self._initialize()
        self.assertFalse(response.success)
        self.assertIn("not done within", response.detail)
        self.assertIn("set_linear_motor_stop sent", response.detail)
        self.harness.wait_for(lambda: self.track.stops == stops + 1, "the track stopped")
        self.assertEqual(len(self.track.set_requests), 1, "a move is never re-sent")

    def _start_a_move_that_never_arrives(self):
        self.vendor.on_zero = 1
        self.track.position_mm = 500
        self.track.arrives = False
        self.harness.wait_for(self.client.service_is_ready, "initialize appeared")
        future = self.client.call_async(InitializeAsset.Request())
        self.harness.wait_for(lambda: self.track.set_requests, "the move sent")
        return future

    def test_the_gate_closing_during_the_move_stops_it(self):
        stops = self.track.stops
        future = self._start_a_move_that_never_arrives()
        self.deadman.say(DeadmanState.STATE_AWAITING, "awaiting")
        self.harness.wait_for(future.done, "initialize answered")
        self.assertFalse(future.result().success)
        self.assertIn("move to the start stopped", future.result().detail)
        self.harness.wait_for(lambda: self.track.stops == stops + 1, "the track stopped")

    def test_a_deactivation_during_the_move_stops_it(self):
        stops = self.track.stops
        future = self._start_a_move_that_never_arrives()
        try:
            self.assertTrue(self.harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
            self.harness.wait_for(future.done, "initialize answered")
            self.assertFalse(future.result().success)
            self.assertIn("deactivated", future.result().detail)
            self.harness.wait_for(lambda: self.track.stops == stops + 1, "the track stopped")
        finally:
            self.assertTrue(self.harness.transition(NODE, Transition.TRANSITION_ACTIVATE))

    def test_the_gate_is_asked_again_immediately_before_the_homing(self):
        """A gate that closed while the zero was read sends no homing (SA Low)."""
        self.deadman.publishing.clear()
        type(self).hold_zero_until = (
            time.monotonic() + PARAMETERS["deadman_state_max_age_s"] + 0.1
        )
        response = self._initialize()
        self.assertFalse(response.success)
        self.assertIn("homing stopped", response.detail)
        self.assertNotIn(FakeTrackInit.HOME, self._sent())

    def test_the_gate_is_asked_again_immediately_before_the_move(self):
        """A gate that closed while the position was read sends no speed and no move."""
        self.vendor.on_zero = 1
        self.track.position_mm = 500
        self.track.answer_get.clear()
        gets = self.track.gets
        self.harness.wait_for(self.client.service_is_ready, "initialize appeared")
        future = self.client.call_async(InitializeAsset.Request())
        self.harness.wait_for(lambda: self.track.gets > gets, "the position read")
        self.deadman.publishing.clear()
        aged = time.monotonic() + PARAMETERS["deadman_state_max_age_s"] + 0.1
        self.harness.wait_for(lambda: time.monotonic() > aged, "the deadman state aged")
        self.track.answer_get.set()
        self.harness.wait_for(future.done, "initialize answered")
        self.assertFalse(future.result().success)
        self.assertIn("move to the start stopped", future.result().detail)
        self.assertEqual(self.track.speeds, [])
        self.assertEqual(self.track.set_requests, [])

    def test_a_track_off_its_zero_is_homed_once_until_it_says_so(self):
        response = self._initialize()
        self.assertTrue(response.success, response.detail)
        sent = self._sent()
        self.assertEqual(
            sent[:4],
            [FakeTrackInit.ENABLE, FakeTrackInit.GRIPPER, FakeTrackInit.ON_ZERO,
             FakeTrackInit.HOME],
        )
        self.assertEqual(sent.count(FakeTrackInit.HOME), 1, "a homing is never re-sent")
        self.assertEqual(set(sent[4:]), {FakeTrackInit.ON_ZERO})
        home = dict(self.vendor.calls)[FakeTrackInit.HOME]
        self.assertFalse(home.wait)
        self.assertFalse(home.auto_enable)
        self.assertIn("homed", response.detail)

    def test_a_homing_that_never_finishes_stops_the_track(self):
        self.vendor.homes = False
        stops = self.track.stops
        response = self._initialize()
        self.assertFalse(response.success)
        self.assertIn("not done within", response.detail)
        self.assertIn("set_linear_motor_stop sent", response.detail)
        self.harness.wait_for(lambda: self.track.stops == stops + 1, "the track stopped")
        self.assertEqual(self._sent().count(FakeTrackInit.HOME), 1)

    def test_each_refused_step_ends_the_initialization_there(self):
        for service in (
            FakeTrackInit.ENABLE, FakeTrackInit.GRIPPER, FakeTrackInit.ON_ZERO,
            FakeTrackInit.HOME,
        ):
            with self.subTest(service=service):
                self.vendor.calls.clear()
                self.vendor.on_zero = 0
                self.vendor.failures[service] = 9
                stops = self.track.stops
                response = self._initialize()
                self.assertFalse(response.success)
                self.assertIn(f"refused {service}", response.detail)
                self.assertIn("(code 9", response.detail)
                self.assertEqual(self._sent()[-1], service, "nothing is sent after it")
                # Only a refused homing is followed by a stop.
                expected = stops + (1 if service == FakeTrackInit.HOME else 0)
                self.harness.wait_for(lambda: self.track.stops == expected, "the stops")

    def test_no_initialization_unless_the_deadman_is_healthy(self):
        self.deadman.say(DeadmanState.STATE_AWAITING, "awaiting")
        self.harness.wait_for(
            lambda: not self._initialize().success, "a refusal while the deadman awaits"
        )
        self.vendor.calls.clear()
        response = self._initialize()
        self.assertFalse(response.success)
        self.assertIn("deadman", response.detail)
        self.assertEqual(self._sent(), [])


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_initializer_exits_cleanly(self, proc_info, initializer):
        self.assertIn(proc_info[initializer].returncode, (0, -2, -15))
