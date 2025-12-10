# Scalable Multi-Robot Architecture

Bu doküman, Digital Twin projesinin ölçeklenebilir multi-robot mimarisini tanımlar.

## 1. Mimari Genel Bakış

### 1.1 Tasarım Prensipleri

| Prensip | Açıklama |
|---------|----------|
| **Bağımsızlık** | Her robot kendi namespace'inde bağımsız çalışır |
| **Ölçeklenebilirlik** | 1'den N'e kadar robot, config değişikliği ile |
| **Heterojenlik** | Farklı robot tipleri (xArm, UR, vs) aynı sistemde |
| **Loose Coupling** | Robotlar sadece pub/sub ile haberleşir |
| **Config-Driven** | Tüm sistem YAML config ile tanımlı |

### 1.2 Sistem Diyagramı

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GAZEBO WORLD                                    │
│                                                                              │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐           ┌─────────┐          │
│   │ Robot 1 │    │ Robot 2 │    │ Robot 3 │    ...    │ Robot N │          │
│   │ (spawn) │    │ (spawn) │    │ (spawn) │           │ (spawn) │          │
│   └────┬────┘    └────┬────┘    └────┬────┘           └────┬────┘          │
│        │              │              │                     │                │
└────────┼──────────────┼──────────────┼─────────────────────┼────────────────┘
         │              │              │                     │
         ▼              ▼              ▼                     ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐    ┌─────────────┐
│ /robot_1/   │  │ /robot_2/   │  │ /robot_3/   │    │ /robot_n/   │
│             │  │             │  │             │    │             │
│ Publishers: │  │ Publishers: │  │ Publishers: │    │ Publishers: │
│ - status    │  │ - status    │  │ - status    │    │ - status    │
│ - handoff   │  │ - handoff   │  │ - handoff   │    │ - handoff   │
│             │  │             │  │             │    │             │
│ Subscribers:│  │ Subscribers:│  │ Subscribers:│    │ Subscribers:│
│ - command   │  │ - command   │  │ - command   │    │ - command   │
│ - neighbor  │  │ - neighbor  │  │ - neighbor  │    │ - neighbor  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘    └──────┬──────┘
       │                │                │                  │
       │    ┌───────────┴───────────┐    │                  │
       │    │   DIRECT PUB/SUB      │    │                  │
       │    │   (neighbor comm)     │    │                  │
       │    └───────────────────────┘    │                  │
       │                                 │                  │
       └────────────────┬────────────────┴──────────────────┘
                        │
              ┌─────────▼─────────┐
              │  FLEET MANAGER    │
              │                   │
              │ - Config loader   │
              │ - Robot spawner   │
              │ - Health monitor  │
              └───────────────────┘
```

## 2. Configuration Yapısı

### 2.1 Fleet Configuration (`fleet_config.yaml`)

```yaml
# ============================================
# FLEET CONFIGURATION
# ============================================
# Bu dosya tüm robot fleet'ini tanımlar.
# Yeni robot eklemek için robots listesine ekleme yap.
# ============================================

fleet:
  name: "assembly_line_fleet"
  version: "1.0"
  
  # ==========================================
  # ROBOT DEFINITIONS
  # ==========================================
  robots:
    - id: "robot_1"
      type: "xarm5"              # Robot tipi (xarm5, xarm6, ur5, ur10, custom)
      enabled: true              # false yapılırsa spawn edilmez
      position:
        x: -0.5
        y: -1.2
        z: 0.8
        roll: 0.0
        pitch: 0.0
        yaw: 1.5708              # 90 derece - banda bakıyor
      config:
        add_gripper: true
        gripper_type: "xarm_gripper"
      
    - id: "robot_2"
      type: "xarm5"
      enabled: true
      position:
        x: -0.5
        y: 0.0
        z: 0.8
        roll: 0.0
        pitch: 0.0
        yaw: 1.5708
      config:
        add_gripper: true
        gripper_type: "xarm_gripper"
        
    - id: "robot_3"
      type: "xarm5"
      enabled: true
      position:
        x: -0.5
        y: 1.2
        z: 0.8
        roll: 0.0
        pitch: 0.0
        yaw: 1.5708
      config:
        add_gripper: true
        gripper_type: "xarm_gripper"

# ==========================================
# TOPOLOGY DEFINITION
# ==========================================
# Robotların birbirleriyle ilişkisini tanımlar.
# Her robot sadece upstream ve downstream'ini bilir.
# ==========================================

