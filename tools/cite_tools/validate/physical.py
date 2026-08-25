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
from cite_tools.model.schema import AssetType, Body, Inertial
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

    for asset_type in model.types:
        findings += _default_grasp_width_can_close(asset_type)
        findings += _followers_can_still_correct(asset_type)

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


def _default_grasp_width_can_close(asset_type: AssetType) -> list[Finding]:
    """A default grasp width the gripper cannot even open to is not a default.

    WHAT THIS BOUND USED TO BE, because the change matters and a silent
    relaxation would be worse than the rule. It was
    ``opening(closed_threshold_rad)`` — 60.92 mm on this gripper — and its whole
    justification was ADR-0023's attachment plugin: a width above it left the
    drive joint short of the threshold the plugin watched, so the plugin never
    fired. That plugin is gone (see `GraspSpec`), and with it the only meaning
    ``closed_threshold_rad`` ever had. A bound derived from a threshold that
    nothing thresholds is an arbitrary number wearing a derivation, so it is not
    kept.

    WHAT SURVIVES is the bound the old rule's own docstring said it subsumed: the
    pads cannot open wider than the linkage opens them, so a default above
    ``max_width_m`` commands a width this gripper cannot reach at either end of
    its travel. That is still an ERROR and still not a matter of degree. It is
    derived through the end effector's own linkage — the same map the skill
    server uses, read from the same place (P1) — so the day the linkage changes,
    the bound moves with it.

    WHAT THIS RULE NO LONGER CHECKS, stated rather than left to be discovered.
    The bound that actually matters for a friction grasp is "narrower than the
    part", because that is what makes the pads stop short of the command and the
    controller report the stall ADR-0022 reads as holding. This rule cannot check
    it: L0 describes no work-piece geometry — `Facility.workpiece_models` holds
    names and nothing else — so there is no part width to compare against. The
    day L0 gains work-piece dimensions, that is the check to add here, and it is
    strictly tighter than this one.
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

    ceiling = grasp.max_width_m
    if grasp.default_grasp_width_m > ceiling:
        return [
            error(
                "default-grasp-width-never-closes",
                where,
                f"{grasp.default_grasp_width_m} m is wider than the pads open; the "
                f"linkage reaches {ceiling:.4f} m at open_position "
                f"({grasp.open_position}), so this width is not commandable at all",
                "Lower default_grasp_width_m below the gripper's own opening. A width "
                "above it is saturated by the linkage, so the gripper is commanded to "
                "its open limit and reports success without ever approaching the part.",
            )
        ]

    return []


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
