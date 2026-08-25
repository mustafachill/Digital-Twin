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
        for frame_id, pose in sorted(asset.frames.items()):
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
