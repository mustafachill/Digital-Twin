"""Guard: `bringup` builds its expected joint names out of the asset id.

Why this exists, because the defect it closes was invisible to every gate that
has ever run on this branch.

`bringup.joints_of` took an asset id as a `str`. `136d046` converted
`TestCellBringUp.arms` from a tuple of ids into a tuple of `ControllerManager`
objects and correctly updated `arm.joint_state_topic` and `arm.asset` at the two
places that needed them — and left `joints_of(arm)` alone. A `str` and a
dataclass both format, so `f"{arm}_{suffix}"` went on producing a set, built out
of the REPR:

    ControllerManager(asset='picker', node='/cite/cell_b/picker/controller_manager',
    ...)_left_inner_knuckle_joint

The published names were correct in both zones. The EXPECTATION was not, so
`test_joint_states_are_actually_delivered` could not pass on any zone — 4 of 4
runs on `cell_b` and 1 of 1 on `cell_a`.

**Nothing in `./scripts/lint && ./scripts/build && ./scripts/test` evaluates that
expression.** `./scripts/test` runs no scenario, and mypy's remit is
`tools/cite_tools` (`scripts/lint:35`) — so a type annotation on `joints_of`
would have been checked by nothing. Extending mypy over `tests/scenarios` would
not have caught it either: `_cell.cell()` is annotated `-> tuple`, so `self.plan`
and everything read off it is `Any`. A guard is therefore the instrument, and it
is the one the sibling files here already use: load the scenario the way
`launch_test` loads it, and drive the arithmetic against the generated tree
without starting anything.

It parametrises over every zone the generated tree declares rather than naming
one — see `_artifacts` for why a guard that names a cell goes green about a file
nobody drives.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import _artifacts
import pytest
from test_scenario_modules_load import (  # the loader `launch_test` itself uses
    SCENARIO_DIR,
    _load_like_launch_test,
    _ros_stubs,
)

#: What a joint name may consist of. Every character class the repr defect
#: introduced — `(`, `)`, `'`, `=`, `,`, `/`, a space — is outside it, so this
#: rejects the whole family rather than the one spelling that was observed. It is
#: also what `ros2_control` and every `sensor_msgs/JointState` consumer assume.
JOINT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@pytest.fixture(scope="module")
def scenario():
    """`bringup` loaded the way `launch_test` loads it, with ROS stubbed."""
    with _ros_stubs():
        return _load_like_launch_test(SCENARIO_DIR / "bringup.py")


@pytest.fixture(scope="module", params=_artifacts.zone_ids(), ids=lambda zone: zone)
def artifacts(request) -> _artifacts.Artifacts:
    """One case per zone the generated tree declares."""
    return _artifacts.load(request.param)


def arms(artifacts: _artifacts.Artifacts) -> list[SimpleNamespace]:
    """The zone's arms, selected by the rule `TestCellBringUp.setUpClass` uses.

    An arm is a controller manager carrying a MoveIt configuration, which is what
    distinguishes it from a belt — read here off the plan as YAML, exactly as the
    scenario reads it off `cite_bringup.plan`.

    `SimpleNamespace` stands in for `cite_bringup.plan.ControllerManager`. It
    carries the ONE field `joints_of` is entitled to read, so a `joints_of` that
    reached for a second one would fail here with an `AttributeError` naming it,
    and a `joints_of` that formatted the object whole would produce
    `namespace(asset='picker')_joint1` — the same shape of wrong answer as the
    defect, caught by the same assertions.
    """
    return [
        SimpleNamespace(asset=manager["asset"])
        for manager in artifacts.plan["controller_managers"]
        if manager.get("moveit") is not None
    ]


def test_the_generated_tree_declares_at_least_one_zone() -> None:
    """The tripwire for the parametrisation collecting nothing."""
    assert _artifacts.zone_ids(), (
        f"no <zone>_plan.yaml under {_artifacts.GENERATED / 'bringup'}; this guard "
        "would collect zero cases and pass"
    )


def test_the_zone_declares_an_arm(artifacts: _artifacts.Artifacts) -> None:
    """The second tripwire: a zone with no arm makes every assertion below vacuous.

    The scenario asserts the same thing at run time (`the generated plan for
    {ZONE} declares no arm`), and this is that assertion made available to the
    host suite, where it costs milliseconds.
    """
    assert arms(artifacts), (
        f"the generated plan for {artifacts.zone} declares no controller manager "
        "with a MoveIt configuration, so `bringup` has no arm to drive and every "
        "case in this file would check an empty set"
    )


def test_the_expected_set_is_the_asset_id_prefixed_joint_names(
    scenario, artifacts: _artifacts.Artifacts
) -> None:
    """THE REGRESSION. This is the expression that could not pass on any zone.

    The expected set is composed here from the plan's asset id and the scenario's
    own suffix tuple, independently of how `joints_of` chooses to compose it, and
    the two are required to agree.
    """
    for arm in arms(artifacts):
        expected = {f"{arm.asset}_{suffix}" for suffix in scenario.JOINT_SUFFIXES}
        assert scenario.joints_of(arm) == expected, (
            f"`joints_of` does not build {artifacts.zone}'s {arm.asset} joint names "
            "from the asset id. If the names carry `ControllerManager(asset=...`, it "
            "is formatting the plan object rather than reading `.asset` off it, and "
            "`test_joint_states_are_actually_delivered` cannot pass on any zone."
        )


def test_every_expected_name_is_a_legal_joint_name(
    scenario, artifacts: _artifacts.Artifacts
) -> None:
    """The property the defect violated, asserted without reference to its spelling.

    A repr carries brackets, quotes, commas, `=` and `/`; a joint name carries
    none of them. This holds whatever the composition is rewritten into.
    """
    for arm in arms(artifacts):
        for name in scenario.joints_of(arm):
            assert JOINT_NAME.match(name), (
                f"`joints_of` produced {name!r} for {artifacts.zone}'s {arm.asset}. "
                "No ros2_control joint can be called that, so the expectation is "
                "being built out of something that is not an asset id."
            )


def test_the_expected_set_has_one_name_per_declared_joint(
    scenario, artifacts: _artifacts.Artifacts
) -> None:
    """A count, so a suffix tuple that silently lost an entry is caught here too.

    Against the scenario's own `JOINTS_PER_ARM`, which is the second statement of
    that quantity the scenario keeps on purpose — see its comment. Here they are
    checked against each other with no cell running.
    """
    for arm in arms(artifacts):
        assert len(scenario.joints_of(arm)) == scenario.JOINTS_PER_ARM, (
            f"`joints_of` produced {len(scenario.joints_of(arm))} names for "
            f"{arm.asset} while JOINTS_PER_ARM is {scenario.JOINTS_PER_ARM}; the "
            "two statements of what an arm publishes have come apart"
        )


def test_the_scenario_still_asserts_against_the_expected_set() -> None:
    """The tripwire for the assertion being deleted while the helper survives.

    Everything above tests `joints_of`. If somebody removes the comparison from
    the scenario but leaves the function defined, all of it still passes and none
    of it means anything.

    Read from the file rather than through `inspect`, for the reason
    `test_place_assertion_sees_height` gives: `launch_test` execs the scenario by
    path and never registers it in `sys.modules`.
    """
    source = (SCENARIO_DIR / "bringup.py").read_text()
    uses = source.count("joints_of")
    assert uses >= 2, (
        f"`joints_of` is defined in bringup.py and used {uses - 1} time(s). The "
        "scenario has stopped comparing the published joint names against the ones "
        "the plan's asset ids require, which is the assertion P2 is made of."
    )
