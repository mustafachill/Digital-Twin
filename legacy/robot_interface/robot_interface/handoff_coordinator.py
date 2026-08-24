#!/usr/bin/env python3
"""
Handoff Coordinator

Manages handoff protocol between robots.
Ensures safe and synchronized object transfers.
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import String, Bool
from geometry_msgs.msg import Point

import yaml
import uuid
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import time


class HandoffState(Enum):
    """Handoff transaction states"""
    PENDING = "PENDING"
    NEGOTIATING = "NEGOTIATING"
    ACCEPTED = "ACCEPTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


@dataclass
class HandoffTransaction:
    """Represents a single handoff transaction"""
    handoff_id: str
    source_robot: str
    target_robot: str
    state: HandoffState
    created_at: float
    object_type: str = "box"
    proposed_position: List[float] = None
    accepted_position: List[float] = None
    timeout: float = 10.0
    error_message: str = ""
    
    def is_timed_out(self) -> bool:
        return time.time() - self.created_at > self.timeout
    
    def to_dict(self) -> Dict:
        return {
            'handoff_id': self.handoff_id,
            'source': self.source_robot,
            'target': self.target_robot,
            'state': self.state.value,
            'created_at': self.created_at,
            'object_type': self.object_type,
        }


class HandoffCoordinator(Node):
    """
    Coordinates handoff operations between robots
    
    This can run as a standalone coordinator or as part of each robot node.
    Handles the handoff protocol:
    1. Source robot signals ready_to_give
    2. Target robot signals ready_to_receive
    3. Coordinator creates handoff transaction
    4. Both robots execute their parts
    5. Transaction completes or fails
    """
    
    def __init__(self):
        super().__init__('handoff_coordinator')
        
        self.callback_group = ReentrantCallbackGroup()
        
        # Declare parameters
        self.declare_parameter('config_file', '')
        self.declare_parameter('robot_pairs', ['robot_1:robot_2', 'robot_2:robot_3'])
        
        # Get parameters
        config_file = self.get_parameter('config_file').get_parameter_value().string_value
        robot_pairs = self.get_parameter('robot_pairs').get_parameter_value().string_array_value
        
        # Parse robot pairs (source:target)
        self.handoff_pairs: List[tuple] = []
        for pair in robot_pairs:
            parts = pair.split(':')
            if len(parts) == 2:
                self.handoff_pairs.append((parts[0], parts[1]))
        
        self.get_logger().info(f"Handoff pairs: {self.handoff_pairs}")
        
        # QoS
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )
        
        # Active transactions
        self.transactions: Dict[str, HandoffTransaction] = {}
        
        # Robot states
        self.robot_ready_to_give: Dict[str, bool] = {}
        self.robot_ready_to_receive: Dict[str, bool] = {}
        
        # Subscribe to all robot handoff signals
        self.ready_give_subs = {}
        self.ready_receive_subs = {}
        
        for source, target in self.handoff_pairs:
            # Source ready to give
            self.ready_give_subs[source] = self.create_subscription(
                Bool,
                f'/{source}/handoff/ready_to_give',
                lambda msg, r=source: self._on_ready_to_give(r, msg),
                reliable_qos,
                callback_group=self.callback_group
            )
            self.robot_ready_to_give[source] = False
            
            # Target ready to receive
            self.ready_receive_subs[target] = self.create_subscription(
                Bool,
                f'/{target}/handoff/ready_to_receive',
                lambda msg, r=target: self._on_ready_to_receive(r, msg),
                reliable_qos,
                callback_group=self.callback_group
            )
            self.robot_ready_to_receive[target] = False
        
        # Publishers for handoff commands
        self.handoff_command_pubs: Dict[str, any] = {}
        for source, target in self.handoff_pairs:
            self.handoff_command_pubs[source] = self.create_publisher(
                String, f'/{source}/handoff/execute', reliable_qos
            )
            self.handoff_command_pubs[target] = self.create_publisher(
                String, f'/{target}/handoff/execute', reliable_qos
            )
        
        # Status publisher
        self.status_pub = self.create_publisher(
            String, '/handoff_coordinator/status', 10
        )
        
        # Timers
        self.check_timer = self.create_timer(
            0.5, self._check_handoff_opportunities, callback_group=self.callback_group
        )
        
        self.cleanup_timer = self.create_timer(
            5.0, self._cleanup_transactions, callback_group=self.callback_group
        )
        
        self.status_timer = self.create_timer(
            1.0, self._publish_status, callback_group=self.callback_group
        )
        
        self.get_logger().info("Handoff Coordinator started")
    
    def _on_ready_to_give(self, robot_id: str, msg: Bool):
        """Called when a robot signals ready to give"""
        old_value = self.robot_ready_to_give.get(robot_id, False)
        self.robot_ready_to_give[robot_id] = msg.data
        
        if msg.data and not old_value:
            self.get_logger().debug(f"Robot {robot_id} ready to give")
    
    def _on_ready_to_receive(self, robot_id: str, msg: Bool):
        """Called when a robot signals ready to receive"""
        old_value = self.robot_ready_to_receive.get(robot_id, False)
        self.robot_ready_to_receive[robot_id] = msg.data
        
        if msg.data and not old_value:
            self.get_logger().debug(f"Robot {robot_id} ready to receive")
    
    def _check_handoff_opportunities(self):
        """Check if any robot pairs are ready for handoff"""
        for source, target in self.handoff_pairs:
            # Skip if transaction already in progress
            if self._has_active_transaction(source, target):
                continue
            
            # Check if both robots are ready
            source_ready = self.robot_ready_to_give.get(source, False)
            target_ready = self.robot_ready_to_receive.get(target, False)
            
            if source_ready and target_ready:
                self._initiate_handoff(source, target)
    
    def _has_active_transaction(self, source: str, target: str) -> bool:
        """Check if there's an active transaction between these robots"""
        for tx in self.transactions.values():
            if tx.source_robot == source and tx.target_robot == target:
                if tx.state in [HandoffState.PENDING, HandoffState.NEGOTIATING, 
                               HandoffState.ACCEPTED, HandoffState.EXECUTING]:
                    return True
        return False
    
    def _initiate_handoff(self, source: str, target: str):
        """Initiate a handoff transaction"""
        handoff_id = str(uuid.uuid4())[:8]
        
        transaction = HandoffTransaction(
            handoff_id=handoff_id,
            source_robot=source,
            target_robot=target,
            state=HandoffState.NEGOTIATING,
            created_at=time.time(),
            timeout=10.0
        )
        
        self.transactions[handoff_id] = transaction
        
        self.get_logger().info(f"Initiated handoff {handoff_id}: {source} -> {target}")
        
        # Send execute commands to both robots
        self._send_handoff_command(source, {
            'handoff_id': handoff_id,
            'action': 'give',
            'partner': target,
        })
        
        self._send_handoff_command(target, {
            'handoff_id': handoff_id,
            'action': 'receive',
            'partner': source,
        })
        
        transaction.state = HandoffState.EXECUTING
    
    def _send_handoff_command(self, robot_id: str, command: Dict):
        """Send handoff command to a robot"""
        if robot_id in self.handoff_command_pubs:
            msg = String()
            msg.data = str(command)
            self.handoff_command_pubs[robot_id].publish(msg)
    
    def _cleanup_transactions(self):
        """Clean up timed out or completed transactions"""
        to_remove = []
        
        for handoff_id, tx in self.transactions.items():
            if tx.is_timed_out() and tx.state not in [HandoffState.COMPLETED, HandoffState.FAILED]:
                tx.state = HandoffState.TIMEOUT
                tx.error_message = "Transaction timed out"
                self.get_logger().warn(f"Handoff {handoff_id} timed out")
            
            # Remove completed/failed transactions older than 60 seconds
            if tx.state in [HandoffState.COMPLETED, HandoffState.FAILED, HandoffState.TIMEOUT]:
                if time.time() - tx.created_at > 60.0:
                    to_remove.append(handoff_id)
        
        for handoff_id in to_remove:
            del self.transactions[handoff_id]
    
    def complete_handoff(self, handoff_id: str, success: bool, error_message: str = ""):
        """Mark a handoff as completed"""
        if handoff_id in self.transactions:
            tx = self.transactions[handoff_id]
            if success:
                tx.state = HandoffState.COMPLETED
                self.get_logger().info(f"Handoff {handoff_id} completed successfully")
            else:
                tx.state = HandoffState.FAILED
                tx.error_message = error_message
                self.get_logger().warn(f"Handoff {handoff_id} failed: {error_message}")
    
    def _publish_status(self):
        """Publish coordinator status"""
        status = {
            'active_transactions': len([t for t in self.transactions.values() 
                                       if t.state in [HandoffState.NEGOTIATING, 
                                                     HandoffState.EXECUTING]]),
            'total_transactions': len(self.transactions),
            'robots_ready_to_give': [r for r, v in self.robot_ready_to_give.items() if v],
            'robots_ready_to_receive': [r for r, v in self.robot_ready_to_receive.items() if v],
        }
        
        msg = String()
        msg.data = str(status)
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    
    node = HandoffCoordinator()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()







