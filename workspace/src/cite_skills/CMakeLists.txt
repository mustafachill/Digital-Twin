cmake_minimum_required(VERSION 3.16)
project(cite_skills)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(cite_interfaces REQUIRED)
find_package(control_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(moveit_core REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

add_executable(skill_server
  src/skill_server.cpp
  src/approach.cpp
  src/gripper.cpp
  src/pose_goal.cpp
)
target_include_directories(skill_server PRIVATE include)
ament_target_dependencies(skill_server
  rclcpp rclcpp_action cite_interfaces control_msgs geometry_msgs
  moveit_core moveit_ros_planning_interface tf2_ros tf2_geometry_msgs
)

install(TARGETS skill_server DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)

  # Two linters in ament_lint_common are registered by hand rather than through
  # ament_lint_auto, because their defaults contradict conventions this
  # repository already follows and neither can be configured through the auto
  # path. What they check is unchanged; only the two conflicting preferences are
  # settled. Same block as cite_bringup and cite_facility carry, for the same
  # reason. See .flake8 at the repository root for the flake8 half.
  #
  # pep257: the "ament" convention ignores D212 and therefore enforces D213 —
  # "summary should start at the second line". D212 and D213 are mutually
  # exclusive by construction, and every docstring in this repository puts the
  # summary on the first line.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)

  # Approach and retreat geometry is pure arithmetic, so it is tested without a
  # planner, a simulator, or any waiting. Pushing it down here is what keeps the
  # scenario suite for things only a whole system can show.
  ament_add_gtest(test_approach test/test_approach.cpp src/approach.cpp)
  target_include_directories(test_approach PRIVATE include)
  ament_target_dependencies(test_approach geometry_msgs tf2_geometry_msgs)

  # The rule from ADR-0026 — solve IK on the exact pose, plan to the joint
  # configuration, and try more than one IK branch before calling a pose
  # unreachable — is sequencing, so it is tested as sequencing, with the planner
  # and the robot replaced by callables that record what was asked of them.
  ament_add_gtest(test_pose_goal test/test_pose_goal.cpp src/pose_goal.cpp)
  target_include_directories(test_pose_goal PRIVATE include)

  # Gripper arithmetic: metres against the drive joint's own units, where the pad
  # face sits on the tool axis, and what a `Pick` closes to when the goal leaves
  # the width unset.
  ament_add_gtest(test_gripper test/test_gripper.cpp src/gripper.cpp)
  target_include_directories(test_gripper PRIVATE include)

  # Turning an object's pose into the tool pose that grasps it. The offset and
  # the offset-along-the-tool-axis each have their own tests above; what this
  # covers is their composition — the sign and the axis, both of which are free
  # to be wrong in a way that reads as plausible and moves the arm 37 mm the
  # wrong way in the cell.
  ament_add_gtest(
    test_grasp_pose test/test_grasp_pose.cpp src/approach.cpp src/gripper.cpp)
  target_include_directories(test_grasp_pose PRIVATE include)
  ament_target_dependencies(test_grasp_pose geometry_msgs tf2_geometry_msgs)

  # One arm, one goal. A concurrency invariant, tested as one — with threads,
  # not with a comment.
  ament_add_gtest(test_exclusive_goal test/test_exclusive_goal.cpp)
  target_include_directories(test_exclusive_goal PRIVATE include)

  # The parts of the action contract that only a running server can show:
  # goal exclusion, a cancel that reaches the gripper, and a reachable pose that
  # is planned to rather than refused. move_group, no simulator, no controllers —
  # so it runs headlessly in CI and still exercises the real binary.
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_skill_contract.py TIMEOUT 400)
endif()

ament_package()
