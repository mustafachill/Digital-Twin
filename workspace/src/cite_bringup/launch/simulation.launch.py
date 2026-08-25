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

"""Bring the simulated cell up, event by event.

There is not one `TimerAction` in this file, and there must never be. v1
sequenced its bring-up with sleeps — twelve seconds per robot, a number raised
whenever startup failed rather than because it meant anything — which put the
third robot's controllers at t = 31 s and worked only on a machine fast enough.
P4 exists because of that, and this file is where P4 is either kept or lost.

The distinction that makes event-driven bring-up possible here:

    Waiting on a condition with a deadline that FAILS is event-driven.
    Waiting a fixed duration and proceeding regardless is not.

`ros_gz_sim create` blocks on the world's create service and on the latched
description, then exits — its exit is a real completion event, not an estimate.
`controller_manager spawner` blocks on the manager's list_controllers service and
exits non-zero on expiry. Its `--controller-manager-timeout` is a deadline, never
a schedule: no correct behaviour depends on its value, and expiry stops bring-up
with a diagnosis instead of continuing into a degraded system.

Every step that can fail stops the launch. That is the second half of P4 and the
one that is easy to lose: an event-gated chain whose last link is ungated brings
the system up half-built and reports success. `_gate` is applied to *every* link,
including the last one, and every long-running process carries `_fatal_on_exit`
so that a node dying mid-run tears the launch down instead of leaving a cell that
answers some interfaces and not others.

Everything specific to *this* cell — the world, the arms, their controllers, the
order — comes from the generated plan. Adding a fourth arm changes that plan and
not this file.
"""

from __future__ import annotations

import os

from cite_bringup.plan import (
    default_plan_path,
    load,
    Plan,
    PlanError,
    require_hardware_opt_in,
)
from launch import LaunchContext, LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    EmitEvent,
    ExecuteProcess,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
    Shutdown,
)
from launch.event_handlers import OnProcessExit
from launch.events import matches_action
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from launch_ros.parameter_descriptions import ParameterValue
from lifecycle_msgs.msg import Transition
import yaml

#: Deadline, not a schedule. Generous enough that a loaded machine still makes it,
#: and short enough that a genuinely absent controller manager is reported rather
#: than waited on forever. Nothing about correct behaviour depends on the value.
SPAWNER_DEADLINE_S = 120

#: The spawner's own default for a controller state switch is five seconds, and
#: that is a timing assumption inside a tool we do not control. Three controller
#: managers switching at once, on top of a 1 kHz physics loop, exceeded it on a
#: loaded machine and bring-up failed — which is precisely the lurking timing
#: assumption cross-cutting-lifecycle.md says a loaded machine must catch.
#: Raised to a real deadline; correctness still does not depend on the value.
SWITCH_DEADLINE_S = 60

#: How long launch lets a process finish its OWN shutdown before escalating to
#: SIGTERM and then SIGKILL. launch's default is five seconds, which is an
#: undocumented implicit deadline: a `move_group` still tearing down at five
#: seconds was killed mid-teardown and reported `-15`, so the run recorded the
#: truncation rather than whatever the process was actually doing. These are
#: ceilings on a failure, not a schedule — nothing waits for them, and a process
#: that exits immediately is not delayed by a millisecond.
#:
#: This does NOT order shutdown. launch broadcasts SIGINT to every process in one
#: event dispatch, so a sim-time consumer and its clock source are still signalled
#: together; see the note on shutdown ordering in the fix report and T-01.
TEARDOWN_SIGTERM_S = "45"
TEARDOWN_SIGKILL_S = "60"

#: Where `./scripts/scenario` puts the seed it decides once per run.
PHYSICS_SEED_ENV = "CITE_PHYSICS_SEED"


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "headless",
                default_value="true",
                description="Run the simulator without a GUI. Required on macOS and in CI.",
            ),
            DeclareLaunchArgument(
                "zone",
                default_value="cell_a",
                description="Which zone of the facility model to bring up.",
            ),
            OpaqueFunction(function=_bring_up),
        ]
    )


