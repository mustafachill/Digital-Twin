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

"""The lines a participant prints when it has finished coming up, and their readers.

ADR-0047 clause 3: a side announces its own readiness **on its own standard
output**, and the pair supervisor's readiness fact is that line arriving on that
side's pipe. This module is the token, stated once and imported by both ends —
the launch graph that emits it and the supervisor that reads it. Two string
literals would be the same defect this whole design is built to avoid, in
miniature.

**Two tokens rather than one, because they are two different facts**
(ADR-0057). A side announcing is *this cell is up*; the boundary announcing is
*the process spanning the two cells is serving*. They are emitted by different
programs, read at different points of the same join, and the supervisor starts
the second only after both of the first have arrived — so a supervisor that
accepted either word from either participant could report a pair complete on two
copies of one announcement. The mechanism is shared and the words are not.

**Standard output rather than a ready file, and the reason is this repository's
own rig.** The second-world-cost campaign joined its two cells with ready files
and had to `rm -f` them before every run. A stale ready file is a false join: it
reports a side up that was never started this time. A pipe has no state to go
stale, cannot be written by anything except the child that owns it, and needs no
polling interval — a blocking read on it is not a timer.

Nothing here imports `rclpy`, and that is load-bearing rather than incidental:
the supervisor imports this module, and ADR-0047 clause 2 forbids the supervisor
an import graph that reaches a ROS client library. See
`cite_bringup/test/test_pair.py` for the check that makes that a fact rather than
a promise.
"""

from __future__ import annotations

#: The fixed word a ready line begins with.
#:
#: Deliberately not a sentence anything else would print. The supervisor scans
#: every line of a side's output for it, and that output also carries three
#: Gazebo servers' worth of logging, so the token has to be one a log line does
#: not produce by accident. It is uppercase and prefixed for the same reason.
READY_TOKEN = "CITE_SIDE_READY"


def ready_announcement(side: str, zone: str) -> str:
    """Format the one line a side emits when its own gate chain has completed.

    The side is named in the line even though the supervisor already knows which
    child's pipe it is reading. That redundancy is the check: a launch started
    with the wrong `side:=` argument would otherwise announce readiness for a
    side the supervisor believes is the other one, which is precisely the class
    of error the two isolations exist to prevent and the one thing the supervisor
    is positioned to catch for free.
    """
    return f"{READY_TOKEN} side={side} zone={zone}"


def announced_side(line: str) -> str | None:
    """Return the side named by a ready line, or ``None`` if this is not one.

    Substring rather than prefix matching, because `launch` prefixes what it logs
    — the emitter's line reaches the pipe as `[INFO] [launch.user]: CITE_SIDE_READY
    side=plant zone=cell_b`. Matching on the token rather than on the start of the
    line keeps this reader independent of that formatting, which is upstream's and
    not ours.
    """
    if READY_TOKEN not in line:
        return None
    for field in line.split():
        if field.startswith("side="):
            return field[len("side="):]
    return None


#: The fixed word the twin boundary's ready line begins with (ADR-0057).
#:
#: A word of its own rather than `READY_TOKEN` with a different field, and the
#: reason is the join it feeds: the supervisor waits for two sides and then for
#: one boundary, on three pipes it is reading at once. One token for both would
#: make "both sides announced" and "a side announced twice" the same observation
#: at the point where the difference decides whether L5 is started.
BOUNDARY_TOKEN = "CITE_BOUNDARY_READY"


def boundary_announcement(zone: str) -> str:
    """Format the one line the twin boundary emits when it is being served.

    The zone is named for the same reason a side's name is: the supervisor
    already knows which zone it asked for, so a boundary announcing another one
    is a boundary spanning a cell nobody asked for, and the supervisor is
    positioned to catch it for free.

    **This said "the one error neither argument's own reader catches" until
    2026-09-18, and that was wrong about the reader it names.** `twin_boundary`'s
    own `main` compares `--zone` against the zone its `--plan` declares and exits
    2 when they disagree, so the boundary refuses that pair itself. What the
    supervisor's check is worth is what a check on a pipe is always worth: it is
    an independent statement, read from what the process SAID rather than from
    what it was given, so it survives a program that ignores its arguments, that
    resolves a different plan, or that is not the process the supervisor thinks
    it started. Redundancy, not sole cover.

    **What the line means is stronger than "the process started".** It is
    printed from inside the executor that serves the boundary's endpoints, so it
    says they are being served rather than that they exist. A join on "about to"
    is the timing guess P4 forbids.
    """
    return f"{BOUNDARY_TOKEN} zone={zone}"


