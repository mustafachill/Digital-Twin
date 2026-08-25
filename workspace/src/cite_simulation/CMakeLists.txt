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

add_library(cite_grasp_attachment SHARED src/grasp_attachment.cpp)
target_include_directories(cite_grasp_attachment PRIVATE include)
target_link_libraries(cite_grasp_attachment
  gz-sim::core
  gz-plugin::register
  gz-math::core
)

install(TARGETS cite_grasp_attachment
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

# Gazebo finds system plugins on GZ_SIM_SYSTEM_PLUGIN_PATH. An environment hook
# puts this package's lib directory there, so a world can name the plugin without
# anyone having to remember to export a path — the failure mode otherwise is a
# plugin that silently does not load and a grasp that silently does not hold.
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/hooks/gz_plugin_path.dsv.in")

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
