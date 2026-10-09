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

"""Bring both arms to the program's start: `python3 -m cite_bringup.program.home`.

    --zone cell_b --speed-scale 0.1

The program's own start, measured and moved to only if a side is not there,
through the twin, on both sides with one signal (ADR-0070, `bring_to_start`):

1. **Initialize** each physical side's arm, every time: its `InitializeAsset`
   service (`cite_hardware`'s initializer, under the plan's
   `initialize_service`) is called on that side's own domain, as
   `program.belt` calls a side's belt (the ADR-0044 clause 3 carve-out). It
   enables the track motor and the gripper, homes the track only where it has
   not found its zero, and brings the carriage to the program's first track
   target only where it is not there; on an initialized arm at the start
   nothing moves. A simulated side has nothing to initialize. Interrupted or
   unanswered once sent, the call is followed by that side's
   `set_linear_motor_stop` (`_call_on_domain`).
2. **Measure**: is every side at the start? Every arm joint within the arm's
   goal tolerance of the program's first pose (its `reset` block, `zero`),
   asked of the twin with `JointsAt`, and every carriage within the track's
   goal tolerance of the program's first track target (0 m), asked with
   `TrackArrived`. A physical side counts only with fresh positions. If every
   side is there, nothing moves.
3. **Home**: the program's first arm move and first track move, at the
   program's speeds scaled by `--speed-scale`, sent once through the twin
   boundary in VALIDATED asked with `SetMode.homing` - the one allowance that
   lets the carriages stand apart, since this move is what brings them
   together - and so to both sides.
4. **Measure again**. Not at the start, or any step failing, stops: nothing is
   retried and nothing is forced. Otherwise the program may start, and it asks
   VALIDATED again WITHOUT the allowance, so its cycle never runs under it.

`python3 -m cite_bringup.program` runs both before its first cycle, and
`./scripts/home` runs this module against a pair that is already up. On a
physical side the operator is asked first, at this terminal, once the twin is
read in SIM - homing the track and both moves move the physical cell.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
import sys
import time

from cite_bringup.plan import (
    ControllerManager,
    default_plan_path,
    domain_base,
    load,
    Plan,
    PlanError,
    PLANT_SIDE,
    resolve_domain_id,
    resolve_uri,
)
from cite_bringup.program import targets
from cite_bringup.program.from_plan import program, Target, target
from cite_bringup.program.steps import (
    _interrupts_ignored,
    execute,
    Interrupted,
    Step,
    StepFailed,
)
import yaml

#: How long a side's initializer may take to match this client, in wall
#: seconds. A hang detector: the side is up before anyone asks.
MATCH_CEILING_S = 60.0

#: What the operator is asked before a home on a physical side.
HOME_PROMPT = (
    "Clear the cell: the track may home and move to its start, and both arms will move. "
    "Then press Enter. "
)


def home_steps(cell: Target) -> list[Step]:
    """Return the program's own start: its first arm move, then its first track move.

    Read off the program rather than restated: the real program begins with
    `reset` (every joint at zero) and slides the carriage to 0 m, and these
    are those two steps, at the program's own speeds.
    """
    steps = program(cell)
    move = next((step for step in steps if step.kind == "move"), None)
    if move is None:
        raise ValueError(f"the program {cell.program.source} moves the arm nowhere")
    slide = next((step for step in steps if step.kind == "track"), None)
    return [move] if slide is None else [move, slide]


@dataclass(frozen=True)
class StartPose:
    """The program's start, as `away_from_start` measures it (ADR-0070)."""

    #: The pose the program's first arm move goes to, and its joint values.
    pose: str
    joints: tuple[str, ...]
    positions: tuple[float, ...]
    #: The arm's declared goal tolerance (`arm_goal_tolerance_rad`).
    tolerance_rad: float
    #: The program's first track target and the track's goal tolerance, or
    #: `None` both for an arm that rides no track.
    track_m: float | None
    track_tolerance_m: float | None

    def away_on_one_side(
        self, positions: Mapping[str, float], track_m: float | None
    ) -> str | None:
        """Say where ONE side, read directly, is not at the start, or None."""
        away = [
            f"{joint} stands at {positions[joint]:.4f}, not within "
            f"{self.tolerance_rad:g} of {target:.4f}"
            for joint, target in zip(self.joints, self.positions)
            if abs(positions[joint] - target) > self.tolerance_rad
        ]
        if self.track_m is not None and (
            track_m is None or abs(track_m - self.track_m) > self.track_tolerance_m
        ):
            stands = "is not heard" if track_m is None else f"stands at {track_m * 1000:.1f} mm"
            away.append(
                f"the track {stands}, not within {self.track_tolerance_m * 1000:g} mm "
                f"of {self.track_m * 1000:.1f} mm"
            )
        return "; ".join(away) if away else None