topology:
  type: "chain"                  # chain | star | mesh | custom
  
  stations:
    - id: "station_1"
      robot: "robot_1"
      role: "pick"               # pick | transfer | place | inspect
      upstream: "conveyor_entry" # Nereden alıyor (önceki robot veya conveyor)
      downstream: "robot_2"      # Kime veriyor (sonraki robot veya conveyor)
      sensor: "break_beam_1"     # İlişkili sensör
      pick_position: [0.0, -0.3, 0.15]   # Alma pozisyonu (relative)
      place_position: [0.3, 0.0, 0.15]   # Bırakma pozisyonu (relative)
      
    - id: "station_2"
      robot: "robot_2"
      role: "transfer"
      upstream: "robot_1"
      downstream: "robot_3"
      sensor: "break_beam_2"
      pick_position: [-0.3, 0.0, 0.15]
      place_position: [0.3, 0.0, 0.15]
      
    - id: "station_3"
      robot: "robot_3"
      role: "place"
      upstream: "robot_2"
      downstream: "conveyor_exit"
      sensor: "break_beam_3"
      pick_position: [-0.3, 0.0, 0.15]
      place_position: [0.0, 0.3, 0.15]

# ==========================================
# CONVEYOR CONFIGURATION
# ==========================================
conveyor:
  enabled: true
  length: 4.0                    # metre
  width: 0.45                    # metre
  speed: 0.1                     # m/s (varsayılan)
  entry_point: [0.0, -1.8, 0.8]  # Kutu giriş noktası
  exit_point: [0.0, 1.8, 0.8]    # Kutu çıkış noktası

# ==========================================
# SENSOR CONFIGURATION  
# ==========================================
sensors:
  break_beam_1:
    type: "break_beam"
    position: [0.0, -1.4, 0.85]
    topic: "/sensors/break_beam_1"
    
  break_beam_2:
    type: "break_beam"
    position: [0.0, -0.2, 0.85]
    topic: "/sensors/break_beam_2"
    
  break_beam_3:
    type: "break_beam"
    position: [0.0, 1.0, 0.85]
    topic: "/sensors/break_beam_3"
```

### 2.2 Robot Types Configuration (`robot_types.yaml`)

```yaml
# ============================================
# ROBOT TYPE DEFINITIONS
# ============================================
# Her robot tipi için URDF ve controller ayarları
# ============================================

robot_types:
  xarm5:
    description: "UFACTORY xArm 5 DOF"
    urdf_package: "xarm_description"
    urdf_file: "urdf/xarm5/xarm5.urdf.xacro"
    controller_config: "xarm_controller/config/xarm5_controllers.yaml"
    joints: ["joint1", "joint2", "joint3", "joint4", "joint5"]
    gripper:
      xarm_gripper:
        urdf_macro: "xarm_gripper"
        controller: "xarm_gripper_traj_controller"
        joints: ["drive_joint"]
        
  xarm6:
    description: "UFACTORY xArm 6 DOF"
    urdf_package: "xarm_description"
    urdf_file: "urdf/xarm6/xarm6.urdf.xacro"
    controller_config: "xarm_controller/config/xarm6_controllers.yaml"
    joints: ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
    
  # Gelecekte eklenebilir:
  # ur5:
  #   description: "Universal Robots UR5"
  #   urdf_package: "ur_description"
  #   ...
```

## 3. ROS2 Topic/Service Yapısı

### 3.1 Robot Namespace Yapısı

Her robot kendi namespace'inde izole çalışır:

```
/{robot_id}/
├── controller_manager/          # ros2_control
│   ├── list_controllers
│   └── ...
├── joint_states                 # sensor_msgs/JointState
├── {robot_id}_traj_controller/  # Trajectory action
│   └── follow_joint_trajectory
├── gripper_controller/          # Gripper action (varsa)
│   └── gripper_command
│
├── status                       # RobotStatus (custom msg) - PUBLISH
├── command                      # RobotCommand (custom msg) - SUBSCRIBE
├── handoff/
│   ├── ready                    # Bool - "Kutu almaya hazırım"
│   └── offering                 # Bool - "Kutu vermeye hazırım"
└── neighbor/
    ├── upstream_status          # Upstream robotun durumu - SUBSCRIBE
    └── downstream_ready         # Downstream robotun hazırlığı - SUBSCRIBE
