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

"""What L5 tells the operator when two sides answer, field by field.

**The defect this file exists to hold shut.** L5 used to build a fresh result,
set `.result`, and ship every other field at its type default — so a `Pick`
returning `SUCCESS` carried `holding=false`, which `Pick.action`'s own comment
calls *"impossible and would be a defect in the skill server"*, and a `Transfer`
returning `TIMEOUT` carried `still_holding=false`, which that action documents
as the upstream robot having released ownership. ADR-0046 refuses a retry on
custody and ADR-0038 decision 5 records what a retry begun with a wrong custody
belief does. The belief was not merely wrong: it was manufactured.

The second defect is in the same family. L5 discarded the goal STATUS and read
success out of a payload field whose default is `SUCCESS = 0`, and rclpy's
`ActionServer` catches an exception in an execute callback, **aborts the goal
and returns a default-constructed result** — so a far side that threw was
reported as a clean success.

No ROS runtime: the message types are imported, and every function under test
takes plain values.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from action_msgs.msg import GoalStatus
from cite_interfaces.action import Grasp, MoveTo, Pick, Place, Transfer
from cite_interfaces.msg import DivergenceMetrics, ResultCode, TwinMode
from cite_twin.boundary import (
    CUSTODY_FIELDS,
    IMPOSSIBLE_WHEN_FALSE_ON_SUCCESS,
    measurement_fields,
    SKILL_ACTION_TYPES,
)
from cite_twin.routing import COUNTERPART_SIDE, PLANT_SIDE
from cite_twin.twin_boundary import (
    _a_transition_may_not_outrun_the_cell,
    _aggregate,
    _compose_result,
    _outcome_of,
    _SideOutcome,
    _SkillEndpoint,
    _uncommanded_result,
    NOT_COMPUTED_FIELDS,
)
import pytest

BOTH = (PLANT_SIDE, COUNTERPART_SIDE)

#: The definition in the source tree, for a checkout that is not installed.
SOURCE_MESSAGE = (
    Path(__file__).resolve().parents[2]
    / "cite_interfaces/msg/DivergenceMetrics.msg"
)


def endpoint(field: str) -> _SkillEndpoint:
    action_type = SKILL_ACTION_TYPES[field]
    return _SkillEndpoint(
        asset="arm_1",
        field=field,
        action_type=action_type,
        side_name=f"/cite/cell_a/arm_1/{field}",
        endpoint=f"/cite/twin/cell_a/arm_1/{field}",
    )


def code(value: int, detail: str = "") -> ResultCode:
    return ResultCode(code=value, detail=detail)


def outcome(value: int, payload=None) -> _SideOutcome:
    return _SideOutcome(code=code(value), payload=payload)


class _Wrapped:
    """The shape `get_result_async()` resolves to: a status and a payload."""

    def __init__(self, status: int, result) -> None:
        self.status = status
        self.result = result


class TestTheCustodyRule:
    def test_success_never_ships_with_holding_false(self) -> None:
        """The assertion the reviewer asked for, over every side combination.

        A `Pick` result carrying `SUCCESS` and `holding=false` is the pair
        `Pick.action` calls impossible. L5 will not emit it in either
        direction: it does not invent custody, and it does not report a success
        it cannot justify.
        """
        for plant_holding in (True, False):
            for counterpart_holding in (True, False):
                composed = _compose_result(
                    endpoint("pick"),
                    BOTH,
                    {
                        PLANT_SIDE: outcome(
                            ResultCode.SUCCESS, Pick.Result(holding=plant_holding)
                        ),
                        COUNTERPART_SIDE: outcome(
                            ResultCode.SUCCESS,
                            Pick.Result(holding=counterpart_holding),
                        ),
                    },
                )
                assert not (
                    composed.result.code == ResultCode.SUCCESS
                    and not composed.holding
                ), (plant_holding, counterpart_holding)

    def test_a_successful_pick_reports_holding(self) -> None:
        composed = _compose_result(
            endpoint("pick"),
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.SUCCESS, Pick.Result(holding=True)),
                COUNTERPART_SIDE: outcome(
                    ResultCode.SUCCESS, Pick.Result(holding=True)
                ),
            },
        )
        assert composed.result.code == ResultCode.SUCCESS
        assert composed.holding

    def test_a_side_returning_success_with_no_custody_is_refused_not_laundered(
        self,
    ) -> None:
        """One side is defective; L5 says so rather than picking a belief."""
        composed = _compose_result(
            endpoint("pick"),
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.SUCCESS, Pick.Result(holding=False)),
                COUNTERPART_SIDE: outcome(
                    ResultCode.SUCCESS, Pick.Result(holding=False)
                ),
            },
        )
        assert composed.result.code == ResultCode.EXECUTION_FAILED
        assert "impossible" in composed.result.detail

    def test_custody_is_the_or_over_the_sides(self) -> None:
        """*Somebody is holding it* — never the default, never one side's answer."""
        composed = _compose_result(
            endpoint("pick"),
            BOTH,
            {
                PLANT_SIDE: outcome(
                    ResultCode.EXECUTION_FAILED, Pick.Result(holding=False)
                ),
                COUNTERPART_SIDE: outcome(
                    ResultCode.SUCCESS, Pick.Result(holding=True)
                ),
            },
        )
        assert composed.holding
        assert composed.result.code == ResultCode.EXECUTION_FAILED

    def test_a_dispatched_side_that_answered_nothing_counts_as_holding(self) -> None:
        """Unknown custody falls on the side that makes L4 escalate.

        ADR-0038 decision 5: the other direction opens the jaws at the home
        pose and drops a part no planner knows is held.
        """
        composed = _compose_result(
            endpoint("pick"),
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.SUCCESS, Pick.Result(holding=False)),
                COUNTERPART_SIDE: outcome(ResultCode.CANCELLED, None),
            },
        )
        assert composed.holding

    def test_a_transfer_that_timed_out_still_reports_the_piece_held(self) -> None:
        """`Transfer.action`: "true after a TIMEOUT — the upstream robot retains ownership"."""
        composed = _compose_result(
            endpoint("transfer"),
            BOTH,
            {
                PLANT_SIDE: outcome(
                    ResultCode.TIMEOUT, Transfer.Result(still_holding=True)
                ),
                COUNTERPART_SIDE: outcome(
                    ResultCode.TIMEOUT, Transfer.Result(still_holding=True)
                ),
            },
        )
        assert composed.result.code == ResultCode.TIMEOUT
        assert composed.still_holding

    def test_a_grasp_that_opened_may_report_no_hold_on_success(self) -> None:
        """`Grasp` is not `Pick`: an open command succeeds holding nothing."""
        composed = _compose_result(
            endpoint("grasp"),
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.SUCCESS, Grasp.Result(holding=False)),
                COUNTERPART_SIDE: outcome(
                    ResultCode.SUCCESS, Grasp.Result(holding=False)
                ),
            },
        )
        assert composed.result.code == ResultCode.SUCCESS
        assert not composed.holding

    def test_a_goal_no_side_was_sent_took_no_custody(self) -> None:
        """The one place a type default is justified, and why.

        Nothing was commanded, so this goal picked nothing up. That is a
        statement about the goal and not a claim that the gripper is empty.
        """
        result = _uncommanded_result(
            endpoint("pick"), code(ResultCode.PRECONDITION_FAILED, "in SIM")
        )
        assert not result.holding
        assert result.result.code == ResultCode.PRECONDITION_FAILED