def announced_boundary(line: str) -> str | None:
    """Return the zone named by a boundary ready line, or ``None`` if it is not one.

    Substring rather than prefix matching, for the reason
    :func:`announced_side` gives: what a supervisor reads on a pipe has whatever
    prefix the emitter's own framework put there, and that formatting is
    upstream's and not ours.
    """
    return _zone_announced(BOUNDARY_TOKEN, line)


#: The fixed word the operator console prints once it is being served
#: (ADR-0071). A third word for a third fact: *the console, whose node lives on
#: the plant's domain, is serving its requests*. The supervisor starts it only
#: after the boundary announced, because every request it serves goes through
#: the boundary; a word shared with the boundary's would let one announcement be
#: read as both.
CONSOLE_TOKEN = "CITE_CONSOLE_READY"


def console_announcement(zone: str) -> str:
    """Format the one line the operator console emits when it is being served.

    The zone is named for the reason the boundary names it: the supervisor
    knows which zone it started the console for, and checks the line against
    it. Printed from inside the executor that serves the console's endpoints,
    once they exist, so it says they are served rather than that they will be.
    """
    return f"{CONSOLE_TOKEN} zone={zone}"


def announced_console(line: str) -> str | None:
    """Return the zone named by a console ready line, or ``None`` if it is not one."""
    return _zone_announced(CONSOLE_TOKEN, line)


#: The fixed word a side's launch prints when its simulator's WINDOW was closed
#: (ADR-0078 decision 3). A fourth word for a fourth fact, and the only one that
#: is not readiness: *the operator ended this side by closing its window*. The
#: supervisor reads it as a stop asked for rather than a side lost, so an
#: ordinary close is a clean end and `PAIR_ENDED` keeps meaning a participant
#: that went away unexpectedly (open-work #107).
WINDOW_CLOSED_TOKEN = "CITE_WINDOW_CLOSED"


def window_closed_announcement(side: str, zone: str) -> str:
    """Format the one line a side emits when its windowed simulator exited 0.

    The side and zone are named for the reason a ready line names them: the
    supervisor knows which participant's pipe it is reading, and the line says
    which side the launch believes it is.
    """
    return f"{WINDOW_CLOSED_TOKEN} side={side} zone={zone}"


def announced_window_closed(line: str) -> str | None:
    """Return the side named by a window-closed line, or ``None`` if it is not one.

    Substring rather than prefix matching, for the reason :func:`announced_side`
    gives: `launch` prefixes what it logs.
    """
    if WINDOW_CLOSED_TOKEN not in line:
        return None
    for field in line.split():
        if field.startswith("side="):
            return field[len("side="):]
    return None


def _zone_announced(token: str, line: str) -> str | None:
    """Return the `zone=` field of a line carrying ``token``, or ``None``."""
    if token not in line:
        return None
    for field in line.split():
        if field.startswith("zone="):
            return field[len("zone="):]
    return None


#: Begins the detail of a `SetMode` refusal that clears by itself: the twin
#: boundary will not let a mode command a physical side until that side's
#: deadman has enabled the arm and its controller and joints are publishing
#: (ADR-0070 item 6). Stated here, beside the other words one participant says
#: and another reads, because the boundary (`cite_twin.mode`) writes it and the
#: fixed program (`cite_bringup.program.cell`) waits on it; any other refusal is
#: final.
PHYSICAL_SIDE_NOT_READY = "physical side not ready"


def waits_for_a_physical_side(detail: str) -> bool:
    """Whether a refusal's detail says only that a physical side is not ready yet."""
    return detail.startswith(PHYSICAL_SIDE_NOT_READY)


#: Part of the detail of a `SetMode` refusal that clears once the goals the
#: twin boundary dispatched have ended: it will not publish a mode ahead of a
#: cell whose goals are still running (`cite_twin.twin_boundary`,
#: `_a_transition_may_not_outrun_the_cell`). Stated here for the reason
#: `PHYSICAL_SIDE_NOT_READY` is: the boundary writes it and the program's
#: return to SIM after a cancel (`cite_bringup.program.cell`) waits on it.
GOALS_STILL_RUNNING = "goal(s) L5 dispatched are still running"


