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
    --via twin       through the twin boundary, both sides (default)
    --via plant      the plant's own servers only
    --dry-run        print the steps and exit
    --speed-scale S  every move and track slide at S in (0, 1] of its speed; 1 when not
                     given, except through the twin on a pair with a physical side,
                     where it must be given (`sides.required_speed_scale`)

The steps are the real robot's program as the bring-up plan states it
(`from_plan`, ADR-0067). It does NOT put parts on the table, and it does NOT run
the belt: the caller supplies one part per cycle and starts each side's belt on
that side, which is what `./scripts/program` does. It refuses to start on an arm
that says it holds a part, because the program opens the gripper before it
closes it.

Ctrl-C (or SIGTERM), or any step that does not succeed, cancels the goal in
flight, holds the track where it stands and exits non-zero.

A PHYSICAL SIDE, through the twin (ADR-0070 item 7). Before each run the twin's
mode is read and must be SIM, where nothing crosses to the physical side; only
then is the operator asked, at this terminal, to place the part and clear the
cell, and only on their answer is VALIDATED asked for. After the run the twin is
put back in SIM, and a run that could not confirm that exits non-zero, so no
caller asks a person into the cell beside an arm the twin may still command.
"""

from __future__ import annotations

import argparse
import sys

from cite_bringup.plan import default_plan_path, load
from cite_bringup.program.from_plan import program, target
from cite_bringup.program.operator import confirm_operator
from cite_bringup.program.sides import physical_sides, required_speed_scale
from cite_bringup.program.steps import (
    EXIT_INTERRUPTED,
    install_interrupt_handlers,
    run,
    StepFailed,
)


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

    plan = load(default_plan_path(args.zone))
    # The one rule, the same `./scripts/program` asks before bring-up (SA-S-02):
    # a physical side is never commanded at a defaulted scale.
    try:
        scale = required_speed_scale(plan, args.speed_scale, args.via)
    except ValueError as error:
        parser.error(f"--speed-scale: {error}")
    physical = physical_sides(plan) if args.via == "twin" else []
    cell = target(plan)
    steps = program(cell)
    if args.dry_run:
        for number, step in enumerate(steps, start=1):
            print(f"{number:2d}. {step}")
        return 0

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
        ros = RosCell(cell.arm, args.via, track=cell.track, speed=scale)
        try:
            if physical:
                # Read, not assumed: the operator is asked in only while the
                # twin forwards nothing to the physical side (SA-S-05).
                confirm_operator(ros.twin_mode(), physical, scale, say_now, input)
            ros.refuse_if_holding()
            if args.via == "twin":
                ros.enter_validated()
        except StepFailed as failure:
            print(f"FAILED before the first step: {failure}", flush=True)
            return 1
        except KeyboardInterrupt:
            print("interrupted before the first step", flush=True)
            return EXIT_INTERRUPTED
        riding = f" on {cell.track.asset}" if cell.track is not None else ""
        say_now(
            f"==> {args.zone}: {cell.arm.asset}{riding}, running {cell.program.source} "
            f"via {args.via} at {scale:g} of its speed"
        )
        status = run(steps, ros, args.cycles, say_now, first_cycle=args.first_cycle)
        if physical and not ros.leave_validated():
            # Operator safety at the next prompt: a person places the part by
            # hand, so the twin must forward nothing to the physical side then;
            # unconfirmed, the run fails and no caller asks anyone in (SA-S-05).
            return status or 1
        return status
    finally:
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
