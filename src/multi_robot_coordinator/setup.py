from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'multi_robot_coordinator'

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
    description='Multi-robot coordination for assembly line pick and place',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'coordinator_node = multi_robot_coordinator.coordinator_node:main',
            'sensor_monitor = multi_robot_coordinator.sensor_monitor:main',
            'box_spawner = multi_robot_coordinator.box_spawner:main',
        ],
    },
)

