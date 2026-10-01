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

"""Put a work-piece into each side of a running pair and watch it reach the end.

WHAT THIS IS FOR, AND WHAT IT IS NOT. `./scripts/demo` exists so a person can
WATCH the thing the scenarios assert. `./scripts/scenario continuous_line`
already carries work-pieces from the pick area to accumulation and CHECKS that
they arrived; it runs headless and drives one side. This drives both sides of a
pair with the windows open, and **it asserts nothing and gates nothing**. The
scenario is the instrument; this is the demonstration. No figure taken from here
means anything, and in particular the two sides' final positions printed at the
end are NOT a fidelity measurement — see `docs/adr/0065-*.md` for what measuring
that actually takes.

IT DRIVES NOTHING. The line is already running: `line:=true` puts the L4
coordinator up on each side, and a work-piece appearing at the pick station is
what starts a cycle. This module spawns and then watches. That is deliberate —
a demonstration that commanded the arms itself would be showing its own
sequencing rather than the cell's.

THIS IS THE PARKED EVENT-DRIVEN LINE (ADR-0066). The cell's default is now the
fixed program, `cite_bringup.program`, which `./scripts/program` runs through
the twin boundary; this module and `./scripts/demo` are kept, unchanged in
behaviour, for the line the program parked.

EVERY GAZEBO-TRANSPORT CALL GOES THROUGH `cite_bringup.gz`. That module is the
one door (ADR-0042): a process that speaks Gazebo transport without the
partition the generated plan names discovers a world that is not there, and
`gz model --list` against no world exits 0, so the failure is silent. A guard
under `tests/scenarios/guards/` enforces this for `tests/`; nothing enforces it
for this package, which is exactly why it is written down here.

WHICH ZONE, AND WHY IT IS NOT A DEFAULT. A pair is what this demonstrates, so
the zone is the one whose L0 model declares `twin: {sides: pair}`. Reading it
out of the model rather than defaulting it means there is no second place
stating which cell is paired (P1), and a facility that pairs two zones is asked
rather than guessed at.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
import time
from xml.etree import ElementTree

from cite_bringup.gz import ModelPoses, plan_for, run
from cite_bringup.plan import default_plan_path, Plan
from cite_bringup.workpiece import SIDE_M, workpiece_sdf

import yaml

#: How far above the pick surface the prop is released when it is spawned. Small
#: enough that it settles rather than bounces, and non-zero so it is not spawned
#: interpenetrating the table.
SPAWN_DROP_M = 0.005

#: How close to the outfeed frame counts as having got there, as a fraction of
#: the box's own width. The belt carries the prop until its BODY passes the end
#: and the pose reported is its CENTRE, so a centre one half-width short of the
#: outfeed frame is a box whose leading face is level with it. Derived from the
#: width rather than stated in metres, so it cannot drift from the part.
ARRIVAL_MARGIN_WIDTHS = 0.5


@dataclass(frozen=True)
class Arrival:
    """One prop's journey, as this module observed it. Not a measurement."""

    side: str
    name: str
    reached: bool
    position: tuple[float, float, float] | None
    seconds: float


def paired_zones(plans: Path) -> list[str]:
    """Every zone in the generated tree whose plan declares more than one side."""
    zones = []
    for path in sorted(plans.glob("*_plan.yaml")):
        zone = path.name[: -len("_plan.yaml")]
        if len(plan_for(zone).sides) > 1:
            zones.append(zone)
    return zones


def world_name(world: Path) -> str:
    """Return the Gazebo world's NAME, read from the world the plan names.

    Read rather than assumed to equal the zone. They agree today, and that is a
    property of the generator rather than a rule: a zone whose world were named
    anything else would leave this module subscribed to
    `/world/<wrong>/dynamic_pose/info`, where no snapshot ever arrives, and an
    unpartitioned or misaddressed Gazebo query does not fail — it waits. The
    scenario reads it the same way from the same file, which is what keeps this
    from being a second statement of a generated name (P1).
    """
    element = ElementTree.parse(world).getroot().find("world")
    if element is None or not element.get("name"):
        raise ValueError(f"{world} declares no named <world>")
    return str(element.get("name"))


