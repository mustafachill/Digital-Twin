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

"""Where the signal goes: the simulation, the real arm, or the twin (ADR-0072).

The operator picks a target with every Home and Start program, and it is never
defaulted (`ConsoleState.TARGET_*`). This module is the ONE place a target is
turned into the twin mode it is run in and the sides it commands:

    simulation  -> SIM        -> the plant
    real arm    -> REAL       -> the counterpart
    twin        -> VALIDATED  -> both

The sides are the ones `cite_twin.routing` commands in that mode; this package
cannot import `cite_twin` (it depends on this one), so `cite_twin`'s tests hold
the two equal rather than either restating the other unchecked.

It also says which targets a running deployment can serve: a target is offered
only when every side it commands RUNS (the pair supervisor's `--sides`) and is
COMMANDABLE now - a simulated side always, a physical side only while the twin
boundary judges it ready by measurement (`TwinSides.commandable`, R-19).
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from cite_bringup.plan import COUNTERPART_SIDE, Plan, PLANT_SIDE
from cite_bringup.program.sides import physical_sides
from cite_interfaces.msg import ConsoleState, TwinMode

SIM = ConsoleState.TARGET_SIM
REAL = ConsoleState.TARGET_REAL
TWIN = ConsoleState.TARGET_TWIN

#: Every target, in the order the panel offers them.
ALL = (SIM, REAL, TWIN)

#: The spelling the terminal's `--target` takes.
NAMES = {SIM: "sim", REAL: "real", TWIN: "twin"}

#: What an operator reads, in a prompt and a refusal.
LABELS = {SIM: "the simulation", REAL: "the real arm", TWIN: "the twin (simulation and real arm)"}

#: The target's arms, as the subject of a sentence about where they are.
ARMS = {SIM: "the simulation's arm is", REAL: "the real arm is", TWIN: "both arms are"}

#: The twin mode each target is run in.
MODES = {SIM: TwinMode.MODE_SIM, REAL: TwinMode.MODE_REAL, TWIN: TwinMode.MODE_VALIDATED}

#: The sides each target commands, in plan order - the plant first.
SIDES = {SIM: (PLANT_SIDE,), REAL: (COUNTERPART_SIDE,), TWIN: (PLANT_SIDE, COUNTERPART_SIDE)}


def label(target: int) -> str:
    return LABELS.get(target, f"target {target}")


def by_name(name: str) -> int:
    """Return the target ``name`` (`sim`, `real`, `twin`) spells, or raise `ValueError`."""
    for target, spelled in NAMES.items():
        if spelled == name:
            return target
    raise ValueError(f"{name!r} is not a target; one of {', '.join(NAMES.values())}")


def homing_allowance(target: int) -> bool:
    """Whether a home in ``target`` asks `SetMode.homing`: VALIDATED's alone (R-11)."""
    return MODES[target] == TwinMode.MODE_VALIDATED


def running_physical(plan: Plan, running: Collection[str]) -> list[str]:
    """The sides this deployment runs whose hardware is physical (R-16: the one place)."""
    return [side for side in physical_sides(plan) if side in running]


def available(running: Collection[str], commandable: Collection[str]) -> list[int]:
    """The targets every side of which runs and is commandable now, in panel order."""
    return [
        target
        for target in ALL
        if all(side in running and side in commandable for side in SIDES[target])
    ]


def refusal(target: int, offered: Sequence[int]) -> str | None:
    """Say why a goal naming ``target`` is rejected now, or None (R-18).

    0 is unset and never read as a default; a value no constant names is
    refused by its number; a target the deployment does not offer now - its
    sides are not running, or a physical one is not ready - is refused naming
    what is offered.
    """
    if target == 0:
        return (
            "no target was sent: the panel names the simulation, the real arm or the twin "
            "with every goal, and none is defaulted (ADR-0072)"
        )
    if target not in MODES:
        return f"{target} is not a target (ConsoleState.TARGET_*)"
    if target not in offered:
        named = ", ".join(LABELS[item] for item in offered) or "nothing"
        return (
            f"{LABELS[target]} is not offered now: a side it commands does not run, or is "
            f"not ready to be commanded. Offered: {named}"
        )
    return None
