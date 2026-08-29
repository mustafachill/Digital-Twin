#!/usr/bin/env bash
# The interleaved run order, exactly as executed.
#
# SOLO is also the V (vendor collision mesh) arm of Q3.1 -- it is the same
# condition measured the same way, so running it twice would be running the same
# thing twice under two names. The order alternates SOLO, PAIR, HULL so that no
# condition occupies a contiguous block of wall-clock time.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for i in 1 2 3; do
    "${HERE}/run_campaign.sh" solo "SOLO_${i}"
    "${HERE}/run_campaign.sh" pair "PAIR_${i}"
    "${HERE}/run_campaign.sh" hull "HULL_${i}"
done
"${HERE}/run_campaign.sh" solo "SOLO_4"
"${HERE}/run_campaign.sh" pair "PAIR_4"
