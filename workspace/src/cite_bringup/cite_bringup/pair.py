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

"""Start both sides of a twin pair, join them, and own the pair's lifetime.

ADR-0047. **A twin pair is two independent launches. Neither waits for the other,
because neither needs anything from the other. They are joined, not sequenced.**
There is no ordering to impose between the sides and this module imposes none:
both are started at once, and what sits above them is a join and a failure rule.

**The boundary, and it is a classification rather than an intention.**

This may: start and stop operating-system processes; read their exit status; read
the standard output of processes it started; read the generated plan and resolve
each side's domain through `plan.resolve_domain_id`; own files it created.

This may not: import `rclpy` or `rclcpp`, or create any context, node, publisher,
subscription, client, service or action endpoint on either domain; set
`ROS_DOMAIN_ID` or `GZ_PARTITION` **in its own** environment in order to reach a
side — it sets them in a child's; decide anything about what crosses between the
sides, which is L5's definition and this is not L5.

**The membership test, for a design nobody anticipated:** if both sides' DDS and
both Gazebo transports were removed from the machine, this module's own code
would run unchanged, because it never speaks either. `test/test_pair.py` drives
:func:`supervise` against two processes that are not ROS at all, which is that
sentence executed rather than asserted, and holds the import graph against
`rclpy` besides. A promise that a component holds no context is not reviewable;
an import test is.

**Readiness is a line on a pipe.** Each side computes its own readiness inside
its own domain — see `readiness_witness.py` — and announces it on its own
standard output. This module's readiness fact is that token arriving on that
side's pipe. It is strictly stronger than liveness, because a process that has
not crashed has not reached the end of a gate chain, and it is not a timer: a
blocking read on a pipe has no interval.

**What it costs a developer, stated because it is a real cost.** The supervisor
owns both sides' output, so a solo bring-up's plain console becomes two labelled
interleaved streams. Every line carries its side's name as a prefix.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
import os
import queue
import signal
import subprocess
import sys
import threading
import time

from cite_bringup.plan import (
    default_plan_path,
    domain_base,
    DOMAIN_ENV,
    load,
    Plan,
    PlanError,
    resolve_domain_id,
)
from cite_bringup.readiness import announced_side

#: A ceiling on a failure, never a schedule. Nothing proceeds when it expires:
#: both sides are stopped and the pair exits non-zero, saying which side never
#: announced readiness and never exited.
#:
#: It exists because that row of ADR-0047's failure table is real — ADR-0044
#: records the silent, indefinite hang that awaits a mis-wired cross-domain
#: lifecycle client, and without a ceiling this supervisor would inherit that
#: silence instead of converting it into a diagnosis.
#:
#: **It must never be widened to absorb a slow host.** Two cells on a machine
#: that cannot hold real time will be slow, and slow is a finding about the
#: machine, not a number to raise here. **Which finding is ADR-0049's, not
#: ADR-0043 half 2's** — ADR-0043's status line says not to cite half 2's
#: wording, because with half 1's throttle in the generated world a measured
#: factor is capped at the declared factor by construction. ADR-0049 keeps the
#: 1.0 floor and puts it on two quantities, neither threshold set: capacity with
#: that throttle lifted, and the accumulated clock deficit in seconds with it in
#: force. Neither is a bring-up condition (ADR-0049 decision 4).
#:
#: **It is stated rather than derived, and nothing binds it to the ceilings a
#: side's own gate chain carries.** The readiness witness alone allows 300 s, and
#: the spawners and scene loader ahead of it carry their own. If those ever sum
#: past this number, this ceiling fires first and the pair reports "never
#: announced readiness and never exited" for a side that was about to fail with a
#: diagnosis naming the step - a strictly worse answer, produced by a number and
#: not by anything that happened. Deriving it from the chain would need the
#: launch to state its own total, which it does not; until it does, this is a
#: recorded hazard rather than a fixed one.
READY_CEILING_S = 900.0

#: How long a side is given to shut itself down after SIGINT before the group is
#: signalled, and then how long before it is killed. Both are ceilings on a
#: failure: a side that exits at once is not delayed by a millisecond.
#:
#: The first is above `simulation.launch.py`'s own teardown ceilings, which let a
#: process take 45 s before SIGTERM and 60 s before SIGKILL. A supervisor that
#: killed the group sooner would truncate the very teardown the launch is in the
#: middle of performing, and record the truncation instead of what happened.
#:
#: **Both are spent per side, because the stop loop is sequential.** Two sides
#: that both refuse to go cost `2 * (STOP_GRACE_S + STOP_KILL_S)` before the pair
#: reports, which is a stated cost rather than a measured one: nothing has ever
#: taken it. Stopping the sides concurrently would halve it and is deliberately
#: not done here, because ending a pair is the path along which evidence is most
#: easily lost (ADR-0038) and a sequential stop keeps each side's teardown
#: readable in the console.
STOP_GRACE_S = 90.0
STOP_KILL_S = 30.0

#: How often the sweep below asks whether a process group has emptied.
#:
#: A poll, stated as one. There is no event a non-parent can wait on for a
#: process group: the members of a side's group past the launch itself are
#: grandchildren, so `waitpid` cannot see them and only `killpg(pgid, 0)` answers
#: whether any of them is left. What carries the meaning is the ceiling above it,
#: whose expiry escalates to `SIGKILL`; this interval only decides how promptly
#: that happens and is not a guess about how long anything takes.
_SWEEP_POLL_S = 0.1

#: The exit status of a pair that ended because a side ended.
#:
#: Distinct from 1, which any of the refusals below the supervisor may produce,
#: so that a caller can tell "a side would not start" from "the pair ran and then
#: one half of it went away".
PAIR_ENDED = 3


@dataclass(frozen=True)
class SideSpec:
    """One side: what to run, and the environment that decides which side it is.

    ``env`` is an OVERLAY on the supervisor's own environment rather than a
    replacement, and it carries the whole of the difference between the two
    sides. That is ADR-0047 clause 1 stated as a data structure: the sides share
    every generated artifact and differ only in the environment their processes
    start in.
    """

    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)


def side_specs(
    plan: Plan, environ: Mapping[str, str], *, headless: bool = True, line: bool = False
) -> list[SideSpec]:
    """One spec per side the plan declares, in the plan's order.

    The domain is resolved through `plan.resolve_domain_id` and nowhere else: a
    second copy of `base + offset` is a value in two places, and the two copies
    disagree the first time the allocation changes (ADR-0044, clause 4).

    **`GZ_PARTITION` is deliberately not set here.** The launch builds it from
    the plan for the side it was told it is, and refuses without it; setting it
    here as well would be a second statement of a generated name, and the two
    could disagree. What this sets is the one value the launch cannot derive for
    itself, because a domain is a deployment fact rather than a modelled one.
    """
    base = domain_base(environ)
    specs = []
    for side in plan.sides:
        argv = (
            "ros2",
            "launch",
            "cite_bringup",
            "simulation.launch.py",
            f"zone:={plan.zone}",
            f"side:={side.name}",
            f"headless:={'true' if headless else 'false'}",
            f"line:={'true' if line else 'false'}",
        )
        domain = resolve_domain_id(plan, side.name, base)
        specs.append(SideSpec(side.name, argv, {DOMAIN_ENV: str(domain)}))
    return specs


@dataclass
class _Side:
    """A started side, and everything the supervisor knows about it."""

    spec: SideSpec
    process: subprocess.Popen
    #: The side's process group, CAPTURED WHEN IT STARTED rather than looked up.
    #:
    #: `os.getpgid` needs the leader to still exist, and the case the sweep below
    #: is for is precisely the one where it does not: the launch has exited, been
    #: reaped, and left everything it started running in the group. Asking for
    #: the group id then answers `ProcessLookupError` and the orphans are never
    #: signalled. `start_new_session` makes the child a session and group leader,
    #: so the group id is the pid it was started with and is known at once.
    pgid: int | None = None
    ready: bool = False
    status: int | None = None

    @property
    def name(self) -> str:
        return self.spec.name


def _start(spec: SideSpec, environ: Mapping[str, str]) -> subprocess.Popen:
    """Start one side, in its own session, with its output on a pipe we own.

    ``start_new_session`` puts the launch and everything it starts into one
    process group, which is what makes stopping a side a single signal rather
    than a search for descendants. It also detaches the side from the terminal's
    group, so an operator's Ctrl-C reaches this supervisor and is delivered to
    the sides by it — in order, and with the same teardown ceilings both times —
    rather than racing it.
    """
    env = dict(environ)
    env.update(spec.env)
    return subprocess.Popen(
        list(spec.argv),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )


def _started(spec: SideSpec, environ: Mapping[str, str]) -> _Side:
    """Start one side and record the group it owns, while its leader is alive."""
    process = _start(spec, environ)
    return _Side(spec, process, pgid=process.pid)


def _pump(side: _Side, events: queue.Queue, out) -> None:
    """Forward one side's output, labelled, and post what the supervisor needs.

    The reader and the join are the same loop on purpose. A side's readiness IS a
    line on this pipe, so there is nothing to poll and no interval to choose: the
    thread blocks in `readline` and the token arrives when the side says so.
    """
    assert side.process.stdout is not None
    for raw in side.process.stdout:
        line = raw.rstrip("\n")
        print(f"[{side.name}] {line}", file=out, flush=True)
        announced = announced_side(line)
        if announced is not None:
            events.put(("ready", side, announced))
    events.put(("exit", side, side.process.wait()))


def _stop(side: _Side, out) -> None:
    """End a side, giving its own teardown the time the launch asks for.

    SIGINT to the launch process alone first, because that is the signal `launch`
    installs a handler for and the one its documented shutdown path runs on;
    signalling the whole group here would deliver a second SIGINT to processes
    launch is already stopping. The group is only reached here if the launch
    itself does not go.

    **A side that has already exited is not this function's job and is not
    ignored either** — see :func:`_sweep`, which runs after every side's stop and
    reaches the group whether or not its leader is still there. Returning early
    here is what keeps this function about the launch's own teardown.
    """
    if side.process.poll() is not None:
        return
    print(f"[pair] stopping {side.name}", file=out, flush=True)
    try:
        side.process.send_signal(signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        side.process.wait(timeout=STOP_GRACE_S)
        return
    except subprocess.TimeoutExpired:
        print(
            f"[pair] {side.name} did not stop within {STOP_GRACE_S:g} s of SIGINT; "
            "signalling its process group",
            file=out,
            flush=True,
        )
    _signal_group(side, signal.SIGTERM)
    try:
        side.process.wait(timeout=STOP_KILL_S)
        return
    except subprocess.TimeoutExpired:
        print(f"[pair] killing {side.name}", file=out, flush=True)
    _signal_group(side, signal.SIGKILL)


def _signal_group(side: _Side, number: int) -> None:
    try:
        if side.pgid is not None:
            os.killpg(side.pgid, number)
    except (ProcessLookupError, PermissionError):
        pass


def _group_is_empty(side: _Side) -> bool:
    """Whether nothing is left in this side's process group."""
    if side.pgid is None:
        return True
    try:
        os.killpg(side.pgid, 0)
    except (ProcessLookupError, PermissionError):
        return True
    return False


