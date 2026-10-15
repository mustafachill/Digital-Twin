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

"""The reach gate (ADR-0077 decision 3): it waits for a robot on the network.

**Nothing here reaches a robot.** The robot is a listening socket this test
opens on 127.0.0.1 on a port the kernel chooses, and the gate is driven as a
process against the shipped plan with the address variable pointing at the
loopback: it must exit once the listener appears, never print the address, and
refuse an unset or malformed one before asking anything.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys

from cite_bringup import reach_gate
from cite_bringup.plan import (
    COUNTERPART_SIDE,
    default_plan_path,
    EnvironmentValueMissingError,
    load,
    PlanError,
    PLANT_SIDE,
)
import pytest

GATE = Path(reach_gate.__file__)

#: The variable the shipped plan names for the arm's address.
ADDRESS_VARIABLE = "CITE_XARM_IP"

#: A ceiling on THIS TEST: a gate that should have exited and did not fails the
#: test rather than the suite's timeout. Nothing under test is compared to it.
BACKSTOP_S = 30.0


def _plan():
    return load(default_plan_path("cell_b"))


#: `XARM_CONF::TCP_PORT_REPORT_NORM` in the pinned SDK, as L0 states it.
VENDOR_REPORT_PORT = 30001


def test_the_report_port_is_the_plans_and_the_vendors_normal_one() -> None:
    """A-01: carried by the plan from L0's `vendor_driver.report_port`; not written here."""
    assert not hasattr(reach_gate, "REPORT_PORT")
    vendor = _plan().controller_managers[0].vendor_on(COUNTERPART_SIDE)
    assert vendor is not None and vendor.report_port == VENDOR_REPORT_PORT


def test_the_address_is_read_through_the_one_reader() -> None:
    environ = {ADDRESS_VARIABLE: " 127.0.0.1 "}
    assert reach_gate.addresses(_plan(), COUNTERPART_SIDE, environ) == [
        ("127.0.0.1", VENDOR_REPORT_PORT)
    ]


def test_a_vendor_block_with_no_report_port_is_refused() -> None:
    from dataclasses import replace

    plan = _plan()
    manager = plan.controller_managers[0]
    stripped = replace(
        plan,
        controller_managers=(
            replace(manager, counterpart_vendor=replace(manager.counterpart_vendor,
                                                        report_port=None)),
            *plan.controller_managers[1:],
        ),
    )
    with pytest.raises(PlanError, match="report port"):
        reach_gate.addresses(stripped, COUNTERPART_SIDE, {ADDRESS_VARIABLE: "127.0.0.1"})


def test_an_unset_address_is_refused_naming_the_variable() -> None:
    with pytest.raises(EnvironmentValueMissingError) as refused:
        reach_gate.addresses(_plan(), COUNTERPART_SIDE, {})
    assert ADDRESS_VARIABLE in str(refused.value)


def test_a_side_with_no_physical_arm_is_refused_rather_than_passed() -> None:
    """A gate that asked nobody would pass at once."""
    with pytest.raises(PlanError):
        reach_gate.addresses(_plan(), PLANT_SIDE, {ADDRESS_VARIABLE: "127.0.0.1"})


def test_wait_for_asks_again_at_its_period_until_every_target_answers() -> None:
    asked: list[str] = []
    pauses: list[float] = []
    answers = iter([False, False, True])

    def probe(address: str, port: int) -> bool:
        asked.append(address)
        assert port == VENDOR_REPORT_PORT
        return next(answers)

    assert reach_gate.wait_for(
        [("192.0.2.1", VENDOR_REPORT_PORT)], ceiling_s=None, probe=probe, pause=pauses.append
    )
    assert asked == ["192.0.2.1"] * 3
    assert pauses == [reach_gate.PROBE_PERIOD_S] * 2


def test_a_target_that_answered_is_not_asked_again() -> None:
    asked: list[str] = []
    replies = {"a": iter([True]), "b": iter([False, True])}

    def probe(address: str, port: int) -> bool:  # noqa: ARG001
        asked.append(address)
        return next(replies[address])

    assert reach_gate.wait_for(
        [("a", 1), ("b", 1)], ceiling_s=None, probe=probe, pause=lambda _s: None
    )
    assert asked == ["a", "b", "b"]


def test_the_ceiling_ends_a_wait_for_a_robot_that_never_answers() -> None:
    now = [0.0]

    def pause(seconds: float) -> None:
        now[0] += seconds

    assert not reach_gate.wait_for(
        [("192.0.2.1", VENDOR_REPORT_PORT)],
        ceiling_s=3.0,
        probe=lambda _a, _p: False,
        clock=lambda: now[0],
        pause=pause,
    )
    assert now[0] == pytest.approx(3.0)


