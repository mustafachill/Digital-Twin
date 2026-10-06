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

"""Bring a PHYSICAL side up, event by event (ADR-0070 item 6).

The physical counterpart of a paired zone: the vendor's `ros2_control` plugin
on the machine, `cite_hardware`'s deadman and adapters beside it, and above it
exactly what a simulated side runs - the facility nodes, the controllers,
MoveIt, the planning scene and the skill servers, built by the same functions
in `cite_bringup.side_launch` - with no Gazebo and the wall clock. It prints
the same readiness token a simulated side prints, so the pair supervisor joins
it the same way.

**Nothing here sleeps, and nothing sequences on a timer** (P4). Each step is
gated on the one before it exiting successfully, and lifecycle transitions are
requested and confirmed by `lifecycle_driver.py` (ADR-0058):

1. **Refusals, before anything is described.** This side must be physical;
   `CITE_ALLOW_HARDWARE=1` must be set (ADR-0054); the process must be on this
   side's domain (ADR-0044); every environment argument the description reads
   must be set and of its declared kind. The robot's address is never logged:
   the description is expanded in this process, so it is on no command line.
2. **The deadman, first** - configured and activated, confirmed - before the
   vendor's hardware component exists, so the arm is held at the vendor's STOP
   state from the moment the plugin connects.
3. **The controller manager** with the vendor plugin, the description
   publisher, the facility nodes and the two adapters; then the adapters and
   facility nodes configured and activated, confirmed.
4. **The hold gate** (`hold_gate.py`): the deadman says AWAITING, every vendor
   service the side's nodes call is advertised, and a STOP sent to the vendor
   is acknowledged. The deadman itself offers no observable for its own first
   acknowledged STOP, so this is the gate's own (safety re-audit L-4).
5. **The controllers**, stage by stage, and **MoveIt**; then the planning
   scene; then the skill servers and the readiness witness, which on this side
   also waits for the two actions the deadman cancels; then the token.

**The token does not mean the arm is enabled.** While the deadman holds the arm
at STOP the vendor plugin deactivates every controller, `joint_state_broadcaster`
included, and it reactivates them itself once the arm is enabled - which the
deadman does only on the twin boundary's first heartbeat. So: side ready (held)
-> the supervisor starts the boundary -> heartbeat -> deadman HEALTHY -> the
deadman enables the arm -> the vendor reactivates its controllers. The program
waits for that last state through the boundary before it commands anything.

**A physical side goes down whole** (safety re-audit L-1 to L-3): the deadman,
the controller manager, a relay, a facility node, move_group or a skill server
exiting for ANY reason stops the launch, and nothing on this side respawns.
Every node here runs on the wall clock (`use_sim_time: false`, L-7), and this
launch declares no argument that could change that.
"""

from __future__ import annotations

import os

from cite_bringup.plan import (
    default_plan_path,
    load,
    Plan,
    PlanError,
    require_domain,
    require_hardware_opt_in,
    resolve_description_args,
    resolve_uri,
)
from cite_bringup.readiness import ready_announcement
from cite_bringup.side_launch import (
    controller_chain,
    DRIVER_HINT,
    facility_nodes,
    gate,
    lifecycle_driver,
    managed_node,
    move_groups,
    planning_scene_loaders,
    side_down_on_exit,
    skill_servers,
    stop,
    TEARDOWN_SIGKILL_S,
    TEARDOWN_SIGTERM_S,
    WITNESS_HINT,
    witness_node,
)
from launch import LaunchContext, LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node

#: Every node on a physical side runs on the wall clock (L-7). One statement,
#: handed to every node this file and the shared functions build.
USE_SIM_TIME = False

#: The `cite_hardware` executable for each node the plan names, by the plan key
#: that names it. Which nodes a side runs is the plan's; what program each is,
#: is this launch's mechanism.
_EXECUTABLES = {
    "deadman": "deadman.py",
    "track_adapter": "track_adapter.py",
    "gripper_relay": "gripper_relay.py",
}

_HOLD_HINT = (
    "The arm was never confirmed held: the hold gate names whether the deadman, a "
    "vendor service or the vendor's answer to a STOP is what never arrived. Nothing "
    "that could move the arm was started."
)


class SimulatedSideError(PlanError):
    """`hardware.launch.py` was asked to start a side that is not physical."""


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "zone",
                # No default, for the reason `simulation.launch.py` gives.
                description="Which zone of the facility model to bring up. Required.",
            ),
            DeclareLaunchArgument(
                "side",
                # No default either: a physical side is started by naming it.
                description=(
                    "Which side of the zone this launch is: a side whose hardware the "
                    "plan declares physical. Required."
                ),
            ),
            OpaqueFunction(function=_bring_up),
        ]
    )


