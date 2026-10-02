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

"""A `Place` whose release never happened must fail, holding the part.

The defect this rig exists for, in one sentence: `GripperActionController`
SUCCEEDS a command it has declared stalled — the stall is a field in the result,
never the goal's status — so an open commanded onto a part that does not let go
comes back `SUCCESS`, and `Place` retreated on it.

Measured on this cell on 2026-09-24 and recorded in ADR-0063's measurement table:
the release returned `commanded 88.9 mm, reached 50.0 mm, stalled=true,
reached_goal=false` while the jaws were still shut on the box, `Place` reported a
successful place, and the box was let go 39 mm above the belt at whatever point
of the retreat the joint finally opened — a different point on each side of the
pair, which is the 74.68 mm that record quotes.

`execute_place` and `execute_transfer` both carried a comment describing the test
their code could not make — *"The jaws did not open, so the part is still between
them"* — while branching on `gripper.result.code`, which is `SUCCESS` on exactly
that path. `SkillServer::release_jaws` is the confirmation that makes the comment
true: it commands the jaws fully open ONCE and then asks
`cite_skills::gripper_is_holding` whether they opened, failing if they still read
as holding. One command, one answer, and no re-asking — the bound on that one
answer is `gripper_result_timeout_` inside `command_gripper` (ADR-0045) and there
is no second deadline anywhere on the path.

## What is asserted, and why each half needs the other

Four facts, and no two of them are satisfiable by one defect:

  * **A release that did not happen fails, and says the arm still has the part.**
    The fake gripper below succeeds an opening command while reporting the jaws
    stalled where a declared work-piece would have stopped them. `Place` must
    terminate unsuccessfully with `still_holding` TRUE — which is the field L5
    aggregates and the field a recovery is meant to choose on.
  * **A release that DID happen proceeds.** The same rig, the same goal, the same
    arm, with the fake reporting `reached_goal` at the width it was sent. Without
    this, the assertion above also passes on a rig that is simply broken — on one
    where `Place` never reached the release step at all, or where every `Place`
    fails. The two cases differ in NOTHING but what the gripper reports, which is
    a stronger statement than two rigs side by side could make.
  * **The failure is reached by the CONFIRMATION and not by a timeout of the
    action.** The code has to be `EXECUTION_FAILED` and the detail has to name the
    width the jaws reached, so that a future change which makes `Place` fail for
    an unrelated reason — an unreachable pose, a planning refusal, a cancelled
    goal — does not keep this file green.
  * **Each release sends EXACTLY ONE command, in both cases.** Re-asking is the
    shape this function had first and may not have again: `command_gripper`'s wait
    breaks on a ready future before it tests for cancellation, so a loop here is
    uncancellable for its whole window while L4's fault branch waits on the goal
    ending. It is also the only assertion of the four that sees the obvious
    mutant — a holding check moved out of a loop and tested after it leaves every
    other assertion green while the control burns a whole deadline.

## Every number is read, never written here

The width the fake stalls at is the narrowest work-piece the generated plan
declares, and the drive position it reports is that width through the linkage the
plan delivers. The window the running node judges it against is built from the
same two statements. If any of them move in L0 this file follows them (P1); a
literal here would be the second copy that P1 forbids, and it is the copy that
would decide whether this test still tests anything.

## The gripper is a fake and everything else is real

A real `GripperActionController` cannot be asked to succeed a stall on demand at
one step of a skill and not at another, and a rig that produced the condition by
clamping the drive joint would be measuring the thing ADR-0063 decided against.
The fake serves `GripperCommand` and answers it the way the controller does —
`handle.succeed()` WITH `stalled` set, which is the upstream behaviour the whole
defect rests on. Everything above it is production: the generated description,
the generated controller configuration, a real `move_group`, the real skill
server, and the parameters the production launch file builds.

Because the plant is mock hardware, this says NOTHING about what a real gripper
does, how long a real stall takes, or what a physical server puts in `stalled` —
which `release_jaws`'s own header records as unestablished and therefore as an
unimplemented hardware path. ADR-0063 measured 116 commands and zero releases
against a clamped joint, over both sides of a pair; this rig cannot and does not
speak to that, and the re-asking that measurement condemned is not what ships.

## What this does NOT evidence

`Transfer` carries the identical call and is **not** covered here: that skill
has a server and no program calls it (CLAUDE.md §2), and no rig in this
repository drives it. Its call site is
the same one line and is left as it is.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import subprocess
import threading
import time
import unittest
import xml.etree.ElementTree as ElementTree

from cite_bringup import plan as bringup_plan
from cite_interfaces.action import Grasp, MoveTo, Place
from cite_interfaces.msg import ResultCode
from control_msgs.action import FollowJointTrajectory, GripperCommand
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import launch_testing
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node as RclpyNode
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

ZONE = 'cell_b'
ARM = 'picker'

#: The hardware plugin every generated description declares, and the one this rig
#: substitutes for it. Asserted rather than assumed when the swap is made, exactly
#: as its two neighbours assert it: if the L0 backend changes, this rig must fail
#: loudly rather than quietly stop substituting anything.
PRODUCTION_PLUGIN = 'gz_ros2_control/GazeboSimSystem'
MOCK_PLUGIN = 'mock_components/GenericSystem'

#: Where the fake controller answers. Outside the arm's namespace on purpose: the
#: real `arm_1_gripper_controller` is still spawned by this rig, and a fake sharing
#: its name would be a test that passed because two servers raced.
FAKE_GRIPPER_ACTION = '/fake_gripper/gripper_cmd'

STARTUP_CEILING_S = 240.0
#: How long a skill result is waited for. A FAILURE deadline on the test's own
#: wall clock and not a quantity under test: the motions below are millimetres and
#: the gripper answers instantly, so a working implementation finishes orders of
#: magnitude inside it.
GOAL_CEILING_S = 180.0

#: The deadline this rig gives the skill server, in seconds of the node's clock.
#: THE RIG'S NUMBER AND NOT THE CELL'S, for the same reason
#: `test_gripper_deadline_launch.py` overrides it. It bounds how long the node
#: waits for the fake to ANSWER a command at all, which is the only thing
#: `gripper_result_timeout_` bounds on this path; the fake answers immediately, so
#: a working implementation never approaches it and a hung one fails here rather
#: than spending the cell's declared 20 s. Nothing under test is measured against
#: it: the confirmation compares reported widths and re-asks nothing. That the L0
#: value reaches this node under this name is a different claim and is already
#: held by `test_plan.py`.
RELEASE_CEILING_S = 3.0


def _production_launch():
    """Load `simulation.launch.py` as a module, for its parameter builders.

    The same reasoning as the two rigs beside this one: `move_group` and the skill
    server are given the parameters the PRODUCTION launch file builds, so a rig
    configured differently from the cell cannot pass while the cell fails. Four
    keys are overridden and only four — the robot description, `use_sim_time`, the
    gripper action, and the release deadline — and each is the point of the
    fixture.
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
CONTROLLER_CONFIG = bringup_plan.resolve_uri(MANAGER.parameters)

