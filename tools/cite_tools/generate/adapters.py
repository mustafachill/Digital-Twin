"""Generate a physical side's adapter configuration from L0 (ADR-0070 items 3-6).

A side whose hardware is physical runs three nodes beside its controller
manager — `cite_hardware`'s deadman, track adapter and gripper relay — and none
of their parameters has a default: each is a fact of the asset, so each is
emitted here from the model and from names `ids` forms, into ONE parameter file
for that side, keyed by the nodes' fully qualified names. The bring-up plan
names the file and the nodes (`physical_side`), and the side's launch starts
each node under that name with that file. Nothing in a launch states a value.

Per side by `per_side_path`, like the description and the controller
configuration, and only for a side that commands physical hardware through an
embedded vendor driver: a simulated side runs none of these nodes.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact, adapters_path
from cite_tools.generate.description import (
    VendorNames,
    described_sides,
    description_argument,
    vendor_names,
)
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.model.units import fmt_float
from cite_tools.render import environment


class PhysicalSideError(Exception):
    """A physical side the generator cannot configure from what L0 states."""


#: The vendor services each physical-side node calls, by the parameter it takes
#: the name under. The only place a vendor service name meets a node parameter;
#: the names themselves are the allow-list in `schema` and are formed by
#: `ids.vendor_interface`.
_DEADMAN_SERVICES = {
    "set_state_service": "set_state",
    "set_mode_service": "set_mode",
    "linear_motor_stop_service": "set_linear_motor_stop",
}
_TRACK_SERVICES = {
    "set_position_service": "set_linear_motor_pos",
    "speed_service": "set_linear_motor_speed",
    "get_position_service": "get_linear_motor_pos",
    "stop_service": "set_linear_motor_stop",
}
_GRIPPER_SERVICES = {"get_position_service": "get_gripper_position"}


@dataclass(frozen=True)
class NodeView:
    """One node: its fully qualified name, and its parameters, already formatted."""

    node: str
    parameters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PhysicalSideView:
    """What a physical side runs beside its controller manager, and how to watch it."""

    #: The generated parameter file, relative to the generated package.
    parameters: str
    deadman: NodeView
    track_adapter: NodeView | None
    gripper_relay: NodeView | None
    deadman_state_topic: str
    #: The arm trajectory controller's state topic, published only while that
    #: controller is active: what the twin boundary reads as "the arm's
    #: controller is running on this side".
    arm_controller_state_topic: str
    #: Every joint whose state this side publishes - the non-fixed, non-mimic
    #: joints of the description - whichever node publishes it.
    joints: tuple[str, ...]


def joint_state_topic(asset: ResolvedAsset) -> str:
    """The arm's joint-state topic: `joint_state_broadcaster`'s, in the arm's namespace."""
    return f"{asset.namespace}/joint_states"


def controller_action(asset: ResolvedAsset, suffix: str) -> str | None:
    """The full action name a controller of this asset exposes, built once by `ids`.

    `None` where the asset declares no such controller. The name is the same on
    every side, whether or not that side loads the controller: a side that does
    not serves the name some other way (ADR-0070 item 4).
    """
    name = ids.controller(asset.id, suffix)
    if not any(c.name == name for c in asset.controllers):
        return None
    action = "follow_joint_trajectory" if "trajectory" in suffix else "gripper_cmd"
    return ids.interface(asset.zone, asset.id, f"{name}/{action}")


def _f(value: float) -> str:
    """A ROS double: always with a decimal point, or a node declaring it refuses it."""
    return fmt_float(value)


def _service(vendor: VendorNames, name: str, asset: ResolvedAsset) -> str:
    services = dict(vendor.services)
    if name not in services:
        raise PhysicalSideError(
            f"asset {asset.id!r}: the physical side calls the vendor service {name!r}, "
            "which its backend's `vendor_driver.services` does not switch on "
            "(`vendor-service-missing`)"
        )
    return services[name]


