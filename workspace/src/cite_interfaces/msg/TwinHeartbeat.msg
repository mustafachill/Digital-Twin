# The twin boundary is alive and serving this side (ADR-0070 item 5).
#
# Published by L5's twin boundary onto EACH side's own domain, from a timer that
# side's own executor runs, so a heartbeat on a domain says two things at once:
# the boundary process is up, and the executor serving that side is turning.
# A side whose heartbeat stops has lost its commander, and a physical side's
# deadman stops motion on it (cross-cutting-safety.md, "Watchdog and
# communication loss"; open-work #74). It is evidence about the boundary
# PROCESS and the path from it to the receiver, never about the vendor's own
# link from its driver to the arm's controller.
#
# What a receiver may conclude from it is ARRIVAL, never age. `header.stamp` is
# the boundary's wall clock, which is a different machine's clock from the
# receiver's on a physical side, so a receiver times liveness on its own steady
# clock between arrivals and reads the stamp only into a record.
#
# TOPIC below is the ONE place this name is written (ADR-0050 decision 5d). It
# is under the facility-singular `/cite/twin/` scope like every other L5 name
# (naming-and-namespaces.md, "Reserved names"); which zone it serves is the
# `zone` field, not a segment of the name.

string TOPIC="/cite/twin/heartbeat"

std_msgs/Header header

string zone                 # the zone this boundary spans, as L0 names it
string boundary_id          # a UUID drawn once per boundary start, the same on both
                            # sides; a deadman latches the first it hears, and a
                            # different one is a second boundary
uint64 sequence             # strictly increasing per side, from 1 at boundary start
