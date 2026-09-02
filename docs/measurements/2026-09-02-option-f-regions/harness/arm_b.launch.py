#!/usr/bin/env python3
"""Arm B's rig: a real controller manager over `JointStopSystem`, with a real skill server.

DERIVED FROM `workspace/src/cite_bringup/test/test_grasp_predicate_launch.py` at commit
`d3eeac4`, whose node set, parameter sources and ordering are reproduced here rather than
reinvented -- `criteria.md` section 5.2 names that file as the shape Arm B uses. What is
different is the STOPS, which the description carries, and which `measure_arm_b.py` builds
and writes to `description_file` before starting this launch.

WHY A LAUNCH FILE AND NOT A LIST OF `subprocess.Popen`s. The 2026-09-01 FP rig started its
two processes by hand because it needed neither `move_group` nor a skill server: its
verdict came out of `predicate_eval`. This campaign's verdict is `Grasp.Result.holding`,
read off the running node (`criteria.md` section 3), so the skill server is not optional
and it needs the parameters the PRODUCTION launch file builds -- including the band and
the work-piece interval, which are the four values option F is made of. Building them by
hand here would prove the predicate works on numbers the cell does not deliver.

NOT A GAZEBO RIG. There is no simulator, no physics and no work-piece. `use_sim_time` is
false throughout, as it is in the launch test, and for the reason stated there: the
generated controller configuration says true because the cell it configures runs under
Gazebo, and a manager waiting for a `/clock` that nobody publishes never runs a control
cycle. The predicate compares two widths and derives nothing from a clock.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from cite_bringup import plan as bringup_plan

ZONE = "cell_a"
ARM = "arm_1"

STARTUP_CEILING_S = 180.0

PLAN = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
MANAGER = next(entry for entry in PLAN.controller_managers if entry.asset == ARM)
NAMESPACE = MANAGER.node.rsplit("/", 1)[0]
CONTROLLER_CONFIG = bringup_plan.resolve_uri(MANAGER.parameters)


def _production_launch():
    """Load `simulation.launch.py` as a module, for its parameter builders.

    The rig gives `move_group` and the skill server the parameters the PRODUCTION launch
    file builds for them, rather than a second set assembled here.
    """
    path = Path(bringup_plan.__file__).resolve().parents[1] / "launch" / "simulation.launch.py"
    if not path.exists():
        # Installed layout: `cite_bringup`'s launch directory lives in the package share.
        from ament_index_python.packages import get_package_share_directory

        path = Path(get_package_share_directory("cite_bringup")) / "launch" / \
            "simulation.launch.py"
    spec = importlib.util.spec_from_file_location("cite_bringup_simulation_launch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SIM = _production_launch()


def _nodes(context, *args, **kwargs):  # noqa: ANN001, ARG001 - launch's callback shape
    description = Path(
        LaunchConfiguration("description_file").perform(context)).read_text()
    semantic = ParameterValue(
        Command(["xacro ", str(MANAGER.moveit.srdf)]), value_type=str)
    moveit = MANAGER.moveit

    # Ordered by the stage the generated plan declares, so the state broadcaster is
    # active before anything claims a command interface -- the same order production
    # spawns them in, read from the same place.
    controllers = [name for _, names in MANAGER.stages() for name in names]

    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="description_publisher",
            namespace=NAMESPACE,
            parameters=[{"robot_description": description, "use_sim_time": False}],
            remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
            output="log",
        ),
        Node(
            package="controller_manager",
            executable="ros2_control_node",
            name="controller_manager",
            namespace=NAMESPACE,
            parameters=[
                # THE GENERATED FILE, UNMODIFIED. The `stall_timeout`,
                # `stall_velocity_threshold` and `goal_tolerance` this rig's stall is
                # declared by are the cell's own.
                str(CONTROLLER_CONFIG),
                {"use_sim_time": False},
                {"robot_description": description},
            ],
            output="screen",
        ),
        Node(
            package="controller_manager",
            executable="spawner",
            name="spawn_controllers",
            arguments=[
                *controllers,
                "--controller-manager", MANAGER.node,
                "--controller-manager-timeout", str(STARTUP_CEILING_S),
            ],
            output="screen",
        ),
        Node(
            package="moveit_ros_move_group",
            executable="move_group",
            name="move_group",
            namespace=NAMESPACE,
            parameters=[
                {
                    "robot_description": description,
                    "robot_description_semantic": semantic,
                    "publish_robot_description_semantic": True,
                },
                SIM._yaml_parameters(
                    moveit.kinematics, prefix="robot_description_kinematics"),
                SIM._planning_limits(moveit),
                SIM._yaml_parameters(moveit.planning_pipelines),
                SIM._yaml_parameters(moveit.controllers),
                {
                    "publish_planning_scene": True,
                    "publish_state_updates": True,
                    "use_sim_time": False,
                },
            ],
            remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
            output="screen",
        ),
        Node(
            package="cite_skills",
            executable="skill_server",
            name="skill_server",
            namespace=NAMESPACE,
            parameters=[
                {
                    "robot_description": description,
                    "robot_description_semantic": semantic,
                },
                SIM._yaml_parameters(
                    moveit.kinematics, prefix="robot_description_kinematics"),
                SIM._planning_limits(moveit),
                # Every skill parameter the CELL gives this server, built by the
                # production launch file's own function -- including the band and the
                # work-piece interval, which are the four values option F is made of.
                SIM._skill_parameters(PLAN, MANAGER),
                {"use_sim_time": False},
            ],
            remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
            output="screen",
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            "description_file",
            description="the expanded rig description, written by measure_arm_b.py",
        ),
        OpaqueFunction(function=_nodes),
    ])
