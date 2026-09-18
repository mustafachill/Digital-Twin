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

import argparse
import ast
from dataclasses import replace
import io
import os
from pathlib import Path
import queue
import signal
import sys
import threading
import time

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
from cite_bringup.readiness import (
    announced_boundary,
    announced_side,
    boundary_announcement,
    ready_announcement,
    READY_TOKEN,
)
import pytest
import yaml

PACKAGE = Path(__file__).resolve().parent.parent
SUPERVISOR = PACKAGE / "cite_bringup" / "pair.py"
SUPERVISOR_MODULE = "cite_bringup.pair"

#: Every first-party package's sources, which is what makes the import walk below
#: able to follow `from cite_runtime import runtime` out of this package. One
#: level up from this package, because that is where the workspace puts them all.
SOURCE_ROOT = PACKAGE.parent

#: A ceiling short enough that a test which is going to hang fails the suite
#: rather than the job. Two tests below deliberately let it expire, so this is
#: also most of their runtime; every other side either announces at once or is
#: released by the tripwire, so nothing else waits on it.
CEILING_S = 10.0

#: The zone every fixture in this file is built from. Its generated plan is read
#: and copied into a tempdir; nothing here starts a cell, of this zone or any
#: other.
ZONE = "cell_a"

#: The boundary's ceiling here, shorter than the sides' because everything it
#: covers in this file is a `python3` process that starts in milliseconds. One
#: test below deliberately lets it expire and that expiry is the test's runtime.
BOUNDARY_S = 5.0

#: How long a test is willing to hold a supervisor that should have returned.
#:
#: **A ceiling on THIS TEST, and not on anything it is testing.** Nothing under
#: test measures itself against it, no assertion reads it, and no production
#: value is compared to it. It exists because the failure mode of every ordering
#: test below is a HANG rather than a wrong answer: a supervisor that never
#: starts the boundary leaves a side waiting on a console line that never
#: arrives, and the suite then reports `ament_add_pytest_test`'s timeout with no
#: sentence in it. A mutation sweep on 2026-09-18 made exactly that happen twice.
#:
#: Comfortably above `CEILING_S`, because two tests below deliberately spend that
#: whole ceiling and are not hanging when they do.
BACKSTOP_S = 30.0

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


def _announces(name: str, *, before: str = "", then: str = "") -> pair.SideSpec:
    """Return a side that announces its readiness, optionally saying more first.

    ``before`` runs ahead of the announcement rather than after it, and that
    ordering is load-bearing wherever a test asserts on a side's output: the
    supervisor forwards a line and only then looks at it for the token, so
    anything printed before the announcement has certainly been forwarded by the
    time the join completes. Printed after it, it is a race with the stop.
    """
    announcement = ready_announcement(name, ZONE)
    return _fake_side(
        name,
        "import os, time\n" + before + f"print({announcement!r}, flush=True)\n" + then,
    )


def _held_until(name: str, release: Path, *, before: str = "") -> pair.SideSpec:
    """Return a side that announces, then stays up until the pair is joined."""
    return _announces(
        name,
        before=before,
        then=f"while not os.path.exists({str(release)!r}):\n    time.sleep(0.02)\n",
    )


def _blocks(name: str) -> pair.SideSpec:
    """Return a side that runs and never announces: alive, and not ready."""
    return _fake_side(name, "import time\ntime.sleep(600)\n")


def _run(specs: list[pair.SideSpec], *, log: _Log | None = None) -> tuple[int, str]:
    out = _Log() if log is None else log
    code = pair.supervise(specs, ceiling_s=CEILING_S, out=out)
    return code, out.getvalue()

def _supervise_within(
    seconds: float,
    specs: list[pair.SideSpec],
    *,
    if_it_hangs: str = "",
    log: _Log | None = None,
    **kwargs,
) -> tuple[int, str]:
    """Run the supervisor on a worker thread, so a hang fails with a sentence.

    **Every assertion below is still the supervisor's own behaviour; what this
    adds is that a supervisor which does not return fails the test instead of the
    job.** Without it a mutation that stops the boundary being started at all
    leaves two fake sides waiting on a console line that never comes, and what
    the suite reports is a bare ctest timeout - a number, from which nobody can
    tell which test hung or why. A wall clock is the only instrument that catches
    "it never returned", and it is not a ceiling on anything under test: it reads
    no production constant and nothing compares itself to it.

    The worker thread is deliberate twice over. `supervise` skips its signal
    handlers off the main thread, which it documents, so this drives exactly the
    join and the failure rule; and a thread that IS stuck can be abandoned, where
    a stuck call in the test's own thread cannot.

    ``if_it_hangs`` is what a hang here would mean, in the words of whoever wrote
    the test. A backstop that fires with nothing but a duration is only half an
    instrument.
    """
    out = _Log() if log is None else log
    finished: dict[str, object] = {}

    def run() -> None:
        try:
            finished["code"] = pair.supervise(specs, out=out, **kwargs)
        except BaseException as error:  # noqa: BLE001 - re-raised below
            finished["error"] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise AssertionError(
            f"the supervisor had not returned {seconds:g} s after the pair it was "
            "given should have ended. " + (if_it_hangs or "It did not hang before.")
        )
    if "error" in finished:
        raise finished["error"]  # type: ignore[misc]
    return finished["code"], out.getvalue()  # type: ignore[return-value]


# --- The boundary -------------------------------------------------------------


