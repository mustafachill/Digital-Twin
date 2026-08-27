"""Scenario: the vertical slice picks a real work-piece.

Phase 1.C's claim is "a single xArm 5 driven through the full stack: facility
model -> generated description -> ros2_control -> MoveIt 2 -> a real Pick skill
-> a behaviour tree that executes it." This is the test of that claim, and it is
deliberately hard to pass by accident: the assertion is that the work-piece
*left the table and arrived where the topology says it should*, measured from
the simulator, not that any component reported success.

Assertions are on outcomes and constraints, never on trajectories. Planning is
sampling-based and therefore stochastic (ADR-0006); a test that pinned a joint
sequence would be flaky and would be deleted by whoever is on call.

Every coordinate this scenario uses is resolved from TF at run time, from the
frames the L0 model generates. Nothing here writes a pick or place coordinate of
its own — that is the property the model exists to give, and a scenario that
hardcoded one would go stale the first time the layout moved and would then be
testing yesterday's cell.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path
from typing import NamedTuple

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

#: The frames station_transfer_1 names in the L0 topology. The scenario passes
#: these names to the coordinator and resolves them through TF for its own
#: measurements; it never writes the coordinates they stand for.
PICK_FRAME = f"{ZONE}__table_pick__surface"
PLACE_FRAME = f"{ZONE}__conveyor_1__infeed"

WORKPIECE_SIZE = 0.05

#: Height above the pick surface the work-piece is released from. Small enough
#: that it settles immediately, large enough that it is not spawned interpenetrating
#: the table — a penetration the physics engine resolves by launching it.
SPAWN_DROP_M = 0.005

#: Wall-clock ceilings, not schedules. Nothing is sequenced by them; they exist so
#: a hang fails the run with a diagnosis instead of blocking CI indefinitely.
#:
#: Their basis, because a bare number tells the next reader nothing: they were
#: chosen against a Linux workstation running near real time. Measured real-time
#: factor on the macOS development host is about 0.14 — `joint_states` arrives at
#: roughly 21 Hz against a configured 150 Hz — so a cycle that takes 110 s there
#: has been observed at 315-420 s here, which is the whole of CYCLE_CEILING_S.
#: A timeout on this host is therefore evidence of a slow machine at least as
#: often as it is evidence of a hang, and the failure message says so.
BRING_UP_CEILING_S = 300.0
CYCLE_CEILING_S = 420.0

#: How far the work-piece must rise above its resting height to count as picked.
#: Larger than any settling or contact jitter, smaller than the retreat distance,
#: so it cannot pass by the box merely being nudged.
LIFTED_M = 0.05

#: How close to the place frame the work-piece must end up, in the horizontal
#: plane. Generous next to the ~0.9 m the piece has to travel, and larger than
#: any settling roll, so it measures "arrived at the right station" rather than
#: placement precision — which is L5's business and needs a metric, not a test.
PLACE_TOLERANCE_M = 0.10

#: How far the work-piece's resting height may differ from the belt surface and
#: still count as placed.
#:
#: This exists because the horizontal check alone cannot see the failure it most
#: needs to see. At the baseline taken before the attachment plugin was removed
#: the work-piece finished at z = 1.201 m — still welded to a finger, half a
#: metre in the air, directly over the infeed — and the scenario passed, because
#: x and y were the only things measured. A part dangling above the target is
#: indistinguishable from a placed part unless height is asserted, and so is a
#: part that fell off the belt onto the floor: both keep their x and y.
#:
#: The check is therefore two-sided, against `place_z + WORKPIECE_SIZE / 2` —
#: resolved from TF at run time like every other coordinate here, never written
#: as a constant. The layout has moved twice on this branch; a hardcoded 0.625
#: would already be wrong once.
#:
#: The bound is set by the widest legitimate resting pose rather than by taste.
#: The cube is released from `release_height_m` (0.04 m above the frame, so about
#: 0.01 m of free fall) and may settle on a corner instead of a face, which lifts
#: its centre by 0.025 x (sqrt(3) - 1) = 0.018 m. 0.05 m clears that worst case
#: with margin while still being an order of magnitude below the 0.576 m error
#: the welded-to-the-gripper baseline showed.
PLACE_HEIGHT_TOLERANCE_M = 0.05

#: How often the work-piece's height is sampled while the cycle runs.
SAMPLE_PERIOD_S = 2.0

#: The seed `./scripts/scenario` exports. It is recorded in the failure report
#: below so that a report names the conditions it was produced under — NOT
#: because it makes the run reproducible.
#:
#: It does not, and the reason is narrower than it used to be. This comment once
#: said "nothing consumes it ... `simulation.launch.py` passes none"; that is now
#: stale, because the launch file does pass it to `gz sim --seed`. But `--seed`
#: calls `gz::math::Rand::Seed`, which covers sensor noise and the transport RNG
#: and neither the physics solver nor the planner. MoveIt exposes no way to seed
#: OMPL's RNG at all — `libmoveit_ompl_interface` contains no reference to it,
#: and MoveIt is apt-installed rather than pinned in `external/cite.repos`, so
#: there is no patch hook either. Sampling-based planning here is therefore
#: genuinely non-deterministic, and no assertion in this file may depend on
#: reproducing a particular plan. `./scripts/scenario` states this on every run.
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


def _workpiece_sdf() -> str:
    """A plain box. Its inertia is computed, not guessed — a wrong tensor here
    would make the pick behave oddly for reasons that look like a controller
    fault (L1).

    It used to carry a `<sensor type="contact">`, which existed for exactly one
    reader: `GraspAttachment::FindGraspable` iterated every `ContactSensorData`
    in the world, and no pad link declares a sensor, so without one here the
    attachment plugin could not fire at all. That plugin is removed, so the
    sensor has no reader and is gone with it. `<mu>` stays and is now the only
    thing holding the part: the grasp is friction, measured over 84 trials in
    `docs/measurements/2026-08-25-friction-grasp/`."""
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
    </link>
  </model>
</sdf>
"""


