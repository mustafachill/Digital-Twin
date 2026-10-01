# One station's contribution to the line state.

string station_id             # from the L0 topology
string actor_asset_id         # the robot serving it; empty for source and sink

uint8 STATE_IDLE=0
uint8 STATE_WAITING=1         # ready, waiting for work or for a trigger
uint8 STATE_WORKING=2
uint8 STATE_BLOCKED=3
uint8 STATE_FAULTED=4
uint8 state

uint32 buffer_occupancy       # work-pieces currently held here
uint32 buffer_capacity        # from the L0 topology
string current_workpiece_id   # empty when none
