# Whether a physical side's deadman permits motion (ADR-0070 item 5).
#
# Published by `cite_hardware`'s deadman on every change of state, latched, so a
# relay that starts later learns the current answer at once. The relays that
# move a physical asset — the gripper relay and the track adapter — refuse a
# command unless the latest state they hold is HEALTHY, and treat the deadman's
# publisher disappearing as not HEALTHY: a gate whose keeper died is closed.
#
# Only HEALTHY permits motion. Every other state refuses it, and the reasons
# differ only in what clears them:
#
#   INACTIVE  the deadman is not active. Cleared by activating it.
#   AWAITING  active, and no heartbeat has arrived yet. Cleared by the first
#             heartbeat from the boundary of the deadman's own zone.
#   TRIPPED   heartbeats stopped, or their publisher disappeared, after the
#             first one arrived. LATCHED: cleared only by a deliberate lifecycle
#             deactivate and activate, never by heartbeats resuming
#             (cross-cutting-safety.md: automatic resumption after an
#             unexplained fault is a Critical finding).
#
# The topic name is generated per asset from L0 (CLAUDE.md §8), so it is not a
# constant here.

uint8 STATE_INACTIVE=0
uint8 STATE_AWAITING=1
uint8 STATE_HEALTHY=2
uint8 STATE_TRIPPED=3

std_msgs/Header header
string asset_id             # the arm whose side this deadman guards

uint8 state
float64 timeout_s           # the declared heartbeat timeout this deadman applies
uint64 last_sequence        # the last heartbeat sequence accepted; 0 before any
string detail               # why the state is what it is, for the record
