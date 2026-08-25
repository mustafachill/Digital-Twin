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

"""Locate and read the generated artifacts.

The boundary this module marks is worth stating plainly, because it is easy to
erode: **nothing here opens anything under `model/`.** L0 says a running system
never reads the model; it reads what was generated from it. Keeping that true is
what lets the model be validated on a laptop with no ROS, and lets the robot run
with no model present at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
import yaml

GENERATED_PACKAGE = "cite_generated"


class ArtifactError(Exception):
    """A generated artifact is missing or unreadable."""


def generated_dir() -> Path:
    try:
        return Path(get_package_share_directory(GENERATED_PACKAGE))
    except Exception as exc:  # noqa: BLE001 - ament raises its own type
        raise ArtifactError(
            f"{GENERATED_PACKAGE} is not on the ament index. It is generated from the "
            "L0 model — run ./scripts/validate-model --write, then ./scripts/build."
        ) from exc


def read_yaml(relative: str) -> dict:
    path = generated_dir() / relative
    if not path.is_file():
        raise ArtifactError(
            f"no generated artifact at {path}. Every artifact here comes from the L0 "
            "model — run ./scripts/validate-model --write, then ./scripts/build. If it "
            "is still missing afterwards, no generator emits it."
        )
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict):
        raise ArtifactError(f"{path}: expected a mapping at the top level")
    return document


def model_hash() -> str:
    """Read the hash of the model these artifacts were generated from.

    Stamped into every recording (L6): a bag recorded against yesterday's layout
    is not comparable to today's, and without this the two are indistinguishable
    after the fact.
    """
    path = generated_dir() / "MODEL_HASH"
    if not path.is_file():
        raise ArtifactError(
            f"no MODEL_HASH at {path}. Run ./scripts/validate-model --write, then "
            "./scripts/build."
        )
    return path.read_text().strip()


@dataclass(frozen=True)
class StaticTransform:
    parent: str
    child: str
    xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]


def static_transforms(zone: str) -> list[StaticTransform]:
    document = read_yaml(f"frames/{zone}_static_tf.yaml")
    entries = document.get("static_transforms") or []
    transforms = [
        StaticTransform(
            parent=entry["parent"],
            child=entry["child"],
            xyz_m=tuple(float(v) for v in entry["xyz_m"]),
            rpy_rad=tuple(float(v) for v in entry["rpy_rad"]),
        )
        for entry in entries
    ]

    # One publisher per transform is a hard rule: two publishers for one transform
    # make TF alternate between them, and the resulting behaviour is intermittent
    # and very hard to attribute. A duplicate here would mean this node is the
    # source of that on its own.
    children = [t.child for t in transforms]
    duplicates = sorted({c for c in children if children.count(c) > 1})
    if duplicates:
        raise ArtifactError(
            f"the generated frame table declares more than one transform for "
            f"{', '.join(duplicates)}. TF would alternate between them."
        )
    return transforms


def topology(zone: str) -> dict:
    document = read_yaml(f"topology/{zone}_flow.yaml")
    if "topology" not in document:
        raise ArtifactError(
            f"the generated topology for zone {zone!r} has no `topology:` mapping"
        )
    return document["topology"]


@dataclass(frozen=True)
class CollisionBody:
    """One piece of the cell's furniture, as MoveIt understands obstacles.

    ``xyz_m`` is the pose of the primitive's CENTRE, which is what MoveIt's
    `primitive_poses` means — the generator has already applied the half-height
    offset from an L0 body's pose, which names the point the body stands on.
    """

    # `object_id` rather than `id`: a class attribute named `id` shadows the
    # builtin, which flake8-builtins flags and which reads badly at every call
    # site. It is MoveIt's `CollisionObject.id` on the wire either way.
    object_id: str
    frame_id: str
    primitive: str
    dimensions_m: tuple[float, ...]
    xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]


def planning_scene(zone: str) -> tuple[str, list[CollisionBody]]:
    """Read the zone's collision objects, and the frame they are expressed in.

    Read from the same generated artifact the scene description is built from, so
    what an arm plans around and what the simulator renders cannot diverge. Only
    the authored furniture is here: neighbouring arms are deliberately absent,
    because an articulated robot frozen at one pose is confidently wrong wherever
    it actually is, and coordinating arms needs the live scene (L4).
    """
    document = read_yaml(f"moveit/{zone}_planning_scene.yaml")
    if "planning_scene" not in document:
        raise ArtifactError(
            f"the generated planning scene for zone {zone!r} has no "
            "`planning_scene:` mapping"
        )
    scene = document["planning_scene"]
    frame_id = scene.get("frame_id")
    if not frame_id:
        raise ArtifactError(
            f"the generated planning scene for zone {zone!r} names no frame_id; "
            "a collision object with no frame is placed at the planner's origin"
        )

    bodies: list[CollisionBody] = []
    for entry in scene.get("collision_objects") or []:
        try:
            primitive = entry["primitive"]
            pose = entry["pose"]
            bodies.append(
                CollisionBody(
                    object_id=str(entry["id"]),
                    frame_id=str(entry.get("frame_id") or frame_id),
                    primitive=str(primitive["type"]),
                    dimensions_m=tuple(float(v) for v in primitive["dimensions_m"]),
                    xyz_m=tuple(float(v) for v in pose["xyz_m"]),
                    rpy_rad=tuple(float(v) for v in pose["rpy_rad"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactError(
                f"the generated planning scene for zone {zone!r} has a malformed "
                f"collision object: {exc}"
            ) from exc

    if not bodies:
        raise ArtifactError(
            f"the generated planning scene for zone {zone!r} lists no collision "
            "objects. Every plan in the zone would be computed against an empty "
            "world, and since every pick and place point lies on a surface, a plan "
            "through that surface would be the normal case."
        )
    return str(frame_id), bodies