def _source_of(name: str) -> Path | None:
    """Return the file a first-party module name lives in, or None if it is not one.

    Every first-party package in this workspace is `<pkg>/<pkg>/<module>.py`, so
    a dotted name resolves without importing anything. Resolving by NAME rather
    than by a prefix match is the point: a walk that only followed
    `"cite_bringup."` stopped at this package's boundary, and `cite_runtime` is
    one import away from `rclpy` and is an `exec_depend` of this package.
    """
    parts = name.split(".")
    package = SOURCE_ROOT / parts[0] / parts[0]
    if not package.is_dir():
        return None
    if len(parts) == 1:
        candidate = package / "__init__.py"
    else:
        candidate = package.joinpath(*parts[1:]).with_suffix(".py")
    return candidate if candidate.is_file() else None


def _absolute(node: ast.ImportFrom, module: str) -> str | None:
    """Resolve one `from ... import ...` to an absolute module name.

    Relative imports are resolved rather than skipped. `from .readiness_witness
    import ...` inside `cite_bringup.pair` names `cite_bringup.readiness_witness`,
    and a walk that skipped `node.level != 0` would not see it - which is the
    cheapest edit there is for putting `rclpy` behind this check without tripping
    it.
    """
    if node.level == 0:
        return node.module
    owner = module.split(".")[:-1]
    if node.level > 1:
        owner = owner[: -(node.level - 1)]
    if not owner:
        return None
    return ".".join(owner + ([node.module] if node.module else []))


def _imported_modules(path: Path, seen: set[Path], module: str) -> set[str]:
    """Every module name reachable from `path`, following first-party imports.

    A source walk rather than a check of `sys.modules` after an import, because
    the failure this guards against is a lazy import inside a function: importing
    the module would never reach it, and a reviewer reading the top of the file
    would not either.

    ``module`` is the dotted name of the module `path` holds, and it is what a
    relative import is resolved against.

    **`from <package> import <name>` contributes `<package>.<name>` as well as
    `<package>`**, because that spelling is how a submodule is usually imported:
    `ast.ImportFrom.module` for `from cite_bringup import readiness_witness` is
    the bare `"cite_bringup"`, and the module that actually gets imported is
    named nowhere else in the node. Names that turn out to be attributes rather
    than modules resolve to no file and simply go no further.
    """
    if path in seen:
        return set()
    seen.add(path)
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(node, module)
            if base is None:
                continue
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    reached = set(names)
    for name in sorted(names):
        source = _source_of(name)
        if source is not None:
            reached |= _imported_modules(source, seen, name)
    return reached


def _reached_from_supervisor() -> set[str]:
    return _imported_modules(SUPERVISOR, set(), SUPERVISOR_MODULE)


def test_the_supervisor_reaches_the_modules_it_is_supposed_to() -> None:
    """A detector that matched nothing would pass the check below on any tree."""
    reached = _reached_from_supervisor()
    assert "cite_bringup.plan" in reached
    assert "cite_bringup.readiness" in reached
    # Transitively, through cite_bringup.plan. If this stops holding, the walk
    # has stopped following first-party imports and the check below is blind.
    assert "yaml" in reached


def test_the_walk_follows_a_first_party_import_out_of_this_package() -> None:
    """The narrowing that would make the check below blind, one package over.

    The check below is only as good as the walk that feeds it, and a walk that
    stops at this package's own boundary passes a supervisor that imports `rclpy`
    through a sibling. That is not hypothetical: this branch added `cite_runtime`
    as an `exec_depend` of `cite_bringup`, and `cite_runtime/runtime.py` imports
    `rclpy` at module scope - so `from cite_runtime import runtime` is the
    shortest violating edit anyone could make here.

    Asserted as the two halves of that hop, so that a narrowing fails HERE with a
    reason rather than turning the check below green:

    1. the walk resolves a first-party module outside this package and follows it
       to `rclpy`; and
    2. a module inside this package that makes exactly that import is seen to
       reach it.

    Together those are *the walk reaches `rclpy` through `cite_runtime`*, which is
    the property the check below depends on and cannot demonstrate about itself.
    """
    hop = "cite_runtime.runtime"
    source = _source_of(hop)
    assert source is not None, (
        f"{hop} did not resolve to a file under {SOURCE_ROOT}. If the workspace "
        "layout changed, fix the resolver rather than deleting this test."
    )
    assert "rclpy" in _imported_modules(source, set(), hop)

    witness = PACKAGE / "cite_bringup" / "readiness_witness.py"
    reached = _imported_modules(witness, set(), "cite_bringup.readiness_witness")
    assert hop in reached, (
        "the walk no longer follows `from cite_runtime import runtime`, so the "
        "import-graph check below cannot see a ROS client library reached "
        "through a sibling package."
    )


def test_the_supervisors_import_graph_does_not_reach_a_ros_client_library() -> None:
    """ADR-0047 clause 2's structural check, and the reason it exists.

    A promise that a component holds no ROS context is not reviewable. This is,
    and it is what makes the rejected parent-launch option rejectable: a
    supervisor that cannot import `rclpy` cannot express the mistake ADR-0044
    warns about - sequencing a counterpart's managed node from a process whose
    context is on the other side's domain, which hangs forever in silence.
    """
    reached = _reached_from_supervisor()
    forbidden = sorted(
        name
        for name in reached
        if name == "rclpy" or name.startswith(("rclpy.", "rclcpp", "launch_ros"))
    )
    assert not forbidden, (
        f"{SUPERVISOR.name} reaches {forbidden}. The pair supervisor observes "
        "processes, not graphs (ADR-0047, clause 2)."
    )


