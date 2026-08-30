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

"""A node spinning through `runtime` exits 0 for SIGINT, whenever it lands.

P4 covers shutdown. A node whose exit code depends on which instruction the
interpreter happened to be executing when the signal arrived is a timing guess,
and this is the test that says so: `sigint_tripwire.py` puts the signal at the
one instant that used to produce a different answer — inside the generated
`convert_to_py` — rather than sending it from outside and hoping.

Two idioms are driven through the same tripwire, and both assertions are load
bearing. The `runtime` idiom must exit 0; the pre-`runtime` idiom must still
fail, with the exact `RuntimeError` the `continuous_line` teardown check reported
from the field on 2026-08-27. Without the second, a tripwire that had stopped
placing the signal would leave the first passing while proving nothing.

THIS TEST RUNS ON A DOMAIN OF ITS OWN, and that is not tidiness. `ROS_DOMAIN_ID`
is derived from the checkout path and deliberately shared, so `./scripts/enter`
can attach to a cell this checkout launched (`scripts/_lib.sh`). `./scripts/test`
neither isolates it nor asks whether a cell is up. This file publishes `/clock`,
and every node in the cell runs `use_sim_time` — so on the ambient domain it
would be a second clock source for a running cell, which `tests/scenarios/`
already names as a defect in its own right. The fixture and the process it
spawns share a private domain and share it with nothing else.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

from cite_runtime import runtime
import pytest
import rclpy
from rclpy.subscription import RCLError
from rosgraph_msgs.msg import Clock

HERE = os.path.dirname(os.path.abspath(__file__))
TRIPWIRE = os.path.join(HERE, "sigint_tripwire.py")

#: The probe module `sigint_tripwire.py` imports. It sits beside the tripwire, so
#: the child's `sys.path[0]` — the tripwire's own directory — already finds it.
PROBE = "spinning_probe"

#: Deadlines, not schedules. Nothing about a correct run depends on either: the
#: probe is signalled by its own first `/clock` message, not by the clock. The
#: first only has to outlast DDS discovery on a cold container; the second only
#: has to outlast a shutdown, and `launch` SIGKILLs a wedged node at 10 s.
DISCOVERY_DEADLINE_S = 60.0
EXIT_DEADLINE_S = 30.0

#: Poll interval while waiting on those two events. Not a schedule either — it
#: bounds how long an event goes unnoticed, and nothing is sequenced by it.
POLL_S = 0.02

#: The signal is placed by the tripwire on the FIRST `/clock` message, so one
#: delivery is all a correct run needs. The loop keeps publishing only because
#: the process may take a moment to leave, and a message that arrives after the
#: tripwire has fired converts normally by construction.
TICK_S = 0.005

#: The traceback the lost-signal race produces, from rclpy's unchecked
#: `convert_to_py`. Asserted verbatim in the negative control so that "the
#: pre-fix idiom failed" cannot be satisfied by the probe failing for some
#: unrelated reason.
LOST_SIGNAL_TRACEBACK = "Unable to convert call argument"


#: The band this test draws its private domain from, and the reason it is not
#: the band `cite_domain_id` draws from.
#:
#: ROS 2 documents two ranges as safe from the Linux ephemeral port range: 0-101
#: and 215-232. A checkout's cell occupies the FIRST — `cite_domain_id` allocates
#: an odd plant in 1..99 and the generated plan puts its counterpart at the even
#: number above it, so 1..100 is cell space (ADR-0044, clause 4). A domain drawn
#: from the SECOND band therefore cannot be any side of any checkout on this
#: host, paired or not.
#:
#: That is a stronger property than the arithmetic this function used to carry.
#: It picked `os.getpid() % 101 + 1` and stepped over exactly one value, the
#: ambient `ROS_DOMAIN_ID` — a second, independent implementation of a rule that
#: lives in `scripts/_lib.sh`, which is why it drifted out of sight when the rule
#: changed. Under a pair there are TWO domains a test must avoid and it knew
#: about one; a pid landing on the counterpart's would have joined a live
#: counterpart's graph, where every node runs `use_sim_time`, which is precisely
#: what the docstring at the top of this file says the private domain prevents.
#: Choosing a disjoint band removes the reimplementation rather than updating it.
PRIVATE_DOMAIN_BAND = range(215, 233)


def _private_domain_id() -> int:
    """Pick a DDS domain this process does not share with anything else.

    Two distinct collisions have to be avoided.

    A LIVE CELL's domain, this checkout's or any other's. Answered structurally
    by :data:`PRIVATE_DOMAIN_BAND` rather than by stepping over a value: no
    domain in that band can be a side of any checkout.

    ANOTHER COPY OF THIS TEST is the collision `CMakeLists.txt` used to warn
    about, and moving the test to a fixed private domain would only have moved
    it. The process id distinguishes copies, because two copies are two pytest
    processes by definition.

    **The trade is stated rather than hidden.** The band holds 18 values where
    the old arithmetic had 101, so two concurrent copies of this test collide
    more often than they did. That is accepted because the two failures are not
    comparable: a copy collision puts a second `/clock` publisher on a domain
    only copies of this test can reach, and this file's assertions are about a
    child process's exit status and stderr, which more clock messages do not
    change; joining a live cell is silent, corrupts a run nobody is looking at,
    and was the failure the private domain existed to prevent.

    The ambient domain is still stepped over, because a developer may set
    `ROS_DOMAIN_ID` explicitly to anything, including a value in this band.
    """
    ambient = os.environ.get("ROS_DOMAIN_ID")
    index = os.getpid() % len(PRIVATE_DOMAIN_BAND)
    if str(PRIVATE_DOMAIN_BAND[index]) == ambient:
        index = (index + 1) % len(PRIVATE_DOMAIN_BAND)
    return PRIVATE_DOMAIN_BAND[index]


@pytest.fixture(name="clock_source", scope="module")
def _clock_source():
    """Yield a `/clock` publisher and the environment its subscriber must use.

    The context is this fixture's own rather than rclpy's default, so nothing
    else in this file can end up on the private domain by accident, and
    `ROS_DOMAIN_ID` is put back immediately after `rclpy.init` has read it.
    """
    domain = _private_domain_id()
    child_env = {**os.environ, "ROS_DOMAIN_ID": str(domain)}
    ambient = os.environ.get("ROS_DOMAIN_ID")

    context = rclpy.Context()
    os.environ["ROS_DOMAIN_ID"] = str(domain)
    try:
        rclpy.init(context=context)
    finally:
        if ambient is None:
            os.environ.pop("ROS_DOMAIN_ID", None)
        else:
            os.environ["ROS_DOMAIN_ID"] = ambient

    # Asserted rather than assumed: setting the variable is not evidence that the
    # context took it, and the failure this guards against is a silent one — a
    # /clock publisher on a live cell's domain looks exactly like a working test.
    assert context.get_domain_id() == domain, (
        f"the private domain did not take: asked for {domain}, "
        f"got {context.get_domain_id()}"
    )
    assert str(domain) != ambient, "the private domain is the ambient one"

    node = rclpy.create_node("shutdown_under_signal_test", context=context)
    publisher = node.create_publisher(Clock, "/clock", 10)
    try:
        yield publisher, child_env
    finally:
        node.destroy_node()
        rclpy.shutdown(context=context)


def _tick(publisher, count: int) -> None:
    message = Clock()
    message.clock.sec = count // 1000
    message.clock.nanosec = (count % 1000) * 1000000
    publisher.publish(message)


def _run_probe(clock_source, idiom: str) -> subprocess.CompletedProcess:
    """Spawn the probe under the tripwire and return once it has exited."""
    publisher, child_env = clock_source
    process = subprocess.Popen(
        [sys.executable, TRIPWIRE, PROBE, idiom],
        env=child_env,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # The probe's own /clock subscription matching this publisher is the
        # event that says it is up. Nothing here waits a guessed duration for it.
        deadline = time.monotonic() + DISCOVERY_DEADLINE_S
        while publisher.get_subscription_count() == 0:
            assert time.monotonic() < deadline, (
                f"the {idiom} probe never subscribed to /clock, so the signal "
                "under test was never placed"
            )
            assert process.poll() is None, (
                f"the {idiom} probe exited before it was signalled"
            )
            time.sleep(POLL_S)

        count = 0
        deadline = time.monotonic() + EXIT_DEADLINE_S
        while process.poll() is None and time.monotonic() < deadline:
            count += 1
            _tick(publisher, count)
            time.sleep(TICK_S)
        assert process.poll() is not None, (
            f"the {idiom} probe did not exit after SIGINT"
        )
    finally:
        if process.poll() is None:
            process.kill()
        _, stderr = process.communicate()

    return subprocess.CompletedProcess(
        args=process.args, returncode=process.returncode, stderr=stderr
    )


def test_sigint_inside_message_conversion_exits_cleanly(clock_source):
    """SIGINT taken mid-conversion still ends the process at 0."""
    result = _run_probe(clock_source, "runtime")
    assert result.returncode == 0, (
        "a node spinning through cite_runtime.runtime exited "
        f"{result.returncode} for a SIGINT taken during message conversion. "
        f"Its stderr was:\n{result.stderr}"
    )


def test_the_tripwire_still_breaks_the_idiom_it_replaced(clock_source):
    """The negative control: the pre-`runtime` idiom still loses the signal.

    If this ever passes, the test above has stopped proving anything and must
    not be believed until this is understood. There are only two ways for it to
    happen: the tripwire has stopped placing the signal inside `convert_to_py`,
    or rclpy's `convert_to_py` has learned to check the pointer it steals — in
    which case `cite_runtime.runtime`'s premise has changed and the module's
    documentation is now wrong.
    """
    result = _run_probe(clock_source, "default")
    assert result.returncode != 0, (
        "the pre-runtime idiom exited 0 under the tripwire, so the tripwire is "
        "no longer placing SIGINT where it claims to and the clean-exit test "
        f"above proves nothing. Its stderr was:\n{result.stderr}"
    )
    assert LOST_SIGNAL_TRACEBACK in result.stderr, (
        "the pre-runtime idiom failed, but not with the lost-signal traceback "
        f"this tripwire exists to produce. Its stderr was:\n{result.stderr}"
    )


def test_a_sigint_arriving_during_init_is_delivered_not_destroyed(monkeypatch):
    """The window inside `init()` itself keeps the signal instead of eating it.

    Between installing the no-op handler and rclpy installing its own — 3-24 ms,
    measured — a delivered SIGINT used to reach the no-op, be absorbed and be
    recorded nowhere: a node signalled there was still running 10 s later, and
    only a second Ctrl-C recovered it.

    The signal is placed inside the window rather than raced into it, so nothing
    here is timed. `rclpy.init` stands in for the real one and does two things
    from inside the window: it raises SIGINT, and it then installs the handler
    that rclpy's own `init` would have installed. Both assertions matter — that
    the signal is *pending* rather than gone, and that it lands on the completed
    chain and not on the no-op. Without the mask, `raise_signal` delivers to the
    no-op before this fake returns and `delivered` stays empty.
    """
    delivered: list[int] = []
    previous = signal.getsignal(signal.SIGINT)

    def _fake_rclpy_init(args=None):
        signal.raise_signal(signal.SIGINT)
        assert signal.SIGINT in signal.sigpending(), (
            "SIGINT was not blocked across init(), so it was delivered to the "
            "no-op handler and destroyed"
        )
        signal.signal(signal.SIGINT, lambda signum, frame: delivered.append(signum))

    monkeypatch.setattr(rclpy, "init", _fake_rclpy_init)
    try:
        runtime.init()
        assert delivered == [signal.SIGINT], (
            "the SIGINT raised inside init()'s window never reached the handler "
            "chain that init() finished building"
        )
    finally:
        signal.signal(signal.SIGINT, previous)


def test_a_wait_set_that_fails_after_shutdown_is_a_shutdown(monkeypatch):
    """The second upstream race is absorbed: the context is already gone.

    And it is absorbed VISIBLY. `rclpy.ok()` is evaluated after the exception, by
    which point the context is down for essentially anything raised during
    teardown, so this clause can swallow more than the race it documents. The
    tolerance stays exactly as narrow; the evidence stops disappearing.
    """
    node = _FakeNode()
    logged: list[str] = []
    monkeypatch.setattr(rclpy, "ok", lambda *a, **k: False)
    monkeypatch.setattr(runtime, "get_logger", lambda name: _Recorder(logged))
    monkeypatch.setattr(
        rclpy, "spin", _raise(RCLError("failed to initialize wait set"))
    )
    runtime.spin(node)
    assert logged and "failed to initialize wait set" in logged[0], (
        "the absorbed RCLError was discarded rather than logged"
    )


def test_a_wait_set_that_fails_with_a_live_context_still_raises(monkeypatch):
    """And the compensation stays that narrow.

    This is the assertion that stops the clause above from growing into a
    blanket `except RCLError`. If the context is still valid, a wait set that
    will not initialise is a fault and has to be visible.
    """
    node = _FakeNode()
    monkeypatch.setattr(rclpy, "ok", lambda *a, **k: True)
    monkeypatch.setattr(rclpy, "spin", _raise(RCLError("something else entirely")))
    with pytest.raises(RCLError):
        runtime.spin(node)


def test_the_liveness_question_is_asked_of_the_node_s_own_context(monkeypatch):
    """`runtime` is shared, so "is it up?" must name whose context is meant.

    Identical to rclpy's default for every node in this repository today, and
    not identical for a caller that builds its own context — which is exactly
    what a shared utility invites.
    """
    node = _FakeNode()
    asked: list[object] = []

    def _ok(*args, **kwargs):
        asked.append(kwargs.get("context"))
        return False

    monkeypatch.setattr(rclpy, "ok", _ok)
    monkeypatch.setattr(rclpy, "spin", _raise(RCLError("failed to initialize")))
    runtime.spin(node)
    assert asked == [node.context]


def test_the_shutdown_exception_set_is_named_once():
    """The loader catches this module's set rather than restating it.

    Which exceptions mean "the context was shut down" is subtle and upstream
    dependent; P1 says it is written down once. This asserts the membership the
    other catch sites rely on.
    """
    assert runtime.SHUTDOWN_EXCEPTIONS == (
        runtime.ExternalShutdownException,
        KeyboardInterrupt,
        RCLError,
    )


class _Recorder:
    """The one method `runtime.spin` calls on a logger."""

    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def info(self, message: str) -> None:
        self._sink.append(message)


class _FakeNode:
    """A node-shaped object with a context and nothing else.

    `rclpy.spin` is monkeypatched in these tests, so the only thing `runtime`
    can reach on the node is the context it asks about.
    """

    def __init__(self) -> None:
        self.context = object()


def _raise(error):
    def _spin(*args, **kwargs):
        raise error

    return _spin


def test_the_private_domain_cannot_be_any_side_of_any_checkout() -> None:
    """The property that replaces stepping over one value.

    `cite_domain_id` allocates an odd plant in 1..99 and the generated plan puts
    the counterpart at the even number above it, so a cell occupies 1..100 on
    any checkout on this host. Nothing in this band can be a side of one, so a
    pid can no longer land on a live counterpart's graph — where every node runs
    `use_sim_time` and this file publishes `/clock` (ADR-0044, clause 4).
    """
    cell_space = range(1, 101)
    assert not set(PRIVATE_DOMAIN_BAND) & set(cell_space)
    assert _private_domain_id() in PRIVATE_DOMAIN_BAND


def test_the_private_domain_still_steps_over_an_explicit_ambient_one(monkeypatch) -> None:
    # A developer may export ROS_DOMAIN_ID to anything, including a value in this
    # band, so the structural guarantee above does not retire the step.
    chosen = _private_domain_id()
    monkeypatch.setenv("ROS_DOMAIN_ID", str(chosen))
    assert _private_domain_id() != chosen
