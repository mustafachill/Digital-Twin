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

"""ADR-0054 clause 8: L5's gate answers on the fact, and the shipped plan behaves.

**NOTHING HERE CONSTRUCTS A NODE, STARTS A GRAPH OR BRINGS ANYTHING UP.** Each
assertion calls a function on an in-memory object, and that is a requirement on
the implementation as much as on this file: the failure the second test guards is
an exception raised *during* `TwinBoundary.__init__`, which no test that needs a
working `__init__` can reach. `deployment_from_plan` and `far_side_is_physical`
are free functions for exactly that reason.

WHY THIS FILE EXISTS AT ALL. `cite_twin` is started by no launch file (CLAUDE.md
§2), so a regression in the mode gate fails no gate outside this package's own
tests. ADR-0054's headline finding is L5's: `physical_sides_commanded` reported
no physical side commanded, for every mode, on a zone whose every side loaded the
vendor's physical `ros2_control` component under the id `sim`.
"""

from __future__ import annotations

from pathlib import Path

from cite_bringup.plan import default_plan_path, load as load_plan
from cite_interfaces.msg import TwinMode
from cite_twin.mode import (
    Deployment,
    deployment_from_plan,
    far_side_is_physical,
    ModeAuthority,
)
from cite_twin.routing import commanded_sides, COUNTERPART_SIDE, PLANT_SIDE
import pytest

#: Every mode that commands the far side, which is the set clause 8 asks about.
TWO_SIDED_MODES = sorted(
    mode
    for mode in (
        TwinMode.MODE_SIM,
        TwinMode.MODE_REAL,
        TwinMode.MODE_SHADOW,
        TwinMode.MODE_VALIDATED,
        TwinMode.MODE_VIRTUAL_LEAD,
    )
    if COUNTERPART_SIDE in commanded_sides(mode)
)


def _refused() -> None:
    raise RuntimeError("CITE_ALLOW_HARDWARE is not set to 1")


# --- Bullet 1: the reproduction's deployment is gated ------------------------


def _the_reproduction() -> Deployment:
    """Every side stating the id `sim` while that backend declares physical.

    The id is not carried at all any more, which is the point: this object holds
    what L0 declared, and the model ADR-0054 reproduces declares `true` on both
    sides while calling the backend `sim`.
    """
    return Deployment(
        {
            asset: {PLANT_SIDE: True, COUNTERPART_SIDE: True}
            for asset in ("arm_1", "arm_2", "arm_3")
        }
    )


@pytest.mark.parametrize("mode", TWO_SIDED_MODES)
def test_the_reproduction_names_a_physical_side_for_every_two_sided_mode(
    mode: int,
) -> None:
    """Where the shipped code named none, for any mode.

    ADR-0054's Context prints `physical_sides_commanded = ()` for
    MODE_VIRTUAL_LEAD, MODE_VALIDATED, MODE_SHADOW and MODE_REAL on this exact
    deployment.
    """
    named = _the_reproduction().physical_sides_commanded(mode, "")
    assert named, "no side was named on a cell whose every side declares physical"


@pytest.mark.parametrize("mode", TWO_SIDED_MODES)
def test_the_safety_blocked_message_still_names_the_asset_and_the_side(
    mode: int,
) -> None:
    """The load-bearing half of the diagnostic survives the datum change.

    The backend id is deliberately gone — printing it would print the value
    ADR-0054 removed from the safety path, and a reader would take it for the
    reason. What may not go is which (asset, side) was refused for: a refusal
    that cannot say that sends its reader to the wrong half of the cell.
    """
    authority = ModeAuthority(_the_reproduction(), _refused)
    verdict = authority.request(mode, "arm_2", "because", force=False)
    assert not verdict.accepted
    assert "arm_2" in verdict.detail
    assert COUNTERPART_SIDE in verdict.detail or PLANT_SIDE in verdict.detail


def test_a_deployment_declaring_nothing_physical_gates_no_mode() -> None:
    """The other direction, which a check that refused everything would fail."""
    simulated = Deployment(
        {
            asset: {PLANT_SIDE: False, COUNTERPART_SIDE: False}
            for asset in ("arm_1", "arm_2", "arm_3")
        }
    )
    for mode in TWO_SIDED_MODES:
        assert simulated.physical_sides_commanded(mode, "") == ()


# --- Bullet 2: the shipped single-sided plan still behaves -------------------
#
# THE ASSERTION THAT CATCHES DECISION 2's TWO-VALUED COLLAPSE. A map carrying a
# bare `bool` per (asset, side) makes every unpaired asset look like it HAS a far
# side that is merely simulated, and the `PRECONDITION_FAILED` refusal of a
# two-sided mode on a one-sided deployment stops firing - on the shipped model,
# which is every deployment this repository can generate today.


