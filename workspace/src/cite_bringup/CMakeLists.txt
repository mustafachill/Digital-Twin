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
#
# ADR-0058's lifecycle driver. The same shape, at the other end of the chain: it
# asks each managed node to configure and activate and confirms each with
# `get_state`, so that no transition event is load-bearing and everything
# downstream of the facility nodes is gated on one process exiting.
#
# Both are installed as PROGRAMS and both therefore need their executable bit in
# the tree - `test_every_installed_program_is_executable_in_the_tree` checks it,
# because a program that cannot exec produces no launch event at all.
# ADR-0065's grasp-hold bridge. The cell says what it holds and the simulation is
# told: it subscribes to one arm's `RobotState` and turns each change of custody
# into an attach or a detach on that arm's grasp-hold plugin, over the Gazebo
# transport. SIMULATION-ONLY - `simulation.launch.py` is the only thing in this
# repository that starts it, and `test_the_bridge_is_simulation_only.py` fails if
# that stops being true.
# ADR-0071's operator console server, which the pair supervisor starts once the
# twin boundary has announced. The node is `program/console.py`; this is the
# file `ros2 run` executes.
install(PROGRAMS
  ${PROJECT_NAME}/readiness_witness.py
  ${PROJECT_NAME}/lifecycle_driver.py
  ${PROJECT_NAME}/grasp_hold_bridge.py
  ${PROJECT_NAME}/hold_gate.py
  ${PROJECT_NAME}/cell_console.py
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
  # ADR-0070 item 6: what the physical side's launch refuses and the order it
  # would start the side in, read off the launch description; nothing starts.
  ament_add_pytest_test(hardware_launch test/test_hardware_launch.py)
  # R-05, R-09: the hold gate against cite_hardware's vendor fakes, each case
  # the real gate as a process; nothing reaches hardware.
  ament_add_pytest_test(hold_gate test/test_hold_gate.py TIMEOUT 180)
  # ADR-0054 clause 6: the reproduction refused end to end - L0 edit, generate,
  # load the plan, call the gate. The only assertion that runs the whole path
  # the defect ran, and the only one crossing `cite_tools` and `cite_bringup`,
  # which is why it drives the generator through the repository virtualenv in a
  # subprocess. It brings nothing up.
  ament_add_pytest_test(reproduction_refused test/test_the_reproduction_is_refused.py)
  # The one statement of the model a work-piece is spawned as. It was two — a
  # hand-written SDF string in each of the two scenarios that spawn one — and the
  # colour in it was authored in neither L0 nor anywhere else, which is half of
  # why the cell rendered black. Pure string building over a YAML document, so it
  # brings nothing up.
  ament_add_pytest_test(workpiece test/test_workpiece.py)
  # ADR-0042 obliged every path that starts a Gazebo process to carry the
  # partition, and the promotion covered only the launch graph. The scenario
  # harness starts its own, and until this module existed they carried nothing
  # and hung at the work-piece spawn. One door, tested here; that nothing goes
  # around it is tests/scenarios/guards/.
  ament_add_pytest_test(gz test/test_gz.py)
  # ADR-0048 clause 3. The key naming a controller manager's host left the plan,
  # and a document that still carries it must load rather than be refused - the
  # document most likely to carry it is a plan left in a stale build tree, where
  # the cause is a rebuild and not a key. Its own file so that the guard barring
  # that name from every other source file needs one exemption rather than a list.
  ament_add_pytest_test(removed_plan_key test/test_a_removed_plan_key_is_ignored.py)
  # The launch description itself: what it refuses to start, and what it stops
  # on. A correct check that nothing calls is the defect this catches, and it is
  # the one that was there.
  ament_add_pytest_test(simulation_launch test/test_simulation_launch.py)
  # ADR-0065 clause 3: a source check that the grasp-hold bridge is reachable
  # from no launch but the simulated one. It is the only simulation-only NODE
  # this repository starts, and nothing but a scan of the tree can say that it
  # stays that way - a launch file is data, and a reviewer reading one file
  # cannot see the other.
  ament_add_pytest_test(bridge_is_simulation_only
    test/test_the_bridge_is_simulation_only.py)
  # ADR-0065 clause 2 and CLAUDE.md §10: which transition produces which message,
  # and that a repeat produces none. Driven against a fake gz publisher, so it
  # brings no simulator up and needs no partition.
  ament_add_pytest_test(grasp_hold_bridge test/test_grasp_hold_bridge.py)
  # ADR-0047. The pair supervisor's failure rule and its boundary. The sides it
  # is driven against here are not ROS at all, which is the record's membership
  # test executed rather than asserted, and the import-graph check is what makes
  # "holds no rclpy context" reviewable.
  # The timeout is stated for the same reason the sibling below states one:
  # `ament_add_pytest_test` defaults to 60 s SILENTLY, and this file spends
  # about 36 s of it on an idle host — four tests here deliberately let a
  # ceiling expire, and that expiry is most of their runtime. 60% of a budget is
  # not a margin once `colcon test` runs this beside ten other packages on a
  # loaded machine, and the failure it produces is a bare number with no
  # sentence in it. **Nothing under test is lengthened by this**: the ceilings
  # those tests spend are the test file's own and are deliberately unchanged.
  ament_add_pytest_test(pair test/test_pair.py TIMEOUT 120)
  # ADR-0047 clause 3. `endpoints()` is the definition of "this side is up", and
  # a witness whose condition is almost empty exits 0 having checked almost
  # nothing - which the launch announces and the supervisor reports as a pair.
  ament_add_pytest_test(readiness_witness test/test_readiness_witness.py)
  ament_add_pytest_test(program test/test_program.py)
  # ADR-0071: the operator console's state machine against a fake cell - what
  # it refuses, the order it calls the program's library in, and what a stop
  # and a failure leave it in. No graph.
  ament_add_pytest_test(console_machine test/test_console_machine.py)
  # R2-05 (ADR-0071): the program sequencer's terminal lines and exit codes, and
  # their order against the calls, on a fake cell with a physical side. No graph.
  ament_add_pytest_test(cycle_terminal test/test_cycle_terminal.py)
  # ADR-0072: the operator's signal target - the one target table, what a
  # deployment offers, the per-target gates of the sequencer and the console,
  # and the pair's sides by the hardware opt-in. No graph.
  ament_add_pytest_test(signal_target test/test_signal_target.py)
  # N-01, S-01, R-05: a terminal client sees an operator console on its graph -
  # by the twin's mode or, via the plant, the arm's state - and the console sees
  # a terminal client by its one node name. A live graph on a domain of its own.
  ament_add_pytest_test(console_presence test/test_console_presence.py)
  # S-01 (ADR-0070): an initialization interrupted or unanswered once sent is
  # followed by the vendor's track stop; against fakes, on a domain of its own.
  ament_add_pytest_test(initialize_interrupted test/test_initialize_interrupted.py)
  # ADR-0058 clause 2. The driver's failure paths, driven against fake managed
  # nodes that advertise the two lifecycle services and answer them as the test
  # says - including one that transitions and never answers, which is the case
  # the record is about and the one a driver trusting the response gets wrong.
  # It brings nothing up: no simulator, no controller manager, no arm. The
  # timeout covers three runs that deliberately spend their whole ceiling.
  ament_add_pytest_test(lifecycle_driver test/test_lifecycle_driver.py TIMEOUT 120)

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

  # ADR-0052. The grasp predicate judges a stall against the width of the parts
  # this facility declares rather than against the width it commanded, and this
  # drives that decision through a real GripperActionController over the same
  # `cite_test_hardware/JointStopSystem` the two rigs above use — with the stops
  # on the gripper's drive joint instead of an arm joint, so the jaws come to
  # rest at a declared width and the controller reports the stall a part
  # produces.
  #
  # `launch_testing.parametrize` runs the whole rig TWICE, once with the stop
  # inside the window and once outside it, because the stop is read at `on_init`
  # from the description and no goal can move it. Hence a timeout of twice the
  # one above; still no Gazebo.
  add_launch_test(test/test_grasp_predicate_launch.py TIMEOUT 1200)

  # `GripperActionController` SUCCEEDS a command it has declared stalled, so an
  # open commanded onto a part that does not let go comes back SUCCESS and `Place`
  # retreated on it — dropping the box 39 mm above the belt, at a different point
  # on each side of a pair (ADR-0063's measurement table). `release_jaws` confirms
  # the release with the grasp predicate instead of reading the result code, and
  # this drives that through the real skill server against a fake gripper that
  # answers the way the real controller does.
  #
  # The same shape of rig as the three above — generated description on mock
  # hardware, a real move_group, the real skill server — with one arm and one fake
  # action server. The control and the defect are two `Place` goals in ONE rig,
  # differing in nothing but what the gripper reports, so the timeout is the
  # abort rig's rather than the parametrized one's: still no Gazebo, but two
  # grasps, two places and FOUR millimetre-scale motions in the control — the
  # `MoveTo home` each case plans from, then `Place`'s approach, descent and
  # retreat. The defect case makes three of the four: it fails at the release, so
  # the retreat it must not make is never planned.
  add_launch_test(test/test_release_confirmation_launch.py TIMEOUT 600)
endif()

ament_package()
