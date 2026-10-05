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

"""How each node in this package runs as a process.

**NOT through `cite_runtime`'s init/spin/shutdown**, by that module's own
adoption rule: it absorbs SIGINT, and it says in terms that the pattern is for
a process that commands no actuator. Every node here commands one. So these
keep rclpy's ordinary signal handling — an operator's Ctrl-C reaches them — and
import from `cite_runtime` only the one constant that module documents as the
single statement of which exceptions mean "the context went away", exactly as
the twin boundary does.

What makes that safe is a property of the nodes rather than of this module: no
callback in this package blocks. Every vendor call is asynchronous and every
wait is a future some other callback completes, so a shutdown is never queued
behind a call to a machine that is not answering.
"""

from __future__ import annotations

from collections.abc import Callable

from cite_runtime.runtime import caused_by_shutdown, SHUTDOWN_EXCEPTIONS
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node


def run(factory: Callable[[], Node]) -> int:
    """Initialise rclpy, spin the node ``factory`` builds, and shut down."""
    rclpy.init()
    node = factory()
    # Multi-threaded, because a vendor response, a command, a cancel and a
    # timer may all be ready at once and none of them may wait on another.
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except SHUTDOWN_EXCEPTIONS as error:
        if not caused_by_shutdown(error, node):
            raise
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0
