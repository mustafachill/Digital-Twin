"""
xArm 5 Digital Twin simulation launch file.
Launches xArm 5 in Gazebo with MoveIt2 and RViz for digital twin simulation.
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Declare arguments
    add_gripper_arg = DeclareLaunchArgument(
        'add_gripper',
        default_value='false',
        description='Add gripper to the robot'
    )
    
    add_bio_gripper_arg = DeclareLaunchArgument(
        'add_bio_gripper',
        default_value='false',
        description='Add bio gripper to the robot'
    )
    
    dof_arg = DeclareLaunchArgument(
        'dof',
        default_value='5',
        description='Degrees of freedom (xArm 5 = 5)'
    )
    
    robot_type_arg = DeclareLaunchArgument(
        'robot_type',
        default_value='xarm',
        description='Robot type: xarm, lite, or uf850'
    )
    
    # Package paths
    pkg_xarm_moveit = FindPackageShare('xarm_moveit_config')
    
    # Include xArm 5 MoveIt Gazebo launch
    xarm5_moveit_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([pkg_xarm_moveit, 'launch', 'xarm5_moveit_gazebo.launch.py'])
        ]),
        launch_arguments={
            'add_gripper': LaunchConfiguration('add_gripper'),
            'add_bio_gripper': LaunchConfiguration('add_bio_gripper'),
        }.items()
    )

    return LaunchDescription([
        add_gripper_arg,
        add_bio_gripper_arg,
        dof_arg,
        robot_type_arg,
        xarm5_moveit_gazebo,
    ])

