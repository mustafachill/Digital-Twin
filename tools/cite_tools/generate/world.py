"""Generate the simulation world from L0.

The world holds what belongs to the *world*: physics settings, lighting, the
ground, the systems every model relies on — and the simulation aids that are
properties of the cell rather than of any one spawned model. The cell itself is
not in here; it is spawned from the generated description, so that the
description is the one place the cell's contents are stated and the simulator and
the planner cannot disagree about what exists.

Why the belts and the beams are declared here rather than in the description, and
it is forced rather than preferred: every authored body in the scene is joined to
the cell root by a fixed joint, and converting URDF to SDF lumps fixed-joint
links into their parent. All twenty-nine links of the scene arrive in the
simulator as one link named ``cite_world``. There is no ``conveyor_1`` model and
no ``beam_c1_out`` model to attach a model plugin to, and a plugin attached to the
scene would see the scene's origin instead of the belt's. Both aids are therefore
world systems, and both receive the pose the generator resolved from the same L0
frame that positions their geometry — so a belt's carry volume and the belt a
station reaches for cannot describe different places.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.render import environment

#: 1 ms. Small enough for stable contact with a parallel gripper, and the value a
#: scenario's determinism depends on — changing it changes results, so it is a
#: generated constant rather than a launch argument someone can vary per run.
STEP_SIZE_S = 0.001

#: Unthrottled. Scenarios are graded on outcomes and wall-clock bounds, not on
#: matching real time, and throttling would only make them slower.
REAL_TIME_FACTOR = 0.0

GROUND_SIZE_M = 40.0

#: How often a simulation aid repeats its current state when nothing has changed.
#:
#: A publication rate, not a schedule. Both aids publish a change IMMEDIATELY, so
#: nothing in the system ever waits for this interval and no behaviour depends on
#: its value (P4). It exists only so that a subscriber which starts late learns
#: the current state without waiting for the next transition. The previous
#: conveyor published every physics step, which at ``STEP_SIZE_S`` is 1 kHz per
#: belt for a value that changes when someone asks it to.
AID_PUBLISH_PERIOD_S = 0.1

#: The frame on a conveyor type that names its working surface. Named here rather
#: than guessed at the template, because a belt without one cannot be driven and
#: that has to be an error with a sentence rather than an empty element.
CONVEYOR_SURFACE_FRAME = "surface"


class WorldError(Exception):
    """The model describes something the world generator cannot express."""


@dataclass(frozen=True)
class _ConveyorView:
    asset: str
    #: "x y z roll pitch yaw" — the working surface, in the world.
    surface_pose: tuple[float, ...]
    length_m: float
    width_m: float
    carry_height_m: float
    direction: str
    installed_speed_mps: float
    command_topic: str
    state_topic: str


@dataclass(frozen=True)
class _BeamView:
    asset: str
    beam_pose: tuple[float, ...]
    beam_axis: str
    beam_length_m: float
    beam_width_m: float
    beam_offset_m: float
    detection_topic: str


#: Which component of a mounting offset lies along each beam axis.
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _beam_offset_m(asset: ResolvedAsset, axis: str) -> float:
    """How far past the housing the middle of the beam lies, along the beam axis.

    A through beam is emitted from its housing and crosses the thing it watches;
    the housing is one END of the segment, not its middle. Reading it as the
    middle is a silent, and very nearly invisible, mis-modelling: ``beam_c1_out``
    stands 0.250 m to the side of a 0.400 m belt and declares a 0.500 m beam, so
    a centred segment spans y in [0.000, 0.500] — half of it in the empty air
    beside the belt, with its near edge exactly on the belt's centreline. The
    sensor could then only be broken by a part that had not drifted by a
    millimetre. Emitted from the housing across the belt, the same 0.500 m spans
    y in [-0.250, +0.250] and covers the belt with 50 mm to spare, which is
    plainly what the number was chosen for.

    Nothing new is declared to get this. The direction is the direction of the
    asset the sensor is mounted on, and how far away it stands is already stated
    once — as the sensor's own pose, relative to that asset's frame. A sensor
    placed directly in ``cite_world``, or standing on the centreline of what it
    watches, has no such offset and its housing IS the middle of its beam.
    """
    if asset.parent_asset is None:
        return 0.0
    index = _AXIS_INDEX.get(axis)
    if index is None:
        return 0.0
    return -asset.instance.pose.xyz_m[index]


def _footprint(asset: ResolvedAsset) -> tuple[float, float]:
    """The belt's length and width, from the collision box the model declares.

    Read from the geometry rather than declared again as a carry extent: the
    volume a belt transports through IS the belt, and stating its size a second
    time is the duplication ADR-0004 exists to make impossible.
    """
    body = asset.asset_type.description.body
    if body is None or body.collision.kind != "box":
        raise WorldError(
            f"conveyor {asset.id!r} has type {asset.asset_type.id!r}, whose collision "
            "geometry is not a box. The belt's carry volume is derived from that box, "
            "so a conveyor type needs one."
        )
    return body.collision.size_m[0], body.collision.size_m[1]


def _pose6(asset_pose) -> tuple[float, ...]:  # noqa: ANN001 - geometry.Pose
    return (*asset_pose.xyz_m, *asset_pose.rpy_rad)


def _conveyors(cell: ResolvedCell) -> tuple[_ConveyorView, ...]:
    views: list[_ConveyorView] = []
    for asset in cell.of_category("conveyor"):
        configuration = asset.instance.configuration
        if configuration is None or configuration.kind != "conveyor":
            continue
        surface = asset.frames.get(CONVEYOR_SURFACE_FRAME)
        if surface is None:
            raise WorldError(
                f"conveyor {asset.id!r} has no {CONVEYOR_SURFACE_FRAME!r} frame. The belt "
                "is driven relative to its working surface, which is the same frame the "
                "stations pick and place against."
            )
        length_m, width_m = _footprint(asset)
        views.append(
            _ConveyorView(
                asset=asset.id,
                surface_pose=_pose6(surface),
                length_m=length_m,
                width_m=width_m,
                carry_height_m=configuration.carry_height_m,
                direction=configuration.direction,
                installed_speed_mps=configuration.installed_speed_mps,
                # The same call the bring-up plan makes, so the name the plugin
                # advertises under and the name the plan declares come from one
                # place and cannot drift (P1).
                command_topic=ids.interface(cell.zone, asset.id, "command"),
                state_topic=ids.interface(cell.zone, asset.id, "state"),
            )
        )
    return tuple(views)


def _beams(cell: ResolvedCell) -> tuple[_BeamView, ...]:
    views: list[_BeamView] = []
    for asset in cell.of_category("sensor"):
        configuration = asset.instance.configuration
        if configuration is None or configuration.kind != "sensor":
            continue
        views.append(
            _BeamView(
                asset=asset.id,
                beam_pose=_pose6(asset.world_pose),
                beam_axis=configuration.beam_axis,
                beam_length_m=configuration.beam_length_m,
                beam_width_m=configuration.beam_width_m,
                beam_offset_m=_beam_offset_m(asset, configuration.beam_axis),
                detection_topic=ids.interface(cell.zone, asset.id, "detection"),
            )
        )
    return tuple(views)


def generate(cell: ResolvedCell) -> list[Artifact]:
    text = (
        environment()
        .get_template("world/cell.sdf.j2")
        .render(
            cell=cell,
            step_size=STEP_SIZE_S,
            real_time_factor=REAL_TIME_FACTOR,
            ground_size=GROUND_SIZE_M,
            publish_period_s=AID_PUBLISH_PERIOD_S,
            conveyors=_conveyors(cell),
            beams=_beams(cell),
            workpieces=cell.workpiece_models,
        )
    )
    return [Artifact(f"worlds/{cell.zone}.sdf", text)]
