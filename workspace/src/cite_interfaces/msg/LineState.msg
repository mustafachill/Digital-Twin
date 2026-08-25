# What the line as a whole is doing. Published by the L4 coordinator.

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
