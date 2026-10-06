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

"""Whether every commanded side's track stands at a target (SA2c-S-02 c).

The program reads arrival on its own domain, which through the twin is the
plant's. The counterpart's carriage - the physical one - is read only by the
boundary, so the boundary answers `TrackArrived` for every side the mode
commands and every physical side, with why: AWAY, which does not clear by
itself, or UNHEARD, which does (S-08). Pure logic with no node, so it is tested
without a graph; the boundary feeds it what it has heard, under its own lock.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from cite_interfaces.srv import TrackArrived


def _unheard(
    side: str,
    heard: tuple[float, float] | None,
    physical: bool,
    now: float,
    max_age_s: float | None,
) -> str | None:
    """Why ``side``'s track position cannot be counted, or `None` when it can.

    A physical side's counts only while younger than ``max_age_s``: a carriage
    read too long ago may be anywhere since. A simulated side's position is its
    simulator's, held by its own controller.
    """
    if heard is None:
        return f"{side}: no track position heard"
    if not physical:
        return None
    if max_age_s is None:
        return f"{side}: physical, and the plan states no state_max_age_s"
    if now - heard[1] > max_age_s:
        return f"{side}: its track position is {now - heard[1]:.2f} s old, above {max_age_s:g} s"
    return None


def _away(side: str, position: float, target_m: float, tolerance_m: float) -> str | None:
    if abs(position - target_m) <= tolerance_m:
        return None
    return (
        f"{side}: stands at {position * 1000:.1f} mm, not within "
        f"{tolerance_m * 1000:g} mm of {target_m * 1000:.1f} mm"
    )


def arrival(
    sides: Iterable[str],
    heard: Mapping[str, tuple[float, float]],
    physical: Iterable[str],
    target_m: float,
    tolerance_m: float,
    now: float,
    max_age_s: float | None,
) -> tuple[int, str | None]:
    """Return the `TrackArrived` reason for ``sides``, and why, or `(ARRIVED, None)`.

    ``heard`` is each side's last track position and its steady-clock arrival.
    A side in ``physical`` counts only with a position younger than
    ``max_age_s`` (`_unheard`). AWAY outranks UNHEARD: a side heard standing
    elsewhere does not clear by itself, a position not heard yet does.
    """
    stale_bound = set(physical)
    away = []
    unheard_sides = []
    for side in sides:
        position = heard.get(side)
        reason = _unheard(side, position, side in stale_bound, now, max_age_s)
        if reason is not None:
            unheard_sides.append(reason)
        elif (reason := _away(side, position[0], target_m, tolerance_m)) is not None:
            away.append(reason)
    if away:
        return TrackArrived.Response.AWAY, "; ".join(away + unheard_sides)
    if unheard_sides:
        return TrackArrived.Response.UNHEARD, "; ".join(unheard_sides)
    return TrackArrived.Response.ARRIVED, None


def elsewhere(
    side: str,
    physical: tuple[float, float] | None,
    target_m: float,
    tolerance_m: float,
    now: float,
    max_age_s: float | None,
) -> str | None:
    """Return why a physical carriage KNOWN to stand away from ``target_m`` does, or `None`.

    `None` when it stands there, and also when its position cannot be counted:
    this is a disagreement that is heard, which does not clear by itself, never
    a position not heard yet, which does (S-08).
    """
    if _unheard(side, physical, True, now, max_age_s) is not None:
        return None
    return _away(side, physical[0], target_m, tolerance_m)


def unheard(
    joint: str,
    plant: tuple[float, float] | None,
    physical_side: str,
    physical: tuple[float, float] | None,
    now: float,
    max_age_s: float | None,
) -> str | None:
    """Return why the physical carriage cannot be compared with the plant's YET, or `None`.

    A position not heard, or too old, is a precondition that clears by itself
    once the physical side publishes; that the carriage stands elsewhere is
    `apart`, and does not (S-08).
    """
    if plant is None:
        return f"no plant {joint} position heard to compare the physical carriage with"
    return _unheard(physical_side, physical, True, now, max_age_s)


def apart(
    joint: str,
    plant: tuple[float, float] | None,
    physical_side: str,
    physical: tuple[float, float] | None,
    tolerance_m: float,
    now: float,
    max_age_s: float | None,
) -> str | None:
    """Return why a physical carriage stands where the plant's does NOT, or `None`.

    SA-S-01 b: the precondition of a mode that commands a physical side. A
    program reads only the plant's carriage, and a track step whose target the
    plant already stands at commands nothing; so the twin does not start
    commanding a physical carriage that stands anywhere else. Only a fresh
    physical position counts, and the plant's is its simulator's; while either
    cannot be counted the answer is `unheard`'s, not this one. Never clears by
    itself (S-08): a carriage is brought there from outside the cell.
    """
    if plant is None:
        return None
    reason = elsewhere(physical_side, physical, plant[0], tolerance_m, now, max_age_s)
    if reason is None:
        return None
    return (
        f"{joint} is not where the plant's stands ({plant[0] * 1000:.1f} mm) - {reason}; "
        "bring the physical carriage there (home it) first"
    )
