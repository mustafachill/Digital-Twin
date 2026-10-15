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
from cite_twin.connection import Connections, DETAILS, failed_detail
from cite_twin.hold import ModeHold
from cite_twin.mode import Deployment, ModeAuthority
from cite_twin.twin_boundary import _GONE, _wait, TwinBoundary

from test_physical_readiness import _boundary_with_carriages, _state, AGE, JOINTS

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


def test_a_failed_side_is_said_with_the_attempts_its_line_carried() -> None:
    """A-02: the words come from the supervisor's line, not from its constant."""
    connections = Connections([COUNTERPART])
    connections.apply(side_state_line(COUNTERPART, SIDE_FAILED, 4))
    assert connections.absent() == [f"{COUNTERPART}: {failed_detail(4)}"]
    assert "4 times in a row" in failed_detail(4)
    refused = Connections([COUNTERPART])
    refused.apply(side_state_line(COUNTERPART, SIDE_FAILED, 0))
    assert refused.absent() == [f"{COUNTERPART}: {DETAILS[SIDE_FAILED]}"]


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
    error = info


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
    boundary._authority = _authority(boundary)
    boundary._hold = ModeHold()
    modes: list[int] = []
    boundary._modes = modes
    boundary._publish_mode = lambda: modes.append(boundary._authority.mode)
    boundary._belt_publishers = {}
    boundary._track_joint_by_topic = {TRACK_TOPIC: "picker_track_joint"}
    boundary._track_publishers = {
        (side, TRACK_TOPIC): _Publisher() for side in ("plant", COUNTERPART)
    }
    return boundary


TRACK_TOPIC = "/cite/cell_b/picker/track/joint_trajectory"


class _Publisher:
    def __init__(self) -> None:
        self.sent: list = []

    def publish(self, message) -> None:
        self.sent.append(message)


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
    assert boundary._track_history["picker_track_joint"] == [], "stillness is measured anew"
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
    assert not waiter.is_alive(), "the wait did not end within 5 s of its side going away"
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


# --- S-01: a mode never outlives the incarnation it was measured on --------------


def _released(boundary: TwinBoundary) -> None:
    boundary._physical_watches["picker"].heard_deadman(
        _state(DeadmanState.STATE_HEALTHY), time.monotonic()
    )


def _heard_again(boundary: TwinBoundary) -> None:
    """Hear the new incarnation's controller, joints and carriage, fresh."""
    now = time.monotonic()
    watch = boundary._physical_watches["picker"]
    watch.heard_controller(now)
    watch.heard_joints(JOINTS, now)
    boundary._track_positions[(COUNTERPART, "picker_track_joint")] = (0.0, now)
    boundary._track_history["picker_track_joint"] = [(0.0, now - AGE), (0.0, now)]


def test_a_side_lost_in_real_takes_the_mode_to_sim_and_real_is_measured_again() -> None:
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    _released(boundary)
    machine = boundary._authority
    assert machine.request(TwinMode.MODE_REAL, "", "run", False).accepted
    boundary._hold.request(1, "run-1", "/console", TwinMode.MODE_REAL, machine.mode, 0.0)

    boundary._read_side_states(io.StringIO(_line(SIDE_DOWN)))
    assert machine.mode == TwinMode.MODE_SIM, "the mode fell with the side"
    # Published at the fall, and once more as the reader ended (S-04).
    assert boundary._modes == [TwinMode.MODE_SIM] * 2, "and the fall was published"
    assert "stopped being up" in machine.reason
    assert boundary._hold.held.mode == TwinMode.MODE_SIM, "the hold went with the mode"
    assert boundary._route(machine.mode).sides == ("plant",), "nothing reaches the side"

    # Restarted, up, and still HELD (ADR-0076): REAL is not back by itself.
    boundary._connections.apply(_line(SIDE_WAITING))
    boundary._connections.apply(_line(SIDE_UP))
    boundary._physical_watches["picker"].heard_deadman(
        _state(DeadmanState.STATE_HELD), time.monotonic()
    )
    assert machine.mode == TwinMode.MODE_SIM
    refused = machine.request(TwinMode.MODE_REAL, "", "again", False)
    assert not refused.accepted and "held until Start robot" in refused.detail
    # Released: a goal still goes to the plant alone until SetMode measures,
    # and SetMode measures THIS incarnation - nothing of the old one is left.
    _released(boundary)
    assert machine.mode == TwinMode.MODE_SIM
    assert boundary._route(machine.mode).sides == ("plant",)
    unheard = machine.request(TwinMode.MODE_REAL, "", "again", False)
    assert not unheard.accepted and "not running" in unheard.detail
    _heard_again(boundary)
    assert machine.request(TwinMode.MODE_REAL, "", "again", False).accepted


