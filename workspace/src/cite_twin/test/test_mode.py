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

"""Every transition the mode server can be asked for, and what it answers.

The check that matters most is the one nothing in this project had before: that
`force` cannot reach the hardware gate. `SetMode.srv` says "Never skips a safety
check - no value of this field can do that", and until this file that sentence
was a comment.

No ROS runtime: `cite_twin.mode` takes the hardware check as a callable, so both
answers are driven here without touching the process environment.
"""

from __future__ import annotations

from cite_interfaces.msg import ResultCode, TwinMode
from cite_twin.mode import Deployment, MODE_NAMES, ModeAuthority
from cite_twin.routing import commanded_sides, route
import pytest

#: A Phase 2.A pair: three arms, every far side a second simulation.
SIMULATED = Deployment.paired({"arm_1": "sim", "arm_2": "sim", "arm_3": "sim"})

#: Phase 2.B's planned state, and the one `cross-cutting-safety.md` insists is
#: not an edge case: one physical arm beside two simulated ones.
MIXED = Deployment.paired(
    {"arm_1": "sim", "arm_2": "uf_robot_hardware", "arm_3": "sim"}
)

#: A zone with no counterpart at all.
UNPAIRED = Deployment.paired({"arm_1": None})

#: Every mode the message declares, read off the message.
#:
#: `dir()` rather than `vars()`: rosidl exposes a message's constants as
#: properties on its METACLASS, so the class's own `__dict__` does not hold them
#: and a `vars()` scan would silently find nothing and pass.
ALL_MODES = sorted(
    getattr(TwinMode, name) for name in dir(TwinMode) if name.startswith("MODE_")
)


def _granted() -> None:
    """Grant the hardware opt-in."""


def _refused() -> None:
    """Withhold it, the way `require_hardware_opt_in` withholds it."""
    raise RuntimeError("CITE_ALLOW_HARDWARE is not set to 1")


def authority(deployment: Deployment = SIMULATED, opt_in=_refused) -> ModeAuthority:
    return ModeAuthority(deployment, opt_in)


class TestTheStartingPoint:
    def test_a_deployment_starts_in_sim(self) -> None:
        """Never reachable by a default parameter, an argument, or an omission."""
        assert authority().mode == TwinMode.MODE_SIM

    def test_the_starting_reason_is_recorded(self) -> None:
        assert authority().reason != ""


class TestRefusalsThatAreNotAboutHardware:
    def test_a_mode_that_is_not_a_mode_is_refused(self) -> None:
        verdict = authority().request(200, "", "because", force=False)
        assert not verdict.accepted
        assert verdict.code == ResultCode.PRECONDITION_FAILED
        assert "TwinMode.MODE_" in verdict.detail

    @pytest.mark.parametrize("reason", ["", "   "])
    def test_a_transition_without_a_reason_is_refused(self, reason: str) -> None:
        """`SetMode.reason` is required, so every transition has a why."""
        verdict = authority().request(TwinMode.MODE_VALIDATED, "", reason, force=False)
        assert not verdict.accepted
        assert verdict.code == ResultCode.PRECONDITION_FAILED

    def test_an_asset_this_zone_does_not_have_is_refused(self) -> None:
        verdict = authority().request(
            TwinMode.MODE_VALIDATED, "arm_9", "because", force=False
        )
        assert not verdict.accepted
        assert verdict.code == ResultCode.PRECONDITION_FAILED
        assert "arm_9" in verdict.detail

    def test_a_refused_transition_leaves_the_mode_where_it_was(self) -> None:
        machine = authority()
        machine.request(TwinMode.MODE_VALIDATED, "", "", force=False)
        assert machine.mode == TwinMode.MODE_SIM


class TestADeploymentWithNoFarSide:
    """Every mode but SIM is a statement about two sides (ADR-0050 decision 4)."""

    @pytest.mark.parametrize(
        "mode",
        [
            TwinMode.MODE_REAL,
            TwinMode.MODE_SHADOW,
            TwinMode.MODE_VALIDATED,
            TwinMode.MODE_VIRTUAL_LEAD,
        ],
    )
    def test_a_mode_needing_a_far_side_is_refused(self, mode: int) -> None:
        verdict = authority(UNPAIRED, _granted).request(mode, "", "because", force=False)
        assert not verdict.accepted
        assert verdict.code == ResultCode.PRECONDITION_FAILED
        assert "arm_1" in verdict.detail

    def test_sim_is_always_supportable(self) -> None:
        verdict = authority(UNPAIRED).request(TwinMode.MODE_SIM, "", "because", force=False)
        assert verdict.accepted

    def test_force_skips_it_because_it_is_not_a_safety_precondition(self) -> None:
        """A forced mode against a missing far side produces invalid samples.

        Which is what the monitor is built to report rather than hide, so this
        precondition is one `force` may skip. The hardware gate below is not.
        """
        verdict = authority(UNPAIRED, _granted).request(
            TwinMode.MODE_VALIDATED, "", "because", force=True
        )
        assert verdict.accepted


