"""Generate the Gazebo GUI configuration: where a windowed run's camera starts.

Presentation only. It is read by `gz sim --gui-config` when the simulator opens a
window and by nothing else, so a headless run — every scenario, every CI step —
never sees it. The file mirrors Harmonic's own default GUI plugin set, so passing
it removes nothing the window had before; the one value it changes is the
MinimalScene camera pose, derived here from where L0 puts the zone's assets.

ONE FILE PER SIDE, and only the plant's carries the operator console's panel
(ADR-0071 decision 5): `cite_console_gui`'s `CellConsole` plugin, given every name
the console serves as a plugin parameter, from `bringup.console_names` — the same
function the plan's `console:` block is emitted from, so the panel and the server
cannot be handed two spellings of one name. The panel is on the plant because the
console serves on the plant's domain, and that is the domain the plant's window
runs on. A counterpart's window — an all-simulated pair opens one per side — gets
the same file without the panel, so that one pair never shows two.

The panel is also handed the 3D view's starting pose, as `<home_camera_pose>`, so
that its "Reset view" can return the camera there (ADR-0071). It is the pose
`gui_camera_pose` derives, rendered once by the template into the one text both
MinimalScene's `<camera_pose>` and the panel's parameter carry.

Beside it, three more views the operator can pick - Top, Side and Front - each
derived here from the same extent of the zone's assets (`camera_presets`), the
model the panel's "Follow robot" asks the window to follow (`follow_model`), the
sides of the pair (`twin_sides`), and how long the panel lets the twin
boundary's heartbeat go unheard before it shows the boundary as stale
(`heartbeat_stale_after_s`). Each is a value the panel would otherwise have to
write as a literal (P1); none of them commands a robot.

The twin-mode, twin-sides and heartbeat topics the panel also reads are not
parameters: they are `TOPIC` constants in the contract, which the plugin reads
from the generated message headers rather than from a second statement here.

The camera stands on the CUSTOMER side of the line: across it from the arms,
facing them. The line runs along world X in every zone L0 declares today, so the
customer side is whichever Y side of the robots the rest of the cell sits on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cite_tools.generate import Artifact, gui_config_path
from cite_tools.generate.bringup import console_names
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import environment
from cite_tools.validate.referential import MINIMUM_HEARTBEATS_PER_DEADMAN_TIMEOUT

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


#: How far the Side and Front presets look down, from horizontal: low enough to
#: read heights against each other, high enough to see over the belt. A framing
#: choice, like `ELEVATION_RAD`.
LOW_ELEVATION_RAD = math.radians(15.0)

#: How far the Top preset looks down. Not a full right angle: straight down is
#: the gimbal pole of the window's orbit control, from which a drag spins the
#: view instead of tilting it. A framing choice.
TOP_ELEVATION_RAD = math.radians(89.0)


@dataclass(frozen=True)
class _Framing:
    """What every preset frames: the centre of the zone's assets and their extent."""

    target: tuple[float, float, float]
    span_x_m: float
    span_y_m: float
    #: +1 when the customer side of the line is +Y of the arms, -1 otherwise.
    customer_side: float


def _framing(cell: ResolvedCell) -> _Framing:
    """The centre, extent and customer side `gui_camera_pose` frames, as data."""
    robot_assets = cell.of_category("robot")
    robots = [a.world_pose.xyz_m for a in robot_assets]
    others = [a.world_pose.xyz_m for a in cell.assets if a not in robot_assets]
    everything = [a.world_pose.xyz_m for a in cell.assets]
    xs = [p[0] for p in everything]
    ys = [p[1] for p in everything]
    side = 1.0
    if others and robots:
        mean_other_y = sum(p[1] for p in others) / len(others)
        mean_robot_y = sum(p[1] for p in robots) / len(robots)
        side = 1.0 if mean_other_y >= mean_robot_y else -1.0
    return _Framing(
        target=(
            (min(xs) + max(xs)) / 2.0,
            (min(ys) + max(ys)) / 2.0,
            sum(p[2] for p in robots) / len(robots),
        ),
        span_x_m=max(xs) - min(xs) + 2.0 * MARGIN_M,
        span_y_m=max(ys) - min(ys) + 2.0 * MARGIN_M,
        customer_side=side,
    )


