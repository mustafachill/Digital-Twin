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
against the real generated files and asks questions a unit test cannot.

The first of them is the one the safety of the whole decision rests on, and it
is asked last because it is the only one that puts anything into move_group's
world: **is the sole remaining collision gate actually working?** Pilz does not
search the scene, so the `ValidateSolution` response adapter is now the only
thing between a generated straight line and the cell's furniture. Tests 9a and
9b load the real generated planning scene, prove that a particular joint-space
interpolation passes through a named object in it, assert the request is refused
with an empty trajectory, and then assert that the identical request succeeds
once the objects are removed. The second half is what makes the first evidence:
without it, the refusal could be coming from anywhere.

The others:

1. **Did the pipeline load at all?** `query_planner_interface` answers it, and it
   is not a formality: a planning plugin that fails to load leaves move_group
   running and every request failing.

2. **Can it actually plan?** This is the one that matters, and it is separate
   from the first because Pilz's limit checks happen at PLAN time. A missing
   `has_deceleration_limits` produces a pipeline that loads perfectly and then
   throws "deceleration limit not set for group" on every single request. Nothing
   short of asking for a plan can see that.

3. **How far apart are the checked waypoints?** `isPathValid` iterates the
   trajectory's waypoints and interpolates nothing between them, so their spacing
   IS the resolution of the collision check above. It is a C++ default argument
   in MoveIt with no ROS parameter behind it, which makes it a number that
   decides whether an obstacle is seen and that nobody had written down. Test 4b
   measures it.

4. **Is the answer the same twice?** That is the whole reason ADR-0027 exists.
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

A further question is asked because ADR-0027 answers it too loosely. It lists LIN
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
from cite_facility.artifacts import planning_scene, static_transforms
from cite_facility.transforms import quaternion_from_rpy
from geometry_msgs.msg import Pose, PoseStamped, TransformStamped
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import launch_testing
import launch_testing.markers
from moveit_msgs.msg import (
    CollisionObject,
    Constraints,
    JointConstraint,
    MoveItErrorCodes,
    PlanningScene,
    PlanningSceneComponents,
    RobotState,
)
from moveit_msgs.srv import (
    ApplyPlanningScene,
    GetMotionPlan,
    GetPlanningScene,
    GetPositionFK,
    GetPositionIK,
    GetStateValidity,
    QueryPlannerInterfaces,
)
import pytest
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node as RclpyNode
from rclpy.time import Time as RclpyTime
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive
from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener
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

#: Pilz's sampling time, in seconds. NOT a setting — there is no parameter for
#: it — but the spacing of the only collision check a generated path receives,
#: so it is written down here and asserted rather than left as a library
#: default nobody has looked at.
SAMPLING_TIME_S = 0.1

GENERATED = Path(get_package_share_directory("cite_generated"))

