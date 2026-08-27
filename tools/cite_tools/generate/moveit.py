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

#: The four adapters MoveIt runs before a planner sees a request.
#:
#: Named once because both pipelines get all four, which is what
#: `moveit_configs_utils/default_configs/*_planning.yaml` ships for each of them
#: upstream. Divergence from that is the thing to justify, not conformance to it.
REQUEST_ADAPTERS = (
    "default_planning_request_adapters/ResolveConstraintFrames",
    "default_planning_request_adapters/ValidateWorkspaceBounds",
    "default_planning_request_adapters/CheckStartStateBounds",
    "default_planning_request_adapters/CheckStartStateCollision",
)


@dataclass(frozen=True)
class _OmplPlannerConfig:
    """One entry of OMPL's `planner_configs` table."""

    name: str
    type: str
    range: float


@dataclass(frozen=True)
class _Pipeline:
    """What one MoveIt planning pipeline is made of.

    A pipeline is a plugin class plus two adapter chains, which is a fact about
    MoveIt rather than about the facility — so *what* a pipeline is made of lives
    here, in code, and *which* one plans lives in the model (P5, ADR-0027).

    `notes` is rendered into the generated file as the comment above the block.
    It lives here rather than in the template for the same reason the plugin name
    does: it explains the composition, and the composition is defined here. It is
    also what lets the template hold no pipeline name at all — the template
    renders whatever this mapping contains, so a pipeline cannot be known to the
    guard below and missing from the generated list.
    """

    planning_plugins: tuple[str, ...]
    response_adapters: tuple[str, ...]
    #: The planner ids this pipeline registers, as `ros2 service call
    #: query_planner_interface` reports them. Empty means the pipeline names its
    #: planners from its own configuration rather than from a fixed set, which is
    #: OMPL: the block below declares exactly one configuration for the group.
    planners: tuple[str, ...] = ()
    #: Of `planners`, the ones that interpolate a path in CARTESIAN space and so
    #: need the full end-effector pose solvable at every sample along it.
    cartesian_planners: tuple[str, ...] = ()
    #: A pipeline that wants no request adapters writes `()`, and the template
    #: then omits the key entirely rather than emitting `request_adapters: []`.
    #: The distinction is not cosmetic: a ROS parameter takes its type from its
    #: value, an empty sequence has none, and launch refuses the whole file with
    #: "Expected 'value' to be one of [float, int, str, bool, bytes], but got
    #: '()'" — an error that names a tuple and not the key it came from. Omitting
    #: the key leaves the pipeline's own default, which is the empty chain.
    request_adapters: tuple[str, ...] = REQUEST_ADAPTERS
    #: OMPL's planner table. Empty for a pipeline that has no such table.
    planner_configs: tuple[_OmplPlannerConfig, ...] = ()
    #: The collision-check resolution for a pipeline that SEARCHES the scene,
    #: as a fraction of the group's extent. `None` for a pipeline that does not
    #: search, where it would be an unread key.
    longest_valid_segment_fraction: float | None = None
    notes: tuple[str, ...] = ()


