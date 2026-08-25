cmake_minimum_required(VERSION 3.16)
project(cite_simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(gz_sim_vendor REQUIRED)
find_package(gz-sim REQUIRED)
find_package(gz_plugin_vendor REQUIRED)
find_package(gz-plugin REQUIRED)
find_package(gz_math_vendor REQUIRED)
find_package(gz-math REQUIRED)

find_package(gz_transport_vendor REQUIRED)
find_package(gz-transport REQUIRED)
find_package(gz_msgs_vendor REQUIRED)
find_package(gz-msgs REQUIRED)

add_library(cite_grasp_attachment SHARED src/grasp_attachment.cpp)
target_include_directories(cite_grasp_attachment PRIVATE include)
target_link_libraries(cite_grasp_attachment
  gz-sim::core
  gz-plugin::register
  gz-math::core
)

add_library(cite_conveyor SHARED src/conveyor.cpp)
target_include_directories(cite_conveyor PRIVATE include)
target_link_libraries(cite_conveyor
  gz-sim::core
  gz-plugin::register
  gz-math::core
  gz-transport::core
  gz-msgs::core
)

# Built, and therefore compiled, linted and kept honest. It was in no target at
# all: 167 lines that nothing referenced, in which a compile error would have
# gone unnoticed indefinitely.
add_library(cite_break_beam SHARED src/break_beam.cpp)
target_include_directories(cite_break_beam PRIVATE include)
target_link_libraries(cite_break_beam
  gz-sim::core
  gz-plugin::register
  gz-math::core
  gz-transport::core
  gz-msgs::core
)

install(TARGETS cite_grasp_attachment cite_conveyor cite_break_beam
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

# No `install(DIRECTORY include/ ...)`. The headers under include/ hold the
# decision rules these plugins share, so that they can be tested without a
# simulator; nothing outside this package includes them, and nothing should.
# Installing them would advertise an API this package does not have — and the
# rule that was here pointed at an EMPTY, untracked directory, so a clean clone
# and every CI run failed at configure time with
# `ament_cmake_symlink_install_directory() can't find .../include/`.

# Gazebo finds system plugins on GZ_SIM_SYSTEM_PLUGIN_PATH. An environment hook
# puts this package's lib directory there, so a world can name the plugin without
# anyone having to remember to export a path — the failure mode otherwise is a
# plugin that silently does not load and a grasp that silently does not hold.
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/hooks/gz_plugin_path.dsv.in")

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_gtest REQUIRED)

  # The decision rules, without a simulator. A Gazebo system plugin is not
  # untestable: the part that decides whether a grasp is a grasp, whether a beam
  # is broken and whether a part is on a belt is pure geometry and pure set
  # membership, and every defect these lock down was in that part.
  ament_add_gtest(test_grasp_rules test/test_grasp_rules.cpp)
  target_include_directories(test_grasp_rules PRIVATE include)

  ament_add_gtest(test_zone_rules test/test_zone_rules.cpp)
  target_include_directories(test_zone_rules PRIVATE include)
  target_link_libraries(test_zone_rules gz-math::core)
endif()

ament_package()
