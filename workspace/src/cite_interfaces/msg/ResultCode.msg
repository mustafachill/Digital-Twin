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
uint8 EXECUTION_FAILED=2       # the commanded motion did not complete, and the arm
                              # is at one of the trajectory's endpoints: it either
                              # never left the start or it reached the goal. It is
                              # NOT part-way and NOT holding an unexplained
                              # position -- that is MOTION_INTERRUPTED below, and
                              # the two want different answers from L4.
                              #
                              # Narrowed by ADR-0037. It previously meant "the
                              # controller did not complete the trajectory",
                              # whatever the arm then did, which put a stalled arm
                              # mid-path and a goal that never took effect under
                              # one code that L4 answered with a retry.
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

uint8 MOTION_INTERRUPTED=10   # the arm stopped part-way through a commanded
                              # motion and is holding position. It is neither at
                              # the start nor at the goal, and WHY it stopped is
                              # not established.
                              #
                              # Stated about the world rather than about a
                              # controller, deliberately (ADR-0037). The upstream
                              # mechanism that most often produces it here is a
                              # `joint_trajectory_controller` path-tolerance
                              # abort, and PATH_TOLERANCE_VIOLATED was explicitly
                              # REFUSED as a constant: it names a vendor's check
                              # rather than a fact, and it would be inexpressible
                              # for a robot type whose controller has no such
                              # check -- a P9 break at the interface that exists
                              # to make P9 possible.
                              #
                              # It does not say what stopped the arm. Nothing on
                              # this stack can: the controller's own error code is
                              # destroyed by three separate funnels before it
                              # reaches L3 (ADR-0037 records all three with line
                              # numbers). L4 escalates this because it cannot
                              # tell, not because anything has been diagnosed.

uint8 code
string detail
