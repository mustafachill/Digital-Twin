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

**The one blind spot in that guarantee, recorded so that nobody re-derives it
from a failed run.** A process that cannot be `exec`'d at all produces NO event
this file can gate on. Upstream `launch/actions/execute_local.py` wraps
`async_execute_process` in `except Exception:` — it logs the error, runs its
cleanup, and returns **without emitting `ProcessExited`** — so for that one class
of failure neither `_gate` nor `_fatal_on_exit` ever fires. The launch does not
stop, does not report, and does not announce; it simply stands still with the
chain broken at that link.

It has happened once, and cost the first paired bring-up its join: a Python
program installed with `install(PROGRAMS ...)` but committed without its
executable bit reached `launch` as `PermissionError: [Errno 13]` under a symlink
install. Both sides came up completely and neither announced. **What caught it
was the pair supervisor's ceiling** — a side that never announced readiness and
never exited, which is the row ADR-0047 clause 4 wrote for exactly this shape.

Two things follow. A failure mode with no event is not detectable inside this
file, so the checks for it live outside it — see
`test_every_installed_program_is_executable_in_the_tree` in
`test/test_simulation_launch.py`, and read its docstring for where that check is
itself blind. And **a ceiling above the whole chain is the only backstop this
class has**: it is not redundancy with the gates, it is the one thing that
converts "stood still forever" into a diagnosis.
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
    refuse_a_physical_side,
    require_domain,
    require_hardware_opt_in,
)
from cite_bringup.readiness import ready_announcement
# The pieces every side's launch runs, written once in `cite_bringup.side_launch`
# (ADR-0070 item 6) and imported under the names this file has always used. The
# ones this file does not call are re-exported for its tests, which read them
# off this module.
from cite_bringup.side_launch import (  # noqa: F401 - see above
    BringUpFailed,
    controller_chain as _controllers,
    DRIVER_HINT as _DRIVER_HINT,
    facility_nodes as _facility,
    FailTheLaunch,
    fatal_on_exit as _fatal_on_exit,
    gate as _gate,
    lifecycle_driver as _lifecycle_driver,
    lifecycle_driver_arguments as _lifecycle_driver_arguments,
    move_groups as _motion_planning,
    planning_limits as _planning_limits,
    planning_scene_loaders as _planning_scene,
    skill_parameters as _skill_parameters,
    skill_servers as _skills,
    stop as _stop,
    TEARDOWN_SIGKILL_S,
    TEARDOWN_SIGTERM_S,
    witness_arguments as _witness_arguments,
    WITNESS_HINT as _WITNESS_HINT,
    witness_node as _witness,
    yaml_parameters as _yaml_parameters,
)
from launch import LaunchContext, LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
    Shutdown,
)
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


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
                # NO DEFAULT, DELIBERATELY. `DeclareLaunchArgument` with no
                # `default_value` is required, and `ros2 launch` refuses the
                # launch by name when it is missing. It defaulted to a literal
                # zone until ADR-0056, which was invisible rather than harmless
                # while the facility declared one zone: with two, an omitted zone
                # brings up a cell nobody asked for and every name in it resolves
                # perfectly. `./scripts/sim` is the shell door, and it defaults
                # only when the model declares one zone (ADR-0069 decision 5),
                # through `cite_bringup.zones`; this launch never guesses.
                description="Which zone of the facility model to bring up. Required.",
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
            OpaqueFunction(function=_bring_up),
        ]
    )


