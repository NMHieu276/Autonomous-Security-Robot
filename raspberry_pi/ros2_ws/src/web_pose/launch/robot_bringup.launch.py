import os
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    robot_bringup.launch.py
    =======================
    Launches all hardware-facing nodes for the Robot An Ninh SLAM platform:

      1. sllidar_node      — RPLidar A1M8 driver (→ /scan)
      2. laser_filter      — Range filter [0.15 m … 12.0 m] (→ /scan_filtered)
      3. TF base_link→laser  (LiDAR height 0.23 m above base_link)
      4. TF base_link→imu_link (IMU height 0.09 m above base_link)
      5. mpu6050_driver    — MPU6050 gyro → /imu/data @ 50 Hz
      6. uart_bridge       — ROS2 /cmd_vel + /robot_mode → STM32 UART
    """
    filter_config = os.path.join(
        os.path.expanduser('~'), 'ros2_ws', 'config', 'laser_filter.yaml'
    )

    return LaunchDescription([

        # ── 1. LiDAR driver ────────────────────────────────────
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            parameters=[{
                'serial_port':     '/dev/rplidar',
                'serial_baudrate': 115200,
                'frame_id':        'laser',
                'scan_mode':       'Standard',
            }],
            output='screen',
        ),

        # ── 2. Laser scan range filter ─────────────────────────
        Node(
            package='laser_filters',
            executable='scan_to_scan_filter_chain',
            name='laser_filter',
            parameters=[filter_config],
            remappings=[
                ('scan',          '/scan'),
                ('scan_filtered', '/scan_filtered'),
            ],
            output='screen',
        ),

        # ── 3. Static TF: base_link → laser ────────────────────
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='tf_base_laser',
            arguments=[
                '--x', '0.0', '--y', '0.0', '--z', '0.23',
                '--yaw', '0', '--pitch', '0', '--roll', '0',
                '--frame-id', 'base_link', '--child-frame-id', 'laser',
            ],
            output='screen',
        ),

        # ── 4. Static TF: base_link → imu_link ─────────────────
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='tf_base_imu',
            arguments=[
                '--x', '0.0', '--y', '0.0', '--z', '0.09',
                '--yaw', '0', '--pitch', '0', '--roll', '0',
                '--frame-id', 'base_link', '--child-frame-id', 'imu_link',
            ],
            output='screen',
        ),

        # ── 5. MPU6050 IMU driver ───────────────────────────────
        Node(
            package='web_pose',
            executable='mpu6050_driver',
            name='mpu6050_driver',
            output='screen',
        ),

        # ── 6. STM32 UART bridge ────────────────────────────────
        Node(
            package='web_pose',
            executable='uart_bridge',
            name='uart_bridge',
            output='screen',
        ),
    ])
