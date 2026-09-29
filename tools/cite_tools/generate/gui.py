"""Generate the Gazebo GUI configuration: where a windowed run's camera starts.

Presentation only. It is read by `gz sim --gui-config` when the simulator opens a
window and by nothing else, so a headless run — every scenario, every CI step —
never sees it. The file mirrors Harmonic's own default GUI plugin set, so passing
it removes nothing the window had before; the one value it changes is the
MinimalScene camera pose, derived here from where L0 puts the zone's assets.

The camera stands on the CUSTOMER side of the line: across it from the arms,
facing them. The line runs along world X in every zone L0 declares today, so the
customer side is whichever Y side of the robots the rest of the cell sits on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import environment

#: How far the camera looks down, from horizontal. A framing choice.
ELEVATION_RAD = math.radians(33.0)

#: The MinimalScene camera's horizontal field of view: gz-gui's MinimalScene
#: default (pi/2), which the config below does not override. Measured, not
#: assumed: framed for 60 degrees, the cell filled well under half the view.
HORIZONTAL_FOV_RAD = math.radians(90.0)

#: Added to each end of the zone's X extent. Asset positions are origins, and a
#: table or a belt reaches past its origin (the widest here by 0.3 m), so the
#: frame needs room beyond them, and their near faces sit closer to the camera
#: than their origins. Checked by eye: 1.0 m left the cell small, 0.4 m clipped
#: the tables.
MARGIN_M = 0.7


@dataclass(frozen=True)
class CameraPose:
    """x y z roll pitch yaw, in the world, as MinimalScene reads `<camera_pose>`.

    Gazebo's camera looks along its own +X, and a positive pitch tilts that axis
    down (Harmonic's default is `-6 0 6 0 0.5 0`: behind the origin, looking down
    at it).
    """

    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float


def gui_camera_pose(cell: ResolvedCell) -> CameraPose:
    """Frame the whole zone from the customer side of the line."""
    robot_assets = cell.of_category("robot")
    robots = [a.world_pose.xyz_m for a in robot_assets]
    others = [a.world_pose.xyz_m for a in cell.assets if a not in robot_assets]
    everything = [a.world_pose.xyz_m for a in cell.assets]

    xs = [p[0] for p in everything]
    ys = [p[1] for p in everything]
    target_x = (min(xs) + max(xs)) / 2.0
    target_y = (min(ys) + max(ys)) / 2.0
    # The arms are mounted on the work surface, so their mount height is the
    # height the eye should rest at.
    target_z = sum(p[2] for p in robots) / len(robots)

    # +1: the rest of the cell is on +Y of the arms, so the customer is on +Y.
    side = 1.0
    if others and robots:
        mean_other_y = sum(p[1] for p in others) / len(others)
        mean_robot_y = sum(p[1] for p in robots) / len(robots)
        side = 1.0 if mean_other_y >= mean_robot_y else -1.0

    width = max(xs) - min(xs) + 2.0 * MARGIN_M
    distance = (width / 2.0) / math.tan(HORIZONTAL_FOV_RAD / 2.0)

    return CameraPose(
        x=target_x,
        y=target_y + side * distance * math.cos(ELEVATION_RAD),
        z=target_z + distance * math.sin(ELEVATION_RAD),
        roll=0.0,
        pitch=ELEVATION_RAD,
        # Looking back across the line, toward the arms.
        yaw=-side * math.pi / 2.0,
    )


def generate(cell: ResolvedCell) -> list[Artifact]:
    text = environment().get_template("world/gui.config.j2").render(camera=gui_camera_pose(cell))
    return [Artifact(f"worlds/{cell.zone}_gui.config", text)]
