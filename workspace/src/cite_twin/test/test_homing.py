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

"""Homing to the program's start through the twin (ADR-0070).

Two things the boundary adds for it, and nothing else. `SetMode.homing` lets
VALIDATED be entered while a physical carriage stands away from the plant's -
the homing move is what brings them together - and bypasses ONLY that refusal:
not the hardware gate, not the physical side's readiness, and never a request
that does not ask for it. `JointsAt` measures the start on every side. Pure
logic and fakes: no graph, no robot.
"""

from __future__ import annotations

import threading
import time

from cite_interfaces.msg import ResultCode, TwinMode
from cite_interfaces.srv import JointsAt
from cite_twin.joints_at import joints_at
from cite_twin.mode import Deployment, ModeAuthority
from cite_twin.twin_boundary import TwinBoundary
import pytest

from test_physical_readiness import _boundary_with_carriages, _ready_watch, AGE

JOINTS = ("picker_joint1", "picker_joint2")


def _authority(boundary: TwinBoundary, opt_in=lambda: None) -> ModeAuthority:
    return ModeAuthority(
        Deployment.paired({"picker": True}),
        opt_in,
        physical_side_unready=boundary._physical_side_unready,
        physical_carriage_apart=boundary._physical_carriage_apart,
    )


def test_homing_enters_validated_with_the_carriages_apart() -> None:
    boundary = _boundary_with_carriages(0.0, 0.30)
    verdict = _authority(boundary).request(
        TwinMode.MODE_VALIDATED, "", "homing", False, homing=True
    )
    assert verdict.accepted and verdict.mode == TwinMode.MODE_VALIDATED


def test_a_normal_validated_request_never_gets_the_allowance() -> None:
    """Neither entering, nor re-asserting after a homing entry, skips the carriage check."""
    boundary = _boundary_with_carriages(0.0, 0.30)
    machine = _authority(boundary)
    verdict = machine.request(TwinMode.MODE_VALIDATED, "", "program", False)
    assert not verdict.accepted and "home it" in verdict.detail
    # `force` is not a way round it either.
    verdict = machine.request(TwinMode.MODE_VALIDATED, "", "program", True)
    assert not verdict.accepted and "home it" in verdict.detail
    assert machine.request(TwinMode.MODE_VALIDATED, "", "homing", False, homing=True).accepted
    # In VALIDATED by the allowance, the program's own re-assertion is refused
    # until the carriages agree, and accepted once they do.
    verdict = machine.request(TwinMode.MODE_VALIDATED, "", "program", False)
    assert not verdict.accepted and "home it" in verdict.detail
    now = time.monotonic()
    boundary._track_positions[("counterpart", "picker_track_joint")] = (0.0, now)
    assert machine.request(TwinMode.MODE_VALIDATED, "", "program", False).accepted


def test_homing_still_waits_for_a_physical_side_that_is_not_ready() -> None:
    boundary = _boundary_with_carriages(0.0, 0.30, counterpart_age_s=2 * AGE)
    verdict = _authority(boundary).request(
        TwinMode.MODE_VALIDATED, "", "homing", False, homing=True
    )
    assert not verdict.accepted and "old" in verdict.detail
    boundary = _boundary_with_carriages(0.0, 0.30)
    watch = _ready_watch(time.monotonic())
    watch.controller_at = None
    boundary._physical_watches = {"picker": watch}
    verdict = _authority(boundary).request(
        TwinMode.MODE_VALIDATED, "", "homing", False, homing=True
    )
    assert not verdict.accepted and "controller is not running" in verdict.detail


def test_homing_never_skips_the_hardware_gate() -> None:
    def refused() -> None:
        raise RuntimeError("CITE_ALLOW_HARDWARE is not 1")

    boundary = _boundary_with_carriages(0.0, 0.30)
    verdict = _authority(boundary, refused).request(
        TwinMode.MODE_VALIDATED, "", "homing", True, homing=True
    )
    assert not verdict.accepted and verdict.code == ResultCode.SAFETY_BLOCKED