def _sweep(sides: Sequence[_Side], out) -> None:
    """Signal every side's whole process group, INCLUDING sides already reaped.

    **`_stop` returns the moment a side's launch has gone, and a launch that died
    on a signal takes its own supervision with it.** Everything it started is
    reparented and keeps running: this repository has documented `move_group`,
    `skill_server`, `parameter_bridge` and `gz` all dying that way at teardown,
    and an orphaned `gz sim` holds that side's `GZ_PARTITION` — so the pair
    reports both statuses, exits, and leaves a Gazebo server occupying the
    transport the next run of that side will look for. That is the orphan this
    project already knows the cost of, one process group up.

    Unconditional, because "the launch has already exited" is exactly the case
    that produces the orphan; a sweep that skipped reaped sides would skip the
    only sides that need it. It is also the only thing that reaches a side at all
    when the supervisor is asked to stop, since `start_new_session` detaches both
    sides from the terminal's group and an operator's Ctrl-C never gets to them.

    `SIGTERM` to every group first, so that anything still running gets its own
    teardown, then `SIGKILL` to whatever has not gone by the same ceiling the
    stop above uses. A group with nothing in it costs one `ProcessLookupError`,
    which :func:`_signal_group` already swallows.
    """
    for side in sides:
        _signal_group(side, signal.SIGTERM)
    deadline = time.monotonic() + STOP_KILL_S
    while any(not _group_is_empty(side) for side in sides):
        if time.monotonic() >= deadline:
            for side in sides:
                if _group_is_empty(side):
                    continue
                print(
                    f"[pair] {side.name} left processes running {STOP_KILL_S:g} s "
                    "after its group was asked to stop; killing them",
                    file=out,
                    flush=True,
                )
                _signal_group(side, signal.SIGKILL)
            return
        time.sleep(_SWEEP_POLL_S)