#: The names an in-place environment mutation is spelled with. `os.environ` is a
#: mapping, so setting one variable in it is a subscript assignment and setting
#: several is one of these methods; `os.putenv` reaches the same place one layer
#: down.
_MUTATORS = frozenset({"update", "setdefault", "pop", "popitem", "clear"})


def _is_environ(node: ast.expr) -> bool:
    """Whether an expression is a process environment this module could mutate.

    `os.environ` under any spelling of the attribute, and a bare `environ` - which
    is not pedantry here: :func:`pair.supervise` takes `environ` as a parameter
    and DEFAULTS IT TO `os.environ`, so `environ.update(...)` anywhere in this
    module sets the supervisor's own environment exactly as `os.environ.update`
    would.
    """
    if isinstance(node, ast.Attribute):
        return node.attr == "environ"
    return isinstance(node, ast.Name) and node.id == "environ"


def _environment_writes(source: str) -> list[str]:
    """Every place this source sets a variable in a process environment it holds."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Subscript) and _is_environ(target.value):
                found.append(f"line {node.lineno}: assignment into an environment")
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in ("putenv", "unsetenv"):
            found.append(f"line {node.lineno}: os.{node.func.attr}")
        elif node.func.attr in _MUTATORS and _is_environ(node.func.value):
            found.append(f"line {node.lineno}: environment .{node.func.attr}()")
    return found


def test_the_supervisor_never_sets_an_isolation_in_its_own_environment() -> None:
    """ADR-0047 clause 2's other half, and it has to be a walk rather than a scan.

    It sets `ROS_DOMAIN_ID` in a CHILD's environment, which is what keeps it off
    both domains. An assignment into its own would put the supervisor on one
    side's domain with nothing in a diff saying so.

    **A substring search for `"os.environ["` does not catch that.** `os.environ`
    is a mapping, so the natural way to set several variables at once is
    `os.environ.update(spec.env)` - one line, at the top of `_start`, that reads
    like the line under it and that a text scan passes.
    """
    writes = _environment_writes(SUPERVISOR.read_text())
    assert not writes, (
        f"{SUPERVISOR.name} writes to its own environment at {writes}. The "
        "supervisor sets a side's isolation in that side's child environment and "
        "never in its own (ADR-0047, clause 2)."
    )


def test_the_environment_guard_catches_the_edit_a_text_scan_missed() -> None:
    """A guard that matched nothing would pass the check above on any source.

    Every line here is a real way to put the supervisor on a side's domain, and
    the last three are the ones the scan this replaced let through.
    """
    for statement in (
        "import os\nos.environ['ROS_DOMAIN_ID'] = '43'\n",
        "import os\nos.putenv('ROS_DOMAIN_ID', '43')\n",
        "import os\nos.environ.update({'ROS_DOMAIN_ID': '43'})\n",
        "import os\nos.environ.setdefault('ROS_DOMAIN_ID', '43')\n",
        "def f(environ):\n    environ.update({'ROS_DOMAIN_ID': '43'})\n",
    ):
        assert _environment_writes(statement), statement
    # And is quiet on what the supervisor actually does: build a child's
    # environment as a copy it owns.
    assert not _environment_writes(
        "import os\n"
        "def f(spec, environ):\n"
        "    env = dict(environ)\n"
        "    env.update(spec.env)\n"
        "    return env\n"
    )


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


def test_both_sides_output_is_forwarded_labelled_by_side(tmp_path: Path) -> None:
    """The console cost ADR-0047 records, and it has to be asserted on a join.

    A developer loses the plain single-launch console and gets two interleaved
    streams, so each line has to say which side it came from.

    **Both sides are held open until the pair is up, rather than printing once
    and exiting**, and that is the whole difference between this test and a
    failure that only appears under load. `_join` returns on the FIRST exit and
    the supervisor then stops the other side, so two sides that print and exit
    race: if the second interpreter has not reached its `print` when it is
    signalled, the line this asserts on never exists. Measured at 5 failures in 6
    runs on a loaded Linux host and 0 in 12 idle. What the failure rule
    guarantees is that both sides are still running at the join, so both lines
    are printed before the announcement and read before the join completes.
    """
    release = tmp_path / "joined"
    log = _Log(marker="the pair is up", release=release)
    specs = [
        _held_until("plant", release, before="print('hello from a side', flush=True)\n"),
        _held_until("counterpart", release, before="print('and the other', flush=True)\n"),
    ]
    _, text = _run(specs, log=log)
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
    """The clause is about REPORTING, and both halves of it are deterministic.

    Both sides get a line, and the side whose exit ended the pair carries its own
    code, because that code is the event the join returned on. The other side's
    number is whatever the supervisor found when it stopped it, and asserting a
    particular value there would be asserting a race: two processes that exit at
    the same instant are stopped and reaped in an order nothing fixes.
    """
    code, text = _run(
        [
            _fake_side("plant", "raise SystemExit(7)"),
            _fake_side("counterpart", "raise SystemExit(9)"),
        ]
    )
    assert code == 1
    reported = [line for line in text.splitlines() if ": ready=" in line]
    assert len(reported) == 2, reported
    assert any("status=7" in line or "status=9" in line for line in reported)


def test_an_exit_already_observed_is_not_replaced_by_the_stop() -> None:
    """The drain, on its own, because a running pair cannot show it reliably.

    Two sides that fail for one reason fail together, and a side stopped by the
    supervisor reports the stop rather than what it was reporting - ADR-0038's
    lesson one level up. Anything already on the queue is that evidence, so it is
    read before anything is signalled. Whether it IS on the queue at that instant
    is a race; that it is used when it is, is not.
    """
    events: queue.Queue = queue.Queue()
    sides = [
        pair._Side(pair.SideSpec("plant", ()), None),
        pair._Side(pair.SideSpec("counterpart", ()), None),
    ]
    events.put(("exit", sides[0], 7))
    events.put(("exit", sides[1], 9))
    pair._drain(events)
    assert [side.status for side in sides] == [7, 9]
    assert events.empty()


def _leaves_a_grandchild(name: str, pidfile: Path) -> pair.SideSpec:
    """Return a side that starts a process of its own and then exits.

    The shape of a real side whose launch died on a signal: the launch is gone
    and everything it started is reparented and still running. The grandchild
    gets its own standard streams so that this side's pipe reaches EOF when the
    side exits, exactly as a launch's does.
    """
    grandchild = (
        "import os, time\n"
        f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(600)\n"
    )
    return _fake_side(
        name,
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}],\n"
        "    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL)\n"
        f"while not os.path.exists({str(pidfile)!r}):\n    time.sleep(0.02)\n"
        "raise SystemExit(7)\n",
    )


def test_a_side_that_has_already_exited_still_has_its_group_signalled(
    tmp_path: Path,
) -> None:
    """The orphan this project already knows the cost of, one process group up.

    `_stop` returns at once for a side whose launch has already gone, so before
    the sweep nothing ever signalled that side's group. The scenario is not
    hypothetical: this repository documents `move_group`, `skill_server`,
    `parameter_bridge` and `gz` all dying on a signal at teardown, and a launch
    that dies takes its own supervision with it. The pair then stops the
    counterpart cleanly, reports both statuses and exits - while that side's
    Gazebo server keeps running, holding that side's `GZ_PARTITION`.

    Driven with a `python3` grandchild rather than a `gz sim`, because what is
    under test is whether the group is reached at all.
    """
    pidfile = tmp_path / "grandchild.pid"
    code, text = _run([_leaves_a_grandchild("plant", pidfile), _blocks("counterpart")])
    assert code == 1
    assert "plant exited 7" in text
    orphan = int(pidfile.read_text())

    # The sweep waits for the group to empty before it returns, so this is a
    # bounded confirmation rather than the fact under test. A pid that outlives
    # its reaper is reaped by init, so the lookup below is the whole check.
    deadline = time.monotonic() + CEILING_S
    while time.monotonic() < deadline:
        try:
            os.kill(orphan, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(orphan, signal.SIGKILL)
    raise AssertionError(
        f"the process {orphan} that plant left behind was still running after "
        "the pair ended. A side whose launch has already exited never has its "
        "process group signalled unless the sweep is unconditional."
    )


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
    announcement = ready_announcement("plant", ZONE)
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
    document = yaml.safe_load(default_plan_path(ZONE).read_text())
    # See the note on the same fixture in `test_simulation_launch.py`: built from
    # whatever the generated plan declares, so that a checkout flipped to `pair`
    # for a run does not fail these on the fixture.
    sides = document["plan"]["sides"]
    if not any(side["name"] == "counterpart" for side in sides):
        sides.append(
            {
                "name": "counterpart",
                "gz_partition": "cite/cell_a/counterpart",
                "domain_offset": 1,
            }
        )
    for manager in document["plan"]["controller_managers"]:
        # Both of the things pairing adds, not one. A plan naming a side that no
        # asset states a backend for is refused at `load` (it is invisible to
        # every gate that asks an asset what it loads), and it is a document no
        # generator emits: ADR-0041 Decision 3's fallback makes an instance that
        # writes no `counterpart_backend` in L0 load the same plugin on both
        # sides, so the plan states the backend of every side that exists. The
        # same shape as `_paired_document` in `test_plan.py`.
        manager.setdefault("counterpart_backend", manager["backend"])
        manager.setdefault(
            "counterpart_commands_physical_hardware",
            manager["commands_physical_hardware"],
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Whether a zone runs as a pair is an L0 fact. Bring-up does not invent one.

    Driven against a plan written here rather than against whatever is on disk,
    and that is not fussiness: `main` STARTS SIDES. Read from the tree, this test
    would launch two real cells on a checkout whose model had been flipped to
    `pair` for a run - which is what it did, once, and it took two minutes and a
    SIGTERM to find out.
    """
    document = yaml.safe_load(default_plan_path(ZONE).read_text())
    document["plan"]["sides"] = [
        side for side in document["plan"]["sides"] if side["name"] == PLANT_SIDE
    ]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    monkeypatch.setattr(pair, "default_plan_path", lambda zone="cell_a": path)
    # Present, so that the refusal is the one about sides and not the one about
    # a base the deployment did not supply.
    monkeypatch.setenv(DOMAIN_BASE_ENV, "42")
    assert pair.main(["--zone", "cell_a"]) == 1
    assert "declares 1 side(s)" in capsys.readouterr().err