def test_a_side_lost_in_sim_moves_no_mode() -> None:
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    with boundary._lock:
        fell = boundary._changed_connection(*boundary._connections.apply(_line(SIDE_DOWN)))
    assert not fell and boundary._modes == []


# --- S-03: the reader fails closed whatever ends it -----------------------------


class _Breaking:
    """A stream that yields its lines and then raises, as a reader's bug would."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def __iter__(self):
        yield from self._lines
        raise RuntimeError("injected")


def test_a_reader_that_raises_still_fails_closed_and_says_why() -> None:
    boundary = _kept_boundary()
    boundary._read_side_states(_Breaking([_line(SIDE_UP)]))
    assert boundary._connections.state(COUNTERPART) == SIDE_DOWN
    assert boundary._published[-1][0] == ("plant",)
    assert any("injected" in line for line in boundary._log.lines)


# --- S-04: a goal on a side that went away is cancelled, best effort ------------


class _Later:
    """A future completed by the test, after the wait on it gave up."""

    def __init__(self) -> None:
        self._callbacks: list = []
        self._value = None
        self._done = False

    def add_done_callback(self, callback) -> None:
        if self._done:
            callback(self)
        else:
            self._callbacks.append(callback)

    def complete(self, value) -> None:
        self._value = value
        self._done = True
        for callback in self._callbacks:
            callback(self)

    def result(self):
        return self._value


class _Handle:
    def __init__(self, result_future) -> None:
        self.accepted = True
        self.cancels = 0
        self._result = result_future

    def get_result_async(self):
        return self._result

    def cancel_goal_async(self) -> None:
        self.cancels += 1


def _done(value):
    later = _Later()
    later.complete(value)
    return later


def test_a_goal_running_on_a_side_that_went_away_is_cancelled() -> None:
    running = _Handle(_Future())
    gone = threading.Event()
    gone.set()
    outcomes = TwinBoundary._await_far_side_goals(
        SimpleNamespace(),
        {COUNTERPART: _done(running)},
        SimpleNamespace(is_cancel_requested=False),
        {COUNTERPART: gone},
    )
    assert outcomes[COUNTERPART].code.code == ResultCode.HARDWARE_FAULT
    assert running.cancels == 1


def test_a_goal_accepted_after_its_side_went_away_is_cancelled() -> None:
    acceptance = _Later()
    gone = threading.Event()
    gone.set()
    outcomes = TwinBoundary._await_far_side_goals(
        SimpleNamespace(),
        {COUNTERPART: acceptance},
        SimpleNamespace(is_cancel_requested=False),
        {COUNTERPART: gone},
    )
    assert outcomes[COUNTERPART].code.code == ResultCode.HARDWARE_FAULT
    late = _Handle(_Future())
    acceptance.complete(late)
    assert late.cancels == 1


# --- Re-audit: the fall is immediate, gates what is sent after it, and stops ----


def test_what_the_old_incarnation_said_after_down_is_forgotten_again_at_waiting() -> None:
    """S-01: `down` comes at the exit, before the sweep; `waiting` after it forgets again."""
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    with boundary._lock:
        boundary._changed_connection(*boundary._connections.apply(_line(SIDE_DOWN)))
    # The old group, not yet swept, still speaks.
    _released(boundary)
    _heard_again(boundary)
    with boundary._lock:
        fell = boundary._changed_connection(*boundary._connections.apply(_line(SIDE_WAITING)))
    assert not fell
    assert boundary._physical_watches["picker"].deadman is None
    assert (COUNTERPART, "picker_track_joint") not in boundary._track_positions
    assert boundary._track_history["picker_track_joint"] == []


class _Client:
    def __init__(self, on_wait=None) -> None:
        self.sent: list = []
        self._on_wait = on_wait

    def wait_for_server(self, timeout_sec: float) -> bool:
        if self._on_wait is not None:
            self._on_wait()
        return True

    def send_goal_async(self, goal, feedback_callback=None):
        self.sent.append(goal)
        return object()


def test_a_goal_routed_in_real_is_not_sent_after_the_fall() -> None:
    """S-02: the side goes away while the goal waits for its server: nothing is sent."""
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    _released(boundary)
    assert boundary._authority.request(TwinMode.MODE_REAL, "", "run", False).accepted
    gone = {COUNTERPART: boundary._gone[COUNTERPART]}

    def fall() -> None:
        with boundary._lock:
            boundary._changed_connection(*boundary._connections.apply(_line(SIDE_DOWN)))

    client = _Client(on_wait=fall)
    boundary._clients = {(COUNTERPART, "move_to"): client}
    refused = boundary._dispatch(
        SimpleNamespace(side_name="move_to"),
        SimpleNamespace(request=object()),
        (COUNTERPART,),
        TwinMode.MODE_REAL,
        gone,
    )
    assert isinstance(refused, ResultCode), refused
    assert refused.code == ResultCode.PRECONDITION_FAILED
    assert "no side was commanded" in refused.detail
    assert client.sent == [], "a goal decided under REAL was sent after the fall"


def test_a_goal_whose_side_went_away_in_an_unchanged_mode_is_not_sent() -> None:
    """S-02: the side's `gone` alone refuses, whatever the mode says."""
    boundary = _kept_boundary()
    gone = threading.Event()
    gone.set()
    client = _Client()
    boundary._clients = {(COUNTERPART, "move_to"): client}
    refused = boundary._dispatch(
        SimpleNamespace(side_name="move_to"),
        SimpleNamespace(request=object()),
        (COUNTERPART,),
        boundary._authority.mode,
        {COUNTERPART: gone},
    )
    assert isinstance(refused, ResultCode) and "went away" in refused.detail
    assert client.sent == []
    # Nothing moved: sent.
    boundary._gone[COUNTERPART] = threading.Event()
    sent = boundary._dispatch(
        SimpleNamespace(side_name="move_to"),
        SimpleNamespace(request=object()),
        (COUNTERPART,),
        boundary._authority.mode,
        {COUNTERPART: boundary._gone[COUNTERPART]},
    )
    assert set(sent) == {COUNTERPART} and len(client.sent) == 1


