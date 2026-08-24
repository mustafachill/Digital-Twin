#!/usr/bin/env python3
"""
Robot Spawner for Fleet Manager

Handles spawning robots into Gazebo with proper namespace isolation.
Each robot gets its own:
- Namespace (/robot_1, /robot_2, etc.)
- robot_state_publisher
- controller_manager
- Controllers
"""

import os
import subprocess
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path

import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory

from .config_loader import RobotConfig, Position


class RobotSpawner:
    """Spawns robots into Gazebo with proper namespace isolation"""
    
    def __init__(self, node: Node, robot_types_config: Dict[str, Any]):
        self.node = node
        self.robot_types = robot_types_config
        self.spawned_robots: Dict[str, Dict[str, Any]] = {}
        self.logger = node.get_logger()
        
    def spawn_robot(self, robot_config: RobotConfig) -> bool:
        """
        Spawn a single robot into Gazebo
        
        Args:
            robot_config: Robot configuration from fleet config
            
        Returns:
            True if spawn was successful
        """
        robot_id = robot_config.id
        robot_type = robot_config.type
        
        if robot_id in self.spawned_robots:
            self.logger.warn(f"Robot {robot_id} already spawned")
            return False
            
        if robot_type not in self.robot_types:
            self.logger.error(f"Unknown robot type: {robot_type}")
            return False
        
        type_config = self.robot_types[robot_type]
        
        self.logger.info(f"Spawning robot: {robot_id} (type: {robot_type})")
        
        try:
            # 1. Generate robot description (URDF)
            urdf_content = self._generate_urdf(robot_config, type_config)
            if not urdf_content:
                return False
            
            # 2. Save URDF to temp file for spawn_entity
            urdf_file = self._save_urdf_temp(robot_id, urdf_content)
            
            # 3. Generate controller config
            controller_config = self._generate_controller_config(robot_config, type_config)
            controller_file = self._save_controller_config_temp(robot_id, controller_config)
            
            # Store spawn info
            self.spawned_robots[robot_id] = {
                'config': robot_config,
                'type_config': type_config,
                'urdf_file': urdf_file,
                'controller_file': controller_file,
                'urdf_content': urdf_content,
                'namespace': f'/{robot_id}',
                'processes': []
            }
            
            self.logger.info(f"Robot {robot_id} prepared for spawn")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to spawn robot {robot_id}: {e}")
            return False
    
    def _generate_urdf(self, robot_config: RobotConfig, type_config: Dict) -> Optional[str]:
        """Generate URDF for the robot using xacro"""
        try:
            urdf_config = type_config.get('urdf', {})
            package = urdf_config.get('package', 'xarm_description')
            urdf_file = urdf_config.get('file', 'urdf/xarm5/xarm5.urdf.xacro')
            
            package_path = get_package_share_directory(package)
            xacro_path = os.path.join(package_path, urdf_file)
            
            # Build xacro command with parameters
            prefix = f"{robot_config.id}_"
            dof = type_config.get('dof', 5)
            
            cmd = [
                'xacro', xacro_path,
                f'prefix:={prefix}',
                f'dof:={dof}',
                'robot_type:=xarm',
                f'add_gripper:={str(robot_config.add_gripper).lower()}',
                'hw_ns:=xarm',
                'limited:=false',
                'effort_control:=false',
                'velocity_control:=false',
                'ros2_control_plugin:=gazebo_ros2_control/GazeboSystem',
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Xacro failed: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"URDF generation failed: {e}")
            return None
    
    def _save_urdf_temp(self, robot_id: str, urdf_content: str) -> str:
        """Save URDF to temporary file"""
        temp_dir = tempfile.gettempdir()
        urdf_path = os.path.join(temp_dir, f'{robot_id}_description.urdf')
        with open(urdf_path, 'w') as f:
            f.write(urdf_content)
        return urdf_path
    
    def _generate_controller_config(self, robot_config: RobotConfig, type_config: Dict) -> Dict:
        """Generate controller configuration for the robot"""
        prefix = f"{robot_config.id}_"
        dof = type_config.get('dof', 5)
        controller_config = type_config.get('controller', {})
        
        joints = [f"{prefix}{j}" for j in type_config.get('joints', [])]
        
        config = {
            'controller_manager': {
                'ros__parameters': {
                    'update_rate': 1000,
                    'joint_state_broadcaster': {
                        'type': 'joint_state_broadcaster/JointStateBroadcaster'
                    },
                    f'{prefix}xarm{dof}_traj_controller': {
                        'type': 'joint_trajectory_controller/JointTrajectoryController'
                    }
                }
            },
            'joint_state_broadcaster': {
                'ros__parameters': {}
            },
            f'{prefix}xarm{dof}_traj_controller': {
                'ros__parameters': {
                    'joints': joints,
                    'command_interfaces': ['position'],
                    'state_interfaces': ['position', 'velocity'],
                    'state_publish_rate': 100.0,
                    'action_monitor_rate': 20.0,
                    'allow_partial_joints_goal': False,
                }
            }
        }
        
        # Add gripper controller if enabled
        if robot_config.add_gripper:
            gripper_joints = [f"{prefix}drive_joint"]
            config['controller_manager']['ros__parameters'][f'{prefix}xarm_gripper_traj_controller'] = {
                'type': 'joint_trajectory_controller/JointTrajectoryController'
            }
            config[f'{prefix}xarm_gripper_traj_controller'] = {
                'ros__parameters': {
                    'joints': gripper_joints,
                    'command_interfaces': ['position'],
                    'state_interfaces': ['position', 'velocity'],
                }
            }
        
        return config
    
    def _save_controller_config_temp(self, robot_id: str, config: Dict) -> str:
        """Save controller config to temporary file"""
        import yaml
        temp_dir = tempfile.gettempdir()
        config_path = os.path.join(temp_dir, f'{robot_id}_controllers.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return config_path
    
    def get_spawn_commands(self, robot_id: str) -> List[Dict[str, Any]]:
        """
        Get the commands needed to spawn a robot
        
        Returns list of command dicts with:
        - 'type': 'node' or 'spawn_entity'
        - 'package': ROS2 package
        - 'executable': Node executable
        - 'arguments': Command arguments
        - 'namespace': Robot namespace
        """
        if robot_id not in self.spawned_robots:
            return []
        
        robot_info = self.spawned_robots[robot_id]
        robot_config = robot_info['config']
        type_config = robot_info['type_config']
        namespace = robot_info['namespace']
        dof = type_config.get('dof', 5)
        prefix = f"{robot_id}_"
        
        commands = []
        
        # 1. robot_state_publisher
        commands.append({
            'type': 'node',
            'package': 'robot_state_publisher',
            'executable': 'robot_state_publisher',
            'name': f'{robot_id}_robot_state_publisher',
            'namespace': namespace,
            'parameters': [
                {'robot_description': robot_info['urdf_content']},
                {'use_sim_time': True}
            ],
            'remappings': [
                ('/tf', 'tf'),
                ('/tf_static', 'tf_static')
            ]
        })
        
        # 2. spawn_entity
        pos = robot_config.position
        commands.append({
            'type': 'spawn_entity',
            'package': 'gazebo_ros',
            'executable': 'spawn_entity.py',
            'arguments': [
                '-topic', f'{namespace}/robot_description',
                '-entity', robot_id,
                '-x', str(pos.x),
                '-y', str(pos.y),
                '-z', str(pos.z),
                '-R', str(pos.roll),
                '-P', str(pos.pitch),
                '-Y', str(pos.yaw),
            ],
            'parameters': [{'use_sim_time': True}]
        })
        
        # 3. Controller spawners
        controllers = [
            'joint_state_broadcaster',
            f'{prefix}xarm{dof}_traj_controller',
        ]
        if robot_config.add_gripper:
            controllers.append(f'{prefix}xarm_gripper_traj_controller')
        
        for controller in controllers:
            commands.append({
                'type': 'spawner',
                'package': 'controller_manager',
                'executable': 'spawner',
                'arguments': [
                    controller,
                    '--controller-manager', f'{namespace}/controller_manager'
                ],
                'parameters': [{'use_sim_time': True}]
            })
        
        return commands
    
    def get_robot_info(self, robot_id: str) -> Optional[Dict]:
        """Get information about a spawned robot"""
        return self.spawned_robots.get(robot_id)
    
    def get_all_robots(self) -> Dict[str, Dict]:
        """Get all spawned robots"""
        return self.spawned_robots.copy()
    
    def remove_robot(self, robot_id: str) -> bool:
        """Remove a robot from tracking (doesn't actually remove from Gazebo)"""
        if robot_id in self.spawned_robots:
            del self.spawned_robots[robot_id]
            return True
        return False


def main():
    """Test robot spawner"""
    print("Robot Spawner module - use via fleet_manager_node")


if __name__ == '__main__':
    main()







