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

"""The operator console server: `python3 -m cite_bringup.program.console --zone cell_b`.

ADR-0071 option C. A managed node, `cell_console`, on the PLANT's domain, that
serves the operator's buttons as typed contracts and publishes what it is doing:

    console.start_robot       cite_interfaces/srv/StartRobot
    console.home              cite_interfaces/action/HomeRobot
    console.run_program       cite_interfaces/action/RunProgram
    console.confirm_operator  cite_interfaces/srv/ConfirmOperator
    console.stop              cite_interfaces/srv/StopCell
    console.state             cite_interfaces/msg/ConsoleState (LATCHED)

under the names the zone's bring-up plan states (`/cite/<zone>/console/...`,
formed once by the generator; `plan.ConsoleNames`). Every decision is
`console_machine.ConsoleMachine`'s; this module is the ROS wrapper around it
and the process around that. A panel (the Gazebo plugin of ADR-0071 decision
5, or anything else) only sends requests and shows the state.

The pair supervisor starts it only when asked to (`./scripts/sim --pair
--console`, `pair.console_spec`), once the twin boundary has announced, and it
starts NO motion: it waits for an operator. It is a client of more than one
domain: its requests go through the boundary on the plant's, while Start robot
and Home call each physical side's `InitializeAsset` (and that side's track
stop) on THAT side's domain, and Start program commands each simulated side's
belt and spawns its work-piece on that side (`program.home`, `program.belt`,
`program.part`).

**Lifecycle.** It offers nothing before `activate`: every endpoint above is
created there and destroyed on `deactivate`, which is refused while a request
runs. Started by the supervisor it configures and activates ITSELF, in `main`,
and only then announces on standard output (`readiness.console_announcement`),
from inside the executor serving those endpoints - the boundary's pattern.

**Threads.** The long requests - Start robot, Home, Start program - block their
handler until they end, in a reentrant callback group of their own, on a
`MultiThreadedExecutor` with threads to spare: the machine admits one such
request at a time, so Stop, the go-ahead, a cancel and the twin's mode always
find a free thread. The cell each request drives (`RosCell`) is a separate node
spun by that request's own thread, never by this executor, so nothing here
waits on an event this executor has to deliver.

**Signals, and why `cite_runtime` is not used.** `cite_runtime` absorbs SIGINT
and is, by its own admission rule, for a process that commands no actuator.
This one does. SIGINT and SIGTERM here ask the machine to stop the request in
flight - the goal cancelled, the track held, the belts it started stopped -
wait for that within `SHUTDOWN_CEILING_S`, and only then shut the context down.
A lifecycle `shutdown` does the same before it withdraws anything.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
import threading

from cite_bringup.gz import KILL_WAIT_S
from cite_bringup.pair import STOP_GRACE_S
from cite_bringup.plan import (
    COUNTERPART_SIDE,
    default_plan_path,
    load,
    Plan,
    PlanError,
    PLANT_SIDE,
)
from cite_bringup.program.belt import ACK_CEILING_S, MATCH_CEILING_S, set_belts
from cite_bringup.program.cell import RosCell
from cite_bringup.program.console_machine import ConsoleMachine, Outcome, Snapshot
from cite_bringup.program.from_plan import program, target
from cite_bringup.program.home import home_steps, initialize, initializer_stop, start_pose
from cite_bringup.program.part import place_on_simulated_sides
from cite_bringup.program.sides import (
    minimum_speed_scale,
    physical_sides,
    required_speed_scale,
    simulated_sides,
)
from cite_bringup.readiness import console_announcement
from cite_interfaces.action import HomeRobot, RunProgram
from cite_interfaces.msg import ConsoleState, TwinMode
from cite_interfaces.qos import LATCHED
from cite_interfaces.srv import ConfirmOperator, StartRobot, StopCell
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.signals import SignalHandlerOptions

#: The executor's threads. One long request at a time holds one; the rest serve
#: Stop, the go-ahead, a cancel, a refused request and the twin's mode.
EXECUTOR_THREADS = 4

#: How long the end of the process waits for the request in flight to stop, in
#: wall seconds. Normally a cancel, the cancelled goal's end and a return to SIM,
#: each answered at once. It is a bound, not a hope (R2-02): from the start of
#: the shutdown every wait of the request's cell and initializer is cut at
#: `SHUTDOWN_CEILING_S - STOP_TAIL_S` (`ConsoleMachine.stop_deadline`).
SHUTDOWN_CEILING_S = 30.0

#: What the request may still spend after that cut, in wall seconds: the
#: initializer's second track stop (checked against each physical side's own
#: `call_deadline_s` when the console configures), a cell's last spin slice,
#: and closing its node.
STOP_TAIL_S = 5.0

#: What the request may spend after the shutdown began in waits that no deadline
#: cuts, in wall seconds, each sequential with the cut ones: a belt setpoint's
#: acknowledgement on each of the two sides (`belt.ACK_CEILING_S`), and a
#: killed Gazebo command's output and reaping (`gz.KILL_WAIT_S`, twice).
_UNCUT_S = 2 * ACK_CEILING_S + 2 * KILL_WAIT_S
if not _UNCUT_S <= SHUTDOWN_CEILING_S - STOP_TAIL_S:
    raise ImportError(
        f"the request's uncut waits ({_UNCUT_S:g} s) must fit before the shutdown's cut "
        f"({SHUTDOWN_CEILING_S - STOP_TAIL_S:g} s)"
    )

#: How long the end of the process waits for each simulated side's belt
#: subscriber before it stops that belt, in wall seconds; each side then waits
#: up to `belt.ACK_CEILING_S` for the stop to be acknowledged.
SHUTDOWN_BELT_MATCH_S = 10.0

#: The longest the end of the process can take before it shuts its context down:
#: the wait for the request (`SHUTDOWN_CEILING_S`, which the request's stop
#: cannot outlast: see `STOP_TAIL_S` and `_UNCUT_S`), then ONE belt stop per side,
#: made by the shutdown alone once the request has ended (the request leaves its
#: belts to it while the process closes, so the two never queue on one lock).
#: It is STRICTLY BELOW the pair supervisor's `STOP_GRACE_S`, the time the
#: supervisor gives a participant after its SIGINT before escalating, so the
#: supervisor never kills a console still stopping what it started. Two sides
#: at most (plant and counterpart).
SHUTDOWN_WORST_S = SHUTDOWN_CEILING_S + len((PLANT_SIDE, COUNTERPART_SIDE)) * (
    SHUTDOWN_BELT_MATCH_S + ACK_CEILING_S
)
if not SHUTDOWN_WORST_S < STOP_GRACE_S:
    raise ImportError(
        f"the console's shutdown ({SHUTDOWN_WORST_S:g} s) must end before the pair "
        f"supervisor's STOP_GRACE_S ({STOP_GRACE_S:g} s)"
    )

#: How soon the announcement asks the executor to call it back, in seconds. Not
#: a schedule: it fires once, on the executor's first turn.
_ANNOUNCE_PERIOD_S = 0.01

#: The name of the node each request's cell creates.
_CELL_NODE = "cell_console_program"


class CellConsole(LifecycleNode):
    """The operator console's ROS face (ADR-0071); `ConsoleMachine` decides."""

    def __init__(self, plan: Plan) -> None:
        # Simulated time, as the cell it drives (`RosCell`), so the state's
        # stamp and the cell's waits read one clock.
        super().__init__(
            "cell_console", parameter_overrides=[Parameter("use_sim_time", value=True)]
        )
        self._plan = plan
        self._names = plan.console
        self._machine: ConsoleMachine | None = None
        #: The long requests' handlers, and the action servers' every callback:
        #: reentrant, so a cancel is served while its goal executes.
        self._work = ReentrantCallbackGroup()
        #: Everything that must answer at once.
        self._quick = ReentrantCallbackGroup()
        self._publish_lock = threading.Lock()
        #: Guards `_twin_mode` alone, so the machine may read it under its own lock.
        self._mode_lock = threading.Lock()
        self._twin_mode = ConsoleState.TWIN_MODE_UNKNOWN
        self._last: Snapshot | None = None
        self._publisher = None
        self._endpoints: list = []
        self._announcement = None

    @property
    def machine(self) -> ConsoleMachine | None:
        return self._machine

    # ------------------------------------------------------------ lifecycle

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        """Read the program, its start and the physical sides off the plan; serve nothing."""
        plan = self._plan
        try:
            if self._names is None:
                raise PlanError(
                    f"the plan for {plan.zone} states no `console:` names; a console runs "
                    "only on a paired zone"
                )
            cell = target(plan)
            homing = home_steps(cell)
            start = start_pose(cell, homing)
            steps = program(cell)
            physical = physical_sides(plan)
            # The floor `required_speed_scale` applies, shown to the panel.
            minimum = (minimum_speed_scale(plan) if physical else None) or 0.0
            _require_track_stops_within_the_tail(plan, physical)
        except (ValueError, PlanError, OSError, KeyError) as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        self._machine = ConsoleMachine(
            physical=physical,
            simulated=simulated_sides(plan),
            home_steps=homing,
            start=start,
            steps=steps,
            make_cell=self._make_cell,
            initialize_physical=lambda say, interrupted: initialize(
                plan, physical, say, interrupted=interrupted, stop_deadline=self._stop_deadline
            ),
            place_parts=lambda may_hold, say, interrupted: place_on_simulated_sides(
                plan.zone, may_hold, say, interrupted
            ),
            set_belts=lambda running, say, interrupted, ceiling: set_belts(
                plan,
                not running,
                say,
                interrupted=interrupted,
                match_ceiling_s=MATCH_CEILING_S if ceiling is None else ceiling,
            ),
            heard_twin_mode=self._heard_twin_mode,
            # The command line's own rule, floor included (SA-S-07), on the
            # value exactly as the goal carries it.
            check_scale=lambda scale: required_speed_scale(plan, repr(float(scale))),
            minimum_speed_scale=minimum,
            on_change=self._publish,
            log=lambda text: self.get_logger().info(text),
        )
        self.get_logger().info(
            f"configured for {plan.zone}: {len(steps)} step(s) per cycle, physical side(s): "
            f"{', '.join(physical) or 'none'}"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        """Create every endpoint, publish the state, and announce once served."""
        names = self._names
        self._publisher = self.create_publisher(ConsoleState, names.state, LATCHED)
        self._endpoints = [
            self.create_subscription(
                TwinMode, TwinMode.TOPIC, self._on_twin_mode, LATCHED,
                callback_group=self._quick,
            ),
            self.create_service(
                StartRobot, names.start_robot, self._on_start_robot,
                callback_group=self._work,
            ),
            self.create_service(
                ConfirmOperator, names.confirm_operator, self._on_confirm_operator,
                callback_group=self._quick,
            ),
            self.create_service(
                StopCell, names.stop, self._on_stop, callback_group=self._quick
            ),
            ActionServer(
                self,
                HomeRobot,
                names.home,
                execute_callback=self._execute_home,
                goal_callback=lambda goal: self._accept(goal.speed_scale, None),
                cancel_callback=self._on_cancel,
                callback_group=self._work,
            ),
            ActionServer(
                self,
                RunProgram,
                names.run_program,
                execute_callback=self._execute_run,
                goal_callback=lambda goal: self._accept(goal.speed_scale, goal.cycles),
                cancel_callback=self._on_cancel,
                callback_group=self._work,
            ),
        ]
        self._publish(self._machine.snapshot())
        # On the steady clock: this node reads simulated time, and a timer in a
        # clock that has not started (no `/clock` yet) would never announce.
        self._announcement = self.create_timer(
            _ANNOUNCE_PERIOD_S,
            self._announce,
            callback_group=self._quick,
            clock=Clock(clock_type=ClockType.STEADY_TIME),
        )
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        """Withdraw every endpoint; refused while a request runs - Stop it first."""
        if self._machine is not None and self._machine.snapshot().busy:
            self.get_logger().error("cannot deactivate while a request runs; Stop it first")
            return TransitionCallbackReturn.FAILURE
        self._withdraw()
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._machine = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        """Stop what is in progress and wait for it, as the process's end does; then withdraw.

        The machine refuses every request from the moment this begins, so
        nothing new starts while the endpoints are still there.
        """
        if self._machine is not None and not self._machine.shutdown(
            SHUTDOWN_CEILING_S, SHUTDOWN_BELT_MATCH_S, STOP_TAIL_S
        ):
            self.get_logger().error(
                "shutdown: what was in progress, or a belt, did not confirm its stop"
            )
        self._withdraw()
        return TransitionCallbackReturn.SUCCESS

    def _withdraw(self) -> None:
        for endpoint in self._endpoints:
            if isinstance(endpoint, ActionServer):
                endpoint.destroy()
            elif hasattr(endpoint, "srv_name"):
                self.destroy_service(endpoint)
            else:
                self.destroy_subscription(endpoint)
        self._endpoints = []
        if self._announcement is not None:
            self.destroy_timer(self._announcement)
            self._announcement = None
        if self._publisher is not None:
            self.destroy_publisher(self._publisher)
            self._publisher = None

    def _announce(self) -> None:
        """Say once, on standard output, that the console is being served (ADR-0071)."""
        self._announcement.cancel()
        print(console_announcement(self._plan.zone), flush=True)

    # ------------------------------------------------------------- the cell

    def _make_cell(self, speed: float | None, interrupted) -> RosCell:
        """Return a cell driving the twin at ``speed``, stopped by ``interrupted``.

        ``speed`` None is Start robot's reading cell: it reads custody and is
        closed before any step, so the scale it is built with commands nothing.
        Every cell that is handed a step is built with the goal's own scale.
        """
        cell = target(self._plan)
        scale = {} if speed is None else {"speed": speed}
        return RosCell(
            cell.arm,
            "twin",
            track=cell.track,
            interrupted=interrupted,
            node_name=_CELL_NODE,
            stop_deadline=self._stop_deadline,
            **scale,
        )

    def _stop_deadline(self) -> float | None:
        """Return the machine's shutdown deadline for the request in flight (R2-02), or None."""
        machine = self._machine
        return None if machine is None else machine.stop_deadline()

    # ------------------------------------------------------------- handlers

    def _on_start_robot(self, request, response):
        outcome = self._machine.start_robot()
        response.success, response.detail = outcome.success, outcome.detail
        return response

    def _on_confirm_operator(self, request, response):
        outcome = self._machine.confirm_operator()
        response.success, response.detail = outcome.success, outcome.detail
        return response

    def _on_stop(self, request, response):
        outcome = self._machine.stop()
        self.get_logger().warning(f"Stop: {outcome.detail}")
        response.success, response.detail = outcome.success, outcome.detail
        return response

    def _accept(self, scale: float, cycles: int | None) -> GoalResponse:
        refusal = self._machine.motion_refusal(scale, cycles)
        if refusal is not None:
            self.get_logger().warning(f"goal rejected: {refusal}")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel(self, goal_handle) -> CancelResponse:
        """Stop the request THIS goal owns: the same software stop as StopCell.

        A cancel of any other goal - one not yet started, or one that lost the
        race for the request - is accepted and stops nothing else: that goal
        reads its own cancel when it starts (`_owner`), and the request in
        progress, owned by another goal, runs on (ADR-0071).
        """
        outcome = self._machine.stop(owner=_owner(goal_handle))
        self.get_logger().warning(f"cancel: {outcome.detail}")
        return CancelResponse.ACCEPT

    def _execute_home(self, goal_handle):
        outcome = self._machine.home(
            goal_handle.request.speed_scale,
            feedback=lambda text: goal_handle.publish_feedback(HomeRobot.Feedback(step=text)),
            owner=_owner(goal_handle),
            cancelled=lambda: goal_handle.is_cancel_requested,
        )
        self._settle(goal_handle, outcome)
        return HomeRobot.Result(success=outcome.success, detail=outcome.detail)

    def _execute_run(self, goal_handle):
        def feedback(cycle: int, number: int, count: int, text: str) -> None:
            goal_handle.publish_feedback(
                RunProgram.Feedback(cycle=cycle, step_index=number, step_count=count, step=text)
            )

        outcome = self._machine.run_program(
            goal_handle.request.speed_scale,
            goal_handle.request.cycles,
            feedback,
            owner=_owner(goal_handle),
            cancelled=lambda: goal_handle.is_cancel_requested,
        )
        self._settle(goal_handle, outcome)
        return RunProgram.Result(
            success=outcome.success,
            detail=outcome.detail,
            cycles_completed=outcome.cycles_completed,
        )

    @staticmethod
    def _settle(goal_handle, outcome: Outcome) -> None:
        """End the goal as the request ended: a request that completed SUCCEEDED.

        A cancel that came after the request's last point that can be
        interrupted changed nothing, and the goal says so rather than
        reporting a stop that did not happen (ADR-0071).
        """
        if outcome.success:
            goal_handle.succeed()
        elif goal_handle.is_cancel_requested:
            goal_handle.canceled()
        else:
            goal_handle.abort()

    # ---------------------------------------------------------------- state

    def _on_twin_mode(self, message: TwinMode) -> None:
        with self._mode_lock:
            self._twin_mode = message.mode
        machine = self._machine
        if machine is not None:
            self._publish(machine.snapshot())

    def _heard_twin_mode(self) -> int | None:
        """Return the twin's mode as last heard, or None before any."""
        with self._mode_lock:
            mode = self._twin_mode
        return None if mode == ConsoleState.TWIN_MODE_UNKNOWN else mode

    def _publish(self, snapshot: Snapshot) -> None:
        """Publish ``snapshot``, unless a later one was already published.

        Snapshots are taken under the machine's lock and numbered there, but
        handed here from several threads; without the order kept, an older one
        published last would be the latched state a late panel receives.
        """
        with self._mode_lock:
            twin_mode = self._twin_mode
        with self._publish_lock:
            if self._last is not None and snapshot.sequence < self._last.sequence:
                return
            self._last = snapshot
            if self._publisher is None:
                return
            message = ConsoleState(
                state=snapshot.state,
                robot_started=snapshot.robot_started,
                busy=snapshot.busy,
                at_start=snapshot.at_start,
                step=snapshot.step,
                prompt=snapshot.prompt,
                last_error=snapshot.last_error,
                twin_mode=twin_mode,
                physical_sides=self._machine.physical if self._machine else [],
                speed_scale=float(snapshot.speed_scale),
                minimum_speed_scale=float(snapshot.minimum_speed_scale),
            )
            message.stamp = self.get_clock().now().to_msg()
            self._publisher.publish(message)


def _require_track_stops_within_the_tail(plan: Plan, physical: list[str]) -> None:
    """Raise `PlanError` if a physical initializer's track stop could outlast `STOP_TAIL_S`.

    After the shutdown's cut an interrupted initialization still sends its
    second track stop and waits for its answer (`home._call_on_domain`); that
    wait is the side's own (`home.initializer_stop`), and it must fit in the
    tail the shutdown's bound allows for it (R2-02).
    """
    for side in physical:
        for manager in plan.controller_managers:
            target_side = manager.physical_on(side)
            if target_side is None or target_side.initialize_service is None:
                continue
            _, ceiling_s = initializer_stop(target_side)
            if ceiling_s > STOP_TAIL_S / 2.0:
                raise PlanError(
                    f"{side}: {manager.asset}'s track stop may wait {ceiling_s:g} s, more than "
                    f"the console's shutdown allows after its cut ({STOP_TAIL_S / 2.0:g} s)"
                )


def _owner(goal_handle) -> bytes:
    """Return an action goal's id, as the owner of the request it starts."""
    return bytes(goal_handle.goal_id.uuid)


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program.console",
        description="Serve the operator console for one zone (ADR-0071).",
    )
    parser.add_argument("--zone", help="The zone, e.g. cell_b.")
    parser.add_argument("--plan", help="The bring-up plan, instead of the zone's default.")
    # `ros2 run` and `launch_ros` append `--ros-args ...`, which is not ours.
    known, _ = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if not known.zone and not known.plan:
        parser.error("--zone is required, and has no default: a console serves ONE zone")
    return known


