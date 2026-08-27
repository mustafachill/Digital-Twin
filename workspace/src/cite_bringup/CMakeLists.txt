cmake_minimum_required(VERSION 3.16)
project(cite_bringup)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

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
  # The plan reader is pure logic with no ROS runtime, so it is unit-tested here
  # rather than exercised only by bringing the whole cell up.
  ament_add_pytest_test(plan test/test_plan.py)
  # The launch description itself: what it refuses to start, and what it stops
  # on. A correct check that nothing calls is the defect this catches, and it is
  # the one that was there.
  ament_add_pytest_test(simulation_launch test/test_simulation_launch.py)

  # ADR-0036. The generator suite proves the `constraints:` block is emitted;
  # only a running controller proves the parameter names are ones
  # joint_trajectory_controller actually reads. A misspelled key generates
  # cleanly, loads cleanly, and restores the silent success the block removes.
  #
  # It stands up two controller managers over mock hardware — no Gazebo, no
  # planner — so the timeout is for process start-up and three action goals,
  # not for physics.
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_trajectory_constraints_launch.py TIMEOUT 300)
endif()

ament_package()
