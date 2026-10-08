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

"""The operator console's state machine, with no ROS in it (ADR-0071).

`cell_console` (`program.console`) serves Start robot, Home, Start program,
the operator's go-ahead and Stop; this class decides every one of them. It
holds the refusals - nothing before Start robot, one request at a time, a speed
scale sent with every goal and never defaulted (`sides.required_speed_scale`'s
rule, floor included, where a side is physical), Start program only with both
arms known to be at the program's start, the go-ahead only while it is asked for
and only while the twin is heard in SIM, nothing while the twin is in a
commanding mode this console did not enter, and nothing once the process is
closing - and it runs the program's ONE sequencer, `program.cycle`, the same
`python3 -m cite_bringup.program` and `program.home` run:

* **Start robot**: `cycle.start_robot` - on a physical side the twin's mode read
  as SIM and the operator asked to clear the cell (the initializer may home the
  track), then `home.initialize` on every physical side, then custody.
* **Home**: `cycle.home` - on a physical side SIM read, the operator asked to
  clear the cell, `home.bring_to_start` through the twin, then SIM again.
* **Start program**, per cycle: a work-piece on every simulated side's table
  and its belt running (`program.part`, `program.belt`); then
  `cycle.run_program` for one cycle - SIM read, the carriage checked and the
  operator's go-ahead awaited on a physical side; custody; VALIDATED;
  `steps.run`; SIM again on a physical side.

The terminal's Enter becomes `confirm_operator`, and the terminal's Ctrl-C
becomes `stop`: the predicate a `RosCell` is built with, so the thread waiting
on the cell raises `steps.Interrupted` - a `KeyboardInterrupt` - and every path
written for Ctrl-C runs unchanged (the goal cancelled and its end read, the
track held, an initialization's track stopped and its answer awaited). Stop is
a software stop on the same command path, NOT an E-stop; a gripper motion in
progress on a physical side is not stopped by it (ADR-0070 item 4); after it,
and after a failure, nothing homes on its own (ADR-0037).

Every collaborator that reaches the cell is injected, so the tests drive this
with a fake cell and no graph. Each request blocks its caller until it ends;
the node calls them from handlers in a callback group of their own.
"""

from __future__ import annotations

from collections.abc import Callable, MutableSet, Sequence
from dataclasses import dataclass
import threading
import time

from cite_bringup.program import cycle
from cite_bringup.program.home import StartPose
from cite_bringup.program.steps import (
    EXIT_INTERRUPTED,
    Interrupted,
    speed_scale,
    Step,
    StepFailed,
)
from cite_interfaces.msg import ConsoleState, TwinMode

#: What the operator is asked before Start robot on a physical side: the
#: initializer may home the physical track and bring the carriage to its start.
START_PROMPT = (
    "Clear the cell: starting the robot enables it, and the physical track may home and "
    "move to its start. Then confirm in the panel."
)

#: What the operator is asked before a run on a physical side: the terminal's
#: `operator.PLACE_PROMPT`, answered in the panel instead.
PLACE_PROMPT = "Place the part on the table by hand and clear the cell, then confirm in the panel."

#: What the operator is asked before a home on a physical side:
#: `home.HOME_PROMPT`, answered in the panel instead.
HOME_PROMPT = (
    "Clear the cell: the track may home and move to its start, and both arms will move. "
    "Then confirm in the panel."
)

#: Each state's name, for the refusals and the log.
STATE_NAMES = {
    ConsoleState.NOT_STARTED: "NOT_STARTED",
    ConsoleState.STARTING: "STARTING",
    ConsoleState.READY: "READY",
    ConsoleState.HOMING: "HOMING",
    ConsoleState.AWAITING_OPERATOR: "AWAITING_OPERATOR",
    ConsoleState.RUNNING: "RUNNING",
    ConsoleState.STOPPING: "STOPPING",
    ConsoleState.FAULT: "FAULT",
}

#: The twin's modes that command a side: entered by another client, they mean
#: someone else may be moving the physical arm.
_COMMANDING = {TwinMode.MODE_VALIDATED: "VALIDATED", TwinMode.MODE_VIRTUAL_LEAD: "VIRTUAL_LEAD"}


@dataclass(frozen=True)
class Snapshot:
    """What `ConsoleState` publishes, apart from what the node itself hears.

    ``sequence`` grows with every snapshot taken, under the machine's lock, so
    a publisher that receives two from two threads keeps the later one.
    """

    sequence: int
    state: int
    robot_started: bool
    busy: bool
    at_start: bool
    step: str
    prompt: str
    last_error: str
    speed_scale: float
    minimum_speed_scale: float


