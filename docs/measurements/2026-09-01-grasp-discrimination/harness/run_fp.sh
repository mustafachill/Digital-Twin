#!/usr/bin/env bash
# The FP arm — a stall on nothing. Runs INSIDE the container.
#
#   run_fp.sh [repeats]
#
# `cite_test_hardware` builds only under BUILD_TESTING, so the workspace must have been
# built with tests on -- which `./scripts/build` does. If the plugin is missing, the
# controller manager fails to load the component and every trial records the failure
# rather than silently falling back to a mock: that is what rule N is for.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/workspace
REPEATS="${1:-3}"
OUTDIR="${CITE_GD_OUT:-${HERE}/../raw}"

set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/workspace/install/setup.bash"
set -u

mkdir -p "${OUTDIR}/logs"

# Refuse to start on top of another cell, exactly as the hull-grasp campaign's block
# runner does: two controller managers on one domain under one node name is a rig
# measuring a component it did not configure.
echo "== checking the domain is clear =="
for attempt in $(seq 1 12); do
    EXISTING="$(ros2 node list 2>/dev/null | grep -c 'cite/cell_a/arm_1/controller_manager' || true)"
    [ "$EXISTING" = "0" ] && break
    echo "   ${EXISTING} controller_manager(s) still on domain ${ROS_DOMAIN_ID}; waiting"
    sleep 5
done
if [ "${EXISTING:-0}" != "0" ]; then
    echo "ABORT: another controller manager is on domain ${ROS_DOMAIN_ID}" >&2
    exit 2
fi

# The fixture is test-only by construction (ADR-0040). Prove it is present before
# claiming a null: rule N distinguishes "did not reproduce" from "was never asked".
echo "== the fixture is present =="
ros2 pkg prefix cite_test_hardware
find "${ROOT}/workspace/install/cite_test_hardware" -name 'libjoint_stop_system*' -o -name 'joint_stop_system*' | head -5

bash "${HERE}/build.sh"

uptime | tee "${OUTDIR}/logs/FP_load.txt"

cleanup() {
    pkill -9 -f ros2_control_node 2>/dev/null
    sleep 2
}
trap cleanup EXIT

python3 "${HERE}/measure_fp.py" --out "${OUTDIR}" --repeats "${REPEATS}" \
    2>&1 | tee "${OUTDIR}/logs/FP_harness.log"
RC=${PIPESTATUS[0]}
echo "== harness exited ${RC} =="
exit "$RC"
