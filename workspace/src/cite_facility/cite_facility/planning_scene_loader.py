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

"""Put the cell's furniture into one arm's planning scene, then exit.

Until this node existed, every plan in this system was computed against an empty
world: not one `CollisionObject` or `PlanningScene` was constructed anywhere in
the repository, so an arm's planning scene contained that arm and nothing else.
That is not a corner case here — every pick and place point in the cell lies
exactly on a surface, so a plan that dives through the surface is the normal
result, and it surfaces as a controller fault rather than as a missing obstacle.

The shape of this node is deliberate. It is a **one-shot process**, like
`ros_gz_sim create` and `controller_manager spawner`: it does one thing, proves
it happened, and exits. Its exit is therefore a real completion event that
bring-up can gate the skill servers on, which is exactly what P4 asks for and
what a long-lived publisher could not offer — nothing can tell when a publisher
has been *received*.

It runs in an arm's namespace and calls the relative service names
`apply_planning_scene` and `get_planning_scene`, so it reaches that arm's
move_group without composing a name from a namespace and an interface (P1).

Applying is not trusted: after the service reports success the scene is read back
and the object names compared. `ApplyPlanningScene` returns success when
move_group has accepted the diff, which is not the same as the objects being in
the world — an object in a frame TF cannot resolve is accepted and then dropped,
and the difference between those two outcomes is a robot planning through a
table.
"""

from __future__ import annotations

import sys

from cite_facility.artifacts import ArtifactError, CollisionBody, planning_scene
from cite_facility.transforms import quaternion_from_rpy
from geometry_msgs.msg import Pose
from moveit_msgs.msg import CollisionObject, PlanningScene, PlanningSceneComponents
from moveit_msgs.srv import ApplyPlanningScene, GetPlanningScene
import rclpy
from rclpy.node import Node
from shape_msgs.msg import SolidPrimitive

#: Deadline, not a schedule. move_group starts alongside the simulator and is
#: usually answering long before this node runs; the value exists so that a
#: move_group which never appears is reported rather than waited on forever.
#: Nothing about correct behaviour depends on it.
SERVICE_DEADLINE_S = 120.0

#: The L0 primitive names, mapped onto `shape_msgs/SolidPrimitive`. A primitive
#: the model grows that is not listed here stops bring-up naming it, rather than
#: being silently dropped out of the scene an arm plans against.
PRIMITIVES = {
    "box": (SolidPrimitive.BOX, 3),
    "cylinder": (SolidPrimitive.CYLINDER, 2),
    "sphere": (SolidPrimitive.SPHERE, 1),
}


class PlanningSceneLoader(Node):
    def __init__(self) -> None:
        super().__init__("planning_scene_loader")
        self.declare_parameter("zone", "cell_a")

    def load(self) -> int:
        """Apply the generated scene and verify it arrived. 0 on success."""
        zone = self.get_parameter("zone").get_parameter_value().string_value
        try:
            frame_id, bodies = planning_scene(zone)
            objects = [_collision_object(body) for body in bodies]
        except (ArtifactError, ValueError) as exc:
            self.get_logger().error(f"cannot load the planning scene: {exc}")
            return 1

        scene = PlanningScene()
        # A diff, not a replacement: move_group's scene already holds the robot's
        # own state and its allowed-collision matrix, and replacing it wholesale
        # would discard both.
        scene.is_diff = True
        scene.world.collision_objects = objects

        apply_client = self.create_client(ApplyPlanningScene, "apply_planning_scene")
        if not apply_client.wait_for_service(timeout_sec=SERVICE_DEADLINE_S):
            self.get_logger().error(
                f"no move_group answered {apply_client.srv_name!r} within "
                f"{SERVICE_DEADLINE_S:.0f}s. The planning scene cannot be loaded, so "
                "every plan for this arm would be computed against an empty world."
            )
            return 1

        future = apply_client.call_async(ApplyPlanningScene.Request(scene=scene))
        rclpy.spin_until_future_complete(self, future, timeout_sec=SERVICE_DEADLINE_S)
        response = future.result()
        if response is None:
            self.get_logger().error(
                f"{apply_client.srv_name!r} never returned a result"
            )
            return 1
        if not response.success:
            self.get_logger().error(
                f"move_group refused the planning scene diff for zone {zone!r}"
            )
            return 1

        missing = self._not_in_the_scene({obj.id for obj in objects})
        if missing is None:
            return 1
        if missing:
            self.get_logger().error(
                f"move_group accepted the diff but {sorted(missing)} are not in "
                f"its world. An object whose frame ({frame_id}) TF cannot resolve "
                "is accepted and then dropped, which leaves the arm planning "
                "through it."
            )
            return 1

        self.get_logger().info(
            f"loaded {len(objects)} collision object(s) for zone {zone!r} in {frame_id}"
        )
        return 0

    def _not_in_the_scene(self, expected: set[str]) -> set[str] | None:
        """Which of `expected` move_group does not actually hold. None on error."""
        client = self.create_client(GetPlanningScene, "get_planning_scene")
        if not client.wait_for_service(timeout_sec=SERVICE_DEADLINE_S):
            self.get_logger().error(
                f"no move_group answered {client.srv_name!r}, so the scene that was "
                "just applied cannot be verified"
            )
            return None
        request = GetPlanningScene.Request()
        request.components.components = PlanningSceneComponents.WORLD_OBJECT_NAMES
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=SERVICE_DEADLINE_S)
        response = future.result()
        if response is None:
            self.get_logger().error(f"{client.srv_name!r} never returned a result")
            return None
        present = {obj.id for obj in response.scene.world.collision_objects}
        return expected - present


def _collision_object(body: CollisionBody) -> CollisionObject:
    try:
        shape, arity = PRIMITIVES[body.primitive]
    except KeyError as exc:
        raise ValueError(
            f"collision object {body.object_id!r} is a {body.primitive!r}, which is not "
            f"one of {', '.join(sorted(PRIMITIVES))}"
        ) from exc
    if len(body.dimensions_m) != arity:
        raise ValueError(
            f"collision object {body.object_id!r} is a {body.primitive!r} with "
            f"{len(body.dimensions_m)} dimension(s); {arity} are required"
        )

    primitive = SolidPrimitive()
    primitive.type = shape
    primitive.dimensions = list(body.dimensions_m)

    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = body.xyz_m
    pose.orientation = quaternion_from_rpy(*body.rpy_rad)

    obj = CollisionObject()
    obj.id = body.object_id
    obj.header.frame_id = body.frame_id
    obj.primitives = [primitive]
    obj.primitive_poses = [pose]
    obj.operation = CollisionObject.ADD
    return obj


def main() -> None:
    rclpy.init()
    node = PlanningSceneLoader()
    try:
        code = node.load()
    except KeyboardInterrupt:
        code = 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    sys.exit(code)


if __name__ == "__main__":
    main()