@dataclass(frozen=True)
class Outcome:
    """How a request ended: what the service or action answers."""

    success: bool
    detail: str
    cycles_completed: int = 0


class _Observed:
    """A cell that remembers the last step failure, a cancel that failed, and VALIDATED.

    `steps.run` and `home.run_home` report a failure by saying it; the console
    needs it as a value, to answer with the failure and to grade a stop whose
    cancel did not go through as a FAULT rather than READY. ``entered`` is told
    True before VALIDATED is asked for, and False once SIM is confirmed, so the
    machine knows whether a commanding mode it hears is its own.
    """

    def __init__(self, cell, entered: Callable[[bool], None]) -> None:
        self._cell = cell
        self._entered = entered
        self.failure: str | None = None
        self.cancel_failure: str | None = None

    def cancel(self) -> None:
        try:
            self._cell.cancel()
        except Exception as error:  # noqa: BLE001 - recorded, and re-raised to the caller
            self.cancel_failure = str(error)
            raise

    def enter_validated(self, **kwargs) -> None:
        # Before the ask: a refused or unanswered ask may still have entered.
        self._entered(True)
        self._recorded(self._cell.enter_validated, **kwargs)

    def leave_validated(self) -> bool:
        left = self._cell.leave_validated()
        if left:
            self._entered(False)
        return left

    def __getattr__(self, name: str):
        attribute = getattr(self._cell, name)
        if not callable(attribute):
            return attribute
        return lambda *args, **kwargs: self._recorded(attribute, *args, **kwargs)

    def _recorded(self, call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        except StepFailed as failure:
            self.failure = str(failure)
            raise


class ConsoleMachine:
    """Decide and run the operator's requests, one at a time (ADR-0071).

    ``make_cell(speed, interrupted)`` returns a `RosCell`-like cell driving the
    twin at ``speed`` that raises `Interrupted` once ``interrupted()`` is true,
    and ``speed`` None for a cell that is never handed a step; the caller
    closes it. ``initialize_physical(say, interrupted)`` is `home.initialize`
    for the plan's physical sides. ``place_parts(may_hold, say, interrupted)``
    puts a work-piece on every simulated side (`program.part`), clearing the
    sides in ``may_hold`` first. ``set_belts(running, say, interrupted,
    match_ceiling_s)`` runs or stops every simulated side's belt and says
    whether every one took it (`program.belt`). ``check_scale`` returns a goal's
    scale or raises `ValueError` (`sides.required_speed_scale`), and
    ``minimum_speed_scale`` is the floor it applies, 0 for none.
    ``heard_twin_mode`` is the twin's mode as last heard on its topic, None
    before any. ``on_change`` is told every new `Snapshot`; ``log`` every line
    said.
    """

    def __init__(
        self,
        *,
        physical: Sequence[str],
        simulated: Sequence[str],
        home_steps: Sequence[Step],
        start: StartPose,
        steps: Sequence[Step],
        make_cell: Callable[[float | None, Callable[[], bool]], object],
        initialize_physical: Callable[[Callable[[str], None], Callable[[], bool]], None],
        place_parts: Callable[
            [MutableSet[str], Callable[[str], None], Callable[[], bool]], None
        ],
        set_belts: Callable[
            [bool, Callable[[str], None], Callable[[], bool] | None, float | None], bool
        ],
        heard_twin_mode: Callable[[], int | None] = lambda: None,
        check_scale: Callable[[float], float] = speed_scale,
        minimum_speed_scale: float = 0.0,
        on_change: Callable[[Snapshot], None] = lambda snapshot: None,
        log: Callable[[str], None] = print,
    ) -> None:
        self._physical = list(physical)
        self._simulated = list(simulated)
        self._home_steps = list(home_steps)
        self._start = start
        self._steps = list(steps)
        self._make_cell = make_cell
        self._initialize_physical = initialize_physical
        self._place_parts = place_parts
        self._set_belts = set_belts
        self._heard_twin_mode = heard_twin_mode
        self._check_scale = check_scale
        self._minimum_speed_scale = float(minimum_speed_scale)
        self._on_change = on_change
        self._log = log
        self._lock = threading.Lock()
        #: Woken by a go-ahead, a stop, and the end of a request.
        self._changed = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._state = ConsoleState.NOT_STARTED
        self._started = False
        self._busy = False
        self._at_start = False
        self._step = ""
        self._prompt = ""
        self._error = ""
        self._speed = 0.0
        self._confirmed = False
        self._sequence = 0
        #: Set once the process began to close: every request is refused after.
        self._closing = False
        #: When the request in flight must have ended its stop, monotonic, or
        #: None before the shutdown began (`stop_deadline`).
        self._stop_deadline: float | None = None
        #: Who asked for the request in progress (an action goal's id), or None.
        self._owner: object = None
        #: The request's own cancel, asked beside the stop (an action goal's).
        self._cancelled: Callable[[], bool] | None = None
        #: Whether this console asked the twin for VALIDATED and has not had
        #: SIM confirmed since.
        self._entered = False
        #: The simulated sides whose world may hold a work-piece. Unknown until
        #: Start robot, which assumes every one may (`program.part`).
        self._parts: set[str] = set(self._simulated)
        #: Whether this console started the belts and has not stopped them: a
        #: stop, a failure and the end of the process stop them. Read and
        #: written only under `_belt_lock`, which also serializes the commands.
        self._belts_running = False
        self._belt_lock = threading.Lock()

    # ------------------------------------------------------------- reading

    @property
    def physical(self) -> list[str]:
        return list(self._physical)

    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snapshot()

    def stop_deadline(self) -> float | None:
        """Return the shutdown's deadline for the request in flight, monotonic, or None.

        None until `shutdown` begins. The cells and the initializer this
        machine drives are built with it (R2-02): none of their waits - a
        cancel, its goal's end, a return to SIM, a server, the initializer's
        answer - runs past it, so the stop in flight ends within the
        shutdown's own ceiling.
        """
        return self._stop_deadline

    def interrupted(self) -> bool:
        """Whether a stop, or the request's own cancel, was asked for the request in progress."""
        if self._stop.is_set():
            return True
        cancelled = self._cancelled
        return cancelled is not None and cancelled()

    def motion_refusal(self, scale: float, cycles: int | None = None) -> str | None:
        """Say why a Home (``cycles`` None) or Start program goal would be rejected now, or None.

        Asked when the goal arrives, and again when it is started: two goals
        that both pass here race for the one request, and the second loses.
        """
        with self._lock:
            return self._motion_refusal(scale, cycles)

    # ------------------------------------------------------------ requests

    def start_robot(self) -> Outcome:
        """Enable the robot: SIM and the cell cleared on a physical side, initialize, custody."""
        refusal = self._begin(ConsoleState.STARTING, self._refusal, 0.0)
        if refusal is not None:
            return Outcome(False, refusal)
        with self._lock:
            # Nothing this console placed is known any more, and nothing it
            # knew of the arms' place either.
            self._parts = set(self._simulated)
            self._at_start = False
        say = self._sayer()
        try:
            say("starting the robot")
            cell = self._make_cell(None, self.interrupted)
            observed = _Observed(cell, self._set_entered)
            try:
                cycle.start_robot(
                    observed,
                    physical=self._physical,
                    say=say,
                    await_operator=self._awaiter(observed),
                    initialize_physical=lambda: self._initialize_physical(
                        say, self.interrupted
                    ),
                    prompt=START_PROMPT,
                )
            finally:
                cell.close()
        except Interrupted:
            self._end(ConsoleState.NOT_STARTED, started=False)
            return Outcome(False, "stopped before the robot was started")
        except StepFailed as failure:
            return self._fault(f"Start robot failed: {failure}", started=False)
        except Exception as error:  # noqa: BLE001 - never leave the console busy
            return self._fault(f"Start robot failed unexpectedly: {error!r}", started=False)
        self._end(ConsoleState.READY, started=True)
        return Outcome(True, "the robot is started; Home is accepted")

    def home(
        self,
        scale: float,
        feedback: Callable[[str], None] | None = None,
        *,
        owner: object = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> Outcome:
        """Bring both arms to the program's start, as `./scripts/home` does (`cycle.home`)."""
        refusal = self._begin(
            ConsoleState.HOMING,
            lambda: self._motion_refusal(scale),
            scale,
            owner=owner,
            cancelled=cancelled,
        )
        if refusal is not None:
            return Outcome(False, refusal)
        say = self._sayer(feedback)
        with self._lock:
            self._at_start = False
        failure: str | None = None
        stopped = False
        problems: list[str] = []
        observed = None
        try:
            cell = self._make_cell(scale, self.interrupted)
            observed = _Observed(cell, self._set_entered)
            try:
                ended = cycle.home(
                    observed,
                    self._home_steps,
                    self._start,
                    physical=self._physical,
                    scale=scale,
                    say=say,
                    await_operator=self._awaiter(observed),
                    initialize_physical=lambda: self._initialize_physical(
                        say, self.interrupted
                    ),
                    prompt=HOME_PROMPT,
                )
            finally:
                cell.close()
            stopped = ended.status == EXIT_INTERRUPTED
            if ended.sim_confirmed is False:
                problems.append("the twin did not confirm SIM after the home")
            if ended.status != 0 and not stopped:
                failure = (
                    ended.failure
                    or observed.failure
                    or (problems.pop(0) if problems else "the home did not complete")
                )
        except Exception as error:  # noqa: BLE001 - never leave the console busy
            failure = f"unexpected: {error!r}"
        if observed is not None and observed.cancel_failure is not None:
            problems.append(f"the cancel failed: {observed.cancel_failure}")
        outcome = self._finish(
            "Home", stopped, failure, problems, "both arms are at the program's start"
        )
        if outcome.success:
            with self._lock:
                self._at_start = True
                snapshot = self._snapshot()
            self._on_change(snapshot)
        return outcome

    def run_program(
        self,
        scale: float,
        cycles: int,
        feedback: Callable[[int, int, int, str], None] | None = None,
        *,
        owner: object = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> Outcome:
        """Run ``cycles`` cycles of the program, one part each, by `cycle.run_program`."""
        refusal = self._begin(
            ConsoleState.RUNNING,
            lambda: self._motion_refusal(scale, cycles),
            scale,
            owner=owner,
            cancelled=cancelled,
        )
        if refusal is not None:
            return Outcome(False, refusal)
        say = self._sayer()

        def on_step(number_of_cycle: int, number: int, count: int, step: Step) -> None:
            if feedback is not None:
                feedback(number_of_cycle, number, count, str(step))

        failure: str | None = None
        stopped = False
        problems: list[str] = []
        completed = 0
        observed = None
        try:
            cell = self._make_cell(scale, self.interrupted)
            observed = _Observed(cell, self._set_entered)
            try:
                for number in range(1, cycles + 1):
                    self._raise_if_stopped()
                    with self._lock:
                        # The first step moves the arm away from the start.
                        self._at_start = False
                    say(f"cycle {number}: putting a work-piece on each simulated side's table")
                    self._place_parts(self._parts, say, self.interrupted)
                    self._start_belts(say)
                    self._raise_if_stopped()
                    ended = cycle.run_program(
                        observed,
                        self._steps,
                        physical=self._physical,
                        scale=scale,
                        cycles=1,
                        say=say,
                        await_operator=self._awaiter(observed),
                        prompt=PLACE_PROMPT,
                        first_cycle=number,
                        on_step=on_step,
                    )
                    if ended.sim_confirmed is False:
                        problems.append(
                            "the twin did not confirm SIM after the cycle, so no one is "
                            "asked into the cell"
                        )
                    if ended.status == EXIT_INTERRUPTED:
                        stopped = True
                        break
                    if ended.status != 0:
                        failure = (
                            ended.failure
                            or observed.failure
                            or (problems.pop(0) if problems else None)
                            or f"cycle {number} did not complete"
                        )
                        break
                    completed += 1
                    with self._lock:
                        # A cycle of the real program ends where it began.
                        self._at_start = True
            finally:
                cell.close()
        except Interrupted:
            stopped = True
        except StepFailed as step_failure:
            failure = str(step_failure)
        except Exception as error:  # noqa: BLE001 - never leave the console busy
            failure = f"unexpected: {error!r}"
        if observed is not None and observed.cancel_failure is not None:
            problems.append(f"the cancel failed: {observed.cancel_failure}")
        outcome = self._finish(
            "Start program", stopped, failure, problems, f"{completed} cycle(s) completed"
        )
        return Outcome(outcome.success, outcome.detail, completed)

    def confirm_operator(self) -> Outcome:
        """Answer the go-ahead the console is asking for, while the twin is heard in SIM."""
        with self._lock:
            if self._closing:
                return Outcome(False, "the console is closing")
            if self._state != ConsoleState.AWAITING_OPERATOR:
                return Outcome(
                    False,
                    f"nothing is awaiting the operator: the console is "
                    f"{STATE_NAMES[self._state]}, not AWAITING_OPERATOR",
                )
            mode = self._heard_twin_mode()
            if self._physical and mode != TwinMode.MODE_SIM:
                return Outcome(
                    False,
                    f"the twin is heard in mode {mode}, not SIM ({TwinMode.MODE_SIM}), so no "
                    "one is let into the cell; the question stands until it is in SIM or "
                    "the request is stopped",
                )
            self._confirmed = True
            self._changed.notify_all()
        return Outcome(True, "the operator confirmed")

    def stop(self, owner: object = None) -> Outcome:
        """Ask the request in progress to stop: a software stop, not an E-stop.

        ``owner`` is an action goal's id: its cancel stops the request only if
        that goal owns it. In FAULT on a pair with a physical side, while the
        twin is not heard in SIM, a Stop with no owner asks the twin for SIM
        again and answers once it has answered (StopCell.srv).
        """
        with self._lock:
            if owner is not None and (not self._busy or owner != self._owner):
                return Outcome(False, "that goal does not own the request in progress")
            if not self._busy:
                resim = (
                    self._state == ConsoleState.FAULT
                    and self._physical
                    and not self._closing
                    and self._heard_twin_mode() != TwinMode.MODE_SIM
                )
                if not resim:
                    return Outcome(False, "nothing is in progress, so there is nothing to stop")
            elif self._stop.is_set():
                return Outcome(False, "already stopping")
            else:
                self._stop.set()
                self._state = ConsoleState.STOPPING
                self._changed.notify_all()
                snapshot = self._snapshot()
                resim = False
        if resim:
            return self._ask_for_sim_again()
        self._on_change(snapshot)
        return Outcome(
            True,
            "stopping: the goal in flight is cancelled, its end awaited and the track held. "
            "This is a software stop on the command path, not an E-stop, and a gripper "
            "motion already in progress on a physical side runs to its end",
        )

    def shutdown(
        self,
        ceiling_s: float,
        belt_match_ceiling_s: float | None = None,
        tail_s: float = 0.0,
    ) -> bool:
        """Refuse everything from now on, stop what is in progress, wait, stop the belts.

        For the end of the process and the node's lifecycle shutdown. Returns
        whether nothing was left running. What it spends, and nothing more
        (R2-02):

        * the wait for the request in flight, at most ``ceiling_s``. From the
          start of the shutdown its cell's and its initializer's waits are cut
          at ``ceiling_s - tail_s`` (`stop_deadline`); ``tail_s`` is what the
          request may still spend after that cut, which the caller bounds;
        * then, only once that request has ended, the belts' stop, ONCE: the
          request leaves its belts to this stop while the process closes, so
          the two never queue on one lock. Each side waits for its subscriber
          within ``belt_match_ceiling_s``, then for the acknowledgement within
          `belt.ACK_CEILING_S`. A request that did not end within
          ``ceiling_s``, or a belt stop already held by another shutdown, is
          reported and not waited for.
        """
        with self._lock:
            self._closing = True
            if self._stop_deadline is None:
                self._stop_deadline = time.monotonic() + max(0.0, ceiling_s - tail_s)
        self.stop()
        with self._lock:
            idle = self._changed.wait_for(lambda: not self._busy, timeout=ceiling_s)
        if not idle:
            self._log(
                f"shutdown: the request in progress did not end within {ceiling_s:g} s; "
                "its belts, if any, are not stopped from here"
            )
            return False
        if not self._belt_lock.acquire(blocking=False):
            self._log("shutdown: another stop is commanding the belts; not waited for")
            return False
        try:
            belts = self._stop_belts_held(self._log, belt_match_ceiling_s)
        finally:
            self._belt_lock.release()
        if belts is not None:
            self._log(f"shutdown: {belts}")
        return belts is None

    # ------------------------------------------------------------ mechanism

    def _refusal(self, foreign_mode_refuses: bool = True) -> str | None:
        """Why no request is accepted now, whatever it is; None if one may be.

        ``foreign_mode_refuses`` False is for the one request that only ever
        asks the twin for SIM, which a commanding mode is no reason to refuse.
        """
        if self._closing:
            return "the console is closing"
        if self._busy:
            return f"another request is in progress ({STATE_NAMES[self._state]})"
        if foreign_mode_refuses and self._physical and not self._entered:
            mode = self._heard_twin_mode()
            if mode in _COMMANDING:
                return (
                    f"the twin is in {_COMMANDING[mode]}, which this console did not ask "
                    f"for: another client may be commanding {', '.join(self._physical)}. "
                    "Nothing is accepted until the twin is back in SIM"
                )
        return None

    def _motion_refusal(self, scale: float, cycles: int | None = None) -> str | None:
        try:
            self._check_scale(scale)
        except ValueError as error:
            return (
                f"{error}: the panel sends the speed scale explicitly with every goal, and "
                "none is defaulted (ADR-0071)"
            )
        if cycles is not None and cycles < 1:
            return f"cycles must be at least 1, not {cycles}; 0 is not read as 'forever'"
        if not self._started:
            return "Start robot has not succeeded, so nothing else is accepted"
        refusal = self._refusal()
        if refusal is not None:
            return refusal
        if self._state != ConsoleState.READY:
            return f"the console is {STATE_NAMES[self._state]}, not READY"
        if cycles is not None and not self._at_start:
            return (
                "the arms are not known to be at the program's start: Home first. A stop, a "
                "failure and Start robot each leave that unknown"
            )
        return None

    def _begin(
        self,
        state: int,
        refusal: Callable[[], str | None],
        scale: float,
        *,
        owner: object = None,
        cancelled: Callable[[], bool] | None = None,
        foreign_mode_refuses: bool = True,
    ) -> str | None:
        with self._lock:
            reason = self._refusal(foreign_mode_refuses) or refusal()
            if reason is not None:
                return reason
            self._busy = True
            self._state = state
            self._owner = owner
            self._cancelled = cancelled
            self._step = ""
            self._prompt = ""
            self._error = ""
            if scale:
                self._speed = scale
            self._confirmed = False
            self._stop.clear()
            if cancelled is not None and cancelled():
                # Cancelled before it began: stopped at its first wait.
                self._stop.set()
                self._state = ConsoleState.STOPPING
            snapshot = self._snapshot()
        self._on_change(snapshot)
        return None

    def _end(self, state: int, *, started: bool | None = None, error: str = "") -> None:
        with self._lock:
            self._state = state
            self._busy = False
            self._owner = None
            self._cancelled = None
            self._prompt = ""
            self._error = error
            if started is not None:
                self._started = started
            self._changed.notify_all()
            snapshot = self._snapshot()
        self._on_change(snapshot)

    def _fault(self, error: str, started: bool | None = None) -> Outcome:
        self._log(f"FAULT: {error}")
        with self._lock:
            self._at_start = False
        self._end(ConsoleState.FAULT, started=started, error=error)
        return Outcome(False, error)

    def _finish(
        self,
        what: str,
        stopped: bool,
        failure: str | None,
        problems: list[str],
        done: str,
    ) -> Outcome:
        """End a motion request: READY, or FAULT with why. Never a homing move (ADR-0037).

        Reached only once the cell has returned: every cancel answered and the
        cancelled goal's end read (`RosCell.cancel`), so READY is said of a
        cell that has stopped, or the cancel's failure makes it a FAULT.
        """
        if stopped or failure is not None:
            with self._lock:
                self._at_start = False
                # While the process closes, the shutdown stops the belts once
                # this request has ended, with its own short ceilings (R2-02).
                closing = self._closing
            belts = None if closing else self._stop_belts(self._sayer())
            if belts is not None:
                problems.append(belts)
        if failure is not None:
            return self._fault("; ".join([f"{what} failed: {failure}", *problems]))
        if problems:
            verb = "stopped" if stopped else "ended"
            return self._fault("; ".join([f"{what} {verb}, and the stop was not confirmed",
                                          *problems]))
        self._end(ConsoleState.READY)
        if stopped:
            return Outcome(False, f"{what} was stopped; nothing homes on its own (ADR-0037)")
        return Outcome(True, f"{what}: {done}")

    def _ask_for_sim_again(self) -> Outcome:
        """In FAULT with the twin not in SIM: ask for SIM once more, and say what came of it."""
        refusal = self._begin(
            ConsoleState.STOPPING, lambda: None, 0.0, foreign_mode_refuses=False
        )
        if refusal is not None:
            return Outcome(False, refusal)
        say = self._sayer()
        say("Stop in FAULT: asking the twin for SIM again")
        try:
            cell = self._make_cell(None, lambda: False)
            try:
                left = _Observed(cell, self._set_entered).leave_validated()
            finally:
                cell.close()
        except Exception as error:  # noqa: BLE001 - never leave the console busy
            left, why = False, f"{error!r}"
        else:
            why = "the twin did not confirm SIM"
        if left:
            error = "the twin confirmed SIM after the fault; Start robot is the way back"
            self._end(ConsoleState.FAULT, error=error)
            return Outcome(True, error)
        error = f"asked for SIM again after the fault, and {why}"
        self._end(ConsoleState.FAULT, error=error)
        return Outcome(False, error)

    def _start_belts(self, say: Callable[[str], None]) -> None:
        """Run every simulated side's belt once, for the console's life, or raise StepFailed."""
        with self._belt_lock:
            if self._belts_running:
                return
            # Set before the command: a side that took its setpoint while the
            # other refused is a running belt.
            self._belts_running = True
            if not self._set_belts(True, say, self.interrupted, None):
                raise StepFailed("a side's belt would not take its setpoint")

    def _stop_belts(
        self, say: Callable[[str], None], match_ceiling_s: float | None = None
    ) -> str | None:
        """Stop the belts this console started, if it did; say why not, or None."""
        with self._belt_lock:
            return self._stop_belts_held(say, match_ceiling_s)

    def _stop_belts_held(
        self, say: Callable[[str], None], match_ceiling_s: float | None = None
    ) -> str | None:
        """`_stop_belts`, with `_belt_lock` already held by the caller."""
        if not self._belts_running:
            return None
        try:
            confirmed = self._set_belts(False, say, None, match_ceiling_s)
        except Exception as error:  # noqa: BLE001 - reported as the stop's failure
            return f"the belts could not be stopped: {error!r}"
        if not confirmed:
            return "a side's belt did not confirm the stop; it may still be running"
        self._belts_running = False
        return None

    def _awaiter(self, cell) -> Callable[[str], str]:
        """Return the `read` `confirm_operator` asks the operator with, for ``cell``.

        It shows ``prompt`` in AWAITING_OPERATOR and waits for
        `confirm_operator` - which is refused unless the twin is heard in SIM -
        or a stop, which raises `Interrupted` as Ctrl-C at the terminal prompt
        would have. Once confirmed it READS the twin's mode again, from the
        twin, and refuses anything but SIM: a confirmation is never taken as
        leave to enter a cell the twin may command (ADR-0071).
        """

        def await_operator(prompt: str) -> str:
            with self._lock:
                if self.interrupted():
                    raise Interrupted("stopped while the operator was asked")
                previous = self._state
                self._state = ConsoleState.AWAITING_OPERATOR
                self._prompt = prompt
                self._step = "awaiting the operator's confirmation"
                self._confirmed = False
                snapshot = self._snapshot()
            self._on_change(snapshot)
            self._log(prompt)
            with self._lock:
                self._changed.wait_for(lambda: self._confirmed or self._stop.is_set())
                self._prompt = ""
                if self._stop.is_set():
                    raise Interrupted("stopped while the operator was asked")
                self._confirmed = False
                self._state = previous
                self._step = "the operator confirmed"
                snapshot = self._snapshot()
            self._on_change(snapshot)
            mode = cell.twin_mode()
            if mode != TwinMode.MODE_SIM:
                raise StepFailed(
                    f"the operator confirmed, and the twin was then read in mode {mode}, not "
                    f"SIM ({TwinMode.MODE_SIM}); nothing goes on"
                )
            return ""

        return await_operator

    def _set_entered(self, entered: bool) -> None:
        with self._lock:
            self._entered = entered

    def _raise_if_stopped(self) -> None:
        if self.interrupted():
            raise Interrupted("stopped from the operator console")

    def _sayer(self, feedback: Callable[[str], None] | None = None) -> Callable[[str], None]:
        def say(text: str) -> None:
            self._log(text)
            with self._lock:
                self._step = text
                snapshot = self._snapshot()
            self._on_change(snapshot)
            if feedback is not None:
                feedback(text)

        return say

    def _snapshot(self) -> Snapshot:
        self._sequence += 1
        return Snapshot(
            sequence=self._sequence,
            state=self._state,
            robot_started=self._started,
            busy=self._busy,
            at_start=self._at_start,
            step=self._step,
            prompt=self._prompt,
            last_error=self._error,
            speed_scale=self._speed,
            minimum_speed_scale=self._minimum_speed_scale,
        )
