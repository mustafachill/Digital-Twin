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

"""The boundary of an operator console's pair, whose real arm comes and goes (ADR-0077).

The shipped plan, whose counterpart is the physical xArm 5, with the hardware
opt-in, and the real `twin_boundary.py` started with `--side-states stdin` -
its standard input a FIFO this test writes, as the pair supervisor writes its
pipe (`readiness.side_state_line`). The plant is a `fake_side.py`. The
counterpart is NOT a launch action: this test starts it, kills it and starts it
again itself - a `fake_side.py` with the plan's physical joints and a
`fake_deadman.py` whose state it sets - each on the counterpart's own domain.

What is shown, in one ordered run, because each step is the state the next one
starts from:

1. Waiting for the robot: the counterpart is expected and not running, and REAL
   is refused naming why.
2. Connecting, then up and HELD (ADR-0076): running, held, not commandable, and
   REAL refused because the arm is held until Start robot.
3. Released (the fake deadman HEALTHY with the arm enabled): commandable, and
   REAL accepted.
4. A goal in flight to the counterpart when it is killed and reported down:
   the goal ENDS - a HARDWARE_FAULT, never a hang - the side leaves running and
   commandable, and the MODE FALLS TO SIM by itself (S-01), published.
5. Started again and up: held again, so REAL is refused again. Released, the
   mode is still SIM: a goal reaches the plant alone, until SetMode(REAL)
   measures this incarnation's readiness and is accepted.
6. The end of the supervisor's input, in REAL: the side is down, failing
   closed, and the mode falls to SIM again.

Nothing here is a robot: the "physical" side is two Python processes.
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest

from ament_index_python.packages import get_package_prefix
from cite_bringup.plan import COUNTERPART_SIDE, default_plan_path, load, resolve_domain_id
from cite_bringup.readiness import (
    SIDE_CONNECTING,
    SIDE_DOWN,
    side_state_line,
    SIDE_UP,
    SIDE_WAITING,
)
from cite_interfaces.action import MoveTo
from cite_interfaces.msg import ResultCode, TwinMode, TwinSides
from cite_interfaces.qos import LATCHED
from cite_interfaces.srv import SetMode
import launch
from launch.actions import ExecuteProcess
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node as RclpyNode

ZONE = "cell_b"
ASSET = "picker"
MOVE_TO = f"/cite/twin/{ZONE}/{ASSET}/move_to"

#: Odd, inside `DOMAIN_BAND`, apart from the other rigs' by its own offset.
BASE = 1 + 2 * ((os.getpid() + 19) % 50)

SETTLE_S = 30.0

HERE = Path(__file__).resolve().parent
FAKE_SIDE = str(HERE / "fake_side.py")
FAKE_DEADMAN = str(HERE / "fake_deadman.py")
PLAN_PATH = default_plan_path(ZONE)
PLAN = load(PLAN_PATH)
PLANT_DOMAIN = resolve_domain_id(PLAN, "plant", BASE)
COUNTERPART_DOMAIN = resolve_domain_id(PLAN, COUNTERPART_SIDE, BASE)
MANAGER = PLAN.controller_managers[0]
PHYSICAL = MANAGER.physical_on(COUNTERPART_SIDE)
TRACK, TRACK_JOINT = MANAGER.track.command_topic, MANAGER.track.joint
ARM_JOINTS = [joint for joint in PHYSICAL.joints if joint != TRACK_JOINT]

#: The FIFO the boundary reads as its standard input, and the file the fake
#: deadman reads its state from. Made at import, so both the launch description
#: and the test class can name them.
WORK = Path(tempfile.mkdtemp(prefix="cite_hot_plug_"))
STATES = WORK / "states"
DEADMAN = WORK / "deadman"
os.mkfifo(STATES)


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    os.environ["CITE_DOMAIN_BASE"] = str(BASE)
    os.environ["ROS_DOMAIN_ID"] = str(PLANT_DOMAIN)
    plant = ExecuteProcess(
        cmd=[
            sys.executable, FAKE_SIDE, "--side", "plant", "--zone", ZONE, "--assets", ASSET,
            "--offset", "0.0", "--track-topic", TRACK, "--track-joint", TRACK_JOINT,
        ],
        additional_env={"ROS_DOMAIN_ID": str(PLANT_DOMAIN)},
        output="screen",
        name="fake_plant",
    )
    program = Path(get_package_prefix("cite_twin")) / "lib" / "cite_twin" / "twin_boundary.py"
    boundary = ExecuteProcess(
        cmd=[
            "bash", "-c",
            f"exec {program} --plan {PLAN_PATH} --sides all --side-states stdin < {STATES}",
        ],
        # The opt-in a REAL transition asks for (ADR-0054); no address is set
        # or needed - nothing here reaches a robot.
        additional_env={"CITE_ALLOW_HARDWARE": "1"},
        output="screen",
        name="twin_boundary",
    )
    return (
        launch.LaunchDescription([plant, boundary, launch_testing.actions.ReadyToTest()]),
        {"plant": plant, "boundary": boundary},
    )


class _Counterpart:
    """The physical side, faked: started, killed and started again by the test."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self._processes: list[subprocess.Popen] = []

    def start(self) -> None:
        DEADMAN.write_text("held")
        self.lines = []
        env = dict(os.environ)
        env["ROS_DOMAIN_ID"] = str(COUNTERPART_DOMAIN)
        for cmd in (
            [
                sys.executable, FAKE_SIDE, "--side", COUNTERPART_SIDE, "--zone", ZONE,
                "--assets", ASSET, "--offset", "0.0", "--joints", ",".join(ARM_JOINTS),
                "--track-topic", TRACK, "--track-joint", TRACK_JOINT,
            ],
            [
                sys.executable, FAKE_DEADMAN, "--asset", ASSET,
                "--state-topic", PHYSICAL.deadman_state_topic,
                "--controller-topic", PHYSICAL.arm_controller_state_topic,
                "--control", str(DEADMAN),
            ],
        ):
            process = subprocess.Popen(
                cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                start_new_session=True,
            )
            threading.Thread(target=self._read, args=(process,), daemon=True).start()
            self._processes.append(process)

    def _read(self, process: subprocess.Popen) -> None:
        for line in process.stdout:
            self.lines.append(line.rstrip("\n"))

    def kill(self) -> None:
        for process in self._processes:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        self._processes = []


class TestTheRealArmComesAndGoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode("twin_hot_plug_test")
        cls.set_mode = cls.node.create_client(SetMode, SetMode.Request.SERVICE)
        cls.move_to = ActionClient(cls.node, MoveTo, MOVE_TO)
        cls.sides: list[TwinSides] = []
        cls.subscription = cls.node.create_subscription(
            TwinSides, TwinSides.TOPIC, cls.sides.append, LATCHED
        )
        cls.modes: list[TwinMode] = []
        cls.mode_subscription = cls.node.create_subscription(
            TwinMode, TwinMode.TOPIC, cls.modes.append, LATCHED
        )
        cls.counterpart = _Counterpart()
        # Opened for writing once the boundary's shell opened it for reading.
        cls.states = open(STATES, "w")  # noqa: SIM115 - closed in step 6

    @classmethod
    def tearDownClass(cls):
        cls.counterpart.kill()
        if not cls.states.closed:
            cls.states.close()
        cls.move_to.destroy()
        cls.node.destroy_node()
        rclpy.shutdown()

    def _say(self, state: str) -> None:
        self.states.write(side_state_line(COUNTERPART_SIDE, state) + "\n")
        self.states.flush()

    def _spin_until(self, predicate, what: str, timeout_s: float = SETTLE_S):
        deadline = self.node.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.05)
            value = predicate()
            if value:
                return value
        latest = self.sides[-1] if self.sides else None
        self.fail(f"{what} did not happen within {timeout_s:g} s; last TwinSides {latest}")

    def _sides_until(self, predicate, what: str) -> TwinSides:
        return self._spin_until(
            lambda: self.sides[-1] if self.sides and predicate(self.sides[-1]) else None, what
        )

    def _mode_until(self, mode: int, what: str) -> TwinMode:
        return self._spin_until(
            lambda: self.modes[-1] if self.modes and self.modes[-1].mode == mode else None,
            what,
        )

    def _request(self, mode: int):
        self.assertTrue(self.set_mode.wait_for_service(timeout_sec=SETTLE_S))
        future = self.set_mode.call_async(SetMode.Request(mode=mode, reason="hot plug"))
        self._spin_until(future.done, f"SetMode({mode}) returned")
        return future.result()

    def test_the_real_arm_comes_and_goes(self, proc_output):
        # 1. Waiting for the robot.
        waiting = self._sides_until(
            lambda s: list(s.expected) == ["plant", COUNTERPART_SIDE], "the expected sides"
        )
        self.assertEqual(list(waiting.running), ["plant"])
        self.assertEqual(list(waiting.physical), [COUNTERPART_SIDE])
        self.assertIn("waiting for the robot", waiting.detail)
        refused = self._request(TwinMode.MODE_REAL)
        self.assertFalse(refused.accepted)
        self.assertIn("waiting for the robot", refused.result.detail)

        # 2. Connecting, then up and held.
        self.counterpart.start()
        self._say(SIDE_CONNECTING)
        self._sides_until(lambda s: COUNTERPART_SIDE in s.connecting, "connecting")
        self._say(SIDE_UP)
        held = self._sides_until(
            lambda s: COUNTERPART_SIDE in s.running and COUNTERPART_SIDE in s.held,
            "running and held",
        )
        self.assertNotIn(COUNTERPART_SIDE, held.commandable)
        refused = self._request(TwinMode.MODE_REAL)
        self.assertFalse(refused.accepted)
        self.assertIn("held until Start robot", refused.result.detail)

        # 3. Released: commandable by measurement, and REAL accepted.
        DEADMAN.write_text("healthy")
        self._sides_until(lambda s: COUNTERPART_SIDE in s.commandable, "commandable")
        accepted = self._request(TwinMode.MODE_REAL)
        self.assertTrue(accepted.accepted, accepted.result.detail)

        # 4. A goal in flight when the side goes away ends.
        self.assertTrue(self.move_to.wait_for_server(timeout_sec=SETTLE_S))
        goal = MoveTo.Goal()
        goal.named_configuration = ":hold"
        sent = self.move_to.send_goal_async(goal)
        handle = self._spin_until(lambda: sent.result() if sent.done() else None, "accepted")
        self.assertTrue(handle.accepted)
        self._spin_until(
            lambda: any("accepted" in line and "hold" in line for line in self.counterpart.lines),
            "the counterpart running the goal",
        )
        result = handle.get_result_async()
        self.counterpart.kill()
        self._say(SIDE_DOWN)
        self._say(SIDE_WAITING)
        self._spin_until(result.done, "the in-flight goal ending")
        self.assertEqual(result.result().result.result.code, ResultCode.HARDWARE_FAULT)
        self.assertIn("disconnected", result.result().result.result.detail)
        gone = self._sides_until(
            lambda s: COUNTERPART_SIDE not in s.running, "the side leaving running"
        )
        self.assertNotIn(COUNTERPART_SIDE, gone.commandable)
        # S-01: nobody asked for SIM; the side leaving took the mode there.
        fell = self._mode_until(TwinMode.MODE_SIM, "the mode falling to SIM")
        self.assertIn("stopped being up", fell.reason)

        # 5. Started again: it comes up held, and REAL is refused again.
        self.counterpart.start()
        self._say(SIDE_CONNECTING)
        self._say(SIDE_UP)
        self._sides_until(
            lambda s: COUNTERPART_SIDE in s.running and COUNTERPART_SIDE in s.held,
            "running and held again",
        )
        refused = self._request(TwinMode.MODE_REAL)
        self.assertFalse(refused.accepted)
        self.assertIn("held until Start robot", refused.result.detail)
        # Released, and still SIM: a goal reaches the plant alone.
        DEADMAN.write_text("healthy")
        self._sides_until(lambda s: COUNTERPART_SIDE in s.commandable, "commandable again")
        self.assertEqual(self.modes[-1].mode, TwinMode.MODE_SIM)
        sent = self.move_to.send_goal_async(MoveTo.Goal())
        handle = self._spin_until(lambda: sent.result() if sent.done() else None, "accepted")
        result = handle.get_result_async()
        self._spin_until(result.done, "the SIM goal ending")
        self.assertEqual(result.result().result.result.code, ResultCode.SUCCESS)
        self.assertFalse(
            any("accepted" in line for line in self.counterpart.lines),
            "a goal reached the new incarnation with no SetMode measuring it",
        )
        # SetMode measures THIS incarnation, and only then is REAL back.
        accepted = self._request(TwinMode.MODE_REAL)
        self.assertTrue(accepted.accepted, accepted.result.detail)

        # 6. The supervisor's input ends: down, failing closed, and out of REAL.
        self.states.close()
        self._sides_until(lambda s: COUNTERPART_SIDE not in s.running, "down at end of input")
        self._mode_until(TwinMode.MODE_SIM, "the mode falling to SIM at end of input")
        proc_output.assertWaitFor(
            expected_output="up -> down", stream="stderr", timeout=SETTLE_S
        )
