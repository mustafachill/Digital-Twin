#!/usr/bin/env python3
"""
Robot Interface Launch File

Launches robot interface node for a single robot.
Can be included multiple times for multi-robot setups.

Usage:
    ros2 launch robot_interface robot_interface.launch.py robot_id:=robot_1
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description"""
    
    pkg_robot_interface = get_package_share_directory('robot_interface')
    
    config_file = os.path.join(pkg_robot_interface, 'config', 'robot_interface.yaml')
    
    return LaunchDescription([
        # Arguments
        DeclareLaunchArgument(
            'robot_id',
            default_value='robot_1',
            description='Unique robot identifier'
        ),
        
        DeclareLaunchArgument(
            'robot_type',
            default_value='xarm5',
            description='Type of robot (xarm5, xarm6, xarm7)'
        ),
        
        DeclareLaunchArgument(
            'role',
            default_value='transfer',
            description='Robot role (pick, transfer, place)'
        ),
        
        DeclareLaunchArgument(
            'upstream_neighbor',
            default_value='',
            description='Upstream neighbor robot ID or conveyor_entry'
        ),
        
        DeclareLaunchArgument(
            'downstream_neighbor',
            default_value='',
            description='Downstream neighbor robot ID or conveyor_exit'
        ),
        
        DeclareLaunchArgument(
            'sensor_topic',
            default_value='',
            description='Break beam sensor topic'
        ),
        
        # Robot interface node
        Node(
            package='robot_interface',
            executable='robot_node',
            name='robot_interface',
            namespace=LaunchConfiguration('robot_id'),
            output='screen',
            parameters=[
                {'robot_id': LaunchConfiguration('robot_id')},
                {'robot_type': LaunchConfiguration('robot_type')},
                {'role': LaunchConfiguration('role')},
                {'upstream_neighbor': LaunchConfiguration('upstream_neighbor')},
                {'downstream_neighbor': LaunchConfiguration('downstream_neighbor')},
                {'sensor_topic': LaunchConfiguration('sensor_topic')},
                {'config_file': config_file},
            ],
        ),
    ])

