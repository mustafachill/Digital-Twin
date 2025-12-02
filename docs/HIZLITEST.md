# Önce eski process'leri temizle
pkill -9 -f gazebo; pkill -9 -f gzserver; pkill -9 -f rviz

# Simülasyonu başlat
cd ~/Desktop/Digital-Twin
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch digital_twin_environment lab_with_xarm5.launch.py