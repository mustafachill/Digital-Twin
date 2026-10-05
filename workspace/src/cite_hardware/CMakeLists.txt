cmake_minimum_required(VERSION 3.16)
project(cite_hardware)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
# Not used by any CMake target here - this package installs Python only. Required
# so that these dependencies are checked at configure time instead of at import
# time, where a shared PYTHONPATH would satisfy them silently and no manifest
# would record it. Same reason as cite_twin's; see ADR-0034.
find_package(cite_interfaces REQUIRED)
find_package(cite_runtime REQUIRED)
find_package(xarm_msgs REQUIRED)
find_package(control_msgs REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  ${PROJECT_NAME}/track_adapter.py
  ${PROJECT_NAME}/gripper_relay.py
  ${PROJECT_NAME}/deadman.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)

  # Two linters in ament_lint_common are registered by hand rather than through
  # ament_lint_auto, because their defaults contradict conventions this
  # repository already follows. Same settlement as every other package here;
  # see .flake8 at the repository root.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)

  # The unit arithmetic between this system's units and the vendor's, and the
  # track command's reading. A unit confusion here moves a machine somewhere
  # valid and wrong, so every conversion is pinned without a graph.
  ament_add_pytest_test(mapping test/test_mapping.py)
  # The deadman's state machine: when it permits, when it trips, and that a
  # trip latches. Events in, state out, no clock.
  ament_add_pytest_test(liveness test/test_liveness.py)
  # Nothing is defaulted: a node configured without its facts refuses, naming
  # each one.
  ament_add_pytest_test(parameters test/test_parameters.py)
  # Interleavings that a launch test cannot place: a trip between the deadman's
  # decision to START and its send, a gate closing between the track adapter's
  # decision to move and its send. Nodes in this process with fake clients.
  ament_add_pytest_test(ordering test/test_ordering.py)

  # Each node against fake vendor endpoints held by the test process. Nothing
  # here reaches hardware: the fakes are services and an action server in the
  # test's own node, and they record what they were asked.
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_track_adapter_launch.py TIMEOUT 180)
  add_launch_test(test/test_gripper_relay_launch.py TIMEOUT 180)
  add_launch_test(test/test_deadman_launch.py TIMEOUT 180)
  # The vendor driver going away and coming back is a process ending: the
  # fake vendor there is a process of its own (test/fake_vendor_process.py).
  add_launch_test(test/test_deadman_vendor_launch.py TIMEOUT 180)
endif()

ament_package()
