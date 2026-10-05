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

"""The arithmetic between this system's units and the vendor's.

The numbers below are test inputs, not the asset's facts: the shipped values
come from L0 through the plan, and these tests hold for any values of the same
shape — which is why a reversed range and a non-millimetre scale are tested too.
"""

from __future__ import annotations

import math

from builtin_interfaces.msg import Duration
from cite_hardware.mapping import (
    from_vendor_position,
    LinearMap,
    next_segment,
    Refused,
    require_carried_out,
    require_within,
    slowest_speed_mps,
    to_vendor_position,
    track_target,
    vendor_speed,
)
import pytest
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

JOINT = "track_joint"


def _trajectory(joints, *points) -> JointTrajectory:
    message = JointTrajectory(joint_names=list(joints))
    for positions, seconds in points:
        whole = int(seconds)
        message.points.append(
            JointTrajectoryPoint(
                positions=list(positions),
                time_from_start=Duration(sec=whole, nanosec=int((seconds - whole) * 1e9)),
            )
        )
    return message


# --------------------------------------------------------------------------- #
# The gripper's linear map
# --------------------------------------------------------------------------- #


def test_the_ends_of_the_drive_travel_land_on_the_ends_of_the_vendor_range() -> None:
    mapping = LinearMap(0.0, 0.85, 850.0, 0.0)  # a vendor range that runs backwards
    assert mapping.forward(0.0) == pytest.approx(850.0)
    assert mapping.forward(0.85) == pytest.approx(0.0)
    assert mapping.forward(0.425) == pytest.approx(425.0)


def test_the_inverse_undoes_the_forward_map() -> None:
    mapping = LinearMap(0.0, 0.85, 0.0, 0.85)
    for position in (0.0, 0.1, 0.4, 0.85):
        assert mapping.inverse(mapping.forward(position)) == pytest.approx(position)
    mapping = LinearMap(0.1, 0.9, 850.0, 0.0)
    for position in (0.1, 0.3, 0.9):
        assert mapping.inverse(mapping.forward(position)) == pytest.approx(position)


def test_a_command_is_clamped_to_the_declared_travel_whichever_way_it_runs() -> None:
    assert LinearMap(0.0, 0.85, 0.0, 850.0).clamp(1.2) == 0.85
    assert LinearMap(0.0, 0.85, 0.0, 850.0).clamp(-0.1) == 0.0
    assert LinearMap(0.85, 0.0, 0.0, 850.0).clamp(1.2) == 0.85


def test_a_reported_position_outside_the_range_is_not_folded_back() -> None:
    """A vendor reporting beyond its own range is a fact; hiding it would be a lie."""
    mapping = LinearMap(0.0, 0.85, 0.0, 850.0)
    assert mapping.inverse(900.0) == pytest.approx(0.9)


@pytest.mark.parametrize(
    "endpoints",
    [(0.0, 0.0, 0.0, 850.0), (0.0, 0.85, 5.0, 5.0), (0.0, math.nan, 0.0, 850.0)],
)
def test_an_empty_or_unfinite_range_is_refused(endpoints) -> None:
    with pytest.raises(ValueError):
        LinearMap(*endpoints)


# --------------------------------------------------------------------------- #
# The track command
# --------------------------------------------------------------------------- #


def test_the_last_point_is_the_target_and_the_speed_is_the_commanded_one() -> None:
    """SA2c-S-02 b: from the first point to the last, never from where the carriage is."""
    target = track_target(_trajectory([JOINT], ([0.1], 0.0), ([0.35], 2.5)), JOINT)
    assert target.position_m == pytest.approx(0.35)
    assert target.speed_mps == pytest.approx(0.1)
    assert not target.is_hold


def test_a_trajectory_that_stays_put_is_a_hold() -> None:
    """SA2c-S-02 a: a hold is the same message shape at zero speed, answered by a stop."""
    target = track_target(_trajectory([JOINT], ([0.4], 0.0), ([0.4], 0.2)), JOINT)
    assert target.is_hold


def test_a_trajectory_without_a_start_point_is_refused() -> None:
    """SA2c-S-02 b: one point commands no speed, so the physical side moves nothing."""
    with pytest.raises(Refused, match="no start"):
        track_target(_trajectory([JOINT], ([0.35], 2.5)), JOINT)


