"""Guard: the continuous-line scenario derives the right line, and can still fail.

`continuous_line` decides Phase 1.D, so two things about it have to be true
before a simulator is worth starting.

**It must describe the line the model describes.** The ladder of milestones a
work-piece has to climb is derived from the generated process topology rather
than written down, which is the property that keeps a layout change from becoming
a test change. Derivation has its own failure mode: a walk that quietly returns a
short chain would produce a scenario that passes having watched a piece move one
station. Everything under "the ladder" below is that check, and it runs against
the real generated artifact.

**Its measurements must still reject the runs they were written for.** The
arithmetic is `pick_and_place`'s, and the run it exists to catch is recorded in
`test_place_assertion_sees_height.py`: a part welded to a gripper finger, half a
metre in the air, directly over the target, which passed every horizontal check
for months. A part that slid onto the floor is the same measurement in two
dimensions. Both are rejected here in milliseconds rather than in minutes of
simulation.

Nothing here writes a coordinate. Frames come from the generated static transform
table and the flow from the generated topology — the same artifacts the scenario
resolves through TF at run time (P1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from test_scenario_modules_load import (  # the loader `launch_test` itself uses
    SCENARIO_DIR,
    _load_like_launch_test,
    _ros_stubs,
)

GENERATED = Path(__file__).resolve().parents[3] / "workspace" / "src" / "cite_generated"

#: The generated process topology for the cell the scenario drives, and the
#: generated static transform table. Read as plain YAML rather than through ROS:
#: this suite is deliberately ROS-free, and both files are produced from the L0
#: model (ADR-0021), so reading them duplicates no value.
TOPOLOGY = GENERATED / "topology" / "cell_a_flow.yaml"
STATIC_TF = GENERATED / "frames" / "cell_a_static_tf.yaml"
WORLD = GENERATED / "worlds" / "cell_a.sdf"

#: Where the work-piece was measured at the pre-ADR-0029 baseline, in metres. A
#: recorded observation of one broken run and NOT a layout value: it is never used
#: as a coordinate, only as the input the assertion under test has to reject.
BASELINE_HELD_Z_M = 1.201

#: Contact jitter and the last millimetres of settling, in metres.
SETTLING_JITTER_M = 0.005


@pytest.fixture(scope="module")
def scenario():
    """`continuous_line` loaded the way `launch_test` loads it, with ROS stubbed."""
    with _ros_stubs():
        return _load_like_launch_test(SCENARIO_DIR / "continuous_line.py")


@pytest.fixture(scope="module")
def topology() -> dict:
    assert TOPOLOGY.is_file(), f"{TOPOLOGY} is missing; it is generated from the L0 model"
    return dict(yaml.safe_load(TOPOLOGY.read_text())["topology"])


@pytest.fixture(scope="module")
def ladder(scenario, topology: dict) -> tuple:
    return tuple(scenario.milestones(topology))


# -----------------------------------------------------------------------------
# The ladder
# -----------------------------------------------------------------------------


def test_the_walk_visits_every_station_exactly_once(scenario, topology: dict) -> None:
    """A chain walk that stopped early would produce a scenario that ends early."""
    order = scenario.flow_order(topology)
    visited = [station["id"] for station in order]
    assert len(visited) == len(topology["stations"]), (
        f"the walk from the source reached {len(visited)} of {len(topology['stations'])} "
        f"stations ({visited}). A short walk yields a short ladder, and the scenario would "
        "then pass having watched a work-piece cross part of the line."
    )
    assert len(set(visited)) == len(visited), f"the walk revisits a station: {visited}"


def test_the_walk_starts_at_the_source_and_ends_at_the_sink(scenario, topology: dict) -> None:
    order = scenario.flow_order(topology)
    assert not order[0].get("upstream"), f"{order[0]['id']} is not a source"
    assert not order[-1].get("downstream"), f"{order[-1]['id']} is not a sink"


def test_every_station_that_acts_contributes_a_pick_and_a_place(scenario, topology: dict) -> None:
    """Every arm in the flow has to be observed doing both halves of its job.

    The failure this rejects is a ladder that watches the first station and the
    last one: a piece that is picked at one end and appears at the other has told
    you nothing about the stations in between, which is the whole of what a *line*
    adds to a cycle.
    """
    ladder = scenario.milestones(topology)
    actors = [s["id"] for s in scenario.flow_order(topology) if s.get("actor")]
    for station in actors:
        kinds = {m.kind for m in ladder if m.station == station}
        assert {"lifted", "on_link"} <= kinds, (
            f"{station} has an actor and contributes {sorted(kinds)}; a station that is "
            "not observed both lifting and delivering is a station the scenario does not "
            "actually test"
        )


def test_every_declared_trigger_is_waited_on(scenario, topology: dict) -> None:
    """ "Sensor-triggered" is the charter's word, and this is what makes it measured.

    Every trigger the topology declares must appear in the ladder as something the
    scenario waits for. A trigger that no milestone watches is a beam the line
    could ignore entirely while the scenario reported success.
    """
    ladder = scenario.milestones(topology)
    declared = {
        station["id"]: station["trigger"]["topic"]
        for station in topology["stations"]
        if station.get("trigger")
    }
    waited = {m.station: m.topic for m in ladder if m.topic}
    assert waited == declared, (
        f"the ladder waits on {waited} and the topology declares {declared}. A declared "
        "trigger nothing waits on is a sensor the line could be ignoring."
    )


def test_the_ladder_ends_at_an_observed_arrival(scenario, topology: dict) -> None:
    """The last milestone is the sink's own beam, not a robot letting go.

    `line_maintenance.hpp` counts a work-piece as complete when the upstream robot
    releases it, because for a long time the model gave the sink nothing to
    observe with. The sink has a trigger now, and the scenario's last milestone is
    that trigger together with a measurement of where the piece is. If this ever
    fails, the scenario has gone back to asserting on an inference.
    """
    ladder = scenario.milestones(topology)
    assert ladder[-1].kind == "arrived", (
        f"the ladder ends at {ladder[-1].describe()}; an arrival that is not observed by "
        "the sink's own sensor is an inference about a gripper"
    )
    assert ladder[-1].topic, "the arrival milestone waits on no topic"
    assert ladder[-1].link, (
        "the arrival milestone names no link, so the scenario cannot measure where the "
        "piece was when the beam reported, and the beam alone is a fact about a beam"
    )


def test_a_broken_flow_is_refused_rather_than_walked(scenario, topology: dict) -> None:
    """A topology that is not a chain fails loudly instead of yielding half a line."""
    forked = {
        "stations": [dict(station) for station in topology["stations"]],
        "edges": list(topology["edges"]),
    }
    for station in forked["stations"]:
        if len(station.get("downstream") or []) == 1:
            station["downstream"] = [*station["downstream"], "somewhere_else"]
            break
    with pytest.raises(ValueError, match="single chain"):
        scenario.flow_order(forked)


def test_every_milestone_frame_exists_in_the_generated_transform_table(ladder) -> None:
    """A frame the ladder names that TF cannot place is a scenario that hangs.

    It would hang for `BRING_UP_CEILING_S` and then blame TF, which is a diagnosis
    pointing at the transform table rather than at the topology that named a frame
    the table does not carry. Checked here in milliseconds instead.
    """
    table = yaml.safe_load(STATIC_TF.read_text())["static_transforms"]
    published = {entry["child"] for entry in table}
    named = {m.frame for m in ladder if m.frame}
    assert named <= published, (
        f"the ladder names {sorted(named - published)}, which the generated static "
        f"transform table does not publish"
    )


# -----------------------------------------------------------------------------
# One piece at a time, and why
# -----------------------------------------------------------------------------


def test_the_world_declares_exactly_one_workpiece_name(scenario) -> None:
    """The tripwire on the scenario's serial structure.

    `conveyor.cpp` and `break_beam.cpp` match a Gazebo model name exactly, and a
    Gazebo model name is unique, so one declared name means one work-piece can be
    on the line at a time — which is why the scenario feeds them one at a time and
    empties the sink between them.

    When the model declares a second name this fails, and the fix is to rewrite
    the scenario to run pieces concurrently, not to widen anything. A continuous
    line whose pieces never overlap is the weaker of the two claims, and the
    scenario should stop making it as soon as the aids allow.
    """
    names = scenario.carried_models(WORLD)
    assert len(names) == 1, (
        f"the generated world declares {sorted(names)} as both carried and watched. The "
        "scenario's one-piece-at-a-time structure exists only because there was one "
        "name; with more, it should drive them concurrently."
    )


def test_the_belts_are_all_described_by_the_world(scenario) -> None:
    """Every belt the scenario measures against has a footprint to measure against."""
    extents = scenario.belt_extents(WORLD)
    assert extents, f"{WORLD.name} describes no conveyor plugin with a command topic"
    for topic, (length, width) in extents.items():
        assert length > 0 and width > 0, f"{topic} has a non-positive footprint"


# -----------------------------------------------------------------------------
# The measurements still reject the runs they were written for
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def belt_z() -> float:
    """A belt surface's height, from the generated transform table."""
    table = yaml.safe_load(STATIC_TF.read_text())["static_transforms"]
    for entry in table:
        if entry["child"].endswith("__conveyor_1__surface"):
            return float(entry["xyz_m"][2])
    pytest.fail(f"no conveyor surface frame in {STATIC_TF.name}")


