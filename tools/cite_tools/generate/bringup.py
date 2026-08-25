"""Generate the bring-up plan.

Deliberately data, not generated Python. A generated launch file is the worst of
both worlds: it is code, so it must be linted, type-checked and read, and it is
generated, so nobody reads it. The launch *mechanism* in `cite_bringup` is
written once and tested once; this plan is what varies.

`stage` here expresses dependency, never elapsed time. The mechanism gates each
stage on the previous one reporting success — which is what P4 requires, and what
v1's twelve-second `TimerAction` increments failed to do.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import environment


@dataclass(frozen=True)
class _ControllerRef:
    name: str
    stage: int


@dataclass(frozen=True)
class _ManagerView:
    asset: str
    node: str
    backend: str
    hosted_by: str
    description_topic: str
    controllers: tuple[_ControllerRef, ...]


@dataclass(frozen=True)
class _ConveyorView:
    asset: str
    state_topic: str
    command_topic: str
    installed_speed_mps: float


@dataclass(frozen=True)
class _SensorView:
    asset: str
    detection_topic: str
    beam_axis: str
    beam_length_m: float


def generate(cell: ResolvedCell) -> list[Artifact]:
    managers = tuple(
        _ManagerView(
            asset=asset.id,
            node=f"{asset.namespace}/controller_manager",
            backend=asset.instance.hardware.backend,
            # A simulated backend's controller manager is created inside the
            # Gazebo process, so there is no separate process to wait on; a real
            # backend runs its own ros2_control_node. The distinction is what
            # lets a mixed fleet be a configuration rather than a special case.
            hosted_by="simulator"
            if asset.instance.hardware.backend == "sim"
            else "ros2_control_node",
            # gz_ros2_control's controller manager inherits the plugin's
            # namespace, so it subscribes to <ns>/robot_description rather than
            # the global topic. The description publisher must match, or the
            # manager waits forever on a topic nobody writes to and the visible
            # error names the spawner instead.
            description_topic=f"{asset.namespace}/robot_description",
            controllers=tuple(
                _ControllerRef(name=c.name, stage=c.stage) for c in asset.controllers
            ),
        )
        for asset in cell.assets
        if asset.controllers
    )

    conveyors = tuple(
        _ConveyorView(
            asset=asset.id,
            state_topic=ids.interface(cell.zone, asset.id, "state"),
            command_topic=ids.interface(cell.zone, asset.id, "command"),
            installed_speed_mps=asset.instance.configuration.installed_speed_mps,  # type: ignore[union-attr]
        )
        for asset in cell.of_category("conveyor")
        if asset.instance.configuration is not None
    )

    sensors = tuple(
        _SensorView(
            asset=asset.id,
            detection_topic=ids.interface(cell.zone, asset.id, "detection"),
            beam_axis=asset.instance.configuration.beam_axis,  # type: ignore[union-attr]
            beam_length_m=asset.instance.configuration.beam_length_m,  # type: ignore[union-attr]
        )
        for asset in cell.of_category("sensor")
        if asset.instance.configuration is not None
    )

    text = (
        environment()
        .get_template("bringup/plan.yaml.j2")
        .render(
            cell=cell,
            managers=managers,
            conveyors=conveyors,
            sensors=sensors,
        )
    )
    return [Artifact(f"bringup/{cell.zone}_plan.yaml", text)]
