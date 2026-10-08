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

"""The vendor's `set_state` and `set_mode` in a process of their own. Test-only.

`vendor_fakes.FakeArmState` lives in the test's own node, and a service there
cannot be withdrawn mid-test (see `vendor_fakes.FakeTrack`). A vendor driver
that goes away and comes back — `ros2_control_node` restarting — is a PROCESS
that ends and starts again, so this is one: started and ended with a signal by
the test, it serves the two services under ``argv[1]`` and prints every call it
receives as ``call <service> <value>`` on its own line.
"""

from __future__ import annotations

import os
import sys

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vendor_fakes import FakeArmState  # noqa: E402


class _Host:
    """What `FakeArmState` needs of a harness: a node and a callback group."""

    def __init__(self, node: Node) -> None:
        self.node = node
        self.group = ReentrantCallbackGroup()


def main() -> int:
    namespace = sys.argv[1]
    rclpy.init()
    node = Node("fake_vendor")
    FakeArmState(
        _Host(node),
        namespace,
        on_call=lambda service, value: print(f"call {service} {value}", flush=True),
    )
    print("serving", flush=True)
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (ExternalShutdownException, KeyboardInterrupt):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
