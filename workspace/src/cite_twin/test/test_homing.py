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


def test_real_does_not_compare_the_carriages_because_the_plant_is_idle() -> None:
    """ADR-0072: in REAL only the physical side is commanded, so agreement is not asked.

    The plant's carriage stands wherever the last target left it and nothing is
    sent to it. Every physical-side readiness question is still asked, and
    VALIDATED still refuses the same carriages apart.
    """
    boundary = _boundary_with_carriages(0.0, 0.30)
    machine = _authority(boundary)
    verdict = machine.request(TwinMode.MODE_REAL, "", "real arm", False)
    assert verdict.accepted, verdict.detail
    assert verdict.mode == TwinMode.MODE_REAL
    assert verdict.commands_hardware
    back = machine.request(TwinMode.MODE_SIM, "", "done", False)
    assert back.accepted
    refused = machine.request(TwinMode.MODE_VALIDATED, "", "twin", False)
    assert not refused.accepted and "home it" in refused.detail


def test_real_still_waits_for_a_physical_side_that_is_not_ready() -> None:
    boundary = _boundary_with_carriages(0.0, 0.30, counterpart_age_s=2 * AGE)
    verdict = _authority(boundary).request(TwinMode.MODE_REAL, "", "real arm", False)
    assert not verdict.accepted
    assert verdict.code == ResultCode.PRECONDITION_FAILED
    assert "old" in verdict.detail


def test_real_still_needs_the_hardware_opt_in() -> None:
    def refused() -> None:
        raise RuntimeError("CITE_ALLOW_HARDWARE is not set to 1")

    boundary = _boundary_with_carriages(0.0, 0.0)
    verdict = _authority(boundary, refused).request(TwinMode.MODE_REAL, "", "real arm", False)
    assert not verdict.accepted
    assert verdict.code == ResultCode.SAFETY_BLOCKED


def test_homing_is_refused_with_real() -> None:
    """The allowance is VALIDATED's alone; REAL needs none."""
    boundary = _boundary_with_carriages(0.0, 0.0)
    verdict = _authority(boundary).request(TwinMode.MODE_REAL, "", "x", False, homing=True)
    assert not verdict.accepted


def _boundary_for_joints(now: float, sides=("plant", "counterpart")) -> TwinBoundary:
    boundary = object.__new__(TwinBoundary)
    boundary._lock = threading.Lock()
    boundary._sides = {side: None for side in sides}
    boundary._physical_watches = {"picker": _ready_watch(now)} if "counterpart" in sides else {}
    boundary._state_max_age_s = AGE
    boundary._joint_positions = {
        ("plant", "picker_joint1"): (0.0, now),
        ("counterpart", "picker_joint1"): (0.5, now),
    }
    return boundary


def test_named_sides_are_judged_alone() -> None:
    """ADR-0072: a target is measured on its own sides; the other's place is not its business."""
    now = time.monotonic()
    boundary = _boundary_for_joints(now)

    def ask(sides):
        request = JointsAt.Request(
            joints=["picker_joint1"], positions=[0.0], tolerance=0.01, sides=list(sides)
        )
        return boundary._on_joints_at(request, JointsAt.Response())

    assert ask(["plant"]).at
    away = ask(["counterpart"])
    assert not away.at and away.reason == JointsAt.Response.AWAY
    assert not ask([]).at


def test_a_plant_alone_deployment_judges_the_plant_alone() -> None:
    now = time.monotonic()
    boundary = _boundary_for_joints(now, sides=("plant",))
    request = JointsAt.Request(joints=["picker_joint1"], positions=[0.0], tolerance=0.01)
    assert boundary._on_joints_at(request, JointsAt.Response()).at


def test_a_forced_mode_whose_side_does_not_run_routes_nowhere() -> None:
    """ADR-0072: `force` past the no-far-side check cannot route to a side with no context."""
    from cite_interfaces.msg import ResultCode as Code

    boundary = object.__new__(TwinBoundary)
    boundary._sides = {"plant": None}
    chosen = boundary._route(TwinMode.MODE_REAL)
    assert not chosen.accepted and chosen.code == Code.PRECONDITION_FAILED
    assert "counterpart" in chosen.detail and "plant alone" in chosen.detail
    sim = boundary._route(TwinMode.MODE_SIM)
    assert sim.accepted and sim.sides == ("plant",)


# --------------------------------------------------------------------------- #
# ADR-0072 safety requirements, at the boundary
# --------------------------------------------------------------------------- #


