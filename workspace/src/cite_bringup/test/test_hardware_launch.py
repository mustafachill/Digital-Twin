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

"""What `hardware.launch.py` refuses, and the order it would start a physical side in.

ADR-0070 item 6, and the launch requirements of the safety re-audit (L-1 to
L-7). **Nothing here starts a process, and nothing reaches a robot.** A fake
`ros2_control` hardware is not possible with the vendor plugin, so the launch
description is built and read: which refusals come first, that the deadman is
confirmed active before the controller manager exists, that nothing that could
move the arm starts before the hold gate, that nothing respawns and that every
process going away takes the side with it. The address used anywhere here is
from RFC 5737's TEST-NET-1, which routes nowhere.

Which launch a side gets (`pair.side_launch`) and which endpoints a physical
side's witness waits on are asserted here too, because they are the two other
halves of the same selection.
"""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from types import ModuleType

from cite_bringup import pair
from cite_bringup.plan import (
    COUNTERPART_SIDE,
    default_plan_path,
    DOMAIN_BASE_ENV,
    DOMAIN_ENV,
    HARDWARE_OPT_IN_ENV,
    load,
    PLANT_SIDE,
)
from cite_bringup.readiness import READY_TOKEN
from cite_bringup.readiness_witness import endpoints, physical_endpoints
from cite_bringup.side_launch import FailTheLaunch, skill_parameters
from control_msgs.action import FollowJointTrajectory, GripperCommand
from launch import LaunchContext
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
    RegisterEventHandler,
    Shutdown,
)
from launch.event_handlers import OnProcessExit
from launch.events.process import ProcessExited
from launch.utilities import perform_substitutions
from launch_ros.actions import LifecycleNode, Node
from launch_ros.utilities import evaluate_parameters
import pytest

LAUNCH_FILE = Path(__file__).resolve().parent.parent / "launch" / "hardware.launch.py"

#: RFC 5737 TEST-NET-1: reserved for documentation, routed nowhere.
TEST_ADDRESS = "192.0.2.1"

#: The variable the shipped plan names for the arm's address.
ADDRESS_VARIABLE = "CITE_XARM_IP"

_BASE = "42"


@pytest.fixture()
def module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cite_bringup_hardware", LAUNCH_FILE)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture(autouse=True)
def counterpart_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the test on the counterpart's own domain, with no opt-in and no real address."""
    plan = load(default_plan_path("cell_b"))
    offset = plan.side_named(COUNTERPART_SIDE).domain_offset
    monkeypatch.setenv(DOMAIN_BASE_ENV, _BASE)
    monkeypatch.setenv(DOMAIN_ENV, str(int(_BASE) + offset))
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    monkeypatch.setenv(ADDRESS_VARIABLE, TEST_ADDRESS)


@pytest.fixture()
def context() -> LaunchContext:
    ctx = LaunchContext()
    ctx.launch_configurations["zone"] = "cell_b"
    ctx.launch_configurations["side"] = COUNTERPART_SIDE
    return ctx


class _Exited:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def _plan():
    return load(default_plan_path("cell_b"))


def _is_stop(actions: list) -> bool:
    return [type(a) for a in actions] == [LogInfo, Shutdown, FailTheLaunch]


def _message(actions: list, context: LaunchContext) -> str:
    return "".join(part.perform(context) for part in actions[0].msg)


def _structure(module: ModuleType) -> list:
    """Build the physical side's description with a stand-in description string."""
    plan = _plan()
    stand_in = {m.asset: "<robot name='stand_in'/>" for m in plan.controller_managers}
    return module.physical_side(plan, COUNTERPART_SIDE, stand_in)


def _gated(actions: list, context: LaunchContext) -> list[tuple[object, list]]:
    """Every (target action, entities it releases on a clean exit), in registration order.

    The target is found by asking the handler which candidate's exit it matches,
    because `launch` keeps it inside a matcher rather than as an attribute.
    """
    handlers = [
        action.event_handler
        for action in actions
        if isinstance(action, RegisterEventHandler)
        and isinstance(action.event_handler, OnProcessExit)
    ]
    released = [(h, h.handle(_Exited(0), context) or []) for h in handlers]
    candidates = [a for a in actions if isinstance(a, ExecuteProcess)] + [
        e for _h, entities in released for e in entities if isinstance(e, ExecuteProcess)
    ]
    found = []
    for handler, entities in released:
        targets = [c for c in candidates if handler.matches(_exit_of(c))]
        assert len(targets) == 1, "every gate waits on exactly one process"
        found.append((targets[0], entities))
    return found


