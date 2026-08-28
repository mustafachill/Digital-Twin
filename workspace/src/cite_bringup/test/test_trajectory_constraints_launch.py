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

"""ADR-0036: that a real controller READS the generated `constraints:` block.

The generator tests in `tools/tests/test_trajectory_constraints.py` prove the
block is emitted, complete and per-instance. They cannot prove the thing that
matters most about it: that `joint_trajectory_controller` recognises these
parameter names and acts on these numbers. A misspelled key — `goal_time_tolerance`
for `goal_time`, or a per-joint block under a name the controller does not own —
generates cleanly, loads cleanly, and silently restores the exact defect ADR-0036
removes. Nothing but a running controller can tell the two apart.

**The configuration under test is the generated file itself**, read from the
installed `cite_generated` share directory rather than restated here (P1). If the
values in L0 change, this test follows them: it asserts the thresholds it read,
not thresholds of its own.

**What is real here and what is not.** The hardware is
`mock_components/GenericSystem`, so the following error a healthy trajectory
produces here is identically zero — mock hardware mirrors a command straight to
its state interface. That is the honest limit of this rig and it is worth stating
plainly: *this test does not and cannot measure the following error the simulated
cell actually produces.* Only Gazebo does that, and only a scenario runs Gazebo.
What this rig gives instead is threshold discrimination against the generated
numbers, which mock hardware does exactly and deterministically:

  * a trajectory tracked perfectly must SUCCEED — the detector does not cry wolf;
  * a trajectory whose error exceeds the goal tolerance but stays under the path
    tolerance must fail as GOAL_TOLERANCE_VIOLATED, after `goal_time`;
  * a trajectory whose error exceeds the path tolerance must fail as
    PATH_TOLERANCE_VIOLATED, mid-motion.

The third case is the auditor's originating case — a joint held back while the
trajectory advances — and the second and third together are what show the two
thresholds are read as two distinct numbers rather than as one.

Mistracking is injected with the mock hardware's own `disable_commands`
parameter, which makes `read()` return before propagating any command, so the
joint state stays where it started while the trajectory advances. The amplitude
of the commanded motion is then exactly the error, which is what lets one
mechanism straddle both thresholds.

Two rigs run side by side under the namespaces of two different arms, each with
its own generated configuration: `arm_1` tracks, `arm_2` is stuck. Using two real
arms' files rather than one file twice also means a per-arm generation bug shows
up here as well as in the generator suite.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from ament_index_python.packages import get_package_share_directory
from control_msgs.action import FollowJointTrajectory
from control_msgs.msg import JointTrajectoryControllerState
from launch import LaunchDescription
from launch_ros.actions import Node
import launch_testing
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node as RclpyNode
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from trajectory_msgs.msg import JointTrajectoryPoint
import yaml

ZONE = "cell_a"

#: The arm whose rig tracks its trajectory, and the arm whose rig does not.
TRACKING_ARM = "arm_1"
STUCK_ARM = "arm_2"

GENERATED = Path(get_package_share_directory("cite_generated"))

STARTUP_CEILING_S = 90.0
GOAL_CEILING_S = 60.0

#: Seconds the commanded trajectory takes. Long enough that the path check gets
#: many control cycles in which to notice a violation, short enough to keep the
#: suite quick. Nothing is sequenced by it — every wait below is on an action
#: result, never on a duration (P4).
MOVE_DURATION_S = 2.0

#: `JointTrajectoryController` publishes `~/controller_state` with
#: `rclcpp::SystemDefaultsQoS()` — KEEP_LAST depth 10, RELIABLE, VOLATILE.
#: Declared here rather than defaulted, because an incompatible profile
#: subscribes silently and delivers nothing (CLAUDE.md §10), and this
#: subscription is the gate the whole class waits on: getting it wrong would
#: turn every run into a startup timeout rather than a visible mismatch.
CONTROLLER_STATE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.VOLATILE,
)


def _config_path(arm):
    return GENERATED / "control" / f"{ZONE}_{arm}_controllers.yaml"


def _controller_parameters(arm):
    """Return the generated `ros__parameters` of one arm's trajectory controller."""
    document = yaml.safe_load(_config_path(arm).read_text())
    key = f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller"
    return document[key]["ros__parameters"]


