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

"""Which sides of a zone are simulated and which physical: `python3 -m cite_bringup.program.sides`.

    --zone cell_b --physical      the sides whose hardware is physical, one per line
    --zone cell_b --simulated     the others
    --zone cell_b --speed-scale S the speed scale to run at, or a refusal

`./scripts/program` asks this before every Gazebo-only step (ADR-0070 item 7):
it spawns a box, removes one, reads a model's pose and runs a belt only on a
simulated side, and on a physical side says so and asks a person instead. The
answer is the plan's declared fact (`commands_physical_hardware_on_or_none`),
never an asset's type or a backend's name.
"""

from __future__ import annotations

import argparse
import sys

from cite_bringup.plan import default_plan_path, load, Plan
from cite_bringup.program.steps import speed_scale


def is_physical(plan: Plan, side: str) -> bool:
    """Whether any asset on ``side`` commands physical hardware."""
    return any(
        manager.commands_physical_hardware_on_or_none(side) is True
        for manager in plan.controller_managers
    )


def physical_sides(plan: Plan) -> list[str]:
    """Return the sides whose hardware is physical, in the plan's order."""
    return [side.name for side in plan.sides if is_physical(plan, side.name)]


def simulated_sides(plan: Plan) -> list[str]:
    """Return the sides a simulator runs, in the plan's order."""
    return [side.name for side in plan.sides if not is_physical(plan, side.name)]


def required_speed_scale(plan: Plan, given: str, via: str = "twin") -> float:
    """Return the speed scale a run uses, refusing one the operator must state (S-04).

    ``given`` is `--speed-scale` exactly as typed, empty when it was not. The
    range is `steps.speed_scale`'s, the one statement of it. Where a side the
    run commands is physical - any physical side, through the twin - the scale
    is never defaulted: the operator names the fraction of the program's speed
    the real arm and carriage move at. ``via`` "plant" commands the plant only.
    """
    physical = physical_sides(plan) if via == "twin" else []
    if not given:
        if physical:
            raise ValueError(
                f"{', '.join(physical)} is physical, so --speed-scale must be given "
                "explicitly: name the fraction of the program's speed the real arm runs at"
            )
        return 1.0
    try:
        value = float(given)
    except ValueError:
        raise ValueError(f"a number is needed, not {given!r}") from None
    return speed_scale(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program.sides", description="List a zone's sides by kind."
    )
    parser.add_argument("--zone", required=True)
    kind = parser.add_mutually_exclusive_group(required=True)
    kind.add_argument("--physical", action="store_true")
    kind.add_argument("--simulated", action="store_true")
    kind.add_argument(
        "--speed-scale",
        metavar="S",
        help="Print the speed scale to run at (S as typed, empty if not given), or refuse.",
    )
    args = parser.parse_args(argv)
    plan = load(default_plan_path(args.zone))
    if args.speed_scale is not None:
        try:
            print(f"{required_speed_scale(plan, args.speed_scale):g}")
        except ValueError as refusal:
            print(f"--speed-scale: {refusal}", file=sys.stderr)
            return 2
        return 0
    for name in physical_sides(plan) if args.physical else simulated_sides(plan):
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
