"""Turn the authored model into the fully-resolved view generators consume.

Authors write relative poses and short identifiers, because that is what keeps a
fact in one place: an arm is placed on its pedestal's top, a sensor is placed
relative to the belt it watches. Generators need the opposite — every pose in
``cite_world`` and every name already built.

Doing that conversion here, once, is what lets a template contain no logic. A
template that computed a frame name would be a second place names are made, and
``ids.py``'s tests would not cover it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cite_tools.model import blockly, ids
from cite_tools.model.geometry import Aabb, Pose
from cite_tools.model.loader import FacilityModel
from cite_tools.model.schema import (
    AssetInstance,
    AssetType,
    ControllerSpec,
    HardwareBackend,
    Material,
    TrajectoryConstraints,
)
from cite_tools.model.workpieces import WorkpieceWidths, workpiece_types, workpiece_widths


class ResolveError(Exception):
    """A pose or frame could not be resolved. Referential validation runs first."""


@dataclass(frozen=True)
class ResolvedController:
    """A controller, with both of the names it is known by.

    ``name`` is what the controller manager calls it — prefixed, so two arms of
    the same type do not collide. ``action`` is how a consumer addresses it,
    inside the asset's namespace. Both come from one suffix here, so they cannot
    drift apart.
    """

    name: str
    type: str
    stage: int
    joints: tuple[str, ...]
    command_interfaces: tuple[str, ...]
    state_interfaces: tuple[str, ...]
    parameters: dict[str, str | bool | int | float]
    #: The execution-side mistracking detector this controller declares, or
    #: ``None`` for a controller that has no such block (ADR-0036). Carried
    #: through unchanged: the per-joint expansion needs ``joints`` above, which
    #: only exists once the instance has been resolved.
    constraints: TrajectoryConstraints | None = None
    #: Which asset's hardware this controller claims a joint of: the asset's
    #: own (`OWN`), the end effector fitted to it (`END_EFFECTOR`) or the track
    #: it rides (`AXIS`). A controller is loaded on a side only where some
    #: hardware component on that side exports its joint, and which component
    #: that is depends on where the controller came from
    #: (`ResolvedAsset.controllers_on`, ADR-0070 items 3 and 4).
    origin: str = "own"


#: The three values of `ResolvedController.origin`.
OWN = "own"
END_EFFECTOR = "end_effector"
AXIS = "axis"


@dataclass(frozen=True)
class ResolvedAxis:
    """The linear track an arm stands on, as the arm's own description needs it.

    Everything here is emitted into the ARM's description and the ARM's
    controller manager, because the carriage carries the arm (ADR-0067): the
    prismatic joint sits between the arm's mount link and its base, and its
    controller is loaded beside the arm's.

    ``direction`` is in the arm's MOUNT frame — the frame the joint's parent
    link has — and is derived from the track type's own direction and the two
    world poses, so the arm may be yawed on the carriage freely.
    """

    asset: str
    joint: str
    carriage_link: str
    direction: tuple[float, float, float]
    stroke_m: float
    max_speed_mps: float
    max_force_n: float
    carriage_mass_kg: float
    carriage_size_m: tuple[float, float, float]
    goal_tolerance_m: float
    #: The track's `ros2_control` plugin on each side, keyed by side name and
    #: read through `plugin_on`. `None` on a side whose track backend declares
    #: no plugin: no `<ros2_control>` block claims the joint there (ADR-0070
    #: item 3). Both sides are always present, the counterpart carrying the
    #: fallback, so a caller never has to know whether the zone is paired.
    plugins: tuple[tuple[str, str | None], ...]
    controller: str
    command_topic: str

    def plugin_on(self, side: str) -> str | None:
        """The track's plugin on ``side``; see `plugins`."""
        return dict(self.plugins)[side]


