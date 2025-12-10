#!/usr/bin/env python3
"""
Digital Twin - Multi-Robot Assembly Line
=========================================

Ana Digital Twin launch dosyası.

Modlar:
- single: Tek xArm 5 robot (test için)
- dual: 2x xArm 5 robot (çalışan assembly line)

Kullanım:
    # Dual robot (varsayılan - assembly line)
    ros2 launch assembly_line_bringup digital_twin.launch.py
    
    # Tek robot (test)
    ros2 launch assembly_line_bringup digital_twin.launch.py mode:=single
    
    # Gripper ile
    ros2 launch assembly_line_bringup digital_twin.launch.py add_gripper:=true
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    GroupAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition


def generate_launch_description():
    # Package paths
    assembly_bringup_pkg = get_package_share_directory('assembly_line_bringup')
    xarm_gazebo_pkg = get_package_share_directory('xarm_gazebo')
    xarm_moveit_pkg = get_package_share_directory('xarm_moveit_config')
    conveyor_pkg = get_package_share_directory('conveyor_system')
    sensor_pkg = get_package_share_directory('assembly_line_sensors')
    
    # Model paths
    model_paths = [
        os.path.join(conveyor_pkg, 'models'),
        os.path.join(sensor_pkg, 'models'),
        os.environ.get('GAZEBO_MODEL_PATH', '')
    ]
    
    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=':'.join(model_paths)
    )
    
    # =========================================
    # Launch Arguments
    # =========================================
    mode_arg = DeclareLaunchArgument(
        'mode',
        default_value='dual',
        description='Robot mode: single or dual',
        choices=['single', 'dual']
    )
    
    add_gripper_arg = DeclareLaunchArgument(
        'add_gripper',
        default_value='true',
        description='Add xArm gripper'
    )
    
    show_rviz_arg = DeclareLaunchArgument(
        'show_rviz',
        default_value='true',
        description='Show RViz'
    )
    
    # =========================================
    # Single Robot Mode
    # =========================================
    single_robot = GroupAction(
        condition=IfCondition(
            PythonExpression(["'", LaunchConfiguration('mode'), "' == 'single'"])
        ),
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(xarm_moveit_pkg, 'launch', 'xarm5_moveit_gazebo.launch.py')
                ),
                launch_arguments={
                    'add_gripper': LaunchConfiguration('add_gripper'),
                    'show_rviz': LaunchConfiguration('show_rviz'),
                }.items(),
            )
        ]
    )
    
    # =========================================
    # Dual Robot Mode (Assembly Line)
    # =========================================
    dual_robot = GroupAction(
        condition=IfCondition(
            PythonExpression(["'", LaunchConfiguration('mode'), "' == 'dual'"])
        ),
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(xarm_gazebo_pkg, 'launch', '_dual_robot_beside_table_gazebo.launch.py')
                ),
                launch_arguments={
                    'prefix_1': 'L_',
                    'prefix_2': 'R_',
                    'dof_1': '5',
                    'dof_2': '5',
                    'robot_type_1': 'xarm',
                    'robot_type_2': 'xarm',
                    'add_gripper_1': LaunchConfiguration('add_gripper'),
                    'add_gripper_2': LaunchConfiguration('add_gripper'),
                    'show_rviz': LaunchConfiguration('show_rviz'),
                    'load_controller': 'true',
                }.items(),
            )
        ]
    )
    
    # =========================================
    # Launch Description
    # =========================================
    return LaunchDescription([
        # Environment
        gazebo_model_path,
        
        # Arguments
        mode_arg,
        add_gripper_arg,
        show_rviz_arg,
        
        # Robot launches
        single_robot,
        dual_robot,
    ])
