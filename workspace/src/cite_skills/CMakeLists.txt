cmake_minimum_required(VERSION 3.16)
project(cite_skills)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(cite_interfaces REQUIRED)
find_package(control_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(moveit_core REQUIRED)
find_package(moveit_msgs REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

add_executable(skill_server
  src/skill_server.cpp
  src/approach.cpp
  src/gripper.cpp
  src/joint_turn.cpp
  src/pose_goal.cpp
)
target_include_directories(skill_server PRIVATE include)
ament_target_dependencies(skill_server
  rclcpp rclcpp_action cite_interfaces control_msgs geometry_msgs
  moveit_core moveit_msgs moveit_ros_planning_interface tf2_ros tf2_geometry_msgs
)

install(TARGETS skill_server DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)

  # Two linters in ament_lint_common are registered by hand rather than through
  # ament_lint_auto, because their defaults contradict conventions this
  # repository already follows and neither can be configured through the auto
  # path. What they check is unchanged; only the two conflicting preferences are
  # settled. Same block as cite_bringup and cite_facility carry, for the same
  # reason. See .flake8 at the repository root for the flake8 half.
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

  # Approach and retreat geometry is pure arithmetic, so it is tested without a
  # planner, a simulator, or any waiting. Pushing it down here is what keeps the
  # scenario suite for things only a whole system can show.
  ament_add_gtest(test_approach test/test_approach.cpp src/approach.cpp)
  target_include_directories(test_approach PRIVATE include)
  ament_target_dependencies(test_approach geometry_msgs tf2_geometry_msgs)

  # The rule from ADR-0026 — solve IK on the exact pose, plan to the joint
  # configuration, and try more than one IK branch before calling a pose
  # unreachable — is sequencing, so it is tested as sequencing, with the planner
  # and the robot replaced by callables that record what was asked of them.
  ament_add_gtest(test_pose_goal test/test_pose_goal.cpp src/pose_goal.cpp)
  target_include_directories(test_pose_goal PRIVATE include)

  # Choosing between joint angles that are the SAME tool pose. `joint1` and
  # `joint5` are declared over two revolutions, so every reachable pose has a
  # wound twin 360 degrees away and IK returns whichever its seed landed near —
  # measured on the running cell as a 301 degree sweep where 59 would have done.
  #
  # Tested here because the rule is arithmetic over four doubles and the two
  # ways of getting it wrong are both invisible from a running cell: a version
  # that only tests `+/- 2*pi` once leaves the far branch wound, and one that
  # normalises into `[-pi, pi]` hands the planner an angle outside the joint's
  # declared limit. The second is the dangerous one, and a scenario would show
  # it as an unexplained planning refusal.
  #
  # NO ROS RUNTIME AND NO MOVEIT LIBRARY — the signature is plain doubles for
  # exactly this reason, the same bargain `test_motion_end` makes below.
  ament_add_gtest(test_joint_turn test/test_joint_turn.cpp src/joint_turn.cpp)
  target_include_directories(test_joint_turn PRIVATE include)

  # Gripper arithmetic: metres against the drive joint's own units, where the pad
  # face sits on the tool axis, and what a `Pick` closes to when the goal leaves
  # the width unset.
  ament_add_gtest(test_gripper test/test_gripper.cpp src/gripper.cpp)
  target_include_directories(test_gripper PRIVATE include)

  # Turning an object's pose into the tool pose that grasps it. The offset and
  # the offset-along-the-tool-axis each have their own tests above; what this
  # covers is their composition — the sign and the axis, both of which are free
  # to be wrong in a way that reads as plausible and moves the arm 37 mm the
  # wrong way in the cell.
  ament_add_gtest(
    test_grasp_pose test/test_grasp_pose.cpp src/approach.cpp src/gripper.cpp)
  target_include_directories(test_grasp_pose PRIVATE include)
  ament_target_dependencies(test_grasp_pose geometry_msgs tf2_geometry_msgs)

  # One arm, one goal. A concurrency invariant, tested as one — with threads,
  # not with a comment.
  ament_add_gtest(test_exclusive_goal test/test_exclusive_goal.cpp)
  target_include_directories(test_exclusive_goal PRIVATE include)

  # Where an arm ended up relative to the trajectory it was given (ADR-0037).
  # This decides whether a failure may be retried unattended or has to stop for
  # an operator, and the boundary cases it has to get right — a short trajectory
  # whose ends overlap, one mistracking joint among five that arrived, a joint
  # state that could not be read at all — cannot be produced on demand in a
  # simulator. So the rule is tested as a rule. No ROS runtime and no MoveIt.
  #
  # NO ROS RUNTIME AND NO MOVEIT LIBRARY. It links two generated message headers
  # — `cite_interfaces` for the `ResultCode` the classifier answers with, and
  # `moveit_msgs` for the two error-code values ADR-0037 decision 4 says survive
  # MoveIt's funnels intact — and nothing else. Neither brings a node, an
  # executor or a planner with it.
  ament_add_gtest(test_motion_end test/test_motion_end.cpp)
  target_include_directories(test_motion_end PRIVATE include)
  ament_target_dependencies(test_motion_end cite_interfaces moveit_msgs)

  # The parts of the action contract that only a running server can show:
  # goal exclusion, a cancel that reaches the gripper, and a reachable pose that
  # is planned to rather than refused. move_group, no simulator, no controllers —
  # so it runs headlessly in CI and still exercises the real binary.
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_skill_contract.py TIMEOUT 400)

  # What the generated MoveIt configuration is worth to a running move_group
  # (ADR-0027). Separate from the contract test above because it asks about the
  # PLANNER rather than about the skill: whether both pipelines loaded, whether
  # the default one can actually produce a trajectory — which is where a missing
  # deceleration limit shows up, and nowhere earlier — and whether the same
  # request produces the same trajectory twice. No skill server, no controllers.
  #
  # It also loads the cell's real planning scene and asks the question the
  # safety of ADR-0027 rests on: whether the response adapter that is now the
  # SOLE environment-collision gate refuses a path through the furniture, and
  # whether the identical request succeeds without it. That pair takes longer
  # than the rest of the file put together, which is what the raised timeout is
  # for.
  add_launch_test(test/test_planning_pipeline.py TIMEOUT 600)
endif()

ament_package()
