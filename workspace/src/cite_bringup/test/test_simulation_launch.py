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

"""What `simulation.launch.py` refuses to start, and what it stops on.

The plan reader is tested next door; this file tests the launch description the
reader feeds. Both halves are needed and neither substitutes for the other: a
perfectly correct `require_hardware_opt_in` that nothing calls is exactly the
defect this file exists to catch, and it is the defect that was there — a gate
existed in `scripts/_lib.sh` and guarded one shell command.

Nothing here starts a process. `_bring_up` builds a launch description and these
tests read it, so they run in milliseconds and do not need a simulator.
"""

from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import re
from types import ModuleType

from cite_bringup.plan import (
    DOMAIN_BASE_ENV,
    DOMAIN_ENV,
    GZ_PARTITION_ENV,
    HARDWARE_OPT_IN_ENV,
    load,
    PLANT_SIDE,
    resolve_uri,
)
from cite_bringup.readiness import announced_side, READY_TOKEN
from launch import LaunchContext
from launch.actions import ExecuteProcess, LogInfo, RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch.utilities import normalize_to_list_of_substitutions, perform_substitutions
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import StateTransition
from lifecycle_msgs.msg import TransitionEvent
import pytest
import yaml

LAUNCH_FILE = Path(__file__).resolve().parent.parent / "launch" / "simulation.launch.py"
GENERATED_PLAN = "package://cite_generated/bringup/cell_a_plan.yaml"

#: The managed nodes bring-up must not proceed without. Named rather than
#: counted: a test that asserts "three handlers exist" passes when the wrong
#: three exist.
MANAGED = ("frame_server", "model_info", "topology_server")


@pytest.fixture()
def module() -> ModuleType:
    """Import the launch file as a module.

    It lives under `launch/` rather than in the Python package, because that is
    where `ros2 launch` looks for it. Loading it by path is what lets its
    behaviour be tested at all.
    """
    spec = importlib.util.spec_from_file_location("cite_bringup_simulation", LAUNCH_FILE)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


#: The base and the domain a side is checked against, as `scripts/_lib.sh` and
#: `docker-compose.yml` supply them. Set for every test rather than inherited, so
#: that the suite answers the same way on a machine whose ambient domain differs
#: and so that the tests which assert the refusal have something to break.
_TEST_DOMAIN = "42"


@pytest.fixture(autouse=True)
def side_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put every test on the plant's own domain, both values independently set."""
    monkeypatch.setenv(DOMAIN_BASE_ENV, _TEST_DOMAIN)
    monkeypatch.setenv(DOMAIN_ENV, _TEST_DOMAIN)


@pytest.fixture()
def context() -> LaunchContext:
    ctx = LaunchContext()
    ctx.launch_configurations["zone"] = "cell_a"
    ctx.launch_configurations["headless"] = "true"
    ctx.launch_configurations["line"] = "false"
    ctx.launch_configurations["side"] = PLANT_SIDE
    return ctx


@pytest.fixture()
def line_context(context: LaunchContext) -> LaunchContext:
    context.launch_configurations["line"] = "true"
    return context


class _Exited:
    """Stands in for launch's ProcessExited, which needs a real process to build."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def _document() -> dict:
    return yaml.safe_load(Path(resolve_uri(GENERATED_PLAN)).read_text())


def _plan_with_backend(tmp_path: Path, backend: str) -> Path:
    document = copy.deepcopy(_document())
    document["plan"]["controller_managers"][1]["backend"] = backend
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


def _use(module: ModuleType, monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(module, "default_plan_path", lambda zone="cell_a": path)


def _kinds(actions: list) -> list[str]:
    return [type(action).__name__ for action in actions]


def _processes(actions: list) -> list[ExecuteProcess]:
    return [action for action in actions if isinstance(action, ExecuteProcess)]


def _refusal(actions: list, context: LaunchContext) -> str:
    """Return the text a person sees when bring-up refuses.

    Read from the `LogInfo` rather than from the `Shutdown`: launch's `Shutdown`
    keeps its reason private, and the message is what actually reaches the
    console anyway — which is the thing that has to name the asset.
    """
    assert any(isinstance(action, Shutdown) for action in actions), _kinds(actions)
    return "\n".join(
        perform_substitutions(context, list(action.msg))
        for action in actions
        if isinstance(action, LogInfo)
    )


# --- C3: a hardware backend does not start without the opt-in -----------------


def test_a_hardware_plan_refuses_to_bring_the_cell_up(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    """The gate, at the boundary that matters.

    Remove `require_hardware_opt_in` from `_bring_up` and this fails: the plan
    still loads, so the description comes back full of processes instead of a
    refusal.
    """
    _use(module, monkeypatch, _plan_with_backend(tmp_path, "real"))
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)

    actions = module._bring_up(context)

    assert "Shutdown" in _kinds(actions), (
        "a plan declaring a hardware backend produced a launch description that "
        "starts processes"
    )
    assert not _processes(actions), "nothing may be started on the way to refusing"
    reason = _refusal(actions, context)
    assert "arm_2" in reason and HARDWARE_OPT_IN_ENV in reason


def test_a_hardware_plan_starts_with_the_opt_in(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    """A refusal, not a ban — and not a divergence in what gets commanded (P2)."""
    _use(module, monkeypatch, _plan_with_backend(tmp_path, "real"))
    monkeypatch.setenv(HARDWARE_OPT_IN_ENV, "1")

    actions = module._bring_up(context)

    assert "Shutdown" not in _kinds(actions)
    assert _processes(actions)


def test_the_simulated_plan_needs_no_opt_in(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)
    assert "Shutdown" not in _kinds(actions)


# --- R-15: a malformed plan is refused, not raised through --------------------


def test_a_malformed_plan_refuses_rather_than_raising(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    document = copy.deepcopy(_document())
    del document["plan"]["controller_managers"][0]["node"]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    _use(module, monkeypatch, path)

    actions = module._bring_up(context)

    assert not _processes(actions)
    assert "node" in _refusal(actions, context)


# --- H6: every process-exit gate stops the launch on a non-zero exit ----------


def test_no_process_exit_handler_passes_a_failure_through(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """Including the last one.

    The chain used to gate every intermediate controller stage and leave the
    final spawner ungated, so a last stage that timed out started the skill
    servers anyway and nothing shut down. Asserting the property over every
    handler, rather than over the one that was wrong, is what stops the next
    ungated link being added.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)

    handlers = [
        action.event_handler
        for action in actions
        if isinstance(action, RegisterEventHandler)
        and isinstance(action.event_handler, OnProcessExit)
    ]
    assert handlers, "bring-up registered no process-exit gates at all"

    for handler in handlers:
        produced = handler.handle(_Exited(returncode=1), context) or []
        entities = produced if isinstance(produced, list) else [produced]
        assert any(isinstance(entity, Shutdown) for entity in entities), (
            f"{handler.describe()[0]} continues after a non-zero exit, which "
            "leaves a half-built system running"
        )


