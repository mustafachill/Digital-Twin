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

from pydantic import BaseModel, ConfigDict, Field, model_validator

# `lower_snake_case`, no leading digit — naming-and-namespaces.md rule 4.
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]

#: ``cite_world``, or ``<asset_id>/<frame_id>`` naming a frame on another asset.
FrameRef = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)?$")]

#: A MoveIt planner id, as the planner registers it — ``PTP``, ``LIN``,
#: ``RRTConnectkConfigDefault``. Deliberately NOT `Identifier`: these are MoveIt's
#: names and MoveIt capitalises them, so rule 4's `lower_snake_case` does not
#: apply. What this does enforce is that the value is a name at all — non-empty,
#: and not something that YAML will read back as a boolean or a number.
PlannerId = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]

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

    @property
    def vertical_extent_m(self) -> float | None:
        """How tall the collision geometry is.

        The other half of the pair above, and derived for the same reason: it is
        already in ``size_m``. One rule needs it — the belt's carry volume, which
        is how far above the working surface a part still counts as resting on
        it. That is a fact about the part, not about the belt, so the world
        generator reads it from here instead of the conveyor declaring a height
        of its own (P1).

        ``None`` for a mesh, exactly as above: its extents live in a file L1
        owns, and saying so is better than guessing.
        """
        geometry = self.collision
        if geometry.kind == "box":
            return geometry.size_m[2]
        if geometry.kind == "cylinder":
            return geometry.length_m
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


class CollisionMeshSet(Strict):
    """One selectable collision-geometry set for a vendor-described type (ADR-0028).

    A vendor description is *invoked, never ingested*, so nothing in this layer
    may open a vendor file to discover what its links collide against. This class
    is how the model states it instead — and stating it is what lets
    ``validate.physical`` fire on a vendor description at all, which ADR-0028
    decision 4 requires and which was impossible while the only collision
    geometry L0 knew about was an authored ``Body``.

    Two kinds, and the asymmetry between them is deliberate:

    * ``vendor_meshes`` carries no paths. It names the vendor's own choice — for
      the variant we model that choice is *the visual meshes* — and exists so
      that a type can say so out loud rather than by omission.
    * ``convex_hull`` names a derived asset set produced by ``cite_tools.meshes``
      from the vendor meshes listed in ``meshes``. Those paths are relative to
      both roots, because the binding replaces one mesh **root** with another in
      the vendor description: a collision reference resolves under our root only
      if its relative path is unchanged. The mirror is the mechanism.
    """

    id: Identifier
    kind: Literal["vendor_meshes", "convex_hull"]
    #: The ament package whose ``share/`` holds the derived meshes, and the
    #: directory under it. Together they form the root the description is handed.
    package: str | None = None
    root: str | None = None
    #: Where the meshes were derived FROM. Recorded here rather than only in
    #: ``assets/manifest.yaml`` because it is what makes the set regenerable: the
    #: pipeline reads these, not the manifest, so the manifest can never be the
    #: thing that decides what the hull is derived from.
    source_package: str | None = None
    source_root: str | None = None
    #: Mesh paths, relative to both roots. Exhaustive for the links of this
    #: description that carry collision geometry — a missing entry is a collision
    #: reference that resolves to nothing once the root is substituted.
    meshes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _kind_carries_its_fields(self) -> CollisionMeshSet:
        derived = (self.package, self.root, self.source_package, self.source_root)
        if self.kind == "vendor_meshes":
            if any(derived) or self.meshes:
                raise ValueError(
                    "a vendor_meshes set names no paths: it IS the vendor's own choice, "
                    "and listing paths here would be a second place for them to be wrong"
                )
            return self
        if not all(derived) or not self.meshes:
            raise ValueError(
                "a convex_hull set needs package, root, source_package, source_root "
                "and at least one mesh; without them nothing can produce or find it"
            )
        return self