def arm_joints(arm: ControllerManager) -> tuple[str, ...]:
    """Return the arm's joints, in order, from its trajectory controller's generated configuration.

    The order the planning group, and so every named pose, states them in: the
    controller and the group are generated from one model.
    """
    controller = arm.trajectory_action.rsplit("/", 1)[0]
    document = yaml.safe_load(resolve_uri(arm.parameters).read_text())
    return tuple(document[controller]["ros__parameters"]["joints"])


def start_pose(cell: Target, steps: list[Step]) -> StartPose:
    """Return the start ``steps`` (`home_steps`) bring the arm and its track to."""
    move = steps[0]
    arm = cell.arm
    positions = arm.moveit.home_rad if move.pose == "home" else arm.moveit.poses_rad[move.pose]
    joints = arm_joints(arm)
    if len(joints) != len(positions):
        raise PlanError(
            f"the pose {move.pose} states {len(positions)} value(s) for {len(joints)} joint(s)"
        )
    slide = next((step for step in steps if step.kind == "track"), None)
    return StartPose(
        pose=move.pose,
        joints=joints,
        positions=tuple(float(value) for value in positions),
        tolerance_rad=float(arm.arm["arm_goal_tolerance_rad"]),
        track_m=None if slide is None else slide.position_m,
        track_tolerance_m=None if slide is None else cell.track.goal_tolerance_m,
    )


def bring_to_start(
    steps: list[Step],
    start: StartPose,
    ros,
    initialize_physical: Callable[[], None],
    say: Callable[[str], None],
    via_twin: bool = True,
    target: int = targets.TWIN,
) -> bool:
    """Initialize; measure the target's start; home only if a side is not there; measure again.

    ``initialize_physical`` runs first, every time (ADR-0070): it is
    idempotent, and only an initialized physical arm is measured; for a target
    with no physical side the caller hands a no-op (R-03). ``target`` names the
    sides measured and moved (ADR-0072, `targets.SIDES`). Returns whether a
    homing move was made. Ends, through the twin, in the target's mode asked
    WITHOUT `SetMode.homing`, so whatever runs next runs under the ordinary
    carriage-agreement refusal. The homing allowance is asked only where the
    target's mode is VALIDATED (R-11). Raises `StepFailed` - and retries
    nothing - when initializing, entering the mode, a home step, or the second
    measurement fails; ``ros`` is a `RosCell`.
    """
    sides = targets.SIDES[target]
    initialize_physical()
    away = ros.away_from_start(start, sides)
    if away is None:
        say(f"every side of {targets.label(target)} is at the program's start ({start.pose}): "
            "no homing move")
        if via_twin:
            ros.enter_target(target)
        return False
    say(f"not at the program's start: {away}")
    if (
        via_twin
        and PLANT_SIDE not in sides
        and start.track_m is not None
        and ros.target_carriage_unknown()
    ):
        # R-10: before any mode is asked and before anything moves. A track
        # step of a target without the plant starts from where the twin
        # confirmed that carriage stands, and the twin confirmed it nowhere.
        raise StepFailed(
            f"{targets.ARMS[target]} initialized, and its carriage is still not at the "
            f"program's start ({start.track_m * 1000:.0f} mm): {away}. This program cannot "
            "read where that carriage stands - the twin answers verdicts, not positions "
            "(ADR-0050 decision 1b) - so it cannot command a track move from it. Run Start "
            "robot again, whose initializer brings the carriage to the start, or Home with "
            "the twin as the target. Nothing was moved"
        )
    if via_twin:
        ros.enter_target(target, homing=targets.homing_allowance(target))
    run_home(steps, ros, say)
    away = ros.away_from_start(start, sides)
    if away is not None:
        raise StepFailed(f"homed, and still not at the program's start: {away}")
    say(f"every side of {targets.label(target)} is at the program's start ({start.pose})")
    if via_twin and targets.homing_allowance(target):
        ros.enter_target(target)
    return True


