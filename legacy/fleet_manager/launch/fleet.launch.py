#!/usr/bin/env python3
"""
Fleet Launch File

Launches the complete multi-robot fleet based on configuration.
This is the main entry point for the fleet system.

Usage:
    ros2 launch fleet_manager fleet.launch.py
    ros2 launch fleet_manager fleet.launch.py config_file:=/path/to/custom_config.yaml
"""

import os
import yaml
import subprocess
from typing import List, Dict, Any

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    OpaqueFunction,
    IncludeLaunchDescription,
    GroupAction,
    RegisterEventHandler,
    TimerAction,
    LogInfo,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition

from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare

from ament_index_python.packages import get_package_share_directory


def load_fleet_config(config_path: str) -> Dict[str, Any]:
    """Load fleet configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_robot_types(types_path: str) -> Dict[str, Any]:
    """Load robot type definitions"""
    with open(types_path, 'r') as f:
        data = yaml.safe_load(f)
        return data.get('robot_types', {})


def generate_robot_description(robot_config: Dict, type_config: Dict) -> str:
    """Generate URDF using xacro for a robot"""
    # Use xarm_device.urdf.xacro which is the main entry point
    package_path = get_package_share_directory('xarm_description')
    xacro_path = os.path.join(package_path, 'urdf', 'xarm_device.urdf.xacro')
    
    robot_id = robot_config['id']
    dof = type_config.get('dof', 5)
    config = robot_config.get('config', {})
    add_gripper = str(config.get('add_gripper', True)).lower()
    
    # Build xacro command
    cmd = [
        'xacro', xacro_path,
        f'prefix:={robot_id}_',
        f'dof:={dof}',
        'robot_type:=xarm',
        f'add_gripper:={add_gripper}',
        'hw_ns:=xarm',
        'limited:=false',
        'effort_control:=false',
        'velocity_control:=false',
        'ros2_control_plugin:=gazebo_ros2_control/GazeboSystem',
        f'ros_namespace:={robot_id}',
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def generate_robot_actions(context, config_path: str, types_path: str) -> List:
    """Generate launch actions for all robots in fleet config"""
    
    fleet_config = load_fleet_config(config_path)
    robot_types = load_robot_types(types_path)
    
    robots = fleet_config.get('fleet', {}).get('robots', [])
    actions = []
    
    spawn_delay = 0.0
    delay_increment = 5.0  # Seconds between robot spawns
    
    for robot in robots:
        if not robot.get('enabled', True):
            continue
            
        robot_id = robot['id']
        robot_type = robot['type']
        
        if robot_type not in robot_types:
            print(f"Warning: Unknown robot type {robot_type} for robot {robot_id}")
            continue
        
        type_config = robot_types[robot_type]
        position = robot.get('position', {})
        config = robot.get('config', {})
        
        # Generate robot description
        try:
            robot_description = generate_robot_description(robot, type_config)
        except Exception as e:
            print(f"Error generating URDF for {robot_id}: {e}")
            continue
        
        dof = type_config.get('dof', 5)
        prefix = f"{robot_id}_"
        namespace = f"/{robot_id}"
        
        # Create robot group with namespace
        robot_group = GroupAction([
            PushRosNamespace(robot_id),
            
            # Robot state publisher
            Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                name='robot_state_publisher',
                output='screen',
                parameters=[
                    {'robot_description': robot_description},
                    {'use_sim_time': True},
                ],
                remappings=[
                    ('/tf', 'tf'),
                    ('/tf_static', 'tf_static'),
                ],
            ),
        ])
        
        # Spawn entity (delayed)
        spawn_action = TimerAction(
            period=spawn_delay,
            actions=[
                Node(
                    package='gazebo_ros',
                    executable='spawn_entity.py',
                    name=f'spawn_{robot_id}',
                    output='screen',
                    arguments=[
                        '-topic', f'{namespace}/robot_description',
                        '-entity', robot_id,
                        '-x', str(position.get('x', 0.0)),
                        '-y', str(position.get('y', 0.0)),
                        '-z', str(position.get('z', 0.0)),
                        '-R', str(position.get('roll', 0.0)),
                        '-P', str(position.get('pitch', 0.0)),
                        '-Y', str(position.get('yaw', 0.0)),
                    ],
                    parameters=[{'use_sim_time': True}],
                ),
            ]
        )
        
        # Controller spawners (more delayed)
        controller_delay = spawn_delay + 3.0
        
        joint_state_broadcaster = TimerAction(
            period=controller_delay,
            actions=[
                Node(
                    package='controller_manager',
                    executable='spawner',
                    name=f'spawner_jsb_{robot_id}',
                    output='screen',
                    arguments=[
                        'joint_state_broadcaster',
                        '--controller-manager', f'{namespace}/controller_manager',
                    ],
                ),
            ]
        )
        
        trajectory_controller = TimerAction(
            period=controller_delay + 1.0,
            actions=[
                Node(
                    package='controller_manager',
                    executable='spawner',
                    name=f'spawner_traj_{robot_id}',
                    output='screen',
                    arguments=[
                        f'{prefix}xarm{dof}_traj_controller',
                        '--controller-manager', f'{namespace}/controller_manager',
                    ],
                ),
            ]
        )
        
        # Gripper controller if enabled
        gripper_actions = []
        if config.get('add_gripper', True):
            gripper_controller = TimerAction(
                period=controller_delay + 2.0,
                actions=[
                    Node(
                        package='controller_manager',
                        executable='spawner',
                        name=f'spawner_gripper_{robot_id}',
                        output='screen',
                        arguments=[
                            f'{prefix}xarm_gripper_traj_controller',
                            '--controller-manager', f'{namespace}/controller_manager',
                        ],
                    ),
                ]
            )
            gripper_actions.append(gripper_controller)
        
        actions.extend([
            robot_group,
            spawn_action,
            joint_state_broadcaster,
            trajectory_controller,
        ])
        actions.extend(gripper_actions)
        
        spawn_delay += delay_increment
    
    return actions


def launch_setup(context, *args, **kwargs):
    """Setup function called at launch time"""
    
    config_file = LaunchConfiguration('config_file').perform(context)
    robot_types_file = LaunchConfiguration('robot_types_file').perform(context)
    launch_gazebo = LaunchConfiguration('launch_gazebo').perform(context)
    world_file = LaunchConfiguration('world_file').perform(context)
    
    actions = []
    
    # Launch Gazebo if requested
    if launch_gazebo.lower() == 'true':
        gazebo_launch = IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('gazebo_ros'),
                    'launch',
                    'gazebo.launch.py'
                ])
            ]),
            launch_arguments={
                'world': world_file,
                'verbose': 'true',
            }.items(),
        )
        actions.append(gazebo_launch)
    
    # Fleet manager node
    fleet_manager_node = Node(
        package='fleet_manager',
        executable='fleet_manager_node',
        name='fleet_manager',
        output='screen',
        parameters=[
            {'config_file': config_file},
            {'robot_types_file': robot_types_file},
            {'auto_spawn': False},  # We handle spawning in launch
        ],
    )
    actions.append(fleet_manager_node)
    
    # Generate robot actions
    robot_actions = generate_robot_actions(context, config_file, robot_types_file)
    actions.extend(robot_actions)
    
    return actions


def generate_launch_description():
    """Generate launch description"""
    
    # Get package paths
    pkg_fleet_manager = get_package_share_directory('fleet_manager')
    pkg_assembly_bringup = get_package_share_directory('assembly_line_bringup')
    
    # Default paths
    default_config = os.path.join(pkg_fleet_manager, 'config', 'fleet_config.yaml')
    default_types = os.path.join(pkg_fleet_manager, 'config', 'robot_types.yaml')
    default_world = os.path.join(pkg_assembly_bringup, 'worlds', 'assembly_line.world')
    
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'config_file',
            default_value=default_config,
            description='Path to fleet configuration YAML file'
        ),
        
        DeclareLaunchArgument(
            'robot_types_file',
            default_value=default_types,
            description='Path to robot types definition file'
        ),
        
        DeclareLaunchArgument(
            'launch_gazebo',
            default_value='true',
            description='Whether to launch Gazebo'
        ),
        
        DeclareLaunchArgument(
            'world_file',
            default_value=default_world,
            description='Path to Gazebo world file'
        ),
        
        # Setup function
        OpaqueFunction(function=launch_setup),
    ])

