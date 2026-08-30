"""Physical plausibility: mass, inertia, collision geometry, and gripper stroke.

L1 is blunt about why this exists: *inertial properties are validated, not
trusted*. A wrong inertia tensor raises no error anywhere. The simulation runs,
the physics is wrong, and the symptom — an arm that jitters, a box that behaves
oddly on contact — reads as a controller bug. People then debug the controller,
which is not where the fault is.

Each check below corresponds to one item in L1's list, and each rejects a
*physically impossible* body rather than an unusual one, so a finding here is
never a matter of taste.
"""

from __future__ import annotations

import numpy as np

from cite_tools.model.loader import FacilityModel
from cite_tools.model.schema import AssetType, Body, GraspSpec, Inertial
from cite_tools.validate import Finding, error, warning

#: Plausible bulk densities in kg/m^3. Below balsa or above lead means either the
#: mass or the dimensions are wrong; which one is not something we can tell, so
#: the finding names both.
MIN_DENSITY = 100.0
MAX_DENSITY = 12000.0

#: Relative slack on the triangle inequality, to absorb the rounding in a tensor
#: someone computed by hand and wrote to four decimal places.
TRIANGLE_TOLERANCE = 1e-6

#: The least follower headroom that has actually been measured sufficient, as a
#: fraction of the follower joints' own velocity limit.
#:
#: Not a round number chosen for looking careful. Eleven candidate remedies were
#: measured for the saturated-mimic defect, three repetitions each, round-robin
#: interleaved, with the criteria fixed before any data was taken. A leader rate
#: of 1.5 rad/s against a follower limit of 2 rad/s — a headroom of 0.25 — settled
#: with a worst follower error of 0.0000 rad in 3 of 3 runs, and is the loosest
#: bound for which that is true. Below it nothing has been measured at all, which
#: is what the warning says; it does not claim the value fails.
MIN_MEASURED_FOLLOWER_HEADROOM = 0.25


