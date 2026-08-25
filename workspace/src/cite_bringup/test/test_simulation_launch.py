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

from cite_bringup.plan import HARDWARE_OPT_IN_ENV, resolve_uri
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
    return ctx


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
