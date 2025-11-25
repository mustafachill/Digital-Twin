# Install script for directory: /home/mustafacil/Desktop/Digital-Twin/src/ros2_control/transmission_interface

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/home/mustafacil/Desktop/Digital-Twin/install/transmission_interface")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set default install directory permissions.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/usr/bin/objdump")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  include("/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/ament_cmake_symlink_install/ament_cmake_symlink_install.cmake")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/gmock/cmake_install.cmake")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/gtest/cmake_install.cmake")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so")
    file(RPATH_CHECK
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so"
         RPATH "")
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/libtransmission_interface.so")
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so")
    file(RPATH_CHANGE
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so"
         OLD_RPATH "/home/mustafacil/Desktop/Digital-Twin/install/hardware_interface/lib:/home/mustafacil/ros2_humble/install/class_loader/lib:/home/mustafacil/ros2_humble/install/action_msgs/lib:/home/mustafacil/ros2_humble/install/unique_identifier_msgs/lib:/home/mustafacil/ros2_humble/install/sensor_msgs/lib:/home/mustafacil/ros2_humble/install/trajectory_msgs/lib:/home/mustafacil/ros2_humble/install/geometry_msgs/lib:/home/mustafacil/ros2_humble/install/std_msgs/lib:/home/mustafacil/ros2_humble/install/rclcpp_lifecycle/lib:/home/mustafacil/ros2_humble/install/rclcpp/lib:/home/mustafacil/ros2_humble/install/libstatistics_collector/lib:/home/mustafacil/ros2_humble/install/rosgraph_msgs/lib:/home/mustafacil/ros2_humble/install/statistics_msgs/lib:/home/mustafacil/ros2_humble/install/rcl_lifecycle/lib:/home/mustafacil/ros2_humble/install/lifecycle_msgs/lib:/home/mustafacil/ros2_humble/install/rcl/lib:/home/mustafacil/ros2_humble/install/rcl_interfaces/lib:/home/mustafacil/ros2_humble/install/builtin_interfaces/lib:/home/mustafacil/ros2_humble/install/rosidl_typesupport_fastrtps_c/lib:/home/mustafacil/ros2_humble/install/rosidl_typesupport_introspection_cpp/lib:/home/mustafacil/ros2_humble/install/rosidl_typesupport_introspection_c/lib:/home/mustafacil/ros2_humble/install/rosidl_typesupport_fastrtps_cpp/lib:/home/mustafacil/ros2_humble/install/fastcdr/lib:/home/mustafacil/ros2_humble/install/rosidl_typesupport_cpp/lib:/home/mustafacil/ros2_humble/install/rosidl_typesupport_c/lib:/home/mustafacil/ros2_humble/install/rcl_yaml_param_parser/lib:/home/mustafacil/ros2_humble/install/libyaml_vendor/lib:/home/mustafacil/ros2_humble/install/rmw_implementation/lib:/home/mustafacil/ros2_humble/install/ament_index_cpp/lib:/home/mustafacil/ros2_humble/install/rmw/lib:/home/mustafacil/ros2_humble/install/rcl_logging_spdlog/lib:/home/mustafacil/ros2_humble/install/rcl_logging_interface/lib:/home/mustafacil/ros2_humble/install/tracetools/lib:/home/mustafacil/ros2_humble/install/rosidl_runtime_c/lib:/home/mustafacil/ros2_humble/install/rcpputils/lib:/home/mustafacil/ros2_humble/install/rcutils/lib:/opt/ros/humble/lib:"
         NEW_RPATH "")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/usr/bin/strip" "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libtransmission_interface.so")
    endif()
  endif()
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/transmission_interface/cmake/export_transmission_interfaceExport.cmake")
    file(DIFFERENT EXPORT_FILE_CHANGED FILES
         "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/transmission_interface/cmake/export_transmission_interfaceExport.cmake"
         "/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/CMakeFiles/Export/share/transmission_interface/cmake/export_transmission_interfaceExport.cmake")
    if(EXPORT_FILE_CHANGED)
      file(GLOB OLD_CONFIG_FILES "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/transmission_interface/cmake/export_transmission_interfaceExport-*.cmake")
      if(OLD_CONFIG_FILES)
        message(STATUS "Old export file \"$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/transmission_interface/cmake/export_transmission_interfaceExport.cmake\" will be replaced.  Removing files [${OLD_CONFIG_FILES}].")
        file(REMOVE ${OLD_CONFIG_FILES})
      endif()
    endif()
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/transmission_interface/cmake" TYPE FILE FILES "/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/CMakeFiles/Export/share/transmission_interface/cmake/export_transmission_interfaceExport.cmake")
  if("${CMAKE_INSTALL_CONFIG_NAME}" MATCHES "^()$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/transmission_interface/cmake" TYPE FILE FILES "/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/CMakeFiles/Export/share/transmission_interface/cmake/export_transmission_interfaceExport-noconfig.cmake")
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "/home/mustafacil/Desktop/Digital-Twin/build/transmission_interface/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