#: The L0 primitive names, mapped onto `shape_msgs/SolidPrimitive`. The same
#: mapping `cite_facility`'s planning-scene loader applies. Only the box arm of
#: it is exercised by this cell; a primitive the model grows that is missing
#: here fails loudly rather than being dropped from the scene.
PRIMITIVES = {
    "box": SolidPrimitive.BOX,
    "cylinder": SolidPrimitive.CYLINDER,
    "sphere": SolidPrimitive.SPHERE,
}


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

        # --- the cell's furniture, and the frame it is expressed in ----------
        #
        # Read through `cite_facility`, which owns both readers and is what
        # bring-up itself uses. Parsing the generated YAML a second time here
        # would be a second place that knows a collision object's pose names its
        # CENTRE while an L0 body's pose names the point it stands on.
        self.scene_frame, self.bodies = planning_scene(ZONE)
        self.scene_ids = frozenset(body.object_id for body in self.bodies)
        self.apply_scene = self.create_client(
            ApplyPlanningScene,
            f"{NAMESPACE}/apply_planning_scene",
            callback_group=self.callbacks,
        )
        self.get_scene = self.create_client(
            GetPlanningScene,
            f"{NAMESPACE}/get_planning_scene",
            callback_group=self.callbacks,
        )
        # What makes the premise of the collision test provable rather than
        # asserted: move_group's own collision check, on one configuration, with
        # the contacts it found.
        self.validity = self.create_client(
            GetStateValidity,
            f"{NAMESPACE}/check_state_validity",
            callback_group=self.callbacks,
        )
        # The generated static transforms, republished here because there is no
        # `cite_bringup` in this rig to run `frame_server`. Without them the
        # collision objects arrive in a frame TF cannot resolve, and move_group
        # ACCEPTS the diff and then drops them — a scene that reports success and
        # holds nothing, which is precisely the failure this file exists to catch
        # rather than to suffer.
        self.frames = StaticTransformBroadcaster(self)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def publish_frames(self) -> None:
        messages = []
        for transform in static_transforms(ZONE):
            message = TransformStamped()
            message.header.stamp = self.get_clock().now().to_msg()
            message.header.frame_id = transform.parent
            message.child_frame_id = transform.child
            (
                message.transform.translation.x,
                message.transform.translation.y,
                message.transform.translation.z,
            ) = transform.xyz_m
            message.transform.rotation = quaternion_from_rpy(*transform.rpy_rad)
            messages.append(message)
        self.frames.sendTransform(messages)

    def wait_for_scene_frame(self, timeout: float = CALL_CEILING_S) -> bool:
        """Block until the frame the collision objects are expressed in resolves.

        A wait on a condition, not on a duration: `can_transform` returns as soon
        as the transform is in the buffer. It is the same shape as
        `wait_for_service` above, and it is here because applying an object into
        an unresolvable frame succeeds and then silently drops it.
        """
        return self.tf_buffer.can_transform(
            self.moveit["base_link"],
            self.scene_frame,
            RclpyTime(),
            timeout=Duration(seconds=timeout),
        )

    def _collision_object(self, body, operation) -> CollisionObject:
        primitive = SolidPrimitive()
        primitive.type = PRIMITIVES[body.primitive]
        primitive.dimensions = list(body.dimensions_m)

        pose = Pose()
        pose.position.x, pose.position.y, pose.position.z = body.xyz_m
        pose.orientation = quaternion_from_rpy(*body.rpy_rad)

        obj = CollisionObject()
        obj.id = body.object_id
        obj.header.frame_id = body.frame_id
        obj.primitives = [primitive]
        obj.primitive_poses = [pose]
        obj.operation = operation
        return obj

    def set_scene(self, operation) -> bool:
        """Add or remove every generated collision object; return the service verdict."""
        scene = PlanningScene()
        # A diff: move_group's scene already holds the robot's own state and its
        # allowed-collision matrix, and replacing it wholesale would discard both.
        scene.is_diff = True
        scene.world.collision_objects = [
            self._collision_object(body, operation) for body in self.bodies
        ]
        response = self.call(self.apply_scene, ApplyPlanningScene.Request(scene=scene))
        return response is not None and response.success

    def scene_object_names(self) -> set:
        request = GetPlanningScene.Request()
        request.components.components = PlanningSceneComponents.WORLD_OBJECT_NAMES
        response = self.call(self.get_scene, request)
        assert response is not None, "get_planning_scene never answered"
        return {obj.id for obj in response.scene.world.collision_objects}

    def validity_of(self, positions) -> tuple:
        """Return (valid, colliding generated-object ids) for one configuration.

        `is_diff` on the state, so the gripper joint and everything else comes
        from what move_group is monitoring; only the arm joints are being asked
        about.
        """
        request = GetStateValidity.Request()
        state = self._state(positions)
        state.is_diff = True
        request.robot_state = state
        request.group_name = self.moveit["group"]
        response = self.call(self.validity, request)
        assert response is not None, "check_state_validity never answered"
        touched = set()
        for contact in response.contacts:
            touched |= {contact.contact_body_1, contact.contact_body_2} & self.scene_ids
        return response.valid, touched

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
        for client, name in (
            (cls.harness.apply_scene, "apply_planning_scene"),
            (cls.harness.get_scene, "get_planning_scene"),
            (cls.harness.validity, "check_state_validity"),
        ):
            assert client.wait_for_service(STARTUP_CEILING_S), (
                f"move_group never advertised {name}"
            )
        # Published once the executor is running, so the latched transforms are
        # already in move_group's buffer by the time anything is applied into the
        # frame they define.
        cls.harness.publish_frames()

    #: The configuration test 9a found, so that 9b can ask for the same one
    #: without the scene. Set by 9a, and its absence is 9b's failure message
    #: rather than an error nobody can read.
    blocked_goal = None

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

    def test_4_b_the_checked_waypoint_spacing_is_the_planners_sampling_time(self) -> None:
        # The number that decides whether an obstacle is SEEN, measured rather
        # than assumed.
        #
        # Pilz's only path check is the ValidateSolution response adapter, which
        # calls `PlanningScene::isPathValid`. That iterates the trajectory's
        # WAYPOINTS and interpolates nothing between them, so the spacing of the
        # waypoints is the resolution of the collision check. The spacing is
        # Pilz's sampling time, and it is a C++ default argument —
        # `TrajectoryGenerator::generate(..., double sampling_time = 0.1)`,
        # called with three arguments — with no ROS parameter anywhere: `grep -rn
        # sampling_time` over this repository returns nothing because there is
        # nothing here to state.
        #
        # This test is what turns that from a library default nobody wrote down
        # into a number this project has measured and will be told about if it
        # changes. The consequence of the number is stated where the
        # configuration is, in the generated planning-pipelines file.
        moveit = self.harness.moveit
        response = self.harness.call(
            self.harness.plan,
            self.harness.request(moveit["default_pipeline"], moveit["default_planner_id"]),
        )
        self.assertIsNotNone(response)
        points = response.motion_plan_response.trajectory.joint_trajectory.points
        self.assertGreater(len(points), 2, "too few waypoints to measure a spacing")

        def seconds(point) -> float:
            return point.time_from_start.sec + point.time_from_start.nanosec * 1e-9

        # The last interval is whatever is left over when the motion ends between
        # two samples, so it is excluded rather than tolerated.
        steps = [seconds(b) - seconds(a) for a, b in zip(points, points[1:])][:-1]
        self.assertTrue(steps, "a trajectory with no interior interval")
        for step in steps:
            self.assertAlmostEqual(
                step,
                SAMPLING_TIME_S,
                places=6,
                msg=(
                    f"the planner sampled at {step:.6f} s, not {SAMPLING_TIME_S} s. "
                    "That is the spacing of the only collision check a Pilz path "
                    "gets, so the note about what it can and cannot see in the "
                    "generated planning-pipelines file is now wrong"
                ),
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

    # -------------------------------------------------------------------------
    # The one question the safety of ADR-0027 rests on
    # -------------------------------------------------------------------------
    #
    # Under OMPL, `ValidateSolution` was redundant: the planner searched the
    # scene and would not return a colliding path in the first place. Under Pilz
    # it is the SOLE environment-collision gate for every arm motion in this
    # cell — the generator performs one self-collision check during IK and
    # nothing else, so nothing but this adapter refuses a straight line through a
    # table.
    #
    # A component that became load-bearing and gained no assertion is the defect,
    # not the configuration. "The fallback was taken zero times across three
    # runs" is equally consistent with the mechanism working and never being
    # needed, and with the mechanism being inert; the two are indistinguishable
    # from that evidence.
    #
    # These two tests make them distinguishable. 9a loads the cell's real
    # planning scene, PROVES that a particular joint-space interpolation passes
    # through a named generated object — start valid, goal valid, an intermediate
    # configuration in contact with `conveyor_1` or whatever else it finds — and
    # asserts the request is refused with an empty trajectory. 9b removes the
    # objects and asserts the identical request then succeeds. Without 9b the
    # refusal in 9a could be coming from anywhere; with it, the scene is the only
    # thing that changed.
    #
    # They run last and in this order on purpose: 9a is the only test that leaves
    # state in move_group's world, and 9b is what takes it out again.

    #: Candidate goals for 9a — the first three joints, in the order they are
    #: tried. Joint-space rather than poses, because the claim is about a
    #: joint-space INTERPOLATION and a pose goal would put IK between the test
    #: and what it is asserting.
    #:
    #: Their shape, so the next reader does not have to reverse-engineer it: the
    #: base is swung a quarter or a half turn towards one of the belts and the
    #: shoulder and elbow are pitched out and down. That is the shape of every
    #: motion in this cell that has furniture under it, and the belts are the
    #: furniture nearest an arm — `conveyor_1` and `conveyor_2` stand either side
    #: of `arm_2`, their top faces level with its mounting plane.
    #:
    #: They were found by sweeping 225 configurations against move_group's own
    #: collision check on 2026-08-27; twelve satisfied the premise below and
    #: these ten are them, ordered so that the one blocked earliest along its
    #: path is tried first. NONE OF THAT IS TRUSTED HERE. Each candidate is
    #: admitted only if move_group says, now, that the start is clear, the goal
    #: is clear, and some point on the straight line between them is inside a
    #: named generated object. If none is, this test fails rather than passing
    #: vacuously — the layout moved, or the scene stopped being loaded, and both
    #: are worth being told about.
    BLOCKED_CANDIDATES = (
        (1.5708, 1.20, -1.05),
        (-1.5708, 1.20, -1.05),
        (1.5708, 1.20, -1.40),
        (-1.5708, 1.20, -1.40),
        (1.5708, 0.80, -1.05),
        (-1.5708, 0.80, -1.05),
        (1.1781, 1.20, -1.05),
        (-1.1781, 1.20, -1.05),
        (1.5708, 1.20, -1.80),
        (-1.5708, 1.20, -1.80),
    )

    #: Where along the straight joint-space line between start and goal the
    #: interpolation is sampled. Fractions rather than a count of waypoints,
    #: because what is being demonstrated is a property of the LINE and not of
    #: any particular planner's sampling.
    INTERPOLATION_FRACTIONS = tuple(i / 10.0 for i in range(1, 10))

    def _candidate(self, first_three) -> list:
        """One candidate as a full joint vector: its three joints, then home's."""
        goal = [float(value) for value in self.harness.home]
        goal[:3] = [float(value) for value in first_three]
        return goal

    def _blocked_between(self, start, goal):
        """Return the ids a point on the straight line between these two touches."""
        for fraction in self.INTERPOLATION_FRACTIONS:
            between = [a + (b - a) * fraction for a, b in zip(start, goal)]
            valid, touched = self.harness.validity_of(between)
            if not valid and touched:
                return fraction, touched
        return None, set()

    def test_9_a_a_ptp_path_through_the_cells_furniture_is_refused(self) -> None:
        harness = self.harness

        self.assertTrue(
            harness.wait_for_scene_frame(),
            f"{harness.scene_frame} never resolved against "
            f"{harness.moveit['base_link']}, so a collision object placed in it "
            "would be accepted and dropped rather than added",
        )
        self.assertTrue(
            harness.set_scene(CollisionObject.ADD),
            "move_group refused the generated planning scene",
        )
        # Applying is not trusted. `ApplyPlanningScene` reports success when the
        # diff was accepted, which is not the same as the objects being in the
        # world — the same distinction `cite_facility`'s loader makes, and for
        # the same reason.
        present = harness.scene_object_names()
        self.assertEqual(
            harness.scene_ids - present,
            set(),
            f"move_group accepted the diff and holds {sorted(present)}",
        )

        start = [float(value) for value in harness.home]
        valid, touched = harness.validity_of(start)
        self.assertTrue(
            valid,
            "the home configuration L0 declares is in collision with "
            f"{sorted(touched)} once the cell's own furniture is loaded. That is a "
            "finding about the model or the scene, not about this test — every "
            "plan in the running cell starts from here",
        )

        found = None
        for candidate in self.BLOCKED_CANDIDATES:
            goal = self._candidate(candidate)
            goal_valid, _ = harness.validity_of(goal)
            if not goal_valid:
                continue
            fraction, blocked_by = self._blocked_between(start, goal)
            if fraction is not None:
                found = (goal, fraction, blocked_by)
                break

        self.assertIsNotNone(
            found,
            "no candidate goal has a clear start, a clear goal and a blocked "
            "straight line between them. The premise of this test is gone, not its "
            "conclusion: either the layout moved or the scene stopped being loaded, "
            "and both are worth knowing",
        )
        goal, fraction, blocked_by = found
        type(self).blocked_goal = goal

        response = harness.call(
            harness.plan,
            harness.request(
                harness.moveit["default_pipeline"], harness.moveit["default_planner_id"], goal
            ),
        )
        self.assertIsNotNone(response, "plan_kinematic_path never answered")
        result = response.motion_plan_response
        self.assertNotEqual(
            result.error_code.val,
            MoveItErrorCodes.SUCCESS,
            f"the default planner returned a path whose interpolation is inside "
            f"{sorted(blocked_by)} at {fraction:.0%} of the way along it. Nothing "
            "else in this configuration checks a generated path against the scene, "
            "so this is an arm driven through the cell's furniture",
        )
        # The code, pinned — and what it is pinned to is the point. MoveIt's
        # ValidateSolution reports a plain `FAILURE`, not `INVALID_MOTION_PLAN`
        # and not a collision-specific code, so a CALLER CANNOT TELL from the
        # response that the refusal was a collision. It cannot tell it from an
        # unreachable goal or from a start state out of bounds either. That is
        # why the pair of tests is the evidence and a single refusal is not, and
        # it is why the skill server's fallback treats every refusal alike.
        self.assertEqual(
            result.error_code.val,
            MoveItErrorCodes.FAILURE,
            f"the refusal came back as {result.error_code.val}, which is not the "
            "generic FAILURE this pipeline reported when this test was written. If "
            "MoveIt has started distinguishing a collision refusal, the skill "
            "server can act on it and the comment here is out of date",
        )
        # And what a refusal LOOKS like here, because it is not what test 7's
        # refusal looks like and a caller that told them apart by the wrong
        # feature would execute this one. LIN is refused during generation and
        # comes back empty; this path is generated successfully and then marked
        # invalid, so the trajectory that failed IS ATTACHED to the response.
        # Only the error code says it must not be run.
        self.assertGreater(
            len(result.trajectory.joint_trajectory.points),
            0,
            "a path rejected after generation came back without the trajectory it "
            "rejected; if MoveIt now clears it, the warning in this test about "
            "callers that branch on the trajectory is out of date",
        )

    def test_9_b_the_same_request_plans_once_the_furniture_is_gone(self) -> None:
        # The complement, and it is what makes 9a evidence rather than
        # decoration. A refusal on its own could come from an unreachable goal, a
        # joint limit, a start state out of bounds — from anywhere. Removing the
        # objects and asking for the identical plan leaves the scene as the only
        # difference between the two answers.
        harness = self.harness
        self.assertIsNotNone(
            self.blocked_goal,
            "test 9a did not record a goal, so this test has nothing to ask for "
            "and proves nothing",
        )

        self.assertTrue(
            harness.set_scene(CollisionObject.REMOVE),
            "move_group refused to remove the generated planning scene",
        )
        self.assertEqual(
            harness.scene_object_names() & harness.scene_ids,
            set(),
            "the objects are still in move_group's world, so the request below "
            "would be asked under the same conditions as 9a",
        )

        response = harness.call(
            harness.plan,
            harness.request(
                harness.moveit["default_pipeline"],
                harness.moveit["default_planner_id"],
                self.blocked_goal,
            ),
        )
        self.assertIsNotNone(response, "plan_kinematic_path never answered")
        result = response.motion_plan_response
        self.assertEqual(
            result.error_code.val,
            MoveItErrorCodes.SUCCESS,
            "the identical request was refused with an EMPTY world, so the refusal "
            f"in 9a was not the planning scene. Error code {result.error_code.val}",
        )
        self.assertGreater(
            len(result.trajectory.joint_trajectory.points),
            1,
            "the planner reported success and returned no motion",
        )
