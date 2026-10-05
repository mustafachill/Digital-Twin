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
    Refused,
    require_within,
    STOP,
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


def test_the_final_point_is_the_command() -> None:
    target = track_target(_trajectory([JOINT], ([0.1], 1.0), ([0.35], 2.5)), JOINT)
    assert target.position_m == pytest.approx(0.35)
    assert target.seconds == pytest.approx(2.5)


def test_an_empty_trajectory_is_a_stop() -> None:
    assert track_target(_trajectory([JOINT]), JOINT) == STOP


@pytest.mark.parametrize(
    "joints", [["some_other_joint"], [JOINT, "picker_joint1"], []]
)
def test_a_trajectory_for_any_other_joint_set_is_refused(joints) -> None:
    with pytest.raises(Refused):
        track_target(_trajectory(joints, ([0.1] * max(1, len(joints)), 1.0)), JOINT)


def test_a_point_due_now_or_in_the_past_is_refused() -> None:
    with pytest.raises(Refused):
        track_target(_trajectory([JOINT], ([0.2], 0.0)), JOINT)


def test_an_unfinite_position_is_refused() -> None:
    with pytest.raises(Refused):
        track_target(_trajectory([JOINT], ([math.inf], 1.0)), JOINT)


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


def test_the_speed_covers_the_distance_in_the_points_time() -> None:
    # 0.2 m in 2 s is 100 mm/s.
    assert vendor_speed(0.2, 2.0, 1000.0, 1.0) == 100
    assert vendor_speed(-0.2, 2.0, 1000.0, 1.0) == 100


def test_the_speed_is_clamped_to_one_unit_and_to_the_declared_maximum() -> None:
    # Zero would mean "keep the vendor's last speed", which nobody chose.
    assert vendor_speed(0.0, 0.2, 1000.0, 1.0) == 1
    assert vendor_speed(0.7, 0.1, 1000.0, 0.5) == 500


def test_a_move_with_no_time_has_no_speed() -> None:
    with pytest.raises(Refused):
        vendor_speed(0.1, 0.0, 1000.0, 1.0)
