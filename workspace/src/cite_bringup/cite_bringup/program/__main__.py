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

"""Run the fixed program: `python3 -m cite_bringup.program --zone cell_b`.

    --cycles N       how many cycles (default 1; 0 runs until Ctrl-C)
    --via twin       through the twin boundary (default), on --target's sides
    --via plant      the plant's own servers only
    --target T       through the twin: `twin` (default; both sides, VALIDATED),
                     `sim` (the plant alone, SIM) or `real` (the real arm alone,
                     REAL) - ADR-0072. Refused with --via plant
    --dry-run        print the steps and exit
    --speed-scale S  every move and track slide at S in (0, 1] of its speed; 1 when not
                     given, except through the twin on a pair with a physical side,
                     where it must be given (`sides.required_speed_scale`)

The steps are the real robot's program as the bring-up plan states it
(`from_plan`, ADR-0067). Before the first cycle (`--first-cycle 1`, the
default) every physical side's arm is initialized, the program's start is
measured on every side, and only where a side is not there are both arms
brought to it and the start measured again (`program.home.bring_to_start`,
ADR-0070).
It does NOT put parts on the table, and it does NOT run the belt: the caller
supplies one part per cycle and starts each side's belt on that side, which is
what `./scripts/program` does.
It refuses to start on an arm that says it holds a part, because the program
opens the gripper before it closes it.

Ctrl-C (or SIGTERM), or any step that does not succeed, cancels the goal in
flight, holds the track where it stands and exits non-zero.

VIA THE PLANT (S-02). `--via plant` speaks to whatever serves the skill names
on this process's own domain, with no twin, no operator gate and, by default,
the program's own speed. It is therefore refused unless this process is on the
PLANT's domain (`plan.require_domain`, the check the plant's own launch makes):
run on the counterpart's domain it would have driven the physical arm
directly. A shell that exported the counterpart's domain passes that check, so
once the context exists the graph is asked too: a simulated side's `/clock`
must be heard there before any goal or mode (`RosCell.simulated_side_refusal`).
Like the twin route, it is also refused where an operator console
serves the pair (one operator surface per pair, ADR-0071).

A PHYSICAL SIDE, through the twin (ADR-0070 item 7). Before each run the twin's
mode is read and must be SIM, where nothing crosses to the physical side; only
then is the operator asked, at this terminal, to place the part and clear the
cell, and only on their answer is VALIDATED asked for. After the run the twin is
put back in SIM, and a run that could not confirm that exits non-zero, so no
caller asks a person into the cell beside an arm the twin may still command.
"""

from __future__ import annotations

import argparse
import os
import sys

from cite_bringup.plan import default_plan_path, load, PlanError, PLANT_SIDE, require_domain
from cite_bringup.program import targets
from cite_bringup.program.cycle import Homing, run_program
from cite_bringup.program.from_plan import program, target
from cite_bringup.program.home import home_steps, initialize, start_pose
from cite_bringup.program.sides import physical_sides, required_speed_scale
from cite_bringup.program.steps import install_interrupt_handlers