class TestTheGateIsDerivedAndNotListed:
    """The criterion, applied to every mode the message declares.

    The gate this class holds is not a list of modes. It is
    `cross-cutting-safety.md`'s criterion computed from two data: which sides a
    mode commands (`cite_twin.routing`) and what each side loads (the generated
    plan). These tests are what makes that checkable rather than asserted, and
    the first of them is the one the branch did not have.
    """

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_every_mode_that_dispatches_a_goal_is_refused_without_the_opt_in(
        self, mode: int
    ) -> None:
        """**The regression.** A mode L5 sends a goal in reaches the far arm.

        Where that far side is physical, entering the mode places physical
        actuation under an authority that was not commanding it, whatever the
        mode is called. `VALIDATED` and `VIRTUAL_LEAD` dispatch by
        byte-identical code, and until 2026-08-31 only the second was gated —
        `SetMode(VALIDATED)` was accepted against `MIXED` with no opt-in and a
        goal then reached `arm_2`'s physical far side.

        Driven off `route()` rather than off a list of mode names, so a seventh
        mode that dispatches a goal fails here on the day it is added.
        """
        if not route(mode).accepted:
            pytest.skip(f"{MODE_NAMES[mode]} dispatches no goal; covered below")
        verdict = authority(MIXED, _refused).request(mode, "", "because", force=False)
        assert not verdict.accepted, f"{MODE_NAMES[mode]} reached a physical far side"
        assert verdict.code == ResultCode.SAFETY_BLOCKED
        assert "arm_2" in verdict.detail

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_every_mode_that_commands_a_physical_side_is_refused_without_the_opt_in(
        self, mode: int
    ) -> None:
        """The same question asked of the wider set, which is the criterion's own.

        A mode commands a side whether or not L5 is the caller — `REAL` and
        `SHADOW` drive the physical side from its own callers — so the gate is
        computed over `commanded_sides` and this test is driven off the same
        function. `SIM` is the one mode that commands only the plant.
        """
        verdict = authority(MIXED, _refused).request(mode, "", "because", force=False)
        if "counterpart" in commanded_sides(mode):
            assert not verdict.accepted, MODE_NAMES[mode]
            assert verdict.code == ResultCode.SAFETY_BLOCKED
        else:
            assert verdict.accepted, verdict.detail

    def test_the_gate_matrix_written_out_by_hand(self) -> None:
        """The same answers, stated rather than derived, so both can be wrong apart.

        A test that computes its expectation from the table under test proves
        the plumbing and not the answer. This one writes the answer down: on a
        cell with one physical far side, every mode but `SIM` is refused, and
        that includes `SHADOW` — `TwinMode.msg` says the physical side is
        commanded in it, and the transcribed list never asked.
        """
        expected = {
            TwinMode.MODE_SIM: True,
            TwinMode.MODE_REAL: False,
            TwinMode.MODE_SHADOW: False,
            TwinMode.MODE_VALIDATED: False,
            TwinMode.MODE_CLOSED_LOOP: False,
            TwinMode.MODE_VIRTUAL_LEAD: False,
        }
        assert set(expected) == set(ALL_MODES), (
            "a mode was added to TwinMode and this matrix was not updated; decide "
            "what it commands rather than letting it default"
        )
        actual = {
            mode: authority(MIXED, _refused)
            .request(mode, "", "because", force=False)
            .accepted
            for mode in expected
        }
        assert actual == expected

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_force_skips_none_of_them(self, mode: int) -> None:
        """`SetMode.srv`: "Never skips a safety check - no value of this field can do that"."""
        verdict = authority(MIXED, _refused).request(mode, "", "because", force=True)
        if "counterpart" in commanded_sides(mode):
            assert not verdict.accepted, MODE_NAMES[mode]
            assert verdict.code == ResultCode.SAFETY_BLOCKED

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_a_wholly_simulated_deployment_gates_nothing_and_claims_nothing(
        self, mode: int
    ) -> None:
        """No side of such a deployment can actuate anything, so nothing is gated.

        And `commands_hardware` says so. It used to report `True` for `REAL` and
        `CLOSED_LOOP` here while the plan-scoped check it was gating on could
        not refuse — a flag that claimed a gate nothing applied.
        """
        verdict = authority(SIMULATED, _refused).request(
            mode, "", "because", force=False
        )
        assert verdict.accepted, verdict.detail
        assert not verdict.commands_hardware

    def test_virtual_lead_against_a_simulated_far_side_is_not_gated(self) -> None:
        """The third transition is the only one that is not self-identifying.

        Where a given asset's far side is a simulated counterpart, entering the
        mode moves nothing physical for that asset — which is what makes the
        mode reachable in Phase 2.A at all.
        """
        verdict = authority(SIMULATED, _refused).request(
            TwinMode.MODE_VIRTUAL_LEAD, "", "because", force=False
        )
        assert verdict.accepted
        assert not verdict.commands_hardware

    def test_virtual_lead_is_gated_where_any_far_side_is_real(self) -> None:
        """Two assets answering "simulated" is not an answer for the third."""
        verdict = authority(MIXED, _refused).request(
            TwinMode.MODE_VIRTUAL_LEAD, "", "because", force=False
        )
        assert not verdict.accepted
        assert verdict.code == ResultCode.SAFETY_BLOCKED
        assert "arm_2" in verdict.detail

    def test_force_does_not_skip_it_either(self) -> None:
        verdict = authority(MIXED, _refused).request(
            TwinMode.MODE_VIRTUAL_LEAD, "", "because", force=True
        )
        assert not verdict.accepted
        assert verdict.code == ResultCode.SAFETY_BLOCKED

    def test_it_is_a_per_asset_question(self) -> None:
        """The simulated asset of a mixed cell is not gated; the physical one is."""
        simulated = authority(MIXED, _refused).request(
            TwinMode.MODE_VIRTUAL_LEAD, "arm_1", "because", force=False
        )
        physical = authority(MIXED, _refused).request(
            TwinMode.MODE_VIRTUAL_LEAD, "arm_2", "because", force=False
        )
        assert simulated.accepted
        assert not physical.accepted
        assert physical.code == ResultCode.SAFETY_BLOCKED

    def test_a_backend_nobody_anticipated_counts_as_hardware(self) -> None:
        """An allowlist: a hardware path is never reachable by omission."""
        deployment = Deployment.paired({"arm_1": "some_future_driver"})
        verdict = authority(deployment, _refused).request(
            TwinMode.MODE_VIRTUAL_LEAD, "", "because", force=False
        )
        assert not verdict.accepted
        assert verdict.code == ResultCode.SAFETY_BLOCKED

    def test_the_gate_passes_when_the_opt_in_was_given(self) -> None:
        verdict = authority(MIXED, _granted).request(
            TwinMode.MODE_VIRTUAL_LEAD, "", "because", force=False
        )
        assert verdict.accepted
        assert verdict.commands_hardware


