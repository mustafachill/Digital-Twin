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

"""The deadman's answer, as the relays that move an asset hold it.

A relay asks one question before it forwards a command: *does the deadman
permit motion right now?* The answer is yes only when the latest
`DeadmanState` received says HEALTHY, arrived within `max_age_s` on this
process's steady clock, and exactly one deadman is publishing. Every other case
is no, including the ones that are easy to get wrong:

- **Nothing received yet.** A relay that starts before the deadman, or whose
  deadman never started, holds no state and refuses.
- **The deadman died or hung.** Its last message said HEALTHY, and the relay's
  own copy would outlive it. The deadman republishes its state on every tick,
  so a copy older than `max_age_s` closes the gate, and so does the publisher
  disappearing, observed as the subscription's `matched` event and as the
  graph's publisher count; any one suffices.
- **Two deadmen.** A second publisher on the topic means two answers to one
  question, and which one is current cannot be told; refused.

When the gate closes on a relay — for any of these reasons or because the
deadman said so — the relay is told (``on_closed``) at the latest on its next
``check()``, so it can stop what it was doing rather than discover the closure
at its next command.

**This gates the relays only.** The arm's own trajectory controller is not
behind this gate: the deadman holds the arm through the vendor's own state
(`cite_hardware.deadman`).
"""

from __future__ import annotations

from collections.abc import Callable
import threading

from cite_hardware.liveness import HEALTHY, STATE_NAMES
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
from rclpy.callback_groups import CallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.event_handler import SubscriptionEventCallbacks
from rclpy.node import Node


class DeadmanGate:
    """Subscribe to a deadman's state and answer whether motion is permitted."""

    def __init__(
        self,
        node: Node,
        topic: str,
        max_age_s: float,
        callback_group: CallbackGroup,
        on_closed: Callable[[str], None],
    ) -> None:
        if not max_age_s > 0.0:
            raise ValueError(f"a deadman state age bound of {max_age_s} s is not a bound")
        self._node = node
        self._topic = topic
        self._max_age_ns = int(max_age_s * 1e9)
        self._on_closed = on_closed
        self._lock = threading.Lock()
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self._state: DeadmanState | None = None
        self._received_ns = 0
        #: Whether the gate was open at the last look, so a closure is
        #: reported once.
        self._was_open = False
        # LATCHED, which is the deadman's own publisher profile: a relay that
        # starts after the deadman's last transition still learns it.
        self.subscription = node.create_subscription(
            DeadmanState,
            topic,
            self._on_state,
            LATCHED,
            callback_group=callback_group,
            event_callbacks=SubscriptionEventCallbacks(matched=self._on_matched),
        )

    def permits_motion(self) -> bool:
        """Whether a command may be forwarded now."""
        return not self._why_closed()

    def why_closed(self) -> str:
        """Return a sentence for a refusal, naming what the gate last knew."""
        return self._why_closed() or "the gate is open"

    def check(self) -> None:
        """Report a closure that no message announced: age, or the publisher count."""
        self._update()

    def destroy(self) -> None:
        self._node.destroy_subscription(self.subscription)

    def _why_closed(self) -> str:
        with self._lock:
            state = self._state
            received_ns = self._received_ns
        if state is None:
            return f"no deadman state received on {self._topic}"
        publishers = self._node.count_publishers(self._topic)
        if publishers == 0:
            return f"no deadman is publishing on {self._topic}"
        if publishers > 1:
            return f"{publishers} deadmen are publishing on {self._topic}; one is expected"
        age_ns = self._steady.now().nanoseconds - received_ns
        if age_ns > self._max_age_ns:
            return (
                f"the deadman state on {self._topic} is {age_ns * 1e-9:.3f} s old, "
                f"above the bound of {self._max_age_ns * 1e-9:g} s"
            )
        if state.state != HEALTHY:
            return (
                f"the deadman reports {STATE_NAMES.get(state.state, state.state)}: "
                f"{state.detail}"
            )
        return ""

    def _update(self) -> None:
        reason = self._why_closed()
        with self._lock:
            closing = self._was_open and bool(reason)
            self._was_open = not reason
        if closing:
            self._on_closed(reason)

    def _on_state(self, message: DeadmanState) -> None:
        with self._lock:
            previous = self._state
            self._state = message
            self._received_ns = self._steady.now().nanoseconds
        # Said on a change only: the deadman republishes on every tick, and
        # this is the record of WHEN this relay learned that it may or may not
        # move the asset.
        if previous is None or (previous.state, previous.detail) != (
            message.state,
            message.detail,
        ):
            self._node.get_logger().info(
                f"deadman state {STATE_NAMES.get(message.state, message.state)} received: "
                f"{message.detail}"
            )
        self._update()

    def _on_matched(self, status) -> None:
        if status.current_count > 0:
            return
        with self._lock:
            self._state = None
        self._update()
