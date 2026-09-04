#!/usr/bin/env bash
# One block, INSIDE the container. `criteria.md` section 6: a block is one container session,
# and the three captures run in the fixed order BRINGUP, PICKPLACE, LINE with ONE recorder
# alive across all three.
#
# DERIVED FROM `docs/measurements/2026-09-04-following-error/harness/run_cell_block.sh`,
# copied at commit `0712272` -- the `set -uo pipefail` without `-e`, the `set +u` around the
# setup sources, the domain guard, the load header, the teardown sweep, `python3 -u` under
# `tee` with `PIPESTATUS[0]`, and the shakedown log retagging. That directory is FROZEN
# (`docs/measurements/README.md` rule 2) and nothing in it is edited from here.
#
# THREE DIFFERENCES FROM THAT ANCESTOR, ALL FORCED BY `criteria.md` RULE C-i.
#   1. **This script starts no cell.** Each scenario starts its own `move_group` inside its
#      own process and every run owns its own cell, so there is no `simulation.launch.py`
#      here, no backgrounded launch PID and no `CITE_SIDE_READY` gate to wait on. `capture.py`
#      launches `./scripts/scenario` three times and watches the door while each runs.
#   2. **There is no `--sim-log`.** Each capture's log is the scenario's own output, captured
#      by `capture.py` into `logs/<TAG>_<CAPTURE>.log`, which is where I5, I6, I2 and I9 are
#      scraped from.
#   3. **The teardown sweep still exists**, because a scenario killed part-way leaves the same
#      processes behind that a launch does, and the next capture's domain guard would find
#      them.
#
# V12: nothing in this script and nothing in `capture.py` makes a Gazebo-transport call. The
# scenarios start their own Gazebo processes through the shipped launch, which carries
# `GZ_PARTITION` (ADR-0042). An unpartitioned `gz model --list` reaches no world and EXITS 0,
# so a raw call here would produce plausible silence rather than an error.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
LABEL="${1:?usage: run_cell_block.sh <label> [extra arguments for capture.py]}"
shift
OUTDIR="${CITE_WC_OUT:-${HERE}/../raw}"
LOGDIR="${OUTDIR}/logs"

# The tag this block's log files carry. A shakedown writes `SHAKEDOWN_*` rather than a block
# name, so a file under `raw/shakedown/` cannot be read as a campaign block's log.
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

# Refuse to start on top of another cell. Two cells on one ROS_DOMAIN_ID put two
# `display_planned_path` publishers under one topic name, and the invisible symptom is a block
# of trajectories captured from a cell that is not the one this block's scenario brought up --
# which V4's matched-publisher count would report as two, after the fact.
echo "== checking the domain is clear =="
for _ in $(seq 1 20); do
    EXISTING="$(ros2 node list 2>/dev/null | grep -c move_group || true)"
    [ "$EXISTING" = "0" ] && break
    echo "   ${EXISTING} move_group(s) still on domain ${ROS_DOMAIN_ID}; waiting"
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
    echo "GZ_PARTITION=${GZ_PARTITION:-<unset>}"
    echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-<unset>}"
} | tee "${LOGDIR}/${TAG}_load.txt"

cleanup() {
    echo "== tearing down =="
    pkill -9 -f "gz sim" 2>/dev/null
    pkill -9 -f ruby 2>/dev/null
    pkill -9 -f move_group 2>/dev/null
    pkill -9 -f ros2_control_node 2>/dev/null
    pkill -9 -f skill_server 2>/dev/null
    pkill -9 -f parameter_bridge 2>/dev/null
    sleep 3
}
trap cleanup EXIT

# `-u`: unbuffered. Through `tee` Python block-buffers its stdout, and a block whose captures
# take many minutes each would show the operator nothing until it ended.
python3 -u "${HERE}/capture.py" --out "$OUTDIR" --block "$LABEL" "$@" \
    2>&1 | tee "${LOGDIR}/${TAG}_harness.log"
RC=${PIPESTATUS[0]}
echo "== capture exited ${RC} =="
exit "$RC"