def run_home(steps: list[Step], cell, say: Callable[[str], None]) -> None:
    """Run the home steps; on any failure or Ctrl-C cancel the goal in flight and re-raise."""
    try:
        for number, step in enumerate(steps, start=1):
            say(f"[home, step {number}/{len(steps)}] {step}")
            execute(step, cell)
    except BaseException:
        try:
            cell.cancel()
        except Exception as error:  # noqa: BLE001 - reported; the failure is re-raised
            say(f"could not cancel the active goal: {error}")
        raise


def initializer_parameter(physical, name: str):
    """Return one of the initializer's parameters, from the side's generated parameters."""
    try:
        document = yaml.safe_load(physical.parameters.read_text()) or {}
        return document[physical.initializer]["ros__parameters"][name]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise PlanError(
            f"{physical.parameters} states no {name} for {physical.initializer}: {exc!r}"
        ) from exc


def initializer_deadline_s(physical) -> float:
    """Return the initializer's own `deadline_s`, from the side's generated parameters."""
    try:
        return float(initializer_parameter(physical, "deadline_s"))
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{physical.parameters}: deadline_s is no number: {exc!r}") from exc


def initializer_stop(physical) -> tuple[str, float]:
    """Return the vendor's track stop the initializer names, and how long to wait for it.

    Twice the initializer's own `call_deadline_s`, as the initializer bounds
    its own stop.
    """
    service = initializer_parameter(physical, "linear_motor_stop_service")
    try:
        ceiling_s = 2.0 * float(initializer_parameter(physical, "call_deadline_s"))
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{physical.parameters}: call_deadline_s is no number: {exc!r}") from exc
    if not isinstance(service, str) or not service:
        raise PlanError(f"{physical.parameters}: linear_motor_stop_service is no name")
    return service, ceiling_s


def initialize(
    plan: Plan,
    sides: list[str],
    say: Callable[[str], None],
    environ=os.environ,
    interrupted: Callable[[], bool] | None = None,
    stop_deadline: Callable[[], float | None] | None = None,
):
    """Call each physical arm's `InitializeAsset` on its side's domain, or raise StepFailed.

    ``interrupted`` is the operator console's stop (ADR-0071), asked while an
    answer is awaited; True there is handled as Ctrl-C is: the track is stopped
    and `steps.Interrupted` raised. ``stop_deadline`` is the console's shutdown
    deadline (monotonic, or None before its shutdown), past which the answer
    is no longer awaited after an interrupt (R2-02). What an interrupt comes
    to is said through ``say``, so the console shows it (R2-06).
    """
    if not sides:
        return
    try:
        base = domain_base(environ)
    except PlanError as error:
        raise StepFailed(str(error)) from None
    for side in sides:
        for manager in plan.controller_managers:
            physical = manager.physical_on(side)
            if physical is None or physical.initialize_service is None:
                say(f"  --  {side}: {manager.asset} has nothing to initialize")
                continue
            try:
                ceiling_s = 2.0 * initializer_deadline_s(physical)
                stop = initializer_stop(physical)
            except PlanError as error:
                raise StepFailed(str(error)) from None
            say(f"==> {side}: initializing {manager.asset} ({physical.initialize_service})")
            response = _call_on_domain(
                physical.initialize_service,
                resolve_domain_id(plan, side, base),
                ceiling_s,
                stop,
                interrupted=interrupted,
                say=say,
                stop_deadline=stop_deadline,
            )
            if not response.success:
                raise StepFailed(f"{side}: {manager.asset} not initialized: {response.detail}")
            say(f"  ok  {side}: {response.detail}")


