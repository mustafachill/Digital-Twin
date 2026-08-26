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

"""Every belt the line indexes can actually be commanded (ADR-0032).

`line_orchestrator` derives which belt a station stops from the topology — it is
the `via_asset_id` of the inbound edge of a station that has a robot actor — and
gets the topic and the speed to command it with from the bring-up plan. Those are
two generated artifacts, and nothing checks that they agree about the same set of
belts.

WHAT GOES WRONG WHEN THEY DO NOT. A belt named by the topology and missing from
the plan is a belt the line stops on the first work-piece and never starts again:
a stalled line that looks, from every topic the coordinator publishes, exactly
like a line waiting for work. The coordinator refuses at start-up rather than
running that way, but a refusal discovered by launching the cell costs a
seven-minute scenario; this costs milliseconds and names the belt.

The mirror case is the one that made the rule what it is. `station_accumulation`
is a sink: it has a trigger (`beam_c3_out`) and no actor, so it has no
`CompleteHandoff` to run its belt again on. A rule keyed on the trigger rather
than on the actor would stop `conveyor_3` for ever, and the ladder would end one
milestone short with no error anywhere.

Nothing here writes a station name, a belt name, a topic or a speed.
"""

from __future__ import annotations

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
import pytest
import yaml

ZONE = "cell_a"

GENERATED = Path(get_package_share_directory("cite_generated"))


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def topology() -> dict:
    return _read(GENERATED / "topology" / f"{ZONE}_flow.yaml")["topology"]


def conveyors() -> dict[str, dict]:
    """Return `asset -> the drive the plan declares for it`."""
    plan = _read(GENERATED / "bringup" / f"{ZONE}_plan.yaml")["plan"]
    return {entry["asset"]: entry for entry in plan.get("conveyors", [])}


def carriers() -> dict[tuple[str, str], str]:
    """Return `(from, to) -> the asset that carries between them`, empty when none."""
    return {
        (edge["from"], edge["to"]): (edge.get("via") or "")
        for edge in topology()["edges"]
    }


def indexed_belts() -> dict[str, str]:
    """Return `belt -> the station that indexes it`, by the coordinator's own rule.

    Derived here the same way `line_plan.hpp` derives it, from the same artifact,
    so that this test and the code answer the question in one way rather than two.
    """
    links = carriers()
    found: dict[str, str] = {}
    for station in topology()["stations"]:
        if not station.get("actor"):
            continue
        for upstream in station.get("upstream") or []:
            belt = links.get((upstream, station["id"]), "")
            if belt:
                found[belt] = station["id"]
    return found


def test_every_indexed_belt_has_a_drive_the_line_can_command() -> None:
    """A belt that is stopped and cannot be started again is a stalled line."""
    indexed = indexed_belts()
    assert indexed, (
        "no station in the generated topology picks from a belt, so nothing was "
        "checked. Either the flow no longer carries work on a conveyor, or this "
        "test is reading the wrong artifact"
    )

    declared = conveyors()
    missing = {belt: station for belt, station in indexed.items() if belt not in declared}
    assert not missing, (
        f"these belts are indexed and have no drive in the bring-up plan: {missing}. "
        "The coordinator refuses to start rather than stopping a belt it cannot run "
        "again, so this is a cell that will not come up"
    )

    for belt, station in indexed.items():
        drive = declared[belt]
        assert drive.get("command_topic"), (
            f"belt '{belt}', which '{station}' indexes, has no command topic. A setpoint "
            "with nowhere to go is a silent no-op and a belt that never moves"
        )
        speed = drive.get("installed_speed_mps")
        assert isinstance(speed, (int, float)) and speed > 0.0, (
            f"belt '{belt}' is installed at {speed!r} m/s. A belt that cannot run "
            "cannot be indexed: it would be stopped and then 'restarted' to a "
            "standstill, which is a stall reported as a running line"
        )


def test_a_belt_feeding_a_station_with_no_actor_is_never_indexed() -> None:
    """The actor condition, which is the whole reason the rule is not the trigger.

    A sink has a trigger and no actor, so nothing at it completes a handoff. A
    belt indexed on its trigger would stop on the first arrival and stay stopped.
    """
    links = carriers()
    indexed = indexed_belts()

    actors = {station["id"]: station.get("actor") for station in topology()["stations"]}
    into_a_sink = {
        belt: to
        for (_, to), belt in links.items()
        if belt and not actors.get(to)
    }
    assert into_a_sink, (
        "no belt in the generated topology feeds a station without an actor, so the "
        "condition this test exists for is no longer exercised by the model"
    )

    also_indexed = {belt: to for belt, to in into_a_sink.items() if belt in indexed}
    assert not also_indexed, (
        f"these belts feed a station with no actor and would still be indexed: "
        f"{also_indexed}. There is no CompleteHandoff at such a station, so each of "
        "them would be stopped by the first work-piece and never started again"
    )


def test_no_station_indexes_the_belt_it_places_onto() -> None:
    """A station stops the belt work ARRIVES on, never the one it leaves on.

    Freezing the outbound link is the same rule applied one station too far along.
    It looks identical in the code and stops the line one belt downstream of where
    anybody would look for it.
    """
    links = carriers()
    indexed = indexed_belts()

    wrong = []
    for station in topology()["stations"]:
        for downstream in station.get("downstream") or []:
            belt = links.get((station["id"], downstream), "")
            if belt and indexed.get(belt) == station["id"]:
                wrong.append((station["id"], belt))
    assert not wrong, (
        f"these stations would stop the belt they place onto: {wrong}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
