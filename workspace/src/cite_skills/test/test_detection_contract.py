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

"""The parts of `Detect` that only a running server can show.

There is no simulator here and there is no bridge. A plain ROS publisher stands
in for the bridged break beam, which is exactly the right stand-in: the beam
plugin publishes a boolean level on the Gazebo transport, `cite_bringup` will
carry it into ROS as `std_msgs/Bool`, and from this node's point of view those
two facts are the whole of the sensor. Nothing here branches on which one it is,
because nothing anywhere may (P2).

**What this cannot show.** The bridge does not exist yet. These tests drive the
ROS side of it by hand, so they prove that a level on the topic named by the
plan becomes a typed event and a typed detection — and they prove nothing about
whether Gazebo's boolean reaches that topic. That half is `cite_bringup`'s and is
untested until it lands.

The sensors, their frames and their topics are read from the generated artifacts
rather than restated. A copy of them here would be a second place they live (P1)
and would go stale silently the first time the model changed.
"""

from __future__ import annotations

from pathlib import Path
import threading
import time
import unittest

from ament_index_python.packages import get_package_share_directory
from cite_interfaces import qos
from cite_interfaces.action import Detect
from cite_interfaces.msg import DetectionEvent, ResultCode
from geometry_msgs.msg import Vector3
from launch import LaunchDescription
from launch_ros.actions import Node
import launch_testing
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node as RclpyNode
from std_msgs.msg import Bool
import yaml

ZONE = "cell_a"
NAMESPACE = f"/cite/{ZONE}/detection"

#: How long a `Detect` waits for a beam that has not reported. Short, because two
#: of the tests below deliberately spend it.
DETECT_TIMEOUT_S = 5.0

STARTUP_CEILING_S = 60.0
GOAL_CEILING_S = 60.0

GENERATED = Path(get_package_share_directory("cite_generated"))


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _sensors() -> list:
    """Return the zone's break beams, from the generated bring-up plan."""
    plan = _read(GENERATED / "bringup" / f"{ZONE}_plan.yaml")
    sensors = plan["plan"]["sensors"]
    assert sensors, "the generated plan declares no sensors"
    return sensors


def _frames() -> dict:
    """Return `child -> (parent, xyz, rpy)` for every generated static transform."""
    frames = _read(GENERATED / "frames" / f"{ZONE}_static_tf.yaml")
    return {
        entry["child"]: (entry["parent"], entry["xyz_m"], entry["rpy_rad"])
        for entry in frames["static_transforms"]
    }


def _beam_frame(asset_id: str, frames: dict) -> str:
    """Return the TF frame the generator emitted for one beam.

    Matched by suffix rather than composed. `ids.frame()` builds
    `<zone>__<asset>__<link>` and lives in `tools/`, which a ROS package cannot
    import; spelling the same rule out here would be the second place a name is
    made that the whole convention exists to prevent.
    """
    matches = [child for child in frames if child.startswith(f"{ZONE}__{asset_id}__")]
    assert len(matches) == 1, f"expected one generated frame for {asset_id}, got {matches}"
    return matches[0]


