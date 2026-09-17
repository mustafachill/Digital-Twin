#!/usr/bin/env python3
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

"""Drive each managed node to `active` by asking it to, then exit.

ADR-0058. Until this program existed the launch drove these transitions with
`OnStateTransition(configuring -> inactive)`, and `launch_ros` derives that event
from exactly one thing: a **subscription** to `/<node>/transition_event`. Both
endpoints are RELIABLE + VOLATILE, and reliable is a promise to *matched*
subscribers. A node whose `on_configure` returned before the launch's
subscription had matched published into nobody; VOLATILE meant it was never
re-sent; the activation never fired; the node sat in `inactive` forever,
published no TF, and bring-up died ten seconds later in another layer blaming
the model. That is CLAUDE.md §10's first bullet, inside `launch_ros`'s plumbing
rather than ours, and it was observed in 3 of 11 scenario launches
(`docs/open-work.md` #72).

**There is no event left to lose.** Each transition is *requested* on
`change_state` and *confirmed* on `get_state`.

**The confirmation is the gate, not the response**, and that is the load-bearing
choice rather than belt and braces. A reply can be dropped exactly as a broadcast
can — one observed run carries both `RuntimeWarning: failed to send response
(timeout)` and `Abandoning wait for the '.../change_state' service response`. So
a lost reply is not read as a failed transition: `get_state` is idempotent and
re-askable, asking again is free, and what decides is what the node says it is.
The same relationship one layer up is `cite_facility/planning_scene_loader.py`,
which applies a scene and then reads it back because `move_group` accepts a diff
it then silently drops.

**Its deadline is measured on the wall clock, deliberately**, and `use_sim_time`
is declared `False` for the reason `readiness_witness.py` gives: one of the
failures this program exists to report is a cell whose simulated clock never
starts, and a deadline in a clock that is not running cannot expire. It reads no
clock for anything else — it publishes nothing and subscribes to nothing.

**What it does not do.** It does not decide which nodes are managed. The names
arrive on `--node`, from the launch that built those nodes, so a node added to
`_facility` is driven without this file learning anything (CLAUDE.md §4 — a
value in two places). And it does not stop at `inactive`: a node that configures
and never activates is exactly the failure that was invisible, so reaching
`active` is the only success.
"""

from __future__ import annotations

import argparse
import sys
import time

from cite_runtime import runtime
from lifecycle_msgs.msg import State, Transition
from lifecycle_msgs.srv import ChangeState, GetState
import rclpy
from rclpy.client import Client
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.task import Future

#: A ceiling on a failure, never a schedule. Nothing proceeds when it expires:
#: this program exits non-zero naming the node and the step, `_gate` stops the
#: launch, and nothing downstream of the facility nodes is started. Generous
#: enough that a loaded machine still reaches `active` on three nodes whose
#: `on_configure` reads generated artifacts off disk, and short enough that a
#: node which is never going to answer is reported rather than waited on for the
#: length of a scenario.
#:
#: It covers the whole program rather than one node, because what a reader needs
#: is a bound on bring-up standing still, and the diagnosis names the node and
#: the step either way. The cost of one shared budget is that a slow first node
#: leaves the third with little of it, and an expiry would then name a healthy
#: node; `_budget_clause` states the split so that the reader can tell the two
#: apart. Raising this number is not the answer to either.
DEADLINE_S = 120.0

#: How long one wait for a `change_state` reply, or for a `get_state` answer,
#: blocks before the loop re-checks :data:`DEADLINE_S`.
#:
#: **This is a poll, and calling it anything else would be false** — the same
#: disclaimer `readiness_witness.py` carries over `wait_for_server`, and the same
#: argument applies unchanged: what makes it permitted is the ceiling, not the
#: interval. P4 forbids sleeping for a guessed duration in place of an event;
#: nothing here proceeds because a slice elapsed. Every slice is spent blocked on
#: a real answer — the transition's own reply, or the state query's — and the
#: bound only decides how often the ceiling gets a chance to be enforced.
#: Shortening or lengthening it changes no outcome, **at any value large enough
#: to block**. That qualifier is not pedantry: at `0.0` the spins stop waiting on
#: anything and the loop turns over on the ceiling check alone, which is the busy
#: wait this docstring would otherwise be denying.
_SLICE_S = 1.0