def test_a_track_trajectory_is_not_published_to_a_side_that_fell() -> None:
    """S-02: routed and published under the lock, so after the fall it reaches the plant only."""
    from cite_bringup.track_command import move as track_move

    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    _released(boundary)
    assert boundary._authority.request(TwinMode.MODE_REAL, "", "run", False).accepted
    with boundary._lock:
        boundary._changed_connection(*boundary._connections.apply(_line(SIDE_DOWN)))
    boundary._on_track_command(TRACK_TOPIC, track_move("picker_track_joint", 0.0, 0.5, 2.0))
    assert boundary._track_publishers[(COUNTERPART, TRACK_TOPIC)].sent == []
    assert len(boundary._track_publishers[("plant", TRACK_TOPIC)].sent) == 1


def test_the_fall_stops_the_physical_carriage_and_holds_no_simulated_one() -> None:
    """S-03: the never-gated stop reaches the physical track at the fall, off the lock."""
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    _released(boundary)
    assert boundary._authority.request(TwinMode.MODE_REAL, "", "run", False).accepted
    boundary._read_side_states(io.StringIO(_line(SIDE_DOWN)))
    (hold,) = boundary._track_publishers[(COUNTERPART, TRACK_TOPIC)].sent
    assert hold.points[0].positions == hold.points[-1].positions, "a hold, not a move"
    assert boundary._track_publishers[("plant", TRACK_TOPIC)].sent == []
    # A side lost in SIM moved no mode, and nothing is sent.
    quiet = _kept_boundary()
    quiet._read_side_states(io.StringIO(_line(SIDE_UP) + _line(SIDE_DOWN)))
    assert quiet._track_publishers[(COUNTERPART, TRACK_TOPIC)].sent == []


def test_a_fall_whose_mode_publish_raises_is_still_applied_and_published_again() -> None:
    """S-04: the publish is logged, the side still forgotten, and the reader republishes."""
    boundary = _kept_boundary()
    boundary._connections.apply(_line(SIDE_UP))
    _released(boundary)
    assert boundary._authority.request(TwinMode.MODE_REAL, "", "run", False).accepted
    attempts: list[int] = []

    def publish() -> None:
        attempts.append(boundary._authority.mode)
        if len(attempts) == 1:
            raise RuntimeError("injected publish")

    boundary._publish_mode = publish
    boundary._read_side_states(io.StringIO(_line(SIDE_DOWN)))
    assert boundary._authority.mode == TwinMode.MODE_SIM
    assert attempts == [TwinMode.MODE_SIM] * 2, "published again as the reader ended"
    assert any("injected publish" in line for line in boundary._log.lines)
    assert boundary._physical_watches["picker"].deadman is None, "the side was still forgotten"
    assert len(boundary._track_publishers[(COUNTERPART, TRACK_TOPIC)].sent) == 1