def _call_on_domain(
    service: str,
    domain: int,
    ceiling_s: float,
    stop: tuple[str, float],
    interrupted: Callable[[], bool] | None = None,
    say: Callable[[str], None] | None = None,
    stop_deadline: Callable[[], float | None] | None = None,
):
    """Call `InitializeAsset` once on ``domain``, in a context of its own, once matched.

    The initialization may move the carriage, so once the request is sent, an
    interrupt (Ctrl-C, SIGTERM) or no answer within ``ceiling_s`` is followed
    by the vendor's track stop on that domain - ``stop`` is its name and how
    long to wait for its answer (`initializer_stop`) - before the failure is
    re-raised (S-01). ``interrupted`` returning True while the answer is
    awaited is such an interrupt (ADR-0071).

    **An interrupt is not the initializer's end** (ADR-0071, S-02). The
    initializer goes on with its sequence after the client stops listening,
    and a later step of it may move the carriage again after the first track
    stop. So after an interrupt the answer is still awaited, within the same
    ``ceiling_s`` the call was given, and the track is stopped a second time
    once it comes (or the ceiling passes); only then is the interrupt
    re-raised, so nothing reports the stop done while the initializer may still
    move. Neither stop nor the wait is itself interrupted; the wait ends early
    only at ``stop_deadline`` - the console's shutdown deadline (R2-02) - and
    the second stop is still sent then. Each outcome is said through ``say``
    (standard output when None).
    """
    say = say_now if say is None else say
    from cite_interfaces.srv import InitializeAsset
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from xarm_msgs.srv import Call

    # One context per side: a side is a ROS domain, as in `program.belt`.
    context = rclpy.Context()
    rclpy.init(context=context, domain_id=domain)
    try:
        node = rclpy.create_node("initialize_client", context=context)
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        client = node.create_client(InitializeAsset, service)
        # Created before the request, so it has matched by the time it is needed.
        stopper = node.create_client(Call, stop[0])
        deadline = time.monotonic() + MATCH_CEILING_S
        while not client.service_is_ready():
            if time.monotonic() > deadline:
                raise StepFailed(
                    f"nothing serves {service} on domain {domain} after "
                    f"{MATCH_CEILING_S:.0f} s; is that side up?"
                )
            if interrupted is not None and interrupted():
                # Nothing sent yet, so there is nothing to stop.
                raise Interrupted(f"stopped from the operator console before {service}")
            executor.spin_once(timeout_sec=0.1)
        future = client.call_async(InitializeAsset.Request())
        deadline = time.monotonic() + ceiling_s
        try:
            while not future.done():
                if time.monotonic() > deadline:
                    raise StepFailed(f"{service} did not answer within {ceiling_s:g} s")
                if interrupted is not None and interrupted():
                    raise Interrupted(f"stopped from the operator console during {service}")
                executor.spin_once(timeout_sec=0.1)
        except KeyboardInterrupt:
            # A second Ctrl-C (the terminal's and the script's) must not
            # abandon the stop half-way, as in `steps.run`.
            with _interrupts_ignored():
                _stop_track(executor, stopper, stop[1], say)
                limit = None if stop_deadline is None else stop_deadline()
                if _await_answer(
                    executor, future, deadline if limit is None else min(deadline, limit)
                ):
                    say(f"{service} answered after the interrupt")
                elif limit is not None and limit < deadline:
                    say(
                        f"{service} did not answer before the console's shutdown deadline; "
                        "the initializer may still be moving the carriage"
                    )
                else:
                    say(f"{service} did not answer within {ceiling_s:g} s of its call")
                _stop_track(executor, stopper, stop[1], say)
            raise
        except BaseException:
            with _interrupts_ignored():
                _stop_track(executor, stopper, stop[1], say)
            raise
        return future.result()
    finally:
        context.try_shutdown()


