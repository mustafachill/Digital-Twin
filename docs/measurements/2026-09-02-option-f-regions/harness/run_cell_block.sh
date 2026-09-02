#!/usr/bin/env bash
# One measurement block against the shipped cell. Runs INSIDE the container.
#
#   run_cell_block.sh <a|c|d> <label> [extra arguments for the runner...]
#
# DERIVED FROM
# `docs/measurements/2026-09-01-grasp-discrimination/harness/run_fn_block_after_ready.sh`,
# copied at commit `eeaf903`. That directory is frozen and nothing in it is edited here.
# The domain guard, the launch command, the readiness gate and the teardown sweep are
# kept verbatim in substance because they encode failures already paid for there.
#
# THE READINESS GATE IS NOT A SLEEP, and it is here because of a documented loss.
# `run_fn_block.sh` started its harness the instant the launch was spawned, so the V1
# check -- `ros2 param get` on the running description -- could run before
# `robot_state_publisher` was serving. One block won that race; three consecutive attempts
# at the next lost it and were discarded with no trial collected. This waits for the
# cell's own token, `CITE_SIDE_READY`, printed once every skill and detection action
# server the plan declares is answering on this side's domain (ADR-0047, P4).
#
# THE CELL IS THE SHIPPED ONE. No geometry flip, no rebuild, nothing to revert: this
# campaign's levers are fields on goal messages and a spawn pose. `criteria.md` section 0.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
ARM_LETTER="${1:?arm: a, c or d}"
LABEL="${2:?label}"
shift 2
OUTDIR="${CITE_OFR_OUT:-${HERE}/../raw}"
LOGDIR="${OUTDIR}/logs"
READY_CEILING_S=420
mkdir -p "$LOGDIR"

case "$ARM_LETTER" in
    a|c|d) RUNNER="${HERE}/measure_arm_${ARM_LETTER}.py" ;;
    *) echo "ABORT: unknown arm '${ARM_LETTER}'; expected a, c or d" >&2; exit 2 ;;
esac

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

# Refuse to start on top of another cell. Two cells on one ROS_DOMAIN_ID publish two
# /clock streams, and the invisible symptom is a block of measurements taken against a
# simulator that is not the one this block brought up.
echo "== checking the domain is clear =="
for _ in $(seq 1 20); do
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

{
    echo "== ${LABEL} =="
    uptime
    nproc
    free -m 2>/dev/null | head -2
    df -h / | tail -1
} | tee "${LOGDIR}/${LABEL}_load.txt"

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

python3 "$RUNNER" --label "$LABEL" --out "$OUTDIR" --sim-log "$SIMLOG" "$@" \
    2>&1 | tee "${LOGDIR}/${LABEL}_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