@pytest.mark.parametrize(
    "mode",
    [
        TwinMode.MODE_SIM,
        TwinMode.MODE_REAL,
        TwinMode.MODE_SHADOW,
        TwinMode.MODE_CLOSED_LOOP,
        TwinMode.MODE_VIRTUAL_LEAD,
    ],
)
def test_homing_is_accepted_with_validated_only(mode) -> None:
    machine = _authority(_boundary_with_carriages(0.0, 0.0))
    verdict = machine.request(mode, "", "homing", True, homing=True)
    assert not verdict.accepted and verdict.code == ResultCode.PRECONDITION_FAILED
    assert "VALIDATED only" in verdict.detail
    assert machine.mode == TwinMode.MODE_SIM


# --------------------------------------------------------------------------- #
# JointsAt
# --------------------------------------------------------------------------- #


def _heard(plant, counterpart, counterpart_age_s=0.0, now=100.0):
    heard = {("plant", j): (p, now) for j, p in zip(JOINTS, plant)}
    heard.update(
        {("counterpart", j): (p, now - counterpart_age_s) for j, p in zip(JOINTS, counterpart)}
    )
    return heard


def _at(heard, targets=(0.0, 0.0), tolerance=0.01, physical=("counterpart",)):
    return joints_at(
        ("plant", "counterpart"), heard, physical, JOINTS, targets, tolerance, 100.0, AGE
    )


def test_every_side_at_every_target_is_at() -> None:
    assert _at(_heard((0.0, 0.005), (-0.004, 0.0))) == (JointsAt.Response.AT, None)


def test_a_side_away_is_away_and_says_which_joint() -> None:
    reason, detail = _at(_heard((0.0, 0.0), (0.0, 0.2)))
    assert reason == JointsAt.Response.AWAY
    assert "counterpart: picker_joint2 stands at 0.2000" in detail


def test_a_physical_side_counts_only_fresh() -> None:
    reason, detail = _at(_heard((0.0, 0.0), (0.0, 0.0), counterpart_age_s=2 * AGE))
    assert reason == JointsAt.Response.UNHEARD and "old" in detail
    # A simulated side has no age bound.
    reason, _ = _at(_heard((0.0, 0.0), (0.0, 0.0), counterpart_age_s=2 * AGE), physical=())
    assert reason == JointsAt.Response.AT


def test_a_joint_never_heard_is_unheard_and_away_outranks_it() -> None:
    heard = _heard((0.0, 0.0), (0.0, 0.0))
    del heard[("counterpart", "picker_joint1")]
    reason, detail = _at(heard)
    assert reason == JointsAt.Response.UNHEARD and "no picker_joint1 position heard" in detail
    heard[("plant", "picker_joint2")] = (1.0, 100.0)
    assert _at(heard)[0] == JointsAt.Response.AWAY


@pytest.mark.parametrize(
    ("targets", "tolerance"), [((0.0,), 0.01), ((0.0, 0.0), -0.01), ((0.0, 0.0), float("nan"))]
)
def test_a_malformed_question_is_answered_as_one(targets, tolerance) -> None:
    reason, _ = _at(_heard((0.0, 0.0), (0.0, 0.0)), targets, tolerance)
    assert reason == JointsAt.Response.MALFORMED


def test_the_boundary_answers_for_every_side_in_every_mode() -> None:
    """Asked in SIM, before anything is commanded, the counterpart is judged too."""
    now = time.monotonic()
    boundary = object.__new__(TwinBoundary)
    boundary._lock = threading.Lock()
    boundary._sides = {"plant": None, "counterpart": None}
    boundary._physical_watches = {"picker": _ready_watch(now)}
    boundary._state_max_age_s = AGE
    boundary._joint_positions = {
        ("plant", "picker_joint1"): (0.0, now),
        ("counterpart", "picker_joint1"): (0.5, now),
    }
    request = JointsAt.Request(joints=["picker_joint1"], positions=[0.0], tolerance=0.01)
    answer = boundary._on_joints_at(request, JointsAt.Response())
    assert not answer.at and answer.reason == JointsAt.Response.AWAY
    assert "counterpart: picker_joint1 stands at 0.5000" in answer.detail
    boundary._joint_positions[("counterpart", "picker_joint1")] = (0.001, now)
    answer = boundary._on_joints_at(request, JointsAt.Response())
    assert answer.at and answer.reason == JointsAt.Response.AT
