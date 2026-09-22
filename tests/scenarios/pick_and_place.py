"""Scenario: the vertical slice picks a real work-piece.

Phase 1.C's claim is "a single xArm 5 driven through the full stack: facility
model -> generated description -> ros2_control -> MoveIt 2 -> a real Pick skill
-> a behaviour tree that executes it." This is the test of that claim, and it is
deliberately hard to pass by accident: the assertion is that the work-piece
*left the table and arrived where the topology says it should*, measured from
the simulator, not that any component reported success.

Assertions are on outcomes and constraints, never on trajectories. A test that
pinned a joint sequence would be flaky and would be deleted by whoever is on
call: a run is not reproducible (see `SEED_VARIABLE` below and ADR-0027).

Every coordinate this scenario uses is resolved from TF at run time, from the
frames the L0 model generates. Nothing here writes a pick or place coordinate of
its own — that is the property the model exists to give, and a scenario that
hardcoded one would go stale the first time the layout moved and would then be
testing yesterday's cell.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import NamedTuple

import launch_testing
import launch_testing.markers
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from cite_bringup.gz import run as gz_run
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.node import Node

# `tests/scenarios/` is not on `sys.path` when this file runs. `launch_test`
# loads a scenario BY PATH — `spec_from_file_location` then `exec_module`, with
# no `sys.modules` entry and no path entry — so a plain `from _cell import ...`
# raises ModuleNotFoundError under the loader that actually runs this, while
# working perfectly under `import`. Put the directory this file lives in on the
# path first, and the sibling resolves under both loaders; the guard
# `test_scenario_loads_by_path` is what proves that, because it uses the same
# loader.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _cell import acting_station, carried_models, cell, zone  # noqa: E402  (insert first)

#: The cell this scenario drives, resolved once at load.
#:
#: NOT A LITERAL ANY MORE. `ZONE = "cell_b"` stood in all three scenarios, which
#: is one fact stated three times and able to disagree silently — the shape
#: CLAUDE.md §4 prohibits — and it also made ADR-0056's own mitigation, a cheap
#: periodic `bringup` against `cell_a`, a source edit rather than a command. The
#: statement lives once in `tests/scenarios/_cell.py`; `./scripts/scenario
#: <name> --zone <zone>` overrides it for one run.
ZONE = zone()

WORKPIECE_SIZE = 0.05

#: Height above the pick surface the work-piece is released from. Small enough
#: that it settles immediately, large enough that it is not spawned interpenetrating
#: the table — a penetration the physics engine resolves by launching it.
SPAWN_DROP_M = 0.005

#: Wall-clock ceilings, not schedules. Nothing is sequenced by them; they exist so
#: a hang fails the run with a diagnosis instead of blocking CI indefinitely.
#:
#: Their basis, because a bare number tells the next reader nothing: they were
#: chosen against a Linux workstation running near real time, and then against the
#: much slower figure the macOS development host was recorded at. That figure holds
#: only under a condition — roughly one CPU core — stated once, with its
#: measurement, in `docs/architecture/cross-cutting-testing.md` under "Wall-clock
#: ceilings". The 315-420 s cycle observed here against a 110 s workstation cycle
#: belongs to that starved condition: at a full CPU allocation the same cycle was
#: measured far below it
#: (`docs/measurements/2026-08-29-real-time-factor-conditions/`).
#:
#: CYCLE_CEILING_S is therefore not a generous ceiling that happens to be large.
#: It is sized for the starved condition, where its margin is about 1.2, and below
#: roughly 1.2 cores this scenario times out with nothing broken. Diagnose the
#: host's CPU allocation before the code, and do not widen this to absorb it.
BRING_UP_CEILING_S = 300.0
CYCLE_CEILING_S = 420.0

#: How long the work-piece may take to appear and come to rest after
#: `ros_gz_sim create` returns. Observed in about a second; this is a hang
#: detector, not a schedule, and the wait ends on the first pose the simulator
#: answers with. Named rather than written at the call site so that a campaign
#: reading `CITE_TIMING` records can tell it from `bringup.TRAJECTORY_CEILING_S`,
#: which is also 60.0 and bounds something else entirely.
SETTLE_CEILING_S = 60.0

#: How close two consecutive readings of the work-piece's position must be to
#: count as "at rest", in metres.
#:
#: `_workpiece_xyz` answers as soon as the model EXISTS, not once it has
#: stopped moving, so the settle wait below has to ask a second question of its
#: own: not "is there a pose" but "has the pose stopped changing". A JUDGEMENT,
#: not a derivation from any physical constant — small enough that a part still
#: settling from its ~5 mm drop (`SPAWN_DROP_M`) will not read as still twice in
#: a row, and well inside every tolerance this scenario actually asserts on
#: (`PLACE_TOLERANCE_M`, `PLACE_HEIGHT_TOLERANCE_M`), so tightening it further
#: could only ever cost time, never coverage.
SETTLE_TOLERANCE_M = 1e-4

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

#: How far any joint of the acting arm may turn from zero, over the whole run.
#: Radians.
#:
#: HALF A TURN, and the claim is exactly "the arm never winds past half a turn".
#: `joint1` and `joint5` on this arm are declared over TWO revolutions, so every
#: reachable tool pose has a wound twin a whole turn away and an IK solver is
#: free to return either. Measured on the running cell: a place pose reached at
#: `joint1 = 5.253 rad` with the joint standing at 1.007 - a 301 degree sweep in
#: place of a 59 degree one, at full speed, through the volume in front of the
#: cell - and `joint5` at -5.743 in the same run. Both are past this bound and
#: neither is past a joint LIMIT, so nothing in the stack refused either and no
#: gate in this repository could see them.
#:
#: This is a CONSTRAINT and not a trajectory, which is what ADR-0006 permits a
#: scenario to assert: it survives a layout change, a different planner and a
#: different seed, because what it says is that a pose is reached the short way
#: round and not which angles reach it. Half a turn is the bound that separates
#: the two - a wound twin is a whole turn away, so it cannot sit inside this
#: band while its unwound partner also does.
WOUND_PAST_RAD = math.pi

#: The seed `./scripts/scenario` exports. It is recorded in the failure report
#: below so that a report names the conditions it was produced under — NOT
#: because it makes the run reproducible. It does not: the physics solver is
#: seeded by nothing, so no assertion in this file may depend on reproducing a
#: particular plan or a particular contact.
#:
#: What the seed does and does not buy is stated once, in ADR-0027 § "What
#: `CITE_PHYSICS_SEED` does and does not buy", and `./scripts/scenario` says it
#: on every run. Do not restate the argument here — it was restated in seven
#: places and the copies drifted, which is why this is a pointer.
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


def _workpiece_sdf(name: str) -> str:
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
  <model name="{name}">
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

        # The station this scenario drives, and the arm that serves it, read off
        # the generated topology in flow order rather than named. The rule is
        # `_cell.acting_station` and is written once: the topology is emitted
        # alphabetically, so "the first station that picks and places" has to be
        # found by walking the edges — reading the list in file order would find
        # whichever id sorts first, which is the sink.
        plan, topology = cell(ZONE)
        cls.station = acting_station(topology)
        cls.pick_frame = cls.station["pick_frame"]
        cls.place_frame = cls.station["place_frame"]
        cls.arm = cls.station["actor"]

        managers = {m.asset: m for m in plan.controller_managers}
        assert cls.arm in managers, (
            f"{cls.station['id']} names actor {cls.arm!r}, which the bring-up plan for "
            f"{ZONE} declares no controller manager for"
        )
        # Every action the coordinator is told to call. The plan states these —
        # this file used to compose them from the zone and the asset under a
        # comment saying "nothing generated declares a station's skill actions
        # yet", which had stopped being true.
        cls.skills = managers[cls.arm].skills
        assert cls.skills is not None, f"the plan declares no skill actions for {cls.arm}"
        # Where this arm reports its joints, per the plan. Read and not composed
        # from the zone and the asset, for the reason everything else here is.
        cls.joint_state_topic = managers[cls.arm].joint_state_topic

        # The Gazebo model name of the part, DERIVED rather than written. It was
        # `WORKPIECE = "workpiece"` under a comment arguing that the name is a
        # facility fact and not a cell one. That is true and it is not the
        # question: being facility-scoped does not stop it being a second
        # statement of `facility.workpiece_models`. `continuous_line` already
        # derived it from the generated world; this is the same three lines.
        names = carried_models(Path(plan.world))
        assert len(names) == 1, (
            f"the generated world for {ZONE} declares {sorted(names)} as both carried and "
            "watched. This scenario drives one part, so it cannot choose between two."
        )
        cls.workpiece = next(iter(names))

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

        On the success path it emits one `CITE_TIMING` record through
        `_emit_timing`, saying how long the wait actually took.
        `docs/measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md` §3
        could reach this scenario's ceilings only through proxies, because
        per-milestone timings were not printed.

        WHAT THIS FILE COVERS, stated exactly rather than generously. All three of
        its ceilings emit: `BRING_UP_CEILING_S` and `SETTLE_CEILING_S` here, and
        `CYCLE_CEILING_S` from the deadline loop in `_run_cycle`, which is the one
        place that ceiling is used and which passes through no wait of this shape.
        This file defines no `DELIVERY_CEILING_S`, `TRAJECTORY_CEILING_S`,
        `SKILL_CEILING_S` or `LEG_CEILING_S` — an earlier version of this
        docstring named them, and a docstring that lists another file's constants
        is a claim about a file it cannot see.
        """
        # `time.monotonic`, never the node clock: these ceilings are wall clock by
        # deliberate design — this observer does not set `use_sim_time`, for the
        # reason `continuous_line.Sample` gives — and a monotonic clock cannot jump
        # backwards under a wall-clock step and report a wait that took less than
        # no time. Do not "fix" this to the node clock.
        started = time.monotonic()
        end = self.node.get_clock().now().nanoseconds + int(ceiling_s * 1e9)
        spins = 0
        result = predicate()
        while result is None and self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.5)
            spins += 1
            result = predicate()
        self.assertIsNotNone(result, f"timed out after {ceiling_s:.0f}s waiting for {what}")
        # Success only. A timing record for a wait that timed out would be a
        # measurement of the ceiling rather than of the milestone.
        self._emit_timing(what, ceiling_s, time.monotonic() - started, spins)
        return result

    def _emit_timing(self, what: str, ceiling_s: float, elapsed_s: float, spins: int) -> None:
        """Print one `CITE_TIMING` record, for a wait that ENDED IN SUCCESS.

        The one writer of the format in this file. Every field exists because a
        campaign re-deriving a ceiling from these records cannot do its job
        without it:

          * `spins` — how many times the wait went round its loop before the thing
            it waited for was there. A LOOP COUNT AND NOT A TIME UNIT: one spin is
            one `rclpy.spin_once` timeout, every emitting loop sets that quantum
            for itself, and the loops that emit these records do not all agree on
            it — `pick_and_place._run_cycle` spins on that file's own
            `SAMPLE_PERIOD_S`, which is not the quantum the `_spin_until` waits
            use. So `spins` may never be multiplied into a duration, and may not
            be read as a sampling density across one table either, because the
            three scenarios are parsed as one table and their quanta differ.
            `elapsed_s` is the only time field.
            `_spin_until` tests its predicate once before spinning at all, so
            `spins: 0` means the predicate answered on its first evaluation and
            the record is NOT a measurement of a milestone. THIS is the field to
            filter on, and `elapsed_s` is not: a zero-spin record usually reads
            near 0.000 s, but not always — `pick_and_place`'s work-piece predicate
            shells out to `gz model -p`, and one evaluation of a subprocess can
            cost an appreciable fraction of a second, which measures that
            subprocess and nothing this project sets a ceiling on. How much it
            costs is unpublished — no directory under `docs/measurements/` stands
            behind any figure for it — which is exactly why the rule is structural:
            discard zero-spin records by rule; do not eyeball the elapsed times.
            `_run_cycle` tests its condition — whether the coordinator process
            has exited — before it spins at all, in the same way, so it can report
            `spins: 0` too; and the subprocess named above is this file's own
            work-piece predicate, so this is the scenario where a zero-spin record
            is least likely to read near zero.
          * `test` — the test method that produced the record. This file runs one
            test today, so it disambiguates nothing here; it is emitted because
            the three scenarios write one format and a campaign parses them as one
            table, and in `bringup` it is what separates a real bring-up wait from
            the near-zero ones every test after the first records.
          * `monotonic_s` — this process's clock at the moment of printing, so
            records can be ordered and lined up against the launch log.

        The keys are asserted by `tests/scenarios/guards/test_timing_records.py`,
        which loads all three scenarios and requires them to agree. `flush=True`
        because `launch_test` captures this stream and can tear the process down
        with a buffered line still sitting in it.
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
        result = gz_run(["gz", "model", "-m", self.workpiece, "-p"], zone=ZONE, timeout=30)
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

        client = ActionClient(self.node, MoveTo, self.skills.move_to)
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=1.0) or None,
            BRING_UP_CEILING_S,
            "the skill server, and therefore the whole stack beneath it",
        )

        # 1b. Watch every joint angle for the rest of the run, so that HOW the
        #     arm reached each pose can be asserted on and not only WHERE it
        #     ended up. Nothing in this repository could see a 301 degree sweep:
        #     it violates no joint limit, produces no error, and leaves the part
        #     in exactly the right place, so every assertion below passes while
        #     the arm swings the long way round through the front of the cell.
        #
        #     FROM THE TOPIC AND NOT FROM THE SAMPLING LOOP BELOW. That loop
        #     turns once per `SAMPLE_PERIOD_S`, and a sweep out and back takes a
        #     few seconds, so a poll at that period can land either side of an
        #     excursion and see neither end of it. A subscription callback sees
        #     every message the executor delivers, and the extremes are folded
        #     in as they arrive.
        from cite_interfaces.qos import STATE
        from sensor_msgs.msg import JointState

        self._extremes: dict[str, tuple[float, float]] = {}

        def record(message: JointState) -> None:
            # `strict=False`: a length mismatch here would be a malformed
            # message, and raising for it inside a subscription callback would
            # propagate out of `rclpy.spin_once` in `_run_cycle` and end the run
            # with a bare traceback - the exact failure mode that method's
            # docstring records having removed. The emptiness check at the
            # assertion is what catches a watch that saw nothing.
            for name, position in zip(message.name, message.position, strict=False):
                low, high = self._extremes.get(name, (position, position))
                self._extremes[name] = (min(low, position), max(high, position))

        # Explicit profile, matching the broadcaster's. An incompatible one
        # connects silently and delivers nothing, which here would look exactly
        # like an arm that never wound (CLAUDE.md section 10) - which is what the
        # emptiness check at the assertion is for.
        self._joint_watch = self.node.create_subscription(
            JointState, self.joint_state_topic, record, STATE
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
        pick = self._resolve(buffer, self.pick_frame)
        place = self._resolve(buffer, self.place_frame)

        # 3. Put a work-piece on the pick surface, resting on it rather than
        #    intersecting it.
        spawn = (
            pick[0],
            pick[1],
            pick[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M,
        )
        sdf_path = Path("/tmp/cite_workpiece.sdf")
        sdf_path.write_text(_workpiece_sdf(self.workpiece))
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

        try:
            # A pose EXISTING and a pose AT REST are different questions, and
            # `_workpiece_xyz` only answers the first — so waiting on it alone
            # starts the cycle at whatever point of the drop this run happens to
            # sample, which is exactly the kind of run-to-run difference in
            # initial state a reproducibility measurement would (and did) catch.
            # `last_pose` is this closure's own memory between polls of the
            # SAME `_spin_until` loop; it is not read or written anywhere else.
            last_pose: list[tuple[float, float, float] | None] = [None]

            def settled() -> tuple[float, float, float] | None:
                current = self._workpiece_xyz()
                previous, last_pose[0] = last_pose[0], current
                if current is None or previous is None:
                    return None
                if any(
                    abs(a - b) > SETTLE_TOLERANCE_M for a, b in zip(current, previous, strict=True)
                ):
                    return None
                return current

            resting = self._spin_until(settled, SETTLE_CEILING_S, "the work-piece to settle")
        except AssertionError as exc:
            # A missing work-piece is a setup failure, not a result. Say which,
            # with the evidence, rather than leaving the reader to guess whether
            # the arm failed or the box was never there.
            listing = gz_run(["gz", "model", "--list"], zone=ZONE, timeout=30)
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
        # Every one of them is now read from the generated plan and topology in
        # `setUpClass`, which is what the superseded version of this comment said
        # would happen "when the topology artifact does" — it already did.
        command = [
            "ros2",
            "run",
            "cite_orchestration",
            "line_coordinator",
            "--ros-args",
            "-p",
            f"tree:={tree}",
            "-p",
            f"asset:={self.arm}",
            "-p",
            f"workpiece:={self.workpiece}",
            "-p",
            f"move_to_action:={self.skills.move_to}",
            "-p",
            f"pick_action:={self.skills.pick}",
            "-p",
            f"place_action:={self.skills.place}",
            "-p",
            f"pick_frame:={self.pick_frame}",
            # Where this station places, per the L0 topology. The scenario names
            # the frame, never a coordinate — that is the property the model
            # exists to give.
            "-p",
            f"place_frame:={self.place_frame}",
            "-p",
            "use_sim_time:=true",
        ]
        outcome, highest = self._run_cycle(command, resting)

        final = self._workpiece_xyz()
        self.assertIsNotNone(final, "the work-piece disappeared from the simulator")

        context = (
            f"seed={self.seed} (a condition this run was produced under, not a "
            "reproducibility claim — see SEED_VARIABLE and ADR-0027)\n"
            f"pick frame {self.pick_frame} at {pick}\n"
            f"place frame {self.place_frame} at {place}\n"
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
            f"the work-piece was lifted but did not arrive at {self.place_frame}; it is "
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
            f"the work-piece arrived over {self.place_frame} but is not resting on it; "
            f"its centre is at z={final[2]:.3f} m against an expected "
            f"{expected_z:.3f} m ({vertical:.3f} m away). Higher than expected "
            "means it was never released; lower means it did not stay on the "
            "belt.\n" + context,
        )

        # HOW THE ARM GOT THERE, which every assertion above is blind to. A part
        # picked and placed by an arm that took the long way round satisfies all
        # three of them, and that is not hypothetical - it is what this cell did
        # until the IK solution was rewritten to the near branch.
        #
        # The emptiness check first, and it is not a formality: this assertion is
        # over what ARRIVED, so a subscription that matched nothing - a renamed
        # topic, an incompatible profile, a controller that never activated -
        # would otherwise report an arm that never wound past anything. A silence
        # is not a clearance.
        self.assertTrue(
            self._extremes,
            f"no message arrived on {self.joint_state_topic} for the whole cycle, so "
            "nothing here observed the arm at all and the constraint below was "
            "never evaluated.\n" + context,
        )
        wound = {
            name: (low, high)
            for name, (low, high) in sorted(self._extremes.items())
            if low < -WOUND_PAST_RAD or high > WOUND_PAST_RAD
        }
        self.assertFalse(
            wound,
            "a joint wound past half a turn while reaching a pose it could have "
            "reached the short way round: "
            + ", ".join(
                f"{name} spanned [{low:.3f}, {high:.3f}] rad" for name, (low, high) in wound.items()
            )
            + f", against a bound of +/-{WOUND_PAST_RAD:.3f}. This breaks no joint limit "
            "and produces no error anywhere in the stack, which is why it needs its own "
            "assertion: the sweep is at full speed, through the volume in front of the "
            "cell, and the part still arrives. If this fires on a motion that genuinely "
            "had no shorter representative - the arm already standing past half a turn "
            "when the next pose was solved - the finding is about this bound and not "
            "about the arm, and it is a project decision rather than one to widen "
            "here.\n" + context,
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
        # Timed as well as bounded. This loop is the only user of
        # `CYCLE_CEILING_S`, and it passes through no `_spin_until`, so without
        # this the one ceiling that dominates this scenario's runtime emitted
        # nothing at all.
        started = time.monotonic()
        spins = 0
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
                                "below 1.0 this is as likely to mean 'slow' as 'hung': this "
                                "ceiling's margin is about 1.2 when the cell has roughly one "
                                "CPU core, so check what this container was allocated and "
                                "what else held the host before suspecting motion. See "
                                "docs/architecture/cross-cutting-testing.md, 'Wall-clock "
                                "ceilings'"
                            ),
                            stdout=stdout,
                            stderr=stderr,
                        ),
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

        stdout, stderr = process.communicate()
        # Success only, in the sense the record means: the coordinator exited
        # under its own ceiling. Its exit STATUS is deliberately not asserted on
        # here (see the caller), and is not what this measures — the interval is
        # the one `CYCLE_CEILING_S` bounds, which ends when the process ends.
        # So the consumer's rule, which the other three emitters do not need: a
        # record exists here whenever the coordinator exited AT ALL, a crash two
        # seconds in included, and it does not say the cycle succeeded. Use these
        # records only from runs whose scenario verdict passed; folding a failed
        # run's short elapsed into a margin makes `CYCLE_CEILING_S` look roomier
        # than any run has shown it to be.
        self._emit_timing(
            "the station cycle to run to completion",
            CYCLE_CEILING_S,
            time.monotonic() - started,
            spins,
        )
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
