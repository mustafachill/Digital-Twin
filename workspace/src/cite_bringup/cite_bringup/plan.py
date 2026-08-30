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

#: The Gazebo transport partition, as gz-transport itself reads it. Every process
#: that speaks that transport — `gz sim`, `parameter_bridge`, `ros_gz_sim create`
#: — must be started with this set to the value the plan names for its side.
#:
#: `ROS_DOMAIN_ID` does not isolate Gazebo transport and this variable is what
#: does (ADR-0042). What isolated the pairs that have been measured was the
#: container hostname, which gz-transport derives its default from — an accident
#: of one deployment that evaporates the moment two sides share a container.
GZ_PARTITION_ENV = "GZ_PARTITION"


class PlanError(Exception):
    """The bring-up plan is missing, malformed, or references something absent."""


class HardwareNotPermittedError(PlanError):
    """The plan would drive physical hardware and the opt-in was not given.

    A `PlanError`, so the launch file's existing refusal path reports it the same
    way it reports every other reason bring-up cannot proceed: a message and a
    `Shutdown`, never a partially started cell.
    """


class GazeboPartitionMissingError(PlanError):
    """A side is about to start Gazebo processes without its declared partition.

    A `PlanError` for the same reason `HardwareNotPermittedError` is, and a
    refusal rather than a warning for a sharper one: what it guards against
    produces no symptom. Two servers sharing a partition connect silently and one
    belt setpoint drives both cells, with nothing logged at either end. A warning
    about that would be read once and then never again (ADR-0042).
    """


@dataclass(frozen=True)
class ControllerRef:
    name: str
    stage: int


@dataclass(frozen=True)
class Side:
    """One side of the zone, and the Gazebo transport partition it runs in.

    An untwinned zone still has a side, and it is still named and still
    partitioned. A partition that appeared only when someone paired a cell would
    be untested on every run that does not, which is the arrangement ADR-0042
    rejected — the isolation was already working by accident, and an accident
    that only fails under the configuration nobody has run yet is the worst kind.
    """

    name: str
    gz_partition: str


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
    planning_pipelines: Path
    joint_limits: Path
    cartesian_limits: Path
    controllers: Path
    #: Which pipeline the skill server asks first, and what a refusal falls back
    #: to (ADR-0027). Carried here rather than compiled into the server, and
    #: under the server's own parameter names, so that no list anywhere maps one
    #: to the other and goes stale.
    default_pipeline: str
    default_planner_id: str
    fallback_pipeline: str
    fallback_planner_id: str
    #: Which of those planner ids define the SHAPE of a path rather than only its
    #: endpoints, so that the skill server can refuse to have such a request
    #: rescued by a planner that samples (ADR-0027).
    cartesian_planner_ids: tuple[str, ...]


@dataclass(frozen=True)
class SkillActions:
    """The action names one arm's L3 skill server advertises.

    Generated, never assembled. Every one of these is `/cite/<zone>/<asset>/...`,
    and an asset name written into a launch file or a parameter by hand is a
    second place that name is made — the failure CLAUDE.md §8 names.
    """

    move_to: str
    pick: str
    place: str
    grasp: str
    transfer: str


#: Every gripper key the plan carries, under the exact name the skill server
#: declares it.
#:
#: One list, because the two names are the same name. `cite_bringup` used to
#: pass four of these by hand, one of which (`gripper_max_width_m`) exists in
#: neither the plan nor the server's declared parameters and was therefore
#: silently dropped, while `gripper_default_grasp_width_m`, the two rate and
#: tolerance keys and all seven linkage dimensions never arrived at all. The node
#: ran on its compiled defaults, which happen to equal the L0 values — so it
#: worked, and it worked only because two copies agreed. Reading the plan through
#: this list keeps the number of statements at one: a key here reaches L3
#: verbatim, and a key that reaches L3 came from the model.
GRIPPER_KEYS = (
    "gripper_open_position",
    "gripper_closed_position",
    "gripper_default_grasp_width_m",
    "gripper_goal_tolerance_rad",
    "gripper_max_drive_rate_rad_s",
    "gripper_result_timeout_s",
    "gripper_drive_pivot_y_m",
    "gripper_drive_pivot_z_m",
    "gripper_finger_offset_y_m",
    "gripper_finger_offset_z_m",
    "gripper_pad_inset_m",
    "gripper_tip_link_z_m",
    "gripper_pad_face_centre_z_m",
)

