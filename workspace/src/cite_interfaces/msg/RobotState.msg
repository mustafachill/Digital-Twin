# The state of one manipulator, as the rest of the system understands it.
#
# This is a summary for orchestration and display, not a substitute for
# /joint_states — a consumer that needs joint-level data subscribes to the
# controller's own topic.

std_msgs/Header header        # stamp, and the frame positions are expressed in
string asset_id               # the L0 asset this concerns

uint8 STATE_UNKNOWN=0
uint8 STATE_IDLE=1
uint8 STATE_MOVING=2
uint8 STATE_HOLDING=3         # an object is grasped
uint8 STATE_FAULTED=4
uint8 state

geometry_msgs/Pose tool_pose  # tool centre point, in header.frame_id
float64[] joint_positions_rad # radians, ordered as the controller's joints parameter
float64[] joint_velocities_rad_s  # rad/s, same ordering
bool gripper_holding          # true when the end effector reports a stalled close
string held_workpiece_id      # empty when nothing is held
string active_skill           # empty when idle; the L3 action currently executing
