# How far the model is from reality (P8).
#
# The twin's central claim is that measurements transfer. Every such claim is
# backed by a published number, and this is that number. It is meaningful only in
# SHADOW and VALIDATED modes; in SIM the fields are zero and `valid` is false,
# rather than being absent or silently stale.

std_msgs/Header header
string asset_id

bool valid                  # false whenever the mode makes divergence undefined

float64 joint_error_rms_rad     # rad, root mean square over the arm's joints
float64 joint_error_max_rad     # rad, worst single joint
float64 tcp_position_error_m    # m, tool centre point
float64 tcp_orientation_error_rad  # rad, angle of the relative rotation
float64 cycle_time_deviation_s  # s, signed: positive means the real cell is slower
float64 event_timing_deviation_s  # s, signed, for discrete transitions

string model_version        # the L0 model hash these numbers were measured against;
                            # a comparison across model versions is not valid
