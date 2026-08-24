#!/usr/bin/env python3
"""
Multi-Robot Coordinator Node

This node coordinates the pick and place operations between 3 robots
on the assembly line. It manages the state machine for each robot
and synchronizes their actions based on sensor feedback.

State Machine:
    IDLE -> BOX_DETECTED -> MOVING_TO_PICK -> PICKING -> MOVING_TO_PLACE -> PLACING -> IDLE

Topics:
    Subscribed:
        /station{N}/break_beam (sensor_msgs/Range)
        /station{N}/proximity (sensor_msgs/Range)
    
    Published:
        /coordinator/state (std_msgs/String)
    
    Action Clients:
        /xarm{N}/xarm{N}_traj_controller/follow_joint_trajectory
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, Bool
from sensor_msgs.msg import Range, JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from conveyorbelt_msgs.srv import ConveyorBeltControl

from enum import Enum
import yaml


class RobotState(Enum):
    """State machine states for each robot"""
    IDLE = "IDLE"
    BOX_DETECTED = "BOX_DETECTED"
    MOVING_TO_PICK = "MOVING_TO_PICK"
    PICKING = "PICKING"
    HOLDING = "HOLDING"
    MOVING_TO_PLACE = "MOVING_TO_PLACE"
    PLACING = "PLACING"
    RETURNING = "RETURNING"


class Robot:
    """Represents a single robot in the assembly line"""
    def __init__(self, name: str, prefix: str, station_id: int, role: str):
        self.name = name
        self.prefix = prefix
        self.station_id = station_id
        self.role = role
        self.state = RobotState.IDLE
        self.box_detected = False
        self.current_joints = []


class CoordinatorNode(Node):
    """Main coordinator node for multi-robot assembly line"""
    
    def __init__(self):
        super().__init__('coordinator_node')
        
        self.get_logger().info('Initializing Multi-Robot Coordinator...')
        
        # Callback group for concurrent execution
        self.callback_group = ReentrantCallbackGroup()
        
        # Robot configurations
        self.robots = {
            'xarm1': Robot('xarm1', 'xarm1_', 1, 'pick'),
            'xarm2': Robot('xarm2', 'xarm2_', 2, 'transfer'),
            'xarm3': Robot('xarm3', 'xarm3_', 3, 'place'),
        }
        
        # State publisher
        self.state_pub = self.create_publisher(
            String, '/coordinator/state', 10
        )
        
        # Break beam sensor subscriptions
        self.break_beam_subs = {}
        for robot in self.robots.values():
            topic = f'/station{robot.station_id}/break_beam'
            self.break_beam_subs[robot.name] = self.create_subscription(
                Range, topic,
                lambda msg, r=robot: self.break_beam_callback(msg, r),
                10, callback_group=self.callback_group
            )
        
        # Joint state subscriptions
        self.joint_state_subs = {}
        for robot in self.robots.values():
            topic = f'/{robot.name}/joint_states'
            self.joint_state_subs[robot.name] = self.create_subscription(
                JointState, topic,
                lambda msg, r=robot: self.joint_state_callback(msg, r),
                10, callback_group=self.callback_group
            )
        
        # Trajectory action clients
        self.trajectory_clients = {}
        for robot in self.robots.values():
            action_name = f'/{robot.name}/{robot.prefix}xarm5_traj_controller/follow_joint_trajectory'
            self.trajectory_clients[robot.name] = ActionClient(
                self, FollowJointTrajectory, action_name,
                callback_group=self.callback_group
            )
        
        # Conveyor control service client
        self.conveyor_client = self.create_client(
            ConveyorBeltControl, '/conveyor/CONVEYORPOWER'
        )
        
        # Predefined positions (joint angles in radians)
        self.positions = {
            'home': [0.0, 0.0, 0.0, 0.0, 0.0],
            'pick_ready': [0.0, -0.5, 0.8, 0.0, 0.0],
            'pick_down': [0.0, -0.3, 1.0, 0.0, 0.0],
            'place_ready': [1.57, -0.5, 0.8, 0.0, 0.0],
            'place_down': [1.57, -0.3, 1.0, 0.0, 0.0],
        }
        
        # Detection threshold (metres)
        self.detection_threshold = 0.4
        
        # Main control loop timer (10 Hz)
        self.control_timer = self.create_timer(
            0.1, self.control_loop, callback_group=self.callback_group
        )
        
        # State publishing timer (1 Hz)
        self.state_timer = self.create_timer(
            1.0, self.publish_state, callback_group=self.callback_group
        )
        
        self.get_logger().info('Coordinator initialized. Waiting for robots...')
    
    def break_beam_callback(self, msg: Range, robot: Robot):
        """Handle break beam sensor data"""
        # If range is less than threshold, beam is broken (object detected)
        robot.box_detected = msg.range < self.detection_threshold
        
        if robot.box_detected and robot.state == RobotState.IDLE:
            self.get_logger().info(f'Box detected at station {robot.station_id} ({robot.name})')
            robot.state = RobotState.BOX_DETECTED
    
    def joint_state_callback(self, msg: JointState, robot: Robot):
        """Handle joint state updates"""
        robot.current_joints = list(msg.position)
    
    def control_loop(self):
        """Main control loop - executes state machine for each robot"""
        for robot in self.robots.values():
            self.execute_state_machine(robot)
    
    def execute_state_machine(self, robot: Robot):
        """Execute state machine for a single robot"""
        
        if robot.state == RobotState.IDLE:
            # Waiting for box detection
            pass
            
        elif robot.state == RobotState.BOX_DETECTED:
            # Box detected, move to pick position
            self.get_logger().info(f'{robot.name}: Moving to pick position')
            self.send_trajectory(robot, self.positions['pick_ready'])
            robot.state = RobotState.MOVING_TO_PICK
            
        elif robot.state == RobotState.MOVING_TO_PICK:
            # Wait for movement to complete
            # In a real implementation, check action result
            pass
            
        elif robot.state == RobotState.PICKING:
            # Execute pick action (close gripper)
            self.get_logger().info(f'{robot.name}: Picking box')
            # In real implementation, call gripper action
            robot.state = RobotState.HOLDING
            
        elif robot.state == RobotState.HOLDING:
            # Move to place position
            self.get_logger().info(f'{robot.name}: Moving to place position')
            self.send_trajectory(robot, self.positions['place_ready'])
            robot.state = RobotState.MOVING_TO_PLACE
            
        elif robot.state == RobotState.MOVING_TO_PLACE:
            # Wait for movement to complete
            pass
            
        elif robot.state == RobotState.PLACING:
            # Execute place action (open gripper)
            self.get_logger().info(f'{robot.name}: Placing box')
            robot.state = RobotState.RETURNING
            
        elif robot.state == RobotState.RETURNING:
            # Return to home position
            self.send_trajectory(robot, self.positions['home'])
            robot.state = RobotState.IDLE
    
    def send_trajectory(self, robot: Robot, target_joints: list):
        """Send a trajectory command to a robot"""
        if robot.name not in self.trajectory_clients:
            self.get_logger().warn(f'No trajectory client for {robot.name}')
            return
        
        client = self.trajectory_clients[robot.name]
        
        if not client.wait_for_server(timeout_sec=1.0):
            self.get_logger().warn(f'Trajectory server not available for {robot.name}')
            return
        
        # Create trajectory goal
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = [
            f'{robot.prefix}joint1',
            f'{robot.prefix}joint2',
            f'{robot.prefix}joint3',
            f'{robot.prefix}joint4',
            f'{robot.prefix}joint5',
        ]
        
        point = JointTrajectoryPoint()
        point.positions = target_joints
        point.time_from_start.sec = 2
        point.time_from_start.nanosec = 0
        
        goal.trajectory.points.append(point)
        
        # Send goal asynchronously
        client.send_goal_async(goal)
    
    def set_conveyor_power(self, power: float):
        """Set conveyor belt power (0-100)"""
        if not self.conveyor_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Conveyor service not available')
            return
        
        request = ConveyorBeltControl.Request()
        request.power = power
        self.conveyor_client.call_async(request)
    
    def publish_state(self):
        """Publish current coordinator state"""
        states = {robot.name: robot.state.value for robot in self.robots.values()}
        msg = String()
        msg.data = str(states)
        self.state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CoordinatorNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

