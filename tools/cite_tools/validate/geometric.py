"""Geometric validation: is the layout physically sensible?

These checks exist because the failures they catch are silent. A station whose
pick point is 20 mm beyond the arm's reach produces a model that validates, a
world that loads, a simulation that runs — and a planner that fails at that one
station, at run time, with an error about inverse kinematics rather than about
the layout.

The reach check in particular is the one that pays for this module. It is the
difference between finding a layout mistake in a second on a laptop and finding
it after a ten-minute container build and a simulation bring-up.
"""

from __future__ import annotations

from itertools import combinations

from cite_tools.model.geometry import Aabb, Pose
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.validate import Finding, error, warning

#: Fraction of an arm's maximum reach beyond which a station is reported. An arm
#: working at the very edge of its envelope has no room for approach and retreat
#: clearance, and its Jacobian is badly conditioned there, so "reachable" and
#: "usable" are not the same number.
COMFORTABLE_REACH_FRACTION = 0.85

#: Metres of designed air between two bodies that are not meant to touch. Far
#: larger than any Phase-2 registration correction, which is millimetre-scale, so
#: a measured layout cannot turn a designed gap into a penetration.
MIN_CLEARANCE_M = 0.020

#: Half-width and height of the corridor a gripper needs above a pick or place
#: point. The xArm parallel gripper opens to 85 mm, so 100 mm each side covers
#: the pads plus the knuckles, and 250 mm of height covers approach and retreat.
#: Square rather than cylindrical, deliberately: a square is the conservative
#: shape, and a conservative approach check fails on a laptop where an optimistic
#: one lets the gripper find the obstruction at run time.
APPROACH_HALF_WIDTH_M = 0.100
APPROACH_HEIGHT_M = 0.250


def check(cell: ResolvedCell) -> list[Finding]:
    findings: list[Finding] = []
    findings += _assets_inside_zone(cell)
    findings += _frames_lie_on_their_own_geometry(cell)
    findings += _no_overlapping_bodies(cell)
    findings += _stations_are_reachable(cell)
    findings += _approach_corridors_are_clear(cell)
    findings += _sensors_sit_on_what_they_watch(cell)
    return findings


def _bounding_box(asset: ResolvedAsset) -> Aabb | None:
    """An axis-aligned box around an authored body, in world coordinates.

    Only bodies we author have known extents; a vendor description's geometry
    lives in files this layer deliberately does not read (L1 owns geometry).
    Returning None for those is honest — it means the overlap check does not
    cover them, rather than pretending to.
    """
    body = asset.asset_type.description.body
    if body is None or body.collision.kind != "box":
        return None
    half = [s / 2.0 for s in body.collision.size_m]
    centre = asset.world_pose.xyz_m
    # Axis-aligned only. Every fixture in this cell is axis-aligned or yawed by a
    # right angle, so this is exact here; a body at an arbitrary yaw would need
    # its extents swelling, and that is worth doing when such a body appears.
    return Aabb(
        min_m=(centre[0] - half[0], centre[1] - half[1], centre[2]),
        max_m=(centre[0] + half[0], centre[1] + half[1], centre[2] + body.collision.size_m[2]),
    )


def _assets_inside_zone(cell: ResolvedCell) -> list[Finding]:
    """The whole body, not just its origin.

    Testing the pose alone cannot report the thing this rule's name promises: a
    0.6 m table whose origin sits 0.65 m inside the boundary still puts a third
    of itself outside the cell, and the check passed it. Where a body has no
    known extents — a vendor description, whose geometry this layer does not read
    — the origin is all there is, and the finding says so rather than claiming
    coverage it does not have.
    """
    findings: list[Finding] = []
    for asset in cell.assets:
        box = _bounding_box(asset)
        if box is not None:
            if cell.zone_bounds.contains_box(box):
                continue
            detail = (
                f"has collision geometry spanning {_fmt_triple(box.min_m)} to "
                f"{_fmt_triple(box.max_m)}, which leaves zone {cell.zone!r}"
            )
        else:
            if cell.zone_bounds.contains(asset.world_pose.xyz_m):
                continue
            detail = f"resolves to {_fmt(asset.world_pose)} which is outside zone {cell.zone!r}"
        findings.append(
            error(
                "outside-zone",
                f"assets.{asset.id}.pose",
                detail,
                f"Zone bounds are {cell.zone_bounds.min_m} to {cell.zone_bounds.max_m}. "
                "Either the pose is wrong or the zone needs to grow.",
            )
        )
    return findings