```

### 3.2 Custom Message Definitions

#### RobotStatus.msg
```
# Her robot periyodik olarak publish eder

string robot_id
string state           # IDLE, MOVING, PICKING, HOLDING, PLACING, ERROR
string role            # pick, transfer, place

geometry_msgs/Pose current_pose
float64[] joint_positions

bool gripper_closed
bool has_payload       # Elinde kutu var mı

string upstream_id     # Kimden alıyor
string downstream_id   # Kime veriyor

builtin_interfaces/Time timestamp
```

#### RobotCommand.msg
```
# Fleet manager veya coordinator'dan gelir

string command_type    # PICK, PLACE, MOVE, HANDOFF, HOME, STOP, EMERGENCY
geometry_msgs/Pose target_pose
string target_robot    # Handoff için hedef robot

float64 timeout        # Komut timeout (saniye)
uint32 priority        # 0=normal, 1=high, 2=emergency
```

#### HandoffRequest.msg
```
# Robot arası transfer isteği

string from_robot
string to_robot
string payload_id      # Kutu/nesne ID

geometry_msgs/Pose handoff_position
float64 timeout
```

### 3.3 Global Topics

```
/fleet/
├── status             # Tüm robotların özet durumu
├── events             # Fleet olayları (spawn, error, vs)
└── emergency_stop     # Acil durdurma (tüm robotlar dinler)

/assembly_line/
├── box_tracking       # Kutu pozisyonları
├── production_stats   # Üretim istatistikleri
└── task_queue         # Bekleyen görevler
```

## 4. Robot Lifecycle

### 4.1 Spawn Sequence

```
1. Fleet Manager config'i okur
2. Her robot için:
   a. URDF generate et (robot_id ile parameterize)
   b. robot_state_publisher başlat (namespace ile)
   c. Gazebo'ya spawn et
   d. Controller'ları yükle ve aktive et
   e. Robot node'u başlat (topology bilgisi ile)
3. Robot node başlangıçta:
   a. Config'den neighbor'larını öğrenir
   b. Neighbor topic'lerine subscribe olur
   c. Kendi status'unu publish etmeye başlar
   d. IDLE state'e geçer
```

### 4.2 State Machine

```
                    ┌──────────────────┐
                    │      IDLE        │◀─────────────────┐
                    └────────┬─────────┘                  │
                             │ upstream_offering          │
                             ▼                            │
                    ┌──────────────────┐                  │
                    │   MOVING_TO_PICK │                  │
                    └────────┬─────────┘                  │
                             │ position_reached           │
                             ▼                            │
                    ┌──────────────────┐                  │
                    │     PICKING      │                  │
                    └────────┬─────────┘                  │
                             │ gripper_closed             │
                             ▼                            │
                    ┌──────────────────┐                  │
                    │     HOLDING      │                  │
                    └────────┬─────────┘                  │
                             │ downstream_ready           │
                             ▼                            │
                    ┌──────────────────┐                  │
                    │  MOVING_TO_PLACE │                  │
                    └────────┬─────────┘                  │
                             │ position_reached           │
                             ▼                            │
                    ┌──────────────────┐                  │
                    │     PLACING      │──────────────────┘
                    └──────────────────┘  gripper_opened
```

## 5. Handoff Protocol

### 5.1 Robot-to-Robot Transfer

```
Timeline:
─────────────────────────────────────────────────────────────────────────►

Robot A (upstream):
    [HOLDING]──publish(offering=true)──[wait]──[MOVING_TO_PLACE]──[PLACING]──[IDLE]
                     │                    ▲              │
                     │                    │              │
                     ▼                    │              ▼
Robot B (downstream):
    [IDLE]──subscribe(offering)──publish(ready=true)──[MOVING_TO_PICK]──[PICKING]──[HOLDING]
```

### 5.2 Handoff Pozisyon Hesaplama

```python
# İki robot arasındaki handoff noktası
def calculate_handoff_position(robot_a_pos, robot_b_pos):
    # Orta nokta + güvenli yükseklik
    handoff_x = (robot_a_pos.x + robot_b_pos.x) / 2
    handoff_y = (robot_a_pos.y + robot_b_pos.y) / 2
    handoff_z = max(robot_a_pos.z, robot_b_pos.z) + 0.1  # 10cm yukarı
    return Position(handoff_x, handoff_y, handoff_z)
