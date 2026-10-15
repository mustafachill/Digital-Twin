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

"""The deadman against a fake boundary and a fake vendor (ADR-0070 item 5, ADR-0076).

The test process is the boundary: it publishes `TwinHeartbeat` on the
contract's own topic, and stops. It also holds the vendor's `set_state`,
`set_mode` and `set_linear_motor_stop`, and a GripperCommand server whose goals
a trip must cancel. Nothing here reaches hardware.

The vendor's arm state is one value any client may set, and the fake lets the
test be that other client (UFACTORY Studio, the pendant): the property under
test is that whenever the deadman is not HEALTHY, the arm is put back to STOP
within a tick, whoever moved it.

A trip ends the deadman's process (ADR-0076 decision 5), so here the launch
RESPAWNS it, standing in for whatever starts a physical side again: each trip
is followed by its exit code, read on the launch's own process record, and by
a new deadman that the test configures and activates. On a physical side
nothing respawns the deadman alone; its exit takes the side down whole.

The cases are one sequence, in one method, because the property under test is a
sequence — awaiting, held, released, tripped, ended, started again — and
splitting it would make each part's precondition another part's side effect.
"""

from __future__ import annotations

import os
import signal
import sys
import unittest
import uuid

from action_msgs.msg import GoalStatus
from cite_hardware.deadman import EXIT_TRIPPED
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
from cite_interfaces.srv import ReleaseArm
from control_msgs.action import GripperCommand
import launch
from launch.events.process import ProcessExited, ProcessStarted
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.markers
import pytest
from rclpy.action import ActionClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import (  # noqa: E402
    FakeArmState,
    FakeBoundary,
    FakeGripper,
    FakeTrack,
    Harness,
    HOLD,
    SETTLE_S,
)

NODE = "deadman"
ZONE = "test_zone"
VENDOR = "/test_vendor/xarm"
STATE_TOPIC = "/test/deadman_state"
RELEASE = "/test/release"
GRIPPER_ACTION = "/test/gripper_controller/gripper_cmd"
TIMEOUT_S = 0.5
TICK_S = 0.05
CALL_DEADLINE_S = 0.3
#: Long enough that the test reads the exit before the respawn replaces it.
RESPAWN_DELAY_S = 1.0
STOP, START, SERVO = 4, 0, 1

PARAMETERS = {
    "zone": ZONE,
    "asset_id": "test_arm",
    "timeout_s": TIMEOUT_S,
    "tick_period_s": TICK_S,
    "call_deadline_s": CALL_DEADLINE_S,
    "state_topic": STATE_TOPIC,
    "release_service": RELEASE,
    "set_state_service": f"{VENDOR}/set_state",
    "set_mode_service": f"{VENDOR}/set_mode",
    "enable_mode": SERVO,
    "linear_motor_stop_service": f"{VENDOR}/set_linear_motor_stop",
    "cancel_actions": [GRIPPER_ACTION],
}

AWAITING = DeadmanState.STATE_AWAITING
HELD = DeadmanState.STATE_HELD
HEALTHY = DeadmanState.STATE_HEALTHY
TRIPPED = DeadmanState.STATE_TRIPPED


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    deadman = Node(
        package="cite_hardware",
        executable="deadman.py",
        name=NODE,
        parameters=[PARAMETERS],
        output="screen",
        respawn=True,
        respawn_delay=RESPAWN_DELAY_S,
    )
    return (
        launch.LaunchDescription([deadman, launch_testing.actions.ReadyToTest()]),
        {"deadman": deadman},
    )


