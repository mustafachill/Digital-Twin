from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'robot_interface'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Mustafa Cil',
    maintainer_email='mustafacil@example.com',
    description='Independent robot interface with state machine and handoff protocol',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'robot_node = robot_interface.robot_node:main',
            'state_machine = robot_interface.state_machine:main',
            'handoff_coordinator = robot_interface.handoff_coordinator:main',
        ],
    },
)







