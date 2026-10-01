# A sensor observed something, or stopped observing it.
#
# Published as an EVENT-profile topic (reliable, keep-all): a missed transition
# is a work-piece the line never notices, and the station downstream then waits
# forever. This is the message that makes the line sensor-driven rather than
# timed.

std_msgs/Header header
string asset_id               # the sensor

uint8 STATE_CLEAR=0
uint8 STATE_BLOCKED=1
uint8 state                   # the state now being reported
uint8 previous_state          # what it was, so a consumer can detect an edge
                              # without keeping its own history

builtin_interfaces/Duration duration_in_previous_state
geometry_msgs/Point position  # where the detection occurred, in header.frame_id
string workpiece_id           # empty when the sensor cannot identify what it saw
