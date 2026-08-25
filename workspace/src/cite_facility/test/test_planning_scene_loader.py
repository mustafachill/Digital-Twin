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

"""Building MoveIt collision objects from the generated planning scene.

The translation is unit-testable and the service call is not, so this covers the
half that decides whether an arm plans around the cell or through it: the shape
type, the number of dimensions, the pose convention, and the frame.

`pose` in the generated artifact is the pose of the primitive's CENTRE, which is
what MoveIt's `primitive_poses` means. An L0 body's pose names the point it
stands on, so the two differ by half a height; the generator applies that
difference, and these tests assert the result rather than reapplying it.
"""

from __future__ import annotations

from cite_facility.artifacts import CollisionBody, planning_scene
from cite_facility.planning_scene_loader import _collision_object
from moveit_msgs.msg import CollisionObject
import pytest
from shape_msgs.msg import SolidPrimitive


def test_every_generated_body_becomes_a_collision_object() -> None:
    frame_id, bodies = planning_scene("cell_a")
    objects = [_collision_object(body) for body in bodies]
    assert len(objects) == len(bodies)
    for obj in objects:
        assert obj.operation == CollisionObject.ADD
        assert obj.header.frame_id == frame_id
        assert len(obj.primitives) == 1 and len(obj.primitive_poses) == 1
        assert obj.primitives[0].type == SolidPrimitive.BOX
        assert len(obj.primitives[0].dimensions) == 3


def test_a_box_keeps_its_size_and_its_centre() -> None:
    body = CollisionBody(
        object_id="table_pick",
        frame_id="cite_world",
        primitive="box",
        dimensions_m=(0.6, 0.6, 0.6),
        xyz_m=(-0.475, 0.0, 0.3),
        rpy_rad=(0.0, 0.0, 0.0),
    )
    obj = _collision_object(body)
    assert list(obj.primitives[0].dimensions) == [0.6, 0.6, 0.6]
    position = obj.primitive_poses[0].position
    assert (position.x, position.y, position.z) == (-0.475, 0.0, 0.3)
    assert obj.primitive_poses[0].orientation.w == pytest.approx(1.0)


def test_a_rotation_becomes_a_quaternion() -> None:
    """Rotations survive the trip into MoveIt.

    The model is roll-pitch-yaw because a person reads it; TF and MoveIt are
    quaternions because nothing does.
    """
    import math

    body = CollisionBody(
        object_id="turned",
        frame_id="cite_world",
        primitive="box",
        dimensions_m=(1.0, 1.0, 1.0),
        xyz_m=(0.0, 0.0, 0.0),
        rpy_rad=(0.0, 0.0, math.pi / 2.0),
    )
    orientation = _collision_object(body).primitive_poses[0].orientation
    assert orientation.z == pytest.approx(math.sqrt(0.5))
    assert orientation.w == pytest.approx(math.sqrt(0.5))


def test_an_unknown_primitive_stops_rather_than_dropping_the_obstacle() -> None:
    """Silently skipping it would leave the arm planning through whatever it is."""
    body = CollisionBody(
        object_id="mystery",
        frame_id="cite_world",
        primitive="mesh",
        dimensions_m=(1.0,),
        xyz_m=(0.0, 0.0, 0.0),
        rpy_rad=(0.0, 0.0, 0.0),
    )
    with pytest.raises(ValueError, match="mesh"):
        _collision_object(body)


def test_a_box_with_the_wrong_number_of_dimensions_is_refused() -> None:
    """A two-dimension box is accepted by SolidPrimitive and is not a box.

    MoveIt reads dimensions positionally, so the missing one becomes zero and the
    obstacle becomes a plane the planner happily passes through.
    """
    body = CollisionBody(
        object_id="flat",
        frame_id="cite_world",
        primitive="box",
        dimensions_m=(1.0, 1.0),
        xyz_m=(0.0, 0.0, 0.0),
        rpy_rad=(0.0, 0.0, 0.0),
    )
    with pytest.raises(ValueError, match="3 are required"):
        _collision_object(body)
