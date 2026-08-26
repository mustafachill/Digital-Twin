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

import math
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

    @property
    def horizontal_extents_m(self) -> tuple[float, float] | None:
        """The smallest and largest horizontal extent of the collision geometry.

        Derived, never declared, because both numbers are already in ``size_m``
        and a declared copy would be a second place to be wrong (P1). Two rules
        need opposite ends of this pair and neither may invent it:

        * the widest horizontal extent is what a work-piece needs supported
          underneath it, so it sets the margin a place point must keep from the
          edge of the body it places onto (``insufficient-support-margin``);
        * the narrowest is the width a parallel gripper closes across, so it
          bounds ``default_grasp_width_m`` (``default-grasp-width-never-closes``).

        ``None`` for a mesh. Its extents live in a file L1 owns and this layer
        deliberately does not read, and returning ``None`` says the rules above
        do not cover it rather than pretending they do.
        """
        geometry = self.collision
        if geometry.kind == "box":
            x, y, _ = geometry.size_m
            return (min(x, y), max(x, y))
        if geometry.kind == "cylinder":
            diameter = 2.0 * geometry.radius_m
            return (diameter, diameter)
        return None


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

    #: Whether the controller manager clamps every command it is about to write
    #: against the limits declared for that joint.
    #:
    #: Required rather than defaulted, and that is the point of the field. It was
    #: absent, `ros2_control` defaults it to **false**, and the consequence was
    #: not a missing feature but a false one: the arm and gripper both declare
    #: position, velocity and effort limits, `cross-cutting-safety.md` requires
    #: limits enforced at planning *and* at execution, MoveIt's generated
    #: `joint_limits.yaml` says in as many words that "the controller is the
    #: other" half — and nothing anywhere was enforcing them. A limit that
    #: nothing checks is documentation, not a limit.
    #:
    #: A default would have re-created exactly that: a type that omits the field
    #: silently gets no enforcement, which is the one outcome no reader would
    #: guess from looking at the model. Making it required forces every robot
    #: type to state its position where a reviewer can see it.
    #:
    #: Scope, stated honestly because it is narrower than the name suggests. The
    #: manager clamps commands for joints it owns, using limits it read from the
    #: URDF — `hardware_interface::ResourceManager::import_joint_limiters` takes
    #: the *most restrictive* of the URDF `<limit>` and any `<command_interface>`
    #: min/max in the `<ros2_control>` block. It reads no ROS parameter for this:
    #: the limiter is constructed with `init(..., nullptr, nullptr)`, so there is
    #: no `joint_limits.<joint>.*` override, and a limit cannot be declared here.
    #: This flag turns enforcement on; the *values* live in the description.
    enforce_command_limits: bool


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


class GripperLinkage(Strict):
    """Where a parallel gripper's pads are, as a function of its drive angle.

    Two maps, one crank. Across the tool axis::

        opening(q) = 2 * (drive_pivot_y_m - pad_inset_m
                          + finger_offset_y_m*cos(q) - finger_offset_z_m*sin(q))

    and along it, how far PROXIMAL of the planning tip link the centre of the pad
    face sits::

        pad_plane_offset(q) = tip_link_z_m - drive_pivot_z_m - pad_face_centre_z_m
                              - (finger_offset_y_m*sin(q)
                                 + finger_offset_z_m*cos(q))

    This is the single home of both relationships (P1). The L3 skill server
    receives these seven numbers through the generated bring-up plan and
    evaluates the same closed forms, so task-space widths and task-space *poses*
    mean the same thing in the model, in the validator, and on the robot.

    They are closed forms rather than fits or tables because they are derivable:
    the drive joint and the finger joint rotate about opposite axes by the same
    angle, so their rotations cancel, the pad face stays parallel to the tool
    axis, and only its origin translates. The two maps are that one translation
    resolved on two axes — which is also why they belong in one model rather than
    two, since separating them would mean a second copy of the crank.

    Every field is a dimension in the robot's own description, which is what makes
    an audit possible: each can be checked against the vendor URDF or mesh rather
    than taken on trust.
    """

    #: y and z of the drive joint's origin in the gripper base frame.
    drive_pivot_y_m: float
    drive_pivot_z_m: float
    #: y and z of the driven finger joint's origin in the outer-knuckle frame —
    #: together the crank whose rotation opens and closes the jaw, and slides the
    #: pad face along the tool axis.
    finger_offset_y_m: float
    finger_offset_z_m: float
    #: How far the pad face lies inboard of the finger link's own origin. Taken
    #: from the collision mesh, because the URDF never states it.
    pad_inset_m: Annotated[float, Field(ge=0.0)]
    #: Where the planning tip link sits on the tool axis, in the gripper base
    #: frame. It is the FINGERTIP plane, not the gripping plane — which is the
    #: whole reason the axial map has to exist.
    tip_link_z_m: float
    #: Centre of the pad face along the tool axis, in the finger link's own
    #: frame. From the collision mesh, like ``pad_inset_m``: the URDF describes
    #: where the finger is, never which part of it grips.
    pad_face_centre_z_m: float

    @property
    def _pivot_m(self) -> float:
        """Half the opening the crank swings about."""
        return self.drive_pivot_y_m - self.pad_inset_m

    @property
    def _crank_m(self) -> float:
        """Length of the crank formed by the finger joint's offset."""
        return math.hypot(self.finger_offset_y_m, self.finger_offset_z_m)

    @property
    def _phase_rad(self) -> float:
        """Where the crank starts, so that ``opening`` is a single cosine."""
        return math.atan2(self.finger_offset_z_m, self.finger_offset_y_m)

    @property
    def _axial_reach_m(self) -> float:
        """The constant part of :meth:`pad_plane_offset_m`.

        Derived, never declared, for the same reason ``max_width_m`` is: the
        campaign that measured this quotes it as 0.0718988 m, and a declared copy
        of a number three other fields already determine is a second place to be
        wrong.
        """
        return self.tip_link_z_m - self.drive_pivot_z_m - self.pad_face_centre_z_m

    def opening_m(self, position: float) -> float:
        """The distance between the pads at drive-joint position ``position``."""
        return 2.0 * (self._pivot_m + self._crank_m * math.cos(position + self._phase_rad))

    def pad_plane_offset_m(self, position: float) -> float:
        """How far proximal of the tip link the pad face centre sits, in metres.

        The same crank as :meth:`opening_m`, projected on the tool axis instead
        of across it — hence a sine where that has a cosine.

        A grasp happens at the pad face, so a caller that knows where an object
        is has to move the tip link this far *past* it. Getting that wrong is not
        a rounding error: 24.4 mm of it put 19.3 mm of a 37.5 mm pad face on a
        50 mm work-piece, 15.35 mm off its centre of mass, and rotated the part
        past 20 degrees in 12 of 20 measured trials.
        """
        return self._axial_reach_m - self._crank_m * math.sin(position + self._phase_rad)

    def position_for(self, width_m: float) -> float:
        """The drive-joint position that opens the pads to ``width_m``.

        The exact inverse of :meth:`opening_m`, valid over the half-turn the
        gripper actually uses. Widths outside the linkage's reach saturate rather
        than raise: the caller's own travel limits decide what is commandable,
        and this function's job is only to be the inverse of the map.
        """
        cosine = (width_m / 2.0 - self._pivot_m) / self._crank_m
        return math.acos(max(-1.0, min(1.0, cosine))) - self._phase_rad


