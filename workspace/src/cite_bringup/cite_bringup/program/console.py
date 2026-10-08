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

    /cite/<zone>/console/start_robot    cite_interfaces/srv/StartRobot
    /cite/<zone>/console/home           cite_interfaces/action/HomeRobot
    /cite/<zone>/console/run_program    cite_interfaces/action/RunProgram
    /cite/<zone>/console/confirm_part   cite_interfaces/srv/ConfirmPart
    /cite/<zone>/console/stop           cite_interfaces/srv/StopCell
    /cite/<zone>/console/state          cite_interfaces/msg/ConsoleState (LATCHED)

composed by `console_name` from the constants the definitions carry. Every
decision is `console_machine.ConsoleMachine`'s; this module is the ROS wrapper
around it and the process around that. A panel (the Gazebo plugin of ADR-0071
decision 5, or anything else) only sends requests and shows the state.

The pair supervisor starts it once the twin boundary has announced
(`pair.console_spec`), and it starts NO motion: it waits for an operator.

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
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import signal
import sys
import threading

from cite_bringup.plan import default_plan_path, load, Plan, PlanError
from cite_bringup.program.belt import set_belts
from cite_bringup.program.cell import ROOT, RosCell
from cite_bringup.program.console_machine import ConsoleMachine, Outcome, Snapshot
from cite_bringup.program.from_plan import program, target
from cite_bringup.program.home import home_steps, initialize, start_pose
from cite_bringup.program.part import place_on_simulated_sides
from cite_bringup.program.sides import physical_sides
from cite_bringup.readiness import console_announcement
from cite_interfaces.action import HomeRobot, RunProgram
from cite_interfaces.msg import ConsoleState, TwinMode
from cite_interfaces.qos import LATCHED
from cite_interfaces.srv import ConfirmPart, StartRobot, StopCell
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
#: wall seconds: a cancel and a return to SIM, each bounded by the cell's own
#: `CANCEL_CEILING_S`, and the belts' stop. A ceiling on a failure.
SHUTDOWN_CEILING_S = 120.0

#: How soon the announcement asks the executor to call it back, in seconds. Not
#: a schedule: it fires once, on the executor's first turn.
_ANNOUNCE_PERIOD_S = 0.01

#: The name of the node each request's cell creates.
_CELL_NODE = "cell_console_program"


def console_name(zone: str, leaf: str) -> str:
    """`(cell_b, state)` -> `/cite/cell_b/console/state`: every console name, once.

    The root is the one `program.cell` reads off the twin's own contract, and
    the scope and the leaves are the definitions' constants (ConsoleState.msg).
    """
    return f"{ROOT}/{zone}/{ConsoleState.SCOPE}/{leaf}"


@dataclass(frozen=True)
class ConsoleNames:
    """Every name the console serves, for one zone."""

    state: str
    start_robot: str
    confirm_part: str
    stop: str
    home: str
    run_program: str


def console_names(zone: str) -> ConsoleNames:
    """Return every name the console serves for ``zone``, from `console_name`."""
    return ConsoleNames(
        state=console_name(zone, ConsoleState.NAME),
        start_robot=console_name(zone, StartRobot.Request.NAME),
        confirm_part=console_name(zone, ConfirmPart.Request.NAME),
        stop=console_name(zone, StopCell.Request.NAME),
        home=console_name(zone, HomeRobot.Goal.NAME),
        run_program=console_name(zone, RunProgram.Goal.NAME),
    )