class TestTheMeasurementRule:
    def test_a_measurement_is_the_plants_and_is_not_averaged(self) -> None:
        """Two arms reach two poses; their mean is a place neither arm went."""
        plant = MoveTo.Result(position_error_m=0.01)
        plant.reached.header.frame_id = "cite_world"
        counterpart = MoveTo.Result(position_error_m=0.90)
        counterpart.reached.header.frame_id = "somewhere_else"
        composed = _compose_result(
            endpoint("move_to"),
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.SUCCESS, plant),
                COUNTERPART_SIDE: outcome(ResultCode.SUCCESS, counterpart),
            },
        )
        assert composed.position_error_m == pytest.approx(0.01)
        assert composed.reached.header.frame_id == "cite_world"
        assert "measurements are the plant's" in composed.result.detail

    def test_no_measurement_is_carried_when_the_plant_answered_nothing(self) -> None:
        """The counterpart's number is never reported under the plant's name."""
        counterpart = MoveTo.Result(position_error_m=0.90)
        counterpart.reached.header.frame_id = "somewhere_else"
        composed = _compose_result(
            endpoint("move_to"),
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.PRECONDITION_FAILED, None),
                COUNTERPART_SIDE: outcome(ResultCode.SUCCESS, counterpart),
            },
        )
        assert composed.position_error_m == 0.0
        assert composed.reached.header.frame_id == ""
        assert "no measurement is carried" in composed.result.detail

    def test_every_result_field_is_classified(self) -> None:
        """No field of a routed result is left for a default to answer."""
        for field, action_type in SKILL_ACTION_TYPES.items():
            names = set(action_type.Result.get_fields_and_field_types())
            classified = (
                {"result"}
                | set(CUSTODY_FIELDS[field])
                | set(measurement_fields(field, action_type))
            )
            assert names == classified, field

    def test_a_boolean_result_field_is_custody_or_the_import_fails(self) -> None:
        """The guard's own assertion, restated where a reader will meet it."""
        for field, action_type in SKILL_ACTION_TYPES.items():
            booleans = {
                name
                for name, kind in action_type.Result.get_fields_and_field_types().items()
                if kind == "boolean"
            }
            assert booleans == set(CUSTODY_FIELDS[field]), field

    def test_only_pick_declares_the_impossible_pair(self) -> None:
        assert set(IMPOSSIBLE_WHEN_FALSE_ON_SUCCESS) == {"pick"}
        assert Place.Result().get_fields_and_field_types()


