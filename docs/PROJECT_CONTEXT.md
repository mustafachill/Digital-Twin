# Project Context – digital-twin (ROS 2 Humble + Gazebo robot arm digital twin)

## 1. High-level overview

This repository defines a ROS 2 Humble workspace that implements a digital twin for a robotic arm.

- The **virtual twin** is a simulated robot arm running in Gazebo, controlled through ROS 2 nodes.
- The **physical system** is a real robot arm that will later be connected to the same ROS 2 interfaces.
- The long-term goal is to have both the simulated and the real arm share a common control interface, so that:
  - Motion plans and control strategies can be developed and validated in simulation.
  - The same interfaces can then be used to control the physical robot safely.

The repository is meant to be built with `colcon build` from the root folder:

```bash
cd digital-twin
colcon build