class CycleOutcome(NamedTuple):
    """What the coordinator process did, for the failure message to quote.

    A `NamedTuple` and deliberately NOT a `@dataclass`, which is the obvious
    choice here and is a trap. This module has `from __future__ import
    annotations`, so `summary: str` reaches the decorator as the *string*
    `"str"`. To decide whether a string annotation means `ClassVar` or
    `InitVar`, `dataclasses._is_type` resolves it against the defining module:
    `sys.modules.get(cls.__module__).__dict__`. `launch_test` loads a scenario
    by path — `spec_from_file_location` / `module_from_spec` / `exec_module`,
    with no `sys.modules` registration — so that lookup returns `None` and
    `@dataclass` raises `AttributeError: 'NoneType' object has no attribute
    '__dict__'` at import time, before a single test runs and with a message
    naming neither this file nor this line.

    `typing.NamedTuple` converts a string annotation to a `ForwardRef` without
    consulting `sys.modules`, so it loads under either loader. Registering this
    module in `sys.modules` would also work and was rejected: it would make the
    scenario depend on a detail of how its runner happens to import it.

    `tests/scenarios/guards/test_scenario_modules_load.py` fails if a dataclass
    comes back here.
    """

    summary: str
    stdout: str
    stderr: str


class TestPickAndPlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.node = Node("scenario_pick_and_place")
        cls.seed = os.environ.get(SEED_VARIABLE, "unset")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, ceiling_s: float, what: str):
        """Spin until `predicate` returns something other than None, or fail.

        `is not None`, not truthiness. A measurement of exactly 0.0 is a perfectly
        good answer, and treating it as "not ready yet" makes a work-piece
        measured at the origin time out as one that never appeared — a diagnosis
        pointing at the spawn instead of at the height. Predicates that answer
        with a bool convert it themselves, at the call site, where the meaning of
        False is obvious.
        """
        end = self.node.get_clock().now().nanoseconds + int(ceiling_s * 1e9)
        result = predicate()
        while result is None and self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.5)
            result = predicate()
        self.assertIsNotNone(result, f"timed out after {ceiling_s:.0f}s waiting for {what}")
        return result

    def _workpiece_xyz(self) -> tuple[float, float, float] | None:
        """Ask the simulator where the work-piece is.

        Read from Gazebo rather than from anything the system under test
        publishes: a component reporting success proves only that it thinks so,
        and the claim being tested is that an object physically moved.

        `gz model -p` prints the pose as bracketed, SPACE-separated triples:

            Model: [4]
              - Name: workpiece
              - Pose [ XYZ (m) ] [ RPY (rad) ]:
                [-0.475000 0.000000 0.630000]
                [0.000000 -0.000000 0.000000]

        so the first numeric triple is the position. The header's `[ XYZ (m) ]`
        contains no numbers and therefore does not match.
        """
        result = subprocess.run(
            ["gz", "model", "-m", WORKPIECE, "-p"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        number = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
        triples = re.findall(rf"\[\s*({number})\s+({number})\s+({number})\s*\]", result.stdout)
        if not triples:
            return None
        try:
            return (float(triples[0][0]), float(triples[0][1]), float(triples[0][2]))
        except ValueError:
            return None

    def _resolve(self, buffer, frame: str) -> tuple[float, float, float]:
        """Where a generated frame is, in `cite_world`, according to the system."""
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

    def test_the_behaviour_tree_picks_and_places_the_workpiece(self) -> None:
        # 1. Wait for the skill server: it is the last thing bring-up starts, so
        #    its presence means the whole stack below it is up.
        import tf2_ros
        from cite_interfaces.action import MoveTo
        from rclpy.action import ActionClient

        client = ActionClient(self.node, MoveTo, f"/cite/{ZONE}/{ARM}/move_to")
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=1.0) or None,
            BRING_UP_CEILING_S,
            "the skill server, and therefore the whole stack beneath it",
        )

        # 2. Ask the running system where the station's frames are. These come
        #    from the L0 model through the generated static transform table, so a
        #    layout change moves the test with it and the belt's working height is
        #    never written here.
        buffer = tf2_ros.Buffer()
        # Held on the instance: a listener that goes out of scope stops filling
        # the buffer, and every later lookup then fails for a reason that has
        # nothing to do with the frames it names.
        self._listener = tf2_ros.TransformListener(buffer, self.node)
        pick = self._resolve(buffer, PICK_FRAME)
        place = self._resolve(buffer, PLACE_FRAME)

        # 3. Put a work-piece on the pick surface, resting on it rather than
        #    intersecting it.
        spawn = (
            pick[0],
            pick[1],
            pick[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M,
        )
        sdf_path = Path("/tmp/cite_workpiece.sdf")
        sdf_path.write_text(_workpiece_sdf())
        created = subprocess.run(
            [
                "ros2",
                "run",
                "ros_gz_sim",
                "create",
                "-file",
                str(sdf_path),
                "-name",
                WORKPIECE,
                "-x",
                str(spawn[0]),
                "-y",
                str(spawn[1]),
                "-z",
                str(spawn[2]),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(created.returncode, 0, created.stderr)

        try:
            resting = self._spin_until(
                lambda: self._workpiece_xyz(), 60.0, "the work-piece to settle"
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
                f"--- ros_gz_sim create stdout ---\n{created.stdout[-2000:]}\n"
                f"--- ros_gz_sim create stderr ---\n{created.stderr[-2000:]}\n"
                f"--- gz model --list (rc={listing.returncode}) ---\n"
                f"{listing.stdout[-2000:]}\n{listing.stderr[-1000:]}"
            ) from exc

        # 4. Run the behaviour tree, sampling the work-piece's height while it
        #    works. Sampling is the only way to observe the lift: a correct cycle
        #    picks from a surface at 0.600 and places onto another surface at
        #    0.600, so comparing start to finish measures nothing — the previous
        #    version of this test asserted a net rise of 50 mm and could therefore
        #    only pass when the cycle failed part of the way through.
        tree = (
            Path(get_package_share_directory("cite_orchestration")) / "trees" / "station_cycle.xml"
        )
        # The coordinator builds no name. Every action it calls, and the
        # work-piece it handles, arrive as parameters — see line_coordinator.cpp.
        # They are written here for now because nothing generated declares a
        # station's skill actions yet; when the topology artifact does, this
        # block reads them from it instead.
        skills = f"/cite/{ZONE}/{ARM}"
        command = [
            "ros2",
            "run",
            "cite_orchestration",
            "line_coordinator",
            "--ros-args",
            "-p",
            f"tree:={tree}",
            "-p",
            f"asset:={ARM}",
            "-p",
            f"workpiece:={WORKPIECE}",
            "-p",
            f"move_to_action:={skills}/move_to",
            "-p",
            f"pick_action:={skills}/pick",
            "-p",
            f"place_action:={skills}/place",
            "-p",
            f"pick_frame:={PICK_FRAME}",
            # Where station_transfer_1 places, per the L0 topology: the first
            # conveyor's infeed. The scenario names the frame, never a
            # coordinate — that is the property the model exists to give.
            "-p",
            f"place_frame:={PLACE_FRAME}",
            "-p",
            "use_sim_time:=true",
        ]
        outcome, highest = self._run_cycle(command, resting)

        final = self._workpiece_xyz()
        self.assertIsNotNone(final, "the work-piece disappeared from the simulator")

        context = (
            f"seed={self.seed} (reaches `gz sim --seed` only, which does not seed "
            "the physics solver or OMPL — see SEED_VARIABLE; this run is not "
            "reproducible)\n"
            f"pick frame {PICK_FRAME} at {pick}\n"
            f"place frame {PLACE_FRAME} at {place}\n"
            f"resting={resting}, highest z={highest:.3f}, final={final}\n"
            f"coordinator {outcome.summary}\n"
            f"--- coordinator stdout ---\n{outcome.stdout[-3000:]}\n"
            f"--- coordinator stderr ---\n{outcome.stderr[-3000:]}"
        )

        # The outcome, measured from the simulator, in two parts. The tree's own
        # exit status is reported for context but is not asserted on: the recovery
        # branch returns SUCCESS after reporting a blockage, so a tree that exits
        # zero has not necessarily picked anything up.
        self.assertGreater(
            highest - resting[2],
            LIFTED_M,
            "the work-piece never left the table.\n" + context,
        )
        horizontal = max(abs(final[0] - place[0]), abs(final[1] - place[1]))
        self.assertLess(
            horizontal,
            PLACE_TOLERANCE_M,
            f"the work-piece was lifted but did not arrive at {PLACE_FRAME}; it is "
            f"{horizontal:.3f} m away in the horizontal plane.\n" + context,
        )

        # Horizontal arrival is not placement. A part still held in the gripper
        # directly above the infeed satisfies the check above, and that is not a
        # hypothetical: it is what the pre-ADR-0029 baseline actually did. So
        # assert the part is resting on the belt, at the height the surface frame
        # puts it — one half-cube above `place`, resolved from TF, not written
        # here. Two-sided on purpose: too high means still carried, too low means
        # it went over the edge, and both keep the x and y that just passed.
        expected_z = place[2] + WORKPIECE_SIZE / 2.0
        vertical = abs(final[2] - expected_z)
        self.assertLess(
            vertical,
            PLACE_HEIGHT_TOLERANCE_M,
            f"the work-piece arrived over {PLACE_FRAME} but is not resting on it; "
            f"its centre is at z={final[2]:.3f} m against an expected "
            f"{expected_z:.3f} m ({vertical:.3f} m away). Higher than expected "
            "means it was never released; lower means it did not stay on the "
            "belt.\n" + context,
        )

    def _run_cycle(
        self, command: list[str], resting: tuple[float, float, float]
    ) -> tuple[CycleOutcome, float]:
        """Run the coordinator to completion, sampling the work-piece as it goes.

        `subprocess.run(timeout=...)` was doing this, and on the single most
        likely failure — a hang — its `TimeoutExpired` propagated uncaught, so the
        carefully assembled report below never ran and the reader got a bare
        traceback naming neither the cycle nor the work-piece.
        """
        highest = resting[2]
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        deadline = self.node.get_clock().now().nanoseconds + int(CYCLE_CEILING_S * 1e9)
        try:
            while process.poll() is None:
                if self.node.get_clock().now().nanoseconds > deadline:
                    process.kill()
                    stdout, stderr = process.communicate()
                    return (
                        CycleOutcome(
                            summary=(
                                f"did not finish within CYCLE_CEILING_S={CYCLE_CEILING_S:.0f}s "
                                "and was killed. On a host whose real-time factor is well "
                                "below 1.0 this is as likely to mean 'slow' as 'hung'"
                            ),
                            stdout=stdout,
                            stderr=stderr,
                        ),
                        highest,
                    )
                rclpy.spin_once(self.node, timeout_sec=SAMPLE_PERIOD_S)
                sample = self._workpiece_xyz()
                if sample is not None:
                    highest = max(highest, sample[2])
        finally:
            if process.poll() is None:  # pragma: no cover - only on an exception path
                process.kill()

        stdout, stderr = process.communicate()
        # One last sample: the cycle may have ended between two polls.
        sample = self._workpiece_xyz()
        if sample is not None:
            highest = max(highest, sample[2])
        return CycleOutcome(f"exited {process.returncode}", stdout, stderr), highest


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    #: See the same exemption in `bringup.py` for the measurement behind this and
    #: for why it is weak: move_group segfaults inside its own destructor —
    #: SIGSEGV in `rclcpp::CallbackGroup::~CallbackGroup` from `MoveItCpp::
    #: ~MoveItCpp` — which a raised `sigterm_timeout` isolated at -11 on 3/3 runs
    #: with no SIGTERM escalation. It is upstream, not a race of ours.
    #:
    #: Kept exactly this wide: one signal, one process name. Widening it to cover
    #: whatever else a contended machine happens to produce would finish turning
    #: this assertion into one that cannot fail.
    UPSTREAM_TEARDOWN_SEGFAULT = "move_group"

    #: What the L3 skill server logs when the default planner refused and the
    #: fallback was tried, and when it refused and the fallback was declined.
    #: Matched rather than parsed: these are log lines for a person, and the only
    #: thing taken from them is that one happened.
    FALLBACK_TAKEN = "planner fallback:"
    FALLBACK_DECLINED = "planner fallback declined:"

    def test_report_how_often_the_planner_fell_back(self, proc_output) -> None:
        """A count, not a gate — and the count is the point (ADR-0027).

        ADR-0027 keeps OMPL as the fallback for the motions a point-to-point
        interpolation cannot make, and says in as many words that a fallback
        which becomes the common path is a finding about the cell's geometry
        rather than about the planner. That is a frequency, a frequency is a
        metric, and metrics belong to L6, which does not exist. This is not a
        second attempt at L6: the report `scripts/scenario` already writes is
        uploaded by CI, and printing the count here puts the number into it at
        the cost of no new interface and no new file.

        Deliberately without a threshold. Nothing has measured what a normal rate
        is on this cell, and a limit invented here would be a pre-registered
        claim with no campaign behind it (P8).
        """
        taken = 0
        declined = 0
        for entry in proc_output:
            text = (
                entry.text.decode(errors="replace")
                if isinstance(entry.text, bytes)
                else str(entry.text)
            )
            taken += text.count(self.FALLBACK_TAKEN)
            declined += text.count(self.FALLBACK_DECLINED)
        print(
            f"planner-fallback count: taken={taken} declined={declined} "
            "(ADR-0027; reported, not gated)"
        )

    def test_nothing_of_ours_exited_badly(self, proc_info) -> None:
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            expected = (
                [*allowed, -11] if name.startswith(self.UPSTREAM_TEARDOWN_SEGFAULT) else allowed
            )
            self.assertIn(info.returncode, expected, f"{name} exited with {info.returncode}")
