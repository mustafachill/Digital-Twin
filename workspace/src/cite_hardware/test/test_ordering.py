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

"""Interleavings a launch test cannot place, placed exactly (ADR-0070 re-audit).

Each node is built in this process and its vendor clients are replaced with
fakes that record every call in order and answer only when the test says so.
A fake can also run a hook in the one window that matters — after the node
decided and before it sent — which is where a concurrent trip, or a gate
closing, or a second poll, would land under the multi-threaded executor: rclpy
(Jazzy) runs a future's done callback as an executor task outside every
callback group, so nothing but the node's own lock orders it against a timer.

No executor and no graph: the node's own callbacks are called directly.
"""

from __future__ import annotations

import os
import sys
import threading

from builtin_interfaces.msg import Duration
from cite_hardware.deadman import Deadman
from cite_hardware.liveness import HEALTHY, TRIPPED
from cite_hardware.track_adapter import TrackAdapter
from cite_interfaces.msg import TwinHeartbeat
import pytest
import rclpy
from rclpy.lifecycle import TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.task import Future

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_parameters import GOOD  # noqa: E402
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint  # noqa: E402
from xarm_msgs.srv import Call, LinearMotorSetPos, SetInt16  # noqa: E402

#: How long a hook waits for the concurrent action it started. With the lock
#: held, as it must be, that action cannot finish, and the hook gives up after
#: this; without the lock it finishes at once. Either way the test's verdict is
#: the order of the recorded calls, never this duration.
HOOK_WAIT_S = 1.0


class FakeClient:
    """A vendor client: records each call in a shared log and answers on demand."""

    def __init__(
        self, name: str, log: list, answer: int | None = None, service_type=None
    ) -> None:
        self.srv_name = name
        self.log = log
        self.futures: list[Future] = []
        self.ready = True
        #: When set, every call is answered at once with this `ret`, in a
        #: ``service_type`` response.
        self.answer = answer
        self.service_type = service_type
        #: Run once, inside `service_is_ready()`: after the caller decided to
        #: send and before `call_async`.
        self.before_send = None

    def service_is_ready(self) -> bool:
        hook, self.before_send = self.before_send, None
        if hook is not None:
            hook()
        return self.ready

    def call_async(self, request) -> Future:
        self.log.append((self.srv_name, getattr(request, "data", getattr(request, "pos", None))))
        future = Future()
        self.futures.append(future)
        if self.answer is not None:
            response = self.service_type.Response()
            response.ret = self.answer
            future.set_result(response)
        return future

    def remove_pending_request(self, _future) -> None:
        pass


class StubGate:
    """The deadman gate, answering from a script, then from ``open``."""

    def __init__(self, answers=(), open_=True) -> None:
        self.answers = list(answers)
        self.open = open_

    def permits_motion(self) -> bool:
        return self.answers.pop(0) if self.answers else self.open

    def why_closed(self) -> str:
        return "closed by the test"

    def check(self) -> None:
        pass

    def destroy(self) -> None:
        pass


@pytest.fixture(scope="module", autouse=True)
def _context():
    rclpy.init()
    yield
    rclpy.shutdown()


def _build(node_type, name: str):
    overrides = [Parameter(key, value=value) for key, value in GOOD[name].items()]
    node = node_type(parameter_overrides=overrides)
    assert node.on_configure(None) == TransitionCallbackReturn.SUCCESS
    return node


def _concurrently(action) -> threading.Thread:
    """Start ``action`` on another thread and wait for it, at most HOOK_WAIT_S."""
    thread = threading.Thread(target=action, daemon=True)
    thread.start()
    thread.join(timeout=HOOK_WAIT_S)
    return thread


# ---------------------------------------------------------------------- #
# The deadman: N-01
# ---------------------------------------------------------------------- #


