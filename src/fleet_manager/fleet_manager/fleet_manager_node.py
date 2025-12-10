#!/usr/bin/env python3
"""
Fleet Manager Node

Main ROS2 node for managing multi-robot fleet.
Responsibilities:
- Load fleet configuration from YAML
- Spawn robots into Gazebo
- Provide services for runtime robot management
- Monitor fleet health
"""

import os
from typing import Dict, List

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from ament_index_python.packages import get_package_share_directory

from std_msgs.msg import String

from .config_loader import ConfigLoader, FleetConfig, RobotConfig
from .robot_spawner import RobotSpawner


class FleetState:
    """Fleet states"""
    INITIALIZING = "INITIALIZING"
    LOADING_CONFIG = "LOADING_CONFIG"
    SPAWNING = "SPAWNING"
    READY = "READY"
    ERROR = "ERROR"


class FleetManagerNode(Node):
    """
    Fleet Manager Node
    
    Reads fleet configuration and orchestrates robot spawning.
    """
    
    def __init__(self):
        super().__init__('fleet_manager')
        
        self.callback_group = ReentrantCallbackGroup()
        
        # Declare parameters
        self.declare_parameter('config_file', '')
        self.declare_parameter('robot_types_file', '')
        self.declare_parameter('auto_spawn', True)
        
        # Get parameters
        config_file = self.get_parameter('config_file').get_parameter_value().string_value
        robot_types_file = self.get_parameter('robot_types_file').get_parameter_value().string_value
        self.auto_spawn = self.get_parameter('auto_spawn').get_parameter_value().bool_value
        
        # Default config paths
        if not config_file:
            pkg_path = get_package_share_directory('fleet_manager')
            config_file = os.path.join(pkg_path, 'config', 'fleet_config.yaml')
        if not robot_types_file:
            pkg_path = get_package_share_directory('fleet_manager')
            robot_types_file = os.path.join(pkg_path, 'config', 'robot_types.yaml')
        
        self.config_file = config_file
        self.robot_types_file = robot_types_file
        
        # State
        self.fleet_state = FleetState.INITIALIZING
        self.fleet_config: FleetConfig = None
        self.robot_types: Dict = {}
        self.spawner: RobotSpawner = None
        self.spawn_queue: List[RobotConfig] = []
        
        # Publishers
        self.fleet_state_pub = self.create_publisher(
            String, '/fleet_manager/state', 10
        )
        
        # Timers
        self.state_timer = self.create_timer(
            1.0, self.publish_state, callback_group=self.callback_group
        )
        
        self.get_logger().info('Fleet Manager Node started')
        self.get_logger().info(f'Config file: {self.config_file}')
        self.get_logger().info(f'Robot types file: {self.robot_types_file}')
        
        # Load configuration
        self.load_config()
        
    def load_config(self):
        """Load fleet and robot type configuration"""
        self.fleet_state = FleetState.LOADING_CONFIG
        
        try:
            # Load fleet config
            loader = ConfigLoader(self.config_file)
            self.fleet_config = loader.load()
            
            # Load robot types
            self.robot_types = loader.load_robot_types(self.robot_types_file)
            
            self.get_logger().info(f'Fleet config loaded: {self.fleet_config.name}')
            self.get_logger().info(f'Robots: {len(self.fleet_config.robots)}')
            self.get_logger().info(f'Robot types: {list(self.robot_types.keys())}')
            
            # Initialize spawner
            self.spawner = RobotSpawner(self, self.robot_types)
            
            # Prepare spawn queue
            self.spawn_queue = list(self.fleet_config.get_enabled_robots())
            
            if self.auto_spawn:
                self.get_logger().info('Auto-spawn enabled, preparing robots...')
                self.prepare_robots()
            else:
                self.fleet_state = FleetState.READY
                self.get_logger().info('Fleet manager ready (auto-spawn disabled)')
                
        except FileNotFoundError as e:
            self.get_logger().error(f'Config file not found: {e}')
            self.fleet_state = FleetState.ERROR
        except Exception as e:
            self.get_logger().error(f'Failed to load config: {e}')
            self.fleet_state = FleetState.ERROR
    
    def prepare_robots(self):
        """Prepare all robots for spawning"""
        self.fleet_state = FleetState.SPAWNING
        
        for robot in self.spawn_queue:
            self.get_logger().info(f'Preparing robot: {robot.id}')
            success = self.spawner.spawn_robot(robot)
            if success:
                self.get_logger().info(f'Robot {robot.id} prepared successfully')
            else:
                self.get_logger().warn(f'Failed to prepare robot {robot.id}')
        
        self.fleet_state = FleetState.READY
        self.get_logger().info('All robots prepared for launch')
        self.log_spawn_info()
    
    def log_spawn_info(self):
        """Log spawn information for launch file generation"""
        robots = self.spawner.get_all_robots()
        
        self.get_logger().info('=' * 60)
        self.get_logger().info('SPAWN INFORMATION')
        self.get_logger().info('=' * 60)
        
        for robot_id, info in robots.items():
            self.get_logger().info(f'Robot: {robot_id}')
            self.get_logger().info(f'  Namespace: {info["namespace"]}')
            self.get_logger().info(f'  URDF file: {info["urdf_file"]}')
            self.get_logger().info(f'  Controller config: {info["controller_file"]}')
            
            # Get spawn commands
            commands = self.spawner.get_spawn_commands(robot_id)
            self.get_logger().info(f'  Commands to execute: {len(commands)}')
        
        self.get_logger().info('=' * 60)
    
    def publish_state(self):
        """Publish current fleet state"""
        msg = String()
        msg.data = self.fleet_state
        self.fleet_state_pub.publish(msg)
    
    def get_fleet_config(self) -> FleetConfig:
        """Get current fleet configuration"""
        return self.fleet_config
    
    def get_robot_spawn_info(self, robot_id: str) -> Dict:
        """Get spawn info for a specific robot"""
        if self.spawner:
            return self.spawner.get_robot_info(robot_id)
        return None
    
    def get_all_spawn_info(self) -> Dict:
        """Get spawn info for all robots"""
        if self.spawner:
            return self.spawner.get_all_robots()
        return {}


def main(args=None):
    rclpy.init(args=args)
    
    node = FleetManagerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()







