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

"""One run's hold on the twin's mode (`HoldMode.srv`; ADR-0072, safety finding S-01).

A client checks the twin's mode and then sends a command; the boundary routes
that command by the mode in force when it DISPATCHES. Between the two another
client may switch the twin, and a SIM run's next command would then reach the
physical arm. A client-side check cannot close that window, because the window
is between the client and the boundary. So the boundary holds the mode for the
run: while a hold exists, no transition to another mode is taken unless the
holder asks for it, and a transition the holder takes carries the hold along.

**Liveness by the graph, bounded.** The hold names the holder's ROS node. The
boundary reports which node names its plant-side graph holds, at its heartbeat
period, and a hold whose node has been absent for longer than
`UNSEEN_CEILING_S` lapses - a dead console or a closed terminal never locks the
twin for good. A lapse changes no mode (`lapse_if_gone`).

Pure logic with no node, as `cite_twin.mode` is: the boundary calls it under
its own lock and owns every clock reading it is handed.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from cite_interfaces.msg import ResultCode, TwinMode
from cite_interfaces.srv import HoldMode

#: How long a hold's node may be absent from the plant's ROS graph before the
#: hold lapses, in seconds of the boundary's steady clock.
#:
#: A hang detector and not a schedule: nothing is sequenced on it, and a live
#: holder is never affected by it. It bounds how long a client that died keeps
#: the twin's mode fixed. It is generous on purpose, because the graph a node
#: joins is learnt by discovery: a holder that has just called this service may
#: not be listed yet, and a hold must never lapse under a client that is alive.
#: A node that crashed leaves the graph only when its middleware lease expires,
#: which comes on top of this.
UNSEEN_CEILING_S = 10.0


@dataclass
class Hold:
    """Who holds the twin's mode, which mode, and when its node was last seen."""

    holder: str
    node: str
    mode: int
    #: The boundary's steady clock when the node was last on the graph, or
    #: when the hold was taken, whichever is later.
    seen_at: float


@dataclass(frozen=True)
class Answer:
    """What one `HoldMode` call did, in the fields its response carries."""

    accepted: bool
    code: int
    detail: str


class ModeHold:
    """The one hold on the twin's mode, if any. Not thread-safe: the caller locks."""

    def __init__(self) -> None:
        self._hold: Hold | None = None

    @property
    def holder(self) -> str:
        """Return the holder's id, empty when nobody holds the mode."""
        return "" if self._hold is None else self._hold.holder

    @property
    def held(self) -> Hold | None:
        return self._hold

    def request(
        self, action: int, holder: str, node: str, mode: int, current_mode: int, now: float
    ) -> Answer:
        """Decide one `HoldMode` call against ``current_mode``, the mode in force."""
        if not holder:
            return _refused("HoldMode.holder is empty: a hold must name the run that holds it")
        if action == HoldMode.Request.ACQUIRE:
            return self._acquire(holder, node, mode, current_mode, now)
        if action == HoldMode.Request.RELEASE:
            return self._release(holder)
        return _refused(
            f"HoldMode.action is {action}, not ACQUIRE ({HoldMode.Request.ACQUIRE}) or "
            f"RELEASE ({HoldMode.Request.RELEASE})"
        )

    def _acquire(
        self, holder: str, node: str, mode: int, current_mode: int, now: float
    ) -> Answer:
        if not node:
            return _refused(
                "HoldMode.node is empty: a hold names the holder's node, so that it lapses "
                "when that node leaves the graph"
            )
        if self._hold is not None and self._hold.holder != holder:
            return _refused(
                f"the twin's mode is held by another run ({self._hold.holder}, node "
                f"{self._hold.node}); it is released by that run, or lapses once its node "
                "leaves the graph"
            )
        if mode != current_mode:
            return _refused(
                f"the mode in force is {current_mode}, not the {mode} this run asked to hold: "
                "another client changed it since this run looked, so nothing is held"
            )
        self._hold = Hold(holder=holder, node=node, mode=mode, seen_at=now)
        return Answer(True, ResultCode.SUCCESS, f"mode {mode} held by {holder} ({node})")

    def _release(self, holder: str) -> Answer:
        if self._hold is None:
            return Answer(True, ResultCode.SUCCESS, "nothing was held")
        if self._hold.holder != holder:
            return _refused(
                f"the hold is {self._hold.holder}'s, not {holder}'s; only the holder releases it"
            )
        self._hold = None
        return Answer(True, ResultCode.SUCCESS, f"released by {holder}")

    def refusal(self, requested_mode: int, holder: str, current_mode: int) -> str | None:
        """Say why a `SetMode` into ``requested_mode`` is refused by the hold, or None.

        A request for the mode in force changes nothing and is never refused
        here, nor is one into SIM (S2-05): SIM commands the plant alone, so
        taking the twin there is the safe direction and no hold may stand in
        its way - the holder's own run then stops on the mode it did not ask
        for (R-05). Any other is refused unless it carries the holder's id.
        """
        hold = self._hold
        if (
            hold is None
            or requested_mode == current_mode
            or requested_mode == TwinMode.MODE_SIM
            or holder == hold.holder
        ):
            return None
        return (
            f"the twin's mode is held by a run in progress ({hold.holder}, node {hold.node}), "
            f"so only that run may change it; this request names "
            f"{holder or 'no holder'}. Wait for the run to end, or stop it"
        )

    def followed(self, holder: str, mode: int) -> None:
        """Carry the hold to ``mode`` after a transition its holder made, or into SIM.

        A transition into SIM is never refused by the hold (`refusal`), whoever
        asks for it, and the hold stays with its holder on the mode now in force.
        """
        if self._hold is not None and (
            holder == self._hold.holder or mode == TwinMode.MODE_SIM
        ):
            self._hold.mode = mode

    def lapse_if_gone(self, nodes: Collection[str], now: float) -> str | None:
        """Lapse the hold if its node is not on the graph and has not been for the ceiling.

        ``nodes`` is every fully qualified node name the plant's graph holds
        now. Returns what lapsed, for the log, or None. The mode is not
        touched: a lapse is the end of a hold, never a transition.
        """
        hold = self._hold
        if hold is None:
            return None
        if hold.node in nodes:
            hold.seen_at = now
            return None
        if now - hold.seen_at <= UNSEEN_CEILING_S:
            return None
        self._hold = None
        return (
            f"the hold of {hold.holder} lapsed: its node {hold.node} has not been on the graph "
            f"for {UNSEEN_CEILING_S:g} s. The mode is left as it was; any client may change it "
            "now, under every gate a transition has"
        )


def _refused(detail: str) -> Answer:
    return Answer(False, ResultCode.PRECONDITION_FAILED, detail)


def node_names(names_and_namespaces) -> set[str]:
    """Return fully qualified node names from `get_node_names_and_namespaces()`."""
    return {
        f"{namespace.rstrip('/')}/{name}" for name, namespace in names_and_namespaces
    }