def test_a_trip_between_the_start_decision_and_its_send_is_never_followed_by_start():
    """N-01: no `set_state(0)` reaches the vendor after the trip's `set_state(4)`."""
    node = _build(Deadman, "deadman")
    started: list[threading.Thread] = []
    try:
        log: list = []
        node._set_state = FakeClient("set_state", log)
        node._set_mode = FakeClient("set_mode", log)
        node._linear_stop = FakeClient("set_linear_motor_stop", log)
        node._cancels = []
        node.on_activate(None)
        node._on_heartbeat(TwinHeartbeat(zone="cell_b", boundary_id="b", sequence=1))
        assert node._liveness.state == HEALTHY
        assert node._set_mode.futures, "set_mode sent on entering HEALTHY"

        def trip_now() -> None:
            def tick_after_the_timeout() -> None:
                node._last_fresh_ns = -(10**18)
                node._tick()

            started.append(_concurrently(tick_after_the_timeout))

        # The trip lands in the window between "HEALTHY in this epoch, so
        # START" and the send of set_state(0).
        node._set_state.before_send = trip_now
        response = SetInt16.Response()
        response.ret = 0
        node._set_mode.futures[0].set_result(response)
        for thread in started:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "the trip never completed"
        assert node._liveness.state == TRIPPED

        states = [value for service, value in log if service == "set_state"]
        assert 4 in states, "the trip's set_state(4)"
        last_stop = len(states) - 1 - states[::-1].index(4)
        assert 0 not in states[last_stop:], f"set_state(0) after the trip's STOP: {states}"
        assert states[-1] == 4, f"the arm left anything but stopped: {states}"
    finally:
        node.destroy_node()


def test_an_abandoned_set_mode_is_retried_while_healthy():
    """N-06: an enable abandoned at its deadline is tried again, and only success enables."""
    node = _build(Deadman, "deadman")
    try:
        log: list = []
        node._set_state = FakeClient("set_state", log)
        node._set_mode = FakeClient("set_mode", log)
        node._linear_stop = FakeClient("set_linear_motor_stop", log)
        node._cancels = []
        node.on_activate(None)
        node._on_heartbeat(TwinHeartbeat(zone="cell_b", boundary_id="b", sequence=1))
        assert len(node._set_mode.futures) == 1
        # In flight: a tick sends no second one.
        node._last_fresh_ns = node._steady.now().nanoseconds
        node._enable(node._epoch)
        assert len(node._set_mode.futures) == 1
        # Abandoned at its deadline, as `_abandon_overdue` does.
        node._abandon_overdue(node._steady.now().nanoseconds + 10**12)
        assert node._enable_in_flight is None
        node._enable(node._epoch)
        assert len(node._set_mode.futures) == 1, "HW-S-04: not on the very next tick"
        # The back-off over, as ENABLE_RETRY_TICKS ticks later.
        node._enable_backoff = (node._epoch, 0)
        node._enable(node._epoch)
        assert len(node._set_mode.futures) == 2, "the enable retried"
        response = SetInt16.Response()
        response.ret = 0
        node._set_mode.futures[1].set_result(response)
        assert ("set_state", 0) in log
        assert node._enabled_epoch is None, "not enabled before set_state(0) is answered"
        node._set_state.futures[-1].set_result(response)
        assert node._enabled_epoch == node._epoch
        node._enable(node._epoch)
        assert len(node._set_mode.futures) == 2, "no enable once enabled in this epoch"
    finally:
        node.destroy_node()


# ---------------------------------------------------------------------- #
# The track adapter: N-04, N-05, N-09
# ---------------------------------------------------------------------- #


def _command(position: float, seconds: int) -> JointTrajectory:
    """From 0.1 m now to ``position`` in ``seconds``: a start point, then the target."""
    message = JointTrajectory(joint_names=[GOOD["track_adapter"]["joint"]])
    message.points.append(JointTrajectoryPoint(positions=[0.1], time_from_start=Duration()))
    message.points.append(
        JointTrajectoryPoint(positions=[position], time_from_start=Duration(sec=seconds))
    )
    return message


