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

"""Nothing moves before the recovery policy has chosen (ADR-0037).

WHY THIS IS A TEST ABOUT ORDER. The defect it guards is not a wrong value, it is
a wrong sequence. `line_station.xml` used to run `MoveToHome` as the first leaf
of its recovery branch, so a station that failed planned and drove a fresh
trajectory, unattended, before `RecoverFromFailure` had been reached at all. Two
policy rows say that must not happen: `SAFETY_BLOCKED`, whose own comment says L4
must never treat a refusal as a transient, and `HARDWARE_FAULT`, whose comment
says the cell is not in a state to be commanded — after which the cell was
commanded.

A test that only checked the station's final state would pass with the leaves in
either order, which is why this reads the shipped XML instead. It is the same
technique `test_indexed_belts.py` already uses on this tree, and it costs
milliseconds rather than a seven-minute scenario.

It is deliberately NOT a test that the classification is right, or that a real
abort reaches it. Those are `test_motion_end.cpp` and the L3 contract tests. This
answers one question: given a recovery branch, is the policy consulted before
anything is commanded?
"""

import os
from pathlib import Path
import xml.etree.ElementTree as ElementTree

import pytest

#: Every leaf that can command an arm or a belt. A leaf added here that moves
#: something and is not in this set would slip past the ordering rule below, so
#: the set is stated once and both trees are checked against it.
#:
#: `ReleaseStationClaims` and `SetStationState` are deliberately absent:
#: releasing a claim and recording a state command nothing at all. Whether
#: releasing a claim is the RIGHT thing to do after an escalation is a separate
#: question, decided in `line_station.xml` and asserted below.
MOTION_LEAVES = frozenset(
    {
        "MoveToHome",
        "PickAt",
        "PlaceAt",
        "TransferTo",
        "DetectAt",
        "ResumeBelt",
    }
)

POLICY_LEAF = "RecoverFromFailure"

#: BT.CPP composites that stop at their first failing child. The recovery branch
#: must be one of them: `RecoverFromFailure` answers ESCALATE and STOP_LINE with
#: FAILURE, and that FAILURE is what makes every later leaf part of the retry.
HALTS_ON_FAILURE = frozenset({"Sequence", "SequenceWithMemory", "ReactiveSequence"})

#: Decorators that turn a child's FAILURE into something else. One of these
#: wrapped around the policy leaf would hide a refusal from the branch that has
#: to obey it.
KEEPS_GOING_AFTER_FAILURE = frozenset(
    {"ForceSuccess", "Inverter", "RetryUntilSuccessful", "KeepRunningUntilFailure"}
)


def _tree(variable: str) -> ElementTree.Element:
    """Parse the tree the package installs, named by the environment.

    Handed in by CMake rather than found by walking upwards, so the file under
    test is the one that ships and not a copy that stopped tracking it.
    """
    path = os.environ.get(variable)
    if not path:
        pytest.skip(f"{variable} is not set; run this through colcon")
    return ElementTree.parse(Path(path)).getroot()


def _recover_branch(root: ElementTree.Element) -> ElementTree.Element:
    for element in root.iter():
        if element.get("name") == "recover":
            return element
    raise AssertionError("no branch named 'recover' in the tree")


def _leaf_names(branch: ElementTree.Element) -> list[str]:
    return [child.tag for child in branch]


def test_the_policy_is_the_first_leaf_of_the_station_recovery_branch() -> None:
    branch = _recover_branch(_tree("CITE_STATION_TREE_XML"))
    leaves = _leaf_names(branch)

    assert leaves, "the recovery branch has no leaves at all"
    assert leaves[0] == POLICY_LEAF, (
        "the recovery branch must consult the policy before it does anything else; "
        f"its first leaf is {leaves[0]}"
    )


def test_no_station_motion_is_commanded_before_the_policy_has_answered() -> None:
    branch = _recover_branch(_tree("CITE_STATION_TREE_XML"))
    leaves = _leaf_names(branch)
    decided_at = leaves.index(POLICY_LEAF)

    commanded_first = [
        (position, leaf)
        for position, leaf in enumerate(leaves)
        if leaf in MOTION_LEAVES and position < decided_at
    ]
    assert not commanded_first, (
        "these leaves command something before the recovery policy has chosen, so a "
        f"SAFETY_BLOCKED or HARDWARE_FAULT station moves anyway: {commanded_first}"
    )


