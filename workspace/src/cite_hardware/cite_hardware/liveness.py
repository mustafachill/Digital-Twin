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

"""The deadman's decision, with no clock, no graph and no vendor in it.

Every input is an event the node observed — activated, deactivated, a heartbeat
arrived, the timeout elapsed, the heartbeat's publisher went away — and every
output is the state those events leave and whether this event is the one that
TRIPPED it. The node turns a trip into stop calls; this module only says when.

THE RULES, which `DeadmanState.msg` states for a reader of the topic:

- Motion is permitted in HEALTHY and in nothing else.
- AWAITING becomes HEALTHY on the first heartbeat from the deadman's own zone,
  carrying a boundary id, while exactly one heartbeat publisher is on the
  topic. That heartbeat's boundary id is LATCHED: it names the one boundary
  this deadman follows until the next activation. AWAITING never trips: before
  any heartbeat there is no commander whose loss could be detected, and nothing
  is permitted to move anyway.
- HEALTHY becomes TRIPPED when the timeout elapses with no fresh heartbeat,
  when the heartbeat's publisher disappears, when a heartbeat carries a
  boundary id other than the latched one, or when more than one heartbeat
  publisher is on the topic. The last two are a second boundary commanding the
  same side, and which of the two is in charge cannot be told from here.
- TRIPPED is LATCHED. Heartbeats resuming do not clear it; only deactivate,
  which leaves INACTIVE, and a later activate do. An unexplained loss of the
  commander is a fault, and resuming on its own would re-run whatever caused it
  (cross-cutting-safety.md).

A heartbeat counts only when it is FRESH: from this zone, from the latched
boundary, and with a sequence above the last one accepted. A repeated or rewound
sequence is not evidence that the boundary is alive now — it is a duplicate, and
it does not reset the timeout.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_interfaces.msg import DeadmanState

INACTIVE = DeadmanState.STATE_INACTIVE
AWAITING = DeadmanState.STATE_AWAITING
HEALTHY = DeadmanState.STATE_HEALTHY
TRIPPED = DeadmanState.STATE_TRIPPED

STATE_NAMES = {
    INACTIVE: "INACTIVE",
    AWAITING: "AWAITING",
    HEALTHY: "HEALTHY",
    TRIPPED: "TRIPPED",
}


@dataclass(frozen=True)
class Outcome:
    """What one event did: whether it was taken, and whether it tripped."""

    #: The event changed the state, or (for a heartbeat) was fresh and counted.
    accepted: bool
    #: This event is the one that moved HEALTHY to TRIPPED. Exactly one event
    #: per trip carries it, so the stop calls are issued once per trip.
    tripped: bool = False
    #: Why, for the record and the published state's `detail`.
    reason: str = ""


class Liveness:
    """The deadman's state machine. Not thread-safe; the node serialises calls."""

    def __init__(self, zone: str, timeout_s: float) -> None:
        if not zone:
            raise ValueError("a deadman with no zone would accept any boundary's heartbeat")
        if not timeout_s > 0.0:
            raise ValueError(f"a heartbeat timeout of {timeout_s} s is not a timeout")
        self.zone = zone
        self.timeout_s = timeout_s
        self.state = INACTIVE
        self.last_sequence = 0
        #: The boundary this deadman follows, latched from the first heartbeat
        #: after activation; empty until then.
        self.boundary_id = ""
        self.detail = "not active"

    @property
    def permits_motion(self) -> bool:
        return self.state == HEALTHY

    def activate(self) -> Outcome:
        self.state = AWAITING
        self.last_sequence = 0
        self.boundary_id = ""
        self.detail = f"awaiting the first heartbeat of zone {self.zone!r}"
        return Outcome(accepted=True, reason=self.detail)

    def deactivate(self) -> Outcome:
        self.state = INACTIVE
        self.detail = "deactivated"
        return Outcome(accepted=True, reason=self.detail)

    def heartbeat(
        self, zone: str, boundary_id: str, sequence: int, publishers: int
    ) -> Outcome:
        """Take one heartbeat. Accepted only when fresh, and only while it can matter.

        ``publishers`` is how many heartbeat publishers the graph shows at the
        moment this one arrived.
        """
        if self.state in (INACTIVE, TRIPPED):
            return Outcome(
                accepted=False,
                reason=f"heartbeat ignored in {STATE_NAMES[self.state]}",
            )
        if zone != self.zone:
            return Outcome(
                accepted=False,
                reason=f"heartbeat from zone {zone!r}, and this deadman guards {self.zone!r}",
            )
        if publishers > 1:
            return self.second_boundary(
                f"{publishers} heartbeat publishers on the topic, and one boundary has one"
            )
        if not boundary_id:
            return Outcome(
                accepted=False,
                reason="heartbeat without a boundary id; which boundary sent it is unknown",
            )
        if self.boundary_id and boundary_id != self.boundary_id:
            return self.second_boundary(
                f"heartbeat from boundary {boundary_id!r}, and this deadman follows "
                f"{self.boundary_id!r}"
            )
        if sequence <= self.last_sequence:
            return Outcome(
                accepted=False,
                reason=(
                    f"heartbeat sequence {sequence} is not above {self.last_sequence}; "
                    "a duplicate, not evidence that the boundary is alive now"
                ),
            )
        self.last_sequence = sequence
        if self.state == AWAITING:
            self.state = HEALTHY
            self.boundary_id = boundary_id
            self.detail = (
                f"heartbeat {sequence} of boundary {boundary_id!r} received; motion permitted"
            )
        return Outcome(accepted=True, reason=self.detail)

    def second_boundary(self, reason: str) -> Outcome:
        """Record evidence of a second boundary: a trip when HEALTHY, a refusal before."""
        if self.state == HEALTHY:
            return self._trip(reason)
        return Outcome(accepted=False, reason=reason)

    def expired(self) -> Outcome:
        """Record that the timeout elapsed since the last fresh heartbeat."""
        if self.state != HEALTHY:
            return Outcome(accepted=False)
        return self._trip(
            f"no heartbeat within {self.timeout_s:g} s after sequence {self.last_sequence}"
        )

    def publisher_lost(self) -> Outcome:
        """Record that the heartbeat topic has no publisher left."""
        if self.state != HEALTHY:
            return Outcome(accepted=False)
        return self._trip(
            f"the heartbeat publisher disappeared after sequence {self.last_sequence}"
        )

    def _trip(self, reason: str) -> Outcome:
        self.state = TRIPPED
        self.detail = f"TRIPPED: {reason}; latched until deactivate and activate"
        return Outcome(accepted=True, tripped=True, reason=self.detail)
