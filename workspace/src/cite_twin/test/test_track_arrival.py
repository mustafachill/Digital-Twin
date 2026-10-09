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

from cite_interfaces.srv import TrackArrived
from cite_twin.track_arrival import apart, arrival, elsewhere, unheard

ARRIVED = TrackArrived.Response.ARRIVED
AWAY = TrackArrived.Response.AWAY
UNHEARD = TrackArrived.Response.UNHEARD

SIDES = ("plant", "counterpart")
AGE = 0.25


def _ask(heard, physical=("counterpart",), now=10.0, target=0.65, tolerance=0.001):
    return arrival(SIDES, heard, physical, target, tolerance, now, AGE)


def test_every_side_at_the_target_has_arrived() -> None:
    assert _ask({"plant": (0.65, 10.0), "counterpart": (0.6505, 9.9)}) == (ARRIVED, None)


def test_the_plant_alone_at_the_target_has_not() -> None:
    reason, detail = _ask({"plant": (0.65, 10.0), "counterpart": (0.30, 9.9)})
    assert reason == AWAY
    assert "counterpart: stands at 300.0 mm" in detail
    assert "plant" not in detail.replace("counterpart", "")


def test_a_side_never_heard_has_not_arrived() -> None:
    reason, detail = _ask({"plant": (0.65, 10.0)})
    assert reason == UNHEARD and "counterpart: no track position heard" in detail


def test_a_stale_physical_position_does_not_count() -> None:
    """A carriage read too long ago may be anywhere since."""
    reason, detail = _ask({"plant": (0.65, 0.0), "counterpart": (0.65, 10.0 - AGE - 0.01)})
    assert reason == UNHEARD and "counterpart" in detail and "old" in detail


def test_away_outranks_unheard() -> None:
    """R-01: a carriage heard elsewhere does not clear by itself; one unheard does."""
    reason, detail = _ask({"plant": (0.30, 10.0)})
    assert reason == AWAY
    assert "plant: stands at 300.0 mm" in detail and "no track position heard" in detail


def test_a_simulated_position_is_its_simulators_however_old() -> None:
    """A simulated side's carriage is held by its own controller; its clock may crawl."""
    assert _ask({"plant": (0.65, 0.0), "counterpart": (0.65, 0.0)}, physical=()) == (
        ARRIVED,
        None,
    )


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


# --- S-02: whether a physical carriage stands still, from the plan's values ----

MAX_AGE_S = 0.25
TOLERANCE_M = 0.001


def test_two_fresh_samples_far_enough_apart_and_still_are_stationary() -> None:
    from cite_twin.track_arrival import moving

    samples = [(0.1, 0.0), (0.1005, 0.1), (0.1, 0.2), (0.1002, 0.3)]
    assert moving("j", samples, 0.35, MAX_AGE_S, TOLERANCE_M) is None


def test_a_carriage_that_moved_within_the_window_is_not_stationary() -> None:
    from cite_twin.track_arrival import moving

    samples = [(0.1, 0.0), (0.12, 0.1), (0.13, 0.3)]
    reason = moving("j", samples, 0.35, MAX_AGE_S, TOLERANCE_M)
    assert reason is not None and "moved" in reason


def test_a_movement_before_the_window_does_not_count() -> None:
    from cite_twin.track_arrival import moving

    # Moved until 0.1 s, then still from 0.2 s to 0.6 s: the sample at 0.2 s is
    # the newest at least MAX_AGE_S before the latest, and nothing since moved.
    samples = [(0.0, 0.0), (0.2, 0.1), (0.3, 0.2), (0.3, 0.4), (0.3, 0.6)]
    assert moving("j", samples, 0.6, MAX_AGE_S, TOLERANCE_M) is None


def test_a_stale_or_too_short_history_is_not_stationary() -> None:
    from cite_twin.track_arrival import moving

    assert "no position" in moving("j", [], 1.0, MAX_AGE_S, TOLERANCE_M)
    # The latest is older than MAX_AGE_S: not fresh.
    assert "old" in moving("j", [(0.1, 0.0), (0.1, 0.3)], 0.6, MAX_AGE_S, TOLERANCE_M)
    # Fresh, but no sample MAX_AGE_S before it yet.
    assert "not heard for" in moving("j", [(0.1, 0.0), (0.1, 0.1)], 0.15, MAX_AGE_S, TOLERANCE_M)
    assert "state_max_age_s" in moving("j", [(0.1, 0.0)], 0.0, None, TOLERANCE_M)


def test_the_history_keeps_only_what_the_judgement_needs() -> None:
    from cite_twin.track_arrival import recent

    samples = [(0.0, 0.0), (0.0, 0.1), (0.0, 0.2), (0.0, 0.5), (0.0, 0.6)]
    # The newest at least MAX_AGE_S before 0.6 s is the one at 0.2 s.
    assert recent(samples, MAX_AGE_S) == samples[2:]
    assert recent([], MAX_AGE_S) == []
