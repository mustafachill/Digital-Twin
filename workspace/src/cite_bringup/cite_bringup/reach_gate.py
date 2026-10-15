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

"""Block until a physical side's robot answers on the network, then exit (ADR-0077).

The FIRST link of `hardware.launch.py`'s chain, after its refusals and before
the deadman: a process that waits on one condition and exits, 0 when it held.
Nothing of the side - no deadman, no vendor driver - starts before it exits 0,
so the vendor driver is never started against a robot that is switched off or
off the network. That driver answers an absent robot by crashing
(`xarm_driver.cpp`), and a side that crashed is a side the pair supervisor has
to judge; a side that is still waiting for its robot is not.

**What it asks**: a TCP connection to every physical arm's report port on the
side, accepted. The port is the vendor's normal report port,
`XARM_CONF::TCP_PORT_REPORT_NORM = 30001`
(`xarm_ros2/xarm_sdk/cxx/include/xarm/core/xarm_config.h`), the one the SDK's
own connect opens for its report stream (`xarm_sdk/cxx/src/xarm/core/connect.cc`).
The connection is closed at once and nothing is sent on it: the gate commands
nothing and reads nothing.

**The address is read by `plan.resolve_description_args` and by nothing else**
(ADR-0070 item 2): the description argument whose kind is `ip_address`, from
the process environment. It is never printed, never logged and never put on a
command line - this process is started with the side's own environment, which is
where the address already is. A failure names the variable, never the value.

**It is a poll, stated as one** (`PROBE_PERIOD_S`). There is no event a client
can wait on for a host starting to listen on a port: a connection either is
accepted or is refused or times out, and the only way to learn that a robot was
switched on is to ask again.

Two ways to end:

- **Waiting for the robot** (`--wait`, which the pair supervisor asks for a KEPT
  side, ADR-0077 decision 2): no ceiling. The side is reported `waiting` while
  this runs, and an operator switching the robot on is what ends it.
- **Otherwise** (`./scripts/program`, `./scripts/home`, a scenario):
  `REACH_CEILING_S`, a ceiling on a failure. A robot that never answers is
  reported naming the variable, and the side exits non-zero as it did when the
  vendor driver crashed on it, without starting the driver.

Exit codes: 0 reached; 1 the ceiling expired; 2 refused before asking - the side
is not physical, or the address is unset or malformed.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import os
import socket
import sys
import time

from cite_bringup.plan import (
    default_plan_path,
    IP_ADDRESS_KIND,
    load,
    Plan,
    PlanError,
    resolve_description_args,
)

#: The arm controller's normal report port: `XARM_CONF::TCP_PORT_REPORT_NORM`
#: in the vendor SDK (`xarm_sdk/cxx/include/xarm/core/xarm_config.h`). A vendor
#: constant, stated once here because nothing in the plan carries it and no
#: Python package exports it.
REPORT_PORT = 30001

#: How long one connection attempt may take before it counts as unanswered, in
#: wall seconds. A ceiling on one attempt: an accepted connection returns as soon
#: as the handshake completes, and a refused one at once.
CONNECT_TIMEOUT_S = 2.0

#: How long the gate waits between attempts, in wall seconds. A POLL, and the
#: reason it is one is in the module docstring: nothing announces that a host
#: began to listen. What it decides is only how soon after the robot is switched
#: on the side begins to come up; nothing is sequenced on it.
PROBE_PERIOD_S = 1.0

#: A ceiling on a failure, never a schedule, for a side that is NOT kept: the
#: robot never answered. It is not a bring-up time - the controller answers on
#: its report port within seconds of booting - and it must never be widened to
#: absorb a robot that is slow to boot: an operator starting a run against a
#: robot that is off is told so, and starts again once it is on.
REACH_CEILING_S = 60.0


def addresses(plan: Plan, side: str, environ: Mapping[str, str]) -> list[str]:
    """Return every physical arm's address on ``side``, read through the one reader.

    Refuses (`PlanError`) a side with no physical arm and an arm with no
    `ip_address` argument: a gate that asked nobody would pass at once, which is
    the one answer it must never give by accident.
    """
    found: list[str] = []
    for manager in plan.controller_managers:
        if manager.commands_physical_hardware_on_or_none(side) is not True:
            continue
        resolved = resolve_description_args(manager, side, environ)
        named = [
            resolved[argument]
            for argument, reference in sorted(manager.description_args_on(side).items())
            if reference.kind == IP_ADDRESS_KIND and argument in resolved
        ]
        if not named:
            raise PlanError(
                f"asset {manager.asset!r} on the {side} side is physical and its description "
                "reads no IP address from the environment, so there is no robot to wait for"
            )
        found += named
    if not found:
        raise PlanError(
            f"zone {plan.zone!r}: the {side} side commands no physical hardware; the reach "
            "gate runs on a physical side only"
        )
    return found


def answers(address: str, port: int = REPORT_PORT, timeout_s: float = CONNECT_TIMEOUT_S) -> bool:
    """Whether ``address`` accepts a TCP connection on ``port`` within ``timeout_s``.

    Opened and closed at once; nothing is sent. Every failure to connect - a
    refusal, a timeout, an unreachable network - is the same answer, no.
    """
    try:
        with socket.create_connection((address, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def wait_for(
    targets: Sequence[str],
    *,
    ceiling_s: float | None,
    port: int = REPORT_PORT,
    period_s: float = PROBE_PERIOD_S,
    probe: Callable[[str, int], bool] | None = None,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> bool:
    """Ask every target until all have answered once; return whether they did in time.

    ``ceiling_s`` None waits for ever. A target that answered is not asked
    again: the gate's fact is "each robot was there", and a robot that is gone
    again by the time the driver connects is the driver's to report.
    """
    ask = probe if probe is not None else (lambda address, at: answers(address, at))
    pending = list(targets)
    deadline = None if ceiling_s is None else clock() + ceiling_s
    while True:
        pending = [address for address in pending if not ask(address, port)]
        if not pending:
            return True
        if deadline is not None and clock() >= deadline:
            return False
        pause(period_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zone", required=True)
    parser.add_argument("--side", required=True)
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the robot without a ceiling (a kept side, ADR-0077).",
    )
    # `launch_ros` appends `--ros-args`; nothing here is a ROS argument.
    arguments, _unknown = parser.parse_known_args(argv)
    try:
        plan = load(default_plan_path(arguments.zone))
        targets = addresses(plan, arguments.side, os.environ)
    except PlanError as error:
        print(f"reach gate: {error}", file=sys.stderr, flush=True)
        return 2
    count = f"{len(targets)} robot(s)"
    if arguments.wait:
        print(
            f"reach gate: waiting for {count} on the {arguments.side} side to answer on "
            f"port {REPORT_PORT}, asking every {PROBE_PERIOD_S:g} s, without a ceiling",
            flush=True,
        )
    ceiling = None if arguments.wait else REACH_CEILING_S
    if wait_for(targets, ceiling_s=ceiling, port=REPORT_PORT):
        print(f"reach gate: {count} on the {arguments.side} side answered", flush=True)
        return 0
    print(
        f"reach gate: the robot on the {arguments.side} side did not answer on port "
        f"{REPORT_PORT} within {REACH_CEILING_S:g} s. Is it switched on and on the "
        "network, and is its address in your local .env right? The address is not "
        "printed.",
        file=sys.stderr,
        flush=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
