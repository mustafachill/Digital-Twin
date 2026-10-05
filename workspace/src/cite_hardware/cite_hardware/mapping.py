# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The arithmetic between this system's units and the vendor's, and nothing else.

Separated from the nodes so every conversion is tested without a graph. A unit
confusion here is silent: a track target of 0.35 sent as 0 mm, or a gripper
command in radians handed to a range in another unit, is a perfectly valid
vendor request that moves the machine somewhere nobody asked for.

Every number a function here needs is an argument. Which values apply to which
asset is configuration delivered by the caller (P5); nothing here knows that the
track is 700 mm long or that the gripper closes at 0.85.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from trajectory_msgs.msg import JointTrajectory


class Refused(ValueError):
    """A command this adapter will not forward, with the reason as its message."""


@dataclass(frozen=True)
class LinearMap:
    """An affine map taking ``[source_a, source_b]`` onto ``[target_a, target_b]``.

    Endpoints, not a slope and an offset, because endpoints are what L0
    declares: the drive joint's open and closed positions on one side, the
    vendor's open and closed values on the other. Either range may run
    backwards; the vendor's gripper does, against the drive joint's.
    """

    source_a: float
    source_b: float
    target_a: float
    target_b: float

    def __post_init__(self) -> None:
        values = (self.source_a, self.source_b, self.target_a, self.target_b)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"a linear map needs four finite endpoints, got {values}")
        if self.source_a == self.source_b:
            raise ValueError(
                f"the source range is empty ({self.source_a} to {self.source_b}), so "
                "every command would land on one point"
            )
        if self.target_a == self.target_b:
            raise ValueError(
                f"the target range is empty ({self.target_a} to {self.target_b}), so "
                "nothing could be mapped back"
            )

    def clamp(self, value: float) -> float:
        """Clamp ``value`` into the source range, whichever way round it runs."""
        low, high = sorted((self.source_a, self.source_b))
        return min(max(value, low), high)

    def forward(self, value: float) -> float:
        """Map a source value onto the target range. Not clamped."""
        fraction = (value - self.source_a) / (self.source_b - self.source_a)
        return self.target_a + fraction * (self.target_b - self.target_a)

    def inverse(self, value: float) -> float:
        """Map a target value back onto the source range. Not clamped.

        Not clamped on purpose: a vendor reporting a position outside its own
        declared range is a fact about the machine, and folding it back inside
        the range would hide it.
        """
        fraction = (value - self.target_a) / (self.target_b - self.target_a)
        return self.source_a + fraction * (self.source_b - self.source_a)


@dataclass(frozen=True)
class TrackTarget:
    """Where a track command sends the carriage, and at what speed it was commanded.

    ``speed_mps`` zero is a HOLD: the command's first and last points are one
    position, which the simulated controller holds where it stands and this
    adapter answers with a stop (SA2c-S-02).
    """

    position_m: float
    speed_mps: float

    @property
    def is_hold(self) -> bool:
        return self.speed_mps == 0.0


def _seconds(point) -> float:
    return point.time_from_start.sec + point.time_from_start.nanosec * 1e-9


def track_target(message: JointTrajectory, joint: str) -> TrackTarget:
    """Read what a track command says: where it ends, and its commanded speed.

    A track command carries its START as its first point and its target as its
    last (`cite_bringup.track_command`): the controller is asked to go from
    there to here in the time between them, so the commanded speed is
    ``|last - first| / (t_last - t_first)``. Both sides receive that one
    message; this adapter bounds the vendor's speed by it rather than by where
    its own carriage happens to stand (SA2c-S-02 b).

    Raises :class:`Refused` for a trajectory with no points, a trajectory
    naming any joint but ``joint``, a point whose position count does not
    match or is not finite, a trajectory with no start point (one point says
    no speed), or a last point not after the first.
    """
    names = list(message.joint_names)
    if names != [joint]:
        raise Refused(
            f"the trajectory names joints {names} and this adapter drives only "
            f"{joint!r}; refused rather than forwarded partially"
        )
    if not message.points:
        # Refused, as `joint_trajectory_controller` (4.x) refuses one: an empty
        # trajectory is not a stop to the simulated track controller either,
        # so it is not one here (P2). A hold is a trajectory that stays put.
        raise Refused("the trajectory has no points")
    if len(message.points) < 2:
        raise Refused(
            "the trajectory has one point and so no start: the commanded speed is "
            "read from the first point to the last, and a speed derived from where "
            "this carriage stands could be faster than anyone commanded"
        )
    first, final = message.points[0], message.points[-1]
    positions = []
    for point in (first, final):
        if len(point.positions) != 1:
            raise Refused(f"a point carries {len(point.positions)} position(s) for one joint")
        position = float(point.positions[0])
        if not math.isfinite(position):
            raise Refused(f"a point's position is {position}")
        positions.append(position)
    seconds = _seconds(final) - _seconds(first)
    if seconds <= 0.0:
        raise Refused(
            f"the last point is due {seconds:g} s after the first; a move needs a duration "
            "to take a speed from"
        )
    return TrackTarget(
        position_m=positions[1], speed_mps=abs(positions[1] - positions[0]) / seconds
    )


