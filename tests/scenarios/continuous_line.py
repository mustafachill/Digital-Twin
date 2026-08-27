"""Scenario: the line runs itself, from the pick area to accumulation.

This is the test of Phase 1.D's claim, which the charter states as: *N
work-pieces enter at the pick area and arrive at accumulation, sensor-triggered,
with no intervention.* Each half of that sentence is asserted separately, because
each has already been claimed here on evidence that turned out to measure
something else:

  * **arrive** is measured from the simulator — where the work-piece physically
    is — and never from a component's report about itself. `LineState` carries a
    `workpieces_completed` count and this scenario does NOT gate on it:
    `line_maintenance.hpp` increments it when the last robot lets go, which is a
    statement about a gripper and not about the accumulation end of the line. It
    is printed as context, labelled as what it is.
  * **sensor-triggered** is measured from the typed `DetectionEvent` stream, one
    beam per link, in the order the L0 topology puts them. A piece that arrived
    without every beam on the way reporting it was not carried by the line the
    topology describes.

Assertions are on outcomes and constraints, never on trajectories. Planning is
sampling-based and stochastic (ADR-0006) and `./scripts/scenario` warns on every
run that the physics seed reaches `gz sim --seed` only, which buys neither solver
determinism nor a reproducible plan. So what is asserted is: every piece reached
every milestone the topology defines, the piece never left the cell's working
volume, no station ever reported a fault, and all of it inside a wall-clock
ceiling.

## Nothing here names a station, a belt, a beam or a coordinate

The milestone ladder is *derived* from the generated process topology, the way
`line_orchestrator` derives the line it runs, and every position it is measured
against is resolved from TF at run time. The layout on this branch has moved
twice and a hardcoded coordinate was wrong both times. `ZONE` and the
work-piece's physical properties are the only cell-specific values below, and the
work-piece's *name* is read out of the generated world rather than written.

## Two things this scenario does that are the line's boundary, not intervention

1. **It feeds the source.** `station_infeed` is a `source_station` and the L0
   model says in as many words that it is fed externally. Something has to put a
   part on the pick table; here it is `ros_gz_sim create`, at the pick frame TF
   reports.
2. **It empties the sink, and it has no choice.** The belt's `<carry>` list and
   the beam's `<watch>` list match a Gazebo model name *exactly*
   (`conveyor.cpp`, `break_beam.cpp`), and `facility.workpiece_models` declares
   exactly one name, so at most one work-piece can exist that the simulation aids
   will act on at all. The pieces therefore traverse the line one at a time and
   the finished one is removed before the next is fed. That limitation is
   asserted rather than assumed — see `carried_models` — so the day the model
   declares a family of work-piece names, this scenario fails and says to make
   itself concurrent.

It supplies nothing else. It used to supply the belt setpoints too, because
nothing in the running system commanded a conveyor; ADR-0032 gave that setpoint an
owner in L4, so this scenario now READS the command topics and asserts the line
started its own belts — see `_assert_the_line_started_the_belts`. A second
publisher on a topic the system owns is a hazard, not a gap.

## What this scenario cannot see

Gazebo publishes no contact stream anything here reads, so "no collision" is
asserted through the observable the system does publish: a collision that matters
in this cell is a planning refusal or an execution fault, and an unrecoverable
one reaches `LineState` as a faulted station. A contact that harmed nothing and
was reported nowhere passes unnoticed, and that is stated rather than implied.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import NamedTuple

import launch_testing
import launch_testing.markers
import pytest
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cite_interfaces.msg import DetectionEvent, LineState, StationState
from cite_interfaces.qos import COMMAND, EVENT, STATE
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.node import Node
from std_msgs.msg import Float64

ZONE = "cell_a"

#: How many work-pieces have to traverse the line. The charter says "N"; three is
#: the smallest N that distinguishes "the line ran once" from "the line runs",
#: because the second piece exercises a station that has already cycled and the
#: third exercises the one after it. Overridable so a bring-up investigation can
#: ask for one piece without editing a test.
WORKPIECES = int(os.environ.get("CITE_LINE_WORKPIECES", "3"))

#: The reference work-piece, whose geometry `pick_and_place` uses and around whose
#: dimensions the beam offsets in `model/assets/instances/sensors.yaml` are
#: chosen. Its NAME is not written here — see `carried_models`.
WORKPIECE_SIZE = 0.05

#: Height above the pick surface the work-piece is released from: small enough to
#: settle immediately, large enough not to be spawned interpenetrating the table,
#: a penetration the physics engine resolves by launching it.
SPAWN_DROP_M = 0.005

#: Wall-clock ceilings, not schedules. Nothing is sequenced by them; they exist so
#: a stalled line fails the run with a diagnosis instead of blocking CI.
#:
#: Their basis: `pick_and_place` measures one station's pick-and-place cycle
#: against a ceiling of 420 s, chosen for a macOS development host whose measured
#: real-time factor is about 0.14. A milestone here is at most one such cycle, so
#: the same number is the right ceiling for one — and applying it per milestone
#: rather than per piece is deliberate: a line that stalls fails at the milestone
#: it stalled on, after one leg's worth of waiting, and the message names that
#: milestone instead of a whole piece's budget having quietly expired.
BRING_UP_CEILING_S = 300.0
LEG_CEILING_S = 420.0

#: How far the work-piece must rise above the frame it is picked from to count as
#: picked. Larger than settling or contact jitter, smaller than the retreat, so a
#: nudge cannot pass for a grasp. Same basis as `pick_and_place.LIFTED_M`.
LIFTED_M = 0.05

#: How far the work-piece's resting height may differ from a surface's and still
#: count as resting on it.
#:
#: The reasoning is `pick_and_place.PLACE_HEIGHT_TOLERANCE_M`'s, restated because
#: the two scenarios must be free to disagree: the widest legitimate resting pose
#: is a cube on a corner, which lifts its centre by 0.025 * (sqrt(3) - 1) =
#: 0.018 m, and 0.05 m clears that with margin while still rejecting, by an order
#: of magnitude, both a part still held in the air and a part that went over an
#: edge onto the floor. Every check that uses it is two-sided for exactly that
#: reason: too high means never released, too low means it did not stay on the
#: belt, and both keep the x and y of a correct placement.
SURFACE_TOLERANCE_M = 0.05

#: How far outside a belt's own footprint a work-piece may sit and still count as
#: on that belt. It absorbs the difference between the work-piece's origin and its
#: body: a cube whose centre is a little past the belt edge still rests on it.
BELT_MARGIN_M = WORKPIECE_SIZE

#: How far outside the span of the line's own frames the work-piece may travel
#: before it has left the cell. Generous, because this is a containment check and
#: not a placement one: its job is to catch a piece that was flung or dropped, not
#: to grade where a station put it.
CELL_MARGIN_M = 0.50

#: How far the work-piece may sit below the lowest of the line's transport
#: surfaces before it is no longer on any of them. A piece resting on a surface
#: has its centre half a cube above it, so anything below the surface itself is
#: unsupported; half a cube of slack absorbs contact penetration while a settling
#: constraint resolves. A piece on the floor is 0.575 m below this, which is not a
#: close call.
DROP_MARGIN_M = WORKPIECE_SIZE / 2.0

#: How often the work-piece's pose is sampled while the line runs.
#:
#: Chosen against the dwell time of the shortest thing sampled here, because the
#: opposite mistake is on record: a scenario that sampled at 4 s missed every
#: event it was written to observe, a part crossing a 0.040 m beam at 0.150 m/s
#: being inside it for 0.27 s of simulated time.
#:
#: Nothing here samples for an event that short. The beam crossings arrive as
#: `DetectionEvent`s on a keep-all subscription, which cannot miss one; what is
#: sampled is where the piece IS, and the briefest of those is `on_link` — a
#: 1.200 m belt at 0.150 m/s, so 8 s of simulated time, plus the margin at each
#: end. At the development host's measured real-time factor of 0.14 that is about
#: 57 s of wall clock and over a hundred samples; on a host running at 1.0 it is
#: still sixteen. Both are far from a coin toss, which is what the number has to
#: buy.
#:
#: Not faster, because each sample is a `gz model -p` — a process and a transport
#: node per sample — and there is nothing left to buy above the dwell times above.
#:
#: A CORRECTION, because the first version of this comment was wrong in a way
#: worth keeping visible. It said the simulator "started logging"
#: `NodeShared::RecvSrvRequest() error sending response: Host unreachable` at
#: 0.25 s, and blamed the rate. Measured across the change: 24 of 699 samples at
#: 0.25 s and 25 of 721 at 0.5 s — the same ~3.4% either way. The losses are a
#: property of spawning a short-lived transport node per sample, where the
#: response can arrive after the requester has exited, and they are not
#: rate-driven. So the rate change is justified by the dwell-time arithmetic
#: alone, and this instrument drops about one sample in thirty at any rate. That
#: is immaterial against the hundred-plus samples each measured milestone gets,
#: and it is recorded rather than left to be rediscovered.
SAMPLE_PERIOD_S = 0.5

#: How many containment breaches are quoted in full before the rest are counted.
#: A piece lying on the floor breaches on every sample, and quoting all of them
#: would bury the milestone the line stopped at under a thousand copies of one
#: fact. The assertion fires on the first; these are for the reader.
BREACHES_REPORTED = 3

#: The seed `./scripts/scenario` exports, recorded so that a report names the
#: conditions it was produced under. It does NOT make the run reproducible:
#: `gz sim --seed` calls `gz::math::Rand::Seed`, which covers sensor noise and the
#: transport RNG and neither the physics solver nor OMPL. See
#: `pick_and_place.SEED_VARIABLE`, ADR-0006 and ADR-0027.
SEED_VARIABLE = "CITE_PHYSICS_SEED"


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> LaunchDescription:
    """The whole cell, with the L4 coordinator running the line.

    `line:=true` is the difference from every other scenario. It is off by default
    because a running coordinator holds all three arms — `simulation.launch.py`
    says so where the argument is declared — and this is the one scenario that
    wants exactly that: nothing here commands an arm.
    """
    simulation = (
        Path(get_package_share_directory("cite_bringup")) / "launch" / "simulation.launch.py"
    )
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(simulation)),
                launch_arguments={
                    "headless": "true",
                    "zone": ZONE,
                    "line": "true",
                }.items(),
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


# -----------------------------------------------------------------------------
# The ladder, derived from the generated topology.
#
# Pure functions over generated artifacts, at module scope and free of ROS, so
# that `tests/scenarios/guards/` can exercise them in milliseconds without a
# simulator. `cross-cutting-testing.md` asks for exactly that: push the test down,
# and do not spend the scenario suite on what a unit test could have caught.
# -----------------------------------------------------------------------------


class Milestone(NamedTuple):
    """One step a work-piece must be observed to take.

    A `NamedTuple` and deliberately not a `@dataclass`: this module has
    `from __future__ import annotations`, and `launch_test` loads a scenario by
    path without registering it in `sys.modules`, which makes `@dataclass` raise
    at import time over a string annotation it cannot resolve. The full account is
    on `pick_and_place.CycleOutcome`, and `guards/test_scenario_modules_load.py`
    fails if a dataclass comes back.
    """

    #: `sensed` — a beam reported BLOCKED. `lifted` — the piece rose off the frame
    #: it is picked from. `on_link` — the piece came to rest on the belt it was
    #: placed onto. `arrived` — the sink's beam reported BLOCKED while the piece
    #: was measured on the last link, which is both halves of the charter's
    #: criterion in a single observation.
    kind: str
    #: The station this milestone belongs to, from the topology. For the report.
    station: str
    #: The TF frame it is measured about; empty for a purely sensed milestone.
    frame: str
    #: The `DetectionEvent` topic it waits on; empty for a measured milestone.
    topic: str
    #: The conveyor asset the piece is on; empty when there is none.
    link: str

    def describe(self) -> str:
        where = self.frame or self.topic or self.link
        return f"{self.kind}({self.station}: {where})"


def flow_order(topology: dict) -> list[dict]:
    """The stations, from source to sink, following the topology's own links.

    Derived by walking `downstream`, not by sorting on a name and not by reading
    the list in file order — the file is emitted alphabetically, which puts the
    sink first. A branch is refused rather than guessed at, because a branch means
    "which way did the piece go" has more than one answer and every milestone
    below assumes it has one.
    """
    stations = {station["id"]: station for station in topology["stations"]}
    sources = [s for s in stations.values() if not s.get("upstream")]
    if len(sources) != 1:
        raise ValueError(
            f"the flow has {len(sources)} station(s) with no upstream, and this scenario "
            "follows a single chain; a line that starts in more than one place needs a "
            "scenario that says which piece went which way"
        )

    order: list[dict] = []
    station = sources[0]
    seen: set[str] = set()
    while True:
        if station["id"] in seen:
            raise ValueError(f"the flow revisits {station['id']}; it is not a chain")
        seen.add(station["id"])
        order.append(station)
        downstream = station.get("downstream") or []
        if not downstream:
            break
        if len(downstream) != 1:
            raise ValueError(
                f"{station['id']} has {len(downstream)} downstream stations, and this "
                "scenario follows a single chain"
            )
        station = stations[downstream[0]]
    return order


def link_between(topology: dict, upstream: str, downstream: str) -> str:
    """The asset a piece is carried by between two stations; empty when handed over."""
    for edge in topology["edges"]:
        if edge["from"] == upstream and edge["to"] == downstream:
            return edge.get("via") or ""
    return ""


def milestones(topology: dict) -> tuple[Milestone, ...]:
    """What a single work-piece must be observed to do, in order.

    One entry per thing the topology says happens to a piece: a beam that gates a
    station reports before that station acts, the station's arm lifts the piece
    off the frame it picks from, and the piece comes to rest on the link it is
    placed onto. The sink contributes the last entry, which is its beam and the
    piece's measured position together.

    The result is the whole of what "the line ran" means here, and it contains no
    station name, no belt and no coordinate that this file wrote.
    """
    order = flow_order(topology)
    ladder: list[Milestone] = []
    for index, station in enumerate(order):
        topic = (station.get("trigger") or {}).get("topic", "")
        inbound = link_between(topology, order[index - 1]["id"], station["id"]) if index else ""

        if not station.get("actor"):
            # A source has nothing to observe and nothing to do. A sink has no
            # actor either, and its trigger is the arrival this ladder is built to
            # reach; a sink without one observes nothing and contributes nothing,
            # which is a gap in the model rather than something to invent here.
            if index and topic:
                ladder.append(Milestone("arrived", station["id"], "", topic, inbound))
            continue

        if topic:
            ladder.append(Milestone("sensed", station["id"], "", topic, inbound))
        ladder.append(Milestone("lifted", station["id"], station["pick_frame"], "", inbound))
        downstream = (station.get("downstream") or [""])[0]
        outbound = link_between(topology, station["id"], downstream)
        ladder.append(Milestone("on_link", station["id"], station["place_frame"], "", outbound))
    return tuple(ladder)


def _world_root(world: Path) -> ElementTree.Element:
    return ElementTree.parse(world).getroot()


def world_name(world: Path) -> str:
    """The Gazebo world's name, for the service that removes a finished piece."""
    element = _world_root(world).find("world")
    if element is None or not element.get("name"):
        raise ValueError(f"{world} declares no named <world>")
    return str(element.get("name"))