class TestDeadman(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Harness("deadman_test")
        node = cls.harness.node
        cls.arm = FakeArmState(cls.harness, VENDOR)
        #: The one boundary of this zone, shared by every case in this file: a
        #: second publisher of it would itself be a rival boundary.
        cls.boundary = FakeBoundary(cls.harness, ZONE)
        cls.track = FakeTrack(cls.harness, VENDOR)
        cls.gripper = FakeGripper(cls.harness, GRIPPER_ACTION)
        cls.states: list[DeadmanState] = []
        node.create_subscription(DeadmanState, STATE_TOPIC, cls.states.append, LATCHED)
        cls.gripper_client = ActionClient(
            node, GripperCommand, GRIPPER_ACTION, callback_group=cls.harness.group
        )
        cls.release_client = node.create_client(
            ReleaseArm, RELEASE, callback_group=cls.harness.group
        )

    @classmethod
    def tearDownClass(cls):
        cls.gripper.release_held()
        cls.arm.release.set()
        cls.arm.mode_release.set()
        cls.gripper_client.destroy()
        cls.harness.close()

    def _state_is(self, state: int, what: str) -> DeadmanState:
        return self.harness.wait_for(
            lambda: self.states and self.states[-1].state == state and self.states[-1],
            what,
        )

    def _release(self) -> ReleaseArm.Response:
        return self.harness.call(self.release_client, ReleaseArm.Request(), "release answered")

    def _release_when_acknowledged(self) -> ReleaseArm.Response:
        """Release once the new deadman's first STOP is acknowledged (S-01).

        A release asked the instant HELD is heard may race the answer to the
        activation's STOP; that refusal, and only that one, is asked again.
        """
        def settled():
            answer = self._release()
            if answer.success or "acknowledged no STOP" not in answer.detail:
                return answer
            return None

        return self.harness.wait_for(settled, "a release past the first acknowledged STOP")

    def _hold_a_gripper_goal(self):
        self.gripper.hold_again()
        self.harness.wait_for(self.gripper_client.server_is_ready, "the fake gripper served")
        goal = GripperCommand.Goal()
        goal.command.max_effort = HOLD
        sent = self.gripper_client.send_goal_async(goal)
        self.harness.wait_for(sent.done, "the held goal accepted")
        return sent.result()

    def _undone_within_a_tick(self, what: str) -> None:
        """Another client starts the arm; the deadman puts it back to STOP."""
        self.arm.flip(START)
        self.harness.wait_for(lambda: self.arm.state == STOP, what)

    def _enabled(self, modes_before: int, what: str) -> None:
        """`set_mode(servo)` and then `set_state(0)`, in that order, once."""
        self.harness.wait_for(
            lambda: len(self.arm.modes) > modes_before and self.arm.state == START, what
        )
        calls = self.arm.calls
        last_mode = max(i for i, call in enumerate(calls) if call == ("set_mode", SERVO))
        self.assertIn(("set_state", START), calls[last_mode:], "set_state(0) after set_mode")

    def _released_and_enabled(self, what: str) -> None:
        self._state_is(HELD, f"HELD {what}")
        modes = len(self.arm.modes)
        response = self._release_when_acknowledged()
        self.assertTrue(response.success, response.detail)
        self._state_is(HEALTHY, f"HEALTHY on the release {what}")
        self._enabled(modes, f"the arm enabled on the release {what}")
        self.harness.wait_for(
            lambda: self.states[-1].state == HEALTHY and self.states[-1].arm_enabled,
            f"arm_enabled {what}",
        )

    def _ended_by_the_trip(self, proc_info, deadman, what: str) -> None:
        """Wait for the deadman's exit with EXIT_TRIPPED, then for the launch's new one."""
        self.harness.wait_for(
            lambda: isinstance(proc_info[deadman], ProcessExited)
            and proc_info[deadman].returncode == EXIT_TRIPPED,
            f"the deadman ended with code {EXIT_TRIPPED} {what}",
        )
        self.harness.wait_for(
            lambda: isinstance(proc_info[deadman], ProcessStarted),
            f"a new deadman started {what}",
            timeout_s=SETTLE_S + RESPAWN_DELAY_S,
        )

    def test_the_deadman_sequence(self, proc_output, proc_info, deadman):
        harness = self.harness
        wrong_zone = FakeBoundary(harness, "another_zone")
        boundary = self.boundary

        # 1. Active, nothing heard yet: AWAITING, the arm held at STOP however
        #    often another client starts it, a release refused, and never a trip.
        harness.bring_up(NODE)
        awaiting = self._state_is(AWAITING, "AWAITING after activation")
        self.assertFalse(awaiting.arm_enabled, "arm_enabled while AWAITING")
        harness.wait_for(lambda: self.arm.state == STOP, "set_state(4) on activation")
        self._undone_within_a_tick("a START by another client undone while AWAITING")
        refused = self._release()
        self.assertFalse(refused.success)
        self.assertIn("AWAITING", refused.detail)
        wrong_zone.beating.set()
        harness.hold_for(
            lambda: self.states[-1].state != AWAITING or self.arm.modes,
            "anything but AWAITING with only another zone's heartbeat",
            4 * TIMEOUT_S,
        )
        wrong_zone.beating.clear()
        wrong_zone.die()

        # 2. ADR-0076: the first heartbeat of its own zone HOLDS. The arm is
        #    sent STOP on every tick, never set_mode nor set_state(0), however
        #    long the heartbeats keep coming.
        boundary.beating.set()
        held = self._state_is(HELD, "HELD on the first heartbeat")
        self.assertEqual(held.asset_id, "test_arm")
        self.assertAlmostEqual(held.timeout_s, TIMEOUT_S)
        self.assertFalse(held.arm_enabled, "arm_enabled while HELD")
        stops = self.arm.requests.count(STOP)
        harness.hold_for(
            lambda: self.states[-1].state != HELD
            or self.arm.modes
            or ("set_state", START) in self.arm.calls,
            "anything but HELD, or an enable, on heartbeats alone",
            4 * TIMEOUT_S,
        )
        self.assertGreaterEqual(
            self.arm.requests.count(STOP), stops + 10, "set_state(4) on every tick while HELD"
        )
        self._undone_within_a_tick("a START by another client undone while HELD")

        # 3. The release - and nothing else - permits motion and enables the
        #    arm: set_mode, then set_state(0). A second release is refused.
        self._released_and_enabled("the first time")
        again = self._release()
        self.assertFalse(again.success)
        self.assertIn("already released", again.detail)
        stops = self.arm.requests.count(STOP)
        harness.hold_for(
            lambda: self.states[-1].state != HEALTHY or self.arm.requests.count(STOP) > stops,
            "a trip, or a STOP, while heartbeats arrive",
            4 * TIMEOUT_S,
        )

        # 4. The heartbeats stop after the release, with motion in flight: the
        #    trip stops everything, and then ENDS the process (decision 5).
        held_goal = self._hold_a_gripper_goal()
        cancels, track_stops = self.gripper.cancels, self.track.stops
        boundary.beating.clear()
        tripped = self._state_is(TRIPPED, "TRIPPED after the timeout")
        self.assertIn("no heartbeat within", tripped.detail)
        self.assertFalse(tripped.arm_enabled, "arm_enabled while TRIPPED")
        harness.wait_for(lambda: self.arm.state == STOP, "set_state(4), the vendor's stop")
        harness.wait_for(lambda: self.track.stops > track_stops, "set_linear_motor_stop")
        harness.wait_for(lambda: self.gripper.cancels > cancels, "every gripper goal cancelled")
        self._ended_by_the_trip(proc_info, deadman, "after a heartbeat loss once released")
        self.gripper.release_held()
        result = held_goal.get_result_async()
        harness.wait_for(result.done, "the held goal ended")
        self.assertIn(
            result.result().status,
            (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED),
        )

        # 5. A deadman started while the boundary is ALREADY beating - a
        #    restarted side - comes up HELD and never enables by itself.
        modes = len(self.arm.modes)
        boundary.beating.set()
        harness.bring_up(NODE)
        self._state_is(HELD, "HELD at once under a beating boundary")
        harness.hold_for(
            lambda: len(self.arm.modes) > modes or self.states[-1].state != HELD,
            "an enable, or a change of state, with no release",
            4 * TIMEOUT_S,
        )
        # A vendor that does not answer holds back nothing: the next ticks'
        # STOPs still arrive, and the unanswered one is abandoned.
        self.arm.release.clear()
        self.arm.hold_next.set()
        harness.wait_for(lambda: not self.arm.hold_next.is_set(), "a set_state held")
        answered = len(self.arm.requests)
        harness.wait_for(
            lambda: len(self.arm.requests) >= answered + 3,
            "set_state re-issued while an earlier one is unanswered",
        )
        proc_output.assertWaitFor(
            expected_output="set_state(4) unanswered within call_deadline_s; abandoned",
            timeout=SETTLE_S,
        )
        self.arm.release.set()

        # 6. HELD trips exactly as HEALTHY does. With the vendor refusing every
        #    STOP, the process still ends, at call_deadline_s after the trip.
        self.arm.failures = 10**6
        boundary.beating.clear()
        tripped = self._state_is(TRIPPED, "TRIPPED from HELD on a heartbeat loss")
        self.assertIn("no heartbeat within", tripped.detail)
        self._ended_by_the_trip(proc_info, deadman, "with every STOP refused")
        # S-03: an unacknowledged trip says the arm may still be enabled.
        proc_output.assertWaitFor(
            expected_output=(
                "the arm may remain enabled; check it in UFACTORY Studio before the next start"
            ),
            timeout=SETTLE_S,
        )
        self.arm.failures = 0
        self.assertEqual(len(self.arm.modes), modes, "an enable from HELD")

        # 7. Released again; the vendor refuses the first set_modes (N-06): the
        #    enable is retried on a later tick while HEALTHY, and only then is
        #    arm_enabled said; never sooner than ENABLE_RETRY_TICKS ticks after
        #    a failure, because each set_mode stops the arm (HW-S-04).
        boundary.beating.set()
        harness.bring_up(NODE)
        self._state_is(HELD, "HELD for the retried enable")
        modes = len(self.arm.modes)
        self.arm.mode_failures = 3
        self.assertTrue(self._release_when_acknowledged().success)
        self._state_is(HEALTHY, "HEALTHY on the release")
        self._enabled(modes + 3, "the arm enabled again after refused set_modes")
        self.assertGreaterEqual(len(self.arm.modes), modes + 4, "set_mode retried")
        self.assertEqual(self.arm.mode_failures, 0)
        retries = self.arm.mode_times[modes:]
        gaps = [later - earlier for earlier, later in zip(retries, retries[1:])]
        self.assertTrue(
            all(gap >= 4 * TICK_S - 0.01 for gap in gaps),
            f"an enable retried sooner than four ticks: gaps {gaps}",
        )
        harness.wait_for(
            lambda: self.states[-1].arm_enabled, "arm_enabled after the retried enable"
        )

        # 8. A second boundary - another id on the same topic - trips it.
        boundary.boundary_id = str(uuid.uuid4())
        tripped = self._state_is(TRIPPED, "TRIPPED on another boundary id")
        self.assertIn("this deadman follows", tripped.detail)
        harness.wait_for(lambda: self.arm.state == STOP, "the arm stopped on the rival")
        self._ended_by_the_trip(proc_info, deadman, "on another boundary id")

        # 9. A second heartbeat PUBLISHER trips it too - in HELD, unreleased.
        harness.bring_up(NODE)
        self._state_is(HELD, "HELD before the rival")
        rival = FakeBoundary(harness, ZONE)
        tripped = self._state_is(TRIPPED, "TRIPPED from HELD on a second publisher")
        self.assertIn("publisher", tripped.detail)
        rival.die()
        self._ended_by_the_trip(proc_info, deadman, "on a second publisher")

        # 10. The boundary dies outright: its publisher disappearing trips it.
        harness.bring_up(NODE)
        self._released_and_enabled("before the boundary dies")
        boundary.die()
        tripped = self._state_is(TRIPPED, "TRIPPED on publisher loss")
        self.assertIn("disappeared", tripped.detail)
        boundary.beating.clear()
        harness.wait_for(lambda: self.arm.state == STOP, "the arm stopped on publisher loss")
        self._ended_by_the_trip(proc_info, deadman, "on publisher loss")

        # 11. N-01: a trip between the set_mode answer and set_state(0). The
        #     vendor holds set_mode; the boundary dies and the deadman trips at
        #     once (its STOP is served meanwhile); then set_mode answers
        #     success. No START may follow the trip's STOP. (The precise
        #     interleaving is pinned in-process by test_ordering.py.)
        boundary.restart()
        boundary.beating.set()
        harness.bring_up(NODE)
        self._state_is(HELD, "HELD before the held enable")
        self.arm.mode_release.clear()
        self.arm.mode_held.clear()
        self.arm.hold_mode.set()
        self.assertTrue(self._release_when_acknowledged().success)
        self._state_is(HEALTHY, "HEALTHY with set_mode held")
        harness.wait_for(self.arm.mode_held.is_set, "set_mode held at the vendor")
        # Counted before the trip: HEALTHY sends no STOP, and the process may
        # end on the trip's first acknowledged one.
        trip_at = len(self.arm.calls)
        boundary.beating.clear()
        boundary.die()
        self._state_is(TRIPPED, "TRIPPED with set_mode held")
        harness.wait_for(
            lambda: ("set_state", STOP) in self.arm.calls[trip_at:], "the trip's set_state(4)"
        )
        self.arm.mode_release.set()
        # The process ends on the trip; its exit is read before anything is
        # held for, so the respawn cannot replace it on the launch's record.
        self._ended_by_the_trip(proc_info, deadman, "with set_mode held")
        self.assertNotIn(
            ("set_state", START), self.arm.calls[trip_at:],
            "set_state(0) after the trip's set_state(4)",
        )
        self.assertEqual(self.arm.state, STOP)

    def test_z_sigint_stops_the_arm_before_exit(self, proc_output, proc_info, deadman):
        """SIGINT reaches no lifecycle transition in rclpy; the process stops the arm itself.

        Last by name: it ends this deadman's process (and the launch starts another).
        """
        harness = self.harness
        boundary = self.boundary
        boundary.restart()
        boundary.beating.set()
        harness.bring_up(NODE)
        self._released_and_enabled("before the SIGINT")
        stops = self.arm.requests.count(STOP)
        os.kill(deadman.process_details["pid"], signal.SIGINT)
        harness.wait_for(
            lambda: self.arm.requests.count(STOP) > stops and self.arm.state == STOP,
            "set_state(4) sent on SIGINT, before the process exited",
        )
        proc_output.assertWaitFor(
            expected_output="SIGINT: every stop call answered; exiting", timeout=SETTLE_S
        )
        harness.wait_for(
            lambda: isinstance(proc_info[deadman], ProcessExited)
            and proc_info[deadman].returncode == 0,
            "the deadman ended with code 0 on SIGINT",
        )
        boundary.beating.clear()


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    def test_the_deadman_exits_cleanly(self, proc_info, deadman):
        self.assertIn(proc_info[deadman].returncode, (0, -2, -15))
