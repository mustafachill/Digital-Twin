#!/usr/bin/env bash
# Compile `predicate_eval` against the SHIPPED gripper source. Runs INSIDE the container.
#
# DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/build.sh`,
# copied at commit `eeaf903`. That directory is frozen and nothing in it is edited here.
# One change: this also builds `predicate_eval_superseded`, because `criteria.md` V10
# makes the comparison quantity a BUILD of `4ef2d7c` rather than a rewrite, and a
# campaign that had to remember to run a second script would eventually forget.
#
# The two paths below are the whole point of this script and are stated rather than
# globbed: the header and the translation unit both come from `workspace/src/cite_skills`
# unmodified, so the predicate this campaign measures is the predicate that ships.
# `cite_skills` exports no library (its CMakeLists compiles `gripper.cpp` straight into
# `skill_server`), which is why this compiles the source instead of linking an artefact.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS=/workspace/workspace/src/cite_skills

test -f "${SKILLS}/src/gripper.cpp"
test -f "${SKILLS}/include/cite_skills/gripper.hpp"

# Recorded so that a rebuild that silently picked up an edited tree is visible in raw/.
mkdir -p "${HERE}/../raw"
{
    echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "where=container"
    echo "commit=$(git -C /workspace rev-parse HEAD)"
    echo "gripper_cpp_sha256=$(sha256sum "${SKILLS}/src/gripper.cpp" | cut -d' ' -f1)"
    echo "gripper_hpp_sha256=$(sha256sum "${SKILLS}/include/cite_skills/gripper.hpp" | cut -d' ' -f1)"
    echo "compiler=$(g++ --version | head -1)"
} > "${HERE}/../raw/predicate_eval_provenance.txt"

g++ -std=c++17 -O2 -Wall -Wextra -Werror \
    -I "${SKILLS}/include" \
    -o "${HERE}/predicate_eval" \
    "${HERE}/predicate_eval.cpp" \
    "${SKILLS}/src/gripper.cpp"

{
    echo "predicate_eval_sha256=$(sha256sum "${HERE}/predicate_eval" | cut -d' ' -f1)"
} >> "${HERE}/../raw/predicate_eval_provenance.txt"

echo "built ${HERE}/predicate_eval"
cat "${HERE}/../raw/predicate_eval_provenance.txt"

bash "${HERE}/build_superseded.sh" /workspace
