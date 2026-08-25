"""Rigid-body poses and their composition.

Conventions are fixed by ADR-0020 and are not negotiable here, because every
consumer of this model — URDF, SDF, TF — assumes them:

* metres and radians, right-handed, x forward / y left / z up (REP-103);
* ``rpy`` is intrinsic Z-Y-X, so ``R = Rz(yaw) @ Ry(pitch) @ Rx(roll)``, which is
  what URDF ``<origin rpy>`` and SDF ``<pose>`` mean;
* composition is parent-then-child: ``T_world_child = T_world_parent @ T_parent_child``.

Nothing in this module converts units or changes representation. A model triple
travels through it and out into a generated artifact unchanged in meaning, which
is what makes it impossible for a factor or a sign to be introduced silently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Matrix4 = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Pose:
    """A pose: translation in metres, orientation as intrinsic Z-Y-X roll/pitch/yaw."""

    xyz_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rpy_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @classmethod
    def identity(cls) -> Pose:
        return cls()

    @classmethod
    def from_matrix(cls, m: Matrix4) -> Pose:
        """Recover a pose from a homogeneous transform."""
        return cls(xyz_m=_translation_of(m), rpy_rad=_rpy_of(m))

    def to_matrix(self) -> Matrix4:
        """The 4x4 homogeneous transform this pose represents."""
        m: Matrix4 = np.eye(4, dtype=np.float64)
        m[:3, :3] = _rotation(*self.rpy_rad)
        m[:3, 3] = np.asarray(self.xyz_m, dtype=np.float64)
        return m

    def compose(self, child: Pose) -> Pose:
        """``self`` is the parent; return the child expressed in the parent's parent.

        Order is the whole point: ``parent.compose(child)`` is
        ``T_parent @ T_child``, never the reverse. Getting it backwards produces
        a model that looks plausible and places everything wrongly.
        """
        return Pose.from_matrix(self.to_matrix() @ child.to_matrix())

    def corrected_by(self, correction: Pose) -> Pose:
        """Apply a calibration correction as a body-frame delta (ADR-0020).

        Post-multiplication, because a touch-probe or ICP result is expressed in
        the asset's own frame — "this arm is 3 mm further along its own x than
        the drawing says", not "3 mm along the building's x".
        """
        return self.compose(correction)

    def inverse(self) -> Pose:
        return Pose.from_matrix(np.linalg.inv(self.to_matrix()))

    def distance_to(self, other: Pose) -> float:
        """Euclidean distance between the two origins, in metres."""
        a = np.asarray(self.xyz_m, dtype=np.float64)
        b = np.asarray(other.xyz_m, dtype=np.float64)
        return float(np.linalg.norm(a - b))

    def approx_equal(self, other: Pose, *, tol: float = 1e-9) -> bool:
        return bool(
            np.allclose(self.xyz_m, other.xyz_m, atol=tol)
            and np.allclose(_wrap_all(self.rpy_rad), _wrap_all(other.rpy_rad), atol=tol)
        )


def _rotation(roll: float, pitch: float, yaw: float) -> npt.NDArray[np.float64]:
    """Intrinsic Z-Y-X rotation matrix: ``Rz(yaw) @ Ry(pitch) @ Rx(roll)``."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=np.float64)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=np.float64)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=np.float64)
    return rz @ ry @ rx


def _translation_of(m: Matrix4) -> tuple[float, float, float]:
    return (float(m[0, 3]), float(m[1, 3]), float(m[2, 3]))


def _rpy_of(m: Matrix4) -> tuple[float, float, float]:
    """Extract intrinsic Z-Y-X roll/pitch/yaw from a rotation matrix.

    Near gimbal lock (``|pitch|`` approaching pi/2) roll and yaw are not
    separately determined; the convention here assigns the whole rotation to yaw
    and sets roll to zero. ADR-0020 argues why this is safe for this model —
    engineered mounting poses are axis-aligned or near it and calibration
    corrections are small — but it is a real degeneracy and it is written down
    rather than hidden.
    """
    r = np.asarray(m[:3, :3], dtype=np.float64)
    sp = float(-r[2, 0])
    sp = max(-1.0, min(1.0, sp))
    pitch = math.asin(sp)
    if abs(sp) > 1.0 - 1e-9:
        roll = 0.0
        yaw = math.atan2(-float(r[0, 1]), float(r[1, 1]))
    else:
        roll = math.atan2(float(r[2, 1]), float(r[2, 2]))
        yaw = math.atan2(float(r[1, 0]), float(r[0, 0]))
    return (_wrap(roll), _wrap(pitch), _wrap(yaw))


def _wrap(angle: float) -> float:
    """Wrap to (-pi, pi], mapping -pi to +pi so two runs agree on the sign."""
    wrapped = math.remainder(angle, math.tau)
    return math.pi if wrapped == -math.pi else wrapped


def _wrap_all(rpy: tuple[float, float, float]) -> tuple[float, float, float]:
    return (_wrap(rpy[0]), _wrap(rpy[1]), _wrap(rpy[2]))


@dataclass(frozen=True)
class Aabb:
    """An axis-aligned bounding box, used for zone bounds and overlap checks.

    L0 defers richer zone shapes to Phase 3, when a building scan exists. A box
    is enough for a robot cell and is cheap to check.
    """

    min_m: tuple[float, float, float]
    max_m: tuple[float, float, float]

    def __post_init__(self) -> None:
        for axis, (lo, hi) in enumerate(zip(self.min_m, self.max_m, strict=True)):
            if hi < lo:
                raise ValueError(
                    f"bounds inverted on axis {axis}: min {lo} is greater than max {hi}"
                )

    def contains(self, point: tuple[float, float, float]) -> bool:
        return all(lo <= v <= hi for lo, v, hi in zip(self.min_m, point, self.max_m, strict=True))

    def intersects(self, other: Aabb) -> bool:
        return all(
            self.min_m[i] < other.max_m[i] and other.min_m[i] < self.max_m[i] for i in range(3)
        )