#: The MoveIt pipelines this generator knows how to configure.
#:
#: Naming one that is not a key here is an error rather than a file that
#: generates cleanly and leaves move_group dying with "Exception while loading
#: planner". The generated file's `planning_pipelines:` list and every block
#: under it are rendered from this mapping, so the two cannot disagree.
PIPELINES: dict[str, _Pipeline] = {
    "pilz_industrial_motion_planner": _Pipeline(
        planning_plugins=("pilz_industrial_motion_planner/CommandPlanner",),
        planners=("PTP", "LIN", "CIRC"),
        cartesian_planners=("LIN", "CIRC"),
        response_adapters=(
            "default_planning_response_adapters/ValidateSolution",
            "default_planning_response_adapters/DisplayMotionPath",
        ),
        notes=(
            "A trajectory GENERATOR, not a search. PTP integrates a trapezoidal",
            "profile over the joint limits in the file beside this one, so the same",
            "request produces the same trajectory and a failure can be bisected",
            "instead of re-run until it goes green (ADR-0027). What it costs is that",
            "it fails on a collision rather than routing around one: its only",
            "collision call during generation is a self-collision check, so a",
            "straight path through a table is refused, not detoured. That is what the",
            "other pipeline is kept for.",
            "",
            "ValidateSolution is therefore the ONLY thing standing between a",
            "generated straight line and a collision with the cell, and it checks",
            "WAYPOINTS. `PlanningScene::isPathValid` tests each waypoint of the",
            "finished trajectory and interpolates nothing between them, so what it",
            "can see is decided by how far apart the waypoints are.",
            "",
            "That spacing is Pilz's sampling time, and it is 0.1 s. It is a C++",
            "default argument — `TrajectoryGenerator::generate(scene, req, res,",
            "double sampling_time = 0.1)`, which `PlanningContextBase::solve` calls",
            "with three arguments — and not a ROS parameter, so it cannot be stated",
            "in L0 and cannot be set from this file. It is asserted rather than",
            "assumed: cite_skills' planning-pipeline launch test measures the",
            "`time_from_start` spacing of a PTP trajectory and fails if a MoveIt",
            "release changes it.",
            "",
            "What that costs, stated rather than glossed. The smallest object in the",
            "generated planning scene is a 40 mm break-beam housing, so a waypoint",
            "step exceeds it whenever the tool point moves faster than 0.40 m/s. This",
            "arm's joints are limited to 3.14 rad/s by the vendor description and",
            "this configuration scales that by the velocity factor in the joint-limit",
            "file, which at a 0.7 m reach still permits roughly 0.077 m of tool",
            "travel between two checked waypoints. An object thinner than that step",
            "CAN lie strictly between two checked waypoints and be missed. Nothing",
            "here closes that; it is a residual of choosing a generator over a",
            "search, and it is named so it is not rediscovered as a mystery",
            "collision.",
            "",
            "The request adapters are upstream's, byte for byte. MoveIt's own",
            "moveit_configs_utils/default_configs/ ships a defaults file for this",
            "pipeline and it gives it the same four it gives the other one. An",
            "earlier version of this file",
            "declared no chain at all and said Pilz wanted none, which was wrong in",
            "one place that matters and imprecise in two more. Taken one at a time:",
            "ResolveConstraintFrames is performed by NOTHING otherwise, and the day",
            "a goal names a frame — a pose target, or a path constraint on a",
            "subframe — its absence is a plan against the wrong frame rather than an",
            "error; CheckStartStateBounds decides whether a start state a hair",
            "outside its bounds is nudged back in or refused, and refusing it here",
            "would spend a whole fallback pass on a numerical epsilon and report it",
            "as the cell's geometry, which is exactly the signal ADR-0027 wants kept",
            "clean; ValidateWorkspaceBounds supplies a default sampling volume for",
            "unbounded joints and is inert for this fixed-base revolute arm — it is",
            "kept because matching upstream is cheaper to reason about than a",
            "divergence, NOT because it enforces a cell workspace, which it has",
            "never done; CheckStartStateCollision is subsumed by ValidateSolution,",
            "which checks every waypoint including waypoint 0.",
            "",
            "No AddTimeOptimalParameterization. This pipeline emits a timed",
            "trajectory — the trapezoidal profile IS the output — and",
            "re-parameterising it would discard the timing the limits produced and",
            "put a different one in its place.",
        ),
    ),
    "ompl": _Pipeline(
        planning_plugins=("ompl_interface/OMPLPlanner",),
        response_adapters=(
            "default_planning_response_adapters/AddTimeOptimalParameterization",
            "default_planning_response_adapters/ValidateSolution",
            "default_planning_response_adapters/DisplayMotionPath",
        ),
        planner_configs=(
            _OmplPlannerConfig(
                name="RRTConnectkConfigDefault", type="geometric::RRTConnect", range=0.0
            ),
        ),
        longest_valid_segment_fraction=0.005,
        notes=(
            "Sampling-based, and therefore stochastic (ADR-0006). It searches the",
            "scene, so it routes around an obstacle the other pipeline would refuse",
            "— which is the whole reason it is kept, and why it is reached through a",
            "fallback rather than deleted.",
            "",
            "Because it searches, its own collision-check resolution is a stated",
            "parameter here: `longest_valid_segment_fraction` is the fraction of the",
            "group's extent below which a motion between two states is taken on",
            "trust. It applies to this pipeline only. The other one does not",
            "interpolate between the waypoints it checks, so this key would be an",
            "unread number in its block rather than a stricter check.",
        ),
    ),
}


