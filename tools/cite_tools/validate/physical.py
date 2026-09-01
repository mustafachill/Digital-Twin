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

#: The narrowest work-piece, in metres, over which a **derived** collision set has
#: been shown not to change how this cell holds a part.
#:
#: **It is 50.0 mm, the width the 2026-09-01 campaign ran at**, and that sentence
#: is the whole of its definition. It is NOT "this cell's cube": today's L0 cube
#: happens to be 50 mm too, and the two are different quantities that agree by
#: coincidence of history. Deriving this from L0 would turn the rule below into
#: ``narrowest >= narrowest``, which cannot fail — so the two stay separate on
#: purpose, and the day someone changes the cube this constant must not move with
#: it. A narrower part is what the rule refuses; a narrower part that has been
#: measured is what moves this number.
#:
#: ADR-0051 decision 3 is the decision, and **it writes ``0.050 m`` literally too**
#: — this module is where the threshold is *enforced*, not the only place it is
#: spelled, and the two have to move together. (This comment claimed to be "the one
#: place it is a number" until 2026-09-01, which the record it cites already
#: falsified on the day it was written.)
#:
#: It is not a safety factor and not a round figure chosen for comfort: it is the
#: width of the part the clause-2 campaign actually ran, and the clearance argument
#: that lets a hull ship is an argument about *this* width. A rigid part with a
#: flat grasped face stalls the jaws wider than the commanded aperture, and the
#: hull's ramps sit behind the pad plane on the same rigid link, so the part never
#: reaches them. A narrower part closes the jaws further and moves the pad plane
#: along the tool axis as it does; whether the ramps then touch is **unverified**,
#: and the campaign tested none.
NARROWEST_MEASURED_WORKPIECE_M = 0.050


