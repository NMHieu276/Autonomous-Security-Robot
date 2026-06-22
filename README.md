# ROS2 Autonomous Security Robot: Core SLAM & Embedded Navigation System

An integrated, end-to-end hardware and software architecture for an autonomous security and patrol robot. The system utilizes a hybrid computing model: a **Raspberry Pi 4** handles high-level spatial computing (ROS2 Humble under Ubuntu Server), while an **STM32 micro-controller** executes real-time low-level hardware control, peripheral management, and hardware-level obstacle avoidance. Teleoperation and live data visualization are delivered via an asynchronous web-based dashboard.

---

## 🛠️ System Architecture & Hardware Stack

### 1. Component Specification
| Core Function | Hardware Component | Software Environment / Driver |
| :--- | :--- | :--- |
| **Low-Level Motor Control** | STM32F103C8T6 (Blue Pill) | Embedded C / PlatformIO & Arduino |
| **Main Processing Unit** | Raspberry Pi 4 Model B (4GB) | Ubuntu Server 22.04 LTS + ROS2 Humble |
| **Spatial Range Sensing** | RPLidar A1M8 | `sllidar_ros2` + `slam_toolbox` |
| **Inertial Measurement** | MPU6050 GY-521 | Custom I2C ROS2 Driver Node |
| **Visual Feed** | IMX219 Raspberry Pi Camera v2 | `rpicam-vid` (MJPEG Pipeline) |
| **Remote Teleoperation** | Cross-platform Web Browser | `rosbridge_suite` + Native JavaScript |

### 2. Data Flow Map

```

┌─────────────────────────────────────────────────────┐
│                  MAIN COMPUTE (Raspberry Pi 4)      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  slam_   │  │rosbridge │  │   cam_stream.py  │  │
│  │ toolbox  │  │  :9090   │  │   (MJPEG :8080)  │  │
│  └────┬─────┘  └────┬─────┘  └──────────────────┘  │
│       │ /map        │ WebSocket                      │
│  ┌────┴──────────────────────────────────────┐       │
│  │         ROS2 Humble Ecosystem (CycloneDDS) │       │
│  │  /scan_filtered  /imu/data  /cmd_vel      │       │
│  └──┬─────────────┬──────────────────────────┘       │
│     │             │                                   │
│  ┌──┴──────┐  ┌───┴─────────┐                        │
│  │RPLidar  │  │  MPU6050    │  uart_bridge.py         │
│  │ A1M8    │  │  GY-521     │  GPIO UART Stream       │
│  └─────────┘  └─────────────┘                        │
└──────────────────────────┬──────────────────────────┘
│ UART Link (115200 baud)
▼
┌─────────────────────────────────────────────────────┐
│            ACTUATION LAYER (STM32F103)              │
│  Hardware PWM · HC-SR04 Ultrasonic · Auto-Avoidance │
└─────────────────────────────────────────────────────┘
▲
│ Wireless WebSocket (:9090)
▼
┌─────────────────────────────────────────────────────┐
│              OPERATOR DASHBOARD (Web Browser)       │
│    Real-time SLAM Map · Telemetry · Video Stream    │
└─────────────────────────────────────────────────────┘

```

---

## 📂 Project Directory Structure


```

quangem/
├── stm32/
│   └── robot_STM32.ino          # Microcontroller firmware execution loop
├── raspberry_pi/
│   └── ros2_ws/
│       ├── src/
│       │   └── web_pose/        # Custom Python-based ROS2 abstraction package
│       │       ├── web_pose/
│       │       │   ├── mpu6050_driver.py   # I2C IMU data publisher
│       │       │   └── uart_bridge.py      # ROS2 velocity to UART translator
│       │       └── launch/
│       │           └── robot_bringup.launch.py
│       └── config/
│           └── laser_filter.yaml           # Scan range filtering configuration
└── web/
├── index.html               # Unified control dashboard frontend
└── cam_stream.py            # Independent MJPEG video broadcasting utility

```

