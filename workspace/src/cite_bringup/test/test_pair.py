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

"""The pair supervisor: the join, the failure rule, and the boundary.

ADR-0047 names three things a change may be promoted on, and this file holds two
of them - the failure rule and the import graph. The third, a run in which both
sides announce readiness and the supervisor reports the pair up, is not something
a unit test can produce; it is evidenced by bringing a pair up.

**The membership test is executed here rather than asserted.** ADR-0047 clause 2
states it as a hypothetical - *if both sides' DDS and both Gazebo transports were
removed from the machine, the supervisor's own code would run unchanged* - and
that is exactly the situation every test below runs in: the sides are `python3`
processes that print a token and then block or exit. Nothing in this file starts
a ROS node, and the supervisor joins them anyway.
"""

from __future__ import annotations

import ast
import io
from pathlib import Path
import sys
import threading

from cite_bringup import pair
from cite_bringup.plan import (
    default_plan_path,
    DOMAIN_BASE_ENV,
    DOMAIN_ENV,
    DomainUnresolvedError,
    load,
    Plan,
    PLANT_SIDE,
    resolve_domain_id,
)
from cite_bringup.readiness import ready_announcement, READY_TOKEN
import pytest
import yaml

PACKAGE = Path(__file__).resolve().parent.parent
SUPERVISOR = PACKAGE / "cite_bringup" / "pair.py"

#: A ceiling short enough that a test which is going to hang fails the suite
#: rather than the job. Two tests below deliberately let it expire, so this is
#: also most of their runtime; every other side either announces at once or is
#: released by the tripwire, so nothing else waits on it.
CEILING_S = 10.0


class _Log(io.StringIO):
    """The supervisor's console, with a tripwire on one line of it.

    Two jobs, and the second is what makes the join testable without a sleep. A
    fake side that exited the instant it announced could be reported as ending
    the pair before the other side's token had been read, so the sides have to
    outlive the join and something has to release them afterwards. The release is
    the supervisor's own "the pair is up" line, which makes the rendezvous the
    fact under test rather than a duration.
    """

    def __init__(self, marker: str | None = None, release: Path | None = None) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._marker = marker
        self._release = release

    def write(self, text: str) -> int:
        with self._lock:
            written = super().write(text)
        if self._marker and self._release is not None and self._marker in text:
            self._release.touch()
        return written


def _fake_side(name: str, script: str) -> pair.SideSpec:
    """Return a side that is not ROS at all: one `python3` process."""
    return pair.SideSpec(name, (sys.executable, "-c", script))


def _announces(name: str, *, then: str = "") -> pair.SideSpec:
    announcement = ready_announcement(name, "cell_a")
    return _fake_side(
        name, f"import os, time\nprint({announcement!r}, flush=True)\n" + then
    )


def _held_until(name: str, release: Path) -> pair.SideSpec:
    """Return a side that announces, then stays up until the pair is joined."""
    return _announces(
        name,
        then=f"while not os.path.exists({str(release)!r}):\n    time.sleep(0.02)\n",
    )


def _blocks(name: str) -> pair.SideSpec:
    """Return a side that runs and never announces: alive, and not ready."""
    return _fake_side(name, "import time\ntime.sleep(600)\n")


def _run(specs: list[pair.SideSpec], *, log: _Log | None = None) -> tuple[int, str]:
    out = _Log() if log is None else log
    code = pair.supervise(specs, ceiling_s=CEILING_S, out=out)
    return code, out.getvalue()


# --- The boundary -------------------------------------------------------------


def _imported_modules(path: Path, seen: set[Path]) -> set[str]:
    """Every module name reachable from `path`, following first-party imports.

    A source walk rather than a check of `sys.modules` after an import, because
    the failure this guards against is a lazy import inside a function: importing
    the module would never reach it, and a reviewer reading the top of the file
    would not either.
    """
    if path in seen:
        return set()
    seen.add(path)
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    for name in sorted(names):
        if not name.startswith("cite_bringup."):
            continue
        local = PACKAGE / "cite_bringup" / (name.split(".", 1)[1] + ".py")
        if local.is_file():
            names |= _imported_modules(local, seen)
    return names


