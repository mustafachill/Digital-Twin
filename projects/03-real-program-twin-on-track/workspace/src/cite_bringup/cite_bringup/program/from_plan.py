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

"""The program the real robot runs, as the bring-up plan states it (ADR-0067).

The steps are not written in this package at all. They are read from the real
xArm 5's own UFACTORY Studio program by `cite_tools.model.blockly` when the plan
is generated, and arrive here as the plan's `programs:` block, in SI units. This
module only maps each one onto the program vocabulary in `steps`:

    move   -> `MoveTo` to a named pose, at the program's velocity scaling
    grip   -> `Grasp` to a width; a close expects a part
    wait   -> a dwell in the cell's own clock
    track  -> a move of the linear track's carriage

`cell_b_pick_place` is the fixed list ADR-0066 wrote by hand; it is kept as that
record and is no longer what `python3 -m cite_bringup.program` runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_bringup.plan import ControllerManager, Plan, Program, Track
from cite_bringup.program.steps import grip, move, Step, track, wait


@dataclass(frozen=True)
class Target:
    """The arm one program drives, its track, and the program, read off the plan."""

    arm: ControllerManager
    track: Track | None
    program: Program


def target(plan: Plan) -> Target:
    """Pick the arm that runs a program out of the plan, or say why there is none."""
    if len(plan.programs) != 1:
        raise ValueError(
            f"zone {plan.zone} states {len(plan.programs)} program(s); this runner drives "
            "exactly one arm. A program is declared in L0 as the arm's "
            "`configuration.program` (ADR-0067)."
        )
    (declared,) = plan.programs
    managers = {manager.asset: manager for manager in plan.controller_managers}
    arm = managers.get(declared.asset)
    if arm is None or arm.skills is None or arm.moveit is None:
        raise ValueError(
            f"the program in zone {plan.zone} is for {declared.asset!r}, which the plan "
            "gives no skill server"
        )
    missing = sorted(
        {s.pose for s in declared.steps if s.kind == "move"} - {"home", *arm.moveit.poses_rad}
    )
    if missing:
        raise ValueError(f"the program moves to {missing}, which the plan names no pose for")
    if arm.track is None and any(s.kind == "track" for s in declared.steps):
        raise ValueError(f"the program moves a track and {arm.asset} rides none")
    return Target(arm=arm, track=arm.track, program=declared)


def program(cell: Target) -> list[Step]:
    """One cycle of the arm's program, step by step."""
    steps: list[Step] = []
    for step in cell.program.steps:
        if step.kind == "move":
            steps.append(move(step.pose, step.velocity_scaling))
        elif step.kind == "grip":
            steps.append(grip(step.width_m, expect_object=step.expect_object))
        elif step.kind == "wait":
            steps.append(wait(step.seconds))
        elif step.kind == "track":
            steps.append(track(step.position_m, step.speed_mps))
        else:  # pragma: no cover - the plan reader refuses any other kind
            raise ValueError(f"unknown step kind {step.kind!r}")
    return steps