def test_a_successful_exit_continues_the_chain(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """The gate must not be a wall: exit 0 has to carry the chain forward."""
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)

    handlers = [
        action.event_handler
        for action in actions
        if isinstance(action, RegisterEventHandler)
        and isinstance(action.event_handler, OnProcessExit)
    ]
    for handler in handlers:
        produced = handler.handle(_Exited(returncode=0), context) or []
        entities = produced if isinstance(produced, list) else [produced]
        assert not any(isinstance(entity, Shutdown) for entity in entities)


# --- H6: a managed node that cannot configure stops bring-up ------------------


def _transition(node, start_state: str, goal_state: str) -> StateTransition:
    msg = TransitionEvent()
    msg.transition.label = "transition_failure"
    msg.start_state.label = start_state
    msg.goal_state.label = goal_state
    return StateTransition(action=node, msg=msg)


@pytest.mark.parametrize(
    ("start_state", "goal_state"),
    [
        ("configuring", "unconfigured"),
        ("configuring", "errorprocessing"),
        ("activating", "inactive"),
        ("activating", "errorprocessing"),
    ],
)
def test_a_managed_node_that_fails_a_transition_stops_bring_up(
    module: ModuleType, context: LaunchContext, monkeypatch, start_state, goal_state
) -> None:
    """`frame_server.on_configure` returning FAILURE used to cost nothing.

    The activation never fired — which was true and was the whole of the claim —
    but nothing else was gated on the facility nodes either, so the cell came up
    fully with a disconnected TF tree and every skill goal failed with a lookup
    error naming frames rather than the node that never published them.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)

    handlers = [
        action.event_handler
        for action in actions
        if isinstance(action, RegisterEventHandler)
        and isinstance(action.event_handler, OnStateTransition)
    ]
    nodes = [action for action in actions if type(action).__name__ == "LifecycleNode"]
    assert len(nodes) == len(MANAGED), _kinds(actions)

    for node in nodes:
        event = _transition(node, start_state, goal_state)
        stopped = [
            entity
            for handler in handlers
            if handler.matches(event)
            for entity in (handler.handle(event, context) or [])
            if isinstance(entity, Shutdown)
        ]
        assert stopped, (
            f"a managed node reaching {start_state} -> {goal_state} does not stop "
            "bring-up; the cell would come up without it"
        )


def test_activation_is_triggered_only_by_a_successful_configure(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """A failed activation lands in `inactive` too.

    A handler matching only the goal state answers that by activating again, and
    a node whose `on_activate` fails deterministically then loops.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)

    nodes = [action for action in actions if type(action).__name__ == "LifecycleNode"]
    handlers = [
        action.event_handler
        for action in actions
        if isinstance(action, RegisterEventHandler)
        and isinstance(action.event_handler, OnStateTransition)
    ]
    for node in nodes:
        failed_activation = _transition(node, "activating", "inactive")
        for handler in handlers:
            if not handler.matches(failed_activation):
                continue
            entities = handler.handle(failed_activation, context) or []
            assert not any(
                type(entity).__name__ == "EmitEvent" for entity in entities
            ), "a failed activation triggered another activation"


# --- The seed reaches gz sim, and a bad one is refused ------------------------


def _command(context: LaunchContext, process: ExecuteProcess) -> list[str]:
    return [perform_substitutions(context, list(part)) for part in process.cmd]


