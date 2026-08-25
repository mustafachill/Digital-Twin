"""The single declaration of the L0 facility model's shape.

Pydantic is authoritative here; the JSON Schema under ``model/schema/`` is a
*generated export* of these classes (ADR-0021), not a second declaration. That is
what keeps the shape from existing in two places, which is the failure this whole
layer exists to prevent.

The rule for what belongs here, and what does not:

* Anything pydantic can declare on a field — type, enum, pattern, range,
  required, extra-forbid — is declared here, so it survives the export and gives
  editors inline validation.
* Anything it cannot — referential integrity, geometry, inertia plausibility,
  determinism — is **not** a schema constraint. It lives in ``cite_tools.validate``
  and the exported JSON Schema never claims it.

``extra="forbid"`` on every model is the single most important line in the file.
It is what makes a mistyped key an error instead of a silent default — v1 read
``conveyor`` while the file said ``conveyors``, the configuration fell back to
defaults, and nothing anywhere reported it.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# `lower_snake_case`, no leading digit — naming-and-namespaces.md rule 4.
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]

#: ``cite_world``, or ``<asset_id>/<frame_id>`` naming a frame on another asset.
FrameRef = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)?$")]

Triple = tuple[float, float, float]


class Strict(BaseModel):
    """Base for every model: unknown keys are errors, instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
class Pose(Strict):
    """Where something is, relative to exactly one named frame.

    There is one pose per asset instance. Task poses — where an arm picks, where
    it places — are never written here; they are named frames on assets, which a
    station references. That is what makes v1's duplicated-and-diverged
    pick/place coordinates unrepresentable.
    """

    frame: FrameRef = "cite_world"
    xyz_m: Triple = (0.0, 0.0, 0.0)
    rpy_rad: Triple = (0.0, 0.0, 0.0)


class NamedFrame(Strict):
    """A reference frame a type offers, that instances can be placed against.

    ``conveyor_1/outfeed`` resolves through one of these, so the coordinate of a
    belt's end is written once — in the type — rather than at every station that
    reaches for it.
    """

    id: Identifier
    xyz_m: Triple = (0.0, 0.0, 0.0)
    rpy_rad: Triple = (0.0, 0.0, 0.0)
    link: str | None = Field(
        default=None,
        description="URDF link this frame is attached to, if the type has a description.",
    )


class Inertial(Strict):
    """Mass properties. Validated, never trusted — see L1.

    A wrong inertia tensor raises no error. The simulation runs and the physics
    is wrong in a way that reads as a controller bug, which is why
    ``cite_tools.validate.physical`` checks positive-definiteness and the
    triangle inequality rather than assuming the author got it right.
    """

    mass_kg: Annotated[float, Field(gt=0.0)]
    #: Centre of mass, relative to the CENTRE of the collision geometry — not to
    #: the body's pose, which names the point it stands on. The two references
    #: differ by half a height and the model used to disagree with itself about
    #: which it meant: `validate.physical._com_inside_geometry` read it as
    #: centre-relative while the scene template emitted it as pose-relative, so
    #: `com_m: [0, 0, -0.25]` on a 0.6 m pedestal passed validation and placed
    #: the mass below the floor. Everything now reads it as centre-relative, and
    #: the tensor that accompanies it is centroidal.
    com_m: Triple = (0.0, 0.0, 0.0)
    ixx: Annotated[float, Field(gt=0.0)]
    iyy: Annotated[float, Field(gt=0.0)]
    izz: Annotated[float, Field(gt=0.0)]
    ixy: float = 0.0
    ixz: float = 0.0
    iyz: float = 0.0


class BoxGeometry(Strict):
    kind: Literal["box"] = "box"
    size_m: Triple


class CylinderGeometry(Strict):
    kind: Literal["cylinder"] = "cylinder"
    radius_m: Annotated[float, Field(gt=0.0)]
    length_m: Annotated[float, Field(gt=0.0)]


