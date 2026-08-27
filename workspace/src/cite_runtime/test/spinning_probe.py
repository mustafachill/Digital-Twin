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

"""The smallest node that can lose the race `cite_runtime.runtime` closes.

Two idioms, one node, so that the test can compare them.

  `runtime`  what every long-lived Python node in this repository uses.
  `default`  what they all used before it existed, reproduced verbatim.

The `default` idiom is not dead code and is not here for history: it is the
NEGATIVE CONTROL. A tripwire that has quietly stopped placing the signal where
it claims to would leave the `runtime` assertion passing while proving nothing,
and the only thing that can tell those two states apart is watching the same
tripwire still break the idiom it is supposed to break.

This package owns the probe rather than importing a node from a package that
has one, because `cite_runtime`'s admission test forbids depending on anything
in-project — and a test dependency is still a dependency. What is under test
here is the mechanism, not any node that uses it.

`use_sim_time` is set on the node itself rather than passed as a ROS argument:
it is the whole point of the probe. It is what makes rclpy attach its internal
`/clock` subscription, and that subscription is the message conversion the
tripwire fires inside.
"""

from __future__ import annotations

import sys

from cite_runtime import runtime
import rclpy
from rclpy.parameter import Parameter

NODE_NAME = "shutdown_probe"

SIM_TIME = [Parameter("use_sim_time", Parameter.Type.BOOL, True)]


def _spin_through_runtime() -> None:
    """Spin the way this repository's nodes do."""
    runtime.init()
    node = rclpy.create_node(NODE_NAME, parameter_overrides=SIM_TIME)
    try:
        runtime.spin(node)
    finally:
        runtime.shutdown(node)


def _spin_the_default_way() -> None:
    """Spin the way they all did before `runtime` existed.

    Copied from `frame_server.main` as it stood at f16ea98. Do not tidy it: its
    value is that it is exactly the idiom the tripwire is claimed to break.
    """
    rclpy.init()
    node = rclpy.create_node(NODE_NAME, parameter_overrides=SIM_TIME)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


IDIOMS = {"runtime": _spin_through_runtime, "default": _spin_the_default_way}


def main() -> None:
    """Spin with the idiom named by the first argument, defaulting to `runtime`."""
    idiom = sys.argv[1] if len(sys.argv) > 1 else "runtime"
    IDIOMS[idiom]()


if __name__ == "__main__":
    main()
