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

"""What the generated MoveIt configuration is worth to a running move_group.

ADR-0027 decides that station-to-station motion is planned by Pilz, with OMPL
kept as the fallback. Everything about that decision is *configuration*, and
configuration is exactly the kind of change that generates cleanly, launches
without an error, and then does nothing — so this file drives the real binary
against the real generated files and asks three questions a unit test cannot.

1. **Did the pipeline load at all?** `query_planner_interface` answers it, and it
   is not a formality: a planning plugin that fails to load leaves move_group
   running and every request failing.

2. **Can it actually plan?** This is the one that matters, and it is separate
   from the first because Pilz's limit checks happen at PLAN time. A missing
   `has_deceleration_limits` produces a pipeline that loads perfectly and then
   throws "deceleration limit not set for group" on every single request. Nothing
   short of asking for a plan can see that.

3. **Is the answer the same twice?** That is the whole reason ADR-0027 exists.
   PTP integrates a trapezoidal profile over the joint limits; it draws no random
   numbers, so the same request must produce the same trajectory to the bit. The
   assertion here is a *planner* property and not a scenario guarantee — ADR-0006
   still forbids a scenario asserting on a trajectory, and this file is allowed to
   because it is asserting on the planner's determinism rather than using a
   trajectory as a proxy for a motion having gone well.

There is no simulator, no controller and no skill server here: move_group plans,
and nothing executes. That is what keeps the file about the configuration.

There is no post-shutdown exit-code assertion here. What one would be asked to
prove — that a refused LIN request does not take move_group down — is proven
instead by test 8 planning successfully after test 7 was refused, through the same
service and the same process.

A fourth question is asked because ADR-0027 answers it too loosely. It lists LIN
as "available for the moves where a defined Cartesian path is the requirement",
and on a five-joint arm that is true for a much narrower set of moves than it
reads. Both halves are asserted here rather than described: LIN plans a purely
vertical approach at a fixed base yaw, and refuses a motion that turns the base.
Neither is a simulation artefact — a straight Cartesian path needs the full
six-degree-of-freedom pose solvable at every sample along it, this arm's tool
axis is confined to the plane its first joint points at (ADR-0026), and both
statements hold identically on the hardware.
"""

from __future__ import annotations

from pathlib import Path
import threading
import time
import unittest

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import launch_testing
import launch_testing.markers
from moveit_msgs.msg import Constraints, JointConstraint, MoveItErrorCodes, RobotState
from moveit_msgs.srv import (
    GetMotionPlan,
    GetPositionFK,
    GetPositionIK,
    QueryPlannerInterfaces,
)
import pytest
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node as RclpyNode
from sensor_msgs.msg import JointState
import yaml

ZONE = "cell_a"
#: A DIFFERENT arm from the one `test_skill_contract.py` drives, and that is the
#: reason it is named here rather than taken as "the first arm in the plan".
#: There is one DDS domain per checkout (`scripts/_lib.sh`), colcon runs the two
#: launch tests concurrently, and two `move_group` nodes in one namespace answer
#: each other's service calls. The symptom is a test that passes alone and fails
#: in the suite, which is the worst shape a failure can take.
ASSET = "arm_2"
NAMESPACE = f"/cite/{ZONE}/{ASSET}"

STARTUP_CEILING_S = 180.0
CALL_CEILING_S = 120.0

#: How far the first joint is asked to move. Small, in free space, and away from
#: every limit: the question here is which planner answers and whether it answers
#: the same way twice, not whether this arm can reach anything difficult.
JOINT1_TARGET_RAD = 0.30

GENERATED = Path(get_package_share_directory("cite_generated"))


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _resolve(uri: str) -> Path:
    prefix = "package://cite_generated/"
    assert uri.startswith(prefix), f"unexpected artifact reference: {uri}"
    return GENERATED / uri[len(prefix):]


def _plan() -> dict:
    """Return this arm's entry in the generated bring-up plan.

    Read rather than restated, for the reason every other test in this package
    reads it: the group name, the joints and the planner choice are already in
    the model, and a copy here would be a second place they are written (P1).
    """
    plan = _read(GENERATED / "bringup" / f"{ZONE}_plan.yaml")
    for manager in plan["plan"]["controller_managers"]:
        if manager["asset"] == ASSET:
            return manager
    raise AssertionError(f"the generated plan has no entry for {ASSET}")


