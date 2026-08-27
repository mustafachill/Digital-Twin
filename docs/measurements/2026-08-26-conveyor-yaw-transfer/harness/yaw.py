"""Yaw of a work-piece about the vertical, and what that yaw presents to the jaws.

NEW CODE, AND IT HAS TO BE. Neither published harness extracts a yaw, and the
one rotation measure they do compute is the wrong question here. The friction
campaign's `twist_max_deg` is a total rotation angle of the part relative to the
PADS (`measure_grasp.py`: `2*acos(|w|)` of the relative quaternion), which is
exactly right for a part already held between two pads and undefined for a part
lying on a belt with no gripper anywhere near it.

What decides whether a downstream gripper can close on a part sitting on a belt
is the part's yaw about the WORLD VERTICAL, because the jaws close horizontally.
That is what this module computes, and it folds that yaw by the cube's own
symmetry before reporting it.

THE FOLD IS THE PART THE PUBLISHED HARNESS EXPLICITLY DOES NOT DO, and its
absence is called out in `measure_grasp.py`'s neighbourhood: the published twist
folds only the quaternion double cover (`abs(delta[3])`), mapping to [0, 180].
For a 50 mm cube whose four side faces are physically indistinguishable, a yaw of
89 degrees presents exactly what a yaw of 1 degree presents, and reporting it as
89 would overstate the hazard by a factor of ninety. The published campaigns
never saw a rotation past 34.3 degrees so it never mattered to them; this
campaign deliberately spawns parts at 45 degrees, so it matters here.

A cube resting on a plane has a symmetry group of order 4 about the vertical, so
the folded yaw lives in [0, 45] degrees and is monotonic in the only thing the
gripper cares about — how wide the part is across the jaws.
"""

from __future__ import annotations

import math

#: Edge of the cell's reference work-piece, metres.
#: `model/assets/types/workpieces/workpiece.yaml`, `size_m: [0.050, 0.050, 0.050]`.
EDGE_M = 0.050

#: How far a body axis may sit off the world vertical before the part is not
#: "lying flat" and a yaw about the vertical stops describing it. A cube that has
#: tipped onto an edge presents a diagonal, not a face, and belongs in a
#: different bucket rather than in the yaw distribution.
FLAT_TOLERANCE_DEG = 5.0


def quat_to_axes(q: tuple[float, float, float, float]):
    """The three body axes of `q`, expressed in the world frame.

    `q` is (x, y, z, w) — the ordering Gazebo's `Pose_V` uses and the ordering
    every published raw CSV in this directory tree stores.
    """
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0.0:
        raise ValueError("zero quaternion")
    x, y, z, w = x / n, y / n, z / n, w / n
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)),
        (2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)),
        (2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)),
    )


def tilt_deg(q) -> float:
    """How far the part is from lying flat, in degrees.

    Defined as the angle between the world vertical and whichever body axis is
    closest to it. Zero when any face is flat on the surface, and it does not
    care WHICH face — for a cube those are the same situation.
    """
    axes = quat_to_axes(q)
    best = max(abs(a[2]) for a in axes)
    return math.degrees(math.acos(min(1.0, best)))


def folded_yaw_deg(q) -> float:
    """The part's yaw about the world vertical, folded into [0, 45] degrees.

    Reads the yaw off whichever body axis is most nearly horizontal, which makes
    the answer independent of which face the cube happens to be resting on. For a
    cube the two horizontal axes differ by exactly 90 degrees, so after the fold
    they agree, and picking either is not a choice that can change the number.
    """
    axes = quat_to_axes(q)
    # The axis nearest the vertical is the one to discard; of the rest, the one
    # with the most horizontal length gives the best-conditioned atan2.
    horizontal = sorted(axes, key=lambda a: math.hypot(a[0], a[1]))[-1]
    yaw = math.degrees(math.atan2(horizontal[1], horizontal[0]))
    return fold_deg(yaw)


def fold_deg(yaw_deg: float) -> float:
    """Fold an unrestricted yaw into [0, 45] by the square's 4-fold symmetry."""
    folded = yaw_deg % 90.0
    if folded > 45.0:
        folded = 90.0 - folded
    return abs(folded)


def presented_mm(folded_yaw_deg_value: float, edge_m: float = EDGE_M) -> float:
    """How wide the part is across a pair of jaws closing on it, in millimetres.

    A square of edge `e` rotated by θ about the closing axis spans
    `e*(cos θ + sin θ)`. Monotonic on [0, 45] degrees, from `e` at square to
    `e*sqrt(2)` on the diagonal — 50.00 mm to 70.71 mm for this cell's part.

    This is the quantity ADR-0031 computes to reject a direct handoff, restated
    here as code so that the campaign's threshold and the ADR's arithmetic cannot
    drift apart.
    """
    r = math.radians(folded_yaw_deg_value)
    return edge_m * (math.cos(r) + math.sin(r)) * 1000.0


def yaw_for_presented_mm(width_mm: float, edge_m: float = EDGE_M) -> float:
    """Inverse of `presented_mm` on [0, 45] degrees — the yaw that presents `width_mm`.

    `cos θ + sin θ = sqrt(2)*sin(θ + 45°)`, so the inverse is closed-form rather
    than a search.
    """
    ratio = (width_mm / 1000.0) / edge_m / math.sqrt(2.0)
    ratio = max(-1.0, min(1.0, ratio))
    return math.degrees(math.asin(ratio)) - 45.0


def is_flat(q, tolerance_deg: float = FLAT_TOLERANCE_DEG) -> bool:
    """Whether a yaw about the vertical describes this orientation at all."""
    return tilt_deg(q) <= tolerance_deg