def _bring_up(context: LaunchContext) -> list:
    zone = LaunchConfiguration("zone").perform(context)
    headless = LaunchConfiguration("headless").perform(context).lower() in ("true", "1")

    try:
        plan = load(default_plan_path(zone))
        # The safety gate, at the ROS boundary rather than only at the shell one.
        # `scripts/_lib.sh` refuses `./scripts/enter hardware` without the opt-in
        # and guards nothing else; a plan naming a hardware backend reaches a
        # physical arm through this launch by every other route. Refusing to
        # start is not a divergence between the sim and real paths (P2) — what
        # gets commanded is identical either way; it simply may not begin by
        # accident (cross-cutting-safety.md).
        require_hardware_opt_in(plan, os.environ)
        seed = _seed(os.environ)
    except PlanError as exc:
        # Fail here, with the reason, rather than launching a partial system that
        # fails three layers later pointing nowhere near the cause.
        return [LogInfo(msg=f"BRING-UP FAILED: {exc}"), Shutdown(reason=str(exc))]

    actions: list = [
        LogInfo(
            msg=f"Bringing up zone {plan.zone}: scene plus "
                f"{len(plan.controller_managers)} arm(s)"
        ),
        # Gazebo resolves system plugins from GZ_SIM_SYSTEM_PLUGIN_PATH, which the
        # ROS environment does not populate. Without this, gz_ros2_control-system
        # fails to load, no controller manager is ever created, and the visible
        # error is a spawner timing out on a service — which points at the
        # spawner rather than at a missing plugin path.
        AppendEnvironmentVariable(
            "GZ_SIM_SYSTEM_PLUGIN_PATH",
            os.path.join("/opt/ros", os.environ.get("ROS_DISTRO", "jazzy"), "lib"),
        ),
    ]
    actions += _simulator(plan, headless=headless, seed=seed)
    actions += _scene(plan)
    actions += _arms(plan)
    actions += _facility(plan)
    controller_actions, last_spawner = _controllers(plan)
    actions += controller_actions
    actions += _motion_planning(plan)

    # The cell's furniture into each arm's planning scene, then the skills. Both
    # gated, and in that order: every pick and place point in this cell lies
    # exactly on a surface, so a skill server that accepts a goal before the
    # collision objects are in the scene plans through the table it is picking
    # from. The loader exits when the scene has actually been applied, which is
    # the completion event the gate needs (P4).
    scene_actions, last_step = _planning_scene(plan, last_spawner)
    actions += scene_actions

    # Skills come last. That is the order cross-cutting-lifecycle.md fixes —
    # controllers, then MoveIt, then skills — and it is a real dependency, not a
    # preference: MoveGroupInterface needs a current robot state, which does not
    # exist until a broadcaster is publishing.
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=last_step,
                on_exit=_gate(_skills(plan), "the skill servers"),
            )
        )
    )
    return actions


def _seed(environ: dict) -> str | None:
    """Read the seed `gz sim` is started with, if the caller supplied one.

    What this buys, stated precisely because the previous absence of a consumer
    was papered over with a claim that was not true: `gz sim --seed` calls
    `gz::math::Rand::Seed`, which seeds sensor noise and the transport RNG. It
    does **not** seed the physics solver, and it has nothing to do with OMPL,
    which is the stochastic component that decides whether two runs of a scenario
    produce the same trajectory. Passing it therefore does not make a scenario
    reproducible and must not be described as doing so. Planning determinism is a
    separate decision and arrives with a deterministic planner, not with this.

    A malformed value is refused rather than ignored: silently dropping it would
    leave a run that believes it is seeded and is not.
    """
    raw = environ.get(PHYSICS_SEED_ENV)
    if raw is None or raw.strip() == "":
        return None
    try:
        return str(int(raw))
    except ValueError as exc:
        # Shares the launch's single refusal path: the failure is the same shape
        # — the run cannot start as configured — and it is reported the same way.
        raise PlanError(
            f"{PHYSICS_SEED_ENV}={raw!r} is not an integer. `gz sim --seed` takes "
            "an integer; a run started with a value it will not accept is a run "
            "whose seed is silently absent."
        ) from exc


def _simulator(plan: Plan, *, headless: bool, seed: str | None) -> list:
    gz_args = ["-s", "-r", "-v", "2"] if headless else ["-r", "-v", "2"]
    if seed is not None:
        gz_args += ["--seed", seed]
    gz_args.append(str(plan.world))

    simulator = ExecuteProcess(
        cmd=["gz", "sim", *gz_args],
        output="screen",
        # An orphaned `gz sim` holds ports and names, and the *next* bring-up then
        # fails pointing nowhere useful. Tearing the whole launch down when the
        # simulator exits is what keeps that from happening.
        on_exit=Shutdown(reason="the simulator exited"),
        sigterm_timeout="10",
        sigkill_timeout="15",
    )

    clock = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
    )

    return [simulator, clock]


