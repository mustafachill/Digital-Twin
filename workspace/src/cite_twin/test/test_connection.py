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

"""A kept physical side, as the boundary reads the supervisor's word on it (ADR-0077).

`cite_twin.connection` is pure and read as a table. The boundary's own use of
it - `TwinSides`' running, expected, connecting, failed and held; the mode
refused while the side is absent or held; a route to an absent side refused; a
goal in flight to a side that goes away ending rather than hanging; the end of
the supervisor's input failing closed - is driven on a boundary built from its
parts, as `test_physical_readiness.py` builds one. No graph, no robot.
"""

from __future__ import annotations

import io
import threading
import time
from types import SimpleNamespace

from cite_bringup.readiness import (
    SIDE_CONNECTING,
    SIDE_DOWN,
    SIDE_FAILED,
    side_state_line,
    SIDE_UP,
    SIDE_WAITING,
)
from cite_interfaces.msg import DeadmanState, ResultCode, TwinMode
from cite_twin.connection import Connections, DETAILS
from cite_twin.mode import Deployment, ModeAuthority
from cite_twin.twin_boundary import _GONE, _wait, TwinBoundary

from test_physical_readiness import _boundary_with_carriages, _state

COUNTERPART = "counterpart"


def _line(state: str) -> str:
    return side_state_line(COUNTERPART, state) + "\n"


# --- The table ------------------------------------------------------------------


def test_a_kept_side_is_waiting_until_told_and_a_side_not_kept_is_always_up() -> None:
    connections = Connections([COUNTERPART])
    assert connections.state(COUNTERPART) == SIDE_WAITING
    assert not connections.up(COUNTERPART)
    assert connections.up("plant") and connections.state("plant") is None
    assert connections.absent() == [f"{COUNTERPART}: {DETAILS[SIDE_WAITING]}"]


def test_each_line_moves_the_state_and_a_repeat_or_a_half_line_moves_nothing() -> None:
    connections = Connections([COUNTERPART])
    assert connections.apply(_line(SIDE_CONNECTING)) == (
        COUNTERPART, SIDE_WAITING, SIDE_CONNECTING
    )
    assert connections.connecting() == (COUNTERPART,)
    assert connections.apply(_line(SIDE_CONNECTING)) is None
    assert connections.apply("CITE_SIDE_STATE side=counterpart") is None
    assert connections.apply(side_state_line("plant", SIDE_DOWN)) is None, "not kept"
    assert connections.apply(_line(SIDE_UP)) == (COUNTERPART, SIDE_CONNECTING, SIDE_UP)
    assert connections.up(COUNTERPART) and connections.absent() == []
    assert connections.apply(_line(SIDE_FAILED))[2] == SIDE_FAILED
    assert connections.failed() == (COUNTERPART,)


def test_the_end_of_input_is_down_for_every_kept_side_not_failed() -> None:
    connections = Connections([COUNTERPART])
    connections.apply(_line(SIDE_UP))
    assert connections.end_of_input() == [(COUNTERPART, SIDE_UP, SIDE_DOWN)]
    assert not connections.up(COUNTERPART)
    failed = Connections([COUNTERPART])
    failed.apply(_line(SIDE_FAILED))
    assert failed.end_of_input() == []


# --- The boundary's use of it ---------------------------------------------------


class _Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, text: str) -> None:
        self.lines.append(text)

    warning = info


def _kept_boundary() -> TwinBoundary:
    """Build a boundary whose physical counterpart is kept, ready by measurement, and not up."""
    boundary = _boundary_with_carriages(0.0, 0.0)
    boundary._lock = threading.Lock()
    boundary._sides = {"plant": None, COUNTERPART: None}
    boundary._connections = Connections([COUNTERPART])
    boundary._gone = {COUNTERPART: threading.Event()}
    boundary._joint_positions = {}
    boundary._custody = {}
    boundary._operands = {}
    boundary._joints = {}
    boundary._log = _Log()
    published: list = []
    boundary._published = published
    boundary._publish_sides = lambda sets_only=False: published.append(boundary._sides_now())
    return boundary


def _authority(boundary: TwinBoundary) -> ModeAuthority:
    return ModeAuthority(
        Deployment.paired({"picker": True}),
        lambda: None,
        physical_side_unready=boundary._physical_side_unready,
        physical_carriage_apart=boundary._physical_carriage_apart,
    )


def test_a_kept_side_not_up_is_expected_physical_and_not_running() -> None:
    boundary = _kept_boundary()
    running, physical, commandable, stationary, detail = boundary._sides_now()
    assert running == ("plant",) and physical == (COUNTERPART,)
    assert commandable == ("plant",) and stationary == ()
    assert DETAILS[SIDE_WAITING] in detail
    expected, connecting, failed, held = boundary._connection_now()
    assert expected == ("plant", COUNTERPART) and connecting == () and failed == ()
    assert held == ()


def test_a_kept_side_that_is_up_runs_and_is_commandable_by_measurement() -> None:
    boundary = _kept_boundary()
    boundary._read_side_states(io.StringIO(_line(SIDE_CONNECTING) + _line(SIDE_UP)))
    # The end of THIS input is down again: read the published snapshot before it.
    running, _physical, commandable, _stationary, detail = boundary._published[1]
    assert running == ("plant", COUNTERPART) and commandable == ("plant", COUNTERPART)
    assert detail == ""


