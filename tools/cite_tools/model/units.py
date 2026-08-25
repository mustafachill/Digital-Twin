"""Unit constants and the single float formatter used by every generator.

Determinism is a hard requirement: ADR-0004 says the same model input must
produce byte-identical output, because the hand-edit check compares a committed
artifact against a fresh generator run and non-determinism turns that check into
noise that gets ignored.

Float formatting is where non-determinism most easily creeps in — repr changes
between Python versions, ``-0.0`` appears from a rotation of exactly zero, and
scientific notation shows up for small values. So there is exactly one formatter
and every template filter routes through it.

Units are strict SI throughout (ADR-0020). Nothing here converts; the constants
exist so that a magnitude check can name the unit it is checking.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Digits of precision emitted for a float. Nine significant figures is well
#: beyond any physical measurement we will make and short of the point where
#: binary representation noise becomes visible, so a value that round-trips
#: through the generator is unchanged.
PRECISION = 9

#: Values whose magnitude is below this are treated as exactly zero when
#: formatting. It is far smaller than any real length (a nanometre) or angle,
#: and exists to stop a rotation computed as -1e-17 from emitting as such.
EPSILON = 1e-12

LENGTH = "m"
ANGLE = "rad"
MASS = "kg"
TIME = "s"
VELOCITY = "m/s"
ANGULAR_VELOCITY = "rad/s"
FORCE = "N"
TORQUE = "N*m"
INERTIA = "kg*m^2"


def fmt(value: float) -> str:
    """Format one float for emission into a generated artifact.

    Normalises negative zero and near-zero to ``"0"`` so that two runs that
    compute the same pose by different arithmetic paths still emit identical
    text.

    >>> fmt(0.0), fmt(-0.0), fmt(-1e-17)
    ('0', '0', '0')
    >>> fmt(1.5707963267948966)
    '1.57079633'
    >>> fmt(1200.0)
    '1200'
    """
    if not isinstance(value, int | float):  # pragma: no cover - guarded by pydantic
        raise TypeError(f"fmt() takes a number, got {type(value).__name__}")
    if abs(value) < EPSILON:
        return "0"
    return f"{float(value):.{PRECISION}g}"


def fmt_triple(values: Iterable[float]) -> str:
    """Format three floats as a space-separated triple, as URDF and SDF want.

    >>> fmt_triple([0.0, -0.0, 0.6])
    '0 0 0.6'
    """
    parts = [fmt(v) for v in values]
    if len(parts) != 3:
        raise ValueError(f"expected exactly 3 values, got {len(parts)}")
    return " ".join(parts)


def degrees_for_display(radians: float) -> str:
    """Render an angle in degrees, for human-facing output only.

    ADR-0020 forbids degrees anywhere in the model, because two representations
    of one angle is a P1 violation. This exists solely for ``cite-model show``,
    which renders a *view* of the model for a person checking that an arm faces
    the conveyor. Never call it from a generator.
    """
    from math import degrees

    return f"{degrees(radians):.4g}"
