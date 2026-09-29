# One station's place in the line, generated from L0.
#
# This is what a station IS and what it is connected to — never what it does.
# Behaviour comes from a behaviour tree; this message is the data that tree is
# instantiated from, which is what lets L4 build one subtree per station without
# knowing what a station is (P5).
#
# StationState is the runtime counterpart: this says a station exists and where
# it sits, that one says what it is doing right now.

string id                     # the L0 station id, e.g. `station_transfer_1`

uint8 TYPE_SOURCE=0           # work-pieces enter the line here
uint8 TYPE_SINK=1             # work-pieces leave the line here
uint8 TYPE_TRANSFER=2         # a robot moves a work-piece from one place to another
uint8 type                    # one of TYPE_*; a station type the publisher does
                              # not recognise is refused at configure rather than
                              # published as a number nobody can act on

string actor_asset_id         # the robot serving this station; empty for a
                              # source or a sink, which have no actor

uint32 capacity               # work-pieces, count: how many this station holds

# The frames a transfer station reaches for. Both empty for a source or a sink.
# Frame identifiers, resolved through TF — never coordinates, so that a station
# and the cell it stands in cannot drift apart.
string pick_frame
string place_frame

# What tells this station a work-piece has arrived. Empty topic means the station
# has no sensor trigger and is sequenced by its upstream station instead.
string trigger_topic          # a DetectionEvent topic
uint8 TRIGGER_ON_CLEAR=0      # matches DetectionEvent/STATE_CLEAR
uint8 TRIGGER_ON_BLOCKED=1    # matches DetectionEvent/STATE_BLOCKED
uint8 trigger_state           # which DetectionEvent state fires this station;
                              # meaningless when trigger_topic is empty

string[] upstream_ids         # station ids feeding this one
string[] downstream_ids       # station ids this one feeds
