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

"""ADR-0040: a genuine trajectory abort, driven into L3 on demand.

ADR-0037's correction to its own decision 8 records the gap this file closes:

    no fixture in this repository drives a genuine abort into L3 on demand.

`test_trajectory_constraints_launch.py` cannot, for two independent reasons. It
launches no `move_group` and no skill server, so nothing it produces reaches
`cite_skills::classify_execution_failure` at all; and it injects mistracking with
`mock_components/GenericSystem`'s `disable_commands`, which stops the command
propagating from the first control cycle, so the arm never leaves the
trajectory's first point and classifies AT_START — the one answer that is NOT
`MOTION_INTERRUPTED`.

This rig runs the whole path: a real `ros2_control_node` loading the generated
controller configuration unmodified, a real `move_group`, and the real
`cite_skills` skill server. The abort therefore travels the three funnels ADR-0037
documents — `finishControllerExecution`, `ExecutionStatus`, and the capability's
collapse into `CONTROL_FAILED` — and arrives at the classifier stripped of the
controller's error code, exactly as it does in the cell.

## What makes the abort happen, and why it is a STATE and not a wait

The hardware is `cite_test_hardware/JointStopSystem` (ADR-0040): `GenericSystem`
with a pair of hard stops on one named joint. The arm tracks normally until that
joint reaches its stop, and then stands there while the trajectory advances
without it. Nothing here waits for a duration and nothing engages on a timer — a
slower machine engages the stop at the same joint angle (P4).

## The discrimination is in the GOAL, not in a second rig

One rig, one hardware configuration, two motions. A motion that stays clear of the
stops must succeed; a motion that drives through them by more than the generated
path tolerance must abort and classify `MOTION_INTERRUPTED`. The two cases differ
in nothing but the goal, which is a stronger statement than two rigs side by side
could make: a rig that manufactured aborts would fail the first test, and a rig
whose stop never engaged would fail the second.

## Every threshold is read, never written here

The stop is placed and the abort motion sized from the arm's OWN generated
`constraints:` block (ADR-0036) and from the generated bring-up plan. If those
values change in L0, this file follows them (P1). What it states of its own are
two multipliers, and it states why each is what it is.

## What is real here and what is not, stated as plainly as the rig it replaces

The plant is a **perfect follower**. Mock hardware mirrors a command to its state
with no dynamics, so the velocity this rig reports is the rate of change of the
controller's own command stream. That is enough to answer "has the commanded
motion stopped when `execute()` returns?", which is what ADR-0037's decision 3
argues from. It is NOT enough to answer "has a real arm stopped coasting?", and no
reading of this file's output may cross that line. Under `gz_ros2_control` the
position command interface is a first-order lag rather than a servo (ADR-0036's
correction), and only a scenario measures that.

The specific risk ADR-0037 names — an abort very early in the path where a
DECELERATING arm is still within tolerance of the start and is classified as never
having moved — is therefore **not** measured here and cannot be. A plant with no
deceleration cannot produce it.
"""

from __future__ import annotations

from collections import deque
import importlib.util
import math
from pathlib import Path
import subprocess
import threading
import unittest
import xml.etree.ElementTree as ElementTree

from cite_bringup import plan as bringup_plan
from cite_interfaces.action import MoveTo
from cite_interfaces.msg import ResultCode
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PoseStamped
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import launch_testing
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node as RclpyNode
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState
from tf2_ros import Buffer, TransformListener
import yaml

ZONE = 'cell_a'
ARM = 'arm_1'

#: The hardware plugin every generated description declares, and the two this rig
#: substitutes for it. Asserted rather than assumed when the swap is made: if the
#: L0 backend ever changes, this rig must fail loudly rather than quietly stop
#: substituting anything.
PRODUCTION_PLUGIN = 'gz_ros2_control/GazeboSimSystem'
FIXTURE_PLUGIN = 'cite_test_hardware/JointStopSystem'
#: Everything that is not the arm — here, the gripper system — gets the vendor's
#: own mock, unmodified. Only the component under test is replaced.
MOCK_PLUGIN = 'mock_components/GenericSystem'

