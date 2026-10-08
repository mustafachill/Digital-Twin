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

"""The pieces of a side's launch that every side runs, written once (ADR-0070 item 6).

A side is either simulated (`simulation.launch.py`) or physical
(`hardware.launch.py`), and both bring up the same things above the hardware:
the facility nodes and their lifecycle driver, the controller spawners, MoveIt,
the planning scene, the skill servers and the readiness witness. Those are
built here, once, so the two launches cannot drift into two versions of one
cell (P1); what differs between them is passed in - the clock
(`use_sim_time`), the robot description a side loads, and what a process exiting
does to the side.

**Every refusal and every gate is the launch's mechanism, and it is here too**:
`stop`, `gate` and `fatal_on_exit` are the one route to a non-zero exit, and
`side_down_on_exit` is the physical side's stricter rule.

Moved here from `simulation.launch.py` unchanged in behaviour; the simulated
launch imports each under the name it always had.
"""

from __future__ import annotations

from collections.abc import Mapping

from cite_bringup.plan import Plan, PLANT_SIDE
from launch import LaunchContext
from launch.actions import LogInfo, OpaqueFunction, RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.parameter_descriptions import ParameterValue
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


class BringUpFailed(RuntimeError):
    """Raised after a refusal has been logged and the shutdown requested.

    Its only job is the exit status: see `stop`.
    """


class FailTheLaunch(OpaqueFunction):
    """The last action of a refusal: raise `BringUpFailed`, and do nothing else.

    A class of its own rather than a bare `OpaqueFunction`, so that a test can
    tell the stop apart from a bring-up step: a transition event may stop the
    launch, and may never start anything (ADR-0058).
    """

    def __init__(self) -> None:
        super().__init__(function=self._fail)

    @staticmethod
    def _fail(context: LaunchContext) -> None:
        # Not while the launch is already stopping. An interrupt — Ctrl-C, or the
        # pair supervisor stopping a side — is not a refusal, and a handler that
        # fires during that teardown must leave the exit status as it was.
        if context.is_shutdown:
            return
        raise BringUpFailed("bring-up refused; the BRING-UP FAILED line above says why")


def stop(message: str) -> list:
    """Log ``message``, shut the launch down, and make it exit non-zero.

    `Shutdown` alone ends a launch with status 0 — `launch`'s `LaunchService`
    returns 1 only when an exception reaches its run loop — so every refusal in
    this file used to report success to whoever started it: `./scripts/sim
    --zone <undeclared>` printed `BRING-UP FAILED` and exited 0. The trailing
    `FailTheLaunch` raises once the message is logged and the shutdown
    requested, which is the one route `launch` offers to a non-zero status;
    launch then logs the exception's text a second time, which is why that text
    points back at the line above instead of repeating it. The `LogInfo` stays
    first, because it is what a person reads.
    """
    return [LogInfo(msg=message), Shutdown(reason=message), FailTheLaunch()]


#: Appended to the lifecycle gate's message. The driver has already named the
#: node and the step on its own standard error; this says what the exit code by
#: itself does not, which is that nothing after it was started and why that is
#: the right answer rather than a harsh one.
DRIVER_HINT = (
    "No managed node was confirmed active, so nothing that depends on the "
    "facility's frames or model version was started. The driver names "
    "the node and the step it never got an answer to."
)


#: Appended to the readiness gate's message. A witness that expires has already
#: said which endpoints never answered, on its own standard error; this points at
#: the difference between that and every other failure in the chain.
WITNESS_HINT = (
    "Every step before this one succeeded, so the cell was started and did not "
    "finish coming up. The witness names the endpoints that never answered."
)


