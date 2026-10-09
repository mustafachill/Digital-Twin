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
import time
import unittest

from cite_bringup.plan import COUNTERPART_ARTIFACT_KEYS, default_plan_path
from cite_bringup.readiness import boundary_announcement
from cite_bringup.track_command import move as track_move
from cite_interfaces.action import MoveTo, Pick
from cite_interfaces.msg import DivergenceMetrics, ResultCode, TwinMode
from cite_interfaces.qos import COMMAND, LATCHED, STATE
from cite_interfaces.srv import Holding, HoldMode, SetMode, TrackArrived
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
from std_msgs.msg import Float64
from trajectory_msgs.msg import JointTrajectory
import yaml

ZONE = "cell_b"
ASSET = "picker"
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


def _stdout(proc_output) -> str:
    """Everything every process has printed on stdout so far, as one string."""
    return "".join(
        entry.text.decode(errors="replace") if isinstance(entry.text, bytes) else entry.text
        for entry in proc_output
        if getattr(entry, "from_stdout", True)
    )


def _paired_plan() -> Path:
    """Return the zone's generated plan with every far side SIMULATED, written to a file.

    The mixed case is the other rig's. This read the generated plan of an
    UNPAIRED zone and appended a counterpart to it unconditionally, which was
    legal only because that zone was single and would have written two sides
    named `counterpart` on a paired one (`docs/open-work.md` #62). The zone is
    paired (ADR-0059), so the pairing is asserted of the generated plan rather
    than manufactured.

    **The far side is normalised, and that is the one edit.** Since ADR-0070 the
    shipped counterpart is the physical xArm 5, and this rig is about the
    boundary with a simulated far side — on a physical one every mode but `SIM`
    is refused, which `test_twin_boundary_launch.py` covers. So each manager's
    counterpart is set to the plant's backend and declaration, and the keys
    naming a differing counterpart's own files are dropped, exactly as the
    generator emits a pair whose sides load one backend (ADR-0048 clause 2).
    """
    document = yaml.safe_load(default_plan_path(ZONE).read_text())
    plan = document["plan"]
    assert [side["name"] for side in plan["sides"]] == ["plant", "counterpart"], (
        f"{ZONE}'s generated plan is not paired, so there is no far side to cross to"
    )
    for manager in plan["controller_managers"]:
        manager["counterpart_backend"] = manager["backend"]
        manager["counterpart_commands_physical_hardware"] = manager[
            "commands_physical_hardware"
        ]
        for key in COUNTERPART_ARTIFACT_KEYS:
            manager.pop(key, None)
    assert not any(
        manager["counterpart_commands_physical_hardware"]
        for manager in plan["controller_managers"]
    ), f"{ZONE}'s plant declares physical hardware; this rig is the simulated one"
    path = Path(tempfile.mkdtemp(prefix="cite_twin_paired_")) / f"{ZONE}_plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


PLAN_PATH = _paired_plan()

#: The first belt's command topic, as a side owns it, and the operator's twin
#: of it, which is where a fixed program sends a setpoint (ADR-0066).
BELT = yaml.safe_load(PLAN_PATH.read_text())["plan"]["conveyors"][0]["command_topic"]
TWIN_BELT = BELT.replace("/cite/", "/cite/twin/", 1)

#: The arm's track, as a side owns its command topic, and the operator's twin
#: of it (ADR-0067). Each fake side stands its carriage at its own offset.
_TRACK = yaml.safe_load(PLAN_PATH.read_text())["plan"]["controller_managers"][0]["track"]
TRACK, TRACK_JOINT = _TRACK["command_topic"], _TRACK["joint"]
TWIN_TRACK = TRACK.replace("/cite/", "/cite/twin/", 1)


