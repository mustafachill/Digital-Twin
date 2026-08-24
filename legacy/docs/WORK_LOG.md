# Work Log – digital-twin

This file acts as a persistent work log for the project.  
Each significant task should append a new section with:
- Date
- Task
- Files touched
- Summary
- Next steps

---

## 2025-11-25 – Initial project setup

- Task:
  - Created the initial documentation and Cursor rule files for the digital-twin project.
- Files touched:
  - docs/PROJECT_CONTEXT.md
  - docs/DIGITAL_TWIN_GOALS.md
  - docs/WORK_LOG.md
  - .cursor/rules/core.mdc
  - .cursor/rules/ros2_gazebo.mdc
  - .cursor/rules/work_log.mdc
- Summary:
  - Defined the high-level context and goals for the digital twin of a robot arm.
  - Established Cursor rules to enforce English-only code and comments, and to use this log as persistent memory.
- Next steps:
  - Initialize the ROS 2 workspace structure under `digital-twin`.
  - Create empty ROS 2 packages:
    - `robot_arm_description`
    - `robot_arm_gazebo`
    - `robot_arm_control`
    - `robot_arm_bringup`
  - Add basic README content describing how to build the workspace with `colcon build`.

---

## 2025-11-25 – ROS2 workspace and robot arm simulation setup

- Task:
  - Created the full ROS2 workspace structure with 4 packages.
  - Implemented 6-DOF robot arm URDF/Xacro model.
  - Configured ros2_control with JointTrajectoryController.
  - Set up Gazebo Classic integration.
  - Created bringup launch files.
- Files touched:
  - src/robot_arm_description/urdf/robot_arm.urdf.xacro
  - src/robot_arm_description/urdf/robot_arm.ros2_control.xacro
  - src/robot_arm_description/urdf/materials.xacro
  - src/robot_arm_description/urdf/inertia_macros.xacro
  - src/robot_arm_description/launch/view_robot.launch.py
  - src/robot_arm_description/rviz/view_robot.rviz
  - src/robot_arm_description/CMakeLists.txt
  - src/robot_arm_description/package.xml
  - src/robot_arm_control/config/robot_arm_controllers.yaml
  - src/robot_arm_control/launch/controllers.launch.py
  - src/robot_arm_control/CMakeLists.txt
  - src/robot_arm_control/package.xml
  - src/robot_arm_gazebo/worlds/empty_world.world
  - src/robot_arm_gazebo/launch/gazebo.launch.py
  - src/robot_arm_gazebo/CMakeLists.txt
  - src/robot_arm_gazebo/package.xml
  - src/robot_arm_bringup/launch/sim.launch.py
  - src/robot_arm_bringup/rviz/sim.rviz
  - src/robot_arm_bringup/CMakeLists.txt
  - src/robot_arm_bringup/package.xml
- Summary:
  - Created a generic 6-DOF robot arm model with proper inertia, collision, and visual properties.
  - Configured ros2_control with GazeboSystem hardware interface for simulation.
  - Set up joint_state_broadcaster and joint_trajectory_controller.
  - Created Gazebo world file and spawn launch file.
  - Created unified bringup launch file (sim.launch.py) that starts everything.
  - Successfully ran `colcon build` without errors.
- Next steps:
  - Install required ROS2 packages: ros-humble-ros2-control, ros-humble-ros2-controllers, ros-humble-gazebo-ros2-control, ros-humble-gazebo-ros
  - Test the simulation with `ros2 launch robot_arm_bringup sim.launch.py`
  - Verify joint control via trajectory commands
  - Begin work on real robot hardware interface (when hardware is decided)

---

## 2025-11-25 – Fixed gazebo_ros2_control compatibility issue

- Task:
  - Debugged and fixed a compatibility issue between source-built ROS2 Humble and gazebo_ros2_control.
  - The issue was caused by robot_description (URDF/XML) being passed as a command-line parameter argument.
- Files touched:
  - src/gazebo_ros2_control/ (cloned from humble branch)
  - src/gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp (patched)
  - src/robot_arm_gazebo/launch/gazebo.launch.py
