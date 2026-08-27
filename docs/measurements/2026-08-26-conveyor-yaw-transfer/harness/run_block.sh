#!/usr/bin/env bash
# One INTERLEAVED block of any of this campaign's arms.
# conveyor_1 alternating spawn yaw and belt mode, bring it down.
#
#   run_block.sh <harness.py> <label> <trials> [extra args for the harness...]
#
# Adapted from the two published campaigns' runners — same launch, same domain
# guard, same teardown — with the output directed at this campaign's raw/.
#
# THE FULL CELL, DELIBERATELY. `simulation.launch.py` with all three arms, nine
# controllers and three move_groups, exactly as the published campaigns used it
# and for the reason they state: a reduced one-arm rig gives systematically
# different results, and a measurement taken on one does not transfer.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
CAMPAIGN="${ROOT}/docs/measurements/2026-08-26-conveyor-yaw-transfer"
HARNESS="${1:?harness script}"; shift
LABEL="${1:?label}"; shift
TRIALS="${1:?trials}"; shift

LOGDIR="${CAMPAIGN}/raw/logs"
mkdir -p "$LOGDIR" "${CAMPAIGN}/raw"

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

# Refuse to start on top of another cell. Two cells on one ROS_DOMAIN_ID publish
# two /clock streams, and the invisible symptom is a block of measurements taken
# against a simulator that is not the one this block configured. Cost the
# published campaign a whole block of trials.
echo "== checking the domain is clear =="
for attempt in $(seq 1 30); do
    EXISTING="$(ros2 node list 2>/dev/null | grep -c skill_server || true)"
    [ "$EXISTING" = "0" ] && break
    echo "   ${EXISTING} skill_server(s) still on domain ${ROS_DOMAIN_ID}; waiting"
    sleep 5
done
if [ "${EXISTING:-0}" != "0" ]; then
    echo "ABORT: another cell is on domain ${ROS_DOMAIN_ID}" >&2
    exit 2
fi

# The configuration facts this block's validity depends on, echoed into the log
# so that the raw data carries its own provenance.
echo "== max_step_size in the generated world =="
grep -o '<max_step_size>[^<]*<' "${ROOT}/workspace/src/cite_generated/worlds/cell_a.sdf" | head -1
echo "== conveyor_1 plugin configuration =="
sed -n '/<plugin filename="cite_conveyor"/,/<\/plugin>/p' \
    "${ROOT}/workspace/src/cite_generated/worlds/cell_a.sdf" | head -14
echo "== the carry list, which decides whether anything moves at all =="
grep -o '<carry>[^<]*<' "${ROOT}/workspace/src/cite_generated/worlds/cell_a.sdf" | sort -u

echo "== launching cell_a headless (domain ${ROS_DOMAIN_ID}) =="
ros2 launch cite_bringup simulation.launch.py headless:=true zone:=cell_a \
    > "${LOGDIR}/${LABEL}_sim.log" 2>&1 &
SIM=$!

cleanup() {
    echo "== tearing down =="
    kill -INT "$SIM" 2>/dev/null
    for _ in $(seq 1 30); do kill -0 "$SIM" 2>/dev/null || break; sleep 1; done
    kill -9 "$SIM" 2>/dev/null
    pkill -9 -f "gz sim" 2>/dev/null
    pkill -9 -f ruby 2>/dev/null
    pkill -9 -f move_group 2>/dev/null
    pkill -9 -f ros2_control_node 2>/dev/null
    pkill -9 -f skill_server 2>/dev/null
    sleep 3
}
trap cleanup EXIT

python3 "${HERE}/${HARNESS}" \
    --label "$LABEL" --trials "$TRIALS" --out "${CAMPAIGN}/raw" "$@" \
    2>&1 | tee "${LOGDIR}/${LABEL}_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