def _constraints(arm):
    constraints = _controller_parameters(arm).get("constraints")
    assert constraints, f"{arm} has no generated constraints block — ADR-0036"
    return constraints


def _joints(arm):
    return list(_controller_parameters(arm)["joints"])


def _urdf(arm, stuck):
    """Return a minimal arm carrying the joints the generated file names.

    The joint NAMES are read from that configuration rather than written here: a
    controller whose joint names differ from the description by one character
    claims no interfaces and silently ignores every command, which is the failure
    this rig would then be measuring instead of the one it is for.

    The joint limits are deliberately far wider than anything the tests command.
    `enforce_command_limits: true` is set in the same generated file, so a narrow
    limit here would clamp the command, and the resulting error would be the
    limiter's doing rather than the injected fault's.
    """
    joints = _joints(arm)
    links = "".join('<link name="{0}_link"/>'.format(j) for j in joints)

    tree = ""
    parent = "base_link"
    for joint in joints:
        tree += (
            '<joint name="{0}" type="revolute">'
            '<parent link="{1}"/><child link="{0}_link"/>'
            '<origin xyz="0 0 0.1"/><axis xyz="0 0 1"/>'
            '<limit lower="-6.28" upper="6.28" velocity="10.0" effort="100.0"/>'
            "</joint>"
        ).format(joint, parent)
        parent = "{0}_link".format(joint)

    interfaces = "".join(
        (
            '<joint name="{0}">'
            '<command_interface name="position"/>'
            '<state_interface name="position">'
            '<param name="initial_value">0.0</param>'
            "</state_interface>"
            '<state_interface name="velocity"/>'
            "</joint>"
        ).format(joint)
        for joint in joints
    )

    # `disable_commands` makes GenericSystem::read() return before propagating
    # the command, so the state interface stays at `initial_value` above while
    # the trajectory advances. From the controller's point of view the joint is
    # held, which is what a trajectory clipping a fixture looks like.
    disable = '<param name="disable_commands">true</param>' if stuck else ""

    return (
        '<?xml version="1.0"?><robot name="{0}_rig">'
        '<link name="base_link"/>{1}{2}'
        '<ros2_control name="{0}_rig" type="system">'
        "<hardware><plugin>mock_components/GenericSystem</plugin>{3}</hardware>"
        "{4}</ros2_control></robot>"
    ).format(arm, links, tree, disable, interfaces)


def _rig(arm, stuck):
    namespace = f"/cite/{ZONE}/{arm}"
    description = _urdf(arm, stuck)
    return [
        # The controller manager finds the description on this namespace's own
        # `robot_description` topic, exactly as it does under `gz_ros2_control`
        # in the real bring-up. No remapping, one publisher per transform.
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="description_publisher",
            namespace=namespace,
            parameters=[{"robot_description": description, "use_sim_time": False}],
            remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
            output="log",
        ),
        Node(
            package="controller_manager",
            executable="ros2_control_node",
            name="controller_manager",
            namespace=namespace,
            parameters=[
                # THE FILE UNDER TEST, unmodified.
                str(_config_path(arm)),
                # The generated file says `use_sim_time: true` because the cell
                # it configures runs under Gazebo. There is no `/clock` in this
                # rig, and a manager waiting for one never runs a control cycle.
                # The override is the rig's, not the model's, and it changes
                # nothing about the tolerances under test: they are position
                # errors compared against a clock, not derived from one.
                {"use_sim_time": False},
                {"robot_description": description},
            ],
            output="screen",
        ),
        Node(
            package="controller_manager",
            executable="spawner",
            name=f"spawn_{arm}",
            arguments=[
                f"{arm}_joint_trajectory_controller",
                "--controller-manager",
                f"{namespace}/controller_manager",
                "--controller-manager-timeout",
                str(STARTUP_CEILING_S),
            ],
            output="screen",
        ),
    ]


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    return LaunchDescription(
        _rig(TRACKING_ARM, False)
        + _rig(STUCK_ARM, True)
        + [launch_testing.actions.ReadyToTest()]
    )


