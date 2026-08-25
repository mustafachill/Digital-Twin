"""Read the generated bring-up plan.

Kept apart from the launch file so it can be unit-tested without a ROS runtime.
A launch file is awkward to test; a function that turns YAML into dataclasses is
not, and most of what can go wrong here — a missing controller, a stage out of
order, a package:// URI that does not resolve — is in this half.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory

PACKAGE_URI_PREFIX = "package://"


class PlanError(Exception):
    """The bring-up plan is missing, malformed, or references something absent."""


@dataclass(frozen=True)
class ControllerRef:
    name: str
    stage: int


@dataclass(frozen=True)
class MoveItConfig:
    """Everything move_group needs for one arm, all generated from L0.

    The controller names here and the ones ros2_control was configured with come
    from the same model, which is what stops MoveIt and the controller manager
    from disagreeing about what a controller is called — a mismatch that fails at
    run time with an error naming neither.
    """

    group: str
    base_link: str
    tip_link: str
    home_rad: tuple[float, ...]
    srdf: Path
    kinematics: Path
    ompl: Path
    joint_limits: Path
    controllers: Path


@dataclass(frozen=True)
class ControllerManager:
    asset: str
    node: str
    backend: str
    hosted_by: str
    description_topic: str
    description: Path
    spawn_xyz_m: tuple[float, float, float]
    spawn_rpy_rad: tuple[float, float, float]
    parameters: str
    controllers: tuple[ControllerRef, ...]
    moveit: MoveItConfig | None
    trajectory_action: str | None
    gripper_action: str | None

    def stages(self) -> list[tuple[int, tuple[str, ...]]]:
        """Controllers grouped by stage, in ascending order.

        Stage is a dependency ordering, not a schedule: a broadcaster must be
        active before the controllers that read the state it publishes. The
        launch mechanism spawns one stage at a time and gates each on the
        previous spawner exiting successfully — never on elapsed time (P4).
        """
        grouped: dict[int, list[str]] = {}
        for controller in self.controllers:
            grouped.setdefault(controller.stage, []).append(controller.name)
        return [(stage, tuple(sorted(names))) for stage, names in sorted(grouped.items())]


@dataclass(frozen=True)
class Conveyor:
    asset: str
    state_topic: str
    command_topic: str
    installed_speed_mps: float


@dataclass(frozen=True)
class Sensor:
    asset: str
    detection_topic: str
    beam_axis: str
    beam_length_m: float


@dataclass(frozen=True)
class Plan:
    zone: str
    world: Path
    scene: Path
    static_frames: Path
    topology: Path
    controller_managers: tuple[ControllerManager, ...]
    conveyors: tuple[Conveyor, ...]
    sensors: tuple[Sensor, ...]


def resolve_uri(uri: str) -> Path:
    """Turn a ``package://pkg/rest`` URI into an absolute path.

    Resolved at launch rather than baked into the plan, because the plan is
    committed to git and an absolute path in it would be wrong on every machine
    but the one that generated it.
    """
    if not uri.startswith(PACKAGE_URI_PREFIX):
        return Path(uri)
    remainder = uri[len(PACKAGE_URI_PREFIX) :]
    package, _, relative = remainder.partition("/")
    if not package or not relative:
        raise PlanError(f"malformed package URI: {uri!r}")
    try:
        share = get_package_share_directory(package)
    except Exception as exc:  # noqa: BLE001 - ament raises its own exception type
        raise PlanError(
            f"{uri}: package {package!r} is not on the ament index. "
            "Has the workspace been built and the overlay sourced?"
        ) from exc
    path = Path(share) / relative
    if not path.exists():
        raise PlanError(f"{uri} resolves to {path}, which does not exist")
    return path


def load(path: Path) -> Plan:
    """Load and check a generated bring-up plan."""
    if not path.is_file():
        raise PlanError(
            f"no bring-up plan at {path}. It is generated from the L0 model — "
            "run ./scripts/validate-model --write, then ./scripts/build."
        )
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict) or "plan" not in document:
        raise PlanError(f"{path}: expected a top-level `plan:` mapping")
    plan = document["plan"]

    managers = tuple(
        ControllerManager(
            asset=entry["asset"],
            node=entry["node"],
            backend=entry["backend"],
            hosted_by=entry["hosted_by"],
            description_topic=entry["description_topic"],
            description=resolve_uri(entry["description"]),
            spawn_xyz_m=_triple(entry["spawn_xyz_m"]),
            spawn_rpy_rad=_triple(entry["spawn_rpy_rad"]),
            parameters=entry["parameters"],
            controllers=tuple(
                ControllerRef(name=c["name"], stage=c["stage"]) for c in entry["controllers"]
            ),
            moveit=_moveit(entry.get("moveit")),
            trajectory_action=entry.get("trajectory_action"),
            gripper_action=entry.get("gripper_action"),
        )
        for entry in plan.get("controller_managers") or []
    )

    for manager in managers:
        if not manager.controllers:
            raise PlanError(
                f"controller manager for {manager.asset!r} lists no controllers; "
                "bring-up would report success having activated nothing"
            )

    conveyors = tuple(
        Conveyor(
            asset=entry["asset"],
            state_topic=entry["state_topic"],
            command_topic=entry["command_topic"],
            installed_speed_mps=float(entry["installed_speed_mps"]),
        )
        for entry in plan.get("conveyors") or []
    )

    sensors = tuple(
        Sensor(
            asset=entry["asset"],
            detection_topic=entry["detection_topic"],
            beam_axis=entry["beam_axis"],
            beam_length_m=float(entry["beam_length_m"]),
        )
        for entry in plan.get("sensors") or []
    )

    return Plan(
        zone=plan["zone"],
        world=resolve_uri(plan["world"]),
        scene=resolve_uri(plan["scene"]),
        static_frames=resolve_uri(plan["static_frames"]),
        topology=resolve_uri(plan["topology"]),
        controller_managers=managers,
        conveyors=conveyors,
        sensors=sensors,
    )


def _moveit(entry: dict | None) -> MoveItConfig | None:
    if entry is None:
        return None
    return MoveItConfig(
        group=entry["group"],
        base_link=entry["base_link"],
        tip_link=entry["tip_link"],
        home_rad=tuple(float(v) for v in entry.get("home_rad") or []),
        srdf=resolve_uri(entry["srdf"]),
        kinematics=resolve_uri(entry["kinematics"]),
        ompl=resolve_uri(entry["ompl"]),
        joint_limits=resolve_uri(entry["joint_limits"]),
        controllers=resolve_uri(entry["controllers"]),
    )


def _triple(value: str) -> tuple[float, float, float]:
    parts = str(value).split()
    if len(parts) != 3:
        raise PlanError(f"expected three space-separated numbers, got {value!r}")
    x, y, z = (float(p) for p in parts)
    return (x, y, z)


def default_plan_path(zone: str = "cell_a") -> Path:
    return resolve_uri(f"package://cite_generated/bringup/{zone}_plan.yaml")
