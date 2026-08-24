#!/usr/bin/env python3
"""
Sensor Test Launch
Tests break beam and proximity sensors in Gazebo.

Usage:
    ros2 launch assembly_line_sensors sensors_test.launch.py

View sensor data:
    ros2 topic echo /station/break_beam
    ros2 topic echo /station/proximity
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
    sensors_pkg = get_package_share_directory('assembly_line_sensors')
    gazebo_ros_pkg = get_package_share_directory('gazebo_ros')
    
    # Model paths
    sensor_models = os.path.join(sensors_pkg, 'models')
    
    # Set GAZEBO_MODEL_PATH
    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=[
            sensor_models, ':',
            os.environ.get('GAZEBO_MODEL_PATH', '')
        ]
    )
    
    # Launch arguments
    gui_arg = DeclareLaunchArgument(
        'gui',
        default_value='true',
        description='Start Gazebo with GUI'
    )
    
    # Gazebo launch with empty world
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros_pkg, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'gui': LaunchConfiguration('gui'),
            'server_required': 'true',
            'gui_required': 'true',
        }.items(),
    )
    
    return LaunchDescription([
        gazebo_model_path,
        gui_arg,
        gazebo_launch,
    ])

