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

from cite_bringup.gz import gz_environment
from cite_bringup.plan import (
    default_plan_path,
    load,
    Plan,
    PlanError,
    PLANT_SIDE,
    require_domain,
    require_hardware_opt_in,
    resolve_uri,
)
from cite_bringup.readiness import ready_announcement
from cite_interfaces.msg import LineState
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

#: The hand-written subtree that says what ONE station does. How many stations
#: there are, what each is called and which arm serves it are generated from the
#: L0 topology by L4 itself. This is mechanism belonging to `cite_orchestration`
#: rather than a fact about the facility, which is why it is named here and not
#: carried in the plan.
STATION_TREE_URI = "package://cite_orchestration/trees/line_station.xml"


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
            DeclareLaunchArgument(
                "side",
                default_value=PLANT_SIDE,
                description=(
                    "Which side of the zone this launch is. The two sides of a "
                    "twin pair share every generated artifact and differ only in "
                    "the environment their processes start in, so this argument "
                    "selects the partition and the domain this launch checks "
                    "itself against - it changes no name (ADR-0044, ADR-0047)."
                ),
            ),
            DeclareLaunchArgument(
                "line",
                default_value="false",
                description=(
                    "Start the L4 line coordinator, which drives every station in the "
                    "zone. Off by default: it takes exclusive hold of each arm's skills, "
                    "so a scenario or an operator driving one arm directly would find "
                    "their goals refused by a server already serving the line."
                ),
            ),
            OpaqueFunction(function=_bring_up),
        ]
    )


def _bring_up(context: LaunchContext) -> list:
    zone = LaunchConfiguration("zone").perform(context)
    headless = LaunchConfiguration("headless").perform(context).lower() in ("true", "1")
    line = LaunchConfiguration("line").perform(context).lower() in ("true", "1")
    side = LaunchConfiguration("side").perform(context)

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
        # The other half of one rule. A process belonging to a side carries both
        # isolations, so both are refused in the same place: this one asks
        # whether the process about to start the side is itself on the domain the
        # plan resolves for that side, comparing `ROS_DOMAIN_ID` against
        # `CITE_DOMAIN_BASE` plus the side's offset. Two independently sourced
        # values, so the plant's half can fail rather than reducing to
        # `env == env + 0` (ADR-0044, clause 4).
        require_domain(plan, side, os.environ)
        # The environment every Gazebo-transport process in this launch is
        # started with. Built once, from the plan, and checked before a single
        # process is described — so the refusal answers the question that
        # actually matters, which is not "did someone export a partition" but
        # "does the environment this launch is about to hand to `gz sim` carry
        # the partition the plan names" (ADR-0042).
        gz_env = gz_environment(plan, side)
        seed = _seed(os.environ)
    except PlanError as exc:
        # Fail here, with the reason, rather than launching a partial system that
        # fails three layers later pointing nowhere near the cause.
        return [LogInfo(msg=f"BRING-UP FAILED: {exc}"), Shutdown(reason=str(exc))]

    actions: list = [
        LogInfo(
            msg=f"Bringing up zone {plan.zone} side {side}: scene plus "
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
    actions += _simulator(plan, headless=headless, seed=seed, gz_env=gz_env)
    actions += _scene(plan, gz_env)
    actions += _arms(plan, gz_env)
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

    # The zone's detection server comes up with the facility nodes rather than
    # after the arms: it commands no motion, needs neither the planner nor a
    # controller, and the sooner it is subscribed the sooner a beam that is
    # already blocked is known. It refuses to start if the plan does not name
    # every sensor's topics and frame, and that refusal stops bring-up.
    actions += _detection(plan)

    # Skills come last. That is the order cross-cutting-lifecycle.md fixes —
    # controllers, then MoveIt, then skills — and it is a real dependency, not a
    # preference: MoveGroupInterface needs a current robot state, which does not
    # exist until a broadcaster is publishing. The line coordinator rides the
    # same gate: it calls those skills, so it may not start on a cell whose
    # planning scene never loaded.
    witness = _witness(plan, side)
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=last_step,
                on_exit=_gate(
                    _skills(plan) + (_line(plan) if line else []) + [witness],
                    "the skill servers",
                ),
            )
        )
    )

    # The last link in the chain, and the only place in this file that emits the
    # readiness token. Gated like every other link: a witness that could not
    # satisfy its condition exits non-zero, and bring-up stops with its diagnosis
    # rather than announcing a side that is not serving (ADR-0047, clause 3).
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=witness,
                on_exit=_gate(
                    [LogInfo(msg=ready_announcement(side, plan.zone))],
                    "the readiness announcement",
                    hint=_WITNESS_HINT,
                ),
            )
        )
    )
    return actions


