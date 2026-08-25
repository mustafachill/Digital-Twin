cmake_minimum_required(VERSION 3.16)
project(cite_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rclcpp REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  msg/ConveyorState.msg
  msg/Detection.msg
  msg/DetectionEvent.msg
  msg/DivergenceMetrics.msg
  msg/LineState.msg
  msg/ModelVersion.msg
  msg/ResultCode.msg
  msg/RobotState.msg
  msg/SafetyState.msg
  msg/StationState.msg
  msg/TwinMode.msg
  srv/GetModelVersion.srv
  srv/SetMode.srv
  action/Detect.action
  action/Grasp.action
  action/MoveTo.action
  action/Pick.action
  action/Place.action
  action/Transfer.action
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs
)

# The QoS profile library (ADR-0025). It lives here because this package already
# sits at the bottom of the dependency graph and is already a dependency of every
# node that publishes anything — so the profile table exists once, in code,
# without inventing a package for it.
install(
  DIRECTORY include/
  DESTINATION include/${PROJECT_NAME}
)
ament_export_include_directories(include)
ament_export_dependencies(rclcpp)

# The Python half of the QoS library cannot be installed with
# ament_python_install_package: rosidl_generate_interfaces already creates a
# Python package of this name for the generated bindings, and both would try to
# define the same CMake targets. Installing the module directly into that
# package's directory puts `cite_interfaces.qos` exactly where a consumer expects
# it, without a second package to import from.
install(
  FILES ${PROJECT_NAME}/qos.py
  DESTINATION "${PYTHON_INSTALL_DIR}/${PROJECT_NAME}"
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_lint_auto_find_test_dependencies()
  # Asserts the C++ header, the Python module and docs/interfaces/qos-profiles.md
  # all state the same numbers. Two implementations of one table are kept honest
  # by a test because ROS 2 has two client libraries and there is no way to have
  # only one.
  ament_add_pytest_test(qos_consistency test/test_qos_consistency.py)
endif()

ament_package()
