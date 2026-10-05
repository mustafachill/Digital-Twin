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

"""The shape of a linear-track command, stated once for its sender and the twin.

A track command is a `JointTrajectory` on the track controller's own topic,
with TWO points: where the sender read the carriage, now, and the target,
``seconds`` later (ADR-0067). The simulated `joint_trajectory_controller`
follows it as it would one point; the physical side's track adapter reads the
COMMANDED speed from it - the distance between the two points over the time
between them - rather than deriving one from where its own carriage stands,
which can be anywhere (SA2c-S-02 b). Both sides receive the identical message.

A HOLD is the same shape with both points at one position: the simulated
controller holds there, and the physical adapter stops its carriage where it
stands whatever position the message names (SA2c-S-02 a). The twin boundary
sends each side a hold at that side's own position; a program driving one side
sends one at that side's.
"""

from __future__ import annotations

from builtin_interfaces.msg import Duration
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

#: How long a hold gives the simulated track to settle where it stands, in the
#: controller's clock. Short: a hold commanded with no duration would be a jump.
#: The physical side reads no duration from a hold; it stops.
HOLD_S = 0.2


def _point(position_m: float, seconds: float) -> JointTrajectoryPoint:
    whole = int(seconds)
    return JointTrajectoryPoint(
        positions=[float(position_m)],
        velocities=[0.0],
        time_from_start=Duration(sec=whole, nanosec=int(round((seconds - whole) * 1e9))),
    )


def move(joint: str, start_m: float, target_m: float, seconds: float) -> JointTrajectory:
    """From ``start_m`` now to ``target_m`` in ``seconds``, in the controller's clock."""
    if seconds <= 0.0:
        raise ValueError(f"a track move needs a duration, got {seconds:g} s")
    return JointTrajectory(
        joint_names=[joint], points=[_point(start_m, 0.0), _point(target_m, seconds)]
    )


def hold(joint: str, position_m: float) -> JointTrajectory:
    """Stay at ``position_m``: a stop on a physical side, a hold on a simulated one."""
    return JointTrajectory(
        joint_names=[joint], points=[_point(position_m, 0.0), _point(position_m, HOLD_S)]
    )
