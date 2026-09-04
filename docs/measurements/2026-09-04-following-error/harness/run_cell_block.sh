#!/usr/bin/env bash
# One measurement block against the shipped cell. Runs INSIDE the container.
#
#   run_cell_block.sh <label> [extra arguments for measure.py...]
#
# DERIVED FROM `docs/measurements/2026-09-02-option-f-regions/harness/run_cell_block.sh`,
# copied at commit `3235cbc`, the commit that file last landed at. That directory is FROZEN
# (`docs/measurements/README.md` rule 2) and nothing in it is edited from here. The domain
# guard, the launch command, the readiness gate and the teardown sweep are kept verbatim in
# substance because they encode failures already paid for there.
#
# THE READINESS GATE IS NOT A SLEEP, and it is here because of a documented loss. The frozen
# ancestor's own ancestor started its harness the instant the launch was spawned, so a
# `ros2 param get` on the running description could run before `robot_state_publisher` was
# serving; one block won that race and three consecutive attempts at the next lost it and
# were discarded with no trial collected. This waits for the cell's OWN token,
# `CITE_SIDE_READY`, printed once every skill and detection action server the plan declares
# is answering on this side's domain (ADR-0047, P4). It is `criteria.md` I5, and V13 is what
# spends it.
#
# THE HARNESS RUNS IN THIS CONTAINER, BESIDE THE LAUNCH. Cross-container ROS discovery in
# this checkout is partial and has already produced a topic that existed and could not be
# seen; a recorder that could not see `controller_state` would record an empty set, and an
# empty set is the exact answer this campaign's central hazard produces by accident
# (`criteria.md` section 7.1).
#
# THE CELL IS THE SHIPPED ONE. No geometry flip, no substituted plugin, no rebuild and
# nothing to revert: this campaign's only levers are two fields on a goal message
# (`criteria.md` section 5.1) and nothing under `model/`, `workspace/src/`, `tools/`,
# `tests/`, `scripts/`, `assets/` or `external/` is touched (section 0, V1).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
LABEL="${1:?usage: run_cell_block.sh <label> [extra arguments for measure.py]}"
shift
OUTDIR="${CITE_FE_OUT:-${HERE}/../raw}"
LOGDIR="${OUTDIR}/logs"
READY_CEILING_S=420

# The tag this block's two log files carry. A shakedown writes `SHAKEDOWN_*` rather than a
# block name, so a file under `raw/shakedown/` cannot be read as a campaign block's log.
# `criteria.md` section 10: THE SHAKEDOWN IS NOT DATA.
TAG="${LABEL}"
for argument in "$@"; do
    [ "$argument" = "--shakedown" ] && TAG="SHAKEDOWN"
done

mkdir -p "$LOGDIR"

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

# Refuse to start on top of another cell. Two cells on one ROS_DOMAIN_ID publish two /clock
# streams and two `controller_state` publishers under one topic name, and the invisible
# symptom is a block of measurements taken against a simulator that is not the one this block
# brought up -- which V4's matched-publisher count would report as two, after the fact.
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

{
    echo "== ${LABEL} (log tag ${TAG}) =="
    date -u +%Y-%m-%dT%H:%M:%SZ
    uptime
    nproc
    free -m 2>/dev/null | head -2
    df -h / | tail -1
    echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-<unset>}"
} | tee "${LOGDIR}/${TAG}_load.txt"

SIMLOG="${LOGDIR}/${TAG}_sim.log"
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

# `--sim-log` is I3(b) and I3(c): the controller's `tolerances` logger and move_group's own
# rendered error code are written to THIS file by other processes, and nothing else in the
# rig can see them. The runner brackets each goal's segment of it by file offset.
# `-u`: unbuffered. Through `tee` Python block-buffers its stdout, and the 2026-09-04
# shakedown ran fourteen trials with the operator seeing nothing until the block ended.
python3 -u "${HERE}/measure.py" \
    --out "$OUTDIR" --block "$LABEL" --sim-log "$SIMLOG" "$@" \
    2>&1 | tee "${LOGDIR}/${TAG}_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
