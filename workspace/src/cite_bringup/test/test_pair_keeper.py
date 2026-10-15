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

"""The pair supervisor KEEPS a physical counterpart (ADR-0077 decision 2).

Two halves. `_Keeper` is a pure table and is read as one: each event in, the
actions out. Then `supervise` is driven, as `test_pair.py` drives it, against
processes that are not ROS at all - `python3 -c` scripts that print the tokens a
side, a boundary and a console print - with a kept side that waits silently,
reaches its robot, comes up, goes away, fails, or hangs, and a fake boundary that
prints every state line the supervisor writes on its standard input and exits
once it has seen the one the test is waiting for. Nothing here starts a ROS
node, and nothing reaches a robot.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import re
import sys
import threading

from cite_bringup import pair
from cite_bringup.plan import COUNTERPART_SIDE, default_plan_path, load, PLANT_SIDE
from cite_bringup.readiness import (
    announced_boundary,
    announced_console,
    announced_reachable,
    boundary_announcement,
    console_announcement,
    parsed_attempts,
    parsed_side_state,
    reachable_announcement,
    ready_announcement,
    SIDE_CONNECTING,
    SIDE_DOWN,
    SIDE_FAILED,
    side_state_line,
    SIDE_STATES,
    SIDE_UP,
    SIDE_WAITING,
)
import pytest

ZONE = "cell_b"

#: A ceiling on THIS TEST: a supervisor that should have returned and did not
#: fails the test with a sentence rather than the suite's timeout. Nothing under
#: test is compared to it.
BACKSTOP_S = 60.0

#: The sides' join ceiling here: everything joined on is a `python3` process
#: that announces in milliseconds.
CEILING_S = 20.0


# --- The tokens -----------------------------------------------------------------


def test_a_reachable_line_names_its_side_and_is_no_ready_line() -> None:
    line = f"[INFO] [launch.user]: {reachable_announcement(COUNTERPART_SIDE, ZONE)}"
    assert announced_reachable(line) == COUNTERPART_SIDE
    assert announced_reachable(ready_announcement(COUNTERPART_SIDE, ZONE)) is None
    from cite_bringup.readiness import announced_side

    assert announced_side(line) is None


def test_a_state_line_round_trips_and_a_half_line_moves_nothing() -> None:
    for state in SIDE_STATES:
        assert parsed_side_state(side_state_line(COUNTERPART_SIDE, state)) == (
            COUNTERPART_SIDE,
            state,
        )
    # A-02: a failed line carries its attempts, and no other line does.
    assert parsed_attempts(side_state_line(COUNTERPART_SIDE, SIDE_FAILED, 3)) == 3
    assert parsed_attempts(side_state_line(COUNTERPART_SIDE, SIDE_FAILED)) == 0
    assert parsed_attempts(side_state_line(COUNTERPART_SIDE, SIDE_UP, 3)) is None
    assert parsed_side_state("CITE_SIDE_STATE side=counterpart") is None
    assert parsed_side_state("CITE_SIDE_STATE state=up") is None
    assert parsed_side_state("CITE_SIDE_STATE side=counterpart state=sideways") is None
    assert parsed_side_state("nothing here") is None
    with pytest.raises(ValueError):
        side_state_line(COUNTERPART_SIDE, "sideways")


# --- The table ------------------------------------------------------------------


def _keeper(attempts: int = 3) -> pair._Keeper:
    keeper = pair._Keeper(COUNTERPART_SIDE, attempts=attempts, ceiling_s=10.0)
    assert keeper.started() == [(pair.KEEP_REPORT, SIDE_WAITING)]
    return keeper


def test_reachable_then_ready_is_connecting_then_up_and_the_ceiling_runs_between() -> None:
    keeper = _keeper()
    assert keeper.deadline is None, "a side waiting for its robot has no ceiling"
    assert keeper.reachable(100.0) == [(pair.KEEP_REPORT, SIDE_CONNECTING)]
    assert keeper.deadline == 110.0
    assert keeper.expired(109.9) == []
    assert keeper.ready() == [(pair.KEEP_REPORT, SIDE_UP)]
    assert keeper.deadline is None


SWEEP = [(pair.KEEP_SWEEP, "")]
DOWN = [(pair.KEEP_REPORT, SIDE_DOWN)]
RESTARTED = [(pair.KEEP_RESTART, ""), (pair.KEEP_REPORT, SIDE_WAITING)]
FAILED = [(pair.KEEP_REPORT, SIDE_FAILED)]


def test_an_exit_after_up_is_down_at_once_and_waiting_and_a_restart_after_the_sweep() -> None:
    keeper = _keeper()
    keeper.reachable(0.0)
    assert keeper.exited(0.0) == SWEEP
    assert keeper.swept() == RESTARTED
    keeper.reachable(0.0)
    assert keeper.failures == 1
    keeper.ready()
    # S-01 (ADR-0077): `down` at the exit, so the boundary falls to SIM now
    # and not after a sweep of up to a minute; `waiting` and the restart only
    # once the old group is empty, so no second driver beside the first.
    assert keeper.exited(1.0) == DOWN + SWEEP
    assert keeper.swept() == RESTARTED
    assert keeper.failures == 0


def test_an_exit_before_the_robot_answered_is_a_refusal_and_is_not_retried() -> None:
    keeper = _keeper()
    assert keeper.exited(0.0) == SWEEP
    assert keeper.swept() == FAILED
    assert keeper.exited(0.0) == [], "a failed side is not judged again"
    assert keeper.reachable(0.0) == [] and keeper.ready() == []


def test_three_failed_attempts_in_a_row_are_failed() -> None:
    keeper = _keeper(attempts=3)
    for _ in range(2):
        keeper.reachable(0.0)
        assert keeper.exited(0.0) == SWEEP
        assert keeper.swept() == RESTARTED
    keeper.reachable(0.0)
    assert keeper.exited(0.0) == SWEEP
    assert keeper.swept() == FAILED
    assert keeper.failures == 3, "the failed line carries the count"


def test_an_attempt_past_its_ceiling_is_stopped_once_and_its_exit_counts() -> None:
    keeper = _keeper()
    keeper.reachable(0.0)
    assert keeper.expired(10.0) == [(pair.KEEP_STOP, pair.STOP_CEILING)]
    assert keeper.expired(11.0) == [], "stopped once"
    assert keeper.exited(11.0) == SWEEP
    assert keeper.swept() == RESTARTED
    assert keeper.failures == 1


def test_an_announcement_after_the_stop_was_sent_is_ignored() -> None:
    """S-06: a stopped attempt that announces late is not `up`, and its exit still counts."""
    keeper = _keeper()
    keeper.reachable(0.0)
    keeper.expired(10.0)
    assert keeper.ready() == [], "a late ready while stopping moves nothing"
    assert keeper.failures == 0
    assert keeper.exited(11.0) == SWEEP
    assert keeper.swept() == RESTARTED
    assert keeper.failures == 1


def test_a_group_that_never_empties_is_failed_and_never_restarted() -> None:
    """S-05: no second driver beside processes of the first."""
    keeper = _keeper()
    keeper.reachable(0.0)
    keeper.ready()
    assert keeper.exited(0.0) == DOWN + SWEEP
    assert keeper.unswept() == FAILED
    assert keeper.swept() == [] and keeper.exited(1.0) == []


def test_reconnects_are_bounded_within_the_window() -> None:
    """S-02: the `reconnects`-th down within `window_s` is `failed`, not another restart."""
    keeper = pair._Keeper(
        COUNTERPART_SIDE, attempts=3, ceiling_s=10.0, reconnects=3, window_s=100.0
    )
    keeper.started()
    for now in (0.0, 10.0):
        keeper.reachable(now)
        keeper.ready()
        assert keeper.exited(now) == DOWN + SWEEP
        assert keeper.swept() == RESTARTED
    keeper.reachable(20.0)
    keeper.ready()
    assert keeper.exited(20.0) == DOWN + SWEEP
    assert keeper.swept() == FAILED


def test_reconnects_older_than_the_window_do_not_count() -> None:
    keeper = pair._Keeper(
        COUNTERPART_SIDE, attempts=3, ceiling_s=10.0, reconnects=2, window_s=100.0
    )
    keeper.started()
    for now in (0.0, 150.0, 300.0, 450.0):
        keeper.reachable(now)
        keeper.ready()
        assert keeper.exited(now) == DOWN + SWEEP
        assert keeper.swept() == RESTARTED


def test_the_shipped_reconnect_bound_is_the_owners_decision() -> None:
    from cite_bringup.readiness import KEPT_RECONNECT_WINDOW_S, KEPT_RECONNECTS

    assert (KEPT_RECONNECTS, KEPT_RECONNECT_WINDOW_S) == (5, 600.0)


def test_a_misnamed_announcement_stops_the_side_and_fails_it() -> None:
    """R-08: a kept side naming another participant is a configuration error for that side."""
    keeper = _keeper()
    keeper.reachable(0.0)
    assert keeper.misnamed() == [(pair.KEEP_STOP, pair.STOP_MISNAMED)]
    assert keeper.exited(1.0) == SWEEP
    assert keeper.swept() == FAILED


def test_a_side_up_and_then_misnamed_is_down_before_its_stop_and_failed_after_its_sweep() -> None:
    """S-01: the stop of an `up` incarnation reports `down` first, not after the sweep."""
    keeper = _keeper()
    keeper.reachable(0.0)
    keeper.ready()
    assert keeper.misnamed() == DOWN + [(pair.KEEP_STOP, pair.STOP_MISNAMED)]
    assert keeper.exited(1.0) == SWEEP, "down is said once"
    assert keeper.swept() == FAILED


# --- Who is kept ----------------------------------------------------------------


def _plan():
    return load(default_plan_path(ZONE))


def test_only_the_physical_side_of_a_hot_plug_pair_is_kept() -> None:
    plan = _plan()
    environ = {"CITE_DOMAIN_BASE": "40"}
    plain = pair.side_specs(plan, environ, sides=pair.SIDES_ALL)
    assert not any(spec.kept for spec in plain)
    assert not any("wait_for_robot:=true" in spec.argv for spec in plain)
    kept = {spec.name: spec for spec in pair.side_specs(plan, environ, hot_plug=True)}
    assert not kept[PLANT_SIDE].kept
    assert kept[COUNTERPART_SIDE].kept
    assert kept[COUNTERPART_SIDE].argv[-1] == "wait_for_robot:=true"


def test_only_a_hot_plug_boundary_reads_states_on_its_stdin() -> None:
    plan = _plan()
    plain = pair.boundary_spec(plan, "/x.yaml", pair.SIDES_ALL)
    assert "--side-states" not in plain.argv and not plain.feed_states
    fed = pair.boundary_spec(plan, "/x.yaml", pair.SIDES_ALL, side_states=True)
    assert fed.argv[-2:] == ("--side-states", "stdin") and fed.feed_states


@pytest.mark.parametrize(
    "argv",
    [
        ["--zone", ZONE, "--sides", "all", "--hot-plug"],
        ["--zone", ZONE, "--sides", "plant", "--console", "--hot-plug"],
    ],
)
def test_hot_plug_is_refused_outside_the_console_with_both_sides(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as refused:
        pair.main(argv)
    assert refused.value.code == 2


# --- The supervisor, against processes that are not ROS -------------------------


class _Log(io.StringIO):
    """The supervisor's console, with tripwires: a marker seen touches a file."""

    def __init__(self, wires: dict[str, Path] | None = None) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._wires = dict(wires or {})

    def write(self, text: str) -> int:
        with self._lock:
            written = super().write(text)
        for marker, path in self._wires.items():
            if marker in text:
                path.touch()
        return written