def main(argv: list[str] | None = None) -> int:
    """Serve the console until SIGINT or SIGTERM, then stop what it started."""
    arguments = _arguments(argv)
    try:
        path = Path(arguments.plan) if arguments.plan else default_plan_path(arguments.zone)
        plan = load(path)
    except PlanError as error:
        print(f"cell_console: {error}", file=sys.stderr)
        return 2
    if arguments.zone and plan.zone != arguments.zone:
        print(
            f"cell_console: --zone {arguments.zone!r} and --plan {str(path)!r}, which "
            f"declares zone {plan.zone!r}; pass one of them.",
            file=sys.stderr,
        )
        return 2

    ended = threading.Event()

    def end(number: int, frame: object) -> None:  # noqa: ARG001 - signal shape
        ended.set()

    # Ours, not rclpy's: its handler would shut the context down under a goal
    # in flight, and nothing could then cancel it.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, end)
    node = CellConsole(plan)
    executor = MultiThreadedExecutor(num_threads=EXECUTOR_THREADS)
    executor.add_node(node)
    status = 0
    try:
        if node.trigger_configure() != TransitionCallbackReturn.SUCCESS:
            return 2
        if node.trigger_activate() != TransitionCallbackReturn.SUCCESS:
            return 2
        spinner = threading.Thread(target=executor.spin, name="console_executor", daemon=True)
        spinner.start()
        while not ended.wait(0.5):
            if not spinner.is_alive():
                print("cell_console: the executor stopped", file=sys.stderr)
                status = 1
                break
        machine = node.machine
        if machine is not None and not machine.shutdown(
            SHUTDOWN_CEILING_S, SHUTDOWN_BELT_MATCH_S, STOP_TAIL_S
        ):
            print(
                "cell_console: what was in progress, or a belt, did not confirm its stop "
                f"within {SHUTDOWN_WORST_S:.0f} s",
                file=sys.stderr,
            )
            status = 1
        node.trigger_deactivate()
        return status
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
