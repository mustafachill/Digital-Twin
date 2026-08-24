#!/usr/bin/env python3
"""
Box Spawner Node

Spawns payload boxes on the conveyor belt at regular intervals.
Uses Gazebo's spawn_entity service.

Services:
    /spawn_entity (gazebo_msgs/SpawnEntity)
    
Parameters:
    spawn_interval (float): Time between spawns in seconds (default: 10.0)
    spawn_x (float): X position for spawning (default: 0.0)
    spawn_y (float): Y position for spawning (default: -1.8)
    spawn_z (float): Z position for spawning (default: 0.85)
"""

import rclpy
from rclpy.node import Node
from gazebo_msgs.srv import SpawnEntity
from std_msgs.msg import String
import os


class BoxSpawner(Node):
    """Spawn boxes on the conveyor belt"""
    
    def __init__(self):
        super().__init__('box_spawner')
        
        self.get_logger().info('Initializing Box Spawner...')
        
        # Declare parameters
        self.declare_parameter('spawn_interval', 10.0)
        self.declare_parameter('spawn_x', 0.0)
        self.declare_parameter('spawn_y', -1.8)
        self.declare_parameter('spawn_z', 0.85)
        self.declare_parameter('auto_spawn', False)
        
        # Get parameters
        self.spawn_interval = self.get_parameter('spawn_interval').value
        self.spawn_x = self.get_parameter('spawn_x').value
        self.spawn_y = self.get_parameter('spawn_y').value
        self.spawn_z = self.get_parameter('spawn_z').value
        self.auto_spawn = self.get_parameter('auto_spawn').value
        
        # Box counter
        self.box_count = 0
        
        # Spawn service client
        self.spawn_client = self.create_client(SpawnEntity, '/spawn_entity')
        
        # Box SDF template
        self.box_sdf = '''<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="payload_box_{count}">
    <static>false</static>
    <link name="box_link">
      <pose>0 0 0.05 0 0 0</pose>
      <inertial>
        <mass>0.5</mass>
        <inertia>
          <ixx>0.000833</ixx><ixy>0</ixy><ixz>0</ixz>
          <iyy>0.000833</iyy><iyz>0</iyz>
          <izz>0.000833</izz>
        </inertia>
      </inertial>
      <collision name="collision">
        <geometry><box><size>0.1 0.1 0.1</size></box></geometry>
        <surface>
          <friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction>
        </surface>
      </collision>
      <visual name="visual">
        <geometry><box><size>0.1 0.1 0.1</size></box></geometry>
        <material>
          <ambient>0.8 0.2 0.1 1</ambient>
          <diffuse>0.8 0.2 0.1 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>'''
        
        # Spawn trigger subscription
        self.create_subscription(
            String, '/box_spawner/trigger',
            self.trigger_callback, 10
        )
        
        # Auto spawn timer
        if self.auto_spawn:
            self.spawn_timer = self.create_timer(
                self.spawn_interval, self.spawn_box
            )
        
        self.get_logger().info(f'Box Spawner initialized. Auto spawn: {self.auto_spawn}')
    
    def trigger_callback(self, msg: String):
        """Handle manual spawn trigger"""
        self.spawn_box()
    
    def spawn_box(self):
        """Spawn a new box on the conveyor"""
        if not self.spawn_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Spawn service not available')
            return
        
        self.box_count += 1
        box_name = f'payload_box_{self.box_count}'
        
        request = SpawnEntity.Request()
        request.name = box_name
        request.xml = self.box_sdf.format(count=self.box_count)
        request.robot_namespace = ''
        request.initial_pose.position.x = self.spawn_x
        request.initial_pose.position.y = self.spawn_y
        request.initial_pose.position.z = self.spawn_z
        request.initial_pose.orientation.w = 1.0
        request.reference_frame = 'world'
        
        future = self.spawn_client.call_async(request)
        future.add_done_callback(
            lambda f: self.get_logger().info(f'Spawned {box_name}')
        )


def main(args=None):
    rclpy.init(args=args)
    node = BoxSpawner()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