def test_the_supervisor_reaches_the_modules_it_is_supposed_to() -> None:
    """A detector that matched nothing would pass the check below on any tree."""
    reached = _imported_modules(SUPERVISOR, set())
    assert "cite_bringup.plan" in reached
    assert "cite_bringup.readiness" in reached
    # Transitively, through cite_bringup.plan. If this stops holding, the walk
    # has stopped following first-party imports and the check below is blind.
    assert "yaml" in reached


def test_the_supervisors_import_graph_does_not_reach_a_ros_client_library() -> None:
    """ADR-0047 clause 2's structural check, and the reason it exists.

    A promise that a component holds no ROS context is not reviewable. This is,
    and it is what makes the rejected parent-launch option rejectable: a
    supervisor that cannot import `rclpy` cannot express the mistake ADR-0044
    warns about - sequencing a counterpart's managed node from a process whose
    context is on the other side's domain, which hangs forever in silence.
    """
    reached = _imported_modules(SUPERVISOR, set())
    forbidden = sorted(
        name
        for name in reached
        if name == "rclpy" or name.startswith(("rclpy.", "rclcpp", "launch_ros"))
    )
    assert not forbidden, (
        f"{SUPERVISOR.name} reaches {forbidden}. The pair supervisor observes "
        "processes, not graphs (ADR-0047, clause 2)."
    )


def test_the_supervisor_never_sets_an_isolation_in_its_own_environment() -> None:
    # It sets them in a child's, which is what keeps it off both domains. An
    # assignment into `os.environ` here would put the supervisor on one side's
    # domain with nothing in a diff saying so.
    source = SUPERVISOR.read_text()
    assert "os.environ[" not in source
    assert "os.putenv" not in source


# --- The join -----------------------------------------------------------------


def test_a_pair_whose_sides_both_announce_is_reported_up(tmp_path: Path) -> None:
    release = tmp_path / "joined"
    log = _Log(marker="the pair is up", release=release)
    code, text = _run(
        [_held_until("plant", release), _held_until("counterpart", release)], log=log
    )
    assert "the pair is up" in text
    assert "plant: ready=True" in text and "counterpart: ready=True" in text
    # Both sides then ended, which ends the pair. That status is distinct from
    # the one a pair that never came up returns: "it ran and lost a side" and
    # "it never started" are different answers.
    assert code == pair.PAIR_ENDED


def test_both_sides_output_is_forwarded_labelled_by_side() -> None:
    # The console cost ADR-0047 records. A developer loses the plain single
    # launch console and gets two interleaved streams, so each line has to say
    # which side it came from.
    specs = [
        _fake_side("plant", "print('hello from a side')"),
        _fake_side("counterpart", "print('and the other')"),
    ]
    _, text = _run(specs)
    assert "[plant] hello from a side" in text
    assert "[counterpart] and the other" in text


def test_a_side_that_exits_before_announcing_ends_the_pair() -> None:
    code, text = _run([_fake_side("plant", "raise SystemExit(7)"), _blocks("counterpart")])
    assert code == 1
    assert "plant exited 7" in text
    # The counterpart is stopped rather than left running as half a pair: a
    # scenario asserting against a pair could otherwise pass on one side alone.
    assert "stopping counterpart" in text


def test_both_statuses_are_reported_and_not_only_the_first() -> None:
    code, text = _run(
        [
            _fake_side("plant", "raise SystemExit(7)"),
            _fake_side("counterpart", "raise SystemExit(9)"),
        ]
    )
    assert code == 1
    assert "plant: ready=False status=7" in text
    assert "counterpart: ready=False status=9" in text


