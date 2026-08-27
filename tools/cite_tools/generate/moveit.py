"""Generate the MoveIt configuration from L0.

ADR-0006 requires this to be generated rather than produced once by the setup
assistant and then maintained by hand. The reason is the same as everywhere else
in this layer: the controller names MoveIt is told about and the controller names
`ros2_control` was configured with must be the same names, and the only way to
guarantee that is for both to come from one source. A mismatch between them fails
at run time with an error naming neither.

The SRDF is the exception that proves the vendor rule. Its self-collision matrix
is a fact about the vendor's geometry, not about our facility — so like the
description, the vendor's SRDF macro is *invoked* with our prefix rather than
copied. Re-deriving that matrix would mean inventing an answer the vendor already
has, and getting it wrong makes a planner refuse valid states or accept invalid
ones.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.render import environment

#: The MoveIt pipelines this generator knows how to configure.
#:
#: A pipeline is a plugin class plus an adapter chain, which is a fact about
#: MoveIt rather than about the facility — so *what* a pipeline is made of lives
#: here, in code, and *which* one plans lives in the model (P5, ADR-0027). Naming
#: one that is not in this set is an error rather than a file that generates
#: cleanly and leaves move_group dying with "Exception while loading planner".
PIPELINES = ("pilz_industrial_motion_planner", "ompl")


class UnknownPipelineError(ValueError):
    """The model named a planning pipeline the generator cannot configure."""


@dataclass(frozen=True)
class _PlanningView:
    id: str
    group: str
    joints: tuple[str, ...]
    trajectory_controller: str
    gripper_controller: str | None
    gripper_joint: str | None
    srdf_package: str
    srdf_file: str
    srdf_macro: str
    srdf_args: tuple[tuple[str, str], ...]
    kinematics_plugin: str
    kinematics_resolution: float
    kinematics_timeout_s: float
    max_velocity_scaling: float
    max_acceleration_scaling: float
    max_acceleration_rad_s2: float
    max_deceleration_rad_s2: float
    default_pipeline: str
    default_planner_id: str
    fallback_pipeline: str
    fallback_planner_id: str
    max_cartesian_velocity_m_s: float
    max_cartesian_acceleration_m_s2: float
    max_cartesian_deceleration_m_s2: float
    max_cartesian_rotational_velocity_rad_s: float


def _view(asset: ResolvedAsset) -> _PlanningView | None:
    planning = asset.asset_type.planning
    kinematics = asset.asset_type.kinematics
    if planning is None or kinematics is None:
        return None
    if not (planning.srdf_package and planning.srdf_file and planning.srdf_macro):
        return None

    for role, pipeline in (
        ("default_pipeline", planning.default_pipeline),
        ("fallback_pipeline", planning.fallback_pipeline),
    ):
        if pipeline not in PIPELINES:
            raise UnknownPipelineError(
                f"{asset.asset_type.id}.planning.{role} is {pipeline!r}, which this "
                f"generator cannot configure. Known pipelines: {', '.join(PIPELINES)}."
            )

    joints = tuple(ids.joint(asset.id, s) for s in kinematics.joint_suffixes)

    trajectory = next(
        (c.name for c in asset.controllers if c.name.endswith("joint_trajectory_controller")),
        None,
    )
    gripper = next(
        (c.name for c in asset.controllers if c.name.endswith("gripper_controller")), None
    )
    if trajectory is None:
        return None

    args: list[tuple[str, str]] = [
        (name, str(value).lower() if isinstance(value, bool) else str(value))
        for name, value in sorted(planning.srdf_args.items())
    ]
    args.append(("prefix", asset.prefix))
    # The gripper is part of the planning chain only when one is actually fitted;
    # telling the SRDF otherwise would give a tip link the description does not
    # contain, and MoveIt would fail to build the group at all.
    args.append(
        (
            "add_gripper",
            str(
                bool(asset.instance.end_effector and asset.instance.end_effector.vendor_integrated)
            ).lower(),
        )
    )

    return _PlanningView(
        id=asset.id,
        group=ids.controller(asset.id, planning.group_suffix),
        joints=joints,
        trajectory_controller=trajectory,
        gripper_controller=gripper,
        gripper_joint=ids.joint(asset.id, "drive_joint") if gripper else None,
        srdf_package=planning.srdf_package,
        srdf_file=planning.srdf_file,
        srdf_macro=planning.srdf_macro,
        srdf_args=tuple(sorted(args)),
        kinematics_plugin=planning.kinematics_plugin,
        kinematics_resolution=planning.kinematics_resolution,
        kinematics_timeout_s=planning.kinematics_timeout_s,
        max_velocity_scaling=planning.max_velocity_scaling,
        max_acceleration_scaling=planning.max_acceleration_scaling,
        # From the type, not from a constant here: an acceleration ceiling is a
        # fact about a particular arm, and a module constant applied it
        # identically to every type the generator would ever see (P5).
        max_acceleration_rad_s2=planning.max_acceleration_rad_s2,
        max_deceleration_rad_s2=planning.max_deceleration_rad_s2,
        default_pipeline=planning.default_pipeline,
        default_planner_id=planning.default_planner_id,
        fallback_pipeline=planning.fallback_pipeline,
        fallback_planner_id=planning.fallback_planner_id,
        max_cartesian_velocity_m_s=planning.max_cartesian_velocity_m_s,
        max_cartesian_acceleration_m_s2=planning.max_cartesian_acceleration_m_s2,
        max_cartesian_deceleration_m_s2=planning.max_cartesian_deceleration_m_s2,
        max_cartesian_rotational_velocity_rad_s=(planning.max_cartesian_rotational_velocity_rad_s),
    )


def generate(cell: ResolvedCell) -> list[Artifact]:
    env = environment()
    artifacts: list[Artifact] = []

    for asset in cell.assets:
        view = _view(asset)
        if view is None:
            continue
        stem = f"moveit/{cell.zone}_{asset.id}"
        for suffix, template in (
            (".srdf.xacro", "moveit/srdf.xacro.j2"),
            ("_kinematics.yaml", "moveit/kinematics.yaml.j2"),
            ("_planning_pipelines.yaml", "moveit/planning_pipelines.yaml.j2"),
            ("_joint_limits.yaml", "moveit/joint_limits.yaml.j2"),
            ("_cartesian_limits.yaml", "moveit/cartesian_limits.yaml.j2"),
            ("_moveit_controllers.yaml", "moveit/moveit_controllers.yaml.j2"),
        ):
            artifacts.append(
                Artifact(f"{stem}{suffix}", env.get_template(template).render(arm=view))
            )

    return artifacts
