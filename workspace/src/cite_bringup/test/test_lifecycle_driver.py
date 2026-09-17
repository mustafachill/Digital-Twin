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

"""What the lifecycle driver believes, and what it refuses to believe.

ADR-0058 clause 2. The driver is the one thing standing between a managed node
that never activated and a cell that comes up around it, so the interesting cases
are all failures: what it says when a node does not answer, and what it says when
a node answers and does not move.

**The nodes here are fakes and they are real ROS servers.** Each advertises the
two lifecycle services under the same names a real managed node does and answers
them as this file instructs, so what is exercised is the service names, the
request, the response and the confirmation — everything except a genuine
`on_configure`. Nothing is brought up: no simulator, no controller manager, no
arm.

**The case that is not a failure is the one the record is about.** A node whose
`change_state` reply is lost, and which transitioned anyway, must be driven on
rather than reported: the reply is not the gate, `get_state` is. That is
`test_a_lost_reply_is_not_a_failed_transition` below, and if the driver were ever
rewritten to trust the response it is the test that would catch it.
"""

from __future__ import annotations

import os
import threading

from cite_bringup import lifecycle_driver
from cite_bringup.lifecycle_driver import main
from lifecycle_msgs.msg import State, Transition
from lifecycle_msgs.srv import ChangeState, GetState
import pytest
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

#: Short, because every test that reaches it is a test of what expiry SAYS. The
#: driver's own ceiling is its module constant; this is the value the launch is
#: free to pass and a test has every reason to.
_TEST_DEADLINE_S = "6.0"

#: Where each transition lands when the fake honours it.
_REACHES = {
    Transition.TRANSITION_CONFIGURE: (State.PRIMARY_STATE_INACTIVE, "inactive"),
    Transition.TRANSITION_ACTIVATE: (State.PRIMARY_STATE_ACTIVE, "active"),
}


class _FakeManaged(Node):
    """A node with the two lifecycle services and no lifecycle behind them.

    Two callback groups' worth of concurrency matters here: `answers_change`
    False blocks inside `change_state` for the whole test, and `get_state` has to
    keep answering while it does — which is exactly the shape of the failure the
    driver exists to survive, a node that is fine and a reply that is not.
    """

    def __init__(
        self,
        namespace: str,
        *,
        answers_change: bool = True,
        transitions: bool = True,
        succeeds: bool = True,
        stops_at: int | None = None,
    ) -> None:
        super().__init__(
            "probe",
            namespace=namespace,
            parameter_overrides=[Parameter("use_sim_time", value=False)],
        )
        self._answers_change = answers_change
        self._transitions = transitions
        self._succeeds = succeeds
        self._stops_at = stops_at
        self._state = (State.PRIMARY_STATE_UNCONFIGURED, "unconfigured")
        self.requested: list[int] = []
        self.released = threading.Event()

        group = ReentrantCallbackGroup()
        self.create_service(ChangeState, "~/change_state", self._change, callback_group=group)
        self.create_service(GetState, "~/get_state", self._get, callback_group=group)

    def _change(self, request, response):  # noqa: ANN001 - rclpy's callback shape
        self.requested.append(request.transition.id)
        if self._transitions and request.transition.id != self._stops_at:
            self._state = _REACHES[request.transition.id]
        if not self._answers_change:
            # Never answered, and released only at teardown so that the executor
            # thread can be joined. The driver must not be waiting on this.
            self.released.wait(timeout=120.0)
        response.success = self._succeeds
        return response

    def _get(self, request, response):  # noqa: ANN001 - rclpy's callback shape
        response.current_state.id, response.current_state.label = self._state
        return response

    @property
    def state_label(self) -> str:
        """Return the label this fake would answer `get_state` with right now."""
        return self._state[1]


@pytest.fixture(name="ros")
def _ros(monkeypatch):
    """One rclpy context for the test, with `main`'s own lifecycle calls stood down.

    The same arrangement `cite_facility`'s loader tests use and for the same
    reason: rclpy's default context cannot be initialised twice in one process,
    so the test owns it. What `runtime.init`/`runtime.shutdown` themselves do is
    tested in `cite_runtime`.
    """
    rclpy.init()
    monkeypatch.setattr(lifecycle_driver.runtime, "init", lambda args=None: None)
    monkeypatch.setattr(
        lifecycle_driver.runtime, "shutdown", lambda node: node.destroy_node()
    )
    try:
        yield
    finally:
        if rclpy.ok():
            rclpy.shutdown()


@pytest.fixture(name="spawn")
def _spawn(ros):
    """Start a fake managed node, spinning, and hand it back."""
    started: list[tuple[_FakeManaged, MultiThreadedExecutor, threading.Thread]] = []
    counter = 0

    def start(**behaviour) -> _FakeManaged:
        nonlocal counter
        counter += 1
        # A namespace nothing else on this domain can collide with: the suite may
        # be running beside a cell, and both would answer to `/cite/facility/...`.
        namespace = f"/cite_driver_test/pid{os.getpid()}_{counter}"
        node = _FakeManaged(namespace, **behaviour)
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        thread = threading.Thread(target=executor.spin, daemon=True)
        thread.start()
        started.append((node, executor, thread))
        return node

    try:
        yield start
    finally:
        for node, executor, thread in started:
            # Released first: a fake told not to answer is blocked inside its own
            # service callback, and the executor cannot be joined while it is.
            node.released.set()
            executor.shutdown(timeout_sec=5.0)
            thread.join(timeout=10.0)
            node.destroy_node()


def _name(node: _FakeManaged) -> str:
    """Return the name the driver addresses, spelled as the launch gives it."""
    return f"{node.get_namespace()}/probe"


