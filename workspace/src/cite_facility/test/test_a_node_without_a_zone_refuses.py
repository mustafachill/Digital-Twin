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

"""A facility node that was never told which cell it serves refuses to start.

WHAT THIS CATCHES, stated as the edit rather than as the rule. Someone puts
`self.declare_parameter("zone", "cell_a")` back into one of these four nodes —
it is a one-word change, it makes a launch that forgot the parameter work again,
and every unit test of `require_zone` still passes, because a node holding
`"cell_a"` never calls it with an empty string. Then `./scripts/sim --zone cell_b`
brings up `cell_b` with `cell_a`'s planning scene: twelve collision objects three
metres away in +y, `cell_b`'s own table, pedestal, conveyor and beams absent, and
`_verify` reading the objects back and succeeding because they were applied. The
first `Pick` plans a Pilz straight line onto a surface MoveIt cannot see.

So these tests assert on the NODE and not on the rule: with nothing supplying the
parameter, configuration must fail. A restored default makes configuration
succeed, and every test here fails.

`rclpy` is initialised and the transition callbacks are called directly. Nothing
is launched and no executor runs: `on_configure` is an ordinary method, and the
refusal happens on its first statement, before any interface is created.
"""

from __future__ import annotations

from cite_facility.artifacts import ArtifactError, require_zone, require_zones
from cite_facility.frame_server import FrameServer
from cite_facility.model_info import ModelInfo
from cite_facility.planning_scene_loader import PlanningSceneLoader
from cite_facility.topology_server import TopologyServer
import pytest
import rclpy
from rclpy.lifecycle import TransitionCallbackReturn

#: The nodes that read a zone, and how each one is asked to use it. Named rather
#: than discovered: a test that walks the package passes when a node stops being
#: in it, which is the failure mode this file exists to prevent.
MANAGED = (FrameServer, ModelInfo, TopologyServer)


@pytest.fixture()
def ros():
    """Provide a context for the nodes, and tear it down either way."""
    rclpy.init()
    try:
        yield
    finally:
        if rclpy.ok():
            rclpy.shutdown()


@pytest.mark.parametrize("node_type", MANAGED, ids=lambda t: t.__name__)
def test_a_managed_node_given_no_zone_fails_to_configure(ros, node_type) -> None:
    """`on_configure` returns FAILURE, which is what stops the launch.

    `simulation.launch.py` registers a handler on `configuring -> unconfigured`
    that emits `Shutdown` with the node's own diagnosis, so a FAILURE here is a
    bring-up that stops and says why rather than a cell that comes up serving
    another zone's answers.
    """
    node = node_type()
    try:
        assert node.on_configure(None) == TransitionCallbackReturn.FAILURE, (
            f"{node_type.__name__} configured with no zone supplied. Its `zone` "
            "parameter has a default again, so a launch that never names a zone "
            "brings this node up serving whichever cell that default names."
        )
    finally:
        node.destroy_node()


class _RecordedLogger:
    """Stands in for the node's own logger, and keeps what was logged at ERROR.

    The node is real and `load()` runs for real; only the sink is replaced. It is
    replaced because the return code alone cannot answer this file's question —
    see `test_the_planning_scene_loader_given_no_zone_refuses_to_load`.
    """

    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, message: object, **_kwargs: object) -> bool:
        self.errors.append(str(message))
        return True

    def info(self, message: object, **_kwargs: object) -> bool:
        return True

    def warn(self, message: object, **_kwargs: object) -> bool:
        return True

    def debug(self, message: object, **_kwargs: object) -> bool:
        return True


def _the_refusal_text() -> str:
    """What `require_zone` says when it refuses, taken from `require_zone`.

    Not restated here (P1), and not restated for a second reason that matters
    more: a copy of the sentence would let this test keep passing against a
    diagnosis the node no longer produces. Asking the rule for its own words ties
    the two together, which is the same wiring
    `test_the_rule_the_nodes_call_is_the_one_that_refuses` asserts below.
    """
    try:
        require_zone("")
    except ArtifactError as exc:
        return str(exc)
    raise AssertionError("require_zone('') did not refuse; see the test at the foot of this file")


