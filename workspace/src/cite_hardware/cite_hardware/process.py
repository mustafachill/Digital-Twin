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

"""How each node in this package runs as a process, and how it stops one.

**A signal stops the asset before the process exits.** rclpy (Jazzy) runs no
lifecycle transition when its context goes down: its SIGINT/SIGTERM handler
shuts the context, `spin()` returns, and `LifecycleNode.destroy_node` does not
call `on_shutdown`. A context's own `on_shutdown` callbacks run only after
`rcl` has shut down, when nothing can be sent any more. So with rclpy's handler
an operator's Ctrl-C left the arm and the carriage as they were.

Here rclpy installs no signal handler. SIGINT and SIGTERM are blocked in every
thread before anything starts, so they stay pending until the main thread takes
them synchronously with `sigwait`; the executor spins on a second thread. On a
signal the node's `stop_before_exit()` runs while the context still stands —
the deadman sends `set_state(4)`, the track adapter `set_linear_motor_stop` —
and the main thread waits for those answers for at most the bound the node
returns (its own vendor-call deadline), then shuts down. A second signal during
that bounded wait is not needed and changes nothing. If the executor thread
ends on its own, it wakes the main thread the same way, with SIGUSR1, and the
stop is attempted all the same.

**NOT through `cite_runtime`'s init/spin/shutdown**, by that module's own
adoption rule: it says in terms that its pattern is for a process that commands
no actuator, or that installs its own hard-stop path. This is that path. Only
the one constant that module documents as the single statement of which
exceptions mean "the context went away" is imported from it.

What keeps the stop bounded is a property of the nodes rather than of this
module: no callback in this package blocks. Every vendor call is asynchronous
and every wait is a future some other callback completes, so neither the stop
nor the shutdown is queued behind a call to a machine that is not answering.
"""

from __future__ import annotations

from collections.abc import Callable
import signal
import threading
import time

from cite_runtime.runtime import caused_by_shutdown, SHUTDOWN_EXCEPTIONS
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

#: The signals that end the process, and the one the executor thread uses to
#: say that it ended.
_STOP_SIGNALS = {signal.SIGINT, signal.SIGTERM}
_SPIN_ENDED = signal.SIGUSR1


def run(factory: Callable[[], Node]) -> int:
    """Initialise rclpy, spin the node ``factory`` builds, stop it, and shut down."""
    # Blocked before any thread exists, so every thread rclpy, DDS or this
    # function starts inherits the mask and none of them takes the signal.
    signal.pthread_sigmask(signal.SIG_BLOCK, _STOP_SIGNALS | {_SPIN_ENDED})
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = factory()
    # Multi-threaded, because a vendor response, a command, a cancel and a
    # timer may all be ready at once and none of them may wait on another.
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    main = threading.main_thread().ident
    failure: list[BaseException] = []

    def spin() -> None:
        try:
            executor.spin()
        except BaseException as error:  # handed to the main thread, re-raised there
            failure.append(error)
        finally:
            signal.pthread_kill(main, _SPIN_ENDED)

    spinner = threading.Thread(target=spin, name="executor", daemon=True)
    spinner.start()
    try:
        received = signal.sigwait(_STOP_SIGNALS | {_SPIN_ENDED})
        why = (
            signal.Signals(received).name if received in _STOP_SIGNALS else "the executor ended"
        )
        # Whatever ended the process, the stop is attempted while the context
        # can still carry it. With the executor gone its answers never arrive,
        # and the wait is the node's bound.
        if rclpy.ok(context=node.context):
            _stop_before_exit(node, why)
    finally:
        # The context first: the executor thread leaves `spin()` on it, so the
        # executor is never shut down under a wait in progress.
        if rclpy.ok(context=node.context):
            rclpy.shutdown(context=node.context)
        spinner.join()
        executor.shutdown()
        node.destroy_node()
    for error in failure:
        if not isinstance(error, SHUTDOWN_EXCEPTIONS) or not caused_by_shutdown(error, node):
            raise error
    return 0


def _stop_before_exit(node: Node, why: str) -> None:
    """Ask the node to stop its asset, and wait for the answers within its bound."""
    stop = getattr(node, "stop_before_exit", None)
    if stop is None:
        return
    futures, bound_s = stop()
    deadline = time.monotonic() + bound_s
    unanswered = 0
    for future in futures:
        answered = threading.Event()
        future.add_done_callback(lambda _done, answered=answered: answered.set())
        if not answered.wait(max(0.0, deadline - time.monotonic())):
            unanswered += 1
    if unanswered:
        node.get_logger().error(
            f"{why}: {unanswered} stop call(s) unanswered within {bound_s:g} s; exiting anyway"
        )
    else:
        node.get_logger().info(f"{why}: every stop call answered; exiting")