#: Appended to the readiness gate's message. A witness that expires has already
#: said which endpoints never answered, on its own standard error; this points at
#: the difference between that and every other failure in the chain.
_WITNESS_HINT = (
    "Every step before this one succeeded, so the cell was started and did not "
    "finish coming up. The witness names the endpoints that never answered."
)


def _witness(plan: Plan, side: str) -> Node:
    """The process whose exit means this side is serving, not merely started.

    A blocking wait that exits, in the shape of every other link in this chain —
    `ros_gz_sim create`, the controller-manager spawners, the planning-scene
    loader. It is started with no environment of its own, which is the point: it
    inherits this launch's, so it runs on this side's `ROS_DOMAIN_ID` and can
    observe one side only, its own (ADR-0047, clause 3).

    `--side` reaches it for its diagnosis and for nothing else. It cannot select
    what the witness looks at, because both sides of a pair carry byte-identical
    names and the only thing that decides which graph is answered is the domain
    the process was started on.
    """
    return Node(
        package="cite_bringup",
        executable="readiness_witness.py",
        name="readiness_witness",
        arguments=["--zone", plan.zone, "--side", side],
        output="screen",
    )


def _seed(environ: dict) -> str | None:
    """Read the seed `gz sim` is started with, if the caller supplied one.

    Passing it does not make a scenario reproducible and must not be described as
    doing so: the physics solver is seeded by nothing, here or anywhere else.

    What the flag does and does not buy is stated once, in ADR-0027 § "What
    `CITE_PHYSICS_SEED` does and does not buy". Do not restate the argument here.
    It was restated in seven places and the copies drifted — this one still said
    planning determinism "arrives with a deterministic planner, not with this",
    in the future tense, after ADR-0027 had already landed one.

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


def _simulator(
    plan: Plan, *, headless: bool, seed: str | None, gz_env: dict[str, str]
) -> list:
    gz_args = ["-s", "-r", "-v", "2"] if headless else ["-r", "-v", "2"]
    if seed is not None:
        gz_args += ["--seed", seed]
    gz_args.append(str(plan.world))

    simulator = ExecuteProcess(
        cmd=["gz", "sim", *gz_args],
        additional_env=gz_env,
        output="screen",
        # An orphaned `gz sim` holds ports and names, and the *next* bring-up then
        # fails pointing nowhere useful. Tearing the whole launch down when the
        # simulator exits is what keeps that from happening.
        on_exit=Shutdown(reason="the simulator exited"),
        sigterm_timeout="10",
        sigkill_timeout="15",
    )

    return [simulator, _bridge(plan, gz_env)]


#: `/clock` from Gazebo into ROS. The one bridged name that is not in the plan,
#: because it is not a fact about the facility: every zone has exactly one clock
#: and it is called this in ROS 2 by convention.
CLOCK_BRIDGE = "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"

#: One bridged topic, in `parameter_bridge`'s own argument grammar.
#:
#:   `@` … `[`   Gazebo to ROS
#:   `@` … `]`   ROS to Gazebo
#:
#: The direction is half of the contract and is easy to lose: a belt command
#: bridged the wrong way produces a ROS publisher nothing reads and a Gazebo
#: subscriber nothing writes, with no error at either end.
GZ_TO_ROS = "{topic}@{ros_type}[{gz_type}"
ROS_TO_GZ = "{topic}@{ros_type}]{gz_type}"


def _bridge(plan: Plan, gz_env: dict[str, str]) -> Node:
    """Carry the simulation-fidelity aids across the Gazebo/ROS boundary.

    The belts and the beams are Gazebo system plugins. They publish and subscribe
    on the Gazebo transport, under the names the generated plan declares — and
    until this existed, `cite_bringup` bridged `/clock` and nothing else, so all
    nine of those names had no ROS endpoint at all. The bring-up plan advertised
    interfaces the running system did not provide, and the sensor-driven line
    could not be driven by its sensors.

    Every name comes from the plan. Nine hand-written entries would be nine
    places an asset name is written a second time, which CLAUDE.md §8 forbids and
    which this repository has already had to correct in four separate files.

    ## The one remapping, and why it is not optional

    A beam's level and a beam's events are two different interfaces. The plugin
    publishes a `gz.msgs.Boolean` level; L3 turns that into a typed
    `DetectionEvent`, and the process topology already gives `detection_topic` to
    a station as the `DetectionEvent` trigger it subscribes to. Bridging the raw
    boolean onto that same ROS name would put two publishers of two types on one
    topic and let them fight over it. So the bridge keeps the plugin's name on
    the Gazebo side — it has to, that is what the plugin advertises — and lands
    it in ROS under the plan's `level_topic`. `parameter_bridge` names both ends
    from one argument, so the ROS end is moved with a remapping, which rclcpp
    applies when the publisher is created.

    ## QoS

    `parameter_bridge` publishes RELIABLE/VOLATILE. Every consumer in this
    repository reads these on the SENSOR or COMMAND profile, and a best-effort
    reader matches a reliable writer while the reverse silently does not — see
    `cite_interfaces/qos.hpp` and `docs/interfaces/qos-profiles.md`.
    """
    arguments, remappings = _bridge_topics(plan)
    return Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="gz_bridge",
        arguments=list(arguments),
        remappings=list(remappings),
        # The bridge is a gz-transport participant like the server is: without
        # the partition it subscribes to a different transport namespace and
        # carries nothing, with no error at either end.
        additional_env=gz_env,
        output="screen",
    )


def _bridge_topics(plan: Plan) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """List what the bridge carries, and where each name lands in ROS.

    Split out of the `Node` so that it can be read back. `launch_ros` normalises
    a node's parameters and hides its arguments behind a private attribute, so a
    test that reached into the action would be testing launch's internals rather
    than this file's decisions — and these decisions are exactly the ones a
    silent failure hides: a direction reversed, a name misspelled, a level landed
    on the topic the line acts on.
    """
    arguments: list[str] = [CLOCK_BRIDGE]
    remappings: list[tuple[str, str]] = []

    for conveyor in plan.conveyors:
        arguments.append(
            ROS_TO_GZ.format(
                topic=conveyor.command_topic,
                ros_type="std_msgs/msg/Float64",
                gz_type="gz.msgs.Double",
            )
        )
        arguments.append(
            GZ_TO_ROS.format(
                topic=conveyor.state_topic,
                ros_type="std_msgs/msg/Float64",
                gz_type="gz.msgs.Double",
            )
        )

    for sensor in plan.sensors:
        arguments.append(
            GZ_TO_ROS.format(
                topic=sensor.detection_topic,
                ros_type="std_msgs/msg/Bool",
                gz_type="gz.msgs.Boolean",
            )
        )
        remappings.append((sensor.detection_topic, sensor.level_topic))

    return tuple(arguments), tuple(remappings)


def _scene(plan: Plan, gz_env: dict[str, str]) -> list:
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
        # `create` calls the world's spawn SERVICE over gz-transport, so it needs
        # the same partition the server was started in or the service is simply
        # not there to call.
        additional_env=gz_env,
        output="screen",
        # `create` exiting non-zero means the scene is not in the world. Every
        # controller spawner after it would then wait out its full deadline on a
        # controller manager that gz_ros2_control never created, and report a
        # service timeout — which names the spawner rather than the spawn.
        on_exit=_fatal_on_exit(f"spawning the {plan.zone} scene"),
    )

    return [publisher, spawn]


def _arms(plan: Plan, gz_env: dict[str, str]) -> list:
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
                additional_env=gz_env,
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
                    _planning_limits(manager.moveit),
                    _skill_parameters(plan, manager),
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


def _detection(plan: Plan) -> list:
    """Start the zone's one L3 detection server, turning levels into typed events.

    One per zone, in a zone-scope namespace of its own, because a break beam
    watches a belt and not a robot: three servers, one per arm, would give the
    question "did the piece pass beam 2" three answers.

    Nothing here composes a name. The server is given, per sensor, the ROS topic
    the bridge lands the raw level on, the topic its typed `DetectionEvent`s go
    to — which is the name the process topology already gives a station as its
    trigger — and the frame the generated static TF table publishes the beam at.
    It refuses to start if any of the three is missing, rather than watching a
    topic nothing writes to and reporting an empty belt forever.
    """
    if plan.detection is None or not plan.sensors:
        return []

    return [
        Node(
            package="cite_skills",
            executable="detection_server",
            name="detection_server",
            namespace=plan.detection.namespace,
            parameters=[_detection_parameters(plan)],
            # It resolves a beam's frame against the facility's static tree,
            # which is published globally. Without these it would look inside its
            # own namespace and find nothing.
            remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
            output="screen",
            # A detection server that dies takes the line's only sight with it,
            # and nothing else notices: the stations simply stop being triggered
            # and wait for a work-piece that already arrived.
            on_exit=_fatal_on_exit("the detection server"),
            sigterm_timeout=TEARDOWN_SIGTERM_S,
            sigkill_timeout=TEARDOWN_SIGKILL_S,
        )
    ]


def _detection_parameters(plan: Plan) -> dict:
    """Every sensor's two topics and its frame, keyed as the server declares them.

    Split out of the `Node` for the same reason `_bridge_topics` is: what matters
    here is which name goes to which key, and getting that pair wrong produces a
    node that starts happily and watches a topic nobody writes to.
    """
    parameters: dict = {
        "zone": plan.zone,
        "sensors": [sensor.asset for sensor in plan.sensors],
        "use_sim_time": True,
    }
    for sensor in plan.sensors:
        # The RAW level in, the TYPED event out. Reversing these gives a server
        # that subscribes to its own output and publishes onto the bridge.
        parameters[f"sensor.{sensor.asset}.state_topic"] = sensor.level_topic
        parameters[f"sensor.{sensor.asset}.event_topic"] = sensor.detection_topic
        parameters[f"sensor.{sensor.asset}.frame_id"] = sensor.frame_id
    return parameters


def _line(plan: Plan) -> list:
    """Start the L4 coordinator that runs every station in the zone.

    Off unless asked for, and that is a real constraint rather than caution: a
    skill server admits one goal at a time per arm, so a running coordinator
    holds all three arms and any other client — a scenario, an operator, a
    diagnostic — has its goals refused by a server that is busy working.

    Every action name it calls comes from the plan, as parallel arrays lined up
    by asset. The shape is `line_orchestrator`'s: a mismatched length is refused
    at start-up with both lengths named, and every value is discoverable with
    `ros2 param get` before anything moves. What has changed is where the names
    come from — they used to be assembled by whoever launched the node, which put
    `/cite/<zone>/<asset>/pick` in a second place, outside the reach of `ids.py`
    and of every test that covers it.

    `Detect` is the exception, deliberately: there is one server for the zone, so
    every asset is given the same action name. That is not one name in two
    places; it is one name, read once, offered to each station that may ask.
    """
    parameters = _line_parameters(plan)
    if parameters is None:
        return []

    return [
        Node(
            package="cite_orchestration",
            executable="line_orchestrator",
            name="line_orchestrator",
            namespace="/cite/line",
            parameters=[parameters],
            remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
            output="screen",
            on_exit=_fatal_on_exit("the line coordinator"),
            sigterm_timeout=TEARDOWN_SIGTERM_S,
            sigkill_timeout=TEARDOWN_SIGKILL_S,
        )
    ]


def _line_parameters(plan: Plan) -> dict | None:
    """Build the coordinator's parameters, or None when the zone has nothing to run.

    None rather than a partial table: a zone with no arm that plans has no
    station an actor can serve, and a coordinator started against it would refuse
    at start-up with an empty `skill_assets` — which is a correct refusal
    reported at the wrong layer.
    """
    served = [m for m in plan.controller_managers if m.skills is not None]
    if not served or plan.detection is None:
        return None

    detect = plan.detection.detect_action
    return {
        "zone": plan.zone,
        "station_tree": str(resolve_uri(STATION_TREE_URI)),
        # Read off the message rather than written here. `LineState` carries the
        # name as a constant for exactly this reason: a topic written in a
        # publisher and again in every subscriber is a value in two places.
        "line_state_topic": LineState.TOPIC,
        "skill_assets": [m.asset for m in served],
        "move_to_actions": [m.skills.move_to for m in served],
        "pick_actions": [m.skills.pick for m in served],
        "place_actions": [m.skills.place for m in served],
        "transfer_actions": [m.skills.transfer for m in served],
        # One server for the zone, so every station is given the same action.
        # That is one name read once, not one name in three places.
        "detect_actions": [detect for _ in served],
        # The belts, in the same parallel-array shape and for the same reason
        # (ADR-0032). L4 owns the belt setpoint: it stops the belt a station picks
        # from when that station's beam fires, and runs it again when the station
        # completes its handoff. Which belt that is comes from the topology's
        # `via_asset_id`, so only the drive — where to send the setpoint, and what
        # the drive is installed to run at — has to arrive here.
        #
        # EVERY belt is passed, not only the indexed ones. Which of them index is
        # a property of the flow that the coordinator derives; deciding it here
        # would put that rule in a second place, and a belt that feeds a sink still
        # has to be started by somebody.
        #
        # `installed_speed_mps` is passed through from the plan rather than
        # recomputed, so the speed a belt runs at exists once, in
        # `model/assets/instances/conveyors.yaml` (P1).
        "conveyor_assets": [conveyor.asset for conveyor in plan.conveyors],
        "conveyor_command_topics": [conveyor.command_topic for conveyor in plan.conveyors],
        "conveyor_speeds_mps": [conveyor.installed_speed_mps for conveyor in plan.conveyors],
        "use_sim_time": True,
    }


def _skill_parameters(plan: Plan, manager) -> dict:
    """Everything one skill server is told about its arm, all of it from L0.

    The gripper half used to be four keys written out by hand, and one of those
    four — `gripper_max_width_m` — exists in neither the plan nor the server's
    declared parameters, so it was accepted and dropped. Meanwhile the default
    grasp width, the goal tolerance, the drive rate and all seven linkage
    dimensions never arrived at all, and the node ran on compiled defaults that
    happen to equal the L0 values. It worked, and it worked only for as long as
    the two copies agreed — which is what a P1 violation looks like from the
    outside right up until it does not.

    They arrive here as whatever the plan states, under the plan's own keys,
    which are the server's own keys. There is no list to keep in step.
    """
    assert manager.moveit is not None, "a skill server is started only for a planned arm"
    return {
        "asset_id": manager.asset,
        "zone": plan.zone,
        "planning_group": manager.moveit.group,
        "tip_link": manager.moveit.tip_link,
        "gripper_action": manager.gripper_action or "",
        "home_rad": list(manager.moveit.home_rad),
        # ADR-0027, and under the plan's own keys for the same reason the gripper
        # values are: the server declares these names, so a key here reaches it
        # verbatim and there is no list to keep in step.
        "default_pipeline": manager.moveit.default_pipeline,
        "default_planner_id": manager.moveit.default_planner_id,
        "fallback_pipeline": manager.moveit.fallback_pipeline,
        "fallback_planner_id": manager.moveit.fallback_planner_id,
        "cartesian_planner_ids": list(manager.moveit.cartesian_planner_ids),
        "use_sim_time": True,
        **manager.gripper,
        **manager.arm,
    }


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
            _planning_limits(moveit),
            # Loaded as dictionaries rather than passed as --params-file. A ROS
            # parameter FILE must be shaped `<node>: ros__parameters: ...`; these
            # generated files hold the content without that wrapper, because the
            # wrapper is a ROS plumbing convention and not a fact about the
            # facility. Passing them as files fails at rcl with "Sequences can
            # only be values and not keys in params", which points at the YAML
            # rather than at the missing wrapper.
            _yaml_parameters(moveit.planning_pipelines),
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


def _planning_limits(moveit) -> dict:
    """Load the joint and Cartesian limits into one MoveIt parameter namespace.

    Both files land under `robot_description_planning`, because that is where
    MoveIt looks for each: the joint half through its own limit loading, and the
    Cartesian half through Pilz's `cartesian_limits` parameter listener, whose
    prefix is that namespace and nothing else (ADR-0027). They are merged into a
    single dictionary rather than passed as two entries so that the file this
    node is configured from is one value, not two that a launch-time merge has to
    be trusted to combine.
    """
    document = yaml.safe_load(moveit.joint_limits.read_text()) or {}
    document.update(yaml.safe_load(moveit.cartesian_limits.read_text()) or {})
    return {"robot_description_planning": document}


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