def physical_managers(plan: Plan, side: str) -> list:
    """Return the controller managers ``side`` runs, refusing a side that is not physical.

    Every asset on the side must be physical and wired as one (`physical_on`):
    a side mixing simulated and physical assets has no launch, and this one
    refuses it rather than starting half of it.
    """
    managers = list(plan.controller_managers)
    simulated = sorted(
        m.asset for m in managers if m.commands_physical_hardware_on(side) is not True
    )
    if simulated:
        raise SimulatedSideError(
            f"zone {plan.zone!r}: on the {side} side, {', '.join(simulated)} commands no "
            "physical hardware. hardware.launch.py starts a physical side and nothing else; "
            "a simulated side is started by simulation.launch.py."
        )
    unwired = sorted(m.asset for m in managers if m.physical_on(side) is None)
    if unwired:
        raise PlanError(
            f"zone {plan.zone!r}: on the {side} side, {', '.join(unwired)} is physical and "
            "the plan names no deadman or adapters for it (`counterpart_physical`). It is "
            "generated from L0 - run ./scripts/validate-model --write, then ./scripts/build."
        )
    return managers


def expand_description(path, arguments: dict[str, str]) -> str:
    """Expand a description with xacro IN THIS PROCESS, with ``arguments`` as mappings.

    In-process rather than through a `Command` substitution, so the robot's
    address is on no command line and in no launch log. A failure names the
    file and never the arguments.
    """
    import xacro

    try:
        return xacro.process_file(str(path), mappings=dict(arguments)).toxml()
    except Exception as error:  # noqa: BLE001 - xacro raises several types
        raise PlanError(
            f"xacro could not expand {path} ({type(error).__name__}). Its arguments are "
            "not printed, because one of them is the robot's address."
        ) from None


def _bring_up(context: LaunchContext) -> list:
    zone = LaunchConfiguration("zone").perform(context)
    side = LaunchConfiguration("side").perform(context)
    try:
        plan = load(default_plan_path(zone))
        managers = physical_managers(plan, side)
        # The door (ADR-0054): this launch starts a physical side, so it asks.
        require_hardware_opt_in(plan, os.environ, sides=(side,))
        require_domain(plan, side, os.environ)
        descriptions = {
            manager.asset: expand_description(
                manager.description_on(side),
                resolve_description_args(manager, side, os.environ),
            )
            for manager in managers
        }
    except PlanError as exc:
        return stop(f"BRING-UP FAILED: {exc}")
    return physical_side(plan, side, descriptions)


def _split(name: str) -> tuple[str, str]:
    """`/a/b/node` -> (`/a/b`, `node`): the plan states names whole."""
    namespace, _, node = name.rpartition("/")
    return namespace, node


def _hardware_node(key: str, name: str, parameters) -> LifecycleNode:
    """One `cite_hardware` node, under the plan's name, with the generated file."""
    namespace, node = _split(name)
    return LifecycleNode(
        package="cite_hardware",
        executable=_EXECUTABLES[key],
        name=node,
        namespace=namespace,
        parameters=[str(parameters)],
        output="screen",
        on_exit=side_down_on_exit(f"the {key} {name}"),
        sigterm_timeout=TEARDOWN_SIGTERM_S,
        sigkill_timeout=TEARDOWN_SIGKILL_S,
    )


def hold_gate(plan: Plan, side: str) -> Node:
    """Build the process whose exit means the arm is confirmed held at the vendor's STOP."""
    return Node(
        package="cite_bringup",
        executable="hold_gate.py",
        name="hold_gate",
        arguments=["--zone", plan.zone, "--side", side],
        output="screen",
    )


