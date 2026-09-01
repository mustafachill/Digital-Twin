#!/usr/bin/env bash
# Compile `predicate_eval` on the HOST, from the same shipped sources as `build.sh`.
#
# WHY BOTH. The AR arm runs on the host, because the validator half of it is
# `cite_tools`, which lives in the host virtualenv. The FP arm runs in the container,
# because its other half is a real `ros2_control_node`. The same program is therefore
# built twice, by two compilers, from the same two files -- and `measure_ar.py` records
# which build answered it. `gripper.cpp` uses nothing but `<algorithm>` and `<cmath>`, so
# this is a portable compile and not a port.
#
# The two binaries are NOT assumed to agree: `analyse.py` re-runs the AR cross-check
# through whichever binary is present and reports if they ever differ.
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

echo "built ${HERE}/predicate_eval_host"
cat "${HERE}/../raw/predicate_eval_host_provenance.txt"