def _track(gate: StubGate, speed_answer: int | None = 0):
    node = _build(TrackAdapter, "track_adapter")
    log: list = []
    node._set_client = FakeClient("set_linear_motor_pos", log)
    # Answered at once unless a test answers it: the speed write precedes every
    # move at a speed not yet acknowledged (SA-S-03).
    node._speed_client = FakeClient("set_linear_motor_speed", log, speed_answer, SetInt16)
    node._get_client = FakeClient("get_linear_motor_pos", log)
    node._stop_client = FakeClient("set_linear_motor_stop", log)
    node._gate = gate
    node.on_activate(None)
    node._position_m = 0.1
    node._position_at_ns = node._steady.now().nanoseconds
    return node, log


def _answer(future: Future, ret: int, response_type) -> None:
    response = response_type.Response()
    response.ret = ret
    future.set_result(response)


def _stops(log: list) -> int:
    return sum(1 for service, _ in log if service == "set_linear_motor_stop")


def test_a_gate_closing_after_the_command_check_sends_no_move():
    """N-04: the last look at the gate is taken in `_send`, under the lock."""
    node, log = _track(StubGate(answers=[True], open_=False))
    try:
        node._on_command(_command(0.3, 2))
        assert not [entry for entry in log if entry[0] == "set_linear_motor_pos"]
    finally:
        node.destroy_node()


def test_the_stop_is_level_triggered_and_resent_until_acknowledged():
    """N-04, N-05: every poll stops a possibly moving carriage until a stop is acked."""
    gate = StubGate()
    node, log = _track(gate)
    try:
        node._on_command(_command(0.3, 2))
        move = node._set_client.futures[-1]
        _answer(move, 0, LinearMotorSetPos)
        gate.open = False
        node._poll()
        assert _stops(log) == 1, "a stop on the first poll with the gate closed"
        node._poll()
        assert _stops(log) == 1, "not a second one while the first is in flight"
        _answer(node._stop_client.futures[-1], 1, Call)
        node._poll()
        assert _stops(log) == 2, "a refused stop is sent again"
        _answer(node._stop_client.futures[-1], 0, Call)
        node._poll()
        node._poll()
        assert _stops(log) == 2, "no stop after one was acknowledged"
    finally:
        node.destroy_node()


def test_a_stop_acked_while_a_move_is_outstanding_does_not_end_the_stopping():
    """N-05: a move whose call may reach the vendor after the stop keeps it stopping."""
    gate = StubGate()
    node, log = _track(gate)
    try:
        node._on_command(_command(0.3, 2))
        move = node._set_client.futures[-1]  # unanswered: the move may land late
        gate.open = False
        node._poll()
        _answer(node._stop_client.futures[-1], 0, Call)
        node._poll()
        assert _stops(log) == 2, "stopping goes on while the move is outstanding"
        _answer(move, 0, LinearMotorSetPos)
        _answer(node._stop_client.futures[-1], 0, Call)
        node._poll()
        # SA2c-S-02 e: the second stop was SENT while the move was outstanding,
        # so it may have been overtaken; one more, sent after the answer, ends it.
        assert _stops(log) == 3, "a stop sent after the move was answered"
        _answer(node._stop_client.futures[-1], 0, Call)
        node._poll()
        assert _stops(log) == 3, "and ends with that stop acknowledged"
    finally:
        node.destroy_node()


def test_a_second_poll_in_the_send_window_sends_no_second_read():
    """N-09: the read is reserved before it is sent, so a concurrent poll sends none."""
    node, log = _track(StubGate())
    try:
        node._get_client.before_send = node._poll
        node._poll()
        reads = [entry for entry in log if entry[0] == "get_linear_motor_pos"]
        assert len(reads) == 1, f"two reads in flight: {log}"
    finally:
        node.destroy_node()


# ---------------------------------------------------------------------- #
# The track adapter: SA-S-03, the speed is written and acknowledged first
# ---------------------------------------------------------------------- #


def _sent(log: list) -> list[str]:
    return [service for service, _ in log if service != "get_linear_motor_pos"]


