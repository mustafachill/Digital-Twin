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
from cite_tools.model.schema import AssetInstance, AssetType, ControllerSpec


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
    #: Types not placed as instances — an end effector is fitted to an arm rather
    #: than standing somewhere, so it has a type but no pose.
    unplaced_types: tuple[AssetType, ...] = ()
    workpiece_models: tuple[str, ...] = ()

    def end_effector_type(self, type_id: str) -> AssetType | None:
        return next(
            (t for t in self.unplaced_types if t.id == type_id and t.category == "end_effector"),
            None,
        )

    @property
    def workpiece_types(self) -> tuple[AssetType, ...]:
        """The types named by ``workpiece_models``, resolved to their geometry.

        ``workpiece_models`` carries names because a name is what the simulator
        matches on. A rule that needs to know how wide a part is needs the type
        behind the name, and resolving it here rather than at each call site
        keeps the two rules that do from each writing their own lookup.

        A name with no type behind it is dropped rather than raised on:
        ``referential`` reports it as ``unknown-type`` and runs first, so by the
        time a generator or a geometric rule sees this the model has been
        checked. Dropping it means a rule sized from work-piece geometry reports
        nothing rather than a wrong bound.
        """
        by_id = {t.id: t for t in self.unplaced_types}
        return tuple(
            asset_type
            for name in self.workpiece_models
            if (asset_type := by_id.get(name)) is not None and asset_type.category == "workpiece"
        )

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


def _resolve_world_pose(model: FacilityModel, asset_id: str, seen: tuple[str, ...] = ()) -> Pose:
    if asset_id in seen:
        raise ResolveError(f"placement cycle through {asset_id!r}")
    asset = model.asset(asset_id)
    if asset is None:
        raise ResolveError(f"no asset named {asset_id!r}")

    local = Pose(xyz_m=asset.pose.xyz_m, rpy_rad=asset.pose.rpy_rad)
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

    return ResolvedCell(
        facility_id=model.facility.id,
        facility_name=model.facility.name,
        zone=zone_id,
        zone_bounds=Aabb(min_m=zone.bounds.min_m, max_m=zone.bounds.max_m),
        assets=tuple(sorted(assets, key=lambda a: a.id)),
        stations=stations,
        unplaced_types=tuple(sorted(model.types, key=lambda t: t.id)),
        workpiece_models=tuple(sorted(model.facility.workpiece_models)),
    )
