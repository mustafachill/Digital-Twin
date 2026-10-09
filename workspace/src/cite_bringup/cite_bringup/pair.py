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

**It starts L5, and it is still not L5** (ADR-0057). The supervisor is the only
component that knows both sides are ready, so it is the only one positioned to
start the twin boundary on that event rather than on somebody's judgement of when
the console looks settled. **Starting a process is not deciding what crosses:**
it hands the boundary the two facts it already holds — which zone this is, and
where the plan is — and gains no branch on modes, routing, skills or divergence.
A change here that passes a mode, a side preference or a skill list has crossed
that line and needs its own record.

**It may start the plant alone** (ADR-0072, amending ADR-0057), when it is
told to: `--sides plant`. Which sides start is decided by the hardware opt-in,
in `./scripts/sim` (`program.sides.pair_sides`), and handed here explicitly; it
is never inferred in this module. The boundary and the console are handed the
same choice, as an argument, so that every participant knows the deployment it
is part of rather than discovering it from a domain that is silent. A pair of
both sides still ends when either side exits.

**It starts the operator console the same way, one step later, ONLY WHEN ASKED**
(ADR-0071, `--console`; `./scripts/sim --pair --console`): `cell_console`, with
the plant's domain as its own, once the boundary has announced, because every
request the console serves goes through the boundary. It is handed the zone,
the plan and the plant's domain, and starts no motion. Stopping the pair stops
it first, the boundary next and the sides last. `./scripts/program` never asks
for it: a pair that did not request a console has none to end it.

**That dependency is one argument vector, and it is deliberately not declared in
`package.xml`.** `cite_twin` build-depends on this package, so an `exec_depend`
back would be a cycle colcon refuses to order. The program is resolved on the
ament index at run time instead, and a workspace without it does not fail
silently: `ros2 run` exits non-zero at once and the pair reports the BOUNDARY
exiting, which is the diagnosis ADR-0057 asks for.

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
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
import os
from pathlib import Path
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
    PLANT_SIDE,
    resolve_domain_id,
)
from cite_bringup.readiness import announced_boundary, announced_console, announced_side

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
#: side's own gate chain carries.** `lifecycle_driver.py` allows 120 s at the
#: head of the chain, before anything else in it starts (ADR-0058); the readiness
#: witness at the tail allows 300 s; and the spawners and scene loader between
#: them carry their own. The driver's is listed because it is new and because an
#: inventory that is silently incomplete is worse than none — this list is the
#: only auditable statement of the chain that exists. If those ever sum
#: past this number, this ceiling fires first and the pair reports "never
#: announced readiness and never exited" for a side that was about to fail with a
#: diagnosis naming the step - a strictly worse answer, produced by a number and
#: not by anything that happened. Deriving it from the chain would need the
#: launch to state its own total, which it does not; until it does, this is a
#: recorded hazard rather than a fixed one.
READY_CEILING_S = 900.0

#: A ceiling on a failure, never a schedule. Nothing proceeds when it expires:
#: every participant is stopped and the pair exits non-zero, saying that THE
#: BOUNDARY never announced readiness and never exited.
#:
#: **Its own number, and not an extension of `READY_CEILING_S`** (ADR-0057's
#: correction of 2026-09-18). The join drops that ceiling on the very iteration
#: it completes — `_join` sets its wait to `None` once every participant is
#: ready — so the boundary, which is started at exactly that point, would
#: otherwise be covered by no ceiling at all and a boundary that hung would leave
#: this supervisor waiting for ever. Widening the one above instead would put two
#: waits that measure different things behind one number, and that number is
#: already recorded as stated rather than derived; a second contributor makes it
#: harder to derive, not easier.
#:
#: **Shorter than a side's, because the boundary starts no cell.** Both sides
#: have already announced when it starts: it reads a plan, opens one context per
#: side, creates its endpoints and reaches its executor. There is no simulator,
#: no controller manager and no planner in that list, so this is not a bring-up
#: ceiling scaled down — it is how long a process with nothing to wait for may be
#: silent before the silence is the fault.
#:
#: **It must never be widened to absorb a slow host**, for the reason the ceiling
#: above gives at length and which is not restated here.
BOUNDARY_CEILING_S = 120.0

