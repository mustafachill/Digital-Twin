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

`RosCell.simulated_side_refusal` (S-02r) on the same graph: a simulated
clock published continuously, as Gazebo's bridge does, and none.
"""

from __future__ import annotations

import os
import threading
import time

from cite_bringup.plan import default_plan_path, load
import cite_bringup.program.cell as cell_module
from cite_bringup.program.cell import RosCell, TERMINAL_NODE, terminal_node_name
from cite_bringup.program.steps import StepFailed
from cite_interfaces.msg import ConsoleState, RobotState, TwinMode, TwinSides
from cite_interfaces.qos import LATCHED, SENSOR
from cite_interfaces.srv import Holding, HoldMode
import pytest
import rclpy
from rosgraph_msgs.msg import Clock

#: The private band `cite_runtime`'s signal test established: valid on Linux,
#: and disjoint from every cell's domain (1 to 100, `scripts/_lib.sh`) and from
#: every launch test's, so this file never joins a live pair nor a launch test.
PRIVATE_DOMAIN_BAND = range(215, 233)
DOMAIN = PRIVATE_DOMAIN_BAND[os.getpid() % len(PRIVATE_DOMAIN_BAND)]


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

    console = CellConsole(load(default_plan_path("cell_b")), ("plant", "counterpart"))
    try:
        assert console._terminal_client() is None
        # Named as a terminal run names its cell: the prefix and its own suffix.
        name = terminal_node_name()
        terminal = rclpy.create_node(name)
        try:
            _until_on_graph(lambda: console._terminal_client() is not None)
            assert console._terminal_client() == f"/{name}"
        finally:
            terminal.destroy_node()
        _until_on_graph(lambda: console._terminal_client() is None)
    finally:
        console.destroy_node()


# --- S-02r: `--via plant` asks the graph for a simulated side ----------------


def test_a_simulated_clock_on_the_domain_is_a_simulated_side(graph, monkeypatch) -> None:
    """S-02r: heard continuously, as Gazebo's bridge publishes it, the clock lets the run on."""
    twin, reader = graph
    # A name of this test's own, so a copy of another clock test sharing the
    # band cannot answer for it; the launch tests tie the real name to Gazebo.
    topic = "/test_s02r/clock_published"
    monkeypatch.setattr(cell_module, "SIMULATED_CLOCK", topic)
    publisher = twin.create_publisher(Clock, topic, SENSOR)
    done = threading.Event()

    def tick() -> None:
        while not done.is_set():
            publisher.publish(Clock())
            done.wait(0.01)

    ticking = threading.Thread(target=tick, daemon=True)
    ticking.start()
    try:
        assert reader.simulated_side_refusal() is None
    finally:
        done.set()
        ticking.join()
        twin.destroy_publisher(publisher)


def test_no_simulated_clock_on_the_domain_refuses(graph, monkeypatch) -> None:
    """S-02r: a physical side publishes no simulated clock, so the run is refused."""
    _twin, reader = graph
    monkeypatch.setattr(cell_module, "SIMULATED_CLOCK", "/test_s02r/clock_absent")
    monkeypatch.setattr(cell_module, "SERVER_WAIT_S", 0.3)
    refusal = reader.simulated_side_refusal()
    assert refusal is not None
    assert "/test_s02r/clock_absent" in refusal and "simulated side" in refusal
    # The probe's subscription does not outlive the question.
    assert reader.node.count_subscribers("/test_s02r/clock_absent") == 0


# --- T-01: the console's belts are the RUNNING sides', said of them alone ------


def test_a_plant_alone_console_commands_and_names_the_plants_belt_alone(
    graph, monkeypatch
) -> None:
    """T-01: a side the pair did not start is neither commanded nor mentioned."""
    import cite_bringup.program.console as console_module

    asked: list = []

    def set_belts(plan, stop, say, sides=None, **kwargs):
        asked.append(sides)
        return True

    monkeypatch.setattr(console_module, "set_belts", set_belts)
    console = console_module.CellConsole(load(default_plan_path("cell_b")), ("plant",))
    try:
        assert console.on_configure(None) == console_module.TransitionCallbackReturn.SUCCESS
        assert console.machine._set_belts(True, lambda text: None, None, None)
        assert asked == [["plant"]]
    finally:
        console.destroy_node()


# --- R-01, S-01, S-02: the cell asks the twin, on its own domain only ---------


class _Twin:
    """A twin boundary's Holding, HoldMode and TwinSides, served on this domain."""

    def __init__(self, holding: Holding.Response) -> None:
        from rclpy.executors import SingleThreadedExecutor

        self.node = rclpy.create_node("fake_twin_services")
        self.holding = holding
        self.holds: list = []
        self.hold_answer = True
        self.node.create_service(Holding, Holding.Request.SERVICE, self._on_holding)
        self.node.create_service(HoldMode, HoldMode.Request.SERVICE, self._on_hold)
        self.sides = self.node.create_publisher(TwinSides, TwinSides.TOPIC, LATCHED)
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self._thread = threading.Thread(target=self.executor.spin, daemon=True)
        self._thread.start()

    def _on_holding(self, request, response):
        return self.holding

    def _on_hold(self, request, response):
        self.holds.append((request.action, request.holder, request.node, request.mode))
        response.accepted = self.hold_answer
        response.result.detail = "fake"
        return response

    def close(self) -> None:
        self.executor.shutdown()
        self.node.destroy_node()


