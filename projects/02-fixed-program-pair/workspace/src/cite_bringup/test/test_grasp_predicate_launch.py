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

"""ADR-0052: a stall is judged against the part, driven through a real controller.

The predicate `cite_skills::gripper_is_holding` used to compare the width the
jaws REACHED against the width they were COMMANDED to. The command is a policy
value and the error the predicate makes is about where the *part* is, and both
directions of that error are measured — a real grasp reported empty, witnessed by
the work-piece's own contact sensor, and a stall on nothing reported as a grasp.
Cite `docs/measurements/2026-09-01-grasp-discrimination/`; its figures stay in
that directory (P1).

Option F replaces it with a window around the interval of declared work-piece
widths, both edges declared in L0. The arithmetic is held by
`cite_skills/test/test_gripper.cpp` and the model half by
`tools/tests/test_stall_band.py`. **This file holds the half neither can: that
the window is applied by the running node, to a stall produced by a real
`GripperActionController` over real hardware interfaces.**

## What makes the stall happen, and why it is a STATE and not a wait

The gripper's hardware is `cite_test_hardware/JointStopSystem` (ADR-0040):
`GenericSystem` with a pair of hard stops on the drive joint. The jaws close
normally until the drive joint reaches its stop and then stand there, so
`GripperActionController` sees a joint below `stall_velocity_threshold` for
`stall_timeout` and reports `stalled` with `reached_goal` false — the exact
report a part between the pads produces. Nothing here waits for a duration and
nothing engages on a timer: a slower machine stalls at the same joint angle (P4).

**IT IS A SYNTHETIC STOP AT A DECLARED POSITION AND NOT A PART.** Nothing is
between the pads. That is the point — it is what lets the same rig ask both
halves of the question — and it is also this rig's limit: it says nothing about
where a real jam stops, which ADR-0052 §A.9.2 records as the quantity F's central
claim rests on and nobody has measured.

## The discrimination is in the STOP, and the stop is where a part would be

Two runs of one rig, differing in one number: the drive position the stops are
placed at. One is inside the window the plan's own values open, one is outside
it. Everything else — the description, the controller configuration, the skill
parameters, the goal — is identical, which is a stronger statement than two rigs
side by side could make. `launch_testing.parametrize` is what runs it twice,
because the stop is read once at `on_init` from the description and cannot be
moved by a goal.

## Every threshold is read, never written here

The window is computed from the generated bring-up plan — the band from the
arm's own gripper block, the interval from the plan's facility block — through
the same closed form `cite_skills` evaluates, built from the linkage dimensions
the plan delivers. If any of those move in L0, this file follows them (P1). What
it states of its own is one margin, and it says why it is what it is.

## What this does NOT evidence

That the defect is fixed. ADR-0052 §A.10 item 2's campaign has not run, and item
5 says in as many words that no green run promotes this. A synthetic stop
demonstrates the mechanism applies; it is not a grasp.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ElementTree

from cite_bringup import plan as bringup_plan
from cite_interfaces.action import Grasp
from cite_interfaces.msg import ResultCode
from control_msgs.action import GripperCommand
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import launch_testing
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node as RclpyNode

ZONE = 'cell_a'
ARM = 'arm_1'

#: The hardware plugin every generated description declares, and the two this rig
#: substitutes for it. Asserted rather than assumed when the swap is made: if the
#: L0 backend ever changes, this rig must fail loudly rather than quietly stop
#: substituting anything.
PRODUCTION_PLUGIN = 'gz_ros2_control/GazeboSimSystem'
FIXTURE_PLUGIN = 'cite_test_hardware/JointStopSystem'
#: Everything that is not the gripper — here, the arm — gets the vendor's own
#: mock, unmodified. Only the component under test is replaced.
MOCK_PLUGIN = 'mock_components/GenericSystem'

STARTUP_CEILING_S = 180.0
GOAL_CEILING_S = 120.0

PLAN = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
MANAGER = next(entry for entry in PLAN.controller_managers if entry.asset == ARM)
NAMESPACE = MANAGER.node.rsplit('/', 1)[0]
CONTROLLER_CONFIG = bringup_plan.resolve_uri(MANAGER.parameters)

#: The interval of declared work-piece widths, from the plan's facility block. The
#: rig refuses to be written against a plan that states none rather than assuming
#: one: a default here would be a width the model never stated, applied inside the
#: predicate this file exists to check.
assert PLAN.workpieces is not None, (
    'the generated plan states no `workpieces:` block, so there is no window for '
    'this rig to place a stop inside or outside (ADR-0052). Run '
    './scripts/validate-model --write, then ./scripts/build.'
)
NARROWEST_M = PLAN.workpieces.narrowest_width_m
WIDEST_M = PLAN.workpieces.widest_width_m

#: The band, from the arm's own gripper block. Read rather than restated: it is
#: an L0 value and a literal here would be the second copy P1 forbids.
BAND_NARROW_M = MANAGER.gripper['gripper_stall_band_narrow_m']
BAND_WIDE_M = MANAGER.gripper['gripper_stall_band_wide_m']

#: The window the running node will apply. Computed here from the same two
#: statements the node is given, so the rig cannot drift from what it checks.
WINDOW_LOW_M = NARROWEST_M - BAND_NARROW_M
WINDOW_HIGH_M = WIDEST_M + BAND_WIDE_M

#: How far outside the window the outside case is placed, in metres. Two
#: millimetres, an order of magnitude above the 0.1 mm the grasp-discrimination
#: campaign reports as its resolution, so the case sits clear of the edge rather
#: than riding the boundary this rig is not the instrument for. The EDGE itself is
#: pinned to a micrometre in `test_gripper.cpp`, where it costs nothing.
OUTSIDE_MARGIN_M = 0.002


def _closed_forms():
    """Return the width map and its inverse, from the linkage the PLAN delivers.

    The same closed form `cite_skills::gripper_width_for` evaluates, built from
    the same four dimensions the plan hands the skill server. Rebuilt here rather
    than imported because `cite_skills` is a C++ library with no Python binding;
    what keeps the two honest is that both read one statement of the linkage, and
    that `test_gripper.cpp` pins the map against the simulator's own stroke.
    """
    gripper = MANAGER.gripper
    pivot = gripper['gripper_drive_pivot_y_m'] - gripper['gripper_pad_inset_m']
    crank = math.hypot(
        gripper['gripper_finger_offset_y_m'], gripper['gripper_finger_offset_z_m'])
    phase = math.atan2(
        gripper['gripper_finger_offset_z_m'], gripper['gripper_finger_offset_y_m'])

    def width_for(position):
        return 2.0 * (pivot + crank * math.cos(position + phase))

    def position_for(width):
        cosine = max(-1.0, min(1.0, (width / 2.0 - pivot) / crank))
        return math.acos(cosine) - phase

    return width_for, position_for


WIDTH_FOR, POSITION_FOR = _closed_forms()

#: The drive joint the stops go on, read from the controller the plan names for
#: the gripper rather than composed from the asset id.
DRIVE_JOINT = None


def _gripper_controller_parameters():
    key = MANAGER.gripper_action.rsplit('/', 1)[0]
    document = __import__('yaml').safe_load(CONTROLLER_CONFIG.read_text())
    return document[key]['ros__parameters']


DRIVE_JOINT = _gripper_controller_parameters()['joint']

#: What the jaws are commanded to close to. The shipped default, from the plan.
#: Narrower than either stop, so the drive joint is still travelling when it
#: meets one — which is what makes the controller report a stall rather than a
#: reached goal, and is the same relationship a real part produces.
COMMANDED_M = MANAGER.gripper['gripper_default_grasp_width_m']

#: The two cases, as WIDTHS the stops are placed at. Named rather than positional
#: so that a reader of a failure knows which one failed.
#:
#: INSIDE is the narrowest declared part's own width — where that part would
#: stop the jaws — and it must be reported as holding. OUTSIDE is clear below the
#: window's narrow edge, where nothing this facility declares could have stopped
#: them, and it must not.
STOPS = {
    'inside': NARROWEST_M,
    'outside': WINDOW_LOW_M - OUTSIDE_MARGIN_M,
}


def _production_launch():
    """Load `simulation.launch.py` as a module, for its parameter builders.

    The rig gives `move_group` and the skill server the parameters the PRODUCTION
    launch file builds for them, rather than a second set assembled here — which
    is the whole point on this file's subject: the four values ADR-0052 adds
    reach the node through `_skill_parameters`, and a rig that assembled them by
    hand would prove the predicate works on numbers the cell does not deliver.
    """
    path = Path(__file__).resolve().parents[1] / 'launch' / 'simulation.launch.py'
    spec = importlib.util.spec_from_file_location('cite_bringup_simulation_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SIM = _production_launch()


def _rig_description(stop_width_m):
    """Build the rig's description: the GENERATED one, altered in two asserted ways.

    Expanded with `xacro` exactly as the production launch does, then: the
    GRIPPER's `<ros2_control>` hardware plugin is replaced by the fixture and
    given stops that hold the drive joint at `stop_width_m`, and every other
    component gets the vendor's plain mock. Link geometry, joint limits,
    interface declarations and joint names are the generated file's, untouched —
    so the controller this rig loads claims the same interfaces it claims in the
    cell.

    The stops are TWO-SIDED and the lower one is at the open end of the stroke.
    The jaws travel from open towards closed, so the upper stop is the one they
    meet; the lower is placed at the open position because `JointStopSystem`
    requires a strictly ordered pair and refuses a joint that starts outside it.

    The `<gazebo>` elements are dropped. They carry the simulator's own system
    plugin and a path to the controller configuration that a plain
    `ros2_control_node` has no use for; leaving them in would be leaving a
    second, contradictory statement about who runs the controllers.
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

    stop_upper = POSITION_FOR(stop_width_m)
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
        if DRIVE_JOINT not in names:
            plugin.text = MOCK_PLUGIN
            continue
        plugin.text = FIXTURE_PLUGIN
        for key, value in (
            ('stop_joint', DRIVE_JOINT),
            ('stop_lower_rad', repr(-1.0)),
            ('stop_upper_rad', repr(stop_upper)),
        ):
            parameter = ElementTree.SubElement(hardware, 'param')
            parameter.set('name', key)
            parameter.text = value
        stopped += 1

    assert stopped == 1, (
        f'expected exactly one <ros2_control> block to declare {DRIVE_JOINT}, '
        f'found {stopped}'
    )
    return ElementTree.tostring(robot, encoding='unicode')


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
@launch_testing.parametrize('case', sorted(STOPS))
def generate_test_description(case):
    """One arm, with the fixture in place of the simulator's gripper hardware."""
    description = _rig_description(STOPS[case])
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
                # THE GENERATED FILE, UNMODIFIED. The `stall_timeout`,
                # `stall_velocity_threshold` and `goal_tolerance` this rig's
                # stall is declared by are the cell's own.
                str(CONTROLLER_CONFIG),
                # The generated file says `use_sim_time: true` because the cell
                # it configures runs under Gazebo. There is no `/clock` here and
                # a manager waiting for one never runs a control cycle. The
                # override is the rig's, it is applied to every node in the rig,
                # and it changes nothing under test: the predicate compares two
                # widths and derives nothing from a clock.
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
                # production launch file's own function — including the band and
                # the work-piece interval, which are the four values this whole
                # file is about.
                SIM._skill_parameters(PLAN, MANAGER),
                {'use_sim_time': False},
            ],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='screen',
        ),
        launch_testing.actions.ReadyToTest(),
    ]), {'case': case}


