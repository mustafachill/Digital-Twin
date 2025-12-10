#!/usr/bin/env python3
"""
Multi-Robot Integration Test Launch File

Launches a complete multi-robot fleet for integration testing.
This file demonstrates the scalable architecture with:
- Config-based fleet spawning
- Independent robot nodes
- Handoff coordination

Usage:
    ros2 launch fleet_manager multi_robot_test.launch.py
    ros2 launch fleet_manager multi_robot_test.launch.py num_robots:=2
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
    TimerAction,
    LogInfo,
    ExecuteProcess,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition

from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare

from ament_index_python.packages import get_package_share_directory

# Import the prefixed config generator from xarm_ros2
from uf_ros_lib.uf_robot_utils import generate_ros2_control_params_temp_file


def load_fleet_config(config_path: str) -> Dict[str, Any]:
    """Load fleet configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_robot_types(types_path: str) -> Dict[str, Any]:
    """Load robot type definitions"""
    with open(types_path, 'r') as f:
        data = yaml.safe_load(f)
        return data.get('robot_types', {})


def generate_robot_description_and_config(robot_config: Dict, type_config: Dict) -> tuple:
    """
    Generate URDF using xacro and create prefixed controller config for a robot.
    
    Returns:
        tuple: (robot_description_xml, ros2_control_params_path)
    """
    # Use xarm_device.urdf.xacro which is the main entry point
    xarm_desc_path = get_package_share_directory('xarm_description')
    xarm_ctrl_path = get_package_share_directory('xarm_controller')
    xacro_path = os.path.join(xarm_desc_path, 'urdf', 'xarm_device.urdf.xacro')
    
    robot_id = robot_config['id']
    dof = type_config.get('dof', 5)
    config = robot_config.get('config', {})
    add_gripper = config.get('add_gripper', True)
    add_gripper_str = str(add_gripper).lower()
    prefix = f'{robot_id}_'
    
    # Get base controller config path
    base_controller_config = os.path.join(xarm_ctrl_path, 'config', f'xarm{dof}_controllers.yaml')
    
    # Generate prefixed controller config using xarm_ros2's utility
    # This creates a temp file with prefixed joint names and controller names
    ros2_control_params = generate_ros2_control_params_temp_file(
        ros2_control_params_path=base_controller_config,
        prefix=prefix,
        add_gripper=add_gripper,
        add_bio_gripper=False,
        ros_namespace=robot_id,
        update_rate=1000,
        robot_type='xarm',
        use_sim_time=True
    )
    
    cmd = [
        'xacro', xacro_path,
        f'prefix:={prefix}',
        f'dof:={dof}',
        'robot_type:=xarm',
        f'add_gripper:={add_gripper_str}',
        'hw_ns:=xarm',
        'limited:=false',
        'effort_control:=false',
        'velocity_control:=false',
        'ros2_control_plugin:=gazebo_ros2_control/GazeboSystem',
        f'ros_namespace:={robot_id}',
        f'ros2_control_params:={ros2_control_params}',
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout, ros2_control_params


def launch_setup(context, *args, **kwargs):
    """Setup function called at launch time"""
    
    num_robots = int(LaunchConfiguration('num_robots').perform(context))
    launch_gazebo = LaunchConfiguration('launch_gazebo').perform(context)
    launch_interfaces = LaunchConfiguration('launch_interfaces').perform(context)
    
    pkg_fleet_manager = get_package_share_directory('fleet_manager')
    pkg_robot_interface = get_package_share_directory('robot_interface')
    
    config_path = os.path.join(pkg_fleet_manager, 'config', 'fleet_config.yaml')
    types_path = os.path.join(pkg_fleet_manager, 'config', 'robot_types.yaml')
    interface_config = os.path.join(pkg_robot_interface, 'config', 'robot_interface.yaml')
    
    fleet_config = load_fleet_config(config_path)
    robot_types = load_robot_types(types_path)
    
    robots = fleet_config.get('fleet', {}).get('robots', [])[:num_robots]
    topology = fleet_config.get('topology', {})
    stations = {s['robot']: s for s in topology.get('stations', [])}
    
    actions = []
    
    # 1. Launch Gazebo with assembly line world
    if launch_gazebo.lower() == 'true':
        # Get world file path
        pkg_assembly_bringup = get_package_share_directory('assembly_line_bringup')
        world_file = os.path.join(pkg_assembly_bringup, 'worlds', 'assembly_line.world')
        
        # Get conveyor system models path
        pkg_conveyor_system = get_package_share_directory('conveyor_system')
        conveyor_models_path = os.path.join(pkg_conveyor_system, 'models')
        
        # Get ros2_conveyorbelt lib path for the plugin
        pkg_ros2_conveyorbelt = get_package_share_directory('ros2_conveyorbelt')
        conveyorbelt_lib_path = os.path.join(os.path.dirname(pkg_ros2_conveyorbelt), '..', 'lib')
        
        # Set GAZEBO_MODEL_PATH and GAZEBO_PLUGIN_PATH environment variables
        gazebo_model_path = os.environ.get('GAZEBO_MODEL_PATH', '')
        gazebo_plugin_path = os.environ.get('GAZEBO_PLUGIN_PATH', '')
        
        if conveyor_models_path not in gazebo_model_path:
            gazebo_model_path = f"{conveyor_models_path}:{gazebo_model_path}" if gazebo_model_path else conveyor_models_path
        if conveyorbelt_lib_path not in gazebo_plugin_path:
            gazebo_plugin_path = f"{conveyorbelt_lib_path}:{gazebo_plugin_path}" if gazebo_plugin_path else conveyorbelt_lib_path
        
        os.environ['GAZEBO_MODEL_PATH'] = gazebo_model_path
        os.environ['GAZEBO_PLUGIN_PATH'] = gazebo_plugin_path
        
        gazebo = IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('gazebo_ros'),
                    'launch',
                    'gazebo.launch.py'
                ])
            ]),
            launch_arguments={
                'verbose': 'true',
                'world': world_file,
            }.items(),
        )
        actions.append(gazebo)
    
    # 2. Fleet Manager Node
    fleet_manager_node = Node(
        package='fleet_manager',
        executable='fleet_manager_node',
        name='fleet_manager',
        output='screen',
        parameters=[
            {'config_file': config_path},
            {'robot_types_file': types_path},
            {'auto_spawn': False},
        ],
    )
    actions.append(fleet_manager_node)
    
    # 3. Spawn each robot
    spawn_delay = 2.0
    delay_increment = 12.0  # Increased from 8.0 to allow more time for controller loading
    
    for i, robot in enumerate(robots):
        if not robot.get('enabled', True):
            continue
        
        robot_id = robot['id']
        robot_type = robot['type']
        
        if robot_type not in robot_types:
            continue
        
        type_config = robot_types[robot_type]
        position = robot.get('position', {})
        config = robot.get('config', {})
        dof = type_config.get('dof', 5)
        prefix = f"{robot_id}_"
        namespace = f"/{robot_id}"
        
        # Generate URDF and prefixed controller config
        try:
            robot_description, ros2_control_params = generate_robot_description_and_config(robot, type_config)
        except Exception as e:
            print(f"Error generating URDF for {robot_id}: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Robot state publisher
        robot_group = GroupAction([
            PushRosNamespace(robot_id),
            Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                name='robot_state_publisher',
                output='screen',
                parameters=[
                    {'robot_description': robot_description},
                    {'use_sim_time': True},
                ],
            ),
        ])
        actions.append(robot_group)
        
        # Spawn entity (delayed)
        current_delay = spawn_delay + (i * delay_increment)
        
        spawn = TimerAction(
            period=current_delay,
            actions=[
                LogInfo(msg=f'Spawning robot: {robot_id}'),
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
                ),
            ]
        )
        actions.append(spawn)
        
        # Controller spawners (wait for robot to fully load)
        controller_delay = current_delay + 5.0
        
        jsb = TimerAction(
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
        actions.append(jsb)
        
        # The prefixed controller name from generate_ros2_control_params_temp_file
        traj_controller_name = f'{prefix}xarm{dof}_traj_controller'
        
        traj = TimerAction(
            period=controller_delay + 1.0,
            actions=[
                Node(
                    package='controller_manager',
                    executable='spawner',
                    name=f'spawner_traj_{robot_id}',
                    output='screen',
                    arguments=[
                        traj_controller_name,
                        '--controller-manager', f'{namespace}/controller_manager',
                    ],
                ),
            ]
        )
        actions.append(traj)
        
        # Gripper controller (if add_gripper is True)
        add_gripper = config.get('add_gripper', True)
        if add_gripper:
            gripper_controller_name = f'{prefix}xarm_gripper_traj_controller'
            
            gripper = TimerAction(
                period=controller_delay + 2.0,
                actions=[
                    Node(
                        package='controller_manager',
                        executable='spawner',
                        name=f'spawner_gripper_{robot_id}',
                        output='screen',
                        arguments=[
                            gripper_controller_name,
                            '--controller-manager', f'{namespace}/controller_manager',
                        ],
                    ),
                ]
            )
            actions.append(gripper)
        
        # Robot interface node (if enabled)
        if launch_interfaces.lower() == 'true':
            station = stations.get(robot_id, {})
            
            interface_node = TimerAction(
                period=controller_delay + 3.0,
                actions=[
                    Node(
                        package='robot_interface',
                        executable='robot_node',
                        name='robot_interface',
                        namespace=robot_id,
                        output='screen',
                        parameters=[
                            {'robot_id': robot_id},
                            {'robot_type': robot_type},
                            {'role': station.get('role', 'transfer')},
                            {'upstream_neighbor': station.get('upstream', '')},
                            {'downstream_neighbor': station.get('downstream', '')},
                            {'sensor_topic': ''},
                            {'config_file': interface_config},
                        ],
                    ),
                ]
            )
            actions.append(interface_node)
    
    # 4. Handoff Coordinator (if interfaces enabled)
    if launch_interfaces.lower() == 'true' and num_robots > 1:
        # Build robot pairs from enabled robots
        robot_ids = [r['id'] for r in robots if r.get('enabled', True)]
        robot_pairs = [f'{robot_ids[i]}:{robot_ids[i+1]}' for i in range(len(robot_ids)-1)]
        
        coordinator_delay = spawn_delay + (num_robots * delay_increment) + 5.0
        
        coordinator = TimerAction(
            period=coordinator_delay,
            actions=[
                Node(
                    package='robot_interface',
                    executable='handoff_coordinator',
                    name='handoff_coordinator',
                    output='screen',
                    parameters=[
                        {'robot_pairs': robot_pairs},
                    ],
                ),
            ]
        )
        actions.append(coordinator)
    
    return actions


def generate_launch_description():
    """Generate launch description"""
    
    return LaunchDescription([
        DeclareLaunchArgument(
            'num_robots',
            default_value='3',
            description='Number of robots to spawn (1-3)'
        ),
        
        DeclareLaunchArgument(
            'launch_gazebo',
            default_value='true',
            description='Whether to launch Gazebo'
        ),
        
        DeclareLaunchArgument(
            'launch_interfaces',
            default_value='true',
            description='Whether to launch robot interface nodes'
        ),
        
        LogInfo(msg='Starting Multi-Robot Integration Test'),
        
        OpaqueFunction(function=launch_setup),
    ])