def _bring_up(context: LaunchContext) -> list:
    zone = LaunchConfiguration("zone").perform(context)
    headless = LaunchConfiguration("headless").perform(context).lower() in ("true", "1")
    side = LaunchConfiguration("side").perform(context)

    try:
        plan = load(default_plan_path(zone))
        # FIRST, and with no opt-in that answers it: this launch starts a
        # simulation, and a side whose hardware is physical started here would be
        # Gazebo answering under the arm's names (ADR-0070). The physical side
        # has a launch of its own (ADR-0070 item 6).
        refuse_a_physical_side(plan, side)
        # The safety gate, at the ROS boundary rather than only at the shell one.
        # Refusing to start is not a divergence between the sim and real paths
        # (P2) — what gets commanded is identical either way; it simply may not
        # begin by accident (cross-cutting-safety.md).
        #
        # WHAT IT DECIDES ON AND WHAT ARRIVES HERE ARE BOTH IN ITS OWN DOCSTRING,
        # AND ARE DELIBERATELY NOT RESTATED. This comment carried two claims that
        # were corrected where they were defined and left standing here: that the
        # gate keys on a plan NAMING a hardware backend, which ADR-0054 replaced
        # with the declared fact `commands_physical_hardware`, and that such a
        # plan reaches an arm "by every other route", which claims a reach no
        # single function has. Four copies of one argument is how they drifted
        # apart. Read the docstring of `require_hardware_opt_in` in
        # `cite_bringup/plan.py`, which is the function called immediately below,
        # and ADR-0054 with its Correction of 2026-09-10 for the two residuals
        # neither this call nor that function can see.
        #
        # ASKED OF THIS SIDE, because this launch starts this side and no other.
        # Since ADR-0070 the counterpart is physical and the plant simulated, and
        # asked of every side this gate refused every plant-only bring-up -
        # every scenario and CI - over a machine this launch never starts. A
        # physical side never reaches it here: `refuse_a_physical_side` above
        # refuses that side first. The launch that starts the physical side asks
        # this gate of it (ADR-0070 item 6).
        require_hardware_opt_in(plan, os.environ, sides=(side,))
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
        return _stop(f"BRING-UP FAILED: {exc}")

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
    actions += _arms(plan, side, gz_env)

    facility_actions, managed = _facility(plan)
    actions += facility_actions
    driver = _lifecycle_driver(managed)
    actions.append(driver)

    controller_actions, first_spawner, last_spawner = _controllers(plan, side)

    # Nothing downstream of `_facility` starts until every managed node has been
    # OBSERVED `active` (ADR-0058). Until this gate existed `_facility` was
    # spliced into the action list with nothing gated on it, so a facility node
    # that never activated did not stop bring-up: the chain ran on, and the first
    # consumer to notice was `move_group` ten seconds later reporting
    # `Tf has two or more unconnected trees` and `Unknown frame: cite_world`. The
    # launch then died blaming the model and the planning scene, which is a
    # diagnosis pointing nowhere near the cause.
    #
    # The three processes here are the ones that start on nothing; everything
    # else in the chain hangs off one of them by a `_gate` of its own, and those
    # handlers stay at the top level where they can be checked as a set.
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=driver,
                on_exit=_gate(
                    [first_spawner, *_motion_planning(plan)],
                    "the controllers and the planners",
                    hint=_DRIVER_HINT,
                ),
            )
        )
    )
    actions += controller_actions

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
    witness = _witness(plan, side)
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=last_step,
                on_exit=_gate(
                    _skills(plan, side=side)
                    + _grasp_hold_bridges(plan, side, gz_env)
                    + [witness],
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
    gz_args = (
        ["-s", "-r", "-v", "2"]
        if headless
        else ["-r", "-v", "2", "--gui-config", str(plan.gui_config)]
    )
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
    interfaces the running system did not provide.

    Every name comes from the plan. Nine hand-written entries would be nine
    places an asset name is written a second time, which CLAUDE.md §8 forbids and
    which this repository has already had to correct in four separate files.

    ## The one remapping, and why it is not optional

    The plugin publishes a `gz.msgs.Boolean` level under the name the plan calls
    `detection_topic`, and the plan states a separate ROS name for that level,
    `level_topic` (see `cite_bringup.plan.Sensor`). So the bridge keeps the
    plugin's name on the Gazebo side — it has to, that is what the plugin
    advertises — and lands it in ROS under the plan's `level_topic`.
    `parameter_bridge` names both ends from one argument, so the ROS end is moved
    with a remapping, which rclcpp applies when the publisher is created.

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
    on the wrong ROS name.
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


def _arms(plan: Plan, side: str, gz_env: dict[str, str]) -> list:
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

    ``side``'s own description, which names ``side``'s own controller
    configuration (ADR-0048 clause 2); `_controllers` spawns what that
    configuration defines.
    """
    actions: list = []
    for manager in plan.controller_managers:
        description = ParameterValue(
            Command(["xacro ", str(manager.description_on(side))]), value_type=str
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


def _grasp_hold_bridges(plan: Plan, side: str, gz_env: dict[str, str]) -> list:
    """One simulation-only bridge per arm, telling the world what that arm holds.

    THE ONLY SIMULATION-ONLY NODE THIS REPOSITORY STARTS, and its presence here
    and nowhere else is ADR-0065's third promotion clause. L3 publishes custody
    identically on both backends — a physical arm saying what it holds is wanted
    for its own sake — and this turns that fact into an attach or a detach on the
    grasp-hold plugin's own Gazebo-transport topics. There is no plugin on the
    hardware path and nothing that needs one, because a real gripper holds what
    it has clamped.

    In the arm's own namespace, so it subscribes to the `state` its skill server
    publishes without anyone assembling that name — the same arrangement
    `_skills` and `_planning_scene` already have. The two Gazebo topics come from
    the plan, which generated them from the same `ids.interface` calls the world
    generator used for the plugin's own declaration, so nothing here builds a
    name (P1, CLAUDE.md §8).

    Gated with the skill servers rather than before them, and that is safe rather
    than lucky: the state topic is LATCHED, so a bridge that starts after its
    server is told the value that is already current instead of waiting for the
    next change.

    An arm whose end effector declares no grasp gets no plugin in the world and
    no entry in the plan, so it gets no bridge here either — one condition, three
    consumers.
    """
    by_asset = {hold.asset: hold for hold in plan.grasp_holds}
    actions: list = []
    for manager in plan.controller_managers:
        hold = by_asset.get(manager.asset)
        if hold is None:
            continue
        actions.append(
            Node(
                package="cite_bringup",
                executable="grasp_hold_bridge.py",
                name="grasp_hold_bridge",
                namespace=manager.node.rsplit("/", 1)[0],
                parameters=[
                    {
                        "zone": plan.zone,
                        "side": side,
                        "attach_topic": hold.attach_topic,
                        "detach_topic": hold.detach_topic,
                        # It reads no clock — it acts on messages and waits for
                        # nothing — and is declared anyway, so that every node in
                        # this launch answers the question the same way.
                        "use_sim_time": True,
                    }
                ],
                # It speaks the Gazebo transport, so it carries this side's
                # partition like every other process in this launch that does
                # (ADR-0042). The node also sets it on its own transport options
                # from the same door; both, because a partition that reaches only
                # one of the two fails silently.
                additional_env=gz_env,
                output="screen",
                # A bridge that dies leaves the arm reporting grasps that the
                # simulation never hears about: the box stays on friction alone,
                # the cell looks like it is working, and the measurement it was
                # built for is wrong rather than absent.
                on_exit=_fatal_on_exit(f"the {manager.asset} grasp-hold bridge"),
                sigterm_timeout=TEARDOWN_SIGTERM_S,
                sigkill_timeout=TEARDOWN_SIGKILL_S,
            )
        )
    return actions