def _scene(plan: Plan) -> list:
    """Publish and spawn the static half of the cell: pedestals, tables, belts.

    The description is published TRANSIENT_LOCAL (the LATCHED profile), which is
    what lets `create` receive it whenever it happens to start. Were it VOLATILE,
    a consumer starting a moment late would wait forever with no error anywhere —
    the exact silent failure docs/interfaces/qos-profiles.md exists to prevent.
    """
    scene_description = ParameterValue(Command(["xacro ", str(plan.scene)]), value_type=str)

    publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="scene_description_publisher",
        parameters=[{"robot_description": scene_description, "use_sim_time": True}],
        output="screen",
    )

    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_scene",
        arguments=["-topic", "robot_description", "-name", f"{plan.zone}_scene"],
        output="screen",
        # `create` exiting non-zero means the scene is not in the world. Every
        # controller spawner after it would then wait out its full deadline on a
        # controller manager that gz_ros2_control never created, and report a
        # service timeout — which names the spawner rather than the spawn.
        on_exit=_fatal_on_exit(f"spawning the {plan.zone} scene"),
    )

    return [publisher, spawn]


def _arms(plan: Plan) -> list:
    """Publish and spawn each arm as its own model.

    One Gazebo model per arm, because gz_ros2_control attaches to a model and the
    controller manager it creates claims every ros2_control component in that
    model's description. With all three arms in one model, all three managers
    claimed all eighteen joints and wrote to them every cycle — three managers
    fighting over the same hardware, which nothing reports and which would surface
    much later as motion nobody can explain.

    Each arm's own publisher lives in that arm's namespace, so its controller
    manager finds the description without a remapping, and TF stays at one
    publisher per transform.
    """
    actions: list = []
    for manager in plan.controller_managers:
        description = ParameterValue(
            Command(["xacro ", str(manager.description)]), value_type=str
        )
        actions.append(
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="description_publisher",
                namespace=manager.node.rsplit("/", 1)[0],
                parameters=[{"robot_description": description, "use_sim_time": True}],
                # Without these the publisher would write to <ns>/tf, and nothing
                # listening on /tf would ever see this arm.
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
            )
        )
        x, y, z = manager.spawn_xyz_m
        roll, pitch, yaw = manager.spawn_rpy_rad
        actions.append(
            Node(
                package="ros_gz_sim",
                executable="create",
                name=f"spawn_{manager.asset}",
                arguments=[
                    "-topic", manager.description_topic,
                    "-name", manager.asset,
                    "-x", str(x), "-y", str(y), "-z", str(z),
                    "-R", str(roll), "-P", str(pitch), "-Y", str(yaw),
                ],
                output="screen",
                on_exit=_fatal_on_exit(f"spawning {manager.asset}"),
            )
        )
    return actions


def _controllers(plan: Plan) -> tuple[list, Node]:
    """Spawn each manager's controllers, stage by stage, gated on the previous.

    The chain starts from `create` exiting — the moment the cell is genuinely in
    the world — and every subsequent step starts only when the one before it
    exits successfully. A non-zero exit anywhere stops the launch with a message
    naming the step, rather than leaving a half-built system running. Including
    the last stage: what follows the final spawner is gated by the caller with
    the same `_gate`, because an ungated last link is how a chain that reports
    every intermediate failure still lets the one that matters through.
    """
    actions: list = []
    previous: object | None = None

    # One chain across every manager and stage, rather than one chain per arm.
    # Spawning three arms concurrently means three controller managers performing
    # a state switch simultaneously while physics runs, and the contention made
    # bring-up intermittent — a scenario that passed and then failed on the very
    # next run. A single chain is still entirely event-gated: each step starts
    # when the previous one exits, so bring-up remains as fast as the machine
    # allows. It is simply no longer racing itself.
    for manager in plan.controller_managers:
        for stage, names in manager.stages():
            spawner = Node(
                package="controller_manager",
                executable="spawner",
                name=f"spawn_{manager.asset}_stage{stage}",
                arguments=[
                    *names,
                    "--controller-manager",
                    manager.node,
                    "--controller-manager-timeout",
                    str(SPAWNER_DEADLINE_S),
                    "--switch-timeout",
                    str(SWITCH_DEADLINE_S),
                ],
                output="screen",
            )

            if previous is None:
                # The first spawner waits on its controller manager's service,
                # which exists only once gz_ros2_control has instantiated it —
                # which in turn happens only once the model is in the world. The
                # dependency is enforced by service availability, not by a guess.
                actions.append(spawner)
            else:
                actions.append(
                    RegisterEventHandler(
                        OnProcessExit(
                            target_action=previous,
                            on_exit=_gate(
                                [spawner],
                                f"{manager.asset} stage {stage}",
                                hint=_SPAWNER_HINT,
                            ),
                        )
                    )
                )
            previous = spawner

    assert previous is not None, "the plan declared no controllers to spawn"
    return actions, previous


