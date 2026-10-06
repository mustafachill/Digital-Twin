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
    --zone cell_b --hardware-opt-in  refuse unless the opt-in permits a physical side

`./scripts/program` asks this before every Gazebo-only step (ADR-0070 item 7):
it spawns a box, removes one, reads a model's pose and runs a belt only on a
simulated side, and on a physical side says so and asks a person instead. The
answer is the plan's declared fact (`commands_physical_hardware_on_or_none`),
never an asset's type or a backend's name.
"""

from __future__ import annotations

import argparse
import os
import sys

from cite_bringup.plan import (
    default_plan_path,
    HARDWARE_OPT_IN_ENV,
    HARDWARE_OPT_IN_VALUE,
    HardwareNotPermittedError,
    load,
    Plan,
    require_hardware_opt_in,
)
from cite_bringup.program.steps import speed_scale
from cite_hardware.mapping import slowest_speed_mps
import yaml


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


def minimum_speed_scale(plan: Plan) -> float | None:
    """Return the slowest scale a physical track carries the program's slowest slide at.

    SA-S-07. A slide below the track adapter's slowest speed is refused there
    (`cite_hardware.mapping.slowest_speed_mps`, the one statement of that
    rule); this asks the same rule, with the adapter's own generated
    `position_scale` and `segment_s`, of the slowest track step of the plan's
    program, so the scale is refused before anything is brought up. `None`
    where no physical side runs a track adapter or the program slides no track.
    """
    slides = [
        step.speed_mps
        for program in plan.programs
        for step in program.steps
        if step.kind == "track" and step.speed_mps > 0.0
    ]
    floors = []
    for side in physical_sides(plan):
        for manager in plan.controller_managers:
            physical = manager.physical_on(side)
            if physical is None or physical.track_adapter is None:
                continue
            document = yaml.safe_load(physical.parameters.read_text()) or {}
            adapter = document[physical.track_adapter]["ros__parameters"]
            floors.append(
                slowest_speed_mps(float(adapter["position_scale"]), float(adapter["segment_s"]))
            )
    if not slides or not floors:
        return None
    return max(floors) / min(slides)


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
    value = speed_scale(value)
    minimum = minimum_speed_scale(plan) if physical else None
    if minimum is not None and value < minimum * (1.0 - 1e-9):
        raise ValueError(
            f"{value:g} is below {minimum:g}: at it the program's slowest track slide is "
            "slower than the physical track carries out, and its adapter would refuse it"
        )
    return value


def hardware_opt_in_refusal(plan: Plan, environ) -> str | None:
    """Say why a run may not bring up this plan's physical sides, or None if it may (T-01).

    The rule is `require_hardware_opt_in`'s, asked of the physical sides only;
    this adds the words `./scripts/program` says before bring-up, so the
    refusal is not found deep in a side's launch log instead.
    """
    physical = physical_sides(plan)
    if not physical:
        return None
    try:
        require_hardware_opt_in(plan, environ, physical)
    except HardwareNotPermittedError as refusal:
        return (
            f"{', '.join(physical)} is physical, and nothing is brought up without "
            f"{HARDWARE_OPT_IN_ENV}={HARDWARE_OPT_IN_VALUE} set in the shell that runs this "
            "or in the repository-root .env, "
            f"once the cell is confirmed clear. {refusal}"
        )
    return None


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
    kind.add_argument(
        "--hardware-opt-in",
        action="store_true",
        help=f"Refuse unless {HARDWARE_OPT_IN_ENV} permits bringing up every physical side.",
    )
    args = parser.parse_args(argv)
    plan = load(default_plan_path(args.zone))
    if args.hardware_opt_in:
        refusal = hardware_opt_in_refusal(plan, os.environ)
        if refusal is not None:
            print(refusal, file=sys.stderr)
            return 2
        return 0
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
