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

#: Metres of support that must remain beyond the far edge of a work-piece once it
#: has been set down on a pick or place point.
#:
#: The bare physical requirement is that the footprint be wholly supported, which
#: is a margin of half the work-piece's widest horizontal extent and no more.
#: That bound is *neutral*, not safe: at exactly half a footprint the part's edge
#: is flush with the body's, its centre of mass projects onto the boundary of its
#: support polygon, and any error towards the edge tips it. This constant is the
#: designed air beyond that boundary, and it is sized against the errors that
#: exist rather than by taste — the measured release pose is accurate to about
#: 1.9 mm, and a Phase-2 registration correction is millimetre-scale, so 20 mm is
#: roughly ten times either.
#:
#: It is deliberately NOT `MIN_CLEARANCE_M`, which happens to hold the same
#: number today. That one is the gap between two bodies that must never touch;
#: this one is overlap between a body and one that is meant to rest on it. Two
#: facts that agree by coincidence, and tying them together would let a change to
#: either move the other silently.
SUPPORT_CLEARANCE_M = 0.020

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
    findings += _station_points_support_the_workpiece(cell)
    findings += _approach_corridors_are_clear(cell)
    findings += _sensors_sit_on_what_they_watch(cell)
    findings += _beams_can_see_the_workpiece(cell)
    findings += _indexing_beams_stop_at_a_pick_point(cell)
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


def _widest_workpiece_footprint_m(cell: ResolvedCell) -> float | None:
    """The largest horizontal extent of anything this facility handles.

    The widest rather than the average, because a margin has to hold for every
    part on the line, and `None` when no work-piece has known extents — a mesh
    part, or a facility that declares none — so that the rule below reports
    nothing rather than a bound it made up.
    """
    extents = [
        body.horizontal_extents_m[1]
        for asset_type in cell.workpiece_types
        if (body := asset_type.description.body) is not None
        and body.horizontal_extents_m is not None
    ]
    return max(extents) if extents else None


