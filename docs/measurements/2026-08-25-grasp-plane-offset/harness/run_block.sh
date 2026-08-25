#!/usr/bin/env bash
# One measurement block: bring the cell up headless, run N trials against it at a
# chosen commanded grasp height, bring it down. Runs INSIDE the container.
#
#   run_block.sh <label> <trials> <grasp_height_m> [extra args for the harness...]
#
# Adapted from the published campaign's run_block.sh — same launch, same domain
# guard, same teardown — with the commanded grasp height threaded through and the
# output directed at this campaign's raw/.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
CAMPAIGN="${ROOT}/docs/measurements/2026-08-25-grasp-plane-offset"
LABEL="${1:?label}"; shift
TRIALS="${1:?trials}"; shift
HEIGHT="${1:?grasp height in metres}"; shift

LOGDIR="${CAMPAIGN}/raw/logs"
mkdir -p "$LOGDIR" "${CAMPAIGN}/raw"

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

# Refuse to start on top of another cell. Two cells on one ROS_DOMAIN_ID publish
# two /clock streams; the visible symptom is a flood of TF_OLD_DATA and move_group
# segfaulting, and the invisible one is a block of measurements taken against a
# simulator that is not the one this block configured. Cost the published
# campaign a whole block of trials.
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

echo "== max_step_size in the generated world =="
grep -o '<max_step_size>[^<]*<' "${ROOT}/workspace/src/cite_generated/worlds/cell_a.sdf" | head -1
echo "== stall_velocity_threshold in the generated controllers =="
grep -o 'stall_velocity_threshold: .*' \
    "${ROOT}/workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml" | head -1

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

python3 "${HERE}/grasp_height_block.py" \
    --grasp-height "$HEIGHT" \
    --label "$LABEL" --trials "$TRIALS" --out "${CAMPAIGN}/raw" "$@" \
    2>&1 | tee "${LOGDIR}/${LABEL}_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