@dataclass(frozen=True)
class ResolvedAsset:
    """One asset instance with everything a generator needs, already computed."""

    id: str
    zone: str
    asset_type: AssetType
    instance: AssetInstance
    world_pose: Pose
    parent_asset: str | None
    parent_frame: str | None
    prefix: str
    namespace: str
    frames: dict[str, Pose] = field(default_factory=dict)
    controllers: tuple[ResolvedController, ...] = ()
    #: The track this arm rides on, or `None` for an arm bolted in place.
    axis: ResolvedAxis | None = None
    #: The program this arm runs, read from L0 (ADR-0067); empty where none.
    program: tuple[blockly.Step, ...] = ()

    def _backend(self, backend_id: str) -> HardwareBackend:
        backend = self.asset_type.hardware_backends.get(backend_id)
        if backend is None:
            raise ResolveError(
                f"asset {self.id!r} selects backend {backend_id!r}, "
                f"which type {self.asset_type.id!r} does not declare"
            )
        return backend

    def backend_on(self, side: str) -> str:
        """The backend id this asset loads on ``side``.

        THE ONE PLACE A GENERATOR TURNS (asset, side) INTO A BACKEND (ADR-0048
        clause 2, ADR-0070 item 1). Every generator site that branches on a
        backend asks this with the side it is generating for; reading
        `instance.hardware.backend` directly is reading the PLANT's, which is
        open-work #38's defect.
        """
        if side == ids.PLANT_SIDE:
            return self.instance.hardware.backend
        if side == ids.COUNTERPART_SIDE:
            return self.instance.hardware.effective_counterpart_backend
        raise ResolveError(f"{side!r} is not a side of a twin pair. Expected one of {ids.SIDES}.")

    def differs_on(self, side: str) -> bool:
        """Whether ``side`` loads a backend other than the plant's.

        A side that names the plant's backend gets no artifact of its own
        (ADR-0048 clause 2), so this is what decides whether one is emitted.
        """
        return self.backend_on(side) != self.backend_on(ids.PLANT_SIDE)

    def ros2_control_plugin_on(self, side: str) -> str | None:
        return self._backend(self.backend_on(side)).ros2_control_plugin

    def controllers_on(self, side: str) -> tuple[ResolvedController, ...]:
        """The controllers this asset's manager loads on ``side``.

        A controller is loaded where some hardware on that side exports its
        joint, and nowhere else: one claiming a joint no component exports fails
        to configure, and a side where it failed would not come up. Two
        declarations decide it, both read from L0 and neither from a plugin
        string:

        * a TRACK controller is dropped where the track's backend on that side
          declares no `ros2_control_plugin` (ADR-0070 item 3);
        * an END-EFFECTOR controller is dropped where this asset's backend on
          that side declares `exports_end_effector_joints: false` (item 4).

        The names stay what they are on every side: what is dropped is what the
        controller manager loads, never what a consumer addresses.
        """
        backend = self._backend(self.backend_on(side))
        track_unserved = self.axis is not None and self.axis.plugin_on(side) is None
        return tuple(
            c
            for c in self.controllers
            if not (c.origin == AXIS and track_unserved)
            and not (c.origin == END_EFFECTOR and not backend.exports_end_effector_joints)
        )

    def commands_physical_hardware_of(self, backend_id: str) -> bool:
        """Whether ``backend_id``, as this asset's type declares it, reaches a machine.

        Takes the backend id rather than reading `instance.hardware.backend`,
        because the caller that needs it most is the bring-up plan generator,
        which states the fact for the counterpart side as well and must ask about
        a backend that is not the plant's (ADR-0041 Decision 3, ADR-0054
        decision 3).

        It is a total function of the TYPE's declaration, which is why the plan
        has to carry the answer rather than derive it: the mapping from an id to
        the fact lives in `hardware_backends`, which the plan does not carry, and
        two types may declare the same id with different answers.
        """
        return self._backend(backend_id).commands_physical_hardware

    def frame_name(self, link_suffix: str) -> str:
        return ids.frame(self.zone, self.id, link_suffix)

    def topic(self, name: str) -> str:
        return ids.interface(self.zone, self.id, name)


@dataclass(frozen=True)
class ResolvedSide:
    """One side of the zone, and the two isolations it runs in.

    A `single` zone has one side and it is the plant, so this is never empty: an
    isolation that appeared only when someone paired a cell would be untested on
    every run that does not (ADR-0042).

    Two isolations rather than one, because neither substitutes for the other.
    `GZ_PARTITION` separates the Gazebo transport and does nothing to the ROS
    graph; `ROS_DOMAIN_ID` separates the ROS graph and was measured to do nothing
    to the Gazebo transport. A pair carrying one and not the other is either two
    cells sharing every belt topic or two cells colliding on every node name
    (ADR-0044, clause 2).

    The domain is a HALF: an offset, not a value. See `ids.domain_offset` for why
    an absolute domain cannot be emitted into a committed, hashed tree.
    """

    name: str
    gz_partition: str
    domain_offset: int


