#!/usr/bin/env python3
"""
Single Robot Test Launch
Tests spawning a single xArm 5 robot in the assembly line world.
Simplified version to debug issues.

Usage:
    ros2 launch assembly_line_bringup single_robot_test.launch.py
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    # Package paths
    assembly_bringup_pkg = get_package_share_directory('assembly_line_bringup')
    xarm_moveit_config_pkg = get_package_share_directory('xarm_moveit_config')
    gazebo_ros_pkg = get_package_share_directory('gazebo_ros')
    conveyor_pkg = get_package_share_directory('conveyor_system')
    sensor_pkg = get_package_share_directory('assembly_line_sensors')
    
    # World file
    world_file = os.path.join(assembly_bringup_pkg, 'worlds', 'assembly_line.world')
    
    # Model paths
    model_paths = [
        os.path.join(conveyor_pkg, 'models'),
        os.path.join(sensor_pkg, 'models'),
    ]
    
    # Set GAZEBO_MODEL_PATH
    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=':'.join(model_paths) + ':' + os.environ.get('GAZEBO_MODEL_PATH', '')
    )
    
    # Use xarm_moveit_config's gazebo launch - this properly handles all the complexity
    xarm5_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xarm_moveit_config_pkg, 'launch', 'xarm5_moveit_gazebo.launch.py')
        ),
        launch_arguments={
            'add_gripper': 'true',
            'show_rviz': 'true',
        }.items(),
    )
    
    return LaunchDescription([
        gazebo_model_path,
        xarm5_gazebo,
    ])