def witness_node(plan: Plan, side: str) -> Node:
    """Build the process whose exit means this side is serving, not just started.

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
        arguments=witness_arguments(plan, side),
        output="screen",
    )


def lifecycle_driver(managed: list[str]) -> Node:
    """Build the process whose exit means every managed node is `active`.

    ADR-0058. A blocking wait that exits, in the shape of every other link in
    this chain — `ros_gz_sim create`, the controller-manager spawners, the
    planning-scene loader, the readiness witness. It asks each node to configure
    and to activate and confirms each with `get_state`, so no transition event is
    load-bearing any more and there is nothing left to lose.

    It is started alongside the nodes it drives rather than after them, because
    what it waits on first is their `change_state` service appearing — which is a
    condition, not an estimate. Its exit is what the rest of bring-up is gated
    on: `facility_nodes` was spliced into the action list with nothing downstream of
    it, which is why a node that stalled cost ten seconds and a diagnosis
    pointing at the model instead of one second and the node's name.
    """
    return Node(
        package="cite_bringup",
        executable="lifecycle_driver.py",
        name="lifecycle_driver",
        arguments=lifecycle_driver_arguments(managed),
        output="screen",
    )


def lifecycle_driver_arguments(managed: list[str]) -> list[str]:
    """Build the driver's argument vector, so that a test can read it back.

    Same reason as `witness_arguments`: `launch_ros` keeps a node's arguments
    behind a private attribute, so a test reaching into the action would be
    testing launch's internals rather than this file's decisions.
    """
    arguments: list[str] = []
    for name in managed:
        arguments += ["--node", name]
    return arguments


def witness_arguments(plan: Plan, side: str) -> list[str]:
    """Build the witness's argument vector, so that a test can read it back.

    `launch_ros` keeps a node's arguments behind a private attribute, so a test
    reaching into the action would be testing launch's internals rather than
    this file's decisions - the same reason `_bridge_topics` exists separately.
    """
    return ["--zone", plan.zone, "--side", side]


def controller_chain(plan: Plan, side: str) -> tuple[list, Node, Node]:
    """Spawn each manager's controllers, stage by stage, gated on the previous.

    Every step starts only when the one before it exits successfully. A non-zero
    exit anywhere stops the launch with a message naming the step, rather than
    leaving a half-built system running. Including the last stage: what follows
    the final spawner is gated by the caller with the same `gate`, because an
    ungated last link is how a chain that reports every intermediate failure
    still lets the one that matters through.

    Returns the chain's handlers and both of its ends. The **first** spawner is
    returned rather than included, because it is the one action here that starts
    on nothing, and the caller gates it on the lifecycle driver — otherwise a
    controller manager would be spawned into a cell whose facility nodes had
    never activated. The **last** is what the caller chains the planning scene
    onto.

    ``side``'s controllers: what the configuration that side loads defines, and
    no controller it does not (`ControllerManager.stages_on`, ADR-0070 item 1).
    """
    actions: list = []
    first: Node | None = None
    previous: object | None = None

    # One chain across every manager and stage, rather than one chain per arm.
    # Spawning three arms concurrently means three controller managers performing
    # a state switch simultaneously while physics runs, and the contention made
    # bring-up intermittent — a scenario that passed and then failed on the very
    # next run. A single chain is still entirely event-gated: each step starts
    # when the previous one exits, so bring-up remains as fast as the machine
    # allows. It is simply no longer racing itself.
    for manager in plan.controller_managers:
        for stage, names in manager.stages_on(side):
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
                # It is handed back to the caller instead of started here, so
                # that the whole chain hangs off the lifecycle driver's exit.
                first = spawner
            else:
                actions.append(
                    RegisterEventHandler(
                        OnProcessExit(
                            target_action=previous,
                            on_exit=gate(
                                [spawner],
                                f"{manager.asset} stage {stage}",
                                hint=SPAWNER_HINT,
                            ),
                        )
                    )
                )
            previous = spawner

    assert first is not None and previous is not None, (
        "the plan declared no controllers to spawn"
    )
    return actions, first, previous


def planning_scene_loaders(
    plan: Plan, previous: Node, *, use_sim_time: bool = True
) -> tuple[list, Node]:
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
            parameters=[{"zone": plan.zone, "use_sim_time": use_sim_time}],
            output="screen",
        )
        actions.append(
            RegisterEventHandler(
                OnProcessExit(
                    target_action=last,
                    on_exit=gate(
                        [loader],
                        f"the planning scene for {manager.asset}",
                        hint=SPAWNER_HINT,
                    ),
                )
            )
        )
        last = loader
    return actions, last


def managed_node(node: LifecycleNode, name: str) -> list:
    """Start a managed node, with the diagnosis for each way it can refuse.

    **It no longer drives the node.** `lifecycle_driver.py` does, by calling
    `change_state` and confirming with `get_state`, and this file gates the rest
    of bring-up on that program's exit (ADR-0058).

    What used to be here was an `EmitEvent(ChangeState(CONFIGURE))` and an
    `OnStateTransition(configuring -> inactive)` that emitted the activation.
    `launch_ros` derives that event from a **subscription** to
    `/<node>/transition_event`, and both endpoints are RELIABLE + VOLATILE —
    reliable is a promise to *matched* subscribers, so a node whose
    `on_configure` returned before the launch's subscription had matched
    published into nobody and the sample was never re-sent. The node then sat in
    `inactive` forever, published no TF, and bring-up died ten seconds later in
    `move_group` reporting unconnected TF trees and an unknown frame — a
    diagnosis pointing at the model, which was the expensive part. Observed in
    3 of 11 scenario launches; `docs/open-work.md` #72 has the proof.

    The comment this function used to end on said the handlers being registered
    before the transition was emitted meant "a node that configures very quickly
    cannot reach `inactive` before anything is watching". Registration order in a
    launch description says nothing about when a DDS subscription matches, and
    that sentence is the assumption the defect lived inside.

    **The four refusals stay, and nothing relies on them.** They ride the same
    volatile topic, so a transition that *fails* is exactly as droppable as one
    that succeeded; what makes a failure reach a person either way is the driver
    observing `unconfigured` rather than `inactive` and naming it. These are the
    better-worded answer on the occasions they do arrive, which is why the ones
    that match a failed activation must still not try to activate again.

    **So one failed transition can produce two shutdown messages**, and a reader
    who sees only one has not necessarily seen the whole of it: on the occasions
    the event does arrive, a refusal here and the driver's own non-zero exit both
    ask the launch to stop. **Both messages appear** — each emitter pairs a
    `LogInfo` with its `Shutdown` — and it is the recorded shutdown *reason* that
    is whichever landed first. **The driver's is the authoritative one.** It is the observation —
    what the node answered `get_state` with — where a refusal is a broadcast that
    may or may not have been delivered, and it names the step as well as the node.
    """
    return [
        refuses(node, name, "configuring", "unconfigured", "on_configure returned FAILURE"),
        refuses(node, name, "configuring", "errorprocessing", "on_configure raised"),
        refuses(node, name, "activating", "inactive", "on_activate returned FAILURE"),
        refuses(node, name, "activating", "errorprocessing", "on_activate raised"),
        node,
    ]


def refuses(
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
            entities=stop(message),
        )
    )


#: The namespace every facility node is started in. One statement, because the
#: fully-qualified names below are composed from it and the driver is handed
#: those — a second spelling of it would be a second place a name is made (§8).
FACILITY_NAMESPACE = "/cite/facility"


def facility_nodes(
    plan: Plan, *, use_sim_time: bool = True, on_exit=None
) -> tuple[list, list[str]]:
    """Runtime access to the generated artifacts: frames and model version.

    These are managed nodes with no dependency on the simulator, so they come up
    alongside it rather than after it. The frame server matters most: without it
    an arm's own model is a disconnected TF tree, and a skill given a pose in
    cite_world can never resolve it into the arm's planning frame.

    Returns the actions and **the fully-qualified name of every node it started**,
    which is what `lifecycle_driver` is given. ADR-0058 expected the driver to
    carry its own list and recorded that as a thing to revisit whenever a node is
    added here; passing the names instead removes the revisit rather than
    scheduling it, and removes the third copy of them that §4 prohibits. Add a
    node below and it is driven, with nothing else to remember.
    """
    zone = {"zone": plan.zone}
    # One row per node, and the name in each row is written once: it becomes the
    # node's ROS name, the subject of that node's four refusal messages, and the
    # fully-qualified name the driver is given. `launch_ros` keeps a node's
    # resolved name behind a property that refuses to be read before the action
    # has executed, which is exactly when this description is built, so the name
    # is carried here rather than asked of the action.
    declared: tuple[tuple[str, str, list, list], ...] = (
        (
            "frame_server",
            "frame_server.py",
            [zone],
            # Without this the publisher would write inside the namespace and
            # nothing listening on /tf_static would ever see the facility tree.
            [("/tf_static", "/tf_static")],
        ),
        ("model_info", "model_info.py", [{"zones": [plan.zone]}], []),
    )

    actions: list = []
    managed: list[str] = []
    for name, executable, parameters, remappings in declared:
        node = LifecycleNode(
            package="cite_facility",
            executable=executable,
            name=name,
            namespace=FACILITY_NAMESPACE,
            parameters=[*parameters, {"use_sim_time": use_sim_time}],
            remappings=remappings,
            output="screen",
            # A physical side passes `side_down_on_exit`, so a facility node
            # that goes away takes the side with it; the simulated side keeps
            # the behaviour it has always had.
            **({} if on_exit is None else {"on_exit": on_exit(name)}),
        )
        actions += managed_node(node, name)
        managed.append(f"{FACILITY_NAMESPACE}/{name}")
    return actions, managed


def skill_servers(
    plan: Plan,
    *,
    side: str = PLANT_SIDE,
    descriptions: Mapping[str, object] | None = None,
    use_sim_time: bool = True,
    on_exit=None,
) -> list:
    """One skill server per arm, in that arm's namespace.

    Every name it uses arrives as a generated parameter — the planning group, the
    tip link, the controller actions, the home configuration. The server builds
    none of them, which is what keeps the number of places a name is made at one
    (P2). It refuses to start if any is missing, rather than guessing and
    advertising skills that command nothing.

    ``descriptions`` is each arm's robot description by asset, as the side
    loads it; by default the plant's, expanded by xacro at launch (see
    `description_of`). ``on_exit`` builds the exit handler from a label; by
    default `fatal_on_exit`, and a physical side passes `side_down_on_exit`.
    ``side`` is the side this launch starts, which `skill_parameters` asks the
    plan about.
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
        robot_description = description_of(manager, descriptions)
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
                    yaml_parameters(
                        manager.moveit.kinematics, prefix="robot_description_kinematics"
                    ),
                    planning_limits(manager.moveit),
                    skill_parameters(plan, manager, side=side, use_sim_time=use_sim_time),
                ],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="screen",
                # A skill server that dies takes its arm's skills with it and
                # nothing else notices: the action server simply stops existing,
                # and the next goal waits out its client's deadline.
                on_exit=(on_exit or fatal_on_exit)(f"the {manager.asset} skill server"),
                sigterm_timeout=TEARDOWN_SIGTERM_S,
                sigkill_timeout=TEARDOWN_SIGKILL_S,
            )
        )
    return actions