---

## ⚡ Deployment & Initialization

### Phase 1: Actuation Firmware Deployment (STM32)
Compile and flash `stm32/robot_STM32.ino` via **Arduino IDE** or **PlatformIO** using the `STM32duino` core wrapper.
* **Target Board:** Generic STM32F1 series (BluePill F103C8)
* **Flashing Interface:** ST-Link V2 or USB-to-TTL Adapter (UART1 on PA9/PA10)
* **Bus Speed:** 115200 baud

### Phase 2: Host Operating System Configuration (Pi 4)
Refer to the comprehensive installation workflow in [`docs/setup_guide.md`](docs/setup_guide.md).

> [!IMPORTANT]
> **Thông tin đăng nhập hệ thống (Pi Credentials)**  
> Khi cài đặt hệ điều hành Ubuntu Server 22.04, hãy thiết lập tài khoản quản trị cục bộ. Mã nguồn này mặc định cấu hình theo phân quyền:
> - **Username:** `ubuntu` (Có thể tùy chỉnh lại theo nhu cầu thiết lập).
> - **Password:** *(Người dùng tự cấu hình khi cài đặt — **Tuyệt đối không** commit mật khẩu lên hệ thống quản lý mã nguồn).*
>
> Nếu thay đổi tài khoản mặc định, đảm bảo cập nhật lại đối số lệnh phân quyền: `sudo usermod -aG ... <your_username>`.

To compile the workspace on the host Linux distribution:
```bash
# Initialize and source ROS2 workspace
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone [https://github.com/Slamtec/sllidar_ros2.git](https://github.com/Slamtec/sllidar_ros2.git)

# Migrate local packages to execution workspace
cp -r /path/to/repo/raspberry_pi/ros2_ws/src/web_pose .
cp -r /path/to/repo/raspberry_pi/ros2_ws/config ~/ros2_ws/

# Resolve dependencies and execute build pipeline
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source ~/.bashrc

```

### Phase 3: System Launch Sequence

Execute the stack concurrently across isolated shell sessions:

```bash
# Session 1: Baseline Hardware Bringup (Sensors & Serial Bridges)
ros2 launch web_pose robot_bringup.launch.py

# Session 2: Asynchronous SLAM Mapping Pipeline
ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/opt/ros/humble/share/slam_toolbox/config/mapper_params_online_async.yaml

# Session 3: WebSocket Network Layer Bridge
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# Session 4: Visual Camera Broadcaster
python3 ~/web/cam_stream.py

# Session 5: Static Web Assets Server
cd ~/web && python3 -m http.server 8000

```

*Access the control interface by navigating to:* `http://<target-raspberry-pi-ip>:8000`

---

## 🔌 Hardware Interface & Pin Map

### Pinout: STM32 to Motor Driver Interface (L298N / TB6612)

| STM32 Peripheral Pin | Functional Mapping |
| --- | --- |
| **PA0** | Left Channel PWM (`ENA`) |
| **PA1** | Right Channel PWM (`ENB`) |
| **PA2** | Left Channel Direction Direction A (`IN1`) |
| **PA3** | Left Channel Direction Direction B (`IN2`) |
| **PA4** | Right Channel Direction Direction A (`IN3`) |
| **PA5** | Right Channel Direction Direction B (`IN4`) |

### Pinout: STM32 to HC-SR04 Ultrasonic Sensor

| STM32 Peripheral Pin | Sensor Pin |
| --- | --- |
| **PB8** | Trigger Signal (`TRIG`) |
| **PB9** | Echo Input Signal (`ECHO`) |

### Pinout: Pi 4 Host to STM32 Bridge

| Raspberry Pi 4 GPIO | STM32 Microcontroller Pin |
| --- | --- |
| **GPIO14 (TXD / Pin 8)** | RX1 (PA10 - 3.3V Tolerant) |
| **GPIO15 (RXD / Pin 10)** | TX1 (PA9 - 3.3V Tolerant) |
| **GND (Pin 6/9/14...)** | Ground Reference |

