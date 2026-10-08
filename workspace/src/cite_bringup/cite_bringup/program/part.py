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

"""Put a work-piece on each simulated side's pick table: `python3 -m cite_bringup.program.part`.

    --zone cell_b             spawn one on each simulated side
    --zone cell_b --replace   take the last cycle's off first, then spawn

The program puts no part on the table itself, so whoever runs it does, once
per cycle: `./scripts/program` between its cycles and the operator console
(ADR-0071) before each of its own. This is the one statement of how, for both.

The box keeps the one name `workpiece`, because the belt's `<carry>` list, the
beams' `<watch>` list and the grasp hold all match that model name exactly
(`cite_bringup.workpiece.workpiece_sdf`); a uniquely named box would ride
through the cell untouched. So the previous cycle's box is removed first.

A PHYSICAL SIDE gets nothing, and it is said (ADR-0070 item 7): a person places
the part there by hand.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile

from cite_bringup.gz import plan_for, run
from cite_bringup.program.sides import is_physical
from cite_bringup.program.steps import StepFailed
from cite_bringup.workpiece import (
    frame,
    part_of,
    spawn,
    SPAWN_DROP_M,
    workpiece_sdf,
    world_name,
)

#: The work-piece's model name, which is also its L0 type id (see above).
WORKPIECE = "workpiece"

#: How long one side's spawn may take, in wall seconds. A hang detector.
SPAWN_CEILING_S = 180.0

#: How long one side's removal may take, in wall seconds. A hang detector.
REMOVE_CEILING_S = 60.0


def place_on_simulated_sides(
    zone: str, remove_first: bool, say: Callable[[str], None]
) -> None:
    """Spawn one work-piece on every simulated side's pick table, or raise StepFailed.

    ``remove_first`` takes the previous one off that side first. Each side is
    reached through `cite_bringup.gz.run`, the one door into its Gazebo
    partition (ADR-0042).
    """
    plan = plan_for(zone)
    world = world_name(plan.world)
    pick = frame(plan, f"{zone}__infeed_table__surface")
    part = part_of(plan, WORKPIECE)
    at = (pick[0], pick[1], pick[2] + part.size_m[2] / 2.0 + SPAWN_DROP_M)
    with NamedTemporaryFile("w", suffix=".sdf", delete=False) as sdf:
        sdf.write(workpiece_sdf(part))
    try:
        for side in plan.sides:
            if is_physical(plan, side.name):
                say(f"  --  {side.name}: physical; no box is spawned or removed there")
                continue
            if remove_first:
                _remove(zone, side.name, world)
            try:
                problem = spawn(
                    zone, side.name, WORKPIECE, at, Path(sdf.name), timeout_s=SPAWN_CEILING_S
                )
            except subprocess.TimeoutExpired:
                problem = f"no answer within {SPAWN_CEILING_S:.0f} s; is that side's world up?"
            if problem is not None:
                raise StepFailed(f"{side.name}: {problem}")
            say(f"  ok  {side.name}: a {WORKPIECE} on the pick table")
    finally:
        Path(sdf.name).unlink(missing_ok=True)


def _remove(zone: str, side: str, world: str) -> None:
    """Take the previous work-piece out of ``side``'s world, or raise StepFailed.

    Queued in the world ahead of the create that follows, so the name is free
    by the time the create is processed; if it is not, the create fails and
    says so.
    """
    try:
        removed = run(
            ["gz", "service", "-s", f"/world/{world}/remove",
             "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
             "--timeout", "5000", "--req", f'name: "{WORKPIECE}" type: MODEL'],
            zone=zone, side=side, timeout=REMOVE_CEILING_S,
        )
    except subprocess.TimeoutExpired:
        raise StepFailed(
            f"{side}: could not remove the previous {WORKPIECE}: no answer within "
            f"{REMOVE_CEILING_S:.0f} s"
        ) from None
    if "data: true" not in removed.stdout:
        raise StepFailed(
            f"{side}: could not remove the previous {WORKPIECE}: "
            f"{removed.stdout.strip()} {removed.stderr.strip()}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.program.part",
        description="Put a work-piece on each simulated side's pick table.",
    )
    parser.add_argument("--zone", required=True)
    parser.add_argument(
        "--replace", action="store_true", help="Remove the previous work-piece first."
    )
    args = parser.parse_args(argv)
    try:
        place_on_simulated_sides(args.zone, args.replace, lambda text: print(text, flush=True))
    except StepFailed as failure:
        print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
