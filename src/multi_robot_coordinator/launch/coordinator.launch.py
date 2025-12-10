#!/usr/bin/env python3
"""
Coordinator Launch File

Launches the multi-robot coordinator, sensor monitor, and box spawner.

Usage:
    ros2 launch multi_robot_coordinator coordinator.launch.py
    ros2 launch multi_robot_coordinator coordinator.launch.py auto_spawn:=true
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Package path
    pkg_path = get_package_share_directory('multi_robot_coordinator')
    
    # Config files
    coordinator_params = os.path.join(pkg_path, 'config', 'coordinator_params.yaml')
    
    # Launch arguments
    auto_spawn_arg = DeclareLaunchArgument(
        'auto_spawn',
        default_value='false',
        description='Enable automatic box spawning'
    )
    
    # Coordinator node
    coordinator_node = Node(
        package='multi_robot_coordinator',
        executable='coordinator_node',
        name='coordinator_node',
        output='screen',
        parameters=[coordinator_params],
    )
    
    # Sensor monitor node
    sensor_monitor_node = Node(
        package='multi_robot_coordinator',
        executable='sensor_monitor',
        name='sensor_monitor',
        output='screen',
        parameters=[coordinator_params],
    )
    
    # Box spawner node
    box_spawner_node = Node(
        package='multi_robot_coordinator',
        executable='box_spawner',
        name='box_spawner',
        output='screen',
        parameters=[
            coordinator_params,
            {'auto_spawn': LaunchConfiguration('auto_spawn')}
        ],
    )
    
    return LaunchDescription([
        auto_spawn_arg,
        coordinator_node,
        sensor_monitor_node,
        box_spawner_node,
    ])

