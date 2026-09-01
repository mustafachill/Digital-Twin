#!/usr/bin/env bash
# The FN arm: two blocks of sixteen, quiescing between them. Run from the repository root
# on the HOST -- the container entry is host-side, the trials are not.
#
#   docs/measurements/2026-09-01-grasp-discrimination/harness/run_fn_campaign.sh [trials]
#
# criteria.md 6.1: two blocks so that a block effect is visible, and V5 is what spends it.
# The four commanded widths are interleaved WITHIN each block -- the lever is a goal field,
# not a rebuild, so `docs/measurements/README.md`'s "interleave, do not block" applies to
# the thing being compared and blocking applies only to the bring-up.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
TRIALS="${1:-16}"
mkdir -p "$RAW/logs"

sweep() {
    echo "   containers still running: $(docker ps -q 2>/dev/null | wc -l | tr -d ' ')"
}

for block in 1 2; do
    LABEL="FN_B${block}"
    if [ -f "$RAW/${LABEL}_trials.json" ]; then echo "== skip $LABEL (collected)"; continue; fi
    echo "===== $LABEL ====="
    # A settled machine before the load average is read and before the cell starts. This
    # is a quiesce for an instrument, not a step of the bring-up sequence -- nothing here
    # waits for a cell to be ready (P4).
    sleep 60
    uptime | tee "$RAW/logs/${LABEL}_load.txt"
    df -h / | tail -1 | tee -a "$RAW/logs/${LABEL}_load.txt"
    "$ROOT/scripts/enter" dev bash -lc \
      "bash /workspace/docs/measurements/2026-09-01-grasp-discrimination/harness/run_fn_block.sh \
         $LABEL $TRIALS"
    sweep
done
echo "FN campaign done"
