#!/usr/bin/env python3
"""
UART Bridge Node — Raspberry Pi <-> STM32F103 via GPIO UART.

Subscribes to:
  /cmd_vel      (geometry_msgs/Twist)  — velocity commands from web joystick / keyboard
  /robot_mode   (std_msgs/String)      — "AUTO" | "MANUAL" mode switch from web dashboard

Translates Twist → ASCII command string and sends over /dev/ttyAMA0 at 115200 baud.

Command protocol (sent to STM32, terminated with \\n):
  ON         forward
  BACK       backward
  LEFT       spin left
  RIGHT      spin right
  UP_LEFT    forward + left arc
  UP_RIGHT   forward + right arc
  DOWN_LEFT  backward + left arc
  DOWN_RIGHT backward + right arc
  AUTO       engage onboard obstacle avoidance on STM32
  OFF        stop / exit AUTO
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import serial
import time

# ── Tunables ────────────────────────────────────────────────
LIN_THRESH  = 0.05    # m/s dead-band for linear velocity
ANG_THRESH  = 0.15    # rad/s dead-band for angular velocity
SERIAL_PORT = '/dev/ttyAMA0'
BAUD        = 115200


def twist_to_cmd(lx: float, az: float) -> str:
    """Convert a Twist linear.x / angular.z to a discrete direction string."""
    fwd  = lx >  LIN_THRESH
    back = lx < -LIN_THRESH
    lft  = az >  ANG_THRESH
    rgt  = az < -ANG_THRESH

    if fwd  and lft: return 'UP_LEFT'
    if fwd  and rgt: return 'UP_RIGHT'
    if fwd:          return 'ON'
    if back and lft: return 'DOWN_LEFT'
    if back and rgt: return 'DOWN_RIGHT'
    if back:         return 'BACK'
    if lft:          return 'LEFT'
    if rgt:          return 'RIGHT'
    return 'OFF'


class UartBridge(Node):
    def __init__(self):
        super().__init__('uart_bridge')
        self._last_cmd   = ''
        self._auto_mode  = False
        self.ser         = None

        # Initial serial connection (wait 2s for STM32 to boot)
        self._open_serial(initial=True)

        # Reconnection watchdog — fires every 2s
        self._reconnect_timer = self.create_timer(2.0, self._check_serial)

        # Best-effort QoS for real-time velocity control
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.create_subscription(Twist,  '/cmd_vel',    self._on_vel,  qos)
        self.create_subscription(String, '/robot_mode', self._on_mode, 10)

        self.get_logger().info(f'uart_bridge ready on {SERIAL_PORT} @ {BAUD}')

    # ── Serial helpers ───────────────────────────────────────

    def _open_serial(self, initial: bool = False) -> bool:
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
            time.sleep(2.0 if initial else 0.2)
            self._last_cmd = ''
            self.get_logger().info('Serial connection established.')
            return True
        except Exception as e:
            self.ser = None
            self.get_logger().warn(f'Serial open failed: {e}')
            return False

    def _check_serial(self):
        """Periodic watchdog: attempt reconnect if port is closed."""
        if self.ser is None or not self.ser.is_open:
            self.get_logger().info('Attempting serial reconnect…')
            self._open_serial(initial=False)

    def _write(self, cmd: str):
        """Send a command string only if it differs from the previous one."""
        if cmd == self._last_cmd:
            return
        if self.ser is None or not self.ser.is_open:
            return
        try:
            self.ser.write(f'{cmd}\n'.encode('utf-8'))
            self.ser.flush()
            self._last_cmd = cmd
            self.get_logger().debug(f'TX → {cmd}')
        except Exception as e:
            self.get_logger().error(f'Serial write error: {e}')
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    # ── Topic callbacks ──────────────────────────────────────

    def _on_vel(self, msg: Twist):
        if self._auto_mode:
            return   # STM32 handles AUTO internally
        self._write(twist_to_cmd(msg.linear.x, msg.angular.z))

    def _on_mode(self, msg: String):
        mode = msg.data.strip().upper()
        if mode == 'AUTO':
            self._auto_mode = True
            self._write('AUTO')
        else:
            self._auto_mode = False
            self._write('OFF')

    # ── Shutdown ─────────────────────────────────────────────

    def stop_robot(self):
        """Best-effort stop command on shutdown."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b'OFF\n')
                self.ser.flush()
            except Exception:
                pass


def main(args=None):
    rclpy.init(args=args)
    node = UartBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        if node.ser and node.ser.is_open:
            node.ser.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
