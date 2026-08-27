# How an operation ended.
#
# A code, never a free-text string. L4 chooses a recovery strategy from this
# value, which is impossible if failure is prose — and is why v1's orchestration
# could only ever retry generically.
#
# `detail` explains the code to a person. It is never the machine-readable part,
# and nothing may parse it.

uint8 SUCCESS=0
uint8 PLANNING_FAILED=1
uint8 EXECUTION_FAILED=2
uint8 CANCELLED=3
uint8 SAFETY_BLOCKED=4
uint8 PRECONDITION_FAILED=5   # the world was not in the state the goal assumed
uint8 TIMEOUT=6
uint8 HARDWARE_FAULT=7
uint8 NOT_IMPLEMENTED=8       # a path deliberately unbuilt, per P7
uint8 UNREACHABLE=9           # no inverse-kinematics solution exists for the
                              # requested pose, at all. Distinct from
                              # PLANNING_FAILED, which means a solution exists
                              # and no collision-free path to it was found. The
                              # remedies differ completely — move the station or
                              # re-reach the pose, versus clear the obstacle —
                              # and reporting the first as the second sent three
                              # investigations to the wrong place in a cell whose
                              # planning scene was empty and therefore contained
                              # no obstacle to clear.

uint8 code
string detail
