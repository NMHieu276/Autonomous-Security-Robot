# Setup Guide — Robot An Ninh SLAM

Hướng dẫn cài đặt từng bước cho Raspberry Pi 4.

---

## Mục lục

1. [Cài đặt Ubuntu Server 22.04](#1-cài-đặt-ubuntu-server-2204)
2. [Cài đặt ROS2 Humble](#2-cài-đặt-ros2-humble)
3. [Cấu hình LiDAR (RPLidar A1M8)](#3-cấu-hình-lidar-rplidar-a1m8)
4. [Cấu hình IMU (MPU6050 GY-521)](#4-cấu-hình-imu-mpu6050-gy-521)
5. [Cấu hình UART GPIO (STM32)](#5-cấu-hình-uart-gpio-stm32)
6. [Build ROS2 Workspace](#6-build-ros2-workspace)
7. [Cấu hình Camera IMX219](#7-cấu-hình-camera-imx219)
8. [CycloneDDS Cross-Machine](#8-cyclonedds-cross-machine)
9. [Mở cổng UFW](#9-mở-cổng-ufw)
10. [Chạy hệ thống](#10-chạy-hệ-thống)

---

## 1. Cài đặt Ubuntu Server 22.04

**Thông tin hệ thống:**
- Hostname: `robotanninh`
- Username: `ubuntu`
- Password: *(đặt mật khẩu mạnh của bạn khi cài Ubuntu)*
- Kết nối LiDAR qua USB Micro-B (cổng đen)

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y
sudo reboot

# Tạo swap 4GB (bổ sung RAM ảo)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Thiết lập ngôn ngữ
sudo apt install -y software-properties-common curl locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Kích hoạt kho Universe
sudo add-apt-repository universe -y
```

---

## 2. Cài đặt ROS2 Humble

```bash
# Thêm ROS2 repository
sudo apt install -y curl
export ROS_APT_SOURCE_VERSION=$(curl -s \
  https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
  | grep -F '"tag_name"' | awk -F\" '{print $4}')

curl -L -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $VERSION_CODENAME)_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb

# Cài ROS2 Humble base + tools
sudo apt update
sudo apt install -y ros-humble-ros-base ros-dev-tools

# Cài packages mở rộng
sudo apt install -y \
  ros-humble-slam-toolbox \
  ros-humble-rosbridge-suite \
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-laser-filters

# Cấu hình môi trường
echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc
echo 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' >> ~/.bashrc
echo 'export ROS_DOMAIN_ID=42' >> ~/.bashrc
source ~/.bashrc

# Đồng bộ thời gian (quan trọng cho ROS2 TF)
sudo apt install -y chrony
```

---

## 3. Cấu hình LiDAR (RPLidar A1M8)

```bash
# Thêm user vào nhóm dialout
sudo usermod -aG dialout ubuntu
sudo systemctl disable --now ModemManager

# Tạo udev rule để cố định /dev/rplidar
sudo nano /etc/udev/rules.d/99-rplidar.rules
```

Dán nội dung sau:
```
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="dialout", SYMLINK+="rplidar"
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger

# Kiểm tra
ls -la /dev/rplidar
```

---

## 4. Cấu hình IMU (MPU6050 GY-521)

```bash
# Kích hoạt I2C tốc độ cao trong config.txt
sudo nano /boot/firmware/config.txt
```

Thêm dòng:
```
dtparam=i2c_arm_baudrate=400000
```

```bash
# Nạp module i2c-dev khi boot
echo 'i2c-dev' | sudo tee /etc/modules-load.d/i2c.conf

# Cài công cụ và thư viện
sudo apt install -y i2c-tools python3-pip
pip3 install smbus2

# Phân quyền I2C cho user ubuntu
sudo groupadd -f i2c
sudo usermod -aG i2c ubuntu
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-i2c.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# Kiểm tra MPU6050 (phải thấy địa chỉ 0x68)
i2cdetect -y 1
```

---

## 5. Cấu hình UART GPIO (STM32)

```bash
# Vô hiệu hoá Bluetooth để giải phóng UART0 (ttyAMA0)
sudo nano /boot/firmware/config.txt
```

Thêm dòng:
```
dtoverlay=disable-bt
```

```bash
# Vô hiệu hoá service chiếm quyền UART
sudo systemctl mask serial-getty@ttyAMA0.service

# Xoá console=serial0 khỏi cmdline.txt (nếu có)
sudo sed -i 's/console=serial0,[0-9]* //' /boot/firmware/cmdline.txt

# Cài pyserial
pip3 install pyserial

sudo reboot
```

**Kiểm tra:**
```bash
# Sau khi reboot
ls -la /dev/ttyAMA0   # phải tồn tại
```

---

## 6. Build ROS2 Workspace

```bash
# Tạo workspace
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src

# Clone sllidar_ros2 driver
git clone https://github.com/Slamtec/sllidar_ros2.git

# Copy package web_pose từ repo này
# (hoặc clone trực tiếp nếu đã đẩy lên GitHub)
cp -r /path/to/repo/raspberry_pi/ros2_ws/src/web_pose ~/ros2_ws/src/

# Copy config
mkdir -p ~/ros2_ws/config
cp /path/to/repo/raspberry_pi/ros2_ws/config/laser_filter.yaml ~/ros2_ws/config/

# Cài laser_filters
sudo apt install -y ros-humble-laser-filters

# Resolve dependencies
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y

# Build
colcon build --packages-select web_pose sllidar_ros2 --symlink-install

# Source
echo 'source ~/ros2_ws/install/setup.bash' >> ~/.bashrc
source ~/.bashrc

# Kiểm tra
ros2 pkg list | grep web_pose
```

---

## 7. Cấu hình Camera IMX219

```bash
# Xoá cấu hình camera cũ và thêm driver IMX219
sudo sed -i '/camera_auto_detect/d' /boot/firmware/config.txt
sudo sed -i '/dtoverlay=imx219/d'   /boot/firmware/config.txt
echo "dtoverlay=imx219" | sudo tee -a /boot/firmware/config.txt

# Tăng CMA lên 128MB cho camera buffer
sudo sed -i -e 's/ cma=[^ ]*//g' -e '1s/$/ cma=128M/' /boot/firmware/cmdline.txt

# Udev rule cho DMA heap
echo 'SUBSYSTEM=="dma_heap", GROUP="video", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-dma-heap.rules

# Systemd service tạo symlink DMA heap
sudo tee /etc/systemd/system/dma-heap-cma.service << 'EOF'
[Unit]
Description=Create dma_heap linux,cma symlink for rpicam-apps
After=local-fs.target
[Service]
Type=oneshot
ExecStart=/bin/ln -sf /dev/dma_heap/reserved /dev/dma_heap/linux,cma
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dma-heap-cma.service
sudo usermod -aG video,render ubuntu

sudo reboot
```

### Build libcamera và rpicam-apps

> ⚠️ **Bước này mất 1–2 giờ** trên Pi 4. Nên chạy trong `screen` hoặc `tmux`.

```bash
# Cài build dependencies
sudo apt install -y \
  clang meson ninja-build pkg-config cmake \
  libyaml-dev python3-yaml python3-ply python3-jinja2 openssl \
  libdw-dev libunwind-dev libudev-dev \
  libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
  libpython3-dev pybind11-dev libevent-dev libtiff-dev \
  liblttng-ust-dev lttng-tools libgtest-dev \
  libboost-dev libboost-program-options-dev \
  libdrm-dev libexif-dev libjpeg-dev libpng-dev
sudo pip3 install --upgrade meson

# Build libcamera
cd ~
git clone https://github.com/raspberrypi/libcamera.git
cd libcamera
meson setup build --buildtype=release \
  -Dpipelines=rpi/vc4,rpi/pisp \
  -Dipas=rpi/vc4,rpi/pisp \
  -Dv4l2=true \
  -Dgstreamer=enabled \
  -Dtest=false \
  -Dlc-compliance=disabled \
  -Dcam=disabled \
  -Dqcam=disabled \
  -Ddocumentation=disabled \
  -Dpycamera=enabled
ninja -C build -j2
sudo ninja -C build install
sudo ldconfig

# Build rpicam-apps
cd ~
git clone https://github.com/raspberrypi/rpicam-apps.git
cd rpicam-apps
meson setup build \
  -Denable_libav=disabled \
  -Denable_drm=disabled \
  -Denable_egl=disabled \
  -Denable_qt=disabled \
  -Denable_opencv=disabled \
  -Denable_tflite=disabled \
  -Denable_hailo=disabled
meson compile -C build -j2
sudo meson install -C build
sudo ldconfig

# Kiểm tra
rpicam-still --list-cameras
```

### Copy web files

```bash
mkdir -p ~/web
cp /path/to/repo/web/cam_stream.py ~/web/
cp /path/to/repo/web/index.html     ~/web/

# Tải roslib.min.js
curl -L -o ~/web/roslib.min.js \
  "https://cdn.jsdelivr.net/npm/roslib@1.3.0/build/roslib.min.js"
```

---

## 8. CycloneDDS Cross-Machine

> Cần thiết nếu rosbridge chạy trên máy Ubuntu VM riêng biệt.

```bash
sudo apt install -y avahi-daemon
sudo systemctl enable --now avahi-daemon

cat > ~/cyclone_dds.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<CycloneDDS>
  <Domain>
    <General>
      <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
    </General>
    <Discovery>
      <Peers>
        <Peer address="vmuser-virtual-machine.local"/>
      </Peers>
    </Discovery>
  </Domain>
</CycloneDDS>
EOF

echo 'export CYCLONEDDS_URI=file:///home/ubuntu/cyclone_dds.xml' >> ~/.bashrc
source ~/.bashrc
```

---

## 9. Mở cổng UFW

```bash
sudo ufw allow 8000   # web dashboard (HTTP server)
sudo ufw allow 8080   # camera MJPEG stream
sudo ufw allow 9090   # rosbridge WebSocket
sudo ufw reload
sudo ufw status
```

---

## 10. Chạy hệ thống

Mở 5 terminal (hoặc dùng `tmux`):

```bash
# Terminal 1 — Hardware nodes
ros2 launch web_pose robot_bringup.launch.py

# Terminal 2 — SLAM Toolbox
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=/opt/ros/humble/share/slam_toolbox/config/mapper_params_online_async.yaml

# Terminal 3 — ROS Bridge WebSocket
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# Terminal 4 — Camera MJPEG stream
python3 ~/web/cam_stream.py

# Terminal 5 — Web Dashboard HTTP server
cd ~/web && python3 -m http.server 8000
```

Mở trình duyệt: **`http://<địa-chỉ-IP-Pi>:8000`**

### Kiểm tra nhanh

```bash
# Kiểm tra các topic
ros2 topic list
ros2 topic hz /scan_filtered   # khoảng 8-10 Hz
ros2 topic hz /imu/data        # khoảng 50 Hz

# Kiểm tra kết nối UART với STM32
ros2 topic pub /cmd_vel geometry_msgs/Twist \
  "{ linear: {x: 0.1}, angular: {z: 0.0} }" --once
```

---

## Lưu bản đồ

Nhấn nút **"Serialize map"** trên web dashboard, hoặc:

```bash
ros2 service call /slam_toolbox/serialize_pose_graph \
  slam_toolbox/srv/SerializePoseGraph \
  "{ filename: '/home/ubuntu/my_map' }"
```

File `.posegraph` và `.data` sẽ được lưu trong `/home/ubuntu/`.
