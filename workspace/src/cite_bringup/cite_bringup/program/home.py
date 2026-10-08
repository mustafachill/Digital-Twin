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

The program's own start, measured first and moved to only if a side is not
there, through the twin, on both sides with one signal (ADR-0070,
`bring_to_start`):

1. **Measure**: is every side at the start? Every arm joint within the arm's
   goal tolerance of the program's first pose (its `reset` block, `zero`),
   asked of the twin with `JointsAt`, and every carriage within the track's
   goal tolerance of the program's first track target (0 m), asked with
   `TrackArrived`. A physical side counts only with fresh positions. If every
   side is there, nothing moves.
2. Otherwise **initialize** each physical side's arm: its `InitializeAsset`
   service (`cite_hardware`'s initializer, under the plan's
   `initialize_service`) is called on that side's own domain. It enables the
   track motor and the gripper and, only where the track has not found its
   zero, homes the track. A simulated side has nothing to initialize.
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
    resolve_domain_id,
    resolve_uri,
)
from cite_bringup.program.from_plan import program, Target, target
from cite_bringup.program.steps import (
    execute,
    EXIT_INTERRUPTED,
    Step,
    StepFailed,
)
import yaml

#: How long a side's initializer may take to match this client, in wall
#: seconds. A hang detector: the side is up before anyone asks.
MATCH_CEILING_S = 60.0

#: What the operator is asked before a home on a physical side.
HOME_PROMPT = "Clear the cell: the track may home and both arms will move. Then press Enter. "


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
) -> bool:
    """Measure the start; home only if a side is not there; measure again (ADR-0070).

    Returns whether a homing move was made. Ends, through the twin, in
    VALIDATED asked WITHOUT `SetMode.homing`, so whatever runs next runs under
    the ordinary carriage-agreement refusal. Raises `StepFailed` - and retries
    nothing - when initializing, entering VALIDATED, a home step, or the second
    measurement fails; ``ros`` is a `RosCell`.
    """
    away = ros.away_from_start(start)
    if away is None:
        say(f"every side is at the program's start ({start.pose}): no homing move")
        if via_twin:
            ros.enter_validated()
        return False
    say(f"not at the program's start: {away}")
    initialize_physical()
    if via_twin:
        ros.enter_validated(homing=True)
    run_home(steps, ros, say)
    away = ros.away_from_start(start)
    if away is not None:
        raise StepFailed(f"homed, and still not at the program's start: {away}")
    say(f"every side is at the program's start ({start.pose})")
    if via_twin:
        ros.enter_validated()
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


def initializer_deadline_s(physical) -> float:
    """Return the initializer's own `deadline_s`, from the side's generated parameters."""
    try:
        document = yaml.safe_load(physical.parameters.read_text()) or {}
        return float(document[physical.initializer]["ros__parameters"]["deadline_s"])
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise PlanError(
            f"{physical.parameters} states no deadline_s for {physical.initializer}: {exc!r}"
        ) from exc


def initialize(plan: Plan, sides: list[str], say: Callable[[str], None], environ=os.environ):
    """Call each physical arm's `InitializeAsset` on its side's domain, or raise StepFailed."""
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
            except PlanError as error:
                raise StepFailed(str(error)) from None
            say(f"==> {side}: initializing {manager.asset} ({physical.initialize_service})")
            response = _call_on_domain(
                physical.initialize_service, resolve_domain_id(plan, side, base), ceiling_s
            )
            if not response.success:
                raise StepFailed(f"{side}: {manager.asset} not initialized: {response.detail}")
            say(f"  ok  {side}: {response.detail}")


def _call_on_domain(service: str, domain: int, ceiling_s: float):
    """Call `InitializeAsset` once on ``domain``, in a context of its own, once matched."""
    from cite_interfaces.srv import InitializeAsset
    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    # One context per side: a side is a ROS domain, as in `program.belt`.
    context = rclpy.Context()
    rclpy.init(context=context, domain_id=domain)
    try:
        node = rclpy.create_node("initialize_client", context=context)
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        client = node.create_client(InitializeAsset, service)
        deadline = time.monotonic() + MATCH_CEILING_S
        while not client.service_is_ready():
            if time.monotonic() > deadline:
                raise StepFailed(
                    f"nothing serves {service} on domain {domain} after "
                    f"{MATCH_CEILING_S:.0f} s; is that side up?"
                )
            executor.spin_once(timeout_sec=0.1)
        future = client.call_async(InitializeAsset.Request())
        deadline = time.monotonic() + ceiling_s
        while not future.done():
            if time.monotonic() > deadline:
                raise StepFailed(f"{service} did not answer within {ceiling_s:g} s")
            executor.spin_once(timeout_sec=0.1)
        return future.result()
    finally:
        context.try_shutdown()


def say_now(text: str) -> None:
    print(text, flush=True)


def main(argv: list[str] | None = None) -> int:
    from cite_bringup.program.operator import confirm_operator
    from cite_bringup.program.sides import physical_sides, required_speed_scale
    from cite_bringup.program.steps import install_interrupt_handlers

    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program.home",
        description="Initialize the physical arm and bring both arms to the program's start.",
    )
    parser.add_argument("--zone", required=True)
    parser.add_argument("--speed-scale", default="")
    args = parser.parse_args(argv)
    plan = load(default_plan_path(args.zone))
    try:
        scale = required_speed_scale(plan, args.speed_scale, "twin")
    except ValueError as error:
        parser.error(f"--speed-scale: {error}")
    physical = physical_sides(plan)
    cell = target(plan)
    steps = home_steps(cell)
    start = start_pose(cell, steps)

    from cite_bringup.program.cell import RosCell
    import rclpy
    from rclpy.signals import SignalHandlerOptions

    install_interrupt_handlers()
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    status = 1
    try:
        ros = RosCell(cell.arm, "twin", track=cell.track, speed=scale)
        try:
            if physical:
                confirm_operator(
                    ros.twin_mode(),
                    physical,
                    scale,
                    say_now,
                    input,
                    lambda: ros.carriage_refusal(homing=True),
                    prompt=HOME_PROMPT,
                )
            bring_to_start(
                steps, start, ros, lambda: initialize(plan, physical, say_now), say_now
            )
            say_now("done: both arms are at the program's start")
            status = 0
        except StepFailed as failure:
            say_now(f"FAILED: {failure}")
        except KeyboardInterrupt:
            say_now("interrupted")
            status = EXIT_INTERRUPTED
        if physical and not ros.leave_validated():
            return status or 1
        return status
    finally:
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