#: How long a side is given to shut itself down after SIGINT before the group is
#: signalled, and then how long before it is killed. Both are ceilings on a
#: failure: a side that exits at once is not delayed by a millisecond.
#:
#: The first is above `simulation.launch.py`'s own teardown ceilings, which let a
#: process take 45 s before SIGTERM and 60 s before SIGKILL. A supervisor that
#: killed the group sooner would truncate the very teardown the launch is in the
#: middle of performing, and record the truncation instead of what happened.
#:
#: **Both are spent per PARTICIPANT, because the stop loop is sequential.** Two
#: sides that both refuse to go cost `2 * (STOP_GRACE_S + STOP_KILL_S)` before
#: the pair reports, which is a stated cost rather than a measured one: nothing
#: has ever taken it. **The boundary is a third participant and extends it to
#: `3 * (STOP_GRACE_S + STOP_KILL_S)` in the worst case** (ADR-0057), and the
#: operator console a fourth to `4 *` (ADR-0071), and that is
#: recorded here rather than hidden by lowering either number — a teardown
#: ceiling shortened to keep a worst case tidy truncates the teardown it was
#: measuring. Stopping them concurrently would divide it and is deliberately not
#: done here, because ending a pair is the path along which evidence is most
#: easily lost (ADR-0038) and a sequential stop keeps each participant's teardown
#: readable in the console. `teardown_ceiling_s` states that worst case for a
#: caller that has to wait it out (`./scripts/program`), from these numbers.
STOP_GRACE_S = 90.0
STOP_KILL_S = 30.0


#: `--sides`: the plant alone, or every side the plan declares (ADR-0072). The
#: boundary takes the same two words (`cite_twin.twin_boundary.SIDES_CHOICES`),
#: and `test_pair.py` holds the two equal; neither package imports the other's.
SIDES_PLANT = "plant"
SIDES_ALL = "all"
SIDES_CHOICES = (SIDES_PLANT, SIDES_ALL)


def started_sides(plan: Plan, sides: str) -> list[str]:
    """Return the side names a pair of ``plan`` starts for a ``--sides`` choice, in plan order."""
    if sides not in SIDES_CHOICES:
        raise ValueError(f"--sides is {sides!r}, not one of {', '.join(SIDES_CHOICES)}")
    names = [side.name for side in plan.sides]
    return [PLANT_SIDE] if sides == SIDES_PLANT else names


def participants(plan: Plan, console: bool, sides: str) -> int:
    """Count the participants a pair of ``plan`` stops: each side started, the boundary, any console."""
    return len(started_sides(plan, sides)) + 1 + (1 if console else 0)


def teardown_ceiling_s(count: int) -> float:
    """How long a caller waits for a pair of ``count`` participants to stop after its SIGINT.

    The supervisor's own worst case - each participant, one after another,
    given `STOP_GRACE_S + STOP_KILL_S` - and one more `2 * STOP_KILL_S` above
    it, so that a supervisor still escalating on its own is not cut short. A
    ceiling on a failure, never a schedule.
    """
    return count * (STOP_GRACE_S + STOP_KILL_S) + 2 * STOP_KILL_S


#: How often the sweep below asks whether a process group has emptied.
#:
#: A poll, stated as one. There is no event a non-parent can wait on for a
#: process group: the members of a side's group past the launch itself are
#: grandchildren, so `waitpid` cannot see them and only `killpg(pgid, 0)` answers
#: whether any of them is left. What carries the meaning is the ceiling above it,
#: whose expiry escalates to `SIGKILL`; this interval only decides how promptly
#: that happens and is not a guess about how long anything takes.
_SWEEP_POLL_S = 0.1

#: What the boundary is reported as. Deliberately not a side's name: a failure
#: of it that read `plant` or `counterpart` would send the reader to a cell that
#: is up and working.
BOUNDARY_NAME = "boundary"

#: What the operator console is reported as (ADR-0071), for the same reason.
CONSOLE_NAME = "console"

#: Where a participant's first SIGINT is delivered: to its leader alone, or to
#: its whole process group.
#:
#: **Data rather than a branch on what the participant is**, for the reason every
#: other difference between a side and the boundary is data: the supervisor does
#: the same four things to all three participants, and a `if it is the boundary`
#: on the teardown path is the shape this module has kept out of every other one.
#:
#: **It is a property of the command, not of the participant's purpose.** A side
#: is `ros2 launch`, which runs the launch service IN ITS OWN PROCESS and installs
#: the SIGINT handler its documented shutdown path runs on — so the leader is the
#: right and only target, and signalling the group would deliver a second SIGINT
#: to processes launch is already stopping.
#:
#: The boundary is `ros2 run`, which does neither. `ros2run.api.run_executable`
#: is `subprocess.Popen(cmd)` followed by a loop that catches `KeyboardInterrupt`
#: and **continues waiting** — it forwards nothing, because the case it was
#: written for is a terminal delivering the signal to the whole foreground group
#: itself. This supervisor starts every participant in a session of its own
#: precisely so that no terminal does that, so the program `ros2 run` started is
#: a GRANDCHILD reachable only by the group signal. A leader-only SIGINT there
#: reaches `ros2`, which swallows it, and the boundary is never asked to stop at
#: all: it spends `STOP_GRACE_S` in full and is then killed by the escalation
#: instead of running its own `stop()` and `rclpy` shutdown.
#:
#: **The ceilings are not what is wrong with that and must not be touched.**
#: `STOP_GRACE_S` is correctly sized for a launch teardown; what was wrong is
#: that one participant was never sent the signal the ceiling is timing.
STOP_LEADER = "leader"
STOP_GROUP = "group"

