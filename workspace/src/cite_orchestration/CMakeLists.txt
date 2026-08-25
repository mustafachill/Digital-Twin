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

install(TARGETS line_coordinator DESTINATION lib/${PROJECT_NAME})
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
endif()

ament_package()