@launch_testing.markers.keep_alive
class TestTheWindowIsAppliedByTheRunningNode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode('grasp_predicate_test')
        cls.client = ActionClient(cls.node, Grasp, MANAGER.skills.grasp)

        # THE RIG IS READY WHEN THIS EXISTS, which is an event rather than an
        # elapsed time (P4). `ReadyToTest` fires as soon as the processes are
        # spawned, well before the controller manager has activated anything: a
        # goal sent then finds no `gripper_cmd` action server and comes back
        # PRECONDITION_FAILED, which is a distinguishable answer rather than a
        # false pass — but a red that says nothing about the predicate.
        gripper = ActionClient(cls.node, GripperCommand, MANAGER.gripper_action)
        assert gripper.wait_for_server(timeout_sec=STARTUP_CEILING_S), (
            f'{MANAGER.gripper_action} never appeared: the gripper controller did '
            f'not activate, so nothing in this rig could have produced a stall.'
        )

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin(self, future, ceiling_s):
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=ceiling_s)
        return future.result()

    def _grasp(self, width_m):
        """Close to `width_m` and return the result, without asserting on it.

        `expect_object` is FALSE deliberately. With it true the server turns
        "not holding" into an `EXECUTION_FAILED`, and the two cases would then
        differ in their result CODE — which is a fine contract and a worse
        instrument, because a code can also be produced by a controller that
        never answered. False leaves the verdict in `holding`, where this file
        can read the predicate's own answer rather than an inference from it.
        """
        self.assertTrue(
            self.client.wait_for_server(timeout_sec=STARTUP_CEILING_S),
            f'{MANAGER.skills.grasp} never appeared — the skill server did not start',
        )
        goal = Grasp.Goal()
        goal.width_m = width_m
        goal.max_effort_n = 60.0
        goal.expect_object = False

        handle = self._spin(self.client.send_goal_async(goal), GOAL_CEILING_S)
        self.assertIsNotNone(handle, 'the skill server never answered the goal request')
        self.assertTrue(handle.accepted, 'the skill server rejected the goal')
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        self.assertIsNotNone(
            outcome,
            f'no Grasp result within {GOAL_CEILING_S}s. A close that neither stalls '
            f'nor reaches goal is the non-terminating goal ADR-0045 bounds, and this '
            f'rig has no simulated clock for that deadline to be measured in.',
        )
        return outcome.result

    def test_1_the_stall_is_real_and_the_window_decides_it(self, case):
        """One rig, one goal, and the stop is the only thing that differs.

        THREE ASSERTIONS IN ONE TEST, AND THE ORDER IS THE ARGUMENT. First that
        the close ended at the stop rather than at its goal — without that the
        verdict below is about a rig that produced no stall. Then where that put
        the reached width relative to the window. Only then the predicate's
        answer, which is the one thing under test.
        """
        result = self._grasp(COMMANDED_M)
        self.assertEqual(
            result.result.code, ResultCode.SUCCESS,
            f'the close did not complete: {result.result.detail}',
        )

        expected_m = STOPS[case]
        self.assertAlmostEqual(
            result.reached_width_m, expected_m, delta=1e-3,
            msg=(
                f'the jaws stopped at {result.reached_width_m * 1000.0:.3f} mm, not at '
                f'the {expected_m * 1000.0:.3f} mm stop this rig placed. The verdict '
                f'below would then be about a stall that did not happen where this '
                f'test thinks it did.'
            ),
        )
        self.assertGreater(
            result.reached_width_m, COMMANDED_M,
            f'the jaws reached or passed the {COMMANDED_M * 1000.0:.1f} mm they were '
            f'commanded to, so the controller ended on its goal-tolerance branch and '
            f'this rig produced no stall at all — which is a different report from a '
            f'stall and would make the verdict below meaningless',
        )

        inside = WINDOW_LOW_M < result.reached_width_m < WINDOW_HIGH_M
        self.assertEqual(
            inside, case == 'inside',
            f'case {case!r} put the reached width at '
            f'{result.reached_width_m * 1000.0:.3f} mm, which is '
            f'{"inside" if inside else "outside"} the window '
            f'[{WINDOW_LOW_M * 1000.0:.3f}, {WINDOW_HIGH_M * 1000.0:.3f}] mm — the '
            f'opposite of what this case exists to produce',
        )

        self.assertEqual(
            result.holding, case == 'inside',
            f'case {case!r}: the jaws stalled at '
            f'{result.reached_width_m * 1000.0:.3f} mm against a window of '
            f'[{WINDOW_LOW_M * 1000.0:.3f}, {WINDOW_HIGH_M * 1000.0:.3f}] mm and the '
            f'server reported holding={result.holding}. Both cases were commanded to '
            f'the same {COMMANDED_M * 1000.0:.1f} mm, so nothing but where the jaws '
            f'stopped can account for a difference.',
        )

    def test_2_the_commanded_width_does_not_move_the_verdict(self, case):
        """ADR-0052's decision, driven rather than reasoned about.

        The same stop, judged again after a command that would have INVERTED the
        old predicate's answer. Under the commanded-width margin a caller could
        move the band by moving the command — which is the unvalidated caller
        door the campaign demonstrated. Here the command is a width the jaws
        cannot reach at all, and the verdict is unchanged because nothing in the
        decision reads it.

        The width is below the gripper's own minimum opening, so it saturates to
        a fully-closed command: the jaws still travel into the stop and still
        stall, and the only thing that changed is the number the old predicate
        would have subtracted.
        """
        result = self._grasp(0.001)
        self.assertEqual(result.result.code, ResultCode.SUCCESS)
        self.assertAlmostEqual(result.reached_width_m, STOPS[case], delta=1e-3)
        self.assertEqual(
            result.holding, case == 'inside',
            f'case {case!r} changed its verdict when only the COMMANDED width '
            f'changed. The command is a policy value and the error is about where '
            f'the part is, which is the whole of ADR-0052.',
        )
