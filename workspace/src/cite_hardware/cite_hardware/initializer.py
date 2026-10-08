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

"""Initialize a physical arm the way its operator does in UFACTORY Studio (ADR-0070).

Before running the real program from Studio the operator initializes the linear
track by hand: the motor enabled, and the carriage homed when it has not found
its zero. Without that every track move is refused by the vendor with code 82
(`LINEAR_MOTOR_NOT_INIT`: the track's `on_zero` bit is not set), which is what
stopped the first supervised paired run at its first track step. This node
does the same, on request, through the vendor driver's own services:

1. `set_linear_motor_enable(1)`;
2. `set_gripper_enable(1)`;
3. `get_linear_motor_on_zero`, and ONLY where it reads 0:
4. `set_linear_motor_back_origin(wait=false, auto_enable=false)`, sent once
   and never re-sent, then `get_linear_motor_on_zero` read every
   `poll_period_s` until it says 1.

It serves `cite_interfaces/srv/InitializeAsset` under the name the plan states
(`/cite/<zone>/<asset>/initialize`), and only while active. Every step must
answer `ret == 0`, and the whole request is bounded by `deadline_s`; anything
else answers `success: false` naming the step and the vendor's code. No
`clean_error`: clearing an error is the operator's decision.

**Homing moves the carriage**, so it is behind the deadman's gate like every
other motion of this side (`cite_hardware.gate`): a request is refused unless
the deadman says HEALTHY, and a homing during which the gate closes, that is
refused, or that does not finish within the deadline is followed by
`set_linear_motor_stop`. So is the process ending while a homing is in flight
(`stop_before_exit`).

**Every vendor call is sent as the hold gate sends its STOP** (commit
`6e7a733`): only once this client has matched the vendor's server, and again
each time `call_deadline_s` passes unanswered, with earlier requests left
pending so a slow answer still counts. Except the homing, which is a motion and
is sent once.

**Nothing blocks a callback.** The service callback is a coroutine that awaits
futures completed by other callbacks (vendor answers, a one-shot timer), on a
re-entrant group under the multi-threaded executor `process.run` spins.
"""

from __future__ import annotations

import sys
import threading

from cite_hardware.gate import DeadmanGate
from cite_hardware.parameters import ParameterError, RequiredParameters, Spec
from cite_hardware.process import run
from cite_interfaces.srv import InitializeAsset
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.task import Future
from xarm_msgs.srv import Call, GetInt16, LinearMotorBackOrigin, SetInt16

NODE_NAME = "initializer"

#: The vendor's argument that enables the track motor, and the gripper.
VENDOR_ENABLE = 1

SPECS: tuple[Spec, ...] = (
    Spec(
        "service_name",
        Parameter.Type.STRING,
        "the InitializeAsset service this node serves: the plan's initialize_service",
    ),
    Spec(
        "linear_motor_enable_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_enable service (xarm_msgs/SetInt16)",
    ),
    Spec(
        "gripper_enable_service",
        Parameter.Type.STRING,
        "the vendor's set_gripper_enable service (xarm_msgs/SetInt16)",
    ),
    Spec(
        "linear_motor_on_zero_service",
        Parameter.Type.STRING,
        "the vendor's get_linear_motor_on_zero service (xarm_msgs/GetInt16)",
    ),
    Spec(
        "linear_motor_back_origin_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_back_origin service (xarm_msgs/LinearMotorBackOrigin)",
    ),
    Spec(
        "linear_motor_stop_service",
        Parameter.Type.STRING,
        "the vendor's set_linear_motor_stop service (xarm_msgs/Call)",
    ),
    Spec(
        "poll_period_s",
        Parameter.Type.DOUBLE,
        "how often the track's zero is read while it homes, seconds",
        positive=True,
    ),
    Spec(
        "call_deadline_s",
        Parameter.Type.DOUBLE,
        "how long one vendor request waits for its answer before it is sent again, seconds",
        positive=True,
    ),
    Spec(
        "deadline_s",
        Parameter.Type.DOUBLE,
        "the ceiling on one whole initialization, homing included, steady-clock seconds",
        positive=True,
    ),
    Spec(
        "deadman_state_topic",
        Parameter.Type.STRING,
        "the deadman's DeadmanState topic for this side",
    ),
    Spec(
        "deadman_state_max_age_s",
        Parameter.Type.DOUBLE,
        "steady-clock age above which the deadman's last state closes the gate",
        positive=True,
    ),
)