STARTUP_CEILING_S = 180.0
GOAL_CEILING_S = 120.0

#: How far from its start the stopped joint is allowed to travel, as a multiple of
#: the arm's own goal tolerance. Ten, so that the arm standing at the stop is an
#: order of magnitude outside the band `classify_motion_end` calls "at the start" —
#: a stop placed just outside it would leave the classification riding on the
#: boundary this test exists to stay away from.
STOP_IN_GOAL_TOLERANCES = 10.0

#: How far past the stop the abort motion commands the joint, as a multiple of the
#: arm's own path tolerance. One and a half, so the following error passes the
#: threshold well inside the motion rather than at its last waypoint — and so the
#: arm ends up far outside the goal tolerance of the target as well, which is what
#: makes the answer PART_WAY rather than either endpoint.
OVERSHOOT_IN_PATH_TOLERANCES = 1.5

#: How far the abort motion also lifts the tool, in metres, on top of the rotation.
#:
#: WITHOUT IT THE MEASUREMENT IN TEST 4 ASKS ITS QUESTION OF AN ARM THAT WAS
#: ALREADY STILL. A pure rotation about the base axis moves the stopped joint and
#: nothing else, so at the instant the path tolerance fires every other joint has
#: been stationary for seconds and a residual velocity of zero says nothing about
#: what a controller-installed hold does to a joint that was moving. The lift puts
#: the four unstopped joints in motion for the whole trajectory, so the residual is
#: measured on joints the abort actually had to stop.
#:
#: Small, because the rotation is what produces the abort and this only has to be
#: enough to keep the other joints busy: a lift large enough to dominate the
#: trajectory's duration would change which joint the timing belongs to.
LIFT_M = 0.10

#: Below this, in rad/s, a sampled joint velocity is read as "not moving". It is a
#: reporting threshold for a measurement, not a tolerance anything is judged
#: against: the numbers this rig produces are printed in full.
STILL_RAD_S = 1e-6

#: What the velocity channel must exceed during a healthy motion for the residual
#: measurement below it to mean anything. A measurement instrument that reads zero
#: is indistinguishable from one that reads nothing, and on a position-only mock
#: the velocity state is never written at all — so this is the positive control,
#: not a performance assertion.
MOVING_RAD_S = 0.05