def test_the_pair_takes_the_same_argument_spelling_the_solo_path_does() -> None:
    """`./scripts/sim --pair line:=true` is the same request as without `--pair`.

    The solo path is `ros2 launch`, so `./scripts/sim --headless line:=true` is
    what the operator documentation shows. `./scripts/sim` forwards whatever it
    does not recognise, so the pair path used to answer the documented spelling
    with an argparse error and a paired line could not be started at all.
    """
    parser = argparse.ArgumentParser()
    assert pair._flags(["zone:=cell_b", "line:=true"], parser) == [
        "--zone",
        "cell_b",
        "--line",
    ]
    # False is the default, so it contributes no flag rather than an error.
    assert pair._flags(["line:=false"], parser) == []
    # And this parser's own spelling still works, unchanged.
    assert pair._flags(["--line", "--ceiling", "5"], parser) == [
        "--line",
        "--ceiling",
        "5",
    ]


def test_a_launch_argument_a_pair_does_not_take_is_named_rather_than_ignored() -> None:
    # Silently dropping `side:=counterpart` would start a pair that looks like
    # what was asked for and is not: the supervisor decides both sides.
    parser = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        pair._flags(["side:=counterpart"], parser)
    with pytest.raises(SystemExit):
        pair._flags(["line:=yes"], parser)


