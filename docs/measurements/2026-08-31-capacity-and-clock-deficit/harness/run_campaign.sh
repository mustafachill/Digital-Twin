#!/usr/bin/env bash
# Drive the 2x2 (plus its solo baseline) for N blocks. Run from the repository root
# on the HOST: the flips and the build are host-side, the trial itself is not.
#
#   docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/run_campaign.sh 3
#
# criteria.md 6: one block runs all eight conditions once, in a fixed order, and the
# ratios are computed WITHIN a block so that host drift between blocks cancels rather
# than landing on one condition.
set -u
BLOCKS="${1:-3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
mkdir -p "$RAW"

revert() { git -C "$ROOT" checkout -- model/ tools/ workspace/src/cite_generated/ 2>/dev/null; }
# `./scripts/enter` is `docker compose run --rm`, so a trial owns a fresh container that
# is removed when its `trial.py` returns -- an orphaned `gz sim` holding a side's
# GZ_PARTITION cannot outlive it. This checks that rather than assuming it, and reports
# a leak instead of quietly running the next trial against one.
sweep()  { local left
           left="$(docker ps -q --filter name=docker-dev --filter name=cite 2>/dev/null | wc -l | tr -d ' ')"
           if [ "$left" != "0" ]; then echo "WARNING: $left container(s) left running after the trial"; fi
           docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -i 'cite\|docker-dev' || true; }

for b in $(seq 1 "$BLOCKS"); do
  for geom in vendor_meshes convex_hull; do
    for thr in on off; do
      for topo in pair solo; do
        case "$thr" in on) T=THROTTLED ;; off) T=FREE ;; esac
        case "$topo" in pair) P=PAIR ;; solo) P=SOLO ;; esac
        case "$geom" in vendor_meshes) G=VENDOR ;; convex_hull) G=HULL ;; esac
        LABEL="${P}_${G}_${T}_${b}"
        if [ -f "$RAW/$LABEL.json" ]; then echo "== skip $LABEL (already collected)"; continue; fi
        echo "===== $LABEL ====="
        revert
        # A settled machine before V6's load average is read, and before the cell
        # starts. A teardown's own cost was still on the 1-minute average when the
        # shakedown read it. This is a quiesce for an instrument, not a step of the
        # bring-up sequence -- nothing here waits for a cell to be ready (P4).
        sleep 60
        python3 "$HERE/configure.py" --topology "$topo" --geometry "$geom" --throttle "$thr" || { revert; continue; }
        "$ROOT/scripts/build" --packages-select cite_generated cite_description >/dev/null 2>&1
        "$ROOT/scripts/enter" dev bash -lc \
          "python3 /workspace/docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/trial.py \
             --label $LABEL --topology $topo --out /workspace/docs/measurements/2026-08-31-capacity-and-clock-deficit/raw"
        sweep
        revert
      done
    done
  done
done
revert
echo "campaign done"
