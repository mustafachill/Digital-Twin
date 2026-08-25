# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Read the generated bring-up plan.

Kept apart from the launch file so it can be unit-tested without a ROS runtime.
A launch file is awkward to test; a function that turns YAML into dataclasses is
not, and most of what can go wrong here — a missing controller, a stage out of
order, a package:// URI that does not resolve — is in this half.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
import yaml

PACKAGE_URI_PREFIX = "package://"

#: The one backend that cannot reach a physical machine. Every other value names
#: a `ros2_control` plugin that drives real hardware, so the check below is an
#: allowlist rather than a denylist: a backend nobody anticipated is refused
#: rather than permitted. `cross-cutting-safety.md` requires that a hardware path
#: is never reachable by omission, and a denylist is reachable by omission by
#: construction.
SIMULATION_BACKEND = "sim"

#: The deliberate opt-in. The same variable `scripts/_lib.sh` enforces at the
#: shell boundary, so a person meets one name rather than two — but enforced here
#: as well, because the shell gate only ever guarded `./scripts/enter hardware`
#: and nothing at all inside the ROS graph.
HARDWARE_OPT_IN_ENV = "CITE_ALLOW_HARDWARE"
HARDWARE_OPT_IN_VALUE = "1"


class PlanError(Exception):
    """The bring-up plan is missing, malformed, or references something absent."""


class HardwareNotPermittedError(PlanError):
    """The plan would drive physical hardware and the opt-in was not given.

    A `PlanError`, so the launch file's existing refusal path reports it the same
    way it reports every other reason bring-up cannot proceed: a message and a
    `Shutdown`, never a partially started cell.
    """


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
    gripper_open_position: float
    gripper_closed_position: float
    gripper_max_width_m: float

    def stages(self) -> list[tuple[int, tuple[str, ...]]]:
        """Group the controllers by stage, in ascending order.

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
    if not isinstance(uri, str):
        raise PlanError(f"expected a package:// URI as a string, got {_kind(uri)} ({uri!r})")
    if not uri.startswith(PACKAGE_URI_PREFIX):
        return Path(uri)
    remainder = uri[len(PACKAGE_URI_PREFIX):]
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
    """Load and check a generated bring-up plan.

    Every failure in here is a `PlanError`. That is not tidiness: the launch file
    catches `PlanError` and turns it into ``BRING-UP FAILED: <reason>`` plus a
    `Shutdown`, so anything escaping as a bare `KeyError` or `ValueError` instead
    surfaces as a traceback out of an `OpaqueFunction` — which names the launch
    machinery rather than the key that is missing from the plan.
    """
    if not path.is_file():
        raise PlanError(
            f"no bring-up plan at {path}. It is generated from the L0 model — "
            "run ./scripts/validate-model --write, then ./scripts/build."
        )
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict) or "plan" not in document:
        raise PlanError(f"{path}: expected a top-level `plan:` mapping")
    plan = document["plan"]
    if not isinstance(plan, dict):
        raise PlanError(f"{path}: `plan:` must be a mapping, not {_kind(plan)}")

    managers = tuple(
        _manager(entry, index)
        for index, entry in enumerate(_sequence(plan, "controller_managers"))
    )

    for manager in managers:
        if not manager.controllers:
            raise PlanError(
                f"controller manager for {manager.asset!r} lists no controllers; "
                "bring-up would report success having activated nothing"
            )

    conveyors = tuple(
        Conveyor(
            asset=_require(entry, "asset", f"conveyor {index}"),
            state_topic=_require(entry, "state_topic", f"conveyor {index}"),
            command_topic=_require(entry, "command_topic", f"conveyor {index}"),
            installed_speed_mps=_number(
                _require(entry, "installed_speed_mps", f"conveyor {index}"),
                "installed_speed_mps",
                f"conveyor {index}",
            ),
        )
        for index, entry in enumerate(_sequence(plan, "conveyors"))
    )

    sensors = tuple(
        Sensor(
            asset=_require(entry, "asset", f"sensor {index}"),
            detection_topic=_require(entry, "detection_topic", f"sensor {index}"),
            beam_axis=_require(entry, "beam_axis", f"sensor {index}"),
            beam_length_m=_number(
                _require(entry, "beam_length_m", f"sensor {index}"),
                "beam_length_m",
                f"sensor {index}",
            ),
        )
        for index, entry in enumerate(_sequence(plan, "sensors"))
    )

    return Plan(
        zone=_require(plan, "zone", "plan"),
        world=resolve_uri(_require(plan, "world", "plan")),
        scene=resolve_uri(_require(plan, "scene", "plan")),
        static_frames=resolve_uri(_require(plan, "static_frames", "plan")),
        topology=resolve_uri(_require(plan, "topology", "plan")),
        controller_managers=managers,
        conveyors=conveyors,
        sensors=sensors,
    )


def require_hardware_opt_in(plan: Plan, environ: Mapping[str, str]) -> None:
    """Refuse a plan that would drive physical hardware without a deliberate opt-in.

    `cross-cutting-safety.md` requires that no command reaches a hardware
    interface without passing the safety layer. Until Phase 2 builds that layer,
    the only enforceable form of the rule is that bring-up refuses to start at
    all — and refusing is the right shape, because it does not change *what* is
    commanded on either path (P2). A `real` backend that does start behaves
    identically to the simulated one; it simply may not start by accident.

    The equivalent shell check, `require_explicit_hardware_opt_in` in
    `scripts/_lib.sh`, guards `./scripts/enter hardware` and nothing else. Every
    other route into the ROS graph — a launch file run directly, a scenario, CI,
    an editor — arrives here instead, which is why the check lives at this
    boundary rather than only in a script.

    ``environ`` is passed in rather than read from `os` here, so that the refusal
    can be tested without mutating the process that tests it.
    """
    hardware = tuple(m for m in plan.controller_managers if m.backend != SIMULATION_BACKEND)
    if not hardware:
        return
    if environ.get(HARDWARE_OPT_IN_ENV) == HARDWARE_OPT_IN_VALUE:
        return

    named = ", ".join(
        f"{m.asset} (backend {m.backend!r})" for m in sorted(hardware, key=lambda m: m.asset)
    )
    raise HardwareNotPermittedError(
        f"zone {plan.zone!r} declares a hardware backend for {named}, and "
        f"{HARDWARE_OPT_IN_ENV} is not set to {HARDWARE_OPT_IN_VALUE}. Starting "
        "would command a physical machine. Confirm the cell is clear, then set "
        f"{HARDWARE_OPT_IN_ENV}={HARDWARE_OPT_IN_VALUE} deliberately — see "
        "docs/operations/safety-procedures.md."
    )


def _manager(entry: object, index: int) -> ControllerManager:
    where = f"controller manager {index}"
    asset = _require(entry, "asset", where)
    where = f"controller manager {asset!r}"
    return ControllerManager(
        asset=asset,
        node=_require(entry, "node", where),
        backend=_require(entry, "backend", where),
        hosted_by=_require(entry, "hosted_by", where),
        description_topic=_require(entry, "description_topic", where),
        description=resolve_uri(_require(entry, "description", where)),
        spawn_xyz_m=_triple(_require(entry, "spawn_xyz_m", where), "spawn_xyz_m", where),
        spawn_rpy_rad=_triple(_require(entry, "spawn_rpy_rad", where), "spawn_rpy_rad", where),
        parameters=_require(entry, "parameters", where),
        controllers=tuple(
            ControllerRef(
                name=_require(controller, "name", f"{where}, controller {position}"),
                stage=int(
                    _number(
                        _require(controller, "stage", f"{where}, controller {position}"),
                        "stage",
                        where,
                    )
                ),
            )
            for position, controller in enumerate(_sequence(entry, "controllers", where))
        ),
        moveit=_moveit(_optional(entry, "moveit"), where),
        trajectory_action=_optional(entry, "trajectory_action"),
        gripper_action=_optional(entry, "gripper_action"),
        gripper_open_position=_number(
            _optional(entry, "gripper_open_position", 0.0), "gripper_open_position", where
        ),
        gripper_closed_position=_number(
            _optional(entry, "gripper_closed_position", 0.0), "gripper_closed_position", where
        ),
        gripper_max_width_m=_number(
            _optional(entry, "gripper_max_width_m", 0.0), "gripper_max_width_m", where
        ),
    )


def _moveit(entry: object | None, where: str = "plan") -> MoveItConfig | None:
    if entry is None:
        return None
    where = f"{where}, moveit"
    return MoveItConfig(
        group=_require(entry, "group", where),
        base_link=_require(entry, "base_link", where),
        tip_link=_require(entry, "tip_link", where),
        home_rad=tuple(
            _number(value, f"home_rad[{position}]", where)
            for position, value in enumerate(_sequence(entry, "home_rad", where))
        ),
        srdf=resolve_uri(_require(entry, "srdf", where)),
        kinematics=resolve_uri(_require(entry, "kinematics", where)),
        ompl=resolve_uri(_require(entry, "ompl", where)),
        joint_limits=resolve_uri(_require(entry, "joint_limits", where)),
        controllers=resolve_uri(_require(entry, "controllers", where)),
    )


def _kind(value: object) -> str:
    """Name a YAML value's shape in the words the plan is written in."""
    return {dict: "a mapping", list: "a list", type(None): "empty"}.get(
        type(value), f"a {type(value).__name__}"
    )