def _production_launch():
    """Load `simulation.launch.py` as a module, for its parameter builders.

    The rig gives `move_group` and the skill server the parameters the PRODUCTION
    launch file builds for them, rather than a second set assembled here. A rig
    configured differently from the cell can pass while the cell fails, and the
    parameter half is where that would happen silently — a kinematics file under
    the wrong prefix, a planning-pipeline document flattened the wrong way.

    Two keys are overridden afterwards and only two: the robot description, which
    is the whole point of the fixture, and `use_sim_time`, because this rig runs
    no simulator and therefore has no `/clock`. Everything else is production's.
    """
    path = Path(__file__).resolve().parents[1] / 'launch' / 'simulation.launch.py'
    spec = importlib.util.spec_from_file_location('cite_bringup_simulation_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SIM = _production_launch()

PLAN = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
MANAGER = next(entry for entry in PLAN.controller_managers if entry.asset == ARM)
NAMESPACE = MANAGER.node.rsplit('/', 1)[0]
#: The plan carries this one as a `package://` URI rather than as a path, because
#: under Gazebo it is read by the simulator's own plugin. Resolved with the plan
#: reader's own resolver, so the file this rig loads is the file the cell loads.
CONTROLLER_CONFIG = bringup_plan.resolve_uri(MANAGER.parameters)


def _controller_document():
    """Read the generated controller configuration for this arm as a dictionary."""
    return yaml.safe_load(CONTROLLER_CONFIG.read_text())


def _trajectory_controller_parameters():
    key = f'{NAMESPACE}/{ARM}_joint_trajectory_controller'
    return _controller_document()[key]['ros__parameters']


TRAJECTORY_JOINTS = list(_trajectory_controller_parameters()['joints'])
CONSTRAINTS = _trajectory_controller_parameters()['constraints']

#: The joint the stops are placed on: the FIRST joint the trajectory controller
#: names, which on this arm is the base rotation. It is chosen from the generated
#: list rather than spelled out, and the base is the right one of them for a
#: reason the rig depends on — the home configuration in the L0 model leaves it at
#: zero, so the control motion below moves four other joints substantially and
#: still comes nowhere near the stops.
STOP_JOINT = TRAJECTORY_JOINTS[0]
GOAL_TOLERANCE_RAD = float(CONSTRAINTS[STOP_JOINT]['goal'])
PATH_TOLERANCE_RAD = float(CONSTRAINTS[STOP_JOINT]['trajectory'])

STOP_RAD = STOP_IN_GOAL_TOLERANCES * GOAL_TOLERANCE_RAD
#: How far the abort motion rotates the base. Two-sided stops mean the sign does
#: not matter: an IK solver that returns the equivalent branch on the other side
#: of zero drives the joint into the other stop and accumulates MORE error, not
#: less.
ROTATION_RAD = STOP_RAD + OVERSHOOT_IN_PATH_TOLERANCES * PATH_TOLERANCE_RAD


def _rig_description() -> str:
    """Build the rig's description: the GENERATED one, altered in two asserted ways.

    Expanded with `xacro` exactly as the production launch does, then: the arm's
    `<ros2_control>` hardware plugin is replaced by the fixture and given its
    stops, and every other component gets the vendor's plain mock. Link geometry,
    joint limits, interface declarations and joint names are the generated file's,
    untouched — so the controller this rig loads claims the same interfaces it
    claims in the cell.

    The `<gazebo>` elements are dropped. They carry the simulator's own system
    plugin and a path to the controller configuration that a plain
    `ros2_control_node` has no use for; leaving them in would be leaving a second,
    contradictory statement about who runs the controllers.
    """
    expanded = subprocess.run(
        ['xacro', str(MANAGER.description)],
        capture_output=True, text=True, check=True,
    ).stdout
    robot = ElementTree.fromstring(expanded)

    for gazebo in robot.findall('gazebo'):
        robot.remove(gazebo)

    blocks = robot.findall('ros2_control')
    assert blocks, f'{MANAGER.description} expanded to no <ros2_control> block'

    stopped = 0
    for block in blocks:
        hardware = block.find('hardware')
        plugin = hardware.find('plugin')
        assert plugin.text.strip() == PRODUCTION_PLUGIN, (
            f'{block.get("name")} declares {plugin.text.strip()!r}, not '
            f'{PRODUCTION_PLUGIN!r}. The L0 backend has changed and this rig is no '
            f'longer substituting what it thinks it is.'
        )
        names = {joint.get('name') for joint in block.findall('joint')}
        if STOP_JOINT not in names:
            plugin.text = MOCK_PLUGIN
            continue
        plugin.text = FIXTURE_PLUGIN
        for key, value in (
            ('stop_joint', STOP_JOINT),
            ('stop_lower_rad', repr(-STOP_RAD)),
            ('stop_upper_rad', repr(STOP_RAD)),
        ):
            parameter = ElementTree.SubElement(hardware, 'param')
            parameter.set('name', key)
            parameter.text = value
        stopped += 1

    assert stopped == 1, (
        f'expected exactly one <ros2_control> block to declare {STOP_JOINT}, found {stopped}'
    )
    return ElementTree.tostring(robot, encoding='unicode')


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    """One arm, with the fixture in place of the simulator's hardware."""
    description = _rig_description()
    semantic = ParameterValue(
        Command(['xacro ', str(MANAGER.moveit.srdf)]), value_type=str
    )
    moveit = MANAGER.moveit

    # Ordered by the stage the generated plan declares, so the state broadcaster
    # is active before anything claims a command interface — the same order
    # production spawns them in, read from the same place.
    controllers = [name for _, names in MANAGER.stages() for name in names]

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='description_publisher',
            namespace=NAMESPACE,
            parameters=[{'robot_description': description, 'use_sim_time': False}],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='log',
        ),
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            name='controller_manager',
            namespace=NAMESPACE,
            parameters=[
                # THE GENERATED FILE, UNMODIFIED. The tolerances this rig produces
                # an abort against are the cell's own (ADR-0036).
                str(CONTROLLER_CONFIG),
                # The generated file says `use_sim_time: true` because the cell it
                # configures runs under Gazebo. There is no `/clock` here and a
                # manager waiting for one never runs a control cycle. The override
                # is the rig's, it is applied to every node in the rig rather than
                # to some of them, and it changes nothing under test: the
                # classification compares joint positions against a trajectory's
                # endpoints and derives nothing from a clock.
                {'use_sim_time': False},
                {'robot_description': description},
            ],
            output='screen',
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            name='spawn_controllers',
            arguments=[
                *controllers,
                '--controller-manager', MANAGER.node,
                '--controller-manager-timeout', str(STARTUP_CEILING_S),
            ],
            output='screen',
        ),
        Node(
            package='moveit_ros_move_group',
            executable='move_group',
            name='move_group',
            namespace=NAMESPACE,
            parameters=[
                {
                    'robot_description': description,
                    'robot_description_semantic': semantic,
                    'publish_robot_description_semantic': True,
                },
                SIM._yaml_parameters(
                    moveit.kinematics, prefix='robot_description_kinematics'),
                SIM._planning_limits(moveit),
                SIM._yaml_parameters(moveit.planning_pipelines),
                SIM._yaml_parameters(moveit.controllers),
                {
                    'publish_planning_scene': True,
                    'publish_state_updates': True,
                    'use_sim_time': False,
                },
            ],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='screen',
        ),
        Node(
            package='cite_skills',
            executable='skill_server',
            name='skill_server',
            namespace=NAMESPACE,
            parameters=[
                {
                    'robot_description': description,
                    'robot_description_semantic': semantic,
                },
                SIM._yaml_parameters(
                    moveit.kinematics, prefix='robot_description_kinematics'),
                SIM._planning_limits(moveit),
                # Every skill parameter the CELL gives this server, built by the
                # production launch file's own function — including the
                # `arm_goal_tolerance_rad` the classification compares against,
                # which is the number this whole test is about.
                SIM._skill_parameters(PLAN, MANAGER),
                {'use_sim_time': False},
            ],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='screen',
        ),
        launch_testing.actions.ReadyToTest(),
    ])


