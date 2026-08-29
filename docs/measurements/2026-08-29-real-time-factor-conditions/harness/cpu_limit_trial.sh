#!/usr/bin/env bash
# Candidate C3: does a smaller CPU allocation reproduce the recorded 0.14?
#
# One cell, brought up at the host's full 12 CPUs, then squeezed with
# `docker update --cpus` while it runs. The probe samples continuously, so each
# allocation's window is cut out of one run afterwards rather than costing a trial each.
# Timestamps of every change are written to raw/<label>.limits.json, which is what the
# analyser cuts on.
#
# Squeezing after bring-up rather than before is deliberate: bring-up at 2 CPUs may not
# complete inside the probe's readiness ceiling, and a cell that never came up measures
# nothing. The quantity of interest is the steady-state step cost under contention.
set -euo pipefail

LABEL="${1:-CPULIMIT_1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMPAIGN="$(dirname "$HERE")"
RAW="${CAMPAIGN}/raw"
REPO="$(cd "${CAMPAIGN}/../../.." && pwd)"
WINDOW_S=760
SEGMENT_S=180          # per allocation: 60 s to settle, 120 s of window
mkdir -p "$RAW"

"${REPO}/scripts/enter" dev python3 \
    "/workspace/docs/measurements/2026-08-29-real-time-factor-conditions/harness/rtf_probe.py" \
    --label "$LABEL" \
    --out "/workspace/docs/measurements/2026-08-29-real-time-factor-conditions/raw" \
    --mode sim --window-s "$WINDOW_S" --hz-seconds 20 \
    > "${RAW}/${LABEL}.trial.log" 2>&1 &
PROBE_PID=$!

CID=""
for _ in $(seq 1 120); do
    CID="$(docker ps --filter "name=cite-digital-twin-3748020299-dev-run" --format '{{.ID}}' | head -1)"
    [ -n "$CID" ] && break
    sleep 2
done
[ -n "$CID" ] || { echo "no container found"; kill "$PROBE_PID"; exit 1; }
echo "[cpu] container ${CID}"

# DEVIATION 2, recorded in the write-up: the first version of this block polled
# readiness through `scripts/enter`, which starts a CONTAINER PER POLL. That would
# have loaded the host this trial exists to characterise. It never ran and produced
# no data; it is replaced by a fixed wait, which is acceptable here and only here
# because nothing is SEQUENCED by it (P4) -- the probe opens its own window on an
# observed readiness state, and this wait only has to land inside that window. The
# IDLE set measured readiness at 21-35 s and the probe's warm-up at 30 s, so 150 s
# is comfortably inside a 760 s window with margin at both ends.
sleep 150

EVENTS="[]"
apply() {
    local cpus="$1"
    docker update --cpus "$cpus" "$CID" >/dev/null
    local now
    now="$(python3 -c 'import time; print(repr(time.time()))')"
    EVENTS="$(python3 - "$EVENTS" "$cpus" "$now" <<'PY'
import json, sys
events = json.loads(sys.argv[1])
events.append(dict(cpus=float(sys.argv[2]), wall=float(sys.argv[3])))
print(json.dumps(events))
PY
)"
    echo "[cpu] --cpus ${cpus} at ${now}"
}

apply 12; sleep "$SEGMENT_S"
apply 4;  sleep "$SEGMENT_S"
apply 2;  sleep "$SEGMENT_S"
apply 12
printf '%s\n' "$EVENTS" > "${RAW}/${LABEL}.limits.json"

wait "$PROBE_PID" || true
docker update --cpus 0 "$CID" >/dev/null 2>&1 || true
echo "[cpu] ${LABEL} done"
