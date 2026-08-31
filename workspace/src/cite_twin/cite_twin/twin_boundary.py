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

"""The twin boundary: one process per zone, one ROS context per side.

Three things, and they are the three ADR-0050 decides:

1. **The mode server.** `SetMode` on `/cite/twin/set_mode`, `TwinMode` latched on
   `/cite/twin/mode`, both on the plant's domain because that is the side the
   operator is on. The transition applies the hardware opt-in check at the
   transition rather than only at bring-up, which is what `SetMode.srv`'s header
   commits this server to.
2. **Command routing.** An L5 action server per arm per skill, under
   `/cite/twin/...`, dispatching the GOAL to each side's own L3 action server on
   that side's own domain. **The goal crosses and the motion never does.**
3. **The divergence monitor.** One `DivergenceMetrics` per asset on
   `/cite/twin/divergence`, with `valid` computed as ADR-0050 decision 3's
   conjunction — which cannot be true today, because one of its terms is each
   side's clock deficit within a bound ADR-0049 leaves unset and no instrument
   measures. **So the monitor publishes self-describing invalid samples rather
   than nothing**, each carrying the terms that decide its own validity.

**NOTHING HERE IS A FIDELITY MEASUREMENT.** Both sides of a Phase 2.A pair run
the same L0 model, the same generated description, the same controllers and the
same solver, so a comparison is a thing with itself. `far_side_physical` is the
field that answers whether a number could ever be one, and in 2.A it is false
for every asset. No log line, no field and no document here may suggest that a
divergence number is a reality gap (P8, ADR-0041).

**WHY THIS PROCESS DOES NOT GO THROUGH `cite_runtime`.** That module's adoption
rule names this component by name: it absorbs SIGINT so that a teardown can run
to completion, and it says in terms that the pattern is *for a process that
commands no actuator*, and that a process which commands one must guarantee no
callback blocks unbounded or install its own hard-stop path. L5 dispatches goals
that move arms and it waits for them without a deadline (see
`_await_far_side_goals`), so it meets neither condition. It therefore keeps
rclpy's ordinary SIGINT behaviour — an operator's Ctrl-C is not absorbed — and
imports from `cite_runtime` only the one thing that module documents as the
single place it is written down: which exceptions mean "the context went away".

**`use_sim_time` IS REFUSED, and that is not an oversight.** L5 holds two
contexts whose simulated clocks are independent and separate without bound
(ADR-0043, ADR-0049), so there is no one simulated clock for this process to
honour; ADR-0050 decision 3 makes the pairing key the wall clock for exactly
that reason. A node that took its time from one side's `/clock` would stamp the
other side's operand in a clock that side never ran in. Every other node in this
system honours `use_sim_time`; this one is the only one that cannot, and it
refuses to start with it set rather than quietly ignoring it.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
import os
from pathlib import Path
import sys
import threading
import time

from cite_bringup.plan import (
    Plan,
    PlanError,
    default_plan_path,
    domain_base,
    load,
    require_hardware_opt_in,
)
from cite_facility import model_info
from cite_interfaces.msg import DivergenceMetrics, ModelVersion, ResultCode, TwinMode
from cite_interfaces.qos import LATCHED, STATE
from cite_interfaces.srv import SetMode
from cite_runtime.runtime import SHUTDOWN_EXCEPTIONS, caused_by_shutdown
from cite_twin.boundary import (
    JOINT_STATE_INTERFACE,
    SKILL_ACTION_TYPES,
    BoundaryError,
    SideContext,
    address,
    asset_namespace,
    operator_endpoint,
)
from cite_twin.divergence import UNMEASURED, Operand, assess, compare
from cite_twin.mode import MODE_NAMES, SIMULATION_BACKEND, Deployment, ModeAuthority
from cite_twin.routing import COUNTERPART_SIDE, PLANT_SIDE, route
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.task import Future
from sensor_msgs.msg import JointState

#: How long L5 waits for a side's L3 action server to appear before it reports
#: that the goal cannot be dispatched, in seconds of the WALL clock.
#:
#: A discovery wait and never a motion wait, which is what makes a wall-clock
#: ceiling defensible here: `ActionClient.wait_for_server` waits on a graph
#: event, so it returns the instant the server appears and the ceiling is only
#: reached when it never does. ADR-0045's defect — a wall-clock deadline
#: supervising a simulation-time process — is the one this is not: nothing
#: bounded by this number is executed by a simulator.
SERVER_WAIT_S = 30.0

#: How often a divergence sample is published, per asset, in seconds.
#:
#: A publication rate rather than a timing guess: nothing is sequenced on it and
#: no state transition waits for it (P4). It is a node parameter so a deployment
#: can change it without a rebuild.
DIVERGENCE_PERIOD_S = 1.0


@dataclass(frozen=True)
class _SkillEndpoint:
    """One routable skill: what it is called on a side, and what type it carries."""

    asset: str
    field: str
    action_type: type
    #: The name each SIDE's own L3 server advertises. Byte-identical on both
    #: sides by rule (ADR-0044 clause 1), which is why one string serves both.
    side_name: str
    #: The `/cite/twin/...` name L5 advertises to the operator.
    endpoint: str


class TwinBoundary:
    """L5, assembled around two `SideContext` objects.

    Every endpoint below is created on exactly one of them, and which one is
    the whole of the "which side is this?" question. Nothing in this class holds
    a context of its own.
    """

    def __init__(self, plan: Plan, base: int, environ: Mapping[str, str]) -> None:
        self._plan = plan
        self._lock = threading.Lock()

        # Both sides resolved by NAME through ADR-0044 clause 4's single
        # resolver. A zone that declares no counterpart refuses here, with the
        # plan reader's own message, rather than L5 inventing a second side.
        self._sides = {
            PLANT_SIDE: SideContext(address(plan, PLANT_SIDE, base)),
            COUNTERPART_SIDE: SideContext(address(plan, COUNTERPART_SIDE, base)),
        }
        self._plant = self._sides[PLANT_SIDE]
        self._counterpart = self._sides[COUNTERPART_SIDE]

        for side in self._sides.values():
            _refuse_sim_time(side)

        self._group = ReentrantCallbackGroup()
        self._log = self._plant.node.get_logger()

        self._plant.node.declare_parameter("divergence_period_s", DIVERGENCE_PERIOD_S)
        period = (
            self._plant.node.get_parameter("divergence_period_s")
            .get_parameter_value()
            .double_value
        )

        # What L5 read about the far side at start-up. ADR-0050 decision 4: a
        # runtime knob may not decide whether a side exists, so this is read
        # once and never re-read.
        self._far_side_backends = {
            manager.asset: manager.counterpart_backend
            for manager in plan.controller_managers
        }
        self._authority = ModeAuthority(
            Deployment(self._far_side_backends),
            partial(require_hardware_opt_in, plan, environ),
        )

        self._mode_publisher = self._plant.node.create_publisher(
            TwinMode, TwinMode.TOPIC, LATCHED
        )
        self._divergence_publisher = self._plant.node.create_publisher(
            DivergenceMetrics, DivergenceMetrics.TOPIC, STATE
        )
        self._set_mode = self._plant.node.create_service(
            SetMode,
            # rosidl puts a service's constants on the section they were
            # declared in; C++ reaches the same one as
            # `SetMode::Request::SERVICE`.
            SetMode.Request.SERVICE,
            self._on_set_mode,
            callback_group=self._group,
        )

        self._skills = _skill_endpoints(plan)
        self._servers = [self._serve(skill) for skill in self._skills]
        self._clients = {
            (side_name, skill.side_name): ActionClient(
                side.node,
                skill.action_type,
                skill.side_name,
                callback_group=self._group,
            )
            for side_name, side in self._sides.items()
            for skill in self._skills
        }

        # The reverse state flow, consumed by L5 and republished nowhere
        # (ADR-0050 decision 1b). One subscription per (side, asset), each on
        # its own side's context, so two identical topic names cannot be
        # confused for one.
        self._operands: dict[tuple[str, str], Operand] = {}
        self._model_versions: dict[str, str] = {}
        self._subscriptions = []
        for side_name, side in self._sides.items():
            for manager in plan.controller_managers:
                topic = f"{asset_namespace(manager)}/{JOINT_STATE_INTERFACE}"
                self._subscriptions.append(
                    side.node.create_subscription(
                        JointState,
                        topic,
                        partial(self._on_joint_state, side_name, manager.asset),
                        # STATE is joint_state_broadcaster's own profile:
                        # reliable, volatile, depth 10. Matched deliberately —
                        # an easier profile would connect and measure a
                        # transport this project does not use (ADR-0025).
                        STATE,
                        callback_group=self._group,
                    )
                )
            self._subscriptions.append(
                side.node.create_subscription(
                    ModelVersion,
                    model_info.TOPIC,
                    partial(self._on_model_version, side_name),
                    LATCHED,
                    callback_group=self._group,
                )
            )

        self._timer = self._plant.node.create_timer(
            period, self._publish_divergence, callback_group=self._group
        )

    # ------------------------------------------------------------------ #
    # Lifetime
    # ------------------------------------------------------------------ #

    def spin(self) -> None:
        """Spin the counterpart off-thread and the plant on this one.

        The plant runs on the calling thread so that rclpy's signal handling
        reaches the process the way it reaches every other node here. The
        counterpart's executor is a thread of its own because two contexts
        cannot share one executor — an executor is built against a context.
        """
        self._counterpart.spin_in_a_thread()
        # Published once the publisher exists and from here rather than from the
        # constructor: a subscriber match is an event, and the LATCHED profile
        # is what makes a late joiner receive it. Publishing from inside the
        # callback that created the publisher is the defect that cost this
        # project a belt setpoint (CLAUDE.md §10).
        self._publish_mode()
        self._log.info(
            f"twin boundary up: plant on domain {self._plant.side.domain_id}, "
            f"counterpart on domain {self._counterpart.side.domain_id}, "
            f"{len(self._skills)} routable skill(s), "
            f"mode {MODE_NAMES[self._authority.mode]}"
        )
        try:
            self._plant.executor.spin()
        except SHUTDOWN_EXCEPTIONS as error:
            if not caused_by_shutdown(error, self._plant.node):
                raise

    def stop(self) -> None:
        for side in self._sides.values():
            side.stop()

    # ------------------------------------------------------------------ #
    # 1. The mode server
    # ------------------------------------------------------------------ #

    def _on_set_mode(
        self, request: SetMode.Request, response: SetMode.Response
    ) -> SetMode.Response:
        """Decide one transition, publish it if it happened, and answer.

        The decision is `cite_twin.mode`'s; this method is the boundary between
        a service call and that decision. It does not start, stop or
        instantiate anything — ADR-0050 decision 4 and ADR-0047 clause 2 — so
        there is nothing to wait for and the answer is immediate.
        """
        with self._lock:
            before = self._authority.mode
            verdict = self._authority.request(
                request.mode, "", request.reason, request.force
            )
            changed = verdict.accepted and verdict.mode != before
            if changed:
                self._publish_mode()

        response.accepted = verdict.accepted
        response.result = ResultCode(code=verdict.code, detail=verdict.detail)
        response.current_mode = verdict.mode
        level = self._log.info if verdict.accepted else self._log.warning
        level(f"SetMode({_mode_name(request.mode)}): {verdict.detail}")
        return response

    def _publish_mode(self) -> None:
        message = TwinMode()
        message.header.stamp = self._plant.node.get_clock().now().to_msg()
        # Facility scope. `TwinMode.asset_id` is "empty for facility-wide", and
        # this server decides facility-wide today: `SetMode` carries no
        # asset_id, so a request is a statement about the whole zone. That
        # asymmetry with `DivergenceMetrics`, whose asset_id is never empty, is
        # ADR-0050 decision 3's — a mode is a facility fact and a divergence
        # sample is not.
        message.asset_id = ""
        message.mode = self._authority.mode
        # Equal by construction: the transition is atomic because a mode never
        # instantiates anything, so nothing is ever in flight (see
        # cite_twin.mode).
        message.requested_mode = self._authority.mode
        message.transition_in_progress = False
        message.reason = self._authority.reason
        self._mode_publisher.publish(message)

    # ------------------------------------------------------------------ #
    # 2. Command routing
    # ------------------------------------------------------------------ #

    def _serve(self, skill: _SkillEndpoint) -> ActionServer:
        return ActionServer(
            self._plant.node,
            skill.action_type,
            skill.endpoint,
            execute_callback=partial(self._execute, skill),
            goal_callback=lambda goal: GoalResponse.ACCEPT,
            cancel_callback=lambda handle: CancelResponse.ACCEPT,
            callback_group=self._group,
        )

    def _execute(self, skill: _SkillEndpoint, goal_handle):
        """Dispatch one operator goal to the sides the mode routes it to.

        **Every refusal is an ABORT carrying a `ResultCode`, never a goal
        rejection.** A rejected goal carries no result, so a caller learns that
        the twin said no and never learns why; every L3 result in this project
        is typed and this one is too (P3).

        Blocking here is deliberate and the executor was chosen for it: the
        plant's executor is multi-threaded and this server is in a reentrant
        callback group, so the responses this method waits for are served by
        other threads of the same executor while this one waits. On a
        single-threaded executor the wait for the PLANT's own goal would
        deadlock against itself.
        """
        with self._lock:
            mode = self._authority.mode
        chosen = route(mode)
        result = skill.action_type.Result()
        if not chosen.accepted:
            result.result = ResultCode(code=chosen.code, detail=chosen.detail)
            goal_handle.abort()
            self._log.warning(
                f"{skill.endpoint} refused in {MODE_NAMES.get(mode, mode)}: {chosen.detail}"
            )
            return result

        dispatched = self._dispatch(skill, goal_handle, chosen.sides)
        if isinstance(dispatched, ResultCode):
            result.result = dispatched
            goal_handle.abort()
            return result

        aggregate = self._await_far_side_goals(dispatched, goal_handle)
        result.result = aggregate
        if aggregate.code == ResultCode.SUCCESS:
            goal_handle.succeed()
        elif aggregate.code == ResultCode.CANCELLED:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return result

    def _dispatch(
        self, skill: _SkillEndpoint, goal_handle, sides: tuple[str, ...]
    ) -> dict[str, Future] | ResultCode:
        """Send the goal to each side's own L3 server, on that side's context.

        The goal message is passed through unchanged. It is not translated, not
        re-stamped and not turned into anything below L3 — what crosses is the
        goal, at the action boundary, and hardware's entry point in 2.B is the
        same typed server on the same name (P2, P9).
        """
        sent: dict[str, Future] = {}
        for side_name in sides:
            client = self._clients[(side_name, skill.side_name)]
            if not client.wait_for_server(timeout_sec=SERVER_WAIT_S):
                return ResultCode(
                    code=ResultCode.PRECONDITION_FAILED,
                    detail=(
                        f"side {side_name!r} is not serving {skill.side_name} after "
                        f"{SERVER_WAIT_S:g} s, so the goal cannot be evaluated there. "
                        "Both sides are brought up independently and neither waits on "
                        "the other (ADR-0047), so a missing server is a side that is "
                        "not up rather than an ordering fault."
                    ),
                )
            feedback = (
                partial(self._forward_feedback, goal_handle)
                if side_name == PLANT_SIDE
                else None
            )
            sent[side_name] = client.send_goal_async(
                goal_handle.request, feedback_callback=feedback
            )
        return sent

    def _forward_feedback(self, goal_handle, message) -> None:
        """Pass the PLANT's feedback through to the operator, unchanged.

        One side's and not both: two sides produce feedback of the same type on
        the same goal, and interleaving them would give the operator a stream in
        which no message says which cell it came from. The plant is chosen
        because it is the side the operator is on (ADR-0044 clause 5).

        Feedback and result are not a reverse state flow and may not be cited as
        one (ADR-0050 decision 2). An action client receives them by
        construction; that is the forward call returning. They carry no joint
        state and cannot supply the divergence metric's second operand.
        """
        goal_handle.publish_feedback(message.feedback)

    def _await_far_side_goals(self, sent: Mapping[str, Future], goal_handle) -> ResultCode:
        """Wait for every dispatched goal, forwarding a cancel to all of them.

        **No deadline, deliberately.** ADR-0045 records what a wall-clock
        deadline supervising a simulation-time process costs this project, and
        L5 has two simulated clocks to be wrong about rather than one. The
        operator's cancel is the bound, and it reaches every side.

        **A failure on one side does not cancel the other.** ADR-0050 decision
        2: L5 does not gate the far side on the near side's outcome — that gate
        is what `CLOSED_LOOP` is, and these are the modes defined as being
        without it. So both sides are allowed to finish and the aggregate is
        reported.
        """
        handles: dict[str, object] = {}
        results: dict[str, ResultCode] = {}
        for side_name, future in sent.items():
            handle = _wait(future, goal_handle, handles.values())
            if handle is None or not handle.accepted:
                results[side_name] = ResultCode(
                    code=ResultCode.PRECONDITION_FAILED,
                    detail=f"side {side_name!r} rejected the goal",
                )
                continue
            handles[side_name] = handle

        for side_name, handle in handles.items():
            future = handle.get_result_async()
            outcome = _wait(future, goal_handle, handles.values())
            results[side_name] = _result_code_of(side_name, outcome)

        return _aggregate(results)

    # ------------------------------------------------------------------ #
    # 3. The divergence monitor
    # ------------------------------------------------------------------ #

    def _on_joint_state(self, side_name: str, asset: str, message: JointState) -> None:
        """Record one side's operand, timestamped ON ARRIVAL by L5's own clock.

        The arrival stamp is the whole reason this is a subscription in L5
        rather than a bridge: a bridge copies and cannot timestamp, and the
        stamp is the term that separates a slow mirror from a wrong model
        (ADR-0044's criterion, ADR-0050 decision 1).

        The message is consumed here. It is not forwarded to a publisher on the
        other side's context, in any mode (ADR-0050 decision 1b).
        """
        positions = {
            name: float(position)
            for name, position in zip(message.name, message.position)
        }
        with self._lock:
            self._operands[(side_name, asset)] = Operand(
                positions=positions,
                received_wall_s=time.time(),
                model_version=self._model_versions.get(side_name, ""),
                # Nothing in the tree measures a clock deficit, so nothing can
                # supply one here. `None` is the honest value and it is what
                # makes term 3 of the conjunction false (ADR-0049 decision 5).
                clock_deficit_s=None,
            )

    def _on_model_version(self, side_name: str, message: ModelVersion) -> None:
        with self._lock:
            self._model_versions[side_name] = message.model_hash

    def _publish_divergence(self) -> None:
        """One sample per asset, valid or not.

        Invalid samples are published rather than withheld. A monitor that went
        quiet when it could not compute would be indistinguishable from a
        monitor that had died, and the fields that say WHICH term failed are the
        product of this mode as much as the comparison is.
        """
        with self._lock:
            mode = self._authority.mode
            operands = dict(self._operands)
            versions = dict(self._model_versions)
        now = time.time()
        for asset, backend in sorted(self._far_side_backends.items()):
            self._divergence_publisher.publish(
                self._sample(asset, backend, mode, operands, versions, now)
            )

    def _sample(
        self,
        asset: str,
        backend: str | None,
        mode: int,
        operands: Mapping[tuple[str, str], Operand],
        versions: Mapping[str, str],
        now: float,
    ) -> DivergenceMetrics:
        plant = operands.get((PLANT_SIDE, asset))
        counterpart = operands.get((COUNTERPART_SIDE, asset))
        far_side_physical = backend is not None and backend != SIMULATION_BACKEND
        conditions = assess(mode, plant, counterpart, far_side_physical)
        comparison = compare(plant, counterpart)

        message = DivergenceMetrics()
        message.header.stamp = self._plant.node.get_clock().now().to_msg()
        message.asset_id = asset
        message.valid = conditions.valid

        # The zeroing rule, applied to the six comparison fields and to nothing
        # else. Four of the six are zero in every sample for a second reason:
        # this monitor does not compute a TCP pose error, a cycle-time deviation
        # or an event-timing deviation at all — see cite_twin.divergence.
        if conditions.valid:
            message.joint_error_rms_rad = comparison.joint_error_rms_rad
            message.joint_error_max_rad = comparison.joint_error_max_rad
        message.tcp_position_error_m = 0.0
        message.tcp_orientation_error_rad = 0.0
        message.cycle_time_deviation_s = 0.0
        message.event_timing_deviation_s = 0.0

        # The condition terms, which the rule does NOT zero: they are how a
        # reader learns which conjunct failed (ADR-0050, 5c).
        message.plant_sample_age_s = _age(plant, now)
        message.counterpart_sample_age_s = _age(counterpart, now)
        message.plant_clock_deficit_s = UNMEASURED
        message.counterpart_clock_deficit_s = UNMEASURED
        # No deficit was measured, so there is no window it was measured over.
        # A reader tells that from the two deficits above rather than from this.
        message.window_s = 0.0
        message.far_side_physical = far_side_physical
        # The plant's, because that is the side this sample is published on. The
        # two disagreeing is exactly what term 4 reports, so the field carries
        # one of them rather than a merged string.
        message.model_version = versions.get(PLANT_SIDE, "")
        return message


def _age(operand: Operand | None, now: float) -> float:
    """How old an operand was at the comparison instant, or that it was absent."""
    if operand is None:
        return UNMEASURED
    return max(0.0, now - operand.received_wall_s)


def _aggregate(results: Mapping[str, ResultCode]) -> ResultCode:
    """One result for the operator, from one per side.

    Success only where every side succeeded. A cancellation outranks a failure
    because the operator asked for it and it is what happened; otherwise the
    first non-success in side order is reported, with the side named, so that
    "the twin failed" is never the whole of what a caller is told.
    """
    if not results:
        return ResultCode(
            code=ResultCode.PRECONDITION_FAILED, detail="no side evaluated the goal"
        )
    detail = "; ".join(
        f"{side}: {result.detail or _code_name(result.code)}"
        for side, result in sorted(results.items())
    )
    codes = {result.code for result in results.values()}
    if codes == {ResultCode.SUCCESS}:
        return ResultCode(code=ResultCode.SUCCESS, detail=detail)
    if ResultCode.CANCELLED in codes:
        return ResultCode(code=ResultCode.CANCELLED, detail=detail)
    for _side, result in sorted(results.items()):
        if result.code != ResultCode.SUCCESS:
            return ResultCode(code=result.code, detail=detail)
    return ResultCode(code=ResultCode.SUCCESS, detail=detail)


def _code_name(code: int) -> str:
    for name in dir(ResultCode):
        if name.isupper() and getattr(ResultCode, name) == code:
            return name
    return str(code)


def _mode_name(mode: int) -> str:
    return MODE_NAMES.get(mode, str(mode))


def _result_code_of(side_name: str, outcome) -> ResultCode:
    if outcome is None:
        return ResultCode(
            code=ResultCode.CANCELLED,
            detail=f"side {side_name!r} was still running when this goal ended",
        )
    result = getattr(outcome, "result", None)
    code = getattr(result, "result", None)
    if code is None:
        return ResultCode(
            code=ResultCode.EXECUTION_FAILED,
            detail=f"side {side_name!r} returned no ResultCode",
        )
    return code


def _wait(future: Future, goal_handle, handles) -> object | None:
    """Block until ``future`` completes, forwarding a cancel while waiting.

    The wait is on a `threading.Event` rather than a poll of the future, so
    nothing here sleeps for a guessed duration (P4). The cancel check is a poll,
    at a rate that only decides how quickly a cancel is forwarded, and it is
    reported to no consumer.
    """
    done = threading.Event()
    future.add_done_callback(lambda _future: done.set())
    forwarded = False
    while not done.wait(timeout=0.1):
        if goal_handle.is_cancel_requested and not forwarded:
            forwarded = True
            for handle in list(handles):
                handle.cancel_goal_async()
    return future.result()


def _skill_endpoints(plan: Plan) -> tuple[_SkillEndpoint, ...]:
    """Every skill L5 routes, derived from the plan and from nothing else."""
    endpoints: list[_SkillEndpoint] = []
    for manager in plan.controller_managers:
        if manager.skills is None:
            continue
        for field, action_type in SKILL_ACTION_TYPES.items():
            side_name = getattr(manager.skills, field)
            endpoints.append(
                _SkillEndpoint(
                    asset=manager.asset,
                    field=field,
                    action_type=action_type,
                    side_name=side_name,
                    endpoint=operator_endpoint(side_name),
                )
            )
    return tuple(endpoints)


def _refuse_sim_time(side: SideContext) -> None:
    """Refuse a side whose node was told to take its time from a simulator."""
    if side.node.get_parameter("use_sim_time").get_parameter_value().bool_value:
        raise BoundaryError(
            f"side {side.side.name!r} was started with use_sim_time, and L5 is the one "
            "component in this system that cannot honour it: it holds a context per "
            "side, the two sides' simulated clocks are independent and separate "
            "without bound (ADR-0043, ADR-0049), and ADR-0050 decision 3 pairs two "
            "operands on the WALL clock for exactly that reason."
        )


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    """Which zone, and which plan.

    `--plan` exists so a test can drive L5 against a plan that declares a
    counterpart WITHOUT editing L0. The shipped model declares
    `twin: {sides: single}` and ADR-0049 decision 4 keeps it there, so L5 cannot
    come up against the generated plan at all: it has one side, and a boundary
    needs two. It is not a second source of truth — the default is the generated
    plan and nothing but a test passes anything else.
    """
    parser = argparse.ArgumentParser(prog="cite_twin", description=__doc__)
    parser.add_argument("--zone", default="cell_a")
    parser.add_argument("--plan", default="")
    # ROS strips its own arguments before a node sees them; anything left that
    # this parser does not know about is ignored rather than fatal, because
    # `launch_ros` appends `--ros-args` unconditionally.
    known, _unknown = parser.parse_known_args(argv)
    return known


def main(argv: list[str] | None = None) -> int:
    """Bring the boundary up, or say why this deployment has no boundary to span."""
    arguments = _arguments(argv)
    environ = os.environ
    try:
        path = (
            Path(arguments.plan)
            if arguments.plan
            else default_plan_path(arguments.zone)
        )
        plan = load(path)
        base = domain_base(environ)
    except PlanError as error:
        print(f"cite_twin: {error}", file=sys.stderr)
        return 2

    boundary: TwinBoundary | None = None
    try:
        boundary = TwinBoundary(plan, base, environ)
        boundary.spin()
    except (PlanError, BoundaryError) as error:
        print(f"cite_twin: {error}", file=sys.stderr)
        return 2
    finally:
        if boundary is not None:
            boundary.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