- Summary:
  - Identified that gazebo_ros2_control was trying to pass robot_description as `--param robot_description:=<xml...>` which failed to parse.
  - Patched gazebo_ros2_control_plugin.cpp to set robot_description as a node parameter AFTER controller_manager creation instead of passing it as a command-line argument.
  - The fix allows the controller_manager to load and activate controllers properly.
- Verification:
  - `ros2 control list_controllers` shows both controllers as active:
    - joint_state_broadcaster (active)
    - joint_trajectory_controller (active)
  - `/joint_states` topic publishes data for all 6 joints.
- Next steps:
  - Test trajectory commands to verify joint control works.
  - Clean up RViz visualization (sync with Gazebo).
  - Begin planning real hardware interface.

---

## 2025-11-25 – RViz-Gazebo Twin Test and Control Guide

- Task:
  - Tested RViz and Gazebo twin synchronization.
  - Created Quick Control Guide documentation.
- Files touched:
  - src/robot_arm_bringup/rviz/sim.rviz (updated for proper sync)
  - docs/QUICK_CONTROL_GUIDE.md (new)
  - README.md (added reference)
- Summary:
  - Successfully tested trajectory commands moving robot in both Gazebo and RViz simultaneously.
  - Verified joint positions reach commanded values accurately.
  - Created comprehensive control guide with example commands.
- Verification:
  - Sent multiple trajectory goals, all completed successfully.
  - Gazebo physics simulation and RViz visualization remain synchronized.
- Next steps:
  - Consider MoveIt2 integration for interactive control.
  - Begin real hardware interface planning when hardware is selected.

---

## 2025-12-02 – xArm 5 Integration

- Task:
  - Integrated UFACTORY xArm 5 robot arm model into the Digital Twin project.
  - Set up MoveIt2 for interactive control.
