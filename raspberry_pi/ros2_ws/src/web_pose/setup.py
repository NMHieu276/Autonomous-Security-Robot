from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'web_pose'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ubuntu',
    maintainer_email='ubuntu@todo.todo',
    description='ROS2 nodes: MPU6050 IMU driver + STM32 UART bridge for Robot An Ninh SLAM',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'mpu6050_driver = web_pose.mpu6050_driver:main',
            'uart_bridge    = web_pose.uart_bridge:main',
        ],
    },
)
