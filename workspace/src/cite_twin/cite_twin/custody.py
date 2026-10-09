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

"""Whether each side's arm holds a part, as `Holding.srv` answers it (ADR-0072, R-01).

The boundary reads each side's latched `RobotState` on that side's own domain -
the one component with endpoints in both (ADR-0044 clause 3) - and answers a
verdict per side, never the message (ADR-0050 decision 1b). Pure logic with no
node, so it is tested without a graph; the boundary feeds it what it heard,
under its own lock.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class SideCustody:
    """One side's answer: heard from every arm, holding anything, and what."""

    side: str
    heard: bool
    holding: bool
    detail: str


def holding(
    sides: Iterable[str],
    assets: Iterable[str],
    custody: Mapping[tuple[str, str], tuple[bool, str]],
) -> list[SideCustody]:
    """Answer for each of ``sides``, from ``custody``: (side, asset) -> (holding, held id).

    A side is heard only when every one of ``assets`` has said something on it;
    one that has not is unheard, never assumed empty. A side that does not run
    has nothing in ``custody`` and is unheard too.
    """
    assets = tuple(assets)
    answers = []
    for side in sides:
        unheard = [asset for asset in assets if (side, asset) not in custody]
        held = [
            f"{asset} holds {custody[(side, asset)][1] or 'a part'}"
            for asset in assets
            if (side, asset) in custody and custody[(side, asset)][0]
        ]
        said = held + [f"no RobotState heard from {asset}" for asset in unheard]
        answers.append(
            SideCustody(
                side=side,
                heard=not unheard and bool(assets),
                holding=bool(held),
                detail="; ".join(said) if assets else "no arm on this side states custody",
            )
        )
    return answers
