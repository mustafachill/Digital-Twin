# Digital Twin - Multi-Robot Assembly Line

A ROS 2 Humble digital twin project for a multi-robot pick & place assembly line, featuring xArm 5 robots, conveyor belt, and sensor integration.

## Overview

This project implements a digital twin architecture for an industrial assembly line:

```
[BOX] --> [CONVEYOR] --> [Robot 1] --> [CONVEYOR] --> [Robot 2] --> [CONVEYOR] --> [Robot 3] --> [EXIT]
                              |              |              |
                         [Sensors]      [Sensors]      [Sensors]
```

### Key Features

- **3x xArm 5 Robots**: UFACTORY 5-DOF robot arms with grippers
- **Conveyor Belt**: ROS2-controlled conveyor with speed control
- **Sensor Network**: Break beam sensors, proximity sensors, cameras
- **Digital Twin Sync**: Same ROS2 interfaces for simulation and real hardware
- **MoveIt2 Integration**: Interactive motion planning

## Quick Start

### Prerequisites

```bash
# ROS2 Humble packages
sudo apt install ros-humble-moveit ros-humble-gazebo-ros2-control \
    ros-humble-controller-manager ros-humble-joint-trajectory-controller \
    ros-humble-ros2-controllers ros-humble-xacro ros-humble-rviz2
```

### Build

```bash
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### Launch

```bash
# Main Digital Twin simulation
ros2 launch assembly_line_bringup digital_twin.launch.py

# Alternative: Single robot test
ros2 launch assembly_line_bringup single_robot_test.launch.py

# xArm official launch with MoveIt
ros2 launch xarm_moveit_config xarm5_moveit_gazebo.launch.py add_gripper:=true
```

## Package Structure

| Package | Description |
|---------|-------------|
| `assembly_line_bringup` | **Main launch package** - Digital Twin entry point |
| `multi_robot_coordinator` | Robot coordination and state machine |
| `conveyor_system` | Conveyor belt models and configuration |
| `assembly_line_sensors` | Break beam and proximity sensor models |
| `xarm_ros2` | UFACTORY xArm ROS2 packages |
| `ifra_conveyor_belt` | Conveyor belt Gazebo plugin |
| `digital_twin_environment` | Custom lab environment models |

## Robot Control

### Conveyor Belt

```bash
# Start conveyor (50% power)
ros2 service call /CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 50.0}"

# Stop conveyor
ros2 service call /CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.0}"
```

### xArm 5 Robot

```bash
# Send trajectory command
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
    control_msgs/action/FollowJointTrajectory \
    "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], \
    points: [{positions: [0.5, -0.5, 0.8, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

### MoveIt2 Interactive Control

Use the RViz MoveIt panel to:
- Drag the interactive marker to set goal pose
- Click "Plan & Execute" to move the robot

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ROS 2 Control Layer                             │
│  ┌────────────────┐  ┌─────────────────────┐  ┌────────────────────┐   │
│  │ JointState     │  │ JointTrajectory     │  │ Gripper            │   │
│  │ Broadcaster    │  │ Controller          │  │ Controller         │   │
│  └────────────────┘  └─────────────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────────┐
│  Gazebo Sim     │      │  Gazebo Sim     │      │  Physical xArm 5    │
│  (Robot 1)      │      │  (Robot 2,3)    │      │  (Future)           │
└─────────────────┘      └─────────────────┘      └─────────────────────┘
```

## Topics & Services

| Topic/Service | Type | Description |
|---------------|------|-------------|
| `/joint_states` | sensor_msgs/JointState | Current joint positions |
| `/xarm5_traj_controller/...` | action | Trajectory execution |
| `/CONVEYORPOWER` | service | Conveyor speed control |
| `/CONVEYORSTATE` | conveyorbelt_msgs/ConveyorBeltState | Belt status |

## Development Status

| Component | Status |
|-----------|--------|
| xArm 5 Integration | ✅ Complete |
| MoveIt2 Control | ✅ Complete |
| Conveyor Belt | ✅ Complete |
| Sensors | ✅ Complete |
| Single Robot Sim | ✅ Working |
| Multi-Robot | 🔄 In Progress |
| Physical Integration | ⏳ Planned |

## Documentation

- [Scalable Architecture](docs/SCALABLE_ARCHITECTURE.md) - **Multi-robot system design**
- [Quick Control Guide](docs/QUICK_CONTROL_GUIDE.md) - Control commands and examples
- [Project Context](docs/PROJECT_CONTEXT.md) - System overview
- [Blender to Gazebo Guide](docs/BLENDER_TO_GAZEBO_GUIDE.md) - Custom model pipeline
- [Work Log](docs/WORK_LOG.md) - Development history

## License

MIT
