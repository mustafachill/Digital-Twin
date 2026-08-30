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

"""ADR-0045: the gripper deadline, driven to expiry in a clock the test owns.

The defect this rig exists for, in one sentence: a wall-clock deadline in
`cite_skills` supervised a process that runs entirely in simulation time, so on a
loaded CI runner it expired while the gripper was still moving — three times, and
each time `Pick` reported the arm empty while the jaws held the work-piece.

## What is asserted, and why each half needs the other

Two facts, and either alone is satisfiable by a defect:

  * **Wall-clock time passing does not expire it.** The simulated clock is held
    still and `WALL_WINDOW_S` is spent in WALL time. That window is sized against
    the 20 s constant the code this replaces compared against, not against this
    rig's own deadline, so the replaced code gives up INSIDE it and this assertion
    fires. It is the only assertion in this repository that would have caught the
    CI failure — and it was not, until the window was widened: at three times the
    rig's 4 s deadline it was twelve wall seconds, which the old code survives.
  * **Simulated time passing does.** The clock is then advanced past the declared
    value and the wait ends at once. Without this, a deadline that never fires at
    all would pass the first assertion perfectly.

The boundary is asserted too: the clock is advanced to just SHORT of the declared
timeout first, and the wait must survive that. So what is measured is the
declared number in the node's clock, not merely "some clock other than the host's".

## What it does with the answer, which is the second half of the decision

On expiry L3 must **send a cancel** for the goal it gave up on, and must **not**
report an empty gripper. Both are checked: the fake controller records the cancel
request, and the `ResultCode.detail` has to say that custody is unestablished.
`Grasp.Result.holding` is a `bool` and cannot say "unknown" — ADR-0045 decision 4
is explicit that widening the contract is not taken here — so the assertion is
that the honest statement is present where it CAN be made, not that a boolean
carries a third state.

**What this rig CANNOT check, stated so that nobody cites it for it.** The fake
gripper below ACCEPTS every cancel, immediately. A real controller may never serve
one — this is the path on which it is not answering — and if it serves one late,
`check_for_success` can have terminated the goal successfully in between, so
`cancel_callback`'s guard does not match and `set_hold_position()` never runs. The
two outcomes leave the jaws squeezing and not squeezing respectively. That the
cancel was SENT is what the assertion below is about, and it is all this fixture
can be about; what a real `GripperActionController` does with it is ADR-0045's
open residual and is measured by nothing here.

**The third thing checked is the refusal that follows** (ADR-0045 decision 4, the
`custody_unknown_` latch). After the timeout, a `Pick` — whose first physical act
is to open the jaws — and a `Place` are both sent, and both must come back
`PRECONDITION_FAILED` naming the unestablished custody rather than being attempted
on an arm nobody has observed.

## The value is the rig's and the mechanism is production's

`gripper_result_timeout_s` is overridden to a small number, because a test that
spent the cell's declared 20 s of simulated time would spend it for no gain: what
is under test is which clock the number is counted in and what happens when it
runs out. That the L0 value reaches this node under this name is a different
claim, and it is already held by `test_plan.py` — which requires every key in
`GRIPPER_KEYS` to be stated in the generated plan AND declared by the skill
server's own source.

## The gripper is a fake and everything else is real

The controller is replaced, not simulated slowly: a real `GripperActionController`
cannot be made to withhold a result on demand, and a rig that produced the
condition by loading the machine would be measuring the runner. The fake accepts
the goal and then does nothing, which is exactly the state the deadline is defined
against — "the controller has not terminated this goal". Everything above it is
production: the generated description, the generated controller configuration, a
real `move_group`, the real skill server, and the parameters the production launch
file builds.

Because the plant is mock hardware, this says NOTHING about what a real gripper
does, how long a real stall takes, or whether `GripperActionController` honours a
cancel. ADR-0045 records that last one as an open question and this rig does not
close it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import threading
import time
import unittest
import xml.etree.ElementTree as ElementTree

from cite_bringup import plan as bringup_plan
from cite_interfaces.action import Grasp, Pick, Place
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
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node as RclpyNode
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock

ZONE = 'cell_a'
ARM = 'arm_1'

#: The hardware plugin every generated description declares, and the one this rig
#: substitutes for it. Asserted rather than assumed when the swap is made, exactly
#: as `test_abort_classification_launch.py` asserts it: if the L0 backend changes,
#: this rig must fail loudly rather than quietly stop substituting anything.
PRODUCTION_PLUGIN = 'gz_ros2_control/GazeboSimSystem'
MOCK_PLUGIN = 'mock_components/GenericSystem'

#: Where the fake controller answers. Outside the arm's namespace on purpose: the
#: real `arm_1_gripper_controller` is still spawned by this rig, and a fake sharing
#: its name would be a test that passed because two servers raced.
FAKE_GRIPPER_ACTION = '/fake_gripper/gripper_cmd'

#: The deadline this rig gives the skill server, in seconds of the node's clock.
#: The rig's number and not the cell's — see the module docstring.
DEADLINE_S = 4.0

#: How far short of the deadline the clock is advanced before the wait is required
#: to SURVIVE. Nine tenths, so the assertion is about the declared value rather
#: than about "some time passed".
SHORT_OF_DEADLINE = 0.9

#: How far past it the clock is then advanced. A tenth over, for the same reason.
PAST_DEADLINE = 1.1

#: The constant this deadline replaces: `constexpr std::chrono::seconds
#: kGripperResultWait{20}`, compared against `steady_clock` (ADR-0045). Stated here
#: because the window below is sized against IT and not against `DEADLINE_S`.
REPLACED_WALL_DEADLINE_S = 20.0

#: How long the wall clock is allowed to run, in wall seconds, while simulated time
#: stands still and the wait is required not to expire.
#:
#: SIZED SO THAT THE REPLACED CODE FAILS INSIDE IT, WHICH IS THE WHOLE POINT AND WAS
#: NOT TRUE. This was `3.0 * DEADLINE_S` — twelve wall seconds — and the docstring
#: above claimed a `steady_clock` deadline "would have given up here". It would not:
#: the code this replaces compares against a compiled 20 s and ignores
#: `gripper_result_timeout_s` entirely, because it does not declare it, so the rig's
#: 4 s override reaches it not at all. Twelve seconds of wall clock is a window the
#: old code survives; it failed this test eight seconds later, on the cancel and the
#: detail, for reasons that are not what the docstring said.
#:
#: A multiple of `DEADLINE_S` was the wrong unit as well as the wrong size. What the
#: window has to outlast is a number in the OLD code, which no override moves, so it
#: is stated in wall seconds against that number with two seconds of margin — the
#: old deadline starts a moment after `wait_for_goal` returns, not before it.
WALL_WINDOW_S = REPLACED_WALL_DEADLINE_S + 2.0

STARTUP_CEILING_S = 240.0
#: How long a result is waited for once simulated time has passed the deadline. It
#: is a FAILURE deadline on the test's own clock, not a quantity under test: the
#: poll inside `command_gripper` is 20 ms, so a working implementation answers
#: three orders of magnitude inside this.
RESULT_CEILING_S = 30.0


def _production_launch():
    """Load `simulation.launch.py` as a module, for its parameter builders.

    The same reasoning as `test_abort_classification_launch.py`: `move_group` and
    the skill server are given the parameters the PRODUCTION launch file builds,
    so a rig configured differently from the cell cannot pass while the cell fails.
    Three keys are overridden and only three — the robot description, the gripper
    action, and the deadline — and each is the point of the fixture.
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

