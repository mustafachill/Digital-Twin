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

"""The fixed program (ADR-0066), run against a fake cell: order, stop, belt off.

Nothing here moves an arm. What moves one is `tests/scenarios/program_cycle.py`.
"""

from __future__ import annotations

import math

from cite_bringup.demo import frame
from cite_bringup.plan import default_plan_path, load
from cite_bringup.program.cell import twin_name
from cite_bringup.program.cell_b_pick_place import program, target
from cite_bringup.program.steps import EXIT_INTERRUPTED, run, StepFailed
import pytest

ZONE = "cell_b"


class FakeCell:
    """Records every call; fails or interrupts on the step it is told to."""

    def __init__(self, fail_on: str | None = None, interrupt_on: str | None = None) -> None:
        self.calls: list[tuple] = []
        self._fail_on = fail_on
        self._interrupt_on = interrupt_on

    def _record(self, *call) -> None:
        self.calls.append(call)
        if call[:2] == ("move", self._fail_on):
            raise StepFailed(f"move to {self._fail_on}: result code 3: refused")
        if call[:2] == ("move", self._interrupt_on):
            raise KeyboardInterrupt

    def move(self, pose: str) -> None:
        self._record("move", pose)

    def grip(self, width_m: float, expect_object: bool) -> None:
        self._record("grip", width_m, expect_object)

    def belt(self, speed_mps: float) -> None:
        self._record("belt", speed_mps)

    def wait(self, seconds: float) -> None:
        self._record("wait", seconds)

    def cancel(self) -> None:
        self._record("cancel")


@pytest.fixture(scope="module")
def cell():
    return target(load(default_plan_path(ZONE)))


def _quiet(_: str) -> None:
    pass


def test_the_program_reads_top_to_bottom(cell) -> None:
    fake = FakeCell()
    assert run(program(cell), fake, cycles=1, say=_quiet) == 0
    moves = [call[1] for call in fake.calls if call[0] == "move"]
    assert moves == [
        "home", "pick_above", "pick", "pick_above",
        "place_above", "place", "place_above", "home",
    ]
    grips = [call for call in fake.calls if call[0] == "grip"]
    assert [expect for _, _, expect in grips] == [False, True, False]
    assert grips[1][1] == cell.grip_width_m
    belts = [call[1] for call in fake.calls if call[0] == "belt"]
    assert belts[:2] == [cell.conveyor.installed_speed_mps, 0.0]


def test_the_numbers_come_from_the_plan(cell) -> None:
    plan = load(default_plan_path(ZONE))
    assert cell.grip_width_m == cell.arm.gripper["gripper_default_grasp_width_m"]
    infeed = frame(plan, f"{ZONE}__{cell.conveyor.asset}__infeed")
    outfeed = frame(plan, f"{ZONE}__{cell.conveyor.asset}__outfeed")
    assert cell.belt_run_s == pytest.approx(
        math.dist(infeed, outfeed) / cell.conveyor.installed_speed_mps
    )
    assert cell.belt_run_s > 0.0


def test_the_first_failure_stops_the_program_and_the_belt(cell) -> None:
    fake = FakeCell(fail_on="pick")
    assert run(program(cell), fake, cycles=3, say=_quiet) == 1
    moves = [call[1] for call in fake.calls if call[0] == "move"]
    assert moves == ["home", "pick_above", "pick"], "a step ran after the failure"
    assert fake.calls[-2:] == [("cancel",), ("belt", 0.0)]


def test_ctrl_c_cancels_and_stops_the_belt(cell) -> None:
    fake = FakeCell(interrupt_on="place")
    assert run(program(cell), fake, cycles=0, say=_quiet) == EXIT_INTERRUPTED
    assert fake.calls[-2:] == [("cancel",), ("belt", 0.0)]


def test_the_belt_is_stopped_even_after_a_clean_run(cell) -> None:
    fake = FakeCell()
    run(program(cell), fake, cycles=2, say=_quiet)
    assert fake.calls[-1] == ("belt", 0.0)
    assert sum(1 for call in fake.calls if call == ("move", "pick")) == 2


def test_a_cell_without_taught_poses_is_refused() -> None:
    with pytest.raises(ValueError):
        target(load(default_plan_path("cell_a")))


def test_the_twin_name_is_the_sides_name_in_the_twin_scope() -> None:
    assert twin_name("/cite/cell_b/picker/move_to") == "/cite/twin/cell_b/picker/move_to"
    with pytest.raises(ValueError):
        twin_name("/elsewhere/move_to")
