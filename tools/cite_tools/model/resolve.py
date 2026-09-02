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

from cite_tools.model import ids
from cite_tools.model.geometry import Aabb, Pose
from cite_tools.model.loader import FacilityModel
from cite_tools.model.schema import (
    AssetInstance,
    AssetType,
    ControllerSpec,
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

    @property
    def ros2_control_plugin(self) -> str:
        backend = self.asset_type.hardware_backends.get(self.instance.hardware.backend)
        if backend is None:
            raise ResolveError(
                f"asset {self.id!r} selects backend {self.instance.hardware.backend!r}, "
                f"which type {self.asset_type.id!r} does not declare"
            )
        return backend.ros2_control_plugin

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
    # end_effector: the vendor gripper exposes exactly one actuated joint; its
    # fingers follow through URDF <mimic> tags rather than being commanded.
    return (ids.joint(asset.id, "drive_joint"),)


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

        specs = list(asset_type.controllers)
        # An end-effector's controllers belong to the arm that carries it: they
        # are loaded into the arm's controller manager and named with the arm's
        # prefix, because that is the asset an operator addresses.
        if instance.end_effector is not None:
            effector_type = model.asset_type(instance.end_effector.type)
            if effector_type is not None:
                specs.extend(effector_type.controllers)

        controllers = tuple(
            ResolvedController(
                name=ids.controller(instance.id, spec.suffix),
                type=spec.type,
                stage=spec.stage,
                joints=_joint_names(instance, asset_type, spec),
                command_interfaces=tuple(spec.command_interfaces),
                state_interfaces=tuple(spec.state_interfaces),
                parameters=dict(spec.parameters),
                constraints=spec.constraints,
            )
            for spec in sorted(specs, key=lambda s: (s.stage, s.suffix))
        )

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
                controllers=controllers,
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
    )
