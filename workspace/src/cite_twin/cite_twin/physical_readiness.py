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

"""Whether a physical side may be commanded yet (ADR-0070 item 6, task item 4).

A physical side announces ready while its arm is still HELD: the deadman keeps
the arm at the vendor's STOP until the twin boundary's first heartbeat, and the
vendor plugin reactivates its controllers only once the deadman has enabled the
arm. So between "the pair is up" and "a command would move both arms" there is
a state the boundary has to wait out, and this module is what decides it is
over. The boundary refuses a mode that would command the side until it is - so
a program's `SetMode(VALIDATED)` is refused, and re-asked, rather than its
first goal reaching an arm that is held, or a track whose joint nobody is
publishing.

Three facts, each read on the physical side's own domain, each fresh within the
plan's `state_max_age_s` on the boundary's steady clock:

1. the deadman permits motion and has enabled the arm
   (`deadman_permits_motion`, the ONE predicate on a `DeadmanState`);
2. the arm trajectory controller is running: its `controller_state`, which it
   publishes only while active;
3. every joint the side publishes - the arm's, the track's, the gripper's - has
   arrived recently, whichever node publishes it.

Pure logic with no node, so it is tested without a graph; the boundary feeds it
arrivals under its own lock.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from cite_interfaces.msg import DeadmanState


def deadman_permits_motion(message: DeadmanState) -> bool:
    """Whether a deadman's state lets this side be commanded.

    THE ONE PREDICATE ON A `DeadmanState` the boundary reads. HEALTHY says
    motion is PERMITTED; `arm_enabled` says the deadman's own enable
    (`set_state(0)`) was acknowledged in this HEALTHY period. Both are required
    (S-03): HEALTHY alone is also the moment between the first heartbeat and an
    enable that may still fail, when a goal would reach an arm held at STOP.
    """
    return message.state == DeadmanState.STATE_HEALTHY and message.arm_enabled


@dataclass
class PhysicalSideWatch:
    """What the boundary has heard from one physical arm, with steady-clock arrivals."""

    asset: str
    joints: tuple[str, ...]
    max_age_s: float
    deadman: DeadmanState | None = None
    deadman_at: float | None = None
    controller_at: float | None = None
    joint_at: dict[str, float] = field(default_factory=dict)

    def heard_deadman(self, message: DeadmanState, now: float) -> None:
        self.deadman = message
        self.deadman_at = now

    def heard_controller(self, now: float) -> None:
        self.controller_at = now

    def heard_joints(self, names: Iterable[str], now: float) -> None:
        for name in names:
            self.joint_at[name] = now

    def unready(self, now: float) -> str | None:
        """Say why this side may not be commanded yet, or `None` if it may."""
        if self.deadman is None or self.deadman_at is None:
            return f"{self.asset}: no deadman state heard"
        if now - self.deadman_at > self.max_age_s:
            return f"{self.asset}: the deadman's last state is {now - self.deadman_at:.2f} s old"
        if not deadman_permits_motion(self.deadman):
            if self.deadman.state == DeadmanState.STATE_HEALTHY:
                return f"{self.asset}: the deadman has not yet enabled the arm"
            return (
                f"{self.asset}: the deadman holds the arm "
                f"(state {self.deadman.state}: {self.deadman.detail})"
            )
        if self.controller_at is None or now - self.controller_at > self.max_age_s:
            return f"{self.asset}: the arm trajectory controller is not running"
        stale = sorted(
            name
            for name in self.joints
            if name not in self.joint_at or now - self.joint_at[name] > self.max_age_s
        )
        if stale:
            return f"{self.asset}: no fresh state for {', '.join(stale)}"
        return None


def unready(watches: Iterable[PhysicalSideWatch], now: float) -> str | None:
    """Return every reason a watched physical arm may not be commanded, or `None`."""
    reasons = [reason for watch in watches if (reason := watch.unready(now)) is not None]
    return "; ".join(reasons) if reasons else None