def _run(*names: str, deadline: str = _TEST_DEADLINE_S) -> int:
    arguments: list[str] = []
    for name in names:
        arguments += ["--node", name]
    return main([*arguments, "--deadline", deadline])


# --- What it does when everything answers -------------------------------------


def test_every_node_is_taken_to_active(spawn) -> None:
    """The success path, and it is `active` rather than `inactive`.

    A node that configures and never activates is exactly the failure that was
    invisible, so stopping at `inactive` is not success and this asserts the
    state rather than the exit code alone.
    """
    first, second = spawn(), spawn()
    assert _run(_name(first), _name(second)) == 0
    assert first.state_label == "active" and second.state_label == "active"


def test_both_transitions_are_requested_in_order(spawn) -> None:
    """Configure then activate, on each node, and nothing else."""
    node = spawn()
    assert _run(_name(node)) == 0
    assert node.requested == [
        Transition.TRANSITION_CONFIGURE,
        Transition.TRANSITION_ACTIVATE,
    ]


# --- The case the record is about: the reply is not the gate -------------------


def test_a_lost_reply_is_not_a_failed_transition(spawn) -> None:
    """A node that transitioned and never answered is driven on, not reported.

    This is ADR-0058's load-bearing choice executed. A `change_state` reply can be
    dropped exactly as a transition broadcast can — one observed run carries both
    `failed to send response (timeout)` and `Abandoning wait for the
    '.../change_state' service response` — so silence from the request says
    nothing about the node. `get_state` is idempotent and re-askable, and what it
    says is what decides.

    Rewrite the driver to wait on the response and this test times out; rewrite
    it to treat an unanswered request as a failure and this test goes red with a
    diagnosis about a node that was `active` the whole time.
    """
    node = spawn(answers_change=False, transitions=True)
    assert _run(_name(node)) == 0
    assert node.state_label == "active"


# --- The failure paths, ADR-0058 clause 2 -------------------------------------


def test_a_node_that_never_answers_and_never_moves_is_named(spawn, capsys) -> None:
    """Non-zero, naming the node and the step it was asked for.

    The whole ceiling is spent here, which is the point of a ceiling: nothing
    proceeds when it expires, and what it produces is a sentence with a node name
    in it rather than a cell that came up around the node.
    """
    node = spawn(answers_change=False, transitions=False)
    assert _run(_name(node)) == 1
    reported = capsys.readouterr().err
    assert _name(node) in reported
    assert "configure" in reported
    assert "unconfigured" in reported


def test_a_node_that_answers_and_never_activates_is_named(spawn, capsys) -> None:
    """Configure lands, activate answers, and the node does not move.

    The failure `_managed`'s four refusals could never see: the node is healthy,
    it answers everything, and it is not `active`. Reported against the ACTIVATE
    step specifically, because a diagnosis naming the wrong step sends the reader
    to the wrong `on_` callback.
    """
    node = spawn(stops_at=Transition.TRANSITION_ACTIVATE)
    assert _run(_name(node)) == 1
    reported = capsys.readouterr().err
    assert _name(node) in reported
    assert "activate" in reported
    assert "inactive" in reported and "active" in reported


def test_a_node_that_refuses_the_transition_is_named(spawn, capsys) -> None:
    """`on_configure` returning FAILURE, reported by observation not by the reply.

    The four `_refuses` handlers ride the same volatile topic the activation used
    to, so a transition that FAILS is exactly as droppable as one that succeeded.
    What makes the failure reach a person either way is this: the driver asked,
    and the node says it is `unconfigured`.
    """
    node = spawn(transitions=False, succeeds=False)
    assert _run(_name(node)) == 1
    reported = capsys.readouterr().err
    assert _name(node) in reported and "unconfigured" in reported
    assert "answered that the transition failed" in reported


def test_a_node_that_is_not_there_is_named(ros, capsys) -> None:
    """A name nothing answers to, reported against the service it waited on.

    Short deadline and no fake at all. `wait_for_service` gates on the
    `change_state` endpoints, which is a different pair from the transition topic
    that carried the defect — discovering them says nothing about whether a
    broadcast would have arrived, and this is the one thing that pair IS good
    for.
    """
    assert _run("/cite_driver_test/nobody/probe", deadline="2.0") == 1
    reported = capsys.readouterr().err
    assert "/cite_driver_test/nobody/probe" in reported
    assert "change_state" in reported


def test_the_first_bad_node_stops_the_run(spawn, capsys) -> None:
    """One diagnosis, about the node that failed, and no node is skipped.

    A driver that reported the last failure rather than the first would name a
    node that is only failing because the one before it never activated.
    """
    stalled = spawn(answers_change=False, transitions=False)
    healthy = spawn()
    assert _run(_name(stalled), _name(healthy)) == 1
    reported = capsys.readouterr().err
    assert _name(stalled) in reported and _name(healthy) not in reported
    assert healthy.requested == [], "the run carried on past the node that failed"


# --- A driver with nothing to drive is refused, not satisfied -----------------


def test_naming_no_node_is_refused_before_a_context_exists(capsys) -> None:
    """An empty list is the one answer this program may never give.

    It is satisfied instantly, so the driver would exit 0, `_gate` would carry
    the chain forward, and the launch would have gated the whole of bring-up on a
    process that asked nothing. Refused with a distinct code, and before rclpy is
    touched — note that this test takes no `ros` fixture.
    """
    assert main(["--deadline", _TEST_DEADLINE_S]) == 2
    assert "no managed node" in capsys.readouterr().err