class _Samples:
    """A bounded record of `/joint_states`, with the time each one arrived.

    The arrival time is the test's own clock rather than the message stamp, and
    that is deliberate: what is being measured is what the caller could have known
    when `execute()` returned, and the caller knows when a message reached it.
    """

    def __init__(self, node, joints):
        self._node = node
        self._joints = list(joints)
        self.samples = deque(maxlen=4000)
        self._lock = threading.Lock()
        # Declared rather than defaulted (CLAUDE.md §10). `joint_state_broadcaster`
        # publishes on the system default profile — reliable, volatile — so this
        # matches it; the depth is the rig's, because a measurement that dropped
        # the sample next to the one it wanted would report the wrong answer
        # rather than no answer.
        node.create_subscription(
            JointState,
            f'{NAMESPACE}/joint_states',
            self._record,
            QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=200,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
            ),
        )

    def _record(self, message):
        received = self._node.get_clock().now()
        index = {name: position for position, name in enumerate(message.name)}
        if not all(joint in index for joint in self._joints):
            return
        entry = {
            'received': received,
            'position': {
                joint: message.position[index[joint]] for joint in self._joints},
            'velocity': {
                joint: (message.velocity[index[joint]] if message.velocity else math.nan)
                for joint in self._joints},
        }
        with self._lock:
            self.samples.append(entry)

    def snapshot(self):
        with self._lock:
            return list(self.samples)

    def latest_at(self, when):
        """Return the last sample that had arrived by `when`, or None."""
        for entry in reversed(self.snapshot()):
            if entry['received'] <= when:
                return entry
        return None

    @staticmethod
    def fastest(entry):
        """Return the largest absolute joint velocity in one sample."""
        return max(abs(value) for value in entry['velocity'].values())