def _resting_z(scenario, surface_z: float) -> float:
    return surface_z + scenario.WORKPIECE_SIZE / 2.0


def test_a_settled_workpiece_is_accepted(scenario, belt_z: float) -> None:
    resting = _resting_z(scenario, belt_z)
    for sample in (resting, resting + SETTLING_JITTER_M, resting - SETTLING_JITTER_M):
        assert abs(sample - resting) < scenario.SURFACE_TOLERANCE_M, (
            f"a work-piece resting at {sample:.4f} m would be rejected against an expected "
            f"{resting:.4f} m; the scenario would fail a line that worked"
        )


def test_settling_on_a_corner_is_still_accepted(scenario, belt_z: float) -> None:
    """The widest legitimate resting pose, which is what sets the tolerance."""
    half_edge = scenario.WORKPIECE_SIZE / 2.0
    error = half_edge * (3.0**0.5 - 1.0)
    assert error < scenario.SURFACE_TOLERANCE_M, (
        f"a cube resting on a corner sits {error:.4f} m high and would be rejected by "
        f"SURFACE_TOLERANCE_M={scenario.SURFACE_TOLERANCE_M}"
    )


def test_a_part_still_held_in_the_air_is_rejected(scenario, belt_z: float) -> None:
    """The regression: the run that used to pass."""
    resting = _resting_z(scenario, belt_z)
    assert abs(BASELINE_HELD_Z_M - resting) >= scenario.SURFACE_TOLERANCE_M, (
        f"the pre-ADR-0029 baseline height {BASELINE_HELD_Z_M} m is within "
        f"SURFACE_TOLERANCE_M of the resting height {resting:.3f} m, so a piece that was "
        "never released would count as delivered to the belt"
    )