def _looking_at(
    framing: _Framing, across_m: float, along_m: float, yaw: float, pitch: float
) -> CameraPose:
    """A camera aimed at the framing's target, seeing `across_m` across its view.

    Gazebo's camera looks along its own +X: yawed by `yaw` and tilted down by
    `pitch`, it looks along (cos p cos y, cos p sin y, -sin p), so it stands
    `distance` back from the target along that direction. It also stands outside
    the `along_m` the zone extends in the direction it looks, so that no asset
    is behind it: far enough that its horizontal offset clears half of it.
    """
    distance = (across_m / 2.0) / math.tan(HORIZONTAL_FOV_RAD / 2.0)
    if along_m > 0.0:
        distance = max(distance, (along_m / 2.0) / math.cos(pitch))
    x, y, z = framing.target
    return CameraPose(
        x=x - distance * math.cos(pitch) * math.cos(yaw),
        y=y - distance * math.cos(pitch) * math.sin(yaw),
        z=z + distance * math.sin(pitch),
        roll=0.0,
        pitch=pitch,
        yaw=yaw,
    )


def camera_presets(cell: ResolvedCell) -> tuple[tuple[str, CameraPose], ...]:
    """The panel's preset views, by the key the plugin reads each under (ADR-0071).

    - **Top**: above the zone, looking (nearly) straight down, the line running
      across the view as in the starting view, framing the larger extent.
    - **Side**: from the +X end of the line, looking along it, framing its depth.
    - **Front**: from the customer side, as the starting view, but low.

    Each frames the extent `gui_camera_pose` frames, so a cell L0 lays out
    differently is framed again with no value changed here.
    """
    framing = _framing(cell)
    # Looking back across the line, toward the arms, as the starting view does.
    across = -framing.customer_side * math.pi / 2.0
    span_x, span_y = framing.span_x_m, framing.span_y_m
    return (
        # Looking down, nothing extends along the view but height.
        (
            "top_camera_pose",
            _looking_at(framing, max(span_x, span_y), 0.0, across, TOP_ELEVATION_RAD),
        ),
        ("side_camera_pose", _looking_at(framing, span_y, span_x, math.pi, LOW_ELEVATION_RAD)),
        ("front_camera_pose", _looking_at(framing, span_x, span_y, across, LOW_ELEVATION_RAD)),
    )


def follow_model(cell: ResolvedCell) -> str:
    """The model the panel's "Follow robot" asks the window to follow.

    The zone's first robot as L0 declares it: its asset id, which is the name it
    is spawned under in the plant's world (`simulation.launch.py` spawns each
    arm with ``-name`` set to its plan manager's asset, which is this id).
    """
    (first, *_) = cell.of_category("robot")
    return first.id


def heartbeat_stale_after_s(cell: ResolvedCell) -> float:
    """How long the panel lets the boundary's heartbeat go unheard (ADR-0070 item 5).

    Where the zone declares a physical side, its deadman's timeout: the panel
    shows the boundary as stale exactly when a physical deadman would trip.
    Where it declares none, the shortest timeout the validator accepts for one
    (`deadman-timeout-below-three-heartbeats`). A display threshold only:
    nothing waits for it and it gates nothing.
    """
    twin = cell.twin
    assert twin is not None and twin.heartbeat_period_s is not None, "only a pair has a panel"
    if twin.physical_side is not None:
        return twin.physical_side.deadman_timeout_s
    return MINIMUM_HEARTBEATS_PER_DEADMAN_TIMEOUT * twin.heartbeat_period_s


def panel_names(cell: ResolvedCell, side: str) -> tuple[tuple[str, str], ...]:
    """The console names ``side``'s window gives its panel; empty for no panel.

    The generator's decision, made here once, so that the template only asks
    whether there is anything to emit: the plant of a paired zone, and no other
    window.
    """
    if cell.is_paired and side == ids.PLANT_SIDE:
        return console_names(cell)
    return ()


def panel_parameters(cell: ResolvedCell) -> dict[str, object]:
    """Everything the panel is handed besides the console's names and its home view."""
    return {
        "presets": camera_presets(cell),
        "follow_model": follow_model(cell),
        "twin_sides": " ".join(side.name for side in cell.sides),
        "heartbeat_stale_after_s": heartbeat_stale_after_s(cell),
    }


def panel_parameter_keys(cell: ResolvedCell) -> tuple[str, ...]:
    """The panel's element names `panel_parameters` fills, presets first."""
    parameters = panel_parameters(cell)
    presets = tuple(key for key, _ in camera_presets(cell))
    return presets + tuple(key for key in parameters if key != "presets")


def generate(cell: ResolvedCell) -> list[Artifact]:
    template = environment().get_template("world/gui.config.j2")
    camera = gui_camera_pose(cell)
    artifacts = []
    for side in cell.sides:
        console = panel_names(cell, side.name)
        artifacts.append(
            Artifact(
                gui_config_path(cell.zone, side.name),
                template.render(
                    camera=camera,
                    console=console,
                    panel=panel_parameters(cell) if console else None,
                ),
            )
        )
    return artifacts