@dataclass(frozen=True)
class ResolvedStation:
    id: str
    zone: str
    type: str
    actor: str | None
    pick_from: tuple[str, str] | None
    pick_pose: Pose | None
    place_to: tuple[str, str] | None
    place_pose: Pose | None
    trigger_sensor: str | None
    trigger_state: str | None
    capacity: int


@dataclass(frozen=True)
class ResolvedCell:
    """Everything a generator needs, with no lookups and no name construction left."""

    facility_id: str
    facility_name: str
    zone: str
    zone_bounds: Aabb
    assets: tuple[ResolvedAsset, ...]
    stations: tuple[ResolvedStation, ...]
    #: The sides this zone runs, derived from ``twin.sides`` rather than declared
    #: (ADR-0041, Decision 3). One entry for a `single` zone, two for a `pair`.
    sides: tuple[ResolvedSide, ...] = ()
    #: Types not placed as instances — an end effector is fitted to an arm rather
    #: than standing somewhere, so it has a type but no pose.
    unplaced_types: tuple[AssetType, ...] = ()
    workpiece_models: tuple[str, ...] = ()
    #: The facility's material library, carried whole rather than pre-joined onto
    #: the bodies that wear it. Two generators need it and they need it in
    #: different shapes — the scene resolves a name per body, the appearance
    #: artifact emits the library itself — so the join happens at each emitter and
    #: the colour is stated once here.
    materials: tuple[Material, ...] = ()

    @property
    def is_paired(self) -> bool:
        """Whether this zone is twinned. Derived from the number of sides.

        Read through rather than restated: `twin.sides` decides how many sides
        `resolve` builds, so anything that asks "is this twinned" asks the same
        collection the partitions come from, and the two cannot disagree.
        """
        return len(self.sides) > 1

    def end_effector_type(self, type_id: str) -> AssetType | None:
        return next(
            (t for t in self.unplaced_types if t.id == type_id and t.category == "end_effector"),
            None,
        )

    @property
    def workpiece_types(self) -> tuple[AssetType, ...]:
        """The types named by ``workpiece_models``, resolved to their geometry.

        Delegated to `cite_tools.model.workpieces` rather than walked here, and
        the delegation is the point (ADR-0052 §A.7). This used to be one of two
        routes through ``workpiece_models`` — the other inside
        ``cite_tools.validate.physical`` — and under option F the generator and
        the validator answer one physical question from this list, so a
        disagreement between the routes is a model that validates against one
        part and a cell that judges against another.
        """
        return workpiece_types(self.workpiece_models, self.unplaced_types)

    @property
    def workpiece_widths(self) -> WorkpieceWidths:
        """How wide the parts this facility handles are, as one interval.

        What the generated bring-up plan states at facility level and L3 judges a
        stall against (ADR-0052 §A.4). Read through the same accessor the
        validator reads, so the window the cell applies and the window the model
        was checked against cannot drift apart.
        """
        return workpiece_widths(self.workpiece_models, self.unplaced_types)

    def material(self, material_id: str) -> Material:
        """One entry of the material library, by the name a body carries.

        Raises rather than returning ``None``: `unknown-material` runs first and
        is an ERROR, so by the time a generator asks, the name has been checked.
        A `None` here would be emitted as no appearance at all, which is the
        black cell this library was written to fix — silently, and in the one
        place that could still have said so.
        """
        found = next((m for m in self.materials if m.id == material_id), None)
        if found is None:
            raise ResolveError(
                f"no material named {material_id!r} in the facility's library; "
                "referential validation reports this as `unknown-material` and "
                "must run before a generator asks"
            )
        return found

    def asset(self, asset_id: str) -> ResolvedAsset | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def of_category(self, category: str) -> tuple[ResolvedAsset, ...]:
        return tuple(a for a in self.assets if a.asset_type.category == category)


def _joint_names(
    asset: AssetInstance, asset_type: AssetType, spec: ControllerSpec
) -> tuple[str, ...]:
    if spec.joints == "none":
        return ()
    if spec.joints == "arm":
        if asset_type.kinematics is None:
            raise ResolveError(
                f"type {asset_type.id!r} declares an arm controller but no kinematics"
            )
        return tuple(ids.joint(asset.id, s) for s in asset_type.kinematics.joint_suffixes)
    if spec.joints == "axis":
        raise ResolveError(f"an axis controller on {asset.id!r} is resolved with its carrier")
    # end_effector: the vendor gripper exposes exactly one actuated joint; its
    # fingers follow through URDF <mimic> tags rather than being commanded.
    return (ids.joint(asset.id, "drive_joint"),)


