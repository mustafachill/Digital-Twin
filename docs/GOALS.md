## 1. Definition and conceptual framework

In this project, a **digital twin** of a robotic arm is understood as the combination of:

1. A **physical asset**: the real robotic arm.
2. A **virtual representation**: the simulated robot model running in Gazebo and controlled through ROS 2.
3. A **two-way data connection**:
   - Real-time or near real-time data flowing from the physical robot to the virtual model.
   - Commands and control strategies that can be developed in the virtual environment and then applied to the real robot.

The digital twin is not just a static model. It should evolve over time together with the physical system, and it should be driven by actual data.

## 2. Level and scope of the twin

The current scope is an **asset-level digital twin** focused on a single robotic arm.

The twin will track and model:
- Joint positions and velocities.
- End-effector pose (where applicable).
- Basic sensor data relevant to the arm (e.g., joint torques, simple force/limit information if available).

System-level or factory-level twins are explicitly out of scope for now.

## 3. Core objectives

The digital twin for the robot arm has the following core objectives:

1. **Common control interface**
   - The simulated arm and the real arm must share a common ROS 2 interface (topics, services, actions).
   - A node that controls the robot in simulation should require minimal or no changes to control the real robot.

2. **Safe experimentation**
   - New control algorithms, motion plans, and behaviors should be validated in the Gazebo simulation first.
   - Only once they pass basic safety and correctness checks should they be deployed to the real arm.

3. **Behavior comparison**
   - The system should allow for comparison between:
     - Expected behavior predicted by the simulation.
     - Actual behavior measured from the physical arm.
   - Discrepancies can later be used to refine models, controllers, and assumptions.

4. **Progressive complexity**
   - Start with simple joint-space control and basic trajectories.
   - Gradually add:
     - More complex motion planning.
     - Additional sensors.
     - More detailed physical modeling (e.g., inertia, friction).

## 4. Functional requirements (high-level)

At a high level, the digital twin must:

1. Provide launch configurations to:
   - Start the Gazebo simulation with the robot arm.
   - Connect to the real robot arm.
   - Start both simultaneously in a “twin mode”.

2. Offer a clear set of ROS 2 interfaces:
   - Topics for joint states and other sensor data.
   - Topics/services/actions for sending joint commands and trajectories.
   - Optional diagnostic topics for monitoring twin consistency.

3. Support logging and replay:
   - Log relevant data from the real robot and simulation.
   - Allow replaying a recorded run in the simulation for analysis.

## 5. Non-functional requirements

- **Language**  
  All source code, comments, configuration file contents, and documentation inside the repository must be written in English.

- **Maintainability**  
  The repository should be structured so that:
  - Another ROS 2 developer can understand and extend it.
  - Hardware-specific details are isolated from generic control logic where possible.

- **Traceability**  
  Important changes to the behavior of the twin (interfaces, models, control strategies) should be documented:
  - In commit messages.
  - In the `docs/WORK_LOG.md` file.

## 6. Future extensions (not required now)

The following items are potential future extensions but are not required for the initial version:

- Integration with external data platforms (cloud or edge).
- Advanced analytics on differences between simulated and real behavior.
- Integration with UI dashboards or web-based monitoring tools.
- Support for multiple robot arms or multi-robot scenarios.