def _script(name: str, body: str) -> tuple[str, ...]:
    return (sys.executable, "-c", "import os, sys, time\n" + body)


def _plant() -> pair.SideSpec:
    return pair.SideSpec(
        PLANT_SIDE,
        _script(
            PLANT_SIDE,
            f"print({ready_announcement(PLANT_SIDE, ZONE)!r}, flush=True)\ntime.sleep(600)\n",
        ),
    )


def _boundary(stop_on: str, count: int = 1, then: Path | None = None) -> pair.SideSpec:
    """Return a boundary printing each state line it reads, ending on the ``count``-th ``stop_on``.

    With ``then``, it exits only once that file also exists.
    """
    body = (
        f"print({boundary_announcement(ZONE)!r}, flush=True)\n"
        "seen = 0\n"
        "for line in sys.stdin:\n"
        "    print('got ' + line.strip(), flush=True)\n"
        f"    if {stop_on!r} in line:\n"
        "        seen += 1\n"
        f"        if seen >= {count}:\n"
        "            break\n"
    )
    if then is not None:
        body += f"while not os.path.exists({str(then)!r}):\n    time.sleep(0.02)\n"
    return pair.SideSpec(
        pair.BOUNDARY_NAME,
        _script("boundary", body),
        announcement=announced_boundary,
        announces=ZONE,
        argument="--zone",
        title="the twin boundary",
        feed_states=True,
    )