def program_steps(model: FacilityModel, instance: AssetInstance) -> tuple[blockly.Step, ...]:
    """The program ``instance`` runs, read and converted, or ``()`` if it names none.

    The one place a program is read against the facts its units convert with —
    the arm's joint count and velocity limit, and the fitted gripper's linkage —
    so that the validator and the generator read one answer (ADR-0067). Raises
    `blockly.BlocklyError` when the program cannot be read; referential
    validation reports that as `program-refused` before anything is generated.
    """
    configuration = instance.configuration
    path = getattr(configuration, "program", None)
    if path is None:
        return ()
    text = model.program(path)
    asset_type = model.asset_type(instance.type)
    if text is None or asset_type is None or asset_type.kinematics is None:
        raise blockly.BlocklyError(f"asset {instance.id!r}: program {path!r} was not loaded")
    kinematics = asset_type.kinematics
    if kinematics.max_joint_velocity_rad_s is None:
        raise blockly.BlocklyError(
            f"type {asset_type.id!r} states no `kinematics.max_joint_velocity_rad_s`, so a "
            "program's joint speed cannot be turned into a velocity scaling"
        )
    effector = (
        None if instance.end_effector is None else model.asset_type(instance.end_effector.type)
    )
    if effector is None or effector.grasp is None:
        raise blockly.BlocklyError(
            f"asset {instance.id!r} fits no end effector with a grasp specification, so a "
            "program's gripper positions cannot be turned into widths"
        )
    return blockly.parse(
        text,
        dof=kinematics.dof,
        linkage=effector.grasp.linkage,
        max_joint_velocity_rad_s=kinematics.max_joint_velocity_rad_s,
    )


def _axis(
    model: FacilityModel, instance: AssetInstance, world: Pose
) -> tuple[ResolvedAxis, AssetType] | None:
    """The track ``instance`` stands on, or None when its parent is not one."""
    if instance.pose.frame == ids.WORLD_FRAME:
        return None
    parent_id = instance.pose.frame.split("/", 1)[0]
    track = model.asset(parent_id)
    track_type = None if track is None else model.asset_type(track.type)
    if track is None or track_type is None or track_type.axis is None:
        return None
    spec = track_type.axis
    plugins: list[tuple[str, str | None]] = []
    for side, backend_id in (
        (ids.PLANT_SIDE, track.hardware.backend),
        (ids.COUNTERPART_SIDE, track.hardware.effective_counterpart_backend),
    ):
        backend = track_type.hardware_backends.get(backend_id)
        if backend is None:
            raise ResolveError(
                f"track {track.id!r} selects backend {backend_id!r}, which type "
                f"{track_type.id!r} does not declare"
            )
        plugins.append((side, backend.ros2_control_plugin))
    track_world = _resolve_world_pose(model, track.id)
    rotation = np.asarray(world.to_matrix())[:3, :3].T @ np.asarray(track_world.to_matrix())[:3, :3]
    direction = rotation @ np.asarray(spec.direction, dtype=float)
    direction = direction / np.linalg.norm(direction)
    controller = next((c for c in track_type.controllers if c.joints == "axis"), None)
    if controller is None:
        raise ResolveError(f"type {track_type.id!r} declares an axis and no controller for it")
    return (
        ResolvedAxis(
            asset=track.id,
            joint=ids.joint(track.id, spec.joint_suffix),
            carriage_link=ids.link(track.id, spec.carriage_link_suffix),
            direction=tuple(round(float(v), 9) + 0.0 for v in direction),  # type: ignore[arg-type]
            stroke_m=spec.stroke_m,
            max_speed_mps=spec.max_speed_mps,
            max_force_n=spec.max_force_n,
            carriage_mass_kg=spec.carriage_mass_kg,
            carriage_size_m=spec.carriage_size_m,
            goal_tolerance_m=spec.goal_tolerance_m,
            plugins=tuple(plugins),
            controller=ids.controller(track.id, controller.suffix),
            command_topic=ids.interface(
                instance.zone,
                instance.id,
                f"{ids.controller(track.id, controller.suffix)}/joint_trajectory",
            ),
        ),
        track_type,
    )


