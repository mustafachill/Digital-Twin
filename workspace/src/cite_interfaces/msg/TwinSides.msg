# Which sides of the pair run, and which of them may be commanded now (ADR-0072).
#
# Published by the twin boundary (`cite_twin`) on the plant's domain, LATCHED
# (`cite_interfaces.qos`), whenever any field changes. The boundary is the one
# component that knows both which sides this deployment started (the pair
# supervisor hands it `--sides`) and whether a physical side is ready to be
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
string[] running      # the sides this deployment started, by the plan's side names:
                      # ["plant"] for a pair started with the plant alone, or
                      # ["plant", "counterpart"]
string[] physical     # those of `running` whose hardware is physical, from the plan
string[] commandable  # those of `running` a mode may command now: a simulated side
                      # always; a physical side only while the boundary judges it
                      # ready, measured and fresh
string detail         # why a running side is not commandable, empty when every one is
