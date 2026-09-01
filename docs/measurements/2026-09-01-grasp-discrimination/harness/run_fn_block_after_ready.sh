#!/usr/bin/env bash
# One FN measurement block, started only once the cell says it is ready.
#
#   run_fn_block_after_ready.sh <label> <trials>
#
# WHY THIS EXISTS, AND WHAT IT DOES NOT CHANGE. `run_fn_block.sh` launches the cell and
# starts the harness immediately, so `measure_fn.py`'s V1 check -- `ros2 param get` on the
# running description -- can run before `robot_state_publisher` is serving. Block FN_B1
# won that race; three consecutive attempts at FN_B2 lost it and were discarded by V1
# exactly as `criteria.md` V1 prescribes, with no trial collected.
#
# The fix is a readiness GATE, not a sleep (P4): this waits for the cell's own readiness
# token, `CITE_SIDE_READY`, which `cite_bringup`'s witness prints once every skill and
# detection action server the plan declares is answering on this side's domain (ADR-0047).
# Nothing here waits for a guessed duration.
#
# WHAT IS IDENTICAL TO `run_fn_block.sh`: the domain guard, the launch command, the
# teardown sweep, and -- this is the part that matters -- `measure_fn.py`, which is the
# code that produces every FN figure and is byte-identical for both blocks. The published
# `ANALYSIS.md` records which block used which runner as a numbered deviation.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
LABEL="${1:?label}"
TRIALS="${2:-16}"
OUTDIR="${CITE_GD_OUT:-${HERE}/../raw}"
LOGDIR="${OUTDIR}/logs"
READY_CEILING_S=420
mkdir -p "$LOGDIR"

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

echo "== checking the domain is clear =="
for attempt in $(seq 1 20); do
    EXISTING="$(ros2 node list 2>/dev/null | grep -c skill_server || true)"
    [ "$EXISTING" = "0" ] && break
    echo "   ${EXISTING} skill_server(s) still on domain ${ROS_DOMAIN_ID}; waiting"
    sleep 5
done
if [ "${EXISTING:-0}" != "0" ]; then
    echo "ABORT: another cell is on domain ${ROS_DOMAIN_ID}" >&2
    exit 2
fi

bash "${HERE}/build.sh"

SIMLOG="${LOGDIR}/${LABEL}_sim.log"
echo "== launching cell_a headless (domain ${ROS_DOMAIN_ID}) =="
ros2 launch cite_bringup simulation.launch.py headless:=true zone:=cell_a \
    > "${SIMLOG}" 2>&1 &
SIM=$!

cleanup() {
    echo "== tearing down =="
    kill -INT "$SIM" 2>/dev/null
    for _ in $(seq 1 40); do kill -0 "$SIM" 2>/dev/null || break; sleep 1; done
    kill -9 "$SIM" 2>/dev/null
    pkill -9 -f "gz sim" 2>/dev/null
    pkill -9 -f ruby 2>/dev/null
    pkill -9 -f move_group 2>/dev/null
    pkill -9 -f ros2_control_node 2>/dev/null
    pkill -9 -f skill_server 2>/dev/null
    pkill -9 -f parameter_bridge 2>/dev/null
    sleep 3
}
trap cleanup EXIT

# The gate. The token is the cell's own, printed once by the readiness witness; a side
# that dies instead of announcing is caught by the process check, so the loop cannot
# outlive the thing it is waiting for.
echo "== waiting for CITE_SIDE_READY (ceiling ${READY_CEILING_S}s) =="
READY=0
for _ in $(seq 1 "$READY_CEILING_S"); do
    if grep -q "CITE_SIDE_READY" "$SIMLOG" 2>/dev/null; then READY=1; break; fi
    if ! kill -0 "$SIM" 2>/dev/null; then
        echo "ABORT: the cell exited before announcing readiness" >&2
        exit 4
    fi
    sleep 1
done
if [ "$READY" != "1" ]; then
    echo "ABORT: the cell never announced readiness within ${READY_CEILING_S}s" >&2
    exit 5
fi
grep -m1 "CITE_SIDE_READY" "$SIMLOG"

python3 "${HERE}/measure_fn.py" --label "$LABEL" --trials "$TRIALS" \
    --out "$OUTDIR" --sim-log "$SIMLOG" \
    2>&1 | tee "${LOGDIR}/${LABEL}_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