def check(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    seen_tensors: dict[tuple[float, ...], list[str]] = {}
    narrowest_workpiece = _narrowest_workpiece_width_m(model)

    for asset_type in model.types:
        findings += _default_grasp_width_can_close(asset_type, narrowest_workpiece)
        findings += _followers_can_still_correct(asset_type)
        findings += _result_timeout_outlasts_the_stall_search(asset_type)

        body = asset_type.description.body
        if body is None:
            continue
        where = f"types.{asset_type.id}.description.body"
        findings += _inertia_is_possible(body.inertial, where)
        findings += _density_is_plausible(body, where)
        findings += _com_inside_geometry(body, where)
        findings += _collision_is_not_a_visual_mesh(asset_type, where)

        key = _tensor_key(body.inertial)
        seen_tensors.setdefault(key, []).append(asset_type.id)

    findings += _no_copied_placeholder_tensors(model, seen_tensors)
    return findings


def _tensor_key(inertial: Inertial) -> tuple[float, ...]:
    return (
        inertial.mass_kg,
        inertial.ixx,
        inertial.iyy,
        inertial.izz,
        inertial.ixy,
        inertial.ixz,
        inertial.iyz,
    )


def _matrix(inertial: Inertial) -> np.ndarray:
    return np.array(
        [
            [inertial.ixx, inertial.ixy, inertial.ixz],
            [inertial.ixy, inertial.iyy, inertial.iyz],
            [inertial.ixz, inertial.iyz, inertial.izz],
        ],
        dtype=np.float64,
    )


def _inertia_is_possible(inertial: Inertial, where: str) -> list[Finding]:
    findings: list[Finding] = []
    matrix = _matrix(inertial)

    # Positive definite. eigvalsh is exact enough here and is why scipy is not a
    # dependency (requirements/tools.txt says so explicitly).
    eigenvalues = np.linalg.eigvalsh(matrix)
    if float(eigenvalues.min()) <= 0.0:
        findings.append(
            error(
                "inertia-not-positive-definite",
                where,
                f"inertia tensor has a non-positive principal moment "
                f"({float(eigenvalues.min()):.6g})",
                "No physical object has this tensor. The solver's behaviour with it is "
                "undefined, and the symptom will look like a controller fault.",
            )
        )
        return findings

    # Triangle inequality on the principal moments. A tensor failing this
    # describes an impossible object even though it is positive definite, which
    # is why the two checks are separate.
    a, b, c = (float(v) for v in sorted(eigenvalues))
    if a + b < c * (1.0 - TRIANGLE_TOLERANCE):
        findings.append(
            error(
                "inertia-triangle-inequality",
                where,
                f"principal moments ({a:.6g}, {b:.6g}, {c:.6g}) violate the triangle " "inequality",
                "Each principal moment must be no greater than the sum of the other two. "
                "This tensor describes an object that cannot exist.",
            )
        )
    return findings


def _volume(body: Body) -> float | None:
    geometry = body.collision
    if geometry.kind == "box":
        x, y, z = geometry.size_m
        return float(x * y * z)
    if geometry.kind == "cylinder":
        return float(np.pi * geometry.radius_m**2 * geometry.length_m)
    return None  # a mesh volume needs the mesh, which L1 owns


def _density_is_plausible(body: Body, where: str) -> list[Finding]:
    volume = _volume(body)
    if volume is None or volume <= 0.0:
        return []
    density = body.inertial.mass_kg / volume
    if density < MIN_DENSITY or density > MAX_DENSITY:
        return [
            warning(
                "implausible-density",
                where,
                f"mass {body.inertial.mass_kg} kg over {volume:.4g} m^3 is "
                f"{density:.0f} kg/m^3",
                f"Expected roughly {MIN_DENSITY:.0f}-{MAX_DENSITY:.0f} kg/m^3. Either the "
                "mass or the collision dimensions are wrong; this check cannot tell which.",
            )
        ]
    return []


def _com_inside_geometry(body: Body, where: str) -> list[Finding]:
    geometry = body.collision
    com = body.inertial.com_m
    if geometry.kind == "box":
        half = [s / 2.0 for s in geometry.size_m]
        outside = any(abs(c) > h for c, h in zip(com, half, strict=True))
    elif geometry.kind == "cylinder":
        radial = float(np.hypot(com[0], com[1]))
        outside = radial > geometry.radius_m or abs(com[2]) > geometry.length_m / 2.0
    else:
        return []

    if outside:
        return [
            error(
                "com-outside-geometry",
                where,
                f"centre of mass {com} lies outside the collision geometry",
                "A body whose centre of mass is outside it behaves in ways nobody will "
                "predict, and the cause is never where people look.",
            )
        ]
    return []


def _collision_is_not_a_visual_mesh(asset_type: AssetType, where: str) -> list[Finding]:
    """The single most consequential rule in L1, checked mechanically."""
    body = asset_type.description.body
    if body is None:
        return []
    if (
        body.visual.kind == "mesh"
        and body.collision.kind == "mesh"
        and body.visual.uri == body.collision.uri
    ):
        return [
            error(
                "collision-reuses-visual-mesh",
                where,
                f"collision geometry is the same mesh as the visual ({body.visual.uri})",
                "L1: reusing a dense visual mesh as collision geometry is the most "
                "reliable way to destroy real-time factor and to produce contact "
                "behaviour nobody can explain. Use a primitive or a convex hull.",
            )
        ]
    return []


def _narrowest_workpiece_width_m(model: FacilityModel) -> float | None:
    """The narrowest thing a gripper in this facility has to close on.

    Narrowest rather than widest, because a default grasp width has to stall on
    *every* part the line handles and the narrowest is the one it comes closest
    to missing. Measured across the horizontal footprint: a part rests on a
    surface in a known attitude and a parallel gripper closes across it.

    ``None`` when no work-piece has known extents — none declared, or a mesh part
    whose geometry L1 owns — so that the rule below falls back to the bound it
    can still derive instead of inventing one.
    """
    by_id = {t.id: t for t in model.types}
    widths = [
        extents[0]
        for name in model.facility.workpiece_models
        if (asset_type := by_id.get(name)) is not None
        and asset_type.category == "workpiece"
        and (body := asset_type.description.body) is not None
        and (extents := body.horizontal_extents_m) is not None
    ]
    return min(widths) if widths else None


def _gripper_goal_tolerance(asset_type: AssetType) -> float | None:
    """The gripper controller's own ``goal_tolerance``, in drive-joint units.

    Read from the controller that will actually be loaded rather than restated
    here: it is the same number L3 sizes its grasp discrimination from, and a
    second copy would be a second place to be wrong (P1).
    """
    for controller in asset_type.controllers:
        if controller.joints != "end_effector":
            continue
        value = controller.parameters.get("goal_tolerance")
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        return float(value)
    return None


def _grasp_discrimination_margin_m(
    asset_type: AssetType, grasp: GraspSpec, width_m: float
) -> float | None:
    """What ``2 * goal_tolerance`` of drive travel is worth in width at ``width_m``.

    Not a constant, which is why it is computed rather than declared:
    ``d(opening)/dq`` runs from 84.1 mm/rad fully open to 108.8 mm/rad fully
    closed on this gripper, so one tolerance buys different widths at different
    commands. Evaluating it at the commanded width is what makes the bound follow
    the linkage rather than a snapshot of it.

    The factor of two is `cite_skills::gripper_is_holding`'s, not a new choice:
    one tolerance is the largest end-of-goal bias the controller can produce, and
    doubling it separates a real stall from that bias with margin on both sides.
    Deriving it here from the same declared tolerance keeps the validator's
    ceiling and the skill's predicate from drifting apart.

    ``None`` when the end effector declares no gripper controller, because then
    there is no tolerance to clear and no honest bound to state.
    """
    tolerance = _gripper_goal_tolerance(asset_type)
    if tolerance is None or tolerance <= 0.0:
        return None
    towards_closed = 1.0 if grasp.closed_position >= grasp.open_position else -1.0
    position = grasp.linkage.position_for(width_m)
    biased = position + towards_closed * 2.0 * tolerance
    return abs(grasp.linkage.opening_m(position) - grasp.linkage.opening_m(biased))


def _default_grasp_width_can_close(
    asset_type: AssetType, narrowest_workpiece_m: float | None
) -> list[Finding]:
    """A default grasp width that cannot evidence a grasp is not a default.

    TWO BOUNDS, and why there are two rather than one.

    The WEAK bound is the gripper's own opening. The pads cannot open wider than
    the linkage opens them, so a default above ``max_width_m`` — 88.93 mm here —
    names a width this gripper cannot reach at either end of its travel. It is
    derived through the end effector's own linkage, the same map the skill server
    uses and read from the same place (P1).

    The STRONG bound is "narrower than the part, by enough to tell". A parallel
    gripper evidences a grasp by *failing* to reach where it was sent: the pads
    meet the part, the drive joint stops short, and the controller reports a
    stall (ADR-0022). Commanding the part's own width lets the gripper arrive
    exactly on target and teaches the skill nothing.

    HOW MUCH NARROWER is not a preference either, and it is the part that used to
    be uncheckable. `GripperActionController` ends a goal the instant
    ``|error| < goal_tolerance``, so the position it reports is systematically
    short of the command — which reads back through the linkage as *phantom
    width* that was never between the pads. `cite_skills::gripper_is_holding`
    therefore demands a width margin of twice that tolerance before it will call
    anything a grasp. A default whose margin against the narrowest part falls
    below the same threshold produces real grasps that L3 cannot tell from free
    air, so the threshold is computed from the two declared facts that set it —
    the linkage and the controller's own tolerance — rather than written as a
    millimetre count.

    THIS CEILING WAS DELIBERATELY LOOSENED ONCE, from 60.92 mm to 88.93 mm, and
    the loosening is now paid back rather than merely recorded. 60.92 mm was
    ``opening(closed_threshold_rad)``, justified entirely by ADR-0023's
    attachment plugin; that plugin is gone, and a bound derived from a threshold
    nothing thresholds is an arbitrary number wearing a derivation. The note left
    in its place named the missing part dimensions as the blocker. L0 records
    them now (`model/assets/types/workpieces/`), so the promised check exists and
    is strictly tighter than either predecessor: 47.86 mm on this gripper against
    this facility's 50 mm cube.

    WHAT IS STILL NOT COVERED, said rather than left to be discovered: a facility
    that declares no work-piece, or one whose parts are meshes, falls back to the
    weak bound alone.
    """
    grasp = asset_type.grasp
    if grasp is None or grasp.default_grasp_width_m is None:
        return []

    where = f"types.{asset_type.id}.grasp.default_grasp_width_m"
    stroke = grasp.closed_position - grasp.open_position
    if stroke == 0.0:
        return [
            error(
                "gripper-stroke-is-zero",
                f"types.{asset_type.id}.grasp",
                "open_position and closed_position are equal, so the gripper has no travel",
                "Every width maps to the same joint position; no width can be commanded.",
            )
        ]

    default = grasp.default_grasp_width_m
    if default > grasp.max_width_m:
        return [
            error(
                "default-grasp-width-never-closes",
                where,
                f"{default} m is wider than the pads open; the "
                f"linkage reaches {grasp.max_width_m:.4f} m at open_position "
                f"({grasp.open_position}), so this width is not commandable at all",
                "Lower default_grasp_width_m below the gripper's own opening. A width "
                "above it is saturated by the linkage, so the gripper is commanded to "
                "its open limit and reports success without ever approaching the part.",
            )
        ]

    if narrowest_workpiece_m is None:
        return []
    discrimination = _grasp_discrimination_margin_m(asset_type, grasp, default)
    if discrimination is None:
        return []

    margin = narrowest_workpiece_m - default
    if margin >= discrimination:
        return []

    return [
        error(
            "default-grasp-width-never-closes",
            where,
            f"{default} m leaves {margin * 1000.0:.2f} mm against the narrowest "
            f"work-piece this facility handles ({narrowest_workpiece_m * 1000.0:.1f} mm), "
            f"below the {discrimination * 1000.0:.2f} mm a stall has to exceed to be "
            "distinguishable from closing on air",
            f"Lower default_grasp_width_m to at most "
            f"{(narrowest_workpiece_m - discrimination) * 1000.0:.2f} mm. The controller "
            "ends a goal as soon as |error| < goal_tolerance, so the width it reports is "
            "systematically wider than commanded even with nothing between the pads, and "
            "cite_skills::gripper_is_holding demands twice that bias before it calls "
            "anything a grasp. Below this margin a real grasp reads as free air and the "
            "skill reports a part it is not holding.",
        )
    ]


def _no_copied_placeholder_tensors(
    model: FacilityModel, seen: dict[tuple[float, ...], list[str]]
) -> list[Finding]:
    """The same tensor on bodies of different size means one was copied.

    L1 lists this explicitly: "no placeholder inertia copy-pasted across links of
    different size". Identical tensors on identically-sized bodies are fine and
    expected — three conveyors of one type share a type, not a duplicate.
    """
    findings: list[Finding] = []
    for key, type_ids in sorted(seen.items()):
        if len(type_ids) < 2:
            continue
        volumes = set()
        for type_id in type_ids:
            asset_type = model.asset_type(type_id)
            if asset_type is None or asset_type.description.body is None:
                continue
            volume = _volume(asset_type.description.body)
            if volume is not None:
                volumes.add(round(volume, 9))
        if len(volumes) > 1:
            findings.append(
                error(
                    "copied-inertia",
                    f"types.{', '.join(sorted(type_ids))}",
                    "share an identical inertia tensor despite having different volumes",
                    f"Tensor: mass {key[0]}, ixx {key[1]}, iyy {key[2]}, izz {key[3]}. "
                    "One of these was copied from the other and never recomputed.",
                )
            )
    return findings


def _followers_can_still_correct(asset_type: AssetType) -> list[Finding]:
    """A mimic linkage whose followers run at their limit is not a linkage.

    The derivation, written out because it is the whole reason the close rate is
    declared at all and a reader who cannot recompute it has to take it on trust.

    The five finger joints of a parallel gripper follow ``drive_joint`` through
    URDF ``<mimic>`` tags. Under Gazebo Harmonic nothing enforces that
    mechanically — dartsim implements no mimic constraint — so `gz_ros2_control`
    substitutes a proportional servo, ``velocity_sp = -(q_follower - q_leader *
    multiplier) * update_rate``. A follower holding the leader's speed ``v``
    therefore commands ``v`` itself, and what it has left to reject a disturbance
    is whatever lies below its own velocity limit:

        headroom = 1 - max_drive_rate_rad_s / follower_max_rate_rad_s

    At zero the servo is saturated for the entire stroke and the coupling stops
    behaving like one. This is not inferred: with both limits at the vendor's
    2 rad/s the leader slewed at exactly 2.000 rad/s, the followers needed a
    standing error of 2/150 = 0.0133 rad to keep up and carried a measured 0.0124,
    and a perturbed follower left at the saturated rate, reached its 0.85 position
    limit and stayed there — one pad about 23 degrees out of position while the
    controller reported the goal reached.

    ERROR below zero headroom, because there the mechanism cannot work at all.
    WARNING below ``MIN_MEASURED_FOLLOWER_HEADROOM``, because there it is merely
    unmeasured — a distinction worth keeping, since a warning that claims to be a
    failure trains people to ignore warnings.
    """
    grasp = asset_type.grasp
    if grasp is None:
        return []

    where = f"types.{asset_type.id}.grasp.max_drive_rate_rad_s"
    headroom = grasp.follower_headroom_fraction

    if headroom <= 0.0:
        return [
            error(
                "gripper-followers-have-no-headroom",
                where,
                f"the drive joint may travel at {grasp.max_drive_rate_rad_s} rad/s while its "
                f"mimic followers are limited to {grasp.follower_max_rate_rad_s} rad/s, "
                f"leaving {headroom:.0%} of their authority for correction",
                "The followers are servoed, not linked: holding the leader's speed already "
                "commands that same speed, so at or above their limit they cannot correct a "
                "disturbance at all and a displaced pad never returns. Declare a "
                "max_drive_rate_rad_s below follower_max_rate_rad_s.",
            )
        ]

    if headroom < MIN_MEASURED_FOLLOWER_HEADROOM:
        return [
            warning(
                "gripper-follower-headroom-is-unmeasured",
                where,
                f"followers keep {headroom:.0%} of their authority, below the "
                f"{MIN_MEASURED_FOLLOWER_HEADROOM:.0%} that has been measured sufficient",
                "Not known to fail — known not to have been tested. Either lower "
                "max_drive_rate_rad_s, or measure this one and move the constant.",
            )
        ]

    return []


def _result_timeout_outlasts_the_stall_search(asset_type: AssetType) -> list[Finding]:
    """A deadline that can cut an ordinary contact stall short is not a backstop.

    The derivation, which is the only part of `grasp.result_timeout_s` that is a
    constraint rather than a choice (ADR-0045 decision 3).

    L3 waits for `GripperActionController` to terminate a `GripperCommand`. The
    controller terminates it in exactly two ways: the drive joint reaches the
    commanded position, or it stops moving for `stall_timeout`. So the longest a
    LEGITIMATE close can take before either branch can fire at all is the stroke
    itself, at the rate the drive joint is allowed to travel, plus that timeout:

        floor = (closed_position - open_position) / max_drive_rate_rad_s
                + stall_timeout

    A `result_timeout_s` below that floor gives up on grasps that were about to
    succeed, and turns a working gripper into an intermittent one.

    THERE IS NO CEILING, and its absence is the decision rather than an omission.
    The stall search restarts on every control cycle above
    `stall_velocity_threshold`, so the quantity above the floor is unbounded and
    any upper bound stated here would be a guess wearing a validator's clothes.
    What the value above the floor buys is patience, and ADR-0045 says plainly
    that its size carries no claim.
    """
    grasp = asset_type.grasp
    if grasp is None:
        return []

    stall_timeout_s = None
    for controller in asset_type.controllers:
        value = controller.parameters.get("stall_timeout")
        if value is not None:
            stall_timeout_s = float(value)
            break
    if stall_timeout_s is None:
        # A gripper whose controller declares no stall timeout is a different
        # finding, and one this function is not the author of: the floor here is
        # derived FROM that timeout, so with none declared there is nothing to
        # derive and nothing to say.
        return []

    stroke_s = abs(grasp.closed_position - grasp.open_position) / grasp.max_drive_rate_rad_s
    floor_s = stroke_s + stall_timeout_s
    if grasp.result_timeout_s > floor_s:
        return []

    return [
        error(
            "gripper-result-timeout-cuts-the-stall-search-short",
            f"types.{asset_type.id}.grasp.result_timeout_s",
            f"L3 gives up after {grasp.result_timeout_s} s while a full stroke at "
            f"{grasp.max_drive_rate_rad_s} rad/s takes {stroke_s:.3f} s and the controller "
            f"may then wait {stall_timeout_s} s before declaring a stall",
            "The deadline expires before the controller is even allowed to answer, so a "
            "grasp that was about to succeed is reported as a gripper that never replied. "
            f"Declare a result_timeout_s above {floor_s:.3f} s.",
        )
    ]
