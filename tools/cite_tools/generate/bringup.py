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
from cite_tools.generate.moveit import PIPELINES
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell, ResolveError
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
    default_pipeline: str | None
    default_planner_id: str | None
    fallback_pipeline: str | None
    fallback_planner_id: str | None
    #: Which of the planner ids the arm's pipelines register define the SHAPE of
    #: a path rather than only its endpoints. Read from the one place that says
    #: what a pipeline is made of, so the L3 server never restates it.
    cartesian_planner_ids: tuple[str, ...]
    home_rad: tuple[float, ...]
    trajectory_action: str | None
    gripper_action: str | None
    gripper_open_position: float | None
    gripper_closed_position: float | None
    gripper_default_grasp_width_m: float | None
    gripper_goal_tolerance_rad: float | None
    #: The ARM trajectory controller's goal tolerance, from the same L0
    #: `constraints:` block that configures the controller (ADR-0036). Delivered
    #: to L3 because ADR-0037 classifies a failed execution against the plan's
    #: endpoints and must use the arm's own threshold rather than a copy of it.
    arm_goal_tolerance_rad: float | None
    gripper_max_drive_rate_rad_s: float | None
    gripper_drive_pivot_y_m: float | None
    gripper_drive_pivot_z_m: float | None
    gripper_finger_offset_y_m: float | None
    gripper_finger_offset_z_m: float | None
    gripper_pad_inset_m: float | None
    gripper_tip_link_z_m: float | None
    gripper_pad_face_centre_z_m: float | None
    skills: _SkillView | None


@dataclass(frozen=True)
class _SkillView:
    """The action names one arm's L3 skill server advertises.

    Generated rather than assembled by whoever launches the coordinator. L4 read
    these as parallel parameter arrays supplied by hand, which put an asset name
    — `/cite/<zone>/<asset>/pick` — in a second place, outside the reach of
    `ids.py` and of every test that covers it. Declaring them here is what makes
    the plan the one statement of what an arm offers.
    """

    move_to: str
    pick: str
    place: str
    grasp: str
    transfer: str


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
    level_topic: str
    frame_id: str
    beam_axis: str
    beam_length_m: float


@dataclass(frozen=True)
class _DetectionView:
    """Where the zone's one detection server lives, and what it advertises.

    One per zone, not one per arm: a break beam watches a belt, not a robot, and
    three servers would give the question "did the piece pass beam 2" three
    answers. It is not an asset, so its namespace is a reserved zone-scope name
    rather than `ids.namespace`.
    """

    namespace: str
    detect_action: str


def _planning_group(asset: ResolvedAsset) -> str | None:
    planning = asset.asset_type.planning
    return ids.controller(asset.id, planning.group_suffix) if planning else None


def _planning_field(asset: ResolvedAsset, field: str) -> str | None:
    """One string from the type's planning specification, or None.

    Read through rather than restated. The planner an arm is asked for first, and
    the one a refusal falls back to, are declared once in L0 (ADR-0027) and reach
    the L3 skill server through this plan under the parameter names the server
    itself declares — so there is no list of keys anywhere that can go stale
    against the server, which is the failure the gripper parameters shipped.
    """
    planning = asset.asset_type.planning
    return getattr(planning, field) if planning else None


def _cartesian_planner_ids(asset: ResolvedAsset) -> tuple[str, ...]:
    """Every Cartesian planner id reachable from this arm's two pipelines.

    A planner whose contract is the shape of the path — Pilz LIN and CIRC — must
    not have a refusal answered by a planner that samples: the caller asked for a
    straight line and would get a curve through the same endpoints, reported as
    success. The L3 server enforces that, and it takes the SET from here rather
    than compiling it in, because which ids are Cartesian is a fact about MoveIt
    that `generate/moveit.py` already states once (P1, ADR-0027).
    """
    planning = asset.asset_type.planning
    if planning is None:
        return ()
    ids_: list[str] = []
    for name in (planning.default_pipeline, planning.fallback_pipeline):
        pipeline = PIPELINES.get(name)
        if pipeline is None:
            continue
        ids_ += [i for i in pipeline.cartesian_planners if i not in ids_]
    return tuple(ids_)


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


def _linkage(cell: ResolvedCell, asset: ResolvedAsset, field: str) -> float | None:
    """One dimension of the end effector's opening linkage, or None.

    Separate from :func:`_grasp` only because the value sits one level deeper.
    The seven dimensions travel together to L3, where the same closed forms are
    evaluated — neither map is ever transmitted, only the geometry both are built
    from, so there is still exactly one statement of each (P1).
    """
    if asset.instance.end_effector is None:
        return None
    effector = cell.end_effector_type(asset.instance.end_effector.type)
    if effector is None or effector.grasp is None:
        return None
    return float(getattr(effector.grasp.linkage, field))


def _controller_parameter(asset: ResolvedAsset, suffix: str, key: str) -> float | None:
    """One parameter of one of this asset's controllers, or None if unset.

    This is how a number that configures a *controller* also reaches the skill
    server without being written twice. `goal_tolerance` is the case that forced
    it: the controller decides when a goal is close enough to end, and L3 cannot
    tell a real grasp from the resulting position bias unless it knows the same
    threshold.
    """
    name = ids.controller(asset.id, suffix)
    for controller in asset.controllers:
        if controller.name == name:
            value = controller.parameters.get(key)
            return None if value is None else float(value)
    return None