def test_real_is_refused_while_the_side_is_waiting_down_or_held() -> None:
    boundary = _kept_boundary()
    machine = _authority(boundary)
    verdict = machine.request(TwinMode.MODE_REAL, "", "x", False)
    assert not verdict.accepted and DETAILS[SIDE_WAITING] in verdict.detail
    boundary._connections.apply(_line(SIDE_UP))
    # Up and HELD (ADR-0076): connected, and still refused by measurement.
    boundary._physical_watches["picker"].heard_deadman(
        _state(DeadmanState.STATE_HELD), time.monotonic()
    )
    assert boundary._connection_now()[3] == (COUNTERPART,)
    verdict = machine.request(TwinMode.MODE_REAL, "", "x", False)
    assert not verdict.accepted and "held until Start robot" in verdict.detail
    # Released: HEALTHY with the arm enabled.
    boundary._physical_watches["picker"].heard_deadman(
        _state(DeadmanState.STATE_HEALTHY), time.monotonic()
    )
    assert boundary._connection_now()[3] == ()
    assert machine.request(TwinMode.MODE_REAL, "", "x", False).accepted


def test_a_side_lost_after_up_forgets_what_it_said_and_ends_its_goals() -> None:
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    taken = boundary._gone[COUNTERPART]
    with boundary._lock:
        boundary._changed_connection(
            *boundary._connections.apply(_line(SIDE_DOWN))
        )
    assert taken.is_set(), "a goal that took this event ends"
    assert not boundary._gone[COUNTERPART].is_set(), "a later goal waits on a fresh one"
    assert boundary._physical_watches["picker"].deadman is None
    assert (COUNTERPART, "picker_track_joint") not in boundary._track_positions
    assert ("plant", "picker_track_joint") in boundary._track_positions
    verdict = _authority(boundary).request(TwinMode.MODE_REAL, "", "x", False)
    assert not verdict.accepted and DETAILS[SIDE_DOWN] in verdict.detail


def test_the_end_of_the_supervisors_input_fails_closed() -> None:
    boundary = _kept_boundary()
    boundary._read_side_states(io.StringIO(_line(SIDE_UP)))
    assert boundary._connections.state(COUNTERPART) == SIDE_DOWN
    running = boundary._published[-1][0]
    assert running == ("plant",)
    assert any("up -> down" in line for line in boundary._log.lines)


def test_a_route_to_a_side_that_is_not_up_is_refused() -> None:
    boundary = _kept_boundary()
    chosen = boundary._route(TwinMode.MODE_VALIDATED)
    assert not chosen.accepted and chosen.code == ResultCode.PRECONDITION_FAILED
    assert DETAILS[SIDE_WAITING] in chosen.detail
    assert boundary._route(TwinMode.MODE_SIM).accepted
    boundary._connections.apply(_line(SIDE_UP))
    assert boundary._route(TwinMode.MODE_VALIDATED).accepted


def test_a_boundary_that_keeps_nothing_runs_every_side_it_started() -> None:
    """Without `--side-states` the class default keeps nothing: today's behaviour."""
    boundary = _boundary_with_carriages(0.0, 0.0)
    boundary._sides = {"plant": None, COUNTERPART: None}
    assert boundary._sides_now()[0] == ("plant", COUNTERPART)
    assert boundary._connection_now()[:3] == (("plant", COUNTERPART), (), ())
    assert boundary._route(TwinMode.MODE_VALIDATED).accepted


class _Future:
    """A future nobody completes: the answer of a server that went away."""

    def add_done_callback(self, _callback) -> None:
        pass

    def result(self):  # pragma: no cover - never reached
        raise AssertionError("a wait on a gone side read a result")


def test_a_wait_on_a_side_that_goes_away_ends_rather_than_hangs() -> None:
    gone = threading.Event()
    handle = SimpleNamespace(is_cancel_requested=False)
    finished: list = []
    waiter = threading.Thread(
        target=lambda: finished.append(_wait(_Future(), handle, [], gone)), daemon=True
    )
    waiter.start()
    waiter.join(0.3)
    assert waiter.is_alive(), "it waits while the side is there"
    gone.set()
    waiter.join(5.0)
    assert finished == [_GONE]


def test_a_goal_whose_far_side_went_away_is_a_hardware_fault_and_the_plant_finishes() -> None:
    class _Done:
        def __init__(self, value) -> None:
            self._value = value

        def add_done_callback(self, callback) -> None:
            callback(self)

        def result(self):
            return self._value

    accepted = SimpleNamespace(accepted=True)
    plant_result = SimpleNamespace(status=4, result=SimpleNamespace(result=ResultCode(code=0)))
    accepted.get_result_async = lambda: _Done(plant_result)
    gone = threading.Event()
    gone.set()
    outcomes = TwinBoundary._await_far_side_goals(
        SimpleNamespace(),
        {"plant": _Done(accepted), COUNTERPART: _Future()},
        SimpleNamespace(is_cancel_requested=False),
        {COUNTERPART: gone},
    )
    assert outcomes[COUNTERPART].code.code == ResultCode.HARDWARE_FAULT
    assert "disconnected" in outcomes[COUNTERPART].code.detail
    assert outcomes["plant"].code.code == ResultCode.SUCCESS
