# One connection in the process topology, generated from L0.
#
# An edge says that work moves from one station to another and what carries it.
# It never says how, or how fast: behaviour is a behaviour tree's business and
# speed is a fact about the conveyor asset, not about this link.

string from_station_id        # the upstream station's id
string to_station_id          # the downstream station's id
string via_asset_id           # the asset that carries the work-piece between
                              # them — a conveyor id; empty when the handoff is
                              # direct and nothing carries it

uint32 buffer_capacity        # work-pieces, count: how many this link may hold
                              # before the upstream station must wait