def waits_for_goals_to_end(detail: str) -> bool:
    """Whether a refusal's detail says only that dispatched goals are still running."""
    return GOALS_STILL_RUNNING in detail


#: The fixed word a physical side's launch prints once its reach gate found the
#: robot on the network (ADR-0077 decision 3). A fifth word for a fifth fact:
#: *the arm's controller answers on its report port, so the vendor driver may be
#: started against it*. It is not readiness - nothing on the side is up yet -
#: and the pair supervisor reads it as the line between "the robot is not
#: there" (an exit before it is a configuration refusal, not retried) and "the
#: robot is there and the side failed to come up" (retried, a bounded number of
#: times).
REACHABLE_TOKEN = "CITE_SIDE_REACHABLE"


def reachable_announcement(side: str, zone: str) -> str:
    """Format the one line a physical side emits when its robot answered the reach gate.

    The side and zone are named for the reason a ready line names them. The
    robot's address is NOT in it, and never may be: it lives only in the
    process environment (ADR-0070 item 2).
    """
    return f"{REACHABLE_TOKEN} side={side} zone={zone}"


def announced_reachable(line: str) -> str | None:
    """Return the side named by a reachable line, or ``None`` if it is not one.

    Substring rather than prefix matching, for the reason :func:`announced_side`
    gives: `launch` prefixes what it logs.
    """
    if REACHABLE_TOKEN not in line:
        return None
    for field in line.split():
        if field.startswith("side="):
            return field[len("side="):]
    return None


#: The fixed word of a line the pair supervisor writes on the twin boundary's
#: STANDARD INPUT (ADR-0077 decision 4): what the supervisor knows of a kept
#: physical side right now. The other tokens here travel up a pipe from a
#: participant to the supervisor; this one travels down, from the supervisor to
#: the boundary, and it is stated here for the same reason - one statement, read
#: by the end that writes it and the end that parses it.
SIDE_STATE_TOKEN = "CITE_SIDE_STATE"

#: A kept side's states, in the order a connection goes through them.
#:
#: - `waiting`: its launch is started and its reach gate is waiting for the
#:   robot on the network; nothing of the side is up.
#: - `connecting`: the robot answered; the side is coming up (driver, deadman,
#:   controllers) and has not announced.
#: - `up`: the side announced readiness. It is still HELD until an operator's
#:   Start robot releases it (ADR-0076); `up` says the side exists, not that it
#:   may move.
#: - `down`: the side was up and exited; the supervisor is sweeping its group
#:   before it starts it again.
#: - `failed`: the side will not be started again in this run: it refused its
#:   configuration before the robot was reached, or it reached the robot and
#:   failed to come up `KEPT_ATTEMPTS` times in a row (`pair.py`).
SIDE_WAITING = "waiting"
SIDE_CONNECTING = "connecting"
SIDE_UP = "up"
SIDE_DOWN = "down"
SIDE_FAILED = "failed"
SIDE_STATES = (SIDE_WAITING, SIDE_CONNECTING, SIDE_UP, SIDE_DOWN, SIDE_FAILED)


def side_state_line(side: str, state: str) -> str:
    """Format one state line for the boundary's standard input; refuse an unknown state."""
    if state not in SIDE_STATES:
        raise ValueError(f"{state!r} is not a side state; one of {', '.join(SIDE_STATES)}")
    return f"{SIDE_STATE_TOKEN} side={side} state={state}"


def parsed_side_state(line: str) -> tuple[str, str] | None:
    """Return ``(side, state)`` from a state line, or ``None`` if it is not a whole one.

    A line carrying the token with a side missing, or a state not in
    `SIDE_STATES`, is not one: the reader that acts on it moves a physical
    side's availability, and a half-read line must move nothing.
    """
    if SIDE_STATE_TOKEN not in line:
        return None
    side = state = None
    for field in line.split():
        if field.startswith("side="):
            side = field[len("side="):]
        elif field.startswith("state="):
            state = field[len("state="):]
    if not side or state not in SIDE_STATES:
        return None
    return side, state
