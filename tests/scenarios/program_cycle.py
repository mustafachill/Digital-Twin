"""Scenario: the real robot's program picks a work-piece, slides it along the track, belts it.

ADR-0067's claim, checked on one side: `python3 -m cite_bringup.program --via
plant` runs the real xArm 5's own program, as the bring-up plan states it — it
grips the part at track 0, lifts it, slides the arm 650 mm along the linear
track and places the part on the belt's infeed. The belt is not part of the
program (the real one has no belt block), so this scenario starts it itself once
the program is done, and checks that it carries the part on. Every assertion is
on the OUTCOME, measured from the simulator; nothing the program reports is
believed on its own:

  * lifted       the part rose off the table,
  * carried      it moved along the track's axis while it was up,
  * placed       it rests on the belt at the infeed frame,
  * belted       and the belt then carries it towards the outfeed.

Plant only, one cycle. Driving both sides through the twin boundary is what
`./scripts/program` demonstrates; a scenario includes one launch in one process
and cannot hold two sides (CLAUDE.md §2).

Every coordinate is resolved from TF at run time, from the frames L0 generates,
exactly as `pick_and_place` does.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

import launch_testing
import launch_testing.markers
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from cite_bringup import workpiece
from cite_bringup.gz import run as gz_run
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.node import Node

# Loaded by path under `launch_test`, so the sibling helper needs this directory
# on the path first; see the same block in `pick_and_place.py`.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _cell import (  # noqa: E402  (insert first)
    acting_station,
    carried_models,
    cell,
    zone,
)

#: The cell this scenario drives, from the one statement in `_cell.py`. The
#: program needs taught poses, so a zone whose arm declares none is refused by
#: the program itself, with a message naming what is missing.
ZONE = zone()

#: Height above the pick surface the work-piece is released from.
SPAWN_DROP_M = 0.005

#: Wall-clock ceilings that bound a failure and sequence nothing. The cycle is
#: the real program's: eleven moves at a ninth of the joint speed limit, two
#: 650 mm track moves at 0.1 m/s and six one-second dwells, which is longer than
#: `pick_and_place`'s cycle; see `pick_and_place.CYCLE_CEILING_S` for the basis.
BRING_UP_CEILING_S = 300.0
SETTLE_CEILING_S = 60.0
CYCLE_CEILING_S = 900.0

#: How still the part must be to count as settled, and how often it is sampled.
SETTLE_TOLERANCE_M = 1e-4
SAMPLE_PERIOD_S = 2.0

#: How far the part must rise to count as picked, as in `pick_and_place`.
LIFTED_M = 0.05

#: How far the part must travel ALONG THE TRACK while it is lifted to count as
#: carried with it. The program slides the arm 650 mm with the part in the jaws;
#: half of that cannot be produced by the arm's own joints at the pick pose.
CARRIED_M = 0.30

#: How close to the belt's infeed frame the placed part must rest, horizontally
#: and in height. Horizontal: the release is 4 mm above the belt, so the part
#: lands where the pads held it; `pick_and_place.PLACE_TOLERANCE_M`'s basis.
#: Height: the same two-sided bound `pick_and_place` uses — too high is still
#: held, too low fell off the belt.
PLACE_TOLERANCE_M = 0.05
HEIGHT_TOLERANCE_M = 0.05

#: How far the belt must carry the part past where it was placed to count as
#: belted, and the wall-clock ceiling for it. The belt is 1.1 m infeed to
#: outfeed at 0.15 m/s, so this is a few seconds of the cell's time.
BELTED_M = 0.30
BELT_CEILING_S = 300.0

#: Recorded in a failure report as a condition of the run, never as a promise
#: of reproducibility; see `pick_and_place.SEED_VARIABLE`.
SEED_VARIABLE = "CITE_PHYSICS_SEED"


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> LaunchDescription:
    simulation = (
        Path(get_package_share_directory("cite_bringup")) / "launch" / "simulation.launch.py"
    )
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(simulation)),
                launch_arguments={"headless": "true", "zone": ZONE}.items(),
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestProgramCycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.node = Node("scenario_program_cycle")
        cls.seed = os.environ.get(SEED_VARIABLE, "unset")
        plan, topology = cell(ZONE)
        station = acting_station(topology)
        cls.pick_frame = station["pick_frame"]
        managers = {m.asset: m for m in plan.controller_managers}
        arm = managers[station["actor"]]
        cls.skills = arm.skills
        assert arm.track is not None, f"{arm.asset} in {ZONE} rides no track"
        assert len(plan.conveyors) == 1, f"{ZONE} does not have exactly one belt"
        cls.conveyor = plan.conveyors[0]
        cls.infeed_frame = f"{ZONE}__{cls.conveyor.asset}__infeed"
        cls.outfeed_frame = f"{ZONE}__{cls.conveyor.asset}__outfeed"
        names = carried_models(Path(plan.world))
        assert len(names) == 1, f"{ZONE}'s world carries {sorted(names)}, not one part"
        cls.workpiece = next(iter(names))
        # The part's size, from the plan that says what is spawned (ADR-0067),
        # rather than a literal of this file's.
        cls.part = workpiece.part_of(plan, cls.workpiece)
        cls.half_height = cls.part.size_m[2] / 2.0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, ceiling_s: float, what: str):
        """Spin until `predicate` answers something other than None, or fail."""
        started = time.monotonic()
        spins = 0
        result = predicate()
        while result is None and time.monotonic() - started < ceiling_s:
            rclpy.spin_once(self.node, timeout_sec=0.5)
            spins += 1
            result = predicate()
        self.assertIsNotNone(result, f"timed out after {ceiling_s:.0f}s waiting for {what}")
        self._emit_timing(what, ceiling_s, time.monotonic() - started, spins)
        return result

    def _emit_timing(self, what: str, ceiling_s: float, elapsed_s: float, spins: int) -> None:
        """Print one timing record in the format every scenario shares.

        The keys and their meaning are `pick_and_place._emit_timing`'s, and
        `tests/scenarios/guards/test_timing_records.py` holds all scenarios to
        one format.
        """
        print(
            "CITE_TIMING "
            + json.dumps(
                {
                    "scenario": Path(__file__).stem,
                    "test": self._testMethodName,
                    "what": what,
                    "ceiling_s": float(ceiling_s),
                    "elapsed_s": round(elapsed_s, 3),
                    "spins": int(spins),
                    "monotonic_s": round(time.monotonic(), 3),
                }
            ),
            flush=True,
        )

    def _workpiece_xyz(self) -> tuple[float, float, float] | None:
        """Ask the simulator where the part is; see `pick_and_place._workpiece_xyz`."""
        result = gz_run(["gz", "model", "-m", self.workpiece, "-p"], zone=ZONE, timeout=30)
        number = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
        triples = re.findall(rf"\[\s*({number})\s+({number})\s+({number})\s*\]", result.stdout)
        if not triples:
            return None
        return (float(triples[0][0]), float(triples[0][1]), float(triples[0][2]))

    def _resolve(self, buffer, frame: str) -> tuple[float, float, float]:
        transform = self._spin_until(
            lambda: (
                buffer.lookup_transform("cite_world", frame, rclpy.time.Time())
                if buffer.can_transform("cite_world", frame, rclpy.time.Time())
                else None
            ),
            BRING_UP_CEILING_S,
            f"a transform from cite_world to {frame}",
        )
        t = transform.transform.translation
        return (t.x, t.y, t.z)

    def test_the_program_picks_slides_places_and_the_belt_carries_it(self) -> None:
        import tf2_ros
        from cite_interfaces.action import MoveTo
        from cite_interfaces.qos import COMMAND
        from rclpy.action import ActionClient
        from std_msgs.msg import Float64

        client = ActionClient(self.node, MoveTo, self.skills.move_to)
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=1.0) or None,
            BRING_UP_CEILING_S,
            "the skill server, and therefore the whole stack beneath it",
        )

        buffer = tf2_ros.Buffer()
        self._listener = tf2_ros.TransformListener(buffer, self.node)
        pick = self._resolve(buffer, self.pick_frame)
        infeed = self._resolve(buffer, self.infeed_frame)
        outfeed = self._resolve(buffer, self.outfeed_frame)

        sdf_path = Path("/tmp/cite_program_workpiece.sdf")
        sdf_path.write_text(workpiece.workpiece_sdf(self.part))
        spawn = (pick[0], pick[1], pick[2] + self.half_height + SPAWN_DROP_M)
        created = gz_run(
            [
                "ros2",
                "run",
                "ros_gz_sim",
                "create",
                "-file",
                str(sdf_path),
                "-name",
                self.workpiece,
                "-x",
                str(spawn[0]),
                "-y",
                str(spawn[1]),
                "-z",
                str(spawn[2]),
            ],
            zone=ZONE,
            timeout=120,
        )
        self.assertEqual(created.returncode, 0, created.stderr)

        last: list[tuple[float, float, float] | None] = [None]

        def settled() -> tuple[float, float, float] | None:
            current = self._workpiece_xyz()
            previous, last[0] = last[0], current
            if current is None or previous is None:
                return None
            if any(abs(a - b) > SETTLE_TOLERANCE_M for a, b in zip(current, previous, strict=True)):
                return None
            return current

        resting = self._spin_until(settled, SETTLE_CEILING_S, "the work-piece to settle")

        command = [
            sys.executable,
            "-m",
            "cite_bringup.program",
            "--zone",
            ZONE,
            "--via",
            "plant",
            "--cycles",
            "1",
        ]
        returncode, output, samples = self._run_program(command, resting)
        placed = self._workpiece_xyz()
        # The track's axis in the world, from the two belt-free facts the layout
        # gives: the program slides from the pick towards the belt's infeed.
        axis = _unit((infeed[0] - pick[0], infeed[1] - pick[1]))
        lifted = [s for s in samples if s[2] - resting[2] > LIFTED_M]
        highest = max((s[2] for s in samples), default=resting[2])
        carried = max(
            (_along(s, resting, axis) for s in lifted),
            default=0.0,
        )
        context = (
            f"seed={self.seed} (a condition of this run, not a reproducibility claim)\n"
            f"pick {self.pick_frame} at {pick}\n"
            f"infeed {self.infeed_frame} at {infeed}, outfeed at {outfeed}\n"
            f"resting={resting}, highest z={highest:.3f}, carried while lifted "
            f"{carried:.3f} m, placed={placed}\n"
            f"program exited {returncode}\n--- program output ---\n{output[-4000:]}"
        )
        self.assertEqual(returncode, 0, "the program did not complete.\n" + context)
        self.assertIsNotNone(placed, "the work-piece disappeared.\n" + context)
        self.assertGreater(
            highest - resting[2], LIFTED_M, "the work-piece never left the table.\n" + context
        )
        self.assertGreater(
            carried, CARRIED_M, "the work-piece did not travel with the track.\n" + context
        )
        horizontal = max(abs(placed[0] - infeed[0]), abs(placed[1] - infeed[1]))
        self.assertLess(
            horizontal,
            PLACE_TOLERANCE_M,
            f"the work-piece rests {horizontal:.3f} m from {self.infeed_frame}.\n" + context,
        )
        expected_z = infeed[2] + self.half_height
        self.assertLess(
            abs(placed[2] - expected_z),
            HEIGHT_TOLERANCE_M,
            f"the work-piece is at z={placed[2]:.3f} m, not resting on the belt at "
            f"{expected_z:.3f} m.\n" + context,
        )

        # The belt, started by this scenario on the plant alone: it is not part
        # of the program or of the twin (ADR-0067). A setpoint published before
        # the belt's subscriber matched would reach nobody (CLAUDE.md §10).
        belt = self.node.create_publisher(Float64, self.conveyor.command_topic, COMMAND)
        self._spin_until(
            lambda: belt.get_subscription_count() > 0 or None,
            BRING_UP_CEILING_S,
            f"a subscriber on {self.conveyor.command_topic}",
        )
        belt.publish(Float64(data=float(self.conveyor.installed_speed_mps)))
        belt_axis = _unit((outfeed[0] - infeed[0], outfeed[1] - infeed[1]))

        def belted() -> tuple[float, float, float] | None:
            current = self._workpiece_xyz()
            if current is None or _along(current, placed, belt_axis) < BELTED_M:
                return None
            return current

        carried_on = self._spin_until(belted, BELT_CEILING_S, "the belt to carry the work-piece")
        self.assertGreater(
            carried_on[2],
            infeed[2],
            "the work-piece left the belt downwards rather than along it.\n" + context,
        )

    def _run_program(self, command, resting):
        """Run the program to completion, sampling the part's position as it goes."""
        samples: list[tuple[float, float, float]] = []
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        started = time.monotonic()
        spins = 0
        try:
            while process.poll() is None:
                if time.monotonic() - started > CYCLE_CEILING_S:
                    process.kill()
                    output, _ = process.communicate()
                    return (
                        f"killed after CYCLE_CEILING_S={CYCLE_CEILING_S:.0f}s",
                        output,
                        samples,
                    )
                rclpy.spin_once(self.node, timeout_sec=SAMPLE_PERIOD_S)
                spins += 1
                sample = self._workpiece_xyz()
                if sample is not None:
                    samples.append(sample)
        finally:
            if process.poll() is None:  # pragma: no cover - only on an exception path
                process.kill()
        output, _ = process.communicate()
        self._emit_timing(
            "the fixed program to run one cycle",
            CYCLE_CEILING_S,
            time.monotonic() - started,
            spins,
        )
        return process.returncode, output, samples


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = (vector[0] ** 2 + vector[1] ** 2) ** 0.5
    return (vector[0] / length, vector[1] / length)


def _along(point, origin, axis: tuple[float, float]) -> float:
    """How far ``point`` lies from ``origin`` along a horizontal ``axis``."""
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    #: The same single exemption `pick_and_place` carries, for the same
    #: upstream `move_group` teardown segfault; see `bringup.py`.
    UPSTREAM_TEARDOWN_SEGFAULT = "move_group"

    def test_nothing_of_ours_exited_badly(self, proc_info) -> None:
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            expected = (
                [*allowed, -11] if name.startswith(self.UPSTREAM_TEARDOWN_SEGFAULT) else allowed
            )
            self.assertIn(info.returncode, expected, f"{name} exited with {info.returncode}")
