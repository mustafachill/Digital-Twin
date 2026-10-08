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

"""The program's one sequencer: the order that keeps a person out of a moving cell.

Three callers drive the cell, and each used to state this order itself:
`python3 -m cite_bringup.program` (`__main__`), `python3 -m
cite_bringup.program.home` (`./scripts/home`) and the operator console
(`console_machine`, ADR-0071). Now each calls these functions, and a change to
the order is made once.

* `run_program`, before the program: on a physical side the twin's mode READ as
  SIM, the carriage judged and the operator's go-ahead awaited
  (`operator.confirm_operator`); the arm's custody read; VALIDATED - through
  `home.bring_to_start` when the run homes first; then `steps.run`; then, on a
  physical side, SIM again, whatever happened.
* `home`: the same gate with the home prompt, `home.bring_to_start`, and SIM
  again on a physical side.
* `start_robot`: the gate without a carriage check - nothing has initialized the
  track yet - then every physical arm's initialization, then custody.

What differs between the callers is injected, never branched on here:
``await_operator`` is `input` at a terminal and the panel's confirmation in the
console; ``say`` prints or publishes; ``on_step`` reports progress as data; and
the cell's own ``interrupted`` (`RosCell`) is how the console's stop reaches a
wait, as Ctrl-C reaches one at a terminal - both as `KeyboardInterrupt`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cite_bringup.program.home import bring_to_start, StartPose
from cite_bringup.program.operator import confirm_operator, PLACE_PROMPT
from cite_bringup.program.steps import EXIT_INTERRUPTED, run, Step, StepFailed


@dataclass(frozen=True)
class Ended:
    """How a sequence ended: an exit status, and what the console reports from it."""

    #: 0, 1, or `steps.EXIT_INTERRUPTED`, as the command line exits.
    status: int
    #: Why it failed before the program's own steps, or None. A step's failure
    #: inside `steps.run` is said there and not repeated here.
    failure: str | None = None
    #: Whether the twin confirmed SIM afterwards; None where it was not asked.
    sim_confirmed: bool | None = None


@dataclass(frozen=True)
class Homing:
    """What a run that homes before its first cycle needs (`home.bring_to_start`)."""

    steps: Sequence[Step]
    start: StartPose
    initialize_physical: Callable[[], None]


def start_robot(
    cell,
    *,
    physical: Sequence[str],
    say: Callable[[str], None],
    await_operator: Callable[[str], str],
    initialize_physical: Callable[[], None],
    prompt: str,
) -> None:
    """Enable the robot: on a physical side, SIM read and the cell cleared first.

    The initializer may home the physical track and bring the carriage to the
    program's start, so on a physical side it runs only once the twin's mode
    is read as SIM and the operator has confirmed ``prompt`` (ADR-0071). The
    carriage is not judged first: initializing is what gives it a position.
    Then custody. Raises `StepFailed` or `KeyboardInterrupt`; leaves the twin's
    mode alone.
    """
    if physical:
        confirm_operator(
            cell.twin_mode(), physical, None, say, await_operator, lambda: None, prompt=prompt
        )
    initialize_physical()
    cell.refuse_if_holding()


def home(
    cell,
    steps: Sequence[Step],
    start: StartPose,
    *,
    physical: Sequence[str],
    scale: float,
    say: Callable[[str], None],
    await_operator: Callable[[str], str],
    initialize_physical: Callable[[], None],
    prompt: str,
    console: str | None = None,
) -> Ended:
    """Bring both arms to the program's start; on a physical side, SIM again after.

    The gate (`_ask_the_operator`, with ``homing``: a carriage apart is what
    the home brings back), then `home.bring_to_start`. Says `done: ...`,
    `FAILED: ...` or `interrupted`, as `./scripts/home` always has.

    ``console`` is the zone's console state topic, given by a TERMINAL caller:
    where a console serves the pair the home is refused before anything -
    SIM is not asked for either, since the console may hold VALIDATED (N-01).
    """
    refused = _refused_for_a_console(cell, console, say)
    if refused is not None:
        return refused
    status = 1
    failure: str | None = None
    try:
        try:
            _ask_the_operator(
                cell, physical, scale, say, await_operator, prompt, homing=True
            )
            bring_to_start(list(steps), start, cell, initialize_physical, say)
            say("done: both arms are at the program's start")
            status = 0
        except StepFailed as error:
            failure = str(error)
            say(f"FAILED: {failure}")
        except KeyboardInterrupt:
            say("interrupted")
            status = EXIT_INTERRUPTED
    finally:
        # The operator's next step may be in the cell, so SIM is asked for
        # whatever happened (SA-S-05).
        sim = cell.leave_validated() if physical else None
    if sim is False:
        status = status or 1
    return Ended(status, failure, sim)


def run_program(
    cell,
    steps: Sequence[Step],
    *,
    physical: Sequence[str],
    scale: float,
    cycles: int,
    say: Callable[[str], None],
    await_operator: Callable[[str], str],
    prompt: str = PLACE_PROMPT,
    via_twin: bool = True,
    homing: Homing | None = None,
    first_cycle: int = 1,
    on_step: Callable[[int, int, int, Step], None] | None = None,
    banner: str | None = None,
    console: str | None = None,
) -> Ended:
    """Gate, custody, VALIDATED (homing first if asked), the program, then SIM again.

    Before the first step a failure says `FAILED before the first step: ...`
    and an interrupt `interrupted before the first step`, as `python3 -m
    cite_bringup.program` always has; ``banner`` is said just before the
    program runs. On a physical side SIM is asked for once VALIDATED may have
    been asked - after the run, after a failure, after an interrupt - and an
    unconfirmed SIM fails the sequence, so no caller asks a person in next
    (SA-S-05). ``console``, from a terminal caller, refuses the run before
    anything where an operator console serves the pair (N-01, as `home`).
    """
    refused = _refused_for_a_console(cell, console, say)
    if refused is not None:
        return refused
    entering = False
    outcome: tuple[int, str | None] | None = None
    try:
        try:
            # Read, not assumed: the operator is asked in only while the twin
            # forwards nothing to the physical side (SA-S-05). Before a homing
            # first cycle a carriage apart is no refusal here: homing brings it
            # to the start, and the start is measured.
            _ask_the_operator(
                cell, physical, scale, say, await_operator, prompt, homing=homing is not None
            )
            cell.refuse_if_holding()
            entering = via_twin
            if homing is not None:
                bring_to_start(
                    list(homing.steps),
                    homing.start,
                    cell,
                    homing.initialize_physical,
                    say,
                    via_twin=entering,
                )
            elif entering:
                cell.enter_validated()
        except (StepFailed, KeyboardInterrupt) as failure:
            interrupted = isinstance(failure, KeyboardInterrupt)
            say(
                "interrupted before the first step"
                if interrupted
                else f"FAILED before the first step: {failure}"
            )
            outcome = (EXIT_INTERRUPTED, None) if interrupted else (1, str(failure))
        if outcome is None:
            if banner is not None:
                say(banner)
            status = run(steps, cell, cycles, say, first_cycle=first_cycle, on_step=on_step)
            outcome = (status, None)
    finally:
        # VALIDATED may have been entered: the operator's next step is in the
        # cell, so SIM is asked for whatever happened (SA-S-05).
        sim = cell.leave_validated() if physical and entering else None
    status, failure_text = outcome
    if sim is False:
        status = status or 1
    return Ended(status, failure_text, sim)


def _refused_for_a_console(
    cell, console: str | None, say: Callable[[str], None]
) -> Ended | None:
    """Refuse a terminal client where an operator console serves the pair (N-01), or None.

    One operator surface per pair: the console's own sequence goes through
    this module too, and never passes ``console``.
    """
    if console is None:
        return None
    try:
        refusal = cell.console_refusal(console)
    except StepFailed as failure:
        refusal = f"could not tell whether an operator console serves this pair: {failure}"
    if refusal is None:
        return None
    say(f"REFUSED: {refusal}")
    return Ended(1, refusal, None)


def _ask_the_operator(
    cell,
    physical: Sequence[str],
    scale: float | None,
    say: Callable[[str], None],
    await_operator: Callable[[str], str],
    prompt: str,
    *,
    homing: bool,
) -> None:
    """On a physical side: SIM read, the carriage judged, then the operator asked."""
    if physical:
        confirm_operator(
            cell.twin_mode(),
            physical,
            scale,
            say,
            await_operator,
            lambda: cell.carriage_refusal(homing=homing),
            prompt=prompt,
        )
