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

"""A run's hold on the twin's mode (`HoldMode.srv`; ADR-0072, safety finding S-01).

The race this closes: a SIM run checks the mode, another client switches the
twin to REAL, and the run's next command reaches the physical arm. Each test
names the half of the rule it holds. Pure logic: no node, no graph.
"""

from __future__ import annotations

from cite_interfaces.msg import ResultCode, TwinMode
from cite_interfaces.srv import HoldMode
from cite_twin.hold import ModeHold, node_names, UNSEEN_CEILING_S

ACQUIRE, RELEASE = HoldMode.Request.ACQUIRE, HoldMode.Request.RELEASE
SIM, REAL, VALIDATED = TwinMode.MODE_SIM, TwinMode.MODE_REAL, TwinMode.MODE_VALIDATED
RUN, OTHER = "run-1", "run-2"
NODE = "/fixed_program"


def _held(mode: int = SIM, now: float = 0.0) -> ModeHold:
    hold = ModeHold()
    assert hold.request(ACQUIRE, RUN, NODE, mode, mode, now).accepted
    return hold


def test_a_foreign_transition_out_of_a_held_sim_is_refused() -> None:
    """S-01: the SIM run's mode cannot be switched to REAL under it."""
    hold = _held(SIM)
    refusal = hold.refusal(REAL, "", SIM)
    assert refusal is not None and "held by a run in progress" in refusal
    assert hold.refusal(REAL, OTHER, SIM) is not None
    assert hold.refusal(VALIDATED, OTHER, SIM) is not None


def test_the_holders_own_transitions_are_allowed_and_carry_the_hold() -> None:
    hold = _held(SIM)
    assert hold.refusal(REAL, RUN, SIM) is None
    hold.followed(RUN, REAL)
    assert hold.held.mode == REAL
    # Another client may not take it on to VALIDATED: only the holder.
    assert hold.refusal(VALIDATED, OTHER, REAL) is not None
    assert hold.refusal(SIM, RUN, REAL) is None


def test_a_transition_into_sim_is_never_refused_by_a_hold() -> None:
    """S2-05: SIM commands the plant alone; nobody is kept from the safe direction."""
    hold = _held(REAL)
    assert hold.refusal(SIM, "", REAL) is None
    assert hold.refusal(SIM, OTHER, REAL) is None
    # The hold stays with its holder, on the mode now in force: the holder's
    # run stops on the mode it did not ask for, and nobody else takes it out.
    hold.followed(OTHER, SIM)
    assert hold.holder == RUN and hold.held.mode == SIM
    assert hold.refusal(REAL, OTHER, SIM) is not None


def test_the_holder_re_asserts_its_hold_idempotently() -> None:
    """S2-05: a re-assertion on the mode in force is accepted and changes nothing."""
    hold = _held(SIM, now=0.0)
    for now in (1.0, 2.0):
        assert hold.request(ACQUIRE, RUN, NODE, SIM, SIM, now).accepted
    assert hold.holder == RUN and hold.held.mode == SIM and hold.held.seen_at == 2.0
    # Re-asserting a mode no longer in force is refused, and the hold kept.
    assert not hold.request(ACQUIRE, RUN, NODE, REAL, SIM, 3.0).accepted
    assert hold.holder == RUN


def test_a_release_with_nothing_held_is_accepted() -> None:
    """R-14: a run that owes a release sends it whether or not its ACQUIRE landed."""
    assert ModeHold().request(RELEASE, RUN, NODE, SIM, SIM, 0.0).accepted


def test_a_request_for_the_mode_in_force_is_never_refused() -> None:
    """A re-assertion changes nothing, so a hold has nothing to protect from it."""
    assert _held(SIM).refusal(SIM, OTHER, SIM) is None


def test_nothing_is_refused_without_a_hold() -> None:
    assert ModeHold().refusal(REAL, "", SIM) is None


def test_a_hold_is_taken_only_on_the_mode_in_force() -> None:
    """A run holds what it checked: if another client moved the twin, nothing is held."""
    hold = ModeHold()
    answer = hold.request(ACQUIRE, RUN, NODE, SIM, REAL, 0.0)
    assert not answer.accepted and answer.code == ResultCode.PRECONDITION_FAILED
    assert "not the" in answer.detail
    assert hold.holder == ""


def test_one_holder_at_a_time() -> None:
    hold = _held(SIM)
    answer = hold.request(ACQUIRE, OTHER, "/other", SIM, SIM, 1.0)
    assert not answer.accepted and RUN in answer.detail
    # The holder re-asserting is accepted.
    assert hold.request(ACQUIRE, RUN, NODE, SIM, SIM, 1.0).accepted


def test_only_the_holder_releases() -> None:
    hold = _held(SIM)
    assert not hold.request(RELEASE, OTHER, "", 0, SIM, 1.0).accepted
    assert hold.holder == RUN
    assert hold.request(RELEASE, RUN, "", 0, SIM, 1.0).accepted
    assert hold.holder == ""
    assert hold.refusal(REAL, OTHER, SIM) is None
    # Releasing nothing is not an error.
    assert hold.request(RELEASE, RUN, "", 0, SIM, 2.0).accepted


def test_a_malformed_request_is_refused() -> None:
    hold = ModeHold()
    assert not hold.request(ACQUIRE, "", NODE, SIM, SIM, 0.0).accepted
    assert not hold.request(ACQUIRE, RUN, "", SIM, SIM, 0.0).accepted
    assert not hold.request(0, RUN, NODE, SIM, SIM, 0.0).accepted
    assert not hold.request(9, RUN, NODE, SIM, SIM, 0.0).accepted
    assert hold.holder == ""


def test_a_hold_lapses_once_its_node_has_left_the_graph_for_the_ceiling() -> None:
    """A dead console never locks the twin for good; a live one is never lapsed."""
    hold = _held(REAL, now=0.0)
    # Seen on the graph: kept, however long it lasts.
    assert hold.lapse_if_gone({NODE, "/twin_boundary"}, 100.0) is None
    # Gone, but within the ceiling of the last sighting: kept.
    assert hold.lapse_if_gone({"/twin_boundary"}, 100.0 + UNSEEN_CEILING_S) is None
    assert hold.holder == RUN
    # Gone for longer: lapsed, and said.
    lapsed = hold.lapse_if_gone({"/twin_boundary"}, 100.0 + UNSEEN_CEILING_S + 0.1)
    assert lapsed is not None and NODE in lapsed and "left as it was" in lapsed
    assert hold.holder == ""
    assert hold.refusal(SIM, OTHER, REAL) is None


def test_a_holder_not_yet_discovered_is_given_the_ceiling() -> None:
    """Discovery may list a node late: a hold just taken is not lapsed at once."""
    hold = _held(SIM, now=5.0)
    assert hold.lapse_if_gone(set(), 5.0 + UNSEEN_CEILING_S) is None
    assert hold.lapse_if_gone(set(), 5.0 + UNSEEN_CEILING_S + 0.1) is not None


def test_node_names_are_fully_qualified() -> None:
    assert node_names([("fixed_program", "/"), ("console", "/cite/cell_b")]) == {
        "/fixed_program",
        "/cite/cell_b/console",
    }
