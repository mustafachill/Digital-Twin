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

"""ADR-0050 decision 2's table, one row at a time.

The table is the decision, so the test is the table: every mode the message
declares has a row, every row says which sides evaluate the goal, and a mode
nobody has added yet is refused rather than defaulted.
"""

from __future__ import annotations

from cite_interfaces.msg import ResultCode, TwinMode
from cite_twin.routing import COUNTERPART_SIDE, PLANT_SIDE, reverse_state_flow, route
import pytest

DECLARED_MODES = [getattr(TwinMode, name) for name in dir(TwinMode) if name.startswith("MODE_")]


def test_the_message_still_declares_six_modes() -> None:
    """A guard on the guard: a `dir()` scan that found nothing would pass silently."""
    assert len(DECLARED_MODES) == 6


@pytest.mark.parametrize("mode", DECLARED_MODES)
def test_every_declared_mode_has_a_row(mode: int) -> None:
    chosen = route(mode)
    assert chosen.detail != ""
    assert set(chosen.sides) <= {PLANT_SIDE, COUNTERPART_SIDE}


@pytest.mark.parametrize("mode", [TwinMode.MODE_VALIDATED, TwinMode.MODE_VIRTUAL_LEAD])
def test_both_sides_evaluate_the_goal(mode: int) -> None:
    """The two rows whose third column is "yes", and the plant comes first."""
    chosen = route(mode)
    assert chosen.accepted
    assert chosen.sides == (PLANT_SIDE, COUNTERPART_SIDE)


@pytest.mark.parametrize(
    "mode", [TwinMode.MODE_SIM, TwinMode.MODE_REAL, TwinMode.MODE_SHADOW]
)
def test_the_modes_with_no_command_flow_refuse(mode: int) -> None:
    """L5's endpoint is not a second front door to the plant's own skill server."""
    chosen = route(mode)
    assert not chosen.accepted
    assert chosen.code == ResultCode.PRECONDITION_FAILED


def test_closed_loop_is_the_row_the_record_leaves_undecided() -> None:
    """Its gate is filed for Phase 5 with its own ADR; a router may not improvise it."""
    chosen = route(TwinMode.MODE_CLOSED_LOOP)
    assert not chosen.accepted
    assert chosen.code == ResultCode.NOT_IMPLEMENTED


def test_a_seventh_mode_is_refused_rather_than_defaulted() -> None:
    """This project has already added a sixth mode."""
    chosen = route(200)
    assert not chosen.accepted
    assert chosen.code == ResultCode.PRECONDITION_FAILED


class TestTheReverseStateFlow:
    def test_virtual_lead_has_none_which_is_what_defines_it(self) -> None:
        """`TwinMode.msg`: "No reverse flow behind it - that is SHADOW".

        This is why the divergence metric's second operand does not exist in
        that mode, and why `valid` is false there for a structural reason rather
        than a semantic one. A change that makes this return a side has added a
        seventh mode without saying so (ADR-0050 decision 3).
        """
        assert reverse_state_flow(TwinMode.MODE_VIRTUAL_LEAD) == ()

    def test_sim_and_real_have_none_because_one_side_is_idle(self) -> None:
        assert reverse_state_flow(TwinMode.MODE_SIM) == ()
        assert reverse_state_flow(TwinMode.MODE_REAL) == ()

    @pytest.mark.parametrize(
        "mode",
        [TwinMode.MODE_SHADOW, TwinMode.MODE_VALIDATED, TwinMode.MODE_CLOSED_LOOP],
    )
    def test_state_crosses_from_the_far_side_only(self, mode: int) -> None:
        """Never from the plant: the plant is the virtual side (ADR-0050, Context)."""
        assert reverse_state_flow(mode) == (COUNTERPART_SIDE,)


def test_the_two_side_identities_are_not_positions() -> None:
    """ADR-0044: a plan whose `sides:` list is addressed by index is one
    reordering away from handing a caller the counterpart while calling it the
    plant. Nothing in this module resolves a side by index.
    """
    assert PLANT_SIDE != COUNTERPART_SIDE
    assert PLANT_SIDE == "plant"
    assert COUNTERPART_SIDE == "counterpart"
