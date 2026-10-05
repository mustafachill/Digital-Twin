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
commands. Pure logic with no node, so it is tested without a graph; the
boundary feeds it what it has heard, under its own lock.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def arrival(
    sides: Iterable[str],
    heard: Mapping[str, tuple[float, float]],
    physical: Iterable[str],
    target_m: float,
    tolerance_m: float,
    now: float,
    max_age_s: float | None,
) -> str | None:
    """Return why the track has not arrived on every side, or `None` when it has.

    ``heard`` is each side's last track position and its steady-clock arrival.
    A side in ``physical`` counts only with a position younger than
    ``max_age_s``: a carriage read too long ago may be anywhere since. A
    simulated side's position is its simulator's, held by its own controller.
    """
    stale_bound = set(physical)
    reasons = []
    for side in sides:
        if side not in heard:
            reasons.append(f"{side}: no track position heard")
            continue
        position, at = heard[side]
        if side in stale_bound:
            if max_age_s is None:
                reasons.append(f"{side}: physical, and the plan states no state_max_age_s")
                continue
            if now - at > max_age_s:
                reasons.append(
                    f"{side}: its track position is {now - at:.2f} s old, above {max_age_s:g} s"
                )
                continue
        if abs(position - target_m) > tolerance_m:
            reasons.append(
                f"{side}: stands at {position * 1000:.1f} mm, not within "
                f"{tolerance_m * 1000:g} mm of {target_m * 1000:.1f} mm"
            )
    return "; ".join(reasons) if reasons else None
