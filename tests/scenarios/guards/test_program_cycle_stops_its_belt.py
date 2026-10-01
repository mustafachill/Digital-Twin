"""Guard: `program_cycle` commands the belt it started back to zero.

The scenario starts the belt itself, because the real robot's program has no
belt block (ADR-0067). Until ADR-0069's review it never stopped it: a simulated
belt stops when its simulator does, so nothing noticed. A physical belt is a
drive whose setpoint persists, and the line's StopAll — the main tree's only
automatic all-belts stop — left with the line. So the scenario registers a stop
as a cleanup, BEFORE it starts the belt, and this guard holds both halves:

* the wiring — the cleanup is registered before the start is published, so no
  route out of the test, a failure included, skips it; and
* the stop itself — the helper publishes the zero it was handed and waits for
  the belt's subscriber to acknowledge it rather than sleeping.

ROS-free like every guard here: the module is loaded with the ROS stubs
`test_scenario_modules_load.py` defines, and the helper is driven unbound
against a fabricated publisher. It brings nothing up.
"""

from __future__ import annotations

import ast
from pathlib import Path

from test_scenario_modules_load import _load_like_launch_test, _ros_stubs

SCENARIO = Path(__file__).resolve().parents[1] / "program_cycle.py"
TEST_METHOD = "test_the_program_picks_slides_places_and_the_belt_carries_it"


class _Publisher:
    def __init__(self) -> None:
        self.published: list[object] = []
        self.acked_waits = 0

    def publish(self, message: object) -> None:
        self.published.append(message)

    def wait_for_all_acked(self, timeout: object) -> bool:
        self.acked_waits += 1
        return True


class _Conveyor:
    command_topic = "/cite/zone_x/belt/command"


class _Self:
    conveyor = _Conveyor()


def test_the_stop_publishes_the_zero_and_waits_for_it_to_be_acknowledged() -> None:
    with _ros_stubs():
        module = _load_like_launch_test(SCENARIO)
        belt = _Publisher()
        zero = object()
        module.TestProgramCycle._stop_the_belt(_Self(), belt, zero)
    assert belt.published == [zero], "the stop did not publish the zero it was handed"
    assert belt.acked_waits == 1, "the stop did not wait for its acknowledgement"


def _calls(method: ast.FunctionDef) -> list[ast.Call]:
    calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def test_the_stop_is_registered_before_the_belt_is_started() -> None:
    tree = ast.parse(SCENARIO.read_text())
    (method,) = (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == TEST_METHOD
    )
    cleanup_line = start_line = None
    for call in _calls(method):
        text = ast.unparse(call)
        if cleanup_line is None and text.startswith("self.addCleanup(self._stop_the_belt"):
            cleanup_line = call.lineno
        if start_line is None and text.startswith("belt.publish(") and "installed_speed" in text:
            start_line = call.lineno
    assert start_line is not None, "the scenario no longer starts the belt; re-read this guard"
    assert cleanup_line is not None, "the scenario starts the belt and never stops it"
    assert cleanup_line < start_line, (
        "the belt's stop is registered after the belt is started, so a failure "
        "between the two leaves it running"
    )
