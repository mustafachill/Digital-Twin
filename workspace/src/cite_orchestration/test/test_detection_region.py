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

"""The region `DetectAt` searches must contain the sensor the station triggers on.

THE DEFECT THIS EXISTS FOR. `DetectAt` asked for a region of 0.30 m about the
station's pick frame. `Detect.Goal.region_size_m` is extents ABOUT the frame, so
that is a half-extent of 0.150 m — and every break beam in this cell stands
0.250 m off its station's pick frame in y, because a beam housing has to clear
the corridor the gripper descends through and `cite_tools.validate.geometric`
enforces that mechanically at 0.100 m of half-width. So no station's `Detect`
could ever see its own beam. Every call came back SUCCESS with an empty list and
the detail "no sensor in this zone lies inside the requested region, so nothing
is observed there. This is not a report that the region is empty" — a distinction
the action carries no code for, and which L4 therefore could not act on.

It was invisible to every existing test. `cite_skills`'s own contract tests send
a 100 m region, "large enough to contain the whole cell", so they exercise the
selection logic and never the number the line actually uses; and
`pick_and_place`, the passing scenario, does not call `Detect` at all.

WHAT THIS ASSERTS, AND WHY IT IS BOTH BOUNDS. Too small and the station is blind
to its own sensor, which is the defect above. Too large and it starts selecting
the NEXT station's beam, and a station would act on a part that is two metres away
and not its own. Both are measured from the generated artifacts, so a layout
change moves this check with the cell and a beam moved out of reach fails a unit
test in milliseconds rather than a scenario in seven minutes.

Nothing here writes a coordinate, a station name, a sensor name or a frame.
"""

from __future__ import annotations

import os
from pathlib import Path
import re

from ament_index_python.packages import get_package_share_directory
import pytest
import yaml

ZONE = "cell_a"

GENERATED = Path(get_package_share_directory("cite_generated"))

#: Where the value under test is written. Supplied by CMake rather than composed
#: from a relative path, because a test that walked `../../` out of its own
#: source tree would pass or fail on where it was invoked from.
SKILL_NODES_HEADER = Path(os.environ["CITE_SKILL_NODES_HEADER"])


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def region_extent_m() -> float:
    """Return the extent `DetectAt` asks for, read from the leaf that asks for it.

    Read rather than restated. The number's whole problem was that it was a
    stand-in nothing checked against the cell, and a test carrying its own copy
    would keep passing after the leaf changed — which is the failure mode this
    repository keeps finding, not a hypothetical.
    """
    text = SKILL_NODES_HEADER.read_text()
    match = re.search(r'InputPort<double>\(\s*"region_m",\s*([0-9.]+)', text)
    assert match, (
        f"no `region_m` default could be found in {SKILL_NODES_HEADER}. This test pins "
        "that number against the generated layout; if the port has been renamed or the "
        "region now arrives from the model, this test should be rewritten to read it "
        "from wherever it now lives rather than deleted"
    )
    return float(match.group(1))


def frames() -> dict[str, tuple[float, float, float]]:
    """Return `child -> xyz` for every generated static transform in the zone.

    Every frame here hangs off one root, so comparing two children's translations
    is comparing them in that root.
    """
    table = _read(GENERATED / "frames" / f"{ZONE}_static_tf.yaml")["static_transforms"]
    return {entry["child"]: tuple(entry["xyz_m"]) for entry in table}


def triggered_stations() -> list[dict]:
    """Return every station the generated topology says acts on a sensor."""
    topology = _read(GENERATED / "topology" / f"{ZONE}_flow.yaml")["topology"]
    return [
        station
        for station in topology["stations"]
        if station.get("actor") and (station.get("trigger") or {}).get("topic")
    ]


def sensor_frames() -> dict[str, str]:
    """Return `detection topic -> the beam's generated TF frame`, from the bring-up plan.

    Keyed by the topic because that is the identifier a station's trigger names,
    and the plan is the one artifact that carries both it and the frame. Composing
    the frame from the asset id would be building a generated name by hand
    (CLAUDE.md §8).
    """
    plan = _read(GENERATED / "bringup" / f"{ZONE}_plan.yaml")["plan"]
    return {sensor["detection_topic"]: sensor["frame_id"] for sensor in plan["sensors"]}


def offsets() -> list[tuple[str, str, tuple[float, float, float]]]:
    """Return each triggered station with its beam's frame and the beam's offset.

    The offset is per axis, from the station's pick frame to the beam's, both
    placed by the generated static transform table.
    """
    placed = frames()
    beams = sensor_frames()
    found = []
    for station in triggered_stations():
        beam_frame = beams[station["trigger"]["topic"]]
        pick = placed[station["pick_frame"]]
        beam = placed[beam_frame]
        found.append(
            (station["id"], beam_frame, tuple(b - p for b, p in zip(beam, pick, strict=True)))
        )
    return found


def test_every_acting_station_has_something_to_observe_with() -> None:
    """A station that acts and observes nothing cannot be started by anything.

    This is the Critical defect in its own right, before any question of region
    size: `station_transfer_1` had no trigger at all, fell through `AwaitTrigger`,
    and came to rest polling `Detect` for ever.
    """
    topology = _read(GENERATED / "topology" / f"{ZONE}_flow.yaml")["topology"]
    acting = [station for station in topology["stations"] if station.get("actor")]
    assert acting, "the generated topology has no acting station, so nothing was checked"
    blind = [s["id"] for s in acting if not (s.get("trigger") or {}).get("topic")]
    assert not blind, (
        f"{blind} act and observe nothing. A station with no trigger falls straight "
        "through the wait for work, and the only thing left in the cycle that can "
        "decline to proceed is `Detect` — which cannot tell an unobserved region from "
        "an empty one. Give it a sensor in model/assets/instances/sensors.yaml"
    )


def test_the_search_region_contains_each_stations_own_beam() -> None:
    half = region_extent_m() / 2.0
    measured = offsets()
    assert measured, "no triggered station was found, so nothing was checked"

    outside = [
        (station, beam, offset)
        for station, beam, offset in measured
        if max(abs(axis) for axis in offset) > half
    ]
    assert not outside, (
        "these stations search a region their own beam does not lie in, so `Detect` "
        "answers SUCCESS with an empty list for ever:\n  "
        + "\n  ".join(
            f"{station}: {beam} is {offset} from the pick frame, against a half-extent "
            f"of {half:.3f} m"
            for station, beam, offset in outside
        )
        + "\n`cite_skills::inside_region` is inclusive and measures about the frame, so "
        "the extent has to be more than twice the largest of those offsets."
    )


def test_the_search_region_does_not_reach_a_neighbouring_beam() -> None:
    """Refuse a region wide enough to catch a beam belonging to another station.

    The other bound. A station acting on a neighbour's detection picks at a part
    that is not there — a wrong answer that looks exactly like a right one.
    """
    half = region_extent_m() / 2.0
    placed = frames()
    beams = sensor_frames()

    intruders = []
    for station in triggered_stations():
        own = beams[station["trigger"]["topic"]]
        pick = placed[station["pick_frame"]]
        for beam_frame in beams.values():
            if beam_frame == own:
                continue
            offset = [abs(b - p) for b, p in zip(placed[beam_frame], pick, strict=True)]
            if max(offset) <= half:
                intruders.append((station["id"], beam_frame, tuple(offset)))
    assert not intruders, (
        "these stations would select a beam that is not their own:\n  "
        + "\n  ".join(f"{s}: {b} at {o}" for s, b, o in intruders)
        + f"\nagainst a half-extent of {half:.3f} m. A station acting on another "
        "station's detection picks at a part that is not there."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
