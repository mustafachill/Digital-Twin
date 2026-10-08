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
the part go-ahead and Stop; this class decides every one of them. It holds the
refusals - nothing before Start robot, one request at a time, a speed scale in
(0, 1] sent with every goal and never defaulted, the go-ahead only while it is
asked for - and it composes the same library calls `python3 -m
cite_bringup.program` and `program.home` compose, in their order:

* **Start robot**: `home.initialize` on every physical side (nothing on an
  all-simulated pair), then the arm's custody (`RosCell.refuse_if_holding`).
* **Home**: on a physical side, the twin's mode read as SIM and the operator
  asked to clear the cell (`operator.confirm_operator`, the home prompt); then
  `home.bring_to_start` through the twin; then, with a physical side, SIM again.
* **Start program**, per cycle: a work-piece on every simulated side's table
  and its belt running (`program.part`, `program.belt`); with a physical side,
  the mode read as SIM, the carriage checked and the operator's go-ahead
  awaited; custody read; VALIDATED; one cycle (`steps.run`); with a physical
  side, SIM again.

The terminal's Enter becomes `confirm_part`, and the terminal's Ctrl-C becomes
`stop`: the predicate a `RosCell` is built with, so the thread waiting on the
cell raises `steps.Interrupted` - a `KeyboardInterrupt` - and every path
written for Ctrl-C runs unchanged (the goal cancelled, the track held). Stop is
a software stop on the same command path, NOT an E-stop; after it, and after a
failure, nothing homes on its own (ADR-0037).

Every collaborator that reaches the cell is injected, so the tests drive this
with a fake cell and no graph. Each request blocks its caller until it ends;
the node calls them from handlers in a callback group of their own.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import threading

from cite_bringup.program.home import bring_to_start, StartPose
from cite_bringup.program.operator import confirm_operator
from cite_bringup.program.steps import (
    EXIT_INTERRUPTED,
    Interrupted,
    run,
    speed_scale,
    Step,
    StepFailed,
)
from cite_interfaces.msg import ConsoleState

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
    ConsoleState.AWAITING_PART: "AWAITING_PART",
    ConsoleState.RUNNING: "RUNNING",
    ConsoleState.STOPPING: "STOPPING",
    ConsoleState.FAULT: "FAULT",
}


@dataclass(frozen=True)
class Snapshot:
    """What `ConsoleState` publishes, apart from what the node itself hears."""

    state: int
    robot_started: bool
    busy: bool
    step: str
    last_error: str
    speed_scale: float


@dataclass(frozen=True)
class Outcome:
    """How a request ended: what the service or action answers."""

    success: bool
    detail: str
    cycles_completed: int = 0


class _Observed:
    """A cell that remembers the last step failure and a cancel that failed.

    `steps.run` and `home.run_home` report both by saying them; the console
    needs them as values, to answer with the failure and to grade a stop whose
    cancel did not go through as a FAULT rather than READY.
    """

    def __init__(self, cell) -> None:
        self._cell = cell
        self.failure: str | None = None
        self.cancel_failure: str | None = None

    def cancel(self) -> None:
        try:
            self._cell.cancel()
        except Exception as error:  # noqa: BLE001 - recorded, and re-raised to the caller
            self.cancel_failure = str(error)
            raise

    def __getattr__(self, name: str):
        attribute = getattr(self._cell, name)
        if not callable(attribute):
            return attribute

        def call(*args, **kwargs):
            try:
                return attribute(*args, **kwargs)
            except StepFailed as failure:
                self.failure = str(failure)
                raise

        return call


