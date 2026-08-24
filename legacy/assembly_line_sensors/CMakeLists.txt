cmake_minimum_required(VERSION 3.8)
project(assembly_line_sensors)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(gazebo_ros REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(xacro REQUIRED)

# Install models
install(DIRECTORY
  models
  DESTINATION share/${PROJECT_NAME}
)

# Install urdf
install(DIRECTORY
  urdf
  DESTINATION share/${PROJECT_NAME}
)

# Install config
install(DIRECTORY
  config
  DESTINATION share/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

# Environment hooks for GAZEBO_MODEL_PATH
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/gazebo_model_path.dsv.in")

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