class InitializeFailed(RuntimeError):
    """One step of an initialization did not succeed; the message says which."""


class Initializer(LifecycleNode):
    def __init__(self, **node_options) -> None:
        super().__init__(NODE_NAME, **node_options)
        self._required = RequiredParameters(self, SPECS)
        self._lock = threading.Lock()
        self._group = ReentrantCallbackGroup()
        self._steady = Clock(clock_type=ClockType.STEADY_TIME)
        self._config: dict | None = None
        self._active = False
        self._busy = False
        #: Whether a homing this node sent may still be moving the carriage.
        self._homing = False
        self._vendor_clients: dict = {}
        self._service = None
        self._gate: DeadmanGate | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            config = self._required.read()
        except ParameterError as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        if self.get_parameter("use_sim_time").value:
            self.get_logger().error("cannot configure: a physical side runs on the wall clock")
            return TransitionCallbackReturn.FAILURE
        self._config = config
        kinds = {
            "linear_motor_enable_service": SetInt16,
            "gripper_enable_service": SetInt16,
            "linear_motor_on_zero_service": GetInt16,
            "linear_motor_back_origin_service": LinearMotorBackOrigin,
            "linear_motor_stop_service": Call,
        }
        self._vendor_clients = {
            key: self.create_client(kind, config[key], callback_group=self._group)
            for key, kind in kinds.items()
        }
        self._gate = DeadmanGate(
            self,
            config["deadman_state_topic"],
            config["deadman_state_max_age_s"],
            self._group,
            lambda reason: None,
        )
        self._service = self.create_service(
            InitializeAsset,
            config["service_name"],
            self._on_initialize,
            callback_group=self._group,
        )
        self.get_logger().info(f"configured: serving {config['service_name']}")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = True
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        with self._lock:
            self._active = False
        self._release()
        return TransitionCallbackReturn.SUCCESS

    def _release(self) -> None:
        if self._service is not None:
            self.destroy_service(self._service)
            self._service = None
        for client in self._vendor_clients.values():
            self.destroy_client(client)
        self._vendor_clients = {}
        if self._gate is not None:
            self._gate.destroy()
            self._gate = None
        self._config = None

    def stop_before_exit(self) -> tuple[list, float]:
        """Stop the carriage if a homing this node sent may still be moving it."""
        with self._lock:
            self._active = False
            homing = self._homing
        config, client = self._config, self._vendor_clients.get("linear_motor_stop_service")
        if not homing or config is None or client is None:
            return [], 0.0
        self.get_logger().warning("process ending during a homing: set_linear_motor_stop sent")
        return [client.call_async(Call.Request())], 2.0 * config["call_deadline_s"]

    # ------------------------------------------------------------------ #
    # The service
    # ------------------------------------------------------------------ #

    async def _on_initialize(self, _request, response):
        with self._lock:
            refusal = (
                "the initializer is not active"
                if not self._active or self._config is None
                else "an initialization is already running"
                if self._busy
                else ""
            )
            if not refusal:
                self._busy = True
        if not refusal and not self._gate.permits_motion():  # type: ignore[union-attr]
            refusal = f"refused: {self._gate.why_closed()}"  # type: ignore[union-attr]
            with self._lock:
                self._busy = False
        if refusal:
            response.success, response.detail = False, refusal
            self.get_logger().warning(f"initialize {refusal}")
            return response
        try:
            response.detail = await self._initialize()
            response.success = True
            self.get_logger().info(f"initialized: {response.detail}")
        except InitializeFailed as failure:
            response.success, response.detail = False, str(failure)
            self.get_logger().error(f"initialize failed: {failure}")
        finally:
            with self._lock:
                self._busy = False
        return response

    async def _initialize(self) -> str:
        config = self._config
        assert config is not None
        deadline = self._now() + config["deadline_s"]
        await self._ask(
            "linear_motor_enable_service",
            SetInt16.Request(data=VENDOR_ENABLE),
            f"set_linear_motor_enable({VENDOR_ENABLE})",
            deadline,
        )
        await self._ask(
            "gripper_enable_service",
            SetInt16.Request(data=VENDOR_ENABLE),
            f"set_gripper_enable({VENDOR_ENABLE})",
            deadline,
        )
        if await self._on_zero(deadline):
            return "track and gripper enabled; the track is on its zero, not homed"
        self.get_logger().warning("the track has not found its zero: homing it")
        with self._lock:
            self._homing = True
        try:
            await self._ask(
                "linear_motor_back_origin_service",
                LinearMotorBackOrigin.Request(wait=False, auto_enable=False),
                "set_linear_motor_back_origin",
                deadline,
                resend=False,
            )
            while True:
                await self._pause(config["poll_period_s"], deadline)
                if not self._gate.permits_motion():  # type: ignore[union-attr]
                    raise InitializeFailed(
                        f"homing stopped: {self._gate.why_closed()}"  # type: ignore[union-attr]
                    )
                if await self._on_zero(deadline):
                    break
        except InitializeFailed as failure:
            await self._stop_track()
            raise InitializeFailed(
                f"{failure}; set_linear_motor_stop sent. Home the track with the vendor's "
                "own tools before starting again"
            ) from failure
        finally:
            with self._lock:
                self._homing = False
        return "track and gripper enabled; the track was homed and is on its zero"

    async def _on_zero(self, deadline: float) -> bool:
        answer = await self._ask(
            "linear_motor_on_zero_service", GetInt16.Request(), "get_linear_motor_on_zero",
            deadline,
        )
        return answer.data == 1

    async def _stop_track(self) -> None:
        config = self._config
        assert config is not None
        try:
            await self._ask(
                "linear_motor_stop_service", Call.Request(), "set_linear_motor_stop",
                self._now() + 2.0 * config["call_deadline_s"],
            )
        except InitializeFailed as failure:
            self.get_logger().error(str(failure))

    async def _ask(self, key: str, request, label: str, deadline: float, resend: bool = True):
        """Send once matched; send again at every `call_deadline_s` until one is answered.

        Every request stays pending, so whichever is answered first counts; all
        still pending are removed on return. ``resend=False`` sends once and
        waits for that answer until ``deadline``. A refusal (`ret != 0`) is final.
        """
        config = self._config
        assert config is not None
        client = self._vendor_clients[key]
        sent: list[Future] = []
        try:
            while not client.service_is_ready():
                if self._now() >= deadline:
                    raise InitializeFailed(f"{client.srv_name} never matched this client")
                await self._pause(config["poll_period_s"], deadline)
            while True:
                sent.append(client.call_async(request))
                resend_at = deadline if not resend else min(
                    deadline, self._now() + config["call_deadline_s"]
                )
                answered = await self._first_of(sent, resend_at)
                if answered is not None:
                    break
                if self._now() >= deadline:
                    raise InitializeFailed(f"the vendor did not answer {label} in time")
        finally:
            for future in sent:
                if not future.done():
                    client.remove_pending_request(future)
                    future.cancel()
        response = answered.result()
        if response is None or response.ret != 0:
            code = None if response is None else response.ret
            detail = "" if response is None else f": {response.message}"
            raise InitializeFailed(f"the vendor refused {label} (code {code}{detail})")
        return response

    async def _first_of(self, futures: list[Future], until: float) -> Future | None:
        """Wait until one of ``futures`` is done or ``until`` passes, without blocking."""
        woken = Future()
        for future in futures:
            future.add_done_callback(lambda _done: woken.done() or woken.set_result(True))
        timer = self._wake_at(woken, until)
        try:
            await woken
        finally:
            self.destroy_timer(timer)
        return next((future for future in futures if future.done()), None)

    async def _pause(self, seconds: float, deadline: float) -> None:
        if self._now() >= deadline:
            raise InitializeFailed(f"not done within {self._config['deadline_s']:g} s")
        woken = Future()
        timer = self._wake_at(woken, min(deadline, self._now() + seconds))
        try:
            await woken
        finally:
            self.destroy_timer(timer)

    def _wake_at(self, future: Future, when: float):
        """Return a timer that completes ``future`` once ``when`` (steady seconds) passed."""

        def fire() -> None:
            if self._now() >= when and not future.done():
                future.set_result(True)

        period = max(0.001, min(0.05, when - self._now()))
        return self.create_timer(
            period, fire, callback_group=self._group, clock=self._steady
        )

    def _now(self) -> float:
        return self._steady.now().nanoseconds * 1e-9


def main() -> int:
    return run(Initializer)


if __name__ == "__main__":
    sys.exit(main())