#: The two steps, in order, each as (name, the transition requested, the state
#: that confirms it). Written here rather than assembled per call so that the
#: diagnosis and the request cannot name different things.
_STEPS = (
    ("configure", Transition.TRANSITION_CONFIGURE, State.PRIMARY_STATE_INACTIVE),
    ("activate", Transition.TRANSITION_ACTIVATE, State.PRIMARY_STATE_ACTIVE),
)

#: What each confirming state is called when a diagnosis has to name it. Read
#: from the constant it confirms rather than spelled out at the point of use.
_EXPECTED_LABELS = {
    State.PRIMARY_STATE_INACTIVE: "inactive",
    State.PRIMARY_STATE_ACTIVE: "active",
}

#: Prefixes every diagnosis, so that a failure is greppable in a launch log where
#: three managed nodes, a simulator and nine spawners are writing at once.
_PREFIX = "LIFECYCLE DRIVER FAILED:"


class LifecycleDriver(Node):
    """Requests transitions and believes only `get_state` about them."""

    def __init__(self, deadline_s: float) -> None:
        super().__init__(
            "lifecycle_driver",
            # Declared rather than defaulted, and False rather than True: see
            # this module's docstring. A deadline in a clock that may never start
            # cannot expire, and expiry is the whole point of this process.
            parameter_overrides=[Parameter("use_sim_time", value=False)],
        )
        self._budget_s = deadline_s
        self._deadline = time.monotonic() + deadline_s
        # When the node currently being driven was reached. Only ever read by
        # `_budget_clause`, which exists because the ceiling above is a ceiling
        # on the whole program and an expiry has to say whose time was spent.
        self._node_started = self._deadline - deadline_s

    def drive(self, names: list[str]) -> str | None:
        """Take every node to `active`. None on success, else the diagnosis."""
        for name in names:
            self._node_started = time.monotonic()
            change = self.create_client(ChangeState, f"{name}/change_state")
            state = self.create_client(GetState, f"{name}/get_state")
            try:
                failure = self._drive_one(name, change, state)
            finally:
                # Both destroyed before the next node, so that a cell with more
                # managed nodes than this one does not accumulate clients whose
                # services are already answered.
                self.destroy_client(change)
                self.destroy_client(state)
            if failure is not None:
                return failure
            self.get_logger().info(f"{name} is active")
        return None

    def _drive_one(self, name: str, change: Client, state: Client) -> str | None:
        """Configure then activate one node, confirming each. None on success."""
        for client in (change, state):
            if not client.wait_for_service(timeout_sec=self._remaining_s()):
                return (
                    f"{_PREFIX} {name} never advertised {client.srv_name!r}. It is "
                    "the launch that started it, so either the process is not "
                    "running or it is not the node this launch believes it started."
                    + self._budget_clause(name)
                )
        for step, transition, expected in _STEPS:
            failure = self._step(name, step, transition, expected, change, state)
            if failure is not None:
                return failure
        return None

    def _step(
        self,
        name: str,
        step: str,
        transition: int,
        expected: int,
        change: Client,
        state: Client,
    ) -> str | None:
        """Request one transition and confirm it took effect. None on success."""
        wanted = _EXPECTED_LABELS[expected]
        request = ChangeState.Request()
        request.transition.id = transition
        future = change.call_async(request)

        while True:
            if not rclpy.ok(context=self.context):
                # The context went away under this loop — the cell is being torn
                # down around a driver that had not finished. Asked here rather
                # than left to whichever exception rclpy's internals raise next:
                # a shutdown reaches this loop as an `RCLError` out of the global
                # executor when the context alone was shut down, and as a bare
                # `TypeError` when `rclpy.shutdown()` was called, and only the
                # first is in `runtime.SHUTDOWN_EXCEPTIONS`. Both measured. The
                # policy is `main`'s and unchanged — an interrupted run is a
                # failure, because nothing was proven `active`.
                return (
                    f"{_PREFIX} the ROS context was shut down while {name} was "
                    f"being asked to {step}, so no managed node can be confirmed "
                    "active and nothing downstream of them is started."
                )

            if not future.done():
                # Blocked on the reply rather than on a duration. `change_state`
                # answers when the transition callback has returned, so while the
                # node is inside `on_configure` this is where the driver waits —
                # and it stops waiting the instant the answer arrives.
                self._spin(future)

            observed = self._observed(state)
            if observed is not None and observed.id == expected:
                return None

            if observed is None:
                # `get_state` is idempotent and re-askable, so an unanswered
                # query costs nothing but the slice it already spent. Asking
                # again is the right answer to silence here; treating silence as
                # a failed transition is what this program exists not to do.
                if self._expired():
                    return (
                        f"{_PREFIX} {name} never answered {state.srv_name!r}, so the "
                        f"{step} it was asked for cannot be confirmed either way."
                        + self._budget_clause(name)
                    )
                continue

            if future.done():
                # The node answered the request, so the transition callback has
                # returned and this state is the one it settled in.
                return (
                    f"{_PREFIX} {name} answered the {step} request and is in "
                    f"{observed.label!r}, not {wanted!r}{_verdict(future)}. The node "
                    "logged why, immediately above this line. Nothing downstream of "
                    "it is started, because a cell missing one of these answers some "
                    "interfaces and not others."
                )

            if self._expired():
                return (
                    f"{_PREFIX} {name} never reached {wanted!r} after being asked to "
                    f"{step}; it is in {observed.label!r} and {change.srv_name!r} has "
                    "not answered. Read the state: a transitional one means the node "
                    "is still inside the callback, and a settled one means it is no "
                    "longer transitioning — either the request never took effect, or "
                    "it took effect and was refused. The node logged which."
                    + self._budget_clause(name)
                )

    def _spin(self, future: Future) -> None:
        """Block on `future` for one slice, or not at all once the context is gone.

        The guard is here rather than left to rclpy, because of what rclpy does
        instead. `rclpy.spin_until_future_complete` asks
        `rclpy.get_global_executor` for an executor, and a context shutdown
        discards the cached one through an `on_shutdown` callback — so the next
        call builds a **fresh** executor against the dead context, and its guard
        condition fails. Measured, both ways round: `RCLError` when only the
        context was shut down, and a bare `TypeError` when `rclpy.shutdown()` was
        called, because by then `context.handle` is None. Only the first is in
        `runtime.SHUTDOWN_EXCEPTIONS`, so the second left `main` with a traceback
        in place of a diagnosis.

        Returning without spinning leaves the future unfinished, which `_step`
        and `_observed` already treat as "no answer this slice" — and the caller's
        own `rclpy.ok` check then says what happened. A shutdown landing *inside*
        a spin is not this window: the executor's own loop stops on
        `context.ok()` and the call returns normally.
        """
        if not rclpy.ok(context=self.context):
            return
        rclpy.spin_until_future_complete(self, future, timeout_sec=_SLICE_S)

    def _observed(self, state: Client) -> State | None:
        """Return what the node says it is, or None when it did not answer in a slice."""
        if not rclpy.ok(context=self.context):
            # Before `call_async`, which needs the client's handle, and not only
            # before the spin. `_step`'s own check turns this into the diagnosis.
            return None
        future = state.call_async(GetState.Request())
        try:
            self._spin(future)
            if not future.done() or future.exception() is not None:
                return None
            response = future.result()
        finally:
            # Nothing else reads this query, and an abandoned future keeps its
            # entry in the client's pending map for the life of the process.
            state.remove_pending_request(future)
        return None if response is None else response.current_state

    def _remaining_s(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def _expired(self) -> bool:
        return time.monotonic() >= self._deadline

    def _budget_clause(self, name: str) -> str:
        """Split the spent ceiling between this node and the ones before it.

        One ceiling covers the whole program, so a node reached late is given
        whatever is left and can expire having been asked a moment ago. Without
        this, the diagnosis reads identically for a node that stood still for two
        minutes and for a healthy one that arrived to find the budget gone — and
        the second sends the reader to the wrong node's logs.

        Both figures are stated rather than one of them branched on, because
        picking which to report would need a threshold on what counts as "late",
        and that is a guessed constant deciding what a failure is called.
        """
        here = max(0.0, time.monotonic() - self._node_started)
        earlier = max(0.0, self._budget_s - here)
        return (
            f" The {self._budget_s:g} s ceiling covers the whole program: about "
            f"{earlier:g} s of it went on the nodes before {name} and {here:g} s on "
            f"{name} itself. A short figure here means this node was reached late, "
            "not that it was slow."
        )


def _verdict(future: Future) -> str:
    """Report what the node said about the request, if it said anything at all.

    Reported beside the observed state and never in place of it. The state is
    what decides; this is here so that a node which answered `success` and then
    is not in the state it claimed reads as the contradiction it is.
    """
    error = future.exception()
    if error is not None:
        return f" (the request itself failed with {type(error).__name__})"
    response = future.result()
    if response is None:
        return ""
    if response.success:
        return " (it answered that the transition succeeded)"
    return " (it answered that the transition failed)"


def main(argv: list[str] | None = None) -> int:
    """Drive every named node to `active`, or name the one that did not."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--node",
        action="append",
        dest="nodes",
        # No default list: argparse appends to the default object itself, so a
        # shared `[]` accumulates across calls and a test that runs this twice
        # drives the first run's nodes again.
        default=None,
        help="A managed node's fully-qualified name. Repeatable, and given by "
             "the launch that started the node rather than restated here.",
    )
    parser.add_argument("--deadline", type=float, default=DEADLINE_S)
    args, ros_args = parser.parse_known_args(argv)
    nodes = list(args.nodes or [])

    if not nodes:
        # Refused before a context is created, because there is nothing this
        # process could go on to observe. Exiting 0 on an empty list would be a
        # gate reporting that every managed node is active having asked none of
        # them — and the launch gates the whole of the rest of bring-up on it.
        print(
            f"{_PREFIX} no managed node was named, so this would announce an "
            "`active` it never asked about. The launch passes `--node` once per "
            "node it started.",
            file=sys.stderr,
        )
        return 2

    # `cite_runtime.init` rather than `rclpy.init`, for the reason ADR-0034
    # records: this process can still be alive when the launch tears the cell
    # down, and the raw pair loses the context shutdown to a signal-handler race.
    runtime.init(args=ros_args)
    driver = LifecycleDriver(args.deadline)
    driver.get_logger().info(f"driving {len(nodes)} managed node(s) to active")
    try:
        failure = driver.drive(nodes)
    except runtime.SHUTDOWN_EXCEPTIONS as error:
        # The SET comes from `runtime` and is not restated here (P1); the POLICY
        # is this program's own, and it is the planning-scene loader's: an
        # interrupted run stays a failure, because nothing was proven `active`
        # and the whole of bring-up downstream is gated on this exit code.
        if not runtime.caused_by_shutdown(error, driver):
            raise
        failure = (
            f"{_PREFIX} interrupted by {type(error).__name__} before every managed "
            f"node was observed active ({error})."
        )
    finally:
        runtime.shutdown(driver)

    if failure is not None:
        print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