def supervise(
    specs: Sequence[SideSpec],
    *,
    environ: Mapping[str, str] | None = None,
    ceiling_s: float = READY_CEILING_S,
    out=None,
) -> int:
    """Start every side at once, join them, and own the pair until it ends.

    The whole of ADR-0047 clause 4's failure table, and nothing else:

    ==================================== =========================================
    What happens                         What this does
    ==================================== =========================================
    A side exits before announcing        stop the other, exit non-zero naming
                                          which side and its status
    Both exit before announcing           the same, reporting BOTH statuses
    A side exits after both announced     the same; the pair ends
    Neither announces, neither exits      the ceiling fires: stop both, and say
                                          that the side never announced readiness
                                          AND never exited, rather than "timeout"
    ==================================== =========================================

    Nothing in here knows what a ROS domain is. It is given argument vectors and
    environment overlays, it reads pipes, and it reads exit statuses — which is
    why the membership test can drive it against two processes that are not ROS.
    """
    out = sys.stdout if out is None else out
    environ = os.environ if environ is None else environ

    events: queue.Queue = queue.Queue()
    sides = [_started(spec, environ) for spec in specs]
    for side in sides:
        threading.Thread(target=_pump, args=(side, events, out), daemon=True).start()

    print(
        "[pair] started " + ", ".join(s.name for s in sides) + "; waiting for each "
        "side to announce its own readiness",
        file=out,
        flush=True,
    )

    interrupted = False
    with _stop_requests(events):
        interrupted = _join(sides, events, ceiling_s, out)
    # Drained BEFORE anything is stopped, and that ordering is the point. When
    # two sides fail for one reason they fail together, and a side stopped by
    # this supervisor reports the stop rather than whatever it was reporting -
    # which is ADR-0038's lesson one level up: ending a process to report a
    # fault takes the evidence of the fault with it. Anything already on the
    # queue is that evidence, and it costs nothing to read it first.
    _drain(events)
    for side in sides:
        _stop(side, out)
        if side.status is None:
            side.status = side.process.poll()
    # After every side's own stop, and unconditionally. `_stop` reaches a side
    # whose launch is still running; this reaches what a launch that has already
    # gone left behind, which is the half nothing else covers.
    _sweep(sides, out)
    return _verdict(sides, interrupted, out)


