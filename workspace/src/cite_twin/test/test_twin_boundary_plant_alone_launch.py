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

"""The boundary of a pair started with the plant alone (ADR-0072, amending ADR-0057).

The shipped plan's counterpart is the physical xArm 5, and without the hardware
opt-in the pair supervisor starts the plant alone and hands the boundary
`--sides plant`. This rig is that deployment with the plant replaced by
`fake_side.py` and NO counterpart behind the boundary: the boundary must come up,
announce, beat on the plant's domain, route a SIM goal and a SIM track command
to the plant, answer `TrackArrived` for the plant without waiting on a physical
carriage nobody runs, and refuse every mode that needs a far side as having none
- PRECONDITION_FAILED naming the missing far side, never SAFETY_BLOCKED, since
there is no physical side here to gate.

A LISTENER sits on the counterpart's domain - a fake side the boundary is never
told about - and must hear nothing from the boundary at all: no heartbeat, no
goal (R-14). A physical side's deadman on that domain would therefore never
enable its arm.

Like the paired rig it brings up no cell and is evidence about the boundary only.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

from cite_bringup.plan import default_plan_path
from cite_bringup.readiness import boundary_announcement
from cite_bringup.track_command import move as track_move
from cite_interfaces.action import MoveTo
from cite_interfaces.msg import ResultCode, TwinMode
from cite_interfaces.qos import COMMAND
from cite_interfaces.srv import SetMode, TrackArrived
import launch
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node as RclpyNode
from trajectory_msgs.msg import JointTrajectory
import yaml

ZONE = "cell_b"
ASSET = "picker"
MOVE_TO = f"/cite/twin/{ZONE}/{ASSET}/move_to"
MOVE_TO_ON_A_SIDE = f"/cite/{ZONE}/{ASSET}/move_to"

#: Odd, inside `DOMAIN_BAND`, and apart from the paired rig's by a different
#: offset of the process id. Nothing runs at BASE + 1, which is the point.
BASE = 1 + 2 * ((os.getpid() + 7) % 50)
PLANT_DOMAIN = BASE
COUNTERPART_DOMAIN = BASE + 1

SETTLE_S = 30.0

FAKE_SIDE = str(Path(__file__).resolve().parent / "fake_side.py")
PLAN_PATH = default_plan_path(ZONE)
_TRACK = yaml.safe_load(PLAN_PATH.read_text())["plan"]["controller_managers"][0]["track"]
TRACK, TRACK_JOINT = _TRACK["command_topic"], _TRACK["joint"]
TWIN_TRACK = TRACK.replace("/cite/", "/cite/twin/", 1)


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    os.environ["CITE_DOMAIN_BASE"] = str(BASE)
    os.environ["ROS_DOMAIN_ID"] = str(PLANT_DOMAIN)
    # Exactly the deployment ADR-0072 starts: no opt-in, so no counterpart.
    os.environ.pop("CITE_ALLOW_HARDWARE", None)
    plant = ExecuteProcess(
        cmd=[
            sys.executable, FAKE_SIDE, "--side", "plant", "--zone", ZONE, "--assets", ASSET,
            "--offset", "0.25", "--track-topic", TRACK, "--track-joint", TRACK_JOINT,
        ],
        additional_env={"ROS_DOMAIN_ID": str(PLANT_DOMAIN)},
        output="screen",
        name="fake_plant",
    )
    # Listens on the counterpart's domain; nothing the boundary does may reach it.
    listener = ExecuteProcess(
        cmd=[
            sys.executable, FAKE_SIDE, "--side", "counterpart", "--zone", ZONE, "--assets",
            ASSET, "--offset", "0.75",
        ],
        additional_env={"ROS_DOMAIN_ID": str(COUNTERPART_DOMAIN)},
        output="screen",
        name="fake_counterpart_listener",
    )
    boundary = Node(
        package="cite_twin",
        executable="twin_boundary.py",
        name="twin_boundary",
        arguments=["--plan", str(PLAN_PATH), "--sides", "plant"],
        output="screen",
    )
    return (
        launch.LaunchDescription(
            [plant, listener, boundary, launch_testing.actions.ReadyToTest()]
        ),
        {"plant": plant, "listener": listener, "boundary": boundary},
    )


class TestThePlantAlone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode("twin_plant_alone_test")
        cls.set_mode = cls.node.create_client(SetMode, SetMode.Request.SERVICE)
        cls.move_to = ActionClient(cls.node, MoveTo, MOVE_TO)
        cls.track = cls.node.create_publisher(JointTrajectory, TWIN_TRACK, COMMAND)
        cls.track_arrived = cls.node.create_client(TrackArrived, TrackArrived.Request.SERVICE)

    @classmethod
    def tearDownClass(cls):
        cls.move_to.destroy()
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, what: str, timeout_s: float = SETTLE_S):
        deadline = self.node.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.05)
            value = predicate()
            if value:
                return value
        self.fail(f"{what} did not happen within {timeout_s:g} s")

    def _request(self, mode: int, force: bool = False):
        self.assertTrue(self.set_mode.wait_for_service(timeout_sec=SETTLE_S))
        future = self.set_mode.call_async(
            SetMode.Request(mode=mode, reason="plant alone", force=force)
        )
        self._spin_until(future.done, f"SetMode({mode}) returned")
        return future.result()

    def test_the_boundary_announces_and_beats_on_the_plant(self, proc_output):
        proc_output.assertWaitFor(
            expected_output=boundary_announcement(ZONE), stream="stdout", timeout=SETTLE_S
        )
        proc_output.assertWaitFor(
            expected_output=f"plant: heartbeat zone={ZONE}", stream="stdout", timeout=SETTLE_S
        )
        proc_output.assertWaitFor(
            expected_output="plant: heartbeat advancing", stream="stdout", timeout=SETTLE_S
        )
        proc_output.assertWaitFor(
            expected_output="counterpart: up with", stream="stdout", timeout=SETTLE_S
        )
        # R-14: the plant has heard several beats; the counterpart's domain none.
        text = "".join(
            entry.text.decode(errors="replace") if isinstance(entry.text, bytes) else entry.text
            for entry in proc_output
        )
        self.assertNotIn("counterpart: heartbeat", text)
        self.assertNotIn("counterpart: accepted", text)

    def test_every_mode_needing_a_far_side_is_refused_as_having_none(self):
        for mode in (TwinMode.MODE_REAL, TwinMode.MODE_VALIDATED, TwinMode.MODE_SHADOW):
            response = self._request(mode)
            self.assertFalse(response.accepted, mode)
            self.assertEqual(response.result.code, ResultCode.PRECONDITION_FAILED, mode)
            self.assertIn("far side", response.result.detail)
            self.assertIn("plant alone", response.result.detail)
            self.assertEqual(response.current_mode, TwinMode.MODE_SIM)

    def test_a_goal_in_sim_reaches_the_plant(self, proc_output):
        self.assertTrue(self._request(TwinMode.MODE_SIM).accepted)
        self._spin_until(self.move_to.server_is_ready, "the twin MoveTo endpoint")
        goal = MoveTo.Goal()
        goal.named_configuration = "alone"
        sent = self.move_to.send_goal_async(goal)
        self._spin_until(sent.done, "the goal was answered")
        future = sent.result().get_result_async()
        self._spin_until(future.done, "the goal produced a result")
        result = future.result().result
        self.assertEqual(result.result.code, ResultCode.SUCCESS, result.result.detail)
        proc_output.assertWaitFor(
            expected_output=f"plant: accepted {MOVE_TO_ON_A_SIDE} as alone",
            stream="stdout",
            timeout=SETTLE_S,
        )

    def test_a_track_command_in_sim_reaches_the_plant_and_arrival_asks_only_it(
        self, proc_output
    ):
        self.assertTrue(self._request(TwinMode.MODE_SIM).accepted)
        self._spin_until(
            lambda: self.track.get_subscription_count() > 0, "the boundary's track endpoint"
        )
        self.track.publish(track_move(TRACK_JOINT, 0.125, 0.375, 2.5))
        proc_output.assertWaitFor(
            expected_output="plant: track [0.125, 0.375]", stream="stdout", timeout=SETTLE_S
        )
        self.assertTrue(self.track_arrived.wait_for_service(timeout_sec=SETTLE_S))

        def arrived():
            future = self.track_arrived.call_async(
                TrackArrived.Request(joint=TRACK_JOINT, position_m=0.25, tolerance_m=0.001)
            )
            self._spin_until(future.done, "TrackArrived returned")
            return future.result()

        answer = self._spin_until(
            lambda: (lambda a: a if a.arrived else None)(arrived()),
            "the plant's carriage was judged at its place, with no physical side waited on",
        )
        self.assertTrue(answer.routed)
        self.assertNotIn("counterpart", answer.detail)


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_boundary_exits_cleanly(self, proc_info, boundary):
        launch_testing.asserts.assertExitCodes(
            proc_info, process=boundary, allowable_exit_codes=[0, -2, -15]
        )