def _await_answer(executor, future, deadline: float) -> bool:
    """Spin until ``future`` is done or ``deadline`` (monotonic) passes; return whether done."""
    while not future.done():
        if time.monotonic() > deadline:
            return False
        executor.spin_once(timeout_sec=0.1)
    return True


def _stop_track(
    executor, stopper, ceiling_s: float, say: Callable[[str], None] | None = None
) -> None:
    """Send the vendor's track stop once matched and wait for its answer, within ``ceiling_s``.

    Reported through ``say`` (standard output when None), never raised: the
    failure that called for it is what is raised.
    """
    from xarm_msgs.srv import Call

    say = say_now if say is None else say
    deadline = time.monotonic() + ceiling_s
    while not stopper.service_is_ready():
        if time.monotonic() > deadline:
            say(f"could not stop the track: nothing serves {stopper.srv_name}")
            return
        executor.spin_once(timeout_sec=0.05)
    answer = stopper.call_async(Call.Request())
    while not answer.done():
        if time.monotonic() > deadline:
            say(f"{stopper.srv_name} did not answer within {ceiling_s:g} s")
            return
        executor.spin_once(timeout_sec=0.05)
    result = answer.result()
    if result is None or result.ret != 0:
        say(f"the vendor refused {stopper.srv_name}: {result}")
    else:
        say(f"interrupted during an initialization: {stopper.srv_name} sent")


def say_now(text: str) -> None:
    print(text, flush=True)


def main(argv: list[str] | None = None) -> int:
    # Here, not at the top: `cycle` builds on this module.
    from cite_bringup.program import cycle
    from cite_bringup.program.sides import physical_sides, required_speed_scale
    from cite_bringup.program.steps import install_interrupt_handlers

    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program.home",
        description="Initialize the physical arm and bring both arms to the program's start.",
    )
    parser.add_argument("--zone", required=True)
    parser.add_argument("--speed-scale", default="")
    parser.add_argument(
        "--target",
        choices=tuple(targets.NAMES.values()),
        default=targets.NAMES[targets.TWIN],
        help="The sides homed: sim, real or twin (default, as ./scripts/home always has).",
    )
    args = parser.parse_args(argv)
    chosen = targets.by_name(args.target)
    sides = targets.SIDES[chosen]
    plan = load(default_plan_path(args.zone))
    try:
        scale = required_speed_scale(plan, args.speed_scale, "twin", sides)
    except ValueError as error:
        parser.error(f"--speed-scale: {error}")
    physical = [side for side in physical_sides(plan) if side in sides]
    cell = target(plan)
    steps = home_steps(cell)
    start = start_pose(cell, steps)

    from cite_bringup.program.cell import RosCell
    import rclpy
    from rclpy.signals import SignalHandlerOptions

    install_interrupt_handlers()
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    try:
        ros = RosCell(cell.arm, "twin", track=cell.track, speed=scale)
        ended = cycle.home(
            ros,
            steps,
            start,
            target=chosen,
            physical=physical,
            scale=scale,
            say=say_now,
            await_operator=input,
            # A target with no physical side initializes nothing (R-03).
            initialize_physical=lambda: initialize(plan, physical, say_now),
            prompt=HOME_PROMPT,
            # One operator surface per pair (N-01): `./scripts/home` is refused
            # where an operator console serves the pair.
            console=plan.console.state if plan.console is not None else None,
        )
        return ended.status
    finally:
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
