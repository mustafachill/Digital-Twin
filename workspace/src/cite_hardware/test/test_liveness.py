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


def _healthy() -> Liveness:
    liveness = Liveness(ZONE, 0.5)
    liveness.activate()
    assert liveness.heartbeat(ZONE, 1).accepted
    assert liveness.state == HEALTHY
    return liveness


def test_nothing_is_permitted_before_activation() -> None:
    liveness = Liveness(ZONE, 0.5)
    assert liveness.state == INACTIVE
    assert not liveness.permits_motion
    assert not liveness.heartbeat(ZONE, 1).accepted
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
    outcome = liveness.heartbeat("cell_a", 1)
    assert not outcome.accepted
    assert "cell_a" in outcome.reason
    assert liveness.state == AWAITING


def test_a_repeated_or_rewound_sequence_is_not_fresh() -> None:
    liveness = _healthy()
    assert liveness.heartbeat(ZONE, 2).accepted
    assert not liveness.heartbeat(ZONE, 2).accepted
    assert not liveness.heartbeat(ZONE, 1).accepted
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
    assert not liveness.heartbeat(ZONE, 99).accepted
    assert liveness.state == TRIPPED
    assert not liveness.permits_motion


def test_only_deactivate_then_activate_clears_a_trip() -> None:
    liveness = _healthy()
    liveness.expired()
    liveness.deactivate()
    assert liveness.state == INACTIVE
    liveness.activate()
    assert liveness.state == AWAITING
    # A restarted boundary counts from 1 again, and is accepted after a reset.
    assert liveness.heartbeat(ZONE, 1).accepted
    assert liveness.permits_motion


@pytest.mark.parametrize("zone, timeout", [("", 0.5), (ZONE, 0.0), (ZONE, -1.0)])
def test_a_deadman_without_a_zone_or_a_timeout_is_refused(zone, timeout) -> None:
    with pytest.raises(ValueError):
        Liveness(zone, timeout)