def test_the_supervisor_needs_a_base_it_did_not_read_from_the_ambient_domain(
    tmp_path: Path,
) -> None:
    plan = _paired_plan(tmp_path)
    with pytest.raises(DomainUnresolvedError, match=DOMAIN_BASE_ENV):
        pair.side_specs(plan, {DOMAIN_ENV: "41"})


def test_a_pair_with_no_zone_named_is_refused_before_anything_starts(capsys) -> None:
    """`--zone` is required and has no default (ADR-0056 decision 4).

    It defaulted to `cell_a` until then, so `./scripts/sim --pair` with no zone
    started two full simulations of whichever cell that default named — and the
    supervisor starts one readiness witness per side, each of which declares its
    own zone with no default, so the value this argument supplies is the only
    one anybody states.

    Asserted through `main` rather than through a parser built here, because a
    parser built here would keep answering after `main` stopped asking it.
    Nothing is started: argparse exits during parsing, before the plan is read.
    """
    with pytest.raises(SystemExit) as exit_code:
        pair.main(["--headless"])
    assert exit_code.value.code == 2
    assert "--zone" in capsys.readouterr().err


def test_a_pair_zone_is_taken_from_the_launch_spelling_too(capsys) -> None:
    """Accept the launch spelling too, since that is what `./scripts/sim` forwards.

    Without this, the no-default rule and the argument rewriting could each be
    correct while the pair path refused the only spelling that reaches it.
    """
    parser = argparse.ArgumentParser()
    assert pair._flags(["zone:=cell_b"], parser) == ["--zone", "cell_b"]


# --- The twin boundary, the third participant ---------------------------------
#
# ADR-0057. Every boundary below is a `python3` process too: what is under test
# is the supervision - when it is started, what it is given, and what its
# failures do to the pair - and none of that is L5. A rig that started the real
# boundary here would need two domains and a plan that declares a counterpart,
# and would be testing `cite_twin`.


def _fake_boundary(tmp_path: Path, script: str) -> pair.SideSpec:
    """Return the REAL boundary spec with a `python3` process for its command.

    Everything about the participant except what to run comes from
    `pair.boundary_spec` — which token it announces, what that token has to say,
    which argument decided it, what its silence means — so a change to any of
    them reaches these tests instead of being restated here and agreeing with
    nothing (P1). A fake that declared its own token would keep passing after the
    supervisor stopped reading it.
    """
    real = pair.boundary_spec(_paired_plan(tmp_path), tmp_path / "plan.yaml")
    return replace(real, argv=(sys.executable, "-c", script))


def _boundary_announces(
    tmp_path: Path, *, zone: str = ZONE, then: str = ""
) -> pair.SideSpec:
    """Return a boundary that announces `zone` — by default the one it is for."""
    announcement = boundary_announcement(zone)
    return _fake_boundary(
        tmp_path,
        "import os, time\n"
        "print('the boundary process is running', flush=True)\n"
        f"print({announcement!r}, flush=True)\n" + then,
    )


def _run_with_boundary(
    specs: list[pair.SideSpec], boundary: pair.SideSpec, *, log: _Log | None = None
) -> tuple[int, str]:
    out = _Log() if log is None else log
    code = pair.supervise(
        specs,
        boundary=boundary,
        ceiling_s=CEILING_S,
        boundary_ceiling_s=BOUNDARY_S,
        out=out,
    )
    return code, out.getvalue()


def test_the_boundary_is_started_after_the_join_and_not_before(
    tmp_path: Path,
) -> None:
    """The event ADR-0057 reuses, and the ordering is the whole decision.

    A boundary started before both sides answer has nothing to connect to. The
    supervisor is the only component that knows they have, so it starts it on
    that fact rather than on an interval or on an operator's eye.

    Read off the console rather than off a clock: the supervisor writes "the pair
    is up" from the join before it starts anything, and the boundary's own first
    line cannot reach the same log until it has been started. Both writes are
    serialized by `_Log`, so their order in the text is their order in time.
    """
    release = tmp_path / "joined"
    log = _Log(marker="the twin boundary announced", release=release)
    held = f"while not os.path.exists({str(release)!r}):\n    time.sleep(0.02)\n"
    code = pair.supervise(
        [_held_until("plant", release), _held_until("counterpart", release)],
        boundary=_boundary_announces(tmp_path, then=held),
        ceiling_s=CEILING_S,
        boundary_ceiling_s=BOUNDARY_S,
        out=log,
    )
    text = log.getvalue()
    assert "the pair is up" in text
    assert "[boundary] the boundary process is running" in text
    assert text.index("the pair is up") < text.index("[boundary] the boundary")
    # And the boundary is a participant of the join rather than something
    # started beside it: the pair is not reported complete until it answers too.
    assert text.index("[boundary] the boundary") < text.index(
        "the twin boundary announced readiness"
    )
    assert "boundary: ready=True" in text
    assert code == pair.PAIR_ENDED