def carried_models(world: Path) -> frozenset[str]:
    """Every Gazebo model name the belts carry and the beams watch.

    Both plugins match this set EXACTLY — `carried_.count(name->Data())` in
    `conveyor.cpp`, `watched_.count(name->Data())` in `break_beam.cpp` — so a part
    spawned under any other name rides through the cell untouched and unseen. The
    intersection is taken rather than either list alone: a name a belt carries but
    no beam watches would move and never be reported, and a scenario that fed one
    would be testing a piece the line is blind to.
    """
    root = _world_root(world)
    carried = {element.text.strip() for element in root.iter("carry") if element.text}
    watched = {element.text.strip() for element in root.iter("watch") if element.text}
    return frozenset(carried & watched)


def belt_extents(world: Path) -> dict[str, tuple[float, float]]:
    """Each belt's length and width, keyed by the command topic that names it.

    Keyed by topic because that is the one identifier the plugin element carries
    which also appears in the bring-up plan, and the plan is what maps it back to
    an asset id. Deriving the asset from the topic string here would be composing
    a name this repository generates (CLAUDE.md §8).
    """
    extents: dict[str, tuple[float, float]] = {}
    for plugin in _world_root(world).iter("plugin"):
        topic = plugin.findtext("command_topic")
        length = plugin.findtext("belt_length_m")
        width = plugin.findtext("belt_width_m")
        if topic and length and width:
            extents[topic.strip()] = (float(length), float(width))
    return extents