def skill_parameters(
    plan: Plan, manager, *, side: str = PLANT_SIDE, use_sim_time: bool = True
) -> dict:
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
        "use_sim_time": use_sim_time,
        # Whether an empty close that expected a part, or an arm at its
        # trajectory's last point whose controller did not report the goal met,
        # fails the step. Not where this side's arm is physical, by owner
        # decisions 2026-10-06 (ADR-0070 amendment): there both are executed, not
        # judged, as the real robot's own program does it. Asked of the plan,
        # never of an asset name.
        "side_judges_outcome": not manager.commands_physical_hardware_on(side),
        **manager.gripper,
        **manager.arm,
        # How wide the parts this facility handles are (ADR-0052 option F). It
        # arrives from the plan's own `plan:` block rather than from the
        # manager's, because it is one statement per ZONE and not one per arm —
        # every key in `manager.gripper` describes an end effector, and a part
        # width is not a property of one.
        #
        # Absent rather than zero where the plan states none, for the reason
        # `_named_numbers` omits an absent gripper key: a zero manufactured here
        # would be passed as a parameter and would override the skill server's
        # own declared sentinel with a number the model never stated — silently,
        # and in the direction of a window opening onto a closed gripper. The
        # server refuses to configure on the sentinel instead.
        **workpiece_parameters(plan),
        **pose_parameters(manager.moveit.poses_rad),
    }


