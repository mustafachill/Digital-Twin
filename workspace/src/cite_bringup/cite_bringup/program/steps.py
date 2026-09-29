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

"""The program's vocabulary: five kinds of step, and one loop that runs them.

A step is data, so a program can be printed (`--dry-run`) and tested without a
cell. What a step DOES is a `Cell`'s job: `RosCell` below talks to the arm and
the belt, and the tests hand in a fake. Every step is one blocking call, and any
answer but SUCCESS stops the program — there is no retry and no recovery here,
because a fixed program that carried on after a failed grasp would be carrying
nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import math
import signal
import threading
from typing import Protocol

#: A release asks for the jaws fully open. L3 clamps a width beyond the
#: linkage's reach to its widest opening (`cite_skills::gripper_position_for`),
#: so asking for "wider than anything" is "fully open" without this module
#: restating the linkage.
FULLY_OPEN_M = math.inf

#: What Ctrl-C exits with, by the shell's convention for SIGINT.
EXIT_INTERRUPTED = 130


@dataclass(frozen=True)
class Step:
    """One step of a program. `kind` says which of the other fields it reads."""

    kind: str
    pose: str = ""
    width_m: float = 0.0
    expect_object: bool = False
    speed_mps: float = 0.0
    seconds: float = 0.0

    def __str__(self) -> str:
        if self.kind == "move":
            return f"move to {self.pose}"
        if self.kind == "grip":
            if math.isinf(self.width_m):
                return "open the gripper"
            what = "expecting a part" if self.expect_object else "expecting nothing"
            return f"close the gripper to {self.width_m * 1000:.1f} mm, {what}"
        if self.kind == "belt":
            if self.speed_mps == 0.0:
                return "stop the belt"
            return f"run the belt at {self.speed_mps:g} m/s"
        return f"wait {self.seconds:.2f} s"


def move(pose: str) -> Step:
    """Move the arm to a named joint pose: `home` or one L0 declares."""
    return Step("move", pose=pose)


def grip(width_m: float, expect_object: bool = True) -> Step:
    """Close the gripper to ``width_m``; with ``expect_object``, closing on nothing fails."""
    return Step("grip", width_m=width_m, expect_object=expect_object)


def release() -> Step:
    """Open the gripper fully."""
    return Step("grip", width_m=FULLY_OPEN_M, expect_object=False)


def belt(speed_mps: float) -> Step:
    """Command the belt to a speed, in m/s. Zero stops it."""
    return Step("belt", speed_mps=speed_mps)


def wait(seconds: float) -> Step:
    """Wait, in the cell's own clock, so simulated time is honoured."""
    return Step("wait", seconds=seconds)


class StepFailed(RuntimeError):
    """A step the cell did not complete. The message says which and why."""


class Cell(Protocol):
    """What a program needs from the cell. `RosCell` is the real one."""

    def move(self, pose: str) -> None: ...

    def grip(self, width_m: float, expect_object: bool) -> None: ...

    def belt(self, speed_mps: float) -> None: ...

    def wait(self, seconds: float) -> None: ...

    def cancel(self) -> None: ...


def execute(step: Step, cell: Cell) -> None:
    """Hand one step to the cell."""
    if step.kind == "move":
        cell.move(step.pose)
    elif step.kind == "grip":
        cell.grip(step.width_m, step.expect_object)
    elif step.kind == "belt":
        cell.belt(step.speed_mps)
    elif step.kind == "wait":
        cell.wait(step.seconds)
    else:
        raise StepFailed(f"unknown step kind {step.kind!r}")


def run(
    steps: Sequence[Step],
    cell: Cell,
    cycles: int,
    say: Callable[[str], None] = print,
    first_cycle: int = 1,
) -> int:
    """Run ``steps`` ``cycles`` times (0: until stopped). Return an exit status.

    ``first_cycle`` only numbers the log lines: a caller that runs one cycle per
    invocation (``scripts/program``, which puts a part on the table between
    cycles) passes its own count so that cycle 3 is not reported as cycle 1.

    However it ends — the last cycle, a failed step, Ctrl-C — the active goal is
    cancelled and the belt is commanded to zero on the way out. A physical belt
    is a drive whose setpoint persists (ADR-0038), so a program that stopped
    without saying so would leave it running; a stop that could not be sent is
    therefore a failure of the run, whatever the steps did.
    """
    done = 0
    cycle = first_cycle - 1
    status = 1
    try:
        while cycles == 0 or done < cycles:
            done += 1
            cycle += 1
            for number, step in enumerate(steps, start=1):
                say(f"[cycle {cycle}, step {number}/{len(steps)}] {step}")
                execute(step, cell)
        say(f"done: {done} cycle(s)")
        status = 0
    except StepFailed as failure:
        say(f"FAILED in cycle {cycle}: {failure}")
        status = 1
    except KeyboardInterrupt:
        say(f"interrupted in cycle {cycle}")
        status = EXIT_INTERRUPTED
    finally:
        # A terminal's Ctrl-C reaches this process AND the script that started
        # it, and the script forwards one more; a second KeyboardInterrupt here
        # would abandon the cancel or the stop half-way.
        with _interrupts_ignored():
            stopped = _stop(cell, say)
    if not stopped:
        say("FAILED: the belt was NOT confirmed stopped; it may still be running")
        return status or 1
    return status


def install_interrupt_handlers() -> None:
    """Make SIGINT and SIGTERM raise KeyboardInterrupt, whatever this process inherited.

    A job started with `&` by a non-interactive shell inherits SIGINT as
    SIG_IGN, and Python then installs no handler of its own, so Ctrl-C would
    never reach `run` and nothing would cancel the goal or stop the belt.
    """
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)


@contextmanager
def _interrupts_ignored() -> Iterator[None]:
    """Ignore SIGINT and SIGTERM for the duration, then restore what was there."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {
        number: signal.signal(number, signal.SIG_IGN)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _stop(cell: Cell, say: Callable[[str], None]) -> bool:
    """Cancel whatever is in flight, then stop the belt, each attempted regardless.

    Return whether the belt's stop was sent.
    """
    try:
        cell.cancel()
    except Exception as error:  # noqa: BLE001 - reported, and the stop still runs
        say(f"could not cancel the active goal: {error}")
    try:
        cell.belt(0.0)
    except Exception as error:  # noqa: BLE001 - reported, and made the exit status
        say(f"could not stop the belt: {error}")
        return False
    return True
