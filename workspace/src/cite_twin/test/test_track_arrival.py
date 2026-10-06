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

"""Whether every commanded side's track stands at a target (SA2c-S-02 c).

Pure logic: the boundary feeds `arrival` what it heard, and the program asks it
through `TrackArrived` before it starts the next step.
"""

from __future__ import annotations

from cite_twin.track_arrival import apart, arrival, elsewhere, unheard

SIDES = ("plant", "counterpart")
AGE = 0.25


def _ask(heard, physical=("counterpart",), now=10.0, target=0.65, tolerance=0.001):
    return arrival(SIDES, heard, physical, target, tolerance, now, AGE)


def test_every_side_at_the_target_has_arrived() -> None:
    assert _ask({"plant": (0.65, 10.0), "counterpart": (0.6505, 9.9)}) is None


def test_the_plant_alone_at_the_target_has_not() -> None:
    reason = _ask({"plant": (0.65, 10.0), "counterpart": (0.30, 9.9)})
    assert reason is not None
    assert "counterpart: stands at 300.0 mm" in reason
    assert "plant" not in reason.replace("counterpart", "")


def test_a_side_never_heard_has_not_arrived() -> None:
    assert "counterpart: no track position heard" in _ask({"plant": (0.65, 10.0)})


def test_a_stale_physical_position_does_not_count() -> None:
    """A carriage read too long ago may be anywhere since."""
    reason = _ask({"plant": (0.65, 0.0), "counterpart": (0.65, 10.0 - AGE - 0.01)})
    assert reason is not None and "counterpart" in reason and "old" in reason


def test_a_simulated_position_is_its_simulators_however_old() -> None:
    """A simulated side's carriage is held by its own controller; its clock may crawl."""
    assert _ask({"plant": (0.65, 0.0), "counterpart": (0.65, 0.0)}, physical=()) is None


# SA-S-01 b: VALIDATED waits until the physical carriage stands where the plant's does.


def _apart(plant, physical, now=10.0, tolerance=0.001):
    return apart("track_joint", plant, "counterpart", physical, tolerance, now, AGE)


def test_a_physical_carriage_away_from_the_plants_is_refused() -> None:
    reason = _apart((0.0, 10.0), (0.30, 9.9))
    assert reason is not None
    assert "counterpart: stands at 300.0 mm" in reason and "home it" in reason


def test_a_physical_carriage_where_the_plants_is_is_accepted() -> None:
    assert _apart((0.30, 0.0), (0.3005, 9.9)) is None


def test_a_stale_physical_carriage_is_not_apart_but_unheard() -> None:
    """S-08: a position too old clears by itself, so it is never the final refusal."""
    stale = (0.0, 10.0 - AGE - 0.01)
    assert _apart((0.30, 10.0), stale) is None
    reason = unheard("track_joint", (0.30, 10.0), "counterpart", stale, 10.0, AGE)
    assert reason is not None and "old" in reason


def test_no_position_on_either_side_is_unheard_and_not_apart() -> None:
    assert _apart((0.30, 10.0), None) is None and _apart(None, (0.30, 10.0)) is None
    assert "no track position heard" in unheard(
        "track_joint", (0.30, 10.0), "counterpart", None, 10.0, AGE
    )
    assert "no plant" in unheard("track_joint", None, "counterpart", (0.30, 10.0), 10.0, AGE)
    assert unheard("track_joint", (0.30, 10.0), "counterpart", (0.0, 9.9), 10.0, AGE) is None


def test_a_carriage_elsewhere_is_only_one_heard_fresh_and_away() -> None:
    assert "stands at 0.0 mm" in elsewhere("counterpart", (0.0, 9.9), 0.30, 0.001, 10.0, AGE)
    assert elsewhere("counterpart", (0.30, 9.9), 0.30, 0.001, 10.0, AGE) is None
    assert elsewhere("counterpart", None, 0.30, 0.001, 10.0, AGE) is None
    assert elsewhere("counterpart", (0.0, 9.0), 0.30, 0.001, 10.0, AGE) is None
