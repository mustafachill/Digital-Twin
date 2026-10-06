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

from cite_bringup.hold_gate import (
    call_until_answered,
    HoldFailed,
    vendor_call_deadline_s,
    wait_until,
)
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
# A STOP is sent only to a matched server, and sent again until answered
# (stage 2 physical run, 2026-10-06: one STOP sent before the client matched
# was lost, and the gate waited on it to the ceiling)
# --------------------------------------------------------------------------- #


class _Future:
    def __init__(self) -> None:
        self.response = None
        self.cancelled = False

    def done(self) -> bool:
        return self.response is not None

    def result(self):
        return self.response

    def cancel(self) -> None:
        self.cancelled = True


class _Client:
    """A vendor client on a fake clock: matched after ``match_after`` spins.

    ``answer`` decides, per request index and spin count, whether a sent
    request is answered on that spin.
    """

    srv_name = "/fake/set_state"

    def __init__(self, match_after: int, answer) -> None:
        self.spins = 0
        self.match_after = match_after
        self.answer = answer
        self.sent: list[_Future] = []
        self.sent_unmatched = 0
        self.removed: list[_Future] = []

    def service_is_ready(self) -> bool:
        return self.spins >= self.match_after

    def call_async(self, _request) -> _Future:
        if not self.service_is_ready():
            self.sent_unmatched += 1
        future = _Future()
        self.sent.append(future)
        return future

    def remove_pending_request(self, future: _Future) -> None:
        self.removed.append(future)


def _run(client: _Client, ceiling_s: float = 5.0, attempt_s: float = 0.25):
    now = {"t": 0.0}

    def spin(timeout_s: float) -> None:
        now["t"] += min(0.05, timeout_s) or 0.05
        client.spins += 1
        for index, future in enumerate(client.sent):
            if future.response is None and client.answer(index, client.spins):
                future.response = ("answer", index)

    result = call_until_answered(
        client, "STOP", attempt_s, ceiling_s, ceiling_s, spin,
        lambda: "picker: the vendor did not answer a STOP", clock=lambda: now["t"],
    )
    return result, now["t"]


def test_a_stop_is_sent_only_once_the_client_has_matched() -> None:
    client = _Client(match_after=10, answer=lambda _index, _spins: True)
    result, _elapsed = _run(client)
    assert client.sent_unmatched == 0
    assert result == ("answer", 0)


def test_a_lost_stop_is_sent_again_and_the_second_answer_holds() -> None:
    # The first request is lost (never answered); every later one is answered.
    client = _Client(match_after=0, answer=lambda index, _spins: index >= 1)
    result, elapsed = _run(client)
    assert result == ("answer", 1)
    assert elapsed < 1.0
    # The lost request does not stay pending in the client for ever.
    assert client.removed == [client.sent[0]] and client.sent[0].cancelled


def test_a_slow_first_answer_still_counts_after_a_resend() -> None:
    # Only the first request is ever answered, and only after two resends.
    client = _Client(match_after=0, answer=lambda index, spins: index == 0 and spins >= 12)
    result, _elapsed = _run(client)
    assert result == ("answer", 0)
    assert len(client.sent) >= 2


def test_a_stop_never_answered_fails_at_the_deadline() -> None:
    client = _Client(match_after=0, answer=lambda _index, _spins: False)
    with pytest.raises(HoldFailed) as failure:
        _run(client, ceiling_s=2.0, attempt_s=0.25)
    assert "the vendor did not answer a STOP not within 2 s" in str(failure.value)
    # Sent again at every per-call bound until the ceiling, and nothing left pending.
    assert len(client.sent) >= 7
    assert client.removed == client.sent


def test_a_client_that_never_matches_fails_at_the_deadline_having_sent_nothing() -> None:
    client = _Client(match_after=10**9, answer=lambda _index, _spins: True)
    with pytest.raises(HoldFailed) as failure:
        _run(client, ceiling_s=1.0)
    assert "never matched" in str(failure.value)
    assert client.sent == []


def test_the_per_call_bound_is_the_deadmans_own() -> None:
    physical, _names = _vendor()
    # A positive number read from the generated file, not restated here.
    assert vendor_call_deadline_s(physical) > 0.0


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


def test_4_a_lost_stop_is_sent_again_and_the_hold_confirmed(rig) -> None:
    # The first STOP is never answered while the gate runs: what a request sent
    # before the client matched looks like from the gate's side. The old gate
    # waited on that one request to the ceiling; this one sends it again.
    harness, _physical, _vendor, _deadman = rig
    _track, arm = harness.fakes
    arm.release.clear()
    arm.hold_next.set()
    before = len(arm.requests)
    try:
        result = _gate()
    finally:
        arm.release.set()
    assert result.returncode == 0, result.stderr
    # The held request is answered once released, so the next case starts clean.
    harness.wait_for(lambda: len(arm.requests) >= before + 2, "the held STOP returned")
    assert set(arm.requests[before:]) == {4}
    assert arm.modes == []


def test_5_an_awaiting_deadman_and_an_acknowledged_stop_confirm_the_hold(rig) -> None:
    harness, _physical, _vendor, _deadman = rig
    _track, arm = harness.fakes
    arm.release.clear()
    before = list(arm.requests)
    result = _gate()
    assert result.returncode == 0, result.stderr
    # The one command the gate may send, and nothing else; a STOP re-sent
    # because an answer was slow is the same command.
    sent = arm.requests[len(before):]
    assert sent and set(sent) == {4}
    assert arm.modes == []
