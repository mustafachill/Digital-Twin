# Digital Twin - Robot Arm

A ROS 2 Humble digital twin project for a 6-DOF robot arm, featuring Gazebo simulation and ros2_control integration.

## Overview

This project implements a digital twin architecture where:
- A simulated robot arm runs in Gazebo with full physics simulation
- The same ROS 2 interfaces can control both the simulated and real robot
- ros2_control provides hardware abstraction between simulation and real hardware

## Package Structure

| Package | Description |
|---------|-------------|
| `robot_arm_description` | URDF/Xacro model, meshes, and RViz configs |
| `robot_arm_control` | ros2_control configuration and controller setup |
| `robot_arm_gazebo` | Gazebo world files and simulation launch |
| `robot_arm_bringup` | Unified launch files for different modes |

## Prerequisites

### Required ROS 2 Packages

```bash
sudo apt-get update
sudo apt-get install -y \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-gazebo-ros2-control \
    ros-humble-gazebo-ros \
    ros-humble-joint-state-publisher \
    ros-humble-joint-state-publisher-gui \
    ros-humble-xacro \
    ros-humble-rviz2
```

## Building

```bash
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## Usage

### View Robot Model in RViz (without simulation)

```bash
ros2 launch robot_arm_description view_robot.launch.py
```

This launches the robot model with a joint state publisher GUI, allowing you to manually move joints.

### Run Full Simulation

```bash
ros2 launch robot_arm_bringup sim.launch.py
```

This starts:
- Gazebo with the robot arm spawned
- ros2_control with joint_state_broadcaster and joint_trajectory_controller
- RViz for visualization

### Available Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/robot_description` | `std_msgs/String` | Robot URDF |
| `/joint_states` | `sensor_msgs/JointState` | Current joint states |
| `/joint_trajectory_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | Trajectory commands |

### Test Joint Control

Send a test trajectory:

```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
    control_msgs/action/FollowJointTrajectory \
    "{trajectory: {joint_names: ['joint1', 'joint2', 'joint3', 'joint4', 'joint5', 'joint6'], points: [{positions: [0.5, 0.3, -0.3, 0.2, 0.1, 0.0], time_from_start: {sec: 2}}]}}"
```

## Robot Arm Specifications

- **DOF**: 6 revolute joints
- **Joints**:
  - Joint 1: Base rotation (yaw), ±180°
  - Joint 2: Shoulder pitch, ±90°
  - Joint 3: Elbow pitch, ±135°
  - Joint 4: Wrist pitch, ±90°
  - Joint 5: Wrist roll, ±180°
  - Joint 6: Wrist yaw, ±180°
- **End Effector**: Generic mounting point (TCP frame)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ROS 2 Control                          │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │ JointStateBroadcaster│    │ JointTrajectoryController │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         ▼                                         ▼
┌─────────────────────┐                 ┌─────────────────────┐
│   GazeboSystem      │                 │   FutureHardware    │
│   (Simulation)      │                 │   (Real Robot)      │
└─────────────────────┘                 └─────────────────────┘
```

## Documentation

- [Quick Control Guide](docs/QUICK_CONTROL_GUIDE.md) - Robot kontrol komutları ve örnekler
- [Project Context](docs/PROJECT_CONTEXT.md)
- [Goals](docs/GOALS.md)
- [Work Log](docs/WORK_LOG.md)

## License

MIT