def next_segment(
    position_m: float, target_m: float, speed_mps: float, segment_s: float
) -> tuple[float, bool]:
    """Return where the next vendor move ends, and whether it ends at the target.

    A move is sent in segments of ``speed_mps * segment_s`` metres from where
    the carriage was last read, so a carriage whose stop never arrives runs at
    most one segment past the last one sent (SA2c-S-02 d). The last segment is
    the target itself.
    """
    reach = speed_mps * segment_s
    remaining = target_m - position_m
    if abs(remaining) <= reach:
        return target_m, True
    return position_m + math.copysign(reach, remaining), False


def require_within(position_m: float, low_m: float, high_m: float) -> None:
    """Refuse a track target outside the declared travel, rather than clamp it.

    Clamping would move the carriage to an end stop nobody asked for. The
    simulated joint would stop at its limit too, but it would report the
    shortfall on its joint state, and the caller's arrival check would see it;
    a refusal says the same thing earlier and moves nothing.
    """
    if not low_m <= position_m <= high_m:
        raise Refused(
            f"target {position_m:.4f} m is outside the track's travel "
            f"[{low_m:.4f}, {high_m:.4f}] m"
        )


def to_vendor_position(position_m: float, scale: float) -> int:
    """Metres to the vendor's integer position unit (millimetres for the xArm track)."""
    return int(round(position_m * scale))


def from_vendor_position(value: int, scale: float) -> float:
    """Convert the vendor's integer position unit back to metres."""
    return float(value) / scale


#: The vendor's slowest track speed, in its position units per second:
#: `set_linear_motor_speed` takes a whole number of mm/s from 1 to 1000
#: (`xarm_sdk/cxx/include/xarm/wrapper/xarm_api.h`, `set_linear_motor_speed`).
VENDOR_MIN_SPEED = 1

#: Slack on a comparison of a speed or a reach computed in floating point
#: against a whole number of vendor units: 0.65 m over 6.5 s is 0.1 m/s, and
#: must not be judged a hair below it.
_UNIT_SLACK = 1e-9


def slowest_speed_mps(scale: float, segment_s: float) -> float:
    """Return the slowest commanded speed this adapter carries out, in m/s.

    Two floors, the larger one binding: the vendor's slowest speed, and a
    segment (``segment_s`` of travel at the commanded speed) that reaches at
    least one vendor position unit - a shorter one would round to where the
    carriage stands and never move it. Stated once, here, for the adapter's
    refusal and for the program's speed-scale check before bring-up (SA-S-07).
    """
    return max(VENDOR_MIN_SPEED, 1.0 / segment_s) / scale


def require_carried_out(speed_mps: float, scale: float, segment_s: float) -> None:
    """Refuse a move slower than `slowest_speed_mps`, rather than stall or speed it up."""
    slowest = slowest_speed_mps(scale, segment_s)
    if speed_mps < slowest * (1.0 - _UNIT_SLACK):
        raise Refused(
            f"a move at {speed_mps:g} m/s is slower than {slowest:g} m/s, the slowest this "
            "track carries out (the vendor's 1 unit/s, and a segment reaching one unit)"
        )


def vendor_speed(speed_mps: float, scale: float, max_speed_mps: float) -> int:
    """Return the commanded speed in the vendor's whole units per second.

    The commanded speed, never one derived from where this carriage stands
    (SA2c-S-02 b), capped at the track's own declared maximum (L0) and rounded
    DOWN, so the vendor is never asked for more than was commanded (R-13).
    Below the vendor's slowest speed, 1 unit/s, it is refused rather than
    raised to it; zero is no floor either, since the vendor reads it as "keep
    whatever speed was set last". A hold has no speed and is a stop, never a
    move.
    """
    if speed_mps <= 0.0:
        raise Refused(f"a move at {speed_mps:g} m/s has no speed")
    units = math.floor(min(speed_mps, max_speed_mps) * scale + _UNIT_SLACK)
    if units < VENDOR_MIN_SPEED:
        raise Refused(
            f"a move at {speed_mps:g} m/s is below the vendor's slowest speed, "
            f"{VENDOR_MIN_SPEED} unit/s; refused rather than run faster than commanded"
        )
    return int(units)
