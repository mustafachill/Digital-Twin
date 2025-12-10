#!/bin/bash
# Conveyor Belt Startup Script
# Starts all 3 conveyor belts with proper direction for zigzag flow
# Belt 2 flows in reverse direction (negative power)

set -e

# Source ROS2 environment
cd "$(dirname "$0")/.."
source /opt/ros/humble/setup.bash
source install/setup.bash

echo "Starting conveyor belts..."

# Belt 1: Flows north (+Y direction), power=0.3
echo "  - Belt 1: North flow (power=0.3)"
ros2 service call /conveyor_belt_1/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.3}" &
PID1=$!

# Belt 2: Flows south (-Y direction), power=-0.3 for reverse
echo "  - Belt 2: South flow (power=-0.3) [REVERSE]"
ros2 service call /conveyor_belt_2/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: -0.3}" &
PID2=$!

# Belt 3: Flows north (+Y direction), power=0.3
echo "  - Belt 3: North flow (power=0.3)"
ros2 service call /conveyor_belt_3/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.3}" &
PID3=$!

# Wait for all service calls to complete
wait $PID1
wait $PID2
wait $PID3

echo "✅ All conveyors started successfully!"
echo ""
echo "Conveyor states:"
ros2 topic echo /conveyor_belt_1/CONVEYORSTATE --once 2>/dev/null &
ros2 topic echo /conveyor_belt_2/CONVEYORSTATE --once 2>/dev/null &
ros2 topic echo /conveyor_belt_3/CONVEYORSTATE --once 2>/dev/null &
wait

echo ""
echo "System ready for operation!"

