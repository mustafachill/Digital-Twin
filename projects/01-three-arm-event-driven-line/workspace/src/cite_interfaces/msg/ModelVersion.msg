# Which facility model the running system was generated from.
#
# Published on the LATCHED profile so a late-joining node receives it
# immediately. L6 stamps it into every recording: a bag recorded against
# yesterday's layout is not comparable to today's, and without this the two are
# indistinguishable after the fact.

std_msgs/Header header
string asset_id             # empty; this is facility scope

string model_hash           # SHA-256 of the L0 model content, not of its files
string generator_version    # the cite_tools version that produced the artifacts
string[] zones              # zones the running system was generated for
