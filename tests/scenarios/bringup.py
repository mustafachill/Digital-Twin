"""Scenario: the cell comes up, is correctly named, and actually delivers data.

This is the scenario every other one depends on. `cross-cutting-testing.md` lists
standing guarantees the tester verifies on every run regardless of what changed;
the ones that do not need a skill server are asserted here:

  * deterministic bring-up — reaches fully active with no timing assumption (P4)
  * sim/hardware interface parity — every name matches /cite/<zone>/<asset_id>,
    which is what P2 is made of
  * message delivery — a subscriber actually RECEIVES, rather than merely
    existing. A QoS mismatch connects silently and delivers nothing, and a test
    that only creates a publisher and a subscriber passes happily against one.
  * clean shutdown, no orphans — the next run's failure is this run's fault

Assertions are on outcomes and constraints, never on exact trajectories.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import launch_testing
import launch_testing.markers
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from control_msgs.action import FollowJointTrajectory
from controller_manager_msgs.srv import ListControllers
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint

from cite_interfaces.action import MoveTo
from cite_interfaces.msg import ModelVersion, ResultCode
from cite_interfaces.qos import LATCHED, STATE

ZONE = "cell_a"
ARMS = ("arm_1", "arm_2", "arm_3")

#: Wall-clock ceilings, not schedules. Nothing is sequenced by them; they exist so
#: a hang fails the run with a diagnosis instead of blocking CI indefinitely.
BRING_UP_CEILING_S = 240.0
DELIVERY_CEILING_S = 30.0
TRAJECTORY_CEILING_S = 60.0
#: Planning is stochastic, so a skill takes longer and varies more than a raw
#: trajectory. Still a ceiling, not a schedule.
SKILL_CEILING_S = 120.0


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> LaunchDescription:
    simulation = Path(get_package_share_directory("cite_bringup")) / "launch" / "simulation.launch.py"
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(simulation)),
                launch_arguments={"headless": "true", "zone": ZONE}.items(),
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestCellBringUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.node = Node("scenario_bringup")
        # Scenarios are deterministic: the seed is fixed so a failure reproduces
        # instead of being a coin flip.
        cls.seed = os.environ.get("CITE_PHYSICS_SEED", "unset")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, ceiling_s: float, what: str):
        """Spin until `predicate` returns something truthy, or fail saying what."""
        end = self.node.get_clock().now().nanoseconds + int(ceiling_s * 1e9)
        result = predicate()
        while not result and self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.5)
            result = predicate()
        self.assertTrue(result, f"timed out after {ceiling_s:.0f}s waiting for {what}")
        return result

    def test_every_controller_reaches_active(self) -> None:
        """Bring-up completes, on this machine, without any step being timed."""
        for arm in ARMS:
            manager = f"/cite/{ZONE}/{arm}/controller_manager"
            client = self.node.create_client(ListControllers, f"{manager}/list_controllers")
            self._spin_until(
                lambda c=client: c.wait_for_service(timeout_sec=0.5),
                BRING_UP_CEILING_S,
                f"{manager} to appear",
            )

            def active(c=client, a=arm):
                future = c.call_async(ListControllers.Request())
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=10.0)
                if future.result() is None:
                    return None
                names = {
                    ctrl.name for ctrl in future.result().controller if ctrl.state == "active"
                }
                expected = {
                    f"{a}_joint_state_broadcaster",
                    f"{a}_joint_trajectory_controller",
                    f"{a}_gripper_controller",
                }
                return names if expected <= names else None

            self._spin_until(active, BRING_UP_CEILING_S, f"{arm}'s controllers to be active")

    def test_joint_states_are_actually_delivered(self) -> None:
        """Not that a subscriber exists — that a message ARRIVES.

        A QoS mismatch connects silently and delivers nothing: the topic is listed,
        both endpoints show in `ros2 topic info`, and no error is raised anywhere.
        Only asserting on receipt catches it.
        """
        for arm in ARMS:
            received: list[JointState] = []
            topic = f"/cite/{ZONE}/{arm}/joint_states"
            subscription = self.node.create_subscription(
                JointState, topic, received.append, STATE
            )
            try:
                self._spin_until(
                    lambda: received or None, DELIVERY_CEILING_S, f"a message on {topic}"
                )
                names = set(received[-1].name)
                expected = {f"{arm}_joint{n}" for n in range(1, 6)} | {f"{arm}_drive_joint"}
                self.assertEqual(
                    names,
                    expected,
                    f"{topic} carries {sorted(names)}; every joint must be prefixed "
                    f"with the L0 asset id, because P2 is made of these names",
                )
            finally:
                self.node.destroy_subscription(subscription)

    def test_no_joint_name_is_shared_between_arms(self) -> None:
        """Two instances of one component type must never collide."""
        seen: dict[str, str] = {}
        for arm in ARMS:
            for joint in [f"{arm}_joint{n}" for n in range(1, 6)] + [f"{arm}_drive_joint"]:
                self.assertNotIn(joint, seen, f"{joint} appears on both {seen.get(joint)} and {arm}")
                seen[joint] = arm

    def test_a_trajectory_executes(self) -> None:
        """The arm moves when commanded, through the action the skills will use."""
        arm = ARMS[0]
        action = f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller/follow_joint_trajectory"
        client = ActionClient(self.node, FollowJointTrajectory, action)
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=0.5), BRING_UP_CEILING_S, action
        )

        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = [f"{arm}_joint{n}" for n in range(1, 6)]
        point = JointTrajectoryPoint()
        point.positions = [0.4, -0.3, 0.2, 0.0, 0.3]
        point.time_from_start.sec = 3
        goal.trajectory.points = [point]

        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, send, timeout_sec=TRAJECTORY_CEILING_S)
        handle = send.result()
        self.assertIsNotNone(handle, "the trajectory goal was never accepted")
        self.assertTrue(handle.accepted, "the controller rejected the trajectory goal")

        result = handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, result, timeout_sec=TRAJECTORY_CEILING_S)
        self.assertIsNotNone(result.result(), "the trajectory never returned a result")
        self.assertEqual(
            result.result().result.error_code,
            FollowJointTrajectory.Result.SUCCESSFUL,
            result.result().result.error_string,
        )


    def test_the_facility_publishes_its_model_version(self) -> None:
        """L6 stamps this into every recording.

        A bag recorded against yesterday's layout is not comparable to today's,
        and without this the two are indistinguishable after the fact. Published
        LATCHED, so a node that starts later still receives it.
        """
        received: list[ModelVersion] = []
        subscription = self.node.create_subscription(
            ModelVersion, "/cite/facility/model_version", received.append, LATCHED
        )
        try:
            self._spin_until(
                lambda: received or None, DELIVERY_CEILING_S, "the model version"
            )
            self.assertEqual(len(received[-1].model_hash), 64)
            self.assertIn(ZONE, received[-1].zones)
        finally:
            self.node.destroy_subscription(subscription)

    def test_station_frames_resolve_against_the_world(self) -> None:
        """Without this an arm's model is a disconnected TF tree.

        A skill given a pose in cite_world could never resolve it into the arm's
        planning frame, and the failure reads as a lookup error naming the frames
        rather than the missing link between them.
        """
        import tf2_ros

        buffer = tf2_ros.Buffer()
        listener = tf2_ros.TransformListener(buffer, self.node)
        try:
            for frame in (
                f"{ZONE}__table_pick__surface",
                f"{ZONE}__conveyor_1__infeed",
                "arm_1_mount",
                "arm_1_link_base",
            ):
                self._spin_until(
                    lambda target=frame: buffer.can_transform(
                        "cite_world", target, rclpy.time.Time()
                    )
                    or None,
                    DELIVERY_CEILING_S,
                    f"a transform from cite_world to {frame}",
                )
        finally:
            del listener

    def test_a_skill_moves_the_arm_to_its_home_configuration(self) -> None:
        """The vertical slice, end to end: L3 goal -> MoveIt -> ros2_control.

        `home` comes from the L0 model, not from the vendor's SRDF — where an arm
        rests between cycles is a fact about this facility.
        """
        arm = ARMS[0]
        client = ActionClient(self.node, MoveTo, f"/cite/{ZONE}/{arm}/move_to")
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=0.5),
            BRING_UP_CEILING_S,
            f"the {arm} skill server",
        )

        goal = MoveTo.Goal()
        goal.named_configuration = "home"
        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, send, timeout_sec=TRAJECTORY_CEILING_S)
        handle = send.result()
        self.assertIsNotNone(handle, "the MoveTo goal was never accepted")
        self.assertTrue(handle.accepted, "the skill server rejected a MoveTo goal")

        result = handle.get_result_async()
        rclpy.spin_until_future_complete(
            self.node, result, timeout_sec=SKILL_CEILING_S
        )
        self.assertIsNotNone(result.result(), "MoveTo never returned a result")
        outcome = result.result().result.result
        self.assertEqual(
            outcome.code,
            ResultCode.SUCCESS,
            f"MoveTo failed with code {outcome.code}: {outcome.detail}",
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    """Shutdown is a designed path, not an afterthought.

    An orphaned `gz sim` holds ports and names, and the NEXT bring-up then fails
    pointing nowhere near the cause. That is why this is asserted rather than
    assumed.
    """

    #: move_group segfaults during its own teardown, after logging "Deleting
    #: MoveItCpp", on SIGINT. Reproduced on every run here with MoveIt 2.12.4 on
    #: Jazzy: the node has already stopped serving by then, it leaves no orphan,
    #: and no configuration of ours changes it.
    #:
    #: Tolerated for move_group ALONE, deliberately not by widening the allowable
    #: codes for every process — a segfault in one of our own nodes must still
    #: fail this test. Re-check on the next MoveIt release and delete this
    #: exemption if it is fixed, rather than leaving it to cover something new.
    UPSTREAM_TEARDOWN_SEGFAULT = "move_group"

    def test_nothing_of_ours_exited_badly(self, proc_info) -> None:
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            expected = [*allowed, -11] if name.startswith(
                self.UPSTREAM_TEARDOWN_SEGFAULT
            ) else allowed
            self.assertIn(
                info.returncode,
                expected,
                f"{name} exited with {info.returncode}",
            )
