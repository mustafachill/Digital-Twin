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

"""The deadman trips when the vendor driver goes away or restarts (N-03, ADR-0070).

The vendor's `ros2_control_node` restarting is a fault: its plugin's
`on_activate` cleans the error, enables motion and STARTS the arm by itself
(`uf_robot_system_hardware.cpp:248-254`). So while HEALTHY, the vendor's
`set_state` must be served by exactly one server. The vendor here is a process
of its own (`fake_vendor_process.py`), ended with SIGINT and started again,
because a driver going away is a process going away. Nothing reaches hardware.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import unittest

from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
from lifecycle_msgs.msg import Transition
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vendor_fakes import FakeBoundary, Harness, SETTLE_S  # noqa: E402

NODE = "deadman_vendor"
ZONE = "test_vendor_zone"
VENDOR = "/test_restarting_vendor/xarm"
STATE_TOPIC = "/test/deadman_vendor_state"
TIMEOUT_S = 0.5
STOP, START = 4, 0

PARAMETERS = {
    "zone": ZONE,
    "asset_id": "test_arm",
    "timeout_s": TIMEOUT_S,
    "tick_period_s": 0.05,
    "call_deadline_s": 0.3,
    "state_topic": STATE_TOPIC,
    "set_state_service": f"{VENDOR}/set_state",
    "set_mode_service": f"{VENDOR}/set_mode",
    "enable_mode": 1,
    "linear_motor_stop_service": f"{VENDOR}/set_linear_motor_stop",
    "cancel_actions": ["/test/deadman_vendor/gripper_cmd"],
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


class VendorProcess:
    """One fake vendor driver process, and the calls it printed."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.serving = threading.Event()
        self._process = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "fake_vendor_process.py"), VENDOR],
            stdout=subprocess.PIPE,
            text=True,
        )
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        for line in self._process.stdout:
            words = line.split()
            if words == ["serving"]:
                self.serving.set()
            elif len(words) == 3 and words[0] == "call":
                self.calls.append((words[1], int(words[2])))

    def end(self) -> None:
        """End the driver with SIGINT, and wait for the process to be gone."""
        if self._process.poll() is None:
            self._process.send_signal(signal.SIGINT)
            self._process.wait(timeout=SETTLE_S)


class TestDeadmanVendor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Harness("deadman_vendor_test")
        cls.states: list[DeadmanState] = []
        cls.harness.node.create_subscription(
            DeadmanState, STATE_TOPIC, cls.states.append, LATCHED
        )
        cls.boundary = FakeBoundary(cls.harness, ZONE)
        cls.vendors: list[VendorProcess] = []

    @classmethod
    def tearDownClass(cls):
        for vendor in cls.vendors:
            vendor.end()
        cls.harness.close()

    def _vendor(self) -> VendorProcess:
        vendor = VendorProcess()
        self.vendors.append(vendor)
        self.harness.wait_for(vendor.serving.is_set, "the fake vendor serving")
        return vendor

    def _servers(self, count: int, what: str) -> None:
        self.harness.wait_for(
            lambda: self.harness.node.count_services(f"{VENDOR}/set_state") == count, what
        )

    def _state_is(self, state: int, what: str) -> DeadmanState:
        return self.harness.wait_for(
            lambda: self.states and self.states[-1].state == state and self.states[-1], what
        )

    def _healthy_and_enabled(self, vendor: VendorProcess, what: str) -> None:
        self.boundary.beating.set()
        self._state_is(DeadmanState.STATE_HEALTHY, f"HEALTHY {what}")
        self.harness.wait_for(
            lambda: ("set_state", START) in vendor.calls and self.states[-1].arm_enabled,
            f"the arm enabled {what}",
        )

    def test_the_vendor_going_away_or_restarting_trips(self):
        harness = self.harness
        first = self._vendor()
        self._servers(1, "one vendor server seen")
        harness.bring_up(NODE)
        self._healthy_and_enabled(first, "with one vendor")

        # The driver goes away while HEALTHY: tripped, and latched.
        first.end()
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED on the vendor going away")
        self.assertIn("served by 0 server(s)", tripped.detail)
        self.assertFalse(tripped.arm_enabled)

        # It comes back — and its own activation would have STARTED the arm.
        # The trip holds, and the returned driver is told to STOP on a tick.
        second = self._vendor()
        harness.wait_for(
            lambda: ("set_state", STOP) in second.calls,
            "set_state(4) at the returned vendor",
        )
        harness.hold_for(
            lambda: self.states[-1].state != DeadmanState.STATE_TRIPPED
            or ("set_state", START) in second.calls
            or ("set_mode", 1) in second.calls,
            "the trip clearing, or the arm enabled, on the vendor's return",
            4 * TIMEOUT_S,
        )

        # A reset with the driver back enables again; a second server — a
        # restart whose predecessor's discovery has not yet expired — trips.
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_DEACTIVATE))
        self.assertTrue(harness.transition(NODE, Transition.TRANSITION_ACTIVATE))
        self._servers(1, "one vendor server again")
        self._healthy_and_enabled(second, "after the reset")
        stops = second.calls.count(("set_state", STOP))
        self._vendor()
        tripped = self._state_is(DeadmanState.STATE_TRIPPED, "TRIPPED on a second vendor server")
        self.assertIn("served by 2 server(s)", tripped.detail)
        harness.wait_for(
            lambda: second.calls.count(("set_state", STOP)) > stops,
            "set_state(4) after the second server appeared",
        )
        self.boundary.beating.clear()


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_deadman_exits_cleanly(self, proc_info, deadman):
        self.assertIn(proc_info[deadman].returncode, (0, -2, -15))