class Sample(NamedTuple):
    """Where the work-piece was, and when, on the observer's WALL clock.

    Wall clock, deliberately, and it is the one place in this repository where
    that is the right answer. This node does not set `use_sim_time`, exactly as
    `bringup` and `pick_and_place` do not: an observer whose clock is the
    simulator's cannot time the simulator out, because a stalled `/clock` freezes
    every deadline and the run hangs for ever instead of failing with a diagnosis.
    Nothing under test reads this clock, and nothing is sequenced by it — every
    deadline it feeds is a failure deadline (P4). Every node the *system* starts
    honours `use_sim_time`; `simulation.launch.py` passes it to all of them.
    """

    seconds: float
    x: float
    y: float
    z: float

    def describe(self) -> str:
        return f"t={self.seconds:.1f}s ({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"


class Beam(NamedTuple):
    """A beam reporting that its volume became occupied."""

    topic: str
    seconds: float


class Fault(NamedTuple):
    """A station the coordinator reported as faulted, and the reason it gave."""

    station: str
    reason: str


class Journey(NamedTuple):
    """What one work-piece was observed to do."""

    piece: int
    reached: tuple[str, ...]
    breaches: tuple[str, ...]


# -----------------------------------------------------------------------------
# The scenario
# -----------------------------------------------------------------------------


class TestContinuousLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.node = Node("scenario_continuous_line")
        cls.seed = os.environ.get(SEED_VARIABLE, "unset")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.destroy_node()
        rclpy.shutdown()

    def setUp(self) -> None:
        self.workpiece = ""
        self.world = ""
        self.root_frame = "cite_world"
        self._frames: dict[str, tuple[float, float, float]] = {}
        self._belts: dict[str, tuple[float, float]] = {}
        self._beams: list[Beam] = []
        self._faults: list[Fault] = []
        self._line_states: list[LineState] = []
        self._samples: list[Sample] = []
        self._subscriptions: list[object] = []
        #: `belt asset -> the fastest setpoint anything was seen commanding it to`.
        #: Read only, and by exactly one writer: L4 (ADR-0032).
        self._belt_setpoints: dict[str, float] = {}
        #: Where in `_beams` the current work-piece's own events start. Without it
        #: the second piece inherits the first piece's beam reports and every
        #: sensed milestone is satisfied before it has moved.
        self._beams_from = 0
        self._span_x = (0.0, 0.0)
        self._lowest_surface_z: float | None = None

    # -- waiting, measuring, resolving ----------------------------------------

    def _now(self) -> float:
        return self.node.get_clock().now().nanoseconds / 1e9

    def _spin_until(self, predicate, ceiling_s: float, what: str):
        """Spin until `predicate` answers with something other than None, or fail.

        `is not None` rather than truthiness, for the reason `pick_and_place`
        gives: a measurement of exactly 0.0 is a good answer, and reading it as
        "not ready yet" produces a timeout that accuses the wrong component.
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

        Read from Gazebo rather than from anything the system publishes: a
        component reporting success proves only that it thinks so, and the claim
        under test is that an object physically moved. `gz model -p` prints the
        pose as bracketed, space-separated triples, position first.
        """
        result = subprocess.run(
            ["gz", "model", "-m", self.workpiece, "-p"],
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

    def _resolve(self, frame: str) -> tuple[float, float, float]:
        """Where a generated frame is, in the facility root, according to the system."""
        if frame in self._frames:
            return self._frames[frame]
        transform = self._spin_until(
            lambda: (
                self._buffer.lookup_transform(self.root_frame, frame, rclpy.time.Time())
                if self._buffer.can_transform(self.root_frame, frame, rclpy.time.Time())
                else None
            ),
            BRING_UP_CEILING_S,
            f"a transform from {self.root_frame} to {frame}",
        )
        translation = transform.transform.translation
        self._frames[frame] = (translation.x, translation.y, translation.z)
        return self._frames[frame]

    # -- milestone predicates, all measured or subscribed ---------------------

    def _sensed(self, topic: str) -> bool:
        return any(beam.topic == topic for beam in self._beams[self._beams_from :])

    def _resting_on(self, sample: Sample, surface_z: float) -> bool:
        """Is the piece sitting on a surface at `surface_z`, rather than above or below it?

        Two-sided, and that is the whole value of it. `pick_and_place` records the
        run this catches: a part welded to a gripper finger half a metre above the
        target passed every horizontal check for months, and so would a part that
        slid off the belt onto the floor, because both keep the x and y of a
        correct placement.
        """
        return abs(sample.z - (surface_z + WORKPIECE_SIZE / 2.0)) < SURFACE_TOLERANCE_M

    def _on_link(self, sample: Sample, link: str) -> bool:
        """Is the piece resting on that belt, anywhere along it?

        Along the whole belt rather than at the place frame, deliberately. The
        belts run, so a piece placed at an infeed is carried away from it within a
        second of simulated time, and a milestone pinned to the infeed point would
        be a race between the sampler and the belt. "It got onto the belt" is the
        outcome the topology cares about, and it still rejects the failure that
        matters most here: a piece released short of the leading edge lands on the
        floor rather than on the belt, and the height half of this check sees that.
        """
        if not link:
            return False
        centre = self._resolve(f"{ZONE}__{link}__surface")
        length, width = self._belts[link]
        return (
            self._resting_on(sample, centre[2])
            and abs(sample.x - centre[0]) <= length / 2.0 + BELT_MARGIN_M
            and abs(sample.y - centre[1]) <= width / 2.0 + BELT_MARGIN_M
        )

    def _reached(self, milestone: Milestone, sample: Sample | None) -> bool:
        if milestone.kind == "sensed":
            return self._sensed(milestone.topic)
        if sample is None:
            return False
        if milestone.kind == "lifted":
            return sample.z - self._resolve(milestone.frame)[2] > LIFTED_M
        if milestone.kind == "on_link":
            return self._on_link(sample, milestone.link)
        if milestone.kind == "arrived":
            # Both halves at once: the sink's beam has reported, and the piece is
            # measurably on the last link while it does. The beam alone is a fact
            # about a beam — the same class of mistake as reading a belt's `state`
            # topic, which republishes the command it was handed and measures
            # nothing.
            return self._sensed(milestone.topic) and self._on_link(sample, milestone.link)
        raise AssertionError(f"unknown milestone kind {milestone.kind!r}")

    def _within_the_cell(self, sample: Sample) -> str:
        """Empty when the piece is where a work-piece may be; the complaint otherwise.

        The envelope comes from the frames the ladder already names and the belts
        it rides, all placed by TF. Nothing is written here, so a layout change
        moves this check with the cell.
        """
        if self._lowest_surface_z is None:
            return ""
        if sample.z < self._lowest_surface_z - DROP_MARGIN_M:
            return (
                "fell below every transport surface in the line "
                f"(z={sample.z:.3f} m against a lowest surface at "
                f"{self._lowest_surface_z:.3f} m) at {sample.describe()}"
            )
        if not self._span_x[0] - CELL_MARGIN_M <= sample.x <= self._span_x[1] + CELL_MARGIN_M:
            return (
                f"left the cell along x (x={sample.x:.3f} m against a line spanning "
                f"{self._span_x[0]:.3f}..{self._span_x[1]:.3f} m) at {sample.describe()}"
            )
        return ""

    # -- the run --------------------------------------------------------------

    def test_the_line_carries_every_workpiece_from_pick_to_accumulation(self) -> None:
        import tf2_ros
        from cite_bringup.plan import default_plan_path, load

        plan = load(default_plan_path(ZONE))
        topology = yaml.safe_load(Path(plan.topology).read_text())["topology"]
        ladder = milestones(topology)
        self.assertTrue(ladder, "the generated topology yields no milestones to observe")
        self.assertEqual(
            ladder[-1].kind,
            "arrived",
            f"the ladder ends at {ladder[-1].describe()} rather than at an arrival. The "
            "sink's own trigger is what makes an arrival observed instead of inferred; "
            "without it this scenario would be asserting that a robot let go.",
        )

        # 1. The one work-piece name the simulation aids act on. Asserted, not
        #    assumed: this is what forces the pieces through the line one at a
        #    time, and the day the model declares a second name this fails and
        #    says so rather than quietly testing a serial line for ever.
        names = carried_models(Path(plan.world))
        self.assertEqual(
            len(names),
            1,
            f"the generated world declares {sorted(names)} as both carried and watched. "
            "This scenario feeds one piece at a time because a Gazebo model name is "
            "unique and the belt and beam plugins match it exactly, so one declared name "
            "means one piece can be on the line at all. More than one name means the line "
            "can be driven concurrently and this scenario should be — that is a rewrite, "
            "not a wider tolerance.",
        )
        self.workpiece = next(iter(names))
        self.world = world_name(Path(plan.world))

        # 2. Belt footprints, from the generated world, keyed back to assets
        #    through the bring-up plan the launch file reads.
        extents = belt_extents(Path(plan.world))
        self._belts = {
            conveyor.asset: extents[conveyor.command_topic]
            for conveyor in plan.conveyors
            if conveyor.command_topic in extents
        }
        self.assertEqual(
            len(self._belts),
            len(plan.conveyors),
            f"the plan declares {len(plan.conveyors)} conveyor(s) and the generated world "
            f"describes {len(self._belts)} of them by command topic; the two disagree "
            "about what this cell has",
        )

        # 3. Listen before anything moves. A subscriber created after the event it
        #    waits for has missed it, and the EVENT profile is keep-all precisely
        #    so that a connected reader gets every transition rather than the
        #    latest level.
        for topic in sorted({m.topic for m in ladder if m.topic}):
            self._subscriptions.append(
                self.node.create_subscription(
                    DetectionEvent,
                    topic,
                    lambda message, topic=topic: self._on_detection(topic, message),
                    EVENT,
                )
            )
        self._subscriptions.append(
            self.node.create_subscription(LineState, LineState.TOPIC, self._on_line_state, STATE)
        )
        # The belt setpoints, read and never written (ADR-0032). Subscribed HERE,
        # with the rest of the listeners and before the wait for the first
        # `LineState` below, because `run_all()` publishes once and does it before
        # the coordinator's first tick — so a subscriber created at step 6 would
        # have missed the very message it is looking for.
        for conveyor in plan.conveyors:
            self._subscriptions.append(
                self.node.create_subscription(
                    Float64,
                    conveyor.command_topic,
                    lambda message, asset=conveyor.asset: self._on_belt_command(asset, message),
                    COMMAND,
                )
            )

        self._buffer = tf2_ros.Buffer()
        # Held on the instance: a listener that goes out of scope stops filling
        # the buffer, and every later lookup fails for a reason that has nothing
        # to do with the frames it names.
        self._listener = tf2_ros.TransformListener(self._buffer, self.node)

        # 4. The coordinator is the last thing bring-up starts and the only thing
        #    that publishes `LineState`, so a state message means the whole stack
        #    beneath it came up. Waiting on the message rather than on a process is
        #    the P4 half of this: nothing here sleeps for a guessed duration.
        self._spin_until(
            lambda: self._line_states[-1] if self._line_states else None,
            BRING_UP_CEILING_S,
            "the first LineState, and so the line coordinator and the stack below it",
        )

        # 5. The cell's envelope, from the frames the ladder names and the belts it
        #    rides, now that TF is filling.
        self._resolve_envelope(ladder)

        # 6. The belts are running, because L4 started them.
        self._assert_the_line_started_the_belts(plan)

        # 7. Feed the line, one piece at a time, and follow each one.
        journeys: list[Journey] = []
        for piece in range(1, WORKPIECES + 1):
            journey = self._run_one_piece(piece, ladder)
            journeys.append(journey)
            self._remove_workpiece()
            if len(journey.reached) != len(ladder):
                # A stalled line does not recover by being given another part, and
                # feeding the rest would spend an hour proving it. What was not fed
                # is named in the report rather than left as a silent short count.
                break

        # 8. The verdict, in three parts.
        context = self._context(ladder, journeys)
        complete = [len(journey.reached) == len(ladder) for journey in journeys]
        self.assertEqual(
            (sum(complete), len(complete)),
            (WORKPIECES, WORKPIECES),
            f"{sum(complete)} of {WORKPIECES} work-piece(s) traversed the line.\n{context}",
        )
        breaches = [b for journey in journeys for b in journey.breaches]
        self.assertEqual(
            breaches,
            [],
            "the work-piece left the cell's working volume:\n  "
            + "\n  ".join(breaches)
            + f"\n{context}",
        )
        self.assertEqual(
            self._faults,
            [],
            "the coordinator reported a faulted station, which is how an unrecoverable "
            "skill failure — a planning refusal against the collision scene included — "
            "reaches this scenario:\n  "
            + "\n  ".join(f"{fault.station}: {fault.reason}" for fault in self._faults)
            + f"\n{context}",
        )

    # -- the pieces of the run ------------------------------------------------

    def _on_detection(self, topic: str, message: DetectionEvent) -> None:
        if message.state == DetectionEvent.STATE_BLOCKED:
            self._beams.append(Beam(topic, self._now()))

    def _on_line_state(self, message: LineState) -> None:
        self._line_states.append(message)
        for station in message.stations:
            if station.state != StationState.STATE_FAULTED:
                continue
            if any(fault.station == station.station_id for fault in self._faults):
                continue
            self._faults.append(Fault(station.station_id, message.blocked_reason))

    def _resolve_envelope(self, ladder: tuple[Milestone, ...]) -> None:
        """Fix the cell's boundary from the frames the ladder names and the belts it rides.

        Every value comes from TF, so the envelope moves with the layout. It is
        computed once, before the first piece is fed, because a boundary that
        widened as the run went on would stop being a boundary.
        """
        heights: list[float] = []
        edges: list[float] = []
        for frame in [m.frame for m in ladder if m.frame]:
            position = self._resolve(frame)
            heights.append(position[2])
            edges.append(position[0])
        for link, (length, _) in self._belts.items():
            centre = self._resolve(f"{ZONE}__{link}__surface")
            heights.append(centre[2])
            edges += [centre[0] - length / 2.0, centre[0] + length / 2.0]
        self.assertTrue(heights, "no frame in the ladder or the belt set could be placed by TF")
        self._span_x = (min(edges), max(edges))
        self._lowest_surface_z = min(heights)

    def _on_belt_command(self, asset: str, message: Float64) -> None:
        self._belt_setpoints[asset] = max(self._belt_setpoints.get(asset, 0.0), message.data)

    def _assert_the_line_started_the_belts(self, plan) -> None:
        """The belts run because L4 ran them, and this scenario writes nothing.

        THIS USED TO PUBLISH. `line_orchestrator` commanded no conveyor, the model
        says the runtime setpoint is L4's decision rather than L0's, and so the
        setpoint had no owner and the scenario supplied it — a gap, reported as
        one. ADR-0032 gave it an owner: `ConveyorIndex::run_all` is called once at
        bring-up, and the same object stops a belt on its station's trigger edge
        and runs it again on `CompleteHandoff`.

        Publishing here after that is not a leftover, it is a SECOND WRITER on a
        command topic with one owner. Nothing arbitrates two publishers of a
        setpoint: whichever message arrives last wins, so a belt L4 had just
        stopped for a station to pick from could be restarted by a test harness,
        and the work-piece would ride past the pick point while every assertion
        in this file still passed. The right thing for a scenario to do with a
        topic the system owns is read it.

        So this reads it. A non-zero setpoint on every declared belt, observed
        rather than assumed, is what says the owner exists and did its job — and
        it is the check that fails if `run_all()` is ever removed, which is
        exactly the state the deleted publisher was hiding.
        """
        # `True` or `None`, never `False`: `_spin_until` waits on `is not None`,
        # so a predicate that answered `False` would be read as a good answer and
        # would return on the first call having waited for nothing.
        self._spin_until(
            lambda: True
            if all(
                self._belt_setpoints.get(conveyor.asset, 0.0) > 0.0 for conveyor in plan.conveyors
            )
            else None,
            BRING_UP_CEILING_S,
            "L4 to command every belt to a non-zero setpoint (ADR-0032). Nothing "
            "else publishes one: if this times out, either `run_all()` no longer "
            "runs at bring-up or the coordinator never reached it",
        )
        for conveyor in plan.conveyors:
            self.assertAlmostEqual(
                self._belt_setpoints[conveyor.asset],
                conveyor.installed_speed_mps,
                places=6,
                msg=f"L4 commanded '{conveyor.asset}' to "
                f"{self._belt_setpoints[conveyor.asset]} m/s against the "
                f"{conveyor.installed_speed_mps} m/s its drive is installed at. The "
                "setpoint is L4's decision and the installed speed is the model's; a "
                "disagreement is a number invented somewhere between them",
            )

    def _spawn_workpiece(self, at: tuple[float, float, float]) -> None:
        sdf_path = Path(f"/tmp/cite_{self.workpiece}.sdf")
        sdf_path.write_text(_workpiece_sdf(self.workpiece))
        created = subprocess.run(
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
                str(at[0]),
                "-y",
                str(at[1]),
                "-z",
                str(at[2]),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        try:
            self._spin_until(
                lambda: self._workpiece_xyz(),
                LEG_CEILING_S,
                f"the work-piece '{self.workpiece}' to settle on the pick surface",
            )
        except AssertionError as exc:
            # A missing work-piece is a setup failure, not a result. Say which,
            # with the evidence, rather than leaving the reader to decide whether
            # the line failed or the part was never there.
            listing = subprocess.run(
                ["gz", "model", "--list"], capture_output=True, text=True, timeout=30
            )
            raise AssertionError(
                f"{exc}\n--- create stdout ---\n{created.stdout[-2000:]}\n"
                f"--- create stderr ---\n{created.stderr[-2000:]}\n"
                f"--- gz model --list (rc={listing.returncode}) ---\n{listing.stdout[-2000:]}"
            ) from exc

    def _remove_workpiece(self) -> None:
        """Take the finished piece off the line so the next one can be fed.

        The sink end of a real line is emptied; here it also has to be, because a
        Gazebo model name is unique and the belts and beams act only on the one
        name the model declares. Waited on as a condition — the piece is gone when
        the simulator stops reporting a pose for it — rather than slept on.
        """
        subprocess.run(
            [
                "gz",
                "service",
                "-s",
                f"/world/{self.world}/remove",
                "--reqtype",
                "gz.msgs.Entity",
                "--reptype",
                "gz.msgs.Boolean",
                "--timeout",
                "5000",
                "--req",
                f'name: "{self.workpiece}" type: MODEL',
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self._spin_until(
            lambda: True if self._workpiece_xyz() is None else None,
            LEG_CEILING_S,
            f"the work-piece '{self.workpiece}' to leave the simulator",
        )

    def _run_one_piece(self, piece: int, ladder: tuple[Milestone, ...]) -> Journey:
        """Feed one work-piece and follow it up the ladder.

        It does NOT assert. A piece that stalls returns what it managed, and the
        verdict is taken once at the end over every piece, so the report names the
        milestone the line stopped at rather than whichever assertion fired first.
        """
        lifts = [m for m in ladder if m.kind == "lifted"]
        self.assertTrue(lifts, "no station in the topology picks anything up")
        pick = self._resolve(lifts[0].frame)
        self._beams_from = len(self._beams)
        self._spawn_workpiece((pick[0], pick[1], pick[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M))

        reached: list[str] = []
        breaches: list[str] = []
        breached = 0
        for milestone in ladder:
            deadline = self.node.get_clock().now().nanoseconds + int(LEG_CEILING_S * 1e9)
            hit = False
            while self.node.get_clock().now().nanoseconds < deadline:
                rclpy.spin_once(self.node, timeout_sec=SAMPLE_PERIOD_S)
                position = self._workpiece_xyz()
                sample = Sample(self._now(), *position) if position is not None else None
                if sample is not None:
                    self._samples.append(sample)
                    breach = self._within_the_cell(sample)
                    if breach:
                        breached += 1
                        # The first few, and then a count. Every sample of a piece
                        # lying on the floor is a distinct breach message, and
                        # recording all of them would bury the milestone the line
                        # actually stopped at under a thousand lines of the same
                        # fact. The assertion fires on one.
                        if len(breaches) < BREACHES_REPORTED:
                            breaches.append(
                                f"piece {piece}, while waiting for "
                                f"{milestone.describe()}: {breach}"
                            )
                if self._reached(milestone, sample):
                    hit = True
                    break
            if not hit:
                break
            reached.append(milestone.describe())
        if breached > len(breaches):
            breaches.append(f"piece {piece}: and {breached - len(breaches)} further sample(s)")
        return Journey(piece, tuple(reached), tuple(breaches))

    def _context(self, ladder: tuple[Milestone, ...], journeys: list[Journey]) -> str:
        """Everything a reader needs in order to say where the line stopped."""
        lines = [
            f"seed={self.seed} (reaches `gz sim --seed` only, which seeds neither the "
            "physics solver nor OMPL — this run is not reproducible)",
            f"work-piece model '{self.workpiece}' in world '{self.world}'",
            f"the ladder the generated topology defines, {len(ladder)} milestone(s):",
        ]
        lines += [f"  {index + 1}. {m.describe()}" for index, m in enumerate(ladder)]
        for journey in journeys:
            if len(journey.reached) == len(ladder):
                lines.append(f"piece {journey.piece}: complete, {len(ladder)}/{len(ladder)}")
                continue
            lines.append(
                f"piece {journey.piece}: STOPPED after {len(journey.reached)}/{len(ladder)} "
                f"milestones, waiting on {ladder[len(journey.reached)].describe()} for "
                f"{LEG_CEILING_S:.0f}s"
            )
        if len(journeys) < WORKPIECES:
            lines.append(
                f"pieces {len(journeys) + 1}..{WORKPIECES} were not fed: the line had "
                "already stalled, and another part does not restart it"
            )
        lines.append(
            "beams that reported BLOCKED: "
            + (", ".join(f"{b.topic}@{b.seconds:.1f}s" for b in self._beams) or "none")
        )
        if self._line_states:
            last = self._line_states[-1]
            lines.append(
                f"last LineState: state={last.state} "
                f"workpieces_completed={last.workpieces_completed} (counted when the last "
                "robot LET GO, not on arrival — see line_maintenance.hpp; context only, "
                "never asserted on) "
                f"blocked_reason={last.blocked_reason or 'none'}"
            )
            lines += [
                f"  station {s.station_id} ({s.actor_asset_id or 'no actor'}): "
                f"state={s.state} occupancy={s.buffer_occupancy}/{s.buffer_capacity} "
                f"workpiece={s.current_workpiece_id or 'none'}"
                for s in last.stations
            ]
        else:
            lines.append("no LineState was ever received")
        if self._samples:
            furthest = max(self._samples, key=lambda s: s.x)
            highest = max(self._samples, key=lambda s: s.z)
            lines.append(
                f"work-piece samples: {len(self._samples)}, furthest {furthest.describe()}, "
                f"highest {highest.describe()}, last {self._samples[-1].describe()}"
            )
        else:
            lines.append("the work-piece was never located in the simulator")
        return "\n".join(lines)


def _workpiece_sdf(name: str) -> str:
    """A plain box, named as the generated world says the belts carry.

    Its inertia is computed rather than guessed — a wrong tensor makes the pick
    behave oddly for reasons that look like a controller fault (L1) — and `<mu>`
    is the only thing holding the part once it is grasped: the grasp is friction,
    measured over 84 trials in `docs/measurements/2026-08-25-friction-grasp/`.
    """
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


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    #: See the same exemption in `bringup.py` for the measurement behind it and
    #: for why it is weak: move_group segfaults inside its own destructor —
    #: SIGSEGV in `rclcpp::CallbackGroup::~CallbackGroup` from
    #: `MoveItCpp::~MoveItCpp` — which a raised `sigterm_timeout` isolated at -11
    #: on 3/3 runs with no SIGTERM escalation. It is upstream, not a race of ours.
    #:
    #: Kept exactly this wide: one signal, one process name. This scenario runs
    #: longer than `pick_and_place`, and the -9/-15 family `bringup.py`
    #: characterises correlates with run DURATION rather than with process
    #: identity, so it will be met here more often. That is a reason to report the
    #: rate, not a reason to widen the list: an assertion that tolerates every
    #: signal a contended machine produces is an assertion that cannot fail.
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
