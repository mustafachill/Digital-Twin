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
import math
import os
from pathlib import Path
import sys
import threading
import time

from action_msgs.msg import GoalStatus
from cite_bringup.plan import (
    default_plan_path,
    domain_base,
    load,
    Plan,
    PlanError,
    require_hardware_opt_in,
)
from cite_facility import model_info
from cite_interfaces.msg import DivergenceMetrics, ModelVersion, ResultCode, TwinMode
from cite_interfaces.qos import LATCHED, STATE
from cite_interfaces.srv import SetMode
from cite_runtime.runtime import caused_by_shutdown, SHUTDOWN_EXCEPTIONS
from cite_twin.boundary import (
    address,
    BoundaryError,
    CUSTODY_FIELDS,
    IMPOSSIBLE_WHEN_FALSE_ON_SUCCESS,
    measurement_fields,
    off_executor,
    operator_endpoint,
    SideContext,
    SKILL_ACTION_TYPES,
)
from cite_twin.divergence import assess, compare, Operand, UNMEASURED
from cite_twin.mode import (
    Deployment,
    MODE_NAMES,
    ModeAuthority,
    SIMULATION_BACKEND,
    Verdict,
)
from cite_twin.routing import (
    COUNTERPART_SIDE,
    PLANT_SIDE,
    reverse_state_flow,
    route,
)
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.task import Future
from sensor_msgs.msg import JointState

#: How long L5 waits for a side's L3 action server to appear before it reports
#: that the goal cannot be dispatched, in seconds of the WALL clock.
#:
#: A discovery wait and never a motion wait, which is what makes a wall-clock
#: ceiling defensible here: nothing bounded by this number is executed by a
#: simulator, so ADR-0045's defect — a wall-clock deadline supervising a
#: simulation-time process — is the one this is not.
#:
#: **It is a poll and not a graph event, and this comment said otherwise until
#: 2026-08-31.** `rclpy`'s `ActionClient.wait_for_server` loops on
#: `server_is_ready()` with `time.sleep(0.25)` between attempts
#: (`rclpy/action/client.py`), so a server that appears is noticed within a
#: quarter of a second rather than instantly. Nothing here is sequenced on that
#: quarter second — it decides only how quickly a goal that could already have
#: been sent is sent — but a comment claiming an event where the upstream code
#: sleeps is the kind of claim this project has been wrong about before.
SERVER_WAIT_S = 30.0

#: **How one operator result is ranked out of one result per side, worst first.**
#:
#: Ranked by CONSEQUENCE, and every row carries the reason it sits where it
#: does. The rule this replaced was "a cancellation outranks a failure, then the
#: first non-success in side order", which meant that a far side reporting
#: `MOTION_INTERRUPTED` — ADR-0037's `ESCALATE` row, *an arm stopped part-way
#: and is holding position* — was reported to the operator as a goal cancelled
#: cleanly, whenever any side had also been cancelled. The worse fact about the
#: cell won.
#:
#: 1. `SAFETY_BLOCKED` — a side refused on safety. Nothing may outrank a safety
#:    refusal; it is the one answer that must never be summarised away.
#: 2. `HARDWARE_FAULT` — a machine is faulted and needs a person.
#: 3. `MOTION_INTERRUPTED` — an arm is stopped part-way, holding position, for a
#:    reason nothing established (ADR-0037). It outranks `CANCELLED`
#:    deliberately: a cancel that left an arm mid-path is that arm, not a tidy
#:    stop, and L4's policy row for it is `ESCALATE`.
#: 4. `HARDWARE`-adjacent execution failures — `EXECUTION_FAILED`,
#:    `PLANNING_FAILED`, `UNREACHABLE`: the goal did not happen and the arm is
#:    at an endpoint. Ranked under `MOTION_INTERRUPTED` because ADR-0037's whole
#:    point is that the two want different answers from L4.
#: 5. `PRECONDITION_FAILED`, `NOT_IMPLEMENTED` — the goal never started.
#: 6. `TIMEOUT` — bounded, with a defined outcome, and the outcome is in the
#:    custody fields rather than here.
#: 7. `CANCELLED` — the operator asked for it, so it is reported only when
#:    nothing worse also happened.
#:
#: `SUCCESS` is not in the table: it is reported only when EVERY side succeeded,
#: which is a conjunction rather than a rank.
AGGREGATE_RANKING: tuple[int, ...] = (
    ResultCode.SAFETY_BLOCKED,
    ResultCode.HARDWARE_FAULT,
    ResultCode.MOTION_INTERRUPTED,
    ResultCode.EXECUTION_FAILED,
    ResultCode.PLANNING_FAILED,
    ResultCode.UNREACHABLE,
    ResultCode.PRECONDITION_FAILED,
    ResultCode.NOT_IMPLEMENTED,
    ResultCode.TIMEOUT,
    ResultCode.CANCELLED,
)

