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

"""ADR-0066's hand-written program, KEPT AS A RECORD and no longer run by default.

`python3 -m cite_bringup.program` runs the real robot's own program since
ADR-0067 (`from_plan`). This list moved the arm through four poses taught in
simulation, and the model no longer declares them: they were taught against the
layout before the arm rode a track, so `target` below refuses today's plan and
says which poses are missing. What it records is the shape the fixed program
started as.

The program: pick the part off the table, put it on the belt, run the belt.

Read it top to bottom; that is the cell's whole cycle. Only the ORDER of the
steps is written here. The poses are taught in L0 (`poses_rad`), and the grip
width, the belt speed and how long the belt runs all come from the generated
plan, so nothing below is a number about the cell (P1).
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from cite_bringup.demo import frame
from cite_bringup.plan import ControllerManager, Conveyor, Plan
from cite_bringup.program.steps import belt, grip, move, release, Step, wait

#: The taught poses this program moves through, in the order it uses them.
POSES = ("pick_above", "pick", "place_above", "place")


@dataclass(frozen=True)
class Target:
    """The arm and the belt one program drives, read off the plan."""

    arm: ControllerManager
    conveyor: Conveyor
    grip_width_m: float
    belt_run_s: float


def target(plan: Plan) -> Target:
    """Pick the arm and the belt out of the plan, or say why this cell cannot run it."""
    arms = [m for m in plan.controller_managers if m.moveit is not None and m.skills]
    if len(arms) != 1 or len(plan.conveyors) != 1:
        raise ValueError(
            f"zone {plan.zone} has {len(arms)} arm(s) and {len(plan.conveyors)} belt(s); "
            "this program drives a cell with exactly one of each"
        )
    arm, conveyor = arms[0], plan.conveyors[0]
    missing = [pose for pose in POSES if pose not in arm.moveit.poses_rad]
    if missing:
        raise ValueError(
            f"{arm.asset} in zone {plan.zone} declares no pose {missing} in L0 "
            "`configuration.poses_rad`; teach them there (ADR-0066)"
        )
    # The width Pick itself closes to, from the end effector's L0 declaration.
    width = arm.gripper.get("gripper_default_grasp_width_m")
    if width is None:
        raise ValueError(f"the plan states no default grasp width for {arm.asset}")
    # Long enough to carry the part from where it is placed to the belt's end:
    # the length between the belt's two generated frames, at its installed speed.
    infeed = frame(plan, f"{plan.zone}__{conveyor.asset}__infeed")
    outfeed = frame(plan, f"{plan.zone}__{conveyor.asset}__outfeed")
    return Target(
        arm=arm,
        conveyor=conveyor,
        grip_width_m=width,
        belt_run_s=math.dist(infeed, outfeed) / conveyor.installed_speed_mps,
    )


def program(cell: Target) -> list[Step]:
    """One cycle of the cell, step by step."""
    return [
        move("home"),
        release(),
        move("pick_above"),
        move("pick"),
        grip(cell.grip_width_m, expect_object=True),
        move("pick_above"),
        move("place_above"),
        move("place"),
        release(),
        move("place_above"),
        move("home"),
        belt(cell.conveyor.installed_speed_mps),
        wait(cell.belt_run_s),
        belt(0.0),
    ]
