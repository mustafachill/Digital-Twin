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

"""The deadman's state machine: events in, state out, no clock and no graph."""

from __future__ import annotations

from cite_hardware.liveness import AWAITING, HEALTHY, INACTIVE, Liveness, TRIPPED
import pytest

ZONE = "cell_b"
BOUNDARY = "boundary-a"


def _healthy() -> Liveness:
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    assert liveness.heartbeat(ZONE, BOUNDARY, 1, 1).accepted
    assert liveness.state == HEALTHY
    return liveness


def test_nothing_is_permitted_before_activation() -> None:
    liveness = Liveness(ZONE, 0.5)
    assert liveness.state == INACTIVE
    assert not liveness.permits_motion
    assert not liveness.heartbeat(ZONE, BOUNDARY, 1, 1).accepted
    assert liveness.state == INACTIVE


def test_nothing_is_permitted_before_the_first_heartbeat() -> None:
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    assert liveness.state == AWAITING
    assert not liveness.permits_motion


def test_awaiting_never_trips() -> None:
    """Before any heartbeat there is no commander whose loss could be detected."""
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    assert not liveness.expired().tripped
    assert not liveness.publisher_lost().tripped
    assert liveness.state == AWAITING


def test_the_first_heartbeat_permits_motion() -> None:
    assert _healthy().permits_motion


def test_a_heartbeat_from_another_zone_does_not_count() -> None:
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    outcome = liveness.heartbeat("cell_a", BOUNDARY, 1, 1)
    assert not outcome.accepted
    assert "cell_a" in outcome.reason
    assert liveness.state == AWAITING


def test_a_repeated_or_rewound_sequence_is_not_fresh() -> None:
    liveness = _healthy()
    assert liveness.heartbeat(ZONE, BOUNDARY, 2, 1).accepted
    assert not liveness.heartbeat(ZONE, BOUNDARY, 2, 1).accepted
    assert not liveness.heartbeat(ZONE, BOUNDARY, 1, 1).accepted
    assert liveness.last_sequence == 2


def test_the_timeout_trips_once() -> None:
    liveness = _healthy()
    first = liveness.expired()
    assert first.tripped
    assert liveness.state == TRIPPED
    assert not liveness.permits_motion
    # Exactly one event per trip carries `tripped`, so the stops go out once.
    assert not liveness.expired().tripped
    assert not liveness.publisher_lost().tripped


def test_losing_the_publisher_trips() -> None:
    liveness = _healthy()
    outcome = liveness.publisher_lost()
    assert outcome.tripped
    assert "disappeared" in outcome.reason
    assert liveness.state == TRIPPED


def test_a_trip_is_latched_against_resumed_heartbeats() -> None:
    liveness = _healthy()
    liveness.expired()
    assert not liveness.heartbeat(ZONE, BOUNDARY, 99, 1).accepted
    assert liveness.state == TRIPPED
    assert not liveness.permits_motion


def test_only_deactivate_then_activate_clears_a_trip() -> None:
    liveness = _healthy()
    liveness.expired()
    liveness.deactivate()
    assert liveness.state == INACTIVE
    liveness.activate()
    assert liveness.state == AWAITING
    # A restarted boundary has a new id and counts from 1 again, and is
    # accepted after a reset.
    assert liveness.heartbeat(ZONE, "boundary-b", 1, 1).accepted
    assert liveness.permits_motion
    assert liveness.boundary_id == "boundary-b"


@pytest.mark.parametrize("zone, timeout", [("", 0.5), (ZONE, 0.0), (ZONE, -1.0)])
def test_a_deadman_without_a_zone_or_a_timeout_is_refused(zone, timeout) -> None:
    with pytest.raises(ValueError):
        Liveness(zone, timeout)


def test_the_first_boundary_id_is_latched_and_another_trips() -> None:
    """S-07: a second boundary commanding the same side is a fault, not a commander."""
    liveness = _healthy()
    assert liveness.boundary_id == BOUNDARY
    outcome = liveness.heartbeat(ZONE, "boundary-b", 2, 1)
    assert outcome.tripped
    assert "boundary-b" in outcome.reason
    assert liveness.state == TRIPPED


def test_a_second_heartbeat_publisher_trips_when_healthy() -> None:
    liveness = _healthy()
    outcome = liveness.heartbeat(ZONE, BOUNDARY, 2, 2)
    assert outcome.tripped
    assert liveness.state == TRIPPED


def test_a_second_heartbeat_publisher_keeps_awaiting() -> None:
    """Before any boundary is followed, two of them are not one to follow."""
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    outcome = liveness.heartbeat(ZONE, BOUNDARY, 1, 2)
    assert not outcome.accepted and not outcome.tripped
    assert liveness.state == AWAITING
    assert liveness.boundary_id == ""


def test_a_heartbeat_without_a_boundary_id_does_not_count() -> None:
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    assert not liveness.heartbeat(ZONE, "", 1, 1).accepted
    assert liveness.state == AWAITING


def test_losing_the_vendor_trips_when_healthy_and_latches() -> None:
    """N-03: a vendor driver that went away or restarted re-enabled the arm itself."""
    liveness = _healthy()
    outcome = liveness.vendor_lost("set_state is served 0 times")
    assert outcome.tripped
    assert "served 0 times" in outcome.reason
    assert liveness.state == TRIPPED
    assert not liveness.vendor_lost("again").tripped
    assert not liveness.heartbeat(ZONE, BOUNDARY, 5, 1).accepted
    assert liveness.state == TRIPPED


def test_losing_the_vendor_before_healthy_does_not_trip() -> None:
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    assert not liveness.vendor_lost("no vendor yet").tripped
    assert liveness.state == AWAITING