def index_offset_m(model: FacilityModel, asset: AssetInstance) -> float:
    """How far past its mounting frame an indexing beam stands, along the belt.

    THE NUMBER THIS REPLACED. ``beam_c1_out`` used to be authored 0.050 m
    *upstream* of ``conveyor_1/outfeed``, which is the point
    ``station_transfer_2`` picks from. Measured, the belt stopped with the cube
    parked at x = 1.531 against a pick point at 1.600 — 0.069 m short — and
    ``arm_2`` closed on air at ``commanded 45.0 mm, reached 46.0 mm,
    stalled=false``, four runs out of four.

    That 0.069 m was the point test's error, not this offset's, and correcting
    the plugin made the shortfall WORSE rather than better: a beam that breaks on
    a leading edge trips half a part-length sooner, so the same -0.050 mounting
    would have parked the part at 1.523, 0.077 m short. Getting the physics right
    is what created the need for this function.

    The tempting repair, twice refused before this and refused here, was to slide
    the beam until the scenario passed. A real through beam breaks on the leading
    edge too, so an offset fitted against the old point test would have been
    compensation for a simulator artefact, and the physical cell would have
    parked its parts about 25 mm elsewhere (P2).

    WHAT IT IS INSTEAD. A part travelling towards a beam breaks it when its
    leading edge reaches the near side of the beam, so at the moment of the break
    the part's centre is half a part-length plus half a beam-width short of the
    beam's centreline. Mount the beam that far PAST the point the part must stop
    on and the two cancel: the part comes to rest with its centre on the pick
    point. That is also how a photo-eye is set on a physical indexing line — you
    put it where the leading edge of a correctly placed part will be — so the
    same arithmetic describes both cells, which is the property that matters.

    Every term is read from the model. The part's length is the widest horizontal
    extent of the work-pieces the facility declares, the beam's width is the
    sensor's own, and the direction is the belt's. Nothing here is authored, so
    nothing here can disagree with the part (P1).

    THE WIDEST, not the narrowest or the mean: a part longer than assumed breaks
    the beam early and parks short, which is the failure above, so the
    conservative reading is the largest one. A facility declaring parts of
    several different lengths cannot index them all to one point with one beam —
    on hardware either — and this picks the reading that fails safe rather than
    the one that fails silently. How far off the shorter parts then park is not
    yet checked, deliberately: the bound is a grasp tolerance, and
    ``_indexing_beams_stop_at_a_pick_point`` in ``cite_tools.validate.geometric``
    records why it is better left unwritten than guessed.

    Zero for every asset that is not an indexing beam, so the pose resolution
    below is unchanged for all of them.

    ZERO ALSO WHEN IT CANNOT BE DERIVED — a beam mounted on something that is not
    a driven belt, or a facility that declares no work-piece geometry — rather
    than raising. Resolution runs before validation, so raising here would
    replace every geometric finding with a traceback: the one report that could
    name the problem is the one that would not run. ``beam-cannot-index`` in
    ``cite_tools.validate.geometric`` reports each of these cases against the
    same conditions, and nothing is generated from a model that fails it.
    """
    configuration = asset.configuration
    if configuration is None or configuration.kind != "sensor":
        return 0.0
    if not configuration.indexes_workpiece:
        return 0.0
    if asset.pose.frame == ids.WORLD_FRAME:
        return 0.0

    parent = model.asset(asset.pose.frame.split("/", 1)[0])
    parent_type = None if parent is None else model.asset_type(parent.type)
    if parent is None or parent_type is None or parent_type.category != "conveyor":
        return 0.0

    drive = parent.configuration
    if drive is None or drive.kind != "conveyor":
        return 0.0
    # A belt's own +x is its forward direction; the frames the sensor is mounted
    # against share the belt's axes, so the stand-off is a signed offset along
    # local x and needs no world-frame rotation.
    travel = 1.0 if drive.direction == "forward" else -1.0

    length = _longest_workpiece_m(model)
    if length is None:
        return 0.0
    return travel * (length / 2.0 + configuration.beam_width_m / 2.0)


def _longest_workpiece_m(model: FacilityModel) -> float | None:
    """The largest horizontal extent of anything this facility handles.

    ``None`` when no declared work-piece has readable extents — a mesh part, or a
    facility that declares none — so the caller refuses rather than inventing a
    length.
    """
    extents = [
        body.horizontal_extents_m[1]
        for name in model.facility.workpiece_models
        if (asset_type := model.asset_type(name)) is not None
        and asset_type.category == "workpiece"
        and (body := asset_type.description.body) is not None
        and body.horizontal_extents_m is not None
    ]
    return max(extents) if extents else None


