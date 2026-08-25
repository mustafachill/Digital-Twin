#!/usr/bin/env python3
"""Serve the process topology generated from L0.

L4 instantiates one behaviour subtree per station without knowing what a station
is, which is only possible if the topology arrives as data. This node is where it
arrives from — the generated artifact, never the model.

Published on the LATCHED profile: a coordinator that starts late must receive the
topology immediately rather than waiting for a republication.
"""

from __future__ import annotations

import json

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from std_msgs.msg import String

from cite_facility.artifacts import ArtifactError, topology

TOPIC = "/cite/line/topology"


class TopologyServer(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("topology_server")
        self.declare_parameter("zone", "cell_a")
        self._topology: dict | None = None
        self._publisher = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        zone = self.get_parameter("zone").get_parameter_value().string_value
        try:
            self._topology = topology(zone)
        except (ArtifactError, KeyError) as exc:
            self.get_logger().error(f"cannot configure: {exc}")
            return TransitionCallbackReturn.FAILURE

        stations = self._topology.get("stations") or []
        if not stations:
            self.get_logger().error(f"the generated topology for zone {zone!r} has no stations")
            return TransitionCallbackReturn.FAILURE

        self.get_logger().info(f"configured with {len(stations)} station(s)")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        # NOTE: a String carrying structured data is a standing prohibition
        # (CLAUDE.md §4), and this is a deliberate, temporary exception that must
        # not survive Phase 1.D. The typed replacement is a LineTopology message
        # in cite_interfaces; it is not defined yet because its shape is settled
        # by the L4 coordinator, and defining it before that would mean changing
        # it once consumers exist. Until then nothing consumes this topic.
        self._publisher = self.create_lifecycle_publisher(String, TOPIC, 1)
        result = super().on_activate(state)
        self._publisher.publish(String(data=json.dumps(self._topology, sort_keys=True)))
        return result

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        if self._publisher is not None:
            self.destroy_lifecycle_publisher(self._publisher)
            self._publisher = None
        self._topology = None
        return TransitionCallbackReturn.SUCCESS


def main() -> None:
    rclpy.init()
    node = TopologyServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