#: What a `Grasp` closes to, taken from the plan rather than written here. The
#: width is irrelevant to what is measured — the fake never moves — but a width
#: this gripper cannot express would fail before the wait began.
GRASP_WIDTH_M = float(MANAGER.gripper['gripper_default_grasp_width_m'])
GRASP_EFFORT_N = 60.0


def _rig_description() -> str:
    """Build the generated description with every hardware plugin replaced by a mock.

    Nothing in this rig is about the arm's hardware: the plant only has to be real
    enough for `move_group` to start and for the skill server to reach `Grasp`. The
    substitution is asserted so that a changed L0 backend fails here rather than
    silently leaving the simulator's plugin in a launch that has no simulator.
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
    """One arm on mock hardware, under a clock this test process owns.

    `use_sim_time` is TRUE everywhere, which is the opposite of what
    `test_abort_classification_launch.py` does and is the whole point here: that
    rig has no clock to offer and nothing it measures comes from one, while this
    one measures a deadline that must follow `/clock`. Nothing publishes `/clock`
    from inside the launch — the test process does, so that the test can stop it.
    """
    description = _rig_description()
    semantic = ParameterValue(
        Command(['xacro ', str(MANAGER.moveit.srdf)]), value_type=str
    )
    moveit = MANAGER.moveit
    controllers = [name for _, names in MANAGER.stages() for name in names]

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='description_publisher',
            namespace=NAMESPACE,
            parameters=[{'robot_description': description, 'use_sim_time': True}],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='log',
        ),
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            name='controller_manager',
            namespace=NAMESPACE,
            parameters=[
                # The generated file, unmodified, and it already says
                # `use_sim_time: true` because the cell it configures runs under
                # Gazebo. Here that is not an override at all — it is the setting
                # the rig wants, served by this process's `/clock`.
                str(CONTROLLER_CONFIG),
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
                    'use_sim_time': True,
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
                # `gripper_result_timeout_s` this rig then overrides. Taking the
                # production set first is what makes the override a change of one
                # value rather than a differently configured node.
                SIM._skill_parameters(PLAN, MANAGER),
                {
                    'use_sim_time': True,
                    'gripper_action': FAKE_GRIPPER_ACTION,
                    'gripper_result_timeout_s': DEADLINE_S,
                },
            ],
            remappings=[('/tf', '/tf'), ('/tf_static', '/tf_static')],
            output='screen',
        ),
        launch_testing.actions.ReadyToTest(),
    ])


class _SimulatedClock:
    """`/clock`, published by this process and stoppable by it.

    A rig that could not stop time could not tell a deadline in simulated time from
    one in wall time, which is the entire distinction under test.

    IT KEEPS PUBLISHING WHILE HELD, rather than falling silent. A subscriber that
    stops receiving `/clock` and one that receives the same stamp repeatedly are
    different conditions, and only the second is "time is not advancing" — the
    first is a dead publisher, which is a fault rather than a state.
    """

    #: `rclcpp`'s own clock subscription profile: keep the last, best effort,
    #: volatile. Declared here rather than defaulted, because a reliable publisher
    #: against that best-effort subscription is one of the silent mismatches
    #: CLAUDE.md §10 is about.
    PROFILE = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )

    #: Where simulated time starts. Non-zero, because a node that reads a zero
    #: stamp cannot tell it from "no clock has arrived".
    EPOCH_S = 1000.0

    #: How often the clock is published, in wall seconds. Faster than the 20 ms
    #: poll inside `command_gripper`, so the expiry the test provokes is seen on
    #: the poll after the one that crossed it.
    PERIOD_S = 0.01

    def __init__(self, node):
        self._publisher = node.create_publisher(Clock, '/clock', self.PROFILE)
        self._lock = threading.Lock()
        self._seconds = self.EPOCH_S
        self._running = True
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._publish_forever, daemon=True)

    def start(self):
        self._thread.start()

    def shutdown(self):
        self._stop.set()
        self._thread.join(timeout=5.0)

    def hold(self):
        """Stop advancing. The stamp goes on being published, unchanged."""
        with self._lock:
            self._running = False

    def advance(self, seconds):
        """Step simulated time forward by `seconds`, while it is held."""
        with self._lock:
            self._seconds += seconds

    @property
    def seconds(self):
        with self._lock:
            return self._seconds

    def _publish_forever(self):
        last = time.monotonic()
        while not self._stop.is_set():
            time.sleep(self.PERIOD_S)
            now = time.monotonic()
            elapsed, last = now - last, now
            with self._lock:
                if self._running:
                    self._seconds += elapsed
                seconds = self._seconds
            message = Clock()
            message.clock.sec = int(seconds)
            message.clock.nanosec = int((seconds - int(seconds)) * 1e9)
            self._publisher.publish(message)


class _SilentGripper:
    """A `GripperCommand` server that accepts a goal and then never answers.

    THE CONDITION THE DEADLINE IS DEFINED AGAINST, produced as a state rather than
    by loading the machine (P4). `GripperActionController` ends a goal when the
    joint arrives or when it has stopped for `stall_timeout`; this ends it never,
    which is what "the controller never answered" means and is the only thing this
    deadline is allowed to mean (ADR-0045 decision 3).

    It records cancellations because that is decision 4's other half: a deadline
    that gives up and leaves the controller commanding a closed position at full
    effort has abandoned a goal rather than ended one.
    """

    def __init__(self, node):
        self._accepted = threading.Event()
        self._cancel_requested = threading.Event()
        self._release = threading.Event()
        self._server = ActionServer(
            node,
            GripperCommand,
            FAKE_GRIPPER_ACTION,
            execute_callback=self._execute,
            goal_callback=lambda _goal: GoalResponse.ACCEPT,
            cancel_callback=self._cancel,
        )

    @property
    def accepted(self):
        return self._accepted.is_set()

    @property
    def cancel_requested(self):
        return self._cancel_requested.is_set()

    def wait_for_goal(self, timeout):
        return self._accepted.wait(timeout)

    def release(self):
        """Let any held goal end, so the rig can shut down."""
        self._release.set()

    def _cancel(self, _handle):
        self._cancel_requested.set()
        return CancelResponse.ACCEPT

    def _execute(self, handle):
        self._accepted.set()
        # Held on the test's own event, not on a duration: nothing here is
        # sequenced by a guessed time, and the goal ends when the test says so.
        self._release.wait(timeout=RESULT_CEILING_S * 2)
        handle.abort()
        return GripperCommand.Result()


class GripperDeadlineTest(unittest.TestCase):
    """One held gripper goal, watched across two clocks."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode('gripper_deadline_test')
        cls.clock = _SimulatedClock(cls.node)
        cls.gripper = _SilentGripper(cls.node)
        cls.executor = MultiThreadedExecutor()
        cls.executor.add_node(cls.node)
        cls.spinner = threading.Thread(target=cls.executor.spin, daemon=True)
        cls.spinner.start()
        cls.clock.start()

    @classmethod
    def tearDownClass(cls):
        cls.gripper.release()
        cls.clock.shutdown()
        cls.executor.shutdown()
        cls.node.destroy_node()
        rclpy.shutdown()

    def test_the_deadline_is_the_nodes_clock_and_its_expiry_cancels_the_goal(self):
        client = ActionClient(self.node, Grasp, MANAGER.skills.grasp)
        self.assertTrue(
            client.wait_for_server(timeout_sec=STARTUP_CEILING_S),
            f'the skill server never advertised {MANAGER.skills.grasp}; it needs '
            f'move_group in {NAMESPACE} before it advertises anything',
        )

        goal = Grasp.Goal()
        goal.width_m = GRASP_WIDTH_M
        goal.max_effort_n = GRASP_EFFORT_N
        # False, because what happens to an empty grasp is ADR-0022's question and
        # this goal never gets far enough to have an answer to it.
        goal.expect_object = False

        # THE CLOCK STOPS BEFORE THE GOAL IS SENT, so the deadline cannot be
        # partly spent before the rig is in the state under test.
        self.clock.hold()
        held_at = self.clock.seconds

        handle_future = client.send_goal_async(goal)
        self.assertTrue(
            self._settled(handle_future, RESULT_CEILING_S), 'the Grasp goal was never accepted')
        handle = handle_future.result()
        self.assertTrue(handle.accepted, 'the skill server rejected the Grasp')
        result_future = handle.get_result_async()

        self.assertTrue(
            self.gripper.wait_for_goal(RESULT_CEILING_S),
            'the skill server never reached the gripper, so nothing below is about '
            'the wait this test exists for',
        )

        # ---- The half that fails against a wall-clock deadline ----------------
        #
        # Wall time runs; simulated time does not. The code this replaces compared
        # `steady_clock::now()` against a 20 s constant and gives up INSIDE this
        # window — which is what a starved CI runner did to it three times, at
        # 20.009 s, 20.025 s and 20.048 s of a clock the gripper does not run on.
        # `WALL_WINDOW_S` is sized against that constant rather than against this
        # rig's deadline, because the old code declares no parameter and so never
        # sees the override.
        started = time.monotonic()
        while time.monotonic() - started < WALL_WINDOW_S:
            time.sleep(0.05)
            self.assertFalse(
                result_future.done(),
                f'the wait ended after {time.monotonic() - started:.3f} s of WALL clock '
                f'while the simulated clock had not moved at all. The deadline is being '
                f'measured against the host, which is the defect ADR-0045 is about',
            )
        self.assertFalse(
            self.gripper.cancel_requested,
            'the gripper goal was cancelled while the deadline had not expired',
        )
        self.assertEqual(
            self.clock.seconds, held_at, 'the clock advanced on its own, so the wall-clock '
            'assertion above was not made against a stopped clock')

        # ---- The boundary: just short of the declared value -------------------
        self.clock.advance(SHORT_OF_DEADLINE * DEADLINE_S)
        started = time.monotonic()
        while time.monotonic() - started < 2.0:
            time.sleep(0.05)
            self.assertFalse(
                result_future.done(),
                f'the wait ended after {SHORT_OF_DEADLINE * DEADLINE_S:.3f} s of simulated '
                f'time, short of the {DEADLINE_S} s declared. Whatever it is counting, it '
                f'is not the value it was given',
            )

        # ---- And past it -------------------------------------------------------
        self.clock.advance((PAST_DEADLINE - SHORT_OF_DEADLINE) * DEADLINE_S)
        self.assertTrue(
            self._settled(result_future, RESULT_CEILING_S),
            f'simulated time passed the {DEADLINE_S} s deadline and the wait did not end. '
            f'A deadline that never expires is not a bound',
        )

        outcome = result_future.result().result
        self.assertEqual(
            outcome.result.code, ResultCode.TIMEOUT,
            f'the skill reported code {outcome.result.code} rather than TIMEOUT: '
            f'{outcome.result.detail}',
        )

        # DECISION 4, FIRST HALF: a cancel is SENT for the goal it gave up on, so
        # the controller is asked to stop holding a commanded position for a goal
        # nobody waits on. WHAT IS ASSERTED IS THE SEND. This fake accepts every
        # cancel; a real controller may never serve one, and this fixture cannot
        # tell the difference — see the module docstring.
        self.assertTrue(
            self.gripper.cancel_requested,
            'the deadline expired and no cancel was even sent for the gripper goal. The '
            'controller goes on commanding the closed position at the configured effort '
            'for a goal nobody is waiting on',
        )

        # DECISION 4, SECOND HALF: it does not claim an empty gripper. The boolean
        # cannot say "unknown" — widening the contract is deliberately not taken —
        # so the statement has to be in the detail, and this is what requires it to
        # be there.
        detail = outcome.result.detail
        self.assertIn(
            'UNESTABLISHED', detail,
            f'the timeout does not say that custody is unestablished, so a reader is left '
            f'to infer an empty gripper from a false `holding` field: {detail!r}',
        )
        # IT SAYS WHAT WAS DONE, NOT WHAT RESULTED. The detail used to end "the goal
        # has been cancelled" — an assertion about a controller that is, on this very
        # path, not answering. The words asserted here are the ones that survive both
        # outcomes of an unawaited cancel.
        self.assertIn(
            'SENT', detail,
            f'the timeout does not say that a cancel was SENT rather than served: '
            f'{detail!r}')
        self.assertNotIn(
            'has been cancelled', detail,
            f'the timeout asserts that the goal WAS cancelled. The cancel is sent and '
            f'not awaited, on the path where the controller is not answering, so that '
            f'is a claim about the plant nothing here observed: {detail!r}')
        self.assertFalse(
            outcome.holding,
            '`holding` is a bool and false is the only value it has here; a true would '
            'be claiming a grasp nothing observed, which is the opposite defect')

        # ---- DECISION 4, THIRD HALF: the refusal that follows -------------------
        #
        # `holding_` was left unwritten, which every consumer reads as false. The
        # latch is what stops that reading turning into motion: `Pick`'s first
        # physical act is to open the jaws, and `pick` is a public action that any
        # client can send. L4's ADR-0046 rule keeps the LINE out of this state; it
        # cannot keep anything else out, so the interlock is in the layer that owns
        # the fact.
        #
        # The goals are otherwise EMPTY on purpose. A refusal that needed a valid
        # pose to be produced would be a refusal reached after something had been
        # resolved, planned or moved; this one is the first statement in each
        # handler, and an empty goal is what proves it.
        pick = Pick.Goal()
        pick.workpiece_id = 'wp_in_unknown_custody'
        self._assert_refused_for_unestablished_custody(
            Pick, MANAGER.skills.pick, pick, 'Pick')
        self._assert_refused_for_unestablished_custody(
            Place, MANAGER.skills.place, Place.Goal(), 'Place')

    def _assert_refused_for_unestablished_custody(self, action, name, goal, label):
        """One skill, sent after the timeout, required to refuse and to say why."""
        client = ActionClient(self.node, action, name)
        self.assertTrue(
            client.wait_for_server(timeout_sec=STARTUP_CEILING_S),
            f'the skill server never advertised {name}')

        handle_future = client.send_goal_async(goal)
        self.assertTrue(
            self._settled(handle_future, RESULT_CEILING_S),
            f'the {label} goal was never answered')
        handle = handle_future.result()
        self.assertTrue(
            handle.accepted,
            f'the {label} goal was rejected outright rather than refused with a reason. '
            f'A rejection carries no ResultCode, so an operator is told nothing')

        result_future = handle.get_result_async()
        self.assertTrue(
            self._settled(result_future, RESULT_CEILING_S),
            f'the {label} sent after a gripper timeout never returned. It must refuse, '
            f'not attempt anything')
        outcome = result_future.result().result.result
        self.assertEqual(
            outcome.code, ResultCode.PRECONDITION_FAILED,
            f'{label} returned code {outcome.code} after a gripper timeout rather than '
            f'refusing. Its next physical act assumes a gripper nothing has observed: '
            f'{outcome.detail}',
        )
        self.assertIn(
            'UNESTABLISHED', outcome.detail,
            f'{label} refused without saying that custody is unestablished, which leaves '
            f'a reader to infer an empty gripper from a false `holding`: '
            f'{outcome.detail!r}',
        )

    @staticmethod
    def _settled(future, ceiling_s):
        """Wait for a future, on the test's own wall clock. A failure deadline."""
        started = time.monotonic()
        while time.monotonic() - started < ceiling_s:
            if future.done():
                return True
            time.sleep(0.02)
        return future.done()