class _Publisher:
    def __init__(self) -> None:
        self.sent = []

    def publish(self, message) -> None:
        self.sent.append(message)


class _Log:
    def __init__(self) -> None:
        self.lines = []

    def warning(self, text, **_kwargs) -> None:
        self.lines.append(text)

    error = warning
    info = warning


def _commanding_boundary(mode: int, physical: bool = True) -> TwinBoundary:
    class _Authority:
        pass

    boundary = _boundary_with_carriages(0.0, 0.0)
    if not physical:
        boundary._physical_watches = {}
    boundary._lock = threading.Lock()
    boundary._authority = _Authority()
    boundary._authority.mode = mode
    boundary._sides = {"plant": None, "counterpart": None}
    boundary._log = _Log()
    return boundary


@pytest.mark.parametrize("value", [0.25, -0.1])
def test_a_non_zero_belt_never_reaches_a_physical_side(value) -> None:
    """R-24: no physical belt exists; in REAL the command is dropped, in VALIDATED plant only."""
    from std_msgs.msg import Float64

    topic = "/cite/cell_b/belt/command"
    for mode, reached in ((TwinMode.MODE_REAL, []), (TwinMode.MODE_VALIDATED, ["plant"])):
        boundary = _commanding_boundary(mode)
        boundary._belt_publishers = {
            (side, topic): _Publisher() for side in ("plant", "counterpart")
        }
        boundary._on_belt_command(topic, Float64(data=value))
        sent = [side for (side, _), pub in boundary._belt_publishers.items() if pub.sent]
        assert sent == reached, mode
    # A stop still reaches every side, physical or not.
    boundary._on_belt_command(topic, Float64(data=0.0))
    assert boundary._belt_publishers[("counterpart", topic)].sent


def test_in_sim_only_a_zero_belt_reaches_the_counterpart() -> None:
    """R-01: in SIM the counterpart's domain receives a belt stop and nothing else."""
    from std_msgs.msg import Float64

    topic = "/cite/cell_b/belt/command"
    for physical in (True, False):
        boundary = _commanding_boundary(TwinMode.MODE_SIM, physical)
        boundary._belt_publishers = {
            (side, topic): _Publisher() for side in ("plant", "counterpart")
        }
        boundary._on_belt_command(topic, Float64(data=0.3))
        assert boundary._belt_publishers[("plant", topic)].sent
        assert not boundary._belt_publishers[("counterpart", topic)].sent
        boundary._on_belt_command(topic, Float64(data=0.0))
        assert [m.data for m in boundary._belt_publishers[("counterpart", topic)].sent] == [0.0]


def _track_boundary(mode: int, physical: bool = True) -> TwinBoundary:
    boundary = _commanding_boundary(mode, physical)
    topic = "/cite/cell_b/picker/track/joint_trajectory"
    boundary._track_joint_by_topic = {topic: "picker_track_joint"}
    boundary._track_publishers = {(side, topic): _Publisher() for side in ("plant", "counterpart")}
    return boundary


def test_in_sim_only_a_hold_reaches_the_counterpart() -> None:
    """R-01: a moving trajectory in SIM reaches the plant alone; a stop holds each where it is."""
    from cite_bringup.track_command import move as track_move
    from trajectory_msgs.msg import JointTrajectory

    topic = "/cite/cell_b/picker/track/joint_trajectory"
    boundary = _track_boundary(TwinMode.MODE_SIM)
    boundary._on_track_command(topic, track_move("picker_track_joint", 0.0, 0.5, 2.0))
    assert boundary._track_publishers[("plant", topic)].sent
    assert not boundary._track_publishers[("counterpart", topic)].sent
    boundary._on_track_command(topic, JointTrajectory(joint_names=["picker_track_joint"]))
    (hold,) = boundary._track_publishers[("counterpart", topic)].sent
    assert hold.points[0].positions == hold.points[-1].positions


def test_a_stop_reaches_a_physical_carriage_never_heard() -> None:
    """R-02: a physical adapter stops where it stands whatever a hold names, so it is sent one."""
    from trajectory_msgs.msg import JointTrajectory

    topic = "/cite/cell_b/picker/track/joint_trajectory"
    boundary = _track_boundary(TwinMode.MODE_REAL)
    del boundary._track_positions[("counterpart", "picker_track_joint")]
    boundary._on_track_command(topic, JointTrajectory(joint_names=["picker_track_joint"]))
    (hold,) = boundary._track_publishers[("counterpart", topic)].sent
    assert hold.points[0].positions == hold.points[-1].positions
    # A SIMULATED side never heard is sent nothing: its controller would go there.
    boundary = _track_boundary(TwinMode.MODE_VALIDATED, physical=False)
    del boundary._track_positions[("counterpart", "picker_track_joint")]
    boundary._on_track_command(topic, JointTrajectory(joint_names=["picker_track_joint"]))
    assert not boundary._track_publishers[("counterpart", topic)].sent


