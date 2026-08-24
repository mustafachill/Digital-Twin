"""
Launch file to start Gazebo with the robot arm model.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # Package directories
    pkg_gazebo = get_package_share_directory('robot_arm_gazebo')
    pkg_description = get_package_share_directory('robot_arm_description')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    # File paths
    xacro_file = os.path.join(pkg_description, 'urdf', 'robot_arm.urdf.xacro')
    world_file = os.path.join(pkg_gazebo, 'worlds', 'empty_world.world')

    # Declare arguments
    paused_arg = DeclareLaunchArgument(
        'paused',
        default_value='false',
        description='Start Gazebo in paused state'
    )

    # Robot description from xacro
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' use_sim:=true']),
        value_type=str
    )

    # Gazebo server
    gazebo_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world_file}.items()
    )

    # Gazebo client (GUI)
    gazebo_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
        )
    )

    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True
        }]
    )

    # Spawn robot in Gazebo
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_robot_arm',
        arguments=['-topic', 'robot_description', '-entity', 'robot_arm'],
        output='screen'
    )

    # Spawn controllers with delay
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
        output='screen'
    )

    joint_trajectory_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_trajectory_controller'],
        output='screen'
    )

    # Delay spawners to give controller_manager time to load
    delayed_broadcaster = TimerAction(
        period=8.0,
        actions=[joint_state_broadcaster_spawner]
    )

    delayed_trajectory = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[joint_trajectory_controller_spawner]
        )
    )

    return LaunchDescription([
        paused_arg,
        gazebo_server,
        gazebo_client,
        robot_state_publisher,
        spawn_robot,
        delayed_broadcaster,
        delayed_trajectory,
    ])