class CellConsole(LifecycleNode):
    """The operator console's ROS face (ADR-0071); `ConsoleMachine` decides."""

    def __init__(self, plan: Plan) -> None:
        # Simulated time, as the cell it drives (`RosCell`), so the state's
        # stamp and the cell's waits read one clock.
        super().__init__(
            "cell_console", parameter_overrides=[Parameter("use_sim_time", value=True)]
        )
        self._plan = plan
        self._names = console_names(plan.zone)
        self._machine: ConsoleMachine | None = None
        #: The long requests' handlers, and the action servers' every callback:
        #: reentrant, so a cancel is served while its goal executes.
        self._work = ReentrantCallbackGroup()
        #: Everything that must answer at once.
        self._quick = ReentrantCallbackGroup()
        self._publish_lock = threading.Lock()
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
            cell = target(plan)
            homing = home_steps(cell)
            start = start_pose(cell, homing)
            steps = program(cell)
            physical = physical_sides(plan)
        except (ValueError, PlanError) as error:
            self.get_logger().error(f"cannot configure: {error}")
            return TransitionCallbackReturn.FAILURE
        self._machine = ConsoleMachine(
            physical=physical,
            home_steps=homing,
            start=start,
            steps=steps,
            make_cell=self._make_cell,
            initialize_physical=lambda say, interrupted: initialize(
                plan, physical, say, interrupted=interrupted
            ),
            place_parts=lambda remove_first, say: place_on_simulated_sides(
                plan.zone, remove_first, say
            ),
            set_belts=lambda running, say: set_belts(plan, not running, say),
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
                ConfirmPart, names.confirm_part, self._on_confirm_part,
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
            **scale,
        )

    # ------------------------------------------------------------- handlers

    def _on_start_robot(self, request, response):
        outcome = self._machine.start_robot()
        response.success, response.detail = outcome.success, outcome.detail
        return response

    def _on_confirm_part(self, request, response):
        outcome = self._machine.confirm_part()
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
        """Stop the request in flight: a cancel is the same software stop as StopCell."""
        if not self._machine.snapshot().busy:
            return CancelResponse.REJECT
        outcome = self._machine.stop()
        self.get_logger().warning(f"cancel: {outcome.detail}")
        return CancelResponse.ACCEPT

    def _execute_home(self, goal_handle):
        outcome = self._machine.home(
            goal_handle.request.speed_scale,
            feedback=lambda text: goal_handle.publish_feedback(HomeRobot.Feedback(step=text)),
        )
        self._settle(goal_handle, outcome)
        return HomeRobot.Result(success=outcome.success, detail=outcome.detail)

    def _execute_run(self, goal_handle):
        def feedback(cycle: int, number: int, count: int, text: str) -> None:
            goal_handle.publish_feedback(
                RunProgram.Feedback(cycle=cycle, step_index=number, step_count=count, step=text)
            )

        outcome = self._machine.run_program(
            goal_handle.request.speed_scale, goal_handle.request.cycles, feedback
        )
        self._settle(goal_handle, outcome)
        return RunProgram.Result(
            success=outcome.success,
            detail=outcome.detail,
            cycles_completed=outcome.cycles_completed,
        )

    @staticmethod
    def _settle(goal_handle, outcome: Outcome) -> None:
        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
        elif outcome.success:
            goal_handle.succeed()
        else:
            goal_handle.abort()

    # ---------------------------------------------------------------- state

    def _on_twin_mode(self, message: TwinMode) -> None:
        with self._publish_lock:
            self._twin_mode = message.mode
        if self._machine is not None:
            self._publish(self._machine.snapshot())

    def _publish(self, snapshot: Snapshot) -> None:
        with self._publish_lock:
            self._last = snapshot
            if self._publisher is None:
                return
            message = ConsoleState(
                state=snapshot.state,
                robot_started=snapshot.robot_started,
                busy=snapshot.busy,
                step=snapshot.step,
                last_error=snapshot.last_error,
                twin_mode=self._twin_mode,
                physical_sides=self._machine.physical if self._machine else [],
                speed_scale=float(snapshot.speed_scale),
            )
            message.stamp = self.get_clock().now().to_msg()
            self._publisher.publish(message)


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
        if machine is not None and not machine.shutdown(SHUTDOWN_CEILING_S):
            print(
                "cell_console: what was in progress, or a belt, did not confirm its stop "
                f"within {SHUTDOWN_CEILING_S:.0f} s",
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