def _console(release: Path | None = None) -> pair.SideSpec:
    wait = (
        f"while not os.path.exists({str(release)!r}):\n    time.sleep(0.02)\n"
        if release is not None
        else "time.sleep(600)\n"
    )
    return pair.SideSpec(
        pair.CONSOLE_NAME,
        _script("console", f"print({console_announcement(ZONE)!r}, flush=True)\n" + wait),
        announcement=announced_console,
        announces=ZONE,
        argument="--zone",
        title="the operator console",
    )


def _kept(tmp_path: Path, behaviours: list[str]) -> pair.SideSpec:
    """Return a kept side whose Nth incarnation does ``behaviours[N]``.

    Every incarnation first prints its number and pid. Behaviours:
    `silent` waits for ever; `refuse` exits 2 at once; `hang` reaches its robot
    and never announces; `deaf` does the same and ignores SIGINT; `misnamed`
    reaches and announces as the plant; `up` reaches, announces and waits for ever; `lost`
    reaches, announces, starts a grandchild in its group, records its pid and
    exits 1 once `lose` exists; `check` reports whether that grandchild is
    still alive and waits for ever.
    """
    counter = tmp_path / "incarnations"
    grandchild = tmp_path / "grandchild"
    lose = tmp_path / "lose"
    reach = reachable_announcement(COUNTERPART_SIDE, ZONE)
    ready = ready_announcement(COUNTERPART_SIDE, ZONE)
    body = (
        "import subprocess\n"
        f"counter = {str(counter)!r}\n"
        "n = int(open(counter).read()) if os.path.exists(counter) else 0\n"
        "open(counter, 'w').write(str(n + 1))\n"
        f"behaviour = {behaviours!r}[n]\n"
        "print(f'incarnation={n} pid={os.getpid()}', flush=True)\n"
        "if behaviour == 'refuse':\n"
        "    sys.exit(2)\n"
        "if behaviour == 'check':\n"
        f"    gpid = int(open({str(grandchild)!r}).read())\n"
        "    try:\n"
        "        os.kill(gpid, 0)\n"
        "        print('grandchild alive', flush=True)\n"
        "    except ProcessLookupError:\n"
        "        print('grandchild gone', flush=True)\n"
        "if behaviour == 'deaf':\n"
        "    import signal\n"
        "    signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "if behaviour in ('hang', 'up', 'lost', 'deaf', 'misnamed'):\n"
        f"    print({reach!r}, flush=True)\n"
        "if behaviour == 'misnamed':\n"
        f"    print({ready_announcement(PLANT_SIDE, ZONE)!r}, flush=True)\n"
        "if behaviour in ('up', 'lost'):\n"
        f"    print({ready!r}, flush=True)\n"
        "if behaviour == 'lost':\n"
        # Off the side's pipe, as a launch's children are: `launch` reads them
        # through pipes of its own, so only the launch holds the supervisor's.
        "    child = subprocess.Popen(['sleep', '600'], stdout=subprocess.DEVNULL,\n"
        "                             stderr=subprocess.DEVNULL)\n"
        f"    open({str(grandchild)!r}, 'w').write(str(child.pid))\n"
        f"    while not os.path.exists({str(lose)!r}):\n"
        "        time.sleep(0.02)\n"
        "    sys.exit(1)\n"
        "time.sleep(600)\n"
    )
    return pair.SideSpec(COUNTERPART_SIDE, _script("kept", body), kept=True)


