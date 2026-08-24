#!/usr/bin/env python3
"""
Full Assembly Line Launch

Launches the complete multi-robot pick and place assembly line:
- Gazebo world with robots via fleet_manager
- 3 xArm 5 robots with grippers
- Robot interface nodes
- Handoff coordinator
- Coordinator node for box management

Usage:
    ros2 launch assembly_line_bringup assembly_line.launch.py
    ros2 launch assembly_line_bringup assembly_line.launch.py num_robots:=2
    ros2 launch assembly_line_bringup assembly_line.launch.py auto_spawn:=true
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    LogInfo,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Package paths
    assembly_bringup_pkg = get_package_share_directory('assembly_line_bringup')
    fleet_manager_pkg = get_package_share_directory('fleet_manager')
    coordinator_pkg = get_package_share_directory('multi_robot_coordinator')
    
    # Launch arguments
    num_robots_arg = DeclareLaunchArgument(
        'num_robots',
        default_value='3',
        description='Number of robots to spawn (1-3)'
    )
    
    auto_spawn_arg = DeclareLaunchArgument(
        'auto_spawn',
        default_value='false',
        description='Enable automatic box spawning'
    )
    
    launch_interfaces_arg = DeclareLaunchArgument(
        'launch_interfaces',
        default_value='true',
        description='Launch robot interface nodes'
    )
    
    # Use fleet_manager for multi-robot spawning (handles prefixed controllers correctly)
    multi_robot_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(fleet_manager_pkg, 'launch', 'multi_robot_test.launch.py')
        ),
        launch_arguments={
            'num_robots': LaunchConfiguration('num_robots'),
            'launch_gazebo': 'true',
            'launch_interfaces': LaunchConfiguration('launch_interfaces'),
        }.items(),
    )
    
    # Multi-robot coordinator launch (delayed to wait for robots)
    coordinator_launch = TimerAction(
        period=35.0,  # Wait for all robots to spawn and controllers to load
        actions=[
            LogInfo(msg='Starting Multi-Robot Coordinator...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(coordinator_pkg, 'launch', 'coordinator.launch.py')
                ),
                launch_arguments={
                    'auto_spawn': LaunchConfiguration('auto_spawn'),
                }.items(),
            )
        ]
    )
    
    return LaunchDescription([
        # Arguments
        num_robots_arg,
        auto_spawn_arg,
        launch_interfaces_arg,
        
        # Launch components
        LogInfo(msg='Starting Assembly Line System...'),
        multi_robot_launch,
        coordinator_launch,
    ])