def _drain(events: queue.Queue) -> None:
    """Apply every event already queued, without waiting for another."""
    while True:
        try:
            kind, side, payload = events.get_nowait()
        except queue.Empty:
            return
        if kind == "exit" and side is not None and side.status is None:
            side.status = payload


@contextmanager
def _stop_requests(events: queue.Queue):
    """Turn SIGINT and SIGTERM into an event, for the length of one pair.

    The pair's whole state is in one queue, so an operator asking it to stop has
    to arrive there too - otherwise the request races the join and is handled in
    two places. It is caught rather than allowed to kill this process because a
    supervisor that dies leaves two detached launches nobody owns, which is the
    orphaned `gz sim` this project already knows the cost of.

    SIGTERM as well as SIGINT: a container stop sends the former, and
    `KeyboardInterrupt` covers only the latter.

    Restored on the way out, and skipped entirely off the main thread, where
    `signal.signal` is not available - a test driving :func:`supervise` from a
    worker thread gets the join and the failure rule without the handlers.

    **A known hazard, recorded rather than fixed, because the fix is bigger than
    the defect.** `Queue.put` takes the queue's own lock, and a Python signal
    handler runs in the main thread between bytecodes - including between the
    bytecodes of :func:`_join`'s `events.get`, which holds that same lock while
    it inspects the queue. A signal arriving in that window would deadlock the
    supervisor against itself, and the ceiling could not fire either, because the
    ceiling is enforced by the call that is stuck. The window is narrow, this has
    never been observed, and the reason it is not repaired here is that the
    repair is a self-pipe plus a reader thread - new mechanism on the teardown
    path, where a bug is worse than the one it removes. Whoever needs it should
    write the reader thread rather than moving the `put`.
    """
    previous: dict[int, object] = {}

    def request(number: int, frame: object) -> None:  # noqa: ARG001 - signal shape
        events.put(("stop", None, number))

    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, request)
    except ValueError:
        previous.clear()
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _join(sides: Sequence[_Side], events: queue.Queue, ceiling_s: float, out) -> bool:
    """Block until the pair is up and then until it ends. Return whether asked to.

    Two phases and one loop. Before the join the wait carries the ceiling, whose
    expiry is a failure; after it there is nothing left to time — a pair that is
    up ends when a side ends or when somebody asks it to, and neither is an
    interval.
    """
    deadline = time.monotonic() + ceiling_s
    while True:
        joined = all(side.ready for side in sides)
        timeout = None if joined else max(0.0, deadline - time.monotonic())
        try:
            kind, side, payload = events.get(timeout=timeout)
        except queue.Empty:
            _report_ceiling(sides, ceiling_s, out)
            return False
        if kind == "stop":
            print(
                f"[pair] asked to stop (signal {payload}); ending both sides",
                file=out,
                flush=True,
            )
            return True
        if kind == "ready":
            if payload != side.name:
                print(
                    f"[pair] {side.name} announced readiness as {payload!r}. A side "
                    "announces the side it was started as, so this launch was given "
                    "the wrong side:= argument and the pair is not what it says.",
                    file=out,
                    flush=True,
                )
                return False
            side.ready = True
            if all(s.ready for s in sides):
                print(
                    "[pair] both sides announced readiness; the pair is up",
                    file=out,
                    flush=True,
                )
        else:
            side.status = payload
            print(
                f"[pair] {side.name} exited {payload}", file=out, flush=True
            )
            return False


