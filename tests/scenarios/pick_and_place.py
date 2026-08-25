"""Scenario: the vertical slice picks a real work-piece.

Phase 1.C's claim is "a single xArm 5 driven through the full stack: facility
model -> generated description -> ros2_control -> MoveIt 2 -> a real Pick skill
-> a behaviour tree that executes it." This is the test of that claim, and it is
deliberately hard to pass by accident: the assertion is that the work-piece
*left the table*, measured from the simulator, not that any component reported
success.

Assertions are on outcomes and constraints, never on trajectories. Planning is
sampling-based and therefore stochastic (ADR-0006); a test that pinned a joint
sequence would be flaky and would be deleted by whoever is on call.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

import launch_testing
import launch_testing.markers
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.node import Node

ZONE = "cell_a"
ARM = "arm_1"
WORKPIECE = "workpiece"

#: Where the work-piece starts: on the pick table's surface, which is the frame
#: the L0 topology names for station_transfer_1's pick point. Written here rather
#: than derived because a scenario is allowed to state its own initial
#: conditions — but the arm is never told these numbers; it is given the frame.
WORKPIECE_XYZ = (-0.45, 0.0, 0.63)
WORKPIECE_SIZE = 0.05

BRING_UP_CEILING_S = 300.0
CYCLE_CEILING_S = 420.0

#: How far the work-piece must move to count as picked. Larger than any settling
#: or contact jitter, smaller than the retreat distance, so it cannot pass by the
#: box merely being nudged.
LIFTED_M = 0.05


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


def _workpiece_sdf() -> str:
    """A plain box. Its inertia is computed, not guessed — a wrong tensor here
    would make the pick behave oddly for reasons that look like a controller
    fault (L1)."""
    mass = 0.2
    side = WORKPIECE_SIZE
    inertia = mass * (side * side + side * side) / 12.0
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{WORKPIECE}">
    <link name="link">
      <inertial>
        <mass>{mass}</mass>
        <inertia>
          <ixx>{inertia}</ixx><iyy>{inertia}</iyy><izz>{inertia}</izz>
          <ixy>0</ixy><ixz>0</ixz><iyz>0</iyz>
        </inertia>
      </inertial>
      <collision name="collision">
        <geometry><box><size>{side} {side} {side}</size></box></geometry>
        <surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface>
      </collision>
      <visual name="visual">
        <geometry><box><size>{side} {side} {side}</size></box></geometry>
        <material><ambient>0.8 0.3 0.1 1</ambient><diffuse>0.9 0.4 0.1 1</diffuse></material>
      </visual>
      <sensor name="contact" type="contact">
        <contact><collision>collision</collision></contact>
        <always_on>true</always_on>
        <update_rate>100</update_rate>
      </sensor>
    </link>
  </model>
</sdf>
"""


class TestPickAndPlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.node = Node("scenario_pick_and_place")
        cls.seed = os.environ.get("CITE_PHYSICS_SEED", "unset")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, ceiling_s: float, what: str):
        end = self.node.get_clock().now().nanoseconds + int(ceiling_s * 1e9)
        result = predicate()
        while not result and self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.5)
            result = predicate()
        self.assertTrue(result, f"timed out after {ceiling_s:.0f}s waiting for {what}")
        return result

    def _workpiece_z(self) -> float | None:
        """Ask the simulator where the work-piece is.

        Read from Gazebo rather than from anything the system under test
        publishes: a component reporting success proves only that it thinks so,
        and the claim being tested is that an object physically moved.

        `gz model -p` prints the pose as bracketed, SPACE-separated triples:

            Model: [4]
              - Name: workpiece
              - Pose [ XYZ (m) ] [ RPY (rad) ]:
                [-0.450000 0.000000 0.630000]
                [0.000000 -0.000000 0.000000]

        so the first numeric triple is the position and its third value is Z. The
        header's `[ XYZ (m) ]` contains no numbers and therefore does not match.
        """
        result = subprocess.run(
            ["gz", "model", "-m", WORKPIECE, "-p"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        number = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
        triples = re.findall(
            rf"\[\s*({number})\s+({number})\s+({number})\s*\]", result.stdout
        )
        if not triples:
            return None
        try:
            return float(triples[0][2])
        except ValueError:
            return None

    def test_the_behaviour_tree_picks_the_workpiece(self) -> None:
        # 1. Wait for the skill server: it is the last thing bring-up starts, so
        #    its presence means the whole stack below it is up.
        from cite_interfaces.action import MoveTo
        from rclpy.action import ActionClient

        client = ActionClient(self.node, MoveTo, f"/cite/{ZONE}/{ARM}/move_to")
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=1.0),
            BRING_UP_CEILING_S,
            "the skill server, and therefore the whole stack beneath it",
        )

        # 2. Put a work-piece on the pick table.
        sdf_path = Path("/tmp/cite_workpiece.sdf")
        sdf_path.write_text(_workpiece_sdf())
        spawn = subprocess.run(
            [
                "ros2", "run", "ros_gz_sim", "create",
                "-file", str(sdf_path),
                "-name", WORKPIECE,
                "-x", str(WORKPIECE_XYZ[0]),
                "-y", str(WORKPIECE_XYZ[1]),
                "-z", str(WORKPIECE_XYZ[2]),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(spawn.returncode, 0, spawn.stderr)

        try:
            resting = self._spin_until(
                lambda: self._workpiece_z(), 60.0, "the work-piece to settle"
            )
        except AssertionError as exc:
            # A missing work-piece is a setup failure, not a result. Say which,
            # with the evidence, rather than leaving the reader to guess whether
            # the arm failed or the box was never there.
            listing = subprocess.run(
                ["gz", "model", "--list"], capture_output=True, text=True, timeout=30
            )
            raise AssertionError(
                f"{exc}\n"
                f"--- ros_gz_sim create stdout ---\n{spawn.stdout[-2000:]}\n"
                f"--- ros_gz_sim create stderr ---\n{spawn.stderr[-2000:]}\n"
                f"--- gz model --list (rc={listing.returncode}) ---\n"
                f"{listing.stdout[-2000:]}\n{listing.stderr[-1000:]}"
            ) from exc

        # 3. Run the behaviour tree. L4 calls L3 skills and nothing else.
        tree = (
            Path(get_package_share_directory("cite_orchestration"))
            / "trees"
            / "station_cycle.xml"
        )
        coordinator = subprocess.run(
            [
                "ros2", "run", "cite_orchestration", "line_coordinator",
                "--ros-args",
                "-p", f"zone:={ZONE}",
                "-p", f"tree:={tree}",
                "-p", f"asset:={ARM}",
                "-p", f"pick_frame:={ZONE}__table_pick__surface",
                # Where station_transfer_1 places, per the L0 topology: the first
                # conveyor's infeed. The scenario names the frame, never a
                # coordinate — that is the property the model exists to give.
                "-p", f"place_frame:={ZONE}__conveyor_1__infeed",
                "-p", "use_sim_time:=true",
            ],
            capture_output=True,
            text=True,
            timeout=CYCLE_CEILING_S,
        )

        lifted = self._workpiece_z()
        self.assertIsNotNone(lifted, "the work-piece disappeared from the simulator")

        # The outcome, measured from the simulator. The tree's own exit status is
        # reported for context but is not what this asserts on: the recovery
        # branch returns SUCCESS after reporting a blockage, so a tree that exits
        # zero has not necessarily picked anything up.
        self.assertGreater(
            lifted - resting,
            LIFTED_M,
            "the work-piece never left the table.\n"
            f"resting z={resting:.3f}, final z={lifted:.3f}\n"
            f"coordinator exit={coordinator.returncode}\n"
            f"--- coordinator stdout ---\n{coordinator.stdout[-3000:]}\n"
            f"--- coordinator stderr ---\n{coordinator.stderr[-3000:]}",
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    UPSTREAM_TEARDOWN_SEGFAULT = "move_group"

    def test_nothing_of_ours_exited_badly(self, proc_info) -> None:
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            expected = (
                [*allowed, -11]
                if name.startswith(self.UPSTREAM_TEARDOWN_SEGFAULT)
                else allowed
            )
            self.assertIn(info.returncode, expected, f"{name} exited with {info.returncode}")
