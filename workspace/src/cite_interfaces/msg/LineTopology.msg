# The process topology of one zone, generated from L0.
#
# Replaces a std_msgs/String carrying JSON. That was a deliberate, temporary
# exception to CLAUDE.md §4 taken on the grounds that the shape could not be
# settled until a consumer existed; the L4 line coordinator now exists, so the
# reason has expired and the typed contract is here.
#
# Published on the LATCHED profile (`cite_interfaces/qos`): reliable,
# transient-local, depth 1. That is not a detail — a coordinator that starts
# after the topology server has published must receive the topology immediately,
# and a VOLATILE publisher would connect to it silently and deliver nothing,
# which is the failure CLAUDE.md §10 names first.
#
# TOPIC below is the ONE place this name is written. A consumer subscribes with
# `cite_interfaces::msg::LineTopology::TOPIC` (C++) or `LineTopology.TOPIC`
# (Python) rather than composing the string again, so the name cannot exist in
# two places (P1) and `ros2 interface show` is enough to discover it (P3).
string TOPIC="/cite/line/topology"

std_msgs/Header header        # frame_id is unused; stamp is when this topology
                              # was published, which L6 stamps recordings against

string zone                   # the L0 zone this topology describes, e.g. `cell_a`
string flow_id                # the L0 flow that arranged these stations

StationTopology[] stations    # every station in the zone
StationEdge[] edges           # how work moves between them