def _resolve_world_pose(model: FacilityModel, asset_id: str, seen: tuple[str, ...] = ()) -> Pose:
    if asset_id in seen:
        raise ResolveError(f"placement cycle through {asset_id!r}")
    asset = model.asset(asset_id)
    if asset is None:
        raise ResolveError(f"no asset named {asset_id!r}")

    # The derived stand-off is folded into the LOCAL pose, before the parent
    # frame is applied, so it runs along the belt whatever direction the belt
    # faces in the world — and so that one world pose feeds the housing's
    # description, the beam plugin and every geometric rule alike. Computing it
    # in the world generator instead would have let the drawn housing and the
    # beam it emits describe different places, which is the mis-modelling the
    # plugin's own header warns about.
    local_xyz = asset.pose.xyz_m
    offset = index_offset_m(model, asset)
    if offset != 0.0:
        local_xyz = (local_xyz[0] + offset, local_xyz[1], local_xyz[2])
    local = Pose(xyz_m=local_xyz, rpy_rad=asset.pose.rpy_rad)
    # Calibration is applied here and only here, as a body-frame post-multiply
    # (ADR-0020), so a Phase 2 measurement changes every derived artifact at once
    # instead of being applied ad hoc at runtime.
    correction = Pose(
        xyz_m=asset.registration.correction.xyz_m,
        rpy_rad=asset.registration.correction.rpy_rad,
    )

    if asset.pose.frame == ids.WORLD_FRAME:
        return local.corrected_by(correction)

    parent_id, frame_id = asset.pose.frame.split("/", 1)
    parent_world = _resolve_world_pose(model, parent_id, (*seen, asset_id))
    parent_type = model.asset_type(model.asset(parent_id).type)  # type: ignore[union-attr]
    if parent_type is None:
        raise ResolveError(f"asset {parent_id!r} has no known type")
    named = next((f for f in parent_type.frames if f.id == frame_id), None)
    if named is None:
        raise ResolveError(f"asset {parent_id!r} has no frame {frame_id!r}")

    frame_pose = Pose(xyz_m=named.xyz_m, rpy_rad=named.rpy_rad)
    return parent_world.compose(frame_pose).compose(local).corrected_by(correction)


