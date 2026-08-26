"""Guard: the place assertion measures height, not only horizontal arrival.

Why this exists, because the gap it closes was invisible to a green run.

`pick_and_place` asserts that the work-piece "arrived where the topology says it
should". Until now it measured that with x and y alone. At the baseline taken
before the attachment plugin was removed under ADR-0029 the work-piece finished
at z = 1.201 m — still welded to a gripper finger, half a metre in the air, and
directly above the infeed. Every horizontal check passed. The scenario was green
about a part that had never been let go of.

A part held above the target and a part resting on the target are the same
measurement in two dimensions. So is a part that slid off the belt onto the
floor: it keeps the x and y that just passed and loses only height. The height
check is what separates all three, and this guard is what stops it being
dropped again.

It belongs in the ROS-free host suite rather than in the scenario because the
scenario can only make this measurement with Gazebo running, which is minutes of
simulation and a machine that can carry it. The arithmetic underneath it is
checkable in milliseconds, so it is checked on every `./scripts/test`, including
`--host-only`. The scenario proves the number is achievable in a real cell; this
proves the comparison would still reject the failure it was written for.

Nothing here writes a coordinate. The belt height comes from the generated
static transform table — the same L0-derived value the scenario resolves through
TF at run time — so a layout change moves this guard with it (P1). The layout has
moved twice on this branch already.
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

#: The generated static transform table for the cell the scenario drives. Read
#: rather than imported: this suite is ROS-free, and the file is plain YAML
#: produced from the L0 model (ADR-0021), so reading it here duplicates no value.
STATIC_TF = (
    Path(__file__).resolve().parents[3]
    / "workspace"
    / "src"
    / "cite_generated"
    / "frames"
    / "cell_a_static_tf.yaml"
)

#: Where the work-piece was measured at the pre-ADR-0029 baseline, in metres, in
#: `cite_world`. This is a recorded observation of a specific broken run and NOT
#: a layout value — it is never used as a coordinate, only as the input that the
#: assertion under test has to reject. It is the one number in this file that
#: does not come from the model, and it is written here once.
BASELINE_HELD_Z_M = 1.201


@pytest.fixture(scope="module")
def scenario():
    """`pick_and_place` loaded the way `launch_test` loads it, with ROS stubbed."""
    with _ros_stubs():
        return _load_like_launch_test(SCENARIO_DIR / "pick_and_place.py")


@pytest.fixture(scope="module")
def place_z() -> float:
    """The height of the place frame, from the generated transform table."""
    assert STATIC_TF.is_file(), (
        f"{STATIC_TF} is missing; it is generated from the L0 model and this guard "
        "reads the belt height from it rather than writing one"
    )
    table = yaml.safe_load(STATIC_TF.read_text())["static_transforms"]
    frame = "cell_a__conveyor_1__infeed"
    for entry in table:
        if entry.get("child") == frame:
            return float(entry["xyz_m"][2])
    pytest.fail(f"{frame} is not in {STATIC_TF.name}; the scenario resolves it through TF")


def _resting_z(scenario, place_z: float) -> float:
    """Where a released work-piece comes to rest: half a cube above the surface."""
    return place_z + scenario.WORKPIECE_SIZE / 2.0


#: Contact jitter and the last millimetres of settling, in metres. A released
#: part does not come to rest at exactly the analytic height, and the tolerance
#: has to absorb that or the scenario fails runs that placed correctly.
SETTLING_JITTER_M = 0.005


def test_a_settled_workpiece_is_accepted(scenario, place_z: float) -> None:
    """A part actually resting on the belt passes, jitter included.

    Checked in both directions: the part may end a few millimetres proud of the
    surface after a bounce, or a few millimetres into it while the contact
    constraint resolves.
    """
    resting = _resting_z(scenario, place_z)
    for sample in (resting, resting + SETTLING_JITTER_M, resting - SETTLING_JITTER_M):
        error = abs(sample - resting)
        assert error < scenario.PLACE_HEIGHT_TOLERANCE_M, (
            f"a work-piece resting at {sample:.4f} m would be rejected against an "
            f"expected {resting:.4f} m; the scenario would fail a correct placement"
        )


def test_settling_on_a_corner_is_still_accepted(scenario, place_z: float) -> None:
    """The tolerance covers the widest legitimate resting pose, not just the flat one.

    A cube that settles on a corner rather than a face carries its centre
    `half_diagonal - half_edge` higher. If the tolerance were ever tightened below
    that, the scenario would start failing runs in which the part is genuinely on
    the belt, and the fix would look like "the place skill regressed".
    """
    half_edge = scenario.WORKPIECE_SIZE / 2.0
    on_a_corner = _resting_z(scenario, place_z) + half_edge * (3.0**0.5 - 1.0)
    error = abs(on_a_corner - _resting_z(scenario, place_z))
    assert error < scenario.PLACE_HEIGHT_TOLERANCE_M, (
        f"a cube resting on a corner sits {error:.4f} m high and would be rejected "
        f"by PLACE_HEIGHT_TOLERANCE_M={scenario.PLACE_HEIGHT_TOLERANCE_M}"
    )


def test_a_part_still_held_in_the_air_is_rejected(scenario, place_z: float) -> None:
    """The regression. This is the run that used to pass.

    Asserted in both directions on purpose: the point is not merely that the
    height check rejects the baseline, but that the horizontal check does NOT —
    which is exactly why the horizontal check alone was insufficient evidence.
    """
    resting = _resting_z(scenario, place_z)
    held_error = abs(BASELINE_HELD_Z_M - resting)

    assert held_error >= scenario.PLACE_HEIGHT_TOLERANCE_M, (
        f"the pre-ADR-0029 baseline height {BASELINE_HELD_Z_M} m is within "
        f"PLACE_HEIGHT_TOLERANCE_M={scenario.PLACE_HEIGHT_TOLERANCE_M} of the "
        f"resting height {resting:.3f} m, so the scenario would accept a part that "
        "was never released"
    )

    # The other half of the finding: horizontally, that run was perfect. A part
    # dangling directly above the infeed is at zero horizontal error, so the
    # check that used to be the only one would wave it through.
    held_horizontal_error = 0.0
    assert held_horizontal_error < scenario.PLACE_TOLERANCE_M, (
        "a held part directly above the place frame has zero horizontal error and "
        "passes the horizontal check; height is the only thing that catches it"
    )


def test_a_part_that_fell_off_the_belt_is_rejected(scenario, place_z: float) -> None:
    """The other failure the two-sided check exists for.

    A work-piece that leaves the belt edge ends up on the floor with its centre
    half a cube above ground. If the height assertion were written as an upper
    bound only — "not still in the air" — this run would pass.
    """
    on_the_floor = scenario.WORKPIECE_SIZE / 2.0
    error = abs(on_the_floor - _resting_z(scenario, place_z))
    assert error >= scenario.PLACE_HEIGHT_TOLERANCE_M, (
        "a part resting on the floor is within tolerance of the belt height; the "
        "height assertion must be two-sided to reject it"
    )


def test_the_scenario_still_asserts_on_height() -> None:
    """The tripwire for the assertion being deleted while the constant survives.

    Everything above tests arithmetic over `PLACE_HEIGHT_TOLERANCE_M`. If somebody
    removes the assertion from the scenario but leaves the constant defined, all of
    it still passes and none of it means anything.

    Read from the file rather than through `inspect`: `launch_test` execs the
    scenario by path and never registers it in `sys.modules`, so `getsource` on
    anything it defines raises "is a built-in class". The sibling guard
    `test_scenario_modules_load` exists because of that same property.
    """
    source = (SCENARIO_DIR / "pick_and_place.py").read_text()

    uses = source.count("PLACE_HEIGHT_TOLERANCE_M")
    assert uses >= 2, (
        "PLACE_HEIGHT_TOLERANCE_M is defined in pick_and_place.py but never used "
        f"(found {uses} mention(s), expected the definition plus at least one "
        "assertion). The place assertion has stopped measuring height and is back "
        "to x and y only, which is exactly the gap this guard exists to hold shut."
    )
    assert "final[2]" in source, (
        "pick_and_place no longer reads the work-piece's z from the simulator; the "
        "height assertion cannot be measuring anything"
    )
