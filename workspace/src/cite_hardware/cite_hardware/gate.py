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
`DeadmanState` received says HEALTHY **and** a deadman is still publishing.
Every other case is no, including the ones that are easy to get wrong:

- **Nothing received yet.** A relay that starts before the deadman, or whose
  deadman never started, holds no state and refuses.
- **The deadman died.** Its last message said HEALTHY, and a latched message
  outlives nothing — transient-local delivery comes from a live writer — but
  the relay's own copy would. So the publisher disappearing closes the gate,
  observed both as the subscription's `matched` event and as the graph's
  publisher count at the moment of the question; either suffices.

When the gate closes on a relay holding work in flight, the relay is told
(``on_closed``), so it can abort what it was doing rather than discover the
closure at its next command.
"""

from __future__ import annotations

from collections.abc import Callable
import threading

from cite_hardware.liveness import HEALTHY, STATE_NAMES
from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED
from rclpy.callback_groups import CallbackGroup
from rclpy.event_handler import SubscriptionEventCallbacks
from rclpy.node import Node


class DeadmanGate:
    """Subscribe to a deadman's state and answer whether motion is permitted."""

    def __init__(
        self,
        node: Node,
        topic: str,
        callback_group: CallbackGroup,
        on_closed: Callable[[str], None],
    ) -> None:
        self._node = node
        self._topic = topic
        self._on_closed = on_closed
        self._lock = threading.Lock()
        self._state: DeadmanState | None = None
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
        with self._lock:
            state = self._state
        return (
            state is not None
            and state.state == HEALTHY
            and self._node.count_publishers(self._topic) > 0
        )

    def why_closed(self) -> str:
        """Return a sentence for a refusal, naming what the gate last knew."""
        with self._lock:
            state = self._state
        if state is None:
            return f"no deadman state received on {self._topic}"
        if self._node.count_publishers(self._topic) == 0:
            return f"no deadman is publishing on {self._topic}"
        return (
            f"the deadman reports {STATE_NAMES.get(state.state, state.state)}: "
            f"{state.detail}"
        )

    def destroy(self) -> None:
        self._node.destroy_subscription(self.subscription)

    def _on_state(self, message: DeadmanState) -> None:
        with self._lock:
            was_open = self._state is not None and self._state.state == HEALTHY
            self._state = message
        # Said on every receipt. The deadman publishes on transitions only, so
        # this is a handful of lines per run, and it is the record of WHEN this
        # relay learned that it may or may not move the asset.
        self._node.get_logger().info(
            f"deadman state {STATE_NAMES.get(message.state, message.state)} received: "
            f"{message.detail}"
        )
        if was_open and message.state != HEALTHY:
            self._on_closed(
                f"the deadman reports {STATE_NAMES.get(message.state, message.state)}: "
                f"{message.detail}"
            )

    def _on_matched(self, status) -> None:
        if status.current_count > 0:
            return
        with self._lock:
            was_open = self._state is not None and self._state.state == HEALTHY
            self._state = None
        if was_open:
            self._on_closed(f"the deadman's publisher on {self._topic} disappeared")