class MeshGeometry(Strict):
    kind: Literal["mesh"] = "mesh"
    uri: str = Field(description="package:// or file:// URI, declared in assets/manifest.yaml")
    scale: Triple = (1.0, 1.0, 1.0)


Geometry = Annotated[
    BoxGeometry | CylinderGeometry | MeshGeometry,
    Field(discriminator="kind"),
]


class Body(Strict):
    """Geometry for a part we author ourselves — a conveyor, a table, a pedestal.

    Visual and collision are separate fields with no default linking them,
    deliberately. L1 calls reusing a dense visual mesh as collision geometry the
    single most consequential mistake in that layer: it destroys real-time factor
    and produces contact behaviour nobody can explain. Making them separate
    required fields means doing it is a visible choice, not an omission.
    """

    visual: Geometry
    collision: Geometry
    inertial: Inertial
    material: str | None = None


# --------------------------------------------------------------------------- #
# Component library — the declarative half (L1 owns the geometric half)
# --------------------------------------------------------------------------- #
class Kinematics(Strict):
    dof: Annotated[int, Field(ge=1, le=7)]
    joint_suffixes: list[str] = Field(min_length=1)
    base_link_suffix: str
    tip_link_suffix: str
    max_reach_m: Annotated[float, Field(gt=0.0)]


class DescriptionSpec(Strict):
    """How a type becomes geometry.

    ``xacro_macro`` is how a vendor description is incorporated **without editing
    it** — the open question L1 leaves for the component library. The generator's
    entire knowledge of the vendor package is the argument names below, which are
    model data. It never opens a vendor file and never patches one, so a vendor
    upgrade that renames a parameter is a two-line model diff.
    """

    provider: Literal["xacro_macro", "body"]
    package: str | None = None
    file: str | None = None
    macro: str | None = None
    fixed_args: dict[str, str | bool | int | float] = Field(default_factory=dict)
    bound_args: dict[str, str] = Field(
        default_factory=dict,
        description="macro parameter -> generator binding name; an unknown binding is an error",
    )
    body: Body | None = None


class HardwareBackend(Strict):
    """One selectable ``ros2_control`` backend for a type.

    The plugin class string exists exactly once, here. That is what makes
    'the only thing that differs is which plugin is loaded' (ADR-0005) true by
    construction rather than by discipline.
    """

    ros2_control_plugin: str
    instance_params: list[str] = Field(default_factory=list)


class ControlSpec(Strict):
    """How the `ros2_control` manager for this type is configured.

    The update rate is a fact about the robot — the vendor ships one — and it
    used to be a module constant in the generator, applied identically to every
    type. P5 puts it here instead: code encodes how a controller manager is
    configured, never which rate a particular arm runs at.
    """

    update_rate_hz: Annotated[int, Field(gt=0)]


class ControllerSpec(Strict):
    """A controller a type needs, named by suffix and ordered by stage.

    ``stage`` exists because a broadcaster must be active before the controllers
    that depend on its state, and expressing that as data rather than as a sleep
    is what P4 requires.
    """

    suffix: Identifier
    type: str
    joints: Literal["arm", "end_effector", "none"]
    stage: Annotated[int, Field(ge=0)]
    command_interfaces: list[str] = Field(default_factory=list)
    state_interfaces: list[str] = Field(default_factory=list)
    parameters: dict[str, str | bool | int | float] = Field(default_factory=dict)