def test_the_speed_is_written_and_acknowledged_before_the_move():
    """SA-S-03: the vendor caches its speed and ignores the write's result."""
    node, log = _track(StubGate(), speed_answer=None)
    try:
        node._on_command(_command(0.3, 2))
        assert _sent(log) == ["set_linear_motor_speed"], "no move before the speed is acked"
        assert log[0][1] == 100, "the commanded speed, 0.2 m / 2 s, in mm/s"
        _answer(node._speed_client.futures[-1], 0, SetInt16)
        assert _sent(log) == ["set_linear_motor_speed", "set_linear_motor_pos"]
        # The same speed again: acknowledged, so not written again.
        _answer(node._set_client.futures[-1], 0, LinearMotorSetPos)
        node._on_command(_command(0.5, 4))
        assert _sent(log)[-1] == "set_linear_motor_pos"
        assert _sent(log).count("set_linear_motor_speed") == 1
    finally:
        node.destroy_node()


def test_a_refused_speed_write_sends_no_move():
    node, log = _track(StubGate(), speed_answer=1)
    try:
        node._on_command(_command(0.3, 2))
        assert _sent(log) == ["set_linear_motor_speed"]
        assert node._target is None and not node._set_in_flight
    finally:
        node.destroy_node()


def test_the_first_move_after_activation_writes_its_speed_again():
    node, log = _track(StubGate())
    try:
        node._on_command(_command(0.3, 2))
        _answer(node._set_client.futures[-1], 0, LinearMotorSetPos)
        node.on_deactivate(None)
        node.on_activate(None)
        node._position_at_ns = node._steady.now().nanoseconds
        node._on_command(_command(0.3, 2))
        assert _sent(log).count("set_linear_motor_speed") == 2
        assert _sent(log)[-2:] == ["set_linear_motor_speed", "set_linear_motor_pos"]
    finally:
        node.destroy_node()


# ---------------------------------------------------------------------- #
# The track adapter: SA-S-06, a move older than the last hold is never sent
# ---------------------------------------------------------------------- #


def _hold(position: float = 0.55) -> JointTrajectory:
    """A hold: both points at one position, which the adapter answers with a stop."""
    message = JointTrajectory(joint_names=[GOOD["track_adapter"]["joint"]])
    for seconds in (0, 1):
        message.points.append(
            JointTrajectoryPoint(positions=[position], time_from_start=Duration(sec=seconds))
        )
    return message


class _GateWithHook(StubGate):
    """Open, and running ``hook`` once inside the first look: a hold landing mid-check."""

    def __init__(self) -> None:
        super().__init__()
        self.hook = None

    def permits_motion(self) -> bool:
        hook, self.hook = self.hook, None
        if hook is not None:
            hook()
        return super().permits_motion()


def _moves(log: list) -> list:
    return [value for service, value in log if service == "set_linear_motor_pos"]


def test_a_hold_landing_while_a_move_is_checked_outranks_it():
    """SA-S-06: the move took its place in line at entry, before the hold."""
    gate = _GateWithHook()
    node, log = _track(gate)
    try:
        gate.hook = lambda: node._on_command(_hold())
        node._on_command(_command(0.3, 2))
        assert _moves(log) == [] and "set_linear_motor_speed" not in _sent(log)
        assert node._holding and node._target is None
    finally:
        node.destroy_node()


def test_a_hold_during_the_speed_write_drops_the_move_behind_it():
    node, log = _track(StubGate(), speed_answer=None)
    try:
        node._on_command(_command(0.3, 2))
        node._on_command(_hold())
        _answer(node._speed_client.futures[-1], 0, SetInt16)
        assert _moves(log) == []
        assert not node._set_in_flight
    finally:
        node.destroy_node()


def test_a_move_after_the_hold_is_sent_in_place_of_the_one_before_it():
    node, log = _track(StubGate(), speed_answer=None)
    try:
        node._on_command(_command(0.3, 2))
        node._on_command(_hold())
        # Back towards 0 at the same speed, held behind the speed write: its
        # first segment ends at 50 mm, the older move's would at 150 mm.
        node._on_command(_command(0.0, 1))
        _answer(node._speed_client.futures[-1], 0, SetInt16)
        assert _moves(log) == [50]
    finally:
        node.destroy_node()
