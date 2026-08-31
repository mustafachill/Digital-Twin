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

"""A goal crossing the twin boundary, watched from one side.

**THIS IS THE TEST FOUR DOCUMENTS SAID COULD NOT BE WRITTEN**, and the claim was
overstated rather than wrong. What they said is that `launch_test` with
`IncludeLaunchDescription` puts a cell's whole launch inside the test process,
which holds one context on one domain, so two sides cannot be included there —
true, and about that shape. This rig takes a different one, and this repository
already contains the proof that it works:
`docs/measurements/2026-08-28-second-world-cost/harness/mirror_latency.py` holds
two contexts on two domains in one process and carried 20,000 messages, and
ADR-0050 chose L5's mechanism from that rig.

**How this one is arranged.** Each side is a CHILD PROCESS with its own
`ROS_DOMAIN_ID` — `test/fake_side.py`, which serves an arm's L3 action names and
moves nothing. The test process holds one context, on the plant's domain, and
never opens a second, so it is not a cross-domain observer and needs no
carve-out (ADR-0044 clause 3). What the far side did is read from its **stdout**
through `launch_testing`'s `proc_output`, which is what a launch-process
supervisor is already permitted to observe.

**WHAT THIS RIG IS NOT.** It brings up no cell: no Gazebo, no controller
manager, no `move_group`, no arm. Nothing here is evidence about motion,
planning, grasping or timing, and no number taken here is a fidelity number
(P8). What it is evidence for is the boundary itself — that a goal dispatched
into `/cite/twin/...` arrives at each side's own server on that side's own
domain, that two operands reach the monitor, and that what the operator is told
about two sides is what the two sides said.

**The counterpart is simulated throughout**, which is what makes a transition
possible at all: on the mixed plan of `test_twin_boundary_launch.py` every mode
but `SIM` is refused, because entering it would place physical actuation under
an authority that was not commanding it.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

from cite_bringup.plan import default_plan_path
from cite_interfaces.action import MoveTo, Pick
from cite_interfaces.msg import DivergenceMetrics, ResultCode, TwinMode
from cite_interfaces.qos import LATCHED, STATE
from cite_interfaces.srv import SetMode
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

ZONE = "cell_a"
ASSET = "arm_1"
MOVE_TO = f"/cite/twin/{ZONE}/{ASSET}/move_to"
PICK = f"/cite/twin/{ZONE}/{ASSET}/pick"

#: The same skill under the name the SIDE serves it on, which is the name a
#: fake prints when a goal reaches it. The two differ only by the reserved
#: `/twin` scope, and that difference is the crossing.
MOVE_TO_ON_A_SIDE = f"/cite/{ZONE}/{ASSET}/move_to"

#: An odd base, so the counterpart at base + 1 is even and inside the band too —
#: the parity rule `scripts/_lib.sh` allocates by, applied to a process id so
#: that two runs of this test do not collide either.
#:
#: **It must land inside `cite_bringup.plan.DOMAIN_BAND`, which is 1..101**, and
#: the first version of this line did not: it started at 101 to keep clear of
#: the mixed rig's band, `resolve_domain_id` refused the counterpart at 102, and
#: the boundary exited 2 before serving anything — which this rig reported as
#: every assertion timing out rather than as a refusal, because a process that
#: never starts and a process that never answers look identical from a client.
BASE = 1 + 2 * ((os.getpid() + 1) % 50)
PLANT_DOMAIN = BASE
COUNTERPART_DOMAIN = BASE + 1

#: How long an assertion waits for a message that should already be on its way.
#: Spun rather than slept: every wait below ends the moment the condition holds.
SETTLE_S = 30.0

FAKE_SIDE = str(Path(__file__).resolve().parent / "fake_side.py")


def _wait_for_side(proc_output, line: str) -> None:
    """Wait for one line on a fake side's STDOUT.

    `stream="stdout"` is not the default and the omission is silent:
    `launch_testing.io_handler.waitFor` defaults to `stream='stderr'`, so an
    assertion about a `print()` times out saying "Waiting for output timed out"
    rather than saying it looked in the wrong stream. Three assertions in this
    file failed that way before the default was read upstream.
    """
    proc_output.assertWaitFor(
        expected_output=line, stream="stdout", timeout=SETTLE_S
    )


def _paired_plan() -> Path:
    """The generated plan, plus a counterpart the shipped model lacks.

    Every far side simulated. The mixed case is the other rig's.
    """
    document = yaml.safe_load(default_plan_path(ZONE).read_text())
    plan = document["plan"]
    plan["sides"].append(
        {
            "name": "counterpart",
            "gz_partition": f"cite/{ZONE}/counterpart",
            "domain_offset": 1,
        }
    )
    for manager in plan["controller_managers"]:
        manager["counterpart_backend"] = "sim"
    path = Path(tempfile.mkdtemp(prefix="cite_twin_paired_")) / f"{ZONE}_plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


PLAN_PATH = _paired_plan()


def _side(name: str, domain: int, offset: float) -> ExecuteProcess:
    return ExecuteProcess(
        cmd=[
            sys.executable,
            FAKE_SIDE,
            "--side",
            name,
            "--zone",
            ZONE,
            "--assets",
            ASSET,
            "--offset",
            str(offset),
        ],
        # The whole of the isolation, and the reason this rig can hold two
        # sides at once: each child process discovers only its own domain.
        additional_env={"ROS_DOMAIN_ID": str(domain)},
        output="screen",
        name=f"fake_{name}",
    )


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    os.environ["CITE_DOMAIN_BASE"] = str(BASE)
    os.environ["ROS_DOMAIN_ID"] = str(PLANT_DOMAIN)
    # No hardware anywhere in this plan, so the opt-in is not the subject here;
    # the gate has its own rig. Cleared anyway, so that a machine that happens
    # to export it does not change what this test means.
    os.environ.pop("CITE_ALLOW_HARDWARE", None)
    plant = _side("plant", PLANT_DOMAIN, 0.25)
    counterpart = _side("counterpart", COUNTERPART_DOMAIN, 0.75)
    boundary = Node(
        package="cite_twin",
        executable="twin_boundary.py",
        name="twin_boundary",
        arguments=["--plan", str(PLAN_PATH)],
        output="screen",
    )
    return (
        launch.LaunchDescription(
            [plant, counterpart, boundary, launch_testing.actions.ReadyToTest()]
        ),
        {"plant": plant, "counterpart": counterpart, "boundary": boundary},
    )


class TestAGoalCrossesTheBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode("twin_paired_test")
        cls.modes: list[TwinMode] = []
        cls.samples: list[DivergenceMetrics] = []
        cls.node.create_subscription(TwinMode, TwinMode.TOPIC, cls.modes.append, LATCHED)
        cls.node.create_subscription(
            DivergenceMetrics, DivergenceMetrics.TOPIC, cls.samples.append, STATE
        )
        cls.set_mode = cls.node.create_client(SetMode, SetMode.Request.SERVICE)
        cls.move_to = ActionClient(cls.node, MoveTo, MOVE_TO)
        cls.pick = ActionClient(cls.node, Pick, PICK)

    @classmethod
    def tearDownClass(cls):
        cls.move_to.destroy()
        cls.pick.destroy()
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

    def _request(self, mode: int, reason: str, force: bool = False):
        self.assertTrue(
            self.set_mode.wait_for_service(timeout_sec=SETTLE_S),
            f"{SetMode.Request.SERVICE} was never advertised",
        )
        request = SetMode.Request()
        request.mode = mode
        request.reason = reason
        request.force = force
        future = self.set_mode.call_async(request)
        self._spin_until(future.done, f"SetMode({mode}) returned")
        return future.result()

    def _enter_validated(self) -> None:
        response = self._request(TwinMode.MODE_VALIDATED, "driving the boundary")
        self.assertTrue(response.accepted, response.result.detail)

    def _send(self, client, goal, timeout_s: float = SETTLE_S):
        self._spin_until(client.server_is_ready, f"{client._action_name} appeared")
        sent = client.send_goal_async(goal)
        self._spin_until(sent.done, "the goal was answered", timeout_s)
        handle = sent.result()
        self.assertTrue(handle.accepted, "L5 rejected the goal")
        return handle

    def _result_of(self, handle, timeout_s: float = SETTLE_S):
        future = handle.get_result_async()
        self._spin_until(future.done, "the goal produced a result", timeout_s)
        return future.result().result

    @staticmethod
    def _move_to(behaviour: str) -> MoveTo.Goal:
        goal = MoveTo.Goal()
        goal.named_configuration = behaviour
        return goal

    # ------------------------------------------------------------------ #

    def test_an_accepted_transition_is_published(self):
        """Asserted here rather than on the mixed plan, where none is possible.

        Every mode but `SIM` is refused there, and correctly: entering one
        would place physical actuation under an authority that was not
        commanding it.
        """
        # Put the mode back first: `unittest` runs a class's methods in
        # alphabetical order, and a test that assumed the order would break the
        # moment one was renamed. Asking for the mode already in force is not a
        # transition and publishes nothing.
        self.assertTrue(self._request(TwinMode.MODE_SIM, "resetting").accepted)
        before = len(self.modes)
        self._enter_validated()
        self._spin_until(lambda: len(self.modes) > before, "the new mode was published")
        latest = self.modes[-1]
        self.assertEqual(latest.mode, TwinMode.MODE_VALIDATED)
        self.assertEqual(latest.reason, "driving the boundary")
        self.assertFalse(latest.transition_in_progress)

    def test_the_goal_reaches_both_sides_own_servers(self, proc_output):
        """**The crossing itself.**

        The operator's goal enters `/cite/twin/...` and each side's own L3 name
        answers it on that side's own domain. The counterpart's half is read
        from its stdout, because the test process holds no context there.
        """
        self._enter_validated()
        handle = self._send(self.move_to, self._move_to("succeed:succeed"))
        result = self._result_of(handle)
        self.assertEqual(result.result.code, ResultCode.SUCCESS, result.result.detail)
        for side in ("plant", "counterpart"):
            _wait_for_side(proc_output, f"{side}: accepted {MOVE_TO_ON_A_SIDE} as succeed")

    def test_the_operators_measurement_is_the_plants(self):
        """Two sides answer with two numbers; the aggregate carries one of them.

        The fakes report `position_error_m` equal to their own offset, so the
        value says which side's measurement was forwarded. An average would be
        0.5 and is a value neither side produced.
        """
        self._enter_validated()
        result = self._result_of(
            self._send(self.move_to, self._move_to("succeed:succeed"))
        )
        self.assertAlmostEqual(result.position_error_m, 0.25)
        self.assertEqual(result.reached.header.frame_id, "plant")
        self.assertIn("measurements are the plant's", result.result.detail)

    def test_a_far_side_that_threw_is_not_reported_as_a_success(self, proc_output):
        """**R-05, end to end.**

        rclpy catches an exception raised in an execute callback, aborts the
        goal and returns a DEFAULT-CONSTRUCTED result whose `ResultCode` is 0 —
        `SUCCESS`. L5 read success out of that payload and discarded the goal
        status, so a far side that threw was reported to the operator as a
        clean success with `holding=false` beside it.
        """
        self._enter_validated()
        result = self._result_of(
            self._send(self.move_to, self._move_to("succeed:throw"))
        )
        self.assertNotEqual(result.result.code, ResultCode.SUCCESS)
        self.assertEqual(result.result.code, ResultCode.EXECUTION_FAILED)
        self.assertIn("counterpart", result.result.detail)

    def test_an_interrupted_arm_is_not_reported_as_a_cancellation(self):
        """**S-05.** ADR-0037's ESCALATE row must reach the operator as itself.

        The plant is cancelled; the far side reports `MOTION_INTERRUPTED` — an
        arm stopped part-way and holding position. The old rule let `CANCELLED`
        outrank everything, so the operator was told the goal ended cleanly.
        """
        self._enter_validated()
        result = self._result_of(
            self._send(self.move_to, self._move_to("abort:abort"))
        )
        self.assertEqual(result.result.code, ResultCode.MOTION_INTERRUPTED)

    def test_a_successful_pick_never_reports_an_empty_gripper(self):
        """**S-02.** `Pick.action`: false with SUCCESS "is impossible"."""
        self._enter_validated()
        goal = Pick.Goal()
        goal.workpiece_id = "succeed:succeed"
        result = self._result_of(self._send(self.pick, goal))
        self.assertEqual(result.result.code, ResultCode.SUCCESS, result.result.detail)
        self.assertTrue(result.holding)

    def test_a_side_claiming_success_with_no_custody_is_refused(self):
        """L5 does not launder a contradiction in either direction."""
        self._enter_validated()
        goal = Pick.Goal()
        goal.workpiece_id = "empty:empty"
        result = self._result_of(self._send(self.pick, goal))
        self.assertEqual(result.result.code, ResultCode.EXECUTION_FAILED)
        self.assertIn("impossible", result.result.detail)

    def test_both_operands_reach_the_monitor(self):
        """**No operand had ever arrived, in any run or any test, until this one.**

        Both sides publish a joint state; L5 records each on its own context,
        stamps it on arrival and pairs the two. `valid` is still false, and for
        the one reason it is always false — the clock deficit has no instrument
        (ADR-0049) — so both ages being present is what this asserts, and no
        number here is a fidelity number: the two sides are the same fake.
        """
        self._enter_validated()
        sample = self._spin_until(
            lambda: next(
                (
                    sample
                    for sample in self.samples
                    if sample.asset_id == ASSET
                    and sample.plant_sample_age_s >= 0.0
                    and sample.counterpart_sample_age_s >= 0.0
                ),
                None,
            ),
            "a sample arrived with both operands present",
        )
        self.assertFalse(sample.valid, "the clock-deficit term has no instrument")
        self.assertTrue(sample.counterpart_observed)
        self.assertFalse(sample.far_side_physical)

    def test_a_transition_is_refused_while_a_goal_is_in_flight(self, proc_output):
        """**S-06.** The mode must not be published ahead of the state it describes.

        A held goal is outstanding on both sides. `SIM` means "physical idle,
        virtual commanded", and publishing it here would describe a cell that
        is not idle at all.
        """
        self._enter_validated()
        handle = self._send(self.move_to, self._move_to("hold:hold"))
        _wait_for_side(proc_output, f"counterpart: accepted {MOVE_TO_ON_A_SIDE} as hold")
        response = self._request(TwinMode.MODE_SIM, "trying to leave mid-goal")
        self.assertFalse(response.accepted, response.result.detail)
        self.assertEqual(response.result.code, ResultCode.PRECONDITION_FAILED)
        self.assertIn(MOVE_TO, response.result.detail)
        self.assertEqual(response.current_mode, TwinMode.MODE_VALIDATED)

        forced = self._request(TwinMode.MODE_SIM, "forcing it", force=True)
        self.assertFalse(forced.accepted, "no value of force may reach this refusal")

        # And the remedy the refusal names: cancel, then ask again.
        cancelled = handle.cancel_goal_async()
        self._spin_until(cancelled.done, "the cancel was answered")
        result = self._result_of(handle)
        self.assertEqual(result.result.code, ResultCode.CANCELLED)
        accepted = self._request(TwinMode.MODE_SIM, "nothing is in flight now")
        self.assertTrue(accepted.accepted, accepted.result.detail)

    def test_the_stop_path_answers_while_a_goal_is_in_flight(self, proc_output):
        """**R-01 / S-03, as a property rather than a thread count.**

        Every in-flight goal used to park a thread of the node's only executor
        pool, and the cancel that bounds a goal is itself executor work — so
        the bound was starved by the thing it was meant to bound. Two blocking
        handlers on a two-thread executor were measured serving 1 timer tick in
        3 s where 15 were due.

        Here three goals are held at once and the two endpoints that stop the
        twin — the mode service and the divergence timer — are required to keep
        answering. Three is more than the arms this rig serves; what matters is
        that the number is not what makes it work.
        """
        self._enter_validated()
        held = [
            self._send(self.move_to, self._move_to("hold:hold")) for _ in range(3)
        ]
        try:
            before = len(self.samples)
            self._spin_until(
                lambda: len(self.samples) - before >= 3,
                "the divergence timer kept publishing under load",
                timeout_s=10.0,
            )
            response = self._request(TwinMode.MODE_SIM, "the service still answers")
            self.assertFalse(response.accepted, "goals are in flight, so S-06 refuses")
            self.assertIn("still running", response.result.detail)
        finally:
            for handle in held:
                handle.cancel_goal_async()
            for handle in held:
                self._result_of(handle)


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_boundary_exits_cleanly(self, proc_info, boundary):
        """The fakes are killed by the launch teardown; L5 must exit on its own.

        Asserted for the boundary alone: a fake side killed with SIGTERM at
        teardown is the harness's doing and says nothing about the code under
        test. L5 keeps rclpy's ordinary SIGINT behaviour, so the signal it is
        stopped with is an allowed answer and a crash is not.
        """
        self.assertIn(proc_info[boundary].returncode, (0, -2, -15))
