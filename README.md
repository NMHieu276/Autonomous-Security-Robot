# 🤖 Autonomous Mobile Robot — SLAM Navigation

> **Robot An Ninh** — Autonomous security robot with real-time SLAM mapping, web dashboard control, and obstacle avoidance.  
> Built on **Raspberry Pi 4 + ROS2 Humble + STM32F103**.

---

## 📌 Project Overview

| Component | Hardware | Software |
|-----------|----------|----------|
| Motor Controller | STM32F103C8T6 (Blue Pill) | Arduino / PlatformIO |
| Main Computer | Raspberry Pi 4 Model B (4GB) | Ubuntu Server 22.04 LTS + ROS2 Humble |
| LiDAR | RPLidar A1M8 | sllidar_ros2 + slam_toolbox |
| IMU | MPU6050 GY-521 | Custom ROS2 driver (I2C) |
| Camera | IMX219 (Raspberry Pi Camera v2) | rpicam-vid MJPEG stream |
| Web Dashboard | Any browser on same LAN | rosbridge + vanilla JS |

### System Architecture

```
┌─────────────────────────────────────────────────────┐
│                Raspberry Pi 4                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  slam_   │  │rosbridge │  │   cam_stream.py  │  │
│  │ toolbox  │  │  :9090   │  │   (MJPEG :8080)  │  │
│  └────┬─────┘  └────┬─────┘  └──────────────────┘  │
│       │ /map        │ WebSocket                      │
│  ┌────┴──────────────────────────────────────┐       │
│  │         ROS2 Humble (CycloneDDS)          │       │
│  │  /scan_filtered  /imu/data  /cmd_vel      │       │
│  └──┬─────────────┬──────────────────────────┘       │
│     │             │                                   │
│  ┌──┴──────┐  ┌───┴─────────┐                        │
│  │RPLidar  │  │  MPU6050    │  uart_bridge.py         │
│  │ A1M8    │  │  GY-521     │  GPIO UART → STM32      │
│  └─────────┘  └─────────────┘                        │
└─────────────────────────────────────────────────────┘
            ↕ WebSocket ws://pi-ip:9090
┌─────────────────────────────────────────────────────┐
│               Web Browser (any device)               │
│  ┌────────────────────────────────────────────────┐  │
│  │  SLAM Map · Camera Feed · Joystick · D-pad     │  │
│  │          web/index.html (served by Pi)          │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
            ↕ UART (115200 baud, GPIO14/15)
┌─────────────────────────────────────────────────────┐
│                STM32F103C8T6                         │
│  Motor PWM · HC-SR04 Ultrasonic · AUTO obstacle avoid│
└─────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
quangem/
├── README.md
├── .gitignore
│
├── stm32/
│   └── robot_STM32.ino          # STM32 firmware (Arduino IDE / PlatformIO)
│
├── raspberry_pi/
│   └── ros2_ws/
│       ├── src/
│       │   └── web_pose/        # Custom ROS2 Python package
│       │       ├── web_pose/
│       │       │   ├── mpu6050_driver.py   # IMU → /imu/data
│       │       │   └── uart_bridge.py      # /cmd_vel → STM32 UART
│       │       ├── launch/
│       │       │   └── robot_bringup.launch.py
│       │       ├── package.xml
│       │       └── setup.py
│       └── config/
│           └── laser_filter.yaml           # LiDAR range filter config
│
└── web/
    ├── index.html               # SLAM Dashboard (served from Pi)
    └── cam_stream.py            # MJPEG camera server (:8080)
```

---

## ⚡ Quick Start

### 1. Flash STM32 Firmware

Open `stm32/robot_STM32.ino` in **Arduino IDE** with the **STM32duino** board package.

```
Board: Generic STM32F1 series → BluePill F103C8
Upload method: Serial (UART1 via USB-TTL adapter) or ST-Link
Baud rate: 115200
```

### 2. Set Up Raspberry Pi 4

Follow the detailed step-by-step guide in [`docs/setup_guide.md`](docs/setup_guide.md).

> [!IMPORTANT]
> **Thông tin đăng nhập Pi (credentials)**  
> Khi cài Ubuntu Server 22.04, bạn sẽ được yêu cầu tạo tài khoản. Dự án này dùng:
> - **Username:** `ubuntu` (tên mặc định — có thể đổi tuỳ ý)
> - **Password:** *(tự đặt trong quá trình cài đặt — **không** lưu mật khẩu thật vào repo)*
>
> Các lệnh trong hướng dẫn có dạng `sudo usermod -aG ... ubuntu` — thay `ubuntu` bằng username bạn đã chọn nếu khác.

**Quick summary:**

```bash
# 1. Install ROS2 Humble (Ubuntu 22.04 LTS)
# 2. Clone and build workspace
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone https://github.com/Slamtec/sllidar_ros2.git
# Copy the web_pose package from this repo
cp -r /path/to/this/repo/raspberry_pi/ros2_ws/src/web_pose .
cp -r /path/to/this/repo/raspberry_pi/ros2_ws/config ~/ros2_ws/

cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source ~/.bashrc
```


### 3. Launch the Robot

