#!/usr/bin/env python3
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

"""A physical side's deadman and arm controller, faked: two topics and nothing behind them.

**Test-only, and it is not a deadman.** It publishes, on its own domain, what
the twin boundary reads of a physical arm (ADR-0070 item 6): a latched
`DeadmanState` on the plan's deadman state topic and, while the arm is enabled,
the arm controller's `controller_state`. The state is read from a file the test
writes - `held` or `healthy` - on every publication, so a test can release the
arm (ADR-0076) without a service. It stops nothing and enables nothing.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from cite_interfaces.msg import DeadmanState
from cite_interfaces.qos import LATCHED, STATE
from control_msgs.msg import JointTrajectoryControllerState
import rclpy
from rclpy.node import Node

#: How often both topics are published, in seconds. A publication rate, well
#: inside the plan's `state_max_age_s`; nothing is sequenced on it.
PERIOD_S = 0.05


class FakeDeadman(Node):
    def __init__(self, asset: str, state_topic: str, controller_topic: str, control: Path):
        super().__init__("fake_deadman")
        self._asset = asset
        self._control = control
        self._state = self.create_publisher(DeadmanState, state_topic, LATCHED)
        self._controller = self.create_publisher(
            JointTrajectoryControllerState, controller_topic, STATE
        )
        self._said = ""
        self.create_timer(PERIOD_S, self._publish)

    def _publish(self) -> None:
        try:
            word = self._control.read_text().strip()
        except OSError:
            word = "held"
        healthy = word == "healthy"
        message = DeadmanState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.asset_id = self._asset
        message.state = DeadmanState.STATE_HEALTHY if healthy else DeadmanState.STATE_HELD
        message.arm_enabled = healthy
        message.detail = "fake"
        self._state.publish(message)
        if healthy:
            self._controller.publish(JointTrajectoryControllerState())
        if word != self._said:
            self._said = word
            print(f"deadman: {word or 'held'}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", required=True)
    parser.add_argument("--state-topic", required=True)
    parser.add_argument("--controller-topic", required=True)
    parser.add_argument("--control", required=True)
    arguments, _ = parser.parse_known_args()
    rclpy.init()
    node = FakeDeadman(
        arguments.asset,
        arguments.state_topic,
        arguments.controller_topic,
        Path(arguments.control),
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
