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
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.model.units import fmt
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
    description: str
    spawn_xyz_m: str
    spawn_rpy_rad: str
    controllers: tuple[_ControllerRef, ...]
    planning_group: str | None
    planning_tip_link: str | None
    planning_base_link: str | None
    home_rad: tuple[float, ...]
    trajectory_action: str | None
    gripper_action: str | None
    gripper_open_position: float | None
    gripper_closed_position: float | None
    gripper_max_width_m: float | None
    gripper_default_grasp_width_m: float | None


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


def _planning_group(asset: ResolvedAsset) -> str | None:
    planning = asset.asset_type.planning
    return ids.controller(asset.id, planning.group_suffix) if planning else None


def _planning_link(asset: ResolvedAsset, which: str) -> str | None:
    planning = asset.asset_type.planning
    kinematics = asset.asset_type.kinematics
    if planning is None or kinematics is None:
        return None
    suffix = planning.tip_link_suffix if which == "tip" else kinematics.base_link_suffix
    return ids.link(asset.id, suffix)


def _grasp(cell: ResolvedCell, asset: ResolvedAsset, field: str) -> float | None:
    """One value from the end effector's grasp specification, or None.

    ``None`` when the arm has no end effector, when its type declares no grasp
    specification, or when that specification leaves this particular field unset
    — which is a real state rather than an error: a vacuum end effector has no
    grasp *width* at all, and a parallel one may deliberately decline to name a
    default rather than have a wrong one applied silently.
    """
    if asset.instance.end_effector is None:
        return None
    effector = cell.end_effector_type(asset.instance.end_effector.type)
    if effector is None or effector.grasp is None:
        return None
    value = getattr(effector.grasp, field)
    return None if value is None else float(value)


def _controller_action(asset: ResolvedAsset, suffix: str) -> str | None:
    """The full action name a controller exposes, built once by ids.py.

    The skill server receives this as a parameter rather than constructing it,
    which is what keeps the number of places a name is made at exactly one.
    """
    name = ids.controller(asset.id, suffix)
    if not any(c.name == name for c in asset.controllers):
        return None
    action = "follow_joint_trajectory" if "trajectory" in suffix else "gripper_cmd"
    return ids.interface(asset.zone, asset.id, f"{name}/{action}")


def _home(asset: ResolvedAsset) -> tuple[float, ...]:
    """The retracted pose an arm returns to between cycles.

    Taken from L0 rather than from the SRDF: where an arm rests between cycles is
    a decision about this facility, not a property of the vendor's robot, and the
    vendor's SRDF declares no named states anyway.
    """
    configuration = asset.instance.configuration
    if configuration is not None and configuration.kind == "robot":
        return tuple(configuration.home_rad)
    return ()


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
            # Each arm is its own Gazebo model with its own controller manager,
            # so it publishes its own description into its own namespace. One
            # manager per model is what keeps a manager from claiming hardware
            # that belongs to another arm.
            description_topic=f"{asset.namespace}/robot_description",
            description=(f"package://cite_generated/description/{cell.zone}_{asset.id}.urdf.xacro"),
            spawn_xyz_m=" ".join(fmt(v) for v in asset.world_pose.xyz_m),
            spawn_rpy_rad=" ".join(fmt(v) for v in asset.world_pose.rpy_rad),
            controllers=tuple(
                _ControllerRef(name=c.name, stage=c.stage) for c in asset.controllers
            ),
            planning_group=_planning_group(asset),
            planning_tip_link=_planning_link(asset, "tip"),
            planning_base_link=_planning_link(asset, "base"),
            home_rad=_home(asset),
            trajectory_action=_controller_action(asset, "joint_trajectory_controller"),
            gripper_action=_controller_action(asset, "gripper_controller"),
            gripper_open_position=_grasp(cell, asset, "open_position"),
            gripper_closed_position=_grasp(cell, asset, "closed_position"),
            gripper_max_width_m=_grasp(cell, asset, "max_width_m"),
            gripper_default_grasp_width_m=_grasp(cell, asset, "default_grasp_width_m"),
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