#: The interval of declared work-piece widths, from the plan's facility block. The
#: rig refuses to be written against a plan that states none rather than assuming
#: one: a default here would be a width the model never stated, reported by the
#: fake into the predicate this file's first assertion depends on.
assert PLAN.workpieces is not None, (
    'the generated plan states no `workpieces:` block, so there is no width for the '
    'fake gripper to stall at and nothing the node would call a held part '
    '(ADR-0052). Run ./scripts/validate-model --write, then ./scripts/build.'
)

#: Where the jaws stall when a part this facility declares is between them: the
#: narrowest declared width. Inside `gripper_is_holding`'s window by construction —
#: the window is that interval widened by the end effector's own stall band — which
#: is what makes the fake's report the report a real grasp produces.
HELD_WIDTH_M = PLAN.workpieces.narrowest_width_m

#: What a `Grasp` closes to. The shipped default, from the plan. Narrower than the
#: part on purpose (ADR-0022), so the command below is a CLOSING command that the
#: jaws fail to reach — which is the relationship the fake reads to tell a close
#: from a release.
GRASP_WIDTH_M = MANAGER.gripper['gripper_default_grasp_width_m']

#: The effort the rig's `Grasp` asks for, in newtons. The rig's number and not the
#: cell's: the fake echoes it back untouched and nothing here is judged on it. The
#: RELEASE's effort is production's — `execute_place` reads it from the node's own
#: `gripper_max_effort_n`, which arrives with the parameter set above.
GRASP_EFFORT_N = 60.0

