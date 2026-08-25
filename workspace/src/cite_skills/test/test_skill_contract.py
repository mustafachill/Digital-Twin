"""The parts of the skill contract that only a running server can show.

Three of them, and each one is a defect this branch shipped:

1. Four action servers share one arm, one MoveGroupInterface and one gripper. A
   second goal accepted while one is in flight lets two goals share a planner
   that is not thread-safe — and the shipped recovery path reached it, because
   the coordinator abandons a goal on its deadline without cancelling it and the
   tree's fallback then sends another goal to the same server.
2. `Grasp` accepted cancellation and ignored it: it never checked
   `is_canceling()`, never kept the gripper's goal handle, and reported success
   for a goal the caller had cancelled.
3. A pose goal on a 5-DOF arm is satisfied by random draws that are almost never
   reachable (ADR-0026). The skill server now solves IK on the exact pose and
   plans to the joint configuration.

There is no simulator here and there are no controllers: move_group plans, and
execution always fails. That is what makes the rig useful — it separates "the
planner produced a trajectory" from "the trajectory ran", which is the
distinction the failing `pick_and_place` needed and could not make.
"""

from __future__ import annotations

import math
import threading
import time
import unittest
from pathlib import Path

import launch_testing
import launch_testing.markers
import pytest
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from control_msgs.action import GripperCommand
from geometry_msgs.msg import PoseStamped
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node as RclpyNode
from sensor_msgs.msg import JointState

from cite_interfaces.action import Grasp, MoveTo
from cite_interfaces.msg import ResultCode

ZONE = "cell_a"
ASSET = "arm_1"
NAMESPACE = f"/cite/{ZONE}/{ASSET}"
GRIPPER_ACTION = "/test_gripper/gripper_cmd"

#: A pose the arm can reach, stated in the arm's own base frame: the approach
#: point of the pick the failing scenario could not plan. Its tool axis points
#: down and its yaw faces the target, which is exactly reachable — IK solves it 8
#: times out of 8 — while the pose goal that used to be sent for it planned 3
#: times out of 8. A test is allowed to state its own initial conditions; this is
#: the only number here that is not read from the model, and it is in the arm's
#: own frame, so where the arm stands in the facility does not change it.
REACHABLE_XYZ = (0.35, 0.45, 0.13)

STARTUP_CEILING_S = 180.0
GOAL_CEILING_S = 120.0

GENERATED = Path(get_package_share_directory("cite_generated"))


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _resolve(uri: str) -> Path:
    """A `package://cite_generated/...` reference from the plan, as a path."""
    prefix = "package://cite_generated/"
    assert uri.startswith(prefix), f"unexpected artifact reference: {uri}"
    return GENERATED / uri[len(prefix):]


def _plan() -> dict:
    """This arm's entry in the generated bring-up plan.

    Read rather than restated. The planning group, the tip link and the home
    configuration are facts about the facility that already exist in the L0
    model; a copy of them here would be a second place they are written (P1),
    and it would go stale silently the first time the model changed.
    """
    plan = _read(GENERATED / "bringup" / f"{ZONE}_plan.yaml")
    for manager in plan["plan"]["controller_managers"]:
        if manager["asset"] == ASSET:
            return manager
    raise AssertionError(f"the generated plan has no entry for {ASSET}")


def _joints(manager: dict) -> list:
    """The arm's joints, plus the gripper's drive joint, as ros2_control has them.

    The skill server's MoveIt client waits for a complete joint state, so a
    missing drive joint means it never learns where the arm is.
    """
    controllers = _read(_resolve(manager["parameters"]))
    names: list = []
    for key, value in controllers.items():
        parameters = value.get("ros__parameters", {})
        if key.endswith("_joint_trajectory_controller"):
            names.extend(parameters["joints"])
        elif key.endswith("_gripper_controller") and "joint" in parameters:
            names.append(parameters["joint"])
    assert names, "no joints found in the generated controller configuration"
    return names


