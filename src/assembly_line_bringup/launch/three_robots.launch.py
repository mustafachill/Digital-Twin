#!/usr/bin/env python3
"""
Three Robot Assembly Line Launch
Spawns 3 xArm 5 robots with grippers at predefined positions along the conveyor belt.

Robot positions (configured for 4m conveyor):
- xArm1: Station 1 (pick) at y=-1.2m
- xArm2: Station 2 (transfer) at y=0.0m  
- xArm3: Station 3 (place) at y=1.2m

Usage:
    ros2 launch assembly_line_bringup three_robots.launch.py
"""

import os
import yaml
from pathlib import Path
from ament_index_python import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    SetEnvironmentVariable,
    GroupAction,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace
from launch.conditions import IfCondition
from launch_ros.substitutions import FindPackageShare
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.actions import OpaqueFunction
from uf_ros_lib.uf_robot_utils import get_xacro_content


def generate_robot_description(context, prefix, dof=5, add_gripper=True):
    """Generate robot description URDF content for a single robot."""
    xacro_file = Path(get_package_share_directory('xarm_description')) / 'urdf' / 'xarm_device.urdf.xacro'
    
    # Get controller params
    controller_params = os.path.join(
        get_package_share_directory('xarm_controller'),
        'config', 'xarm5_controllers.yaml'
    )
    
    robot_description = get_xacro_content(
        context,
        xacro_file=xacro_file,
        prefix=prefix,
        dof=str(dof),
        robot_type='xarm',
        add_gripper=str(add_gripper).lower(),
        hw_ns='xarm',
        limited='false',
        effort_control='false',
        velocity_control='false',
        ros2_control_plugin='gazebo_ros2_control/GazeboSystem',
        ros2_control_params=controller_params,
        add_realsense_d435i='false',
    )
    return robot_description


def launch_setup(context, *args, **kwargs):
    # Robot configurations
    robots = [
        {'prefix': 'xarm1_', 'x': -0.5, 'y': -1.2, 'z': 0.8, 'yaw': 1.5708},  # Station 1
        {'prefix': 'xarm2_', 'x': -0.5, 'y': 0.0, 'z': 0.8, 'yaw': 1.5708},   # Station 2
        {'prefix': 'xarm3_', 'x': -0.5, 'y': 1.2, 'z': 0.8, 'yaw': 1.5708},   # Station 3
    ]
    
    show_rviz = LaunchConfiguration('show_rviz', default='true')
    add_gripper = LaunchConfiguration('add_gripper', default='true')
    
    # Model paths
    conveyor_models = os.path.join(get_package_share_directory('conveyor_system'), 'models')
    sensor_models = os.path.join(get_package_share_directory('assembly_line_sensors'), 'models')
    
    # Get Gazebo packages
    gazebo_ros_pkg = get_package_share_directory('gazebo_ros')
    assembly_bringup_pkg = get_package_share_directory('assembly_line_bringup')
    
    # World file
    world_file = os.path.join(assembly_bringup_pkg, 'worlds', 'assembly_line.world')
    
    launch_items = []
    
    # Set GAZEBO_MODEL_PATH
    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=[
            conveyor_models, ':',
            sensor_models, ':',
            os.environ.get('GAZEBO_MODEL_PATH', '')
        ]
    )
    launch_items.append(gazebo_model_path)
    
    # Gazebo launch
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros_pkg, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'world': world_file,
            'server_required': 'true',
            'gui_required': 'true',
        }.items(),
    )
    launch_items.append(gazebo_launch)
    
    # Generate robot descriptions and spawn each robot
    for i, robot in enumerate(robots):
        prefix = robot['prefix']
        robot_name = prefix.rstrip('_')
        
        # Generate URDF
        robot_description = generate_robot_description(
            context, 
            prefix=prefix,
            add_gripper=add_gripper.perform(context) in ('True', 'true')
        )
        
        # Robot state publisher
        robot_state_publisher = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name=f'{robot_name}_robot_state_publisher',
            namespace=robot_name,
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': True,
            }],
            remappings=[
                ('/tf', 'tf'),
                ('/tf_static', 'tf_static'),
            ]
        )
        
        # Spawn entity
        spawn_entity = Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            name=f'spawn_{robot_name}',
            output='screen',
            arguments=[
                '-topic', f'/{robot_name}/robot_description',
                '-entity', robot_name,
                '-x', str(robot['x']),
                '-y', str(robot['y']),
                '-z', str(robot['z']),
                '-Y', str(robot['yaw']),
            ],
            parameters=[{'use_sim_time': True}],
        )
        
        # Controller spawners (with delay to wait for spawn)
        controllers = [
            f'{prefix}xarm5_traj_controller',
            'joint_state_broadcaster',
        ]
        
        if add_gripper.perform(context) in ('True', 'true'):
            controllers.append(f'{prefix}xarm_gripper_traj_controller')
        
        controller_nodes = []
        for controller in controllers:
            controller_nodes.append(
                Node(
                    package='controller_manager',
                    executable='spawner',
                    name=f'spawner_{controller}_{robot_name}',
                    output='screen',
                    arguments=[
                        controller,
                        '--controller-manager', f'/{robot_name}/controller_manager'
                    ],
                    parameters=[{'use_sim_time': True}],
                )
            )
        
        # Add delays to sequential spawning
        delay = i * 3.0  # 3 second delay between robots
        
        launch_items.append(
            TimerAction(
                period=delay,
                actions=[robot_state_publisher]
            )
        )
        
        launch_items.append(
            TimerAction(
                period=delay + 1.0,
                actions=[spawn_entity]
            )
        )
        
        # Spawn controllers after entity
        for j, ctrl_node in enumerate(controller_nodes):
            launch_items.append(
                TimerAction(
                    period=delay + 2.0 + (j * 0.5),
                    actions=[ctrl_node]
                )
            )
    
    return launch_items


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'show_rviz',
            default_value='true',
            description='Show RViz'
        ),
        DeclareLaunchArgument(
            'add_gripper',
            default_value='true',
            description='Add gripper to robots'
        ),
        OpaqueFunction(function=launch_setup)
    ])

