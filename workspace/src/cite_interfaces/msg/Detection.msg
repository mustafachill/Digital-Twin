# One detected object.

string workpiece_id
string workpiece_type
geometry_msgs/PoseStamped pose
float64 confidence                      # 0..1; 1.0 when the simulator reports
                                        # ground truth rather than a perception
                                        # estimate, so a consumer can tell the
                                        # difference