def _supervise(specs, *, boundary, console=None, log=None, **kwargs) -> tuple[int, str]:
    out = _Log() if log is None else log
    finished: dict[str, object] = {}

    def run() -> None:
        try:
            finished["code"] = pair.supervise(
                specs, boundary=boundary, console=console, out=out, ceiling_s=CEILING_S,
                **kwargs,
            )
        except BaseException as error:  # noqa: BLE001 - re-raised below
            finished["error"] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(BACKSTOP_S)
    if worker.is_alive():
        raise AssertionError(
            f"the supervisor had not returned within {BACKSTOP_S:g} s:\n" + out.getvalue()
        )
    if "error" in finished:
        raise finished["error"]  # type: ignore[misc]
    return finished["code"], out.getvalue()  # type: ignore[return-value]


def _states(text: str) -> list[str]:
    """Return the states the fake boundary received, in order.

    Read with a pattern rather than line by line: the supervisor's own lines and
    a participant's forwarded ones are printed from different threads, and a
    `print` writes its text and its newline separately, so two of them can share
    a line of the log.
    """
    return re.findall(
        rf"\[{pair.BOUNDARY_NAME}\] got CITE_SIDE_STATE side={COUNTERPART_SIDE} "
        r"state=([a-z]+)",
        text,
    )


