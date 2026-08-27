cmake_minimum_required(VERSION 3.16)
project(cite_runtime)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

ament_python_install_package(${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)

  # Registered by hand for the same two reasons cite_facility gives; see the
  # comment there and .flake8 at the repository root.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)

  # Spawns probe processes and signals them, so it needs a longer budget than a
  # unit test. The budget is arithmetic, not a guess: two spawning tests, each
  # bounded by DISCOVERY_DEADLINE_S + EXIT_DEADLINE_S = 60 + 30 in
  # test_shutdown_under_signal.py, is a 180 s worst case. 300 leaves 120 s of
  # margin so that a genuine failure surfaces as the test's own worded
  # assertion rather than as an opaque ctest timeout, which is what a
  # below-worst-case budget used to produce.
  ament_add_pytest_test(shutdown_under_signal test/test_shutdown_under_signal.py
    TIMEOUT 300
  )
endif()

ament_package()
