"""Scenario: the fixed program carries a work-piece from the table to the belt's end.

ADR-0066's claim, checked on one side: `python3 -m cite_bringup.program --via
plant` moves the arm through its taught L0 poses, grips the part, places it on
the belt and runs the belt long enough to carry it to the outfeed. The assertion
is on the OUTCOME, measured from the simulator: the work-piece rests on the belt
at the outfeed frame. Nothing the program reports is believed on its own.

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
    tie_the_work_piece_size,
    zone,
)

#: The cell this scenario drives, from the one statement in `_cell.py`. The
#: program needs taught poses, so a zone whose arm declares none is refused by
#: the program itself, with a message naming what is missing.
ZONE = zone()

#: The reference work-piece's edge length; tied to `cite_bringup.workpiece`
#: at run time by `tie_the_work_piece_size`, as in `pick_and_place`.
WORKPIECE_SIZE = 0.05

#: Height above the pick surface the work-piece is released from.
SPAWN_DROP_M = 0.005

#: Wall-clock ceilings that bound a failure and sequence nothing. The cycle is
#: `pick_and_place`'s cycle plus the belt run, so it is that scenario's ceiling
#: plus room for the belt; see `pick_and_place.CYCLE_CEILING_S` for the basis.
BRING_UP_CEILING_S = 300.0
SETTLE_CEILING_S = 60.0
CYCLE_CEILING_S = 600.0

#: How still the part must be to count as settled, and how often it is sampled.
SETTLE_TOLERANCE_M = 1e-4
SAMPLE_PERIOD_S = 2.0

#: How far the part must rise to count as picked, as in `pick_and_place`.
LIFTED_M = 0.05

#: How close to the outfeed frame the part must end, horizontally and in height.
#: Horizontal: the part rides the belt from where it was placed for the belt's
#: length at its speed, so it ends about where it was placed relative to the
#: infeed; `pick_and_place.PLACE_TOLERANCE_M` bounds that placement. Height: the
#: same two-sided bound `pick_and_place` uses — too high is still held, too low
#: fell off the end.
ARRIVAL_TOLERANCE_M = 0.10
HEIGHT_TOLERANCE_M = 0.05

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
        tie_the_work_piece_size(WORKPIECE_SIZE)
        plan, topology = cell(ZONE)
        station = acting_station(topology)
        cls.pick_frame = station["pick_frame"]
        managers = {m.asset: m for m in plan.controller_managers}
        cls.skills = managers[station["actor"]].skills
        assert len(plan.conveyors) == 1, f"{ZONE} does not have exactly one belt"
        cls.outfeed_frame = f"{ZONE}__{plan.conveyors[0].asset}__outfeed"
        names = carried_models(Path(plan.world))
        assert len(names) == 1, f"{ZONE}'s world carries {sorted(names)}, not one part"
        cls.workpiece = next(iter(names))

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

    def test_the_program_carries_the_workpiece_to_the_outfeed(self) -> None:
        import tf2_ros
        from cite_interfaces.action import MoveTo
        from rclpy.action import ActionClient

        client = ActionClient(self.node, MoveTo, self.skills.move_to)
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=1.0) or None,
            BRING_UP_CEILING_S,
            "the skill server, and therefore the whole stack beneath it",
        )

        buffer = tf2_ros.Buffer()
        self._listener = tf2_ros.TransformListener(buffer, self.node)
        pick = self._resolve(buffer, self.pick_frame)
        outfeed = self._resolve(buffer, self.outfeed_frame)

        sdf_path = Path("/tmp/cite_program_workpiece.sdf")
        sdf_path.write_text(workpiece.workpiece_sdf(self.workpiece))
        spawn = (pick[0], pick[1], pick[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M)
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
        returncode, output, highest = self._run_program(command, resting)
        final = self._workpiece_xyz()
        context = (
            f"seed={self.seed} (a condition of this run, not a reproducibility claim)\n"
            f"pick frame {self.pick_frame} at {pick}\n"
            f"outfeed frame {self.outfeed_frame} at {outfeed}\n"
            f"resting={resting}, highest z={highest:.3f}, final={final}\n"
            f"program exited {returncode}\n--- program output ---\n{output[-4000:]}"
        )
        self.assertEqual(returncode, 0, "the program did not complete.\n" + context)
        self.assertIsNotNone(final, "the work-piece disappeared.\n" + context)
        self.assertGreater(
            highest - resting[2], LIFTED_M, "the work-piece never left the table.\n" + context
        )
        horizontal = max(abs(final[0] - outfeed[0]), abs(final[1] - outfeed[1]))
        self.assertLess(
            horizontal,
            ARRIVAL_TOLERANCE_M,
            f"the work-piece ended {horizontal:.3f} m from {self.outfeed_frame}.\n" + context,
        )
        expected_z = outfeed[2] + WORKPIECE_SIZE / 2.0
        self.assertLess(
            abs(final[2] - expected_z),
            HEIGHT_TOLERANCE_M,
            f"the work-piece is at z={final[2]:.3f} m, not resting on the belt at "
            f"{expected_z:.3f} m.\n" + context,
        )

    def _run_program(self, command, resting):
        """Run the program to completion, sampling the part's height as it goes."""
        highest = resting[2]
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
                        highest,
                    )
                rclpy.spin_once(self.node, timeout_sec=SAMPLE_PERIOD_S)
                spins += 1
                sample = self._workpiece_xyz()
                if sample is not None:
                    highest = max(highest, sample[2])
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
        return process.returncode, output, highest


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
