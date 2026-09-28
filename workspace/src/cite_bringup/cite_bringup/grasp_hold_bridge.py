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

"""Tell the simulated cell what this arm is holding (ADR-0065).

**A SIMULATION-ONLY NODE, AND THAT IS A STRUCTURAL CLAIM RATHER THAN A HABIT.**
It subscribes to one arm's `RobotState` — which L3 publishes identically on both
backends, because a physical arm saying what it holds is wanted for its own sake
— and turns each change of `gripper_holding` into an attach or a detach on that
arm's grasp-hold plugin, over the Gazebo transport. The plugin exists only in the
generated world; on hardware there is nothing on the other end of those topics
and nothing that needs one, because a real gripper holds what it has clamped.
`simulation.launch.py` is the only place in this repository that starts it, and
`test/test_the_bridge_is_simulation_only.py` fails if that stops being true.

**Why the arrow points this way.** The plugin used to decide for itself that a
grasp had begun and ended, from the drive joint's own position and a part-width
window — a re-derivation of `cite_skills::gripper_is_holding`, which is the one
place this project decided that question (ADR-0052). Two thresholds in two
packages answering one question is what P1 forbids, and tuning them refuted two
decisions in a week (ADR-0062, ADR-0064). The cell knows; the simulation is told.

**What it publishes is an EMPTY message**, because that is the shape Gazebo
Harmonic's own `DetachableJoint` takes on its `<attach_topic>` and
`<detach_topic>`. The plugin uses that system's component; it takes that system's
trigger.

**Both names come from the generated bring-up plan and neither is built here.**
`generate/world.py` emits the same two into the plugin's own declaration from the
same `ids.interface` calls, so what this publishes to and what the plugin listens
on cannot drift (P1, CLAUDE.md §8). The ROS side needs no name at all: this node
runs in its arm's own namespace, exactly as that arm's skill server and
planning-scene loader do, so `state` resolves against the namespace the server
published into.

**The partition comes from `cite_bringup.gz` and from nowhere else.** That module
is the one door for the environment a Gazebo-transport process needs (ADR-0042),
and a process that does not carry the partition discovers a transport that is not
there — silently, because nothing reports it. The partition is set on this node's
own `NodeOptions` rather than read from the shell, the same way
`cite_bringup.gz.ModelPoses` sets it.

**A message can be lost here, and the plugin could not miss one before.** That is
the cost ADR-0065 takes knowingly. Two things bound it and neither removes it:
the state topic is LATCHED, so this node is told the present value when it starts
rather than waiting for the next change; and a publication to a topic with no
connections is logged, so a message sent into an empty partition is visible
instead of silent. It does not retry, because a retry answers a different
question — whether the message was *received* — which nothing here can observe.
"""

from __future__ import annotations

import os
import sys

from cite_bringup.gz import gz_environment, plan_for
from cite_bringup.plan import GZ_PARTITION_ENV, PLANT_SIDE
from cite_interfaces.msg import RobotState
from cite_interfaces.qos import latched
from cite_runtime import runtime
import rclpy
from rclpy.node import Node


class BridgeError(Exception):
    """The bring-up plan did not deliver something this node may not invent."""


def _stop_this_directory_shadowing_gz() -> None:
    """Drop this file's own directory from `sys.path`, before `gz` is imported.

    THE DEFECT THIS EXISTS FOR, AND IT STOPPED THE WHOLE CELL. This file is
    installed as a PROGRAM and `./scripts/build` uses `--symlink-install`, so the
    installed path is a symlink back into `src/cite_bringup/cite_bringup/`. Python
    puts the RESOLVED script directory at `sys.path[0]`, and that directory holds
    `gz.py` — this package's own Gazebo-environment door. It shadows the `gz`
    namespace package that ships `gz.transport13`, and the import dies with
    `ModuleNotFoundError: No module named 'gz.transport13'; 'gz' is not a package`.

    Found by `./scripts/scenario pick_and_place --zone cell_b`, which is the only
    thing that runs this file the way the cell does: every unit test IMPORTS the
    module, where `cite_bringup` is reached through `PYTHONPATH` and its directory
    is never `sys.path[0]`. `readiness_witness.py` and `lifecycle_driver.py` sit in
    the same directory and never noticed, because neither imports `gz`.

    Removing the entry rather than renaming `gz.py`: that module is the one door
    ADR-0042 designates for a Gazebo-transport environment, it is named in this
    package's README and in the scenario guard, and moving it to dodge a path
    collision would cost more than it buys. Nothing here needs that entry —
    `cite_bringup` itself is on `PYTHONPATH`.
    """
    ours = os.path.dirname(os.path.realpath(__file__))
    sys.path[:] = [
        entry for entry in sys.path if os.path.realpath(entry or ".") != ours
    ]


