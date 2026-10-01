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

"""What every scenario has to work out about the cell it is pointed at.

Two derivations lived in three places before this file existed: `cell()` was
byte-identical in two scenarios and inlined in a third, and the rule for finding
the station that acts was written twice. Neither is obvious enough to be safe as a copy — see
`acting_stations` below for why reading the station list in file order finds the
wrong one — and a copy that drifts produces a scenario that drives a different
station from the one it reports.

The leading underscore keeps this out of `./scripts/scenario`'s listing and out
of the guards' `scenario_paths()`: it is a helper, not a runnable scenario.

NO ROS AT MODULE SCOPE, deliberately. `tests/scenarios/guards/` loads the
scenario modules on a host with no ROS overlay, so anything they import at module
level must import on that host too. `cell()` reaches into the built workspace and
does its importing inside the function, which is the rule the scenarios already
followed for the same reason.
"""

from __future__ import annotations

import importlib.util
import os
import xml.etree.ElementTree as ElementTree
from pathlib import Path

#: The repository root, from this file's place in it.
_ROOT = Path(__file__).resolve().parents[2]

#: The one statement of the zone-default rule (ADR-0069 decision 5), loaded BY
#: PATH: `cite_bringup` is a workspace package the ROS-free guards cannot import,
#: and `zones.py` is written to be read this way — standard library only, no
#: sibling imports.
_ZONES = _ROOT / "workspace" / "src" / "cite_bringup" / "cite_bringup" / "zones.py"

#: The generated bring-up plans the default is read from. A module constant so
#: the guards can point it at a synthetic plan set; every scenario leaves it.
PLANS = _ROOT / "workspace" / "src" / "cite_generated" / "bringup"

#: Where `./scripts/scenario --zone` puts its answer. An environment variable
#: rather than an argument because `launch_test` owns the scenario's argv and
#: passes nothing of ours through it; `CITE_`-prefixed so that
#: `exec_in_container` carries it into the container with the rest.
SELECTED_BY = "CITE_SCENARIO_ZONE"


def _zones_module():
    spec = importlib.util.spec_from_file_location("_cite_bringup_zones", _ZONES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def zone(plans: Path | None = None) -> str:
    """Which cell this run drives: the selection, else the model's only zone.

    THE DEFAULT IS NOT STATED HERE. It is `cite_bringup/zones.py`'s answer — the
    one zone the generated plans declare — so the scenarios, `./scripts/sim` and
    `./scripts/program` cannot disagree about it. When the model declares more
    than one zone there is no default, and this raises `NoDefaultZone` naming them:
    a scenario run then has to be given `--zone`, which is ADR-0056's rule
    returning by itself.

    **THIS FUNCTION reads the environment on every call; the SCENARIOS bind
    `ZONE = zone()` once at module scope.** A scenario process is handed its
    environment by `./scripts/scenario` before it starts and drives one cell from
    the first assertion to the last, so it resolves the answer once. The guards
    import these modules on a host that runs no cell, and set and unset the
    variable expecting a different answer each time, which a module-level read
    here would freeze.
    """
    selected = os.environ.get(SELECTED_BY)
    if selected:
        return selected
    return _zones_module().default_zone(PLANS if plans is None else plans)


def cell(zone_id: str) -> tuple:
    """The generated bring-up plan and process topology for ``zone_id``.

    Imported inside the function, not at module scope: `cite_bringup` is a
    workspace package and `plan.load` reads a file out of the built workspace,
    which the ROS-free guards have no reason to require.
    """
    import yaml
    from cite_bringup.plan import default_plan_path, load

    plan = load(default_plan_path(zone_id))
    return plan, yaml.safe_load(Path(plan.topology).read_text())["topology"]


def acting_stations(topology: dict) -> list[dict]:
    """Every station that picks and places, in flow order.

    THE ORDER IS THE POINT, and it is why this is not a list comprehension at
    each call site. The generated topology emits its stations ALPHABETICALLY, so
    "the first station in the list that acts" finds whichever id sorts first —
    in `cell_b` that is `b_accumulation`, the sink, which acts not at all.
    Walking the edges instead asks the flow rather than the spelling.
    """
    stations = {station["id"]: station for station in topology["stations"]}
    ordered: list[dict] = []
    for edge in topology["edges"]:
        station = stations[edge["from"]]
        if station.get("pick_frame") and station not in ordered:
            ordered.append(station)
    return ordered


def acting_station(topology: dict) -> dict:
    """The first station in flow order that picks and places.

    What a one-arm cell has exactly one of, and a scenario driving a single arm
    is asking for. Raises rather than returning None: a cell with nothing that
    acts is a cell no scenario can drive, and that is a diagnosis, not a skip.
    """
    ordered = acting_stations(topology)
    if not ordered:
        raise ValueError(
            f"the topology for zone {topology.get('zone')!r} declares no station with a "
            "pick frame, so nothing in it picks and places and there is no arm for a "
            "scenario to drive"
        )
    return ordered[0]


def tie_the_work_piece_size(size_m: float, zone_id: str) -> None:
    """Check that a scenario and the plan it drives mean one box.

    A scenario's `WORKPIECE_SIZE` and the part the bring-up plan states — which
    `cite_bringup.workpiece` spawns (ADR-0067) — are the same quantity in two
    places: the first is what the scenario measures heights against at module
    scope, where the guards load it on a host with no ROS and no plan, and the
    second is what is actually in the world. So the two are tied at run time
    instead, and this is that tie, written once rather than once per scenario.

    CALL IT FROM `setUpClass` AND NOWHERE ELSE. It was an assertion inside
    `_spawn_workpiece` first, and the guards drive that method unbound against a
    fabricated `self` — so it fired on the stub and replaced the diagnosis a
    guard was reading with its own. `setUpClass` is reached only by a real run,
    where both values are real.

    Imported inside the function for the reason the module docstring gives.
    """
    from cite_bringup.workpiece import part_of

    plan, _ = cell(zone_id)
    for name in carried_models(Path(plan.world)):
        part = part_of(plan, name)
        if part.size_m != (size_m, size_m, size_m):
            raise AssertionError(
                f"this scenario measures against a {size_m} m work-piece and the "
                f"{zone_id} plan spawns {name!r} as {part.size_m}, so every height "
                "assertion in it is about a different box from the one in the world"
            )


def world_root(world: Path) -> ElementTree.Element:
    """The generated world, parsed. Plain XML, so no simulator is needed."""
    return ElementTree.parse(world).getroot()


def carried_models(world: Path) -> frozenset[str]:
    """Every Gazebo model name the belts carry and the beams watch.

    Both plugins match this set EXACTLY — `carried_.count(name->Data())` in
    `conveyor.cpp`, `watched_.count(name->Data())` in `break_beam.cpp` — so a
    part spawned under any other name rides through the cell untouched and
    unseen. The intersection is taken rather than either list alone: a name a
    belt carries but no beam watches would move and never be reported, and a
    scenario that fed one would be testing a piece the line is blind to.

    Here rather than in a scenario because the name is a facility fact: a
    literal `"workpiece"` in a scenario would be a second statement of
    `facility.workpiece_models`, which is exactly the value in two places
    CLAUDE.md §4 prohibits.
    """
    root = world_root(world)
    carried = {element.text.strip() for element in root.iter("carry") if element.text}
    watched = {element.text.strip() for element in root.iter("watch") if element.text}
    return frozenset(carried & watched)