#: What to add when a SIDE neither announced nor exited within its ceiling.
_A_SIDE_IN_NEITHER_STATE = (
    "That is not a slow side: every step of its bring-up either completes or "
    "fails, so a side in neither state is one that is waiting on something that "
    "will not arrive."
)

#: And when the BOUNDARY does not, which is a different diagnosis and sends the
#: reader somewhere else. Both sides had already announced when it was started,
#: so nothing it is waiting for is a cell coming up.
_THE_BOUNDARY_IN_NEITHER_STATE = (
    "That is the twin boundary and not a side, and both sides had announced "
    "before it was started — so it is not waiting for a cell to come up. It "
    "reads the plan, opens one context per side and announces only once its own "
    "endpoints are being served; a boundary in neither state reached none of "
    "those and is holding a context on each side's domain while it does not."
)

#: And when the CONSOLE does not. The boundary had announced when it was
#: started, so it is not waiting for anything to come up either.
_THE_CONSOLE_IN_NEITHER_STATE = (
    "That is the operator console, started once the twin boundary had announced "
    "- so it is not waiting for a cell or for the boundary. It reads the plan, "
    "configures and activates itself and announces only once its own endpoints "
    "are being served; it commands nothing until an operator asks."
)

#: The exit status of a pair that ended because a side ended.
#:
#: Distinct from 1, which any of the refusals below the supervisor may produce,
#: so that a caller can tell "a side would not start" from "the pair ran and then
#: one half of it went away".
PAIR_ENDED = 3


@dataclass(frozen=True)
class SideSpec:
    """One participant: what to run, and the environment that says which it is.

    ``env`` is an OVERLAY on the supervisor's own environment rather than a
    replacement, and it carries the whole of the difference between the two
    sides. That is ADR-0047 clause 1 stated as a data structure: the sides share
    every generated artifact and differ only in the environment their processes
    start in.

    **The twin boundary is described by this same record** (ADR-0057), because
    everything this supervisor does to a participant is the same for all three:
    start it in its own session, read its pipe for its announcement, stop it,
    sweep its group. What differs between a side and the boundary is the five
    optional fields below — which word it announces, what that word has to say,
    which argument decided that, what its silence means, and where its first
    SIGINT is delivered — and every one of them is data rather than a branch.

    **Two differences are NOT fields here, and saying which keeps this list
    honest.** The ceiling a participant's silence is measured against is control
    flow rather than data: `_join` carries one ceiling before the join and the
    other after it, because it is a property of the phase and not of the
    participant. And which participant is stopped first is decided in
    :func:`supervise` from the spec it was handed, because it is a property of
    the list and not of any one member of it.
    """

    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    #: Which of this participant's output lines is its announcement, and what it
    #: announces. Two tokens, one pump: a participant's readiness is a line on
    #: its own pipe whatever the participant is, and the words are different so
    #: that two copies of one announcement cannot be read as two participants.
    announcement: Callable[[str], str | None] = announced_side
    #: What that line has to say for this participant to be the one that said it.
    #: Empty means "its own name", which is a side; the boundary announces the
    #: zone it spans. Either way it is a fact the supervisor already holds, and
    #: the redundancy is the check.
    announces: str = ""
    #: The argument that decided `announces`, named in the diagnosis when the
    #: announcement disagrees with it. A reader who is told only that two strings
    #: differ has to find out which knob sets them.
    argument: str = "side:="
    #: What to say when this participant neither announces nor exits. The ceiling
    #: is the same mechanism for all three and the diagnosis is not.
    silence: str = _A_SIDE_IN_NEITHER_STATE
    #: Where this participant's first SIGINT goes: `STOP_LEADER` for a command
    #: that installs its own handler, `STOP_GROUP` for one that forwards nothing
    #: to the program it started. See those two constants for why the answer is
    #: a property of the command rather than of what the participant is for.
    stop_reach: str = STOP_LEADER
    #: What the console calls this participant when it starts it after the
    #: join and when it announces. Empty for a side, which the join reports as
    #: one of "both sides".
    title: str = ""


