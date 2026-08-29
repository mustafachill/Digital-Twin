# The twin's operating mode (ADR-0011, amended 2026-08-29 for the sixth mode,
# which ADR-0041 Decision 2 specifies).
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
uint8 MODE_VIRTUAL_LEAD=5   # virtual commanded; the far side follows and actuates.
                            # No validation gate in front of it — that is CLOSED_LOOP.
                            # No reverse flow behind it — that is SHADOW.
                            # It carries L3's direction without L3's validation gate,
                            # so it is not a maturity level and must never be cited as
                            # one. Entering it against a real far side is one of the
                            # three most dangerous transitions in the system; see
                            # SetMode.srv and cross-cutting-safety.md.

std_msgs/Header header
string asset_id             # empty for facility-wide mode

uint8 mode
uint8 requested_mode        # differs from `mode` only while a transition is in flight
bool transition_in_progress
string reason               # why the current mode was entered, for the record