def _exit_of(action) -> ProcessExited:
    return ProcessExited(
        action=action, name="x", cmd=["x"], cwd=None, env=None, pid=1, returncode=0
    )


def _everything(actions: list, context: LaunchContext) -> list:
    """Every action the description can ever start, gated or not."""
    found = [a for a in actions if not isinstance(a, RegisterEventHandler)]
    for _target, entities in _gated(actions, context):
        found += [e for e in entities if not isinstance(e, RegisterEventHandler)]
    return found


def _nodes(actions: list, context: LaunchContext) -> list[Node]:
    return [a for a in _everything(actions, context) if isinstance(a, Node)]


def _parameters(node, context: LaunchContext) -> list:
    """Return a node's parameters as `launch_ros` hands them over: paths and dicts."""
    evaluated = evaluate_parameters(context, node._Node__parameters or [])  # noqa: SLF001
    found: list = []
    for item in evaluated:
        if isinstance(item, Path):
            found.append(str(item))
        elif hasattr(item, "evaluate"):
            found.append(str(item.evaluate(context)))
        else:
            found.append(dict(item))
    return found


def _executable(node) -> str | None:
    return getattr(node, "node_executable", None)


def _releasing(actions: list, context: LaunchContext, executable: str):
    """Return the target whose clean exit releases the node running ``executable``."""
    for target, entities in _gated(actions, context):
        if any(_executable(e) == executable for e in entities):
            return target
    return None


# --- Refusals, before anything is described ----------------------------------


def test_without_the_opt_in_nothing_is_started(module, context) -> None:
    actions = module._bring_up(context)
    assert _is_stop(actions)
    message = _message(actions, context)
    assert HARDWARE_OPT_IN_ENV in message
    assert TEST_ADDRESS not in message


