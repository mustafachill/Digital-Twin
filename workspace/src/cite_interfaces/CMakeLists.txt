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
  msg/LineTopology.msg
  msg/ModelVersion.msg
  msg/ResultCode.msg
  msg/RobotState.msg
  msg/SafetyState.msg
  msg/StationEdge.msg
  msg/StationState.msg
  msg/StationTopology.msg
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

  # Two linters in ament_lint_common are registered by hand rather than through
  # ament_lint_auto, because their defaults contradict conventions this
  # repository already follows and neither can be configured through the auto
  # path. What they check is unchanged; only the two conflicting preferences are
  # settled. See .flake8 at the repository root for the flake8 half.
  #
  # pep257: the "ament" convention ignores D212 and therefore enforces D213 —
  # "summary should start at the second line". D212 and D213 are mutually
  # exclusive by construction, and every docstring in this repository puts the
  # summary on the first line. Enforcing D213 would rewrite all of them to say
  # the same thing differently.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)
  # Asserts the C++ header, the Python module and docs/interfaces/qos-profiles.md
  # all state the same numbers. Two implementations of one table are kept honest
  # by a test because ROS 2 has two client libraries and there is no way to have
  # only one.
  ament_add_pytest_test(qos_consistency test/test_qos_consistency.py)
  # The interface-contract baseline cross-cutting-testing.md requires: a
  # breaking change to a .msg/.srv/.action fails here rather than in a consumer
  # nobody thought about, months later, against a recording on disk.
  ament_add_pytest_test(interface_contract test/test_interface_contract.py)
  # The baseline above strips comments on purpose, so it cannot see a field
  # documented against the wrong limit. This covers that gap for the one field
  # family where the units are not implied by the name.
  ament_add_pytest_test(scaling_basis test/test_scaling_basis.py)
endif()

ament_package()