class TestReadingOneSidesAnswer:
    def test_an_abort_with_an_unset_code_is_not_a_success(self) -> None:
        """Read an abort as an abort, which is the branch this revived.

        rclpy aborts a goal whose execute callback raised and returns a
        default-constructed result. `ResultCode.SUCCESS` is 0, so the payload
        alone said "fine".
        """
        answer = _outcome_of(
            PLANT_SIDE, _Wrapped(GoalStatus.STATUS_ABORTED, MoveTo.Result())
        )
        assert answer.code.code == ResultCode.EXECUTION_FAILED
        assert "uncaught exception" in answer.code.detail

    def test_an_abort_carrying_a_code_keeps_that_code(self) -> None:
        """`MOTION_INTERRUPTED` must reach L4 as itself (ADR-0037)."""
        payload = MoveTo.Result()
        payload.result = code(ResultCode.MOTION_INTERRUPTED, "stopped part-way")
        answer = _outcome_of(
            PLANT_SIDE, _Wrapped(GoalStatus.STATUS_ABORTED, payload)
        )
        assert answer.code.code == ResultCode.MOTION_INTERRUPTED

    def test_a_cancelled_status_is_a_cancellation_whatever_the_payload_says(
        self,
    ) -> None:
        answer = _outcome_of(
            PLANT_SIDE, _Wrapped(GoalStatus.STATUS_CANCELED, MoveTo.Result())
        )
        assert answer.code.code == ResultCode.CANCELLED

    def test_a_succeeded_status_carries_the_payloads_code(self) -> None:
        payload = MoveTo.Result()
        payload.result = code(ResultCode.SUCCESS, "arrived")
        answer = _outcome_of(
            PLANT_SIDE, _Wrapped(GoalStatus.STATUS_SUCCEEDED, payload)
        )
        assert answer.code.code == ResultCode.SUCCESS
        assert answer.payload is payload

    def test_a_missing_payload_is_a_failure_and_not_a_default(self) -> None:
        answer = _outcome_of(PLANT_SIDE, _Wrapped(GoalStatus.STATUS_ABORTED, None))
        assert answer.code.code == ResultCode.EXECUTION_FAILED
        assert "no ResultCode" in answer.code.detail

    def test_no_result_at_all_is_reported_as_such(self) -> None:
        answer = _outcome_of(COUNTERPART_SIDE, None)
        assert answer.code.code == ResultCode.CANCELLED
        assert answer.payload is None


class TestTheAggregateRanking:
    """Ranked by consequence, and the ranking is stated in one table."""

    def test_success_requires_every_side(self) -> None:
        assert (
            _aggregate(
                BOTH,
                {
                    PLANT_SIDE: outcome(ResultCode.SUCCESS),
                    COUNTERPART_SIDE: outcome(ResultCode.SUCCESS),
                },
            ).code
            == ResultCode.SUCCESS
        )

    def test_an_interrupted_arm_outranks_a_cancellation(self) -> None:
        """**S-05.** ADR-0037's `ESCALATE` row must not be reported as a tidy stop.

        The far side stopped part-way and is holding position; the near side was
        cancelled. Under the old rule the operator was told the goal was
        cancelled cleanly.
        """
        aggregate = _aggregate(
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.CANCELLED),
                COUNTERPART_SIDE: outcome(ResultCode.MOTION_INTERRUPTED),
            },
        )
        assert aggregate.code == ResultCode.MOTION_INTERRUPTED

    def test_a_safety_refusal_outranks_everything(self) -> None:
        aggregate = _aggregate(
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.MOTION_INTERRUPTED),
                COUNTERPART_SIDE: outcome(ResultCode.SAFETY_BLOCKED),
            },
        )
        assert aggregate.code == ResultCode.SAFETY_BLOCKED

    def test_a_hardware_fault_outranks_an_interrupted_arm(self) -> None:
        aggregate = _aggregate(
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.MOTION_INTERRUPTED),
                COUNTERPART_SIDE: outcome(ResultCode.HARDWARE_FAULT),
            },
        )
        assert aggregate.code == ResultCode.HARDWARE_FAULT

    def test_a_cancellation_is_reported_when_nothing_worse_happened(self) -> None:
        aggregate = _aggregate(
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.CANCELLED),
                COUNTERPART_SIDE: outcome(ResultCode.SUCCESS),
            },
        )
        assert aggregate.code == ResultCode.CANCELLED

    def test_a_code_the_ranking_does_not_know_is_reported_ahead_of_it(self) -> None:
        """An unweighed answer is not thereby a mild one."""
        aggregate = _aggregate(
            BOTH,
            {
                PLANT_SIDE: outcome(ResultCode.CANCELLED),
                COUNTERPART_SIDE: outcome(200),
            },
        )
        assert aggregate.code == 200

    def test_the_fallback_order_is_the_routes_and_not_the_alphabet(self) -> None:
        """**R-10.** `sorted()` put `counterpart` ahead of `plant` for no reason.

        Two unranked codes, one per side: the side the route names first is the
        one reported, and the plant is first because the operator is on it.
        """
        aggregate = _aggregate(
            BOTH,
            {PLANT_SIDE: outcome(201), COUNTERPART_SIDE: outcome(202)},
        )
        assert aggregate.code == 201
        assert aggregate.detail.index("plant") < aggregate.detail.index("counterpart")

    def test_every_side_is_named_in_the_detail(self) -> None:
        aggregate = _aggregate(
            BOTH,
            {
                PLANT_SIDE: _SideOutcome(
                    code=code(ResultCode.SUCCESS, "arrived"), payload=None
                ),
                COUNTERPART_SIDE: _SideOutcome(
                    code=code(ResultCode.EXECUTION_FAILED, "did not"), payload=None
                ),
            },
        )
        assert "plant: arrived" in aggregate.detail
        assert "counterpart: did not" in aggregate.detail

    def test_no_side_at_all_is_a_precondition_failure(self) -> None:
        assert _aggregate(BOTH, {}).code == ResultCode.PRECONDITION_FAILED


