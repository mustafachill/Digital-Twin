cmake_minimum_required(VERSION 3.16)
project(cite_test_hardware)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

# EVERYTHING IS INSIDE THIS BLOCK, and that is the decision rather than a
# convention (ADR-0040 decision 2). A build configured with -DBUILD_TESTING=OFF
# produces an ament package that declares no library, installs no library, and
# registers no pluginlib class — so `cite_test_hardware/JointStopSystem` does not
# resolve, and a production bring-up naming it fails to load rather than loading
# a test double.
#
# The second half of that guarantee is not here: the fixture refuses to
# initialise without a parameter the L0 model cannot express, so even where the
# class does resolve it cannot serve as a backend. Neither half is sufficient on
# its own, which is why there are two.
if(BUILD_TESTING)
  find_package(hardware_interface REQUIRED)
  find_package(pluginlib REQUIRED)
  find_package(rclcpp REQUIRED)
  find_package(rclcpp_lifecycle REQUIRED)

  add_library(joint_stop_system SHARED src/joint_stop_system.cpp)
  target_include_directories(joint_stop_system PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include/${PROJECT_NAME}>)
  ament_target_dependencies(joint_stop_system
    hardware_interface pluginlib rclcpp rclcpp_lifecycle)

  pluginlib_export_plugin_description_file(hardware_interface plugin_description.xml)

  install(TARGETS joint_stop_system
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin)
  install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

  find_package(ament_lint_auto REQUIRED)

  # Two linters in ament_lint_common are registered by hand rather than through
  # ament_lint_auto, because their defaults contradict conventions this
  # repository already follows and neither can be configured through the auto
  # path. Same block as cite_bringup, cite_skills and cite_facility carry, for
  # the same reason. See .flake8 at the repository root for the flake8 half.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)

  # What the fixture REFUSES. The structural half of ADR-0040 decision 2 — that a
  # component which will not start without a parameter L0 cannot express is not a
  # backend — is a property of this class, and without this file it rests on a
  # comment. Cheap, because a refusal needs nothing started.
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_refusal test/test_refusal.cpp src/joint_stop_system.cpp)
  target_include_directories(test_refusal PRIVATE include)
  ament_target_dependencies(test_refusal
    hardware_interface pluginlib rclcpp rclcpp_lifecycle)

  # The claim that a production launch path cannot reach this plugin, checked
  # rather than asserted. It is already covered twice over — by the refusal in
  # `on_init` and by ADR-0021's rule that the generated tree is never hand
  # edited, which `./scripts/validate-model` enforces by byte-diffing it — but
  # "covered by another gate" is not the same as tested.
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(unreachable test/test_unreachable.py)
endif()

ament_package()
