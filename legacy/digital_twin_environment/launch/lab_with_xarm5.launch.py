#!/usr/bin/env python3
"""
Digital Twin Laboratory Environment with xArm 5

Bu launch dosyası robotics_lab.world ortamında xArm 5 simülasyonunu başlatır.
MoveIt2 ile interaktif kontrol dahildir.

Kullanım:
    ros2 launch digital_twin_environment lab_with_xarm5.launch.py

Parametreler:
    show_rviz (bool): RViz ve MoveIt arayüzünü göster (default: true)
    use_custom_world (bool): Özel world dosyası kullan (default: true)
"""

import os
from pathlib import Path

from ament_index_python import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Package paths
    digital_twin_env_pkg = get_package_share_directory('digital_twin_environment')
    xarm_moveit_config_pkg = get_package_share_directory('xarm_moveit_config')
    
    # Custom world file path
    robotics_lab_world = os.path.join(digital_twin_env_pkg, 'worlds', 'robotics_lab.world')
    
    # Models path for GAZEBO_MODEL_PATH
    models_path = os.path.join(digital_twin_env_pkg, 'models')
    
    # =====================================================
    # Launch Arguments
    # =====================================================
    
    show_rviz_arg = DeclareLaunchArgument(
        'show_rviz',
        default_value='true',
        description='Launch RViz with MoveIt interface'
    )
    
    use_custom_world_arg = DeclareLaunchArgument(
        'use_custom_world',
        default_value='true',
        description='Use robotics_lab.world instead of default table.world'
    )
    
    add_gripper_arg = DeclareLaunchArgument(
        'add_gripper',
        default_value='false',
        description='Add gripper to xArm 5'
    )
    
    # =====================================================
    # Environment Variables
    # =====================================================
    
    # Add custom models to GAZEBO_MODEL_PATH
    set_gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=[
            models_path,
            ':',
            os.environ.get('GAZEBO_MODEL_PATH', '')
        ]
    )
    
    # =====================================================
    # xArm 5 MoveIt Gazebo Launch
    # =====================================================
    
    # Use xarm_moveit_config's gazebo launch with our custom world
    xarm5_moveit_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xarm_moveit_config_pkg, 'launch', 'xarm5_moveit_gazebo.launch.py')
        ),
        launch_arguments={
            'add_gripper': LaunchConfiguration('add_gripper'),
            'show_rviz': LaunchConfiguration('show_rviz'),
            # World file will be overridden via GAZEBO parameters if needed
        }.items(),
    )
    
    # =====================================================
    # Return Launch Description
    # =====================================================
    
    return LaunchDescription([
        # Arguments
        show_rviz_arg,
        use_custom_world_arg,
        add_gripper_arg,
        
        # Environment
        set_gazebo_model_path,
        
        # Launch xArm 5 simulation
        xarm5_moveit_gazebo,
    ])

