#!/usr/bin/env python3
"""
Sensor Monitor Node

Monitors all sensors in the assembly line and provides
consolidated status information.

Topics:
    Subscribed:
        /station{N}/break_beam (sensor_msgs/Range)
        /station{N}/proximity (sensor_msgs/Range)
        /conveyor/CONVEYORSTATE (conveyorbelt_msgs/ConveyorBeltState)
    
    Published:
        /assembly_line/sensor_status (std_msgs/String)
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Range
from conveyorbelt_msgs.msg import ConveyorBeltState
import json


class SensorMonitor(Node):
    """Monitor all assembly line sensors"""
    
    def __init__(self):
        super().__init__('sensor_monitor')
        
        self.get_logger().info('Initializing Sensor Monitor...')
        
        # Sensor data storage
        self.sensor_data = {
            'stations': {
                1: {'break_beam': None, 'proximity': None, 'box_detected': False},
                2: {'break_beam': None, 'proximity': None, 'box_detected': False},
                3: {'break_beam': None, 'proximity': None, 'box_detected': False},
            },
            'conveyor': {
                'enabled': False,
                'power': 0.0,
            }
        }
        
        # Detection threshold
        self.detection_threshold = 0.4  # metres
        
        # Subscribe to break beam sensors
        for station_id in [1, 2, 3]:
            self.create_subscription(
                Range,
                f'/station{station_id}/break_beam',
                lambda msg, sid=station_id: self.break_beam_callback(msg, sid),
                10
            )
            self.create_subscription(
                Range,
                f'/station{station_id}/proximity',
                lambda msg, sid=station_id: self.proximity_callback(msg, sid),
                10
            )
        
        # Subscribe to conveyor state
        self.create_subscription(
            ConveyorBeltState,
            '/conveyor/CONVEYORSTATE',
            self.conveyor_callback,
            10
        )
        
        # Status publisher
        self.status_pub = self.create_publisher(
            String, '/assembly_line/sensor_status', 10
        )
        
        # Publish timer (5 Hz)
        self.create_timer(0.2, self.publish_status)
        
        self.get_logger().info('Sensor Monitor initialized')
    
    def break_beam_callback(self, msg: Range, station_id: int):
        """Handle break beam sensor data"""
        self.sensor_data['stations'][station_id]['break_beam'] = msg.range
        self.sensor_data['stations'][station_id]['box_detected'] = \
            msg.range < self.detection_threshold
    
    def proximity_callback(self, msg: Range, station_id: int):
        """Handle proximity sensor data"""
        self.sensor_data['stations'][station_id]['proximity'] = msg.range
    
    def conveyor_callback(self, msg: ConveyorBeltState):
        """Handle conveyor state data"""
        self.sensor_data['conveyor']['enabled'] = msg.enabled
        self.sensor_data['conveyor']['power'] = msg.power
    
    def publish_status(self):
        """Publish consolidated sensor status"""
        msg = String()
        msg.data = json.dumps(self.sensor_data)
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SensorMonitor()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

