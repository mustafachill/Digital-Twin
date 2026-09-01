#!/usr/bin/env bash
# Run ONE condition of the 2x2, once. New in this campaign; see README.md.
#
#   run_condition.sh <pair|solo> <convex_hull|vendor_meshes> <on|off> <block>
#
# The extended campaign drove its whole 24-trial matrix from one long-lived
# `run_campaign.sh` invocation. This campaign is driven by an agent whose shell calls are
# individually time-bounded, so the loop is split out: `run_campaign.sh` still exists and
# still walks the same eight conditions in the same registered order (criteria.md 6), and
# it now walks them by calling this script rather than by inlining the body. The body is
# otherwise the extended campaign's, step for step.
#
# ONE MEASUREMENT IS ADDED HERE, AND IT IS criteria.md 7's CORRECTED V6.
# `trial.py` records `os.getloadavg()` inside the container, which is the Docker Desktop
# Linux VM's load and not the machine's -- the extended campaign's Deviation 1. That call
# is left exactly as it was, so the two campaigns' V6 inputs stay comparable. This script
# additionally reads the macOS HOST's 1-minute load average either side of the trial and
# writes it to `raw/<LABEL>.host.json`, which is what criteria.md 7 registers V6 as being
# evaluated on. Registered before the first trial, not discovered after it.
set -u

TOPO="${1:?topology}"; GEOM="${2:?geometry}"; THR="${3:?throttle}"; BLOCK="${4:?block}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
mkdir -p "$RAW"

case "$THR"  in on) T=THROTTLED ;; off) T=FREE ;;   *) echo "bad throttle";  exit 2 ;; esac
case "$TOPO" in pair) P=PAIR ;;    solo) P=SOLO ;;  *) echo "bad topology";  exit 2 ;; esac
case "$GEOM" in vendor_meshes) G=VENDOR ;; convex_hull) G=HULL ;; *) echo "bad geometry"; exit 2 ;; esac
LABEL="${P}_${G}_${T}_${BLOCK}"

# Resumable, exactly as the extended campaign is: a condition already collected is not
# re-measured, so an interrupted campaign continues rather than restarting.
if [ -f "$RAW/$LABEL.json" ]; then echo "== skip $LABEL (already collected)"; exit 0; fi
echo "===== $LABEL ====="

revert() { git -C "$ROOT" checkout -- model/ tools/ workspace/src/cite_generated/ 2>/dev/null; }
# `./scripts/enter` is `docker compose run --rm`, so a trial owns a fresh container that is
# removed when its `trial.py` returns -- an orphaned `gz sim` holding a side's GZ_PARTITION
# cannot outlive it. This checks that rather than assuming it.
sweep()  { local left
           left="$(docker ps -q --filter name=docker-dev --filter name=cite 2>/dev/null | wc -l | tr -d ' ')"
           if [ "$left" != "0" ]; then echo "WARNING: $left container(s) left running after the trial"; fi
           docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -i 'cite\|docker-dev' || true; }
# 1-minute load average of the HOST, not of the container VM. criteria.md 7, V6.
host_load1() { uptime | sed -E 's/.*load averages?: *([0-9.]+).*/\1/'; }

revert
# A settled machine before V6's load average is read, and before the cell starts. A
# teardown's own cost is still on the 1-minute average immediately after a trial. This is
# a quiesce for an instrument, not a step of the bring-up sequence -- nothing here waits
# for a cell to be ready (P4).
sleep 60

LOAD_BEFORE="$(host_load1)"
STARTED="$(date +%s)"

python3 "$HERE/configure.py" --topology "$TOPO" --geometry "$GEOM" --throttle "$THR" || {
    # NOT a failure path for the vendor arm: `validate` exits non-zero there by design
    # (criteria.md 5, note 1). configure.py itself returns 0 unless it could not apply the
    # flip at all, which is the only case this branch is for.
    echo "configure.py failed for $LABEL"; revert; exit 1; }

"$ROOT/scripts/build" --packages-select cite_generated cite_description >/dev/null 2>&1

"$ROOT/scripts/enter" dev bash -lc \
  "python3 /workspace/docs/measurements/2026-09-01-capacity-on-shipped-main/harness/trial.py \
     --label $LABEL --topology $TOPO --out /workspace/docs/measurements/2026-09-01-capacity-on-shipped-main/raw"

LOAD_AFTER="$(host_load1)"
ENDED="$(date +%s)"

sweep
revert

# Written AFTER the revert, so `worktree_clean_outside_campaign` answers the question
# criteria.md 2 actually asks -- whether the scratch flip was put back -- rather than
# reporting the flip that was still applied a moment earlier.
cat > "$RAW/$LABEL.host.json" <<JSON
{
 "label": "$LABEL",
 "host_load1_before": $LOAD_BEFORE,
 "host_load1_after": $LOAD_AFTER,
 "host_started_epoch": $STARTED,
 "host_ended_epoch": $ENDED,
 "base_commit": "$(git -C "$ROOT" rev-parse HEAD)",
 "worktree_clean_outside_campaign": "$(git -C "$ROOT" status --porcelain -- model tools scripts tests workspace | wc -l | tr -d ' ')"
}
JSON

echo "== $LABEL done in $((ENDED - STARTED)) s (host load $LOAD_BEFORE -> $LOAD_AFTER)"
