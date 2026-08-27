"""Generate `ros2_control` configuration from L0.

This is where ADR-0005's guarantee stops being a promise and becomes structural:
the controller names, joint names and interfaces emitted here are the ones the
physical arm will use in Phase 2, because there is nowhere else for them to come
from. The only thing that changes between the two paths is the plugin string in
the description, which is itself a per-instance selection in the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.model.schema import ControlSpec
from cite_tools.model.units import fmt_float
from cite_tools.render import environment

#: Controllers whose parameter is a single `joint`, not a `joints` list. Getting
#: this wrong produces a controller that loads and then claims no interfaces,
#: which presents as an arm that ignores commands.
SINGLE_JOINT_TYPES = frozenset({"position_controllers/GripperActionController"})

#: Controllers that must declare a `constraints:` block (ADR-0036).
#:
#: These are the controllers that execute a whole trajectory and can therefore
#: mistrack one. Named as a set rather than tested by substring so that a new
#: controller type is a deliberate addition here, in the place the rule is
#: stated, rather than something a name happens to match.
TRAJECTORY_CONTROLLER_TYPES = frozenset({"joint_trajectory_controller/JointTrajectoryController"})


class MissingControlSpecError(Exception):
    """A type declares controllers but no controller-manager configuration."""


class MissingTrajectoryConstraintsError(Exception):
    """A trajectory controller declares no execution-side tolerances."""


@dataclass(frozen=True)
class _JointToleranceView:
    """One joint's row of the `constraints:` block, already formatted."""

    joint: str
    #: `None` when the type declared no path tolerance, which makes the template
    #: omit the key rather than emit a `0.0` that reads as a deliberate choice.
    trajectory: str | None
    goal: str


@dataclass(frozen=True)
class _ConstraintsView:
    """A trajectory controller's `constraints:` block, ready to render.

    Every number arrives as text, formatted by `fmt_float`. That is not a
    cosmetic choice: these are ROS `double` parameters, YAML reads a bare `0` as
    an integer, and a node declaring a double rejects it with "invalid type:
    expected [double] got [integer]" — an error that names the type and not the
    missing decimal point. `stopped_velocity_tolerance` is the one that would hit
    it, because zero is the value we actually want there.
    """

    goal_time: str
    stopped_velocity_tolerance: str
    per_joint: tuple[_JointToleranceView, ...]


@dataclass(frozen=True)
class _ControllerView:
    name: str
    type: str
    stage: int
    joints: tuple[str, ...]
    command_interfaces: tuple[str, ...]
    state_interfaces: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...]
    single_joint_key: bool
    constraints: _ConstraintsView | None


def _constraints_view(controller: object, asset: ResolvedAsset) -> _ConstraintsView | None:
    """Expand a type's tolerances over the joints this instance actually has.

    The per-joint expansion happens here rather than in the model because the
    joint NAMES are per-instance — `arm_1_joint1` and `arm_2_joint1` are the same
    fact about the same arm type. The model states the tolerance once; this
    applies it to each joint the controller owns, which is the P5 split and the
    reason the tolerance cannot simply live in the free-form `parameters` dict.

    A trajectory controller with no block is an error rather than a default. That
    is the whole finding ADR-0036 records: the default is `0.0`, `0.0` disables
    the check, and the arm reports `SUCCEEDED` on a trajectory it never tracked.
    Defaulting here would silently reproduce exactly that, and it is the one
    outcome nobody reading the model would guess.
    """
    constraints = controller.constraints  # type: ignore[attr-defined]
    if constraints is None:
        if controller.type in TRAJECTORY_CONTROLLER_TYPES:  # type: ignore[attr-defined]
            raise MissingTrajectoryConstraintsError(
                f"controller {controller.name!r} on asset {asset.id!r} is a "  # type: ignore[attr-defined]
                f"{controller.type}, which executes whole trajectories and so can "  # type: ignore[attr-defined]
                "mistrack one, but its type declares no `constraints:` block. "
                "joint_trajectory_controller defaults every tolerance to 0.0, which "
                "DISABLES it, so the controller would run any trajectory to the end "
                "and report SUCCEEDED however badly it tracked. Add `constraints: "
                "{goal_time_s: <s>, goal_tolerance_rad: <rad>, "
                "stopped_velocity_tolerance_rad_s: <rad/s>}` to the controller in the "
                "type (ADR-0036)."
            )
        return None
    return _ConstraintsView(
        goal_time=fmt_float(constraints.goal_time_s),
        stopped_velocity_tolerance=fmt_float(constraints.stopped_velocity_tolerance_rad_s),
        per_joint=tuple(
            _JointToleranceView(
                joint=joint,
                trajectory=(
                    None
                    if constraints.trajectory_tolerance_rad is None
                    else fmt_float(constraints.trajectory_tolerance_rad)
                ),
                goal=fmt_float(constraints.goal_tolerance_rad),
            )
            for joint in controller.joints  # type: ignore[attr-defined]
        ),
    )


def _view(controller: object, asset: ResolvedAsset) -> _ControllerView:
    assert hasattr(controller, "name")
    return _ControllerView(
        name=controller.name,  # type: ignore[attr-defined]
        type=controller.type,  # type: ignore[attr-defined]
        stage=controller.stage,  # type: ignore[attr-defined]
        joints=controller.joints,  # type: ignore[attr-defined]
        command_interfaces=controller.command_interfaces,  # type: ignore[attr-defined]
        state_interfaces=controller.state_interfaces,  # type: ignore[attr-defined]
        parameters=tuple(
            (key, _yaml_scalar(value))
            for key, value in sorted(controller.parameters.items())  # type: ignore[attr-defined]
        ),
        single_joint_key=controller.type in SINGLE_JOINT_TYPES,  # type: ignore[attr-defined]
        constraints=_constraints_view(controller, asset),
    )


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _controlled(cell: ResolvedCell) -> tuple[ResolvedAsset, ...]:
    return tuple(a for a in cell.assets if a.controllers)


def _control_spec(asset: ResolvedAsset) -> ControlSpec:
    """The controller-manager configuration this asset's type declares.

    Read from the model rather than held as module constants. An update rate is a
    fact about a robot — the vendor ships one — and a constant here would apply
    one arm's rate to every type the generator ever sees, which is the P5
    inversion. Missing is an error rather than a default: silently running a
    manager at a rate nobody chose produces an arm that tracks badly for no
    visible reason, and silently leaving limit enforcement off produces an arm
    whose declared limits are decoration.
    """
    control = asset.asset_type.control
    if control is None:
        raise MissingControlSpecError(
            f"asset {asset.id!r} of type {asset.asset_type.id!r} declares controllers "
            "but no `control:` section, so there is no update rate to run its "
            "controller manager at, and no statement of whether its declared "
            "limits are enforced. Add `control: {update_rate_hz: <hz>, "
            "enforce_command_limits: <bool>}` to the type."
        )
    return control


def generate(cell: ResolvedCell) -> list[Artifact]:
    env = environment()
    template = env.get_template("control/controllers.yaml.j2")
    artifacts: list[Artifact] = []
    for asset in _controlled(cell):
        control = _control_spec(asset)
        text = template.render(
            zone=cell.zone,
            arm=asset,
            namespace=asset.namespace,
            update_rate=control.update_rate_hz,
            enforce_command_limits=_yaml_scalar(control.enforce_command_limits),
            use_sim_time="true" if asset.instance.hardware.backend == "sim" else "false",
            controllers=[_view(c, asset) for c in asset.controllers],
        )
        artifacts.append(Artifact(f"control/{cell.zone}_{asset.id}_controllers.yaml", text))
    return artifacts