def frame(plan: Plan, name: str) -> tuple[float, float, float]:
    """Where one generated static frame stands, read from the plan's own file.

    The generated frames document is what the static transform publisher itself
    is given, so reading it is not a second statement of the geometry — it is the
    same statement, read in the same place (P1).
    """
    document = yaml.safe_load(plan.static_frames.read_text())
    for transform in document["static_transforms"]:
        if transform["child"] == name:
            x, y, z = transform["xyz_m"]
            return (float(x), float(y), float(z))
    raise KeyError(f"{plan.zone} declares no frame named {name!r}")


def spawn(zone: str, side: str, name: str, at: tuple[float, float, float],
          sdf: Path, timeout_s: float) -> str | None:
    """Put one prop into one side's world. Returns None on success, else why not.

    Returns rather than raises: a demonstration that cannot spawn should say so
    and go on to tear the cell down, not traceback over a running pair.
    """
    result = run(
        ["ros2", "run", "ros_gz_sim", "create", "-file", str(sdf), "-name", name,
         "-x", f"{at[0]}", "-y", f"{at[1]}", "-z", f"{at[2]}"],
        zone=zone, side=side, timeout=timeout_s,
    )
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or "no output").strip().splitlines()[-1]


def watch(zone: str, world: str, sides: tuple[str, ...], name: str,
          outfeed_x_m: float, margin_m: float, ceiling_s: float,
          report) -> list[Arrival]:
    """Follow the prop on every side until it reaches the outfeed, or time runs out.

    THE CEILING BOUNDS A FAILURE AND SEQUENCES NOTHING (P4). The loop ends when
    every side's prop has arrived; the ceiling exists only so that a cell which
    has stopped does not hold a person's terminal for ever. Nothing downstream
    waits for it.

    IT IS NOT THE THING THAT NOTICES A STOPPED LINE, AND MUST NOT BECOME IT.
    When a station escalates, `line_orchestrator` latches the fault and exits 1,
    `simulation.launch.py` treats that as fatal for its side, and the pair
    supervisor ends the pair — so the run is over long before this ceiling, and
    what should report it is whoever can see the supervisor exit. `scripts/demo`
    does, and ends this process rather than letting it poll a dead partition for
    the rest of the ceiling. **This module deliberately does not subscribe to
    `LineState` itself**: the two sides are on two ROS domains, and ADR-0044
    clause 3 makes L5 the only component permitted endpoints in both.
    """
    poses = {side: ModelPoses(zone=zone, world=world, side=side) for side in sides}
    arrived: dict[str, Arrival] = {}
    last_said: dict[str, float] = {}
    started = time.monotonic()
    try:
        while len(arrived) < len(sides) and time.monotonic() - started < ceiling_s:
            for side in sides:
                if side in arrived:
                    continue
                at = poses[side].position(name)
                if at is None:
                    continue
                if abs(at[0] - last_said.get(side, -1e9)) > 0.05:
                    last_said[side] = at[0]
                    report(side, at)
                if at[0] >= outfeed_x_m - margin_m:
                    arrived[side] = Arrival(
                        side, name, True, at, time.monotonic() - started)
                    report(side, at, arrived=True)
            time.sleep(0.2)
        for side in sides:
            if side not in arrived:
                arrived[side] = Arrival(
                    side, name, False, poses[side].position(name),
                    time.monotonic() - started)
    finally:
        for poll in poses.values():
            poll.close()
    return [arrived[side] for side in sides]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m cite_bringup.demo",
        description="Spawn a work-piece on each side of a running pair and watch it.",
    )
    parser.add_argument("--zone", help="Which zone to drive. Default: the paired one.")
    parser.add_argument("--ceiling-s", type=float, default=900.0,
                        help="How long to wait for an arrival before giving up.")
    parser.add_argument("--name", default="workpiece",
                        help="The model name the generated world's belts carry.")
    # `./scripts/demo` has to name the zone when it starts the pair, and asking
    # for it here is what keeps ONE answer to "which zone is paired" (P1). A
    # shell that worked it out for itself would be the second place.
    parser.add_argument("--print-zone", action="store_true",
                        help="Print the zone this would drive, and exit.")
    args = parser.parse_args(argv)

    plans = default_plan_path("cell_a").parent
    if args.zone:
        zone = args.zone
    else:
        candidates = paired_zones(plans)
        if len(candidates) != 1:
            print(f"error: {len(candidates)} zones declare `twin: {{sides: pair}}` "
                  f"({', '.join(candidates) or 'none'}); name one with --zone.",
                  file=sys.stderr)
            return 2
        zone = candidates[0]

    if args.print_zone:
        print(zone)
        return 0

    plan = plan_for(zone)
    sides = tuple(side.name for side in plan.sides)
    pick = frame(plan, f"{zone}__infeed_table__surface")
    outfeed = frame(plan, f"{zone}__transfer_belt__outfeed")
    # The box's own edge length, from the one module that states it, rather than
    # the plan's work-piece INTERVAL. Those are two different quantities: the
    # interval is what `cite_skills::gripper_is_holding` judges a stall against
    # (ADR-0052), and the demonstration needs the size of the thing it is about
    # to spawn. They agree on today's model, which is a coincidence and not a
    # reason to read one off the other.
    width = SIDE_M
    release = (pick[0], pick[1], pick[2] + width / 2.0 + SPAWN_DROP_M)

    print(f"==> zone {zone}, sides {' and '.join(sides)}")
    print(f"    the box is {width * 1000:.0f} mm, released at the pick table "
          f"and carried to x={outfeed[0]:.2f} m")

    sdf_file = NamedTemporaryFile("w", suffix=".sdf", delete=False)
    sdf_file.write(workpiece_sdf(args.name))
    sdf_file.close()
    sdf = Path(sdf_file.name)
    try:
        for side in sides:
            problem = spawn(zone, side, args.name, release, sdf, timeout_s=180.0)
            if problem is not None:
                print(f"error: {side} would not take the box: {problem}", file=sys.stderr)
                return 1
            print(f"  ok  {side}: box on the pick table")

        def report(side: str, at: tuple[float, float, float], arrived: bool = False) -> None:
            mark = "ARRIVED" if arrived else "       "
            print(f"    {mark} {side:<12} x={at[0]:+.3f}  y={at[1]:+.3f}  z={at[2]:+.3f}")

        arrivals = watch(zone, world_name(plan.world), sides, args.name,
                         outfeed[0], width * ARRIVAL_MARGIN_WIDTHS,
                         args.ceiling_s, report)
    finally:
        sdf.unlink(missing_ok=True)

    print()
    print("=" * 70)
    for arrival in arrivals:
        where = ("nowhere — the box is not in that world" if arrival.position is None
                 else f"({arrival.position[0]:+.4f}, {arrival.position[1]:+.4f}, "
                      f"{arrival.position[2]:+.4f})")
        verdict = "reached the end of the belt" if arrival.reached else "DID NOT ARRIVE"
        print(f"  {arrival.side:<12} {verdict:<28} {where}  after {arrival.seconds:.0f} s")
    # NO GAP BETWEEN THE SIDES IS PRINTED, AND THAT IS DELIBERATE. This loop
    # stops polling each box the moment it is first seen past the line, so the
    # two positions above were taken at two different instants while both boxes
    # were still riding a moving belt. Their difference is poll timing, and a
    # run that printed it in millimetres would be handing the reader a number
    # that looks like a divergence measurement and is not one. The measurement
    # of how far the two sides actually diverge is ADR-0065's, taken at matched
    # simulated instants over nine runs; this run neither reproduces it nor
    # bears on it.
    print("  This run shows the cell working. It measures nothing:")
    print("  the two positions above were sampled at different instants on a")
    print("  moving belt. For how far the sides diverge, see ADR-0065.")
    print("=" * 70)
    return 0 if all(a.reached for a in arrivals) else 1


if __name__ == "__main__":
    raise SystemExit(main())