class Custody:
    """Which topic, if any, a reported custody means telling the simulation on.

    Kept free of ROS and of gz-transport so that the rule can be tested for what
    it is — an edge detector over one boolean — without a node, a simulator or a
    partition. The same reason `cite_skills`' own decisions live in headers.

    ON CHANGE AND NOT ON EVERY MESSAGE. The state topic is latched and republished
    whenever custody moves, so a message that says what the last one said means
    the arm changed something else. Publishing an attach on it would tell a plugin
    already holding a part to take one, which it declines, and would make a log
    that shows an attach per goal rather than per grasp.

    THE FIRST MESSAGE ACTS WHICHEVER WAY IT READS, which is why the initial state
    is `None` and not `False`. An arm that comes up already holding something —
    custody latched unknown across a restart, say — has to be attached, and
    starting at `False` would silently make that first message a no-op.
    """

    def __init__(self, attach_topic: str, detach_topic: str) -> None:
        self._attach_topic = attach_topic
        self._detach_topic = detach_topic
        self._holding: bool | None = None

    def topic_for(self, holding: bool) -> str | None:
        """Return the topic to publish on, or None when nothing has changed."""
        if holding == self._holding:
            return None
        self._holding = holding
        return self._attach_topic if holding else self._detach_topic


class GraspHoldBridge(Node):
    """One arm's custody, on that arm's grasp-hold topics."""

    def __init__(self) -> None:
        super().__init__("grasp_hold_bridge")
        # Every one of these is supplied by the generated bring-up plan through
        # the launch file. The defaults are empty so that a plan which failed to
        # deliver one is a refusal with a sentence rather than a bridge
        # publishing into a topic nothing listens on.
        self.declare_parameter("zone", "")
        self.declare_parameter("side", PLANT_SIDE)
        self.declare_parameter("attach_topic", "")
        self.declare_parameter("detach_topic", "")

        # Imported here and not at module scope, the same way `cite_bringup.gz`
        # defers it: importing this module must not cost a transport node in a
        # process — a test — that has no use for one.
        #
        # ABOVE THE PARAMETER CHECK, DELIBERATELY. It is the statement the call
        # above exists for, and a refusal that ran first would make the cheapest
        # test of that call — start the program with no parameters and require the
        # refusal rather than a traceback — pass without ever reaching the import.
        _stop_this_directory_shadowing_gz()
        from gz.transport13 import AdvertiseMessageOptions, Node as GzNode, NodeOptions
        from gz.msgs10.empty_pb2 import Empty

        zone = self.get_parameter("zone").value
        side = self.get_parameter("side").value
        self._attach_topic = self.get_parameter("attach_topic").value
        self._detach_topic = self.get_parameter("detach_topic").value
        for name, value in (
            ("zone", zone),
            ("attach_topic", self._attach_topic),
            ("detach_topic", self._detach_topic),
        ):
            if not value:
                raise BridgeError(
                    f"parameter {name!r} is empty. Both topics are generated per arm "
                    "from the L0 asset id and carried by the bring-up plan; an empty "
                    "one means the plan did not deliver it, and building the name here "
                    "would put it in a second place."
                )

        options = NodeOptions()
        options.partition = gz_environment(plan_for(zone), side)[GZ_PARTITION_ENV]
        self._gz = GzNode(options)
        self._empty = Empty
        #: One publisher per topic, keyed by the topic itself, so that the rule
        #: below can decide in names and this class only has to look one up.
        self._publishers = {
            topic: self._gz.advertise(topic, Empty, AdvertiseMessageOptions())
            for topic in (self._attach_topic, self._detach_topic)
        }
        self._custody = Custody(self._attach_topic, self._detach_topic)

        # LATCHED to match the publisher exactly (docs/interfaces/qos-profiles.md).
        # A subscriber whose durability is stricter than the publisher's connects
        # SILENTLY and delivers nothing, and this node starts after the skill
        # servers do, so volatile here would mean missing the value that is
        # already current.
        self._state = self.create_subscription(
            RobotState, "state", self._on_state, latched()
        )
        self.get_logger().info(
            f"bridging custody onto {self._attach_topic} / {self._detach_topic}"
        )

    def _on_state(self, message: RobotState) -> None:
        """Publish an attach or a detach when, and only when, custody changes."""
        topic = self._custody.topic_for(message.gripper_holding)
        if topic is not None:
            self._publish(topic)

    def _publish(self, topic: str) -> None:
        what = "take hold" if topic == self._attach_topic else "let go"
        publisher = self._publishers[topic]
        if not publisher.has_connections():
            # Reported and still sent. A gz-transport publication with no matched
            # subscriber reaches nobody and says nothing about it — the same
            # silence CLAUDE.md §10 records for ROS QoS — and the consequence
            # here is an arm that carries a box on friction alone while
            # everything above reports a grasp. Sending anyway costs nothing and
            # covers the case where the connection appears between this check and
            # the call.
            self.get_logger().warn(
                f"telling the simulation to {what} on {topic}, which has no subscriber. "
                "Either the world declares no grasp-hold plugin for this arm, or this "
                "process is in a different Gazebo partition from the simulator."
            )
        if not publisher.publish(self._empty()):
            self.get_logger().error(f"could not publish on {topic}")


def main() -> int:
    """Run one arm's bridge until the context shuts down."""
    # `cite_runtime.init` rather than `rclpy.init`, for the reason ADR-0034
    # gives: the shutdown handler has to be in the chain before rclpy records it.
    runtime.init(args=sys.argv)
    try:
        node = GraspHoldBridge()
    except BridgeError as error:
        print(f"GRASP HOLD BRIDGE FAILED: {error}", file=sys.stderr)
        rclpy.shutdown()
        return 1
    try:
        runtime.spin(node)
    finally:
        runtime.shutdown(node)
    return 0


if __name__ == "__main__":
    sys.exit(main())
