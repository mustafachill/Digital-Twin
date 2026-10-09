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

"""The operator console server (ADR-0071) over the real twin boundary and two fake sides.

The rig of `test_twin_boundary_paired_launch.py` - each side a `fake_side.py`
process on a domain of its own, both simulated, the real `twin_boundary.py`
between them - with the real `cell_console.py` on the plant's domain, which
is where the test process sits too. It lives in `cite_twin` rather than beside
the console in `cite_bringup` because it starts the boundary, and `cite_twin`
depends on `cite_bringup`, never the other way round.

**What it covers.** The console's names and its latched state; every refusal
before Start robot; Start robot on an all-simulated pair (nothing to initialize,
custody read off a `RobotState` this test publishes on the plant's domain);
the speed scale and cycle count refused at the goal; and Home through the
boundary - the start measured with `JointsAt` and `TrackArrived`, VALIDATED
asked with the homing allowance, the first move answered by both fakes - up to
the track slide, which a fake carriage never completes, and there the goal is
CANCELLED: the console's stop interrupts the waiting cell, the track is held on
each side at that side's own position, and the console is READY again with no
homing move after it.

**What it does not cover, stated exactly.** A Start program goal that runs:
each cycle first spawns a work-piece through Gazebo (`program.part`), and this
rig has no Gazebo, so a run would fail there. The fakes serve no `Grasp`, and
their arms and carriages never move, so no program step past the first motion
could complete either. Those paths are the state machine's tests
(`cite_bringup/test/test_console_machine.py`, against a fake cell) and, on a
real cell, `./scripts/program`'s and `program_cycle`'s. Nothing here is
physical: the plan's far side is normalised to the plant's backend.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import unittest

from cite_bringup.plan import load
from cite_bringup.program.cell import state_topic
from cite_bringup.program.from_plan import target
from cite_bringup.program.home import arm_joints
from cite_bringup.readiness import console_announcement
from cite_interfaces.action import HomeRobot, RunProgram
from cite_interfaces.msg import ConsoleState, RobotState, TwinMode
from cite_interfaces.qos import LATCHED
from cite_interfaces.srv import ConfirmOperator, StartRobot, StopCell
import launch
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node as RclpyNode
import yaml

ZONE = "cell_b"

#: Every goal names its target (ADR-0072); this rig drives the twin.
TWIN = ConsoleState.TARGET_TWIN


def _run_goal() -> RunProgram.Goal:
    """One cycle at the program's own speed, on the twin."""
    return RunProgram.Goal(speed_scale=1.0, cycles=1, target=TWIN)


#: An odd base inside `DOMAIN_BAND`, offset from the paired rig's so that two
#: rigs run side by side do not share a domain.
BASE = 1 + 2 * ((os.getpid() + 17) % 50)
PLANT_DOMAIN = BASE
COUNTERPART_DOMAIN = BASE + 1

#: How long one assertion waits for what should already be on its way. Spun,
#: never slept: every wait ends the moment its condition holds.
SETTLE_S = 60.0

FAKE_SIDE = str(Path(__file__).resolve().parent / "fake_side.py")

# The paired rig's plan, both sides simulated: its own helper, imported from
# beside this file rather than restated here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
PLAN_PATH = importlib.import_module("test_twin_boundary_paired_launch")._paired_plan()
PLAN = load(PLAN_PATH)
CELL = target(PLAN)
#: The console's names, as the generated plan states them (ADR-0071).
NAMES = PLAN.console
ARM = CELL.arm.asset
_DOCUMENT = yaml.safe_load(PLAN_PATH.read_text())["plan"]
_TRACK = _DOCUMENT["controller_managers"][0]["track"]
TRACK, TRACK_JOINT = _TRACK["command_topic"], _TRACK["joint"]


#: The arm's joints, from its generated controller configuration: what the
#: start measures, and so what the fakes report.
ARM_JOINTS = arm_joints(CELL.arm)