def _report_ceiling(sides: Iterable[_Side], ceiling_s: float, out) -> None:
    for side in sides:
        if side.ready:
            continue
        print(
            f"[pair] {side.name} never announced readiness and never exited, "
            f"within {ceiling_s:g} s. That is not a slow side: every step of its "
            "bring-up either completes or fails, so a side in neither state is "
            "one that is waiting on something that will not arrive.",
            file=out,
            flush=True,
        )


def _verdict(sides: Sequence[_Side], interrupted: bool, out) -> int:
    """Report both sides' statuses, never only the first, and grade the run."""
    for side in sides:
        print(
            f"[pair] {side.name}: ready={side.ready} status={side.status}",
            file=out,
            flush=True,
        )
    if interrupted and all(side.ready for side in sides):
        # The pair came up and an operator ended it. That is what asking for a
        # pair and then stopping it looks like, and it is not a failure.
        return 0
    if not all(side.ready for side in sides):
        return 1
    return PAIR_ENDED


#: The `key:=value` arguments `./scripts/sim` forwards, and the option each one
#: means here. The solo path is `ros2 launch`, which takes that spelling, so
#: `./scripts/sim --headless line:=true` works and `./scripts/sim --pair
#: line:=true` used to fail with an argparse error - the same request, refused
#: only because the pair path is a Python program rather than a launch file. A
#: paired line could not be started through the entry point at all.
#:
#: Translated here rather than in `scripts/sim`, because the shell would then
#: hold a second statement of which arguments a pair takes.
_LAUNCH_STYLE = {
    "zone": "--zone",
    "line": "--line",
    "headless": "--headless",
    "ceiling": "--ceiling",
}

