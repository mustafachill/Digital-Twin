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

"""The operator's go-ahead before a run commands a physical side (ADR-0070 item 7).

The ONE place a person is asked into the physical cell: `python3 -m
cite_bringup.program` asks it before every run through the twin on a pair with a
physical side, and `./scripts/program` only hands this process its terminal
(SA-S-02). The question is asked only once the twin's mode has been READ as SIM,
where nothing crosses to the physical side, so the prompt's "the twin forwards
nothing" is a fact and not an assumption (SA-S-05).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cite_bringup.program.steps import StepFailed
from cite_interfaces.msg import TwinMode


def confirm_operator(
    mode: int | None,
    physical: Sequence[str],
    scale: float,
    say: Callable[[str], None],
    read: Callable[[str], str],
    carriage_refusal: Callable[[], str | None],
) -> None:
    """Ask the operator to place the part and clear the cell, once the twin is in SIM.

    ``mode`` is the twin's mode as read from `TwinMode.TOPIC`, `None` when none
    was heard. Anything but SIM refuses before a word is said to the operator.
    ``carriage_refusal`` is asked next, in SIM (`RosCell.carriage_refusal`): a
    physical carriage standing away from the plant's refuses the run before the
    operator is asked, never after (S-08). ``read`` is `input`: an end of input
    is no answer, and refuses.
    """
    if mode is None:
        raise StepFailed(
            f"no twin mode was heard on {TwinMode.TOPIC}, so the operator is not asked "
            "into the cell; is the pair up?"
        )
    if mode != TwinMode.MODE_SIM:
        raise StepFailed(
            f"the twin is in mode {mode}, not SIM ({TwinMode.MODE_SIM}): it may still "
            f"command {', '.join(physical)}, so no one is asked into the cell. Put it in "
            "SIM first"
        )
    refusal = carriage_refusal()
    if refusal is not None:
        raise StepFailed(refusal)
    for side in physical:
        say(f"{side} is physical and runs at speed scale {scale:g}.")
        say(
            f"The twin is in SIM and forwards nothing to {side}, but its ARM IS ENABLED "
            "and holds where it stands."
        )
    try:
        read("Place the part on the table by hand, clear the cell, then press Enter. ")
    except EOFError:
        raise StepFailed(
            "no operator answer (end of input): a physical side needs one at this terminal"
        ) from None
