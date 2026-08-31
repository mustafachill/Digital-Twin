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

"""The twin boundary as a running process, with neither side of the pair up.

**That is the case under test, not a limitation of the rig.** In Phase 2.A the
monitor's job is to publish samples that say why they cannot be read, and a
sample whose operands never arrive is the sharpest version of that: every
condition term is present, every comparison field is zeroed by the rule, and the
`valid` flag is false for reasons a reader can name.

WHAT THIS RIG CANNOT ANSWER, stated rather than left to be assumed. It brings up
no cell, so nothing here shows a goal reaching a far side's L3 server, a joint
state crossing the boundary, or a comparison over two real arms. **Nothing
automated can show those today**: `launch_test` puts the launch inside the test
process, which holds one context on one domain, so two sides cannot be included
in one, and `./scripts/scenario` addresses the plant (CLAUDE.md §2). A paired
scenario does not exist and ADR-0047 left whether one should open.

**The plan is fabricated and the shipped model is not paired.**
`model/facility/zones.yaml` declares `twin: {sides: single}` and ADR-0049
decision 4 keeps it there, so the generated plan has one side and L5 cannot come
up against it — a boundary needs two. This rig therefore reads the generated
plan and adds a counterpart to it, in memory, rather than editing L0. The
counterpart it adds is **mixed**: two simulated far sides and one physical one,
which is charter §8's planned state and the case
`cross-cutting-safety.md` insists is not an edge case. That is what lets the
hardware gate be exercised against the real `require_hardware_opt_in` rather
than against a stub.

**The domain is this process's, and only the plant's.** The test observes one
side, so it is not a cross-domain observer and needs no carve-out (ADR-0044
clause 3). The base is derived from this process's own id so that a run cannot
land on the domain of a cell somebody else is running from another checkout.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile
import unittest

from cite_bringup.plan import default_plan_path
from cite_interfaces.action import MoveTo
from cite_interfaces.msg import DivergenceMetrics, ResultCode, TwinMode
from cite_interfaces.qos import LATCHED, STATE
from cite_interfaces.srv import SetMode
from cite_twin.divergence import UNMEASURED
import launch
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node as RclpyNode
import yaml

#: The asset whose far side is physical in the fabricated plan.
PHYSICAL_ASSET = "arm_2"
PHYSICAL_BACKEND = "uf_robot_hardware"
SIMULATED_BACKEND = "sim"

#: An odd base in the band `cite_bringup.plan.DOMAIN_BAND` admits, so that the
#: counterpart at base + 1 is even and inside it too — the same parity rule
#: `scripts/_lib.sh` allocates by, applied to a process id instead of a path so
#: that two runs of this test do not collide either.
BASE = 1 + 2 * (os.getpid() % 50)
PLANT_DOMAIN = BASE

#: How long an assertion waits for a message that should already be on its way.
#: Spun rather than slept: every wait below is a loop over `spin_once` that ends
#: the moment the condition holds (P4).
SETTLE_S = 20.0


def _paired_plan() -> Path:
    """Write the generated plan, plus a counterpart the shipped model lacks."""
    document = yaml.safe_load(default_plan_path("cell_a").read_text())
    plan = document["plan"]
    plan["sides"].append(
        {
            "name": "counterpart",
            "gz_partition": "cite/cell_a/counterpart",
            "domain_offset": 1,
        }
    )
    for manager in plan["controller_managers"]:
        manager["counterpart_backend"] = (
            PHYSICAL_BACKEND if manager["asset"] == PHYSICAL_ASSET else SIMULATED_BACKEND
        )
    path = Path(tempfile.mkdtemp(prefix="cite_twin_plan_")) / "cell_a_plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


PLAN_PATH = _paired_plan()


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    # Set in this process so the child inherits it AND `rclpy.init()` below
    # lands on the same domain. The plant's offset is 0, so the plant's domain
    # is the base; L5 resolves both sides itself through the plan's offsets and
    # never reads either from this environment.
    os.environ["CITE_DOMAIN_BASE"] = str(BASE)
    os.environ["ROS_DOMAIN_ID"] = str(PLANT_DOMAIN)
    # Deliberately NOT set: CITE_ALLOW_HARDWARE. The gate under test is what
    # happens when it is absent.
    os.environ.pop("CITE_ALLOW_HARDWARE", None)
    return launch.LaunchDescription(
        [
            Node(
                package="cite_twin",
                executable="twin_boundary.py",
                name="twin_boundary",
                arguments=["--plan", str(PLAN_PATH)],
                output="screen",
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestTheTwinBoundary(unittest.TestCase):
    """One process, two contexts, three products."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = RclpyNode("twin_boundary_test")
        cls.modes: list[TwinMode] = []
        cls.samples: list[DivergenceMetrics] = []
        cls.node.create_subscription(
            TwinMode, TwinMode.TOPIC, cls.modes.append, LATCHED
        )
        cls.node.create_subscription(
            DivergenceMetrics, DivergenceMetrics.TOPIC, cls.samples.append, STATE
        )
        cls.set_mode = cls.node.create_client(SetMode, SetMode.Request.SERVICE)

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, what: str, timeout_s: float = SETTLE_S):
        deadline = self.node.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            value = predicate()
            if value:
                return value
        self.fail(f"{what} did not happen within {timeout_s:g} s")

    def _request(self, mode: int, reason: str, force: bool = False) -> SetMode.Response:
        self.assertTrue(
            self.set_mode.wait_for_service(timeout_sec=SETTLE_S),
            f"{SetMode.Request.SERVICE} was never advertised",
        )
        request = SetMode.Request()
        request.mode = mode
        request.reason = reason
        request.force = force
        future = self.set_mode.call_async(request)
        self._spin_until(lambda: future.done(), f"SetMode({mode}) returned")
        return future.result()

    def _reset_to_sim(self) -> None:
        """Put the mode back where a deployment starts.

        Called by every test that cares about the mode, because `unittest` runs
        the methods of a class in alphabetical order and a test that assumed the
        order would break the moment one was renamed.
        """
        response = self._request(TwinMode.MODE_SIM, "resetting between assertions")
        self.assertTrue(response.accepted, response.result.detail)

    # ------------------------------------------------------------------ #
    # 1. The mode server
    # ------------------------------------------------------------------ #

    def test_the_mode_is_published_latched_and_starts_in_sim(self):
        """A late joiner receives it immediately, which is what LATCHED buys."""
        self._spin_until(lambda: self.modes, "a TwinMode message arrived")
        first = self.modes[0]
        self.assertEqual(first.mode, TwinMode.MODE_SIM)
        self.assertEqual(first.requested_mode, TwinMode.MODE_SIM)
        self.assertFalse(first.transition_in_progress)
        self.assertEqual(first.asset_id, "", "mode is facility scope")
        self.assertNotEqual(first.reason, "")

    def test_a_transition_without_a_reason_is_refused(self):
        self._reset_to_sim()
        response = self._request(TwinMode.MODE_VALIDATED, "")
        self.assertFalse(response.accepted)
        self.assertEqual(response.result.code, ResultCode.PRECONDITION_FAILED)
        self.assertEqual(response.current_mode, TwinMode.MODE_SIM)

    def test_entering_virtual_lead_against_a_real_far_side_is_refused(self):
        """The real `require_hardware_opt_in`, applied at the transition.

        `CITE_ALLOW_HARDWARE` is unset and one asset's far side names a hardware
        backend, so this is the transition `SetMode.srv`'s header commits this
        server to refusing — and until this server existed, nothing refused it
        anywhere.
        """
        self._reset_to_sim()
        response = self._request(TwinMode.MODE_VIRTUAL_LEAD, "checking the gate")
        self.assertFalse(response.accepted)
        self.assertEqual(response.result.code, ResultCode.SAFETY_BLOCKED)
        self.assertIn(PHYSICAL_ASSET, response.result.detail)
        self.assertEqual(response.current_mode, TwinMode.MODE_SIM)

    def test_force_does_not_skip_it(self):
        self._reset_to_sim()
        response = self._request(TwinMode.MODE_VIRTUAL_LEAD, "forcing it", force=True)
        self.assertFalse(response.accepted)
        self.assertEqual(response.result.code, ResultCode.SAFETY_BLOCKED)

    def test_entering_validated_against_a_real_far_side_is_refused(self):
        """**This test asserted the bypass until 2026-08-31.**

        It read `assertTrue(response.accepted)`, and it passed: the gate was a
        transcribed list of three modes, `VALIDATED` was not in it, and
        `VALIDATED` dispatches the operator's goal to both sides by
        byte-identical code to `VIRTUAL_LEAD`'s. So on this very plan — one
        physical far side, `CITE_ALLOW_HARDWARE` unset —
        `SetMode(VIRTUAL_LEAD)` was refused `SAFETY_BLOCKED` and
        `SetMode(VALIDATED)` was accepted with no gate, after which a goal
        reached `arm_2`'s physical far side. A passing test is what checked it
        in.

        What an accepted transition looks like is now asserted where one is
        possible: `test_twin_boundary_paired_launch.py`, whose counterpart is
        simulated throughout.
        """
        self._reset_to_sim()
        response = self._request(TwinMode.MODE_VALIDATED, "measuring the instrument")
        self.assertFalse(response.accepted, response.result.detail)
        self.assertEqual(response.result.code, ResultCode.SAFETY_BLOCKED)
        self.assertIn(PHYSICAL_ASSET, response.result.detail)
        self.assertEqual(response.current_mode, TwinMode.MODE_SIM)

    def test_no_mode_but_sim_is_reachable_on_this_plan(self):
        """The criterion, at the point of transition, against every mode there is.

        Not a list of three: every mode this message declares commands the
        counterpart except `SIM`, and this plan's counterpart is physical for
        one asset — so on this deployment the gate refuses all five, and `SIM`
        is reachable because it is already in force.
        """
        self._reset_to_sim()
        modes = [
            getattr(TwinMode, name)
            for name in dir(TwinMode)
            if name.startswith("MODE_")
        ]
        self.assertGreaterEqual(len(modes), 6)
        for mode in modes:
            if mode == TwinMode.MODE_SIM:
                continue
            response = self._request(mode, "checking every row of the gate")
            self.assertFalse(response.accepted, f"mode {mode} was accepted")
            self.assertEqual(
                response.result.code, ResultCode.SAFETY_BLOCKED, f"mode {mode}"
            )
            self.assertEqual(response.current_mode, TwinMode.MODE_SIM)

    # ------------------------------------------------------------------ #
    # 2. Command routing
    # ------------------------------------------------------------------ #

    def test_the_operator_endpoint_is_served_and_the_side_name_is_not(self):
        """L5 advertises under `/cite/twin/` and nowhere else.

        The second half is the one worth having: the plant's own skill server is
        not running in this rig, so if anything answered on the side's own name
        it could only be L5 — which is the defect ADR-0050 decision 1 clause 3
        forbids.
        """
        twin = ActionClient(self.node, MoveTo, "/cite/twin/cell_a/arm_1/move_to")
        side = ActionClient(self.node, MoveTo, "/cite/cell_a/arm_1/move_to")
        try:
            self._spin_until(
                lambda: twin.server_is_ready(), "the twin MoveTo endpoint appeared"
            )
            for _ in range(20):
                rclpy.spin_once(self.node, timeout_sec=0.1)
            self.assertFalse(
                side.server_is_ready(),
                "something is serving the side's own MoveTo name; L5 may only "
                "advertise under /cite/twin/",
            )
        finally:
            twin.destroy()
            side.destroy()

    def test_a_goal_in_a_mode_with_no_command_flow_is_refused_with_a_code(self):
        """A refusal is an abort carrying a `ResultCode`, never a bare rejection.

        A rejected goal carries no result, so a caller would learn that the twin
        said no and never learn why.
        """
        self._reset_to_sim()
        client = ActionClient(self.node, MoveTo, "/cite/twin/cell_a/arm_1/move_to")
        try:
            self._spin_until(
                lambda: client.server_is_ready(), "the twin MoveTo endpoint appeared"
            )
            goal = MoveTo.Goal()
            goal.target.header.frame_id = "cite_world"
            sent = client.send_goal_async(goal)
            self._spin_until(lambda: sent.done(), "the goal was answered")
            handle = sent.result()
            self.assertTrue(handle.accepted)
            result = handle.get_result_async()
            self._spin_until(lambda: result.done(), "the goal produced a result")
            code = result.result().result.result
            self.assertEqual(code.code, ResultCode.PRECONDITION_FAILED)
            self.assertIn("SIM", code.detail)
        finally:
            client.destroy()

    # ------------------------------------------------------------------ #
    # 3. The divergence monitor
    # ------------------------------------------------------------------ #

    def test_a_sample_is_published_for_every_asset_and_none_of_them_is_valid(self):
        """The deliverable: self-describing invalid samples rather than silence.

        `valid` cannot be true here and could not be true against a running
        pair either — one of its terms is each side's clock deficit within a
        bound ADR-0049 leaves unset, and nothing measures it (ADR-0050 decision
        3). This asserts the shape of that answer, not a fidelity result: both
        sides of a 2.A pair run the same model, so no number here is one.
        """
        expected = {"arm_1", "arm_2", "arm_3"}
        self._spin_until(
            lambda: expected <= {sample.asset_id for sample in self.samples},
            "a divergence sample arrived for every asset",
        )
        for sample in self.samples:
            self.assertNotEqual(sample.asset_id, "", "there is no facility-level number")
            self.assertFalse(sample.valid)
            # The zeroing rule, applied to the two fields this monitor computes.
            self.assertEqual(sample.joint_error_rms_rad, 0.0)
            self.assertEqual(sample.joint_error_max_rad, 0.0)
            # And the OTHER rule, on the other axis: a field nothing computes
            # carries NaN in every sample. Zero here would be a measurement of
            # zero, and these four were never measured at all.
            self.assertTrue(math.isnan(sample.tcp_position_error_m))
            self.assertTrue(math.isnan(sample.tcp_orientation_error_rad))
            self.assertTrue(math.isnan(sample.cycle_time_deviation_s))
            self.assertTrue(math.isnan(sample.event_timing_deviation_s))
            # The far side is being watched, which is not the same claim as the
            # far side having published anything (it has not, in this rig).
            self.assertTrue(sample.counterpart_observed)
            # And NOT applied to the condition terms, which are how a reader
            # learns which conjunct failed.
            self.assertEqual(sample.plant_clock_deficit_s, UNMEASURED)
            self.assertEqual(sample.counterpart_clock_deficit_s, UNMEASURED)
            # Neither side is up, so neither operand ever arrived.
            self.assertEqual(sample.plant_sample_age_s, UNMEASURED)
            self.assertEqual(sample.counterpart_sample_age_s, UNMEASURED)

    def test_a_transition_is_refused_while_a_goal_l5_dispatched_is_running(self):
        """**S-06.** The mode must not be published ahead of the state it describes.

        This rig cannot hold a goal in flight — no side serves an L3 action, so
        every dispatch fails at `wait_for_server` — so what is asserted here is
        the other half: with nothing in flight, a transition is decided by the
        mode authority as before. The refusal itself is unit-tested against the
        function, and the paired rig drives a real in-flight goal.
        """
        self._reset_to_sim()
        response = self._request(TwinMode.MODE_VALIDATED, "nothing is in flight")
        self.assertFalse(response.accepted)
        self.assertEqual(response.result.code, ResultCode.SAFETY_BLOCKED)
        self.assertNotIn("still running", response.result.detail)

    def test_whether_the_far_side_is_physical_rides_with_the_sample(self):
        """The predicate that answers whether a number could ever be a fidelity one.

        Per asset, because whether a far side actuates hardware is a per-(asset,
        side) fact — which is also why there is no aggregate.
        """
        self._spin_until(
            lambda: {"arm_1", "arm_2", "arm_3"}
            <= {sample.asset_id for sample in self.samples},
            "a divergence sample arrived for every asset",
        )
        by_asset = {sample.asset_id: sample for sample in self.samples}
        self.assertTrue(by_asset[PHYSICAL_ASSET].far_side_physical)
        self.assertFalse(by_asset["arm_1"].far_side_physical)
        self.assertFalse(by_asset["arm_3"].far_side_physical)


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_process_exits_cleanly(self, proc_info):
        """L5 keeps rclpy's ordinary SIGINT behaviour rather than absorbing it.

        `cite_runtime`'s own adoption rule bars a process that commands an
        actuator from absorbing SIGINT, and L5 dispatches goals that move arms,
        so an operator's Ctrl-C reaches this process the way it reaches any
        other rclpy node.
        """
        launch_testing.asserts.assertExitCodes(proc_info)
