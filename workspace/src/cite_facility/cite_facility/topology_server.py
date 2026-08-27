#!/usr/bin/env python3
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

"""Serve the process topology generated from L0.

L4 instantiates one behaviour subtree per station without knowing what a station
is, which is only possible if the topology arrives as data. This node is where it
arrives from — the generated artifact, never the model.

Two things were wrong here and both are fixed:

* It published a `std_msgs/String` carrying JSON. That is a standing prohibition
  (CLAUDE.md §4), taken as a deliberate temporary exception on the grounds that
  the typed shape could not be settled before a consumer existed. The L4 line
  coordinator now exists, so the reason expired; the contract is
  `cite_interfaces/LineTopology`.
* It claimed in this docstring to publish LATCHED and published with a bare depth
  of 1, which is RELIABLE/VOLATILE. It published exactly once, in `on_activate`,
  so a subscriber that started a moment later received nothing, ever, with no
  error anywhere — the silent QoS mismatch CLAUDE.md §10 names first. It now uses
  the LATCHED profile from `cite_interfaces.qos`, which is the profile's first
  consumer in the repository.

The topic name is not written here. It is a constant on the message
(`LineTopology.TOPIC`), which is the one place it exists and the place a C++
consumer reads it from too, so the name cannot drift between publisher and
subscriber (P1).
"""

from __future__ import annotations

from cite_facility import runtime
from cite_facility.artifacts import ArtifactError, topology
from cite_interfaces.msg import LineTopology, StationEdge, StationTopology
from cite_interfaces.qos import LATCHED
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

#: The L0 station types, mapped onto the message's constants. A type the model
#: grows that is not listed here fails at `configure` with the name in the
#: message, rather than being published as a number no consumer can act on.
STATION_TYPES = {
    "source_station": StationTopology.TYPE_SOURCE,
    "sink_station": StationTopology.TYPE_SINK,
    "transfer_station": StationTopology.TYPE_TRANSFER,
}

#: The detection states a station can be triggered by, mapped the same way.
TRIGGER_STATES = {
    "clear": StationTopology.TRIGGER_ON_CLEAR,
    "blocked": StationTopology.TRIGGER_ON_BLOCKED,
}


class TopologyServer(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("topology_server")
        self.declare_parameter("zone", "cell_a")
        self._message: LineTopology | None = None
        self._publisher = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        zone = self.get_parameter("zone").get_parameter_value().string_value
        try:
            document = topology(zone)
        except (ArtifactError, KeyError, TypeError) as exc:
            self.get_logger().error(f"cannot configure: {exc}")
            return TransitionCallbackReturn.FAILURE

        try:
            message = _to_message(document)
        except ValueError as exc:
            self.get_logger().error(f"cannot configure: {exc}")
            return TransitionCallbackReturn.FAILURE

        if not message.stations:
            self.get_logger().error(f"the generated topology for zone {zone!r} has no stations")
            return TransitionCallbackReturn.FAILURE

        self._message = message
        # Created here, not published. `configure` may allocate and create
        # interfaces; it must not publish (cross-cutting-lifecycle.md).
        self._publisher = self.create_lifecycle_publisher(
            LineTopology, LineTopology.TOPIC, LATCHED
        )
        self.get_logger().info(
            f"configured with {len(message.stations)} station(s) and "
            f"{len(message.edges)} edge(s)"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        result = super().on_activate(state)
        if self._publisher is not None and self._message is not None:
            self._message.header.stamp = self.get_clock().now().to_msg()
            self._publisher.publish(self._message)
        return result

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        if self._publisher is not None:
            self.destroy_lifecycle_publisher(self._publisher)
            self._publisher = None
        self._message = None
        return TransitionCallbackReturn.SUCCESS


def _to_message(document: dict) -> LineTopology:
    """Turn the generated topology artifact into the typed contract.

    Kept a module function rather than a method so it can be tested without a ROS
    runtime: everything that can go wrong translating the artifact — an unknown
    station type, a trigger naming a state that does not exist — is in here.
    """
    message = LineTopology()
    message.zone = str(document.get("zone", ""))
    message.flow_id = str(document.get("flow", ""))

    for entry in document.get("stations") or []:
        station = StationTopology()
        station.id = str(entry["id"])
        raw_type = str(entry["type"])
        if raw_type not in STATION_TYPES:
            raise ValueError(
                f"station {station.id!r} has type {raw_type!r}, which "
                f"{__name__} cannot map onto StationTopology.TYPE_*. Known types: "
                f"{', '.join(sorted(STATION_TYPES))}."
            )
        station.type = STATION_TYPES[raw_type]
        station.actor_asset_id = str(entry.get("actor") or "")
        station.capacity = int(entry.get("capacity") or 0)
        station.pick_frame = str(entry.get("pick_frame") or "")
        station.place_frame = str(entry.get("place_frame") or "")

        trigger = entry.get("trigger") or {}
        station.trigger_topic = str(trigger.get("topic") or "")
        if station.trigger_topic:
            raw_state = str(trigger.get("state") or "")
            if raw_state not in TRIGGER_STATES:
                raise ValueError(
                    f"station {station.id!r} triggers on detection state "
                    f"{raw_state!r}, which is not one of "
                    f"{', '.join(sorted(TRIGGER_STATES))}"
                )
            station.trigger_state = TRIGGER_STATES[raw_state]

        station.upstream_ids = [str(v) for v in entry.get("upstream") or []]
        station.downstream_ids = [str(v) for v in entry.get("downstream") or []]
        message.stations.append(station)

    for entry in document.get("edges") or []:
        edge = StationEdge()
        edge.from_station_id = str(entry["from"])
        edge.to_station_id = str(entry["to"])
        edge.via_asset_id = str(entry.get("via") or "")
        edge.buffer_capacity = int(entry.get("buffer") or 0)
        message.edges.append(edge)

    return message


def main() -> None:
    runtime.init()
    node = TopologyServer()
    try:
        runtime.spin(node)
    finally:
        runtime.shutdown(node)


if __name__ == "__main__":
    main()