### Pinout: Pi 4 Host to MPU6050 IMU Sensor

| Raspberry Pi 4 GPIO | MPU6050 Pin |
| --- | --- |
| **GPIO2 (SDA / Pin 3)** | Serial Data (`SDA`) |
| **GPIO3 (SCL / Pin 5)** | Serial Clock (`SCL`) |
| **3.3V Power (Pin 1)** | VCC Input |
| **GND (Pin 9/25...)** | Ground Reference |

---

## 📡 Networking & Communication Protocols

### 1. Unified Web Dashboard Controls

* **Keyboard Mappings:** `W` (Forward), `S` (Reverse), `A` (CCW Spin), `D` (CW Spin), `Spacebar` (Emergency Stop Trigger).
* **Proportional Navigation:** On-screen virtual analog joystick supporting dynamic linear and angular scaling.
* **Autonomous Override:** On-board `AUTO NAV` switch to yield low-level routing autonomy directly to the micro-controller's sub-routine.

### 2. Serial ASCII Command Protocol (115200 Baud)

Commands are packaged as payload strings terminated via a newline literal (`\n`):

* `ON` / `BACK`: Continuous linear propulsion vectors.
* `LEFT` / `RIGHT`: Local coordinate spot-turns.
* `UP_LEFT` / `UP_RIGHT` / `DOWN_LEFT` / `DOWN_RIGHT`: Combined arc maneuvering vectors.
* `AUTO`: Relinquishes master control to the local ultrasonic hardware avoidance routine.
* `OFF` / `MANUAL`: Halts processing loop and re-establishes master teleoperation authority.

---

## 🎛️ ROS2 Computation Graphs

### Core Topic Registry

| ROS2 Topic | Message Data Type | Function Description |
| --- | --- | --- |
| `/scan` | `sensor_msgs/LaserScan` | Unfiltered, raw spatial array data from LiDAR |
| `/scan_filtered` | `sensor_msgs/LaserScan` | Range-bounded spatial array [0.15m – 12.0m] |
| `/imu/data` | `sensor_msgs/Imu` | High-frequency rotational acceleration vectors (50 Hz) |
| `/cmd_vel` | `geometry_msgs/Twist` | Target linear and angular multi-axis vectors |
| `/robot_mode` | `std_msgs/String` | Operational state reporting (`AUTO` / `MANUAL`) |
| `/map` | `nav_msgs/OccupancyGrid` | Generated dynamic SLAM spatial matrix map |
| `/robot_pose` | `geometry_msgs/PoseStamped` | Estimated coordinate positioning transformations |
| `/odom` | `nav_msgs/Odometry` | Derived spatial transformation odometry data |

---

## 📋 Software Dependencies

### Host Architecture (Raspberry Pi Stack)

```bash
# Core ROS2 Components
ros-humble-ros-base
ros-humble-slam-toolbox
ros-humble-rosbridge-suite
ros-humble-rmw-cyclonedds-cpp
ros-humble-laser-filters

# Target System Level Libraries
pip3 install smbus2 pyserial

```

### Actuation Firmware Layer (STM32 Stack)

* **BSP Layer:** `STM32duino` official board support definitions repository layout.
* **External Libraries:** None (Built entirely utilizing native low-overhead peripheral abstractions).

---

## 📄 Licensing & Acknowledgments

This framework is licensed under the terms of the **MIT License**.

Special credit and appreciation to the open-source projects providing foundations for this implementation:

* [Slamtec sllidar_ros2 Hardware Drivers](https://github.com/Slamtec/sllidar_ros2)
* [Steve Macenski's slam_toolbox Mapping Engine](https://github.com/SteveMacenski/slam_toolbox)
* [RobotWebTools Suite (rosbridge_suite & roslibjs)](https://github.com/RobotWebTools)

```

```
