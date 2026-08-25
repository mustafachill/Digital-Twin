cmake_minimum_required(VERSION 3.16)
project(cite_facility)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  ${PROJECT_NAME}/model_info.py
  ${PROJECT_NAME}/frame_server.py
  ${PROJECT_NAME}/topology_server.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_lint_auto_find_test_dependencies()
  ament_add_pytest_test(artifacts test/test_artifacts.py)
endif()

ament_package()