#: Every ARM key the plan carries, under the exact name the skill server declares
#: it. Same mechanism as `GRIPPER_KEYS`, kept as a separate tuple because these
#: describe the arm's trajectory controller and not the end-effector, and one
#: tuple named for the gripper carrying an arm's tolerance is how a name stops
#: meaning anything.
#:
#: `arm_goal_tolerance_rad` is the L0 `constraints:` block's goal tolerance
#: (ADR-0036), delivered to L3 because ADR-0037 classifies a failed execution by
#: comparing the arm against the plan's endpoints and must use the same threshold
#: the controller itself checks against rather than a second copy of it (P1).
ARM_KEYS = ("arm_goal_tolerance_rad",)


@dataclass(frozen=True)
class ControllerManager:
    asset: str
    node: str
    backend: str
    #: What the counterpart side of this asset loads, or `None` where the zone
    #: has no counterpart. The plan states it only on a paired zone, and states
    #: it for every asset there, so `None` means "there is no such side" and
    #: never "the model left the key out" (ADR-0041, Decision 3).
    counterpart_backend: str | None
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
    skills: SkillActions | None
    #: Keyed by the names in `GRIPPER_KEYS`, which are the skill server's own
    #: parameter names. Held as a mapping rather than as a dozen fields so that
    #: delivering them cannot drift from declaring them: the launch file passes
    #: this dictionary through, and a key it does not know about is impossible.
    gripper: Mapping[str, float]
    #: Keyed by the names in `ARM_KEYS`, delivered by the same route and for the
    #: same reason as `gripper` above.
    arm: Mapping[str, float]

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
    """One break beam: where its level arrives, and where its events go.

    `level_topic` and `detection_topic` are two interfaces, not two names for
    one. The level is a state the beam republishes periodically; the event is
    the edge L3 makes from it, and the process topology already gives
    `detection_topic` to a station as a `DetectionEvent` trigger. Bridging the
    raw `std_msgs/Bool` onto that name would put a second publisher of a second
    type on the topic the line acts on.
    """

    asset: str
    detection_topic: str
    level_topic: str
    frame_id: str
    beam_axis: str
    beam_length_m: float


@dataclass(frozen=True)
class Detection:
    """Where the zone's single detection server runs, and what it advertises.

    One per zone. A break beam watches a belt rather than a robot, so three
    servers would give the question "did the piece pass beam 2" three answers.
    """

    namespace: str
    detect_action: str


@dataclass(frozen=True)
class Plan:
    zone: str
    world: Path
    scene: Path
    static_frames: Path
    topology: Path
    #: Every side this zone runs, in the order the generator emitted them, the
    #: first of which is always the plant. Never empty — `load` refuses a plan
    #: with no sides rather than defaulting one, because a defaulted partition is
    #: the thing ADR-0042 forbids.
    sides: tuple[Side, ...]
    controller_managers: tuple[ControllerManager, ...]
    conveyors: tuple[Conveyor, ...]
    sensors: tuple[Sensor, ...]
    #: `None` when the zone declares no sensors, which is a real state and not a
    #: fault: a cell with no beams has nothing for a detection server to watch,
    #: and starting one would advertise `detect` over an empty sensor table.
    detection: Detection | None


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

    sides = _sides(plan, path)

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
            level_topic=_require(entry, "level_topic", f"sensor {index}"),
            frame_id=_require(entry, "frame_id", f"sensor {index}"),
            beam_axis=_require(entry, "beam_axis", f"sensor {index}"),
            beam_length_m=_number(
                _require(entry, "beam_length_m", f"sensor {index}"),
                "beam_length_m",
                f"sensor {index}",
            ),
        )
        for index, entry in enumerate(_sequence(plan, "sensors"))
    )

    for sensor in sensors:
        if sensor.level_topic == sensor.detection_topic:
            raise PlanError(
                f"sensor {sensor.asset!r} names one topic for both its raw level and its "
                f"typed events ({sensor.detection_topic}). The bridge would publish a "
                "std_msgs/Bool on the topic a station subscribes to for DetectionEvent, "
                "and the two would fight over it."
            )

    detection = _detection(_optional(plan, "detection"))
    if sensors and detection is None:
        raise PlanError(
            f"zone {_require(plan, 'zone', 'plan')!r} declares {len(sensors)} sensor(s) and "
            "no `detection:` block, so nothing says where the server that turns their "
            "levels into typed events runs. The beams would be bridged into ROS and "
            "read by nobody."
        )

    return Plan(
        zone=_require(plan, "zone", "plan"),
        world=resolve_uri(_require(plan, "world", "plan")),
        scene=resolve_uri(_require(plan, "scene", "plan")),
        static_frames=resolve_uri(_require(plan, "static_frames", "plan")),
        topology=resolve_uri(_require(plan, "topology", "plan")),
        sides=sides,
        controller_managers=managers,
        conveyors=conveyors,
        sensors=sensors,
        detection=detection,
    )