def _require(entry: object, key: str, where: str) -> object:
    if not isinstance(entry, dict):
        raise PlanError(f"{where}: expected a mapping, got {_kind(entry)}")
    if key not in entry:
        raise PlanError(f"{where}: missing required key {key!r}")
    value = entry[key]
    if value is None:
        raise PlanError(f"{where}: {key!r} is empty")
    return value


def _optional(entry: object, key: str, default: object | None = None) -> object | None:
    if not isinstance(entry, dict):
        raise PlanError(f"expected a mapping, got {_kind(entry)}")
    value = entry.get(key, default)
    return default if value is None else value


def _sequence(entry: object, key: str, where: str = "plan") -> list:
    if not isinstance(entry, dict):
        raise PlanError(f"{where}: expected a mapping, got {_kind(entry)}")
    value = entry.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise PlanError(f"{where}: {key!r} must be a list, not {_kind(value)}")
    return value


def _number(value: object, key: str, where: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{where}: {key!r} must be a number, got {value!r}") from exc


def _triple(value: object, key: str, where: str) -> tuple[float, float, float]:
    if not isinstance(value, str):
        raise PlanError(
            f"{where}: {key!r} must be three space-separated numbers in a string, "
            f"got {_kind(value)} ({value!r})"
        )
    parts = value.split()
    if len(parts) != 3:
        raise PlanError(
            f"{where}: {key!r} must be three space-separated numbers, got {value!r}"
        )
    x, y, z = (_number(part, key, where) for part in parts)
    return (x, y, z)


def default_plan_path(zone: str = "cell_a") -> Path:
    return resolve_uri(f"package://cite_generated/bringup/{zone}_plan.yaml")
