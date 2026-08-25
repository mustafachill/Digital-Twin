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

"""Publish the static transforms for everything that is not a robot link.

`robot_state_publisher` covers the links inside a description. This covers the
other half: zone origins, the frames a station reaches for — a conveyor's infeed
and outfeed, a table's surface — and each arm's mount, which is what ties an arm's
own model into the facility frame.

One node, one publisher per transform. Two publishers for a single transform make
TF alternate between them, and the resulting behaviour is intermittent and very
hard to attribute; the artifact reader rejects a table that would cause it.

A managed node (cross-cutting-lifecycle.md): `configure` reads and validates,
`activate` publishes. Nothing is published before activation, so a consumer never
sees a partially-populated tree.
"""

from __future__ import annotations

from cite_facility.artifacts import ArtifactError, static_transforms, StaticTransform
from cite_facility.transforms import quaternion_from_rpy
from geometry_msgs.msg import TransformStamped
import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from tf2_ros import StaticTransformBroadcaster


class FrameServer(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("frame_server")
        self.declare_parameter("zone", "cell_a")
        self._transforms: list[StaticTransform] = []
        self._broadcaster: StaticTransformBroadcaster | None = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        """Read and validate. Publish nothing — that is `activate`'s job."""
        zone = self.get_parameter("zone").get_parameter_value().string_value
        try:
            self._transforms = static_transforms(zone)
        except ArtifactError as exc:
            # Failing here stops bring-up with a diagnosis. Activating with an
            # empty table would leave every consumer waiting on a transform that
            # is never going to arrive, which reports as nothing at all.
            self.get_logger().error(f"cannot configure: {exc}")
            return TransitionCallbackReturn.FAILURE

        if not self._transforms:
            self.get_logger().error(f"the generated frame table for zone {zone!r} is empty")
            return TransitionCallbackReturn.FAILURE

        self.get_logger().info(f"configured with {len(self._transforms)} static transform(s)")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._broadcaster = StaticTransformBroadcaster(self)
        stamp = self.get_clock().now().to_msg()
        messages = []
        for transform in self._transforms:
            message = TransformStamped()
            message.header.stamp = stamp
            message.header.frame_id = transform.parent
            message.child_frame_id = transform.child
            message.transform.translation.x = transform.xyz_m[0]
            message.transform.translation.y = transform.xyz_m[1]
            message.transform.translation.z = transform.xyz_m[2]
            message.transform.rotation = quaternion_from_rpy(*transform.rpy_rad)
            messages.append(message)
        self._broadcaster.sendTransform(messages)
        self.get_logger().info(f"published {len(messages)} static transform(s)")
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        # A static broadcaster is transient-local: what it published stays
        # available to late joiners. Dropping it here is the closest thing to
        # ceasing to publish, and it leaves nothing half-populated.
        self._broadcaster = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._transforms = []
        self._broadcaster = None
        return TransitionCallbackReturn.SUCCESS


def main() -> None:
    rclpy.init()
    node = FrameServer()
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
