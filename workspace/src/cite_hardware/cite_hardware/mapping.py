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


#: A track trajectory with no points. ``trajectory_msgs`` gives an empty
#: trajectory one meaning on a `joint_trajectory_controller` topic — stop and
#: hold where it stands — and the adapter keeps that meaning, so a caller that
#: stops the simulated carriage this way stops the physical one the same way (P2).
STOP = "stop"


@dataclass(frozen=True)
class TrackTarget:
    """Where a track command sends the carriage, and how long it gives it."""

    position_m: float
    seconds: float


def track_target(message: JointTrajectory, joint: str) -> TrackTarget | str:
    """Read the one thing a track command says: its final point, or a stop.

    Returns :data:`STOP` for an empty trajectory. Raises :class:`Refused` for a
    trajectory naming any joint but ``joint``, a final point whose position
    count does not match, a position that is not finite, or a final point that
    is not in the future. The track's own controller takes the last point as
    the place to be at ``time_from_start``; a vendor position command has no
    intermediate points, so the final one is the whole of the command, which is
    exactly what the program sends (ADR-0067).
    """
    names = list(message.joint_names)
    if names != [joint]:
        raise Refused(
            f"the trajectory names joints {names} and this adapter drives only "
            f"{joint!r}; refused rather than forwarded partially"
        )
    if not message.points:
        return STOP
    final = message.points[-1]
    if len(final.positions) != 1:
        raise Refused(
            f"the final point carries {len(final.positions)} position(s) for one joint"
        )
    position = float(final.positions[0])
    if not math.isfinite(position):
        raise Refused(f"the final point's position is {position}")
    seconds = final.time_from_start.sec + final.time_from_start.nanosec * 1e-9
    if seconds <= 0.0:
        raise Refused(
            f"the final point is due {seconds:g} s from start; a move needs a duration "
            "to take a speed from"
        )
    return TrackTarget(position_m=position, seconds=seconds)


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


def vendor_speed(
    distance_m: float, seconds: float, scale: float, max_speed_mps: float
) -> int:
    """Return the vendor speed covering ``distance_m`` in ``seconds``, in units per second.

    The track controller in simulation reaches the final point AT
    ``time_from_start``; a vendor position command takes a speed instead, so
    the duration is turned into one. Clamped to ``[1, max_speed_mps]`` in vendor
    units: the vendor reads zero as "keep whatever speed was set last", which
    is a speed nobody in this system chose, and the declared maximum is the
    track's own (L0).
    """
    if seconds <= 0.0:
        raise Refused(f"a move due in {seconds:g} s has no speed")
    wanted = abs(distance_m) / seconds * scale
    ceiling = max_speed_mps * scale
    return int(max(1.0, min(round(wanted), ceiling)))
