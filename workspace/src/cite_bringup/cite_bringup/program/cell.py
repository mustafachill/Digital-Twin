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

"""The real `Cell`: one rclpy node, on ONE domain, calling the L3 skills.

`--via twin` addresses the twin boundary's operator endpoints on the plant's
domain, and L5 forwards each goal and each belt setpoint to both sides. The
program never opens the counterpart's domain itself: ADR-0044 clause 3 makes the
boundary the only component with endpoints in both. `--via plant` addresses the
plant's own servers, which is a single side.

Nothing here runs inside a callback. The program is a plain loop on the main
thread that spins the node while it waits, so a blocking call cannot starve an
executor (CLAUDE.md §10).
"""

from __future__ import annotations

from cite_bringup.plan import resolve_uri
from cite_bringup.program.cell_b_pick_place import Target
from cite_bringup.program.steps import StepFailed
from cite_interfaces.action import Grasp, MoveTo
from cite_interfaces.msg import ResultCode, TwinMode
from cite_interfaces.qos import COMMAND
from cite_interfaces.srv import SetMode
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import Float64
import yaml

#: The reserved twin scope, read off the one contract that states it. The
#: boundary forms `/cite/twin/<zone>/...` from a side's `/cite/<zone>/...` the
#: same way (`cite_twin.boundary.operator_endpoint`); cite_twin cannot be
#: imported here, because it depends on this package.
TWIN_SCOPE = SetMode.Request.SERVICE.rsplit("/", 1)[0]
ROOT = TWIN_SCOPE.rsplit("/", 1)[0]

#: How long to wait for a server to appear. A hang detector, not a schedule.
SERVER_WAIT_S = 60.0

#: How long one step may take before it is reported as hung, in wall seconds.
#: A motion or a grasp takes seconds; this is sized for a cell running well
#: below real time, and it bounds a failure rather than sequencing anything.
STEP_CEILING_S = 600.0


def twin_name(name: str) -> str:
    """`/cite/cell_b/picker/move_to` -> `/cite/twin/cell_b/picker/move_to`."""
    if not name.startswith(f"{ROOT}/"):
        raise ValueError(f"{name!r} is not a name under {ROOT}/")
    return f"{TWIN_SCOPE}{name[len(ROOT):]}"


def gripper_effort_n(target: Target) -> float:
    """Return the gripper controller's own effort ceiling, from its generated configuration."""
    controller = target.arm.gripper_action.rsplit("/", 1)[0]
    document = yaml.safe_load(resolve_uri(target.arm.parameters).read_text())
    return float(document[controller]["ros__parameters"]["max_effort"])


class RosCell:
    """Drive one arm and one belt, through the twin or on the plant alone."""

    def __init__(self, target: Target, via: str) -> None:
        skills = target.arm.skills
        name = twin_name if via == "twin" else (lambda plain: plain)
        self._via = via
        self._effort_n = gripper_effort_n(target)
        self.node = Node(
            "fixed_program", parameter_overrides=[Parameter("use_sim_time", value=True)]
        )
        self._move_to = ActionClient(self.node, MoveTo, name(skills.move_to))
        self._grasp = ActionClient(self.node, Grasp, name(skills.grasp))
        self._belt = self.node.create_publisher(
            Float64, name(target.conveyor.command_topic), COMMAND
        )
        self._active = None

    # --------------------------------------------------------------- setup

    def enter_validated(self) -> None:
        """Put the twin in VALIDATED, where L5 routes a command to both sides."""
        client = self.node.create_client(SetMode, SetMode.Request.SERVICE)
        if not client.wait_for_service(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{SetMode.Request.SERVICE} is not served; is the pair up?")
        request = SetMode.Request(
            mode=TwinMode.MODE_VALIDATED, reason="fixed program (ADR-0066)"
        )
        response = self._until(client.call_async(request), "SetMode(VALIDATED)")
        if not response.accepted:
            raise StepFailed(f"the twin refused VALIDATED: {response.result.detail}")

    # --------------------------------------------------------------- steps

    def move(self, pose: str) -> None:
        self._goal(self._move_to, MoveTo.Goal(named_configuration=pose), f"move to {pose}")

    def grip(self, width_m: float, expect_object: bool) -> None:
        goal = Grasp.Goal(
            width_m=width_m, max_effort_n=self._effort_n, expect_object=expect_object
        )
        self._goal(self._grasp, goal, "grip")

    def belt(self, speed_mps: float) -> None:
        # Asked to wait for the belt's subscriber first: a setpoint published
        # before the match reaches nobody, reliable or not (CLAUDE.md §10).
        self._until_true(
            lambda: self._belt.get_subscription_count() > 0,
            f"a subscriber on {self._belt.topic_name}",
        )
        self._belt.publish(Float64(data=float(speed_mps)))

    def wait(self, seconds: float) -> None:
        clock = self.node.get_clock()
        end = clock.now().nanoseconds + int(seconds * 1e9)
        while clock.now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def cancel(self) -> None:
        handle, self._active = self._active, None
        if handle is not None:
            self._until(handle.cancel_goal_async(), "the cancel")

    # --------------------------------------------------------------- mechanism

    def _goal(self, client: ActionClient, goal, what: str) -> None:
        if not client.wait_for_server(timeout_sec=SERVER_WAIT_S):
            raise StepFailed(f"{what}: {client._action_name} is not served")
        handle = self._until(client.send_goal_async(goal), f"{what}: acceptance")
        if not handle.accepted:
            raise StepFailed(f"{what}: {client._action_name} rejected the goal")
        self._active = handle
        wrapped = self._until(handle.get_result_async(), what)
        self._active = None
        code = wrapped.result.result
        if code.code != ResultCode.SUCCESS:
            raise StepFailed(f"{what}: result code {code.code}: {code.detail}")

    def _until(self, future, what: str):
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=STEP_CEILING_S)
        if not future.done():
            raise StepFailed(f"{what} did not finish within {STEP_CEILING_S:.0f} s")
        return future.result()

    def _until_true(self, predicate, what: str) -> None:
        for _ in range(int(SERVER_WAIT_S / 0.1)):
            if predicate():
                return
            rclpy.spin_once(self.node, timeout_sec=0.1)
        raise StepFailed(f"no {what} after {SERVER_WAIT_S:.0f} s")
