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

"""A second zone on one ROS graph is refused, and named (ADR-0056 decision 3).

The invariant was stated by that record and enforced by nothing. Two zones
started from one checkout share one domain — it is derived per checkout and
side, never per zone — and exactly one of the collisions was loud. The rest were
silent, and the worst of them is two `/clock` publishers from two independent
simulators.

These tests are in two halves on purpose. The rule is a pure function over a
list of names, so every case is stated exactly rather than raced for; the node
half asserts that the rule is actually asked, because a rule nothing calls is
indistinguishable from no rule, which is how this project's lint gate once
reported clean while linting zero packages.
"""

from __future__ import annotations

from cite_facility.artifacts import declared_zones
from cite_facility.model_info import ModelInfo
from cite_facility.occupancy import refusal, zones_already_on_the_graph
import pytest
import rclpy
from rclpy.lifecycle import TransitionCallbackReturn

#: A graph with one cell up: the names a `cell_a` bring-up puts on it, plus the
#: facility-scope names that are there whichever cell is running.
CELL_A_GRAPH = (
    "/cite/cell_a/arm_1/move_to",
    "/cite/cell_a/conveyor_1/command",
    "/cite/facility/model_version",
    "/cite/facility/get_model_version",
    "/cite/line/topology",
    "/tf_static",
    "/clock",
)

DECLARED = ("cell_a", "cell_b")


def test_another_declared_zone_on_the_graph_is_reported() -> None:
    assert zones_already_on_the_graph(CELL_A_GRAPH, ["cell_b"], DECLARED) == ["cell_a"]


def test_our_own_zone_is_not_foreign_to_itself() -> None:
    """The same-zone case is out of scope, deliberately and with a reason.

    CI brings one zone up twice in a row per run, and a rule that could not tell
    a teardown that has not finished from a second cell would turn a lingering
    process into a hard bring-up failure. `occupancy.py` records it; this pins
    that it stays that way rather than being "fixed" into a flake.
    """
    assert zones_already_on_the_graph(CELL_A_GRAPH, ["cell_a"], DECLARED) == []


def test_the_reserved_facility_scopes_are_not_zones() -> None:
    """`/cite/facility`, `/cite/line` and `/cite/twin` are there in every run.

    They are not listed anywhere in the rule — it asks which names belong to a
    DECLARED ZONE, so a scope that is not a zone of this facility never arises.
    """
    facility_only = [name for name in CELL_A_GRAPH if not name.startswith("/cite/cell_")]
    assert zones_already_on_the_graph(facility_only, ["cell_b"], DECLARED) == []


def test_a_scope_that_is_not_a_declared_zone_is_ignored() -> None:
    """A test fixture inventing `/cite/whatever/...` is not another cell."""
    assert zones_already_on_the_graph(["/cite/whatever/arm_1/move_to"], ["cell_b"], DECLARED) == []


def test_a_facility_declaring_one_zone_can_never_refuse() -> None:
    """The rule contributes nothing until a second zone is declared, by construction."""
    assert zones_already_on_the_graph(CELL_A_GRAPH, ["cell_a"], ["cell_a"]) == []


def test_an_empty_graph_refuses_nothing() -> None:
    assert zones_already_on_the_graph([], ["cell_b"], DECLARED) == []


def test_a_zone_name_that_is_a_prefix_of_another_is_not_a_false_match() -> None:
    """Match a whole zone name and not a prefix of one.

    `cell_b` and `cell_b2` are different cells, and `startswith` is why this is
    asked.
    """
    assert zones_already_on_the_graph(
        ["/cite/cell_b2/arm_1/move_to"], ["cell_b"], ["cell_b", "cell_b2"]
    ) == ["cell_b2"]
    assert zones_already_on_the_graph(
        ["/cite/cell_b/arm_1/move_to"], ["cell_b2"], ["cell_b", "cell_b2"]
    ) == ["cell_b"]


def test_the_refusal_names_the_zone_that_is_already_there() -> None:
    """Name the intruder, because "another zone is running" only sends a reader looking."""
    message = refusal(["cell_a"], ["cell_b"], "37")
    assert "cell_a" in message
    assert "cell_b" in message
    assert "37" in message
    # The three collisions a reader cannot be expected to know about.
    assert "/clock" in message
    assert "robot_description" in message


def test_the_zones_the_rule_is_given_are_the_generated_ones() -> None:
    """`declared_zones` is read from the bring-up plans, not listed in code.

    If it were listed, declaring a third zone in L0 would need an edit here and
    would silently not be refused until somebody made it.
    """
    zones = declared_zones()
    assert zones, "no bring-up plan found; the rule would have nothing to compare against"
    assert zones == sorted(zones)


# --- the node actually asks ---------------------------------------------------


@pytest.fixture()
def ros():
    rclpy.init()
    try:
        yield
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def _configure(node, zones: list[str], graph: tuple[str, ...]):
    node.set_parameters([rclpy.Parameter("zones", value=zones)])
    node.graph_names = lambda: list(graph)
    return node.on_configure(None)


def test_model_info_refuses_to_configure_beside_another_zone(ros) -> None:
    """Refuse to configure beside another zone.

    The bring-up stops here, with `simulation.launch.py` turning the FAILURE into
    a `Shutdown` that carries this node's own diagnosis.
    """
    node = ModelInfo()
    try:
        available = declared_zones()
        if len(available) < 2:
            pytest.skip("the facility declares one zone; there is no second one to collide")
        ours, theirs = available[1], available[0]
        graph = (f"/cite/{theirs}/arm_1/move_to", "/cite/facility/model_version")
        assert _configure(node, [ours], graph) == TransitionCallbackReturn.FAILURE, (
            "model_info configured beside another zone's names. Nothing then stops two "
            "cells sharing one /clock, one get_model_version and two different "
            "/robot_description publishers."
        )
    finally:
        node.destroy_node()


def test_model_info_configures_when_it_is_the_only_zone(ros) -> None:
    """Configure normally when this is the only zone.

    The other half: a refusal that fires on a cell running alone is worse than
    none, because it refuses every ordinary bring-up.
    """
    node = ModelInfo()
    try:
        ours = declared_zones()[0]
        graph = (f"/cite/{ours}/arm_1/move_to", "/cite/facility/model_version", "/clock")
        assert _configure(node, [ours], graph) == TransitionCallbackReturn.SUCCESS
    finally:
        node.destroy_node()


def test_the_node_reads_the_real_graph_rather_than_an_empty_list(ros) -> None:
    """Read the real graph rather than an empty list.

    `graph_names` is stubbed above; this is the tripwire for it being stubbed in
    production too.

    It asserts only that the node's own names come back — which they must, since
    it has just created none of its interfaces but the graph carries the
    parameter services every node has.
    """
    node = ModelInfo()
    try:
        names = node.graph_names()
        assert any("model_info" in name for name in names), names
    finally:
        node.destroy_node()