#: The comparison fields no producer in this tree computes.
#:
#: Published as NaN rather than as zero, in every sample. `DivergenceMetrics.msg`
#: declares the marker; the reason it is not zero is that zero is a measurement
#: of zero and these were never measured at all. A reader plotting a series of
#: them gets a hole, which is the truth, instead of a flat line at the origin,
#: which is a claim.
#:
#: What would delete this list: a TCP pose error needs one TF buffer per side
#: (ADR-0050 clause 1c) and forward kinematics for each; the two timing
#: deviations need L4 line state from both sides. Neither exists here.
NOT_COMPUTED_FIELDS: tuple[str, ...] = (
    "tcp_position_error_m",
    "tcp_orientation_error_rad",
    "cycle_time_deviation_s",
    "event_timing_deviation_s",
)

#: How often a divergence sample is published, per asset, in seconds.
#:
#: A publication rate rather than a timing guess: nothing is sequenced on it and
#: no state transition waits for it (P4). It is a node parameter so a deployment
#: can change it without a rebuild.
DIVERGENCE_PERIOD_S = 1.0


@dataclass(frozen=True)
class _SideOutcome:
    """What one side answered: the code, and the typed result behind it.

    The payload is kept rather than reduced to a code, because the fields that
    are not the code are the ones L5 has to decide about — custody above all.
    `None` means the side produced no result message at all, which is not the
    same as a result whose code is a failure and must not be flattened into
    one.
    """

    code: ResultCode
    payload: object | None


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
        #
        # Built one at a time and released on the way out, because the refusal
        # is the COMMON case on this repository's own model: it ships
        # `twin: {sides: single}`, so every ordinary run of L5 reaches the
        # second `address()` call and raises. Constructing both in one literal
        # left the plant's `rclpy` context initialised with no reference to it
        # anywhere — `main`'s `finally` only stops a boundary that finished
        # constructing — and the process then exited with a live context.
        self._sides: dict[str, SideContext] = {}
        try:
            for name in (PLANT_SIDE, COUNTERPART_SIDE):
                self._sides[name] = SideContext(address(plan, name, base))
                _refuse_sim_time(self._sides[name])
        except BaseException:  # noqa: B036
            self.stop()
            raise
        self._plant = self._sides[PLANT_SIDE]
        self._counterpart = self._sides[COUNTERPART_SIDE]

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
        # Both sides, read per asset, because the hardware gate asks which
        # sides the requested mode commands and what each of them loads -
        # never which mode it is (see cite_twin.mode).
        self._authority = ModeAuthority(
            Deployment(
                {
                    manager.asset: {
                        PLANT_SIDE: manager.backend,
                        COUNTERPART_SIDE: manager.counterpart_backend,
                    }
                    for manager in plan.controller_managers
                }
            ),
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

        #: Every goal L5 has dispatched and not yet finished, by the endpoint
        #: it entered on. Read by the mode server, which refuses a transition
        #: while any of them is outstanding (S-06).
        self._in_flight: dict[tuple[str, bytes], str] = {}

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
                # The plan's own name. Composing it here would be the second
                # place it is written, and a rename would leave this monitor
                # reporting UNMEASURED forever while looking correct.
                topic = manager.joint_state_topic
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
            outstanding = sorted(self._in_flight.values())
            if outstanding and request.mode != before:
                verdict = _a_transition_may_not_outrun_the_cell(
                    before, request.mode, outstanding
                )
            else:
                verdict = self._authority.request(
                    request.mode, "", request.reason, request.force
                )
            changed = verdict.accepted and verdict.mode != before
            if changed:
                # A far-side operand recorded under the old mode is not an
                # operand under the new one: whether a side's state crosses at
                # all is a property of the mode (ADR-0050 decision 1b), so one
                # kept across a transition would be a sample the new mode says
                # cannot exist, ageing quietly rather than being absent.
                for key in [
                    key for key in self._operands if key[0] != PLANT_SIDE
                ]:
                    del self._operands[key]
                self._publish_mode()

        response.accepted = verdict.accepted
        response.result = ResultCode(code=verdict.code, detail=verdict.detail)
        response.current_mode = verdict.mode
        # Two call sites rather than one and a chosen method: rclpy memoises a
        # logger by CALL SITE and raises `Logger severity cannot be changed
        # between calls` when one line logs at two severities. It killed this
        # process the first time a transition was refused.
        line = f"SetMode({_mode_name(request.mode)}): {verdict.detail}"
        if verdict.accepted:
            self._log.info(line)
        else:
            self._log.warning(line)
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

    async def _execute(self, skill: _SkillEndpoint, goal_handle):
        """Run one operator goal, off the executor, and return its result.

        **A coroutine, and the `await` is the point.** Everything this goal does
        is blocking and unbounded — see :meth:`_await_far_side_goals` — so it
        runs on a thread of L5's own and this callback yields the executor
        thread back to the pool for the duration. The cancel that bounds the
        goal is served by that pool, so it must never be queued behind the goal
        it bounds (`cite_twin.boundary.off_executor`).
        """
        return await off_executor(
            self._plant.executor,
            partial(self._run_goal, skill, goal_handle),
            name=f"twin-goal-{skill.asset}-{skill.field}",
        )

    def _run_goal(self, skill: _SkillEndpoint, goal_handle):
        """Dispatch one operator goal to the sides the mode routes it to.

        Runs on its own thread, never on an executor thread.

        **Every refusal is an ABORT carrying a `ResultCode`, never a goal
        rejection.** A rejected goal carries no result, so a caller learns that
        the twin said no and never learns why; every L3 result in this project
        is typed and this one is too (P3).
        """
        # Read and registered under ONE acquisition, so that a transition
        # cannot slip between them: either this goal is outstanding when the
        # mode server looks, and the transition is refused, or the mode has
        # already moved and this goal reads the new one.
        key = (skill.endpoint, bytes(goal_handle.goal_id.uuid))
        with self._lock:
            mode = self._authority.mode
            chosen = route(mode)
            if chosen.accepted:
                self._in_flight[key] = skill.endpoint
        try:
            return self._run_dispatched_goal(skill, goal_handle, mode, chosen)
        finally:
            with self._lock:
                self._in_flight.pop(key, None)

    def _run_dispatched_goal(
        self, skill: _SkillEndpoint, goal_handle, mode: int, chosen
    ):
        """Run the body of one goal, with the goal already registered as in flight.

        Split out so that the registration above has exactly one exit — the
        `finally` — and cannot be left behind by a return added later. A goal
        that stayed registered would refuse every mode transition for the life
        of the process.
        """
        if not chosen.accepted:
            self._log.warning(
                f"{skill.endpoint} refused in {MODE_NAMES.get(mode, mode)}: {chosen.detail}"
            )
            goal_handle.abort()
            return _uncommanded_result(
                skill, ResultCode(code=chosen.code, detail=chosen.detail)
            )

        # Asked between acceptance and the far-side wait, because there is a
        # wait in between: `wait_for_server` can take SERVER_WAIT_S, and a goal
        # cancelled inside that window used to be dispatched anyway and then
        # cancelled mid-motion — an arm that moved because nobody asked the
        # question. Nothing was commanded, so custody is unchanged.
        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            return _uncommanded_result(
                skill,
                ResultCode(
                    code=ResultCode.CANCELLED,
                    detail=(
                        "cancelled after acceptance and before any side was "
                        "commanded; no goal was dispatched."
                    ),
                ),
            )

        dispatched = self._dispatch(skill, goal_handle, chosen.sides)
        if isinstance(dispatched, ResultCode):
            goal_handle.abort()
            return _uncommanded_result(skill, dispatched)

        outcomes = self._await_far_side_goals(dispatched, goal_handle)
        result = _compose_result(skill, chosen.sides, outcomes)
        if result.result.code == ResultCode.SUCCESS:
            goal_handle.succeed()
        elif result.result.code == ResultCode.CANCELLED:
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

    def _await_far_side_goals(
        self, sent: Mapping[str, Future], goal_handle
    ) -> dict[str, _SideOutcome]:
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
        outcomes: dict[str, _SideOutcome] = {}
        for side_name, future in sent.items():
            handle = _wait(future, goal_handle, handles.values())
            if handle is None or not handle.accepted:
                outcomes[side_name] = _SideOutcome(
                    code=ResultCode(
                        code=ResultCode.PRECONDITION_FAILED,
                        detail=f"side {side_name!r} rejected the goal",
                    ),
                    payload=None,
                )
                continue
            handles[side_name] = handle

        for side_name, handle in handles.items():
            future = handle.get_result_async()
            outcomes[side_name] = _outcome_of(
                side_name, _wait(future, goal_handle, handles.values())
            )

        return outcomes

    # ------------------------------------------------------------------ #
    # 3. The divergence monitor
    # ------------------------------------------------------------------ #

    def _on_joint_state(self, side_name: str, asset: str, message: JointState) -> None:
        """Record one side's operand, timestamped ON ARRIVAL by L5's own clock.

        **Consumed only where the mode has a reverse state flow for that side**
        (`cite_twin.routing.reverse_state_flow`), which is the production caller
        that function did not have. The subscription exists in every mode
        because it is created once at start-up, and a message it delivers in a
        mode with no reverse flow is dropped here rather than becoming an
        operand — otherwise L5 would hold a far-side state in `VIRTUAL_LEAD`,
        which is the one mode DEFINED by there being none, and the module that
        says "L5 may not quietly open a reverse state flow" would be
        contradicted by the node that imports it.

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
            if side_name != PLANT_SIDE and side_name not in reverse_state_flow(
                self._authority.mode
            ):
                return
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

        # The zeroing rule, applied to the two comparison fields this monitor
        # computes. `valid` false zeroes them; that is ADR-0050 decision 5c.
        if conditions.valid:
            message.joint_error_rms_rad = comparison.joint_error_rms_rad
            message.joint_error_max_rad = comparison.joint_error_max_rad

        # **NOT ZERO: NOT COMPUTED.** Nothing in this tree computes a TCP pose
        # error, a cycle-time deviation or an event-timing deviation — see
        # `cite_twin.divergence.Comparison`. Zero is a measurement of zero, and
        # it is the strongest claim these fields can carry; it was being
        # published for four fields no instrument had touched. The day term 3
        # gains an instrument and `valid` turns true, a zero here would have
        # become a fidelity number nobody measured.
        #
        # NaN is the marker, declared in `DivergenceMetrics.msg`. It is not the
        # zeroing rule and does not replace it: the rule says what an INVALID
        # sample carries, and this says what an UNCOMPUTED field carries, in
        # every sample either way.
        for field in NOT_COMPUTED_FIELDS:
            setattr(message, field, math.nan)

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
        # Whether L5 is still watching the far side at all, which the ages
        # above cannot say: an operand that never arrives and an observer that
        # died look identical in a timestamp.
        message.counterpart_observed = self._counterpart.observing
        # The plant's, because that is the side this sample is published on. The
        # two disagreeing is exactly what term 4 reports, so the field carries
        # one of them rather than a merged string.
        message.model_version = versions.get(PLANT_SIDE, "")
        return message


def _a_transition_may_not_outrun_the_cell(
    current: int, requested: int, outstanding: tuple[str, ...] | list[str]
) -> Verdict:
    """Refuse a transition while L5 still has goals it dispatched in flight.

    **The mode must not be published ahead of the state it describes.** A
    transition touched nothing in flight, so `/cite/twin/mode` could publish
    `SIM` — `TwinMode.msg`: *"physical idle, virtual commanded"* — while a
    physical arm was mid-motion under L5's own command, and every consumer of
    that topic would have been told the cell was idle.

    Refused rather than answered by cancelling. Cancelling is motion policy and
    L5 is not the layer that decides what an arm does; the operator's cancel
    already reaches every side through the goal that is outstanding, and this
    refusal names the goals so that the operator knows which ones. It is
    evaluated BEFORE `ModeAuthority` is consulted, so no value of `force`
    reaches it — a forced transition here would be a forced lie on a topic
    whose readers cannot check it.
    """
    named = ", ".join(outstanding)
    return Verdict(
        accepted=False,
        mode=current,
        code=ResultCode.PRECONDITION_FAILED,
        detail=(
            f"{MODE_NAMES.get(requested, requested)} describes a cell in which "
            f"{len(outstanding)} goal(s) L5 dispatched are still running "
            f"({named}). Publishing the new mode now would describe a state the "
            "cell is not in - cancel those goals and ask again."
        ),
        commands_hardware=False,
    )


def _age(operand: Operand | None, now: float) -> float:
    """How old an operand was at the comparison instant, or that it was absent."""
    if operand is None:
        return UNMEASURED
    return max(0.0, now - operand.received_wall_s)


def _aggregate(
    order: tuple[str, ...], outcomes: Mapping[str, _SideOutcome]
) -> ResultCode:
    """One result for the operator, from one per side.

    Success only where every side succeeded. Otherwise the worst consequence in
    :data:`AGGREGATE_RANKING` is reported, with every side named in `detail`, so
    that "the twin failed" is never the whole of what a caller is told.

    A code no rank knows about is reported ahead of everything ranked rather
    than behind it: an answer this function has not been taught to weigh is not
    thereby a mild one, and reporting it is how the omission is noticed.

    ``order`` is the route's own tuple. A code outside the ranking is broken by
    that order and never alphabetically — sorting side names put `counterpart`
    ahead of `plant` for no reason anybody chose.
    """
    if not outcomes:
        return ResultCode(
            code=ResultCode.PRECONDITION_FAILED, detail="no side evaluated the goal"
        )
    ordered = [side for side in order if side in outcomes]
    ordered += [side for side in outcomes if side not in ordered]
    detail = "; ".join(
        f"{side}: {outcomes[side].code.detail or _code_name(outcomes[side].code.code)}"
        for side in ordered
    )
    codes = [outcomes[side].code.code for side in ordered]
    if set(codes) == {ResultCode.SUCCESS}:
        return ResultCode(code=ResultCode.SUCCESS, detail=detail)
    unranked = [
        code
        for code in codes
        if code != ResultCode.SUCCESS and code not in AGGREGATE_RANKING
    ]
    if unranked:
        return ResultCode(code=unranked[0], detail=detail)
    for ranked in AGGREGATE_RANKING:
        if ranked in codes:
            return ResultCode(code=ranked, detail=detail)
    return ResultCode(code=ResultCode.SUCCESS, detail=detail)


def _uncommanded_result(skill: _SkillEndpoint, code: ResultCode):
    """Return the result for a goal no side was ever sent.

    Every field but the code stays at its default, and that is justified here
    and only here: this goal commanded nothing, so it took no custody and
    produced no measurement. `holding=false` after such a refusal is a statement
    about THIS goal — it did not pick anything up — and not a claim that the
    gripper is empty, which L5 has no way to know and does not make.
    """
    result = skill.action_type.Result()
    result.result = code
    return result


def _compose_result(
    skill: _SkillEndpoint, order: tuple[str, ...], outcomes: Mapping[str, _SideOutcome]
):
    """Build the operator's result from one result per side, field by field.

    **The rule, and it is applied per field rather than per message.**

    * The code is :func:`_aggregate`'s.
    * A CUSTODY field is the logical OR over the dispatched sides — *somebody is
      holding it* — with a side that returned no result counting as holding.
      Never the type default: ADR-0038 decision 5 and ADR-0046 both key on this
      bit, and in 2.B the gripper is physical.
    * A MEASUREMENT field is one side's number and is not aggregable, so the
      plant's is forwarded whole (ADR-0044 clause 5) and the `detail` says so.
      Where the plant returned nothing, none is forwarded and the `detail` says
      that instead — a `PoseStamped` with an empty `frame_id` is the one signal
      the typed contract offers for "not measured", and inventing the
      counterpart's number under the plant's name would be worse than none.
    """
    aggregate = _aggregate(order, outcomes)
    result = skill.action_type.Result()

    for field in CUSTODY_FIELDS.get(skill.field, ()):
        held = [
            True if outcomes[side].payload is None
            else bool(getattr(outcomes[side].payload, field))
            for side in order
            if side in outcomes
        ]
        if (
            aggregate.code == ResultCode.SUCCESS
            and not any(held)
            and field in IMPOSSIBLE_WHEN_FALSE_ON_SUCCESS.get(skill.field, ())
        ):
            # Every side said it succeeded and none of them says it is holding
            # the piece. `Pick.action` calls that pair impossible, so one side
            # is defective, and L5 laundering it in EITHER direction would ship
            # a custody belief nobody measured. It reports the contradiction.
            aggregate = ResultCode(
                code=ResultCode.EXECUTION_FAILED,
                detail=(
                    f"a side returned SUCCESS with {field}=false, which "
                    f"{skill.action_type.__name__}.action calls impossible and a defect "
                    f"in the skill server; L5 will not report it as a success. "
                    f"{aggregate.detail}"
                ),
            )
        setattr(result, field, any(held))

    source = outcomes.get(PLANT_SIDE)
    measurements = measurement_fields(skill.field, skill.action_type)
    if source is not None and source.payload is not None:
        for field in measurements:
            setattr(result, field, getattr(source.payload, field))
        carried = f"measurements are the {PLANT_SIDE}'s"
    else:
        carried = (
            f"no measurement is carried: the {PLANT_SIDE} returned no result, and "
            "one side's number may not be reported under the other's name"
        )
    result.result = ResultCode(
        code=aggregate.code,
        detail=f"{aggregate.detail} [{carried}: {', '.join(measurements) or 'none'}]",
    )
    return result


def _code_name(code: int) -> str:
    for name in dir(ResultCode):
        if name.isupper() and getattr(ResultCode, name) == code:
            return name
    return str(code)


def _mode_name(mode: int) -> str:
    return MODE_NAMES.get(mode, str(mode))


def _outcome_of(side_name: str, outcome) -> _SideOutcome:
    """Read one side's answer, from the goal STATUS first and the payload second.

    **The status is the authority on whether the goal succeeded**, and until
    2026-08-31 this function discarded it and read success out of a payload
    field whose default is `SUCCESS = 0`. rclpy's `ActionServer` catches an
    exception raised in an execute callback, **aborts the goal and returns a
    default-constructed result** — so a far side that threw was reported to the
    operator as a clean success, with `holding=false` beside it.

    The payload is still read, because it is where this project's own vocabulary
    lives: an abort carrying `MOTION_INTERRUPTED` must reach L4 as that and not
    as a generic failure (ADR-0037).
    """
    if outcome is None:
        return _SideOutcome(
            code=ResultCode(
                code=ResultCode.CANCELLED,
                detail=f"side {side_name!r} was still running when this goal ended",
            ),
            payload=None,
        )
    payload = getattr(outcome, "result", None)
    code = getattr(payload, "result", None)
    status = getattr(outcome, "status", GoalStatus.STATUS_UNKNOWN)

    if status == GoalStatus.STATUS_CANCELED:
        return _SideOutcome(
            code=ResultCode(
                code=ResultCode.CANCELLED,
                detail=f"side {side_name!r} cancelled the goal",
            ),
            payload=payload,
        )
    if code is None:
        # Revived by the status check above: while success was read out of the
        # payload alone, this branch was unreachable, because a missing payload
        # produced code 0 and read as SUCCESS.
        return _SideOutcome(
            code=ResultCode(
                code=ResultCode.EXECUTION_FAILED,
                detail=f"side {side_name!r} returned no ResultCode",
            ),
            payload=payload,
        )
    if status == GoalStatus.STATUS_SUCCEEDED:
        return _SideOutcome(code=code, payload=payload)
    if code.code != ResultCode.SUCCESS:
        return _SideOutcome(code=code, payload=payload)
    # Aborted, or a status nothing here knows about, with a payload that says
    # SUCCESS. The status wins: a default-constructed result is what an
    # uncaught exception in an execute callback produces.
    return _SideOutcome(
        code=ResultCode(
            code=ResultCode.EXECUTION_FAILED,
            detail=(
                f"side {side_name!r} ended in goal status {status} carrying no "
                "ResultCode of its own; a default-constructed result is what an "
                "uncaught exception in an execute callback returns."
            ),
        ),
        payload=payload,
    )


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