def check(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    seen_tensors: dict[tuple[float, ...], list[str]] = {}
    narrowest_workpiece = _narrowest_workpiece_width_m(model)
    unstated_workpieces = _workpieces_without_a_stated_width(model)

    for asset_type in model.types:
        findings += _default_grasp_width_can_close(asset_type, narrowest_workpiece)
        findings += _derived_collision_is_within_its_measured_range(
            asset_type, narrowest_workpiece, unstated_workpieces
        )
        findings += _followers_can_still_correct(asset_type)
        findings += _result_timeout_outlasts_the_stall_search(asset_type)
        findings += _vendor_collision_is_declared(
            asset_type, narrowest_workpiece, unstated_workpieces
        )
        findings += _vendor_self_collision_matrix_is_acknowledged(asset_type)

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

    # Positive definite. `numpy.linalg.eigvalsh` is exact enough here, so this
    # check needs nothing beyond numpy — which is what the comment beside numpy's
    # pin says. It used to add "and is why scipy is not a dependency"; scipy is
    # one since 2026-08-31, for the hull pipeline (ADR-0028), and this check is
    # still not why.
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


def _no_derived_set_may_be_bound(
    narrowest_workpiece_m: float | None, unstated_workpieces: tuple[str, ...]
) -> str | None:
    """Why a derived collision set is refused for this facility, or ``None``.

    One predicate, read by both collision rules, and having exactly one is the
    point. ``_derived_collision_is_within_its_measured_range`` refuses a derived
    set when this returns a reason; ``_vendor_collision_is_declared`` stays silent
    about the vendor's meshes when it does, because then **the vendor's set is the
    only selection left** and refusing it too would leave the model author no
    legal value for a required field.

    That contradiction shipped on 2026-09-01 and is what this function exists to
    remove: both rules were ERRORs, each hint pointed at the other's state, and a
    40 mm work-piece was refused `convex_hull` for being outside the measured range
    **and** refused `vendor_meshes` for reusing a rendering mesh. A narrow part was
    unmodellable, which is not a policy anyone chose. The vendor's meshes are the
    geometry this cell shipped and measured for months; they are a worse collision
    surface and they are a legal one.
    """
    if unstated_workpieces:
        return (
            f"the narrowest work-piece this facility declares has no stated width "
            f"({', '.join(unstated_workpieces)})"
        )
    if narrowest_workpiece_m is not None and narrowest_workpiece_m < NARROWEST_MEASURED_WORKPIECE_M:
        return (
            f"the narrowest work-piece this facility declares is "
            f"{narrowest_workpiece_m * 1000.0:.1f} mm, below the "
            f"{NARROWEST_MEASURED_WORKPIECE_M * 1000.0:.1f} mm the geometry that promoted "
            "a derived set was argued over"
        )
    return None


def _vendor_collision_is_declared(
    asset_type: AssetType,
    narrowest_workpiece_m: float | None,
    unstated_workpieces: tuple[str, ...],
) -> list[Finding]:
    """The other half of the rule below: it reaches a *vendor* description.

    ADR-0028 decision 4. ``_collision_is_not_a_visual_mesh`` returns an empty list
    for every ``xacro_macro`` type, because it reads ``description.body`` and a
    vendor-described type has none — so the single most consequential rule in L1
    could never fire on the twelve links per arm where the failure it names
    actually occurs. Its silence had been read as evidence for as long as it had
    existed.

    Nothing here opens a vendor file; the model declares what its links collide
    against (``CollisionSpec``) and this reads the declaration. Two outcomes, and
    **both are ERRORs since 2026-09-01**:

    * **No declaration at all** is an ERROR. A vendor description whose collision
      geometry nobody has stated is exactly the state that made this rule silent,
      and it is the one case where "we do not know" is the answer.
    * **A declaration of ``vendor_meshes``** is an ERROR too. It was a WARNING
      until 2026-09-01, and that severity was recorded as a compromise rather than
      a judgement that the state is mild: the shipped selection *was* the vendor's
      meshes, deliberately, because ADR-0028's promotion gate was unmet, and an
      ERROR would have failed ``./scripts/validate-model`` on a state the project
      had decided to remain in. The docstring's instruction was to **promote it in
      the change that moves the default, and not before**. That change is this
      one: ADR-0028 is `Accepted` against the clause ADR-0051 restates, the
      shipped selection is the derived hulls, and reusing a rendering mesh as
      collision geometry is once again the plain defect CLAUDE.md §10 names —
      with, now, a generated alternative one field away. ``--strict`` no longer
      has anything to add here.

    **ONE CONDITION ON THE SECOND OUTCOME, ADDED 2026-09-01 BY THE REVIEW OF THE
    CHANGE THAT SHIPPED IT.** ``vendor_meshes`` is a legal selection for a type
    whose derived sets ``_no_derived_set_may_be_bound`` refuses — that function is
    the single predicate both collision rules read, and it exists because without
    it the two rules contradicted each other: a 40 mm work-piece was refused
    ``convex_hull`` for being outside the measured range **and** refused
    ``vendor_meshes`` for reusing a rendering mesh, so a narrow part had no valid
    collision selection at all. This finding is a defect **relative to an
    alternative that is actually available**; where none is, it is not a defect but
    the state of the evidence, and the rule below is the one that says so.
    """
    if not asset_type.emits_vendor_description:
        return []
    where = f"types.{asset_type.id}.description.collision"
    collision = asset_type.description.collision
    if collision is None:
        return [
            error(
                "vendor-collision-undeclared",
                where,
                "a vendor description is emitted for this type and nothing states what "
                "its links collide against",
                "L1: a vendor macro is invoked, never ingested, so no check here can "
                "discover this by reading the vendor's files. Declare it (ADR-0028) or "
                "the most consequential rule in this layer stays silent on this type.",
            )
        ]
    if collision.selected.kind != "vendor_meshes":
        return []
    alternatives = sorted(s.id for s in collision.sets if s.kind != "vendor_meshes")
    refused = _no_derived_set_may_be_bound(narrowest_workpiece_m, unstated_workpieces)
    if alternatives and refused is not None:
        return []
    return [
        error(
            "collision-reuses-visual-mesh",
            where,
            f"this type's links collide against the vendor's own meshes "
            f"(set {collision.select!r})",
            "For the xArm variant this model describes, the vendor's collision_dir IS "
            "its visual_dir, so those are rendering meshes. ADR-0028 is the decision; "
            + (
                f"the set(s) {alternatives} are generated and available, and this "
                "facility's declared work-pieces are inside the range they were "
                "measured over (ADR-0051 decision 3)."
                if alternatives
                else "no alternative set is declared."
            ),
        )
    ]


def _vendor_self_collision_matrix_is_acknowledged(asset_type: AssetType) -> list[Finding]:
    """A derived collision set and the vendor's matrix must be declared together.

    ADR-0028's interim check, built 2026-09-01 in the shape ADR-0028 decision 4
    already established for the identical structural hole one layer down.

    THE HOLE. The SRDF is *invoked*, never copied, so its self-collision matrix
    is a function of the **vendor's** collision geometry. This type now binds
    convex hulls of that geometry. A hull is never smaller than what it replaces,
    so the failure runs one way: **a pair the vendor DISABLED can interpenetrate
    under hulls, and MoveIt never checks a disabled pair.** The opposite —
    an always-colliding pair that stops touching — cannot occur, and no pair on
    this arm carries ``reason="Always"`` anyway.

    WHY THIS SHAPE AND NOT THE ONE ADR-0028 NAMED. That record asks for "a check
    that fails when a derived set is selected while the SRDF's matrix names the
    vendor's". Written that way it fails on the shipped configuration the moment
    it exists, with no passing state to move towards — a **blocker**, which gets
    reverted rather than answered, and this project has watched a carried finding
    become invisible before. Keyed on an L0 *declaration* instead, the state
    becomes declarable: the model says what the vendor's matrix was audited
    against, the rule holds the two together, and **changing either one reopens
    it**. That is exactly what decision 4 did for collision meshes.

    WHAT IT DOES NOT DO, stated so nobody reads the green as safety. It does not
    check the matrix, re-derive it, or verify a figure in the declaration. It
    checks that a human wrote one down against the set actually bound. The
    numbers are the audit's, and the audit is static geometry on one reading.

    AND THE OBVIOUS NEXT STEP IS NOT OBVIOUSLY RIGHT. Regenerating the matrix
    from the *selected* geometry would disable pairs on the strength of hull
    material that does not exist — a hull fills concavities, so two links whose
    hulls interpenetrate may have millimetres of real metal between them. On this
    arm nothing is lost, because the always-interpenetrating hull pairs are the
    gripper linkage the vendor already disables; that is a measured fact and not
    a general one.
    """
    if not asset_type.emits_vendor_description:
        return []
    collision = asset_type.description.collision
    if collision is None or collision.selected.kind == "vendor_meshes":
        return []
    planning = asset_type.planning
    if planning is None or planning.srdf_macro is None:
        return []

    where = f"types.{asset_type.id}.planning.vendor_self_collision_matrix"
    hint = (
        "ADR-0028: the SRDF is invoked rather than copied, so its matrix is a property of "
        "the vendor's collision geometry, and this type binds a hull of that geometry "
        "instead. A hull is never smaller than what it replaces, so a pair the vendor "
        "DISABLED can interpenetrate while MoveIt never checks it. Declare the "
        "acknowledgement with the audit that produced its figures, or select the vendor's "
        "collision set. Do not answer this by regenerating the matrix against hulls: that "
        "disables pairs on the strength of material a hull invented."
    )
    acknowledged = planning.vendor_self_collision_matrix
    if acknowledged is None:
        return [
            error(
                "vendor-self-collision-matrix-unacknowledged",
                where,
                f"this type binds the derived collision set {collision.select!r} and "
                f"invokes the vendor SRDF macro {planning.srdf_macro!r}, whose "
                "self-collision matrix was computed against the vendor's geometry; "
                "nothing in the model acknowledges the mismatch",
                hint,
            )
        ]
    declared = {s.id for s in collision.sets}
    if acknowledged.audited_for not in declared:
        return [
            error(
                "vendor-self-collision-matrix-unacknowledged",
                where,
                f"the acknowledgement names collision set "
                f"{acknowledged.audited_for!r}, which this type does not declare "
                f"(declared: {sorted(declared)})",
                hint,
            )
        ]
    if acknowledged.audited_for != collision.select:
        return [
            error(
                "vendor-self-collision-matrix-unacknowledged",
                where,
                f"this type binds {collision.select!r} and the acknowledgement was "
                f"audited against {acknowledged.audited_for!r}, so it covers geometry "
                "this model no longer loads",
                "An acknowledgement that survives a geometry change reads as coverage "
                "and is not. Re-run the audit against the set now bound and restate the "
                "figures, or bind the set it was taken against. " + hint,
            )
        ]
    return []


def _collision_is_not_a_visual_mesh(asset_type: AssetType, where: str) -> list[Finding]:
    """The single most consequential rule in L1, checked mechanically.

    This half covers bodies we author. The vendor half is
    ``_vendor_collision_is_declared`` above, which reads a declaration because it
    is not permitted to read a vendor file.
    """
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

    **``None`` is two different states and this function cannot tell them apart**,
    which is why ``_workpieces_without_a_stated_width`` exists beside it. "This
    facility handles no parts" and "this facility handles a part nobody has stated
    the width of" deserve different answers, and collapsing them here is what let a
    one-line edit — a mesh work-piece — switch off both this rule's consumers at
    once with no finding at all.
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


def _workpieces_without_a_stated_width(model: FacilityModel) -> tuple[str, ...]:
    """Declared work-piece types whose horizontal footprint is not a stated number.

    The complement of ``_narrowest_workpiece_width_m``'s input, and it is a
    finding rather than a silence. A mesh work-piece — or one with no
    ``description.body`` at all — carries its extents in a file L1 owns, so
    nothing at L0 can measure across it. That is a legitimate way to describe a
    part; it is not a legitimate way to acquire a *bound*, and the rules that want
    one have to be told rather than left to read ``None``.

    Both consumers used to fall silent on it together
    (``default-grasp-width-never-closes`` and
    ``derived-collision-outside-measured-range``), so one line in L0 removed two
    bounds and reported nothing. This closes the half where the silence is
    load-bearing: a derived collision set bound against a width nobody has stated
    is exactly the act ADR-0051 decision 3 refuses. **The grasp-width half is
    deliberately still a silence** — its weak bound survives, and widening that
    rule was not this review's finding.
    """
    by_id = {t.id: t for t in model.types}
    return tuple(
        sorted(
            name
            for name in model.facility.workpiece_models
            if (asset_type := by_id.get(name)) is not None
            and asset_type.category == "workpiece"
            and ((body := asset_type.description.body) is None or body.horizontal_extents_m is None)
        )
    )


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


def _derived_collision_is_within_its_measured_range(
    asset_type: AssetType,
    narrowest_workpiece_m: float | None,
    unstated_workpieces: tuple[str, ...],
) -> list[Finding]:
    """A derived collision set ships against a width, not against every width.

    ADR-0051 decision 3, which names this rule and deliberately does not write it:
    *"If that rule is not written, the precondition is prose"*. This is the rule.

    WHY THERE IS A RANGE AT ALL. ADR-0028's hulls are `Accepted` on a campaign
    whose verdict on its own question was INCONCLUSIVE, and what carries the
    promotion in its place is a **geometric** clearance argument: the hull's ramps
    are recessed behind the pad plane on the same rigid link, so the part never
    reaches them. That argument is bounded by the width at which the jaws stall,
    and the campaign ran one part at one width. Cite ADR-0051 for the geometry and
    for both computations; it is not restated here (P1).

    WHY THIS IS AN ERROR AND NOT A WARNING. Declaring a narrower part is precisely
    the act ADR-0051 says reopens ADR-0028's clause 2, and this rule is the only
    thing in the tree that will say so — nothing downstream of L0 can tell that a
    part is outside the range the geometry was argued over, because both geometries
    load and run. A warning is what the project already tried for the state this
    rule replaces, and the campaign that settled the geometry shipped a pre-flight
    check that named a directory that does not exist, reported nothing in all four
    of its blocks, and was noticed by nobody: **a check that cannot fail is
    indistinguishable from one that passes**, and one whose finding is routinely
    carried is barely better. It also has a correct answer that is always
    available and never destructive — select the vendor's set — so refusing costs a
    model author one field and no measurement.

    **THAT ESCAPE HATCH IS NOW REAL, AND IT WAS NOT WHEN THIS RULE SHIPPED.** The
    same change made ``_vendor_collision_is_declared`` refuse ``vendor_meshes``
    unconditionally, so for one day both rules were ERRORs and the answer each hint
    named was refused by the other: a 40 mm cube reported
    ``derived-collision-outside-measured-range`` on ``convex_hull`` and
    ``collision-reuses-visual-mesh`` on ``vendor_meshes``, and had no legal
    selection at all. ``_no_derived_set_may_be_bound`` is now the one predicate
    both rules read, and the vendor's set is silent wherever this rule fires.

    WHAT MUST BE MEASURED BEFORE A NARROWER PART MAY SHIP AGAINST A DERIVED SET,
    in ADR-0051 decision 3's order and not repeated in detail here:

    1. the static geometry audit re-run at that part's **achieved** stall aperture
       and pad-plane registration, reporting shoulder-to-pad-plane clearance as a
       function of height along the pad — cheap, and it settles two other open
       questions at the same time;
    2. **if that clearance does not hold**, the clause-2 A/B re-run at that width,
       with the contact-patch and contact-normal instruments pre-registered as
       before.

    A WORK-PIECE WITH NO STATED WIDTH IS ITS OWN FINDING, since 2026-09-01, and
    this paragraph used to record it as a gap instead. ``_narrowest_workpiece_width_m``
    returns ``None`` for a **mesh** work-piece as well as for a facility that
    declares none, and returning ``[]`` on ``None`` meant one line in L0 — change
    the cube to a mesh — shipped a 20 mm part against the hulls with this rule
    silent, which is precisely the act ADR-0051 decision 3 says reopens clause 2.
    ``derived-collision-range-unstated`` now says so. It is an ERROR for the same
    reason the width case is: the vendor's set is available, costs one field, and
    the alternative is a bound nobody can check.

    WHAT THIS STILL DOES NOT COVER, said rather than left to be found. A facility
    that declares **no work-piece at all** gets no bound and no finding — the
    derived set then ships against a width nobody has stated, which is a weaker
    silence than a wrong answer but is still a silence, and it is a silence about
    a facility that handles nothing rather than about a part. It also says nothing
    about *shape*: the clearance argument wants a rigid part with a flat grasped
    face, and a horizontal extent is all L0 records.
    """
    collision = asset_type.description.collision
    if collision is None or collision.selected.kind == "vendor_meshes":
        return []
    where = f"types.{asset_type.id}.description.collision"
    remedy = (
        "ADR-0051 decision 3: a work-piece outside that range may not ship against a "
        "derived collision set until clause 2 has been answered at its width, and "
        "declaring one reopens the clause. The pads hold by friction alone (ADR-0029), "
        "so the contact surface is the mechanism and a narrower part closes the jaws "
        "past the aperture the clearance was computed at. Either select the vendor's "
        "set for this type — which is legal here, and this validator will not fault it "
        "while this finding stands — or take the two measurements ADR-0051 names, in "
        "its order, and move the range with the evidence."
    )
    if unstated_workpieces:
        return [
            error(
                "derived-collision-range-unstated",
                where,
                f"this type binds the derived collision set {collision.select!r} while "
                f"the work-piece type(s) {list(unstated_workpieces)} state no horizontal "
                "extents, so the width the derived geometry would be judged against "
                "cannot be computed at all",
                "A mesh work-piece carries its extents in a file L1 owns, so no rule here "
                "can measure across it, and a bound nobody can compute is not a bound. " + remedy,
            )
        ]
    if narrowest_workpiece_m is None or narrowest_workpiece_m >= NARROWEST_MEASURED_WORKPIECE_M:
        return []
    return [
        error(
            "derived-collision-outside-measured-range",
            where,
            f"this type binds the derived collision set {collision.select!r} while the "
            f"narrowest work-piece this facility declares is "
            f"{narrowest_workpiece_m * 1000.0:.1f} mm, below the "
            f"{NARROWEST_MEASURED_WORKPIECE_M * 1000.0:.1f} mm the geometry that promoted "
            "that set was argued over",
            remedy,
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
    commanded position, or it stops moving for `stall_timeout`. So a full stroke
    at the fastest rate the drive joint is allowed to travel, plus that timeout,
    is the SHORTEST time in which either branch can fire on a full-stroke close:

        floor = (closed_position - open_position) / max_drive_rate_rad_s
                + stall_timeout

    A `result_timeout_s` below that floor cannot even be reached by a gripper
    running flat out, so it gives up on grasps that were about to succeed and
    turns a working gripper into an intermittent one.

    THE FLOOR IS NECESSARY AND NOT SUFFICIENT, and reading it the other way round
    is the mistake this paragraph used to make. `max_drive_rate_rad_s` is a
    MAXIMUM, so the arithmetic above is a lower bound on the stroke time and not
    an upper one: a plant that drives at half its declared limit takes twice as
    long, and a deadline that clears this floor can still expire mid-stroke. On
    the shipped gripper that would be 1.7 s against a 1.15 s floor, so
    `result_timeout_s: 1.2` passes this check and is still wrong — and since
    ADR-0046 an expiry stops the line. Clearing the floor is the least this value
    must do, not the most.

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
        # NOTHING AUTHORS THAT FINDING, AND THIS RULE THEREFORE DISABLES ITSELF
        # SILENTLY. The floor is derived FROM `stall_timeout`, so with none
        # declared there is nothing to derive — but deleting the key from the L0
        # end-effector type makes `physical.check()` return zero findings, which
        # was verified by doing it rather than assumed. This comment used to say
        # the missing timeout "is a different finding"; no rule anywhere writes
        # that finding, so it is a gap and not a division of labour. Whoever adds
        # a rule requiring a gripper controller to declare its stall timeout
        # closes it; until then, a gripper that loses that key loses this check
        # with it and nothing says so.
        return []

    stroke_s = abs(grasp.closed_position - grasp.open_position) / grasp.max_drive_rate_rad_s
    floor_s = stroke_s + stall_timeout_s
    if grasp.result_timeout_s > floor_s:
        return []

    return [
        error(
            "gripper-result-timeout-cuts-the-stall-search-short",
            f"types.{asset_type.id}.grasp.result_timeout_s",
            f"L3 gives up after {grasp.result_timeout_s} s while a full stroke takes at "
            f"least {stroke_s:.3f} s — that is at the declared maximum "
            f"{grasp.max_drive_rate_rad_s} rad/s, so it is the fastest the stroke can be — "
            f"and the controller may then wait {stall_timeout_s} s before declaring a stall",
            "The deadline expires before the controller is even allowed to answer, so a "
            "grasp that was about to succeed is reported as a gripper that never replied. "
            f"Declare a result_timeout_s above {floor_s:.3f} s. That floor is the least it "
            "must clear and not enough on its own: the stroke figure assumes the drive "
            "runs at its declared maximum, and a slower plant needs proportionally more.",
        )
    ]