- Files touched:
  - src/xarm_ros2/ (cloned from https://github.com/xArm-Developer/xarm_ros2, humble branch)
  - src/xarm_ros2/xarm_gazebo/CMakeLists.txt (disabled mimic_joint_plugin due to header compatibility)
  - src/robot_arm_bringup/launch/xarm5_sim.launch.py (new)
  - docs/QUICK_CONTROL_GUIDE.md (updated for xArm 5)
- Summary:
  - Cloned official xArm ROS2 package from UFACTORY.
  - Updated git submodules for xArm SDK.
  - Installed MoveIt2 and required dependencies.
  - Successfully built all xArm packages (xarm_description, xarm_controller, xarm_gazebo, xarm_moveit_config, xarm_planner).
  - Created unified launch file `xarm5_sim.launch.py` in robot_arm_bringup package.
  - Tested xArm 5 simulation with Gazebo and MoveIt2.
- Verification:
  - `ros2 control list_controllers` shows:
    - joint_state_broadcaster (active)
    - xarm5_traj_controller (active)
  - `/joint_states` publishes xArm 5's 5 joints (joint1-joint5).
  - MoveIt2 interactive control works in RViz.
  - Trajectory commands work via action interface.
- Packages installed:
  - ros-humble-moveit
  - ros-humble-moveit-ros-planning-interface
  - ros-humble-moveit-msgs
  - ros-humble-moveit-ros-move-group
  - ros-humble-moveit-servo
  - ros-humble-launch-param-builder
  - ros-humble-tf-transformations
  - ros-humble-joy
- Next steps:
  - Test MoveIt2 interactive planning via RViz.
  - Implement custom digital twin synchronization layer.
  - Plan physical xArm 5 hardware integration.

---

## 2025-12-02 – Gazebo Laboratory Environment Setup

- Task:
  - Created infrastructure for custom Gazebo laboratory environment.
  - Set up Blender-to-Gazebo model pipeline.
  - Prepared template files for custom 3D models.
- Files touched:
  - src/digital_twin_environment/ (new ROS2 package)
  - src/digital_twin_environment/CMakeLists.txt
  - src/digital_twin_environment/package.xml
  - src/digital_twin_environment/env-hooks/gazebo_model_path.dsv.in
  - src/digital_twin_environment/worlds/robotics_lab.world
  - src/digital_twin_environment/models/workbench/{model.config, model.sdf}
  - src/digital_twin_environment/models/lab_floor/{model.config, model.sdf}
  - src/digital_twin_environment/models/shelf/{model.config, model.sdf}
  - src/digital_twin_environment/launch/lab_with_xarm5.launch.py
  - docs/BLENDER_TO_GAZEBO_GUIDE.md (new)
- Summary:
  - Created `digital_twin_environment` ROS2 package with proper Gazebo model database structure.
  - Implemented automatic GAZEBO_MODEL_PATH configuration via environment hooks.
  - Created `robotics_lab.world` template with physics, lighting, and placeholder sections.
  - Created model templates (workbench, lab_floor, shelf) with model.config and model.sdf files.
  - Created comprehensive Blender-to-Gazebo pipeline documentation.
  - Created launch file that integrates custom environment with xArm 5 simulation.
- Package Structure:
  ```
  digital_twin_environment/
  ├── worlds/robotics_lab.world
  ├── models/{workbench,lab_floor,shelf}/
  ├── materials/{textures,scripts}/
  └── launch/lab_with_xarm5.launch.py
  ```
- Next steps:
  - Build package: `colcon build --packages-select digital_twin_environment`
  - Model the laboratory in Blender following BLENDER_TO_GAZEBO_GUIDE.md
  - Export models and add them to the models/ directory
  - Update robotics_lab.world with custom model placements
  - Test full simulation with xArm 5 in custom environment

---

## 2025-12-04 – Multi-Robot Assembly Line Implementation

- Task:
  - Implemented a complete multi-robot pick and place assembly line system.
  - Created conveyor belt integration, sensors, and coordination system.
  - Set up 3 xArm 5 robots with grippers for synchronized operations.
- New Packages Created:
  1. `conveyor_system` - Conveyor belt models and configuration
  2. `assembly_line_sensors` - Break beam and proximity sensors
  3. `assembly_line_bringup` - Main launch package for full system
  4. `multi_robot_coordinator` - State machine and robot coordination
- External Packages Integrated:
  - `ifra_conveyor_belt` - IFRA-Cranfield ROS2 conveyor belt plugin
    - `conveyorbelt_msgs` - Custom messages/services
    - `ros2_conveyorbelt` - Gazebo plugin
    - `conveyorbelt_gazebo` - Models and worlds
- Files touched:
  - src/ifra_conveyor_belt/ (cloned from IFRA-Cranfield/IFRA_ConveyorBelt)
  - src/conveyor_system/
    - package.xml, CMakeLists.txt
    - models/long_conveyor_belt/{model.config, model.sdf}
    - models/payload_box/{model.config, model.sdf}
    - config/conveyor_params.yaml
    - worlds/conveyor_test.world
    - launch/conveyor_test.launch.py
  - src/assembly_line_sensors/
    - package.xml, CMakeLists.txt
    - models/break_beam_sensor/{model.config, model.sdf}
    - models/proximity_sensor/{model.config, model.sdf}
    - urdf/sensor_station.xacro
    - config/sensor_topics.yaml
    - launch/sensors_test.launch.py
  - src/assembly_line_bringup/
    - package.xml, CMakeLists.txt
    - launch/three_robots.launch.py
    - launch/assembly_line.launch.py
    - worlds/assembly_line.world
    - config/robot_positions.yaml
    - rviz/assembly_line.rviz
  - src/multi_robot_coordinator/
    - package.xml, setup.py, setup.cfg
    - multi_robot_coordinator/coordinator_node.py
    - multi_robot_coordinator/sensor_monitor.py
    - multi_robot_coordinator/box_spawner.py
    - config/coordinator_params.yaml
    - config/pick_place_poses.yaml
    - launch/coordinator.launch.py
- Summary:
  - Created a 4-metre conveyor belt with ROS2 control plugin.
  - Implemented break beam sensors at each robot station for box detection.
  - Created payload box model for pick and place operations.
  - Developed state machine coordinator for robot synchronization.
  - Created sensor monitor for consolidated sensor data.
  - Implemented box spawner for dynamic object spawning.
  - Created assembly line world with 3 robot tables and sensors.
  - Set up 3 xArm 5 robots with namespaced controllers and grippers.
- System Architecture:
  ```
  [KUTU] --> [BANT] --> [Robot 1] --> [BANT] --> [Robot 2] --> [BANT] --> [Robot 3] --> [ÇIKIŞ]
                              |              |              |
                        [Sensor 1]     [Sensor 2]     [Sensor 3]
  ```
- Launch Commands:
  - Test conveyor: `ros2 launch conveyor_system conveyor_test.launch.py`
  - Test 3 robots: `ros2 launch assembly_line_bringup three_robots.launch.py`
  - Full system: `ros2 launch assembly_line_bringup assembly_line.launch.py`
  - With auto spawn: `ros2 launch assembly_line_bringup assembly_line.launch.py auto_spawn:=true`
- Conveyor Control:
  - Start belt: `ros2 service call /conveyor/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 50.0}"`
  - Stop belt: `ros2 service call /conveyor/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.0}"`
  - Spawn box: `ros2 topic pub --once /box_spawner/trigger std_msgs/msg/String "data: 'spawn'"`
- Next steps:
  - Test the full assembly line simulation.
  - Tune pick and place poses for actual operations.
  - Add MoveIt2 integration for motion planning.
  - Implement gripper control in coordinator.
  - Add vision-based box detection with cameras.

---

## 2025-12-04 – Project Reorganization (Multi-Robot as Main Project)

- Task:
  - Reorganized project structure to make multi-robot assembly line the main Digital Twin.
  - Updated documentation and created unified launch entry point.
- Files touched:
  - README.md (complete rewrite for assembly line focus)
  - docs/PROJECT_CONTEXT.md (updated architecture documentation)
  - src/assembly_line_bringup/launch/digital_twin.launch.py (new main launch)
  - src/assembly_line_bringup/launch/single_robot_test.launch.py (debug launch)
  - src/assembly_line_bringup/worlds/assembly_line.world (simplified)
- Summary:
  - Established `assembly_line_bringup` as the main launch package.
  - Created `digital_twin.launch.py` as the primary entry point.
  - Fixed world file issues (sensor namespace conflicts).
  - Single robot simulation confirmed working.
  - Updated all documentation to reflect assembly line focus.
- Main Launch Command:
  ```bash
  ros2 launch assembly_line_bringup digital_twin.launch.py
  ```
- Next steps:
  - Debug multi-robot simultaneous spawning.
  - Implement robot handoff coordination.
  - Physical xArm 5 hardware integration.

---

## 2025-12-04 – Scalable Architecture Design

- Task:
  - Designed new scalable multi-robot architecture.
  - Moved from bundled URDF approach to independent robot nodes.
  - Created comprehensive architecture documentation.
- Key Decisions:
  1. **Config-Driven Fleet**: Robots defined in YAML, auto-spawned at startup
  2. **Independent Namespaces**: Each robot in own namespace (/robot_1, /robot_2, ...)
  3. **Topology Definition**: upstream/downstream relationships in config
  4. **Direct Pub/Sub**: Robot-to-robot communication without central broker
  5. **Neighbor Discovery**: Robots learn neighbors from config at startup
- Files touched:
  - docs/SCALABLE_ARCHITECTURE.md (new - comprehensive architecture doc)
- Architecture Highlights:
  ```
  Fleet Config (YAML)
       │
       ▼
  Fleet Manager ──► Spawn robots with namespaces
       │
       ├──► /robot_1/ (independent node)
       ├──► /robot_2/ (independent node)
       └──► /robot_N/ (independent node)
             │
             └──► Direct pub/sub to neighbors
  ```
- Message Types Defined:
  - RobotStatus.msg: Robot state, position, payload status
  - RobotCommand.msg: Commands from coordinator
  - HandoffRequest.msg: Robot-to-robot transfer protocol
- New Packages Planned:
  - fleet_manager: Config loading, robot spawning
  - robot_interface: Independent robot node, state machine
  - assembly_coordinator: High-level orchestration
- Next steps:
  - Implement fleet_manager package
  - Create parametric URDF template
  - Implement robot_interface with state machine
  - Test with 3+ robots

---

## 2025-12-04 – Scalable Fleet Implementation

- Task:
  - Implemented the scalable multi-robot fleet architecture.
  - Created two new core packages: fleet_manager and robot_interface.
- New Packages Created:
  1. `fleet_manager` - Config-based fleet management and robot spawning
  2. `robot_interface` - Independent robot node with state machine and handoff protocol
- Files touched:
  - src/fleet_manager/
    - package.xml, CMakeLists.txt
    - fleet_manager/__init__.py
    - fleet_manager/config_loader.py - YAML parsing and typed dataclasses
    - fleet_manager/robot_spawner.py - Gazebo spawn orchestration
    - fleet_manager/fleet_manager_node.py - Main fleet management node
    - config/fleet_config.yaml - 3-robot fleet definition
    - config/robot_types.yaml - xArm 5/6/7 robot type definitions
    - urdf/spawnable_robot.urdf.xacro - Parametric robot URDF
    - srv/SpawnRobot.srv, RemoveRobot.srv, GetFleetStatus.srv
    - launch/fleet.launch.py - Main fleet launch file
    - launch/multi_robot_test.launch.py - Integration test launch
  - src/robot_interface/
    - package.xml, CMakeLists.txt
    - robot_interface/__init__.py
    - robot_interface/state_machine.py - Robot state machine (IDLE/PICKING/HOLDING/PLACING)
    - robot_interface/robot_node.py - Independent robot controller
    - robot_interface/handoff_coordinator.py - Robot-to-robot handoff management
    - msg/RobotStatus.msg, HandoffRequest.msg, HandoffResponse.msg
    - srv/RequestHandoff.srv
    - config/robot_interface.yaml - Per-robot pick/place positions
    - launch/robot_interface.launch.py
  - src/assembly_line_bringup/package.xml (added dependencies)
  - docs/WORK_LOG.md
- Key Features Implemented:
  1. **Config-Driven Fleet**:
     - fleet_config.yaml defines all robots with positions, types, and roles
     - robot_types.yaml contains URDF/controller mappings for each robot type
     - Supports xArm 5, 6, and 7 (with templates for UR5 etc.)
  2. **Topology Definition**:
     - Stations with upstream/downstream relationships
     - Sensor mappings per station
     - Chain topology (robot_1 → robot_2 → robot_3)
  3. **Independent Robot Nodes**:
     - Each robot runs its own RobotNode
     - State machine: IDLE → PICKING → HOLDING → PLACING
     - Publishes status and handoff signals
     - Subscribes to neighbor signals
  4. **Handoff Protocol**:
     - ready_to_give / ready_to_receive signals
     - HandoffCoordinator manages transactions
     - Timeout and error handling
- Launch Commands:
  - Fleet with 3 robots: `ros2 launch fleet_manager multi_robot_test.launch.py num_robots:=3`
  - Fleet with interfaces: `ros2 launch fleet_manager multi_robot_test.launch.py launch_interfaces:=true`
  - Single robot interface: `ros2 launch robot_interface robot_interface.launch.py robot_id:=robot_1`
- Message Flow:
  ```
  /robot_1/status                 - Robot status (state, holding_object, etc.)
  /robot_1/handoff/ready_to_give  - Bool signal when ready to hand off
  /robot_1/handoff/ready_to_receive - Bool signal when ready to receive
  /handoff_coordinator/status     - Overall coordination status
  ```
- Next steps:
  - Build and test the new packages: `colcon build --packages-select fleet_manager robot_interface`
  - Test 3-robot fleet spawning
  - Implement actual motion execution (MoveIt2 integration)
  - Add gripper control to state machine
  - Physical hardware integration