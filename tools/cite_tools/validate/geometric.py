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


def check(cell: ResolvedCell) -> list[Finding]:
    findings: list[Finding] = []
    findings += _assets_inside_zone(cell)
    findings += _no_overlapping_bodies(cell)
    findings += _stations_are_reachable(cell)
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
    findings: list[Finding] = []
    for asset in cell.assets:
        if not cell.zone_bounds.contains(asset.world_pose.xyz_m):
            findings.append(
                error(
                    "outside-zone",
                    f"assets.{asset.id}.pose",
                    f"resolves to {_fmt(asset.world_pose)} which is outside zone " f"{cell.zone!r}",
                    f"Zone bounds are {cell.zone_bounds.min_m} to {cell.zone_bounds.max_m}. "
                    "Either the pose is wrong or the zone needs to grow.",
                )
            )
    return findings


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
    x, y, z = pose.xyz_m
    return f"({x:.3f}, {y:.3f}, {z:.3f})"
