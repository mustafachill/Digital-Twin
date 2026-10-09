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

"""The terminal's words and exit codes from the program's one sequencer (R2-05, ADR-0071).

`python3 -m cite_bringup.program` and `./scripts/home` print what
`program.cycle` says and exit with what it returns; an operator, and
`./scripts/program` reading the exit code, act on both. These pin each line and
code on a pair with a physical side, so a renamed message or a changed code
fails here. The cell is a fake recording every call in one log with the lines
said, so the ORDER of a line and a call is pinned too.
"""

from __future__ import annotations

from cite_bringup.program import cycle
from cite_bringup.program.home import StartPose
from cite_bringup.program.steps import EXIT_INTERRUPTED, move
from cite_bringup.program.targets import TWIN
from cite_interfaces.msg import TwinMode
import pytest

START = StartPose(
    pose="zero",
    joints=("joint1",),
    positions=(0.0,),
    tolerance_rad=0.01,
    track_m=None,
    track_tolerance_m=None,
)
PHYSICAL = ["counterpart"]


class Cell:
    """`RosCell` on a pair with a physical side, in SIM; ``raises``: what a call raises."""

    def __init__(self, log: list[str], raises: dict | None = None, left: bool = True) -> None:
        self.log = log
        self.raises = raises or {}
        self.left = left

    def _call(self, name: str) -> None:
        self.log.append(f"call {name}")
        if name in self.raises:
            raise self.raises[name]

    def twin_mode(self) -> int:
        self._call("twin_mode")
        return TwinMode.MODE_SIM

    def carriage_refusal(self, target: int, homing: bool = False):
        self._call("carriage_refusal")
        return None

    def refuse_if_holding(self, sides=("plant",)) -> None:
        self._call("refuse_if_holding")

    def require_running(self, target: int) -> None:
        pass

    def enter_target(self, target: int, homing: bool = False) -> None:
        self._call("enter_target")

    def return_to_sim(self) -> bool:
        self._call("return_to_sim")
        return self.left

    def away_from_start(self, start, sides=()) -> None:
        self._call("measure")
        return None

    def move(self, pose: str, velocity_scaling: float) -> None:
        self._call(f"move {pose}")

    def cancel(self) -> None:
        self._call("cancel")


def _reader(log: list[str], raises: BaseException | None = None):
    def read(prompt: str) -> str:
        log.append(f"asked {prompt}")
        if raises is not None:
            raise raises
        return ""

    return read


def _run(cell: Cell, log: list[str], read) -> cycle.Ended:
    return cycle.run_program(
        cell,
        [move("pick")],
        target=TWIN,
        physical=PHYSICAL,
        scale=0.1,
        cycles=1,
        say=lambda text: log.append(f"said {text}"),
        await_operator=read,
    )


def _home(cell: Cell, log: list[str], read) -> cycle.Ended:
    return cycle.home(
        cell,
        [move("zero")],
        START,
        target=TWIN,
        physical=PHYSICAL,
        scale=0.1,
        say=lambda text: log.append(f"said {text}"),
        await_operator=read,
        initialize_physical=lambda: log.append("call initialize"),
        prompt="HOME?",
    )


def _said(log: list[str]) -> list[str]:
    return [line[len("said "):] for line in log if line.startswith("said ")]


# --- python3 -m cite_bringup.program ----------------------------------------


def test_run_interrupted_at_the_prompt_exits_130_and_leaves_nothing() -> None:
    log: list[str] = []
    ended = _run(Cell(log), log, _reader(log, KeyboardInterrupt()))
    assert ended.status == EXIT_INTERRUPTED == 130
    assert ended.sim_confirmed is None
    assert _said(log)[-1] == "interrupted before the first step"
    assert "call enter_target" not in log and "call return_to_sim" not in log


def test_run_interrupted_while_entering_exits_130_then_leaves() -> None:
    log: list[str] = []
    cell = Cell(log, {"enter_target": KeyboardInterrupt()})
    ended = _run(cell, log, _reader(log))
    assert (ended.status, ended.sim_confirmed) == (130, True)
    said = log.index("said interrupted before the first step")
    assert log[said + 1:] == ["call return_to_sim"]


def test_run_interrupted_in_a_step_cancels_then_leaves() -> None:
    log: list[str] = []
    cell = Cell(log, {"move pick": KeyboardInterrupt()})
    ended = _run(cell, log, _reader(log))
    assert (ended.status, ended.sim_confirmed) == (130, True)
    tail = log[log.index("call move pick"):]
    assert tail == [
        "call move pick",
        "said interrupted in cycle 1",
        "call cancel",
        "call return_to_sim",
    ]


def test_run_with_no_answer_at_the_prompt_exits_1_and_leaves_nothing() -> None:
    log: list[str] = []
    ended = _run(Cell(log), log, _reader(log, EOFError()))
    assert (ended.status, ended.sim_confirmed) == (1, None)
    assert _said(log)[-1] == (
        "FAILED before the first step: no operator answer (end of input): a physical "
        "side needs one at this terminal"
    )
    assert "call return_to_sim" not in log


def test_run_whose_return_to_sim_is_unconfirmed_exits_1() -> None:
    log: list[str] = []
    ended = _run(Cell(log, left=False), log, _reader(log))
    assert (ended.status, ended.sim_confirmed) == (1, False)
    assert "said done: 1 cycle(s)" in log
    assert log[-1] == "call return_to_sim"


def test_a_completed_run_exits_0_after_sim() -> None:
    log: list[str] = []
    ended = _run(Cell(log), log, _reader(log))
    assert (ended.status, ended.sim_confirmed) == (0, True)
    assert log[-2:] == ["call cancel", "call return_to_sim"]


# --- ./scripts/home -----------------------------------------------------------


def test_home_interrupted_at_the_prompt_exits_130_then_asks_for_sim() -> None:
    """A home asks SIM whatever happened (SA-S-05); the prompt's interrupt included."""
    log: list[str] = []
    ended = _home(Cell(log), log, _reader(log, KeyboardInterrupt()))
    assert (ended.status, ended.sim_confirmed) == (130, True)
    assert log[-2:] == ["said interrupted", "call return_to_sim"]
    assert "call initialize" not in log


def test_home_with_no_answer_at_the_prompt_exits_1() -> None:
    log: list[str] = []
    ended = _home(Cell(log), log, _reader(log, EOFError()))
    assert ended.status == 1
    assert _said(log)[-1] == (
        "FAILED: no operator answer (end of input): a physical side needs one at this terminal"
    )
    assert "call initialize" not in log


def test_a_completed_home_says_done_and_exits_0() -> None:
    log: list[str] = []
    ended = _home(Cell(log), log, _reader(log))
    assert (ended.status, ended.sim_confirmed) == (0, True)
    assert log[-2:] == ["said done: both arms are at the program's start", "call return_to_sim"]
    assert log.index("asked Target: the twin (simulation and real arm); physical side(s) "
                     "commanded: counterpart. HOME?") < log.index("call initialize")


@pytest.mark.parametrize("homed", [True, False])
def test_a_home_whose_return_to_sim_is_unconfirmed_exits_1(homed: bool) -> None:
    log: list[str] = []
    raises = {} if homed else {"measure": KeyboardInterrupt()}
    ended = _home(Cell(log, raises, left=False), log, _reader(log))
    assert ended.sim_confirmed is False
    assert ended.status == (1 if homed else 130)