def test_a_side_that_never_announces_and_never_exits_fires_the_ceiling() -> None:
    """The row that is the reason a ceiling exists at all.

    ADR-0044 records the silent, indefinite hang a mis-wired cross-domain
    lifecycle client produces. Without a ceiling this supervisor would inherit
    that silence; with one it becomes a diagnosis that says what happened rather
    than "timeout".
    """
    code, text = _run([_announces("plant", then="time.sleep(600)\n"), _blocks("counterpart")])
    assert code == 1
    assert "counterpart never announced readiness and never exited" in text
    assert "stopping plant" in text


def test_a_side_that_announces_the_other_sides_name_is_refused() -> None:
    # A launch given the wrong `side:=` would otherwise announce readiness for a
    # side the supervisor believes is the other one. The supervisor is the only
    # thing positioned to catch that, and it catches it for free.
    announcement = ready_announcement("plant", "cell_a")
    wrong = _fake_side(
        "counterpart",
        f"import time\nprint({announcement!r}, flush=True)\ntime.sleep(600)\n",
    )
    code, text = _run([_announces("plant", then="time.sleep(600)\n"), wrong])
    assert code == 1
    assert "announced readiness as 'plant'" in text


def test_readiness_is_the_token_and_not_the_absence_of_a_crash() -> None:
    # Liveness is not readiness. A side that is running and has not reached the
    # end of its gate chain has announced nothing, and the pair is not up.
    code, text = _run([_blocks("plant"), _blocks("counterpart")])
    assert code == 1
    assert "the pair is up" not in text
    assert READY_TOKEN not in text


# --- What the supervisor asks the plan for ------------------------------------


def _paired_plan(tmp_path: Path) -> Plan:
    document = yaml.safe_load(default_plan_path("cell_a").read_text())
    document["plan"]["sides"].append(
        {
            "name": "counterpart",
            "gz_partition": "cite/cell_a/counterpart",
            "domain_offset": 1,
        }
    )
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return load(path)


def test_each_side_is_given_the_domain_the_resolver_returns(tmp_path: Path) -> None:
    plan = _paired_plan(tmp_path)
    specs = pair.side_specs(plan, {DOMAIN_BASE_ENV: "41"})
    assert [spec.name for spec in specs] == [PLANT_SIDE, "counterpart"]
    assert specs[0].env == {DOMAIN_ENV: str(resolve_domain_id(plan, PLANT_SIDE, 41))}
    assert specs[1].env == {DOMAIN_ENV: str(resolve_domain_id(plan, "counterpart", 41))}
    assert specs[0].env[DOMAIN_ENV] != specs[1].env[DOMAIN_ENV]


def test_the_side_is_named_to_the_launch_rather_than_implied(tmp_path: Path) -> None:
    plan = _paired_plan(tmp_path)
    for spec in pair.side_specs(plan, {DOMAIN_BASE_ENV: "41"}):
        assert f"side:={spec.name}" in spec.argv
        assert f"zone:={plan.zone}" in spec.argv


def test_no_side_is_given_a_partition_by_the_supervisor(tmp_path: Path) -> None:
    # The launch derives it from the plan and refuses without it. Setting it here
    # too would be a second statement of a generated name (P1), and the two could
    # disagree with nothing reporting it.
    plan = _paired_plan(tmp_path)
    for spec in pair.side_specs(plan, {DOMAIN_BASE_ENV: "41"}):
        assert set(spec.env) == {DOMAIN_ENV}


def test_an_untwinned_zone_is_refused_rather_than_given_a_second_side(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Whether a zone runs as a pair is an L0 fact. Bring-up does not invent one,
    # and it must not report the missing base instead, so the base is present.
    monkeypatch.setenv(DOMAIN_BASE_ENV, "42")
    assert pair.main(["--zone", "cell_a"]) == 1
    assert "declares 1 side(s)" in capsys.readouterr().err


def test_the_supervisor_needs_a_base_it_did_not_read_from_the_ambient_domain(
    tmp_path: Path,
) -> None:
    plan = _paired_plan(tmp_path)
    with pytest.raises(DomainUnresolvedError, match=DOMAIN_BASE_ENV):
        pair.side_specs(plan, {DOMAIN_ENV: "41"})