def _yaml_parameters(path: Path, prefix: str) -> dict:
    return {prefix: _read(path)}


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> LaunchDescription:
    manager = _plan()
    moveit = manager["moveit"]
    description = ParameterValue(
        Command(["xacro ", str(_resolve(manager["description"]))]), value_type=str
    )
    semantic = ParameterValue(
        Command(["xacro ", str(_resolve(moveit["srdf"]))]), value_type=str
    )
    kinematics = _yaml_parameters(
        _resolve(moveit["kinematics"]), "robot_description_kinematics"
    )
    planning = _yaml_parameters(
        _resolve(moveit["joint_limits"]), "robot_description_planning"
    )
    ompl = _read(_resolve(moveit["ompl"]))
    controllers = _read(_resolve(moveit["controllers"]))

    return LaunchDescription(
        [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                namespace=NAMESPACE,
                parameters=[{"robot_description": description, "use_sim_time": False}],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="log",
            ),
            Node(
                package="moveit_ros_move_group",
                executable="move_group",
                name="move_group",
                namespace=NAMESPACE,
                parameters=[
                    {
                        "robot_description": description,
                        "robot_description_semantic": semantic,
                        "use_sim_time": False,
                        "publish_robot_description_semantic": True,
                    },
                    kinematics,
                    planning,
                    ompl,
                    controllers,
                ],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="log",
            ),
            Node(
                package="cite_skills",
                executable="skill_server",
                name="skill_server",
                namespace=NAMESPACE,
                parameters=[
                    {
                        "robot_description": description,
                        "robot_description_semantic": semantic,
                    },
                    kinematics,
                    planning,
                    {
                        "asset_id": ASSET,
                        "zone": ZONE,
                        "planning_group": moveit["group"],
                        "tip_link": moveit["tip_link"],
                        "gripper_action": GRIPPER_ACTION,
                        "home_rad": list(moveit["home_rad"]),
                        "use_sim_time": False,
                    },
                ],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class Harness(RclpyNode):
    """Everything the skill server needs to exist, and the clients that drive it.

    The gripper is served here rather than by a controller: a gripper that never
    finishes on its own is what makes cancellation observable at all.
    """

    def __init__(self) -> None:
        super().__init__("skill_contract_harness")
        manager = _plan()
        self.moveit = manager["moveit"]
        self.joints = _joints(manager)
        # Every joint at zero except the arm's, which rest at the configuration
        # the L0 model calls home.
        home = list(self.moveit["home_rad"])
        self.positions = home + [0.0] * (len(self.joints) - len(home))
        self.callbacks = ReentrantCallbackGroup()
        self.gripper_running = threading.Event()
        self.gripper_cancelled = threading.Event()

        self.states = self.create_publisher(JointState, f"{NAMESPACE}/joint_states", 10)
        self.create_timer(0.05, self._publish_state, callback_group=self.callbacks)

        self.gripper = ActionServer(
            self,
            GripperCommand,
            GRIPPER_ACTION,
            execute_callback=self._hold_until_cancelled,
            goal_callback=lambda _goal: GoalResponse.ACCEPT,
            cancel_callback=lambda _goal: CancelResponse.ACCEPT,
            callback_group=self.callbacks,
        )
        self.grasp = ActionClient(self, Grasp, f"{NAMESPACE}/grasp",
                                  callback_group=self.callbacks)
        self.move_to = ActionClient(self, MoveTo, f"{NAMESPACE}/move_to",
                                    callback_group=self.callbacks)

    def _publish_state(self) -> None:
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = self.joints
        message.position = self.positions
        self.states.publish(message)

    def _hold_until_cancelled(self, goal_handle):
        self.gripper_running.set()
        while not goal_handle.is_cancel_requested:
            time.sleep(0.05)
        self.gripper_cancelled.set()
        goal_handle.canceled()
        return GripperCommand.Result()

    @staticmethod
    def wait(future, timeout: float):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if future.done():
                return future.result()
            time.sleep(0.05)
        return None


class TestSkillContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.harness = Harness()
        cls.executor = MultiThreadedExecutor()
        cls.executor.add_node(cls.harness)
        cls.spinner = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.spinner.start()
        assert cls.harness.grasp.wait_for_server(STARTUP_CEILING_S), (
            "the skill server never advertised 'grasp'"
        )
        assert cls.harness.move_to.wait_for_server(STARTUP_CEILING_S), (
            "the skill server never advertised 'move_to'"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.executor.shutdown()
        cls.harness.destroy_node()
        rclpy.shutdown()

    def test_1_one_goal_at_a_time_and_a_cancel_that_is_honoured(self) -> None:
        grasp = Grasp.Goal()
        grasp.width_m = 0.0
        grasp.max_effort_n = 10.0
        grasp.expect_object = False
        grasp_handle = self.harness.wait(
            self.harness.grasp.send_goal_async(grasp), GOAL_CEILING_S)
        self.assertIsNotNone(grasp_handle, "the grasp goal was never answered")
        self.assertTrue(grasp_handle.accepted, "the first goal must be accepted")
        self.assertTrue(
            self.harness.gripper_running.wait(GOAL_CEILING_S),
            "the skill server never commanded the gripper",
        )

        # A second goal, while the first still holds the arm. Accepting it would
        # put two goals on one planner and one trajectory.
        blocked = MoveTo.Goal()
        blocked.named_configuration = "home"
        blocked_handle = self.harness.wait(
            self.harness.move_to.send_goal_async(blocked), GOAL_CEILING_S)
        self.assertIsNotNone(blocked_handle, "the second goal was never answered")
        self.assertFalse(
            blocked_handle.accepted,
            "a second goal was accepted while a grasp was in flight",
        )

        # And the cancel must reach the gripper rather than being noticed after
        # it has finished.
        self.harness.wait(grasp_handle.cancel_goal_async(), GOAL_CEILING_S)
        self.assertTrue(
            self.harness.gripper_cancelled.wait(GOAL_CEILING_S),
            "the cancelled grasp never cancelled the gripper command",
        )
        wrapped = self.harness.wait(grasp_handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped, "the cancelled grasp never reported a result")
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.CANCELLED,
            f"a cancelled grasp reported {wrapped.result.result.code}: "
            f"{wrapped.result.result.detail}",
        )

    def test_2_a_cartesian_path_is_refused_rather_than_silently_replaced(self) -> None:
        # The field is declared, so it gets an answer. Planning it as an ordinary
        # joint-space move would give a caller asking for a straight line a
        # different, possibly colliding, motion (ADR-0026).
        goal = MoveTo.Goal()
        goal.cartesian_path = True
        goal.named_configuration = "home"
        handle = self.harness.wait(
            self.harness.move_to.send_goal_async(goal), GOAL_CEILING_S)
        self.assertIsNotNone(handle)
        self.assertTrue(handle.accepted)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped)
        self.assertEqual(wrapped.result.result.code, ResultCode.NOT_IMPLEMENTED)

    def test_3_a_reachable_pose_is_planned_to_rather_than_refused(self) -> None:
        # The regression that matters: this exact pose, sent as a 6-DOF pose
        # goal, planned 3 times out of 8 and failed the rest with
        # PLANNING_FAILED. Solved as IK and planned as a joint configuration it
        # succeeds every time. There are no controllers here, so the trajectory
        # cannot run — EXECUTION_FAILED means the planner produced one.
        yaw = math.atan2(REACHABLE_XYZ[1], REACHABLE_XYZ[0])
        goal = MoveTo.Goal()
        goal.target = PoseStamped()
        # The arm's own base frame, named by the generated plan. Nothing here
        # depends on where the arm stands in the facility.
        goal.target.header.frame_id = self.harness.moveit["base_link"]
        (goal.target.pose.position.x,
         goal.target.pose.position.y,
         goal.target.pose.position.z) = REACHABLE_XYZ
        # Tool pointing down, yawed to face the target: roll pi then yaw.
        goal.target.pose.orientation.x = math.cos(yaw / 2.0)
        goal.target.pose.orientation.y = math.sin(yaw / 2.0)
        goal.target.pose.orientation.z = 0.0
        goal.target.pose.orientation.w = 0.0

        handle = self.harness.wait(
            self.harness.move_to.send_goal_async(goal), GOAL_CEILING_S)
        self.assertIsNotNone(handle)
        self.assertTrue(handle.accepted)
        wrapped = self.harness.wait(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(wrapped, "the move never reported a result")
        self.assertNotEqual(
            wrapped.result.result.code,
            ResultCode.PLANNING_FAILED,
            f"a reachable pose was refused: {wrapped.result.result.detail}",
        )
        self.assertEqual(
            wrapped.result.result.code,
            ResultCode.EXECUTION_FAILED,
            f"expected the plan to run and fail for want of a controller, got "
            f"{wrapped.result.result.code}: {wrapped.result.result.detail}",
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_skill_server_exited_cleanly(self, proc_info) -> None:
        # A goal thread that outlives its node crashes here, and only here: the
        # detached threads this replaced were never joined, so teardown ran the
        # node's destructor underneath them.
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            if not name.startswith("skill_server"):
                continue
            self.assertIn(
                info.returncode, allowed, f"{name} exited with {info.returncode}")
