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

"""Whether every side stands at a set of joint positions (`JointsAt`, ADR-0070).

The fixed program measures the program's start before its first cycle: every
arm joint at the program's first pose, on every side. It reads its own domain's
joint states only, which through the twin are the plant's, so the boundary,
which reads every side's, answers for all of them. Pure logic with no node, so
it is tested without a graph; the boundary feeds it what it has heard, under its
own lock. Units are the joints' own: nothing here assumes radians or metres.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import math

from cite_interfaces.srv import JointsAt


def _unheard(
    side: str,
    joint: str,
    heard: tuple[float, float] | None,
    physical: bool,
    now: float,
    max_age_s: float | None,
) -> str | None:
    """Why ``side``'s ``joint`` cannot be counted, or `None` when it can.

    The rule `track_arrival` applies to a carriage: a physical side's position
    counts only while younger than ``max_age_s``; a simulated side's is its
    simulator's.
    """
    if heard is None:
        return f"{side}: no {joint} position heard"
    if not physical:
        return None
    if max_age_s is None:
        return f"{side}: physical, and the plan states no state_max_age_s"
    if now - heard[1] > max_age_s:
        return f"{side}: its {joint} position is {now - heard[1]:.2f} s old, above {max_age_s:g} s"
    return None


def joints_at(
    sides: Iterable[str],
    heard: Mapping[tuple[str, str], tuple[float, float]],
    physical: Iterable[str],
    joints: Sequence[str],
    targets: Sequence[float],
    tolerance: float,
    now: float,
    max_age_s: float | None,
) -> tuple[int, str | None]:
    """Return the `JointsAt` reason for ``sides``, and why, or `(AT, None)`.

    ``heard`` is each (side, joint)'s last position and its steady-clock
    arrival. AWAY outranks UNHEARD: a joint heard standing elsewhere does not
    clear by itself, a position not heard yet does.
    """
    if not joints or len(joints) != len(targets):
        return JointsAt.Response.MALFORMED, (
            f"{len(joints)} joint(s) and {len(targets)} position(s); one position per "
            "joint, and at least one joint"
        )
    if not math.isfinite(tolerance) or tolerance < 0.0:
        return JointsAt.Response.MALFORMED, f"a tolerance of {tolerance}"
    stale_bound = set(physical)
    away = []
    unheard = []
    for side in sides:
        for joint, target in zip(joints, targets):
            position = heard.get((side, joint))
            reason = _unheard(side, joint, position, side in stale_bound, now, max_age_s)
            if reason is not None:
                unheard.append(reason)
            elif abs(position[0] - target) > tolerance:
                away.append(
                    f"{side}: {joint} stands at {position[0]:.4f}, not within "
                    f"{tolerance:g} of {target:.4f}"
                )
    if away:
        return JointsAt.Response.AWAY, "; ".join(away + unheard)
    if unheard:
        return JointsAt.Response.UNHEARD, "; ".join(unheard)
    return JointsAt.Response.AT, None