def physical_side(plan: Plan, side: str, descriptions: dict[str, str]) -> list:
    """Describe the whole physical side, gated step by step (see the module docstring).

    Split from `_bring_up` so that a test can build it with a description
    string of its own and read the structure back, without an environment.
    """
    actions: list = [
        LogInfo(
            msg=f"Bringing up zone {plan.zone} side {side}: "
            f"{len(plan.controller_managers)} physical arm(s), no simulator"
        )
    ]

    # 2. The deadman(s), and a driver for them alone.
    deadmen = []
    for manager in plan.controller_managers:
        physical = manager.physical_on(side)
        node = _hardware_node("deadman", physical.deadman, physical.parameters)
        actions += managed_node(node, physical.deadman)
        deadmen.append(physical.deadman)
    first_driver = lifecycle_driver(deadmen)
    actions.append(first_driver)

    # 3. The hardware, the facility nodes and the adapters, once every deadman
    # is confirmed active.
    hardware: list = []
    adapters: list[str] = []
    for manager in plan.controller_managers:
        physical = manager.physical_on(side)
        namespace = manager.node.rsplit("/", 1)[0]
        hardware.append(
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="description_publisher",
                namespace=namespace,
                parameters=[
                    {
                        "robot_description": descriptions[manager.asset],
                        "use_sim_time": USE_SIM_TIME,
                    }
                ],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
                on_exit=side_down_on_exit(f"the {manager.asset} description publisher"),
            )
        )
        hardware.append(controller_manager(manager, side))
        for key in ("track_adapter", "gripper_relay"):
            name = getattr(physical, key)
            if name is None:
                continue
            node = _hardware_node(key, name, physical.parameters)
            hardware += managed_node(node, name)
            adapters.append(name)
    facility_actions, facility = facility_nodes(
        plan, use_sim_time=USE_SIM_TIME, on_exit=side_down_on_exit
    )
    hardware += facility_actions
    second_driver = lifecycle_driver([*facility, *adapters])
    hardware.append(second_driver)
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=first_driver,
                on_exit=gate(hardware, "the hardware", hint=DRIVER_HINT),
            )
        )
    )

    # 4. The hold gate, once the facility nodes and adapters are confirmed active.
    held = hold_gate(plan, side)
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=second_driver,
                on_exit=gate([held], "the hold gate", hint=DRIVER_HINT),
            )
        )
    )

    # 5. Controllers and planners once the arm is confirmed held; then the
    # planning scene; then the skills and the witness; then the token.
    controller_actions, first_spawner, last_spawner = controller_chain(plan, side)
    planners = move_groups(
        plan, descriptions=descriptions, use_sim_time=USE_SIM_TIME, on_exit=side_down_on_exit
    )
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=held,
                on_exit=gate(
                    [first_spawner, *planners], "the controllers and the planners", hint=_HOLD_HINT
                ),
            )
        )
    )
    actions += controller_actions
    scene_actions, last_step = planning_scene_loaders(
        plan, last_spawner, use_sim_time=USE_SIM_TIME
    )
    actions += scene_actions
    witness = witness_node(plan, side)
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=last_step,
                on_exit=gate(
                    skill_servers(
                        plan,
                        side=side,
                        descriptions=descriptions,
                        use_sim_time=USE_SIM_TIME,
                        on_exit=side_down_on_exit,
                    )
                    + [witness],
                    "the skill servers",
                ),
            )
        )
    )
    actions.append(
        RegisterEventHandler(
            OnProcessExit(
                target_action=witness,
                on_exit=gate(
                    [LogInfo(msg=ready_announcement(side, plan.zone))],
                    "the readiness announcement",
                    hint=WITNESS_HINT,
                ),
            )
        )
    )
    return actions


def controller_manager(manager, side: str) -> Node:
    """Build the side's controller manager: the vendor plugin, in the plant's namespace.

    Under the plant's own node name - no `name=` remapping - so every
    controller, action and the vendor driver's parameters resolve as the plan
    states them. The configuration is the side's own (`parameters_on`), loaded
    as a parameter file so its `ufactory_driver` block reaches the vendor
    driver's node in this process. The description arrives on the topic the
    side's description publisher latches, never as a parameter, so the robot's
    address is in no parameter of this node.

    The vendor plugin's own clients of the controller manager use ABSOLUTE
    names (`/controller_manager/list_controllers`, `.../switch_controller`)
    from inside `write()`, where an unserved call blocks the control loop for
    seconds. Each is remapped here onto this manager's own service, as the plan
    states the pair (`controller_manager_remaps`, generated from L0's
    `vendor_driver`). A process-wide remap: the plugin's node lives in this
    process, and the manager's own `~/` services are not touched by it.
    """
    vendor = manager.vendor_on(side)
    remaps = [] if vendor is None else list(vendor.controller_manager_remaps.items())
    return Node(
        package="controller_manager",
        executable="ros2_control_node",
        namespace=manager.node.rsplit("/", 1)[0],
        parameters=[str(resolve_uri(manager.parameters_on(side))), {"use_sim_time": USE_SIM_TIME}],
        remappings=[("~/robot_description", manager.description_topic), *remaps],
        output="screen",
        on_exit=side_down_on_exit(f"the {manager.asset} controller manager"),
        sigterm_timeout=TEARDOWN_SIGTERM_S,
        sigkill_timeout=TEARDOWN_SIGKILL_S,
    )
