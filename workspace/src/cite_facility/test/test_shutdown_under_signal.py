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

"""Every long-lived node here exits 0 for SIGINT, whenever the signal lands.

P4 covers shutdown. A node whose exit code depends on which instruction the
interpreter happened to be executing when the signal arrived is a timing guess,
and this is the test that says so: `sigint_tripwire.py` puts the signal at the
one instant that used to produce a different answer — inside the generated
`convert_to_py` — rather than sending it from outside and hoping.

Before `cite_facility.runtime` existed these exited 1, deterministically, with
`RuntimeError: Unable to convert call argument '0' to Python object` out of
`rclpy/executors.py`, which is the traceback the `continuous_line` teardown
check reported from the field on 2026-08-27.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from cite_facility import runtime
import pytest
import rclpy
from rclpy.subscription import RCLError
from rosgraph_msgs.msg import Clock

TRIPWIRE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sigint_tripwire.py")

#: The nodes that spin. `planning_scene_loader` is a one-shot whose interrupted
#: exit code is deliberately nonzero, so it is not one of these.
SPINNING_NODES = [
    "cite_facility.frame_server",
    "cite_facility.model_info",
    "cite_facility.topology_server",
]

#: Deadlines, not schedules. Nothing about a correct run depends on either: the
#: node is signalled by its own first `/clock` message, not by the clock.
DISCOVERY_DEADLINE_S = 60.0
EXIT_DEADLINE_S = 60.0


@pytest.fixture(name="clock_publisher", scope="module")
def _clock_publisher():
    """Publish `/clock`, which is the only subscription these nodes hold."""
    rclpy.init()
    node = rclpy.create_node("shutdown_under_signal_test")
    publisher = node.create_publisher(Clock, "/clock", 10)
    try:
        yield publisher
    finally:
        node.destroy_node()
        rclpy.shutdown()


def _tick(publisher, count: int) -> None:
    message = Clock()
    message.clock.sec = count // 1000
    message.clock.nanosec = (count % 1000) * 1000000
    publisher.publish(message)


@pytest.mark.parametrize("module", SPINNING_NODES)
def test_sigint_inside_message_conversion_exits_cleanly(clock_publisher, module):
    """SIGINT taken mid-conversion still ends the process at 0."""
    process = subprocess.Popen(
        [
            sys.executable,
            TRIPWIRE,
            module,
            "--ros-args",
            "-r",
            "__node:=shutdown_probe",
            "-p",
            "use_sim_time:=true",
        ],
        env=dict(os.environ),
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # The node's own /clock subscription matching this publisher is the
        # event that says it is up. Nothing here waits a guessed duration for it.
        deadline = time.monotonic() + DISCOVERY_DEADLINE_S
        while clock_publisher.get_subscription_count() == 0:
            assert time.monotonic() < deadline, (
                f"{module} never subscribed to /clock, so the signal under test "
                "was never placed"
            )
            assert process.poll() is None, f"{module} exited before it was signalled"
            time.sleep(0.02)

        count = 0
        deadline = time.monotonic() + EXIT_DEADLINE_S
        while process.poll() is None and time.monotonic() < deadline:
            count += 1
            _tick(clock_publisher, count)
            time.sleep(0.005)
        assert process.poll() is not None, f"{module} did not exit after SIGINT"
    finally:
        if process.poll() is None:
            process.kill()
        _, stderr = process.communicate()

    assert process.returncode == 0, (
        f"{module} exited {process.returncode} for a SIGINT taken during message "
        f"conversion. Its stderr was:\n{stderr}"
    )


def test_a_wait_set_that_fails_after_shutdown_is_a_shutdown(monkeypatch):
    """The second upstream race is absorbed: the context is already gone."""
    monkeypatch.setattr(rclpy, "ok", lambda *a, **k: False)
    monkeypatch.setattr(
        rclpy, "spin", _raise(RCLError("failed to initialize wait set"))
    )
    runtime.spin(node=None)


def test_a_wait_set_that_fails_with_a_live_context_still_raises(monkeypatch):
    """And the compensation stays that narrow.

    This is the assertion that stops the clause above from growing into a
    blanket `except RCLError`. If the context is still valid, a wait set that
    will not initialise is a fault and has to be visible.
    """
    monkeypatch.setattr(rclpy, "ok", lambda *a, **k: True)
    monkeypatch.setattr(rclpy, "spin", _raise(RCLError("something else entirely")))
    with pytest.raises(RCLError):
        runtime.spin(node=None)


def _raise(error):
    def _spin(*args, **kwargs):
        raise error

    return _spin