```

## 6. Error Handling

### 6.1 Fault Tolerance

| Hata Durumu | Davranış |
|-------------|----------|
| Robot timeout | Neighbor'lara UNAVAILABLE status, skip edilir |
| Gripper fail | HOLDING state'de kalır, manual intervention gerekir |
| Collision detect | Emergency stop, tüm robotlar IDLE'a |
| Sensor fail | Fallback: zamanlama tabanlı handoff |

### 6.2 Recovery

```python
# Robot recovery sequence
def recover_robot(robot_id):
    1. Send STOP command
    2. Wait for motion complete
    3. Open gripper (drop payload if holding)
    4. Move to HOME position
    5. Clear error state
    6. Resume IDLE
```

## 7. Paket Yapısı

```
src/
├── fleet_manager/                    # Ana yönetim paketi
│   ├── fleet_manager/
│   │   ├── __init__.py
│   │   ├── fleet_manager_node.py     # Config okuma, spawn orchestration
│   │   ├── robot_spawner.py          # Gazebo spawn işlemleri
│   │   └── config_loader.py          # YAML parsing
│   ├── config/
│   │   ├── fleet_config.yaml         # Fleet tanımı
│   │   └── robot_types.yaml          # Robot tipi tanımları
│   ├── launch/
│   │   └── fleet.launch.py           # Ana launch dosyası
│   └── package.xml
│
├── robot_interface/                  # Robot node paketi
│   ├── robot_interface/
│   │   ├── __init__.py
│   │   ├── robot_node.py             # Bağımsız robot controller
│   │   ├── state_machine.py          # State machine implementation
│   │   ├── neighbor_comm.py          # Pub/sub neighbor iletişimi
│   │   └── trajectory_executor.py    # Hareket execution
│   ├── msg/
│   │   ├── RobotStatus.msg
│   │   ├── RobotCommand.msg
│   │   └── HandoffRequest.msg
│   ├── srv/
│   │   └── GetRobotInfo.srv
│   └── package.xml
│
└── assembly_coordinator/             # Üst seviye koordinasyon (opsiyonel)
    ├── assembly_coordinator/
    │   ├── coordinator_node.py       # Fleet-level orchestration
    │   └── task_scheduler.py         # Görev planlama
    └── package.xml
```

## 8. Kullanım

### 8.1 Temel Kullanım

```bash
# Fleet'i başlat (config'deki tüm robotlar spawn edilir)
ros2 launch fleet_manager fleet.launch.py

# Özel config ile
ros2 launch fleet_manager fleet.launch.py config:=my_fleet.yaml
```

### 8.2 Runtime Robot Ekleme

```bash
# Çalışırken yeni robot ekle
ros2 service call /fleet/spawn_robot fleet_manager/srv/SpawnRobot \
  "{robot_id: 'robot_4', robot_type: 'xarm5', x: -0.5, y: 2.0, z: 0.8}"
```

### 8.3 Monitoring

```bash
# Tüm robot durumları
ros2 topic echo /fleet/status

# Tek robot durumu
ros2 topic echo /robot_1/status

# Handoff events
ros2 topic echo /assembly_line/events
```

## 9. Örnek Senaryolar

### 9.1 Assembly Line (3 Robot)

```yaml
# Kutu akışı: Giriş → Robot1 → Robot2 → Robot3 → Çıkış
topology:
  type: chain
  stations:
    - {robot: robot_1, upstream: conveyor, downstream: robot_2}
    - {robot: robot_2, upstream: robot_1, downstream: robot_3}
    - {robot: robot_3, upstream: robot_2, downstream: conveyor}
```

### 9.2 Paralel İşleme (4 Robot)

```yaml
# 2 pick robotu, 2 place robotu
topology:
  type: custom
  stations:
    - {robot: robot_1, role: pick, downstream: [robot_3, robot_4]}
    - {robot: robot_2, role: pick, downstream: [robot_3, robot_4]}
    - {robot: robot_3, role: place, upstream: [robot_1, robot_2]}
    - {robot: robot_4, role: place, upstream: [robot_1, robot_2]}
```

### 9.3 Heterojen Fleet

```yaml
# Farklı robot tipleri
robots:
  - {id: heavy_1, type: ur10, role: pick_heavy}
  - {id: fast_1, type: xarm5, role: transfer}
  - {id: precise_1, type: xarm6, role: place_precise}
```

---

**Son Güncelleme:** 2025-12-04
**Versiyon:** 1.0







