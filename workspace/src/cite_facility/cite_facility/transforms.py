"""Rotation conversion for the runtime side.

The model is roll-pitch-yaw because a person reads it (ADR-0020); TF is
quaternions because nothing reads those. This is the one place the conversion
happens on the ROS side, using the same intrinsic Z-Y-X convention the generator
used — the two agreeing is what makes a pose mean the same thing in both.
"""

from __future__ import annotations

import math

from geometry_msgs.msg import Quaternion


def quaternion_from_rpy(roll: float, pitch: float, yaw: float) -> Quaternion:
    """Intrinsic Z-Y-X roll/pitch/yaw to a quaternion, matching URDF and SDF."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return Quaternion(
        x=sr * cp * cy - cr * sp * sy,
        y=cr * sp * cy + sr * cp * sy,
        z=cr * cp * sy - sr * sp * cy,
        w=cr * cp * cy + sr * sp * sy,
    )