def pose_parameters(poses) -> dict:
    """Return the arm's named joint poses as the skill server's two flat parameters.

    Absent rather than empty where L0 declares none: an empty list carries no
    element type, and a parameter file cannot state one, so the server's own
    empty defaults are what an arm with no poses gets (ADR-0066).
    """
    if not poses:
        return {}
    return {
        "pose_names": list(poses),
        "pose_values_rad": [value for values in poses.values() for value in values],
    }


def workpiece_parameters(plan: Plan) -> dict:
    """Return the work-piece interval, under the names the skill server declares.

    Empty where the zone declares no part width. That is a real state and not a
    fault here — a facility that grasps nothing has no predicate to configure —
    and where it IS a fault it is caught at L0 by
    `workpiece-width-unstated-for-a-grasping-facility` before a plan exists.
    """
    if plan.workpieces is None:
        return {}
    return {
        "workpiece_narrowest_width_m": plan.workpieces.narrowest_width_m,
        "workpiece_widest_width_m": plan.workpieces.widest_width_m,
    }


def move_groups(
    plan: Plan,
    *,
    descriptions: Mapping[str, object] | None = None,
    use_sim_time: bool = True,
    on_exit=None,
) -> list:
    """One move_group per arm, in that arm's namespace.

    Per arm rather than per cell, because each arm is its own model with its own
    description and its own controller manager. Nothing above L3 talks to MoveIt
    (ADR-0006); the skill servers are its only client.

    move_group is not gated on the controllers: it waits for /joint_states on its
    own, and gating it on them would add an ordering constraint the system does
    not have.

    It IS gated on the lifecycle driver, and **that is not an ordering dependency
    either** (ADR-0058, amended 2026-09-17). `frame_server` publishes the
    facility's static tree through a `StaticTransformBroadcaster`, whose publisher
    is TRANSIENT_LOCAL depth 1 over a message that accumulates every transform
    sent — so a move_group that starts late still receives the whole tree, and
    `frame_server.on_deactivate`'s own comment says so: "what it published stays
    available to late joiners". The `Tf has two or more unconnected trees` and
    `Unknown frame: cite_world` errors were read off the **stall**, where the tree
    was never published at all. They are what a node that never activated looks
    like, not what starting early looks like.

    What the gate buys is two things, neither of which is a dependency:

    * **Log ordering.** Ungated, move_group starts at t≈0 and logs those two
      frame errors seconds before the driver says which node never answered — so
      the misdirection ADR-0058 exists to remove would still be the first thing
      in the log.
    * **One invariant instead of a rule with a hole in it.** "Nothing downstream
      of `facility_nodes` starts before the driver exits" is testable as written; a
      carve-out for move_group is a second rule nothing checks.

    **The cost is real and is stated here rather than discovered.** One
    `move_group` and one `xacro` expansion **per arm that carries MoveIt** now sit
    behind facility activation instead of running beside it — **ask the plan
    how many, rather than reading a number out of this comment** (ADR-0027's
    first correction: do not state the cardinality of a generated collection in
    prose). The added wall-clock cost is **estimated at
    the order of a second and has not been measured** — no instrument, host or
    trial count stands behind it, and it must not be quoted as though one did.
    Every scenario ceiling in
    this repository is wall clock and none of them may be widened to absorb it
    (CLAUDE.md §2, the real-time-factor bullet).

    This docstring said "started unconditionally" until the gate landed, and then
    said the gate was "a real dependency rather than caution" until 2026-09-17.
    The first was true of the code; the second was a mechanism asserted from an
    audit of the broken case, which is the ADR-0028 lesson this project keeps.
    """
    actions: list = []
    for manager in plan.controller_managers:
        moveit = manager.moveit
        if moveit is None:
            continue

        namespace = manager.node.rsplit("/", 1)[0]
        robot_description = description_of(manager, descriptions)
        semantic = ParameterValue(Command(["xacro ", str(moveit.srdf)]), value_type=str)

        parameters: list = [
            {
                "robot_description": robot_description,
                "robot_description_semantic": semantic,
                "use_sim_time": use_sim_time,
                "publish_robot_description_semantic": True,
            },
            yaml_parameters(moveit.kinematics, prefix="robot_description_kinematics"),
            planning_limits(moveit),
            # Loaded as dictionaries rather than passed as --params-file. A ROS
            # parameter FILE must be shaped `<node>: ros__parameters: ...`; these
            # generated files hold the content without that wrapper, because the
            # wrapper is a ROS plumbing convention and not a fact about the
            # facility. Passing them as files fails at rcl with "Sequences can
            # only be values and not keys in params", which points at the YAML
            # rather than at the missing wrapper.
            yaml_parameters(moveit.planning_pipelines),
            yaml_parameters(moveit.controllers),
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
                on_exit=(on_exit or fatal_on_exit)(f"move_group for {manager.asset}"),
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


def planning_limits(moveit) -> dict:
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


def yaml_parameters(path, *, prefix: str | None = None) -> dict:
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
SPAWNER_HINT = (
    "A timeout at this step usually means the node it waits on never appeared, or "
    "that a controller's joint names do not match the description — run "
    "./scripts/validate-model."
)


def gate(entities: list, what: str, *, hint: str = "") -> callable:
    """Continue to `entities` only if the step that just exited actually succeeded.

    Applied to every link in the chain. An ungated final link is the failure this
    exists to prevent: the intermediate stages reported their failures correctly
    while the last one let a non-zero exit through, and the skill servers started
    against a cell that had never finished coming up.
    """

    def handler(event, context):  # noqa: ANN001 - launch's callback shape
        # Silent while the launch is stopping, as `fatal_on_exit` is: an
        # interrupt mid-bring-up ends a step non-zero, and reporting it as
        # "BRING-UP FAILED before ..." — and exiting 1 — would blame the cell
        # for the operator's Ctrl-C.
        if context.is_shutdown:
            return None
        if event.returncode == 0:
            return entities
        message = (
            f"BRING-UP FAILED before {what}: the previous step exited "
            f"{event.returncode}. {hint}".rstrip()
        )
        return stop(message)

    return handler


def fatal_on_exit(what: str) -> callable:
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
        return stop(message)

    return handler


def side_down_on_exit(what: str) -> callable:
    """Stop the launch when a process exits FOR ANY REASON while it is not stopping.

    For a physical side (ADR-0070, the safety re-audit's L-1 and L-3): a
    deadman, a controller manager, a relay or a planner that goes away takes
    the whole side with it, never to be restarted automatically. Unlike
    `fatal_on_exit`, an exit status of 0 is no excuse: a deadman that returned
    cleanly watches nothing all the same.
    """

    def handler(event, context):  # noqa: ANN001 - launch's callback shape
        if context.is_shutdown:
            return None
        return stop(
            f"BRING-UP FAILED: {what} exited {event.returncode}. A physical side is "
            "stopped whole rather than left running without it, and nothing restarts it."
        )

    return handler


def description_of(manager, descriptions: Mapping[str, object] | None) -> object:
    """Return an arm's robot description: the one in ``descriptions``, else the plant's.

    The plant's is expanded by xacro when the launch runs, as it always was. A
    physical side hands in its own, expanded in the launch process with the
    resolved environment arguments, so the robot's address never appears on a
    command line (`expand_description`).
    """
    if descriptions is not None and manager.asset in descriptions:
        return descriptions[manager.asset]
    return ParameterValue(Command(["xacro ", str(manager.description)]), value_type=str)
