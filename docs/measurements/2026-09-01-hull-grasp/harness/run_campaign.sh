#!/usr/bin/env bash
# Drive the A/B for N block-pairs. Run from the repository root on the HOST: the flip
# and the build are host-side, the trials are not.
#
#   docs/measurements/2026-09-01-hull-grasp/harness/run_campaign.sh 2 12
#
# criteria.md 6: four blocks of twelve, VENDOR HULL VENDOR HULL, so that each geometry
# gets two separate blocks and V4 can compare a within-geometry block difference against
# the between-geometry one.
set -u
PAIRS="${1:-2}"
TRIALS="${2:-12}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
mkdir -p "$RAW/logs"

revert() { git -C "$ROOT" checkout -- model/ workspace/src/cite_generated/ 2>/dev/null; }

# An orphaned `gz sim` holds the world name and the next block then measures a
# simulator it did not configure. `run_block.sh` sweeps inside the container; this
# checks from outside that the container itself went away, and reports a leak rather
# than quietly starting the next block on top of one.
sweep() {
    local left
    left="$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')"
    echo "   containers still running: ${left}"
    docker ps --format '{{.Names}}' 2>/dev/null | grep -i 'cite\|docker-dev' || true
}

for b in $(seq 1 "$PAIRS"); do
  for geom in vendor_meshes convex_hull; do
    case "$geom" in vendor_meshes) G=VENDOR ;; convex_hull) G=HULL ;; esac
    LABEL="${G}_B${b}"
    if [ -f "$RAW/${LABEL}_trials.json" ]; then echo "== skip $LABEL (collected)"; continue; fi
    echo "===== $LABEL ====="
    revert
    # A settled machine before the load average is read and before the cell starts.
    # This is a quiesce for an instrument, not a step of the bring-up sequence --
    # nothing here waits for a cell to be ready (P4).
    sleep 60
    uptime | tee "$RAW/logs/${LABEL}_load.txt"
    df -h / | tail -1 | tee -a "$RAW/logs/${LABEL}_load.txt"
    python3 "$HERE/configure.py" --geometry "$geom" || { revert; continue; }
    "$ROOT/scripts/build" --packages-select cite_generated cite_description >/dev/null 2>&1
    "$ROOT/scripts/enter" dev bash -lc \
      "bash /workspace/docs/measurements/2026-09-01-hull-grasp/harness/run_block.sh \
         $LABEL $geom $TRIALS"
    sweep
    revert
  done
done
revert
echo "campaign done"