def resolve(model: FacilityModel, zone_id: str) -> ResolvedCell:
    """Resolve one zone. Referential validation must have passed first."""
    zone = model.zone(zone_id)
    if zone is None:
        raise ResolveError(f"no zone named {zone_id!r}")

    assets: list[ResolvedAsset] = []
    for instance in model.assets_in(zone_id):
        asset_type = model.asset_type(instance.type)
        if asset_type is None:
            raise ResolveError(f"asset {instance.id!r} has unknown type {instance.type!r}")

        world = _resolve_world_pose(model, instance.id)

        frames = {
            f.id: world.compose(Pose(xyz_m=f.xyz_m, rpy_rad=f.rpy_rad)) for f in asset_type.frames
        }

        # A track's controllers are loaded by the arm it carries, below, and
        # never by a controller manager of the track's own.
        specs = (
            []
            if asset_type.category == "linear_axis"
            else [(spec, OWN) for spec in asset_type.controllers]
        )
        # An end-effector's controllers belong to the arm that carries it: they
        # are loaded into the arm's controller manager and named with the arm's
        # prefix, because that is the asset an operator addresses.
        if instance.end_effector is not None:
            effector_type = model.asset_type(instance.end_effector.type)
            if effector_type is not None:
                specs.extend((spec, END_EFFECTOR) for spec in effector_type.controllers)

        controllers = [
            ResolvedController(
                name=ids.controller(instance.id, spec.suffix),
                type=spec.type,
                stage=spec.stage,
                joints=_joint_names(instance, asset_type, spec),
                command_interfaces=tuple(spec.command_interfaces),
                state_interfaces=tuple(spec.state_interfaces),
                parameters=dict(spec.parameters),
                constraints=spec.constraints,
                origin=origin,
            )
            for spec, origin in sorted(specs, key=lambda s: (s[0].stage, s[0].suffix))
        ]

        # A track's controller is loaded by the controller manager of the arm on
        # its carriage, because its joint is in that arm's description
        # (ADR-0067). Named for the TRACK, so the joint and the controller say
        # which asset they drive.
        axis = None
        if asset_type.category == "robot":
            carried = _axis(model, instance, world)
            if carried is not None:
                axis, track_type = carried
                assert track_type.axis is not None
                controllers += [
                    ResolvedController(
                        name=ids.controller(axis.asset, spec.suffix),
                        type=spec.type,
                        stage=spec.stage,
                        joints=(axis.joint,),
                        command_interfaces=tuple(spec.command_interfaces),
                        state_interfaces=tuple(spec.state_interfaces),
                        parameters=dict(spec.parameters),
                        # In the joint's own units, which for this joint are
                        # metres; `TrajectoryConstraints` names its fields for
                        # the revolute case it was written for.
                        constraints=TrajectoryConstraints(
                            goal_time_s=track_type.axis.goal_time_s,
                            goal_tolerance_rad=track_type.axis.goal_tolerance_m,
                            trajectory_tolerance_rad=track_type.axis.trajectory_tolerance_m,
                            stopped_velocity_tolerance_rad_s=0.0,
                        ),
                        origin=AXIS,
                    )
                    for spec in track_type.controllers
                    if spec.joints == "axis"
                ]
                controllers.sort(key=lambda c: (c.stage, c.name))

        parent_asset, parent_frame = (
            (None, None)
            if instance.pose.frame == ids.WORLD_FRAME
            else tuple(instance.pose.frame.split("/", 1))  # type: ignore[assignment]
        )

        assets.append(
            ResolvedAsset(
                id=instance.id,
                zone=zone_id,
                asset_type=asset_type,
                instance=instance,
                world_pose=world,
                parent_asset=parent_asset,
                parent_frame=parent_frame,
                prefix=ids.prefix(instance.id),
                namespace=ids.namespace(zone_id, instance.id),
                frames=frames,
                controllers=tuple(controllers),
                axis=axis,
                program=program_steps(model, instance),
            )
        )

    by_id = {a.id: a for a in assets}

    def point(asset_id: str | None, frame_id: str | None) -> Pose | None:
        if asset_id is None or frame_id is None:
            return None
        resolved = by_id.get(asset_id)
        if resolved is None:
            raise ResolveError(f"station references asset {asset_id!r}, which is not in this zone")
        pose = resolved.frames.get(frame_id)
        if pose is None:
            raise ResolveError(f"asset {asset_id!r} has no frame {frame_id!r}")
        return pose

    stations = tuple(
        ResolvedStation(
            id=s.id,
            zone=s.zone,
            type=s.type,
            actor=s.actor,
            pick_from=(s.pick_from.asset, s.pick_from.frame) if s.pick_from else None,
            pick_pose=point(
                s.pick_from.asset if s.pick_from else None,
                s.pick_from.frame if s.pick_from else None,
            ),
            place_to=(s.place_to.asset, s.place_to.frame) if s.place_to else None,
            place_pose=point(
                s.place_to.asset if s.place_to else None, s.place_to.frame if s.place_to else None
            ),
            trigger_sensor=s.trigger.sensor if s.trigger else None,
            trigger_state=s.trigger.state if s.trigger else None,
            capacity=s.capacity,
        )
        for s in model.stations
        if s.zone == zone_id
    )

    # `single` yields one side and `pair` yields two, in `ids.SIDES` order. The
    # count is the only thing L0 states; which sides exist and what they are
    # called is mechanism, so the names are read from `ids` and never authored.
    side_count = 1 if zone.twin.sides == "single" else len(ids.SIDES)
    sides = tuple(
        ResolvedSide(
            name=name,
            gz_partition=ids.partition(zone_id, name),
            domain_offset=ids.domain_offset(name),
        )
        for name in ids.SIDES[:side_count]
    )

    return ResolvedCell(
        facility_id=model.facility.id,
        facility_name=model.facility.name,
        zone=zone_id,
        zone_bounds=Aabb(min_m=zone.bounds.min_m, max_m=zone.bounds.max_m),
        assets=tuple(sorted(assets, key=lambda a: a.id)),
        stations=stations,
        sides=sides,
        unplaced_types=tuple(sorted(model.types, key=lambda t: t.id)),
        workpiece_models=tuple(sorted(model.facility.workpiece_models)),
        materials=model.materials,
    )