def _sides(plan: object, path: Path) -> tuple[Side, ...]:
    """Read the zone's sides, refusing anything that would leave one unpartitioned.

    Three refusals, and each names a way the isolation could be lost silently
    rather than a way the file could be untidy:

    * **no sides at all** — a plan generated before ADR-0042, or one hand-edited
      to remove the block. Defaulting a partition here would put the derivation
      in two places, which is the failure the emission exists to prevent;
    * **an empty partition** — a side that would fall back to gz-transport's own
      `<HOSTNAME>:<USERNAME>` default, which is exactly the accident the decision
      replaced;
    * **two sides sharing one partition** — the measured defect itself, written
      down: two servers on one partition see each other's topics, and one belt
      command starts both cells' belts.
    """
    entries = _sequence(plan, "sides")
    sides = tuple(
        Side(
            name=str(_require(entry, "name", f"side {index}")),
            gz_partition=str(_require(entry, "gz_partition", f"side {index}")),
        )
        for index, entry in enumerate(entries)
    )
    if not sides:
        raise GazeboPartitionMissingError(
            f"{path}: the plan declares no `sides:`, so nothing says which Gazebo "
            "transport partition this zone runs in. ROS_DOMAIN_ID does not isolate "
            "Gazebo transport (ADR-0042), and the partition is generated from L0 — "
            "run ./scripts/validate-model --write, then ./scripts/build."
        )
    for side in sides:
        if not side.gz_partition.strip():
            raise GazeboPartitionMissingError(
                f"{path}: side {side.name!r} names an empty gz_partition. An unset "
                "partition falls back to gz-transport's <HOSTNAME>:<USERNAME> default, "
                "which is the deployment accident ADR-0042 replaced."
            )
    partitions = [s.gz_partition for s in sides]
    if len(set(partitions)) != len(partitions):
        shared = sorted({p for p in partitions if partitions.count(p) > 1})
        raise GazeboPartitionMissingError(
            f"{path}: sides share the Gazebo partition(s) {', '.join(shared)}. Two "
            "servers on one partition subscribe to each other's topics, so one belt "
            "setpoint would start both cells' belts with nothing logged."
        )
    return sides


def require_gz_partition(side: Side, environ: Mapping[str, str]) -> None:
    """Refuse to start a side whose process environment lacks its own partition.

    ``environ`` is the environment the caller is about to hand to the Gazebo
    processes, not the launching shell's. That is the sharper question, and it is
    the one that catches the failure that actually happens: a stale generated
    tree is caught earlier by `./scripts/validate-model`, while this catches the
    launch path that dropped the value on its way into the process (ADR-0042).

    A refusal rather than a warning, and never a default. What a missing
    partition produces is not an error but silence — two cells that discover each
    other's topics and act on each other's commands, with every ROS-side
    instrument this project has reporting clean isolation at the same moment.
    """
    carried = environ.get(GZ_PARTITION_ENV)
    if carried == side.gz_partition:
        return
    if carried is None:
        raise GazeboPartitionMissingError(
            f"side {side.name!r} would start its Gazebo processes with no "
            f"{GZ_PARTITION_ENV}. The plan names {side.gz_partition!r}; without it "
            "gz-transport falls back to <HOSTNAME>:<USERNAME>, and two sides sharing a "
            "container then share every Gazebo topic silently (ADR-0042)."
        )
    raise GazeboPartitionMissingError(
        f"side {side.name!r} would start its Gazebo processes with "
        f"{GZ_PARTITION_ENV}={carried!r}, but the plan names {side.gz_partition!r}. "
        "The partition is generated from L0 and is the one name that decides which "
        "cell a belt command reaches; it may not be overridden per run."
    )


