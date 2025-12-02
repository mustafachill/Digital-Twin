# Robot Kol Kontrol Rehberi

Bu dosya, robot kolu simülasyonda nasıl çalıştırıp kontrol edeceğinizi açıklar.

---

## xArm 5 Simülasyonu (MoveIt ile)

### Terminal 1: Simülasyonu Başlat
```bash
# Proje klasörüne git
cd ~/Desktop/Digital-Twin

# ROS2 ortamını yükle
source /opt/ros/humble/setup.bash
source install/setup.bash

# xArm 5 Simülasyonunu başlat (Gazebo + RViz + MoveIt + Controllers)
ros2 launch robot_arm_bringup xarm5_sim.launch.py
```

> **Not:** Gazebo ve RViz (MoveIt2 ile) pencereleri açılacak, xArm 5 robot kol görünecek.

---

## xArm 5 Kontrolü

### Terminal 2: Komut Gönderme
```bash
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
joint_state_broadcaster   [active]
xarm5_traj_controller     [active]
```

### Joint Pozisyonlarını Gör
```bash
ros2 topic echo /joint_states --once
```

---

## xArm 5 Hareketleri

### Home Pozisyonu (Tüm jointler 0)
```bash
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], \
  points: [{positions: [0.0, 0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

### Pozisyon 1 - Sağa Dönüş
```bash
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], \
  points: [{positions: [0.5, -0.3, 0.2, 0.5, 0.3], time_from_start: {sec: 2}}]}}"
```

### Pozisyon 2 - Sola Dönüş
```bash
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], \
  points: [{positions: [-0.5, 0.3, -0.2, -0.5, -0.3], time_from_start: {sec: 2}}]}}"
```

### Yukarı Uzanma
```bash
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], \
  points: [{positions: [0.0, -0.5, 0.5, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

### Öne Eğilme
```bash
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], \
  points: [{positions: [0.0, 0.3, 0.7, 0.5, 0.0], time_from_start: {sec: 2}}]}}"
```

---

## Çoklu Nokta Trajectory (Sıralı Hareket)

```bash
ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {
    joint_names: ['joint1','joint2','joint3','joint4','joint5'],
    points: [
      {positions: [0.3, -0.2, 0.2, 0.1, 0.0], time_from_start: {sec: 1}},
      {positions: [0.6, -0.4, 0.4, 0.2, 0.2], time_from_start: {sec: 2}},
      {positions: [0.3, -0.2, 0.2, 0.1, 0.0], time_from_start: {sec: 3}},
      {positions: [0.0, 0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 4}}
    ]
  }}"
```

---

## MoveIt2 İnteraktif Kontrol

RViz'de açılan MoveIt Motion Planning panelinde:
1. **Interactive Marker** ile robot ucunu sürükle
2. **Plan** butonuna bas - yol planla
3. **Execute** butonuna bas - hareketi uygula
4. **Plan & Execute** - tek seferde planla ve uygula

### MoveIt2 ile Programatik Kontrol
```bash
# MoveIt2 Python API ile hareket
ros2 run xarm_planner run_xarm_planner_node --ros-args -p dof:=5
```

---

## xArm 5 Joint Limitleri

| Joint | Min (rad) | Max (rad) | Açıklama |
|-------|-----------|-----------|----------|
| joint1 | -6.28 | 6.28 | Base rotation (±360°) |
| joint2 | -2.06 | 2.09 | Shoulder pitch |
| joint3 | -3.93 | 0.19 | Elbow |
| joint4 | -6.28 | 6.28 | Wrist pitch (±360°) |
| joint5 | -6.28 | 6.28 | Wrist roll (±360°) |

---

## Simülasyonu Kapatma

Terminal 1'de:
```
Ctrl + C
```

Eğer kapanmazsa:
```bash
pkill -9 -f gazebo
pkill -9 -f gzserver
pkill -9 -f rviz
```

---

## Sorun Giderme

### "Controller not active" hatası
```bash
ros2 control list_controllers

# Eğer inactive ise
ros2 run controller_manager spawner joint_state_broadcaster
ros2 run controller_manager spawner xarm5_traj_controller
```

### Gazebo açılmıyor
```bash
pkill -9 -f gazebo
pkill -9 -f gzserver
ros2 launch robot_arm_bringup xarm5_sim.launch.py
```

### RViz'de robot görünmüyor
- Fixed Frame: `world` veya `link_base` olmalı
- RobotModel display'inde Description Topic: `/robot_description` olmalı

---

## Hızlı Başlangıç (Tek Seferde)

```bash
# Terminal 1
cd ~/Desktop/Digital-Twin && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch robot_arm_bringup xarm5_sim.launch.py

# Terminal 2 (30 saniye bekle, sonra)
cd ~/Desktop/Digital-Twin && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 action send_goal /xarm5_traj_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory "{trajectory: {joint_names: ['joint1','joint2','joint3','joint4','joint5'], points: [{positions: [0.5, -0.3, 0.2, 0.5, 0.3], time_from_start: {sec: 2}}]}}"
```

---

## Eski Generic Model (Opsiyonel)

Eski 6-DOF generic model için:
```bash
ros2 launch robot_arm_bringup sim.launch.py
```
Controller: `/joint_trajectory_controller/follow_joint_trajectory`
Jointler: `joint1` - `joint6`