def _station_points_support_the_workpiece(cell: ResolvedCell) -> list[Finding]:
    """A pick or place point too close to the edge of the thing it stands on.

    THE FAILURE THIS EXISTS FOR, because it is not the one anybody expected.
    `cell_a__conveyor_1__infeed` lay exactly on the belt's leading-edge plane —
    the belt's collision box began at x = 0.450 and so did the frame. Every rule
    above passed it: the frame *is* on its own geometry, the point *is* inside
    the arm's envelope, the corridor above it *is* clear. And every work-piece
    `PlaceAt` released there was set down with half of it over the void, its
    centre of mass projecting exactly onto the boundary of its support polygon.
    It tipped about the edge and fell 0.600 m to the floor, landing at z = 0.025
    with a 90-degree pitch. `pick_and_place` failed 0 of 18, deterministically,
    and the model validated cleanly every time.

    `_frames_lie_on_their_own_geometry` could not see it and was not written to:
    it asks whether a frame is outside its body, using strict comparisons, so a
    frame lying exactly on a boundary face is inside and passes. Being on the
    boundary is right for a work *surface* and wrong for a work *point*, and the
    difference is a margin — which needs a work-piece width, which L0 did not
    record until `model/assets/types/workpieces/` existed.

    WHAT IT DOES NOT COVER, stated rather than left to be discovered. Only points
    a station names. `conveyor_3/outfeed` is the end of the line and no station
    picks from it, so nothing here checks it — but it is the same type frame as
    the two that are checked, so it moves with them. And only bodies we author:
    a vendor description's extents live in files L1 owns.
    """
    footprint = _widest_workpiece_footprint_m(cell)
    if footprint is None:
        return []
    required = footprint / 2.0 + SUPPORT_CLEARANCE_M

    findings: list[Finding] = []
    for station in cell.stations:
        for label, point, owner in (
            ("pick_from", station.pick_pose, station.pick_from),
            ("place_to", station.place_pose, station.place_to),
        ):
            if point is None or owner is None:
                continue
            asset = cell.asset(owner[0])
            if asset is None:
                continue
            box = _bounding_box(asset)
            if box is None:
                continue
            margin = min(
                min(point.xyz_m[axis] - box.min_m[axis], box.max_m[axis] - point.xyz_m[axis])
                for axis in (0, 1)
            )
            if margin >= required:
                continue
            findings.append(
                error(
                    "insufficient-support-margin",
                    f"stations.{station.id}.{label}",
                    f"is {margin * 1000.0:.1f} mm from the edge of {asset.id!r}, which "
                    f"cannot support a {footprint * 1000.0:.0f} mm work-piece "
                    f"({required * 1000.0:.1f} mm needed)",
                    f"The point resolves through frame {owner[1]!r} on type "
                    f"{asset.asset_type.id!r}; move it there, not here, or every asset of "
                    "that type keeps the fault. A part set down with its centre of mass "
                    "over the boundary of its support polygon is neutrally stable: it "
                    "tips about the edge and falls, and no layer above reports anything, "
                    f"because the release itself succeeded. {required * 1000.0:.1f} mm is "
                    f"half the work-piece ({footprint / 2.0 * 1000.0:.1f} mm) plus "
                    f"{SUPPORT_CLEARANCE_M * 1000.0:.0f} mm of designed margin.",
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


def _shortest_workpiece_m(cell: ResolvedCell) -> float | None:
    """The height of the shortest part this facility handles.

    The shortest rather than the tallest, because the rule below asks what a beam
    can still see, and the part that walks under a beam is the short one.
    """
    heights = [
        extent
        for asset_type in cell.workpiece_types
        if (body := asset_type.description.body) is not None
        and (extent := body.vertical_extent_m) is not None
    ]
    return min(heights) if heights else None


def _beams_can_see_the_workpiece(cell: ResolvedCell) -> list[Finding]:
    """A beam mounted higher than the part it is supposed to detect.

    THE FAILURE THIS EXISTS FOR. A through beam is broken by a body that reaches
    its line, so a beam standing above the top of every part on the line can
    never be broken at all — and a line whose stations act on detection then
    simply never acts. It is the quietest failure in the cell: the model
    validates, the world loads, the belt runs, and a station waits for ever.

    It has happened. An 80 mm mounting height above the belt was tried against a
    50 mm cube, and the sensor could not be broken by anything the facility
    declared. It was caught by running the line, which is the expensive way.

    The height is measured against the frame the sensor is mounted on, which is
    the working surface a part rests on, so it is directly comparable with the
    part's own height. Only sensors anchored to another asset are checked: a beam
    placed in world coordinates has no surface to be a height above, and
    ``unanchored-sensor`` already reports that.

    Half the beam's own width counts, because a beam is thick: a part whose top
    reaches the lower edge of the spot breaks it. That is the same edge the
    plugin tests and the same one a real sensor responds to.
    """
    shortest = _shortest_workpiece_m(cell)
    if shortest is None:
        return []

    findings: list[Finding] = []
    for asset in cell.of_category("sensor"):
        configuration = asset.instance.configuration
        if configuration is None or configuration.kind != "sensor":
            continue
        if asset.parent_asset is None:
            continue
        height = asset.instance.pose.xyz_m[2]
        reach = height - configuration.beam_width_m / 2.0
        if reach <= shortest:
            continue
        findings.append(
            error(
                "beam-cannot-see-workpiece",
                f"assets.{asset.id}.pose.xyz_m",
                f"stands {height * 1000.0:.0f} mm above {asset.parent_frame!r}, which is "
                f"higher than the shortest declared work-piece is tall "
                f"({shortest * 1000.0:.0f} mm)",
                "A through beam is broken by a body that reaches its line, so this one "
                "can never be broken by anything the facility handles: the part passes "
                "underneath it. Nothing reports that at run time — the belt runs, the "
                "model validates, and the station that waits for this beam waits for "
                "ever. Mount it below the top of the shortest part.",
            )
        )
    return findings


def _cannot_index(cell: ResolvedCell, asset: ResolvedAsset) -> str | None:
    """Why an indexing beam's stand-off could not be derived, or ``None``.

    These are the conditions ``cite_tools.model.resolve.index_offset_m`` gives up
    on. They are read here from the resolved cell rather than shared with it,
    because the resolver needs only to know THAT it cannot derive a number and
    this needs to say WHY — and the two run against different views of the model.
    """
    if asset.parent_asset is None:
        return "it is placed in world coordinates rather than against a belt"
    belt = cell.asset(asset.parent_asset)
    if belt is None or belt.asset_type.category != "conveyor":
        category = "nothing" if belt is None else repr(belt.asset_type.category)
        return f"it is mounted on {asset.parent_asset!r}, which is {category} and not a conveyor"
    drive = belt.instance.configuration
    if drive is None or drive.kind != "conveyor":
        return f"{asset.parent_asset!r} declares no conveyor configuration, so it has no direction"
    if not cell.workpiece_types:
        return "facility.workpiece_models names no work-piece type"
    measurable = [
        asset_type
        for asset_type in cell.workpiece_types
        if (body := asset_type.description.body) is not None
        and body.horizontal_extents_m is not None
    ]
    if not measurable:
        return "no declared work-piece has collision geometry with a horizontal extent"
    return None


def _indexing_beams_stop_at_a_pick_point(cell: ResolvedCell) -> list[Finding]:
    """A beam that indexes a belt, but cannot leave the part where it is wanted.

    WHY THIS IS A RULE AND NOT A COMMENT. A beam declared ``indexes_workpiece``
    is claiming to stop a moving part at a station's pick point, and that claim
    is pure geometry: the resolver derives the mounting stand-off from the part's
    length, so the only ways it can be wrong are ways this can read directly. The
    alternative to reading them here is the way the defect was actually found —
    four runs of ``continuous_line``, ten minutes each, ending in a gripper that
    closed on air 69 mm from the part. One second against ten minutes, for the
    same information.

    Three things have to hold, and each has its own code because the repairs are
    different:

    * ``beam-indexes-off-frame`` — the along-belt component of the authored pose
      must be zero. This is the guard against the repair everyone reaches for
      first: sliding the beam by hand until the scenario passes. A fitted offset
      here would sit next to a derived one and silently win, and the number it
      would be fitted to is a property of this simulator rather than of the cell.
    * ``beam-indexes-no-pick-point`` — the frame it is mounted on must be one a
      station actually picks from. A belt indexed to a point no arm reaches for
      stops parts somewhere nobody collects them.
    * ``beam-off-its-belt`` — the derived position must still be over the belt.
      The stand-off pushes the housing downstream by half a part-length, so a
      long enough part walks the beam off the end of the conveyor, where it can
      never be broken and the belt never stops.
    * ``beam-cannot-index`` — the stand-off must be derivable at all. It is not
      if the beam is mounted on something that is not a driven belt, or if no
      declared work-piece has readable extents to take half a length from.
      ``cite_tools.model.resolve.index_offset_m`` contributes nothing in those
      cases rather than raising, because resolution runs before validation and a
      traceback there would suppress every finding in this module — including
      this one. So this is the rule that has to say it.

    ``beam-off-its-belt`` measures along world x, because it compares against
    ``_bounding_box``, which is axis-aligned. Every belt in this cell runs along
    x, so it is exact here; a belt yawed by a right angle would need the
    comparison taken along its own travel axis, and that is worth doing when such
    a belt appears. The restriction is the same one ``_bounding_box`` already
    carries, so this rule is no less general than the box it is built on.

    What is deliberately NOT checked: whether several work-piece types of
    DIFFERENT lengths all park within some tolerance of the pick point. They
    cannot all park exactly, on hardware either, and the bound on how far off is
    acceptable is a gripper property this rule would have to invent. Inventing it
    is how the constants this project has had to re-derive got here. The facility
    declares one work-piece today; when it declares two, that rule is worth
    writing against a measured grasp tolerance rather than a guessed one.
    """
    pick_points = {station.pick_from for station in cell.stations if station.pick_from is not None}

    findings: list[Finding] = []
    for asset in cell.of_category("sensor"):
        configuration = asset.instance.configuration
        if configuration is None or configuration.kind != "sensor":
            continue
        if not configuration.indexes_workpiece:
            continue

        authored_along_belt = asset.instance.pose.xyz_m[0]
        if authored_along_belt != 0.0:
            findings.append(
                error(
                    "beam-indexes-off-frame",
                    f"assets.{asset.id}.pose.xyz_m",
                    f"is offset {authored_along_belt * 1000.0:.0f} mm along the belt while "
                    "declaring indexes_workpiece",
                    "An indexing beam's position along the belt is derived from the "
                    "work-piece's length by cite_tools.model.resolve.index_offset_m, so "
                    "this pose says only WHICH point the part must stop on. An authored "
                    "offset here is a second, fitted copy of a derived number: it stops "
                    "being right the day the facility handles a different part, and "
                    "nothing reports it. Set it to zero.",
                )
            )

        reason = _cannot_index(cell, asset)
        if reason is not None:
            findings.append(
                error(
                    "beam-cannot-index",
                    f"assets.{asset.id}.configuration.indexes_workpiece",
                    f"is declared, but the stand-off cannot be derived: {reason}",
                    "An indexing beam is mounted half a work-piece downstream of the point "
                    "it stops parts on, and that half-length has to come from somewhere. "
                    "With nothing to derive it from the beam resolves onto the pick point "
                    "itself, where a part breaks it half a part-length early and the belt "
                    "stops short. Declare the missing geometry, or drop "
                    "indexes_workpiece — a beam that only observes needs neither.",
                )
            )
            continue

        if asset.parent_asset is None or asset.parent_frame is None:
            continue
        if (asset.parent_asset, asset.parent_frame) not in pick_points:
            findings.append(
                error(
                    "beam-indexes-no-pick-point",
                    f"assets.{asset.id}.pose.frame",
                    f"indexes to {asset.parent_asset}/{asset.parent_frame}, which no "
                    "station picks from",
                    "Indexing means stopping a part where it will be collected. A belt "
                    "stopped on a point no station reaches for leaves parts standing "
                    "somewhere nobody comes, and the line blocks behind them. Either "
                    "mount the beam against the frame a station picks from, or drop "
                    "indexes_workpiece — a beam that only observes needs neither.",
                )
            )

        belt = cell.asset(asset.parent_asset)
        box = None if belt is None else _bounding_box(belt)
        if box is None:
            continue
        along = asset.world_pose.xyz_m[0]
        if box.min_m[0] <= along <= box.max_m[0]:
            continue
        findings.append(
            error(
                "beam-off-its-belt",
                f"assets.{asset.id}.pose.frame",
                f"resolves to x = {along:.3f} m, which is off the ends of "
                f"{belt.id!r} (x {box.min_m[0]:.3f} to {box.max_m[0]:.3f} m)",  # type: ignore[union-attr]
                "The derived stand-off puts an indexing beam half a work-piece "
                "downstream of the point it indexes to, so a long part walks it past "
                "the end of the conveyor. There it is never broken, the belt is never "
                "stopped, and parts run off the end. Move the pick point further from "
                "the belt's end, or index a shorter part.",
            )
        )
    return findings


def _fmt(pose: Pose) -> str:
    return _fmt_triple(pose.xyz_m)


def _fmt_triple(values: tuple[float, ...]) -> str:
    return "(" + ", ".join(f"{v:.3f}" for v in values) + ")"
