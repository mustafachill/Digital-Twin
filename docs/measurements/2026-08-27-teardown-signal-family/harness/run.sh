#!/usr/bin/env bash
# Run ./scripts/scenario bringup N times, recording each run's log.
#   usage: measure/run.sh <arm-label> <n>
set -u
ARM="$1"
N="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/measure/${ARM}"
mkdir -p "$OUT"
for i in $(seq 1 "$N"); do
    start=$(date +%s)
    "${ROOT}/scripts/scenario" bringup > "${OUT}/run${i}.log" 2>&1
    rc=$?
    end=$(date +%s)
    echo "run=${i} rc=${rc} seconds=$((end - start))" >> "${OUT}/summary.txt"
done
echo "DONE ${ARM}"