def _planning_scene(plan: Plan, previous: Node) -> tuple[list, Node]:
    """Load the generated collision objects into each arm's planning scene.

    Without this an arm's planning scene contains that arm and nothing else, and
    every plan in the cell is computed against an empty world. That is not an
    exotic failure here: every pick and place point lies exactly on a surface, so
    a plan that dives through the surface is the normal case, and it surfaces as
    a controller fault rather than as a missing obstacle.

    One loader per arm, in that arm's namespace, chained rather than concurrent —
    for the same reason the spawners are chained, and because each loader is a
    single service call that completes in milliseconds once move_group answers.
    A loader exits when the scene it was asked to apply is actually in place, so
    its exit is a completion event and not an estimate.
    """
    actions: list = []
    last: Node = previous
    for manager in plan.controller_managers:
        if manager.moveit is None:
            continue
        loader = Node(
            package="cite_facility",
            executable="planning_scene_loader.py",
            name=f"load_planning_scene_{manager.asset}",
            # In the arm's own namespace, so `apply_planning_scene` resolves to
            # that arm's move_group without this file composing a service name.
            namespace=manager.node.rsplit("/", 1)[0],
            parameters=[{"zone": plan.zone, "use_sim_time": True}],
            output="screen",
        )
        actions.append(
            RegisterEventHandler(
                OnProcessExit(
                    target_action=last,
                    on_exit=_gate(
                        [loader],
                        f"the planning scene for {manager.asset}",
                        hint=_SPAWNER_HINT,
                    ),
                )
            )
        )
        last = loader
    return actions, last


def _managed(node: LifecycleNode, name: str) -> list:
    """Drive a managed node through configure and activate, on its transitions.

    Not on a timer. `configure` is where a node reads and validates everything it
    needs; if it cannot, it returns FAILURE and never reaches `inactive`.

    That last sentence used to be the whole story, and it was half of one: the
    activation below indeed never fires, but nothing else was gated on these
    nodes either, so bring-up carried on regardless. `frame_server.on_configure`
    returning FAILURE produced a cell that came up fully with a disconnected TF
    tree, and every subsequent skill goal failed with a lookup error naming
    frames rather than the node that never published them. So each failing
    transition is registered here and stops the launch with the node's own
    diagnosis.

    The success handler matches `configuring -> inactive` specifically rather
    than any transition ending in `inactive`. A failed activation lands in
    `inactive` too, and a handler matching only the goal state would answer it by
    trying to activate again.
    """
    configure = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(node),
            transition_id=Transition.TRANSITION_CONFIGURE,
        )
    )
    activate = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=node,
            start_state="configuring",
            goal_state="inactive",
            entities=[
                EmitEvent(
                    event=ChangeState(
                        lifecycle_node_matcher=matches_action(node),
                        transition_id=Transition.TRANSITION_ACTIVATE,
                    )
                )
            ],
        )
    )
    refusals = [
        _refuses(node, name, "configuring", "unconfigured", "on_configure returned FAILURE"),
        _refuses(node, name, "configuring", "errorprocessing", "on_configure raised"),
        _refuses(node, name, "activating", "inactive", "on_activate returned FAILURE"),
        _refuses(node, name, "activating", "errorprocessing", "on_activate raised"),
    ]
    # The handlers are registered before the transition is emitted, so a node that
    # configures very quickly cannot reach `inactive` before anything is watching.
    return [activate, *refusals, node, configure]


def _refuses(
    node: LifecycleNode, name: str, start_state: str, goal_state: str, what: str
) -> RegisterEventHandler:
    """Stop the launch when a managed node fails a transition."""
    message = (
        f"BRING-UP FAILED: {name} could not reach `active` — {what} "
        f"({start_state} -> {goal_state}). The node logged why, immediately above "
        "this line. Nothing downstream of it is started, because a cell missing "
        "one of these answers some interfaces and not others."
    )
    return RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=node,
            start_state=start_state,
            goal_state=goal_state,
            entities=[LogInfo(msg=message), Shutdown(reason=message)],
        )
    )


