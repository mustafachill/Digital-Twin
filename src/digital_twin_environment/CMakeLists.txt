cmake_minimum_required(VERSION 3.8)
project(digital_twin_environment)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)

# Install worlds
install(DIRECTORY worlds/
  DESTINATION share/${PROJECT_NAME}/worlds
)

# Install models (for Gazebo model database)
install(DIRECTORY models/
  DESTINATION share/${PROJECT_NAME}/models
)

# Install materials (textures, scripts)
install(DIRECTORY materials/
  DESTINATION share/${PROJECT_NAME}/materials
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Environment hooks for GAZEBO_MODEL_PATH
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/gazebo_model_path.dsv.in")

ament_package()

