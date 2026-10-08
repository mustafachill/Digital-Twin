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

"""Block until a physical side's arm is confirmed held, then exit (ADR-0070 item 6).

A link in `hardware.launch.py`'s chain, in the shape of every other: a process
that waits on conditions under a wall-clock ceiling and exits, 0 when they all
held and non-zero naming the one that did not. Nothing that could move the arm
- no controller spawner, no planner, no skill server - starts before it exits 0
(the safety re-audit's L-4).

What it confirms, for every physical arm on the side, in order:

1. **The deadman says AWAITING**: active, and holding the arm because no
   heartbeat has arrived. Read on its latched `DeadmanState`.
2. **Every vendor service the side's nodes call is advertised**: the vendor
   driver is up, which means the plugin has connected to the arm's controller.
3. **A STOP sent to the vendor is acknowledged** (`set_state(4)`, `ret == 0`).
   The deadman sends the same STOP on every tick and publishes no observable of
   its acknowledgement, so this gate sends one of its own and waits for the
   answer: the arm is held, and the link to it answers. A STOP is the one
   command this gate may send, and it sends nothing else.

   **Advertised is not matched, and matched is not delivered** (CLAUDE.md
   §10). The service being on the graph says nothing about THIS client: a
   request sent before the client matched the server is lost without a word,
   which is how the first physical run failed at the ceiling while the
   deadman's own STOPs were answered every tick. So the gate waits for the
   client's match as an event (`service_is_ready`), sends, and sends the same
   STOP again each time the side's `call_deadline_s` passes unanswered, until
   the ceiling. Earlier requests stay pending, so a slow answer still counts.
   An answer that refuses (`ret != 0`) is final; it is never re-sent.

**Its deadline is the wall clock**, and `use_sim_time` is false, for the reason
`readiness_witness.py` gives.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
import time

from cite_bringup.plan import default_plan_path, load, PhysicalSide, PlanError
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
from cite_runtime import runtime
import rclpy
from rclpy.parameter import Parameter
from xarm_msgs.srv import SetInt16
import yaml

#: A ceiling on a failure, never a schedule: the vendor plugin connecting to the
#: arm's controller is a network event, and a side that cannot reach its arm is
#: reported rather than waited on.
DEADLINE_S = 120.0

#: How long one spin blocks before the ceiling is checked again. A poll bounded
#: by the ceiling above, as `readiness_witness.py`'s is.
_SLICE_S = 0.5

#: The vendor's STOP state (`XARM_STATE`, `uxbus_cmd_config.h`). A constant of
#: the vendor's API, as `cite_hardware.deadman` states it.
VENDOR_STATE_STOP = 4


class HoldFailed(RuntimeError):
    """A condition of the hold did not hold before the ceiling."""


def awaiting(message: DeadmanState | None) -> bool:
    """Whether the deadman's last word is AWAITING: active, and holding the arm."""
    return message is not None and message.state == DeadmanState.STATE_AWAITING


def missing_services(wanted: list[str], advertised: set[str]) -> list[str]:
    """Return the vendor services not yet advertised, in the order they were asked for."""
    return [name for name in wanted if name not in advertised]