def _facility(plan: Plan) -> list:
    """Runtime access to the generated artifacts: frames, model version, topology.

    These are managed nodes with no dependency on the simulator, so they come up
    alongside it rather than after it. The frame server matters most: without it
    an arm's own model is a disconnected TF tree, and a skill given a pose in
    cite_world can never resolve it into the arm's planning frame.
    """
    zone = {"zone": plan.zone}
    return [
        *_managed(
            LifecycleNode(
                package="cite_facility",
                executable="frame_server.py",
                name="frame_server",
                namespace="/cite/facility",
                parameters=[zone, {"use_sim_time": True}],
                remappings=[("/tf_static", "/tf_static")],
                output="screen",
            ),
            "frame_server",
        ),
        *_managed(
            LifecycleNode(
                package="cite_facility",
                executable="model_info.py",
                name="model_info",
                namespace="/cite/facility",
                parameters=[{"zones": [plan.zone]}, {"use_sim_time": True}],
                output="screen",
            ),
            "model_info",
        ),
        *_managed(
            LifecycleNode(
                package="cite_facility",
                executable="topology_server.py",
                name="topology_server",
                namespace="/cite/facility",
                parameters=[zone, {"use_sim_time": True}],
                output="screen",
            ),
            "topology_server",
        ),
    ]


def _skills(plan: Plan) -> list:
    """One skill server per arm, in that arm's namespace.

    Every name it uses arrives as a generated parameter — the planning group, the
    tip link, the controller actions, the home configuration. The server builds
    none of them, which is what keeps the number of places a name is made at one
    (P2). It refuses to start if any is missing, rather than guessing and
    advertising skills that command nothing.
    """
    actions: list = []
    for manager in plan.controller_managers:
        if manager.moveit is None:
            continue
        namespace = manager.node.rsplit("/", 1)[0]
        # MoveGroupInterface builds its own RobotModel, so the skill server needs
        # the same description, semantics and kinematics parameters move_group
        # has. Without the kinematics entry it loads the model, warns "No
        # kinematics plugins defined", and then fails every pose goal with an
        # inverse-kinematics error that says nothing about a missing parameter.
        robot_description = ParameterValue(
            Command(["xacro ", str(manager.description)]), value_type=str
        )
        semantic = ParameterValue(
            Command(["xacro ", str(manager.moveit.srdf)]), value_type=str
        )
        actions.append(
            Node(
                package="cite_skills",
                executable="skill_server",
                name="skill_server",
                namespace=namespace,
                parameters=[
                    {
                        "robot_description": robot_description,
                        "robot_description_semantic": semantic,
                    },
                    _yaml_parameters(
                        manager.moveit.kinematics, prefix="robot_description_kinematics"
                    ),
                    _yaml_parameters(
                        manager.moveit.joint_limits, prefix="robot_description_planning"
                    ),
                    {
                        "asset_id": manager.asset,
                        "zone": plan.zone,
                        "planning_group": manager.moveit.group,
                        "tip_link": manager.moveit.tip_link,
                        "gripper_action": manager.gripper_action or "",
                        "gripper_open_position": manager.gripper_open_position,
                        "gripper_closed_position": manager.gripper_closed_position,
                        "gripper_max_width_m": manager.gripper_max_width_m,
                        "home_rad": list(manager.moveit.home_rad),
                        "use_sim_time": True,
                    }
                ],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
                # A skill server that dies takes its arm's skills with it and
                # nothing else notices: the action server simply stops existing,
                # and the next goal waits out its client's deadline.
                on_exit=_fatal_on_exit(f"the {manager.asset} skill server"),
                sigterm_timeout=TEARDOWN_SIGTERM_S,
                sigkill_timeout=TEARDOWN_SIGKILL_S,
            )
        )
    return actions