def say_now(text: str) -> None:
    print(text, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program", description="Run the cell's fixed program."
    )
    parser.add_argument("--zone", required=True, help="The zone to drive, e.g. cell_b.")
    parser.add_argument("--cycles", type=int, default=1, help="Cycles to run; 0 = forever.")
    parser.add_argument("--via", choices=("twin", "plant"), default="twin")
    parser.add_argument(
        "--target",
        choices=tuple(targets.NAMES.values()),
        default=None,
        help="Through the twin, the sides the signal goes to: sim, real or twin (default).",
    )
    parser.add_argument(
        "--first-cycle", type=int, default=1, help="Number of the first cycle, for the log."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the steps and exit.")
    parser.add_argument(
        "--speed-scale",
        default="",
        help="Run every move and track slide at this fraction (0, 1] of its own speed, on "
        "both sides alike. 1.0 is the program as written; required through the twin "
        "when a side is physical.",
    )
    args = parser.parse_args(argv)
    if args.cycles < 0:
        parser.error("--cycles must be 0 or more")

    if args.via == "plant" and args.target is not None:
        parser.error("--target names sides of the twin; --via plant drives the plant alone")
    # `./scripts/program` drives the twin, as it always has (ADR-0072 decision 5).
    chosen = targets.by_name(args.target or targets.NAMES[targets.TWIN])
    sides = targets.SIDES[chosen]

    plan = load(default_plan_path(args.zone))
    # The one rule, the same `./scripts/program` asks before bring-up (SA-S-02):
    # a physical side the run commands is never commanded at a defaulted scale.
    try:
        scale = required_speed_scale(plan, args.speed_scale, args.via, sides)
    except ValueError as error:
        parser.error(f"--speed-scale: {error}")
    physical = (
        [side for side in physical_sides(plan) if side in sides] if args.via == "twin" else []
    )
    cell = target(plan)
    steps = program(cell)
    # Before the first cycle only: each later invocation by `./scripts/program`
    # numbers its cycle after the first.
    homing = home_steps(cell) if args.first_cycle == 1 else []
    start = start_pose(cell, homing) if homing else None
    if args.dry_run:
        for number, step in enumerate(homing, start=1):
            print(f"home {number}. {step}")
        for number, step in enumerate(steps, start=1):
            print(f"{number:2d}. {step}")
        return 0

    if args.via == "plant":
        # Before any ROS context exists (S-02): the plant's own servers, and
        # never the counterpart's - which may be the physical arm.
        try:
            require_domain(plan, PLANT_SIDE, os.environ)
        except PlanError as error:
            print(f"--via plant refused: {error}", file=sys.stderr, flush=True)
            return 2

    # Imported here so that --dry-run needs no ROS graph at all.
    from cite_bringup.program.cell import RosCell
    import rclpy
    from rclpy.signals import SignalHandlerOptions

    # rclpy's own SIGINT handler shuts the context down, and then nothing could
    # cancel the goal or stop the belt. Python's default raises
    # KeyboardInterrupt instead, which `run` turns into that cleanup — installed
    # explicitly, because a process started with `&` inherits SIGINT ignored.
    install_interrupt_handlers()
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    try:
        ros = RosCell(
            cell.arm,
            args.via,
            track=cell.track,
            speed=scale,
        )
        if args.via == "plant":
            # The environment's domain is only what the shell exported (S-02r):
            # the graph must show a simulated side before anything is asked.
            refusal = ros.simulated_side_refusal()
            if refusal is not None:
                print(f"--via plant refused: {refusal}", file=sys.stderr, flush=True)
                return 2
        riding = f" on {cell.track.asset}" if cell.track is not None else ""
        # The order - SIM read, the operator asked, custody, VALIDATED (homing
        # first before the first cycle), the program, SIM again - is the one
        # sequencer's, shared with `./scripts/home` and the operator console.
        ended = run_program(
            ros,
            steps,
            target=chosen,
            physical=physical,
            scale=scale,
            cycles=args.cycles,
            say=say_now,
            await_operator=input,
            via_twin=args.via == "twin",
            homing=(
                # What the operator does in Studio before running the program.
                Homing(homing, start, lambda: initialize(plan, physical, say_now))
                if homing
                else None
            ),
            first_cycle=args.first_cycle,
            # One operator surface per pair (N-01, R-05): by either route, a
            # pair an operator console serves is refused before anything.
            console=plan.console.state if plan.console is not None else None,
            banner=(
                f"==> {args.zone}: {cell.arm.asset}{riding}, running {cell.program.source} "
                f"via {args.via}"
                + (f" on {targets.label(chosen)}" if args.via == "twin" else "")
                + f" at {scale:g} of its speed"
            ),
        )
        return ended.status
    finally:
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
