# Robot Kol Kontrol Rehberi

Bu dosya, robot kolu simülasyonda nasıl çalıştırıp kontrol edeceğinizi açıklar.

---

## 1. Simülasyonu Başlatma

### Terminal 1: Simülasyon
```bash
# Proje klasörüne git
cd ~/Desktop/Digital-Twin

# ROS2 ortamını yükle
source /opt/ros/humble/setup.bash
source install/setup.bash

# Simülasyonu başlat (Gazebo + RViz + Controllers)
ros2 launch robot_arm_bringup sim.launch.py
```

> **Not:** Gazebo ve RViz pencereleri açılacak, robot kol görünecek.

---

## 2. Robot Kontrolü (Yeni Terminal)

### Terminal 2: Komut Gönderme
```bash
# Önce ROS2 ortamını yükle
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
source install/setup.bash
```

### Controller Durumunu Kontrol Et
```bash
ros2 control list_controllers
```
Beklenen çıktı:
```
joint_state_broadcaster     [active]
joint_trajectory_controller [active]
```

### Joint Pozisyonlarını Gör
```bash
ros2 topic echo /joint_states --once
```

---

## 3. Robot Hareketleri

### Home Pozisyonu (Tüm jointler 0)
```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'], \
  points: [{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

### Pozisyon 1 - Sağa Dönüş
```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'], \
  points: [{positions: [0.5, 0.3, -0.4, 0.2, 0.1, 0.3], time_from_start: {sec: 2}}]}}"
```

### Pozisyon 2 - Sola Dönüş
```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'], \
  points: [{positions: [-0.5, -0.3, 0.4, -0.2, 0.5, -0.3], time_from_start: {sec: 3}}]}}"
```

### Yukarı Uzanma
```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'], \
  points: [{positions: [0.0, 0.5, -0.5, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

### Öne Eğilme
```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'], \
  points: [{positions: [0.0, 0.0, 0.7, 0.5, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

---

## 4. Çoklu Nokta Trajectory (Sıralı Hareket)

Robotun birden fazla noktadan geçmesini istiyorsan:

```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {
    joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'],
    points: [
      {positions: [0.3, 0.2, -0.2, 0.1, 0.0, 0.0], time_from_start: {sec: 1}},
      {positions: [0.6, 0.4, -0.4, 0.2, 0.1, 0.2], time_from_start: {sec: 2}},
      {positions: [0.3, 0.2, -0.2, 0.1, 0.0, 0.0], time_from_start: {sec: 3}},
      {positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 4}}
    ]
  }}"
```

---

## 5. Joint Limitleri

| Joint | Min (rad) | Max (rad) | Açıklama |
|-------|-----------|-----------|----------|
| joint1 | -3.14 | 3.14 | Base rotation |
| joint2 | -1.57 | 1.57 | Shoulder pitch |
| joint3 | -2.36 | 2.36 | Elbow |
| joint4 | -1.57 | 1.57 | Wrist pitch |
| joint5 | -3.14 | 3.14 | Wrist roll |
| joint6 | -3.14 | 3.14 | Wrist yaw |

---

## 6. Simülasyonu Kapatma

Terminal 1'de (simülasyonun çalıştığı yer):
```
Ctrl + C
```

Eğer Gazebo kapanmazsa:
```bash
pkill -9 -f gazebo
pkill -9 -f gzserver
```

---

## 7. Sorun Giderme

### "Controller not active" hatası
```bash
# Controller durumunu kontrol et
ros2 control list_controllers

# Eğer inactive ise, yeniden spawn et
ros2 run controller_manager spawner joint_state_broadcaster
ros2 run controller_manager spawner joint_trajectory_controller
```

### Gazebo açılmıyor
```bash
# Eski process'leri temizle
pkill -9 -f gazebo
pkill -9 -f gzserver

# Tekrar başlat
ros2 launch robot_arm_bringup sim.launch.py
```

### RViz'de robot görünmüyor
- Fixed Frame: `world` olmalı
- RobotModel display'inde Description Topic: `/robot_description` olmalı

---

## Hızlı Başlangıç (Tek Seferde)

```bash
# Terminal 1
cd ~/Desktop/Digital-Twin && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch robot_arm_bringup sim.launch.py

# Terminal 2 (bekle, sonra)
cd ~/Desktop/Digital-Twin && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5','joint6'], points: [{positions: [0.5, 0.3, -0.4, 0.2, 0.1, 0.3], time_from_start: {sec: 2}}]}}"
```

