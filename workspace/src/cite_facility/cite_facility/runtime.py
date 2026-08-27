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

"""Start-up and shutdown for this package's nodes, with no timing guess in it.

P4 governs shutdown as much as start-up, and the default rclpy idiom does not
satisfy it. `rclpy.init()` chains its own SIGINT handler to Python's
`default_int_handler`, which raises KeyboardInterrupt at the next eval-breaker
check. Where that check falls is a race the node loses at a measurable rate:

  * If it falls at an ordinary bytecode boundary, KeyboardInterrupt leaves
    `spin()` and `except KeyboardInterrupt` catches it. Exit 0.
  * If it falls inside `PyObject_CallObject` in a generated `convert_to_py` —
    which is where the interpreter is whenever a subscription message is being
    turned into a Python object — the constructor returns NULL. rclpy's
    `convert_to_py` does not test that pointer (`rclpy/src/rclpy/utils.cpp`
    line 139 steals it unchecked), so `Subscription::take_message` reaches
    `py::make_tuple` with a null object and pybind11 raises `cast_error`.
    Reporting it calls `PyErr_SetString`, which *discards* the pending
    KeyboardInterrupt and puts `RuntimeError: Unable to convert call argument
    '0' to Python object` in its place. Nothing catches that. Exit 1.

Measured on this stack: 3 of 30 SIGINTs at 2026-08-27 with `/clock` saturated,
0 of 30 with the node idle — which is why an earlier 50-trial investigation
against idle nodes correctly found nothing. Every node here runs with
`use_sim_time`, so every one of them holds rclpy's internal `/clock`
subscription and is converting messages continuously.

The fix is to stop making the exit depend on an asynchronous raise at all. A
SIGINT handler that returns without raising cannot set an error indicator, so
the window closes: rclpy's own handler still triggers the guard conditions and
shuts the context down from its deferred thread, and `spin()` leaves through
`ExternalShutdownException` at a point of the executor's choosing.

Closing that race exposed a second one underneath it, which `spin` below
documents and which was invisible only because KeyboardInterrupt used to reach
the process first. Both are upstream; neither is compensated any wider than the
state in which it can mean nothing else.

This does not swallow a stuck node. Absorbing SIGINT only removes the raise;
if the context never shuts down, `launch` escalates to SIGTERM and the process
dies visibly rather than exiting 0.
"""

from __future__ import annotations

import signal

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
# Jazzy's `rclpy.exceptions` does not export this; `rclpy.subscription` holds the
# only alias for it that is not an import of `rclpy._rclpy_pybind11` directly.
from rclpy.subscription import RCLError


def _absorb_sigint(signum: int, frame: object) -> None:
    """Handle SIGINT by doing nothing, so that nothing is raised for it.

    rclpy has already been told about the signal by its own C handler, which
    chains here. Shutdown is that handler's job; this one exists solely to
    occupy the slot `default_int_handler` would otherwise hold.
    """


def init(args: list[str] | None = None) -> None:
    """Install the shutdown handler, then initialise rclpy.

    The order is load-bearing and cannot be reversed. `rclpy.init()` records
    whatever SIGINT handler it finds and chains to it; installing ours first is
    what puts it in that chain. Installing it afterwards would instead replace
    rclpy's handler with Python's C trampoline and lose the context shutdown.
    """
    signal.signal(signal.SIGINT, _absorb_sigint)
    rclpy.init(args=args)


def spin(node: Node) -> None:
    """Spin until the context is shut down, however that shutdown was asked for.

    Three exits, one meaning.

    `ExternalShutdownException` is the intended one, and the one `init()` above
    makes the common case.

    KeyboardInterrupt is still caught. `init()` makes it unreachable under
    SIGINT, but a caller that spins without it — a test, an interactive session —
    should still stop rather than traceback.

    `RCLError` is the second upstream race in this path and it only became
    reachable once the first was closed: measured at 11 of 30 SIGINTs once
    KeyboardInterrupt stopped winning them. `_wait_for_ready_callbacks` builds
    its wait set from `self._context` at line 757 of Jazzy's
    `rclpy/executors.py` and only asks whether that context is still valid at
    line 784 — twenty-seven lines *after* it has already used it. The deferred
    thread that rclpy's own signal handler runs shuts the context down in that
    window, and the wait set then fails to initialise instead of the executor
    reaching the `ExternalShutdownException` it was about to raise.

    Tolerated only while `rclpy.ok()` is already false, which is the single
    state in which that error can mean nothing else. A wait set that fails for
    any other reason still leaves this function.
    """
    try:
        rclpy.spin(node)
    except (ExternalShutdownException, KeyboardInterrupt):
        pass
    except RCLError:
        if rclpy.ok():
            raise


def shutdown(node: Node) -> None:
    """Release the node and the context, in that order, exactly once."""
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