def test_the_planning_scene_loader_given_no_zone_refuses_to_load(ros) -> None:
    """The same rule for the one node here that is not managed.

    It is the node whose silent success is worst: it APPLIES a scene and then
    verifies it, so a wrong zone's objects are read back successfully and the
    arm plans against a room it is not in.

    **THIS ASSERTS THE DIAGNOSIS AND NOT THE RETURN CODE, and the difference is
    the whole value of the test.** `load()` returns 1 on the zone refusal and
    also on `if not apply_client.wait_for_service(...)` — and in a unit-test
    environment no `move_group` ever answers, so `load() != 0` is satisfied by a
    node that never looked at its zone at all. Restoring
    `self.declare_parameter("zone", "cell_a")` — the exact edit this file's
    docstring names — left that assertion passing; what surfaced the mutation was
    the ament ctest wall-clock timeout, which reports "timeout" rather than a
    diagnosis and stops working the moment anyone lengthens `TIMEOUT` or shortens
    `SERVICE_DEADLINE_S`.

    `require_zone`'s text is the one message the service-timeout path cannot
    produce, so requiring it is what discriminates the two.
    """
    node = PlanningSceneLoader()
    recorder = _RecordedLogger()
    node.get_logger = lambda: recorder  # type: ignore[method-assign]
    try:
        code = node.load()
        assert code != 0, (
            "PlanningSceneLoader loaded a scene with no zone supplied; its `zone` "
            "parameter has a default again and it will apply that cell's collision "
            "objects into whichever cell is actually running"
        )
        refusal = _the_refusal_text()
        assert any(refusal in logged for logged in recorder.errors), (
            "PlanningSceneLoader failed, but not because it was given no zone: it "
            f"logged {recorder.errors!r}, none of which carries what `require_zone` "
            "says. A `zone` default has probably been restored and this is the "
            "120 s move_group service deadline expiring instead — a failure that "
            "looks identical in the exit code and means the opposite."
        )
    finally:
        node.destroy_node()


def test_the_planning_scene_loader_declares_no_zone_of_its_own(ros) -> None:
    """The diagnosis for the test above, and the one that fails instantly.

    The managed nodes have had this since this file was written; the loader was
    left out because `MANAGED` drives `on_configure` and the loader has no
    lifecycle. The check itself has nothing to do with lifecycle, and without it
    the loader was the one node here whose restored default had to be inferred
    from behaviour rather than read off the parameter.
    """
    node = PlanningSceneLoader()
    try:
        declared = node.get_parameter("zone").get_parameter_value().string_value
        assert not declared, (
            f"PlanningSceneLoader declares zone default {declared!r}. A facility node "
            "may not name a cell it was not given (ADR-0056 decision 4), and this one "
            "applies that cell's collision objects into whichever cell is running."
        )
    finally:
        node.destroy_node()


@pytest.mark.parametrize("node_type", MANAGED, ids=lambda t: t.__name__)
def test_a_managed_node_declares_no_zone_of_its_own(ros, node_type) -> None:
    """Read from the parameter rather than from the source text.

    The test above is the behavioural one and this is its diagnosis: it names
    the default that came back, so the failure reads as "someone restored
    'cell_a'" instead of "configure returned the wrong thing".
    """
    node = node_type()
    try:
        parameter = node.get_parameter("zones" if node_type is ModelInfo else "zone")
        value = parameter.get_parameter_value()
        declared = list(value.string_array_value) or [value.string_value]
        assert not any(declared), (
            f"{node_type.__name__} declares zone default {declared!r}. A facility node "
            "may not name a cell it was not given (ADR-0056 decision 4)."
        )
    finally:
        node.destroy_node()


@pytest.mark.parametrize("node_type", MANAGED, ids=lambda t: t.__name__)
def test_a_named_zone_still_configures(ros, node_type) -> None:
    """The other half: the refusal must reject an absence, not every value.

    Without this, deleting the parameter read entirely would pass every
    assertion above while making the nodes serve nothing at all.
    """
    node = node_type()
    try:
        name = "zones" if node_type is ModelInfo else "zone"
        value = ["cell_a"] if node_type is ModelInfo else "cell_a"
        node.set_parameters([rclpy.Parameter(name, value=value)])
        if node_type is ModelInfo:
            # Stood down so that this test answers the question it asks. The
            # other rule `model_info.on_configure` applies is "no other zone is
            # on this graph", and ctest runs many nodes on one domain; that rule
            # has its own file, `test_one_zone_at_a_time.py`.
            node.graph_names = list
        assert node.on_configure(None) == TransitionCallbackReturn.SUCCESS, (
            f"{node_type.__name__} refuses a zone it was given; the rule is about an "
            "unnamed zone and this one is named"
        )
    finally:
        node.destroy_node()


def test_the_rule_the_nodes_call_is_the_one_that_refuses() -> None:
    """The two are wired together, so neither can be satisfied on its own.

    A node that stopped calling `require_zone` and hand-rolled its own check
    would still pass the behavioural tests above; this is what makes the pair
    one fact instead of two.
    """
    with pytest.raises(ArtifactError):
        require_zone("")
    with pytest.raises(ArtifactError):
        require_zones([""])
