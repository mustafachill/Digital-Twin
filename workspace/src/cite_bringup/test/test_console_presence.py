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

"""One operator surface per pair: a terminal client sees the console (N-01, ADR-0071).

`RosCell.console_refusal` on a live graph of its own domain: the twin's latched
mode is published here as the boundary publishes it, and the console's latched
`ConsoleState` as `cell_console` does. Nothing here moves anything.
"""

from __future__ import annotations

import os
import time

from cite_bringup.plan import default_plan_path, load
import cite_bringup.program.cell as cell_module
from cite_bringup.program.cell import RosCell, TERMINAL_NODE
from cite_bringup.program.steps import StepFailed
from cite_interfaces.msg import ConsoleState, RobotState, TwinMode
from cite_interfaces.qos import LATCHED
import pytest
import rclpy

DOMAIN = 100 + os.getpid() % 100


@pytest.fixture(scope="module")
def graph():
    rclpy.init(domain_id=DOMAIN)
    try:
        twin = rclpy.create_node("fake_twin_boundary")
        reader = object.__new__(RosCell)
        reader.node = rclpy.create_node("terminal_client")
        reader._via = "twin"
        reader._state_topic = "/cite/test_presence/arm/state"
        yield twin, reader
        twin.destroy_node()
        reader.node.destroy_node()
    finally:
        rclpy.try_shutdown()


#: How long a test waits for the graph to show what it just created, in wall
#: seconds. A hang detector: each wait ends once the graph shows it.
GRAPH_S = 10.0


def _until_on_graph(predicate) -> None:
    deadline = time.monotonic() + GRAPH_S
    while not predicate():
        assert time.monotonic() < deadline, "the graph never showed it"
        time.sleep(0.01)


def _twin_in(node, mode: int):
    publisher = node.create_publisher(TwinMode, TwinMode.TOPIC, LATCHED)
    publisher.publish(TwinMode(mode=mode))
    return publisher


def test_a_console_awaiting_the_operator_refuses_a_terminal_client(graph) -> None:
    """N-01 (c): the console's own AWAITING_OPERATOR, in SIM, is a console holding the cell."""
    twin, reader = graph
    modes = _twin_in(twin, TwinMode.MODE_SIM)
    console = twin.create_publisher(ConsoleState, "/cite/test_a/console/state", LATCHED)
    console.publish(ConsoleState(state=ConsoleState.AWAITING_OPERATOR, busy=True))
    try:
        refusal = reader.console_refusal("/cite/test_a/console/state")
    finally:
        twin.destroy_publisher(console)
        twin.destroy_publisher(modes)
    assert refusal is not None
    assert "AWAITING_OPERATOR" in refusal and "Use the panel" in refusal


def test_without_a_console_a_terminal_client_is_let_through(graph) -> None:
    twin, reader = graph
    modes = _twin_in(twin, TwinMode.MODE_SIM)
    try:
        assert reader.console_refusal("/cite/test_b/console/state") is None
    finally:
        twin.destroy_publisher(modes)


def test_with_no_twin_heard_nothing_is_taken_for_no_console(graph, monkeypatch) -> None:
    """An absence read before the twin is heard is never read as 'no console'."""
    _twin, reader = graph
    monkeypatch.setattr(cell_module, "SERVER_WAIT_S", 0.3)
    with pytest.raises(StepFailed, match="no TwinMode"):
        reader.console_refusal("/cite/test_c/console/state")


def test_a_console_publisher_that_has_said_nothing_yet_still_refuses(graph) -> None:
    """S-01/R-03: the publisher-only path - present on the graph, no message arrived."""
    twin, reader = graph
    topic = "/cite/test_d/console/state"
    console = twin.create_publisher(ConsoleState, topic, LATCHED)
    modes = _twin_in(twin, TwinMode.MODE_SIM)
    try:
        # The precondition this path exists for: the graph knows the publisher.
        _until_on_graph(lambda: reader.node.count_publishers(topic) > 0)
        refusal = reader.console_refusal(topic)
    finally:
        twin.destroy_publisher(modes)
        twin.destroy_publisher(console)
    assert refusal is not None and "Use the panel" in refusal
    # Nothing was heard, so no state is claimed for it.
    assert "(it is" not in refusal


def test_via_the_plant_a_console_is_seen_without_any_twin(graph) -> None:
    """R-05: `--via plant` asks too, witnessed by the arm's own latched state."""
    twin, reader = graph
    reader._via = "plant"
    state = twin.create_publisher(RobotState, reader._state_topic, LATCHED)
    state.publish(RobotState())
    console = twin.create_publisher(ConsoleState, "/cite/test_e/console/state", LATCHED)
    console.publish(ConsoleState(state=ConsoleState.READY))
    try:
        assert reader.console_refusal("/cite/test_f/console/state") is None
        refusal = reader.console_refusal("/cite/test_e/console/state")
    finally:
        reader._via = "twin"
        twin.destroy_publisher(console)
        twin.destroy_publisher(state)
    assert refusal is not None and "READY" in refusal


def test_via_the_plant_with_no_arm_heard_nothing_is_taken_for_no_console(
    graph, monkeypatch
) -> None:
    _twin, reader = graph
    reader._via = "plant"
    monkeypatch.setattr(cell_module, "SERVER_WAIT_S", 0.3)
    try:
        with pytest.raises(StepFailed, match="no RobotState"):
            reader.console_refusal("/cite/test_g/console/state")
    finally:
        reader._via = "twin"


def test_the_console_names_a_terminal_program_client_on_its_graph(graph) -> None:
    """S-01: the console finds a terminal run by the one name `RosCell` gives it."""
    from cite_bringup.program.console import CellConsole

    console = CellConsole(load(default_plan_path("cell_b")))
    try:
        assert console._terminal_client() is None
        terminal = rclpy.create_node(TERMINAL_NODE)
        try:
            _until_on_graph(lambda: console._terminal_client() is not None)
            assert console._terminal_client() == f"/{TERMINAL_NODE}"
        finally:
            terminal.destroy_node()
        _until_on_graph(lambda: console._terminal_client() is None)
    finally:
        console.destroy_node()