def _side(name: str, domain: int, offset: float, custody: str) -> ExecuteProcess:
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
            "--belts",
            BELT,
            "--track-topic",
            TRACK,
            "--track-joint",
            TRACK_JOINT,
            # Each side's custody, latched on its own domain (R-01).
            "--custody",
            custody,
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
    plant = _side("plant", PLANT_DOMAIN, 0.25, "empty")
    counterpart = _side("counterpart", COUNTERPART_DOMAIN, 0.75, "holding")
    boundary = Node(
        package="cite_twin",
        executable="twin_boundary.py",
        name="twin_boundary",
        arguments=["--plan", str(PLAN_PATH), "--sides", "all"],
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
        cls.belt = cls.node.create_publisher(Float64, TWIN_BELT, COMMAND)
        cls.track = cls.node.create_publisher(JointTrajectory, TWIN_TRACK, COMMAND)
        cls.track_arrived = cls.node.create_client(
            TrackArrived, TrackArrived.Request.SERVICE
        )
        cls.hold_mode = cls.node.create_client(HoldMode, HoldMode.Request.SERVICE)
        cls.holding = cls.node.create_client(Holding, Holding.Request.SERVICE)

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

    def _request(self, mode: int, reason: str, force: bool = False, holder: str = ""):
        self.assertTrue(
            self.set_mode.wait_for_service(timeout_sec=SETTLE_S),
            f"{SetMode.Request.SERVICE} was never advertised",
        )
        request = SetMode.Request()
        request.mode = mode
        request.reason = reason
        request.force = force
        request.holder = holder
        future = self.set_mode.call_async(request)
        self._spin_until(future.done, f"SetMode({mode}) returned")
        return future.result()

    def _hold(self, action: int, holder: str, node: str = "", mode: int = 0):
        self.assertTrue(self.hold_mode.wait_for_service(timeout_sec=SETTLE_S))
        future = self.hold_mode.call_async(
            HoldMode.Request(action=action, holder=holder, node=node, mode=mode)
        )
        self._spin_until(future.done, f"HoldMode({action}, {holder}) returned")
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

    # --- S-01: a run's hold on the mode -------------------------------------

    def test_a_foreign_set_mode_is_refused_while_a_sim_run_holds_the_mode(self):
        """S-01: the race a SIM run had with another client, closed in the boundary.

        A run holds SIM; another client's SetMode(REAL) - forced or not - is
        refused and the mode stays SIM; the holder's own transitions are taken
        and carry the hold; only the holder releases it, and once it has, the
        same foreign request is accepted.
        """
        run = "paired-run"
        me = self.node.get_fully_qualified_name()
        self.assertTrue(self._request(TwinMode.MODE_SIM, "before the hold").accepted)
        taken = self._hold(HoldMode.Request.ACQUIRE, run, me, TwinMode.MODE_SIM)
        self.assertTrue(taken.accepted, taken.result.detail)
        try:
            for force in (False, True):
                foreign = self._request(TwinMode.MODE_REAL, "another client", force=force)
                self.assertFalse(foreign.accepted, f"force={force}")
                self.assertEqual(foreign.result.code, ResultCode.PRECONDITION_FAILED)
                self.assertIn("held by a run in progress", foreign.result.detail)
                self.assertEqual(foreign.current_mode, TwinMode.MODE_SIM)
            # A second run may not take the hold, nor release this one.
            other = self._hold(HoldMode.Request.ACQUIRE, "other-run", me, TwinMode.MODE_SIM)
            self.assertFalse(other.accepted)
            self.assertEqual(other.holder, run)
            self.assertFalse(self._hold(HoldMode.Request.RELEASE, "other-run").accepted)
            # The holder's own transition is taken, and carries the hold.
            own = self._request(TwinMode.MODE_REAL, "the run itself", holder=run)
            self.assertTrue(own.accepted, own.result.detail)
            again = self._request(TwinMode.MODE_VALIDATED, "another client")
            self.assertFalse(again.accepted, "the hold moved with the holder to REAL")
            self.assertIn("held by a run in progress", again.result.detail)
            # S2-05: SIM, the safe direction, is never refused by a hold; the
            # hold stays with its holder, now on SIM.
            back = self._request(TwinMode.MODE_SIM, "another client")
            self.assertTrue(back.accepted, back.result.detail)
            self.assertEqual(back.current_mode, TwinMode.MODE_SIM)
            still = self._request(TwinMode.MODE_REAL, "another client, still held")
            self.assertFalse(still.accepted, "the hold stayed with its holder on SIM")
            self.assertIn("held by a run in progress", still.result.detail)
            self.assertTrue(
                self._request(TwinMode.MODE_SIM, "the run ends", holder=run).accepted
            )
        finally:
            released = self._hold(HoldMode.Request.RELEASE, run)
        self.assertTrue(released.accepted, released.result.detail)
        self.assertEqual(released.holder, "")
        after = self._request(TwinMode.MODE_REAL, "another client, after the run")
        self.assertTrue(after.accepted, after.result.detail)
        self.assertTrue(self._request(TwinMode.MODE_SIM, "back to SIM").accepted)

    def test_a_hold_is_not_taken_on_a_mode_that_is_not_in_force(self):
        """A run holds the mode it checked, or nothing (S-01)."""
        self.assertTrue(self._request(TwinMode.MODE_SIM, "SIM first").accepted)
        me = self.node.get_fully_qualified_name()
        refused = self._hold(HoldMode.Request.ACQUIRE, "late-run", me, TwinMode.MODE_REAL)
        self.assertFalse(refused.accepted)
        self.assertEqual(refused.holder, "")
        self.assertEqual(refused.mode, TwinMode.MODE_SIM)

    def test_a_hold_lapses_once_its_holders_node_leaves_the_graph(self):
        """S-01: a dead client cannot lock the twin for good; the mode is left alone."""
        from cite_twin.hold import UNSEEN_CEILING_S

        self.assertTrue(self._request(TwinMode.MODE_SIM, "SIM first").accepted)
        holder = rclpy.create_node(f"hold_holder_{os.getpid()}")
        try:
            taken = self._hold(
                HoldMode.Request.ACQUIRE,
                "dying-run",
                holder.get_fully_qualified_name(),
                TwinMode.MODE_SIM,
            )
            self.assertTrue(taken.accepted, taken.result.detail)
            refused = self._request(TwinMode.MODE_REAL, "while the holder lives")
            self.assertFalse(refused.accepted)
        finally:
            holder.destroy_node()
        # Gone from the graph: within the ceiling and a discovery's margin the
        # hold lapses, and the same request is then taken.
        # Asked at most every half second: each refusal is a line in the log.
        last = [0.0]

        def lapsed() -> bool:
            if time.monotonic() - last[0] < 0.5:
                return False
            last[0] = time.monotonic()
            return self._request(TwinMode.MODE_REAL, "after the holder died").accepted

        accepted = self._spin_until(
            lapsed, "the dead holder's hold lapsed", timeout_s=UNSEEN_CEILING_S + SETTLE_S
        )
        self.assertTrue(accepted)
        self.assertTrue(self._request(TwinMode.MODE_SIM, "back to SIM").accepted)

    # --- R-01: each side's custody, read by the boundary on its own domain ----

    def test_each_sides_custody_is_answered_by_the_boundary(self):
        """R-01: the counterpart's custody is read on its domain by L5, not by a client."""
        self.assertTrue(self.holding.wait_for_service(timeout_sec=SETTLE_S))

        def asked():
            future = self.holding.call_async(Holding.Request())
            self._spin_until(future.done, "Holding returned")
            answer = future.result()
            return answer if all(answer.heard) else None

        answer = self._spin_until(asked, "both sides' custody was heard")
        by_side = dict(zip(answer.sides, zip(answer.heard, answer.holding, answer.detail)))
        self.assertEqual(set(by_side), {"plant", "counterpart"})
        self.assertFalse(by_side["plant"][1])
        self.assertTrue(by_side["counterpart"][1])
        self.assertIn("counterpart_part", by_side["counterpart"][2])
        # Asked for one side, answered for that one side.
        future = self.holding.call_async(Holding.Request(sides=["counterpart"]))
        self._spin_until(future.done, "Holding(counterpart) returned")
        self.assertEqual(list(future.result().sides), ["counterpart"])

    def test_the_boundary_announces_itself_on_stdout(self, proc_output):
        """ADR-0057's promotion clause 1: the mechanism a pair supervisor joins on.

        **On stdout and not through the logger**, which is why this assertion
        can exist at all: `rcutils` writes every severity to stderr, and the
        helper above records three assertions in this file that failed silently
        because they looked in the wrong stream.

        What the line means is stronger than "the process started": it is
        printed from a callback the plant's executor ran, so the endpoints
        asserted on throughout this class are being served by the time it
        appears. Asserted here beside a `SetMode` call rather than alone,
        because the token's whole claim is about that server.
        """
        proc_output.assertWaitFor(
            expected_output=boundary_announcement(ZONE),
            stream="stdout",
            timeout=SETTLE_S,
        )
        self.assertTrue(
            self.set_mode.wait_for_service(timeout_sec=SETTLE_S),
            "the boundary announced and SetMode was never advertised",
        )

    def test_each_side_hears_the_heartbeat_on_its_own_domain(self, proc_output):
        """ADR-0070 item 5: the liveness a physical side's deadman stops on.

        Read from each fake's stdout, because each side is on a domain of its
        own and the counterpart's is one this process holds no context on. The
        zone is the plan's and the sequence advances — a heartbeat that repeats
        one sequence is not evidence the boundary is alive now, and the deadman
        does not count it.
        """
        for side in ("plant", "counterpart"):
            _wait_for_side(proc_output, f"{side}: heartbeat zone={ZONE}")
            _wait_for_side(proc_output, f"{side}: heartbeat advancing")

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
        """Watch the crossing itself, which is what this rig exists for.

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
        """Refuse a far side that threw, end to end.

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

    def test_a_belt_command_goes_to_the_sides_the_mode_routes(self, proc_output):
        """ADR-0066, ADR-0072: a belt setpoint follows the skills' routing table.

        SIM sends to the plant alone, REAL to the counterpart alone and
        VALIDATED to both. Each mode's value is distinct, so the side it must
        NOT have reached can be read from the same output its arrival is.
        """
        self._spin_until(
            lambda: self.node.count_subscribers(TWIN_BELT) > 0, "L5 subscribed to the belt"
        )
        for mode, value, reached, idle in (
            (TwinMode.MODE_SIM, 0.125, ("plant",), "counterpart"),
            (TwinMode.MODE_REAL, 0.375, ("counterpart",), "plant"),
            (TwinMode.MODE_VALIDATED, 0.25, ("plant", "counterpart"), None),
        ):
            response = self._request(mode, f"belt in mode {mode}")
            self.assertTrue(response.accepted, response.result.detail)
            command = Float64(data=value)
            for side in reached:
                self._spin_until(
                    lambda side=side: self.belt.publish(command)
                    or f"{side}: belt {BELT} {value:g}" in _stdout(proc_output),
                    f"the belt command in mode {mode} reached the {side}",
                )
            if idle is not None:
                self.assertNotIn(
                    f"{idle}: belt {BELT} {value:g}",
                    _stdout(proc_output),
                    f"a belt command crossed to the idle {idle} in mode {mode}",
                )
        self.assertTrue(self._request(TwinMode.MODE_SIM, "resetting").accepted)

    def test_a_goal_reaches_exactly_the_sides_its_mode_commands(self, proc_output):
        """ADR-0072: SIM reaches the plant only, REAL the counterpart only, VALIDATED both.

        In SIM nothing reaches the far side: that is the premise of asking a
        person into the cell (SA-S-05), and it is now the routing table itself.
        Each mode's goal carries its own word, so a side it must not reach is
        read as the absence of that word on that side's output. The counterpart
        is simulated here, so REAL is entered without the hardware opt-in.
        """
        for mode, word, reached, idle in (
            (TwinMode.MODE_SIM, "insim", ("plant",), "counterpart"),
            (TwinMode.MODE_REAL, "inreal", ("counterpart",), "plant"),
            (TwinMode.MODE_VALIDATED, "intwin", ("plant", "counterpart"), None),
        ):
            response = self._request(mode, f"a goal in mode {mode}")
            self.assertTrue(response.accepted, response.result.detail)
            result = self._result_of(
                self._send(self.move_to, self._move_to(f"{word}:{word}"))
            )
            self.assertEqual(result.result.code, ResultCode.SUCCESS, result.result.detail)
            for side in reached:
                _wait_for_side(proc_output, f"{side}: accepted {MOVE_TO_ON_A_SIDE} as {word}")
                self.assertIn(f"{side}:", result.result.detail)
            if idle is not None:
                self.assertNotIn(
                    f"{idle}: accepted {MOVE_TO_ON_A_SIDE} as {word}", _stdout(proc_output)
                )
                self.assertNotIn(f"{idle}:", result.result.detail)
        self.assertTrue(self._request(TwinMode.MODE_SIM, "resetting").accepted)

    def test_a_track_move_reaches_only_the_side_a_single_side_mode_commands(
        self, proc_output
    ):
        """ADR-0072: a track command in SIM moves the plant's carriage, in REAL the far one."""
        self._spin_until(
            lambda: self.track.get_subscription_count() > 0, "the boundary's track endpoint"
        )
        for mode, start, reached, idle in (
            (TwinMode.MODE_SIM, 0.0, "plant", "counterpart"),
            (TwinMode.MODE_REAL, 0.875, "counterpart", "plant"),
        ):
            response = self._request(mode, f"a track move in mode {mode}")
            self.assertTrue(response.accepted, response.result.detail)
            self.track.publish(track_move(TRACK_JOINT, start, 0.5, 2.5))
            _wait_for_side(proc_output, f"{reached}: track [{start}, 0.5]")
            self.assertNotIn(f"{idle}: track [{start}, 0.5]", _stdout(proc_output))
        self.assertTrue(self._request(TwinMode.MODE_SIM, "resetting").accepted)

    def test_a_belt_stop_crosses_in_every_mode(self, proc_output):
        """ADR-0066: a zero setpoint is never gated, and leaving a mode stops its belts.

        Counted as exact lines, because `0` is a prefix of every other value
        this class sends. VALIDATED -> SIM must send exactly one zero to the
        counterpart, which SIM no longer commands, and none to the plant, which
        SIM still commands (ADR-0072); only then is an operator's zero sent in
        SIM, which reaches both sides, the counterpart included.
        """
        def zeros(side: str) -> int:
            line = f"{side}: belt {BELT} 0"
            return sum(1 for text in _stdout(proc_output).splitlines() if text == line)

        sides = ("plant", "counterpart")
        self._spin_until(
            lambda: self.node.count_subscribers(TWIN_BELT) > 0, "L5 subscribed to the belt"
        )
        self._enter_validated()
        before = {side: zeros(side) for side in sides}
        self.assertTrue(self._request(TwinMode.MODE_SIM, "leaving VALIDATED").accepted)
        self._spin_until(
            lambda: zeros("counterpart") == before["counterpart"] + 1,
            "leaving VALIDATED stopped the counterpart's belt",
        )
        self.assertEqual(zeros("plant"), before["plant"], "SIM still commands the plant")
        stop = Float64(data=0.0)
        for side, at_least in (("plant", 1), ("counterpart", 2)):
            self._spin_until(
                lambda side=side, at_least=at_least: self.belt.publish(stop)
                or zeros(side) >= before[side] + at_least,
                f"a stop sent in SIM reached the {side}",
            )

    def test_a_track_move_reaches_both_sides_unchanged(self, proc_output):
        """One signal, both carriages: the identical message, start point included."""
        self._enter_validated()
        self._spin_until(
            lambda: self.track.get_subscription_count() > 0, "the boundary's track endpoint"
        )
        self.track.publish(track_move(TRACK_JOINT, 0.125, 0.375, 2.5))
        _wait_for_side(proc_output, "plant: track [0.125, 0.375]")
        _wait_for_side(proc_output, "counterpart: track [0.125, 0.375]")

    def test_a_track_stop_holds_each_side_where_it_stands_in_every_mode(self, proc_output):
        """SA2c-S-02 a: never the plant's position sent to the counterpart's carriage.

        The plant stands at 0.25 and the counterpart at 0.75. A stop - a
        trajectory with no points - is answered with a hold at each side's OWN
        position, and it crosses in SIM, where nothing else does.
        """
        self._spin_until(
            lambda: self.track.get_subscription_count() > 0, "the boundary's track endpoint"
        )
        response = self._request(TwinMode.MODE_SIM, "a stop crosses in every mode")
        self.assertTrue(response.accepted, response.result.detail)
        # Re-sent until both holds are seen: the boundary holds only once it
        # has heard each side's carriage, which this process cannot observe.
        for _attempt in range(int(SETTLE_S / 0.5)):
            self.track.publish(JointTrajectory(joint_names=[TRACK_JOINT]))
            try:
                proc_output.assertWaitFor(
                    expected_output="counterpart: track [0.75, 0.75]", stream="stdout",
                    timeout=0.5,
                )
                break
            except AssertionError:
                continue
        else:
            self.fail("the counterpart was never held at its own position")
        _wait_for_side(proc_output, "plant: track [0.25, 0.25]")
        self.assertNotIn("counterpart: track [0.25, 0.25]", _stdout(proc_output))

    def _arrived(self, position_m: float, tolerance_m: float, sides=()):
        self.assertTrue(
            self.track_arrived.wait_for_service(timeout_sec=SETTLE_S),
            f"{TrackArrived.Request.SERVICE} was never advertised",
        )
        future = self.track_arrived.call_async(
            TrackArrived.Request(
                joint=TRACK_JOINT,
                position_m=position_m,
                tolerance_m=tolerance_m,
                sides=list(sides),
            )
        )
        self._spin_until(future.done, "TrackArrived returned")
        return future.result()

    def test_arrival_is_every_commanded_sides(self, proc_output):
        """SA2c-S-02 c: the plant at its target is not the pair at its target."""
        self._enter_validated()
        # Heard first: until then no side has a position at all.
        self._spin_until(
            lambda: "no track position" not in self._arrived(0.25, 0.001).detail,
            "the boundary heard both carriages",
        )
        at_plant = self._arrived(0.25, 0.001)
        self.assertFalse(at_plant.arrived)
        self.assertIn("counterpart: stands at 750.0 mm", at_plant.detail)
        self.assertNotIn("plant:", at_plant.detail)
        self.assertEqual(at_plant.reason, TrackArrived.Response.AWAY)
        self.assertTrue(at_plant.routed)
        self.assertTrue(self._arrived(0.5, 0.3).arrived)
        response = self._request(TwinMode.MODE_SIM, "no side commanded")
        self.assertTrue(response.accepted, response.result.detail)
        # In SIM the plant is the commanded side, and a track command is routed
        # to it alone (ADR-0072): the plant's carriage is asked about, and a
        # SIMULATED counterpart is not (only a physical side is judged there).
        in_sim = self._arrived(0.25, 0.001)
        self.assertTrue(in_sim.arrived, in_sim.detail)
        self.assertTrue(in_sim.routed)
        away = self._arrived(0.75, 0.001)
        self.assertFalse(away.arrived)
        self.assertIn("plant: stands at 250.0 mm", away.detail)
        # Named sides are judged alone, whatever the mode (ADR-0072): the
        # counterpart's own carriage, asked about in SIM.
        far = self._arrived(0.75, 0.001, sides=("counterpart",))
        self.assertTrue(far.arrived, far.detail)
        self.assertFalse(self._arrived(0.75, 0.001, sides=("plant",)).arrived)

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
        """Pair two operands, which no run and no test had ever done before this.

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

    def test_a_quiet_joint_publisher_ages_the_operand(self, proc_output):
        """R-05: partial joint states merge by name, and the oldest joint sets the age.

        Each fake publishes joint1, joint2 and joint3 from three publishers on
        one topic; joint3's goes quiet. Recorded per message, the operand would
        stay as fresh as the last publisher to speak; merged per joint, it ages
        with joint3, which is what a physical side whose track adapter died
        must look like to the monitor.
        """
        _wait_for_side(proc_output, "plant: joint3 publisher quiet")
        threshold_s = 2.0
        self._spin_until(
            lambda: any(
                sample.asset_id == ASSET and sample.plant_sample_age_s > threshold_s
                for sample in self.samples
            ),
            f"the plant operand aged past {threshold_s:g} s with joint3 quiet",
        )

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
        """Keep the stop path answering, as a property rather than a thread count.

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