def test_a_simulated_side_is_refused_whatever_the_opt_in(
    module, context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(HARDWARE_OPT_IN_ENV, "1")
    monkeypatch.setenv(DOMAIN_ENV, _BASE)
    context.launch_configurations["side"] = PLANT_SIDE
    actions = module._bring_up(context)
    assert _is_stop(actions)
    assert "simulation.launch.py" in _message(actions, context)


def test_an_unset_address_is_refused_naming_the_variable(
    module, context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(HARDWARE_OPT_IN_ENV, "1")
    monkeypatch.delenv(ADDRESS_VARIABLE)
    actions = module._bring_up(context)
    assert _is_stop(actions)
    assert ADDRESS_VARIABLE in _message(actions, context)


def test_a_malformed_address_is_refused_without_printing_it(
    module, context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(HARDWARE_OPT_IN_ENV, "1")
    monkeypatch.setenv(ADDRESS_VARIABLE, "robot.example")
    actions = module._bring_up(context)
    assert _is_stop(actions)
    message = _message(actions, context)
    assert ADDRESS_VARIABLE in message and "robot.example" not in message


def test_the_wrong_domain_is_refused(module, context, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HARDWARE_OPT_IN_ENV, "1")
    monkeypatch.setenv(DOMAIN_ENV, _BASE)  # the plant's
    assert _is_stop(module._bring_up(context))


def test_the_address_reaches_the_description_and_no_command_line(
    module, context, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expanded in the launch process: the address is a parameter value, never an argv."""
    monkeypatch.setenv(HARDWARE_OPT_IN_ENV, "1")
    actions = module._bring_up(context)
    assert not _is_stop(actions), _message(actions, context)
    publishers = [n for n in _nodes(actions, context) if _executable(n) == "robot_state_publisher"]
    assert len(publishers) == 1
    (parameters,) = _parameters(publishers[0], context)
    assert TEST_ADDRESS in parameters["robot_description"]
    assert "uf_robot_hardware/UFRobotSystemHardware" in parameters["robot_description"]
    for node in _nodes(actions, context):
        for argument in node.cmd if hasattr(node, "cmd") else []:
            assert TEST_ADDRESS not in str(argument)


def test_the_launch_declares_no_clock_argument(module) -> None:
    """L-7: nothing a caller passes can put a physical side on simulated time."""
    declared = {
        entity.name
        for entity in module.generate_launch_description().entities
        if isinstance(entity, DeclareLaunchArgument)
    }
    assert declared == {"zone", "side"}


# --- The order a physical side comes up in -----------------------------------


def test_the_deadman_is_the_first_thing_started_and_driven_alone(module, context) -> None:
    actions = _structure(module)
    started = [a for a in actions if isinstance(a, Node)]
    assert [_executable(n) for n in started] == ["deadman.py", "lifecycle_driver.py"]
    physical = _plan().controller_managers[0].physical_on(COUNTERPART_SIDE)
    driver = started[1]
    assert driver._Node__arguments == ["--node", physical.deadman]  # noqa: SLF001


def test_the_controller_manager_exists_only_after_the_deadman_is_confirmed(
    module, context
) -> None:
    actions = _structure(module)
    first_driver = [a for a in actions if _executable(a) == "lifecycle_driver.py"][0]
    assert _releasing(actions, context, "ros2_control_node") is first_driver
    assert not any(_executable(a) == "ros2_control_node" for a in actions)


def test_nothing_that_moves_starts_before_the_hold_gate(module, context) -> None:
    actions = _structure(module)
    held = [n for n in _nodes(actions, context) if _executable(n) == "hold_gate.py"]
    assert len(held) == 1
    assert _releasing(actions, context, "spawner") is held[0]
    assert _releasing(actions, context, "move_group") is held[0]
    second_driver = _releasing(actions, context, "hold_gate.py")
    assert _executable(second_driver) == "lifecycle_driver.py"


def test_the_token_comes_last_after_the_witness(module, context) -> None:
    actions = _structure(module)
    tokens = [
        (target, e)
        for target, entities in _gated(actions, context)
        for e in entities
        if isinstance(e, LogInfo) and READY_TOKEN in "".join(p.perform(context) for p in e.msg)
    ]
    assert len(tokens) == 1
    assert _executable(tokens[0][0]) == "readiness_witness.py"


def test_the_controller_manager_runs_where_the_plan_names_it(module, context) -> None:
    """The plant's namespace, no `name=` remap, the side's own configuration."""
    manager = _plan().controller_managers[0]
    (node,) = [
        n for n in _nodes(_structure(module), context) if _executable(n) == "ros2_control_node"
    ]
    assert node._Node__node_name is None  # noqa: SLF001 - no name remapping
    assert node._Node__node_namespace == manager.node.rsplit("/", 1)[0]  # noqa: SLF001
    files = [p for p in _parameters(node, context) if isinstance(p, str)]
    assert files == [str(module.resolve_uri(manager.parameters_on(COUNTERPART_SIDE)))]
    assert {"use_sim_time": False} in _parameters(node, context)
    remappings = [
        tuple(perform_substitutions(context, list(part)) for part in pair_)
        for pair_ in node._Node__remappings  # noqa: SLF001 - read only
    ]
    assert ("~/robot_description", manager.description_topic) in remappings


#: The pinned vendor plugin, read for the absolute controller manager names its
#: own clients use, so that the L0 declaration is checked against the source.
VENDOR_PLUGIN = (
    Path(__file__).resolve().parents[2]
    / "external/xarm_ros2/xarm_controller/src/hardware/uf_robot_system_hardware.cpp"
)


def test_the_vendor_plugins_controller_manager_calls_reach_this_manager(
    module, context
) -> None:
    """SA2c-S-01: the plugin calls `/controller_manager/...` by absolute name.

    Our controller manager runs in the asset's namespace, so without a remap
    those calls wait on a service nothing serves, from inside `write()`. Every
    absolute name the pinned source creates a client for is remapped, and each
    lands on this manager's own service of the same leaf name.
    """
    import re

    manager = _plan().controller_managers[0]
    called = set(
        re.findall(
            r'create_client<controller_manager_msgs::srv::\w+>\("(/controller_manager/\w+)"\)',
            VENDOR_PLUGIN.read_text(),
        )
    )
    assert called, f"no controller manager client found in {VENDOR_PLUGIN}"
    (node,) = [
        n for n in _nodes(_structure(module), context) if _executable(n) == "ros2_control_node"
    ]
    remappings = dict(
        tuple(perform_substitutions(context, list(part)) for part in pair_)
        for pair_ in node._Node__remappings  # noqa: SLF001 - read only
    )
    for absolute in called:
        assert remappings.get(absolute) == f"{manager.node}/{absolute.rsplit('/', 1)[1]}", (
            f"{absolute} is not remapped onto {manager.node}"
        )


def test_every_hardware_node_is_named_by_the_plan_with_the_generated_file(
    module, context
) -> None:
    physical = _plan().controller_managers[0].physical_on(COUNTERPART_SIDE)
    hardware = {
        f"{n._Node__node_namespace}/{n._Node__node_name}": n  # noqa: SLF001
        for n in _nodes(_structure(module), context)
        if n.node_package == "cite_hardware"
    }
    assert set(hardware) == {physical.deadman, physical.track_adapter, physical.gripper_relay}
    for node in hardware.values():
        assert isinstance(node, LifecycleNode)
        assert _parameters(node, context) == [str(physical.parameters)]


# --- A physical side goes down whole, and nothing comes back by itself --------


def test_nothing_on_a_physical_side_respawns(module, context) -> None:
    """L-2."""
    for node in _nodes(_structure(module), context):
        assert not node._ExecuteLocal__respawn, _executable(node)  # noqa: SLF001


@pytest.mark.parametrize(
    "executable",
    [
        "deadman.py",
        "ros2_control_node",
        "track_adapter.py",
        "gripper_relay.py",
        "robot_state_publisher",
        "move_group",
        "skill_server",
        "frame_server.py",
        "model_info.py",
    ],
)
@pytest.mark.parametrize("returncode", [0, 1, -9])
def test_any_exit_of_a_long_running_node_stops_the_side(
    module, context, executable: str, returncode: int
) -> None:
    """L-1, L-3: a clean exit is no excuse either."""
    (node,) = [n for n in _nodes(_structure(module), context) if _executable(n) == executable]
    on_exit = node._ExecuteLocal__on_exit  # noqa: SLF001 - read only
    assert _is_stop(on_exit(_Exited(returncode), context))


def test_every_node_runs_on_the_wall_clock(module, context) -> None:
    """L-7: no node of a physical side is handed simulated time."""
    for node in _nodes(_structure(module), context):
        for parameters in _parameters(node, context):
            if isinstance(parameters, dict):
                assert parameters.get("use_sim_time", False) is False, _executable(node)


def test_the_physical_sides_skill_server_executes_its_outcomes_unjudged(module, context) -> None:
    """Owner decisions 2026-10-06 (ADR-0070): physical outcomes are executed, not judged.

    A physical close and a physical arm arrival both, through the one
    `side_judges_outcome`.

    Asked of the plan through the production builder, on both sides of the one
    shipped plan: the physical counterpart's skill server is told not to judge,
    and the plant's keeps judging exactly as before.
    """
    servers = [n for n in _nodes(_structure(module), context) if _executable(n) == "skill_server"]
    assert servers, "the physical side starts no skill server"
    for node in servers:
        delivered = {
            key: value
            for parameters in _parameters(node, context)
            if isinstance(parameters, dict)
            for key, value in parameters.items()
        }
        assert delivered.get("side_judges_outcome") is False
    plan = _plan()
    for manager in plan.controller_managers:
        if manager.moveit is not None:
            assert skill_parameters(plan, manager, side=PLANT_SIDE)["side_judges_outcome"] is True


# --- Which launch a side gets, and what its witness waits on -----------------


def test_the_physical_counterpart_gets_the_hardware_launch() -> None:
    plan = _plan()
    argv = pair.side_launch(plan, COUNTERPART_SIDE, headless=False)
    assert argv[3] == pair.HARDWARE_LAUNCH
    assert "side:=counterpart" in argv and not any(a.startswith("headless") for a in argv)
    assert pair.side_launch(plan, PLANT_SIDE, headless=True)[3] == pair.SIMULATION_LAUNCH


def test_the_selection_reads_the_declared_fact_and_not_the_backend_name() -> None:
    """A counterpart declaring no physical hardware is simulated, whatever it is called."""
    plan = _plan()
    manager = plan.controller_managers[0]
    simulated = dataclasses.replace(manager, counterpart_commands_physical_hardware=False)
    renamed = dataclasses.replace(plan, controller_managers=(simulated,))
    assert pair.side_launch(renamed, COUNTERPART_SIDE, headless=True)[3] == pair.SIMULATION_LAUNCH


def test_a_physical_witness_waits_for_what_its_deadman_cancels() -> None:
    plan = _plan()
    manager = plan.controller_managers[0]
    assert physical_endpoints(plan, COUNTERPART_SIDE) == [
        (manager.trajectory_action, FollowJointTrajectory),
        (manager.gripper_action, GripperCommand),
    ]
    assert physical_endpoints(plan, PLANT_SIDE) == []
    assert len(endpoints(plan, COUNTERPART_SIDE)) == len(endpoints(plan)) + 2
