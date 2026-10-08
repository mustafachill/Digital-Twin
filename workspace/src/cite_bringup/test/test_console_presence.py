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

import cite_bringup.program.cell as cell_module
from cite_bringup.program.cell import RosCell
from cite_bringup.program.steps import StepFailed
from cite_interfaces.msg import ConsoleState, TwinMode
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
        yield twin, reader
        twin.destroy_node()
        reader.node.destroy_node()
    finally:
        rclpy.try_shutdown()


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