def _refuse_controllers_that_fight(asset: ResolvedAsset, side: str) -> None:
    """Refuse a physical side whose controllers would command one joint twice (L-5).

    The vendor plugin activates EVERY controller its manager lists when the arm
    recovers (`uf_robot_system_hardware.cpp:426-440`), so every controller loaded
    on a physical side must be safe to be active at once with every other.
    """
    claimed: dict[str, str] = {}
    for controller in asset.controllers_on(side):
        if not controller.command_interfaces:
            continue
        for joint in controller.joints:
            if joint in claimed:
                raise PhysicalSideError(
                    f"asset {asset.id!r} loads {claimed[joint]!r} and {controller.name!r} on "
                    f"the {side} side, and both command {joint!r}. The vendor plugin "
                    "activates every listed controller at once on recovery."
                )
            claimed[joint] = controller.name


def physical_side(cell: ResolvedCell, asset: ResolvedAsset, side: str) -> PhysicalSideView | None:
    """What ``side`` of ``asset`` runs as a physical side, or `None` where it is not one.

    A side is configured here when it loads a description of its own, its
    backend commands physical hardware, and that backend embeds a vendor driver.
    """
    if side not in described_sides(cell, asset) or side == ids.PLANT_SIDE:
        return None
    if not asset.commands_physical_hardware_of(asset.backend_on(side)):
        return None
    vendor = vendor_names(asset, cell, side)
    if vendor is None:
        return None
    timing = None if cell.twin is None else cell.twin.physical_side
    if timing is None:
        raise PhysicalSideError(
            f"zone {cell.zone!r} states no `twin.physical_side` timing, and the {side} side "
            f"of {asset.id!r} is physical (`physical-side-timing-unstated`)"
        )
    _refuse_controllers_that_fight(asset, side)

    deadman_state_topic = ids.interface(cell.zone, asset.id, ids.DEADMAN_STATE)
    trajectory_action = controller_action(asset, "joint_trajectory_controller")
    if trajectory_action is None:
        raise PhysicalSideError(
            f"asset {asset.id!r} has no arm trajectory controller, so the deadman has no "
            "arm action to cancel"
        )
    states = joint_state_topic(asset)
    kinematics = asset.asset_type.kinematics
    joints = (
        []
        if kinematics is None
        else [ids.joint(asset.id, suffix) for suffix in kinematics.joint_suffixes]
    )

    track = None
    axis = asset.axis
    if axis is not None and axis.plugin_on(side) is None:
        served = axis.vendor_axis_on(side)
        if served is None:
            raise PhysicalSideError(
                f"track {axis.asset!r} is physical and plugin-less on the {side} side and "
                "states no `vendor_axis` (`vendor-axis-unstated`)"
            )
        track = NodeView(
            node=ids.interface(cell.zone, asset.id, ids.TRACK_ADAPTER_NODE),
            parameters=(
                ("use_sim_time", "false"),
                ("command_topic", axis.command_topic),
                ("joint", axis.joint),
                ("joint_state_topic", states),
                ("position_scale", _f(served.position_scale)),
                # The joint's travel as the description limits it: from stroke
                # zero to the stroke (the axis's `<limit lower upper>`).
                ("position_min_m", _f(0.0)),
                ("position_max_m", _f(axis.stroke_m)),
                ("max_speed_mps", _f(axis.max_speed_mps)),
                ("poll_period_s", _f(served.poll_period_s)),
                ("position_max_age_s", _f(served.position_max_age_s)),
                ("segment_s", _f(served.segment_s)),
                ("auto_enable", "true" if served.auto_enable else "false"),
                *(
                    (parameter, _service(vendor, name, asset))
                    for parameter, name in _TRACK_SERVICES.items()
                ),
                ("deadman_state_topic", deadman_state_topic),
                ("deadman_state_max_age_s", _f(timing.state_max_age_s)),
            ),
        )
        joints.append(axis.joint)

    relay = None
    effector = asset.instance.end_effector
    effector_type = None if effector is None else cell.end_effector_type(effector.type)
    grasp = None if effector_type is None else effector_type.grasp
    gripper_action = controller_action(asset, "gripper_controller")
    if vendor.gripper_action is not None and grasp is not None and gripper_action is not None:
        units = grasp.vendor
        if units is None:
            raise PhysicalSideError(
                f"end effector {effector_type.id!r} states no `grasp.vendor` units "  # type: ignore[union-attr]
                "(`vendor-gripper-units-unstated`)"
            )
        drive_joint = ids.joint(asset.id, grasp.drive_joint_suffix)
        relay = NodeView(
            node=ids.interface(cell.zone, asset.id, ids.GRIPPER_RELAY_NODE),
            parameters=(
                ("use_sim_time", "false"),
                ("action_name", gripper_action),
                ("vendor_action_name", vendor.gripper_action),
                ("open_position", _f(grasp.open_position)),
                ("closed_position", _f(grasp.closed_position)),
                ("vendor_open_position", _f(units.action_open_position)),
                ("vendor_closed_position", _f(units.action_closed_position)),
                ("result_timeout_s", _f(grasp.result_timeout_s)),
                ("deadman_state_topic", deadman_state_topic),
                ("deadman_state_max_age_s", _f(timing.state_max_age_s)),
                ("drive_joint", drive_joint),
                ("joint_state_topic", states),
                *(
                    (parameter, _service(vendor, name, asset))
                    for parameter, name in _GRIPPER_SERVICES.items()
                ),
                ("vendor_state_open_position", _f(units.state_open_position)),
                ("vendor_state_closed_position", _f(units.state_closed_position)),
                ("poll_period_s", _f(units.poll_period_s)),
            ),
        )
        joints.append(drive_joint)

    backend = asset.asset_type.hardware_backends[asset.backend_on(side)]
    assert backend.vendor_driver is not None  # vendor_names returned names
    streaming = backend.vendor_driver.streaming_mode
    selector = description_argument(asset, cell, side, streaming.argument)
    if selector not in ("true", "false"):
        raise PhysicalSideError(
            f"asset {asset.id!r}: `{streaming.argument}` is {selector!r}, not a boolean, so "
            "the mode the plugin streams in is unknown"
        )
    enable_mode = streaming.when_true if selector == "true" else streaming.when_false
    cancel_actions = [trajectory_action]
    if relay is not None and gripper_action is not None:
        cancel_actions.append(gripper_action)
    deadman = NodeView(
        node=ids.interface(cell.zone, asset.id, ids.DEADMAN_NODE),
        parameters=(
            ("use_sim_time", "false"),
            ("zone", cell.zone),
            ("asset_id", asset.id),
            ("state_topic", deadman_state_topic),
            *(
                (parameter, _service(vendor, name, asset))
                for parameter, name in _DEADMAN_SERVICES.items()
            ),
            ("timeout_s", _f(timing.deadman_timeout_s)),
            ("tick_period_s", _f(timing.deadman_tick_period_s)),
            ("call_deadline_s", _f(timing.call_deadline_s)),
            ("enable_mode", str(enable_mode)),
            ("cancel_actions", "[" + ", ".join(cancel_actions) + "]"),
        ),
    )
    trajectory_controller = trajectory_action.rsplit("/", 1)[0]
    return PhysicalSideView(
        parameters=adapters_path(cell.zone, asset.id, side),
        deadman=deadman,
        track_adapter=track,
        gripper_relay=relay,
        deadman_state_topic=deadman_state_topic,
        arm_controller_state_topic=f"{trajectory_controller}/controller_state",
        joints=tuple(sorted(joints)),
    )


def generate(cell: ResolvedCell) -> list[Artifact]:
    """One adapter configuration per physical side of each controlled asset."""
    template = environment().get_template("control/adapters.yaml.j2")
    artifacts: list[Artifact] = []
    for asset in cell.assets:
        if not asset.controllers:
            continue
        for side in described_sides(cell, asset):
            view = physical_side(cell, asset, side)
            if view is None:
                continue
            nodes = [n for n in (view.deadman, view.track_adapter, view.gripper_relay) if n]
            artifacts.append(
                Artifact(view.parameters, template.render(arm=asset, side=side, nodes=nodes))
            )
    return artifacts
