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

"""One side of a twin pair, faked: L3's action names, and nothing behind them.

**Test-only, and it is not a cell.** It serves the action names an arm's skill
server serves, publishes a joint state and a model version, and moves nothing.
What it exists to make possible is the one thing no automated test in this
repository could do before: watch a goal cross the twin boundary and arrive on
the far side's own domain.

**WHY THIS IS NOT THE THING FOUR DOCUMENTS SAID WAS IMPOSSIBLE.** They said
`launch_test` holds one context on one domain, so two sides cannot be included
in one test process — which is true, and is about `IncludeLaunchDescription`
putting a whole cell's launch inside the test. It is not the only shape a test
can take. This one puts each side in its own PROCESS, with its own
`ROS_DOMAIN_ID`, started as a child of the launch description; the test process
holds one context on the plant's domain and never opens a second. What the far
side did is read from its STDOUT, which is what a launch-process supervisor is
already allowed to observe (ADR-0044 clause 3's second carve-out).

**HOW A TEST STEERS IT.** The behaviour of each goal is carried in the goal
itself, per side, as `<plant>:<counterpart>` in whichever string field the
action has — `named_configuration` for `MoveTo`, `workpiece_id` for `Pick`. A
server reads the half addressed to the side it was started as. That is what lets
one rig drive "the plant succeeds and the far side aborts", which is the case
that used to be reported to the operator as a clean success.

Behaviours: `succeed`, `abort`, `throw` (an uncaught exception in the execute
callback, which is what rclpy answers with a default-constructed result),
`hold` (never finishes until cancelled), and `empty` (succeed while reporting no
custody).
"""

from __future__ import annotations

import argparse
import sys
import threading

from cite_interfaces.action import MoveTo, Pick
from cite_interfaces.msg import ModelVersion, ResultCode
from cite_interfaces.qos import LATCHED, STATE
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState

#: The joints this fake reports, and the only thing a divergence comparison
#: here has to work over.
JOINTS = ("joint1", "joint2")

#: How often the fake publishes its joint state, in seconds. A publication rate
#: and not a timing guess: nothing is sequenced on it.
STATE_PERIOD_S = 0.05


def _behaviour(text: str, side: str) -> str:
    """Read the half of ``<plant>:<counterpart>`` addressed to ``side``."""
    plant, _, counterpart = text.partition(":")
    chosen = counterpart if side == "counterpart" else plant
    return chosen or "succeed"


class FakeSide(Node):
    def __init__(self, side: str, zone: str, assets: list[str], offset: float) -> None:
        super().__init__("fake_side")
        self._side = side
        self._offset = offset
        self._group = ReentrantCallbackGroup()
        self._servers = []
        for asset in assets:
            namespace = f"/cite/{zone}/{asset}"
            self._servers.append(
                self._serve(MoveTo, f"{namespace}/move_to", "named_configuration")
            )
            self._servers.append(
                self._serve(Pick, f"{namespace}/pick", "workpiece_id")
            )
        self._states = [
            self.create_publisher(JointState, f"/cite/{zone}/{asset}/joint_states", STATE)
            for asset in assets
        ]
        self._model = self.create_publisher(
            ModelVersion, "/cite/facility/model_version", LATCHED
        )
        self.create_timer(STATE_PERIOD_S, self._publish_state, callback_group=self._group)
        self.create_timer(0.5, self._publish_model, callback_group=self._group)
        print(f"{side}: up with {len(self._servers)} action server(s)", flush=True)

    def _serve(self, action_type, name: str, steering_field: str) -> ActionServer:
        return ActionServer(
            self,
            action_type,
            name,
            execute_callback=lambda handle: self._execute(
                action_type, name, steering_field, handle
            ),
            goal_callback=lambda goal: GoalResponse.ACCEPT,
            cancel_callback=lambda handle: CancelResponse.ACCEPT,
            callback_group=self._group,
        )

    def _execute(self, action_type, name: str, steering_field: str, goal_handle):
        behaviour = _behaviour(
            getattr(goal_handle.request, steering_field, ""), self._side
        )
        # The line the test reads. It is the evidence that this goal reached
        # this side, on this side's own domain, and it is printed BEFORE the
        # behaviour is applied so that a goal which never finishes is still
        # visible as having arrived.
        print(f"{self._side}: accepted {name} as {behaviour}", flush=True)

        if behaviour == "throw":
            raise RuntimeError("the far side's execute callback raised")

        if behaviour == "hold":
            while not goal_handle.is_cancel_requested:
                if not rclpy.ok(context=self.context):
                    break
                threading.Event().wait(0.05)
            print(f"{self._side}: cancelled {name}", flush=True)
            goal_handle.canceled()
            return self._result(action_type, ResultCode.CANCELLED, holding=True)

        if behaviour == "abort":
            goal_handle.abort()
            return self._result(
                action_type, ResultCode.MOTION_INTERRUPTED, holding=True
            )

        goal_handle.succeed()
        return self._result(
            action_type, ResultCode.SUCCESS, holding=behaviour != "empty"
        )

    def _result(self, action_type, code: int, holding: bool):
        result = action_type.Result()
        result.result = ResultCode(code=code, detail=f"{self._side}: {code}")
        if hasattr(result, "holding"):
            result.holding = holding
        if hasattr(result, "position_error_m"):
            # A number the test can tell the two sides apart by, which is what
            # makes "the plant's measurement is forwarded" checkable.
            result.position_error_m = self._offset
            result.reached.header.frame_id = self._side
        return result

    def _publish_state(self) -> None:
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(JOINTS)
        message.position = [self._offset for _ in JOINTS]
        for publisher in self._states:
            publisher.publish(message)

    def _publish_model(self) -> None:
        message = ModelVersion()
        message.header.stamp = self.get_clock().now().to_msg()
        # Identical on both sides: two sides of one pair are generated from one
        # L0 model, so a disagreement here would be term 4 failing rather than
        # the case under test.
        message.model_hash = "fake-pair"
        self._model.publish(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", required=True)
    parser.add_argument("--zone", default="cell_a")
    parser.add_argument("--assets", default="arm_1")
    parser.add_argument("--offset", type=float, default=0.0)
    arguments, _ = parser.parse_known_args()

    rclpy.init()
    node = FakeSide(
        arguments.side, arguments.zone, arguments.assets.split(","), arguments.offset
    )
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