def test_a_silent_kept_side_holds_neither_the_boundary_nor_the_console(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    log = _Log({f"[{pair.BOUNDARY_NAME}] got CITE_SIDE_STATE": release})
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["silent"])],
        boundary=_boundary("never"),
        console=_console(release),
        log=log,
    )
    assert "the operator console announced readiness; the pair is complete" in text, text
    assert _states(text) == [SIDE_WAITING], "the state said before the boundary existed"
    # The console ended the pair; the silent kept side was neither waited for
    # nor graded.
    assert code == pair.PAIR_ENDED
    assert "never announced readiness" not in text
    assert f"[pair] {COUNTERPART_SIDE}: ready=False status=" in text
    assert "(kept, not graded)" in text


def test_a_robot_that_answers_and_a_side_that_comes_up_are_connecting_then_up(
    tmp_path: Path,
) -> None:
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["up"])], boundary=_boundary(f"state={SIDE_UP}")
    )
    assert _states(text) == [SIDE_WAITING, SIDE_CONNECTING, SIDE_UP], text
    assert code == pair.PAIR_ENDED, "the boundary ending the pair is what ended it"


def test_a_side_lost_after_it_was_up_is_swept_and_started_again_and_ends_nothing(
    tmp_path: Path,
) -> None:
    checked = tmp_path / "checked"
    log = _Log({
        f"[{pair.BOUNDARY_NAME}] got CITE_SIDE_STATE side=counterpart state=up": tmp_path / "lose",
        "grandchild ": checked,
    })
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["lost", "check"])],
        boundary=_boundary(f"state={SIDE_WAITING}", count=2, then=checked),
        log=log,
    )
    assert _states(text) == [
        SIDE_WAITING, SIDE_CONNECTING, SIDE_UP, SIDE_DOWN, SIDE_WAITING
    ], text
    pids = [line.split("pid=")[1] for line in text.splitlines() if "incarnation=" in line]
    assert len(pids) == 2 and pids[0] != pids[1], "a new incarnation, a new process"
    assert "grandchild gone" in text, "the old group was swept before the restart"
    assert f"[pair] {COUNTERPART_SIDE} exited 1" in text
    # The pair went on: what ended it was the boundary, after the restart.
    assert text.index(f"[pair] {COUNTERPART_SIDE} exited 1") < text.index(
        f"[pair] {pair.BOUNDARY_NAME} exited 0"
    )
    # R-02: the restarted incarnation is the supervisor's to stop too, and it
    # did - nothing of it outlives the pair.
    restarted = int(pids[1])
    with pytest.raises(ProcessLookupError):
        os.kill(restarted, 0)