class GraspSpec(Strict):
    """How the simulated grasp plugin recognises a grasp on this end effector.

    Declared here rather than hardcoded in the plugin: an end effector with
    different link names is a data change, and a plugin that guessed a link name
    would be a second place a name is made (P1). ADR-0023 requires these to come
    from the model for exactly that reason.
    """

    attach_link_suffix: str
    drive_joint_suffix: str
    #: The xArm gripper's drive joint opens towards zero and closes towards its
    #: upper limit, so "closed" is the LARGER value. The gap between the two is
    #: hysteresis — with a single threshold the object drops and re-attaches
    #: repeatedly while the gripper rests near it.
    closed_threshold_rad: Annotated[float, Field(gt=0.0)] = 0.30
    open_threshold_rad: Annotated[float, Field(ge=0.0)] = 0.15
    #: The drive joint's own units at each end of its travel, and the opening
    #: those correspond to.
    #:
    #: `GripperCommand.position` is passed straight through to the joint, so for
    #: this gripper it is an ANGLE, not a width. A skill that sent metres would
    #: command a nearly-closed gripper when it meant fully open — and nothing
    #: would report it, because 0.085 is a perfectly valid angle. Keeping the
    #: mapping here lets the Grasp action stay in task terms (ADR-0022) while the
    #: robot-specific numbers stay in the model.
    open_position: float = 0.0
    closed_position: float = 0.85
    max_width_m: Annotated[float, Field(gt=0.0)] = 0.085


class PlanningSpec(Strict):
    """How this type is planned for, and where its SRDF comes from.

    Group names are the vendor's, prefixed with the asset id exactly as joints
    and controllers are — so `arm_1` plans with group `arm_1_xarm5`. Recording
    the vendor's suffix here rather than hardcoding it keeps the same property
    the description has: a vendor rename is a model edit.
    """

    group_suffix: str
    end_effector_group_suffix: str | None = None
    tip_link_suffix: str
    #: The vendor SRDF macro, invoked with our prefix rather than copied. It
    #: carries the self-collision matrix, which is a property of the vendor's
    #: geometry and not of our facility — re-deriving it here would be inventing
    #: an answer the vendor already has.
    srdf_package: str | None = None
    srdf_file: str | None = None
    srdf_macro: str | None = None
    srdf_args: dict[str, str | bool | int | float] = Field(default_factory=dict)
    #: Kinematics solver, and the planning-time limits MoveIt applies.
    kinematics_plugin: str = "kdl_kinematics_plugin/KDLKinematicsPlugin"
    kinematics_resolution: float = 0.005
    kinematics_timeout_s: float = 0.05
    max_velocity_scaling: float = 0.5
    max_acceleration_scaling: float = 0.5
    #: Joint acceleration ceiling in rad/s^2, applied at planning time. Required
    #: with no default: a vendor description that carries no acceleration limit
    #: leaves MoveIt's time parameterisation without one, and a default here
    #: would silently apply one arm's ceiling to a different robot.
    max_acceleration_rad_s2: Annotated[float, Field(gt=0.0)]


class AssetType(Strict):
    """A reusable definition, instantiated many times with different prefixes."""

    id: Identifier
    category: Literal["robot", "end_effector", "conveyor", "sensor", "fixture"]
    vendor: str | None = None
    kinematics: Kinematics | None = None
    frames: list[NamedFrame] = Field(default_factory=list)
    description: DescriptionSpec
    hardware_backends: dict[Identifier, HardwareBackend] = Field(default_factory=dict)
    control: ControlSpec | None = None
    controllers: list[ControllerSpec] = Field(default_factory=list)
    planning: PlanningSpec | None = None
    grasp: GraspSpec | None = None


# --------------------------------------------------------------------------- #
# Instances
# --------------------------------------------------------------------------- #
class Registration(Strict):
    """What calibration measured, kept apart from what was designed.

    L5 writes here, never into ``pose``. Keeping them separate means a Phase 2
    measurement can never destroy engineered intent, and ``git diff`` shows
    exactly what calibration changed. ``correction`` is a **body-frame** delta
    (ADR-0020), which is what a touch probe or an ICP fit naturally produces.
    """

    status: Literal["unregistered", "measured", "stale"] = "unregistered"
    correction: Pose = Field(default_factory=Pose)
    measured_at: str | None = None
    method: Literal["survey", "tcp_touch_probe", "scan_icp"] | None = None
    residual_rms_m: float | None = None
    survey_reference: str | None = None


class HardwareSelection(Strict):
    """Which backend this instance loads. Required, with no default, on purpose.

    A schema default here would let an instance become ``real`` because someone
    omitted a key. `cross-cutting-safety.md` is explicit that a mode must never
    be reachable by omission, and this is the field that decides whether a
    command reaches a physical arm.
    """

    backend: Identifier
    params: dict[str, str | bool | int | float] = Field(default_factory=dict)