def test_a_join_that_never_completes_starts_no_boundary(tmp_path: Path) -> None:
    """The other half of "after the join": a pair that never joins starts nothing.

    The strongest form of "not before", because a boundary that is never started
    prints nothing at all - there is no ordering to get right and no window to
    lose a race in.
    """
    code, text = _run_with_boundary(
        [_announces("plant", then="time.sleep(600)\n"), _blocks("counterpart")],
        _boundary_announces(tmp_path, then="time.sleep(600)\n"),
    )
    assert code == 1
    assert "counterpart never announced readiness and never exited" in text
    assert "starting the twin boundary" not in text
    assert "[boundary]" not in text
    # And nothing is reported about a participant that was never started.
    assert "boundary: ready=" not in text


def test_the_boundary_is_given_the_zone_and_the_plan_and_nothing_else(
    tmp_path: Path,
) -> None:
    """ADR-0057's promotion clause 3, as a test that fails if it passes more.

    **Starting a process is not deciding what crosses**, and the two facts the
    supervisor hands over are ones it already holds. `divergence_period_s` is the
    argument this asserts the absence of by name: it is a ROS parameter, so
    passing it would mean appending `--ros-args`, and a supervisor that stated a
    value L5 declares would be that value in two places.
    """
    plan = _paired_plan(tmp_path)
    path = tmp_path / "plan.yaml"
    spec = pair.boundary_spec(plan, path)
    assert plan.zone == ZONE

    assert spec.argv == (
        "ros2",
        "run",
        "cite_twin",
        "twin_boundary.py",
        "--zone",
        plan.zone,
        "--plan",
        str(path),
    )
    # Asserted as a set as well as a sequence, so that an added option fails here
    # even if it is inserted where the tuple comparison above reads plausibly.
    assert [token for token in spec.argv if token.startswith("--")] == [
        "--zone",
        "--plan",
    ]
    assert "--ros-args" not in spec.argv
    assert "divergence_period_s" not in " ".join(spec.argv)
    # No environment overlay: a side is told which domain it is on because a side
    # is one domain. The boundary holds a context on both and resolves each from
    # the plan, so there is no single value that would be right for it, and one
    # set here would put it on a side.
    assert spec.env == {}


def _identifiers(source: str) -> set[str]:
    """Every word the SOURCE names something with, split at underscores.

    Identifiers only, and never string literals: this module's refusals are
    written in English and say things like "set `twin: {sides: pair}` in the L0
    model", and a scan that read those would be scanning prose. What a
    supervisor that had started deciding would have is a name for what it was
    deciding about.
    """
    words: set[str] = set()

    def add(name: str | None) -> None:
        if name:
            words.update(name.lower().split("_"))

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            add(node.id)
        elif isinstance(node, ast.Attribute):
            add(node.attr)
        elif isinstance(node, ast.arg):
            add(node.arg)
        elif isinstance(node, ast.keyword):
            add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            add(node.name)
        elif isinstance(node, ast.alias):
            add(node.asname or node.name)
    return words


def test_the_supervisor_gains_no_branch_on_what_crosses() -> None:
    """The line ADR-0057 draws, checked in the source rather than promised.

    The record says the supervisor "learns nothing about modes, routing, skills
    or divergence, and gains no branch on any of them", and admits that a
    sentence in a record is weaker than a mechanism. This is the cheapest
    mechanism there is: the vocabulary of what crosses is not a word this module
    names anything with. It is a scan and not a proof - a branch could be written
    in words it does not know - but it catches the edit anybody would actually
    make, which is a parameter or a flag named after the thing it decides.
    """
    named = _identifiers(SUPERVISOR.read_text())
    forbidden = sorted(
        named
        & {"mode", "modes", "routing", "skill", "skills", "divergence", "custody"}
    )
    assert not forbidden, (
        f"the pair supervisor now names {forbidden}. Starting a process is not "
        "deciding what crosses (ADR-0057); a supervisor that decides is a new "
        "decision and needs its own record."
    )


def test_the_vocabulary_guard_would_catch_the_edit_it_is_for() -> None:
    """A guard that matched nothing would pass the check above on any source."""
    assert "mode" in _identifiers("def supervise(specs, mode=None):\n    pass\n")
    assert "divergence" in _identifiers("divergence_period_s = 1.0\n")
    # And it is quiet on the prose the refusals above are written in.
    assert "mode" not in _identifiers("print('set it in the L0 model')\n")


def test_a_boundary_that_never_announces_fails_the_pair_naming_the_boundary(
    tmp_path: Path,
) -> None:
    """ADR-0057's promotion clause 2, and the ceiling its correction asks for.

    The join drops the sides' ceiling on the iteration it completes, so without
    one of its own the boundary would be covered by nothing and a boundary that
    hung would leave the supervisor waiting for ever. What it reports has to name
    the boundary: both sides are up and working, and a diagnosis pointing at one
    of them sends the reader to a cell that is fine.
    """
    code, text = _run_with_boundary(
        [
            _announces("plant", then="time.sleep(600)\n"),
            _announces("counterpart", then="time.sleep(600)\n"),
        ],
        _fake_boundary(tmp_path, "import time\ntime.sleep(600)\n"),
    )
    assert code == 1
    assert "boundary never announced readiness and never exited" in text
    # The sides are up, and nothing says otherwise.
    assert "plant never announced" not in text
    assert "counterpart never announced" not in text
    assert "plant: ready=True" in text and "counterpart: ready=True" in text
    # And both of them are stopped rather than left running with no boundary: a
    # pair whose boundary is not there cannot answer for the pair at all.
    assert "stopping plant" in text and "stopping counterpart" in text