def test_a_physical_carriage_outside_its_travel_is_refused_for_good() -> None:
    """R-10: REAL and VALIDATED alike, homing or not."""
    boundary = _boundary_with_carriages(0.0, 0.80)
    boundary._physical_strokes = {"picker_track_joint": 0.70}
    assert "outside its travel" in boundary._physical_carriage_outside_travel()
    machine = ModeAuthority(
        Deployment.paired({"picker": True}),
        lambda: None,
        physical_side_unready=boundary._physical_side_unready,
        physical_carriage_outside_travel=boundary._physical_carriage_outside_travel,
    )
    for mode, homing in ((TwinMode.MODE_REAL, False), (TwinMode.MODE_VALIDATED, True)):
        verdict = machine.request(mode, "", "x", False, homing=homing)
        assert not verdict.accepted and "outside its travel" in verdict.detail
    boundary._track_positions[("counterpart", "picker_track_joint")] = (0.70, time.monotonic())
    assert boundary._physical_carriage_outside_travel() is None


def test_twin_sides_offers_a_physical_side_only_when_ready() -> None:
    """R-19: commandable by measurement - a stale physical side is running, not commandable."""
    boundary = _boundary_with_carriages(0.0, 0.0)
    boundary._sides = {"plant": None, "counterpart": None}
    running, physical, commandable, stationary, detail = boundary._sides_now()
    assert running == ("plant", "counterpart") and physical == ("counterpart",)
    assert commandable == ("plant", "counterpart") and detail == ""
    assert stationary == ("counterpart",)
    stale = _boundary_with_carriages(0.0, 0.0, counterpart_age_s=2 * AGE)
    stale._sides = {"plant": None, "counterpart": None}
    _, _, commandable, stationary, detail = stale._sides_now()
    assert commandable == ("plant",) and "old" in detail
    assert stationary == (), "a carriage not heard fresh is not reported stationary"
    alone = _boundary_with_carriages(0.0, 0.0)
    alone._physical_watches = {}
    alone._physical_tracks = []
    alone._sides = {"plant": None}
    assert alone._sides_now() == (("plant",), (), ("plant",), (), "")


def test_twin_sides_reports_a_moving_physical_carriage_as_not_stationary() -> None:
    """S-02: from the plan's freshness bound and the track's goal tolerance alone."""
    boundary = _boundary_with_carriages(0.0, 0.30)
    boundary._sides = {"plant": None, "counterpart": None}
    now = time.monotonic()
    boundary._track_history["picker_track_joint"] = [(0.20, now - AGE), (0.30, now)]
    _, _, commandable, stationary, detail = boundary._sides_now()
    assert stationary == () and "picker_track_joint is not reported stationary" in detail
    # Moving is no readiness question: the side stays commandable.
    assert commandable == ("plant", "counterpart")
    # Still to within the goal tolerance over the bound: stationary again.
    boundary._track_history["picker_track_joint"] = [(0.3005, now - AGE), (0.30, now)]
    assert boundary._sides_now()[3] == ("counterpart",)


def test_twin_sides_does_not_offer_a_physical_side_whose_carriage_is_outside_its_travel() -> None:
    """R-06: what a REAL transition would refuse for good is not offered at all."""
    boundary = _boundary_with_carriages(0.0, 0.80)
    boundary._sides = {"plant": None, "counterpart": None}
    _, _, commandable, _, detail = boundary._sides_now()
    assert commandable == ("plant",) and "outside its travel" in detail


def test_a_plant_alone_deployment_refuses_every_mode_but_sim_even_forced_and_opted_in() -> None:
    """R-15: from the running deployment, not from the plan, and never behind `force`."""
    from cite_twin.mode import MODE_NAMES

    deployment = Deployment(
        {"picker": {"plant": False, "counterpart": None}}, absent=frozenset({"counterpart"})
    )
    for mode in MODE_NAMES:
        machine = ModeAuthority(deployment, lambda: None)
        verdict = machine.request(mode, "", "x", True)
        if mode == TwinMode.MODE_SIM:
            assert verdict.accepted
        else:
            assert not verdict.accepted, MODE_NAMES[mode]
            assert machine.mode == TwinMode.MODE_SIM
