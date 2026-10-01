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

"""Nothing moves before the recovery policy has chosen (ADR-0037, ADR-0038).

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
import re
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


def _generated_fault_branch() -> list[str]:
    """Return the leaf names the root-tree generator emits into its fault branch.

    Read out of `line_tree.hpp`, which is where the branch is written: the root
    tree is generated in C++ and there is no shipped XML file to parse. The branch
    is a fixed literal — it carries no data at all, which is asserted from the
    other side in `test_line_logic.cpp` against the generated output — so reading
    the literal and reading the output are the same set of names.

    This lives here rather than in that gtest so that `MOTION_LEAVES` stays
    written down once. Copying the set into C++ to assert the same rule would be a
    value in two places, and the copy is the one that would go stale.
    """
    configured = os.environ.get("CITE_LINE_TREE_HEADER")
    assert configured, (
        "CITE_LINE_TREE_HEADER is unset. CMakeLists.txt sets it for this test, so run it "
        "through ./scripts/test rather than invoking pytest on this file directly"
    )
    source = Path(configured).read_text()
    block = re.search(r'<Sequence name=\\"fault\\">(.*?)</Sequence>', source, re.DOTALL)
    assert block, (
        "the root-tree generator emits no fault branch, so a station that escalates "
        "still ends the coordinator's process (ADR-0038)"
    )
    return re.findall(r"<([A-Za-z_][A-Za-z0-9_]*)\s*/?>", block.group(1))


def test_the_fault_branch_commands_no_motion() -> None:
    """A stopped line commands no arm, and the belts are `StopAll`'s alone.

    ADR-0038 decision 2: every station subtree that was RUNNING has already been
    halted by the root `Parallel` before the first leaf of this branch runs, and
    halting a skill leaf cancels its goal. So there is nothing left to stop, and
    anything commanded here would be NEW motion after a failure the policy has
    already refused to retry — the same defect `test_the_policy_is_the_first_leaf…`
    guards one level down, at the point where there is no policy left to consult.

    `ResumeBelt` is in `MOTION_LEAVES` and is the one that would look most
    reasonable here: it is how a stopped belt is started, and a stopped line is
    exactly where somebody will want to start one. It must not be here. A station
    that failed may not have picked, so running its belt puts a work-piece on the
    floor — and `AwaitReArm` refuses precisely because the belt is stopped, which
    is a refusal, not a to-do list.
    """
    commanded = [leaf for leaf in _generated_fault_branch() if leaf in MOTION_LEAVES]
    assert not commanded, (
        "the fault branch commands motion on a line that has just stopped without "
        f"anything classifying why: {commanded}"
    )


def test_the_fault_branch_consults_no_policy_because_it_is_downstream_of_one() -> None:
    """`RecoverFromFailure` belongs to a station, and this branch is the line's.

    The classification has already happened — it is what made the station return
    FAILURE — and a second consultation here would be a second author for the
    answer. `OnFault` reads the station's recorded code and reason rather than
    re-deriving them, which is why it is a recorder and not a decider.
    """
    assert POLICY_LEAF not in _generated_fault_branch()


def test_the_tick_loop_is_guarded_against_a_leaf_that_throws() -> None:
    """Returning is not the only way out of a leaf.

    The fault branch's rule is about statuses only. `line_fault.hpp` says no leaf
    in it may return `FAILURE`, because a `FAILURE` ends the coordinator's tick
    loop and reinstates the process exit ADR-0038 removes. That rule is necessary
    and not sufficient: an exception thrown out of a `tick()` walks past every
    status it is about, and `StopAll` calls `publish()` once per belt, which can
    throw `RCLError`. Out of `main` an uncaught one is `std::terminate` — a signal
    death, with nothing halted, no goal cancelled and an exit status that says
    nothing, which is strictly worse than the exit that was removed.

    Read as source text rather than driven, and that is a real limit on what this
    proves: it asserts the guard is present, not that it behaves. The tick loop
    lives in `main`, which no harness in this package can enter, so the behaviour
    is unasserted and this is what stops the guard being deleted silently.
    """
    configured = os.environ.get("CITE_LINE_ORCHESTRATOR_SRC")
    assert configured, (
        "CITE_LINE_ORCHESTRATOR_SRC is unset. CMakeLists.txt sets it for this test, so "
        "run it through ./scripts/test rather than invoking pytest on this file directly"
    )
    source = Path(configured).read_text()
    loop = source.find("while (rclcpp::ok() && outcome == BT::NodeStatus::RUNNING)")
    assert loop != -1, "the tick loop is no longer where this test can find it"

    before = source[:loop]
    guard = before.rfind("try {")
    assert guard != -1, (
        "the tick loop is not inside a try block, so an exception out of a leaf "
        "terminates the process instead of halting the tree and exiting 1"
    )
    assert "catch" not in before[guard:], (
        "the last try block before the tick loop is already closed, so the loop is "
        "outside it and an exception out of a leaf still terminates the process"
    )
    assert "catch (const std::exception &" in source[loop:], (
        "nothing catches what a leaf throws out of the tick loop"
    )


def test_the_line_state_is_published_on_the_tick_thread_after_the_tick() -> None:
    """The leg of ADR-0039's stall predicate that no unit test can drive.

    `stalled_stations` reports a station that is `IDLE` or `WAITING` with its
    inbound belt stopped and every stopping edge already consumed. Condition 4
    closes the interval between an edge arriving and the station taking it. It
    does **not** close the interval between the station taking it and
    `SetStationState` writing `WORKING` — in which a perfectly healthy station
    satisfies all four conditions at once.

    What closes that one is where `publish()` runs: on the tick thread, after
    `tickOnce()` returns, inside the same `lock_guard`. So no publication can land
    between `AwaitTrigger` taking the edge and the end of that tick, and BT.CPP
    reaches `SetStationState` before the tick ends.

    Move `publish()` onto a timer, or out of the locked section, and the predicate
    becomes a false positive on **every arrival** — which `continuous_line` aborts
    on, so a healthy line would fail the scenario naming a station that is fine.

    `RunningLine.ALineIsNeverReportedStalledWhileAPartIsArriving` covers the tree
    half of the invariant and is mutation-checked. It cannot cover this half: the
    tick loop is in `main`, so that test arranges the ordering itself rather than
    reading the coordinator's. Hence source text, and the same limit applies as to
    the guard above — this asserts the ordering is written, not that it behaves.
    """
    configured = os.environ.get("CITE_LINE_ORCHESTRATOR_SRC")
    assert configured, (
        "CITE_LINE_ORCHESTRATOR_SRC is unset. CMakeLists.txt sets it for this test, so "
        "run it through ./scripts/test rather than invoking pytest on this file directly"
    )
    source = Path(configured).read_text()
    loop = source.find("while (rclcpp::ok() && outcome == BT::NodeStatus::RUNNING)")
    assert loop != -1, "the tick loop is no longer where this test can find it"

    # The body of the loop, up to the sleep that ends it. Everything asserted below
    # has to be inside it, so the slice is the assertion's scope.
    body_end = source.find("tree.sleep(tick_period)", loop)
    assert body_end != -1, "the tick loop no longer ends on tree.sleep, so this slice is wrong"
    body = source[loop:body_end]

    lock = body.find("std::lock_guard<std::mutex> lock(*tick_mutex)")
    tick = body.find("tree.tickOnce()")
    publish = body.find("maintenance.publish()")
    assert lock != -1, (
        "the tick loop body no longer takes the tick mutex, so the tick and the report "
        "are no longer one critical section (ADR-0039 correction 3)"
    )
    assert tick != -1, "the tick loop body no longer calls tickOnce()"
    assert publish != -1, (
        "the tick loop body no longer publishes LineState. If publication moved to a "
        "timer it is off the tick thread, and ADR-0039's stall predicate can then be "
        "sampled between a station consuming its edge and SetStationState writing "
        "WORKING — a false positive on every arrival"
    )
    assert lock < tick < publish, (
        "the order in the tick loop is no longer lock -> tickOnce -> publish. The stall "
        "predicate is only safe when no publication can land between AwaitTrigger taking "
        "an edge and the end of that same tick (ADR-0039 correction 3)"
    )

    # And the lock is STILL HELD at the publish. The `lock_guard` is scoped, so it is
    # released by the brace that closes the block it was declared in: walk the depth
    # from the lock to the publish and require it never to go negative.
    depth = 0
    for character in body[lock:publish]:
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            assert depth >= 0, (
                "the block holding the tick mutex closes before LineState is published, "
                "so the report is outside the critical section that makes it consistent "
                "with the tick it describes"
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
