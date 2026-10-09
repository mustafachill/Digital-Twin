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

"""When the boundary lets a mode command a physical side (ADR-0070 item 6).

A physical side comes up with its arm held. `SetMode` into a mode that would
command it is refused - as a PRECONDITION, with the one detail the fixed
program waits on - until the deadman permits motion, the arm controller is
running and every joint the side publishes is fresh. Pure logic and fakes: no
graph, no robot.
"""

from __future__ import annotations

import time

from cite_bringup.readiness import PHYSICAL_SIDE_NOT_READY, waits_for_a_physical_side
from cite_interfaces.msg import DeadmanState, ResultCode, TwinMode
from cite_twin.mode import Deployment, ModeAuthority
from cite_twin.physical_readiness import deadman_permits_motion, PhysicalSideWatch, unready
from cite_twin.twin_boundary import TwinBoundary
import pytest

JOINTS = ("picker_joint1", "picker_track_joint", "picker_drive_joint")
AGE = 0.25


def _state(state: int, arm_enabled: bool | None = None) -> DeadmanState:
    """Build a deadman state, enabled exactly when HEALTHY unless the test says otherwise."""
    message = DeadmanState()
    message.state = state
    message.detail = "for the record"
    message.arm_enabled = (
        state == DeadmanState.STATE_HEALTHY if arm_enabled is None else arm_enabled
    )
    return message


def _ready_watch(now: float = 10.0) -> PhysicalSideWatch:
    watch = PhysicalSideWatch(asset="picker", joints=JOINTS, max_age_s=AGE)
    watch.heard_deadman(_state(DeadmanState.STATE_HEALTHY), now)
    watch.heard_controller(now)
    watch.heard_joints(JOINTS, now)
    return watch


@pytest.mark.parametrize(
    ("state", "permits"),
    [
        (DeadmanState.STATE_INACTIVE, False),
        (DeadmanState.STATE_AWAITING, False),
        (DeadmanState.STATE_HEALTHY, True),
        (DeadmanState.STATE_TRIPPED, False),
    ],
)
def test_only_a_healthy_deadman_permits_motion(state: int, permits: bool) -> None:
    assert deadman_permits_motion(_state(state)) is permits


def test_healthy_is_not_enough_until_the_arm_is_enabled() -> None:
    """S-03: HEALTHY with the enable not yet acknowledged is an arm still at STOP."""
    assert deadman_permits_motion(_state(DeadmanState.STATE_HEALTHY, arm_enabled=False)) is False
    watch = _ready_watch()
    watch.heard_deadman(_state(DeadmanState.STATE_HEALTHY, arm_enabled=False), 10.0)
    assert "not yet enabled the arm" in watch.unready(10.0)


def test_a_side_that_said_nothing_is_not_ready() -> None:
    watch = PhysicalSideWatch(asset="picker", joints=JOINTS, max_age_s=AGE)
    assert "no deadman state" in watch.unready(0.0)


def test_a_fresh_healthy_publishing_side_is_ready() -> None:
    assert unready([_ready_watch()], 10.0 + AGE / 2) is None


def test_a_held_arm_is_not_ready() -> None:
    watch = _ready_watch()
    watch.heard_deadman(_state(DeadmanState.STATE_AWAITING), 10.0)
    assert "holds the arm" in watch.unready(10.0)


@pytest.mark.parametrize("what", ["deadman", "controller", "picker_track_joint"])
def test_anything_stale_is_not_ready(what: str) -> None:
    watch = _ready_watch(now=10.0)
    later = 10.0 + 2 * AGE
    # Everything else heard again, the one thing under test left to age.
    if what != "deadman":
        watch.heard_deadman(_state(DeadmanState.STATE_HEALTHY), later)
    if what != "controller":
        watch.heard_controller(later)
    watch.heard_joints([j for j in JOINTS if j != what], later)
    assert watch.unready(later) is not None


def test_a_joint_never_heard_is_named() -> None:
    watch = _ready_watch()
    del watch.joint_at["picker_drive_joint"]
    assert "picker_drive_joint" in watch.unready(10.0)


def _authority(watch: PhysicalSideWatch) -> ModeAuthority:
    return ModeAuthority(
        Deployment.paired({"picker": True}),
        lambda: None,
        physical_side_unready=lambda: unready([watch], 10.0),
    )


def test_validated_waits_for_the_physical_side_with_a_detail_the_program_reads() -> None:
    watch = _ready_watch()
    watch.heard_deadman(_state(DeadmanState.STATE_AWAITING), 10.0)
    verdict = _authority(watch).request(TwinMode.MODE_VALIDATED, "", "go", force=False)
    assert not verdict.accepted
    assert verdict.code == ResultCode.PRECONDITION_FAILED
    assert verdict.detail.startswith(PHYSICAL_SIDE_NOT_READY)
    assert waits_for_a_physical_side(verdict.detail)


def test_force_does_not_skip_the_wait() -> None:
    watch = _ready_watch()
    watch.heard_deadman(_state(DeadmanState.STATE_TRIPPED), 10.0)
    verdict = _authority(watch).request(TwinMode.MODE_VALIDATED, "", "go", force=True)
    assert not verdict.accepted


