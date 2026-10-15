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

The operator picks a target with every Start robot, Home and Start program
(`ConsoleState.TARGET_*`, ADR-0075): the server never defaults a target; the
panel may preselect SIM (ADR-0072 amendment 2026-10-15). This module is the
ONE place a target is turned into the twin mode it is run in and the sides it commands:

    simulation  -> SIM        -> the plant
    real arm    -> REAL       -> the counterpart
    twin        -> VALIDATED  -> both

The sides are the ones `cite_twin.routing` commands in that mode; this package
cannot import `cite_twin` (it depends on this one), so `cite_twin`'s tests hold
the two equal rather than either restating the other unchecked.

It also says which targets a running deployment can serve: a target is offered
- selectable, and accepted by Start robot - when every side it commands is UP
NOW (`TwinSides.running`; ADR-0075 decision 4 as ADR-0077 amends it: an
operator console's pair keeps its physical counterpart, which comes and goes). Whether a side may be
COMMANDED now is a separate question - a simulated side always, a physical side
only while the twin boundary judges it ready by measurement
(`TwinSides.commandable`, R-19) - which Home and Start program ask
(`not_commandable`): a physical track that has not found its zero accepts Start
robot, the request that zeroes it, and nothing else.
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

#: The target's arms, as the subject of a sentence about what they will do.
MOVERS = {
    SIM: "the simulation's arm",
    REAL: "the real arm",
    TWIN: "both arms (the simulation's and the real one)",
}

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
    """Return the sides this deployment runs whose hardware is physical (R-16: the one place)."""
    return [side for side in physical_sides(plan) if side in running]


def available(running: Collection[str]) -> list[int]:
    """Return the targets every side of which is up now, in panel order (ADR-0075, ADR-0077).

    Commandability is not asked here: a physical side that has not found its
    zero, or that is connected and HELD (ADR-0076), still offers its targets,
    so Start robot - the request that zeroes and releases it - can be sent to
    them. Home and Start program ask `not_commandable`.
    """
    return [target for target in ALL if all(side in running for side in SIDES[target])]


def not_commandable(target: int, commandable: Collection[str]) -> list[str]:
    """Return the sides of ``target`` the twin does not call commandable now (R-19)."""
    return [side for side in SIDES.get(target, ()) if side not in commandable]


def refusal(target: int, offered: Sequence[int]) -> str | None:
    """Say why a goal naming ``target`` is rejected now, or None (R-18).

    0 is unset and the server never reads it as a default (the panel may
    preselect SIM, ADR-0072 amendment 2026-10-15); a value no constant names is
    refused by its number; a target the deployment does not offer - a side it
    commands does not run - is refused naming what is offered.
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
            f"{LABELS[target]} is not offered now: a side it commands is not up. "
            f"Offered: {named}"
        )
    return None
