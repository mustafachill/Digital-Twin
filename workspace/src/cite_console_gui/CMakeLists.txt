cmake_minimum_required(VERSION 3.16)
project(cite_console_gui)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(cite_interfaces REQUIRED)
find_package(gz_gui_vendor REQUIRED)
find_package(gz-gui REQUIRED)
find_package(gz_plugin_vendor REQUIRED)
find_package(gz-plugin REQUIRED COMPONENTS register)
find_package(Qt5 REQUIRED COMPONENTS Core Qml Quick)
find_package(tinyxml2 REQUIRED)

# What the buttons may do, as a pure function of what the console last said.
# No Qt and no ROS, so the whole table is tested without a window or a graph.
add_library(cite_console_gui_enablement STATIC src/enablement.cpp src/selection.cpp)
target_include_directories(cite_console_gui_enablement PUBLIC include)
set_target_properties(cite_console_gui_enablement PROPERTIES POSITION_INDEPENDENT_CODE ON)

# The ROS half: one context of its own on the domain the window runs on, its own
# spin thread, and the console's names handed in - read off the plugin's
# configuration element by `read_console_names`. No Qt.
add_library(cite_console_gui_client STATIC
  src/console_view.cpp
  src/console_client.cpp
  src/console_config.cpp
)
target_include_directories(cite_console_gui_client PUBLIC include)
target_link_libraries(cite_console_gui_client cite_console_gui_enablement tinyxml2::tinyxml2)
ament_target_dependencies(cite_console_gui_client rclcpp rclcpp_action cite_interfaces)
set_target_properties(cite_console_gui_client PROPERTIES POSITION_INDEPENDENT_CODE ON)

# The gz-gui plugin. gz-gui loads `lib<filename>.so` for a config's
# `<plugin filename="CellConsole">`, and its QML from the embedded resource
# `:/CellConsole/CellConsole.qml`, so the library and the resource prefix are both
# named for the plugin.
add_library(CellConsole SHARED
  src/cell_console.cpp
  src/cell_console.hpp
  src/CellConsole.qrc
)
set_target_properties(CellConsole PROPERTIES AUTOMOC ON AUTORCC ON)
target_link_libraries(CellConsole
  cite_console_gui_client
  cite_console_gui_enablement
  gz-gui::gz-gui
  gz-plugin::register
  Qt5::Core
  Qt5::Qml
  Qt5::Quick
)

install(TARGETS CellConsole
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

# No `install(DIRECTORY include/ ...)`: the headers are this package's own seams
# for its tests, and nothing outside it includes them.

# gz-gui finds plugins on GZ_GUI_PLUGIN_PATH. This hook puts this package's lib
# directory there when the workspace is sourced, so nothing below L7 - not the
# launch that opens the window, not the plan - has to name this package.
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/hooks/gz_gui_plugin_path.dsv.in")

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_gtest REQUIRED)

  # Every state, every flag: which buttons the panel enables.
  ament_add_gtest(test_enablement test/test_enablement.cpp)
  target_link_libraries(test_enablement cite_console_gui_enablement)

  # The one place the contract's constants become the panel's: every
  # ConsoleState and TwinMode constant, read from the generated headers.
  ament_add_gtest(test_console_view test/test_console_view.cpp)
  target_link_libraries(test_console_view cite_console_gui_client)

  # The configuration's keys against the one the generator installs (A-02).
  find_package(ament_index_cpp REQUIRED)
  ament_add_gtest(test_console_config test/test_console_config.cpp)
  target_link_libraries(test_console_config cite_console_gui_client)
  ament_target_dependencies(test_console_config ament_index_cpp)

  # The sequences that keep or clear the operator's selected target, on the
  # holder the plugin delegates to, with views built by `view_from` (R-01).
  ament_add_gtest(test_selection test/test_selection.cpp)
  target_link_libraries(test_selection cite_console_gui_client)

  # The ROS half against a fake console on a graph of its own (P-R02).
  ament_add_gtest(test_console_client test/test_console_client.cpp TIMEOUT 120)
  target_link_libraries(test_console_client cite_console_gui_client)
endif()

ament_package()
