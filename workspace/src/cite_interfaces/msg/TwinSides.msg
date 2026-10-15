# Which sides of the pair run, and which of them may be commanded now (ADR-0072,
# ADR-0077).
#
# Published by the twin boundary (`cite_twin`) on the plant's domain, LATCHED
# (`cite_interfaces.qos`), whenever any field changes. The boundary is the one
# component that knows which sides this deployment declared (the pair
# supervisor hands it `--sides`), which of them are up NOW (an operator
# console's pair keeps its physical counterpart and tells the boundary each
# change, ADR-0077), and whether a physical side is ready to be
# commanded (ADR-0070 item 6: its deadman HEALTHY with the arm enabled, its arm
# controller and every joint fresh), so this message is the ONE place a client -
# the operator console, a terminal program - reads either from. A client
# deciding which signal targets it may offer reads `commandable`, never the plan.
#
# What this is NOT: a permission. The boundary still decides every transition
# at the transition (SetMode.srv), and a side listed here may stop being
# commandable before a request reaches it.
#
# TOPIC is the one place this name is written, as SetMode's is.

string TOPIC="/cite/twin/sides"

builtin_interfaces/Time stamp
string[] running      # the sides UP NOW, by the plan's side names (ADR-0077): every
                      # simulated side of `expected`, and a physical one while its
                      # side's launch is up - until 2026-10-15 this meant "started",
                      # and on a pair that keeps no side the two are the same.
                      # ["plant"] for a pair started with the plant alone
string[] physical     # those of `expected` whose hardware is physical, from the plan,
                      # whether up or not
string[] commandable  # those of `running` a mode may command now: a simulated side
                      # always; a physical side only while the boundary judges it
                      # ready, measured and fresh, and its carriage, heard fresh,
                      # stands inside its track's travel. A physical track publishes
                      # no position until it has found its zero (`cite_hardware`'s
                      # track adapter), so such a side is not commandable either
string[] stationary   # those of `physical` whose every carriage the boundary reports
                      # standing still: its latest position fresh (the plan's
                      # `state_max_age_s`), and every position since one at least
                      # `state_max_age_s` older within the track's `goal_tolerance_m`
                      # of it. Read before a person is asked into the cell (S-02)
string detail         # why an expected side is not running, a running side not
                      # commandable, or a physical one not stationary; empty when none
string[] expected     # the sides this deployment declared (`--sides`): ["plant"] or
                      # ["plant", "counterpart"]. Fixed for the boundary's life
string[] connecting   # those of `expected` whose robot answered on the network and
                      # whose side is coming up, not yet running (ADR-0077)
string[] failed       # those of `expected` that will not be started again in this
                      # run: refused their configuration, or failed to connect too
                      # many times in a row (ADR-0077). An operator restarts the app
string[] held         # those of `running` whose physical arm the deadman, heard fresh,
                      # holds until an operator's Start robot releases it (ADR-0076)