class PlanningConfigurationError(ValueError):
    """The model asked for a planner configuration this generator cannot emit.

    Carries `rule` and `where` so the CLI can report it in the same shape as
    every other model problem — `error <rule> <where>` — rather than as a raw
    traceback. A traceback is the right answer for a generator bug and the wrong
    one for a model that says something the generator will not build.
    """

    def __init__(self, rule: str, where: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule
        self.where = where
        self.message = message


class UnknownPipelineError(PlanningConfigurationError):
    """The model named a planning pipeline the generator cannot configure."""


class UnknownPlannerError(PlanningConfigurationError):
    """The model named a planner the chosen pipeline does not register."""


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


def _check_planner(
    type_id: str, role: str, pipeline_name: str, planner_id: str, joint_count: int
) -> None:
    """Reject a planner the pipeline does not register, or the arm cannot use.

    Both checks fail at GENERATION time, which is the only place they can be
    cheap. A planner id the pipeline does not know produces a file that loads
    perfectly and then refuses every request — the failure mode ADR-0027's
    deceleration limit already demonstrated once.
    """
    pipeline = PIPELINES[pipeline_name]
    if not planner_id:
        # An empty id means "whatever that pipeline defaults to", which is only
        # answerable for a pipeline that names its planners from its own
        # configuration. Pilz has no default and answers "No ContextLoader for
        # planner_id ''" at plan time.
        if pipeline.planners:
            raise UnknownPlannerError(
                "planner-id",
                f"{type_id}.planning.{role}",
                f"is empty, and {pipeline_name} has no default planner — it refuses "
                f"a request with an empty planner id. Name one of: "
                f"{', '.join(pipeline.planners)}.",
            )
        return

    if pipeline.planners and planner_id not in pipeline.planners:
        raise UnknownPlannerError(
            "planner-id",
            f"{type_id}.planning.{role}",
            f"is {planner_id!r}, which {pipeline_name} does not register. Known "
            f"planners: {', '.join(pipeline.planners)}.",
        )

    # Not a taste question, and not hardcoded to this arm. A Cartesian planner
    # interpolates the tool POSE and solves full six-degree-of-freedom IK at
    # every sample, so it needs six joints in the group to have a solution
    # anywhere but on a surface. Making it an arm's DEFAULT on a group with fewer
    # refuses most of the cell's motions at plan time, which reads as the cell
    # being unreachable rather than as the planner being the wrong one. Measured
    # on the five-joint arm in cite_skills' planning-pipeline launch test: a
    # purely vertical approach plans, a motion that turns the base does not.
    if (
        role == "default_planner_id"
        and planner_id in pipeline.cartesian_planners
        and joint_count < 6
    ):
        raise UnknownPlannerError(
            "cartesian-default-planner",
            f"{type_id}.planning.{role}",
            f"is {planner_id!r}, which interpolates in Cartesian space and needs "
            f"the full end-effector pose solvable at every sample along the path. "
            f"This group has {joint_count} joints, so its reachable poses are a "
            f"surface rather than a volume (ADR-0026) and most straight paths have "
            f"no solution in the middle. Keep it available per request and default "
            f"to a joint-space planner.",
        )


def _view(asset: ResolvedAsset) -> _PlanningView | None:
    planning = asset.asset_type.planning
    kinematics = asset.asset_type.kinematics
    if planning is None or kinematics is None:
        return None
    if not (planning.srdf_package and planning.srdf_file and planning.srdf_macro):
        return None

    joints = tuple(ids.joint(asset.id, s) for s in kinematics.joint_suffixes)

    for pipeline_role, pipeline, planner_role, planner_id in (
        (
            "default_pipeline",
            planning.default_pipeline,
            "default_planner_id",
            planning.default_planner_id,
        ),
        (
            "fallback_pipeline",
            planning.fallback_pipeline,
            "fallback_planner_id",
            planning.fallback_planner_id,
        ),
    ):
        if pipeline not in PIPELINES:
            raise UnknownPipelineError(
                "planning-pipeline",
                f"{asset.asset_type.id}.planning.{pipeline_role}",
                f"is {pipeline!r}, which this generator cannot configure. Known "
                f"pipelines: {', '.join(PIPELINES)}.",
            )
        _check_planner(asset.asset_type.id, planner_role, pipeline, planner_id, len(joints))

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
                Artifact(
                    f"{stem}{suffix}",
                    env.get_template(template).render(arm=view, pipelines=PIPELINES),
                )
            )

    return artifacts
