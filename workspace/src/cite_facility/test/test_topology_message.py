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

"""The generated topology, turned into its typed contract.

The translation is the part that can be wrong: a station type that maps onto
nothing, a trigger naming a state that does not exist, a field that quietly
becomes an empty string. Testing the module function rather than the node keeps
this a unit test with no ROS runtime and no lifecycle to drive.

What this replaced is worth stating: the topology was published as a
`std_msgs/String` carrying JSON — a standing prohibition (CLAUDE.md §4) — on a
publisher with a bare depth of 1, which is RELIABLE/VOLATILE, exactly once, in
`on_activate`. A subscriber that started a moment later received nothing, ever,
with no error anywhere.
"""

from __future__ import annotations

from cite_facility.artifacts import topology
from cite_facility.topology_server import _to_message
from cite_interfaces.msg import LineTopology, StationTopology
from cite_interfaces.qos import LATCHED
import pytest
from rclpy.qos import DurabilityPolicy, ReliabilityPolicy


def _message() -> LineTopology:
    return _to_message(topology("cell_a"))


def test_the_generated_topology_becomes_a_typed_message() -> None:
    message = _message()
    assert message.zone == "cell_a"
    assert message.flow_id
    assert {s.id for s in message.stations} >= {
        "station_infeed",
        "station_transfer_1",
        "station_accumulation",
    }
    assert message.edges


def test_the_coordinator_gets_what_it_needs_for_a_transfer_station() -> None:
    """`line_coordinator` is started with an asset and two frames per station.

    Those three values come from here, so a station missing any of them is a
    coordinator that cannot be configured — and the failure would otherwise
    appear as an empty parameter refusal, three layers away from this file.
    """
    message = _message()
    transfers = [s for s in message.stations if s.type == StationTopology.TYPE_TRANSFER]
    assert len(transfers) == 3
    for station in transfers:
        assert station.actor_asset_id, station.id
        assert station.pick_frame, station.id
        assert station.place_frame, station.id


def test_a_source_and_a_sink_have_no_actor_and_no_frames() -> None:
    message = _message()
    for station in message.stations:
        if station.type in (StationTopology.TYPE_SOURCE, StationTopology.TYPE_SINK):
            assert station.actor_asset_id == ""
            assert station.pick_frame == "" and station.place_frame == ""


def test_a_trigger_is_a_constant_and_not_a_string() -> None:
    """Enumerations are uint8 constants (P3).

    A typo in a string comparison is a runtime bug that a constant makes
    impossible, and the valid set is discoverable rather than folklore.
    """
    message = _message()
    triggered = [s for s in message.stations if s.trigger_topic]
    assert triggered, "the generated topology declares no sensor triggers at all"
    for station in triggered:
        assert station.trigger_state == StationTopology.TRIGGER_ON_BLOCKED


def test_the_edges_describe_the_same_line_as_the_stations() -> None:
    message = _message()
    ids = {s.id for s in message.stations}
    for edge in message.edges:
        assert edge.from_station_id in ids, edge.from_station_id
        assert edge.to_station_id in ids, edge.to_station_id


def test_an_unknown_station_type_is_refused_rather_than_guessed() -> None:
    document = {
        "zone": "cell_a",
        "flow": "f",
        "stations": [{"id": "station_x", "type": "inspection_station"}],
        "edges": [],
    }
    with pytest.raises(ValueError, match="inspection_station"):
        _to_message(document)


def test_an_unknown_trigger_state_is_refused() -> None:
    document = {
        "zone": "cell_a",
        "flow": "f",
        "stations": [
            {
                "id": "station_x",
                "type": "transfer_station",
                "trigger": {"topic": "/cite/cell_a/beam/detection", "state": "maybe"},
            }
        ],
        "edges": [],
    }
    with pytest.raises(ValueError, match="maybe"):
        _to_message(document)


def test_the_topic_name_exists_in_exactly_one_place() -> None:
    """The name is a constant on the message, not a literal in the publisher.

    That is what lets the C++ coordinator subscribe with
    `cite_interfaces::msg::LineTopology::TOPIC` instead of composing the string a
    second time — and a name written by hand in a second place is how P2 breaks.
    """
    import inspect

    from cite_facility import topology_server

    assert LineTopology.TOPIC == "/cite/line/topology"
    source = inspect.getsource(topology_server)
    literals = [
        line
        for line in source.splitlines()
        if LineTopology.TOPIC in line and not line.lstrip().startswith("#")
    ]
    assert not literals, (
        f"topology_server writes {LineTopology.TOPIC!r} by hand: {literals}"
    )


def test_the_topology_is_published_latched() -> None:
    """A coordinator that starts late must receive the topology immediately.

    The publisher used to be created with a bare depth of 1 — RELIABLE/VOLATILE —
    under a docstring claiming it was latched, and it published exactly once.
    """
    assert LATCHED.durability == DurabilityPolicy.TRANSIENT_LOCAL
    assert LATCHED.reliability == ReliabilityPolicy.RELIABLE

    import inspect

    from cite_facility import topology_server

    source = inspect.getsource(topology_server.TopologyServer.on_configure)
    assert "LATCHED" in source, (
        "the topology publisher does not use the LATCHED profile, so a late "
        "subscriber connects silently and receives nothing"
    )