def test_a_kept_sides_stop_never_holds_the_loop_that_judges_the_plant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S-07: a kept side deaf to SIGINT is escalated from the loop, not waited on.

    Before the fix the loop sat in the kept side's `STOP_GRACE_S` and judged
    the plant's exit only after it.
    """
    monkeypatch.setattr(pair, "STOP_GRACE_S", 6.0)
    monkeypatch.setattr(pair, "STOP_KILL_S", 1.0)
    stopping = tmp_path / "stopping"
    plant = pair.SideSpec(
        PLANT_SIDE,
        _script(
            PLANT_SIDE,
            f"print({ready_announcement(PLANT_SIDE, ZONE)!r}, flush=True)\n"
            f"while not os.path.exists({str(stopping)!r}):\n    time.sleep(0.02)\n"
            "sys.exit(5)\n",
        ),
    )
    log = _Log({f"[pair] stopping {COUNTERPART_SIDE}": stopping})
    code, text = _supervise(
        [plant, _kept(tmp_path, ["deaf"])],
        boundary=_boundary("never"),
        log=log,
        kept_ceiling_s=0.5,
    )
    assert f"[pair] {PLANT_SIDE} exited 5" in text, text
    judged = text.index(f"[pair] {PLANT_SIDE} exited 5")
    grace = f"[pair] {COUNTERPART_SIDE} did not stop within"
    assert grace not in text[:judged], "the plant waited out the kept side's grace"
    assert code == pair.PAIR_ENDED


def test_a_kept_group_that_never_empties_is_failed_and_not_started_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S-05: still not empty after SIGKILL and the bounded poll: failed, no restart."""
    monkeypatch.setattr(pair, "STOP_KILL_S", 0.3)
    monkeypatch.setattr(pair, "_group_is_empty", lambda side: False)
    log = _Log({
        f"[{pair.BOUNDARY_NAME}] got CITE_SIDE_STATE side=counterpart state=up": tmp_path / "lose",
    })
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["lost", "up"])],
        boundary=_boundary(f"state={SIDE_FAILED}"),
        log=log,
    )
    assert _states(text) == [
        SIDE_WAITING, SIDE_CONNECTING, SIDE_UP, SIDE_DOWN, SIDE_FAILED
    ], text
    assert text.count("incarnation=") == 1, "never a second driver beside the first"
    assert "process group was still not empty" in text
    # S-01: `down` reached the boundary at the exit, before the sweep gave up.
    assert text.index(f"[pair] {COUNTERPART_SIDE}: {SIDE_DOWN}") < text.index(
        "left processes running"
    )


def test_a_kept_side_announcing_as_another_is_failed_and_the_pair_goes_on(
    tmp_path: Path,
) -> None:
    """R-08: a misnamed announcement is that side's configuration error, not the pair's end."""
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["misnamed", "up"])],
        boundary=_boundary(f"state={SIDE_FAILED}"),
    )
    assert _states(text) == [SIDE_WAITING, SIDE_CONNECTING, SIDE_FAILED], text
    assert text.count("incarnation=") == 1
    # What ended the pair is the boundary, after the side was failed.
    assert f"[pair] {pair.BOUNDARY_NAME} exited 0" in text


def test_a_side_that_refuses_before_its_robot_answered_is_failed_and_not_restarted(
    tmp_path: Path,
) -> None:
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["refuse", "up"])],
        boundary=_boundary(f"state={SIDE_FAILED}"),
    )
    assert _states(text) == [SIDE_WAITING, SIDE_FAILED], text
    assert text.count("incarnation=") == 1
    assert "starting counterpart again" not in text


def test_three_attempts_that_each_outlive_their_ceiling_are_failed(tmp_path: Path) -> None:
    code, text = _supervise(
        [_plant(), _kept(tmp_path, ["hang", "hang", "hang", "up"])],
        boundary=_boundary(f"state={SIDE_FAILED}"),
        kept_attempts=3,
        kept_ceiling_s=1.0,
    )
    assert _states(text) == [
        SIDE_WAITING, SIDE_CONNECTING,
        SIDE_WAITING, SIDE_CONNECTING,
        SIDE_WAITING, SIDE_CONNECTING,
        SIDE_FAILED,
    ], text
    assert text.count("incarnation=") == 3, "no fourth attempt"
    assert text.count("did not announce within 1 s; stopping this attempt") == 3