#: Where the raw bridged level lands in ROS.
#:
#: `cite_bringup` owns this name and has not chosen it yet, because the bridge it
#: belongs to does not exist. The test picks one so that it has something to
#: publish on; the node under test composes nothing and takes both names as
#: parameters, so the choice is the test's and not the node's.
#:
#: It is deliberately NOT the plan's `detection_topic`. That name is already
#: spoken for: `cell_a_flow.yaml` gives it to L4 as a station trigger and
#: `StationTopology.msg` documents it as *a DetectionEvent topic*. Bridging a
#: `std_msgs/Bool` onto it would put the raw level on the name the line expects to
#: carry the typed event, and the two would fight over one topic.
def _state_topic(sensor: dict) -> str:
    return f"{sensor['detection_topic']}_level"


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> LaunchDescription:
    sensors = _sensors()
    frames = _frames()

    parameters = {
        "zone": ZONE,
        "sensors": [sensor["asset"] for sensor in sensors],
        "detect_timeout_s": DETECT_TIMEOUT_S,
        "use_sim_time": False,
    }
    for sensor in sensors:
        asset = sensor["asset"]
        parameters[f"sensor.{asset}.state_topic"] = _state_topic(sensor)
        # The typed side keeps the plan's own name, which is the name L4's
        # station triggers already subscribe to.
        parameters[f"sensor.{asset}.event_topic"] = sensor["detection_topic"]
        parameters[f"sensor.{asset}.frame_id"] = _beam_frame(asset, frames)

    # The beams' static transforms, republished here because there is no
    # `cite_bringup` in this rig to do it. Read from the generated frames file, so
    # where a beam stands is still stated once, in L0.
    transforms = []
    for sensor in sensors:
        child = _beam_frame(sensor["asset"], frames)
        parent, xyz, rpy = frames[child]
        transforms.append(
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name=f"tf_{sensor['asset']}",
                arguments=[
                    "--x", str(xyz[0]), "--y", str(xyz[1]), "--z", str(xyz[2]),
                    "--roll", str(rpy[0]), "--pitch", str(rpy[1]), "--yaw", str(rpy[2]),
                    "--frame-id", parent, "--child-frame-id", child,
                ],
                output="log",
            )
        )

    return LaunchDescription(
        transforms
        + [
            Node(
                package="cite_skills",
                executable="detection_server",
                name="detection_server",
                namespace=NAMESPACE,
                parameters=[parameters],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class Harness(RclpyNode):
    """A stand-in for the bridge, and a client for the action."""

    def __init__(self) -> None:
        super().__init__("detection_contract_harness")
        self.sensors = _sensors()
        self.frames = _frames()
        self.callbacks = ReentrantCallbackGroup()

        # Reliable on the way out, against a best-effort reader on the way in.
        #
        # That pairing is compatible and the reverse is not, which is the whole
        # reason the subscription uses the SENSOR profile: a reliable reader would
        # fail to match a best-effort bridge, connect anyway, appear in
        # `ros2 topic info`, and deliver nothing. Publishing reliably here proves
        # the compatible direction actually carries.
        self.levels = {
            sensor["asset"]: self.create_publisher(
                Bool, _state_topic(sensor), qos.command()
            )
            for sensor in self.sensors
        }

        self.events: dict = {sensor["asset"]: [] for sensor in self.sensors}
        self.events_lock = threading.Lock()
        self.event_subscriptions = [
            self.create_subscription(
                DetectionEvent,
                sensor["detection_topic"],
                self._record,
                qos.event(),
                callback_group=self.callbacks,
            )
            for sensor in self.sensors
        ]

        self.detect = ActionClient(
            self, Detect, f"{NAMESPACE}/detect", callback_group=self.callbacks
        )

    def _record(self, event: DetectionEvent) -> None:
        with self.events_lock:
            self.events.setdefault(event.asset_id, []).append(event)

    def recorded(self, asset_id: str) -> list:
        with self.events_lock:
            return list(self.events.get(asset_id, []))

    def await_events(self, asset_id: str, count: int, timeout: float) -> list:
        deadline = time.time() + timeout
        while time.time() < deadline:
            events = self.recorded(asset_id)
            if len(events) >= count:
                return events
            time.sleep(0.05)
        return self.recorded(asset_id)

    def publish_level(self, asset_id: str, blocked: bool, times: int = 6) -> None:
        """Publish a level the way the beam does — repeatedly.

        The plugin republishes its current state every period so that a late
        subscriber learns it. Repeating here reproduces that, and it is also what
        makes the test independent of whether any single best-effort datagram
        arrived.
        """
        message = Bool()
        message.data = blocked
        for _ in range(times):
            self.levels[asset_id].publish(message)
            time.sleep(0.05)

    @staticmethod
    def wait(future, timeout: float):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if future.done():
                return future.result()
            time.sleep(0.05)
        return None

    def send(self, goal, timeout: float = GOAL_CEILING_S):
        handle = self.wait(self.detect.send_goal_async(goal), timeout)
        assert handle is not None, "the detect goal was never answered"
        assert handle.accepted, "the detect goal was rejected"
        return handle


def _region(size: float = 100.0) -> Vector3:
    """Return a region large enough to contain the whole cell."""
    return Vector3(x=size, y=size, z=size)


def _world_frame() -> str:
    """Return the frame the generated static transforms hang off."""
    parents = {parent for parent, _, _ in _frames().values()}
    roots = parents - set(_frames())
    assert len(roots) == 1, f"expected one root frame, got {roots}"
    return next(iter(roots))


class TestDetectionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.harness = Harness()
        cls.executor = MultiThreadedExecutor()
        cls.executor.add_node(cls.harness)
        cls.spinner = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.spinner.start()
        assert cls.harness.detect.wait_for_server(STARTUP_CEILING_S), (
            "the detection server never advertised 'detect'"
        )
        cls.world = _world_frame()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.executor.shutdown()
        cls.harness.destroy_node()
        rclpy.shutdown()

    def test_1_a_detect_waiting_on_a_silent_sensor_can_be_cancelled(self) -> None:
        """Cancellation, tested where the skill actually blocks.

        Nothing has published a level yet, so this goal is inside its bounded
        wait for a first report — the one place a `Detect` spends any time at
        all. No sleep decides when to cancel and none decides when it takes
        effect (P4).
        """
        goal = Detect.Goal()
        goal.region_frame = self.world
        goal.region_size_m = _region()
        handle = self.harness.send(goal)

        self.harness.wait(handle.cancel_goal_async(), GOAL_CEILING_S)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped, "the cancelled detect never reported a result")
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.CANCELLED,
            f"a cancelled detect reported {wrapped.result.result.code}: "
            f"{wrapped.result.result.detail}",
        )

    def test_2_a_silent_sensor_is_a_fault_and_not_an_empty_belt(self) -> None:
        # The failure this exists to prevent: a bridge that is not delivering
        # looks exactly like a clear beam if the answer is an empty list. The line
        # would then run into the work-piece it was told was not there.
        goal = Detect.Goal()
        goal.region_frame = self.world
        goal.region_size_m = _region()
        handle = self.harness.send(goal)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped)
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.TIMEOUT,
            f"a detect over sensors that have never reported returned "
            f"{wrapped.result.result.code}: {wrapped.result.result.detail}",
        )
        self.assertEqual(
            len(wrapped.result.detections), 0,
            "a faulted detect must not also carry detections",
        )

    def test_3_a_first_level_is_reported_as_a_state_and_not_as_an_arrival(self) -> None:
        """A work-piece already in the beam at start-up.

        Nothing saw it arrive, so an event claiming CLEAR -> BLOCKED would be a
        transition invented rather than observed. It is still published, with
        `state == previous_state`, because the alternative is a part nobody knows
        about until it leaves.
        """
        asset = self.harness.sensors[0]["asset"]
        self.harness.publish_level(asset, blocked=True)

        events = self.harness.await_events(asset, 1, GOAL_CEILING_S)
        self.assertGreaterEqual(len(events), 1, "no DetectionEvent was published")
        first = events[0]
        self.assertEqual(first.asset_id, asset)
        self.assertEqual(first.state, DetectionEvent.STATE_BLOCKED)
        self.assertEqual(
            first.previous_state,
            first.state,
            "the first sample must not read as an edge",
        )
        self.assertEqual(
            first.header.frame_id,
            _beam_frame(asset, self.harness.frames),
            "the event must be stamped in the beam's own generated frame",
        )
        self.assertEqual(
            first.workpiece_id, "",
            "a break beam reports occupancy, never identity",
        )

        # And the republished levels that follow are not events. The beam repeats
        # its state every period; one DetectionEvent per repetition would bury the
        # transitions the keep-all topic exists to carry.
        self.harness.publish_level(asset, blocked=True)
        time.sleep(1.0)
        self.assertEqual(
            len(self.harness.recorded(asset)), 1,
            "a republished level was turned into a second event",
        )

    def test_4_a_change_of_level_is_an_edge(self) -> None:
        asset = self.harness.sensors[0]["asset"]
        self.harness.publish_level(asset, blocked=False)

        events = self.harness.await_events(asset, 2, GOAL_CEILING_S)
        self.assertGreaterEqual(len(events), 2, "the falling edge produced no event")
        edge = events[1]
        self.assertEqual(edge.state, DetectionEvent.STATE_CLEAR)
        self.assertEqual(
            edge.previous_state,
            DetectionEvent.STATE_BLOCKED,
            "an edge must carry the state it left, so a consumer need keep no history",
        )
        self.assertGreater(
            edge.duration_in_previous_state.sec
            + edge.duration_in_previous_state.nanosec / 1e9,
            0.0,
            "the beam was blocked for a measurable time before it cleared",
        )

    def test_5_a_blocked_beam_inside_the_region_is_detected(self) -> None:
        # Every beam has now reported, so the wait is over and this is the
        # ordinary path: read the levels, answer the question.
        for sensor in self.harness.sensors:
            self.harness.publish_level(sensor["asset"], blocked=False)
        blocked = self.harness.sensors[1]["asset"]
        self.harness.publish_level(blocked, blocked=True)
        time.sleep(0.5)

        goal = Detect.Goal()
        goal.region_frame = self.world
        goal.region_size_m = _region()
        handle = self.harness.send(goal)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped)
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.SUCCESS,
            f"detect returned {wrapped.result.result.code}: "
            f"{wrapped.result.result.detail}",
        )
        self.assertEqual(
            len(wrapped.result.detections), 1,
            "exactly one beam was blocked",
        )
        detection = wrapped.result.detections[0]
        self.assertEqual(detection.pose.header.frame_id, self.world)
        self.assertEqual(
            detection.workpiece_id, "",
            "a break beam cannot identify what it saw",
        )
        self.assertEqual(detection.workpiece_type, "")
        self.assertEqual(detection.confidence, 1.0)
        # The pose reported is the SENSOR's, which is the only position a
        # through-beam carries — and it must be where the model puts it.
        child = _beam_frame(blocked, self.harness.frames)
        _parent, xyz, _rpy = self.harness.frames[child]
        self.assertAlmostEqual(detection.pose.pose.position.x, xyz[0], places=3)
        self.assertAlmostEqual(detection.pose.pose.position.y, xyz[1], places=3)
        self.assertAlmostEqual(detection.pose.pose.position.z, xyz[2], places=3)

    def test_6_a_region_that_excludes_every_beam_detects_nothing(self) -> None:
        # A beam is still blocked from the previous test; the region is what
        # changes. A tiny box at the world origin contains no beam.
        goal = Detect.Goal()
        goal.region_frame = self.world
        goal.region_size_m = Vector3(x=0.01, y=0.01, z=0.01)
        handle = self.harness.send(goal)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped)
        self.assertEqual(wrapped.result.result.code, ResultCode.SUCCESS)
        self.assertEqual(len(wrapped.result.detections), 0)
        self.assertIn(
            "not a report", wrapped.result.result.detail,
            "an empty region must say that it observed nothing, not that nothing "
            "is there",
        )

    def test_7_a_type_filter_is_refused_rather_than_ignored(self) -> None:
        # A through-beam reports that its volume is occupied and nothing about by
        # what. Answering anyway would either ignore the filter — a narrower
        # question than was asked — or copy the requested type into the result,
        # handing the caller its own assumption back as a reading.
        goal = Detect.Goal()
        goal.region_frame = self.world
        goal.region_size_m = _region()
        goal.workpiece_type = "workpiece"
        handle = self.harness.send(goal)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped)
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.NOT_IMPLEMENTED,
            f"a type filter returned {wrapped.result.result.code}: "
            f"{wrapped.result.result.detail}",
        )

    def test_8_a_region_with_no_volume_is_refused(self) -> None:
        # A default-constructed goal has a zero region. Answering it with an empty
        # list would be a wrong answer that looks exactly like a right one.
        goal = Detect.Goal()
        goal.region_frame = self.world
        goal.region_size_m = Vector3(x=0.0, y=0.0, z=0.0)
        handle = self.harness.send(goal)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped)
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.PRECONDITION_FAILED,
            f"a zero-volume region returned {wrapped.result.result.code}: "
            f"{wrapped.result.result.detail}",
        )

    def test_9_the_event_topic_is_the_one_the_line_subscribes_to(self) -> None:
        """The events land where L4's station triggers listen.

        `cell_a_flow.yaml` names a trigger topic per station and
        `StationTopology.msg` documents it as a DetectionEvent topic. This is the
        node that publishes it. v1's handoff died of publishing to a topic nothing
        subscribed to, and the only defence is to check that the two names are the
        same name.
        """
        flow = _read(GENERATED / "topology" / f"{ZONE}_flow.yaml")
        triggers = {
            station["trigger"]["topic"]
            for station in flow["topology"]["stations"]
            if station.get("trigger")
        }
        self.assertTrue(triggers, "the generated topology declares no triggers")
        published = {sensor["detection_topic"] for sensor in self.harness.sensors}
        self.assertTrue(
            triggers <= published,
            f"stations trigger on {triggers - published}, which no beam publishes",
        )
        # And the events actually arrived on them, rather than merely being named.
        for sensor in self.harness.sensors:
            if sensor["detection_topic"] in triggers:
                self.assertTrue(
                    self.harness.recorded(sensor["asset"]),
                    f"no event was ever received on {sensor['detection_topic']}",
                )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_detection_server_exited_cleanly(self, proc_info) -> None:
        # The goal thread must be joined before the node it holds is destroyed. A
        # detached one crashes here and only here.
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            if not name.startswith("detection_server"):
                continue
            self.assertIn(
                info.returncode, allowed, f"{name} exited with {info.returncode}")