def test_answers_is_a_connection_accepted() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        assert not reach_gate.answers("127.0.0.1", port, timeout_s=1.0), "nothing listens yet"
        listener.listen(1)
        assert reach_gate.answers("127.0.0.1", port, timeout_s=1.0)


def _run_gate(environ: dict[str, str], *extra: str) -> subprocess.Popen:
    env = dict(os.environ)
    env.update(environ)
    return subprocess.Popen(
        [sys.executable, str(GATE), "--zone", "cell_b", "--side", COUNTERPART_SIDE, *extra],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_the_gate_exits_once_a_listener_appears_and_never_prints_the_address() -> None:
    """The process end to end: waiting, then a listener, then exit 0."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        # The gate asks the plan's port; this rig redirects it to the
        # ephemeral one by running the module with its reader wrapped.
        script = (
            "import sys; from cite_bringup import reach_gate as g; "
            "read = g.addresses; "
            f"g.addresses = lambda *a: [(ad, {port}) for ad, _p in read(*a)]; "
            "sys.exit(g.main(sys.argv[1:]))"
        )
        env = dict(os.environ)
        env[ADDRESS_VARIABLE] = "127.0.0.1"
        gate = subprocess.Popen(
            [sys.executable, "-c", script, "--zone", "cell_b", "--side", COUNTERPART_SIDE,
             "--wait"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            assert gate.stdout is not None
            first = gate.stdout.readline()
            assert "waiting for 1 robot(s)" in first, first
            assert gate.poll() is None, "it exited with nothing listening"
            listener.listen(1)
            output, _ = gate.communicate(timeout=BACKSTOP_S)
        finally:
            if gate.poll() is None:
                gate.kill()
                gate.wait()
    assert gate.returncode == 0, first + output
    assert "answered" in output
    assert "127.0.0.1" not in first + output


def test_the_gate_refuses_an_unset_address_before_asking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ADDRESS_VARIABLE, raising=False)
    gate = _run_gate({}, "--wait")
    output, _ = gate.communicate(timeout=BACKSTOP_S)
    assert gate.returncode == 2
    assert ADDRESS_VARIABLE in output


def test_the_gate_refuses_a_malformed_address_without_printing_it() -> None:
    gate = _run_gate({ADDRESS_VARIABLE: "robot.example"}, "--wait")
    output, _ = gate.communicate(timeout=BACKSTOP_S)
    assert gate.returncode == 2
    assert ADDRESS_VARIABLE in output and "robot.example" not in output


def test_a_gate_that_is_not_kept_gives_up_and_says_so_without_the_address(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The ceiling path, run in process with the clock and the pause faked."""
    now = [0.0]
    original = reach_gate.wait_for

    def pause(seconds: float) -> None:
        now[0] += seconds

    def fast(targets, *, ceiling_s):
        return original(
            targets, ceiling_s=ceiling_s, probe=lambda _a, _p: False,
            clock=lambda: now[0], pause=pause,
        )

    monkeypatch.setattr(reach_gate, "wait_for", fast)
    monkeypatch.setenv(ADDRESS_VARIABLE, "192.0.2.1")
    code = reach_gate.main(["--zone", "cell_b", "--side", COUNTERPART_SIDE])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code == 1
    assert now[0] >= reach_gate.REACH_CEILING_S
    assert "did not answer" in text and "192.0.2.1" not in text


def test_a_kept_gate_is_still_waiting_long_past_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """R-04: `--wait` has no ceiling - a robot switched on late is still waited for."""
    now = [0.0]
    original = reach_gate.wait_for
    late = 3 * reach_gate.REACH_CEILING_S

    def pause(seconds: float) -> None:
        now[0] += seconds

    def fast(targets, *, ceiling_s):
        assert ceiling_s is None
        return original(
            targets, ceiling_s=ceiling_s, probe=lambda _a, _p: now[0] >= late,
            clock=lambda: now[0], pause=pause,
        )

    monkeypatch.setattr(reach_gate, "wait_for", fast)
    monkeypatch.setenv(ADDRESS_VARIABLE, "192.0.2.1")
    code = reach_gate.main(["--zone", "cell_b", "--side", COUNTERPART_SIDE, "--wait"])
    text = capsys.readouterr().out
    assert code == 0, text
    assert now[0] >= late > reach_gate.REACH_CEILING_S
    assert "answered" in text and "did not answer" not in text