def _cell(graph) -> RosCell:
    _, reader = graph
    reader._holder = "run-under-test"
    reader._holds = False
    reader._release_owed = False
    reader._expected_mode = None
    reader._heard_mode = None
    return reader


def test_custody_of_every_side_is_asked_of_the_twin_on_this_domain(graph) -> None:
    """R-01: one call to the boundary; the counterpart's domain is never opened."""
    twin = _Twin(
        Holding.Response(
            sides=["plant", "counterpart"],
            heard=[True, True],
            holding=[False, True],
            detail=["", "picker holds box_7"],
        )
    )
    try:
        cell = _cell(graph)
        with pytest.raises(StepFailed, match="counterpart: picker holds box_7"):
            cell.refuse_if_holding(("plant", "counterpart"))
        twin.holding = Holding.Response(
            sides=["plant", "counterpart"],
            heard=[True, True],
            holding=[False, False],
            detail=["", ""],
        )
        cell.refuse_if_holding(("plant", "counterpart"))
    finally:
        twin.close()


def test_the_cell_holds_and_releases_the_mode_by_its_own_node(graph) -> None:
    """S-01: the hold names this run and this cell's node, and is let go once."""
    twin = _Twin(Holding.Response())
    try:
        cell = _cell(graph)
        cell._hold(TwinMode.MODE_SIM, "SIM")
        assert cell.release_hold()
        # R-17: nothing owed is None, and nothing is asked.
        assert cell.release_hold() is None, "nothing held: nothing asked"
        (acquire, release) = twin.holds
        assert acquire == (
            HoldMode.Request.ACQUIRE, "run-under-test", "/terminal_client", TwinMode.MODE_SIM
        )
        assert release[:2] == (HoldMode.Request.RELEASE, "run-under-test")
        twin.hold_answer = False
        with pytest.raises(StepFailed, match="would not hold"):
            cell._hold(TwinMode.MODE_REAL, "REAL")
    finally:
        twin.close()


def test_a_release_is_sent_whenever_an_acquire_was(graph) -> None:
    """R-14: owed before the ACQUIRE is sent, so a refused or lost one is released too."""
    twin = _Twin(Holding.Response())
    try:
        cell = _cell(graph)
        twin.hold_answer = False
        with pytest.raises(StepFailed, match="would not hold"):
            cell.hold_sim()
        twin.hold_answer = True
        assert cell.release_hold() is True
        assert [hold[0] for hold in twin.holds] == [
            HoldMode.Request.ACQUIRE, HoldMode.Request.RELEASE
        ]
    finally:
        twin.close()


def test_the_hold_is_re_asserted_before_every_step(graph) -> None:
    """S2-05: `check_mode` asks the twin, under its lock, whether this run still holds."""
    twin = _Twin(Holding.Response())
    try:
        cell = _cell(graph)
        cell._hold(TwinMode.MODE_REAL, "REAL")
        cell._expected_mode = cell._heard_mode = TwinMode.MODE_REAL
        cell.check_mode()
        assert twin.holds[-1] == (
            HoldMode.Request.ACQUIRE, "run-under-test", "/terminal_client", TwinMode.MODE_REAL
        )
        twin.hold_answer = False
        with pytest.raises(StepFailed, match="would not hold REAL"):
            cell.check_mode()
    finally:
        twin.close()


def test_terminal_runs_have_names_of_their_own_on_one_prefix() -> None:
    """S2-05: each terminal run's node is its own, and is known by its prefix."""
    from cite_bringup.program.cell import is_terminal_node, terminal_node_name

    first, second = terminal_node_name(), terminal_node_name()
    assert first != second
    assert is_terminal_node(first) and is_terminal_node(second)
    assert is_terminal_node(TERMINAL_NODE)
    assert not is_terminal_node("cell_console_program_0a1b2c3d")
    assert not is_terminal_node(f"{TERMINAL_NODE}x")


def test_the_operator_waits_for_a_stationary_physical_carriage(graph, monkeypatch) -> None:
    """S-02: a moving carriage holds the prompt back, bounded, and refuses at the bound."""
    from cite_bringup.program import targets

    twin = _Twin(Holding.Response())
    try:
        cell = _cell(graph)
        sides = {"running": ["plant", "counterpart"], "physical": ["counterpart"]}
        twin.sides.publish(TwinSides(**sides, commandable=["plant", "counterpart"],
                                     stationary=[], detail="picker_track_joint is not "
                                     "reported stationary"))
        monkeypatch.setattr(cell_module, "PHYSICAL_SIDE_READY_CEILING_S", 1.0)
        refusal = cell._await_physical_sides(targets.REAL)
        assert refusal is not None and "not reported stationary" in refusal
        assert "no one is asked into the cell" in refusal
        twin.sides.publish(TwinSides(**sides, commandable=["plant", "counterpart"],
                                     stationary=["counterpart"]))
        monkeypatch.setattr(cell_module, "PHYSICAL_SIDE_READY_CEILING_S", GRAPH_S)
        assert cell._await_physical_sides(targets.REAL) is None
    finally:
        twin.close()