def test_nothing_after_the_policy_runs_when_the_policy_refuses() -> None:
    """The recovery branch must abandon itself on ESCALATE and on STOP_LINE.

    `RecoverFromFailure` returns FAILURE on both, so every leaf placed after it
    is on the RETRY PATH and reachable on no other answer. That is the decided
    behaviour, and this is the property that delivers it: a composite that went
    on ticking after a FAILURE — a `Fallback`, a `ForceSuccess` wrapper, a
    `Parallel` — would give a station the policy refused a way to keep acting.

    Stated as a rule about answers rather than as `tag == "Sequence"`, because
    what matters is what a refused station does, not which composite happens to
    express it.
    """
    branch = _recover_branch(_tree("CITE_STATION_TREE_XML"))
    assert branch.tag in HALTS_ON_FAILURE, (
        f"a {branch.tag} does not stop at its first failing child, so a station the "
        "policy refused would go on running the leaves after it"
    )
    for child in branch:
        assert child.tag not in KEEPS_GOING_AFTER_FAILURE, (
            f"{child.tag} would swallow the policy's refusal and let the branch continue"
        )


def test_clearing_the_arm_is_reachable_only_on_the_retry_path() -> None:
    # The justification for clearing the arm — a station that failed mid-cycle
    # may have left it somewhere the next attempt would collide with — argues for
    # doing it INSIDE the retry. If the answer is escalate there is no next
    # attempt to protect.
    branch = _recover_branch(_tree("CITE_STATION_TREE_XML"))
    leaves = _leaf_names(branch)
    assert "MoveToHome" in leaves, "the retry path no longer clears the arm at all"
    assert leaves.index("MoveToHome") > leaves.index(POLICY_LEAF)


def test_the_claims_are_given_up_on_the_retry_path_and_on_no_other_answer() -> None:
    """The decision this file's comment used to state backwards.

    An earlier comment in `line_station.xml` said `ReleaseStationClaims` "runs on
    BOTH answers". It cannot, and the tree does not: it sits after the policy in
    a composite that stops at the first failure, so an escalating station keeps
    everything it holds.

    That is the decided behaviour, not an accident of the ordering. A station
    that escalates performs no motion, so its arm is still standing in the frames
    it reached into, and telling the arbiter they are free would be a claim about
    the world that the failure has just contradicted. What the station does with
    them once an operator has reset it is deliberately open (ADR-0037 decision
    5); what it must not do is give them up while nobody has looked at it.

    The consequence is asserted where it can be observed —
    `test_line_nodes.cpp`'s `AStationThatEscalatesCommandsNothingAndKeepsWhatItIsStandingIn`
    drives the shipped tree and reads the arbiter. This asserts the structure
    that produces it, so that a leaf moved above the policy fails here rather
    than only there.
    """
    branch = _recover_branch(_tree("CITE_STATION_TREE_XML"))
    leaves = _leaf_names(branch)
    assert "ReleaseStationClaims" in leaves, (
        "the retry path no longer gives the frames back, so a retrying station starves "
        "the rest of the line"
    )
    assert leaves.index("ReleaseStationClaims") > leaves.index(POLICY_LEAF), (
        "the claims are released before the policy has answered, so an escalating "
        "station gives up the frames its arm is still standing in"
    )


def test_the_single_station_cycle_commands_nothing_when_it_gives_up() -> None:
    # `station_cycle.xml` has no `<Repeat>`, so its recover branch has no next
    # attempt to protect and consults no policy at all — `ReportBlocked` logs and
    # returns SUCCESS. Clearing the arm there is an unattended motion after an
    # undiagnosed failure, bought for nothing. The nominal branch already begins
    # with `MoveToHome`, so a cycle that is run again clears the arm inside the
    # attempt, which is where it belongs.
    branch = _recover_branch(_tree("CITE_STATION_CYCLE_XML"))
    moving = [leaf for leaf in _leaf_names(branch) if leaf in MOTION_LEAVES]
    assert not moving, (
        "the single-station recovery branch commands motion after a failure it has not "
        f"classified: {moving}"
    )


def test_the_nominal_cycle_still_clears_the_arm_before_it_works() -> None:
    # The other half of the change above: removing `MoveToHome` from the recover
    # branch is only safe because the nominal branch opens with it.
    root = _tree("CITE_STATION_CYCLE_XML")
    nominal = next(
        (element for element in root.iter() if element.get("name") == "nominal"), None
    )
    assert nominal is not None, "no branch named 'nominal' in station_cycle.xml"
    assert _leaf_names(nominal)[0] == "MoveToHome"
