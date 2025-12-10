from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'fleet_manager'

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
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*.xacro')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Mustafa Cil',
    maintainer_email='mustafacil@example.com',
    description='Scalable Fleet Manager for multi-robot systems',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fleet_manager_node = fleet_manager.fleet_manager_node:main',
            'config_loader = fleet_manager.config_loader:main',
            'robot_spawner = fleet_manager.robot_spawner:main',
        ],
    },
)







