# What the safety layer is currently enforcing and whether anything is latched.
#
# This is software interlocking, not functional safety. Certified safety for a
# physical cell is a hardware and process matter and lives outside this
# repository (charter §3.2); nothing here substitutes for it, and saying so in
# the interface itself is deliberate.

std_msgs/Header header
string asset_id             # empty for facility-wide state

bool estop_active           # latched; clears only on a deliberate reset
bool limits_enforced        # false is a fault condition, never a configuration
bool workspace_bounds_ok
bool keep_out_zones_ok

uint8 SOURCE_NONE=0
uint8 SOURCE_OPERATOR=1
uint8 SOURCE_WATCHDOG=2
uint8 SOURCE_LIMIT_VIOLATION=3
uint8 SOURCE_COLLISION=4
uint8 SOURCE_HARDWARE=5
uint8 estop_source

builtin_interfaces/Time estop_asserted_at
string detail