def _shipped() -> Deployment:
    return deployment_from_plan(load_plan(Path(default_plan_path("cell_a"))))


def test_the_shipped_plan_yields_a_deployment_with_no_far_side() -> None:
    """And building it does not raise, which is the total accessor's whole job."""
    shipped = _shipped()
    assert set(shipped.sides) == {"arm_1", "arm_2", "arm_3"}
    assert shipped.assets_without_a_far_side("") == ("arm_1", "arm_2", "arm_3")
    assert not shipped.has_a_far_side("")


def test_the_shipped_plan_states_no_far_side_rather_than_a_simulated_one() -> None:
    """`None` and not `False`. The two are different answers to different questions.

    This is the mutation: collapse the map to `bool` and every value below
    becomes `False`, which reads as "there is a far side and it is simulated".
    """
    shipped = _shipped()
    for asset in shipped.sides:
        assert shipped.declares_physical_hardware(asset, PLANT_SIDE) is False
        assert shipped.declares_physical_hardware(asset, COUNTERPART_SIDE) is None


@pytest.mark.parametrize("mode", TWO_SIDED_MODES)
def test_a_two_sided_mode_is_refused_on_the_shipped_deployment(mode: int) -> None:
    """The refusal the collapse would silently retire.

    Reported as a verdict rather than raised: `ModeAuthority.request` turns a
    `ModeError` into the response the caller gets back, which is the shape
    `SetMode` answers in.
    """
    from cite_interfaces.msg import ResultCode

    verdict = ModeAuthority(_shipped(), _refused).request(
        mode, "", "because", force=False
    )
    assert not verdict.accepted
    assert verdict.code == ResultCode.PRECONDITION_FAILED
    # And it names the assets, which is what `assets_without_a_far_side` is for.
    assert "arm_1" in verdict.detail


# --- Bullet 3: `far_side_physical` is a free function of the declaration -----
#
# It does not live on `Deployment`: it was a local in `TwinBoundary._sample`
# computed from a map of backend ids, so an implementation could migrate
# `Deployment` fully, satisfy both bullets above, and leave `_sample` still
# deciding on a name. It feeds `frames_correspond` (ADR-0050), a P8 concern.


def test_a_far_side_declaring_physical_is_physical() -> None:
    assert far_side_is_physical(True) is True


def test_a_far_side_declaring_no_physical_hardware_is_not() -> None:
    assert far_side_is_physical(False) is False


def test_an_absent_far_side_is_not_physical() -> None:
    """An absent far side is not a machine.

    `None` means there is no far side. Written as `is True` upstream so the two
    false answers stay one answer here and nowhere else.
    """
    assert far_side_is_physical(None) is False


def test_the_sample_asks_the_free_function_rather_than_deciding_again() -> None:
    """The route, not the behaviour.

    Every other assertion in this section is satisfied by an implementation that
    leaves `_sample` computing its own answer from a backend id and never calls
    this function.
    """
    source = (
        Path(__file__).resolve().parents[1] / "cite_twin" / "twin_boundary.py"
    ).read_text()
    assert "far_side_is_physical(" in source
    assert "_far_side_backends" not in source, (
        "twin_boundary still keeps a map of far-side BACKEND IDS; ADR-0054 moved "
        "that map onto the declared fact"
    )


# --- What a TwinBoundary does with the shipped single-sided plan -------------


def test_the_boundary_refuses_the_shipped_plan_at_side_resolution() -> None:
    """It refuses, and WHERE it refuses is the finding this test records.

    ADR-0054's decision 2 warns that migrating `twin_boundary` with the refusing
    accessor would make `TwinBoundary.__init__` raise on the shipped model. **On
    this tree it would not have got that far**, and that is a correction to the
    record rather than a defence of the shortcut: `__init__` resolves both sides
    through `address()` FIRST, and `Plan.side_named` refuses a counterpart the
    shipped single-sided plan does not declare. So an implementation that used
    the refusing accessor would have been masked here by an earlier, deliberate
    refusal — and would still have broken `deployment_from_plan`, which clause 8
    calls on this same plan with no node at all.

    Pinned so that a later change to the construction ORDER does not quietly turn
    the masked failure into a live one.
    """
    from cite_bringup.plan import SideNotDeclaredError
    from cite_twin.twin_boundary import TwinBoundary

    plan = load_plan(Path(default_plan_path("cell_a")))
    with pytest.raises(SideNotDeclaredError) as raised:
        TwinBoundary(plan, base=1, environ={})
    assert "declares no side named" in str(raised.value), (
        "the shipped plan must be refused for having one side, not for anything "
        "the hardware declaration says"
    )
