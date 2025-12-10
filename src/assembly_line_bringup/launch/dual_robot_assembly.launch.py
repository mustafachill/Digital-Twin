#!/usr/bin/env python3
"""
Dual Robot Assembly Line Launch
===============================

2 adet xArm 5 robot ile assembly line simülasyonu.
xarm_ros2'nin kanıtlanmış dual robot launch'ını kullanır.

Robot Pozisyonları:
- Robot 1 (L_): Pick Station
- Robot 2 (R_): Place Station

Kullanım:
    ros2 launch assembly_line_bringup dual_robot_assembly.launch.py
    ros2 launch assembly_line_bringup dual_robot_assembly.launch.py add_gripper:=true
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
    xarm_gazebo_pkg = get_package_share_directory('xarm_gazebo')
    conveyor_pkg = get_package_share_directory('conveyor_system')
    sensor_pkg = get_package_share_directory('assembly_line_sensors')
    
    # Model paths for GAZEBO_MODEL_PATH
    model_paths = [
        os.path.join(conveyor_pkg, 'models'),
        os.path.join(sensor_pkg, 'models'),
        os.environ.get('GAZEBO_MODEL_PATH', '')
    ]
    
    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=':'.join(model_paths)
    )
    
    # Launch arguments
    add_gripper_arg = DeclareLaunchArgument(
        'add_gripper',
        default_value='true',
        description='Add xArm gripper to both robots'
    )
    
    show_rviz_arg = DeclareLaunchArgument(
        'show_rviz',
        default_value='true',
        description='Show RViz visualization'
    )
    
    # Use xarm_ros2's dual robot gazebo launch
    # This properly handles:
    # - Combined URDF for both robots
    # - Namespaced controllers (L_, R_)
    # - gazebo_ros2_control plugin
    dual_robot_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xarm_gazebo_pkg, 'launch', '_dual_robot_beside_table_gazebo.launch.py')
        ),
        launch_arguments={
            # Robot 1 configuration (Left/Pick)
            'prefix_1': 'L_',
            'dof_1': '5',
            'robot_type_1': 'xarm',
            'add_gripper_1': LaunchConfiguration('add_gripper'),
            
            # Robot 2 configuration (Right/Place)
            'prefix_2': 'R_',
            'dof_2': '5',
            'robot_type_2': 'xarm',
            'add_gripper_2': LaunchConfiguration('add_gripper'),
            
            # Common settings
            'show_rviz': LaunchConfiguration('show_rviz'),
            'load_controller': 'true',
        }.items(),
    )
    
    return LaunchDescription([
        # Environment
        gazebo_model_path,
        
        # Arguments
        add_gripper_arg,
        show_rviz_arg,
        
        # Dual robot simulation
        dual_robot_gazebo,
    ])







