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
from pathlib import Path
from types import ModuleType

from cite_bringup.plan import HARDWARE_OPT_IN_ENV, load, resolve_uri
from launch import LaunchContext
from launch.actions import ExecuteProcess, LogInfo, RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch.utilities import perform_substitutions
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


@pytest.fixture()
def context() -> LaunchContext:
    ctx = LaunchContext()
    ctx.launch_configurations["zone"] = "cell_a"
    ctx.launch_configurations["headless"] = "true"
    ctx.launch_configurations["line"] = "false"
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

    What it buys is narrow and must not be overstated: it seeds `gz::math::Rand`
    — sensor noise and the transport RNG — and not the physics solver, and it has
    nothing to do with OMPL. This asserts the value arrives, not that a scenario
    is reproducible.
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


# --- The Gazebo/ROS bridge: nine names, none of them written here -------------
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
    `cite_bringup` bridged `/clock` and nothing else. Nine declared interfaces had
    no ROS endpoint at all, so the bring-up plan advertised a system the running
    one did not provide.
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
