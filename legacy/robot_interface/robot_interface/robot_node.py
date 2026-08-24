#!/usr/bin/env python3
"""
Robot Node - Independent Robot Interface

Each robot runs its own instance of this node.
Handles:
- State machine management
- Neighbor communication (pub/sub)
- Sensor monitoring
- Handoff coordination
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import String, Bool
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Point
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

import yaml
import os
from typing import Dict, Optional, List
import uuid

from .state_machine import RobotStateMachine, RobotState, RobotSubState


class RobotNode(Node):
    """
    Independent Robot Node
    
    Each robot in the fleet runs its own RobotNode.
    Communication with other robots is via pub/sub.
    """
    
    def __init__(self):
        # Get robot_id from parameter or use default
        super().__init__('robot_node')
        
        self.callback_group = ReentrantCallbackGroup()
        
        # Declare parameters
        self.declare_parameter('robot_id', 'robot_1')
        self.declare_parameter('robot_type', 'xarm5')
        self.declare_parameter('role', 'transfer')
        self.declare_parameter('upstream_neighbor', '')
        self.declare_parameter('downstream_neighbor', '')
        self.declare_parameter('sensor_topic', '')
        self.declare_parameter('config_file', '')
        
        # Get parameters
        self.robot_id = self.get_parameter('robot_id').get_parameter_value().string_value
        self.robot_type = self.get_parameter('robot_type').get_parameter_value().string_value
        self.role = self.get_parameter('role').get_parameter_value().string_value
        self.upstream_neighbor = self.get_parameter('upstream_neighbor').get_parameter_value().string_value
        self.downstream_neighbor = self.get_parameter('downstream_neighbor').get_parameter_value().string_value
        self.sensor_topic = self.get_parameter('sensor_topic').get_parameter_value().string_value
        config_file = self.get_parameter('config_file').get_parameter_value().string_value
        
        # Pick and place positions (default values)
        self.pick_position = [0.0, 0.3, 0.05]
        self.place_position = [0.3, 0.0, 0.15]
        
        # Load additional config if provided
        if config_file and os.path.exists(config_file):
            self._load_config(config_file)
        
        # Initialize state machine
        self.state_machine = RobotStateMachine(self.robot_id, self.role)
        self.state_machine.set_on_state_change(self._on_state_change)
        self.state_machine.set_on_error(self._on_error)
        
        # QoS profiles
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )
        
        # ==========================================
        # Publishers
        # ==========================================
        
        # Status publisher (for monitoring and neighbor discovery)
        self.status_pub = self.create_publisher(
            String, f'/{self.robot_id}/status', reliable_qos
        )
        
        # Ready to receive signal (downstream listens to this)
        self.ready_receive_pub = self.create_publisher(
            Bool, f'/{self.robot_id}/handoff/ready_to_receive', reliable_qos
        )
        
        # Ready to give signal (upstream listens to this)
        self.ready_give_pub = self.create_publisher(
            Bool, f'/{self.robot_id}/handoff/ready_to_give', reliable_qos
        )
        
        # Handoff request publisher
        self.handoff_request_pub = self.create_publisher(
            String, f'/{self.robot_id}/handoff/request', reliable_qos
        )
        
        # Trajectory command publisher
        self.trajectory_pub = self.create_publisher(
            JointTrajectory,
            f'/{self.robot_id}/{self.robot_id}_xarm5_traj_controller/joint_trajectory',
            10
        )
        
        # ==========================================
        # Subscribers
        # ==========================================
        
        # Listen to upstream robot's ready_to_give
        if self.upstream_neighbor and self.upstream_neighbor not in ['conveyor_entry', 'none']:
            self.upstream_ready_sub = self.create_subscription(
                Bool,
                f'/{self.upstream_neighbor}/handoff/ready_to_give',
                self._upstream_ready_callback,
                reliable_qos,
                callback_group=self.callback_group
            )
            self.get_logger().info(f"Listening to upstream: {self.upstream_neighbor}")
        
        # Listen to downstream robot's ready_to_receive
        if self.downstream_neighbor and self.downstream_neighbor not in ['conveyor_exit', 'none']:
            self.downstream_ready_sub = self.create_subscription(
                Bool,
                f'/{self.downstream_neighbor}/handoff/ready_to_receive',
                self._downstream_ready_callback,
                reliable_qos,
                callback_group=self.callback_group
            )
            self.get_logger().info(f"Listening to downstream: {self.downstream_neighbor}")
        
        # Sensor subscription (if provided)
        if self.sensor_topic:
            self.sensor_sub = self.create_subscription(
                Bool,
                self.sensor_topic,
                self._sensor_callback,
                10,
                callback_group=self.callback_group
            )
        
        # Joint state subscription
        self.joint_state_sub = self.create_subscription(
            JointState,
            f'/{self.robot_id}/joint_states',
            self._joint_state_callback,
            10,
            callback_group=self.callback_group
        )
        
        # ==========================================
        # State variables
        # ==========================================
        
        self.current_joint_positions: List[float] = []
        self.upstream_ready = False
        self.downstream_ready = False
        self.sensor_triggered = False
        
        # ==========================================
        # Timers
        # ==========================================
        
        self.status_timer = self.create_timer(
            0.5, self._publish_status, callback_group=self.callback_group
        )
        
        self.handoff_timer = self.create_timer(
            0.1, self._publish_handoff_signals, callback_group=self.callback_group
        )
        
        self.get_logger().info(f"Robot Node started: {self.robot_id}")
        self.get_logger().info(f"  Role: {self.role}")
        self.get_logger().info(f"  Upstream: {self.upstream_neighbor}")
        self.get_logger().info(f"  Downstream: {self.downstream_neighbor}")
    
    def _load_config(self, config_file: str):
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            robot_config = config.get(self.robot_id, {})
            self.pick_position = robot_config.get('pick_position', self.pick_position)
            self.place_position = robot_config.get('place_position', self.place_position)
            
        except Exception as e:
            self.get_logger().warn(f"Could not load config: {e}")
    
    def _on_state_change(self, old_state: RobotState, new_state: RobotState):
        """Callback when state changes"""
        self.get_logger().info(f"[{self.robot_id}] State: {old_state.value} -> {new_state.value}")
        
        # Trigger actions based on new state
        if new_state == RobotState.PICKING:
            self._execute_pick()
        elif new_state == RobotState.PLACING:
            self._execute_place()
    
    def _on_error(self, message: str):
        """Callback when error occurs"""
        self.get_logger().error(f"[{self.robot_id}] Error: {message}")
    
    def _upstream_ready_callback(self, msg: Bool):
        """Called when upstream robot signals ready to give"""
        self.upstream_ready = msg.data
        
        if msg.data and self.state_machine.is_ready_to_receive:
            self.get_logger().info(f"Upstream {self.upstream_neighbor} ready to give")
            # Signal that we're ready to receive
            if self.state_machine.state == RobotState.IDLE:
                self.state_machine.trigger('handoff_request')
    
    def _downstream_ready_callback(self, msg: Bool):
        """Called when downstream robot signals ready to receive"""
        self.downstream_ready = msg.data
        
        if msg.data and self.state_machine.is_ready_to_give:
            self.get_logger().info(f"Downstream {self.downstream_neighbor} ready to receive")
            self.state_machine.trigger('downstream_ready')
    
    def _sensor_callback(self, msg: Bool):
        """Called when sensor is triggered"""
        old_value = self.sensor_triggered
        self.sensor_triggered = msg.data
        
        if msg.data and not old_value:
            self.get_logger().info("Sensor triggered - object detected")
            if self.state_machine.state == RobotState.IDLE:
                self.state_machine.trigger('object_detected')
    
    def _joint_state_callback(self, msg: JointState):
        """Called when joint states are updated"""
        self.current_joint_positions = list(msg.position)
    
    def _publish_status(self):
        """Publish robot status"""
        status = self.state_machine.get_status_dict()
        status['upstream_neighbor'] = self.upstream_neighbor
        status['downstream_neighbor'] = self.downstream_neighbor
        
        msg = String()
        msg.data = str(status)
        self.status_pub.publish(msg)
    
    def _publish_handoff_signals(self):
        """Publish handoff ready signals"""
        # Ready to receive
        receive_msg = Bool()
        receive_msg.data = self.state_machine.is_ready_to_receive
        self.ready_receive_pub.publish(receive_msg)
        
        # Ready to give
        give_msg = Bool()
        give_msg.data = self.state_machine.is_ready_to_give
        self.ready_give_pub.publish(give_msg)
    
    def _execute_pick(self):
        """Execute pick operation"""
        self.get_logger().info(f"[{self.robot_id}] Executing PICK")
        self.state_machine.set_sub_state(RobotSubState.MOVING_TO_PICK)
        
        # In a real implementation, this would:
        # 1. Move to pick position
        # 2. Close gripper
        # 3. Signal completion
        
        # For now, simulate with a timer
        self.create_timer(2.0, self._pick_complete_callback, callback_group=self.callback_group)
    
    def _pick_complete_callback(self):
        """Called when pick is complete"""
        self.state_machine.set_sub_state(RobotSubState.CLOSING_GRIPPER)
        self.get_logger().info(f"[{self.robot_id}] Pick complete")
        self.state_machine.trigger('pick_complete')
        self.destroy_timer(self._pick_complete_callback)
    
    def _execute_place(self):
        """Execute place operation"""
        self.get_logger().info(f"[{self.robot_id}] Executing PLACE")
        self.state_machine.set_sub_state(RobotSubState.MOVING_TO_PLACE)
        
        # For now, simulate with a timer
        self.create_timer(2.0, self._place_complete_callback, callback_group=self.callback_group)
    
    def _place_complete_callback(self):
        """Called when place is complete"""
        self.state_machine.set_sub_state(RobotSubState.OPENING_GRIPPER)
        self.get_logger().info(f"[{self.robot_id}] Place complete")
        self.state_machine.trigger('place_complete')
        self.destroy_timer(self._place_complete_callback)
    
    def send_trajectory(self, joint_positions: List[float], duration: float = 2.0):
        """
        Send a trajectory command to the robot
        
        Args:
            joint_positions: Target joint positions
            duration: Time to reach the target
        """
        msg = JointTrajectory()
        msg.header.stamp = self.get_clock().now().to_msg()
        
        # Joint names with robot prefix
        dof = 5  # xArm5
        msg.joint_names = [f'{self.robot_id}_joint{i+1}' for i in range(dof)]
        
        point = JointTrajectoryPoint()
        point.positions = joint_positions
        point.time_from_start = Duration(sec=int(duration), nanosec=int((duration % 1) * 1e9))
        
        msg.points = [point]
        
        self.trajectory_pub.publish(msg)
        self.get_logger().info(f"Sent trajectory to {len(joint_positions)} joints")


def main(args=None):
    rclpy.init(args=args)
    
    node = RobotNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