def test_a_ready_side_is_entered() -> None:
    verdict = _authority(_ready_watch()).request(TwinMode.MODE_VALIDATED, "", "go", force=False)
    assert verdict.accepted and verdict.mode == TwinMode.MODE_VALIDATED


def test_the_opt_in_is_asked_before_readiness() -> None:
    """A missing opt-in is a safety refusal, never reported as 'not ready yet'."""

    def refused() -> None:
        raise RuntimeError("CITE_ALLOW_HARDWARE is not set to 1")

    machine = ModeAuthority(
        Deployment.paired({"picker": True}),
        refused,
        physical_side_unready=lambda: "not yet",
    )
    verdict = machine.request(TwinMode.MODE_VALIDATED, "", "go", force=False)
    assert verdict.code == ResultCode.SAFETY_BLOCKED
    assert not waits_for_a_physical_side(verdict.detail)


def test_a_simulated_far_side_never_waits() -> None:
    machine = ModeAuthority(
        Deployment.paired({"picker": False}),
        lambda: None,
        physical_side_unready=lambda: "should never be asked",
    )
    assert machine.request(TwinMode.MODE_VALIDATED, "", "go", force=False).accepted


def test_reasserting_validated_checks_the_physical_side_again() -> None:
    """R-04: a re-assertion is about to command the side, which may have tripped since."""
    watch = _ready_watch()
    machine = _authority(watch)
    assert machine.request(TwinMode.MODE_VALIDATED, "", "go", force=False).accepted
    watch.heard_deadman(_state(DeadmanState.STATE_TRIPPED), 10.0)
    verdict = machine.request(TwinMode.MODE_VALIDATED, "", "again", force=False)
    assert not verdict.accepted
    assert waits_for_a_physical_side(verdict.detail)
    assert machine.mode == TwinMode.MODE_VALIDATED  # refused, not left
    watch.heard_deadman(_state(DeadmanState.STATE_HEALTHY), 10.0)
    assert machine.request(TwinMode.MODE_VALIDATED, "", "again", force=False).accepted


def test_reasserting_a_mode_that_commands_no_physical_side_never_waits() -> None:
    watch = _ready_watch()
    watch.heard_deadman(_state(DeadmanState.STATE_TRIPPED), 10.0)
    machine = _authority(watch)
    assert machine.request(TwinMode.MODE_SIM, "", "stay", force=False).accepted


def _boundary_with_carriages(
    plant_m: float, counterpart_m: float, counterpart_age_s: float = 0.0
) -> TwinBoundary:
    """Build the boundary's own readiness question, on a ready arm with two carriages."""
    now = time.monotonic()
    boundary = object.__new__(TwinBoundary)
    boundary._physical_watches = {"picker": _ready_watch(now)}
    boundary._physical_tracks = [("picker_track_joint", 0.001)]
    boundary._state_max_age_s = AGE
    boundary._track_positions = {
        ("plant", "picker_track_joint"): (plant_m, now),
        ("counterpart", "picker_track_joint"): (counterpart_m, now - counterpart_age_s),
    }
    return boundary


def _boundary_authority(boundary: TwinBoundary) -> ModeAuthority:
    return ModeAuthority(
        Deployment.paired({"picker": True}),
        lambda: None,
        physical_side_unready=boundary._physical_side_unready,
        physical_carriage_apart=boundary._physical_carriage_apart,
    )


def test_a_physical_carriage_apart_is_refused_for_good() -> None:
    """SA-S-01 b, S-08: a ready arm whose carriage stands elsewhere is refused, finally.

    It never clears by itself, and the program asks VALIDATED after the operator
    confirmed the cell clear; a refusal it waited on would keep them waiting.
    """
    boundary = _boundary_with_carriages(0.0, 0.30)
    reason = boundary._physical_carriage_apart()
    assert reason is not None and "picker_track_joint" in reason and "home it" in reason
    assert boundary._physical_side_unready() is None
    verdict = _boundary_authority(boundary).request(TwinMode.MODE_VALIDATED, "", "go", False)
    assert not verdict.accepted and verdict.code == ResultCode.PRECONDITION_FAILED
    assert "home it" in verdict.detail
    assert not waits_for_a_physical_side(verdict.detail)


def test_the_program_stops_at_once_on_a_carriage_apart() -> None:
    """The boundary's verdict, read by the program's own loop: one ask, no wait."""
    from cite_bringup.program.cell import ask_until_accepted
    from cite_bringup.program.steps import StepFailed

    authority = _boundary_authority(_boundary_with_carriages(0.0, 0.30))
    asks: list[int] = []

    def ask() -> tuple[bool, str]:
        asks.append(1)
        verdict = authority.request(TwinMode.MODE_VALIDATED, "", "go", False)
        return verdict.accepted, verdict.detail

    def pause() -> None:
        raise AssertionError("waited on a refusal that never clears by itself")

    with pytest.raises(StepFailed, match="refused VALIDATED"):
        ask_until_accepted(ask, pause, lambda _text: None)
    assert asks == [1]