class GraspSpec(Strict):
    """How this end effector grasps: the stroke it has, and what a skill commands.

    One audience, on both paths. Every value here is read by the L3 skill server
    in simulation and on hardware alike; none of it is simulation-only. That is a
    change from what this block used to be. It also carried
    `attach_link_suffix`, `closed_threshold_rad` and `open_threshold_rad`, which
    existed solely to configure the contact-triggered attachment plugin ADR-0023
    introduced. That plugin is gone — superseded on the evidence of the 84-trial
    friction campaign in `docs/measurements/2026-08-25-friction-grasp/`, which
    measured it firing at first pad contact and destroying the very stall this
    block exists to produce — so the fields that fed it are gone with it.

    What remains is one stroke described once: where the joint travels, how fast,
    how its angle maps to a pad opening, and how wide to close by default. A
    grasp is now evidenced the way ADR-0022 always said it was — the pads meet
    the part, the joint stops short of its command, and the controller reports a
    stall.
    """

    drive_joint_suffix: str
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
    #: How fast the drive joint is allowed to travel, in rad/s, in either
    #: direction. Required: an end effector that does not say how fast it moves
    #: is an end effector nobody can reason about, and the omission is invisible.
    #:
    #: This is a *declaration about the actuator*, not a simulation tuning knob,
    #: and it has two distinct consumers on two different paths. In simulation it
    #: bounds the drive joint's command so the linkage's follower joints keep
    #: authority to correct (see `follower_headroom_fraction`). On hardware the
    #: same number is what the UFACTORY SDK's gripper speed argument has to be
    #: derived from — the physical gripper is driven through `xarm_api`'s service
    #: layer in r/min, not through `ros2_control`, so the value transfers but the
    #: mechanism does not. Declaring it here is what keeps those two from drifting.
    max_drive_rate_rad_s: Annotated[float, Field(gt=0.0)]
    #: The follower joints' own velocity limit, rad/s, as the *description*
    #: declares it — not a limit we impose, but a fact about the description we
    #: have to know in order to check `max_drive_rate_rad_s` against it.
    #:
    #: It is stated rather than read out of the vendor's URDF on purpose. L1's
    #: rule is that a vendor description is invoked, never ingested: nothing in
    #: this repository opens `xarm_gripper.urdf.xacro`, so the alternative to
    #: writing the number here is a validator that parses a vendor file, which is
    #: precisely the coupling that rule exists to prevent. Stating it makes the
    #: assumption checkable and makes a vendor change that invalidates it a
    #: failing test rather than a silent regression.
    follower_max_rate_rad_s: Annotated[float, Field(gt=0.0)]
    #: The linkage that turns the drive joint's angle into an opening between the
    #: pads. Required, because without it a width in metres cannot be commanded at
    #: all — and a plausible-looking linear guess is exactly how this gripper spent
    #: Phase 1.C closing on air.
    linkage: GripperLinkage
    #: What a `Pick` closes to when its goal names no width — the fallback L3
    #: applies for `grasp_width_m == 0`, in metres between the pads.
    #:
    #: It has to be *narrower than the work-piece*, not equal to it. A parallel
    #: gripper reports a grasp by failing to reach where it was told: the pads
    #: meet the part, the drive joint stops short, and the controller reports a
    #: stall. Commanding the part's own width means the gripper arrives exactly
    #: where it was sent, reports `reached_goal`, and the skill learns nothing
    #: about whether anything is between the pads (ADR-0022).
    #:
    #: The upper bound is a real constraint, not a preference; it is checked by
    #: `cite_tools.validate.physical`. See that check for the derivation.
    default_grasp_width_m: Annotated[float, Field(gt=0.0)] | None = None

    @property
    def max_width_m(self) -> float:
        """The widest the pads open, at ``open_position``.

        Derived, never declared. It used to be a field, and the declared 0.085 m
        disagreed with the linkage's true 0.08893 m — the textbook shape of the
        duplication P1 forbids, where two places state one fact and only one of
        them is right.
        """
        return self.linkage.opening_m(self.open_position)

    @property
    def min_width_m(self) -> float:
        """The narrowest the pads close to, at ``closed_position``."""
        return self.linkage.opening_m(self.closed_position)

    @property
    def follower_headroom_fraction(self) -> float:
        """How much of a follower joint's speed is left over while the leader moves.

        Derived, never declared, because it is the quantity the close rate is
        *chosen* by and a declared copy would be a second place to be wrong.

        The five finger joints are `<mimic>` followers of `drive_joint`, and
        under Gazebo Harmonic nothing couples them mechanically — dartsim
        implements no mimic constraint. `gz_ros2_control` closes the loop in
        software instead, with a proportional servo whose gain is the controller
        manager's update rate::

            velocity_setpoint = -(q_follower - q_leader * multiplier) * rate

        A follower therefore *must* carry a standing position error to command
        any speed at all: holding the leader's speed ``v`` needs an error of
        ``v / rate``, and the velocity it commands to do so is ``v`` itself. What
        is left for correcting a disturbance is whatever remains below the
        follower's own velocity limit:

            headroom = 1 - max_drive_rate_rad_s / follower_max_rate_rad_s

        At zero headroom the servo is saturated for the whole stroke and the
        linkage stops being a linkage: a perturbed follower departs at the
        saturated rate, runs to its position limit and stays there, leaving one
        pad roughly 23 degrees out of position while the controller reports the
        goal reached. That is not a hypothetical — it is the measured failure
        this field exists to prevent, at a leader and follower limit that were
        both 2 rad/s and so gave a headroom of exactly zero.
        """
        return 1.0 - (self.max_drive_rate_rad_s / self.follower_max_rate_rad_s)


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
    #: ``workpiece`` is the only member that describes something the facility
    #: *processes* rather than something it is built from, and it is here rather
    #: than in a document kind of its own because a work-piece needs exactly what
    #: every other authored body needs — extents, mass, an inertia tensor — and a
    #: parallel declaration would be a second `Body` to keep in step.
    #:
    #: A work-piece type is never instantiated as an `AssetInstance`: it has no
    #: fixed pose, because where it is is the process's business and not the
    #: layout's. `Facility.workpiece_models` names the ones this facility handles.
    category: Literal["robot", "end_effector", "conveyor", "sensor", "fixture", "workpiece"]
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
    #: An engineering floor, and still a declared one. 0.100 m clears the 50 mm
    #: cube while staying well below the 0.12 m an arm retreats to after a pick,
    #: so a part that has been lifted is released rather than fought over.
    #:
    #: It used to say it *could* not be derived, because L0 recorded no
    #: work-piece geometry. That is no longer true — `Facility.workpiece_models`
    #: resolves to types with extents now — so the honest statement is narrower:
    #: the datum exists and this value has not yet been rewritten against it.
    #: Doing so is a behaviour change to the belt plugin's carry volume and wants
    #: its own measurement, not a side effect of the change that made it possible.
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
    #: Which work-piece types this facility handles, by type id.
    #:
    #: L0's open question — "does the model describe products and work-pieces, or
    #: only equipment?" — used to be answered here with bare names and nothing
    #: else, on the grounds that no consumer needed more. Two consumers then
    #: appeared and both were blocked by the gap, which is what changed the
    #: answer: the support-margin rule cannot say how much belt a part needs
    #: underneath it without knowing how wide the part is, and the grasp-width
    #: ceiling cannot say "narrower than the part" without knowing the part.
    #:
    #: So these are references into the component library now, resolved to an
    #: `AssetType` of category ``workpiece``, and the geometry lives there —
    #: once, in the same `Body` every other authored object uses. The names still
    #: reach the simulator as Gazebo model names (the belt carries what this
    #: lists, and the beam watches it), which is why the type id and the spawned
    #: model name have to be the same string.
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
