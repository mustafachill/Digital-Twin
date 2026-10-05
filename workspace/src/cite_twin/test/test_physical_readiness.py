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

from cite_bringup.readiness import PHYSICAL_SIDE_NOT_READY, waits_for_a_physical_side
from cite_interfaces.msg import DeadmanState, ResultCode, TwinMode
from cite_twin.mode import Deployment, ModeAuthority
from cite_twin.physical_readiness import deadman_permits_motion, PhysicalSideWatch, unready
import pytest

JOINTS = ("picker_joint1", "picker_track_joint", "picker_drive_joint")
AGE = 0.25


def _state(state: int, arm_enabled: bool | None = None) -> DeadmanState:
    """A deadman state; enabled exactly when HEALTHY unless the test says otherwise."""
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
