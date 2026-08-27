cmake_minimum_required(VERSION 3.16)
project(cite_facility)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  ${PROJECT_NAME}/model_info.py
  ${PROJECT_NAME}/frame_server.py
  ${PROJECT_NAME}/planning_scene_loader.py
  ${PROJECT_NAME}/topology_server.py
  DESTINATION lib/${PROJECT_NAME}
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
  ament_add_pytest_test(artifacts test/test_artifacts.py)
  ament_add_pytest_test(topology_message test/test_topology_message.py)
  ament_add_pytest_test(planning_scene_loader test/test_planning_scene_loader.py)
  # Spawns the real node executables and signals them, so it needs a longer
  # budget than a unit test and must not run beside another copy of itself.
  ament_add_pytest_test(shutdown_under_signal test/test_shutdown_under_signal.py
    TIMEOUT 300
  )
endif()

ament_package()
