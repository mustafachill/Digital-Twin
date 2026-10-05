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

**Its deadline is the wall clock**, and `use_sim_time` is false, for the reason
`readiness_witness.py` gives.
"""

from __future__ import annotations

import argparse
import sys
import time

from cite_bringup.plan import default_plan_path, load, PlanError
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
from cite_runtime import runtime
import rclpy
from rclpy.parameter import Parameter
from xarm_msgs.srv import SetInt16

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
    except PlanError as exc:
        print(f"HOLD GATE FAILED: {exc}", file=sys.stderr)
        return 2
    unwired = [m.asset for m, physical, vendor in arms if physical is None or vendor is None]
    if unwired or not arms:
        print(
            f"HOLD GATE FAILED: side {args.side!r} of zone {plan.zone!r} names no deadman or "
            f"vendor driver for {unwired or 'any arm'}; there is no hold to confirm.",
            file=sys.stderr,
        )
        return 2

    runtime.init(args=ros_args)
    node = rclpy.create_node(
        "hold_gate", parameter_overrides=[Parameter("use_sim_time", value=False)]
    )
    deadline = time.monotonic() + args.deadline

    def spin_until(condition, what: str) -> None:
        while not condition():
            if time.monotonic() >= deadline:
                raise HoldFailed(f"{what} not within {args.deadline:g} s")
            rclpy.spin_once(node, timeout_sec=_SLICE_S)

    try:
        for manager, physical, vendor in arms:
            last: list[DeadmanState] = []
            node.create_subscription(
                DeadmanState, physical.deadman_state_topic, last.append, LATCHED
            )
            spin_until(
                lambda: awaiting(last[-1] if last else None),
                f"{manager.asset}: the deadman did not say AWAITING on "
                f"{physical.deadman_state_topic}",
            )
            wanted = list(vendor.services.values())
            spin_until(
                lambda: not missing_services(
                    wanted, {name for name, _types in node.get_service_names_and_types()}
                ),
                f"{manager.asset}: the vendor driver did not advertise "
                f"{missing_services(wanted, {n for n, _t in node.get_service_names_and_types()})}",
            )
            client = node.create_client(SetInt16, vendor.services["set_state"])
            future = client.call_async(SetInt16.Request(data=VENDOR_STATE_STOP))
            spin_until(future.done, f"{manager.asset}: the vendor did not answer a STOP")
            response = future.result()
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
