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
install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
