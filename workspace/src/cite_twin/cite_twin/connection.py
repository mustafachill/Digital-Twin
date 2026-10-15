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

"""Whether each KEPT physical side is up now, as the pair supervisor says (ADR-0077).

The twin boundary of an operator console's pair is started with
`--side-states stdin`: the supervisor, which owns each side's process, writes
one line on the boundary's standard input every time a kept side's state
changes (`readiness.side_state_line`). This module is what those lines mean,
with no node, no thread and no clock, so it is tested without a graph; the
boundary feeds it lines under its own lock.

**Up is a process fact, not a permission.** A side `up` here is one whose
launch announced readiness; whether a mode may command it is still the
boundary's measurement of its deadman, controller and joints
(`physical_readiness`), and a connected side is HELD until an operator's Start
robot (ADR-0076). What this module adds is the other direction: a side that is
NOT up is not running, whatever was last heard from it.

**It fails closed.** Before the first line every kept side is `waiting`; a
line that is not a whole state line moves nothing; and the end of the input -
the supervisor gone - is `down` for every kept side.
"""

from __future__ import annotations

from collections.abc import Iterable

from cite_bringup.readiness import (
    KEPT_ATTEMPTS,
    parsed_side_state,
    SIDE_CONNECTING,
    SIDE_DOWN,
    SIDE_FAILED,
    SIDE_UP,
    SIDE_WAITING,
)

#: What the operator reads for a kept side that is not up, by its state.
DETAILS = {
    SIDE_WAITING: "waiting for the robot on the network",
    SIDE_CONNECTING: "connecting",
    SIDE_DOWN: "disconnected, reconnecting",
    SIDE_FAILED: (
        f"failed to connect {KEPT_ATTEMPTS} times, or refused its configuration; not "
        "retried, see the log"
    ),
}


class Connections:
    """The supervisor's word on each kept side; every side not kept is always up."""

    def __init__(self, kept: Iterable[str] = ()) -> None:
        self._state = {side: SIDE_WAITING for side in kept}

    @property
    def kept(self) -> tuple[str, ...]:
        return tuple(self._state)

    def state(self, side: str) -> str | None:
        """Return the kept side's state, or None for a side that is not kept."""
        return self._state.get(side)

    def up(self, side: str) -> bool:
        """Whether ``side`` runs now: any side not kept, and a kept one that is `up`."""
        return self._state.get(side, SIDE_UP) == SIDE_UP

    def apply(self, line: str) -> tuple[str, str, str] | None:
        """Take one line; return ``(side, before, after)`` if it changed a kept side."""
        parsed = parsed_side_state(line)
        if parsed is None:
            return None
        side, state = parsed
        before = self._state.get(side)
        if before is None or before == state:
            return None
        self._state[side] = state
        return side, before, state

    def end_of_input(self) -> list[tuple[str, str, str]]:
        """Mark every kept side not already failed `down`: the supervisor is gone."""
        changed = []
        for side, before in self._state.items():
            if before in (SIDE_DOWN, SIDE_FAILED):
                continue
            self._state[side] = SIDE_DOWN
            changed.append((side, before, SIDE_DOWN))
        return changed

    def connecting(self) -> tuple[str, ...]:
        return tuple(side for side, state in self._state.items() if state == SIDE_CONNECTING)

    def failed(self) -> tuple[str, ...]:
        return tuple(side for side, state in self._state.items() if state == SIDE_FAILED)

    def absent(self) -> list[str]:
        """Why each kept side that is not up does not run, as `<side>: <reason>`."""
        return [
            f"{side}: {DETAILS[state]}"
            for side, state in self._state.items()
            if state != SIDE_UP
        ]
