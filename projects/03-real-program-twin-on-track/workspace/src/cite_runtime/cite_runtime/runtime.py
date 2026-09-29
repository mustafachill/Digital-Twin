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

"""Start-up and shutdown for a Python node, with no timing guess in it.

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
against idle nodes correctly found nothing. Any node running with `use_sim_time`
holds rclpy's internal `/clock` subscription and is converting messages
continuously.

The fix is to stop making the exit depend on an asynchronous raise at all. A
SIGINT handler that returns without raising cannot set an error indicator, so
the window closes: rclpy's own handler still triggers the guard conditions and
shuts the context down from its deferred thread, and `spin()` leaves through
`ExternalShutdownException` at a point of the executor's choosing.

Closing that race exposed a second one underneath it, which `spin` below
documents and which was invisible only because KeyboardInterrupt used to reach
the process first. Both are upstream; neither is compensated any wider than the
state in which it can mean nothing else.

WHAT BACKS THIS UP WHEN A NODE WEDGES, stated exactly, because the load-bearing
safety claim in this module used to be stated wrongly. It said `launch` escalates
a stuck node to SIGTERM and the process "dies visibly". It does not.
`rclpy.init()` installs handlers for **both** SIGINT and SIGTERM
(`SignalHandlerOptions.ALL`) and does not chain either to `SIG_DFL`. Measured in
this project's image: a running rclpy node sent SIGTERM shut its context down,
left `spin()` with `ExternalShutdownException`, **and kept running**. SIGTERM is
therefore not an escalation for these nodes — it does exactly what SIGINT
already did. The only real backstop is **SIGKILL**, which `launch` sends at
`sigterm_timeout + sigkill_timeout` after the shutdown request. The four
`cite_facility` nodes leave both defaulted, so that is 5 + 5 = **10 s**.

Say the consequence plainly rather than softening it: **a callback that does not
return is no longer interruptible by Ctrl-C at all.** Measured, same image: a
callback holding a 12 s busy loop absorbed *three* SIGINTs and left `spin()` at
12.1 s; the same node with Python's default handler left at 1.0 s. Nothing
between the first Ctrl-C and the 10 s SIGKILL can stop it.

WHO MAY USE THIS. There is a counterweight and it decides the rule. For a
*graceful* stop, absorbing SIGINT is the safer design: it is what lets a
teardown run to completion instead of being torn apart by an asynchronous
exception at an arbitrary bytecode boundary. The hazard is only the wedged case,
and the wedged case is only dangerous when something is moving. So:

    This pattern is for a process that commands no actuator. A process that
    commands one must additionally guarantee that no callback can block
    unbounded, or install its own hard-stop path that does not depend on this
    module's shutdown.

That sentence is a constraint on adoption, not advice. A jog tool, a teach
pendant bridge or an L5 mode controller that imports this module without meeting
it has traded an operator's Ctrl-C for up to 10 s of unstoppable motion.

ADR-0034 records why this lives in its own package, and the admission test that
keeps it there is in `package.xml`.
"""

from __future__ import annotations

import signal

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.logging import get_logger
from rclpy.node import Node
# Jazzy's `rclpy.exceptions` does not export this; `rclpy.subscription` holds the
# only alias for it that is not an import of `rclpy._rclpy_pybind11` directly.
from rclpy.subscription import RCLError

#: The exceptions that can mean "the context was shut down while we were in it".
#:
#: Which exceptions carry that meaning is subtle, upstream-dependent and has
#: changed under us twice; this tuple is the one place it is written down (P1).
#: `spin` below and `cite_facility.planning_scene_loader` catch the same set and
#: then apply DIFFERENT policies to it — the loader keeps an interrupted load a
#: failure — which is the split this constant exists to make possible. Membership
#: is the shared fact; what a caller does about it is not.
#:
#: `RCLError` is the only conditional member: see `caused_by_shutdown`.
SHUTDOWN_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ExternalShutdownException,
    KeyboardInterrupt,
    RCLError,
)

#: Named rather than derived from a node, because the one thing this module logs
#: happens when the node's context is already gone.
_LOGGER_NAME = "cite_runtime"


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

    Between the two calls there used to be a hole: for the 3-24 ms `rclpy.init()`
    takes, our no-op was installed and rclpy's handler was not, so a SIGINT
    delivered in that window was absorbed and recorded nowhere — measured, a node
    signalled there was still running 10 s later, and only a second Ctrl-C
    recovered it. SIGINT is blocked across the pair instead of handled there. A
    blocked signal stays *pending*, so the unblock delivers it to the completed
    handler chain; nothing is dropped and nothing waits for a duration.
    """
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    try:
        signal.signal(signal.SIGINT, _absorb_sigint)
        rclpy.init(args=args)
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT})


def caused_by_shutdown(error: BaseException, node: Node) -> bool:
    """Say whether `error` can only mean this node's context was shut down.

    Two of `SHUTDOWN_EXCEPTIONS` say so by existing. `RCLError` does not: it is
    the general rcl failure, and it is in the set only for the wait-set race
    `spin` documents, which can arise exclusively once the context is already
    invalid. So the question is asked of the context, and only for that member.

    The context comes from the node rather than from rclpy's default. They are
    the same object for every node in this repository today, but this module is
    shared and a caller that builds its own context would otherwise get an answer
    about somebody else's.
    """
    if not isinstance(error, RCLError):
        return True
    return not rclpy.ok(context=node.context)


def spin(node: Node) -> None:
    """Spin until the context is shut down, however that shutdown was asked for.

    Three exits, one meaning; take whichever of them the executor reaches.
    Measured over 30 external SIGINTs on this stack:
    `ExternalShutdownException` 13, a plain clean return 16, `RCLError` 1. All
    thirty exited 0, and no one of the three is the "normal" one.

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

    Tolerated only while the context is already invalid, which is the single
    state in which that error can mean nothing else. `rclpy.ok()` is evaluated
    *after* the exception, by which point the context is down for essentially
    anything raised during teardown — so this clause can absorb more than the
    documented race, and the absorbed exception is therefore logged rather than
    discarded. A wait set that fails with a live context still leaves this
    function.
    """
    try:
        rclpy.spin(node)
    except SHUTDOWN_EXCEPTIONS as error:
        if not caused_by_shutdown(error, node):
            raise
        if isinstance(error, RCLError):
            get_logger(_LOGGER_NAME).info(
                f"rcl reported {str(error)!r} after the context was already "
                "invalid, which is the documented wait-set race in "
                "rclpy/executors.py; treating it as the shutdown it can only "
                "have been."
            )


def shutdown(node: Node) -> None:
    """Release the node and then the context, in that order.

    Not idempotent, and nothing here enforces once — this is the one call in a
    node's `finally`, and a second call would reach `destroy_node` on a destroyed
    node. The context half is conditional only because `rclpy.shutdown()` on an
    already-invalid context raises; that is a guard, not a re-entry guard.

    The context is taken from the node, and read before `destroy_node` so that
    the two halves cannot disagree about which context is being released.
    """
    context = node.context
    node.destroy_node()
    if rclpy.ok(context=context):
        rclpy.shutdown(context=context)