class EndEffectorSelection(Strict):
    type: Identifier
    vendor_integrated: bool = Field(
        default=False,
        description="True when the robot type's own description already builds it in.",
    )


class ConveyorConfiguration(Strict):
    kind: Literal["conveyor"] = "conveyor"
    installed_speed_mps: Annotated[float, Field(gt=0.0)]
    direction: Literal["forward", "reverse"] = "forward"
    #: How far above the belt's working surface a part still counts as resting
    #: on it, and is therefore carried.
    #:
    #: An engineering floor, not a derived value, and the same floor the beam
    #: heights are: L0 describes no work-piece geometry — `Facility.workpiece_models`
    #: holds names and nothing else — so there is no model fact to compute the
    #: right headroom from. 0.100 m clears the 50 mm box the scenario uses while
    #: staying well below the 0.12 m an arm retreats to after a pick, so a part
    #: that has been lifted is released rather than fought over. It becomes
    #: derivable the day a work-piece carries a height.
    carry_height_m: Annotated[float, Field(gt=0.0)] = 0.100


class BreakBeamConfiguration(Strict):
    kind: Literal["sensor"] = "sensor"
    beam_axis: Literal["x", "y", "z"]
    beam_length_m: Annotated[float, Field(gt=0.0)]
    #: How thick the beam is across its axis.
    #:
    #: A real through beam is a few millimetres. This is deliberately wider, so
    #: that a work-piece travelling at belt speed cannot cross the beam between
    #: two physics steps and go unnoticed: at the installed 0.150 m/s and a 1 ms
    #: step a part advances 0.15 mm, so 40 mm is roughly 260 steps of margin.
    #: It lives here rather than as a plugin default because it decides whether a
    #: sensor can detect anything at all, and code must never be where that is
    #: decided (P5).
    beam_width_m: Annotated[float, Field(gt=0.0)] = 0.040
    idle_state: Literal["clear", "blocked"] = "clear"


class RobotConfiguration(Strict):
    kind: Literal["robot"] = "robot"
    home_rad: list[float] = Field(default_factory=list)


#: Only the categories that actually carry settings appear here. A fixture has
#: no configuration, so it has no member — adding an empty one "for symmetry"
#: would put a construct in the schema that nothing reads, which is exactly the
#: kind of unused surface P7 asks us not to claim.
Configuration = Annotated[
    ConveyorConfiguration | BreakBeamConfiguration | RobotConfiguration,
    Field(discriminator="kind"),
]


class AssetInstance(Strict):
    """One physical thing that exists, with an identity, a pose and a zone."""

    id: Identifier
    zone: Identifier
    type: Identifier
    pose: Pose
    hardware: HardwareSelection
    end_effector: EndEffectorSelection | None = None
    configuration: Configuration | None = None
    registration: Registration = Field(default_factory=Registration)


# --------------------------------------------------------------------------- #
# Facility
# --------------------------------------------------------------------------- #
class SurveyOrigin(Strict):
    status: Literal["provisional", "surveyed"] = "provisional"
    marker_id: str | None = None
    description: str | None = None


class Facility(Strict):
    id: Identifier
    name: str
    root_frame: Literal["cite_world"] = "cite_world"
    units: Literal["si_m_rad_kg_s"] = Field(
        default="si_m_rad_kg_s",
        description=(
            "Closed enum with one member. Its existence is a tripwire: adding a "
            "second member requires an ADR, because ADR-0020 forbids a second "
            "representation of any quantity."
        ),
    )
    survey_origin: SurveyOrigin = Field(default_factory=SurveyOrigin)
    #: Model names a gripper in this facility may pick up.
    #:
    #: The minimal answer to L0's open question "does the model describe products
    #: and work-pieces, or only equipment?". Not a work-piece *type* with
    #: attributes — only the names, because that is all anything needs today and
    #: inventing the rest before a consumer exists is how a schema acquires
    #: fields nobody reads. A gripper that attached to whatever it touched would
    #: pick up the table.
    workpiece_models: list[Identifier] = Field(default_factory=list)


