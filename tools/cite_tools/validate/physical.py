"""Physical plausibility: mass, inertia, and collision geometry.

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


def check(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    seen_tensors: dict[tuple[float, ...], list[str]] = {}

    for asset_type in model.types:
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