def _trajectory_constraint(asset: ResolvedAsset, suffix: str, field: str) -> float | None:
    """One field of one controller's `constraints:` block, or None if it has none.

    The `constraints:` counterpart of `_controller_parameter` above, and it exists
    for the same reason: ADR-0036 declares the arm's tolerances once in L0, the
    control generator renders them into the controller's own configuration, and
    ADR-0037's classification in L3 has to judge against the SAME number. Reading
    it here is what keeps the count of places that number is stated at one (P1).

    `constraints` is carried on the resolved controller rather than flattened into
    `parameters` because its per-joint expansion needs the resolved joint list —
    see `ResolvedController.constraints`.
    """
    name = ids.controller(asset.id, suffix)
    for controller in asset.controllers:
        if controller.name == name and controller.constraints is not None:
            value = getattr(controller.constraints, field, None)
            return None if value is None else float(value)
    return None


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


#: The zone-scope namespace the one detection server runs in.
#:
#: It occupies an asset slot in `/cite/<zone>/<name>` without being an asset,
#: which is legal and is checked below: an asset of this name would put two
#: different things on one namespace, and `ids.py` reserves only the
#: facility-level scopes.
DETECTION_SCOPE = "detection"


def _skills(cell: ResolvedCell, asset: ResolvedAsset) -> _SkillView | None:
    """The action names this arm's skill server advertises, or None.

    None when the arm has no planning group, because `cite_bringup` starts a
    skill server only for an arm MoveIt can plan for — a plan that advertised
    skills for an arm nothing plans for would name five actions that never come
    into existence.
    """
    if _planning_group(asset) is None:
        return None
    return _SkillView(
        **{
            skill: ids.interface(cell.zone, asset.id, skill)
            for skill in ("move_to", "pick", "place", "grasp", "transfer")
        }
    )


def _sensor_frame(cell: ResolvedCell, asset: ResolvedAsset) -> str:
    """The TF frame a sensor reports its detections in.

    Read from the asset's own frames rather than named here. A break beam
    declares exactly one — where the beam is — and taking it from the model is
    what keeps the frame the detection server resolves against and the frame the
    static TF table publishes from being the same statement.
    """
    frames = sorted(asset.frames)
    if len(frames) != 1:
        raise ResolveError(
            f"sensor {asset.id!r} declares {len(frames)} frames ({', '.join(frames) or 'none'}); "
            "a detection is reported in exactly one, and this generator cannot choose "
            "between them. Declare one frame on the sensor's type, or teach the model "
            "which frame detections are reported in."
        )
    return ids.frame(cell.zone, asset.id, frames[0])


def _detection(cell: ResolvedCell) -> _DetectionView | None:
    """Where the zone's detection server runs, or None when it has no sensors."""
    if not any(cell.of_category("sensor")):
        return None
    colliding = [a.id for a in cell.assets if a.id == DETECTION_SCOPE]
    if colliding:
        raise ResolveError(
            f"zone {cell.zone!r} contains an asset named {DETECTION_SCOPE!r}, which would "
            f"share a namespace with the zone's detection server at "
            f"{ids.namespace(cell.zone, DETECTION_SCOPE)}. Rename the asset."
        )
    return _DetectionView(
        namespace=ids.namespace(cell.zone, DETECTION_SCOPE),
        detect_action=ids.interface(cell.zone, DETECTION_SCOPE, "detect"),
    )


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
            default_pipeline=_planning_field(asset, "default_pipeline"),
            default_planner_id=_planning_field(asset, "default_planner_id"),
            fallback_pipeline=_planning_field(asset, "fallback_pipeline"),
            fallback_planner_id=_planning_field(asset, "fallback_planner_id"),
            cartesian_planner_ids=_cartesian_planner_ids(asset),
            home_rad=_home(asset),
            trajectory_action=_controller_action(asset, "joint_trajectory_controller"),
            gripper_action=_controller_action(asset, "gripper_controller"),
            gripper_open_position=_grasp(cell, asset, "open_position"),
            gripper_closed_position=_grasp(cell, asset, "closed_position"),
            gripper_default_grasp_width_m=_grasp(cell, asset, "default_grasp_width_m"),
            gripper_goal_tolerance_rad=_controller_parameter(
                asset, "gripper_controller", "goal_tolerance"
            ),
            arm_goal_tolerance_rad=_trajectory_constraint(
                asset, "joint_trajectory_controller", "goal_tolerance_rad"
            ),
            gripper_max_drive_rate_rad_s=_grasp(cell, asset, "max_drive_rate_rad_s"),
            gripper_drive_pivot_y_m=_linkage(cell, asset, "drive_pivot_y_m"),
            gripper_drive_pivot_z_m=_linkage(cell, asset, "drive_pivot_z_m"),
            gripper_finger_offset_y_m=_linkage(cell, asset, "finger_offset_y_m"),
            gripper_finger_offset_z_m=_linkage(cell, asset, "finger_offset_z_m"),
            gripper_pad_inset_m=_linkage(cell, asset, "pad_inset_m"),
            gripper_tip_link_z_m=_linkage(cell, asset, "tip_link_z_m"),
            gripper_pad_face_centre_z_m=_linkage(cell, asset, "pad_face_centre_z_m"),
            skills=_skills(cell, asset),
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
            # The same name the plugin advertises on the Gazebo transport, with
            # `_level` on the end. The two must differ: `detection_topic` is
            # already spoken for as the TYPED `DetectionEvent` a station triggers
            # on, and bridging a raw `std_msgs/Bool` onto it would put the level
            # and the event on one topic, fighting.
            level_topic=ids.interface(cell.zone, asset.id, "detection_level"),
            frame_id=_sensor_frame(cell, asset),
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
            detection=_detection(cell),
        )
    )
    return [Artifact(f"bringup/{cell.zone}_plan.yaml", text)]