class ConsoleMachine:
    """Decide and run the operator's requests, one at a time (ADR-0071).

    ``make_cell(speed, interrupted)`` returns a `RosCell`-like cell driving the
    twin at ``speed`` that raises `Interrupted` once ``interrupted()`` is true,
    and ``speed`` None for a cell that only reads and is never handed a step;
    the caller closes it. ``initialize_physical(say, interrupted)`` is
    `home.initialize` for the plan's physical sides. ``place_parts(remove_first,
    say)`` puts a work-piece on every simulated side (`program.part`), and
    ``set_belts(running, say)`` runs or stops every simulated side's belt and
    says whether every one took it (`program.belt`). ``on_change`` is told
    every new `Snapshot`; ``log`` every line said.
    """

    def __init__(
        self,
        *,
        physical: Sequence[str],
        home_steps: Sequence[Step],
        start: StartPose,
        steps: Sequence[Step],
        make_cell: Callable[[float | None, Callable[[], bool]], object],
        initialize_physical: Callable[[Callable[[str], None], Callable[[], bool]], None],
        place_parts: Callable[[bool, Callable[[str], None]], None],
        set_belts: Callable[[bool, Callable[[str], None]], bool],
        on_change: Callable[[Snapshot], None] = lambda snapshot: None,
        log: Callable[[str], None] = print,
    ) -> None:
        self._physical = list(physical)
        self._home_steps = list(home_steps)
        self._start = start
        self._steps = list(steps)
        self._make_cell = make_cell
        self._initialize_physical = initialize_physical
        self._place_parts = place_parts
        self._set_belts = set_belts
        self._on_change = on_change
        self._log = log
        self._lock = threading.Lock()
        #: Woken by a go-ahead, a stop, and the end of a request.
        self._changed = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._state = ConsoleState.NOT_STARTED
        self._started = False
        self._busy = False
        self._step = ""
        self._error = ""
        self._speed = 0.0
        self._confirmed = False
        #: Whether a work-piece this console spawned may still be in a world,
        #: so the next one is spawned after removing it.
        self._spawned = False
        #: Whether this console started the belts and has not stopped them:
        #: a stop, a failure and the end of the process stop them.
        self._belts_running = False

    # ------------------------------------------------------------- reading

    @property
    def physical(self) -> list[str]:
        return list(self._physical)

    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snapshot()

    def interrupted(self) -> bool:
        """Whether a stop was asked for the request in progress."""
        return self._stop.is_set()

    def motion_refusal(self, scale: float, cycles: int | None = None) -> str | None:
        """Say why a Home or Start program goal would be rejected now, or None.

        Asked when the goal arrives, and again when it is started: two goals
        that both pass here race for the one request, and the second loses.
        """
        with self._lock:
            return self._motion_refusal(scale, cycles)

    # ------------------------------------------------------------ requests

    def start_robot(self) -> Outcome:
        """Initialize every physical arm and read custody; READY on success."""
        refusal = self._begin(ConsoleState.STARTING, lambda: None, 0.0)
        if refusal is not None:
            return Outcome(False, refusal)
        say = self._sayer()
        try:
            say("starting the robot: initializing every physical arm, reading custody")
            self._initialize_physical(say, self.interrupted)
            cell = self._make_cell(None, self.interrupted)
            try:
                cell.refuse_if_holding()
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
        return Outcome(True, "the robot is started; Home and Start program are accepted")

    def home(self, scale: float, feedback: Callable[[str], None] | None = None) -> Outcome:
        """Bring both arms to the program's start, as `program.home` does."""
        refusal = self._begin(
            ConsoleState.HOMING, lambda: self._motion_refusal(scale), scale
        )
        if refusal is not None:
            return Outcome(False, refusal)
        say = self._sayer(feedback)
        failure: str | None = None
        stopped = False
        problems: list[str] = []
        observed = None
        try:
            cell = self._make_cell(scale, self.interrupted)
            observed = _Observed(cell)
            try:
                if self._physical:
                    # Read, not assumed (SA-S-05); a carriage apart is no
                    # refusal before a home, which is what brings it back.
                    confirm_operator(
                        cell.twin_mode(),
                        self._physical,
                        scale,
                        say,
                        self._await_part,
                        lambda: cell.carriage_refusal(homing=True),
                        prompt=HOME_PROMPT,
                    )
                bring_to_start(
                    self._home_steps,
                    self._start,
                    observed,
                    lambda: self._initialize_physical(say, self.interrupted),
                    say,
                    via_twin=True,
                )
            except Interrupted:
                stopped = True
            except StepFailed as step_failure:
                failure = str(step_failure)
            finally:
                # As `program.home`: the operator's next step may be in the
                # cell, so SIM is asked for whatever happened.
                if self._physical and not cell.leave_validated():
                    problems.append("the twin did not confirm SIM after the home")
                cell.close()
        except Exception as error:  # noqa: BLE001 - never leave the console busy
            failure = f"unexpected: {error!r}"
        if observed is not None and observed.cancel_failure is not None:
            problems.append(f"the cancel failed: {observed.cancel_failure}")
        return self._finish(
            "Home", stopped, failure, problems, "both arms are at the program's start"
        )

    def run_program(
        self,
        scale: float,
        cycles: int,
        feedback: Callable[[int, int, int, str], None] | None = None,
    ) -> Outcome:
        """Run ``cycles`` cycles of the program, as `./scripts/program` does, one part each."""
        refusal = self._begin(
            ConsoleState.RUNNING, lambda: self._motion_refusal(scale, cycles), scale
        )
        if refusal is not None:
            return Outcome(False, refusal)
        say = self._sayer()

        def on_step(cycle: int, number: int, count: int, step: Step) -> None:
            if feedback is not None:
                feedback(cycle, number, count, str(step))

        failure: str | None = None
        stopped = False
        problems: list[str] = []
        completed = 0
        observed = None
        try:
            cell = self._make_cell(scale, self.interrupted)
            observed = _Observed(cell)
            entering = False
            try:
                for cycle in range(1, cycles + 1):
                    self._raise_if_stopped()
                    say(f"cycle {cycle}: putting a work-piece on each simulated side's table")
                    self._place_parts(self._spawned, say)
                    self._spawned = True
                    if not self._belts_running:
                        # Set before the command: a side that took its
                        # setpoint while the other refused is a running belt.
                        self._belts_running = True
                        if not self._set_belts(True, say):
                            raise StepFailed("a side's belt would not take its setpoint")
                    self._raise_if_stopped()
                    if self._physical:
                        confirm_operator(
                            cell.twin_mode(),
                            self._physical,
                            scale,
                            say,
                            self._await_part,
                            cell.carriage_refusal,
                            prompt=PLACE_PROMPT,
                        )
                    cell.refuse_if_holding()
                    entering = True
                    cell.enter_validated()
                    status = run(
                        self._steps, observed, 1, say, first_cycle=cycle, on_step=on_step
                    )
                    if self._physical:
                        # Before the next question to the operator (SA-S-05).
                        entering = False
                        if not cell.leave_validated():
                            raise StepFailed(
                                "the twin did not confirm SIM after the cycle, so no one is "
                                "asked into the cell"
                            )
                    if status == EXIT_INTERRUPTED:
                        stopped = True
                        break
                    if status != 0:
                        failure = observed.failure or f"cycle {cycle} did not complete"
                        break
                    completed += 1
            except Interrupted:
                stopped = True
            except StepFailed as step_failure:
                failure = str(step_failure)
            finally:
                if self._physical and entering and not cell.leave_validated():
                    problems.append("the twin did not confirm SIM")
                cell.close()
        except Exception as error:  # noqa: BLE001 - never leave the console busy
            failure = f"unexpected: {error!r}"
        if observed is not None and observed.cancel_failure is not None:
            problems.append(f"the cancel failed: {observed.cancel_failure}")
        outcome = self._finish(
            "Start program", stopped, failure, problems, f"{completed} cycle(s) completed"
        )
        return Outcome(outcome.success, outcome.detail, completed)

    def confirm_part(self) -> Outcome:
        """Answer the go-ahead the console is asking for; refused when it asks for none."""
        with self._lock:
            if self._state != ConsoleState.AWAITING_PART:
                return Outcome(
                    False,
                    f"nothing is awaiting the part: the console is "
                    f"{STATE_NAMES[self._state]}, not AWAITING_PART",
                )
            self._confirmed = True
            self._changed.notify_all()
        return Outcome(True, "the operator confirmed the part is placed and the cell clear")

    def stop(self) -> Outcome:
        """Ask the request in progress to stop: a software stop, not an E-stop."""
        with self._lock:
            if not self._busy:
                return Outcome(False, "nothing is in progress, so there is nothing to stop")
            if self._stop.is_set():
                return Outcome(False, "already stopping")
            self._stop.set()
            self._state = ConsoleState.STOPPING
            self._changed.notify_all()
            snapshot = self._snapshot()
        self._on_change(snapshot)
        return Outcome(
            True,
            "stopping: the goal in flight is cancelled and the track held. This is a "
            "software stop on the command path, not an E-stop",
        )

    def shutdown(self, ceiling_s: float) -> bool:
        """Stop whatever is in progress, wait for it within ``ceiling_s``, stop the belts.

        For the end of the process. Returns whether nothing was left running.
        """
        self.stop()
        with self._lock:
            idle = self._changed.wait_for(lambda: not self._busy, timeout=ceiling_s)
        belts = self._stop_belts(self._log)
        return idle and belts is None

    # ------------------------------------------------------------ mechanism

    def _motion_refusal(self, scale: float, cycles: int | None = None) -> str | None:
        try:
            speed_scale(scale)
        except ValueError as error:
            return (
                f"{error}: the panel sends the speed scale explicitly with every goal, and "
                "none is defaulted (ADR-0071)"
            )
        if cycles is not None and cycles < 1:
            return f"cycles must be at least 1, not {cycles}; 0 is not read as 'forever'"
        if not self._started:
            return "Start robot has not succeeded, so nothing else is accepted"
        if self._busy:
            return f"another request is in progress ({STATE_NAMES[self._state]})"
        if self._state != ConsoleState.READY:
            return f"the console is {STATE_NAMES[self._state]}, not READY"
        return None

    def _begin(self, state: int, refusal: Callable[[], str | None], scale: float) -> str | None:
        with self._lock:
            if self._busy:
                return f"another request is in progress ({STATE_NAMES[self._state]})"
            reason = refusal()
            if reason is not None:
                return reason
            self._busy = True
            self._state = state
            self._step = ""
            self._error = ""
            if scale:
                self._speed = scale
            self._confirmed = False
            self._stop.clear()
            snapshot = self._snapshot()
        self._on_change(snapshot)
        return None

    def _end(self, state: int, *, started: bool | None = None, error: str = "") -> None:
        with self._lock:
            self._state = state
            self._busy = False
            self._error = error
            if started is not None:
                self._started = started
            self._changed.notify_all()
            snapshot = self._snapshot()
        self._on_change(snapshot)

    def _fault(self, error: str, started: bool | None = None) -> Outcome:
        self._log(f"FAULT: {error}")
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
        """End a motion request: READY, or FAULT with why. Never a homing move (ADR-0037)."""
        if stopped or failure is not None:
            belts = self._stop_belts(self._sayer())
            if belts is not None:
                problems.append(belts)
        if failure is not None:
            return self._fault("; ".join([f"{what} failed: {failure}", *problems]))
        if problems:
            verb = "stopped" if stopped else "ended"
            return self._fault("; ".join([f"{what} {verb}, and the stop was not confirmed",
                                          *problems]))
        if stopped:
            self._end(ConsoleState.READY)
            return Outcome(False, f"{what} was stopped; nothing homes on its own (ADR-0037)")
        self._end(ConsoleState.READY)
        return Outcome(True, f"{what}: {done}")

    def _stop_belts(self, say: Callable[[str], None]) -> str | None:
        """Stop the belts this console started, if it did; say why not, or None."""
        if not self._belts_running:
            return None
        try:
            confirmed = self._set_belts(False, say)
        except Exception as error:  # noqa: BLE001 - reported as the stop's failure
            return f"the belts could not be stopped: {error!r}"
        if not confirmed:
            return "a side's belt did not confirm the stop; it may still be running"
        self._belts_running = False
        return None

    def _await_part(self, prompt: str) -> str:
        """Wait for `confirm_part`: the `read` `confirm_operator` asks the operator with.

        Raises `Interrupted` on a stop, which reaches the request as Ctrl-C at
        the terminal prompt would have.
        """
        with self._lock:
            if self._stop.is_set():
                raise Interrupted("stopped while the part was awaited")
            previous = self._state
            self._state = ConsoleState.AWAITING_PART
            self._step = prompt
            self._confirmed = False
            snapshot = self._snapshot()
        self._on_change(snapshot)
        self._log(prompt)
        with self._lock:
            self._changed.wait_for(lambda: self._confirmed or self._stop.is_set())
            if self._stop.is_set():
                raise Interrupted("stopped while the part was awaited")
            self._confirmed = False
            self._state = previous
            self._step = "the operator confirmed"
            snapshot = self._snapshot()
        self._on_change(snapshot)
        return ""

    def _raise_if_stopped(self) -> None:
        if self._stop.is_set():
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
        return Snapshot(
            state=self._state,
            robot_started=self._started,
            busy=self._busy,
            step=self._step,
            last_error=self._error,
            speed_scale=self._speed,
        )
