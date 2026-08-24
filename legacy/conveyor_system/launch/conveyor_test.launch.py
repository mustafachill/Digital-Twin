#!/usr/bin/env python3
"""
Conveyor System Test Launch
Tests the conveyor belt and box models without robots.

Usage:
    ros2 launch conveyor_system conveyor_test.launch.py

Control conveyor:
    ros2 service call /conveyor/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 50.0}"
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
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Package paths
    conveyor_system_pkg = get_package_share_directory('conveyor_system')
    gazebo_ros_pkg = get_package_share_directory('gazebo_ros')
    
    # World file
    world_file = os.path.join(conveyor_system_pkg, 'worlds', 'conveyor_test.world')
    
    # Model paths
    conveyor_models = os.path.join(conveyor_system_pkg, 'models')
    ifra_models = os.path.join(
        get_package_share_directory('conveyorbelt_gazebo'), 'models'
    )
    
    # Set GAZEBO_MODEL_PATH
    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=[
            conveyor_models, ':',
            ifra_models, ':',
            os.environ.get('GAZEBO_MODEL_PATH', '')
        ]
    )
    
    # Launch arguments
    gui_arg = DeclareLaunchArgument(
        'gui',
        default_value='true',
        description='Start Gazebo with GUI'
    )
    
    paused_arg = DeclareLaunchArgument(
        'paused',
        default_value='false',
        description='Start Gazebo paused'
    )
    
    # Gazebo launch
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros_pkg, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'world': world_file,
            'gui': LaunchConfiguration('gui'),
            'paused': LaunchConfiguration('paused'),
            'server_required': 'true',
            'gui_required': 'true',
        }.items(),
    )
    
    return LaunchDescription([
        gazebo_model_path,
        gui_arg,
        paused_arg,
        gazebo_launch,
    ])

