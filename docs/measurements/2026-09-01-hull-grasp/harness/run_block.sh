#!/usr/bin/env bash
# One measurement block: bring the cell up headless, run N trials against it, bring
# it down. Runs INSIDE the container. Derived from the friction campaign's
# `run_block.sh`, whose domain guard and teardown sweep are kept verbatim because
# they encode failures already paid for there.
#
#   run_block.sh <label> <geometry> <trials> [extra args for measure_hull_grasp.py...]
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
LABEL="${1:?label}"; shift
GEOMETRY="${1:?geometry}"; shift
TRIALS="${1:?trials}"; shift
OUTDIR="${CITE_HULL_OUT:-${HERE}/../raw}"

LOGDIR="${OUTDIR}/logs"
mkdir -p "$LOGDIR"

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

# Refuse to start on top of another cell. Two cells on one ROS_DOMAIN_ID publish two
# /clock streams, and the invisible symptom is a block of measurements taken against a
# simulator that is not the one this block configured.
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

# What geometry is actually loaded, read off the description this cell will publish
# rather than off the model file the flip edited. criteria.md V2: a block that ran on
# the geometry it did not name is worthless, and nothing else in the pipeline checks it.
echo "== collision roots in the generated description =="
grep -o 'collision_mesh_path[^ ]*' \
    "${ROOT}/workspace/src/cite_generated/descriptions/cell_a_arm_1.urdf.xacro" \
    | head -3 | tee "${LOGDIR}/${LABEL}_geometry.txt"
echo "declared_geometry=${GEOMETRY}" >> "${LOGDIR}/${LABEL}_geometry.txt"

echo "== launching cell_a headless (domain ${ROS_DOMAIN_ID}) =="
ros2 launch cite_bringup simulation.launch.py headless:=true zone:=cell_a \
    > "${LOGDIR}/${LABEL}_sim.log" 2>&1 &
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

python3 "${HERE}/measure_hull_grasp.py" --label "$LABEL" --geometry "$GEOMETRY" \
    --trials "$TRIALS" --out "$OUTDIR" "$@" \
    2>&1 | tee "${LOGDIR}/${LABEL}_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