```bash
# Terminal 1 — Hardware nodes (LiDAR + IMU + UART bridge)
ros2 launch web_pose robot_bringup.launch.py

# Terminal 2 — SLAM
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=/opt/ros/humble/share/slam_toolbox/config/mapper_params_online_async.yaml

# Terminal 3 — ROS Bridge (WebSocket for dashboard)
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# Terminal 4 — Camera stream
python3 ~/web/cam_stream.py

# Terminal 5 — Web server
cd ~/web && python3 -m http.server 8000
```

Open browser: **`http://<pi-ip>:8000`**

---

## 🎮 Controls

| Input | Action |
|-------|--------|
| W / ↑ | Forward |
| S / ↓ | Backward |
| A / ← | Turn Left |
| D / → | Turn Right |
| Space | Emergency Stop |
| D-pad buttons | Same as keyboard |
| Analog Joystick | Smooth proportional control |
| AUTO NAV button | Toggle STM32 obstacle avoidance |

---

## 🔌 Hardware Wiring

### STM32 ↔ Motor Driver (L298N / TB6612)

| STM32 Pin | Function |
|-----------|----------|
| PA0 (ENA) | Left motor PWM |
| PA1 (ENB) | Right motor PWM |
| PA2 (IN1) | Left motor direction A |
| PA3 (IN2) | Left motor direction B |
| PA4 (IN3) | Right motor direction A |
| PA5 (IN4) | Right motor direction B |

### STM32 ↔ HC-SR04 Ultrasonic

| STM32 Pin | HC-SR04 |
|-----------|---------|
| PB8 (TRIG) | TRIG |
| PB9 (ECHO) | ECHO |

### Pi 4 ↔ STM32 (UART)

| Pi 4 GPIO | STM32 |
|-----------|-------|
| GPIO14 (TX, pin 8) | RX (PA10 / Serial1) |
| GPIO15 (RX, pin 10) | TX (PA9 / Serial1) |
| GND | GND |

> ⚠️ **Logic level**: Pi GPIO is 3.3V; STM32 Blue Pill is 3.3V tolerant on most pins. No level shifter needed for this configuration.

### Pi 4 ↔ MPU6050 (I2C)

| Pi 4 GPIO | MPU6050 |
|-----------|---------|
| GPIO2 (SDA, pin 3) | SDA |
| GPIO3 (SCL, pin 5) | SCL |
| 3.3V (pin 1) | VCC |
| GND | GND |

---

## 🗺️ SLAM Map Dashboard

The web dashboard (`web/index.html`) provides:

- **Live SLAM map** with robot position overlay (click minimap to expand)
- **LiDAR scan points** rendered in real-time
- **Camera feed** via MJPEG stream
- **Robot pose** (X, Y, Yaw)
- **Speed telemetry** (linear m/s, angular rad/s)
- **Map save** button (serializes pose graph to disk)
- **D-pad + analog joystick** (touch-friendly)
- **Keyboard shortcuts** (WASD / arrow keys)

---

## 🛠️ ROS2 Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/scan` | `sensor_msgs/LaserScan` | Raw LiDAR scan |
| `/scan_filtered` | `sensor_msgs/LaserScan` | Filtered scan [0.15–12m] |
| `/imu/data` | `sensor_msgs/Imu` | MPU6050 gyro Z (50 Hz) |
| `/cmd_vel` | `geometry_msgs/Twist` | Velocity commands |
| `/robot_mode` | `std_msgs/String` | "AUTO" / "MANUAL" |
| `/map` | `nav_msgs/OccupancyGrid` | SLAM occupancy map |
| `/robot_pose` | `geometry_msgs/PoseStamped` | Robot estimated pose |
| `/odom` | `nav_msgs/Odometry` | Odometry from SLAM |

---

## 📡 STM32 UART Command Protocol

Commands are sent as ASCII strings terminated with `\n` at 115200 baud:

| Command | Behavior |
|---------|----------|
| `ON` | Move forward |
| `BACK` | Move backward |
| `LEFT` | Spin left |
| `RIGHT` | Spin right |
| `UP_LEFT` | Forward + left arc |
| `UP_RIGHT` | Forward + right arc |
| `DOWN_LEFT` | Backward + left arc |
| `DOWN_RIGHT` | Backward + right arc |
| `AUTO` | Enable onboard obstacle avoidance |
| `OFF` / `MANUAL` | Stop / exit AUTO mode |

---

## 📋 Dependencies

### Raspberry Pi (Ubuntu 22.04 + ROS2 Humble)

```bash
# ROS2 packages
ros-humble-ros-base
ros-humble-slam-toolbox
ros-humble-rosbridge-suite
ros-humble-rmw-cyclonedds-cpp
ros-humble-laser-filters

# Python packages
pip3 install smbus2 pyserial
```

### STM32 (Arduino IDE)

- Board package: `STM32duino` (stm32duino.github.io)
- No extra libraries required

---

## 📄 License

This project is released under the **MIT License**.

---

## 🙏 Acknowledgements

- [Slamtec sllidar_ros2](https://github.com/Slamtec/sllidar_ros2)
- [ROS2 slam_toolbox](https://github.com/SteveMacenski/slam_toolbox)
- [rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite)
- [ROSLIB.js](https://github.com/RobotWebTools/roslibjs)
