# Project Context – Digital Twin (Multi-Robot Assembly Line)

## 1. High-level Overview

This repository defines a ROS 2 Humble workspace that implements a **Digital Twin** for a multi-robot assembly line system.

### System Architecture

```
[KUTU] --> [BANT] --> [Robot 1] --> [BANT] --> [Robot 2] --> [BANT] --> [Robot 3] --> [ÇIKIŞ]
                           |              |              |
                      [Sensor 1]     [Sensor 2]     [Sensor 3]
                      [Kamera 1]     [Kamera 2]     [Kamera 3]
```

### Core Components

- **3x xArm 5 Robot Arms**: UFACTORY xArm 5 DOF robot kolları, gripper ile
- **Conveyor Belt System**: ROS2 kontrollü konveyör bant (IFRA-Cranfield plugin)
- **Sensor Network**: Break beam sensörler, proximity sensörler, RealSense D435 kameralar
- **Coordination System**: State machine tabanlı robot koordinasyonu

### Digital Twin Concept

- **Virtual Twin**: Gazebo simülasyonunda çalışan 3 robotlu montaj hattı
- **Physical System**: Gerçek xArm 5 robotlar (gelecekte entegre edilecek)
- **Synchronization**: Aynı ROS2 interface'leri ile simülasyon ve gerçek sistem kontrol edilebilir

## 2. Package Structure

```
src/
├── xarm_ros2/                    # UFACTORY xArm ROS2 packages
│   ├── xarm_description/         # Robot URDF/meshes
│   ├── xarm_controller/          # ros2_control configuration
│   ├── xarm_gazebo/              # Gazebo integration
│   ├── xarm_moveit_config/       # MoveIt2 configuration
│   └── ...
│
├── ifra_conveyor_belt/           # Conveyor belt plugin (IFRA-Cranfield)
│   ├── conveyorbelt_msgs/        # Custom messages/services
│   ├── ros2_conveyorbelt/        # Gazebo plugin
│   └── conveyorbelt_gazebo/      # Models and worlds
│
├── conveyor_system/              # Custom conveyor models
├── assembly_line_sensors/        # Sensor models (break beam, proximity)
├── assembly_line_bringup/        # Main launch package ⭐
├── multi_robot_coordinator/      # Robot coordination node
│
├── digital_twin_environment/     # Custom lab environment
├── robot_arm_description/        # Generic robot arm (legacy)
├── robot_arm_control/            # Generic control (legacy)
├── robot_arm_gazebo/             # Generic gazebo (legacy)
└── robot_arm_bringup/            # Generic bringup (legacy)
```

## 3. Quick Start

### Build

```bash
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### Launch Digital Twin

```bash
# Ana simülasyon (tek robot - çalışıyor)
ros2 launch assembly_line_bringup digital_twin.launch.py

# Alternatif: xArm resmi launch
ros2 launch xarm_moveit_config xarm5_moveit_gazebo.launch.py add_gripper:=true
```

### Conveyor Control

```bash
# Bandı başlat (%50 güç)
ros2 service call /CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 50.0}"

# Bandı durdur
ros2 service call /CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.0}"
```

## 4. Development Status

| Component | Status |
|-----------|--------|
| xArm 5 Integration | ✅ Complete |
| MoveIt2 Control | ✅ Complete |
| Conveyor Belt Plugin | ✅ Complete |
| Sensor Models | ✅ Complete |
| Single Robot Simulation | ✅ Working |
| Multi-Robot Launch | 🔄 In Progress |
| Coordinator Node | ✅ Framework Ready |
| Physical Robot Integration | ⏳ Planned |

## 5. Key Files

- **Main Launch**: `src/assembly_line_bringup/launch/digital_twin.launch.py`
- **World File**: `src/assembly_line_bringup/worlds/assembly_line.world`
- **Coordinator**: `src/multi_robot_coordinator/multi_robot_coordinator/coordinator_node.py`
- **Work Log**: `docs/WORK_LOG.md`

## 6. Dependencies

```bash
# ROS2 Humble packages
sudo apt install ros-humble-moveit ros-humble-gazebo-ros2-control \
    ros-humble-controller-manager ros-humble-joint-trajectory-controller \
    ros-humble-joint-state-broadcaster
```

## 7. Architecture Documentation

**Detaylı mimari için:** [SCALABLE_ARCHITECTURE.md](SCALABLE_ARCHITECTURE.md)

### Temel Prensipler

- **Config-Driven**: Tüm fleet YAML ile tanımlı
- **Independent Robots**: Her robot kendi namespace'inde
- **Pub/Sub Communication**: Robot-to-robot direct messaging
- **Topology Awareness**: Robotlar neighbor'larını config'den öğrenir

## 8. Next Steps

1. Fleet Manager paketi implementasyonu
2. Parametric robot URDF template
3. Robot interface ve state machine
4. Multi-robot spawn testi
5. Handoff protocol implementasyonu
6. Physical xArm 5 integration
