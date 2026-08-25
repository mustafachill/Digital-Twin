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
find_package(moveit_ros_planning_interface REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

add_executable(skill_server
  src/skill_server.cpp
  src/approach.cpp
)
target_include_directories(skill_server PRIVATE include)
ament_target_dependencies(skill_server
  rclcpp rclcpp_action cite_interfaces control_msgs geometry_msgs
  moveit_ros_planning_interface tf2_ros tf2_geometry_msgs
)

install(TARGETS skill_server DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  ament_lint_auto_find_test_dependencies()

  # Approach and retreat geometry is pure arithmetic, so it is tested without a
  # planner, a simulator, or any waiting. Pushing it down here is what keeps the
  # scenario suite for things only a whole system can show.
  ament_add_gtest(test_approach test/test_approach.cpp src/approach.cpp)
  target_include_directories(test_approach PRIVATE include)
  ament_target_dependencies(test_approach geometry_msgs tf2_geometry_msgs)
endif()

ament_package()
