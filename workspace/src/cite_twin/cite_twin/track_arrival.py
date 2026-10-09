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

from collections.abc import Iterable, Mapping, Sequence

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


def moving(
    joint: str,
    samples: Sequence[tuple[float, float]],
    now: float,
    max_age_s: float | None,
    tolerance_m: float,
) -> str | None:
    """Return why a physical carriage is not reported stationary, or `None` when it is.

    S-02 (ADR-0072): before a person is asked into the cell, the physical
    carriage has to be standing still, and that is judged from the plan's own
    values and nothing chosen here. ``samples`` is the carriage's recent
    positions with their steady-clock arrivals, oldest first. It is stationary
    when the latest is fresh (no older than ``max_age_s``, the plan's
    `state_max_age_s`) and a sample at least ``max_age_s`` before it exists,
    with every sample from that one to the latest within ``tolerance_m`` (the
    track's `goal_tolerance_m`) of the latest: two fresh readings that far
    apart, and nothing between them that moved.
    """
    if max_age_s is None:
        return f"{joint}: physical, and the plan states no state_max_age_s"
    if not samples:
        return f"{joint}: no position heard"
    latest, latest_at = samples[-1]
    if now - latest_at > max_age_s:
        return f"{joint}: its position is {now - latest_at:.2f} s old, above {max_age_s:g} s"
    since = None
    for index in range(len(samples) - 1, -1, -1):
        if latest_at - samples[index][1] >= max_age_s:
            since = index
            break
    if since is None:
        return f"{joint}: not heard for {max_age_s:g} s yet, so whether it moves is not known"
    spread = max(abs(position - latest) for position, _at in samples[since:])
    if spread > tolerance_m:
        window_s = latest_at - samples[since][1]
        return (
            f"{joint}: moved {spread * 1000:.1f} mm in the last {window_s:.2f} s, more than "
            f"{tolerance_m * 1000:g} mm"
        )
    return None


def recent(
    samples: list[tuple[float, float]], max_age_s: float | None
) -> list[tuple[float, float]]:
    """Return ``samples`` without those `moving` can no longer need, oldest first.

    Kept: the newest sample at least ``max_age_s`` before the latest, and every
    one after it. Anything older says nothing about whether the carriage moves
    now. Without ``max_age_s`` `moving` judges no history at all, so only the
    latest is kept and the list stays bounded (R-17).
    """
    if not samples:
        return samples
    if max_age_s is None:
        return samples[-1:]
    latest_at = samples[-1][1]
    keep_from = 0
    for index in range(len(samples) - 1, -1, -1):
        if latest_at - samples[index][1] >= max_age_s:
            keep_from = index
            break
    return samples[keep_from:]