#: How far the rig's release pose sits from the configuration the arm is already
#: in, in metres, along the tool axis. Five millimetres.
#:
#: SMALL ON PURPOSE AND NOT ZERO. Nothing in this file is about where the arm
#: goes — the release step is, and every motion before it exists only to reach it
#: — so the three motions `Place` makes are perturbations of the `home`
#: configuration the model declares, with the tool's orientation unchanged. That
#: makes each one IK-solvable by construction rather than by luck, which is what
#: keeps a planning refusal from being read here as a failed release. Zero would
#: not do: a plan whose start and goal are the same point is a degenerate request
#: and this rig should not be asking one.
RELEASE_STANDOFF_M = 0.005


def _closed_forms():
    """Return the linkage's three maps, built from what the PLAN delivers.

    The same closed forms `cite_skills::gripper_width_for`,
    `gripper_position_for` and `gripper_pad_plane_offset_m` evaluate, built from
    the same dimensions the plan hands the skill server. Rebuilt here rather than
    imported for the reason `test_grasp_predicate_launch.py` gives for doing the
    same: `cite_skills` is a C++ library with no Python binding, and `cite_tools`
    — which holds the single home of these maps — is host tooling that is not on
    the path inside the container. What keeps the two honest is that both read one
    statement of the linkage, and that `test_gripper.cpp` pins the map against the
    simulator's own stroke.
    """
    gripper = MANAGER.gripper
    pivot = gripper['gripper_drive_pivot_y_m'] - gripper['gripper_pad_inset_m']
    crank = math.hypot(
        gripper['gripper_finger_offset_y_m'], gripper['gripper_finger_offset_z_m'])
    phase = math.atan2(
        gripper['gripper_finger_offset_z_m'], gripper['gripper_finger_offset_y_m'])
    axial_reach = (
        gripper['gripper_tip_link_z_m']
        - gripper['gripper_drive_pivot_z_m']
        - gripper['gripper_pad_face_centre_z_m']
    )

    def width_for(position):
        return 2.0 * (pivot + crank * math.cos(position + phase))

    def position_for(width):
        cosine = max(-1.0, min(1.0, (width / 2.0 - pivot) / crank))
        return math.acos(cosine) - phase

    def pad_plane_offset_for(position):
        return axial_reach - crank * math.sin(position + phase)

    return width_for, position_for, pad_plane_offset_for


WIDTH_FOR, POSITION_FOR, PAD_PLANE_OFFSET_FOR = _closed_forms()

#: The drive position the fake reports whenever the jaws are on the part: where
#: `HELD_WIDTH_M` puts them. Derived, so that the width the node computes back out
#: of it — and prints in the failure this file asserts on — is the declared one.
HELD_POSITION = POSITION_FOR(HELD_WIDTH_M)

#: How far proximal of the planning tip link the pad face sits while the part is
#: held. `execute_place` shifts the caller's target by exactly this, because the
#: target names where the OBJECT goes and the object is between the pads; the rig
#: cancels the shift so that the release pose it asks for is the one it means.
PAD_OFFSET_M = PAD_PLANE_OFFSET_FOR(HELD_POSITION)


