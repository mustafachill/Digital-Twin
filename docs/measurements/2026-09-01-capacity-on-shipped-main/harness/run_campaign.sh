#!/usr/bin/env bash
# Drive the 2x2 (plus its solo baseline) for N blocks. Run from the repository root on the
# HOST: the flips and the build are host-side, the trial itself is not.
#
#   docs/measurements/2026-09-01-capacity-on-shipped-main/harness/run_campaign.sh 3
#
# criteria.md 6: one block runs all eight conditions once, in a fixed order, and the ratios
# are computed WITHIN a block so that host drift between blocks cancels rather than landing
# on one condition. The order below is byte-for-byte the extended campaign's, so the two
# campaigns' block structures line up.
#
# ADAPTED: the body of one condition now lives in `run_condition.sh` and this file calls it,
# where the extended campaign inlined it. Nothing about the order, the flips or the
# measurement changed; the split exists so that one condition can be invoked on its own by a
# driver whose individual calls are time-bounded. See README.md.
set -u
BLOCKS="${1:-3}"
HERE="$(cd "$(dirname "$0")" && pwd)"

for b in $(seq 1 "$BLOCKS"); do
  # criteria.md 6 registers this order: vendor throttled, vendor free, hull throttled, hull
  # free, pair before solo within each. It is the extended campaign's order and it is
  # followed literally -- including that the VENDOR arm runs first, even though the shipped
  # configuration is the hull one and running it first would be more convenient if the
  # campaign were cut short. The order was registered before the first trial and a
  # convenience is not a reason to move it.
  for geom in vendor_meshes convex_hull; do
    for thr in on off; do
      for topo in pair solo; do
        "$HERE/run_condition.sh" "$topo" "$geom" "$thr" "$b"
      done
    done
  done
done
echo "campaign done"
