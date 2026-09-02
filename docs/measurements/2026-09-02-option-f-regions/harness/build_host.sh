#!/usr/bin/env bash
# Compile `predicate_eval` on the HOST, from the same shipped sources as `build.sh`.
#
# DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/build_host.sh`,
# copied at commit `eeaf903`. That directory is frozen and nothing in it is edited here.
#
# WHY BOTH. The container build is what every arm uses, because every arm runs there.
# This exists so that `arithmetic.py`'s section 2 cross-check can be checked against the
# shipped functions from a machine with no ROS at all -- which is the same reason the L0
# layer is ROS-free. `gripper.cpp` uses nothing but `<algorithm>` and `<cmath>`, so this
# is a portable compile and not a port.
#
# The two binaries are NOT assumed to agree. Any figure taken from the host build is
# recorded as such in the trial record's `predicate_build` field.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../../.." && pwd)"
SKILLS="${ROOT}/workspace/src/cite_skills"

test -f "${SKILLS}/src/gripper.cpp"
test -f "${SKILLS}/include/cite_skills/gripper.hpp"

mkdir -p "${HERE}/../raw"
{
    echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "where=host"
    echo "commit=$(git -C "${ROOT}" rev-parse HEAD)"
    echo "gripper_cpp_sha256=$(shasum -a 256 "${SKILLS}/src/gripper.cpp" | cut -d' ' -f1)"
    echo "gripper_hpp_sha256=$(shasum -a 256 "${SKILLS}/include/cite_skills/gripper.hpp" | cut -d' ' -f1)"
    echo "compiler=$(c++ --version | head -1)"
} > "${HERE}/../raw/predicate_eval_host_provenance.txt"

c++ -std=c++17 -O2 -Wall -Wextra -Werror \
    -I "${SKILLS}/include" \
    -o "${HERE}/predicate_eval_host" \
    "${HERE}/predicate_eval.cpp" \
    "${SKILLS}/src/gripper.cpp"

{
    echo "predicate_eval_host_sha256=$(shasum -a 256 "${HERE}/predicate_eval_host" | cut -d' ' -f1)"
} >> "${HERE}/../raw/predicate_eval_host_provenance.txt"

echo "built ${HERE}/predicate_eval_host"
cat "${HERE}/../raw/predicate_eval_host_provenance.txt"