def _motion_planning(plan: Plan) -> list:
    """One move_group per arm, in that arm's namespace.

    Per arm rather than per cell, because each arm is its own model with its own
    description and its own controller manager. Nothing above L3 talks to MoveIt
    (ADR-0006); the skill servers are its only client.

    move_group is started unconditionally rather than gated on the controllers:
    it waits for /joint_states on its own, and gating it here would add an
    ordering constraint that the system does not actually have.
    """
    actions: list = []
    for manager in plan.controller_managers:
        moveit = manager.moveit
        if moveit is None:
            continue

        namespace = manager.node.rsplit("/", 1)[0]
        robot_description = ParameterValue(
            Command(["xacro ", str(manager.description)]), value_type=str
        )
        semantic = ParameterValue(Command(["xacro ", str(moveit.srdf)]), value_type=str)

        parameters: list = [
            {
                "robot_description": robot_description,
                "robot_description_semantic": semantic,
                "use_sim_time": True,
                "publish_robot_description_semantic": True,
            },
            _yaml_parameters(moveit.kinematics, prefix="robot_description_kinematics"),
            _yaml_parameters(moveit.joint_limits, prefix="robot_description_planning"),
            # Loaded as dictionaries rather than passed as --params-file. A ROS
            # parameter FILE must be shaped `<node>: ros__parameters: ...`; these
            # generated files hold the content without that wrapper, because the
            # wrapper is a ROS plumbing convention and not a fact about the
            # facility. Passing them as files fails at rcl with "Sequences can
            # only be values and not keys in params", which points at the YAML
            # rather than at the missing wrapper.
            _yaml_parameters(moveit.ompl),
            _yaml_parameters(moveit.controllers),
            {
                # No depth sensor feeds this cell yet, so the octomap monitor
                # has nothing to update from. Setting the resolution silences the
                # "Resolution not specified" warning; it does NOT silence the
                # accompanying "No 3D sensor plugin(s) defined for octomap
                # updates" ERROR, which move_group logs regardless and which is
                # accurate — there are no sensors. It goes away when Phase 3
                # brings depth sensing, not before.
                "octomap_resolution": 0.05,
                "publish_planning_scene": True,
                "publish_geometry_updates": True,
                "publish_state_updates": True,
                "publish_transforms_updates": True,
            },
        ]

        actions.append(
            Node(
                package="moveit_ros_move_group",
                executable="move_group",
                name="move_group",
                namespace=namespace,
                parameters=parameters,
                # move_group listens on the global TF tree; without these it would
                # subscribe inside its namespace and never see the arm it plans for.
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
                on_exit=_fatal_on_exit(f"move_group for {manager.asset}"),
                # move_group tears down while the simulator that owns its clock is
                # tearing down too, and launch's implicit five-second default was
                # cutting that teardown short and recording the truncation. These
                # ceilings stop the run from measuring launch's default instead of
                # move_group's behaviour. They do not order the shutdown — see the
                # note on TEARDOWN_SIGTERM_S.
                sigterm_timeout=TEARDOWN_SIGTERM_S,
                sigkill_timeout=TEARDOWN_SIGKILL_S,
            )
        )
    return actions


def _yaml_parameters(path, *, prefix: str | None = None) -> dict:
    """Load a generated YAML file under a parameter prefix.

    MoveIt expects kinematics and joint limits nested under
    `robot_description_kinematics` and `robot_description_planning`. The generated
    files hold the content without that nesting, because the nesting is a MoveIt
    convention rather than a fact about the facility — so it is applied here,
    where MoveIt is the consumer.
    """
    document = yaml.safe_load(path.read_text()) or {}
    return {prefix: document} if prefix else document


#: Appended to a gate's message when the step that failed waits on a service.
_SPAWNER_HINT = (
    "A timeout at this step usually means the node it waits on never appeared, or "
    "that a controller's joint names do not match the description — run "
    "./scripts/validate-model."
)


def _gate(entities: list, what: str, *, hint: str = "") -> callable:
    """Continue to `entities` only if the step that just exited actually succeeded.

    Applied to every link in the chain. An ungated final link is the failure this
    exists to prevent: the intermediate stages reported their failures correctly
    while the last one let a non-zero exit through, and the skill servers started
    against a cell that had never finished coming up.
    """

    def handler(event, context):  # noqa: ANN001, ARG001 - launch's callback shape
        if event.returncode == 0:
            return entities
        message = (
            f"BRING-UP FAILED before {what}: the previous step exited "
            f"{event.returncode}. {hint}".rstrip()
        )
        return [LogInfo(msg=message), Shutdown(reason=message)]

    return handler


def _fatal_on_exit(what: str) -> callable:
    """Stop the launch when a process dies before the launch was shutting down.

    The `context.is_shutdown` check is what makes this usable on a long-running
    node: during a normal teardown every process exits, and reporting each of
    them as a bring-up failure would bury the real reason the run ended.
    """

    def handler(event, context):  # noqa: ANN001 - launch's callback shape
        if context.is_shutdown or event.returncode == 0:
            return None
        message = (
            f"BRING-UP FAILED: {what} exited {event.returncode}. The cell is "
            "stopped rather than left running without it."
        )
        return [LogInfo(msg=message), Shutdown(reason=message)]

    return handler