def _frames_lie_on_their_own_geometry(cell: ResolvedCell) -> list[Finding]:
    """A named frame that is nowhere near the body it is declared on.

    This is the check that would have caught the conveyor in one second. Its
    `surface`, `infeed` and `outfeed` frames were all at z = 0.600 while its
    collision box was 0.100 m tall, so the declared work surface floated half a
    metre above the geometry: a place released the work-piece into empty air, and
    the break beam watching the belt sat 0.58 m above it and could never be
    broken. Nothing reported any of it — the model validated, the world loaded,
    and the line simply never worked.

    Only frames on bodies we author are checkable. A frame naming a `link`
    belongs to a vendor description whose geometry this layer does not read, so
    reporting on it would mean inventing an answer.
    """
    findings: list[Finding] = []
    for asset in cell.assets:
        body = asset.asset_type.description.body
        if body is None or body.collision.kind != "box":
            continue
        size = body.collision.size_m
        # The body's pose names the point it stands on and a type frame is
        # declared in that same reference, so the box spans [0, height] in z and
        # is centred on the origin in x and y.
        lower = (-size[0] / 2.0, -size[1] / 2.0, 0.0)
        upper = (size[0] / 2.0, size[1] / 2.0, size[2])
        for named in sorted(asset.asset_type.frames, key=lambda f: f.id):
            if named.link is not None:
                continue
            outside = [
                axis
                for axis, (lo, value, hi) in enumerate(zip(lower, named.xyz_m, upper, strict=True))
                if value < lo or value > hi
            ]
            if not outside:
                continue
            findings.append(
                error(
                    "frame-outside-geometry",
                    f"types.{asset.asset_type.id}.frames.{named.id}",
                    f"is declared at {_fmt_triple(named.xyz_m)}, outside this type's own "
                    f"collision box spanning {_fmt_triple(lower)} to {_fmt_triple(upper)} "
                    f"(axes {', '.join('xyz'[a] for a in outside)})",
                    "A frame and the body it is declared on must describe the same "
                    "object. When they do not, a station reaches for a surface that is "
                    "not there and the work-piece is released into empty space.",
                )
            )
    # One finding per type rather than per instance: three conveyors of one type
    # share one mistake, and reporting it three times buries it.
    return _unique_by_where(findings)


