"""
Launch file to view the robot arm in RViz with joint state publisher GUI.
This is useful for testing the URDF model before running the full simulation.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # Package directories
    pkg_description = get_package_share_directory('robot_arm_description')

    # URDF/Xacro file path
    xacro_file = os.path.join(pkg_description, 'urdf', 'robot_arm.urdf.xacro')

    # RViz config path
    rviz_config = os.path.join(pkg_description, 'rviz', 'view_robot.rviz')

    # Declare arguments
    use_sim_arg = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation mode (affects ros2_control hardware interface)'
    )

    use_gui_arg = DeclareLaunchArgument(
        'use_gui',
        default_value='true',
        description='Use joint state publisher GUI'
    )

    # Robot description from xacro - use_sim=false so no Gazebo plugin
    robot_description = ParameterValue(
        Command([
            'xacro ', xacro_file,
            ' use_sim:=', LaunchConfiguration('use_sim'),
            ' controller_config:=none'
        ]),
        value_type=str
    )

    # Robot state publisher node
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': False
        }]
    )

    # Joint state publisher (or GUI version)
    joint_state_publisher = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui',
        condition=IfCondition(LaunchConfiguration('use_gui'))
    )

    joint_state_publisher_no_gui = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        condition=UnlessCondition(LaunchConfiguration('use_gui'))
    )

    # RViz node
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config]
    )

    return LaunchDescription([
        use_sim_arg,
        use_gui_arg,
        robot_state_publisher,
        joint_state_publisher,
        joint_state_publisher_no_gui,
        rviz_node
    ])