def test_a_boundary_that_exits_ends_the_pair_reported_as_the_boundarys(
    tmp_path: Path,
) -> None:
    """`twin_boundary` exits 0 or 2 and never 1, so nothing here reads a 1.

    Every refusal it makes - a zone with one side, a plan that disagrees with
    the zone it was given, a side carrying `use_sim_time` - is a 2. A supervisor
    keyed on 1 would report each of them as a boundary that came up.
    """
    code, text = _run_with_boundary(
        [
            _announces("plant", then="time.sleep(600)\n"),
            _announces("counterpart", then="time.sleep(600)\n"),
        ],
        _fake_boundary(tmp_path, "raise SystemExit(2)"),
    )
    assert code == 1
    assert "boundary exited 2" in text
    assert "boundary: ready=False status=2" in text
    assert "stopping plant" in text and "stopping counterpart" in text


def test_a_boundary_announcing_another_zone_is_refused(tmp_path: Path) -> None:
    """The redundancy in the token, which is the same check a side's name is.

    A boundary spans one zone and reads it off the plan it was handed. Handed a
    path to another cell's plan it would come up, serve, and span a cell nobody
    asked for - and it is the supervisor, which stated the zone, that is
    positioned to notice.
    """
    announcement = boundary_announcement("cell_b")
    # Started for `cell_a` - which is what `announces` on the spec records - and
    # announcing `cell_b`.
    wrong = _fake_boundary(
        tmp_path,
        f"import time\nprint({announcement!r}, flush=True)\ntime.sleep(600)\n",
    )
    code, text = _run_with_boundary(
        [
            _announces("plant", then="time.sleep(600)\n"),
            _announces("counterpart", then="time.sleep(600)\n"),
        ],
        wrong,
    )
    assert code == 1
    assert "announced readiness as 'cell_b'" in text
    assert "announced readiness as" in text
    assert "--zone" in text


def test_the_two_tokens_are_not_one_word_in_two_places() -> None:
    """A side's word and the boundary's, neither readable as the other.

    The supervisor waits for two sides and then for one boundary, on three pipes
    it reads at once. One token for both would make "both sides announced" and "a
    side announced twice" the same observation at the point where the difference
    decides whether L5 is started at all.
    """
    side_line = ready_announcement("plant", ZONE)
    boundary_line = boundary_announcement(ZONE)
    assert announced_boundary(side_line) is None
    assert announced_side(boundary_line) is None
    assert announced_side(side_line) == "plant"
    assert announced_boundary(boundary_line) == ZONE


# --- Ending a pair: who is signalled, where, and in what order ----------------


def _forwards_nothing(tmp_path: Path, caught: Path) -> pair.SideSpec:
    """Return the real boundary spec running `ros2 run`'s SHAPE, not its name.

    **The one thing about the boundary this file could not see.** Every other
    fake here is a `python3` process started directly, so it is its own leader
    and honours a leader-only SIGINT — while the participant it stands for begins
    its argv with `ros2 run`, which does neither. `ros2run.api.run_executable` is
    `subprocess.Popen(cmd)` followed by a loop that catches `KeyboardInterrupt`
    and **keeps waiting**: it installs no handler, forwards no signal, and the
    program it started is a grandchild of this supervisor. So the fakes honoured
    a signal the real participant never received, and the defect was invisible
    here while the tester reproduced it on a real pair.

    Reproduced rather than named: the parent below is that loop, and the child is
    a program that would shut down cleanly if it were ever asked to. It records
    being asked, in a file, because "the teardown was quick" is a duration and
    "the program received SIGINT" is the fact.

    **The CHILD announces, which is faithful and is also what makes this test
    deterministic.** The real boundary is the grandchild and prints the token
    itself, on the standard output it inherits. Announcing from the parent
    instead left a window in which the supervisor could have joined, been ended
    and signalled before the child interpreter had reached `signal.signal` — and
    the child then died on the DEFAULT SIGINT disposition, recording nothing,
    which reads exactly like the defect. Ordering the announcement after the
    handler closes that window without a sleep: the token now means the handler
    is installed, which is the same kind of fact a real readiness token is.
    """
    child = (
        "import signal, time\n"
        "def received(number, frame):\n"
        f"    open({str(caught)!r}, 'w').write('SIGINT')\n"
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGINT, received)\n"
        f"print({boundary_announcement(ZONE)!r}, flush=True)\n"
        "while True:\n"
        "    time.sleep(0.02)\n"
    )
    parent = (
        "import subprocess, sys\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child!r}])\n"
        "while child.returncode is None:\n"
        "    try:\n"
        "        child.communicate()\n"
        "    except KeyboardInterrupt:\n"
        "        pass\n"
        "raise SystemExit(child.returncode)\n"
    )
    return _fake_boundary(tmp_path, parent)


