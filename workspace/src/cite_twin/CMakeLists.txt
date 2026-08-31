cmake_minimum_required(VERSION 3.16)
project(cite_twin)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
# Not used by any CMake target here - this package installs Python only. Required
# so that these dependencies are checked at configure time instead of at import
# time, where a shared PYTHONPATH would satisfy them silently and no manifest
# would record it. Same reason as cite_facility's and cite_bringup's; see
# ADR-0034.
find_package(cite_bringup REQUIRED)
find_package(cite_facility REQUIRED)
find_package(cite_runtime REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  ${PROJECT_NAME}/twin_boundary.py
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

  # ADR-0050 decision 4 and SetMode.srv's header: which transitions are gated,
  # and that `force` cannot reach the gate. Pure logic - the hardware check is
  # injected, so both answers are driven without touching the environment.
  ament_add_pytest_test(mode test/test_mode.py)
  # ADR-0050 decision 2's table, one row per mode, including the two rows that
  # refuse and the one the record leaves undecided.
  ament_add_pytest_test(routing test/test_routing.py)
  # ADR-0050 decision 3's conjunction. The load-bearing case is that `valid` is
  # false for a NAMED term, so a change that makes it true has to confront that
  # term rather than slip past a boolean.
  ament_add_pytest_test(divergence test/test_divergence.py)
  # ADR-0050 decision 1 clause 3: no L5 endpoint carries a name a side already
  # owns. A static check over the generated plan, because the defect it guards
  # against produces no symptom at run time.
  ament_add_pytest_test(boundary test/test_boundary.py)
  # Every field of the result L5 hands the operator, and the ranking it hands it
  # under. The defect this holds shut is a manufactured custody belief: a Pick
  # returning SUCCESS with holding=false, which Pick.action calls impossible.
  ament_add_pytest_test(results test/test_results.py)

  # The node itself, against a plan that declares a counterpart. It brings no
  # cell up - neither side is running - which is exactly the case that has to
  # work: the monitor's job in this phase is to publish invalid samples that say
  # why they are invalid.
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_twin_boundary_launch.py TIMEOUT 300)
  # And the same node against a pair that answers: two fake sides, one process
  # each, one domain each. It is what shows a goal CROSSING the boundary and
  # two operands reaching the monitor - the thing four documents said nothing
  # automated could show, which was overstated. It brings no cell up either, so
  # nothing here is evidence about motion.
  add_launch_test(test/test_twin_boundary_paired_launch.py TIMEOUT 300)
endif()

ament_package()