def _detection(entry: object | None) -> Detection | None:
    if entry is None:
        return None
    return Detection(
        namespace=_require(entry, "namespace", "detection"),
        detect_action=_require(entry, "detect_action", "detection"),
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

    EVERY SIDE, not only the plant. A backend is selected per (asset, side), so a
    twinned zone can name a physical machine on its counterpart while its plant
    stays simulated — which is exactly what Phase 2.B is (ADR-0041, Decision 3),
    and what `MODE_VIRTUAL_LEAD` describes. Reading only `backend` here would let
    the far side become physical behind a gate that never looked at it. The
    reverse case — a physical plant on a paired zone — cannot reach this
    function: the L0 validator refuses to generate a plan that names one.
    """
    # Keyed by the plan field the value came from rather than by a side name:
    # which side `counterpart_backend` describes is stated once, in the plan's
    # own `sides:` block and in L0 behind it, and repeating it here would be a
    # third place the pair of names lives.
    hardware = tuple(
        (manager, field, backend)
        for manager in plan.controller_managers
        for field, backend in (
            ("backend", manager.backend),
            ("counterpart_backend", manager.counterpart_backend),
        )
        if backend is not None and backend != SIMULATION_BACKEND
    )
    if not hardware:
        return
    if environ.get(HARDWARE_OPT_IN_ENV) == HARDWARE_OPT_IN_VALUE:
        return

    named = ", ".join(
        f"{manager.asset} ({field} {backend!r})"
        for manager, field, backend in sorted(hardware, key=lambda row: (row[0].asset, row[1]))
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
        counterpart_backend=_optional(entry, "counterpart_backend"),
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
        skills=_skills(_optional(entry, "skills"), where),
        gripper=_named_numbers(entry, GRIPPER_KEYS, where),
        arm=_named_numbers(entry, ARM_KEYS, where),
    )


def _skills(entry: object | None, where: str) -> SkillActions | None:
    """Read the arm's L3 action names, or None when the plan declares none.

    None is a real state: a plan may describe an asset with controllers and no
    planning group, and `cite_bringup` starts no skill server for it. What must
    never happen is a launch file inventing the names instead, which is why
    there is no default here.
    """
    if entry is None:
        return None
    where = f"{where}, skills"
    return SkillActions(
        **{name: _require(entry, name, where) for name in ("move_to", "pick", "place",
                                                           "grasp", "transfer")}
    )


def _named_numbers(
    entry: object, keys: tuple[str, ...], where: str
) -> Mapping[str, float]:
    """Read the values the plan carries for `keys`, under L3's own parameter names.

    A key the plan omits is omitted here rather than defaulted to zero. That is
    the whole point: the skill server declares its own defaults and says why, and
    a zero manufactured here would override them with a number the model never
    stated — which is exactly how `gripper_max_width_m` came to be delivered
    while eleven real values were not.
    """
    if not isinstance(entry, dict):
        raise PlanError(f"{where}: expected a mapping, got {_kind(entry)}")
    return {
        key: _number(entry[key], key, where)
        for key in keys
        if entry.get(key) is not None
    }


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
        planning_pipelines=resolve_uri(_require(entry, "planning_pipelines", where)),
        joint_limits=resolve_uri(_require(entry, "joint_limits", where)),
        cartesian_limits=resolve_uri(_require(entry, "cartesian_limits", where)),
        controllers=resolve_uri(_require(entry, "controllers", where)),
        default_pipeline=str(_require(entry, "default_pipeline", where)),
        default_planner_id=str(_require(entry, "default_planner_id", where)),
        fallback_pipeline=str(_require(entry, "fallback_pipeline", where)),
        # The only one of the four that may legitimately be empty: an empty
        # planner id means "whatever that pipeline defaults to", so it is read
        # with a default rather than required, and `_require` would reject it.
        fallback_planner_id=str(_optional(entry, "fallback_planner_id") or ""),
        # May legitimately be empty — a cell whose pipelines register no
        # Cartesian planner has nothing to list — so it is read with a default.
        cartesian_planner_ids=tuple(
            str(value) for value in (_optional(entry, "cartesian_planner_ids") or [])
        ),
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