def _rig_description() -> str:
    """Build the generated description with every hardware plugin replaced by a mock.

    Nothing in this rig is about the arm's hardware: the plant only has to be real
    enough for `move_group` to plan and execute millimetres, and for the skill
    server to reach its gripper. The substitution is asserted so that a changed L0
    backend fails here rather than silently leaving the simulator's plugin in a
    launch that has no simulator.

    The `<gazebo>` elements are dropped for the reason the sibling rigs drop them:
    they carry the simulator's own system plugin and a path to the controller
    configuration that a plain `ros2_control_node` has no use for.
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
    for block in blocks:
        plugin = block.find('hardware').find('plugin')
        assert plugin.text.strip() == PRODUCTION_PLUGIN, (
            f'{block.get("name")} declares {plugin.text.strip()!r}, not '
            f'{PRODUCTION_PLUGIN!r}. The L0 backend has changed and this rig is no '
            f'longer substituting what it thinks it is.'
        )
        plugin.text = MOCK_PLUGIN
    return ElementTree.tostring(robot, encoding='unicode')


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    """One arm on mock hardware, with a fake gripper in place of the controller."""
    description = _rig_description()
    semantic = ParameterValue(
        Command(['xacro ', str(MANAGER.moveit.srdf)]), value_type=str
    )
    moveit = MANAGER.moveit
    # Ordered by the stage the generated plan declares, so the state broadcaster is
    # active before anything claims a command interface — the same order production
    # spawns them in, read from the same place.
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
                # THE GENERATED FILE, UNMODIFIED.
                str(CONTROLLER_CONFIG),
                # The generated file says `use_sim_time: true` because the cell it
                # configures runs under Gazebo. There is no `/clock` here and a
                # manager waiting for one never runs a control cycle. The override
                # is the rig's, it is applied to every node in the rig rather than
                # to some of them, and it changes nothing under test: the release
                # confirmation compares a reported width against declared ones and
                # derives nothing from a clock but its own ceiling.
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
                # production launch file's own function — including the work-piece
                # interval the release confirmation is judged against, which is the
                # number this whole test is about. Taking the production set first
                # is what makes the three overrides below changes of three values
                # rather than a differently configured node.
                SIM._skill_parameters(PLAN, MANAGER),
                {
                    'use_sim_time': False,
                    'gripper_action': FAKE_GRIPPER_ACTION,
                    'gripper_result_timeout_s': RELEASE_CEILING_S,
                },
            ],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='screen',
        ),
        launch_testing.actions.ReadyToTest(),
    ])


class _FakeGripper:
    """A `GripperCommand` server that succeeds a stall, the way the real one does.

    THE UPSTREAM BEHAVIOUR THE WHOLE DEFECT RESTS ON, produced as a state rather
    than by clamping a joint (P4, and ADR-0063 decision). `GripperActionController`
    reports a stall in a FIELD of its result and succeeds the goal regardless, so
    `handle.succeed()` below is called on both branches and is not a mistake.

    It answers a CLOSING command — one that asks for a width no wider than where
    the part is — as a real controller answers a grasp: stalled at the part, goal
    not reached. That branch is the same in both modes, because a close onto the
    part is not what this rig varies.

    It answers an OPENING command according to `mode`, and that is the one thing
    the two cases differ in:

      * `JAWS_STAY_SHUT` — the jaws do not move. The report is the one ADR-0063
        measured: the position they are already at, `stalled` true, `reached_goal`
        false. `cite_skills::gripper_is_holding` reads that as still holding.
      * `JAWS_OPEN` — the jaws open. `reached_goal` true at the width commanded,
        which the predicate reads as not holding by its first condition.

    Opening and closing are told apart by WIDTH rather than by the sign of a drive
    position, so the rig does not assume which end of the stroke the model calls
    open.
    """

    JAWS_STAY_SHUT = 'the jaws do not move off the part'
    JAWS_OPEN = 'the jaws open to where they were sent'

    def __init__(self, node):
        self._lock = threading.Lock()
        self._mode = self.JAWS_STAY_SHUT
        self._commands = []
        self._server = ActionServer(
            node,
            GripperCommand,
            FAKE_GRIPPER_ACTION,
            execute_callback=self._execute,
            goal_callback=lambda _goal: GoalResponse.ACCEPT,
            cancel_callback=lambda _handle: CancelResponse.ACCEPT,
        )

    def set_mode(self, mode):
        """Decide how the next OPENING command is answered."""
        with self._lock:
            self._mode = mode

    def commanded_widths(self):
        """Every width commanded so far, in order. Evidence, not a threshold."""
        with self._lock:
            return list(self._commands)

    def _execute(self, handle):
        commanded_position = handle.request.command.position
        commanded_width = WIDTH_FOR(commanded_position)
        with self._lock:
            self._commands.append(commanded_width)
            mode = self._mode

        result = GripperCommand.Result()
        result.effort = handle.request.command.max_effort
        opening = commanded_width > HELD_WIDTH_M
        if opening and mode == self.JAWS_OPEN:
            result.position = commanded_position
            result.reached_goal = True
            result.stalled = False
        else:
            result.position = HELD_POSITION
            result.reached_goal = False
            result.stalled = True
        # SUCCEEDED WITH `stalled` SET. This is the line the defect lives behind:
        # a caller reading `result.code` alone cannot tell this from a release.
        handle.succeed()
        return result


class ReleaseConfirmationTest(unittest.TestCase):
    """One arm, one fake gripper, two places that differ only in what it reports."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode('release_confirmation_test')
        cls.gripper = _FakeGripper(cls.node)
        # A background executor rather than `spin_until_future_complete`: the fake
        # gripper is served by this same node, so a blocking spin inside a wait
        # would stop it answering the very command being waited on.
        cls.executor = MultiThreadedExecutor()
        cls.executor.add_node(cls.node)
        cls.spinner = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.spinner.start()

        # THE RIG IS READY WHEN THESE EXIST, and each is an event rather than an
        # elapsed time (P4). `ReadyToTest` fires as soon as the processes are
        # spawned, which is well before the controller manager has activated
        # anything — and this rig OBSERVED that: without these waits the first
        # `MoveTo home` came back in 1.4 s with "the commanded trajectory did not
        # take effect ... (MoveIt error code -4)", the same race
        # `test_abort_classification_launch.py` measured. Here it is worse than a
        # confusing red, because a `Place` that fails before its release step is
        # the shape of the failure this file asserts, and only the code and the
        # detail tell them apart.
        arrived = threading.Event()
        # Declared rather than defaulted (CLAUDE.md §10): `joint_state_broadcaster`
        # publishes on the system default profile, reliable and volatile, and this
        # matches it. Depth 1, because what is wanted is that one has arrived.
        cls.node.create_subscription(
            JointState,
            f'{NAMESPACE}/joint_states',
            lambda _message: arrived.set(),
            QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
            ),
        )
        trajectory = ActionClient(
            cls.node, FollowJointTrajectory, MANAGER.trajectory_action)
        assert trajectory.wait_for_server(timeout_sec=STARTUP_CEILING_S), (
            f'{MANAGER.trajectory_action} never appeared: the trajectory controller '
            f'did not activate, so no Place in this rig could have reached its release.'
        )
        assert arrived.wait(STARTUP_CEILING_S), (
            f'no joint state arrived on {NAMESPACE}/joint_states; the skill server '
            f'seeds its IK from this topic and refuses every goal without it.'
        )

    @classmethod
    def tearDownClass(cls):
        cls.executor.shutdown()
        cls.node.destroy_node()
        rclpy.shutdown()

    def test_a_place_whose_release_never_happened_fails_holding_the_part(self):
        """The control first, then the defect, in one rig and in this order.

        ONE METHOD BECAUSE THE ORDER IS LOAD-BEARING and a shared arm carries its
        state. The control establishes that this rig reaches the release step and
        gets past it, which is what makes the failure below a statement about the
        confirmation rather than about the fixture.
        """
        # ---- The control: the jaws open, and `Place` completes ----------------
        self.gripper.set_mode(_FakeGripper.JAWS_OPEN)
        self._grasp()
        before_control = len(self.gripper.commanded_widths())
        control = self._place()
        self.assertEqual(
            control.result.code, ResultCode.SUCCESS,
            f'a Place whose gripper reported the jaws open at the width it was sent '
            f'returned {control.result.code}: {control.result.detail!r}. Nothing below '
            f'is evidence about the release confirmation until this passes — a rig that '
            f'never reaches the release step fails every Place for its own reasons.',
        )
        self.assertFalse(
            control.still_holding,
            'a completed place reported that the arm is still holding the part',
        )
        self.assertEqual(
            len(self.gripper.commanded_widths()) - before_control, 1,
            f'the release sent '
            f'{len(self.gripper.commanded_widths()) - before_control} gripper '
            f'command(s) where it must send exactly one. See the defect case below '
            f'for why the count is asserted and not merely observed.',
        )

        # ---- The defect: the jaws stay shut, and `Place` must say so -----------
        self.gripper.set_mode(_FakeGripper.JAWS_STAY_SHUT)
        self._grasp()
        before = len(self.gripper.commanded_widths())
        outcome = self._place()

        self.assertNotEqual(
            outcome.result.code, ResultCode.SUCCESS,
            f'the gripper succeeded an open it had declared stalled, with the part '
            f'still between the pads, and Place reported a successful place. That is '
            f'the defect: it retreats from here and lets go wherever it gets to '
            f'(ADR-0063). Detail: {outcome.result.detail!r}',
        )
        self.assertTrue(
            outcome.still_holding,
            f'Place failed its release and reported `still_holding` false. The part is '
            f'between the pads; a recovery reading this opens the jaws on a work-piece '
            f'no planner knows is held. Detail: {outcome.result.detail!r}',
        )

        # ---- It failed BY THE CONFIRMATION, and not for some other reason ------
        #
        # Without these two, a future change that makes Place fail on an
        # unreachable pose, a planning refusal or its own ceiling keeps this file
        # green while the defect is back.
        self.assertEqual(
            outcome.result.code, ResultCode.EXECUTION_FAILED,
            f'the release failed with code {outcome.result.code} rather than '
            f'EXECUTION_FAILED. TIMEOUT would mean the controller never answered — it '
            f'answered every time here — and anything else means this Place failed '
            f'somewhere other than its release: {outcome.result.detail!r}',
        )
        reached = f'{HELD_WIDTH_M * 1000.0:.1f} mm'
        self.assertIn(
            reached, outcome.result.detail,
            f'the failure does not quote the width the jaws reached ({reached}), so a '
            f'reader is told that a release failed and not what the gripper said: '
            f'{outcome.result.detail!r}',
        )

        # ---- EXACTLY ONE COMMAND, AND THIS IS THE ASSERTION THAT PINS THE SHAPE --
        #
        # Not a count for its own sake. Re-asking is what this function used to do
        # and what it may not do again: `command_gripper`'s wait breaks on a ready
        # future before it tests for cancellation, so a loop here is uncancellable
        # for its whole window while L4's fault branch waits on the goal ending —
        # and ADR-0063 measured 116 such commands buying zero releases.
        #
        # It is also the assertion that kills the mutant the four above survive.
        # Move the holding check out of a loop and test it afterwards and every
        # other assertion in this method stays green while the control case burns a
        # whole deadline; the command count is the only thing that sees it.
        asked = len(self.gripper.commanded_widths()) - before
        self.assertEqual(
            asked, 1,
            f'the release sent {asked} gripper command(s) where it must send exactly '
            f'one. A fully-open command is idempotent, which is what makes re-asking '
            f'look free, and it is not: the re-ask cannot be cancelled and the '
            f'measurement in ADR-0063 that condemned it was taken against 116 of them.',
        )

    def _grasp(self):
        """Close on the part, and require the node to agree that it is held.

        `Place` is refused outright unless this arm believes it holds something,
        and `still_holding` is read from that same belief — so a rig whose grasp
        did not register would assert nothing at all below.
        """
        goal = Grasp.Goal()
        goal.width_m = GRASP_WIDTH_M
        goal.max_effort_n = GRASP_EFFORT_N
        goal.expect_object = True
        outcome = self._send(Grasp, MANAGER.skills.grasp, goal, 'Grasp')
        self.assertEqual(
            outcome.result.code, ResultCode.SUCCESS,
            f'the grasp failed: {outcome.result.detail!r}')
        self.assertTrue(
            outcome.holding,
            f'the node did not read the fake gripper as holding the part. It reported '
            f'the jaws stalled at the narrowest declared work-piece width '
            f'({HELD_WIDTH_M * 1000.0:.1f} mm), which is inside the window '
            f'`gripper_is_holding` opens by construction: {outcome.result.detail!r}',
        )

    def _place(self):
        """Put the part down five millimetres from where the arm is standing.

        The target is expressed IN THE TOOL'S OWN FRAME, so it is always "just
        behind where you are" wherever the previous case left the arm, and no pose
        is read or computed here. Its z cancels the pad-plane shift `execute_place`
        applies — the caller's target names where the OBJECT goes, and the object
        sits proximal of the planning tip link by exactly that much — so the pose
        the arm is actually sent to is the standoff this rig chose and not a
        stroke-dependent distance from it.
        """
        self._home()
        goal = Place.Goal()
        goal.target_pose.header.frame_id = MANAGER.moveit.tip_link
        goal.target_pose.pose.orientation.w = 1.0
        goal.target_pose.pose.position.z = -PAD_OFFSET_M - RELEASE_STANDOFF_M
        goal.approach_distance_m = RELEASE_STANDOFF_M
        goal.retreat_distance_m = RELEASE_STANDOFF_M
        goal.require_holding = True
        return self._send(Place, MANAGER.skills.place, goal, 'Place')

    def _home(self):
        """Put the arm at the configuration L0 declares, before each case.

        Both cases therefore plan from one state, which is what makes "they differ
        in nothing but what the gripper reports" true of the motion as well as of
        the goal.
        """
        goal = MoveTo.Goal()
        goal.named_configuration = 'home'
        outcome = self._send(MoveTo, MANAGER.skills.move_to, goal, 'MoveTo home')
        self.assertEqual(
            outcome.result.code, ResultCode.SUCCESS,
            f'the arm could not reach the home configuration, so nothing below plans '
            f'from a known state: {outcome.result.detail!r}',
        )

    def _send(self, action, name, goal, label):
        """Send one goal and return its result, on the test's own failure deadlines."""
        client = ActionClient(self.node, action, name)
        self.assertTrue(
            client.wait_for_server(timeout_sec=STARTUP_CEILING_S),
            f'the skill server never advertised {name}; it needs move_group in '
            f'{NAMESPACE} before it advertises anything',
        )
        handle_future = client.send_goal_async(goal)
        self.assertTrue(
            self._settled(handle_future, GOAL_CEILING_S),
            f'the {label} goal was never answered')
        handle = handle_future.result()
        self.assertTrue(handle.accepted, f'the skill server rejected the {label} goal')

        result_future = handle.get_result_async()
        self.assertTrue(
            self._settled(result_future, GOAL_CEILING_S),
            f'no {label} result within {GOAL_CEILING_S} s. A goal that neither succeeds '
            f'nor fails is not the failure this file is about',
        )
        return result_future.result().result

    @staticmethod
    def _settled(future, ceiling_s):
        """Wait for a future, on the test's own wall clock. A failure deadline."""
        started = time.monotonic()
        while time.monotonic() - started < ceiling_s:
            if future.done():
                return True
            time.sleep(0.02)
        return future.done()
