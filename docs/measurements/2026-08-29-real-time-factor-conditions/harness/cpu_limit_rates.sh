#!/usr/bin/env bash
# Candidate C3, second follow-up: measure the OTHER half of the recorded figure --
# `joint_states` frequency -- under the CPU allocation that reproduced its RTF half.
#
# CPULOW_1 established that ~1 CPU puts the window RTF inside the pre-registered band.
# The record pairs "RTF about 0.14" with "`joint_states` at roughly 21 Hz", and
# `criteria.md` section 4 registered the hypothesis that those are ONE measurement
# divided by 150 rather than two. Measuring the rate under the same constraint is what
# tells the two hypotheses apart, so it is worth one trial.
#
# A third script rather than an edit to either of the first two, for the reason the
# campaign convention gives: both have produced data.
#
# The limit is applied BEFORE the probe's window opens, which is why the warm-up is
# long: the probe measures rates at window_open, and in the earlier scripts that
# instant fell before the first `docker update`.
set -euo pipefail

LABEL="${1:-CPURATE_1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMPAIGN="$(dirname "$HERE")"
RAW="${CAMPAIGN}/raw"
REPO="$(cd "${CAMPAIGN}/../../.." && pwd)"
mkdir -p "$RAW"

"${REPO}/scripts/enter" dev python3 \
    "/workspace/docs/measurements/2026-08-29-real-time-factor-conditions/harness/rtf_probe.py" \
    --label "$LABEL" \
    --out "/workspace/docs/measurements/2026-08-29-real-time-factor-conditions/raw" \
    --mode sim --warmup-s 220 --window-s 300 --hz-seconds 30 \
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

sleep 140
docker update --cpus 1 "$CID" >/dev/null
NOW="$(python3 -c 'import time; print(repr(time.time()))')"
echo "[cpu] --cpus 1 at ${NOW}"
printf '[{"cpus": 1.0, "wall": %s}]\n' "$NOW" > "${RAW}/${LABEL}.limits.json"

sleep 420
docker update --cpus 12 "$CID" >/dev/null
echo "[cpu] --cpus 12 restored"

wait "$PROBE_PID" || true
docker update --cpus 0 "$CID" >/dev/null 2>&1 || true
echo "[cpu] ${LABEL} done"