def _side(name: str, domain: int, offset: float) -> ExecuteProcess:
    return ExecuteProcess(
        cmd=[
            sys.executable,
            FAKE_SIDE,
            "--side", name,
            "--zone", ZONE,
            "--assets", ARM,
            "--offset", str(offset),
            "--track-topic", TRACK,
            "--track-joint", TRACK_JOINT,
            "--joints", ",".join(ARM_JOINTS),
        ],
        additional_env={"ROS_DOMAIN_ID": str(domain)},
        output="screen",
        name=f"fake_{name}",
    )


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    os.environ["CITE_DOMAIN_BASE"] = str(BASE)
    os.environ["ROS_DOMAIN_ID"] = str(PLANT_DOMAIN)
    os.environ.pop("CITE_ALLOW_HARDWARE", None)
    plant = _side("plant", PLANT_DOMAIN, 0.25)
    counterpart = _side("counterpart", COUNTERPART_DOMAIN, 0.75)
    boundary = Node(
        package="cite_twin",
        executable="twin_boundary.py",
        name="twin_boundary",
        arguments=["--plan", str(PLAN_PATH), "--sides", "all"],
        output="screen",
    )
    console = Node(
        package="cite_bringup",
        executable="cell_console.py",
        # No `name`: a node-name remap reaches every node in the process,
        # and the console creates one per request for the cell it drives.
        arguments=["--zone", ZONE, "--plan", str(PLAN_PATH), "--sides", "all"],
        output="screen",
    )
    return (
        launch.LaunchDescription(
            [plant, counterpart, boundary, console, launch_testing.actions.ReadyToTest()]
        ),
        {"plant": plant, "counterpart": counterpart, "console": console},
    )


class TestTheConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode("console_test")
        cls.states: list[ConsoleState] = []
        cls.node.create_subscription(ConsoleState, NAMES.state, cls.states.append, LATCHED)
        # The arm's custody, which Start robot reads: an empty gripper, latched
        # on the plant's domain where a skill server would publish it.
        cls.custody = cls.node.create_publisher(RobotState, state_topic(CELL.arm), LATCHED)
        cls.custody.publish(RobotState(gripper_holding=False))
        cls.start_robot = cls.node.create_client(StartRobot, NAMES.start_robot)
        cls.confirm_operator = cls.node.create_client(ConfirmOperator, NAMES.confirm_operator)
        cls.stop = cls.node.create_client(StopCell, NAMES.stop)
        cls.home = ActionClient(cls.node, HomeRobot, NAMES.home)
        cls.run_program = ActionClient(cls.node, RunProgram, NAMES.run_program)

    @classmethod
    def tearDownClass(cls):
        cls.home.destroy()
        cls.run_program.destroy()
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, what: str, timeout_s: float = SETTLE_S):
        deadline = self.node.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.05)
            value = predicate()
            if value:
                return value
        self.fail(f"{what} did not happen within {timeout_s:g} s")

    def _call(self, client, request):
        self.assertTrue(
            client.wait_for_service(timeout_sec=SETTLE_S), f"{client.srv_name} never served"
        )
        future = client.call_async(request)
        self._spin_until(future.done, f"{client.srv_name} answered", 2 * SETTLE_S)
        return future.result()

    def _send(self, client, goal, feedback=None):
        self._spin_until(client.server_is_ready, f"{client._action_name} appeared")
        sent = client.send_goal_async(goal, feedback_callback=feedback)
        self._spin_until(sent.done, "the goal was answered")
        return sent.result()

    def _state(self, state: int, what: str) -> ConsoleState:
        return self._spin_until(
            lambda: self.states and self.states[-1].state == state and self.states[-1],
            what,
        )

    def test_the_console_announces_itself_once_served(self, proc_output):
        proc_output.assertWaitFor(
            expected_output=console_announcement(ZONE), stream="stdout", timeout=SETTLE_S
        )

    def test_the_console_refuses_starts_homes_and_is_stopped(self, proc_output):
        """One sequence, because the console's state is the subject: each step needs the last."""
        # The latched state reaches a late subscriber, and says what the plan does.
        first = self._spin_until(lambda: self.states and self.states[-1], "a ConsoleState")
        self.assertEqual(list(first.physical_sides), [])
        self._spin_until(
            lambda: self.states[-1].twin_mode != ConsoleState.TWIN_MODE_UNKNOWN,
            "the twin's mode in the console's state",
        )
        self.assertEqual(self.states[-1].twin_mode, TwinMode.MODE_SIM)
        self.assertEqual(self.states[-1].state, ConsoleState.NOT_STARTED)

        # Nothing but Start robot before it has succeeded.
        handle = self._send(self.home, HomeRobot.Goal(speed_scale=1.0, target=TWIN))
        self.assertFalse(handle.accepted, "Home was accepted before Start robot")
        # P-R01: the rejection carries no reason to its client; the state does,
        # and the state itself is unchanged.
        refused = self._spin_until(
            lambda: self.states
            and self.states[-1].last_error.startswith("refused: ")
            and self.states[-1],
            "the rejected goal's reason in the console's state",
        )
        self.assertIn("Start robot", refused.last_error)
        self.assertEqual(refused.state, ConsoleState.NOT_STARTED)
        handle = self._send(self.run_program, _run_goal())
        self.assertFalse(handle.accepted, "Start program was accepted before Start robot")
        self.assertFalse(self._call(self.confirm_operator, ConfirmOperator.Request()).success)
        self.assertFalse(self._call(self.stop, StopCell.Request()).success)

        # Start robot: nothing physical to initialize; custody read, empty.
        response = self._call(self.start_robot, StartRobot.Request())
        self.assertTrue(response.success, response.detail)
        ready = self._state(ConsoleState.READY, "READY after Start robot")
        self.assertTrue(ready.robot_started)
        # Not at the program's start until a Home says so: Start program is refused.
        self.assertFalse(ready.plant_at_start or ready.counterpart_at_start)
        # ADR-0072: both sides run and are simulated, so every target is offered.
        self.assertEqual(
            list(ready.available_targets),
            [ConsoleState.TARGET_SIM, ConsoleState.TARGET_REAL, ConsoleState.TARGET_TWIN],
        )
        self.assertEqual(ready.prompt, "")
        self.assertEqual(ready.minimum_speed_scale, 0.0)
        self.assertFalse(
            self._send(self.run_program, _run_goal()).accepted
        )

        # The scale and the cycle count are refused at the goal, never defaulted.
        for goal in (
            RunProgram.Goal(speed_scale=0.0, cycles=1, target=TWIN),
            RunProgram.Goal(speed_scale=1.5, cycles=1, target=TWIN),
            RunProgram.Goal(speed_scale=1.0, cycles=0, target=TWIN),
        ):
            self.assertFalse(self._send(self.run_program, goal).accepted, str(goal))
        self.assertFalse(self._send(self.home, HomeRobot.Goal()).accepted)
        # R-18: a goal with no target is rejected, and the state says why.
        self.assertFalse(self._send(self.home, HomeRobot.Goal(speed_scale=1.0)).accepted)
        self._spin_until(
            lambda: "no target was sent" in self.states[-1].last_error,
            "the missing target named in the console's state",
        )

        # Home, through the boundary, until the fake carriage that never moves.
        steps: list[str] = []
        handle = self._send(
            self.home,
            HomeRobot.Goal(speed_scale=1.0, target=TWIN),
            feedback=lambda message: steps.append(message.feedback.step),
        )
        self.assertTrue(handle.accepted)
        self._spin_until(
            lambda: any("slide the track" in step for step in steps),
            "Home reached its track slide",
        )
        self.assertTrue(any("not at the program's start" in step for step in steps), steps)
        busy = self._state(ConsoleState.HOMING, "HOMING while the slide waits")
        self.assertTrue(busy.busy)
        self.assertEqual(busy.speed_scale, 1.0)
        # Both fakes answered the first move, through the twin.
        # (A fake reads `<plant>:<counterpart>` behaviours off the pose name, so
        # `zero` is the plant's word and the counterpart's half is "succeed".)
        for side, behaviour in (("plant", "zero"), ("counterpart", "succeed")):
            proc_output.assertWaitFor(
                expected_output=f"{side}: accepted /cite/{ZONE}/{ARM}/move_to as {behaviour}",
                stream="stdout",
                timeout=SETTLE_S,
            )
        # A second motion goal is refused while one runs.
        self.assertFalse(
            self._send(self.run_program, _run_goal()).accepted
        )

        # Cancel: the same software stop as StopCell.
        cancel = handle.cancel_goal_async()
        self._spin_until(cancel.done, "the cancel was answered")
        result_future = handle.get_result_async()
        self._spin_until(result_future.done, "Home ended after its cancel")
        result = result_future.result().result
        self.assertFalse(result.success)
        self.assertIn("stopped", result.detail)
        # Each carriage held where IT stands, never sent the plant's position.
        for side, offset in (("plant", 0.25), ("counterpart", 0.75)):
            proc_output.assertWaitFor(
                expected_output=f"{side}: track [{offset}, {offset}]",
                stream="stdout",
                timeout=SETTLE_S,
            )
        after = self._state(ConsoleState.READY, "READY after the cancel")
        self.assertTrue(after.robot_started)
        self.assertFalse(after.busy)
        self.assertFalse(after.plant_at_start or after.counterpart_at_start)
        self.assertEqual(after.last_error, "")
        self.assertTrue(any(state.state == ConsoleState.STOPPING for state in self.states))
        # And no homing move followed the stop (ADR-0037): the first move was
        # the only one either side was sent.
        text = "".join(
            entry.text.decode(errors="replace") if isinstance(entry.text, bytes) else entry.text
            for entry in proc_output
        )
        self.assertEqual(text.count(f"plant: accepted /cite/{ZONE}/{ARM}/move_to"), 1)