#: The values `ros2 launch` reads as true and false for a boolean argument, and
#: the same ones `simulation.launch.py` reads. Anything else is refused rather
#: than treated as false, which is what a launch argument's own reader does not
#: do and is the one place this is deliberately stricter.
_TRUE = ("true", "1")
_FALSE = ("false", "0")


def _flags(argv: Sequence[str], parser: argparse.ArgumentParser) -> list[str]:
    """Rewrite `ros2 launch`'s `key:=value` arguments as this parser's options."""
    rewritten: list[str] = []
    for token in argv:
        key, separator, value = token.partition(":=")
        if not separator:
            rewritten.append(token)
            continue
        option = _LAUNCH_STYLE.get(key)
        if option is None:
            parser.error(
                f"unknown launch argument {token!r}. A pair takes "
                + ", ".join(f"{name}:=" for name in sorted(_LAUNCH_STYLE))
                + ", which is a smaller set than a single side's launch: the "
                "rest are per-side and a pair has two."
            )
        if option in ("--line", "--headless"):
            if value.lower() in _TRUE:
                rewritten.append(option)
            elif value.lower() not in _FALSE:
                parser.error(
                    f"{token!r} is not a boolean. Use {key}:=true or {key}:=false."
                )
            continue
        rewritten.extend([option, value])
    return rewritten


def main(argv: list[str] | None = None) -> int:
    """Resolve both sides from the plan and supervise them."""
    parser = argparse.ArgumentParser(description="Bring up both sides of a twin pair.")
    parser.add_argument("--zone", default="cell_a")
    parser.add_argument(
        "--headless", action="store_true", help="Run both simulators without a GUI."
    )
    parser.add_argument(
        "--line", action="store_true", help="Start the L4 coordinator on each side."
    )
    parser.add_argument("--ceiling", type=float, default=READY_CEILING_S)
    args = parser.parse_args(
        _flags(sys.argv[1:] if argv is None else argv, parser)
    )

    try:
        plan = load(default_plan_path(args.zone))
        specs = side_specs(plan, os.environ, headless=args.headless, line=args.line)
    except PlanError as exc:
        print(f"PAIR BRING-UP FAILED: {exc}", file=sys.stderr)
        return 1
    if len(specs) < 2:
        # Not an error to be repaired here. Whether a zone runs as a pair is an
        # L0 fact, and inventing a second side would be bring-up deciding what
        # the facility is (P5).
        print(
            f"PAIR BRING-UP FAILED: zone {plan.zone!r} declares "
            f"{len(specs)} side(s). A pair needs two; set `twin: {{sides: pair}}` "
            "on the zone in the L0 model and regenerate.",
            file=sys.stderr,
        )
        return 1
    return supervise(specs, ceiling_s=args.ceiling)


if __name__ == "__main__":
    sys.exit(main())
