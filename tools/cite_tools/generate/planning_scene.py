"""Generate the planning-scene collision objects from L0.

Each arm's planning scene contains that arm and nothing else. Every pick and
place point in this cell lies exactly on a surface, so a planner that cannot see
the surface treats a path straight through it as the normal case — and the
failure is a trajectory that executes, collides, and is blamed on the controller.

The bodies here are the *same* resolved bodies `generate.description` emits into
the scene URDF, taken through the same `_body_view`, so the planner's idea of the
cell and the simulator's cannot drift apart. That sharing is the point of the
module; recomputing the geometry here would be the second place a value lives.

Two deliberate omissions, stated rather than left to be discovered:

* **Neighbouring arms are not here.** An articulated robot is not a static
  collision object, and freezing one at a pose would be worse than omitting it —
  it would be confidently wrong wherever the other arm actually is. Coordinating
  arms against each other is L4's problem and needs the live scene, not this.
* **Nothing reads this file yet.** The node that publishes these objects onto
  `/monitored_planning_scene` belongs in `cite_facility` or `cite_bringup`, and
  neither exists (CLAUDE.md §2). Until it does, this artifact is generated and
  unread: the geometry is available and correct, and the planner still cannot
  see it.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import environment


class UnsupportedCollisionShapeError(Exception):
    """A body's collision geometry cannot be expressed as a MoveIt primitive."""


@dataclass(frozen=True)
class _ObjectView:
    id: str
    type_id: str
    kind: str
    #: Box extents, empty for other primitives.
    size_m: tuple[float, ...]
    radius_m: float | None
    length_m: float | None
    #: Pose of the primitive's CENTRE, which is what MoveIt's `primitive_poses`
    #: means — not the body's pose, which names the point it stands on.
    centre_xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]


def _objects(cell: ResolvedCell) -> tuple[_ObjectView, ...]:
    from cite_tools.generate.description import body_views

    views = []
    for view in body_views(cell):
        geometry = view.body.collision
        pose = view.world_pose
        views.append(
            _ObjectView(
                id=view.id,
                type_id=view.asset_type.id,
                kind=geometry.kind,
                size_m=tuple(geometry.size_m) if geometry.kind == "box" else (),
                radius_m=geometry.radius_m if geometry.kind == "cylinder" else None,
                length_m=geometry.length_m if geometry.kind == "cylinder" else None,
                centre_xyz_m=(
                    pose.xyz_m[0],
                    pose.xyz_m[1],
                    pose.xyz_m[2] + view.half_height,
                ),
                rpy_rad=pose.rpy_rad,
            )
        )
    return tuple(views)


def generate(cell: ResolvedCell) -> list[Artifact]:
    objects = _objects(cell)
    # A mesh collision body would need its extents read out of a file this layer
    # deliberately does not open (L1 owns geometry), so it is refused loudly
    # rather than emitted as a box of guessed size.
    unsupported = [o.id for o in objects if o.kind not in ("box", "cylinder")]
    if unsupported:
        raise UnsupportedCollisionShapeError(
            f"{', '.join(sorted(unsupported))} use collision geometry this generator "
            "cannot express as a MoveIt solid primitive. Give them a box or a cylinder, "
            "or extend this generator to emit a mesh resource."
        )

    text = (
        environment()
        .get_template("moveit/planning_scene.yaml.j2")
        .render(cell=cell, world_frame=ids.WORLD_FRAME, objects=objects)
    )
    return [Artifact(f"moveit/{cell.zone}_planning_scene.yaml", text)]
