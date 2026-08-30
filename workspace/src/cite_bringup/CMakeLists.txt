cmake_minimum_required(VERSION 3.16)
project(cite_bringup)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
# Not used by any CMake target here - this package installs Python only. Required
# so that the dependency is checked at configure time instead of at import time,
# where a shared PYTHONPATH would satisfy it silently and no manifest would record
# it. Same reason as cite_facility's, and see ADR-0034.
find_package(cite_runtime REQUIRED)

ament_python_install_package(${PROJECT_NAME})

# ADR-0047 clause 3's readiness witness. A process that blocks on this side's own
# endpoints and exits, so that the gate chain ends on "serving" rather than on
# "started" - and so that the launch has something real to announce readiness on.
install(PROGRAMS
  ${PROJECT_NAME}/readiness_witness.py
  DESTINATION lib/${PROJECT_NAME}
)

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
  # ADR-0042 obliged every path that starts a Gazebo process to carry the
  # partition, and the promotion covered only the launch graph. The scenario
  # harness starts its own, and until this module existed they carried nothing
  # and hung at the work-piece spawn. One door, tested here; that nothing goes
  # around it is tests/scenarios/guards/.
  ament_add_pytest_test(gz test/test_gz.py)
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

  # ADR-0040. The gap ADR-0037 records against its own decision 8: no fixture
  # drove a genuine abort into L3. This one does, through a real move_group and
  # the real skill server, over `cite_test_hardware/JointStopSystem` — mock
  # hardware with a pair of hard stops on one joint, so the arm comes to rest
  # PART WAY along its trajectory rather than at its first point.
  #
  # It stands up a planner and a skill server for one arm and plans two motions,
  # which is why the timeout is twice the one above. Still no Gazebo.
  add_launch_test(test/test_abort_classification_launch.py TIMEOUT 600)

  # ADR-0045. The gripper deadline, driven to expiry in a clock the test owns.
  # The same shape of rig as the one above — generated description on mock
  # hardware, a real move_group, the real skill server — with two differences that
  # are the point: `use_sim_time` is TRUE and `/clock` comes from the test process,
  # and the gripper action is served by a fake that accepts a goal and never
  # answers. So the test can stop simulated time while wall time runs, which is
  # the only way to tell the two deadlines apart.
  add_launch_test(test/test_gripper_deadline_launch.py TIMEOUT 600)
endif()

ament_package()
