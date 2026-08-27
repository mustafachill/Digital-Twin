# The twin's operating mode (ADR-0011).
#
# A constant, never a string: a typo in a string comparison is a runtime bug that
# a constant makes impossible, and the valid set is discoverable rather than
# folklore.
#
# Mode is explicit, observable and gated. It is never reachable through a default
# parameter, an environment variable, or a launch-argument default — a system
# that can enter REAL because someone forgot an argument is a system that will.

uint8 MODE_SIM=0            # physical idle, virtual commanded
uint8 MODE_REAL=1           # physical commanded, virtual idle
uint8 MODE_SHADOW=2         # physical commanded, virtual follows its state
uint8 MODE_VALIDATED=3      # both commanded, divergence measured, virtual does not actuate
uint8 MODE_CLOSED_LOOP=4    # physical commanded only after the virtual validates it

std_msgs/Header header
string asset_id             # empty for facility-wide mode

uint8 mode
uint8 requested_mode        # differs from `mode` only while a transition is in flight
bool transition_in_progress
string reason               # why the current mode was entered, for the record