def _arm_joints(manager: dict) -> list:
    """Return the arm's joints, in the order the generated controller declares them."""
    controllers = _read(_resolve(manager["parameters"]))
    for key, value in controllers.items():
        if key.endswith("_joint_trajectory_controller"):
            return list(value["ros__parameters"]["joints"])
    raise AssertionError("no joint trajectory controller in the generated configuration")


def _gripper_joint(manager: dict) -> str | None:
    controllers = _read(_resolve(manager["parameters"]))
    for key, value in controllers.items():
        if key.endswith("_gripper_controller"):
            return value["ros__parameters"].get("joint")
    return None


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
    # Exactly the merge `cite_bringup` performs, and for exactly its reason: the
    # joint limits and the Cartesian limits are two files and one MoveIt
    # parameter namespace. Pilz's Cartesian parameter listener declares its four
    # keys with no defaults, so a run without the second file does not disable
    # LIN — it takes move_group down while the pipeline initialises.
    planning = {
        **_read(_resolve(moveit["joint_limits"])),
        **_read(_resolve(moveit["cartesian_limits"])),
    }

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
                    {"robot_description_kinematics": _read(_resolve(moveit["kinematics"]))},
                    {"robot_description_planning": planning},
                    _read(_resolve(moveit["planning_pipelines"])),
                    _read(_resolve(moveit["controllers"])),
                ],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class Harness(RclpyNode):
    """A joint state for move_group to plan from, and the two service clients."""

    def __init__(self) -> None:
        super().__init__("planning_pipeline_harness")
        manager = _plan()
        self.moveit = manager["moveit"]
        self.arm_joints = _arm_joints(manager)
        gripper = _gripper_joint(manager)
        self.home = list(self.moveit["home_rad"])

        self.names = list(self.arm_joints) + ([gripper] if gripper else [])
        self.positions = list(self.home) + ([0.0] if gripper else [])

        self.callbacks = ReentrantCallbackGroup()
        self.states = self.create_publisher(JointState, f"{NAMESPACE}/joint_states", 10)
        self.create_timer(0.05, self._publish_state, callback_group=self.callbacks)
        self.query = self.create_client(
            QueryPlannerInterfaces,
            f"{NAMESPACE}/query_planner_interface",
            callback_group=self.callbacks,
        )
        self.plan = self.create_client(
            GetMotionPlan,
            f"{NAMESPACE}/plan_kinematic_path",
            callback_group=self.callbacks,
        )
        # move_group's own kinematics services. Used rather than a hard-coded
        # joint configuration so that the LIN cases below stay expressed in the
        # terms they are actually about — a tool moving so far along an axis —
        # and keep meaning that after the arm or its home pose changes.
        self.fk = self.create_client(
            GetPositionFK, f"{NAMESPACE}/compute_fk", callback_group=self.callbacks
        )
        self.ik = self.create_client(
            GetPositionIK, f"{NAMESPACE}/compute_ik", callback_group=self.callbacks
        )

    def _publish_state(self) -> None:
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = self.names
        message.position = self.positions
        self.states.publish(message)

    def request(
        self, pipeline: str, planner_id: str, goal=None
    ) -> GetMotionPlan.Request:
        """Build a joint-space goal one joint away from where the arm stands.

        Joint space rather than a pose, because that is the only goal form this
        cell's L3 sends: a 5-DOF arm cannot be given an arbitrary Cartesian pose
        goal, so the skill server solves IK itself and plans to the resulting
        configuration (ADR-0026). Testing the pipeline with a goal shape nothing
        sends would prove something about MoveIt rather than about this cell.
        """
        request = GetMotionPlan.Request()
        motion = request.motion_plan_request
        motion.group_name = self.moveit["group"]
        motion.pipeline_id = pipeline
        motion.planner_id = planner_id
        motion.num_planning_attempts = 1
        motion.allowed_planning_time = 5.0
        motion.max_velocity_scaling_factor = 0.35
        motion.max_acceleration_scaling_factor = 0.35
        # An empty diff against the current state: move_group starts from wherever
        # the joint states above put the arm, which is home.
        motion.start_state.is_diff = True

        # Floats, explicitly. The home configuration is read from generated YAML
        # where `0` is an integer, and rosidl's Python conversion asserts on the
        # C side rather than raising — the process dies at
        # `PyFloat_Check(field)` with no Python traceback and no field name.
        if goal is None:
            target = [float(value) for value in self.home]
            target[0] = JOINT1_TARGET_RAD
        else:
            target = [float(value) for value in goal]
        constraints = Constraints()
        for name, position in zip(self.arm_joints, target):
            constraint = JointConstraint()
            constraint.joint_name = name
            constraint.position = float(position)
            constraint.tolerance_above = 1e-4
            constraint.tolerance_below = 1e-4
            constraint.weight = 1.0
            constraints.joint_constraints.append(constraint)
        motion.goal_constraints.append(constraints)
        return request

    def _state(self, positions) -> RobotState:
        state = RobotState()
        joint_state = JointState()
        joint_state.name = list(self.arm_joints)
        joint_state.position = [float(value) for value in positions]
        state.joint_state = joint_state
        return state

    def home_tool_pose(self) -> PoseStamped:
        """Where the tool stands when the arm is at the home configuration L0 names."""
        request = GetPositionFK.Request()
        request.header.frame_id = self.moveit["base_link"]
        request.fk_link_names = [self.moveit["tip_link"]]
        request.robot_state = self._state(self.home)
        response = self.call(self.fk, request)
        assert response is not None, "compute_fk never answered"
        assert response.error_code.val == MoveItErrorCodes.SUCCESS, (
            f"forward kinematics on the home configuration failed: "
            f"{response.error_code.val}"
        )
        return response.pose_stamped[0]

    def joints_for_tool_offset(self, dx: float, dy: float, dz: float):
        """Solve for the configuration that offsets the tool, orientation unchanged.

        Returns None when no configuration does, which on a five-joint arm is a
        real answer rather than a failure: its reachable poses are a surface, not
        a volume (ADR-0026), and an offset that leaves that surface has no
        solution at either end of the motion — never mind along it.
        """
        target = self.home_tool_pose()
        target.pose.position.x += dx
        target.pose.position.y += dy
        target.pose.position.z += dz

        request = GetPositionIK.Request()
        request.ik_request.group_name = self.moveit["group"]
        request.ik_request.robot_state = self._state(self.home)
        request.ik_request.pose_stamped = target
        request.ik_request.ik_link_name = self.moveit["tip_link"]
        request.ik_request.timeout.sec = 1
        response = self.call(self.ik, request)
        assert response is not None, "compute_ik never answered"
        if response.error_code.val != MoveItErrorCodes.SUCCESS:
            return None
        names = list(response.solution.joint_state.name)
        values = list(response.solution.joint_state.position)
        return [values[names.index(joint)] for joint in self.arm_joints]

    def call(self, client, request, timeout: float = CALL_CEILING_S):
        future = client.call_async(request)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if future.done():
                return future.result()
            time.sleep(0.05)
        return None

    @staticmethod
    def fingerprint(trajectory) -> list:
        """Everything about a trajectory that a second identical run must repeat."""
        return [
            (
                tuple(point.positions),
                tuple(point.velocities),
                tuple(point.accelerations),
                point.time_from_start.sec,
                point.time_from_start.nanosec,
            )
            for point in trajectory.joint_trajectory.points
        ]


class TestPlanningPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.harness = Harness()
        cls.executor = MultiThreadedExecutor()
        cls.executor.add_node(cls.harness)
        cls.spinner = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.spinner.start()
        assert cls.harness.query.wait_for_service(STARTUP_CEILING_S), (
            "move_group never advertised query_planner_interface"
        )
        assert cls.harness.plan.wait_for_service(STARTUP_CEILING_S), (
            "move_group never advertised plan_kinematic_path"
        )
        assert cls.harness.fk.wait_for_service(STARTUP_CEILING_S), (
            "move_group never advertised compute_fk"
        )
        assert cls.harness.ik.wait_for_service(STARTUP_CEILING_S), (
            "move_group never advertised compute_ik"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.executor.shutdown()
        cls.harness.destroy_node()
        rclpy.shutdown()

    def _interfaces(self) -> dict:
        response = self.harness.call(self.harness.query, QueryPlannerInterfaces.Request())
        self.assertIsNotNone(response, "query_planner_interface never answered")
        return {
            description.pipeline_id: list(description.planner_ids)
            for description in response.planner_interfaces
        }

    def test_1_both_pipelines_loaded(self) -> None:
        # The plugin loading at all. It is the cheap half of the question and it
        # is still worth asking separately: a pipeline that failed to load leaves
        # move_group up and turns every later assertion into a planning failure
        # whose message says nothing about a plugin.
        interfaces = self._interfaces()
        moveit = self.harness.moveit
        self.assertIn(
            moveit["default_pipeline"],
            interfaces,
            f"move_group loaded {sorted(interfaces)}; the generated configuration "
            f"names {moveit['default_pipeline']} as the default pipeline",
        )
        self.assertIn(
            moveit["fallback_pipeline"],
            interfaces,
            f"move_group loaded {sorted(interfaces)}; the fallback ADR-0027 relies "
            f"on is {moveit['fallback_pipeline']}",
        )

    def test_2_the_default_planner_is_registered(self) -> None:
        interfaces = self._interfaces()
        moveit = self.harness.moveit
        self.assertIn(
            moveit["default_planner_id"],
            interfaces[moveit["default_pipeline"]],
            f"{moveit['default_pipeline']} registered "
            f"{interfaces[moveit['default_pipeline']]}",
        )

    def test_3_the_default_planner_actually_plans(self) -> None:
        # THE ONE THAT CATCHES A MISSING LIMIT. Pilz builds its trajectory
        # generator when the first request arrives, not when the pipeline loads,
        # and refuses there if any joint of the group lacks a velocity,
        # acceleration or deceleration ceiling. The two tests above pass in that
        # state; this one does not.
        moveit = self.harness.moveit
        request = self.harness.request(
            moveit["default_pipeline"], moveit["default_planner_id"]
        )
        response = self.harness.call(self.harness.plan, request)
        self.assertIsNotNone(response, "plan_kinematic_path never answered")
        result = response.motion_plan_response
        self.assertEqual(
            result.error_code.val,
            MoveItErrorCodes.SUCCESS,
            f"{moveit['default_pipeline']}/{moveit['default_planner_id']} refused a "
            f"one-joint move in free space with error code {result.error_code.val}",
        )
        self.assertGreater(
            len(result.trajectory.joint_trajectory.points),
            1,
            "the planner reported success and returned no motion",
        )

    def test_4_the_same_request_produces_the_same_trajectory(self) -> None:
        # ADR-0027's entire point, stated as an assertion. A sampling planner
        # cannot pass this: OMPL draws its per-instance seeds from a
        # process-global generator whose hand-out order is not fixed across
        # threads, so two identical requests do different work. Pilz integrates a
        # profile, which is a computation.
        #
        # This asserts on a trajectory, which ADR-0006 forbids a SCENARIO from
        # doing. The rule and this test are not in conflict: the rule exists
        # because a scenario uses a trajectory as a proxy for a motion having
        # gone well, and a stochastic planner makes that proxy flaky. Here the
        # trajectory is the subject, not the proxy.
        moveit = self.harness.moveit
        first = self.harness.call(
            self.harness.plan,
            self.harness.request(moveit["default_pipeline"], moveit["default_planner_id"]),
        )
        second = self.harness.call(
            self.harness.plan,
            self.harness.request(moveit["default_pipeline"], moveit["default_planner_id"]),
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.motion_plan_response.error_code.val, MoveItErrorCodes.SUCCESS)
        self.assertEqual(second.motion_plan_response.error_code.val, MoveItErrorCodes.SUCCESS)
        self.assertEqual(
            self.harness.fingerprint(first.motion_plan_response.trajectory),
            self.harness.fingerprint(second.motion_plan_response.trajectory),
            "two identical requests to the deterministic planner produced different "
            "trajectories; whatever ADR-0027 bought, it did not buy this",
        )

    def test_5_the_fallback_pipeline_still_plans(self) -> None:
        # The fallback has to work on the day the default refuses, and the day it
        # refuses is not the day to find out. Its planner id is empty, which is
        # what the model says and what the skill server sends: the generated OMPL
        # block declares one planner configuration for this group, so "the
        # pipeline's own default" is unambiguous.
        moveit = self.harness.moveit
        request = self.harness.request(
            moveit["fallback_pipeline"], moveit["fallback_planner_id"] or ""
        )
        response = self.harness.call(self.harness.plan, request)
        self.assertIsNotNone(response, "plan_kinematic_path never answered")
        self.assertEqual(
            response.motion_plan_response.error_code.val,
            MoveItErrorCodes.SUCCESS,
            f"the fallback pipeline {moveit['fallback_pipeline']} refused a one-joint "
            f"move in free space with error code "
            f"{response.motion_plan_response.error_code.val}",
        )

    # -------------------------------------------------------------------------
    # LIN on a five-joint arm — both halves of the answer, because there are two
    # -------------------------------------------------------------------------
    #
    # ADR-0027 lists LIN among what Pilz gets us, "available for the moves where
    # a defined Cartesian path is the requirement rather than a preference".
    # Measured on this arm on 2026-08-27, that sentence is true and much narrower
    # than it reads, and the two tests below are the measurement.
    #
    # LIN interpolates the tool's POSE — position linearly, orientation by
    # spherical interpolation — and solves full six-degree-of-freedom IK at every
    # sample. This arm has one yaw joint, three parallel pitch joints and one
    # wrist roll, so its tool axis is confined to the vertical plane the first
    # joint points at. A motion that keeps that plane keeps every intermediate
    # pose solvable; a motion that turns the base sweeps the plane while the
    # interpolated orientation does not follow it, and the samples in the middle
    # have no solution at all.
    #
    # Neither of these is a simulation artefact. Both are consequences of the
    # arm's kinematics and hold identically on the hardware.

    def test_6_lin_plans_an_approach_along_the_tool_axis(self) -> None:
        # The half that WORKS: straight down, orientation unchanged, first joint
        # unchanged. This is the shape of an approach and of a retreat, which is
        # the only place a defined Cartesian path is a requirement in this cell.
        goal = self.harness.joints_for_tool_offset(0.0, 0.0, -0.05)
        self.assertIsNotNone(
            goal,
            "no configuration puts the tool 50 mm below home at the same "
            "orientation; the premise of this test is gone, not its conclusion",
        )
        response = self.harness.call(
            self.harness.plan,
            self.harness.request(self.harness.moveit["default_pipeline"], "LIN", goal),
        )
        self.assertIsNotNone(response, "plan_kinematic_path never answered a LIN request")
        self.assertEqual(
            response.motion_plan_response.error_code.val,
            MoveItErrorCodes.SUCCESS,
            "LIN refused a purely vertical 50 mm move at a fixed base yaw, which is "
            "the one motion shape this arm's geometry makes solvable along its whole "
            "length. Error code "
            f"{response.motion_plan_response.error_code.val}",
        )

    def test_7_lin_refuses_a_motion_that_turns_the_base(self) -> None:
        # The half that DOES NOT, and the reason LIN is not the default planner.
        # The failure is geometric rather than stochastic: the interpolated
        # orientation halfway through leaves the plane the pitch joints live in,
        # and no seed reaches a solution that does not exist.
        #
        # Asserting a refusal is deliberate. If this ever starts passing, the
        # arm's reachable set is not what ADR-0026 measured, and a failing test
        # is the right way to be told.
        #
        # That move_group SURVIVED the refusal is proven by test 8, which plans
        # afterwards through the same service. It is deliberately not proven by a
        # post-shutdown exit code: move_group exiting -11 during teardown is a
        # known unresolved failure elsewhere in this repository, and the standing
        # instruction on the exemption that covers it is to delete it rather than
        # widen it — so this file does not add a second place that tolerates it.
        response = self.harness.call(
            self.harness.plan,
            self.harness.request(self.harness.moveit["default_pipeline"], "LIN"),
        )
        self.assertIsNotNone(
            response,
            "a LIN request was never answered; the pipeline that serves PTP must "
            "refuse LIN rather than fail to reply — a planner that takes move_group "
            "down takes the arm with it",
        )
        self.assertNotEqual(
            response.motion_plan_response.error_code.val,
            MoveItErrorCodes.SUCCESS,
            "LIN planned a straight Cartesian path across a change of base yaw on a "
            "five-joint arm. If that is real, ADR-0026's reachability measurement and "
            "this file's reasoning about why LIN is not the default are both wrong",
        )
        self.assertEqual(
            len(response.motion_plan_response.trajectory.joint_trajectory.points),
            0,
            "a refused plan came back carrying a trajectory",
        )

    def test_8_the_default_planner_makes_the_same_motion(self) -> None:
        # The complement of test 7, so that it cannot pass by the goal being
        # unreachable rather than by LIN being unable to reach it in a straight
        # line. PTP plans the same request, because it interpolates in joint
        # space and never asks what the tool's pose is in between.
        moveit = self.harness.moveit
        response = self.harness.call(
            self.harness.plan,
            self.harness.request(moveit["default_pipeline"], moveit["default_planner_id"]),
        )
        self.assertIsNotNone(response)
        self.assertEqual(
            response.motion_plan_response.error_code.val,
            MoveItErrorCodes.SUCCESS,
            "the goal LIN refused is one PTP must be able to make; if PTP refuses it "
            "too then the goal is unreachable and test 7 proves nothing",
        )