class CollisionSpec(Strict):
    """Which collision geometry a vendor-described type's links use (ADR-0028).

    The choice is per type rather than per link, and that is a decision with a
    reason. The mechanism underneath is the substitution of one mesh *root* for
    another in the vendor description, which is not something a single link can
    have an opinion about. Per-link exceptions are foreseen — ADR-0028 expects the
    gripper fingers to need one — but the exception it describes is *a primitive
    instead of a mesh*, which this field could never express whatever its
    granularity. That is a different mechanism and belongs to the change that
    measures it.

    This docstring said until 2026-08-31 that the exception was needed "because a
    convex hull fills the gap between the pads". It does not: each link is hulled
    separately, so that gap lies between two collision bodies, and the aperture at
    the pads is unchanged to 0.01 mm.

    It then said, until 2026-09-01, that "what makes the fingers still need the
    exception is the 2.0 mm relief step at each end of each pad, which the hull
    ramps across". **That is a second wrong mechanism derived the same way as the
    first**, from a static audit taken at a *commanded* aperture the gripper never
    occupies while holding this cell's part. The ramps are real; they are recessed
    behind the pad plane on the same rigid link, so a flat face resting on the pad
    is clear of them at every aperture. Both errors and the measurement that
    settled them are in ADR-0028's corrections of 2026-08-31 and 2026-09-01 and in
    ADR-0051, which restates the promotion gate around them.

    **So no measured mechanism requires the exception today, and it is still
    foreseen rather than retired.** What is untested is a work-piece narrow enough
    to close the jaws past the pad plane's recess — ADR-0051 decision 3 makes
    declaring one a model error, enforced by
    ``validate.physical._derived_collision_is_within_its_measured_range``, and
    names what must be measured first. If that case ever needs answering with
    geometry, the answer is the per-link exception above, which this field still
    cannot express.
    """

    #: The ``id`` of the set in ``sets`` that is bound into the description.
    select: Identifier
    #: The vendor macro parameter through which a collision-mesh root reaches the
    #: description. Vendor-specific by nature, exactly like ``bound_args``, and it
    #: is what makes this mechanism usable by a description other than this one.
    root_arg: str | None = None
    #: Backend id -> the URI scheme the vendor's own mesh root resolves to under
    #: that backend. Model data for the same reason ``root_arg`` is: it is a fact
    #: about the vendor description, and a generator that knew it would be a
    #: generator that knows the vendor's plugin class strings.
    #:
    #: It exists because the substituted root has to branch the way the root it
    #: substitutes for does, and it did not. ``xarm_device_macro.xacro`` sets
    #: ``mesh_path`` to ``file://$(find xarm_description)/meshes`` for a Gazebo
    #: plugin and ``package://xarm_description/meshes`` for anything else; the
    #: generator emitted ``file://`` unconditionally. Under ``backend: real`` that
    #: produced a description whose visuals were ``package://`` and whose
    #: collisions were absolute paths into the generating machine's install
    #: prefix — unportable, and it is the half a planner uses. Patch 03's header
    #: claimed *"the only asymmetry is the vendor's own"*, which stopped being
    #: true the moment this generator emitted one of its own.
    #:
    #: Required whenever a derived set is declared, not merely when one is
    #: selected, so that flipping ``select`` stays a one-field change.
    root_uri_scheme: dict[Identifier, Literal["file", "package"]] = Field(default_factory=dict)
    sets: list[CollisionMeshSet] = Field(min_length=1)

    @property
    def selected(self) -> CollisionMeshSet:
        """The bound set. Guaranteed present by ``_select_names_a_set``."""
        return next(s for s in self.sets if s.id == self.select)

    @model_validator(mode="after")
    def _select_names_a_set(self) -> CollisionSpec:
        ids = [s.id for s in self.sets]
        if len(set(ids)) != len(ids):
            raise ValueError("collision set ids must be unique")
        if self.select not in ids:
            raise ValueError(f"select {self.select!r} names no set; have {sorted(ids)}")
        if self.selected.kind != "vendor_meshes" and not self.root_arg:
            raise ValueError(
                "a derived collision set needs root_arg: without a macro parameter to "
                "carry the root, the set is generated and never reaches the description"
            )
        if any(s.kind != "vendor_meshes" for s in self.sets) and not self.root_uri_scheme:
            raise ValueError(
                "a declared derived collision set needs root_uri_scheme: the substituted "
                "root has to resolve the way the root it replaces does, and the vendor "
                "branches that on the backend. Required on DECLARATION rather than on "
                "selection, so that flipping `select` stays a one-field change."
            )
        return self

    def scheme_for(self, backend: str) -> str:
        """The URI scheme for one backend, or a raise. Never a default.

        A default here would be a silently wrong description on whichever backend
        nobody thought about — which is exactly how the unconditional `file://`
        survived: it was right on `sim`, where every scenario runs, and wrong on
        `real`, where nothing runs yet.
        """
        try:
            return self.root_uri_scheme[backend]
        except KeyError:
            raise KeyError(
                f"collision.root_uri_scheme names no scheme for backend {backend!r}; "
                f"have {sorted(self.root_uri_scheme)}"
            ) from None


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
    #: What the links of a vendor description collide against (ADR-0028).
    #: Optional on the class because most types provide a ``body`` instead;
    #: ``validate.physical`` requires it of every type whose vendor description
    #: this generator actually emits, which is the set of types where its absence
    #: means "nobody has looked".
    collision: CollisionSpec | None = None
    body: Body | None = None