def _joined_then_ended(
    tmp_path: Path, release: Path
) -> list[pair.SideSpec]:
    """Two sides that both announce; the counterpart ends the pair once joined.

    The plant stays up so that it is still there to be stopped, and the
    counterpart's exit is what returns the join — which is the only way a pair
    that came up reaches the stop path without a signal, and a signal is what a
    test driving `supervise` off the main thread does not have.
    """
    return [
        _announces("plant", then="time.sleep(600)\n"),
        _held_until("counterpart", release),
    ]


def test_the_boundarys_first_signal_reaches_the_program_ros2_run_started(
    tmp_path: Path,
) -> None:
    """The boundary is ASKED to stop, rather than waited out and then killed.

    `ros2 run` forks and forwards nothing (see :func:`_forwards_nothing`), so a
    SIGINT delivered to the leader alone is caught by `ros2` and reaches the
    boundary never. What follows is not a slow teardown: the boundary is never
    asked at all, spends `STOP_GRACE_S` in full, and is then killed by the
    escalation — so its own `stop()` and `rclpy` shutdown do not run, every
    paired teardown costs 90 s it should not, and the console says the boundary
    refused to stop when nothing had asked it to. A tester observed exactly that
    on a real pair, twice, and isolated it outside this supervisor as well.

    **The fix is data and not a shorter ceiling**: `SideSpec.stop_reach` says
    where a participant's first SIGINT goes, and `STOP_GRACE_S` is correctly
    sized for the launch teardown it was written for.
    """
    release = tmp_path / "joined"
    caught = tmp_path / "sigint"
    log = _Log(marker="the twin boundary announced", release=release)
    code, text = _supervise_within(
        BACKSTOP_S,
        _joined_then_ended(tmp_path, release),
        boundary=_forwards_nothing(tmp_path, caught),
        ceiling_s=CEILING_S,
        boundary_ceiling_s=BOUNDARY_S,
        log=log,
        if_it_hangs=(
            "That is what a leader-only SIGINT costs: `ros2 run` swallows it, "
            "the program it started is never asked to stop, and the supervisor "
            "sits out the whole of STOP_GRACE_S before escalating."
        ),
    )
    assert caught.exists(), (
        "the program `ros2 run` started never received SIGINT. The supervisor "
        "signalled the leader alone, which is `ros2 run` - it installs no "
        "handler and forwards nothing, so the boundary was waited out and "
        "killed rather than stopped."
    )
    assert caught.read_text() == "SIGINT"
    # And therefore no grace was spent: the participant went on the first signal.
    assert f"did not stop within {pair.STOP_GRACE_S:g} s of SIGINT" not in text
    assert "boundary: ready=True" in text
    assert code == pair.PAIR_ENDED


def test_a_side_is_signalled_at_its_leader_and_the_boundary_at_its_group(
    tmp_path: Path,
) -> None:
    """Which reach each participant declares, and why it is that one.

    The behavioural test above is the evidence; this is the statement of it next
    to the commands it is a fact about. A side is `ros2 launch`, which runs the
    launch service in its own process and installs the handler its documented
    shutdown path runs on — signalling its group would deliver a second SIGINT
    to processes launch is already stopping. The boundary is `ros2 run`, which
    does neither.

    **So this asserts the first token of `argv` beside the reach**, because the
    reach is a property of the command: changing either without the other is the
    edit that would put this back.
    """
    plan = _paired_plan(tmp_path)
    for spec in pair.side_specs(plan, {DOMAIN_BASE_ENV: "41"}):
        assert spec.argv[:2] == ("ros2", "launch")
        assert spec.stop_reach == pair.STOP_LEADER
    boundary = pair.boundary_spec(plan, tmp_path / "plan.yaml")
    assert boundary.argv[:2] == ("ros2", "run")
    assert boundary.stop_reach == pair.STOP_GROUP

def test_the_boundary_is_stopped_before_the_sides(tmp_path: Path) -> None:
    """The commanding process goes first, and the stop loop is sequential.

    Each participant costs its own `STOP_GRACE_S + STOP_KILL_S` before the next
    is reached, so stopping the boundary last leaves it serving `SetMode` and
    holding an action client on each side for the whole of both sides' teardown
    — up to `2 * (90 + 30) s` in the worst case this module states. A goal
    arriving in that window is dispatched to a side that is already shutting down
    and to one that has not been signalled at all.

    It is the only participant that commands anything, it starts no cell, and no
    side's teardown consults it. **Ordering only: no ceiling moves**, and the
    reporting order is unchanged.
    """
    release = tmp_path / "joined"
    log = _Log(marker="the twin boundary announced", release=release)
    code, text = _supervise_within(
        BACKSTOP_S,
        _joined_then_ended(tmp_path, release),
        boundary=_boundary_announces(tmp_path, then="time.sleep(600)\n"),
        ceiling_s=CEILING_S,
        boundary_ceiling_s=BOUNDARY_S,
        log=log,
        if_it_hangs=(
            "The plant and the boundary are both held open until they are "
            "stopped, so a stop loop that never reaches one of them never "
            "returns."
        ),
    )
    assert "stopping boundary" in text and "stopping plant" in text
    assert text.index("stopping boundary") < text.index("stopping plant"), text
    # The counterpart ended the pair itself, so it is not stopped - which is what
    # leaves exactly two "stopping" lines to order.
    assert "stopping counterpart" not in text
    # And the REPORT is still sides first, boundary last: the stop order is not
    # the reading order and changing one did not change the other.
    reported = [line.split(":")[0] for line in text.splitlines() if ": ready=" in line]
    assert reported == ["[pair] plant", "[pair] counterpart", "[pair] boundary"]
    assert code == pair.PAIR_ENDED