def wait_until(
    condition: Callable[[], bool],
    describe: Callable[[], str],
    deadline: float,
    ceiling_s: float,
    spin: Callable[[], None],
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Spin until ``condition`` holds, or raise `HoldFailed` once ``deadline`` passes.

    ``describe`` is called only at expiry, so the failure names what was still
    missing THEN, not what was missing when the wait began (R-09).
    """
    while not condition():
        if clock() >= deadline:
            raise HoldFailed(f"{describe()} not within {ceiling_s:g} s")
        spin()


def vendor_call_deadline_s(physical: PhysicalSide) -> float:
    """Return the side's per-call bound on a vendor answer, as its deadman is given it.

    Declared once in L0 (`physical_side.call_deadline_s`) and generated into the
    side's parameter file under the deadman's name; read from there rather than
    restated, so the gate and the deadman can never disagree about it.
    """
    try:
        document = yaml.safe_load(physical.parameters.read_text()) or {}
        return float(document[physical.deadman]["ros__parameters"]["call_deadline_s"])
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise PlanError(
            f"{physical.parameters} states no call_deadline_s for {physical.deadman}: {exc!r}"
        ) from exc


def call_until_answered(
    client,
    request,
    attempt_s: float,
    deadline: float,
    ceiling_s: float,
    spin: Callable[[float], None],
    describe: Callable[[], str],
    clock: Callable[[], float] = time.monotonic,
):
    """Send ``request`` once ``client`` has matched its server; re-send until one is answered.

    Each send waits ``attempt_s`` (or until ``deadline``) for an answer before
    the same request is sent again; every send stays pending, so whichever is
    answered first is returned. Raises `HoldFailed` once ``deadline`` passes
    with no answer. ``spin`` blocks for at most the seconds it is given. Every
    request still pending on return is removed from the client.
    """
    sent = []
    try:
        while True:
            wait_until(
                client.service_is_ready,
                lambda: f"{describe()} ({client.srv_name} never matched this client)",
                deadline,
                ceiling_s,
                lambda: spin(max(0.0, deadline - clock())),
                clock,
            )
            sent.append(client.call_async(request))
            resend_at = min(deadline, clock() + attempt_s)
            while True:
                answered = next((future for future in sent if future.done()), None)
                if answered is not None:
                    return answered.result()
                now = clock()
                if now >= deadline:
                    raise HoldFailed(f"{describe()} not within {ceiling_s:g} s")
                if now >= resend_at:
                    break
                spin(resend_at - now)
    finally:
        for future in sent:
            if not future.done():
                client.remove_pending_request(future)
                future.cancel()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", required=True)
    parser.add_argument("--side", required=True)
    parser.add_argument("--deadline", type=float, default=DEADLINE_S)
    args, ros_args = parser.parse_known_args(argv)
    try:
        plan = load(default_plan_path(args.zone))
        arms = [
            (manager, manager.physical_on(args.side), manager.vendor_on(args.side))
            for manager in plan.controller_managers
        ]
        unwired = [m.asset for m, physical, vendor in arms if physical is None or vendor is None]
        if unwired or not arms:
            print(
                f"HOLD GATE FAILED: side {args.side!r} of zone {plan.zone!r} names no deadman "
                f"or vendor driver for {unwired or 'any arm'}; there is no hold to confirm.",
                file=sys.stderr,
            )
            return 2
        attempts_s = {m.asset: vendor_call_deadline_s(physical) for m, physical, _ in arms}
    except PlanError as exc:
        print(f"HOLD GATE FAILED: {exc}", file=sys.stderr)
        return 2

    runtime.init(args=ros_args)
    node = rclpy.create_node(
        "hold_gate", parameter_overrides=[Parameter("use_sim_time", value=False)]
    )
    deadline = time.monotonic() + args.deadline

    def spin_until(condition, describe: Callable[[], str]) -> None:
        wait_until(
            condition,
            describe,
            deadline,
            args.deadline,
            lambda: rclpy.spin_once(node, timeout_sec=_SLICE_S),
        )

    def advertised() -> set[str]:
        return {name for name, _types in node.get_service_names_and_types()}

    try:
        for manager, physical, vendor in arms:
            last: list[DeadmanState] = []
            node.create_subscription(
                DeadmanState, physical.deadman_state_topic, last.append, LATCHED
            )
            spin_until(
                lambda: awaiting(last[-1] if last else None),
                lambda: f"{manager.asset}: the deadman did not say AWAITING on "
                f"{physical.deadman_state_topic}",
            )
            wanted = list(vendor.services.values())
            spin_until(
                lambda: not missing_services(wanted, advertised()),
                lambda: f"{manager.asset}: the vendor driver did not advertise "
                f"{missing_services(wanted, advertised())}",
            )
            client = node.create_client(SetInt16, vendor.services["set_state"])
            response = call_until_answered(
                client,
                SetInt16.Request(data=VENDOR_STATE_STOP),
                attempts_s[manager.asset],
                deadline,
                args.deadline,
                lambda timeout_s: rclpy.spin_once(node, timeout_sec=min(_SLICE_S, timeout_s)),
                lambda: f"{manager.asset}: the vendor did not answer a STOP",
            )
            if response is None or response.ret != 0:
                code = None if response is None else response.ret
                raise HoldFailed(
                    f"{manager.asset}: the vendor refused a STOP (code {code}). Clear the "
                    "arm's error with the vendor's own tools before starting again."
                )
            node.get_logger().info(f"{manager.asset}: held at STOP, deadman AWAITING")
    except HoldFailed as failure:
        print(f"HOLD GATE FAILED: {failure}", file=sys.stderr)
        return 1
    finally:
        runtime.shutdown(node)
    return 0


if __name__ == "__main__":
    sys.exit(main())