def test_an_empty_trajectory_is_refused_not_a_stop() -> None:
    """R-02: `joint_trajectory_controller` refuses one, so the adapter does (P2)."""
    with pytest.raises(Refused, match="no points"):
        track_target(_trajectory([JOINT]), JOINT)


@pytest.mark.parametrize(
    "joints", [["some_other_joint"], [JOINT, "picker_joint1"], []]
)
def test_a_trajectory_for_any_other_joint_set_is_refused(joints) -> None:
    width = max(1, len(joints))
    with pytest.raises(Refused):
        track_target(_trajectory(joints, ([0.1] * width, 0.0), ([0.2] * width, 1.0)), JOINT)


def test_a_last_point_not_after_the_first_is_refused() -> None:
    with pytest.raises(Refused):
        track_target(_trajectory([JOINT], ([0.1], 1.0), ([0.2], 1.0)), JOINT)


def test_an_unfinite_position_is_refused() -> None:
    with pytest.raises(Refused):
        track_target(_trajectory([JOINT], ([0.1], 0.0), ([math.inf], 1.0)), JOINT)


def test_a_move_is_sent_in_segments_of_the_declared_time() -> None:
    """SA2c-S-02 d: a lost stop overruns by one segment at most."""
    # 0.1 m/s for 0.5 s is 50 mm ahead of the carriage, either way.
    assert next_segment(0.1, 0.4, 0.1, 0.5) == (pytest.approx(0.15), False)
    assert next_segment(0.4, 0.1, 0.1, 0.5) == (pytest.approx(0.35), False)
    # Within one segment, the target itself, and the move is complete.
    assert next_segment(0.37, 0.4, 0.1, 0.5) == (0.4, True)


def test_a_target_outside_the_travel_is_refused_not_clamped() -> None:
    require_within(0.7, 0.0, 0.7)
    with pytest.raises(Refused):
        require_within(0.7001, 0.0, 0.7)
    with pytest.raises(Refused):
        require_within(-0.001, 0.0, 0.7)


def test_metres_become_the_vendors_integer_unit_and_back() -> None:
    assert to_vendor_position(0.35, 1000.0) == 350
    assert to_vendor_position(0.3504, 1000.0) == 350
    assert to_vendor_position(0.3506, 1000.0) == 351
    assert from_vendor_position(350, 1000.0) == pytest.approx(0.35)
    # Any scale, not only millimetres.
    assert to_vendor_position(0.35, 100.0) == 35


def test_the_vendor_speed_is_the_commanded_speed() -> None:
    assert vendor_speed(0.1, 1000.0, 1.0) == 100


def test_the_speed_is_capped_at_the_declared_maximum() -> None:
    assert vendor_speed(0.7, 1000.0, 0.5) == 500


def test_the_vendor_speed_never_exceeds_the_commanded_one() -> None:
    """R-13: rounded down, never up; a float hair below a whole unit still counts."""
    assert vendor_speed(0.1239, 1000.0, 1.0) == 123
    assert vendor_speed(0.65 / 6.5, 1000.0, 1.0) == 100
    assert vendor_speed(0.001, 1000.0, 1.0) == 1


def test_a_speed_below_the_vendors_slowest_is_refused_not_raised() -> None:
    """R-13: below 1 unit/s the vendor would run faster than commanded; zero means
    "keep the vendor's last speed", which nobody chose."""
    with pytest.raises(Refused, match="slowest"):
        vendor_speed(0.0001, 1000.0, 1.0)


def test_the_slowest_carried_out_speed_is_the_larger_of_the_two_floors() -> None:
    """SA-S-07: the vendor's 1 unit/s, and a segment reaching one unit."""
    assert slowest_speed_mps(1000.0, 0.5) == pytest.approx(0.002)
    assert slowest_speed_mps(1000.0, 2.0) == pytest.approx(0.001)
    require_carried_out(0.002, 1000.0, 0.5)
    require_carried_out(0.13 / 65.0, 1000.0, 0.5)  # 0.002 m/s, computed
    with pytest.raises(Refused, match="slowest this track carries out"):
        require_carried_out(0.0019, 1000.0, 0.5)


def test_a_hold_has_no_speed() -> None:
    with pytest.raises(Refused):
        vendor_speed(0.0, 1000.0, 1.0)
