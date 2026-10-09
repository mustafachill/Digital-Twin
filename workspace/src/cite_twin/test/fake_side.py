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
from cite_interfaces.msg import ModelVersion, ResultCode, TwinHeartbeat
from cite_interfaces.qos import COMMAND, LATCHED, STATE
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from trajectory_msgs.msg import JointTrajectory

#: The joints this fake reports, each from a publisher of its own, as a
#: physical side's arm broadcaster, track adapter and gripper relay share one
#: joint-state topic with partial messages (R-05).
JOINTS = ("joint1", "joint2")

#: A third joint, from a third publisher that goes QUIET after
#: `QUIET_AFTER` messages delivered to a matched subscriber: the publisher
#: whose silence the boundary's merged operand must not hide.
QUIET_JOINT = "joint3"
QUIET_AFTER = 20

#: How often the fake publishes its joint state, in seconds. A publication rate
#: and not a timing guess: nothing is sequenced on it.
STATE_PERIOD_S = 0.05


def _behaviour(text: str, side: str) -> str:
    """Read the half of ``<plant>:<counterpart>`` addressed to ``side``."""
    plant, _, counterpart = text.partition(":")
    chosen = counterpart if side == "counterpart" else plant
    return chosen or "succeed"


class FakeSide(Node):
    def __init__(
        self,
        side: str,
        zone: str,
        assets: list[str],
        offset: float,
        belts: list[str],
        track: tuple[str, str] | None = None,
        joints: tuple[str, ...] = JOINTS,
    ) -> None:
        super().__init__("fake_side")
        #: The arm joints this side reports. The default is the boundary rigs';
        #: the console's rig (ADR-0071) names the plan's own, so that the start
        #: the program measures is heard rather than waited for.
        self._joints = tuple(joints)
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
            [
                self.create_publisher(JointState, f"/cite/{zone}/{asset}/joint_states", STATE)
                for _joint in self._joints + (QUIET_JOINT,)
            ]
            for asset in assets
        ]
        self._quiet_sent = 0
        # Each belt command this side receives is printed, which is how the
        # test sees a setpoint L5 forwarded onto this side's own domain.
        self._belts = [
            self.create_subscription(
                Float64,
                topic,
                lambda message, topic=topic: print(
                    f"{side}: belt {topic} {message.data:g}", flush=True
                ),
                COMMAND,
            )
            for topic in belts
        ]
        # A track joint at this side's offset, on the first asset's joint
        # states, and every track command this side receives printed with its
        # points' positions: how the test sees what L5 sent to which carriage.
        self._track_joint = None
        self._track_state = None
        if track is not None:
            topic, self._track_joint = track
            self._track_state = self.create_publisher(
                JointState, f"/cite/{zone}/{assets[0]}/joint_states", STATE
            )
            self._track_commands = self.create_subscription(
                JointTrajectory,
                topic,
                lambda message: print(
                    f"{side}: track {[round(p.positions[0], 3) for p in message.points]}",
                    flush=True,
                ),
                COMMAND,
            )
        self._model = self.create_publisher(
            ModelVersion, "/cite/facility/model_version", LATCHED
        )
        # The boundary's heartbeat on THIS side's domain (ADR-0070 item 5),
        # printed twice and no more: the first one, and the first that shows
        # the sequence advancing. Every heartbeat would flood the output the
        # test reads.
        self._heartbeat_first: int | None = None
        self._heartbeat_advanced = False
        self._heartbeats = self.create_subscription(
            TwinHeartbeat, TwinHeartbeat.TOPIC, self._on_heartbeat, STATE
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

    def _on_heartbeat(self, message: TwinHeartbeat) -> None:
        if self._heartbeat_first is None:
            self._heartbeat_first = message.sequence
            print(f"{self._side}: heartbeat zone={message.zone}", flush=True)
        elif not self._heartbeat_advanced and message.sequence > self._heartbeat_first:
            self._heartbeat_advanced = True
            print(f"{self._side}: heartbeat advancing", flush=True)

    def _publish_state(self) -> None:
        stamp = self.get_clock().now().to_msg()
        quiet_now = False
        for publishers in self._states:
            for joint, publisher in zip(self._joints + (QUIET_JOINT,), publishers):
                if joint == QUIET_JOINT:
                    # Counted only once a subscriber matched, so the boundary
                    # has heard it before it goes quiet.
                    if publisher.get_subscription_count() == 0:
                        continue
                    if self._quiet_sent >= QUIET_AFTER:
                        continue
                    quiet_now = True
                message = JointState()
                message.header.stamp = stamp
                message.name = [joint]
                message.position = [self._offset]
                publisher.publish(message)
        if self._track_state is not None:
            message = JointState()
            message.header.stamp = stamp
            message.name = [self._track_joint]
            message.position = [self._offset]
            self._track_state.publish(message)
        if quiet_now:
            self._quiet_sent += 1
            if self._quiet_sent == QUIET_AFTER:
                print(f"{self._side}: {QUIET_JOINT} publisher quiet", flush=True)

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
    parser.add_argument("--zone", default="cell_b")
    parser.add_argument("--assets", default="picker")
    parser.add_argument("--offset", type=float, default=0.0)
    parser.add_argument("--belts", default="", help="Belt command topics to listen on.")
    parser.add_argument("--track-topic", default="", help="A track command topic to listen on.")
    parser.add_argument("--track-joint", default="", help="The track joint to publish.")
    parser.add_argument(
        "--joints", default=",".join(JOINTS), help="The arm joints to publish."
    )
    arguments, _ = parser.parse_known_args()

    rclpy.init()
    node = FakeSide(
        arguments.side,
        arguments.zone,
        arguments.assets.split(","),
        arguments.offset,
        [topic for topic in arguments.belts.split(",") if topic],
        (arguments.track_topic, arguments.track_joint) if arguments.track_topic else None,
        tuple(joint for joint in arguments.joints.split(",") if joint),
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
