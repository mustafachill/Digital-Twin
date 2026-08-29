# How far the model is from reality (P8).
#
# The twin's central claim is that measurements transfer. Every such claim is
# backed by a published number, and this is that number.
#
# THE RULE, which is the part to read: `valid` is false whenever the mode makes
# divergence undefined, and when it is false the fields are zero rather than
# absent or silently stale. The rule decides every mode, including modes added
# after this file was written.
#
# The modes named below are an ILLUSTRATION of that rule and a PARTIAL list, not
# the rule itself. The metric is meaningful in SHADOW and VALIDATED; in SIM the
# fields are zero and `valid` is false. VIRTUAL_LEAD is deliberately absent
# rather than excluded: both sides move, so the metric is in principle
# computable, but nothing mirrors back, and whether `valid` is true there is an
# open question filed in docs/architecture/L5-twin-synchronization.md. Until that
# is answered the rule above governs. Do not read this list as having answered it
# by exclusion, and do not extend the list to close the question — the decision
# belongs in L5.

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
