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

import signal

from cite_facility import planning_scene_loader
from cite_facility.artifacts import CollisionBody, planning_scene
from cite_facility.planning_scene_loader import _collision_object
from moveit_msgs.msg import CollisionObject
import pytest
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.subscription import RCLError
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


# ---------------------------------------------------------------------------
# `main`'s exception policy.
#
# rclpy's DEFAULT context cannot be initialised twice in one process, so the
# context is owned by the fixture below and `runtime.init`/`runtime.shutdown` are
# stood down for the duration. That is not a gap: what these two tests are about
# is which exceptions `main` tolerates and what it says about them, and the
# lifecycle calls themselves are tested in `cite_runtime`.
# ---------------------------------------------------------------------------


@pytest.fixture(name="context")
def _context(monkeypatch):
    """One rclpy context for the test, with `main`'s own lifecycle calls stood down."""
    previous = signal.getsignal(signal.SIGINT)
    rclpy.init()
    monkeypatch.setattr(planning_scene_loader.runtime, "init", lambda args=None: None)
    monkeypatch.setattr(
        planning_scene_loader.runtime, "shutdown", lambda node: node.destroy_node()
    )
    try:
        yield
    finally:
        if rclpy.ok():
            rclpy.shutdown()
        signal.signal(signal.SIGINT, previous)


def test_an_rcl_fault_with_a_live_context_is_not_a_bare_exit_1(context, monkeypatch) -> None:
    """`main` mirrors `runtime.spin`: only a dead context makes an RCLError benign.

    This clause used to be `except (..., RCLError)` with no condition, so an rcl
    fault while the context was still valid became `sys.exit(1)` with nothing
    logged — bring-up reported "exited 1" and named no cause, while every other
    failure path in this node carries a specific diagnosis.
    """
    monkeypatch.setattr(
        planning_scene_loader.PlanningSceneLoader,
        "load",
        _raise(RCLError("an rcl fault that is not a shutdown")),
    )
    with pytest.raises(RCLError):
        planning_scene_loader.main()


def test_an_interrupted_load_still_exits_1_and_says_why(context, monkeypatch) -> None:
    """The policy stays the loader's own: interrupted is not applied.

    The set and the narrowing come from `cite_runtime`; what this node does with
    them does not. An interruption is still a failure here, because bring-up
    gates the skill servers on this exit code and the scene was never proven to
    have arrived — but it now says so rather than exiting silently.
    """
    logged: list[str] = []
    monkeypatch.setattr(
        planning_scene_loader.PlanningSceneLoader,
        "load",
        _raise(ExternalShutdownException()),
    )
    monkeypatch.setattr(
        planning_scene_loader.PlanningSceneLoader,
        "get_logger",
        lambda self: _Recorder(logged),
    )
    with pytest.raises(SystemExit) as exit_info:
        planning_scene_loader.main()
    assert exit_info.value.code == 1
    assert logged and "ExternalShutdownException" in logged[0]


class _Recorder:
    """The one method `main` calls on a logger."""

    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def error(self, message: str) -> None:
        self._sink.append(message)


def _raise(error):
    def _load(*args, **kwargs):
        raise error

    return _load
