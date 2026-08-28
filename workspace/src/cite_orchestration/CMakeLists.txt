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
# L3, for `cite_skills/observation.hpp` — the unobserved-pose predicate `PickAt`
# reads. A downward dependency (CLAUDE.md section 5) and a header-only one.
find_package(cite_skills REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

add_executable(line_coordinator src/line_coordinator.cpp)
target_include_directories(line_coordinator PRIVATE include)
ament_target_dependencies(line_coordinator
  rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs std_msgs
  tf2_ros
)

# The line. One subtree per station, instantiated from the L0 topology; the
# coordinator above runs one station in isolation, which is what ADR-0024 needs
# for a handoff to be testable with one arm.
add_executable(line_orchestrator src/line_orchestrator.cpp)
target_include_directories(line_orchestrator PRIVATE include)
ament_target_dependencies(line_orchestrator
  rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs std_msgs
  tf2_ros
)

install(TARGETS line_coordinator line_orchestrator DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY trees DESTINATION share/${PROJECT_NAME})

# No `install(DIRECTORY include/ ...)`. This package exports no headers; the one
# under include/ holds the behaviour-tree leaves so that a test can drive them,
# and nothing outside this package includes it. The rule that was here pointed at
# an EMPTY, untracked directory — git carries no empty directories, so a clean
# clone and every CI run failed at configure time with
# `ament_cmake_symlink_install_directory() can't find .../include/`, while
# developer machines passed because the directory happened to exist locally.

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  # Two linters in ament_lint_common are registered by hand rather than through
  # ament_lint_auto, because their defaults contradict conventions this
  # repository already follows and neither can be configured through the auto
  # path. What they check is unchanged; only the two conflicting preferences are
  # settled. The same block as cite_skills, cite_bringup and cite_facility carry,
  # for the same reason — this package needed it as soon as it gained its first
  # Python test. See .flake8 at the repository root for the flake8 half.
  #
  # pep257: the "ament" convention ignores D212 and therefore enforces D213 —
  # "summary should start at the second line". D212 and D213 are mutually
  # exclusive by construction, and every docstring in this repository puts the
  # summary on the first line.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)

  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)

  # The one number in this package that has to agree with the CELL, pinned
  # against the generated artifacts rather than against a copy of them.
  #
  # `DetectAt` asks `Detect` for a region about the station's pick frame, and the
  # extent it asked for was smaller than the distance the model puts every break
  # beam at — so no station could ever see its own sensor, and `Detect` answered
  # SUCCESS with an empty list every time. Nothing caught it: `cite_skills`'s
  # contract tests send a 100 m region on purpose, and `pick_and_place` never
  # calls `Detect` at all. This runs in milliseconds and reads the value out of
  # the header, so neither the layout nor the constant can move without it saying
  # so.
  ament_add_pytest_test(test_detection_region test/test_detection_region.py
    ENV CITE_SKILL_NODES_HEADER=${CMAKE_CURRENT_SOURCE_DIR}/include/cite_orchestration/skill_nodes.hpp)

  # The other number this package has to agree with the CELL about: which belts
  # the line indexes (ADR-0032). The rule is derived from the generated topology
  # and the drives come from the generated bring-up plan, and nothing else checks
  # that the two artifacts name the same set of belts. A belt in one and not the
  # other is a cell that refuses to come up, or a belt stopped for ever — both
  # of which cost a seven-minute scenario to discover and milliseconds here.
  # It also pins the indexing STAND-OFF, which is the number both this package's
  # belt comments quote and neither of them could keep true: the beam's placement
  # is derived from the work-piece (ADR-0033), so it moves whenever the part does.
  # The two files that state it in prose are handed to the test, which reads the
  # number out of them and checks it against the generated frames.
  ament_add_pytest_test(test_indexed_belts test/test_indexed_belts.py
    ENV
      CITE_CONVEYOR_INDEX_HEADER=${CMAKE_CURRENT_SOURCE_DIR}/include/cite_orchestration/conveyor_index.hpp
      CITE_STATION_TREE_XML=${CMAKE_CURRENT_SOURCE_DIR}/trees/line_station.xml)

  # Driven against a real action server, in-process. The defect under test is
  # what a leaf does to a SERVER when it gives up, so a mock would test the wrong
  # side of the boundary.
  ament_add_gtest(test_skill_cancellation test/test_skill_cancellation.cpp)
  target_include_directories(test_skill_cancellation PRIVATE include)
  ament_target_dependencies(test_skill_cancellation
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs
  )

  # What these leaves put in a goal, read from the far side of the action. A
  # leaf's whole job is turning ports into one typed goal, so the goal IS its
  # behaviour — and `PickAt` filled in a tool height where the action asks for
  # where the object is, which nothing could see until this existed.
  ament_add_gtest(test_skill_goals test/test_skill_goals.cpp)
  target_include_directories(test_skill_goals PRIVATE include)
  ament_target_dependencies(test_skill_goals
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs
  )

  # The rules the line is made of — single ownership, the two-party handoff and
  # its timeout, buffer and reach arbitration, the recovery policy, and the
  # translation from an L0 topology into a plan and a tree. Pure logic, so it is
  # provable without standing up a cell, which is exactly what ADR-0024 means by
  # a handoff being testable in isolation.
  ament_add_gtest(test_line_logic test/test_line_logic.cpp)
  target_include_directories(test_line_logic PRIVATE include)
  ament_target_dependencies(test_line_logic
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs std_msgs
  )

  # The operator reset (ADR-0037). What is under test is a set of REFUSALS —
  # a station that is not blocked, a station that is faulted, any station while
  # any other is faulted, a station this line does not have — and refusals are
  # the part of an operator control a happy-path test never reaches. It drives
  # the real `StationReset` through its real handler rather than a client,
  # because a client blocking on a future served by the same executor is the
  # deadlock every service test has to avoid.
  ament_add_gtest(test_station_reset test/test_station_reset.cpp)
  target_include_directories(test_station_reset PRIVATE include)
  ament_target_dependencies(test_station_reset
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs std_msgs
  )

  # The recovery branch's leaf ORDER, in both trees (ADR-0037). Read out of the
  # shipped XML, because the defect it guards against is not a wrong value but a
  # wrong sequence: a `MoveToHome` ahead of `RecoverFromFailure` plans and drives
  # a fresh trajectory before anything has asked whether the station is allowed
  # to move, and a test that only checked the final station state would pass with
  # the leaves in either order.
  #
  # It also reads the ROOT tree's fault branch (ADR-0038), and that one has no
  # shipped XML file: the root is generated in C++, so the branch is read out of
  # `line_tree.hpp` where it is written. The rule applied to it — that a stopped
  # line commands nothing — is the same `MOTION_LEAVES` set, which is why the
  # check is here rather than in a gtest that would need its own copy of the set.
  ament_add_pytest_test(test_recovery_ordering test/test_recovery_ordering.py
    ENV
      CITE_STATION_TREE_XML=${CMAKE_CURRENT_SOURCE_DIR}/trees/line_station.xml
      CITE_STATION_CYCLE_XML=${CMAKE_CURRENT_SOURCE_DIR}/trees/station_cycle.xml
      CITE_LINE_TREE_HEADER=${CMAKE_CURRENT_SOURCE_DIR}/include/cite_orchestration/line_tree.hpp
      CITE_LINE_ORCHESTRATOR_SRC=${CMAKE_CURRENT_SOURCE_DIR}/src/line_orchestrator.cpp)

  # Indexing the belt (ADR-0032), against a real publisher and a real
  # subscription in one process. What is under test is a decision about EVENTS —
  # which edge stops which belt, and which belt is left alone — so a fake that
  # called `stop()` directly would test the half that was never in doubt. The
  # setpoint is read back off the command topic, which is the only place the rest
  # of the system can see it.
  ament_add_gtest(test_conveyor_index test/test_conveyor_index.cpp)
  target_include_directories(test_conveyor_index PRIVATE include)
  ament_target_dependencies(test_conveyor_index
    rclcpp behaviortree_cpp cite_interfaces cite_skills geometry_msgs std_msgs
  )

  # The same rules, composed: a real behaviour tree with real in-process action
  # servers and a real sensor publisher, driving two stations through a handoff.
  # The logic tests prove each rule; this proves the tree wires them together,
  # which is the half that a unit test building its own expected values cannot
  # reach.
  ament_add_gtest(test_line_nodes test/test_line_nodes.cpp test/fake_arm.cpp TIMEOUT 180)
  target_include_directories(test_line_nodes PRIVATE include test)
  ament_target_dependencies(test_line_nodes
    rclcpp rclcpp_action behaviortree_cpp cite_interfaces cite_skills geometry_msgs std_msgs
  )
  # The station subtree under test is the one that ships, read from the source
  # tree rather than copied: a test that carried its own copy would keep passing
  # after the shipped tree changed.
  target_compile_definitions(test_line_nodes PRIVATE
    CITE_STATION_TREE="${CMAKE_CURRENT_SOURCE_DIR}/trees/line_station.xml")
  # No debug info for this one. It instantiates the client and server templates
  # for three action types alongside BehaviorTree.CPP, and with `-g` the single
  # translation unit exceeds the 2500 MB per-job budget ./scripts/build derives —
  # the OOM killer takes cc1plus out and reports a "fatal error" that names
  # neither memory nor this file. A test binary's debug info is not what anybody
  # is debugging.
  target_compile_options(test_line_nodes PRIVATE -g0)
endif()

ament_package()