class HardwareBackend(Strict):
    """One selectable ``ros2_control`` backend for a type.

    The plugin class string is *authored* exactly once, here. Nothing else may
    introduce one: every generated ``<ros2_control>`` block takes its plugin from
    this field, which is what makes 'the only thing that differs is which plugin
    is loaded' (ADR-0005) true by construction rather than by discipline.

    One exception exists and it is deliberate. ``cite_bringup``'s
    abort-classification launch test names the production plugin in order to
    ASSERT against it before substituting a fixture, so that a change to this
    field fails that rig loudly rather than silently stopping it substituting
    anything (ADR-0040). That is a mirror, not a second home: it feeds no
    description, and its whole purpose is to break when this field moves. A third
    occurrence is a trend rather than another exception — treat it as one.
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


class TrajectoryConstraints(Strict):
    """When a `JointTrajectoryController` should call a trajectory mistracked.

    ADR-0036. Without these the controller runs any trajectory to the end and
    reports ``SUCCEEDED`` however badly it tracked, because
    `joint_trajectory_controller` defaults every tolerance to ``0.0`` and
    ``check_state_tolerance_per_joint`` skips any variable whose tolerance is not
    ``> 0.0``. That silence reaches the caller: MoveIt returns success,
    ``execute_plan`` maps it to ``ResultCode::SUCCESS``, and ``Pick`` reports a
    clean pick it never made.

    These are a DETECTOR and not a protective measure. What stops an arm driving
    into a fixture is the vendor controller's torque limiting and physical
    guarding — a risk assessment and ISO 10218 matter outside this repository
    (charter §3.2). This turns a silent success into an ``EXECUTION_FAILED``
    after the fact, which is what lets L4 fault a station instead of building on
    a lie.

    They live in the model rather than in the generator for the same reason
    ``update_rate_hz`` and ``max_acceleration_rad_s2`` do: how tightly a
    particular arm tracks is a fact about that arm (P5). One block serves both
    backends — a tolerance that differed between simulation and hardware would
    be a P2 break, not a tuning choice.
    """

    #: How long after the trajectory's end time the controller keeps waiting for
    #: the goal tolerance below, in seconds.
    #:
    #: Required and strictly positive, and that constraint is the whole reason
    #: this is a typed block rather than two loose keys. ``0.0`` does NOT mean
    #: "disabled" here: in ``update()`` the abort lives in an
    #: ``else if (!within_goal_time)`` branch, and ``within_goal_time`` is only
    #: ever set false inside ``if (goal_time_tolerance != 0.0)``. So a goal
    #: tolerance paired with ``goal_time: 0.0`` can neither succeed nor fail — the
    #: controller "runs another cycle" forever. Upstream says so outright: "If set
    #: to zero, the controller will wait a potentially infinite amount of time."
    #:
    #: That is the failure shape ADR-0022 already found once, in
    #: ``GripperActionController``, where neither terminating branch could fire
    #: and the action simply never returned. The caller sees a timeout in the
    #: layer above rather than an answer, which is strictly worse than the false
    #: success this block exists to remove. Making both fields required and
    #: positive means the model cannot express that combination.
    goal_time_s: Annotated[float, Field(gt=0.0)]

    #: Per-joint position error allowed at the goal, in radians, checked from the
    #: trajectory's end time until ``goal_time_s`` after it. Exceeded, the goal
    #: aborts with ``GOAL_TOLERANCE_VIOLATED``.
    #:
    #: Strictly positive for the mirror-image reason: at ``0.0`` the position
    #: check is skipped entirely, the success branch is taken immediately, and
    #: ``goal_time_s`` becomes configuration nothing reads.
    goal_tolerance_rad: Annotated[float, Field(gt=0.0)]

    #: Per-joint position error allowed WHILE MOVING, in radians. Exceeded, the
    #: goal aborts mid-trajectory with ``PATH_TOLERANCE_VIOLATED``. This is the
    #: only one of the three that catches a trajectory clipping a fixture rather
    #: than merely arriving wrong.
    #:
    #: Nullable, and the null case is a real one rather than a schema
    #: convenience. This is also the tolerance that can cry wolf: it is evaluated
    #: on every cycle of every motion, and one that fires on a healthy run under
    #: a loaded machine converts a blocking CI gate into a flake — which this
    #: project's history says gets exempted rather than fixed. ``null`` emits no
    #: per-joint ``trajectory`` key and leaves the path check off, so an arm can
    #: decline the path detector while keeping the goal detector. Prefer that to
    #: widening the value until it never fires, which leaves something that only
    #: looks like a detector.
    trajectory_tolerance_rad: Annotated[float, Field(gt=0.0)] | None = None

    #: Joint velocity, in rad/s, below which the arm counts as stopped at the
    #: goal. ``0.0`` disables the check.
    #:
    #: Required with no default, and the reason is NOT the one an earlier version
    #: of this docstring gave (ADR-0036's 2026-08-27 correction). It said this was
    #: the one goal-side tolerance already armed, and that setting ``goal_time_s``
    #: would arm it. Half of that is right: ``get_segment_tolerances`` does assign
    #: ``goal_state_tolerance[i].velocity = stopped_velocity_tolerance``
    #: unconditionally, and the parameter does default to ``0.01`` rather than to
    #: zero. The rest is false for any controller that commands position alone.
    #: ``compute_error_for_joint`` writes a velocity error only under
    #: ``has_velocity_state_interface_ && (has_velocity_command_interface_ ||
    #: has_effort_command_interface_)``, so with ``command_interfaces:
    #: [position]`` the error stays at the zeros it was sized to and no velocity
    #: tolerance can ever be exceeded. ``goal_time_s`` does not change that.
    #:
    #: It is required anyway, because the value has to be a decision the moment it
    #: CAN fire, and the change that makes it fire is a ``velocity`` or ``effort``
    #: entry in this controller's ``command_interfaces`` — nothing else. That is a
    #: plausible change here: the vendor configuration these values were copied
    #: from commands ``[position, velocity]``. Inheriting ``0.01`` silently on the
    #: run after such a change would mean a VELOCITY-driven abort appearing inside
    #: a block whose purpose is a POSITION detector, so the model states it.
    stopped_velocity_tolerance_rad_s: Annotated[float, Field(ge=0.0)]


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
    #: Execution-side mistracking detector, for a trajectory controller only
    #: (ADR-0036). Optional on the field because most controllers have no such
    #: block; a trajectory controller that omits it is rejected by the generator
    #: rather than defaulted, which is where that rule can name the type.
    constraints: TrajectoryConstraints | None = None


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
    #: How long the L3 skill server waits for this gripper's controller to answer
    #: a `GripperCommand` at all, in seconds of the waiting node's own clock
    #: (ADR-0045). Required: a gripper whose controller can stop answering and
    #: does not say how long anyone should wait is a station that hangs.
    #:
    #: IT DOES NOT BOUND "A SLOW GRASP". `GripperActionController` restarts its
    #: stall search on every control cycle above `stall_velocity_threshold`, so
    #: the time it takes to declare a stall has no upper bound and no value here
    #: could cap it. What this bounds is the controller not terminating the goal,
    #: and its expiry says nothing whatever about whether the jaws hold a part.
    #:
    #: Its floor is derived from the stroke and the stall timeout together and is
    #: checked by `cite_tools.validate.physical`; above that floor the value
    #: carries no claim. The same declaration reaches the hardware path, where
    #: the node clock is the wall clock and the server being waited on is the
    #: vendor's rather than a `GripperActionController` (P2).
    result_timeout_s: Annotated[float, Field(gt=0.0)]

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
    #: Joint deceleration ceiling in rad/s^2, as a MAGNITUDE. Pilz's trapezoidal
    #: profile treats braking separately from accelerating (ADR-0027).
    #:
    #: It is NOT true that omitting it makes Pilz refuse every request, which is
    #: what this comment claimed before it was checked. MoveIt derives the
    #: ceiling when it is missing — `joint_limits_aggregator.cpp` sets
    #: `max_deceleration = -max_acceleration` whenever an acceleration limit is
    #: present and a deceleration limit is not — so an arm that states
    #: `max_acceleration_rad_s2` already has a derived braking ceiling equal to
    #: it. Requiring this key makes that ceiling a stated decision rather than a
    #: side effect of the acceleration one, which is the only form in which the
    #: two can ever differ.
    #:
    #: MoveIt's own convention is that the value is negative; the sign is applied
    #: where MoveIt is the consumer, not stated here, because a braking ceiling
    #: is a magnitude in every other part of this model.
    max_deceleration_rad_s2: Annotated[float, Field(gt=0.0)]

    #: Which MoveIt pipeline plans by default, and which one a refusal falls back
    #: to (ADR-0027). Both are data rather than constants in the generator: a
    #: trajectory generator that fails instead of searching is a choice about
    #: THIS arm's motions, and an arm whose limits Pilz cannot satisfy has to be
    #: able to say so in the model rather than in code (P1, P5).
    #:
    #: The generator knows what each named pipeline is made of — its plugin class
    #: and its adapter chain — and rejects a name it does not know. That is the
    #: P5 split: the model chooses which pipeline plans, the generator encodes how
    #: a pipeline is configured.
    default_pipeline: str
    #: Pilz has no default planner and refuses a request with an empty planner id
    #: ("No ContextLoader for planner_id ''"), so this is stated rather than left
    #: to the pipeline.
    #:
    #: Constrained rather than a bare `str`. An empty value was schema-legal,
    #: generated an unquoted plan value that YAML parses back as `None`, and
    #: failed at launch — after `validate-model` had already said the model was
    #: valid, which is the worst possible place for it to fail. The generator
    #: checks the rest: that the id is one the chosen pipeline registers, and
    #: that a Cartesian planner is not made the default of a group that cannot
    #: solve one along a whole path.
    default_planner_id: PlannerId
    fallback_pipeline: str
    #: Empty means "whatever that pipeline is configured to default to". For the
    #: generated OMPL block that is its single planner configuration, which is
    #: exactly the planner every motion in this cell used before ADR-0027 — so
    #: the fallback path is the behaviour this cell already had, unchanged.
    #:
    #: The one planner id that may be empty, which is why it is not a `PlannerId`.
    #: A non-empty value still has to be a name, and the generator still checks it
    #: against what the fallback pipeline registers.
    fallback_planner_id: Annotated[str, Field(pattern=r"^([A-Za-z][A-Za-z0-9_]*)?$")] = ""

    #: Cartesian ceilings for the pipelines that interpolate a path in task space
    #: rather than in joint space — Pilz LIN and CIRC read all four and cannot be
    #: constructed without them. They are ceilings we choose for this arm, not
    #: vendor figures: the tool-point speed an xArm 5 can reach is a consequence
    #: of its joint limits and its pose, and a single number for it only exists
    #: because a planner needs one.
    max_cartesian_velocity_m_s: Annotated[float, Field(gt=0.0)]
    max_cartesian_acceleration_m_s2: Annotated[float, Field(gt=0.0)]
    #: A magnitude, negated at emission for the same reason as the joint value.
    max_cartesian_deceleration_m_s2: Annotated[float, Field(gt=0.0)]
    max_cartesian_rotational_velocity_rad_s: Annotated[float, Field(gt=0.0)]

    @model_validator(mode="after")
    def _pipelines_differ(self) -> PlanningSpec:
        """A fallback that is the default is not a fallback.

        It would also emit the same pipeline name twice in `planning_pipelines`,
        which move_group loads without complaint and which makes the generated
        file read as though two pipelines were configured when one is.
        """
        if self.default_pipeline == self.fallback_pipeline:
            raise ValueError(
                f"default_pipeline and fallback_pipeline are both "
                f"{self.default_pipeline!r}; a refusal would fall back to the "
                f"planner that refused"
            )
        return self


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

    @model_validator(mode="after")
    def _every_backend_answers_the_collision_scheme(self) -> AssetType:
        """A backend with no URI scheme is a backend nobody decided about.

        Checked here rather than on `CollisionSpec` because this is the only class
        that can see both halves. Adding a hardware backend to a type that binds
        collision geometry is now a change that has to state how meshes resolve
        under it, which is the question `backend: real` answered wrongly by
        omission for as long as the field did not exist.
        """
        spec = self.description.collision
        if spec is None or not spec.root_uri_scheme:
            return self
        missing = sorted(set(self.hardware_backends) - set(spec.root_uri_scheme))
        unknown = sorted(set(spec.root_uri_scheme) - set(self.hardware_backends))
        if missing:
            raise ValueError(
                f"collision.root_uri_scheme names no scheme for backend(s) {missing}; "
                "every declared backend needs one, because the vendor resolves its own "
                "mesh root differently under each"
            )
        if unknown:
            raise ValueError(
                f"collision.root_uri_scheme names backend(s) {unknown} that this type "
                "does not declare"
            )
        return self

    @property
    def emits_vendor_description(self) -> bool:
        """Whether the generator emits a vendor macro invocation for this type.

        Derived, and derived HERE, because two modules need the same answer and a
        second copy of the predicate would drift: ``generate.description`` uses it
        to decide what to emit, and ``validate.physical`` uses it to decide whose
        collision geometry it is entitled to demand a declaration of. A type that
        names a macro but is built into another type's description — the parallel
        gripper is the one in this model — is not emitted and is not asked.
        """
        return self.description.provider == "xacro_macro" and self.category == "robot"


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
    #: What the COUNTERPART side of this instance loads, where the two sides
    #: differ. Absent means the same backend as ``backend`` (ADR-0041,
    #: Decision 3).
    #:
    #: ``backend`` is a scalar with no side index: it says which plugin *this
    #: instance* loads, and in a twin pair this instance exists on both sides. So
    #: a backend is selected per (asset, side), and the only thing ever written
    #: per asset is a side that DIFFERS from the plant — which is a genuine
    #: per-asset fact. 2.A writes nothing here at all: the zone says ``pair``,
    #: both sides are ``sim`` because the plant is.
    #:
    #: This one may have a fallback where ``backend`` may not, and the fallback
    #: is what preserves that field's property rather than weakening it: **no
    #: omitted key can produce a non-sim value anywhere**, because the value it
    #: falls back to is itself required and explicit. A counterpart becomes
    #: physical only by someone writing it, and the bring-up refusal in
    #: `cite_bringup.plan.require_hardware_opt_in` then fires on it.
    counterpart_backend: Identifier | None = None
    params: dict[str, str | bool | int | float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _counterpart_defaults_to_the_plant(self) -> HardwareSelection:
        """Apply the fallback at load, so the two spellings are one model.

        ``counterpart_backend: sim`` written out and ``counterpart_backend``
        omitted describe the same facility, by the definition of the fallback, so
        they must be the same loaded model — and `model_hash` is why that matters
        rather than being tidiness. The hash is taken over this object graph and
        identifies *the facility that was described*; without this, one facility
        would carry two identities depending on how explicitly it was written,
        and an L6 recording stamped with one would not match the other.

        Every other optional field in this schema already has that property for
        free, because pydantic materialises a literal default. This one cannot
        have a literal default — the value it falls back to is a sibling field —
        which is the whole reason it needs a validator instead.

        The authored model still shows the distinction, which is where ADR-0041
        wanted it: an untwinned instance writes nothing, and ``git diff`` shows
        exactly the assets whose counterpart differs.
        """
        if self.counterpart_backend is None:
            return self.model_copy(update={"counterpart_backend": self.backend})
        return self

    @property
    def effective_counterpart_backend(self) -> str:
        """The backend the counterpart side loads.

        Reads through the normalisation above rather than repeating it, and
        exists so that a consumer never has to decide what a `None` means — after
        validation there is no `None` here, and the ``or`` is a type-narrowing
        formality rather than a second statement of the rule.
        """
        return self.counterpart_backend or self.backend


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

    # No `carry_height_m`. It used to be declared here, defaulting to 0.100 m,
    # with a comment saying the value could not be derived because L0 recorded no
    # work-piece geometry — and then a narrower one saying the datum had arrived
    # but the number had not been rewritten against it.
    #
    # It has been. How far above a belt's surface a part still counts as resting
    # on it is a fact about the PART, not about the belt: it is the part's own
    # height. `cite_tools.generate.world` now derives it from the tallest type in
    # `Facility.workpiece_models`, the same way it already reads the belt's
    # footprint from the belt's collision box rather than letting an instance
    # restate it (P1).


class BreakBeamConfiguration(Strict):
    kind: Literal["sensor"] = "sensor"
    beam_axis: Literal["x", "y", "z"]
    beam_length_m: Annotated[float, Field(gt=0.0)]
    #: How thick the beam is across its axis: the width of the emitted spot.
    #:
    #: 4 mm is a lensed through-beam aperture, which is what these sensors are.
    #: It lives here rather than as a plugin default because it decides whether a
    #: sensor can detect anything at all, and code must never be where that is
    #: decided (P5).
    #:
    #: IT USED TO BE 40 mm and that was an anti-tunnelling inflation, not a
    #: measurement: the plugin tested the work-piece's model ORIGIN against the
    #: beam's volume, so the beam had to be wide enough that a part could not
    #: step across it between two physics frames. The plugin now tests the beam
    #: against the part's BODY, which is occluded for the whole length of the
    #: part — 54 mm at the declared cube, or about 360 steps at 0.150 m/s and a
    #: 1 ms step, against the roughly 260 the inflation used to buy. The margin
    #: went up when the inflation came out.
    #:
    #: Taking it out mattered for more than tidiness. Half this number is the
    #: distance before the beam's centre at which a part first breaks it, and
    #: ``indexes_workpiece`` below derives a mounting position from exactly that.
    #: At 40 mm the derivation would have carried 20 mm of simulator artefact
    #: into L0 geometry, and the physical cell would have parked its parts 20 mm
    #: from where this model says they park (P2).
    beam_width_m: Annotated[float, Field(gt=0.0)] = 0.004

    #: Whether this beam indexes the conveyor it is mounted on.
    #:
    #: A beam that indexes is one an indexing belt stops on: the part runs until
    #: its leading edge breaks the beam, the belt stops, and the part is left
    #: standing at the point a robot picks from. Setting this true says that the
    #: frame this sensor is mounted against IS that point, and hands the beam's
    #: position along the belt to the generator.
    #:
    #: WHY THE POSITION IS DERIVED AND NOT WRITTEN DOWN. A through beam breaks on
    #: a leading edge, so a part comes to rest with its centre half a part-length
    #: short of the beam. Where the beam has to be mounted is therefore a fact
    #: about the PART, in exactly the way ``carry_height_m`` above turned out to
    #: be: pick point, plus half the work-piece, plus half the beam's own width.
    #: Writing that as a coordinate would fix it to one part size and let it rot
    #: silently the day the facility handles another — which is the failure this
    #: field exists to make impossible, not merely to document.
    #:
    #: This is also why the along-travel component of an indexing beam's pose
    #: must be zero: the pose says which point the beam indexes to, and the
    #: offset from it is not an authored number. ``beam-indexes-off-frame`` in
    #: cite_tools.validate.geometric refuses a second, fitted copy.
    #:
    #: False for a beam that only observes. ``beam_pick`` watches a table that
    #: nothing indexes, and ``beam_c3_out`` reports arrivals at a sink with no
    #: actor, so neither stops a belt and neither has a pick point to stand off
    #: from.
    indexes_workpiece: bool = False

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


class TwinSpec(Strict):
    """Whether this zone is modelled as one cell or as a twinned pair.

    ADR-0041's Decision 3, and it is a ZONE fact written once rather than an
    asset fact written per instance. In Phase 2.A the counterpart is a complete
    second simulation of the cell, so its world contains every asset whether or
    not anyone wanted that asset twinned; "arm_1 is paired but conveyor_1 is not"
    has no meaning there, and writing the same deployment fact on fifteen
    instances is P1 at a different granularity.

    There is deliberately no ``counterpart`` field and no ``none`` sentinel.
    Twinned is DERIVED — an asset is twinned exactly when its zone declares a
    second side — because a sentinel is a way of making an untwinned asset
    declare that it is untwinned, and it crosses with `HardwareSelection` to give
    one physical situation two encodings.

    The two sides are named ``plant`` and ``counterpart``, structurally: `plant`
    is the side the untwinned model already describes and that every Phase 1
    artifact, scenario and script already addresses, and `counterpart` is the
    side that exists only where the zone is a `pair`. Nothing in that naming
    moves when `TwinMode` moves, which is what makes it safe to derive a Gazebo
    transport partition from (ADR-0042). The names themselves are mechanism and
    live in `cite_tools.model.ids`, never here.
    """

    #: Required, with no default, for the same reason `HardwareSelection.backend`
    #: is: this decides how many machines the model describes, and a second cell
    #: must not appear because a key was omitted. The churn that costs is one
    #: line in one file, which is what moving the fact to zone scope bought.
    sides: Literal["single", "pair"]


class Zone(Strict):
    """A named region. Zones partition; they do not nest.

    Nesting would change every name in the system, so `naming-and-namespaces.md`
    rule 6 puts it behind an ADR.
    """

    id: Identifier
    name: str
    bounds: ZoneBounds
    twin: TwinSpec


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