class TestAcceptedTransitions:
    def test_the_mode_moves_and_the_reason_is_kept(self) -> None:
        machine = authority()
        verdict = machine.request(
            TwinMode.MODE_VALIDATED, "", "measuring the instrument", force=False
        )
        assert verdict.accepted
        assert verdict.code == ResultCode.SUCCESS
        assert machine.mode == TwinMode.MODE_VALIDATED
        assert machine.reason == "measuring the instrument"

    def test_asking_for_the_mode_already_in_force_is_not_a_transition(self) -> None:
        """Nothing enters an authority it was already under, so nothing is gated."""
        machine = authority(MIXED, _refused)
        machine.request(TwinMode.MODE_SIM, "", "unchanged", force=False)
        verdict = machine.request(TwinMode.MODE_SIM, "", "still unchanged", force=False)
        assert verdict.accepted
        assert not verdict.commands_hardware
        assert machine.mode == TwinMode.MODE_SIM

    def test_every_mode_the_message_declares_can_be_asked_for(self) -> None:
        """A mode the message grows and this layer does not know about is a defect.

        Asked of every constant rather than of a list here, so a seventh mode
        fails this test rather than being silently unreachable.
        """
        modes = ALL_MODES
        assert len(modes) >= 6
        for mode in modes:
            verdict = authority(SIMULATED, _granted).request(
                mode, "", "because", force=False
            )
            assert verdict.accepted, f"mode {mode} was refused: {verdict.detail}"