def test_a_physical_carriage_not_heard_fresh_is_waited_for() -> None:
    """A position too old clears by itself: still the retryable 'not ready'."""
    boundary = _boundary_with_carriages(0.0, 0.30, counterpart_age_s=2 * AGE)
    assert boundary._physical_carriage_apart() is None
    reason = boundary._physical_side_unready()
    assert reason is not None and "old" in reason
    verdict = _boundary_authority(boundary).request(TwinMode.MODE_VALIDATED, "", "go", False)
    assert not verdict.accepted and waits_for_a_physical_side(verdict.detail)


def test_a_physical_carriage_where_the_plants_is_is_ready() -> None:
    boundary = _boundary_with_carriages(0.30, 0.3005)
    assert boundary._physical_side_unready() is None
    assert boundary._physical_carriage_apart() is None
    verdict = _boundary_authority(boundary).request(TwinMode.MODE_VALIDATED, "", "go", False)
    assert verdict.accepted


def _track_arrived(boundary: TwinBoundary, mode: int, position_m: float):
    from cite_interfaces.srv import TrackArrived
    import threading

    class _Authority:
        pass

    boundary._lock = threading.Lock()
    boundary._authority = _Authority()
    boundary._authority.mode = mode
    boundary._sides = {"plant": None, "counterpart": None}
    boundary._track_asset_by_joint = {"picker_track_joint": "picker"}
    request = TrackArrived.Request(
        joint="picker_track_joint", position_m=position_m, tolerance_m=0.001
    )
    return boundary._on_track_arrived(request, TrackArrived.Response())


def test_in_sim_a_physical_carriage_heard_elsewhere_has_not_arrived() -> None:
    """S-08: what the program asks before the operator, at the plant's own position."""
    from cite_interfaces.srv import TrackArrived

    answer = _track_arrived(_boundary_with_carriages(0.0, 0.30), TwinMode.MODE_SIM, 0.0)
    assert not answer.arrived and "counterpart: stands at 300.0 mm" in answer.detail
    # SIM routes a track command to the plant (ADR-0072); the physical side is
    # still judged, because this is the ask before a person is let in.
    assert answer.reason == TrackArrived.Response.AWAY and answer.routed
    answer = _track_arrived(_boundary_with_carriages(0.30, 0.3005), TwinMode.MODE_SIM, 0.30)
    assert answer.arrived and answer.reason == TrackArrived.Response.ARRIVED


def test_in_sim_a_physical_carriage_not_heard_fresh_has_not_arrived() -> None:
    """R-01: unheard is never agreement; it is UNHEARD, which the program waits on."""
    from cite_interfaces.srv import TrackArrived

    boundary = _boundary_with_carriages(0.0, 0.0, counterpart_age_s=2 * AGE)
    answer = _track_arrived(boundary, TwinMode.MODE_SIM, 0.0)
    assert not answer.arrived and answer.reason == TrackArrived.Response.UNHEARD
    assert "old" in answer.detail
    del boundary._track_positions[("counterpart", "picker_track_joint")]
    answer = _track_arrived(boundary, TwinMode.MODE_SIM, 0.0)
    assert answer.reason == TrackArrived.Response.UNHEARD
    assert "no track position heard" in answer.detail


def test_in_sim_the_plants_carriage_is_still_asked_about() -> None:
    answer = _track_arrived(_boundary_with_carriages(0.0, 0.0), TwinMode.MODE_SIM, 0.30)
    assert not answer.arrived and "plant: stands at 0.0 mm" in answer.detail


@pytest.mark.parametrize("mode", [TwinMode.MODE_REAL, TwinMode.MODE_SHADOW])
def test_in_real_and_shadow_the_physical_side_is_judged_strictly(mode) -> None:
    """R-02: the commanded side there is the counterpart, so its staleness counts."""
    from cite_interfaces.srv import TrackArrived

    stale = _boundary_with_carriages(0.30, 0.30, counterpart_age_s=2 * AGE)
    answer = _track_arrived(stale, mode, 0.30)
    assert not answer.arrived and answer.reason == TrackArrived.Response.UNHEARD
    # REAL routes a track command to the counterpart (ADR-0072); SHADOW none.
    assert answer.routed == (mode == TwinMode.MODE_REAL)
    # The plant is not commanded there, so it is not asked about.
    answer = _track_arrived(_boundary_with_carriages(0.0, 0.30), mode, 0.30)
    assert answer.arrived, answer.detail
    assert "no side is commanded" not in answer.detail


def test_in_validated_a_track_command_is_routed() -> None:
    answer = _track_arrived(_boundary_with_carriages(0.30, 0.30), TwinMode.MODE_VALIDATED, 0.30)
    assert answer.arrived and answer.routed


def test_a_carriage_apart_is_refused_without_a_readiness_question() -> None:
    """R-07: the carriage check stands on its own."""
    boundary = _boundary_with_carriages(0.0, 0.30)
    machine = ModeAuthority(
        Deployment.paired({"picker": True}),
        lambda: None,
        physical_carriage_apart=boundary._physical_carriage_apart,
    )
    verdict = machine.request(TwinMode.MODE_VALIDATED, "", "go", False)
    assert not verdict.accepted and "home it" in verdict.detail
