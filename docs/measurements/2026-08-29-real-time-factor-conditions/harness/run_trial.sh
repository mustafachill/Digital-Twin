#!/usr/bin/env bash
# One trial: record the host state, run the probe in the container, clean up, record again.
#
#   harness/run_trial.sh IDLE_1 sim
#   harness/run_trial.sh CYCLE_1 scenario pick_and_place
#
# The host state around a trial is part of the measurement, not decoration: this campaign
# deliberately does NOT stop the project owner's unrelated containers (criteria.md
# section 1), so their load has to be quantified per trial or the figure is unattributable
# in exactly the way this campaign exists to correct.
set -euo pipefail

LABEL="$1"
MODE="${2:-sim}"
SCENARIO="${3:-pick_and_place}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMPAIGN="$(dirname "$HERE")"
RAW="${CAMPAIGN}/raw"
REPO="$(cd "${CAMPAIGN}/../../.." && pwd)"
mkdir -p "$RAW"

host_state() {
    {
        printf '=== %s %s ===\n' "$LABEL" "$1"
        date -u +'%Y-%m-%dT%H:%M:%SZ'
        uptime
        docker info --format 'docker: {{.NCPU}} CPUs, {{.MemTotal}} bytes, {{.ServerVersion}}'
        docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
        docker system df --format '{{.Type}} {{.Size}} reclaimable {{.Reclaimable}}' || true
        docker run --rm alpine df -h / | tail -2
    } >> "${RAW}/${LABEL}.host.txt" 2>&1
}

# A survivor from a previous trial invalidates this one (criteria.md section 1), so it is
# reported rather than quietly cleaned before the fact.
survivors() {
    docker ps --format '{{.Names}}' | grep -c 'cite-' || true
}

echo "[trial] ${LABEL} mode=${MODE}"
echo "[trial] cite containers before: $(survivors)" | tee -a "${RAW}/${LABEL}.host.txt"
host_state before

set +e
"${REPO}/scripts/enter" dev python3 \
    "/workspace/docs/measurements/2026-08-29-real-time-factor-conditions/harness/rtf_probe.py" \
    --label "$LABEL" \
    --out "/workspace/docs/measurements/2026-08-29-real-time-factor-conditions/raw" \
    --mode "$MODE" --scenario "$SCENARIO" \
    2>&1 | tee "${RAW}/${LABEL}.trial.log"
RC=${PIPESTATUS[0]}
set -e

# Teardown is the launch file's job; this is the check that it did it, and the fallback.
sleep 5
LEFT="$("${REPO}/scripts/enter" dev bash -lc 'pgrep -a "gz|ruby|move_group" | wc -l' 2>/dev/null || echo unknown)"
echo "[trial] gz-like processes left in container: ${LEFT}" | tee -a "${RAW}/${LABEL}.host.txt"
"${REPO}/scripts/enter" dev bash -lc 'pkill -9 -f "gz sim" || true; pkill -9 -f "ruby.*gz" || true' >/dev/null 2>&1 || true

host_state after
echo "[trial] ${LABEL} done rc=${RC}"
exit "$RC"