class TestATransitionMayNotOutrunTheCell:
    """**S-06.** The mode must not be published ahead of the state it describes.

    A transition touched nothing in flight, so `/cite/twin/mode` could publish
    `SIM` — `TwinMode.msg`: *"physical idle, virtual commanded"* — while a
    physical arm was mid-motion under L5's own command.
    """

    def test_a_transition_is_refused_while_a_goal_is_outstanding(self) -> None:
        verdict = _a_transition_may_not_outrun_the_cell(
            TwinMode.MODE_VIRTUAL_LEAD,
            TwinMode.MODE_SIM,
            ["/cite/twin/cell_a/arm_1/pick"],
        )
        assert not verdict.accepted
        assert verdict.code == ResultCode.PRECONDITION_FAILED

    def test_the_refusal_names_the_goals(self) -> None:
        """A refusal an operator cannot act on is a refusal they will force."""
        verdict = _a_transition_may_not_outrun_the_cell(
            TwinMode.MODE_VALIDATED,
            TwinMode.MODE_SIM,
            ["/cite/twin/cell_a/arm_1/pick", "/cite/twin/cell_a/arm_3/move_to"],
        )
        assert "/cite/twin/cell_a/arm_1/pick" in verdict.detail
        assert "/cite/twin/cell_a/arm_3/move_to" in verdict.detail
        assert "cancel" in verdict.detail

    def test_the_mode_does_not_move(self) -> None:
        verdict = _a_transition_may_not_outrun_the_cell(
            TwinMode.MODE_VALIDATED, TwinMode.MODE_SIM, ["/cite/twin/x"]
        )
        assert verdict.mode == TwinMode.MODE_VALIDATED
        assert not verdict.commands_hardware


class TestTheFieldsNothingComputes:
    """**S-07.** A zero is a measurement of zero, and these were never measured."""

    def test_the_four_are_named_and_are_not_the_two_that_are_computed(self) -> None:
        assert set(NOT_COMPUTED_FIELDS) == {
            "tcp_position_error_m",
            "tcp_orientation_error_rad",
            "cycle_time_deviation_s",
            "event_timing_deviation_s",
        }
        assert "joint_error_rms_rad" not in NOT_COMPUTED_FIELDS
        assert "joint_error_max_rad" not in NOT_COMPUTED_FIELDS

    def test_every_one_of_them_is_a_field_of_the_message(self) -> None:
        declared = DivergenceMetrics.get_fields_and_field_types()
        for field in NOT_COMPUTED_FIELDS:
            assert declared[field] == "double", field

    def test_the_message_declares_the_marker_where_a_consumer_will_read_it(
        self,
    ) -> None:
        """`ros2 interface show` returns the comments, and L6 records beside them.

        The README said it and the contract did not, which is the half a
        consumer never sees.
        """
        text = (
            Path(inspect.getfile(DivergenceMetrics))
            .resolve()
            .parents[3]
            .joinpath("share/cite_interfaces/msg/DivergenceMetrics.msg")
        )
        if not text.is_file():  # pragma: no cover - source checkout, not installed
            text = SOURCE_MESSAGE
        body = text.read_text()
        assert "NaN" in body
        assert "NOT COMPUTED AT ALL" in body