class ZoneBounds(Strict):
    kind: Literal["aabb"] = "aabb"
    frame: FrameRef = "cite_world"
    min_m: Triple
    max_m: Triple


class Zone(Strict):
    """A named region. Zones partition; they do not nest.

    Nesting would change every name in the system, so `naming-and-namespaces.md`
    rule 6 puts it behind an ADR.
    """

    id: Identifier
    name: str
    bounds: ZoneBounds


# --------------------------------------------------------------------------- #
# Topology
# --------------------------------------------------------------------------- #
class StationPoint(Strict):
    asset: Identifier
    frame: Identifier


class StationTrigger(Strict):
    """The sensor state that starts this station's work.

    The field is ``state`` and not ``on``, which reads better, because YAML 1.1
    resolves a bare ``on`` to the boolean ``true``. A key that quietly becomes
    ``True`` is precisely the silently-wrong-value class this model exists to
    eliminate, and relying on every author remembering to quote it is not a
    defence.
    """

    sensor: Identifier
    state: Literal["blocked", "clear"]


class Station(Strict):
    """A place in the process where work happens.

    A station says what it is connected to, never what it does — behaviour is
    L4's. The distinction is what keeps a layout change from being a code change.
    """

    id: Identifier
    zone: Identifier
    type: Literal["source_station", "transfer_station", "sink_station"]
    actor: Identifier | None = None
    assets: list[Identifier] = Field(default_factory=list)
    pick_from: StationPoint | None = None
    place_to: StationPoint | None = None
    trigger: StationTrigger | None = None
    capacity: Annotated[int, Field(ge=1)] = 1


class FlowEdge(Strict):
    """One directed link in the process flow.

    An edge list, not per-station ``upstream``/``downstream`` fields: writing
    both ends of a link is the same fact twice. The generator derives each
    station's neighbours.
    """

    from_station: Identifier = Field(alias="from")
    to_station: Identifier = Field(alias="to")
    via: Identifier | None = None
    buffer: Annotated[int, Field(ge=0)] = 0

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Flow(Strict):
    id: Identifier
    zone: Identifier
    edges: list[FlowEdge] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Documents — one per file kind, dispatched on the `schema:` key
# --------------------------------------------------------------------------- #
class Document(Strict):
    """Common head of every model file.

    The loader dispatches on ``schema``, not on which directory the file was
    found in, so a misfiled document is an error rather than a silent omission.
    """

    schema_: str = Field(alias="schema")

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class FacilityDocument(Document):
    schema_: Literal["cite/facility/v1"] = Field(alias="schema")
    facility: Facility


class ZonesDocument(Document):
    schema_: Literal["cite/zones/v1"] = Field(alias="schema")
    zones: list[Zone] = Field(min_length=1)


class AssetTypeDocument(Document):
    schema_: Literal["cite/asset_type/v1"] = Field(alias="schema")
    asset_type: AssetType


class AssetInstancesDocument(Document):
    schema_: Literal["cite/asset_instances/v1"] = Field(alias="schema")
    assets: list[AssetInstance] = Field(min_length=1)


class StationsDocument(Document):
    schema_: Literal["cite/stations/v1"] = Field(alias="schema")
    stations: list[Station] = Field(min_length=1)


class FlowDocument(Document):
    schema_: Literal["cite/flow/v1"] = Field(alias="schema")
    flow: Flow


DOCUMENT_TYPES: dict[str, type[Document]] = {
    "cite/facility/v1": FacilityDocument,
    "cite/zones/v1": ZonesDocument,
    "cite/asset_type/v1": AssetTypeDocument,
    "cite/asset_instances/v1": AssetInstancesDocument,
    "cite/stations/v1": StationsDocument,
    "cite/flow/v1": FlowDocument,
}
