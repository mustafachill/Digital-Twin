#!/usr/bin/env python3
"""Publish which facility model this running system was generated from.

L6 requires a recording to carry the model version: a bag recorded against
yesterday's layout is not comparable to today's, and without this stamp the two
are indistinguishable after the fact. L5 needs it too — a divergence measurement
is only meaningful against a stated model.

Published on the LATCHED profile so a node that starts later receives the current
value immediately rather than waiting for a publication that never comes.
"""

from __future__ import annotations

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from cite_facility.artifacts import ArtifactError, generated_dir, model_hash
from cite_interfaces.msg import ModelVersion
from cite_interfaces.qos import LATCHED
from cite_interfaces.srv import GetModelVersion

TOPIC = "/cite/facility/model_version"
SERVICE = "/cite/facility/get_model_version"


class ModelInfo(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("model_info")
        self.declare_parameter("zones", ["cell_a"])
        self._message: ModelVersion | None = None
        self._publisher = None
        self._service = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            digest = model_hash()
        except ArtifactError as exc:
            self.get_logger().error(f"cannot configure: {exc}")
            return TransitionCallbackReturn.FAILURE

        message = ModelVersion()
        message.header.stamp = self.get_clock().now().to_msg()
        message.model_hash = digest
        message.generator_version = _generator_version()
        message.zones = list(
            self.get_parameter("zones").get_parameter_value().string_array_value
        )
        self._message = message

        # Created here, not published. `configure` may allocate and create
        # interfaces; it must not publish (cross-cutting-lifecycle.md).
        self._publisher = self.create_lifecycle_publisher(ModelVersion, TOPIC, LATCHED)
        self._service = self.create_service(
            GetModelVersion, SERVICE, self._on_request
        )
        self.get_logger().info(f"configured for model {digest[:12]}")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        result = super().on_activate(state)
        if self._publisher is not None and self._message is not None:
            self._publisher.publish(self._message)
        return result

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        if self._publisher is not None:
            self.destroy_lifecycle_publisher(self._publisher)
            self._publisher = None
        if self._service is not None:
            self.destroy_service(self._service)
            self._service = None
        self._message = None
        return TransitionCallbackReturn.SUCCESS

    def _on_request(
        self, request: GetModelVersion.Request, response: GetModelVersion.Response
    ) -> GetModelVersion.Response:
        if self._message is not None:
            response.version = self._message
        return response


def _generator_version() -> str:
    """Which cite_tools produced these artifacts.

    Read from the generated package rather than imported: cite_tools is
    host-agnostic tooling with no ROS dependency (ADR-0013) and is deliberately
    not installed alongside the runtime.
    """
    marker = generated_dir() / "GENERATED"
    return "cite_tools" if marker.is_file() else "unknown"


def main() -> None:
    rclpy.init()
    node = ModelInfo()
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
