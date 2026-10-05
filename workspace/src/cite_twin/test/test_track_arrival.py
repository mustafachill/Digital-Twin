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

from cite_twin.track_arrival import arrival

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