def _quaternion_about_z(angle):
    return (0.0, 0.0, math.sin(angle / 2.0), math.cos(angle / 2.0))


def _multiply(left, right):
    x1, y1, z1, w1 = left
    x2, y2, z2, w2 = right
    return (
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    )


@launch_testing.markers.keep_alive
class TestAnAbortReachesTheClassifier(unittest.TestCase):
    """One arm, two motions, in this order.

    THE ORDER IS LOAD-BEARING and is why the methods are numbered. The arm carries
    its state from one test to the next: the first motion puts it at the home
    configuration, which is where the second one's geometry is computed from, and
    the second leaves it standing against a hard stop with a failed goal behind it.
    Run in any other order these assert different things.
    """

    control_samples = None
    abort_samples = None
    abort_result = None
    abort_result_at = None
    start_positions = None

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode('abort_classification_test')
        cls.buffer = Buffer()
        cls.listener = TransformListener(cls.buffer, cls.node)
        cls.recorder = _Samples(cls.node, TRAJECTORY_JOINTS)
        cls.client = ActionClient(cls.node, MoveTo, MANAGER.skills.move_to)

        # THE RIG IS READY WHEN THREE THINGS EXIST, and each of them is an event
        # rather than an elapsed time (P4). `ReadyToTest` fires as soon as the
        # processes are spawned, which is well before the controller manager has
        # activated anything: a goal sent then reaches move_group, finds no
        # `follow_joint_trajectory` action server, and comes back CONTROL_FAILED
        # with the arm still at the start — a perfect imitation of the abort this
        # rig is supposed to produce, arriving from a rig that never produced one.
        # That is the single most dangerous way this file could pass.
        trajectory = ActionClient(
            cls.node, FollowJointTrajectory, MANAGER.trajectory_action)
        assert trajectory.wait_for_server(timeout_sec=STARTUP_CEILING_S), (
            f'{MANAGER.trajectory_action} never appeared: the trajectory controller '
            f'did not activate, so nothing in this rig could have executed anything.'
        )
        deadline = cls.node.get_clock().now() + Duration(seconds=STARTUP_CEILING_S)
        while not cls.recorder.snapshot() and cls.node.get_clock().now() < deadline:
            rclpy.spin_once(cls.node, timeout_sec=0.1)
        assert cls.recorder.snapshot(), (
            f'no joint state arrived on {NAMESPACE}/joint_states; the classification '
            f'reads the arm through this topic and would answer UNKNOWN without it.'
        )

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin(self, future, ceiling_s):
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=ceiling_s)
        return future.result()

    def _move(self, goal):
        """Send one `MoveTo` and return (result, the time it arrived)."""
        self.assertTrue(
            self.client.wait_for_server(timeout_sec=STARTUP_CEILING_S),
            f'{MANAGER.skills.move_to} never appeared — the skill server did not start',
        )
        handle = self._spin(self.client.send_goal_async(goal), GOAL_CEILING_S)
        self.assertIsNotNone(handle, 'the skill server never answered the goal request')
        self.assertTrue(handle.accepted, 'the skill server rejected the goal')
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        arrived = self.node.get_clock().now()
        self.assertIsNotNone(
            outcome,
            f'no MoveTo result within {GOAL_CEILING_S}s. A goal that neither succeeds '
            f'nor fails is the goal_time hang ADR-0036 describes, one layer up.',
        )
        return outcome.result, arrived

    def _tool_pose(self):
        """Look up the tool's pose in the arm's own base frame, from TF.

        Both frame names come from the generated bring-up plan. Reading the pose
        rather than computing it is what lets the abort motion be defined as "the
        pose you are at, rotated about the base axis" — which has an exact IK
        solution by construction, because it is the forward kinematics of the
        configuration the arm is already in with one joint changed.
        """
        deadline = self.node.get_clock().now() + Duration(seconds=STARTUP_CEILING_S)
        while self.node.get_clock().now() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if self.buffer.can_transform(
                MANAGER.moveit.base_link, MANAGER.moveit.tip_link, rclpy.time.Time()
            ):
                return self.buffer.lookup_transform(
                    MANAGER.moveit.base_link, MANAGER.moveit.tip_link, rclpy.time.Time()
                )
        self.fail(
            f'{MANAGER.moveit.base_link} -> {MANAGER.moveit.tip_link} never appeared on TF'
        )

    def test_1_a_motion_clear_of_the_stops_succeeds(self):
        """The rig does not manufacture aborts.

        The home configuration comes from L0 and leaves the stopped joint at zero
        while moving four others — one of them by more than the path tolerance —
        so this is a real motion of a real arm past a real detector, and it must
        come back SUCCESS. A fixture that aborted everything would fail here, and
        every later assertion would be worthless without it.
        """
        goal = MoveTo.Goal()
        goal.named_configuration = 'home'
        before = len(self.recorder.snapshot())
        result, _ = self._move(goal)
        self.assertEqual(
            result.result.code, ResultCode.SUCCESS,
            f'a motion that never reaches the stops was reported as '
            f'{result.result.code}: {result.result.detail!r}',
        )
        type(self).control_samples = self.recorder.snapshot()[before:]
        stopped = self.recorder.snapshot()[-1]['position'][STOP_JOINT]
        self.assertLess(
            abs(stopped), STOP_RAD,
            f'{STOP_JOINT} reached {stopped} rad, which is at its stop at '
            f'{STOP_RAD} rad. The control motion is not clear of the fixture, so it '
            f'is not a control.',
        )

    def test_2_the_velocity_channel_reports_motion(self):
        """The positive control for the measurement in test 4.

        On a position-only command interface `GenericSystem` never writes the
        velocity state at all, so an unmodified mock reports exactly zero for an
        arm travelling at any speed. This asserts the fixture's differentiated
        velocity is a function of motion before anything is concluded from it
        being small.
        """
        self.assertIsNotNone(
            self.control_samples, 'test 1 did not run; nothing was recorded')
        fastest = max(
            (self.recorder.fastest(entry) for entry in self.control_samples), default=0.0)
        print(f'\n[ADR-0040] peak sampled joint speed during the healthy motion: '
              f'{fastest:.6f} rad/s')
        self.assertGreater(
            fastest, MOVING_RAD_S,
            'the velocity channel reported nothing above the noise floor during a '
            'motion that demonstrably happened, so it measures nothing and test 4 '
            'would be reporting an artefact.',
        )

    def test_3_a_motion_through_the_stops_is_interrupted(self):
        """The case the classifier exists for, produced on demand.

        The goal is the tool's current pose rotated about the base axis by more
        than the stop plus the path tolerance. The arm sets off, the base joint
        reaches its stop, the trajectory advances without it, and the controller
        aborts on the path tolerance mid-motion. MoveIt collapses that into
        CONTROL_FAILED carrying no reason, and L3 answers by asking the arm where
        it is.
        """
        transform = self._tool_pose()
        rotation = _quaternion_about_z(ROTATION_RAD)
        translation = transform.transform.translation
        orientation = transform.transform.rotation

        target = PoseStamped()
        target.header.frame_id = MANAGER.moveit.base_link
        target.pose.position.x = (
            translation.x * math.cos(ROTATION_RAD) - translation.y * math.sin(ROTATION_RAD))
        target.pose.position.y = (
            translation.x * math.sin(ROTATION_RAD) + translation.y * math.cos(ROTATION_RAD))
        target.pose.position.z = translation.z + LIFT_M
        turned = _multiply(
            rotation, (orientation.x, orientation.y, orientation.z, orientation.w))
        target.pose.orientation.x, target.pose.orientation.y = turned[0], turned[1]
        target.pose.orientation.z, target.pose.orientation.w = turned[2], turned[3]

        goal = MoveTo.Goal()
        goal.target = target

        type(self).start_positions = self.recorder.snapshot()[-1]['position']
        before = len(self.recorder.snapshot())
        result, arrived = self._move(goal)
        type(self).abort_samples = self.recorder.snapshot()[before:]
        type(self).abort_result = result
        type(self).abort_result_at = arrived

        detail = result.result.detail
        self.assertEqual(
            result.result.code, ResultCode.MOTION_INTERRUPTED,
            f'an arm held part-way along its trajectory was classified '
            f'{result.result.code}: {detail!r}',
        )
        # MOTION_INTERRUPTED is also what the classifier answers when it CANNOT
        # READ the arm at all, and the two are opposite claims. Without this the
        # rig would pass on a joint state that never arrived — reporting an
        # interruption it did not observe, which is exactly the failure P6 says is
        # worse than having no rig.
        self.assertIn(
            'part-way', detail,
            f'the code is right and the reason is not: {detail!r}. This is the '
            f'UNKNOWN branch, not the PART_WAY one.',
        )

        # And the fixture is what caused it: the stopped joint is standing at the
        # stop the description declared, outside the goal tolerance of both ends
        # of the trajectory it was given.
        held = self.recorder.snapshot()[-1]['position'][STOP_JOINT]
        self.assertAlmostEqual(
            abs(held), STOP_RAD, places=6,
            msg=f'{STOP_JOINT} came to rest at {held} rad, not at its declared stop '
                f'at +/-{STOP_RAD} rad. Whatever aborted this motion, the fixture '
                f'did not.',
        )
        self.assertGreater(
            abs(held - self.start_positions[STOP_JOINT]), GOAL_TOLERANCE_RAD,
            'the arm is within its goal tolerance of where it started, which is '
            'AT_START and not an interruption.',
        )

        # And the motion was not a pure rotation of the stopped joint. This is
        # test 4's precondition, asserted here where the evidence is: a residual
        # velocity of zero means nothing if every unstopped joint had been
        # stationary throughout, because then the abort had nothing to stop.
        travelled = {
            joint: abs(self.recorder.snapshot()[-1]['position'][joint]
                       - self.start_positions[joint])
            for joint in TRAJECTORY_JOINTS if joint != STOP_JOINT
        }
        self.assertTrue(
            any(distance > GOAL_TOLERANCE_RAD for distance in travelled.values()),
            f'only {STOP_JOINT} moved: {travelled}. The abort had no moving joint to '
            f'stop, so the residual velocity test 4 reports would be an artefact of '
            f'an arm that was already still.',
        )

    def test_4_the_joint_state_when_execute_returned(self):
        """ADR-0037's outstanding measurement, as a number rather than an argument.

        Decision 3 argues that the joint state is static by the time `execute()`
        returns, and records that this is reasoned rather than measured. This
        samples it.

        WHAT IS SAMPLED, precisely, because the difference matters. The instant
        used is when the MoveTo RESULT reached this test, which is strictly after
        `execute()` returned: between them sit `getCurrentState`, the
        classification itself, and the action result's trip over the wire. So this
        is an upper bound on the elapsed time and, for a plant that decelerates, a
        LOWER bound on how still the arm was. On this rig the plant does not
        decelerate at all — see the module docstring.
        """
        self.assertIsNotNone(self.abort_result, 'test 3 did not run')
        entry = self.recorder.latest_at(self.abort_result_at)
        self.assertIsNotNone(
            entry, 'no joint state had arrived when the result did; nothing to measure')

        speeds = {joint: entry['velocity'][joint] for joint in TRAJECTORY_JOINTS}
        fastest = self.recorder.fastest(entry)
        print('\n[ADR-0040] joint state at the moment the MoveTo result arrived:')
        for joint in TRAJECTORY_JOINTS:
            print(f'  {joint}: {entry["position"][joint]:+.9f} rad, '
                  f'{speeds[joint]:+.9f} rad/s')
        print(f'[ADR-0040] largest absolute joint speed: {fastest:.9f} rad/s '
              f'(reporting floor {STILL_RAD_S} rad/s)')

        before = [
            sample for sample in self.abort_samples
            if sample['received'] <= self.abort_result_at
        ]
        moving = [
            sample for sample in before if self.recorder.fastest(sample) > STILL_RAD_S
        ]
        intervals = [
            (later['received'] - earlier['received']).nanoseconds / 1e6
            for earlier, later in zip(before, before[1:])
        ]
        if intervals:
            intervals.sort()
            print(f'[ADR-0040] {len(before)} joint states during the aborted motion, '
                  f'median interval {intervals[len(intervals) // 2]:.2f} ms')
        if moving:
            gap = (self.abort_result_at - moving[-1]['received']).nanoseconds / 1e6
            still = len(before) - before.index(moving[-1]) - 1
            print(f'[ADR-0040] last moving sample was {gap:.1f} ms before the result, '
                  f'and {still} sample(s) reported no motion after it')
        else:
            print('[ADR-0040] no sample during the aborted motion reported any motion, '
                  'which means the rig measured nothing')

        self.assertLessEqual(
            fastest, STILL_RAD_S,
            f'the arm was still moving at {fastest} rad/s when the result arrived. '
            f'That is a FINDING, not a flake: ADR-0037 decision 3 classifies from a '
            f'position sampled at this instant, and a moving quantity sampled once is '
            f'not the world state the classification claims to read.',
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    """What the rig's processes did on the way out.

    `move_group` IS DELIBERATELY NOT ASSERTED ON, and the reason is copied from
    `cite_skills/test/test_planning_pipeline.py` rather than invented here:
    `move_group` exiting -11 during teardown is a known unresolved failure
    elsewhere in this repository, and the standing instruction on the exemption
    that covers it is to delete it rather than widen it — so this file adds no
    second place that tolerates it. `cite_skills/test/test_skill_contract.py`,
    which also launches `move_group`, resolves it the same way: it filters
    `proc_info` down to the process it is answerable for.

    What is asserted is everything this rig is answerable for, and `skill_server`
    is the one that matters: it is the process the classification runs in, and its
    own -11 sits OUTSIDE the exemption above and must stay outside it.
    """

    #: Excluded above. Named here so that adding a process to this rig does not
    #: silently inherit the exclusion by matching a prefix nobody re-read.
    UNASSERTED = ('move_group',)

    def test_processes_exit_cleanly(self, proc_info):
        # A spawner exits 0 once its controllers are active; everything else is
        # stopped by the harness, which is the SIGINT code.
        allowed = [0, launch_testing.asserts.EXIT_SIGINT, -15]
        checked = 0
        for info in proc_info:
            name = str(info.process_name)
            if name.startswith(self.UNASSERTED):
                continue
            checked += 1
            self.assertIn(
                info.returncode, allowed,
                f'{name} exited with {info.returncode}',
            )
        # A filter that matched everything would make this test silently vacuous,
        # which is the failure mode the filter itself introduces.
        self.assertGreater(
            checked, 0, 'every process was excluded; this assertion checked nothing')