def test_a_part_that_fell_off_the_belt_is_rejected(scenario, belt_z: float) -> None:
    """The other half of the two-sided check."""
    on_the_floor = scenario.WORKPIECE_SIZE / 2.0
    assert abs(on_the_floor - _resting_z(scenario, belt_z)) >= scenario.SURFACE_TOLERANCE_M, (
        "a part on the floor is within tolerance of the belt height; the height check "
        "must be two-sided to reject it"
    )


def test_the_containment_check_sees_a_dropped_piece(scenario, belt_z: float) -> None:
    """A piece on the floor breaches the cell envelope as well as the surface check.

    Two independent assertions catch the same failure on purpose. The milestone
    check can only fire while the scenario is waiting for that milestone; the
    containment check runs on every sample, so a piece dropped between two
    stations is caught even where no milestone was watching for it.
    """
    on_the_floor = scenario.WORKPIECE_SIZE / 2.0
    assert on_the_floor < belt_z - scenario.DROP_MARGIN_M, (
        f"a part on the floor at z={on_the_floor:.3f} m is not below the containment "
        f"floor of {belt_z - scenario.DROP_MARGIN_M:.3f} m; the envelope check cannot see "
        "a dropped piece"
    )


def test_a_carried_piece_does_not_breach_containment(scenario, belt_z: float) -> None:
    """The check must not fire on a work-piece being carried between stations.

    An envelope that a normal cycle violates is an envelope that gets widened
    until it means nothing. A piece in the gripper is ABOVE the surfaces, and the
    floor of this check is below them, so the whole of a legitimate cycle is
    inside it.
    """
    lifted = _resting_z(scenario, belt_z) + scenario.LIFTED_M
    assert lifted > belt_z - scenario.DROP_MARGIN_M, (
        "a lifted work-piece would breach the containment floor, so every successful pick "
        "would be reported as a piece that left the cell"
    )


def test_the_scenario_still_asserts_on_height_and_containment() -> None:
    """The tripwire for an assertion being deleted while its constant survives.

    Everything above tests arithmetic over the scenario's constants. If somebody
    removes the check from the scenario and leaves the constant defined, all of it
    still passes and none of it means anything.

    Read from the file rather than through `inspect`: `launch_test` execs the
    scenario by path and never registers it in `sys.modules`, so `getsource` on
    anything it defines raises.
    """
    source = (SCENARIO_DIR / "continuous_line.py").read_text()
    for constant in ("SURFACE_TOLERANCE_M", "DROP_MARGIN_M", "CELL_MARGIN_M"):
        uses = source.count(constant)
        assert uses >= 2, (
            f"{constant} is defined in continuous_line.py and used {uses - 1} time(s). "
            "The check it belongs to has been removed and the scenario is no longer "
            "measuring what this guard covers."
        )
    assert "_within_the_cell" in source, "the containment check is gone from the scenario"
    assert "workpieces_completed" in source, (
        "the scenario no longer mentions `workpieces_completed`; it is reported as "
        "context precisely because it must never become the thing asserted on"
    )
