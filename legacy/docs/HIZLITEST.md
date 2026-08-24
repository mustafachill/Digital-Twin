# Önce eski process'leri temizle
pkill -9 -f gazebo; pkill -9 -f gzserver; pkill -9 -f rviz

# Simülasyonu başlat
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch digital_twin_environment lab_with_xarm5.launch.py

cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch assembly_line_bringup assembly_line.launch.py

# Başlat (%50 güç)
ros2 service call /conveyor/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 50.0}"

# Durdur
ros2 service call /conveyor/CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.0}"

ros2 topic pub --once /box_spawner/trigger std_msgs/msg/String "data: 'spawn'"

tamam, şimdi bu robotlardan ilki kutuyu alacak, banda koyacak, o kutuyu diğeri alacak banda koyacak, o kutuyu diğeri alacak banda koyacak

killall -9 gzserver gzclient 2>/dev/null
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch fleet_manager multi_robot_test.launch.py num_robots:=3