class _Activation:
    """Records that one arm's trajectory controller has reached ACTIVE.

    `JointTrajectoryController::update()` ends with an unconditional
    `publish_state()` (`joint_trajectory_controller.cpp` 4.40.1, the version in
    the container image), and `controller_manager` calls `update()` only on a
    controller that is ACTIVE. So one message on `controller_state` proves this
    controller is active *and* running control cycles against its hardware —
    which is the precondition a goal needs, and strictly more than "the action
    server exists".
    """

    def __init__(self, node, arm):
        self.arm = arm
        self.seen = False
        self.subscription = node.create_subscription(
            JointTrajectoryControllerState,
            f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller/controller_state",
            self._record,
            CONTROLLER_STATE_QOS,
        )

    def _record(self, _message):
        self.seen = True


class TestTheGeneratedTolerancesAreRead(unittest.TestCase):
    """The generated numbers, enforced by a real `JointTrajectoryController`."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode("trajectory_constraints_test")

        # THE RIG IS READY WHEN BOTH CONTROLLERS ARE ACTIVE, and that is an
        # event rather than an elapsed time (P4).
        #
        # `ReadyToTest` fires as soon as the processes are spawned; each spawner
        # then loads, configures and activates its controller, which took ~4 s
        # on the CI runner. `ActionClient.wait_for_server()` does NOT bridge that
        # gap, and this is the whole defect: `joint_trajectory_controller` 4.40.1
        # creates its `follow_joint_trajectory` server in `on_configure`, so the
        # server is discoverable while the controller is still INACTIVE, and
        # `goal_received_callback` then rejects on its very first check —
        #
        #     if (get_lifecycle_state().id() == ...PRIMARY_STATE_INACTIVE)
        #       "Can't accept new action goals. Controller is not running."
        #       return rclcpp_action::GoalResponse::REJECT;
        #
        # An action rejection carries no reason to the client, so all the test
        # could see was a bare `handle.accepted == False`. On CI run 33200891048
        # the goal reached arm_2 10.6 ms before its "Activating controllers"
        # line; on an idle machine the same goal lands after activation and
        # everything passes. That is the entire "intermittent, load-correlated"
        # behaviour this file carried — a race with the spawner, not with any
        # earlier test, and not specific to arm_2: reproducing it under CPU
        # contention failed on arm_1 too.
        waiters = [_Activation(cls.node, arm) for arm in (TRACKING_ARM, STUCK_ARM)]
        deadline = cls.node.get_clock().now() + Duration(seconds=STARTUP_CEILING_S)
        while not all(w.seen for w in waiters):
            if cls.node.get_clock().now() >= deadline:
                break
            rclpy.spin_once(cls.node, timeout_sec=0.1)

        missing = [w.arm for w in waiters if not w.seen]
        # Destroyed either way: at 150 Hz per arm these would otherwise deliver
        # 300 messages a second into every `spin_until_future_complete` below,
        # adding load to the very contention that produced the defect.
        for waiter in waiters:
            cls.node.destroy_subscription(waiter.subscription)

        assert not missing, (
            f"{', '.join(missing)} published no controller_state within "
            f"{STARTUP_CEILING_S}s, so its trajectory controller never reached "
            "ACTIVE and nothing below could have measured a tolerance."
        )

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _client(self, arm):
        client = ActionClient(
            self.node,
            FollowJointTrajectory,
            f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller/follow_joint_trajectory",
        )
        # Kept for the clear message it gives if the server is absent outright.
        # It is NOT what makes a goal safe to send: this server is created in
        # `on_configure`, so it answers while the controller is still INACTIVE
        # and rejects everything. `setUpClass` holds that gate.
        self.assertTrue(
            client.wait_for_server(timeout_sec=STARTUP_CEILING_S),
            f"{arm} never offered follow_joint_trajectory — its controller never configured",
        )
        return client

    def _run(self, arm, amplitude):
        """Command every joint to `amplitude` radians and return the result.

        The goal carries no `path_tolerance` or `goal_tolerance` of its own, so
        the controller falls back to its configured `constraints:` — which is the
        whole point. MoveIt sends goals the same way, which is why the generated
        block is what governs a real motion.
        """
        joints = _joints(arm)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = joints

        start = JointTrajectoryPoint()
        start.positions = [0.0] * len(joints)
        start.velocities = [0.0] * len(joints)
        start.time_from_start.sec = 0

        end = JointTrajectoryPoint()
        end.positions = [amplitude] * len(joints)
        end.velocities = [0.0] * len(joints)
        end.time_from_start.sec = int(MOVE_DURATION_S)

        goal.trajectory.points = [start, end]

        client = self._client(arm)
        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, send, timeout_sec=GOAL_CEILING_S)
        handle = send.result()
        self.assertIsNotNone(handle, f"{arm} never answered the goal request")
        self.assertTrue(handle.accepted, f"{arm} rejected the trajectory")

        result = handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, result, timeout_sec=GOAL_CEILING_S)
        outcome = result.result()
        self.assertIsNotNone(
            outcome,
            f"{arm} returned no result within {GOAL_CEILING_S}s. A goal that "
            "neither succeeds nor fails is the goal_time hang ADR-0036 describes.",
        )
        return outcome.result

    def test_a_tracked_trajectory_still_succeeds(self):
        """A healthy motion must not trip the detector.

        This is the direction that matters most for keeping the detector alive.
        `./scripts/scenario pick_and_place` is a blocking CI gate, and a
        tolerance that fires on a good run is a flake — which this project's
        history says gets exempted rather than fixed.

        Read its limits honestly: mock hardware tracks perfectly, so what this
        shows is that the block is not *inherently* self-tripping. It does not
        show that the margin over a real Gazebo following error is adequate.
        That measurement belongs to a scenario run and ADR-0036 names it as
        outstanding.
        """
        joint = _joints(TRACKING_ARM)[0]
        amplitude = 2.0 * _constraints(TRACKING_ARM)[joint]["trajectory"]
        result = self._run(TRACKING_ARM, amplitude)
        self.assertEqual(
            result.error_code,
            FollowJointTrajectory.Result.SUCCESSFUL,
            f"a perfectly tracked trajectory was rejected: {result.error_string!r}",
        )

    def test_a_held_joint_violates_the_path_tolerance(self):
        """The auditor's case: the arm cannot follow, and the goal now fails.

        Before ADR-0036 this returned SUCCESSFUL. The controller ran the whole
        trajectory against a joint that never moved, reported success, MoveIt
        passed that on, and `Pick` reported a pick it had not made.
        """
        joint = _joints(STUCK_ARM)[0]
        path_tolerance = _constraints(STUCK_ARM)[joint]["trajectory"]
        # The joint is held at 0.0, so the commanded position IS the error.
        result = self._run(STUCK_ARM, path_tolerance * 2.0)
        self.assertEqual(
            result.error_code,
            FollowJointTrajectory.Result.PATH_TOLERANCE_VIOLATED,
            f"a held joint was not detected mid-trajectory: {result.error_string!r}",
        )

    def test_an_error_under_the_path_tolerance_still_fails_at_the_goal(self):
        """The two thresholds are two numbers, not one.

        The commanded amplitude sits deliberately between them — above `goal`,
        below `trajectory`. So the path check must stay silent for the whole
        motion and the goal check must fail afterwards. If the generator had
        emitted one value for both keys, or the controller read only one of them,
        this is the test that notices.

        It also exercises `goal_time` as a real deadline: the result can only
        arrive because the controller stopped waiting. With `goal_time: 0.0` this
        call would hang until `GOAL_CEILING_S` and fail on the assertion in
        `_run` instead.
        """
        joint = _joints(STUCK_ARM)[0]
        constraints = _constraints(STUCK_ARM)
        goal_tolerance = constraints[joint]["goal"]
        path_tolerance = constraints[joint]["trajectory"]

        amplitude = goal_tolerance * 10.0
        self.assertLess(
            amplitude,
            path_tolerance,
            "the generated tolerances no longer leave a band between them, so "
            "this test can no longer tell the two checks apart",
        )

        result = self._run(STUCK_ARM, amplitude)
        self.assertEqual(
            result.error_code,
            FollowJointTrajectory.Result.GOAL_TOLERANCE_VIOLATED,
            f"a joint short of its goal was accepted: {result.error_string!r}",
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):

    def test_processes_exit_cleanly(self, proc_info):
        # A spawner exits 0 once its controller is active; the managers and the
        # publishers are stopped by the harness, which is the SIGINT code.
        allowed = [0, launch_testing.asserts.EXIT_SIGINT, -15]
        for info in proc_info:
            self.assertIn(
                info.returncode,
                allowed,
                f"{info.process_name} exited with {info.returncode}",
            )