def _unique_by_where(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    unique: list[Finding] = []
    for finding in findings:
        if finding.where not in seen:
            seen.add(finding.where)
            unique.append(finding)
    return unique


def _no_overlapping_bodies(cell: ResolvedCell) -> list[Finding]:
    findings: list[Finding] = []
    boxes = [(a, _bounding_box(a)) for a in cell.assets]
    for (a, box_a), (b, box_b) in combinations(boxes, 2):
        if box_a is None or box_b is None:
            continue
        # An asset placed on another's frame is meant to be in contact with it.
        if b.parent_asset == a.id or a.parent_asset == b.id:
            continue
        if box_a.intersects(box_b):
            findings.append(
                error(
                    "overlapping-assets",
                    f"assets.{a.id}",
                    f"collision geometry overlaps {b.id!r}",
                    "Two solid bodies occupying the same volume make the physics engine "
                    "resolve a penetration on the first step, which presents as objects "
                    "leaping apart at start-up.",
                )
            )
            continue
        gap = box_a.separation(box_b)
        if gap < MIN_CLEARANCE_M:
            findings.append(
                warning(
                    "insufficient-clearance",
                    f"assets.{a.id}",
                    f"stands {gap * 1000.0:.1f} mm from {b.id!r}",
                    f"Design in at least {MIN_CLEARANCE_M * 1000.0:.0f} mm. Exact face "
                    "contact passes the overlap check above only because that check uses "
                    "a strict inequality; a millimetre of Phase-2 registration correction "
                    "turns this pair into a penetration, and the physics engine resolves "
                    "a penetration by flinging both bodies apart.",
                )
            )
    return findings


def _stations_are_reachable(cell: ResolvedCell) -> list[Finding]:
    findings: list[Finding] = []
    for station in cell.stations:
        if station.actor is None:
            continue
        actor = cell.asset(station.actor)
        if actor is None or actor.asset_type.kinematics is None:
            continue
        reach = actor.asset_type.kinematics.max_reach_m
        base = actor.frames.get("base", actor.world_pose)

        for label, target in (("pick_from", station.pick_pose), ("place_to", station.place_pose)):
            if target is None:
                continue
            distance = base.distance_to(target)
            if distance > reach:
                findings.append(
                    error(
                        "unreachable-station",
                        f"stations.{station.id}.{label}",
                        f"is {distance:.3f} m from {actor.id!r}, whose reach is {reach:.3f} m",
                        "The planner will fail at this station with an inverse-kinematics "
                        "error that says nothing about the layout. Move the asset or the arm.",
                    )
                )
            elif distance > reach * COMFORTABLE_REACH_FRACTION:
                findings.append(
                    warning(
                        "reach-margin",
                        f"stations.{station.id}.{label}",
                        f"is {distance:.3f} m from {actor.id!r}, "
                        f"{distance / reach:.0%} of its {reach:.3f} m reach",
                        "Reachable, but with little room for approach and retreat, and near "
                        "the edge of the envelope the arm's conditioning is poor.",
                    )
                )
    return findings


def _approach_corridors_are_clear(cell: ResolvedCell) -> list[Finding]:
    """Something solid standing where the gripper has to come down.

    The reach check asks whether the arm can get its tool to the point. This asks
    whether anything is in the way of getting there, which is a different
    question and the one nobody was asking: a sensor housing stood 30 mm from a
    pick point in x and rose 200 mm above the pick plane, straight through the
    descent. The planner refuses that approach at run time with a message about
    inverse kinematics or collision, and says nothing about the layout.

    The asset owning the pick or place frame is excluded. The point lies on its
    surface by construction, so it is always in contact with the base of the
    corridor, and reporting it would make this rule fire at every station.
    """
    findings: list[Finding] = []
    boxes = [(a, _bounding_box(a)) for a in cell.assets]
    for station in cell.stations:
        if station.actor is None:
            continue
        for label, point, owner in (
            ("pick_from", station.pick_pose, station.pick_from),
            ("place_to", station.place_pose, station.place_to),
        ):
            if point is None:
                continue
            corridor = _approach_corridor(point)
            owner_id = owner[0] if owner else None
            for asset, box in boxes:
                if box is None or asset.id in (owner_id, station.actor):
                    continue
                if not box.intersects(corridor):
                    continue
                findings.append(
                    error(
                        "approach-obstruction",
                        f"stations.{station.id}.{label}",
                        f"has {asset.id!r} inside the "
                        f"{APPROACH_HALF_WIDTH_M * 1000.0:.0f} mm corridor above "
                        f"{_fmt(point)}",
                        "The gripper has to descend onto this point and retreat from it. "
                        "Move the obstruction, or the planner refuses the approach at run "
                        "time with an error that names inverse kinematics rather than the "
                        "layout.",
                    )
                )
    return findings


def _approach_corridor(point: Pose) -> Aabb:
    """The volume a gripper needs above a pick or place point."""
    x, y, z = point.xyz_m
    half = APPROACH_HALF_WIDTH_M
    return Aabb(
        min_m=(x - half, y - half, z),
        max_m=(x + half, y + half, z + APPROACH_HEIGHT_M),
    )


def _sensors_sit_on_what_they_watch(cell: ResolvedCell) -> list[Finding]:
    """A sensor placed in world coordinates rather than against its conveyor.

    Not an error — it is legal and occasionally right. It is a warning because it
    is how a sensor and the belt it watches drift apart: move the belt, and a
    world-placed sensor stays behind, silently watching empty air.
    """
    findings: list[Finding] = []
    for asset in cell.of_category("sensor"):
        if asset.parent_asset is None:
            findings.append(
                warning(
                    "unanchored-sensor",
                    f"assets.{asset.id}.pose.frame",
                    "is placed in world coordinates rather than relative to the asset "
                    "it observes",
                    "Move the conveyor and this sensor stays behind. Place it against a "
                    "frame on that conveyor instead.",
                )
            )
    return findings


def _fmt(pose: Pose) -> str:
    return _fmt_triple(pose.xyz_m)


def _fmt_triple(values: tuple[float, ...]) -> str:
    return "(" + ", ".join(f"{v:.3f}" for v in values) + ")"
