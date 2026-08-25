cmake_minimum_required(VERSION 3.16)
project(cite_bringup)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_lint_auto_find_test_dependencies()
  # The plan reader is pure logic with no ROS runtime, so it is unit-tested here
  # rather than exercised only by bringing the whole cell up.
  ament_add_pytest_test(plan test/test_plan.py)
endif()

ament_package()