def side_specs(
    plan: Plan,
    environ: Mapping[str, str],
    *,
    headless: bool = True,
    sides: str = SIDES_ALL,
) -> list[SideSpec]:
    """One spec per side started, in the plan's order: every side, or the plant alone.

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
    chosen = started_sides(plan, sides)
    for side in plan.sides:
        if side.name not in chosen:
            continue
        domain = resolve_domain_id(plan, side.name, base)
        argv = side_launch(plan, side.name, headless)
        specs.append(SideSpec(side.name, argv, {DOMAIN_ENV: str(domain)}))
    return specs


#: The launch that starts a side whose hardware is physical (ADR-0070 item 6),
#: and the one that starts a simulated side. Which one a side gets is read off
#: the plan by `side_launch`, never off an asset's type.
HARDWARE_LAUNCH = "hardware.launch.py"
SIMULATION_LAUNCH = "simulation.launch.py"


def side_launch(plan: Plan, side: str, headless: bool) -> tuple[str, ...]:
    """Return the argument vector that starts ``side``, chosen by what its hardware is.

    A side on which any asset declares physical hardware is started by
    `hardware.launch.py`, which asks the hardware opt-in and starts no
    simulator; every other side by `simulation.launch.py`, which refuses a
    physical side whatever it is told. The answer is the plan's declared fact
    (`commands_physical_hardware_on_or_none`), so a backend's name decides
    nothing (ADR-0054). A physical side has no window, so it takes no
    `headless`.
    """
    physical = any(
        manager.commands_physical_hardware_on_or_none(side) is True
        for manager in plan.controller_managers
    )
    if physical:
        return (
            "ros2",
            "launch",
            "cite_bringup",
            HARDWARE_LAUNCH,
            f"zone:={plan.zone}",
            f"side:={side}",
        )
    return (
        "ros2",
        "launch",
        "cite_bringup",
        SIMULATION_LAUNCH,
        f"zone:={plan.zone}",
        f"side:={side}",
        f"headless:={'true' if headless else 'false'}",
    )


def boundary_spec(plan: Plan, path: Path | str, sides: str = SIDES_ALL) -> SideSpec:
    """Return the third participant: the boundary spanning the two sides above.

    **Two arguments and nothing else, and that is ADR-0057's load-bearing
    sentence rather than an economy.** The supervisor hands over the two facts
    it already holds — which zone this is, and where the plan is — and every
    decision about what crosses stays inside `cite_twin` where ADR-0050 put it.
    In particular it does not pass `divergence_period_s`: that is a ROS
    parameter, passing it would mean appending `--ros-args`, and a supervisor
    that states a value L5 declares is a value in two places (P1).

    **No environment overlay, and that is not an omission either.** A side is
    told which domain it is on because a side is one domain; the boundary holds
    a context on BOTH and resolves each of them itself, from `CITE_DOMAIN_BASE`
    and the plan, through the same `resolve_domain_id` that resolved the sides.
    There is no single `ROS_DOMAIN_ID` that would be right for it, and setting
    one would put it on a side.

    Both `--zone` and `--plan`, though the boundary reads the zone off the plan:
    the two are checked against each other there, and a supervisor that passed
    only the path would be handing over a cell name it never stated.

    **And `--sides`** (ADR-0072): which sides were started, so a pair started
    with the plant alone has a boundary that opens no context on the
    counterpart's domain and refuses every mode but SIM. That is a fact about
    the deployment this supervisor started, not a decision about what crosses.
    """
    return SideSpec(
        BOUNDARY_NAME,
        (
            "ros2",
            "run",
            "cite_twin",
            # The installed program's own file name. `cite_twin` installs it
            # under PROGRAMS rather than as a console script, so this is the
            # spelling `ros2 run` resolves and the one its launch tests use.
            "twin_boundary.py",
            "--zone",
            plan.zone,
            "--plan",
            str(path),
            "--sides",
            sides,
        ),
        announcement=announced_boundary,
        announces=plan.zone,
        argument="--zone",
        silence=_THE_BOUNDARY_IN_NEITHER_STATE,
        # `ros2 run` forks and forwards nothing, so the program above is a
        # grandchild and the group signal is the only one that reaches it. See
        # `STOP_GROUP`, and note that this is a fact about the first token of
        # `argv` and would change if that token did.
        stop_reach=STOP_GROUP,
        title="the twin boundary",
    )


def console_spec(
    plan: Plan, path: Path | str, environ: Mapping[str, str], sides: str = SIDES_ALL
) -> SideSpec:
    """Return the fourth participant, when asked for: the operator console (ADR-0071).

    Started once the boundary has announced, because every request it serves
    goes through the boundary's `/cite/twin/...` names on the plant's domain.
    The same two facts the boundary is handed - the zone and the plan - and the
    one environment value a side is handed, its domain: the plant's, resolved
    through `resolve_domain_id` like a side's, where its node and its requests
    live. It is nonetheless a CROSS-DOMAIN CLIENT, as `program.home` and
    `program.belt` are: Start robot and Home call each physical side's
    `InitializeAsset` (and that side's track stop) on that side's own domain,
    and Start program commands each simulated side's belt on that side's
    domain - each from the plan, in a context of its own. Starting it commands
    nothing; it waits for an operator.
    """
    domain = resolve_domain_id(plan, PLANT_SIDE, domain_base(environ))
    return SideSpec(
        CONSOLE_NAME,
        (
            "ros2",
            "run",
            "cite_bringup",
            # Installed under PROGRAMS, like the boundary's.
            "cell_console.py",
            "--zone",
            plan.zone,
            "--plan",
            str(path),
            "--sides",
            sides,
        ),
        {DOMAIN_ENV: str(domain)},
        announcement=announced_console,
        announces=plan.zone,
        argument="--zone",
        silence=_THE_CONSOLE_IN_NEITHER_STATE,
        # `ros2 run`, as the boundary: only the group signal reaches it.
        stop_reach=STOP_GROUP,
        title="the operator console",
    )


@dataclass
class _Side:
    """A started participant, and everything the supervisor knows about it."""

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

    @property
    def announces(self) -> str:
        """Return what this participant must announce for an announcement to be its.

        A side announces its own name, which the spec already carries, so the
        spec states it only where it is something else. Defaulting it here
        rather than at every construction site keeps the two `SideSpec`
        factories from repeating what one of them already said (P1).
        """
        return self.spec.announces or self.spec.name


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


def _launch(
    spec: SideSpec, environ: Mapping[str, str], events: queue.Queue, out
) -> _Side:
    """Start one participant, record the group it owns, and read its pipe.

    The group is recorded while its leader is alive, and the pump is started
    here rather than by the caller so that no participant can be started without
    one: a process whose pipe nothing reads can neither announce nor be seen to
    exit, and would be invisible to the join that is about to wait for it.
    """
    process = _start(spec, environ)
    started = _Side(spec, process, pgid=process.pid)
    threading.Thread(target=_pump, args=(started, events, out), daemon=True).start()
    return started


def _pump(side: _Side, events: queue.Queue, out) -> None:
    """Forward one side's output, labelled, and post what the supervisor needs.

    The reader and the join are the same loop on purpose. A participant's
    readiness IS a line on this pipe, so there is nothing to poll and no interval
    to choose: the thread blocks in `readline` and the token arrives when the
    participant says so.

    Which token is the participant's own, off its spec, so that this one reader
    serves a side and the boundary without knowing which it is holding.
    """
    assert side.process.stdout is not None
    for raw in side.process.stdout:
        line = raw.rstrip("\n")
        print(f"[{side.name}] {line}", file=out, flush=True)
        announced = side.spec.announcement(line)
        if announced is not None:
            events.put(("ready", side, announced))
    events.put(("exit", side, side.process.wait()))


def _stop(side: _Side, out) -> None:
    """End a participant, giving its own teardown the time its command asks for.

    SIGINT first, **to whichever of its leader and its group its spec says
    reaches the program that has to handle it** — `STOP_LEADER` for `ros2
    launch`, which installs the handler itself, and `STOP_GROUP` for `ros2 run`,
    which installs none and forwards nothing to the grandchild it started. Those
    two constants carry the reasoning; what matters here is that both spellings
    are one signal at one ceiling and the difference is data.

    A leader that is sent a signal the program behind it never receives is not a
    slow teardown: it is a participant that was never asked to stop, spending the
    whole grace below before the escalation kills it. **The ceiling is not the
    defect in that and is not to be shortened for it.**

    **A side that has already exited is not this function's job and is not
    ignored either** — see :func:`_sweep`, which runs after every side's stop and
    reaches the group whether or not its leader is still there. Returning early
    here is what keeps this function about the launch's own teardown.
    """
    if side.process.poll() is not None:
        return
    print(f"[pair] stopping {side.name}", file=out, flush=True)
    if side.spec.stop_reach == STOP_GROUP:
        _signal_group(side, signal.SIGINT)
    else:
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
    boundary: SideSpec | None = None,
    console: SideSpec | None = None,
    environ: Mapping[str, str] | None = None,
    ceiling_s: float = READY_CEILING_S,
    boundary_ceiling_s: float = BOUNDARY_CEILING_S,
    out=None,
) -> int:
    """Start every side at once, join them, start the boundary, and own the pair.

    ADR-0047 clause 4's failure table, and ADR-0057's three rows under it:

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
    Both sides announce                   the boundary is started, on that event
                                          and on nothing else
    The boundary exits before announcing  stop everything, exit non-zero naming
                                          THE BOUNDARY and its status
    The boundary is silent                its own ceiling fires, saying the
                                          boundary never announced and never
                                          exited
    A side exits while the boundary       stop everything; the pair never
    is starting                           completed, so this grades 1 and not
                                          PAIR_ENDED - see :func:`_verdict`
    ==================================== =========================================

    ``console`` (ADR-0071) is started the same way one step later, and only
    when the caller asked for one (`--console`): once the boundary has
    announced, on that event, under the boundary's ceiling. Asked for, it is a
    participant like the others - its exit ends the pair, because a pair whose
    operator surface died is a cell nobody can stop from where they stand, and
    ending it stops everything the console started; not asked for, there is no
    console to end anything. It needs a boundary, and is ignored without one.

    ``boundary`` is optional, and a supervisor given none joins two sides and
    stops there. That is not a mode: it is what keeps ADR-0047's membership test
    able to drive this function against two processes that are not ROS at all.

    **Everything that was started is stopped, the boundary first** - see
    :func:`_stop_order`, which is where the reason lives and is ordering alone.

    Nothing in here knows what a ROS domain is. It is given argument vectors and
    environment overlays, it reads pipes, and it reads exit statuses — and it
    does not know what the boundary it starts is for, which is the line ADR-0057
    draws.
    """
    out = sys.stdout if out is None else out
    environ = os.environ if environ is None else environ

    events: queue.Queue = queue.Queue()

    def starter(spec: SideSpec) -> Callable[[], _Side]:
        def start() -> _Side:
            # The whole command, because what this supervisor is allowed to
            # pass the boundary is two arguments and a reader should be able to
            # see all of them in the console rather than take this file's word
            # for it.
            print(
                f"[pair] starting {spec.title}: " + " ".join(spec.argv),
                file=out,
                flush=True,
            )
            return _launch(spec, environ, events, out)

        return start

    # Started after the join, each on the announcement of the one before it.
    followers = [spec for spec in (boundary, console if boundary else None) if spec]

    interrupted = False
    # The handlers go in BEFORE any side is started, and the order is the fix
    # for a three-minute teardown. A supervisor started as a background job of a
    # non-interactive shell (`scripts/program`) inherits SIGINT
    # as IGNORED, an ignored disposition survives `exec`, and a side started
    # while it was still ignored could not hear the SIGINT `_stop` sends it - so
    # every such teardown waited out `STOP_GRACE_S` per side before the group
    # SIGTERM. Once a Python handler is installed, a child's `exec` resets
    # SIGINT to the default instead.
    with _stop_requests(events):
        sides = [_launch(spec, environ, events, out) for spec in specs]
        print(
            "[pair] started " + ", ".join(s.name for s in sides) + "; waiting for "
            "each side to announce its own readiness",
            file=out,
            flush=True,
        )
        interrupted, participants = _join(
            sides,
            events,
            ceiling_s,
            out,
            start_next=[starter(spec) for spec in followers],
            boundary_ceiling_s=boundary_ceiling_s,
        )
    # Drained BEFORE anything is stopped, and that ordering is the point. When
    # two sides fail for one reason they fail together, and a side stopped by
    # this supervisor reports the stop rather than whatever it was reporting -
    # which is ADR-0038's lesson one level up: ending a process to report a
    # fault takes the evidence of the fault with it. Anything already on the
    # queue is that evidence, and it costs nothing to read it first.
    _drain(events)
    # Every participant the join returned, which includes the boundary if it was
    # started and does not if the join never completed. A boundary that was never
    # started is not a process to stop, and a list built here from the specs
    # rather than from what ran would try to stop one.
    for participant in _stop_order(participants, followers):
        _stop(participant, out)
        if participant.status is None:
            participant.status = participant.process.poll()
    # After every participant's own stop, and unconditionally. `_stop` reaches
    # one whose process is still running; this reaches what a process that has
    # already gone left behind, which is the half nothing else covers.
    _sweep(participants, out)
    return _verdict(participants, interrupted, out)


def _stop_order(
    participants: Sequence[_Side], followers: Sequence[SideSpec]
) -> list[_Side]:
    """Return the participants in the order they are to be stopped: commander first.

    **The stop loop is sequential and each participant costs its own ceilings**
    (`STOP_GRACE_S` and `STOP_KILL_S`), so the order decides what is still
    running, and still commanding, while the ones before it are being stopped.
    Started in the order they appear, the boundary is appended last and would
    therefore be stopped last — holding an action client on each side, and
    answering `SetMode`, for the whole of both sides' teardown. A goal arriving
    in that window is dispatched to a side that is already shutting down and to
    one that has not been signalled at all.

    So the boundary goes first. **It is the only participant that commands
    anything**, it starts no cell, and nothing about its teardown is evidence
    any side's teardown depends on — a side does not consult it, and both sides
    were up before it existed.

    **Ordering only.** No ceiling moves, no participant is skipped, and the
    reporting order is deliberately NOT changed: :func:`_verdict` and
    :func:`_report_ceiling` still read sides first and the boundary last, which
    is the order a reader looks for them in.

    Identity against the spec this supervisor was handed, rather than a name or a
    kind: the caller knows which participant it asked for as the boundary, and
    `sorted` is stable, so the sides keep the plan's order between themselves.

    **The console goes before the boundary** (ADR-0071), for the boundary's own
    reason one level up: it is the client that sends the boundary its goals,
    and stopped first it cancels what it has in flight while the boundary is
    still there to carry the cancel. So the participants started after the
    join are stopped in the reverse of the order they were started in, and the
    sides after them.
    """
    if not followers:
        return list(participants)

    def rank(started: _Side) -> int:
        for index, spec in enumerate(followers):
            if started.spec is spec:
                return -index
        return 1

    return sorted(participants, key=rank)


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

    **A third participant widens the exposure, and that is recorded here rather
    than acted on** (ADR-0057). The orphan a deadlocked supervisor strands used
    to be two launches and their Gazebo servers; it is now those and a twin
    boundary, which holds an `rclpy` context on BOTH sides' domains and whose
    endpoints stay advertised on them. Nothing about the window or the fix
    changes - it is the same narrow race and the same self-pipe - but what it
    would leave behind is larger.
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


def _join(
    sides: Sequence[_Side],
    events: queue.Queue,
    ceiling_s: float,
    out,
    *,
    start_next: Sequence[Callable[[], _Side]] = (),
    boundary_ceiling_s: float = BOUNDARY_CEILING_S,
) -> tuple[bool, list[_Side]]:
    """Block until the pair is complete and then until it ends.

    Return whether it was asked to stop, and every participant that was started
    — which the caller stops, sweeps and reports on, and which is why this
    returns the list rather than letting the caller rebuild it from the specs: a
    boundary that was never started is not a process to stop.

    Three phases and one loop. Before the join the wait carries the sides'
    ceiling; **the moment the last side announces, the boundary is started and
    the wait carries ITS ceiling instead**, because the first one is dropped on
    that same iteration and a participant covered by no ceiling is the hang
    ADR-0044 records (ADR-0057's correction of 2026-09-18). After everything has
    announced there is nothing left to time — a pair that is up ends when a
    participant ends or when somebody asks it to, and neither is an interval.

    ``start_next`` is every participant started after the join, in order: the
    boundary, then the operator console (ADR-0071). Each is started on the
    announcement of everything before it, under the boundary's ceiling.
    """
    participants = list(sides)
    ceiling = ceiling_s
    deadline = time.monotonic() + ceiling
    pending = list(start_next)
    # The participant started last after the join, None before the join. What
    # an arrival of "everything is ready" means depends on it.
    latest: _Side | None = None
    while True:
        joined = all(participant.ready for participant in participants)
        timeout = None if joined else max(0.0, deadline - time.monotonic())
        try:
            kind, side, payload = events.get(timeout=timeout)
        except queue.Empty:
            _report_ceiling(participants, ceiling, out)
            return False, participants
        if kind == "stop":
            print(
                f"[pair] asked to stop (signal {payload}); ending both sides",
                file=out,
                flush=True,
            )
            return True, participants
        if kind == "ready":
            if payload != side.announces:
                print(
                    f"[pair] {side.name} announced readiness as {payload!r}, and "
                    f"this supervisor started it as {side.announces!r}. A "
                    "participant announces what it was started as, so this one was "
                    f"given the wrong {side.spec.argument} argument and the pair is "
                    "not what it says.",
                    file=out,
                    flush=True,
                )
                return False, participants
            side.ready = True
            if not all(p.ready for p in participants):
                continue
            if latest is None:
                print(
                    "[pair] every side started announced readiness; the pair is up",
                    file=out,
                    flush=True,
                )
            else:
                print(
                    f"[pair] {latest.spec.title} announced readiness"
                    + ("" if pending else "; the pair is complete"),
                    file=out,
                    flush=True,
                )
            if not pending:
                # Nothing more was asked for, so this is the whole of the join.
                continue
            # On this event and on nothing else (ADR-0057). This is the one
            # place in this system where "both sides are ready" is a fact rather
            # than a judgement, and the boundary has nothing to connect to
            # before it - nor the console before the boundary (ADR-0071).
            latest = pending.pop(0)()
            participants.append(latest)
            ceiling = boundary_ceiling_s
            deadline = time.monotonic() + ceiling
        else:
            side.status = payload
            print(
                f"[pair] {side.name} exited {payload}", file=out, flush=True
            )
            return False, participants


def _report_ceiling(
    participants: Iterable[_Side], ceiling_s: float, out
) -> None:
    """Name what never answered, and say what its silence means.

    The sentence after the ceiling is the participant's own, because a side that
    is silent and a boundary that is silent send the reader to different places.
    """
    for participant in participants:
        if participant.ready:
            continue
        print(
            f"[pair] {participant.name} never announced readiness and never "
            f"exited, within {ceiling_s:g} s. {participant.spec.silence}",
            file=out,
            flush=True,
        )


def _verdict(participants: Sequence[_Side], interrupted: bool, out) -> int:
    """Report every participant's status, never only the first, and grade the run.

    Every participant that was started, which is both sides and the boundary
    when there is one. A boundary that failed is reported as the boundary and
    graded as one: it never announced, so the pair never came up, which is the
    same 1 a side that would not start produces and is deliberately not a code
    of its own — the line above it says which participant it was.

    **Nothing here keys on a participant's exit status**, and for the boundary
    that matters: `twin_boundary` exits 0 or 2 and never 1, so a verdict that
    read 1 as its failure would call every refusal it makes a success.

    **The grade is over EVERY participant, so there is a window in which a side's
    death grades 1 rather than `PAIR_ENDED`, and it is stated rather than left to
    be discovered.** That window opens when the last side announces and closes
    when the boundary does: a side that exits inside it leaves a participant that
    never announced, which is "the pair never came up" and not "the pair ran and
    lost a side". Before the boundary existed there was no such window, and this
    is the one behaviour of a two-side pair that gaining a third participant
    changed. It is deliberately not narrowed by grading on "every SIDE is ready":
    a pair whose boundary never answered cannot answer `SetMode`, which is the
    thing the pair is for, and reporting that as a pair that merely ended would
    lose the diagnosis the line above it just printed.
    """
    for participant in participants:
        print(
            f"[pair] {participant.name}: ready={participant.ready} "
            f"status={participant.status}",
            file=out,
            flush=True,
        )
    if interrupted and all(participant.ready for participant in participants):
        # The pair came up and an operator ended it. That is what asking for a
        # pair and then stopping it looks like, and it is not a failure.
        return 0
    if not all(participant.ready for participant in participants):
        return 1
    return PAIR_ENDED


#: The `key:=value` arguments `./scripts/sim` forwards, and the option each one
#: means here. The solo path is `ros2 launch`, which takes that spelling, so a
#: `key:=value` that works without `--pair` used to fail with an argparse error
#: with it - the same request, refused only because the pair path is a Python
#: program rather than a launch file.
#:
#: Translated here rather than in `scripts/sim`, because the shell would then
#: hold a second statement of which arguments a pair takes.
_LAUNCH_STYLE = {
    "zone": "--zone",
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
        if option == "--headless":
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
    # Required, with no default (ADR-0056 decision 4). `readiness_witness`
    # already declares its own zone this way, and the supervisor starts one
    # of those per side, so a defaulted zone here would decide which cell a
    # pair is without the caller ever naming it.
    parser.add_argument("--zone", required=True)
    parser.add_argument(
        "--headless", action="store_true", help="Run both simulators without a GUI."
    )
    # The SIDES' ceiling, and there is deliberately no option for the boundary's.
    # `--ceiling` exists because a caller may know something about how long a
    # cell takes to come up on a given machine; nothing comparable is knowable
    # about the boundary, which starts no cell and whose ceiling covers a process
    # that reads a plan and opens two contexts. An option there would be a knob
    # for widening a ceiling to absorb a slow host, which is the one thing every
    # ceiling in this file says never to do. A test that needs a shorter one
    # passes `boundary_ceiling_s` to `supervise` directly.
    parser.add_argument("--ceiling", type=float, default=READY_CEILING_S)
    parser.add_argument(
        "--console",
        action="store_true",
        help="Also start the operator console once the boundary is up (ADR-0071).",
    )
    # REQUIRED, with no default (ADR-0072): which sides start is decided by the
    # hardware opt-in in `./scripts/sim` and handed here, never inferred.
    parser.add_argument(
        "--sides",
        required=True,
        choices=SIDES_CHOICES,
        help="Start every side the plan declares, or the plant alone (ADR-0072).",
    )
    args = parser.parse_args(
        _flags(sys.argv[1:] if argv is None else argv, parser)
    )

    try:
        path = default_plan_path(args.zone)
        plan = load(path)
        specs = side_specs(plan, os.environ, headless=args.headless, sides=args.sides)
    except PlanError as exc:
        print(f"PAIR BRING-UP FAILED: {exc}", file=sys.stderr)
        return 1
    if len(plan.sides) < 2:
        # Not an error to be repaired here. Whether a zone runs as a pair is an
        # L0 fact, and inventing a second side would be bring-up deciding what
        # the facility is (P5).
        print(
            f"PAIR BRING-UP FAILED: zone {plan.zone!r} declares "
            f"{len(plan.sides)} side(s). A pair needs two; set `twin: {{sides: pair}}` "
            "on the zone in the L0 model and regenerate.",
            file=sys.stderr,
        )
        return 1
    if args.sides == SIDES_PLANT:
        print(
            "[pair] starting the plant alone (--sides plant): no counterpart runs, and the "
            "twin boundary supports SIM only (ADR-0072)",
            flush=True,
        )
    # The path rather than the zone, so that the boundary reads the same
    # document this supervisor resolved the sides from. Resolving it a second
    # time from the zone would be the same lookup written twice, and the two
    # copies disagree the first time one of them is pointed elsewhere - which is
    # exactly what a test does.
    console = None
    if args.console:
        try:
            console = console_spec(plan, path, os.environ, args.sides)
        except PlanError as exc:
            print(f"PAIR BRING-UP FAILED: {exc}", file=sys.stderr)
            return 1
    return supervise(
        specs,
        boundary=boundary_spec(plan, path, args.sides),
        console=console,
        ceiling_s=args.ceiling,
    )


if __name__ == "__main__":
    sys.exit(main())
