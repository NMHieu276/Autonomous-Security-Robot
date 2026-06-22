#!/usr/bin/env python3
"""
MPU6050 GY-521 IMU Driver Node for ROS2 Humble.

Reads gyroscope Z-axis data via I2C and publishes to /imu/data.
Only angular velocity Z is used (yaw rate); other axes are masked.

Hardware: Raspberry Pi 4 <-> MPU6050 via I2C-1 (GPIO2=SDA, GPIO3=SCL)
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import smbus2
import math
import time

# ── Register map ────────────────────────────────────────────
MPU6050_ADDR  = 0x68
PWR_MGMT_1    = 0x6B
GYRO_CONFIG   = 0x1B
GYRO_XOUT_H   = 0x43   # X-axis high byte; Z = XOUT_H + 4

# ── Scale factor ────────────────────────────────────────────
# FS_SEL=0 → ±250°/s → 131 LSB per °/s
GYRO_SCALE    = 131.0
DEG2RAD       = math.pi / 180.0
SCALE_FACTOR  = DEG2RAD / GYRO_SCALE

# ── Calibration ─────────────────────────────────────────────
CALIBRATE_N   = 150    # ~3s of still measurements at 50Hz


class MPU6050Driver(Node):
    def __init__(self):
        super().__init__('mpu6050_driver')

        # Initialise I2C bus
        self.bus = smbus2.SMBus(1)

        # Wake up from sleep (default after power-on)
        self.bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0x00)
        time.sleep(0.1)

        # Set gyro full-scale to ±250°/s (FS_SEL=0)
        self.bus.write_byte_data(MPU6050_ADDR, GYRO_CONFIG, 0x00)
        time.sleep(0.05)

        # Calibrate gyro bias on start-up (keep robot still!)
        self._gz_offset = self._calibrate()

        self.pub = self.create_publisher(Imu, '/imu/data', 10)
        self.create_timer(0.02, self._publish)   # 50 Hz
        self.get_logger().info(
            f'MPU6050 ready  |  gz_offset = {math.degrees(self._gz_offset):.3f} deg/s'
        )

    # ── Helpers ──────────────────────────────────────────────

    def _read_i16(self, reg: int) -> int:
        """Read a signed 16-bit integer from two consecutive registers."""
        d = self.bus.read_i2c_block_data(MPU6050_ADDR, reg, 2)
        v = (d[0] << 8) | d[1]
        return v - 65536 if v >= 0x8000 else v

    def _calibrate(self) -> float:
        """Average CALIBRATE_N gyro-Z readings to estimate static bias."""
        self.get_logger().info(f'Calibrating gyro  ({CALIBRATE_N} samples) — keep robot still…')
        total = 0.0
        for _ in range(CALIBRATE_N):
            total += self._read_i16(GYRO_XOUT_H + 4)
            time.sleep(0.02)
        return (total / CALIBRATE_N) * SCALE_FACTOR

    # ── Timer callback ───────────────────────────────────────

    def _publish(self):
        try:
            d       = self.bus.read_i2c_block_data(MPU6050_ADDR, GYRO_XOUT_H, 6)
            v       = (d[4] << 8) | d[5]
            gz_raw  = v - 65536 if v >= 0x8000 else v
            gz_rads = (gz_raw * SCALE_FACTOR) - self._gz_offset

            msg = Imu()
            msg.header.stamp    = self.get_clock().now().to_msg()
            msg.header.frame_id = 'imu_link'

            msg.angular_velocity.z = float(gz_rads)

            # Only Z gyro is valid; mask off everything else
            msg.angular_velocity_covariance = [
                1e6, 0.0, 0.0,
                0.0, 1e6, 0.0,
                0.0, 0.0, 1e-4
            ]
            msg.linear_acceleration_covariance[0] = -1.0   # not provided
            msg.orientation_covariance[0]          = -1.0   # not provided

            self.pub.publish(msg)

        except Exception as e:
            self.get_logger().warn(f'IMU read error: {e}', throttle_duration_sec=3.0)


def main():
    rclpy.init()
    node = MPU6050Driver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
