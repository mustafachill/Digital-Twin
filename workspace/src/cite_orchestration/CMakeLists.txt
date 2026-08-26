cmake_minimum_required(VERSION 3.16)
project(cite_orchestration)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(cite_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

add_executable(line_coordinator src/line_coordinator.cpp)
target_include_directories(line_coordinator PRIVATE include)
ament_target_dependencies(line_coordinator
  rclcpp rclcpp_action behaviortree_cpp cite_interfaces geometry_msgs tf2_ros
)

# The line. One subtree per station, instantiated from the L0 topology; the
# coordinator above runs one station in isolation, which is what ADR-0024 needs
# for a handoff to be testable with one arm.
add_executable(line_orchestrator src/line_orchestrator.cpp)
target_include_directories(line_orchestrator PRIVATE include)
ament_target_dependencies(line_orchestrator
  rclcpp rclcpp_action behaviortree_cpp cite_interfaces geometry_msgs tf2_ros
)

install(TARGETS line_coordinator line_orchestrator DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY trees DESTINATION share/${PROJECT_NAME})

# No `install(DIRECTORY include/ ...)`. This package exports no headers; the one
# under include/ holds the behaviour-tree leaves so that a test can drive them,
# and nothing outside this package includes it. The rule that was here pointed at
# an EMPTY, untracked directory — git carries no empty directories, so a clean
# clone and every CI run failed at configure time with
# `ament_cmake_symlink_install_directory() can't find .../include/`, while
# developer machines passed because the directory happened to exist locally.

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_gtest REQUIRED)

  # Driven against a real action server, in-process. The defect under test is
  # what a leaf does to a SERVER when it gives up, so a mock would test the wrong
  # side of the boundary.
  ament_add_gtest(test_skill_cancellation test/test_skill_cancellation.cpp)
  target_include_directories(test_skill_cancellation PRIVATE include)
  ament_target_dependencies(test_skill_cancellation
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces geometry_msgs
  )

  # What these leaves put in a goal, read from the far side of the action. A
  # leaf's whole job is turning ports into one typed goal, so the goal IS its
  # behaviour — and `PickAt` filled in a tool height where the action asks for
  # where the object is, which nothing could see until this existed.
  ament_add_gtest(test_skill_goals test/test_skill_goals.cpp)
  target_include_directories(test_skill_goals PRIVATE include)
  ament_target_dependencies(test_skill_goals
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces geometry_msgs
  )

  # The rules the line is made of — single ownership, the two-party handoff and
  # its timeout, buffer and reach arbitration, the recovery policy, and the
  # translation from an L0 topology into a plan and a tree. Pure logic, so it is
  # provable without standing up a cell, which is exactly what ADR-0024 means by
  # a handoff being testable in isolation.
  ament_add_gtest(test_line_logic test/test_line_logic.cpp)
  target_include_directories(test_line_logic PRIVATE include)
  ament_target_dependencies(test_line_logic
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces geometry_msgs
  )

  # The same rules, composed: a real behaviour tree with real in-process action
  # servers and a real sensor publisher, driving two stations through a handoff.
  # The logic tests prove each rule; this proves the tree wires them together,
  # which is the half that a unit test building its own expected values cannot
  # reach.
  ament_add_gtest(test_line_nodes test/test_line_nodes.cpp test/fake_arm.cpp TIMEOUT 180)
  target_include_directories(test_line_nodes PRIVATE include test)
  ament_target_dependencies(test_line_nodes
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces geometry_msgs
  )
  # The station subtree under test is the one that ships, read from the source
  # tree rather than copied: a test that carried its own copy would keep passing
  # after the shipped tree changed.
  target_compile_definitions(test_line_nodes PRIVATE
    CITE_STATION_TREE="${CMAKE_CURRENT_SOURCE_DIR}/trees/line_station.xml")
  # No debug info for this one. It instantiates the client and server templates
  # for three action types alongside BehaviorTree.CPP, and with `-g` the single
  # translation unit exceeds the 2500 MB per-job budget ./scripts/build derives —
  # the OOM killer takes cc1plus out and reports a "fatal error" that names
  # neither memory nor this file. A test binary's debug info is not what anybody
  # is debugging.
  target_compile_options(test_line_nodes PRIVATE -g0)
endif()

ament_package()
