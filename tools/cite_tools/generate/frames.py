"""Generate the static TF table for everything that is not a URDF link.

`robot_state_publisher` publishes the transforms inside the description. This
covers the other half: zone origins and the named frames a station reaches for.

One publisher per transform, which is why these are emitted as a table for a
single node rather than as a set of `static_transform_publisher` invocations —
two publishers for one transform makes TF alternate between them, and the
resulting behaviour is intermittent and extremely hard to attribute.
"""

from __future__ import annotations

import yaml

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import hash_banner


def generate(cell: ResolvedCell) -> list[Artifact]:
    transforms: list[dict[str, object]] = []
    for asset in cell.assets:
        # An arm is spawned as its own model whose root link is its mount, so
        # nothing else ties that root to the facility. Without this transform TF
        # has two disconnected trees, and a skill given a pose in cite_world can
        # never resolve it into the arm's planning frame — which surfaces as an
        # extrapolation or lookup error naming the frames but not the cause.
        if asset.asset_type.category == "robot":
            transforms.append(
                {
                    "parent": ids.WORLD_FRAME,
                    "child": ids.link(asset.id, "mount"),
                    "xyz_m": [round(v, 9) for v in asset.world_pose.xyz_m],
                    "rpy_rad": [round(v, 9) for v in asset.world_pose.rpy_rad],
                }
            )
        # A frame that names a `link` is NOT emitted here. It belongs to a link
        # in a robot description, so `robot_state_publisher` already publishes
        # it, at wherever forward kinematics puts it. Emitting it as well made
        # `cell_a__arm_1__tcp` a STATIC transform sitting at the arm's mount —
        # byte-identical to `cell_a__arm_1__base`, and 0.836 m from where the
        # tool centre point actually is at the model's own home configuration.
        # Under the naming rule that is *the* canonical name for the arm's TCP,
        # so a consumer resolving it got a constant, confidently wrong answer
        # with nothing reporting anything. `NamedFrame.link` exists to record
        # exactly this distinction; this is the code that reads it.
        published_by_state_publisher = {f.id for f in asset.asset_type.frames if f.link is not None}
        for frame_id, pose in sorted(asset.frames.items()):
            if frame_id in published_by_state_publisher:
                continue
            transforms.append(
                {
                    "parent": ids.WORLD_FRAME,
                    "child": ids.frame(cell.zone, asset.id, frame_id),
                    "xyz_m": [round(v, 9) for v in pose.xyz_m],
                    "rpy_rad": [round(v, 9) for v in pose.rpy_rad],
                }
            )

    transforms.sort(key=lambda t: str(t["child"]))
    body = yaml.safe_dump(
        {"static_transforms": transforms}, sort_keys=False, default_flow_style=False
    )
    header = (
        "---\n"
        f"{hash_banner()}\n"
        "#\n"
        "# Frames for assets that are not links in the robot description.\n"
    )
    return [Artifact(f"frames/{cell.zone}_static_tf.yaml", header + body)]
