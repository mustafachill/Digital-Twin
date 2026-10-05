# Whether a physical side's deadman permits motion (ADR-0070 item 5).
#
# Published by `cite_hardware`'s deadman on every change of state and on every
# tick, latched, so a relay that starts later learns the current answer at once
# and a relay holding an old copy can tell it is old. The relays that move a
# physical asset — the gripper relay and the track adapter — refuse a command
# unless the latest state they hold is HEALTHY, recent, and from the one deadman
# publishing: a gate whose keeper died, hung or has a rival is closed.
#
# The deadman watches the twin boundary's heartbeat: the boundary process and
# the path from it to this side. The arm itself is not behind this gate; the
# deadman holds it stopped through the vendor's own state (set_state 4) in
# every state but HEALTHY.
#
# Only HEALTHY permits motion. Every other state refuses it, and the reasons
# differ only in what clears them:
#
#   INACTIVE  the deadman is not active. Cleared by activating it.
#   AWAITING  active, and no heartbeat has arrived yet. Cleared by the first
#             heartbeat from the boundary of the deadman's own zone, which
#             latches that boundary's id and enables the arm.
#   TRIPPED   heartbeats stopped, their publisher disappeared, or a second
#             boundary appeared (another id, or a second publisher), after the
#             first one arrived. LATCHED: cleared only by a deliberate lifecycle
#             deactivate and activate, which return to AWAITING with the arm
#             still stopped, never by heartbeats resuming
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
