# What the line as a whole is doing. Published by the L4 coordinator.
#
# Published on the STATE profile (`cite_interfaces/qos`): reliable, volatile,
# depth 10. It is a periodic report of the present, not a record — a consumer
# that starts late wants the next one, not the last one.
#
# TOPIC below is the ONE place this name is written, and it is here for the same
# reason `LineTopology` carries its own: without it the name has to be supplied
# to the publisher as a parameter and repeated in every subscriber, which is a
# value in two places (P1) and is not discoverable with `ros2 interface show`
# (P3). `line_orchestrator` still reads `line_state_topic` as a parameter so that
# a test rig can publish somewhere private; what has changed is that bring-up now
# reads the default off this constant instead of writing the string again.

string TOPIC="/cite/line/state"

std_msgs/Header header
string asset_id               # the zone this line occupies; empty for facility scope

uint8 STATE_STOPPED=0
uint8 STATE_RUNNING=1
uint8 STATE_PAUSED=2
uint8 STATE_BLOCKED=3         # a station cannot proceed and the line is waiting
uint8 STATE_FAULTED=4
uint8 state

StationState[] stations
uint32 workpieces_completed
float64 cycle_time_s          # s, mean over the last completed cycles
float64 throughput_per_hour   # work-pieces per hour, over the same window
string blocked_reason         # empty unless state is BLOCKED