def test_the_seed_reaches_the_simulator(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """`gz sim --seed` is a command-line flag; SDFormat has no seed element.

    This asserts that the value reaches the command line, and nothing beyond it.
    It is not a reproducibility test and must not be cited as one: the physics
    solver is seeded by nothing. ADR-0027 § "What `CITE_PHYSICS_SEED` does and
    does not buy" is the one place that states the rest; do not restate it here.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    monkeypatch.setenv(module.PHYSICS_SEED_ENV, "20260824")
    actions = module._bring_up(context)

    simulator = next(
        p for p in _processes(actions) if _command(context, p)[:2] == ["gz", "sim"]
    )
    command = _command(context, simulator)
    assert "--seed" in command
    assert command[command.index("--seed") + 1] == "20260824"
    assert command[-1].endswith(".sdf"), "the world must stay the last argument"


def test_no_seed_means_no_flag(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    monkeypatch.delenv(module.PHYSICS_SEED_ENV, raising=False)
    actions = module._bring_up(context)
    simulator = next(
        p for p in _processes(actions) if _command(context, p)[:2] == ["gz", "sim"]
    )
    assert "--seed" not in _command(context, simulator)


def test_a_seed_gz_will_not_accept_is_refused(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """Refused rather than dropped.

    A run that believes it is seeded and is not is worse than a run that will
    not start.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    monkeypatch.setenv(module.PHYSICS_SEED_ENV, "not-a-number")
    actions = module._bring_up(context)
    assert not _processes(actions)
    assert module.PHYSICS_SEED_ENV in _refusal(actions, context)


# --- M-08: the planning scene is loaded, and bring-up waits for it ------------


def test_the_planning_scene_is_loaded_before_the_skills(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """Every plan in this cell used to be computed against an empty world.

    Not one `CollisionObject` or `PlanningScene` existed in the repository, and
    since every pick and place point lies exactly on a surface, a plan through
    that surface was the normal case rather than an exotic one.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)

    loaders: list = []
    skills: list = []
    for action in actions:
        if not isinstance(action, RegisterEventHandler):
            continue
        handler = action.event_handler
        if not isinstance(handler, OnProcessExit):
            continue
        for entity in handler.handle(_Exited(returncode=0), context) or []:
            name = getattr(entity, "node_executable", None)
            if name == "planning_scene_loader.py":
                loaders.append(entity)
            elif name == "skill_server":
                skills.append(entity)

    assert len(loaders) == 3, "one planning-scene loader per arm"
    assert len(skills) == 3, "one skill server per arm"

    # Ordering: the skill servers must be reachable only through a chain that has
    # already passed a loader. Structurally, the loaders are produced by handlers
    # registered before the one that produces the skills.
    order = [
        "loader" if any(e is loader for loader in loaders) else "skill"
        for action in actions
        if isinstance(action, RegisterEventHandler)
        and isinstance(action.event_handler, OnProcessExit)
        for e in (action.event_handler.handle(_Exited(returncode=0), context) or [])
        if getattr(e, "node_executable", None) in ("planning_scene_loader.py", "skill_server")
    ]
    assert order.count("loader") == 3
    assert order.index("skill") > max(
        index for index, kind in enumerate(order) if kind == "loader"
    ), "a skill server can start before the planning scene is loaded"


# --- The Gazebo/ROS bridge: ten names, none of them written here --------------
#
# `launch_ros` normalises a node's parameters and keeps its arguments private, so
# these read the pure functions the launch file builds them from rather than
# reaching into launch's internals — and then assert the node that carries them
# is actually in the description.


def _plan():
    return load(Path(resolve_uri(GENERATED_PLAN)))


def _nodes(actions: list, executable: str, context: LaunchContext) -> list:
    """Every Node with this executable, including ones behind a process gate."""
    found = [a for a in actions if getattr(a, "node_executable", None) == executable]
    for action in actions:
        if not isinstance(action, RegisterEventHandler):
            continue
        handler = action.event_handler
        if not isinstance(handler, OnProcessExit):
            continue
        for entity in handler.handle(_Exited(returncode=0), context) or []:
            if getattr(entity, "node_executable", None) == executable:
                found.append(entity)
    return found


def _namespace(node, context: LaunchContext) -> str:
    """Return the namespace a node will actually be launched into.

    `launch_ros` resolves a node's namespace only when the action executes, so it
    has to be asked to. Reading the constructor argument instead would test what
    this file passed rather than where the node lands, and those differ the
    moment a substitution is involved.
    """
    node._perform_substitutions(context)
    return node.expanded_node_namespace


def test_every_aid_topic_in_the_plan_is_bridged(module: ModuleType) -> None:
    """The blocker this work exists for.

    The belt and beam plugins were built, instantiated by the generated world and
    publishing on the Gazebo transport under exactly these names — and
    `cite_bringup` bridged `/clock` and nothing else. Ten declared interfaces had
    no ROS endpoint at all — a command and a state topic for each of the three
    belts, and a level for each of the four beams — so the bring-up plan
    advertised a system the running one did not provide.

    The count below is arithmetic on the plan rather than the literal ten, for
    the reason this docstring had to be corrected: a number written out is a
    number that stops being true when the cell gains a sensor.
    """
    plan = _plan()
    arguments, _ = module._bridge_topics(plan)

    assert module.CLOCK_BRIDGE in arguments
    for conveyor in plan.conveyors:
        assert (
            f"{conveyor.command_topic}@std_msgs/msg/Float64]gz.msgs.Double" in arguments
        ), conveyor.asset
        assert (
            f"{conveyor.state_topic}@std_msgs/msg/Float64[gz.msgs.Double" in arguments
        ), conveyor.asset
    for sensor in plan.sensors:
        assert (
            f"{sensor.detection_topic}@std_msgs/msg/Bool[gz.msgs.Boolean" in arguments
        ), sensor.asset

    expected = 1 + 2 * len(plan.conveyors) + len(plan.sensors)
    assert len(arguments) == expected, (
        f"the bridge carries {len(arguments)} topics against {expected} in the plan; "
        "a name was written here rather than taken from the model"
    )


def test_the_bridge_directions_are_not_interchangeable(module: ModuleType) -> None:
    """A command bridged the wrong way fails at both ends with no error at either.

    `]` is ROS to Gazebo and `[` is Gazebo to ROS. Reversed, a belt command
    becomes a ROS publisher nothing reads and a Gazebo subscriber nothing writes.
    """
    plan = _plan()
    arguments, _ = module._bridge_topics(plan)

    commands = [a for a in arguments if "/command@" in a]
    assert len(commands) == len(plan.conveyors)
    assert all("]" in a and "[" not in a for a in commands)

    inbound = [a for a in arguments if "/state@" in a or "/detection@" in a]
    assert len(inbound) == len(plan.conveyors) + len(plan.sensors)
    assert all("[" in a and "]" not in a for a in inbound)


def test_the_bridged_level_never_lands_on_the_event_topic(module: ModuleType) -> None:
    """The collision the whole naming split exists to prevent.

    `cell_a_flow.yaml` gives `/cite/<zone>/<asset>/detection` to L4 as a typed
    `DetectionEvent` trigger, and the `Detect` server publishes its events there.
    A bridge that put a `std_msgs/Bool` on the same name would give one topic two
    publishers of two types, and both would look healthy in `ros2 topic info`.
    """
    plan = _plan()
    arguments, remappings = module._bridge_topics(plan)
    remapped = dict(remappings)

    assert len(remapped) == len(plan.sensors)
    for sensor in plan.sensors:
        assert remapped.get(sensor.detection_topic) == sensor.level_topic, (
            f"{sensor.asset}: the raw level would be published on "
            f"{sensor.detection_topic}, which is the typed event topic"
        )
    # The bridge argument still names the GAZEBO topic, because that is what the
    # plugin advertises. Only the ROS end moves.
    assert not any(sensor.level_topic in a for a in arguments for sensor in plan.sensors)


def test_one_bridge_process_carries_them_all(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """Two would mean two publishers on /clock, and a cell with two clocks."""
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    bridges = _nodes(module._bring_up(context), "parameter_bridge", context)
    assert len(bridges) == 1


# --- L3 detection is started, and it is one server for the zone ---------------


def test_the_detection_server_is_started_with_every_beam(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """Built, installed, tested — and started by no launch graph until now."""
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    plan = _plan()

    servers = _nodes(module._bring_up(context), "detection_server", context)
    assert len(servers) == 1, "one detection server per zone, not one per arm"
    assert plan.detection is not None
    assert _namespace(servers[0], context) == plan.detection.namespace

    parameters = module._detection_parameters(plan)
    assert parameters["zone"] == plan.zone
    assert parameters["sensors"] == [s.asset for s in plan.sensors]
    assert parameters["use_sim_time"] is True
    for sensor in plan.sensors:
        assert parameters[f"sensor.{sensor.asset}.state_topic"] == sensor.level_topic
        assert parameters[f"sensor.{sensor.asset}.event_topic"] == sensor.detection_topic
        assert parameters[f"sensor.{sensor.asset}.frame_id"] == sensor.frame_id


def test_the_detection_server_reads_the_level_and_publishes_the_event(
    module: ModuleType,
) -> None:
    """Reversing the two gives a node that subscribes to its own output.

    It would start, log that it is watching every beam, and never see a sample.
    """
    plan = _plan()
    parameters = module._detection_parameters(plan)
    for sensor in plan.sensors:
        assert (
            parameters[f"sensor.{sensor.asset}.state_topic"]
            != parameters[f"sensor.{sensor.asset}.event_topic"]
        )
        # And the level side is the one the bridge writes to.
        _, remappings = module._bridge_topics(plan)
        assert (sensor.detection_topic, sensor.level_topic) in remappings


# --- L4 is startable, and off by default -------------------------------------


def test_the_line_coordinator_is_off_unless_asked_for(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """A running coordinator holds all three arms.

    A skill server admits one goal at a time per arm, so anything else driving an
    arm directly — a scenario, an operator, a diagnostic — would have its goals
    refused by a server that is busy working.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    assert not _nodes(module._bring_up(context), "line_orchestrator", context)


def test_the_line_coordinator_gets_its_action_names_from_the_plan(
    module: ModuleType, line_context: LaunchContext, monkeypatch
) -> None:
    """Parallel arrays, lined up by asset, every value generated by `ids.py`.

    The shape is `line_orchestrator`'s and is deliberate: a mismatched length is
    refused at start-up with both lengths named. What has changed is that the
    names are no longer assembled by whoever launches the node — that put
    `/cite/<zone>/<asset>/pick` in a second place, outside `ids.py` and outside
    every test that covers it.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    coordinators = _nodes(module._bring_up(line_context), "line_orchestrator", line_context)
    assert len(coordinators) == 1, "one coordinator per zone"

    plan = _plan()
    parameters = module._line_parameters(plan)
    assert parameters is not None

    served = [m for m in plan.controller_managers if m.skills is not None]
    assert served
    assert parameters["skill_assets"] == [m.asset for m in served]
    assert parameters["zone"] == plan.zone
    assert parameters["use_sim_time"] is True
    for key, attribute in (
        ("move_to_actions", "move_to"),
        ("pick_actions", "pick"),
        ("place_actions", "place"),
        ("transfer_actions", "transfer"),
    ):
        assert parameters[key] == [getattr(m.skills, attribute) for m in served], key
        assert len(parameters[key]) == len(parameters["skill_assets"])

    # One detection server for the zone, so every station is given the same
    # action: one name read once, not one name in three places.
    assert plan.detection is not None
    assert parameters["detect_actions"] == [plan.detection.detect_action] * len(served)

    assert Path(parameters["station_tree"]).exists(), parameters["station_tree"]


def test_the_line_coordinator_is_given_every_belt_drive_from_the_plan(
    module: ModuleType,
) -> None:
    """L4 owns the belt setpoint (ADR-0032), so it has to be given every drive.

    The same parallel-array shape as the skills, and for the same reason. What
    matters here is that the three arrays line up and that the speed is the plan's
    own `installed_speed_mps` rather than a number written into this launch file —
    the belt runs at the speed `model/assets/instances/conveyors.yaml` declares,
    in one place (P1).

    EVERY belt, not only the indexed ones. Which belts index is derived from the
    flow by the coordinator; deciding it here would put that rule in a second
    place, and a belt feeding a sink still has to be started by somebody.
    """
    plan = _plan()
    parameters = module._line_parameters(plan)
    assert parameters is not None

    assert plan.conveyors, "the generated plan declares no conveyor to command"
    assert parameters["conveyor_assets"] == [c.asset for c in plan.conveyors]
    assert parameters["conveyor_command_topics"] == [c.command_topic for c in plan.conveyors]
    assert parameters["conveyor_speeds_mps"] == [c.installed_speed_mps for c in plan.conveyors]

    lengths = {
        len(parameters["conveyor_assets"]),
        len(parameters["conveyor_command_topics"]),
        len(parameters["conveyor_speeds_mps"]),
    }
    assert len(lengths) == 1, f"the conveyor arrays do not line up: {lengths}"

    # The command topic is the one the bridge carries ROS->Gazebo. A setpoint sent
    # anywhere else is published to a topic nobody consumes, which is a silent
    # no-op and a belt that never moves.
    bridged, _ = module._bridge_topics(plan)
    for topic in parameters["conveyor_command_topics"]:
        assert any(topic in argument for argument in bridged), topic
    for speed in parameters["conveyor_speeds_mps"]:
        assert speed > 0.0, "a belt that cannot run cannot be indexed"


def test_the_line_state_topic_comes_off_the_message(module: ModuleType) -> None:
    """`LineState` now carries its own topic name, the way `LineTopology` does.

    Without the constant the name has to be supplied to the publisher and written
    again in every subscriber, which is a value in two places and is not
    discoverable with `ros2 interface show`.
    """
    from cite_interfaces.msg import LineState

    parameters = module._line_parameters(_plan())
    assert parameters is not None
    assert parameters["line_state_topic"] == LineState.TOPIC
    assert LineState.TOPIC == "/cite/line/state"


def test_the_line_coordinator_starts_behind_the_same_gate_as_the_skills(
    module: ModuleType, line_context: LaunchContext, monkeypatch
) -> None:
    """It calls those skills, so it may not start on a cell that never finished.

    Reachable only through a process-exit gate, which is what makes a failed
    planning-scene load stop it rather than let it drive an arm against a
    planning scene that holds nothing but the arm.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(line_context)
    assert not [
        a for a in actions if getattr(a, "node_executable", None) == "line_orchestrator"
    ], "the coordinator is started ungated, before anything it needs exists"
    assert _nodes(actions, "line_orchestrator", line_context)


# --- The gripper values the plan states are the ones L3 receives ---------------


def test_every_gripper_value_in_the_plan_reaches_the_skill_server(
    module: ModuleType,
) -> None:
    """A P1 defect wearing a disguise.

    Four keys were delivered by hand. One of them, `gripper_max_width_m`, exists
    in neither the plan nor the server's declared parameters, so it was accepted
    and dropped. The other eleven values the plan carries — the default grasp
    width, the goal tolerance, the drive rate and the seven linkage dimensions —
    never arrived at all, and the node ran on compiled defaults that happen to
    equal the L0 values. It worked only for as long as the two copies agreed.
    """
    plan = _plan()
    for manager in plan.controller_managers:
        if manager.moveit is None:
            continue
        delivered = module._skill_parameters(plan, manager)

        assert manager.gripper, manager.asset
        for key, value in manager.gripper.items():
            assert delivered[key] == value, f"{manager.asset}: {key}"
        assert "gripper_max_width_m" not in delivered, (
            "a parameter the skill server does not declare is accepted and dropped, "
            "which reads as delivered and is not"
        )
        assert delivered["asset_id"] == manager.asset
        assert delivered["use_sim_time"] is True


#: Where the L3 server declares its parameter names. Read rather than restated:
#: rclcpp drops an override for a parameter the node never declared, WITHOUT an
#: error, so a rename on either side of this boundary is silent by construction
#: and only a comparison can see it.
SKILL_SERVER = (
    Path(__file__).resolve().parents[2] / "cite_skills" / "src" / "skill_server.cpp"
)

#: The one delivered name the server does not declare, and does not have to.
#: `use_sim_time` is declared by rclcpp itself for every node.
BUILT_IN_PARAMETERS = frozenset({"use_sim_time"})

#: The planner choice the plan carries for L3 (ADR-0027), by the name the server
#: declares. Listed rather than derived from `MoveItConfig`: most of that
#: dataclass is artifact paths for move_group and never reaches the skill server,
#: so a derived list would assert something else and pass.
PLANNER_KEYS = (
    "default_pipeline",
    "default_planner_id",
    "fallback_pipeline",
    "fallback_planner_id",
    "cartesian_planner_ids",
)


def _declared_parameters() -> set:
    assert SKILL_SERVER.exists(), (
        f"{SKILL_SERVER} is not where this test expects it; the comparison below "
        "would silently assert nothing"
    )
    return set(re.findall(r'declare_parameter\(\s*"([A-Za-z0-9_]+)"', SKILL_SERVER.read_text()))


def test_every_planner_value_in_the_plan_reaches_the_skill_server(
    module: ModuleType,
) -> None:
    """The gripper defect above, in the shape ADR-0027 could repeat it.

    The test beside this one exists because eleven plan values silently failed to
    arrive. It iterates `manager.gripper`, and the planner choice is not there —
    it is on `manager.moveit`, so nothing that test does can see it. Which
    pipeline plans and which one rescues a refusal is exactly the kind of value
    whose absence changes nothing visible: the planner field stays empty, the
    default pipeline answers everything, and every scenario still passes.
    """
    plan = _plan()
    for manager in plan.controller_managers:
        if manager.moveit is None:
            continue
        delivered = module._skill_parameters(plan, manager)
        for key in PLANNER_KEYS:
            expected = getattr(manager.moveit, key)
            if isinstance(expected, tuple):
                expected = list(expected)
            assert key in delivered, f"{manager.asset}: {key} never reaches L3"
            assert delivered[key] == expected, f"{manager.asset}: {key}"

        # Not empty, which is the failure the four keys were added to prevent:
        # an empty pipeline name means "say nothing", so a plan that stopped
        # carrying them would leave every arm on move_group's own default and
        # look identical from outside.
        assert delivered["default_pipeline"], manager.asset
        assert delivered["default_planner_id"], manager.asset
        assert delivered["fallback_pipeline"] != delivered["default_pipeline"], (
            f"{manager.asset}: the fallback is the planner that would have refused"
        )


def test_the_skill_server_declares_every_parameter_the_plan_delivers(
    module: ModuleType,
) -> None:
    """The mechanism behind both of the tests above, asserted once.

    An override for an undeclared parameter is dropped by rclcpp without an
    error. That is why `gripper_max_width_m` "arrived" for as long as nobody
    checked. Comparing the delivered names against the declared ones catches the
    next one without anybody having to think of it first.
    """
    declared = _declared_parameters()
    plan = _plan()
    for manager in plan.controller_managers:
        if manager.moveit is None:
            continue
        delivered = set(module._skill_parameters(plan, manager))
        undeclared = delivered - declared - BUILT_IN_PARAMETERS
        assert not undeclared, (
            f"{manager.asset}: {sorted(undeclared)} are delivered to the skill server "
            f"and declared nowhere in {SKILL_SERVER.name}, so rclcpp drops them "
            "silently"
        )


def test_the_skill_servers_are_given_those_parameters(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    """The pure function above is only worth testing if the nodes use it."""
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    servers = _nodes(module._bring_up(context), "skill_server", context)
    assert len(servers) == 3
    namespaces = {_namespace(node, context) for node in servers}
    assert namespaces == {
        m.node.rsplit("/", 1)[0] for m in _plan().controller_managers
    }


# --- Every Gazebo-transport process is started in the plan's partition --------
#
# The half of ADR-0042 that cannot be checked next door. `require_gz_partition`
# is correct and useless if the environment it approves is not the environment
# the processes are actually given — which is the same defect shape this file
# was written for: a `require_hardware_opt_in` that nothing called, and a shell
# gate that guarded one command.
#
# The failure being prevented has no symptom. A bridge or a spawner started
# outside the server's partition sees an empty transport: the spawn service is
# simply not there, and a belt topic carries nothing, with no error at either
# end. Two servers sharing one partition is worse — they connect, and one belt
# setpoint drives both cells.

#: The packages in this launch whose processes speak the Gazebo transport.
#: `gz sim` itself is matched on its command instead, because it is an
#: `ExecuteProcess` rather than a `Node`.
GZ_TRANSPORT_PACKAGES = ("ros_gz_sim", "ros_gz_bridge")


def _package(context: LaunchContext, action: ExecuteProcess) -> str | None:
    """Read the ROS package a `Node` action runs from, or None for a bare process.

    `node_package` hands back whatever was passed to `Node(package=...)`, which
    here is a plain string; it is normalised anyway so that a substitution — a
    `LaunchConfiguration`, say — would still be read rather than crashing this
    helper into a false negative.
    """
    package = getattr(action, "node_package", None)
    if package is None:
        return None
    return perform_substitutions(context, normalize_to_list_of_substitutions(package))


def _environment(context: LaunchContext, action: ExecuteProcess) -> dict[str, str]:
    pairs = action.additional_env or []
    return {
        perform_substitutions(context, list(name)): perform_substitutions(
            context, list(value)
        )
        for name, value in pairs
    }


def _gz_transport_processes(
    context: LaunchContext, actions: list
) -> list[ExecuteProcess]:
    found = []
    for process in _processes(actions):
        package = _package(context, process)
        if package is not None:
            # A `Node`. Its command cannot be performed before execution — it
            # reads `context.locals.ros_specific_arguments`, which launch sets up
            # on the way in — so the package is the only thing readable here.
            if package in GZ_TRANSPORT_PACKAGES:
                found.append(process)
        elif _command(context, process)[:2] == ["gz", "sim"]:
            found.append(process)
    return found


def test_every_gazebo_process_carries_the_partition_the_plan_names(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    plan = load(Path(resolve_uri(GENERATED_PLAN)))
    expected = plan.sides[0].gz_partition

    actions = module._bring_up(context)
    carriers = _gz_transport_processes(context, actions)

    # The server, the bridge, the scene spawn, and one spawn per arm. Counted so
    # that a process added later without the partition fails here rather than
    # discovering an empty transport at run time.
    assert len(carriers) == 3 + len(plan.controller_managers)
    for process in carriers:
        assert _environment(context, process).get(GZ_PARTITION_ENV) == expected


def test_the_partition_does_not_depend_on_the_launching_shell(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    # A partition exported by hand must not reach the processes: it is generated
    # from L0 and is the one name that decides which cell a belt command lands
    # in, so a per-run override would be a second statement of it.
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    monkeypatch.setenv(GZ_PARTITION_ENV, "somewhere_else")
    plan = load(Path(resolve_uri(GENERATED_PLAN)))

    actions = module._bring_up(context)

    for process in _gz_transport_processes(context, actions):
        assert (
            _environment(context, process).get(GZ_PARTITION_ENV)
            == plan.sides[0].gz_partition
        )


def test_a_plan_with_no_partition_refuses_to_bring_the_cell_up(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    # A bring-up failure, not a warning. What a missing partition produces is
    # silence, and a warning about silence is read once and then never again.
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    document = copy.deepcopy(_document())
    del document["plan"]["sides"]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    _use(module, monkeypatch, path)

    actions = module._bring_up(context)

    assert "Shutdown" in _kinds(actions)
    assert not _processes(actions), "nothing may be started on the way to refusing"
    assert "sides" in _refusal(actions, context)


# --- A side starts on its own domain, or it does not start --------------------
#
# ADR-0044 clause 4's refusal, at the boundary that actually starts the side. The
# unit tests next door hold `require_domain` itself; these hold that this launch
# calls it, on the side it was asked for, and that a mismatch stops bring-up
# rather than producing a cell nobody is addressing.


def test_a_side_on_a_domain_that_is_not_its_own_refuses_to_start(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    # Base and carried domain disagree. This is the plant, at offset 0, so it is
    # the case that would have been unreachable had the base been read from
    # ROS_DOMAIN_ID - the whole reason CITE_DOMAIN_BASE travels separately.
    monkeypatch.setenv(DOMAIN_ENV, "43")
    actions = module._bring_up(context)
    message = _refusal(actions, context)
    assert "43" in message and DOMAIN_ENV in message


def test_a_side_started_without_a_base_refuses_to_start(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    monkeypatch.delenv(DOMAIN_BASE_ENV, raising=False)
    actions = module._bring_up(context)
    assert DOMAIN_BASE_ENV in _refusal(actions, context)


def _paired(module: ModuleType, tmp_path: Path, monkeypatch) -> None:
    """Point the launch at a plan for a paired zone, as `sides: pair` generates it."""
    document = copy.deepcopy(_document())
    # Built from whatever the generated plan declares rather than assuming it is
    # `single`: a checkout whose model has been flipped to `pair` for a run would
    # otherwise end up with two sides named 'counterpart', and these tests would
    # fail on the fixture rather than on what they are asking about.
    sides = document["plan"]["sides"]
    if not any(side["name"] == "counterpart" for side in sides):
        sides.append(
            {
                "name": "counterpart",
                "gz_partition": "cite/cell_a/counterpart",
                "domain_offset": 1,
            }
        )
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    _use(module, monkeypatch, path)


def test_the_counterpart_takes_the_other_partition_and_the_other_domain(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    """The two sides differ in their environment and in nothing else.

    The counterpart's launch is this launch, given a different `side:=`. It
    checks itself against base + 1 and hands its Gazebo processes the
    counterpart's partition, while every name it builds is the plant's byte for
    byte - ADR-0044 clause 1, and what makes a consumer portable between sides.
    """
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    _paired(module, tmp_path, monkeypatch)
    context.launch_configurations["side"] = "counterpart"
    monkeypatch.setenv(DOMAIN_ENV, "43")

    actions = module._bring_up(context)
    assert not any(isinstance(action, Shutdown) for action in actions), _kinds(actions)
    carriers = _gz_transport_processes(context, actions)
    assert carriers
    for process in carriers:
        assert (
            _environment(context, process).get(GZ_PARTITION_ENV)
            == "cite/cell_a/counterpart"
        )


def test_the_counterpart_started_on_the_plants_domain_refuses(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    # Two identically named node sets and two /clock publishers in one graph,
    # reported by nothing. The one failure the pair's isolation exists for.
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    _paired(module, tmp_path, monkeypatch)
    context.launch_configurations["side"] = "counterpart"
    actions = module._bring_up(context)
    assert DOMAIN_ENV in _refusal(actions, context)


def test_asking_an_untwinned_zone_for_a_counterpart_refuses(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    # Whether a zone runs as a pair is an L0 fact. Bring-up does not invent a
    # second side, and the refusal says so rather than reporting a domain error.
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    context.launch_configurations["side"] = "counterpart"
    assert "counterpart" in _refusal(module._bring_up(context), context)


# --- The chain ends on a witness, and the token is the last thing it says -----
#
# ADR-0047 clause 3. Until this existed the last gate was labelled "the skill
# servers" and fired when they were started rather than when they were serving,
# and nothing anywhere announced that a cell had finished coming up.

WITNESS_EXECUTABLE = "readiness_witness.py"


def _readiness_gate(actions: list, context: LaunchContext):
    """Return the one process-exit gate whose clean branch emits the token.

    Found by what it does rather than by where it sits in the list. A handler
    identified positionally would keep passing after an edit moved it, which is
    the positional meaning this project refuses everywhere else.
    """
    found = []
    for action in actions:
        if not isinstance(action, RegisterEventHandler):
            continue
        handler = action.event_handler
        if not isinstance(handler, OnProcessExit):
            continue
        if READY_TOKEN in _logged(handler.handle(_Exited(returncode=0), context) or [],
                                  context):
            found.append(handler)
    assert len(found) == 1, "exactly one gate announces this side's readiness"
    return found[0]


def _logged(entities: list, context: LaunchContext) -> str:
    return "\n".join(
        perform_substitutions(context, list(entity.msg))
        for entity in entities
        if isinstance(entity, LogInfo)
    )


def test_the_side_starts_exactly_one_readiness_witness(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    witnesses = _nodes(module._bring_up(context), WITNESS_EXECUTABLE, context)
    assert len(witnesses) == 1, "one witness per side, not one per arm"
    assert module._witness_arguments(_plan(), PLANT_SIDE) == [
        "--zone",
        "cell_a",
        "--side",
        PLANT_SIDE,
    ]


def test_the_witness_is_started_with_no_environment_of_its_own(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    # It has to inherit this launch's, because that is what puts it on this
    # side's domain. A witness given an environment of its own is a witness that
    # could be pointed at another graph (ADR-0047, clause 3).
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    witness = _nodes(module._bring_up(context), WITNESS_EXECUTABLE, context)[0]
    assert not _environment(context, witness)


def test_the_readiness_token_names_this_side(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)
    gate = _readiness_gate(actions, context)
    announced = _logged(gate.handle(_Exited(returncode=0), context) or [], context)
    assert announced_side(announced) == PLANT_SIDE


def test_the_counterpart_announces_itself_as_the_counterpart(
    module: ModuleType, context: LaunchContext, tmp_path: Path, monkeypatch
) -> None:
    # The supervisor reads its own child's pipe and already knows which side it
    # started, so this is the cross-check: a launch given the wrong `side:=`
    # announces a side its supervisor is not expecting rather than passing.
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    _paired(module, tmp_path, monkeypatch)
    context.launch_configurations["side"] = "counterpart"
    monkeypatch.setenv(DOMAIN_ENV, "43")
    actions = module._bring_up(context)
    gate = _readiness_gate(actions, context)
    announced = _logged(gate.handle(_Exited(returncode=0), context) or [], context)
    assert announced_side(announced) == "counterpart"


def test_a_witness_that_expired_announces_nothing_and_stops_bring_up(
    module: ModuleType, context: LaunchContext, monkeypatch
) -> None:
    monkeypatch.delenv(HARDWARE_OPT_IN_ENV, raising=False)
    actions = module._bring_up(context)
    gate = _readiness_gate(actions, context)
    produced = gate.handle(_Exited(returncode=1), context) or []
    assert any(isinstance(entity, Shutdown) for entity in produced)
    assert READY_TOKEN not in _logged(produced, context)


def test_the_launch_file_writes_the_token_nowhere() -> None:
    """Two string literals would be the defect this design exists to avoid.

    ADR-0047 clause 3 requires the token to be defined once in `cite_bringup` and
    imported by both the emitter and the reader. This is the check that the
    emitter did not grow a copy of it, and that the announcement is made in one
    place rather than on several gates.
    """
    source = LAUNCH_FILE.read_text()
    assert READY_TOKEN not in source
    assert source.count("ready_announcement(") == 1


# --- Anything this package installs as a program has to be one ----------------
#
# The defect this closes, and it is worth stating as a class: **`install(PROGRAMS
# ...)` does not make a file executable under a symlink install.** colcon
# symlinks the installed path back at the source file, so the mode is the
# source's mode, and a Python file committed without the executable bit reaches
# the launch as `PermissionError: [Errno 13]`.
#
# It cost the first paired bring-up its join. Both sides came up completely -
# nine controllers, three planning scenes, three skill servers accepting goals -
# and neither announced, because launch reports a failure to EXEC as an
# exception on its own logger rather than as a process exit, so `_gate` never
# fired and nothing downstream noticed. What caught it was the pair supervisor's
# ceiling, which is the row ADR-0047 clause 4 wrote for exactly this shape: a
# side that never announced readiness and never exited.
#
# Read out of CMakeLists rather than listed here, so the check covers the next
# program this package installs without anybody remembering to extend it.


def _installed_programs() -> list[Path]:
    source = (LAUNCH_FILE.parent.parent / "CMakeLists.txt").read_text()
    found = []
    for block in re.findall(r"install\(PROGRAMS(.*?)\)", source, re.DOTALL):
        for line in block.splitlines():
            name = line.strip()
            if not name or name.startswith("DESTINATION"):
                continue
            found.append(
                LAUNCH_FILE.parent.parent
                / name.replace("${PROJECT_NAME}", "cite_bringup")
            )
    return found


def test_every_installed_program_is_executable_in_the_tree() -> None:
    programs = _installed_programs()
    assert programs, (
        "no install(PROGRAMS ...) found in CMakeLists.txt. If it moved, move this "
        "check with it rather than deleting it."
    )
    for program in programs:
        assert program.is_file(), program
        assert os.access(program, os.X_OK), (
            f"{program} is installed as a program and is not executable. Under a "
            "symlink install the installed path IS this file, so the launch that "
            "starts it fails to exec - and a failure to exec is reported by "
            "launch as an exception rather than as a non-zero process exit, so "
            "no gate fires."
        )
