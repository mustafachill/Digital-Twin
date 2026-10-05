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

"""The hold gate against `cite_hardware`'s vendor fakes (ADR-0070 item 6, R-05, R-09).

`hold_gate.py` is the link in the physical side's launch whose exit 0 means the
arm is confirmed held at the vendor's STOP: nothing that could move the arm
starts before it. Each case runs the real gate as its own process, on a domain
of its own, against the shipped plan's names served by fakes in this test's
node. **Nothing here reaches hardware**: every vendor endpoint is a fake.

The cases run in file order, because a faked service once answered stays
advertised (`vendor_fakes.FakeTrack`): the missing-service case runs before
that service exists.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from cite_bringup.hold_gate import HoldFailed, wait_until
from cite_bringup.plan import COUNTERPART_SIDE, default_plan_path, load
from cite_interfaces.msg import DeadmanState
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cite_hardware" / "test"))
from vendor_fakes import FakeArmState, FakeDeadman, FakeTrack, Harness  # noqa: E402
from xarm_msgs.srv import GetFloat32  # noqa: E402

ZONE = "cell_b"
#: Short, because every failing case waits it out; a ceiling, not a schedule.
DEADLINE_S = 3.0
DOMAIN = str(10 + os.getpid() % 80)


def _vendor():
    (manager,) = load(default_plan_path(ZONE)).controller_managers
    return manager.physical_on(COUNTERPART_SIDE), manager.vendor_on(COUNTERPART_SIDE)


@pytest.fixture(scope="module")
def rig():
    os.environ["ROS_DOMAIN_ID"] = DOMAIN
    harness = Harness("hold_gate_test")
    physical, vendor = _vendor()
    deadman = FakeDeadman(harness, physical.deadman_state_topic)
    try:
        yield harness, physical, vendor, deadman
    finally:
        harness.close()


def _gate() -> subprocess.CompletedProcess:
    environment = dict(os.environ, ROS_DOMAIN_ID=DOMAIN)
    environment.pop("CITE_ALLOW_HARDWARE", None)
    return subprocess.run(
        [
            sys.executable, "-m", "cite_bringup.hold_gate",
            "--zone", ZONE, "--side", COUNTERPART_SIDE, "--deadline", str(DEADLINE_S),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=DEADLINE_S + 30.0,
    )


# --------------------------------------------------------------------------- #
# R-09: the failure names what was missing at expiry
# --------------------------------------------------------------------------- #


def test_the_failure_is_described_when_the_wait_expires() -> None:
    now = {"t": 0.0}
    missing = ["a", "b", "c"]

    def spin() -> None:
        now["t"] += 1.0
        if len(missing) > 1:
            missing.pop(0)

    with pytest.raises(HoldFailed) as failure:
        wait_until(
            lambda: False, lambda: f"still missing {missing}", 5.0, 5.0, spin,
            clock=lambda: now["t"],
        )
    assert "still missing ['c']" in str(failure.value)


# --------------------------------------------------------------------------- #
# R-05: the gate against the vendor fakes, in order
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("state", [DeadmanState.STATE_HEALTHY, DeadmanState.STATE_TRIPPED])
def test_1_a_deadman_that_is_not_awaiting_confirms_no_hold(rig, state: int) -> None:
    _harness, physical, _vendor, deadman = rig
    deadman.say(state, "not awaiting")
    result = _gate()
    assert result.returncode == 1, result.stderr
    assert f"did not say AWAITING on {physical.deadman_state_topic}" in result.stderr


def test_2_a_vendor_service_not_advertised_is_named(rig) -> None:
    harness, _physical, vendor, deadman = rig
    deadman.say(DeadmanState.STATE_AWAITING, "awaiting")
    rig_track = FakeTrack(harness, vendor.service_namespace)
    rig_arm = FakeArmState(harness, vendor.service_namespace)
    harness.fakes = [rig_track, rig_arm]
    result = _gate()
    assert result.returncode == 1, result.stderr
    assert vendor.services["get_gripper_position"] in result.stderr
    assert vendor.services["set_state"] not in result.stderr


def test_3_a_refused_stop_confirms_no_hold(rig) -> None:
    harness, _physical, vendor, _deadman = rig
    harness.gripper_state = harness.node.create_service(
        GetFloat32,
        vendor.services["get_gripper_position"],
        lambda _request, response: response,
        callback_group=harness.group,
    )
    _track, arm = harness.fakes
    arm.failures = 1
    result = _gate()
    assert result.returncode == 1, result.stderr
    assert "refused a STOP (code 1)" in result.stderr


def test_4_an_unanswered_stop_fails_at_the_deadline(rig) -> None:
    harness, _physical, _vendor, _deadman = rig
    _track, arm = harness.fakes
    arm.hold_next.set()
    try:
        result = _gate()
    finally:
        arm.release.set()
    assert result.returncode == 1, result.stderr
    assert f"the vendor did not answer a STOP not within {DEADLINE_S:g} s" in result.stderr


def test_5_an_awaiting_deadman_and_an_acknowledged_stop_confirm_the_hold(rig) -> None:
    harness, _physical, _vendor, _deadman = rig
    _track, arm = harness.fakes
    arm.release.clear()
    before = list(arm.requests)
    result = _gate()
    assert result.returncode == 0, result.stderr
    # The one command the gate may send, and nothing else.
    assert arm.requests[len(before):] == [4]
    assert arm.modes == []
