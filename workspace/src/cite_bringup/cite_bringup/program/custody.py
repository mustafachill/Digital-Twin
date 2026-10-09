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

"""Read one side's arm custody on THAT side's domain (R-09, ADR-0072).

A run reads the custody of every side its target commands before its first
step: the program opens with a release, and a release on an arm that holds a
part drops it where the arm stands. The plant's `RobotState` is on the
program's own domain; any other side's is on that side's, which the program's
cell never opens (ADR-0044 clause 3). So it is read here, in a context of its
own, as `program.belt` commands a side's belt and `program.home` calls a side's
`InitializeAsset` - a READ of the side's latched state, and nothing else: no
publisher, no client, no service on that domain.

`None` when nothing is heard within the ceiling, which the caller refuses
(`cell.holding_refusal`): an unheard custody is never assumed empty.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
import time

from cite_bringup.plan import domain_base, Plan, PlanError, resolve_domain_id
from cite_bringup.program.steps import Interrupted
from cite_interfaces.msg import RobotState
from cite_interfaces.qos import LATCHED

#: How long a side's latched state may take to arrive, in wall seconds. A hang
#: detector: the side is up and its skill server publishes it latched at once.
READ_CEILING_S = 30.0

#: How long one spin waits for a callback, in wall seconds: how soon a stop is seen.
_SLICE_S = 0.1


def read_state_on_side(
    plan: Plan,
    side: str,
    topic: str,
    environ: Mapping[str, str] = os.environ,
    interrupted: Callable[[], bool] | None = None,
    ceiling_s: float = READ_CEILING_S,
) -> RobotState | None:
    """Return the latest `RobotState` on ``topic`` on ``side``'s domain, or None if unheard.

    ``interrupted`` is the console's stop, asked between spins; True raises
    `steps.Interrupted`, as every other wait of a run does.
    """
    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    try:
        domain = resolve_domain_id(plan, side, domain_base(environ))
    except PlanError:
        return None
    context = rclpy.Context()
    rclpy.init(context=context, domain_id=domain)
    try:
        node = rclpy.create_node("custody_reader", context=context)
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        heard: list[RobotState] = []
        node.create_subscription(RobotState, topic, heard.append, LATCHED)
        deadline = time.monotonic() + ceiling_s
        while not heard:
            if time.monotonic() > deadline:
                return None
            if interrupted is not None and interrupted():
                raise Interrupted(f"stopped while {side}'s custody was read")
            executor.spin_once(timeout_sec=_SLICE_S)
        return heard[-1]
    finally:
        context.try_shutdown()
