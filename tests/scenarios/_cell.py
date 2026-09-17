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
byte-identical in `bringup.py` and `pick_and_place.py` and inlined a third time
in `continuous_line.py`, and the rule for finding the station that acts was
written twice. Neither is obvious enough to be safe as a copy — see
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

import os
from pathlib import Path

#: The zone the scenarios drive when nothing says otherwise, stated ONCE for all
#: three of them (ADR-0056 decision 5). It was a `ZONE = "cell_b"` literal in each
#: scenario until this file existed: three statements of one fact, able to
#: disagree silently, which is the shape CLAUDE.md §4 prohibits.
#:
#: `cell_a`, the three-arm cell Phase 1 closed on, is kept as a zone and is no
#: longer driven by these scenarios — a deliberate reduction in regression
#: coverage recorded in ADR-0056's consequences. ADR-0056 names "a cheap periodic
#: `bringup` against `cell_a`" as the answer if the showcase is found broken, and
#: `SELECTED_BY` below is what makes that a command rather than a commit:
#: `./scripts/scenario bringup --zone cell_a`.
DRIVEN_ZONE = "cell_b"

#: Where `./scripts/scenario --zone` puts its answer. An environment variable
#: rather than an argument because `launch_test` owns the scenario's argv and
#: passes nothing of ours through it; `CITE_`-prefixed so that
#: `exec_in_container` carries it into the container with the rest.
SELECTED_BY = "CITE_SCENARIO_ZONE"


def zone() -> str:
    """Which cell this run drives.

    Read at call time rather than at import: `./scripts/scenario` sets it in the
    environment, and a module-level read would freeze whatever was set when the
    guards imported the module on a host that runs no cell at all.
    """
    return os.environ.get(SELECTED_BY) or DRIVEN_ZONE


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
    in `cell_b` that is `b_accumulation`, the sink, which acts not at all, and in
    `cell_a` the same sort puts `station_accumulation` first. Walking the edges
    instead asks the flow rather than the spelling.
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
