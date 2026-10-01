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

"""Run one side's belt on that side alone: `python3 -m cite_bringup.program.belt`.

    --zone cell_b                         every side's belt at its installed speed
    --zone cell_b --side counterpart --stop

THE BELT IS NOT TWINNED (ADR-0067). The real robot's program has no belt block,
so the fixed program no longer drives one, and each simulated side's belt is run
by this command on that side's own ROS domain — never through the twin boundary.
It publishes one setpoint once the belt's subscriber has matched (a setpoint sent
before the match reaches nobody, CLAUDE.md §10) and exits.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from cite_bringup.plan import default_plan_path, domain_base, load, resolve_domain_id

#: How long to wait for the belt's subscriber, in wall seconds. A hang detector.
MATCH_CEILING_S = 60.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program.belt", description="Run each side's belt."
    )
    parser.add_argument("--zone", required=True)
    parser.add_argument(
        "--side", action="append", help="plant or counterpart; every side the zone runs if omitted"
    )
    parser.add_argument("--stop", action="store_true", help="Command zero instead.")
    args = parser.parse_args(argv)

    plan = load(default_plan_path(args.zone))
    sides = [plan.side_named(name).name for name in (args.side or [])] or [
        side.name for side in plan.sides
    ]
    if len(plan.conveyors) != 1:
        parser.error(f"zone {args.zone} has {len(plan.conveyors)} belts, not one")
    (conveyor,) = plan.conveyors
    speed = 0.0 if args.stop else conveyor.installed_speed_mps
    base = domain_base(os.environ)
    status = 0
    for side in sides:
        domain = resolve_domain_id(plan, side, base)
        if not _set_on_one_side(conveyor.command_topic, speed, domain, side):
            status = 1
        else:
            print(f"  ok  {side}: {conveyor.asset} at {speed:g} m/s", flush=True)
    return status


def _set_on_one_side(topic: str, speed: float, domain: int, side: str) -> bool:
    """Publish one setpoint on ``domain``, in a context of its own, once matched."""
    # Imported here so that the argument errors above need no ROS at all.
    from cite_interfaces.qos import COMMAND
    import rclpy
    from rclpy.duration import Duration
    from rclpy.executors import SingleThreadedExecutor
    from std_msgs.msg import Float64

    # One context per side: a side is a ROS domain, and a context is bound to
    # exactly one, so the two belts are reached as two separate graphs.
    context = rclpy.Context()
    rclpy.init(context=context, domain_id=domain)
    try:
        node = rclpy.create_node("belt_setpoint", context=context)
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        publisher = node.create_publisher(Float64, topic, COMMAND)
        deadline = time.monotonic() + MATCH_CEILING_S
        while publisher.get_subscription_count() == 0:
            if time.monotonic() > deadline:
                print(
                    f"{side}: nothing subscribes to {topic} on domain {domain} after "
                    f"{MATCH_CEILING_S:.0f} s; is that side up?",
                    file=sys.stderr,
                )
                return False
            executor.spin_once(timeout_sec=0.1)
        publisher.publish(Float64(data=float(speed)))
        # Reliable delivery to a matched subscriber is asynchronous; wait for the
        # middleware to acknowledge it rather than exiting on a sleep.
        return publisher.wait_for_all_acked(Duration(seconds=10.0))
    finally:
        context.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
